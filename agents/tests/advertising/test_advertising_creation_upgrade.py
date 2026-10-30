"""Offline payload and guided-creation checks; all network calls are replaced."""

import json

import pytest

from agents.agent_harness.core.interfaces import ToolContext
from agents.agent_harness.core.tool_registry import validate_tool_input
from agents.tools.advertising.clients.google_ads_client import GoogleAdsAPIClient
from agents.tools.advertising.clients.meta_client import MetaAPIClient
from agents.tools.advertising.clients.tiktok_client import TikTokAPIClient
from scripts.advertising.audit_creation_contracts import build_runtime
from agents.tools.advertising.providers.meta import create_meta_tool_source
from agents.tools.advertising.providers.google import create_google_tool_source


@pytest.fixture(autouse=True)
def block_provider_http(monkeypatch):
    from requests import Session
    def blocked(*_args, **_kwargs):
        pytest.fail("provider HTTP is forbidden in creation-contract tests")
    monkeypatch.setattr(Session, "request", blocked)


@pytest.fixture(scope="module")
def runtime():
    value = build_runtime()
    yield value
    value.close(wait=True)


@pytest.mark.parametrize("media,fields,story_key", [
    ("IMAGE", {"image_hash": "image-1"}, "link_data"),
    ("VIDEO", {"video_id": "video-1", "thumbnail_image_hash": "cover-1"}, "video_data"),
])
def test_meta_lead_media_survives_registered_tool_and_provider(runtime, media, fields, story_key):
    definition, _ = runtime.registry.get("meta_create_lead_ad")
    payload = {"adset_id": "set-1", "name": "Leads", "page_id": "page-1",
               "form_id": "form-1", "media_type": media, "headline": "报名",
               "message": "了解详情", **fields}
    assert not validate_tool_input(definition.input_schema, payload)
    client = MetaAPIClient({"access_token": "test"})
    client.request = lambda *_args, **_kw: pytest.fail("unexpected provider I/O")
    handler = next(handler for tool, handler in create_meta_tool_source(client).register_tools()
                   if tool.name == definition.name)
    result = handler.execute(ToolContext("s", "u", scope={"account_id": "account-1"}), payload)
    assert result.success, result.error
    operation = result.data["ad_id"]["operation"]["/act_account-1/ads"]["create"]
    story = json.loads(operation["creative"])["object_story_spec"]
    assert story[story_key]["call_to_action"]["value"]["lead_gen_form_id"] == "form-1"
    if media == "VIDEO":
        assert story["video_data"]["video_id"] == "video-1"
        assert story["video_data"]["image_hash"] == "cover-1"
        assert "link_data" not in story
    else:
        assert story["link_data"]["image_hash"] == "image-1"


@pytest.mark.parametrize("media,extra", [
    ("IMAGE", {}), ("VIDEO", {}), ("VIDEO", {"video_id": "v", "image_hash": "wrong"}),
    ("GIF", {"image_hash": "i"}),
])
def test_meta_invalid_lead_media_fails_before_provider(media, extra):
    client = MetaAPIClient({"access_token": "test"})
    client.request = lambda *_a, **_kw: pytest.fail("unexpected provider I/O")
    with pytest.raises(ValueError):
        client.create_lead_ad("1", "2", {"name": "Lead", "page_id": "p", "form_id": "f",
                             "media_type": media, **extra}, live=True)


@pytest.mark.parametrize("tool_name", [
    "google_create_demand_gen_ad_group", "google_create_specialized_ad_group",
])
def test_google_demand_gen_group_does_not_inject_display_type_or_cpc(runtime, tool_name):
    definition, _ = runtime.registry.get(tool_name)
    payload = {"campaign_id": "101", "campaign_type": "DEMAND_GEN", "name": "Demand group",
               "demand_gen_ad_group_settings": {"channel_controls": {
                   "selected_channels": {"youtube_shorts": True, "discover": False},
               }}}
    assert not validate_tool_input(definition.input_schema, payload)
    client = GoogleAdsAPIClient({"customer_id": "1234567890"})
    client.request = lambda *_a, **_kw: pytest.fail("unexpected provider I/O")
    handler = next(handler for tool, handler in create_google_tool_source(client).register_tools()
                   if tool.name == tool_name)
    result = handler.execute(ToolContext("s", "u", scope={"account_id": "1234567890"}), payload)
    assert result.success, result.error
    operation = result.data["ad_group_id"]["operation"]["adGroups"]["create"]
    assert operation["status"] == "PAUSED"
    assert "type" not in operation
    assert "cpcBidMicros" not in operation
    assert operation["demandGenAdGroupSettings"]["channelControls"]["selectedChannels"]["youtubeShorts"]
    assert "channelConfig" not in operation["demandGenAdGroupSettings"]["channelControls"]


