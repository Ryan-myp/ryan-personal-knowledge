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
    assert result.runtime_signals["observer_error_types"] == ["RuntimeError"]
    assert result.recovery_required is False
    app.close()


def test_harness_keeps_transcripts_isolated_per_session():
    seen = []

    class _SessionModel:
        def complete(self, messages, _tools, request):
            seen.append((
                request.session_id,
                [message.content for message in messages],
            ))
            return f"reply-{request.session_id}"

    app = AgentApplication.create(model=_SessionModel())
    try:
        first = app.prompt("private-a", session_id="session-a")
        second = app.prompt("private-b", session_id="session-b")
        again = app.prompt("follow-up-a", session_id="session-a")

        assert first.reply == "reply-session-a"
        assert second.reply == "reply-session-b"
        assert again.reply == "reply-session-a"
        second_messages = next(
            messages for session_id, messages in seen
            if session_id == "session-b"
        )
        assert "private-a" not in second_messages
        assert "follow-up-a" in seen[-1][1]
    finally:
        app.close()


def test_harness_tool_errors_are_redacted_before_return():
    class _BrokenModel:
        def __init__(self):
            self.calls = 0

        def complete(self, _messages, _tools, _request):
            self.calls += 1
            if self.calls == 1:
                return ModelTurn(
                    tool_calls=(
                        ToolCall("call-1", "broken", {}),
                    ),
                )
            return "done"

    app = AgentApplication.create(model=_BrokenModel())
    app.register_tool_source(StaticToolSource(
        "broken",
        [ToolBinding(
            {"name": "broken"},
            lambda _context, _data: (_ for _ in ()).throw(
                RuntimeError('access_token="do-not-leak"')
            ),
        )],
    ))
    try:
        result = app.prompt("run")
        error_content = next(
            message["content"]
            for message in result.data["messages"]
            if message["role"] == "tool"
        )
        assert "do-not-leak" not in error_content
        assert "<redacted>" in error_content
    finally:
        app.close()


def test_harness_surfaces_run_store_observer_failures_as_recovery():
    class _BrokenStore:
        def start_run(self, **_payload):
            return None

        def append_event(self, _run_id, _event):
            raise RuntimeError("append unavailable")

        def finish_run(self, _run_id, *, status, metadata=None):
            raise RuntimeError("finish unavailable")

    app = AgentApplication.create(
        model=lambda *_args: "done",
        run_store=_BrokenStore(),
    )
    try:
        result = app.prompt("hello")
        assert result.recovery_required is True
        assert result.runtime_signals["run_store_error"] is True
        assert result.status.value == "recovery_required"
    finally:
        app.close()


def test_harness_treats_explicit_run_store_rejection_as_recovery():
    class RejectingStore:
        def start_run(self, **_payload):
            return None

        def append_event(self, _run_id, _event):
            return False

        def finish_run(self, _run_id, *, status, metadata=None):
            return False

    app = AgentApplication.create(
        model=lambda *_args: "done",
        run_store=RejectingStore(),
    )
    try:
        result = app.prompt("hello")
        assert result.status.value == "recovery_required"
        assert result.recovery_required is True
        assert result.runtime_signals["run_store_error"] is True
    finally:
        app.close()


def test_harness_bounds_tools_sent_to_the_model_and_supports_selection():
    seen = []

    def model(_messages, tools, _request):
        seen.append([item["name"] for item in tools])
        return "done"

    app = AgentApplication.create(
        model=model,
        max_tools=2,
        tool_selector=lambda _request, tools: tuple(reversed(tools)),
    )
    app.register_tool_source(StaticToolSource(
        "many",
        [
            ToolBinding({"name": "one"}, lambda _context, _data: "one"),
            ToolBinding({"name": "two"}, lambda _context, _data: "two"),
            ToolBinding({"name": "three"}, lambda _context, _data: "three"),
        ],
    ))
    try:
        app.prompt("choose")
        assert seen == [["three", "two"]]
    finally:
        app.close()


def test_harness_retries_transient_model_failure_and_bounds_transcript():
    class FlakyModel:
        def __init__(self):
            self.calls = 0

        def complete(self, messages, _tools, _request):
            self.calls += 1
            if self.calls == 1:
                raise TimeoutError("temporary model failure")
            return f"reply-{len(messages)}"

    model = FlakyModel()
    app = AgentApplication.create(
        model=model,
        model_max_retries=1,
        max_transcript_messages=4,
        max_transcript_chars=200,
    )
    try:
        for index in range(4):
            result = app.prompt(f"message-{index}", session_id="bounded")
            assert result.status.value == "succeeded"
        assert model.calls == 5
        messages = app.agent.state.messages
        assert len(messages) <= 4
        assert sum(len(str(message.content)) for message in messages) <= 200
    finally:
        app.close()


def test_harness_run_store_start_failure_returns_recovery_required():
    class BrokenStore:
        def start_run(self, **_payload):
            raise RuntimeError("store unavailable")

        def append_event(self, _run_id, _event):
            return True

        def finish_run(self, _run_id, *, status, metadata=None):
            return True

    app = AgentApplication.create(
        model=lambda *_args: "must not execute",
        run_store=BrokenStore(),
    )
    try:
        result = app.prompt("hello")
        assert result.status.value == "recovery_required"
        assert result.recovery_required is True
        assert result.runtime_signals["run_store_error"] is True
        assert result.runtime_signals["run_store_phase"] == "start"
    finally:
        app.close()
