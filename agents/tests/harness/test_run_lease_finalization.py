"""Lease cleanup precedes the single durable Run completion."""

import threading
from unittest.mock import Mock

import pytest

from agents.agent_harness import AgentRuntime, RunResult, TurnRequest
from agents.agent_harness.runtime_kernel import SessionLease
from agents.agent_harness.turn_pipeline import CallableTurnPipeline
from agents.agent_platform.infrastructure.durable.sqlite_run_store import SQLiteRunStore
from agents.applications.advertising.composition.ad_application_components import AdRunStoreAdapter
from agents.applications.advertising.persistence.session_manager import SessionManager
from agents.applications.advertising.persistence.store import AdAgentStore


@pytest.fixture(params=["generic", "advertising"])
def stores(request):
    leases = AdAgentStore(":memory:")
    leases.create_session("session", "user", metadata={"tenant_id": "tenant"})
    history = SQLiteRunStore(":memory:")
    adapter = history
    read = history.get_run
    if request.param == "advertising":
        adapter = AdRunStoreAdapter(SessionManager(leases), leases)
        read = lambda run: leases.get_execution_run(run).to_dict()
    yield leases, adapter, read
    history.close()
    leases.close()


def run(leases, history, handler, run_id="run"):
    runtime = AgentRuntime(
        pipeline=CallableTurnPipeline(handler), session_manager=leases,
        lease_owner="runtime", lease_seconds=1, run_store=history,
    )
    return runtime.run(TurnRequest(
        user_input="offline", session_id="session", tenant_id="tenant",
        user_id="user", run_id=run_id, turn_id=f"turn-{run_id}",
    ))


@pytest.mark.parametrize("payload", ["result", "dict"])
def test_lost_heartbeat_is_persisted_as_recovery(stores, monkeypatch, payload):
    leases, history, read = stores
    monkeypatch.setattr(leases, "heartbeat_session_lease", lambda *_: False)

    def handler(request):
        assert request.lease_lost_event.wait(3)
        if payload == "result":
            return RunResult(reply="done")
        return {"status": "succeeded", "reply": "done"}

    result = run(leases, history, handler)
    normalized = RunResult.from_payload(result)
    assert normalized.status.value == "recovery_required"
    assert read("run")["status"] == normalized.status.value
    assert read("run")["metadata"]["recovery_required"] is True


def test_release_rejection_preserves_new_owner_and_records_recovery(stores):
    leases, history, read = stores

    def handler(request):
        old = leases.get_session("session")["lease_owner"]
        assert leases.release_session_lease("session", old)
        assert leases.acquire_session_lease("session", "new-owner", 60)
        return RunResult(reply="done")

    result = run(leases, history, handler)
    assert result.status.value == "recovery_required"
    assert read("run")["status"] == "recovery_required"
    assert leases.get_session("session")["lease_owner"] == "new-owner"


def test_completion_happens_once_after_lease_cleanup(stores, monkeypatch):
    leases, history, read = stores
    finish = history.finish_run

    def completed(*args, **kwargs):
        assert leases.get_session("session")["lease_owner"] is None
        return finish(*args, **kwargs)

    completion = Mock(side_effect=completed)
    monkeypatch.setattr(history, "finish_run", completion)
    result = run(leases, history, lambda _: RunResult(reply="done"))
    assert result.status.value == read("run")["status"] == "succeeded"
    assert completion.call_count == 1


def test_previous_run_owner_cannot_heartbeat_or_release_next_run(stores):
    leases, history, read = stores
    owners = []

    def first(_):
        owners.append(leases.get_session("session")["lease_owner"])
        return RunResult(reply="one")

    run(leases, history, first, "first")

    def second(_):
        new_owner = leases.get_session("session")["lease_owner"]
        assert new_owner != owners[0]
        assert not leases.heartbeat_session_lease("session", owners[0], 60)
        assert not leases.release_session_lease("session", owners[0])
        assert leases.get_session("session")["lease_owner"] == new_owner
        return RunResult(reply="two")

    run(leases, history, second, "second")
    assert read("first")["status"] == read("second")["status"] == "succeeded"


def test_release_exception_is_recorded_without_losing_result(stores, monkeypatch):
    leases, history, read = stores
    monkeypatch.setattr(leases, "release_session_lease", Mock(side_effect=OSError("offline")))
    result = run(leases, history, lambda _: RunResult(reply="completed"))
    assert result.reply == "completed"
    assert result.status.value == read("run")["status"] == "recovery_required"
    assert result.runtime_signals["session_lease_release_error_type"] == "OSError"
    assert read("run")["metadata"]["session_lease_release_error_type"] == "OSError"


@pytest.mark.parametrize("release_failure", [False, True])
def test_pipeline_error_remains_primary_after_cleanup(stores, monkeypatch, release_failure):
    leases, history, read = stores
    original = ValueError("pipeline-original")
    if release_failure:
        monkeypatch.setattr(leases, "release_session_lease", Mock(side_effect=OSError("offline")))

    def fail(_):
        raise original

    with pytest.raises(ValueError) as caught:
        run(leases, history, fail)
    assert caught.value is original
    assert read("run")["status"] == ("recovery_required" if release_failure else "failed")
    if release_failure:
        assert any("OSError" in note for note in caught.value.__notes__)


