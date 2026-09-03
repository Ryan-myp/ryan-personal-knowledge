"""Durable task lifecycle tests; handlers are local and never call providers."""

import threading
import time

import pytest

from agents.ad_agent.core.auth import RequestPrincipal
from agents.ad_agent.persistence.models import TaskRecord
from agents.ad_agent.persistence.store import AdAgentStore
from agents.ad_agent.runtime.task_executor import TaskExecutor, TaskCapacityError


def _wait_for(executor, task_id, statuses, timeout=2.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        record = executor.get(task_id)
        if record and record.status in statuses:
            return record
        time.sleep(0.01)
    return executor.get(task_id)


def test_task_is_idempotent_and_persisted_without_callback_data():
    store = AdAgentStore(":memory:")
    executor = TaskExecutor(store, max_workers=1, max_queue=1)
    executor.register_handler("local", lambda context: {"ok": True, "workflow_id": "wf-1"})

    first, created = executor.submit(
        "local", {"input": "safe"}, tenant_id="tenant-a", user_id="user-a",
        idempotency_key="same-request",
        metadata={"principal": {"user_id": "user-a", "tenant_id": "tenant-a"}},
    )
    second, duplicate = executor.submit(
        "local", {"input": "different"}, tenant_id="tenant-a", user_id="user-a",
        idempotency_key="same-request",
    )

    assert created is True
    assert duplicate is False
    assert second.task_id == first.task_id
    assert _wait_for(executor, first.task_id, {"succeeded"}).result == {
        "ok": True, "workflow_id": "wf-1",
    }
    stored = store.get_task(first.task_id)
    assert stored and stored.payload == {"input": "safe"}
    assert stored.workflow_id == "wf-1"
    assert "handler" not in stored.to_dict()
    executor.shutdown()


def test_pause_resume_only_controls_queued_work():
    store = AdAgentStore(":memory:")
    executor = TaskExecutor(store, max_workers=1, max_queue=1)
    started = threading.Event()
    release = threading.Event()
    ran_second = threading.Event()

    def blocking(_context):
        started.set()
        release.wait(2)
        return {"first": True}

    def second(_context):
        ran_second.set()
        return {"second": True}

    executor.register_handler("blocking", blocking)
    executor.register_handler("second", second)
    first, _ = executor.submit("blocking", {}, tenant_id="t", user_id="u")
    assert started.wait(1)
    queued, _ = executor.submit("second", {}, tenant_id="t", user_id="u")
    assert executor.pause(queued.task_id).status == "paused"
    release.set()
    assert _wait_for(executor, first.task_id, {"succeeded"})
    time.sleep(0.05)
    assert not ran_second.is_set()
    assert executor.resume(queued.task_id).status in {"queued", "running", "succeeded"}
    assert ran_second.wait(1)
    assert _wait_for(executor, queued.task_id, {"succeeded"})
    executor.shutdown()


def test_cancel_signals_running_handler_and_never_marks_it_succeeded():
    store = AdAgentStore(":memory:")
    executor = TaskExecutor(store, max_workers=1, max_queue=0)
    started = threading.Event()

    def cancellable(context):
        started.set()
        while not context.is_cancelled():
            time.sleep(0.005)
        return {"would_have_been": "stopped"}

    executor.register_handler("cancellable", cancellable)
    task, _ = executor.submit("cancellable", {}, tenant_id="t", user_id="u")
    assert started.wait(1)
    assert executor.cancel(task.task_id).status == "cancelling"
    final = _wait_for(executor, task.task_id, {"cancelled"})
    assert final.status == "cancelled"
    executor.shutdown()


def test_task_scope_isolated_and_queue_capacity_is_bounded():
    store = AdAgentStore(":memory:")
    executor = TaskExecutor(store, max_workers=1, max_queue=0)
    release = threading.Event()
    executor.register_handler("wait", lambda _context: release.wait(2) or {"ok": True})
    first, _ = executor.submit("wait", {}, tenant_id="t", user_id="u")
    with pytest.raises(TaskCapacityError):
        executor.submit("wait", {}, tenant_id="t", user_id="u2")
    assert executor.get(first.task_id, tenant_id="other", user_id="u") is None
    release.set()
    assert _wait_for(executor, first.task_id, {"succeeded"})
    executor.shutdown()


def test_stale_running_task_is_recovery_required_and_not_auto_replayed():
    store = AdAgentStore(":memory:")
    now = "2000-01-01T00:00:00"
    store.create_task(TaskRecord(
        task_id="stale", tenant_id="t", user_id="u", kind="local",
        status="running", payload={}, created_at=now, updated_at=now,
        started_at=now, lease_owner="old-worker", lease_expires_at=now,
    ))
    executor = TaskExecutor(store, max_workers=1, max_queue=0)
    executor.register_handler("local", lambda _context: {"unexpected": True})
    executor.start()
    assert executor.get("stale").status == "recovery_required"
    executor.shutdown()


def test_task_deadline_never_reports_late_handler_as_success():
    store = AdAgentStore(":memory:")
    executor = TaskExecutor(
        store, max_workers=1, max_queue=0, task_timeout_seconds=0.01,
    )

    def late_handler(_context):
        time.sleep(0.03)
        return {"provider_write": "possibly_completed"}

    executor.register_handler("late", late_handler)
    task, _ = executor.submit("late", {}, tenant_id="t", user_id="u")
    final = _wait_for(executor, task.task_id, {"recovery_required"}, timeout=1)

    assert final.status == "recovery_required"
    assert final.metadata["deadline_exceeded"] is True
    assert final.metadata["provider_state"] == "unknown"
    executor.shutdown()
