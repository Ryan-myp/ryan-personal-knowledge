from __future__ import annotations

import json
from types import MappingProxyType, SimpleNamespace

import pytest

from agents.agent_harness import (
    AgentApplication, AgentMessage,
    StaticToolSource,
    ToolBinding,
    TurnRequest,
)
from agents.agent_harness.core.interfaces import (
    ToolDefinition,
    ToolEffect,
    ToolSchema,
)
from agents.agent_harness.core.llm_client import LLMClient
from agents.agent_harness.core.tool_selection import ToolSelector
from agents.agent_harness.messages import ModelTurn, ToolCall
from agents.agent_platform.tools.policy import ToolExecutionPolicy


def _definition(
    name: str,
    *,
    namespace: str,
    action: str,
    resource: str,
    description: str,
    intent_types: tuple[str, ...] = (),
    intent_aliases: tuple[str, ...] = (),
    properties: dict | None = None,
    parent_resource: str | None = None,
) -> ToolDefinition:
    return ToolDefinition(
        name=name,
        skill=namespace,
        namespace=namespace,
        description=description,
        input_schema=ToolSchema(properties=properties or {}),
        action=action,
        resource_type=resource,
        intent_types=list(intent_types),
        intent_aliases=list(intent_aliases),
        parent_resource_type=parent_resource,
        effect_class=(
            ToolEffect.READ
            if action in {"get", "list", "read", "search", "query", "fetch"}
            else ToolEffect.WRITE
        ),
    )


def test_read_request_does_not_select_write_tools_and_remains_bounded():
    tools = [
        _definition(
            "find_campaigns",
            namespace="google-ads",
            action="list",
            resource="campaign",
            description="列出广告系列及其投放状态",
            intent_types=("list_campaigns",),
        ),
        _definition(
            "update_campaign_budget",
            namespace="google-ads",
            action="update",
            resource="campaign",
            description="Update a campaign daily budget",
            properties={"campaign_id": {"type": "string"}},
        ),
        *[
            _definition(
                f"read_invoice_{index}",
                namespace="billing",
                action="get",
                resource="invoice",
                description="Read one invoice by identifier",
            )
            for index in range(20)
        ],
    ]

    selected = ToolSelector().select_relevant(
        "列出 Google Ads campaigns", tools, limit=2,
    )

    assert [item.name for item in selected] == ["find_campaigns"]


def test_compound_list_and_detail_request_keeps_both_read_tools():
    tools = [
        _definition(
            "meta_list_campaigns",
            namespace="meta",
            action="list",
            resource="campaign",
            description="List Meta campaigns",
        ),
        _definition(
            "meta_get_campaign",
            namespace="meta",
            action="get",
            resource="campaign",
            description="Get one Meta campaign by ID",
        ),
    ]

    selector = ToolSelector()
    list_only = selector.select_relevant(
        "查询 Meta campaign 列表",
        tools,
    )
    assert [item.name for item in list_only] == ["meta_list_campaigns"]

    selected = selector.select_relevant(
        "查询 Meta campaign 列表和详情",
        tools,
    )

    assert {item.name for item in selected} == {
        "meta_list_campaigns",
        "meta_get_campaign",
    }


def test_explicit_tool_name_narrows_selection_to_the_named_registered_tool():
    tools = [
        _definition(
            "google_list_campaigns",
            namespace="google-ads",
            action="list",
            resource="campaign",
            description="List campaigns",
        ),
        _definition(
            "google_update_campaign",
            namespace="google-ads",
            action="update",
            resource="campaign",
            description="Update a campaign",
        ),
    ]

    selected = ToolSelector().select_relevant(
        "只调用 google_list_campaigns 一次，不得启用或修改广告。",
        tools,
        limit=8,
    )

    assert [item.name for item in selected] == ["google_list_campaigns"]


def test_read_intent_with_negative_write_constraints_selects_reads_only():
    tools = [
        _definition(
            "list_campaigns",
            namespace="ads",
            action="list",
            resource="campaign",
            description="List campaigns",
        ),
        _definition(
            "pause_campaign",
            namespace="ads",
            action="pause",
            resource="campaign",
            description="Pause a campaign",
        ),
        _definition(
            "update_campaign",
            namespace="ads",
            action="update",
            resource="campaign",
            description="Update a campaign",
        ),
    ]

    selected = ToolSelector().select_relevant(
        "列出 campaigns，只查询，不要暂停、启用或更新任何 campaign。",
        tools,
        limit=8,
    )

    assert [item.name for item in selected] == ["list_campaigns"]


def test_explicit_current_namespace_overrides_conversation_history():
    tools = [
        _definition(
            "meta_list_campaigns",
            namespace="meta",
            action="list",
            resource="campaign",
            description="列出 Meta 广告系列",
        ),
        _definition(
            "google_list_campaigns",
            namespace="google-ads",
            action="list",
            resource="campaign",
            description="列出 Google Ads 广告系列",
        ),
    ]

    selected = ToolSelector().select_relevant(
        "列出 Google Ads campaigns",
        tools,
        conversation_context=("帮我查询 Meta campaign",),
    )

    assert [item.name for item in selected] == ["google_list_campaigns"]


def test_child_list_alias_treats_parent_resource_as_scope():
    tools = [
        _definition(
            "meta_list_ad_sets",
            namespace="meta",
            action="list",
            resource="ad_set",
            description="List Meta Ad Sets",
        ),
        _definition(
            "meta_list_ads",
            namespace="meta",
            action="list",
            resource="ad",
            description="List Meta Ads",
            intent_aliases=("Ad 列表",),
            parent_resource="ad_set",
        ),
    ]

    selected = ToolSelector().select_relevant(
        "查询 Meta 测试账户 Ad Set ID 123 下的 Ad 列表，只查询一次。",
        tools,
        limit=32,
    )

    assert [item.name for item in selected] == ["meta_list_ads"]


