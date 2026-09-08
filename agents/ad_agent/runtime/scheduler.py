"""Provider-neutral recurring schedule service for the Agent Runtime."""

from __future__ import annotations

import logging
import re
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ..persistence.models import ScheduledTaskRecord, ScheduledTaskRunRecord

logger = logging.getLogger(__name__)


class CronExpressionError(ValueError):
    """The schedule is not a supported five-field cron expression."""


class CronExpression:
    """Small dependency-free five-field cron evaluator.

    Supported syntax is deliberately bounded: ``*``, ``*/n``, comma lists,
    inclusive ranges and single values. This is enough for user-facing daily,
    hourly and weekly schedules while keeping the parser auditable.
    """

    RANGES = ((0, 59), (0, 23), (1, 31), (1, 12), (0, 6))

    def __init__(self, expression: str):
        self.expression = " ".join(str(expression or "").strip().split())
        fields = self.expression.split(" ")
        if len(fields) != 5:
            raise CronExpressionError("cron expression must contain five fields")
        self._values = [
            self._parse_field(field, bounds)
            for field, bounds in zip(fields, self.RANGES)
        ]

    @staticmethod
    def _parse_field(field: str, bounds: tuple[int, int]) -> set[int]:
        low, high = bounds
        values: set[int] = set()
        for item in str(field).split(","):
            item = item.strip()
            if not item:
                raise CronExpressionError("empty cron item")
            step = 1
            if "/" in item:
                base, raw_step = item.split("/", 1)
                try:
                    step = int(raw_step)
                except ValueError as exc:
                    raise CronExpressionError("cron step must be an integer") from exc
                if step <= 0:
                    raise CronExpressionError("cron step must be positive")
            else:
                base = item
            if base == "*":
                start, end = low, high
            elif "-" in base:
                parts = base.split("-", 1)
                try:
                    start, end = int(parts[0]), int(parts[1])
                except ValueError as exc:
                    raise CronExpressionError("cron range must be numeric") from exc
            else:
                try:
                    start = end = int(base)
                except ValueError as exc:
                    raise CronExpressionError("cron value must be numeric") from exc
                if "/" in item:
                    start, end = low, high
            if start < low or end > high or start > end:
                raise CronExpressionError(f"cron value out of range: {item}")
            values.update(range(start, end + 1, step))
        if not values:
            raise CronExpressionError("cron field has no values")
        return values

    def matches(self, value: datetime) -> bool:
        # Python weekday is Monday=0 while cron convention is Sunday=0.
        cron_weekday = (value.weekday() + 1) % 7
        return all(
            candidate in values
            for candidate, values in zip(
                (value.minute, value.hour, value.day, value.month, cron_weekday),
                self._values,
            )
        )

    def next_after(self, value: datetime) -> datetime:
        candidate = value.replace(second=0, microsecond=0) + timedelta(minutes=1)
        # A bounded search keeps malformed or extremely sparse schedules from
        # blocking the scheduler forever.
        for _ in range(366 * 24 * 60 * 2):
            if self.matches(candidate):
                return candidate
            candidate += timedelta(minutes=1)
        raise CronExpressionError("could not find next cron occurrence within one year")


def validate_timezone(value: str) -> str:
    timezone_name = str(value or "Asia/Shanghai").strip() or "Asia/Shanghai"
    try:
        ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"unknown timezone: {timezone_name}") from exc
    return timezone_name


def next_run_at(expression: str, timezone_name: str, after: Optional[datetime] = None) -> str:
    cron = CronExpression(expression)
    timezone_name = validate_timezone(timezone_name)
    zone = ZoneInfo(timezone_name)
    base = after or datetime.now(timezone.utc)
    if base.tzinfo is None:
        base = base.replace(tzinfo=timezone.utc)
    local = base.astimezone(zone)
    occurrence = cron.next_after(local)
    return occurrence.astimezone(timezone.utc).isoformat()


@dataclass
class SchedulerMetrics:
    state: str = "stopped"
    worker_id: str = ""
    last_scan_at: Optional[str] = None
    last_error: Optional[str] = None
    claimed_total: int = 0
    submitted_total: int = 0
    failed_total: int = 0

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


