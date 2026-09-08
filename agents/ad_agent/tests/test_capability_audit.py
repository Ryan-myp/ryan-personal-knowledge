from agents.ad_agent.scripts.audit_capabilities import (
    _covered_tool_names,
    audit_capabilities,
)
from agents.ad_agent.scripts.audit_creation_contracts import (
    audit_creation_contracts,
    build_runtime as build_creation_runtime,
)
from agents.ad_agent.scripts.validate_contracts import (
    build_contract_snapshot,
    build_runtime,
    verify_snapshot,
)
from agents.ad_agent.core.interfaces import ToolDefinition, ToolEffect, ToolSchema

import copy
import json


def test_capability_audit_can_detect_registered_tools_missing_from_coverage():
    coverage = {
        "list_campaigns": ["provider_list_campaigns"],
        "update_campaign": "provider_update_campaign",
    }

    assert _covered_tool_names(coverage) == {
        "provider_list_campaigns", "provider_update_campaign"
    }
    assert {"provider_update_campaign", "unmapped_tool"} - _covered_tool_names(coverage) == {
        "unmapped_tool"
    }


def test_capability_audit_discovers_all_installed_channels_without_issues():
    report = audit_capabilities()

    assert report["issues"] == []
    assert report["tool_count"] >= 124
    assert set(report["platforms"]) == {"meta", "google-ads", "tiktok", "dv360"}
    assert report["platforms"]["tiktok"]["actions"]["create:ad_group"] == 3
    assert report["platforms"]["dv360"]["actions"]["create:line_item"] == 1
    assert all(
        item["intent_types"]
        for details in report["platforms"].values()
        for item in details["creation_chain"]
    )


def test_capability_audit_includes_provider_owned_api_surface_and_planned_gaps():
    report = audit_capabilities()

    google = report["platforms"]["google-ads"]
    meta = report["platforms"]["meta"]
    assert google["api_surface"]["implemented"] > 0
    assert google["api_surface"]["planned"] > 0
    assert not any(
        item["resource"] == "asset_group"
        and item["action"] == "live_create"
        for item in google["api_surface_planned"]
    )
    assert not any(
        entry["resource"] == "campaign_criterion"
        for entry in google["api_surface_planned"]
    )
    assert meta["api_surface"]["implemented"] > 0
    assert "meta_create_lookalike_audience" in {
        tool
        for method in meta["provider_method_coverage"].values()
        for tool in method["tools"]
    }
    assert not any(
        entry["resource"] == "lookalike_audience"
        for entry in meta["official_inventory"]["gaps_entries"]
    )
    assert any(
        entry["resource"] == "pixel"
        for entry in meta["api_surface_planned"]
    )
    custom_conversion_actions = {
        entry["action"]
        for method in (
            "create_custom_conversion", "list_custom_conversions",
            "get_custom_conversion", "update_custom_conversion",
            "delete_custom_conversion",
        )
        for entry in meta["provider_method_coverage"][method]["surface_entries"]
    }
    assert custom_conversion_actions == {"create", "list", "get", "update", "delete"}
    assert report["surface_gaps"] == {
        platform: [] for platform in report["platforms"]
    }
    dv360 = report["platforms"]["dv360"]
    assert not any(
        item["tool"] == "dv360_create_campaign"
        for item in dv360["creation_chain"]
    )
    assert any(
        item["resource"] == "campaign" and item["action"] == "create"
        for item in dv360["api_surface_planned"]
    )
    assert set(dv360["provider_method_coverage"]["update_resource"]["tools"]) == {
        "dv360_update_campaign", "dv360_update_io", "dv360_update_line_item",
    }
    assert all(
        all(item["surface_entries"] for item in methods.values())
        for methods in report["provider_method_coverage"].values()
    )


def test_capability_audit_reports_scoped_official_inventory_separately_from_tools():
    report = audit_capabilities()

    for platform, details in report["platforms"].items():
        inventory = details["official_inventory"]
        assert inventory["total"] > 0, platform
        assert inventory["source_url"].startswith("https://"), platform
        assert inventory["completeness"] == "scoped_not_exhaustive"
        assert inventory["covered"] + inventory["gaps"] == inventory["total"]
        assert inventory["execution_statuses"], platform
        assert inventory["evidence_levels"] == {"provider_doc_scope": inventory["total"]}
        assert len(inventory["evidence_gaps"]) == inventory["total"]
        assert all(
            entry["endpoint"] and entry["source_url"]
            for entry in inventory["covered_entries"] + inventory["gaps_entries"]
        )

    # Newly implemented resources must move from the explicit planned gap
    # list into covered entries without changing the scoped-not-exhaustive
    # semantics of the provider inventory.
    google_covered = report["platforms"]["google-ads"]["official_inventory"]["covered_entries"]
    assert any(entry["resource"] == "feed" for entry in google_covered)
    assert any(
        entry["resource"] == "conversion_goal"
        for entry in google_covered
    )


def test_capability_audit_keeps_client_method_tool_surface_chain_complete():
    report = audit_capabilities()

    for platform, methods in report["provider_method_coverage"].items():
        assert methods, platform
        for method, coverage in methods.items():
            assert coverage["tools"], f"{platform}:{method} has no Tool"
            assert coverage["surface_entries"], f"{platform}:{method} has no Surface entry"


