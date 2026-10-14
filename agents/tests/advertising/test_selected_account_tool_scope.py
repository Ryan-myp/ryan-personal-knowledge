from types import SimpleNamespace

from agents.agent_harness import TurnRequest
from agents.agent_harness.core.namespace import normalize_namespace
from agents.agent_harness.core.tool_selection import ToolSelector
from agents.applications.advertising.composition.ad_application_assembly import AdApplicationAssembly
from agents.tools.advertising.providers.source_factory import create_tool_source


def _selection(account, text, scope, read_scopes=None):
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
            "_agent_tool_selection_context": (
                "查询 campaign 123 的详情", "查询 campaign 123 的详情",
            ),
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


def test_explicit_channel_switch_overrides_remembered_read_scope():
    selected, _ = _selection(
        None, "查询 Google campaign 列表",
        {"google-ads": {"google-test"}, "tiktok": {"tiktok-test"}},
        read_scopes={"tiktok": "tiktok-test"},
    )
    assert {tool.namespace for tool in selected} == {"google-ads"}
