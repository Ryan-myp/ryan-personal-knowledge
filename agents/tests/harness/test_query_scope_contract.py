from agents.agent_harness.core.agent_profile import CORE_AGENT_SYSTEM_PROMPT
from agents.agent_harness.core.tool_selection import ToolSelector
from agents.agent_harness.core.policy import PolicyContext
from agents.agent_platform.tools.knowledge import knowledge_search_tool_source
from agents.agent_platform.tools.web_search import web_search_tool_source
from agents.tools.advertising.providers.source_factory import create_tool_source


def test_query_contract_forbids_unrequested_child_queries_and_rounded_counts():
    prompt = " ".join(CORE_AGENT_SYSTEM_PROMPT.split())
    assert "QUERY SCOPE" in prompt
    assert "Do not fetch child resources" in prompt
    assert "explicitly requests descendants" in prompt
    assert "Do not ask the user to resend the same request" in prompt
    assert "say only that it was not selected this turn" in prompt
    assert "Do not round counts" in prompt
    assert "not supplied for this turn" in prompt


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


def test_explicit_comma_separated_resource_list_keeps_parent_and_children():
    tools = [
        binding.definition for binding in create_tool_source("meta").list_bindings()
    ]

    selected = ToolSelector().select_relevant(
        "查询 Meta campaign, ad set, ad 列表",
        tools,
        limit=32,
    )

    assert {
        "meta_list_campaigns",
        "meta_list_ad_sets",
        "meta_list_ads",
    } <= {tool.name for tool in selected}


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


def test_campaign_filter_followup_reuses_the_previous_read_without_web_search():
    tools = [
        binding.definition
        for source in (
            create_tool_source("google-ads"),
            knowledge_search_tool_source(
                provider=object(), required_permission="ads.read",
            ),
            web_search_tool_source(
                configuration_provider=lambda: {}, required_permission="ads.read",
            ),
        )
        for binding in source.list_bindings()
    ]
    selector = ToolSelector()
    previous = (
        "查询 Google Ads 报表，account 是 7574609568",
        "查询一下campaign信息",
    )
    for request in (
        "那我们根据状态过滤一下，不要 REMOVED 的",
        "我是让你重新查询，根据状态进行过滤",
    ):
        selected = selector.select_relevant(
            request, tools, conversation_context=previous,
            contextual_namespaces=("google-ads",),
        )
        assert [tool.name for tool in selected] == ["google_list_campaigns"]
        assert selector.requires_tool_call(
            request, selected, conversation_context=previous,
        )

    assert selector.select_relevant(
        "根据状态过滤一下", tools, contextual_namespaces=("google-ads",),
    ) == []
    for previous_input in (
        "讲讲 Google campaign 的状态",
        "查询 Google campaign 123 的详情",
    ):
        assert selector.select_relevant(
            "根据状态过滤一下", tools,
            conversation_context=(previous_input,),
            contextual_namespaces=("google-ads",),
        ) == []


def test_status_check_followup_reuses_the_latest_actionable_campaign_query():
    tools = [
        binding.definition
        for provider in ("google-ads", "meta", "tiktok")
        for binding in create_tool_source(provider).list_bindings()
    ]
    selector = ToolSelector()
    history = (
        "查询 Google Ads campaign 列表",
        "按 status != REMOVED 过滤后重新查询",
    )

    selected = selector.select_relevant(
        "现在可以了吗", tools,
        conversation_context=history,
        contextual_namespaces=("google-ads",),
    )

    assert [tool.name for tool in selected] == ["google_list_campaigns"]
    assert selector.requires_tool_call(
        "现在可以了吗", selected, conversation_context=history,
    )


def test_status_check_followup_does_not_replay_a_knowledge_or_write_request():
    tools = [
        binding.definition
        for provider in ("google-ads", "meta", "tiktok")
        for binding in create_tool_source(provider).list_bindings()
    ]
    selector = ToolSelector()

    assert selector.select_relevant(
        "现在可以了吗", tools,
        conversation_context=("讲讲 Google campaign 的状态",),
        contextual_namespaces=("google-ads",),
    ) == []
    assert selector.select_relevant(
        "现在可以了吗", tools,
        conversation_context=("创建 Google campaign",),
        contextual_namespaces=("google-ads",),
    ) == []