def test_cross_channel_request_keeps_tools_when_namespace_alias_is_not_registered():
    tools = [
        _definition(
            "meta_delete_campaign",
            namespace="meta",
            action="delete",
            resource="campaign",
            description="Delete a Meta campaign",
        ),
        _definition(
            "google_delete_campaign",
            namespace="google-ads",
            action="delete",
            resource="campaign",
            description="Delete a Google Ads campaign",
        ),
        _definition(
            "tiktok_delete_campaign",
            namespace="tiktok",
            action="delete",
            resource="campaign",
            description="Delete a TikTok campaign",
        ),
        _definition(
            "dv360_delete_campaign",
            namespace="dv360",
            action="delete",
            resource="campaign",
            description="Delete a DV360 campaign",
        ),
    ]

    selected = ToolSelector().select_relevant(
        "跨渠道删除 Meta、Google、TikTok、DV360 campaign",
        tools,
        limit=64,
    )

    assert {
        item.name for item in selected
        if item.action == "delete" and item.resource_type == "campaign"
    } == {
        "meta_delete_campaign",
        "google_delete_campaign",
        "tiktok_delete_campaign",
        "dv360_delete_campaign",
    }


def test_write_tool_call_is_required_only_for_explicit_matching_write():
    selector = ToolSelector()
    create_campaign = _definition(
        "meta_create_campaign",
        namespace="meta",
        action="create",
        resource="campaign",
        description="Create a Meta campaign",
    )
    list_campaigns = _definition(
        "meta_list_campaigns",
        namespace="meta",
        action="list",
        resource="campaign",
        description="List Meta campaigns",
    )

    assert selector.requires_tool_call(
        "创建 Meta campaign", [create_campaign],
    )
    assert not selector.requires_tool_call(
        "不要创建 Meta campaign", [create_campaign],
    )
    assert not selector.requires_tool_call(
        "创建 Meta campaign", [list_campaigns],
    )
    assert not selector.requires_tool_call(
        "你好，你有什么能力？", [create_campaign],
    )


def test_relevant_tool_selection_returns_empty_for_unmatched_request():
    tools = [
        _definition(
            "read_invoice",
            namespace="billing",
            action="get",
            resource="invoice",
            description="Read one invoice by identifier",
        ),
    ]

    assert ToolSelector().select_relevant("Tell me a joke", tools) == []


def test_short_channel_comparison_followup_does_not_expose_provider_tools():
    tools = [
        _definition(
            "meta_list_campaigns",
            namespace="meta",
            action="list",
            resource="campaign",
            description="List Meta campaigns",
        ),
        _definition(
            "tiktok_list_campaigns",
            namespace="tiktok",
            action="list",
            resource="campaign",
            description="List TikTok campaigns",
        ),
        _definition(
            "tiktok_create_campaign",
            namespace="tiktok",
            action="create",
            resource="campaign",
            description="Create a TikTok campaign",
        ),
    ]
    selector = ToolSelector()

    assert selector.select_relevant(
        "tiktok ads 呢",
        tools,
        conversation_context=("Meta 广告投放目标应该怎么选？",),
    ) == []
    assert selector.select_relevant(
        "What about TikTok Ads?",
        tools,
        conversation_context=("How should I choose a Meta campaign objective?",),
    ) == []


def test_actionable_channel_followup_still_selects_matching_provider_tool():
    tools = [
        _definition(
            "tiktok_list_campaigns",
            namespace="tiktok",
            action="list",
            resource="campaign",
            description="List TikTok campaigns",
        ),
        _definition(
            "tiktok_create_campaign",
            namespace="tiktok",
            action="create",
            resource="campaign",
            description="Create a TikTok campaign",
        ),
    ]
    selector = ToolSelector()

    assert [
        item.name for item in selector.select_relevant(
            "查询 TikTok campaign 列表",
            tools,
        )
    ] == ["tiktok_list_campaigns"]
    selected = selector.select_relevant("创建 TikTok campaign", tools)
    assert "tiktok_create_campaign" in {
        item.name for item in selected
    }


def test_self_contained_architecture_request_ignores_previous_provider_query():
    tools = [
        _definition(
            "meta_list_campaigns",
            namespace="meta",
            action="list",
            resource="campaign",
            description="List Meta campaigns",
        ),
        _definition(
            "meta_list_video_assets",
            namespace="meta",
            action="list",
            resource="video_asset",
            description="List Meta video assets",
        ),
        _definition(
            "meta_list_image_assets",
            namespace="meta",
            action="list",
            resource="image_asset",
            description="List Meta image assets",
        ),
    ]

    selected = ToolSelector().select_relevant(
        "你画一个当前系统run的流程图吧",
        tools,
        conversation_context=(
            "查询 Meta campaign、video assets 和 image assets",
        ),
    )

    assert selected == []


def test_current_run_flowchart_never_reuses_historical_provider_asset_queries():
    tools = [
        _definition(
            "meta_list_campaigns",
            namespace="meta",
            action="list",
            resource="campaign",
            description="List Meta campaigns",
        ),
        _definition(
            "meta_list_video_assets",
            namespace="meta",
            action="list",
            resource="video_asset",
            description="List Meta video assets",
        ),
        _definition(
            "meta_list_image_assets",
            namespace="meta",
            action="list",
            resource="image_asset",
            description="List Meta image assets",
        ),
    ]

    selected = ToolSelector().select_relevant(
        "根据刚才的实际执行流程，画一个当前系统 Run 流程图",
        tools,
        conversation_context=(
            "查询 Meta campaign、video assets 和 image assets",
        ),
    )

    assert selected == []


