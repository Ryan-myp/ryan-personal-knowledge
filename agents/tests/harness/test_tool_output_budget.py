"""Shared Tool previews obey their complete serialized JSON budget."""

import json

import pytest

from agents.agent_harness.tool_output import bound_tool_output, serialize_tool_value


@pytest.mark.parametrize("budget", [2, 16, 64, 128, 512, 2048])
@pytest.mark.parametrize("value", [
    {"success": True, "data": {"id": "keep-id", "body": "图文\\\"" * 1000}},
    [{"id": str(index), "text": "body" * 1000} for index in range(5)],
])
def test_complete_json_output_fits_even_very_small_structured_budgets(value, budget):
    original = serialize_tool_value(value)
    bounded = bound_tool_output(value, budget)
    assert len(serialize_tool_value(bounded)) <= budget
    json.loads(serialize_tool_value(bounded))
    assert serialize_tool_value(value) == original


@pytest.mark.parametrize("budget", [0, -1, True, 1.5])
def test_invalid_budget_types_fail_closed(budget):
    with pytest.raises(ValueError):
        bound_tool_output({}, budget)


@pytest.mark.parametrize("pagination", [
    {"next_cursor": "opaque-next-page"},
    {"next_page_token": "opaque-next-page"},
    {"nextPageToken": "opaque-next-page"},
    {"paging": {"cursors": {"after": "opaque-next-page"}, "next": "https://example.test/page2"}},
])
def test_large_result_keeps_exact_pagination_before_rows(pagination):
    data = {"items": [{"id": "record-1", "body": "x" * 5000}], "has_more": True, **pagination}
    original = serialize_tool_value(data)
    bounded = bound_tool_output({"success": True, "data": data}, 512)
    assert bounded["output_truncated"] is True
    assert len(serialize_tool_value(bounded)) <= 512
    for key, value in pagination.items():
        assert bounded["data"][key] == value
    assert serialize_tool_value(data) == original


def test_oversized_cursor_is_omitted_and_marked_instead_of_fabricated():
    bounded = bound_tool_output({"next_cursor": "opaque" * 1000, "has_more": True}, 512)
    assert "next_cursor" not in bounded
    assert "next_cursor" in bounded["truncated_fields"]
    assert bounded["has_more"] is True


def test_agent_can_continue_paging_after_a_large_result():
    from agents.agent_harness import AgentApplication, ModelTurn, StaticToolSource, ToolBinding, ToolCall

    pages = []

    def model(messages, _tools, _request):
        results = [m.content for m in messages if m.role == "tool"]
        if not results:
            return ModelTurn(tool_calls=[ToolCall("first", "list_records", {})])
        if len(results) == 1:
            cursor = results[-1]["data"]["next_page_token"]
            assert cursor == "opaque-next-page"
            return ModelTurn(tool_calls=[ToolCall("second", "list_records", {"cursor": cursor})])
        return "已读取两页"

    def read_page(_context, arguments):
        pages.append(arguments.get("cursor"))
        return {"success": True, "data": {
            "items": [{"id": "record-1", "body": "x" * 5000}],
            "next_page_token": "opaque-next-page" if len(pages) == 1 else None,
            "has_more": len(pages) == 1,
        }}

    app = AgentApplication.create(model=model, max_tool_result_chars=512)
    app.register_tool_source(StaticToolSource("pagination", [ToolBinding(
        {"name": "list_records", "effect_class": "read"}, read_page,
    )]))
    try:
        result = app.prompt("读取两页")
        assert result.status.value == "succeeded", result.to_dict()
        assert pages == [None, "opaque-next-page"]
    finally:
        app.close()
