"""Durable, provider-neutral asynchronous task execution.

This module owns queueing and lifecycle control only.  It never imports a
Provider client, resolves a channel, or executes a Handler directly.  The
embedding Runtime registers a small, trusted handler for each task kind; the
durable record contains data, not callbacks or executable user code.
"""

from __future__ import annotations

import json
import logging
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Optional

from ..core.task import TaskSubmission

logger = logging.getLogger(__name__)


class TaskExecutorError(RuntimeError):
    """Base error for task lifecycle operations."""


class TaskCapacityError(TaskExecutorError):
    """The bounded in-process queue cannot accept another task."""


class UnknownTaskKind(TaskExecutorError):
    """No trusted handler has been registered for the requested kind."""


TASK_OUTCOME_STATUSES = frozenset({
    "succeeded", "failed", "partially_failed", "awaiting_input",
    "recovery_required", "cancelled",
})


def task_outcome_status(result: Any) -> str:
    """Translate a handler result into a durable task outcome.

    A handler returning normally only means that the handler completed.  It
    does not mean the business operation succeeded.  The explicit
    ``task_status`` field is preferred; the remaining fallbacks keep existing
    handlers safe while they migrate to the result contract.
    """
    if isinstance(result, dict):
        explicit = result.get("task_status")
        if explicit in TASK_OUTCOME_STATUSES:
            return str(explicit)
        signals = result.get("runtime_signals")
        if isinstance(signals, dict) and any(
            bool(signals.get(name))
            for name in ("session_lease_lost", "task_lease_lost")
        ):
            return "recovery_required"
        if result.get("recovery_required") or result.get("provider_state") == "unknown":
            return "recovery_required"
        if result.get("needs_input") or result.get("needs_confirmation"):
            return "awaiting_input"
        raw_status = result.get("status")
        if raw_status in TASK_OUTCOME_STATUSES:
            return str(raw_status)
        result_items = result.get("results")
        if isinstance(result_items, list) and result_items:
            successes = [bool(item.get("success")) for item in result_items if isinstance(item, dict)]
            if successes and not any(successes):
                return "failed"
            if successes and any(successes) and not all(successes):
                return "partially_failed"
        if result.get("success") is False:
            return "failed"
    return "succeeded"


@dataclass
class TaskExecutionContext:
    """Input exposed to one trusted task handler."""

    task_id: str
    kind: str
    payload: dict[str, Any]
    tenant_id: str
    user_id: str
    metadata: dict[str, Any] = field(default_factory=dict)
    cancel_event: threading.Event = field(default_factory=threading.Event)
    lease_lost_event: threading.Event = field(default_factory=threading.Event)
    deadline: Optional[datetime] = None

    def is_cancelled(self) -> bool:
        return self.cancel_event.is_set()

    def is_lease_lost(self) -> bool:
        """Whether this worker no longer owns the durable task lease."""
        return self.lease_lost_event.is_set()

    def remaining_seconds(self) -> Optional[float]:
        if self.deadline is None:
            return None
        return max((self.deadline - datetime.now()).total_seconds(), 0.0)


@dataclass
class _TaskHandle:
    cancel_event: threading.Event
    future: Any


