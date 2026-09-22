"""
runtime/ad_runtime.py - Advertising application runtime composition

借鉴 DAP Agent internal/core/engine/runtime.go
核心职责：
1. 管理 Session 生命周期
2. 处理用户输入 → LLM → ToolCall → 执行 → 返回结果
3. 多平台 Skill 工具的统一调度
4. 跨 Skill 上下文传递
"""

from __future__ import annotations

import time
import os
import re
import threading
import logging
from contextvars import ContextVar
from types import MappingProxyType
from typing import Any, Callable, Iterable, Mapping, Optional

from ..core.interfaces import (
    ToolResult, ToolSourceModule,
    ToolRegistry, WriteGuard, IntentParser, IntentRouter,
    ParsedIntent, ToolEffect, ExecutionMode, EffectReconciler,
    ToolDefinition,
)
from ..core.intent import LLMIntentParser, SimpleIntentRouter
from ..core.features import RuntimeFeature
from ..core.execution_plan import ExecutionPlan
from ..core.execution_trace import ExecutionTrace, ExecutionEventCallback
from ..core.response import ResponseRenderer, ResponseSynthesizer
from ..domain.ad.response import LLMResponseSynthesizer
from ..features.factory import feature_for_intent
from ..core.tool_selector import DynamicToolSelector
from ..core.policy import RuntimePolicy, validate_policies
from agents.agent_platform.tools.policy import (
    ToolExecutionPolicy,
)
from ..core.memory import MemoryManager
from ..domain.ad.knowledge import KnowledgeProvider
from ..domain.ad.auth import RequestPrincipal
from ..domain.ad.security import (
    ACCOUNT_SCOPE_FIELDS,
    PROTECTED_INPUT_FIELDS,
)
from .skill import Skill, SkillLoader
from .account_policy import AccountWhitelistValidator
from .session_context import SessionContext
from .security import RuntimeSecurity
from .ad_runtime_policy import AdvertisingRuntimePolicy
from .ad_runtime_context import AdvertisingRuntimeContext
from .ad_run_service import AdvertisingRunService
from .ad_runtime_catalog import AdvertisingCatalogService
from .ad_runtime_lifecycle import AdvertisingLifecycleService
from .ad_runtime_presentation import AdvertisingPresentationService
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

logger = logging.getLogger(__name__)


class SessionBusyError(RuntimeError):
    """Another Runtime instance currently owns the mutable session lease."""

