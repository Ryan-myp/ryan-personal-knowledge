import threading
import time
from contextvars import ContextVar
from pathlib import Path

from agents.agent_harness import (
    AgentRuntime,
    RunResult,
    RunStatus,
    RuntimePorts,
    SequentialTurnPipeline,
    TurnRequest,
)


def _ports(calls):
    return RuntimePorts(
        session_manager=None,
        session_locks={},
        session_locks_guard=threading.RLock(),
        lease_owner="test",
        lease_seconds=30,
        mode_context=ContextVar("harness_test_mode", default=None),
        validate_mode=lambda value: value or "dry_run",
        resolve_mode=lambda _tenant, _user, _requested: "dry_run",
        assert_ready=lambda: None,
        ensure_session=lambda request: calls.append(("ensure", request)),
    )


def test_agent_harness_is_importable_without_ad_agent_runtime():
    import agents.agent_harness as harness

    assert harness.__version__ == "0.1.0"
    assert (Path(__file__).resolve().parents[2] / "agent_harness" / "pyproject.toml").is_file()

    calls = []
    pipeline = SequentialTurnPipeline(
        [
            lambda context: {
                "run_id": context.request.run_id,
                "turn_id": context.request.turn_id,
            }
        ]
    )
    runtime = AgentRuntime(ports=_ports(calls), pipeline=pipeline)

    result = runtime.run(TurnRequest(user_input="hello"))

    assert result["run_id"]
    assert result["turn_id"]
    assert calls[0][0] == "ensure"


def test_ad_application_does_not_publish_a_second_harness_import_surface():
    """The application must use the standalone Harness package directly."""
    from pathlib import Path

    core = Path(__file__).resolve().parents[1] / "core"
    forbidden = {
        "agent_runtime.py",
        "runtime_kernel.py",
        "tool_sources.py",
        "turn_pipeline.py",
    }
    assert forbidden.isdisjoint(
        path.name for path in core.iterdir() if path.is_file()
    )


def test_run_result_normalizes_application_payload_without_losing_data():
    result = RunResult.from_payload(
        {
            "run_id": "run-1",
            "turn_id": "turn-1",
            "reply": "done",
            "needs_confirmation": True,
            "effect_state": "planned",
            "custom": {"value": 1},
        }
    )

    assert result.status == RunStatus.AWAITING_INPUT
    assert result.run_id == "run-1"
    assert result.reply == "done"
    assert result.data["custom"] == {"value": 1}
    assert result.to_dict()["needs_input"] is True

    assert RunResult.from_payload(
        {"results": [{"success": False}]}
    ).status == RunStatus.FAILED
    assert RunResult.from_payload(
        {"results": [{"success": True}, {"success": False}]}
    ).status == RunStatus.PARTIALLY_FAILED


def test_run_result_treats_audit_failure_as_recovery_required():
    result = RunResult.from_payload({
        "status": "succeeded",
        "runtime_signals": {"audit_error": True},
    })
    assert result.status == RunStatus.RECOVERY_REQUIRED
    assert result.recovery_required is True


def test_agent_harness_owns_durable_run_lifecycle_when_run_store_is_bound():
    events = []

    class Store:
        def start_run(self, **payload):
            events.append(("start", payload["run_id"]))

        def append_event(self, run_id, event):
            events.append(("event", run_id, event["type"]))

        def finish_run(self, run_id, *, status, metadata=None):
            events.append(("finish", run_id, status, metadata or {}))

    def stage(context):
        context.request.event_callback({"type": "stage.completed"})
        return {"reply": "done"}

    runtime = AgentRuntime(
        ports=_ports([]),
        pipeline=SequentialTurnPipeline([stage]),
        run_store=Store(),
    )

    result = runtime.run(TurnRequest(user_input="hello"))

    run_id = result["run_id"]
    assert events[0] == ("start", run_id)
    assert ("event", run_id, "stage.completed") in events
    assert events[-1][0:3] == ("finish", run_id, "succeeded")


def test_session_lease_loss_marks_a_run_result_for_recovery():
    class LeaseStore:
        def acquire_session_lease(self, _session_id, _owner, _seconds):
            return True

        def heartbeat_session_lease(self, _session_id, _owner, _seconds):
            return False

        def release_session_lease(self, _session_id, _owner):
            return True

    pipeline = SequentialTurnPipeline([
        lambda _context: time.sleep(1.1) or RunResult(reply="done"),
    ])
    runtime = AgentRuntime(
        ports=RuntimePorts(
            session_manager=LeaseStore(),
            session_locks={},
            session_locks_guard=threading.RLock(),
            lease_owner="test",
            lease_seconds=1,
            mode_context=ContextVar("lease_loss_mode", default=None),
            validate_mode=lambda value: value or "dry_run",
            resolve_mode=lambda _tenant, _user, _requested: "dry_run",
            assert_ready=lambda: None,
            ensure_session=lambda _request: None,
        ),
        pipeline=pipeline,
    )

    result = runtime.run(TurnRequest(user_input="hello"))

    assert result.status == RunStatus.RECOVERY_REQUIRED
    assert result.recovery_required is True
    assert result.runtime_signals["session_lease_lost"] is True


def test_agent_runtime_rolls_back_tool_source_when_catalog_refresh_fails():
    from agents.agent_harness import InMemoryToolCatalog, StaticToolSource, ToolBinding

    catalog = InMemoryToolCatalog()
    runtime = AgentRuntime(
        ports=_ports([]),
        pipeline=SequentialTurnPipeline([lambda _context: {}]),
        tool_registry=catalog,
        on_tool_catalog_changed=lambda: (_ for _ in ()).throw(
            RuntimeError("catalog refresh failed")
        ),
    )

    try:
        runtime.register_tool_source(
            StaticToolSource("local", [ToolBinding({"name": "search"}, lambda *_: {})])
        )
    except RuntimeError as error:
        assert "catalog refresh failed" in str(error)
    else:
        raise AssertionError("catalog refresh failure must be surfaced")

    assert catalog.list_tools() == []
