"""Regression tests for the evidence-based release gate."""

from agents.ad_agent.domain.ad.release_readiness import ReadinessPolicy, build_readiness_report
from agents.ad_agent.scripts.provider_contract_harness import run_harness


def _policy() -> ReadinessPolicy:
    return ReadinessPolicy.from_dict({
        "format_version": 1,
        "default_profile": "local",
        "profiles": {
            "local": ["code_contract", "dry_run"],
            "release": ["code_contract", "dry_run", "provider_e2e", "live_verified"],
        },
    })


def test_local_profile_does_not_promote_local_stub_to_provider_e2e():
    report = build_readiness_report(
        capability_report={
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
        capability_report={"issues": [], "official_inventory": {}},
        dry_run_report={"executed": True, "failed": 0},
        policy=_policy(),
        profile="release",
    )

    assert report["passed"] is False
    assert report["blocking_stages"] == ["provider_e2e", "live_verified"]


def test_provider_contract_harness_covers_all_builtin_provider_factories():
    report = run_harness(
        "agents/ad_agent/contracts/provider_contract_scenarios.json"
    )

    assert report["executed"] is True
    assert report["failed"] == 0
    assert report["passed"] == 4
    assert all(row["client_calls"] == 1 for row in report["scenarios"])
