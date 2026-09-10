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
import queue
import time
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
        self._rows: list[tuple[Any, ...]] = []
        self._offset = 0

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
        if self._columns:
            self._rows = list(self._cursor.fetchall())
        return self

    def fetchone(self) -> Optional[_MySQLRow]:
        row = self._rows[self._offset] if self._offset < len(self._rows) else None
        self._offset += 1
        return _MySQLRow(self._columns, row) if row is not None else None

    def fetchall(self) -> list[_MySQLRow]:
        rows = self._rows[self._offset:]
        self._offset = len(self._rows)
        return [_MySQLRow(self._columns, row) for row in rows]


class _MySQLPool:
    """Small bounded PyMySQL pool with ping-before-borrow semantics."""

    def __init__(self, connect: Any, *, pool_size: int, max_overflow: int):
        self._connect = connect
        self._capacity = max(1, int(pool_size)) + max(0, int(max_overflow))
        self._available: queue.Queue[Any] = queue.Queue(maxsize=self._capacity)
        self._created = 0
        self._condition = threading.Condition(threading.RLock())
        self._all: dict[int, Any] = {}
        self._checked_out: dict[int, Any] = {}
        self._closed = False

    def acquire(self) -> Any:
        with self._condition:
            if self._closed:
                raise RuntimeError("MySQL connection pool is closed")
            while True:
                try:
                    connection = self._available.get_nowait()
                except queue.Empty:
                    if self._created >= self._capacity:
                        # Domain operations are already serialized by the store
                        # boundary, so waiting here is preferable to opening an
                        # unbounded number of database connections.
                        if not self._condition.wait(timeout=30.0):
                            raise TimeoutError("MySQL connection pool is exhausted")
                        continue
                    connection = self._connect()
                    self._created += 1
                    self._all[id(connection)] = connection
                break
            self._checked_out[id(connection)] = connection
        try:
            connection.ping(reconnect=True)
            return connection
        except Exception:
            self.discard(connection)
            raise

    def release(self, connection: Any) -> None:
        connection_id = id(connection)
        with self._condition:
            self._checked_out.pop(connection_id, None)
            if self._closed:
                try:
                    connection.close()
                finally:
                    self._all.pop(connection_id, None)
                    self._created = max(0, self._created - 1)
                    self._condition.notify()
                return
            try:
                self._available.put_nowait(connection)
            except queue.Full:
                connection.close()
                self._all.pop(connection_id, None)
                self._created = max(0, self._created - 1)
            self._condition.notify()

    def discard(self, connection: Any) -> None:
        connection_id = id(connection)
        with self._condition:
            self._checked_out.pop(connection_id, None)
            tracked = connection_id in self._all
            try:
                connection.close()
            finally:
                if tracked:
                    self._all.pop(connection_id, None)
                    self._created = max(0, self._created - 1)
                self._condition.notify()

    def close(self) -> None:
        with self._condition:
            self._closed = True
            connections = list(self._all.values())
            self._all.clear()
            self._checked_out.clear()
            self._available = queue.Queue(maxsize=self._capacity)
            self._created = 0
            self._condition.notify_all()
        for connection in connections:
            try:
                connection.close()
            except Exception:
                pass

    def metrics(self) -> dict[str, Any]:
        with self._condition:
            return {
                "capacity": self._capacity,
                "created": self._created,
                "idle": self._available.qsize(),
                "in_use": len(self._checked_out),
                "closed": self._closed,
            }


