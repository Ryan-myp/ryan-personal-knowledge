"""Model input bounds preserve policy and complete conversation turns."""

from types import SimpleNamespace

import pytest

from agents.agent_harness import AgentApplication, AgentMessage, ModelTurn, TurnRequest


def test_input_window_evicts_whole_old_turns_without_mutating_the_transcript():
    from agents.agent_harness.model_limits import bound_model_messages, model_input_chars

    messages = [
        AgentMessage.system("protected policy"),
        AgentMessage.user("old " * 100),
        AgentMessage.assistant("", metadata={"tool_calls": [
            {"id": "old-call", "name": "lookup", "arguments": {"id": "1"}},
        ]}),
        AgentMessage.tool("old evidence", tool_call_id="old-call", name="lookup"),
        AgentMessage.assistant("old answer"),
        AgentMessage.user("current request", turn_id="current"),
        AgentMessage.assistant("", metadata={"tool_calls": [
            {"id": "new-call", "name": "lookup", "arguments": {"id": "2"}},
        ]}),
        AgentMessage.tool("new evidence", tool_call_id="new-call", name="lookup"),
    ]
    original = list(messages)
    expected = [messages[0], *messages[5:]]
    limit = model_input_chars(expected, ())

    bounded = bound_model_messages(messages, (), max_chars=limit)

    assert bounded == expected
    assert messages == original
    assert model_input_chars(bounded, ()) == limit
    assert all(message.tool_call_id != "old-call" for message in bounded)


def test_input_window_charges_tools_and_call_arguments_not_only_content():
    from agents.agent_harness.model_limits import (
        ModelInputLimitError, bound_model_messages, model_input_chars,
    )

    messages = [
        AgentMessage.system("policy"),
        AgentMessage.user("now"),
        AgentMessage.assistant("", metadata={"tool_calls": [
            {"id": "call", "name": "lookup", "arguments": {"body": "x" * 1000}},
        ]}),
    ]
    tool = {"name": "lookup", "description": "lookup", "input_schema": {
        "properties": {"body": {"type": "string", "enum": ["x" * 1000]}},
    }}
    size = model_input_chars(messages, (tool,))
    assert size > 2000
    with pytest.raises(ModelInputLimitError):
        bound_model_messages(messages, (tool,), max_chars=size - 1)
    assert bound_model_messages(messages, (tool,), max_chars=size) == messages


def test_input_window_keeps_all_system_messages_and_never_slices_current_input():
    from agents.agent_harness.model_limits import ModelInputLimitError, bound_model_messages

    messages = [
        AgentMessage.system("POLICY"),
        AgentMessage.system("ADVISORY " * 100, metadata={"context_type": "skills"}),
        AgentMessage.user("CURRENT " * 100),
    ]
    with pytest.raises(ModelInputLimitError) as caught:
        bound_model_messages(messages, (), max_chars=100)
    assert "CURRENT" not in str(caught.value)
    assert "ADVISORY" not in str(caught.value)
    assert caught.value.safe_reason_code == "model_input_limit_exceeded"


def test_harness_rejects_oversized_current_input_before_calling_model():
    calls = []
    app = AgentApplication.create(
        model=lambda *_: calls.append("called"),
        max_model_input_chars=9000,
        max_transcript_chars=1000,
    )
    try:
        result = app.prompt("PRIVATE REQUEST " * 1000)
        assert result.status.value == "failed"
        assert result.data["error"] == "model_input_limit_exceeded"
        assert result.reply
        assert calls == []
        assert "PRIVATE REQUEST" not in result.reply
    finally:
        app.close()


def test_harness_limits_context_plus_tools_plus_history_and_emits_sizes_only():
    class Model:
        inputs = []

        def complete(self, messages, _tools, request):
            self.inputs.append(tuple(messages))
            assert request.context["max_model_input_chars"] == 11_000
            return ModelTurn(content="done")

    model = Model()
    events = []
    app = AgentApplication.create(
        model=model, max_model_input_chars=11_000, event_callback=events.append,
    )
    try:
        assert app.prompt("old " * 500, session_id="long").status.value == "succeeded"
        result = app.prompt("new " * 500, session_id="long")
        assert result.status.value == "succeeded"
        assert not any("old old" in str(message.content) for message in model.inputs[-1])
        assert any(
            "old old" in str(message.content)
            for message in app.agent._state_for("long").messages
        )
        event = next(item for item in events if item["type"] == "model_input_trimmed")
        assert event["removed_messages"] == 2
        assert event["input_chars"] <= 11_000
        assert "old old" not in str(event)
    finally:
        app.close()