def test_advertising_process_explanations_do_not_select_provider_tools():
    tools = [
        _definition(
            "meta_list_campaigns",
            namespace="meta",
            action="list",
            resource="campaign",
            description="List Meta campaigns",
        ),
        _definition(
            "meta_get_campaign_report",
            namespace="meta",
            action="get",
            resource="campaign_report",
            description="Get a Meta campaign performance report",
        ),
        _definition(
            "meta_create_campaign",
            namespace="meta",
            action="create",
            resource="campaign",
            description="Create a Meta campaign",
        ),
    ]

    requests = (
        "画一个meta广告创建流程",
        "创意分析流程呢",
        "账户诊断流程",
    )
    for request in requests:
        assert ToolSelector().select_relevant(
            request,
            tools,
            conversation_context=("查询 Meta campaign 列表",),
        ) == []


def test_targeting_setting_explanation_does_not_select_provider_tools():
    tools = [
        _definition(
            "tiktok_list_targeting_options",
            namespace="tiktok",
            action="list",
            resource="targeting_options",
            description="查询 TikTok 定向和兴趣选项",
        ),
        _definition(
            "tiktok_update_ad_group",
            namespace="tiktok",
            action="update",
            resource="ad_group",
            description="更新 TikTok 广告组定向设置",
        ),
    ]
    selector = ToolSelector()

    for request in (
        "定向设置详解",
        "详细讲解 TikTok 受众定向设置",
        "What is audience targeting?",
    ):
        assert selector.select_relevant(
            request,
            tools,
            conversation_context=("查询 TikTok campaign 列表",),
        ) == [], request

    assert [
        item.name for item in selector.select_relevant(
            "查询 TikTok 定向选项",
            tools,
        )
    ] == ["tiktok_list_targeting_options"]
    updated = {
        item.name for item in selector.select_relevant(
            "帮我更新 TikTok 广告组定向",
            tools,
        )
    }
    assert "tiktok_update_ad_group" in updated


def test_broad_channel_knowledge_requests_do_not_select_account_tools():
    tools = [
        _definition(
            "google_list_accounts",
            namespace="google-ads",
            action="list",
            resource="account",
            description="List Google Ads accounts",
        ),
        _definition(
            "google_list_campaigns",
            namespace="google-ads",
            action="list",
            resource="campaign",
            description="List campaigns for a Google Ads account",
        ),
        _definition(
            "google_get_campaign",
            namespace="google-ads",
            action="get",
            resource="campaign",
            description="Get a Google Ads campaign",
        ),
        _definition(
            "google_update_campaign",
            namespace="google-ads",
            action="update",
            resource="campaign",
            description="Update a Google Ads campaign",
        ),
        _definition(
            "tiktok_list_accounts",
            namespace="tiktok",
            action="list",
            resource="account",
            description="List TikTok advertiser accounts",
        ),
    ]
    selector = ToolSelector()

    for request in (
        "讲下Google ads相关知识",
        "讲下Google Ads相关知识，使用账户 1234567890 继续",
        "介绍一下 TikTok Ads 的基础知识",
    ):
        assert selector.select_relevant(
            request,
            tools,
            conversation_context=("查询 Google Ads campaign 列表",),
        ) == [], request

    assert [
        item.name for item in selector.select_relevant(
            "查询 Google Ads campaign 列表",
            tools,
        )
    ] == ["google_list_campaigns"]
    assert "google_update_campaign" in {
        item.name for item in selector.select_relevant(
            "讲下 Google Ads 相关知识，并更新 campaign budget",
            tools,
        )
    }


def test_explicit_campaign_operations_remain_routable_with_process_language():
    tools = [
        _definition(
            "meta_list_campaigns",
            namespace="meta",
            action="list",
            resource="campaign",
            description="List Meta campaigns",
        ),
        _definition(
            "meta_create_campaign",
            namespace="meta",
            action="create",
            resource="campaign",
            description="Create a Meta campaign",
        ),
    ]
    selector = ToolSelector()

    assert [
        item.name for item in selector.select_relevant(
            "查询 Meta campaign 列表",
            tools,
        )
    ] == ["meta_list_campaigns"]
    selected = selector.select_relevant(
        "创建 Meta campaign，并说明创建流程",
        tools,
    )
    assert any(item.name == "meta_create_campaign" for item in selected)
    assert [
        item.name for item in selector.select_relevant(
            "画一个 Meta campaign 创建流程",
            tools,
        )
    ] == []


def test_process_explanation_turn_completes_without_executing_provider_tools():
    executions = []

    class Model:
        def complete(self, _messages, tools, _request):
            assert tools == []
            return ModelTurn(content=(
                "flowchart TD\n"
                "  A[选择账户与目标] --> B[配置 Campaign]\n"
                "  B --> C[配置 Ad Group]\n"
                "  C --> D[准备 Ad 与 Creative]"
            ))

    definition = _definition(
        "meta_list_campaigns",
        namespace="meta",
        action="list",
        resource="campaign",
        description="List Meta campaigns",
    )
    selector = ToolSelector()
    app = AgentApplication.create(
        model=Model(),
        tool_selector=lambda request, tools: selector.select_relevant(
            request.user_input,
            tools,
            conversation_context=request.context.get(
                "_agent_tool_selection_context", (),
            ),
        ),
    )
    app.register_tool_source(StaticToolSource("advertising", [
        ToolBinding(
            definition,
            lambda _context, _values: executions.append("called"),
        ),
    ]))
    try:
        result = app.runtime.run(TurnRequest(
            user_input="画一个meta广告创建流程",
            user_id="operator",
        ))

        assert result.status.value == "succeeded"
        assert executions == []
    finally:
        app.close()


def test_unselected_tool_is_rejected_when_request_context_is_missing():
    executions = []

    class Model:
        def complete(self, _messages, tools, _request):
            assert tools == []
            return ModelTurn(tool_calls=(
                ToolCall("hallucinated", "private_write", {"value": "x"}),
            ))

    app = AgentApplication.create(
        model=Model(),
        tool_selector=lambda _request, _tools: [],
    )
    app.register_tool_source(StaticToolSource("private", [
        ToolBinding(
            {"name": "private_write", "effect_class": "write"},
            lambda _context, value: executions.append(value) or {
                "success": True,
            },
        ),
    ]))
    try:
        result = app.runtime.run(TurnRequest(
            user_input="unmatched request",
            context=MappingProxyType({}),
        ))

        assert executions == []
        assert result.status.value == "failed"
        blocked = result.data["tool_results"][0]
        assert blocked["runtime_signals"]["tool_allowlist_violation"] is True
    finally:
        app.close()


