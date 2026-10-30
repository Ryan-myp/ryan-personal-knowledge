"""Draft validation must reuse registered contracts before Provider execution."""

from copy import deepcopy

import pytest

from agents.agent_harness.core.interfaces import ParsedIntent
from agents.applications.advertising.composition.ad_application import AdvertisingComposition
from agents.applications.advertising.execution.account_policy import AccountWhitelistValidator
from agents.tools.advertising.providers.source_factory import create_tool_source
from agents.tools.advertising.shared.domain.blueprint import (
    AdCreationBlueprint, BlueprintCascadeEngine,
)


def blueprint(**field_overrides):
    return AdCreationBlueprint.from_dict({
        "id": "example.validation", "version": "1.0.0", "provider": "example",
        "ad_format": "EXAMPLE",
        "tools": ["create"],
        "fields": [{"path": "ad.value", "tool_ref": "create.value", **field_overrides}],
        "rules": [],
    })


@pytest.mark.parametrize(("schema", "value", "message"), [
    ({"type": "integer"}, True, "类型"),
    ({"type": "number", "minimum": 1}, 0, "小于"),
    ({"type": "number", "maximum": 100}, 101, "大于"),
    ({"type": "string", "minLength": 2}, "x", "至少"),
    ({"type": "string", "maxLength": 2}, "xxx", "最多"),
    ({"type": "string", "pattern": "[0-9]+"}, "not-an-id", "格式"),
    ({"type": "array", "minItems": 2, "items": {"type": "string"}}, ["a"], "至少"),
    ({"type": "array", "uniqueItems": True, "items": {"type": "integer"}}, [1, 1], "重复"),
    ({"type": "object", "required": ["child"], "properties": {"child": {"type": "string"}}},
     {"other": 1}, "必填"),
    ({"type": "object", "additionalProperties": False, "properties": {"child": {"type": "string"}}},
     {"access_token": "must-not-echo"}, "未声明"),
    ({"type": "array", "items": {"type": "string", "enum": ["A"]}}, ["must-not-echo"], "选项"),
    ({"type": "number"}, float("inf"), "有限"),
])
def test_draft_uses_schema_constraints_with_safe_explanations(schema, value, message):
    result = BlueprintCascadeEngine().evaluate(
        blueprint(), {"ad.value": value}, field_schemas={"ad.value": schema},
    )
    assert result["invalid_fields"] == ["ad.value"]
    assert result["ready"] is False
    field = result["fields"][0]
    assert field["state"] == "invalid"
    assert message in " ".join(field["validation_errors"])
    assert "must-not-echo" not in str(field["validation_errors"])
    assert "access_token" not in str(field["validation_errors"])


@pytest.mark.parametrize("value", [None, "", [], {}])
def test_empty_partial_drafts_remain_editable(value):
    result = BlueprintCascadeEngine().evaluate(
        blueprint(required=True), {"ad.value": value},
        field_schemas={"ad.value": {"type": "array", "minItems": 2}},
    )
    assert result["missing_fields"] == ["ad.value"]
    assert not result["invalid_fields"]


def test_hidden_invalid_fields_do_not_block_current_branch_or_mutate_draft():
    values = {"ad.value": "wrong-type"}
    original = deepcopy(values)
    result = BlueprintCascadeEngine().evaluate(
        blueprint(visible_when={"field": "ad.value", "equals": "visible"}),
        values, field_schemas={"ad.value": {"type": "integer"}},
    )
    assert result["ready"] is True
    assert result["fields"][0]["state"] == "hidden"
    assert values == original


def test_false_and_zero_are_provided_values_and_can_be_valid():
    for value, schema in [(False, {"type": "boolean"}), (0, {"type": "integer", "minimum": 0})]:
        result = BlueprintCascadeEngine().evaluate(
            blueprint(required=True), {"ad.value": value}, field_schemas={"ad.value": schema},
        )
        assert result["ready"] is True
        assert result["fields"][0].get("validation_errors", []) == []


def test_fixed_derived_selector_is_available_before_dependent_validation():
    document = blueprint().to_dict()
    document["fields"][0]["visible_when"] = {"field": "ad.format", "equals": "TEXT"}
    document["fields"].append({
        "path": "ad.format", "tool_ref": "create.format",
        "presentation": "derived_readonly", "options": ["TEXT"],
    })
    result = BlueprintCascadeEngine().evaluate(
        AdCreationBlueprint.from_dict(document), {"ad.value": 10},
        field_schemas={"ad.value": {"type": "string"}, "ad.format": {"type": "string"}},
    )
    assert "ad.value" in result["invalid_fields"]


@pytest.fixture
def runtime(monkeypatch):
    monkeypatch.setattr(AccountWhitelistValidator, "_load_config", lambda _self: None)
    value = AdvertisingComposition(require_llm=False, offline_mode=True)
    for provider in ("google-ads", "meta", "tiktok"):
        value.register_tool_source(create_tool_source(provider))
    yield value
    value.close(wait=True)


@pytest.mark.parametrize(("blueprint_id", "path", "value", "context"), [
    ("google-ads.search", "ad.headlines", ["Only one"], {}),
    ("google-ads.shopping", "campaign.shopping_setting.merchant_id", "not-an-integer", {}),
    ("meta.traffic_link", "campaign.daily_budget", "not-a-number", {}),
    ("tiktok.web_conversions", "ad.music_info", {"unsupported": "value"}, {}),
])
def test_runtime_evaluation_uses_three_channel_registered_schemas(runtime, blueprint_id, path, value, context):
    document = next(item for item in runtime.list_creation_blueprints() if item["id"] == blueprint_id)
    assert any(field["path"] == path for field in document["fields"])
    result = runtime.evaluate_creation_blueprint(blueprint_id, {path: value, **context})
    assert path in result["invalid_fields"]
    assert next(field for field in result["fields"] if field["path"] == path)["validation_errors"]


def test_conversation_card_rejects_short_google_headline_array_before_execution(runtime):
    intent = ParsedIntent(
        "create_campaign", "Create search campaign", ["google-ads"],
        campaign_type="SEARCH",
        scoped_parameters={"google-ads": {
            "google_create_search_ad": {"headlines": ["Only one"]},
        }},
    )
    cards = runtime.creation_card_builder.build(intent, account_id="test-account")
    card = next(item for item in cards if item.get("blueprint_id") == "google-ads.search")
    assert "ad.headlines" in card["invalid_fields"]
    field = next(item for item in card["fields"] if item["path"] == "ad.headlines")
    assert field["validation_errors"]


def test_optional_single_enum_array_is_not_selected_without_user_input(runtime):
    cards = runtime.creation_card_builder.build(
        ParsedIntent("create_campaign", "Create lead campaign", ["meta"], objective="OUTCOME_LEADS"),
        account_id="test-account",
    )
    card = next(item for item in cards if item.get("blueprint_id") == "meta.lead_generation")
    field = next(item for item in card["fields"] if item["path"] == "ad_set.regional_regulated_categories")
    assert field["value"] is None
    assert not field["auto_filled"]
    assert field["state"] != "invalid"


def test_missing_field_contract_fails_closed_for_provided_values():
    result = BlueprintCascadeEngine().evaluate(blueprint(), {"ad.value": "value"}, field_schemas={})
    assert "合同暂不可用" in result["fields"][0]["validation_errors"][0]
