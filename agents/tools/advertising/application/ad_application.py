"""
runtime/ad_application.py - Advertising application composition root

广告应用组合根。通用 Run/Turn 生命周期由
``agents.agent_harness.AgentRuntime`` 提供；这里仅组装广告场景的
Skills、Tools、策略、持久化和管理服务。
"""

from __future__ import annotations

import threading
from typing import Any, Callable, Iterable, Mapping, Optional

from agents.agent_harness import (
    AlertSink,
    CredentialProvider,
    MetricsSink,
    QuotaProvider,
    TraceSink,
)

from agents.agent_harness.core.features import RuntimeFeature
from agents.agent_harness.core.interfaces import (
    EffectReconciler,
    ExecutionMode,
    IntentParser,
    IntentRouter,
    ToolRegistry,
    WriteGuard,
)
from agents.agent_harness.core.policy import RuntimePolicy
from agents.agent_harness.core.tool_selector import DynamicToolSelector
from agents.agent_platform.data.knowledge.wiki import KnowledgeProvider
from agents.tools.advertising.shared.domain.security import PROTECTED_INPUT_FIELDS
from agents.agent_platform.data.persistence.interfaces import PersistenceBackend
from .account_policy import AccountWhitelistValidator
from .ad_application_contracts import (
    SessionBusyError,
    execution_mode_context,
)
from .ad_application_facade import AdApplicationFacadeMixin
from .ad_application_hooks import AdApplicationHooksMixin
from .ad_creation_services import AdCreationServicesMixin
from .ad_tool_source_services import AdToolSourceLifecycleMixin
from .ad_runtime_facades import (
    AdConversationRuntimeFacade,
    AdSessionRuntimeFacade,
    AdTaskRuntimeFacade,
    AdWorkflowRuntimeFacade,
)
from .session_context import SessionContext


class AdvertisingComposition(
    AdApplicationFacadeMixin,
    AdApplicationHooksMixin,
    AdToolSourceLifecycleMixin,
    AdCreationServicesMixin,
    AdTaskRuntimeFacade,
    AdConversationRuntimeFacade,
    AdSessionRuntimeFacade,
    AdWorkflowRuntimeFacade,
):
    """Advertising Skills + Tools composition over the generic Agent Runtime."""

    PROTECTED_INPUT_FIELDS = PROTECTED_INPUT_FIELDS

    def __init__(
        self,
        registry: ToolRegistry = None,
        intent_parser: IntentParser = None,
        intent_router: IntentRouter = None,
        write_guard: WriteGuard = None,
        skill_roots: list[str] = None,
        llm_client=None,
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
        trace_sink: Optional[TraceSink] = None,
        alert_sink: Optional[AlertSink] = None,
        credential_provider: Optional[CredentialProvider] = None,
        quota_provider: Optional[QuotaProvider] = None,
    ):
        from .ad_application_bootstrap import AdApplicationBootstrap

        AdApplicationBootstrap.initialize(
            self,
            locals(),
            mode_context=execution_mode_context,
            busy_error=SessionBusyError,
        )


__all__ = [
    "AdvertisingComposition",
    "AccountWhitelistValidator",
    "SessionBusyError",
    "SessionContext",
]
