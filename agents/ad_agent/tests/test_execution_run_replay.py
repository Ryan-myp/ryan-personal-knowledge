from datetime import datetime, timedelta, timezone

from agents.ad_agent.persistence.models import ExecutionRunRecord
from agents.ad_agent.persistence.store import AdAgentStore
from agents.ad_agent.runtime.runtime import AdvertisingComposition


def _run(run_id="run-1", *, updated_at=None):
    now = updated_at or datetime.now(timezone.utc).isoformat()
    return ExecutionRunRecord(
        run_id=run_id,
        session_id="session-1",
        turn_id=run_id,
        user_id="user-1",
        tenant_id="tenant-1",
        created_at=now,
        updated_at=now,
    )


def test_execution_run_events_are_idempotent_and_scoped():
    store = AdAgentStore(":memory:")
    store.create_execution_run(_run())
    start = {
        "type": "start", "event_type": "start", "seq": 1,
        "status": "running", "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    assert store.append_execution_run_event("run-1", start)
    assert not store.append_execution_run_event("run-1", start)
    assert store.get_execution_run("run-1", "other-user", "tenant-1") is None
    assert store.list_execution_run_events("run-1") == [start]


def test_stale_execution_run_becomes_recovery_required_with_event():
    store = AdAgentStore(":memory:")
    stale = (datetime.now(timezone.utc) - timedelta(seconds=600)).isoformat()
    store.create_execution_run(_run("stale", updated_at=stale))
    assert store.recover_stale_execution_runs(300) == 1
    record = store.get_execution_run("stale")
    assert record.status == "recovery_required"
    assert store.list_execution_run_events("stale")[-1]["type"] == "recovery_required"


def test_runtime_exposes_durable_latest_run_after_async_free_turn():
    store = AdAgentStore(":memory:")
    runtime = AdvertisingComposition(
        require_llm=False,
        persistence_store=store,
        offline_mode=True,
        enforce_account_scope=False,
    )
    try:
        result = runtime.run("你好", user_id="user-1", tenant_id="tenant-1")
        latest = runtime.get_latest_run(
            result["session_id"], user_id="user-1", tenant_id="tenant-1"
        )
        assert latest["run_id"] == result["run_id"]
        assert latest["events"]
        assert latest["status"] == "succeeded"
    finally:
        runtime.close(wait=True)


def test_parser_failure_closes_durable_run_instead_of_leaving_it_running():
    class BrokenParser:
        def parse(self, _user_input, _context):
            raise RuntimeError("model transport failed")

    store = AdAgentStore(":memory:")
    runtime = AdvertisingComposition(
        require_llm=False,
        intent_parser=BrokenParser(),
        persistence_store=store,
        offline_mode=True,
        enforce_account_scope=False,
        features=[],
    )
    try:
        result = runtime.run("请帮我分析", user_id="user-1", tenant_id="tenant-1")
        latest = runtime.get_latest_run(
            result["session_id"], user_id="user-1", tenant_id="tenant-1"
        )
        assert result["reply"] == "暂时无法完成请求理解，请稍后重试。"
        assert latest["status"] == "failed"
        assert latest["metadata"]["reason"] == "intent_parse_failed"
        assert any(
            event.get("type") == "agent_end"
            and event.get("status") == "failed"
            for event in latest["events"]
        )
    finally:
        runtime.close(wait=True)
