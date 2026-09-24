"""Tests for declarative creation blueprints and cascade behavior."""

from pathlib import Path

import pytest

from agents.ad_agent.tools.providers.tiktok import create_tiktok_tool_source
from agents.ad_agent.tools.providers.dv360 import create_dv360_tool_source
from agents.ad_agent.tools.providers.meta import create_meta_tool_source
from agents.ad_agent.tools.providers.google import create_google_tool_source
from agents.ad_agent.domain.ad.blueprint import (
    AdCreationBlueprint,
    BlueprintCascadeEngine,
    BlueprintRegistry,
    BlueprintValidationError,
    load_blueprint_file,
)
from agents.ad_agent.domain.ad.creation_card import CreationCardBuilder
from agents.ad_agent.core.interfaces import ParsedIntent, ToolDefinition, ToolSchema, ToolEffect
from agents.ad_agent.core.tool_registry import SimpleToolRegistry
from agents.ad_agent.runtime.account_policy import AccountWhitelistValidator
from agents.ad_agent.runtime.runtime import AdvertisingComposition


BLUEPRINT_PATH = Path(__file__).parents[1] / "tools" / "providers" / "tiktok" / "blueprints" / "app_conversion_video.v1.json"


@pytest.fixture(autouse=True)
def isolate_blueprint_tests_from_deployment_account_config(monkeypatch):
    """Keep schema tests independent from the checked-in test-account config.

    Account-first behavior is covered explicitly below with a configured
    whitelist. The remaining Blueprint tests exercise field contracts and
    should not unexpectedly turn into account-selector tests just because
    the local deployment config contains test accounts.
    """
    monkeypatch.setattr(
        AccountWhitelistValidator,
        "_load_config",
        lambda _self: None,
    )


def test_tiktok_blueprint_is_json_and_references_registered_tools():
    runtime = AdvertisingComposition(require_llm=False, offline_mode=True)
    runtime.register_tool_source(create_tiktok_tool_source())

    items = runtime.list_creation_blueprints("tiktok", "SINGLE_VIDEO")
    assert {item["id"] for item in items} == {
        "tiktok.app_conversion_video",
        "tiktok.lead_generation",
        "tiktok.product_sales_video",
        "tiktok.traffic_video",
    }
    assert all(item["selector"]["dimension"] == "objective" for item in items)
    versions = {item["id"]: item["version"] for item in items}
    assert versions["tiktok.app_conversion_video"] == "2.0.1"
    assert versions["tiktok.lead_generation"] == "2.0.0"
    assert versions["tiktok.product_sales_video"] == "2.0.1"
    assert versions["tiktok.traffic_video"] == "3.0.0"
    assert runtime.creation_blueprints.get("tiktok.app_conversion_video") is not None


def test_creation_blueprint_list_publishes_contract_and_support_metadata():
    runtime = AdvertisingComposition(require_llm=False, offline_mode=True)
    for tool_source in (
        create_google_tool_source(), create_meta_tool_source(), create_tiktok_tool_source(),
    ):
        runtime.register_tool_source(tool_source)

    blueprints = runtime.list_creation_blueprints()
    search = next(item for item in blueprints if item["id"] == "google-ads.search")

    assert search["ui_contract"]["field_count"] == len(search["fields"])
    assert search["ui_contract"]["required_count"] > 0
    assert {item["name"] for item in search["ui_contract"]["hierarchies"]} == {
        "Campaign", "Ad Group", "Ad",
    }
    assert search["support"]["level"] in {"supported_dry_run", "partial_dry_run"}
    assert search["support"]["catalog_match"] is True


def test_creation_blueprint_support_does_not_claim_unverified_tiktok_formats():
    runtime = AdvertisingComposition(require_llm=False, offline_mode=True)
    runtime.register_tool_source(create_tiktok_tool_source())

    formats = runtime.list_ad_formats("tiktok")
    blueprint_suffixes = {
        item.blueprint_id.rsplit(".", 1)[-1]
        for item in runtime.creation_blueprints.list(provider="tiktok")
    }
    assert {item["format_id"] for item in formats if item["coverage"] == "declared_only"} == {
        "brand.topview", "brand.takeover",
    }
    assert "topview" not in blueprint_suffixes
    assert "takeover" not in blueprint_suffixes


def test_dv360_guided_surfaces_start_from_explicit_existing_parents():
    runtime = AdvertisingComposition(require_llm=False, offline_mode=True)
    runtime.register_tool_source(create_dv360_tool_source())

    blueprints = runtime.list_creation_blueprints(provider="dv360")
    assert {item["id"] for item in blueprints} == {
        "dv360.insertion_order", "dv360.line_item",
    }
    insertion_order = next(item for item in blueprints if item["id"] == "dv360.insertion_order")
    line_item = next(item for item in blueprints if item["id"] == "dv360.line_item")
    assert any(field["path"] == "insertion_order.campaign_id" for field in insertion_order["fields"])
    assert any(field["path"] == "line_item.io_id" for field in line_item["fields"])
    assert line_item["selector"]["values"] == [
        "DISPLAY_DEFAULT", "VIDEO_DEFAULT", "AUDIO_DEFAULT",
        "CONNECTED_TV_DEFAULT", "YOUTUBE_AND_PARTNERS_VIDEO",
    ]


def test_tiktok_lead_blueprint_uses_smart_plus_and_requires_instant_page():
    runtime = AdvertisingComposition(require_llm=False, offline_mode=True)
    runtime.register_tool_source(create_tiktok_tool_source())
    blueprint = runtime.creation_blueprints.get("tiktok.lead_generation")

    assert blueprint is not None
    assert blueprint.version == "2.0.0"
    assert blueprint.tools == (
        "tiktok_smart_plus_create_campaign",
        "tiktok_smart_plus_create_adgroup",
        "tiktok_smart_plus_create_ad",
    )
    fields = {field["path"]: field for field in blueprint.fields}
    assert fields["ad.page_list"]["required"] is True
    assert fields["ad.page_list"]["manual_entry"]["source"] == "provider_instant_page"


def test_tiktok_optional_boolean_defaults_are_materialized_in_creation_card():
    runtime = AdvertisingComposition(require_llm=False, offline_mode=True)
    runtime.register_tool_source(create_tiktok_tool_source())
    intent = ParsedIntent(
        "create_campaign", "创建 TikTok 流量广告", ["tiktok"],
        scoped_parameters={"tiktok": {"objective_type": "TRAFFIC"}},
    )

    card = runtime.build_creation_ui(intent)["cards"][0]
    fields = {field["path"]: field for field in card["fields"]}

    assert fields["campaign.is_search_campaign"]["value"] is False
    assert fields["campaign.catalog_enabled"]["value"] is False
    assert "campaign.catalog_enabled" not in card["missing_fields"]


def test_creation_card_separates_safe_defaults_from_account_context_inputs():
    runtime = AdvertisingComposition(require_llm=False, offline_mode=True)
    runtime.register_tool_source(create_tiktok_tool_source())
    card = runtime.build_creation_ui(ParsedIntent(
        "create_campaign", "创建 TikTok 流量广告", ["tiktok"],
        scoped_parameters={"tiktok": {"objective": "TRAFFIC"}},
    ))["cards"][0]
    fields = {field["path"]: field for field in card["fields"]}

    assert card["auto_filled_count"] >= 8
    assert fields["campaign.campaign_name"]["input_mode"] == "auto_default"
    assert fields["campaign.campaign_name"]["user_required"] is False
    assert fields["ad_group.budget_mode"]["value"] == "BUDGET_MODE_DYNAMIC_DAILY_BUDGET"
    assert fields["ad_group.location_ids"]["input_mode"] == "context_required"
    assert fields["ad_group.location_ids"]["user_required"] is True
    assert fields["ad_group.budget"]["user_required"] is True


