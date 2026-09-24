import json
from pathlib import Path

from agents.ad_agent.domain.ad.provider_evidence import (
    build_provider_evidence_report,
    load_provider_evidence,
    validate_provider_evidence,
)
from agents.ad_agent.scripts.provider_e2e_runner import (
    ProviderE2ERequest,
    ProviderE2ERunner,
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
    assert report["providers"]["meta"]["query_evidence"] == []
    meta_operations = report["providers"]["meta"]["operation_evidence"]
    attributed_meta_operations = [item for item in meta_operations if item["tool"]]
    assert len(attributed_meta_operations) == 6
    assert all(item["action"] == "create" for item in attributed_meta_operations)
    assert all(
        item["evidence_level"] == "provider_e2e"
        for item in attributed_meta_operations
    )
    assert all(
        item["execution_status"] == "live_verified"
        for item in attributed_meta_operations
    )
    assert not any(
        item["tool"] and item["action"] == "update"
        for item in meta_operations
    )
    tiktok_operations = report["providers"]["tiktok"]["operation_evidence"]
    assert any(
        item["tool"] == "tiktok_smart_plus_create_campaign"
        and item["campaign_types"] == ["LEAD_GENERATION"]
        and item["execution_status"] == "live_verified"
        for item in tiktok_operations
    )
    google_operations = report["providers"]["google-ads"]["operation_evidence"]
    assert google_operations
    assert not any(item["tool"] for item in google_operations)
    assert not any(
        item["evidence_level"] == "provider_e2e"
        for item in google_operations
    )


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

    raw["safety"]["credentials_included"] = False
    raw["runs"][0].pop("access_token")
    raw["runs"][0]["resources"]["campaign"]["id"] = "campaign-1"
    errors = validate_provider_evidence(raw)
    assert any("readback is not passed" in error for error in errors)


def test_invalid_tool_attribution_is_rejected_without_echoing_its_value():
    raw = {
        "schema_version": "1.0",
        "generated_at": "2026-09-24",
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
            "test_account": "test-account",
            "campaign_type": "TRAFFIC",
            "status": "partial_live_verified",
            "resources": {
                "campaign": {
                    "tool": "client_secret=must-not-echo",
                    "id": "campaign-1",
                    "status": "PAUSED",
                    "create": "passed",
                }
            },
        }],
    }

    errors = validate_provider_evidence(raw)

    assert any("tool must be a valid Tool name" in error for error in errors)
    assert "must-not-echo" not in " ".join(errors)


def test_loader_returns_redacted_summary_and_keeps_raw_ids_out_of_report(tmp_path):
    path = tmp_path / "evidence.json"
    raw = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))
    path.write_text(json.dumps(raw), encoding="utf-8")

    report = load_provider_evidence(path)

    assert report["valid"] is True
    serialized = json.dumps(report, ensure_ascii=False)
    assert "2806375919473667" not in serialized
    assert report["providers"]["meta"]["account_previews"] == ["…3667"]
    assert "120251262026940251" not in serialized


def test_operation_evidence_needs_exact_tool_action_readback_and_paused_status():
    raw = {
        "schema_version": "1.0",
        "generated_at": "2026-09-24",
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
            "test_account": "test-account",
            "campaign_type": "TRAFFIC",
            "status": "partial_live_verified",
            "resources": {
                "campaign": {
                    "tool": "meta_create_campaign",
                    "update_tool": "meta_update_campaign",
                    "id": "campaign-1",
                    "status": "PAUSED",
                    "create": "passed",
                    "create_readback": "passed",
                    "update": "passed",
                    "update_readback": "failed",
                }
            },
        }],
    }

    operations = build_provider_evidence_report(raw)["providers"]["meta"][
        "operation_evidence"
    ]
    by_action = {item["action"]: item for item in operations}

    assert by_action["create"]["tool"] == "meta_create_campaign"
    assert by_action["create"]["execution_status"] == "live_verified"
    assert by_action["update"]["tool"] == "meta_update_campaign"
    assert by_action["update"]["evidence_level"] == "provider_e2e"
    assert by_action["update"]["execution_status"] == "dry_run_only"