def test_relevant_tool_selection_rejects_non_positive_limit():
    selector = ToolSelector()

    try:
        selector.select_relevant("read record", [], limit=0)
    except ValueError as error:
        assert "limit" in str(error)
    else:
        raise AssertionError("non-positive limit should be rejected")


def test_default_tool_subset_stays_bounded():
    tools = [
        _definition(
            f"lookup_record_{index}",
            namespace="records",
            action="get",
            resource="record",
            description="Look up a record",
        )
        for index in range(24)
    ]

    selected = ToolSelector().select_relevant("record", tools)

    assert len(selected) == 16


def test_channel_context_from_recent_user_turns_routes_short_followup():
    class Model:
        def __init__(self):
            self.visible_tools = []
            self.model_contexts = []
            self.turn = 0

        def complete(self, _messages, tools, request):
            self.visible_tools.append([
                item.get("name") if isinstance(item, dict) else item.name
                for item in tools
            ])
            self.model_contexts.append(dict(request.context))
            self.turn += 1
            if self.turn == 1:
                return ModelTurn(content="你要查询哪个渠道？")
            if self.turn == 2:
                return ModelTurn(content="要查询哪个广告账户？")
            if self.turn == 3:
                return ModelTurn(tool_calls=(
                    ToolCall("accounts", "meta_list_accounts", {}),
                ))
            return ModelTurn(content="当前授权的 Meta 账户已列出。")

    definitions = [
        _definition(
            "meta_list_campaigns",
            namespace="meta",
            action="list",
            resource="campaign",
            description="列出 Meta 广告系列",
        ),
        _definition(
            "meta_list_accounts",
            namespace="meta",
            action="list",
            resource="account",
            description="列出 Meta 可访问的广告账户",
        ),
        _definition(
            "meta_create_campaign",
            namespace="meta",
            action="create",
            resource="campaign",
            description="创建 Meta 广告系列",
        ),
        _definition(
            "google_list_accounts",
            namespace="google-ads",
            action="list",
            resource="account",
            description="List Google Ads accounts",
        ),
    ]
    model = Model()
    selector = ToolSelector()
    selection_histories = []

    def select_tools(request, tools):
        history = request.context.get("_agent_tool_selection_context", ())
        selection_histories.append(tuple(history))
        return selector.select_relevant(
            request.user_input,
            tools,
            conversation_context=history,
        )

    app = AgentApplication.create(
        model=model,
        tool_selector=select_tools,
        tool_execution="sequential",
    )
    app.register_tool_source(StaticToolSource(
        "advertising",
        [
            ToolBinding(
                definition,
                lambda _context, _values: {
                    "success": True,
                    "data": {"accounts": ["test-account"]},
                },
            )
            for definition in definitions
        ],
    ))
    try:
        for user_input in (
            "帮我查一下 campaign",
            "Meta",
            "有哪些 account 呢",
        ):
            result = app.runtime.run(TurnRequest(
                user_input=user_input,
                session_id="clarification-session",
                user_id="operator",
            ))

        assert len(model.visible_tools) >= 3, (
            model.visible_tools, selection_histories, result.to_dict()
        )
        assert "meta_list_accounts" in model.visible_tools[2], (
            model.visible_tools, selection_histories, result.to_dict()
        )
        assert result.status.value == "succeeded", result.to_dict()
        assert selection_histories[0] == ()
        assert selection_histories[1] == ("帮我查一下 campaign",)
        assert selection_histories[2] == (
            "帮我查一下 campaign",
            "Meta",
        )
        assert "meta_list_campaigns" in model.visible_tools[1]
        assert "google_list_accounts" not in model.visible_tools[1]
        assert "meta_list_accounts" in model.visible_tools[2]
        assert "google_list_accounts" not in model.visible_tools[2]
        assert "meta_create_campaign" not in model.visible_tools[2]
        assert "meta_list_accounts" in model.visible_tools[3]
        assert "google_list_accounts" not in model.visible_tools[3]
        assert all(
            "_agent_tool_selection_context" not in context
            for context in model.model_contexts
        )
    finally:
        app.close()


def test_explicit_write_uses_required_tool_choice_only_for_initial_model_turn():
    class Model:
        def __init__(self):
            self.tool_choices = []
            self.turn = 0

        def complete(self, _messages, _tools, request):
            self.tool_choices.append(request.initial_tool_choice)
            self.turn += 1
            if self.turn == 1:
                return ModelTurn(tool_calls=(
                    ToolCall("create", "meta_create_campaign", {}),
                ))
            return ModelTurn(content="已生成 dry-run 计划。")

    selector = ToolSelector()
    definition = _definition(
        "meta_create_campaign",
        namespace="meta",
        action="create",
        resource="campaign",
        description="Create a Meta campaign",
    )
    model = Model()

    def select_tools(request, tools):
        selected = selector.select_relevant(
            request.user_input,
            tools,
            conversation_context=request.context.get(
                "_agent_tool_selection_context", (),
            ),
        )
        if selector.requires_tool_call(request.user_input, selected):
            request.context["_agent_tool_choice_required"] = True
        return selected

    app = AgentApplication.create(
        model=model,
        tool_selector=select_tools,
        tool_execution="sequential",
    )
    app.register_tool_source(StaticToolSource(
        "advertising",
        [ToolBinding(definition, lambda _context, _values: {"success": True})],
    ))
    try:
        result = app.runtime.run(TurnRequest(
            user_input="创建 Meta campaign",
            user_id="operator",
        ))

        assert result.status.value == "succeeded"
        assert model.tool_choices == ["required", None]
    finally:
        app.close()


