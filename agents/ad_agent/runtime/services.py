"""Runtime service port adapter for domain Features."""

from __future__ import annotations

from typing import Any, Optional

from ..core.features import RuntimeServices as RuntimeServicesPort
from ..core.tool_registry import validate_tool_input as validate_registered_tool_input


class RuntimeServices(RuntimeServicesPort):
    """Expose generic execution primitives without leaking Runtime internals."""

    def __init__(self, runtime: Any):
        self._runtime = runtime

    @property
    def registry(self):
        return self._runtime.registry

    @property
    def plugin_registry(self):
        """Expose lifecycle metadata to trusted Runtime extensions."""
        return self._runtime.plugin_registry

    @property
    def security(self):
        return self._runtime.security

    @property
    def parameter_selection_signer(self):
        return self._runtime._parameter_selection_signer

    @property
    def input_builder(self):
        return self._runtime.input_builder

    @property
    def account_resolver(self):
        return self._runtime.account_resolver

    @property
    def session_manager(self):
        return self._runtime._session_manager

    @property
    def response_renderer(self):
        return self._runtime.response_renderer

    @property
    def execution_mode(self) -> str:
        return self._runtime.execution_mode

    @property
    def max_tool_calls(self) -> int:
        return self._runtime.max_tool_calls

    @property
    def allow_live_writes(self) -> bool:
        return self._runtime.allow_live_writes

    @property
    def live_approved_tools(self) -> set[str]:
        return self._runtime._live_approved_tools

    @property
    def write_guard(self):
        return self._runtime.write_guard

    @property
    def read_only_mode(self) -> bool:
        return self._runtime._read_only_mode

    @property
    def offline_mode(self) -> bool:
        return self._runtime.offline_mode

    @property
    def creation_blueprints(self):
        """Expose declarative creation metadata to trusted Runtime features."""
        return self._runtime.creation_blueprints

    @property
    def blueprint_cascade(self):
        return self._runtime.blueprint_cascade

    def canonical_platform(self, platform: str) -> str:
        return self._runtime._canonical_platform(platform)

    def get_registered_tool(self, tool_name: str) -> tuple[Any, Any]:
        return self._runtime._get_registered_tool(tool_name)

    def resolve_account(
        self, intent: Any, platform: str, tools: list[Any],
        fallback_account: Optional[str],
    ) -> Optional[str]:
        return self.account_resolver.resolve(intent, platform, tools, fallback_account)

    def available_accounts(self, platform: str, account_scope: Any) -> list[str]:
        return self._runtime._available_accounts_for_request(platform, account_scope)

    def validate_account(
        self, platform: str, account_id: str, is_write: bool, account_scope: Any,
    ) -> tuple[bool, str]:
        return self._runtime._validate_account_with_principal(
            platform, account_id, is_write, account_scope
        )

    def check_tool_permissions(self, tool: Any, permissions: Any) -> Optional[str]:
        return self._runtime._check_tool_permissions(tool, permissions)

    def validate_input_redline(self, value: Any) -> list[str]:
        return self._runtime.security.validate_input_redline(value)

    def validate_tool_input(
        self,
        tool: Any,
        value: dict[str, Any],
        include_provider_contract: bool = False,
    ) -> list[str]:
        schema = getattr(tool, "input_schema", None)
        if schema is None:
            return []
        return validate_registered_tool_input(
            schema,
            value,
            include_provider_contract=include_provider_contract,
        )

    def resource_id_field(self, tool: Any) -> str:
        return self._runtime._resource_id_field_for_tool(tool)

    def parent_resource_id_field(self, tool: Any) -> Optional[str]:
        return self._runtime._parent_resource_id_field_for_tool(tool)

    def heartbeat(self, workflow_id: Optional[str]) -> bool:
        return self._runtime.workflow.heartbeat(workflow_id)

    def simulate_write(self, tool: Any, value: dict[str, Any], platform: str) -> Any:
        return self._runtime._simulate_write(tool, value, platform)

    def redact(self, value: Any) -> Any:
        return self._runtime._redact_for_persistence(value)

    def persist_conversation_turn(
        self, session: Any, turn_id: str, user_input: str, reply: str,
    ) -> None:
        self._runtime.persist_conversation_turn(session, turn_id, user_input, reply)

    def finish_workflow(
        self, workflow_id: Optional[str], tool_plan: dict[str, list[Any]],
        results: list[dict[str, Any]], workflow_inputs: dict[int, dict],
        planning_errors: list[str] | None = None,
    ) -> None:
        self._runtime.workflow.finish(
            workflow_id, tool_plan, results, workflow_inputs, planning_errors
        )

    def build_resource_results(self, results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return self._runtime._build_resource_results(results)

    def execute_tool(
        self, ctx: Any, tool_name: str, value: dict[str, Any],
        request_clients: dict[str, Any] | None = None,
    ) -> Any:
        return self._runtime.tool_executor.execute(
            ctx, tool_name, value, request_clients
        )

    def persist_tool_result(
        self, session: Any, turn_id: str, tool: Any, platform: str,
        input_data: dict[str, Any], result: Any,
    ) -> None:
        self._runtime._persist_tool_result(
            session, turn_id, tool, platform, input_data, result
        )

    def is_dry_run(self) -> bool:
        return self._runtime.is_dry_run

    def workflow_lease_owner(self) -> str:
        return self._runtime._workflow_lease_owner

    def workflow_stale_after_seconds(self) -> float:
        return self._runtime.workflow_stale_after_seconds
