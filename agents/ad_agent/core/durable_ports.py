"""Small durable-store ports used by reusable Runtime infrastructure.

The application persistence facade intentionally has a larger contract because
it serves the advertising control plane.  Queue, schedule and outbox workers
must not depend on that facade wholesale: each worker only needs the narrow
durable operations below.  Structural typing keeps SQLite/MySQL adapters
interchangeable without importing either backend into Core.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional, Protocol


class WorkerLeaseStore(Protocol):
    """Optional cross-process worker liveness port."""

    def register_worker(
        self, worker_id: str, worker_kind: str, *,
        metadata: Optional[Mapping[str, Any]] = None,
        lease_seconds: float = 30.0,
    ) -> None: ...

    def heartbeat_worker(self, worker_id: str, *, lease_seconds: float = 30.0) -> bool: ...

    def unregister_worker(self, worker_id: str) -> bool: ...


class TaskQueueStore(WorkerLeaseStore, Protocol):
    """Durable operations required by the generic task executor."""

    def create_task(self, record: Any) -> Any: ...
    def get_task(
        self, task_id: str, tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Optional[Any]: ...
    def find_task_by_idempotency(
        self, tenant_id: str, user_id: str, idempotency_key: str,
    ) -> Optional[Any]: ...
    def list_tasks(
        self, tenant_id: Optional[str] = None, user_id: Optional[str] = None,
        statuses: Optional[list[str]] = None, limit: int = 50,
    ) -> list[Any]: ...
    def claim_task(self, task_id: str, lease_owner: str, lease_seconds: float = 300.0) -> Optional[Any]: ...
    def heartbeat_task(self, task_id: str, lease_owner: str, lease_seconds: float = 300.0) -> bool: ...
    def update_task(
        self, task_id: str, status: str, *, result: Optional[dict] = None,
        error: Optional[str] = None, metadata: Optional[dict] = None,
        workflow_id: Optional[str] = None, expected_statuses: Optional[list[str]] = None,
    ) -> bool: ...
    def recover_stale_tasks(self, stale_after_seconds: float = 300.0) -> int: ...
    def pause_task(self, task_id: str, tenant_id: Optional[str] = None, user_id: Optional[str] = None) -> Optional[Any]: ...
    def resume_task(self, task_id: str, tenant_id: Optional[str] = None, user_id: Optional[str] = None) -> Optional[Any]: ...
    def cancel_task(self, task_id: str, tenant_id: Optional[str] = None, user_id: Optional[str] = None) -> Optional[Any]: ...
    def requeue_recovery_task(
        self, task_id: str, *, recovery_reference: str,
        tenant_id: Optional[str] = None, user_id: Optional[str] = None,
    ) -> Optional[Any]: ...


class OutboxStore(WorkerLeaseStore, Protocol):
    """Durable operations required by the generic outbox consumer."""

    def claim_outbox_events(self, limit: int = 20, consumer_id: Optional[str] = None) -> list[Any]: ...
    def mark_outbox_delivered(self, event_id: str, consumer_id: Optional[str] = None) -> bool: ...
    def mark_outbox_retry(
        self, event_id: str, next_retry_at: str, error: Optional[str] = None,
        consumer_id: Optional[str] = None,
    ) -> bool: ...
    def mark_outbox_failed(
        self, event_id: str, error: Optional[str] = None,
        consumer_id: Optional[str] = None,
    ) -> bool: ...


class ScheduleStore(WorkerLeaseStore, Protocol):
    """Durable operations required by the recurring schedule worker."""

    def claim_due_scheduled_tasks(
        self, now: str, lease_owner: str, lease_seconds: float = 60.0,
        limit: int = 20,
    ) -> list[tuple[Any, Any]]: ...
    def attach_scheduled_task_run(
        self, schedule_run_id: str, task_id: str, status: str = "queued",
        lease_owner: Optional[str] = None,
    ) -> bool: ...
    def advance_scheduled_task(
        self, schedule_id: str, expected_next_run_at: str, next_run_at: str,
        lease_owner: Optional[str] = None,
    ) -> bool: ...
    def update_scheduled_task_run(
        self, schedule_run_id: str, status: str, *, task_id: Optional[str] = None,
        started_at: Optional[str] = None, finished_at: Optional[str] = None,
        error: Optional[str] = None, result: Optional[dict] = None,
        lease_owner: Optional[str] = None,
    ) -> bool: ...
    def list_scheduled_task_runs(
        self, schedule_id: Optional[str] = None, tenant_id: Optional[str] = None,
        user_id: Optional[str] = None, statuses: Optional[list[str]] = None,
        limit: int = 100,
    ) -> list[Any]: ...
    def get_task(self, task_id: str, tenant_id: Optional[str] = None, user_id: Optional[str] = None) -> Optional[Any]: ...


__all__ = ["WorkerLeaseStore", "TaskQueueStore", "OutboxStore", "ScheduleStore"]