def test_clarification_choice_restores_original_tool_intent_without_web_discovery():
    selector = ToolSelector()
    selected_inputs = []

    def select_tools(request, tools):
        selected_inputs.append(request.user_input)
        selected = selector.select_relevant(request.user_input, tools)
        if selector.requires_tool_call(request.user_input, selected):
            request.context["_agent_tool_choice_required"] = True
        return selected

    render = _definition(
        "render_visual", namespace="creative", action="generate",
        resource="visual_asset", description="生成视觉素材",
        intent_aliases=("生成视觉素材",),
    )
    discovery = ToolDefinition(
        name="external_lookup", skill="research", namespace="research",
        description="搜索外部网页", input_schema=ToolSchema(properties={}),
        action="search", resource_type="web", intent_types=["web_search"],
        intent_aliases=["搜索网页"], effect_class=ToolEffect.READ,
        traits=["semantic_discovery", "web_search"],
    )
    app = AgentApplication.create(
        model=SimpleNamespace(complete=lambda *_args: ModelTurn(content="")),
        tool_selector=select_tools,
    )
    app.register_tool_source(StaticToolSource(
        "test", [
            ToolBinding(render, lambda *_args: {"success": True}),
            ToolBinding(discovery, lambda *_args: {"success": True}),
        ],
    ))
    transcript = [
        AgentMessage.user("生成视觉素材", turn_id="previous"),
        AgentMessage.tool(
            json.dumps({
                "success": True, "needs_input": True,
                "data": {"choices": ["深蓝背景", "暖色背景"]},
            }),
            tool_call_id="clarify", name="request_input", turn_id="previous",
        ),
    ]
    try:
        choice = TurnRequest("深蓝背景", turn_id="current", session_id="same")
        tools, required = app.agent._tools_for_turn(choice, transcript)
        assert [tool.name for tool in tools] == ["render_visual"]
        assert required is True
        assert selected_inputs[-1] == "生成视觉素材\n深蓝背景"
        assert choice.user_input == "深蓝背景"

        new_topic = TurnRequest("暖色数据报表", turn_id="other", session_id="same")
        app.agent._tools_for_turn(new_topic, transcript)
        assert selected_inputs[-1] == "暖色数据报表"
    finally:
        app.close()


def test_clarification_only_uses_the_immediately_previous_offered_choice():
    selector = ToolSelector()
    seen = []

    def select_tools(request, tools):
        seen.append(request.user_input)
        return selector.select_relevant(request.user_input, tools)

    app = AgentApplication.create(
        model=SimpleNamespace(complete=lambda *_args: ModelTurn(content="")),
        tool_selector=select_tools,
    )
    app.register_tool_source(StaticToolSource("test", [
        ToolBinding(_definition(
            "render_visual", namespace="creative", action="generate",
            resource="visual_asset", description="生成视觉素材",
            intent_aliases=("生成视觉素材",),
        ), lambda *_args: {"success": True}),
    ]))
    origin = AgentMessage.user("生成视觉素材", turn_id="origin")
    clarification = AgentMessage.tool(
        {"needs_input": True, "data": {"choices": ["深蓝背景"]}},
        tool_call_id="clarify", name="request_input", turn_id="origin",
    )
    try:
        app.agent._tools_for_turn(
            TurnRequest("深蓝背景", turn_id="reply"),
            [origin, clarification, AgentMessage.assistant(
                "请选择背景", turn_id="origin",
            )],
        )
        assert seen[-1] == "生成视觉素材\n深蓝背景"

        for response in (
            {"needs_input": False, "data": {"choices": ["深蓝背景"]}},
            {"needs_input": True, "data": {"choices": ["其他选项"]}},
            "{malformed",
        ):
            app.agent._tools_for_turn(
                TurnRequest("深蓝背景", turn_id="reply"),
                [origin, AgentMessage.tool(
                    response, tool_call_id="clarify", name="request_input",
                    turn_id="origin",
                )],
            )
            assert seen[-1] == "深蓝背景"

        app.agent._tools_for_turn(
            TurnRequest("深蓝背景", turn_id="new"),
            [origin, clarification, AgentMessage.user(
                "另一个问题", turn_id="intervening",
            )],
        )
        assert seen[-1] == "深蓝背景"
    finally:
        app.close()


@pytest.mark.parametrize("with_clarification", [False, True])
def test_selecting_a_recent_list_item_routes_to_its_registered_detail_tool(with_clarification):
    selector = ToolSelector()
    list_tool = ToolDefinition(
        name="tiktok_list_creation_templates",
        skill="tiktok",
        namespace="tiktok",
        description="List available creation templates",
        input_schema=ToolSchema(properties={}),
        action="list",
        resource_type="creation_template",
        intent_types=["list_creation_templates"],
        effect_class=ToolEffect.READ,
        result_items_key="templates",
        result_id_fields=["template_id"],
    )
    get_tool = ToolDefinition(
        name="tiktok_get_creation_template",
        skill="tiktok",
        namespace="tiktok",
        description="Read a selected creation template",
        input_schema=ToolSchema(
            properties={"template_id": {"type": "string"}},
            required=["template_id"],
        ),
        action="get",
        resource_type="creation_template",
        intent_types=["get_creation_template"],
        intent_aliases=["使用模板", "选择模板", "预览模板"],
        effect_class=ToolEffect.READ,
    )

    def select_tools(request, tools):
        selected = selector.select_relevant(request.user_input, tools)
        if selector.requires_tool_call(request.user_input, selected):
            request.context["_agent_tool_choice_required"] = True
        return selected

    app = AgentApplication.create(
        model=SimpleNamespace(complete=lambda *_args: ModelTurn(content="")),
        tool_selector=select_tools,
    )
    app.register_tool_source(StaticToolSource("catalog", [
        ToolBinding(list_tool, lambda *_args: {"success": True}),
        ToolBinding(get_tool, lambda *_args: {"success": True}),
    ]))
    transcript = [
        AgentMessage.user("创建 TikTok 广告系列", turn_id="catalog-turn"),
        AgentMessage.tool(
            {
                "success": True,
                "data": {
                    "templates": [{
                        "template_id": "tiktok.product-sales",
                        "name": "TikTok 测试账号 · 商品目录销售",
                    }],
                },
            },
            tool_call_id="catalog-call",
            name=list_tool.name,
            turn_id="catalog-turn",
        ),
        AgentMessage.assistant("找到一个模板。", turn_id="catalog-turn"),
    ]
    choice = "TikTok 测试账号 · 商品目录销售（补充名称、排期、预算）"
    if with_clarification:
        transcript.append(AgentMessage.tool(
            {
                "success": True,
                "needs_input": True,
                "data": {"choices": [choice, "不使用模板"]},
            },
            name="ask_for_choice",
            tool_call_id="clarify",
            turn_id="catalog-turn",
        ))
    try:
        tools, required = app.agent._tools_for_turn(
            TurnRequest(
                choice,
                turn_id="selection-turn",
                session_id="catalog-session",
            ),
            transcript,
        )
        assert [tool.name for tool in tools] == [get_tool.name]
        assert required is True
        selected_request, target = app.agent._tool_selection_request(
            TurnRequest(choice, turn_id="selection-turn"),
            transcript,
            app.agent.tool_catalog.list_tools(),
        )
        assert target == get_tool.name
        assert "tiktok.product-sales" in selected_request.user_input
    finally:
        app.close()


