"""Objective-level regressions; all provider transports are replaced locally."""

import pytest

from scripts.advertising.audit_creation_contracts import build_runtime
from agents.tools.advertising.clients.google_ads_client import GoogleAdsAPIClient
from agents.tools.advertising.clients.meta_client import MetaAPIClient
from agents.tools.advertising.clients.tiktok_client import TikTokAPIClient
from agents.agent_harness.core.tool_registry import validate_tool_input


@pytest.fixture(scope="module")
def runtime():
    return build_runtime()


def test_meta_awareness_has_complete_guided_hierarchy(runtime):
    blueprint = runtime.creation_blueprints.resolve(
        "meta", selector_values={"objective": "OUTCOME_AWARENESS"},
    )
    assert blueprint is not None
    assert list(blueprint.tools) == [
        "meta_create_campaign", "meta_create_adset", "meta_create_awareness_ad",
    ]
    tool = runtime.registry.get("meta_create_awareness_ad")[0]
    payload = {"adset_id": "s1", "name": "Awareness", "page_id": "p1",
               "link": "https://example.com", "media_type": "IMAGE"}
    assert validate_tool_input(tool.input_schema, payload)
    assert not validate_tool_input(tool.input_schema, {**payload, "image_hash": "image1"})


@pytest.mark.parametrize("alias,canonical", [
    ("OUTCOME_MESSAGES", "OUTCOME_ENGAGEMENT"),
    ("TRAFFIC", "OUTCOME_TRAFFIC"), ("LINK_CLICKS", "OUTCOME_TRAFFIC"),
    ("CONVERSIONS", "OUTCOME_SALES"),
    ("PRODUCT_CATALOG_SALES", "OUTCOME_SALES"),
    ("APP_INSTALLS", "OUTCOME_APP_PROMOTION"),
])
def test_meta_legacy_objective_is_normalized_at_transport(alias, canonical):
    client = MetaAPIClient({"access_token": "test"})
    captured = []
    client.request = lambda *args, **kwargs: captured.append(kwargs["data"]) or {"id": "c1"}
    client.create_campaign("123", {"name": "Alias", "objective": alias}, live=True)
    assert captured[0]["objective"] == canonical
    assert captured[0]["status"] == "PAUSED"


def lead_group(**updates):
    return {
        "objective_type": "LEAD_GENERATION", "adgroup_name": "Website leads",
        "promotion_type": "LEAD_GENERATION", "promotion_target_type": "EXTERNAL_WEBSITE",
        "optimization_goal": "CONVERT", "pixel_id": "px1", "optimization_event": "FORM",
        "bid_type": "BID_TYPE_CUSTOM", "conversion_bid_price": 2,
        "billing_event": "OCPM", "schedule_type": "SCHEDULE_FROM_NOW",
        "schedule_start_time": "2026-11-01 00:00:00", "location_ids": ["1562822"],
        **updates,
    }


def lead_ad(**updates):
    return {
        "objective_type": "LEAD_GENERATION", "promotion_target_type": "EXTERNAL_WEBSITE",
        "ad_name": "Lead creative", "tiktok_item_id": "item1",
        "identity_type": "AUTH_CODE", "identity_id": "identity1",
        "landing_page_url": "https://example.com/signup", **updates,
    }


def test_tiktok_website_lead_builds_current_wire_contract(runtime):
    client = TikTokAPIClient({"access_token": "test"})
    captured = []
    client.request = lambda *args, **kw: captured.append(kw["data"]) or {
        "code": 0, "data": {"adgroup_id": "g1", "smart_plus_ad_id": "a1"},
    }
    group_tool = runtime.registry.get("tiktok_smart_plus_create_adgroup")[0]
    assert not validate_tool_input(group_tool.input_schema, {"account_id": "123", "campaign_id": "c1", **lead_group()})
    client.create_smart_plus_adgroup("123", "c1", lead_group(), live=True)
    assert captured[0]["optimization_goal"] == "CONVERT"
    assert captured[0]["optimization_event"] == "FORM"
    assert "objective_type" not in captured[0]
    ad_tool = runtime.registry.get("tiktok_smart_plus_create_ad")[0]
    assert not validate_tool_input(ad_tool.input_schema, {"account_id": "123", "campaign_id": "c1", "adgroup_id": "g1", **lead_ad()})
    client.create_smart_plus_ad("123", "c1", "g1", lead_ad(), live=True)
    assert captured[1]["landing_page_url_list"] == [{"landing_page_url": "https://example.com/signup"}]
    assert "page_list" not in captured[1]
    assert "promotion_target_type" not in captured[1]
    assert "objective_type" not in captured[1]
    assert captured[1]["operation_status"] == "DISABLE"