# A request-scoped mode must not be read from mutable process-global state.
# The Runtime value remains the deployment default; ``run`` installs the
# effective principal/request mode in this context variable.
_execution_mode_context: ContextVar[Optional[str]] = ContextVar(
    "ad_agent_execution_mode", default=None
)
_EXECUTION_MODE_CACHE_TTL_SECONDS = 5.0
_EXECUTION_MODE_CACHE_MAX_ENTRIES = 1024
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
    广告应用层的单 Agent 组合根。

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

    借鉴 DAP Agent internal/core/engine/runtime.go 的核心设计：
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
        from .ad_runtime_bootstrap import AdRuntimeBootstrap

        AdRuntimeBootstrap.initialize(
            self,
            locals(),
            mode_context=_execution_mode_context,
            busy_error=SessionBusyError,
        )
        return


    @staticmethod
    def _validate_execution_mode(execution_mode: str) -> str:
        mode = str(execution_mode or "").strip().lower()
        if mode not in {item.value for item in ExecutionMode}:
            raise ValueError(f"Unsupported execution_mode: {execution_mode}")
        return mode

    @property
    def execution_mode(self) -> str:
        """Return the request mode, falling back to the deployment default."""
        return _execution_mode_context.get() or self._execution_mode

    @execution_mode.setter
    def execution_mode(self, value: str) -> None:
        self._execution_mode = self._validate_execution_mode(value)

    def set_execution_mode(
        self,
        execution_mode: str,
        *,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> None:
        """Set a deployment default or an isolated principal override.

        The one-argument form remains available to local/CLI callers. HTTP
        callers should provide both identity dimensions to avoid changing the
        mode observed by another principal in the same process.
        """
        mode = self._validate_execution_mode(execution_mode)
        tenant = str(tenant_id or "").strip()
        user = str(user_id or "").strip()
        with self._execution_mode_lock:
            if tenant and user:
                self._cache_execution_mode((tenant, user), mode)
                store = self._persistence_store
                persist = getattr(store, "set_execution_mode", None)
                if callable(persist):
                    try:
                        persist(tenant, user, mode)
                    except Exception:
                        # A preference write must never turn a safe mode
                        # switch into an unsafe fallback or mutate process
                        # state for another principal. Keep the in-memory
                        # value for this process and expose the backend issue
                        # via structured logging for later observability.
                        logger.warning(
                            "Failed to persist execution mode preference",
                            extra={"tenant_id": tenant, "user_id": user},
                            exc_info=True,
                        )
            else:
                self._execution_mode = mode

    def _cache_execution_mode(self, key: tuple[str, str], mode: str) -> None:
        """Cache a mode briefly without allowing principal cardinality leaks."""
        self._execution_mode_cache.pop(key, None)
        self._execution_mode_cache[key] = (
            mode, time.monotonic() + _EXECUTION_MODE_CACHE_TTL_SECONDS
        )
        while len(self._execution_mode_cache) > _EXECUTION_MODE_CACHE_MAX_ENTRIES:
            self._execution_mode_cache.popitem(last=False)

    def get_execution_mode(
        self, tenant_id: Optional[str] = None, user_id: Optional[str] = None,
    ) -> str:
        """Resolve a principal-scoped override over the deployment default."""
        tenant = str(tenant_id or "").strip()
        user = str(user_id or "").strip()
        with self._execution_mode_lock:
            if tenant and user:
                key = (tenant, user)
                cached = self._execution_mode_cache.get(key)
                if cached:
                    cached_mode, expires_at = cached
                    if time.monotonic() < expires_at:
                        self._execution_mode_cache.move_to_end(key)
                        return cached_mode
                    self._execution_mode_cache.pop(key, None)
                persisted = getattr(self._persistence_store, "get_execution_mode", None)
                if callable(persisted):
                    try:
                        stored = persisted(tenant, user)
                        if stored is not None:
                            mode = self._validate_execution_mode(stored)
                            self._cache_execution_mode(key, mode)
                            return mode
                    except ValueError:
                        logger.warning(
                            "Ignoring invalid persisted execution mode preference",
                            extra={"tenant_id": tenant, "user_id": user},
                        )
                    except Exception:
                        logger.warning(
                            "Failed to load execution mode preference",
                            extra={"tenant_id": tenant, "user_id": user},
                            exc_info=True,
                        )
                return self._execution_mode
            return self._execution_mode

    def set_policies(self, policies: Optional[Iterable[RuntimePolicy]]) -> None:
        """Replace Skill-owned policies without interpreting their vocabulary."""
        self.policies = list(policies or [])
        setter = getattr(self.tool_selector, "set_policies", None)
        if callable(setter):
            setter(self.policies)

    def _feature_for_intent(self, intent: Any) -> Optional[RuntimeFeature]:
        """Resolve an optional domain feature through its generic contract."""
        return feature_for_intent(self.features, intent)

    def _resolve_workflow_item_scope(
        self,
        intent: Any,
        platform: str,
        tools: list[Any],
        session: Any,
    ) -> Optional[str]:
        """Resolve the advertising scope at the application boundary.

        ``WorkflowCoordinator`` persists an opaque scope returned by this
        callback.  Account semantics therefore stay in the advertising
        composition root instead of leaking into generic workflow
        infrastructure.
        """
        if not tools:
            return None
        tool = tools[0]
        fallback = None
        if not getattr(tool, "is_write_tool", False):
            fallback = (
                getattr(getattr(session, "ctx", None), "account_id", None)
                if len(getattr(intent, "namespaces", []) or []) == 1 else None
            )
        return self.account_resolver.resolve(intent, platform, tools, fallback)

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
        """Resolve persisted workflow scope at the advertising boundary."""
        for source in (item, output_data, input_data):
            for field in ACCOUNT_SCOPE_FIELDS:
                value = source.get(field) if isinstance(source, Mapping) else None
                if value not in (None, ""):
                    return str(value)
        return self._resolve_workflow_item_scope(intent, platform, tools, session)

    def _presentation_service(self) -> AdvertisingPresentationService:
        service = getattr(self, "presentation_service", None)
        if service is None:
            service = AdvertisingPresentationService(self)
            self.presentation_service = service
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
        """Stop durable workers through the infrastructure supervisor."""
        self.supervisor.close(wait=wait)

    def get_readiness(self) -> dict[str, Any]:
        """Aggregate application readiness without making Provider requests.

        The Runtime remains the advertising composition root, while the
        supervisor contributes only generic worker/backend lifecycle state.
        This method is the application-facing readiness contract used by the
        HTTP adapter; it is intentionally separate from liveness.
        """
        try:
            tool_count = len(self.registry.list_all())
        except Exception:
            tool_count = 0
        model_ready = not self.require_llm or self._llm is not None
        supervisor_health = self.supervisor.health()
        checks = {
            "runtime": True,
            "llm": model_ready,
            "tool_registry": tool_count > 0,
            "persistence": (
                self._persistence_store is None
                or supervisor_health.get("backend", {}).get("status") == "healthy"
            ),
            "workers": (
                self._persistence_store is None
                or supervisor_health.get("status") == "healthy"
                or not self.supervisor.task_executor
            ),
        }
        ready = all(checks.values())
        return {
            "status": "ready" if ready else "not_ready",
            "checks": checks,
            "tool_count": tool_count,
            "supervisor": supervisor_health,
        }

    @staticmethod
    def _default_outbox_delivery(event: Any) -> None:
        """Consume events safely until an application sink is configured.

        The Runtime owns lifecycle, while SSE/Webhook/metrics integrations are
        supplied through ``outbox_delivery``.  Do not log the event payload:
        workflow data may contain user-provided values.
        """
        logger.info(
            "Outbox event consumed by default sink: event_id=%s run_id=%s type=%s",
            getattr(event, "event_id", ""),
            getattr(event, "run_id", ""),
            getattr(event, "event_type", ""),
        )

    @property
    def memory_manager(self) -> Optional[MemoryManager]:
        """Expose the optional, provider-neutral Agent Memory service."""
        return self._memory_manager

    def set_auto_memory_capture_enabled(self, enabled: bool) -> None:
        """Toggle automatic event capture without disabling explicit memory."""
        self.auto_memory_capture_enabled = bool(enabled)
        manager = self._memory_manager
        if manager is not None:
            manager.set_auto_capture_enabled(bool(enabled))

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
        """注入 LLM 客户端"""
        self._llm = llm_client
        if self.response_synthesizer is None and llm_client is not None:
            self.response_synthesizer = LLMResponseSynthesizer(
                profile=self.agent_profile
            )
        if isinstance(self.intent_parser, LLMIntentParser):
            self.intent_parser.inject_llm(llm_client)

    def assert_llm_ready(self) -> None:
        """Fail fast when a production Runtime has no model-backed parser."""
        if (
            self.require_llm
            and isinstance(self.intent_parser, LLMIntentParser)
            and self._llm is None
        ):
            raise RuntimeError(
                "LLM client is required; configure the model before starting the Agent"
            )

    def enable_read_only_mode(self) -> None:
        """
        启用只读模式：从注册表中移除所有 WRITE 类工具。
        调用此方法后，所有写操作工具将不可用。
        """
        self._read_only_mode = True

        self._filter_write_tools()

    def _filter_write_tools(self) -> None:
        """Remove write tools from the registry at every registration seam."""

        # 收集所有 WRITE 类工具名称
        write_tools = []
        for tool_def in self.registry.list_all():
            if tool_def.effect_class in (ToolEffect.WRITE, ToolEffect.EXTERNAL_WRITE):
                write_tools.append(tool_def.name)

        # 从注册表中移除
        for name in write_tools:
            try:
                self.registry.unregister(name)
                logger.debug(f"只读模式：已移除写工具 {name}")
            except Exception as e:
                logger.warning(f"移除工具 {name} 失败: {e}")

        logger.info(f"✅ 只读模式已启用，已过滤 {len(write_tools)} 个写工具")

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
        """Make credentials visible to handlers as a read-only snapshot."""
        if isinstance(value, dict):
            return MappingProxyType({
                    key: AdvertisingComposition._freeze_credentials(item)
                for key, item in value.items()
            })
        if isinstance(value, list):
            return tuple(AdvertisingComposition._freeze_credentials(item) for item in value)
        return value

    @staticmethod
    def _redact_for_persistence(value: Any) -> Any:
        return RuntimeSecurity.redact_for_persistence(value)

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
        """Find the read Tool matching a write Tool's resource metadata."""
        try:
            write_definition, _handler = self._get_registered_tool(write_tool)
        except KeyError:
            return None
        platform = self._canonical_platform(write_definition.namespace)
        declared_readback = str(
            getattr(write_definition, "readback_tool", "") or ""
        ).strip()
        if declared_readback:
            try:
                candidate, _handler = self._get_registered_tool(declared_readback)
            except KeyError:
                return None
            if not candidate.is_read_tool:
                return None
            if self._canonical_platform(candidate.namespace) != platform:
                return None
            if candidate.action != "get" or candidate.resource_type != write_definition.resource_type:
                return None
            if candidate.parent_resource_type != write_definition.parent_resource_type:
                return None
            return candidate

        candidates = []
        for definition in self.registry.list_all():
            if not definition.is_read_tool:
                continue
            if self._canonical_platform(definition.namespace) != platform:
                continue
            if definition.action != "get" or definition.resource_type != write_definition.resource_type:
                continue
            if definition.parent_resource_type != write_definition.parent_resource_type:
                continue
            candidates.append(definition)
        # A name/order based tie-breaker would make a provider upgrade
        # silently reconcile against the wrong endpoint. Ambiguity is a
        # provider contract problem and must remain visible to recovery.
        return candidates[0] if len(candidates) == 1 else None

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
