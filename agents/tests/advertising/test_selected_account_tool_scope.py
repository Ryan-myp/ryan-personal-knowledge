from types import SimpleNamespace

from agents.agent_harness import TurnRequest
from agents.agent_harness.core.namespace import normalize_namespace
from agents.agent_harness.core.tool_selection import ToolSelector
from agents.applications.advertising.composition.ad_application_assembly import AdApplicationAssembly
from agents.tools.advertising.providers.source_factory import create_tool_source


def _selection(
    account, text, scope, read_scopes=None, history=None,
    clarification_followup=False,
):
    tools = [
        binding.definition
        for namespace in ("google-ads", "meta", "tiktok")
        for binding in create_tool_source(namespace).list_bindings()
        if not binding.definition.is_write_tool
    ]
    runtime = SimpleNamespace(
        _canonical_platform=normalize_namespace,
        _validate_account_with_principal=lambda namespace, value, _write, allowed: (
            value in allowed.get(namespace, ()), "not authorized",
        ),
    )
    request = TurnRequest(
        user_input=text,
        principal=SimpleNamespace(account_scope=scope),
        context={
            "account_id": account,
            "_agent_read_account_scopes": read_scopes or {},
            "_agent_tool_selection_context": history or (
                "查询 campaign 123 的详情", "查询 campaign 123 的详情",
            ),
            "_agent_clarification_followup": clarification_followup,
        },
    )
    selected = AdApplicationAssembly._tool_selector(runtime, ToolSelector())(request, tools)
    return selected, request.context


def test_selected_authorized_account_keeps_channel_on_short_followups():
    selected, context = _selection(
        "google-test", "列出刚才这个 campaign 下的 ad group 列表",
        {"google-ads": {"google-test"}, "meta": {"meta-test"}, "tiktok": {"tiktok-test"}},
    )
    assert selected
    assert {tool.namespace for tool in selected} == {"google-ads"}
    assert context["_agent_tool_namespaces"] == ["google-ads"]


def test_explicit_channel_switch_is_not_overridden_by_selected_account():
    selected, _context = _selection(
        "google-test", "列出 Meta campaign 列表",
        {"google-ads": {"google-test"}, "meta": {"meta-test"}},
    )
    assert selected
    assert {tool.namespace for tool in selected} == {"meta"}


def test_unauthorized_or_ambiguous_account_does_not_invent_channel_authority():
    for account, scope in (
        ("unconfirmed", {"google-ads": {"google-test"}, "meta": {"meta-test"}}),
        ("shared", {"google-ads": {"shared"}, "meta": {"shared"}}),
    ):
        selected, context = _selection(account, "查询 campaign 列表", scope)
        assert selected
        assert len(context["_agent_tool_namespaces"]) > 1


def test_broad_knowledge_candidates_cannot_bypass_initial_schema_budget():
    selected, _ = _selection(
        None, "讲解程序化广告中 SSP 和 DSP 的区别，不需要账户数据。",
        {"google-ads": {"g"}, "meta": {"m"}, "tiktok": {"t"}},
    )
    assert len(selected) <= 8


def test_successful_read_scope_keeps_channel_when_http_account_was_never_selected():
    selected, context = _selection(
        None, "列出广告组 123 下的 ad 列表",
        {"google-ads": {"google-test"}, "meta": {"meta-test"}, "tiktok": {"tiktok-test"}},
        read_scopes={"tiktok": "tiktok-test"},
    )
    assert selected
    assert {tool.namespace for tool in selected} == {"tiktok"}
    assert "tiktok_list_ads" in {tool.name for tool in selected}
    assert context["_agent_tool_namespaces"] == ["tiktok"]


def test_campaign_filter_followup_reuses_verified_google_read_scope():
    selected, context = _selection(
        None,
        "那我们根据状态过滤一下，不要 REMOVED 的",
        {"google-ads": {"google-test"}, "meta": {"meta-test"}},
        read_scopes={"google-ads": "google-test"},
        history=(
            "查询 Google Ads 报表，account 是 google-test",
            "查询一下campaign信息",
        ),
    )
    assert [tool.name for tool in selected] == ["google_list_campaigns"]
    assert context["_agent_tool_namespaces"] == ["google-ads"]
    assert context["_agent_tool_choice_required"] is True


def test_status_check_followup_reuses_verified_google_read_scope():
    selected, context = _selection(
        None,
        "现在可以了吗",
        {"google-ads": {"google-test"}, "meta": {"meta-test"}},
        read_scopes={"google-ads": "google-test"},
        history=(
            "查询 Google Ads campaign 列表",
            "按 status != REMOVED 过滤后重新查询",
        ),
    )

    assert [tool.name for tool in selected] == ["google_list_campaigns"]
    assert context["_agent_tool_namespaces"] == ["google-ads"]
    assert context["_agent_tool_choice_required"] is True


