from datetime import datetime, timedelta, timezone

import pytest

from agents.agent_harness.messages import ModelTurn
from agents.agent_platform.data.persistence.models import ExecutionRunRecord
from agents.agent_platform.data.persistence.session_manager import SessionManager
from agents.agent_platform.data.persistence.store import AdAgentStore
from agents.tools.advertising.application.composition.ad_application import AdvertisingComposition


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


def test_application_bootstrap_fails_if_durable_run_recovery_fails(monkeypatch):
    def fail_recovery(_self, _stale_after_seconds):
        raise RuntimeError("run recovery storage failure")

    monkeypatch.setattr(
        SessionManager, "recover_stale_execution_runs", fail_recovery,
    )
    store = AdAgentStore(":memory:")
    try:
        with pytest.raises(RuntimeError, match="run recovery storage failure"):
            AdvertisingComposition(persistence_store=store)
    finally:
        store.close()


def test_run_store_adapter_logs_safe_failure_and_queues_event_repair(caplog):
    from agents.tools.advertising.application.composition.ad_application_components import (
        AdRunStoreAdapter,
    )

    class SessionManagerStub:
        def append_execution_run_event(self, _run_id, _event):
            raise OSError("private provider payload")

    class PersistenceStub:
        def __init__(self):
            self.events = []

        def enqueue_execution_event_repair(self, run_id, event):
            self.events.append((run_id, event))
            return True

    persistence = PersistenceStub()
    adapter = AdRunStoreAdapter(
        SessionManagerStub(), persistence_store=persistence,
    )

    assert adapter.append_event("run-repair", {"type": "tool_started"}) is False
    assert persistence.events == [
        ("run-repair", {"type": "tool_started"}),
    ]
    assert "OSError" in caplog.text
    assert "private provider payload" not in caplog.text


def test_run_store_adapter_surfaces_repair_enqueue_failure():
    from agents.tools.advertising.application.composition.ad_application_components import (
        AdRunStoreAdapter,
    )

    class SessionManagerStub:
        def append_execution_run_event(self, _run_id, _event):
            return False

    class PersistenceStub:
        def enqueue_execution_event_repair(self, _run_id, _event):
            raise OSError("repair store unavailable")

    adapter = AdRunStoreAdapter(
        SessionManagerStub(), persistence_store=PersistenceStub(),
    )
    with pytest.raises(OSError, match="repair store unavailable"):
        adapter.append_event("run-repair", {"type": "tool_started"})


def test_runtime_exposes_durable_latest_run_after_async_free_turn():
    class Model:
        def complete(self, _messages, _tools, _request):
            return ModelTurn(content="你好")

    store = AdAgentStore(":memory:")
    runtime = AdvertisingComposition(
        require_llm=False,
        llm_client=Model(),
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


def test_model_failure_closes_durable_run_instead_of_leaving_it_running():
    class BrokenModel:
        def complete(self, _messages, _tools, _request):
            raise RuntimeError("model transport failed")

    store = AdAgentStore(":memory:")
    runtime = AdvertisingComposition(
        require_llm=False,
        llm_client=BrokenModel(),
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
        assert result["status"] == "failed"
        assert latest["status"] == "failed"
        assert any(
            event.get("type") == "agent_end"
            and event.get("status") == "failed"
            for event in latest["events"]
        )
    finally:
        runtime.close(wait=True)


def test_cancelled_and_partial_runs_have_terminal_timestamps():
    store = AdAgentStore(":memory:")
    store.create_execution_run(_run("cancelled"))
    store.create_execution_run(_run("partial"))

    assert store.update_execution_run("cancelled", status="cancelled")
    assert store.update_execution_run("partial", status="partially_failed")

    cancelled = store.get_execution_run("cancelled")
    partial = store.get_execution_run("partial")
    assert cancelled.status == "cancelled"
    assert cancelled.finished_at
    assert partial.status == "partially_failed"
    assert partial.finished_at
