"""Composition of the advertising application's Runtime dependencies.

``AdAgentRuntime`` is the public application facade, not the place where
every infrastructure object should be constructed.  This module owns the
application composition graph and returns explicit components to the facade.

The assembly is intentionally not a generic Runtime.  It is the advertising
application's composition root: it may connect advertising services to the
generic Kernel, durable ports and worker supervisor, but it must not add
provider branches or business workflow decisions.  A different application
can reuse the Core Kernel and worker services with its own assembly.
"""

from __future__ import annotations

import logging
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Callable, Optional

from ..core.memory import MemoryManager
from ..core.agent_runtime import GenericAgentRuntime
from ..domain.ad.auth import RequestPrincipal
from ..domain.ad.security import ACCOUNT_SCOPE_FIELDS
from ..persistence.interfaces import PersistenceBackend
from ..persistence.models import ScheduledTaskRecord
from ..persistence.session_manager import SessionManager
from .account_context import AccountResolver
from .ad_conversation_services import AdConversationServices
from .ad_persistence_services import AdPersistenceServices
from .ad_session_services import AdSessionServices
from .ad_task_services import AdTaskServices
from .ad_turn_pipeline import AdTurnPipeline
from .ad_workflow_services import AdWorkflowServices
from .input_builder import ToolInputBuilder
from .outbox import OutboxPublisher
from .scheduling_service import SchedulingService
from .security import RuntimeSecurity
from .services import AdRuntimeServices
from .supervisor import RuntimeSupervisor
from .tool_executor import ToolExecutor
from .workflow import WorkflowCoordinator

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AdRuntimeAssemblyOptions:
    """Infrastructure options supplied by the application boundary.

    Domain settings such as Skill roots, Tool definitions and provider
    clients are initialized by ``AdAgentRuntime`` before this assembly runs.
    Only lifecycle/queue options belong here, which keeps the composition
    graph explicit and makes it possible to replace SQLite with MySQL through
    the same persistence port.
    """

    persistence_store: Optional[PersistenceBackend]
    outbox_delivery: Optional[Callable[[Any], None]]
    outbox_poll_interval: float
    outbox_max_attempts: int
    max_task_workers: int
    max_task_queue: int
    task_timeout_seconds: float
    task_lease_seconds: float
    task_queue_poll_interval: float
    start_background_workers: bool


@dataclass(frozen=True)
class AdRuntimeComponents:
    """Fully wired application services returned by the assembly.

    Keeping these as one typed value prevents the facade constructor from
    silently growing another group of partially initialized attributes.
    ``install`` is the only mutation step and is intentionally kept at the
    application boundary.
    """

    persistence_store: Optional[PersistenceBackend]
    session_manager: Optional[SessionManager]
    memory_manager: Optional[MemoryManager]
    outbox: Optional[OutboxPublisher]
    services: AdRuntimeServices
    input_builder: ToolInputBuilder
    account_resolver: AccountResolver
    workflow: WorkflowCoordinator
    security: RuntimeSecurity
    scheduling_service: SchedulingService
    persistence_services: AdPersistenceServices
    conversation_services: AdConversationServices
    session_services: AdSessionServices
    workflow_services: AdWorkflowServices
    task_services: AdTaskServices
    runtime_kernel: GenericAgentRuntime
    tool_executor: ToolExecutor
    supervisor: RuntimeSupervisor
    start_background_workers: bool

    def install(self, runtime: Any) -> None:
        """Install the graph on the application facade in one bounded step."""
        values = {
            "_persistence_store": self.persistence_store,
            "_session_manager": self.session_manager,
            "_memory_manager": self.memory_manager,
            "outbox": self.outbox,
            "services": self.services,
            "input_builder": self.input_builder,
            "account_resolver": self.account_resolver,
            "workflow": self.workflow,
            "security": self.security,
            "scheduling_service": self.scheduling_service,
            "persistence_services": self.persistence_services,
            "conversation_services": self.conversation_services,
            "session_services": self.session_services,
            "workflow_services": self.workflow_services,
            "task_services": self.task_services,
            "_runtime_kernel": self.runtime_kernel,
            "tool_executor": self.tool_executor,
            "supervisor": self.supervisor,
        }
        for name, value in values.items():
            setattr(runtime, name, value)
        runtime.outbox_consumer = self.supervisor.outbox_consumer
        runtime.event_repair_consumer = self.supervisor.event_repair_consumer
        runtime.task_executor = self.supervisor.task_executor
        runtime.scheduler = self.supervisor.scheduler
        if self.start_background_workers:
            self.supervisor.start()