@pytest.mark.parametrize("updates,field", [
    ({"pixel_id": None}, "pixel_id"),
    ({"optimization_event": None}, "optimization_event"),
    ({"optimization_goal": "LEAD_GENERATION"}, "optimization_goal"),
    ({"promotion_target_type": "unknown"}, "promotion_target_type"),
])
def test_tiktok_lead_invalid_group_fails_before_network(updates, field):
    client = TikTokAPIClient({"access_token": "test"})
    client.request = lambda *a, **kw: pytest.fail("unexpected provider I/O")
    with pytest.raises(ValueError, match=field):
        client.create_smart_plus_adgroup("123", "c1", lead_group(**updates), live=True)


@pytest.mark.parametrize("updates,field", [
    ({"landing_page_url": None}, "landing_page_url"),
    ({"promotion_target_type": "INSTANT_PAGE"}, "page_list"),
    ({"promotion_target_type": "unknown"}, "promotion_target_type"),
])
def test_tiktok_lead_invalid_destination_fails_before_network(updates, field):
    client = TikTokAPIClient({"access_token": "test"})
    client.request = lambda *a, **kw: pytest.fail("unexpected provider I/O")
    with pytest.raises(ValueError, match=field):
        client.create_smart_plus_ad("123", "c1", "g1", lead_ad(**updates), live=True)


def test_latest_blueprint_listing_preserves_explicit_old_version(runtime):
    old = runtime.creation_blueprints.get("tiktok.lead_generation", "2.0.2")
    latest = runtime.creation_blueprints.get("tiktok.lead_generation")
    assert old is not None
    assert latest.version != old.version
    listed = [b for b in runtime.list_creation_blueprints("tiktok") if b["id"] == old.blueprint_id]
    assert [b["version"] for b in listed] == [latest.version]
    assert runtime.creation_blueprints.get(old.blueprint_id, old.version) == old


def test_tiktok_web_conversions_resolves_dedicated_blueprint(runtime):
    blueprint = runtime.creation_blueprints.resolve(
        "tiktok", selector_values={"objective": "WEB_CONVERSIONS"},
    )
    assert blueprint is not None
    assert blueprint.blueprint_id == "tiktok.web_conversions"
    assert list(blueprint.tools) == [
        "tiktok_smart_plus_create_campaign", "tiktok_smart_plus_create_adgroup",
        "tiktok_smart_plus_create_ad",
    ]


@pytest.mark.parametrize("channel,alternative", [("VIDEO", "Demand Gen"), ("SMART", "Performance Max")])
def test_google_unavailable_creation_stops_before_budget_mutation(channel, alternative):
    client = GoogleAdsAPIClient({"customer_id": "1234567890"})
    client.request = lambda *args, **kwargs: pytest.fail("must not create an orphan budget")
    with pytest.raises(ValueError, match=alternative):
        client.create_campaign("Blocked", channel, "MANUAL_CPC", 20, live=True)


@pytest.mark.parametrize("blueprint_id", ["google-ads.video", "google-ads.smart"])
def test_google_unavailable_creation_is_visible_in_support_label(runtime, blueprint_id):
    item = next(b for b in runtime.list_creation_blueprints("google-ads") if b["id"] == blueprint_id)
    assert item["support"]["creation_available"] is False
    assert item["support"]["limitation"]["source_url"].startswith("https://")


def test_objective_audit_reports_missing_blueprints_instead_of_ignoring_them(runtime):
    from types import SimpleNamespace
    from scripts.advertising.audit_objective_coverage import audit_objective_coverage

    report = audit_objective_coverage(runtime)
    assert set(report) == {"google-ads", "meta", "tiktok"}
    assert all(not row["missing"] for row in report.values())
    isolated = SimpleNamespace(
        registry=runtime.registry,
        list_ad_formats=runtime.list_ad_formats,
        creation_blueprints=SimpleNamespace(list=lambda **kw: [
            b for b in runtime.creation_blueprints.list(**kw) if b.blueprint_id != "meta.awareness"
        ]),
    )
    assert "OUTCOME_AWARENESS" in audit_objective_coverage(isolated)["meta"]["missing"]


