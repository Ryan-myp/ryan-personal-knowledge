from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from agents.applications.advertising.persistence.store import AdAgentStore
from agents.applications.advertising.operations.optimization_reviews import (
    OptimizationReviewService,
)


def measurement(value=10, **overrides):
    return {
        "value": value,
        "metric": "CPA",
        "unit": "currency/conversion",
        "currency": "USD",
        "timezone": "UTC",
        "attribution_days": 7,
        "start_date": "2026-08-01",
        "end_date": "2026-08-07",
        "source": "用户提供的测试报表",
        **overrides,
    }


def proposal():
    return {
        "namespace": "test_ads",
        "account_id": "test-account",
        "resource_type": "campaign",
        "resource_id": "c1",
        "proposal": "预算从100调整到80",
        "field": "budget",
        "expected_value": 80,
        "baseline": measurement(),
        "cooldown_days": 7,
        "observation_days": 7,
    }


@pytest.fixture
def reviews():
    store = AdAgentStore(":memory:")
    principal = SimpleNamespace(
        tenant_id="t", user_id="u", account_scope={"test_ads": {"test-account"}}
    )
    context = SimpleNamespace(principal=principal, session_id="s", metadata={"run_id": "run"})
    service = OptimizationReviewService(
        store, SimpleNamespace(), now=lambda: datetime(2026, 10, 29, tzinfo=timezone.utc)
    )
    yield service, context, store
    store.close()


def test_proposal_dedup_scope_cas_and_reopen(reviews):
    service, context, store = reviews
    first = service.create(context, proposal())
    assert first.success
    row = first.data["review"]
    assert row["status"] == "proposed" and row["version"] == 1
    again = service.create(context, proposal())
    assert again.data["deduplicated"] is True
    assert again.data["review"]["id"] == row["id"]
    assert store.get_optimization_review(row["id"], "other", "u") is None
    assert store.save_optimization_review(row["id"], "t", "u", row, expected_version=0) is False
    changed = {**proposal(), "expected_value": 60}
    assert not service.create(context, changed).success
    context.principal.account_scope = {"test_ads": {"different"}}
    assert not service.create(context, proposal()).success


def test_observation_refuses_immature_or_incomparable_data(reviews):
    service, context, store = reviews
    row = service.create(context, proposal()).data["review"]
    # Simulated local fixture: a recorded readback, not actual provider activity.
    row.update(status="verified", executed_at="2026-09-01T00:00:00+00:00")
    assert store.save_optimization_review(row["id"], "t", "u", row, expected_version=1)
    for outcome in (
        measurement(8, currency="EUR"),
        measurement(8, start_date="2026-10-22", end_date="2026-10-28"),
        measurement(8, start_date="2026-07-01", end_date="2026-07-07"),
    ):
        result = service.update(
            context,
            {"review_id": row["id"], "expected_version": 2, "action": "review", "outcome": outcome},
        )
        assert not result.success
    result = service.update(
        context,
        {
            "review_id": row["id"],
            "expected_version": 2,
            "action": "review",
            "outcome": measurement(8, start_date="2026-09-02", end_date="2026-09-08"),
        },
    )
    assert result.success
    assert result.data["review"]["result"]["relative_change"] == pytest.approx(-0.2)
    assert result.data["review"]["result"]["causal_claim"] is False


def test_no_unverified_approval_or_execution_from_model_claim(reviews):
    service, context, _ = reviews
    row = service.create(context, proposal()).data["review"]
    result = service.update(
        context,
        {
            "review_id": row["id"],
            "expected_version": 1,
            "action": "link_execution",
            "evidence": {"session_id": "foreign", "turn_id": "fake", "tool_name": "write"},
        },
    )
    assert not result.success
    assert not service.update(
        context,
        {
            "review_id": row["id"],
            "expected_version": 1,
            "action": "review",
            "outcome": measurement(8),
        },
    ).success


def test_execution_and_readback_require_matching_audited_target_and_value(reviews):
    from agents.applications.advertising.persistence.models import ToolCallRecord

    service, context, store = reviews
    row = service.create(context, proposal()).data["review"]
    store.create_session("s", "u", metadata={"tenant_id": "t"})
    definitions = {
        "update": SimpleNamespace(
            is_write_tool=True,
            namespace="test_ads",
            resource_type="campaign",
            resource_id_field="campaign_id",
            scope_fields=["account_id"],
            readback_tool="get",
        ),
        "get": SimpleNamespace(
            is_write_tool=False,
            namespace="test_ads",
            resource_type="campaign",
            resource_id_field="campaign_id",
            scope_fields=["account_id"],
        ),
    }
    service.registry = SimpleNamespace(get=lambda name: (definitions[name], None))
    for tool, turn, output, stamp in (
        (
            "update",
            "t1",
            {"execution_mode": "live", "execution_status": "executed"},
            "2026-10-29T01:00:00+00:00",
        ),
        ("get", "t2", {"campaign": {"budget": 80}}, "2026-10-29T02:00:00+00:00"),
    ):
        store.record_tool_call(
            ToolCallRecord(
                id=turn,
                session_id="s",
                turn_id=turn,
                tool_name=tool,
                platform="test_ads",
                input_data={"campaign_id": "c1", "account_id": "test-account", "budget": 80},
                output_data=output,
                ended_at=stamp,
            )
        )
    evidence = {"session_id": "s", "turn_id": "t1", "tool_name": "update"}
    result = service.update(
        context,
        {
            "review_id": row["id"],
            "expected_version": 1,
            "action": "link_execution",
            "evidence": evidence,
        },
    )
    assert result.success, result.error
    assert result.data["review"]["approval_status"] == "verified_runtime_gates"
    readback = {"session_id": "s", "turn_id": "t2", "tool_name": "get"}
    assert not service.update(
        context,
        {
            "review_id": row["id"],
            "expected_version": 2,
            "action": "verify_readback",
            "evidence": readback,
            "readback_path": "missing",
        },
    ).success
    result = service.update(
        context,
        {
            "review_id": row["id"],
            "expected_version": 2,
            "action": "verify_readback",
            "evidence": readback,
            "readback_path": "campaign.budget",
        },
    )
    assert result.success and result.data["review"]["status"] == "verified"


