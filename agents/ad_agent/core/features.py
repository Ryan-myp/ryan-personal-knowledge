"""Generic Runtime feature contracts.

Features are optional domain extensions. The Runtime discovers and invokes
them through this small protocol, without importing a business workflow or
provider implementation.
"""

from __future__ import annotations

from typing import Any, Protocol


class RuntimeFeature(Protocol):
    """A domain workflow extension owned by a Skill/feature package."""

    feature_name: str

    def can_handle(self, intent: Any) -> bool:
        """Return whether this feature owns the intent/workflow."""

    def is_batch_intent(self, intent: Any) -> bool:
        """Return whether the feature owns a planning-only batch path."""

    def handles_creation_preflight(self, intent: Any) -> bool:
        """Return whether the feature owns creation preflight for the intent."""


class RuntimeServices(Protocol):
    """Generic execution services exposed to domain Features."""

    registry: Any
    security: Any
    parameter_selection_signer: Any
    input_builder: Any
    account_resolver: Any
    session_manager: Any
    response_renderer: Any
    execution_mode: str
    max_tool_calls: int
    allow_live_writes: bool
    live_approved_tools: set[str]
    write_guard: Any
    read_only_mode: bool
    offline_mode: bool

    def canonical_platform(self, platform: str) -> str: ...
    def get_registered_tool(self, tool_name: str) -> tuple[Any, Any]: ...
    def resolve_account(
        self, intent: Any, platform: str, tools: list[Any],
        fallback_account: str | None,
    ) -> str | None: ...
    def available_accounts(self, platform: str, account_scope: Any) -> list[str]: ...
    def validate_account(
        self, platform: str, account_id: str, is_write: bool, account_scope: Any,
    ) -> tuple[bool, str]: ...
    def check_tool_permissions(self, tool: Any, permissions: Any) -> str | None: ...
    def validate_input_redline(self, value: Any) -> list[str]: ...
    def validate_tool_input(
        self, tool: Any, value: dict[str, Any],
        include_provider_contract: bool = False,
    ) -> list[str]: ...
    def resource_id_field(self, tool: Any) -> str: ...
    def parent_resource_id_field(self, tool: Any) -> str | None: ...
    def heartbeat(self, workflow_id: str | None) -> bool: ...
    def simulate_write(self, tool: Any, value: dict[str, Any], platform: str) -> Any: ...
    def redact(self, value: Any) -> Any: ...
    def finish_workflow(
        self, workflow_id: str | None, tool_plan: dict[str, list[Any]],
        results: list[dict[str, Any]], workflow_inputs: dict[int, dict],
        planning_errors: list[str] | None = None,
    ) -> None: ...
    def build_resource_results(self, results: list[dict[str, Any]]) -> list[dict[str, Any]]: ...
    def execute_tool(
        self, ctx: Any, tool_name: str, value: dict[str, Any],
        request_clients: dict[str, Any] | None = None,
    ) -> Any: ...
    def persist_tool_result(
        self, session: Any, turn_id: str, tool: Any, platform: str,
        input_data: dict[str, Any], result: Any,
    ) -> None: ...
    def is_dry_run(self) -> bool: ...
    def workflow_lease_owner(self) -> str: ...
    def workflow_stale_after_seconds(self) -> float: ...