def test_explicit_local_catalog_alias_beats_large_same_namespace_write_schemas():
    catalog = ToolDefinition(
        name="docs_list_presets", namespace="docs", skill="docs",
        description="List local document presets.", action="list",
        resource_type="preset", intent_aliases=["列出预设"],
        traits=["read", "local", "catalog"], input_schema=ToolSchema(),
    )
    write = ToolDefinition(
        name="docs_publish", namespace="docs", skill="docs",
        description="Publish a document using a preset.", action="create",
        resource_type="document", effect_class=ToolEffect.WRITE,
        input_schema=ToolSchema(properties={"settings": {
            "type": "object", "description": "x" * 20000,
        }}),
    )
    selected = ToolSelector().select_relevant(
        "创建 docs document，先列出预设，不要提交。", [write, catalog],
    )
    assert [tool.name for tool in selected] == [catalog.name]
    assert ToolSelector().requires_tool_call(
        "创建 docs document，先列出预设，不要提交。", selected,
    )


class _Completions:
    def __init__(self, tool_name="lookup_record"):
        self.requests = []
        self.responses = [
            SimpleNamespace(
                choices=[SimpleNamespace(
                    message=SimpleNamespace(
                        content="",
                        tool_calls=[SimpleNamespace(
                            id="call-1",
                            function=SimpleNamespace(
                                name=tool_name,
                                arguments='{"record_id":"r-17"}',
                            ),
                        )],
                    ),
                    finish_reason="tool_calls",
                )],
                usage=None,
            ),
            SimpleNamespace(
                choices=[SimpleNamespace(
                    message=SimpleNamespace(content="Record r-17 is ready.", tool_calls=[]),
                    finish_reason="stop",
                )],
                usage=None,
            ),
        ]

    def create(self, **kwargs):
        self.requests.append(kwargs)
        return self.responses.pop(0)


def test_generic_model_tool_call_runs_through_harness_and_returns_result_to_model():
    completions = _Completions()
    client = LLMClient(model="test-model", api_key="test-only")
    client._client = SimpleNamespace(
        chat=SimpleNamespace(completions=completions),
    )
    definition = _definition(
        "lookup_record",
        namespace="records",
        action="get",
        resource="record",
        description="Look up one record by identifier",
        properties={"record_id": {"type": "string"}},
    )
    executed = []
    preflight = []

    def execute(_context, values):
        executed.append(dict(values))
        return {"success": True, "data": {"record_id": values["record_id"]}}

    def before_tool_call(context):
        preflight.append(context.tool_call.name)

    app = AgentApplication.create(
        model=client,
        tool_selector=lambda request, tools: ToolSelector().select_relevant(
            request.user_input, tools, limit=4,
        ),
        before_tool_call=before_tool_call,
        tool_execution="sequential",
    )
    app.register_tool_source(StaticToolSource(
        "records",
        [ToolBinding(definition, execute)],
    ))
    try:
        result = app.runtime.run(TurnRequest(
            user_input="Look up record r-17",
            session_id="session-1",
            user_id="user-1",
            tenant_id="tenant-1",
        ))

        assert result.status.value == "succeeded", result.to_dict()
        assert result.reply == "Record r-17 is ready."
        assert executed == [{"record_id": "r-17"}]
        assert preflight == ["lookup_record"]
        assert len(completions.requests) == 2
        assert completions.requests[1]["messages"][-1]["role"] == "tool"
        assert completions.requests[1]["messages"][-1]["content"].find("r-17") >= 0
        assert result.run_id
        assert result.turn_id
    finally:
        app.close()


def test_request_validator_rejects_before_model_and_keeps_run_identity():
    calls = []

    def model(_messages, _tools, _request):
        calls.append("called")
        return "must not run"

    app = AgentApplication.create(
        model=model,
        request_validator=lambda _request: "request is outside policy",
    )
    try:
        result = app.runtime.run(TurnRequest(
            user_input="do work",
            session_id="session-1",
            user_id="user-1",
            tenant_id="tenant-1",
        ))

        assert result.status.value == "failed"
        assert result.reply == "request is outside policy"
        assert result.run_id
        assert result.turn_id
        assert result.data["request_validation_error"] == "request is outside policy"
        assert calls == []
    finally:
        app.close()


def test_missing_model_adapter_fails_with_explicit_nonempty_run_error():
    app = AgentApplication.create(model=None)
    try:
        result = app.runtime.run(TurnRequest(
            user_input="Do work",
            session_id="unconfigured-model-session",
            user_id="user-1",
            tenant_id="tenant-1",
        ))

        assert result.status.value == "failed"
        assert result.reply
        assert "模型" in result.reply
        assert result.data["error"] == "model_not_configured"
    finally:
        app.close()


