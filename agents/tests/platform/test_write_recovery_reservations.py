"""Local replay-safety checks; no advertising clients or external writes."""

from types import SimpleNamespace
from contextlib import contextmanager

import pytest

from agents.agent_harness import (
    AgentApplication, AgentMessage, AgentState, ModelTurn, StaticToolSource,
    ToolBinding, ToolCall, ToolCallContext, TurnRequest,
)
from agents.agent_platform.tools.policy import ToolExecutionPolicy
from agents.applications.advertising.persistence.adapters import PersistenceIdempotencyStore
from agents.applications.advertising.persistence.store import AdAgentStore


DEFINITION = {
    "name": "write_record", "effect_class": "write", "live_support": True,
    "idempotency_key_field": "request_id",
    "input_schema": {
        "type": "object", "required": ["request_id"],
        "properties": {"request_id": {"type": "string"}},
        "additionalProperties": False,
    },
}


def _context(run_id="run", call_id="call"):
    return ToolCallContext(
        request=TurnRequest(
            "write", tenant_id="tenant", user_id="user", run_id=run_id, turn_id=run_id,
            execution_mode="live",
            principal=SimpleNamespace(tenant_id="tenant", user_id="user"),
            context={"confirmed": True, "confirmation_payload": {"plan": "same"}},
        ),
        assistant_message=AgentMessage.assistant(""),
        tool_call=ToolCall(call_id, "write_record", {"request_id": "same"}),
        state=AgentState(), tool_definition=DEFINITION,
    )


def _policy(store, audit=None):
    return ToolExecutionPolicy(
        allow_live_writes=True, live_approved_tools={"write_record"},
        write_guard_configured=True, require_confirmation_for_writes=True,
        idempotency_store=store, audit_sink=audit,
    )


def test_unknown_write_error_keeps_durable_replay_block_and_unknown_audit(tmp_path):
    backend = AdAgentStore(str(tmp_path / "replay.db"))
    store = PersistenceIdempotencyStore(backend)
    audits = []
    policy = _policy(store, audits.append)
    first = _context()
    try:
        assert policy.before_tool_call(first) is None
        outcome = policy.after_tool_call(first, {
            "is_error": True, "recovery_required": True, "effect_state": "unknown",
        })
        assert outcome["recovery_required"] is True
        row = backend._get_conn().execute(
            "SELECT status FROM write_reservations",
        ).fetchone()
        assert row["status"] == "uncertain"
        assert policy.before_tool_call(_context("another")) is not None
        assert audits[-2]["decision"] == "unknown"
        assert audits[-2]["reason_code"] == "provider_result_unknown"
    finally:
        backend.close()


def test_unknown_reservation_survives_expiry_restart_and_normal_release(tmp_path):
    path = str(tmp_path / "uncertain.db")
    first = AdAgentStore(path)
    adapter = PersistenceIdempotencyStore(first)
    assert adapter.reserve("key", request_hash="hash", ttl_seconds=1)
    adapter.mark_uncertain("key", request_hash="hash")
    first._get_conn().execute(
        "UPDATE write_reservations SET updated_at = ? WHERE idempotency_key = ?",
        ("2000-01-01T00:00:00+00:00", "key"),
    )
    first._get_conn().commit()
    first.close()
    reopened = AdAgentStore(path)
    adapter = PersistenceIdempotencyStore(reopened)
    try:
        adapter.release("key", request_hash="hash")
        assert not adapter.reserve("key", request_hash="hash", ttl_seconds=1)
        assert not adapter.resolve_uncertain("key", request_hash="wrong", executed=False)
        assert not adapter.reserve("key", request_hash="hash", ttl_seconds=1)
        assert adapter.resolve_uncertain("key", request_hash="hash", executed=False)
        assert adapter.reserve("key", request_hash="hash", ttl_seconds=1)
    finally:
        reopened.close()