def test_meta_creation_card_materializes_objective_dependent_defaults():
    runtime = AdvertisingComposition(require_llm=False, offline_mode=True)
    runtime.register_tool_source(create_meta_tool_source())
    card = runtime.build_creation_ui(ParsedIntent(
        "create_campaign", "创建 Meta 流量广告", ["meta"],
        scoped_parameters={"meta": {"objective": "OUTCOME_TRAFFIC"}},
    ))["cards"][0]
    fields = {field["path"]: field for field in card["fields"]}

    assert fields["campaign.buying_type"]["value"] == "AUCTION"
    assert fields["ad_set.optimization_goal"]["value"] == "LANDING_PAGE_VIEWS"
    assert fields["ad_set.billing_event"]["value"] == "IMPRESSIONS"
    assert fields["ad_set.bid_strategy"]["value"] == "LOWEST_COST_WITHOUT_CAP"
    assert fields["ad.link"]["user_required"] is True


def test_tiktok_spark_blueprint_uses_current_all_in_one_surface():
    runtime = AdvertisingComposition(require_llm=False, offline_mode=True)
    runtime.register_tool_source(create_tiktok_tool_source())

    blueprint = runtime.creation_blueprints.get("tiktok.spark")
    assert blueprint is not None
    assert blueprint.version == "2.0.0"
    assert blueprint.tools == ("tiktok_create_all_in_one_spark_ad",)
    assert blueprint.selector["values"] == ["REACH", "VIDEO_VIEWS", "ENGAGEMENT"]

    result = runtime.evaluate_creation_blueprint(
        "tiktok.spark",
        {
            "campaign.objective_type": "VIDEO_VIEWS",
            "ad_group.optimization_goal": "ENGAGED_VIEW",
        },
    )
    states = {item["path"]: item for item in result["fields"]}
    assert states["ad_group.optimization_goal"]["options"] == ["ENGAGED_VIEW"]
    assert states["ad_group.frequency"]["required"] is False
    assert states["ad.tiktok_item_id"]["required"] is True


def test_blueprint_registry_resolves_each_provider_entry_dimension_without_router_branches():
    runtime = AdvertisingComposition(require_llm=False, offline_mode=True)
    for factory in (create_meta_tool_source, create_tiktok_tool_source, create_google_tool_source):
        runtime.register_tool_source(factory())

    assert runtime.resolve_creation_blueprint(
        "meta", selector_values={"objective": "OUTCOME_LEADS"}
    )["id"] == "meta.lead_generation"
    assert runtime.resolve_creation_blueprint(
        "tiktok", selector_values={"objective": "PRODUCT_SALES"}
    )["id"] == "tiktok.product_sales_video"
    assert runtime.resolve_creation_blueprint(
        "google-ads", selector_values={"ad_format": "DISPLAY"}
    )["id"] == "google-ads.display"
    assert runtime.resolve_creation_blueprint(
        "google-ads", selector_values={"ad_format": "APP"}
    )["id"] == "google-ads.app"
    assert runtime.resolve_creation_blueprint(
        "google-ads", selector_values={"ad_format": "UNKNOWN"}
    ) is None


def test_demand_gen_variants_resolve_by_explicit_format_or_declared_terms():
    runtime = AdvertisingComposition(require_llm=False, offline_mode=True)
    runtime.register_tool_source(create_google_tool_source())

    assert runtime.resolve_creation_blueprint(
        "google-ads", selector_values={"ad_format": "DEMAND_GEN_PRODUCT"}
    )["id"] == "google-ads.demand_gen_product"

    cases = {
        "创建 Google Demand Gen 轮播广告": "google-ads.demand_gen_carousel",
        "创建 Google Demand Gen 多素材广告": "google-ads.demand_gen_multi_asset",
        "创建 Google Demand Gen 视频响应式广告": "google-ads.demand_gen_video_responsive",
        "创建 Google Demand Gen 商品广告": "google-ads.demand_gen_product",
    }
    for text, expected in cases.items():
        card = runtime.build_creation_ui(ParsedIntent(
            "create_campaign", text, ["google-ads"],
            campaign_type="DEMAND_GEN",
            scoped_parameters={"google-ads": {"campaign_type": "DEMAND_GEN"}},
        ))["cards"][0]
        assert card["blueprint_id"] == expected


def test_demand_gen_without_variant_returns_specific_blueprint_choices():
    runtime = AdvertisingComposition(require_llm=False, offline_mode=True)
    runtime.register_tool_source(create_google_tool_source())
    card = runtime.build_creation_ui(ParsedIntent(
        "create_campaign", "创建 Google Demand Gen 广告", ["google-ads"],
        campaign_type="DEMAND_GEN",
        scoped_parameters={"google-ads": {"campaign_type": "DEMAND_GEN"}},
    ))["cards"][0]

    assert card["type"] == "ad_creation_selector"
    field = card["fields"][0]
    assert field["selection_kind"] == "blueprint_variant"
    assert field["value"] is None
    assert field["state"] == "missing"
    assert {option["blueprint_id"] for option in field["options"]} == {
        "google-ads.demand_gen_carousel",
        "google-ads.demand_gen_multi_asset",
        "google-ads.demand_gen_product",
        "google-ads.demand_gen_video_responsive",
    }


def test_blueprint_field_options_are_declared_and_invalid_selection_is_not_ready():
    blueprint = load_blueprint_file(
        Path(__file__).parents[1]
        / "tools"
        / "providers"
        / "google"
        / "blueprints"
        / "display.v1.json"
    )
    result = BlueprintCascadeEngine().evaluate(
        blueprint,
        {
            "campaign.advertising_channel_type": "SEARCH",
        },
    )
    assert "campaign.advertising_channel_type" in result["invalid_fields"]
    assert result["ready"] is False


def test_meta_and_google_blueprints_use_only_registered_tool_fields():
    for blueprint_id, factory, provider in (
        ("meta.conversion_link", create_meta_tool_source, "meta"),
        ("google-ads.search", create_google_tool_source, "google-ads"),
    ):
        runtime = AdvertisingComposition(require_llm=False, offline_mode=True)
        runtime.register_tool_source(factory())
        blueprint = runtime.creation_blueprints.get(blueprint_id)
        assert blueprint is not None
        assert blueprint.provider == provider
        assert all(
            field["tool_ref"].split(".", 1)[0] in blueprint.tools
            for field in blueprint.fields
        )


def test_google_bidding_strategy_cascade_requires_only_matching_target():
    runtime = AdvertisingComposition(require_llm=False, offline_mode=True)
    runtime.register_tool_source(create_google_tool_source())
    result = runtime.evaluate_creation_blueprint(
        "google-ads.search",
        {"campaign.bidding_strategy": "TARGET_CPA"},
    )
    states = {item["path"]: item for item in result["fields"]}
    assert states["campaign.target_cpa_micros"]["required"] is True
    assert states["campaign.target_roas"]["visible"] is False
    assert "campaign.target_cpa_micros" in result["missing_fields"]


def test_meta_objective_cascade_resolves_optimization_and_billing_options():
    runtime = AdvertisingComposition(require_llm=False, offline_mode=True)
    runtime.register_tool_source(create_meta_tool_source())

    result = runtime.evaluate_creation_blueprint(
        "meta.conversion_link",
        {"campaign.objective": "OUTCOME_CONVERSIONS"},
    )
    states = {item["path"]: item for item in result["fields"]}
    assert states["ad_set.optimization_goal"]["options"] == [
        "OFFSITE_CONVERSIONS", "CONVERSIONS"
    ]
    assert states["ad_set.billing_event"]["options_state"] == "awaiting_dependency"
    assert states["ad_set.billing_event"]["options"] == []

    result = runtime.evaluate_creation_blueprint(
        "meta.conversion_link",
        {
            "campaign.objective": "OUTCOME_CONVERSIONS",
            "ad_set.optimization_goal": "OFFSITE_CONVERSIONS",
        },
    )
    states = {item["path"]: item for item in result["fields"]}
    assert states["ad_set.billing_event"]["options"] == ["IMPRESSIONS"]
    assert states["ad_set.billing_event"]["option_labels"]["IMPRESSIONS"] == "展示（按展示计费）"


