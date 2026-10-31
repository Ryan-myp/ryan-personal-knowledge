from datetime import datetime, timedelta, timezone

from agents.applications.advertising.persistence.models import ExecutionRunRecord
from agents.applications.advertising.persistence.store import AdAgentStore


def make_run(store, name, *, user="u"):
    old = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    store.create_session(name, user, metadata={"tenant_id": "t"})
    store.create_execution_run(ExecutionRunRecord(
        run_id=name, session_id=name, turn_id=name, user_id=user, tenant_id="t",
        created_at=old, updated_at=old,
    ))


def test_stale_sweep_respects_live_session_lease_and_never_replays_tools():
    with_store = AdAgentStore(":memory:")
    try:
        make_run(with_store, "live")
        make_run(with_store, "abandoned")
        assert with_store.acquire_session_lease("live", "worker", 300)
        assert with_store.recover_stale_execution_runs(300) == 1
        assert with_store.get_execution_run("live").status == "running"
        row = with_store.get_execution_run("abandoned")
        assert row.status == "recovery_required"
        assert row.metadata["effect_state"] == "unknown"
        assert with_store.recover_stale_execution_runs(300) == 0
        assert len(with_store.list_execution_run_events("abandoned")) == 1
    finally:
        with_store.close()


def test_recovery_inbox_is_scoped_bounded_and_actionable():
    store = AdAgentStore(":memory:")
    try:
        make_run(store, "visible")
        make_run(store, "hidden", user="other")
        store.create_workflow(
            "visible-workflow", "visible", "update_campaign", "live",
            status="recovery_required",
        )
        store.create_workflow(
            "hidden-workflow", "hidden", "update_campaign", "live",
            status="recovery_required",
        )
        store.recover_stale_execution_runs(300)
        snapshot = store.get_monitoring_snapshot(tenant_id="t", user_id="u")
        inbox = snapshot["recovery"]
        assert {row["id"] for row in inbox["items"]} == {
            "visible", "visible-workflow",
        }
        assert {
            row["kind"]: row["next_action"] for row in inbox["items"]
        } == {
            "run": "inspect_run_evidence",
            "workflow": "inspect_workflow_evidence",
        }
        assert all(
            row["automatic_replay_allowed"] is False for row in inbox["items"]
        )
        assert inbox["total"] == 2
        assert inbox["scope"] == "runs_tasks_and_workflows"
        assert "hidden" not in str(inbox)
    finally:
        store.close()


def test_periodic_repair_performs_lease_aware_sweep():
    from agents.agent_platform.infrastructure.durable.event_repair import ExecutionEventRepairConsumer
    store = AdAgentStore(":memory:")
    try:
        make_run(store, "stale")
        consumer = ExecutionEventRepairConsumer(store)
        consumer.tick()
        assert store.get_execution_run("stale").status == "recovery_required"
        assert consumer.metrics()["recovered_runs_total"] == 1
    finally:
        store.close()


def test_sweep_releases_expired_lease_only_after_classifying_run():
    store = AdAgentStore(":memory:")
    try:
        make_run(store, "expired")
        old = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        store._get_conn().execute(
            "UPDATE sessions SET lease_owner = ?, lease_expires_at = ? WHERE session_id = ?",
            ("expired-worker", old, "expired"),
        )
        store._get_conn().commit()
        assert store.recover_stale_execution_runs(300) == 1
        assert store.get_session("expired")["lease_owner"] is None
        assert store.get_execution_run("expired").status == "recovery_required"
    finally:
        store.close()
