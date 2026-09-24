"""Regression tests for the evidence-based release gate."""

from pathlib import Path

import pytest

from agents.ad_agent.domain.ad.quality_scorecard import (
    QUALITY_THRESHOLD,
    build_quality_scorecard,
    provider_evidence_ratios,
    provider_query_evidence_ratio,
)
from agents.ad_agent.domain.ad.release_readiness import (
    ReadinessPolicy,
    build_readiness_report,
)
from agents.ad_agent.scripts.provider_contract_harness import run_harness
from agents.ad_agent.tools.providers.api_surface import (
    select_readiness_surface,
    validate_readiness_actions,
    validate_surface,
)


def _policy() -> ReadinessPolicy:
    return ReadinessPolicy.from_dict({
        "format_version": 1,
        "default_profile": "local",
        "readiness_scope": {"required_providers": ["meta"]},
        "profiles": {
            "local": ["code_contract", "dry_run", "provider_scope"],
            "release": [
                "code_contract",
                "dry_run",
                "provider_scope",
                "provider_query_e2e",
                "provider_e2e",
                "live_verified",
                "quality_95",
            ],
        },
    })


def _readiness_scope() -> dict:
    return {
        "meta": {
            "included": True,
            "total": 2,
            "covered": 2,
            "gaps": 0,
            "coverage_ratio": 1.0,
            "query_total": 1,
            "query_covered": 1,
            "managed_write_total": 1,
            "operations": [
                {
                    "readiness_category": "query",
                    "evidence_level": "provider_doc_scope",
                    "execution_status": "dry_run_only",
                },
                {
                    "readiness_category": "managed_write",
                    "evidence_level": "provider_doc_scope",
                    "execution_status": "dry_run_only",
                },
            ],
        },
        "dv360": {
            "included": False,
            "total": 0,
            "covered": 0,
            "gaps": 0,
            "coverage_ratio": 1.0,
            "query_total": 0,
            "query_covered": 0,
            "managed_write_total": 0,
            "operations": [],
        },
    }


def test_local_profile_does_not_promote_local_stub_to_provider_e2e():
    report = build_readiness_report(
        tool_source_report={
            "issues": [],
            "readiness_scope": _readiness_scope(),
            "official_inventory": {
                "test-provider": {
                    "total": 1,
                    "evidence_levels": {"provider_doc_scope": 1},
                    "execution_statuses": {"dry_run_only": 1},
                    "scope": "scoped_not_exhaustive",
                    "completeness": "scoped_not_exhaustive",
                }
            },
        },
        dry_run_report={"executed": True, "failed": 0},
        policy=_policy(),
        profile="local",
    )

    assert report["passed"] is True
    assert report["stage_results"]["provider_query_e2e"]["status"] == "not_verified"
    assert report["stage_results"]["provider_e2e"]["status"] == "not_verified"
    assert report["stage_results"]["live_verified"]["status"] == "not_verified"


def test_release_profile_blocks_without_operation_specific_evidence():
    report = build_readiness_report(
        tool_source_report={
            "issues": [],
            "readiness_scope": _readiness_scope(),
            "official_inventory": {},
        },
        dry_run_report={"executed": True, "failed": 0},
        policy=_policy(),
        profile="release",
    )

    assert report["passed"] is False
    assert report["blocking_stages"] == [
        "provider_query_e2e",
        "provider_e2e",
        "live_verified",
        "quality_95",
    ]
    scorecard = report["stage_results"]["quality_95"]["scorecard"]
    assert scorecard["passed"] is False
    assert {
        "generic_platform",
        "provider_query_e2e",
        "provider_e2e",
        "live_verified",
        "production",
        "maintainability",
    }.issubset(scorecard["blocking_dimensions"])


def test_provider_contract_harness_covers_all_builtin_provider_factories():
    report = run_harness(
        "agents/ad_agent/contracts/provider_contract_scenarios.json"
    )

    assert report["executed"] is True
    assert report["failed"] == 0
    assert report["passed"] == 4
    assert all(row["client_calls"] == 1 for row in report["scenarios"])


