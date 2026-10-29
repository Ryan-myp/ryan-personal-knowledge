from agents.agent_harness import (
    AgentApplication,
    AgentMessage,
    AgentState,
    ModelTurn,
    StaticToolSource,
    ToolBinding,
    ToolCall,
    ToolCallContext,
    TurnRequest,
)
from agents.agent_platform.tools.clarification import clarification_tool_source
from agents.agent_platform.tools.policy import ToolExecutionPolicy


def test_clarification_is_a_structured_pause_not_a_provider_operation():
    class Model:
        def complete(self, *_args):
            return ModelTurn(tool_calls=(ToolCall(
                "ask", "agent_request_input",
                {"question": "Which workspace?", "choices": ["one", "two"]},
            ),))

    app = AgentApplication.create(model=Model())
    app.register_tool_source(clarification_tool_source(required_permission="workspace.read"))
    try:
        result = app.prompt("create a resource")
        assert result.status.value == "awaiting_input"
    finally:
        app.close()


def test_clarification_contract_has_no_execution_or_identity_parameters():
    binding, = clarification_tool_source(required_permission="workspace.read").list_bindings()
    definition = binding.definition
    assert definition.effect_class.value == "read"
    assert definition.input_schema.additional_properties is False
    assert set(definition.input_schema.properties) == {"question", "choices"}
    result = binding.executor(None, {"question": "Select a target", "choices": ["a", "b"]})
    assert result.needs_input is True
    assert result.interaction["prompt"] == "Select a target"
    assert result.interaction["payload"]["options"] == [
        {"label": "a", "value": "a"}, {"label": "b", "value": "b"},
    ]


def test_missing_clarification_question_is_retried_instead_of_asking_user_for_question():
    definition = clarification_tool_source(
        required_permission="workspace.read",
    ).list_bindings()[0].definition
    policy = ToolExecutionPolicy(
        permissions=frozenset({"workspace.read"}),
        interaction_builder=lambda *_args: {
            "type": "action_clarification",
            "payload": {"fields": [{"label": "Question"}]},
        },
    )
    context = ToolCallContext(
        request=TurnRequest(user_input="compare this workflow"),
        assistant_message=AgentMessage.assistant(""),
        tool_call=ToolCall("ask", "agent_request_input", {}),
        state=AgentState(),
        tool_definition=definition,
    )

    blocked = policy.before_tool_call(context)

    assert blocked is not None
    assert blocked["block"] is True
    assert blocked["needs_input"] is False
    assert blocked["terminate"] is False
    assert "clarification_tool_input_missing" in blocked["runtime_signals"]
    assert "interaction" not in blocked


def test_placeholder_clarification_question_is_retried_without_showing_a_form():
    definition = clarification_tool_source(
        required_permission="workspace.read",
    ).list_bindings()[0].definition
    policy = ToolExecutionPolicy(
        permissions=frozenset({"workspace.read"}),
        interaction_builder=lambda *_args: {
            "type": "action_clarification",
            "payload": {"fields": [{"label": "Question"}]},
        },
    )
    context = ToolCallContext(
        request=TurnRequest(user_input="看图里的流程是否正确"),
        assistant_message=AgentMessage.assistant(""),
        tool_call=ToolCall(
            "ask", "agent_request_input", {"question": "Question"},
        ),
        state=AgentState(),
        tool_definition=definition,
    )

    blocked = policy.before_tool_call(context)

    assert blocked is not None
    assert blocked["block"] is True
    assert blocked["needs_input"] is False
    assert blocked["terminate"] is False
    assert "clarification_tool_input_missing" in blocked["runtime_signals"]
    assert "interaction" not in blocked


def test_clarification_prevents_later_batch_writes():
    writes = []

    class Model:
        def complete(self, *_args):
            return ModelTurn(tool_calls=(
                ToolCall("ask", "agent_request_input", {"question": "Select the target"}),
                ToolCall("write", "update_record", {}),
            ))

    app = AgentApplication.create(model=Model(), tool_execution="parallel_reads")
    app.register_tool_source(clarification_tool_source(required_permission="workspace.read"))
    app.register_tool_source(StaticToolSource("write", [ToolBinding(
        {"name": "update_record", "effect_class": "write"},
        lambda *_: writes.append("executed"),
    )]))
    try:
        assert app.prompt("update a record").status.value == "awaiting_input"
        assert writes == []
    finally:
        app.close()