def test_meta_blueprint_lookup_declarations_are_carried_to_creation_card():
    runtime = AdvertisingComposition(require_llm=False, offline_mode=True)
    runtime.register_tool_source(create_meta_tool_source())
    intent = ParsedIntent(
        "create_campaign", "创建 Meta 潜在客户广告", ["meta"],
        scoped_parameters={"meta": {"objective": "OUTCOME_LEADS"}},
    )
    card = runtime.build_creation_ui(intent)["cards"][0]
    page = next(item for item in card["fields"] if item["path"] == "ad.page_id")
    assert page["lookup"]["tool"] == "meta_list_pages"

    conversion_intent = ParsedIntent(
        "create_campaign", "创建 Meta 转化广告", ["meta"],
        scoped_parameters={"meta": {
            "objective": "OUTCOME_CONVERSIONS",
            "optimization_goal": "OFFSITE_CONVERSIONS",
        }},
    )
    conversion_card = runtime.build_creation_ui(conversion_intent)["cards"][0]
    promoted = next(item for item in conversion_card["fields"] if item["path"] == "ad_set.promoted_object")
    assert promoted["object_properties"]["pixel_id"]["lookup_tool"] == "meta_list_pixels"


def test_tiktok_cascade_filters_app_options_and_clears_incompatible_value():
    runtime = AdvertisingComposition(require_llm=False, offline_mode=True)
    runtime.register_tool_source(create_tiktok_tool_source())
    result = runtime.evaluate_creation_blueprint(
        "tiktok.app_conversion_video",
        {
            "campaign.objective_type": "APP_PROMOTION",
            "ad_group.promotion_type": "APP_ANDROID",
            "ad_group.optimization_goal": "INSTALL",
            "ad_group.deep_bid_type": "ROAS",
        },
    )
    states = {item["path"]: item for item in result["fields"]}
    assert states["ad_group.optimization_goal"]["options"] == [
        "INSTALL", "IN_APP_EVENT", "VALUE"
    ]
    assert states["ad_group.deep_bid_type"]["options"] == ["AEO"]
    assert "ad_group.deep_bid_type" in result["invalid_fields"]

    ios = runtime.evaluate_creation_blueprint(
        "tiktok.app_conversion_video",
        {
            "campaign.objective_type": "APP_PROMOTION",
            "ad_group.promotion_type": "APP_IOS",
            "ad.promotion_type": "APP_IOS",
        },
    )
    ios_states = {item["path"]: item for item in ios["fields"]}
    assert ios_states["ad_group.operating_systems"]["options"] == ["IOS"]


def test_google_search_blueprint_exposes_format_specific_bidding_catalog():
    runtime = AdvertisingComposition(require_llm=False, offline_mode=True)
    runtime.register_tool_source(create_google_tool_source())
    blueprint = runtime.creation_blueprints.get("google-ads.search")
    assert blueprint is not None
    field = next(item for item in blueprint.fields if item["path"] == "campaign.bidding_strategy")
    assert field["options"] == [
        "MANUAL_CPC", "MAXIMIZE_CLICKS", "MAXIMIZE_CONVERSIONS",
        "TARGET_CPA", "TARGET_ROAS", "TARGET_IMPRESSION_SHARE",
    ]
    assert field["option_labels"]["MAXIMIZE_CLICKS"] == "最大化点击次数"


def test_google_entry_type_is_not_repeated_at_ad_group_level():
    runtime = AdvertisingComposition(require_llm=False, offline_mode=True)
    runtime.register_tool_source(create_google_tool_source())
    blueprint = runtime.creation_blueprints.get("google-ads.display")
    assert blueprint is not None
    paths = {field["path"] for field in blueprint.fields}
    assert "ad_group.campaign_type" not in paths
    group_type = next(field for field in blueprint.fields if field["path"] == "ad_group.type")
    assert group_type["presentation"] == "derived_readonly"
    result = runtime.evaluate_creation_blueprint("google-ads.display", {})
    state = {item["path"]: item for item in result["fields"]}
    assert state["campaign.advertising_channel_type"]["value"] == "DISPLAY"
    assert state["ad_group.type"]["value"] == "DISPLAY_STANDARD"
    assert "ad_group.type" not in result["missing_fields"]


def test_provider_applicability_hides_unrelated_google_fields_and_keeps_derived_format_fields_visible():
    """Provider UI rules must narrow the card without Runtime channel branches."""
    runtime = AdvertisingComposition(require_llm=False, offline_mode=True)
    runtime.register_tool_source(create_google_tool_source())
    card = runtime.build_creation_ui(ParsedIntent(
        "create_campaign", "创建 Google Search 广告", ["google-ads"],
        scoped_parameters={"google-ads": {"ad_format": "SEARCH"}},
    ))["cards"][0]
    fields = {item["path"]: item for item in card["fields"]}

    assert fields["ad.headlines"]["visible"] is True
    assert fields["ad.descriptions"]["visible"] is True
    assert fields["campaign.shopping_setting"]["visible"] is False
    assert fields["campaign.app_campaign_setting"]["visible"] is False
    assert fields["campaign.target_cpa_micros"]["visible"] is False


def test_provider_applicability_switches_tiktok_asset_controls_by_selected_format():
    runtime = AdvertisingComposition(require_llm=False, offline_mode=True)
    runtime.register_tool_source(create_tiktok_tool_source())
    card = runtime.build_creation_ui(ParsedIntent(
        "create_campaign", "创建 TikTok 商品视频广告", ["tiktok"],
        scoped_parameters={"tiktok": {
            "objective": "PRODUCT_SALES", "ad_format": "SINGLE_VIDEO",
        }},
    ))["cards"][0]
    fields = {item["path"]: item for item in card["fields"]}

    assert fields["ad.video_id"]["visible"] is True
    assert fields["ad.video_id"]["control"] == "asset_picker"
    assert fields["ad.image_ids"]["visible"] is False
    assert fields["ad.tiktok_item_id"]["visible"] is True


def test_all_google_blueprints_make_ad_group_type_provider_derived():
    runtime = AdvertisingComposition(require_llm=False, offline_mode=True)
    runtime.register_tool_source(create_google_tool_source())
    for blueprint in runtime.creation_blueprints.list(provider="google-ads"):
        field = next(
            (item for item in blueprint.fields if item["path"] == "ad_group.type"),
            None,
        )
        if field is None:
            continue
        assert field.get("presentation") == "derived_readonly"
        assert field.get("source") == "enum"


def test_google_demand_gen_does_not_expose_a_second_ad_group_type_selector():
    runtime = AdvertisingComposition(require_llm=False, offline_mode=True)
    runtime.register_tool_source(create_google_tool_source())
    for blueprint_id in (
        "google-ads.demand_gen_multi_asset",
        "google-ads.demand_gen_carousel",
        "google-ads.demand_gen_video_responsive",
        "google-ads.demand_gen_product",
    ):
        blueprint = runtime.creation_blueprints.get(blueprint_id)
        field = next(item for item in blueprint.fields if item["path"] == "ad_group.type")
        assert field["presentation"] == "derived_readonly"
        assert field["options"] == ["SEARCH_STANDARD"]
        card = runtime.build_creation_ui(ParsedIntent(
            "create_campaign", "创建 Google Demand Gen 广告", ["google-ads"],
            scoped_parameters={"google-ads": {"ad_format": blueprint.ad_format}},
        ))["cards"][0]
        type_field = next(item for item in card["fields"] if item["path"] == "ad_group.type")
        assert type_field["control"] == "derived_readonly"
        assert type_field["options"] == [{"value": "SEARCH_STANDARD", "label": "SEARCH_STANDARD"}]


