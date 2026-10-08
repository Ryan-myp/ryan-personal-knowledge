"""SQLite persistence adapter for generic Agent Run history and events."""

from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator, Mapping, Optional

from agents.agent_harness.redaction import redact_for_persistence


class SQLiteRunStore:
    """Persist Run lifecycle metadata and ordered, redacted events."""

    def __init__(self, database: str | Path, *, timeout_seconds: float = 10.0):
        self.database = str(database)
        self.timeout_seconds = max(0.1, float(timeout_seconds))
        self._lock = threading.RLock()
        self._closed = False
        self._connection = sqlite3.connect(
            self.database, timeout=self.timeout_seconds, check_same_thread=False,
        )
        self._connection.row_factory = sqlite3.Row
        if self.database != ":memory:":
            self._connection.execute("PRAGMA journal_mode = WAL")
            self._connection.execute("PRAGMA synchronous = NORMAL")
        self._create_schema()

    def _conn(self) -> sqlite3.Connection:
        if self._closed:
            raise RuntimeError("SQLiteRunStore is closed")
        return self._connection

    @contextmanager
    def _write_transaction(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            connection = self._conn()
            connection.execute("BEGIN IMMEDIATE")
            committed = False
            try:
                yield connection
                connection.commit()
                committed = True
            finally:
                if not committed and connection.in_transaction:
                    connection.rollback()

    def _create_schema(self) -> None:
        with self._lock:
            self._conn().executescript(
                """
                CREATE TABLE IF NOT EXISTS agent_runs (
                    run_id TEXT PRIMARY KEY,
                    turn_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    tenant_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    task_id TEXT,
                    execution_mode TEXT NOT NULL,
                    status TEXT NOT NULL,
                    metadata TEXT NOT NULL DEFAULT '{}',
                    started_at TEXT NOT NULL,
                    finished_at TEXT
                );
                CREATE INDEX IF NOT EXISTS ix_agent_runs_owner
                    ON agent_runs(tenant_id, user_id, started_at);
                CREATE TABLE IF NOT EXISTS agent_run_events (
                    run_id TEXT NOT NULL REFERENCES agent_runs(run_id) ON DELETE CASCADE,
                    seq INTEGER NOT NULL,
                    event TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (run_id, seq)
                );
                """
            )
            self._conn().execute("PRAGMA foreign_keys = ON")

    @staticmethod
    def _decode_run(row: Optional[sqlite3.Row]) -> Optional[dict[str, Any]]:
        if row is None:
            return None
        return {
            "run_id": row["run_id"],
            "turn_id": row["turn_id"],
            "session_id": row["session_id"],
            "tenant_id": row["tenant_id"],
            "user_id": row["user_id"],
            "task_id": row["task_id"],
            "execution_mode": row["execution_mode"],
            "status": row["status"],
            "metadata": json.loads(row["metadata"] or "{}"),
            "started_at": row["started_at"],
            "finished_at": row["finished_at"],
        }

    def start_run(self, **payload: Any) -> bool:
        required = ("run_id", "turn_id", "tenant_id", "user_id")
        values = {name: str(payload.get(name) or "").strip() for name in required}
        if not all(values.values()):
            raise ValueError("run, turn, tenant and user identity are required")
        now = datetime.now().isoformat()
        with self._write_transaction() as connection:
            cursor = connection.execute(
                """INSERT INTO agent_runs (
                   run_id, turn_id, session_id, tenant_id, user_id, task_id,
                   execution_mode, status, metadata, started_at
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, 'running', '{}', ?)
                   ON CONFLICT(run_id) DO NOTHING""",
                (
                    values["run_id"], values["turn_id"],
                    str(payload.get("session_id") or ""), values["tenant_id"],
                    values["user_id"],
                    str(payload["task_id"]) if payload.get("task_id") else None,
                    str(payload.get("execution_mode") or "dry_run"), now,
                ),
            )
            created = cursor.rowcount == 1
        return created

    def append_event(self, run_id: str, event: Mapping[str, Any]) -> bool:
        if not isinstance(event, Mapping):
            raise ValueError("run event must be an object")
        safe_event = redact_for_persistence(dict(event))
        with self._write_transaction() as connection:
            exists = connection.execute(
                "SELECT 1 FROM agent_runs WHERE run_id = ? AND finished_at IS NULL",
                (str(run_id),),
            ).fetchone()
            if exists is None:
                return False
            last = connection.execute(
                "SELECT MAX(seq) AS seq FROM agent_run_events WHERE run_id = ?",
                (str(run_id),),
            ).fetchone()["seq"]
            try:
                requested_seq = max(0, int(safe_event.get("seq", 0)))
            except (TypeError, ValueError, OverflowError):
                requested_seq = 0
            sequence = max(requested_seq, int(last or 0) + 1)
            safe_event["seq"] = sequence
            connection.execute(
                """INSERT INTO agent_run_events(run_id, seq, event, created_at)
                   VALUES (?, ?, ?, ?)""",
                (str(run_id), sequence,
                 json.dumps(safe_event, ensure_ascii=False, sort_keys=True, default=str),
                 datetime.now().isoformat()),
            )
        return True

    def finish_run(
        self, run_id: str, *, status: str,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> bool:
        if not str(status or "").strip():
            raise ValueError("run status is required")
        safe_metadata = redact_for_persistence(dict(metadata or {}))
        with self._write_transaction() as connection:
            row = connection.execute(
                "SELECT metadata FROM agent_runs WHERE run_id = ? AND finished_at IS NULL",
                (str(run_id),),
            ).fetchone()
            if row is None:
                return False
            current = json.loads(row["metadata"] or "{}")
            current.update(safe_metadata)
            cursor = connection.execute(
                """UPDATE agent_runs SET status = ?, metadata = ?, finished_at = ?
                   WHERE run_id = ? AND finished_at IS NULL""",
                (str(status), json.dumps(current, ensure_ascii=False, sort_keys=True),
                 datetime.now().isoformat(), str(run_id)),
            )
            return cursor.rowcount == 1

    def get_run(
        self, run_id: str, *, tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        query = "SELECT * FROM agent_runs WHERE run_id = ?"
        params: list[Any] = [str(run_id)]
        if tenant_id is not None:
            query += " AND tenant_id = ?"
            params.append(str(tenant_id))
        if user_id is not None:
            query += " AND user_id = ?"
            params.append(str(user_id))
        with self._lock:
            row = self._conn().execute(query, params).fetchone()
            return self._decode_run(row)

    def list_run_events(
        self, run_id: str, *, tenant_id: Optional[str] = None,
        user_id: Optional[str] = None, after_seq: int = 0, limit: int = 200,
    ) -> list[dict[str, Any]]:
        owner_query = "SELECT 1 FROM agent_runs WHERE run_id = ?"
        owner_params: list[Any] = [str(run_id)]
        if tenant_id is not None:
            owner_query += " AND tenant_id = ?"
            owner_params.append(str(tenant_id))
        if user_id is not None:
            owner_query += " AND user_id = ?"
            owner_params.append(str(user_id))
        bounded_limit = max(1, min(int(limit), 500))
        with self._lock:
            if self._conn().execute(owner_query, owner_params).fetchone() is None:
                return []
            rows = self._conn().execute(
                """SELECT seq, event, created_at FROM agent_run_events
                   WHERE run_id = ? AND seq > ? ORDER BY seq LIMIT ?""",
                (str(run_id), max(0, int(after_seq)), bounded_limit),
            ).fetchall()
            return [
                {"seq": row["seq"], "event": json.loads(row["event"]),
                 "created_at": row["created_at"]}
                for row in rows
            ]

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._connection.close()
            self._closed = True


__all__ = ["SQLiteRunStore"]
