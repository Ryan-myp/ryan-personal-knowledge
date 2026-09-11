"""Stable application-facing facades for :class:`AdAgentRuntime`.

The runtime is the advertising composition root, not the owner of every
application query and control API.  These small facades preserve the public
runtime surface used by HTTP, CLI, and worker adapters while keeping the
composition root focused on wiring, request entry, and lifecycle policy.

They intentionally contain delegation only.  Durable state access and
application query assembly stay in the corresponding service modules; Tool
execution and Provider access remain behind the normal Runtime boundaries.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional

from ..persistence.models import ScheduledTaskRecord, ScheduledTaskRunRecord
from .ad_conversation_services import AdConversationServices
from .task_executor import TaskExecutionContext


class AdTaskRuntimeFacade:
    """Keep task and schedule controls out of the composition root body."""

    def submit_task(self, *args: Any, **kwargs: Any) -> tuple[dict[str, Any], bool]:
        return self.task_services.submit_task(*args, **kwargs)

    def create_schedule(self, **kwargs: Any) -> dict[str, Any]:
        return self.task_services.create_schedule(**kwargs)

    def list_schedules(self, **kwargs: Any) -> list[dict[str, Any]]:
        return self.task_services.list_schedules(**kwargs)

    def get_schedule(
        self, schedule_id: str, *, user_id: str, tenant_id: str
    ) -> Optional[dict[str, Any]]:
        return self.task_services.get_schedule(
            schedule_id, user_id=user_id, tenant_id=tenant_id
        )

    def pause_schedule(
        self, schedule_id: str, *, user_id: str, tenant_id: str
    ) -> Optional[dict[str, Any]]:
        return self.task_services.pause_schedule(
            schedule_id, user_id=user_id, tenant_id=tenant_id
        )

    def resume_schedule(
        self, schedule_id: str, *, user_id: str, tenant_id: str
    ) -> Optional[dict[str, Any]]:
        return self.task_services.resume_schedule(
            schedule_id, user_id=user_id, tenant_id=tenant_id
        )

    def delete_schedule(
        self, schedule_id: str, *, user_id: str, tenant_id: str
    ) -> bool:
        return self.task_services.delete_schedule(
            schedule_id, user_id=user_id, tenant_id=tenant_id
        )

    def list_schedule_runs(self, **kwargs: Any) -> list[dict[str, Any]]:
        return self.task_services.list_schedule_runs(**kwargs)

    def get_schedule_metrics(self, **kwargs: Any) -> dict[str, Any]:
        return self.task_services.get_schedule_metrics(**kwargs)

    def run_schedule_now(
        self, schedule_id: str, *, user_id: str, tenant_id: str
    ) -> Optional[dict[str, Any]]:
        return self.task_services.run_schedule_now(
            schedule_id, user_id=user_id, tenant_id=tenant_id
        )

    def _submit_scheduled_task(
        self, schedule: ScheduledTaskRecord, occurrence: ScheduledTaskRunRecord
    ) -> dict[str, Any]:
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


class AdConversationRuntimeFacade:
    """Expose conversation and durable run queries without query assembly."""

    @staticmethod
    def _decode_session_metadata(session: Mapping[str, Any]) -> dict[str, Any]:
        return AdConversationServices._decode_session_metadata(session)

    @staticmethod
    def _conversation_summary(
        session: Mapping[str, Any], messages: list[Mapping[str, Any]]
    ) -> dict[str, Any]:
        return AdConversationServices._conversation_summary(session, messages)

    def list_conversations(self, *args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        return self.conversation_services.list_conversations(*args, **kwargs)

    def rename_conversation(
        self, *args: Any, **kwargs: Any
    ) -> Optional[dict[str, Any]]:
        return self.conversation_services.rename_conversation(*args, **kwargs)

    def search_knowledge(self, *args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        return self.conversation_services.search_knowledge(*args, **kwargs)

    def catalog_knowledge(self, *args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        return self.conversation_services.catalog_knowledge(*args, **kwargs)

    def summarize_knowledge(self, *args: Any, **kwargs: Any) -> str:
        return self.conversation_services.summarize_knowledge(*args, **kwargs)

    def get_conversation(
        self, *args: Any, **kwargs: Any
    ) -> Optional[dict[str, Any]]:
        return self.conversation_services.get_conversation(*args, **kwargs)

    @staticmethod
    def _execution_run_dict(record: Any) -> Optional[dict[str, Any]]:
        return AdConversationServices._execution_run_dict(record)

    def _bind_execution_run_workflow(self, *args: Any, **kwargs: Any) -> None:
        self.conversation_services._bind_execution_run_workflow(*args, **kwargs)

    def get_latest_run(
        self, *args: Any, **kwargs: Any
    ) -> Optional[dict[str, Any]]:
        return self.conversation_services.get_latest_run(*args, **kwargs)

    def get_run_events(
        self, *args: Any, **kwargs: Any
    ) -> Optional[dict[str, Any]]:
        return self.conversation_services.get_run_events(*args, **kwargs)

    def delete_conversation(self, *args: Any, **kwargs: Any) -> bool:
        return self.conversation_services.delete_conversation(*args, **kwargs)

    def delete_conversations(self, *args: Any, **kwargs: Any) -> list[str]:
        return self.conversation_services.delete_conversations(*args, **kwargs)


class AdSessionRuntimeFacade:
    """Bridge the generic Kernel session hooks to the app session service."""

    def _ensure_session(
        self,
        session_id: str,
        user_id: str,
        account_id: str,
        credentials: dict,
        tenant_id: str = "default",
    ) -> Any:
        return self.session_services.ensure_session(
            session_id, user_id, account_id, credentials, tenant_id=tenant_id
        )

    def _refresh_session_for_turn(
        self,
        session_id: str,
        user_id: str,
        account_id: Optional[str],
        credentials: Optional[dict],
        tenant_id: str = "default",
    ) -> Any:
        return self.session_services.refresh_session_for_turn(
            session_id, user_id, account_id, credentials, tenant_id=tenant_id
        )


class AdWorkflowRuntimeFacade:
    """Expose durable workflow inspection and recovery controls."""

    def get_workflow(self, *args: Any, **kwargs: Any) -> Optional[dict[str, Any]]:
        return self.workflow_services.get_workflow(*args, **kwargs)

    def get_workflow_resume_plan(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return self.workflow_services.get_workflow_resume_plan(*args, **kwargs)

    def _is_stale_workflow(self, workflow: Mapping[str, Any]) -> bool:
        return self.workflow_services._is_stale_workflow(workflow)

    def list_resumable_workflows(
        self, *args: Any, **kwargs: Any
    ) -> list[dict[str, Any]]:
        return self.workflow_services.list_resumable_workflows(*args, **kwargs)

    def reconcile_workflow(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return self.workflow_services.reconcile_workflow(*args, **kwargs)

    def reconcile_workflow_from_provider(
        self, *args: Any, **kwargs: Any
    ) -> dict[str, Any]:
        return self.workflow_services.reconcile_workflow_from_provider(
            *args, **kwargs
        )

    def cancel_workflow(self, *args: Any, **kwargs: Any) -> bool:
        return self.workflow_services.cancel_workflow(*args, **kwargs)


__all__ = [
    "AdConversationRuntimeFacade",
    "AdSessionRuntimeFacade",
    "AdTaskRuntimeFacade",
    "AdWorkflowRuntimeFacade",
]