def test_google_video_ad_group_type_is_derived_from_video_format():
    blueprint = load_blueprint_file(
        Path(__file__).parents[1]
        / "tools"
        / "providers"
        / "google"
        / "blueprints"
        / "video.v1.json"
    )
    result = BlueprintCascadeEngine().evaluate(
        blueprint,
        {"ad.video_ad_format": "BUMPER"},
    )
    states = {item["path"]: item for item in result["fields"]}
    assert states["ad_group.type"]["value"] == "VIDEO_BUMPER"
    assert states["ad_group.type"]["state"] == "set"
    assert "ad_group.type" not in result["missing_fields"]


def test_creation_cards_expose_complete_schema_limits_and_provider_source_groups():
    runtime = AdvertisingComposition(require_llm=False, offline_mode=True)
    runtime.register_tool_source(create_google_tool_source())
    intent = ParsedIntent(
        "create_campaign", "创建 Google Search 广告", ["google-ads"],
        campaign_type="SEARCH",
        scoped_parameters={"google-ads": {"campaign_type": "SEARCH"}},
    )
    card = runtime.build_creation_ui(intent)["cards"][0]
    fields = {item["path"]: item for item in card["fields"]}
    assert len(card["fields"]) > 11
    assert fields["ad.headlines"]["constraints"]["minItems"] == 3
    assert fields["ad.headlines"]["constraints"]["items"]["maxLength"] == 30
    assert fields["campaign.daily_budget"]["constraints"]["minimum"] == 0
    targeting = fields["ad_group.targeting"]
    assert targeting["control"] == "object_editor"
    assert targeting["object_properties"]["target_restrictions"]["items"]["properties"][
        "targeting_dimension"
    ]["enum"]
    source_groups = [
        item for item in card["constraints"]
        if item["tool"] == "google_create_campaign" and item["type"] == "any_of"
    ]
    assert source_groups
    assert source_groups[0]["satisfied"] is False
    assert "campaign.daily_budget" in card["missing_fields"]


def test_tiktok_creation_card_does_not_truncate_provider_parameter_catalog():
    runtime = AdvertisingComposition(require_llm=False, offline_mode=True)
    runtime.register_tool_source(create_tiktok_tool_source())
    intent = ParsedIntent(
        "create_campaign", "创建 TikTok 商品销售广告", ["tiktok"],
        scoped_parameters={"tiktok": {"objective": "PRODUCT_SALES"}},
    )
    card = runtime.build_creation_ui(intent)["cards"][0]
    fields = {item["path"]: item for item in card["fields"]}
    assert len(card["fields"]) > 60
    assert fields["ad_group.location_ids"]["control"] == "lookup"
    assert fields["ad_group.location_ids"]["lookup"]["tool"] == "tiktok_list_regions"
    assert fields["ad.video_id"]["control"] == "asset_picker"


def test_meta_nested_targeting_and_app_event_guidance_are_renderable():
    runtime = AdvertisingComposition(require_llm=False, offline_mode=True)
    runtime.register_tool_source(create_meta_tool_source())
    intent = ParsedIntent(
        "create_campaign", "创建 Meta 转化广告", ["meta"],
        scoped_parameters={"meta": {
            "objective": "OUTCOME_CONVERSIONS",
            "optimization_goal": "OFFSITE_CONVERSIONS",
        }},
    )
    card = runtime.build_creation_ui(intent)["cards"][0]
    targeting = next(item for item in card["fields"] if item["path"] == "ad_set.targeting")
    geo = targeting["object_properties"]["geo_locations"]
    assert geo["properties"]["regions"]["lookup_tool"] == "meta_search_targeting_options"
    assert geo["properties"]["regions"]["lookup_defaults"] == {"type": "adgeolocation"}
    promoted = next(item for item in card["fields"] if item["path"] == "ad_set.promoted_object")
    assert promoted["object_properties"]["application_id"]["manual_entry"]["source"] == "external_provider_identifier"
    assert promoted["object_properties"]["custom_event_type"]["enum"]
    assert promoted["object_properties"]["custom_event_str"]["manual_entry"]


def test_creation_contracts_expose_provider_resource_sources_and_fixed_placements():
    runtime = AdvertisingComposition(require_llm=False, offline_mode=True)
    runtime.register_tool_source(create_meta_tool_source())
    intent = ParsedIntent(
        "create_campaign", "创建 Meta 转化广告", ["meta"],
        scoped_parameters={"meta": {"objective": "OUTCOME_CONVERSIONS"}},
    )
    card = runtime.build_creation_ui(intent)["cards"][0]
    targeting = next(item for item in card["fields"] if item["path"] == "ad_set.targeting")
    properties = targeting["object_properties"]
    countries = properties["geo_locations"]["properties"]["countries"]
    assert countries["items"]["enum"]
    assert "US" in countries["items"]["enum"]
    assert "SG" in countries["items"]["enum"]
    assert "lookup_tool" not in countries
    assert properties["facebook_positions"]["items"]["enum"]
    assert properties["instagram_positions"]["items"]["enum"]

    link = runtime.list_creation_blueprints("meta", "link_conversion")[0]
    link_field = next(
        item for item in link["fields"] if item["path"] == "ad.image_hash"
    )
    assert link_field["lookup_tool"] == "meta_list_image_assets"


def test_provider_and_blueprint_visibility_conditions_are_deduplicated():
    runtime = AdvertisingComposition(require_llm=False, offline_mode=True)
    runtime.register_tool_source(create_meta_tool_source())
    intent = ParsedIntent(
        "create_campaign", "创建 Meta 转化广告", ["meta"],
        scoped_parameters={"meta": {"objective": "OUTCOME_CONVERSIONS"}},
    )
    card = runtime.build_creation_ui(intent)["cards"][0]
    visibility = next(
        item for item in card["fields"] if item["path"] == "campaign.daily_budget"
    )["visible_when"]
    assert visibility == {"not": {"field": "campaign.buying_type", "equals": "RESERVED"}}


def test_declared_resource_fields_inherit_provider_lookup_metadata():
    runtime = AdvertisingComposition(require_llm=False, offline_mode=True)
    runtime.register_tool_source(create_meta_tool_source())
    intent = ParsedIntent(
        "create_campaign", "创建 Meta 商品广告", ["meta"],
        scoped_parameters={"meta": {"objective": "PRODUCT_CATALOG_SALES"}},
    )
    card = runtime.build_creation_ui(intent)["cards"][0]
    fields = {item["path"]: item for item in card["fields"]}
    # These fields are explicitly listed in the Blueprint, but their lookup
    # source is owned by the Tool/Tool Source contract.
    assert fields["ad.page_id"]["control"] == "lookup"
    assert fields["ad.page_id"]["lookup"]["tool"] == "meta_list_pages"
    assert fields["ad.product_set_id"]["control"] == "lookup"