def test_store_survives_reopen_without_overwriting_another_version(tmp_path):
    path = str(tmp_path / "reviews.db")
    store = AdAgentStore(path)
    assert store.save_optimization_review("r", "t", "u", {"status": "proposed"}, expected_version=0)
    store.close()
    store = AdAgentStore(path)
    try:
        assert store.get_optimization_review("r", "t", "u")["version"] == 1
        assert not store.save_optimization_review("r", "other", "u", {}, expected_version=1)
    finally:
        store.close()


def test_registered_review_tool_creates_only_local_record_through_harness():
    from agents.applications.advertising.composition.ad_application import AdvertisingComposition
    from agents.agent_platform.governance.identity.principal import RequestPrincipal
    from agents.agent_harness import ModelTurn
    from agents.tests.advertising.harness_models import install, call

    runtime = AdvertisingComposition(
        persistence_store=AdAgentStore(":memory:"),
        require_llm=False,
        offline_mode=True,
        start_background_workers=False,
    )
    principal = RequestPrincipal(
        user_id="u",
        permissions=frozenset({"ads.read", "ads.plan"}),
        account_scope={"test_ads": frozenset({"test-account"})},
    )
    try:
        install(
            runtime,
            ModelTurn(tool_calls=[call("agent_create_optimization_review", proposal())]),
            ModelTurn(content="仅登记建议，尚未修改广告。"),
        )
        result = runtime.run(
            "agent_create_optimization_review 登记预算优化建议", user_id="u", principal=principal
        )
        assert result["status"] == "succeeded", result
        records = runtime._persistence_store.list_optimization_reviews("default", "u")
        assert len(records) == 1 and records[0]["status"] == "proposed"
    finally:
        runtime.close(wait=True)


def test_missing_storage_is_an_explicit_unavailable_result(reviews):
    service, context, _ = reviews
    service.store = None
    for method, arguments in (
        (service.create, proposal()),
        (service.read, {}),
        (service.update, {"review_id": "missing"}),
    ):
        result = method(context, arguments)
        assert not result.success and "存储" in result.error


def test_reopen_requires_review_and_cooldown_and_preserves_previous_cycle(reviews):
    service, context, store = reviews
    row = service.create(context, {**proposal(), "cooldown_days": 90}).data["review"]
    args = {
        "review_id": row["id"],
        "expected_version": 1,
        "action": "reopen",
        "outcome": measurement(8),
        "proposal": "新一轮建议",
        "expected_value": 60,
    }
    assert not service.update(context, args).success
    row.update(
        status="reviewed", executed_at="2026-10-01T00:00:00+00:00", result={"causal_claim": False}
    )
    assert store.save_optimization_review(row["id"], "t", "u", row, expected_version=1)
    args["expected_version"] = 2
    assert "冷却" in service.update(context, args).error
    service.now = lambda: datetime(2027, 2, 1, tzinfo=timezone.utc)
    result = service.update(context, args)
    assert result.success, result.error
    new = result.data["review"]
    assert new["status"] == "proposed" and new["approval_status"] == "not_approved"
    assert new["previous_cycle"]["result"]["causal_claim"] is False
    assert "executed_at" not in new and "result" not in new


def test_list_pagination_and_revoked_account_scope(reviews):
    service, context, _ = reviews
    for resource in ("c1", "c2", "c3"):
        assert service.create(context, {**proposal(), "resource_id": resource}).success
    first = service.read(context, {"limit": 2}).data
    assert len(first["reviews"]) == 2 and first["has_more"]
    second = service.read(context, {"limit": 2, "offset": first["next_offset"]}).data
    assert len(second["reviews"]) == 1 and not second["has_more"]
    context.principal.account_scope = {}
    assert service.read(context, {}).data["reviews"] == []


def test_evidence_values_distinguish_booleans_from_numbers():
    from agents.applications.advertising.operations.optimization_evidence import same_value

    assert same_value(80, 80.0)
    assert not same_value(True, 1)
    assert not same_value("80", 80)


def test_baseline_must_precede_execution_in_the_measurement_timezone():
    from agents.applications.advertising.operations.optimization_measurements import (
        compare_measurements,
    )

    executed = datetime(2026, 9, 8, 23, 30, tzinfo=timezone.utc)
    baseline = measurement(
        10, timezone="Asia/Shanghai", start_date="2026-09-03", end_date="2026-09-09"
    )
    outcome = measurement(
        8, timezone="Asia/Shanghai", start_date="2026-09-10", end_date="2026-09-16"
    )
    with pytest.raises(ValueError, match="基线"):
        compare_measurements(
            baseline,
            outcome,
            executed_at=executed,
            observation_days=7,
            today=datetime(2026, 10, 29).date(),
        )
