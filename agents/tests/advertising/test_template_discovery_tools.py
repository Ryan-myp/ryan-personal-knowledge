import json

import pytest

from agents.agent_harness import AgentMessage, ModelTurn, ToolCall, TurnRequest
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
from agents.tools.advertising.providers.tiktok import create_tiktok_tool_source


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


@pytest.mark.parametrize("provider", ["google-ads", "meta", "tiktok"])
def test_explicit_template_catalog_query_does_not_send_creation_schemas(runtime, provider):
    if provider == "tiktok":
        runtime.register_tool_source(create_tiktok_tool_source())
    request = TurnRequest(
        f"创建 {provider} 广告系列，先列出内置模板让我选择，不要提交创建。",
        execution_mode="live",
    )
    selected = AdApplicationAssembly._tool_selector(runtime, ToolSelector())(
        request, runtime.registry.list_all(),
    )
    assert selected
    catalogs = [tool for tool in selected if "clarification" not in tool.traits]
    assert all(
        tool.namespace == provider and tool.resource_type == "creation_template"
        for tool in catalogs
    )
    assert catalogs and len(selected) <= 3
    assert all(tool.is_read_tool for tool in selected)


def test_template_catalog_model_request_stays_within_small_schema_budget(runtime):
    from agents.agent_harness.model_limits import model_input_chars

    measurements = []

    class Model:
        def complete(self, messages, tools, request):
            measurements.append({
                "schema_chars": model_input_chars([], tools),
                "input_chars": model_input_chars(messages, tools),
                "tool_count": len(tools),
            })
            if not any(
                message.role == "tool" and message.turn_id == request.turn_id
                for message in messages
            ):
                return ModelTurn(tool_calls=[ToolCall("list", LIST, {"account_id": ACCOUNT})])
            return ModelTurn(content="已返回本地广告模板，请选择。")

    runtime.platform_application.agent.model = Model()
    result = runtime.run(
        "创建 Google Ads 广告，先列出内置模板让我选择，不要提交创建。",
        session_id="bounded-template-context", account_id=ACCOUNT,
    )
    assert result["status"] == "succeeded"
    assert measurements[0]["tool_count"] <= 3
    assert measurements[0]["schema_chars"] < 6000
    assert measurements[0]["input_chars"] < 50000
    assert result["knowledge_context"]["documents"] == []


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


def test_missing_template_inputs_select_preview_before_creating(runtime):
    template = shopping_template(runtime)
    request = TurnRequest(
        "Campaign 名称：demo，开始时间2026-10-24，结束时间2026-10-25，日预算50",
        execution_mode="live",
        principal=RequestPrincipal(
            user_id="operator", tenant_id="tenant",
            permissions=frozenset({"ads.read", "ads.write"}),
            account_scope={"google-ads": {ACCOUNT}},
        ),
        context={
            "account_id": ACCOUNT,
            "creation_blueprint_id": template["blueprint_id"],
            "creation_blueprint_version": template["blueprint_version"],
            "creation_template_id": template["template_id"],
            "platform_params": {"google-ads": {}},
        },
    )
    selected = AdApplicationAssembly._tool_selector(runtime, ToolSelector())(
        request, runtime.registry.list_all(),
    )
    assert [tool.name for tool in selected] == [GET]
    assert request.context["_agent_template_input_fields"] == template["required_input_fields"]


def test_template_edit_preserves_previous_form_values(runtime):
    template = shopping_template(runtime)
    ctx = context()
    ctx.metadata["creation_request"] = {
        "creation_template_id": template["template_id"],
        "platform_params": {"google-ads": {
            "google_create_campaign": {
                "campaign_name": "earlier-name",
                "start_date": "2026-10-24",
                "end_date": "2026-10-25",
                "daily_budget": 20,
            },
        }},
    }
    result = execute(runtime, GET, {
        "template_id": template["template_id"],
        "values": {"campaign.campaign_name": "new-name", "campaign.daily_budget": 50},
    }, ctx)
    assert result.success, result.error
    fields = {field["path"]: field for field in result.interaction["payload"]["fields"]}
    assert fields["campaign.campaign_name"]["value"] == "new-name"
    assert fields["campaign.daily_budget"]["value"] == 50
    assert fields["campaign.start_date"]["value"] == "2026-10-24"
    assert fields["campaign.end_date"]["value"] == "2026-10-25"
    assert fields["campaign.shopping_setting.merchant_id"]["value"] == 115791065