def test_list_filter_followup_stays_in_the_prior_provider_namespace():
    selector = ToolSelector()
    tools = [
        binding.definition
        for provider in ("google-ads", "meta", "tiktok")
        for binding in create_tool_source(provider).list_bindings()
    ]
    for provider, expected in (
        ("google-ads", "google_list_campaigns"),
        ("meta", "meta_list_campaigns"),
        ("tiktok", "tiktok_list_campaigns"),
    ):
        selected = selector.select_relevant(
            "根据状态重新筛选",
            tools,
            conversation_context=(f"查询 {provider} campaign 列表",),
            contextual_namespaces=(provider,),
        )
        assert [tool.name for tool in selected] == [expected]


def test_filter_word_in_a_concept_question_does_not_query_an_account():
    tools = [
        binding.definition
        for source in (
            create_tool_source("google-ads"),
            knowledge_search_tool_source(
                provider=object(), required_permission="ads.read",
            ),
            web_search_tool_source(
                configuration_provider=lambda: {}, required_permission="ads.read",
            ),
        )
        for binding in source.list_bindings()
    ]
    selected = ToolSelector().select_relevant(
        "Google Campaign 排除式定向是什么？", tools,
    )
    assert selected
    assert all(
        "semantic_discovery" in tool.traits for tool in selected
    )


def test_campaign_detail_with_descendants_loads_registered_tiktok_read_tools():
    tools = [binding.definition for binding in create_tool_source("tiktok").list_bindings()]
    selector = ToolSelector()
    request = "这个campaign：1879821177383105的详情展示一下含下层级"
    selected = selector.select_relevant(
        request, tools, limit=16, contextual_namespaces=("tiktok",),
    )

    names = {tool.name for tool in selected}
    assert {
        "tiktok_get_campaign", "tiktok_list_adgroups", "tiktok_list_ads",
    } <= names
    assert all(tool.effect_class.value == "read" for tool in selected)
    assert selector.requires_tool_call(request, selected)


def test_descendant_read_selection_uses_resource_metadata_and_is_bounded():
    tools = [
        {
            "name": name, "namespace": namespace, "resource_type": resource,
            "parent_resource_type": parent, "action": action,
            "effect_class": effect, "description": f"{action} {resource}",
        }
        for name, namespace, resource, parent, action, effect in [
            ("get_folder", "files", "folder", None, "get", "read"),
            ("list_documents", "files", "document", "folder", "list", "read"),
            ("list_pages", "files", "page", "document", "list", "read"),
            ("delete_page", "files", "page", "document", "delete", "write"),
            ("list_other", "other", "document", "folder", "list", "read"),
        ]
    ]
    selector = ToolSelector(max_read_tools_per_turn=3)
    selected = selector.select_relevant(
        "展示 files folder 123 详情，包含下层级",
        tools, limit=3,
    )
    assert [tool["name"] for tool in selected] == [
        "get_folder", "list_documents", "list_pages",
    ]
    assert selector.requires_tool_call(
        "展示 files folder 123 详情，包含下层级", selected,
    )
    plain = selector.select_relevant(
        "展示 files folder 123 详情", tools, limit=3,
    )
    assert "list_documents" not in [tool["name"] for tool in plain]


def test_short_meta_descendant_detail_followup_loads_child_detail_tools():
    tools = [binding.definition for binding in create_tool_source("meta").list_bindings()]
    selector = ToolSelector()
    selected = selector.select_relevant(
        "下层级详细信息呢？",
        tools,
        conversation_context=(
            "查询一下meta 的campaign 列表",
            "查询这个campaign ：120251918088900251",
        ),
        contextual_namespaces=("meta",),
    )
    assert {"meta_get_adset", "meta_get_ad"} <= {tool.name for tool in selected}
    assert "meta_get_campaign_report" not in {tool.name for tool in selected}
    assert selector.requires_tool_call("下层级详细信息呢？", selected)