class AdRuntimeAssembly:
    """Build the advertising application graph over generic runtime ports."""

    @classmethod
    def compose(
        cls,
        runtime: Any,
        options: AdRuntimeAssemblyOptions,
        *,
        mode_context: ContextVar[Optional[str]],
        busy_error: type[Exception],
    ) -> AdRuntimeComponents:
        store = options.persistence_store
        session_manager: Optional[SessionManager] = None
        memory_manager: Optional[MemoryManager] = None
        if store is not None:
            session_manager = SessionManager(store)
            recover_runs = getattr(session_manager, "recover_stale_execution_runs", None)
            if callable(recover_runs):
                try:
                    recovered_runs = recover_runs(runtime.workflow_stale_after_seconds)
                    if recovered_runs:
                        logger.warning(
                            "marked %s stale Agent runs for recovery", recovered_runs
                        )
                except Exception:
                    logger.exception("failed to recover stale Agent runs")
            if all(
                callable(getattr(store, method, None))
                for method in ("save_memory", "search_memories", "delete_memory")
            ):
                # Reuse the SessionManager-owned policy/cache instance so
                # Runtime recall and management/API recall share one bounded
                # cache and one automatic-capture switch per process.
                memory_manager = session_manager.memory_manager
                memory_manager.set_auto_capture_enabled(
                    bool(getattr(runtime, "auto_memory_capture_enabled", True))
                )
            if runtime.write_guard and hasattr(runtime.write_guard, "bind_store"):
                runtime.write_guard.bind_store(store)

        outbox = OutboxPublisher(session_manager) if session_manager else None
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
        scheduling_service = SchedulingService(
            store=store,
            submit_task=runtime.submit_task,
            session_context=lambda session_id: runtime._sessions.get(str(session_id or "")),
            preflight=runtime.preflight_scheduled_prompt,
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
        services.bind_scheduling(scheduling_service)

        persistence_services = AdPersistenceServices(runtime)
        conversation_services = AdConversationServices(runtime)
        session_services = AdSessionServices(runtime)
        workflow_services = AdWorkflowServices(runtime)
        task_services = AdTaskServices(runtime)
        turn_pipeline = AdTurnPipeline(runtime)
        runtime_kernel = GenericAgentRuntime(
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
            turn_pipeline=turn_pipeline,
            tool_registry=runtime.registry,
            on_tool_catalog_changed=runtime._on_generic_tool_catalog_changed,
            busy_error=busy_error,
        )
        tool_executor = ToolExecutor(services)
        supervisor = RuntimeSupervisor(
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
            # Start only after ``AdRuntimeComponents.install`` has published
            # every callback target on the facade. This prevents a recovered
            # task/schedule from racing a partially initialized application.
            start_background_workers=False,
            create_background_workers=options.start_background_workers,
        )
        return AdRuntimeComponents(
            persistence_store=store,
            session_manager=session_manager,
            memory_manager=memory_manager,
            outbox=outbox,
            services=services,
            input_builder=input_builder,
            account_resolver=account_resolver,
            workflow=workflow,
            security=security,
            scheduling_service=scheduling_service,
            persistence_services=persistence_services,
            conversation_services=conversation_services,
            session_services=session_services,
            workflow_services=workflow_services,
            task_services=task_services,
            runtime_kernel=runtime_kernel,
            tool_executor=tool_executor,
            supervisor=supervisor,
            start_background_workers=options.start_background_workers,
        )


__all__ = [
    "AdRuntimeAssembly",
    "AdRuntimeAssemblyOptions",
    "AdRuntimeComponents",
]