def test_completion_error_does_not_replace_pipeline_error(stores, monkeypatch):
    leases, history, _ = stores
    original = LookupError("pipeline-original")
    monkeypatch.setattr(history, "finish_run", Mock(side_effect=OSError("offline")))

    def fail(_):
        raise original

    with pytest.raises(LookupError) as caught:
        run(leases, history, fail)
    assert caught.value is original
    assert any("finish_run failed" in note for note in caught.value.__notes__)


@pytest.mark.parametrize("rejected", [False, True])
def test_direct_session_lease_keeps_release_failure_contract(rejected):
    lease_store = Mock()
    lease_store.acquire_session_lease.return_value = True
    if rejected:
        lease_store.release_session_lease.return_value = False
    else:
        lease_store.release_session_lease.side_effect = OSError("offline")
    with pytest.raises(RuntimeError if rejected else OSError):
        with SessionLease(lease_store, "session", "owner", 30):
            pass


def test_finalization_keeps_local_lock_and_only_updates_its_run(stores, monkeypatch):
    leases, history, read = stores
    history.start_run(run_id="new-run", turn_id="new-turn", session_id="session",
                      tenant_id="tenant", user_id="user", execution_mode="dry_run")
    finish = history.finish_run
    runtime = AgentRuntime(
        pipeline=CallableTurnPipeline(lambda _: RunResult(reply="done")),
        session_manager=leases, run_store=history,
    )

    def completed(*args, **kwargs):
        lock = runtime._kernel.session_locks["session"]
        attempts = []

        def contend():
            acquired = lock.acquire(blocking=False)
            attempts.append(acquired)
            if acquired:
                lock.release()

        thread = threading.Thread(target=contend)
        thread.start()
        thread.join(timeout=1)
        assert attempts == [False]
        assert args[0] == "old-run"
        assert leases.acquire_session_lease("session", "new-owner", 60)
        return finish(*args, **kwargs)

    monkeypatch.setattr(history, "finish_run", completed)
    result = runtime.run(TurnRequest(user_input="offline", session_id="session", run_id="old-run"))
    assert result.status.value == read("old-run")["status"] == "succeeded"
    assert read("new-run")["status"] == "running"
    assert leases.get_session("session")["lease_owner"] == "new-owner"


def test_late_event_repair_cannot_replace_final_recovery(stores):
    leases, history, read = stores

    def handler(_):
        owner = leases.get_session("session")["lease_owner"]
        leases.release_session_lease("session", owner)
        leases.acquire_session_lease("session", "replacement", 60)
        return RunResult(reply="done")

    result = run(leases, history, handler)
    history.append_event("run", {"seq": 10, "type": "done", "status": "succeeded"})
    history.append_event("run", {"seq": 11, "type": "start", "status": "running"})
    assert read("run")["status"] == result.status.value == "recovery_required"


def test_inflight_old_heartbeat_cannot_touch_next_run(stores, monkeypatch):
    leases, history, read = stores
    entered = threading.Event()
    resume = threading.Event()
    finished = threading.Event()
    heartbeat = leases.heartbeat_session_lease
    heartbeat_results = []

    def delayed(*args):
        entered.set()
        assert resume.wait(5)
        heartbeat_results.append(heartbeat(*args))
        finished.set()
        return heartbeat_results[-1]

    monkeypatch.setattr(leases, "heartbeat_session_lease", delayed)

    def first(_):
        assert entered.wait(3)
        return RunResult(reply="one")

    try:
        first_result = run(leases, history, first, "first")
        assert first_result.status.value == read("first")["status"] == "recovery_required"
        monkeypatch.setattr(leases, "heartbeat_session_lease", heartbeat)

        def second(_):
            owner = leases.get_session("session")["lease_owner"]
            resume.set()
            assert finished.wait(3)
            assert heartbeat_results == [False]
            assert leases.get_session("session")["lease_owner"] == owner
            return RunResult(reply="two")

        assert run(leases, history, second, "second").status.value == "succeeded"
        assert read("first")["status"] == "recovery_required"
    finally:
        resume.set()
        if entered.is_set():
            assert finished.wait(3)


def test_failing_finalizer_does_not_replace_pipeline_error(stores):
    leases, history, _ = stores
    original = LookupError("pipeline-original")

    def fail(_):
        raise original

    runtime = AgentRuntime(pipeline=CallableTurnPipeline(fail), session_manager=leases,
                           run_store=history)
    runtime._kernel.finalize_result = Mock(side_effect=ArithmeticError("offline"))
    with pytest.raises(LookupError) as caught:
        runtime.run(TurnRequest(user_input="offline", session_id="session"))
    assert caught.value is original
    assert any("ArithmeticError" in note for note in caught.value.__notes__)
