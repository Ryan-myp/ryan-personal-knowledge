"""MySQL persistence backend for the ad-agent.

The domain store keeps its SQL behind the persistence boundary.  This adapter
reuses the existing backend methods while translating the small SQLite syntax
surface used by the current store and overrides claims with InnoDB row locks.
Runtime, Skills, and Tools do not know which database is active.
"""

from __future__ import annotations

import threading
import uuid
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from urllib.parse import parse_qs, unquote, urlparse
from pymysql.err import MySQLError

from .models import (
    ConversationMessagePage, ConversationMessageRecord,
    OutboxEvent,
    TaskRecord,
    ScheduledTaskRecord,
    ScheduledTaskRunRecord,
)
from .conversation_pagination import (
    list_conversation_message_page as query_conversation_message_page,
)
from .store import AdAgentStore
from .mysql_pool import _MySQLPool
from .mysql_connection import _MySQLConnection, _retry_transaction
from .mysql_sql import _mysql_schema
from .mysql_migrations import apply_mysql_migration


class MySQLStore(AdAgentStore):
    """InnoDB implementation of the existing ``PersistenceBackend`` contract."""

    backend_name = "mysql"

    def __init__(
        self, database_url: str, *, pool_size: int = 5,
        max_overflow: int = 10, connect_timeout: int = 10,
    ):
        if not str(database_url).startswith(("mysql://", "mysql+pymysql://")):
            raise ValueError("MySQLStore requires mysql:// or mysql+pymysql://")
        self._database_url = str(database_url)
        self.pool_size = max(1, int(pool_size))
        self.max_overflow = max(0, int(max_overflow))
        self.connect_timeout = max(1, int(connect_timeout))
        self._pool = _MySQLPool(
            self._connect,
            pool_size=self.pool_size,
            max_overflow=self.max_overflow,
        )
        self._mysql_conn: Optional[_MySQLConnection] = None
        self._mysql_connect_lock = threading.RLock()
        super().__init__(database_url)

    def _connect(self) -> _MySQLConnection:
        try:
            import pymysql
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "MySQL backend requires PyMySQL; install the repository requirements.txt"
            ) from exc
        parsed = urlparse(self._database_url.replace("mysql+pymysql://", "mysql://", 1))
        if not parsed.hostname or not parsed.path.strip("/"):
            raise ValueError("MySQL URL must include host and database name")
        query = parse_qs(parsed.query)
        kwargs: dict[str, Any] = {
            "host": parsed.hostname, "port": int(parsed.port or 3306),
            "user": unquote(parsed.username or ""),
            "password": unquote(parsed.password or ""),
            "database": parsed.path.strip("/"), "charset": "utf8mb4",
            "autocommit": False, "connect_timeout": self.connect_timeout,
        }
        if query.get("unix_socket"):
            kwargs["unix_socket"] = query["unix_socket"][0]
        return pymysql.connect(**kwargs)

    def _get_conn(self) -> _MySQLConnection:
        with self._mysql_connect_lock:
            if self._mysql_conn is None:
                self._mysql_conn = _MySQLConnection(self._pool)
            return self._mysql_conn

    def close(self) -> None:
        """Close all idle pooled connections and prevent new borrows."""
        with self._mysql_connect_lock:
            if self._pool:
                self._pool.close()
            self._mysql_conn = None

    @property
    def is_closed(self) -> bool:
        return bool(self._pool.metrics().get("closed"))

    def get_backend_health(self) -> dict[str, Any]:
        try:
            with self._lock:
                self._get_conn().execute("SELECT 1").fetchone()
            return {
                "backend": self.backend_name,
                "status": "healthy",
                "pool": self._pool.metrics(),
            }
        except (MySQLError, OSError, RuntimeError, ValueError) as exc:
            return {
                "backend": self.backend_name,
                "status": "unhealthy",
                "error": type(exc).__name__,
                "pool": self._pool.metrics(),
            }

    def reserve_write(
        self, idempotency_key: str, ttl_seconds: int = 300,
        request_hash: Optional[str] = None,
    ) -> bool:
        """Atomically reserve one replay key with an InnoDB row lock."""
        conn = self._get_conn()
        with conn.transaction():
            now = datetime.now(timezone.utc)
            row = conn.execute(
                "SELECT status, updated_at, request_hash "
                "FROM write_reservations WHERE idempotency_key = ? FOR UPDATE",
                (str(idempotency_key),),
            ).fetchone()
            if row:
                if (
                    row["request_hash"]
                    and request_hash
                    and str(row["request_hash"]) != str(request_hash)
                ):
                    return False
                try:
                    age = (
                        now - datetime.fromisoformat(str(row["updated_at"]))
                    ).total_seconds()
                except (TypeError, ValueError):
                    age = 0
                if age < float(ttl_seconds):
                    return False
            timestamp = now.isoformat()
            conn.execute(
                """INSERT INTO write_reservations
                   (idempotency_key, request_hash, status, created_at, updated_at)
                   VALUES (?, ?, 'pending', ?, ?)
                   ON DUPLICATE KEY UPDATE
                     request_hash = VALUES(request_hash),
                     status = 'pending',
                     created_at = VALUES(created_at),
                     updated_at = VALUES(updated_at)""",
                (str(idempotency_key), request_hash, timestamp, timestamp),
            )
            return True

    def mark_write_executed(
        self, idempotency_key: str, request_hash: Optional[str] = None,
    ) -> None:
        conn = self._get_conn()
        conn.execute(
            "UPDATE write_reservations SET status = ?, updated_at = ? "
            "WHERE idempotency_key = ? AND "
            "(request_hash IS NULL OR request_hash = ?)",
            (
                "executed", datetime.now(timezone.utc).isoformat(),
                str(idempotency_key), request_hash,
            ),
        )

    def release_write(
        self, idempotency_key: str, request_hash: Optional[str] = None,
    ) -> None:
        conn = self._get_conn()
        conn.execute(
            "DELETE FROM write_reservations WHERE idempotency_key = ? "
            "AND status = 'pending' AND "
            "(request_hash IS NULL OR request_hash = ?)",
            (str(idempotency_key), request_hash),
        )

    def record_conversation_message(
        self, record: ConversationMessageRecord,
    ) -> None:
        data = record.to_dict()
        self._get_conn().execute(
            """INSERT INTO conversation_messages
               (message_id, session_id, turn_id, role, content, created_at,
                tool_call_id, name, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON DUPLICATE KEY UPDATE
                 turn_id = VALUES(turn_id), role = VALUES(role),
                 content = VALUES(content), created_at = VALUES(created_at),
                 tool_call_id = VALUES(tool_call_id), name = VALUES(name),
                 metadata = VALUES(metadata)""",
            (
                data["message_id"], data["session_id"], data["turn_id"],
                data["role"], data["content"], data["created_at"],
                data.get("tool_call_id"), data.get("name"),
                json.dumps(data.get("metadata") or {}, ensure_ascii=False),
            ),
        )

    def list_conversation_messages(
        self, session_id: str, limit: int = 200,
    ) -> list[ConversationMessageRecord]:
        rows = self._get_conn().execute(
            """SELECT * FROM conversation_messages
               WHERE session_id = ?
               ORDER BY created_at DESC, message_id DESC LIMIT ?""",
            (str(session_id), max(1, int(limit))),
        ).fetchall()
        return [
            ConversationMessageRecord.from_row(dict(row))
            for row in reversed(rows)
        ]

    def list_conversation_message_page(
        self,
        session_id: str,
        limit: int = 10,
        before_message_id: Optional[str] = None,
    ) -> ConversationMessagePage:
        return query_conversation_message_page(
            self._get_conn(),
            session_id,
            limit=limit,
            before_message_id=before_message_id,
        )

    def update_conversation_message_metadata(
        self,
        session_id: str,
        turn_id: str,
        role: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> int:
        """Merge metadata into matching transcript rows without changing content."""
        conn = self._get_conn()
        rows = conn.execute(
            """SELECT message_id, metadata
               FROM conversation_messages
               WHERE session_id = ? AND turn_id = ? AND role = ?""",
            (str(session_id), str(turn_id), str(role)),
        ).fetchall()
        if not rows:
            return 0
        updates = []
        for row in rows:
            current = row["metadata"]
            if isinstance(current, str):
                try:
                    current = json.loads(current or "{}")
                except (TypeError, ValueError):
                    current = {}
            merged = dict(current) if isinstance(current, dict) else {}
            merged.update(dict(metadata or {}))
            updates.append((
                json.dumps(merged, ensure_ascii=False, default=str),
                str(row["message_id"]),
            ))
        conn.executemany(
            "UPDATE conversation_messages SET metadata = ? WHERE message_id = ?",
            updates,
        )
        conn.commit()
        return len(updates)


    def _init_db(self) -> None:
        with self._lock:
            conn = self._get_conn()
            conn.executescript(_mysql_schema(self.SCHEMA))
            applied = {
                int(row["version"])
                for row in conn.execute("SELECT version FROM schema_migrations").fetchall()
            }
            if not applied:
                # The current DDL is complete; record its migration baseline.
                for version in range(1, self.SCHEMA_VERSION + 1):
                    conn.execute(
                        "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                        (version, datetime.now(timezone.utc).isoformat()),
                    )
            else:
                for version in range(1, self.SCHEMA_VERSION + 1):
                    if version in applied:
                        continue
                    apply_mysql_migration(conn, version)
                    conn.execute(
                        "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                        (version, datetime.now(timezone.utc).isoformat()),
                    )
            conn.commit()


    def claim_task(
        self, task_id: str, lease_owner: str, lease_seconds: float = 300.0,
    ) -> Optional[TaskRecord]:
        return _retry_transaction(
            lambda: self._claim_task_once(task_id, lease_owner, lease_seconds)
        )

    def _claim_task_once(
        self, task_id: str, lease_owner: str, lease_seconds: float = 300.0,
    ) -> Optional[TaskRecord]:
        if not lease_owner or float(lease_seconds) <= 0:
            return None
        now = datetime.now(timezone.utc)
        with self._lock:
            conn = self._get_conn()
            with conn.transaction():
                row = conn.execute(
                    "SELECT * FROM tasks WHERE task_id = ? FOR UPDATE", (str(task_id),)
                ).fetchone()
                if not row or str(row["status"]) != "queued":
                    return None
                conn.execute(
                    """UPDATE tasks SET status = 'running', updated_at = ?,
                       started_at = COALESCE(started_at, ?), lease_owner = ?,
                       lease_expires_at = ? WHERE task_id = ? AND status = 'queued'""",
                    (
                        now.isoformat(), now.isoformat(), str(lease_owner),
                        (now + timedelta(seconds=float(lease_seconds))).isoformat(),
                        str(task_id),
                    ),
                )
                claimed = conn.execute(
                    "SELECT * FROM tasks WHERE task_id = ?", (str(task_id),)
                ).fetchone()
                return self._task_from_row(claimed)

    def claim_outbox_events(
        self, limit: int = 20, consumer_id: Optional[str] = None,
    ) -> list[OutboxEvent]:
        return _retry_transaction(
            lambda: self._claim_outbox_events_once(limit, consumer_id)
        )

    def _claim_outbox_events_once(
        self, limit: int = 20, consumer_id: Optional[str] = None,
    ) -> list[OutboxEvent]:
        bounded_limit = max(1, min(int(limit), 100))
        owner = str(consumer_id or f"consumer:{uuid.uuid4().hex}")
        now = datetime.now(timezone.utc)
        with self._lock:
            conn = self._get_conn()
            with conn.transaction():
                conn.execute(
                    """UPDATE outbox_events SET status = 'pending', claimed_by = NULL,
                       claimed_at = NULL WHERE status = 'claimed' AND claimed_at IS NOT NULL
                       AND claimed_at < ?""",
                    ((now - timedelta(minutes=5)).isoformat(),),
                )
                rows = conn.execute(
                    """SELECT * FROM outbox_events
                       WHERE status = 'pending'
                         AND (next_retry_at IS NULL OR next_retry_at <= ?)
                       ORDER BY created_at ASC LIMIT ? FOR UPDATE SKIP LOCKED""",
                    (now.isoformat(), bounded_limit),
                ).fetchall()
                claimed: list[OutboxEvent] = []
                for row in rows:
                    conn.execute(
                        """UPDATE outbox_events SET status = 'claimed', claimed_by = ?,
                           claimed_at = ? WHERE event_id = ? AND status = 'pending'""",
                        (owner, now.isoformat(), str(row["event_id"])),
                    )
                    data = dict(row)
                    data.update({
                        "status": "claimed", "claimed_by": owner,
                        "claimed_at": now.isoformat(),
                    })
                    claimed.append(OutboxEvent.from_row(data))
                return claimed

    def claim_due_scheduled_tasks(
        self, now: str, lease_owner: str, lease_seconds: float = 60.0,
        limit: int = 20,
    ) -> list[tuple[ScheduledTaskRecord, ScheduledTaskRunRecord]]:
        return _retry_transaction(
            lambda: self._claim_due_scheduled_tasks_once(
                now, lease_owner, lease_seconds, limit
            )
        )

    def _claim_due_scheduled_tasks_once(
        self, now: str, lease_owner: str, lease_seconds: float = 60.0,
        limit: int = 20,
    ) -> list[tuple[ScheduledTaskRecord, ScheduledTaskRunRecord]]:
        """Claim recurring schedules with InnoDB row locks across instances."""
        if not lease_owner or float(lease_seconds) <= 0:
            return []
        now_value = str(now)
        expires = (datetime.now(timezone.utc) + timedelta(seconds=float(lease_seconds))).isoformat()
        claimed: list[tuple[ScheduledTaskRecord, ScheduledTaskRunRecord]] = []
        with self._lock:
            conn = self._get_conn()
            with conn.transaction():
                rows = conn.execute(
                    """SELECT * FROM scheduled_tasks
                       WHERE status = 'active' AND next_run_at IS NOT NULL
                         AND next_run_at <= ?
                         AND (lease_expires_at IS NULL OR lease_expires_at <= ?)
                       ORDER BY next_run_at ASC LIMIT ? FOR UPDATE SKIP LOCKED""",
                    (now_value, now_value, max(1, min(int(limit), 100))),
                ).fetchall()
                for row in rows:
                    schedule = ScheduledTaskRecord.from_row(dict(row))
                    scheduled_for = str(schedule.next_run_at)
                    conn.execute(
                        """UPDATE scheduled_tasks
                           SET lease_owner = ?, lease_expires_at = ?, updated_at = ?
                           WHERE schedule_id = ?""",
                        (str(lease_owner), expires, now_value, schedule.schedule_id),
                    )
                    run_row = conn.execute(
                        "SELECT * FROM scheduled_task_runs "
                        "WHERE schedule_id = ? AND scheduled_for = ? FOR UPDATE",
                        (schedule.schedule_id, scheduled_for),
                    ).fetchone()
                    if not run_row:
                        run = ScheduledTaskRunRecord(
                            schedule_run_id=str(uuid.uuid4()), schedule_id=schedule.schedule_id,
                            tenant_id=schedule.tenant_id, user_id=schedule.user_id,
                            scheduled_for=scheduled_for, created_at=now_value,
                        )
                        conn.execute(
                            """INSERT INTO scheduled_task_runs
                               (schedule_run_id, schedule_id, tenant_id, user_id, scheduled_for,
                                status, task_id, started_at, finished_at, error, result, created_at)
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                            (run.schedule_run_id, run.schedule_id, run.tenant_id, run.user_id,
                             run.scheduled_for, run.status, run.task_id, run.started_at,
                             run.finished_at, run.error, None, run.created_at),
                        )
                    else:
                        run = ScheduledTaskRunRecord.from_row(dict(run_row))
                    claimed.append((schedule, run))
        return claimed