def test_creation_contract_audit_closes_blueprint_and_lookup_sources_without_io():
    report = audit_creation_contracts(build_creation_runtime())

    assert report["issues"] == []
    assert report["blueprint_count"] == 26
    assert report["creation_tool_count"] > 0
    assert report["lookup_contract_count"] > 0
    assert not report["unresolved_fields"]
    assert report["blueprint_coverage"]["tiktok"]["unmapped_guided_formats"] == []
    assert not next(
        row for row in report["blueprint_coverage"]["tiktok"]["formats"]
        if row["format_id"] == "brand.topview"
    )["blueprints"]
    assert report["selector_overlaps"] == [{
        "provider": "google-ads",
        "dimension": "ad_format",
        "values": ["DEMAND_GEN"],
        "blueprints": [
            "google-ads.demand_gen_carousel",
            "google-ads.demand_gen_multi_asset",
            "google-ads.demand_gen_product",
            "google-ads.demand_gen_video_responsive",
        ],
    }]
    assert any(
        item["tool"] == "meta_create_adset"
        and item["field"] == "targeting.custom_audiences"
        and item["lookup_tool"] == "meta_list_audiences"
        and item["read_only"]
        for item in report["lookup_contracts"]
    )


def test_creation_contract_audit_reports_field_source_distribution():
    report = audit_creation_contracts(build_creation_runtime())

    assert report["field_source_total"] > 0
    assert report["unclassified_fields"] == []
    for provider, counts in report["field_source_counts"].items():
        assert counts["enum"] > 0, provider
        assert counts["free_text"] > 0, provider
    assert any(
        item["provider"] == "tiktok"
        and item["source"] == "lookup"
        and item["details"]["lookup_tool"] == "tiktok_list_apps"
        for item in report["field_sources"]
    )
    assert all(
        item["same_provider"]
        for item in report["lookup_contracts"]
    )
    assert not any(
        item["tool"] == "google_create_ad_group"
        and item["field"] == "targeting"
        for item in report["structured_guidance_gaps"]
    )
    assert any(
        item["provider"] == "google-ads"
        and item["tool"] == "google_create_ad"
        and item["field"] == "responsive_display_ad"
        and item["presentation"] == "advanced_json"
        for item in report["advanced_structured_fields"]
    )
    assert any(
        item["provider"] == "dv360"
        and item["tool"] == "dv360_create_report"
        and item["field"] == "report"
        for item in report["advanced_structured_fields"]
    )


def test_creation_contract_audit_rejects_resource_field_without_value_source():
    runtime = build_creation_runtime()
    runtime.registry.register(
        ToolDefinition(
            name="test_create_ad_with_unresolved_asset",
            skill="test",
            platform="meta",
            description="test-only create Tool",
            input_schema=ToolSchema(
                required=["asset_id"],
                properties={"asset_id": {"type": "string"}},
            ),
            action="create",
            resource_type="ad",
            intent_types=["test_create_ad"],
            effect_class=ToolEffect.EXTERNAL_WRITE,
            live_support=False,
        ),
        object(),
    )

    report = audit_creation_contracts(runtime)

    assert {
        "tool": "test_create_ad_with_unresolved_asset",
        "field": "asset_id",
        "source": "free_text",
    } in report["unresolved_fields"]
    assert any(
        "test_create_ad_with_unresolved_asset.asset_id" in issue
        for issue in report["issues"]
    )


def test_creation_contract_audit_rejects_cross_provider_lookup():
    runtime = build_creation_runtime()
    runtime.registry.register(
        ToolDefinition(
            name="test_google_lookup",
            skill="test",
            platform="google-ads",
            description="test-only lookup Tool",
            input_schema=ToolSchema(
                required=[],
                properties={"items": {"type": "array"}},
            ),
            action="list",
            resource_type="asset",
            intent_types=["test_list_assets"],
            effect_class=ToolEffect.READ,
        ),
        object(),
    )
    runtime.registry.register(
        ToolDefinition(
            name="test_meta_create_ad",
            skill="test",
            platform="meta",
            description="test-only create Tool",
            input_schema=ToolSchema(
                required=["asset_id"],
                properties={
                    "asset_id": {
                        "type": "string",
                        "lookup_tool": "test_google_lookup",
                    },
                },
            ),
            action="create",
            resource_type="ad",
            intent_types=["test_create_ad"],
            effect_class=ToolEffect.EXTERNAL_WRITE,
            live_support=False,
        ),
        object(),
    )

    report = audit_creation_contracts(runtime)

    assert any(
        "test_meta_create_ad.asset_id" in issue
        and "must belong to provider meta" in issue
        for issue in report["issues"]
    )
    lookup = next(
        item for item in report["lookup_contracts"]
        if item["tool"] == "test_meta_create_ad"
    )
    assert lookup["read_only"] is True
    assert lookup["same_provider"] is False


def test_contract_snapshot_is_deterministic_and_partitioned_by_platform():
    runtime = build_runtime()
    first = build_contract_snapshot(runtime)
    second = build_contract_snapshot(runtime)

    assert first == second
    assert first["tool_count"] >= 124
    assert set(first["platforms"]) == {"meta", "google-ads", "tiktok", "dv360"}
    assert all(details["digest"] for details in first["platforms"].values())
    assert set(first["provider_api_surfaces"]) == {
        "meta", "google-ads", "tiktok", "dv360"
    }


def test_contract_snapshot_reports_existing_tool_drift(tmp_path):
    runtime = build_runtime()
    expected = build_contract_snapshot(runtime)
    snapshot_path = tmp_path / "contracts.json"
    snapshot_path.write_text(
        json.dumps(expected, ensure_ascii=False),
        encoding="utf-8",
    )

    actual = copy.deepcopy(expected)
    actual["platforms"]["meta"]["tools"][0]["description"] += " changed"

    errors = verify_snapshot(snapshot_path, actual)

    assert any("changed contract" in error for error in errors)
