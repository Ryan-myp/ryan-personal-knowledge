from types import SimpleNamespace

import pytest

from agents.tools.advertising.clients.base import APIError
from agents.tools.advertising.clients.tiktok_client import TikTokAPIClient
from agents.agent_harness.core.tool_registry import validate_tool_input
from agents.applications.advertising.composition.ad_application import AdvertisingComposition
from agents.tools.advertising.providers.tiktok import create_tiktok_tool_source
from scripts.advertising.campaign_service_e2e import ProviderRecorder


ACCOUNT = "7397068114548195329"
PORTFOLIO = "7696698198538112006"
CTA_CONTENT = [{"asset_content": "Learn more", "asset_ids": ["201781", "201535"]}]


@pytest.fixture
def cta_runtime():
    runtime = AdvertisingComposition(
        require_llm=False, offline_mode=True, start_background_workers=False,
    )
    yield runtime
    runtime.close(wait=True)


def definitions():
    return {
        binding.definition.name: binding.definition
        for binding in create_tiktok_tool_source().list_bindings()
    }


def test_cta_asset_creation_is_dry_run_by_default():
    client = TikTokAPIClient({"access_token": "test"})
    client.request = lambda *_args, **_kwargs: pytest.fail("Dry run must not call provider")
    plan = client.create_creative_portfolio(
        "7397068114548195329", "CTA",
        CTA_CONTENT,
    )
    assert plan["mode"] == "dry_run"


@pytest.mark.parametrize("content", [
    [{}],
    [{"call_to_action": "LEARN_MORE"}],
    [{"asset_content": "Learn more"}],
    [{"asset_ids": ["201781"]}],
    [{"asset_content": "", "asset_ids": ["201781"]}],
    [{"asset_content": "Learn more", "asset_ids": []}],
    [{"asset_content": "Learn more", "asset_ids": [""]}],
    [{"asset_content": "Learn more", "asset_ids": [201781]}],
    [{"asset_content": "Learn more", "asset_ids": "201781"}],
    [{"asset_content": "Learn more", "asset_ids": ["201781"], "extra": True}],
])
@pytest.mark.parametrize("live", [False, True])
def test_invalid_cta_content_is_rejected_before_provider_call(content, live):
    client = TikTokAPIClient({"access_token": "test"})
    client.request = lambda *_a, **_kw: pytest.fail("Invalid CTA must not reach provider")
    assert validate_tool_input(
        definitions()["tiktok_create_creative_portfolio"].input_schema,
        {"account_id": ACCOUNT, "creative_portfolio_type": "CTA", "portfolio_content": content},
    )
    with pytest.raises(ValueError, match="CTA"):
        client.create_creative_portfolio(ACCOUNT, "CTA", content, live=live)


def test_recommended_cta_content_passes_the_closed_schema_and_live_transport():
    assert validate_tool_input(
        definitions()["tiktok_create_creative_portfolio"].input_schema,
        {"account_id": ACCOUNT, "creative_portfolio_type": "CTA", "portfolio_content": CTA_CONTENT},
    ) == []
    client = TikTokAPIClient({"access_token": "test"})
    calls = []
    client.request = lambda method, path, **kwargs: (
        calls.append((method, path, kwargs)) or {"creative_portfolio_id": PORTFOLIO}
    )
    result = client.create_creative_portfolio(ACCOUNT, "CTA", CTA_CONTENT, live=True)
    assert result["creative_portfolio_id"] == PORTFOLIO
    assert calls == [("POST", "creative/portfolio/create/", {"data": {
        "advertiser_id": ACCOUNT, "creative_portfolio_type": "CTA",
        "portfolio_content": CTA_CONTENT,
    }})]


def test_test_transport_rejects_cta_portfolio_writes_outside_campaign_scope(tmp_path):
    recorder = ProviderRecorder(tmp_path)
    recorder.case = {"provider": "tiktok", "account": "7397068114548195329"}
    request = SimpleNamespace(
        method="POST", url="https://business-api.tiktok.com/open_api/v1.3/creative/portfolio/create/",
    )
    with pytest.raises(PermissionError, match="outside campaign hierarchy"):
        recorder._guard(request, "tiktok", {
            "advertiser_id": "7397068114548195329", "creative_portfolio_type": "CTA",
        })
    with pytest.raises(PermissionError, match="outside campaign hierarchy"):
        recorder._guard(request, "tiktok", {
            "advertiser_id": "7397068114548195329", "creative_portfolio_type": "CARD",
        })


