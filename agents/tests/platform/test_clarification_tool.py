from agents.agent_harness import AgentApplication, ModelTurn, ToolCall, StaticToolSource, ToolBinding
from agents.agent_platform.tools.clarification import clarification_tool_source


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
