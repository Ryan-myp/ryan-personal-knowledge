from types import SimpleNamespace
import json
from pathlib import Path

from scripts.advertising import provider_query_e2e
from agents.tools.advertising.shared.domain.provider_evidence import validate_provider_evidence
from scripts.advertising.summarize_provider_latency import summarize_evidence


def test_test_account_query_evidence_records_provider_call_latency(monkeypatch):
    suite = provider_query_e2e.ReadOnlyQueryRun.__new__(
        provider_query_e2e.ReadOnlyQueryRun
    )
    suite.accounts = {"tiktok": "test-account"}
    suite.queries = {"tiktok": []}
    suite.runtime = SimpleNamespace(
        whitelist_validator=SimpleNamespace(
            validate_account=lambda _provider, _account: (True, None)
        ),
        tool_executor=SimpleNamespace(
            execute=lambda _context, _tool, _input: SimpleNamespace()
        ),
    )
    suite._read_tool = lambda _provider, _tool: SimpleNamespace(input_schema={})
    suite._record_result = lambda provider, _definition, _result, _key, _input: (
        suite.queries[provider].append({"tool": "tiktok_list_campaigns", "outcome": "passed"})
        or {"ok": True, "data": {}}
    )
    monkeypatch.setattr(provider_query_e2e, "validate_tool_input", lambda *_args, **_kwargs: [])

    suite.execute("tiktok", "tiktok_list_campaigns", {}, "campaigns")

    assert isinstance(suite.queries["tiktok"][0]["latency_ms"], float)
    assert suite.queries["tiktok"][0]["latency_ms"] >= 0


def test_query_evidence_accepts_only_finite_non_negative_latency():
    raw = json.loads(Path(
        "agents/tools/advertising/contracts/provider_query_e2e_evidence.json"
    ).read_text(encoding="utf-8"))
    query = next(
        item for run in raw["runs"] for item in run["queries"]
        if item["outcome"] == "passed"
    )
    query["latency_ms"] = 12.5
    assert validate_provider_evidence(raw) == []
    query["latency_ms"] = float("inf")
    assert any("latency_ms" in error for error in validate_provider_evidence(raw))
    query["latency_ms"] = -1
    assert any("latency_ms" in error for error in validate_provider_evidence(raw))


def test_latency_summary_excludes_skips_and_unmeasured_queries():
    raw = json.loads(Path(
        "agents/tools/advertising/contracts/provider_query_e2e_evidence.json"
    ).read_text(encoding="utf-8"))
    for run in raw["runs"]:
        for item in run["queries"]:
            item.pop("latency_ms", None)
    passed = next(
        item for run in raw["runs"] for item in run["queries"]
        if run["provider"] == "tiktok" and item["outcome"] == "passed"
    )
    passed["latency_ms"] = 12.5
    report = summarize_evidence(raw)
    assert report["providers"]["tiktok"]["measured"] == 1
    assert report["providers"]["tiktok"]["p95_ms"] == 12.5
    assert report["providers"]["tiktok"]["skipped"] > 0
