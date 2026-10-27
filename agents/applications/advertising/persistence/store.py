"""
persistence/store.py - SQLite 持久化存储

Tables:
- sessions: session metadata
- conversation_messages: complete sanitized chat history
- tool_calls: tool invocation history (with input/output/status)
- campaign_state: campaign resource state (shared across sessions)
"""

import json
import sqlite3
import logging
import hashlib
import threading
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, List

from .models import (
    CampaignRecord, ConversationMessagePage, ConversationMessageRecord, KnowledgeDocumentRecord,
    RawKnowledgeSourceRecord,
    ExecutionRunRecord, TaskRecord, ToolCallRecord,
    OutboxEvent, ScheduledTaskRecord, ScheduledTaskRunRecord,
    CreationTemplateRecord,
)
from .conversation_feedback_store import (
    get_conversation_feedback_trend as query_conversation_feedback_trend,
    list_conversation_feedback_review_queue as query_feedback_review_queue,
    review_conversation_feedback as update_feedback_review,
    save_conversation_feedback as persist_conversation_feedback,
)
from .semantic_index_store import (
    get_knowledge_semantic_index_metadata as query_semantic_index_metadata,
    is_knowledge_semantic_index_current as check_semantic_index_current,
    rebuild_knowledge_semantic_index as persist_semantic_index,
    search_knowledge_semantic_index as query_semantic_index,
)
from .schema import DATABASE_SCHEMA, SCHEMA_VERSION
from .sqlite_migrations import apply_sqlite_migration
from .extension_store import ExtensionRepository
from .memory_store import MemoryRepository
from .session_store import SessionRepository
from .knowledge_store import KnowledgeRepository
from .workflow_store import WorkflowRepository
from .errors import PersistenceConflictError
from agents.agent_harness.core.memory import MemoryRecord

logger = logging.getLogger(__name__)


