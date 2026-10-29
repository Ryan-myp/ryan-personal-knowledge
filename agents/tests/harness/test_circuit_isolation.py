"""Dependency recovery is bounded and cannot block another principal."""

from concurrent.futures import ThreadPoolExecutor

import pytest

from agents.agent_harness import AgentApplication, ModelTurn, StaticToolSource, ToolBinding, ToolCall
from agents.agent_harness.reliability import ToolCircuitBreaker


def test_tool_failures_do_not_open_another_identity_circuit():
    calls = []

    class Model:
        def complete(self, messages, _tools, _request):
            if messages[-1].role == "user":
                return ModelTurn(tool_calls=(ToolCall("read", "lookup", {}),))
            return "done"

    def lookup(context, _arguments):
        identity = (context.request.tenant_id, context.request.user_id)
        calls.append(identity)
        if identity == ("tenant", "alice"):
            raise TimeoutError("temporary")
        return {"success": True, "data": {"value": 1}}

    app = AgentApplication.create(
        model=Model(), tool_max_retries=0, tool_circuit_failure_threshold=1,
    )
    app.register_tool_source(StaticToolSource("read", [ToolBinding(
        {"name": "lookup", "effect_class": "read"}, lookup,
    )]))
    try:
        for tenant, user in (("tenant", "alice"), ("tenant", "bob"), ("other", "alice")):
            app.prompt("lookup", session_id=f"{tenant}-{user}", tenant_id=tenant, user_id=user)
        assert calls == [("tenant", "alice"), ("tenant", "bob"), ("other", "alice")]
    finally:
        app.close()


def test_cooling_circuit_allows_one_concurrent_recovery_probe(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr("agents.agent_harness.reliability.time.monotonic", lambda: clock[0])
    circuit = ToolCircuitBreaker(failure_threshold=1, reset_seconds=10)
    circuit.record_failure("dependency")
    assert circuit.allow("dependency") is False
    clock[0] = 11

    with ThreadPoolExecutor(max_workers=8) as executor:
        admitted = list(executor.map(lambda _: circuit.allow("dependency"), range(16)))

    assert sum(admitted) == 1
    circuit.record_success("dependency")
    assert circuit.allow("dependency") is True


def test_abandoned_probe_reopens_without_permanent_lockout(monkeypatch):
    clock = [100.0]
    monkeypatch.setattr("agents.agent_harness.reliability.time.monotonic", lambda: clock[0])
    circuit = ToolCircuitBreaker(failure_threshold=1, reset_seconds=10)
    circuit.record_failure("dependency")
    clock[0] += 11
    assert circuit.allow("dependency") is True

    circuit.abandon_probe("dependency")

    assert circuit.allow("dependency") is False
    clock[0] += 11
    assert circuit.allow("dependency") is True
    circuit.record_failure("dependency")
    assert circuit.allow("dependency") is False


def test_circuit_state_is_bounded():
    circuit = ToolCircuitBreaker(max_entries=3)
    for index in range(20):
        circuit.record_failure(f"dependency-{index}")
    assert len(circuit.snapshot()) == 3


def test_probe_lease_expiry_allows_one_new_attempt(monkeypatch):
    clock = [100.0]
    monkeypatch.setattr("agents.agent_harness.reliability.time.monotonic", lambda: clock[0])
    circuit = ToolCircuitBreaker(
        failure_threshold=1, reset_seconds=10, probe_timeout_seconds=20,
    )
    circuit.record_failure("dependency")
    clock[0] += 11
    assert circuit.allow("dependency")
    clock[0] += 21
    assert circuit.allow("dependency")
    assert circuit.allow("dependency") is False


@pytest.mark.parametrize("options", [
    {"failure_threshold": True}, {"max_entries": 0},
    {"reset_seconds": float("nan")}, {"reset_seconds": True},
    {"probe_timeout_seconds": float("inf")},
])
def test_invalid_circuit_configuration_fails_early(options):
    with pytest.raises(ValueError):
        ToolCircuitBreaker(**options)