def test_pending_after_process_loss_is_not_automatically_replayed_after_ttl(tmp_path):
    path = str(tmp_path / "crashed.db")
    backend = AdAgentStore(path)
    store = PersistenceIdempotencyStore(backend)
    assert store.reserve("key", request_hash="hash", ttl_seconds=1)
    backend._get_conn().execute(
        "UPDATE write_reservations SET updated_at = ?",
        ("2000-01-01T00:00:00+00:00",),
    )
    backend._get_conn().commit()
    backend.close()
    reopened = AdAgentStore(path)
    store = PersistenceIdempotencyStore(reopened)
    try:
        assert not store.reserve("key", request_hash="hash", ttl_seconds=1)
        assert store.resolve_uncertain("key", request_hash="hash", executed=False)
        assert store.reserve("key", request_hash="hash", ttl_seconds=1)
    finally:
        reopened.close()


def test_uncertain_state_requires_exact_hash_and_cannot_downgrade_to_executed():
    backend = AdAgentStore(":memory:")
    store = PersistenceIdempotencyStore(backend)
    try:
        assert store.reserve("key", request_hash="hash", ttl_seconds=60)
        with pytest.raises(RuntimeError):
            store.mark_uncertain("key", request_hash="wrong")
        store.mark_uncertain("key", request_hash="hash")
        with pytest.raises(RuntimeError, match="executed"):
            store.mark_executed("key", request_hash="hash")
        assert backend._get_conn().execute(
            "SELECT status FROM write_reservations",
        ).fetchone()["status"] == "uncertain"
        assert store.resolve_uncertain("key", request_hash="hash", executed=True)
        assert not store.reserve("key", request_hash="hash", ttl_seconds=60)
    finally:
        backend.close()


def test_all_reservation_finalizers_are_attempted_even_when_one_fails():
    attempts = []

    class Store:
        def release(self, key, *, request_hash):
            attempts.append(key)
            raise RuntimeError("private backend detail")

    policy = _policy(Store())
    policy._reservations_by_call[("run", "run", "call")] = {("a", "ha"), ("b", "hb")}
    result = policy.after_tool_call(_context(), {"is_error": True, "effect_state": "none"})
    assert set(attempts) == {"a", "b"}
    assert result["recovery_required"]
    assert result["runtime_signals"]["idempotency_store_error"]
    assert "private backend detail" not in repr(result)


def test_circuit_rejection_releases_unused_reservation_and_runs_audit():
    backend = AdAgentStore(":memory:")
    executions, audits = [], []
    policy = _policy(PersistenceIdempotencyStore(backend), audits.append)

    class Model:
        def complete(self, *_):
            return ModelTurn(tool_calls=(ToolCall("call", "write_record", {"request_id": "same"}),))

    app = AgentApplication.create(
        model=Model(), max_turns=1, tool_policy=policy,
        tool_circuit_failure_threshold=1,
    )
    app.register_tool_source(StaticToolSource("test", [
        ToolBinding(DEFINITION, lambda *_: executions.append("write") or {"success": True}),
    ]))
    try:
        circuit_key = app.agent._tool_executor._circuit_key(_context().request, "write_record")
        app.agent._tool_circuit.record_failure(circuit_key)
        blocked = app.runtime.run(_context().request)
        assert not executions
        assert blocked.data["tool_results"][0]["runtime_signals"]["tool_circuit_open"]
        assert policy._reservations_by_call == {}
        assert audits[-1]["decision"] == "failed"
        app.agent._tool_circuit.record_success(circuit_key)
        app.runtime.run(_context("retry").request)
        assert executions == ["write"]
    finally:
        app.close()
        backend.close()


def test_unknown_write_preserves_the_original_failure_signals():
    policy = ToolExecutionPolicy()
    result = policy.after_tool_call(_context(), {
        "is_error": True, "effect_state": "unknown",
        "runtime_signals": {"tool_timeout": True, "tool_output_invalid": True},
    })
    assert result["runtime_signals"]["tool_timeout"] is True
    assert result["runtime_signals"]["tool_output_invalid"] is True


def test_non_boolean_store_reservation_is_not_an_execution_permit():
    class Store:
        def reserve(self, *_args, **_kwargs):
            return "false"

    blocked = _policy(Store()).before_tool_call(_context())
    assert blocked["runtime_signals"]["idempotency_store_error"] is True
    assert blocked["recovery_required"] is True