TASK_TRANSITIONS = {
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


class AdAgentStore:
    """Persistence facade with one connection/lock and domain repositories."""
    
    # Schema changes are tracked explicitly even while SQLite remains the
    # current single-process backend. This keeps the PersistenceBackend
    # boundary stable and gives a future MySQL/PostgreSQL adapter a concrete
    # migration contract instead of relying on scattered PRAGMA checks.
    SCHEMA_VERSION = SCHEMA_VERSION

    SCHEMA = DATABASE_SCHEMA
    
    def __init__(self, db_path: str = ":memory:"):
        self._db_path = db_path
        self._lock = threading.RLock()
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()
        self._extensions = ExtensionRepository(self._get_conn, self._lock)
        self._memories = MemoryRepository(self._get_conn, self._lock)
        self._sessions = SessionRepository(self._get_conn, self._lock)
        self._knowledge = KnowledgeRepository(self._get_conn, self._lock)
        self._workflows = WorkflowRepository(self._get_conn, self._lock)
    
    def _get_conn(self) -> sqlite3.Connection:
        """Get thread-safe database connection (single connection mode)"""
        if self._conn is None:
            self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._conn.execute("PRAGMA busy_timeout=5000")
        return self._conn
    
    def _init_db(self):
        """Create tables, migrate legacy columns, then install current indexes."""
        with self._lock:
            conn = self._get_conn()
            indexes = []
            statement = ""
            for line in self.SCHEMA.splitlines(keepends=True):
                statement += line
                if not sqlite3.complete_statement(statement):
                    continue
                sql = statement.strip()
                statement = ""
                if sql.upper().startswith(("CREATE INDEX", "CREATE UNIQUE INDEX")):
                    indexes.append(sql)
                elif sql:
                    conn.execute(sql)
            if statement.strip():
                raise ValueError("incomplete SQLite schema statement")
            applied = {
                int(row[0])
                for row in conn.execute("SELECT version FROM schema_migrations")
            }
            for version in range(1, self.SCHEMA_VERSION + 1):
                if version in applied:
                    continue
                apply_sqlite_migration(conn, version)
                conn.execute(
                    "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                    (version, datetime.now(timezone.utc).isoformat()),
                )
            for index in indexes:
                conn.execute(index)
            conn.commit()


    
    def close(self):
        """Close database connection"""
        with self._lock:
            if self._conn:
                self._conn.close()
                self._conn = None

    @property
    def is_closed(self) -> bool:
        """Expose backend lifecycle without leaking a connection object."""
        return self._conn is None

    # -- Durable worker liveness -------------------------------------

    def register_worker(
        self, worker_id: str, worker_kind: str, *, metadata: Optional[dict[str, Any]] = None,
        lease_seconds: float = 30.0,
    ) -> None:
        """Register one process worker for cross-instance monitoring."""
        now = datetime.now(timezone.utc)
        expires = now + timedelta(seconds=max(1.0, float(lease_seconds)))
        payload = json.dumps(metadata or {}, ensure_ascii=False, sort_keys=True, default=str)
        with self._lock:
            self._get_conn().execute(
                """INSERT INTO worker_instances
                   (worker_id, worker_kind, status, started_at, last_heartbeat_at,
                    lease_expires_at, metadata)
                   VALUES (?, ?, 'running', ?, ?, ?, ?)
                   ON CONFLICT(worker_id) DO UPDATE SET
                    worker_kind = excluded.worker_kind, status = 'running',
                    last_heartbeat_at = excluded.last_heartbeat_at,
                    lease_expires_at = excluded.lease_expires_at,
                    metadata = excluded.metadata""",
                (str(worker_id), str(worker_kind), now.isoformat(), now.isoformat(),
                 expires.isoformat(), payload),
            )
    def heartbeat_worker(
        self, worker_id: str, *, lease_seconds: float = 30.0,
    ) -> bool:
        now = datetime.now(timezone.utc)
        expires = now + timedelta(seconds=max(1.0, float(lease_seconds)))
        with self._lock:
            cursor = self._get_conn().execute(
                """UPDATE worker_instances SET status = 'running',
                   last_heartbeat_at = ?, lease_expires_at = ?
                   WHERE worker_id = ?""",
                (now.isoformat(), expires.isoformat(), str(worker_id)),
            )
            self._get_conn().commit()
            return cursor.rowcount == 1

    def unregister_worker(self, worker_id: str) -> bool:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            cursor = self._get_conn().execute(
                """UPDATE worker_instances SET status = 'stopped',
                   last_heartbeat_at = ?, lease_expires_at = NULL
                   WHERE worker_id = ?""",
                (now, str(worker_id)),
            )
            self._get_conn().commit()
            return cursor.rowcount == 1

    def list_workers(
        self, *, statuses: Optional[list[str]] = None, limit: int = 200,
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM worker_instances WHERE 1 = 1"
        params: list[Any] = []
        if statuses:
            values = [str(item) for item in statuses]
            query += " AND status IN (" + ",".join("?" for _ in values) + ")"
            params.extend(values)
        query += " ORDER BY last_heartbeat_at DESC LIMIT ?"
        params.append(max(1, min(int(limit), 500)))
        with self._lock:
            rows = self._get_conn().execute(query, params).fetchall()
        result = []
        now = datetime.now(timezone.utc)
        for row in rows:
            item = dict(row)
            try:
                metadata = json.loads(item.get("metadata") or "{}")
            except (TypeError, ValueError):
                metadata = {}
            item["metadata"] = metadata if isinstance(metadata, dict) else {}
            expires = item.get("lease_expires_at")
            try:
                item["lease_expired"] = bool(expires) and datetime.fromisoformat(
                    str(expires).replace("Z", "+00:00")
                ) <= now
            except (TypeError, ValueError):
                item["lease_expired"] = True
            result.append(item)
        return result

    def get_backend_health(self) -> dict[str, Any]:
        """Return a small backend-neutral health snapshot."""
        try:
            with self._lock:
                self._get_conn().execute("SELECT 1").fetchone()
            return {"backend": getattr(self, "backend_name", "sqlite"), "status": "healthy"}
        except Exception as exc:
            return {
                "backend": getattr(self, "backend_name", "sqlite"),
                "status": "unhealthy", "error": type(exc).__name__,
            }

    # -- Execution event repair --------------------------------------

    def enqueue_execution_event_repair(self, run_id: str, event: dict[str, Any]) -> bool:
        """Durably retain a sanitized event that could not be appended."""
        if not isinstance(event, dict):
            return False
        try:
            seq = int(event.get("seq"))
        except (TypeError, ValueError):
            return False
        if seq < 1:
            return False
        now = datetime.now(timezone.utc).isoformat()
        payload = json.dumps(event, ensure_ascii=False, sort_keys=True, default=str)
        with self._lock:
            cursor = self._get_conn().execute(
                """INSERT OR IGNORE INTO execution_event_repairs
                   (repair_id, run_id, seq, event_type, payload, status,
                    attempts, next_attempt_at, created_at)
                   VALUES (?, ?, ?, ?, ?, 'pending', 0, ?, ?)""",
                (str(uuid.uuid4()), str(run_id), seq,
                 str(event.get("event_type") or event.get("type") or "event"),
                 payload, now, now),
            )
            self._get_conn().commit()
            return cursor.rowcount == 1

    def repair_execution_run_events(self, limit: int = 50) -> int:
        """Retry pending event appends without affecting Agent execution."""
        now = datetime.now(timezone.utc)
        with self._lock:
            rows = self._get_conn().execute(
                """SELECT * FROM execution_event_repairs
                   WHERE status = 'pending'
                     AND (next_attempt_at IS NULL OR next_attempt_at <= ?)
                   ORDER BY created_at ASC LIMIT ?""",
                (now.isoformat(), max(1, min(int(limit), 100))),
            ).fetchall()
        repaired = 0
        for row in rows:
            try:
                event = json.loads(row["payload"] or "{}")
            except (TypeError, ValueError):
                event = {}
            success = self.append_execution_run_event(str(row["run_id"]), event)
            already_present = any(
                int(item.get("seq", 0)) == int(row["seq"])
                for item in self.list_execution_run_events(
                    str(row["run_id"]), after_seq=int(row["seq"]) - 1, limit=2
                )
            )
            if success or already_present:
                with self._lock:
                    self._get_conn().execute(
                        "DELETE FROM execution_event_repairs WHERE repair_id = ?",
                        (str(row["repair_id"]),),
                    )
                    self._get_conn().commit()
                repaired += 1
                continue
            attempts = int(row["attempts"] or 0) + 1
            delay = min(300, 2 ** min(attempts, 8))
            next_attempt = (now + timedelta(seconds=delay)).isoformat()
            with self._lock:
                self._get_conn().execute(
                    """UPDATE execution_event_repairs SET attempts = ?,
                       next_attempt_at = ?, last_error = ? WHERE repair_id = ?""",
                    (attempts, next_attempt, "event append was not accepted", str(row["repair_id"])),
                )
                self._get_conn().commit()
        return repaired

    # -- Runtime configuration -----------------------------------------

    def get_execution_mode(
        self, tenant_id: str, user_id: str,
    ) -> Optional[str]:
        """Read a principal-scoped execution-mode preference.

        The store returns the opaque persisted value; Runtime owns validation
        and the safety decision about whether that value may be used. Keeping
        that policy out of SQLite makes the same contract usable by another
        persistence backend.
        """
        tenant = str(tenant_id or "").strip()
        user = str(user_id or "").strip()
        if not tenant or not user:
            return None
        with self._lock:
            row = self._get_conn().execute(
                """SELECT mode FROM execution_mode_preferences
                   WHERE tenant_id = ? AND user_id = ?""",
                (tenant, user),
            ).fetchone()
            return str(row[0]) if row and row[0] is not None else None

    def set_execution_mode(
        self, tenant_id: str, user_id: str, mode: str,
    ) -> None:
        """Upsert a principal-scoped execution-mode preference."""
        tenant = str(tenant_id or "").strip()
        user = str(user_id or "").strip()
        if not tenant or not user:
            raise ValueError("tenant_id and user_id are required")
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                """INSERT INTO execution_mode_preferences
                   (tenant_id, user_id, mode, updated_at)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(tenant_id, user_id) DO UPDATE SET
                     mode = excluded.mode,
                     updated_at = excluded.updated_at""",
                (
                    tenant,
                    user,
                    str(mode),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            conn.commit()

    # -- Generic asynchronous Agent tasks -------------------------------

    @staticmethod
    def _task_from_row(row: Any) -> Optional[TaskRecord]:
        return TaskRecord.from_row(dict(row)) if row else None

    def create_task(self, record: TaskRecord) -> TaskRecord:
        """Create one durable task; idempotency is enforced by the database."""
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                """INSERT INTO tasks
                   (task_id, tenant_id, user_id, kind, status, payload, result,
                    error, idempotency_key, workflow_id, metadata, created_at,
                    updated_at, started_at, finished_at, lease_owner, lease_expires_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    record.task_id, record.tenant_id, record.user_id, record.kind,
                    record.status, json.dumps(record.payload or {}),
                    json.dumps(record.result) if record.result is not None else None,
                    record.error, record.idempotency_key, record.workflow_id,
                    json.dumps(record.metadata or {}), record.created_at,
                    record.updated_at, record.started_at, record.finished_at,
                    record.lease_owner, record.lease_expires_at,
                ),
            )
            conn.commit()
        return record

    def get_task(
        self, task_id: str, tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Optional[TaskRecord]:
        query = "SELECT * FROM tasks WHERE task_id = ?"
        params: list[Any] = [str(task_id)]
        if tenant_id is not None:
            query += " AND tenant_id = ?"
            params.append(str(tenant_id))
        if user_id is not None:
            query += " AND user_id = ?"
            params.append(str(user_id))
        with self._lock:
            row = self._get_conn().execute(query, params).fetchone()
            return self._task_from_row(row)

    def find_task_by_idempotency(
        self, tenant_id: str, user_id: str, idempotency_key: str,
    ) -> Optional[TaskRecord]:
        with self._lock:
            row = self._get_conn().execute(
                """SELECT * FROM tasks
                   WHERE tenant_id = ? AND user_id = ? AND idempotency_key = ?""",
                (str(tenant_id), str(user_id), str(idempotency_key)),
            ).fetchone()
            return self._task_from_row(row)

    def list_tasks(
        self, tenant_id: Optional[str] = None, user_id: Optional[str] = None,
        statuses: Optional[list[str]] = None, limit: int = 50,
    ) -> list[TaskRecord]:
        query = "SELECT * FROM tasks WHERE 1 = 1"
        params: list[Any] = []
        if tenant_id is not None:
            query += " AND tenant_id = ?"
            params.append(str(tenant_id))
        if user_id is not None:
            query += " AND user_id = ?"
            params.append(str(user_id))
        if statuses:
            values = [str(status) for status in statuses]
            query += " AND status IN (" + ",".join("?" for _ in values) + ")"
            params.extend(values)
        query += " ORDER BY updated_at DESC LIMIT ?"
        params.append(max(1, min(int(limit), 200)))
        with self._lock:
            rows = self._get_conn().execute(query, params).fetchall()
            return [self._task_from_row(row) for row in rows]

    # -- Operational monitoring ---------------------------------------

    @staticmethod
    def _monitoring_age_seconds(value: Any, now: datetime) -> Optional[float]:
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            if parsed.tzinfo is None and now.tzinfo is not None:
                # Existing domain timestamps are intentionally backend-neutral
                # local ISO strings. Compare them in the same wall-clock
                # domain instead of interpreting them as UTC.
                current = now.replace(tzinfo=None)
            elif parsed.tzinfo is not None and now.tzinfo is None:
                current = now.replace(tzinfo=parsed.tzinfo)
            else:
                current = now
            return max(0.0, (current - parsed).total_seconds())
        except (TypeError, ValueError, OverflowError):
            return None

    @staticmethod
    def _monitoring_duration_ms(started_at: Any, ended_at: Any) -> Optional[float]:
        if not started_at or not ended_at:
            return None
        try:
            started = datetime.fromisoformat(str(started_at).replace("Z", "+00:00"))
            ended = datetime.fromisoformat(str(ended_at).replace("Z", "+00:00"))
            if started.tzinfo is None:
                started = started.replace(tzinfo=timezone.utc)
            if ended.tzinfo is None:
                ended = ended.replace(tzinfo=timezone.utc)
            return max(0.0, (ended - started).total_seconds() * 1000.0)
        except (TypeError, ValueError, OverflowError):
            return None

    @staticmethod
    def _monitoring_timestamp(value: Any) -> Optional[datetime]:
        """Parse a stored timestamp into the local naive clock used by charts."""
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            if parsed.tzinfo is not None:
                return parsed.astimezone().replace(tzinfo=None)
            return parsed
        except (TypeError, ValueError, OverflowError):
            return None

    def get_monitoring_snapshot(
        self, *, tenant_id: Optional[str] = None, user_id: Optional[str] = None,
        stale_after_seconds: float = 300.0,
        lease_expiry_window_seconds: float = 60.0,
        tool_window_seconds: float = 3600.0,
    ) -> dict[str, Any]:
        """Return a bounded, credential-free operational view of the store.

        All filters are applied inside the persistence layer.  The HTTP layer
        never loads raw task/tool payloads just to render the monitoring page.
        SQL intentionally stays within the small common subset used by the
        SQLite and MySQL adapters.
        """
        stale_after = max(1.0, float(stale_after_seconds))
        lease_window = max(1.0, float(lease_expiry_window_seconds))
        tool_window = max(1.0, float(tool_window_seconds))
        now = datetime.now()
        now_iso = now.isoformat()
        stale_cutoff = (now - timedelta(seconds=stale_after)).isoformat()
        lease_cutoff = (
            now + timedelta(seconds=lease_window)
        ).isoformat()
        tool_cutoff = (
            now - timedelta(seconds=tool_window)
        ).isoformat()

        def scope_clause(prefix: str = "") -> tuple[str, list[Any]]:
            clauses: list[str] = []
            params: list[Any] = []
            if tenant_id is not None:
                clauses.append(f"{prefix}tenant_id = ?")
                params.append(str(tenant_id))
            if user_id is not None:
                clauses.append(f"{prefix}user_id = ?")
                params.append(str(user_id))
            return (" AND " + " AND ".join(clauses)) if clauses else "", params

        def grouped(table: str, *, where: str = "", params: list[Any] | None = None) -> dict[str, int]:
            rows = conn.execute(
                f"SELECT status, COUNT(*) AS count FROM {table} WHERE 1 = 1{where} GROUP BY status",
                params or [],
            ).fetchall()
            return {str(row["status"]): int(row["count"] or 0) for row in rows}

        def scalar(statement: str, params: list[Any] | None = None) -> Any:
            row = conn.execute(statement, params or []).fetchone()
            return row[0] if row else None

        with self._lock:
            conn = self._get_conn()

            task_scope, task_params = scope_clause()
            task_statuses = grouped("tasks", where=task_scope, params=task_params)
            task_active_where = (
                f"{task_scope} AND status IN ('running', 'cancelling')"
            )
            task_active_params = list(task_params)
            task_expired = int(scalar(
                "SELECT COUNT(*) FROM tasks WHERE 1 = 1" + task_active_where
                + " AND (lease_expires_at IS NULL OR lease_expires_at <= ?)",
                task_active_params + [now_iso],
            ) or 0)
            task_expiring = int(scalar(
                "SELECT COUNT(*) FROM tasks WHERE 1 = 1" + task_active_where
                + " AND lease_expires_at > ? AND lease_expires_at <= ?",
                task_active_params + [now_iso, lease_cutoff],
            ) or 0)
            task_stale = int(scalar(
                "SELECT COUNT(*) FROM tasks WHERE 1 = 1" + task_scope
                + " AND status IN ('running', 'cancelling') AND updated_at <= ?",
                task_params + [stale_cutoff],
            ) or 0)
            queued_oldest = scalar(
                "SELECT MIN(created_at) FROM tasks WHERE 1 = 1" + task_scope
                + " AND status = 'queued'", task_params,
            )
            task_owners = conn.execute(
                "SELECT lease_owner, COUNT(*) AS count FROM tasks WHERE 1 = 1"
                + task_active_where + " AND lease_owner IS NOT NULL"
                + " GROUP BY lease_owner ORDER BY count DESC LIMIT 20",
                task_active_params,
            ).fetchall()

            run_scope, run_params = scope_clause()
            run_statuses = grouped("execution_runs", where=run_scope, params=run_params)
            run_stale = int(scalar(
                "SELECT COUNT(*) FROM execution_runs WHERE 1 = 1" + run_scope
                + " AND status = 'running' AND updated_at <= ?",
                run_params + [stale_cutoff],
            ) or 0)

            session_scope = ""
            session_params: list[Any] = []
            if tenant_id is not None:
                session_scope += " AND w.tenant_id = ?"
                session_params.append(str(tenant_id))
            if user_id is not None:
                session_scope += " AND s.user_id = ?"
                session_params.append(str(user_id))
            workflow_statuses = {
                str(row["status"]): int(row["count"] or 0)
                for row in conn.execute(
                    "SELECT w.status, COUNT(*) AS count FROM workflows w "
                    "JOIN sessions s ON s.session_id = w.session_id WHERE 1 = 1"
                    + session_scope + " GROUP BY w.status", session_params,
                ).fetchall()
            }
            workflow_expired = int(scalar(
                "SELECT COUNT(*) FROM workflows w JOIN sessions s ON s.session_id = w.session_id "
                "WHERE w.status = 'running'" + session_scope
                + " AND (w.lease_expires_at IS NULL OR w.lease_expires_at <= ?)",
                session_params + [now_iso],
            ) or 0)
            workflow_expiring = int(scalar(
                "SELECT COUNT(*) FROM workflows w JOIN sessions s ON s.session_id = w.session_id "
                "WHERE w.status = 'running'" + session_scope
                + " AND w.lease_expires_at > ? AND w.lease_expires_at <= ?",
                session_params + [now_iso, lease_cutoff],
            ) or 0)
            workflow_stale = int(scalar(
                "SELECT COUNT(*) FROM workflows w JOIN sessions s ON s.session_id = w.session_id "
                "WHERE w.status = 'running'" + session_scope + " AND w.updated_at <= ?",
                session_params + [stale_cutoff],
            ) or 0)
            session_leases = int(scalar(
                "SELECT COUNT(*) FROM sessions s WHERE s.lease_owner IS NOT NULL"
                + (" AND s.tenant_id = ?" if tenant_id is not None else "")
                + (" AND s.user_id = ?" if user_id is not None else "")
                + " AND s.lease_expires_at > ?",
                ([str(tenant_id)] if tenant_id is not None else [])
                + ([str(user_id)] if user_id is not None else []) + [now_iso],
            ) or 0)
            session_expired = int(scalar(
                "SELECT COUNT(*) FROM sessions s WHERE s.lease_owner IS NOT NULL"
                + (" AND s.tenant_id = ?" if tenant_id is not None else "")
                + (" AND s.user_id = ?" if user_id is not None else "")
                + " AND (s.lease_expires_at IS NULL OR s.lease_expires_at <= ?)",
                ([str(tenant_id)] if tenant_id is not None else [])
                + ([str(user_id)] if user_id is not None else []) + [now_iso],
            ) or 0)

            outbox_where = ""
            outbox_params: list[Any] = []
            if tenant_id is not None or user_id is not None:
                outbox_where = (
                    " AND EXISTS (SELECT 1 FROM workflows w JOIN sessions s "
                    "ON s.session_id = w.session_id WHERE w.workflow_id = outbox_events.run_id "
                    + ("AND w.tenant_id = ? " if tenant_id is not None else "")
                    + ("AND s.user_id = ?" if user_id is not None else "") + ")"
                )
                if tenant_id is not None:
                    outbox_params.append(str(tenant_id))
                if user_id is not None:
                    outbox_params.append(str(user_id))
            outbox_statuses = grouped(
                "outbox_events", where=outbox_where, params=outbox_params,
            )
            outbox_retrying = int(scalar(
                "SELECT COUNT(*) FROM outbox_events WHERE status = 'pending'"
                + outbox_where + " AND retry_count > 0", outbox_params,
            ) or 0)

            tool_rows = conn.execute(
                "SELECT tc.tool_name, tc.platform, tc.success, tc.started_at, tc.ended_at "
                "FROM tool_calls tc JOIN sessions s ON s.session_id = tc.session_id "
                "WHERE tc.started_at >= ?"
                + (" AND s.tenant_id = ?" if tenant_id is not None else "")
                + (" AND s.user_id = ?" if user_id is not None else "")
                + " ORDER BY tc.started_at DESC LIMIT 2000",
                [tool_cutoff]
                + ([str(tenant_id)] if tenant_id is not None else [])
                + ([str(user_id)] if user_id is not None else []),
            ).fetchall()
            tool_total = len(tool_rows)
            tool_failed = sum(1 for row in tool_rows if not bool(row["success"]))
            durations = [
                duration for row in tool_rows
                if (duration := self._monitoring_duration_ms(row["started_at"], row["ended_at"])) is not None
            ]
            timeline_bucket_count = 12
            timeline_bucket_seconds = tool_window / timeline_bucket_count
            timeline_start = now - timedelta(seconds=tool_window)
            tool_timeline = [
                {
                    "label": (timeline_start + timedelta(seconds=index * timeline_bucket_seconds)).strftime("%H:%M"),
                    "calls": 0,
                    "failed": 0,
                    "avg_latency_ms": None,
                }
                for index in range(timeline_bucket_count)
            ]
            timeline_durations: list[list[float]] = [[] for _ in range(timeline_bucket_count)]
            for row in tool_rows:
                started_at = self._monitoring_timestamp(row["started_at"])
                if started_at is None:
                    continue
                offset_seconds = (started_at - timeline_start).total_seconds()
                if offset_seconds < 0 or offset_seconds >= tool_window:
                    continue
                bucket = min(timeline_bucket_count - 1, int(offset_seconds / timeline_bucket_seconds))
                tool_timeline[bucket]["calls"] += 1
                tool_timeline[bucket]["failed"] += int(not bool(row["success"]))
                duration = self._monitoring_duration_ms(row["started_at"], row["ended_at"])
                if duration is not None:
                    timeline_durations[bucket].append(duration)
            for index, durations_for_bucket in enumerate(timeline_durations):
                if durations_for_bucket:
                    tool_timeline[index]["avg_latency_ms"] = round(
                        sum(durations_for_bucket) / len(durations_for_bucket), 2,
                    )
            by_tool: dict[str, dict[str, Any]] = {}
            for row in tool_rows:
                name = str(row["tool_name"] or "unknown")
                item = by_tool.setdefault(name, {"tool_name": name, "platform": row["platform"], "calls": 0, "failed": 0})
                item["calls"] += 1
                item["failed"] += int(not bool(row["success"]))
            top_tools = sorted(by_tool.values(), key=lambda item: (-item["calls"], item["tool_name"]))[:12]

        queued_age = self._monitoring_age_seconds(queued_oldest, now)
        schedule_metrics = self.get_scheduled_task_metrics(
            tenant_id=tenant_id, user_id=user_id,
        )
        workers = self.list_workers()
        backend_health = self.get_backend_health()
        alert_count = sum(
            value > 0 for value in (
                task_statuses.get("recovery_required", 0),
                run_statuses.get("recovery_required", 0),
                workflow_statuses.get("recovery_required", 0),
                task_expired, workflow_expired, outbox_statuses.get("failed", 0),
                outbox_statuses.get("dead_letter", 0),
            )
        )
        warning_count = sum(value > 0 for value in (task_expiring, workflow_expiring, queued_age or 0))
        overall_status = "critical" if alert_count else "attention" if warning_count else "healthy"
        return {
            "generated_at": now.astimezone().isoformat(),
            "backend": getattr(self, "backend_name", "sqlite"),
            "status": overall_status,
            "scope": {"tenant_id": tenant_id, "user_id": user_id},
            "tasks": {
                "by_status": task_statuses,
                "queued_depth": task_statuses.get("queued", 0),
                "queued_oldest_at": queued_oldest,
                "queued_oldest_age_seconds": round(queued_age, 3) if queued_age is not None else None,
                "stale_running": task_stale,
                "leases": {"expired": task_expired, "expiring_soon": task_expiring},
                "lease_owners": [dict(row) for row in task_owners],
            },
            "runs": {"by_status": run_statuses, "stale_running": run_stale},
            "workflows": {
                "by_status": workflow_statuses,
                "stale_running": workflow_stale,
                "leases": {"expired": workflow_expired, "expiring_soon": workflow_expiring},
            },
            "sessions": {"active_leases": session_leases, "expired_leases": session_expired},
            "outbox": {
                "by_status": outbox_statuses,
                "pending_depth": outbox_statuses.get("pending", 0),
                "claimed": outbox_statuses.get("claimed", 0),
                "retrying": outbox_retrying,
                "dead_letter": outbox_statuses.get("dead_letter", 0),
            },
            "workers": {
                "total": len(workers),
                "running": sum(
                    1 for item in workers
                    if item.get("status") == "running" and not item.get("lease_expired")
                ),
                "stale": sum(1 for item in workers if item.get("lease_expired")),
                "items": workers,
            },
            "backend_health": backend_health,
            "schedules": schedule_metrics,
            "tools": {
                "window_seconds": tool_window,
                "total": tool_total,
                "failed": tool_failed,
                "success_rate": round((tool_total - tool_failed) / tool_total, 4) if tool_total else None,
                "avg_latency_ms": round(sum(durations) / len(durations), 2) if durations else None,
                "timeline_interval_seconds": timeline_bucket_seconds,
                "timeline": tool_timeline,
                "top_tools": top_tools,
            },
            "alerts": {
                "recovery_required": (
                    task_statuses.get("recovery_required", 0)
                    + run_statuses.get("recovery_required", 0)
                    + workflow_statuses.get("recovery_required", 0)
                ),
                "expired_leases": task_expired + workflow_expired + session_expired,
                "expiring_leases": task_expiring + workflow_expiring,
                "failed_outbox": outbox_statuses.get("failed", 0),
                "dead_letter_outbox": outbox_statuses.get("dead_letter", 0),
            },
        }

    def claim_task(
        self, task_id: str, lease_owner: str, lease_seconds: float = 300.0,
    ) -> Optional[TaskRecord]:
        if not lease_owner or float(lease_seconds) <= 0:
            return None
        now = datetime.now()
        now_iso = now.isoformat()
        expires_iso = (now + timedelta(seconds=float(lease_seconds))).isoformat()
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute(
                """UPDATE tasks SET status = 'running', updated_at = ?,
                   started_at = COALESCE(started_at, ?), lease_owner = ?,
                   lease_expires_at = ?
                   WHERE task_id = ? AND status = 'queued'""",
                (now_iso, now_iso, str(lease_owner), expires_iso, str(task_id)),
            )
            conn.commit()
            if cursor.rowcount == 0:
                return None
            return self._task_from_row(
                conn.execute("SELECT * FROM tasks WHERE task_id = ?", (str(task_id),)).fetchone()
            )

    def heartbeat_task(
        self, task_id: str, lease_owner: str, lease_seconds: float = 300.0,
    ) -> bool:
        if not lease_owner or float(lease_seconds) <= 0:
            return False
        now = datetime.now()
        now_iso = now.isoformat()
        expires_iso = (now + timedelta(seconds=float(lease_seconds))).isoformat()
        with self._lock:
            cursor = self._get_conn().execute(
                """UPDATE tasks SET updated_at = ?, lease_expires_at = ?
                   WHERE task_id = ? AND lease_owner = ?
                     AND status IN ('running', 'cancelling')""",
                (now_iso, expires_iso, str(task_id), str(lease_owner)),
            )
            self._get_conn().commit()
            return cursor.rowcount > 0

    def update_task(
        self, task_id: str, status: str, *, result: Optional[dict] = None,
        error: Optional[str] = None, metadata: Optional[dict] = None,
        workflow_id: Optional[str] = None,
        expected_statuses: Optional[list[str]] = None,
    ) -> bool:
        status = str(status)
        with self._lock:
            conn = self._get_conn()
            row = conn.execute(
                "SELECT status, metadata FROM tasks WHERE task_id = ?", (str(task_id),)
            ).fetchone()
            if not row:
                return False
            current = str(row["status"])
            if expected_statuses and current not in {str(item) for item in expected_statuses}:
                return False
            if status not in TASK_TRANSITIONS.get(current, set()):
                logger.warning(
                    "Rejected invalid task transition %s -> %s for %s",
                    current, status, task_id,
                )
                return False
            merged_metadata = {}
            try:
                merged_metadata = json.loads(row["metadata"] or "{}") or {}
            except (TypeError, ValueError):
                pass
            merged_metadata.update(metadata or {})
            now = datetime.now().isoformat()
            terminal = status in {
                "succeeded", "failed", "partially_failed", "awaiting_input",
                "cancelled", "recovery_required",
            }
            assignments = [
                "status = ?", "error = ?", "metadata = ?", "updated_at = ?",
            ]
            values: list[Any] = [status, error, json.dumps(merged_metadata), now]
            if result is not None:
                assignments.append("result = ?")
                values.append(json.dumps(result))
            if workflow_id is not None:
                assignments.append("workflow_id = ?")
                values.append(str(workflow_id))
            if terminal:
                assignments.extend(["finished_at = COALESCE(finished_at, ?)", "lease_owner = NULL", "lease_expires_at = NULL"])
                values.append(now)
            values.append(str(task_id))
            cursor = conn.execute(
                "UPDATE tasks SET " + ", ".join(assignments) + " WHERE task_id = ?",
                values,
            )
            conn.commit()
            return cursor.rowcount > 0

    def pause_task(
        self, task_id: str, tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Optional[TaskRecord]:
        with self._lock:
            conn = self._get_conn()
            now = datetime.now().isoformat()
            where = "task_id = ? AND status = 'queued'"
            params: list[Any] = [now, str(task_id)]
            if tenant_id is not None:
                where += " AND tenant_id = ?"
                params.append(str(tenant_id))
            if user_id is not None:
                where += " AND user_id = ?"
                params.append(str(user_id))
            cursor = conn.execute(
                "UPDATE tasks SET status = 'paused', updated_at = ? "
                "WHERE " + where,
                params,
            )
            conn.commit()
            return self.get_task(
                str(task_id), tenant_id=tenant_id, user_id=user_id,
            )

    def resume_task(
        self, task_id: str, tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Optional[TaskRecord]:
        with self._lock:
            conn = self._get_conn()
            now = datetime.now().isoformat()
            where = "task_id = ? AND status = 'paused'"
            params: list[Any] = [now, str(task_id)]
            if tenant_id is not None:
                where += " AND tenant_id = ?"
                params.append(str(tenant_id))
            if user_id is not None:
                where += " AND user_id = ?"
                params.append(str(user_id))
            cursor = conn.execute(
                "UPDATE tasks SET status = 'queued', updated_at = ?, error = NULL "
                "WHERE " + where,
                params,
            )
            conn.commit()
            return self.get_task(
                str(task_id), tenant_id=tenant_id, user_id=user_id,
            )

    def cancel_task(
        self, task_id: str, tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Optional[TaskRecord]:
        with self._lock:
            conn = self._get_conn()
            scope = ""
            scope_params: list[Any] = []
            if tenant_id is not None:
                scope += " AND tenant_id = ?"
                scope_params.append(str(tenant_id))
            if user_id is not None:
                scope += " AND user_id = ?"
                scope_params.append(str(user_id))
            row = conn.execute(
                "SELECT status, metadata FROM tasks WHERE task_id = ?" + scope,
                [str(task_id)] + scope_params,
            ).fetchone()
            if not row:
                return None
            current = str(row["status"])
            if current in {"queued", "paused"}:
                status = "cancelled"
            elif current in {"running", "cancelling"}:
                status = "cancelling"
            else:
                return self._task_from_row(
                    conn.execute("SELECT * FROM tasks WHERE task_id = ?", (str(task_id),)).fetchone()
                )
            try:
                metadata = json.loads(row["metadata"] or "{}") or {}
            except (TypeError, ValueError):
                metadata = {}
            metadata["cancellation_requested"] = True
            now = datetime.now().isoformat()
            finished = ", finished_at = ?" if status == "cancelled" else ""
            values: list[Any] = [status, json.dumps(metadata), now]
            if finished:
                values.append(now)
            values.append(str(task_id))
            values.extend(scope_params)
            if status == "cancelled":
                status_guard = " AND status IN ('queued', 'paused')"
            else:
                status_guard = " AND status IN ('running', 'cancelling')"
            conn.execute(
                "UPDATE tasks SET status = ?, metadata = ?, updated_at = ?" + finished
                + " WHERE task_id = ?" + scope + status_guard, values,
            )
            conn.commit()
            return self.get_task(
                str(task_id), tenant_id=tenant_id, user_id=user_id,
            )

    def recover_stale_tasks(self, stale_after_seconds: float = 300.0) -> int:
        if float(stale_after_seconds) <= 0:
            return 0
        cutoff = (datetime.now() - timedelta(seconds=float(stale_after_seconds))).isoformat()
        now = datetime.now().isoformat()
        with self._lock:
            conn = self._get_conn()
            rows = conn.execute(
                """SELECT task_id, metadata FROM tasks
                   WHERE status IN ('running', 'cancelling')
                     AND (updated_at <= ? OR lease_expires_at <= ?)""",
                (cutoff, now),
            ).fetchall()
            for row in rows:
                try:
                    metadata = json.loads(row["metadata"] or "{}") or {}
                except (TypeError, ValueError):
                    metadata = {}
                metadata["recovery_reason"] = "stale_task"
                conn.execute(
                    """UPDATE tasks SET status = 'recovery_required', updated_at = ?,
                       finished_at = COALESCE(finished_at, ?), lease_owner = NULL,
                       lease_expires_at = NULL, metadata = ?
                       WHERE task_id = ? AND status IN ('running', 'cancelling')""",
                    (now, now, json.dumps(metadata), row["task_id"]),
                )
            conn.commit()
            return len(rows)

    def requeue_recovery_task(
        self, task_id: str, *, recovery_reference: str,
        tenant_id: Optional[str] = None, user_id: Optional[str] = None,
    ) -> Optional[TaskRecord]:
        """Move an uncertain task back to the queue after operator recovery.

        This is intentionally separate from ``resume_task``.  A recovery task
        may have produced an external side effect, so callers must first
        reconcile the provider and provide an auditable reference.
        """
        reference = str(recovery_reference or "").strip()[:255]
        if not reference:
            raise ValueError("recovery_reference is required")
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            conn = self._get_conn()
            scope = ""
            scope_params: list[Any] = []
            if tenant_id is not None:
                scope += " AND tenant_id = ?"
                scope_params.append(str(tenant_id))
            if user_id is not None:
                scope += " AND user_id = ?"
                scope_params.append(str(user_id))
            row = conn.execute(
                "SELECT metadata FROM tasks WHERE task_id = ? AND status = 'recovery_required'" + scope,
                [str(task_id)] + scope_params,
            ).fetchone()
            if not row:
                return None
            try:
                metadata = json.loads(row["metadata"] or "{}") or {}
            except (TypeError, ValueError):
                metadata = {}
            metadata.update({
                "recovery_action": "operator_requeue",
                "recovery_reference": reference,
                "requeued_at": now,
            })
            cursor = conn.execute(
                """UPDATE tasks SET status = 'queued', error = NULL, result = NULL,
                   updated_at = ?, started_at = NULL, finished_at = NULL,
                   lease_owner = NULL, lease_expires_at = NULL, metadata = ?
                   WHERE task_id = ? AND status = 'recovery_required'""",
                [now, json.dumps(metadata, ensure_ascii=False, sort_keys=True), str(task_id)]
                + scope_params,
            )
            conn.commit()
            if cursor.rowcount != 1:
                return None
            return self.get_task(
                str(task_id), tenant_id=tenant_id, user_id=user_id,
            )

    # -- Recurring Agent schedules ------------------------------------

    @staticmethod
    def _scheduled_from_row(row: Any) -> Optional[ScheduledTaskRecord]:
        return ScheduledTaskRecord.from_row(dict(row)) if row else None

    @staticmethod
    def _scheduled_run_from_row(row: Any) -> Optional[ScheduledTaskRunRecord]:
        return ScheduledTaskRunRecord.from_row(dict(row)) if row else None

    def create_scheduled_task(self, record: ScheduledTaskRecord) -> ScheduledTaskRecord:
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                """INSERT INTO scheduled_tasks
                   (schedule_id, tenant_id, user_id, name, prompt, cron_expression,
                    timezone, status, next_run_at, last_run_at, last_run_status,
                    last_task_id, run_count, success_count, failure_count, payload,
                    metadata, lease_owner, lease_expires_at, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    record.schedule_id, record.tenant_id, record.user_id, record.name,
                    record.prompt, record.cron_expression, record.timezone, record.status,
                    record.next_run_at, record.last_run_at, record.last_run_status,
                    record.last_task_id, record.run_count, record.success_count,
                    record.failure_count, json.dumps(record.payload or {}, ensure_ascii=False),
                    json.dumps(record.metadata or {}, ensure_ascii=False), record.lease_owner,
                    record.lease_expires_at, record.created_at, record.updated_at,
                ),
            )
            conn.commit()
        return record

    def get_scheduled_task(
        self, schedule_id: str, tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Optional[ScheduledTaskRecord]:
        query = "SELECT * FROM scheduled_tasks WHERE schedule_id = ?"
        params: list[Any] = [str(schedule_id)]
        if tenant_id is not None:
            query += " AND tenant_id = ?"
            params.append(str(tenant_id))
        if user_id is not None:
            query += " AND user_id = ?"
            params.append(str(user_id))
        with self._lock:
            return self._scheduled_from_row(self._get_conn().execute(query, params).fetchone())

    def list_scheduled_tasks(
        self, tenant_id: Optional[str] = None, user_id: Optional[str] = None,
        statuses: Optional[list[str]] = None, limit: int = 100,
    ) -> list[ScheduledTaskRecord]:
        query = "SELECT * FROM scheduled_tasks WHERE 1 = 1"
        params: list[Any] = []
        if tenant_id is not None:
            query += " AND tenant_id = ?"; params.append(str(tenant_id))
        if user_id is not None:
            query += " AND user_id = ?"; params.append(str(user_id))
        if statuses:
            query += " AND status IN (" + ",".join("?" for _ in statuses) + ")"
            params.extend(str(item) for item in statuses)
        query += " ORDER BY COALESCE(next_run_at, updated_at) ASC LIMIT ?"
        params.append(max(1, min(int(limit), 500)))
        with self._lock:
            rows = self._get_conn().execute(query, params).fetchall()
            return [self._scheduled_from_row(row) for row in rows]

    def update_scheduled_task(
        self, schedule_id: str, *, status: Optional[str] = None,
        next_run_at: Optional[str] = None, last_run_at: Optional[str] = None,
        last_run_status: Optional[str] = None, last_task_id: Optional[str] = None,
        metadata: Optional[dict] = None, name: Optional[str] = None,
        prompt: Optional[str] = None, cron_expression: Optional[str] = None,
        schedule_timezone: Optional[str] = None, payload: Optional[dict] = None,
        only_unleased: bool = False, tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> bool:
        assignments = ["updated_at = ?"]
        values: list[Any] = [datetime.now(timezone.utc).isoformat()]
        for column, value in (
            ("status", status), ("name", name), ("prompt", prompt),
            ("cron_expression", cron_expression), ("timezone", schedule_timezone),
            ("next_run_at", next_run_at), ("last_run_at", last_run_at),
            ("last_run_status", last_run_status), ("last_task_id", last_task_id),
        ):
            if value is not None:
                assignments.append(f"{column} = ?"); values.append(value)
        if metadata is not None:
            assignments.append("metadata = ?"); values.append(json.dumps(metadata or {}, ensure_ascii=False))
        if payload is not None:
            assignments.append("payload = ?")
            values.append(json.dumps(payload, ensure_ascii=False))
        values.append(str(schedule_id))
        where = "schedule_id = ?"
        if tenant_id is not None:
            where += " AND tenant_id = ?"
            values.append(str(tenant_id))
        if user_id is not None:
            where += " AND user_id = ?"
            values.append(str(user_id))
        if only_unleased:
            where += " AND lease_owner IS NULL"
        with self._lock:
            cursor = self._get_conn().execute(
                "UPDATE scheduled_tasks SET " + ", ".join(assignments)
                + " WHERE " + where, values,
            )
            self._get_conn().commit()
            return cursor.rowcount > 0

    def advance_scheduled_task(
        self, schedule_id: str, expected_next_run_at: str, next_run_at: str,
        lease_owner: Optional[str] = None,
    ) -> bool:
        where = "schedule_id = ? AND next_run_at = ?"
        params: list[Any] = [next_run_at, datetime.now(timezone.utc).isoformat(), str(schedule_id), expected_next_run_at]
        if lease_owner is not None:
            where += " AND lease_owner = ?"
            params.append(str(lease_owner))
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute(
                """UPDATE scheduled_tasks SET next_run_at = ?, lease_owner = NULL,
                   lease_expires_at = NULL, updated_at = ?
                   WHERE """ + where,
                params,
            )
            conn.commit()
            return cursor.rowcount > 0

    def pause_scheduled_task(
        self, schedule_id: str, *, tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Optional[ScheduledTaskRecord]:
        if not self.update_scheduled_task(
            schedule_id, status="paused", tenant_id=tenant_id, user_id=user_id,
        ):
            return None
        return self.get_scheduled_task(
            schedule_id, tenant_id=tenant_id, user_id=user_id,
        )

    def resume_scheduled_task(
        self, schedule_id: str, next_run_at: str, *,
        tenant_id: Optional[str] = None, user_id: Optional[str] = None,
    ) -> Optional[ScheduledTaskRecord]:
        if not self.update_scheduled_task(
            schedule_id, status="active", next_run_at=next_run_at,
            tenant_id=tenant_id, user_id=user_id,
        ):
            return None
        return self.get_scheduled_task(
            schedule_id, tenant_id=tenant_id, user_id=user_id,
        )

    def delete_scheduled_task(
        self, schedule_id: str, *, tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> bool:
        with self._lock:
            conn = self._get_conn()
            where = "schedule_id = ?"
            params: list[Any] = [str(schedule_id)]
            if tenant_id is not None:
                where += " AND tenant_id = ?"
                params.append(str(tenant_id))
            if user_id is not None:
                where += " AND user_id = ?"
                params.append(str(user_id))
            cursor = conn.execute(
                "DELETE FROM scheduled_tasks WHERE " + where, params,
            )
            conn.commit()
            return cursor.rowcount > 0

    def claim_due_scheduled_tasks(
        self, now: str, lease_owner: str, lease_seconds: float = 60.0,
        limit: int = 20,
    ) -> list[tuple[ScheduledTaskRecord, ScheduledTaskRunRecord]]:
        if not lease_owner or float(lease_seconds) <= 0:
            return []
        now_value = str(now)
        expires = (datetime.now(timezone.utc) + timedelta(seconds=float(lease_seconds))).isoformat()
        claimed: list[tuple[ScheduledTaskRecord, ScheduledTaskRunRecord]] = []
        with self._lock:
            conn = self._get_conn()
            if conn.in_transaction:
                conn.commit()
            conn.execute("BEGIN IMMEDIATE")
            try:
                rows = conn.execute(
                    """SELECT * FROM scheduled_tasks
                       WHERE status = 'active' AND next_run_at IS NOT NULL
                         AND next_run_at <= ?
                         AND (lease_expires_at IS NULL OR lease_expires_at <= ?)
                       ORDER BY next_run_at ASC LIMIT ?""",
                    (now_value, now_value, max(1, min(int(limit), 100))),
                ).fetchall()
                for row in rows:
                    schedule = self._scheduled_from_row(row)
                    scheduled_for = str(schedule.next_run_at)
                    conn.execute(
                        """UPDATE scheduled_tasks SET lease_owner = ?, lease_expires_at = ?, updated_at = ?
                           WHERE schedule_id = ?""",
                        (str(lease_owner), expires, now_value, schedule.schedule_id),
                    )
                    run_row = conn.execute(
                        """SELECT * FROM scheduled_task_runs
                           WHERE schedule_id = ? AND scheduled_for = ?""",
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
                        run = self._scheduled_run_from_row(run_row)
                    claimed.append((schedule, run))
                conn.commit()
            except Exception:
                conn.rollback()
                raise
        return claimed

    def create_scheduled_task_run(
        self, record: ScheduledTaskRunRecord,
    ) -> ScheduledTaskRunRecord:
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                """INSERT INTO scheduled_task_runs
                   (schedule_run_id, schedule_id, tenant_id, user_id, scheduled_for,
                    status, task_id, started_at, finished_at, error, result, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    record.schedule_run_id,
                    record.schedule_id,
                    record.tenant_id,
                    record.user_id,
                    record.scheduled_for,
                    record.status,
                    record.task_id,
                    record.started_at,
                    record.finished_at,
                    record.error,
                    json.dumps(record.result, ensure_ascii=False)
                    if record.result is not None else None,
                    record.created_at,
                ),
            )
            conn.commit()
        return record

    def attach_scheduled_task_run(
        self, schedule_run_id: str, task_id: str, status: str = "queued",
        lease_owner: Optional[str] = None,
    ) -> bool:
        with self._lock:
            conn = self._get_conn()
            owner_clause = ""
            owner_values: list[Any] = []
            if lease_owner is not None:
                owner_clause = (
                    " AND EXISTS (SELECT 1 FROM scheduled_tasks s "
                    "WHERE s.schedule_id = scheduled_task_runs.schedule_id "
                    "AND s.lease_owner = ?)"
                )
                owner_values.append(str(lease_owner))
            cursor = conn.execute(
                "UPDATE scheduled_task_runs SET task_id = ?, status = ?, started_at = ?, error = NULL "
                "WHERE schedule_run_id = ? AND status IN ('queued', 'running')" + owner_clause,
                [str(task_id), str(status), datetime.now(timezone.utc).isoformat(), str(schedule_run_id)] + owner_values,
            )
            conn.commit()
            return cursor.rowcount > 0

    def update_scheduled_task_run(
        self, schedule_run_id: str, status: str, *, task_id: Optional[str] = None,
        started_at: Optional[str] = None, finished_at: Optional[str] = None,
        error: Optional[str] = None, result: Optional[dict] = None,
        lease_owner: Optional[str] = None,
    ) -> bool:
        status = str(status)
        with self._lock:
            conn = self._get_conn()
            row = conn.execute("SELECT * FROM scheduled_task_runs WHERE schedule_run_id = ?", (str(schedule_run_id),)).fetchone()
            if not row:
                return False
            current = str(row["status"])
            terminal_statuses = {
                "succeeded", "failed", "partially_failed", "awaiting_input",
                "cancelled", "recovery_required",
            }
            if current in terminal_statuses and status != current:
                return False
            assignments = ["status = ?"]
            values: list[Any] = [status]
            for column, value in (("task_id", task_id), ("started_at", started_at), ("finished_at", finished_at), ("error", error)):
                if value is not None:
                    assignments.append(f"{column} = ?"); values.append(value)
            if result is not None:
                assignments.append("result = ?"); values.append(json.dumps(result, ensure_ascii=False))
            values.append(str(schedule_run_id))
            owner_clause = ""
            if lease_owner is not None:
                owner_clause = (
                    " AND EXISTS (SELECT 1 FROM scheduled_tasks s "
                    "WHERE s.schedule_id = scheduled_task_runs.schedule_id "
                    "AND s.lease_owner = ?)"
                )
                values.append(str(lease_owner))
            cursor = conn.execute(
                "UPDATE scheduled_task_runs SET " + ", ".join(assignments)
                + " WHERE schedule_run_id = ?" + owner_clause, values,
            )
            if cursor.rowcount == 0:
                conn.commit()
                return False
            if status in terminal_statuses and current not in terminal_statuses:
                schedule_id = str(row["schedule_id"])
                conn.execute(
                    """UPDATE scheduled_tasks SET run_count = run_count + 1,
                       success_count = success_count + ?, failure_count = failure_count + ?,
                       last_run_at = ?, last_run_status = ?, last_task_id = COALESCE(?, last_task_id),
                       lease_owner = NULL, lease_expires_at = NULL, updated_at = ?
                       WHERE schedule_id = ?""",
                    (int(status == "succeeded"), int(status in {
                        "failed", "partially_failed", "cancelled", "recovery_required",
                    }),
                     finished_at or datetime.now(timezone.utc).isoformat(), status,
                     task_id or row["task_id"], datetime.now(timezone.utc).isoformat(), schedule_id),
                )
            conn.commit()
            return True

    def list_scheduled_task_runs(
        self, schedule_id: Optional[str] = None, tenant_id: Optional[str] = None,
        user_id: Optional[str] = None, statuses: Optional[list[str]] = None,
        limit: int = 100,
    ) -> list[ScheduledTaskRunRecord]:
        query = "SELECT * FROM scheduled_task_runs WHERE 1 = 1"
        params: list[Any] = []
        for column, value in (("schedule_id", schedule_id), ("tenant_id", tenant_id), ("user_id", user_id)):
            if value is not None:
                query += f" AND {column} = ?"; params.append(str(value))
        if statuses:
            query += " AND status IN (" + ",".join("?" for _ in statuses) + ")"
            params.extend(str(item) for item in statuses)
        query += " ORDER BY scheduled_for DESC LIMIT ?"; params.append(max(1, min(int(limit), 500)))
        with self._lock:
            return [self._scheduled_run_from_row(row) for row in self._get_conn().execute(query, params).fetchall()]

    def get_scheduled_task_metrics(
        self, tenant_id: Optional[str] = None, user_id: Optional[str] = None,
    ) -> dict[str, Any]:
        def scoped(table: str) -> tuple[str, list[Any]]:
            clauses, params = [], []
            for column, value in (("tenant_id", tenant_id), ("user_id", user_id)):
                if value is not None:
                    clauses.append(f"{column} = ?"); params.append(str(value))
            return (" WHERE " + " AND ".join(clauses)) if clauses else "", params
        with self._lock:
            conn = self._get_conn()
            task_where, task_params = scoped("scheduled_tasks")
            run_where, run_params = scoped("scheduled_task_runs")
            task_rows = conn.execute("SELECT status, COUNT(*) AS count FROM scheduled_tasks" + task_where + " GROUP BY status", task_params).fetchall()
            run_rows = conn.execute("SELECT status, COUNT(*) AS count FROM scheduled_task_runs" + run_where + " GROUP BY status", run_params).fetchall()
            next_row = conn.execute("SELECT MIN(next_run_at) AS next_run_at FROM scheduled_tasks" + task_where + (" AND status = 'active'" if task_where else " WHERE status = 'active'"), task_params).fetchone()
            return {
                "tasks_by_status": {str(row["status"]): int(row["count"] or 0) for row in task_rows},
                "runs_by_status": {str(row["status"]): int(row["count"] or 0) for row in run_rows},
                "next_run_at": next_row["next_run_at"] if next_row else None,
            }

    # -- Write idempotency -------------------------------------------------

    def reserve_write(
        self, idempotency_key: str, ttl_seconds: int = 300,
        request_hash: Optional[str] = None,
    ) -> bool:
        """Atomically reserve a write key across Runtime processes.

        Unresolved reservations never expire into an execution permit: a
        crashed worker may already have performed the external write. TTL
        bounds only the replay window for a known executed result.
        """
        with self._lock:
            conn = self._get_conn()
            if conn.in_transaction:
                conn.commit()
            conn.execute("BEGIN IMMEDIATE")
            try:
                now = datetime.now(timezone.utc)
                row = conn.execute(
                    "SELECT status, updated_at, request_hash "
                    "FROM write_reservations WHERE idempotency_key = ?",
                    (str(idempotency_key),),
                ).fetchone()
                if row and row["status"] in {"pending", "uncertain"}:
                    conn.rollback()
                    return False
                if row:
                    if (
                        row["request_hash"]
                        and request_hash
                        and str(row["request_hash"]) != str(request_hash)
                    ):
                        conn.rollback()
                        return False
                    try:
                        age = (
                            now - datetime.fromisoformat(row["updated_at"])
                        ).total_seconds()
                    except (TypeError, ValueError):
                        age = 0
                    if age < float(ttl_seconds):
                        conn.rollback()
                        return False
                timestamp = now.isoformat()
                conn.execute(
                    "INSERT OR REPLACE INTO write_reservations "
                    "(idempotency_key, request_hash, status, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (str(idempotency_key), request_hash, "pending",
                     timestamp, timestamp),
                )
                conn.commit()
                return True
            except Exception:
                if conn.in_transaction:
                    conn.rollback()
                raise

    def mark_write_executed(
        self, idempotency_key: str, request_hash: Optional[str] = None,
    ) -> None:
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute(
                "UPDATE write_reservations SET status = ?, updated_at = ? "
                "WHERE idempotency_key = ? AND status = 'pending' "
                "AND (request_hash IS NULL OR request_hash = ?)",
                ("executed", datetime.now(timezone.utc).isoformat(), idempotency_key, request_hash),
            )
            conn.commit()
            if cursor.rowcount != 1:
                raise RuntimeError("write reservation cannot be marked executed")

    def mark_write_uncertain(
        self, idempotency_key: str, request_hash: str,
    ) -> bool:
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute(
                "UPDATE write_reservations SET status = 'uncertain', updated_at = ? "
                "WHERE idempotency_key = ? AND request_hash = ? "
                "AND status IN ('pending', 'uncertain')",
                (datetime.now(timezone.utc).isoformat(), str(idempotency_key), str(request_hash)),
            )
            conn.commit()
            return cursor.rowcount == 1

    def resolve_write_uncertain(
        self, idempotency_key: str, *, request_hash: str, executed: bool,
    ) -> bool:
        if type(executed) is not bool:
            raise ValueError("executed must be boolean")
        with self._lock:
            conn = self._get_conn()
            if executed:
                cursor = conn.execute(
                    "UPDATE write_reservations SET status = 'executed', updated_at = ? "
                    "WHERE idempotency_key = ? AND request_hash = ? "
                    "AND status IN ('pending', 'uncertain')",
                    (datetime.now(timezone.utc).isoformat(), str(idempotency_key), str(request_hash)),
                )
            else:
                cursor = conn.execute(
                    "DELETE FROM write_reservations WHERE idempotency_key = ? "
                    "AND request_hash = ? AND status IN ('pending', 'uncertain')",
                    (str(idempotency_key), str(request_hash)),
                )
            conn.commit()
            return cursor.rowcount == 1

    def release_write(
        self, idempotency_key: str, request_hash: Optional[str] = None,
    ) -> None:
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                "DELETE FROM write_reservations WHERE idempotency_key = ? AND status = ? "
                "AND (request_hash IS NULL OR request_hash = ?)",
                (idempotency_key, "pending", request_hash),
            )
            conn.commit()

    # -- Durable workflow outbox -----------------------------------------

    def insert_outbox_event(self, event: OutboxEvent) -> None:
        """Insert an already-sanitized event exactly once."""
        now = str(event.created_at or datetime.now(timezone.utc).isoformat())
        payload = json.dumps(
            event.payload or {}, ensure_ascii=False, sort_keys=True, default=str
        )
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                """INSERT OR IGNORE INTO outbox_events
                   (event_id, run_id, event_type, payload, status, retry_count,
                    next_retry_at, created_at, claimed_by, claimed_at, last_error)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL)""",
                (
                    str(event.event_id), str(event.run_id), str(event.event_type),
                    payload, str(event.status or "pending"), int(event.retry_count or 0),
                    event.next_retry_at, now,
                ),
            )
            conn.commit()

    def claim_outbox_events(
        self, limit: int = 20, consumer_id: Optional[str] = None,
    ) -> list[OutboxEvent]:
        """Atomically claim pending events for one SQLite consumer.

        SQLite has no ``SKIP LOCKED``. The backend-wide lock plus conditional
        status updates gives this single-process backend the same no-duplicate
        claim guarantee; a future SQL backend can replace this method with
        row-level locking without changing Runtime code.
        """
        bounded_limit = max(1, min(int(limit), 100))
        owner = str(consumer_id or f"consumer:{uuid.uuid4().hex}")
        now = datetime.now(timezone.utc)
        stale_before = (now - timedelta(minutes=5)).isoformat()
        now_text = now.isoformat()
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                """UPDATE outbox_events
                   SET status = 'pending', claimed_by = NULL, claimed_at = NULL
                   WHERE status = 'claimed' AND claimed_at IS NOT NULL
                     AND claimed_at < ?""",
                (stale_before,),
            )
            rows = conn.execute(
                """SELECT * FROM outbox_events
                   WHERE status = 'pending'
                     AND (next_retry_at IS NULL OR next_retry_at <= ?)
                   ORDER BY created_at ASC LIMIT ?""",
                (now_text, bounded_limit),
            ).fetchall()
            events: list[OutboxEvent] = []
            for row in rows:
                cursor = conn.execute(
                    """UPDATE outbox_events SET status = 'claimed', claimed_by = ?,
                       claimed_at = ? WHERE event_id = ? AND status = 'pending'""",
                    (owner, now_text, str(row["event_id"])),
                )
                if cursor.rowcount == 1:
                    claimed = dict(row)
                    claimed.update({
                        "status": "claimed", "claimed_by": owner,
                        "claimed_at": now_text,
                    })
                    events.append(OutboxEvent.from_row(claimed))
            conn.commit()
            return events

    def mark_outbox_delivered(
        self, event_id: str, consumer_id: Optional[str] = None,
    ) -> bool:
        with self._lock:
            owner_clause = ""
            params: list[Any] = [str(event_id)]
            if consumer_id is not None:
                owner_clause = " AND claimed_by = ?"
                params.append(str(consumer_id))
            cursor = self._get_conn().execute(
                """UPDATE outbox_events SET status = 'delivered',
                   claimed_by = NULL, claimed_at = NULL
                   WHERE event_id = ? AND status = 'claimed'""" + owner_clause,
                params,
            )
            self._get_conn().commit()
            return cursor.rowcount == 1

    def mark_outbox_retry(
        self, event_id: str, next_retry_at: str, error: Optional[str] = None,
        consumer_id: Optional[str] = None,
    ) -> bool:
        with self._lock:
            owner_clause = ""
            params: list[Any] = [str(next_retry_at), str(error) if error else None, str(event_id)]
            if consumer_id is not None:
                owner_clause = " AND claimed_by = ?"
                params.append(str(consumer_id))
            cursor = self._get_conn().execute(
                """UPDATE outbox_events SET status = 'pending',
                   retry_count = retry_count + 1, next_retry_at = ?,
                   last_error = ?, claimed_by = NULL, claimed_at = NULL
                   WHERE event_id = ? AND status = 'claimed'""" + owner_clause,
                params,
            )
            self._get_conn().commit()
            return cursor.rowcount == 1

    def mark_outbox_failed(
        self, event_id: str, error: Optional[str] = None,
        consumer_id: Optional[str] = None,
    ) -> bool:
        """Move an event to a terminal dead-letter state.

        Delivery is at-least-once, so retrying forever is not a safe default:
        a malformed event or permanently unavailable sink would otherwise
        occupy every future poll indefinitely.  The consumer owns the retry
        policy; the store only performs the owner-checked terminal transition.
        """
        with self._lock:
            owner_clause = ""
            params: list[Any] = [str(error) if error else None, str(event_id)]
            if consumer_id is not None:
                owner_clause = " AND claimed_by = ?"
                params.append(str(consumer_id))
            cursor = self._get_conn().execute(
                """UPDATE outbox_events SET status = 'dead_letter',
                   last_error = ?, claimed_by = NULL, claimed_at = NULL
                   WHERE event_id = ? AND status = 'claimed'""" + owner_clause,
                params,
            )
            self._get_conn().commit()
            return cursor.rowcount == 1

    # -- Durable Agent run/event replay ---------------------------------

    @staticmethod
    def _execution_run_from_row(row: Any) -> Optional[ExecutionRunRecord]:
        return ExecutionRunRecord.from_row(dict(row)) if row else None

    def create_execution_run(self, record: ExecutionRunRecord) -> ExecutionRunRecord:
        """Create a durable turn before any provider work can start.

        ``INSERT OR IGNORE`` makes retrying the Runtime bootstrap harmless and
        keeps the run identifier stable when an HTTP worker is restarted.
        """
        data = record.to_dict()
        now = str(data.get("created_at") or datetime.now(timezone.utc).isoformat())
        updated = str(data.get("updated_at") or now)
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                """INSERT OR IGNORE INTO execution_runs
                   (run_id, session_id, turn_id, user_id, tenant_id, status,
                    execution_mode, workflow_id, task_id, metadata, created_at,
                    updated_at, finished_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    str(data["run_id"]), str(data["session_id"]),
                    str(data["turn_id"]), str(data["user_id"]),
                    str(data["tenant_id"]), str(data.get("status") or "running"),
                    str(data.get("execution_mode") or "dry_run"),
                    str(data["workflow_id"]) if data.get("workflow_id") else None,
                    str(data["task_id"]) if data.get("task_id") else None,
                    json.dumps(data.get("metadata") or {}, ensure_ascii=False,
                               sort_keys=True, default=str),
                    now, updated, data.get("finished_at"),
                ),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM execution_runs WHERE run_id = ?",
                (str(data["run_id"]),),
            ).fetchone()
            return self._execution_run_from_row(row) or record

    def append_execution_run_event(self, run_id: str, event: dict[str, Any]) -> bool:
        """Append one sanitized event idempotently and advance run state."""
        if not isinstance(event, dict):
            return False
        try:
            seq = int(event.get("seq"))
        except (TypeError, ValueError):
            return False
        if seq < 1:
            return False
        event_type = str(event.get("event_type") or event.get("type") or "event")
        payload = json.dumps(event, ensure_ascii=False, sort_keys=True, default=str)
        now = str(event.get("timestamp") or datetime.now(timezone.utc).isoformat())
        with self._lock:
            conn = self._get_conn()
            exists = conn.execute(
                "SELECT 1 FROM execution_runs WHERE run_id = ?", (str(run_id),)
            ).fetchone()
            if not exists:
                return False
            cursor = conn.execute(
                """INSERT OR IGNORE INTO execution_run_events
                   (run_id, seq, event_type, payload, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (str(run_id), seq, event_type, payload, now),
            )
            if cursor.rowcount != 1:
                conn.commit()
                return False
            latest_seq = conn.execute(
                "SELECT MAX(seq) FROM execution_run_events WHERE run_id = ?",
                (str(run_id),),
            ).fetchone()[0]
            # A delayed event from another worker is still retained for
            # replay, but it must not move the durable lifecycle backwards
            # after a later ``done`` event has already been committed.
            if int(latest_seq or 0) != seq:
                conn.commit()
                return True
            status = str(event.get("status") or "")
            is_done = event_type == "done"
            terminal = status in {
                "succeeded", "failed", "partially_failed",
                "recovery_required", "cancelled",
            }
            assignments = ["updated_at = ?"]
            values: list[Any] = [now]
            if is_done and status:
                assignments.append("status = ?")
                values.append(status)
                if terminal:
                    assignments.append("finished_at = COALESCE(finished_at, ?)")
                    values.append(now)
            elif status in {"running", "awaiting_confirmation", "recovery_required"}:
                assignments.append("status = ?")
                values.append(status)
            values.append(str(run_id))
            conn.execute(
                "UPDATE execution_runs SET " + ", ".join(assignments)
                + " WHERE run_id = ?",
                values,
            )
            conn.commit()
            return cursor.rowcount == 1

    def get_execution_run(
        self, run_id: str, user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> Optional[ExecutionRunRecord]:
        clauses = ["run_id = ?"]
        params: list[Any] = [str(run_id)]
        if user_id is not None:
            clauses.append("user_id = ?")
            params.append(str(user_id))
        if tenant_id is not None:
            clauses.append("tenant_id = ?")
            params.append(str(tenant_id))
        with self._lock:
            row = self._get_conn().execute(
                "SELECT * FROM execution_runs WHERE " + " AND ".join(clauses),
                params,
            ).fetchone()
            return self._execution_run_from_row(row)

    def get_latest_execution_run(
        self, session_id: str, user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> Optional[ExecutionRunRecord]:
        clauses = ["session_id = ?"]
        params: list[Any] = [str(session_id)]
        if user_id is not None:
            clauses.append("user_id = ?")
            params.append(str(user_id))
        if tenant_id is not None:
            clauses.append("tenant_id = ?")
            params.append(str(tenant_id))
        with self._lock:
            row = self._get_conn().execute(
                "SELECT * FROM execution_runs WHERE " + " AND ".join(clauses)
                + " ORDER BY created_at DESC LIMIT 1",
                params,
            ).fetchone()
            return self._execution_run_from_row(row)

    def list_execution_run_events(
        self, run_id: str, after_seq: int = 0, limit: int = 256,
    ) -> list[dict[str, Any]]:
        bounded_limit = max(1, min(int(limit), 512))
        with self._lock:
            rows = self._get_conn().execute(
                """SELECT payload FROM execution_run_events
                   WHERE run_id = ? AND seq > ? ORDER BY seq ASC LIMIT ?""",
                (str(run_id), max(0, int(after_seq)), bounded_limit),
            ).fetchall()
            events: list[dict[str, Any]] = []
            for row in rows:
                try:
                    payload = json.loads(row[0] or "{}")
                except (TypeError, ValueError):
                    payload = {}
                if isinstance(payload, dict):
                    events.append(payload)
            return events

    def update_execution_run(
        self, run_id: str, *, workflow_id: Optional[str] = None,
        status: Optional[str] = None, metadata: Optional[dict] = None,
    ) -> bool:
        assignments = ["updated_at = ?"]
        values: list[Any] = [datetime.now(timezone.utc).isoformat()]
        if workflow_id is not None:
            assignments.append("workflow_id = ?")
            values.append(str(workflow_id))
        if status is not None:
            assignments.append("status = ?")
            values.append(str(status))
            if status in {
                "succeeded", "failed", "partially_failed",
                "recovery_required", "cancelled",
            }:
                assignments.append("finished_at = COALESCE(finished_at, ?)")
                values.append(datetime.now(timezone.utc).isoformat())
        if metadata is not None:
            encoded = json.dumps(metadata, ensure_ascii=False, sort_keys=True, default=str)
            assignments.append("metadata = ?")
            values.append(encoded)
        values.append(str(run_id))
        with self._lock:
            cursor = self._get_conn().execute(
                "UPDATE execution_runs SET " + ", ".join(assignments)
                + " WHERE run_id = ?", values,
            )
            self._get_conn().commit()
            return cursor.rowcount > 0

    def recover_stale_execution_runs(self, stale_after_seconds: float = 300.0) -> int:
        if float(stale_after_seconds) <= 0:
            return 0
        cutoff = (datetime.now(timezone.utc) - timedelta(
            seconds=float(stale_after_seconds)
        )).isoformat()
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            conn = self._get_conn()
            rows = conn.execute(
                """SELECT run_id, metadata FROM execution_runs
                   WHERE status = 'running' AND updated_at <= ?""",
                (cutoff,),
            ).fetchall()
            recovered = 0
            for row in rows:
                try:
                    metadata = json.loads(row["metadata"] or "{}") or {}
                except (TypeError, ValueError):
                    metadata = {}
                metadata.update({
                    "recovery_reason": "stale_execution_run",
                    "effect_state": "unknown",
                    "recovery_detected_at": now,
                })
                cursor = conn.execute(
                    """UPDATE execution_runs SET status = 'recovery_required',
                       metadata = ?, updated_at = ?
                       WHERE run_id = ? AND status = 'running'""",
                    (json.dumps(metadata, ensure_ascii=False, sort_keys=True), now,
                     str(row["run_id"])),
                )
                if cursor.rowcount != 1:
                    continue
                next_seq = conn.execute(
                    "SELECT COALESCE(MAX(seq), 0) + 1 FROM execution_run_events WHERE run_id = ?",
                    (str(row["run_id"]),),
                ).fetchone()[0]
                event = {
                    "type": "recovery_required",
                    "event_type": "recovery_required",
                    "seq": int(next_seq),
                    "status": "recovery_required",
                    "timestamp": now,
                    "safe_metadata": metadata,
                }
                conn.execute(
                    """INSERT OR IGNORE INTO execution_run_events
                       (run_id, seq, event_type, payload, created_at)
                       VALUES (?, ?, ?, ?, ?)""",
                    (str(row["run_id"]), int(next_seq), "recovery_required",
                     json.dumps(event, ensure_ascii=False, sort_keys=True), now),
                )
                recovered += 1
            conn.commit()
            return recovered

    # -- Approval records --------------------------------------------------

    @staticmethod
    def _token_hash(token: str) -> str:
        return hashlib.sha256(str(token).encode("utf-8")).hexdigest()

    def create_approval(
        self, plan_fingerprint: str, token: str, session_id: str,
        user_id: str, account_id: str, tool_name: str, expires_at: str,
        input_hash: Optional[str] = None, preview_hash: Optional[str] = None,
        request_hash: Optional[str] = None, contract_hash: Optional[str] = None,
    ) -> None:
        now = datetime.now().isoformat()
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                """INSERT OR IGNORE INTO approvals
                   (plan_fingerprint, token_hash, session_id, user_id, account_id,
                   tool_name, expires_at, status, created_at, input_hash,
                   preview_hash, request_hash, contract_hash)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?, ?)""",
                (
                    plan_fingerprint, self._token_hash(token), str(session_id),
                    str(user_id), str(account_id or ""), str(tool_name),
                    str(expires_at), now, input_hash, preview_hash,
                    request_hash, contract_hash,
                ),
            )
            conn.commit()

    def get_approval(self, plan_fingerprint: str) -> Optional[dict]:
        with self._lock:
            row = self._get_conn().execute(
                "SELECT * FROM approvals WHERE plan_fingerprint = ?",
                (plan_fingerprint,),
            ).fetchone()
            return dict(row) if row else None

    def validate_approval(
        self, plan_fingerprint: str, token: str, session_id: str,
        user_id: str, account_id: str, tool_name: str,
        input_hash: Optional[str] = None, preview_hash: Optional[str] = None,
        request_hash: Optional[str] = None, contract_hash: Optional[str] = None,
    ) -> tuple[bool, str]:
        row = self.get_approval(plan_fingerprint)
        if not row:
            return False, "approval record not found"
        if row.get("status") != "pending":
            return False, "approval has already been consumed"
        if row.get("token_hash") != self._token_hash(token):
            return False, "approval token mismatch"
        if str(row.get("session_id")) != str(session_id):
            return False, "approval session mismatch"
        if str(row.get("user_id")) != str(user_id):
            return False, "approval user mismatch"
        if str(row.get("account_id")) != str(account_id or ""):
            return False, "approval account mismatch"
        if str(row.get("tool_name")) != str(tool_name):
            return False, "approval tool mismatch"
        for field, expected in (
            ("input_hash", input_hash), ("preview_hash", preview_hash),
            ("request_hash", request_hash), ("contract_hash", contract_hash),
        ):
            stored = row.get(field)
            if stored and str(stored) != str(expected or ""):
                return False, f"approval {field} mismatch"
        try:
            if datetime.fromisoformat(str(row.get("expires_at"))) <= datetime.now():
                return False, "approval expired"
        except (TypeError, ValueError):
            return False, "approval expiry is invalid"
        return True, ""

    def consume_approval(self, plan_fingerprint: str, token: str) -> bool:
        with self._lock:
            now = datetime.now().isoformat()
            cursor = self._get_conn().execute(
                """UPDATE approvals SET status = 'consumed', consumed_at = ?
                   WHERE plan_fingerprint = ? AND token_hash = ? AND status = 'pending'""",
                (now, plan_fingerprint, self._token_hash(token)),
            )
            self._get_conn().commit()
            return cursor.rowcount > 0

    # -- Managed Agent Skills -------------------------------------------


    def create_skill_version(
        self, version_id: str, tenant_id: str, skill_name: str,
        version: str, files: dict[str, dict[str, Any]], sha256: str,
        created_by: str, status: str = "draft",
    ) -> dict:
        return self._extensions.create_skill_version(
            version_id, tenant_id, skill_name, version, files, sha256, created_by, status,
        )

    def get_skill_version(
        self, tenant_id: str, skill_name: str, version: Optional[str] = None,
    ) -> Optional[dict]:
        return self._extensions.get_skill_version(tenant_id, skill_name, version)

    def list_skill_versions(
        self, tenant_id: str, skill_name: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict]:
        return self._extensions.list_skill_versions(tenant_id, skill_name, limit)

    def publish_skill_version(
        self, tenant_id: str, skill_name: str, version: str,
    ) -> Optional[dict]:
        return self._extensions.publish_skill_version(tenant_id, skill_name, version)

    def unpublish_skill_version(
        self, tenant_id: str, skill_name: str, version: str,
    ) -> Optional[dict]:
        """Remove the active release pointer and archive that version.

        The version remains available for audit or an explicit later rollback;
        only the tenant/Skill release pointer is removed.  The join and
        version check make this operation safe when an older API request tries
        to unpublish a release that has already been replaced.
        """
        return self._extensions.unpublish_skill_version(tenant_id, skill_name, version)

    def set_skill_evaluation(
        self, version_id: str, tenant_id: str, status: str, run_id: Optional[str] = None,
        report: Optional[dict] = None,
    ) -> bool:
        return self._extensions.set_skill_evaluation(version_id, tenant_id, status, run_id, report)

    def create_skill_evaluation(
        self, run_id: str, version_id: str, tenant_id: str,
        status: str = "queued",
    ) -> dict:
        return self._extensions.create_skill_evaluation(run_id, version_id, tenant_id, status)

    def claim_skill_evaluation(
        self, run_id: str, version_id: str, tenant_id: str,
    ) -> Optional[dict]:
        """Atomically claim one version for a queued evaluation.

        The version row is the durable single-flight lock.  Keeping the
        claim and run creation in one transaction prevents two API workers
        from evaluating the same immutable version concurrently, and gives a
        future MySQL/PostgreSQL backend a precise transaction contract to
        preserve.
        """
        return self._extensions.claim_skill_evaluation(run_id, version_id, tenant_id)

    def get_skill_evaluation(self, run_id: str, tenant_id: str) -> Optional[dict]:
        return self._extensions.get_skill_evaluation(run_id, tenant_id)

    def update_skill_evaluation_run(
        self, run_id: str, tenant_id: str, status: str, report: Optional[dict] = None,
        error: Optional[str] = None,
    ) -> bool:
        return self._extensions.update_skill_evaluation_run(
            run_id, tenant_id, status, report, error,
        )

    def recover_stale_skill_evaluations(
        self, stale_after_seconds: float = 900.0,
    ) -> int:
        """Mark evaluations interrupted by a process failure as retryable.

        Evaluation workers are process-local, so a queued/running row cannot
        be resumed after the process that owned it disappears.  The update is
        guarded by both ``run_id`` and the version's current run ID, which
        keeps a late worker from overwriting a newer retry.  A future
        multi-process backend should preserve this atomic lease-recovery
        contract, even if it implements it with row locks or a lease table.
        """
        return self._extensions.recover_stale_skill_evaluations(stale_after_seconds)

    # -- Generic Plugin package control plane ---------------------------


    def create_plugin_package(
        self, package_id: str, tenant_id: str, plugin_id: str, version: str,
        manifest: dict, files: dict[str, dict[str, Any]], package_digest: str,
        signature_verified: bool, created_by: str, status: str = "validated",
    ) -> dict:
        """Persist one immutable, tenant-owned Plugin package snapshot."""
        return self._extensions.create_plugin_package(
            package_id, tenant_id, plugin_id, version, manifest, files, package_digest,
            signature_verified, created_by, status,
        )

    def get_plugin_package(
        self, tenant_id: str, plugin_id: str, version: Optional[str] = None,
    ) -> Optional[dict]:
        return self._extensions.get_plugin_package(tenant_id, plugin_id, version)

    def list_plugin_packages(
        self, tenant_id: str, plugin_id: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict]:
        return self._extensions.list_plugin_packages(tenant_id, plugin_id, limit)

    def activate_plugin_package(
        self, tenant_id: str, plugin_id: str, version: str,
    ) -> Optional[dict]:
        return self._extensions.activate_plugin_package(tenant_id, plugin_id, version)

    def deactivate_plugin_package(
        self, tenant_id: str, plugin_id: str, version: str,
    ) -> Optional[dict]:
        return self._extensions.deactivate_plugin_package(tenant_id, plugin_id, version)

    def uninstall_plugin_package(
        self, tenant_id: str, plugin_id: str, version: str,
    ) -> Optional[dict]:
        """Remove a package from the active release without deleting audit data."""
        return self._extensions.uninstall_plugin_package(tenant_id, plugin_id, version)

    # -- External MCP control plane -----------------------------------


    def create_mcp_server(self, data: dict[str, Any]) -> dict:
        """Persist a tenant-scoped external MCP Server declaration."""
        return self._extensions.create_mcp_server(data)

    def get_mcp_server(self, tenant_id: str, server_id: str) -> Optional[dict]:
        return self._extensions.get_mcp_server(tenant_id, server_id)

    def list_mcp_servers(self, tenant_id: str, limit: int = 50) -> list[dict]:
        return self._extensions.list_mcp_servers(tenant_id, limit)

    def update_mcp_server(self, server_id: str, tenant_id: str, data: dict[str, Any]) -> Optional[dict]:
        return self._extensions.update_mcp_server(server_id, tenant_id, data)


    def upsert_mcp_tool(self, data: dict[str, Any]) -> dict:
        return self._extensions.upsert_mcp_tool(data)

    def list_mcp_tools(self, server_id: str, tenant_id: Optional[str] = None) -> list[dict]:
        return self._extensions.list_mcp_tools(server_id, tenant_id)

    def get_mcp_tool(self, tool_id: str, tenant_id: str) -> Optional[dict]:
        return self._extensions.get_mcp_tool(tool_id, tenant_id)

    def update_mcp_tool(self, tool_id: str, tenant_id: str, data: dict[str, Any]) -> Optional[dict]:
        return self._extensions.update_mcp_tool(tool_id, tenant_id, data)
    
    # -- Session --
    
    # -- Agent Memory -----------------------------------------------------


    def save_memory(self, record: MemoryRecord) -> None:
        """Persist one already-policy-checked memory record."""
        return self._memories.save_memory(record)

    def find_active_memory(
        self, memory_key: str, *, tenant_id: str, user_id: str,
    ) -> Optional[MemoryRecord]:
        """Find the current version of one scoped logical memory."""
        return self._memories.find_active_memory(memory_key, tenant_id=tenant_id, user_id=user_id)

    def supersede_memory(
        self, memory_id: str, superseded_by: str, *, tenant_id: str, user_id: str,
    ) -> bool:
        """Close an older logical version while retaining its audit history."""
        return self._memories.supersede_memory(
            memory_id, superseded_by, tenant_id=tenant_id, user_id=user_id,
        )

    def search_memories(
        self, query: str, *, tenant_id: str, user_id: str,
        session_id: Optional[str] = None, kinds: Optional[List[str]] = None,
        limit: int = 10,
    ) -> List[MemoryRecord]:
        """Scope memory first, then perform deterministic lexical ranking."""
        return self._memories.search_memories(
            query, tenant_id=tenant_id, user_id=user_id, session_id=session_id, kinds=kinds,
            limit=limit,
        )

    def delete_memory(self, memory_id: str, *, tenant_id: str, user_id: str) -> bool:
        """Tombstone a record; a tenant/user can never delete another scope."""
        return self._memories.delete_memory(memory_id, tenant_id=tenant_id, user_id=user_id)

    def purge_memories(self, *, before: str, expired_before: str) -> int:
        """Bounded lifecycle cleanup for expired records and old tombstones."""
        return self._memories.purge_memories(before=before, expired_before=expired_before)

    def create_session(self, session_id: str, user_id: str, account_id: str = None, 
                       metadata: dict = None) -> None:
        return self._sessions.create_session(session_id, user_id, account_id, metadata)
    
    def update_session(self, session_id: str, metadata: dict = None) -> None:
        return self._sessions.update_session(session_id, metadata)
    
    def get_session(
        self, session_id: str, user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> Optional[dict]:
        return self._sessions.get_session(session_id, user_id, tenant_id)

    def delete_session(self, session_id: str) -> bool:
        """Delete a session; SQLite foreign keys remove its local history."""
        return self._sessions.delete_session(session_id)

    def list_sessions(
        self, user_id: str = None, limit: int = 50,
        tenant_id: Optional[str] = None,
        before_updated_at: Optional[str] = None,
        before_session_id: Optional[str] = None,
    ) -> List[dict]:
        return self._sessions.list_sessions(
            user_id, limit, tenant_id, before_updated_at, before_session_id,
        )

    def acquire_session_lease(
        self, session_id: str, lease_owner: str, lease_seconds: float = 300.0,
    ) -> bool:
        """Atomically reserve a session across Runtime instances."""
        return self._sessions.acquire_session_lease(session_id, lease_owner, lease_seconds)

    def heartbeat_session_lease(
        self, session_id: str, lease_owner: str, lease_seconds: float = 300.0,
    ) -> bool:
        return self._sessions.heartbeat_session_lease(session_id, lease_owner, lease_seconds)

    def release_session_lease(self, session_id: str, lease_owner: str) -> bool:
        return self._sessions.release_session_lease(session_id, lease_owner)

    def record_conversation_message(self, record: ConversationMessageRecord) -> None:
        return self._sessions.record_conversation_message(record)

    def list_conversation_messages(
        self, session_id: str, limit: int = 200,
    ) -> List[ConversationMessageRecord]:
        return self._sessions.list_conversation_messages(session_id, limit)

    def list_recent_user_messages(
        self, session_id: str, limit: int = 128,
    ) -> list[dict[str, str]]:
        return self._sessions.list_recent_user_messages(session_id, limit)

    def list_conversation_message_page(
        self,
        session_id: str,
        limit: int = 10,
        before_message_id: Optional[str] = None,
    ) -> ConversationMessagePage:
        return self._sessions.list_conversation_message_page(session_id, limit, before_message_id)

    def update_conversation_message_metadata(
        self,
        session_id: str,
        turn_id: str,
        role: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> int:
        """Merge metadata into matching transcript rows without changing content."""
        return self._sessions.update_conversation_message_metadata(
            session_id, turn_id, role, metadata,
        )

    def save_conversation_feedback(
        self,
        session_id: str,
        turn_id: str,
        *,
        user_id: str,
        tenant_id: str,
        feedback: dict[str, Any],
    ) -> bool:
        """Atomically persist one feedback write and its analytics aggregate."""
        with self._lock:
            return persist_conversation_feedback(
                self._get_conn(),
                mysql=getattr(self, "backend_name", "sqlite") == "mysql",
                session_id=str(session_id),
                turn_id=str(turn_id),
                user_id=str(user_id),
                tenant_id=str(tenant_id),
                feedback=dict(feedback),
            )

    def get_conversation_feedback_trend(
        self,
        *,
        days: int,
        user_id: str,
        tenant_id: str,
    ) -> dict[str, Any]:
        """Return bounded daily aggregates scoped to one principal."""
        with self._lock:
            return query_conversation_feedback_trend(
                self._get_conn(),
                days=int(days),
                user_id=str(user_id),
                tenant_id=str(tenant_id),
            )

    def list_conversation_feedback_review_queue(
        self, *, tenant_id: str, status: str = "pending", limit: int = 50,
    ) -> list[dict[str, Any]]:
        with self._lock:
            return query_feedback_review_queue(
                self._get_conn(),
                tenant_id=str(tenant_id),
                status=str(status),
                limit=int(limit),
            )

    def review_conversation_feedback(
        self,
        feedback_id: str,
        *,
        tenant_id: str,
        reviewer_id: str,
        review_status: str,
        expected_behavior: str,
        reviewed_at: str,
        assertions: Optional[dict[str, Any]] = None,
    ) -> bool:
        with self._lock:
            return update_feedback_review(
                self._get_conn(),
                feedback_id=str(feedback_id),
                tenant_id=str(tenant_id),
                reviewer_id=str(reviewer_id),
                review_status=str(review_status),
                expected_behavior=str(expected_behavior or ""),
                reviewed_at=str(reviewed_at),
                assertions=assertions,
            )

    def rebuild_knowledge_semantic_index(
        self,
        records: list[dict[str, Any]],
        *,
        scope: str,
        fingerprint: str,
    ) -> bool:
        with self._lock:
            return persist_semantic_index(
                self._get_conn(),
                mysql=getattr(self, "backend_name", "sqlite") == "mysql",
                records=records,
                scope=scope,
                fingerprint=fingerprint,
            )

    def search_knowledge_semantic_index(
        self,
        vector: list[float],
        *,
        scope: str,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        with self._lock:
            return query_semantic_index(
                self._get_conn(),
                query_vector=vector,
                scope=scope,
                limit=limit,
            )

    def is_knowledge_semantic_index_current(
        self, *, scope: str, fingerprint: str,
    ) -> bool:
        with self._lock:
            return check_semantic_index_current(
                self._get_conn(),
                scope=scope,
                fingerprint=fingerprint,
            )

    def get_knowledge_semantic_index_metadata(self, *, scope: str) -> dict[str, Any]:
        with self._lock:
            return query_semantic_index_metadata(self._get_conn(), scope=scope)

    def delete_conversation_messages(self, session_id: str) -> None:
        """Delete one session transcript after the adapter checked its scope."""
        with self._lock:
            self._get_conn().execute(
                "DELETE FROM conversation_messages WHERE session_id = ?",
                (str(session_id),),
            )
            self._get_conn().commit()

    # -- Tenant-scoped Markdown Wiki documents -------------------------


    def create_knowledge_document(self, record: KnowledgeDocumentRecord) -> KnowledgeDocumentRecord:
        return self._knowledge.create_knowledge_document(record)

    def update_knowledge_document(
        self, document_id: str, *, tenant_id: str, data: dict[str, Any],
    ) -> Optional[KnowledgeDocumentRecord]:
        return self._knowledge.update_knowledge_document(
            document_id, tenant_id=tenant_id, data=data,
        )

    def delete_knowledge_document(
        self, document_id: str, *, tenant_id: str,
    ) -> Optional[KnowledgeDocumentRecord]:
        return self._knowledge.delete_knowledge_document(document_id, tenant_id=tenant_id)

    def get_knowledge_document(
        self, document_id: str, *, tenant_id: Optional[str] = None,
    ) -> Optional[KnowledgeDocumentRecord]:
        return self._knowledge.get_knowledge_document(document_id, tenant_id=tenant_id)

    def list_knowledge_documents(
        self, tenant_id: str, status: Optional[str] = None, limit: int = 100,
    ) -> list[KnowledgeDocumentRecord]:
        return self._knowledge.list_knowledge_documents(tenant_id, status, limit)

    def publish_knowledge_document(
        self, document_id: str, *, tenant_id: str,
    ) -> Optional[KnowledgeDocumentRecord]:
        return self._knowledge.publish_knowledge_document(document_id, tenant_id=tenant_id)

    def unpublish_knowledge_document(
        self, document_id: str, *, tenant_id: str,
    ) -> Optional[KnowledgeDocumentRecord]:
        return self._knowledge.unpublish_knowledge_document(document_id, tenant_id=tenant_id)

    # -- Immutable raw Wiki sources -----------------------------------


    def create_raw_knowledge_source(
        self, record: RawKnowledgeSourceRecord,
    ) -> RawKnowledgeSourceRecord:
        return self._knowledge.create_raw_knowledge_source(record)

    def get_raw_knowledge_source(
        self, source_id: str, *, tenant_id: Optional[str] = None,
    ) -> Optional[RawKnowledgeSourceRecord]:
        return self._knowledge.get_raw_knowledge_source(source_id, tenant_id=tenant_id)

    def find_raw_knowledge_source_by_hash(
        self, tenant_id: str, sha256: str,
    ) -> Optional[RawKnowledgeSourceRecord]:
        return self._knowledge.find_raw_knowledge_source_by_hash(tenant_id, sha256)

    def update_raw_knowledge_source(
        self, source_id: str, *, tenant_id: str, data: dict[str, Any],
    ) -> Optional[RawKnowledgeSourceRecord]:
        return self._knowledge.update_raw_knowledge_source(
            source_id, tenant_id=tenant_id, data=data,
        )

    def claim_raw_knowledge_source(
        self,
        source_id: str,
        *,
        tenant_id: str,
        task_id: Optional[str],
        started_at: str,
    ) -> Optional[RawKnowledgeSourceRecord]:
        """Atomically move a retryable raw source into ``ingesting``."""
        return self._knowledge.claim_raw_knowledge_source(
            source_id, tenant_id=tenant_id, task_id=task_id, started_at=started_at,
        )

    def recover_stale_raw_knowledge_sources(
        self,
        *,
        tenant_id: str,
        stale_after_seconds: float = 900.0,
        recovered_at: Optional[str] = None,
    ) -> int:
        """Release raw sources whose ingest worker stopped heartbeating."""
        return self._knowledge.recover_stale_raw_knowledge_sources(
            tenant_id=tenant_id, stale_after_seconds=stale_after_seconds,
            recovered_at=recovered_at,
        )

    def list_raw_knowledge_sources(
        self, tenant_id: str, status: Optional[str] = None,
        limit: int = 100,
    ) -> list[RawKnowledgeSourceRecord]:
        return self._knowledge.list_raw_knowledge_sources(tenant_id, status, limit)


    def rebuild_knowledge_search_index(
        self, chunks: list[dict[str, Any]], *, scope: str,
    ) -> bool:
        return self._knowledge.rebuild_knowledge_search_index(chunks, scope=scope)

    def search_knowledge_search_index(
        self, query: str, *, scopes: list[str], limit: int = 100,
    ) -> list[dict[str, Any]]:
        return self._knowledge.search_knowledge_search_index(query, scopes=scopes, limit=limit)

    # -- Campaign creation templates ------------------------------------

    @staticmethod
    def _creation_template_row(row: Any) -> Optional[CreationTemplateRecord]:
        return CreationTemplateRecord.from_row(dict(row)) if row else None

    def create_creation_template(self, record: CreationTemplateRecord) -> CreationTemplateRecord:
        data = record.to_dict()
        with self._lock:
            conn = self._get_conn()
            try:
                conn.execute(
                    """INSERT INTO creation_templates
                       (template_id, tenant_id, user_id, name, description,
                        provider, blueprint_id, blueprint_version, ad_format,
                        scope_type, account_id, region, tags, template_values,
                        status, is_default, usage_count, created_at, updated_at, last_used_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        data["template_id"], data["tenant_id"], data["user_id"],
                        data["name"], data["description"], data["provider"],
                        data["blueprint_id"], data["blueprint_version"], data["ad_format"],
                        data["scope_type"], data["account_id"], data["region"],
                        json.dumps(data["tags"], ensure_ascii=False),
                        json.dumps(data["values"], ensure_ascii=False), data["status"],
                        int(data["is_default"]), data["usage_count"], data["created_at"], data["updated_at"],
                        data["last_used_at"],
                    ),
                )
                if data["is_default"]:
                    conn.execute(
                        """UPDATE creation_templates SET is_default = 0
                           WHERE tenant_id = ? AND user_id = ? AND provider = ?
                             AND blueprint_id = ? AND scope_type = ?
                             AND account_id = ? AND region = ? AND template_id != ?""",
                        (
                            data["tenant_id"], data["user_id"], data["provider"],
                            data["blueprint_id"], data["scope_type"], data["account_id"],
                            data["region"], data["template_id"],
                        ),
                    )
            except sqlite3.IntegrityError as exc:
                raise PersistenceConflictError(
                    "creation template violates a persistence constraint"
                ) from exc
            conn.commit()
            return self._creation_template_row(conn.execute(
                "SELECT * FROM creation_templates WHERE template_id = ?",
                (data["template_id"],),
            ).fetchone()) or record

    def get_creation_template(
        self, template_id: str, *, tenant_id: str, user_id: str,
    ) -> Optional[CreationTemplateRecord]:
        with self._lock:
            return self._creation_template_row(self._get_conn().execute(
                """SELECT * FROM creation_templates
                   WHERE template_id = ? AND tenant_id = ? AND user_id = ?""",
                (str(template_id), str(tenant_id), str(user_id)),
            ).fetchone())

    def list_creation_templates(
        self, tenant_id: str, user_id: str, *, provider: Optional[str] = None,
        blueprint_id: Optional[str] = None, status: Optional[str] = None,
        query: Optional[str] = None, limit: int = 100,
    ) -> list[CreationTemplateRecord]:
        bounded_limit = max(1, min(int(limit), 200))
        clauses = ["tenant_id = ?", "user_id = ?"]
        params: list[Any] = [str(tenant_id), str(user_id)]
        if provider:
            clauses.append("provider = ?")
            params.append(str(provider))
        if blueprint_id:
            clauses.append("blueprint_id = ?")
            params.append(str(blueprint_id))
        if status:
            clauses.append("status = ?")
            params.append(str(status))
        if query:
            clauses.append("(name LIKE ? OR description LIKE ? OR tags LIKE ?)")
            needle = f"%{str(query).strip()}%"
            params.extend([needle, needle, needle])
        params.append(bounded_limit)
        with self._lock:
            rows = self._get_conn().execute(
                f"""SELECT * FROM creation_templates
                    WHERE {' AND '.join(clauses)}
                    ORDER BY updated_at DESC, name ASC LIMIT ?""",
                params,
            ).fetchall()
            return [self._creation_template_row(row) for row in rows if row]

    def update_creation_template(
        self, template_id: str, *, tenant_id: str, user_id: str,
        data: dict[str, Any],
    ) -> Optional[CreationTemplateRecord]:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute(
                """UPDATE creation_templates
                   SET name = ?, description = ?, scope_type = ?, account_id = ?,
                       region = ?, tags = ?, template_values = ?, status = ?, is_default = ?,
                       updated_at = ?
                   WHERE template_id = ? AND tenant_id = ? AND user_id = ?""",
                (
                    data["name"], data["description"], data["scope_type"],
                    data["account_id"], data["region"],
                    json.dumps(data["tags"], ensure_ascii=False),
                    json.dumps(data["values"], ensure_ascii=False), data["status"],
                    int(data["is_default"]), now,
                    str(template_id), str(tenant_id), str(user_id),
                ),
            )
            if cursor.rowcount and data["is_default"]:
                conn.execute(
                    """UPDATE creation_templates SET is_default = 0
                       WHERE tenant_id = ? AND user_id = ? AND provider = ?
                         AND blueprint_id = ? AND scope_type = ?
                         AND account_id = ? AND region = ? AND template_id != ?""",
                    (
                        str(tenant_id), str(user_id), data["provider"], data["blueprint_id"],
                        data["scope_type"], data["account_id"], data["region"], str(template_id),
                    ),
                )
            conn.commit()
            if not cursor.rowcount:
                return None
            return self._creation_template_row(conn.execute(
                "SELECT * FROM creation_templates WHERE template_id = ?",
                (str(template_id),),
            ).fetchone())

    def delete_creation_template(
        self, template_id: str, *, tenant_id: str, user_id: str,
    ) -> Optional[CreationTemplateRecord]:
        with self._lock:
            conn = self._get_conn()
            existing = self._creation_template_row(conn.execute(
                """SELECT * FROM creation_templates
                   WHERE template_id = ? AND tenant_id = ? AND user_id = ?""",
                (str(template_id), str(tenant_id), str(user_id)),
            ).fetchone())
            if not existing:
                return None
            conn.execute(
                """DELETE FROM creation_templates
                   WHERE template_id = ? AND tenant_id = ? AND user_id = ?""",
                (str(template_id), str(tenant_id), str(user_id)),
            )
            conn.commit()
            return existing

    def record_creation_template_usage(
        self, template_id: str, *, tenant_id: str, user_id: str,
    ) -> Optional[CreationTemplateRecord]:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute(
                """UPDATE creation_templates
                   SET usage_count = usage_count + 1, last_used_at = ?, updated_at = ?
                   WHERE template_id = ? AND tenant_id = ? AND user_id = ?
                     AND status = 'active'""",
                (now, now, str(template_id), str(tenant_id), str(user_id)),
            )
            conn.commit()
            if not cursor.rowcount:
                return None
            return self._creation_template_row(conn.execute(
                "SELECT * FROM creation_templates WHERE template_id = ?",
                (str(template_id),),
            ).fetchone())
    
    # -- Tool Calls --
    
    def record_tool_call(self, record: ToolCallRecord) -> None:
        d = record.to_dict()
        with self._lock:
            conn = self._get_conn()
            sql = """INSERT INTO tool_calls 
                     (id, session_id, turn_id, tool_name, platform, input_data, output_data, 
                      success, error, started_at, ended_at)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""
            conn.execute(sql, (
                d['id'], d['session_id'], d['turn_id'], d['tool_name'], d['platform'],
                d['input_data'], d['output_data'], int(d['success']), d['error'],
                d['started_at'], d['ended_at']
            ))
            conn.commit()
    
    def list_tool_calls(self, session_id: str, turn_id: str = None, limit: int = 100) -> List[ToolCallRecord]:
        with self._lock:
            conn = self._get_conn()
            if turn_id:
                rows = conn.execute(
                    "SELECT * FROM tool_calls WHERE session_id = ? AND turn_id = ? ORDER BY started_at ASC LIMIT ?",
                    (session_id, turn_id, limit)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM tool_calls WHERE session_id = ? ORDER BY started_at DESC LIMIT ?",
                    (session_id, limit)
                ).fetchall()
            return [ToolCallRecord.from_row(dict(r)) for r in rows]
    
    # -- Campaign State --
    
    def save_campaign(self, record: CampaignRecord) -> None:
        return self._workflows.save_campaign(record)
    
    def get_campaign(
        self, platform: str, campaign_id: str, account_id: str = None
    ) -> Optional[CampaignRecord]:
        return self._workflows.get_campaign(platform, campaign_id, account_id)
    
    def list_campaigns(
        self, platform: str = None, status: str = None, limit: int = 100,
        account_id: str = None,
    ) -> List[CampaignRecord]:
        return self._workflows.list_campaigns(platform, status, limit, account_id)
    
    def update_campaign_status(
        self, platform: str, campaign_id: str, status: str,
        account_id: str = None,
    ) -> bool:
        return self._workflows.update_campaign_status(platform, campaign_id, status, account_id)
    
    def delete_campaign(
        self, platform: str, campaign_id: str, account_id: str = None,
    ) -> bool:
        return self._workflows.delete_campaign(platform, campaign_id, account_id)

    # -- Workflow audit / compensation ---------------------------------

    def create_workflow(
        self, workflow_id: str, session_id: str, intent_type: str,
        execution_mode: str, status: str = "planned", metadata: dict = None,
        emit_outbox: bool = True,
    ) -> None:
        return self._workflows.create_workflow(
            workflow_id, session_id, intent_type, execution_mode, status, metadata,
            emit_outbox,
        )

    def update_workflow(
        self, workflow_id: str, status: str, metadata: dict = None,
        emit_outbox: bool = True,
    ) -> bool:
        return self._workflows.update_workflow(workflow_id, status, metadata, emit_outbox)

    def heartbeat_workflow(
        self, workflow_id: str, lease_owner: str, lease_seconds: float = 300.0,
    ) -> bool:
        """Refresh an active workflow lease without changing its state."""
        return self._workflows.heartbeat_workflow(workflow_id, lease_owner, lease_seconds)

    def recover_stale_workflow(
        self, workflow_id: str, stale_after_seconds: float = 300.0,
        metadata: dict = None,
    ) -> bool:
        """Atomically move an expired running workflow into recovery."""
        return self._workflows.recover_stale_workflow(workflow_id, stale_after_seconds, metadata)

    def claim_workflow_recovery(
        self, workflow_id: str, lease_owner: str,
        stale_after_seconds: float = 300.0, lease_seconds: float = 300.0,
    ) -> bool:
        """Atomically claim a stale/runnable workflow for one recovery worker."""
        return self._workflows.claim_workflow_recovery(
            workflow_id, lease_owner, stale_after_seconds, lease_seconds,
        )

    def release_workflow_lease(self, workflow_id: str, lease_owner: str) -> bool:
        """Release only the lease owned by the calling recovery worker."""
        return self._workflows.release_workflow_lease(workflow_id, lease_owner)

    def add_workflow_item(
        self, item_id: str, workflow_id: str, sequence: int, platform: str,
        tool_name: str, status: str, input_data: dict,
        output_data: dict = None, error: str = None,
        compensation_required: bool = False,
        resource_type: Optional[str] = None,
        parent_sequence: Optional[int] = None,
        parent_resource_id: Optional[str] = None,
        provider_resource_id: Optional[str] = None,
        logical_resource_id: Optional[str] = None,
        account_id: Optional[str] = None,
        parent_resource_type: Optional[str] = None,
    ) -> None:
        return self._workflows.add_workflow_item(
            item_id, workflow_id, sequence, platform, tool_name, status, input_data,
            output_data, error, compensation_required, resource_type, parent_sequence,
            parent_resource_id, provider_resource_id, logical_resource_id, account_id,
            parent_resource_type,
        )

    def upsert_workflow_item(
        self, item_id: str, workflow_id: str, sequence: int, platform: str,
        tool_name: str, status: str, input_data: dict,
        output_data: dict = None, error: str = None,
        compensation_required: bool = False,
        resource_type: Optional[str] = None,
        parent_sequence: Optional[int] = None,
        parent_resource_id: Optional[str] = None,
        provider_resource_id: Optional[str] = None,
        logical_resource_id: Optional[str] = None,
        account_id: Optional[str] = None,
        parent_resource_type: Optional[str] = None,
    ) -> None:
        """Create or advance an item checkpoint without duplicating rows.

        Workflow items are registered before execution and advanced after the
        handler returns.  ``INSERT OR REPLACE`` would reset creation metadata
        and could overwrite a newer state, so the update path validates the
        state transition and only changes the mutable checkpoint fields.
        """
        return self._workflows.upsert_workflow_item(
            item_id, workflow_id, sequence, platform, tool_name, status, input_data,
            output_data, error, compensation_required, resource_type, parent_sequence,
            parent_resource_id, provider_resource_id, logical_resource_id, account_id,
            parent_resource_type,
        )

    def get_workflow(
        self, workflow_id: str, user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> Optional[dict]:
        return self._workflows.get_workflow(workflow_id, user_id, tenant_id)

    def list_workflow_items(self, workflow_id: str) -> list[dict]:
        return self._workflows.list_workflow_items(workflow_id)

    def update_workflow_item(
        self,
        workflow_id: str,
        sequence: int,
        status: str,
        output_data: Optional[dict] = None,
        error: Optional[str] = None,
        compensation_required: Optional[bool] = None,
        resource_type: Optional[str] = None,
        parent_sequence: Optional[int] = None,
        parent_resource_id: Optional[str] = None,
        provider_resource_id: Optional[str] = None,
        logical_resource_id: Optional[str] = None,
        account_id: Optional[str] = None,
        parent_resource_type: Optional[str] = None,
    ) -> bool:
        """Update one item during an explicitly verified reconciliation."""
        return self._workflows.update_workflow_item(
            workflow_id, sequence, status, output_data, error, compensation_required,
            resource_type, parent_sequence, parent_resource_id, provider_resource_id,
            logical_resource_id, account_id, parent_resource_type,
        )

    def list_resumable_workflows(
        self, user_id: Optional[str] = None, limit: int = 50,
        include_stale_running: bool = False, stale_after_seconds: float = 300.0,
        tenant_id: Optional[str] = None,
    ) -> list[dict]:
        """List non-terminal workflows for an operator/recovery worker."""
        return self._workflows.list_resumable_workflows(
            user_id, limit, include_stale_running, stale_after_seconds, tenant_id,
        )

    def mark_workflow_items_for_compensation(
        self, workflow_id: str, sequences: list[int]
    ) -> None:
        return self._workflows.mark_workflow_items_for_compensation(workflow_id, sequences)
