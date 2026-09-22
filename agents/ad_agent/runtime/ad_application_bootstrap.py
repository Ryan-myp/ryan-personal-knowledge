"""Bootstrap the advertising application over the generic Agent Platform.

The public ``AdvertisingComposition`` remains the advertising boundary, but
its constructor should not also be the dependency-injection container.  This
module owns startup wiring only.  It does not implement a second run loop,
tool policy, provider router, or execution gate.
"""

from __future__ import annotations

import logging
import os
import threading
import uuid
from collections import OrderedDict
from pathlib import Path
from typing import Any, Mapping

from agents.agent_harness import MetricsSink

from ..core.agent_profile import AgentProfile
from ..core.conversation_title import ConversationTitleGenerator
from ..core.features import RuntimeFeature
from ..features.factory import discover_features, discover_response_renderer
from ..core.intent import LLMIntentParser, SimpleIntentRouter
from ..core.interfaces import EffectReconciler, ExecutionMode
from ..core.plugins import PluginKind, PluginLoader, PluginRegistry
from ..core.policy import RuntimePolicy
from ..core.response import ResponseRenderer, ResponseSynthesizer
from ..core.tool_registry import GuardedToolRegistry, SimpleToolRegistry
from ..core.tool_selector import DynamicToolSelector
from ..domain.ad.blueprint import BlueprintCascadeEngine, BlueprintRegistry
from ..domain.ad.clarification import ActionClarificationBuilder
from ..domain.ad.creation_card import CreationCardBuilder
from ..domain.ad.knowledge import MarkdownWikiKnowledgeProvider
from ..domain.ad.parameter_catalog import ParameterCatalogRegistry
from ..domain.ad.parameter_selection import ParameterSelectionSigner
from ..domain.ad.response import LLMResponseSynthesizer
from ..knowledge_management import ManagedKnowledgeProvider
from ..persistence.interfaces import PersistenceBackend
from .account_policy import AccountWhitelistValidator
from .ad_application_assembly import (
    AdApplicationAssembly,
    AdApplicationAssemblyOptions,
)
from .ad_runtime_context import AdvertisingRuntimeContext
from .ad_runtime_catalog import AdvertisingCatalogService
from .ad_runtime_controls import AdvertisingRuntimeControls
from .ad_runtime_lifecycle import AdvertisingLifecycleService
from .ad_runtime_policy import AdvertisingRuntimePolicy
from .ad_runtime_presentation import AdvertisingPresentationService
from .ad_runtime_reconciliation import AdvertisingRuntimeReconciliation
from .ad_run_service import AdvertisingRunService
from .ad_runtime_scope import AdvertisingRuntimeScope
from .provider_bindings import ProviderBindings
from .skill import Skill
from .skill import SkillLoader
from agents.agent_platform.tools.policy import ToolExecutionPolicy

logger = logging.getLogger(__name__)


