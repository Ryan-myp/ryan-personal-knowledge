"""The platform task adapter is independent of product persistence packages."""

from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
import multiprocessing
import sqlite3
from threading import Barrier

import pytest

from agents.agent_platform.infrastructure.durable.task import TaskSubmission
from agents.agent_platform.infrastructure.durable.sqlite_store import SQLiteTaskQueueStore


def _claim_in_process(database, owner, start_event, result_queue):
    store = SQLiteTaskQueueStore(database)
    try:
        start_event.wait(timeout=10)
        result_queue.put(store.claim_task("task-1", owner, 30) is not None)
    finally:
        store.close()


def _task(task_id="task-1", **overrides):
    fields = {
        "task_id": task_id,
        "tenant_id": "tenant-a",
        "user_id": "user-a",
        "kind": "agent.turn",
        "status": "queued",
        "payload": {"text": "hello"},
        "idempotency_key": None,
        "workflow_id": None,
        "metadata": {},
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }
    fields.update(overrides)
    return TaskSubmission(**fields)


def test_task_store_persists_and_scopes_records(tmp_path):
    path = tmp_path / "tasks.sqlite3"
    first = SQLiteTaskQueueStore(path)
    first.create_task(_task(idempotency_key="request-1"))
    first.close()

    second = SQLiteTaskQueueStore(path)
    try:
        row = second.get_task("task-1", tenant_id="tenant-a", user_id="user-a")
        assert row.payload == {"text": "hello"}
        assert second.get_task("task-1", tenant_id="tenant-b") is None
        assert second.find_task_by_idempotency(
            "tenant-a", "user-a", "request-1"
        ).task_id == "task-1"
        assert second.list_tasks(tenant_id="tenant-b") == []
    finally:
        second.close()


def test_claim_is_atomic_across_store_instances(tmp_path):
    path = tmp_path / "claims.sqlite3"
    first = SQLiteTaskQueueStore(path)
    second = SQLiteTaskQueueStore(path)
    try:
        first.create_task(_task())
        barrier = Barrier(2)

        def claim(store, owner):
            barrier.wait(timeout=2)
            return store.claim_task("task-1", owner, 30)

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [
                pool.submit(claim, first, "worker-a"),
                pool.submit(claim, second, "worker-b"),
            ]
            claims = [future.result(timeout=3) for future in futures]
        assert sum(claim is not None for claim in claims) == 1
        assert first.get_task("task-1").status == "running"
    finally:
        first.close()
        second.close()


def test_claim_is_atomic_across_processes(tmp_path):
    database = str(tmp_path / "process-claims.sqlite3")
    store = SQLiteTaskQueueStore(database)
    store.create_task(_task())
    store.close()

    context = multiprocessing.get_context("spawn")
    start_event = context.Event()
    results = context.Queue()
    processes = [
        context.Process(
            target=_claim_in_process,
            args=(database, worker, start_event, results),
        )
        for worker in ("process-a", "process-b")
    ]
    try:
        for process in processes:
            process.start()
        start_event.set()
        claimed = [results.get(timeout=15) for _ in processes]
        for process in processes:
            process.join(timeout=15)
        assert all(process.exitcode == 0 for process in processes)
        assert sum(claimed) == 1
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
            process.join(timeout=2)
        results.close()


def test_stale_task_requires_explicit_recovery_and_reference(tmp_path):
    store = SQLiteTaskQueueStore(tmp_path / "recovery.sqlite3")
    old = (datetime.now() - timedelta(minutes=10)).isoformat()
    try:
        store.create_task(_task(
            status="running", started_at=old, updated_at=old,
            lease_owner="dead-worker", lease_expires_at=old,
        ))
        assert store.recover_stale_tasks(60) == 1
        assert store.get_task("task-1").status == "recovery_required"
        assert store.requeue_recovery_task(
            "task-1", recovery_reference="provider-state-checked",
            tenant_id="tenant-a", user_id="user-a",
        ).status == "queued"
        assert store.get_task("task-1").metadata["recovery_reference"] == "provider-state-checked"
    finally:
        store.close()


def test_worker_lease_and_task_controls_are_scoped(tmp_path):
    store = SQLiteTaskQueueStore(tmp_path / "worker.sqlite3")
    try:
        store.register_worker("worker-1", "task_executor", lease_seconds=30)
        assert store.heartbeat_worker("worker-1", lease_seconds=30)
        assert store.unregister_worker("worker-1")

        store.create_task(_task())
        assert store.pause_task("task-1", "tenant-b", "user-a") is None
        assert store.pause_task("task-1", "tenant-a", "user-a").status == "paused"
        assert store.resume_task("task-1", "tenant-a", "user-a").status == "queued"
        assert store.cancel_task("task-1", "tenant-a", "user-a").status == "cancelled"
    finally:
        store.close()


def test_idempotency_is_unique_and_invalid_transitions_are_rejected(tmp_path):
    store = SQLiteTaskQueueStore(tmp_path / "constraints.sqlite3")
    try:
        store.create_task(_task(idempotency_key="same-key"))
        with pytest.raises(sqlite3.IntegrityError):
            store.create_task(_task(
                task_id="task-2", idempotency_key="same-key",
            ))
        assert store.get_task("task-2") is None
        assert store.update_task("task-1", "succeeded") is False
        assert store.update_task("task-1", "made-up-status") is False
        assert store.get_task("task-1").status == "queued"
    finally:
        store.close()