def test_clarification_topic_takes_precedence_over_remembered_account_provider():
    selected, context = _selection(
        "meta-test",
        "Sales/PURCHASE + 搜索 Ad Group",
        {"google-ads": {"google-test"}, "meta": {"meta-test"},
         "tiktok": {"tiktok-test"}},
        history=(
            "讲下 TikTok 怎么广告支持 search keyword",
            "Campaign、Ad Group、Ad 的 API 字段逐项讲解",
        ),
        clarification_followup=True,
    )

    assert selected
    assert {tool.namespace for tool in selected} == {"tiktok"}
    assert context["_agent_tool_namespaces"] == ["tiktok"]


def test_meta_child_detail_followup_keeps_account_scope_and_requires_fresh_reads():
    selected, context = _selection(
        None,
        "下层级详细信息呢？",
        {"google-ads": {"google-test"}, "meta": {"meta-test"}},
        read_scopes={"meta": "meta-test"},
        history=(
            "查询一下meta 的campaign 列表",
            "查询这个campaign ：120251918088900251",
        ),
    )
    assert {"meta_get_adset", "meta_get_ad"} <= {tool.name for tool in selected}
    assert {tool.namespace for tool in selected} == {"meta"}
    assert context["_agent_tool_choice_required"] is True


def test_child_detail_followup_does_not_override_current_account_with_stale_channel():
    selected, _context = _selection(
        None, "下层级详细信息呢？",
        {"meta": {"meta-test"}, "tiktok": {"tiktok-test"}},
        read_scopes={"meta": "meta-test"},
        history=("查询 TikTok campaign 1879821177383105",),
    )
    assert selected == []


def test_explicit_channel_switch_overrides_remembered_read_scope():
    selected, _ = _selection(
        None, "查询 Google campaign 列表",
        {"google-ads": {"google-test"}, "tiktok": {"tiktok-test"}},
        read_scopes={"tiktok": "tiktok-test"},
    )
    assert {tool.namespace for tool in selected} == {"google-ads"}


def test_explicit_multi_account_query_overrides_stale_single_channel_history():
    selected, context = _selection(
        None,
        "用这几个账号测试一下 campaign、ad group、ad 的查询",
        {
            "google-ads": {"google-test"},
            "meta": {"meta-test"},
            "tiktok": {"tiktok-test"},
        },
        history=(
            "在讲下 Meta 广告吧",
            "现在的测试账号是有哪几个",
            "咱们不是内置了几个账号吗",
        ),
    )

    assert {tool.namespace for tool in selected} == {
        "google-ads", "meta", "tiktok",
    }
    names = {tool.name for tool in selected}
    assert {
        "google_list_campaigns",
        "google_list_ad_groups",
        "google_list_ads",
        "meta_list_campaigns",
        "meta_list_ad_sets",
        "meta_list_ads",
        "tiktok_list_campaigns",
        "tiktok_list_adgroups",
        "tiktok_list_ads",
    } <= names
    assert context["_agent_tool_namespaces"] == [
        "google-ads", "meta", "tiktok",
    ]


def test_multi_account_query_never_expands_beyond_principal_scope():
    selected, _context = _selection(
        None,
        "用这几个账号查询 campaign 列表",
        {
            "meta": {"meta-test"},
            "tiktok": {"tiktok-test"},
        },
        history=("在讲下 Meta 广告吧",),
    )

    assert {tool.namespace for tool in selected} == {"meta", "tiktok"}


def test_pronoun_followup_reuses_multi_channel_scope_and_ad_set_aliases():
    selected, context = _selection(
        None,
        "测试一下他们对campaign、ad set、ad 的查询",
        {
            "google-ads": {"google-test"},
            "meta": {"meta-test"},
            "tiktok": {"tiktok-test"},
        },
        history=("现在有几个内容的账户呀",),
    )

    assert set(context["_agent_tool_namespaces"]) == {
        "google-ads", "meta", "tiktok",
    }
    names = {tool.name for tool in selected}
    assert {
        "google_list_campaigns",
        "google_list_ad_groups",
        "google_list_ads",
        "meta_list_campaigns",
        "meta_list_ad_sets",
        "meta_list_ads",
        "tiktok_list_campaigns",
        "tiktok_list_adgroups",
        "tiktok_list_ads",
    } <= names
