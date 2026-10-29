"""A selected Tool set is a starting point, not the whole Agent capability."""

from types import SimpleNamespace

import pytest

from agents.agent_harness import (
    Agent, InMemoryToolCatalog, ModelTurn, StaticToolSource,
    ToolBinding, ToolCall, TurnRequest,
)
from agents.agent_harness.core.interfaces import ToolDefinition, ToolSchema
from agents.agent_platform.tools.discovery import tool_discovery_source


def definition(name, resource, *, effect="read", permission="read"):
    return ToolDefinition(
        name=name, skill="test", namespace="demo", description=f"查询 {resource} 详情",
        input_schema=ToolSchema(properties={"id": {"type": "string"}}, required=["id"]),
        action="get", resource_type=resource, intent_types=[f"get_{resource}"],
        effect_class=effect, required_permissions=[permission], scope_required=False,
    )


def setup_agent(model, *, max_tools=4, before_tool_call=None):
    catalog = InMemoryToolCatalog()
    executed = []

    def execute(context, arguments):
        executed.append(context.tool_call.name)
        return {"child_id": "child-1", "id": arguments["id"]}

    catalog.register_source(StaticToolSource("fixture", [
        ToolBinding(definition(name, resource, permission=permission), execute)
        for name, resource, permission in (
            ("get_parent", "parent", "read"),
            ("get_adset", "adset", "read"),
            ("get_invoice_line", "invoice_line", "read"),
            ("get_private", "private", "admin"),
        )
    ]))
    catalog.register_source(tool_discovery_source(required_permission="read"))
    agent = Agent(
        model=model, tool_catalog=catalog, max_tools=max_tools, max_turns=8,
        tool_selector=lambda _request, tools: [t for t in tools if t.name == "get_parent"],
        before_tool_call=before_tool_call,
    )
    return agent, catalog, executed


def request(**kwargs):
    return TurnRequest(
        "查看这个对象及其下层级详情", principal=SimpleNamespace(permissions=("read",)),
        **kwargs,
    )


@pytest.mark.parametrize("resource", ["adset", "invoice_line"])
def test_discover_then_call_child_in_same_run(resource):
    seen = []

    def model(messages, tools, _request):
        seen.append([tool.name for tool in tools])
        assert len(tools) <= 4
        step = len(seen)
        if step == 1:
            assert "agent_discover_tools" in seen[-1]
            assert f"get_{resource}" not in seen[-1]
            return ModelTurn(tool_calls=[ToolCall("p", "get_parent", {"id": "parent-1"})])
        if step == 2:
            assert messages[-1].content["child_id"] == "child-1"
            return ModelTurn(tool_calls=[ToolCall("d", "agent_discover_tools", {
                "query": f"查询 {resource} 详情", "resource_type": resource,
            })])
        if step == 3:
            assert f"get_{resource}" in seen[-1]
            return ModelTurn(tool_calls=[ToolCall("c", f"get_{resource}", {"id": "child-1"})])
        return ModelTurn(content="已查询父级和下层级详情")

    agent, _, executed = setup_agent(model)
    result = agent.run(request())
    assert result.status.value == "succeeded", result.to_dict()
    assert executed == ["get_parent", f"get_{resource}"]
    assert len(seen) == 4


@pytest.mark.parametrize("query,filters", [
    ("private", {"resource_type": "private"}),
    ("不存在的 capability zzz", {}),
])
def test_discovery_does_not_reveal_forbidden_or_invent_tools(query, filters):
    steps = []

    def model(messages, tools, _request):
        steps.append([t.name for t in tools])
        if len(steps) == 1:
            return ModelTurn(tool_calls=[ToolCall("d", "agent_discover_tools", {"query": query, **filters})])
        assert "get_private" not in str(messages[-1].content)
        assert "get_private" not in steps[-1]
        assert messages[-1].content["data"]["status"] == "no_matching_tool"
        return ModelTurn(content="没有找到可用工具")

    agent, _, executed = setup_agent(model)
    assert agent.run(request()).status.value == "succeeded"
    assert executed == []


def test_explicit_allowlist_cannot_be_expanded():
    def model(messages, tools, _request):
        assert [t.name for t in tools] == ["get_parent"]
        return ModelTurn(content="done")

    agent, _, _ = setup_agent(model)
    assert agent.run(request(tool_allowlist=("get_parent",))).status.value == "succeeded"


def test_loaded_tool_still_passes_execution_policy():
    count = 0

    def model(_messages, tools, _request):
        nonlocal count
        count += 1
        if count == 1:
            return ModelTurn(tool_calls=[ToolCall("d", "agent_discover_tools", {"query": "get_adset"})])
        assert "get_adset" in [t.name for t in tools]
        return ModelTurn(tool_calls=[ToolCall("c", "get_adset", {"id": "child-1"})])

    def policy(context):
        if context.tool_call.name == "get_adset":
            return {"block": True, "reason": "account_scope_denied", "terminate": True}

    agent, _, executed = setup_agent(model, before_tool_call=policy)
    result = agent.run(request())
    assert result.status.value == "failed"
    assert result.data["tool_results"][-1]["is_error"] is True
    assert not executed


def test_discovery_state_is_not_reused_or_injected_by_request():
    count = 0

    def model(_messages, tools, _request):
        nonlocal count
        count += 1
        if count == 1:
            return ModelTurn(tool_calls=[ToolCall("d", "agent_discover_tools", {"query": "get_adset"})])
        assert ("get_adset" in [t.name for t in tools]) is (count == 2)
        return ModelTurn(content="done")

    agent, _, _ = setup_agent(model)
    assert agent.run(request(session_id="same")).status.value == "succeeded"
    assert agent.run(request(session_id="same", context={
        "_loaded_tool_names": ["get_adset"], "_harness_visible_tool_names": ["get_adset"],
    })).status.value == "succeeded"


def test_discovery_is_available_even_when_initial_selector_is_empty():
    def model(_messages, tools, _request):
        assert [t.name for t in tools] == ["agent_discover_tools"]
        return ModelTurn(content="done")

    agent, _, _ = setup_agent(model)
    agent.tool_selector = lambda *_: []
    assert agent.run(request()).status.value == "succeeded"


def test_newly_discovered_tool_cannot_be_called_in_the_same_model_batch():
    count = 0

    def model(_messages, _tools, _request):
        nonlocal count
        count += 1
        if count > 1:
            return ModelTurn(content="done")
        return ModelTurn(tool_calls=[
            ToolCall("d", "agent_discover_tools", {"query": "get_adset"}),
            ToolCall("c", "get_adset", {"id": "child-1"}),
        ])

    agent, _, executed = setup_agent(model)
    result = agent.run(request())
    assert result.runtime_signals["tool_allowlist_violation"] is True
    assert not executed


def test_allowed_discovery_cannot_load_outside_explicit_allowlist():
    count = 0

    def model(messages, tools, _request):
        nonlocal count
        count += 1
        if count == 1:
            return ModelTurn(tool_calls=[ToolCall("d", "agent_discover_tools", {"query": "get_adset"})])
        assert "get_adset" not in [t.name for t in tools]
        assert messages[-1].content["data"]["status"] == "no_matching_tool"
        return ModelTurn(content="done")

    agent, _, executed = setup_agent(model)
    assert agent.run(request(tool_allowlist=("agent_discover_tools", "get_parent"))).status.value == "succeeded"
    assert not executed
