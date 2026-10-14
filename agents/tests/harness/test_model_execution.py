"""Model execution remains reusable independently of the Agent Run loop."""

import threading
from types import SimpleNamespace
from concurrent.futures import ThreadPoolExecutor

import pytest


def test_agent_delegates_model_capacity_to_the_execution_coordinator():
    from agents.agent_harness import AgentApplication, ModelTurn
    from agents.agent_harness.model_execution import ModelExecutionCoordinator

    app = AgentApplication.create(model=lambda *_: ModelTurn(content="done"))
    assert isinstance(app.agent._models, ModelExecutionCoordinator)
    assert app.prompt("hello").reply == "done"


def test_model_capacity_is_enforced_even_without_a_timeout():
    from agents.agent_harness import AgentApplication, ModelCapacityError

    entered, release = threading.Event(), threading.Event()
    app = AgentApplication.create(
        model=lambda *_: "done", max_inflight_model_invocations=1
    )

    def blocked():
        entered.set()
        assert release.wait(5)
        return "done"

    with ThreadPoolExecutor(max_workers=1) as executor:
        running = executor.submit(app.agent._models.invoke, blocked)
        try:
            assert entered.wait(2)
            with pytest.raises(ModelCapacityError):
                app.agent._models.invoke(lambda: "second")
        finally:
            release.set()
        assert running.result(timeout=5) == "done"
    assert app.agent._models.invoke(lambda: "reused") == "reused"


@pytest.mark.parametrize(
    "option",
    [
        {"max_inflight": 0},
        {"timeout_seconds": 0},
        {"max_retries": -1},
        {"max_stream_delta_chars": 0},
        {"max_total_tokens": 0},
    ],
)
def test_model_execution_options_reject_invalid_bounds(option):
    from agents.agent_harness.model_execution import ModelExecutionOptions

    with pytest.raises(ValueError):
        ModelExecutionOptions(**option)


@pytest.mark.parametrize("exhausted", (False, True))
def test_model_retries_share_one_deadline(exhausted, monkeypatch):
    from agents.agent_harness import AgentApplication
    from agents.agent_harness import model_execution

    clock = SimpleNamespace(now=0.0)
    monkeypatch.setattr(model_execution.time, "monotonic", lambda: clock.now)

    class RateLimited(Exception):
        status_code = 429

    class Model:
        windows = []

        def complete(self, _messages, _tools, request):
            self.windows.append(request.context["model_timeout_seconds"])
            if len(self.windows) == 1:
                clock.now += 2.0 if exhausted else 0.8
                raise RateLimited("temporary limit")
            return "done"

    model = Model()
    app = AgentApplication.create(
        model=model, model_timeout_seconds=1.0,
        model_max_retries=1, model_retry_delay_seconds=0,
    )
    try:
        result = app.prompt("hello")
        if exhausted:
            assert result.status.value == "failed"
            assert result.runtime_signals["model_timeout"] is True
            assert len(model.windows) == 1
        else:
            assert result.reply == "done"
            assert model.windows == pytest.approx([1.0, 0.2])
    finally:
        app.close()


def test_model_rate_limit_obeys_retry_after_within_remaining_budget(monkeypatch):
    from agents.agent_harness import AgentApplication
    from agents.agent_harness import model_execution

    clock = SimpleNamespace(now=0.0)
    waits = []
    monkeypatch.setattr(model_execution.time, "monotonic", lambda: clock.now)
    def sleep(seconds):
        waits.append(seconds)
        clock.now += seconds
    monkeypatch.setattr(model_execution.time, "sleep", sleep)

    class RateLimited(Exception):
        status_code = 429
        response = SimpleNamespace(headers={"retry-after": "3"})

    class Model:
        windows = []

        def complete(self, _messages, _tools, request):
            self.windows.append(request.context["model_timeout_seconds"])
            if len(self.windows) == 1:
                raise RateLimited("temporary limit")
            return "done"

    model = Model()
    app = AgentApplication.create(
        model=model, model_timeout_seconds=20,
        model_max_retries=1, model_retry_delay_seconds=1,
    )
    try:
        assert app.prompt("hello").reply == "done"
        assert sum(waits) == pytest.approx(3)
        assert model.windows == pytest.approx([20, 17])
    finally:
        app.close()


def test_streaming_retry_does_not_repeat_already_emitted_text():
    from agents.agent_harness import AgentApplication, TurnRequest

    class Model:
        calls = 0

        def stream(self, *_args):
            self.calls += 1
            yield "partial"
            raise ConnectionError("connection interrupted")

    model = Model()
    app = AgentApplication.create(model=model, model_max_retries=2)
    try:
        result = app.runtime.run(TurnRequest(user_input="hello", streaming=True))
        assert result.status.value == "failed"
        assert model.calls == 1
    finally:
        app.close()


def test_llm_adapter_passes_the_remaining_deadline_to_the_sdk():
    from agents.agent_harness import TurnRequest
    from agents.agent_harness.core.llm_client import LLMClient

    calls = []
    def complete(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(
                message=SimpleNamespace(content="done", tool_calls=[]), finish_reason="stop",
            )], usage=None,
        )
    client = LLMClient(model="fixture")
    client._client = SimpleNamespace(chat=SimpleNamespace(
        completions=SimpleNamespace(create=complete),
    ))
    client.complete([], [], TurnRequest(
        user_input="hello", context={"model_timeout_seconds": 0.25},
    ))
    assert calls[0]["timeout"] == 0.25
