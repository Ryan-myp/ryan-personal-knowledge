import json
from pathlib import Path

from agents.ad_agent.domain.ad.provider_evidence import (
    build_provider_evidence_report,
    load_provider_evidence,
    validate_provider_evidence,
)


EVIDENCE_PATH = Path(
    "agents/ad_agent/contracts/provider_e2e_evidence.json"
)


def test_checked_in_provider_evidence_is_valid_and_operation_specific():
    raw = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))

    errors = validate_provider_evidence(raw)
    report = build_provider_evidence_report(raw)

    assert errors == []
    assert report["valid"] is True
    assert report["run_count"] == 9
    assert report["providers"]["meta"]["fully_verified_runs"] == 2
    assert report["providers"]["tiktok"]["partial_runs"] == 4
    assert report["providers"]["tiktok"]["limited_runs"] == 1
    assert report["providers"]["google-ads"]["campaign_types"] == [
        "APP", "PERFORMANCE_MAX", "SHOPPING"
    ]
    assert report["providers"]["tiktok"]["operations"]["ad:create"]["provider_rejected"] == 2


def test_provider_evidence_rejects_unsafe_or_ambiguous_claims():
    raw = {
        "schema_version": "1.0",
        "generated_at": "2026-09-18",
        "scope": "campaign_and_descendant_create_update",
        "safety": {
            "test_accounts_only": False,
            "new_resources_paused": True,
            "deleted": False,
            "credentials_included": True,
            "raw_provider_responses_included": False,
        },
        "runs": [{
            "provider": "meta",
            "test_account": "test",
            "campaign_type": "TRAFFIC",
            "status": "live_verified",
            "access_token": "should-never-be-here",
            "resources": {
                "campaign": {
                    "create": "passed",
                    "id": None,
                }
            },
        }],
    }

    errors = validate_provider_evidence(raw)

    assert any("test_accounts_only" in error for error in errors)
    assert any("credentials_included" in error for error in errors)
    assert any("credential-shaped field" in error for error in errors)
    assert any("create passed but id is missing" in error for error in errors)


def test_loader_returns_redacted_summary_and_keeps_raw_ids_out_of_report(tmp_path):
    path = tmp_path / "evidence.json"
    raw = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))
    path.write_text(json.dumps(raw), encoding="utf-8")

    report = load_provider_evidence(path)

    assert report["valid"] is True
    serialized = json.dumps(report, ensure_ascii=False)
    assert "2806375919473667" not in serialized
    assert report["providers"]["meta"]["account_previews"] == ["…3667"]
