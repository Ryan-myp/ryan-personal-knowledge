import pytest

from agents.agent_harness import ModelTurn, ToolCall, TurnRequest
from agents.agent_harness.core.interfaces import ToolContext
from agents.agent_harness.core.tool_registry import validate_tool_input
from agents.agent_harness.core.tool_selection import ToolSelector
from agents.agent_platform.governance.identity.principal import RequestPrincipal
from agents.applications.advertising.composition.ad_application import AdvertisingComposition
from agents.applications.advertising.composition.ad_application_assembly import AdApplicationAssembly
from agents.applications.advertising.persistence.store import AdAgentStore
from agents.applications.advertising.execution.ad_tool_policy_factory import AdvertisingToolPolicyFactory
from agents.tools.advertising.providers.google import create_google_tool_source
from agents.tools.advertising.providers.meta import create_meta_tool_source


ACCOUNT = "9055507554"
LIST = "google_ads_list_creation_templates"
GET = "google_ads_get_creation_template"


@pytest.fixture
def runtime():
    owner = AdvertisingComposition(
        require_llm=False, offline_mode=True, persistence_store=AdAgentStore(":memory:"),
        start_background_workers=False,
    )
    owner.whitelist_validator.allowed_accounts = {
        "google-ads": [ACCOUNT], "meta": ["2806375919473667"],
    }
    owner.register_tool_source(create_google_tool_source())
    owner.register_tool_source(create_meta_tool_source())
    yield owner
    owner.close(wait=True)


def context(*, user="operator", tenant="tenant", scope=None):
    return ToolContext(
        "template-discovery", user, account_id=ACCOUNT,
        metadata={
            "tenant_id": tenant,
            "account_scope": {"google-ads": {ACCOUNT}} if scope is None else scope,
        },
    )


def execute(runtime, name, arguments, ctx=None):
    definition, _ = runtime.registry.get(name)
    assert validate_tool_input(definition.input_schema, arguments) == []
    return runtime.tool_executor.execute(ctx or context(), name, arguments)


def shopping_template(runtime):
    result = execute(runtime, LIST, {"query": "Shopping"})
    assert result.success, result.error
    return next(row for row in result.data["templates"] if row["catalog_key"] == "google.test.shopping")


def test_template_discovery_tools_are_registered_read_only_local_contracts(runtime):
    definition, _ = runtime.registry.get(LIST)
    assert definition.is_read_tool
    assert definition.scope_required is False
    assert definition.required_permissions == ["ads.read"]
    assert definition.input_schema.additional_properties is False
    assert validate_tool_input(definition.input_schema, {"user_id": "other-user"})
    assert validate_tool_input(definition.input_schema, {"limit": 101})
    assert definition.max_output_bytes <= 128_000
    assert runtime.plugin_registry.get("creation-templates:google-ads") is not None


def test_natural_template_followup_exposes_template_tools_in_the_active_channel(runtime):
    request = TurnRequest(
        user_input="有模板吗",
        session_id="template-discovery",
        principal=RequestPrincipal(
            user_id="operator", tenant_id="tenant",
            permissions=frozenset({"ads.read"}),
            account_scope={"google-ads": {ACCOUNT}},
        ),
        context={
            "account_id": ACCOUNT,
            "_agent_tool_selection_context": ["创建 Google 广告系列", "想投放购物广告，预算20"],
        },
    )
    selected = AdApplicationAssembly._tool_selector(runtime, ToolSelector())(
        request, runtime.registry.list_all(),
    )
    assert LIST in {tool.name for tool in selected}
    assert "meta_list_creation_templates" not in {tool.name for tool in selected}


def test_list_templates_finds_account_presets_without_provider_calls(runtime):
    result = execute(runtime, LIST, {})
    assert result.success
    assert result.data["data_status"] == "local"
    assert {row["catalog_key"] for row in result.data["templates"]} >= {
        "google.test.app", "google.test.shopping", "google.test.performance-max",
    }
    template = shopping_template(runtime)
    assert "campaign.shopping_setting.merchant_id" in template["prefilled_fields"]
    assert template["required_input_fields"] == [
        "campaign.campaign_name", "campaign.start_date", "campaign.end_date", "campaign.daily_budget",
    ]


def test_local_template_lookup_never_crosses_account_scope(runtime):
    result = execute(
        runtime, LIST, {}, context(scope={"google-ads": set()}),
    )
    assert result.success
    assert result.data["templates"] == []
    template = shopping_template(runtime)
    denied = execute(
        runtime, GET, {"template_id": template["template_id"]},
        context(scope={"google-ads": set()}),
    )
    assert not denied.success
    assert "merchant" not in str(denied.data).lower()