def test_ready_template_inputs_select_only_approved_blueprint_writes(runtime):
    template = shopping_template(runtime)
    runtime._live_approved_tools = {"google_create_campaign"}
    request = TurnRequest(
        "提交创建计划",
        execution_mode="live",
        principal=RequestPrincipal(
            user_id="operator", tenant_id="tenant",
            permissions=frozenset({"ads.read", "ads.write"}),
            account_scope={"google-ads": {ACCOUNT}},
        ),
        context={
            "account_id": ACCOUNT,
            "creation_blueprint_id": template["blueprint_id"],
            "creation_blueprint_version": template["blueprint_version"],
            "creation_template_id": template["template_id"],
            "platform_params": {"google-ads": {"google_create_campaign": {
                "campaign_name": "demo", "start_date": "2026-10-24",
                "end_date": "2026-10-25", "daily_budget": 50,
            }}},
        },
    )
    selected = AdApplicationAssembly._tool_selector(runtime, ToolSelector())(
        request, runtime.registry.list_all(),
    )
    names = {tool.name for tool in selected}
    assert "google_create_campaign" in names
    assert GET not in names
    assert all(
        not tool.is_write_tool or tool.name in runtime._live_approved_tools
        for tool in selected
    )


@pytest.mark.parametrize("provider,account,query,overrides", [
    ("google-ads", ACCOUNT, "Shopping", {
        "campaign.campaign_name": "dialog-shopping",
        "campaign.start_date": "2026-10-24", "campaign.end_date": "2026-10-25",
        "campaign.daily_budget": 50,
    }),
    ("meta", "2806375919473667", "流量", {
        "campaign.name": "dialog-meta",
        "ad_set.start_time": "2026-10-24T00:00:00+00:00",
        "ad_set.end_time": "2026-10-25T00:00:00+00:00",
        "campaign.daily_budget": 5000,
    }),
    ("tiktok", "7397068114548195329", "商品目录销售", {
        "campaign.campaign_name": "dialog-sales",
        "ad_group.schedule_start_time": "2026-10-24T00:00:00+00:00",
        "ad_group.schedule_end_time": "2026-10-25T00:00:00+00:00",
        "ad_group.budget": 50,
    }),
])
def test_dialog_selection_loads_template_card_then_merges_freeform_inputs(
    runtime, provider, account, query, overrides,
):
    if provider == "tiktok":
        runtime.register_tool_source(create_tiktok_tool_source())
        runtime.whitelist_validator.allowed_accounts[provider] = [account]
    prefix = provider.replace("-", "_")
    list_name = f"{prefix}_list_creation_templates"
    get_name = f"{prefix}_get_creation_template"
    principal = RequestPrincipal(
        user_id="operator", tenant_id="tenant",
        permissions=frozenset({"ads.read", "ads.write"}),
        account_scope={provider: {account}},
    )
    state = {"phase": 0, "calls": 0, "template": None, "choice": ""}

    class Model:
        def complete(self, messages, tools, request):
            names = {tool.name for tool in tools}
            state["calls"] += 1
            if state["phase"] == 0:
                prior = [
                    message for message in messages
                    if message.role == "tool" and message.turn_id == request.turn_id
                ]
                if not prior:
                    return ModelTurn(tool_calls=[ToolCall(
                        "list", list_name, {"account_id": account, "query": query},
                    )])
                result = prior[-1].content
                if isinstance(result, str):
                    result = json.loads(result)
                template = result["data"]["templates"][0]
                state["template"] = template
                state["choice"] = template["name"] + "（仅需补充名称、日期、预算）"
                return ModelTurn(tool_calls=[ToolCall(
                    "choice", "agent_request_input",
                    {"question": "请选择模板", "choices": [state["choice"]]},
                )])
            assert names == {get_name}
            assert request.initial_tool_choice == "required"
            return ModelTurn(tool_calls=[ToolCall(
                "preview", get_name, {
                    "template_id": state["template"]["template_id"],
                    "account_id": account,
                    "values": overrides if state["phase"] == 2 else {},
                },
            )])

    runtime.platform_application.agent.model = Model()
    base = {
        "session_id": f"dialog-template-{provider}",
        "account_id": account, "principal": principal, "execution_mode": "live",
    }
    first = runtime.run(f"创建 {provider} 广告系列，查询{query}模板", **base)
    assert first["status"] == "awaiting_input", first["reply"]
    state["phase"] = 1
    selected = runtime.run(state["choice"], **base)
    assert selected["status"] == "awaiting_input", selected["reply"]
    card = selected["ui"]["cards"][0]
    assert card["template_id"] == state["template"]["template_id"]
    assert any(field.get("value") for field in card["fields"])
    scoped = {}
    for field in card["fields"]:
        if field.get("tool") and field.get("value") not in (None, ""):
            runtime._set_creation_path(
                scoped.setdefault(field["tool"], {}),
                field["provider_field"], field["value"],
            )
    state["phase"] = 2
    edited = runtime.run(
        "名称、日期和预算按我这次补充的参数填写", **base,
        creation_template_id=card["template_id"],
        creation_blueprint_id=card["blueprint_id"],
        creation_blueprint_version=card["blueprint_version"],
        platform_params={provider: scoped},
    )
    assert edited["status"] == "awaiting_input", edited["reply"]
    updated = {field["path"]: field for field in edited["ui"]["cards"][0]["fields"]}
    for path, value in overrides.items():
        assert updated[path]["value"] == value
    assert not any(row.get("action") == "create" for row in edited["results"])


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