@pytest.mark.parametrize("destination,required,not_required", [
    ("INSTANT_PAGE", "ad.page_list", "ad.landing_page_url"),
    ("EXTERNAL_WEBSITE", "ad.landing_page_url", "ad.page_list"),
])
def test_lead_form_cascade_only_requires_selected_destination(runtime, destination, required, not_required):
    from agents.tools.advertising.shared.domain.blueprint import BlueprintCascadeEngine

    blueprint = runtime.creation_blueprints.get("tiktok.lead_generation")
    result = BlueprintCascadeEngine().evaluate(blueprint, {
        "campaign.objective_type": "LEAD_GENERATION",
        "ad_group.promotion_target_type": destination,
    })
    assert required in result["missing_fields"]
    assert not_required not in result["missing_fields"]


def test_tiktok_native_lead_keeps_page_list_and_pause_status():
    client = TikTokAPIClient({"access_token": "test"})
    captured = []
    client.request = lambda *a, **kw: captured.append(kw["data"]) or {
        "code": 0, "data": {"smart_plus_ad_id": "a1"},
    }
    client.create_smart_plus_ad("123", "c1", "g1", lead_ad(
        promotion_target_type="INSTANT_PAGE", landing_page_url=None,
        page_list=[{"page_id": "form1"}],
    ), live=True)
    assert captured[0]["page_list"] == [{"page_id": "form1"}]
    assert captured[0]["operation_status"] == "DISABLE"


def test_lead_tool_schema_rejects_missing_website_destination(runtime):
    tool = runtime.registry.get("tiktok_smart_plus_create_ad")[0]
    payload = {"account_id": "123", "campaign_id": "c1", "adgroup_id": "g1", **lead_ad(landing_page_url=None)}
    assert validate_tool_input(tool.input_schema, payload)
    payload.pop("landing_page_url")
    payload["landing_page_url_list"] = [{"landing_page_url": "https://example.com/signup"}]
    assert not validate_tool_input(tool.input_schema, payload)


def test_lead_selects_smart_plus_instead_of_legacy_chain(runtime):
    from agents.agent_harness.core.interfaces import ParsedIntent
    from agents.agent_harness.core.intent import SimpleIntentRouter

    intent = ParsedIntent("create_campaign", "创建线索广告", ["tiktok"],
                          scoped_parameters={"tiktok": {"objective_type": "LEAD_GENERATION"}})
    for name in ("tiktok_smart_plus_create_campaign", "tiktok_smart_plus_create_adgroup", "tiktok_smart_plus_create_ad"):
        tool = runtime.registry.get(name)[0]
        assert SimpleIntentRouter._matches_activation(tool, intent, "tiktok", narrow_candidates=True)
    for name in ("tiktok_create_campaign", "tiktok_create_adgroup", "tiktok_create_single_video_ad"):
        tool = runtime.registry.get(name)[0]
        assert not SimpleIntentRouter._matches_activation(tool, intent, "tiktok", narrow_candidates=True)


def test_new_awareness_tool_keeps_write_gate_and_readback(runtime):
    from agents.agent_harness.core.interfaces import ToolEffect

    tool = runtime.registry.get("meta_create_awareness_ad")[0]
    assert tool.effect_class == ToolEffect.WRITE
    assert "ads.plan" in tool.required_permissions
    assert tool.readback_tool == "meta_get_ad"


@pytest.mark.parametrize("destination,goal,price_field", [
    ("EXTERNAL_WEBSITE", "CONVERT", "conversion_bid_price"),
    ("INSTANT_PAGE", "LEAD_GENERATION", "bid_price"),
])
def test_custom_lead_bid_is_required_before_any_hierarchy_execution(runtime, destination, goal, price_field):
    tool = runtime.registry.get("tiktok_smart_plus_create_adgroup")[0]
    payload = {"account_id": "123", "campaign_id": "c1", **lead_group(
        promotion_target_type=destination, optimization_goal=goal,
    )}
    payload.pop("conversion_bid_price")
    assert validate_tool_input(tool.input_schema, payload)
    payload[price_field] = 2
    assert not validate_tool_input(tool.input_schema, payload)
