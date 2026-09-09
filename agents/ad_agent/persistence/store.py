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
import math
import re
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, List

from .models import (
    CampaignRecord, ConversationMessageRecord, KnowledgeDocumentRecord,
    ExecutionRunRecord, TaskRecord, ToolCallRecord,
    OutboxEvent, ScheduledTaskRecord, ScheduledTaskRunRecord,
    CreationTemplateRecord,
)
from .errors import PersistenceConflictError
from ..core.memory import MemoryRecord

logger = logging.getLogger(__name__)


WORKFLOW_TRANSITIONS = {
    "planned": {"planned", "running", "awaiting_confirmation", "blocked", "failed", "cancelled"},
    "running": {"running", "planned", "awaiting_confirmation", "blocked", "failed", "succeeded", "partially_failed", "recovery_required", "cancelled"},
    "awaiting_confirmation": {"awaiting_confirmation", "running", "blocked", "failed", "cancelled"},
    "partially_failed": {"partially_failed", "recovery_required", "succeeded", "failed", "cancelled"},
    "recovery_required": {"recovery_required", "running", "succeeded", "failed", "cancelled"},
    "blocked": {"blocked", "running", "failed", "recovery_required", "succeeded", "cancelled"},
    "failed": {"failed", "running", "recovery_required", "succeeded", "cancelled"},
    "succeeded": {"succeeded"},
    "cancelled": {"cancelled"},
}

WORKFLOW_ITEM_TRANSITIONS = {
    "planned": {"planned", "awaiting_confirmation", "running", "succeeded", "failed", "unknown", "skipped"},
    "running": {"running", "awaiting_confirmation", "succeeded", "failed", "unknown", "skipped"},
    "awaiting_confirmation": {"awaiting_confirmation", "succeeded", "failed", "unknown"},
    "failed": {"failed", "succeeded", "unknown"},
    "unknown": {"unknown", "succeeded", "failed"},
    "succeeded": {"succeeded"},
    "unsupported": {"unsupported"},
    "skipped": {"skipped"},
}

TASK_TRANSITIONS = {
    "queued": {"queued", "running", "paused", "cancelled", "failed"},
    "running": {"running", "succeeded", "failed", "cancelling", "cancelled", "recovery_required"},
    "paused": {"paused", "queued", "cancelling", "cancelled"},
    "cancelling": {"cancelling", "cancelled", "failed", "recovery_required"},
    "recovery_required": {"recovery_required", "queued", "cancelled"},
    "succeeded": {"succeeded"},
    "failed": {"failed"},
    "cancelled": {"cancelled"},
}