class TaskExecutor:
    """Bounded worker pool backed by a ``PersistenceBackend`` contract."""

    def __init__(
        self,
        store: Any,
        *,
        max_workers: int = 4,
        max_queue: int = 32,
        task_timeout_seconds: float = 900.0,
        lease_seconds: float = 300.0,
        redact: Optional[Callable[[Any], Any]] = None,
        task_record_factory: Optional[Callable[..., Any]] = None,
    ):
        if max_workers <= 0 or max_queue < 0:
            raise ValueError("max_workers must be positive and max_queue cannot be negative")
        if task_timeout_seconds <= 0 or lease_seconds <= 0:
            raise ValueError("task and lease timeouts must be positive")
        self.store = store
        self.max_workers = int(max_workers)
        self.max_queue = int(max_queue)
        self.task_timeout_seconds = float(task_timeout_seconds)
        self.lease_seconds = float(lease_seconds)
        self._redact = redact or (lambda value: value)
        # The default value is generic. Applications may inject a richer
        # persistence record without coupling this queue to that model.
        self._task_record_factory = task_record_factory or TaskSubmission
        self._capacity = threading.BoundedSemaphore(self.max_workers + self.max_queue)
        self._pool = ThreadPoolExecutor(
            max_workers=self.max_workers, thread_name_prefix="ad-agent-task"
        )
        self._handlers: dict[str, Callable[[TaskExecutionContext], Any]] = {}
        self._handles: dict[str, _TaskHandle] = {}
        self._lock = threading.RLock()
        self._closed = False
        self._worker_id = f"task-worker:{uuid.uuid4()}"
        self._worker_heartbeat_stop = threading.Event()
        self._worker_heartbeat_thread: Optional[threading.Thread] = None

    def register_handler(
        self, kind: str, handler: Callable[[TaskExecutionContext], Any]
    ) -> None:
        kind = str(kind or "").strip()
        if not kind or not callable(handler):
            raise ValueError("task kind and callable handler are required")
        with self._lock:
            if self._closed:
                raise TaskExecutorError("task executor is closed")
            self._handlers[kind] = handler

    def registered_kinds(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(sorted(self._handlers))

    def metrics(self) -> dict[str, Any]:
        """Return process-local worker metrics without exposing task payloads."""
        with self._lock:
            handles = len(self._handles)
            closed = self._closed
            worker_id = self._worker_id
            kinds = tuple(sorted(self._handlers))
        try:
            internal_queue = max(0, int(self._pool._work_queue.qsize()))
        except (AttributeError, TypeError, ValueError):  # pragma: no cover - implementation detail
            internal_queue = None
        return {
            "worker_id": worker_id,
            "state": "closed" if closed else "running",
            "max_workers": self.max_workers,
            "max_queue": self.max_queue,
            "in_process_tasks": handles,
            "in_process_queued": internal_queue,
            "admission_capacity": self.max_workers + self.max_queue,
            "registered_kinds": list(kinds),
        }

    @staticmethod
    def _now() -> str:
        return datetime.now().isoformat()

    def submit(
        self,
        kind: str,
        payload: dict[str, Any],
        *,
        tenant_id: str,
        user_id: str,
        idempotency_key: Optional[str] = None,
        workflow_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> tuple[Any, bool]:
        """Persist and schedule a task. Returns ``(record, created)``."""
        kind = str(kind or "").strip()
        if kind not in self.registered_kinds():
            raise UnknownTaskKind(kind)
        if not isinstance(payload, dict):
            raise ValueError("task payload must be an object")
        if self._closed:
            raise TaskExecutorError("task executor is closed")
        if idempotency_key:
            existing = self.store.find_task_by_idempotency(
                str(tenant_id), str(user_id), str(idempotency_key)
            )
            if existing is not None:
                return existing, False
        if not self._capacity.acquire(blocking=False):
            raise TaskCapacityError("task queue is full")
        now = self._now()
        record = self._task_record_factory(
            task_id=str(uuid.uuid4()), tenant_id=str(tenant_id), user_id=str(user_id),
            kind=kind, status="queued", payload=payload,
            idempotency_key=str(idempotency_key) if idempotency_key else None,
            workflow_id=str(workflow_id) if workflow_id else None,
            metadata=metadata or {}, created_at=now, updated_at=now,
        )
        try:
            self.store.create_task(record)
        except Exception:
            self._capacity.release()
            if idempotency_key:
                existing = self.store.find_task_by_idempotency(
                    str(tenant_id), str(user_id), str(idempotency_key)
                )
                if existing is not None:
                    return existing, False
            raise
        try:
            if not self._schedule(record.task_id, slot_reserved=True):
                raise TaskExecutorError("task could not be scheduled")
        except Exception as exc:
            self.store.update_task(
                record.task_id, "failed", error=self._safe_error(exc),
                expected_statuses=["queued"],
            )
            self._capacity.release()
            raise
        return self.store.get_task(record.task_id) or record, True

    def start(self) -> int:
        """Recover stale workers and schedule durable queued records."""
        register = getattr(self.store, "register_worker", None)
        if callable(register):
            register(
                self._worker_id, "task_executor",
                metadata={"pid": __import__("os").getpid(), "max_workers": self.max_workers},
                lease_seconds=min(max(self.lease_seconds, 10.0), 60.0),
            )
            self._start_worker_heartbeat()
        recovered = self.store.recover_stale_tasks(self.lease_seconds)
        if recovered:
            logger.warning("marked %s stale Agent tasks for recovery", recovered)
        scheduled = 0
        for record in self.store.list_tasks(statuses=["queued"], limit=self.max_workers + self.max_queue):
            if self._schedule(record.task_id):
                scheduled += 1
        return scheduled

    def _start_worker_heartbeat(self) -> None:
        if self._worker_heartbeat_thread and self._worker_heartbeat_thread.is_alive():
            return
        self._worker_heartbeat_stop.clear()
        self._worker_heartbeat_thread = threading.Thread(
            target=self._heartbeat_worker, name="ad-agent-worker-heartbeat", daemon=True,
        )
        self._worker_heartbeat_thread.start()

    def _heartbeat_worker(self) -> None:
        heartbeat = getattr(self.store, "heartbeat_worker", None)
        if not callable(heartbeat):
            return
        interval = min(max(self.lease_seconds / 3.0, 2.0), 15.0)
        while not self._worker_heartbeat_stop.wait(interval):
            if getattr(self.store, "is_closed", False):
                return
            try:
                if not heartbeat(
                    self._worker_id,
                    lease_seconds=min(max(self.lease_seconds, 10.0), 60.0),
                ):
                    return
            except Exception:
                logger.warning("task worker heartbeat failed", exc_info=True)

    def _schedule(self, task_id: str, *, slot_reserved: bool = False) -> bool:
        with self._lock:
            if self._closed or task_id in self._handles:
                return False
            # ``submit`` acquires the admission slot before persisting. Startup
            # recovery and resume acquire it at scheduling time.
            if not slot_reserved and not self._capacity.acquire(blocking=False):
                return False
            cancel_event = threading.Event()
            try:
                future = self._pool.submit(self._run, str(task_id), cancel_event)
            except Exception:
                if not slot_reserved:
                    self._capacity.release()
                raise
            self._handles[str(task_id)] = _TaskHandle(cancel_event, future)
            return True

    def _run(self, task_id: str, cancel_event: threading.Event) -> None:
        try:
            record = self.store.claim_task(task_id, self._worker_id, self.lease_seconds)
            if record is None:
                return
            with self._lock:
                handler = self._handlers.get(record.kind)
            if handler is None:
                self.store.update_task(
                    task_id, "failed", error="task handler is no longer registered",
                    expected_statuses=["running"],
                )
                return
            deadline = datetime.now() + timedelta(seconds=self.task_timeout_seconds)
            context = TaskExecutionContext(
                task_id=record.task_id, kind=record.kind, payload=record.payload,
                tenant_id=record.tenant_id, user_id=record.user_id,
                metadata=record.metadata, cancel_event=cancel_event, deadline=deadline,
            )
            current_before_run = self.store.get_task(task_id)
            if current_before_run and current_before_run.status == "cancelling":
                cancel_event.set()
            heartbeat_stop = threading.Event()
            deadline_event = threading.Event()

            # Python cannot safely kill a provider call running in a worker
            # thread. A watchdog still makes the deadline observable to the
            # handler and ensures a late return is recorded as uncertain.
            def expire() -> None:
                deadline_event.set()
                cancel_event.set()

            deadline_timer = threading.Timer(
                self.task_timeout_seconds, expire
            )
            deadline_timer.daemon = True
            deadline_timer.start()

            def heartbeat() -> None:
                interval = min(max(self.lease_seconds / 3.0, 0.5), 10.0)
                while not heartbeat_stop.wait(interval):
                    try:
                        owned = self.store.heartbeat_task(
                            task_id, self._worker_id, self.lease_seconds
                        )
                    except Exception:
                        # A backend error means this worker can no longer
                        # prove ownership. Stop the handler cooperatively and
                        # let the task finish in recovery_required rather than
                        # risking a second worker running beside it.
                        context.lease_lost_event.set()
                        cancel_event.set()
                        logger.warning("task lease heartbeat failed", exc_info=True)
                        return
                    if not owned:
                        context.lease_lost_event.set()
                        cancel_event.set()
                        return

            heartbeat_thread = threading.Thread(
                target=heartbeat, name="ad-agent-task-heartbeat", daemon=True
            )
            heartbeat_thread.start()
            try:
                result = handler(context)
                safe_result = self._safe_result(result)
                current = self.store.get_task(task_id)
                cancellation_requested = bool(
                    current and current.status == "cancelling"
                ) or (cancel_event.is_set() and not deadline_event.is_set())
                deadline_exceeded = deadline_event.is_set() or context.remaining_seconds() == 0.0
                lease_lost = context.is_lease_lost() or bool(
                    isinstance(safe_result, dict)
                    and (safe_result.get("runtime_signals") or {}).get("task_lease_lost")
                )
                workflow_id = (
                    safe_result.get("workflow_id")
                    if isinstance(safe_result, dict) else None
                )
                if lease_lost:
                    self.store.update_task(
                        task_id,
                        "recovery_required",
                        result=safe_result,
                        workflow_id=workflow_id,
                        error="任务执行租约丢失；外部副作用状态未知，请先核对后再处理",
                        metadata={"lease_lost": True, "provider_state": "unknown"},
                        expected_statuses=["running", "cancelling"],
                    )
                elif cancellation_requested:
                    self.store.update_task(
                        task_id, "cancelled", result=safe_result,
                        workflow_id=workflow_id,
                        metadata={"completed_after_cancellation": True},
                        expected_statuses=["running", "cancelling"],
                    )
                elif deadline_exceeded:
                    # The handler may have completed an external write before
                    # returning. Do not report a late result as success; make
                    # recovery/reconciliation explicit to the operator.
                    self.store.update_task(
                        task_id,
                        "recovery_required",
                        result=safe_result,
                        workflow_id=workflow_id,
                        error=(
                            "任务超过执行时限；外部副作用状态未知，"
                            "请先核对工作流后再处理"
                        ),
                        metadata={
                            "deadline_exceeded": True,
                            "provider_state": "unknown",
                        },
                        expected_statuses=["running"],
                    )
                else:
                    outcome_status = task_outcome_status(safe_result)
                    outcome_error = None
                    if outcome_status in {"failed", "partially_failed"}:
                        if isinstance(safe_result, dict):
                            outcome_error = safe_result.get("error") or safe_result.get("reply")
                        outcome_error = str(outcome_error or "Agent turn reported an unsuccessful outcome")[:1000]
                    outcome_metadata = (
                        {"handler_outcome": outcome_status}
                        if outcome_status != "succeeded" else None
                    )
                    self.store.update_task(
                        task_id, outcome_status, result=safe_result,
                        error=outcome_error, metadata=outcome_metadata,
                        workflow_id=workflow_id,
                        expected_statuses=["running"],
                    )
            except Exception as exc:
                current = self.store.get_task(task_id)
                cancellation_requested = bool(
                    current and current.status == "cancelling"
                ) or (cancel_event.is_set() and not deadline_event.is_set())
                deadline_exceeded = deadline_event.is_set() or context.remaining_seconds() == 0.0
                status = (
                    "recovery_required" if context.is_lease_lost()
                    else "cancelled" if cancellation_requested
                    else "recovery_required" if deadline_exceeded
                    else "failed"
                )
                self.store.update_task(
                    task_id, status,
                    error=self._safe_error(exc),
                    metadata=(
                        {"deadline_exceeded": True, "provider_state": "unknown"}
                        if deadline_exceeded else None
                    ),
                    expected_statuses=["running", "cancelling"],
                )
            finally:
                deadline_timer.cancel()
                heartbeat_stop.set()
                heartbeat_thread.join(timeout=0.1)
        finally:
            with self._lock:
                self._handles.pop(task_id, None)
            self._capacity.release()

    def get(
        self, task_id: str, *, tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Optional[Any]:
        return self.store.get_task(task_id, tenant_id=tenant_id, user_id=user_id)

    def list(
        self, *, tenant_id: Optional[str] = None, user_id: Optional[str] = None,
        statuses: Optional[list[str]] = None, limit: int = 50,
    ) -> list[Any]:
        return self.store.list_tasks(tenant_id, user_id, statuses, limit)

    def cancel(
        self, task_id: str, *, tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Optional[Any]:
        record = self.store.cancel_task(
            task_id, tenant_id=tenant_id, user_id=user_id,
        )
        if record and record.status == "cancelling":
            with self._lock:
                handle = self._handles.get(task_id)
                if handle:
                    handle.cancel_event.set()
        return record

    def pause(
        self, task_id: str, *, tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Optional[Any]:
        return self.store.pause_task(
            task_id, tenant_id=tenant_id, user_id=user_id,
        )

    def resume(
        self, task_id: str, *, tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Optional[Any]:
        record = self.store.resume_task(
            task_id, tenant_id=tenant_id, user_id=user_id,
        )
        if record is None or record.status != "queued":
            return record
        if not self._schedule(record.task_id):
            self.store.update_task(
                record.task_id, "paused", error="task queue is full",
                expected_statuses=["queued"],
            )
            return self.store.get_task(
                record.task_id, tenant_id=tenant_id, user_id=user_id,
            )
        return self.store.get_task(
            record.task_id, tenant_id=tenant_id, user_id=user_id,
        ) or record

    def requeue_recovery(
        self, task_id: str, *, recovery_reference: str,
        tenant_id: Optional[str] = None, user_id: Optional[str] = None,
    ) -> Optional[Any]:
        """Requeue only after an explicit, externally verified recovery."""
        requeue = getattr(self.store, "requeue_recovery_task", None)
        if not callable(requeue):
            return None
        record = requeue(
            str(task_id), recovery_reference=str(recovery_reference),
            tenant_id=tenant_id, user_id=user_id,
        )
        if record is None or record.status != "queued":
            return record
        if not self._schedule(record.task_id):
            self.store.update_task(
                record.task_id, "paused", error="task queue is full",
                expected_statuses=["queued"],
            )
            return self.store.get_task(
                record.task_id, tenant_id=tenant_id, user_id=user_id,
            )
        return self.store.get_task(
            record.task_id, tenant_id=tenant_id, user_id=user_id,
        ) or record

    def shutdown(self, wait: bool = False) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            for handle in self._handles.values():
                handle.cancel_event.set()
        self._worker_heartbeat_stop.set()
        heartbeat_thread = self._worker_heartbeat_thread
        if heartbeat_thread:
            heartbeat_thread.join(timeout=0.5)
        unregister = getattr(self.store, "unregister_worker", None)
        if callable(unregister):
            try:
                unregister(self._worker_id)
            except Exception:
                logger.warning("failed to unregister task worker", exc_info=True)
        self._pool.shutdown(wait=wait, cancel_futures=True)

    def _safe_error(self, error: Exception) -> str:
        try:
            return str(self._redact(str(error)))[:4000]
        except Exception:
            return type(error).__name__

    def _safe_result(self, value: Any) -> Any:
        try:
            safe = self._redact(value)
            encoded = json.dumps(safe, ensure_ascii=False, default=str)
            if len(encoded.encode("utf-8")) > 2_000_000:
                return {"truncated": True, "reason": "task result exceeds output limit"}
            return json.loads(encoded)
        except Exception:
            return {"truncated": True, "reason": "task result is not serializable"}
