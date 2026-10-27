"""Versioned schema upgrades, separate from MySQL runtime operations."""

import json
from .mysql_sql import _mysql_schema

def add_column_if_missing(conn, table, column, definition):
    rows = conn.execute("SHOW COLUMNS FROM `" + table + "`").fetchall()
    if column not in {str(row["Field"]) for row in rows}:
        conn.execute(f"ALTER TABLE `{table}` ADD COLUMN `{column}` {definition}")


def migrate_1(conn):
    add_column_if_missing(conn, "campaign_state", "account_id", "VARCHAR(255)")


def migrate_2(conn):
    for column in ("lease_owner", "lease_expires_at"):
        add_column_if_missing(conn, "workflows", column, "VARCHAR(255)")


def migrate_3(conn):
    for column, definition in {
        "account_id": "VARCHAR(255)", "resource_type": "VARCHAR(255)",
        "parent_resource_type": "VARCHAR(255)", "parent_sequence": "BIGINT",
        "parent_resource_id": "VARCHAR(255)", "provider_resource_id": "VARCHAR(255)",
        "logical_resource_id": "VARCHAR(255)",
    }.items():
        add_column_if_missing(conn, "workflow_items", column, definition)


def migrate_5(conn):
    for column in ("input_hash", "preview_hash", "request_hash", "contract_hash"):
        add_column_if_missing(conn, "approvals", column, "VARCHAR(255)")


def migrate_7(conn):
    add_column_if_missing(conn, "write_reservations", "request_hash", "VARCHAR(255)")


def migrate_9(conn):
    for column in ("lease_owner", "lease_expires_at"):
        add_column_if_missing(conn, "sessions", column, "VARCHAR(255)")


def migrate_10(conn):
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


def migrate_11(conn):
    add_column_if_missing(conn, "memories", "memory_key", "VARCHAR(191)")
    add_column_if_missing(conn, "memories", "superseded_by", "VARCHAR(191)")
    conn.executescript(_mysql_schema(
        """
        CREATE INDEX IF NOT EXISTS idx_memories_key
            ON memories(tenant_id, user_id, memory_key, status, updated_at);
        """
    ))


def migrate_12(conn):
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


def migrate_13(conn):
    add_column_if_missing(
        conn, "creation_templates", "is_default", "BIGINT NOT NULL DEFAULT 0"
    )
    conn.executescript(_mysql_schema(
        """
        CREATE INDEX IF NOT EXISTS idx_creation_templates_default
            ON creation_templates(tenant_id, user_id, blueprint_id, scope_type, is_default);
        """
    ))


def migrate_14(conn):
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


def migrate_15(conn):
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


