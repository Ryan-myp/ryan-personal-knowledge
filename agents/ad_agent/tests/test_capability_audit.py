from agents.ad_agent.scripts.audit_capabilities import (
    _covered_tool_names,
    audit_capabilities,
)
from agents.ad_agent.scripts.validate_contracts import (
    build_contract_snapshot,
    build_runtime,
    verify_snapshot,
)

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
    assert report["platforms"]["tiktok"]["actions"]["create:ad_group"] == 2
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
    assert any(
        item["resource"] == "asset_group"
        and item["action"] == "live_create"
        for item in google["api_surface_planned"]
    )
    assert not any(
        entry["resource"] == "campaign_criterion"
        for entry in google["api_surface_planned"]
    )
    assert meta["api_surface"]["implemented"] > 0
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


def test_capability_audit_keeps_client_method_tool_surface_chain_complete():
    report = audit_capabilities()

    for platform, methods in report["provider_method_coverage"].items():
        assert methods, platform
        for method, coverage in methods.items():
            assert coverage["tools"], f"{platform}:{method} has no Tool"
            assert coverage["surface_entries"], f"{platform}:{method} has no Surface entry"


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
