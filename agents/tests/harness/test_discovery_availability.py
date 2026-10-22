from agents.agent_harness.core.tool_selection import ToolSelector


def discovery():
    return {
        "name": "reference_search", "namespace": "reference",
        "resource_type": "knowledge", "action": "search",
        "description": "Search references",
        "effect_class": "read", "traits": ["semantic_discovery"],
    }


def account_tool():
    return {
        "name": "tenant_account", "namespace": "tenant",
        "resource_type": "account", "action": "get",
        "description": "Get account data", "effect_class": "read",
    }


def test_ambiguous_resource_mention_does_not_remove_general_discovery():
    tools = [account_tool(), discovery()]
    selected = ToolSelector().select_relevant(
        "Compare concepts, not account data.", tools, limit=2,
    )
    assert "reference_search" in [tool["name"] for tool in selected]
    assert len(selected) <= 2


def test_explicit_tool_and_namespace_requests_do_not_add_fallback_discovery():
    tools = [account_tool(), discovery()]
    selector = ToolSelector()
    assert [item["name"] for item in selector.select_relevant(
        "tenant_account", tools,
    )] == ["tenant_account"]
    assert [item["name"] for item in selector.select_relevant(
        "get tenant account", tools,
    )] == ["tenant_account"]