def test_release_report_exposes_controlled_evidence_without_promoting_partial_runs():
    report = build_readiness_report(
        tool_source_report={
            "issues": [],
            "readiness_scope": _readiness_scope(),
            "official_inventory": {
                "meta": {
                    "total": 1,
                    "evidence_levels": {"provider_doc_scope": 1},
                    "execution_statuses": {"dry_run_only": 1},
                    "scope": "scoped_not_exhaustive",
                    "completeness": "scoped_not_exhaustive",
                }
            },
        },
        dry_run_report={"executed": True, "failed": 0},
        provider_evidence={
            "schema_version": "1.0",
            "generated_at": "2026-09-18",
            "scope": "campaign_and_descendant_create_update",
            "safety": {
                "test_accounts_only": True,
                "new_resources_paused": True,
                "deleted": False,
                "credentials_included": False,
                "raw_provider_responses_included": False,
            },
            "runs": [{
                "provider": "meta",
                "test_account": "m-test",
                "campaign_type": "TRAFFIC",
                "status": "partial_live_verified",
                "resources": {
                    "campaign": {
                        "id": "c1",
                        "create": "passed",
                        "update": "passed",
                    },
                    "ad_set": {
                        "id": None,
                        "create": "provider_rejected",
                        "update": "not_run",
                    },
                },
            }],
        },
        policy=_policy(),
        profile="local",
    )

    evidence = report["controlled_evidence"]
    assert evidence["valid"] is True
    assert evidence["providers"]["meta"]["fully_verified_runs"] == 0
    assert evidence["providers"]["meta"]["partial_runs"] == 1
    assert report["passed"] is True


def test_quality_scorecard_requires_explicit_evidence_and_95_threshold():
    scorecard = build_quality_scorecard(
        code_contract_ok=True,
        dry_run_ok=True,
        provider_scope_ratio=0.95,
        provider_query_e2e_ratio=0.95,
        generic_platform_ok=False,
        security_ok=True,
        provider_e2e_ratio=0.95,
        live_verified_ratio=0.95,
        production_evidence_ok=False,
        max_runtime_module_lines=None,
    )

    assert QUALITY_THRESHOLD == 95
    assert scorecard["passed"] is False
    assert "generic_platform" in scorecard["blocking_dimensions"]
    assert "production" in scorecard["blocking_dimensions"]
    assert "maintainability" in scorecard["blocking_dimensions"]


def test_provider_evidence_ratios_use_operation_totals():
    e2e, live = provider_evidence_ratios({
        "meta": {
            "included": True,
            "operations": [
                {
                    "readiness_category": "managed_write",
                    "evidence_level": "provider_e2e" if index < 3 else "provider_doc_scope",
                    "execution_status": "live_verified" if index < 2 else "dry_run_only",
                }
                for index in range(4)
            ],
        },
        "tiktok": {
            "included": True,
            "operations": [
                {
                    "readiness_category": "managed_write",
                    "evidence_level": "provider_e2e",
                    "execution_status": "live_verified" if index < 5 else "dry_run_only",
                }
                for index in range(6)
            ],
        },
        "dv360": {
            "included": False,
            "operations": [
                {
                    "readiness_category": "managed_write",
                    "evidence_level": "provider_e2e",
                    "execution_status": "live_verified",
                }
            ],
        },
    })

    assert e2e == 0.75
    assert live == 0.5


def test_release_readiness_uses_scoped_provider_operations_not_full_api_inventory():
    report = build_readiness_report(
        tool_source_report={
            "issues": [],
            "readiness_scope": _readiness_scope(),
            "official_inventory": {
                "dv360": {
                    "total": 100,
                    "evidence_levels": {},
                    "execution_statuses": {},
                }
            },
        },
        dry_run_report={"executed": True, "failed": 0},
        policy=_policy(),
        profile="release",
    )

    assert set(report["provider_summaries"]) == {"meta"}
    assert report["provider_summaries"]["meta"]["coverage_ratio"] == 1.0
    assert report["stage_results"]["provider_scope"]["status"] == "passed"
    dimensions = {
        item["name"]: item
        for item in report["stage_results"]["quality_95"]["scorecard"]["dimensions"]
    }
    assert dimensions["provider_scope"]["score"] == 100
    assert dimensions["provider_e2e"]["score"] == 0


