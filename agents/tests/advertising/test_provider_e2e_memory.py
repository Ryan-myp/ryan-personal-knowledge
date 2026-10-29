import json
import hashlib
import re
import shutil
from pathlib import Path

import pytest

from agents.applications.advertising.knowledge.wiki import (
    MarkdownWikiKnowledgeProvider,
)
from scripts.advertising.provider_live_e2e_memory import (
    append_live_e2e_observation,
    build_live_e2e_memory_report,
    hierarchy_reuse_state,
    load_live_e2e_memory,
    require_new_hierarchy_authorization,
    resolve_template_memory,
)
from scripts.advertising.campaign_service_e2e import _created_live_resources


ROOT = Path(__file__).resolve().parents[3]
MEMORY_PATH = (
    ROOT / "agents/tools/advertising/contracts/provider_live_e2e_memory.json"
)
TEMPLATE_PATH = (
    ROOT
    / "agents/applications/advertising/contracts/builtin_creation_templates.json"
)
E2E_TEST_PATH = ROOT / "agents/tests/advertising/test_campaign_service_e2e.py"
GOOGLE_APP_GUARD_TEST_PATH = (
    ROOT / "agents/tests/advertising/test_google_app_delivery_guard.py"
)
PAYLOAD_TEST_PATH = (
    ROOT / "agents/tests/advertising/test_provider_payload_contracts.py"
)
TEMPLATE_TEST_PATH = ROOT / "agents/tests/advertising/test_creation_templates.py"
META_TEMPLATE_TEST_PATH = (
    ROOT / "agents/tests/advertising/test_meta_creation_templates.py"
)

EXPECTED_TEMPLATES = {
    ("google-ads", "PERFORMANCE_MAX"): "google.test.performance-max",
    ("google-ads", "SHOPPING"): "google.test.shopping",
    ("google-ads", "APP"): "google.test.app",
    ("meta", "TRAFFIC"): "meta.test.traffic",
    ("meta", "CATALOG_SALES"): "meta.test.catalog-sales",
    ("meta", "CONVERSION"): "meta.test.conversion",
    ("meta", "APP_PROMOTION"): "meta.test.app-promotion",
    ("tiktok", "TRAFFIC"): "tiktok.test.traffic",
    ("tiktok", "PRODUCT_SALES"): "tiktok.test.sales",
    ("tiktok", "APP_PROMOTION"): "tiktok.test.app-promotion",
}