def test_cta_portfolio_readback_uses_get_query_parameters():
    client = TikTokAPIClient({"access_token": "test"})
    calls = []
    client.request = lambda method, path, **kwargs: (
        calls.append((method, path, kwargs)) or {"creative_portfolio_id": "123"}
    )
    client.get_creative_portfolio("7397068114548195329", "123")
    assert calls[0][0] == "GET"
    assert calls[0][2]["params"]["creative_portfolio_id"] == "123"


def test_cta_recommendations_keep_real_asset_ids_and_content_together():
    client = TikTokAPIClient({"access_token": "test"})
    calls = []
    client.request = lambda method, path, **kwargs: (
        calls.append((method, path, kwargs)) or {"data": {"recommend_assets": [
            {"asset_ids": ["201404"], "asset_content": "Learn More"},
        ]}}
    )
    assert client.recommend_ctas("7397068114548195329", "LANDING_PAGE") == [
        {"asset_ids": ["201404"], "asset_content": "Learn More"},
    ]
    assert calls[0][0] == "GET"
    assert calls[0][2]["params"]["asset_type"] == "CTA_AUTO_OPTIMIZED"
    assert calls[0][2]["params"]["content_type"] == "LANDING_PAGE"


@pytest.mark.parametrize("method", ["recommend_ctas", "list_creative_portfolios"])
@pytest.mark.parametrize("limit", [0, 101, True])
def test_cta_queries_reject_invalid_bounds_before_network(method, limit):
    client = TikTokAPIClient({"access_token": "test"})
    client.request = lambda *_a, **_kw: pytest.fail("Invalid query must not reach provider")
    client.request_raw = client.request
    with pytest.raises(ValueError, match="limit"):
        getattr(client, method)(ACCOUNT, limit=limit)


@pytest.mark.parametrize("payload", [{}, {"recommend_assets": {}}, {"recommend_assets": None}])
def test_cta_recommendations_fail_on_a_missing_or_malformed_collection(payload):
    client = TikTokAPIClient({"access_token": "test"})
    client.request = lambda *_a, **_kw: {"data": payload}
    with pytest.raises(APIError, match="recommend_assets"):
        client.recommend_ctas(ACCOUNT)


def test_traffic_template_records_verified_flow_without_marking_sales_verified():
    from agents.applications.advertising.creation.templates import load_builtin_template_definitions

    templates = {row["key"]: row for row in load_builtin_template_definitions()}
    assert templates["tiktok.test.traffic"]["verification_status"] == "live_verified"
    assert templates["tiktok.test.sales"]["verification_status"] == "provider_limited"


def test_smart_plus_update_schema_does_not_mutate_the_create_schema():
    from agents.tools.advertising.providers.tiktok.parameters import tiktok_smart_plus_ad_schema
    from agents.tools.advertising.providers.update_contracts import tiktok_smart_plus_updates

    create_schema = tiktok_smart_plus_ad_schema()
    update_schema = tiktok_smart_plus_updates("ad", ad_schema=create_schema)
    update_cta = update_schema["properties"]["ad_configuration"]["properties"]["call_to_action_id"]
    create_cta = create_schema["properties"]["ad_configuration"]["properties"]["call_to_action_id"]
    assert update_cta is not create_cta
    update_cta["manual_entry"] = {"title": "Update only"}
    assert "manual_entry" not in create_cta


def test_reused_campaign_reference_is_resolved_before_the_latest_page_limit():
    from agents.tools.advertising.providers.tiktok.campaigns import TikTokListCampaignsHandler

    client = SimpleNamespace(
        list_campaigns=lambda *_args, **_kwargs: pytest.fail("Do not scan latest campaigns"),
        get_campaign=lambda account, identifier: {"campaign_id": identifier, "operation_status": "DISABLE"},
    )
    result = TikTokListCampaignsHandler(client).execute(
        SimpleNamespace(account_id="7397068114548195329"), {"campaign_id": "1879024049711217"},
    )
    assert result.success
    assert result.data["campaigns"][0]["campaign_id"] == "1879024049711217"