def test_oversized_user_input_does_not_erase_previously_kept_transcript():
    app = AgentApplication.create(
        model=lambda *_: "done", max_transcript_chars=1000,
    )
    try:
        assert app.prompt("earlier", session_id="kept").status.value == "succeeded"
        before = app.agent._state_for("kept").snapshot()
        result = app.prompt("x" * 1001, session_id="kept")
        assert result.data["error"] == "model_input_limit_exceeded"
        assert app.agent._state_for("kept").snapshot() == before
    finally:
        app.close()


@pytest.mark.parametrize("value", [0, -1, True, 1.5, float("inf")])
def test_input_and_output_limits_are_positive_integers(value):
    from agents.agent_platform.governance.policy import GovernancePolicy

    for name in ("max_model_input_chars", "max_model_output_chars", "max_stream_chunks"):
        with pytest.raises(ValueError):
            AgentApplication.create(model=lambda *_: "done", **{name: value})
        with pytest.raises(ValueError):
            GovernancePolicy(**{name: value})


def test_sdk_rechecks_size_after_attaching_document_text():
    from agents.agent_harness import InputMedia
    from agents.agent_harness.core.llm_client import LLMClient
    from agents.agent_harness.model_limits import ModelInputLimitError

    calls = []
    client = LLMClient(model="fixture")
    client._client = SimpleNamespace(chat=SimpleNamespace(
        completions=SimpleNamespace(create=lambda **kw: calls.append(kw)),
    ))
    with pytest.raises(ModelInputLimitError):
        client.complete([AgentMessage.user("analyze")], (), TurnRequest(
            "analyze",
            context={"max_model_input_chars": 200},
            input_media=(InputMedia(
                attachment_id="report", filename="report.csv", media_type="text/csv",
                content=b"csv", extracted_text="row,value\n" * 100,
            ),),
        ))
    assert calls == []


def test_sdk_rechecks_budget_before_internal_empty_reply_repair():
    from agents.agent_harness.core.llm_client import LLMClient
    from agents.agent_harness.model_limits import ModelInputLimitError

    calls = []

    def complete(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(
                message=SimpleNamespace(content="", tool_calls=[]),
                finish_reason="stop",
            )],
            usage=None,
        )

    client = LLMClient(model="fixture")
    client._client = SimpleNamespace(chat=SimpleNamespace(
        completions=SimpleNamespace(create=complete),
    ))
    with pytest.raises(ModelInputLimitError):
        client.complete([AgentMessage.user("hello")], (), TurnRequest(
            "hello", context={"max_model_input_chars": 100},
        ))
    assert len(calls) == 1


def test_binary_images_are_not_mistaken_for_text_context_but_text_stays_bounded():
    from agents.agent_harness.model_limits import provider_input_chars

    text = {"type": "text", "text": "analyze this image"}
    small = {"type": "image_url", "image_url": {"url": "data:image/png;base64,AA=="}}
    large = {"type": "image_url", "image_url": {"url": "data:image/png;base64," + "A" * 10000}}
    assert provider_input_chars([{"role": "user", "content": [text, small]}], ()) == (
        provider_input_chars([{"role": "user", "content": [text, large]}], ())
    )
    assert provider_input_chars([{"role": "user", "content": [text, large]}], ()) > len(text["text"])


def test_input_window_removes_orphan_prefix_even_when_it_fits():
    from agents.agent_harness.model_limits import bound_model_messages

    messages = [
        AgentMessage.system("policy"),
        AgentMessage.tool("orphan", tool_call_id="missing", name="lookup"),
        AgentMessage.assistant("old response"),
        AgentMessage.user("current"),
    ]
    assert bound_model_messages(messages, (), max_chars=10000) == [messages[0], messages[-1]]


def test_current_request_cannot_raise_trusted_input_budget():
    app = AgentApplication.create(model=lambda *_: "not called", max_model_input_chars=100)
    try:
        result = app.prompt("hello", context={"max_model_input_chars": 1_000_000})
        assert result.data["error"] == "model_input_limit_exceeded"
    finally:
        app.close()