def test_creation_catalog_covers_provider_reference_sources_across_channels():
    google = AdvertisingComposition(require_llm=False, offline_mode=True)
    google.register_tool_source(create_google_tool_source())
    shopping = google.build_creation_ui(ParsedIntent(
        "create_campaign", "创建 Google Shopping 广告", ["google-ads"],
        scoped_parameters={"google-ads": {"ad_format": "SHOPPING"}},
    ))["cards"][0]
    shopping_fields = {item["path"]: item for item in shopping["fields"]}
    assert shopping_fields["product_group.parent_criterion_id"]["control"] == "lookup"

    tiktok = AdvertisingComposition(require_llm=False, offline_mode=True)
    tiktok.register_tool_source(create_tiktok_tool_source())
    lead = tiktok.build_creation_ui(ParsedIntent(
        "create_campaign", "创建 TikTok 线索广告", ["tiktok"],
        scoped_parameters={"tiktok": {"objective": "LEAD_GENERATION"}},
    ))["cards"][0]
    lead_fields = {item["path"]: item for item in lead["fields"]}
    assert lead_fields["ad.video_id"]["control"] == "asset_picker"
    assert lead_fields["ad.page_list"]["presentation"] == "advanced_json"

    sales = tiktok.build_creation_ui(ParsedIntent(
        "create_campaign", "创建 TikTok 商品广告", ["tiktok"],
        scoped_parameters={"tiktok": {"objective": "PRODUCT_SALES"}},
    ))["cards"][0]
    sales_fields = {item["path"]: item for item in sales["fields"]}
    assert sales_fields["ad.call_to_action_id"]["manual_entry"]["source"] == "external_provider_identifier"
    assert sales_fields["ad.identity_type"]["source"] == "enum"


def test_lookup_catalog_applies_provider_defaults_without_network_call():
    runtime = AdvertisingComposition(require_llm=False, offline_mode=True)
    runtime.register_tool_source(create_meta_tool_source())
    catalog = runtime.list_parameter_options(
        "meta", "targeting.geo_locations.regions", "meta_create_adset"
    )[0]
    assert catalog["lookup_tool"] == "meta_search_targeting_options"
    assert catalog["query_field"] == "query"
    assert catalog["lookup_defaults"] == {"type": "adgeolocation"}


def test_blueprint_submission_composes_declared_parent_child_tools():
    runtime = AdvertisingComposition(require_llm=False, offline_mode=True)
    runtime.register_tool_source(create_google_tool_source())
    intent = ParsedIntent(
        "create_search_ad", "按 Google Search 蓝图提交", ["google-ads"],
        scoped_parameters={"google-ads": {
            "campaign_name": "Search draft",
            "advertising_channel_type": "SEARCH",
                "bidding_strategy": "MAXIMIZE_CONVERSIONS",
                "daily_budget": 50,
                "contains_eu_political_advertising": "DOES_NOT_CONTAIN_EU_POLITICAL_ADVERTISING",
                "google_create_campaign": {
                "campaign_name": "Search draft",
                "advertising_channel_type": "SEARCH",
                    "bidding_strategy": "MAXIMIZE_CONVERSIONS",
                    "daily_budget": 50,
                    "contains_eu_political_advertising": "DOES_NOT_CONTAIN_EU_POLITICAL_ADVERTISING",
                },
            "google_create_ad_group": {
                "name": "Search group", "type": "SEARCH_STANDARD",
            },
            "google_create_search_ad": {
                "headlines": ["One", "Two", "Three"],
                "descriptions": ["Description one", "Description two"],
                "final_url": "https://example.com",
            },
        }},
    )
    plan, error = runtime._creation_blueprint_tool_plan(
        "google-ads.search", "1.0.0", intent
    )
    assert error is None
    assert [tool.name for tool in plan["google-ads"]] == [
        "google_create_campaign", "google_create_ad_group", "google_create_search_ad",
    ]
    card = runtime.build_creation_ui(intent)["cards"][0]
    assert card["ready"] is True
    assert card["missing_fields"] == []
    fields = {item["path"]: item for item in card["fields"]}
    assert fields["campaign.campaign_name"]["value"] == "Search draft"
    assert fields["ad_group.name"]["value"] == "Search group"


def test_incomplete_creation_returns_card_without_failed_tool_result():
    runtime = AdvertisingComposition(require_llm=False, offline_mode=True)
    runtime.register_tool_source(create_google_tool_source())

    result = runtime.run(
        "创建 Google App 广告",
        session_id="incomplete-creation",
        user_id="test-user",
    )

    assert result["results"] == []
    assert result["ui"]["needs_input"] is True
    assert result["response_source"] == "creation_card"
    assert result.get("workflow_id") is None
    assert "选择" in result["reply"]


def test_ambiguous_creation_asks_for_blueprint_choice_before_routing_tools():
    events = []
    runtime = AdvertisingComposition(require_llm=False, offline_mode=True)
    runtime.register_tool_source(create_tiktok_tool_source())

    result = runtime.run(
        "创建 TikTok 广告系列",
        session_id="ambiguous-tiktok-creation",
        user_id="test-user",
        event_callback=events.append,
    )

    assert result["results"] == []
    # A lightweight composition has no durable account/template context, so
    # the generic text clarification remains the appropriate surface.
    assert result["response_source"] == "creation_clarification"
    assert result["ui"]["cards"] == []
    assert result["ui"]["clarification"]["kind"] == "creation_clarification"
    assert {item["label"] for item in result["ui"]["clarification"]["options"]} >= {
        "流量", "应用推广", "潜在客户"
    }
    assert result["tool_plan"] == {}
    assert result["execution_plan"] == {}
    assert not any(
        event.get("type") == "plan" for event in events
    )
    assert not any(
        event.get("type") in {"node_started", "node_status", "confirmation"}
        for event in events
    )


def test_creation_follow_up_adopts_persisted_selector_and_then_shows_full_form():
    runtime = AdvertisingComposition(require_llm=False, offline_mode=True)
    runtime.register_tool_source(create_tiktok_tool_source())
    session_id = "follow-up-tiktok-creation"

    first = runtime.run(
        "创建 TikTok 广告系列", session_id=session_id, user_id="test-user"
    )
    second = runtime.run(
        "流量广告", session_id=session_id, user_id="test-user"
    )

    assert first["ui"]["cards"] == []
    assert second["intent"]["intent_type"] == "create_campaign"
    assert second["intent"]["namespaces"] == ["tiktok"]
    assert second["intent"]["scoped_parameters"]["tiktok"]["objective_type"] == "TRAFFIC"
    assert second["response_source"] == "creation_card"
    assert second["ui"]["cards"][0]["blueprint_id"] == "tiktok.traffic_video"
    assert second["tool_plan"] == {}
    assert second["execution_plan"] == {}


def test_incomplete_update_asks_for_resource_before_materializing_tool_plan():
    events = []
    runtime = AdvertisingComposition(require_llm=False, offline_mode=True)
    runtime.register_tool_source(create_meta_tool_source())

    result = runtime.run(
        "更新 Meta campaign 状态为暂停",
        session_id="incomplete-update",
        user_id="test-user",
        account_id="meta-test-account",
        event_callback=events.append,
    )

    assert result["response_source"] == "action_clarification"
    assert result["results"] == []
    assert result["tool_plan"] == {}
    assert result["execution_plan"] == {}
    assert result["workflow_id"] is None
    assert result["ui"]["clarification"]["kind"] == "action_clarification"
    assert any(item["path"] == "campaign_id" for item in result["ui"]["clarification"]["fields"])
    assert not any(event.get("type") == "plan" for event in events)
    assert not any(event.get("type") in {"node_started", "node_status", "confirmation"} for event in events)