def test_readiness_requires_every_provider_declared_in_policy():
    policy = ReadinessPolicy.from_dict({
        "format_version": 1,
        "default_profile": "local",
        "readiness_scope": {
            "required_providers": ["meta", "google-ads", "tiktok"],
        },
        "profiles": {
            "local": ["code_contract", "dry_run", "provider_scope"],
        },
    })

    report = build_readiness_report(
        tool_source_report={
            "issues": [],
            "readiness_scope": _readiness_scope(),
        },
        dry_run_report={"executed": True, "failed": 0},
        policy=policy,
        profile="local",
    )

    assert report["stage_results"]["provider_scope"]["status"] == "failed"
    assert report["stage_results"]["provider_scope"]["missing_providers"] == [
        "google-ads",
        "tiktok",
    ]
    scorecard = report["stage_results"]["quality_95"]["scorecard"]
    dimensions = {item["name"]: item for item in scorecard["dimensions"]}
    assert dimensions["provider_scope"]["score"] == 0


def test_readiness_policy_requires_normalized_nonempty_provider_set():
    base = {
        "format_version": 1,
        "default_profile": "local",
        "profiles": {"local": ["code_contract"]},
    }
    with pytest.raises(ValueError, match="readiness_scope"):
        ReadinessPolicy.from_dict(base)

    for providers in ([], ["Meta"], ["meta", "meta"]):
        with pytest.raises(ValueError, match="required_providers"):
            ReadinessPolicy.from_dict({
                **base,
                "readiness_scope": {"required_providers": providers},
            })


def test_readiness_rejects_unexpected_enabled_provider():
    scopes = _readiness_scope()
    scopes["unexpected-provider"] = {
        "included": True,
        "total": 1,
        "covered": 1,
        "gaps": 0,
        "coverage_ratio": 1.0,
        "query_total": 1,
        "query_covered": 1,
        "managed_write_total": 0,
        "operations": [],
    }

    report = build_readiness_report(
        tool_source_report={"issues": [], "readiness_scope": scopes},
        dry_run_report={"executed": True, "failed": 0},
        policy=_policy(),
        profile="local",
    )

    assert report["stage_results"]["provider_scope"]["status"] == "failed"
    assert report["stage_results"]["provider_scope"]["unexpected_providers"] == [
        "unexpected-provider",
    ]


def test_provider_quality_ratios_use_the_weakest_included_provider():
    e2e, live = provider_evidence_ratios({
        "meta": {
            "included": True,
            "operations": [
                {
                    "readiness_category": "managed_write",
                    "evidence_level": "provider_e2e" if index < 3 else "code_contract",
                    "execution_status": "live_verified" if index < 2 else "dry_run_only",
                }
                for index in range(4)
            ],
        },
        "tiktok": {
            "included": True,
            "operations": [
                {
                    "readiness_category": "managed_write",
                    "evidence_level": "provider_e2e",
                    "execution_status": "live_verified",
                }
                for _ in range(20)
            ],
        },
    })

    assert e2e == 0.75
    assert live == 0.5


def test_query_evidence_ratio_uses_the_weakest_required_provider():
    ratio = provider_query_evidence_ratio({
        "meta": {
            "included": True,
            "operations": [
                {
                    "readiness_category": "query",
                    "evidence_level": (
                        "provider_e2e" if index < 3 else "code_contract"
                    ),
                }
                for index in range(4)
            ],
        },
        "tiktok": {
            "included": True,
            "operations": [
                {
                    "readiness_category": "query",
                    "evidence_level": "provider_e2e",
                }
                for _ in range(20)
            ],
        },
    }, required_providers=["meta", "tiktok", "google-ads"])

    assert ratio == 0.0