def test_get_template_builds_a_prefilled_draft_without_creating_ads(runtime):
    template = shopping_template(runtime)
    values = {
        "campaign.campaign_name": "ai-test1",
        "campaign.start_date": "2026-10-18",
        "campaign.end_date": "2026-10-20",
        "campaign.daily_budget": 20,
    }
    result = execute(runtime, GET, {"template_id": template["template_id"], "values": values})
    assert result.success, result.error
    assert result.data["template"]["values"]["campaign.shopping_setting.merchant_id"] == 115791065
    assert result.interaction["type"] == "ad_creation_form"
    card = result.interaction["payload"]
    assert card["template_id"] == template["template_id"]
    fields = {field["path"]: field for field in card["fields"]}
    for path, value in values.items():
        assert fields[path]["value"] == value
    assert fields["campaign.shopping_setting.merchant_id"]["value"] == 115791065
    assert fields["campaign.shopping_setting.merchant_id"]["user_required"] is False
    assert result.data["external_effects"] is False


@pytest.mark.parametrize("values", [
    {"unknown.path": 20},
    {"campaign.access_token": "must-not-be-used"},
    {"campaign.campaign_name": {"scripts": "must-not-run"}},
])
def test_template_preview_rejects_unowned_or_unsafe_overrides(runtime, values):
    template = shopping_template(runtime)
    result = execute(runtime, GET, {"template_id": template["template_id"], "values": values})
    assert not result.success
    assert result.interaction is None


def test_private_template_queries_are_user_and_tenant_isolated(runtime):
    manager = runtime._creation_template_manager_for_request({"google-ads": {ACCOUNT}})
    preset = shopping_template(runtime)
    copied = manager.duplicate("tenant", "operator", preset["template_id"], "private-preset")
    own = execute(runtime, LIST, {"query": "private-preset"})
    assert [row["template_id"] for row in own.data["templates"]] == [copied["template_id"]]
    for ctx in (context(user="other-user"), context(tenant="other-tenant")):
        result = execute(runtime, LIST, {"query": "private-preset"}, ctx)
        assert result.data["templates"] == []
        assert not execute(runtime, GET, {"template_id": copied["template_id"]}, ctx).success


def test_duplicate_provider_registration_keeps_the_existing_template_plugin(runtime):
    plugin = runtime.plugin_registry.get("creation-templates:google-ads")
    with pytest.raises(ValueError):
        runtime.register_tool_source(create_google_tool_source())
    assert runtime.plugin_registry.get("creation-templates:google-ads") is plugin
    assert runtime.registry.get(LIST)[0].name == LIST


def test_unloading_the_provider_removes_its_template_tools_and_plugin(runtime):
    assert runtime.unload_skill("google-ads")
    with pytest.raises(KeyError):
        runtime.registry.get(LIST)
    with pytest.raises(KeyError):
        runtime.plugin_registry.get("creation-templates:google-ads")


@pytest.mark.parametrize("name", [LIST, "google_list_campaigns"])
def test_server_defaults_cannot_grant_permissions_missing_from_a_principal(runtime, name):
    definition, _ = runtime.registry.get(name)
    request = TurnRequest(
        user_input="查询", principal=RequestPrincipal(
            user_id="operator", tenant_id="tenant", permissions=frozenset(),
            account_scope={"google-ads": {ACCOUNT}},
        ), context={"account_id": ACCOUNT},
    )
    error = AdvertisingToolPolicyFactory(runtime).check_scope_and_confirmation(
        definition, request, {},
    )
    assert error is not None and error[0] == "permission_denied"


@pytest.mark.parametrize("permissions", [frozenset({"ads.read"}), frozenset()])
def test_template_query_uses_trusted_principal_scope_through_the_real_run(runtime, permissions):
    class Model:
        def complete(self, messages, tools, request):
            previous = [message for message in messages if message.role == "tool"]
            if not previous:
                return ModelTurn(tool_calls=[ToolCall(
                    id="template-list", name=LIST, arguments={},
                )])
            return ModelTurn(content="当前账号有 Shopping、App 和 PMax 模板。")

    runtime._llm = Model()
    runtime.platform_application.agent.model = runtime._llm
    result = runtime.run(
        "Google 有模板吗", session_id="trusted-template-query",
        account_id=ACCOUNT, principal=RequestPrincipal(
            user_id="operator", tenant_id="tenant",
            permissions=permissions,
            account_scope={"google-ads": {ACCOUNT}},
        ),
    )
    if permissions:
        assert result["status"] == "succeeded"
        assert result["results"][0]["tool"] == LIST
        assert result["results"][0]["success"] is True
        assert result["results"][0]["data"]["templates"]
    else:
        assert not any(
            row.get("success") and row.get("data", {}).get("templates")
            for row in result["results"]
        )
        assert any("permission" in str(row.get("content", "")).lower() for row in result["tool_results"])