def test_action_clarification_draft_survives_restart_and_merges_short_follow_up():
    from agents.ad_agent.persistence.store import AdAgentStore

    store = AdAgentStore(":memory:")
    validator = AccountWhitelistValidator.__new__(AccountWhitelistValidator)
    validator.allowed_accounts = {"meta": ["meta-test-account"]}
    runtime = AdvertisingComposition(
        require_llm=False,
        offline_mode=True,
        persistence_store=store,
        whitelist_validator=validator,
    )
    runtime.register_tool_source(create_meta_tool_source())
    first = runtime.run(
        "删除 Meta campaign",
        session_id="restart-action-draft",
        user_id="test-user",
        account_id="meta-test-account",
    )
    assert first["ui"]["clarification"]["kind"] == "action_clarification"

    restarted = AdvertisingComposition(
        require_llm=False,
        offline_mode=True,
        persistence_store=store,
        whitelist_validator=validator,
    )
    restarted.register_tool_source(create_meta_tool_source())
    second = restarted.run(
        "campaign_id=campaign-123",
        session_id="restart-action-draft",
        user_id="test-user",
        account_id="meta-test-account",
    )

    assert second["intent"]["intent_type"] == "delete_campaign"
    assert second["intent"]["scoped_parameters"]["meta"]["campaign_id"] == "campaign-123"
    assert second["response_source"] != "action_clarification"


def test_explicit_blueprint_submission_waits_for_required_fields_before_execution():
    validator = AccountWhitelistValidator.__new__(AccountWhitelistValidator)
    validator.allowed_accounts = {"google-ads": ["123"]}
    runtime = AdvertisingComposition(require_llm=False, whitelist_validator=validator)
    runtime.register_tool_source(create_google_tool_source())

    result = runtime.run(
        "创建 Google App campaign",
        account_id="123",
        platform_params={"google-ads": {"campaign_type": "APP"}},
        creation_blueprint_id="google-ads.app",
        creation_blueprint_version="1.0.0",
    )

    assert result["results"] == []
    assert result["workflow_id"] is None
    assert result["ui"]["needs_input"] is True
    assert result["response_source"] == "creation_card"


def test_creation_submission_validates_asset_minimums_before_any_tool_runs():
    validator = AccountWhitelistValidator.__new__(AccountWhitelistValidator)
    validator.allowed_accounts = {"google-ads": ["123"]}
    runtime = AdvertisingComposition(require_llm=False, whitelist_validator=validator)
    runtime.register_tool_source(create_google_tool_source())

    result = runtime.run(
        "创建 Google App 广告",
        session_id="creation-asset-preflight",
        user_id="test-user",
        account_id="123",
        platform_params={"google-ads": {
            "campaign_name": "App campaign",
            "campaign_type": "APP",
            "advertising_channel_type": "MULTI_CHANNEL",
            "advertising_channel_sub_type": "APP_CAMPAIGN",
            "app_campaign_setting": {
                "app_id": "com.example.app",
                "app_store": "GOOGLE_APP_STORE",
                "bidding_strategy_goal_type": "OPTIMIZE_INSTALLS_WITHOUT_TARGET_INSTALL_COST",
            },
            "bidding_strategy": "MAXIMIZE_CONVERSIONS",
            "daily_budget": 50,
            "google_create_campaign": {
                "campaign_name": "App campaign",
                "campaign_type": "APP",
                "advertising_channel_type": "MULTI_CHANNEL",
                "advertising_channel_sub_type": "APP_CAMPAIGN",
                "app_campaign_setting": {
                    "app_id": "com.example.app",
                    "app_store": "GOOGLE_APP_STORE",
                    "bidding_strategy_goal_type": "OPTIMIZE_INSTALLS_WITHOUT_TARGET_INSTALL_COST",
                },
                "bidding_strategy": "MAXIMIZE_CONVERSIONS",
                "daily_budget": 50,
                "contains_eu_political_advertising": "DOES_NOT_CONTAIN_EU_POLITICAL_ADVERTISING",
            },
                "google_create_app_ad_group": {
                    "name": "App group",
                },
            "google_create_app_ad": {
                "name": "App ad",
                "headlines": ["Only one headline"],
                "descriptions": ["Only one description"],
            },
        }},
        creation_blueprint_id="google-ads.app",
        creation_blueprint_version="1.0.0",
    )

    assert result["results"] == []
    assert result["workflow_id"] is None
    assert result["response_source"] == "creation_validation"
    assert "标题素材（每行一条）至少需要 2 项" in result["reply"]
    assert "描述素材（每行一条）至少需要 2 项" in result["reply"]
    assert result["creation_validation"]["status"] == "blocked"


def test_creation_cards_expose_account_boundary_and_friendly_asset_controls():
    runtime = AdvertisingComposition(require_llm=False, offline_mode=True)
    runtime.register_tool_source(create_google_tool_source())
    intent = ParsedIntent(
        "create_campaign", "创建 Google App 广告", ["google-ads"],
        campaign_type="APP", scoped_parameters={"google-ads": {"campaign_type": "APP"}},
    )
    card = runtime.build_creation_ui(intent)["cards"][0]
    assert card["account_required"] is True
    fields = {item["path"]: item for item in card["fields"]}
    assert fields["campaign.campaign_type"]["control"] == "derived_readonly"
    assert fields["ad.headlines"]["control"] == "text_list"
    assert fields["ad.images"]["control"] == "asset_picker"
    assert fields["campaign.app_campaign_setting"]["control"] == "object_editor"
    assert "object_properties" in fields["campaign.app_campaign_setting"]


def test_creation_cards_publish_outer_shape_for_advanced_provider_payloads():
    tool_registry = SimpleToolRegistry()
    tool_registry.register(
        ToolDefinition(
            name="test_create_payload",
            skill="test",
            namespace="test",
            description="test payload",
            input_schema=ToolSchema(
                properties={
                    "object_payload": {"type": "object", "presentation": "advanced_json"},
                    "array_payload": {"type": "array", "presentation": "advanced_json"},
                },
                required=["object_payload", "array_payload"],
            ),
            action="create",
            resource_type="test_payload",
            intent_types=["create_test_payload"],
        ),
        lambda _context, _data: None,
    )
    blueprint_registry = BlueprintRegistry()
    blueprint_registry.register(
        AdCreationBlueprint.from_dict({
            "id": "test.payload",
            "version": "1.0.0",
            "provider": "test",
            "ad_format": "PAYLOAD",
            "title": "测试高级 Payload",
            "tools": ["test_create_payload"],
            "fields": [
                {
                    "path": "payload.object",
                    "tool_ref": "test_create_payload.object_payload",
                    "required": True,
                },
                {
                    "path": "payload.array",
                    "tool_ref": "test_create_payload.array_payload",
                    "required": True,
                },
            ],
        }),
        tool_registry=tool_registry,
    )
    card = CreationCardBuilder(blueprint_registry, tool_registry).build(
        ParsedIntent("create_test_payload", "测试高级 Payload", ["test"])
    )[0]
    fields = {item["path"]: item for item in card["fields"]}
    assert fields["payload.object"]["control"] == "advanced_json"
    assert fields["payload.object"]["json_shape"] == "object"
    assert fields["payload.array"]["control"] == "advanced_json"
    assert fields["payload.array"]["json_shape"] == "array"


def test_google_app_nested_dynamic_field_exposes_lookup_metadata():
    runtime = AdvertisingComposition(require_llm=False, offline_mode=True)
    runtime.register_tool_source(create_google_tool_source())
    intent = ParsedIntent(
        "create_campaign", "创建 Google App Engagement 广告", ["google-ads"],
        campaign_type="APP", scoped_parameters={"google-ads": {"campaign_type": "APP"}},
    )

    card = runtime.build_creation_ui(intent)["cards"][0]
    settings = next(
        field for field in card["fields"]
        if field["path"] == "campaign.app_campaign_setting"
    )
    selective = settings["object_properties"]["selective_optimization"]
    assert selective["lookup_tool"] == "google_list_conversion_actions"
    assert selective["type"] == "array"

    catalog = runtime.list_parameter_options(
        "google-ads", "app_campaign_setting.selective_optimization",
        "google_create_campaign",
    )
    assert catalog[0]["source"] == "lookup"
    assert catalog[0]["lookup_tool"] == "google_list_conversion_actions"

    app_store = runtime.list_parameter_options(
        "google-ads", "app_campaign_setting.app_store", "google_create_campaign"
    )
    assert {item["value"]: item["label"] for item in app_store[0]["options"]} == {
        "GOOGLE_APP_STORE": "Google Play",
        "APPLE_APP_STORE": "Apple App Store",
    }


