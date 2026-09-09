"""Regression coverage for durable worker liveness and explicit recovery."""

import os
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import pytest

from agents.ad_agent.persistence.models import (
    ExecutionRunRecord, OutboxEvent, ScheduledTaskRecord, TaskRecord,
)
from agents.ad_agent.persistence.mysql_store import _MySQLPool
from agents.ad_agent.persistence.store import AdAgentStore
from agents.ad_agent.runtime.runtime import AgentRuntime
from agents.ad_agent.runtime.task_executor import TaskExecutor


def test_worker_liveness_is_durable_and_visible_to_monitoring():
    store = AdAgentStore(":memory:")
    store.register_worker("worker-a", "task_executor", metadata={"pid": 1})
    assert store.heartbeat_worker("worker-a") is True
    snapshot = store.get_monitoring_snapshot()
    assert snapshot["workers"]["running"] == 1
    assert snapshot["workers"]["items"][0]["worker_id"] == "worker-a"
    assert store.unregister_worker("worker-a") is True
    assert store.list_workers()[0]["status"] == "stopped"
    store.close()


def test_execution_event_repair_is_idempotent():
    store = AdAgentStore(":memory:")
    store.create_execution_run(ExecutionRunRecord(
        run_id="run-repair", session_id="session", turn_id="turn",
        user_id="user", tenant_id="tenant",
        created_at=datetime.now(timezone.utc).isoformat(),
        updated_at=datetime.now(timezone.utc).isoformat(),
    ))
    event = {
        "type": "start", "event_type": "start", "seq": 1,
        "status": "running", "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    assert store.enqueue_execution_event_repair("run-repair", event) is True
    assert store.repair_execution_run_events() == 1
    assert store.repair_execution_run_events() == 0
    assert store.list_execution_run_events("run-repair")[0]["seq"] == 1
    store.close()


def test_recovery_task_requires_provider_proof_before_requeue():
    store = AdAgentStore(":memory:")
    store.create_task(TaskRecord(
        task_id="recovery-task", tenant_id="tenant", user_id="user",
        kind="local", status="recovery_required", payload={},
        metadata={"provider_state": "unknown"},
        created_at=datetime.now(timezone.utc).isoformat(),
        updated_at=datetime.now(timezone.utc).isoformat(),
    ))
    executor = TaskExecutor(store, max_workers=1, max_queue=0)
    executor.register_handler("local", lambda _ctx: {"ok": True})
    with pytest.raises(ValueError):
        executor.requeue_recovery("recovery-task", recovery_reference="")
    record = executor.requeue_recovery(
        "recovery-task", recovery_reference="provider-readback-1",
    )
    assert record is not None
    assert record.status in {"queued", "running", "succeeded"}
    executor.shutdown(wait=True)
    store.close()


def test_runtime_recovery_checks_permission_and_provider_verification():
    store = AdAgentStore(":memory:")
    store.create_task(TaskRecord(
        task_id="runtime-recovery", tenant_id="tenant", user_id="user",
        kind="agent.turn", status="recovery_required", payload={"user_input": "hello"},
        created_at=datetime.now(timezone.utc).isoformat(),
        updated_at=datetime.now(timezone.utc).isoformat(),
    ))
    runtime = AgentRuntime(require_llm=False, persistence_store=store, features=[])
    with pytest.raises(PermissionError):
        runtime.recover_task(
            "runtime-recovery", user_id="user", tenant_id="tenant",
            recovery_reference="readback-1", provider_verified=True,
            permissions={"ads.read"},
        )
    with pytest.raises(ValueError):
        runtime.recover_task(
            "runtime-recovery", user_id="user", tenant_id="tenant",
            recovery_reference="readback-1", provider_verified=False,
            permissions={"ads.reconcile"},
        )
    runtime.close(wait=True)
    store.close()


def test_two_sqlite_instances_only_one_worker_claims_a_task():
    path = tempfile.mktemp(suffix=".db")
    first = AdAgentStore(path)
    second = AdAgentStore(path)
    try:
        now = datetime.now(timezone.utc).isoformat()
        first.create_task(TaskRecord(
            task_id="shared-task", tenant_id="tenant", user_id="user",
            kind="agent.turn", status="queued", payload={},
            created_at=now, updated_at=now,
        ))
        with ThreadPoolExecutor(max_workers=2) as pool:
            claims = list(pool.map(
                lambda args: args[0].claim_task("shared-task", args[1], 30.0),
                [(first, "worker-a"), (second, "worker-b")],
            ))
        owners = [claim.lease_owner for claim in claims if claim]
        assert len(owners) == 1
        assert owners[0] in {"worker-a", "worker-b"}
        assert first.get_task("shared-task").lease_owner == owners[0]
    finally:
        first.close()
        second.close()
        if os.path.exists(path):
            os.unlink(path)


def test_two_sqlite_instances_create_one_schedule_occurrence():
    path = tempfile.mktemp(suffix=".db")
    first = AdAgentStore(path)
    second = AdAgentStore(path)
    try:
        now = datetime.now(timezone.utc).isoformat()
        first.create_scheduled_task(ScheduledTaskRecord(
            schedule_id="shared-schedule", tenant_id="tenant", user_id="user",
            name="daily", prompt="report", cron_expression="* * * * *",
            next_run_at="2000-01-01T00:00:00+00:00", created_at=now, updated_at=now,
        ))
        with ThreadPoolExecutor(max_workers=2) as pool:
            claims = list(pool.map(
                lambda args: args[0].claim_due_scheduled_tasks(
                    now, args[1], 30.0, 1,
                ),
                [(first, "scheduler-a"), (second, "scheduler-b")],
            ))
        assert sum(len(items) for items in claims) == 1
        assert len(first.list_scheduled_task_runs()) == 1
    finally:
        first.close()
        second.close()
        if os.path.exists(path):
            os.unlink(path)


def test_two_sqlite_instances_only_one_outbox_consumer_claims_event():
    path = tempfile.mktemp(suffix=".db")
    first = AdAgentStore(path)
    second = AdAgentStore(path)
    try:
        now = datetime.now(timezone.utc).isoformat()
        first.insert_outbox_event(OutboxEvent(
            event_id="shared-event", run_id="run", event_type="started",
            payload={}, created_at=now,
        ))
        with ThreadPoolExecutor(max_workers=2) as pool:
            claims = list(pool.map(
                lambda args: args[0].claim_outbox_events(1, args[1]),
                [(first, "outbox-a"), (second, "outbox-b")],
            ))
        assert sum(len(items) for items in claims) == 1
    finally:
        first.close()
        second.close()
        if os.path.exists(path):
            os.unlink(path)


def test_runtime_can_disable_background_workers_for_in_memory_tests():
    store = AdAgentStore(":memory:")
    runtime = AgentRuntime(
        require_llm=False, persistence_store=store, features=[],
        start_background_workers=False,
    )
    assert runtime.outbox_consumer is None
    assert runtime.scheduler is not None
    assert runtime.scheduler.metrics()["state"] == "stopped"
    runtime.close(wait=True)
    store.close()


class _FakeMySQLConnection:
    def __init__(self):
        self.closed = False
        self.pings = 0

    def ping(self, reconnect=False):
        self.pings += 1

    def close(self):
        self.closed = True


def test_mysql_pool_wakes_waiters_and_closes_checked_out_connections():
    connections = []

    def connect():
        connection = _FakeMySQLConnection()
        connections.append(connection)
        return connection

    pool = _MySQLPool(connect, pool_size=1, max_overflow=0)
    held = pool.acquire()

    with ThreadPoolExecutor(max_workers=1) as executor:
        waiter = executor.submit(pool.acquire)
        assert pool.metrics()["in_use"] == 1
        pool.release(held)
        borrowed = waiter.result(timeout=2)
        assert borrowed is held
        assert borrowed.pings == 2
        pool.close()

    assert connections[0].closed is True
    assert pool.metrics()["created"] == 0
    with pytest.raises(RuntimeError, match="pool is closed"):
        pool.acquire()
