"""Regression tests for the dap_agent-inspired safety contracts."""

from datetime import datetime, timedelta
from types import SimpleNamespace

from agents.ad_agent.api_clients.base import AuthError, RateLimitError, TemporaryError
from agents.ad_agent.core.interfaces import (
    ToolDefinition, ToolEffect, ToolError, ToolResult, ToolSchema,
)
from agents.ad_agent.core.tool_registry import SimpleToolRegistry
from agents.ad_agent.persistence.models import OutboxEvent
from agents.ad_agent.persistence.store import AdAgentStore
from agents.ad_agent.runtime.outbox import OutboxConsumer
from agents.ad_agent.runtime.runtime import AgentRuntime
from agents.ad_agent.runtime.security import RuntimeSecurity
from agents.ad_agent.runtime.tool_executor import classify_error


def _tool(name="meta_update_campaign", effect=ToolEffect.WRITE):
    return ToolDefinition(
        name=name, skill="meta", namespace="meta", description="update",
        input_schema=ToolSchema(properties={"campaign_id": {"type": "string"}}),
        action="update", resource_type="campaign", intent_types=["update_campaign"],
        effect_class=effect,
    )


def test_canonical_confirmation_hashes_bind_input_preview_request_and_contract():
    tool = _tool()
    first = RuntimeSecurity.confirmation_plan(
        "s1", "u1", "a1", tool, {"campaign_id": "c1"},
        preview={"tool": tool.name, "input": {"campaign_id": "c1"}},
    )
    equivalent = RuntimeSecurity.confirmation_plan(
        "s1", "u1", "a1", tool, {"campaign_id": "c1"},
        preview={"input": {"campaign_id": "c1"}, "tool": tool.name},
    )
    changed = RuntimeSecurity.confirmation_plan(
        "s1", "u1", "a1", tool, {"campaign_id": "c2"},
        preview={"tool": tool.name, "input": {"campaign_id": "c2"}},
    )
    assert first["input_hash"] == equivalent["input_hash"]
    assert first["preview_hash"] == equivalent["preview_hash"]
    assert first["request_hash"] == equivalent["request_hash"]
    assert first["input_hash"] != changed["input_hash"]
    assert first["preview_hash"] != changed["preview_hash"]
    assert first["request_hash"] != changed["request_hash"]


def test_approval_hash_binding_rejects_tampering():
    store = AdAgentStore(":memory:")
    tool = _tool()
    plan = RuntimeSecurity.confirmation_plan("s1", "u1", "a1", tool, {"campaign_id": "c1"})
    store.create_approval(
        plan["plan_fingerprint"], plan["confirmation_token"], "s1", "u1", "a1",
        tool.name, (datetime.now() + timedelta(minutes=5)).isoformat(),
        plan["input_hash"], plan["preview_hash"], plan["request_hash"],
        plan["contract_hash"],
    )
    assert store.validate_approval(
        plan["plan_fingerprint"], plan["confirmation_token"], "s1", "u1", "a1",
        tool.name, plan["input_hash"], plan["preview_hash"],
        plan["request_hash"], plan["contract_hash"],
    ) == (True, "")
    assert not store.validate_approval(
        plan["plan_fingerprint"], plan["confirmation_token"], "s1", "u1", "a1",
        tool.name, "tampered", plan["preview_hash"],
        plan["request_hash"], plan["contract_hash"],
    )[0]


def test_registry_rejects_same_tool_name_with_schema_drift():
    registry = SimpleToolRegistry()
    registry.register(_tool("tool"), lambda _ctx, _value: ToolResult.ok({}))
    drifted = _tool("tool")
    drifted.input_schema.properties["new_field"] = {"type": "string"}
    drifted.contract_hash = "changed-contract"
    try:
        registry.register(drifted, lambda _ctx, _value: ToolResult.ok({}))
    except ValueError as exc:
        assert "contract hash mismatch" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("schema drift was accepted")


def test_outbox_claim_is_single_delivery_and_consumer_acknowledges():
    store = AdAgentStore(":memory:")
    store.insert_outbox_event(OutboxEvent("e1", "w1", "workflow.updated", {"status": "failed"}))
    seen = []
    consumer = OutboxConsumer(store, lambda event: seen.append(event.event_id))
    assert consumer.drain_once() == 1
    assert consumer.drain_once() == 0
    assert seen == ["e1"]


def test_outbox_delivery_moves_to_dead_letter_after_bounded_retries():
    store = AdAgentStore(":memory:")
    store.insert_outbox_event(OutboxEvent("dead", "w1", "workflow.updated", {}))

    def failing_sink(_event):
        raise RuntimeError("sink down")

    consumer = OutboxConsumer(store, failing_sink, max_attempts=1)
    assert consumer.drain_once() == 0
    event = store._get_conn().execute(
        "SELECT status, retry_count FROM outbox_events WHERE event_id = ?", ("dead",)
    ).fetchone()
    assert event["status"] == "dead_letter"
    assert event["retry_count"] == 0
    assert consumer.metrics()["dead_letter_total"] == 1
    store.close()


def test_runtime_starts_outbox_consumer_and_workflow_publishes_once():
    store = AdAgentStore(":memory:")
    delivered = []
    runtime = AgentRuntime(
        require_llm=False,
        persistence_store=store,
        features=[],
        outbox_delivery=lambda event: delivered.append(event.event_type),
        outbox_poll_interval=60,
    )
    try:
        assert runtime.outbox_consumer is not None
        assert runtime.outbox_consumer._thread is not None
        assert runtime.outbox_consumer._thread.is_alive()

        # Stop the background loop so the test can inspect the durable event.
        runtime.outbox_consumer.stop()
        store.create_session("s1", "u1")
        workflow_id = runtime.workflow.start(
            SimpleNamespace(
                session_id="s1",
                ctx=SimpleNamespace(account_id=None),
            ),
            SimpleNamespace(
                intent_type="update_campaign",
                namespaces=["meta"],
                raw_input="更新 campaign",
            ),
            {"meta": [_tool()]},
            register_items=False,
        )
        events = store.claim_outbox_events(10, "test-workflow-publisher")
        assert workflow_id
        assert len(events) == 1
        assert events[0].event_type == "workflow.created"
        assert delivered == []
    finally:
        runtime.close()


def test_error_classification_preserves_three_state_write_recovery_semantics():
    write = _tool()
    read = _tool("meta_get_campaign", ToolEffect.READ)
    assert classify_error(TimeoutError("timeout"), write).category == "provider_result_unknown"
    assert classify_error(TemporaryError("temporary"), write).code == "PROVIDER_RESULT_UNKNOWN"
    assert classify_error(RateLimitError("rate"), read).category == "retriable"
    assert classify_error(AuthError("expired"), read).code == "AUTH_EXPIRED"
    result = ToolResult.error(
        "provider timeout",
        detail=ToolError("provider_result_unknown", "PROVIDER_RESULT_UNKNOWN", "timeout"),
    )
    assert result.to_dict()["error_detail"]["category"] == "provider_result_unknown"
