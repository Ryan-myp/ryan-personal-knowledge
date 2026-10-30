"""Creation evidence is version/account bound and never grants execution rights."""

from copy import deepcopy

import pytest

from agents.applications.advertising.creation.verification import (
    CreationVerificationCatalog,
    template_values_digest,
)


def template(**overrides):
    return {
        "catalog_key": "demo.traffic",
        "provider": "meta",
        "blueprint_id": "meta.traffic",
        "blueprint_version": "1.0.0",
        "account_id": "123",
        "source": "builtin",
        "values": {"campaign.name": "Paused demo"},
        "verification_status": "live_verified",
        **overrides,
    }


def memory(**overrides):
    return {
        "template_key": "demo.traffic",
        "provider": "meta",
        "blueprint_id": "meta.traffic",
        "blueprint_version": "1.0.0",
        "test_account": "123",
        "template_values_sha256": template_values_digest(template()["values"]),
        "verification_state": "live_verified",
        "last_verified_at": "2026-10-26",
        "coverage": {
            "campaign_create_update_read": "live_pass",
            "ad_set_create_update_read": "live_pass",
            "ad_create_update_read": "live_pass",
        },
        **overrides,
    }


def test_exact_evidence_has_operation_scope_and_is_defensively_copied():
    catalog = CreationVerificationCatalog([memory()])
    result = catalog.summarize(template())
    assert result["status"] == "live_verified"
    assert result["match"] == "exact"
    assert result["verified_at"] == "2026-10-26"
    assert len(result["operations"]) == 3
    assert "权限" in result["notice"]
    result["operations"].clear()
    assert len(catalog.summarize(template())["operations"]) == 3


@pytest.mark.parametrize("changes", [
    {"blueprint_version": "1.1.0"},
    {"values": {"campaign.name": "Changed"}},
    {"account_id": "456"},
    {"provider": "tiktok"},
    {"source": "user"},
])
def test_unrelated_evidence_does_not_verify_a_template(changes):
    result = CreationVerificationCatalog([memory()]).summarize(template(**changes))
    assert result["status"] != "live_verified"
    assert result["match"] != "exact"


def test_partial_coverage_overrides_an_optimistic_top_level_label():
    row = memory(coverage={
        "campaign": "live_pass", "ad_group": "live_pass", "ad": "not_run",
    })
    result = CreationVerificationCatalog([row]).summarize(template())
    assert result["status"] == "partial_live_verified"
    assert any(item["state"] == "not_run" for item in result["operations"])


def test_blocked_evidence_keeps_successful_parents_without_claiming_a_complete_ad():
    row = memory(verification_state="blocked_by_provider", coverage={
        "campaign_create": "live_pass", "ad_create": "provider_rejected",
    })
    result = CreationVerificationCatalog([row]).summarize(template())
    assert result["status"] == "provider_limited"
    assert result["blockers"]
    assert {item["state"] for item in result["operations"]} == {"passed", "failed"}


def test_no_evidence_cannot_inherit_a_catalog_verification_claim():
    result = CreationVerificationCatalog().summarize(template())
    assert result["status"] == "pending_live_verification"
    assert result["operations"] == []


def test_legacy_runs_without_a_template_version_are_historical_only():
    legacy = {
        "provider": "meta", "test_account": "123", "campaign_type": "TRAFFIC",
        "status": "live_verified", "resources": {
            "campaign": {"create": "passed", "readback": "passed"},
            "ad": {"create": "not_run"},
        },
    }
    definition = template(campaign_type="TRAFFIC")
    result = CreationVerificationCatalog(legacy_runs=[legacy]).summarize(definition)
    assert result["status"] == "pending_live_verification"
    assert result["match"] == "historical"
    assert result["historical_operations"]


def test_known_same_account_blocker_remains_visible_after_version_upgrade():
    row = memory(verification_state="blocked_by_provider", coverage={"campaign": "provider_rejected"})
    result = CreationVerificationCatalog([row]).summarize(template(blueprint_version="1.1.0"))
    assert result["status"] == "pending_live_verification"
    assert result["blockers"]
    other = CreationVerificationCatalog([row]).summarize(template(account_id="456"))
    assert not other["blockers"]


def test_empty_coverage_or_unknown_states_never_count_as_passed():
    for coverage in ({}, {"campaign": "unknown"}, {"campaign": "invented_pass"}):
        result = CreationVerificationCatalog([memory(coverage=coverage)]).summarize(template())
        assert result["status"] != "live_verified"


def test_catalog_does_not_mutate_input_or_echo_untrusted_evidence_text():
    row = memory(remaining_gap="access_token=must-not-appear",
                 coverage={"bad<script>": "failed"})
    original = deepcopy(row)
    result = CreationVerificationCatalog([row]).summarize(template())
    assert row == original
    assert "must-not-appear" not in str(result)
    assert "<script>" not in str(result)


@pytest.mark.parametrize("coverage", [[], "passed", 1, [{"campaign": "live_pass"}]])
def test_malformed_coverage_fails_closed_without_breaking_template_listing(coverage):
    result = CreationVerificationCatalog([memory(coverage=coverage)]).summarize(template())
    assert result["status"] != "live_verified"


def test_bounded_display_cannot_hide_a_later_failed_operation():
    coverage = {f"operation_{index}": "live_pass" for index in range(90)}
    coverage["last_operation"] = "failed"
    result = CreationVerificationCatalog([memory(coverage=coverage)]).summarize(template())
    assert result["status"] != "live_verified"
    assert len(result["operations"]) <= 80


@pytest.mark.parametrize("field", ["provider", "test_account", "template_key"])
def test_invalid_evidence_identity_does_not_raise_or_match(field):
    result = CreationVerificationCatalog([memory(**{field: ["invalid"]})]).summarize(template())
    assert result["status"] == "pending_live_verification"


def test_malformed_legacy_resources_remain_unverified():
    row = {"provider": "meta", "test_account": "123", "campaign_type": "TRAFFIC", "resources": ["bad"]}
    result = CreationVerificationCatalog(legacy_runs=[row]).summarize(template(campaign_type="TRAFFIC"))
    assert result["status"] == "pending_live_verification"


def test_malformed_legacy_resource_entries_remain_visible_as_unknown():
    row = {
        "provider": "meta", "test_account": "123", "campaign_type": "TRAFFIC",
        "resources": {
            "campaign": {"create": "passed"},
            "<script>": {"ad": {"create": "passed"}},
            "ad": {"unexpected_operation": "passed"},
        },
    }
    result = CreationVerificationCatalog(legacy_runs=[row]).summarize(
        template(campaign_type="TRAFFIC")
    )
    states = [item["state"] for item in result["historical_operations"]]
    assert states.count("unknown") == 2
    assert "<script>" not in str(result)


def test_evidence_date_cannot_echo_arbitrary_text():
    result = CreationVerificationCatalog([memory(last_verified_at="access_token=must-not-echo")]).summarize(template())
    assert "must-not-echo" not in str(result)