class AdAgentStore:
    """
    Unified persistence layer (SQLite).
    
    Thread-safe: each connection is independent, read/write operations are locked.
    """
    
    # Schema changes are tracked explicitly even while SQLite remains the
    # current single-process backend. This keeps the PersistenceBackend
    # boundary stable and gives a future MySQL/PostgreSQL adapter a concrete
    # migration contract instead of relying on scattered PRAGMA checks.
    SCHEMA_VERSION = 16

    SCHEMA = """
    CREATE TABLE IF NOT EXISTS schema_migrations (
        version INTEGER PRIMARY KEY,
        applied_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS sessions (
        session_id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        tenant_id TEXT NOT NULL DEFAULT 'default',
        account_id TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        metadata TEXT DEFAULT '{}',
        lease_owner TEXT,
        lease_expires_at TEXT
    );

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

    CREATE TABLE IF NOT EXISTS conversation_messages (
        message_id TEXT PRIMARY KEY,
        session_id TEXT NOT NULL,
        turn_id TEXT NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS knowledge_documents (
        document_id TEXT PRIMARY KEY,
        tenant_id TEXT NOT NULL,
        title TEXT NOT NULL,
        content TEXT NOT NULL,
        platform TEXT NOT NULL DEFAULT 'all',
        layer TEXT NOT NULL DEFAULT 'business',
        knowledge_type TEXT NOT NULL DEFAULT 'general',
        source TEXT NOT NULL DEFAULT 'user',
        source_ref TEXT NOT NULL,
        version TEXT NOT NULL,
        confidence REAL NOT NULL DEFAULT 0.8,
        tags TEXT NOT NULL DEFAULT '[]',
        status TEXT NOT NULL DEFAULT 'draft',
        created_by TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        published_at TEXT
    );

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
        is_default INTEGER NOT NULL DEFAULT 0,
        usage_count INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        last_used_at TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_creation_templates_scope
        ON creation_templates(tenant_id, user_id, status, updated_at DESC);
    CREATE INDEX IF NOT EXISTS idx_creation_templates_blueprint
        ON creation_templates(tenant_id, user_id, blueprint_id, status);

    CREATE TABLE IF NOT EXISTS memories (
        memory_id TEXT PRIMARY KEY,
        tenant_id TEXT NOT NULL,
        user_id TEXT NOT NULL,
        session_id TEXT,
        kind TEXT NOT NULL,
        content TEXT NOT NULL,
        source TEXT NOT NULL,
        tags TEXT DEFAULT '[]',
        importance REAL NOT NULL DEFAULT 0.5,
        confidence REAL NOT NULL DEFAULT 1.0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        expires_at TEXT,
        status TEXT NOT NULL DEFAULT 'active',
        memory_key TEXT,
        superseded_by TEXT
    );
    
    CREATE TABLE IF NOT EXISTS tool_calls (
        id TEXT PRIMARY KEY,
        session_id TEXT NOT NULL,
        turn_id TEXT NOT NULL,
        tool_name TEXT NOT NULL,
        platform TEXT NOT NULL,
        input_data TEXT NOT NULL,
        output_data TEXT,
        success INTEGER NOT NULL DEFAULT 1,
        error TEXT,
        started_at TEXT NOT NULL,
        ended_at TEXT,
        FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
    );
    
    CREATE TABLE IF NOT EXISTS campaign_state (
        id TEXT PRIMARY KEY,
        platform TEXT NOT NULL,
        campaign_id TEXT NOT NULL,
        name TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'DRAFT',
        objective TEXT,
        budget_daily REAL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        metadata TEXT DEFAULT '{}',
        account_id TEXT
    );
    
    CREATE INDEX IF NOT EXISTS idx_tool_calls_session ON tool_calls(session_id);
    CREATE INDEX IF NOT EXISTS idx_tool_calls_turn ON tool_calls(session_id, turn_id);
    CREATE INDEX IF NOT EXISTS idx_conversation_messages_session
        ON conversation_messages(session_id, created_at);
    CREATE INDEX IF NOT EXISTS idx_knowledge_documents_scope
        ON knowledge_documents(tenant_id, status, updated_at DESC);
    CREATE UNIQUE INDEX IF NOT EXISTS uq_knowledge_documents_version
        ON knowledge_documents(tenant_id, title, version);
    CREATE INDEX IF NOT EXISTS idx_campaigns_platform ON campaign_state(platform, campaign_id);
    CREATE INDEX IF NOT EXISTS idx_campaigns_name ON campaign_state(name);
    CREATE INDEX IF NOT EXISTS idx_memories_scope
        ON memories(tenant_id, user_id, status, updated_at DESC);
    CREATE INDEX IF NOT EXISTS idx_memories_session
        ON memories(tenant_id, user_id, session_id, status);

    CREATE TABLE IF NOT EXISTS workflows (
        workflow_id TEXT PRIMARY KEY,
        session_id TEXT NOT NULL,
        tenant_id TEXT NOT NULL DEFAULT 'default',
        intent_type TEXT NOT NULL,
        execution_mode TEXT NOT NULL,
        status TEXT NOT NULL,
        metadata TEXT DEFAULT '{}',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        lease_owner TEXT,
        lease_expires_at TEXT,
        FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS workflow_items (
        item_id TEXT PRIMARY KEY,
        workflow_id TEXT NOT NULL,
        sequence INTEGER NOT NULL,
        platform TEXT NOT NULL,
        account_id TEXT,
        tool_name TEXT NOT NULL,
        status TEXT NOT NULL,
        input_data TEXT NOT NULL,
        output_data TEXT,
        error TEXT,
        compensation_required INTEGER NOT NULL DEFAULT 0,
        resource_type TEXT,
        parent_resource_type TEXT,
        parent_sequence INTEGER,
        parent_resource_id TEXT,
        provider_resource_id TEXT,
        logical_resource_id TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (workflow_id) REFERENCES workflows(workflow_id) ON DELETE CASCADE
    );

    CREATE INDEX IF NOT EXISTS idx_workflow_items_workflow ON workflow_items(workflow_id, sequence);
    CREATE INDEX IF NOT EXISTS idx_sessions_tenant ON sessions(tenant_id, user_id, updated_at DESC);
    CREATE INDEX IF NOT EXISTS idx_workflows_tenant ON workflows(tenant_id, status, updated_at DESC);

    CREATE TABLE IF NOT EXISTS skill_versions (
        version_id TEXT PRIMARY KEY,
        tenant_id TEXT NOT NULL,
        skill_name TEXT NOT NULL,
        version TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'draft',
        files TEXT NOT NULL,
        sha256 TEXT NOT NULL,
        created_by TEXT NOT NULL,
        created_at TEXT NOT NULL,
        published_at TEXT,
        evaluation_status TEXT NOT NULL DEFAULT 'not_run',
        evaluation_run_id TEXT,
        evaluation_report TEXT DEFAULT '{}',
        UNIQUE (tenant_id, skill_name, version)
    );

    CREATE TABLE IF NOT EXISTS skill_releases (
        tenant_id TEXT NOT NULL,
        skill_name TEXT NOT NULL,
        version_id TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        PRIMARY KEY (tenant_id, skill_name),
        FOREIGN KEY (version_id) REFERENCES skill_versions(version_id)
    );
    CREATE INDEX IF NOT EXISTS idx_skill_versions_name
        ON skill_versions(tenant_id, skill_name, created_at DESC);

    CREATE TABLE IF NOT EXISTS skill_evaluation_runs (
        run_id TEXT PRIMARY KEY,
        version_id TEXT NOT NULL,
        tenant_id TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'queued',
        report TEXT DEFAULT '{}',
        error TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (version_id) REFERENCES skill_versions(version_id)
    );
    CREATE INDEX IF NOT EXISTS idx_skill_evaluation_runs_tenant
        ON skill_evaluation_runs(tenant_id, created_at DESC);

    CREATE TABLE IF NOT EXISTS plugin_packages (
        package_id TEXT PRIMARY KEY,
        tenant_id TEXT NOT NULL,
        plugin_id TEXT NOT NULL,
        version TEXT NOT NULL,
        manifest TEXT NOT NULL,
        files TEXT NOT NULL,
        package_digest TEXT NOT NULL,
        signature_verified INTEGER NOT NULL DEFAULT 0,
        status TEXT NOT NULL DEFAULT 'validated',
        created_by TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        activated_at TEXT,
        last_error TEXT,
        UNIQUE (tenant_id, plugin_id, version)
    );

    CREATE TABLE IF NOT EXISTS plugin_releases (
        tenant_id TEXT NOT NULL,
        plugin_id TEXT NOT NULL,
        package_id TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        PRIMARY KEY (tenant_id, plugin_id),
        FOREIGN KEY (package_id) REFERENCES plugin_packages(package_id)
    );
    CREATE INDEX IF NOT EXISTS idx_plugin_packages_tenant
        ON plugin_packages(tenant_id, plugin_id, created_at DESC);

    CREATE TABLE IF NOT EXISTS write_reservations (
        idempotency_key TEXT PRIMARY KEY,
        request_hash TEXT,
        status TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS tasks (
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
        metadata TEXT DEFAULT '{}',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        started_at TEXT,
        finished_at TEXT,
        lease_owner TEXT,
        lease_expires_at TEXT,
        UNIQUE (tenant_id, user_id, idempotency_key)
    );
    CREATE INDEX IF NOT EXISTS idx_tasks_scope ON tasks(tenant_id, user_id, updated_at DESC);
    CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status, updated_at ASC);

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
        ON scheduled_tasks(tenant_id, user_id, updated_at DESC);

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
        ON scheduled_task_runs(tenant_id, user_id, created_at DESC);
    CREATE INDEX IF NOT EXISTS idx_scheduled_task_runs_status
        ON scheduled_task_runs(status, created_at ASC);

    CREATE TABLE IF NOT EXISTS execution_runs (
        run_id TEXT PRIMARY KEY,
        session_id TEXT NOT NULL,
        turn_id TEXT NOT NULL,
        user_id TEXT NOT NULL,
        tenant_id TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'running',
        execution_mode TEXT NOT NULL DEFAULT 'dry_run',
        workflow_id TEXT,
        task_id TEXT,
        metadata TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        finished_at TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_execution_runs_session
        ON execution_runs(tenant_id, user_id, session_id, created_at DESC);
    CREATE INDEX IF NOT EXISTS idx_execution_runs_status
        ON execution_runs(status, updated_at ASC);

    CREATE TABLE IF NOT EXISTS execution_run_events (
        run_id TEXT NOT NULL,
        seq INTEGER NOT NULL,
        event_type TEXT NOT NULL,
        payload TEXT NOT NULL,
        created_at TEXT NOT NULL,
        PRIMARY KEY (run_id, seq),
        FOREIGN KEY (run_id) REFERENCES execution_runs(run_id) ON DELETE CASCADE
    );
    CREATE INDEX IF NOT EXISTS idx_execution_run_events_created
        ON execution_run_events(run_id, seq ASC);

    CREATE TABLE IF NOT EXISTS approvals (
        plan_fingerprint TEXT PRIMARY KEY,
        token_hash TEXT NOT NULL,
        session_id TEXT NOT NULL,
        user_id TEXT NOT NULL,
        account_id TEXT NOT NULL,
        tool_name TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        created_at TEXT NOT NULL,
        consumed_at TEXT,
        input_hash TEXT,
        preview_hash TEXT,
        request_hash TEXT,
        contract_hash TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_approvals_session ON approvals(session_id, status);

    CREATE TABLE IF NOT EXISTS outbox_events (
        event_id TEXT PRIMARY KEY,
        run_id TEXT NOT NULL,
        event_type TEXT NOT NULL,
        payload TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        retry_count INTEGER NOT NULL DEFAULT 0,
        next_retry_at TEXT,
        created_at TEXT NOT NULL,
        claimed_by TEXT,
        claimed_at TEXT,
        last_error TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_outbox_pending
        ON outbox_events(status, next_retry_at, created_at);

    CREATE TABLE IF NOT EXISTS execution_mode_preferences (
        tenant_id TEXT NOT NULL,
        user_id TEXT NOT NULL,
        mode TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        PRIMARY KEY (tenant_id, user_id)
    );
    CREATE INDEX IF NOT EXISTS idx_execution_mode_preferences_updated
        ON execution_mode_preferences(updated_at DESC);
    """
    
    def __init__(self, db_path: str = ":memory:"):
        self._db_path = db_path
        self._lock = threading.RLock()
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()
    
    def _get_conn(self) -> sqlite3.Connection:
        """Get thread-safe database connection (single connection mode)"""
        if self._conn is None:
            self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
        return self._conn
    
    def _init_db(self):
        """Initialize the latest schema and apply versioned migrations."""
        with self._lock:
            conn = self._get_conn()
            conn.executescript(self.SCHEMA)
            applied = {
                int(row[0])
                for row in conn.execute("SELECT version FROM schema_migrations")
            }
            for version in range(1, self.SCHEMA_VERSION + 1):
                if version in applied:
                    continue
                self._apply_migration(conn, version)
                conn.execute(
                    "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                    (version, datetime.now(timezone.utc).isoformat()),
                )
            conn.commit()

    @staticmethod
    def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
        """Read legacy columns through a single migration-only helper."""
        return {str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})")}

    @classmethod
    def _add_column_if_missing(
        cls, conn: sqlite3.Connection, table: str, column: str, definition: str,
    ) -> None:
        if column not in cls._table_columns(conn, table):
            # Names and definitions are class-owned constants, never user input.
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    @classmethod
    def _apply_migration(cls, conn: sqlite3.Connection, version: int) -> None:
        """Apply one idempotent compatibility migration.

        The latest ``SCHEMA`` creates these columns for new databases. The
        guarded ALTERs exist only for databases created by earlier revisions.
        """
        if version == 1:
            cls._add_column_if_missing(conn, "campaign_state", "account_id", "TEXT")
        elif version == 2:
            cls._add_column_if_missing(conn, "workflows", "lease_owner", "TEXT")
            cls._add_column_if_missing(conn, "workflows", "lease_expires_at", "TEXT")
        elif version == 3:
            for column, definition in {
                "account_id": "TEXT",
                "resource_type": "TEXT",
                "parent_resource_type": "TEXT",
                "parent_sequence": "INTEGER",
                "parent_resource_id": "TEXT",
                "provider_resource_id": "TEXT",
                "logical_resource_id": "TEXT",
            }.items():
                cls._add_column_if_missing(conn, "workflow_items", column, definition)
        elif version == 4:
            # The table is created by the latest schema above. Keeping this
            # migration explicit makes the schema history complete for old
            # databases and leaves room for backend-specific migrations.
            conn.execute(
                """CREATE TABLE IF NOT EXISTS execution_mode_preferences (
                    tenant_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, user_id)
                )"""
            )
        elif version == 5:
            for column, definition in {
                "input_hash": "TEXT",
                "preview_hash": "TEXT",
                "request_hash": "TEXT",
                "contract_hash": "TEXT",
            }.items():
                cls._add_column_if_missing(conn, "approvals", column, definition)
        elif version == 6:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS outbox_events (
                    event_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    retry_count INTEGER NOT NULL DEFAULT 0,
                    next_retry_at TEXT,
                    created_at TEXT NOT NULL,
                    claimed_by TEXT,
                    claimed_at TEXT,
                    last_error TEXT
                )"""
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_outbox_pending "
                "ON outbox_events(status, next_retry_at, created_at)"
            )
        elif version == 7:
            cls._add_column_if_missing(
                conn, "write_reservations", "request_hash", "TEXT"
            )
        elif version == 8:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS execution_runs (
                    run_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    turn_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    tenant_id TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'running',
                    execution_mode TEXT NOT NULL DEFAULT 'dry_run',
                    workflow_id TEXT,
                    task_id TEXT,
                    metadata TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    finished_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_execution_runs_session
                    ON execution_runs(tenant_id, user_id, session_id, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_execution_runs_status
                    ON execution_runs(status, updated_at ASC);
                CREATE TABLE IF NOT EXISTS execution_run_events (
                    run_id TEXT NOT NULL,
                    seq INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (run_id, seq),
                    FOREIGN KEY (run_id) REFERENCES execution_runs(run_id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_execution_run_events_created
                    ON execution_run_events(run_id, seq ASC);
                """
            )
        elif version == 9:
            cls._add_column_if_missing(conn, "sessions", "lease_owner", "TEXT")
            cls._add_column_if_missing(conn, "sessions", "lease_expires_at", "TEXT")
        elif version == 10:
            conn.executescript(
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
                    ON scheduled_tasks(tenant_id, user_id, updated_at DESC);
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
                    ON scheduled_task_runs(tenant_id, user_id, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_scheduled_task_runs_status
                    ON scheduled_task_runs(status, created_at ASC);
                """
            )
        elif version == 11:
            cls._add_column_if_missing(conn, "memories", "memory_key", "TEXT")
            cls._add_column_if_missing(conn, "memories", "superseded_by", "TEXT")
        elif version == 12:
            conn.executescript(
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
                    ON creation_templates(tenant_id, user_id, status, updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_creation_templates_blueprint
                    ON creation_templates(tenant_id, user_id, blueprint_id, status);
                """
            )
        elif version == 13:
            cls._add_column_if_missing(conn, "creation_templates", "is_default", "INTEGER NOT NULL DEFAULT 0")
            conn.execute(
                """CREATE INDEX IF NOT EXISTS idx_creation_templates_default
                   ON creation_templates(tenant_id, user_id, blueprint_id, scope_type, is_default)"""
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_memories_key "
                "ON memories(tenant_id, user_id, memory_key, status, updated_at DESC)"
            )
        elif version == 14:
            conn.executescript(
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
            )
        elif version == 15:
            conn.executescript(
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
            )
        elif version == 16:
            cls._add_column_if_missing(conn, "sessions", "tenant_id", "TEXT NOT NULL DEFAULT 'default'")
            cls._add_column_if_missing(conn, "workflows", "tenant_id", "TEXT NOT NULL DEFAULT 'default'")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_sessions_tenant "
                "ON sessions(tenant_id, user_id, updated_at DESC)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_workflows_tenant "
                "ON workflows(tenant_id, status, updated_at DESC)"
            )
            # Prefer an already-persisted trusted tenant marker when upgrading
            # an older database. Rows without one remain in the explicit
            # default tenant and must be re-associated by deployment policy.
            for table in ("sessions", "workflows"):
                key = "session_id" if table == "sessions" else "workflow_id"
                for row in conn.execute(
                    f"SELECT {key}, metadata FROM {table} WHERE tenant_id = 'default'"
                ).fetchall():
                    try:
                        metadata = json.loads(row["metadata"] or "{}") or {}
                    except (TypeError, ValueError):
                        metadata = {}
                    tenant_id = str(metadata.get("tenant_id") or "").strip()
                    if tenant_id and tenant_id != "default":
                        conn.execute(
                            f"UPDATE {table} SET tenant_id = ? WHERE {key} = ?",
                            (tenant_id, str(row[key])),
                        )
        else:
            raise ValueError(f"Unsupported schema migration: {version}")
    
    def close(self):
        """Close database connection"""
        with self._lock:
            if self._conn:
                self._conn.close()
                self._conn = None

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
            self._get_conn().commit()

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
                + (" AND s.user_id = ?" if user_id is not None else "")
                + " ORDER BY tc.started_at DESC LIMIT 2000",
                [tool_cutoff] + ([str(user_id)] if user_id is not None else []),
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
            terminal = status in {"succeeded", "failed", "cancelled", "recovery_required"}
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

    def pause_task(self, task_id: str) -> Optional[TaskRecord]:
        with self._lock:
            conn = self._get_conn()
            now = datetime.now().isoformat()
            cursor = conn.execute(
                "UPDATE tasks SET status = 'paused', updated_at = ? "
                "WHERE task_id = ? AND status = 'queued'",
                (now, str(task_id)),
            )
            conn.commit()
            return self._task_from_row(
                conn.execute("SELECT * FROM tasks WHERE task_id = ?", (str(task_id),)).fetchone()
            ) if cursor.rowcount else self.get_task(str(task_id))

    def resume_task(self, task_id: str) -> Optional[TaskRecord]:
        with self._lock:
            conn = self._get_conn()
            now = datetime.now().isoformat()
            cursor = conn.execute(
                "UPDATE tasks SET status = 'queued', updated_at = ?, error = NULL "
                "WHERE task_id = ? AND status = 'paused'",
                (now, str(task_id)),
            )
            conn.commit()
            return self._task_from_row(
                conn.execute("SELECT * FROM tasks WHERE task_id = ?", (str(task_id),)).fetchone()
            ) if cursor.rowcount else self.get_task(str(task_id))

    def cancel_task(self, task_id: str) -> Optional[TaskRecord]:
        with self._lock:
            conn = self._get_conn()
            row = conn.execute(
                "SELECT status, metadata FROM tasks WHERE task_id = ?", (str(task_id),)
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
            conn.execute(
                "UPDATE tasks SET status = ?, metadata = ?, updated_at = ?" + finished
                + " WHERE task_id = ?", values,
            )
            conn.commit()
            return self._task_from_row(
                conn.execute("SELECT * FROM tasks WHERE task_id = ?", (str(task_id),)).fetchone()
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
            row = conn.execute(
                "SELECT metadata FROM tasks WHERE task_id = ? AND status = 'recovery_required'",
                (str(task_id),),
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
                (now, json.dumps(metadata, ensure_ascii=False, sort_keys=True), str(task_id)),
            )
            conn.commit()
            if cursor.rowcount != 1:
                return None
            return self._task_from_row(
                conn.execute("SELECT * FROM tasks WHERE task_id = ?", (str(task_id),)).fetchone()
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
        metadata: Optional[dict] = None,
    ) -> bool:
        assignments = ["updated_at = ?"]
        values: list[Any] = [datetime.now(timezone.utc).isoformat()]
        for column, value in (
            ("status", status), ("next_run_at", next_run_at),
            ("last_run_at", last_run_at), ("last_run_status", last_run_status),
            ("last_task_id", last_task_id),
        ):
            if value is not None:
                assignments.append(f"{column} = ?"); values.append(value)
        if metadata is not None:
            assignments.append("metadata = ?"); values.append(json.dumps(metadata or {}, ensure_ascii=False))
        values.append(str(schedule_id))
        with self._lock:
            cursor = self._get_conn().execute(
                "UPDATE scheduled_tasks SET " + ", ".join(assignments)
                + " WHERE schedule_id = ?", values,
            )
            self._get_conn().commit()
            return cursor.rowcount > 0

    def advance_scheduled_task(
        self, schedule_id: str, expected_next_run_at: str, next_run_at: str,
    ) -> bool:
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute(
                """UPDATE scheduled_tasks SET next_run_at = ?, lease_owner = NULL,
                   lease_expires_at = NULL, updated_at = ?
                   WHERE schedule_id = ? AND next_run_at = ?""",
                (next_run_at, datetime.now(timezone.utc).isoformat(), str(schedule_id), expected_next_run_at),
            )
            conn.commit()
            return cursor.rowcount > 0

    def pause_scheduled_task(self, schedule_id: str) -> Optional[ScheduledTaskRecord]:
        self.update_scheduled_task(schedule_id, status="paused")
        with self._lock:
            return self._scheduled_from_row(self._get_conn().execute(
                "SELECT * FROM scheduled_tasks WHERE schedule_id = ?", (str(schedule_id),)
            ).fetchone())

    def resume_scheduled_task(self, schedule_id: str, next_run_at: str) -> Optional[ScheduledTaskRecord]:
        self.update_scheduled_task(schedule_id, status="active", next_run_at=next_run_at)
        with self._lock:
            return self._scheduled_from_row(self._get_conn().execute(
                "SELECT * FROM scheduled_tasks WHERE schedule_id = ?", (str(schedule_id),)
            ).fetchone())

    def delete_scheduled_task(self, schedule_id: str) -> bool:
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute("DELETE FROM scheduled_tasks WHERE schedule_id = ?", (str(schedule_id),))
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

    def attach_scheduled_task_run(self, schedule_run_id: str, task_id: str, status: str = "queued") -> bool:
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute(
                "UPDATE scheduled_task_runs SET task_id = ?, status = ?, started_at = ?, error = NULL "
                "WHERE schedule_run_id = ? AND status IN ('queued', 'running')",
                (str(task_id), str(status), datetime.now(timezone.utc).isoformat(), str(schedule_run_id)),
            )
            conn.commit()
            return cursor.rowcount > 0

    def update_scheduled_task_run(
        self, schedule_run_id: str, status: str, *, task_id: Optional[str] = None,
        started_at: Optional[str] = None, finished_at: Optional[str] = None,
        error: Optional[str] = None, result: Optional[dict] = None,
    ) -> bool:
        status = str(status)
        with self._lock:
            conn = self._get_conn()
            row = conn.execute("SELECT * FROM scheduled_task_runs WHERE schedule_run_id = ?", (str(schedule_run_id),)).fetchone()
            if not row:
                return False
            current = str(row["status"])
            if current in {"succeeded", "failed", "cancelled"} and status != current:
                return False
            assignments = ["status = ?"]
            values: list[Any] = [status]
            for column, value in (("task_id", task_id), ("started_at", started_at), ("finished_at", finished_at), ("error", error)):
                if value is not None:
                    assignments.append(f"{column} = ?"); values.append(value)
            if result is not None:
                assignments.append("result = ?"); values.append(json.dumps(result, ensure_ascii=False))
            values.append(str(schedule_run_id))
            conn.execute("UPDATE scheduled_task_runs SET " + ", ".join(assignments) + " WHERE schedule_run_id = ?", values)
            if status in {"succeeded", "failed", "cancelled"} and current not in {"succeeded", "failed", "cancelled"}:
                schedule_id = str(row["schedule_id"])
                conn.execute(
                    """UPDATE scheduled_tasks SET run_count = run_count + 1,
                       success_count = success_count + ?, failure_count = failure_count + ?,
                       last_run_at = ?, last_run_status = ?, last_task_id = COALESCE(?, last_task_id),
                       lease_owner = NULL, lease_expires_at = NULL, updated_at = ?
                       WHERE schedule_id = ?""",
                    (int(status == "succeeded"), int(status != "succeeded"),
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

        Both pending and executed reservations block a duplicate within the
        TTL.  A stale pending reservation is replaceable so a crashed worker
        does not permanently prevent a later explicit retry.
        """
        with self._lock:
            conn = self._get_conn()
            now = datetime.now()
            row = conn.execute(
                "SELECT status, updated_at, request_hash FROM write_reservations WHERE idempotency_key = ?",
                (idempotency_key,),
            ).fetchone()
            if row:
                if row["request_hash"] and request_hash and str(row["request_hash"]) != str(request_hash):
                    return False
                try:
                    age = (now - datetime.fromisoformat(row["updated_at"])).total_seconds()
                except (TypeError, ValueError):
                    age = 0
                if age < ttl_seconds:
                    return False
            timestamp = now.isoformat()
            conn.execute(
                "INSERT OR REPLACE INTO write_reservations "
                "(idempotency_key, request_hash, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (idempotency_key, request_hash, "pending", timestamp, timestamp),
            )
            conn.commit()
            return True

    def mark_write_executed(
        self, idempotency_key: str, request_hash: Optional[str] = None,
    ) -> None:
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                "UPDATE write_reservations SET status = ?, updated_at = ? "
                "WHERE idempotency_key = ? AND (request_hash IS NULL OR request_hash = ?)",
                ("executed", datetime.now().isoformat(), idempotency_key, request_hash),
            )
            conn.commit()

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

    def mark_outbox_delivered(self, event_id: str) -> bool:
        with self._lock:
            cursor = self._get_conn().execute(
                """UPDATE outbox_events SET status = 'delivered',
                   claimed_by = NULL, claimed_at = NULL
                   WHERE event_id = ? AND status = 'claimed'""",
                (str(event_id),),
            )
            self._get_conn().commit()
            return cursor.rowcount == 1

    def mark_outbox_retry(
        self, event_id: str, next_retry_at: str, error: Optional[str] = None,
    ) -> bool:
        with self._lock:
            cursor = self._get_conn().execute(
                """UPDATE outbox_events SET status = 'pending',
                   retry_count = retry_count + 1, next_retry_at = ?,
                   last_error = ?, claimed_by = NULL, claimed_at = NULL
                   WHERE event_id = ? AND status = 'claimed'""",
                (str(next_retry_at), str(error) if error else None, str(event_id)),
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
            terminal = status in {"succeeded", "failed", "recovery_required"}
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
            if status in {"succeeded", "failed", "recovery_required"}:
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
                    "provider_state": "unknown",
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

    @staticmethod
    def _skill_row(row: Any) -> Optional[dict]:
        if not row:
            return None
        value = dict(row)
        for key in ("files", "evaluation_report", "report"):
            raw = value.get(key)
            if isinstance(raw, str):
                try:
                    value[key] = json.loads(raw or "{}")
                except (TypeError, ValueError):
                    value[key] = {}
        return value

    def create_skill_version(
        self, version_id: str, tenant_id: str, skill_name: str,
        version: str, files: dict[str, dict[str, Any]], sha256: str,
        created_by: str, status: str = "draft",
    ) -> dict:
        now = datetime.now().isoformat()
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                """INSERT INTO skill_versions
                   (version_id, tenant_id, skill_name, version, status, files,
                    sha256, created_by, created_at, evaluation_status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'not_run')""",
                (
                    str(version_id), str(tenant_id), str(skill_name), str(version),
                    str(status), json.dumps(files, ensure_ascii=False, sort_keys=True),
                    str(sha256), str(created_by), now,
                ),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM skill_versions WHERE version_id = ?",
                (str(version_id),),
            ).fetchone()
            return self._skill_row(row) or {}

    def get_skill_version(
        self, tenant_id: str, skill_name: str, version: Optional[str] = None,
    ) -> Optional[dict]:
        with self._lock:
            conn = self._get_conn()
            if version:
                row = conn.execute(
                    "SELECT * FROM skill_versions WHERE tenant_id = ? "
                    "AND skill_name = ? AND version = ?",
                    (str(tenant_id), str(skill_name), str(version)),
                ).fetchone()
            else:
                row = conn.execute(
                    """SELECT v.* FROM skill_versions v
                       JOIN skill_releases r ON r.version_id = v.version_id
                       WHERE r.tenant_id = ? AND r.skill_name = ?""",
                    (str(tenant_id), str(skill_name)),
                ).fetchone()
            return self._skill_row(row)

    def list_skill_versions(
        self, tenant_id: str, skill_name: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict]:
        limit = max(1, min(int(limit), 200))
        with self._lock:
            conn = self._get_conn()
            if skill_name:
                rows = conn.execute(
                    "SELECT * FROM skill_versions WHERE tenant_id = ? "
                    "AND skill_name = ? ORDER BY created_at DESC LIMIT ?",
                    (str(tenant_id), str(skill_name), limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM skill_versions WHERE tenant_id = ? "
                    "ORDER BY created_at DESC LIMIT ?",
                    (str(tenant_id), limit),
                ).fetchall()
            return [self._skill_row(row) for row in rows]

    def publish_skill_version(
        self, tenant_id: str, skill_name: str, version: str,
    ) -> Optional[dict]:
        now = datetime.now().isoformat()
        with self._lock:
            conn = self._get_conn()
            row = conn.execute(
                "SELECT * FROM skill_versions WHERE tenant_id = ? "
                "AND skill_name = ? AND version = ?",
                (str(tenant_id), str(skill_name), str(version)),
            ).fetchone()
            # Archived versions remain immutable and can be selected as an
            # explicit rollback target.  The release pointer is the source of
            # truth for what is currently active; version status alone must
            # not make rollback impossible.
            if not row:
                return None
            conn.execute(
                "UPDATE skill_versions SET status = 'archived' WHERE tenant_id = ? "
                "AND skill_name = ? AND status = 'published'",
                (str(tenant_id), str(skill_name)),
            )
            conn.execute(
                "UPDATE skill_versions SET status = 'published', published_at = ? "
                "WHERE version_id = ?",
                (now, str(row["version_id"])),
            )
            conn.execute(
                "INSERT INTO skill_releases (tenant_id, skill_name, version_id, updated_at) "
                "VALUES (?, ?, ?, ?) ON CONFLICT(tenant_id, skill_name) DO UPDATE SET "
                "version_id = excluded.version_id, updated_at = excluded.updated_at",
                (str(tenant_id), str(skill_name), str(row["version_id"]), now),
            )
            conn.commit()
            published = conn.execute(
                "SELECT * FROM skill_versions WHERE version_id = ?",
                (str(row["version_id"]),),
            ).fetchone()
            return self._skill_row(published)

    def unpublish_skill_version(
        self, tenant_id: str, skill_name: str, version: str,
    ) -> Optional[dict]:
        """Remove the active release pointer and archive that version.

        The version remains available for audit or an explicit later rollback;
        only the tenant/Skill release pointer is removed.  The join and
        version check make this operation safe when an older API request tries
        to unpublish a release that has already been replaced.
        """
        with self._lock:
            conn = self._get_conn()
            row = conn.execute(
                """SELECT v.* FROM skill_versions v
                   JOIN skill_releases r ON r.version_id = v.version_id
                   WHERE r.tenant_id = ? AND r.skill_name = ?
                     AND v.version = ?""",
                (str(tenant_id), str(skill_name), str(version)),
            ).fetchone()
            if not row:
                return None
            conn.execute(
                "DELETE FROM skill_releases WHERE tenant_id = ? AND skill_name = ?",
                (str(tenant_id), str(skill_name)),
            )
            conn.execute(
                "UPDATE skill_versions SET status = 'archived' "
                "WHERE version_id = ? AND tenant_id = ?",
                (str(row["version_id"]), str(tenant_id)),
            )
            conn.commit()
            unpublished = conn.execute(
                "SELECT * FROM skill_versions WHERE version_id = ?",
                (str(row["version_id"]),),
            ).fetchone()
            return self._skill_row(unpublished)

    def set_skill_evaluation(
        self, version_id: str, tenant_id: str, status: str, run_id: Optional[str] = None,
        report: Optional[dict] = None,
    ) -> bool:
        with self._lock:
            conn = self._get_conn()
            sql = (
                "UPDATE skill_versions SET evaluation_status = ?, "
                "evaluation_run_id = ?, evaluation_report = ? "
                "WHERE version_id = ? AND tenant_id = ?"
            )
            params = [
                str(status), str(run_id) if run_id else None,
                json.dumps(report or {}, ensure_ascii=False, sort_keys=True),
                str(version_id), str(tenant_id),
            ]
            # A worker from an older retry must not overwrite the current
            # evaluation attached to this immutable version.
            if run_id:
                sql += " AND evaluation_run_id = ?"
                params.append(str(run_id))
            cursor = conn.execute(sql, params)
            conn.commit()
            return cursor.rowcount > 0

    def create_skill_evaluation(
        self, run_id: str, version_id: str, tenant_id: str,
        status: str = "queued",
    ) -> dict:
        now = datetime.now().isoformat()
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                """INSERT INTO skill_evaluation_runs
                   (run_id, version_id, tenant_id, status, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (str(run_id), str(version_id), str(tenant_id), str(status), now, now),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM skill_evaluation_runs WHERE run_id = ? "
                "AND tenant_id = ?",
                (str(run_id), str(tenant_id)),
            ).fetchone()
            return self._skill_row(row) or {}

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
        now = datetime.now().isoformat()
        with self._lock:
            conn = self._get_conn()
            row = conn.execute(
                "SELECT version_id, evaluation_status FROM skill_versions "
                "WHERE version_id = ? AND tenant_id = ?",
                (str(version_id), str(tenant_id)),
            ).fetchone()
            if not row or str(row["evaluation_status"]) in {"queued", "running"}:
                return None
            conn.execute(
                "INSERT INTO skill_evaluation_runs "
                "(run_id, version_id, tenant_id, status, created_at, updated_at) "
                "VALUES (?, ?, ?, 'queued', ?, ?)",
                (str(run_id), str(version_id), str(tenant_id), now, now),
            )
            cursor = conn.execute(
                "UPDATE skill_versions SET evaluation_status = 'queued', "
                "evaluation_run_id = ?, evaluation_report = '{}' "
                "WHERE version_id = ? AND tenant_id = ? "
                "AND evaluation_status NOT IN ('queued', 'running')",
                (str(run_id), str(version_id), str(tenant_id)),
            )
            if cursor.rowcount != 1:
                conn.rollback()
                return None
            conn.commit()
            claimed = conn.execute(
                "SELECT * FROM skill_evaluation_runs WHERE run_id = ? "
                "AND tenant_id = ?",
                (str(run_id), str(tenant_id)),
            ).fetchone()
            return self._skill_row(claimed)

    def get_skill_evaluation(self, run_id: str, tenant_id: str) -> Optional[dict]:
        with self._lock:
            row = self._get_conn().execute(
                "SELECT * FROM skill_evaluation_runs WHERE run_id = ? "
                "AND tenant_id = ?",
                (str(run_id), str(tenant_id)),
            ).fetchone()
            return self._skill_row(row)

    def update_skill_evaluation_run(
        self, run_id: str, tenant_id: str, status: str, report: Optional[dict] = None,
        error: Optional[str] = None,
    ) -> bool:
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute(
                "UPDATE skill_evaluation_runs SET status = ?, report = ?, error = ?, "
                "updated_at = ? WHERE run_id = ? AND tenant_id = ?",
                (
                    str(status),
                    json.dumps(report or {}, ensure_ascii=False, sort_keys=True),
                    str(error) if error else None,
                    datetime.now().isoformat(),
                    str(run_id), str(tenant_id),
                ),
            )
            conn.commit()
            return cursor.rowcount > 0

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
        try:
            age = max(0.0, float(stale_after_seconds))
        except (TypeError, ValueError):
            raise ValueError("stale_after_seconds must be a non-negative number")
        cutoff = (datetime.now() - timedelta(seconds=age)).isoformat()
        recovered = 0
        with self._lock:
            conn = self._get_conn()
            rows = conn.execute(
                "SELECT run_id, version_id FROM skill_evaluation_runs "
                "WHERE status IN ('queued', 'running') AND updated_at <= ?",
                (cutoff,),
            ).fetchall()
            for row in rows:
                run_id = str(row["run_id"])
                version_id = str(row["version_id"])
                now = datetime.now().isoformat()
                report = {
                    "recovered": True,
                    "reason": "evaluation worker interrupted before completion",
                    "recovered_at": now,
                }
                conn.execute("SAVEPOINT recover_skill_evaluation")
                version_cursor = conn.execute(
                    "UPDATE skill_versions SET evaluation_status = 'error', "
                    "evaluation_run_id = ?, evaluation_report = ? "
                    "WHERE version_id = ? AND evaluation_run_id = ? "
                    "AND evaluation_status IN ('queued', 'running')",
                    (
                        run_id,
                        json.dumps(report, ensure_ascii=False, sort_keys=True),
                        version_id,
                        run_id,
                    ),
                )
                if version_cursor.rowcount != 1:
                    conn.execute("ROLLBACK TO recover_skill_evaluation")
                    conn.execute("RELEASE recover_skill_evaluation")
                    continue
                run_cursor = conn.execute(
                    "UPDATE skill_evaluation_runs SET status = 'error', "
                    "report = ?, error = ?, updated_at = ? "
                    "WHERE run_id = ? AND status IN ('queued', 'running')",
                    (
                        json.dumps(report, ensure_ascii=False, sort_keys=True),
                        "skill-up evaluation interrupted; retry is allowed",
                        now,
                        run_id,
                    ),
                )
                if run_cursor.rowcount == 1 and version_cursor.rowcount == 1:
                    conn.execute("RELEASE recover_skill_evaluation")
                    recovered += 1
                else:
                    conn.execute("ROLLBACK TO recover_skill_evaluation")
                    conn.execute("RELEASE recover_skill_evaluation")
            conn.commit()
        return recovered

    # -- Generic Plugin package control plane ---------------------------

    @staticmethod
    def _plugin_row(row: Any) -> Optional[dict]:
        if not row:
            return None
        value = dict(row)
        for key in ("manifest", "files"):
            raw = value.get(key)
            if isinstance(raw, str):
                try:
                    value[key] = json.loads(raw or "{}")
                except (TypeError, ValueError):
                    value[key] = {}
        value["signature_verified"] = bool(value.get("signature_verified"))
        return value

    def create_plugin_package(
        self, package_id: str, tenant_id: str, plugin_id: str, version: str,
        manifest: dict, files: dict[str, dict[str, Any]], package_digest: str,
        signature_verified: bool, created_by: str, status: str = "validated",
    ) -> dict:
        """Persist one immutable, tenant-owned Plugin package snapshot."""
        now = datetime.now().isoformat()
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                """INSERT INTO plugin_packages
                   (package_id, tenant_id, plugin_id, version, manifest, files,
                    package_digest, signature_verified, status, created_by,
                    created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    str(package_id), str(tenant_id), str(plugin_id), str(version),
                    json.dumps(manifest, ensure_ascii=False, sort_keys=True),
                    json.dumps(files, ensure_ascii=False, sort_keys=True),
                    str(package_digest), int(bool(signature_verified)), str(status),
                    str(created_by), now, now,
                ),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM plugin_packages WHERE package_id = ?",
                (str(package_id),),
            ).fetchone()
            return self._plugin_row(row) or {}

    def get_plugin_package(
        self, tenant_id: str, plugin_id: str, version: Optional[str] = None,
    ) -> Optional[dict]:
        with self._lock:
            conn = self._get_conn()
            if version:
                row = conn.execute(
                    "SELECT * FROM plugin_packages WHERE tenant_id = ? "
                    "AND plugin_id = ? AND version = ?",
                    (str(tenant_id), str(plugin_id), str(version)),
                ).fetchone()
            else:
                row = conn.execute(
                    """SELECT p.* FROM plugin_packages p
                       JOIN plugin_releases r ON r.package_id = p.package_id
                       WHERE r.tenant_id = ? AND r.plugin_id = ?""",
                    (str(tenant_id), str(plugin_id)),
                ).fetchone()
            return self._plugin_row(row)

    def list_plugin_packages(
        self, tenant_id: str, plugin_id: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict]:
        limit = max(1, min(int(limit), 200))
        with self._lock:
            conn = self._get_conn()
            if plugin_id:
                rows = conn.execute(
                    "SELECT * FROM plugin_packages WHERE tenant_id = ? "
                    "AND plugin_id = ? ORDER BY created_at DESC LIMIT ?",
                    (str(tenant_id), str(plugin_id), limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM plugin_packages WHERE tenant_id = ? "
                    "ORDER BY created_at DESC LIMIT ?",
                    (str(tenant_id), limit),
                ).fetchall()
            return [self._plugin_row(row) for row in rows]

    def activate_plugin_package(
        self, tenant_id: str, plugin_id: str, version: str,
    ) -> Optional[dict]:
        now = datetime.now().isoformat()
        with self._lock:
            conn = self._get_conn()
            row = conn.execute(
                "SELECT * FROM plugin_packages WHERE tenant_id = ? "
                "AND plugin_id = ? AND version = ?",
                (str(tenant_id), str(plugin_id), str(version)),
            ).fetchone()
            if not row or str(row["status"]) == "uninstalled":
                return None
            conn.execute(
                "UPDATE plugin_packages SET status = 'inactive', updated_at = ? "
                "WHERE tenant_id = ? AND plugin_id = ? AND status = 'active'",
                (now, str(tenant_id), str(plugin_id)),
            )
            conn.execute(
                "UPDATE plugin_packages SET status = 'active', activated_at = ?, "
                "updated_at = ?, last_error = NULL WHERE package_id = ?",
                (now, now, str(row["package_id"])),
            )
            conn.execute(
                """INSERT INTO plugin_releases
                   (tenant_id, plugin_id, package_id, updated_at)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(tenant_id, plugin_id) DO UPDATE SET
                   package_id = excluded.package_id, updated_at = excluded.updated_at""",
                (str(tenant_id), str(plugin_id), str(row["package_id"]), now),
            )
            conn.commit()
            active = conn.execute(
                "SELECT * FROM plugin_packages WHERE package_id = ?",
                (str(row["package_id"]),),
            ).fetchone()
            return self._plugin_row(active)

    def deactivate_plugin_package(
        self, tenant_id: str, plugin_id: str, version: str,
    ) -> Optional[dict]:
        now = datetime.now().isoformat()
        with self._lock:
            conn = self._get_conn()
            row = conn.execute(
                """SELECT p.* FROM plugin_packages p
                   JOIN plugin_releases r ON r.package_id = p.package_id
                   WHERE r.tenant_id = ? AND r.plugin_id = ?
                     AND p.version = ?""",
                (str(tenant_id), str(plugin_id), str(version)),
            ).fetchone()
            if not row:
                return None
            conn.execute(
                "DELETE FROM plugin_releases WHERE tenant_id = ? AND plugin_id = ?",
                (str(tenant_id), str(plugin_id)),
            )
            conn.execute(
                "UPDATE plugin_packages SET status = 'inactive', updated_at = ? "
                "WHERE package_id = ?",
                (now, str(row["package_id"])),
            )
            conn.commit()
            updated = conn.execute(
                "SELECT * FROM plugin_packages WHERE package_id = ?",
                (str(row["package_id"]),),
            ).fetchone()
            return self._plugin_row(updated)

    def uninstall_plugin_package(
        self, tenant_id: str, plugin_id: str, version: str,
    ) -> Optional[dict]:
        """Remove a package from the active release without deleting audit data."""
        now = datetime.now().isoformat()
        with self._lock:
            conn = self._get_conn()
            row = conn.execute(
                "SELECT * FROM plugin_packages WHERE tenant_id = ? "
                "AND plugin_id = ? AND version = ?",
                (str(tenant_id), str(plugin_id), str(version)),
            ).fetchone()
            if not row or str(row["status"]) == "uninstalled":
                return None
            conn.execute(
                "DELETE FROM plugin_releases WHERE tenant_id = ? AND plugin_id = ? "
                "AND package_id = ?",
                (str(tenant_id), str(plugin_id), str(row["package_id"])),
            )
            conn.execute(
                "UPDATE plugin_packages SET status = 'uninstalled', updated_at = ? "
                "WHERE package_id = ?",
                (now, str(row["package_id"])),
            )
            conn.commit()
            removed = conn.execute(
                "SELECT * FROM plugin_packages WHERE package_id = ?",
                (str(row["package_id"]),),
            ).fetchone()
            return self._plugin_row(removed)
    
    # -- Session --
    
    # -- Agent Memory -----------------------------------------------------

    @staticmethod
    def _memory_from_row(row: Any, score: float = 0.0) -> MemoryRecord:
        data = dict(row)
        try:
            tags = json.loads(data.get("tags") or "[]")
        except (TypeError, ValueError):
            tags = []
        if not isinstance(tags, list):
            tags = []
        return MemoryRecord(
            memory_id=str(data["memory_id"]),
            tenant_id=str(data["tenant_id"]),
            user_id=str(data["user_id"]),
            kind=str(data["kind"]),
            content=str(data["content"]),
            source=str(data["source"]),
            session_id=data.get("session_id"),
            tags=tuple(str(tag) for tag in tags),
            importance=float(data.get("importance") or 0.5),
            confidence=float(data.get("confidence") or 1.0),
            created_at=str(data.get("created_at") or ""),
            updated_at=str(data.get("updated_at") or ""),
            expires_at=data.get("expires_at"),
            status=str(data.get("status") or "active"),
            memory_key=data.get("memory_key"),
            superseded_by=data.get("superseded_by"),
            score=score,
        )

    def save_memory(self, record: MemoryRecord) -> None:
        """Persist one already-policy-checked memory record."""
        if not isinstance(record, MemoryRecord):
            raise TypeError("record must be a MemoryRecord")
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                """INSERT OR REPLACE INTO memories
                (memory_id, tenant_id, user_id, session_id, kind, content, source,
                 tags, importance, confidence, created_at, updated_at, expires_at,
                 status, memory_key, superseded_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    record.memory_id, record.tenant_id, record.user_id,
                    record.session_id, record.kind, record.content, record.source,
                    json.dumps(list(record.tags), ensure_ascii=False), record.importance,
                    record.confidence, record.created_at, record.updated_at,
                    record.expires_at, record.status,
                    record.memory_key, record.superseded_by,
                ),
            )
            conn.commit()

    def find_active_memory(
        self, memory_key: str, *, tenant_id: str, user_id: str,
    ) -> Optional[MemoryRecord]:
        """Find the current version of one scoped logical memory."""
        with self._lock:
            row = self._get_conn().execute(
                """SELECT * FROM memories
                   WHERE tenant_id = ? AND user_id = ? AND memory_key = ?
                     AND status = 'active'
                   ORDER BY updated_at DESC LIMIT 1""",
                (str(tenant_id), str(user_id), str(memory_key)),
            ).fetchone()
            return self._memory_from_row(row) if row else None

    def supersede_memory(
        self, memory_id: str, superseded_by: str, *, tenant_id: str, user_id: str,
    ) -> bool:
        """Close an older logical version while retaining its audit history."""
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute(
                """UPDATE memories
                   SET status = 'superseded', superseded_by = ?, updated_at = ?
                   WHERE memory_id = ? AND tenant_id = ? AND user_id = ?
                     AND status = 'active'""",
                (
                    str(superseded_by), datetime.now(timezone.utc).isoformat(),
                    str(memory_id), str(tenant_id), str(user_id),
                ),
            )
            conn.commit()
            return cursor.rowcount > 0

    def search_memories(
        self, query: str, *, tenant_id: str, user_id: str,
        session_id: Optional[str] = None, kinds: Optional[List[str]] = None,
        limit: int = 10,
    ) -> List[MemoryRecord]:
        """Scope memory first, then perform deterministic lexical ranking."""
        if limit <= 0:
            return []
        params: list[Any] = [str(tenant_id), str(user_id)]
        query_sql = (
            "SELECT * FROM memories WHERE tenant_id = ? AND user_id = ? "
            "AND status = 'active'"
        )
        if session_id:
            query_sql += " AND (session_id = ? OR session_id IS NULL)"
            params.append(str(session_id))
        normalized_kinds = [str(kind).strip().lower() for kind in (kinds or []) if str(kind).strip()]
        if normalized_kinds:
            placeholders = ",".join("?" for _ in normalized_kinds)
            query_sql += f" AND kind IN ({placeholders})"
            params.extend(normalized_kinds)
        query_sql += " ORDER BY updated_at DESC LIMIT ?"
        # The small candidate bound keeps SQLite recall predictable. Ranking
        # remains backend-owned and can later become a MySQL full-text query.
        params.append(max(20, min(200, int(limit) * 10)))
        raw_terms = re.findall(r"[\u4e00-\u9fff]{2,}|[a-z0-9_]{2,}", str(query or "").lower())
        terms: list[str] = []
        for term in raw_terms:
            terms.append(term)
            if re.fullmatch(r"[\u4e00-\u9fff]+", term) and len(term) > 2:
                terms.extend(term[index:index + 2] for index in range(len(term) - 1))
        phrase = str(query or "").strip().lower()
        ranked: list[tuple[float, MemoryRecord]] = []
        half_life_days = {
            "working": 2.0,
            "episodic": 14.0,
            "semantic": 45.0,
            "procedural": 120.0,
        }
        now = datetime.now(timezone.utc)
        with self._lock:
            rows = self._get_conn().execute(query_sql, params).fetchall()
        for row in rows:
            expires_at = row["expires_at"]
            if expires_at:
                try:
                    expiry = datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
                    if expiry.tzinfo is None:
                        expiry = expiry.replace(tzinfo=timezone.utc)
                    if expiry <= now:
                        continue
                except (TypeError, ValueError, OverflowError):
                    # Invalid expiry is safer treated as expired than recalled.
                    continue
            record = self._memory_from_row(row)
            searchable = f"{record.content} {' '.join(record.tags)}".lower()
            score = 0.0
            if phrase and phrase in searchable:
                score += 4.0
            score += sum(1.0 for term in terms if term in searchable)
            if not terms and not phrase:
                score = 0.1
            if score <= 0:
                continue
            try:
                updated_at = datetime.fromisoformat(
                    str(record.updated_at).replace("Z", "+00:00")
                )
                if updated_at.tzinfo is None:
                    updated_at = updated_at.replace(tzinfo=timezone.utc)
                age_days = max(0.0, (now - updated_at).total_seconds() / 86400.0)
            except (TypeError, ValueError, OverflowError):
                age_days = 3650.0
            half_life = half_life_days.get(record.kind, 30.0)
            recency = math.pow(0.5, age_days / half_life)
            score = (
                score * (0.7 + 0.3 * recency)
                + record.importance * 0.5
                + record.confidence * 0.5
            )
            ranked.append((score, record))
        ranked.sort(key=lambda item: (-item[0], item[1].updated_at, item[1].memory_id))
        return [
            MemoryRecord(**{**record.__dict__, "score": round(score, 6)})
            for score, record in ranked[: int(limit)]
        ]

    def delete_memory(self, memory_id: str, *, tenant_id: str, user_id: str) -> bool:
        """Tombstone a record; a tenant/user can never delete another scope."""
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute(
                "UPDATE memories SET status = 'deleted', updated_at = ? "
                "WHERE memory_id = ? AND tenant_id = ? AND user_id = ? AND status != 'deleted'",
                (datetime.now().isoformat(), str(memory_id), str(tenant_id), str(user_id)),
            )
            conn.commit()
            return cursor.rowcount > 0

    def create_session(self, session_id: str, user_id: str, account_id: str = None, 
                       metadata: dict = None) -> None:
        with self._lock:
            conn = self._get_conn()
            now = datetime.now().isoformat()
            # Session creation is intentionally insert-once. Replacing a row
            # would clear a cross-instance lease while another turn is using
            # the session; metadata updates have their own method.
            session_metadata = metadata or {}
            tenant_id = str(session_metadata.get("tenant_id") or "default")
            sql = """INSERT OR IGNORE INTO sessions
                     (session_id, user_id, tenant_id, account_id, created_at, updated_at, metadata)
                     VALUES (?, ?, ?, ?, ?, ?, ?)"""
            conn.execute(sql, (session_id, user_id, tenant_id, account_id, now, now,
                               json.dumps(session_metadata)))
            conn.commit()
    
    def update_session(self, session_id: str, metadata: dict = None) -> None:
        with self._lock:
            conn = self._get_conn()
            sql = "UPDATE sessions SET updated_at = ?, metadata = ? WHERE session_id = ?"
            conn.execute(sql, (datetime.now().isoformat(), json.dumps(metadata or {}), session_id))
            conn.commit()
    
    def get_session(self, session_id: str) -> Optional[dict]:
        with self._lock:
            conn = self._get_conn()
            row = conn.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,)).fetchone()
            if row:
                return dict(row)
            return None

    def delete_session(self, session_id: str) -> bool:
        """Delete a session; SQLite foreign keys remove its local history."""
        with self._lock:
            conn = self._get_conn()
            # Keep durable run/event replay data within the same privacy
            # boundary even for databases created before the FK was added.
            conn.execute(
                "DELETE FROM execution_runs WHERE session_id = ?",
                (str(session_id),),
            )
            cursor = conn.execute(
                "DELETE FROM sessions WHERE session_id = ?", (str(session_id),)
            )
            conn.commit()
            return cursor.rowcount > 0

    def list_sessions(self, user_id: str = None, limit: int = 50) -> List[dict]:
        with self._lock:
            conn = self._get_conn()
            if user_id:
                rows = conn.execute(
                    "SELECT * FROM sessions WHERE user_id = ? ORDER BY updated_at DESC LIMIT ?",
                    (user_id, limit)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM sessions ORDER BY updated_at DESC LIMIT ?", (limit,)
                ).fetchall()
            return [dict(r) for r in rows]

    def acquire_session_lease(
        self, session_id: str, lease_owner: str, lease_seconds: float = 300.0,
    ) -> bool:
        """Atomically reserve a session across Runtime instances."""
        if not session_id or not lease_owner or float(lease_seconds) <= 0:
            return False
        now = datetime.now(timezone.utc)
        now_text = now.isoformat()
        expires_text = (now + timedelta(seconds=float(lease_seconds))).isoformat()
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute(
                """UPDATE sessions
                   SET lease_owner = ?, lease_expires_at = ?, updated_at = ?
                   WHERE session_id = ?
                     AND (lease_owner IS NULL OR lease_owner = ?
                          OR lease_expires_at IS NULL OR lease_expires_at <= ?)""",
                (
                    str(lease_owner), expires_text, now_text, str(session_id),
                    str(lease_owner), now_text,
                ),
            )
            conn.commit()
            return cursor.rowcount == 1

    def heartbeat_session_lease(
        self, session_id: str, lease_owner: str, lease_seconds: float = 300.0,
    ) -> bool:
        if not session_id or not lease_owner or float(lease_seconds) <= 0:
            return False
        now = datetime.now(timezone.utc)
        with self._lock:
            cursor = self._get_conn().execute(
                """UPDATE sessions SET lease_expires_at = ?, updated_at = ?
                   WHERE session_id = ? AND lease_owner = ?""",
                (
                    (now + timedelta(seconds=float(lease_seconds))).isoformat(),
                    now.isoformat(), str(session_id), str(lease_owner),
                ),
            )
            self._get_conn().commit()
            return cursor.rowcount == 1

    def release_session_lease(self, session_id: str, lease_owner: str) -> bool:
        if not session_id or not lease_owner:
            return False
        with self._lock:
            cursor = self._get_conn().execute(
                """UPDATE sessions SET lease_owner = NULL, lease_expires_at = NULL
                   WHERE session_id = ? AND lease_owner = ?""",
                (str(session_id), str(lease_owner)),
            )
            self._get_conn().commit()
            return cursor.rowcount == 1

    def record_conversation_message(self, record: ConversationMessageRecord) -> None:
        data = record.to_dict()
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                """INSERT OR REPLACE INTO conversation_messages
                   (message_id, session_id, turn_id, role, content, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    data["message_id"], data["session_id"], data["turn_id"],
                    data["role"], data["content"], data["created_at"],
                ),
            )
            conn.commit()

    def list_conversation_messages(
        self, session_id: str, limit: int = 200,
    ) -> List[ConversationMessageRecord]:
        with self._lock:
            conn = self._get_conn()
            rows = conn.execute(
                """SELECT * FROM conversation_messages
                   WHERE session_id = ?
                   ORDER BY created_at DESC, rowid DESC LIMIT ?""",
                (session_id, limit),
            ).fetchall()
            return [
                ConversationMessageRecord.from_row(dict(row))
                for row in reversed(rows)
            ]

    # -- Tenant-scoped Markdown Wiki documents -------------------------

    @staticmethod
    def _knowledge_row(row: Any) -> Optional[KnowledgeDocumentRecord]:
        return KnowledgeDocumentRecord.from_row(dict(row)) if row else None

    def create_knowledge_document(self, record: KnowledgeDocumentRecord) -> KnowledgeDocumentRecord:
        data = record.to_dict()
        with self._lock:
            conn = self._get_conn()
            try:
                conn.execute(
                    """INSERT INTO knowledge_documents
                       (document_id, tenant_id, title, content, platform, layer,
                        knowledge_type, source, source_ref, version, confidence,
                        tags, status, created_by, created_at, updated_at, published_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        data["document_id"], data["tenant_id"], data["title"],
                        data["content"], data["platform"], data["layer"],
                        data["knowledge_type"], data["source"], data["source_ref"],
                        data["version"], data["confidence"],
                        json.dumps(data["tags"], ensure_ascii=False), data["status"],
                        data["created_by"], data["created_at"], data["updated_at"],
                        data["published_at"],
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise PersistenceConflictError(
                    "knowledge document violates a persistence constraint"
                ) from exc
            conn.commit()
            return self._knowledge_row(
                conn.execute(
                    "SELECT * FROM knowledge_documents WHERE document_id = ?",
                    (data["document_id"],),
                ).fetchone()
            ) or record

    def update_knowledge_document(
        self, document_id: str, *, tenant_id: str, data: dict[str, Any],
    ) -> Optional[KnowledgeDocumentRecord]:
        now = datetime.now().isoformat()
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute(
                """UPDATE knowledge_documents
                   SET title = ?, content = ?, platform = ?, layer = ?,
                       knowledge_type = ?, source = ?, source_ref = ?,
                       version = ?, confidence = ?, tags = ?, updated_at = ?
                   WHERE document_id = ? AND tenant_id = ? AND status = 'draft'""",
                (
                    data["title"], data["content"], data["platform"], data["layer"],
                    data["knowledge_type"], data["source"], data["source_ref"],
                    data["version"], data["confidence"],
                    json.dumps(data["tags"], ensure_ascii=False), now,
                    str(document_id), str(tenant_id),
                ),
            )
            conn.commit()
            if not cursor.rowcount:
                return None
            return self._knowledge_row(
                conn.execute(
                    "SELECT * FROM knowledge_documents WHERE document_id = ?",
                    (str(document_id),),
                ).fetchone()
            )

    def delete_knowledge_document(
        self, document_id: str, *, tenant_id: str,
    ) -> Optional[KnowledgeDocumentRecord]:
        now = datetime.now().isoformat()
        with self._lock:
            conn = self._get_conn()
            existing = self._knowledge_row(conn.execute(
                "SELECT * FROM knowledge_documents WHERE document_id = ? AND tenant_id = ?",
                (str(document_id), str(tenant_id)),
            ).fetchone())
            if not existing:
                return None
            if existing.status == "published":
                conn.execute(
                    """UPDATE knowledge_documents
                       SET status = 'deprecated', updated_at = ?
                       WHERE document_id = ? AND tenant_id = ?""",
                    (now, str(document_id), str(tenant_id)),
                )
                conn.commit()
                return self._knowledge_row(conn.execute(
                    "SELECT * FROM knowledge_documents WHERE document_id = ?",
                    (str(document_id),),
                ).fetchone())
            conn.execute(
                "DELETE FROM knowledge_documents WHERE document_id = ? AND tenant_id = ?",
                (str(document_id), str(tenant_id)),
            )
            conn.commit()
            return existing

    def get_knowledge_document(
        self, document_id: str, *, tenant_id: Optional[str] = None,
    ) -> Optional[KnowledgeDocumentRecord]:
        query = "SELECT * FROM knowledge_documents WHERE document_id = ?"
        params: list[Any] = [str(document_id)]
        if tenant_id is not None:
            query += " AND tenant_id = ?"
            params.append(str(tenant_id))
        with self._lock:
            return self._knowledge_row(self._get_conn().execute(query, params).fetchone())

    def list_knowledge_documents(
        self, tenant_id: str, status: Optional[str] = None, limit: int = 100,
    ) -> list[KnowledgeDocumentRecord]:
        limit = max(1, min(int(limit), 500))
        query = "SELECT * FROM knowledge_documents WHERE tenant_id = ?"
        params: list[Any] = [str(tenant_id)]
        if status:
            query += " AND status = ?"
            params.append(str(status))
        query += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)
        with self._lock:
            rows = self._get_conn().execute(query, params).fetchall()
            return [self._knowledge_row(row) for row in rows if row]

    def publish_knowledge_document(
        self, document_id: str, *, tenant_id: str,
    ) -> Optional[KnowledgeDocumentRecord]:
        now = datetime.now().isoformat()
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute(
                """UPDATE knowledge_documents SET status = 'draft', updated_at = ?
                   WHERE tenant_id = ? AND title = (
                       SELECT title FROM knowledge_documents WHERE document_id = ?
                   ) AND status = 'published' AND document_id != ?""",
                (now, str(tenant_id), str(document_id), str(document_id)),
            )
            cursor = conn.execute(
                """UPDATE knowledge_documents
                   SET status = 'published', published_at = ?, updated_at = ?
                   WHERE document_id = ? AND tenant_id = ? AND status != 'deprecated'""",
                (now, now, str(document_id), str(tenant_id)),
            )
            conn.commit()
            if not cursor.rowcount:
                return None
            return self._knowledge_row(
                conn.execute(
                    "SELECT * FROM knowledge_documents WHERE document_id = ?",
                    (str(document_id),),
                ).fetchone()
            )

    def unpublish_knowledge_document(
        self, document_id: str, *, tenant_id: str,
    ) -> Optional[KnowledgeDocumentRecord]:
        now = datetime.now().isoformat()
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute(
                """UPDATE knowledge_documents
                   SET status = 'draft', updated_at = ?
                   WHERE document_id = ? AND tenant_id = ? AND status = 'published'""",
                (now, str(document_id), str(tenant_id)),
            )
            conn.commit()
            if not cursor.rowcount:
                return None
            return self._knowledge_row(
                conn.execute(
                    "SELECT * FROM knowledge_documents WHERE document_id = ?",
                    (str(document_id),),
                ).fetchone()
            )

    def _ensure_knowledge_search_index(self, conn: Any) -> bool:
        if not isinstance(conn, sqlite3.Connection):
            return False
        try:
            existing = conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'knowledge_search_fts'"
            ).fetchone()
            if existing:
                columns = {
                    str(row[1])
                    for row in conn.execute("PRAGMA table_info(knowledge_search_fts)").fetchall()
                }
                if not {"category", "subcategory"}.issubset(columns):
                    conn.execute("DROP TABLE knowledge_search_fts")
            conn.execute(
                """CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_search_fts
                   USING fts5(
                       scope UNINDEXED,
                       chunk_id UNINDEXED,
                       document_id UNINDEXED,
                       title,
                       heading_path,
                       tags,
                       category,
                       subcategory,
                       content,
                       platform UNINDEXED,
                       knowledge_type UNINDEXED,
                       status UNINDEXED,
                       confidence UNINDEXED
                   )"""
            )
        except sqlite3.OperationalError:
            return False
        return True

    def rebuild_knowledge_search_index(
        self, chunks: list[dict[str, Any]], *, scope: str,
    ) -> bool:
        normalized_scope = str(scope or "").strip()
        if not normalized_scope:
            return False
        with self._lock:
            conn = self._get_conn()
            if not self._ensure_knowledge_search_index(conn):
                return False
            conn.execute(
                "DELETE FROM knowledge_search_fts WHERE scope = ?",
                (normalized_scope,),
            )
            rows = []
            for chunk in chunks or []:
                if not isinstance(chunk, dict):
                    continue
                rows.append(
                    (
                        normalized_scope,
                        str(chunk.get("chunk_id") or ""),
                        str(chunk.get("document_id") or ""),
                        str(chunk.get("title") or ""),
                        str(chunk.get("heading_path") or ""),
                        str(chunk.get("tags") or ""),
                        str(chunk.get("category") or ""),
                        str(chunk.get("subcategory") or ""),
                        str(chunk.get("content") or ""),
                        str(chunk.get("platform") or "all"),
                        str(chunk.get("knowledge_type") or "general"),
                        str(chunk.get("status") or "published"),
                        float(chunk.get("confidence") or 0.0),
                    )
                )
            if rows:
                conn.executemany(
                    """INSERT INTO knowledge_search_fts
                       (scope, chunk_id, document_id, title, heading_path,
                        tags, category, subcategory, content, platform,
                        knowledge_type, status, confidence)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    rows,
                )
            conn.commit()
        return True

    def search_knowledge_search_index(
        self, query: str, *, scopes: list[str], limit: int = 100,
    ) -> list[dict[str, Any]]:
        safe_query = str(query or "").strip()
        normalized_scopes = [str(scope).strip() for scope in scopes if str(scope).strip()]
        if not safe_query or not normalized_scopes or limit <= 0:
            return []
        with self._lock:
            conn = self._get_conn()
            if not self._ensure_knowledge_search_index(conn):
                return []
            placeholders = ",".join("?" for _ in normalized_scopes)
            rows = conn.execute(
                f"""SELECT scope, chunk_id, document_id,
                           bm25(knowledge_search_fts, 8.0, 5.0, 3.0, 3.0, 3.0, 1.0) AS rank
                    FROM knowledge_search_fts
                    WHERE knowledge_search_fts MATCH ?
                      AND scope IN ({placeholders})
                      AND status = 'published'
                    ORDER BY rank ASC
                    LIMIT ?""",
                [safe_query, *normalized_scopes, max(1, min(int(limit), 500))],
            ).fetchall()
        return [dict(row) for row in rows]

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
        d = record.to_dict()
        with self._lock:
            conn = self._get_conn()
            sql = """INSERT INTO campaign_state 
                     (id, platform, campaign_id, name, status, objective, budget_daily,
                      created_at, updated_at, metadata, account_id)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                     ON CONFLICT(id) DO UPDATE SET
                       name = excluded.name,
                       status = excluded.status,
                       objective = excluded.objective,
                       budget_daily = excluded.budget_daily,
                       updated_at = excluded.updated_at,
                       metadata = excluded.metadata,
                       account_id = excluded.account_id"""
            conn.execute(sql, (
                d['id'], d['platform'], d['campaign_id'], d['name'], d['status'],
                d['objective'], d['budget_daily'], d['created_at'], d['updated_at'],
                d['metadata'], d['account_id']
            ))
            conn.commit()
    
    def get_campaign(
        self, platform: str, campaign_id: str, account_id: str = None
    ) -> Optional[CampaignRecord]:
        with self._lock:
            # Campaign IDs are only unique inside a provider account.  A
            # caller that omits account scope must not receive the newest
            # record from an arbitrary account.
            if account_id is None or account_id == "":
                return None
            conn = self._get_conn()
            row = conn.execute(
                "SELECT * FROM campaign_state WHERE platform = ? AND campaign_id = ? "
                "AND account_id = ?",
                (platform, campaign_id, account_id),
            ).fetchone()
            return CampaignRecord.from_row(dict(row)) if row else None
    
    def list_campaigns(
        self, platform: str = None, status: str = None, limit: int = 100,
        account_id: str = None,
    ) -> List[CampaignRecord]:
        with self._lock:
            conn = self._get_conn()
            clauses = []
            params: list[Any] = []
            if platform:
                clauses.append("platform = ?")
                params.append(platform)
            if status:
                clauses.append("status = ?")
                params.append(status)
            if account_id:
                clauses.append("account_id = ?")
                params.append(account_id)
            where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
            rows = conn.execute(
                f"SELECT * FROM campaign_state{where} ORDER BY updated_at DESC LIMIT ?",
                (*params, limit),
            ).fetchall()
            return [CampaignRecord.from_row(dict(r)) for r in rows]
    
    def update_campaign_status(
        self, platform: str, campaign_id: str, status: str,
        account_id: str = None,
    ) -> bool:
        with self._lock:
            conn = self._get_conn()
            if account_id is None:
                cursor = conn.execute(
                    "UPDATE campaign_state SET status = ?, updated_at = ? "
                    "WHERE platform = ? AND campaign_id = ? AND account_id IS NULL",
                    (status, datetime.now().isoformat(), platform, campaign_id),
                )
            else:
                cursor = conn.execute(
                    "UPDATE campaign_state SET status = ?, updated_at = ? "
                    "WHERE platform = ? AND campaign_id = ? AND account_id = ?",
                    (status, datetime.now().isoformat(), platform, campaign_id, account_id),
                )
            conn.commit()
            return cursor.rowcount > 0
    
    def delete_campaign(
        self, platform: str, campaign_id: str, account_id: str = None,
    ) -> bool:
        with self._lock:
            conn = self._get_conn()
            if account_id is None:
                cursor = conn.execute(
                    "DELETE FROM campaign_state WHERE platform = ? AND campaign_id = ? "
                    "AND account_id IS NULL",
                    (platform, campaign_id),
                )
            else:
                cursor = conn.execute(
                    "DELETE FROM campaign_state WHERE platform = ? AND campaign_id = ? "
                    "AND account_id = ?",
                    (platform, campaign_id, account_id),
                )
            conn.commit()
            return cursor.rowcount > 0

    # -- Workflow audit / compensation ---------------------------------

    def create_workflow(
        self, workflow_id: str, session_id: str, intent_type: str,
        execution_mode: str, status: str = "planned", metadata: dict = None,
        emit_outbox: bool = True,
    ) -> None:
        now = datetime.now().isoformat()
        with self._lock:
            conn = self._get_conn()
            session_row = conn.execute(
                "SELECT tenant_id, metadata FROM sessions WHERE session_id = ?",
                (str(session_id),),
            ).fetchone()
            tenant_id = str(session_row["tenant_id"] or "default") if session_row else "default"
            conn.execute(
                """INSERT INTO workflows
                   (workflow_id, session_id, tenant_id, intent_type, execution_mode, status,
                    metadata, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (workflow_id, session_id, tenant_id, intent_type, execution_mode, status,
                json.dumps(metadata or {}), now, now),
            )
            if emit_outbox:
                conn.execute(
                    """INSERT OR IGNORE INTO outbox_events
                       (event_id, run_id, event_type, payload, created_at)
                       VALUES (?, ?, 'workflow.created', ?, ?)""",
                    (
                        str(uuid.uuid4()), str(workflow_id),
                        json.dumps({
                            "workflow_id": str(workflow_id),
                            "status": str(status),
                            "metadata": metadata or {},
                        }, ensure_ascii=False, sort_keys=True, default=str),
                        now,
                    ),
                )
            conn.commit()

    def update_workflow(
        self, workflow_id: str, status: str, metadata: dict = None,
        emit_outbox: bool = True,
    ) -> bool:
        with self._lock:
            conn = self._get_conn()
            current = conn.execute(
                "SELECT status FROM workflows WHERE workflow_id = ?",
                (workflow_id,),
            ).fetchone()
            if not current:
                return False
            current_status = str(current[0])
            if status not in WORKFLOW_TRANSITIONS.get(current_status, set()):
                logger.warning(
                    "Rejected invalid workflow transition %s -> %s for %s",
                    current_status, status, workflow_id,
                )
                return False
            # Only an actively running workflow owns an execution lease.
            # Awaiting confirmation and recovery-required are waiting states;
            # a recovery worker must acquire a fresh lease through the atomic
            # claim method instead of inheriting the old Runtime lease.
            lease_sql = ", lease_owner = NULL, lease_expires_at = NULL" if status != "running" else ""
            merged_metadata = {}
            if metadata is None:
                existing = conn.execute(
                    "SELECT metadata FROM workflows WHERE workflow_id = ?",
                    (workflow_id,),
                ).fetchone()
                if existing and existing[0]:
                    try:
                        merged_metadata = json.loads(existing[0]) or {}
                    except (TypeError, ValueError):
                        merged_metadata = {}
                cursor = conn.execute(
                    f"UPDATE workflows SET status = ?, updated_at = ?{lease_sql} WHERE workflow_id = ?",
                    (status, datetime.now().isoformat(), workflow_id),
                )
            else:
                existing = conn.execute(
                    "SELECT metadata FROM workflows WHERE workflow_id = ?",
                    (workflow_id,),
                ).fetchone()
                merged_metadata = {}
                if existing and existing[0]:
                    try:
                        merged_metadata = json.loads(existing[0]) or {}
                    except (TypeError, ValueError):
                        merged_metadata = {}
                merged_metadata.update(metadata)
                cursor = conn.execute(
                    f"""UPDATE workflows SET status = ?, metadata = ?, updated_at = ?{lease_sql}
                       WHERE workflow_id = ?""",
                    (status, json.dumps(merged_metadata), datetime.now().isoformat(), workflow_id),
                )
            if cursor.rowcount > 0 and emit_outbox:
                conn.execute(
                    """INSERT INTO outbox_events
                       (event_id, run_id, event_type, payload, created_at)
                       VALUES (?, ?, 'workflow.updated', ?, ?)""",
                    (
                        str(uuid.uuid4()), str(workflow_id),
                        json.dumps({
                            "workflow_id": str(workflow_id),
                            "from_status": current_status,
                            "status": str(status),
                            "metadata": merged_metadata,
                        }, ensure_ascii=False, sort_keys=True, default=str),
                        datetime.now().isoformat(),
                    ),
                )
            conn.commit()
            return cursor.rowcount > 0

    def heartbeat_workflow(
        self, workflow_id: str, lease_owner: str, lease_seconds: float = 300.0,
    ) -> bool:
        """Refresh an active workflow lease without changing its state."""
        if not lease_owner or float(lease_seconds) <= 0:
            return False
        now = datetime.now()
        now_iso = now.isoformat()
        expires_iso = (now + timedelta(seconds=float(lease_seconds))).isoformat()
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute(
                """UPDATE workflows
                   SET updated_at = ?, lease_owner = ?, lease_expires_at = ?
                   WHERE workflow_id = ? AND status = 'running'
                     AND (lease_owner IS NULL OR lease_owner = ?)""",
                (now_iso, str(lease_owner), expires_iso, workflow_id, str(lease_owner)),
            )
            conn.commit()
            return cursor.rowcount > 0

    def recover_stale_workflow(
        self, workflow_id: str, stale_after_seconds: float = 300.0,
        metadata: dict = None,
    ) -> bool:
        """Atomically move an expired running workflow into recovery."""
        if float(stale_after_seconds) <= 0:
            return False
        now = datetime.now()
        cutoff_iso = (now - timedelta(seconds=float(stale_after_seconds))).isoformat()
        now_iso = now.isoformat()
        merged_metadata = dict(metadata or {})
        merged_metadata.setdefault("recovery_reason", "stale_running_workflow")
        merged_metadata.setdefault("recovery_detected_at", now_iso)
        with self._lock:
            conn = self._get_conn()
            current = conn.execute(
                "SELECT metadata FROM workflows WHERE workflow_id = ? AND status = 'running' "
                "AND updated_at <= ?",
                (workflow_id, cutoff_iso),
            ).fetchone()
            if not current:
                return False
            try:
                existing = json.loads(current[0] or "{}") or {}
            except (TypeError, ValueError):
                existing = {}
            existing.update(merged_metadata)
            cursor = conn.execute(
                """UPDATE workflows SET status = 'recovery_required', metadata = ?,
                   updated_at = ?, lease_owner = NULL, lease_expires_at = NULL
                   WHERE workflow_id = ? AND status = 'running' AND updated_at <= ?""",
                (json.dumps(existing), now_iso, workflow_id, cutoff_iso),
            )
            conn.commit()
            return cursor.rowcount > 0

    def claim_workflow_recovery(
        self, workflow_id: str, lease_owner: str,
        stale_after_seconds: float = 300.0, lease_seconds: float = 300.0,
    ) -> bool:
        """Atomically claim a stale/runnable workflow for one recovery worker."""
        if not lease_owner or float(lease_seconds) <= 0:
            return False
        now = datetime.now()
        now_iso = now.isoformat()
        expires_iso = (now + timedelta(seconds=float(lease_seconds))).isoformat()
        cutoff_iso = (now - timedelta(seconds=float(stale_after_seconds))).isoformat()
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute(
                """UPDATE workflows SET status = 'recovery_required',
                   updated_at = ?, lease_owner = ?, lease_expires_at = ?
                   WHERE workflow_id = ?
                     AND ((status = 'running' AND updated_at <= ?)
                       OR status IN ('failed', 'partially_failed', 'blocked', 'recovery_required'))
                     AND (lease_owner IS NULL OR lease_owner = ?
                       OR lease_expires_at IS NULL OR lease_expires_at <= ?)""",
                (
                    now_iso, str(lease_owner), expires_iso, workflow_id,
                    cutoff_iso, str(lease_owner), now_iso,
                ),
            )
            conn.commit()
            return cursor.rowcount > 0

    def release_workflow_lease(self, workflow_id: str, lease_owner: str) -> bool:
        """Release only the lease owned by the calling recovery worker."""
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute(
                """UPDATE workflows SET lease_owner = NULL, lease_expires_at = NULL
                   WHERE workflow_id = ? AND lease_owner = ?""",
                (workflow_id, str(lease_owner)),
            )
            conn.commit()
            return cursor.rowcount > 0

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
        now = datetime.now().isoformat()
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                """INSERT INTO workflow_items
                   (item_id, workflow_id, sequence, platform, account_id, tool_name, status,
                   input_data, output_data, error, compensation_required,
                   resource_type, parent_resource_type, parent_sequence, parent_resource_id,
                   provider_resource_id, logical_resource_id,
                   created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    item_id, workflow_id, sequence, platform, account_id, tool_name, status,
                    json.dumps(input_data or {}),
                    json.dumps(output_data) if output_data is not None else None,
                    error, int(compensation_required), resource_type, parent_resource_type,
                    parent_sequence, parent_resource_id, provider_resource_id,
                    logical_resource_id, now, now,
                ),
            )
            conn.commit()

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
        with self._lock:
            conn = self._get_conn()
            current = conn.execute(
                "SELECT status FROM workflow_items WHERE workflow_id = ? AND sequence = ?",
                (workflow_id, int(sequence)),
            ).fetchone()
            if not current:
                now = datetime.now().isoformat()
                conn.execute(
                    """INSERT INTO workflow_items
                       (item_id, workflow_id, sequence, platform, account_id, tool_name, status,
                       input_data, output_data, error, compensation_required,
                       resource_type, parent_resource_type, parent_sequence, parent_resource_id,
                       provider_resource_id, logical_resource_id,
                       created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        item_id, workflow_id, int(sequence), platform, account_id,
                        tool_name, status, json.dumps(input_data or {}),
                        json.dumps(output_data) if output_data is not None else None,
                        error, int(compensation_required), resource_type, parent_resource_type,
                        parent_sequence, parent_resource_id, provider_resource_id,
                        logical_resource_id, now, now,
                    ),
                )
            else:
                current_status = str(current[0])
                if status not in WORKFLOW_ITEM_TRANSITIONS.get(current_status, set()):
                    raise ValueError(
                        f"cannot advance workflow item {sequence} from "
                        f"{current_status} to {status}"
                    )
                assignments = [
                    "status = ?", "input_data = ?", "output_data = ?",
                    "error = ?", "compensation_required = ?",
                    "account_id = ?", "resource_type = ?",
                    "parent_resource_type = ?", "parent_sequence = ?",
                    "parent_resource_id = ?", "provider_resource_id = ?",
                    "logical_resource_id = ?", "updated_at = ?",
                ]
                conn.execute(
                    f"UPDATE workflow_items SET {', '.join(assignments)} "
                    "WHERE workflow_id = ? AND sequence = ?",
                    (
                        status, json.dumps(input_data or {}),
                        json.dumps(output_data) if output_data is not None else None,
                        error, int(compensation_required), account_id, resource_type,
                        parent_resource_type,
                        parent_sequence, parent_resource_id, provider_resource_id,
                        logical_resource_id, datetime.now().isoformat(),
                        workflow_id, int(sequence),
                    ),
                )
            conn.commit()

    def get_workflow(self, workflow_id: str) -> Optional[dict]:
        with self._lock:
            conn = self._get_conn()
            row = conn.execute(
                "SELECT * FROM workflows WHERE workflow_id = ?", (workflow_id,)
            ).fetchone()
            if not row:
                return None
            result = dict(row)
            try:
                result["metadata"] = json.loads(result.get("metadata") or "{}")
            except (TypeError, ValueError):
                result["metadata"] = {}
            result["items"] = self.list_workflow_items(workflow_id)
            return result

    def list_workflow_items(self, workflow_id: str) -> list[dict]:
        with self._lock:
            conn = self._get_conn()
            rows = conn.execute(
                "SELECT * FROM workflow_items WHERE workflow_id = ? ORDER BY sequence ASC",
                (workflow_id,),
            ).fetchall()
            items = []
            for row in rows:
                item = dict(row)
                for key in ("input_data", "output_data"):
                    if item.get(key):
                        try:
                            item[key] = json.loads(item[key])
                        except (TypeError, ValueError):
                            item[key] = {}
                item["compensation_required"] = bool(item.get("compensation_required"))
                items.append(item)
        return items

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
        assignments = ["status = ?", "error = ?", "updated_at = ?"]
        values: list[Any] = [status, error, datetime.now().isoformat()]
        if output_data is not None:
            assignments.append("output_data = ?")
            values.append(json.dumps(output_data))
        if compensation_required is not None:
            assignments.append("compensation_required = ?")
            values.append(int(compensation_required))
        for column, value in (
            ("account_id", account_id),
            ("resource_type", resource_type),
            ("parent_resource_type", parent_resource_type),
            ("parent_sequence", parent_sequence),
            ("parent_resource_id", parent_resource_id),
            ("provider_resource_id", provider_resource_id),
            ("logical_resource_id", logical_resource_id),
        ):
            if value is not None:
                assignments.append(f"{column} = ?")
                values.append(value)
        values.extend([workflow_id, int(sequence)])
        with self._lock:
            conn = self._get_conn()
            current = conn.execute(
                "SELECT status FROM workflow_items WHERE workflow_id = ? AND sequence = ?",
                (workflow_id, int(sequence)),
            ).fetchone()
            if not current:
                return False
            current_status = str(current[0])
            if status not in WORKFLOW_ITEM_TRANSITIONS.get(current_status, set()):
                logger.warning(
                    "Rejected invalid workflow item transition %s -> %s for %s/%s",
                    current_status, status, workflow_id, sequence,
                )
                return False
            cursor = conn.execute(
                f"UPDATE workflow_items SET {', '.join(assignments)} "
                "WHERE workflow_id = ? AND sequence = ?",
                values,
            )
            conn.commit()
            return cursor.rowcount > 0

    def list_resumable_workflows(
        self, user_id: Optional[str] = None, limit: int = 50,
        include_stale_running: bool = False, stale_after_seconds: float = 300.0,
    ) -> list[dict]:
        """List non-terminal workflows for an operator/recovery worker."""
        statuses = ["failed", "partially_failed", "recovery_required", "blocked"]
        if include_stale_running:
            statuses.append("running")
        placeholders = ",".join("?" for _ in statuses)
        params: list[Any] = list(statuses)
        query = (
            "SELECT w.* FROM workflows w JOIN sessions s "
            f"ON s.session_id = w.session_id WHERE w.status IN ({placeholders})"
        )
        if user_id is not None:
            query += " AND s.user_id = ?"
            params.append(str(user_id))
        query += " ORDER BY w.updated_at ASC LIMIT ?"
        params.append(max(1, int(limit)))
        with self._lock:
            rows = self._get_conn().execute(query, params).fetchall()
            result = []
            for row in rows:
                item = dict(row)
                if item.get("status") == "running" and include_stale_running:
                    try:
                        age = time.time() - datetime.fromisoformat(
                            str(item.get("updated_at"))
                        ).timestamp()
                    except (TypeError, ValueError, OverflowError):
                        age = 0
                    if age < float(stale_after_seconds):
                        continue
                try:
                    item["metadata"] = json.loads(item.get("metadata") or "{}")
                except (TypeError, ValueError):
                    item["metadata"] = {}
                result.append(item)
            return result

    def mark_workflow_items_for_compensation(
        self, workflow_id: str, sequences: list[int]
    ) -> None:
        if not sequences:
            return
        placeholders = ",".join("?" for _ in sequences)
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                f"""UPDATE workflow_items SET compensation_required = 1,
                       updated_at = ? WHERE workflow_id = ?
                       AND sequence IN ({placeholders})""",
                (datetime.now().isoformat(), workflow_id, *sequences),
            )
            conn.commit()