def test_query_evidence_is_separate_from_write_evidence_and_redacted():
    raw = {
        "schema_version": "1.0",
        "generated_at": "2026-09-24",
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
            "test_account": "test-account",
            "campaign_type": "TRAFFIC",
            "status": "read_verified",
            "resources": {},
            "queries": [{
                "resource": "campaign",
                "action": "list",
                "tool": "meta_list_campaigns",
                "outcome": "passed",
            }],
        }],
    }

    assert validate_provider_evidence(raw) == []
    evidence = build_provider_evidence_report(raw)["providers"]["meta"][
        "query_evidence"
    ]

    assert evidence == [{
        "readiness_category": "query",
        "resource": "campaign",
        "action": "list",
        "tool": "meta_list_campaigns",
        "campaign_types": ["TRAFFIC"],
        "outcome": "passed",
        "evidence_level": "provider_e2e",
    }]


def test_query_only_evidence_does_not_require_a_write_operation():
    raw = {
        "schema_version": "1.0",
        "generated_at": "2026-09-24",
        "scope": "provider_query_e2e",
        "safety": {
            "test_accounts_only": True,
            "new_resources_paused": True,
            "deleted": False,
            "credentials_included": False,
            "raw_provider_responses_included": False,
        },
        "runs": [{
            "provider": "meta",
            "test_account": "test-account",
            "campaign_type": "TRAFFIC",
            "status": "read_verified",
            "resources": {},
            "queries": [{
                "resource": "campaign",
                "action": "list",
                "tool": "meta_list_campaigns",
                "outcome": "passed",
            }],
        }],
    }

    assert validate_provider_evidence(raw) == []
    report = build_provider_evidence_report(raw)
    assert report["providers"]["meta"]["operation_evidence"] == []
    assert report["providers"]["meta"]["query_evidence"][0]["evidence_level"] == (
        "provider_e2e"
    )


def test_provider_e2e_runner_requires_live_gates_and_redacts_evidence():
    calls = []

    class Adapter:
        def execute(self, operation, payload):
            calls.append((operation, dict(payload)))
            if operation == "create_campaign":
                return {"id": "campaign-123", "status": "PAUSED"}
            if operation == "read_campaign":
                return {"id": payload["id"], "status": "PAUSED"}
            raise AssertionError(operation)

    runner = ProviderE2ERunner(
        adapter=Adapter(),
        allowed_test_accounts={"meta": {"test-account"}},
    )
    result = runner.run(ProviderE2ERequest(
        provider="meta",
        account_ref="test-account",
        campaign_type="TRAFFIC",
        execution_mode="live",
        confirmed=True,
        operations=("create_campaign",),
        require_paused=True,
        idempotency_key="test-run-meta-traffic-1",
    ))

    assert result["status"] == "live_verified"
    assert result["resources"]["campaign"]["readback"] == "passed"
    assert result["resources"]["campaign"]["id"] == "…-123"
    assert "test-account" not in json.dumps(result)
    assert [item[0] for item in calls] == ["create_campaign", "read_campaign"]


def test_provider_e2e_runner_rejects_unsafe_write_request_without_adapter_call():
    class Adapter:
        def execute(self, _operation, _payload):
            raise AssertionError("must not execute")

    runner = ProviderE2ERunner(
        adapter=Adapter(),
        allowed_test_accounts={"meta": {"test-account"}},
    )
    result = runner.run(ProviderE2ERequest(
        provider="meta",
        account_ref="outside-account",
        campaign_type="TRAFFIC",
        execution_mode="dry_run",
        confirmed=False,
        operations=("create_campaign",),
        require_paused=True,
        idempotency_key="unsafe-run",
    ))

    assert result["status"] == "blocked"
    assert result["blocked_reason"] == "live_execution_required"
