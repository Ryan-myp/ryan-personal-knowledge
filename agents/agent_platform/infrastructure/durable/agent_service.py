"""Bind a durable task queue to the application's single Agent Run entry."""

from __future__ import annotations

from typing import Any, Callable

from agents.agent_harness import RunResult, TurnRequest
from agents.agent_harness.redaction import redact_for_persistence

from .task_executor import TaskExecutionContext, TaskExecutor


class DurableAgentService:
    """Queue turns without giving durable payloads authority over identity."""

    def __init__(
        self,
        *,
        application: Any,
        store: Any,
        principal_resolver: Callable[[str, str], Any],
        task_kind: str = "agent.turn",
        max_task_workers: int = 4,
        max_task_queue: int = 32,
        max_input_chars: int = 100_000,
    ) -> None:
        if not callable(principal_resolver):
            raise TypeError("principal_resolver must be callable")
        self.application = application
        self.principal_resolver = principal_resolver
        self.task_kind = str(task_kind or "").strip()
        if not self.task_kind:
            raise ValueError("task_kind is required")
        if max_input_chars <= 0:
            raise ValueError("max_input_chars must be positive")
        self.max_input_chars = int(max_input_chars)
        self.executor = TaskExecutor(
            store,
            max_workers=max_task_workers,
            max_queue=max_task_queue,
            redact=redact_for_persistence,
        )
        self.executor.register_handler(self.task_kind, self._run_task)

    @staticmethod
    def _identity(principal: Any) -> tuple[str, str]:
        if principal is None:
            raise ValueError("trusted principal is required")
        tenant_id = str(getattr(principal, "tenant_id", "") or "").strip()
        user_id = str(getattr(principal, "user_id", "") or "").strip()
        if not tenant_id or not user_id:
            raise ValueError("trusted principal requires tenant_id and user_id")
        return tenant_id, user_id

    def _run_task(self, task: TaskExecutionContext) -> dict[str, Any]:
        principal = self.principal_resolver(task.tenant_id, task.user_id)
        if self._identity(principal) != (task.tenant_id, task.user_id):
            raise PermissionError("durable task principal no longer matches owner")
        payload = task.payload
        result = self.application.run(TurnRequest(
            user_input=str(payload["user_input"]),
            session_id=str(payload["session_id"]),
            principal=principal,
            tenant_id=task.tenant_id,
            user_id=task.user_id,
            task_id=task.task_id,
            cancellation_event=task.cancel_event,
            lease_lost_event=task.lease_lost_event,
        ))
        return RunResult.from_payload(result).to_dict()

    def start(self) -> None:
        start = getattr(self.application, "start", None)
        if callable(start):
            start()
        self.executor.start()

    def submit(
        self,
        user_input: str,
        *,
        principal: Any,
        session_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> tuple[Any, bool]:
        tenant_id, user_id = self._identity(principal)
        content = str(user_input or "").strip()
        if not content:
            raise ValueError("user_input is required")
        if len(content) > self.max_input_chars:
            raise ValueError("user_input exceeds the configured character limit")
        session_value = str(session_id or "")
        if len(session_value) > 255:
            raise ValueError("session_id exceeds 255 characters")
        key_value = str(idempotency_key or "").strip() or None
        if key_value is not None and len(key_value) > 255:
            raise ValueError("idempotency_key exceeds 255 characters")
        payload = {"user_input": content, "session_id": session_value}
        record, created = self.executor.submit(
            self.task_kind,
            payload,
            tenant_id=tenant_id,
            user_id=user_id,
            idempotency_key=key_value,
        )
        if not created and (
            getattr(record, "kind", None) != self.task_kind
            or getattr(record, "payload", None) != payload
        ):
            raise ValueError("idempotency key conflict: request differs from existing task")
        return record, created

    def get(self, task_id: str, *, principal: Any) -> Any:
        tenant_id, user_id = self._identity(principal)
        return self.executor.get(
            task_id, tenant_id=tenant_id, user_id=user_id,
        )

    def list(
        self, *, principal: Any, statuses: list[str] | None = None,
        limit: int = 50,
    ) -> list[Any]:
        tenant_id, user_id = self._identity(principal)
        return self.executor.list(
            tenant_id=tenant_id, user_id=user_id, statuses=statuses, limit=limit,
        )

    def cancel(self, task_id: str, *, principal: Any) -> Any:
        tenant_id, user_id = self._identity(principal)
        return self.executor.cancel(
            task_id, tenant_id=tenant_id, user_id=user_id,
        )

    def pause(self, task_id: str, *, principal: Any) -> Any:
        tenant_id, user_id = self._identity(principal)
        return self.executor.pause(
            task_id, tenant_id=tenant_id, user_id=user_id,
        )

    def resume(self, task_id: str, *, principal: Any) -> Any:
        tenant_id, user_id = self._identity(principal)
        return self.executor.resume(
            task_id, tenant_id=tenant_id, user_id=user_id,
        )

    def close(self) -> None:
        self.executor.shutdown(wait=True)


__all__ = ["DurableAgentService"]