class SchedulerService:
    """Poll durable schedules and submit normal Agent turns.

    The service has no provider knowledge. A database lease and the unique
    ``(schedule_id, scheduled_for)`` occurrence key make multiple instances
    safe when backed by MySQL/InnoDB; SQLite remains intentionally single-
    process as documented by the repository architecture.
    """

    def __init__(
        self,
        store: Any,
        submit_turn: Callable[[ScheduledTaskRecord, ScheduledTaskRunRecord], Any],
        *, poll_interval: float = 5.0,
        lease_seconds: float = 60.0,
        batch_size: int = 20,
    ):
        self.store = store
        self.submit_turn = submit_turn
        self.poll_interval = max(0.5, float(poll_interval))
        self.lease_seconds = max(5.0, float(lease_seconds))
        self.batch_size = max(1, min(int(batch_size), 100))
        self.worker_id = f"scheduler:{uuid.uuid4().hex}"
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.RLock()
        self._metrics = SchedulerMetrics(worker_id=self.worker_id)

    def start(self) -> None:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._stop.clear()
            self._metrics.state = "running"
            self._thread = threading.Thread(
                target=self._run, name="ad-agent-scheduler", daemon=True
            )
            self._thread.start()

    def stop(self, wait: bool = False) -> None:
        with self._lock:
            self._stop.set()
            thread = self._thread
            self._metrics.state = "stopped"
        if wait and thread:
            thread.join(timeout=max(1.0, self.poll_interval + 1.0))

    def metrics(self) -> dict[str, Any]:
        with self._lock:
            return self._metrics.to_dict()

    def scan_once(self) -> int:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            self._metrics.last_scan_at = now
        claimed = self.store.claim_due_scheduled_tasks(
            now, self.worker_id, self.lease_seconds, self.batch_size
        )
        for schedule, occurrence in claimed:
            with self._lock:
                self._metrics.claimed_total += 1
            try:
                task = self.submit_turn(schedule, occurrence)
                task_id = str(task.get("task_id") if isinstance(task, dict) else getattr(task, "task_id", ""))
                if not task_id:
                    raise RuntimeError("scheduled Agent task did not return task_id")
                self.store.attach_scheduled_task_run(occurrence.schedule_run_id, task_id)
                # Advance only after the durable Agent task exists. If the
                # process dies before this point, the same occurrence is
                # recovered by its unique run key on the next scan.
                following = next_run_at(
                    schedule.cron_expression, schedule.timezone,
                    after=datetime.fromisoformat(str(occurrence.scheduled_for).replace("Z", "+00:00")),
                )
                self.store.advance_scheduled_task(
                    schedule.schedule_id, str(occurrence.scheduled_for), following,
                )
                with self._lock:
                    self._metrics.submitted_total += 1
            except Exception as exc:
                safe_error = str(exc)[:1000]
                # Keep submission failures queued so a transient queue/database
                # outage is retried instead of consuming the recurring slot.
                self.store.update_scheduled_task_run(
                    occurrence.schedule_run_id, "queued", error=safe_error,
                )
                with self._lock:
                    self._metrics.failed_total += 1
                logger.exception("failed to submit scheduled Agent task")
        self.reconcile_once()
        return len(claimed)

    def reconcile_once(self) -> int:
        runs = self.store.list_scheduled_task_runs(statuses=["queued", "running"], limit=100)
        changed = 0
        for run in runs:
            if not run.task_id:
                continue
            task = self.store.get_task(run.task_id, tenant_id=run.tenant_id, user_id=run.user_id)
            if not task or task.status in {"queued", "running", "cancelling"}:
                continue
            status = "succeeded" if task.status == "succeeded" else "failed"
            self.store.update_scheduled_task_run(
                run.schedule_run_id, status,
                finished_at=task.finished_at or datetime.now(timezone.utc).isoformat(),
                error=task.error,
                result=task.result,
            )
            changed += 1
        return changed

    def _run(self) -> None:
        # Run immediately after startup so a restart does not wait a full poll.
        while not self._stop.is_set():
            try:
                self.scan_once()
                with self._lock:
                    self._metrics.last_error = None
            except Exception as exc:
                with self._lock:
                    self._metrics.last_error = str(exc)[:1000]
                logger.exception("scheduled task scan failed")
            self._stop.wait(self.poll_interval)


__all__ = [
    "CronExpression", "CronExpressionError", "SchedulerService",
    "next_run_at", "validate_timezone",
]
