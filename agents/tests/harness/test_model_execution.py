"""Model execution remains reusable independently of the Agent Run loop."""

import threading
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
