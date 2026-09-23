"""Regression tests for the evidence-based release gate."""

from agents.ad_agent.domain.ad.quality_scorecard import (
    QUALITY_THRESHOLD,
    build_quality_scorecard,
    provider_evidence_ratios,
)
from agents.ad_agent.domain.ad.release_readiness import (
    ReadinessPolicy,
    build_readiness_report,
)
from agents.ad_agent.scripts.provider_contract_harness import run_harness


def _policy() -> ReadinessPolicy:
    return ReadinessPolicy.from_dict({
        "format_version": 1,
        "default_profile": "local",
        "profiles": {
            "local": ["code_contract", "dry_run"],
            "release": [
                "code_contract",
                "dry_run",
                "provider_e2e",
                "live_verified",
                "quality_95",
            ],
        },
    })


def test_local_profile_does_not_promote_local_stub_to_provider_e2e():
    report = build_readiness_report(
        tool_source_report={
            "issues": [],
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
    assert report["stage_results"]["provider_e2e"]["status"] == "not_verified"
    assert report["stage_results"]["live_verified"]["status"] == "not_verified"


def test_release_profile_blocks_without_operation_specific_evidence():
    report = build_readiness_report(
        tool_source_report={"issues": [], "official_inventory": {}},
        dry_run_report={"executed": True, "failed": 0},
        policy=_policy(),
        profile="release",
    )

    assert report["passed"] is False
    assert report["blocking_stages"] == [
        "provider_e2e",
        "live_verified",
        "quality_95",
    ]
    scorecard = report["stage_results"]["quality_95"]["scorecard"]
    assert scorecard["passed"] is False
    assert {
        "generic_platform",
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
            "total": 4,
            "evidence_levels": {"provider_e2e": 3},
            "execution_statuses": {"live_verified": 2},
        },
        "tiktok": {
            "total": 6,
            "evidence_levels": {"provider_e2e": 6},
            "execution_statuses": {"live_verified": 5},
        },
    })

    assert e2e == 0.9
    assert live == 0.7