def migrate_16(conn):
    add_column_if_missing(
        conn, "sessions", "tenant_id", "VARCHAR(255) NOT NULL DEFAULT 'default'"
    )
    add_column_if_missing(
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
    queries = (
        ("session_id", "SELECT session_id, metadata FROM sessions WHERE tenant_id = ?",
         "UPDATE sessions SET tenant_id = ? WHERE session_id = ?"),
        ("workflow_id", "SELECT workflow_id, metadata FROM workflows WHERE tenant_id = ?",
         "UPDATE workflows SET tenant_id = ? WHERE workflow_id = ?"),
    )
    for key, select_sql, update_sql in queries:
        for row in conn.execute(select_sql, ("default",)).fetchall():
            try:
                metadata = json.loads(row["metadata"] or "{}") or {}
            except (TypeError, ValueError):
                metadata = {}
            if not isinstance(metadata, dict):
                continue
            tenant_id = str(metadata.get("tenant_id") or "").strip()
            if tenant_id and tenant_id != "default":
                conn.execute(
                    update_sql,
                    (tenant_id, str(row[key])),
                )


def migrate_17(conn):
    conn.executescript(_mysql_schema(
        """
        CREATE INDEX IF NOT EXISTS idx_mcp_servers_scope
            ON mcp_servers(tenant_id, status, updated_at);
        CREATE INDEX IF NOT EXISTS idx_mcp_tools_server
            ON mcp_tools(tenant_id, server_id, status, updated_at);
        """
    ))


def migrate_18(conn):
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
        add_column_if_missing(conn, "mcp_tools", column, definition)


def migrate_19(conn):
    for column, definition in {
        "wiki_type": "VARCHAR(32) NOT NULL DEFAULT 'concept'",
        "derived_from": "VARCHAR(255) NOT NULL DEFAULT ''",
        "raw_sha256": "VARCHAR(128) NOT NULL DEFAULT ''",
        "wikilinks": "LONGTEXT NOT NULL",
    }.items():
        add_column_if_missing(
            conn, "knowledge_documents", column, definition
        )
    conn.executescript(_mysql_schema(
        """
        CREATE TABLE IF NOT EXISTS raw_knowledge_sources (
            source_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            filename TEXT NOT NULL,
            media_type TEXT NOT NULL,
            content LONGTEXT NOT NULL,
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
            ON raw_knowledge_sources(tenant_id, status, updated_at);
        """
    ))


def migrate_20(conn):
    for column, definition in {
        "ingest_attempts": "INT NOT NULL DEFAULT 0",
        "ingest_started_at": "VARCHAR(64)",
        "ingest_finished_at": "VARCHAR(64)",
    }.items():
        add_column_if_missing(
            conn, "raw_knowledge_sources", column, definition
        )


def migrate_21(conn):
    for column, definition in {
        "tool_call_id": "VARCHAR(255)",
        "name": "VARCHAR(255)",
        "metadata": "LONGTEXT NOT NULL",
    }.items():
        add_column_if_missing(
            conn, "conversation_messages", column, definition,
        )


def migrate_22(conn):
    conn.executescript(_mysql_schema(
        """
        CREATE INDEX IF NOT EXISTS idx_conversation_messages_turn_history
            ON conversation_messages(session_id, turn_id, created_at, message_id);
        """
    ))


def migrate_23(conn):
    conn.executescript(_mysql_schema(
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
    ))
    conn.execute(
        """INSERT IGNORE INTO conversation_feedback
           (feedback_id, session_id, turn_id, tenant_id, user_id, rating, submitted_at)
           SELECT UUID(), cm.session_id, cm.turn_id, s.tenant_id, s.user_id,
                  CASE WHEN JSON_VALID(cm.metadata)
                       THEN JSON_UNQUOTE(JSON_EXTRACT(
                           cm.metadata, '$.user_feedback.rating'
                       ))
                       ELSE NULL END,
                  CASE WHEN JSON_VALID(cm.metadata)
                       THEN JSON_UNQUOTE(JSON_EXTRACT(
                           cm.metadata, '$.user_feedback.submitted_at'
                       ))
                       ELSE NULL END
           FROM conversation_messages cm
           JOIN sessions s ON s.session_id = cm.session_id
           WHERE cm.role = 'assistant'
             AND CASE WHEN JSON_VALID(cm.metadata)
                      THEN JSON_UNQUOTE(JSON_EXTRACT(
                          cm.metadata, '$.user_feedback.rating'
                      ))
                      ELSE NULL END IN ('positive', 'negative')
             AND CASE WHEN JSON_VALID(cm.metadata)
                      THEN JSON_UNQUOTE(JSON_EXTRACT(
                          cm.metadata, '$.user_feedback.submitted_at'
                      ))
                      ELSE NULL END IS NOT NULL"""
    )


def migrate_24(conn):
    for column, definition in {
        "reason": "LONGTEXT",
        "review_status": "VARCHAR(32) NOT NULL DEFAULT 'pending'",
        "reviewer_id": "VARCHAR(191)",
        "reviewed_at": "VARCHAR(64)",
        "expected_behavior": "LONGTEXT",
    }.items():
        add_column_if_missing(
            conn, "conversation_feedback", column, definition,
        )
    conn.executescript(_mysql_schema(
        """
        CREATE INDEX IF NOT EXISTS idx_conversation_feedback_review
            ON conversation_feedback(tenant_id, rating, review_status, submitted_at);
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
    ))


def migrate_25(conn):
    conn.execute(
        """UPDATE conversation_feedback AS feedback
           SET reason = (
               SELECT CASE WHEN JSON_VALID(cm.metadata)
                           THEN JSON_UNQUOTE(JSON_EXTRACT(
                               cm.metadata, '$.user_feedback.reason'
                           ))
                           ELSE NULL END
               FROM conversation_messages AS cm
               WHERE cm.session_id = feedback.session_id
                 AND cm.turn_id = feedback.turn_id
                 AND cm.role = 'assistant'
               ORDER BY cm.created_at DESC, cm.message_id DESC
               LIMIT 1
           )
           WHERE feedback.reason IS NULL OR feedback.reason = ''"""
    )


def migrate_26(conn):
    add_column_if_missing(conn, "conversation_feedback", "assertions", "LONGTEXT")
    conn.execute(
        "UPDATE conversation_feedback SET assertions = ? "
        "WHERE assertions IS NULL OR assertions = ''",
        ("{}",),
    )


def migrate_27(conn):
    conn.executescript(_mysql_schema(
        """
        CREATE INDEX IF NOT EXISTS idx_conversation_user_history
            ON conversation_messages(session_id, role, created_at);
        """
    ))


MIGRATIONS = {
    1: migrate_1,
    2: migrate_2,
    3: migrate_3,
    5: migrate_5,
    7: migrate_7,
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
NOOP_VERSIONS = frozenset({4, 6, 8})


def apply_mysql_migration(conn, version):
    if isinstance(version, bool) or not isinstance(version, int):
        raise ValueError("migration version must be an integer")
    if version in NOOP_VERSIONS:
        return
    handler = MIGRATIONS.get(version)
    if handler is None:
        raise ValueError("unsupported MySQL migration version")
    handler(conn)
