"""Durable workflow event publishing and delivery helpers.

The outbox is deliberately a backend/service seam. It does not know about a
provider or add a second Runtime router. SSE remains a request-scoped view;
this module is the durable hand-off for a later SSE/Webhook/metrics sink.
"""

from __future__ import annotations

import threading
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Optional

from ..core.durable_ports import OutboxStore

logger = logging.getLogger(__name__)


class OutboxPublisher:
    """Persist sanitized events through ``SessionManager``."""

    def __init__(self, session_manager: Any):
        self.session_manager = session_manager

    def publish(self, run_id: str, event_type: str, payload: dict[str, Any]) -> str:
        if not self.session_manager:
            raise RuntimeError("outbox requires a persistence-backed SessionManager")
        return self.session_manager.publish_outbox_event(run_id, event_type, payload)


class OutboxConsumer:
    """Bounded background consumer with explicit ack/retry semantics."""

    def __init__(
        self,
        store: OutboxStore,
        publish: Callable[[Any], None],
        *,
        poll_interval: float = 0.25,
        batch_size: int = 20,
        max_backoff_seconds: float = 60.0,
    ):
        self.store = store
        self.publish = publish
        self.poll_interval = max(0.01, float(poll_interval))
        self.batch_size = max(1, min(int(batch_size), 100))
        self.max_backoff_seconds = max(0.1, float(max_backoff_seconds))
        # ``id(self)`` is only process-local and can collide after a restart;
        # claims are a cross-instance coordination boundary.
        self.consumer_id = f"outbox:{uuid.uuid4().hex}"
        self._stop = threading.Event()
        self._lock = threading.RLock()
        self._thread: Optional[threading.Thread] = None
        self._heartbeat_thread: Optional[threading.Thread] = None
        self._claimed_total = 0
        self._delivered_total = 0
        self._retry_total = 0
        self._error_total = 0

    def drain_once(self) -> int:
        delivered = 0
        events = self.store.claim_outbox_events(self.batch_size, self.consumer_id)
        with self._lock:
            self._claimed_total += len(events)
        for event in events:
            try:
                self.publish(event)
            except Exception:
                delay = min(
                    self.max_backoff_seconds,
                    max(0.1, 2 ** min(int(event.retry_count), 8)),
                )
                next_retry = (
                    datetime.now(timezone.utc) + timedelta(seconds=delay)
                ).isoformat()
                self.store.mark_outbox_retry(
                    # Delivery exceptions may contain provider payloads or
                    # credentials; keep the durable retry record generic.
                    event.event_id, next_retry, "outbox delivery failed",
                    self.consumer_id,
                )
                with self._lock:
                    self._retry_total += 1
            else:
                if self.store.mark_outbox_delivered(
                    event.event_id, self.consumer_id
                ):
                    delivered += 1
                    with self._lock:
                        self._delivered_total += 1
        return delivered

    def start(self) -> None:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._stop.clear()
            register = getattr(self.store, "register_worker", None)
            registered = False
            try:
                if callable(register):
                    register(
                        self.consumer_id, "outbox_consumer",
                        metadata={"batch_size": self.batch_size}, lease_seconds=30.0,
                    )
                    registered = True
                self._heartbeat_thread = threading.Thread(
                    target=self._heartbeat, name="ad-agent-outbox-heartbeat", daemon=True,
                )
                self._heartbeat_thread.start()
                self._thread = threading.Thread(
                    target=self._run, name="ad-agent-outbox", daemon=True
                )
                self._thread.start()
            except Exception:
                self._stop.set()
                thread = self._thread
                heartbeat_thread = self._heartbeat_thread
                self._thread = None
                self._heartbeat_thread = None
                if thread:
                    thread.join(timeout=0.5)
                if heartbeat_thread:
                    heartbeat_thread.join(timeout=0.5)
                if registered and callable(getattr(self.store, "unregister_worker", None)):
                    try:
                        self.store.unregister_worker(self.consumer_id)
                    except Exception:
                        logger.warning("failed to roll back outbox worker registration", exc_info=True)
                raise

    def _heartbeat(self) -> None:
        heartbeat = getattr(self.store, "heartbeat_worker", None)
        if not callable(heartbeat):
            return
        while not self._stop.wait(10.0):
            if getattr(self.store, "is_closed", False):
                return
            try:
                if not heartbeat(self.consumer_id, lease_seconds=30.0):
                    return
            except Exception:
                logger.warning("outbox worker heartbeat failed", exc_info=True)

    def metrics(self) -> dict[str, Any]:
        """Return process-local delivery state for the monitoring console."""
        with self._lock:
            thread = self._thread
            return {
                "consumer_id": self.consumer_id,
                "state": "running" if thread and thread.is_alive() else "stopped",
                "poll_interval_seconds": self.poll_interval,
                "batch_size": self.batch_size,
                "claimed_total": self._claimed_total,
                "delivered_total": self._delivered_total,
                "retry_total": self._retry_total,
                "error_total": self._error_total,
            }

    def stop(self, timeout: float = 2.0) -> None:
        with self._lock:
            self._stop.set()
            thread = self._thread
            heartbeat_thread = self._heartbeat_thread
        if thread:
            thread.join(max(0.0, float(timeout)))
        if heartbeat_thread:
            heartbeat_thread.join(max(0.0, min(float(timeout), 0.5)))
        unregister = getattr(self.store, "unregister_worker", None)
        if callable(unregister):
            try:
                unregister(self.consumer_id)
            except Exception:
                logger.warning("failed to unregister outbox worker", exc_info=True)
        with self._lock:
            self._thread = None
            self._heartbeat_thread = None

    def _run(self) -> None:
        while not self._stop.is_set():
            if getattr(self.store, "is_closed", False):
                break
            try:
                self.drain_once()
            except Exception as exc:
                # Delivery failures are handled per event in ``drain_once``.
                # A backend outage/close can still fail the claim itself; keep
                # the daemon alive and leave pending rows durable for retry.
                logger.warning(
                    "Outbox poll failed; retrying: %s",
                    type(exc).__name__,
                )
                with self._lock:
                    self._error_total += 1
                if self._stop.wait(min(max(self.poll_interval * 4, 0.5), 5.0)):
                    break
                continue
            self._stop.wait(self.poll_interval)