def test_template_confirmation_choice_routes_to_blueprint_writes_not_template_preview():
    account_id = "7397068114548195329"
    owner = AdvertisingComposition(
        require_llm=False,
        offline_mode=True,
        persistence_store=AdAgentStore(":memory:"),
        start_background_workers=False,
    )
    try:
        owner.register_tool_source(create_tiktok_tool_source())
        owner._live_approved_tools = {
            "tiktok_smart_plus_create_campaign",
            "tiktok_smart_plus_create_adgroup",
            "tiktok_smart_plus_create_ad",
        }
        options = [
            "确认按上述 4 项创建",
            "我要修改",
            "先不创建",
        ]
        transcript = [
            AgentMessage.user("创建吧", turn_id="confirmation-prompt"),
            AgentMessage.tool(
                json.dumps({
                    "success": True,
                    "data": {"choices": options},
                    "needs_input": True,
                    "interaction": {
                        "type": "action_clarification",
                        "payload": {
                            "options": [
                                {"label": option, "value": option}
                                for option in options
                            ],
                        },
                    },
                }),
                tool_call_id="confirmation-choice",
                name="agent_request_input",
                turn_id="confirmation-prompt",
            ),
        ]
        request = TurnRequest(
            user_input=options[0],
            session_id="template-confirmation-routing",
            turn_id="confirmation-answer",
            user_id="operator",
            principal=RequestPrincipal(
                user_id="operator",
                tenant_id="tenant",
                permissions=frozenset({"ads.read", "ads.write"}),
                account_scope={"tiktok": {account_id}},
            ),
            context={
                "account_id": account_id,
                "creation_blueprint_id": "tiktok.product_sales_video",
                "creation_blueprint_version": "2.3.0",
                "creation_template_id": "builtin_f24270752ed0b43298ac45d8",
                "platform_params": {"tiktok": {
                    "campaign_name": "test",
                    "tiktok_smart_plus_create_adgroup": {
                        "schedule_start_time": "2026-10-24T00:00:00+00:00",
                        "schedule_end_time": "2026-10-25T00:00:00+00:00",
                        "budget": 50,
                    },
                }},
            },
            execution_mode="live",
            initial_tool_choice="required",
        )

        agent = owner.platform_application.agent
        tools, _required = agent._tools_for_turn(request, transcript)
        selected_names = {tool.name for tool in tools}

        assert {
            "tiktok_smart_plus_create_campaign",
            "tiktok_smart_plus_create_adgroup",
            "tiktok_smart_plus_create_ad",
        } <= selected_names
        assert "tiktok_get_creation_template" not in selected_names
        selection_request, catalog_target = agent._tool_selection_request(
            request,
            transcript,
            agent.tool_catalog.list_tools(),
        )
        assert selection_request.user_input == "创建吧\n确认按上述 4 项创建"
        assert catalog_target == ""
        assert request.initial_tool_choice == "required"
    finally:
        owner.close(wait=True)
