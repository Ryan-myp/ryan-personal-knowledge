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

import uuid
import time
import json
import os
import re
import threading
import logging
import inspect
from collections import OrderedDict
from contextvars import ContextVar
from pathlib import Path
from types import MappingProxyType
from typing import Any, Callable, Iterable, Mapping, Optional

from ..core.interfaces import (
    ToolResult, CapabilityModule,
    ToolRegistry, WriteGuard, IntentParser, IntentRouter,
    ParsedIntent, ToolEffect, ExecutionMode, ProviderReconciler,
)
from ..core.tool_registry import GuardedToolRegistry, SimpleToolRegistry, validate_tool_input
from ..core.intent import LLMIntentParser, SimpleIntentRouter
from ..core.features import RuntimeFeature
from ..core.execution_plan import ExecutionPlan
from ..core.execution_trace import ExecutionTrace, ExecutionEventCallback
from ..core.response import ResponseRenderer, ResponseSynthesizer
from ..domain.ad.response import LLMResponseSynthesizer
from ..core.agent_profile import AgentProfile
from ..core.conversation_title import ConversationTitleGenerator
from ..core.plugins import (
    PluginKind,
    PluginLoader,
    PluginRegistry,
    manifest_for_builtin,
    manifest_for_managed_skill,
)
from ..features.factory import discover_features, feature_for_intent
from ..features.factory import discover_response_renderer
from ..core.tool_selector import DynamicToolSelector
from ..core.policy import RuntimePolicy, validate_policies
from ..domain.ad.knowledge import KnowledgeProvider, MarkdownWikiKnowledgeProvider
from ..knowledge_management import ManagedKnowledgeProvider
from ..core.memory import MemoryManager
from ..domain.ad.parameter_catalog import ParameterCatalogRegistry
from ..domain.ad.blueprint import BlueprintRegistry, BlueprintCascadeEngine
from ..domain.ad.creation_card import CreationCardBuilder
from ..domain.ad.contracts import ResourceResult
from ..domain.ad.clarification import ActionClarificationBuilder
from ..domain.ad.parameter_selection import (
    ParameterSelectionSigner,
)
from ..domain.ad.auth import RequestPrincipal, normalize_account_id
from ..domain.ad.security import (
    ACCOUNT_SCOPE_FIELDS,
    PROTECTED_INPUT_FIELDS,
)
from .skill import BaseSkill, Skill, SkillContract, SkillLoader
from .input_builder import ToolInputBuilder
from .account_context import AccountResolver
from .services import AdRuntimeServices
from .workflow import WorkflowCoordinator
from .account_policy import AccountWhitelistValidator
from .session_context import SessionContext
from .security import RuntimeSecurity
from .tool_executor import ToolExecutor
from .outbox import OutboxPublisher
from .scheduling_service import SchedulingService
from .provider_bindings import ProviderBindings
from .supervisor import RuntimeSupervisor
from .ad_creation_services import AdCreationServicesMixin
from .ad_capability_services import AdCapabilityLifecycleMixin
from .ad_task_services import AdTaskServices
from .ad_persistence_services import AdPersistenceServices
from .ad_conversation_services import AdConversationServices
from .ad_session_services import AdSessionServices
from .ad_workflow_services import AdWorkflowServices
from ..core.runtime_kernel import AgentRuntimeKernel, TurnRequest
from ..persistence.session_manager import SessionManager
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