class _MySQLConnection:
    def __init__(self, pool: _MySQLPool):
        self._pool = pool
        self._local = threading.local()

    def _transaction_connection(self) -> Any:
        return getattr(self._local, "connection", None)

    def execute(self, statement: str, params: Any = None) -> _MySQLCursor:
        import pymysql
        active = self._transaction_connection()
        connection = active or self._pool.acquire()
        borrowed = active is None
        discarded = False
        cursor = None
        try:
            cursor = connection.cursor(pymysql.cursors.Cursor)
            result = _MySQLCursor(cursor).execute(_translate_sql(statement), params)
            if borrowed:
                try:
                    connection.commit()
                except Exception:
                    self._pool.discard(connection)
                    discarded = True
                    raise
            return result
        except Exception as exc:
            if borrowed:
                try:
                    connection.rollback()
                except Exception:
                    pass
                if not discarded and isinstance(exc, getattr(pymysql.err, "OperationalError", ())):
                    self._pool.discard(connection)
                    discarded = True
            raise
        finally:
            if cursor is not None:
                cursor.close()
            if borrowed and not discarded:
                self._pool.release(connection)

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
        if self._transaction_connection() is not None:
            raise RuntimeError("nested MySQL transactions are not supported")
        connection = self._pool.acquire()
        try:
            connection.begin()
        except Exception:
            self._pool.discard(connection)
            raise
        self._local.connection = connection

    def commit(self) -> None:
        connection = self._transaction_connection()
        if connection is None:
            return
        try:
            connection.commit()
        except Exception:
            self._pool.discard(connection)
            raise
        finally:
            self._local.connection = None
        self._pool.release(connection)

    def rollback(self) -> None:
        connection = self._transaction_connection()
        if connection is None:
            return
        try:
            connection.rollback()
        except Exception:
            self._pool.discard(connection)
            raise
        finally:
            self._local.connection = None
        self._pool.release(connection)

    def close(self) -> None:
        self._pool.close()


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
        # External MCP schemas and validation reports are bounded by the
        # control-plane contract, not by the 191-char index-safe fallback.
        "input_schema", "annotations", "validation_report", "description", "last_error",
        "intent_types", "intent_aliases", "skill_refs", "required_permissions", "traits",
    }
    for column in large_columns:
        sql = re.sub(
            rf"(\b{re.escape(column)}\s+)VARCHAR\(191\)",
            r"\1LONGTEXT", sql, flags=re.IGNORECASE,
        )
    sql = re.sub(r"\btitle\s+VARCHAR\(191\)", "title VARCHAR(255)", sql, flags=re.IGNORECASE)
    sql = re.sub(r"\bsource_ref\s+VARCHAR\(191\)", "source_ref VARCHAR(1024)", sql, flags=re.IGNORECASE)
    sql = re.sub(r"\bendpoint\s+VARCHAR\(191\)", "endpoint VARCHAR(2048)", sql, flags=re.IGNORECASE)
    # Index prefixes are valid for character columns, not numeric columns.
    # In particular execution_event_repairs has UNIQUE(run_id, seq); blindly
    # appending ``(191)`` to ``seq`` makes the generated MySQL DDL invalid.
    prefixable = {
        "run_id", "tenant_id", "skill_name", "version", "plugin_id", "idempotency_key",
        "schedule_id", "scheduled_for",
    }

    def unique_prefix(match: re.Match[str]) -> str:
        columns = [item.strip() for item in match.group(1).split(",")]
        rendered = []
        for column in columns:
            bare = column.strip("`")
            rendered.append(f"{column}(191)" if bare in prefixable else column)
        return "UNIQUE (" + ", ".join(rendered) + ")"
    sql = re.sub(r"UNIQUE\s*\(([^)]*)\)", unique_prefix, sql, flags=re.IGNORECASE)
    # MySQL does not permit literal defaults on LONGTEXT/BLOB columns.
    sql = re.sub(
        r"\bLONGTEXT(\s+NOT\s+NULL)?\s+DEFAULT\s+'[^']*'",
        lambda match: "LONGTEXT" + (match.group(1) or ""),
        sql,
        flags=re.IGNORECASE,
    )
    sql = re.sub(
        r"CREATE\s+(UNIQUE\s+)?INDEX\s+IF\s+NOT\s+EXISTS",
        r"CREATE \1INDEX", sql, flags=re.IGNORECASE,
    )

    def force_innodb(match: re.Match[str]) -> str:
        statement = match.group(0)
        if re.search(r"\bENGINE\s*=", statement, flags=re.IGNORECASE):
            return statement
        return statement[:-1] + " ENGINE=InnoDB;"

    # Locking/foreign-key semantics are part of this backend contract. Do not
    # silently depend on a server's default storage engine.
    return re.sub(
        r"CREATE\s+TABLE\b.*?;", force_innodb, sql,
        flags=re.IGNORECASE | re.DOTALL,
    )


def _translate_sql(statement: str) -> str:
    """Translate the limited SQLite DML syntax used by ``AdAgentStore``."""
    statement = statement.strip()
    # SQLite uses BEGIN IMMEDIATE for the scheduler's claim transaction;
    # MySQL's equivalent is a normal transaction whose SELECT ... FOR UPDATE
    # statements acquire the row locks.
    statement = re.sub(r"^BEGIN\s+IMMEDIATE$", "BEGIN", statement, flags=re.IGNORECASE)
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


def _is_retryable_transaction_error(error: BaseException) -> bool:
    """Return whether MySQL aborted a transaction that is safe to retry."""
    code = None
    args = getattr(error, "args", ())
    if args:
        try:
            code = int(args[0])
        except (TypeError, ValueError):
            code = None
    # ER_LOCK_DEADLOCK and ER_LOCK_WAIT_TIMEOUT. Connection failures are not
    # retried here: the pool discards those connections and the caller can
    # apply its own request-level retry policy without duplicating mutations.
    return code in {1205, 1213}


