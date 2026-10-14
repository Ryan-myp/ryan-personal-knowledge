from types import SimpleNamespace

from agents.agent_harness.core.interfaces import ParsedIntent, ToolDefinition, ToolSchema
from agents.agent_harness.messages import AgentMessage
from agents.agent_harness.messages import ToolCall
from agents.agent_harness.tool_execution import ToolExecutionCoordinator
from agents.applications.advertising.execution.ad_tool_interaction import AdvertisingToolInteractionProvider


def test_selected_template_uses_the_created_parent_id_instead_of_model_guesses():
    parent = ToolDefinition(
        name="example_create_parent", namespace="example", skill="example",
        description="Create parent", action="create", resource_type="parent",
        resource_id_field="parent_id",
        input_schema=ToolSchema(properties={"name": {"type": "string"}}),
    )
    child = ToolDefinition(
        name="example_create_child", namespace="example", skill="example",
        description="Create child", action="create", resource_type="child",
        parent_resource_type="parent", parent_resource_id_field="parent_id",
        input_schema=ToolSchema(properties={"name": {"type": "string"}, "parent_id": {"type": "string"}}),
    )
    messages = [
        AgentMessage.tool(
            {"success": True, "data": {"parent_id": "old-id"}},
            tool_call_id="old-parent", name=parent.name, run_id="old-run",
        ),
        AgentMessage.tool(
            {"success": True, "data": {"parent_id": "created-id"}},
            tool_call_id="created-parent", name=parent.name, run_id="current-run",
        ),
    ]
    runtime = SimpleNamespace(
        _sessions={},
        _canonical_platform=lambda value: value,
        registry=SimpleNamespace(get=lambda name: (parent, None) if name == parent.name else (child, None)),
        input_builder=SimpleNamespace(build=lambda *_: {"name": "Template child"}),
    )
    request = SimpleNamespace(
        session_id="session", run_id="current-run", execution_mode="live",
        context={"creation_template_id": "template", "account_id": "test-account"},
    )
    context = SimpleNamespace(
        request=request, state=SimpleNamespace(messages=messages),
        tool_definition=child,
        tool_call=SimpleNamespace(arguments={"name": "Model child", "parent_id": "guessed-name"}),
    )
    interaction = AdvertisingToolInteractionProvider(runtime)
    interaction._intent = lambda *_: (
        ParsedIntent("create_child", "create", ["example"]), {}, request.context,
    )
    result = interaction.resolve_tool_arguments(context)
    assert result == {"name": "Template child", "parent_id": "created-id"}


def test_batch_binding_replaces_a_parent_name_that_violates_the_declared_id_schema():
    parent = ToolDefinition(
        name="example_create_parent", namespace="example", skill="example",
        description="Create parent", action="create", resource_type="parent",
        resource_id_field="parent_id", input_schema=ToolSchema(properties={}),
    )
    child = ToolDefinition(
        name="example_create_child", namespace="example", skill="example",
        description="Create child", action="create", resource_type="child",
        parent_resource_type="parent", parent_resource_id_field="parent_id",
        input_schema=ToolSchema(properties={"parent_id": {"type": "string", "pattern": "^[0-9]+$"}}),
    )
    root_call = ToolCall(id="root", name=parent.name, arguments={})
    child_call = ToolCall(id="child", name=child.name, arguments={"parent_id": "Campaign name"})
    calls = [root_call, child_call]
    definitions = {"root": parent, "child": child}
    producers = ToolExecutionCoordinator._resource_producers(calls, definitions)
    bound, binding, unresolved, rejection = ToolExecutionCoordinator._bind_parent_resource(
        child_call, child, producers,
    )
    assert bound.depends_on == ("root",)
    assert binding == ("parent_id", "root", "parent_id")
    assert unresolved is rejection is None
