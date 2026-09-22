"""Internal callbacks used to connect the application to generic services."""

from __future__ import annotations

from typing import Any, Mapping, Optional

from agents.agent_harness import TurnRequest

from ..core.execution_trace import ExecutionTrace
from ..core.features import RuntimeFeature
from ..core.interfaces import ExecutionMode, ParsedIntent, ToolResult
from ..core.policy import validate_policies
from .ad_application_contracts import execution_mode_context
from .ad_run_service import AdvertisingRunService
from .ad_runtime_catalog import AdvertisingCatalogService
from .ad_runtime_context import AdvertisingRuntimeContext
from .ad_runtime_controls import AdvertisingRuntimeControls
from .ad_runtime_lifecycle import AdvertisingLifecycleService
from .ad_runtime_presentation import AdvertisingPresentationService
from .ad_runtime_reconciliation import AdvertisingRuntimeReconciliation
from .ad_runtime_policy import AdvertisingRuntimePolicy
from .ad_runtime_scope import AdvertisingRuntimeScope
from .session_context import SessionContext


class AdApplicationHooksMixin:
    """Non-public application hooks consumed by the assembled runtime graph."""

    def _feature_for_intent(self, intent: Any) -> Optional[RuntimeFeature]:
        return self._controls_service().feature_for_intent(intent)

    def _resolve_workflow_item_scope(
        self,
        intent: Any,
        platform: str,
        tools: list[Any],
        session: Any,
    ) -> Optional[str]:
        return self._scope_service().resolve_item(
            intent,
            platform,
            tools,
            session,
        )

    def _resolve_workflow_result_scope(
        self,
        intent: Any,
        platform: str,
        tools: list[Any],
        session: Any,
        item: Mapping[str, Any],
        input_data: Mapping[str, Any],
        output_data: Mapping[str, Any],
    ) -> Optional[str]:
        return self._scope_service().resolve_result(
            intent,
            platform,
            tools,
            session,
            item,
            input_data,
            output_data,
        )

    def _presentation_service(self) -> AdvertisingPresentationService:
        service = getattr(self, "presentation_service", None)
        if service is None:
            service = AdvertisingPresentationService(self)
            self.presentation_service = service
        return service

    def _controls_service(self) -> AdvertisingRuntimeControls:
        service = getattr(self, "controls_service", None)
        if service is None:
            service = AdvertisingRuntimeControls(
                self,
                mode_context=execution_mode_context,
            )
            self.controls_service = service
        return service

    def _scope_service(self) -> AdvertisingRuntimeScope:
        service = getattr(self, "scope_service", None)
        if service is None:
            service = AdvertisingRuntimeScope(self)
            self.scope_service = service
        return service

    def _reconciliation_service(self) -> AdvertisingRuntimeReconciliation:
        service = getattr(self, "reconciliation_service", None)
        if service is None:
            service = AdvertisingRuntimeReconciliation(self)
            self.reconciliation_service = service
        return service

    def _clarification_field_label(
        self,
        path: str,
        spec: Mapping[str, Any],
    ) -> Optional[str]:
        return self._presentation_service().clarification_field_label(path, spec)

    def _clarification_field_hint(
        self,
        path: str,
        spec: Mapping[str, Any],
    ) -> Optional[str]:
        return self._presentation_service().clarification_field_hint(path, spec)

    def _catalog_service(self) -> AdvertisingCatalogService:
        service = getattr(self, "catalog_service", None)
        if service is None:
            service = AdvertisingCatalogService(self)
            self.catalog_service = service
        return service

    def _refresh_parser_catalog(self) -> None:
        return self._catalog_service().refresh_parser_catalog()

    def _on_generic_tool_catalog_changed(self) -> None:
        return self._catalog_service().on_tool_catalog_changed()

    @staticmethod
    def _canonical_platform(platform: str) -> str:
        return AdvertisingCatalogService.canonical_platform(platform)

    def _resolve_platform_identifier(self, platform: str) -> str:
        return self._catalog_service().resolve_platform_identifier(platform)

    @staticmethod
    def _default_outbox_delivery(event: Any) -> None:
        return AdvertisingRuntimeControls.default_outbox_delivery(event)

    def _register_builtin_plugin(
        self,
        plugin_id: str,
        contribution: Any,
        kinds: tuple[str, ...] | list[str],
        *,
        version: str = "1.0.0",
        description: str = "",
        replace: bool = False,
    ) -> None:
        return self._lifecycle_service().register_builtin_plugin(
            plugin_id,
            contribution,
            kinds,
            version=version,
            description=description,
            replace=replace,
        )

    def _lifecycle_service(self) -> AdvertisingLifecycleService:
        service = getattr(self, "lifecycle_service", None)
        if service is None:
            service = AdvertisingLifecycleService(self)
            self.lifecycle_service = service
        return service

    def _build_skill_context(
        self,
        user_input: str,
        available_tools: list,
        intent_type: Optional[str],
        tenant_id: str,
    ) -> dict:
        return self._context_service().build_skill_context(
            user_input,
            available_tools,
            intent_type,
            tenant_id,
        )

    def _optimize_tool_selection(
        self,
        user_input: str,
        intent: ParsedIntent,
        available_tools: list,
        tenant_id: str,
    ) -> dict:
        return self._context_service().optimize_tool_selection(
            user_input,
            intent,
            available_tools,
            tenant_id,
        )

    def _build_prior_tool_results_context(
        self,
        session: SessionContext,
        max_results: int = 8,
        max_chars: int = 4000,
    ) -> str:
        return self._context_service().prior_tool_results(
            session,
            max_results=max_results,
            max_chars=max_chars,
        )

    def _context_service(self) -> AdvertisingRuntimeContext:
        context = getattr(self, "runtime_context", None)
        if context is None:
            context = AdvertisingRuntimeContext(self)
            self.runtime_context = context
        return context

    def _validate_policies(self, intent: ParsedIntent) -> list[str]:
        """Run Skill-owned policies through the generic policy contract."""
        return validate_policies(self.policies, intent)

    @property
    def is_dry_run(self) -> bool:
        return self.execution_mode == ExecutionMode.DRY_RUN.value

    def _validate_request_limits(
        self,
        user_input: str,
        platform_params: Optional[dict],
    ) -> Optional[str]:
        return self._policy_service().validate_request_limits(
            user_input,
            platform_params,
        )

    def _policy_service(self) -> AdvertisingRuntimePolicy:
        """Return the app policy, including for contract-only ``__new__`` tests."""
        policy = getattr(self, "runtime_policy", None)
        if policy is None:
            policy = AdvertisingRuntimePolicy(self)
            self.runtime_policy = policy
        return policy

    @staticmethod
    def _check_turn_budget(
        deadline: float,
        tool_call_count: int,
        max_tool_calls: int = 32,
    ) -> Optional[str]:
        return AdvertisingRuntimePolicy.check_turn_budget(
            deadline,
            tool_call_count,
            max_tool_calls,
        )

    def _check_tool_permissions(
        self,
        tool_def: Any,
        granted_permissions: Optional[set[str] | frozenset[str]] = None,
    ) -> Optional[str]:
        return self._policy_service().check_tool_permissions(
            tool_def,
            granted_permissions,
        )

    def _evaluate_tool_policy(
        self,
        tool_def: Any,
        *,
        granted_permissions: Optional[set[str] | frozenset[str]] = None,
        scope: Any = None,
        principal: Any = None,
        confirmed: bool = False,
        require_confirmation: bool = True,
    ) -> Any:
        return self._policy_service().evaluate_tool_policy(
            tool_def,
            granted_permissions=granted_permissions,
            scope=scope,
            principal=principal,
            confirmed=confirmed,
            require_confirmation=require_confirmation,
        )

    def _filter_write_tools(self) -> None:
        return self._controls_service().filter_write_tools()

    def _validate_account_for_tool(
        self,
        platform: str,
        account_id: str,
        is_write: bool,
    ) -> tuple[bool, str]:
        return self._policy_service().validate_account_for_tool(
            platform,
            account_id,
            is_write,
        )

    @staticmethod
    def _principal_accounts(
        platform: str,
        account_scope: Optional[Mapping[str, Any]],
    ) -> Optional[set[str]]:
        return AdvertisingRuntimePolicy.principal_accounts(platform, account_scope)

    def _validate_account_with_principal(
        self,
        platform: str,
        account_id: str,
        is_write: bool,
        account_scope: Optional[Mapping[str, Any]],
    ) -> tuple[bool, str]:
        return self._policy_service().validate_account_with_principal(
            platform,
            account_id,
            is_write,
            account_scope,
        )

    def _available_accounts_for_request(
        self,
        platform: str,
        account_scope: Optional[Mapping[str, Any]],
    ) -> list[str]:
        return self._policy_service().available_accounts(platform, account_scope)

    def _simulate_write(
        self,
        tool_def: Any,
        input_data: dict,
        platform: str,
    ) -> ToolResult:
        return self._policy_service().simulate_write(tool_def, input_data, platform)

    @classmethod
    def _resource_id_field_for_tool(cls, tool_def: Any) -> Optional[str]:
        return AdvertisingRuntimePolicy.resource_id_field(tool_def)

    @staticmethod
    def _parent_resource_id_field_for_tool(tool_def: Any) -> Optional[str]:
        return AdvertisingRuntimePolicy.parent_resource_id_field(tool_def)

    @classmethod
    def _parent_resource_id_for_tool(
        cls,
        tool_def: Any,
        input_data: Optional[dict[str, Any]] = None,
    ) -> Optional[str]:
        return AdvertisingRuntimePolicy.parent_resource_id_for_tool(
            tool_def,
            input_data,
        )

    @classmethod
    def _build_resource_results(cls, results: list[dict]) -> list[dict]:
        return AdvertisingRuntimePolicy.build_resource_results(results)

    @staticmethod
    def _freeze_credentials(value: Any) -> Any:
        return AdvertisingRuntimeControls.freeze_credentials(value)

    @staticmethod
    def _redact_for_persistence(value: Any) -> Any:
        return AdvertisingRuntimeControls.redact_for_persistence(value)

    def persist_conversation_turn(
        self,
        session: SessionContext,
        turn_id: str,
        user_input: str,
        reply: str,
        execution_trace: Optional[ExecutionTrace] = None,
        ui: Optional[Mapping[str, Any]] = None,
    ) -> None:
        self.persistence_services.persist_conversation_turn(
            session,
            turn_id,
            user_input,
            reply,
            execution_trace=execution_trace,
            ui=ui,
        )

    def _persist_tool_result(
        self,
        session: SessionContext,
        turn_id: str,
        tool_def: Any,
        platform: str,
        input_data: dict,
        result: ToolResult,
        *,
        started_at: Optional[str] = None,
        ended_at: Optional[str] = None,
    ) -> None:
        self.persistence_services.persist_tool_result(
            session,
            turn_id,
            tool_def,
            platform,
            input_data,
            result,
            started_at=started_at,
            ended_at=ended_at,
        )

    def _resolve_readback_definition(self, write_tool: str):
        return self._reconciliation_service().resolve_readback_definition(write_tool)

    def _render_response(
        self,
        user_input: str,
        intent: Any,
        results: list[dict[str, Any]],
        needs_confirmation: bool,
        analysis: Optional[dict[str, Any]] = None,
        session: Optional[SessionContext] = None,
        fallback_reply: Optional[str] = None,
    ) -> tuple[str, str]:
        return self._presentation_service().render_response(
            user_input,
            intent,
            results,
            needs_confirmation,
            analysis=analysis,
            session=session,
            fallback_reply=fallback_reply,
        )

    def _build_skill_context_from_metadata(
        self,
        session: Optional[SessionContext] = None,
    ) -> dict[str, Any]:
        return self._context_service().from_session_metadata(session)

    def _run_service(self) -> AdvertisingRunService:
        service = getattr(self, "run_service", None)
        if service is None:
            service = AdvertisingRunService(self)
            self.run_service = service
        return service

    def _ensure_kernel_session(self, request: TurnRequest) -> SessionContext:
        """Interpret the opaque Kernel context at the advertising boundary."""
        context = request.context if isinstance(request.context, Mapping) else {}
        return self._ensure_session(
            str(request.session_id),
            request.user_id,
            context.get("account_id"),
            context.get("credentials"),
            tenant_id=request.tenant_id,
        )

    def _refresh_kernel_session(self, request: TurnRequest) -> SessionContext:
        """Reload the application session after the generic lease is held."""
        context = request.context if isinstance(request.context, Mapping) else {}
        return self._refresh_session_for_turn(
            str(request.session_id),
            request.user_id,
            context.get("account_id"),
            context.get("credentials"),
            tenant_id=request.tenant_id,
        )


__all__ = ["AdApplicationHooksMixin"]
