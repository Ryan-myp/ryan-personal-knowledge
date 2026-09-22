"""
runtime/ad_application.py - Advertising application composition root

广告应用组合根。通用 Run/Turn 生命周期由
``agents.agent_harness.AgentRuntime`` 提供；这里仅组装广告场景的
Skills、Tools、策略、持久化和管理服务。
"""

from __future__ import annotations

import re
import threading
from contextvars import ContextVar
from typing import Any, Callable, Iterable, Mapping, Optional

from ..core.interfaces import (
    ToolResult,
    ToolRegistry, WriteGuard, IntentParser, IntentRouter,
    ParsedIntent, ExecutionMode, EffectReconciler,
    ToolDefinition,
)
from ..core.intent import SimpleIntentRouter
from ..core.features import RuntimeFeature
from ..core.execution_plan import ExecutionPlan
from ..core.execution_trace import ExecutionTrace, ExecutionEventCallback
from ..core.response import ResponseRenderer, ResponseSynthesizer
from ..core.tool_selector import DynamicToolSelector
from ..core.policy import RuntimePolicy, validate_policies
from agents.agent_platform.tools.policy import (
    ToolExecutionPolicy,
)
from ..domain.ad.knowledge import KnowledgeProvider
from ..domain.ad.auth import RequestPrincipal
from ..domain.ad.security import (
    PROTECTED_INPUT_FIELDS,
)
from .skill import Skill, SkillLoader
from .account_policy import AccountWhitelistValidator
from .session_context import SessionContext
from ..core.memory import MemoryManager
from .ad_runtime_policy import AdvertisingRuntimePolicy
from .ad_runtime_context import AdvertisingRuntimeContext
from .ad_run_service import AdvertisingRunService
from .ad_runtime_catalog import AdvertisingCatalogService
from .ad_runtime_controls import (
    AdvertisingRuntimeControls,
)
from .ad_runtime_lifecycle import AdvertisingLifecycleService
from .ad_runtime_presentation import AdvertisingPresentationService
from .ad_runtime_reconciliation import AdvertisingRuntimeReconciliation
from .ad_runtime_scope import AdvertisingRuntimeScope
from .ad_creation_services import AdCreationServicesMixin
from .ad_tool_source_services import AdToolSourceLifecycleMixin
from .ad_runtime_facades import (
    AdConversationRuntimeFacade,
    AdSessionRuntimeFacade,
    AdTaskRuntimeFacade,
    AdWorkflowRuntimeFacade,
)
from agents.agent_harness import MetricsSink, TurnRequest
from ..persistence.interfaces import PersistenceBackend

class SessionBusyError(RuntimeError):
    """Another Runtime instance currently owns the mutable session lease."""

# A request-scoped mode must not be read from mutable process-global state.
# The Runtime value remains the deployment default; ``run`` installs the
# effective principal/request mode in this context variable.
_execution_mode_context: ContextVar[Optional[str]] = ContextVar(
    "ad_agent_execution_mode", default=None
)
# ─── Advertising application runtime ──────────────────────────

