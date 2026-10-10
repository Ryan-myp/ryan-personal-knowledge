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

from agents.agent_harness.core.agent_profile import AgentProfile
from agents.agent_harness.core.conversation_title import ConversationTitleGenerator
from agents.tools.advertising.shared.features.factory import discover_features
from agents.agent_harness.core.interfaces import EffectReconciler, ExecutionMode
from agents.agent_harness.core.plugins import (
    PluginKind,
    PluginLoader,
    PluginManifest,
    PluginRegistry,
)
from agents.agent_harness.core.tool_registry import GuardedToolRegistry, SimpleToolRegistry
from agents.agent_harness.core.tool_selector import DynamicToolSelector
from agents.tools.advertising.shared.domain.blueprint import (
    BlueprintCascadeEngine,
    BlueprintRegistry,
)
from agents.tools.advertising.shared.domain.clarification import ActionClarificationBuilder
from agents.tools.advertising.shared.domain.creation_card import CreationCardBuilder
from agents.applications.advertising.knowledge.wiki import MarkdownWikiKnowledgeProvider
from agents.tools.advertising.shared.domain.parameter_catalog import ParameterCatalogRegistry
from agents.tools.advertising.shared.domain.parameter_selection import ParameterSelectionSigner
from agents.applications.advertising.knowledge.knowledge_management import ManagedKnowledgeProvider
from ..execution.account_policy import AccountWhitelistValidator
from .ad_application_assembly import AdApplicationAssembly
from .ad_application_components import AdApplicationAssemblyOptions
from ..run.ad_runtime_context import AdvertisingRuntimeContext
from ..run.ad_runtime_catalog import AdvertisingCatalogService
from ..run.ad_runtime_controls import AdvertisingRuntimeControls
from ..run.ad_runtime_lifecycle import AdvertisingLifecycleService
from ..run.ad_runtime_policy import AdvertisingRuntimePolicy
from ..run.ad_runtime_presentation import AdvertisingPresentationService
from ..run.ad_runtime_reconciliation import AdvertisingRuntimeReconciliation
from ..run.ad_run_service import AdvertisingRunService
from ..run.ad_runtime_scope import AdvertisingRuntimeScope
from ..integrations.provider_bindings import ProviderBindings
from agents.agent_harness.skills.contract import SkillLoader
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
        """Build the application in distinct runtime, policy and platform phases."""
        cls._initialize_runtime_services(runtime, options, mode_context)
        cls._initialize_runtime_policy(runtime, options)
        cls._initialize_runtime_components(
            runtime, options, mode_context, busy_error,
        )
        if bool(options.get("read_only_mode", False)):
            logger.info("只读模式已启用，仅允许查询操作")

    @staticmethod
    def _initialize_runtime_services(
        runtime: Any,
        options: Mapping[str, Any],
        mode_context: Any,
    ) -> None:
        AdApplicationBootstrap._initialize_agent_services(runtime, options)
        AdApplicationBootstrap._initialize_session_state(runtime)
        AdApplicationBootstrap._initialize_plugin_services(runtime, mode_context)
        AdApplicationBootstrap._initialize_features(runtime, options)
        AdApplicationBootstrap._initialize_skill_state(runtime)
        AdApplicationBootstrap._initialize_data_sources(runtime, options)
        AdApplicationBootstrap._initialize_catalog_services(runtime)
        AdApplicationBootstrap._initialize_creation_services(runtime)
        AdApplicationBootstrap._initialize_run_services(runtime, options)

    @staticmethod
    def _initialize_agent_services(
        runtime: Any,
        options: Mapping[str, Any],
    ) -> None:
        base_registry = options.get("registry") or SimpleToolRegistry()
        runtime.registry = (
            base_registry if isinstance(base_registry, GuardedToolRegistry)
            else GuardedToolRegistry(base_registry)
        )
        runtime._registry_execution_token = getattr(
            runtime.registry, "_execution_token", None,
        )
        runtime.provider_bindings = ProviderBindings()
        runtime.require_llm = bool(options.get("require_llm", True))
        runtime.auto_memory_capture_enabled = bool(
            options.get("auto_memory_capture_enabled", True)
        )
        for name in ("metrics", "trace_sink", "alert_sink",
                     "credential_provider", "quota_provider"):
            setattr(runtime, name, options.get(name))
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
        runtime.write_guard = options.get("write_guard")
        skill_roots = options.get("skill_roots")
        if skill_roots is None:
            skill_roots = [
                str(Path(__file__).resolve().parents[3] / "skills" / "advertising")
            ]
        runtime.skill_loader = SkillLoader(skill_roots)
        runtime.skill_loader.load_all()
        runtime._llm = options.get("llm_client")
        runtime.conversation_title_generator = ConversationTitleGenerator()
        runtime.conversation_title_use_llm = bool(
            options.get("conversation_title_use_llm", False)
        )

    @staticmethod
    def _initialize_session_state(runtime: Any) -> None:
        runtime._sessions = {}
        runtime._session_locks = {}
        runtime._session_locks_guard = threading.RLock()
        runtime._background_tasks = []
        runtime._skill_lifecycle_lock = threading.RLock()
        runtime._managed_skill_lock = threading.RLock()
        runtime._execution_mode_lock = threading.RLock()
        runtime._execution_mode_cache = OrderedDict()

    @staticmethod
    def _initialize_plugin_services(runtime: Any, mode_context: Any) -> None:
        runtime.plugin_registry = PluginRegistry()
        runtime.plugin_loader = PluginLoader(
            runtime.plugin_registry,
            allow_trusted_source=True,
        )
        for skill in runtime.skill_loader.list_all().values():
            skill_name = str(getattr(skill, "name", "") or "").strip()
            if not skill_name:
                continue
            manifest = PluginManifest(
                plugin_id=f"builtin:skill:{skill_name.lower()}",
                version=str(getattr(skill, "version", "1.0.0") or "1.0.0"),
                kinds=(PluginKind.SKILL.value,),
                display_name=skill_name,
                description=str(getattr(skill, "description", "") or ""),
                source="builtin",
                trusted=False,
                executable=False,
                metadata={
                    "namespace": str(getattr(skill, "namespace", "") or ""),
                    "advisory_only": True,
                },
            )
            runtime.plugin_loader.install(manifest, contribution=skill)
        runtime.controls_service = AdvertisingRuntimeControls(
            runtime, mode_context=mode_context,
        )
        runtime.lifecycle_service = AdvertisingLifecycleService(runtime)

    @staticmethod
    def _initialize_features(runtime: Any, options: Mapping[str, Any]) -> None:
        configured = options.get("features")
        runtime.features = list(
            discover_features() if configured is None else configured
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

    @staticmethod
    def _initialize_skill_state(runtime: Any) -> None:
        runtime._skill_objects = {}
        runtime._skill_keys_by_platform = {}
        runtime._skill_tool_names = {}
        runtime._skill_namespaces = {}
        runtime._skill_format_ids = {}
        runtime._managed_context_skills = {}
        runtime._skill_factories = {}
        runtime._credentials = {}

    @staticmethod
    def _initialize_data_sources(
        runtime: Any,
        options: Mapping[str, Any],
    ) -> None:
        knowledge_provider = options.get("knowledge_provider")
        persistence_store = options.get("persistence_store")
        base_provider = knowledge_provider or MarkdownWikiKnowledgeProvider(
            Path(__file__).resolve().parents[3]
            / "knowledge" / "advertising" / "wiki",
            search_index=persistence_store,
        )
        runtime.knowledge_provider = (
            ManagedKnowledgeProvider(base_provider, persistence_store)
            if knowledge_provider is None and persistence_store is not None
            else base_provider
        )
        runtime.tool_selector = options.get("tool_selector") or DynamicToolSelector(
            skill_loader=runtime.skill_loader,
            knowledge_source=runtime.knowledge_provider,
        )

    @staticmethod
    def _initialize_catalog_services(runtime: Any) -> None:
        runtime.parameter_catalogs = ParameterCatalogRegistry()
        runtime.catalog_service = AdvertisingCatalogService(runtime)
        runtime.presentation_service = AdvertisingPresentationService()
        runtime.scope_service = AdvertisingRuntimeScope(runtime)
        runtime.reconciliation_service = AdvertisingRuntimeReconciliation(runtime)

    @staticmethod
    def _initialize_creation_services(runtime: Any) -> None:
        runtime.creation_blueprints = BlueprintRegistry()
        runtime.blueprint_cascade = BlueprintCascadeEngine()
        runtime.creation_card_builder = CreationCardBuilder(
            runtime.creation_blueprints,
            runtime.registry,
            runtime.blueprint_cascade,
            account_provider=lambda provider, account_scope:
                runtime._available_accounts_for_request(provider, account_scope),
            template_provider=lambda provider, account_id, account_scope, tenant_id, user_id:
                runtime.list_creation_templates(
                    provider=provider,
                    account_id=account_id,
                    account_scope=account_scope,
                    tenant_id=tenant_id,
                    user_id=user_id,
                ),
        )
        runtime.action_clarification_builder = ActionClarificationBuilder(
            field_labeler=runtime._clarification_field_label,
            field_hint_builder=runtime._clarification_field_hint,
        )

    @staticmethod
    def _initialize_run_services(
        runtime: Any,
        options: Mapping[str, Any],
    ) -> None:
        runtime.runtime_context = AdvertisingRuntimeContext(runtime)
        runtime.run_service = AdvertisingRunService(runtime)
        runtime.ad_format_catalogs = {}
        runtime.provider_version_contracts = {}
        runtime.provider_api_surfaces = {}
        selection_secret = options.get("selection_token_secret") or os.environ.get(
            "AD_AGENT_SELECTION_TOKEN_KEY"
        )
        runtime._parameter_selection_signer = ParameterSelectionSigner(
            selection_secret,
            int(options.get("parameter_selection_ttl_seconds", 600)),
        )
        runtime.policy_engine = ToolExecutionPolicy()
        runtime.policies = list(options.get("policies") or [])
        if runtime.policies:
            runtime.tool_selector.set_policies(runtime.policies)

    @staticmethod
    def _initialize_runtime_policy(
        runtime: Any,
        options: Mapping[str, Any],
    ) -> None:
        AdApplicationBootstrap._initialize_execution_policy(runtime, options)
        AdApplicationBootstrap._initialize_runtime_limits(runtime, options)
        AdApplicationBootstrap._initialize_provider_reconciliation(runtime, options)
        runtime.whitelist_validator = (
            options.get("whitelist_validator") or AccountWhitelistValidator()
        )
        runtime._read_only_mode = bool(options.get("read_only_mode", False))
        runtime.runtime_policy = AdvertisingRuntimePolicy(runtime)

    @staticmethod
    def _initialize_execution_policy(
        runtime: Any,
        options: Mapping[str, Any],
    ) -> None:
        runtime._execution_mode = runtime._validate_execution_mode(
            options.get("execution_mode", ExecutionMode.DRY_RUN.value)
        )
        runtime._live_approved_tools = set(
            options.get("live_approved_tools") or set()
        )
        runtime.allow_live_writes = bool(options.get("allow_live_writes", False))
        runtime.enforce_account_scope = bool(
            options.get("enforce_account_scope", True)
        )
        runtime.offline_mode = bool(options.get("offline_mode", False))
        defaults = {"ads.read", "ads.plan", "memory.read", "memory.write"}
        permissions = options.get("granted_permissions")
        runtime._granted_permissions = frozenset(
            str(permission)
            for permission in (defaults if permissions is None else permissions)
        )

    @staticmethod
    def _initialize_runtime_limits(
        runtime: Any,
        options: Mapping[str, Any],
    ) -> None:
        max_tool_calls = int(options.get("max_tool_calls", 32))
        turn_timeout = float(options.get("turn_timeout_seconds", 120.0))
        if max_tool_calls <= 0:
            raise ValueError("max_tool_calls must be positive")
        if turn_timeout <= 0:
            raise ValueError("turn_timeout_seconds must be positive")
        runtime.max_tool_calls = max_tool_calls
        runtime.turn_timeout_seconds = turn_timeout
        runtime.max_user_input_chars = int(
            options.get("max_user_input_chars", 12_000)
        )
        runtime.max_platform_params_bytes = int(
            options.get("max_platform_params_bytes", 256_000)
        )
        stale_after = float(options.get("workflow_stale_after_seconds", 300.0))
        lease_seconds = float(options.get("session_lease_seconds", 300.0))
        if stale_after <= 0:
            raise ValueError("workflow_stale_after_seconds must be positive")
        if lease_seconds <= 0:
            raise ValueError("session_lease_seconds must be positive")
        runtime.workflow_stale_after_seconds = stale_after
        runtime._workflow_lease_owner = f"runtime:{os.getpid()}:{uuid.uuid4().hex}"
        runtime.session_lease_seconds = lease_seconds
        runtime._session_lease_owner = f"session:{os.getpid()}:{uuid.uuid4().hex}"

    @staticmethod
    def _initialize_provider_reconciliation(
        runtime: Any,
        options: Mapping[str, Any],
    ) -> None:
        runtime._effect_reconcilers = {}
        for platform, reconciler in (
            options.get("effect_reconcilers") or {}
        ).items():
            if not isinstance(reconciler, EffectReconciler):
                raise TypeError("provider reconciler must implement EffectReconciler")
            runtime._effect_reconcilers[
                runtime._canonical_platform(platform)
            ] = reconciler

    @staticmethod
    def _initialize_runtime_components(
        runtime: Any,
        options: Mapping[str, Any],
        mode_context: Any,
        busy_error: type[Exception],
    ) -> None:
        components = AdApplicationAssembly.compose(
            runtime,
            AdApplicationAssemblyOptions(
                persistence_store=options.get("persistence_store"),
                outbox_delivery=options.get("outbox_delivery"),
                outbox_poll_interval=float(options.get("outbox_poll_interval", 0.25)),
                outbox_max_attempts=int(options.get("outbox_max_attempts", 10)),
                max_task_workers=int(options.get("max_task_workers", 4)),
                max_task_queue=int(options.get("max_task_queue", 32)),
                task_timeout_seconds=float(options.get("task_timeout_seconds", 900.0)),
                task_lease_seconds=float(options.get("task_lease_seconds", 300.0)),
                task_queue_poll_interval=float(
                    options.get("task_queue_poll_interval", 0.5)
                ),
                start_background_workers=bool(
                    options.get("start_background_workers", True)
                ),
            ),
            mode_context=mode_context,
            busy_error=busy_error,
        )
        components.install(runtime)
__all__ = ["AdApplicationBootstrap"]
