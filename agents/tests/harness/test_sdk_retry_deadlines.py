"""SDK repair requests share one deadline and trusted cancellation tokens."""

import threading
from types import SimpleNamespace

import pytest

from agents.agent_harness import AgentMessage, TurnRequest
from agents.agent_harness.core import llm_client
from agents.agent_harness.core.llm_client import LLMClient


def _response(content=""):
    return SimpleNamespace(
        choices=[SimpleNamespace(
            message=SimpleNamespace(content=content, tool_calls=[]),
            finish_reason="stop",
        )],
        usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1),
    )


def _client(complete):
    client = LLMClient(model="fixture", timeout_seconds=1)
    client._client = SimpleNamespace(chat=SimpleNamespace(
        completions=SimpleNamespace(create=complete),
    ))
    return client


def test_sdk_repair_uses_remaining_timeout_instead_of_resetting(monkeypatch):
    now = [0.0]
    calls = []
    monkeypatch.setattr(
        llm_client, "time", SimpleNamespace(monotonic=lambda: now[0]), raising=False,
    )

    def complete(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            now[0] += 0.8
            return _response()
        return _response("done")

    result = _client(complete).complete(
        [AgentMessage.user("hello")], (), TurnRequest("hello"),
    )
    assert result.content == "done"
    assert [call["timeout"] for call in calls] == pytest.approx([1.0, 0.2])


def test_sdk_does_not_retry_or_accept_response_after_its_deadline(monkeypatch):
    from agents.agent_harness import ModelTimeoutError

    now = [0.0]
    calls = []
    monkeypatch.setattr(
        llm_client, "time", SimpleNamespace(monotonic=lambda: now[0]), raising=False,
    )

    def complete(**kwargs):
        calls.append(kwargs)
        now[0] += 2.0
        return _response()

    with pytest.raises(ModelTimeoutError):
        _client(complete).complete([AgentMessage.user("hello")], (), TurnRequest("hello"))
    assert len(calls) == 1


@pytest.mark.parametrize("token_name", ["cancellation_event", "lease_lost_event"])
def test_sdk_cannot_repair_after_cancellation_or_lease_loss(token_name):
    from agents.agent_harness.model_limits import ModelInvocationStoppedError

    token = threading.Event()
    calls = []

    def complete(**kwargs):
        calls.append(kwargs)
        token.set()
        return _response()

    with pytest.raises(ModelInvocationStoppedError):
        _client(complete).complete(
            [AgentMessage.user("hello")], (), TurnRequest("hello", **{token_name: token}),
        )
    assert len(calls) == 1


@pytest.mark.parametrize("timeout", [float("nan"), float("inf"), True, 0, -1])
def test_sdk_timeout_configuration_must_be_finite_and_positive(timeout):
    with pytest.raises(ValueError):
        LLMClient(model="fixture", timeout_seconds=timeout)


def test_sdk_parent_absolute_deadline_includes_worker_and_preparation_time(monkeypatch):
    now = [100.0]
    calls = []
    monkeypatch.setattr(
        llm_client, "time", SimpleNamespace(monotonic=lambda: now[0]),
    )

    def complete(**kwargs):
        calls.append(kwargs)
        return _response("done")

    client = _client(complete)
    original = client._provider_messages

    def prepare(messages):
        now[0] += 0.1
        return original(messages)

    monkeypatch.setattr(client, "_provider_messages", prepare)
    client.complete([AgentMessage.user("hello")], (), TurnRequest(
        "hello", context={"_harness_model_deadline": 100.25},
    ))
    assert calls[0]["timeout"] == pytest.approx(0.15)
