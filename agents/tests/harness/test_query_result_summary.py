"""A read result can summarize a whole returned page before model truncation."""

from agents.agent_harness.core.interfaces import (
    ToolDefinition, ToolSchema,
)
from agents.agent_harness.tool_execution import ToolExecutionCoordinator


def _coordinator(limit=1200):
    coordinator = object.__new__(ToolExecutionCoordinator)
    coordinator.max_tool_result_chars = limit
    return coordinator


def test_list_summary_counts_full_returned_page_without_claiming_full_account():
    rows = [
        {"id": str(index), "status": "PAUSED" if index < 130 else "ENABLED",
         "text": "x" * 200}
        for index in range(200)
    ]
    definition = ToolDefinition(
        name="campaigns", skill="test", namespace="test", description="read",
        input_schema=ToolSchema(properties={}),
        result_items_key="campaigns", result_summary_fields=["status"],
    )
    content = _coordinator()._query_content(
        {"success": True, "data": {
            "campaigns": rows, "has_more": True, "next_page": "opaque",
        }}, definition,
    )
    summary = content["data"]["query_summary"]
    assert summary["returned_count"] == 200
    assert summary["facets"]["status"] == {"PAUSED": 130, "ENABLED": 70}
    assert summary["scope"] == "returned_page"
    assert summary["context_truncated"] is True
    assert summary["context_count"] < 200
    assert content["data"]["has_more"] is True
    assert content["data"]["next_page"] == "opaque"
    assert len(rows) == 200


def test_summary_is_not_inferred_for_writes_or_undeclared_fields():
    definition = ToolDefinition(
        name="read", skill="test", namespace="test", description="read",
        input_schema=ToolSchema(properties={}),
        result_items_key="campaigns",
    )
    content = _coordinator()._query_content({
        "success": True, "data": {
            "campaigns": [{"status": "PAUSED"}],
        },
    }, definition)
    assert "facets" not in content["data"]["query_summary"]


def test_distinct_values_and_missing_counts_do_not_collide():
    rows = [{"status": "(other_or_missing)"}] + [
        {"status": str(index)} for index in range(17)
    ] + [{}]
    definition = ToolDefinition(
        name="campaigns", skill="test", namespace="test", description="read",
        input_schema=ToolSchema(properties={}),
        result_items_key="campaigns", result_summary_fields=["status"],
    )
    summary = _coordinator()._query_content(
        {"success": True, "data": {"campaigns": rows}}, definition,
    )["data"]["query_summary"]
    assert summary["facets"]["status"]["(other_or_missing)"] == 1
    assert summary["facet_other_counts"]["status"] == 3


def test_provider_query_summary_cannot_override_runtime_counts():
    definition = ToolDefinition(
        name="campaigns", skill="test", namespace="test", description="read",
        input_schema=ToolSchema(properties={}),
        result_items_key="campaigns", result_summary_fields=["status"],
    )
    content = _coordinator()._query_content({
        "success": True,
        "data": {
            "query_summary": {"returned_count": 999, "scope": "full_account"},
            "campaigns": [{"status": "PAUSED"}, {}, {"status": None}],
            "has_more": True,
        },
    }, definition)
    summary = content["data"]["query_summary"]
    assert summary["returned_count"] == 3
    assert summary["scope"] == "returned_page"
    assert summary["facets"]["status"] == {"PAUSED": 1}
    assert summary["facet_other_counts"]["status"] == 2
    assert content["data"]["has_more"] is True


def test_result_summary_field_rejects_invalid_or_unbounded_metadata():
    try:
        ToolDefinition(
            name="read", skill="test", namespace="test", description="read",
            input_schema=ToolSchema(properties={}),
            result_items_key="items", result_summary_fields=["access_token"],
        )
    except ValueError:
        pass
    else:
        raise AssertionError("sensitive result field must not be aggregated")
    try:
        ToolDefinition(
            name="read", skill="test", namespace="test", description="read",
            input_schema=ToolSchema(properties={}),
            result_items_key="items", result_summary_fields="status",
        )
    except ValueError:
        pass
    else:
        raise AssertionError("a summary field list is required")
