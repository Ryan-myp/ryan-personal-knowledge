"""Provider-neutral recurring task control-plane service.

This service owns durable schedule CRUD, schedule drafts and hand-off to a
generic task queue. It does not parse business requests, select Tools or call
Providers; those responsibilities remain with a Feature and the Agent turn
engine respectively.
"""

from __future__ import annotations

import copy
import json
import uuid
from datetime import datetime
from typing import Any, Callable, Mapping, Optional

from ..domain.ad.auth import RequestPrincipal
from ..persistence.models import ScheduledTaskRecord, ScheduledTaskRunRecord
from .scheduler import CronExpression, next_run_at, validate_timezone


class SchedulingService:
    """Durable, generic schedule management behind a narrow service port."""

    def __init__(
        self,
        *,
        store: Any,
        submit_task: Callable[..., Any],
        session_context: Callable[[str], Any],
        preflight: Callable[..., dict[str, Any]],
        redact: Callable[[Any], Any],
        validate_input: Callable[[Any], list[str]],
        max_prompt_chars: int,
        default_permissions: Any,
    ) -> None:
        self.store = store
        self.submit_task = submit_task
        self.session_context = session_context
        self.preflight = preflight
        self.redact = redact
        self.validate_input = validate_input
        self.max_prompt_chars = int(max_prompt_chars)
        self.default_permissions = default_permissions

    def get_draft(self, session_id: str) -> Optional[dict[str, Any]]:
        session = self.session_context(str(session_id or ""))
        if session is None:
            return None
        draft = session.ctx.metadata.get("schedule_draft")
        return copy.deepcopy(draft) if isinstance(draft, dict) else None

    def set_draft(
        self, session_id: str, draft: Optional[Mapping[str, Any]],
    ) -> None:
        session = self.session_context(str(session_id or ""))
        if session is None:
            return
        if draft is None:
            session.ctx.metadata.pop("schedule_draft", None)
            return
        safe = self.redact(dict(draft))
        serialized = json.dumps(safe, ensure_ascii=False, default=str)
        if len(serialized.encode("utf-8")) > 32_000:
            raise ValueError("scheduled task draft exceeds persistence limit")
        session.ctx.metadata["schedule_draft"] = safe

    def preflight_prompt(self, prompt: str, **kwargs: Any) -> dict[str, Any]:
        return self.preflight(prompt, **kwargs)

    def create(
        self, *, name: str, prompt: str, cron_expression: str,
        timezone: str = "Asia/Shanghai", session_id: Optional[str] = None,
        account_id: Optional[str] = None, platform_params: Optional[dict] = None,
        principal: Optional[RequestPrincipal] = None,
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
        safe_params = platform_params if platform_params is not None else {}
        protected = self.validate_input(safe_params)
        if protected:
            raise ValueError("定时任务包含禁止持久化的凭证/账户配置字段：" + ", ".join(protected))
        effective_principal = principal or RequestPrincipal(
            user_id="anonymous", tenant_id="default",
            permissions=self.default_permissions,
        )
        safe_payload = self.redact({
            "user_input": safe_prompt,
            "session_id": session_id,
            "account_id": account_id,
            "platform_params": safe_params,
            "execution_mode": "dry_run",
            "confirmed": False,
            "confirmation_payload": None,
        })
        now = datetime.now().isoformat()
        record = ScheduledTaskRecord(
            schedule_id=str(uuid.uuid4()),
            tenant_id=str(effective_principal.tenant_id),
            user_id=str(effective_principal.user_id),
            name=name,
            prompt=safe_prompt,
            cron_expression=expression,
            timezone=timezone,
            status="active",
            next_run_at=next_run_at(expression, timezone),
            payload=safe_payload,
            metadata={
                "principal": effective_principal.to_safe_dict(),
                "account_id_present": bool(account_id),
                "execution_mode": "dry_run",
                "created_via": "runtime",
            },
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

    def get(self, schedule_id: str, *, user_id: str, tenant_id: str) -> Optional[dict[str, Any]]:
        if self.store is None:
            return None
        record = self.store.get_scheduled_task(
            schedule_id, tenant_id=tenant_id, user_id=user_id
        )
        return record.to_dict() if record else None

    def pause(self, schedule_id: str, *, user_id: str, tenant_id: str) -> Optional[dict[str, Any]]:
        if self.get(schedule_id, user_id=user_id, tenant_id=tenant_id) is None:
            return None
        record = self.store.pause_scheduled_task(schedule_id)
        return record.to_dict() if record else None

    def resume(self, schedule_id: str, *, user_id: str, tenant_id: str) -> Optional[dict[str, Any]]:
        current = self.get(schedule_id, user_id=user_id, tenant_id=tenant_id)
        if current is None:
            return None
        record = self.store.resume_scheduled_task(
            schedule_id, next_run_at(current["cron_expression"], current["timezone"])
        )
        return record.to_dict() if record else None

    def delete(self, schedule_id: str, *, user_id: str, tenant_id: str) -> bool:
        if self.get(schedule_id, user_id=user_id, tenant_id=tenant_id) is None:
            return False
        return bool(self.store.delete_scheduled_task(schedule_id))

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

    def run_now(self, schedule_id: str, *, user_id: str, tenant_id: str) -> Optional[dict[str, Any]]:
        record = self.store.get_scheduled_task(
            schedule_id, tenant_id=tenant_id, user_id=user_id
        )
        if record is None:
            return None
        claims = record.metadata.get("principal") if isinstance(record.metadata, dict) else None
        principal = (
            RequestPrincipal.from_claims(claims)
            if isinstance(claims, dict)
            else RequestPrincipal(
                user_id=user_id, tenant_id=tenant_id,
                permissions=self.default_permissions,
            )
        )
        task, _created = self.submit_task(
            "agent.turn", dict(record.payload or {}), principal=principal,
            idempotency_key=f"schedule:{schedule_id}:manual:{uuid.uuid4().hex}",
        )
        return task

    def submit_occurrence(
        self, schedule: ScheduledTaskRecord, occurrence: ScheduledTaskRunRecord,
    ) -> dict[str, Any]:
        claims = schedule.metadata.get("principal") if isinstance(schedule.metadata, dict) else None
        principal = (
            RequestPrincipal.from_claims(claims)
            if isinstance(claims, dict)
            else RequestPrincipal(
                user_id=schedule.user_id, tenant_id=schedule.tenant_id,
                permissions=self.default_permissions,
            )
        )
        task, _created = self.submit_task(
            "agent.turn", dict(schedule.payload or {}), principal=principal,
            idempotency_key=f"schedule:{schedule.schedule_id}:{occurrence.scheduled_for}",
        )
        return task


__all__ = ["SchedulingService"]
