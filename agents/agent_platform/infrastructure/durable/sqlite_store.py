"""SQLite persistence adapter for provider-neutral durable Agent tasks."""

from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterator, Mapping, Optional

from .task import TaskSubmission


_TASK_TRANSITIONS = {
    "queued": {"queued", "running", "paused", "cancelled", "failed"},
    "running": {
        "running", "succeeded", "failed", "partially_failed", "awaiting_input",
        "cancelling", "cancelled", "recovery_required",
    },
    "paused": {"paused", "queued", "cancelling", "cancelled"},
    "cancelling": {
        "cancelling", "cancelled", "failed", "partially_failed",
        "awaiting_input", "recovery_required",
    },
    "recovery_required": {"recovery_required", "queued", "cancelled"},
    "succeeded": {"succeeded"},
    "failed": {"failed"},
    "partially_failed": {"partially_failed", "recovery_required", "queued", "failed"},
    "awaiting_input": {"awaiting_input", "queued", "cancelled"},
    "cancelled": {"cancelled"},
}
_TERMINAL = {
    "succeeded", "failed", "partially_failed", "awaiting_input",
    "cancelled", "recovery_required",
}


def _now() -> datetime:
    return datetime.now()


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _load(value: Any, fallback: Any) -> Any:
    if value is None:
        return fallback
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return fallback


