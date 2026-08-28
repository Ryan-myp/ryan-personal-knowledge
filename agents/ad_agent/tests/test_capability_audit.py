from agents.ad_agent.scripts.audit_capabilities import audit_capabilities
from agents.ad_agent.scripts.validate_contracts import (
    build_contract_snapshot,
    build_runtime,
    verify_snapshot,
)

import copy
import json


def test_capability_audit_discovers_all_installed_channels_without_issues():
    report = audit_capabilities()

    assert report["issues"] == []
    assert report["tool_count"] == 120
    assert set(report["platforms"]) == {"meta", "google-ads", "tiktok", "dv360"}
    assert report["platforms"]["tiktok"]["actions"]["create:ad_group"] == 1
    assert report["platforms"]["dv360"]["actions"]["create:line_item"] == 1
    assert all(
        item["intent_types"]
        for details in report["platforms"].values()
        for item in details["creation_chain"]
    )


def test_contract_snapshot_is_deterministic_and_partitioned_by_platform():
    runtime = build_runtime()
    first = build_contract_snapshot(runtime)
    second = build_contract_snapshot(runtime)

    assert first == second
    assert first["tool_count"] == 120
    assert set(first["platforms"]) == {"meta", "google-ads", "tiktok", "dv360"}
    assert all(details["digest"] for details in first["platforms"].values())


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
