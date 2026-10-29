"""Catalog follow-ups use registered metadata across supported Tool shapes."""

from types import SimpleNamespace

import pytest

from agents.agent_harness import AgentApplication, AgentMessage, TurnRequest
from agents.agent_harness.core.conversation_selection import catalog_selection_input


def definitions(resource="record", shape="object"):
    common = {"namespace": "alpha", "resource_type": resource, "effect_class": "read"}
    listing = {**common, "name": f"list_{resource}", "action": "list",
               "result_items_key": "items", "result_id_fields": ["id"]}
    detail = {**common, "name": f"get_{resource}", "action": "get",
              "intent_aliases": ["查看详情"], "input_schema": {"required": ["id"]}}
    if shape == "object":
        detail["input_schema"] = SimpleNamespace(required=["id"])
        detail["is_read_tool"] = True
        return SimpleNamespace(**listing), SimpleNamespace(**detail)
    return listing, detail


def transcript(*resources):
    return [AgentMessage.user("给我目录", turn_id="prior"), *[
        AgentMessage.tool(
            {"success": True, "data": {"items": [{"id": "row-001", "name": "Demo Alpha"}]}},
            name=f"list_{resource}", tool_call_id=f"call-{resource}", turn_id="prior",
        ) for resource in resources
    ]]


@pytest.mark.parametrize("shape", ["dict", "object"])
@pytest.mark.parametrize("choice", ["Demo Alpha", "row-001"])
def test_named_or_identified_result_can_resolve_to_registered_detail(shape, choice):
    result, target = catalog_selection_input(choice, "new", transcript("record"), definitions(shape=shape))
    assert target == "get_record"
    assert '"id": "row-001"' in result


def test_same_id_and_label_across_different_resources_stay_ambiguous():
    tools = (*definitions("record"), *definitions("invoice"))
    assert catalog_selection_input("Demo Alpha", "new", transcript("record", "invoice"), tools) == ("", "")


def test_read_action_does_not_override_write_effect():
    listing, detail = definitions(shape="dict")
    detail["effect_class"] = "write"
    assert catalog_selection_input("Demo Alpha", "new", transcript("record"), (listing, detail)) == ("", "")


def test_catalog_target_restriction_accepts_mapping_and_respects_allowlist():
    listing, detail = definitions(shape="dict")
    app = AgentApplication.create(model=lambda *_: "done")
    try:
        assert app.agent._restrict_to_catalog_target([listing, detail], "get_record") == [detail]
        app.agent.tool_catalog = SimpleNamespace(list_tools=lambda: [listing, detail])
        app.agent.tool_selector = lambda _request, tools: tools
        request = TurnRequest("Demo Alpha", turn_id="new", tool_allowlist=("list_record",))
        selected, required = app.agent._tools_for_turn(request, transcript("record"))
        assert selected == []
        assert required is False
    finally:
        app.close()
