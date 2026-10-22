"""Canonical persistence schema shared by SQL backend adapters."""

SCHEMA_VERSION = 26
DATABASE_SCHEMA = """
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
        tool_call_id TEXT,
        name TEXT,
        metadata TEXT NOT NULL DEFAULT '{}',
        FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS conversation_feedback (
        feedback_id TEXT PRIMARY KEY,
        session_id TEXT NOT NULL,
        turn_id TEXT NOT NULL,
        tenant_id TEXT NOT NULL,
        user_id TEXT NOT NULL,
        rating TEXT NOT NULL,
        reason TEXT,
        submitted_at TEXT NOT NULL,
        review_status TEXT NOT NULL DEFAULT 'pending',
        reviewer_id TEXT,
        reviewed_at TEXT,
        expected_behavior TEXT,
        assertions TEXT NOT NULL DEFAULT '{}',
        UNIQUE (session_id, turn_id),
        FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
    );
    CREATE INDEX IF NOT EXISTS idx_conversation_feedback_scope_time
        ON conversation_feedback(tenant_id, user_id, submitted_at);
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
        published_at TEXT,
        wiki_type TEXT NOT NULL DEFAULT 'concept',
        derived_from TEXT NOT NULL DEFAULT '',
        raw_sha256 TEXT NOT NULL DEFAULT '',
        wikilinks TEXT NOT NULL DEFAULT '[]'
    );

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
        ingest_attempts INTEGER NOT NULL DEFAULT 0,
        ingest_started_at TEXT,
        ingest_finished_at TEXT,
        UNIQUE (tenant_id, sha256)
    );
    CREATE INDEX IF NOT EXISTS idx_raw_knowledge_sources_scope
        ON raw_knowledge_sources(tenant_id, status, updated_at DESC);

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
    CREATE INDEX IF NOT EXISTS idx_conversation_messages_turn_history
        ON conversation_messages(session_id, turn_id, created_at, message_id);
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
    -- Tenant indexes for sessions/workflows are created by migration 16.
    -- Keeping them out of the bootstrap script is important: an older
    -- database can still be missing tenant_id until that migration runs.

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

    CREATE TABLE IF NOT EXISTS mcp_servers (
        server_id TEXT PRIMARY KEY,
        tenant_id TEXT NOT NULL,
        name TEXT NOT NULL,
        description TEXT NOT NULL DEFAULT '',
        endpoint TEXT NOT NULL,
        transport TEXT NOT NULL DEFAULT 'streamable_http',
        auth_type TEXT NOT NULL DEFAULT 'none',
        credential_ref TEXT,
        auth_header TEXT NOT NULL DEFAULT 'Authorization',
        timeout_seconds REAL NOT NULL DEFAULT 500,
        status TEXT NOT NULL DEFAULT 'draft',
        enabled INTEGER NOT NULL DEFAULT 0,
        validation_status TEXT NOT NULL DEFAULT 'not_run',
        validation_report TEXT NOT NULL DEFAULT '{}',
        protocol_version TEXT,
        created_by TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        last_checked_at TEXT,
        last_error TEXT,
        UNIQUE (tenant_id, name)
    );
    CREATE INDEX IF NOT EXISTS idx_mcp_servers_scope
        ON mcp_servers(tenant_id, status, updated_at DESC);

    CREATE TABLE IF NOT EXISTS mcp_tools (
        tool_id TEXT PRIMARY KEY,
        server_id TEXT NOT NULL,
        tenant_id TEXT NOT NULL,
        remote_name TEXT NOT NULL,
        title TEXT NOT NULL DEFAULT '',
        description TEXT NOT NULL DEFAULT '',
        input_schema TEXT NOT NULL DEFAULT '{}',
        annotations TEXT NOT NULL DEFAULT '{}',
        intent_types TEXT NOT NULL DEFAULT '[]',
        intent_aliases TEXT NOT NULL DEFAULT '[]',
        skill_refs TEXT NOT NULL DEFAULT '[]',
        action TEXT NOT NULL DEFAULT 'invoke',
        resource_type TEXT NOT NULL DEFAULT 'mcp_invocation',
        resource_id_field TEXT,
        readback_tool TEXT,
        idempotency_key_field TEXT,
        required_permissions TEXT NOT NULL DEFAULT '[]',
        traits TEXT NOT NULL DEFAULT '["external", "mcp"]',
        status TEXT NOT NULL DEFAULT 'discovered',
        enabled INTEGER NOT NULL DEFAULT 0,
        validation_status TEXT NOT NULL DEFAULT 'pending',
        last_error TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        UNIQUE (server_id, remote_name),
        FOREIGN KEY (server_id) REFERENCES mcp_servers(server_id) ON DELETE CASCADE
    );
    CREATE INDEX IF NOT EXISTS idx_mcp_tools_server
        ON mcp_tools(tenant_id, server_id, status, updated_at DESC);

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
