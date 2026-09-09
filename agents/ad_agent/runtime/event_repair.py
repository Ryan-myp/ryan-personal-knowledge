"""Durable, provider-neutral repair loop for execution run events."""

from __future__ import annotations

import logging
import threading
import uuid
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ExecutionEventRepairConsumer:
    """Retry observability writes without coupling them to Agent execution."""

    def __init__(self, store: Any, *, poll_interval: float = 2.0):
        self.store = store
        self.poll_interval = max(0.5, float(poll_interval))
        self.worker_id = f"event-repair:{uuid.uuid4().hex}"
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._last_error: Optional[str] = None
        self._repaired_total = 0

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        register = getattr(self.store, "register_worker", None)
        if callable(register):
            register(
                self.worker_id, "execution_event_repair",
                metadata={"poll_interval_seconds": self.poll_interval},
                lease_seconds=30.0,
            )
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run, name="ad-agent-event-repair", daemon=True,
        )
        self._thread.start()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                repair = getattr(self.store, "repair_execution_run_events", None)
                if callable(repair):
                    self._repaired_total += int(repair(50) or 0)
                self._last_error = None
                heartbeat = getattr(self.store, "heartbeat_worker", None)
                if callable(heartbeat) and not heartbeat(self.worker_id, lease_seconds=30.0):
                    break
            except Exception as exc:
                self._last_error = type(exc).__name__
                logger.warning("execution event repair failed", exc_info=True)
            self._stop.wait(self.poll_interval)

    def metrics(self) -> dict[str, Any]:
        thread = self._thread
        return {
            "worker_id": self.worker_id,
            "state": "running" if thread and thread.is_alive() else "stopped",
            "repaired_total": self._repaired_total,
            "last_error": self._last_error,
        }

    def stop(self, timeout: float = 2.0) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(max(0.0, float(timeout)))
        unregister = getattr(self.store, "unregister_worker", None)
        if callable(unregister):
            try:
                unregister(self.worker_id)
            except Exception:
                logger.warning("failed to unregister event repair worker", exc_info=True)
        self._thread = None


__all__ = ["ExecutionEventRepairConsumer"]
