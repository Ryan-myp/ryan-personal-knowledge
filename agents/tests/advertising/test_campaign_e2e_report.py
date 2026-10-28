import json
from datetime import date

from scripts.advertising.campaign_e2e_report import build_report


MEMORY = {
    "scope": {"test_accounts": {"meta": "1234"}},
    "campaign_types": [{
        "provider": "meta",
        "campaign_type": "TRAFFIC",
        "template_key": "meta.test.traffic",
        "template_values_sha256": "a" * 64,
        "verification_state": "live_verified",
    }],
}


def _case(tmp_path, *, account="1234", tool="meta_list_campaigns", write=False):
    row = {
        "provider": "meta", "account": account, "tool": tool,
        "response": {
            "run_id": "8da61da5-941d-4268-8473-40df3df65f12",
            "status": "succeeded",
            "results": [{
                "tool": tool, "success": True,
                "data": {"data_status": "live"},
            }],
        },
    }
    if write:
        row["template_id"] = "meta.test.traffic"
        row["e2e_memory"] = {"template_values_sha256": "a" * 64}
    (tmp_path / "cases").mkdir(exist_ok=True)
    (tmp_path / "cases" / "case-1.json").write_text(json.dumps(row))
    (tmp_path / "provider-http.jsonl").write_text(json.dumps({
        "case_id": "case-1", "provider": "meta", "method": "GET",
        "http_status": 200, "provider_code": None,
    }) + "\n")


def test_report_requires_transport_and_live_tool_result(tmp_path):
    _case(tmp_path)
    report = build_report(tmp_path, MEMORY)
    assert report["read_verified"] == 1
    assert report["write_verified"] == 0
    assert report["cases"][0]["verdict"] == "read_verified"
    assert report["campaign_types"][0]["current_write_verified"] is False
    assert "1234" not in json.dumps(report)

    (tmp_path / "provider-http.jsonl").unlink()
    report = build_report(tmp_path, MEMORY)
    assert report["read_verified"] == 0
    assert report["cases"][0]["verdict"] == "not_verified"


def test_report_rejects_out_of_scope_and_never_promotes_write_by_reply(tmp_path):
    _case(tmp_path, account="unconfirmed", tool="meta_create_campaign", write=True)
    report = build_report(tmp_path, MEMORY)
    assert report["cases"][0]["verdict"] == "out_of_scope"
    assert report["write_verified"] == 0
    assert "unconfirmed" not in json.dumps(report)

    case_path = tmp_path / "cases" / "case-1.json"
    row = json.loads(case_path.read_text())
    row["account"] = "1234"
    case_path.write_text(json.dumps(row))
    report = build_report(tmp_path, MEMORY)
    assert report["cases"][0]["verdict"] == "write_requires_readback_review"
    assert report["campaign_types"][0]["current_write_verified"] is False


def test_report_does_not_leak_untrusted_run_id_or_promote_unrelated_write(tmp_path):
    _case(tmp_path, tool="meta_create_campaign", write=True)
    case_path = tmp_path / "cases" / "case-1.json"
    row = json.loads(case_path.read_text())
    row["response"]["run_id"] = "private-token-from-corrupt-case"
    row["tool"] = "meta_create_creative"
    row["response"]["results"][0]["tool"] = row["tool"]
    case_path.write_text(json.dumps(row))

    report = build_report(tmp_path, MEMORY)
    assert report["cases"][0]["verdict"] == "out_of_scope"
    assert "private-token-from-corrupt-case" not in json.dumps(report)


def test_report_exposes_age_of_historical_provider_evidence(tmp_path):
    memory = {
        **MEMORY,
        "campaign_types": [{
            **MEMORY["campaign_types"][0],
            "last_verified_at": "2026-01-01",
        }],
    }

    report = build_report(tmp_path, memory, as_of=date(2026, 3, 1))

    assert report["evidence_as_of"] == "2026-03-01"
    assert report["campaign_types"][0]["evidence_last_verified_at"] == "2026-01-01"
    assert report["campaign_types"][0]["evidence_age_days"] == 59
    assert report["campaign_types"][0]["current_write_verified"] is False


def test_report_marks_missing_invalid_or_future_verification_date_as_unknown(tmp_path):
    for value in (None, "not-a-date", "2026-03-02"):
        memory = {
            **MEMORY,
            "campaign_types": [{
                **MEMORY["campaign_types"][0],
                "last_verified_at": value,
            }],
        }

        report = build_report(tmp_path, memory, as_of=date(2026, 3, 1))

        assert report["campaign_types"][0]["evidence_last_verified_at"] is None
        assert report["campaign_types"][0]["evidence_age_days"] is None
