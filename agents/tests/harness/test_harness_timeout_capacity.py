import threading
import time
from types import SimpleNamespace

import pytest

from agents.agent_harness.messages import AgentMessage, ToolCall
from agents.agent_harness.agent import Agent, ModelCapacityError, ModelTimeoutError
from agents.agent_harness.runtime_kernel import TurnRequest
from agents.agent_harness.tool_execution import (
    ToolCallContext,
    ToolCapacityError,
    ToolExecutionCoordinator,
)


def test_timed_out_tool_keeps_capacity_until_underlying_call_exits():
    entered = threading.Event()
    release = threading.Event()

    def blocked(_context, _arguments):
        entered.set()
        release.wait(2)
        return {"success": True}

    coordinator = ToolExecutionCoordinator(
        tool_catalog=None,
        emit=lambda *_args, **_kwargs: None,
        interrupt_reason=lambda _request: None,
        assert_not_interrupted=lambda _request: None,
        tool_timeout_seconds=0.02,
        max_inflight_tool_invocations=1,
    )
    request = TurnRequest(user_input="test")
    call = ToolCall(id="one", name="blocked")
    context = ToolCallContext(
        request=request,
        assistant_message=AgentMessage.assistant(""),
        tool_call=call,
        state=None,
    )
    binding = SimpleNamespace(executor=blocked)
    try:
        with pytest.raises(TimeoutError):
            coordinator._invoke_tool(binding, context, call, {})
        assert entered.is_set()
        with pytest.raises(ToolCapacityError):
            coordinator._invoke_tool(binding, context, call, {})
    finally:
        release.set()
    deadline = time.monotonic() + 2
    while True:
        try:
            output, _, _ = coordinator._invoke_tool(binding, context, call, {})
            break
        except ToolCapacityError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.01)
    assert output == {"success": True}


def test_timed_out_model_keeps_capacity_until_provider_call_exits():
    entered = threading.Event()
    release = threading.Event()

    def blocked():
        entered.set()
        release.wait(2)
        return "done"

    agent = Agent(
        model=lambda *_args, **_kwargs: "unused",
        model_timeout_seconds=0.02,
        max_inflight_model_invocations=1,
    )
    try:
        with pytest.raises(ModelTimeoutError):
            agent._models.invoke(blocked)
        assert entered.is_set()
        with pytest.raises(ModelCapacityError):
            agent._models.invoke(blocked)
    finally:
        release.set()
    deadline = time.monotonic() + 2
    while True:
        try:
            assert agent._models.invoke(blocked) == "done"
            break
        except ModelCapacityError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.01)
