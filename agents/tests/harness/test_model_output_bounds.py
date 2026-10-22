"""Bounded model responses must not truncate valid text or outlive a Run."""

import threading

import pytest

from agents.agent_harness import AgentApplication, ModelTurn, ToolCall


def test_large_stream_delta_is_split_without_losing_any_text():
    class Model:
        def stream(self, *_):
            yield "abcdefghij" * 1000

    events = []
    app = AgentApplication.create(model=Model(), event_callback=events.append)
    try:
        result = app.prompt("hello", streaming=True)
        deltas = [item["delta"] for item in events if item["type"] == "model_delta"]
        assert result.reply == "abcdefghij" * 1000
        assert "".join(deltas) == result.reply
        assert max(map(len, deltas)) <= 4096
    finally:
        app.close()


@pytest.mark.parametrize("streaming", [False, True])
def test_cumulative_model_output_limit_is_not_retried_or_executed(streaming):
    class Model:
        calls = 0
        closed = False

        def complete(self, *_):
            self.calls += 1
            return ModelTurn(content="x" * 101)

        def stream(self, *_):
            self.calls += 1
            try:
                yield "x" * 60
                yield "x" * 41
            finally:
                self.closed = True

    model = Model()
    events = []
    app = AgentApplication.create(
        model=model, model_max_retries=2, max_model_output_chars=100,
        event_callback=events.append,
    )
    try:
        result = app.prompt("hello", streaming=streaming)
        assert result.status.value == "failed"
        assert result.data["error"] == "model_output_limit_exceeded"
        assert result.reply
        assert model.calls == 1
        assert sum(len(item["delta"]) for item in events if item["type"] == "model_delta") <= 100
        if streaming:
            assert model.closed
    finally:
        app.close()


def test_empty_stream_chunks_are_bounded_and_iterator_is_closed():
    class Model:
        consumed = 0
        closed = False

        def stream(self, *_):
            try:
                for _ in range(100):
                    self.consumed += 1
                    yield {"delta": ""}
            finally:
                self.closed = True

    model = Model()
    app = AgentApplication.create(model=model, max_stream_chunks=3)
    try:
        result = app.prompt("hello", streaming=True)
        assert result.data["error"] == "model_output_limit_exceeded"
        assert model.consumed <= 4
        assert model.closed
    finally:
        app.close()


@pytest.mark.parametrize("streaming", [False, True])
def test_model_tool_call_metadata_is_part_of_output_budget(streaming):
    class Model:
        def complete(self, *_):
            return ModelTurn(tool_calls=(
                ToolCall("call", "unknown", {"body": "x" * 500}),
            ))

        def stream(self, *_):
            yield self.complete()

    app = AgentApplication.create(model=Model(), max_model_output_chars=100)
    try:
        result = app.prompt("hello", streaming=streaming)
        assert result.data["error"] == "model_output_limit_exceeded"
        assert result.data["tool_results"] == []
    finally:
        app.close()


def test_timed_out_stream_cannot_emit_late_deltas_into_a_finished_run():
    entered, release, closed = threading.Event(), threading.Event(), threading.Event()

    class Model:
        def stream(self, *_):
            try:
                entered.set()
                assert release.wait(3)
                yield "LATE PRIVATE OUTPUT"
            finally:
                closed.set()

    events = []
    app = AgentApplication.create(
        model=Model(), model_timeout_seconds=0.05, event_callback=events.append,
    )
    try:
        result = app.prompt("hello", streaming=True)
        assert entered.is_set()
        assert result.runtime_signals["model_timeout"]
        release.set()
        assert closed.wait(2)
        assert not any(item["type"] == "model_delta" for item in events)
        assert events[-1]["type"] == "agent_end"
        assert str(result.run_id) not in app.agent._event_sequences
    finally:
        release.set()
        app.close()


def test_stream_closes_generator_after_provider_exception():
    class Model:
        closed = False

        def stream(self, *_):
            try:
                yield "partial"
                raise ConnectionError("broken")
            finally:
                self.closed = True

    model = Model()
    app = AgentApplication.create(model=model)
    try:
        assert app.prompt("hello", streaming=True).status.value == "failed"
        assert model.closed
    finally:
        app.close()


@pytest.mark.parametrize("streaming", [False, True])
def test_model_output_at_the_exact_limit_is_accepted(streaming):
    class Model:
        def complete(self, *_):
            return ModelTurn(content="x" * 100)

        def stream(self, *_):
            yield "x" * 50
            yield "x" * 50
            yield self.complete()

    app = AgentApplication.create(model=Model(), max_model_output_chars=100)
    try:
        result = app.prompt("hello", streaming=streaming)
        assert result.status.value == "succeeded"
        assert result.reply == "x" * 100
    finally:
        app.close()


def test_streamed_tool_calls_preserve_declared_argument_bindings():
    from agents.agent_harness import ToolArgumentBinding, TurnRequest

    app = AgentApplication.create(model=lambda *_: "done")
    try:
        turn = app.agent._models._consume_stream(iter([{
            "tool_calls": [{
                "id": "child", "name": "create_child", "arguments": {},
                "depends_on": ["parent"],
                "argument_bindings": [{
                    "target_field": "parent_id", "source_call_id": "parent",
                    "source_path": "data.id",
                }],
            }],
        }]), TurnRequest(user_input="create"))
        assert turn.tool_calls[0].argument_bindings == (
            ToolArgumentBinding("parent_id", "parent", "data.id"),
        )
    finally:
        app.close()


def test_cancelled_stream_is_closed_and_does_not_retry_or_emit_more_text():
    cancelled = threading.Event()

    class Model:
        closed = False
        calls = 0

        def stream(self, *_):
            self.calls += 1
            try:
                yield "first"
                yield "must not emit"
            finally:
                self.closed = True

    events = []

    def observe(event):
        events.append(event)
        if event["type"] == "model_delta":
            cancelled.set()

    model = Model()
    app = AgentApplication.create(
        model=model, event_callback=observe, model_max_retries=2,
    )
    try:
        result = app.prompt("hello", streaming=True, cancellation_event=cancelled)
        assert result.status.value == "cancelled"
        assert model.closed
        assert model.calls == 1
        assert [item["delta"] for item in events if item["type"] == "model_delta"] == ["first"]
    finally:
        app.close()
