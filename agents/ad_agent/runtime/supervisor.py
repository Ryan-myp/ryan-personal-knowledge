"""Generic lifecycle supervisor for Runtime-owned durable workers."""

from __future__ import annotations

from typing import Any, Callable, Mapping, Optional

from .event_repair import ExecutionEventRepairConsumer
from .outbox import OutboxConsumer
from .scheduler import SchedulerService
from .task_executor import TaskExecutor


class RuntimeSupervisor:
    """Compose and stop queue/lease workers without domain knowledge."""

    def __init__(
        self,
        *,
        store: Any,
        outbox_delivery: Optional[Callable[[Any], None]],
        scheduled_submitter: Optional[Callable[..., Any]],
        task_handlers: Mapping[str, Callable[..., Any]],
        redact: Callable[[Any], Any],
        max_task_workers: int,
        max_task_queue: int,
        task_timeout_seconds: float,
        task_lease_seconds: float,
        task_queue_poll_interval: float,
        outbox_poll_interval: float,
        outbox_max_attempts: int = 10,
        start_background_workers: bool = True,
        create_background_workers: Optional[bool] = None,
    ) -> None:
        self.store = store
        self.outbox_consumer = None
        self.event_repair_consumer = None
        self.task_executor = None
        self.scheduler = None
        if store is None:
            return
        # ``start_background_workers=False`` is used by deterministic
        # in-process embeddings. Do not create daemon consumers in that mode;
        # the durable task object remains available for explicit test driving.
        # Creation and startup are separate lifecycle phases. The application
        # assembly uses this to publish every callback target before a worker
        # can recover durable work; direct callers retain the old behavior by
        # defaulting creation to the startup flag.
        create_workers = (
            bool(start_background_workers)
            if create_background_workers is None
            else bool(create_background_workers)
        )
        if create_workers:
            if outbox_delivery is not None:
                self.outbox_consumer = OutboxConsumer(
                    store, outbox_delivery, poll_interval=outbox_poll_interval,
                    max_attempts=outbox_max_attempts,
                )
            elif callable(getattr(store, "claim_outbox_events", None)):
                self.outbox_consumer = OutboxConsumer(
                    store, self._default_delivery, poll_interval=outbox_poll_interval,
                    max_attempts=outbox_max_attempts,
                )
            if callable(getattr(store, "enqueue_execution_event_repair", None)):
                self.event_repair_consumer = ExecutionEventRepairConsumer(store)
        self.task_executor = TaskExecutor(
            store,
            max_workers=max_task_workers,
            max_queue=max_task_queue,
            task_timeout_seconds=task_timeout_seconds,
            lease_seconds=task_lease_seconds,
            queue_poll_interval=task_queue_poll_interval,
            redact=redact,
        )
        for kind, handler in task_handlers.items():
            self.task_executor.register_handler(kind, handler)
        self.scheduler = (
            SchedulerService(store, scheduled_submitter)
            if callable(scheduled_submitter) else None
        )
        if start_background_workers:
            self.start()

    @staticmethod
    def _default_delivery(event: Any) -> None:
        # Applications can provide a sink; the default intentionally does not
        # inspect or log payload data.
        return None

    def start(self) -> None:
        if self.outbox_consumer is not None:
            self.outbox_consumer.start()
        if self.event_repair_consumer is not None:
            self.event_repair_consumer.start()
        if self.task_executor is not None:
            self.task_executor.start()
        if self.scheduler is not None:
            self.scheduler.start()

    def health(self) -> dict[str, Any]:
        """Return provider-neutral worker health for readiness and monitoring.

        This is deliberately an infrastructure view. It reports lifecycle
        state and durable backend health, but never inspects task payloads or
        knows which application owns a task kind.
        """
        backend = {"status": "disabled"}
        get_backend_health = getattr(self.store, "get_backend_health", None)
        if callable(get_backend_health):
            try:
                backend = dict(get_backend_health())
            except Exception as exc:
                backend = {"status": "unhealthy", "error": type(exc).__name__}

        components: dict[str, dict[str, Any]] = {}
        for name, worker in (
            ("task_executor", self.task_executor),
            ("outbox_consumer", self.outbox_consumer),
            ("event_repair", self.event_repair_consumer),
            ("scheduler", self.scheduler),
        ):
            if worker is None:
                components[name] = {"state": "disabled"}
                continue
            metrics = getattr(worker, "metrics", None)
            try:
                data = dict(metrics()) if callable(metrics) else {}
            except Exception as exc:
                data = {"state": "unhealthy", "error": type(exc).__name__}
            components[name] = {"state": str(data.get("state") or "unknown"), **data}

        required = [
            item for item in components.values()
            if item["state"] != "disabled"
        ]
        worker_ready = all(item.get("state") == "running" for item in required)
        backend_ready = backend.get("status") in {"healthy", "disabled"}
        status = "healthy" if backend_ready and worker_ready else "unhealthy"
        return {
            "status": status,
            "backend": backend,
            "components": components,
        }

    def close(self, *, wait: bool = False) -> None:
        if self.outbox_consumer is not None:
            self.outbox_consumer.stop()
        if self.event_repair_consumer is not None:
            self.event_repair_consumer.stop()
        if self.scheduler is not None:
            self.scheduler.stop(wait=wait)
        if self.task_executor is not None:
            self.task_executor.shutdown(wait=wait)


__all__ = ["RuntimeSupervisor"]
