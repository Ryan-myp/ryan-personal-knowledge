from types import SimpleNamespace

from agents.applications.advertising.run.initial_tool_budget import bound_initial_tools


def test_initial_selection_is_bounded_without_truncating_tool_contracts():
    tools = [
        SimpleNamespace(name=f"tool-{i}", input_schema={"description": "x" * 2000})
        for i in range(32)
    ]
    selected = bound_initial_tools(tools, max_tools=8, max_chars=9000)
    assert 1 <= len(selected) <= 4
    assert selected == tools[: len(selected)]
    assert len(selected[0].input_schema["description"]) == 2000


def test_large_first_tool_remains_reachable_and_empty_is_valid():
    tool = SimpleNamespace(name="large", input_schema={"description": "x" * 30000})
    assert bound_initial_tools([tool]) == [tool]
    assert bound_initial_tools([]) == []