class AdApplicationBootstrap:
    """Build the advertising composition graph in explicit startup phases."""

    @classmethod
    def initialize(
        cls,
        runtime: Any,
        options: Mapping[str, Any],
        *,
        mode_context: Any,
        busy_error: type[Exception],
    ) -> None:
        """Initialize ``runtime`` from constructor options.

        ``options`` is deliberately the constructor's local mapping.  Keeping
        the public constructor signature on the facade preserves a clear
        application API while moving the dependency graph into one testable
        bootstrap boundary.
        """
        registry = options.get("registry")
        intent_parser = options.get("intent_parser")
        intent_router = options.get("intent_router")
        write_guard = options.get("write_guard")
        skill_roots = options.get("skill_roots")
        llm_client = options.get("llm_client")
        require_llm = bool(options.get("require_llm", True))
        persistence_store = options.get("persistence_store")
        whitelist_validator = options.get("whitelist_validator")
        read_only_mode = bool(options.get("read_only_mode", False))
        execution_mode = options.get(
            "execution_mode", ExecutionMode.DRY_RUN.value
        )
        enforce_account_scope = bool(options.get("enforce_account_scope", True))
        live_approved_tools = options.get("live_approved_tools")
        allow_live_writes = bool(options.get("allow_live_writes", False))
        policies = options.get("policies")
        tool_selector = options.get("tool_selector")
        knowledge_provider = options.get("knowledge_provider")
        offline_mode = bool(options.get("offline_mode", False))
        granted_permissions = options.get("granted_permissions")
        max_tool_calls = int(options.get("max_tool_calls", 32))
        turn_timeout_seconds = float(
            options.get("turn_timeout_seconds", 120.0)
        )
        max_user_input_chars = int(
            options.get("max_user_input_chars", 12_000)
        )
        max_platform_params_bytes = int(
            options.get("max_platform_params_bytes", 256_000)
        )
        effect_reconcilers = options.get("effect_reconcilers")
        features = options.get("features")
        response_renderer = options.get("response_renderer")
        response_synthesizer = options.get("response_synthesizer")
        workflow_stale_after_seconds = float(
            options.get("workflow_stale_after_seconds", 300.0)
        )
        selection_token_secret = options.get("selection_token_secret")
        parameter_selection_ttl_seconds = int(
            options.get("parameter_selection_ttl_seconds", 600)
        )
        session_lease_seconds = float(
            options.get("session_lease_seconds", 300.0)
        )
        conversation_title_use_llm = bool(
            options.get("conversation_title_use_llm", False)
        )
        auto_memory_capture_enabled = bool(
            options.get("auto_memory_capture_enabled", True)
        )
        metrics = options.get("metrics")

        cls._initialize_runtime_services(
            runtime,
            registry=registry,
            intent_parser=intent_parser,
            intent_router=intent_router,
            write_guard=write_guard,
            skill_roots=skill_roots,
            llm_client=llm_client,
            require_llm=require_llm,
            persistence_store=persistence_store,
            features=features,
            response_renderer=response_renderer,
            response_synthesizer=response_synthesizer,
            tool_selector=tool_selector,
            knowledge_provider=knowledge_provider,
            policies=policies,
            selection_token_secret=selection_token_secret,
            parameter_selection_ttl_seconds=parameter_selection_ttl_seconds,
            conversation_title_use_llm=conversation_title_use_llm,
            auto_memory_capture_enabled=auto_memory_capture_enabled,
            metrics=metrics,
            mode_context=mode_context,
        )
        cls._initialize_runtime_policy(
            runtime,
            execution_mode=execution_mode,
            live_approved_tools=live_approved_tools,
            allow_live_writes=allow_live_writes,
            enforce_account_scope=enforce_account_scope,
            offline_mode=offline_mode,
            granted_permissions=granted_permissions,
            max_tool_calls=max_tool_calls,
            turn_timeout_seconds=turn_timeout_seconds,
            max_user_input_chars=max_user_input_chars,
            max_platform_params_bytes=max_platform_params_bytes,
            workflow_stale_after_seconds=workflow_stale_after_seconds,
            effect_reconcilers=effect_reconcilers,
            whitelist_validator=whitelist_validator,
            read_only_mode=read_only_mode,
            session_lease_seconds=session_lease_seconds,
        )
        cls._initialize_runtime_components(
            runtime,
            persistence_store=persistence_store,
            write_guard=write_guard,
            mode_context=mode_context,
            busy_error=busy_error,
            outbox_delivery=options.get("outbox_delivery"),
            outbox_poll_interval=float(
                options.get("outbox_poll_interval", 0.25)
            ),
            outbox_max_attempts=int(options.get("outbox_max_attempts", 10)),
            max_task_workers=int(options.get("max_task_workers", 4)),
            max_task_queue=int(options.get("max_task_queue", 32)),
            task_timeout_seconds=float(
                options.get("task_timeout_seconds", 900.0)
            ),
            task_lease_seconds=float(
                options.get("task_lease_seconds", 300.0)
            ),
            task_queue_poll_interval=float(
                options.get("task_queue_poll_interval", 0.5)
            ),
            start_background_workers=bool(
                options.get("start_background_workers", True)
            ),
        )
        if read_only_mode:
            logger.info("只读模式已启用，仅允许查询操作")

    @staticmethod
    def _initialize_runtime_services(
        runtime: Any,
        *,
        registry: Any,
        intent_parser: Any,
        intent_router: Any,
        write_guard: Any,
        skill_roots: Any,
        llm_client: Any,
        require_llm: bool,
        persistence_store: Any,
        features: Any,
        response_renderer: Any,
        response_synthesizer: Any,
        tool_selector: Any,
        knowledge_provider: Any,
        policies: Any,
        selection_token_secret: Any,
        parameter_selection_ttl_seconds: int,
        conversation_title_use_llm: bool,
        auto_memory_capture_enabled: bool,
        metrics: MetricsSink | None,
        mode_context: Any,
    ) -> None:
        base_registry = registry or SimpleToolRegistry()
        runtime.registry = (
            base_registry
            if isinstance(base_registry, GuardedToolRegistry)
            else GuardedToolRegistry(base_registry)
        )
        runtime._registry_execution_token = getattr(
            runtime.registry, "_execution_token", None
        )
        runtime.provider_bindings = ProviderBindings()
        runtime.require_llm = require_llm
        runtime.auto_memory_capture_enabled = auto_memory_capture_enabled
        runtime.metrics = metrics
        runtime.agent_profile = AgentProfile(
            name="ad-agent",
            role="广告投放与分析助手",
            domain_guidance=(
                "广告业务知识只来自当前注册的 Skills、Tools、Blueprints "
                "和受控知识源。"
            ),
            response_guidance=(
                "面向广告运营人员回答，必须区分预览、已执行、失败和状态未知。"
            ),
            structured_fields=(
                "仅使用当前注册的 Skill、Tool、Tool Source 和 Blueprint 契约中声明的字段；"
                "缺少必填信息时先澄清，不从业务常识猜测"
            ),
        )
        runtime.intent_parser = intent_parser or LLMIntentParser(
            llm_client,
            allow_rule_fallback=not require_llm,
            profile=runtime.agent_profile,
        )
        if require_llm and isinstance(runtime.intent_parser, LLMIntentParser):
            runtime.intent_parser.allow_rule_fallback = False
        runtime.intent_router = intent_router or SimpleIntentRouter()
        runtime.write_guard = write_guard
        runtime.skill_loader = SkillLoader(skill_roots)
        runtime.skill_loader.load_all()
        for skill in runtime.skill_loader.list_all().values():
            register_aliases = getattr(
                runtime.intent_parser, "register_namespace_aliases", None
            )
            if callable(register_aliases):
                register_aliases(
                    skill.namespace, skill.namespace_aliases or []
                )
        runtime._llm = llm_client
        runtime.conversation_title_generator = ConversationTitleGenerator()
        runtime.conversation_title_use_llm = conversation_title_use_llm
        if runtime._llm is None:
            model_client = getattr(runtime.intent_parser, "model_client", None)
            if callable(model_client):
                runtime._llm = model_client()
        runtime._sessions = {}
        runtime._session_locks = {}
        runtime._session_locks_guard = threading.RLock()
        runtime._background_tasks = []
        runtime.plugin_registry = PluginRegistry()
        runtime.plugin_loader = PluginLoader(
            runtime.plugin_registry,
            allow_trusted_source=True,
        )
        runtime.controls_service = AdvertisingRuntimeControls(
            runtime,
            mode_context=mode_context,
        )
        runtime.lifecycle_service = AdvertisingLifecycleService(runtime)
        runtime.features = list(
            discover_features()
            if features is None else features
        )
        for feature in runtime.features:
            feature_name = str(
                getattr(feature, "feature_name", "") or ""
            ).strip()
            if feature_name:
                runtime._register_builtin_plugin(
                    f"feature:{feature_name}",
                    feature,
                    (PluginKind.FEATURE.value,),
                    description=f"Runtime feature {feature_name}",
                )
            register_descriptors = getattr(
                runtime.intent_parser,
                "register_intent_descriptors",
                None,
            )
            if callable(register_descriptors):
                register_descriptors(feature.intent_descriptors())
        runtime.response_renderer = response_renderer or discover_response_renderer()
        if runtime.response_renderer is None:
            raise RuntimeError("no response renderer is registered")
        runtime.response_synthesizer = (
            response_synthesizer
            if response_synthesizer is not None
            else (
                LLMResponseSynthesizer(profile=runtime.agent_profile)
                if runtime._llm is not None else None
            )
        )
        renderer_name = str(
            getattr(runtime.response_renderer, "renderer_name", "") or ""
        ).strip()
        if renderer_name:
            runtime._register_builtin_plugin(
                f"renderer:{renderer_name}",
                runtime.response_renderer,
                (PluginKind.RENDERER.value,),
                description=f"Response renderer {renderer_name}",
            )
        runtime._skill_objects = {}
        runtime._skill_keys_by_platform = {}
        runtime._skill_tool_names = {}
        runtime._skill_namespaces = {}
        runtime._skill_format_ids = {}
        runtime._skill_lifecycle_lock = threading.RLock()
        runtime._managed_context_skills = {}
        runtime._managed_skill_lock = threading.RLock()
        runtime._skill_factories = {}
        runtime._credentials = {}
        runtime._execution_mode_lock = threading.RLock()
        runtime._execution_mode_cache = OrderedDict()
        base_knowledge_provider = knowledge_provider or MarkdownWikiKnowledgeProvider(
            Path(__file__).resolve().parent.parent / "knowledge_base",
            search_index=persistence_store,
        )
        runtime.knowledge_provider = (
            ManagedKnowledgeProvider(base_knowledge_provider, persistence_store)
            if knowledge_provider is None and persistence_store is not None
            else base_knowledge_provider
        )
        runtime.tool_selector = tool_selector or DynamicToolSelector(
            skill_loader=runtime.skill_loader,
            knowledge_source=runtime.knowledge_provider,
        )
        runtime.parameter_catalogs = ParameterCatalogRegistry()
        runtime.catalog_service = AdvertisingCatalogService(runtime)
        runtime.presentation_service = AdvertisingPresentationService(runtime)
        runtime.scope_service = AdvertisingRuntimeScope(runtime)
        runtime.reconciliation_service = AdvertisingRuntimeReconciliation(runtime)
        runtime.creation_blueprints = BlueprintRegistry()
        runtime.blueprint_cascade = BlueprintCascadeEngine()
        runtime.creation_card_builder = CreationCardBuilder(
            runtime.creation_blueprints,
            runtime.registry,
            runtime.blueprint_cascade,
        )
        runtime.action_clarification_builder = ActionClarificationBuilder(
            field_labeler=runtime._clarification_field_label,
            field_hint_builder=runtime._clarification_field_hint,
        )
        runtime.runtime_context = AdvertisingRuntimeContext(runtime)
        runtime.run_service = AdvertisingRunService(runtime)
        runtime.ad_format_catalogs = {}
        runtime.provider_version_contracts = {}
        runtime.provider_api_surfaces = {}
        selection_secret = selection_token_secret or os.environ.get(
            "AD_AGENT_SELECTION_TOKEN_KEY"
        )
        runtime._parameter_selection_signer = ParameterSelectionSigner(
            selection_secret, parameter_selection_ttl_seconds
        )
        runtime.policy_engine = ToolExecutionPolicy()
        runtime.policies = list(policies or [])
        if runtime.policies:
            runtime.tool_selector.set_policies(runtime.policies)

    @staticmethod
    def _initialize_runtime_policy(
        runtime: Any,
        *,
        execution_mode: str,
        live_approved_tools: Any,
        allow_live_writes: bool,
        enforce_account_scope: bool,
        offline_mode: bool,
        granted_permissions: Any,
        max_tool_calls: int,
        turn_timeout_seconds: float,
        max_user_input_chars: int,
        max_platform_params_bytes: int,
        workflow_stale_after_seconds: float,
        effect_reconcilers: Any,
        whitelist_validator: Any,
        read_only_mode: bool,
        session_lease_seconds: float,
    ) -> None:
        runtime._execution_mode = runtime._validate_execution_mode(
            execution_mode
        )
        runtime._live_approved_tools = set(live_approved_tools or set())
        runtime.allow_live_writes = allow_live_writes
        runtime.enforce_account_scope = enforce_account_scope
        runtime.offline_mode = offline_mode
        default_permissions = {
            "ads.read", "ads.plan", "memory.read", "memory.write"
        }
        runtime._granted_permissions = frozenset(
            str(permission)
            for permission in (
                default_permissions
                if granted_permissions is None else granted_permissions
            )
        )
        if max_tool_calls <= 0:
            raise ValueError("max_tool_calls must be positive")
        if turn_timeout_seconds <= 0:
            raise ValueError("turn_timeout_seconds must be positive")
        runtime.max_tool_calls = max_tool_calls
        runtime.turn_timeout_seconds = turn_timeout_seconds
        runtime.max_user_input_chars = max_user_input_chars
        runtime.max_platform_params_bytes = max_platform_params_bytes
        if workflow_stale_after_seconds <= 0:
            raise ValueError("workflow_stale_after_seconds must be positive")
        runtime.workflow_stale_after_seconds = workflow_stale_after_seconds
        runtime._workflow_lease_owner = (
            f"runtime:{os.getpid()}:{uuid.uuid4().hex}"
        )
        if session_lease_seconds <= 0:
            raise ValueError("session_lease_seconds must be positive")
        runtime.session_lease_seconds = session_lease_seconds
        runtime._session_lease_owner = (
            f"session:{os.getpid()}:{uuid.uuid4().hex}"
        )
        runtime._effect_reconcilers = {}
        for platform, reconciler in (effect_reconcilers or {}).items():
            if not isinstance(reconciler, EffectReconciler):
                raise TypeError("provider reconciler must implement EffectReconciler")
            runtime._effect_reconcilers[
                runtime._canonical_platform(platform)
            ] = reconciler
        runtime.whitelist_validator = (
            whitelist_validator or AccountWhitelistValidator()
        )
        runtime._read_only_mode = read_only_mode
        # Keep application policy replaceable and outside the Run facade. The
        # policy object delegates to the generic ToolExecutionPolicy for
        # generic gates, while owning only advertising account/resource rules.
        runtime.runtime_policy = AdvertisingRuntimePolicy(runtime)

    @staticmethod
    def _initialize_runtime_components(
        runtime: Any,
        *,
        persistence_store: PersistenceBackend | None,
        write_guard: Any,
        mode_context: ContextManager[Any] | Any,
        busy_error: type[Exception],
        outbox_delivery: Any,
        outbox_poll_interval: float,
        outbox_max_attempts: int,
        max_task_workers: int,
        max_task_queue: int,
        task_timeout_seconds: float,
        task_lease_seconds: float,
        task_queue_poll_interval: float,
        start_background_workers: bool,
    ) -> None:
        components = AdApplicationAssembly.compose(
            runtime,
            AdApplicationAssemblyOptions(
                persistence_store=persistence_store,
                outbox_delivery=outbox_delivery,
                outbox_poll_interval=outbox_poll_interval,
                outbox_max_attempts=outbox_max_attempts,
                max_task_workers=max_task_workers,
                max_task_queue=max_task_queue,
                task_timeout_seconds=task_timeout_seconds,
                task_lease_seconds=task_lease_seconds,
                task_queue_poll_interval=task_queue_poll_interval,
                start_background_workers=start_background_workers,
            ),
            mode_context=mode_context,
            busy_error=busy_error,
        )
        components.install(runtime)


__all__ = ["AdApplicationBootstrap"]
