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
