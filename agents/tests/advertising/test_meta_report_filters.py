"""Read-only Meta report filters reach the HTTP payload without extra queries."""

import json

import pytest

from agents.agent_harness.core.interfaces import ToolContext
from agents.agent_harness.core.tool_registry import validate_tool_input
from agents.tools.advertising.clients.meta_client import MetaAPIClient
from agents.tools.advertising.providers.meta import create_meta_tool_source
from agents.tools.advertising.providers.meta.reports import MetaGetReportHandler


def test_report_schema_exposes_bounded_status_filter_and_row_collection():
    definition = next(b.definition for b in create_meta_tool_source().list_bindings()
                      if b.definition.name == "meta_get_campaign_report")
    assert validate_tool_input(definition.input_schema, {"effective_status": ["PAUSED"]}) == []
    for value in ([], ["UNKNOWN"], ["PAUSED", "PAUSED"], "PAUSED"):
        assert validate_tool_input(definition.input_schema, {"effective_status": value})
    assert definition.result_items_key == "report"
    assert {"meta-marketing-api-expert", "account-diagnostics"} <= set(definition.skill_refs)
    assert validate_tool_input(definition.input_schema, {"date_preset": "imaginary_period"})
    assert validate_tool_input(definition.input_schema, {"date_preset": "LAST_7_DAYS"}) == []


def test_status_filter_combines_with_resource_ids_instead_of_overwriting_them():
    client = MetaAPIClient({})
    calls = []
    client._list_graph_pages = lambda *args: calls.append(args) or []
    client.get_campaign_report("act_123", ["101"], effective_status=["PAUSED"], time_range="yesterday")
    assert len(calls) == 1
    params = calls[0][2]
    assert params["date_preset"] == "yesterday"
    assert json.loads(params["filtering"]) == [
        {"field": "campaign.id", "operator": "IN", "value": ["101"]},
        {"field": "campaign.effective_status", "operator": "IN", "value": ["PAUSED"]},
    ]


@pytest.mark.parametrize("statuses", [[], ["UNKNOWN"], ["PAUSED", "PAUSED"], "PAUSED", [None]])
def test_invalid_statuses_are_rejected_before_network_access(statuses):
    client = MetaAPIClient({})
    calls = []
    client._list_graph_pages = lambda *args: calls.append(args) or []
    with pytest.raises(ValueError):
        client.get_campaign_report("123", [], effective_status=statuses)
    assert calls == []


def test_handler_forwards_filter_and_explains_its_current_status_semantics():
    calls = []
    client = type("Client", (), {"get_campaign_report": lambda self, *args, **kwargs: (
        calls.append((args, kwargs)) or []
    )})()
    result = MetaGetReportHandler(client).execute(
        ToolContext("s", "u", account_id="act_123"),
        {"date_preset": "yesterday", "effective_status": ["PAUSED"]},
    )
    assert result.success is True
    assert calls[0][1]["effective_status"] == ["PAUSED"]
    assert result.data["report_context"]["filters"] == {
        "effective_status": ["PAUSED"], "status_basis": "current_campaign_effective_status",
    }


def test_offline_report_filter_is_never_claimed_as_provider_verified():
    result = MetaGetReportHandler().execute(
        ToolContext("s", "u", account_id="act_123"), {"effective_status": ["PAUSED"]},
    )
    assert result.data["simulated"] is True
    assert result.data["report_context"]["filters_executed"] is False


def test_invalid_report_period_fails_before_network_or_offline_success():
    client = MetaAPIClient({})
    calls = []
    client._list_graph_pages = lambda *args: calls.append(args) or []
    with pytest.raises(ValueError):
        client.get_campaign_report("123", [], time_range="imaginary_period")
    assert calls == []
    result = MetaGetReportHandler().execute(
        ToolContext("s", "u", account_id="act_123"), {"date_preset": "imaginary_period"},
    )
    assert result.success is False
