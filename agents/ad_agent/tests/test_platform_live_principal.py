from types import SimpleNamespace

from agents.agent_harness import AgentMessage, AgentState, ToolCall, ToolCallContext, TurnRequest
from agents.agent_platform.tools.policy import PolicyRequest, ToolExecutionPolicy


WRITE_TOOL = {
    "name": "update_record",
    "effect_class": "write",
    "live_support": True,
    "input_schema": {"type": "object", "properties": {}},
}


def _policy():
    return ToolExecutionPolicy(
        allow_live_writes=True,
        live_approved_tools={"update_record"},
        write_guard_configured=True,
        require_durable_idempotency=False,
    )


def test_live_write_requires_principal_in_policy_evaluation():
    policy = _policy()
    decision = policy.evaluate(PolicyRequest(
        tool=WRITE_TOOL,
        execution_mode="live",
        allow_live_writes=True,
        live_approved_tools={"update_record"},
        write_guard_configured=True,
        require_confirmation=False,
    ))
    assert decision.allowed is False
    assert "principal" in decision.reason.lower()


def test_live_write_requires_principal_in_actual_tool_path():
    policy = _policy()
    context = ToolCallContext(
        request=TurnRequest(
            user_input="update", execution_mode="live", user_id="forged",
            tenant_id="forged",
        ),
        assistant_message=AgentMessage.assistant(""),
        tool_call=ToolCall("call-1", "update_record", {}),
        state=AgentState(),
        tool_definition=WRITE_TOOL,
    )
    blocked = policy.before_tool_call(context)
    assert blocked is not None
    assert blocked["block"] is True
    assert "principal" in blocked["reason"].lower()
    context.request = TurnRequest(
        user_input="update", execution_mode="live",
        principal=SimpleNamespace(tenant_id="tenant-1", user_id="user-1"),
    )
    assert policy.before_tool_call(context) is None