class AdAgentRuntime(AdCapabilityLifecycleMixin, AdCreationServicesMixin):
    """
    广告应用层的单 Agent 组合根。

    通用并发、会话租约和请求生命周期由 ``AgentRuntimeKernel`` 提供；本类
    只负责把广告应用的 Skills、Tools、Capabilities、记忆、工作流和展示
    适配器组合起来。它不是通用 Runtime，新的非广告应用不应继承或修改它。

    架构层次：
    ┌─────────────────────────────────────────┐
    │  AdAgentRuntime（广告应用组合根）          │
    │  ├─ SessionManager（会话管理）             │
    │  ├─ IntentRouter（意图路由）               │
    │  ├─ ToolRegistry（工具执行）               │
    │  └─ WriteGuard（写入保护）                 │
    └─────────────────────────────────────────┘

    借鉴 DAP Agent internal/core/engine/runtime.go 的核心设计：
    - Core 只认接口，不 import 业务
    - 业务通过 CapabilityModule 注入
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
        provider_reconcilers: Optional[Mapping[str, ProviderReconciler]] = None,
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
        session_lease_seconds: float = 300.0,
        outbox_delivery: Optional[Callable[[Any], None]] = None,
        outbox_poll_interval: float = 0.25,
        start_background_workers: bool = True,
        conversation_title_use_llm: bool = False,
    ):
        base_registry = registry or SimpleToolRegistry()
        self.registry = (
            base_registry
            if isinstance(base_registry, GuardedToolRegistry)
            else GuardedToolRegistry(base_registry)
        )
        # GuardedToolRegistry exposes only non-executable Handler views to
        # callers. Runtime keeps the opaque capability needed for its
        # post-policy execution path.
        self._registry_execution_token = getattr(
            self.registry, "_execution_token", None
        )
        self.provider_bindings = ProviderBindings()
        self.require_llm = bool(require_llm)
        self.agent_profile = AgentProfile(
            name="ad-agent",
            role="广告投放与分析助手",
            domain_guidance="广告业务知识只来自当前注册的 Skills、Tools、Blueprints 和受控知识源。",
            response_guidance="面向广告运营人员回答，必须区分预览、已执行、失败和状态未知。",
            structured_fields=(
                "仅使用当前注册的 Skill、Tool、Capability 和 Blueprint 契约中声明的字段；"
                "缺少必填信息时先澄清，不从业务常识猜测"
            ),
        )
        self.intent_parser = intent_parser or LLMIntentParser(
            llm_client, allow_rule_fallback=not self.require_llm,
            profile=self.agent_profile,
        )
        if self.require_llm and isinstance(self.intent_parser, LLMIntentParser):
            # An explicitly supplied LLMIntentParser must obey the Runtime's
            # production boundary too; it cannot silently fall back to rules.
            self.intent_parser.allow_rule_fallback = False
        self.intent_router = intent_router or SimpleIntentRouter()
        self.write_guard = write_guard
        self.skill_loader = SkillLoader(skill_roots)
        self.skill_loader.load_all()
        # SkillLoader is the sole owner of Skill discovery. Publish the
        # validated platform aliases to the parser before the first turn;
        # Parser/Core must not scan the filesystem independently.
        for skill in self.skill_loader.list_all().values():
            register_aliases = getattr(self.intent_parser, "register_platform_aliases", None)
            if callable(register_aliases):
                register_aliases(skill.platform, skill.platform_aliases or [])
        self._llm = llm_client
        self.conversation_title_generator = ConversationTitleGenerator()
        # A conversation title is presentation metadata and must never add a
        # model round-trip to the user's execution request.  Keep the model
        # implementation available for an explicitly configured asynchronous
        # title worker, while using the bounded deterministic fallback on the
        # request path by default.
        self.conversation_title_use_llm = bool(conversation_title_use_llm)
        # A caller may inject an already-configured LLMIntentParser instead
        # of passing the model separately.  Treat that parser-owned model as
        # the same model-backed Agent dependency; otherwise the strict
        # startup gate would reject a valid LLM configuration while checking
        # only the Runtime field.
        if self._llm is None:
            model_client = getattr(self.intent_parser, "model_client", None)
            if callable(model_client):
                self._llm = model_client()
        self._sessions: dict[str, "SessionContext"] = {}
        self._session_locks: dict[str, threading.RLock] = {}
        self._session_locks_guard = threading.RLock()
        self._background_tasks: list[dict] = []
        # One provider-neutral lifecycle registry for all extension types.
        # Existing discovery seams feed this registry; it is not a second
        # Tool router and never bypasses Runtime execution gates.
        self.plugin_registry = PluginRegistry()
        self.plugin_loader = PluginLoader(
            self.plugin_registry,
            allow_trusted_source=True,
        )
        # Optional domain workflows are discovered by package convention.
        # Runtime only knows the generic feature seam; it does not import a
        # domain workflow or maintain an intent-to-feature table.
        self.features: list[RuntimeFeature] = list(
            discover_features() if features is None else features
        )
        for feature in self.features:
            feature_name = str(getattr(feature, "feature_name", "") or "").strip()
            if feature_name:
                self._register_builtin_plugin(
                    f"feature:{feature_name}",
                    feature,
                    (PluginKind.FEATURE.value,),
                    description=f"Runtime feature {feature_name}",
                )
            register_descriptors = getattr(
                self.intent_parser, "register_intent_descriptors", None
            )
            if callable(register_descriptors):
                register_descriptors(feature.intent_descriptors())
        self.response_renderer: ResponseRenderer = (
            response_renderer or discover_response_renderer()
        )
        if self.response_renderer is None:
            raise RuntimeError("no response renderer is registered")
        self.response_synthesizer: Optional[ResponseSynthesizer] = (
            response_synthesizer
            if response_synthesizer is not None
            else (
                LLMResponseSynthesizer(profile=self.agent_profile)
                if self._llm is not None else None
            )
        )
        renderer_name = str(
            getattr(self.response_renderer, "renderer_name", "") or ""
        ).strip()
        if renderer_name:
            self._register_builtin_plugin(
                f"renderer:{renderer_name}",
                self.response_renderer,
                (PluginKind.RENDERER.value,),
                description=f"Response renderer {renderer_name}",
            )
        # Keep exact registration ownership so multiple Skills can share a
        # platform and unload cannot rely on a non-existent ``skill.tools``
        # attribute or accidentally remove another Skill's tools.
        self._skill_objects: dict[str, Skill] = {}
        self._skill_keys_by_platform: dict[str, list[str]] = {}
        self._skill_tool_names: dict[str, list[str]] = {}
        self._skill_platforms: dict[str, str] = {}
        self._skill_format_ids: dict[str, set[str]] = {}
        # User-managed Skills are tenant-owned context packages.  They are
        # deliberately tracked separately from executable provider Skills so
        # an uploaded directory cannot become a Tool merely by containing a
        # contract or a Python file.  The Runtime itself is process-global,
        # therefore this index must be tenant-scoped.
        self._managed_context_skills: dict[str, dict[str, Skill]] = {}
        self._managed_skill_lock = threading.RLock()
        self._skill_factories: dict[str, callable] = {}  # platform -> Capability factory
        self._credentials: dict = {}  # API 凭证配置
        self._execution_mode_lock = threading.RLock()
        # Principal preferences are cached only as a bounded-in-process
        # acceleration layer. The PersistenceBackend remains the source of
        # truth so a Runtime restart does not silently reset a user's mode.
        self._execution_mode_cache: OrderedDict[
            tuple[str, str], tuple[str, float]
        ] = OrderedDict()
        base_knowledge_provider = knowledge_provider or MarkdownWikiKnowledgeProvider(
            Path(__file__).resolve().parent.parent / "knowledge_base",
            search_index=persistence_store,
        )
        self.knowledge_provider = (
            ManagedKnowledgeProvider(base_knowledge_provider, persistence_store)
            if knowledge_provider is None and persistence_store is not None
            else base_knowledge_provider
        )
        self.tool_selector = tool_selector or DynamicToolSelector(
            skill_loader=self.skill_loader,
            knowledge_provider=self.knowledge_provider,
        )
        self.parameter_catalogs = ParameterCatalogRegistry()
        # Provider-owned declarative creation metadata.  The registry is a
        # discovery index only; cascade evaluation is deterministic and does
        # not execute arbitrary configuration or provider code.
        self.creation_blueprints = BlueprintRegistry()
        self.blueprint_cascade = BlueprintCascadeEngine()
        self.creation_card_builder = CreationCardBuilder(
            self.creation_blueprints,
            self.registry,
            self.blueprint_cascade,
        )
        self.action_clarification_builder = ActionClarificationBuilder(
            field_labeler=self._clarification_field_label,
            field_hint_builder=self._clarification_field_hint,
        )
        # Blueprint context is declarative and changes only at registry
        # lifecycle boundaries. Cache the bounded LLM view per provider scope
        # so ordinary turns do not re-expand every creation schema twice.
        self._creation_blueprint_context_cache: dict[tuple[str, ...], str] = {}
        # This is a metadata index, not a second executable routing table.
        # Each provider Capability owns and publishes its own entries.
        self.ad_format_catalogs: dict[str, list[dict[str, Any]]] = {}
        # Provider-owned compatibility metadata is a diagnostic/release
        # index, never a routing table.  Keeping it on Runtime lets the
        # contract snapshot detect an API version change even when Tool names
        # and schemas remain unchanged.
        self.provider_version_contracts: dict[str, dict[str, Any]] = {}
        self.provider_api_surfaces: dict[str, list[dict[str, Any]]] = {}
        selection_secret = selection_token_secret or os.environ.get(
            "AD_AGENT_SELECTION_TOKEN_KEY"
        )
        self._parameter_selection_signer = ParameterSelectionSigner(
            selection_secret, parameter_selection_ttl_seconds
        )
        self.services = AdRuntimeServices(self)
        self.input_builder = ToolInputBuilder(
            self.services,
            scope_field_names=ACCOUNT_SCOPE_FIELDS,
            scope_value_resolver=lambda context: getattr(context, "account_id", None),
        )
        self.account_resolver = AccountResolver(self.services)
        self.policies: list[RuntimePolicy] = list(policies or [])
        if self.policies:
            self.tool_selector.set_policies(self.policies)

        if execution_mode not in {mode.value for mode in ExecutionMode}:
            raise ValueError(f"Unsupported execution_mode: {execution_mode}")
        # dry_run 是安全默认值；只有调用方显式指定 live 才允许进入真实写入分支。
        self._execution_mode = self._validate_execution_mode(execution_mode)
        # ``ToolDefinition.live_support`` describes adapter intent, but is not
        # an approval.  Keep a separate, code-side allowlist so an unverified
        # write can never become live merely because a definition defaulted to
        # True.  This set is deliberately not populated from user input or
        # provider credentials.
        self._live_approved_tools = set(live_approved_tools or set())
        # This is a second, deployment-level fuse.  A configured execution
        # mode or tool allowlist must never be sufficient to turn on provider
        # mutations.  The embedding/application must opt in explicitly after
        # the operator has selected and verified the test accounts.
        self.allow_live_writes = bool(allow_live_writes)
        # 读请求也默认受受控账户边界约束，避免带凭证的服务被用来查询
        # 任意账户。需要本地离线探索时应显式提供测试 validator。
        self.enforce_account_scope = enforce_account_scope
        # Offline fixtures are useful for local development, but a normal
        # Runtime must not present provider-free mock rows as real query
        # results.  Write planning remains available without a client because
        # dry-run writes are intercepted before handlers execute.
        self.offline_mode = bool(offline_mode)
        # Permissions are injected by the trusted embedding/auth layer, never
        # inferred from user text or provider credentials. Missing permissions
        # fail closed for both read and write tools.
        # A direct/local embedding gets the safe baseline needed to inspect
        # data and build dry-run plans.  Passing an explicit empty set is
        # different: it intentionally denies every permissioned tool.  The
        # HTTP server always passes its configured principal permissions.
        default_permissions = {"ads.read", "ads.plan", "memory.read", "memory.write"}
        self._granted_permissions = frozenset(
            str(permission)
            for permission in (
                default_permissions if granted_permissions is None else granted_permissions
            )
        )
        if max_tool_calls <= 0:
            raise ValueError("max_tool_calls must be positive")
        if turn_timeout_seconds <= 0:
            raise ValueError("turn_timeout_seconds must be positive")
        self.max_tool_calls = int(max_tool_calls)
        self.turn_timeout_seconds = float(turn_timeout_seconds)
        self.max_user_input_chars = int(max_user_input_chars)
        self.max_platform_params_bytes = int(max_platform_params_bytes)
        if workflow_stale_after_seconds <= 0:
            raise ValueError("workflow_stale_after_seconds must be positive")
        self.workflow_stale_after_seconds = float(workflow_stale_after_seconds)
        self._workflow_lease_owner = f"runtime:{os.getpid()}:{uuid.uuid4().hex}"
        if session_lease_seconds <= 0:
            raise ValueError("session_lease_seconds must be positive")
        self.session_lease_seconds = float(session_lease_seconds)
        self._session_lease_owner = f"session:{os.getpid()}:{uuid.uuid4().hex}"
        # Reconciliation is provider-owned. Built-in adapters use only
        # registered read tools; custom providers can replace/extend them
        # without adding provider branches to the Runtime.
        # Custom provider reconcilers are optional. The default reconciler
        # discovers a matching read Tool from registered metadata at use time.
        self._provider_reconcilers: dict[str, ProviderReconciler] = {}
        for platform, reconciler in (provider_reconcilers or {}).items():
            if not isinstance(reconciler, ProviderReconciler):
                raise TypeError("provider reconciler must implement ProviderReconciler")
            canonical = self._canonical_platform(platform)
            self._provider_reconcilers[canonical] = reconciler

        # 账户白名单验证器
        self.whitelist_validator = whitelist_validator or AccountWhitelistValidator()

        # 持久化层（可选）
        self._session_manager: Optional[SessionManager] = None
        self._memory_manager: Optional[MemoryManager] = None
        if persistence_store:
            self._persistence_store = persistence_store
            self._session_manager = SessionManager(persistence_store)
            recover_runs = getattr(
                self._session_manager, "recover_stale_execution_runs", None
            )
            if callable(recover_runs):
                try:
                    recovered_runs = recover_runs(self.workflow_stale_after_seconds)
                    if recovered_runs:
                        logger.warning(
                            "marked %s stale Agent runs for recovery", recovered_runs
                        )
                except Exception:
                    logger.exception("failed to recover stale Agent runs")
            if all(callable(getattr(persistence_store, method, None)) for method in (
                "save_memory", "search_memories", "delete_memory"
            )):
                self._memory_manager = MemoryManager(persistence_store)
            if self.write_guard and hasattr(self.write_guard, "bind_store"):
                self.write_guard.bind_store(persistence_store)
        else:
            self._persistence_store = None
        self.outbox = OutboxPublisher(self._session_manager) if self._session_manager else None
        self.outbox_consumer = None
        self.event_repair_consumer = None

        # 只读模式：只注册 READ 类工具，跳过写保护检查
        self._read_only_mode = read_only_mode
        self.workflow = WorkflowCoordinator(
            self.services,
            outbox=self.outbox,
            item_scope_resolver=self._resolve_workflow_item_scope,
            result_scope_resolver=self._resolve_workflow_result_scope,
        )
        self.security = RuntimeSecurity(self)
        self.scheduling_service = SchedulingService(
            store=self._persistence_store,
            submit_task=self.submit_task,
            session_context=lambda session_id: self._sessions.get(str(session_id or "")),
            preflight=self.preflight_scheduled_prompt,
            redact=self._redact_for_persistence,
            validate_input=self.security.validate_input_redline,
            max_prompt_chars=self.max_user_input_chars,
            default_permissions=self._granted_permissions,
        )
        self.services.bind_scheduling(self.scheduling_service)
        self.persistence_services = AdPersistenceServices(self)
        self.conversation_services = AdConversationServices(self)
        self.session_services = AdSessionServices(self)
        self.workflow_services = AdWorkflowServices(self)
        self.task_services = AdTaskServices(self)
        # The kernel is intentionally business-neutral.  This composition
        # point is the only place where the advertising application binds its
        # policy/session implementation to the generic turn shell.
        self._runtime_kernel = AgentRuntimeKernel(
            session_manager=self._session_manager,
            session_locks=self._session_locks,
            session_locks_guard=self._session_locks_guard,
            lease_owner=self._session_lease_owner,
            lease_seconds=self.session_lease_seconds,
            mode_context=_execution_mode_context,
            validate_mode=self._validate_execution_mode,
            resolve_mode=lambda tenant, user, _requested: self.get_execution_mode(
                tenant, user
            ),
            assert_ready=self.assert_llm_ready,
            ensure_session=self._ensure_kernel_session,
            refresh_session=self._refresh_kernel_session,
            execute_unlocked=self._execute_kernel_request,
            busy_error=SessionBusyError,
        )
        self.tool_executor = ToolExecutor(self.services)
        # Queue, lease and repair workers are infrastructure. The supervisor
        # owns their lifecycle; this Runtime only supplies the trusted Agent
        # turn callback and the generic scheduled-task hand-off.
        self.supervisor = RuntimeSupervisor(
            store=self._persistence_store,
            outbox_delivery=outbox_delivery or self._default_outbox_delivery,
            scheduled_submitter=self._submit_scheduled_task,
            task_handler=self._execute_agent_task,
            redact=self._redact_for_persistence,
            max_task_workers=max_task_workers,
            max_task_queue=max_task_queue,
            task_timeout_seconds=task_timeout_seconds,
            task_lease_seconds=task_lease_seconds,
            outbox_poll_interval=outbox_poll_interval,
            start_background_workers=start_background_workers,
        )
        self.outbox_consumer = self.supervisor.outbox_consumer
        self.event_repair_consumer = self.supervisor.event_repair_consumer
        self.task_executor = self.supervisor.task_executor
        self.scheduler = self.supervisor.scheduler
        if read_only_mode:
            logger.info("🔒 只读模式已启用，仅允许查询操作")

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
                if len(getattr(intent, "platforms", []) or []) == 1 else None
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

    @staticmethod
    def _clarification_field_label(
        path: str, spec: Mapping[str, Any]
    ) -> Optional[str]:
        """Advertising presentation labels stay outside Core clarification."""
        configured = spec.get("label") or spec.get("title")
        if configured:
            return str(configured)
        return {
            "account_id": "广告账户 ID",
            "ad_account_id": "广告账户 ID",
            "advertiser_id": "广告主 ID",
            "customer_id": "客户账户 ID",
            "campaign_id": "Campaign ID",
            "campaign_ids": "Campaign ID 列表",
            "ad_group_id": "Ad Group ID",
            "adgroup_id": "Ad Group ID",
            "ad_id": "Ad ID",
        }.get(str(path or "").rsplit(".", 1)[-1])

    @staticmethod
    def _clarification_field_hint(
        path: str, _spec: Mapping[str, Any]
    ) -> Optional[str]:
        if str(path or "").rsplit(".", 1)[-1] in {
            "account_id", "ad_account_id", "advertiser_id", "customer_id",
        }:
            return "请填写当前渠道的广告账户 ID，不能用其他渠道账户代替。"
        return None

    def _refresh_parser_catalog(self) -> None:
        """Synchronize parser discovery data with the active Tool registry."""
        self._creation_blueprint_context_cache.clear()
        definitions = self.registry.list_all()
        refresh_catalog = getattr(self.intent_parser, "refresh_tool_catalog", None)
        if callable(refresh_catalog):
            refresh_catalog(definitions)
        for feature in self.features:
            register_descriptors = getattr(
                self.intent_parser, "register_intent_descriptors", None
            )
            if callable(register_descriptors):
                register_descriptors(feature.intent_descriptors())

        # Skill aliases are context metadata, but they must follow the same
        # lifecycle as their active Skill.  Provider identity itself remains
        # discovered from Tool metadata; aliases never create Tools.
        for skill in list(self._skill_objects.values()):
            register_aliases = getattr(self.intent_parser, "register_platform_aliases", None)
            if callable(register_aliases):
                register_aliases(skill.platform, skill.platform_aliases or [])

    @staticmethod
    def _canonical_platform(platform: str) -> str:
        """Normalize aliases without keeping a Runtime platform registry."""
        return ProviderBindings.normalize_platform(platform)

    def _resolve_platform_identifier(self, platform: str) -> str:
        """Resolve a caller-facing platform alias from active Skill metadata.

        Canonicalization only normalizes separators. Alias resolution belongs
        to the active Skill/Capability lifecycle, so structured continuation
        payloads such as ``platform_params={"google": ...}`` can converge on
        the registered ``google-ads`` key without a Core provider map.
        """
        raw = str(platform or "").strip().casefold()
        normalized = self._canonical_platform(raw)
        if not raw:
            return ""
        for skill in self.skill_loader.list_all().values():
            canonical = self._canonical_platform(getattr(skill, "platform", ""))
            aliases = {
                str(getattr(skill, "platform", "") or "").strip().casefold(),
                canonical,
                canonical.replace("-", " "),
            }
            aliases.update(
                str(alias or "").strip().casefold()
                for alias in (getattr(skill, "platform_aliases", []) or [])
            )
            aliases.update(
                self._canonical_platform(alias)
                for alias in list(aliases)
            )
            if raw in aliases or normalized in aliases:
                return canonical
        for definition in self.registry.list_all():
            canonical = self._canonical_platform(getattr(definition, "platform", ""))
            if normalized == canonical:
                return canonical
        return normalized

    @property
    def persistence_store(self):
        """Expose the persistence abstraction to management services."""
        return self._session_manager.store if self._session_manager else None

    def close(self, wait: bool = False) -> None:
        """Stop durable workers through the infrastructure supervisor."""
        self.supervisor.close(wait=wait)

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
        """Publish a trusted in-process extension in the common registry."""

        manifest = manifest_for_builtin(
            plugin_id,
            version,
            kinds=tuple(kinds),
            description=description,
        )
        self.plugin_loader.install(
            manifest,
            contribution=contribution,
            replace=replace,
        )
        self.plugin_registry.activate(manifest.plugin_id)

    def list_plugins(self, tenant_id: Optional[str] = None) -> list[dict[str, Any]]:
        """Return safe, tenant-scoped plugin lifecycle metadata."""

        snapshots = self.plugin_registry.snapshot()
        if tenant_id is None:
            return snapshots
        tenant = str(tenant_id or "default").strip().lower()
        return [
            item for item in snapshots
            if item.get("manifest", {}).get("source") != "managed"
            or item.get("manifest", {}).get("metadata", {}).get("tenant_id") == tenant
        ]

    def load_managed_skill(self, skill_dir: str, tenant_id: str = "default") -> bool:
        """Load a published standard Skill directory as advisory context.

        This path intentionally does not call ``register_skill`` and never
        imports ``tools.py``.  Provider Tools must continue to come from
        built-in/verified Capabilities; a managed Skill can guide the Agent
        but cannot create a new side-effect path.
        """
        from pathlib import Path

        tenant_id = str(tenant_id or "default")
        directory = Path(skill_dir).resolve()
        if not directory.is_dir() or not (directory / "SKILL.md").is_file():
            raise ValueError("managed Skill directory must contain SKILL.md")
        contract = SkillContract(str(directory)).load()
        if contract.context_only or not contract.name:
            raise ValueError("managed Skill must be a standalone Skill with a name")
        # Build the complete advisory object before touching any Runtime
        # indexes. A malformed package therefore cannot remove the old
        # published context.
        skill = BaseSkill(contract)
        setattr(skill, "skill_dir", str(directory))

        with self._managed_skill_lock:
            if (
                contract.name in self._skill_objects
            ):
                raise ValueError(
                    "managed Skill name conflicts with executable Skill: "
                    f"{contract.name}"
                )

            # Replace only a previous managed version for this tenant. A
            # built-in Skill with the same name is protected by the conflict
            # check above. Managed Skills never enter SkillLoader or the
            # global parser alias index; both are process-wide and would leak
            # tenant-owned context.
            self._managed_context_skills.setdefault(tenant_id, {})[contract.name] = skill
            managed_manifest = manifest_for_managed_skill(
                tenant_id,
                contract.name,
                contract.version,
                description=contract.description,
            )
            self.plugin_loader.install(
                managed_manifest,
                contribution=skill,
                replace=True,
            )
            self.plugin_registry.activate(managed_manifest.plugin_id)
            if hasattr(self.tool_selector, "register_context_skill"):
                self.tool_selector.register_context_skill(skill, tenant_id=tenant_id)
            self._refresh_parser_catalog()
        return True

    def unload_managed_skill(self, skill_name: str, tenant_id: str = "default") -> bool:
        """Remove advisory context without touching executable provider Tools."""
        key = str(skill_name or "")
        tenant_id = str(tenant_id or "default")
        with self._managed_skill_lock:
            tenant_skills = self._managed_context_skills.get(tenant_id)
            skill = tenant_skills.pop(key, None) if tenant_skills else None
            if skill is None:
                return False
            if hasattr(self.tool_selector, "unregister_context_skill"):
                self.tool_selector.unregister_context_skill(key, tenant_id=tenant_id)
            self.plugin_registry.unregister(
                manifest_for_managed_skill(tenant_id, key, "1.0.0").plugin_id
            )
            if not tenant_skills:
                self._managed_context_skills.pop(tenant_id, None)
            self._refresh_parser_catalog()
            return True

    def get_managed_skills(self, tenant_id: Optional[str] = None) -> dict[str, Skill]:
        """Return tenant-scoped managed Skills for diagnostics/UI.

        The no-argument form is retained for single-tenant callers. Once the
        Runtime contains multiple non-default tenants it returns an empty
        mapping instead of guessing and exposing another tenant's context.
        """
        with self._managed_skill_lock:
            if tenant_id is not None:
                return dict(self._managed_context_skills.get(str(tenant_id or "default"), {}))
            if len(self._managed_context_skills) == 1:
                return dict(next(iter(self._managed_context_skills.values())))
            if "default" in self._managed_context_skills:
                return dict(self._managed_context_skills["default"])
            return {}

    def _build_skill_context(
        self,
        user_input: str,
        available_tools: list,
        intent_type: Optional[str],
        tenant_id: str,
    ) -> dict:
        """Build parser context through the selector contract."""
        context = self.tool_selector.build_context_for_input(
            user_input, available_tools, intent_type, tenant_id=tenant_id
        )
        if not isinstance(context, dict):
            context = {}
        # Blueprints are bounded declarative context for the LLM. They do not
        # register Tools and cannot execute lookup/provider operations.
        # Reuse the selector's registry-derived platform scope so the LLM gets
        # the complete relevant Blueprint catalog within a bounded prompt.
        # With no provider scope, the registry-backed builder returns the full
        # bounded declarative catalog.
        raw_platforms = context.get("platforms")
        provider_scope = [
            item.strip() for item in str(raw_platforms or "").split(",")
            if item.strip()
        ]
        provider_key = tuple(sorted(set(provider_scope)))
        if provider_key not in self._creation_blueprint_context_cache:
            self._creation_blueprint_context_cache[provider_key] = (
                self.creation_card_builder.llm_context(
                    providers=list(provider_key) or None
                )
            )
        context["publisher_context"] = self._creation_blueprint_context_cache[
            provider_key
        ]
        return context

    def _optimize_tool_selection(
        self, user_input: str, intent: ParsedIntent,
        available_tools: list, tenant_id: str,
    ) -> dict:
        """Optimize the current Tool context through the selector contract."""
        optimizer = self.tool_selector.optimize_for_llm
        try:
            parameters = inspect.signature(optimizer).parameters
        except (TypeError, ValueError):
            parameters = {}
        if "tenant_id" in parameters:
            return optimizer(
                user_input, intent, available_tools, tenant_id=tenant_id
            )
        return optimizer(user_input, intent, available_tools)

    def _build_prior_tool_results_context(
        self, session: "SessionContext", max_results: int = 8, max_chars: int = 4000
    ) -> str:
        """Build a bounded, redacted context view of prior Tool results.

        Tool results are durable execution evidence, not conversation prose.
        Keeping this bridge explicit lets a later LLM turn understand IDs,
        statuses and lookup output without exposing raw result objects as a
        new execution interface or allowing the model to bypass Runtime gates.
        """
        rows: list[str] = []
        for tool_name, result in list(session.tool_results.items())[-max_results:]:
            if not isinstance(result, ToolResult):
                continue
            safe = self._redact_for_persistence(result.to_dict())
            try:
                encoded = json.dumps(safe, ensure_ascii=False, sort_keys=True, default=str)
            except (TypeError, ValueError):
                encoded = json.dumps(
                    {"success": result.success, "error": str(result.error or "")},
                    ensure_ascii=False,
                )
            rows.append(f"[{tool_name}] {encoded[:1200]}")
        return "\n".join(rows)[:max_chars]

    def _validate_policies(self, intent: ParsedIntent) -> list[str]:
        """Run Skill-owned policies through the generic policy contract."""
        return validate_policies(self.policies, intent)

    @property
    def is_dry_run(self) -> bool:
        return self.execution_mode == ExecutionMode.DRY_RUN.value

    def _validate_request_limits(
        self, user_input: str, platform_params: Optional[dict],
    ) -> Optional[str]:
        """Fail closed on oversized request envelopes before parsing/LLM use."""
        if not isinstance(user_input, str) or not user_input.strip():
            return "user_input 不能为空"
        if len(user_input) > self.max_user_input_chars:
            return f"user_input 超过长度限制（最多 {self.max_user_input_chars} 个字符）"
        if platform_params is not None:
            if not isinstance(platform_params, dict):
                return "platform_params 必须是对象"
            try:
                size = len(json.dumps(platform_params, ensure_ascii=False, default=str).encode("utf-8"))
            except (TypeError, ValueError):
                return "platform_params 不是可序列化的对象"
            if size > self.max_platform_params_bytes:
                return (
                    "platform_params 超过大小限制（最多 "
                    f"{self.max_platform_params_bytes} 字节）"
                )
        return None

    @staticmethod
    def _check_turn_budget(deadline: float, tool_call_count: int, max_tool_calls: int = 32) -> Optional[str]:
        if tool_call_count > max_tool_calls:
            return f"工具调用次数超过本回合上限（最多 {max_tool_calls} 次）"
        if time.monotonic() > deadline:
            return "本回合执行超时，已停止后续工具调用"
        return None

    def _check_tool_permissions(
        self,
        tool_def: Any,
        granted_permissions: Optional[set[str] | frozenset[str]] = None,
    ) -> Optional[str]:
        required = {
            str(permission) for permission in (getattr(tool_def, "required_permissions", []) or [])
        }
        # Planning and live execution are distinct grants.  A write tool may
        # be used to produce a dry-run plan with ads.plan, but executing it
        # against a provider additionally requires ads.write.
        if tool_def.is_write_tool and self.execution_mode == ExecutionMode.LIVE.value:
            required.add("ads.write")
        granted = self._granted_permissions if granted_permissions is None else frozenset(granted_permissions)
        missing = sorted(required - granted)
        if missing:
            return "缺少工具所需权限：" + ", ".join(missing)
        return None

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

    # ─── Capability 注册 ───────────────────────────────────────


    def _validate_account_for_tool(self, platform: str, account_id: str, is_write: bool) -> tuple[bool, str]:
        """统一账户边界。

        写操作无论是 dry-run 还是 live，都必须命中显式测试账户白名单；
        dry-run 也不能用任意生产账户生成看似可执行的计划。
        """
        if not account_id:
            return False, "缺少账户ID"
        allowed = self.whitelist_validator.get_allowed_accounts(platform)
        if (is_write or self.enforce_account_scope) and not allowed:
            return False, f"{platform} 未配置受控账户白名单，当前请求被拒绝"
        return self.whitelist_validator.validate_account(platform, account_id)

    @staticmethod
    def _principal_accounts(
        platform: str,
        account_scope: Optional[Mapping[str, Any]],
    ) -> Optional[set[str]]:
        """Return the trusted principal's account scope, or ``None`` if absent."""
        if account_scope is None:
            return None
        normalized = AdAgentRuntime._canonical_platform(platform)
        aliases = {normalized, platform}
        accounts: set[str] = set()
        for key in aliases:
            values = account_scope.get(key, ()) if hasattr(account_scope, "get") else ()
            if isinstance(values, (str, bytes)):
                values = (values,)
            accounts.update(normalize_account_id(value) for value in (values or ()))
        return {value for value in accounts if value}

    def _validate_account_with_principal(
        self,
        platform: str,
        account_id: str,
        is_write: bool,
        account_scope: Optional[Mapping[str, Any]],
    ) -> tuple[bool, str]:
        """Apply both configured test-account and trusted principal scopes."""
        if account_scope is not None:
            principal_accounts = self._principal_accounts(platform, account_scope)
            if not principal_accounts or normalize_account_id(account_id) not in principal_accounts:
                return False, f"账户 {account_id or '<empty>'} 不在当前身份的授权范围内"
        return self._validate_account_for_tool(platform, account_id, is_write)

    def _available_accounts_for_request(
        self,
        platform: str,
        account_scope: Optional[Mapping[str, Any]],
    ) -> list[str]:
        configured = self.whitelist_validator.get_allowed_accounts(platform)
        principal_accounts = self._principal_accounts(platform, account_scope)
        if principal_accounts is None:
            return list(configured)
        return [
            account for account in configured
            if normalize_account_id(account) in principal_accounts
        ]

    def _simulate_write(self, tool_def: Any, input_data: dict, platform: str) -> ToolResult:
        """生成本地模拟结果，保证 dry-run 不触发任何平台 API。"""
        key = self.registry.generate_idempotency_key(tool_def.name, input_data, "dry-run") \
            if hasattr(self.registry, "generate_idempotency_key") else uuid.uuid4().hex[:16]
        name = input_data.get("name") or f"dry_run_{key}"
        resource_type = getattr(tool_def, "resource_type", None) or "resource"
        resource_key = self._resource_id_field_for_tool(tool_def)
        if not resource_key:
            return ToolResult.error(
                f"Tool '{tool_def.name}' must declare resource_id_field"
            )
        parent_type = getattr(tool_def, "parent_resource_type", None)
        parent_field = self._parent_resource_id_field_for_tool(tool_def)
        parent_id = input_data.get(parent_field) if parent_field else None

        action = str(getattr(tool_def, "action", "") or "").lower()
        is_update = action in {"update", "pause", "resume", "enable", "disable"}
        is_delete = action == "delete"
        resource_id = input_data.get(resource_key) or f"dry_{platform}_{key}"
        operation = "delete" if is_delete else ("update" if is_update else "create")
        data = {
            "mode": ExecutionMode.DRY_RUN.value,
            "simulated": True,
            "live_support": bool(getattr(tool_def, "live_support", False)),
            "operation": operation,
            resource_key: resource_id,
            "resource_id_field": resource_key,
            "parent_resource_type": parent_type,
            "parent_resource_id_field": parent_field,
            "parent_resource_id": (
                str(parent_id) if parent_id not in (None, "") else None
            ),
            "name": name,
            "status": (
                "SIMULATED_DELETED" if is_delete
                else ("SIMULATED_UPDATED" if is_update else "SIMULATED_DRAFT")
            ),
            "input": {k: v for k, v in input_data.items() if k != "credentials"},
        }
        provider_errors = validate_tool_input(
            tool_def.input_schema,
            input_data,
            include_provider_contract=True,
        ) if tool_def.input_schema else []
        data["provider_validation"] = {
            "ready": not provider_errors,
            "errors": provider_errors,
        }
        return ToolResult.dry_run(data)

    @classmethod
    def _resource_id_field_for_tool(cls, tool_def: Any) -> Optional[str]:
        """Resolve the provider resource ID from the Tool contract.

        A provider with a different wire name publishes
        ``resource_id_field`` on its Tool. Runtime never infers an identity
        from a logical resource type or a schema property name.
        """
        declared = str(getattr(tool_def, "resource_id_field", "") or "").strip()
        if declared:
            return declared
        return None

    @staticmethod
    def _parent_resource_id_field_for_tool(tool_def: Any) -> Optional[str]:
        """Resolve a Tool's parent ID field from its explicit contract."""
        declared = str(
            getattr(tool_def, "parent_resource_id_field", "") or ""
        ).strip()
        if declared:
            return declared

        return None

    @classmethod
    def _parent_resource_id_for_tool(
        cls, tool_def: Any, input_data: Optional[dict[str, Any]] = None,
    ) -> Optional[str]:
        field = cls._parent_resource_id_field_for_tool(tool_def)
        value = (input_data or {}).get(field) if field else None
        return str(value) if value not in (None, "") else None

    @classmethod
    def _build_resource_results(cls, results: list[dict]) -> list[dict]:
        """Normalize write results without exposing provider credentials."""
        resource_items: list[ResourceResult] = []
        id_index: dict[tuple[str, str, str], int] = {}
        sequence = 0
        for item in results or []:
            tool_name = str(item.get("tool") or "")
            if not tool_name or not item.get("resource_type"):
                continue
            # Only resource-mutating results belong in this model.  A future
            # custom Tool may use a different name, so the result metadata is
            # also accepted as an explicit signal.
            data = item.get("data") if isinstance(item.get("data"), dict) else {}
            if not item.get("account_id") and not data and not item.get("error"):
                continue
            sequence += 1
            resource_type = str(item["resource_type"])
            id_field = str(item.get("resource_id_field") or "")
            if not id_field:
                continue
            input_data = data.get("input") if isinstance(data.get("input"), dict) else {}
            raw_id = data.get(id_field) or input_data.get(id_field) or item.get(id_field)
            raw_id = str(raw_id) if raw_id not in (None, "") else None
            simulated = bool(data.get("simulated") or item.get("simulated"))
            execution_status = str(data.get("execution_status") or "").lower()
            if item.get("skipped") or data.get("skipped"):
                status = "skipped"
            elif execution_status == "unsupported":
                status = "unsupported"
            elif execution_status in {"unknown", "timed_out", "transport_unknown"}:
                status = "unknown"
            elif item.get("needs_confirmation"):
                status = "awaiting_confirmation"
            elif item.get("success") and simulated:
                status = "planned"
            elif item.get("success"):
                status = "succeeded"
            else:
                status = "failed"

            parent_type = item.get("parent_resource_type") or data.get("parent_resource_type")
            parent_id = item.get("parent_resource_id") or data.get("parent_resource_id")
            if parent_id in (None, ""):
                # External consumers may provide a normalized result without
                # the top-level parent ID.  Only use the declared metadata
                # when available; do not guess from the provider name.
                parent_field = item.get("parent_resource_id_field")
                parent_id = input_data.get(parent_field) if parent_field else None
            parent_id = str(parent_id) if parent_id not in (None, "") else None
            normalized_platform = cls._canonical_platform(str(item.get("platform") or ""))
            parent_sequence = None
            if parent_id and parent_type:
                parent_sequence = id_index.get(
                    (normalized_platform, str(parent_type), parent_id)
                )
            local_id = raw_id if simulated else None
            provider_id = raw_id if raw_id and not simulated else None
            logical_id = str(
                data.get("logical_resource_id") or local_id or provider_id
                or input_data.get(id_field) or ""
            ) or None
            normalized = ResourceResult(
                sequence=sequence,
                platform=normalized_platform,
                resource_type=resource_type,
                tool_name=tool_name,
                status=status,
                parent_resource_type=(str(parent_type) if parent_type else None),
                account_id=(str(item.get("account_id")) if item.get("account_id") is not None else None),
                parent_sequence=parent_sequence,
                parent_resource_id=parent_id,
                provider_resource_id=provider_id,
                logical_resource_id=logical_id,
                local_resource_id=local_id,
                error=item.get("error"),
                simulated=simulated,
            )
            resource_items.append(normalized)
            if raw_id:
                id_index[(normalized_platform, resource_type, raw_id)] = sequence
        return [item.to_dict() for item in resource_items]

    @staticmethod
    def _freeze_credentials(value: Any) -> Any:
        """Make credentials visible to handlers as a read-only snapshot."""
        if isinstance(value, dict):
            return MappingProxyType({
                    key: AdAgentRuntime._freeze_credentials(item)
                for key, item in value.items()
            })
        if isinstance(value, list):
            return tuple(AdAgentRuntime._freeze_credentials(item) for item in value)
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
    ) -> None:
        self.persistence_services.persist_tool_result(
            session, turn_id, tool_def, platform, input_data, result,
        )



    def _resolve_readback_definition(self, write_tool: str):
        """Find the read Tool matching a write Tool's resource metadata."""
        try:
            write_definition, _handler = self._get_registered_tool(write_tool)
        except KeyError:
            return None
        platform = self._canonical_platform(write_definition.platform)
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
            if self._canonical_platform(candidate.platform) != platform:
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
            if self._canonical_platform(definition.platform) != platform:
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
        """Render a grounded answer with a deterministic safe fallback."""
        fallback = fallback_reply or self.response_renderer.render(
            intent, results, needs_confirmation, analysis=analysis
        )
        synthesizer = self.response_synthesizer
        if synthesizer is None or self._llm is None:
            return fallback, "renderer"
        skill_context = self._build_skill_context_from_metadata(session)
        try:
            answer = synthesizer.synthesize(
                self._llm,
                user_input=user_input,
                intent=intent,
                results=self._redact_for_persistence(results),
                knowledge=self._redact_for_persistence(
                    skill_context.get("knowledge", [])
                ),
                memory=self._redact_for_persistence(
                    skill_context.get("memory", [])
                ),
                analysis=self._redact_for_persistence(analysis or {}),
                fallback_reply=fallback,
                needs_confirmation=needs_confirmation,
            )
        except Exception as exc:
            logger.debug("LLM 最终回复生成失败，使用 Renderer 兜底: %s", exc)
            answer = None
        if answer:
            return answer, "llm"
        return fallback, "renderer"

    # -- Durable task and schedule facade ------------------------------

    def submit_task(self, *args: Any, **kwargs: Any) -> tuple[dict[str, Any], bool]:
        return self.task_services.submit_task(*args, **kwargs)

    def create_schedule(self, **kwargs: Any) -> dict[str, Any]:
        return self.task_services.create_schedule(**kwargs)

    def list_schedules(self, **kwargs: Any) -> list[dict[str, Any]]:
        return self.task_services.list_schedules(**kwargs)

    def get_schedule(self, schedule_id: str, *, user_id: str, tenant_id: str) -> Optional[dict[str, Any]]:
        return self.task_services.get_schedule(schedule_id, user_id=user_id, tenant_id=tenant_id)

    def pause_schedule(self, schedule_id: str, *, user_id: str, tenant_id: str) -> Optional[dict[str, Any]]:
        return self.task_services.pause_schedule(schedule_id, user_id=user_id, tenant_id=tenant_id)

    def resume_schedule(self, schedule_id: str, *, user_id: str, tenant_id: str) -> Optional[dict[str, Any]]:
        return self.task_services.resume_schedule(schedule_id, user_id=user_id, tenant_id=tenant_id)

    def delete_schedule(self, schedule_id: str, *, user_id: str, tenant_id: str) -> bool:
        return self.task_services.delete_schedule(schedule_id, user_id=user_id, tenant_id=tenant_id)

    def list_schedule_runs(self, **kwargs: Any) -> list[dict[str, Any]]:
        return self.task_services.list_schedule_runs(**kwargs)

    def get_schedule_metrics(self, **kwargs: Any) -> dict[str, Any]:
        return self.task_services.get_schedule_metrics(**kwargs)

    def run_schedule_now(self, schedule_id: str, *, user_id: str, tenant_id: str) -> Optional[dict[str, Any]]:
        return self.task_services.run_schedule_now(schedule_id, user_id=user_id, tenant_id=tenant_id)

    def _submit_scheduled_task(self, schedule: ScheduledTaskRecord, occurrence: ScheduledTaskRunRecord) -> dict[str, Any]:
        return self.task_services.submit_scheduled_task(schedule, occurrence)

    def _execute_agent_task(self, context: TaskExecutionContext) -> dict[str, Any]:
        return self.task_services.execute_agent_task(context)

    def get_task(self, *args: Any, **kwargs: Any) -> Optional[dict[str, Any]]:
        return self.task_services.get_task(*args, **kwargs)

    def list_tasks(self, *args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        return self.task_services.list_tasks(*args, **kwargs)

    def get_monitoring_snapshot(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return self.task_services.get_monitoring_snapshot(*args, **kwargs)

    def pause_task(self, *args: Any, **kwargs: Any) -> Optional[dict[str, Any]]:
        return self.task_services.pause_task(*args, **kwargs)

    def resume_task(self, *args: Any, **kwargs: Any) -> Optional[dict[str, Any]]:
        return self.task_services.resume_task(*args, **kwargs)

    def recover_task(self, *args: Any, **kwargs: Any) -> Optional[dict[str, Any]]:
        return self.task_services.recover_task(*args, **kwargs)

    def cancel_task(self, *args: Any, **kwargs: Any) -> Optional[dict[str, Any]]:
        return self.task_services.cancel_task(*args, **kwargs)


    def _build_skill_context_from_metadata(
        self, session: Optional["SessionContext"] = None
    ) -> dict[str, Any]:
        """Return the current advisory context without adding a new registry."""
        if session is not None:
            value = session.ctx.metadata.get("skill_context")
            if isinstance(value, dict):
                return value
        return {}

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
        """Execute one turn through the business-neutral Runtime Kernel."""
        return self._runtime_kernel.run(
            TurnRequest(
                user_input=user_input,
                session_id=session_id,
                user_id=user_id,
                tenant_id=tenant_id or "default",
                # The generic Kernel treats this envelope as opaque. Only
                # this advertising composition root interprets its fields.
                context={
                    "account_id": account_id,
                    "credentials": credentials,
                    "platform_params": platform_params,
                    "confirmed": confirmed,
                    "confirmation_payload": confirmation_payload,
                    "creation_blueprint_id": creation_blueprint_id,
                    "creation_blueprint_version": creation_blueprint_version,
                },
                principal=principal,
                cancellation_event=cancellation_event,
                event_callback=event_callback,
                execution_mode=execution_mode,
                task_id=task_id,
            )
        )

    def _execute_kernel_request(self, request: TurnRequest) -> dict:
        """Adapt the generic kernel request to the application turn engine."""
        request_context = request.context if isinstance(request.context, Mapping) else {}
        principal = request.principal
        permissions = (
            principal.permissions
            if principal is not None else self._granted_permissions
        )
        account_scope = principal.account_scope if principal is not None else None
        result = self._run_unlocked(
            user_input=request.user_input,
            session_id=request.session_id,
            user_id=request.user_id,
            account_id=request_context.get("account_id"),
            credentials=request_context.get("credentials"),
            platform_params=request_context.get("platform_params"),
            confirmed=bool(request_context.get("confirmed", False)),
            confirmation_payload=request_context.get("confirmation_payload"),
            creation_blueprint_id=request_context.get("creation_blueprint_id"),
            creation_blueprint_version=request_context.get("creation_blueprint_version"),
            granted_permissions=permissions,
            account_scope=account_scope,
            tenant_id=request.tenant_id,
            cancellation_event=request.cancellation_event,
            lease_lost_event=request.lease_lost_event,
            event_callback=request.event_callback,
            task_id=request.task_id,
        )
        if request.lease_lost_event is not None and request.lease_lost_event.is_set():
            # The application run may already have crossed a provider side
            # effect boundary. Persist uncertainty, never a retryable success.
            signals = dict(result.get("runtime_signals") or {}) if isinstance(result, dict) else {}
            signals["session_lease_lost"] = True
            if isinstance(result, dict):
                result["runtime_signals"] = signals
                run_id = result.get("run_id")
                updater = getattr(self._session_manager, "update_execution_run", None)
                if run_id and callable(updater):
                    updater(
                        str(run_id), status="recovery_required",
                        metadata={"provider_state": "unknown", "session_lease_lost": True},
                    )
        return result

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

    def _run_unlocked(self, *args: Any, **kwargs: Any) -> dict:
        """Delegate the application workflow to AdAgentTurnEngine."""
        from .ad_turn_engine import execute

        return execute(self, *args, **kwargs)
# ─── Session 管理 ──────────────────────────────────────────

    @staticmethod
    def _decode_session_metadata(session: Mapping[str, Any]) -> dict[str, Any]:
        return AdConversationServices._decode_session_metadata(session)

    @staticmethod
    def _conversation_summary(
        session: Mapping[str, Any], messages: list[Mapping[str, Any]],
    ) -> dict[str, Any]:
        return AdConversationServices._conversation_summary(session, messages)

    def list_conversations(self, *args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        return self.conversation_services.list_conversations(*args, **kwargs)

    def rename_conversation(self, *args: Any, **kwargs: Any) -> Optional[dict[str, Any]]:
        return self.conversation_services.rename_conversation(*args, **kwargs)

    def search_knowledge(self, *args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        return self.conversation_services.search_knowledge(*args, **kwargs)

    def catalog_knowledge(self, *args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        return self.conversation_services.catalog_knowledge(*args, **kwargs)

    def summarize_knowledge(self, *args: Any, **kwargs: Any) -> str:
        return self.conversation_services.summarize_knowledge(*args, **kwargs)

    def get_conversation(self, *args: Any, **kwargs: Any) -> Optional[dict[str, Any]]:
        return self.conversation_services.get_conversation(*args, **kwargs)

    @staticmethod
    def _execution_run_dict(record: Any) -> Optional[dict[str, Any]]:
        return AdConversationServices._execution_run_dict(record)

    def _bind_execution_run_workflow(self, *args: Any, **kwargs: Any) -> None:
        self.conversation_services._bind_execution_run_workflow(*args, **kwargs)

    def get_latest_run(self, *args: Any, **kwargs: Any) -> Optional[dict[str, Any]]:
        return self.conversation_services.get_latest_run(*args, **kwargs)

    def get_run_events(self, *args: Any, **kwargs: Any) -> Optional[dict[str, Any]]:
        return self.conversation_services.get_run_events(*args, **kwargs)

    def delete_conversation(self, *args: Any, **kwargs: Any) -> bool:
        return self.conversation_services.delete_conversation(*args, **kwargs)

    def delete_conversations(self, *args: Any, **kwargs: Any) -> list[str]:
        return self.conversation_services.delete_conversations(*args, **kwargs)



    def _ensure_session(
        self,
        session_id: str,
        user_id: str,
        account_id: str,
        credentials: dict,
        tenant_id: str = "default",
    ) -> "SessionContext":
        return self.session_services.ensure_session(
            session_id, user_id, account_id, credentials, tenant_id=tenant_id,
        )

    def _refresh_session_for_turn(
        self, session_id: str, user_id: str, account_id: Optional[str],
        credentials: Optional[dict], tenant_id: str = "default",
    ) -> "SessionContext":
        return self.session_services.refresh_session_for_turn(
            session_id, user_id, account_id, credentials, tenant_id=tenant_id,
        )



    def get_workflow(self, *args: Any, **kwargs: Any) -> Optional[dict[str, Any]]:
        return self.workflow_services.get_workflow(*args, **kwargs)

    def get_workflow_resume_plan(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return self.workflow_services.get_workflow_resume_plan(*args, **kwargs)

    def _is_stale_workflow(self, workflow: Mapping[str, Any]) -> bool:
        return self.workflow_services._is_stale_workflow(workflow)

    def list_resumable_workflows(self, *args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        return self.workflow_services.list_resumable_workflows(*args, **kwargs)

    def reconcile_workflow(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return self.workflow_services.reconcile_workflow(*args, **kwargs)

    def reconcile_workflow_from_provider(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return self.workflow_services.reconcile_workflow_from_provider(*args, **kwargs)

    def cancel_workflow(self, *args: Any, **kwargs: Any) -> bool:
        return self.workflow_services.cancel_workflow(*args, **kwargs)
