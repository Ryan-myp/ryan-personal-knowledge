"""Persistence backend contract used by the ad-agent runtime.

The current implementation is SQLite, but the orchestration layer should not
depend on SQLite connections or SQL semantics.  A future MySQL/PostgreSQL
backend only needs to implement this protocol; workflow, approval and
idempotency policy remains in the Runtime/SessionManager layer.
"""

from __future__ import annotations

from typing import Any, Optional, Protocol


class PersistenceBackend(Protocol):
    """Structural contract for the durable ad-agent state backend."""

    def create_session(
        self, session_id: str, user_id: str,
        account_id: Optional[str] = None, metadata: Optional[dict] = None,
    ) -> None: ...

    def get_session(
        self, session_id: str, user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> Optional[dict]: ...
    def delete_session(self, session_id: str) -> bool: ...
    def update_session(self, session_id: str, metadata: Optional[dict] = None) -> None: ...
    def list_sessions(
        self, user_id: Optional[str] = None, limit: int = 50,
        tenant_id: Optional[str] = None,
    ) -> list[dict]: ...
    def acquire_session_lease(
        self, session_id: str, lease_owner: str, lease_seconds: float = 300.0,
    ) -> bool: ...
    def heartbeat_session_lease(
        self, session_id: str, lease_owner: str, lease_seconds: float = 300.0,
    ) -> bool: ...
    def release_session_lease(self, session_id: str, lease_owner: str) -> bool: ...

    # -- Durable worker liveness -------------------------------------
    def register_worker(
        self, worker_id: str, worker_kind: str, *, metadata: Optional[dict[str, Any]] = None,
        lease_seconds: float = 30.0,
    ) -> None: ...
    def heartbeat_worker(
        self, worker_id: str, *, lease_seconds: float = 30.0,
    ) -> bool: ...
    def unregister_worker(self, worker_id: str) -> bool: ...
    def list_workers(
        self, *, statuses: Optional[list[str]] = None, limit: int = 200,
    ) -> list[dict[str, Any]]: ...
    def get_backend_health(self) -> dict[str, Any]: ...

    def record_conversation_message(self, record: Any) -> None: ...
    def list_conversation_messages(
        self, session_id: str, limit: int = 200,
    ) -> list[Any]: ...

    def create_knowledge_document(self, record: Any) -> Any: ...
    def update_knowledge_document(
        self, document_id: str, *, tenant_id: str, data: dict[str, Any],
    ) -> Optional[Any]: ...
    def delete_knowledge_document(
        self, document_id: str, *, tenant_id: str,
    ) -> Optional[Any]: ...
    def get_knowledge_document(
        self, document_id: str, *, tenant_id: Optional[str] = None,
    ) -> Optional[Any]: ...
    def list_knowledge_documents(
        self, tenant_id: str, status: Optional[str] = None,
        limit: int = 100,
    ) -> list[Any]: ...
    def publish_knowledge_document(
        self, document_id: str, *, tenant_id: str,
    ) -> Optional[Any]: ...
    def unpublish_knowledge_document(
        self, document_id: str, *, tenant_id: str,
    ) -> Optional[Any]: ...
    def rebuild_knowledge_search_index(
        self, chunks: list[dict[str, Any]], *, scope: str,
    ) -> bool: ...
    def search_knowledge_search_index(
        self, query: str, *, scopes: list[str], limit: int = 100,
    ) -> list[dict[str, Any]]: ...

    # -- Campaign creation templates ------------------------------------
    def create_creation_template(self, record: Any) -> Any: ...
    def get_creation_template(
        self, template_id: str, *, tenant_id: str, user_id: str,
    ) -> Optional[Any]: ...
    def list_creation_templates(
        self, tenant_id: str, user_id: str, *, provider: Optional[str] = None,
        blueprint_id: Optional[str] = None, status: Optional[str] = None,
        query: Optional[str] = None, limit: int = 100,
    ) -> list[Any]: ...
    def update_creation_template(
        self, template_id: str, *, tenant_id: str, user_id: str, data: dict[str, Any],
    ) -> Optional[Any]: ...
    def delete_creation_template(
        self, template_id: str, *, tenant_id: str, user_id: str,
    ) -> Optional[Any]: ...
    def record_creation_template_usage(
        self, template_id: str, *, tenant_id: str, user_id: str,
    ) -> Optional[Any]: ...

    def record_tool_call(self, record: Any) -> None: ...
    def list_tool_calls(
        self, session_id: str, turn_id: Optional[str] = None, limit: int = 100,
    ) -> list[Any]: ...

    def save_campaign(self, record: Any) -> None: ...
    def get_campaign(
        self, platform: str, campaign_id: str, account_id: Optional[str] = None,
    ) -> Optional[Any]: ...
    def list_campaigns(
        self, platform: Optional[str] = None, status: Optional[str] = None,
        limit: int = 100, account_id: Optional[str] = None,
    ) -> list[Any]: ...
    def delete_campaign(
        self, platform: str, campaign_id: str, account_id: Optional[str] = None,
    ) -> bool: ...

    def reserve_write(
        self, idempotency_key: str, ttl_seconds: int = 300,
        request_hash: Optional[str] = None,
    ) -> bool: ...
    def mark_write_executed(
        self, idempotency_key: str, request_hash: Optional[str] = None,
    ) -> None: ...
    def release_write(
        self, idempotency_key: str, request_hash: Optional[str] = None,
    ) -> None: ...

    # -- Durable workflow outbox ---------------------------------------
    def insert_outbox_event(self, event: Any) -> None: ...
    def claim_outbox_events(
        self, limit: int = 20, consumer_id: Optional[str] = None,
    ) -> list[Any]: ...
    def mark_outbox_delivered(self, event_id: str) -> bool: ...
    def mark_outbox_retry(
        self, event_id: str, next_retry_at: str, error: Optional[str] = None,
    ) -> bool: ...

    # -- Durable Agent run/event replay -------------------------------
    def create_execution_run(self, record: Any) -> Any: ...
    def append_execution_run_event(self, run_id: str, event: dict[str, Any]) -> bool: ...
    def get_execution_run(
        self, run_id: str, user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> Optional[Any]: ...
    def get_latest_execution_run(
        self, session_id: str, user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> Optional[Any]: ...
    def list_execution_run_events(
        self, run_id: str, after_seq: int = 0, limit: int = 256,
    ) -> list[dict[str, Any]]: ...
    def update_execution_run(
        self, run_id: str, *, workflow_id: Optional[str] = None,
        status: Optional[str] = None, metadata: Optional[dict] = None,
    ) -> bool: ...
    def recover_stale_execution_runs(self, stale_after_seconds: float = 300.0) -> int: ...

    # -- Runtime configuration -----------------------------------------
    # Execution mode is a principal-scoped preference. Persisting ``live``
    # never grants permission to perform a live write; deployment gates,
    # permissions, account scope and confirmation remain Runtime concerns.
    def get_execution_mode(
        self, tenant_id: str, user_id: str,
    ) -> Optional[str]: ...
    def set_execution_mode(
        self, tenant_id: str, user_id: str, mode: str,
    ) -> None: ...

    def create_workflow(
        self, workflow_id: str, session_id: str, intent_type: str,
        execution_mode: str, status: str = "planned",
        metadata: Optional[dict] = None, emit_outbox: bool = True,
    ) -> None: ...
    def update_workflow(
        self, workflow_id: str, status: str, metadata: Optional[dict] = None,
        emit_outbox: bool = True,
    ) -> bool: ...
    def heartbeat_workflow(
        self, workflow_id: str, lease_owner: str, lease_seconds: float = 300.0,
    ) -> bool: ...
    def recover_stale_workflow(
        self, workflow_id: str, stale_after_seconds: float = 300.0,
        metadata: Optional[dict] = None,
    ) -> bool: ...
    def claim_workflow_recovery(
        self, workflow_id: str, lease_owner: str,
        stale_after_seconds: float = 300.0, lease_seconds: float = 300.0,
    ) -> bool: ...
    def release_workflow_lease(self, workflow_id: str, lease_owner: str) -> bool: ...
    def upsert_workflow_item(
        self, item_id: str, workflow_id: str, sequence: int, platform: str,
        tool_name: str, status: str, input_data: dict,
        output_data: Optional[dict] = None, error: Optional[str] = None,
        compensation_required: bool = False,
        resource_type: Optional[str] = None,
        parent_sequence: Optional[int] = None,
        parent_resource_id: Optional[str] = None,
        provider_resource_id: Optional[str] = None,
        logical_resource_id: Optional[str] = None,
        account_id: Optional[str] = None,
        parent_resource_type: Optional[str] = None,
    ) -> None: ...
    def get_workflow(
        self, workflow_id: str, user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> Optional[dict]: ...
    def update_workflow_item(
        self, workflow_id: str, sequence: int, status: str,
        output_data: Optional[dict] = None, error: Optional[str] = None,
        compensation_required: Optional[bool] = None,
        resource_type: Optional[str] = None,
        parent_sequence: Optional[int] = None,
        parent_resource_id: Optional[str] = None,
        provider_resource_id: Optional[str] = None,
        logical_resource_id: Optional[str] = None,
        account_id: Optional[str] = None,
        parent_resource_type: Optional[str] = None,
    ) -> bool: ...
    def mark_workflow_items_for_compensation(
        self, workflow_id: str, sequences: list[int],
    ) -> None: ...
    def list_resumable_workflows(
        self, user_id: Optional[str] = None, limit: int = 50,
        include_stale_running: bool = False, stale_after_seconds: float = 300.0,
        tenant_id: Optional[str] = None,
    ) -> list[dict]: ...

    def validate_approval(
        self, plan_fingerprint: str, token: str, session_id: str,
        user_id: str, account_id: str, tool_name: str,
        input_hash: Optional[str] = None, preview_hash: Optional[str] = None,
        request_hash: Optional[str] = None, contract_hash: Optional[str] = None,
    ) -> tuple[bool, str]: ...
    def create_approval(
        self, plan_fingerprint: str, token: str, session_id: str,
        user_id: str, account_id: str, tool_name: str, expires_at: str,
        input_hash: Optional[str] = None, preview_hash: Optional[str] = None,
        request_hash: Optional[str] = None, contract_hash: Optional[str] = None,
    ) -> None: ...
    def get_approval(self, plan_fingerprint: str) -> Optional[dict]: ...
    def consume_approval(self, plan_fingerprint: str, token: str) -> bool: ...

    # -- Managed Agent Skills -------------------------------------------
    # A Skill version is a complete directory snapshot.  The Runtime only
    # consumes the published snapshot; editing and publication stay in the
    # management layer so a failed draft can never affect live sessions.
    def create_skill_version(
        self, version_id: str, tenant_id: str, skill_name: str,
        version: str, files: dict[str, dict[str, Any]], sha256: str,
        created_by: str, status: str = "draft",
    ) -> dict: ...
    def get_skill_version(
        self, tenant_id: str, skill_name: str, version: Optional[str] = None,
    ) -> Optional[dict]: ...
    def list_skill_versions(
        self, tenant_id: str, skill_name: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict]: ...
    def publish_skill_version(
        self, tenant_id: str, skill_name: str, version: str,
    ) -> Optional[dict]: ...
    def unpublish_skill_version(
        self, tenant_id: str, skill_name: str, version: str,
    ) -> Optional[dict]: ...
    def set_skill_evaluation(
        self, version_id: str, tenant_id: str, status: str, run_id: Optional[str] = None,
        report: Optional[dict] = None,
    ) -> bool: ...
    def create_skill_evaluation(
        self, run_id: str, version_id: str, tenant_id: str,
        status: str = "queued",
    ) -> dict: ...
    def claim_skill_evaluation(
        self, run_id: str, version_id: str, tenant_id: str,
    ) -> Optional[dict]: ...
    def get_skill_evaluation(self, run_id: str, tenant_id: str) -> Optional[dict]: ...
    def update_skill_evaluation_run(
        self, run_id: str, tenant_id: str, status: str, report: Optional[dict] = None,
        error: Optional[str] = None,
    ) -> bool: ...
    def recover_stale_skill_evaluations(
        self, stale_after_seconds: float = 900.0,
    ) -> int: ...

    # -- Generic asynchronous Agent tasks -------------------------------
    def create_task(self, record: Any) -> Any: ...
    def get_task(
        self, task_id: str, tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Optional[Any]: ...
    def find_task_by_idempotency(
        self, tenant_id: str, user_id: str, idempotency_key: str,
    ) -> Optional[Any]: ...
    def list_tasks(
        self, tenant_id: Optional[str] = None, user_id: Optional[str] = None,
        statuses: Optional[list[str]] = None, limit: int = 50,
    ) -> list[Any]: ...
    def claim_task(
        self, task_id: str, lease_owner: str, lease_seconds: float = 300.0,
    ) -> Optional[Any]: ...
    def heartbeat_task(
        self, task_id: str, lease_owner: str, lease_seconds: float = 300.0,
    ) -> bool: ...
    def update_task(
        self, task_id: str, status: str, *, result: Optional[dict] = None,
        error: Optional[str] = None, metadata: Optional[dict] = None,
        workflow_id: Optional[str] = None,
        expected_statuses: Optional[list[str]] = None,
    ) -> bool: ...
    def pause_task(self, task_id: str) -> Optional[Any]: ...
    def resume_task(self, task_id: str) -> Optional[Any]: ...
    def cancel_task(self, task_id: str) -> Optional[Any]: ...
    def recover_stale_tasks(self, stale_after_seconds: float = 300.0) -> int: ...
    def requeue_recovery_task(
        self, task_id: str, *, recovery_reference: str,
    ) -> Optional[Any]: ...

    # -- Recurring Agent schedules ------------------------------------
    def create_scheduled_task(self, record: Any) -> Any: ...
    def get_scheduled_task(
        self, schedule_id: str, tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Optional[Any]: ...
    def list_scheduled_tasks(
        self, tenant_id: Optional[str] = None, user_id: Optional[str] = None,
        statuses: Optional[list[str]] = None, limit: int = 100,
    ) -> list[Any]: ...
    def update_scheduled_task(
        self, schedule_id: str, *, status: Optional[str] = None,
        next_run_at: Optional[str] = None, last_run_at: Optional[str] = None,
        last_run_status: Optional[str] = None, last_task_id: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> bool: ...
    def pause_scheduled_task(self, schedule_id: str) -> Optional[Any]: ...
    def resume_scheduled_task(self, schedule_id: str, next_run_at: str) -> Optional[Any]: ...
    def delete_scheduled_task(self, schedule_id: str) -> bool: ...
    def claim_due_scheduled_tasks(
        self, now: str, lease_owner: str, lease_seconds: float = 60.0,
        limit: int = 20,
    ) -> list[tuple[Any, Any]]: ...
    def advance_scheduled_task(
        self, schedule_id: str, expected_next_run_at: str, next_run_at: str,
    ) -> bool: ...
    def attach_scheduled_task_run(
        self, schedule_run_id: str, task_id: str, status: str = "queued",
    ) -> bool: ...
    def update_scheduled_task_run(
        self, schedule_run_id: str, status: str, *, task_id: Optional[str] = None,
        started_at: Optional[str] = None, finished_at: Optional[str] = None,
        error: Optional[str] = None, result: Optional[dict] = None,
    ) -> bool: ...
    def list_scheduled_task_runs(
        self, schedule_id: Optional[str] = None, tenant_id: Optional[str] = None,
        user_id: Optional[str] = None, statuses: Optional[list[str]] = None,
        limit: int = 100,
    ) -> list[Any]: ...
    def get_scheduled_task_metrics(
        self, tenant_id: Optional[str] = None, user_id: Optional[str] = None,
    ) -> dict[str, Any]: ...

    # -- Operational monitoring ---------------------------------------
    # This is a read-only aggregate seam.  It deliberately returns counts
    # and bounded summaries rather than raw payloads or credentials, so the
    # same contract works for SQLite and a shared MySQL deployment.
    def get_monitoring_snapshot(
        self, *, tenant_id: Optional[str] = None, user_id: Optional[str] = None,
        stale_after_seconds: float = 300.0,
        lease_expiry_window_seconds: float = 60.0,
        tool_window_seconds: float = 3600.0,
    ) -> dict[str, Any]: ...

    # -- Agent Memory -----------------------------------------------------
    # Memory is separate from session/tool audit state.  The contract keeps
    # Runtime independent of SQLite so a future MySQL/PostgreSQL backend can
    # implement the same scoped recall semantics.
    def save_memory(self, record: Any) -> None: ...
    def search_memories(
        self, query: str, *, tenant_id: str, user_id: str,
        session_id: Optional[str] = None, kinds: Optional[list[str]] = None,
        limit: int = 10,
    ) -> list[Any]: ...
    def delete_memory(
        self, memory_id: str, *, tenant_id: str, user_id: str,
    ) -> bool: ...
    def find_active_memory(
        self, memory_key: str, *, tenant_id: str, user_id: str,
    ) -> Optional[Any]: ...
    def supersede_memory(
        self, memory_id: str, superseded_by: str, *, tenant_id: str, user_id: str,
    ) -> bool: ...

    # -- Generic Plugin package control plane ---------------------------
    # A package is an immutable declaration + file snapshot.  The release
    # pointer is tenant-scoped; activating it through this contract does not
    # imply importing or executing package code.
    def create_plugin_package(
        self, package_id: str, tenant_id: str, plugin_id: str, version: str,
        manifest: dict[str, Any], files: dict[str, dict[str, Any]],
        package_digest: str, signature_verified: bool, created_by: str,
        status: str = "validated",
    ) -> dict: ...
    def get_plugin_package(
        self, tenant_id: str, plugin_id: str, version: Optional[str] = None,
    ) -> Optional[dict]: ...
    def list_plugin_packages(
        self, tenant_id: str, plugin_id: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict]: ...
    def activate_plugin_package(
        self, tenant_id: str, plugin_id: str, version: str,
    ) -> Optional[dict]: ...
    def deactivate_plugin_package(
        self, tenant_id: str, plugin_id: str, version: str,
    ) -> Optional[dict]: ...
    def uninstall_plugin_package(
        self, tenant_id: str, plugin_id: str, version: str,
    ) -> Optional[dict]: ...

    def close(self) -> None: ...
