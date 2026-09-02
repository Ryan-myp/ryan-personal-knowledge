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

    def get_session(self, session_id: str) -> Optional[dict]: ...
    def update_session(self, session_id: str, metadata: Optional[dict] = None) -> None: ...
    def list_sessions(self, user_id: Optional[str] = None, limit: int = 50) -> list[dict]: ...

    def record_conversation_message(self, record: Any) -> None: ...
    def list_conversation_messages(
        self, session_id: str, limit: int = 200,
    ) -> list[Any]: ...

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

    def reserve_write(self, idempotency_key: str, ttl_seconds: int = 300) -> bool: ...
    def mark_write_executed(self, idempotency_key: str) -> None: ...
    def release_write(self, idempotency_key: str) -> None: ...

    def create_workflow(
        self, workflow_id: str, session_id: str, intent_type: str,
        execution_mode: str, status: str = "planned",
        metadata: Optional[dict] = None,
    ) -> None: ...
    def update_workflow(
        self, workflow_id: str, status: str, metadata: Optional[dict] = None,
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
    def get_workflow(self, workflow_id: str) -> Optional[dict]: ...
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
    ) -> list[dict]: ...

    def validate_approval(
        self, plan_fingerprint: str, token: str, session_id: str,
        user_id: str, account_id: str, tool_name: str,
    ) -> tuple[bool, str]: ...
    def create_approval(
        self, plan_fingerprint: str, token: str, session_id: str,
        user_id: str, account_id: str, tool_name: str, expires_at: str,
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