def test_demand_gen_dedicated_tool_rejects_manual_cpc_and_wrong_type(runtime):
    definition, _ = runtime.registry.get("google_create_demand_gen_ad_group")
    payload = {"campaign_id": "101", "name": "Demand group"}
    assert not validate_tool_input(definition.input_schema, payload)
    for field, value in (("cpc_bid_micros", 500000), ("type", "DISPLAY_STANDARD"),
                         ("campaign_type", "SEARCH")):
        assert validate_tool_input(definition.input_schema, {**payload, field: value})


@pytest.mark.parametrize("controls", [
    {"channel_config": "SELECTED_CHANNELS"},
    {"selected_channels": {"youtube_shorts": False}},
    {"selected_channels": {"youtube_shorts": True}, "channel_strategy": "ALL_CHANNELS"},
    {"selected_channels": {"unpublished_channel": True}},
])
def test_demand_gen_invalid_controls_fail_in_schema_and_client(runtime, controls):
    definition, _ = runtime.registry.get("google_create_demand_gen_ad_group")
    payload = {"campaign_id": "101", "name": "Demand",
               "demand_gen_ad_group_settings": {"channel_controls": controls}}
    assert validate_tool_input(definition.input_schema, payload)
    client = GoogleAdsAPIClient({"customer_id": "1234567890"})
    client.request = lambda *_a, **_kw: pytest.fail("unexpected provider I/O")
    with pytest.raises(ValueError):
        client.create_ad_group("101", "Demand", demand_gen_ad_group_settings=payload[
            "demand_gen_ad_group_settings"], live=True)


def test_versioned_blueprints_expose_new_media_and_keep_old_contracts(runtime):
    old = runtime.creation_blueprints.get("meta.lead_generation", "1.0.0")
    latest = runtime.creation_blueprints.get("meta.lead_generation")
    assert old and latest.version != old.version
    assert {"ad.media_type", "ad.image_hash", "ad.video_id", "ad.thumbnail_image_hash"} <= {
        field["path"] for field in latest.fields
    }
    traffic = runtime.creation_blueprints.get("tiktok.traffic_video")
    assert runtime.creation_blueprints.get("tiktok.traffic_video", "3.3.0")
    media = next(field for field in traffic.fields if field["path"] == "ad.ad_format")
    assert set(media["options"]) == {"SINGLE_VIDEO", "SINGLE_IMAGE", "CAROUSEL_ADS"}
    for name in ("multi_asset", "carousel", "product", "video_responsive"):
        bp = runtime.creation_blueprints.get(f"google-ads.demand_gen_{name}")
        assert "google_create_demand_gen_ad_group" in bp.tools


@pytest.mark.parametrize("media,fields", [
    ("SINGLE_IMAGE", {"image_ids": ["image1"], "video_id": "video1"}),
    ("CAROUSEL_ADS", {"image_ids": ["image1"]}),
    ("CAROUSEL_ADS", {"image_ids": ["image1", "image2"], "video_id": "video1"}),
])
def test_tiktok_invalid_media_combinations_fail_before_any_lookup(media, fields):
    client = TikTokAPIClient({"access_token": "test"})
    client.request = lambda *_a, **_kw: pytest.fail("unexpected provider I/O or asset lookup")
    with pytest.raises(ValueError):
        client.create_smart_plus_ad("1", "2", "3", {
            "ad_name": "Traffic", "ad_format": media, **fields,
        }, live=True)


def test_tiktok_schema_accepts_existing_structured_creative_and_uri_inputs(runtime):
    definition, _ = runtime.registry.get("tiktok_smart_plus_create_ad")
    base = {"account_id": "1", "campaign_id": "2", "adgroup_id": "3", "ad_name": "Traffic"}
    assert not validate_tool_input(definition.input_schema, {**base, "image_web_uris": ["uri1"]})
    assert not validate_tool_input(definition.input_schema, {**base, "creative_list": [{
        "creative_info": {"ad_format": "SINGLE_IMAGE", "image_info": [{"web_uri": "uri1"}]},
    }]})


def test_every_builtin_template_resolves_its_pinned_blueprint_and_values(runtime):
    from scripts.advertising.audit_creation_templates import audit_creation_templates
    result = audit_creation_templates(runtime)
    assert result["count"] > 35
    assert result["issues"] == []


