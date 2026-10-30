"""Failed restoration cannot partially replace an existing conversation."""

from copy import deepcopy
from types import SimpleNamespace

import pytest

from agents.agent_harness import AgentMessage, TurnRequest
from agents.agent_harness.agent import AgentState
from agents.agent_harness.state_persistence import AgentStatePersistence, TranscriptPersistenceError


def persistence(checkpoint=None, **kwargs):
    return AgentStatePersistence(
        transcript_store=kwargs.get("transcript_store"),
        checkpoint_store=SimpleNamespace(load_checkpoint=lambda _: checkpoint),
        system_messages=[AgentMessage.system("trusted policy")],
        max_messages=200, max_chars=20000, emit=lambda *_args, **_kwargs: None,
    )


@pytest.mark.parametrize("patch", [
    {"messages": [{"role": "user", "content": "partial"}, {"role": "tool", "metadata": 42}]},
    {"messages": [{"role": "user", "timestamp": "private diagnostic"}]},
    {"messages": "invalid collection"},
    {"messages": [{"role": "unknown", "content": "invalid role"}]},
    {"usage": {"total_tokens": float("nan")}},
    {"usage": {"total_tokens": float("inf")}},
    {"usage": [1, 2]},
])
def test_invalid_checkpoint_preserves_messages_and_usage(patch):
    state = AgentState(messages=[AgentMessage.user("keep my task")], usage={"total_tokens": 12})
    before = deepcopy(state)
    checkpoint = {
        "tenant_id": "default", "user_id": "anonymous", "session_id": "session",
        "messages": [{"role": "user", "content": "partial replacement"}],
        "usage": {"total_tokens": 20}, **patch,
    }
    request = TurnRequest("resume", session_id="session", context={
        "resume_from_checkpoint": True, "resume_run_id": "old-run",
    })
    with pytest.raises(TranscriptPersistenceError) as error:
        persistence(checkpoint).restore_checkpoint(request, state)
    assert "private diagnostic" not in str(error.value)
    assert state == before


def test_failed_hydration_preserves_state_and_can_be_retried():
    payload = [{"role": "user", "content": "new task"}, {"role": "assistant", "metadata": 42}]
    store = SimpleNamespace(load=lambda *_args, **_kwargs: payload)
    io = persistence(transcript_store=store)
    state = AgentState(messages=[AgentMessage.user("previous task")])
    before = deepcopy(state)
    request = TurnRequest("hello", session_id="session")
    with pytest.raises(TranscriptPersistenceError):
        io.hydrate(request, state)
    assert state == before
    payload[1] = {"role": "assistant", "content": "stored answer", "timestamp": 0}
    io.hydrate(request, state)
    assert state.hydrated
    assert state.messages[-1].timestamp == 0
    assert [m.content for m in state.messages] == ["trusted policy", "new task", "stored answer"]


def test_history_is_trimmed_once_after_decoding_all_messages(monkeypatch):
    payload = [message for i in range(1000) for message in (
        {"role": "user", "content": str(i)}, {"role": "assistant", "content": str(i)},
    )]
    io = persistence(transcript_store=SimpleNamespace(load=lambda *_args, **_kwargs: payload))
    sizes = []
    trim = io._trim_completed_turns

    def record_trim(state):
        sizes.append(len(state.messages))
        trim(state)

    monkeypatch.setattr(io, "_trim_completed_turns", record_trim)
    state = AgentState()
    io.hydrate(TurnRequest("hi", session_id="session"), state)
    assert sizes == [2001]
    assert len(state.messages) <= 200
    assert state.messages[1].role == "user"
    assert state.messages[-1].content == "999"


@pytest.mark.parametrize("timestamp", [float("nan"), float("inf"), -1, True])
def test_invalid_persisted_timestamps_fail_closed(timestamp):
    with pytest.raises(TranscriptPersistenceError):
        persistence().message_from_payload({"role": "user", "timestamp": timestamp})


def test_failed_resume_does_not_poison_the_next_conversation_turn():
    from agents.agent_harness import AgentApplication, RunStatus

    checkpoint = {
        "tenant_id": "default", "user_id": "anonymous", "session_id": "session",
        "messages": [{"role": "user", "content": "partial replacement"}],
        "usage": {"total_tokens": float("inf")},
    }
    seen = []

    def model(messages, _tools, _request):
        seen.append([m.content for m in messages])
        return "ok"

    app = AgentApplication.create(
        model=model, checkpoint_store=SimpleNamespace(load_checkpoint=lambda _: checkpoint),
    )
    try:
        assert app.prompt("keep original task", session_id="session").status == RunStatus.SUCCEEDED
        failed = app.prompt("resume", session_id="session", context={
            "resume_from_checkpoint": True, "resume_run_id": "old",
        })
        assert failed.status == RunStatus.RECOVERY_REQUIRED
        assert len(seen) == 1
        assert app.prompt("continue", session_id="session").status == RunStatus.SUCCEEDED
        assert "keep original task" in seen[-1]
        assert "partial replacement" not in seen[-1]
    finally:
        app.close()


@pytest.mark.parametrize("save_result", [False, "raise"])
def test_checkpoint_failure_stops_before_the_next_tool_batch(save_result):
    from agents.agent_harness import AgentApplication, ModelTurn, RunStatus, StaticToolSource, ToolBinding, ToolCall

    calls, model_calls, events = [], [], []

    def save(*_args):
        if save_result == "raise":
            raise OSError("private storage diagnostic")
        return save_result

    def model(*_args):
        model_calls.append(len(model_calls))
        if len(model_calls) == 1:
            return ModelTurn(tool_calls=[ToolCall("read", "lookup", {})])
        return ModelTurn(content="continued despite failed checkpoint")

    app = AgentApplication.create(
        model=model, event_callback=events.append,
        checkpoint_store=SimpleNamespace(save_checkpoint=save),
    )
    app.register_tool_source(StaticToolSource("fixture", [ToolBinding(
        {"name": "lookup", "effect_class": "read"},
        lambda *_args: calls.append("lookup") or {"success": True, "data": {"id": "record-1"}},
    )]))
    try:
        result = app.prompt("query")
        assert result.status == RunStatus.RECOVERY_REQUIRED
        assert result.recovery_required
        assert calls == ["lookup"]
        assert len(model_calls) == 1
        assert len(result.data["tool_results"]) == 1
        assert any(event["type"] == "checkpoint_error" for event in events)
        assert not any(event["type"] == "checkpoint_saved" for event in events)
        assert "private storage diagnostic" not in str(result.to_dict())
    finally:
        app.close()


def test_agent_message_payload_keeps_tool_pairs_and_structured_content():
    messages = [
        AgentMessage.user("task", timestamp=0),
        AgentMessage.assistant("", metadata={"tool_calls": [{"id": "call", "name": "lookup"}]}),
        AgentMessage.tool({"id": "record-1"}, tool_call_id="call", name="lookup"),
    ]
    io = persistence(transcript_store=SimpleNamespace(load=lambda *_args, **_kwargs: messages))
    state = AgentState()
    io.hydrate(TurnRequest("hi", session_id="session"), state)
    assert state.messages[1:] == messages