def _load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_live_e2e_memory_is_complete_and_bound_to_current_templates():
    memory = _load_json(MEMORY_PATH)
    templates = {
        row["key"]: row
        for row in _load_json(TEMPLATE_PATH)["templates"]
    }
    rows = memory["campaign_types"]
    actual = {
        (row["provider"], row["campaign_type"], row["test_account"]): row["template_key"]
        for row in rows
    }
    expected = {
        (provider, campaign_type, templates[key]["account_id"]): key
        for (provider, campaign_type), key in EXPECTED_TEMPLATES.items()
    }
    expected.update({
        ("google-ads", "PERFORMANCE_MAX", "7574609568"):
            "google.test.7574609568.performance-max",
        ("google-ads", "SHOPPING", "7574609568"):
            "google.test.7574609568.shopping",
        ("google-ads", "APP", "7574609568"):
            "google.test.7574609568.app",
    })

    assert actual == expected
    assert memory["scope"]["excluded"] == [
        {
            "provider": "tiktok",
            "campaign_type": "LEAD_GENERATION",
            "reason": "User explicitly deferred TikTok Lead for this test pass.",
        }
    ]

    allowed_states = {
        "live_verified",
        "partial_live",
        "blocked_by_provider",
        "not_run",
    }
    for row in rows:
        template = templates[row["template_key"]]
        assert row["blueprint_id"] == template["blueprint_id"]
        assert row["blueprint_version"] == template["blueprint_version"]
        assert row["verification_state"] in allowed_states
        assert row["critical_fields"]
        assert row["evidence_refs"]
        configured_accounts = memory["scope"]["test_accounts"][row["provider"]]
        if isinstance(configured_accounts, str):
            configured_accounts = [configured_accounts]
        assert row["test_account"] in configured_accounts
        if row["verification_state"] in {"not_run", "blocked_by_provider"} and not row[
            "prior_live_write_observed"
        ]:
            assert row["prior_live_write_observed"] is False
            assert row["known_live_hierarchies"] == []
            assert row["remaining_gap"]
        else:
            assert row["prior_live_write_observed"] is True
            assert row["known_live_hierarchies"]
        for field, expected in row["expected_status_values"].items():
            assert template["values"][field] == expected
        value_digest = hashlib.sha256(
            json.dumps(
                template["values"],
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        assert row["template_values_sha256"] == value_digest
        for field in row["critical_fields"]:
            assert field in template["values"]
        if row["verification_state"] != "live_verified":
            assert row["remaining_gap"]


def test_live_e2e_memory_supports_a_second_account_without_prior_writes(tmp_path):
    shutil.copytree(ROOT / "agents", tmp_path / "agents")
    memory_path = tmp_path / "agents/tools/advertising/contracts/provider_live_e2e_memory.json"
    template_path = (
        tmp_path
        / "agents/applications/advertising/contracts/builtin_creation_templates.json"
    )
    memory = _load_json(memory_path)
    catalog = _load_json(template_path)
    account = "7574609568"
    configured_accounts = memory["scope"]["test_accounts"]["google-ads"]
    prior_account = next(
        item for item in configured_accounts if item != account
    )
    second_account_rows = [
        row for row in memory["campaign_types"]
        if row["provider"] == "google-ads" and row["test_account"] == account
    ]
    second_account_keys = {row["template_key"] for row in second_account_rows}
    second_account_templates = [
        row for row in catalog["templates"] if row["key"] in second_account_keys
    ]
    assert len(second_account_rows) == 3
    assert all(
        row["verification_state"] in {"not_run", "blocked_by_provider"}
        for row in second_account_rows
    )

    # Reconstruct the prior single-account state, then add the second account
    # records back to the isolated copy exactly as a migration would.
    memory["campaign_types"] = [
        row for row in memory["campaign_types"]
        if row["template_key"] not in second_account_keys
    ]
    catalog["templates"] = [
        row for row in catalog["templates"] if row["key"] not in second_account_keys
    ]
    memory["scope"]["test_accounts"]["google-ads"] = prior_account
    memory_path.write_text(json.dumps(memory, ensure_ascii=False, indent=2), encoding="utf-8")
    template_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")

    memory["scope"]["test_accounts"]["google-ads"] = [prior_account, account]
    memory["campaign_types"].extend(second_account_rows)
    catalog["templates"].extend(second_account_templates)
    memory_path.write_text(json.dumps(memory, ensure_ascii=False, indent=2), encoding="utf-8")
    template_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")

    loaded = load_live_e2e_memory(tmp_path)
    pmax = next(
        item for item in second_account_rows
        if item["campaign_type"] == "PERFORMANCE_MAX"
    )
    resolved = resolve_template_memory(
        tmp_path,
        provider="google-ads",
        account_id=account,
        template_id=pmax["template_key"],
        api_template={
            "provider": "google-ads",
            "account_id": account,
            "blueprint_id": pmax["blueprint_id"],
            "blueprint_version": pmax["blueprint_version"],
            "status": "active",
        },
    )

    assert len(loaded["campaign_types"]) == len(memory["campaign_types"])
    assert resolved["verification_state"] == "blocked_by_provider"
    assert resolved["recovery_plan"]["action"] == "respect_provider_block"
    assert resolved["hierarchy_reuse"]["requires_reconciliation"] is False
    assert not resolved["known_live_hierarchies"]

    observation = append_live_e2e_observation(
        tmp_path,
        event_type="attempt_started",
        attempt_id="google-7574609568-pmax-create",
        phase_id="google-7574609568-pmax-create:1",
        phase=1,
        provider="google-ads",
        account_id=account,
        template_id=pmax["template_key"],
        blueprint_version=pmax["blueprint_version"],
        template_values_sha256=pmax["template_values_sha256"],
        case_id="google-7574609568-pmax-create",
        outcome="pending",
    )
    assert observation["account_id"] == account


def test_live_e2e_memory_encodes_paused_creation_and_non_overclaimed_evidence():
    memory = _load_json(MEMORY_PATH)
    templates = {
        row["key"]: row
        for row in _load_json(TEMPLATE_PATH)["templates"]
    }

    assert memory["safety"]["test_accounts_only"] is True
    assert memory["safety"]["dry_run_is_not_live_evidence"] is True
    assert memory["safety"]["new_campaign_hierarchy_must_remain_paused"] is True

    for row in memory["campaign_types"]:
        if row["provider"] in {"google-ads", "meta"}:
            assert row["creation_status"] == "PAUSED"
        elif row["campaign_type"] == "APP_PROMOTION":
            assert row["creation_status"] == 0
        else:
            assert row["creation_status"] == "DISABLE"

        for evidence in row["evidence_refs"]:
            assert evidence["evidence_level"] in {
                "live_chat_and_provider",
                "live_chat_no_provider_effect",
                "tracked_live_evidence_record",
                "local_regression_only",
                "template_contract",
            }
            assert evidence["case_ref"]

    tiktok_app = next(
        row for row in memory["campaign_types"]
        if row["provider"] == "tiktok"
        and row["campaign_type"] == "APP_PROMOTION"
    )
    assert tiktok_app["verification_state"] == "live_verified"
    assert tiktok_app["coverage"]["current_template_paused_create"] == "live_pass"
    assert tiktok_app["coverage"]["ad_create_and_exact_get"] == "live_pass"
    assert tiktok_app["coverage"]["ad_app_name_matches_selected_app"] == "live_pass"
    assert tiktok_app["coverage"]["ad_group_list"] == "live_pass"
    assert tiktok_app["coverage"]["real_mmp_attribution"] == "not_verified"
    latest_hierarchy = tiktok_app["known_live_hierarchies"][-1]
    assert latest_hierarchy["resource_ids"] == {
        "campaign": "1880085399156082",
        "ad_group": "1880085378463186",
        "ad": "1880085435261650",
    }
    assert latest_hierarchy["delivery_statuses"] == {
        "campaign": "DISABLE",
        "ad_group": "DISABLE",
        "ad": "DISABLE",
    }

    tiktok_template = templates["tiktok.test.app-promotion"]
    assert tiktok_template["verification_status"] == "live_verified_with_provider_limits"
    assert "1879196654038418" in tiktok_template["verified_scope"]
    assert "真实 MMP 归因未验证" in tiktok_template["verified_scope"]

    template_hierarchy = tiktok_app["known_live_hierarchies"][-2]
    assert template_hierarchy["selected_identity_id"] == (
        tiktok_template["values"]["ad.identity_id"]
    )
    assert template_hierarchy["template_values_sha256"] == next(
        row["template_values_sha256"]
        for row in memory["campaign_types"]
        if row["template_key"] == "tiktok.test.app-promotion"
    )
    assert len(template_hierarchy["readback_refs"]) == 3


def test_google_app_template_requires_enabled_ad_under_paused_parents():
    memory = _load_json(MEMORY_PATH)
    template = next(
        row for row in _load_json(TEMPLATE_PATH)["templates"]
        if row["key"] == "google.test.app"
    )
    record = next(
        row for row in memory["campaign_types"]
        if row["template_key"] == "google.test.app"
    )

    assert template["verification_status"] == "partial_live_verified"
    assert template["values"]["campaign.status"] == "PAUSED"
    assert template["values"]["ad_group.status"] == "PAUSED"
    assert template["values"]["ad.status"] == "ENABLED"
    assert record["verification_state"] == "partial_live"
    assert record["expected_status_values"] == {
        "campaign.status": "PAUSED",
        "ad_group.status": "PAUSED",
        "ad.status": "ENABLED",
    }
    assert record["coverage"]["app_ad_create_and_readback"] == "not_run"

    existing_hierarchy = next(
        hierarchy for hierarchy in record["known_live_hierarchies"]
        if hierarchy["resource_ids"].get("campaign") == "24366769615"
    )
    assert existing_hierarchy["resource_ids"] == {
        "campaign": "24366769615",
        "ad_group": "204899076647",
    }
    assert existing_hierarchy["delivery_statuses"] == {
        "campaign": "PAUSED",
        "ad_group": "PAUSED",
    }
    historical_enabled_hierarchy = next(
        hierarchy
        for hierarchy in record["known_live_hierarchies"]
        if hierarchy["resource_ids"].get("ad") == "199870458~823804628628"
    )
    assert historical_enabled_hierarchy["delivery_statuses"]["ad"] == "ENABLED"
    assert historical_enabled_hierarchy["resume_safe"] is False

    finding = next(
        row for row in memory["known_findings"]
        if row["id"] == "google_app_ad_pause_limit"
    )
    assert finding["status"] == "provider_limited"
    assert "App Ad to ENABLED" in finding["fix"]
    assert "keep Campaign and Ad Group PAUSED" in finding["fix"]


def test_google_app_rejected_paused_attempt_remains_auditable_without_raw_outputs():
    memory = _load_json(MEMORY_PATH)
    record = next(
        row for row in memory["campaign_types"]
        if row["template_key"] == "google.test.app"
    )
    rejected_attempt = next(
        row for row in memory["known_findings"]
        if row["id"] == "google_app_ad_pause_limit"
    )
    assert record["verification_state"] == "partial_live"
    assert any(
        "google-app-ad-create-child-20261016-r5" in str(reference)
        for evidence in record["evidence_refs"]
        for reference in evidence.values()
        if isinstance(reference, str)
    )
    assert "Cannot pause an adgroup ad with this ad type" in (
        rejected_attempt["root_cause"]
    )
    assert "HTTP 401 then 403" in record["remaining_gap"]
    assert "no write was sent" in record["remaining_gap"]

    journal_rows = [
        json.loads(line)
        for line in (
            ROOT
            / "agents/tools/advertising/contracts/"
            / "provider_live_e2e_observations.jsonl"
        ).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    attempt_rows = [
        row for row in journal_rows
        if row.get("case_id") == "google-app-ad-create-child-20261016-r5"
    ]
    assert {row["event_type"] for row in attempt_rows} == {
        "attempt_started", "attempt_completed",
    }
    assert next(
        row for row in attempt_rows if row["event_type"] == "attempt_completed"
    )["outcome"] == "provider_rejected"


def test_google_app_paused_provider_rejection_stays_documented():
    memory = _load_json(MEMORY_PATH)
    record = next(
        row for row in memory["campaign_types"]
        if row["template_key"] == "google.test.app"
    )
    finding = next(
        row for row in memory["known_findings"]
        if row["id"] == "google_app_ad_pause_limit"
    )
    assert record["verification_state"] == "partial_live"
    assert "Use ENABLED for the App Ad" in finding["next_action"]
    assert "Never enable Campaign or Ad Group" in finding["next_action"]


def test_known_failure_memory_links_fixes_to_existing_regression_tests():
    memory = _load_json(MEMORY_PATH)
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            E2E_TEST_PATH,
            GOOGLE_APP_GUARD_TEST_PATH,
            PAYLOAD_TEST_PATH,
            TEMPLATE_TEST_PATH,
            META_TEMPLATE_TEST_PATH,
            Path(__file__),
        )
    )
    test_names = set(
        re.findall(r"^def (test_[a-zA-Z0-9_]+)\(", source, re.MULTILINE)
    )
    findings = {item["id"]: item for item in memory["known_findings"]}

    assert {
        "tiktok_smart_plus_recorder_schema",
        "tiktok_lookup_provider_502",
        "chat_recovery_input_shape",
        "tiktok_app_ad_template_media_and_tracking",
        "google_app_ad_pause_limit",
        "meta_app_template_argument_resolution",
    } <= findings.keys()

    for finding in findings.values():
        assert finding["root_cause"]
        assert finding["status"] in {"resolved", "unresolved", "provider_limited"}
        assert finding["next_action"]
        assert finding["applies_to"]
        assert set(finding["regression_tests"]) <= test_names

    tiktok_app = findings["tiktok_app_ad_template_media_and_tracking"]
    assert tiktok_app["status"] == "resolved"
    assert "impression" in tiktok_app["root_cause"].lower()
    assert "never enable" in tiktok_app["fix"].lower()
    assert "identity_id" in tiktok_app["root_cause"]


def test_provider_e2e_memory_is_retrievable_by_the_ad_agent():
    provider = MarkdownWikiKnowledgeProvider(
        ROOT / "agents/knowledge/advertising/wiki"
    )
    results = provider.query(
        "广告测试账号 每个渠道广告类型 模板参数 真实 E2E 失败根因 恢复 不要重复创建 Campaign",
        limit=5,
    )

    assert any(
        result.document_id == "provider-live-e2e-memory"
        for result in results
    )
    assert provider.validate() == []


def test_live_e2e_preflight_resolves_template_and_known_recovery_guidance():
    resolved = resolve_template_memory(
        ROOT,
        provider="tiktok",
        account_id="7397068114548195329",
        template_id="tiktok.test.traffic",
        api_template={
            "provider": "tiktok",
            "account_id": "7397068114548195329",
            "blueprint_id": "tiktok.traffic_video",
            "blueprint_version": "3.3.0",
            "status": "active",
        },
    )

    assert resolved["verification_state"] == "live_verified"
    assert resolved["template_values_sha256"]
    assert resolved["expected_status_values"]["ad.operation_status"] == "DISABLE"
    assert resolved["latest_live_test_resources"] == {
        "account_id": "7397068114548195329",
        "campaign_id": "1880079487888913",
        "ad_group_id": "1880080345882434",
        "ad_id": "1880080658604161",
        "smart_plus_creative_id": "1880080658606593",
        "delivery_status": "DISABLE",
        "resume_policy": (
            "Use these existing resources for update and query regression. Do not "
            "recreate the hierarchy unless the caller explicitly authorizes "
            "--allow-new-hierarchy."
        ),
    }
    assert any(
        finding["id"] == "tiktok_smart_plus_ad_creative_identity"
        for finding in resolved["known_findings"]
    )
    assert resolved["recovery_plan"]["action"] == (
        "readback_and_resume_existing_hierarchy"
    )


def test_program_memory_report_exposes_locked_parameters_resources_and_next_action():
    report = build_live_e2e_memory_report(
        ROOT,
        provider="tiktok",
        template_id="tiktok.test.traffic",
        include_template_values=True,
    )

    assert len(report["entries"]) == 1
    entry = report["entries"][0]
    assert entry["template_values_sha256"]
    assert entry["template_values"]["ad.video_id"] == (
        "v10033g50000d8nltv7og65nd6868v7g"
    )
    assert entry["known_live_hierarchies"][-1]["resource_ids"]["campaign"] == (
        "1880079487888913"
    )
    assert entry["recovery_plan"]["action"] == "readback_and_resume_existing_hierarchy"
    assert any(
        finding["id"] == "tiktok_smart_plus_ad_creative_identity"
        for finding in entry["known_findings"]
    )
    assert all(
        any(
            scope["provider"] == "tiktok"
            and scope["campaign_type"] == "TRAFFIC"
            for scope in finding["applies_to"]
        )
        for finding in entry["known_findings"]
    )


def test_program_memory_report_resumes_google_app_with_enabled_ad_and_paused_parents():
    report = build_live_e2e_memory_report(
        ROOT,
        provider="google-ads",
        template_id="google.test.app",
    )

    entry = report["entries"][0]
    assert entry["recovery_plan"]["action"] == "readback_and_resume_existing_hierarchy"
    assert "ENABLED" in entry["recovery_plan"]["instruction"]
    assert "PAUSED" in entry["recovery_plan"]["instruction"]
    assert any(
        finding["id"] == "google_app_ad_pause_limit"
        for finding in entry["known_findings"]
    )
    assert all(
        any(
            scope["provider"] == "google-ads"
            and scope["campaign_type"] == "APP"
            for scope in finding["applies_to"]
        )
        for finding in entry["known_findings"]
    )


def test_program_memory_report_resumes_meta_app_without_recreating_parents(tmp_path):
    shutil.copytree(ROOT / "agents", tmp_path / "agents")
    (
        tmp_path
        / "agents/tools/advertising/contracts/provider_live_e2e_observations.jsonl"
    ).write_text("", encoding="utf-8")
    report = build_live_e2e_memory_report(
        tmp_path,
        provider="meta",
        template_id="meta.test.app-promotion",
    )

    entry = report["entries"][0]
    assert entry["recovery_plan"]["action"] == (
        "readback_and_resume_existing_hierarchy"
    )
    assert "Do not replay the full template or recreate existing parents" in (
        entry["recovery_plan"]["instruction"]
    )
    assert any(
        finding["id"] == "meta_app_template_argument_resolution"
        for finding in entry["known_findings"]
    )


def test_product_sales_memory_requires_real_product_selection_before_ad_retry():
    report = build_live_e2e_memory_report(
        ROOT, provider="tiktok", template_id="tiktok.test.sales",
    )
    entry = report["entries"][0]
    assert entry["verification_state"] == "blocked_by_provider"
    record = next(
        item for item in _load_json(MEMORY_PATH)["campaign_types"]
        if item["template_key"] == "tiktok.test.sales"
    )
    assert record["coverage"]["campaign_create"] == "live_pass"
    assert record["coverage"]["ad_group_create"] == "live_pass"
    assert record["coverage"]["ad_create"] == "provider_rejected"
    assert entry["recovery_plan"]["action"] == "respect_provider_block"
    assert "Product Set" in entry["recovery_plan"]["instruction"]
    assert any(
        finding["id"] == "tiktok_product_sales_product_selection"
        for finding in entry["known_findings"]
    )


def test_live_e2e_preflight_rejects_template_contract_drift(tmp_path):
    source_contracts = ROOT / "agents"
    shutil.copytree(source_contracts, tmp_path / "agents")
    template_path = (
        tmp_path
        / "agents/applications/advertising/contracts/builtin_creation_templates.json"
    )
    templates = _load_json(template_path)
    traffic = next(
        item for item in templates["templates"]
        if item["key"] == "tiktok.test.traffic"
    )
    traffic["values"]["ad.operation_status"] = "ENABLE"
    template_path.write_text(
        json.dumps(templates, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="parameter digest"):
        load_live_e2e_memory(tmp_path)


def test_live_e2e_preflight_rejects_missing_campaign_type_coverage(tmp_path):
    shutil.copytree(ROOT / "agents", tmp_path / "agents")
    memory_path = tmp_path / "agents/tools/advertising/contracts/provider_live_e2e_memory.json"
    memory = _load_json(memory_path)
    memory["campaign_types"] = [
        row
        for row in memory["campaign_types"]
        if row["template_key"] != "meta.test.app-promotion"
    ]
    memory_path.write_text(
        json.dumps(memory, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="declared campaign type scope"):
        load_live_e2e_memory(tmp_path)


def test_live_e2e_preflight_rejects_template_account_scope_drift(tmp_path):
    shutil.copytree(ROOT / "agents", tmp_path / "agents")
    template_path = (
        tmp_path
        / "agents/applications/advertising/contracts/builtin_creation_templates.json"
    )
    templates = _load_json(template_path)
    traffic = next(
        item for item in templates["templates"]
        if item["key"] == "meta.test.traffic"
    )
    traffic["account_id"] = "not-the-confirmed-test-account"
    template_path.write_text(
        json.dumps(templates, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="test account scope drift"):
        load_live_e2e_memory(tmp_path)


def test_live_e2e_memory_accepts_registered_historical_template_digest(tmp_path):
    shutil.copytree(ROOT / "agents", tmp_path / "agents")
    memory_path = (
        tmp_path
        / "agents/tools/advertising/contracts/provider_live_e2e_memory.json"
    )
    memory = _load_json(memory_path)
    app_record = next(
        row
        for row in memory["campaign_types"]
        if row["template_key"] == "tiktok.test.app-promotion"
    )
    app_record["historical_template_locks"] = [
        {
            "blueprint_version": "3.0.3",
            "template_values_sha256": (
                "3d2c6c2b6024b6fcb13c0fe9e703a58d4e66e206e899fca1323efc982c12e9a7"
            ),
            "evidence_refs": [
                "outputs/full-agent-e2e-20261016-live-run4/"
                "cases/tiktok-app-ad-create-corrected-20261016-r1.json"
            ],
        }
    ]
    memory_path.write_text(
        json.dumps(memory, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    loaded = load_live_e2e_memory(tmp_path)
    assert loaded["campaign_types"][
        next(
            index
            for index, row in enumerate(loaded["campaign_types"])
            if row["template_key"] == "tiktok.test.app-promotion"
        )
    ]["historical_template_locks"][0]["template_values_sha256"].startswith("3d2c")

    append_live_e2e_observation(
        tmp_path,
        event_type="attempt_started",
        attempt_id="tiktok-app-current-template",
        phase_id="tiktok-app-current-template:1",
        phase=1,
        provider="tiktok",
        account_id="7397068114548195329",
        template_id="tiktok.test.app-promotion",
        blueprint_version="3.0.3",
        template_values_sha256=app_record["template_values_sha256"],
        case_id="tiktok-app-current-template",
        outcome="pending",
    )
    observations = (
        tmp_path
        / "agents/tools/advertising/contracts/provider_live_e2e_observations.jsonl"
    ).read_text(encoding="utf-8").splitlines()
    assert json.loads(observations[-1])["template_values_sha256"] == (
        app_record["template_values_sha256"]
    )
    load_live_e2e_memory(tmp_path)


def test_live_e2e_memory_rejects_unregistered_historical_template_digest(tmp_path):
    shutil.copytree(ROOT / "agents", tmp_path / "agents")
    memory_path = (
        tmp_path
        / "agents/tools/advertising/contracts/provider_live_e2e_memory.json"
    )
    memory = _load_json(memory_path)
    app_record = next(
        row
        for row in memory["campaign_types"]
        if row["template_key"] == "tiktok.test.app-promotion"
    )
    app_record["historical_template_locks"] = [
        {
            "blueprint_version": "3.0.3",
            "template_values_sha256": "0" * 64,
            "evidence_refs": ["outputs/unrelated-evidence.json"],
        }
    ]
    memory_path.write_text(
        json.dumps(memory, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="historical template lock"):
        load_live_e2e_memory(tmp_path)


def test_live_e2e_preflight_rejects_api_template_version_drift():
    with pytest.raises(ValueError, match="blueprint"):
        resolve_template_memory(
            ROOT,
            provider="tiktok",
            account_id="7397068114548195329",
            template_id="tiktok.test.traffic",
            api_template={
                "provider": "tiktok",
                "account_id": "7397068114548195329",
                "blueprint_id": "tiktok.traffic_video",
                "blueprint_version": "0.0.0",
                "status": "active",
            },
        )


def test_live_e2e_memory_preserves_reusable_existing_resources():
    resolved = resolve_template_memory(
        ROOT,
        provider="meta",
        account_id="2806375919473667",
        template_id="meta.test.traffic",
        api_template={
            "provider": "meta",
            "account_id": "2806375919473667",
            "blueprint_id": "meta.traffic_link",
            "blueprint_version": "1.2.0",
            "status": "active",
        },
    )

    assert resolved["hierarchy_reuse"]["requires_reconciliation"] is True
    assert any(
        hierarchy["resource_ids"]["campaign"] == "120251918011200251"
        for hierarchy in resolved["known_live_hierarchies"]
    )
    assert any(
        hierarchy["resource_ids"]["ad_set"] == "120251918013540251"
        and hierarchy["resource_ids"]["ad"] == "120251918014470251"
        for hierarchy in resolved["known_live_hierarchies"]
    )


def test_live_e2e_observations_persist_resources_and_recovery_state(tmp_path):
    shutil.copytree(ROOT / "agents", tmp_path / "agents")
    template_root = tmp_path
    observation_path = (
        template_root
        / "agents/tools/advertising/contracts/provider_live_e2e_observations.jsonl"
    )
    observation_path.write_text("", encoding="utf-8")
    common = {
        "attempt_id": "attempt-traffic-1",
        "phase_id": "attempt-traffic-1:1",
        "provider": "tiktok",
        "account_id": "7397068114548195329",
        "template_id": "tiktok.test.traffic",
        "blueprint_version": "3.3.0",
        "template_values_sha256": (
            "1a226772ad23bc219815f08754d3948b457ad0178c73a7d2d296289766b1bff2"
        ),
        "case_id": "tiktok-traffic-live-recovery",
        "phase": 1,
    }

    append_live_e2e_observation(
        template_root,
        event_type="attempt_started",
        outcome="pending",
        **common,
    )
    append_live_e2e_observation(
        template_root,
        event_type="attempt_completed",
        outcome="partial",
        created_resources=[
            {
                "resource_type": "campaign",
                "id": "1879182108006450",
                "status": "DISABLE",
            },
            {
                "resource_type": "ad_group",
                "id": "1879182124055009",
                "status": "DISABLE",
            },
        ],
        error_messages=["access_token=must-not-persist"],
        **common,
    )

    persisted = observation_path.read_text(encoding="utf-8")
    assert "must-not-persist" not in persisted
    assert "1879182108006450" in persisted

    resolved = resolve_template_memory(
        template_root,
        provider="tiktok",
        account_id="7397068114548195329",
        template_id="tiktok.test.traffic",
        api_template={
            "provider": "tiktok",
            "account_id": "7397068114548195329",
            "blueprint_id": "tiktok.traffic_video",
            "blueprint_version": "3.3.0",
            "status": "active",
        },
    )
    assert resolved["hierarchy_reuse"]["requires_reconciliation"] is True
    assert resolved["hierarchy_reuse"]["resource_ids"]["campaign"] == (
        "1880079487888913"
    )
    assert resolved["hierarchy_reuse"]["resource_ids"]["ad_group"] == (
        "1880080345882434"
    )
    assert resolved["observations"][-1]["outcome"] == "partial"


def test_live_e2e_timeout_records_ambiguous_outcome_without_resources(tmp_path):
    shutil.copytree(ROOT / "agents", tmp_path / "agents")
    (
        tmp_path
        / "agents/tools/advertising/contracts/provider_live_e2e_observations.jsonl"
    ).write_text("", encoding="utf-8")
    row = next(
        item for item in _load_json(MEMORY_PATH)["campaign_types"]
        if item["template_key"] == "meta.test.app-promotion"
    )
    common = {
        "attempt_id": "meta-app-timeout",
        "phase_id": "meta-app-timeout:0",
        "phase": 0,
        "provider": "meta",
        "account_id": "2806375919473667",
        "template_id": "meta.test.app-promotion",
        "blueprint_version": row["blueprint_version"],
        "template_values_sha256": row["template_values_sha256"],
        "case_id": "meta-app-timeout",
    }
    append_live_e2e_observation(
        tmp_path, event_type="attempt_started", outcome="pending", **common,
    )
    completed = append_live_e2e_observation(
        tmp_path,
        event_type="attempt_completed",
        outcome="ambiguous",
        error_messages=["ReadTimeout"],
        **common,
    )
    assert completed["created_resources"] == []
    assert completed["error_messages"] == ["ReadTimeout"]
    report = build_live_e2e_memory_report(
        tmp_path, provider="meta", template_id="meta.test.app-promotion",
    )
    assert report["entries"][0]["recovery_plan"]["action"] == "reconcile_ambiguous_write"

    with pytest.raises(ValueError, match="readback"):
        append_live_e2e_observation(
            tmp_path, event_type="attempt_reconciled", outcome="no_write", **common,
        )
    reconciled = append_live_e2e_observation(
        tmp_path,
        event_type="attempt_reconciled",
        outcome="no_write",
        reconciliation_case_id="meta-app-timeout-reconcile-read",
        **common,
    )
    assert reconciled["reconciliation_case_id"] == "meta-app-timeout-reconcile-read"
    report = build_live_e2e_memory_report(
        tmp_path, provider="meta", template_id="meta.test.app-promotion",
    )
    assert report["entries"][0]["recovery_plan"]["action"] == (
        "readback_and_resume_existing_hierarchy"
    )


def test_live_e2e_reconciliation_cannot_clear_another_attempt(tmp_path):
    shutil.copytree(ROOT / "agents", tmp_path / "agents")
    (
        tmp_path
        / "agents/tools/advertising/contracts/provider_live_e2e_observations.jsonl"
    ).write_text("", encoding="utf-8")
    row = next(
        item for item in _load_json(MEMORY_PATH)["campaign_types"]
        if item["template_key"] == "meta.test.app-promotion"
    )
    with pytest.raises(ValueError, match="ambiguous"):
        append_live_e2e_observation(
            tmp_path,
            event_type="attempt_reconciled",
            outcome="no_write",
            attempt_id="unrelated",
            phase_id="unrelated:0",
            phase=0,
            provider="meta",
            account_id="2806375919473667",
            template_id="meta.test.app-promotion",
            blueprint_version=row["blueprint_version"],
            template_values_sha256=row["template_values_sha256"],
            case_id="unrelated",
            reconciliation_case_id="meta-app-timeout-reconcile-read",
        )


def test_unresolved_live_attempt_cannot_be_overridden_as_a_new_hierarchy(tmp_path):
    shutil.copytree(ROOT / "agents", tmp_path / "agents")
    append_live_e2e_observation(
        tmp_path,
        event_type="attempt_started",
        attempt_id="attempt-ambiguous",
        phase_id="attempt-ambiguous:1",
        phase=1,
        provider="meta",
        account_id="2806375919473667",
        template_id="meta.test.traffic",
        blueprint_version="1.2.0",
        template_values_sha256=(
            "990ce4e8f6063521939c7176fb37decd3fa3fab8e28d3ecbf017264b3b0de0fa"
        ),
        case_id="meta-traffic-timeout",
        outcome="pending",
    )
    resolved = resolve_template_memory(
        tmp_path,
        provider="meta",
        account_id="2806375919473667",
        template_id="meta.test.traffic",
        api_template={
            "provider": "meta",
            "account_id": "2806375919473667",
            "blueprint_id": "meta.traffic_link",
            "blueprint_version": "1.2.0",
            "status": "active",
        },
    )
    state = hierarchy_reuse_state(
        resolved,
        resolved["observations"],
    )

    assert state["unresolved_attempt_ids"] == ["attempt-ambiguous"]
    assert state["requires_reconciliation"] is True
    with pytest.raises(ValueError, match="ambiguous outcome"):
        require_new_hierarchy_authorization(
            state,
            allow_new_hierarchy=True,
        )


def test_known_live_write_requires_explicit_new_hierarchy_authorization():
    memory = load_live_e2e_memory(ROOT)
    for record in memory["campaign_types"]:
        state = hierarchy_reuse_state(record, [])
        if record["verification_state"] == "not_run":
            assert state["requires_reconciliation"] is False
            continue
        if (
            record["verification_state"] == "blocked_by_provider"
            and not record["prior_live_write_observed"]
        ):
            assert state["requires_reconciliation"] is False
            applicable_findings = [
                finding
                for finding in memory["known_findings"]
                if any(
                    scope["provider"] == record["provider"]
                    and scope["campaign_type"] == record["campaign_type"]
                    and scope.get("test_account") in (None, record["test_account"])
                    for scope in finding["applies_to"]
                )
            ]
            with pytest.raises(ValueError, match="known Provider block"):
                require_new_hierarchy_authorization(
                    state,
                    allow_new_hierarchy=True,
                    verification_state=record["verification_state"],
                    known_findings=applicable_findings,
                )
            continue
        assert state["requires_reconciliation"] is True
        applicable_findings = [
            finding
            for finding in memory["known_findings"]
            if any(
                scope["provider"] == record["provider"]
                and scope["campaign_type"] == record["campaign_type"]
                and scope.get("test_account") in (None, record["test_account"])
                for scope in finding["applies_to"]
            )
        ]
        if record["verification_state"] == "blocked_by_provider":
            with pytest.raises(ValueError, match="known Provider block"):
                require_new_hierarchy_authorization(
                    state,
                    allow_new_hierarchy=True,
                    verification_state=record["verification_state"],
                    known_findings=applicable_findings,
                )
            continue
        if any(item["status"] == "unresolved" for item in applicable_findings):
            with pytest.raises(ValueError, match="unresolved known failure"):
                require_new_hierarchy_authorization(
                    state,
                    allow_new_hierarchy=True,
                    verification_state=record["verification_state"],
                    known_findings=applicable_findings,
                )
            continue
        with pytest.raises(ValueError, match="prior live writes"):
            require_new_hierarchy_authorization(
                state,
                allow_new_hierarchy=False,
            )
        with pytest.raises(ValueError, match="readback reconciliation"):
            require_new_hierarchy_authorization(
                state,
                allow_new_hierarchy=True,
                existing_resources_reconciled=False,
                verification_state=record["verification_state"],
                known_findings=applicable_findings,
            )
        require_new_hierarchy_authorization(
            state,
            allow_new_hierarchy=True,
            existing_resources_reconciled=True,
            verification_state=record["verification_state"],
            known_findings=applicable_findings,
        )


def test_live_resource_capture_ignores_simulated_and_failed_creates():
    resources = _created_live_resources(
        {
            "results": [
                {
                    "tool": "tiktok_smart_plus_create_ad",
                    "success": True,
                    "data": {
                        "execution_mode": "live",
                        "ad": {
                            "smart_plus_ad_id": "1879183742331441",
                            "operation_status": "DISABLE",
                        },
                    },
                },
                {
                    "tool": "meta_create_campaign",
                    "success": True,
                    "data": {
                        "execution_mode": "dry_run",
                        "campaign_id": "not-a-live-id",
                    },
                },
                {
                    "tool": "google_create_campaign",
                    "success": False,
                    "data": {},
                },
            ]
        }
    )

    assert resources == [
        {
            "resource_type": "ad",
            "id": "1879183742331441",
            "status": "DISABLE",
        }
    ]


def test_google_7574609568_campaign_limit_blocks_creation_for_that_account_only():
    memory = load_live_e2e_memory(ROOT)
    finding_id = "google_7574609568_campaign_resource_limit"
    finding = next(
        item for item in memory["known_findings"] if item["id"] == finding_id
    )
    assert finding["status"] == "provider_limited"
    assert {item.get("test_account") for item in finding["applies_to"]} == {
        "7574609568",
    }
    assert {item["campaign_type"] for item in finding["applies_to"]} == {
        "PERFORMANCE_MAX", "SHOPPING", "APP",
    }

    test_account_entries = [
        entry
        for entry in build_live_e2e_memory_report(ROOT, provider="google-ads")["entries"]
        if entry["test_account"] == "7574609568"
    ]
    assert len(test_account_entries) == 3
    assert all(entry["verification_state"] == "blocked_by_provider" for entry in test_account_entries)
    assert all(entry["recovery_plan"]["action"] == "respect_provider_block" for entry in test_account_entries)
    assert all(
        any(item["id"] == finding_id for item in entry["known_findings"])
        for entry in test_account_entries
    )

    legacy_account_entries = [
        entry
        for entry in build_live_e2e_memory_report(ROOT, provider="google-ads")["entries"]
        if entry["test_account"] == "9055507554"
    ]
    assert all(
        all(item["id"] != finding_id for item in entry["known_findings"])
        for entry in legacy_account_entries
    )
