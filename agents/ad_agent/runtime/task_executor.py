"""Durable, provider-neutral asynchronous task execution.

This module owns queueing and lifecycle control only.  It never imports an
external-system client, resolves an integration, or executes a Handler directly.  The
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

from ..core.durable_ports import TaskQueueStore

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
        if result.get("recovery_required") or result.get("effect_state") == "unknown":
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
        store: TaskQueueStore,
        *,
        max_workers: int = 4,
        max_queue: int = 32,
        task_timeout_seconds: float = 900.0,
        lease_seconds: float = 300.0,
        queue_poll_interval: float = 0.5,
        redact: Optional[Callable[[Any], Any]] = None,
        task_record_factory: Optional[Callable[..., Any]] = None,
        before_execute: Optional[Callable[[TaskExecutionContext], None]] = None,
    ):
        if max_workers <= 0 or max_queue < 0:
            raise ValueError("max_workers must be positive and max_queue cannot be negative")
        if task_timeout_seconds <= 0 or lease_seconds <= 0:
            raise ValueError("task and lease timeouts must be positive")
        if queue_poll_interval <= 0:
            raise ValueError("queue_poll_interval must be positive")
        self.store = store
        self.max_workers = int(max_workers)
        self.max_queue = int(max_queue)
        self.task_timeout_seconds = float(task_timeout_seconds)
        self.lease_seconds = float(lease_seconds)
        self.queue_poll_interval = max(0.1, float(queue_poll_interval))
        self._redact = redact or (lambda value: value)
        # The default value is generic. Applications may inject a richer
        # persistence record without coupling this queue to that model.
        self._task_record_factory = task_record_factory or TaskSubmission
        self._capacity = threading.BoundedSemaphore(self.max_workers + self.max_queue)
        self._pool = ThreadPoolExecutor(
            max_workers=self.max_workers, thread_name_prefix="ad-agent-task"
        )
        self._handlers: dict[str, Callable[[TaskExecutionContext], Any]] = {}
        self._before_execute = before_execute
        self._handles: dict[str, _TaskHandle] = {}
        self._lock = threading.RLock()
        self._closed = False
        self._started = False
        self._worker_id = f"task-worker:{uuid.uuid4()}"
        self._worker_heartbeat_stop = threading.Event()
        self._worker_heartbeat_thread: Optional[threading.Thread] = None
        self._queue_poller_stop = threading.Event()
        self._queue_poller_wakeup = threading.Event()
        self._queue_poller_thread: Optional[threading.Thread] = None
        self._queue_poll_total = 0
        self._queue_poll_errors = 0
        self._last_queue_poll_at: Optional[str] = None
        self._queue_rejection_total = 0
        self._admitted_slots = 0

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

    def set_before_execute_hook(
        self, hook: Optional[Callable[[TaskExecutionContext], None]]
    ) -> None:
        """Install an embedding-owned hook before a claimed task runs.

        The queue remains provider-neutral. An embedding can use this seam to
        refresh tenant-scoped extension registries before a recovered task
        re-enters the Runtime without teaching the queue about MCP or Skills.
        """
        with self._lock:
            self._before_execute = hook

    def registered_kinds(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(sorted(self._handlers))

    def metrics(self) -> dict[str, Any]:
        """Return process-local worker metrics without exposing task payloads."""
        with self._lock:
            handles = len(self._handles)
            closed = self._closed
            started = self._started
            worker_id = self._worker_id
            kinds = tuple(sorted(self._handlers))
            admitted_slots = self._admitted_slots
            queue_rejections = self._queue_rejection_total
        try:
            internal_queue = max(0, int(self._pool._work_queue.qsize()))
        except (AttributeError, TypeError, ValueError):  # pragma: no cover - implementation detail
            internal_queue = None
        return {
            "worker_id": worker_id,
            "state": "closed" if closed else "running" if started else "stopped",
            "max_workers": self.max_workers,
            "max_queue": self.max_queue,
            "in_process_tasks": handles,
            "in_process_queued": internal_queue,
            "admission_capacity": self.max_workers + self.max_queue,
            "admitted_slots": admitted_slots,
            "capacity_remaining": max(
                0, self.max_workers + self.max_queue - admitted_slots
            ),
            "queue_rejection_total": queue_rejections,
            "queue_poll_interval_seconds": self.queue_poll_interval,
            "queue_poller": {
                "state": (
                    "running" if self._queue_poller_thread
                    and self._queue_poller_thread.is_alive() else "stopped"
                ),
                "refill_total": self._queue_poll_total,
                "error_total": self._queue_poll_errors,
                "last_poll_at": self._last_queue_poll_at,
            },
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
        with self._lock:
            if self._closed:
                raise TaskExecutorError("task executor is closed")
        if idempotency_key:
            existing = self.store.find_task_by_idempotency(
                str(tenant_id), str(user_id), str(idempotency_key)
            )
            if existing is not None:
                return existing, False
        if not self._capacity.acquire(blocking=False):
            with self._lock:
                self._queue_rejection_total += 1
            raise TaskCapacityError("task queue is full")
        with self._lock:
            self._admitted_slots += 1
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
            with self._lock:
                self._admitted_slots = max(0, self._admitted_slots - 1)
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
            # Shutdown is a lifecycle event, not a task failure. Keep the
            # durable row queued so another process can claim it after a
            # restart; only actual submission failures are terminal here.
            with self._lock:
                closing = self._closed
            if not closing:
                self.store.update_task(
                    record.task_id, "failed", error=self._safe_error(exc),
                    expected_statuses=["queued"],
                )
            self._capacity.release()
            with self._lock:
                self._admitted_slots = max(0, self._admitted_slots - 1)
            raise
        return self.store.get_task(record.task_id) or record, True

    def start(self) -> int:
        """Recover stale workers and schedule durable queued records."""
        with self._lock:
            if self._closed:
                raise TaskExecutorError("task executor is closed")
            if self._started:
                return 0
            self._started = True
        register = getattr(self.store, "register_worker", None)
        registered = False
        try:
            if callable(register):
                register(
                    self._worker_id, "task_executor",
                    metadata={"pid": __import__("os").getpid(), "max_workers": self.max_workers},
                    lease_seconds=min(max(self.lease_seconds, 10.0), 60.0),
                )
                registered = True
                self._start_worker_heartbeat()
            recovered = self.store.recover_stale_tasks(self.lease_seconds)
            if recovered:
                logger.warning("marked %s stale Agent tasks for recovery", recovered)
            scheduled = self._refill_queue()
            self._start_queue_poller()
            return scheduled
        except Exception:
            # ``start`` is retryable after a transient database or schema
            # failure. Do not leave an in-memory started flag or worker lease
            # behind, otherwise a later health-recovery attempt becomes a
            # silent no-op and the next process sees a false live worker.
            self._worker_heartbeat_stop.set()
            heartbeat_thread = self._worker_heartbeat_thread
            if heartbeat_thread:
                heartbeat_thread.join(timeout=0.5)
            self._worker_heartbeat_thread = None
            if registered and callable(getattr(self.store, "unregister_worker", None)):
                try:
                    self.store.unregister_worker(self._worker_id)
                except Exception:
                    logger.warning("failed to roll back task worker registration", exc_info=True)
            with self._lock:
                self._started = False
            raise

    def _refill_queue(self) -> int:
        """Admit durable queued tasks until this worker reaches capacity.

        The database is the source of truth.  The in-process semaphore only
        bounds local concurrency; it must not make queued durable records
        disappear after the first batch has completed.
        """
        with self._lock:
            if self._closed:
                return 0
        scheduled = 0
        now = self._now()
        try:
            records = self.store.list_tasks(
                statuses=["queued"],
                limit=self.max_workers + self.max_queue,
            )
            for record in records:
                task_id = str(record.task_id)
                with self._lock:
                    already_scheduled = task_id in self._handles
                if already_scheduled:
                    continue
                if not self._schedule(task_id):
                    # A false result here means local admission is full (or
                    # shutdown raced this poll).  Later polls will retry.
                    break
                scheduled += 1
            with self._lock:
                self._queue_poll_total += scheduled
                self._last_queue_poll_at = now
            return scheduled
        except Exception:
            with self._lock:
                self._queue_poll_errors += 1
                self._last_queue_poll_at = now
            raise

    def _start_queue_poller(self) -> None:
        with self._lock:
            if self._queue_poller_thread and self._queue_poller_thread.is_alive():
                return
            self._queue_poller_stop.clear()
            self._queue_poller_wakeup.clear()
            self._queue_poller_thread = threading.Thread(
                target=self._poll_durable_queue,
                name="ad-agent-task-queue-poller",
                daemon=True,
            )
            self._queue_poller_thread.start()

    def _poll_durable_queue(self) -> None:
        """Continuously refill local capacity from the durable task table."""
        while not self._queue_poller_stop.is_set():
            try:
                self._refill_queue()
            except Exception:
                # A transient persistence outage must not terminate the worker;
                # durable rows remain queued and are retried on the next poll.
                logger.warning("durable task queue poll failed", exc_info=True)
            self._queue_poller_wakeup.wait(self.queue_poll_interval)
            self._queue_poller_wakeup.clear()

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
                with self._lock:
                    self._queue_rejection_total += 1
                return False
            if not slot_reserved:
                self._admitted_slots += 1
            cancel_event = threading.Event()
            # A very fast handler can finish before ``submit`` returns. Hold
            # it behind a one-shot gate until the handle is visible; otherwise
            # ``_run`` can remove a not-yet-installed handle and leave a stale
            # entry that blocks future durable refills.
            start_gate = threading.Event()
            try:
                future = self._pool.submit(
                    self._run, str(task_id), cancel_event, start_gate
                )
            except Exception:
                if not slot_reserved:
                    self._capacity.release()
                    self._admitted_slots = max(0, self._admitted_slots - 1)
                raise
            self._handles[str(task_id)] = _TaskHandle(cancel_event, future)
            future.add_done_callback(
                lambda completed, scheduled_task_id=str(task_id): (
                    self._release_cancelled_slot(scheduled_task_id, completed)
                )
            )
            start_gate.set()
            return True

    def _release_cancelled_slot(self, task_id: str, future: Any) -> None:
        """Release admission held by a Future cancelled before ``_run`` starts."""
        if not future.cancelled():
            return
        with self._lock:
            handle = self._handles.pop(task_id, None)
            if handle is None:
                return
            self._admitted_slots = max(0, self._admitted_slots - 1)
        self._capacity.release()
        self._queue_poller_wakeup.set()

    def _run(
        self, task_id: str, cancel_event: threading.Event,
        start_gate: Optional[threading.Event] = None,
    ) -> None:
        if start_gate is not None:
            start_gate.wait()
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
            with self._lock:
                before_execute = self._before_execute
            if before_execute is not None:
                try:
                    before_execute(context)
                except Exception as exc:
                    self.store.update_task(
                        task_id, "failed",
                        error=f"pre-execution hook failed: {type(exc).__name__}",
                        expected_statuses=["running"],
                    )
                    return
            current_before_run = self.store.get_task(task_id)
            if current_before_run and current_before_run.status == "cancelling":
                cancel_event.set()
            heartbeat_stop = threading.Event()
            deadline_event = threading.Event()

            # Python cannot safely kill an external call running in a worker
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
                        metadata={"lease_lost": True, "effect_state": "unknown"},
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
                            "effect_state": "unknown",
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
                        {"deadline_exceeded": True, "effect_state": "unknown"}
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
            with self._lock:
                self._admitted_slots = max(0, self._admitted_slots - 1)
            self._queue_poller_wakeup.set()

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
            # Queue saturation is transient. Keep the durable task queued so
            # the poller can admit it when a local slot is released.
            self._queue_poller_wakeup.set()
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
            # Recovery has already been explicitly verified. Admission is a
            # local concern and must not turn a durable queued task into a
            # user-visible pause.
            self._queue_poller_wakeup.set()
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
        self._queue_poller_stop.set()
        self._queue_poller_wakeup.set()
        queue_poller = self._queue_poller_thread
        if queue_poller:
            queue_poller.join(timeout=0.5)
        self._queue_poller_thread = None
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