def test_child_detail_followup_needs_prior_resource_and_never_crosses_namespace():
    tools = [
        {
            "name": name, "namespace": namespace, "resource_type": resource,
            "parent_resource_type": parent, "action": action,
            "effect_class": "read", "description": f"{action} {resource}",
        }
        for name, namespace, resource, parent, action in [
            ("get_folder", "files", "folder", None, "get"),
            ("get_document", "files", "document", "folder", "get"),
            ("list_documents", "files", "document", "folder", "list"),
            ("get_page", "files", "page", "document", "get"),
            ("list_pages", "files", "page", "document", "list"),
            ("get_foreign_document", "other", "document", "folder", "get"),
        ]
    ]
    selector = ToolSelector(max_read_tools_per_turn=4)
    selected = selector.select_relevant(
        "下层级详细信息呢？", tools,
        conversation_context=("查询 files folder 123",),
        contextual_namespaces=("files",),
    )
    assert {"get_document", "get_page"} <= {
        tool["name"] for tool in selected
    }
    assert len(selected) <= 4
    assert all(tool["namespace"] == "files" for tool in selected)
    assert selector.select_relevant(
        "下层级详细信息呢？", tools, contextual_namespaces=("files",),
    ) == []
    assert selector.select_relevant(
        "下层级详细信息呢？", tools,
        conversation_context=("查询 files folder 列表",),
        contextual_namespaces=("files",),
    ) == []
    assert selector.select_relevant(
        "讲讲下层级的概念", tools,
        conversation_context=("查询 files folder 123",),
        contextual_namespaces=("files",),
    ) == []


def test_colloquial_concept_comparison_does_not_route_provider_tools():
    tools = [
        binding.definition
        for binding in create_tool_source("tiktok").list_bindings()
    ]
    tools.extend(_semantic_discovery_definitions())
    selector = ToolSelector()
    question = "TikTok Pixel 和 Events API 有啥区别呢？"
    selected = selector.select_relevant(question, tools)

    selected_names = {tool.name for tool in selected}
    assert {"agent_knowledge_search", "agent_web_search"} <= selected_names
    assert "tiktok_list_accounts" not in selected_names
    assert not any(
        tool.namespace == "tiktok"
        for tool in selected
    )
    assert selector.requires_tool_call(question, selected)


def test_generic_lookup_word_does_not_override_an_explicit_concept_comparison():
    tools = [
        binding.definition
        for binding in create_tool_source("tiktok").list_bindings()
    ]
    tools.extend(_semantic_discovery_definitions())
    selector = ToolSelector()
    question = "查一下 TikTok Pixel 和 Events API 有啥区别？"

    selected = selector.select_relevant(question, tools)

    selected_names = {tool.name for tool in selected}
    assert {"agent_knowledge_search", "agent_web_search"} <= selected_names
    assert "tiktok_list_accounts" not in selected_names
    assert selector.requires_tool_call(question, selected)


def test_colloquial_account_question_still_routes_a_matching_read_tool():
    tool = {
        "name": "tiktok_list_campaigns",
        "namespace": "tiktok",
        "action": "list",
        "resource_type": "campaign",
        "description": "List campaigns for a TikTok account",
        "effect_class": "read",
        "intent_types": ["list_campaigns"],
        "input_schema": {"properties": {}},
    }
    selector = ToolSelector()
    question = "TikTok 账户有啥 campaign？"
    selected = selector.select_relevant(question, [tool])

    assert [item["name"] for item in selected] == ["tiktok_list_campaigns"]
    assert selector.requires_tool_call(question, selected)


def test_colloquial_account_list_selects_only_the_requested_resource():
    tools = [
        binding.definition
        for binding in create_tool_source("tiktok").list_bindings()
    ]
    tools.extend(_semantic_discovery_definitions())
    selector = ToolSelector()
    question = "TikTok 账户有啥 campaign？"

    selected = selector.select_relevant(question, tools)

    selected_names = {tool.name for tool in selected}
    assert "tiktok_list_campaigns" in selected_names
    assert "agent_knowledge_search" not in selected_names
    assert "agent_web_search" not in selected_names
    assert selector.requires_tool_call(question, selected)


def test_localized_account_alias_matches_without_platform_specific_rules():
    account_tool = {
        "name": "alpha_list_accounts",
        "namespace": "alpha",
        "action": "list",
        "resource_type": "account",
        "effect_class": "read",
        "intent_types": ["list_accounts"],
        "intent_aliases": ["账户列表", "account list"],
    }
    campaign_tool = {
        "name": "alpha_list_campaigns",
        "namespace": "alpha",
        "action": "list",
        "resource_type": "campaign",
        "effect_class": "read",
        "intent_types": ["list_campaigns"],
    }

    selected = ToolSelector().select_relevant(
        "帮我列出 Alpha 账户",
        [account_tool, campaign_tool],
    )

    assert [tool["name"] for tool in selected] == ["alpha_list_accounts"]


