"""Management catalogs must reflect declared contracts, never word overlap."""

import pytest

from agents.applications.advertising.composition.ad_application import AdvertisingComposition
from agents.applications.advertising.persistence.store import AdAgentStore
from agents.tools.advertising.providers.google import create_google_tool_source
from agents.tools.advertising.providers.meta import create_meta_tool_source
from agents.tools.advertising.providers.tiktok import create_tiktok_tool_source
from scripts.advertising.audit_creation_contracts import _blueprint_match_score


@pytest.fixture(scope="module")
def runtime():
    app = AdvertisingComposition(require_llm=False, offline_mode=True, persistence_store=AdAgentStore(":memory:"))
    for factory in (create_google_tool_source, create_meta_tool_source, create_tiktok_tool_source):
        app.register_tool_source(factory())
    return app


def test_catalog_declares_exact_blueprint_relationships(runtime):
    for provider in ("google-ads", "meta", "tiktok"):
        entries = runtime.list_ad_formats(provider)
        mapped = set()
        for entry in entries:
            ids = entry.get("blueprint_ids", [])
            if entry["coverage"] == "declared_only":
                assert not ids
            for blueprint_id in ids:
                blueprint = runtime.creation_blueprints.get(blueprint_id)
                assert blueprint is not None
                assert blueprint.provider == provider
                mapped.add(blueprint_id)
        assert mapped == {item.blueprint_id for item in runtime.creation_blueprints.list(provider)}
    assert any(item["format_id"] == "app_promotion" for item in runtime.list_ad_formats("meta"))


def test_similar_format_words_do_not_invent_a_mapping(runtime):
    search = next(item for item in runtime.list_ad_formats("google-ads") if item["format_id"] == "search.responsive_search_ad")
    assert _blueprint_match_score(search, runtime.creation_blueprints.get("google-ads.search")) == 100
    assert _blueprint_match_score(search, runtime.creation_blueprints.get("google-ads.demand_gen_video_responsive")) == 0
    app = runtime.creation_blueprints.get("tiktok.app_conversion_video")
    assert runtime._creation_blueprint_support(app)["catalog_format"] == "app"


@pytest.mark.parametrize("format_id,tool,media_field", [
    ("single_image", "tiktok_create_single_image_ad", "ad.image_ids"),
    ("single_video", "tiktok_create_single_video_ad", "ad.video_id"),
])
def test_tiktok_regular_media_formats_have_their_own_guided_contract(runtime, format_id, tool, media_field):
    entry = next(item for item in runtime.list_ad_formats("tiktok") if item["format_id"] == format_id)
    assert entry["blueprint_ids"] == [f"tiktok.{format_id}"]
    blueprint = runtime.creation_blueprints.get(entry["blueprint_ids"][0])
    assert tool in blueprint.tools
    fields = {f["path"]: f for f in runtime.creation_card_builder.expand_blueprint(blueprint).fields}
    assert fields[media_field]["required"]
    assert fields[media_field]["lookup_tool"] in {"tiktok_list_images", "tiktok_get_video"}


def test_exact_variant_wins_over_shared_selector_but_conflicts_are_rejected(runtime):
    registry = runtime.creation_blueprints
    resolved = registry.resolve("google-ads", selector_values={"ad_format": "DEMAND_GEN_PRODUCT"},
                                values={"campaign.advertising_channel_type": "DEMAND_GEN"})
    assert resolved is not None and resolved.blueprint_id == "google-ads.demand_gen_product"
    assert registry.resolve("meta", selector_values={"ad_format": "app_promotion", "objective": "OUTCOME_TRAFFIC"}) is None
    resolved = registry.resolve("tiktok", selector_values={"ad_format": "SINGLE_VIDEO", "objective": "APP_PROMOTION"})
    assert resolved is not None and resolved.blueprint_id == "tiktok.app_conversion_video"


def test_template_missing_inputs_respect_conditions_and_empty_values(runtime, monkeypatch):
    monkeypatch.setattr(runtime, "list_creation_templates", lambda **kw: [{
        "blueprint_id": "meta.app_promotion",
        "blueprint_version": runtime.creation_blueprints.get("meta.app_promotion").version,
        "values": {
            "ad.media_type": "IMAGE", "ad.image_hash": "", "ad.name": "   ",
        },
    }])
    row = next(item for item in runtime.list_creation_catalog("meta")["ad_types"]
               if item["blueprint_id"] == "meta.app_promotion")
    missing = row["template_options"][0]["missing_inputs"]
    assert "ad.image_hash" in missing
    assert "ad.name" in missing
    assert "ad.video_id" not in missing


def test_every_three_channel_blueprint_has_a_template_without_leaking_account_values(runtime):
    from agents.applications.advertising.creation.templates import load_builtin_template_definitions

    definitions = load_builtin_template_definitions()
    covered = {item["blueprint_id"] for item in definitions}
    assert {item.blueprint_id for item in runtime.creation_blueprints.list()} <= covered
    starters = [item for item in definitions if item.get("scope_type") == "general"]
    assert len(starters) >= 16
    for item in starters:
        assert not item.get("account_id")
        assert item["verification_status"] == "dry_run_only"
        assert not any(path.endswith(("account_id", "customer_id", "image_hash", "video_id", "page_id")) for path in item["values"])
        blueprint = runtime.creation_blueprints.get(item["blueprint_id"], item["blueprint_version"])
        assert blueprint.version == item["blueprint_version"]
        if not item.get("catalog_hidden"):
            assert runtime.creation_blueprints.get(item["blueprint_id"]).version == blueprint.version
    templates = runtime.list_creation_templates(provider="meta", account_scope={"meta": ["other-account"]})
    assert templates and all(not item["account_id"] for item in templates)
    assert runtime.list_creation_templates(provider="meta", account_scope={"tiktok": ["other-account"]}) == []


def test_starter_template_defaults_match_their_blueprint_options(runtime):
    from agents.applications.advertising.creation.templates import load_builtin_template_definitions
    from agents.tools.advertising.shared.domain.blueprint import BlueprintCascadeEngine

    for item in load_builtin_template_definitions():
        if item.get('scope_type') != 'general':
            continue
        blueprint = runtime.creation_blueprints.get(item['blueprint_id'])
        evaluation = BlueprintCascadeEngine().evaluate(blueprint, item['values'])
        assert not evaluation['invalid_fields'], (item['key'], evaluation['invalid_fields'])


def test_starter_templates_remain_valid_when_ui_adds_schema_defaults(runtime):
    from agents.applications.advertising.creation.templates import load_builtin_template_definitions

    for item in load_builtin_template_definitions():
        if item.get('scope_type') != 'general':
            continue
        blueprint = runtime.creation_card_builder.expand_blueprint(
            runtime.creation_blueprints.get(item['blueprint_id']))
        values = {field['path']: field['default'] for field in blueprint.fields if 'default' in field}
        values.update(item['values'])
        evaluation = runtime.evaluate_creation_blueprint(item['blueprint_id'], values)
        assert not evaluation['invalid_fields'], (item['key'], evaluation['invalid_fields'])
