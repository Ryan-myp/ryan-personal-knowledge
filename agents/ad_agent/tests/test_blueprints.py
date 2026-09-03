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
from agents.ad_agent.core.interfaces import ParsedIntent, ToolDefinition, ToolSchema, ToolEffect
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
