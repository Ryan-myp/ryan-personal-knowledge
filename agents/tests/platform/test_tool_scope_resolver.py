from agents.agent_harness import ToolCall, ToolCallContext, TurnRequest
from agents.agent_platform.tools.policy import ToolExecutionPolicy


def test_scope_resolver_supplies_context_scope_without_adding_tool_arguments():
    definition = {
        "name": "read_resource",
        "scope_required": True,
        "input_schema": {
            "type": "object",
            "properties": {"id": {"type": "string"}},
            "additionalProperties": False,
        },
    }
    request = TurnRequest(user_input="read", context={"account_id": "test-account"})
    context = ToolCallContext(
        request=request,
        tool_call=ToolCall("read", "read_resource", {"id": "resource"}),
        assistant_message=None,
        state=None,
        tool_definition=definition,
    )
    policy = ToolExecutionPolicy(
        scope_resolver=lambda _tool, request, _args: request.context.get("account_id")
    )
    assert policy.before_tool_call(context) is None
