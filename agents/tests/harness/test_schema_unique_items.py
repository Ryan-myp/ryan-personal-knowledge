import pytest

from agents.agent_harness.core.interfaces import ToolSchema
from agents.agent_harness.core.tool_registry import validate_tool_input


@pytest.mark.parametrize(("items", "valid"), [
    (["PAUSED", "PAUSED"], False), (["PAUSED", "ACTIVE"], True),
    ([1, 1.0], False), ([1, True], True),
    ([{"a": 1, "b": [2]}, {"b": [2], "a": 1}], False),
    ([[1, 2], [2, 1]], True),
])
def test_unique_items_respects_json_values_and_number_equivalence(items, valid):
    schema = ToolSchema(properties={"items": {"type": "array", "uniqueItems": True}})
    errors = validate_tool_input(schema, {"items": items})
    assert (not errors) is valid


def test_uniqueness_remains_optional():
    schema = ToolSchema(properties={"items": {"type": "array"}})
    assert validate_tool_input(schema, {"items": ["same", "same"]}) == []