def test_persistence_adapter_does_not_coerce_invalid_backend_reservation():
    backend = SimpleNamespace(reserve_write=lambda *_args, **_kwargs: "false")
    blocked = _policy(PersistenceIdempotencyStore(backend)).before_tool_call(_context())
    assert blocked["runtime_signals"]["idempotency_store_error"] is True
    assert blocked["recovery_required"] is True


def test_persistence_adapter_requires_a_matching_executed_transition():
    backend = AdAgentStore(":memory:")
    store = PersistenceIdempotencyStore(backend)
    try:
        with pytest.raises(RuntimeError, match="executed"):
            store.mark_executed("missing", request_hash="hash")
        assert store.reserve("key", request_hash="hash", ttl_seconds=60)
        with pytest.raises(RuntimeError, match="executed"):
            store.mark_executed("key", request_hash="wrong")
        store.mark_executed("key", request_hash="hash")
        assert backend._get_conn().execute(
            "SELECT status FROM write_reservations WHERE idempotency_key = 'key'",
        ).fetchone()["status"] == "executed"
    finally:
        backend.close()


def test_policy_reports_failed_execution_finalizer_as_recovery_required():
    backend = AdAgentStore(":memory:")
    store = PersistenceIdempotencyStore(backend)
    policy = _policy(store)
    context = _context()
    try:
        assert policy.before_tool_call(context) is None
        backend._get_conn().execute("DELETE FROM write_reservations")
        backend._get_conn().commit()
        result = policy.after_tool_call(context, {"success": True})
        assert result["recovery_required"] is True
        assert result["runtime_signals"]["idempotency_store_error"] is True
    finally:
        backend.close()


@pytest.mark.parametrize("action", ["release", "mark_executed", "mark_uncertain"])
def test_invalid_store_finalizer_acknowledgement_is_not_reported_as_success(action):
    class Store:
        def __getattr__(self, name):
            assert name == action
            return lambda *_args, **_kwargs: False

    policy = _policy(Store())
    policy._reservations_by_call[("run", "run", "call")] = {("key", "hash")}
    outcome = {
        "release": {"is_error": True, "effect_state": "none"},
        "mark_executed": {"is_error": False},
        "mark_uncertain": {"effect_state": "unknown"},
    }[action]
    result = policy.after_tool_call(_context(), outcome)
    assert result["runtime_signals"]["idempotency_store_error"]
    assert result["recovery_required"]


def test_mysql_quarantine_statements_obey_the_same_hash_bound_transitions():
    from agents.applications.advertising.persistence.mysql_store import MySQLStore

    sqlite_store = AdAgentStore(":memory:")
    sqlite_store.reserve_write("key", request_hash="opaque-recovery-hash")
    statements = []

    class PortableSQLConnection:
        def execute(self, statement, parameters):
            statements.append((statement, parameters))
            return sqlite_store._get_conn().execute(statement.removesuffix(" FOR UPDATE"), parameters)

        @contextmanager
        def transaction(self):
            try:
                yield
                sqlite_store._get_conn().commit()
            except BaseException:
                sqlite_store._get_conn().rollback()
                raise

    mysql = MySQLStore.__new__(MySQLStore)
    mysql._get_conn = lambda: PortableSQLConnection()
    try:
        assert mysql.mark_write_uncertain("key", "opaque-recovery-hash")
        assert not mysql.reserve_write("key", ttl_seconds=0, request_hash="opaque-recovery-hash")
        assert not mysql.resolve_write_uncertain("key", request_hash="wrong", executed=False)
        with pytest.raises(RuntimeError, match="executed"):
            mysql.mark_write_executed("key", request_hash="opaque-recovery-hash")
        assert sqlite_store._get_conn().execute(
            "SELECT status FROM write_reservations",
        ).fetchone()["status"] == "uncertain"
        assert mysql.resolve_write_uncertain("key", request_hash="opaque-recovery-hash", executed=True)
        assert sqlite_store._get_conn().execute(
            "SELECT status FROM write_reservations",
        ).fetchone()["status"] == "executed"
        assert all("opaque-recovery-hash" not in statement for statement, _ in statements)
    finally:
        sqlite_store.close()