@pytest.mark.parametrize("key", ["tiktok.test.traffic", "tiktok.test.sales"])
def test_verified_cta_reference_replaces_unusable_plain_button_enum(key):
    from agents.applications.advertising.creation.templates import load_builtin_template_definitions
    template = next(row for row in load_builtin_template_definitions() if row["key"] == key)
    assert template["values"]["ad.call_to_action_id"] == "7696698198538112006"
    assert "ad.call_to_action" not in template["values"]


@pytest.mark.parametrize("blueprint_id", ["tiktok.traffic_video", "tiktok.product_sales_video"])
def test_blueprint_accepts_a_portfolio_without_asking_for_a_plain_enum(blueprint_id, cta_runtime):
    runtime = cta_runtime
    runtime.register_tool_source(create_tiktok_tool_source())
    evaluated = runtime.evaluate_creation_blueprint(
        blueprint_id, {"ad.call_to_action_id": PORTFOLIO},
    )
    fields = {field["path"]: field for field in evaluated["fields"]}
    assert fields["ad.call_to_action"]["required"] is False
    assert fields["ad.call_to_action_id"]["value"] == PORTFOLIO
    empty = runtime.evaluate_creation_blueprint(blueprint_id, {})
    assert "ad.call_to_action" in empty["missing_fields"]
    changed = runtime.evaluate_creation_blueprint(
        blueprint_id, {"ad.call_to_action": "SHOP_NOW"},
        changed_fields=["ad.call_to_action"],
    )
    assert "ad.call_to_action_id" in changed["reset_fields"]


@pytest.mark.parametrize("field", ["call_to_action_id", "ad_configuration.call_to_action_id"])
def test_smart_plus_cta_picker_uses_scoped_exact_portfolio_readback(field, cta_runtime):
    client = TikTokAPIClient({"access_token": "test"})
    calls = []
    client.get_creative_portfolio = lambda account, identifier: (
        calls.append((account, identifier)) or {
            "creative_portfolio_id": identifier, "creative_portfolio_type": "CTA",
        }
    )
    runtime = cta_runtime
    runtime.whitelist_validator.allowed_accounts = {"tiktok": [ACCOUNT]}
    runtime.register_tool_source(create_tiktok_tool_source(client))
    schema = definitions()["tiktok_smart_plus_create_ad"].input_schema.properties
    for part in field.split("."):
        field_schema = schema[part]
        schema = field_schema.get("properties", {})
    assert field_schema.get("manual_entry") is None
    result = runtime.resolve_parameter_options(
        "tiktok", field, "tiktok_smart_plus_create_ad",
        account_id=ACCOUNT, session_id="cta-template", user_id="test-user",
        account_scope={"tiktok": {ACCOUNT}}, query=PORTFOLIO,
    )
    assert calls == [(ACCOUNT, PORTFOLIO)]
    assert [option["value"] for option in result["options"]] == [PORTFOLIO]
    assert result["options"][0]["selection_token"]


@pytest.mark.parametrize("cta", [
    {"call_to_action_id": PORTFOLIO},
    {"ad_configuration": {"call_to_action_id": PORTFOLIO}},
])
@pytest.mark.parametrize("plain", [
    {"call_to_action": "SHOP_NOW"},
    {"call_to_action_list": [{"call_to_action": "SHOP_NOW"}]},
])
def test_conflicting_cta_choices_are_not_silently_overridden(cta, plain):
    data = {
        "account_id": ACCOUNT, "campaign_id": "123", "adgroup_id": "456",
        "ad_name": "Paused test", "video_id": "video-1", **cta, **plain,
    }
    assert any("CTA" in error for error in validate_tool_input(
        definitions()["tiktok_smart_plus_create_ad"].input_schema, data,
    ))
    client = TikTokAPIClient({"access_token": "test"})
    client.request = lambda *_a, **_kw: pytest.fail("Conflicting CTA must not reach provider")
    with pytest.raises(ValueError, match="CTA"):
        client.create_smart_plus_ad(ACCOUNT, "123", "456", data)