def test_nested_creation_assets_keep_provider_sources_and_controls():
    runtime = AdvertisingComposition(require_llm=False, offline_mode=True)
    runtime.register_tool_source(create_google_tool_source())
    intent = ParsedIntent(
        "create_campaign", "创建 Google Demand Gen 轮播广告", ["google-ads"],
        campaign_type="DEMAND_GEN",
        scoped_parameters={"google-ads": {"campaign_type": "DEMAND_GEN"}},
    )
    card = runtime.build_creation_ui(intent)["cards"][0]
    fields = {item["path"]: item for item in card["fields"]}
    carousel = fields["ad.carousel_cards"]
    assert carousel["object_shape"] == "array"
    assert carousel["object_max_items"] == 10
    card_props = carousel["object_properties"]
    assert card_props["marketing_image_asset"]["lookup_tool"] == "google_list_assets"
    assert card_props["marketing_image_asset"]["presentation"] == "asset_picker"

    runtime = AdvertisingComposition(require_llm=False, offline_mode=True)
    runtime.register_tool_source(create_tiktok_tool_source())
    tiktok_intent = ParsedIntent(
        "create_campaign", "创建 TikTok 视频广告", ["tiktok"],
        campaign_type="TRAFFIC",
        scoped_parameters={"tiktok": {"objective_type": "TRAFFIC"}},
    )
    tiktok_card = runtime.build_creation_ui(tiktok_intent)["cards"][0]
    tiktok_fields = {item["path"]: item for item in tiktok_card["fields"]}
    item = tiktok_fields["ad.tiktok_item_id"]
    assert item["tool"] == "tiktok_smart_plus_create_ad"
    assert tiktok_fields["ad.identity_id"]["lookup"]["tool"] == "tiktok_list_identities"


def test_cascade_hides_and_requires_app_fields_for_app_objective():
    blueprint = load_blueprint_file(BLUEPRINT_PATH)
    result = BlueprintCascadeEngine().evaluate(
        blueprint,
        {
            "campaign.objective_type": "APP_PROMOTION",
            "ad_group.promotion_type": "APP_ANDROID",
            "ad_group.optimization_goal": "INSTALL",
        },
    )
    states = {item["path"]: item for item in result["fields"]}

    assert states["campaign.app_promotion_type"]["visible"] is True
    assert states["campaign.app_promotion_type"]["required"] is True
    assert states["ad_group.app_id"]["required"] is True
    assert states["ad_group.optimization_event"]["required"] is False
    assert "campaign.app_promotion_type" in result["missing_fields"]


def test_creation_ui_builds_tiktok_app_card_from_registered_blueprint():
    runtime = AdvertisingComposition(require_llm=False, offline_mode=True)
    runtime.register_tool_source(create_tiktok_tool_source())
    intent = ParsedIntent(
        "create_campaign",
        "创建 TikTok App 转化广告，投放给 18 到 35 岁用户",
        ["tiktok"],
        scoped_parameters={
            "tiktok": {
                "objective_type": "APP_PROMOTION",
                "promotion_type": "APP_ANDROID",
                "age_groups": ["AGE_18_24", "AGE_25_34"],
            }
        },
    )

    ui = runtime.build_creation_ui(intent)
    card = ui["cards"][0]
    fields = {item["path"]: item for item in card["fields"]}

    assert card["type"] == "ad_creation_form"
    assert card["blueprint_id"] == "tiktok.app_conversion_video"
    assert fields["campaign.objective_type"]["value"] == "APP_PROMOTION"
    assert fields["ad_group.age_groups"]["value"] == ["AGE_18_24", "AGE_25_34"]
    assert fields["ad_group.app_id"]["lookup"]["tool"] == "tiktok_list_apps"
    assert fields["ad_group.optimization_event"]["manual_entry"]["source"] == (
        "provider_conversion_event"
    )
    assert fields["ad_group.optimization_goal"]["options"] == [
        {"value": "INSTALL", "label": "INSTALL"},
        {"value": "IN_APP_EVENT", "label": "IN_APP_EVENT"},
        {"value": "VALUE", "label": "VALUE"},
    ]
    assert ui["needs_input"] is True


def test_creation_ui_returns_selector_card_when_creation_dimension_is_ambiguous():
    runtime = AdvertisingComposition(require_llm=False, offline_mode=True)
    runtime.register_tool_source(create_tiktok_tool_source())
    intent = ParsedIntent(
        "create_campaign", "创建 TikTok 广告", ["tiktok"], objective="sales"
    )
    card = runtime.build_creation_ui(intent)["cards"][0]
    assert card["type"] == "ad_creation_form"
    assert card["blueprint_id"] == "tiktok.product_sales_video"


def test_creation_selector_publishes_scoped_accounts_and_templates():
    from agents.ad_agent.persistence.store import AdAgentStore

    runtime = AdvertisingComposition(
        require_llm=False,
        offline_mode=True,
        persistence_store=AdAgentStore(":memory:"),
    )
    runtime.whitelist_validator.allowed_accounts = {
        "tiktok": ["7397068114548195329"],
    }
    runtime.register_tool_source(create_tiktok_tool_source())

    card = runtime.build_creation_ui(ParsedIntent(
        "create_campaign", "创建 TikTok 广告", ["tiktok"],
    ))["cards"][0]

    assert card["type"] == "ad_creation_selector"
    assert card["account_required"] is True
    assert card["account_options"] == [{
        "value": "7397068114548195329",
        "label": "账户 7397068114548195329",
    }]
    assert len(card["template_options"]) == 4
    assert {
        item["account_id"] for item in card["template_options"]
    } == {"7397068114548195329"}
    assert all(item["source"] == "builtin" for item in card["template_options"])


def test_creation_form_keeps_selected_account_and_only_matching_templates():
    from agents.ad_agent.persistence.store import AdAgentStore

    runtime = AdvertisingComposition(
        require_llm=False,
        offline_mode=True,
        persistence_store=AdAgentStore(":memory:"),
    )
    runtime.whitelist_validator.allowed_accounts = {
        "tiktok": ["7397068114548195329"],
    }
    runtime.register_tool_source(create_tiktok_tool_source())

    card = runtime.build_creation_ui(ParsedIntent(
        "create_campaign", "创建 TikTok 流量广告", ["tiktok"],
        scoped_parameters={
            "tiktok": {
                "account_id": "7397068114548195329",
                "objective_type": "TRAFFIC",
            },
        },
    ))["cards"][0]

    assert card["type"] == "ad_creation_form"
    assert card["account_id"] == "7397068114548195329"
    assert {
        item["blueprint_id"] for item in card["template_options"]
    } == {"tiktok.traffic_video"}


