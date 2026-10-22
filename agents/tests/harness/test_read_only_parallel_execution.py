import threading
from types import SimpleNamespace

from agents.agent_harness import (
    AgentApplication, ModelTurn, StaticToolSource, ToolBinding, ToolCall,
)
from agents.agent_harness.tool_execution import ToolExecutionCoordinator


def test_independent_reads_overlap_but_writes_are_ordered_barriers():
    lock = threading.Lock()
    barrier = threading.Barrier(2)
    active = 0
    peak = 0
    events = []
    calls = [ToolCall(name, name, {}) for name in ("r1", "r2", "write", "r3", "r4")]

    class Model:
        def complete(self, messages, _tools, _request):
            return "done" if any(message.role == "tool" for message in messages) else ModelTurn(
                tool_calls=tuple(calls),
            )

    def read(name):
        def execute(_context, _arguments):
            nonlocal active, peak
            with lock:
                if name in {"r3", "r4"}:
                    assert "write" in events
                active += 1
                peak = max(peak, active)
            barrier.wait(timeout=2)
            with lock:
                events.append(name)
                active -= 1
            return {"name": name}
        return execute

    def write(_context, _arguments):
        with lock:
            assert active == 0
            assert set(events) == {"r1", "r2"}
            events.append("write")
        return {"updated": True}

    app = AgentApplication.create(
        model=Model(), tool_execution="parallel_reads", max_parallel_tools=2,
    )
    app.register_tool_source(StaticToolSource("test", [
        ToolBinding(
            {"name": name, "effect_class": "write" if name == "write" else "read",
             "replay_policy": "idempotent" if name == "write" else "safe"},
            write if name == "write" else read(name),
        )
        for name in ("r1", "r2", "write", "r3", "r4")
    ]))
    try:
        result = app.prompt("run the independent read groups with a write barrier")
        assert result.status.value == "succeeded"
        assert peak == 2
        assert len(events) == 5
        assert events.index("write") == 2
    finally:
        app.close()


def test_read_dependencies_still_wait_for_successful_parents():
    events = []

    class Model:
        def complete(self, messages, _tools, _request):
            if any(message.role == "tool" for message in messages):
                return "done"
            return ModelTurn(tool_calls=(
                ToolCall("first", "first", {}),
                ToolCall("second", "second", {}, depends_on=("first",)),
            ))

    def execute(context, _arguments):
        name = context.tool_call.name
        if name == "second":
            assert events == ["first"]
        events.append(name)
        return {"ok": True}

    app = AgentApplication.create(model=Model(), tool_execution="parallel_reads")
    app.register_tool_source(StaticToolSource("test", [
        ToolBinding({"name": name, "effect_class": "read", "replay_policy": "safe"}, execute)
        for name in ("first", "second")
    ]))
    try:
        assert app.prompt("read in dependency order").status.value == "succeeded"
        assert events == ["first", "second"]
    finally:
        app.close()


def test_missing_replay_metadata_and_unknown_effects_are_serial_barriers():
    definitions = {
        "safe": {"effect_class": "read", "replay_policy": "safe"},
        "missing": {"effect_class": "read"},
        "unsafe": {"effect_class": "read", "replay_policy": "unsafe"},
        "unknown": {"effect_class": "unknown", "replay_policy": "safe"},
    }
    coordinator = ToolExecutionCoordinator(
        tool_catalog=SimpleNamespace(
            get_binding=lambda name: SimpleNamespace(definition=definitions[name]),
        ),
        emit=lambda *_args, **_kwargs: None,
        interrupt_reason=lambda *_: None,
        assert_not_interrupted=lambda *_: None,
        tool_execution="parallel_reads",
    )
    calls = [ToolCall(name, name, {}) for name in definitions]
    assert [[call.name for call in group] for group in coordinator._execution_batches(calls)] == [
        ["safe"], ["missing"], ["unsafe"], ["unknown"],
    ]