class AdvertisingComposition(
    AdToolSourceLifecycleMixin,
    AdCreationServicesMixin,
    AdTaskRuntimeFacade,
    AdConversationRuntimeFacade,
    AdSessionRuntimeFacade,
    AdWorkflowRuntimeFacade,
):
    """
    广告应用层的单 Agent 组合根，不是通用 Run Runtime。

    通用并发、会话租约和请求生命周期由 ``AgentRuntimeKernel`` 提供；本类
    只负责把广告应用的 Skills、Tools、Tool Sources、记忆、工作流和展示
    适配器组合起来。它不是通用 Runtime，新的非广告应用不应继承或修改它。

    架构层次：
    ┌─────────────────────────────────────────┐
    │  AdvertisingComposition（广告应用组合根）             │
    │  ├─ SessionManager（会话管理）             │
    │  ├─ IntentRouter（意图路由）               │
    │  ├─ ToolRegistry（工具执行）               │
    │  └─ WriteGuard（写入保护）                 │
    └─────────────────────────────────────────┘

    通用 Run/Turn 生命周期由 ``agents.agent_harness.AgentRuntime`` 提供；
    本类只负责广告场景的依赖装配、领域策略和管理 API。

    借鉴 DAP Agent internal/core/engine/runtime.go 的应用组合设计：
    - Core 只认接口，不 import 业务
    - 业务通过 ToolSourceModule 注入
    - Tool 执行有统一的生命周期（权限→审批→幂等→执行→审计）
    """

    # These fields are configuration/credential material, not advertising
    # resource fields.  They must never be accepted inside a tool payload or
    # an ``updates`` object.  Request-scoped ``credentials=...`` remains a
    # separate, in-memory transport input and is intentionally not scanned by
    # this validator.
    PROTECTED_INPUT_FIELDS = PROTECTED_INPUT_FIELDS

    def __init__(
        self,
        registry: ToolRegistry = None,
        intent_parser: IntentParser = None,
        intent_router: IntentRouter = None,
        write_guard: WriteGuard = None,
        skill_roots: list[str] = None,
        llm_client=None,  # 可选：自定义 LLM 客户端
        # A production Agent is model-backed by definition. Explicit offline
        # tooling may opt into the schema-driven parser with ``require_llm=False``;
        # the default must never silently degrade.
        require_llm: bool = True,
        persistence_store: PersistenceBackend = None,
        whitelist_validator: AccountWhitelistValidator = None,
        read_only_mode: bool = False,
        execution_mode: str = ExecutionMode.DRY_RUN.value,
        enforce_account_scope: bool = True,
        live_approved_tools: Optional[set[str]] = None,
        allow_live_writes: bool = False,
        policies: Optional[Iterable[RuntimePolicy]] = None,
        tool_selector: Optional[DynamicToolSelector] = None,
        knowledge_provider: Optional[KnowledgeProvider] = None,
        offline_mode: bool = False,
        granted_permissions: Optional[set[str]] = None,
        max_tool_calls: int = 32,
        turn_timeout_seconds: float = 120.0,
        max_user_input_chars: int = 12_000,
        max_platform_params_bytes: int = 256_000,
        effect_reconcilers: Optional[Mapping[str, EffectReconciler]] = None,
        features: Optional[Iterable[RuntimeFeature]] = None,
        response_renderer: Optional[ResponseRenderer] = None,
        response_synthesizer: Optional[ResponseSynthesizer] = None,
        workflow_stale_after_seconds: float = 300.0,
        selection_token_secret: Optional[str] = None,
        parameter_selection_ttl_seconds: int = 600,
        max_task_workers: int = 4,
        max_task_queue: int = 32,
        task_timeout_seconds: float = 900.0,
        task_lease_seconds: float = 300.0,
        task_queue_poll_interval: float = 0.5,
        session_lease_seconds: float = 300.0,
        outbox_delivery: Optional[Callable[[Any], None]] = None,
        outbox_poll_interval: float = 0.25,
        outbox_max_attempts: int = 10,
        start_background_workers: bool = True,
        conversation_title_use_llm: bool = False,
        auto_memory_capture_enabled: bool = True,
        metrics: Optional[MetricsSink] = None,
    ):
        from .ad_application_bootstrap import AdApplicationBootstrap

        AdApplicationBootstrap.initialize(
            self,
            locals(),
            mode_context=_execution_mode_context,
            busy_error=SessionBusyError,
        )
        return


    @staticmethod
    def _validate_execution_mode(execution_mode: str) -> str:
        return AdvertisingRuntimeControls.validate_execution_mode(execution_mode)

    @property
    def execution_mode(self) -> str:
        return self._controls_service().execution_mode

    @execution_mode.setter
    def execution_mode(self, value: str) -> None:
        self._controls_service().execution_mode = value

    def set_execution_mode(
        self,
        execution_mode: str,
        *,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> None:
        return self._controls_service().set_execution_mode(
            execution_mode,
            tenant_id=tenant_id,
            user_id=user_id,
        )

    def get_execution_mode(
        self, tenant_id: Optional[str] = None, user_id: Optional[str] = None,
    ) -> str:
        return self._controls_service().get_execution_mode(tenant_id, user_id)

    def set_policies(self, policies: Optional[Iterable[RuntimePolicy]]) -> None:
        """Replace Skill-owned policies without interpreting their vocabulary."""
        self.policies = list(policies or [])
        setter = getattr(self.tool_selector, "set_policies", None)
        if callable(setter):
            setter(self.policies)

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
            intent, platform, tools, session
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
                mode_context=_execution_mode_context,
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
        self, path: str, spec: Mapping[str, Any]
    ) -> Optional[str]:
        return self._presentation_service().clarification_field_label(path, spec)

    def _clarification_field_hint(
        self, path: str, spec: Mapping[str, Any]
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

    def register_tool(
        self,
        definition: ToolDefinition,
        executor: Any,
        *,
        source_id: str = "local",
    ) -> None:
        return self._catalog_service().register_tool(
            definition, executor, source_id=source_id
        )

    def register_tool_source(self, source: Any) -> list[str]:
        return self._catalog_service().register_tool_source(source)

    def unregister_tool_source(self, source_id: str) -> list[str]:
        return self._catalog_service().unregister_tool_source(source_id)

    @staticmethod
    def _canonical_platform(platform: str) -> str:
        return AdvertisingCatalogService.canonical_platform(platform)

    def _resolve_platform_identifier(self, platform: str) -> str:
        return self._catalog_service().resolve_platform_identifier(platform)

    @property
    def persistence_store(self):
        """Expose the persistence abstraction to management services."""
        return self._session_manager.store if self._session_manager else None

    def close(self, wait: bool = False) -> None:
        return self._controls_service().close(wait=wait)

    def get_readiness(self) -> dict[str, Any]:
        return self._controls_service().readiness()

    @staticmethod
    def _default_outbox_delivery(event: Any) -> None:
        return AdvertisingRuntimeControls.default_outbox_delivery(event)

    @property
    def memory_manager(self) -> Optional[MemoryManager]:
        return self._controls_service().memory_manager

    def set_auto_memory_capture_enabled(self, enabled: bool) -> None:
        return self._controls_service().set_auto_memory_capture_enabled(enabled)

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

    def list_plugins(self, tenant_id: Optional[str] = None) -> list[dict[str, Any]]:
        return self._lifecycle_service().list_plugins(tenant_id)

    def load_managed_skill(self, skill_dir: str, tenant_id: str = "default") -> bool:
        return self._lifecycle_service().load_managed_skill(
            skill_dir, tenant_id=tenant_id
        )

    def unload_managed_skill(self, skill_name: str, tenant_id: str = "default") -> bool:
        return self._lifecycle_service().unload_managed_skill(
            skill_name, tenant_id=tenant_id
        )

    def get_managed_skills(self, tenant_id: Optional[str] = None) -> dict[str, Skill]:
        return self._lifecycle_service().get_managed_skills(tenant_id)

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
        self, user_input: str, intent: ParsedIntent,
        available_tools: list, tenant_id: str,
    ) -> dict:
        return self._context_service().optimize_tool_selection(
            user_input, intent, available_tools, tenant_id
        )

    def _build_prior_tool_results_context(
        self, session: "SessionContext", max_results: int = 8, max_chars: int = 4000
    ) -> str:
        return self._context_service().prior_tool_results(
            session, max_results=max_results, max_chars=max_chars
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
        self, user_input: str, platform_params: Optional[dict],
    ) -> Optional[str]:
        return self._policy_service().validate_request_limits(
            user_input, platform_params
        )

    def _policy_service(self) -> AdvertisingRuntimePolicy:
        """Return the app policy, including for contract-only ``__new__`` tests."""
        policy = getattr(self, "runtime_policy", None)
        if policy is None:
            policy = AdvertisingRuntimePolicy(self)
            self.runtime_policy = policy
        return policy

    @staticmethod
    def _check_turn_budget(deadline: float, tool_call_count: int, max_tool_calls: int = 32) -> Optional[str]:
        return AdvertisingRuntimePolicy.check_turn_budget(
            deadline, tool_call_count, max_tool_calls
        )

    def _check_tool_permissions(
        self,
        tool_def: Any,
        granted_permissions: Optional[set[str] | frozenset[str]] = None,
    ) -> Optional[str]:
        return self._policy_service().check_tool_permissions(
            tool_def, granted_permissions
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

    def inject_llm(self, llm_client) -> None:
        return self._controls_service().inject_llm(llm_client)

    def assert_llm_ready(self) -> None:
        return self._controls_service().assert_llm_ready()

    def enable_read_only_mode(self) -> None:
        return self._controls_service().enable_read_only_mode()

    def _filter_write_tools(self) -> None:
        return self._controls_service().filter_write_tools()

    # ─── Tool Source 注册 ───────────────────────────────────────


    def _validate_account_for_tool(self, platform: str, account_id: str, is_write: bool) -> tuple[bool, str]:
        return self._policy_service().validate_account_for_tool(
            platform, account_id, is_write
        )

    @staticmethod
    def _principal_accounts(
        platform: str,
        account_scope: Optional[Mapping[str, Any]],
    ) -> Optional[set[str]]:
        return AdvertisingRuntimePolicy.principal_accounts(
            platform, account_scope
        )

    def _validate_account_with_principal(
        self,
        platform: str,
        account_id: str,
        is_write: bool,
        account_scope: Optional[Mapping[str, Any]],
    ) -> tuple[bool, str]:
        return self._policy_service().validate_account_with_principal(
            platform, account_id, is_write, account_scope
        )

    def _available_accounts_for_request(
        self,
        platform: str,
        account_scope: Optional[Mapping[str, Any]],
    ) -> list[str]:
        return self._policy_service().available_accounts(platform, account_scope)

    def _simulate_write(self, tool_def: Any, input_data: dict, platform: str) -> ToolResult:
        return self._policy_service().simulate_write(tool_def, input_data, platform)

    @classmethod
    def _resource_id_field_for_tool(cls, tool_def: Any) -> Optional[str]:
        return AdvertisingRuntimePolicy.resource_id_field(tool_def)

    @staticmethod
    def _parent_resource_id_field_for_tool(tool_def: Any) -> Optional[str]:
        return AdvertisingRuntimePolicy.parent_resource_id_field(tool_def)

    @classmethod
    def _parent_resource_id_for_tool(
        cls, tool_def: Any, input_data: Optional[dict[str, Any]] = None,
    ) -> Optional[str]:
        return AdvertisingRuntimePolicy.parent_resource_id_for_tool(tool_def, input_data)

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
        self, session: "SessionContext", turn_id: str,
        user_input: str, reply: str,
        execution_trace: Optional[ExecutionTrace] = None,
        ui: Optional[Mapping[str, Any]] = None,
    ) -> None:
        self.persistence_services.persist_conversation_turn(
            session, turn_id, user_input, reply,
            execution_trace=execution_trace, ui=ui,
        )

    def _persist_tool_result(
        self, session: "SessionContext", turn_id: str, tool_def: Any,
        platform: str, input_data: dict, result: ToolResult,
        *, started_at: Optional[str] = None, ended_at: Optional[str] = None,
    ) -> None:
        self.persistence_services.persist_tool_result(
            session, turn_id, tool_def, platform, input_data, result,
            started_at=started_at, ended_at=ended_at,
        )



    def _resolve_readback_definition(self, write_tool: str):
        return self._reconciliation_service().resolve_readback_definition(
            write_tool
        )

    # ─── 主循环入口 ────────────────────────────────────────────

    def _render_response(
        self,
        user_input: str,
        intent: Any,
        results: list[dict[str, Any]],
        needs_confirmation: bool,
        analysis: Optional[dict[str, Any]] = None,
        session: Optional["SessionContext"] = None,
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
        self, session: Optional["SessionContext"] = None
    ) -> dict[str, Any]:
        return self._context_service().from_session_metadata(session)

    def run(
        self,
        user_input: str,
        session_id: str = None,
        user_id: str = "anonymous",
        account_id: str = None,
        credentials: dict = None,
        platform_params: dict = None,
        confirmed: bool = False,
        confirmation_payload: Optional[dict] = None,
        creation_blueprint_id: Optional[str] = None,
        creation_blueprint_version: Optional[str] = None,
        principal: Optional[RequestPrincipal] = None,
        tenant_id: Optional[str] = None,
        cancellation_event: Optional[threading.Event] = None,
        event_callback: Optional[ExecutionEventCallback] = None,
        execution_mode: Optional[str] = None,
        task_id: Optional[str] = None,
    ) -> dict:
        return self._run_service().run(
            user_input=user_input,
            session_id=session_id,
            user_id=user_id,
            account_id=account_id,
            credentials=credentials,
            platform_params=platform_params,
            confirmed=confirmed,
            confirmation_payload=confirmation_payload,
            creation_blueprint_id=creation_blueprint_id,
            creation_blueprint_version=creation_blueprint_version,
            principal=principal,
            tenant_id=tenant_id,
            cancellation_event=cancellation_event,
            event_callback=event_callback,
            execution_mode=execution_mode,
            task_id=task_id,
        )

    def _run_service(self) -> AdvertisingRunService:
        service = getattr(self, "run_service", None)
        if service is None:
            service = AdvertisingRunService(self)
            self.run_service = service
        return service

    def _ensure_kernel_session(self, request: TurnRequest) -> "SessionContext":
        """Interpret the opaque Kernel context at the advertising boundary."""
        context = request.context if isinstance(request.context, Mapping) else {}
        return self._ensure_session(
            str(request.session_id), request.user_id, context.get("account_id"),
            context.get("credentials"), tenant_id=request.tenant_id,
        )

    def _refresh_kernel_session(self, request: TurnRequest) -> "SessionContext":
        """Reload the application session after the generic lease is held."""
        context = request.context if isinstance(request.context, Mapping) else {}
        return self._refresh_session_for_turn(
            str(request.session_id), request.user_id, context.get("account_id"),
            context.get("credentials"), tenant_id=request.tenant_id,
        )
