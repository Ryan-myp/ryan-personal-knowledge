"""Advertising application component contracts and persistence adapters."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Optional

from agents.agent_harness import AgentRuntime
from agents.agent_harness.core.memory import MemoryManager
from agents.agent_platform import PlatformApplication
from agents.agent_platform.data.persistence.interfaces import PersistenceBackend
from agents.agent_platform.data.persistence.session_manager import SessionManager
from agents.agent_platform.infrastructure.durable import OutboxPublisher, RuntimeSupervisor
from .account_context import AccountResolver
from .ad_conversation_services import AdConversationServices
from .ad_persistence_services import AdPersistenceServices
from .ad_session_services import AdSessionServices
from .ad_task_services import AdTaskServices
from .ad_workflow_services import AdWorkflowServices
from .input_builder import ToolInputBuilder
from .scheduling_service import SchedulingService
from .security import RuntimeSecurity
from .services import AdRuntimeServices
from .tool_executor import ToolExecutor
from .workflow import WorkflowCoordinator


class AdRunStoreAdapter:
    """Expose the advertising persistence API through the generic RunStore port."""

    def __init__(self, session_manager: SessionManager, runtime: Any) -> None:
        self.session_manager = session_manager
        self.runtime = runtime

    def start_run(self, **payload: Any) -> Any:
        from agents.agent_platform.data.persistence.models import ExecutionRunRecord

        now = datetime.now(timezone.utc).isoformat()
        return self.session_manager.create_execution_run(
            ExecutionRunRecord(
                run_id=str(payload.get("run_id") or ""),
                session_id=str(payload.get("session_id") or ""),
                turn_id=str(payload.get("turn_id") or ""),
                user_id=str(payload.get("user_id") or "anonymous"),
                tenant_id=str(payload.get("tenant_id") or "default"),
                execution_mode=str(
                    payload.get("execution_mode")
                    or getattr(self.runtime, "execution_mode", "dry_run")
                ),
                task_id=(
                    str(payload["task_id"]) if payload.get("task_id") else None
                ),
                metadata={"effect_state": "unknown"},
                created_at=now,
                updated_at=now,
            )
        )

    def append_event(self, run_id: str, event: dict[str, Any]) -> bool:
        try:
            accepted = self.session_manager.append_execution_run_event(
                str(run_id), dict(event),
            )
        except Exception:
            accepted = False
        if accepted:
            return True
        enqueue = getattr(
            self.runtime._persistence_store,
            "enqueue_execution_event_repair",
            None,
        )
        if callable(enqueue):
            enqueue(str(run_id), dict(event))
        return False

    def finish_run(
        self,
        run_id: str,
        *,
        status: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> bool:
        current = self.session_manager.get_execution_run(str(run_id))
        current_metadata = getattr(current, "metadata", {}) if current else {}
        merged = {
            **(current_metadata if isinstance(current_metadata, dict) else {}),
            **dict(metadata or {}),
        }
        return bool(self.session_manager.update_execution_run(
            str(run_id),
            status=str(status),
            metadata=merged,
        ))

    def save_checkpoint(
        self, run_id: str, checkpoint: Mapping[str, Any],
    ) -> bool:
        current = self.session_manager.get_execution_run(str(run_id))
        metadata = getattr(current, "metadata", {}) if current else {}
        merged = dict(metadata) if isinstance(metadata, dict) else {}
        merged["checkpoint"] = dict(checkpoint)
        return bool(self.session_manager.update_execution_run(
            str(run_id), metadata=merged,
        ))

    def load_checkpoint(self, run_id: str) -> Optional[Mapping[str, Any]]:
        current = self.session_manager.get_execution_run(str(run_id))
        metadata = getattr(current, "metadata", {}) if current else {}
        checkpoint = (
            metadata.get("checkpoint")
            if isinstance(metadata, dict) else None
        )
        return dict(checkpoint) if isinstance(checkpoint, Mapping) else None

    def clear_checkpoint(self, run_id: str) -> bool:
        current = self.session_manager.get_execution_run(str(run_id))
        metadata = getattr(current, "metadata", {}) if current else {}
        merged = dict(metadata) if isinstance(metadata, dict) else {}
        merged.pop("checkpoint", None)
        return bool(self.session_manager.update_execution_run(
            str(run_id), metadata=merged,
        ))


@dataclass(frozen=True)
class AdApplicationAssemblyOptions:
    """Infrastructure options supplied by the application boundary.

    Domain settings such as Skill roots, Tool definitions and provider
    clients are initialized by ``AdvertisingComposition`` before this assembly runs.
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
class AdApplicationServiceGraph:
    """Advertising-facing adapters consumed by the generic Platform graph."""

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
    run_store: Any
    tool_policy: Any
    tool_executor: ToolExecutor


@dataclass(frozen=True)
class AdApplicationComponents:
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
    runtime_kernel: AgentRuntime
    platform_application: PlatformApplication
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
            "_platform_application": self.platform_application,
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