class SQLiteTaskQueueStore:
    """TaskQueueStore backed by a standalone SQLite database.

    SQLite supports multiple processes for local deployments, but remains a
    single-host, single-writer database and is not a distributed SQL backend.
    """

    def __init__(self, database: str | Path, *, timeout_seconds: float = 10.0):
        self.database = str(database)
        self.timeout_seconds = max(0.1, float(timeout_seconds))
        self._lock = threading.RLock()
        self._closed = False
        self._connection = sqlite3.connect(
            self.database, timeout=self.timeout_seconds,
            check_same_thread=False,
        )
        self._connection.row_factory = sqlite3.Row
        if self.database != ":memory:":
            self._connection.execute("PRAGMA journal_mode = WAL")
            self._connection.execute("PRAGMA synchronous = NORMAL")
        self._create_schema()

    @property
    def is_closed(self) -> bool:
        return self._closed

    def _conn(self) -> sqlite3.Connection:
        if self._closed:
            raise RuntimeError("SQLiteTaskQueueStore is closed")
        return self._connection

    def _transaction(self):
        """Serialize writers and make claims atomic across connections."""
        connection = self._conn()
        connection.execute("BEGIN IMMEDIATE")
        return connection

    @contextmanager
    def _write_transaction(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            connection = self._transaction()
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
            connection = self._conn()
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS agent_tasks (
                    task_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    status TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    result TEXT,
                    error TEXT,
                    idempotency_key TEXT,
                    workflow_id TEXT,
                    metadata TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT,
                    lease_owner TEXT,
                    lease_expires_at TEXT
                );
                CREATE UNIQUE INDEX IF NOT EXISTS uq_agent_tasks_idempotency
                    ON agent_tasks(tenant_id, user_id, idempotency_key)
                    WHERE idempotency_key IS NOT NULL;
                CREATE INDEX IF NOT EXISTS ix_agent_tasks_queue
                    ON agent_tasks(status, updated_at);
                CREATE TABLE IF NOT EXISTS agent_workers (
                    worker_id TEXT PRIMARY KEY,
                    worker_kind TEXT NOT NULL,
                    status TEXT NOT NULL,
                    metadata TEXT NOT NULL DEFAULT '{}',
                    started_at TEXT NOT NULL,
                    last_heartbeat_at TEXT NOT NULL,
                    lease_expires_at TEXT
                );
                """
            )

    @staticmethod
    def _record(row: Optional[sqlite3.Row]) -> Optional[TaskSubmission]:
        if row is None:
            return None
        return TaskSubmission(
            task_id=row["task_id"], tenant_id=row["tenant_id"],
            user_id=row["user_id"], kind=row["kind"], status=row["status"],
            payload=_load(row["payload"], {}), result=_load(row["result"], None),
            error=row["error"], idempotency_key=row["idempotency_key"],
            workflow_id=row["workflow_id"], metadata=_load(row["metadata"], {}),
            created_at=row["created_at"], updated_at=row["updated_at"],
            started_at=row["started_at"], finished_at=row["finished_at"],
            lease_owner=row["lease_owner"], lease_expires_at=row["lease_expires_at"],
        )

    def create_task(self, record: TaskSubmission) -> TaskSubmission:
        if not all(str(getattr(record, field, "") or "").strip() for field in (
            "task_id", "tenant_id", "user_id", "kind",
        )):
            raise ValueError("task identity, tenant, user and kind are required")
        if record.status not in _TASK_TRANSITIONS:
            raise ValueError("unsupported initial task status")
        if not isinstance(record.payload, Mapping) or not isinstance(record.metadata, Mapping):
            raise ValueError("task payload and metadata must be objects")
        with self._write_transaction() as connection:
            connection.execute(
                """INSERT INTO agent_tasks (
                   task_id, tenant_id, user_id, kind, status, payload, result,
                   error, idempotency_key, workflow_id, metadata, created_at,
                   updated_at, started_at, finished_at, lease_owner, lease_expires_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    record.task_id, record.tenant_id, record.user_id, record.kind,
                    record.status, _json(record.payload or {}),
                    _json(record.result) if record.result is not None else None,
                    record.error, record.idempotency_key, record.workflow_id,
                    _json(record.metadata or {}), record.created_at or _now().isoformat(),
                    record.updated_at or _now().isoformat(), record.started_at,
                    record.finished_at, record.lease_owner, record.lease_expires_at,
                ),
            )
        return record

    def get_task(
        self, task_id: str, tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Optional[TaskSubmission]:
        query = "SELECT * FROM agent_tasks WHERE task_id = ?"
        params: list[Any] = [str(task_id)]
        if tenant_id is not None:
            query += " AND tenant_id = ?"
            params.append(str(tenant_id))
        if user_id is not None:
            query += " AND user_id = ?"
            params.append(str(user_id))
        with self._lock:
            return self._record(self._conn().execute(query, params).fetchone())

    def find_task_by_idempotency(
        self, tenant_id: str, user_id: str, idempotency_key: str,
    ) -> Optional[TaskSubmission]:
        with self._lock:
            row = self._conn().execute(
                """SELECT * FROM agent_tasks
                   WHERE tenant_id = ? AND user_id = ? AND idempotency_key = ?""",
                (str(tenant_id), str(user_id), str(idempotency_key)),
            ).fetchone()
            return self._record(row)

    def list_tasks(
        self, tenant_id: Optional[str] = None, user_id: Optional[str] = None,
        statuses: Optional[list[str]] = None, limit: int = 50,
    ) -> list[TaskSubmission]:
        query = "SELECT * FROM agent_tasks WHERE 1 = 1"
        params: list[Any] = []
        if tenant_id is not None:
            query += " AND tenant_id = ?"
            params.append(str(tenant_id))
        if user_id is not None:
            query += " AND user_id = ?"
            params.append(str(user_id))
        if statuses:
            query += " AND status IN (" + ",".join("?" for _ in statuses) + ")"
            params.extend(str(status) for status in statuses)
        query += " ORDER BY updated_at DESC LIMIT ?"
        params.append(max(1, min(int(limit), 200)))
        with self._lock:
            rows = self._conn().execute(query, params).fetchall()
            return [self._record(row) for row in rows]

    def claim_task(
        self, task_id: str, lease_owner: str, lease_seconds: float = 300.0,
    ) -> Optional[TaskSubmission]:
        if not lease_owner or float(lease_seconds) <= 0:
            return None
        now = _now()
        with self._write_transaction() as connection:
            cursor = connection.execute(
                """UPDATE agent_tasks SET status = 'running', updated_at = ?,
                   started_at = COALESCE(started_at, ?), lease_owner = ?,
                   lease_expires_at = ? WHERE task_id = ? AND status = 'queued'""",
                (now.isoformat(), now.isoformat(), str(lease_owner),
                 (now + timedelta(seconds=float(lease_seconds))).isoformat(),
                 str(task_id)),
            )
            row = connection.execute(
                "SELECT * FROM agent_tasks WHERE task_id = ?", (str(task_id),)
            ).fetchone() if cursor.rowcount else None
        return self._record(row)

    def heartbeat_task(
        self, task_id: str, lease_owner: str, lease_seconds: float = 300.0,
    ) -> bool:
        if not lease_owner or float(lease_seconds) <= 0:
            return False
        now = _now()
        with self._write_transaction() as connection:
            cursor = connection.execute(
                """UPDATE agent_tasks SET updated_at = ?, lease_expires_at = ?
                   WHERE task_id = ? AND lease_owner = ?
                   AND status IN ('running', 'cancelling')""",
                (now.isoformat(), (now + timedelta(seconds=float(lease_seconds))).isoformat(),
                 str(task_id), str(lease_owner)),
            )
            return cursor.rowcount == 1

    def update_task(
        self, task_id: str, status: str, *, result: Optional[dict] = None,
        error: Optional[str] = None, metadata: Optional[dict] = None,
        workflow_id: Optional[str] = None, expected_statuses: Optional[list[str]] = None,
    ) -> bool:
        with self._write_transaction() as connection:
            row = connection.execute(
                "SELECT status, metadata FROM agent_tasks WHERE task_id = ?",
                (str(task_id),),
            ).fetchone()
            if row is None or (expected_statuses and row["status"] not in expected_statuses):
                return False
            if status not in _TASK_TRANSITIONS.get(row["status"], set()):
                return False
            merged = _load(row["metadata"], {})
            merged.update(metadata or {})
            terminal = status in _TERMINAL
            now = _now().isoformat()
            cursor = connection.execute(
                """UPDATE agent_tasks SET status = ?, error = ?, metadata = ?, updated_at = ?,
                   result = COALESCE(?, result), workflow_id = COALESCE(?, workflow_id),
                   finished_at = CASE WHEN ? THEN COALESCE(finished_at, ?) ELSE finished_at END,
                   lease_owner = CASE WHEN ? THEN NULL ELSE lease_owner END,
                   lease_expires_at = CASE WHEN ? THEN NULL ELSE lease_expires_at END
                   WHERE task_id = ?""",
                (status, error, _json(merged), now,
                 _json(result) if result is not None else None,
                 str(workflow_id) if workflow_id is not None else None,
                 terminal, now, terminal, terminal, str(task_id)),
            )
            return cursor.rowcount == 1

    def pause_task(self, task_id: str, tenant_id: Optional[str] = None,
                   user_id: Optional[str] = None) -> Optional[TaskSubmission]:
        return self._set_queued_state(task_id, "paused", tenant_id, user_id)

    def resume_task(self, task_id: str, tenant_id: Optional[str] = None,
                    user_id: Optional[str] = None) -> Optional[TaskSubmission]:
        return self._set_queued_state(task_id, "queued", tenant_id, user_id, source="paused")

    def _set_queued_state(
        self, task_id: str, target: str, tenant_id: Optional[str],
        user_id: Optional[str], source: str = "queued",
    ) -> Optional[TaskSubmission]:
        query = "UPDATE agent_tasks SET status = ?, updated_at = ? WHERE task_id = ? AND status = ?"
        params: list[Any] = [target, _now().isoformat(), str(task_id), source]
        if tenant_id is not None:
            query += " AND tenant_id = ?"
            params.append(str(tenant_id))
        if user_id is not None:
            query += " AND user_id = ?"
            params.append(str(user_id))
        with self._write_transaction() as connection:
            connection.execute(query, params)
        return self.get_task(task_id, tenant_id=tenant_id, user_id=user_id)

    def cancel_task(self, task_id: str, tenant_id: Optional[str] = None,
                    user_id: Optional[str] = None) -> Optional[TaskSubmission]:
        query = "SELECT * FROM agent_tasks WHERE task_id = ?"
        params: list[Any] = [str(task_id)]
        if tenant_id is not None:
            query += " AND tenant_id = ?"
            params.append(str(tenant_id))
        if user_id is not None:
            query += " AND user_id = ?"
            params.append(str(user_id))
        with self._write_transaction() as connection:
            row = connection.execute(query, params).fetchone()
            if row is None:
                return None
            current = row["status"]
            if current in {"queued", "paused"}:
                target = "cancelled"
            elif current in {"running", "cancelling"}:
                target = "cancelling"
            else:
                return self._record(row)
            metadata = _load(row["metadata"], {})
            metadata["cancellation_requested"] = True
            finished = _now().isoformat() if target == "cancelled" else None
            connection.execute(
                """UPDATE agent_tasks SET status = ?, metadata = ?, updated_at = ?,
                   finished_at = COALESCE(?, finished_at)
                   WHERE task_id = ?""",
                (target, _json(metadata), _now().isoformat(), finished, str(task_id)),
            )
        return self.get_task(task_id, tenant_id=tenant_id, user_id=user_id)

    def recover_stale_tasks(self, stale_after_seconds: float = 300.0) -> int:
        if float(stale_after_seconds) <= 0:
            return 0
        now = _now()
        cutoff = (now - timedelta(seconds=float(stale_after_seconds))).isoformat()
        with self._write_transaction() as connection:
            rows = connection.execute(
                """SELECT task_id, metadata FROM agent_tasks
                   WHERE status IN ('running', 'cancelling')
                   AND (updated_at <= ? OR lease_expires_at <= ?)""",
                (cutoff, now.isoformat()),
            ).fetchall()
            for row in rows:
                metadata = _load(row["metadata"], {})
                metadata["recovery_reason"] = "stale_task"
                connection.execute(
                    """UPDATE agent_tasks SET status = 'recovery_required',
                       updated_at = ?, finished_at = COALESCE(finished_at, ?),
                       lease_owner = NULL, lease_expires_at = NULL, metadata = ?
                       WHERE task_id = ? AND status IN ('running', 'cancelling')""",
                    (now.isoformat(), now.isoformat(), _json(metadata), row["task_id"]),
                )
        return len(rows)

    def requeue_recovery_task(
        self, task_id: str, *, recovery_reference: str,
        tenant_id: Optional[str] = None, user_id: Optional[str] = None,
    ) -> Optional[TaskSubmission]:
        reference = str(recovery_reference or "").strip()[:255]
        if not reference:
            raise ValueError("recovery_reference is required")
        query = (
            "SELECT metadata FROM agent_tasks "
            "WHERE task_id = ? AND status = 'recovery_required'"
        )
        params: list[Any] = [str(task_id)]
        if tenant_id is not None:
            query += " AND tenant_id = ?"
            params.append(str(tenant_id))
        if user_id is not None:
            query += " AND user_id = ?"
            params.append(str(user_id))
        now = _now().isoformat()
        with self._write_transaction() as connection:
            row = connection.execute(query, params).fetchone()
            if row is None:
                return None
            metadata = _load(row["metadata"], {})
            metadata.update({
                "recovery_action": "operator_requeue",
                "recovery_reference": reference,
                "requeued_at": now,
            })
            connection.execute(
                """UPDATE agent_tasks SET status = 'queued', error = NULL, result = NULL,
                   updated_at = ?, started_at = NULL, finished_at = NULL,
                   lease_owner = NULL, lease_expires_at = NULL, metadata = ?
                   WHERE task_id = ? AND status = 'recovery_required'""",
                (now, _json(metadata), str(task_id)),
            )
        return self.get_task(task_id, tenant_id=tenant_id, user_id=user_id)

    def register_worker(
        self, worker_id: str, worker_kind: str, *,
        metadata: Optional[Mapping[str, Any]] = None, lease_seconds: float = 30.0,
    ) -> None:
        now = _now()
        expires = now + timedelta(seconds=max(1.0, float(lease_seconds)))
        with self._write_transaction() as connection:
            connection.execute(
                """INSERT INTO agent_workers (
                   worker_id, worker_kind, status, metadata, started_at,
                   last_heartbeat_at, lease_expires_at
                   ) VALUES (?, ?, 'running', ?, ?, ?, ?)
                   ON CONFLICT(worker_id) DO UPDATE SET
                   worker_kind = excluded.worker_kind, status = 'running',
                   metadata = excluded.metadata, last_heartbeat_at = excluded.last_heartbeat_at,
                   lease_expires_at = excluded.lease_expires_at""",
                (str(worker_id), str(worker_kind), _json(metadata or {}), now.isoformat(),
                 now.isoformat(), expires.isoformat()),
            )

    def heartbeat_worker(self, worker_id: str, *, lease_seconds: float = 30.0) -> bool:
        now = _now()
        with self._write_transaction() as connection:
            cursor = connection.execute(
                """UPDATE agent_workers SET status = 'running', last_heartbeat_at = ?,
                   lease_expires_at = ? WHERE worker_id = ?""",
                (now.isoformat(),
                 (now + timedelta(seconds=max(1.0, float(lease_seconds)))).isoformat(),
                 str(worker_id)),
            )
            return cursor.rowcount == 1

    def unregister_worker(self, worker_id: str) -> bool:
        now = _now().isoformat()
        with self._write_transaction() as connection:
            cursor = connection.execute(
                """UPDATE agent_workers SET status = 'stopped',
                   last_heartbeat_at = ?, lease_expires_at = NULL WHERE worker_id = ?""",
                (now, str(worker_id)),
            )
            return cursor.rowcount == 1

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._connection.close()
            self._closed = True

    def __enter__(self) -> "SQLiteTaskQueueStore":
        self._conn()
        return self

    def __exit__(self, *_exc: Any) -> None:
        self.close()


__all__ = ["SQLiteTaskQueueStore"]