def test_creation_catalog_unifies_ad_types_required_inputs_and_account_templates():
    from agents.ad_agent.persistence.store import AdAgentStore

    runtime = AdvertisingComposition(
        require_llm=False,
        offline_mode=True,
        persistence_store=AdAgentStore(":memory:"),
    )
    runtime.whitelist_validator.allowed_accounts = {
        "tiktok": ["7397068114548195329"],
    }
    runtime.register_tool_source(create_tiktok_tool_source())

    catalog = runtime.list_creation_catalog(
        provider="tiktok",
        account_id="7397068114548195329",
        account_scope={"tiktok": ["7397068114548195329"]},
        tenant_id="tenant-a",
        user_id="user-a",
    )

    traffic = next(
        item for item in catalog["ad_types"]
        if item["blueprint_id"] == "tiktok.traffic_video"
    )
    assert traffic["provider"] == "tiktok"
    assert traffic["ad_format"] == "SINGLE_VIDEO"
    assert traffic["required_inputs"]
    assert all(
        set(item) >= {"path", "label", "required"}
        for item in traffic["required_inputs"]
    )
    assert traffic["template_options"]
    assert all(
        item["account_id"] == "7397068114548195329"
        for item in traffic["template_options"]
    )
    assert all(
        "missing_input_count" in item
        and "recommendation_score" in item
        for item in traffic["template_options"]
    )


def test_creation_run_gates_known_type_on_account_before_showing_full_form():
    from agents.ad_agent.persistence.store import AdAgentStore

    runtime = AdvertisingComposition(
        require_llm=False,
        offline_mode=True,
        persistence_store=AdAgentStore(":memory:"),
    )
    runtime.whitelist_validator.allowed_accounts = {
        "tiktok": ["7397068114548195329"],
    }
    runtime.register_tool_source(create_tiktok_tool_source())

    result = runtime.run(
        "创建 TikTok 流量广告",
        session_id="account-first-creation",
        user_id="template-user",
    )

    card = result["ui"]["cards"][0]
    assert result["response_source"] == "creation_card"
    assert card["type"] == "ad_creation_selector"
    assert card["blueprint_id"] == "tiktok.traffic_video"
    assert card["account_id"] is None
    assert card["template_options"]


def test_creation_card_ui_survives_durable_conversation_reload():
    from agents.ad_agent.persistence.store import AdAgentStore

    runtime = AdvertisingComposition(
        require_llm=False,
        offline_mode=True,
        persistence_store=AdAgentStore(":memory:"),
    )
    runtime.whitelist_validator.allowed_accounts = {
        "tiktok": ["7397068114548195329"],
    }
    runtime.register_tool_source(create_tiktok_tool_source())

    result = runtime.run(
        "创建 TikTok 流量广告",
        session_id="durable-card-history",
        user_id="history-user",
    )

    assert result["ui"]["cards"]
    conversation = runtime.get_conversation(
        "durable-card-history",
        "history-user",
    )
    assert conversation is not None
    assistant_messages = [
        message for message in conversation["messages"]
        if message["role"] == "assistant"
    ]
    assert assistant_messages
    assert assistant_messages[-1]["ui"] == result["ui"]
    records = runtime._session_manager.list_conversation_messages(
        "durable-card-history",
        limit=20,
    )
    persisted_assistant = [
        record for record in records if record.role == "assistant"
    ]
    assert persisted_assistant[-1].metadata["ui"] == result["ui"]


def test_template_selection_is_applied_to_creation_draft_without_execution():
    from agents.ad_agent.persistence.store import AdAgentStore

    runtime = AdvertisingComposition(
        require_llm=False,
        offline_mode=True,
        persistence_store=AdAgentStore(":memory:"),
    )
    runtime.whitelist_validator.allowed_accounts = {
        "tiktok": ["7397068114548195329"],
    }
    runtime.register_tool_source(create_tiktok_tool_source())
    template = next(
        item for item in runtime.list_creation_templates(
            provider="tiktok",
            account_id="7397068114548195329",
            user_id="template-user",
            tenant_id="default",
        )
        if item["blueprint_id"] == "tiktok.traffic_video"
    )

    intent = runtime.apply_creation_template_to_intent(
        ParsedIntent("chat", "使用模板", ["tiktok"]),
        template["template_id"],
        account_id="7397068114548195329",
        user_id="template-user",
        tenant_id="default",
    )

    assert intent.intent_type == "create_campaign"
    assert intent.namespaces == ["tiktok"]
    assert intent.scoped_parameters["tiktok"]["campaign.objective_type"] == "TRAFFIC"
    assert intent.metadata["creation_template_id"] == template["template_id"]
    assert intent.metadata["creation_blueprint_id"] == "tiktok.traffic_video"

    result = runtime.run(
        "使用模板",
        session_id="template-selection-run",
        user_id="template-user",
        account_id="7397068114548195329",
        creation_template_id=template["template_id"],
    )
    selected_card = result["ui"]["cards"][0]
    assert result["results"] == []
    assert selected_card["type"] == "ad_creation_form"
    assert selected_card["blueprint_id"] == "tiktok.traffic_video"
    assert selected_card["account_id"] == "7397068114548195329"


def test_blueprint_tool_ref_supports_nested_schema_paths():
    blueprint = AdCreationBlueprint.from_dict({
        "id": "test.nested",
        "version": "1.0.0",
        "provider": "test",
        "ad_format": "video",
        "tools": ["test_create"],
        "fields": [{
            "path": "ad_group.targeting.age_groups",
            "tool_ref": "test_create.targeting.age_groups",
            "required": True,
            "source": "enum",
            "options": ["AGE_18_24"],
        }],
    })
    from agents.ad_agent.core.tool_registry import SimpleToolRegistry

    registry = SimpleToolRegistry()
    registry.register(
        ToolDefinition(
            name="test_create", skill="test", namespace="test",
            description="test", action="create", resource_type="ad_group",
            intent_types=["create_campaign"], effect_class=ToolEffect.WRITE,
            input_schema=ToolSchema(properties={
                "targeting": {
                    "type": "object",
                    "properties": {
                        "age_groups": {
                            "type": "array",
                            "items": {"type": "string", "enum": ["AGE_18_24"]},
                        }
                    },
                }
            }),
        ),
        lambda _ctx, _input: None,
    )
    from agents.ad_agent.domain.ad.blueprint import validate_blueprint_against_tools

    validate_blueprint_against_tools(blueprint, registry)


def test_parent_change_reports_downstream_reset_without_mutating_values():
    blueprint = load_blueprint_file(BLUEPRINT_PATH)
    values = {
        "campaign.objective_type": "TRAFFIC",
        "ad_group.promotion_type": "WEBSITE",
        "ad_group.app_id": "app-old",
        "ad_group.optimization_goal": "CLICK",
    }
    result = BlueprintCascadeEngine().evaluate(
        blueprint,
        values,
        previous_values={"campaign.objective_type": "APP_PROMOTION"},
    )

    assert "campaign.objective_type" in result["changed_fields"]
    assert "ad_group.app_id" in result["reset_fields"]
    assert values["ad_group.app_id"] == "app-old"


def test_blueprint_registry_rejects_executable_configuration():
    with pytest.raises(BlueprintValidationError, match="not allowed"):
        AdCreationBlueprint.from_dict({
            "id": "unsafe.blueprint",
            "version": "1.0.0",
            "provider": "test",
            "ad_format": "video",
            "tools": ["test_create"],
            "fields": [{
                "path": "campaign.name",
                "tool_ref": "test_create.name",
                "script": "do_anything()",
            }],
        })


def test_blueprint_registry_versions_are_immutable():
    first = AdCreationBlueprint.from_dict({
        "id": "test.video",
        "version": "1.0.0",
        "provider": "test",
        "ad_format": "video",
        "tools": ["test_create"],
        "fields": [{"path": "campaign.name", "tool_ref": "test_create.name"}],
    })
    second = AdCreationBlueprint.from_dict({
        "id": "test.video",
        "version": "1.0.0",
        "provider": "test",
        "ad_format": "video",
        "tools": ["test_create"],
        "fields": [{"path": "campaign.title", "tool_ref": "test_create.name"}],
    })
    registry = BlueprintRegistry()
    registry.register(first)
    with pytest.raises(BlueprintValidationError, match="conflicting blueprint version"):
        registry.register(second)
