"""Operational task controls and monitoring projections."""

from __future__ import annotations

import os
from typing import Any, Iterable, Optional


class AdTaskOperationalServicesMixin:
    def get_monitoring_snapshot(
        self,
        *,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Build the read-only operational view used by monitoring."""
        if self.runtime._persistence_store is None:
            raise RuntimeError("monitoring requires a persistence-backed Runtime")
        getter = getattr(
            self.runtime._persistence_store, "get_monitoring_snapshot", None
        )
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
            "execution_mode": (
                self.runtime.get_execution_mode(tenant_id, user_id)
                if tenant_id and user_id else self.runtime.execution_mode
            ),
            "tool_count": len(self.runtime.registry.list_all()),
            "platform_count": len(self.runtime.registry.list_all_namespaces()),
            "task_executor": (
                task_executor.metrics() if task_executor else {"state": "disabled"}
            ),
            "outbox_consumer": (
                outbox_consumer.metrics()
                if outbox_consumer else {"state": "disabled"}
            ),
            "event_repair": (
                self.runtime.event_repair_consumer.metrics()
                if self.runtime.event_repair_consumer
                else {"state": "disabled"}
            ),
            "scheduler": (
                self.runtime.scheduler.metrics()
                if self.runtime.scheduler else {"state": "disabled"}
            ),
        }
        memory_manager = self.runtime.memory_manager
        knowledge_provider = self.runtime.knowledge_provider
        snapshot["instance"]["cache"] = {
            "memory": (
                memory_manager.cache_metrics()
                if memory_manager and callable(
                    getattr(memory_manager, "cache_metrics", None)
                ) else {"state": "disabled"}
            ),
            "knowledge": (
                knowledge_provider.cache_metrics()
                if callable(getattr(knowledge_provider, "cache_metrics", None))
                else {"state": "unavailable"}
            ),
        }
        return snapshot

    def pause_task(
        self, task_id: str, *, user_id: str, tenant_id: str,
    ) -> Optional[dict[str, Any]]:
        if self.runtime.task_executor is None:
            return None
        if self.runtime.task_executor.get(
            task_id, tenant_id=tenant_id, user_id=user_id
        ) is None:
            return None
        record = self.runtime.task_executor.pause(
            task_id, tenant_id=tenant_id, user_id=user_id
        )
        return record.to_dict() if record else None

    def resume_task(
        self, task_id: str, *, user_id: str, tenant_id: str,
    ) -> Optional[dict[str, Any]]:
        if self.runtime.task_executor is None:
            return None
        if self.runtime.task_executor.get(
            task_id, tenant_id=tenant_id, user_id=user_id
        ) is None:
            return None
        record = self.runtime.task_executor.resume(
            task_id, tenant_id=tenant_id, user_id=user_id
        )
        return record.to_dict() if record else None

    def recover_task(
        self,
        task_id: str,
        *,
        user_id: str,
        tenant_id: str,
        recovery_reference: str,
        provider_verified: bool = False,
        permissions: Optional[Iterable[str]] = None,
    ) -> Optional[dict[str, Any]]:
        """Requeue an uncertain task only after verified provider read-back."""
        if self.runtime.task_executor is None:
            return None
        task = self.runtime.task_executor.get(
            task_id, tenant_id=tenant_id, user_id=user_id
        )
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
            task_id,
            recovery_reference=str(recovery_reference),
            tenant_id=tenant_id,
            user_id=user_id,
        )
        return recovered.to_dict() if recovered else None

    def cancel_task(
        self, task_id: str, *, user_id: str, tenant_id: str,
    ) -> Optional[dict[str, Any]]:
        if self.runtime.task_executor is None:
            return None
        if self.runtime.task_executor.get(
            task_id, tenant_id=tenant_id, user_id=user_id
        ) is None:
            return None
        record = self.runtime.task_executor.cancel(
            task_id, tenant_id=tenant_id, user_id=user_id
        )
        return record.to_dict() if record else None


__all__ = ["AdTaskOperationalServicesMixin"]
