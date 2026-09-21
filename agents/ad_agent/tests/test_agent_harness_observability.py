from agents.agent_harness import (
    AgentApplication,
    InMemoryMetrics,
    ModelTurn,
    StaticToolSource,
    ToolBinding,
    ToolCall,
)


class _Model:
    def __init__(self):
        self.calls = 0

    def complete(self, _messages, _tools, _request):
        self.calls += 1
        if self.calls == 1:
            return ModelTurn(
                content="",
                tool_calls=(ToolCall("call-1", "lookup", {"query": "hello"}),),
            )
        return "done"


def test_harness_metrics_track_runs_and_tools_without_payloads():
    metrics = InMemoryMetrics()
    app = AgentApplication.create(model=_Model(), metrics=metrics)
    app.register_tool_source(StaticToolSource(
        "docs",
        [ToolBinding(
            {"name": "lookup"},
            lambda _context, data: {"secret": "must-not-be-metric", "ok": bool(data)},
        )],
    ))

    result = app.prompt("hello")
    snapshot = metrics.snapshot()

    assert result.status.value == "succeeded"
    assert snapshot["counters"]["runs_started"] == 1
    assert snapshot["counters"]["runs_finished.succeeded"] == 1
    assert snapshot["counters"]["tool_calls_finished"] == 1
    assert "must-not-be-metric" not in str(snapshot)
    assert snapshot["durations"]["run_duration"]["count"] == 1
    assert snapshot["durations"]["tool_duration"]["count"] == 1
    assert snapshot["in_flight"] == 0
    app.close()


def test_harness_metric_observer_failure_does_not_fail_a_run():
    class BrokenMetrics:
        def observe(self, _event):
            raise RuntimeError("metrics unavailable")

    app = AgentApplication.create(model=lambda *_args: "done", metrics=BrokenMetrics())
    result = app.prompt("hello")
    assert result.status.value == "succeeded"
    app.close()
