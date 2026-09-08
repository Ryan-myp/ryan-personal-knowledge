"""MySQL persistence backend for the ad-agent.

The domain store keeps its SQL behind the persistence boundary.  This adapter
reuses the existing backend methods while translating the small SQLite syntax
surface used by the current store and overrides claims with InnoDB row locks.
Runtime, Skills, Tools and Capabilities do not know which database is active.
"""

from __future__ import annotations

import re
import sqlite3
import threading
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from urllib.parse import parse_qs, unquote, urlparse

from .models import OutboxEvent, TaskRecord, ScheduledTaskRecord, ScheduledTaskRunRecord
from .store import AdAgentStore


class _MySQLRow(dict):
    """Dict row that also preserves SQLite-style integer indexing."""

    def __init__(self, columns: list[str], values: tuple[Any, ...]):
        super().__init__(zip(columns, values))
        self._columns = columns
        self._values = values

    def __getitem__(self, key: Any) -> Any:
        if isinstance(key, int):
            return self._values[key]
        return super().__getitem__(key)


class _MySQLCursor:
    def __init__(self, cursor: Any):
        self._cursor = cursor
        self._columns: list[str] = []

    @property
    def rowcount(self) -> int:
        return int(self._cursor.rowcount)

    def execute(self, statement: str, params: Any = None) -> "_MySQLCursor":
        try:
            self._cursor.execute(statement, params or ())
        except Exception as exc:
            # A few existing domain methods intentionally normalize SQLite
            # uniqueness failures to PersistenceConflictError. Preserve that
            # backend-neutral behavior for MySQL callers too.
            try:
                import pymysql
                is_integrity_error = isinstance(exc, pymysql.err.IntegrityError)
            except ImportError:  # pragma: no cover
                is_integrity_error = False
            if is_integrity_error:
                raise sqlite3.IntegrityError(str(exc)) from exc
            raise
        self._columns = [str(item[0]) for item in (self._cursor.description or ())]
        return self

    def fetchone(self) -> Optional[_MySQLRow]:
        row = self._cursor.fetchone()
        return _MySQLRow(self._columns, row) if row is not None else None

    def fetchall(self) -> list[_MySQLRow]:
        return [_MySQLRow(self._columns, row) for row in self._cursor.fetchall()]


class _MySQLConnection:
    def __init__(self, connection: Any):
        self._connection = connection

    def execute(self, statement: str, params: Any = None) -> _MySQLCursor:
        import pymysql

        cursor = self._connection.cursor(pymysql.cursors.Cursor)
        return _MySQLCursor(cursor).execute(_translate_sql(statement), params)

    def executescript(self, script: str) -> None:
        # The checked-in schema contains no semicolons inside string literals.
        for statement in script.split(";"):
            statement = statement.strip()
            if not statement:
                continue
            try:
                self.execute(statement)
            except Exception as exc:
                message = str(exc).lower()
                if "already exists" not in message and "duplicate key name" not in message:
                    raise

    def begin(self) -> None:
        self._connection.begin()

    def commit(self) -> None:
        self._connection.commit()

    def rollback(self) -> None:
        self._connection.rollback()

    def close(self) -> None:
        self._connection.close()


def _mysql_schema(sql: str) -> str:
    """Convert the current SQLite DDL to valid InnoDB DDL."""
    # 191 characters keeps composite utf8mb4 indexes within InnoDB's
    # portable 3072-byte limit. Large unindexed text is promoted below.
    sql = re.sub(r"\bTEXT\b", "VARCHAR(191)", sql)
    sql = re.sub(r"\bREAL\b", "DOUBLE", sql)
    sql = re.sub(r"\bINTEGER\b", "BIGINT", sql)
    large_columns = {
        "metadata", "content", "tags", "template_values", "input_data", "output_data", "files",
        "manifest", "evaluation_report", "report", "payload", "result", "error",
    }
    for column in large_columns:
        sql = re.sub(
            rf"(\b{re.escape(column)}\s+)VARCHAR\(191\)",
            r"\1LONGTEXT", sql, flags=re.IGNORECASE,
        )
    sql = re.sub(r"\btitle\s+VARCHAR\(191\)", "title VARCHAR(255)", sql, flags=re.IGNORECASE)
    sql = re.sub(r"\bsource_ref\s+VARCHAR\(191\)", "source_ref VARCHAR(1024)", sql, flags=re.IGNORECASE)
    def unique_prefix(match: re.Match[str]) -> str:
        columns = [item.strip() for item in match.group(1).split(",")]
        return "UNIQUE (" + ", ".join(f"{column}(191)" for column in columns) + ")"
    sql = re.sub(r"UNIQUE\s*\(([^)]*)\)", unique_prefix, sql, flags=re.IGNORECASE)
    # MySQL does not permit literal defaults on LONGTEXT/BLOB columns.
    sql = re.sub(
        r"\bLONGTEXT(\s+NOT\s+NULL)?\s+DEFAULT\s+'[^']*'",
        lambda match: "LONGTEXT" + (match.group(1) or ""),
        sql,
        flags=re.IGNORECASE,
    )
    return re.sub(
        r"CREATE\s+(UNIQUE\s+)?INDEX\s+IF\s+NOT\s+EXISTS",
        r"CREATE \1INDEX", sql, flags=re.IGNORECASE,
    )


