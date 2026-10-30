"""Provider extensions use closed, documented fields, with no external calls."""

import pytest

from agents.agent_harness.core.interfaces import ToolSchema
from agents.agent_harness.core.tool_registry import validate_tool_input
from agents.tools.advertising.providers.tiktok.parameters import tiktok_smart_plus_ad_schema


def validate(field, value):
    spec = tiktok_smart_plus_ad_schema()["properties"][field]
    return validate_tool_input(ToolSchema(properties={"value": spec}), {"value": value})


def test_music_is_a_real_closed_object_not_an_empty_object_placeholder():
    assert not validate("music_info", {"music_id": "music-123"})
    assert validate("music_info", {})
    assert validate("music_info", {"music_id": "music-123", "unknown": True})


def test_product_and_catalog_configuration_use_documented_smart_plus_fields():
    assert not validate("ad_configuration", {
        "product_ids": ["product-1"], "catalog_creative_toggle": True,
        "product_display_field_list": ["price"],
    })
    assert validate("ad_configuration", {"product_ids": "product-1"})
    assert validate("ad_configuration", {"catalog_creative_toggle": "true"})
    assert validate("ad_configuration", {"product_info": {"guessed": True}})


def test_unimplemented_opaque_aliases_are_not_advertised_as_fillable_objects():
    schema = tiktok_smart_plus_ad_schema()
    assert "product_info" not in schema["properties"]
    assert "catalog_creative_info" not in schema["properties"]
    music = schema["properties"]["creative_list"]["items"]["properties"][
        "creative_info"]["properties"]["music_info"]
    assert music["properties"]["music_id"]["type"] == "string"


def test_utm_entries_are_bounded_and_closed():
    assert not validate("ad_configuration", {"utm_params": [{"key":"utm_source","value":"tiktok"}]})
    assert validate("ad_configuration", {"utm_params": [{"key":"utm_source"}]})
    assert validate("ad_configuration", {"utm_params": [{"key":"k","value":"v","command":"bad"}]})
    assert validate("ad_configuration", {"utm_params": [{"key":"k","value":"v"}] * 51})


def test_client_rejects_unimplemented_aliases_before_any_http(monkeypatch):
    from agents.tools.advertising.clients.tiktok_client import TikTokAPIClient
    client = TikTokAPIClient({"access_token": "test"})
    monkeypatch.setattr(client, "request", lambda *_a, **_kw: pytest.fail("unexpected HTTP"))
    for field in ("product_info", "catalog_creative_info"):
        with pytest.raises(ValueError, match=field):
            client.create_smart_plus_ad("1", "2", "3", {
                "ad_name": "Paused", field: {"guessed": True},
            }, live=True)


def test_every_latest_three_channel_blueprint_has_an_account_independent_starter():
    from scripts.advertising.audit_creation_contracts import build_runtime
    from agents.applications.advertising.creation.templates import load_builtin_template_definitions
    runtime = build_runtime()
    try:
        starters = {
            (row["blueprint_id"], row["blueprint_version"])
            for row in load_builtin_template_definitions()
            if row.get("scope_type") == "general" and not row.get("catalog_hidden")
        }
        for blueprint in runtime.creation_blueprints.list():
            if blueprint.provider in runtime.ad_format_catalogs:
                assert (blueprint.blueprint_id, blueprint.version) in starters
    finally:
        runtime.close(wait=True)


def test_music_and_product_controls_reach_the_creation_form():
    from scripts.advertising.audit_creation_contracts import build_runtime
    from agents.agent_harness.core.interfaces import ParsedIntent
    runtime = build_runtime()
    try:
        intent = ParsedIntent("create_campaign", "TikTok 流量", ["tiktok"], metadata={
            "creation_blueprint_id": "tiktok.traffic_video",
        })
        cards = runtime.build_creation_ui(intent).get("cards", [])
        assert cards
        fields = {row["path"]: row for row in cards[0]["fields"]}
        assert fields["ad.music_info"]["object_properties"]["music_id"]
        assert fields["ad.ad_configuration"]["object_properties"]["catalog_creative_toggle"]["type"] == "boolean"
    finally:
        runtime.close(wait=True)


@pytest.mark.parametrize("nested", [False, True])
def test_optional_fields_survive_smart_plus_dry_run(nested, monkeypatch):
    from agents.tools.advertising.clients.tiktok_client import TikTokAPIClient
    client = TikTokAPIClient({"access_token": "test"})
    monkeypatch.setattr(client, "request", lambda *_a, **_kw: pytest.fail("unexpected HTTP"))
    creative = {"ad_format": "SINGLE_VIDEO", "video_id": "video-1",
                "image_web_uris": ["cover-1"], "music_info": {"music_id": "music-1"}}
    configuration = {
        "product_ids": ["product-1"], "product_display_field_list": ["price"],
        "catalog_creative_toggle": True,
        "utm_params": [{"key": "utm_source", "value": "tiktok"}],
    }
    ad = {"ad_name": "Paused", "operation_status": "DISABLE",
          "ad_configuration": configuration}
    ad.update({"creative_list": [{"creative_info": creative}]} if nested else creative)
    result = client.create_smart_plus_ad("1", "2", "3", ad, live=False)
    payload = result["operation"]["smart_plus/ad/create/"]["create"]
    assert payload["creative_list"][0]["creative_info"]["music_info"] == {"music_id": "music-1"}
    assert all(payload["ad_configuration"][key] == value for key, value in configuration.items())


def test_template_audit_detects_missing_latest_starters():
    from agents.applications.advertising.creation.templates import load_builtin_template_definitions
    from scripts.advertising.audit_creation_contracts import build_runtime
    from scripts.advertising.audit_creation_templates import audit_creation_templates
    runtime = build_runtime()
    try:
        rows = [row for row in load_builtin_template_definitions()
                if row["key"] != "meta.app_promotion.starter"]
        report = audit_creation_templates(runtime, rows)
        assert any(item["blueprint_id"] == "meta.app_promotion"
                   for item in report["missing_general_starters"])
    finally:
        runtime.close(wait=True)


def test_strict_creation_audit_rejects_unusable_empty_objects(monkeypatch):
    from scripts.advertising import audit_creation_contracts as audit
    monkeypatch.setattr(audit, "build_runtime", lambda: None)
    monkeypatch.setattr(audit, "audit_creation_contracts", lambda _runtime: {
        "issues": [], "blueprint_coverage": {},
        "structured_guidance_gaps": [{"tool": "create", "field": "music_info"}],
    })
    assert audit.main(["--json", "--strict-guided"]) == 1


def test_template_audit_rejects_invalid_generic_preset_values():
    from copy import deepcopy
    from agents.applications.advertising.creation.templates import load_builtin_template_definitions
    from scripts.advertising.audit_creation_contracts import build_runtime
    from scripts.advertising.audit_creation_templates import audit_creation_templates
    runtime = build_runtime()
    try:
        rows = deepcopy(load_builtin_template_definitions())
        starter = next(row for row in rows if row["key"] == "meta.app_promotion.starter")
        starter["values"]["campaign.name"] = {"wrong_type": True}
        report = audit_creation_templates(runtime, rows)
        assert any(item["key"] == starter["key"] for item in report["issues"])
    finally:
        runtime.close(wait=True)