def _retry_transaction(operation: Any, *, attempts: int = 3) -> Any:
    """Retry a complete claim transaction, never an individual SQL statement."""
    for attempt in range(max(1, int(attempts))):
        try:
            return operation()
        except Exception as exc:
            if attempt + 1 >= max(1, int(attempts)) or not _is_retryable_transaction_error(exc):
                raise
            time.sleep(min(0.25, 0.05 * (2 ** attempt)))
    raise AssertionError("unreachable")


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
        except Exception as exc:
            return {
                "backend": self.backend_name,
                "status": "unhealthy",
                "error": type(exc).__name__,
                "pool": self._pool.metrics(),
            }

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
        elif version == 14:
            conn.executescript(_mysql_schema(
                """
                CREATE TABLE IF NOT EXISTS worker_instances (
                    worker_id TEXT PRIMARY KEY,
                    worker_kind TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'running',
                    started_at TEXT NOT NULL,
                    last_heartbeat_at TEXT NOT NULL,
                    lease_expires_at TEXT,
                    metadata TEXT NOT NULL DEFAULT '{}'
                );
                CREATE INDEX IF NOT EXISTS idx_worker_instances_heartbeat
                    ON worker_instances(status, last_heartbeat_at);
                """
            ))
        elif version == 15:
            conn.executescript(_mysql_schema(
                """
                CREATE TABLE IF NOT EXISTS execution_event_repairs (
                    repair_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    seq INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    attempts INTEGER NOT NULL DEFAULT 0,
                    next_attempt_at TEXT,
                    created_at TEXT NOT NULL,
                    last_error TEXT,
                    UNIQUE (run_id, seq)
                );
                CREATE INDEX IF NOT EXISTS idx_execution_event_repairs_due
                    ON execution_event_repairs(status, next_attempt_at, created_at);
                """
            ))
        elif version == 16:
            self._add_mysql_column_if_missing(
                conn, "sessions", "tenant_id", "VARCHAR(255) NOT NULL DEFAULT 'default'"
            )
            self._add_mysql_column_if_missing(
                conn, "workflows", "tenant_id", "VARCHAR(255) NOT NULL DEFAULT 'default'"
            )
            conn.executescript(_mysql_schema(
                """
                CREATE INDEX IF NOT EXISTS idx_sessions_tenant
                    ON sessions(tenant_id, user_id, updated_at);
                CREATE INDEX IF NOT EXISTS idx_workflows_tenant
                    ON workflows(tenant_id, status, updated_at);
                """
            ))
            # Preserve a tenant marker already present in legacy metadata when
            # possible. Records without one intentionally stay in default and
            # require explicit deployment-level association.
            for table, key in (("sessions", "session_id"), ("workflows", "workflow_id")):
                for row in conn.execute(
                    f"SELECT {key}, metadata FROM `{table}` WHERE tenant_id = ?",
                    ("default",),
                ).fetchall():
                    try:
                        import json
                        metadata = json.loads(row["metadata"] or "{}") or {}
                    except (TypeError, ValueError):
                        metadata = {}
                    tenant_id = str(metadata.get("tenant_id") or "").strip()
                    if tenant_id and tenant_id != "default":
                        conn.execute(
                            f"UPDATE `{table}` SET tenant_id = ? WHERE `{key}` = ?",
                            (tenant_id, str(row[key])),
                        )
        elif version == 17:
            # The current bootstrap DDL creates these tables before the
            # version loop. Keep the migration explicit so an older MySQL
            # database records the MCP control-plane contract as well.
            conn.executescript(_mysql_schema(
                """
                CREATE INDEX IF NOT EXISTS idx_mcp_servers_scope
                    ON mcp_servers(tenant_id, status, updated_at);
                CREATE INDEX IF NOT EXISTS idx_mcp_tools_server
                    ON mcp_tools(tenant_id, server_id, status, updated_at);
                """
            ))
        elif version == 18:
            for column, definition in {
                "intent_types": "LONGTEXT NOT NULL",
                "intent_aliases": "LONGTEXT NOT NULL",
                "skill_refs": "LONGTEXT NOT NULL",
                "action": "VARCHAR(64) NOT NULL DEFAULT 'invoke'",
                "resource_type": "VARCHAR(191) NOT NULL DEFAULT 'mcp_invocation'",
                "resource_id_field": "VARCHAR(191)",
                "readback_tool": "VARCHAR(255)",
                "idempotency_key_field": "VARCHAR(191)",
                "required_permissions": "LONGTEXT NOT NULL",
                "traits": "LONGTEXT NOT NULL",
            }.items():
                self._add_mysql_column_if_missing(conn, "mcp_tools", column, definition)

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