def _translate_sql(statement: str) -> str:
    """Translate the limited SQLite DML syntax used by ``AdAgentStore``."""
    statement = statement.strip()
    statement = re.sub(r"\bINSERT\s+OR\s+IGNORE\s+INTO\b", "INSERT IGNORE INTO", statement, flags=re.IGNORECASE)
    statement = re.sub(r"\bINSERT\s+OR\s+REPLACE\s+INTO\b", "REPLACE INTO", statement, flags=re.IGNORECASE)
    statement = re.sub(r"\browid\b", "message_id", statement, flags=re.IGNORECASE)
    match = re.search(
        r"ON\s+CONFLICT\s*\([^)]*\)\s+DO\s+UPDATE\s+SET\s+(.+)$",
        statement, flags=re.IGNORECASE | re.DOTALL,
    )
    if match:
        assignments = re.sub(
            r"\bexcluded\.([A-Za-z_][A-Za-z0-9_]*)\b",
            r"VALUES(\1)", match.group(1), flags=re.IGNORECASE,
        )
        statement = statement[:match.start()] + "ON DUPLICATE KEY UPDATE " + assignments
    return statement.replace("?", "%s")


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
        self._mysql_conn: Optional[_MySQLConnection] = None
        self._mysql_connect_lock = threading.RLock()
        super().__init__(database_url)

    def _connect(self) -> _MySQLConnection:
        try:
            import pymysql
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "MySQL backend requires PyMySQL; install agents/ad_agent/requirements.txt"
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
        return _MySQLConnection(pymysql.connect(**kwargs))

    def _get_conn(self) -> _MySQLConnection:
        with self._mysql_connect_lock:
            if self._mysql_conn is None:
                self._mysql_conn = self._connect()
            return self._mysql_conn

    @staticmethod
    def _table_columns(conn: _MySQLConnection, table: str) -> set[str]:
        rows = conn.execute("SHOW COLUMNS FROM `" + str(table) + "`").fetchall()
        return {str(row["Field"]) for row in rows}

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
                    self._apply_mysql_migration(conn, version)
                    conn.execute(
                        "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                        (version, datetime.now(timezone.utc).isoformat()),
                    )
            conn.commit()

    def _add_mysql_column_if_missing(
        self, conn: _MySQLConnection, table: str, column: str, definition: str,
    ) -> None:
        if column not in self._table_columns(conn, table):
            conn.execute(f"ALTER TABLE `{table}` ADD COLUMN `{column}` {definition}")

    def _apply_mysql_migration(self, conn: _MySQLConnection, version: int) -> None:
        if version == 1:
            self._add_mysql_column_if_missing(conn, "campaign_state", "account_id", "VARCHAR(255)")
        elif version == 2:
            for column in ("lease_owner", "lease_expires_at"):
                self._add_mysql_column_if_missing(conn, "workflows", column, "VARCHAR(255)")
        elif version == 3:
            for column, definition in {
                "account_id": "VARCHAR(255)", "resource_type": "VARCHAR(255)",
                "parent_resource_type": "VARCHAR(255)", "parent_sequence": "BIGINT",
                "parent_resource_id": "VARCHAR(255)", "provider_resource_id": "VARCHAR(255)",
                "logical_resource_id": "VARCHAR(255)",
            }.items():
                self._add_mysql_column_if_missing(conn, "workflow_items", column, definition)
        elif version == 5:
            for column in ("input_hash", "preview_hash", "request_hash", "contract_hash"):
                self._add_mysql_column_if_missing(conn, "approvals", column, "VARCHAR(255)")
        elif version == 7:
            self._add_mysql_column_if_missing(conn, "write_reservations", "request_hash", "VARCHAR(255)")
        elif version == 9:
            for column in ("lease_owner", "lease_expires_at"):
                self._add_mysql_column_if_missing(conn, "sessions", column, "VARCHAR(255)")
        elif version == 10:
            conn.executescript(_mysql_schema(
                """
                CREATE TABLE IF NOT EXISTS scheduled_tasks (
                    schedule_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    prompt TEXT NOT NULL,
                    cron_expression TEXT NOT NULL,
                    timezone TEXT NOT NULL DEFAULT 'Asia/Shanghai',
                    status TEXT NOT NULL DEFAULT 'active',
                    next_run_at TEXT,
                    last_run_at TEXT,
                    last_run_status TEXT,
                    last_task_id TEXT,
                    run_count INTEGER NOT NULL DEFAULT 0,
                    success_count INTEGER NOT NULL DEFAULT 0,
                    failure_count INTEGER NOT NULL DEFAULT 0,
                    payload TEXT NOT NULL DEFAULT '{}',
                    metadata TEXT NOT NULL DEFAULT '{}',
                    lease_owner TEXT,
                    lease_expires_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_scheduled_tasks_due
                    ON scheduled_tasks(status, next_run_at, lease_expires_at);
                CREATE INDEX IF NOT EXISTS idx_scheduled_tasks_scope
                    ON scheduled_tasks(tenant_id, user_id, updated_at);
                CREATE TABLE IF NOT EXISTS scheduled_task_runs (
                    schedule_run_id TEXT PRIMARY KEY,
                    schedule_id TEXT NOT NULL,
                    tenant_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    scheduled_for TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'queued',
                    task_id TEXT,
                    started_at TEXT,
                    finished_at TEXT,
                    error TEXT,
                    result TEXT,
                    created_at TEXT NOT NULL,
                    UNIQUE (schedule_id, scheduled_for),
                    FOREIGN KEY (schedule_id) REFERENCES scheduled_tasks(schedule_id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_scheduled_task_runs_scope
                    ON scheduled_task_runs(tenant_id, user_id, created_at);
                CREATE INDEX IF NOT EXISTS idx_scheduled_task_runs_status
                    ON scheduled_task_runs(status, created_at);
                """
            ))
        elif version == 11:
            self._add_mysql_column_if_missing(conn, "memories", "memory_key", "VARCHAR(191)")
            self._add_mysql_column_if_missing(conn, "memories", "superseded_by", "VARCHAR(191)")
            conn.executescript(_mysql_schema(
                """
                CREATE INDEX IF NOT EXISTS idx_memories_key
                    ON memories(tenant_id, user_id, memory_key, status, updated_at);
                """
            ))
        elif version == 12:
            conn.executescript(_mysql_schema(
                """
                CREATE TABLE IF NOT EXISTS creation_templates (
                    template_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    provider TEXT NOT NULL,
                    blueprint_id TEXT NOT NULL,
                    blueprint_version TEXT NOT NULL,
                    ad_format TEXT NOT NULL,
                    scope_type TEXT NOT NULL DEFAULT 'general',
                    account_id TEXT NOT NULL DEFAULT '',
                    region TEXT NOT NULL DEFAULT '',
                    tags TEXT NOT NULL DEFAULT '[]',
                    template_values TEXT NOT NULL DEFAULT '{}',
                    status TEXT NOT NULL DEFAULT 'active',
                    usage_count INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    last_used_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_creation_templates_scope
                    ON creation_templates(tenant_id, user_id, status, updated_at);
                CREATE INDEX IF NOT EXISTS idx_creation_templates_blueprint
                    ON creation_templates(tenant_id, user_id, blueprint_id, status);
                """
            ))
        elif version == 13:
            self._add_mysql_column_if_missing(
                conn, "creation_templates", "is_default", "BIGINT NOT NULL DEFAULT 0"
            )
            conn.executescript(_mysql_schema(
                """
                CREATE INDEX IF NOT EXISTS idx_creation_templates_default
                    ON creation_templates(tenant_id, user_id, blueprint_id, scope_type, is_default);
                """
            ))

    def claim_task(
        self, task_id: str, lease_owner: str, lease_seconds: float = 300.0,
    ) -> Optional[TaskRecord]:
        if not lease_owner or float(lease_seconds) <= 0:
            return None
        now = datetime.now(timezone.utc)
        with self._lock:
            conn = self._get_conn()
            conn.begin()
            try:
                row = conn.execute(
                    "SELECT * FROM tasks WHERE task_id = ? FOR UPDATE", (str(task_id),)
                ).fetchone()
                if not row or str(row["status"]) != "queued":
                    conn.rollback()
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
                conn.commit()
                return self._task_from_row(claimed)
            except Exception:
                conn.rollback()
                raise

    def claim_outbox_events(
        self, limit: int = 20, consumer_id: Optional[str] = None,
    ) -> list[OutboxEvent]:
        bounded_limit = max(1, min(int(limit), 100))
        owner = str(consumer_id or f"consumer:{uuid.uuid4().hex}")
        now = datetime.now(timezone.utc)
        with self._lock:
            conn = self._get_conn()
            conn.begin()
            try:
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
                    data.update({"status": "claimed", "claimed_by": owner, "claimed_at": now.isoformat()})
                    claimed.append(OutboxEvent.from_row(data))
                conn.commit()
                return claimed
            except Exception:
                conn.rollback()
                raise

    def claim_due_scheduled_tasks(
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
            conn.begin()
            try:
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
                        """UPDATE scheduled_tasks SET lease_owner = ?, lease_expires_at = ?, updated_at = ?
                           WHERE schedule_id = ?""",
                        (str(lease_owner), expires, now_value, schedule.schedule_id),
                    )
                    run_row = conn.execute(
                        "SELECT * FROM scheduled_task_runs WHERE schedule_id = ? AND scheduled_for = ? FOR UPDATE",
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
                conn.commit()
            except Exception:
                conn.rollback()
                raise
        return claimed
