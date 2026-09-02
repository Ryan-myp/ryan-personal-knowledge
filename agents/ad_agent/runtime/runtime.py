"""
runtime/runtime.py - Agent Runtime 主循环

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
import copy
import re
import hashlib
import hmac
import threading
import logging
import importlib.util
import inspect
from pathlib import Path
from types import MappingProxyType
from typing import Any, Iterable, Mapping, Optional
from dataclasses import dataclass, field
from datetime import datetime

from ..core.interfaces import (
    ToolContext, ToolResult, CapabilityModule,
    CapabilityRuntime, ToolRegistry, WriteGuard, IntentParser, IntentRouter,
    ParsedIntent, ToolEffect, ExecutionMode, ProviderReconciler,
    ReconciliationContext, ReconciliationObservation, ResourceResult,
    AdFormatCoverage,
)
from ..core.tool_registry import GuardedToolRegistry, SimpleToolRegistry, validate_tool_input
from ..core.intent import LLMIntentParser, SimpleIntentRouter
from ..core.features import RuntimeFeature
from ..core.execution_plan import ExecutionPlan
from ..core.execution_trace import ExecutionTrace, ExecutionEventCallback
from ..core.response import ResponseRenderer, ResponseSynthesizer, LLMResponseSynthesizer
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
from ..core.knowledge import KnowledgeProvider, LocalMarkdownKnowledgeProvider
from ..knowledge_management import ManagedKnowledgeProvider
from ..core.memory import MemoryManager
from ..core.parameter_catalog import ParameterCatalogRegistry
from ..core.blueprint import BlueprintRegistry, BlueprintCascadeEngine
from ..core.creation_card import CreationCardBuilder
from ..core.parameter_selection import (
    ParameterSelectionSigner,
)
from ..core.auth import RequestPrincipal, normalize_account_id, normalize_platform
from ..core.security import (
    PROTECTED_INPUT_FIELDS,
)
from .skill import BaseSkill, Skill, SkillContract, SkillLoader
from .input_builder import ToolInputBuilder
from .account_context import AccountResolver
from .services import RuntimeServices
from .workflow import WorkflowCoordinator
from .account_policy import AccountWhitelistValidator
from .session_context import SessionContext
from .capability_context import CapabilityContextWrapper
from .security import RuntimeSecurity
from .tool_executor import ToolExecutor
from .task_executor import TaskExecutionContext, TaskExecutor
from ..persistence.session_manager import SessionManager
from ..persistence.interfaces import PersistenceBackend
from ..persistence.models import ToolCallRecord
from .reconciliation import ToolReadbackReconciler

logger = logging.getLogger(__name__)


# ─── Agent Runtime ─────────────────────────────────────────────

class AgentRuntime:
    """
    单 Agent + 多 Skills 的主运行时。
    
    架构层次：
    ┌─────────────────────────────────────────┐
    │  AgentRuntime（主循环）                   │
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
        # A production Agent is model-backed by definition.  Tests and
        # explicitly offline tooling may opt into the legacy rule parser with
        # ``require_llm=False``; the default must never silently degrade.
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
        self.require_llm = bool(require_llm)
        self.intent_parser = intent_parser or LLMIntentParser(
            llm_client, allow_rule_fallback=not self.require_llm
        )
        if self.require_llm and isinstance(self.intent_parser, LLMIntentParser):
            # An explicitly supplied LLMIntentParser must obey the Runtime's
            # production boundary too; it cannot silently fall back to rules.
            self.intent_parser.allow_rule_fallback = False
        self.intent_router = intent_router or SimpleIntentRouter()
        self.write_guard = write_guard
        self.skill_loader = SkillLoader(skill_roots)
        self.skill_loader.load_all()
        self._llm = llm_client
        self.conversation_title_generator = ConversationTitleGenerator()
        # A caller may inject an already-configured LLMIntentParser instead
        # of passing the model separately.  Treat that parser-owned model as
        # the same model-backed Agent dependency; otherwise the strict
        # startup gate would reject a valid LLM configuration while checking
        # only the Runtime field.
        if self._llm is None and isinstance(self.intent_parser, LLMIntentParser):
            self._llm = getattr(self.intent_parser, "_llm", None)
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
        self.response_renderer: ResponseRenderer = (
            response_renderer or discover_response_renderer()
        )
        if self.response_renderer is None:
            raise RuntimeError("no response renderer is registered")
        self.response_synthesizer: Optional[ResponseSynthesizer] = (
            response_synthesizer
            if response_synthesizer is not None
            else (LLMResponseSynthesizer() if self._llm is not None else None)
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
        self._loaded_skills: dict[str, Skill] = {}  # platform -> Skill
        # Keep exact registration ownership so multiple Skills can share a
        # platform and unload cannot rely on a non-existent ``skill.tools``
        # attribute or accidentally remove another Skill's tools.
        # ``_loaded_skills`` remains a primary-by-platform compatibility view;
        # these indexes retain every Skill for exact lifecycle operations.
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
        base_knowledge_provider = knowledge_provider or LocalMarkdownKnowledgeProvider(
            Path(__file__).resolve().parent.parent / "knowledge_base"
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
        self.services = RuntimeServices(self)
        self.input_builder = ToolInputBuilder(self.services)
        self.account_resolver = AccountResolver(self.services)
        self.policies: list[RuntimePolicy] = list(policies or [])
        if self.policies and hasattr(self.tool_selector, "set_policies"):
            self.tool_selector.set_policies(self.policies)

        if execution_mode not in {mode.value for mode in ExecutionMode}:
            raise ValueError(f"Unsupported execution_mode: {execution_mode}")
        # dry_run 是安全默认值；只有调用方显式指定 live 才允许进入真实写入分支。
        self.execution_mode = execution_mode
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
        default_permissions = {"ads.read", "ads.plan"}
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
        self._workflow_lease_owner = (
            f"runtime:{os.getpid()}:{id(self)}"
        )
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
            self._session_manager = SessionManager(persistence_store)
            if all(callable(getattr(persistence_store, method, None)) for method in (
                "save_memory", "search_memories", "delete_memory"
            )):
                self._memory_manager = MemoryManager(persistence_store)
            if self.write_guard and hasattr(self.write_guard, "bind_store"):
                self.write_guard.bind_store(persistence_store)

        # 只读模式：只注册 READ 类工具，跳过写保护检查
        self._read_only_mode = read_only_mode
        self.workflow = WorkflowCoordinator(self.services)
        self.security = RuntimeSecurity(self)
        self.tool_executor = ToolExecutor(self.services)
        self.task_executor: Optional[TaskExecutor] = None
        if persistence_store:
            self.task_executor = TaskExecutor(
                persistence_store,
                max_workers=max_task_workers,
                max_queue=max_task_queue,
                task_timeout_seconds=task_timeout_seconds,
                lease_seconds=task_lease_seconds,
                redact=self._redact_for_persistence,
            )
            # This is the only built-in task kind: it re-enters the normal
            # Agent Runtime turn boundary, so workers cannot bypass parser,
            # policy, account, approval, idempotency or audit gates.
            self.task_executor.register_handler("agent.turn", self._execute_agent_task)
            self.task_executor.start()
        if read_only_mode:
            logger.info("🔒 只读模式已启用，仅允许查询操作")

    def set_execution_mode(self, execution_mode: str) -> None:
        """设置执行模式。外部请求不能通过 user_input 修改此值。"""
        if execution_mode not in {mode.value for mode in ExecutionMode}:
            raise ValueError(f"Unsupported execution_mode: {execution_mode}")
        self.execution_mode = execution_mode

    def set_policies(self, policies: Optional[Iterable[RuntimePolicy]]) -> None:
        """Replace Skill-owned policies without interpreting their vocabulary."""
        self.policies = list(policies or [])
        setter = getattr(self.tool_selector, "set_policies", None)
        if callable(setter):
            setter(self.policies)

    def _feature_for_intent(self, intent: Any) -> Optional[RuntimeFeature]:
        """Resolve an optional domain feature through its generic contract."""
        return feature_for_intent(self.features, intent)

    def _refresh_parser_catalog(self) -> None:
        """Synchronize parser discovery data with the active Tool registry."""
        refresh = getattr(self.intent_parser, "refresh_tool_catalog", None)
        definitions = self.registry.list_all()
        if callable(refresh):
            refresh(definitions)
        elif hasattr(self.intent_parser, "register_tool_definitions"):
            self.intent_parser.register_tool_definitions(definitions)

        # Skill aliases are context metadata, but they must follow the same
        # lifecycle as their active Skill.  Provider identity itself remains
        # discovered from Tool metadata; aliases never create Tools.
        for skill in list(self._skill_objects.values()):
            if hasattr(self.intent_parser, "register_platform_aliases"):
                self.intent_parser.register_platform_aliases(
                    getattr(skill, "platform", ""),
                    getattr(skill, "platform_aliases", []) or [],
                )

    @staticmethod
    def _canonical_platform(platform: str) -> str:
        """Normalize aliases without keeping a Runtime platform registry."""
        from ..capabilities.factory import normalize_platform

        return normalize_platform(platform)

    @property
    def persistence_store(self):
        """Expose the persistence abstraction to management services."""
        return self._session_manager.store if self._session_manager else None

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
        """Call selector extensions without breaking older injected selectors."""
        builder = getattr(self.tool_selector, "build_context_for_input", None)
        if not callable(builder):
            return {"creation_blueprints": self.creation_card_builder.llm_context()}
        try:
            parameters = inspect.signature(builder).parameters.values()
        except (TypeError, ValueError):
            parameters = ()
        supports_keyword = any(
            parameter.name == "tenant_id" or parameter.kind == inspect.Parameter.VAR_KEYWORD
            for parameter in parameters
        )
        supports_extra_positional = any(
            parameter.kind == inspect.Parameter.VAR_POSITIONAL
            for parameter in parameters
        )
        context = None
        if supports_keyword:
            context = builder(
                user_input, available_tools, intent_type, tenant_id=tenant_id
            )
        elif supports_extra_positional:
            context = builder(user_input, available_tools, intent_type, tenant_id)
        else:
            context = builder(user_input, available_tools, intent_type)
        if not isinstance(context, dict):
            context = {}
        # Blueprints are bounded declarative context for the LLM. They do not
        # register Tools and cannot execute lookup/provider operations.
        context["creation_blueprints"] = self.creation_card_builder.llm_context()
        return context

    def _optimize_tool_selection(
        self, user_input: str, intent: ParsedIntent,
        available_tools: list, tenant_id: str,
    ) -> dict:
        """Invoke selector extensions without breaking older selectors."""
        optimizer = getattr(self.tool_selector, "optimize_for_llm", None)
        if not callable(optimizer):
            return {}
        try:
            parameters = inspect.signature(optimizer).parameters.values()
        except (TypeError, ValueError):
            parameters = ()
        supports_keyword = any(
            parameter.name == "tenant_id"
            or parameter.kind == inspect.Parameter.VAR_KEYWORD
            for parameter in parameters
        )
        if supports_keyword:
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
            self.response_synthesizer = LLMResponseSynthesizer()
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
    
    def register_capability(self, module: CapabilityModule) -> CapabilityRuntime:
        """Register a Capability atomically from the Runtime's perspective.

        Capability ``configure`` implementations register Tools through a
        callback, so a failure after the first Tool would otherwise leave a
        half-loaded provider in the live Registry.  Keep the rollback here,
        at the boundary that owns the derived indexes, rather than requiring
        every provider package to implement its own transaction protocol.
        """
        before_tool_names = {
            definition.name for definition in self.registry.list_all()
        }
        before_formats = copy.deepcopy(self.ad_format_catalogs)
        before_provider_versions = copy.deepcopy(self.provider_version_contracts)
        before_provider_surfaces = copy.deepcopy(self.provider_api_surfaces)
        before_blueprints = self.creation_blueprints.snapshot()
        try:
            runtime = self._register_capability_unchecked(module)
            platform = self._canonical_platform(getattr(module, "platform_name", ""))
            if platform:
                self._register_builtin_plugin(
                    f"capability:{platform}",
                    module,
                    (PluginKind.CAPABILITY.value, PluginKind.TOOL_PROVIDER.value),
                    version=str(
                        getattr(module, "capability_version", "1.0.0") or "1.0.0"
                    ),
                    description=f"Provider capability {platform}",
                )
            return runtime
        except Exception:
            current_tool_names = {
                definition.name for definition in self.registry.list_all()
            }
            added_tool_names = current_tool_names - before_tool_names
            for name in added_tool_names:
                self.registry.unregister(name)
            self.parameter_catalogs.remove_tools(list(added_tool_names))

            # Normally ownership indexes are written only after all metadata
            # validation succeeds.  Remove them defensively as well so a
            # future failure in the final parser refresh cannot leave an
            # unloadable Skill marker behind.
            for skill_key, tool_names in list(self._skill_tool_names.items()):
                if not (set(tool_names) & added_tool_names):
                    continue
                platform = self._skill_platforms.pop(skill_key, None)
                self._skill_tool_names.pop(skill_key, None)
                self._skill_objects.pop(skill_key, None)
                self._skill_format_ids.pop(skill_key, None)
                if platform:
                    canonical = self._canonical_platform(platform)
                    keys = [
                        key for key in self._skill_keys_by_platform.get(canonical, [])
                        if key != skill_key
                    ]
                    if keys:
                        self._skill_keys_by_platform[canonical] = keys
                    else:
                        self._skill_keys_by_platform.pop(canonical, None)
                        self._loaded_skills.pop(canonical, None)
            self.ad_format_catalogs = before_formats
            self.provider_version_contracts = before_provider_versions
            self.provider_api_surfaces = before_provider_surfaces
            self.creation_blueprints.restore(before_blueprints)
            platform = self._canonical_platform(getattr(module, "platform_name", ""))
            if platform:
                self.plugin_registry.unregister(f"capability:{platform}")
            try:
                self._refresh_parser_catalog()
            except Exception:
                logger.exception("Capability rollback could not refresh parser catalog")
            raise

    def _register_capability_unchecked(
        self, module: CapabilityModule
    ) -> CapabilityRuntime:
        """
        注册一个 CapabilityModule。
        
        对应 DAP Agent 的 CapabilityModule.Configure() 模式：
        业务模块不直接操作 Runtime，而是通过接口注入能力。
        """
        before_tool_names = {
            definition.name for definition in self.registry.list_all()
        }
        context = CapabilityContextWrapper(self.registry)
        runtime = module.configure(context)

        # Publish provider parameter options as data owned by the Capability.
        # Existing tools get enum/lookup discovery automatically; a future
        # Skill can additionally provide richer versioned catalogs through the
        # CapabilityRuntime extension field.
        for definition in self.registry.list_all():
            self.parameter_catalogs.register_tool_schema(
                definition.platform,
                getattr(definition.input_schema, "properties", {})
                if definition.input_schema else {},
                tool_name=definition.name,
            )
        self.parameter_catalogs.register_many(
            getattr(runtime, "parameter_catalogs", []) or []
        )
        platform = self._canonical_platform(getattr(module, "platform_name", ""))
        blueprints = getattr(runtime, "creation_blueprints", []) or []
        if blueprints:
            self.creation_blueprints.register_many(
                blueprints,
                owner=platform or None,
                tool_registry=self.registry,
            )
        self._register_ad_format_catalog(
            getattr(module, "platform_name", "") or "",
            getattr(runtime, "ad_format_catalogs", []) or [],
        )
        provider_contract_getter = getattr(module, "get_provider_version_contract", None)
        if callable(provider_contract_getter):
            platform = self._canonical_platform(getattr(module, "platform_name", ""))
            if platform:
                self.provider_version_contracts[platform] = copy.deepcopy(
                    provider_contract_getter()
                )
        provider_surface_getter = getattr(module, "get_api_surface", None)
        if callable(provider_surface_getter):
            platform = self._canonical_platform(getattr(module, "platform_name", ""))
            if platform:
                self.provider_api_surfaces[platform] = copy.deepcopy(
                    provider_surface_getter()
                )
        self._validate_parameter_lookup_contract()
        # Capability.configure() registers platform tools before returning.
        # Apply the read-only boundary immediately so callers cannot forget a
        # second, manually-invoked enable_read_only_mode() call.
        if self._read_only_mode:
            self._filter_write_tools()

        # Keep the Parser's language catalog derived from the actual Registry
        # rather than from a central intent table.  Custom parsers may ignore
        # this optional extension seam.
        if hasattr(self.intent_parser, "register_tool_definitions"):
            self.intent_parser.register_tool_definitions(self.registry.list_all())

        # Register executable tools supplied by the Capability.  Tool metadata
        # is the routing contract; no workflow file is consulted here.
        capability_platform = getattr(module, "platform_name", None)
        # A Capability registration already activated the platform's tools.
        # Keep the declarative Skill as the platform lifecycle marker so the
        # next turn does not try to register the same tools again.
        if capability_platform:
            canonical_platform = self._canonical_platform(capability_platform)
            skill_candidates = self.skill_loader.get_by_platform(canonical_platform)
            if skill_candidates:
                primary_skill = skill_candidates[0]
                self._loaded_skills.setdefault(canonical_platform, primary_skill)
                skill_key = str(getattr(primary_skill, "name", "") or canonical_platform)
            else:
                primary_skill = None
                skill_key = f"{canonical_platform}:capability:{id(module)}"
            registered_names = sorted(
                definition.name
                for definition in self.registry.list_all()
                if definition.name not in before_tool_names
            )
            if registered_names:
                self._skill_tool_names[skill_key] = registered_names
                self._skill_platforms[skill_key] = canonical_platform
                if primary_skill is not None:
                    self._skill_objects[skill_key] = primary_skill
                self._skill_keys_by_platform.setdefault(canonical_platform, []).append(
                    skill_key
                )
                self._skill_format_ids[skill_key] = {
                    str(item.get("format_id"))
                    for item in (getattr(runtime, "ad_format_catalogs", []) or [])
                    if isinstance(item, dict) and item.get("format_id")
                }

        # Rebuild derived discovery state after ownership has been recorded.
        # This is the same lifecycle boundary used by unload_skill().
        self._refresh_parser_catalog()
        
        # 注册后台任务
        self._background_tasks.extend(runtime.background_tasks)
        
        # 注册写入保护
        if runtime.write_guard:
            self.write_guard = runtime.write_guard
            if self._session_manager and hasattr(self.write_guard, "bind_store"):
                self.write_guard.bind_store(self._session_manager.store)

        # A caller may set credentials before registering a Capability.  Bind
        # a client only to handlers that were created without an explicit
        # client; never replace an injected fake/test/client instance.
        self._refresh_unbound_clients()
        
        return runtime

    def _register_ad_format_catalog(
        self, platform: str, catalogs: list[dict[str, Any]]
    ) -> None:
        """Validate and index a Capability's format metadata.

        The catalog is intentionally declarative.  It cannot register a
        handler, expand permissions, or enable live writes.  Duplicate IDs
        are rejected so two provider packages cannot silently disagree about
        the same format contract.
        """
        if not catalogs:
            return
        canonical = self._canonical_platform(platform)
        allowed = {item.value for item in AdFormatCoverage}
        existing = {
            str(item.get("format_id")): item
            for item in self.ad_format_catalogs.get(canonical, [])
        }
        normalized: list[dict[str, Any]] = list(
            self.ad_format_catalogs.get(canonical, [])
        )
        for item in catalogs:
            if not isinstance(item, dict):
                raise ValueError(f"{canonical}: ad format catalog entry must be an object")
            entry = dict(item)
            format_id = str(entry.get("format_id", "")).strip()
            status = str(entry.get("coverage", "")).strip().lower()
            if not format_id:
                raise ValueError(f"{canonical}: ad format catalog entry needs format_id")
            if status not in allowed:
                raise ValueError(
                    f"{canonical}.{format_id}: unsupported coverage {status!r}"
                )
            if not str(entry.get("category", "")).strip():
                raise ValueError(f"{canonical}.{format_id}: category is required")
            if not str(entry.get("resource_type", "")).strip():
                raise ValueError(f"{canonical}.{format_id}: resource_type is required")
            tool_names = entry.get("tool_names", []) or []
            if not isinstance(tool_names, list) or not all(
                isinstance(name, str) and name for name in tool_names
            ):
                raise ValueError(f"{canonical}.{format_id}: tool_names must be a string list")
            entry["format_id"] = format_id
            entry["coverage"] = status
            entry["tool_names"] = list(dict.fromkeys(tool_names))
            entry["live_support"] = bool(entry.get("live_support", False))
            registered_tools = {
                definition.name for definition in self.registry.list_all()
            }
            missing_tools = sorted(set(entry["tool_names"]) - registered_tools)
            if missing_tools:
                raise ValueError(
                    f"{canonical}.{format_id}: unknown tool_names: {', '.join(missing_tools)}"
                )
            if entry["live_support"]:
                raise ValueError(
                    f"{canonical}.{format_id}: ad-format live_support must remain false; "
                    "live enablement is a separate deployment approval"
                )
            if status == AdFormatCoverage.SUPPORTED_DRY_RUN.value and not entry.get(
                "payload_adapter"
            ):
                raise ValueError(
                    f"{canonical}.{format_id}: supported_dry_run needs payload_adapter"
                )
            previous = existing.get(format_id)
            if previous is not None and previous != entry:
                raise ValueError(f"{canonical}.{format_id}: conflicting catalog entry")
            if previous is None:
                existing[format_id] = entry
                normalized.append(entry)
        self.ad_format_catalogs[canonical] = normalized

    def list_ad_formats(
        self, platform: Optional[str] = None, coverage: Optional[str] = None
    ) -> list[dict[str, Any]]:
        """Return JSON-safe format coverage metadata for UI/planners."""
        if coverage is not None:
            coverage = str(coverage).strip().lower()
            if coverage not in {item.value for item in AdFormatCoverage}:
                raise ValueError(f"unsupported ad format coverage: {coverage}")
        platforms = [self._canonical_platform(platform)] if platform else sorted(
            self.ad_format_catalogs
        )
        result: list[dict[str, Any]] = []
        for current in platforms:
            for entry in self.ad_format_catalogs.get(current, []):
                if coverage and entry.get("coverage") != coverage:
                    continue
                result.append({"platform": current, **dict(entry)})
        return result

    def list_parameter_options(
        self, platform: Optional[str] = None, field: Optional[str] = None,
        tool_name: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Return JSON-safe static or dynamic provider parameter metadata."""
        return [
            catalog.to_dict()
            for catalog in self.parameter_catalogs.list(
                platform=platform, field=field, tool_name=tool_name
            )
        ]

    def list_creation_blueprints(
        self, provider: Optional[str] = None, ad_format: Optional[str] = None,
        selector_dimension: Optional[str] = None, selector_value: Any = None,
    ) -> list[dict[str, Any]]:
        """Return provider-owned creation metadata without making network calls."""
        return self.creation_blueprints.to_dict(
            provider, ad_format, selector_dimension, selector_value
        )

    def resolve_creation_blueprint(
        self,
        provider: str,
        *,
        selector_values: Optional[Mapping[str, Any]] = None,
        values: Optional[Mapping[str, Any]] = None,
        version: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        """Resolve provider-owned creation metadata from declarative selectors."""
        blueprint = self.creation_blueprints.resolve(
            provider,
            selector_values=selector_values,
            values=values,
            version=version,
        )
        return blueprint.to_dict() if blueprint is not None else None

    def evaluate_creation_blueprint(
        self,
        blueprint_id: str,
        values: Mapping[str, Any],
        *,
        version: Optional[str] = None,
        previous_values: Optional[Mapping[str, Any]] = None,
        changed_fields: Optional[Iterable[str]] = None,
    ) -> dict[str, Any]:
        """Evaluate cascade state for a registered Blueprint deterministically."""
        blueprint = self.creation_blueprints.get(blueprint_id, version)
        if blueprint is None:
            raise KeyError(f"creation blueprint not found: {blueprint_id}@{version or 'latest'}")
        return self.blueprint_cascade.evaluate(
            blueprint,
            values,
            previous_values=previous_values,
            changed_fields=changed_fields,
        )

    def build_creation_ui(self, intent: ParsedIntent) -> dict[str, Any]:
        """Build safe conversational creation cards without executing Tools."""
        try:
            cards = self.creation_card_builder.build(intent)
        except Exception:
            logger.exception("构建广告创建参数卡失败")
            cards = []
        if not cards:
            return {}
        return self._redact_for_persistence({
            "cards": cards,
            "schema_version": "1.0",
            "needs_input": any(
                bool(card.get("missing_fields") or card.get("invalid_fields"))
                for card in cards
            ),
        })

    def _creation_blueprint_tool_plan(
        self,
        blueprint_id: Optional[str],
        blueprint_version: Optional[str],
        intent: ParsedIntent,
    ) -> tuple[Optional[dict[str, list[Any]]], Optional[str]]:
        """Resolve a submitted Blueprint into its declared Tool composition.

        A form submission is a structured continuation of an earlier turn.
        Re-parsing its short UI label can select one leaf Tool (for example an
        ad) instead of the Blueprint's complete parent-to-child chain. The
        Blueprint remains the source of composition; this method only reads
        its already-validated Tool references and never contains provider
        names or business field branches.
        """
        if not blueprint_id:
            return None, None
        blueprint = self.creation_blueprints.get(blueprint_id, blueprint_version)
        if blueprint is None:
            return None, f"广告创建蓝图不存在：{blueprint_id}@{blueprint_version or 'latest'}"
        requested_platforms = {
            self._canonical_platform(platform)
            for platform in (getattr(intent, "platforms", []) or [])
        }
        blueprint_platform = self._canonical_platform(blueprint.provider)
        if requested_platforms and requested_platforms != {blueprint_platform}:
            return None, "广告创建蓝图与当前请求的平台不一致，请重新打开对应向导。"
        definitions = []
        missing_tools = []
        for tool_name in blueprint.tools:
            try:
                definition, _handler = self.registry.get(tool_name)
            except (KeyError, LookupError):
                missing_tools.append(str(tool_name))
                continue
            if self._canonical_platform(definition.platform) != blueprint_platform:
                missing_tools.append(str(tool_name))
                continue
            definitions.append(definition)
        if missing_tools:
            return None, "广告创建蓝图依赖的能力暂不可用：" + ", ".join(missing_tools[:8])
        if not definitions:
            return None, "广告创建蓝图没有可用的创建能力。"
        ordered = SimpleIntentRouter._order_by_resource_dependencies(definitions)
        return {blueprint_platform: ordered}, None

    @staticmethod
    def creation_ui_reply(ui: Mapping[str, Any]) -> str:
        """Business-facing copy for an incomplete creation draft."""
        cards = ui.get("cards") if isinstance(ui, Mapping) else []
        titles = [
            str(card.get("title") or "广告创建")
            for card in cards or []
            if isinstance(card, Mapping)
        ]
        selector_cards = [
            card for card in cards or []
            if isinstance(card, Mapping) and card.get("type") == "ad_creation_selector"
        ]
        if selector_cards:
            provider = str(selector_cards[0].get("provider") or "目标平台")
            return (
                f"我已经识别到你要在 {provider} 创建广告。"
                "创建之前还需要你：请提供要操作的广告账户 ID，并在下方选择推广目标或广告类型；"
                "选定后，我会只展示与该类型匹配的参数。"
            )
        subject = titles[0] if len(titles) == 1 else "广告创建参数"
        pending_labels: list[str] = []
        invalid_labels: list[str] = []
        account_missing = False
        for card in cards or []:
            if not isinstance(card, Mapping):
                continue
            account_missing = account_missing or bool(
                card.get("account_required") and not str(card.get("account_id") or "").strip()
            )
            invalid_paths = {str(path) for path in (card.get("invalid_fields") or [])}
            for field in card.get("fields") or []:
                if not isinstance(field, Mapping) or field.get("visible") is False:
                    continue
                path = str(field.get("path") or "")
                label = str(field.get("label") or path or "参数")
                value = field.get("value")
                is_empty = value in (None, "", [], {})
                if path in invalid_paths or field.get("state") == "invalid":
                    if label not in invalid_labels:
                        invalid_labels.append(label)
                elif field.get("required") and is_empty and label not in pending_labels:
                    pending_labels.append(label)

        # Keep account scope visible even when the Blueprint has no other
        # missing fields. It is a user decision, not an inferred default.
        if account_missing:
            pending_labels.insert(0, "广告账户 ID")
        pending_labels = list(dict.fromkeys(pending_labels))
        invalid_labels = list(dict.fromkeys(invalid_labels))
        visible_labels = (pending_labels + invalid_labels)[:8]
        remaining = len(pending_labels) + len(invalid_labels) - len(visible_labels)
        detail = "、".join(visible_labels)
        if remaining > 0:
            detail += f"等另外 {remaining} 项"
        if invalid_labels:
            action = "请先调整标记为需要修改的参数"
        elif pending_labels:
            action = "请在下方卡片中选择或填写这些内容"
        else:
            action = "你可以先查看下方预览"
        if detail:
            action += f"：{detail}"
        return (
            f"我已经识别到你要创建{subject}，并把平台规则、广告类型和可联动的参数整理到下方卡片。"
            f"{action}。填写完整后，我会先展示最终预览，只有你确认后才会提交创建。"
        )

    def _creation_contract_preflight(
        self,
        intent: ParsedIntent,
        tool_plan: Mapping[str, Iterable[Any]],
        session: "SessionContext",
        account_id: str,
    ) -> list[dict[str, Any]]:
        """Validate the complete creation chain before any Tool is executed.

        Parent IDs are generated by the preceding create step at execution
        time, so they receive a bounded planning placeholder here. All user
        and provider-contract fields are still validated against the actual
        Tool schema, including minItems and conditional requirements. This
        keeps an invalid child creative from partially creating its parents.
        """
        issues: list[dict[str, Any]] = []
        original_account = session.ctx.account_id
        session.ctx.account_id = account_id
        try:
            for platform, tools in tool_plan.items():
                actual_platform = self._canonical_platform(platform)
                for tool_def in tools:
                    if not tool_def.is_write_tool or not tool_def.input_schema:
                        continue
                    tool_input = self.input_builder.build(
                        tool_def, intent, platform, session.ctx
                    )
                    unknown = tool_input.pop("_unknown_params", []) or []
                    selection_errors = tool_input.pop("_selection_errors", []) or []
                    missing = list(tool_input.pop("_missing_params", []) or [])

                    parent_field = self._parent_resource_id_field_for_tool(tool_def)
                    if parent_field in missing:
                        # The parent create Tool will supply this ID. It is
                        # intentionally never exposed as a user-fillable ID.
                        tool_input[parent_field] = f"__planned_{parent_field}__"
                        missing.remove(parent_field)
                    for field_name in missing:
                        issues.append({
                            "tool": tool_def.name,
                            "platform": actual_platform,
                            "field": str(field_name),
                            "message": f"Missing required field: {field_name}",
                        })
                    for field_name in unknown:
                        issues.append({
                            "tool": tool_def.name,
                            "platform": actual_platform,
                            "field": str(field_name),
                            "message": f"Field '{field_name}' is not allowed",
                        })
                    for message in selection_errors:
                        issues.append({
                            "tool": tool_def.name,
                            "platform": actual_platform,
                            "field": "selection",
                            "message": str(message),
                        })
                    schema_errors = validate_tool_input(
                        tool_def.input_schema,
                        tool_input,
                        include_provider_contract=True,
                    )
                    for message in schema_errors:
                        field_match = re.search(r"Field '([^']+)'", str(message))
                        if field_match is None:
                            field_match = re.search(
                                r"Provider contract requires field:\s*([A-Za-z0-9_.-]+)",
                                str(message),
                            )
                        issues.append({
                            "tool": tool_def.name,
                            "platform": actual_platform,
                            "field": field_match.group(1) if field_match else "",
                            "message": str(message),
                        })
        finally:
            session.ctx.account_id = original_account
        return issues

    @staticmethod
    def _creation_contract_reply(
        ui: Mapping[str, Any], issues: Iterable[Mapping[str, Any]]
    ) -> str:
        """Turn schema errors into concise operator-facing corrections."""
        label_by_key: dict[tuple[str, str], str] = {}
        for card in ui.get("cards", []) if isinstance(ui, Mapping) else []:
            if not isinstance(card, Mapping):
                continue
            for field in card.get("fields", []) or []:
                if not isinstance(field, Mapping):
                    continue
                label = str(field.get("label") or field.get("path") or "参数")
                tool = str(field.get("tool") or "")
                provider_field = str(field.get("provider_field") or "")
                path = str(field.get("path") or "")
                for key in ((tool, provider_field), (tool, path), ("", provider_field), ("", path)):
                    if key[1]:
                        label_by_key.setdefault(key, label)

        details: list[str] = []
        issue_list = [item for item in issues if isinstance(item, Mapping)]
        exact_fields = {
            str(item.get("field") or "")
            for item in issue_list
        }
        for issue in issue_list:
            tool = str(issue.get("tool") or "")
            field = str(issue.get("field") or "")
            message = str(issue.get("message") or "")
            # A short item-type error (for example headlines[0] must be an
            # object) is secondary when the same field already reports its
            # actionable minimum count. Keep the operator message focused.
            if "[" in field and field.split("[", 1)[0] in exact_fields:
                continue
            label = label_by_key.get((tool, field)) or label_by_key.get(("", field))
            count_match = re.search(r"at least (\d+) items?/characters", message)
            if count_match and label:
                detail = f"{label}至少需要 {count_match.group(1)} 项"
            elif message.startswith("Missing required field:") and label:
                detail = f"请补充{label}"
            elif "Provider contract requires field:" in message and label:
                detail = f"请补充{label}"
            elif label:
                detail = f"{label}需要调整"
            else:
                detail = "有一项创建参数不符合平台要求"
            if detail not in details:
                details.append(detail)
        details = details[:8]
        return (
            "提交前检查发现以下内容还不符合当前广告类型的要求："
            + "；".join(details)
            + "。本次没有创建任何广告资源，请返回卡片补充或调整后再提交。"
        )

    def resolve_parameter_options(
        self,
        platform: str,
        field: str,
        tool_name: str,
        account_id: str,
        *,
        session_id: Optional[str] = None,
        user_id: str = "parameter-options",
        tenant_id: str = "default",
        account_scope: Optional[Mapping[str, set[str]]] = None,
        granted_permissions: Optional[set[str] | frozenset[str]] = None,
    ) -> dict[str, Any]:
        """Resolve one dynamic catalog through a registered read Tool.

        The metadata endpoint intentionally does not make network calls. This
        explicit resolver is the provider-backed counterpart for a form/UI:
        it reuses the normal account, permission, timeout and read-data
        boundaries, then returns short-lived selection tokens that are bound
        to this user/session/account/tool/field context.
        """
        actual_platform = self._canonical_platform(platform)
        catalog = self.parameter_catalogs.get(actual_platform, field, tool_name)
        if catalog is None:
            raise KeyError(
                f"parameter catalog not found for {actual_platform}.{field} ({tool_name})"
            )
        if catalog.source != "lookup":
            return catalog.to_dict()
        source_tool = str(catalog.lookup_tool or "")
        definition, _handler = self._get_registered_tool(source_tool)
        if not definition.is_read_tool:
            raise PermissionError("parameter lookup source must be read-only")
        if self._canonical_platform(definition.platform) != actual_platform:
            raise ValueError("parameter lookup source belongs to a different platform")
        if not account_id:
            raise ValueError("dynamic parameter lookup requires account_id")
        allowed, account_error = self._validate_account_with_principal(
            actual_platform, str(account_id), False, account_scope
        )
        if not allowed:
            raise PermissionError(account_error)
        permissions = self._granted_permissions if granted_permissions is None else frozenset(granted_permissions)
        permission_error = self._check_tool_permissions(definition, permissions)
        if permission_error:
            raise PermissionError(permission_error)

        session = self._ensure_session(
            session_id or str(uuid.uuid4()), user_id, str(account_id),
            None, tenant_id=tenant_id,
        )
        session.ctx.account_id = str(account_id)
        input_data: dict[str, Any] = {}
        properties = getattr(definition.input_schema, "properties", {}) or {}
        for account_field in ("account_id", "advertiser_id", "customer_id"):
            if account_field in properties:
                input_data[account_field] = str(account_id)
                break
        result = self.tool_executor.execute(session.ctx, source_tool, input_data)
        result = self.input_builder.decorate_lookup_result(
            definition, result, session.ctx, actual_platform
        )
        result = self.security.enforce_result_limit(result, definition)
        if not result.success:
            raise RuntimeError(result.error or "parameter lookup failed")
        for selection in result.data.get("parameter_selections", []):
            if (
                selection.get("tool_name") == tool_name
                and selection.get("field") == field
            ):
                return selection
        raise RuntimeError(
            f"provider lookup {source_tool} returned no options for {tool_name}.{field}"
        )

    def _validate_parameter_lookup_contract(self) -> None:
        """Ensure dynamic fields point to executable same-provider read tools.

        A lookup descriptor is part of the Skill contract, not a free-form
        hint. Failing at registration keeps a typo or a write-tool reference
        from reaching the UI as a selectable option that Runtime cannot
        safely attest later.
        """
        definitions = {tool.name: tool for tool in self.registry.list_all()}
        errors: list[str] = []
        for tool in definitions.values():
            properties = getattr(tool.input_schema, "properties", {}) or {}
            for field_name, field_schema in properties.items():
                lookup_tool = self.input_builder.lookup_tool_for_schema_field(
                    field_schema
                )
                if not lookup_tool:
                    continue
                source = definitions.get(lookup_tool)
                if source is None:
                    errors.append(
                        f"{tool.name}.{field_name} references unknown lookup tool {lookup_tool}"
                    )
                    continue
                tool_platform = self._canonical_platform(tool.platform)
                source_platform = self._canonical_platform(source.platform)
                if tool_platform != source_platform:
                    errors.append(
                        f"{tool.name}.{field_name} lookup tool {lookup_tool} "
                        f"belongs to {source_platform}, not {tool_platform}"
                    )
                if not source.is_read_tool:
                    errors.append(
                        f"{tool.name}.{field_name} lookup tool {lookup_tool} must be read-only"
                    )
        if errors:
            raise ValueError("Invalid parameter lookup contract: " + "; ".join(errors[:20]))

    def _register_skill(self, skill: Skill) -> None:
        """将 Skill 的工具注册到 Registry"""
        if hasattr(self.intent_parser, "register_platform_aliases"):
            self.intent_parser.register_platform_aliases(
                getattr(skill, "platform", ""),
                getattr(skill, "platform_aliases", []) or [],
            )
        registered_names: list[str] = []
        for tool_def in skill.get_tools():
            skill_platform = self._canonical_platform(skill.platform)
            tool_platform = self._canonical_platform(tool_def.platform)
            if skill.platform != "multi_platform" and tool_platform != skill_platform:
                raise ValueError(
                    f"Tool '{tool_def.name}' platform '{tool_platform}' "
                    f"does not match Skill platform '{skill_platform}'"
                )
            if self._read_only_mode and tool_def.is_write_tool:
                continue
            handler = skill.get_tool_handler(tool_def.name)
            if handler:
                self.registry.register(tool_def, handler)
                registered_names.append(tool_def.name)
        if registered_names:
            skill_key = str(getattr(skill, "name", "") or skill.platform)
            self._skill_tool_names[skill_key] = registered_names
            self._skill_platforms[skill_key] = skill.platform
            self._skill_objects[skill_key] = skill
            platform_key = self._canonical_platform(skill.platform)
            keys = self._skill_keys_by_platform.setdefault(platform_key, [])
            if skill_key not in keys:
                keys.append(skill_key)
            if hasattr(self.intent_parser, "register_tool_definitions"):
                self.intent_parser.register_tool_definitions(
                    [self.registry.get(name)[0] for name in registered_names]
                )
    
    # ─── Skill 动态注册 ────────────────────────────────────────
    
    def register_skill(self, skill: Skill, platform: str, api_client=None) -> bool:
        """
        动态注册一个 Skill。
        
        策略：直接使用 Capability 的工具定义，而不是动态创建 Handler。
        
        Args:
            skill: Skill 对象（从 SKILL.md 解析）
            platform: 平台名称
            api_client: API 客户端（None 时使用 mock 模式）
        """
        # Dynamic Skill loading and the API/CLI path must use the same
        # canonical Capability factory.  The factory only constructs local
        # objects and does not contact a provider.
        from ..capabilities.factory import create_capability, normalize_platform
        canonical_platform = normalize_platform(platform)
        declared_platform = normalize_platform(getattr(skill, "platform", ""))
        if declared_platform and declared_platform != canonical_platform:
            raise ValueError(
                f"Skill '{getattr(skill, 'name', '')}' platform '{declared_platform}' "
                f"does not match requested platform '{canonical_platform}'"
            )
        skill_key = str(getattr(skill, "name", "") or f"{canonical_platform}:{id(skill)}")
        if skill_key in self._skill_tool_names:
            logger.info("ⓘ Skill '%s' 已加载，跳过重复注册", skill_key)
            return True
        
        # Capability is the compatibility source for built-in channel Skills.
        # A custom Skill may provide its own ToolDefinitions and handlers; in
        # that case register only the declared executable tools instead of
        # exposing every tool belonging to the platform.
        declared_tools = []
        get_tools = getattr(skill, "get_tools", None)
        get_handler = getattr(skill, "get_tool_handler", None)
        if callable(get_tools) and callable(get_handler):
            try:
                declared_tools = list(get_tools() or [])
            except Exception as exc:
                logger.warning("解析 Skill '%s' 工具声明失败: %s", skill_key, exc)

        # A custom Skill can target a new platform and provide all of its own
        # handlers.  Only built-in fallback Skills require a known Capability;
        # this keeps the extension seam genuinely Skill + Tools based.
        capability = self._discover_capability(canonical_platform, api_client)
        if capability is None:
            try:
                capability = create_capability(canonical_platform, api_client)
            except ValueError:
                if not declared_tools:
                    logger.warning("⚠️ 未找到平台 '%s' 的 Capability，且 Skill 没有声明可执行工具", platform)
                    return

        capability_tools = {
            definition.name: (definition, handler)
            for definition, handler in capability.register_tools()
        } if capability is not None else {}

        tools = []
        if declared_tools:
            for declared in declared_tools:
                declared_tool_platform = normalize_platform(
                    getattr(declared, "platform", "")
                )
                if declared_tool_platform != canonical_platform:
                    raise ValueError(
                        f"Tool '{declared.name}' platform '{declared_tool_platform}' "
                        f"does not match Skill platform '{canonical_platform}'"
                    )
                handler = get_handler(declared.name)
                if handler is None and declared.name in capability_tools:
                    # Allow a declarative channel Skill to reuse the verified
                    # provider handler while retaining the Skill's own scope.
                    _, handler = capability_tools[declared.name]
                if handler is not None:
                    tools.append((declared, handler))
            if not tools:
                logger.warning(
                    "⚠️ Skill '%s' 的工具均没有可执行 Handler，未注册",
                    skill_key,
                )
                return False
        else:
            # A declarative Skill with no executable declarations uses the
            # provider Capability for its platform's verified handlers.
            tools = list(capability_tools.values())

        if not tools:
            logger.warning(f"⚠️ Capability '{platform}' 没有定义任何工具")
            return False

        # 注册工具
        registered_count = 0
        for tool_def, handler in tools:
            tool_platform = normalize_platform(getattr(tool_def, "platform", ""))
            if tool_platform != canonical_platform:
                raise ValueError(
                    f"Tool '{tool_def.name}' platform '{tool_platform}' "
                    f"does not match Skill platform '{canonical_platform}'"
                )
            metadata_errors = tool_def.routing_metadata_errors()
            if metadata_errors:
                raise ValueError(
                    f"Skill '{skill_key}' Tool '{tool_def.name}' is missing explicit "
                    "routing metadata: " + ", ".join(metadata_errors)
                )
            if self._read_only_mode and tool_def.is_write_tool:
                continue
            if not tool_def.required_permissions:
                tool_def.required_permissions = [
                    "ads.plan" if tool_def.is_write_tool else "ads.read"
                ]
            try:
                self.registry.register(tool_def, handler)
                self.parameter_catalogs.register_tool_schema(
                    tool_def.platform,
                    getattr(tool_def.input_schema, "properties", {})
                    if tool_def.input_schema else {},
                    tool_name=tool_def.name,
                )
                registered_count += 1
                logger.debug(f"✅ 注册工具: {tool_def.name} (platform={platform})")
            except Exception as e:
                logger.warning(f"⚠️ 注册工具失败 '{tool_def.name}': {e}")
        
        if registered_count == 0:
            logger.warning("⚠️ Skill '%s' 没有实际注册任何工具", skill_key)
            return False

        self._validate_parameter_lookup_contract()
        if hasattr(self.intent_parser, "register_tool_definitions"):
            self.intent_parser.register_tool_definitions(self.registry.list_all())

        # 保存 Skill 和平台映射
        self._loaded_skills.setdefault(canonical_platform, skill)
        self._skill_tool_names[skill_key] = [tool_def.name for tool_def, _ in tools]
        self._skill_platforms[skill_key] = canonical_platform
        self._skill_objects[skill_key] = skill
        keys = self._skill_keys_by_platform.setdefault(canonical_platform, [])
        if skill_key not in keys:
            keys.append(skill_key)

        self._refresh_parser_catalog()
        self._register_builtin_plugin(
            f"skill:{skill_key}",
            skill,
            (PluginKind.SKILL.value, PluginKind.TOOL_PROVIDER.value),
            version=str(getattr(skill, "version", "1.0.0") or "1.0.0"),
            description=str(getattr(skill, "description", "") or ""),
        )

        logger.info(f"✅ 已动态注册 Skill '{skill.name}'，共 {registered_count} 个工具")
        return True

    @staticmethod
    def _verify_skill_plugin(skill_dir: Any, plugin_path: Any) -> tuple[bool, str]:
        """Verify an optional Skill manifest before importing executable code."""
        skill_dir = os.fspath(skill_dir)
        plugin_path = os.fspath(plugin_path)
        manifest_path = os.path.join(skill_dir, "skill.manifest.json")
        require_manifest = os.environ.get("AD_AGENT_REQUIRE_SKILL_MANIFEST") == "1"
        if not os.path.exists(manifest_path):
            if require_manifest:
                return False, "skill.manifest.json is required"
            return True, "manifest not configured"
        try:
            with open(manifest_path, "r", encoding="utf-8") as file:
                manifest = json.load(file)
        except (OSError, TypeError, ValueError) as exc:
            return False, f"invalid skill manifest: {exc}"
        files = manifest.get("files") if isinstance(manifest, dict) else None
        if not isinstance(files, dict):
            return False, "skill manifest files must be an object"
        relative_name = os.path.basename(plugin_path)
        expected = files.get(relative_name) or files.get(os.path.relpath(plugin_path, skill_dir))
        if not isinstance(expected, str):
            return False, f"skill manifest does not cover {relative_name}"
        digest = hashlib.sha256()
        try:
            with open(plugin_path, "rb") as file:
                for chunk in iter(lambda: file.read(1024 * 1024), b""):
                    digest.update(chunk)
        except OSError as exc:
            return False, f"cannot hash Skill plugin: {exc}"
        if not hmac.compare_digest(digest.hexdigest(), expected.lower()):
            return False, f"hash mismatch for {relative_name}"

        signing_key = os.environ.get("AD_AGENT_SKILL_MANIFEST_KEY")
        signature = manifest.get("signature") if isinstance(manifest, dict) else None
        if require_manifest and not signing_key:
            return False, "AD_AGENT_SKILL_MANIFEST_KEY is required with manifest enforcement"
        if signing_key:
            if not isinstance(signature, str) or not signature:
                return False, "signed Skill manifest is required"
            signed_payload = json.dumps(
                {
                    "skill": manifest.get("skill", os.path.basename(skill_dir)),
                    "version": manifest.get("version", "1"),
                    "files": files,
                },
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            expected_signature = hmac.new(
                signing_key.encode("utf-8"), signed_payload, hashlib.sha256
            ).hexdigest()
            if not hmac.compare_digest(signature, expected_signature):
                return False, "skill manifest signature mismatch"
        return True, "verified"

    @staticmethod
    def _load_skill_plugin(skill_dir: Any, api_client=None) -> Optional[Skill]:
        """Load an optional executable Skill plugin from a Skill directory.

        Supported convention:

        ``skills/<name>/tools.py`` or ``skills/<name>/tools/__init__.py``
        exports ``create_skill(api_client=None)`` (``get_skill`` is accepted
        as a compatibility alias).  The factory must return a Core ``Skill``
        implementation with ``get_tools`` and ``get_tool_handler`` methods.

        Importing a plugin only constructs local objects; provider I/O remains
        inside Runtime's normal execution gates.
        """
        from pathlib import Path

        skill_dir = Path(skill_dir)
        candidates = [skill_dir / "tools.py", skill_dir / "tools" / "__init__.py"]
        plugin_path = next((path for path in candidates if path.exists()), None)
        if plugin_path is None:
            return None

        verified, reason = AgentRuntime._verify_skill_plugin(skill_dir, plugin_path)
        if not verified:
            logger.error("拒绝加载 Skill plugin %s: %s", plugin_path, reason)
            return None

        module_name = "ad_agent_skill_" + hashlib.sha256(
            str(plugin_path.resolve()).encode("utf-8")
        ).hexdigest()[:16]
        try:
            spec = importlib.util.spec_from_file_location(module_name, plugin_path)
            if spec is None or spec.loader is None:
                return None
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            factory = getattr(module, "create_skill", None) or getattr(module, "get_skill", None)
            if not callable(factory):
                logger.warning("Skill plugin %s 缺少 create_skill(api_client=None)", plugin_path)
                return None
            try:
                signature = inspect.signature(factory)
            except (TypeError, ValueError):
                skill = factory(api_client)
            else:
                try:
                    signature.bind(api_client)
                except TypeError:
                    skill = factory()
                else:
                    # Do not catch TypeError from inside the factory: that is
                    # an implementation failure, not evidence of a zero-arg
                    # compatibility signature.
                    skill = factory(api_client)
            if not (
                skill is not None
                and callable(getattr(skill, "get_tools", None))
                and callable(getattr(skill, "get_tool_handler", None))
            ):
                logger.warning("Skill plugin %s 未返回可执行 Core Skill", plugin_path)
                return None
            return skill
        except Exception as exc:
            logger.warning("加载 Skill plugin %s 失败: %s", plugin_path, exc)
            return None
    
    def load_skill(self, platform: str, skill: Skill, api_client=None) -> bool:
        """
        根据平台名称加载对应的 Skill。
        
        Args:
            platform: 平台名称 (meta/google/tiktok/dv360)
            skill: Skill 对象
            api_client: API 客户端
            
        Returns:
            是否加载成功
        """
        skill_key = str(getattr(skill, "name", "") or platform)
        if skill_key in self._skill_tool_names:
            logger.info(f"ⓘ Skill '{skill_key}' 已加载，跳过")
            return True
        
        try:
            return bool(self.register_skill(skill, platform, api_client))
        except Exception as e:
            logger.error(f"❌ 加载 Skill '{platform}' 失败: {e}")
            return False
    
    def unload_skill(self, platform: str, skill_name: Optional[str] = None) -> bool:
        """
        卸载指定平台的 Skill 工具。
        
        Args:
            platform: 平台名称
            
        Returns:
            是否卸载成功
        """
        canonical_platform = self._canonical_platform(platform)
        candidates = list(self._skill_keys_by_platform.get(canonical_platform, []))
        if not candidates:
            primary = self._loaded_skills.get(canonical_platform) or self._loaded_skills.get(platform)
            if primary is not None:
                candidates = [str(getattr(primary, "name", "") or canonical_platform)]
        if not candidates and platform not in self._loaded_skills and canonical_platform not in self._loaded_skills:
            return True
        
        try:
            if skill_name:
                if skill_name not in candidates:
                    return False
                target_key = skill_name
            else:
                primary = self._loaded_skills.get(canonical_platform)
                target_key = str(getattr(primary, "name", "") or "") if primary else ""
                if target_key not in candidates:
                    target_key = candidates[0]
            tool_names = list(self._skill_tool_names.get(target_key, []))
            target_skill = self._skill_objects.get(target_key)

            # Use the registry's locking/unregister seam instead of mutating
            # private indexes directly.
            for name in dict.fromkeys(tool_names):
                self.registry.unregister(name)
            self.parameter_catalogs.remove_tools(tool_names)
            format_ids = self._skill_format_ids.pop(target_key, set())
            if format_ids:
                self.ad_format_catalogs[canonical_platform] = [
                    entry for entry in self.ad_format_catalogs.get(canonical_platform, [])
                    if str(entry.get("format_id")) not in format_ids
                ]
                if not self.ad_format_catalogs[canonical_platform]:
                    self.ad_format_catalogs.pop(canonical_platform, None)
            self._skill_tool_names.pop(target_key, None)
            self._skill_platforms.pop(target_key, None)
            self._skill_objects.pop(target_key, None)
            self.plugin_registry.unregister(f"skill:{target_key}")
            if target_skill is not None:
                self.skill_loader.unload(getattr(target_skill, "name", ""))

            remaining = [key for key in candidates if key != target_key]
            if remaining:
                self._skill_keys_by_platform[canonical_platform] = remaining
                replacement = self._skill_objects.get(remaining[0])
                if replacement is not None:
                    self._loaded_skills[canonical_platform] = replacement
            else:
                self._skill_keys_by_platform.pop(canonical_platform, None)
                self._loaded_skills.pop(canonical_platform, None)
                # Blueprints are owned by the provider Capability. Remove
                # them only after the final Skill for that platform is gone.
                self.creation_blueprints.remove_owner(canonical_platform)

            if platform != canonical_platform:
                self._loaded_skills.pop(platform, None)
            self._refresh_parser_catalog()
            logger.info(
                "✅ 已卸载 Skill '%s' (platform=%s)，移除 %s 个工具",
                target_key, canonical_platform, len(set(tool_names)),
            )
            return True
        except Exception as e:
            logger.error(f"❌ 卸载 Skill '{platform}' 失败: {e}")
            return False
    
    def get_loaded_skills(self) -> dict[str, Skill]:
        """获取所有已加载的 Skills"""
        return self._loaded_skills.copy()
    
    def get_available_skills(self) -> dict[str, Skill]:
        """获取所有可用的 Skills（包括未加载的）"""
        for skill_dir in self.skill_loader.iter_skill_dirs():
            try:
                self.skill_loader.load_skill_dir(skill_dir)
            except Exception as exc:
                logger.debug("加载可用 Skill 失败 %s: %s", skill_dir, exc)
        return self.skill_loader.list_all()
    
    def _load_required_skills(self, platforms: list[str]) -> None:
        """
        根据平台列表动态加载对应的 Skill 工具。

        Args:
            platforms: 需要加载的平台列表
        """
        if not platforms:
            return

        for platform in platforms:
            actual_platform = self._canonical_platform(platform)

            if actual_platform in self._loaded_skills:
                continue  # 已加载，跳过

            # 查找对应的 Skill
            skill = self._find_skill_by_platform(actual_platform)
            if not skill:
                logger.warning(f"未找到平台 '{actual_platform}' 的 Skill 定义")
                continue

            # 获取 API 客户端
            api_client = self._get_api_client(platform)

            # 加载 Skill
            self.load_skill(actual_platform, skill, api_client)
    
    def _find_skill_by_platform(self, platform: str) -> 'Skill':
        """
        根据平台名称查找对应的 Skill。
        
        策略：
        1. 从已加载的 Skill 中查找
        2. 从 SkillLoader 缓存中查找
        """
        # 先从已加载的 Skill 中查找
        if platform in self._loaded_skills:
            return self._loaded_skills[platform]
        canonical_platform = self._canonical_platform(platform)
        for skill_key in self._skill_keys_by_platform.get(canonical_platform, []):
            skill = self._skill_objects.get(skill_key)
            if skill is not None:
                return skill

        # SkillLoader owns recursive discovery and package validation.  Runtime
        # only asks for the loaded package by its declared platform; it does not
        # parse another copy of SKILL.md or inspect loader internals.
        candidates = self.skill_loader.get_by_platform(canonical_platform)
        if candidates:
            return candidates[0]
        return None
    
    def set_credentials(self, credentials: dict) -> None:
        """设置凭证，仅保存在进程内；绝不据此修改账户白名单。

        白名单必须来自受控配置文件，不能由线上凭证中的 account/customer ID
        自动扩大，否则会把凭证范围误当成允许操作范围。
        """
        self._credentials = copy.deepcopy(credentials or {})
        self._refresh_unbound_clients()

    def _refresh_unbound_clients(self) -> None:
        """Attach configured clients to handlers that are still offline.

        This makes ``runtime.set_credentials(...)`` and
        ``runtime.run(credentials=...)`` useful even when Capabilities were
        registered first.  Explicitly injected clients are left untouched.
        Client construction itself is side-effect free; network access only
        occurs when a read Handler is actually executed.
        """
        if not self._credentials:
            return
        clients: dict[str, Any] = {}
        for tool_def in self.registry.list_all():
            try:
                _, handler = self._get_registered_tool(tool_def.name)
            except KeyError:
                continue
            if not hasattr(handler, "client") or getattr(handler, "client") is not None:
                continue
            platform = self._canonical_platform(tool_def.platform)
            if platform not in clients:
                clients[platform] = self._get_api_client(platform)
            client = clients[platform]
            if client is not None:
                handler.client = client
    
    def _get_api_client(self, platform: str):
        """获取指定平台的 API 客户端"""
        if not self._credentials:
            return None

        # Keep provider construction in one side-effect-free factory.  The
        # previous implementation duplicated this map in Runtime and could
        # drift from the CLI/server construction path.
        credentials = self._credentials_for_platform(platform)
        if not credentials:
            return None

        try:
            from ..api_clients.factory import create_platform_client
            return create_platform_client(platform, credentials)
        except Exception as e:
            logger.debug(f"创建 {platform} API Client 失败: {e}")

        return None

    def _credentials_for_platform(
        self, platform: str, credentials: Optional[Mapping[str, Any]] = None,
    ) -> dict[str, Any]:
        """Resolve credentials by the same canonical platform identity.

        Credential dictionaries are request/application configuration, not a
        second provider registry.  Normalizing their keys lets a newly added
        Capability use its own platform ID without adding another Runtime
        branch.  The returned value is copied so callers cannot mutate the
        request envelope through a Client constructor.
        """
        source = credentials if credentials is not None else self._credentials
        if not isinstance(source, Mapping):
            return {}
        from ..capabilities.factory import normalize_platform

        wanted = normalize_platform(platform)
        for key, value in source.items():
            if normalize_platform(str(key)) == wanted and isinstance(value, dict):
                return copy.deepcopy(value)
        return {}

    @staticmethod
    def _discover_capability(platform: str, api_client: Any = None) -> Any:
        """Discover a built-in Capability by package convention.

        This keeps adding a provider out of the central Router and factory
        table. A channel package only needs
        ``capabilities/<platform>/capability.py`` and a
        ``create_<platform>_capability`` factory. Custom channels can instead
        expose executable Tools from their Skill plugin.
        """
        from ..capabilities.factory import discover_capability_factory, _call_factory

        factory = discover_capability_factory(platform)
        if not callable(factory):
            return None
        return _call_factory(factory, api_client)

    def _build_request_clients(self, credentials: Optional[dict]) -> dict[str, Any]:
        """Build per-request clients without replacing shared handlers.

        ``run(credentials=...)`` is request-scoped input. Mutating the
        Runtime's global credential/client state here would allow one user to
        affect another user's request, so these clients are passed through a
        copied Handler at execution time instead.
        """
        if not credentials:
            return {}
        from ..api_clients.factory import create_platform_client

        clients: dict[str, Any] = {}
        for raw_platform in credentials:
            platform = self._canonical_platform(str(raw_platform))
            provider_credentials = self._credentials_for_platform(platform, credentials)
            if not provider_credentials:
                continue
            try:
                client = create_platform_client(platform, provider_credentials)
                if client is not None:
                    clients[platform] = client
            except Exception as exc:
                logger.warning("创建请求级 %s client 失败: %s", platform, exc)
        return clients

    def _execute_registered_tool(
        self, ctx: ToolContext, tool_name: str, input_data: dict,
    ) -> ToolResult:
        """Execute through the registry's Runtime-only authorized seam."""
        execute = getattr(self.registry, "execute_authorized", None)
        if callable(execute):
            return execute(
                ctx, tool_name, input_data,
                _execution_token=self._registry_execution_token,
            )
        return self.registry.execute(ctx, tool_name, input_data)

    def _get_registered_tool(self, tool_name: str):
        """Get a raw tool tuple only through Runtime's guarded seam."""
        getter = getattr(self.registry, "get_authorized", None)
        if callable(getter):
            return getter(tool_name, self._registry_execution_token)
        return self.registry.get(tool_name)

    def auto_load_skills(self, skills_root: str, credentials: dict = None) -> int:
        """
        自动加载 skills 目录下的所有 Skills。
        
        策略：
        1. 按标准 Agent Skill 约定发现所有包含 SKILL.md 的目录（可在根目录或任意层级）
        2. 业务上下文 Skill 只作为策略上下文，不注册执行工具
        3. 有受控插件的 Skill 通过统一 Runtime 注册工具
        4. 没有插件但能按包约定发现 Capability 的渠道 Skill，加载该 Capability
        5. 其他 Skill 只保留为自然语言上下文，不会因文件名或 workflow.yaml 变成工具
        
        Args:
            skills_root: Skills 根目录路径
            credentials: API 凭证配置
            
        Returns:
            成功加载的 Skill 数量
        """
        loaded_count = 0
        # Reuse credentials previously installed through set_credentials()
        # when callers do not repeat them during Skill discovery. Passing an
        # explicit empty mapping still means intentionally no provider creds.
        credentials = self._credentials if credentials is None else credentials
        credentials = credentials or {}
        # 保存凭证配置
        if credentials:
            self._credentials = copy.deepcopy(credentials)

        # Keep automatic discovery on the same canonical SkillLoader used by
        # normal Runtime initialization. This publishes aliases and expert
        # context from the user's root as well; the executable plugin or
        # Capability is still the only source of Tools below.
        self.skill_loader.add_root(skills_root)
        self.skill_loader.load_all()
        
        # SkillLoader is the single source of truth for standard directory
        # discovery.  Do not infer behavior from a parent folder name: a
        # packaged Skill can be mounted at the root or nested arbitrarily.
        # Only scan the root explicitly requested by this call.  The Runtime
        # may also have its built-in Skill root registered; including it here
        # would make a caller's temporary/managed root unexpectedly register
        # all built-in Capabilities a second time.
        for skill_dir in self.skill_loader.iter_skill_dirs([skills_root]):
            try:
                    # SkillLoader owns SKILL.md parsing, standard frontmatter,
                    # duplicate detection and malformed-package isolation.
                    # Runtime consumes the validated package instead of
                    # maintaining a second YAML parser for the same contract.
                    loaded_skill = self.skill_loader.load_skill_dir(skill_dir)
                    if loaded_skill is None or bool(getattr(loaded_skill, "context_only", False)):
                        continue
                    platform = loaded_skill.platform

                    # Loading SKILL.md supplies bounded expert context. It
                    # does not register routes or executable workflow steps.

                    # Executable extensions take precedence over declarative
                    # Skill metadata.  A plugin is still
                    # subject to the same registry, schema, account and write
                    # gates as built-in capabilities.
                    api_client = None
                    provider_credentials = self._credentials_for_platform(
                        platform, credentials
                    )
                    if provider_credentials:
                        try:
                            from ..api_clients.factory import create_platform_client
                            api_client = create_platform_client(
                                platform, provider_credentials
                            )
                        except Exception as e:
                            logger.debug(f"创建 {platform} API Client 失败: {e}")
                    plugin_skill = self._load_skill_plugin(skill_dir, api_client)
                    if plugin_skill is not None:
                        before_tool_count = len(self.registry.list_all())
                        registered = self.register_skill(
                            plugin_skill, platform, api_client
                        )
                        if not registered:
                            logger.warning(
                                "⚠️ Skill plugin '%s' 未注册任何可执行工具",
                                plugin_skill.name,
                            )
                            continue
                        loaded_count += 1
                        logger.info(
                            f"✅ 自动加载 Skill plugin: {plugin_skill.name} ({platform}, "
                            f"{len(self.registry.list_all()) - before_tool_count} executable tools)"
                        )
                        continue
                    
                    # Channel capability discovery is based on package
                    # convention, not on a parent directory name or a
                    # Markdown table. Context-only Skills remain
                    # context-only because their frontmatter is handled by
                    # SkillContract as ``context_only`` and never reaches
                    # this loop.
                    try:
                        from ..capabilities.factory import create_capability
                        canonical = self._canonical_platform(platform)
                        capability = self._discover_capability(canonical, api_client)
                        if capability is None:
                            capability = create_capability(canonical, api_client)
                        before_tool_count = len(self.registry.list_all())
                        self.register_capability(capability)
                        registered_count = len(self.registry.list_all()) - before_tool_count
                        if registered_count <= 0:
                            logger.warning(
                                "⚠️ Capability '%s' 未注册任何可执行工具",
                                canonical,
                            )
                            continue
                        loaded_count += 1
                        logger.info(
                            "✅ 自动加载 Capability: %s (%s, %s executable tools)",
                            platform,
                            platform,
                            registered_count,
                        )
                    except ValueError:
                        # A normal advisory Skill may have no executable
                        # Capability. That is expected and must not make a
                        # package layout convention mandatory.
                        logger.debug("未找到平台 Capability: %s", platform)
            except Exception as e:
                logger.warning(f"⚠️ 解析 Skill {skill_dir.name}/SKILL.md 失败: {e}")
        
        logger.info(f"✅ 自动加载完成，共加载 {loaded_count} 个 Skills")
        return loaded_count
    
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
        normalized = AgentRuntime._canonical_platform(platform)
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

    @staticmethod
    def _resource_id_field(resource_type: str) -> str:
        # Kept as a compatibility helper for callers that need a neutral
        # result key. Provider/Skill Tools must declare the actual wire field
        # through ``resource_id_field``; Core must not turn a logical resource
        # type into a provider field name.
        return "resource_id"

    @classmethod
    def _resource_id_field_for_tool(cls, tool_def: Any) -> str:
        """Resolve the provider resource ID from the Tool contract.

        A provider with a different wire name publishes
        ``resource_id_field`` on its Tool and does not require a Runtime
        change. A schema marker is accepted for custom Skill tools, but there
        is deliberately no resource-type-to-field lookup here.
        """
        declared = str(getattr(tool_def, "resource_id_field", "") or "").strip()
        if declared:
            return declared
        schema = getattr(tool_def, "input_schema", None)
        properties = getattr(schema, "properties", {}) if schema else {}
        if isinstance(properties, dict):
            marked = [
                str(name) for name, spec in properties.items()
                if isinstance(spec, dict)
                and (spec.get("resource_id") or spec.get("x-resource-id"))
            ]
            if len(marked) == 1:
                return marked[0]
        return "resource_id"

    @staticmethod
    def _parent_resource_id_field_for_tool(tool_def: Any) -> Optional[str]:
        """Resolve a Tool's parent ID field without provider branching.

        ``parent_resource_id_field`` is authoritative.  The schema marker is
        useful for plugin Tools that want to keep metadata close to their
        input contract; conventional logical names remain a compatibility
        fallback for older Tools.
        """
        declared = str(
            getattr(tool_def, "parent_resource_id_field", "") or ""
        ).strip()
        if declared:
            return declared

        schema = getattr(tool_def, "input_schema", None)
        properties = getattr(schema, "properties", {}) if schema else {}
        if isinstance(properties, dict):
            marked = [
                str(name) for name, spec in properties.items()
                if isinstance(spec, dict)
                and (spec.get("parent_resource_id") or spec.get("x-parent-resource-id"))
            ]
            if len(marked) == 1:
                return marked[0]

        parent_type = str(getattr(tool_def, "parent_resource_type", "") or "")
        normalized_parent = re.sub(r"[^a-z0-9]+", "_", parent_type.lower()).strip("_")
        candidates = [f"{normalized_parent}_id"] if normalized_parent else []
        if isinstance(properties, dict):
            for candidate in candidates:
                if candidate in properties:
                    return candidate
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
            id_field = str(item.get("resource_id_field") or cls._resource_id_field(resource_type))
            input_data = data.get("input") if isinstance(data.get("input"), dict) else {}
            raw_id = data.get(id_field) or input_data.get(id_field) or item.get(id_field)
            if raw_id in (None, ""):
                raw_id = input_data.get("resource_id") or data.get("resource_id")
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
                key: AgentRuntime._freeze_credentials(item)
                for key, item in value.items()
            })
        if isinstance(value, list):
            return tuple(AgentRuntime._freeze_credentials(item) for item in value)
        return value

    @staticmethod
    def _redact_for_persistence(value: Any) -> Any:
        """移除可能包含凭证的字段后再写入 SQLite。"""
        sensitive = (
            "token", "secret", "api_key", "private_key", "private_key_id",
            "service_account", "sa_email", "developer_key", "credential", "authorization",
            "bc_id", "bcid", "partner_id", "partnerid", "perter_id", "perterid", "developer_token",
            "mcc", "login_customer_id", "logincustomerid",
            "manager_customer_id", "managercustomerid", "client_id", "clientid",
        )
        if isinstance(value, dict):
            return {
                k: (
                    AgentRuntime._redact_for_persistence(v)
                    if str(k).lower() in {"selection_token", "selection_tokens"}
                    else "<redacted>"
                    if any(part in str(k).lower() for part in sensitive)
                    else AgentRuntime._redact_for_persistence(v)
                )
                for k, v in value.items()
            }
        if isinstance(value, list):
            return [AgentRuntime._redact_for_persistence(v) for v in value]
        if isinstance(value, str):
            # User messages are persisted as strings, so key-based redaction
            # alone is insufficient when a secret is pasted into chat.
            patterns = (
                # Quoted JSON/Python values, e.g. {'access_token': '...'}.
                r"(?is)(?P<prefix>['\"]?(?:access|refresh|developer)[_-]?token['\"]?\s*[:=]\s*)['\"][^'\"]*['\"]",
                r"(?is)(?P<prefix>['\"]?private[_-]?key['\"]?\s*[:=]\s*)['\"]-----BEGIN.*?-----END[^\r\n]*-----['\"]",
                r"(?is)(?P<prefix>['\"]?private[_-]?key['\"]?\s*[:=]\s*)['\"][^'\"]*['\"]",
                r"(?is)(?P<prefix>['\"]?client[_-]?secret['\"]?\s*[:=]\s*)['\"][^'\"]*['\"]",
                r"(?is)(?P<prefix>['\"]?(?:bc[_-]?id|partner[_-]?id|perter[_-]?id|mcc|login[_-]?customer[_-]?id|manager[_-]?customer[_-]?id|client[_-]?id)['\"]?\s*[:=]\s*)['\"][^'\"]*['\"]",
                r"(?is)(?P<prefix>['\"]?authorization['\"]?\s*[:=]\s*)['\"][^'\"]*['\"]",
                # Unquoted key/value forms used by logs and CLI snippets.
                r"(?i)(?P<prefix>\b(?:access|refresh|developer)[_-]?token\s*[:=]\s*)[^\s,;}]+",
                r"(?is)(?P<prefix>\bprivate[_-]?key\s*[:=]\s*)-----BEGIN.*?-----END[^\r\n]*-----",
                r"(?i)(?P<prefix>\bprivate[_-]?key\s*[:=]\s*)[^\s,;}]+",
                r"(?i)(?P<prefix>\bclient[_-]?secret\s*[:=]\s*)[^\s,;}]+",
                r"(?i)(?P<prefix>\b(?:bc[_-]?id|partner[_-]?id|perter[_-]?id|mcc|login[_-]?customer[_-]?id|manager[_-]?customer[_-]?id|client[_-]?id|authorization)\s*[:=]\s*)[^\s,;}]+",
            )
            redacted = value
            for pattern in patterns:
                redacted = re.sub(
                    pattern,
                    lambda match: f"{match.group('prefix')}<redacted>",
                    redacted,
                )
            return redacted
        return value

    def persist_conversation_turn(
        self, session: "SessionContext", turn_id: str,
        user_input: str, reply: str,
        execution_trace: Optional[ExecutionTrace] = None,
        ui: Optional[Mapping[str, Any]] = None,
    ) -> None:
        """Persist a complete sanitized turn and keep bounded model context.

        Full history belongs to the persistence backend's message store. The
        session metadata keeps only a small recent window for prompt context,
        so restoring a session never requires loading an unbounded transcript.
        """
        safe_user = self._redact_for_persistence(user_input)
        safe_reply = self._redact_for_persistence(reply)
        session.add_message({"role": "user", "content": safe_user})
        session.add_message({"role": "assistant", "content": safe_reply})
        if not session.ctx.metadata.get("conversation_title"):
            first_user = next(
                (
                    str(message.get("content", ""))
                    for message in session.messages
                    if message.get("role") == "user"
                ),
                safe_user,
            )
            title, title_source = self.conversation_title_generator.generate(
                first_user, self._llm
            )
            session.ctx.metadata["conversation_title"] = self._redact_for_persistence(title)
            session.ctx.metadata["conversation_title_source"] = title_source
        if not self._session_manager:
            return
        self._session_manager.record_conversation_message(
            session.session_id, turn_id, "user", safe_user
        )
        self._session_manager.record_conversation_message(
            session.session_id, turn_id, "assistant", safe_reply
        )
        metadata = {
            "execution_mode": self.execution_mode,
            "read_only_mode": self._read_only_mode,
            "tenant_id": session.ctx.metadata.get("tenant_id", "default"),
            "conversation_title": session.ctx.metadata.get("conversation_title", "新对话"),
            "conversation_title_source": session.ctx.metadata.get(
                "conversation_title_source", "fallback"
            ),
            "message_count": len(session.messages),
            "messages": self._redact_for_persistence(session.messages[-20:]),
        }
        ui_by_turn = session.ctx.metadata.get("conversation_ui", {})
        ui_by_turn = dict(ui_by_turn) if isinstance(ui_by_turn, dict) else {}
        if isinstance(ui, Mapping) and ui:
            # A2UI is persisted as sanitized message metadata, not as model
            # context. It can be restored for display, but it never grants an
            # execution permission or bypasses the confirmation boundary.
            ui_by_turn[str(turn_id)] = self._redact_for_persistence(dict(ui))
        ui_by_turn = dict(list(ui_by_turn.items())[-20:])
        session.ctx.metadata["conversation_ui"] = ui_by_turn
        metadata["conversation_ui"] = ui_by_turn
        if execution_trace is not None:
            traces = session.ctx.metadata.get("execution_traces", {})
            traces = dict(traces) if isinstance(traces, dict) else {}
            traces[str(turn_id)] = execution_trace.snapshot()
            # Keep durable trace context bounded just like the recent message
            # window. The full live stream remains available to observers.
            traces = dict(list(traces.items())[-20:])
            session.ctx.metadata["execution_traces"] = traces
            metadata["execution_traces"] = traces
        self._session_manager.update_session(
            session.session_id,
            metadata,
        )

    def _persist_tool_result(
        self, session: "SessionContext", turn_id: str, tool_def: Any,
        platform: str, input_data: dict, result: ToolResult,
    ) -> None:
        """记录安全的工具审计信息和模拟资源状态。"""
        if not self._session_manager:
            return
        now = datetime.now().isoformat()
        safe_input = self._redact_for_persistence(input_data)
        safe_output = self._redact_for_persistence(result.data)
        self._session_manager.record_tool_call(
            session.session_id,
            turn_id,
            ToolCallRecord(
                id=str(uuid.uuid4()), session_id=session.session_id, turn_id=turn_id,
                tool_name=tool_def.name, platform=platform, input_data=safe_input,
                output_data=safe_output, success=result.success,
                error=self._redact_for_persistence(result.error),
                started_at=now, ended_at=datetime.now().isoformat(),
            ),
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
    
    def _get_session_lock(self, session_id: str) -> threading.RLock:
        """Return the per-session lock used to serialize mutable turn state."""
        with self._session_locks_guard:
            return self._session_locks.setdefault(session_id, threading.RLock())

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

    # -- Durable asynchronous Agent tasks -------------------------------

    def submit_task(
        self,
        kind: str,
        payload: dict[str, Any],
        *,
        principal: Optional[RequestPrincipal] = None,
        user_id: str = "anonymous",
        tenant_id: str = "default",
        idempotency_key: Optional[str] = None,
        workflow_id: Optional[str] = None,
    ) -> tuple[dict[str, Any], bool]:
        """Submit a task that will re-enter the normal Runtime turn loop.

        The public task contract is intentionally data-only.  ``agent.turn``
        is validated here before persistence; credentials, confirmation
        tokens, arbitrary callbacks and identity fields are never accepted.
        New task kinds must be registered by trusted application code, not by
        an HTTP request or an uploaded Skill package.
        """
        if self.task_executor is None:
            raise RuntimeError("durable task executor is not configured")
        effective_user = principal.user_id if principal is not None else str(user_id)
        effective_tenant = principal.tenant_id if principal is not None else str(tenant_id or "default")
        kind = str(kind or "").strip()
        if kind != "agent.turn":
            raise ValueError(f"unsupported task kind: {kind}")
        if not isinstance(payload, dict):
            raise ValueError("task payload must be an object")
        protected_paths = self.security.validate_input_redline(payload)
        if protected_paths:
            raise ValueError(
                "任务包含禁止持久化的凭证/账户配置字段：" + ", ".join(protected_paths)
            )
        user_input = payload.get("user_input")
        if not isinstance(user_input, str) or not user_input.strip():
            raise ValueError("agent.turn task requires user_input")
        if payload.get("confirmed") or payload.get("confirmation_payload"):
            raise ValueError(
                "异步任务不持久化 live confirmation token；请使用同步确认接口"
            )
        allowed_fields = {
            "user_input", "session_id", "account_id", "platform_params",
            "confirmed", "confirmation_payload", "creation_blueprint_id",
            "creation_blueprint_version",
        }
        unknown = sorted(set(payload) - allowed_fields)
        if unknown:
            raise ValueError("任务参数不支持以下字段：" + ", ".join(unknown))
        platform_params = payload.get("platform_params")
        if platform_params is not None and not isinstance(platform_params, dict):
            raise ValueError("platform_params must be an object")
        safe_payload = self._redact_for_persistence({
            "user_input": user_input,
            "session_id": payload.get("session_id"),
            "account_id": payload.get("account_id"),
            "platform_params": platform_params,
            "creation_blueprint_id": payload.get("creation_blueprint_id"),
            "creation_blueprint_version": payload.get("creation_blueprint_version"),
            "confirmed": False,
            "confirmation_payload": None,
        })
        try:
            json.dumps(safe_payload, ensure_ascii=False)
        except (TypeError, ValueError) as exc:
            raise ValueError("任务参数必须是 JSON 可序列化对象") from exc
        principal_claims = (
            principal.to_safe_dict()
            if principal is not None
            else RequestPrincipal(
                user_id=effective_user, tenant_id=effective_tenant,
                permissions=self._granted_permissions,
            ).to_safe_dict()
        )
        record, created = self.task_executor.submit(
            kind,
            safe_payload,
            tenant_id=effective_tenant,
            user_id=effective_user,
            idempotency_key=idempotency_key,
            workflow_id=workflow_id,
            metadata={"principal": principal_claims, "submission_source": "runtime"},
        )
        return record.to_dict(), created

    def _execute_agent_task(self, context: TaskExecutionContext) -> dict[str, Any]:
        """Re-enter Runtime; this handler never resolves or calls a Provider."""
        if context.is_cancelled():
            return {"success": False, "cancelled": True}
        claims = context.metadata.get("principal")
        principal = RequestPrincipal.from_claims(claims) if isinstance(claims, dict) else None
        payload = context.payload
        return self.run(
            user_input=str(payload.get("user_input") or ""),
            session_id=payload.get("session_id"),
            account_id=payload.get("account_id"),
            platform_params=payload.get("platform_params"),
            creation_blueprint_id=payload.get("creation_blueprint_id"),
            creation_blueprint_version=payload.get("creation_blueprint_version"),
            confirmed=False,
            confirmation_payload=None,
            principal=principal,
            user_id=context.user_id,
            tenant_id=context.tenant_id,
            cancellation_event=context.cancel_event,
        )

    def get_task(
        self, task_id: str, *, user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        if self.task_executor is None:
            return None
        record = self.task_executor.get(task_id, tenant_id=tenant_id, user_id=user_id)
        return record.to_dict() if record else None

    def list_tasks(
        self, *, user_id: str, tenant_id: str,
        statuses: Optional[list[str]] = None, limit: int = 50,
    ) -> list[dict[str, Any]]:
        if self.task_executor is None:
            return []
        return [
            record.to_dict()
            for record in self.task_executor.list(
                tenant_id=tenant_id, user_id=user_id,
                statuses=statuses, limit=limit,
            )
        ]

    def pause_task(
        self, task_id: str, *, user_id: str, tenant_id: str,
    ) -> Optional[dict[str, Any]]:
        if self.task_executor is None:
            return None
        if self.task_executor.get(task_id, tenant_id=tenant_id, user_id=user_id) is None:
            return None
        record = self.task_executor.pause(task_id)
        return record.to_dict() if record else None

    def resume_task(
        self, task_id: str, *, user_id: str, tenant_id: str,
    ) -> Optional[dict[str, Any]]:
        if self.task_executor is None:
            return None
        if self.task_executor.get(task_id, tenant_id=tenant_id, user_id=user_id) is None:
            return None
        record = self.task_executor.resume(task_id)
        return record.to_dict() if record else None

    def cancel_task(
        self, task_id: str, *, user_id: str, tenant_id: str,
    ) -> Optional[dict[str, Any]]:
        if self.task_executor is None:
            return None
        if self.task_executor.get(task_id, tenant_id=tenant_id, user_id=user_id) is None:
            return None
        record = self.task_executor.cancel(task_id)
        return record.to_dict() if record else None

    def _build_skill_context_from_metadata(
        self, session: Optional["SessionContext"] = None
    ) -> dict[str, Any]:
        """Return the current advisory context without adding a new registry."""
        # ToolContext metadata is session-scoped; this helper is only called
        # after the current turn has established that context.
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
    ) -> dict:
        """Execute one turn while serializing turns for the same session.

        SessionContext, credentials and protected state are mutable.  Without
        this boundary two concurrent requests for one session can interleave
        account context, tool outputs and confirmation state.
        """
        self.assert_llm_ready()
        lock = self._get_session_lock(session_id or "__new_session__")
        effective_user_id = principal.user_id if principal is not None else user_id
        effective_permissions = (
            principal.permissions if principal is not None else self._granted_permissions
        )
        effective_account_scope = (
            principal.account_scope if principal is not None else None
        )
        with lock:
            return self._run_unlocked(
                user_input=user_input,
                session_id=session_id,
                user_id=effective_user_id,
                account_id=account_id,
                credentials=credentials,
                platform_params=platform_params,
                confirmed=confirmed,
                confirmation_payload=confirmation_payload,
                creation_blueprint_id=creation_blueprint_id,
                creation_blueprint_version=creation_blueprint_version,
                granted_permissions=effective_permissions,
                account_scope=effective_account_scope,
                tenant_id=(
                    principal.tenant_id
                    if principal is not None
                    else (tenant_id or "default")
                ),
                cancellation_event=cancellation_event,
                event_callback=event_callback,
            )

    def _run_unlocked(
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
        granted_permissions: Optional[set[str] | frozenset[str]] = None,
        account_scope: Optional[Mapping[str, Any]] = None,
        tenant_id: str = "default",
        cancellation_event: Optional[threading.Event] = None,
        event_callback: Optional[ExecutionEventCallback] = None,
    ) -> dict:
        """
        执行一次完整的对话回合。
        
        对应 DAP Agent 的 Core Engine 主循环：
        用户输入 → 意图解析 → 工具路由 → 执行 → 返回结果
        
        Returns:
            {
                "session_id": str,
                "turn_id": str,
                "intent": dict,           # 解析后的意图
                "tool_calls": [...],       # 计划调用的工具
                "results": [...],          # 各工具执行结果
                "reply": str,              # 给用户的回复
                "needs_confirmation": bool, # 是否需要用户确认
            }
        """
        session_id = session_id or str(uuid.uuid4())
        turn_id = str(uuid.uuid4())[:8]
        trace = ExecutionTrace(event_callback, turn_id=turn_id)
        trace.start()
        input_error = self._validate_request_limits(user_input, platform_params)
        if input_error:
            trace.error(reason="request_invalid")
            trace.done("failed", safe_metadata={"reason": "request_invalid"})
            return {
                "session_id": session_id,
                "turn_id": turn_id,
                "timestamp": datetime.now().isoformat(),
                "intent": None,
                "tool_plan": {},
                "tool_selection": None,
                "results": [],
                "reply": f"❌ {input_error}",
                "needs_confirmation": False,
                "confirmation_payload": None,
                "policy_errors": [input_error],
            }
        # Secrets must not be sent to the LLM or retained in session history,
        # even when a caller accidentally pastes them into the chat text.
        safe_user_input = self._redact_for_persistence(user_input)
        
        # Step 1: 确保 Session 存在
        request_clients = self._build_request_clients(credentials)
        session = self._ensure_session(
            session_id, user_id, account_id, credentials, tenant_id=tenant_id
        )
        turn_deadline = time.monotonic() + self.turn_timeout_seconds
        session.ctx.metadata["turn_deadline"] = turn_deadline
        session.ctx.metadata["tenant_id"] = str(tenant_id or "default")
        if cancellation_event is not None:
            session.ctx.metadata["task_cancel_event"] = cancellation_event
        else:
            session.ctx.metadata.pop("task_cancel_event", None)
        effective_permissions = (
            self._granted_permissions
            if granted_permissions is None
            else frozenset(granted_permissions)
        )

        # Memory is an advisory context layer, never an execution source.
        # Only an explicit user request can create a long-lived record; normal
        # tool results and chat history remain session/audit state.
        recalled_memories: list[dict[str, Any]] = []
        memory_context = ""
        if self._memory_manager:
            try:
                explicit = self._memory_manager.explicit_memory_text(safe_user_input)
                if explicit:
                    self._memory_manager.remember(
                        explicit,
                        tenant_id=tenant_id,
                        user_id=user_id,
                        # An explicit user memory is long-lived by policy;
                        # keep it user-scoped rather than tying it to the
                        # current conversation session.
                        session_id=None,
                        source="user_explicit",
                        kind="semantic",
                        importance=0.85,
                    )
                recalled_memories, memory_context = self._memory_manager.build_context(
                    safe_user_input,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    session_id=session_id,
                )
            except Exception as exc:
                # Memory failure must never block intent parsing or tool policy.
                logger.debug("构建 Memory 上下文失败: %s", exc)
        
        # Step 2: 解析用户意图
        # Give an injected LLM the bounded Skill/tool context before it emits
        # an intent.  The post-parse IntentRouter remains authoritative, so
        # this context can improve recognition but cannot grant execution.
        trace.stage_status(
            "intent",
            "Intent 识别",
            "running",
            subtitle="理解用户目标与约束",
            safe_metadata={"phase": "intent_parsing"},
            safe_input={
                "request": safe_user_input,
                "request_length": len(safe_user_input),
            },
        )
        try:
            skill_context = self._build_skill_context(
                safe_user_input, self.registry.list_all(), None, tenant_id
            )
            skill_context["prior_tool_results"] = self._build_prior_tool_results_context(session)
            skill_context["memory"] = recalled_memories
            skill_context["memory_context"] = memory_context
            session.ctx.metadata["skill_context"] = skill_context
        except Exception as exc:
            logger.debug("构建 Skill 解析上下文失败: %s", exc)
        intent = self.intent_parser.parse(safe_user_input, session.ctx)
        trace.stage_status(
            "intent",
            "Intent 识别",
            "succeeded",
            subtitle="已识别请求目标",
            platform=", ".join(str(item) for item in (intent.platforms or [])),
            safe_metadata={
                "intent_type": intent.intent_type,
                "platform_count": len(intent.platforms or []),
            },
            safe_output={
                "intent_type": intent.intent_type,
                "platforms": list(intent.platforms or []),
                "structured_parameters": bool(intent.platform_params),
                "parameters": self._redact_for_persistence(intent.platform_params or {}),
            },
        )
        # Refresh advisory context with the parsed intent.  This changes only
        # the model-facing explanation/context; IntentRouter remains the sole
        # authority for the executable plan below.
        try:
            skill_context = self._build_skill_context(
                safe_user_input,
                self.registry.list_all(),
                intent.intent_type,
                tenant_id,
            )
            skill_context["prior_tool_results"] = self._build_prior_tool_results_context(session)
            skill_context["memory"] = recalled_memories
            skill_context["memory_context"] = memory_context
            session.ctx.metadata["skill_context"] = skill_context
        except Exception as exc:
            logger.debug("构建意图级 Skill/知识上下文失败: %s", exc)
        
        # 如果提供了 platform_params（来自确认请求），合并到意图中
        if platform_params:
            protected_paths = self.security.validate_input_redline(platform_params)
            if protected_paths:
                error = "请求包含禁止传入的凭证/账户配置字段：" + ", ".join(protected_paths)
                trace.error(reason="protected_input")
                trace.done("failed", safe_metadata={"reason": "protected_input"})
                self.persist_conversation_turn(
                    session, turn_id, safe_user_input, error, execution_trace=trace
                )
                return {
                    "session_id": session_id,
                    "turn_id": turn_id,
                    "timestamp": datetime.now().isoformat(),
                    "intent": None,
                    "tool_plan": {},
                    "tool_selection": None,
                    "results": [],
                    "reply": f"❌ {error}",
                    "needs_confirmation": False,
                    "confirmation_payload": None,
                    "policy_errors": [error],
                }
            merged_params = copy.deepcopy(intent.platform_params or {})
            for platform, values in platform_params.items():
                if isinstance(values, dict) and isinstance(merged_params.get(platform), dict):
                    merged_params[platform] = {
                        **merged_params[platform],
                        **self._redact_for_persistence(values),
                    }
                else:
                    merged_params[platform] = self._redact_for_persistence(values)
            intent.platform_params = merged_params
        
        # Step 2.5: 动态加载相关平台的 Skill 工具
        self._load_required_skills(intent.platforms)

        policy_errors = self._validate_policies(intent)
        if policy_errors:
            reply = "❌ 业务策略阻止本次请求：" + "；".join(policy_errors)
            trace.error(reason="policy_blocked")
            trace.done("failed", safe_metadata={"reason": "policy_blocked"})
            self.persist_conversation_turn(
                session, turn_id, safe_user_input, reply,
                execution_trace=trace,
            )
            return {
                "session_id": session_id,
                "turn_id": turn_id,
                "timestamp": datetime.now().isoformat(),
                "intent": intent.to_dict(),
                "tool_plan": {},
                "tool_selection": None,
                "results": [],
                "reply": reply,
                "needs_confirmation": False,
                "confirmation_payload": None,
                "policy_errors": policy_errors,
            }

        # Step 3: discover Tools from their self-described action/resource
        # metadata. Skills provide expert context and SOP; the Runtime orders
        # the returned Tool plan from provider-owned resource metadata.
        trace.stage_status(
            "skill_selection",
            "Skill 选择",
            "running",
            subtitle="根据请求加载相关 Skill 与能力",
            safe_metadata={"phase": "skill_selection"},
            safe_input={
                "intent_type": intent.intent_type,
                "platforms": list(intent.platforms or []),
            },
        )
        tool_plan = self.intent_router.route(intent, self.registry)

        # A model may return a semantic synonym or an invalid operation name.
        # Let an LLM-aware parser repair that result against the active Tool
        # catalog once, after the authoritative Router has rejected it. This
        # is deliberately optional for custom parsers and is not a keyword or
        # provider dispatch table.
        routed_platforms = {
            self._canonical_platform(platform) for platform in tool_plan
        }
        requested_platforms = {
            self._canonical_platform(platform)
            for platform in (getattr(intent, "platforms", []) or [])
        }
        route_is_incomplete = bool(
            requested_platforms and routed_platforms != requested_platforms
        )
        should_repair_route = bool(
            tool_plan
            or route_is_incomplete
            or str(getattr(intent, "intent_type", "") or "") != "chat"
            or bool(getattr(intent, "platforms", []) or [])
        )
        if should_repair_route and (not tool_plan or route_is_incomplete):
            repair = getattr(self.intent_parser, "repair_for_routing", None)
            if callable(repair):
                repaired_intent = repair(safe_user_input, session.ctx, intent)
                if repaired_intent is not None:
                    intent = repaired_intent
                    self._load_required_skills(intent.platforms)
                    policy_errors = self._validate_policies(intent)
                    if not policy_errors:
                        tool_plan = self.intent_router.route(intent, self.registry)
        if creation_blueprint_id:
            if not (
                str(getattr(intent, "intent_type", "") or "") == "create_campaign"
                or str(getattr(intent, "intent_type", "") or "").startswith("create_")
            ):
                reply = "这份广告创建草稿需要在创建广告的对话中继续提交。"
                trace.error(reason="creation_blueprint_context_invalid")
                trace.done("failed", safe_metadata={"reason": "creation_blueprint_context_invalid"})
                self.persist_conversation_turn(
                    session, turn_id, safe_user_input, reply,
                    execution_trace=trace,
                )
                return {
                    "session_id": session_id,
                    "turn_id": turn_id,
                    "timestamp": datetime.now().isoformat(),
                    "intent": intent.to_dict(),
                    "tool_plan": {},
                    "execution_plan": {},
                    "tool_selection": None,
                    "results": [],
                    "reply": reply,
                    "needs_confirmation": False,
                    "confirmation_payload": None,
                    "policy_errors": ["creation blueprint requires a create intent"],
                    "ui": {},
                }
            blueprint_tool_plan, blueprint_error = self._creation_blueprint_tool_plan(
                creation_blueprint_id, creation_blueprint_version, intent
            )
            if blueprint_error:
                reply = "这份广告创建草稿暂时无法继续：" + blueprint_error
                trace.error(reason="creation_blueprint_invalid")
                trace.done("failed", safe_metadata={"reason": "creation_blueprint_invalid"})
                self.persist_conversation_turn(
                    session, turn_id, safe_user_input, reply,
                    execution_trace=trace,
                )
                return {
                    "session_id": session_id,
                    "turn_id": turn_id,
                    "timestamp": datetime.now().isoformat(),
                    "intent": intent.to_dict(),
                    "tool_plan": {},
                    "execution_plan": {},
                    "tool_selection": None,
                    "results": [],
                    "reply": reply,
                    "needs_confirmation": False,
                    "confirmation_payload": None,
                    "policy_errors": [blueprint_error],
                    "ui": {},
                }
            # Blueprint submission is an explicit structured continuation.
            # Use the generic creation lifecycle so provider-owned Tool
            # activation metadata and dependency ordering select the exact
            # declared chain without trusting the short UI label.
            intent.intent_type = "create_campaign"
            intent.platforms = [next(iter(blueprint_tool_plan))]
            tool_plan = blueprint_tool_plan or {}

        execution_groups = list(tool_plan.items())
        routed_tools = [
            tool for _platform, tools in execution_groups for tool in tools
        ]
        tool_selection = self._optimize_tool_selection(
            safe_user_input, intent, routed_tools, tenant_id
        )
        feature = self._feature_for_intent(intent)
        execution_plan = ExecutionPlan.from_tool_plan(
            intent, tool_plan, canonicalize=self._canonical_platform
        )
        trace.bind_plan(execution_plan)
        trace.stage_status(
            "skill_selection",
            "Skill 选择",
            "succeeded",
            subtitle=(
                f"已选择 {len(routed_tools)} 个可用 Tool"
                if routed_tools else "未匹配到可执行 Tool"
            ),
            safe_metadata={"tool_count": len(routed_tools)},
            safe_output={
                "tool_count": len(routed_tools),
                "tools": [tool.name for tool in routed_tools[:12]],
            },
        )
        # The card is a structured view of the same Blueprint/Tool contract
        # used by the execution path. It is returned alongside the normal
        # conversation so users can edit fields or continue in natural
        # language; it never invokes a lookup or Provider API.
        creation_ui = self.build_creation_ui(intent)
        if account_id and isinstance(creation_ui, dict):
            for card in creation_ui.get("cards", []) or []:
                if isinstance(card, dict):
                    # Keep the explicitly supplied account visible when a
                    # later validation response returns the same card. The
                    # value still comes from the request, never inference.
                    card["account_id"] = str(account_id)

        # A creation Blueprint is a parameter-collection boundary. Do not
        # enter the generic workflow/account loop while the explicit account
        # is missing: that loop would represent a draft as a failed Tool
        # result. Resolve the account through the same schema-driven resolver
        # used by execution so an explicitly supplied provider account (for
        # example Google customer_id) is treated consistently with the
        # top-level account_id. The later card submission is the only
        # continuation into the normal creation lifecycle.
        creation_is_requested = self.creation_card_builder.is_creation_intent(intent)
        creation_has_write_tools = creation_is_requested and any(
            tool.is_write_tool
            for tools in tool_plan.values()
            for tool in tools
        )
        missing_account_platform = None
        if creation_has_write_tools:
            for platform, tools in execution_groups:
                if not any(tool.is_write_tool for tool in tools):
                    continue
                resolved_account = self.account_resolver.resolve(
                    intent,
                    platform,
                    tools,
                    account_id,
                    allow_automatic_account=False,
                )
                if not resolved_account:
                    missing_account_platform = self._canonical_platform(platform)
                    break
        creation_account_missing = missing_account_platform is not None

        # A natural-language dry-run with an explicitly supplied account may
        # still be used to inspect a provider validation preview. Its card can
        # contain fields that are not part of the selected Tool chain (for
        # example a broader catalog card), so only an explicit Blueprint form
        # submission makes card readiness a hard execution gate. The initial
        # conversational request is still blocked whenever it lacks an
        # account, which is the safety boundary visible to the user.
        creation_needs_input = bool(
            creation_ui.get("cards")
            and (
                creation_account_missing
                or (creation_blueprint_id and creation_ui.get("needs_input"))
            )
        )
        if creation_has_write_tools and (creation_account_missing or creation_needs_input):
            trace.all_nodes_status("awaiting_confirmation", reason="creation_parameters_required")
            trace.reply()
            trace.done(
                "awaiting_confirmation",
                safe_metadata={"reason": "creation_parameters_required", "tool_count": len(routed_tools)},
            )
            account_payload = (
                {
                    "type": "ask_account",
                    "platform": missing_account_platform,
                    "question": f"请提供要操作的 {missing_account_platform} 广告账户 ID。",
                }
                if missing_account_platform
                else None
            )
            reply = (
                self.creation_ui_reply(creation_ui)
                if creation_ui.get("cards")
                else (
                    account_payload["question"]
                    if account_payload
                    else "请先补充广告创建参数。"
                )
            )
            self.persist_conversation_turn(
                session, turn_id, safe_user_input, reply,
                execution_trace=trace, ui=creation_ui,
            )
            return {
                "session_id": session_id,
                "turn_id": turn_id,
                "timestamp": datetime.now().isoformat(),
                "intent": intent.to_dict(),
                "tool_plan": {k: [t.name for t in v] for k, v in tool_plan.items()},
                "execution_plan": execution_plan.to_dict(),
                "tool_selection": {
                    "tool_count": tool_selection["tool_count"],
                    "tools": [tool.name for tool in tool_selection["selected_tools"]],
                    "platforms": tool_selection["platforms"],
                    "context": tool_selection["context"],
                    "tool_prompt": tool_selection["tool_prompt"],
                    "expert_knowledge": tool_selection["expert_knowledge"],
                    "knowledge": tool_selection.get("knowledge", []),
                },
                "memory": recalled_memories,
                "results": [],
                "response_source": "creation_card",
                "reply": reply,
                # Keep the account request in the machine-readable response
                # even when a form card is present. The web UI intentionally
                # renders the card (rather than a second account popup),
                # while API clients can still use this payload to understand
                # why the plan is paused.
                "needs_confirmation": bool(account_payload),
                "confirmation_payload": account_payload,
                "workflow_id": None,
                "ui": creation_ui,
            }

        parameter_errors = self.input_builder.validate_platform_parameter_contract(
            intent, tool_plan
        )
        if parameter_errors:
            reply = (
                self.creation_ui_reply(creation_ui)
                if creation_ui.get("needs_input")
                else "❌ 参数契约阻止本次请求：" + "；".join(parameter_errors)
            )
            first_tool = next(
                (tool for tools in tool_plan.values() for tool in tools), None
            )
            parameter_result = {
                "tool": first_tool.name if first_tool else "parameter_contract",
                "platform": first_tool.platform if first_tool else "",
                "success": False,
                "data": {},
                "error": "; ".join(parameter_errors),
                "needs_confirmation": False,
            }
            trace.all_nodes_status("failed", reason="parameter_contract")
            trace.reply()
            trace.done("failed", safe_metadata={"reason": "parameter_contract"})
            self.persist_conversation_turn(
                session, turn_id, safe_user_input, reply,
                execution_trace=trace, ui=creation_ui,
            )
            return {
                "session_id": session_id,
                "turn_id": turn_id,
                "timestamp": datetime.now().isoformat(),
                "intent": intent.to_dict(),
                "tool_plan": {k: [t.name for t in v] for k, v in tool_plan.items()},
                "execution_plan": execution_plan.to_dict(),
                "tool_selection": None,
                "results": [parameter_result],
                "reply": reply,
                "needs_confirmation": False,
                "confirmation_payload": None,
                "policy_errors": parameter_errors,
                "ui": creation_ui,
            }

        # A submitted Blueprint must pass the complete provider contract
        # before the first parent Tool is executed. This is especially
        # important for creatives: a missing minimum asset count must not
        # leave a campaign or ad group partially created in live mode.
        if creation_blueprint_id and creation_has_write_tools:
            creation_issues = self._creation_contract_preflight(
                intent, tool_plan, session, str(account_id or "")
            )
            if creation_issues:
                issue_pairs = {
                    (str(item.get("tool") or ""), str(item.get("field") or ""))
                    for item in creation_issues
                }
                for card in creation_ui.get("cards", []) if isinstance(creation_ui, dict) else []:
                    if not isinstance(card, dict):
                        continue
                    invalid_fields = list(card.get("invalid_fields") or [])
                    for field in card.get("fields", []) or []:
                        if not isinstance(field, dict):
                            continue
                        key = (str(field.get("tool") or ""), str(field.get("provider_field") or ""))
                        if key in issue_pairs or (
                            key[1]
                            and any(
                                pair[1] == key[1]
                                for pair in issue_pairs
                            )
                        ):
                            field["state"] = "invalid"
                            if field.get("path") not in invalid_fields:
                                invalid_fields.append(field.get("path"))
                    card["invalid_fields"] = list(dict.fromkeys(invalid_fields))
                    card["ready"] = False
                creation_ui["needs_input"] = True
                creation_reply = self._creation_contract_reply(
                    creation_ui, creation_issues
                )
                trace.stage_status(
                    "creation_validation",
                    "创建前检查",
                    "running",
                    subtitle="核对广告素材和平台必填规则",
                    safe_metadata={"phase": "creation_contract_validation"},
                )
                trace.stage_status(
                    "creation_validation",
                    "创建前检查",
                    "failed",
                    subtitle="参数未满足，尚未进入创建",
                    safe_metadata={
                        "phase": "creation_contract_validation",
                        "issue_count": len(creation_issues),
                    },
                    safe_output={
                        "ready": False,
                        "issue_count": len(creation_issues),
                    },
                )
                trace.all_nodes_status(
                    "skipped", reason="creation_validation_failed"
                )
                trace.reply()
                trace.done(
                    "failed",
                    safe_metadata={
                        "reason": "creation_validation_failed",
                        "issue_count": len(creation_issues),
                        "tool_count": len(routed_tools),
                    },
                )
                self.persist_conversation_turn(
                    session, turn_id, safe_user_input, creation_reply,
                    execution_trace=trace, ui=creation_ui,
                )
                return {
                    "session_id": session_id,
                    "turn_id": turn_id,
                    "timestamp": datetime.now().isoformat(),
                    "intent": intent.to_dict(),
                    "tool_plan": {k: [t.name for t in v] for k, v in tool_plan.items()},
                    "execution_plan": execution_plan.to_dict(),
                    "tool_selection": {
                        "tool_count": tool_selection["tool_count"],
                        "tools": [tool.name for tool in tool_selection["selected_tools"]],
                        "platforms": tool_selection["platforms"],
                        "context": tool_selection["context"],
                        "tool_prompt": tool_selection["tool_prompt"],
                        "expert_knowledge": tool_selection["expert_knowledge"],
                        "knowledge": tool_selection.get("knowledge", []),
                    },
                    "memory": recalled_memories,
                    "results": [],
                    "resource_results": [],
                    "response_source": "creation_validation",
                    "reply": creation_reply,
                    "needs_confirmation": False,
                    "confirmation_payload": None,
                    "policy_errors": ["creation_validation_failed"],
                    "creation_validation": {"status": "blocked", "issue_count": len(creation_issues)},
                    "workflow_id": None,
                    "ui": creation_ui,
                }

        # Cross-channel creation is preflighted as one provider-neutral plan.
        # This must happen before workflow creation or any provider Tool is
        # invoked, otherwise one channel could be committed/planned before a
        # later channel reveals a missing objective, app, targeting or asset.
        creation_preflight = None
        if (
            feature is not None
            and callable(getattr(feature, "preflight_creation", None))
            and callable(getattr(feature, "handles_creation_preflight", None))
            and feature.handles_creation_preflight(intent)
        ):
            creation_preflight = feature.preflight_creation(
                self.services,
                intent,
                tool_plan,
                session,
                account_id,
                account_scope,
                effective_permissions,
            )
            if not creation_preflight.ready:
                preflight_results = feature.preflight_results(creation_preflight)
                preflight_reply = getattr(feature, "preflight_failure_reply", None)
                reply = (
                    preflight_reply(intent, creation_preflight)
                    if callable(preflight_reply)
                    else "跨渠道创建 preflight 未通过；已停止所有渠道的创建。"
                )
                if creation_ui.get("needs_input") and not any(
                    isinstance(item.get("confirmation_payload"), dict)
                    and item["confirmation_payload"].get("type") == "ask_account"
                    for item in preflight_results
                ):
                    reply = self.creation_ui_reply(creation_ui)
                trace.all_nodes_status("failed", reason="preflight_blocked")
                trace.reply()
                trace.done("failed", safe_metadata={"reason": "preflight_blocked"})
                self.persist_conversation_turn(
                    session, turn_id, safe_user_input, reply,
                    execution_trace=trace, ui=creation_ui,
                )
                return {
                    "session_id": session_id,
                    "turn_id": turn_id,
                    "timestamp": datetime.now().isoformat(),
                    "intent": intent.to_dict(),
                    "tool_plan": {k: [t.name for t in v] for k, v in tool_plan.items()},
                        "tool_selection": {
                        "tool_count": tool_selection["tool_count"],
                        "tools": [tool.name for tool in tool_selection["selected_tools"]],
                        "platforms": tool_selection["platforms"],
                        "context": tool_selection["context"],
                        "tool_prompt": tool_selection["tool_prompt"],
                        "expert_knowledge": tool_selection["expert_knowledge"],
                            "knowledge": tool_selection.get("knowledge", []),
                        },
                        "execution_plan": execution_plan.to_dict(),
                        "results": preflight_results,
                    "resource_results": [],
                    "workflow_id": None,
                    **(
                        feature.preflight_payload(creation_preflight)
                        if callable(getattr(feature, "preflight_payload", None))
                        else {"preflight": creation_preflight.to_dict()}
                    ),
                    "reply": reply,
                    "needs_confirmation": any(
                        item.get("needs_confirmation")
                        for item in preflight_results
                    ),
                    "confirmation_payload": next(
                        (
                            item.get("confirmation_payload")
                            for item in preflight_results
                            if item.get("confirmation_payload")
                        ),
                        None,
                    ),
                    "policy_errors": list(creation_preflight.errors),
                    "ui": creation_ui,
                }
        
        # Batch management is a first-class planning operation.  It expands
        # IDs into independent items while retaining the normal whitelist and
        # workflow audit boundaries; no provider Handler is called here.
        if feature is not None and callable(
            getattr(feature, "is_batch_intent", None)
        ) and feature.is_batch_intent(intent):
            workflow_id = self.workflow.start(
                session,
                intent,
                tool_plan,
                register_items=not feature.is_batch_intent(intent),
                execution_plan=execution_plan,
            )
            batch_result = feature.run_batch_plan(
                self.services,
                safe_user_input, session, turn_id, intent, tool_plan,
                account_id, workflow_id,
                account_scope=account_scope,
                granted_permissions=effective_permissions,
            )
            for result in batch_result.get("results", []) if isinstance(batch_result, dict) else []:
                node = trace.node_for(result.get("platform", ""), result.get("tool", ""))
                trace.node_status(
                    node,
                    "succeeded" if result.get("success") else "failed",
                    safe_metadata={"simulated": True, "reason": "batch_plan"},
                )
            trace.reply(needs_confirmation=bool(batch_result.get("needs_confirmation")) if isinstance(batch_result, dict) else False)
            trace.done(
                "awaiting_confirmation" if isinstance(batch_result, dict) and batch_result.get("needs_confirmation") else "succeeded",
                safe_metadata={"batch_plan": True},
            )
            return batch_result

        # 检查是否需要执行任何工具
        if not tool_plan:
            intent_type = str(getattr(intent, "intent_type", "") or "")
            platform_params = getattr(intent, "platform_params", {}) or {}
            has_structured_request = bool(
                getattr(intent, "platforms", None)
                or any(
                    isinstance(values, dict) and any(
                        value not in (None, "", {}, [])
                        for value in values.values()
                    )
                    for values in platform_params.values()
                )
            )
            if intent_type == "chat" and not has_structured_request:
                no_tool_reply = self.response_renderer.render_chat(safe_user_input)
            elif has_structured_request:
                no_tool_reply = (
                    "我理解你想查询广告数据，但还无法确定具体的查询对象。"
                    "请补充平台和对象，例如：查询 Google Ads Campaign 列表，"
                    "或查询最近 7 天的 Google Ads 报表。"
                )
            else:
                no_tool_reply = (
                    "这次请求还没有匹配到可用的广告能力。请说明平台、对象和操作，"
                    "例如查询某个广告账户的 Campaign 列表。"
                )
            # There is no provider evidence at this point. Structured
            # requests must use the deterministic message; sending an empty
            # result set to the final-answer LLM could make it claim that a
            # query was attempted or that a report was empty. Ordinary chat
            # still gets the normal conversational synthesizer so controlled
            # Memory context remains useful.
            if intent_type == "chat" and not has_structured_request:
                no_tool_reply, response_source = self._render_response(
                    safe_user_input,
                    intent,
                    [],
                    False,
                    session=session,
                    fallback_reply=no_tool_reply,
                )
            else:
                response_source = "renderer"
            if creation_ui.get("needs_input"):
                no_tool_reply = self.creation_ui_reply(creation_ui)
                response_source = "creation_card"
            trace.stage_status(
                "reply",
                "回复生成",
                "running",
                subtitle="生成面向业务人员的结果说明",
                safe_metadata={"phase": "response_rendering"},
                safe_input={
                    "result_count": 0,
                    "structured_request": has_structured_request,
                },
            )
            # The chat renderer is the actual response boundary even when no
            # executable Tool was selected. Keep this stage conditional on
            # reaching the branch; it is not a prebuilt workflow step.
            trace.stage_status(
                "reply",
                "回复生成",
                "succeeded",
                subtitle="已生成本轮回复",
                safe_metadata={"response_source": response_source},
                safe_output={
                    "response_source": response_source,
                    "available": True,
                    "preview": self._redact_for_persistence(no_tool_reply),
                },
            )
            trace.reply()
            trace.done(
                "failed" if has_structured_request or intent_type != "chat" else "succeeded",
                safe_metadata={"tool_count": 0},
            )
            self.persist_conversation_turn(
                session, turn_id, safe_user_input, no_tool_reply,
                execution_trace=trace, ui=creation_ui,
            )
            return {
                "session_id": session_id,
                "turn_id": turn_id,
                "timestamp": datetime.now().isoformat(),
                "intent": intent.to_dict(),
                "tool_plan": {},
                "execution_plan": execution_plan.to_dict(),
                "tool_selection": {
                    "tool_count": tool_selection["tool_count"],
                    "tools": [tool.name for tool in tool_selection["selected_tools"]],
                    "platforms": tool_selection["platforms"],
                    "context": tool_selection["context"],
                    "tool_prompt": tool_selection["tool_prompt"],
                    "expert_knowledge": tool_selection["expert_knowledge"],
                    "knowledge": tool_selection.get("knowledge", []),
                },
                "memory": recalled_memories,
                "results": [],
                "response_source": response_source,
                "reply": no_tool_reply,
                "needs_confirmation": False,
                "confirmation_payload": None,
                "ui": creation_ui,
            }
        
        # Keep the caller's approval separate from the response payload that
        # is built during this turn.  Reusing the same variable would erase a
        # supplied plan token before the live validation branch.
        incoming_confirmation_payload = confirmation_payload

        # Step 4: 执行工具（按平台顺序）
        results = []
        needs_confirmation = False
        confirmation_payload = None
        workflow_id = self.workflow.start(
            session, intent, tool_plan, execution_plan=execution_plan
        )
        # Keep sensitive execution inputs local; they are only copied through
        # the redaction path when a workflow is persisted and are never added
        # to the public result payload.
        workflow_inputs: dict[int, dict] = {}
        workflow_sequence = 0

        tool_call_count = 0
        for platform, tools in execution_groups:
            if cancellation_event is not None and cancellation_event.is_set():
                break
            # 转换平台名称
            actual_platform = self._canonical_platform(platform)

            account_stage_id = f"account_scope:{actual_platform}"
            trace.stage_status(
                account_stage_id,
                "账户范围",
                "running",
                subtitle=f"校验 {actual_platform} 账户与访问范围",
                platform=actual_platform,
                safe_metadata={"phase": "account_scope"},
                safe_input={"platform": actual_platform},
            )

            # 每个平台使用自己的账户（不跨平台共享）。读请求可以在
            # 单账户白名单下方便地兜底；写请求必须由本回合显式提供账户，
            # 绝不能因为白名单恰好只有一个账户就静默选中目标广告主。
            platform_has_write = any(tool.is_write_tool for tool in tools)
            per_platform_account = self.account_resolver.resolve(
                intent,
                platform,
                tools,
                account_id,
                allow_automatic_account=not platform_has_write,
            )
            if not per_platform_account:
                test_accounts = self._available_accounts_for_request(
                    actual_platform, account_scope
                )
                if not platform_has_write and len(test_accounts) == 1:
                    per_platform_account = test_accounts[0]
                else:
                    results.append({
                        "tool": tools[0].name if tools else "unknown",
                        "platform": actual_platform,
                        "success": False,
                        "data": {},
                        "error": "缺少账户ID",
                        "needs_confirmation": True,
                        "confirmation_payload": {
                            "type": "ask_account",
                            "platform": actual_platform,
                            "question": (
                                f"请提供要操作的 {actual_platform} 广告账户 ID。"
                                if platform_has_write else
                                f"请提供 {actual_platform} 账户 ID（当前仅允许查询受控账户）。"
                            ),
                        },
                    })
                    for tool_def in tools:
                        trace.node_status(
                            trace.node_for(actual_platform, tool_def.name),
                            "awaiting_confirmation",
                            safe_metadata={"reason": "account_required"},
                        )
                    needs_confirmation = True
                    confirmation_payload = results[-1]["confirmation_payload"]
                    trace.stage_status(
                        account_stage_id,
                        "账户范围",
                        "awaiting_confirmation",
                        subtitle="等待补充账户范围",
                        platform=actual_platform,
                        safe_metadata={"reason": "account_required"},
                        safe_output={"validated": False, "account_required": True},
                    )
                    continue

            # 只读模式验证所有操作；写操作在 dry-run/live 两种模式下都必须
            # 命中显式测试账户白名单。
            if self._read_only_mode or platform_has_write or self.enforce_account_scope:
                allowed, error_msg = self._validate_account_with_principal(
                    actual_platform, per_platform_account, platform_has_write,
                    account_scope,
                )
                if not allowed:
                    results.append({
                        "tool": tools[0].name if tools else "unknown",
                        "platform": actual_platform,
                        "success": False,
                        "error": f"账户不在白名单中: {error_msg}",
                    })
                    for tool_def in tools:
                        trace.node_status(
                            trace.node_for(actual_platform, tool_def.name),
                            "failed",
                            safe_metadata={"reason": "account_scope_denied"},
                        )
                    trace.stage_status(
                        account_stage_id,
                        "账户范围",
                        "failed",
                        subtitle="账户不在允许范围内",
                        platform=actual_platform,
                        safe_metadata={"reason": "account_scope_denied"},
                        safe_output={"validated": False, "account_allowed": False},
                    )
                    continue

            trace.stage_status(
                account_stage_id,
                "账户范围",
                "succeeded",
                subtitle="账户范围校验通过",
                platform=actual_platform,
                safe_metadata={"validated": True},
                safe_output={
                    "validated": True,
                    "account_selected": bool(per_platform_account),
                },
            )

            # 非只读模式：写操作需要白名单 + 幂等保护
            chain_blocked = False
            chain_blocker = None
            for tool_def in tools:
                node = trace.node_for(actual_platform, tool_def.name)
                if cancellation_event is not None and cancellation_event.is_set():
                    chain_blocked = True
                    chain_blocker = tool_def.name
                    trace.node_status(node, "skipped", safe_metadata={"reason": "cancelled"})
                    break
                self.workflow.heartbeat(workflow_id)
                if workflow_id and tool_def.is_write_tool:
                    workflow_sequence += 1
                    self._session_manager.record_workflow_item(
                        workflow_id=workflow_id,
                        sequence=workflow_sequence,
                        platform=actual_platform,
                        tool_name=tool_def.name,
                        status="running",
                        input_data={},
                        account_id=per_platform_account,
                        parent_resource_type=getattr(tool_def, "parent_resource_type", None),
                    )
                tool_call_count += 1
                turn_budget_error = self._check_turn_budget(
                    turn_deadline, tool_call_count, self.max_tool_calls
                )
                if turn_budget_error:
                    results.append({
                        "tool": tool_def.name,
                        "platform": platform,
                        "success": False,
                        "data": {"execution_status": "budget_exceeded"},
                        "error": turn_budget_error,
                        "needs_confirmation": False,
                    })
                    trace.node_status(node, "failed", safe_metadata={"reason": "turn_budget_exceeded"})
                    chain_blocked = True
                    chain_blocker = tool_def.name
                    continue
                if chain_blocked:
                    results.append({
                        "tool": tool_def.name,
                        "platform": platform,
                        "success": False,
                        "data": {"skipped": True, "mode": self.execution_mode},
                        "error": f"前置工具 {chain_blocker} 未成功，已停止后续依赖步骤",
                        "skipped": True,
                    })
                    trace.node_status(node, "skipped", safe_metadata={"reason": "dependency_blocked"})
                    continue
                permission_error = self._check_tool_permissions(
                    tool_def, effective_permissions
                )
                if permission_error:
                    results.append({
                        "tool": tool_def.name,
                        "platform": platform,
                        "success": False,
                        "data": {},
                        "error": permission_error,
                        "needs_confirmation": False,
                    })
                    trace.node_status(node, "failed", safe_metadata={"reason": "permission_denied"})
                    chain_blocked = True
                    chain_blocker = tool_def.name
                    continue
                if not self._read_only_mode:
                    if tool_def.is_write_tool and per_platform_account:
                        allowed, error_msg = self.whitelist_validator.validate_account(actual_platform, per_platform_account)
                        if not allowed:
                            results.append({
                                "tool": tool_def.name,
                                "platform": actual_platform,
                                "success": False,
                                "error": f"账户验证失败: {error_msg}",
                            })
                            trace.node_status(node, "failed", safe_metadata={"reason": "account_not_allowed"})
                            continue
                # 为当前平台临时设置账户上下文
                original_account = session.ctx.account_id
                session.ctx.account_id = per_platform_account

                # 构建执行输入
                tool_input = self.input_builder.build(
                    tool_def, intent, platform, session.ctx
                )
                if workflow_id and tool_def.is_write_tool:
                    self._session_manager.record_workflow_item(
                        workflow_id=workflow_id,
                        sequence=workflow_sequence,
                        platform=actual_platform,
                        tool_name=tool_def.name,
                        status="running",
                        input_data=self._redact_for_persistence(tool_input),
                        account_id=per_platform_account,
                        parent_resource_type=getattr(tool_def, "parent_resource_type", None),
                    )

                protected_paths = self.security.validate_input_redline(tool_input)
                if protected_paths:
                    error = "请求包含禁止传入的凭证/账户配置字段：" + ", ".join(protected_paths)
                    results.append({
                        "tool": tool_def.name,
                        "platform": platform,
                        "success": False,
                        "data": {},
                        "error": error,
                        "needs_confirmation": False,
                    })
                    trace.node_status(node, "failed", safe_metadata={"reason": "protected_input"})
                    chain_blocked = True
                    chain_blocker = tool_def.name
                    session.ctx.account_id = original_account
                    continue

                unknown_params = tool_input.pop("_unknown_params", None)
                if unknown_params:
                    results.append({
                        "tool": tool_def.name,
                        "platform": platform,
                        "success": False,
                        "data": {},
                        "error": (
                            "工具参数契约不支持以下字段："
                            + ", ".join(unknown_params)
                            + "；请使用该工具 Schema 中声明的参数"
                        ),
                        "needs_confirmation": False,
                    })
                    trace.node_status(node, "failed", safe_metadata={"reason": "unknown_parameters"})
                    chain_blocked = True
                    chain_blocker = tool_def.name
                    session.ctx.account_id = original_account
                    continue

                selection_errors = tool_input.pop("_selection_errors", None)
                if selection_errors:
                    results.append({
                        "tool": tool_def.name,
                        "platform": platform,
                        "success": False,
                        "data": {"execution_status": "invalid_parameter_selection"},
                        "error": "参数选择凭证无效：" + "; ".join(selection_errors),
                        "needs_confirmation": False,
                    })
                    trace.node_status(node, "failed", safe_metadata={"reason": "invalid_parameter_selection"})
                    chain_blocked = True
                    chain_blocker = tool_def.name
                    session.ctx.account_id = original_account
                    continue
                
                # 检查必需参数是否齐全，不齐全则询问用户
                missing_params = tool_input.pop("_missing_params", None)
                if missing_params:
                    lookup_tools = self.input_builder.lookup_tools_for_fields(
                        tool_def, missing_params
                    )
                    results.append({
                        "tool": tool_def.name,
                        "platform": platform,
                        "success": False,
                        "error": f"缺少必需参数: {', '.join(missing_params)}",
                        "needs_confirmation": True,
                        "confirmation_payload": {
                            "type": "ask_params",
                            "tool": tool_def.name,
                            "missing": missing_params,
                            "lookup_tools": lookup_tools,
                            "question": f"⚠️ 执行 {tool_def.name} 需要以下参数：{', '.join(missing_params)}，请提供这些参数",
                        },
                    })
                    trace.confirmation(node, reason="missing_parameters")
                    needs_confirmation = True
                    confirmation_payload = results[-1]["confirmation_payload"]
                    chain_blocked = True
                    chain_blocker = tool_def.name
                    session.ctx.account_id = original_account
                    continue

                schema_errors = (
                    validate_tool_input(tool_def.input_schema, tool_input)
                    if tool_def.input_schema else []
                )
                if schema_errors:
                    results.append({
                        "tool": tool_def.name,
                        "platform": platform,
                        "success": False,
                        "error": f"Input validation failed: {schema_errors}",
                        "needs_confirmation": False,
                    })
                    trace.node_status(node, "failed", safe_metadata={"reason": "schema_invalid"})
                    chain_blocked = True
                    chain_blocker = tool_def.name
                    session.ctx.account_id = original_account
                    continue

                # Provider-specific requirements are stricter than the
                # fields needed to generate a dry-run plan.  Validate them
                # before confirmation/client execution only in the live path,
                # so dry-run can still preview an incomplete plan while live
                # can fail with an actionable error before any API call.
                if tool_def.is_write_tool and self.execution_mode == ExecutionMode.LIVE.value:
                    provider_errors = validate_tool_input(
                        tool_def.input_schema,
                        tool_input,
                        include_provider_contract=True,
                    )
                    if provider_errors:
                        results.append({
                            "tool": tool_def.name,
                            "platform": platform,
                            "success": False,
                            "error": f"Provider contract validation failed: {provider_errors}",
                            "needs_confirmation": False,
                        })
                        trace.node_status(node, "failed", safe_metadata={"reason": "provider_contract_invalid"})
                        chain_blocked = True
                        chain_blocker = tool_def.name
                        session.ctx.account_id = original_account
                        continue

                if tool_def.is_write_tool and self.execution_mode == ExecutionMode.LIVE.value and (
                    not self.allow_live_writes
                    or not tool_def.live_support
                    or tool_def.name not in self._live_approved_tools
                ):
                    if not self.allow_live_writes:
                        reason = "Runtime 全局 allow_live_writes 未开启"
                    elif not tool_def.live_support:
                        reason = "该 Tool 当前仅支持 dry-run"
                    else:
                        reason = "该 Tool 未加入 live 执行批准清单"
                    results.append({
                        "tool": tool_def.name,
                        "platform": platform,
                        "success": False,
                        "error": f"{tool_def.name} 当前禁止 live 执行：{reason}",
                        "needs_confirmation": False,
                    })
                    trace.node_status(node, "failed", safe_metadata={"reason": "live_write_blocked"})
                    chain_blocked = True
                    chain_blocker = tool_def.name
                    session.ctx.account_id = original_account
                    continue

                if (
                    tool_def.is_write_tool
                    and self.execution_mode == ExecutionMode.LIVE.value
                    and self.write_guard is None
                ):
                    results.append({
                        "tool": tool_def.name,
                        "platform": platform,
                        "success": False,
                        "error": "live 写操作必须配置 WriteGuard；已拒绝执行",
                        "needs_confirmation": False,
                    })
                    trace.node_status(node, "failed", safe_metadata={"reason": "write_guard_missing"})
                    chain_blocked = True
                    chain_blocker = tool_def.name
                    session.ctx.account_id = original_account
                    continue

                # live 写入必须由调用方显式确认；dry-run 不需要确认，因为不会
                # 触发外部写 API。确认状态只来自受信任的请求字段，不从自然语言推断。
                expected_confirmation = None
                if tool_def.is_write_tool and self.execution_mode == ExecutionMode.LIVE.value:
                    expected_confirmation = self.security.prepare_confirmation(
                        self.security.confirmation_plan(
                            session_id, session.ctx.user_id, session.ctx.account_id,
                            tool_def, tool_input,
                        ),
                        create=not confirmed,
                    )

                if (
                    tool_def.is_write_tool
                    and self.execution_mode == ExecutionMode.LIVE.value
                    and confirmed
                    and incoming_confirmation_payload is None
                ):
                    results.append({
                        "tool": tool_def.name,
                        "platform": platform,
                        "success": False,
                        "error": "confirmed=true 必须携带当前写入计划的 confirmation_payload",
                        "needs_confirmation": True,
                        "confirmation_payload": {
                            "type": "confirm_write",
                            **(expected_confirmation or {}),
                            "input": self._redact_for_persistence(tool_input),
                            "question": "请使用当前计划返回的 confirmation_payload 确认。",
                        },
                    })
                    trace.confirmation(node, reason="confirmation_payload_required")
                    needs_confirmation = True
                    confirmation_payload = results[-1]["confirmation_payload"]
                    chain_blocked = True
                    chain_blocker = tool_def.name
                    session.ctx.account_id = original_account
                    continue

                if tool_def.is_write_tool and self.execution_mode == ExecutionMode.LIVE.value and confirmed and incoming_confirmation_payload is not None and not self.security.confirmation_matches(
                    incoming_confirmation_payload, expected_confirmation or {}
                ):
                    results.append({
                        "tool": tool_def.name,
                        "platform": platform,
                        "success": False,
                        "error": "确认信息与当前写入计划不匹配，已拒绝执行",
                        "needs_confirmation": True,
                        "confirmation_payload": {
                            "type": "confirm_write",
                            **(expected_confirmation or {}),
                            "input": self._redact_for_persistence(tool_input),
                            "question": "写入计划已变化，请使用最新计划重新确认。",
                        },
                    })
                    trace.confirmation(node, reason="confirmation_mismatch")
                    needs_confirmation = True
                    confirmation_payload = results[-1]["confirmation_payload"]
                    chain_blocked = True
                    chain_blocker = tool_def.name
                    session.ctx.account_id = original_account
                    continue

                if (
                    tool_def.is_write_tool
                    and self.execution_mode == ExecutionMode.LIVE.value
                    and confirmed
                    and incoming_confirmation_payload is not None
                ):
                    approval_ok, approval_error = self.security.validate_confirmation_record(
                        expected_confirmation or {}, incoming_confirmation_payload
                    )
                    if not approval_ok:
                        results.append({
                            "tool": tool_def.name,
                            "platform": platform,
                            "success": False,
                            "error": f"确认记录无效：{approval_error}",
                            "needs_confirmation": True,
                            "confirmation_payload": {
                                "type": "confirm_write",
                                **(expected_confirmation or {}),
                                "input": self._redact_for_persistence(tool_input),
                                "question": "确认记录已过期或已使用，请重新生成计划并确认。",
                            },
                        })
                        trace.confirmation(node, reason="confirmation_invalid")
                        needs_confirmation = True
                        confirmation_payload = results[-1]["confirmation_payload"]
                        chain_blocked = True
                        chain_blocker = tool_def.name
                        session.ctx.account_id = original_account
                        continue

                if tool_def.is_write_tool and self.execution_mode == ExecutionMode.LIVE.value and not confirmed:
                    results.append({
                        "tool": tool_def.name,
                        "platform": platform,
                        "success": False,
                        "error": "live 写操作等待显式确认",
                        "needs_confirmation": True,
                        "confirmation_payload": {
                            "type": "confirm_write",
                            "tool": tool_def.name,
                            "platform": actual_platform,
                            "input": self._redact_for_persistence(tool_input),
                            **(expected_confirmation or {}),
                            "question": f"即将对 {actual_platform} 执行 live 写操作 {tool_def.name}，请确认。",
                        },
                    })
                    trace.confirmation(node, reason="live_confirmation_required")
                    needs_confirmation = True
                    confirmation_payload = results[-1]["confirmation_payload"]
                    chain_blocked = True
                    chain_blocker = tool_def.name
                    session.ctx.account_id = original_account
                    continue

                # 使用最终规范化后的输入生成幂等键，保证 reserve 与成功后的
                # mark_executed 使用同一组字段；不能使用原始自然语言参数。
                if (
                    self.execution_mode == ExecutionMode.LIVE.value
                    and not self._read_only_mode
                    and tool_def.is_write_tool
                    and self.write_guard
                ):
                    allowed, reason = self.write_guard.reserve_write(
                        session.ctx, tool_def, tool_input
                    )
                    if not allowed:
                        results.append({
                            "tool": tool_def.name,
                            "platform": platform,
                            "success": False,
                            "error": f"Write guard blocked: {reason}",
                        })
                        trace.node_status(node, "failed", safe_metadata={"reason": "write_guard_blocked"})
                        chain_blocked = True
                        chain_blocker = tool_def.name
                        session.ctx.account_id = original_account
                        continue
                
                # dry-run 下写工具只生成本地模拟结果，绝不触发 API Client。
                started_at = datetime.now().isoformat()
                trace.node_status(
                    node,
                    "running",
                    safe_input=self._redact_for_persistence(tool_input),
                )
                try:
                    if tool_def.is_write_tool and self.is_dry_run:
                        schema_errors = validate_tool_input(tool_def.input_schema, tool_input) if tool_def.input_schema else []
                        if schema_errors:
                            result = ToolResult.error(f"Input validation failed: {schema_errors}")
                        else:
                            result = self._simulate_write(tool_def, tool_input, actual_platform)
                    else:
                        result = self.tool_executor.execute(
                            session.ctx, tool_def.name, tool_input, request_clients
                        )
                except Exception as exc:
                    logger.exception("工具执行失败: %s", tool_def.name)
                    result = ToolResult.error(f"工具执行失败: {exc}")

                result = self.security.normalize_read_result_evidence(tool_def, result)
                result = self.input_builder.decorate_lookup_result(
                    tool_def, result, session.ctx, actual_platform
                )
                result = self.security.enforce_result_limit(result, tool_def)
                if self.security.is_uncertain_provider_failure(tool_def, result):
                    # A transport/temporary error does not prove that the
                    # provider rejected the write. Persist an explicit
                    # unknown outcome so workflow recovery and reconciliation
                    # do not depend on parsing the human-readable error.
                    result.data = {
                        **(result.data if isinstance(result.data, dict) else {}),
                        "execution_status": "unknown",
                    }
                self.workflow.heartbeat(workflow_id)

                resource_type = getattr(tool_def, "resource_type", None)
                resource_id_field = self._resource_id_field_for_tool(tool_def)
                parent_type = getattr(tool_def, "parent_resource_type", None)
                parent_field = self._parent_resource_id_field_for_tool(tool_def)
                parent_id = tool_input.get(parent_field) if parent_field else None
                # Keep hierarchy metadata next to the provider result. This
                # is especially important for live adapters whose response
                # only contains the newly created object's ID.
                if resource_type and isinstance(result.data, dict):
                    result.data = {
                        **result.data,
                        "resource_type": resource_type,
                        "resource_id_field": resource_id_field,
                        "parent_resource_type": parent_type,
                        "parent_resource_id_field": parent_field,
                        "parent_resource_id": (
                            str(parent_id) if parent_id not in (None, "") else None
                        ),
                    }

                result_index = len(results)
                safe_result_data = self._redact_for_persistence(result.data)
                safe_result_error = self._redact_for_persistence(result.error)
                results.append({
                    "tool": tool_def.name,
                    "platform": platform,
                    "resource_type": resource_type,
                    "resource_id_field": resource_id_field,
                    "parent_resource_type": parent_type,
                    "parent_resource_id_field": parent_field,
                    "parent_resource_id": (
                        str(parent_id) if parent_id not in (None, "") else None
                    ),
                    "account_id": per_platform_account,
                    "success": result.success,
                    "data": safe_result_data,
                    "error": safe_result_error,
                    "needs_confirmation": result.requires_confirmation,
                })
                execution_status = (
                    result.data.get("execution_status")
                    if isinstance(result.data, dict) else None
                )
                result_status = (
                    "awaiting_confirmation" if result.requires_confirmation
                    else "succeeded" if result.success
                    else "unknown" if execution_status == "unknown"
                    else "failed"
                )
                trace.node_status(
                    node,
                    result_status,
                    safe_metadata={
                        "simulated": bool(result.simulated),
                        "execution_status": execution_status,
                    },
                    safe_input=self._redact_for_persistence(tool_input),
                    safe_output={
                        "success": bool(result.success),
                        "data": safe_result_data,
                        "has_error": bool(safe_result_error),
                        "execution_status": execution_status,
                    },
                )
                workflow_inputs[result_index] = copy.deepcopy(tool_input)

                if not result.success or result.requires_confirmation:
                    chain_blocked = True
                    chain_blocker = tool_def.name
                
                if result.requires_confirmation:
                    needs_confirmation = True
                    confirmation_payload = result.card_payload
                
                # 保存执行结果到会话上下文（跨 Tool 传递）
                safe_result = ToolResult(
                    success=result.success,
                    data=safe_result_data,
                    error=safe_result_error,
                    requires_confirmation=result.requires_confirmation,
                    card_payload=self._redact_for_persistence(result.card_payload),
                    simulated=result.simulated,
                )
                session.save_result(tool_def.name, safe_result, platform=actual_platform)

                # 将 protected_state 同步回 ctx，使后续 Tool 可以读取
                session.ctx.protected_state.update(session.protected_state)

                # 成功的 live 写入才进入幂等记录；dry-run 不污染 live 去重状态。
                if (
                    result.success and not result.simulated and not result.requires_confirmation
                    and tool_def.is_write_tool
                    and self.write_guard and hasattr(self.write_guard, "mark_executed")
                ):
                    self.write_guard.mark_executed(tool_def.name, tool_input, session.ctx.user_id)
                    if expected_confirmation and incoming_confirmation_payload:
                        if self._session_manager:
                            self._session_manager.consume_approval(
                                expected_confirmation["plan_fingerprint"],
                                expected_confirmation["confirmation_token"],
                            )
                elif (
                    (not result.success or result.requires_confirmation)
                    and self.execution_mode == ExecutionMode.LIVE.value
                    and tool_def.is_write_tool
                    and self.write_guard
                    and hasattr(self.write_guard, "release_write")
                    and not self.security.is_uncertain_provider_failure(tool_def, result)
                ):
                    self.write_guard.release_write(
                        tool_def.name, tool_input, session.ctx.user_id
                    )

                # 记录安全审计信息，并保存本地模拟 Campaign 状态。
                self._persist_tool_result(
                    session, turn_id, tool_def, actual_platform,
                    tool_input, result,
                )

                # 恢复原始账户上下文
                session.ctx.account_id = original_account

        # Cross-channel comparison is a two-phase read workflow: first list
        # campaigns, then collect campaign-scoped report rows.
        analysis_owner = getattr(feature, "handles_analysis", None) if feature is not None else None
        analysis_stage_active = bool(
            feature is not None
            and callable(analysis_owner)
            and analysis_owner(intent)
        )
        if analysis_stage_active:
            trace.stage_status(
                "analysis",
                "结果分析",
                "running",
                subtitle="整理工具结果并提取业务信息",
                safe_metadata={"phase": "result_analysis"},
                safe_input={"result_count": len(results)},
            )
        if feature is not None and callable(
            getattr(feature, "collect_metrics", None)
        ):
            feature.collect_metrics(
                self.services,
                intent, tool_plan, results, session, turn_id, request_clients,
                account_scope=account_scope,
                granted_permissions=effective_permissions,
                execution_trace=trace,
            )
        self.workflow.finish(workflow_id, tool_plan, results, workflow_inputs)
        resource_results = self._build_resource_results(results)

        analysis: dict[str, Any] = {}
        if feature is not None and callable(getattr(feature, "analyze", None)):
            analysis = feature.analyze(intent, results)
        if analysis_stage_active:
            trace.stage_status(
                "analysis",
                "结果分析",
                "succeeded",
                subtitle="结果已整理完成",
                safe_metadata={"result_count": len(results)},
                safe_input={"result_count": len(results)},
                safe_output={
                    "result_count": len(results),
                    "analysis_available": bool(analysis),
                    "summary": self._redact_for_persistence(analysis or {}),
                },
            )
        trace.stage_status(
            "reply",
            "回复生成",
            "running",
            subtitle="生成面向业务人员的结果说明",
            safe_metadata={"phase": "response_rendering"},
            safe_input={
                "result_count": len(results),
                "needs_confirmation": needs_confirmation,
            },
        )
        if creation_ui.get("needs_input") and not any(
            isinstance(item.get("confirmation_payload"), dict)
            and item["confirmation_payload"].get("type") == "ask_account"
            for item in results
        ):
            reply, response_source = self.creation_ui_reply(creation_ui), "creation_card"
        else:
            reply, response_source = self._render_response(
                safe_user_input,
                intent,
                results,
                needs_confirmation,
                analysis=analysis,
                session=session,
            )
        trace.stage_status(
            "reply",
            "回复生成",
            "succeeded",
            subtitle="已生成本轮回复",
            safe_metadata={"response_source": response_source},
            safe_output={
                "response_source": response_source,
                "available": True,
                "preview": self._redact_for_persistence(reply),
            },
        )
        trace.reply(needs_confirmation=needs_confirmation)
        has_failure = any(
            not item.get("success", False) and not item.get("skipped", False)
            for item in results
        )
        trace.done(
            "awaiting_confirmation" if needs_confirmation else "failed" if has_failure else "succeeded",
            safe_metadata={"tool_count": len(results)},
        )
        
        # Step 6: 记录消息历史
        self.persist_conversation_turn(
            session, turn_id, safe_user_input, reply,
            execution_trace=trace, ui=creation_ui,
        )
        
        return {
            "session_id": session_id,
            "turn_id": turn_id,
            "timestamp": datetime.now().isoformat(),
            "intent": intent.to_dict(),
            "tool_plan": {k: [t.name for t in v] for k, v in tool_plan.items()},
            "tool_selection": {
                "tool_count": tool_selection["tool_count"],
                "tools": [tool.name for tool in tool_selection["selected_tools"]],
                "platforms": tool_selection["platforms"],
                "context": tool_selection["context"],
                "tool_prompt": tool_selection["tool_prompt"],
                "expert_knowledge": tool_selection["expert_knowledge"],
                "knowledge": tool_selection.get("knowledge", []),
            },
            "memory": recalled_memories,
            "response_source": response_source,
            "execution_plan": execution_plan.to_dict(),
            "results": results,
            "resource_results": resource_results,
            "workflow_id": workflow_id,
            **(
                feature.preflight_payload(creation_preflight)
                if creation_preflight is not None
                and callable(getattr(feature, "preflight_payload", None))
                else (
                    {"preflight": creation_preflight.to_dict()}
                    if creation_preflight is not None
                    else {}
                )
            ),
            **(analysis if isinstance(analysis, dict) else {}),
            "reply": reply,
            "needs_confirmation": needs_confirmation,
            "confirmation_payload": confirmation_payload,
            "ui": creation_ui,
        }
    
# ─── Session 管理 ──────────────────────────────────────────

    @staticmethod
    def _decode_session_metadata(session: Mapping[str, Any]) -> dict[str, Any]:
        value = session.get("metadata")
        if isinstance(value, dict):
            return dict(value)
        if isinstance(value, str):
            try:
                decoded = json.loads(value or "{}")
                return decoded if isinstance(decoded, dict) else {}
            except (TypeError, ValueError):
                return {}
        return {}

    @staticmethod
    def _conversation_summary(
        session: Mapping[str, Any], messages: list[Mapping[str, Any]],
    ) -> dict[str, Any]:
        user_messages = [item for item in messages if item.get("role") == "user"]
        title_source = str((user_messages[0] if user_messages else messages[0]).get("content", "")) if messages else "新对话"
        metadata = AgentRuntime._decode_session_metadata(session)
        title = str(metadata.get("conversation_title") or "").strip()
        if not title:
            title = ConversationTitleGenerator.fallback_title(title_source)
        latest = str(messages[-1].get("content", "")) if messages else ""
        return {
            "session_id": str(session.get("session_id") or ""),
            "title": title,
            "preview": " ".join(latest.split())[:100],
            "message_count": len(messages) or int(session.get("message_count") or 0),
            "created_at": session.get("created_at"),
            "updated_at": session.get("updated_at"),
        }

    def list_conversations(
        self, user_id: str, tenant_id: str = "default", limit: int = 50,
    ) -> list[dict[str, Any]]:
        """List only the authenticated principal's durable conversations."""
        if not self._session_manager:
            return []
        conversations = []
        for session in self._session_manager.list_sessions(user_id, limit=limit):
            metadata = self._decode_session_metadata(session)
            if str(metadata.get("tenant_id", "default")) != str(tenant_id or "default"):
                continue
            records = self._session_manager.list_conversation_messages(
                str(session.get("session_id") or ""), limit=500
            )
            messages = [record.to_dict() for record in records]
            if not messages:
                legacy = metadata.get("messages")
                messages = legacy if isinstance(legacy, list) else []
            conversations.append(self._conversation_summary(session, messages))
        return conversations[:limit]

    def rename_conversation(
        self, session_id: str, title: str, *, user_id: str,
        tenant_id: str = "default",
    ) -> Optional[dict[str, Any]]:
        """Rename one local conversation inside the authenticated scope."""
        if not self._session_manager:
            return None
        persisted = self._session_manager.get_session(str(session_id))
        if not persisted:
            return None
        if persisted.get("user_id") and str(persisted["user_id"]) != str(user_id):
            return None
        metadata = self._decode_session_metadata(persisted)
        if str(metadata.get("tenant_id", "default")) != str(tenant_id or "default"):
            return None
        safe_title = self._redact_for_persistence(str(title or "")).strip()
        if not safe_title:
            raise ValueError("对话标题不能为空")
        if len(safe_title) > ConversationTitleGenerator.MAX_TITLE_CHARS:
            raise ValueError(
                f"对话标题不能超过 {ConversationTitleGenerator.MAX_TITLE_CHARS} 个字符"
            )
        metadata["conversation_title"] = safe_title
        metadata["conversation_title_source"] = "manual"
        self._session_manager.update_session(str(session_id), metadata)
        session = self._sessions.get(str(session_id))
        if session is not None:
            session.ctx.metadata.update({
                "conversation_title": safe_title,
                "conversation_title_source": "manual",
            })
        return {"session_id": str(session_id), "title": safe_title}

    def search_knowledge(
        self, query: str, *, tenant_id: str = "default",
        platform: Optional[str] = None, knowledge_type: Optional[str] = None,
        limit: int = 10, max_excerpt_chars: int = 1200,
    ) -> list[dict[str, Any]]:
        """Search built-in and published tenant Wiki documents."""
        if self.knowledge_provider is None:
            return []
        kwargs: dict[str, Any] = {
            "platforms": [platform] if platform else None,
            "knowledge_types": [knowledge_type] if knowledge_type else None,
            "limit": limit,
            "max_excerpt_chars": max_excerpt_chars,
        }
        try:
            parameters = inspect.signature(self.knowledge_provider.query).parameters
            if "tenant_id" in parameters or any(
                item.kind == inspect.Parameter.VAR_KEYWORD
                for item in parameters.values()
            ):
                kwargs["tenant_id"] = tenant_id
        except (TypeError, ValueError):
            pass
        documents = self.knowledge_provider.query(query, **kwargs)
        return [document.to_dict() for document in documents]

    def summarize_knowledge(
        self, query: str, documents: list[dict[str, Any]],
    ) -> str:
        """Create a business-facing summary without executing any Tool."""
        safe_documents = self._redact_for_persistence(documents or [])
        if not safe_documents:
            return "暂时没有找到匹配的知识内容。可以换一个关键词，或扩大平台范围。"
        fallback_parts = []
        for document in safe_documents[:3]:
            title = str(document.get("title") or document.get("topic") or "相关知识")
            excerpt = re.sub(r"[#>*`|-]+", " ", str(document.get("excerpt") or ""))
            excerpt = " ".join(excerpt.split())[:180]
            fallback_parts.append(f"{title}：{excerpt}" if excerpt else title)
        fallback = "根据检索到的资料，重点参考：" + "；".join(fallback_parts) + "。"
        if self._llm is None:
            return fallback[:1200]
        prompt = (
            "你是广告运营知识助手。请根据用户问题和检索到的 Markdown Wiki 资料，"
            "用中文写一段面向广告运营人员的简短总结，先给结论，再给 2 到 4 条关键点。"
            "不要提及模型、Runtime、Tool、API、检索过程或内部字段；不要编造资料中没有的事实。"
            "只返回总结正文，不要包裹 JSON。\n\n"
            f"用户问题：{str(query or '')[:2000]}\n"
            f"资料：{json.dumps(safe_documents[:6], ensure_ascii=False, default=str)[:12000]}"
        )
        try:
            try:
                answer = self._llm.call(
                    [{"role": "system", "content": "只输出业务总结。"},
                     {"role": "user", "content": prompt}],
                    temperature=0.2,
                )
            except TypeError:
                answer = self._llm.call(
                    [{"role": "system", "content": "只输出业务总结。"},
                     {"role": "user", "content": prompt}],
                )
            answer = self._redact_for_persistence(str(answer or "")).strip()
            internal_terms = ("runtime", "tool", "provider", "intent_type", "access_token")
            if not answer or len(answer) > 1600 or any(
                term in answer.lower() for term in internal_terms
            ):
                return fallback[:1200]
            return answer
        except Exception:
            return fallback[:1200]

    def get_conversation(
        self, session_id: str, user_id: str, tenant_id: str = "default",
        limit: int = 500,
    ) -> Optional[dict[str, Any]]:
        """Load one conversation after enforcing user and tenant ownership."""
        if not self._session_manager:
            return None
        session = self._session_manager.get_session(session_id)
        if not session or str(session.get("user_id") or "") != str(user_id):
            return None
        metadata = self._decode_session_metadata(session)
        if str(metadata.get("tenant_id", "default")) != str(tenant_id or "default"):
            return None
        records = self._session_manager.list_conversation_messages(session_id, limit=limit)
        messages = [
            {
                "role": record.role,
                "content": self._redact_for_persistence(record.content),
                "created_at": record.created_at,
                "turn_id": record.turn_id,
            }
            for record in records
        ]
        ui_by_turn = metadata.get("conversation_ui", {})
        if isinstance(ui_by_turn, dict):
            for message in messages:
                if message.get("role") != "assistant":
                    continue
                stored_ui = ui_by_turn.get(str(message.get("turn_id")))
                if isinstance(stored_ui, dict) and stored_ui:
                    message["ui"] = self._redact_for_persistence(stored_ui)
        if not messages:
            legacy = metadata.get("messages")
            messages = legacy if isinstance(legacy, list) else []
        summary = self._conversation_summary(session, messages)
        traces = metadata.get("execution_traces")
        if not isinstance(traces, dict) or not traces:
            # Older sessions predate durable lifecycle snapshots. Rebuild a
            # tool-level trace from the already-sanitized audit records so
            # opening an existing conversation still shows what ran.
            traces = self._legacy_execution_traces(session_id)
        return {
            **summary,
            "messages": messages,
            "execution_traces": traces if isinstance(traces, dict) else {},
        }

    def delete_conversation(
        self, session_id: str, user_id: str, tenant_id: str = "default",
    ) -> bool:
        """Delete one conversation after enforcing its user/tenant scope."""
        if not self._session_manager:
            return False
        normalized_session_id = str(session_id or "").strip()
        if not normalized_session_id:
            return False
        session = self._session_manager.get_session(normalized_session_id)
        if not session or str(session.get("user_id") or "") != str(user_id):
            return False
        metadata = self._decode_session_metadata(session)
        if str(metadata.get("tenant_id", "default")) != str(tenant_id or "default"):
            return False
        deleted = self._session_manager.delete_session(normalized_session_id)
        if deleted:
            self._sessions.pop(normalized_session_id, None)
        return deleted

    def delete_conversations(
        self, session_ids: list[str], user_id: str,
        tenant_id: str = "default",
    ) -> list[str]:
        """Delete up to the caller-selected conversations in one scoped action."""
        deleted: list[str] = []
        seen: set[str] = set()
        for session_id in session_ids or []:
            normalized_session_id = str(session_id or "").strip()
            if not normalized_session_id or normalized_session_id in seen:
                continue
            seen.add(normalized_session_id)
            if self.delete_conversation(
                normalized_session_id, user_id=user_id, tenant_id=tenant_id
            ):
                deleted.append(normalized_session_id)
        return deleted

    def _legacy_execution_traces(self, session_id: str) -> dict[str, dict[str, Any]]:
        """Build a bounded compatibility trace from durable Tool audit rows."""
        if not self._session_manager:
            return {}
        records = list(reversed(self._session_manager.get_session_history(
            session_id, limit=200
        )))
        grouped: dict[str, list[Any]] = {}
        for record in records:
            turn_id = str(getattr(record, "turn_id", "") or "legacy")
            grouped.setdefault(turn_id, []).append(record)
        snapshots: dict[str, dict[str, Any]] = {}
        for turn_id, turn_records in list(grouped.items())[-20:]:
            nodes = []
            events = [{
                "type": "start", "event_type": "start", "trace_id": f"legacy:{turn_id}",
                "turn_id": turn_id, "seq": 1, "status": "running",
                "safe_metadata": {"source": "durable_tool_audit"},
            }]
            sequence = 1
            for index, record in enumerate(turn_records, start=1):
                tool_name = str(getattr(record, "tool_name", "") or "Tool")
                platform = str(getattr(record, "platform", "") or "")
                node_id = f"legacy-node-{index:04d}"
                nodes.append({
                    "node_id": node_id, "sequence": index,
                    "platform": platform, "tool": tool_name,
                    "action": "", "resource_type": "",
                    "depends_on": [nodes[-1]["node_id"]] if nodes else [],
                })
                sequence += 1
                events.append({
                    "type": "node_started", "event_type": "node_started",
                    "trace_id": f"legacy:{turn_id}", "turn_id": turn_id,
                    "seq": sequence, "node_id": node_id, "platform": platform,
                    "tool": tool_name, "status": "running",
                    "safe_input": self._redact_for_persistence(getattr(record, "input_data", {})),
                })
                sequence += 1
                success = bool(getattr(record, "success", False))
                events.append({
                    "type": "node_status", "event_type": "node_status",
                    "trace_id": f"legacy:{turn_id}", "turn_id": turn_id,
                    "seq": sequence, "node_id": node_id, "platform": platform,
                    "tool": tool_name, "status": "succeeded" if success else "failed",
                    "safe_input": self._redact_for_persistence(getattr(record, "input_data", {})),
                    "safe_output": self._redact_for_persistence(getattr(record, "output_data", {})),
                    "safe_metadata": {
                        "reason": self._redact_for_persistence(getattr(record, "error", "")),
                        "source": "durable_tool_audit",
                    },
                })
            sequence += 1
            final_status = "succeeded" if all(
                bool(getattr(record, "success", False)) for record in turn_records
            ) else "failed"
            events.append({
                "type": "done", "event_type": "done",
                "trace_id": f"legacy:{turn_id}", "turn_id": turn_id,
                "seq": sequence, "status": final_status,
                "safe_metadata": {"source": "durable_tool_audit"},
            })
            snapshots[turn_id] = {
                "trace_id": f"legacy:{turn_id}", "turn_id": turn_id,
                "status": final_status, "events": [
                    {"type": "plan", "event_type": "plan", "trace_id": f"legacy:{turn_id}",
                     "turn_id": turn_id, "seq": 2, "status": "planned",
                     "execution_plan": {"schema_version": "1.0", "intent_type": "legacy",
                                         "nodes": nodes}},
                    *events,
                ],
            }
        return snapshots
    
    def _ensure_session(
        self,
        session_id: str,
        user_id: str,
        account_id: str,
        credentials: dict,
        tenant_id: str = "default",
    ) -> "SessionContext":
        if session_id not in self._sessions:
            persisted = self._session_manager.get_session(session_id) if self._session_manager else None
            if persisted:
                persisted_user = persisted.get("user_id")
                persisted_account = persisted.get("account_id")
                if persisted_user and persisted_user != user_id:
                    raise PermissionError("session belongs to a different user")
                if account_id and persisted_account and str(account_id) != str(persisted_account):
                    raise PermissionError("session belongs to a different account")
            persisted_metadata = {}
            if persisted and persisted.get("metadata"):
                try:
                    persisted_metadata = json.loads(persisted["metadata"])
                except (TypeError, ValueError):
                    persisted_metadata = {}
            persisted_tenant = str(persisted_metadata.get("tenant_id", "default"))
            if persisted and persisted_tenant != str(tenant_id or "default"):
                raise PermissionError("session belongs to a different tenant")
            ctx = ToolContext(
                session_id=session_id,
                user_id=user_id,
                account_id=account_id or (persisted or {}).get("account_id"),
                credentials=self._freeze_credentials(copy.deepcopy(credentials or {})),
            )
            session = SessionContext(session_id, ctx)
            ctx.metadata["tenant_id"] = str(tenant_id or "default")
            stored_title = persisted_metadata.get("conversation_title")
            if isinstance(stored_title, str) and stored_title.strip():
                ctx.metadata["conversation_title"] = stored_title.strip()
                ctx.metadata["conversation_title_source"] = str(
                    persisted_metadata.get("conversation_title_source") or "legacy"
                )
            stored_traces = persisted_metadata.get("execution_traces")
            if isinstance(stored_traces, dict):
                ctx.metadata["execution_traces"] = stored_traces
            stored_ui = persisted_metadata.get("conversation_ui")
            if isinstance(stored_ui, dict):
                ctx.metadata["conversation_ui"] = stored_ui
            session.messages = persisted_metadata.get("messages", [])[-20:]
            ctx.messages = list(session.messages)
            if self._session_manager and persisted:
                for record in reversed(self._session_manager.get_session_history(session_id, limit=20)):
                    if record.output_data:
                        session.save_result(
                            record.tool_name,
                            ToolResult.ok(record.output_data),
                            platform=record.platform,
                        )
                # Restore resource IDs into the actual ToolContext before the
                # first tool of the new turn, not only after a new tool runs.
                ctx.protected_state.update(session.protected_state)
            self._sessions[session_id] = session
            
            # Create only genuinely new sessions. INSERT OR REPLACE here would
            # otherwise erase a persisted account_id when the caller omits it
            # during session restoration.
            if self._session_manager and not persisted:
                self._session_manager.create_session(
                    session_id,
                    user_id,
                    account_id,
                    {
                        "execution_mode": self.execution_mode,
                        "read_only_mode": self._read_only_mode,
                        "tenant_id": str(tenant_id or "default"),
                    },
                )
        session = self._sessions[session_id]
        if session.ctx.user_id != user_id:
            raise PermissionError("session belongs to a different user")
        if str(session.ctx.metadata.get("tenant_id", "default")) != str(tenant_id or "default"):
            raise PermissionError("session belongs to a different tenant")
        if account_id and session.ctx.account_id and str(account_id) != str(session.ctx.account_id):
            raise PermissionError("session belongs to a different account")
        if credentials:
            session.ctx.credentials = self._freeze_credentials(copy.deepcopy(credentials))
        return session
    
    def get_workflow(
        self,
        workflow_id: str,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> Optional[dict]:
        """Read a durable workflow while enforcing its owning user boundary."""
        if not self._session_manager:
            return None
        workflow = self._session_manager.get_workflow(workflow_id)
        if not workflow:
            return None
        if user_id is not None or tenant_id is not None:
            session = self._session_manager.get_session(workflow.get("session_id")) or {}
            if user_id is not None and str(session.get("user_id")) != str(user_id):
                raise PermissionError("workflow belongs to a different user")
            if tenant_id is not None:
                try:
                    metadata = json.loads(session.get("metadata") or "{}")
                except (TypeError, ValueError):
                    metadata = {}
                if str(metadata.get("tenant_id", "default")) != str(tenant_id or "default"):
                    raise PermissionError("workflow belongs to a different tenant")
        return workflow

    def get_workflow_resume_plan(
        self,
        workflow_id: str,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> dict:
        """Return a safe replay plan without executing any provider operation.

        Recovery is deliberately an explicit two-step protocol.  This method
        only exposes the durable items that still need action; a future worker
        must call the normal Runtime path with a fresh approval and current
        principal instead of replaying handlers directly from SQLite.
        """
        workflow = self.get_workflow(
            workflow_id, user_id=user_id, tenant_id=tenant_id
        )
        if not workflow:
            raise KeyError("workflow not found")
        if workflow.get("status") == "running" and self._is_stale_workflow(workflow):
            self._session_manager.recover_stale_workflow(
                workflow_id,
                self.workflow_stale_after_seconds,
                {
                    "recovery_reason": "stale_running_workflow",
                    "recovery_detected_at": datetime.now().isoformat(),
                },
            )
            workflow = self.get_workflow(
                workflow_id, user_id=user_id, tenant_id=tenant_id
            ) or workflow
        resumable = {"failed", "partially_failed", "recovery_required", "blocked"}
        if workflow.get("status") not in resumable:
            return {
                "workflow_id": workflow_id,
                "status": workflow.get("status"),
                "resumable": False,
                "requires_fresh_confirmation": False,
                "items": [],
            }
        pending = [
            item for item in workflow.get("items", [])
            if item.get("status") not in {"succeeded", "unsupported"}
        ]
        session_record = (
            self._session_manager.get_session(workflow.get("session_id"))
            if self._session_manager else None
        ) or {}
        session_account_id = str(session_record.get("account_id") or "")

        def item_account_id(item: Mapping[str, Any]) -> Optional[str]:
            account_id = item.get("account_id")
            if account_id not in (None, ""):
                return str(account_id)
            input_data = item.get("input_data")
            if isinstance(input_data, Mapping):
                for key in ("account_id", "advertiser_id", "customer_id"):
                    value = input_data.get(key)
                    if value not in (None, ""):
                        return str(value)
            return session_account_id or None

        definitions = {
            definition.name: definition
            for definition in self.registry.list_all()
        }

        def item_definition_value(
            item: Mapping[str, Any], field: str,
        ) -> Optional[str]:
            value = item.get(field)
            if value not in (None, ""):
                return str(value)
            definition = definitions.get(str(item.get("tool_name") or ""))
            value = getattr(definition, field, None) if definition else None
            return str(value) if value not in (None, "") else None

        return {
            "workflow_id": workflow_id,
            "status": workflow.get("status"),
            "resumable": bool(pending),
            "requires_fresh_confirmation": workflow.get("execution_mode") == ExecutionMode.LIVE.value,
            "replay_policy": "explicit_operator_confirmation",
            "items": [
                {
                    "sequence": item.get("sequence"),
                    "platform": self._canonical_platform(str(item.get("platform") or "")),
                    "account_id": item_account_id(item),
                    "tool_name": item.get("tool_name"),
                    "resource_type": item_definition_value(item, "resource_type"),
                    "parent_resource_type": item_definition_value(
                        item, "parent_resource_type"
                    ),
                    "parent_resource_id": item.get("parent_resource_id"),
                    "status": item.get("status"),
                    "input_data": self._redact_for_persistence(item.get("input_data") or {}),
                    "error": self._redact_for_persistence(item.get("error")),
                }
                for item in pending
            ],
        }

    def _is_stale_workflow(self, workflow: Mapping[str, Any]) -> bool:
        """Treat a running workflow as recoverable only after its lease age."""
        try:
            updated_at = datetime.fromisoformat(str(workflow.get("updated_at")))
            age = (datetime.now() - updated_at).total_seconds()
        except (TypeError, ValueError, OverflowError):
            return False
        return age >= self.workflow_stale_after_seconds

    def list_resumable_workflows(
        self, user_id: Optional[str] = None, tenant_id: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict]:
        """List failed or stale-running workflows within an optional tenant."""
        if not self._session_manager:
            return []
        workflows = self._session_manager.list_resumable_workflows(
            user_id=user_id,
            limit=limit,
            include_stale_running=True,
            stale_after_seconds=self.workflow_stale_after_seconds,
        )
        if tenant_id is None:
            return workflows
        filtered = []
        for workflow in workflows:
            session = self._session_manager.get_session(workflow.get("session_id")) or {}
            try:
                metadata = json.loads(session.get("metadata") or "{}")
            except (TypeError, ValueError):
                metadata = {}
            if str(metadata.get("tenant_id", "default")) == str(tenant_id):
                filtered.append(workflow)
        return filtered

    def reconcile_workflow(
        self,
        workflow_id: str,
        observations: list[dict] | dict[int, dict],
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> dict:
        """Apply provider-verified observations to a durable workflow.

        No provider is contacted here.  Every observation must explicitly set
        ``verified=true`` so an untrusted status guess cannot mark a failed
        live write as successful.  Unknown outcomes remain recovery-required.
        """
        workflow = self.get_workflow(
            workflow_id, user_id=user_id, tenant_id=tenant_id
        )
        if not workflow:
            raise KeyError("workflow not found")
        if isinstance(observations, dict):
            entries = [dict(value, sequence=key) for key, value in observations.items()]
        else:
            entries = list(observations or [])
        if not entries:
            raise ValueError("reconciliation requires at least one observation")
        known_sequences = {
            int(item.get("sequence"))
            for item in workflow.get("items", [])
            if item.get("sequence") is not None
        }
        current_statuses = {
            int(item.get("sequence")): str(item.get("status"))
            for item in workflow.get("items", [])
            if item.get("sequence") is not None
        }
        allowed_item_transitions = {
            "failed": {"failed", "succeeded", "unknown"},
            "unknown": {"unknown", "succeeded", "failed"},
            "awaiting_confirmation": {"awaiting_confirmation", "succeeded", "failed", "unknown"},
            "running": {"running", "succeeded", "failed", "unknown"},
            "planned": {"planned", "awaiting_confirmation", "running", "succeeded", "failed", "unknown"},
            "succeeded": {"succeeded"},
            "unsupported": {"unsupported"},
            "skipped": {"skipped"},
        }
        seen_sequences: set[int] = set()
        for observation in entries:
            if not isinstance(observation, dict) or observation.get("verified") is not True:
                raise ValueError("each reconciliation observation must set verified=true")
            status = str(observation.get("status", "unknown"))
            if status not in {"succeeded", "failed", "unknown"}:
                raise ValueError("reconciliation status must be succeeded, failed or unknown")
            if observation.get("sequence") is None:
                raise ValueError("reconciliation observation requires sequence")
            try:
                sequence = int(observation["sequence"])
            except (TypeError, ValueError):
                raise ValueError("reconciliation sequence must be an integer")
            if sequence not in known_sequences:
                raise ValueError("reconciliation sequence does not belong to workflow")
            if sequence in seen_sequences:
                raise ValueError("reconciliation sequence must be unique")
            current_status = current_statuses[sequence]
            if status not in allowed_item_transitions.get(current_status, set()):
                raise ValueError(
                    f"cannot reconcile workflow item {sequence} from {current_status} to {status}"
                )
            seen_sequences.add(sequence)
        for observation in entries:
            sequence = int(observation["sequence"])
            status = str(observation.get("status", "unknown"))
            updated_item = self._session_manager.update_workflow_item(
                workflow_id,
                sequence,
                status,
                output_data=self._redact_for_persistence(observation.get("output_data")),
                error=self._redact_for_persistence(observation.get("error")),
            )
            if not updated_item:
                raise ValueError(f"workflow item {sequence} could not be updated")

        updated = self._session_manager.get_workflow(workflow_id)
        items = updated.get("items", []) if updated else []
        statuses = [str(item.get("status")) for item in items]
        succeeded = [item for item in items if item.get("status") == "succeeded"]
        failed = [item for item in items if item.get("status") == "failed"]
        if any(status == "unknown" for status in statuses):
            workflow_status = "recovery_required"
        elif failed and succeeded:
            self._session_manager.mark_workflow_items_for_compensation(
                workflow_id,
                [int(item["sequence"]) for item in succeeded],
            )
            workflow_status = "partially_failed"
        elif failed:
            workflow_status = "failed"
        elif statuses and all(status in {"succeeded", "unsupported"} for status in statuses):
            workflow_status = "succeeded"
        else:
            workflow_status = "recovery_required"
        self._session_manager.update_workflow(
            workflow_id,
            workflow_status,
            {
                "last_reconciled_by": str(user_id or "operator"),
                "reconciliation_verified": True,
            },
        )
        return self.get_workflow(
            workflow_id, user_id=user_id, tenant_id=tenant_id
        ) or {}

    def reconcile_workflow_from_provider(
        self,
        workflow_id: str,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        credentials: Optional[dict] = None,
        principal: Optional[RequestPrincipal] = None,
    ) -> dict:
        """Resolve pending items through provider-owned read-back adapters.

        This method never replays a write. A reconciler can only invoke a
        registered read tool through the Runtime, and its observation is
        applied by the same verified state-transition path as externally
        supplied observations.
        """
        if not self._session_manager:
            raise RuntimeError("provider reconciliation requires persistence")
        effective_user_id = principal.user_id if principal is not None else user_id
        effective_tenant_id = principal.tenant_id if principal is not None else tenant_id
        permissions = (
            principal.permissions if principal is not None else self._granted_permissions
        )
        permissions = frozenset(permissions or ())
        if "ads.reconcile" not in permissions and "ads.write" not in permissions:
            raise PermissionError("provider reconciliation requires ads.reconcile or ads.write")
        if "ads.read" not in permissions and "ads.write" not in permissions:
            raise PermissionError("provider reconciliation requires ads.read")

        workflow = self.get_workflow(
            workflow_id,
            user_id=effective_user_id,
            tenant_id=effective_tenant_id,
        )
        if not workflow:
            raise KeyError("workflow not found")
        if not self._session_manager.claim_workflow_recovery(
            workflow_id,
            self._workflow_lease_owner,
            self.workflow_stale_after_seconds,
            self.workflow_stale_after_seconds,
        ):
            raise RuntimeError("workflow is already being recovered or is still active")
        workflow = self.get_workflow(
            workflow_id,
            user_id=effective_user_id,
            tenant_id=effective_tenant_id,
        ) or workflow
        session_record = self._session_manager.get_session(workflow.get("session_id")) or {}
        request_clients = self._build_request_clients(credentials)
        account_scope = principal.account_scope if principal is not None else None
        observations: list[dict[str, Any]] = []
        pending_statuses = {
            "planned", "running", "awaiting_confirmation", "failed", "unknown",
        }

        for item in workflow.get("items", []):
            if str(item.get("status")) not in pending_statuses:
                continue
            platform = self._canonical_platform(item.get("platform") or "")
            input_data = item.get("input_data") if isinstance(item.get("input_data"), dict) else {}
            account_id = None
            for account_key in ("account_id", "advertiser_id", "customer_id"):
                if input_data.get(account_key):
                    account_id = str(input_data[account_key])
                    break
            account_id = account_id or str(session_record.get("account_id") or "")
            allowed, account_error = self._validate_account_with_principal(
                platform, account_id, False, account_scope
            )
            if not allowed:
                observations.append({
                    "sequence": item.get("sequence"),
                    "status": "unknown",
                    "verified": True,
                    "error": f"read-back account boundary rejected: {account_error}",
                    "source": "runtime_account_boundary",
                })
                continue

            reconciler = self._provider_reconcilers.get(platform) or ToolReadbackReconciler(platform)

            ctx = ToolContext(
                session_id=str(workflow.get("session_id") or ""),
                user_id=str(effective_user_id or session_record.get("user_id") or ""),
                account_id=account_id,
                credentials=self._freeze_credentials(credentials or {}),
                metadata={
                    "tenant_id": str(effective_tenant_id or "default"),
                    "reconciliation": True,
                },
            )

            def execute_read(read_tool: str, read_input: dict[str, Any]) -> ToolResult:
                definition, _handler = self._get_registered_tool(read_tool)
                if not definition.is_read_tool:
                    return ToolResult.error("reconciliation callback only permits read tools")
                permission_error = self._check_tool_permissions(definition, permissions)
                if permission_error:
                    return ToolResult.error(permission_error)
                return self.tool_executor.execute(
                    ctx, read_tool, read_input, request_clients
                )

            observation = reconciler.reconcile(
                ReconciliationContext(
                    workflow=workflow,
                    item=item,
                    tool_context=ctx,
                    execute_read=execute_read,
                    resolve_read_tool=self._resolve_readback_definition,
                    resolve_tool=lambda tool_name: self._get_registered_tool(tool_name)[0]
                    if tool_name else None,
                )
            )
            if not isinstance(observation, ReconciliationObservation):
                raise TypeError("ProviderReconciler must return ReconciliationObservation")
            if int(observation.sequence) != int(item.get("sequence")):
                raise ValueError("ProviderReconciler returned a mismatched workflow sequence")
            if not observation.verified:
                raise ValueError("ProviderReconciler must return verified observations")
            payload = dict(observation.output_data or {})
            payload["_reconciliation"] = {
                "source": observation.source,
                "observed_at": observation.observed_at,
                "provider_resource_id": observation.provider_resource_id,
            }
            observations.append({
                "sequence": observation.sequence,
                "status": observation.status,
                "verified": True,
                "output_data": payload,
                "error": observation.error,
                "source": observation.source,
            })

        if not observations:
            self._session_manager.release_workflow_lease(
                workflow_id, self._workflow_lease_owner
            )
            raise ValueError("workflow has no pending items eligible for provider reconciliation")
        reconciled = self.reconcile_workflow(
            workflow_id,
            observations,
            user_id=effective_user_id,
            tenant_id=effective_tenant_id,
        )
        self._session_manager.release_workflow_lease(
            workflow_id, self._workflow_lease_owner
        )
        return reconciled

    def cancel_workflow(
        self, workflow_id: str, user_id: str, tenant_id: Optional[str] = None
    ) -> bool:
        """Cancel a non-terminal workflow without contacting a provider."""
        workflow = self.get_workflow(
            workflow_id, user_id=user_id, tenant_id=tenant_id
        )
        if not workflow:
            return False
        return self._session_manager.update_workflow(
            workflow_id, "cancelled", {"cancelled_by": str(user_id)}
        )
