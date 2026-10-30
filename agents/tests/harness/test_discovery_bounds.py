"""Discovery cannot turn metadata search into unbounded or privileged execution."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import threading

import pytest

from agents.agent_harness import ModelTurn, ToolCall
from agents.agent_harness.tool_discovery import RunToolDiscovery, active_tool_discovery
from agents.agent_platform.tools.discovery import tool_discovery_source
from agents.tests.harness.test_runtime_tool_discovery import definition, request, setup_agent


def test_capacity_search_limit_namespace_and_contract_drift():
    agent, catalog, _ = setup_agent(lambda *_: ModelTurn(content="done"))
    state = RunToolDiscovery(request(), catalog, max_tools=2, max_searches=3)
    assert state.search("adset", namespace="other", permitted=lambda _: True)["status"] == "no_matching_tool"
    assert state.search("adset", namespace="demo", permitted=lambda _: True)["status"] == "loaded"
    assert state.search("invoice_line", permitted=lambda _: True)["status"] == "loaded"
    assert state.search("adset", permitted=lambda _: True)["status"] == "discovery_limit"
    assert len(state.select(catalog.list_tools(), catalog.list_tools())) == 2
    child = catalog.get_binding("get_invoice_line").definition
    child.contract_hash = "changed-after-discovery"
    assert "get_invoice_line" not in [t.name for t in state.select([], catalog.list_tools())]
    state.close()
    assert state.search("adset", permitted=lambda _: True)["status"] == "discovery_limit"


def test_discovery_requires_explicit_write_search_and_current_permissions():
    from agents.agent_harness import StaticToolSource, ToolBinding

    _, catalog, _ = setup_agent(lambda *_: ModelTurn(content="done"))
    write = definition("update_record", "record", effect="write")
    catalog.register_source(StaticToolSource("write", [ToolBinding(write, lambda *_: {})]))
    state = RunToolDiscovery(request(), catalog, max_tools=3)
    assert state.search("record", permitted=lambda _: True)["status"] == "no_matching_tool"
    allowed = True
    assert state.search("record", effect="write", permitted=lambda _: allowed)["status"] == "loaded"
    allowed = False
    assert "update_record" not in [t.name for t in state.select([], catalog.list_tools())]


@pytest.mark.parametrize("arguments", [
    {}, {"query": "a", "extra": True}, {"query": "a", "limit": 0},
    {"query": "a", "limit": 5}, {"query": "a", "limit": True},
    {"query": "a", "effect": "all"}, {"query": "a" * 501},
])
def test_discovery_closed_schema(arguments):
    binding = tool_discovery_source(required_permission="read").list_bindings()[0]
    assert not binding.executor(None, arguments).success


def test_discovery_cannot_be_invoked_without_run_or_permission():
    binding = tool_discovery_source(required_permission="read").list_bindings()[0]
    assert not binding.executor(None, {"query": "adset"}).success
    _, catalog, _ = setup_agent(lambda *_: ModelTurn(content="done"))
    state = RunToolDiscovery(replace(request(), principal=None), catalog, max_tools=4)
    token = active_tool_discovery.set(state)
    try:
        assert not binding.executor(None, {"query": "adset"}).success
    finally:
        active_tool_discovery.reset(token)


def test_parallel_runs_do_not_share_loaded_definitions():
    barrier = threading.Barrier(2)

    def model(messages, tools, current):
        resource = current.user_input
        if messages[-1].role == "user":
            barrier.wait(timeout=5)
            return ModelTurn(tool_calls=[ToolCall("d", "agent_discover_tools", {"query": resource})])
        names = [t.name for t in tools]
        assert f"get_{resource}" in names
        other = "invoice_line" if resource == "adset" else "adset"
        assert f"get_{other}" not in names
        return ModelTurn(content="done")

    agent, _, _ = setup_agent(model)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(agent.run, replace(request(session_id=resource), user_input=resource))
                   for resource in ("adset", "invoice_line")]
        assert [f.result().status.value for f in futures] == ["succeeded", "succeeded"]
    assert active_tool_discovery.get() is None


def test_selection_resolves_names_against_current_catalog_and_deduplicates_control_tools():
    _, catalog, _ = setup_agent(lambda *_: ModelTurn(content="done"))
    current = catalog.list_tools()
    parent = next(t for t in current if t.name == "get_parent")
    stale = replace(parent, description="obsolete schema")
    removed = definition("removed_tool", "removed")
    discovery = next(t for t in current if t.name == "agent_discover_tools")
    state = RunToolDiscovery(request(), catalog, max_tools=4)
    selected = state.select([discovery, stale, removed, stale], current)
    assert [t.name for t in selected] == ["get_parent", "agent_discover_tools"]
    assert selected[0] is parent


@pytest.mark.parametrize("max_tools,expected", [(1, 0), (2, 0), (3, 1), (4, 2)])
def test_discovery_reserves_all_control_slots_before_reporting_loaded(max_tools, expected):
    from agents.agent_harness import StaticToolSource, ToolBinding

    _, catalog, _ = setup_agent(lambda *_: ModelTurn(content="done"))
    original = catalog.get_binding("agent_discover_tools")
    catalog.register_source(StaticToolSource("other-discovery", [ToolBinding(
        replace(original.definition, name="other_discovery"), original.executor,
    )]))
    state = RunToolDiscovery(request(), catalog, max_tools=max_tools)
    found = state.search("", namespace="demo", permitted=lambda _: True)
    assert len(found["tools"]) == expected
    visible = {t.name for t in state.select([], catalog.list_tools())}
    assert {t["name"] for t in found["tools"]} <= visible
    assert found["status"] == ("loaded" if expected else "capacity_limit")
