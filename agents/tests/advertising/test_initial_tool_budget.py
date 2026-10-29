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


def test_oversize_candidate_does_not_hide_smaller_tools_after_it():
    tools = [SimpleNamespace(name=str(i), input_schema={"description": "x" * size})
             for i, size in enumerate((200, 20000, 200))]
    assert bound_initial_tools(tools, max_chars=1000) == [tools[0], tools[2]]


def test_budget_preserves_namespace_variety_without_schema_truncation():
    tools = [SimpleNamespace(name=f"{ns}-{i}", namespace=ns, input_schema={})
             for ns in ("a", "b", "c") for i in range(6)]
    selected = bound_initial_tools(tools, max_tools=4)
    assert len(selected) == 4
    assert {tool.namespace for tool in selected} == {"a", "b", "c"}


def test_pinned_workflow_entry_is_retained_even_above_soft_budget():
    tools = [SimpleNamespace(name=str(i), input_schema={"description": "x" * 2000})
             for i in range(3)]
    assert bound_initial_tools(tools, max_chars=100, pinned_names={"2"}) == [tools[0], tools[2]]


def test_real_broad_knowledge_selection_keeps_top_ranked_search_within_tool_limit():
    from agents.agent_harness import TurnRequest
    from agents.agent_harness.core.tool_selection import ToolSelector
    from agents.applications.advertising.composition.ad_application import AdvertisingComposition
    from agents.applications.advertising.composition.ad_application_assembly import AdApplicationAssembly
    from agents.applications.advertising.persistence.store import AdAgentStore

    runtime = AdvertisingComposition(persistence_store=AdAgentStore(":memory:"),
                                     require_llm=False, offline_mode=True,
                                     start_background_workers=False)
    try:
        request = TurnRequest(user_input="讲解程序化广告中 SSP 和 DSP 的区别，不需要账户数据。", context={})
        selected = AdApplicationAssembly._tool_selector(runtime, ToolSelector())(
            request, runtime.registry.list_all(),
        )
        assert "agent_knowledge_search" in {tool.name for tool in selected}
        assert len(selected) <= 9  # Eight schemas plus clarification, if applicable.
    finally:
        runtime.close(wait=True)
