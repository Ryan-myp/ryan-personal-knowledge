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
from agents.ad_agent.runtime.runtime import AdvertisingComposition
from agents.ad_agent.runtime.task_executor import TaskExecutor
from agents.ad_agent.persistence.mysql_store import _mysql_schema, _translate_sql


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


def test_legacy_sqlite_schema_migrates_tenant_columns_before_indexes(tmp_path):
    """An older database must reach the migration that owns tenant indexes."""
    path = tmp_path / "legacy.db"
    import sqlite3

    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL
        );
        CREATE TABLE sessions (
            session_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            account_id TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            metadata TEXT DEFAULT '{}',
            lease_owner TEXT,
            lease_expires_at TEXT
        );
        CREATE TABLE workflows (
            workflow_id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            intent_type TEXT NOT NULL,
            execution_mode TEXT NOT NULL,
            status TEXT NOT NULL,
            metadata TEXT DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            lease_owner TEXT,
            lease_expires_at TEXT
        );
        INSERT INTO schema_migrations(version, applied_at)
        VALUES
            (1, 'legacy'), (2, 'legacy'), (3, 'legacy'), (4, 'legacy'),
            (5, 'legacy'), (6, 'legacy'), (7, 'legacy'), (8, 'legacy'),
            (9, 'legacy'), (10, 'legacy'), (11, 'legacy');
        INSERT INTO sessions(
            session_id, user_id, account_id, created_at, updated_at, metadata
        ) VALUES (
            'legacy-session', 'legacy-user', NULL, '2026-01-01', '2026-01-01',
            '{"tenant_id":"tenant-from-metadata"}'
        );
        """
    )
    conn.commit()
    conn.close()

    store = AdAgentStore(str(path))
    try:
        columns = {
            row[1]
            for row in store._get_conn().execute("PRAGMA table_info(sessions)")
        }
        assert "tenant_id" in columns
        assert store._get_conn().execute(
            "SELECT tenant_id FROM sessions WHERE session_id = ?",
            ("legacy-session",),
        ).fetchone()[0] == "tenant-from-metadata"
        indexes = {
            row[1]
            for row in store._get_conn().execute("PRAGMA index_list(sessions)")
        }
        assert "idx_sessions_tenant" in indexes
    finally:
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
        metadata={"effect_state": "unknown"},
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
    runtime = AdvertisingComposition(require_llm=False, persistence_store=store, features=[])
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


def test_outbox_ack_and_retry_require_the_current_consumer_owner():
    store = AdAgentStore(":memory:")
    now = datetime.now(timezone.utc).isoformat()
    store.insert_outbox_event(OutboxEvent(
        event_id="owned-event", run_id="run", event_type="started",
        payload={}, created_at=now,
    ))
    claimed = store.claim_outbox_events(1, "consumer-a")[0]
    assert store.mark_outbox_delivered(claimed.event_id, "consumer-b") is False
    assert store.mark_outbox_retry(
        claimed.event_id, now, "retry", "consumer-b"
    ) is False
    assert store.mark_outbox_delivered(claimed.event_id, "consumer-a") is True
    store.close()


def test_outbox_can_be_dead_lettered_by_its_current_consumer_owner():
    store = AdAgentStore(":memory:")
    now = datetime.now(timezone.utc).isoformat()
    store.insert_outbox_event(OutboxEvent(
        event_id="dead-letter-event", run_id="run", event_type="started",
        payload={}, created_at=now,
    ))
    claimed = store.claim_outbox_events(1, "consumer-a")[0]
    assert store.mark_outbox_failed(claimed.event_id, "permanent", "consumer-b") is False
    assert store.mark_outbox_failed(claimed.event_id, "permanent", "consumer-a") is True
    snapshot = store.get_monitoring_snapshot()
    assert snapshot["outbox"]["dead_letter"] == 1
    assert snapshot["alerts"]["dead_letter_outbox"] == 1
    store.close()


def test_schedule_claim_ack_and_advance_require_the_current_scheduler_owner():
    store = AdAgentStore(":memory:")
    now = datetime.now(timezone.utc).isoformat()
    store.create_scheduled_task(ScheduledTaskRecord(
        schedule_id="owned-schedule", tenant_id="tenant", user_id="user",
        name="daily", prompt="report", cron_expression="* * * * *",
        next_run_at="2000-01-01T00:00:00+00:00", created_at=now, updated_at=now,
    ))
    schedule, occurrence = store.claim_due_scheduled_tasks(now, "scheduler-a")[0]
    assert store.attach_scheduled_task_run(
        occurrence.schedule_run_id, "task-a", lease_owner="scheduler-b"
    ) is False
    assert store.attach_scheduled_task_run(
        occurrence.schedule_run_id, "task-a", lease_owner="scheduler-a"
    ) is True
    assert store.advance_scheduled_task(
        schedule.schedule_id, schedule.next_run_at, "2099-01-01T00:00:00+00:00",
        lease_owner="scheduler-b",
    ) is False
    assert store.advance_scheduled_task(
        schedule.schedule_id, schedule.next_run_at, "2099-01-01T00:00:00+00:00",
        lease_owner="scheduler-a",
    ) is True
    store.close()


def test_task_mutations_are_scoped_atomically_to_tenant_and_user():
    store = AdAgentStore(":memory:")
    now = datetime.now(timezone.utc).isoformat()
    store.create_task(TaskRecord(
        task_id="scoped-task", tenant_id="tenant-a", user_id="user-a",
        kind="local", status="queued", payload={},
        created_at=now, updated_at=now,
    ))
    assert store.pause_task(
        "scoped-task", tenant_id="tenant-b", user_id="user-b"
    ) is None
    assert store.get_task("scoped-task").status == "queued"
    paused = store.pause_task(
        "scoped-task", tenant_id="tenant-a", user_id="user-a"
    )
    assert paused is not None and paused.status == "paused"
    assert store.resume_task(
        "scoped-task", tenant_id="tenant-b", user_id="user-b"
    ) is None
    resumed = store.resume_task(
        "scoped-task", tenant_id="tenant-a", user_id="user-a"
    )
    assert resumed is not None and resumed.status == "queued"
    assert store.cancel_task(
        "scoped-task", tenant_id="tenant-b", user_id="user-b"
    ) is None
    assert store.get_task("scoped-task").status == "queued"
    store.close()


def test_schedule_mutations_are_scoped_atomically_to_tenant_and_user():
    store = AdAgentStore(":memory:")
    now = datetime.now(timezone.utc).isoformat()
    store.create_scheduled_task(ScheduledTaskRecord(
        schedule_id="scoped-schedule", tenant_id="tenant-a", user_id="user-a",
        name="daily", prompt="report", cron_expression="* * * * *",
        next_run_at="2099-01-01T00:00:00+00:00", created_at=now, updated_at=now,
    ))
    assert store.pause_scheduled_task(
        "scoped-schedule", tenant_id="tenant-b", user_id="user-b"
    ) is None
    assert store.get_scheduled_task("scoped-schedule").status == "active"
    paused = store.pause_scheduled_task(
        "scoped-schedule", tenant_id="tenant-a", user_id="user-a"
    )
    assert paused is not None and paused.status == "paused"
    assert store.resume_scheduled_task(
        "scoped-schedule", "2099-01-01T00:00:00+00:00",
        tenant_id="tenant-b", user_id="user-b",
    ) is None
    assert store.get_scheduled_task("scoped-schedule").status == "paused"
    assert store.delete_scheduled_task(
        "scoped-schedule", tenant_id="tenant-b", user_id="user-b"
    ) is False
    assert store.delete_scheduled_task(
        "scoped-schedule", tenant_id="tenant-a", user_id="user-a"
    ) is True
    store.close()


def test_stale_scheduler_cannot_requeue_a_run_after_lease_loss():
    store = AdAgentStore(":memory:")
    now = datetime.now(timezone.utc).isoformat()
    store.create_scheduled_task(ScheduledTaskRecord(
        schedule_id="lease-schedule", tenant_id="tenant", user_id="user",
        name="daily", prompt="report", cron_expression="* * * * *",
        next_run_at="2000-01-01T00:00:00+00:00", created_at=now, updated_at=now,
    ))
    schedule, occurrence = store.claim_due_scheduled_tasks(now, "scheduler-a")[0]
    assert store.update_scheduled_task_run(
        occurrence.schedule_run_id, "queued", error="stale",
        lease_owner="scheduler-b",
    ) is False
    assert store.update_scheduled_task_run(
        occurrence.schedule_run_id, "queued", error="current",
        lease_owner="scheduler-a",
    ) is True
    store.close()


def test_mysql_translation_preserves_numeric_unique_columns_and_transactions():
    ddl = _mysql_schema(
        "CREATE TABLE execution_event_repairs "
        "(run_id TEXT, seq INTEGER, UNIQUE (run_id, seq));"
    )
    assert "UNIQUE (run_id(191), seq)" in ddl
    assert "ENGINE=InnoDB" in ddl
    assert _translate_sql("BEGIN IMMEDIATE") == "BEGIN"


def test_runtime_can_disable_background_workers_for_in_memory_tests():
    store = AdAgentStore(":memory:")
    runtime = AdvertisingComposition(
        require_llm=False, persistence_store=store, features=[],
        start_background_workers=False,
    )
    assert runtime.outbox_consumer is None
    assert runtime.scheduler is not None
    assert runtime.scheduler.metrics()["state"] == "stopped"
    assert runtime.get_readiness()["checks"]["workers"] is False
    runtime.close(wait=True)
    store.close()


def test_runtime_readiness_includes_backend_and_started_worker_health():
    store = AdAgentStore(":memory:")
    runtime = AdvertisingComposition(
        require_llm=False,
        persistence_store=store,
        features=[],
    )
    try:
        report = runtime.get_readiness()
        assert report["status"] == "not_ready"
        assert report["checks"] == {
            "runtime": True,
            "llm": True,
            "tool_registry": False,
            "persistence": True,
            "workers": True,
        }
        assert report["supervisor"]["backend"]["status"] == "healthy"
        assert report["supervisor"]["components"]["task_executor"]["state"] == "running"
    finally:
        runtime.close(wait=True)
        store.close()


def test_runtime_deployment_health_requires_credentials_for_live_mode():
    runtime = AdvertisingComposition(
        require_llm=False,
        execution_mode="live",
        allow_live_writes=True,
        features=[],
        start_background_workers=False,
    )
    try:
        report = runtime.get_readiness()["deployment_health"]
        assert report["status"] == "not_ready"
        assert report["checks"]["credentials"]["status"] == "unconfigured"
        assert report["blocking_checks"] == ["credentials"]
    finally:
        runtime.close(wait=True)


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


def test_process_reliability_evidence_covers_multi_instance_worker_and_recovery():
    from agents.ad_agent.scripts.production_reliability_evidence import (
        run_reliability_evidence,
    )

    report = run_reliability_evidence(timeout_seconds=15)

    assert report["format_version"] == 2
    assert report["evidence_scope"] == "local_sqlite_shared_persistence_processes"
    assert report["persistence_backend"] == "sqlite"
    assert report["production_deployment_attested"] is False
    assert report["passed"] is True
    assert report["scenario_count"] == 5
    assert all(item["passed"] for item in report["scenarios"])

    scenarios = {item["scenario"]: item for item in report["scenarios"]}
    assert scenarios["session_lease_multi_instance"]["busy_count"] == 1
    assert scenarios["durable_task_claim_multi_instance"]["winner_count"] == 1
    assert scenarios["worker_runtime_route"]["terminal_status"] == "succeeded"
    assert scenarios["worker_runtime_route"]["runtime_entry"] == "AdvertisingComposition.run"
    assert scenarios["worker_runtime_route"]["run_store_status"] == "succeeded"
    worker_liveness = scenarios["worker_liveness_multi_instance"]
    assert worker_liveness["registered_while_running"] is True
    assert worker_liveness["heartbeat_advanced_while_running"] is True
    assert worker_liveness["shutdown_status"] == "stopped"
    assert worker_liveness["lease_cleared"] is True
    assert worker_liveness["error_type"] is None
    assert scenarios["worker_crash_recovery"]["recovered_status"] == "recovery_required"
    assert scenarios["worker_crash_recovery"]["final_status"] == "succeeded"
    assert scenarios["worker_crash_recovery"]["restart_run_store_status"] == "succeeded"


def test_reliability_process_timeout_is_shared_and_children_are_reaped():
    import subprocess
    import sys
    import time

    from agents.ad_agent.scripts.production_reliability_evidence import (
        _read_processes,
    )

    processes = [
        subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(5)"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for _ in range(2)
    ]
    started = time.monotonic()
    results = _read_processes(processes, timeout_seconds=0.15)

    assert time.monotonic() - started < 1.0
    assert all(code != 0 for code, _payload, _error in results)
    assert all(process.poll() is not None for process in processes)


def test_reliability_json_line_read_does_not_block_on_partial_output():
    import subprocess
    import sys
    import time

    from agents.ad_agent.scripts.production_reliability_evidence import (
        _read_json_line,
        _terminate_process,
    )

    process = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "import sys, time; sys.stdout.write('{'); sys.stdout.flush(); time.sleep(5)",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    started = time.monotonic()
    payload = _read_json_line(process.stdout, timeout_seconds=0.15)
    _terminate_process(process)

    assert payload is None
    assert time.monotonic() - started < 1.0
    assert process.poll() is not None


def test_mysql_sandbox_cleanup_reconnects_if_admin_connection_was_lost(
    monkeypatch,
):
    from types import SimpleNamespace

    from agents.ad_agent.scripts import production_reliability_evidence as evidence

    statements = []

    class Cursor:
        def __init__(self, should_fail):
            self.should_fail = should_fail

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, statement):
            if self.should_fail:
                raise ConnectionError("connection lost")
            statements.append(statement)

    class Connection:
        def __init__(self, should_fail):
            self.should_fail = should_fail
            self.closed = False

        def cursor(self):
            return Cursor(self.should_fail)

        def close(self):
            self.closed = True

    original = Connection(should_fail=True)
    replacement = Connection(should_fail=False)
    connector = SimpleNamespace(connect=lambda **_kwargs: replacement)
    monkeypatch.setattr(
        evidence,
        "_mysql_connection_options",
        lambda _url: (connector, {}),
    )

    evidence._drop_mysql_sandbox(
        original,
        "agent_reliability_test",
        admin_url="mysql://localhost/mysql",
    )

    assert original.closed is True
    assert replacement.closed is True
    assert statements == ["DROP DATABASE IF EXISTS `agent_reliability_test`"]


def test_mysql_reliability_admin_url_rejects_remote_database_hosts(monkeypatch):
    import sys
    from types import ModuleType

    from agents.ad_agent.scripts.production_reliability_evidence import (
        _mysql_connection_options,
    )

    monkeypatch.setitem(sys.modules, "pymysql", ModuleType("pymysql"))
    with pytest.raises(ValueError, match="restricted to a local server"):
        _mysql_connection_options("mysql://user:secret@db.example/mysql")
