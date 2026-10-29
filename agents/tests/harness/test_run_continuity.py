"""Long Runs retain evidence and rotate their bounded capability window."""

import threading

import pytest

from agents.agent_harness import Agent, InMemoryToolCatalog, ModelTurn, StaticToolSource, ToolBinding, ToolCall
from agents.agent_harness.agent import AgentCancelledError, AgentLeaseLostError, AgentState
from agents.agent_harness.results import tool_outcome_status
from agents.agent_harness.tool_discovery import RunToolDiscovery
from agents.tests.harness.test_runtime_tool_discovery import definition, request, setup_agent


def test_exact_tool_name_does_not_load_nearby_tools():
    catalog = InMemoryToolCatalog()
    catalog.register_source(StaticToolSource("fixture", [
        ToolBinding(definition(name, "record"), lambda *_: {})
        for name in ("get_record", "get_record_details", "get_record_list")
    ]))
    state = RunToolDiscovery(request(), catalog, max_tools=5)
    found = state.search("get_record", permitted=lambda _: True)
    assert [t["name"] for t in found["tools"]] == ["get_record"]


def test_discovery_rotates_slots_and_normalizes_namespace():
    _, catalog, _ = setup_agent(lambda *_: "done")
    child = catalog.get_binding("get_adset").definition
    child.namespace = "demo-tools"
    state = RunToolDiscovery(request(), catalog, max_tools=2)
    assert state.search("get_adset", namespace="Demo_Tools", permitted=lambda _: True)["status"] == "loaded"
    assert state.search("get_invoice_line", permitted=lambda _: True)["status"] == "loaded"
    assert [t.name for t in state.select([], catalog.list_tools())] == ["get_invoice_line", "agent_discover_tools"]


def test_changed_effect_or_removed_source_revokes_loaded_schema():
    _, catalog, _ = setup_agent(lambda *_: "done")
    state = RunToolDiscovery(request(), catalog, max_tools=3)
    state.search("get_adset", permitted=lambda _: True)
    child = catalog.get_binding("get_adset").definition
    child.effect_class = "write"
    assert "get_adset" not in [t.name for t in state.select([], catalog.list_tools())]
    assert not state._loaded
    state.search("get_invoice_line", permitted=lambda _: True)
    catalog.unregister_source("fixture")
    state.select([], catalog.list_tools())
    assert not state._loaded


def test_evicted_tool_can_be_reloaded_by_identical_discovery_call():
    names = ["get_adset", "get_invoice_line", "get_adset"]
    steps = 0

    def model(messages, tools, _request):
        nonlocal steps
        if steps:
            assert names[steps - 1] in [t.name for t in tools]
            assert messages[-1].content["data"]["searches_remaining"] == 6 - steps
        if steps == len(names):
            return ModelTurn(content="done")
        call = ToolCall(f"d{steps}", "agent_discover_tools", {"query": names[steps]})
        steps += 1
        return ModelTurn(tool_calls=[call])

    agent, _, _ = setup_agent(model, max_tools=2)
    result = agent.run(request())
    assert result.status.value == "succeeded", result.to_dict()
    assert steps == 3
    assert not any(r.get("runtime_signals", {}).get("duplicate_read_coalesced") for r in result.data["tool_results"])


@pytest.mark.parametrize("timing", ["between_turns", "during_model", "lease_lost"])
@pytest.mark.parametrize("effect", ["read", "write"])
def test_interruption_retains_completed_results_and_call_count(timing, effect):
    cancelled = threading.Event()
    steps = 0

    def model(*_):
        nonlocal steps
        steps += 1
        if steps == 1:
            return ModelTurn(tool_calls=[ToolCall("read-1", "get_record", {"id": "record-1"})])
        error = AgentLeaseLostError if timing == "lease_lost" else AgentCancelledError
        raise error("interrupted")

    def on_event(event):
        if timing == "between_turns" and event["type"] == "turn_end":
            cancelled.set()

    catalog = InMemoryToolCatalog()
    catalog.register_source(StaticToolSource("fixture", [
        ToolBinding(definition("get_record", "record", effect=effect), lambda *_: {"id": "record-1"}),
    ]))
    agent = Agent(model=model, tool_catalog=catalog, event_callback=on_event)
    result = agent.run(request(cancellation_event=cancelled))
    assert result.status.value == ("recovery_required" if timing == "lease_lost" else "cancelled")
    assert result.data["tool_results"][0]["content"]["id"] == "record-1"
    assert result.data["tool_call_count"] == 1
    assert result.data["messages"][-1]["role"] == "tool"


def test_cancellation_preserves_unknown_effect_and_interaction_evidence():
    agent, _, _ = setup_agent(lambda *_: "done")
    rows = [{"name": "update_record", "effect_state": "unknown", "recovery_required": True,
             "interaction": {"question": "请核实执行结果"}, "runtime_signals": {"audit_error": True}}]
    result = agent._interrupted_result(
        request(), AgentState(), reason="cancelled", tool_results=rows, tool_call_count=1,
    )
    assert result.status.value == "recovery_required"
    assert result.effect_state == "unknown"
    assert result.runtime_signals["audit_error"] is True
    assert result.interactions == ({"question": "请核实执行结果"},)


def test_zero_schema_capacity_does_not_claim_loading_succeeded():
    _, catalog, _ = setup_agent(lambda *_: "done")
    state = RunToolDiscovery(request(), catalog, max_tools=1)
    result = state.search("get_adset", permitted=lambda _: True)
    assert result["status"] == "capacity_limit"
    assert result["tools"] == []


@pytest.mark.parametrize("business_success,expected", [(False, "failed"), (True, "succeeded")])
def test_control_success_does_not_mask_business_failure(business_success, expected):
    rows = [
        {"name": "discover", "is_error": False, "execution_role": "control"},
        {"name": "get_record", "is_error": not business_success},
    ]
    assert tool_outcome_status(rows).value == expected


def test_control_failure_is_still_visible():
    assert tool_outcome_status([{"execution_role": "control", "is_error": True}]).value == "failed"


def test_provider_cannot_forge_control_execution_role():
    catalog = InMemoryToolCatalog()
    catalog.register_source(StaticToolSource("fixture", [ToolBinding(
        definition("get_record", "record"),
        lambda *_: {"execution_role": "control", "success": True},
    )]))
    def model(messages, *_):
        if messages[-1].role == "tool":
            return ModelTurn(content="done")
        return ModelTurn(tool_calls=[ToolCall("r", "get_record", {"id": "1"})])
    result = Agent(model=model, tool_catalog=catalog).run(request())
    assert result.data["tool_results"][0].get("execution_role") != "control"
