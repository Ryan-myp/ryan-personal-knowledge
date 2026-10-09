"""Composition of the advertising application's Runtime dependencies.

``AdvertisingComposition`` is the public application facade, not the place where
every infrastructure object should be constructed.  This module owns the
application composition graph and returns explicit components to the facade.

The assembly is the advertising scenario's composition root. It contributes
Skills, Tools, data adapters and lifecycle resources to the generic Runtime;
the Harness owns the only Run/Session/Turn entry point.
"""

from __future__ import annotations

import logging
from contextvars import ContextVar
from typing import Any, Callable, Mapping, Optional

from agents.agent_harness import (
    InMemorySkillCatalog,
    RuntimePorts,
    TurnRequest,
)
from agents.agent_harness.core.tool_selection import ToolSelector
from agents.agent_platform import (
    AgentPlatform,
    PlatformDependencies,
)
from agents.agent_platform.runtime import DataLayer, InfrastructureLayer, IntegrationLayer
from agents.agent_harness.core.memory import MemoryManager
from agents.scenarios.advertising import (
    advertising_agent_definition,
    advertising_scenario_definition,
)
from agents.agent_platform.governance.identity.principal import RequestPrincipal
from agents.tools.advertising.shared.domain.security import ACCOUNT_SCOPE_FIELDS
from agents.agent_platform.data.persistence.models import ScheduledTaskRecord
from agents.agent_platform.data.persistence.session_manager import SessionManager
from agents.agent_platform.data.persistence.adapters import (
    PersistenceTranscriptStore,
)
from .account_context import AccountResolver
from .ad_conversation_services import AdConversationServices
from .ad_persistence_services import AdPersistenceServices
from .ad_session_services import AdSessionServices
from .ad_task_services import AdTaskServices
from .integration import (
    AdvertisingContextProvider,
    AdvertisingToolCatalog,
)
from .ad_tool_policy_factory import AdvertisingToolPolicyFactory
from .ad_workflow_services import AdWorkflowServices
from .input_builder import ToolInputBuilder
from agents.agent_platform.infrastructure.durable import OutboxPublisher
from .scheduling_service import SchedulingService
from .security import RuntimeSecurity
from .services import AdRuntimeServices
from agents.agent_platform.infrastructure.durable import RuntimeSupervisor
from .tool_executor import ToolExecutor
from .workflow import WorkflowCoordinator
from .ad_application_components import (
    AdApplicationAssemblyOptions,
    AdApplicationComponents,
    AdApplicationServiceGraph,
    AdRunStoreAdapter,
)

logger = logging.getLogger(__name__)


