from types import SimpleNamespace

import pytest

from agents.agent_harness.messages import AgentMessage, ToolCall
from agents.agent_harness.runtime_kernel import TurnRequest
from agents.agent_harness.tool_execution import ToolCallContext, ToolExecutionCoordinator


def coordinator(handler, effect="read", **options):
    binding = SimpleNamespace(
        executor=handler,
        definition={"name": "sample", "effect_class": effect, "replay_policy": "never"},
    )
    instance = ToolExecutionCoordinator(
        tool_catalog=SimpleNamespace(get_binding=lambda _name: binding),
        emit=lambda *_args, **_kwargs: None,
        interrupt_reason=lambda _request: None,
        assert_not_interrupted=lambda _request: None,
        **options,
    )
    return instance, binding


def execute(instance):
    return instance.execute_one(
        TurnRequest(user_input="test"), AgentMessage.assistant(""),
        ToolCall(id="one", name="sample"), SimpleNamespace(),
    )


@pytest.mark.parametrize("field", [
    "success", "needs_input", "needs_confirmation", "recovery_required",
])
@pytest.mark.parametrize("value", ["false", 0, 1, None])
def test_malformed_result_flags_cannot_be_reported_as_success(field, value):
    instance, _ = coordinator(lambda *_args: {field: value})
    result = execute(instance)
    assert result["is_error"] is True
    assert "must be boolean" in result["content"]
    assert result["terminate"] is True
    assert result["runtime_signals"]["tool_output_invalid"] is True


def test_write_result_contract_failure_is_recovery_required_not_a_known_rollback():
    effects = []

    def handler(*_args):
        effects.append("committed")
        return {"success": "false"}

    instance, _ = coordinator(handler, effect="write")
    result = execute(instance)
    assert effects == ["committed"]
    assert result["is_error"] is True
    assert result["effect_state"] == "unknown"
    assert result["recovery_required"] is True


def test_exception_after_write_executor_started_has_uncertain_effect():
    def handler(*_args):
        raise RuntimeError("unexpected result after a possible write")

    instance, _ = coordinator(handler, effect="write")
    result = execute(instance)
    assert result["effect_state"] == "unknown"
    assert result["recovery_required"] is True


def test_explicit_write_rejection_remains_a_known_failure():
    instance, _ = coordinator(
        lambda *_args: {"success": False, "error": "rejected"}, effect="write",
    )
    result = execute(instance)
    assert result["is_error"] is True
    assert not result.get("recovery_required")


def test_submit_failure_cannot_leave_a_tool_call_running_in_the_background(monkeypatch):
    from agents.agent_harness import tool_execution

    class QueuedThenFailed:
        def submit(self, method, *args):
            self.pending = lambda: method(*args)
            raise RuntimeError("failed to start worker")

        def shutdown(self, **_kwargs):
            pass

    effects = []
    instance, binding = coordinator(
        lambda *_args: effects.append("executed") or {"success": True},
        effect="write", max_inflight_tool_invocations=1,
    )
    pool = QueuedThenFailed()
    call = ToolCall(id="one", name="sample")
    context = ToolCallContext(
        request=TurnRequest(user_input="test"), assistant_message=AgentMessage.assistant(""),
        tool_call=call, state=None,
    )
    with monkeypatch.context() as patch:
        patch.setattr(tool_execution, "ThreadPoolExecutor", lambda **_kwargs: pool)
        with pytest.raises(RuntimeError):
            instance._invoke_tool(binding, context, call, binding.definition)
    pool.pending()
    assert effects == []
    assert instance._invoke_tool(binding, context, call, binding.definition)[0] == {"success": True}
    assert effects == ["executed"]


def test_exception_messages_are_redacted_and_bounded_before_model_context():
    def handler(*_args):
        raise RuntimeError("client_secret=PRIVATE " + "detail " * 100_000)

    instance, _ = coordinator(handler, max_tool_result_chars=128)
    result = execute(instance)
    assert result["is_error"] is True
    assert len(result["content"]) <= 128
    assert "PRIVATE" not in result["content"]


def test_write_postprocessing_failure_cannot_be_described_as_no_effect(monkeypatch):
    effects = []
    instance, _ = coordinator(
        lambda *_args: effects.append("committed") or {"success": True},
        effect="write",
    )

    def broken(*_args):
        raise ValueError("result projection failed")

    monkeypatch.setattr(instance, "_query_content", broken)
    result = execute(instance)
    assert effects == ["committed"]
    assert result["recovery_required"] is True
    assert result["effect_state"] == "unknown"