def test_template_audit_finds_removed_fields_and_wrong_media_family(runtime):
    from copy import deepcopy
    from agents.applications.advertising.creation.templates import load_builtin_template_definitions
    from scripts.advertising.audit_creation_templates import audit_creation_templates
    rows = deepcopy(load_builtin_template_definitions())
    demand = next(row for row in rows if row["key"] == "google-ads.demand_gen_carousel.v1.1.starter")
    demand["values"]["ad_group.type"] = "SEARCH_STANDARD"
    traffic = next(row for row in rows if row["key"] == "tiktok.traffic.single_image.starter")
    traffic["ad_format"] = "SINGLE_IMAGE"
    result = audit_creation_templates(runtime, rows)
    assert {item["key"] for item in result["issues"]} == {demand["key"], traffic["key"]}


def test_followup_adgroup_intent_routes_to_demand_gen_contract(runtime):
    from agents.agent_harness.core.interfaces import ParsedIntent
    from agents.agent_harness.core.intent import SimpleIntentRouter
    routed = SimpleIntentRouter().route(ParsedIntent(
        "create_adgroup", "继续创建 Demand Gen Ad Group", ["google-ads"],
        scoped_parameters={"google-ads": {"campaign_type": "DEMAND_GEN"}},
    ), runtime.registry)
    assert [tool.name for tool in routed["google-ads"]] == ["google_create_demand_gen_ad_group"]


@pytest.mark.parametrize("settings", [
    {}, {"channel_controls": {"channel_strategy": "ALL_CHANNELS"}},
    {"channel_controls": {"channel_strategy": "ALL_OWNED_AND_OPERATED_CHANNELS"}},
])
def test_demand_gen_supported_strategy_payloads_need_no_manual_bids(runtime, settings):
    definition, _ = runtime.registry.get("google_create_demand_gen_ad_group")
    arguments = {"campaign_id": "101", "name": "Demand", "demand_gen_ad_group_settings": settings}
    assert not validate_tool_input(definition.input_schema, arguments)
    client = GoogleAdsAPIClient({"customer_id": "1234567890"})
    result = client.create_ad_group("101", "Demand", cpc_bid_micros=None, type=None,
                                    demand_gen_ad_group_settings=settings, live=False)
    assert result["execution_status"] == "planned"
    assert "cpcBidMicros" not in result["operation"]["adGroups"]["create"]


@pytest.mark.parametrize("key,blueprint", [
    ("google-ads.demand_gen_carousel.starter", "google-ads.demand_gen_carousel"),
    ("meta.lead_generation.starter", "meta.lead_generation"),
])
def test_old_builtin_ids_remain_readable_but_do_not_duplicate_current_catalog(runtime, key, blueprint):
    import hashlib
    from agents.applications.advertising.creation.templates import creation_template_manager_for_runtime
    old_id = "builtin_" + hashlib.sha256(f"{key}:{blueprint}:1.0.0:".encode()).hexdigest()[:24]
    manager = creation_template_manager_for_runtime(runtime)
    old = manager.get("t", "u", old_id)
    assert old is not None and old["blueprint_version"] == "1.0.0"
    visible = manager.list("t", "u", source="builtin", limit=200)
    assert old_id not in {row["template_id"] for row in visible}
    assert any(row["blueprint_id"] == blueprint and row["blueprint_version"] == "1.1.0"
               for row in visible)


@pytest.mark.parametrize("key,provider,visible,hidden", [
    ("meta.lead_generation.image.starter", "meta", "ad.image_hash", "ad.video_id"),
    ("meta.lead_generation.video.starter", "meta", "ad.video_id", "ad.image_hash"),
    ("tiktok.traffic.single_image.starter", "tiktok", "ad.image_ids", "ad.video_id"),
    ("tiktok.traffic.carousel_ads.starter", "tiktok", "ad.image_ids", "ad.video_id"),
])
def test_new_starters_materialize_matching_media_controls(runtime, key, provider, visible, hidden):
    from agents.agent_harness.core.interfaces import ParsedIntent
    from agents.applications.advertising.creation.templates import creation_template_manager_for_runtime
    account = "1234567890"
    runtime.whitelist_validator.allowed_accounts[provider] = [account]
    manager = creation_template_manager_for_runtime(runtime)
    template = next(item for item in manager.list("t", "u", source="builtin", limit=200)
                    if item["catalog_key"] == key)
    intent = runtime.apply_creation_template_to_intent(
        ParsedIntent("create_campaign", "新建广告", [provider]), template["template_id"],
        account_id=account, account_scope={provider: [account]}, tenant_id="t", user_id="u",
    )
    card = runtime.build_creation_ui(
        intent, account_id=account, account_scope={provider: [account]}, tenant_id="t", user_id="u",
    )["cards"][0]
    assert card["type"] == "ad_creation_form"
    fields = {field["path"]: field for field in card["fields"]}
    assert fields[visible]["visible"] and fields[visible]["required"]
    assert not fields[hidden]["visible"]
    assert card["blueprint_version"] == template["blueprint_version"]
    assert card["invalid_fields"] == []
