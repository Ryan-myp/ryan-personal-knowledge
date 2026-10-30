from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from agents.applications.advertising.operations.optimization_reviews import OptimizationReviewService
from agents.applications.advertising.persistence.models import ToolCallRecord
from agents.applications.advertising.persistence.store import AdAgentStore
from agents.tests.advertising.test_optimization_reviews import proposal, measurement


@pytest.fixture
def report_review():
    store = AdAgentStore(":memory:")
    store.create_session("s", "u", metadata={"tenant_id": "t"})
    principal = SimpleNamespace(user_id="u", tenant_id="t", account_scope={"test_ads": {"test-account"}})
    context = SimpleNamespace(principal=principal, metadata={})
    definition = SimpleNamespace(namespace="test_ads", resource_type="campaign", action="report",
                                 is_write_tool=False, scope_fields=["account_id"])
    service = OptimizationReviewService(store, SimpleNamespace(get=lambda _: (definition, None)),
                                       now=lambda: datetime(2026, 10, 30, tzinfo=timezone.utc))
    output = {"data_status": "live", "report": [{"campaign_id": "c1", "cpc": "10"}],
              "report_context": {"resource_level": "campaign", "period": {"value": {
                  "since": "2026-08-01", "until": "2026-08-07"}},
                  "completeness": {"may_be_truncated": False, "status": "within_limit"}}}
    args = {**proposal(), "baseline": measurement(metric="cpc"), "baseline_evidence": {
        "session_id": "s", "turn_id": "report", "tool_name": "report", "row_index": 0,
    }}
    def save():
        store.record_tool_call(ToolCallRecord(id="report", session_id="s", turn_id="report",
            tool_name="report", platform="test_ads", input_data={"account_id": "test-account"},
            output_data=output, ended_at="2026-08-23T00:00:00+00:00"))
    yield service, context, store, output, args, save
    store.close()


def test_report_provenance_is_derived_from_owned_audit_not_model_claim(report_review):
    service, context, _, _, args, save = report_review
    save()
    result = service.create(context, args)
    assert result.success
    evidence = result.data["review"]["baseline_provenance"]
    assert evidence["status"] == "audited_value_declared_context"
    assert evidence["record_id"] == "report"
    assert set(evidence["unverified_context_fields"]) == {"currency", "timezone", "attribution_days", "unit"}


@pytest.mark.parametrize("mutation", ["value", "resource", "truncated", "simulated", "period", "foreign", "metric", "segmented"])
def test_invalid_report_provenance_cannot_create_review(report_review, mutation):
    service, context, _, output, args, save = report_review
    if mutation == "value": args["baseline"]["value"] = 99
    if mutation == "metric": args["baseline"]["metric"] = "CPA"
    if mutation == "segmented": output["report"].append(dict(output["report"][0]))
    if mutation == "resource": output["report"][0]["campaign_id"] = "other"
    if mutation == "truncated": output["report_context"]["completeness"]["may_be_truncated"] = True
    if mutation == "simulated": output["simulated"] = True
    if mutation == "period": args["baseline"]["start_date"] = "2026-08-02"
    if mutation == "foreign": context.principal.tenant_id = "other"
    save()
    assert not service.create(context, args).success


def test_manual_baseline_is_explicitly_unverified(report_review):
    service, context, _, _, _, _ = report_review
    result = service.create(context, proposal())
    assert result.data["review"]["baseline_provenance"]["status"] == "user_supplied"


def test_audited_baseline_execution_readback_and_outcome_form_one_cycle(report_review):
    """Offline audit fixtures exercise the whole cycle without a Provider call."""
    service, context, store, output, args, save = report_review
    save()
    service.now = lambda: datetime(2026, 8, 25, tzinfo=timezone.utc)
    row = service.create(context, args).data["review"]
    report_def = service.registry.get("report")[0]
    definitions = {"report": report_def, **{name: SimpleNamespace(
        namespace="test_ads", resource_type="campaign", resource_id_field="campaign_id",
        scope_fields=["account_id"], is_write_tool=writing, readback_tool="get",
    ) for name, writing in (("update", True), ("get", False))}}
    service.registry = SimpleNamespace(get=lambda name: (definitions[name], None))
    for name, turn, timestamp, result in (
        ("update", "execution", "2026-09-01T00:00:00+00:00", {"execution_mode": "live", "execution_status": "executed"}),
        ("get", "readback", "2026-09-01T01:00:00+00:00", {"data_status": "live", "budget": 80}),
    ):
        store.record_tool_call(ToolCallRecord(id=turn, session_id="s", turn_id=turn, tool_name=name,
            platform="test_ads", input_data={"account_id": "test-account", "campaign_id": "c1", "budget": 80},
            output_data=result, ended_at=timestamp))
        action = "link_execution" if name == "update" else "verify_readback"
        result = service.update(context, {"review_id": row["id"], "expected_version": row["version"],
            "action": action, "readback_path": "budget", "evidence": {
                "session_id": "s", "turn_id": turn, "tool_name": name}})
        assert result.success, result
        row = result.data["review"]
    service.now = lambda: datetime(2026, 10, 30, tzinfo=timezone.utc)
    outcome = measurement(8, metric="cpc", start_date="2026-09-02", end_date="2026-09-08")
    output["report"][0]["cpc"] = "8"
    output["report_context"]["period"]["value"] = {"since": "2026-09-02", "until": "2026-09-08"}
    store.record_tool_call(ToolCallRecord(id="after", session_id="s", turn_id="after", tool_name="report",
        platform="test_ads", input_data={"account_id": "test-account"}, output_data=output,
        ended_at="2026-10-28T00:00:00+00:00"))
    result = service.update(context, {"review_id": row["id"], "expected_version": row["version"],
        "action": "review", "outcome": outcome, "outcome_evidence": {
            "session_id": "s", "turn_id": "after", "tool_name": "report", "row_index": 0}})
    assert result.success, result
    review = result.data["review"]
    assert review["status"] == "reviewed"
    assert review["result"]["relative_change"] == pytest.approx(-0.2)
    assert review["result"]["evidence_status"] == "audited_values_with_context_gaps"
    assert review["result"]["causal_claim"] is False


