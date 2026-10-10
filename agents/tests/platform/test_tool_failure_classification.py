from agents.agent_harness import (
    AgentApplication,
    AgentMessage,
    AgentState,
    ModelTurn,
    StaticToolSource,
    ToolBinding,
    ToolCall,
    TurnRequest,
)
from agents.agent_harness.tool_execution import ToolCallContext
from agents.agent_platform.tools.policy import ToolExecutionPolicy


def context(effect, arguments=None, schema=None):
    return ToolCallContext(
        request=TurnRequest(user_input="test", run_id="r", turn_id="t"),
        assistant_message=AgentMessage.assistant(""),
        tool_call=ToolCall("c", "test_tool", arguments or {}),
        state=AgentState(),
        tool_definition={
            "name": "test_tool",
            "effect_class": effect,
            "input_schema": schema or {},
        },
    )


def test_failed_read_does_not_claim_an_uncertain_external_write():
    result = ToolExecutionPolicy().after_tool_call(
        context("read"), {"success": False, "is_error": True}
    )
    assert result is None


def test_uncertain_write_still_requires_reconciliation():
    result = ToolExecutionPolicy().after_tool_call(
        context("write"),
        {
            "success": False,
            "is_error": False,
            "data": {"execution_status": "unknown"},
        },
    )
    assert result["recovery_required"] is True


def test_extra_model_argument_can_be_repaired_without_requesting_user_input():
    call_context = context(
        "read",
        {"value": "given", "account_id": "extra"},
        schema={
            "type": "object",
            "properties": {"value": {"type": "string"}},
            "required": ["value"],
            "additionalProperties": False,
        },
    )
    blocked = ToolExecutionPolicy().before_tool_call(call_context)
    assert blocked["block"] is True
    assert blocked["needs_input"] is False
    assert blocked["terminate"] is False


def test_missing_required_value_still_requires_user_input():
    call_context = context(
        "read",
        schema={
            "type": "object",
            "properties": {"value": {"type": "string"}},
            "required": ["value"],
            "additionalProperties": False,
        },
    )
    blocked = ToolExecutionPolicy().before_tool_call(call_context)
    assert blocked["needs_input"] is True
    assert blocked["terminate"] is True


def test_harness_reenters_model_after_extra_argument_without_executing_invalid_call():
    executed = []

    class Model:
        turn = 0

        def complete(self, _messages, _tools, _request):
            self.turn += 1
            if self.turn == 1:
                return ModelTurn(
                    tool_calls=(
                        ToolCall("bad", "read", {"value": "given", "extra": "invalid"}),
                    )
                )
            if self.turn == 2:
                return ModelTurn(
                    tool_calls=(ToolCall("good", "read", {"value": "given"}),)
                )
            return "done"

    app = AgentApplication.create(
        model=Model(), max_turns=3, tool_policy=ToolExecutionPolicy()
    )
    app.register_tool_source(
        StaticToolSource(
            "read-source",
            [
                ToolBinding(
                    {
                        "name": "read",
                        "effect_class": "read",
                        "input_schema": {
                            "type": "object",
                            "properties": {"value": {"type": "string"}},
                            "required": ["value"],
                            "additionalProperties": False,
                        },
                    },
                    lambda _ctx, values: executed.append(values) or {"success": True},
                ),
            ],
        )
    )
    try:
        result = app.prompt("read given")
        assert result.status.value == "succeeded"
        assert executed == [{"value": "given"}]
    finally:
        app.close()
