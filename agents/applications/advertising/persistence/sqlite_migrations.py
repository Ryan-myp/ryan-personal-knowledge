"""Version-owned SQLite schema upgrades; no application execution logic."""

import sqlite3
import json

def _table_columns(conn, table):
    return {str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})")}


def _add_column_if_missing(conn, table, column, definition):
    if column not in _table_columns(conn, table):
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def migrate_1(conn):
    _add_column_if_missing(conn, "campaign_state", "account_id", "TEXT")


def migrate_2(conn):
    _add_column_if_missing(conn, "workflows", "lease_owner", "TEXT")
    _add_column_if_missing(conn, "workflows", "lease_expires_at", "TEXT")


def migrate_3(conn):
    for column, definition in {
        "account_id": "TEXT",
        "resource_type": "TEXT",
        "parent_resource_type": "TEXT",
        "parent_sequence": "INTEGER",
        "parent_resource_id": "TEXT",
        "provider_resource_id": "TEXT",
        "logical_resource_id": "TEXT",
    }.items():
        _add_column_if_missing(conn, "workflow_items", column, definition)


def migrate_4(conn):
    conn.execute(
        """CREATE TABLE IF NOT EXISTS execution_mode_preferences (
            tenant_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            mode TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (tenant_id, user_id)
        )"""
    )


def migrate_5(conn):
    for column, definition in {
        "input_hash": "TEXT",
        "preview_hash": "TEXT",
        "request_hash": "TEXT",
        "contract_hash": "TEXT",
    }.items():
        _add_column_if_missing(conn, "approvals", column, definition)


def migrate_6(conn):
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


def migrate_7(conn):
    _add_column_if_missing(
        conn, "write_reservations", "request_hash", "TEXT"
    )


def migrate_8(conn):
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


def migrate_9(conn):
    _add_column_if_missing(conn, "sessions", "lease_owner", "TEXT")
    _add_column_if_missing(conn, "sessions", "lease_expires_at", "TEXT")


def migrate_10(conn):
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


def migrate_11(conn):
    _add_column_if_missing(conn, "memories", "memory_key", "TEXT")
    _add_column_if_missing(conn, "memories", "superseded_by", "TEXT")


def migrate_12(conn):
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


def migrate_13(conn):
    _add_column_if_missing(conn, "creation_templates", "is_default", "INTEGER NOT NULL DEFAULT 0")
    conn.execute(
        """CREATE INDEX IF NOT EXISTS idx_creation_templates_default
           ON creation_templates(tenant_id, user_id, blueprint_id, scope_type, is_default)"""
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_memories_key "
        "ON memories(tenant_id, user_id, memory_key, status, updated_at DESC)"
    )


def migrate_14(conn):
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


def migrate_15(conn):
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


def migrate_16(conn):
    _add_column_if_missing(conn, "sessions", "tenant_id", "TEXT NOT NULL DEFAULT 'default'")
    _add_column_if_missing(conn, "workflows", "tenant_id", "TEXT NOT NULL DEFAULT 'default'")
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


def migrate_17(conn):
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_mcp_servers_scope "
        "ON mcp_servers(tenant_id, status, updated_at DESC)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_mcp_tools_server "
        "ON mcp_tools(tenant_id, server_id, status, updated_at DESC)"
    )


def migrate_18(conn):
    for column, definition in {
        "intent_types": "TEXT NOT NULL DEFAULT '[]'",
        "intent_aliases": "TEXT NOT NULL DEFAULT '[]'",
        "skill_refs": "TEXT NOT NULL DEFAULT '[]'",
        "action": "TEXT NOT NULL DEFAULT 'invoke'",
        "resource_type": "TEXT NOT NULL DEFAULT 'mcp_invocation'",
        "resource_id_field": "TEXT",
        "readback_tool": "TEXT",
        "idempotency_key_field": "TEXT",
        "required_permissions": "TEXT NOT NULL DEFAULT '[]'",
        "traits": "TEXT NOT NULL DEFAULT '[\"external\", \"mcp\"]'",
    }.items():
        _add_column_if_missing(conn, "mcp_tools", column, definition)