def test_run_tool_call_budget_rejects_oversized_batch_atomically():
    calls = []

    class Model:
        def __init__(self):
            self.invocations = 0

        def complete(self, _messages, _tools, _request):
            self.invocations += 1
            return ModelTurn(tool_calls=(
                ToolCall("call-1", "read_first", {}),
                ToolCall("call-2", "read_second", {}),
            ))

    model = Model()
    app = AgentApplication.create(
        model=model,
        max_tool_calls_per_run=1,
        tool_execution="sequential",
    )
    definition = _definition(
        "read_first", namespace="records", action="get", resource="record",
        description="Read the first record",
    )
    second = _definition(
        "read_second", namespace="records", action="get", resource="record",
        description="Read the second record",
    )

    def execute(_context, _input):
        calls.append(True)
        return {"success": True}

    app.register_tool_source(StaticToolSource("records", [
        ToolBinding(definition, execute),
        ToolBinding(second, execute),
    ]))
    try:
        result = app.runtime.run(TurnRequest(user_input="read records"))

        assert result.status.value == "failed"
        assert result.runtime_signals["tool_call_budget_exceeded"] is True
        assert result.data["tool_call_count"] == 0
        assert len(result.data["tool_results"]) == 2
        assert all(item["is_error"] for item in result.data["tool_results"])
        assert calls == []
        assert model.invocations == 1
    finally:
        app.close()


def test_run_tool_call_budget_applies_across_model_turns():
    calls = []

    class Model:
        def __init__(self):
            self.turns = iter((
                ModelTurn(tool_calls=(ToolCall("call-1", "read_first", {}),)),
                ModelTurn(tool_calls=(ToolCall("call-2", "read_second", {}),)),
            ))
            self.invocations = 0

        def complete(self, _messages, _tools, _request):
            self.invocations += 1
            return next(self.turns)

    model = Model()
    app = AgentApplication.create(
        model=model,
        max_tool_calls_per_run=1,
        tool_execution="sequential",
    )
    bindings = []
    for name in ("read_first", "read_second"):
        definition = _definition(
            name, namespace="records", action="get", resource="record",
            description=f"Read {name.replace('_', ' ')}",
        )

        def execute(_context, _input, tool_name=name):
            calls.append(tool_name)
            return {"success": True}

        bindings.append(ToolBinding(definition, execute))
    app.register_tool_source(StaticToolSource("records", bindings))
    try:
        result = app.runtime.run(TurnRequest(user_input="read records"))

        assert result.status.value == "failed"
        assert result.runtime_signals["tool_call_budget_exceeded"] is True
        assert result.data["tool_call_count"] == 1
        assert calls == ["read_first"]
        assert model.invocations == 2
    finally:
        app.close()


def test_generic_model_tool_call_confirmation_gate_prevents_executor_run():
    completions = _Completions(tool_name="publish_record")
    client = LLMClient(model="test-model", api_key="test-only")
    client._client = SimpleNamespace(
        chat=SimpleNamespace(completions=completions),
    )
    definition = _definition(
        "publish_record",
        namespace="records",
        action="publish",
        resource="record",
        description="Publish a record",
        properties={"record_id": {"type": "string"}},
    )
    executed = []

    def execute(_context, values):
        executed.append(dict(values))
        return {"success": True}

    app = AgentApplication.create(
        model=client,
        before_tool_call=lambda _context: {
            "block": True,
            "needs_confirmation": True,
            "confirmation_payload": {"question": "Confirm publish?"},
        },
        tool_execution="sequential",
    )
    app.register_tool_source(StaticToolSource(
        "records",
        [ToolBinding(definition, execute)],
    ))
    try:
        result = app.runtime.run(TurnRequest(
            user_input="Publish record r-17",
            session_id="session-2",
            execution_mode="live",
        ))

        assert result.status.value == "awaiting_input", result.to_dict()
        assert result.needs_input is True
        assert result.reply == "Confirm publish?"
        assert executed == []
    finally:
        app.close()


def test_generic_policy_interaction_survives_run_result_without_executing_tool():
    executed = []

    class Model:
        def complete(self, _messages, _tools, _request):
            return ModelTurn(tool_calls=(ToolCall("call-1", "update_record", {}),))

    interaction = {
        "type": "input_form",
        "payload": {"fields": [{"name": "record_id"}]},
    }
    policy = ToolExecutionPolicy(
        interaction_builder=lambda _context, reason, _message: (
            interaction if reason == "input_schema" else None
        ),
    )
    app = AgentApplication.create(
        model=Model(),
        tool_policy=policy,
        tool_execution="sequential",
    )
    definition = _definition(
        "update_record",
        namespace="records",
        action="update",
        resource="record",
        description="Update a record",
        properties={"record_id": {"type": "string"}},
    )
    definition.input_schema.required = ["record_id"]

    app.register_tool_source(StaticToolSource(
        "records",
        [ToolBinding(definition, lambda *_args: executed.append(True))],
    ))
    try:
        result = app.runtime.run(TurnRequest(
            user_input="Update a record",
            session_id="interaction-session",
            user_id="user-1",
            tenant_id="tenant-1",
        ))

        payload = result.to_dict()
        assert result.status.value == "awaiting_input"
        assert result.needs_input is True
        assert payload["interactions"] == [interaction]
        assert payload["tool_results"][0]["interaction"] == interaction
        assert executed == []
    finally:
        app.close()