@pytest.mark.parametrize("namespace,tool_name,report,metric", [
    ("meta", "meta_get_campaign_report", [{"campaign_id": "c1", "cpc": "10"}], "cpc"),
    ("google-ads", "google_get_campaign_report",
     [{"campaign": {"id": "c1"}, "metrics": {"cost_micros": 10}}], "metrics.cost_micros"),
    ("tiktok", "tiktok_get_campaign_report",
     {"list": [{"dimensions": {"campaign_id": "c1"}, "metrics": {"cpc": "10"}}]},
     "metrics.cpc"),
])
def test_registered_provider_contract_can_supply_baseline(report_review, namespace, tool_name, report, metric):
    from scripts.advertising.validate_contracts import build_runtime
    service, context, store, output, args, _ = report_review
    runtime = build_runtime()
    try:
        service.registry = runtime.registry
        context.principal.account_scope = {namespace: {"test-account"}}
        args["namespace"] = namespace
        args["baseline"]["metric"] = metric
        args["baseline_evidence"]["tool_name"] = tool_name
        output["report"] = report
        store.record_tool_call(ToolCallRecord(id="registered", session_id="s", turn_id="report",
            tool_name=tool_name, platform=namespace, input_data={"account_id": "test-account"},
            output_data=output, ended_at="2026-08-23T00:00:00+00:00"))
        result = service.create(context, args)
        assert result.success, result
    finally:
        runtime.close(wait=True)


@pytest.mark.parametrize("audit_fails", [False, True])
def test_native_tool_execution_persists_resolved_scope_for_later_review(audit_fails, monkeypatch):
    from agents.agent_harness import ToolBinding, StaticToolSource, ModelTurn
    from agents.agent_harness.core.interfaces import ToolDefinition, ToolSchema, ToolResult
    from agents.agent_platform.governance.identity.principal import RequestPrincipal
    from agents.applications.advertising.composition.ad_application import AdvertisingComposition
    from agents.tests.advertising.harness_models import install, call
    from agents.applications.advertising.execution.account_policy import AccountWhitelistValidator

    store = AdAgentStore(":memory:")
    whitelist = AccountWhitelistValidator()
    whitelist.allowed_accounts = {"test-ads": ["test-account"]}
    runtime = AdvertisingComposition(persistence_store=store, require_llm=False,
        offline_mode=True, start_background_workers=False, whitelist_validator=whitelist)
    definition = ToolDefinition(name="test_report", namespace="test-ads", skill="test",
        description="读取离线测试报表", action="report", resource_type="campaign",
        intent_types=["test_report"], input_schema=ToolSchema(),
        required_permissions=["ads.read"])
    runtime.register_tool_source(StaticToolSource("test:reports", [ToolBinding(
        definition, lambda *_: ToolResult.ok({"data_status": "live", "report": []}),
    )]))
    principal = RequestPrincipal(user_id="u", permissions=frozenset({"ads.read"}),
                                 account_scope={"test-ads": frozenset({"test-account"})})
    try:
        if audit_fails:
            def fail_audit(*_args, **_kwargs):
                raise OSError("audit storage unavailable")
            monkeypatch.setattr(runtime.persistence_services, "persist_tool_result", fail_audit)
        install(runtime, ModelTurn(tool_calls=[call("test_report", {})]), ModelTurn(content="已读取"))
        result = runtime.run("调用 test_report 查询测试报表", user_id="u",
                             principal=principal, account_id="test-account")
        if audit_fails:
            assert result["status"] == "failed"
            assert result["tool_results"][0]["is_error"] is True
            assert store.list_tool_calls(result["session_id"]) == []
            return
        assert result["status"] == "succeeded", result
        rows = store.list_tool_calls(result["session_id"], turn_id=result["turn_id"])
        assert len(rows) == 1
        assert rows[0].input_data["account_id"] == "test-account"
        assert rows[0].output_data["data_status"] == "live"
    finally:
        runtime.close(wait=True)
