"""Tests for declarative creation blueprints and cascade behavior."""

from pathlib import Path

import pytest

from agents.ad_agent.capabilities.tiktok import create_tiktok_capability
from agents.ad_agent.capabilities.meta import create_meta_capability
from agents.ad_agent.capabilities.google import create_google_capability
from agents.ad_agent.core.blueprint import (
    AdCreationBlueprint,
    BlueprintCascadeEngine,
    BlueprintRegistry,
    BlueprintValidationError,
    load_blueprint_file,
)
from agents.ad_agent.core.creation_card import CreationCardBuilder
from agents.ad_agent.core.interfaces import ParsedIntent, ToolDefinition, ToolSchema, ToolEffect
from agents.ad_agent.core.tool_registry import SimpleToolRegistry
from agents.ad_agent.runtime.account_policy import AccountWhitelistValidator
from agents.ad_agent.runtime.runtime import AgentRuntime


BLUEPRINT_PATH = Path(__file__).parents[1] / "capabilities" / "tiktok" / "blueprints" / "app_conversion_video.v1.json"


def test_tiktok_blueprint_is_json_and_references_registered_tools():
    runtime = AgentRuntime(require_llm=False, offline_mode=True)
    runtime.register_capability(create_tiktok_capability())

    items = runtime.list_creation_blueprints("tiktok", "SINGLE_VIDEO")
    assert {item["id"] for item in items} == {
        "tiktok.app_conversion_video",
        "tiktok.lead_generation",
        "tiktok.product_sales_video",
        "tiktok.traffic_video",
    }
    assert all(item["selector"]["dimension"] == "objective" for item in items)
    assert items[0]["version"] == "1.0.0"
    assert runtime.creation_blueprints.get("tiktok.app_conversion_video") is not None


def test_blueprint_registry_resolves_each_provider_entry_dimension_without_router_branches():
    runtime = AgentRuntime(require_llm=False, offline_mode=True)
    for factory in (create_meta_capability, create_tiktok_capability, create_google_capability):
        runtime.register_capability(factory())

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
    runtime = AgentRuntime(require_llm=False, offline_mode=True)
    runtime.register_capability(create_google_capability())

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
            platform_params={"google-ads": {"campaign_type": "DEMAND_GEN"}},
        ))["cards"][0]
        assert card["blueprint_id"] == expected


