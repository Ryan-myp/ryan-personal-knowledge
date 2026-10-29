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