class AdApplicationAssembly:
    """Build the advertising application graph over generic runtime ports."""

    @classmethod
    def compose(
        cls,
        runtime: Any,
        options: AdApplicationAssemblyOptions,
        *,
        mode_context: ContextVar[Optional[str]],
        busy_error: type[Exception],
    ) -> AdApplicationComponents:
        store = options.persistence_store
        session_manager, memory_manager = cls._create_session_manager(runtime, store)
        outbox = OutboxPublisher(session_manager) if session_manager else None
        services = cls._build_service_graph(
            runtime, store, session_manager, outbox,
        )
        ports = cls._build_runtime_ports(
            runtime, session_manager, mode_context, busy_error,
        )
        supervisor = cls._build_supervisor(runtime, options, store)
        platform_application = cls._build_platform_application(
            runtime, options, services, session_manager, memory_manager, ports,
            supervisor,
        )
        return AdApplicationComponents(
            persistence_store=store,
            session_manager=session_manager,
            memory_manager=memory_manager,
            outbox=services.outbox,
            services=services.services,
            input_builder=services.input_builder,
            account_resolver=services.account_resolver,
            workflow=services.workflow,
            security=services.security,
            scheduling_service=services.scheduling_service,
            persistence_services=services.persistence_services,
            conversation_services=services.conversation_services,
            session_services=services.session_services,
            workflow_services=services.workflow_services,
            task_services=services.task_services,
            runtime_kernel=platform_application.runtime,
            platform_application=platform_application,
            tool_executor=services.tool_executor,
            supervisor=supervisor,
            start_background_workers=options.start_background_workers,
        )

    @staticmethod
    def _create_session_manager(
        runtime: Any,
        store: Any,
    ) -> tuple[Optional[SessionManager], Optional[MemoryManager]]:
        if store is None:
            return None, None
        session_manager = SessionManager(store)
        recover_runs = getattr(session_manager, "recover_stale_execution_runs", None)
        if callable(recover_runs):
            recovered_runs = recover_runs(runtime.workflow_stale_after_seconds)
            if recovered_runs:
                logger.warning(
                    "marked %s stale Agent runs for recovery", recovered_runs,
                )
        memory_manager = None
        memory_methods = ("save_memory", "search_memories", "delete_memory")
        if all(callable(getattr(store, method, None)) for method in memory_methods):
            memory_manager = session_manager.memory_manager
            memory_manager.set_auto_capture_enabled(
                bool(getattr(runtime, "auto_memory_capture_enabled", True))
            )
        if runtime.write_guard and hasattr(runtime.write_guard, "bind_store"):
            runtime.write_guard.bind_store(store)
        return session_manager, memory_manager

    @staticmethod
    def _build_service_graph(
        runtime: Any,
        store: Any,
        session_manager: Optional[SessionManager],
        outbox: Optional[OutboxPublisher],
    ) -> AdApplicationServiceGraph:
        services = AdRuntimeServices(runtime)
        input_builder = ToolInputBuilder(
            services,
            scope_field_names=ACCOUNT_SCOPE_FIELDS,
            scope_value_resolver=lambda context: getattr(context, "account_id", None),
        )
        account_resolver = AccountResolver(services)
        workflow = WorkflowCoordinator(
            services,
            outbox=outbox,
            item_scope_resolver=runtime._resolve_workflow_item_scope,
            result_scope_resolver=runtime._resolve_workflow_result_scope,
        )
        security = RuntimeSecurity(runtime)
        scheduling_service = AdApplicationAssembly._build_scheduling_service(
            runtime, store, security,
        )
        services.bind_scheduling(scheduling_service)
        return AdApplicationServiceGraph(
            outbox=outbox,
            services=services,
            input_builder=input_builder,
            account_resolver=account_resolver,
            workflow=workflow,
            security=security,
            scheduling_service=scheduling_service,
            persistence_services=AdPersistenceServices(runtime),
            conversation_services=AdConversationServices(runtime),
            session_services=AdSessionServices(runtime),
            workflow_services=AdWorkflowServices(runtime),
            task_services=AdTaskServices(runtime),
            run_store=(
                AdRunStoreAdapter(session_manager, runtime)
                if session_manager is not None else None
            ),
            tool_policy=AdvertisingToolPolicyFactory(runtime).build(store),
            tool_executor=ToolExecutor(services),
        )

    @staticmethod
    def _build_scheduling_service(
        runtime: Any,
        store: Any,
        security: RuntimeSecurity,
    ) -> SchedulingService:
        return SchedulingService(
            store=store,
            submit_task=runtime.submit_task,
            redact=runtime._redact_for_persistence,
            validate_input=security.validate_input_redline,
            max_prompt_chars=runtime.max_user_input_chars,
            schedule_record_factory=ScheduledTaskRecord,
            task_kind="agent.turn",
            principal_from_metadata=lambda claims: RequestPrincipal.from_claims(claims),
            default_principal=lambda user, tenant: RequestPrincipal(
                user_id=user,
                tenant_id=tenant,
                permissions=runtime._granted_permissions,
            ),
        )

    @staticmethod
    def _build_runtime_ports(
        runtime: Any,
        session_manager: Optional[SessionManager],
        mode_context: ContextVar[Optional[str]],
        busy_error: type[Exception],
    ) -> RuntimePorts:
        return RuntimePorts(
            session_manager=session_manager,
            session_locks=runtime._session_locks,
            session_locks_guard=runtime._session_locks_guard,
            lease_owner=runtime._session_lease_owner,
            lease_seconds=runtime.session_lease_seconds,
            mode_context=mode_context,
            validate_mode=runtime._validate_execution_mode,
            resolve_mode=lambda tenant, user, _requested: runtime.get_execution_mode(
                tenant, user
            ),
            assert_ready=runtime.assert_llm_ready,
            ensure_session=runtime._ensure_kernel_session,
            refresh_session=runtime._refresh_kernel_session,
            busy_error=busy_error,
        )

    @staticmethod
    def _build_supervisor(
        runtime: Any,
        options: AdApplicationAssemblyOptions,
        store: Any,
    ) -> RuntimeSupervisor:
        return RuntimeSupervisor(
            store=store,
            outbox_delivery=options.outbox_delivery or runtime._default_outbox_delivery,
            scheduled_submitter=runtime._submit_scheduled_task,
            task_handlers={
                "agent.turn": runtime._execute_agent_task,
                "knowledge.ingest": runtime._execute_knowledge_ingest_task,
            },
            redact=runtime._redact_for_persistence,
            max_task_workers=options.max_task_workers,
            max_task_queue=options.max_task_queue,
            task_timeout_seconds=options.task_timeout_seconds,
            task_lease_seconds=options.task_lease_seconds,
            task_queue_poll_interval=options.task_queue_poll_interval,
            outbox_poll_interval=options.outbox_poll_interval,
            outbox_max_attempts=options.outbox_max_attempts,
            start_background_workers=False,
            create_background_workers=options.start_background_workers,
        )

    @staticmethod
    def _build_platform_application(
        runtime: Any,
        options: AdApplicationAssemblyOptions,
        services: AdApplicationServiceGraph,
        session_manager: Optional[SessionManager],
        memory_manager: Optional[MemoryManager],
        ports: RuntimePorts,
        supervisor: RuntimeSupervisor,
    ) -> Any:
        platform = AgentPlatform()
        platform.register_agent(advertising_agent_definition())
        platform.register_scenario(
            advertising_scenario_definition(agent_id=platform.agent_id)
        )
        return platform.create_application(
            "advertising",
            model=runtime._llm,
            dependencies=AdApplicationAssembly._platform_dependencies(
                runtime, options, services, session_manager, memory_manager,
                supervisor,
            ),
            options=AdApplicationAssembly._platform_options(
                runtime, options, services, ports,
            ),
        )

    @staticmethod
    def _platform_dependencies(
        runtime: Any,
        options: AdApplicationAssemblyOptions,
        services: AdApplicationServiceGraph,
        session_manager: Optional[SessionManager],
        memory_manager: Optional[MemoryManager],
        supervisor: RuntimeSupervisor,
    ) -> PlatformDependencies:
        resources = (supervisor,) if options.start_background_workers else ()
        return PlatformDependencies(
            data=DataLayer(
                knowledge_store=runtime.knowledge_provider,
                memory_store=memory_manager,
                session_store=session_manager,
                run_store=services.run_store,
            ),
            integrations=IntegrationLayer(registry=runtime.registry),
            infrastructure=InfrastructureLayer(resources=resources),
        )

    @staticmethod
    def _platform_options(
        runtime: Any,
        options: AdApplicationAssemblyOptions,
        services: AdApplicationServiceGraph,
        ports: RuntimePorts,
    ) -> dict[str, Any]:
        return {
            "ports": ports,
            "tool_catalog": AdvertisingToolCatalog(runtime),
            "tool_selector": AdApplicationAssembly._tool_selector(
                runtime, ToolSelector(),
            ),
            "skill_catalog": InMemorySkillCatalog(),
            "tool_policy": services.tool_policy,
            "context_provider": AdvertisingContextProvider(runtime),
            "input_sanitizer": runtime._redact_for_persistence,
            "request_validator": AdApplicationAssembly._request_validator(
                runtime, services.security,
            ),
            "run_store": services.run_store,
            "checkpoint_store": services.run_store,
            "transcript_store": (
                PersistenceTranscriptStore(options.persistence_store)
                if options.persistence_store is not None else None
            ),
            "metrics": getattr(runtime, "metrics", None),
            "max_turns": max(4, int(runtime.max_tool_calls) + 2),
            "max_tool_calls_per_run": int(runtime.max_tool_calls),
            "tool_execution": "sequential",
        }

    @staticmethod
    def _tool_selector(
        runtime: Any,
        selector: ToolSelector,
    ) -> Callable[[TurnRequest, Any], list[Any]]:
        def select_tools(request: TurnRequest, tools: Any) -> list[Any]:
            selected = selector.select_relevant(
                request.user_input,
                tools,
                limit=max(1, min(int(runtime.max_tool_calls), 64)),
            )
            if isinstance(request.context, dict):
                request.context["_agent_tool_namespaces"] = list(dict.fromkeys(
                    str(getattr(item, "namespace", "") or "")
                    for item in selected
                    if getattr(item, "namespace", None)
                ))
            return selected
        return select_tools

    @staticmethod
    def _request_validator(
        runtime: Any,
        security: RuntimeSecurity,
    ) -> Callable[[TurnRequest], str | None]:
        def validate_request(request: TurnRequest) -> str | None:
            context = request.context if isinstance(request.context, Mapping) else {}
            platform_params = context.get("platform_params")
            limit_error = runtime._validate_request_limits(
                request.user_input, platform_params,
            )
            if limit_error:
                return limit_error
            protected_fields = security.validate_input_redline(platform_params)
            if protected_fields:
                return (
                    "请求包含禁止传入的凭证/账户配置字段："
                    + ", ".join(protected_fields)
                )
            text_fields = security.validate_text_redline(request.user_input)
            if text_fields:
                return (
                    "请求包含禁止传入的凭证字段："
                    + ", ".join(text_fields)
                )
            return None
        return validate_request



__all__ = [
    "AdApplicationAssembly",
]
