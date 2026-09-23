"""Application task and schedule control services."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Optional

from ..domain.ad.auth import RequestPrincipal
from ..knowledge_ingest import KnowledgeIngestService
from ..knowledge_management import ManagedKnowledgeManager
from ..persistence.models import ScheduledTaskRecord, ScheduledTaskRunRecord
from .ad_task_operational_services import AdTaskOperationalServicesMixin
from .task_executor import TaskExecutionContext


class AdTaskServices(AdTaskOperationalServicesMixin):
    def __init__(self, runtime: Any) -> None:
        self.runtime = runtime

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
        """Submit a task that re-enters the normal Runtime turn loop."""
        if self.runtime.task_executor is None:
            raise RuntimeError("durable task executor is not configured")
        effective_user = principal.user_id if principal is not None else str(user_id)
        effective_tenant = (
            principal.tenant_id if principal is not None else str(tenant_id or "default")
        )
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
            "creation_blueprint_version", "creation_template_id",
            "execution_mode",
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
            "creation_template_id": payload.get("creation_template_id"),
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
                user_id=effective_user,
                tenant_id=effective_tenant,
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

    def submit_knowledge_ingest(
        self, source_id: str, *, principal: RequestPrincipal,
    ) -> tuple[dict[str, Any], bool]:
        """Queue raw Wiki ingestion without exposing arbitrary task payloads."""
        if self.runtime.task_executor is None:
            raise RuntimeError("durable task executor is not configured")
        source = self.runtime.persistence_store.get_raw_knowledge_source(
            str(source_id), tenant_id=principal.tenant_id
        )
        if not source:
            raise ValueError("raw 文档不存在或无权访问")
        if source.status == "draft_ready":
            if source.ingest_task_id:
                existing_task = self.runtime.persistence_store.get_task(
                    source.ingest_task_id, tenant_id=principal.tenant_id
                )
                if existing_task is not None:
                    return existing_task.to_dict(), False
            raise ValueError("raw 文档已完成 ingest，不能重复排队")
        if source.ingest_task_id and source.status != "failed":
            existing_task = self.runtime.persistence_store.get_task(
                source.ingest_task_id, tenant_id=principal.tenant_id
            )
            if existing_task is not None and existing_task.status not in {
                "failed", "recovery_required", "cancelled",
            }:
                return existing_task.to_dict(), False
            if source.status == "ingesting" and existing_task is None:
                raise ValueError("raw 文档正在 ingest，任务状态暂不可用")
        attempt = max(int(source.ingest_attempts or 0) + 1, 1)
        record, created = self.runtime.task_executor.submit(
            "knowledge.ingest",
            {"source_id": str(source.source_id)},
            tenant_id=principal.tenant_id,
            user_id=principal.user_id,
            idempotency_key=(
                f"knowledge-ingest:{principal.tenant_id}:{source.source_id}:"
                f"attempt-{attempt}"
            ),
            metadata={
                "principal": principal.to_safe_dict(),
                "submission_source": "knowledge",
            },
        )
        self.runtime.persistence_store.update_raw_knowledge_source(
            source.source_id,
            tenant_id=principal.tenant_id,
            data={
                "ingest_task_id": record.task_id,
                "updated_at": datetime.now().isoformat(),
            },
        )
        return record.to_dict(), created

    def create_schedule(self, **kwargs: Any) -> dict[str, Any]:
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
        if context.is_cancelled():
            return {"success": False, "cancelled": True}
        claims = context.metadata.get("principal")
        principal = (
            RequestPrincipal.from_claims(claims)
            if isinstance(claims, dict) else None
        )
        payload = context.payload
        return self.runtime.run(
            user_input=str(payload.get("user_input") or ""),
            session_id=payload.get("session_id"),
            account_id=payload.get("account_id"),
            platform_params=payload.get("platform_params"),
            creation_blueprint_id=payload.get("creation_blueprint_id"),
            creation_blueprint_version=payload.get("creation_blueprint_version"),
            creation_template_id=payload.get("creation_template_id"),
            execution_mode=payload.get("execution_mode"),
            confirmed=False,
            confirmation_payload=None,
            principal=principal,
            user_id=context.user_id,
            tenant_id=context.tenant_id,
            cancellation_event=context.cancel_event,
            task_id=context.task_id,
        )

    def execute_knowledge_ingest_task(
        self, context: TaskExecutionContext
    ) -> dict[str, Any]:
        claims = context.metadata.get("principal")
        principal = (
            RequestPrincipal.from_claims(claims)
            if isinstance(claims, dict) else None
        )
        source_id = str(context.payload.get("source_id") or "")
        if not source_id:
            raise ValueError("knowledge.ingest requires source_id")
        if principal is None:
            raise PermissionError("knowledge ingest requires authenticated principal")
        service = KnowledgeIngestService(
            store=self.runtime.persistence_store,
            llm=self.runtime._llm,
            knowledge_manager=ManagedKnowledgeManager(
                self.runtime.persistence_store
            ),
            knowledge_provider=self.runtime.knowledge_provider,
        )
        return service.ingest(
            source_id,
            tenant_id=principal.tenant_id,
            created_by=principal.user_id,
            task_id=context.task_id,
        )

    def get_task(
        self,
        task_id: str,
        *,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        if self.runtime.task_executor is None:
            return None
        record = self.runtime.task_executor.get(
            task_id, tenant_id=tenant_id, user_id=user_id
        )
        return record.to_dict() if record else None

    def list_tasks(
        self,
        *,
        user_id: str,
        tenant_id: str,
        statuses: Optional[list[str]] = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        if self.runtime.task_executor is None:
            return []
        return [
            record.to_dict()
            for record in self.runtime.task_executor.list(
                tenant_id=tenant_id,
                user_id=user_id,
                statuses=statuses,
                limit=limit,
            )
        ]


__all__ = ["AdTaskServices"]