def migrate_19(conn):
    for column, definition in {
        "wiki_type": "TEXT NOT NULL DEFAULT 'concept'",
        "derived_from": "TEXT NOT NULL DEFAULT ''",
        "raw_sha256": "TEXT NOT NULL DEFAULT ''",
        "wikilinks": "TEXT NOT NULL DEFAULT '[]'",
    }.items():
        _add_column_if_missing(conn, "knowledge_documents", column, definition)
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS raw_knowledge_sources (
            source_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            filename TEXT NOT NULL,
            media_type TEXT NOT NULL,
            content TEXT NOT NULL,
            sha256 TEXT NOT NULL,
            source_ref TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'received',
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            ingest_task_id TEXT,
            ingest_error TEXT,
            UNIQUE (tenant_id, sha256)
        );
        CREATE INDEX IF NOT EXISTS idx_raw_knowledge_sources_scope
            ON raw_knowledge_sources(tenant_id, status, updated_at DESC);
        """
    )


def migrate_20(conn):
    for column, definition in {
        "ingest_attempts": "INTEGER NOT NULL DEFAULT 0",
        "ingest_started_at": "TEXT",
        "ingest_finished_at": "TEXT",
    }.items():
        _add_column_if_missing(
            conn, "raw_knowledge_sources", column, definition
        )


def migrate_21(conn):
    for column, definition in {
        "tool_call_id": "TEXT",
        "name": "TEXT",
        "metadata": "TEXT NOT NULL DEFAULT '{}'",
    }.items():
        _add_column_if_missing(
            conn, "conversation_messages", column, definition,
        )


def migrate_22(conn):
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_conversation_messages_turn_history "
        "ON conversation_messages(session_id, turn_id, created_at, message_id)"
    )


def migrate_23(conn):
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS conversation_feedback (
            feedback_id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            turn_id TEXT NOT NULL,
            tenant_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            rating TEXT NOT NULL,
            submitted_at TEXT NOT NULL,
            UNIQUE (session_id, turn_id),
            FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_conversation_feedback_scope_time
            ON conversation_feedback(tenant_id, user_id, submitted_at);
        """
    )
    conn.execute(
        """INSERT OR IGNORE INTO conversation_feedback
           (feedback_id, session_id, turn_id, tenant_id, user_id, rating, submitted_at)
           SELECT lower(hex(randomblob(16))), cm.session_id, cm.turn_id,
                  s.tenant_id, s.user_id,
                  CASE WHEN json_valid(cm.metadata)
                       THEN json_extract(cm.metadata, '$.user_feedback.rating')
                       ELSE NULL END,
                  CASE WHEN json_valid(cm.metadata)
                       THEN json_extract(cm.metadata, '$.user_feedback.submitted_at')
                       ELSE NULL END
           FROM conversation_messages cm
           JOIN sessions s ON s.session_id = cm.session_id
           WHERE cm.role = 'assistant'
             AND CASE WHEN json_valid(cm.metadata)
                      THEN json_extract(cm.metadata, '$.user_feedback.rating')
                      ELSE NULL END IN ('positive', 'negative')
             AND CASE WHEN json_valid(cm.metadata)
                      THEN json_extract(cm.metadata, '$.user_feedback.submitted_at')
                      ELSE NULL END IS NOT NULL"""
    )


def migrate_24(conn):
    for column, definition in {
        "reason": "TEXT",
        "review_status": "TEXT NOT NULL DEFAULT 'pending'",
        "reviewer_id": "TEXT",
        "reviewed_at": "TEXT",
        "expected_behavior": "TEXT",
    }.items():
        _add_column_if_missing(
            conn, "conversation_feedback", column, definition,
        )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_conversation_feedback_review "
        "ON conversation_feedback(tenant_id, rating, review_status, submitted_at)"
    )
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS knowledge_semantic_index_meta (
            scope TEXT PRIMARY KEY,
            fingerprint TEXT NOT NULL,
            dimension INTEGER NOT NULL DEFAULT 0,
            record_count INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS knowledge_semantic_vectors (
            scope TEXT NOT NULL,
            chunk_id TEXT NOT NULL,
            document_id TEXT NOT NULL,
            vector TEXT NOT NULL,
            dimension INTEGER NOT NULL,
            PRIMARY KEY (scope, chunk_id)
        );
        CREATE INDEX IF NOT EXISTS idx_knowledge_semantic_vectors_scope
            ON knowledge_semantic_vectors(scope, dimension);
        """
    )


def migrate_25(conn):
    conn.execute(
        """UPDATE conversation_feedback
           SET reason = (
               SELECT CASE WHEN json_valid(cm.metadata)
                           THEN json_extract(
                               cm.metadata, '$.user_feedback.reason'
                           )
                           ELSE NULL END
               FROM conversation_messages AS cm
               WHERE cm.session_id = conversation_feedback.session_id
                 AND cm.turn_id = conversation_feedback.turn_id
                 AND cm.role = 'assistant'
               ORDER BY cm.created_at DESC, cm.message_id DESC
               LIMIT 1
           )
           WHERE reason IS NULL OR reason = ''"""
    )


def migrate_26(conn):
    _add_column_if_missing(
        conn, "conversation_feedback", "assertions", "TEXT NOT NULL DEFAULT '{}'",
    )


def migrate_27(conn):
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_conversation_user_history "
        "ON conversation_messages(session_id, role, created_at)"
    )


MIGRATIONS = {
    1: migrate_1,
    2: migrate_2,
    3: migrate_3,
    4: migrate_4,
    5: migrate_5,
    6: migrate_6,
    7: migrate_7,
    8: migrate_8,
    9: migrate_9,
    10: migrate_10,
    11: migrate_11,
    12: migrate_12,
    13: migrate_13,
    14: migrate_14,
    15: migrate_15,
    16: migrate_16,
    17: migrate_17,
    18: migrate_18,
    19: migrate_19,
    20: migrate_20,
    21: migrate_21,
    22: migrate_22,
    23: migrate_23,
    24: migrate_24,
    25: migrate_25,
    26: migrate_26,
    27: migrate_27,
}


def apply_sqlite_migration(conn, version):
    if isinstance(version, bool) or not isinstance(version, int) or version not in MIGRATIONS:
        raise ValueError("unsupported SQLite migration version")
    MIGRATIONS[version](conn)