def test_generic_operation_request_does_not_fall_back_to_discovery():
    schedule_tool = {
        "name": "agent_schedule_run_now",
        "namespace": "platform",
        "action": "run",
        "resource_type": "schedule",
        "effect_class": "write",
        "intent_types": ["run_schedule"],
        "intent_aliases": ["执行定时任务", "run scheduled task"],
    }
    discovery_tool = {
        "name": "agent_web_search",
        "namespace": "platform",
        "action": "search",
        "resource_type": "web_search",
        "effect_class": "read",
        "traits": ["semantic_discovery", "web_search"],
        "intent_aliases": ["search online"],
    }

    selected = ToolSelector().select_relevant(
        "直接执行一下这个任务",
        [schedule_tool, discovery_tool],
    )

    assert [tool["name"] for tool in selected] == ["agent_schedule_run_now"]


def test_policy_declared_namespaces_prevent_disallowed_operations_from_becoming_searches():
    discovery_tool = {
        "name": "agent_web_search",
        "namespace": "platform",
        "action": "search",
        "resource_type": "web_search",
        "effect_class": "read",
        "traits": ["semantic_discovery", "web_search"],
        "intent_aliases": ["search online", "联网搜索"],
    }
    selector = ToolSelector(policies=[
        PolicyContext(
            name="channel-scope",
            allowed_namespaces=("google-ads",),
            denied_namespaces=("tiktok",),
        ),
    ])

    assert selector.select_relevant(
        "列出 TikTok campaign",
        [discovery_tool],
    ) == []
    assert [tool["name"] for tool in selector.select_relevant(
        "查询 Google 开源的 HERNES",
        [discovery_tool],
    )] == ["agent_web_search"]


def test_greetings_expose_only_non_forced_semantic_discovery_tools():
    tools = _semantic_discovery_definitions()
    selector = ToolSelector()

    for greeting in ("你好", "你有什么能力？"):
        selected = selector.select_relevant(greeting, tools)

        assert selected
        assert all("semantic_discovery" in tool.traits for tool in selected)
        assert not selector.requires_tool_call(greeting, selected)


def test_unknown_read_target_still_routes_to_semantic_discovery():
    tools = _semantic_discovery_definitions()
    selector = ToolSelector()

    selected = selector.select_relevant("帮我查询 HERNES 的资料", tools)

    assert {tool.name for tool in selected} == {
        "agent_knowledge_search",
        "agent_web_search",
    }


def test_unknown_read_target_does_not_select_provider_account_tools():
    tools = [
        binding.definition
        for binding in create_tool_source("google-ads").list_bindings()
    ]
    tools.extend(_semantic_discovery_definitions())
    selector = ToolSelector()

    selected = selector.select_relevant(
        "帮我查一下 QuantaBridge 的用法",
        tools,
        limit=32,
    )

    selected_names = {tool.name for tool in selected}
    assert selected_names == {
        "agent_knowledge_search",
        "agent_web_search",
    }
    assert "google_list_customer_clients" not in selected_names


def test_colloquial_look_request_requires_the_selected_discovery_tool():
    tools = _semantic_discovery_definitions()
    selector = ToolSelector()

    for request in (
        "看下Google的股票趋势",
        "帮我看看 QuantaBridge 的近期趋势",
        "看一下 QuantaBridge 的近期趋势",
    ):
        selected = selector.select_relevant(request, tools)

        assert selected
        assert selector.is_read_only_request(request, selected)
        assert selector.requires_tool_call(request, selected)


def test_explicit_namespaces_and_intent_metadata_beat_generic_recipe_aliases():
    tools = [
        {
            "name": f"{namespace}_read_record",
            "namespace": namespace,
            "action": "list",
            "resource_type": "resource",
            "effect_class": "read",
            "intent_types": ["list_records"],
            "description": f"Read records from {namespace}",
        }
        for namespace in ("alpha", "beta")
    ]
    tools.append({
        "name": "agent_readonly_recipe",
        "namespace": "platform",
        "action": "transform",
        "resource_type": "json_records",
        "effect_class": "read",
        "intent_aliases": ["filter these records", "aggregate these results"],
    })

    selected = ToolSelector().select_relevant(
        "Read records from alpha and beta",
        tools,
    )

    assert {tool["name"] for tool in selected} == {
        "alpha_read_record",
        "beta_read_record",
    }


def _semantic_discovery_definitions():
    return [
        binding.definition
        for source in (
            web_search_tool_source(
                configuration_provider=lambda: {},
                required_permission="ads.read",
            ),
            knowledge_search_tool_source(
                provider=object(),
                required_permission="ads.read",
            ),
        )
        for binding in source.list_bindings()
    ]


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