def test_demand_gen_without_variant_returns_specific_blueprint_choices():
    runtime = AgentRuntime(require_llm=False, offline_mode=True)
    runtime.register_capability(create_google_capability())
    card = runtime.build_creation_ui(ParsedIntent(
        "create_campaign", "创建 Google Demand Gen 广告", ["google-ads"],
        campaign_type="DEMAND_GEN",
        platform_params={"google-ads": {"campaign_type": "DEMAND_GEN"}},
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
        / "capabilities"
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
        ("meta.conversion_link", create_meta_capability, "meta"),
        ("google-ads.search", create_google_capability, "google-ads"),
    ):
        runtime = AgentRuntime(require_llm=False, offline_mode=True)
        runtime.register_capability(factory())
        blueprint = runtime.creation_blueprints.get(blueprint_id)
        assert blueprint is not None
        assert blueprint.provider == provider
        assert all(
            field["tool_ref"].split(".", 1)[0] in blueprint.tools
            for field in blueprint.fields
        )


def test_google_bidding_strategy_cascade_requires_only_matching_target():
    runtime = AgentRuntime(require_llm=False, offline_mode=True)
    runtime.register_capability(create_google_capability())
    result = runtime.evaluate_creation_blueprint(
        "google-ads.search",
        {"campaign.bidding_strategy": "TARGET_CPA"},
    )
    states = {item["path"]: item for item in result["fields"]}
    assert states["campaign.target_cpa_micros"]["required"] is True
    assert states["campaign.target_roas"]["visible"] is False
    assert "campaign.target_cpa_micros" in result["missing_fields"]


def test_meta_objective_cascade_resolves_optimization_and_billing_options():
    runtime = AgentRuntime(require_llm=False, offline_mode=True)
    runtime.register_capability(create_meta_capability())

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
    runtime = AgentRuntime(require_llm=False, offline_mode=True)
    runtime.register_capability(create_meta_capability())
    intent = ParsedIntent(
        "create_campaign", "创建 Meta 潜在客户广告", ["meta"],
        platform_params={"meta": {"objective": "OUTCOME_LEADS"}},
    )
    card = runtime.build_creation_ui(intent)["cards"][0]
    page = next(item for item in card["fields"] if item["path"] == "ad.page_id")
    assert page["lookup"]["tool"] == "meta_list_pages"

    conversion_intent = ParsedIntent(
        "create_campaign", "创建 Meta 转化广告", ["meta"],
        platform_params={"meta": {
            "objective": "OUTCOME_CONVERSIONS",
            "optimization_goal": "OFFSITE_CONVERSIONS",
        }},
    )
    conversion_card = runtime.build_creation_ui(conversion_intent)["cards"][0]
    promoted = next(item for item in conversion_card["fields"] if item["path"] == "ad_set.promoted_object")
    assert promoted["object_properties"]["pixel_id"]["lookup_tool"] == "meta_list_pixels"


def test_tiktok_cascade_filters_app_options_and_clears_incompatible_value():
    runtime = AgentRuntime(require_llm=False, offline_mode=True)
    runtime.register_capability(create_tiktok_capability())
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
        "INSTALL", "IN_APP_EVENT", "CONVERSION"
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
    assert ios_states["ad.operating_systems"]["options"] == ["IOS"]


def test_google_search_blueprint_exposes_format_specific_bidding_catalog():
    runtime = AgentRuntime(require_llm=False, offline_mode=True)
    runtime.register_capability(create_google_capability())
    blueprint = runtime.creation_blueprints.get("google-ads.search")
    assert blueprint is not None
    field = next(item for item in blueprint.fields if item["path"] == "campaign.bidding_strategy")
    assert field["options"] == [
        "MANUAL_CPC", "MAXIMIZE_CLICKS", "MAXIMIZE_CONVERSIONS",
        "TARGET_CPA", "TARGET_ROAS", "TARGET_IMPRESSION_SHARE",
    ]
    assert field["option_labels"]["MAXIMIZE_CLICKS"] == "最大化点击次数"


def test_google_entry_type_is_not_repeated_at_ad_group_level():
    runtime = AgentRuntime(require_llm=False, offline_mode=True)
    runtime.register_capability(create_google_capability())
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
    runtime = AgentRuntime(require_llm=False, offline_mode=True)
    runtime.register_capability(create_google_capability())
    card = runtime.build_creation_ui(ParsedIntent(
        "create_campaign", "创建 Google Search 广告", ["google-ads"],
        platform_params={"google-ads": {"ad_format": "SEARCH"}},
    ))["cards"][0]
    fields = {item["path"]: item for item in card["fields"]}

    assert fields["ad.headlines"]["visible"] is True
    assert fields["ad.descriptions"]["visible"] is True
    assert fields["campaign.shopping_setting"]["visible"] is False
    assert fields["campaign.app_campaign_setting"]["visible"] is False
    assert fields["campaign.target_cpa_micros"]["visible"] is False


def test_provider_applicability_switches_tiktok_asset_controls_by_selected_format():
    runtime = AgentRuntime(require_llm=False, offline_mode=True)
    runtime.register_capability(create_tiktok_capability())
    card = runtime.build_creation_ui(ParsedIntent(
        "create_campaign", "创建 TikTok 商品视频广告", ["tiktok"],
        platform_params={"tiktok": {
            "objective": "PRODUCT_SALES", "ad_format": "SINGLE_VIDEO",
        }},
    ))["cards"][0]
    fields = {item["path"]: item for item in card["fields"]}

    assert fields["ad.video_id"]["visible"] is True
    assert fields["ad.video_id"]["control"] == "lookup"
    assert fields["ad.image_ids"]["visible"] is False
    assert fields["ad.spark_post_id"]["visible"] is False


def test_all_google_blueprints_make_ad_group_type_provider_derived():
    runtime = AgentRuntime(require_llm=False, offline_mode=True)
    runtime.register_capability(create_google_capability())
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
    runtime = AgentRuntime(require_llm=False, offline_mode=True)
    runtime.register_capability(create_google_capability())
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
            platform_params={"google-ads": {"ad_format": blueprint.ad_format}},
        ))["cards"][0]
        type_field = next(item for item in card["fields"] if item["path"] == "ad_group.type")
        assert type_field["control"] == "derived_readonly"
        assert type_field["options"] == [{"value": "SEARCH_STANDARD", "label": "SEARCH_STANDARD"}]


