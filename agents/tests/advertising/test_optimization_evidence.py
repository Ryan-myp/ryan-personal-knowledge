from types import SimpleNamespace

import pytest

from agents.applications.advertising.operations.optimization_evidence import load_evidence
from agents.applications.advertising.persistence.models import ToolCallRecord
from agents.applications.advertising.persistence.store import AdAgentStore


@pytest.fixture
def evidence():
    store = AdAgentStore(":memory:")
    store.create_session("s", "u", metadata={"tenant_id": "t"})
    principal = SimpleNamespace(user_id="u", tenant_id="t")
    definition = SimpleNamespace(is_write_tool=False, namespace="test_ads",
                                 resource_type="campaign", resource_id_field="campaign_id",
                                 scope_fields=["account_id"])
    registry = SimpleNamespace(get=lambda name: (definition, None))
    reference = {"session_id": "s", "turn_id": "turn", "tool_name": "get"}
    review = {"namespace": "test-ads", "resource_type": "campaign",
              "account_id": "a1", "resource_id": "c1"}
    def record(identifier, *, account="a1", resource="c1", output=None, success=True):
        store.record_tool_call(ToolCallRecord(
            id=identifier, session_id="s", turn_id="turn", tool_name="get", platform="test_ads",
            input_data={"account_id": account, "campaign_id": resource},
            output_data={"data_status": "live"} if output is None else output, success=success,
        ))
    def load():
        return load_evidence(store, registry, principal, reference, review, writing=False)[0]
    yield record, load, principal, store
    store.close()


def test_same_turn_batch_disambiguates_by_audited_account_and_resource(evidence):
    record, load, _, _ = evidence
    record("other-resource", resource="c2")
    record("other-account", account="a2")
    record("target")
    assert load().id == "target"


def test_repeated_target_cannot_silently_choose_a_successful_attempt(evidence):
    record, load, _, _ = evidence
    record("failed-attempt", success=False)
    record("success")
    with pytest.raises(ValueError, match="多个|歧义"):
        load()


@pytest.mark.parametrize("output", [{}, {"data_status": "unknown"},
                                      {"data_status": "live", "simulated": True},
                                      {"data_status": "live", "execution_mode": "dry_run"}])
def test_readback_requires_explicit_live_provenance(evidence, output):
    record, load, _, _ = evidence
    record("target", output=output)
    with pytest.raises(ValueError, match="live|模拟"):
        load()


def test_evidence_window_fails_closed_instead_of_hiding_duplicate_target(evidence):
    record, load, _, _ = evidence
    record("target")
    for i in range(99):
        record(f"other-{i}", resource=f"other-{i}")
    record("target-again")
    with pytest.raises(ValueError, match="上限"):
        load()


def test_foreign_principal_cannot_use_audit_records(evidence):
    record, load, principal, _ = evidence
    record("target")
    principal.tenant_id = "other"
    with pytest.raises(ValueError, match="身份"):
        load()


def test_wrong_target_or_failed_call_cannot_verify_readback(evidence):
    record, load, _, _ = evidence
    record("other", resource="c2")
    with pytest.raises(ValueError):
        load()
    record("failed-target", success=False)
    with pytest.raises(ValueError, match="失败"):
        load()
