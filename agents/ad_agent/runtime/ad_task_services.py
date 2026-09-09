"""Application task and schedule control services.

This module owns durable task-facing APIs while delegating execution back to
the application Runtime. It contains no Provider dispatch.
"""

from __future__ import annotations

import json
import os
from typing import Any, Iterable, Optional

from ..domain.ad.auth import RequestPrincipal
from ..persistence.models import ScheduledTaskRecord, ScheduledTaskRunRecord
from .task_executor import TaskExecutionContext


class AdTaskServices:
    def __init__(self, runtime: Any) -> None:
        self.runtime = runtime

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
        if self.runtime.task_executor is None:
            raise RuntimeError("durable task executor is not configured")
        effective_user = principal.user_id if principal is not None else str(user_id)
        effective_tenant = principal.tenant_id if principal is not None else str(tenant_id or "default")
        kind = str(kind or "").strip()
        if kind != "agent.turn":
            raise ValueError(f"unsupported task kind: {kind}")
        if not isinstance(payload, dict):
            raise ValueError("task payload must be an object")
        protected_paths = self.runtime.security.validate_input_redline(payload)
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
            "creation_blueprint_version", "execution_mode",
        }
        unknown = sorted(set(payload) - allowed_fields)
        if unknown:
            raise ValueError("任务参数不支持以下字段：" + ", ".join(unknown))
        platform_params = payload.get("platform_params")
        if platform_params is not None and not isinstance(platform_params, dict):
            raise ValueError("platform_params must be an object")
        if payload.get("execution_mode") is not None:
            self.runtime._validate_execution_mode(payload.get("execution_mode"))
        safe_payload = self.runtime._redact_for_persistence({
            "user_input": user_input,
            "session_id": payload.get("session_id"),
            "account_id": payload.get("account_id"),
            "platform_params": platform_params,
            "creation_blueprint_id": payload.get("creation_blueprint_id"),
            "creation_blueprint_version": payload.get("creation_blueprint_version"),
            "execution_mode": payload.get("execution_mode"),
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
                permissions=self.runtime._granted_permissions,
            ).to_safe_dict()
        )
        record, created = self.runtime.task_executor.submit(
            kind,
            safe_payload,
            tenant_id=effective_tenant,
            user_id=effective_user,
            idempotency_key=idempotency_key,
            workflow_id=workflow_id,
            metadata={"principal": principal_claims, "submission_source": "runtime"},
        )
        return record.to_dict(), created

    # -- Recurring schedule control plane ------------------------------

    def create_schedule(self, **kwargs: Any) -> dict[str, Any]:
        """Adapt advertising request data into the generic schedule contract."""
        values = dict(kwargs)
        account_id = values.pop("account_id", None)
        platform_params = values.pop("platform_params", None)
        session_id = values.pop("session_id", None)
        principal = values.pop("principal", None)
        values["payload"] = self.runtime._redact_for_persistence({
            "user_input": values.get("prompt"),
            "session_id": session_id,
            "account_id": account_id,
            "platform_params": platform_params or {},
            "execution_mode": "dry_run",
            "confirmed": False,
            "confirmation_payload": None,
        })
        values["metadata"] = {
            "tenant_id": getattr(principal, "tenant_id", "default"),
            "user_id": getattr(principal, "user_id", "anonymous"),
            "principal": (
                principal.to_safe_dict() if principal is not None else None
            ),
            "account_id_present": bool(account_id),
            "execution_mode": "dry_run",
            "created_via": "runtime",
        }
        return self.runtime.scheduling_service.create(**values)

    def list_schedules(self, **kwargs: Any) -> list[dict[str, Any]]:
        return self.runtime.scheduling_service.list(**kwargs)

    def get_schedule(self, schedule_id: str, *, user_id: str, tenant_id: str) -> Optional[dict[str, Any]]:
        return self.runtime.scheduling_service.get(
            schedule_id, user_id=user_id, tenant_id=tenant_id
        )

    def pause_schedule(self, schedule_id: str, *, user_id: str, tenant_id: str) -> Optional[dict[str, Any]]:
        return self.runtime.scheduling_service.pause(
            schedule_id, user_id=user_id, tenant_id=tenant_id
        )

    def resume_schedule(self, schedule_id: str, *, user_id: str, tenant_id: str) -> Optional[dict[str, Any]]:
        return self.runtime.scheduling_service.resume(
            schedule_id, user_id=user_id, tenant_id=tenant_id
        )

    def delete_schedule(self, schedule_id: str, *, user_id: str, tenant_id: str) -> bool:
        return self.runtime.scheduling_service.delete(
            schedule_id, user_id=user_id, tenant_id=tenant_id
        )

    def list_schedule_runs(self, **kwargs: Any) -> list[dict[str, Any]]:
        return self.runtime.scheduling_service.list_runs(**kwargs)

    def get_schedule_metrics(self, **kwargs: Any) -> dict[str, Any]:
        return self.runtime.scheduling_service.metrics(**kwargs)

    def run_schedule_now(self, schedule_id: str, *, user_id: str, tenant_id: str) -> Optional[dict[str, Any]]:
        return self.runtime.scheduling_service.run_now(
            schedule_id, user_id=user_id, tenant_id=tenant_id
        )

    def submit_scheduled_task(
        self, schedule: ScheduledTaskRecord, occurrence: ScheduledTaskRunRecord,
    ) -> dict[str, Any]:
        return self.runtime.scheduling_service.submit_occurrence(schedule, occurrence)

    def execute_agent_task(self, context: TaskExecutionContext) -> dict[str, Any]:
        """Re-enter Runtime; this handler never resolves or calls a Provider."""
        if context.is_cancelled():
            return {"success": False, "cancelled": True}
        claims = context.metadata.get("principal")
        principal = RequestPrincipal.from_claims(claims) if isinstance(claims, dict) else None
        payload = context.payload
        return self.runtime.run(
            user_input=str(payload.get("user_input") or ""),
            session_id=payload.get("session_id"),
            account_id=payload.get("account_id"),
            platform_params=payload.get("platform_params"),
            creation_blueprint_id=payload.get("creation_blueprint_id"),
            creation_blueprint_version=payload.get("creation_blueprint_version"),
            execution_mode=payload.get("execution_mode"),
            confirmed=False,
            confirmation_payload=None,
            principal=principal,
            user_id=context.user_id,
            tenant_id=context.tenant_id,
            cancellation_event=context.cancel_event,
            task_id=context.task_id,
        )

    def get_task(
        self, task_id: str, *, user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        if self.runtime.task_executor is None:
            return None
        record = self.runtime.task_executor.get(task_id, tenant_id=tenant_id, user_id=user_id)
        return record.to_dict() if record else None

    def list_tasks(
        self, *, user_id: str, tenant_id: str,
        statuses: Optional[list[str]] = None, limit: int = 50,
    ) -> list[dict[str, Any]]:
        if self.runtime.task_executor is None:
            return []
        return [
            record.to_dict()
            for record in self.runtime.task_executor.list(
                tenant_id=tenant_id, user_id=user_id,
                statuses=statuses, limit=limit,
            )
        ]

    def get_monitoring_snapshot(
        self, *, user_id: Optional[str] = None, tenant_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Build the read-only operational view used by the monitoring console."""
        if self.runtime._persistence_store is None:
            raise RuntimeError("monitoring requires a persistence-backed Runtime")
        getter = getattr(self.runtime._persistence_store, "get_monitoring_snapshot", None)
        if not callable(getter):
            raise RuntimeError("persistence backend does not support monitoring")
        snapshot = getter(
            tenant_id=tenant_id,
            user_id=user_id,
            stale_after_seconds=self.runtime.workflow_stale_after_seconds,
        )
        task_executor = self.runtime.task_executor
        outbox_consumer = self.runtime.outbox_consumer
        snapshot["instance"] = {
            "process_id": os.getpid(),
            "execution_mode": self.runtime.get_execution_mode(tenant_id, user_id)
            if tenant_id and user_id else self.runtime.execution_mode,
            "tool_count": len(self.runtime.registry.list_all()),
            "platform_count": len(self.runtime.registry.list_all_namespaces()),
            "task_executor": task_executor.metrics() if task_executor else {"state": "disabled"},
            "outbox_consumer": outbox_consumer.metrics() if outbox_consumer else {"state": "disabled"},
            "event_repair": self.runtime.event_repair_consumer.metrics()
            if self.runtime.event_repair_consumer else {"state": "disabled"},
            "scheduler": self.runtime.scheduler.metrics() if self.runtime.scheduler else {"state": "disabled"},
        }
        return snapshot

    def pause_task(
        self, task_id: str, *, user_id: str, tenant_id: str,
    ) -> Optional[dict[str, Any]]:
        if self.runtime.task_executor is None:
            return None
        if self.runtime.task_executor.get(task_id, tenant_id=tenant_id, user_id=user_id) is None:
            return None
        record = self.runtime.task_executor.pause(
            task_id, tenant_id=tenant_id, user_id=user_id,
        )
        return record.to_dict() if record else None

    def resume_task(
        self, task_id: str, *, user_id: str, tenant_id: str,
    ) -> Optional[dict[str, Any]]:
        if self.runtime.task_executor is None:
            return None
        if self.runtime.task_executor.get(task_id, tenant_id=tenant_id, user_id=user_id) is None:
            return None
        record = self.runtime.task_executor.resume(
            task_id, tenant_id=tenant_id, user_id=user_id,
        )
        return record.to_dict() if record else None

    def recover_task(
        self, task_id: str, *, user_id: str, tenant_id: str,
        recovery_reference: str, provider_verified: bool = False,
        permissions: Optional[Iterable[str]] = None,
    ) -> Optional[dict[str, Any]]:
        """Explicitly requeue an uncertain task after provider readback.

        A stale task is never replayed merely because a process restarted.
        The caller must prove that a provider/workflow reconciliation was
        performed and supply its audit reference.  The task then re-enters
        the normal ``agent.turn`` Runtime boundary.
        """
        if self.runtime.task_executor is None:
            return None
        task = self.runtime.task_executor.get(task_id, tenant_id=tenant_id, user_id=user_id)
        if task is None:
            return None
        granted = set(permissions or self.runtime._granted_permissions)
        if "ads.reconcile" not in granted and "ads.write" not in granted:
            raise PermissionError("task recovery requires ads.reconcile or ads.write")
        if not provider_verified:
            raise ValueError("provider_verified=true is required before task recovery")
        if not str(recovery_reference or "").strip():
            raise ValueError("recovery_reference is required")
        recovered = self.runtime.task_executor.requeue_recovery(
            task_id, recovery_reference=str(recovery_reference),
            tenant_id=tenant_id, user_id=user_id,
        )
        return recovered.to_dict() if recovered else None

    def cancel_task(
        self, task_id: str, *, user_id: str, tenant_id: str,
    ) -> Optional[dict[str, Any]]:
        if self.runtime.task_executor is None:
            return None
        if self.runtime.task_executor.get(task_id, tenant_id=tenant_id, user_id=user_id) is None:
            return None
        record = self.runtime.task_executor.cancel(
            task_id, tenant_id=tenant_id, user_id=user_id,
        )
        return record.to_dict() if record else None