def test_google_video_ad_group_type_is_derived_from_video_format():
    blueprint = load_blueprint_file(
        Path(__file__).parents[1]
        / "capabilities"
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
    runtime = AgentRuntime(require_llm=False, offline_mode=True)
    runtime.register_capability(create_google_capability())
    intent = ParsedIntent(
        "create_campaign", "创建 Google Search 广告", ["google-ads"],
        campaign_type="SEARCH",
        platform_params={"google-ads": {"campaign_type": "SEARCH"}},
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
    runtime = AgentRuntime(require_llm=False, offline_mode=True)
    runtime.register_capability(create_tiktok_capability())
    intent = ParsedIntent(
        "create_campaign", "创建 TikTok 商品销售广告", ["tiktok"],
        platform_params={"tiktok": {"objective": "PRODUCT_SALES"}},
    )
    card = runtime.build_creation_ui(intent)["cards"][0]
    fields = {item["path"]: item for item in card["fields"]}
    assert len(card["fields"]) > 80
    assert fields["ad_group.audience_ids"]["control"] == "lookup"
    assert fields["ad_group.audience_ids"]["lookup"]["tool"] == "tiktok_list_audiences"
    assert fields["ad_group.device_price_ranges"]["control"] == "json"


def test_meta_nested_targeting_and_app_event_guidance_are_renderable():
    runtime = AgentRuntime(require_llm=False, offline_mode=True)
    runtime.register_capability(create_meta_capability())
    intent = ParsedIntent(
        "create_campaign", "创建 Meta 转化广告", ["meta"],
        platform_params={"meta": {
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
    runtime = AgentRuntime(require_llm=False, offline_mode=True)
    runtime.register_capability(create_meta_capability())
    intent = ParsedIntent(
        "create_campaign", "创建 Meta 转化广告", ["meta"],
        platform_params={"meta": {"objective": "OUTCOME_CONVERSIONS"}},
    )
    card = runtime.build_creation_ui(intent)["cards"][0]
    targeting = next(item for item in card["fields"] if item["path"] == "ad_set.targeting")
    properties = targeting["object_properties"]
    assert properties["geo_locations"]["properties"]["countries"]["lookup_tool"] == (
        "meta_search_targeting_options"
    )
    assert properties["facebook_positions"]["items"]["enum"]
    assert properties["instagram_positions"]["items"]["enum"]

    link = runtime.list_creation_blueprints("meta", "link_conversion")[0]
    link_field = next(
        item for item in link["fields"] if item["path"] == "ad.image_hash"
    )
    assert link_field["lookup_tool"] == "meta_list_image_assets"


def test_provider_and_blueprint_visibility_conditions_are_deduplicated():
    runtime = AgentRuntime(require_llm=False, offline_mode=True)
    runtime.register_capability(create_meta_capability())
    intent = ParsedIntent(
        "create_campaign", "创建 Meta 转化广告", ["meta"],
        platform_params={"meta": {"objective": "OUTCOME_CONVERSIONS"}},
    )
    card = runtime.build_creation_ui(intent)["cards"][0]
    visibility = next(
        item for item in card["fields"] if item["path"] == "campaign.daily_budget"
    )["visible_when"]
    assert visibility == {"not": {"field": "campaign.buying_type", "equals": "RESERVED"}}


def test_declared_resource_fields_inherit_provider_lookup_metadata():
    runtime = AgentRuntime(require_llm=False, offline_mode=True)
    runtime.register_capability(create_meta_capability())
    intent = ParsedIntent(
        "create_campaign", "创建 Meta 商品广告", ["meta"],
        platform_params={"meta": {"objective": "PRODUCT_CATALOG_SALES"}},
    )
    card = runtime.build_creation_ui(intent)["cards"][0]
    fields = {item["path"]: item for item in card["fields"]}
    # These fields are explicitly listed in the Blueprint, but their lookup
    # source is owned by the Tool/Capability contract.
    assert fields["ad.page_id"]["control"] == "lookup"
    assert fields["ad.page_id"]["lookup"]["tool"] == "meta_list_pages"
    assert fields["ad.product_set_id"]["control"] == "lookup"


def test_creation_catalog_covers_provider_reference_sources_across_channels():
    google = AgentRuntime(require_llm=False, offline_mode=True)
    google.register_capability(create_google_capability())
    shopping = google.build_creation_ui(ParsedIntent(
        "create_campaign", "创建 Google Shopping 广告", ["google-ads"],
        platform_params={"google-ads": {"ad_format": "SHOPPING"}},
    ))["cards"][0]
    shopping_fields = {item["path"]: item for item in shopping["fields"]}
    assert shopping_fields["product_group.parent_criterion_id"]["control"] == "lookup"

    tiktok = AgentRuntime(require_llm=False, offline_mode=True)
    tiktok.register_capability(create_tiktok_capability())
    lead = tiktok.build_creation_ui(ParsedIntent(
        "create_campaign", "创建 TikTok 线索广告", ["tiktok"],
        platform_params={"tiktok": {"objective": "LEAD_GENERATION"}},
    ))["cards"][0]
    lead_fields = {item["path"]: item for item in lead["fields"]}
    assert lead_fields["ad.tracking_pixel_id"]["control"] == "lookup"

    sales = tiktok.build_creation_ui(ParsedIntent(
        "create_campaign", "创建 TikTok 商品广告", ["tiktok"],
        platform_params={"tiktok": {"objective": "PRODUCT_SALES"}},
    ))["cards"][0]
    sales_fields = {item["path"]: item for item in sales["fields"]}
    assert sales_fields["ad.call_to_action_id"]["manual_entry"]["source"] == "external_provider_identifier"
    assert sales_fields["ad.identity_type"]["source"] == "enum"


def test_lookup_catalog_applies_provider_defaults_without_network_call():
    runtime = AgentRuntime(require_llm=False, offline_mode=True)
    runtime.register_capability(create_meta_capability())
    catalog = runtime.list_parameter_options(
        "meta", "targeting.geo_locations.regions", "meta_create_adset"
    )[0]
    assert catalog["lookup_tool"] == "meta_search_targeting_options"
    assert catalog["query_field"] == "query"
    assert catalog["lookup_defaults"] == {"type": "adgeolocation"}


def test_blueprint_submission_composes_declared_parent_child_tools():
    runtime = AgentRuntime(require_llm=False, offline_mode=True)
    runtime.register_capability(create_google_capability())
    intent = ParsedIntent(
        "create_search_ad", "按 Google Search 蓝图提交", ["google-ads"],
        platform_params={"google-ads": {
            "campaign_name": "Search draft",
            "advertising_channel_type": "SEARCH",
            "bidding_strategy": "MAXIMIZE_CONVERSIONS",
            "daily_budget": 50,
            "google_create_campaign": {
                "campaign_name": "Search draft",
                "advertising_channel_type": "SEARCH",
                "bidding_strategy": "MAXIMIZE_CONVERSIONS",
                "daily_budget": 50,
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
    runtime = AgentRuntime(require_llm=False, offline_mode=True)
    runtime.register_capability(create_google_capability())

    result = runtime.run(
        "创建 Google App 广告",
        session_id="incomplete-creation",
        user_id="test-user",
    )

    assert result["results"] == []
    assert result["ui"]["needs_input"] is True
    assert result["response_source"] == "creation_card"
    assert result.get("workflow_id") is None
    assert "请提供要操作的" in result["reply"]


def test_explicit_blueprint_submission_waits_for_required_fields_before_execution():
    validator = AccountWhitelistValidator.__new__(AccountWhitelistValidator)
    validator.allowed_accounts = {"google-ads": ["123"]}
    runtime = AgentRuntime(require_llm=False, whitelist_validator=validator)
    runtime.register_capability(create_google_capability())

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
    runtime = AgentRuntime(require_llm=False, whitelist_validator=validator)
    runtime.register_capability(create_google_capability())

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
                },
                "bidding_strategy": "MAXIMIZE_CONVERSIONS",
                "daily_budget": 50,
            },
            "google_create_app_ad_group": {
                "name": "App group",
                "type": "SEARCH_STANDARD",
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
    runtime = AgentRuntime(require_llm=False, offline_mode=True)
    runtime.register_capability(create_google_capability())
    intent = ParsedIntent(
        "create_campaign", "创建 Google App 广告", ["google-ads"],
        campaign_type="APP", platform_params={"google-ads": {"campaign_type": "APP"}},
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
            platform="test",
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
    runtime = AgentRuntime(require_llm=False, offline_mode=True)
    runtime.register_capability(create_google_capability())
    intent = ParsedIntent(
        "create_campaign", "创建 Google App Engagement 广告", ["google-ads"],
        campaign_type="APP", platform_params={"google-ads": {"campaign_type": "APP"}},
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
    runtime = AgentRuntime(require_llm=False, offline_mode=True)
    runtime.register_capability(create_google_capability())
    intent = ParsedIntent(
        "create_campaign", "创建 Google Demand Gen 轮播广告", ["google-ads"],
        campaign_type="DEMAND_GEN",
        platform_params={"google-ads": {"campaign_type": "DEMAND_GEN"}},
    )
    card = runtime.build_creation_ui(intent)["cards"][0]
    fields = {item["path"]: item for item in card["fields"]}
    carousel = fields["ad.carousel_cards"]
    assert carousel["object_shape"] == "array"
    assert carousel["object_max_items"] == 10
    card_props = carousel["object_properties"]
    assert card_props["marketing_image_asset"]["lookup_tool"] == "google_list_assets"
    assert card_props["marketing_image_asset"]["presentation"] == "asset_picker"

    runtime = AgentRuntime(require_llm=False, offline_mode=True)
    runtime.register_capability(create_tiktok_capability())
    tiktok_intent = ParsedIntent(
        "create_campaign", "创建 TikTok 视频广告", ["tiktok"],
        campaign_type="TRAFFIC",
        platform_params={"tiktok": {"objective_type": "TRAFFIC"}},
    )
    tiktok_card = runtime.build_creation_ui(tiktok_intent)["cards"][0]
    tiktok_fields = {item["path"]: item for item in tiktok_card["fields"]}
    media = tiktok_fields["ad.media"]
    assert media["manual_entry"]["source"] == "provider_media_payload"
    assert media["item_properties"]["image_id"]["lookup_tool"] == "tiktok_list_images"


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
    assert states["ad_group.conversion_id"]["required"] is True
    assert "campaign.app_promotion_type" in result["missing_fields"]


def test_creation_ui_builds_tiktok_app_card_from_registered_blueprint():
    runtime = AgentRuntime(require_llm=False, offline_mode=True)
    runtime.register_capability(create_tiktok_capability())
    intent = ParsedIntent(
        "create_campaign",
        "创建 TikTok App 转化广告，投放给 18 到 35 岁用户",
        ["tiktok"],
        platform_params={
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
    assert fields["ad_group.optimization_goal"]["options"] == [
        {"value": "INSTALL", "label": "INSTALL"},
        {"value": "IN_APP_EVENT", "label": "IN_APP_EVENT"},
        {"value": "CONVERSION", "label": "CONVERSION"},
    ]
    assert ui["needs_input"] is True


def test_creation_ui_returns_selector_card_when_creation_dimension_is_ambiguous():
    runtime = AgentRuntime(require_llm=False, offline_mode=True)
    runtime.register_capability(create_tiktok_capability())
    intent = ParsedIntent(
        "create_campaign", "创建 TikTok 广告", ["tiktok"], objective="sales"
    )
    card = runtime.build_creation_ui(intent)["cards"][0]
    assert card["type"] == "ad_creation_selector"
    assert card["fields"][0]["provider_field"] == "objective_type"
    assert card["fields"][0]["state"] == "invalid"
    assert card["fields"][0]["path"] in card["invalid_fields"]


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
            name="test_create", skill="test", platform="test",
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
    from agents.ad_agent.core.blueprint import validate_blueprint_against_tools

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