def test_large_interaction_is_not_truncated_by_model_tool_result_limit():
    executed = []
    interaction = {
        "type": "input_form",
        "payload": {
            "fields": [
                {"name": f"field_{index}", "description": "x" * 900}
                for index in range(80)
            ],
        },
    }

    class Model:
        def complete(self, _messages, _tools, _request):
            return ModelTurn(tool_calls=(ToolCall("call-1", "update_record", {}),))

    policy = ToolExecutionPolicy(
        interaction_builder=lambda _context, reason, _message: (
            interaction if reason == "input_schema" else None
        ),
    )
    app = AgentApplication.create(
        model=Model(),
        tool_policy=policy,
        tool_execution="sequential",
        max_tool_result_chars=240,
    )
    definition = _definition(
        "update_record",
        namespace="records",
        action="update",
        resource="record",
        description="Update a record",
        properties={"record_id": {"type": "string"}},
    )
    definition.input_schema.required = ["record_id"]
    app.register_tool_source(StaticToolSource(
        "records",
        [ToolBinding(definition, lambda *_args: executed.append(True))],
    ))
    try:
        result = app.runtime.run(TurnRequest(
            user_input="Update a record",
            session_id="large-interaction-session",
            user_id="user-1",
            tenant_id="tenant-1",
        ))

        payload = result.to_dict()
        assert len(str(interaction)) > 32_000
        assert result.status.value == "awaiting_input"
        assert payload["interactions"] == [interaction]
        assert payload["tool_results"][0]["interaction"] == interaction
        assert executed == []
    finally:
        app.close()


def test_oversized_interaction_is_rejected_without_returning_a_partial_form():
    interaction = {
        "type": "input_form",
        "payload": {
            "fields": [
                {"name": f"field_{index}", "description": "x" * 900}
                for index in range(8)
            ],
        },
    }

    class Model:
        def complete(self, _messages, _tools, _request):
            return ModelTurn(tool_calls=(ToolCall("call-1", "update_record", {}),))

    policy = ToolExecutionPolicy(
        interaction_builder=lambda _context, reason, _message: (
            interaction if reason == "input_schema" else None
        ),
    )
    app = AgentApplication.create(
        model=Model(),
        tool_policy=policy,
        tool_execution="sequential",
        max_interaction_chars=1024,
    )
    definition = _definition(
        "update_record",
        namespace="records",
        action="update",
        resource="record",
        description="Update a record",
        properties={"record_id": {"type": "string"}},
    )
    definition.input_schema.required = ["record_id"]
    app.register_tool_source(StaticToolSource(
        "records",
        [ToolBinding(definition, lambda *_args: None)],
    ))
    try:
        result = app.runtime.run(TurnRequest(
            user_input="Update a record",
            session_id="oversized-interaction-session",
            user_id="user-1",
            tenant_id="tenant-1",
        ))

        payload = result.to_dict()
        bounded = payload["tool_results"][0]["interaction"]
        assert result.status.value == "awaiting_input"
        assert bounded == {
            "type": "interaction_error",
            "error_code": "interaction_payload_too_large",
            "max_chars": 1024,
        }
        assert result.runtime_signals["interaction_payload_too_large"] is True
        assert "no partial interaction" in result.reply.lower()
    finally:
        app.close()


def test_generic_policy_enforces_nested_schema_constraints_before_execution():
    executed = []
    interactions = []

    class Model:
        def complete(self, _messages, _tools, _request):
            return ModelTurn(tool_calls=(ToolCall(
                "call-1",
                "create_package",
                {
                    "name": "draft",
                    "headlines": ["one"],
                    "settings": {"daily_budget": 0},
                },
            ),))

    definition = _definition(
        "create_package",
        namespace="packages",
        action="create",
        resource="package",
        description="Create a package",
        properties={
            "name": {"type": "string"},
            "headlines": {"type": "array", "minItems": 2},
            "settings": {
                "type": "object",
                "properties": {"daily_budget": {"type": "number", "minimum": 1}},
                "required": ["daily_budget"],
                "additionalProperties": False,
            },
        },
    )
    definition.input_schema.required = ["name", "headlines", "settings"]
    policy = ToolExecutionPolicy(
        interaction_builder=lambda _context, reason, message: (
            interactions.append((reason, message))
            or {"type": "input_form", "prompt": message}
            if reason == "input_schema" else None
        ),
    )
    app = AgentApplication.create(
        model=Model(),
        tool_policy=policy,
        tool_execution="sequential",
    )
    app.register_tool_source(StaticToolSource(
        "packages",
        [ToolBinding(definition, lambda *_args: executed.append(True))],
    ))
    try:
        result = app.runtime.run(TurnRequest(
            user_input="Create a package",
            session_id="schema-constraints-session",
            user_id="user-1",
            tenant_id="tenant-1",
        ))

        assert result.status.value == "awaiting_input"
        assert result.interactions[0]["type"] == "input_form"
        assert interactions and interactions[0][0] == "input_schema"
        assert executed == []
    finally:
        app.close()


def test_model_adapter_gets_redacted_context_while_tools_keep_credentials():
    seen_model_context = []
    seen_tool_credentials = []

    class Model:
        def complete(self, _messages, _tools, request):
            seen_model_context.append(dict(request.context))
            if len(seen_model_context) == 1:
                return ModelTurn(tool_calls=(ToolCall("call-1", "read_record", {}),))
            return ModelTurn(content="done")

    definition = _definition(
        "read_record",
        namespace="records",
        action="get",
        resource="record",
        description="Read a record",
    )

    def execute(context, _arguments):
        seen_tool_credentials.append(
            context.request.context["credentials"]["access_token"]
        )
        return {"success": True}

    app = AgentApplication.create(model=Model(), tool_execution="sequential")
    app.register_tool_source(StaticToolSource(
        "records", [ToolBinding(definition, execute)],
    ))
    try:
        result = app.runtime.run(TurnRequest(
            user_input="Read a record",
            session_id="model-context-redaction",
            context={"credentials": {"access_token": "secret-token"}},
        ))

        assert result.status.value == "succeeded"
        assert all("secret-token" not in repr(item) for item in seen_model_context)
        assert all(item["credentials"] == "<redacted>" for item in seen_model_context)
        assert seen_tool_credentials == ["secret-token"]
    finally:
        app.close()