def test_readiness_scope_includes_all_reads_and_only_managed_hierarchy_writes():
    surface = [
        {"resource": "campaign", "action": "list", "method": "list_campaigns"},
        {"resource": "audience", "action": "get", "method": "get_audience"},
        {"resource": "campaign", "action": "create", "method": "create_campaign"},
        {"resource": "campaign", "action": "update", "method": "update_campaign"},
        {"resource": "campaign", "action": "delete", "method": "delete_campaign"},
        {
            "resource": "feed",
            "action": "list",
            "method": "list_feeds",
            "status": "not_applicable",
        },
        {"resource": "ad_set", "action": "create", "method": "create_adset"},
        {"resource": "creative", "action": "update", "method": "update_creative"},
        {"resource": "audience", "action": "create", "method": "create_audience"},
    ]
    metadata = {
        "readiness_enabled": True,
        "managed_write_resources": ["campaign", "ad_set", "ad", "creative"],
    }

    selected = select_readiness_surface(surface, metadata)

    assert [(item["resource"], item["action"]) for item in selected] == [
        ("campaign", "list"),
        ("audience", "get"),
        ("campaign", "create"),
        ("campaign", "update"),
        ("ad_set", "create"),
        ("creative", "update"),
    ]
    assert [item["readiness_category"] for item in selected] == [
        "query",
        "query",
        "managed_write",
        "managed_write",
        "managed_write",
        "managed_write",
    ]


def test_readiness_scope_can_exclude_a_provider_without_disabling_its_tools():
    surface = [
        {"resource": "campaign", "action": "list", "method": "list_campaigns"},
        {"resource": "creative", "action": "create", "method": "create_creative"},
    ]

    assert select_readiness_surface(surface, {
        "readiness_enabled": False,
        "managed_write_resources": [],
    }) == []


def test_readiness_action_audit_rejects_unclassified_actions():
    metadata = {
        "readiness_enabled": True,
        "managed_write_resources": ["campaign"],
    }

    assert validate_readiness_actions([
        {"resource": "campaign", "action": "list", "status": "implemented"},
        {"resource": "campaign", "action": "delete", "status": "implemented"},
        {"resource": "campaign", "action": "create", "status": "implemented"},
    ], metadata) == []
    errors = validate_readiness_actions([
        {"resource": "campaign", "action": "fetch_latest", "status": "implemented"},
    ], metadata)
    assert errors == [
        "surface[0].action has no readiness classification: 'fetch_latest'"
    ]


def test_readiness_action_audit_covers_all_target_provider_surfaces():
    from agents.ad_agent.tools.providers.google._surface_data import (
        API_SURFACE as google_surface,
        PROVIDER_METADATA as google_metadata,
    )
    from agents.ad_agent.tools.providers.meta._surface_data import (
        API_SURFACE as meta_surface,
        PROVIDER_METADATA as meta_metadata,
    )
    from agents.ad_agent.tools.providers.tiktok._surface_data import (
        API_SURFACE as tiktok_surface,
        PROVIDER_METADATA as tiktok_metadata,
    )

    for surface, metadata in (
        (google_surface, google_metadata),
        (meta_surface, meta_metadata),
        (tiktok_surface, tiktok_metadata),
    ):
        assert validate_readiness_actions(surface, metadata) == []


def test_not_applicable_surface_operations_require_a_reason():
    assert validate_surface([{
        "resource": "campaign",
        "action": "list",
        "status": "not_applicable",
    }]) == [
        "surface[0].gap is required for not_applicable operation"
    ]
    assert validate_surface([{
        "resource": "campaign",
        "action": "list",
        "status": "not_applicable",
        "gap": "Provider API version does not expose this resource",
    }]) == []


def test_readiness_scope_is_exposed_and_excludes_dv360_from_gate():
    from agents.ad_agent.scripts.audit_provider_tools import audit_provider_tools

    report = audit_provider_tools()

    assert "dv360" in report["platforms"]
    assert report["platforms"]["dv360"]["readiness_scope"]["included"] is False
    assert report["platforms"]["dv360"]["readiness_scope"]["total"] == 0
    for platform in ("meta", "google-ads", "tiktok"):
        scope = report["platforms"][platform]["readiness_scope"]
        assert scope["included"] is True
        assert scope["query_total"] > 0
        assert scope["managed_write_total"] > 0
        assert scope["covered"] + scope["gaps"] == scope["total"]


