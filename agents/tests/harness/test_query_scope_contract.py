from agents.agent_harness.core.agent_profile import CORE_AGENT_SYSTEM_PROMPT
from agents.agent_harness.core.tool_selection import ToolSelector
from agents.tools.advertising.providers.source_factory import create_tool_source


def test_query_contract_forbids_unrequested_child_queries_and_rounded_counts():
    prompt = " ".join(CORE_AGENT_SYSTEM_PROMPT.split())
    assert "QUERY SCOPE" in prompt
    assert "Do not fetch child resources" in prompt
    assert "Do not round counts" in prompt


def test_architecture_diagrams_do_not_trigger_business_data_tools():
    prompt = " ".join(CORE_AGENT_SYSTEM_PROMPT.split())

    assert "architecture or runtime diagrams" in prompt
    assert "Do not call business or provider Tools" in prompt


def test_google_account_tool_explains_root_level_without_claiming_manager_status():
    tool = next(
        binding.definition
        for binding in create_tool_source("google-ads").list_bindings()
        if binding.definition.name == "google_list_customer_clients"
    )
    assert "list_accounts" in tool.intent_types
    assert "level=0" in tool.description
    assert "manager=true" in tool.description


def test_publisher_query_alias_narrows_a_single_resource_request():
    tools = [
        {
            "name": "account_list", "namespace": "sample", "resource_type": "account",
            "effect_class": "read", "intent_aliases": ["账户列表"],
        },
        {
            "name": "campaign_list", "namespace": "sample", "resource_type": "campaign",
            "effect_class": "read", "description": "List campaigns in an account",
        },
    ]
    selected = ToolSelector().select_relevant("查询 sample 测试账户列表", tools)
    assert [tool["name"] for tool in selected] == ["account_list"]
    selected = ToolSelector().select_relevant(
        "查询 sample 账户列表以及 campaign 列表", tools,
    )
    assert {tool["name"] for tool in selected} == {"account_list", "campaign_list"}


def test_alias_selection_keeps_explicit_details_and_multiple_namespaces():
    tools = [
        {"name": "list_one", "namespace": "one", "resource_type": "record",
         "effect_class": "read", "intent_aliases": ["记录列表"]},
        {"name": "get_one", "namespace": "one", "resource_type": "record",
         "effect_class": "read", "intent_aliases": ["记录详情"]},
        {"name": "list_two", "namespace": "two", "resource_type": "record",
         "effect_class": "read", "description": "List records"},
    ]
    selected = ToolSelector().select_relevant("查询 one 记录列表和详情", tools)
    assert {tool["name"] for tool in selected} == {"list_one", "get_one"}
    selected = ToolSelector().select_relevant("查询 one 记录列表以及 two records", tools)
    assert {"list_one", "list_two"} <= {tool["name"] for tool in selected}


def test_meta_child_ad_query_selects_the_ad_list_tool_once():
    tools = [
        binding.definition for binding in create_tool_source("meta").list_bindings()
    ]

    selected = ToolSelector().select_relevant(
        "查询 Meta 测试账户 Ad Set ID 123 下的 Ad 列表，只查询一次。",
        tools,
        limit=32,
    )

    assert [tool.name for tool in selected] == ["meta_list_ads"]


def test_all_three_account_queries_expose_only_account_discovery_tools():
    for provider in ("google-ads", "meta", "tiktok"):
        tools = [
            binding.definition for binding in create_tool_source(provider).list_bindings()
        ]
        selected = ToolSelector().select_relevant(
            f"查询 {provider} 测试广告账户列表，显示账户 ID 和名称", tools, limit=32,
        )
        assert selected
        assert all("list_accounts" in tool.intent_types for tool in selected)


def test_explicit_data_query_requires_a_fresh_tool_but_capability_questions_do_not():
    tools = [binding.definition for binding in create_tool_source("meta").list_bindings()]
    selector = ToolSelector()
    assert selector.requires_tool_call("查询 Meta campaign 123 的详情", tools)
    assert not selector.requires_tool_call("Meta 支持哪些 campaign 查询能力？", tools)
    assert not selector.requires_tool_call("汇总刚才查询的 campaign 结果", tools)


def test_resource_nouns_do_not_turn_reads_into_write_requests():
    tools = [binding.definition for binding in create_tool_source("meta").list_bindings()]
    selector = ToolSelector()
    text = "列出这个 ad set 下的广告列表，显示广告ID和名称"
    assert selector.requires_tool_call(text, tools)
    assert selector.requires_tool_call(text, [tool for tool in tools if not tool.is_write_tool])
    assert all(not tool.is_write_tool for tool in selector.select_relevant(text, tools))
    assert selector.requires_tool_call("修改 Meta ad set 123 的预算", tools)
    google = [binding.definition for binding in create_tool_source("google-ads").list_bindings()]
    assert selector.requires_tool_call("查询 Google Ads assets 列表", google)
