"""Generic Runtime extension contracts.

The Core package owns the extension seam, not an application's domain model.
Feature implementations may expose richer methods, but those methods belong
to the embedding application and are intentionally resolved by capability
inspection there.  Keeping the Core protocol small prevents a new business
feature from becoming a mandatory Runtime service.
"""

from __future__ import annotations

from typing import Any, Protocol


class RuntimeFeature(Protocol):
    """A domain extension owned by a Skill/feature package.

    ``can_handle`` is the only execution hook the generic Runtime needs.  A
    feature may publish optional application-specific hooks (for example a
    control-plane handler or a preflight operation), but those are not part of
    the Core contract and must not be added here.
    """

    feature_name: str

    def intent_descriptors(self) -> dict[str, dict[str, Any]]:
        """Return Feature-owned intent language metadata, if any."""
        ...

    def can_handle(self, intent: Any) -> bool:
        """Return whether this feature owns the intent/workflow."""

class RuntimeExecutionServices(Protocol):
    """Provider- and business-neutral execution port.

    This port contains only services needed by generic Tool execution and
    workflow persistence.  Account selection, business preflight, schedules,
    creation blueprints and other application concerns stay on the embedding
    Runtime's private feature adapter instead of expanding this contract.
    """

    registry: Any
    plugin_registry: Any
    security: Any
    parameter_selection_signer: Any
    input_builder: Any
    session_manager: Any
    response_renderer: Any
    execution_mode: str
    max_tool_calls: int
    allow_live_writes: bool
    live_approved_tools: set[str]
    write_guard: Any
    read_only_mode: bool
    offline_mode: bool

    def normalize_namespace(self, value: str) -> str: ...
    def get_registered_tool(self, tool_name: str) -> tuple[Any, Any]: ...
    def check_tool_permissions(self, tool: Any, permissions: Any) -> str | None: ...
    def validate_input_redline(self, value: Any) -> list[str]: ...
    def validate_tool_input(
        self, tool: Any, value: dict[str, Any],
        include_provider_contract: bool = False,
    ) -> list[str]: ...
    def resource_id_field(self, tool: Any) -> str | None: ...
    def parent_resource_id_field(self, tool: Any) -> str | None: ...
    def heartbeat(self, workflow_id: str | None) -> bool: ...
    def simulate_write(self, tool: Any, value: dict[str, Any], platform: str) -> Any: ...
    def redact(self, value: Any) -> Any: ...
    def persist_conversation_turn(
        self, session: Any, turn_id: str, user_input: str, reply: str,
    ) -> None: ...
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