def test_provider_audit_links_only_operation_specific_provider_evidence():
    from agents.ad_agent.scripts.audit_provider_tools import audit_provider_tools

    report = audit_provider_tools()
    meta_operations = report["readiness_scope"]["meta"]["operations"]
    meta_campaign_create = next(
        item for item in meta_operations
        if item["resource"] == "campaign" and item["action"] == "create"
    )
    meta_campaign_update = next(
        item for item in meta_operations
        if item["resource"] == "campaign" and item["action"] == "update"
    )
    tiktok_operations = report["readiness_scope"]["tiktok"]["operations"]
    tiktok_lead_campaign = next(
        item for item in tiktok_operations
        if item["resource"] == "smart_plus_campaign"
        and item["action"] == "create"
    )

    assert meta_campaign_create["evidence_level"] == "provider_e2e"
    assert meta_campaign_create["execution_status"] == "live_verified"
    assert meta_campaign_update["evidence_level"] != "provider_e2e"
    assert meta_campaign_update["execution_status"] != "live_verified"
    assert tiktok_lead_campaign["execution_status"] == "live_verified"
    assert report["readiness_scope"]["google-ads"]["managed_write_live_verified"] == 0
    assert report["readiness_scope"]["google-ads"]["query_provider_e2e"] == 0


def test_provider_audit_links_query_evidence_only_to_exact_query_tool(tmp_path):
    import json

    from agents.ad_agent.scripts.audit_provider_tools import audit_provider_tools

    raw = json.loads(
        Path("agents/ad_agent/contracts/provider_e2e_evidence.json").read_text(
            encoding="utf-8"
        )
    )
    raw["runs"][0]["queries"] = [{
        "resource": "ad",
        "action": "list",
        "tool": "meta_list_campaigns",
        "outcome": "passed",
    }]
    custom_evidence = tmp_path / "provider-evidence.json"
    custom_evidence.write_text(json.dumps(raw), encoding="utf-8")

    report = audit_provider_tools(custom_evidence)
    campaign_list = next(
        item for item in report["readiness_scope"]["meta"]["operations"]
        if item["resource"] == "campaign" and item["action"] == "list"
    )
    assert campaign_list["evidence_level"] != "provider_e2e"
    assert campaign_list["evidence_records"] == []

    raw["runs"][0]["queries"] = [{
        "resource": "campaign",
        "action": "list",
        "tool": "meta_list_campaigns",
        "outcome": "passed",
    }]
    custom_evidence.write_text(json.dumps(raw), encoding="utf-8")

    report = audit_provider_tools(custom_evidence)
    campaign_list = next(
        item for item in report["readiness_scope"]["meta"]["operations"]
        if item["resource"] == "campaign" and item["action"] == "list"
    )

    assert campaign_list["evidence_level"] == "provider_e2e"
    assert campaign_list["evidence_records"][0]["tool"] == "meta_list_campaigns"


def test_release_readiness_uses_default_controlled_provider_evidence(monkeypatch):
    from agents.ad_agent.scripts import release_readiness

    expected_evidence_path = (
        release_readiness.ROOT
        / "agents"
        / "ad_agent"
        / "contracts"
        / "provider_e2e_evidence.json"
    )
    audit_arguments = {}

    def fake_audit_provider_tools(evidence_path=None):
        audit_arguments["evidence_path"] = evidence_path
        return {"issues": [], "official_inventory": {}}

    monkeypatch.setattr(
        release_readiness, "audit_provider_tools", fake_audit_provider_tools
    )
    monkeypatch.setattr(release_readiness, "_contract_gate_errors", lambda: [])
    monkeypatch.setattr(
        release_readiness,
        "run_harness",
        lambda *_args: {"executed": True, "failed": 0, "passed": 1},
    )
    monkeypatch.setattr(
        release_readiness,
        "_run_skill_up_cases",
        lambda: {"executed": True, "failed": 0, "passed": 1},
    )
    monkeypatch.setattr(
        release_readiness,
        "_run_generic_platform_smoke",
        lambda: {"passed": True},
    )
    monkeypatch.setattr(
        release_readiness,
        "_run_reliability_evidence",
        lambda: {"executed": True, "passed": True},
    )
    monkeypatch.setattr(
        release_readiness, "_application_service_module_lines", lambda: 300
    )

    report = release_readiness.build_report(
        "local",
        release_readiness.ROOT
        / "agents"
        / "ad_agent"
        / "contracts"
        / "readiness_policy.json",
    )

    assert audit_arguments["evidence_path"] == expected_evidence_path
    assert report["controlled_evidence"]["run_count"] == 9
    assert report["controlled_evidence"]["valid"] is True
