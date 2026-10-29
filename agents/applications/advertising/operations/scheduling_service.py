"""Provider-neutral recurring task control-plane service.

This service owns durable schedule CRUD and hand-off to the generic task queue.
It does not parse business requests, select Tools or call Providers.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Optional

from agents.agent_platform.infrastructure.durable import CronExpression, next_run_at, validate_timezone
from agents.applications.advertising.persistence.schedule_pages import SchedulePageQuery


class ScheduleBusyError(RuntimeError):
    """Raised when the scheduler has already claimed a schedule for dispatch."""


class SchedulingService:
    """Durable, generic schedule management behind a narrow service port."""

    def __init__(
        self,
        *,
        store: Any,
        submit_task: Callable[..., Any],
        redact: Callable[[Any], Any],
        validate_input: Callable[[Any], list[str]],
        max_prompt_chars: int,
        schedule_record_factory: Callable[..., Any],
        schedule_run_record_factory: Callable[..., Any],
        task_kind: str,
        principal_from_metadata: Optional[Callable[[Mapping[str, Any]], Any]] = None,
        default_principal: Optional[Callable[[str, str], Any]] = None,
    ) -> None:
        self.store = store
        self.submit_task = submit_task
        self.redact = redact
        self.validate_input = validate_input
        self.max_prompt_chars = int(max_prompt_chars)
        self.schedule_record_factory = schedule_record_factory
        self.schedule_run_record_factory = schedule_run_record_factory
        self.task_kind = str(task_kind or "").strip()
        if not self.task_kind:
            raise ValueError("task_kind is required")
        self.principal_from_metadata = principal_from_metadata
        self.default_principal = default_principal

    def create(
        self, *, name: str, prompt: str, cron_expression: str,
        timezone: str = "Asia/Shanghai", payload: Optional[Mapping[str, Any]] = None,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> dict[str, Any]:
        if self.store is None or not callable(getattr(self.store, "create_scheduled_task", None)):
            raise RuntimeError("scheduled task persistence is not configured")
        expression = " ".join(str(cron_expression or "").strip().split())
        CronExpression(expression)
        timezone = validate_timezone(timezone)
        prompt = str(prompt or "").strip()
        name = str(name or prompt[:40] or "Scheduled Agent task").strip()[:120]
        if not prompt:
            raise ValueError("scheduled task prompt is required")
        if len(prompt) > self.max_prompt_chars:
            raise ValueError("scheduled task prompt exceeds input limit")
        safe_prompt = self.redact(prompt)
        if safe_prompt != prompt:
            raise ValueError("定时任务指令不能包含凭证或认证材料")
        raw_payload = dict(payload or {})
        protected = self.validate_input(raw_payload)
        if protected:
            raise ValueError("定时任务包含禁止持久化的凭证/账户配置字段：" + ", ".join(protected))
        safe_payload = self.redact(raw_payload)
        if not isinstance(safe_payload, dict):
            raise ValueError("scheduled task payload must be an object")
        now = datetime.now().isoformat()
        record = self.schedule_record_factory(
            schedule_id=str(uuid.uuid4()),
            tenant_id=str((metadata or {}).get("tenant_id") or "default"),
            user_id=str((metadata or {}).get("user_id") or "anonymous"),
            name=name,
            prompt=safe_prompt,
            cron_expression=expression,
            timezone=timezone,
            status="active",
            next_run_at=next_run_at(expression, timezone),
            payload=safe_payload,
            metadata=self.redact(dict(metadata or {})),
            created_at=now,
            updated_at=now,
        )
        self.store.create_scheduled_task(record)
        return record.to_dict()

    def list(
        self, *, user_id: Optional[str] = None, tenant_id: Optional[str] = None,
        statuses: Optional[list[str]] = None, limit: int = 100,
    ) -> list[dict[str, Any]]:
        if self.store is None:
            return []
        records = self.store.list_scheduled_tasks(
            tenant_id=tenant_id, user_id=user_id, statuses=statuses, limit=limit,
        )
        return [record.to_dict() for record in records]

    def page(self, filters: SchedulePageQuery) -> dict[str, Any]:
        if self.store is None:
            raise RuntimeError('scheduled task persistence is not configured')
        return self.redact(self.store.page_scheduled_tasks(filters))

    def runs_page(self, filters: SchedulePageQuery) -> dict[str, Any]:
        if self.store is None:
            raise RuntimeError('scheduled task persistence is not configured')
        return self.redact(self.store.page_scheduled_task_runs(filters))

    def get_run(self, schedule_id: str, run_id: str, **scope: str) -> Optional[dict]:
        if self.store is None:
            return None
        record = self.store.get_scheduled_task_run(schedule_id, run_id, **scope)
        return self.redact(record.to_dict()) if record else None

    def get(self, schedule_id: str, *, user_id: str, tenant_id: str) -> Optional[dict[str, Any]]:
        if self.store is None:
            return None
        record = self.store.get_scheduled_task(
            schedule_id, tenant_id=tenant_id, user_id=user_id
        )
        return record.to_dict() if record else None

    def update(
        self,
        schedule_id: str,
        *,
        user_id: str,
        tenant_id: str,
        name: Optional[str] = None,
        prompt: Optional[str] = None,
        cron_expression: Optional[str] = None,
        timezone: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        """Update user-editable schedule fields without changing its scope/history."""
        if self.store is None:
            raise RuntimeError("scheduled task persistence is not configured")
        current = self.store.get_scheduled_task(
            schedule_id, tenant_id=tenant_id, user_id=user_id,
        )
        if current is None:
            return None
        if getattr(current, "lease_owner", None):
            raise ScheduleBusyError("schedule is currently being claimed")

        next_name = self._validated_name(
            current.name if name is None else name,
        )
        next_prompt = self._validated_prompt(
            current.prompt if prompt is None else prompt,
        )
        next_expression = self._validated_cron(
            current.cron_expression
            if cron_expression is None else cron_expression,
        )
        next_timezone = validate_timezone(
            current.timezone if timezone is None else timezone,
        )
        payload = dict(current.payload or {})
        if prompt is not None:
            payload["user_input"] = next_prompt
        protected = self.validate_input(payload)
        if protected:
            raise ValueError(
                "定时任务包含禁止持久化的凭证/账户配置字段："
                + ", ".join(protected)
            )
        safe_payload = self.redact(payload)
        if not isinstance(safe_payload, dict):
            raise ValueError("scheduled task payload must be an object")

        recurrence_changed = (
            next_expression != current.cron_expression
            or next_timezone != current.timezone
        )
        updates: dict[str, Any] = {
            "name": next_name,
            "prompt": next_prompt,
            "cron_expression": next_expression,
            "schedule_timezone": next_timezone,
            "payload": safe_payload,
            "tenant_id": tenant_id,
            "user_id": user_id,
            "only_unleased": True,
        }
        if recurrence_changed:
            updates["next_run_at"] = next_run_at(
                next_expression, next_timezone,
            )
        if not self.store.update_scheduled_task(schedule_id, **updates):
            if self.store.get_scheduled_task(
                schedule_id, tenant_id=tenant_id, user_id=user_id,
            ) is None:
                return None
            raise ScheduleBusyError("schedule is currently being claimed")
        return self.get(schedule_id, user_id=user_id, tenant_id=tenant_id)

    def pause(self, schedule_id: str, *, user_id: str, tenant_id: str) -> Optional[dict[str, Any]]:
        if self.get(schedule_id, user_id=user_id, tenant_id=tenant_id) is None:
            return None
        record = self.store.pause_scheduled_task(
            schedule_id, tenant_id=tenant_id, user_id=user_id,
        )
        return record.to_dict() if record else None

    def resume(self, schedule_id: str, *, user_id: str, tenant_id: str) -> Optional[dict[str, Any]]:
        current = self.get(schedule_id, user_id=user_id, tenant_id=tenant_id)
        if current is None:
            return None
        record = self.store.resume_scheduled_task(
            schedule_id, next_run_at(current["cron_expression"], current["timezone"]),
            tenant_id=tenant_id, user_id=user_id,
        )
        return record.to_dict() if record else None

    def delete(self, schedule_id: str, *, user_id: str, tenant_id: str) -> bool:
        if self.get(schedule_id, user_id=user_id, tenant_id=tenant_id) is None:
            return False
        return bool(self.store.delete_scheduled_task(
            schedule_id, tenant_id=tenant_id, user_id=user_id,
        ))

    def list_runs(
        self, *, schedule_id: Optional[str] = None, user_id: Optional[str] = None,
        tenant_id: Optional[str] = None, statuses: Optional[list[str]] = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        if self.store is None:
            return []
        return [
            record.to_dict()
            for record in self.store.list_scheduled_task_runs(
                schedule_id=schedule_id, tenant_id=tenant_id, user_id=user_id,
                statuses=statuses, limit=limit,
            )
        ]

    def metrics(self, *, user_id: Optional[str] = None, tenant_id: Optional[str] = None) -> dict[str, Any]:
        if self.store is None:
            return {}
        return self.store.get_scheduled_task_metrics(tenant_id=tenant_id, user_id=user_id)

    def run_now(
        self, schedule_id: str, *, user_id: str, tenant_id: str,
    ) -> Optional[dict[str, Any]]:
        record = self.store.get_scheduled_task(
            schedule_id, tenant_id=tenant_id, user_id=user_id
        )
        if record is None:
            return None
        now = datetime.now(timezone.utc).isoformat()
        schedule_run = self.schedule_run_record_factory(
            schedule_run_id=str(uuid.uuid4()),
            schedule_id=record.schedule_id,
            tenant_id=record.tenant_id,
            user_id=record.user_id,
            scheduled_for=now,
            created_at=now,
        )
        self.store.create_scheduled_task_run(schedule_run)
        try:
            principal = self._principal_for(record, user_id, tenant_id)
            task, created = self.submit_task(
                self.task_kind, dict(record.payload or {}), principal=principal,
                idempotency_key=f"schedule:{schedule_id}:manual:{uuid.uuid4().hex}",
            )
        except Exception as error:
            self.store.update_scheduled_task_run(
                schedule_run.schedule_run_id,
                "failed",
                finished_at=datetime.now(timezone.utc).isoformat(),
                error=type(error).__name__,
            )
            raise
        task_id = str(task.get("task_id") or "") if isinstance(task, Mapping) else ""
        if not task_id:
            self.store.update_scheduled_task_run(
                schedule_run.schedule_run_id,
                "failed",
                finished_at=datetime.now(timezone.utc).isoformat(),
                error="task_id_missing",
            )
            raise RuntimeError("scheduled Agent task did not return task_id")
        if not self.store.attach_scheduled_task_run(
            schedule_run.schedule_run_id,
            task_id,
            status=str(task.get("status") or "queued"),
        ):
            self.store.update_scheduled_task_run(
                schedule_run.schedule_run_id,
                "recovery_required",
                task_id=task_id,
                finished_at=datetime.now(timezone.utc).isoformat(),
                error="task_link_failed",
            )
            raise RuntimeError("scheduled task run could not be linked")
        saved_run = self.store.list_scheduled_task_runs(
            schedule_id=schedule_id,
            tenant_id=tenant_id,
            user_id=user_id,
            limit=1,
        )
        return {
            "task": task,
            "run": saved_run[0].to_dict() if saved_run else schedule_run.to_dict(),
            "created": bool(created),
        }

    def submit_occurrence(
        self, schedule: Any, occurrence: Any,
    ) -> dict[str, Any]:
        principal = self._principal_for(
            schedule, schedule.user_id, schedule.tenant_id
        )
        task, _created = self.submit_task(
            self.task_kind, dict(schedule.payload or {}), principal=principal,
            idempotency_key=f"schedule:{schedule.schedule_id}:{occurrence.scheduled_for}",
        )
        return task

    def _principal_for(self, schedule: Any, user_id: str, tenant_id: str) -> Any:
        """Rehydrate opaque application identity through an injected adapter."""
        metadata = getattr(schedule, "metadata", None)
        claims = metadata.get("principal") if isinstance(metadata, dict) else None
        if isinstance(claims, Mapping) and self.principal_from_metadata is not None:
            principal = self.principal_from_metadata(claims)
            if principal is not None:
                return principal
        if self.default_principal is not None:
            return self.default_principal(str(user_id), str(tenant_id))
        return None

    def _validated_prompt(self, value: Any) -> str:
        prompt = str(value or "").strip()
        if not prompt:
            raise ValueError("scheduled task prompt is required")
        if len(prompt) > self.max_prompt_chars:
            raise ValueError("scheduled task prompt exceeds input limit")
        safe_prompt = self.redact(prompt)
        if safe_prompt != prompt:
            raise ValueError("定时任务指令不能包含凭证或认证材料")
        return safe_prompt

    @staticmethod
    def _validated_name(value: Any) -> str:
        name = str(value or "").strip()
        if not name or len(name) > 120:
            raise ValueError("scheduled task name is empty or exceeds 120 characters")
        return name

    @staticmethod
    def _validated_cron(value: Any) -> str:
        expression = " ".join(str(value or "").strip().split())
        CronExpression(expression)
        return expression


__all__ = ["SchedulingService"]
