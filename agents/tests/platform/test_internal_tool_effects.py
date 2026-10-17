from types import SimpleNamespace

import pytest

from agents.agent_harness import ToolCall, ToolCallContext
from agents.agent_harness.core.interfaces import (
    ReplayPolicy,
    RiskLevel,
    ToolDefinition,
    ToolEffect,
    ToolSchema,
)
from agents.agent_platform.governance.identity.principal import RequestPrincipal
from agents.agent_platform.tools.policy import ToolExecutionPolicy


class IdempotencyStore:
    def __init__(self):
        self.keys = set()

    def reserve(self, key, *, request_hash, ttl_seconds):
        del request_hash, ttl_seconds
        if key in self.keys:
            return False
        self.keys.add(key)
        return True

    def mark_executed(self, key, *, request_hash):
        del key, request_hash

    def release(self, key, *, request_hash):
        del key, request_hash


def _internal_write_definition():
    return ToolDefinition(
        name="agent_schedule_create",
        skill="agent-scheduling",
        namespace="agent_platform",
        description="Create an Agent schedule",
        input_schema=ToolSchema(
            properties={"prompt": {"type": "string"}},
            required=["prompt"],
        ),
        action="schedule",
        resource_type="scheduled_task",
        intent_types=["schedule_create"],
        risk_level=RiskLevel.MEDIUM,
        effect_class=ToolEffect.INTERNAL_WRITE,
        replay_policy=ReplayPolicy.UNSAFE,
        required_permissions=["agent.schedule.write"],
        scope_required=False,
    )


def _call_context(definition, *, call_id, mode):
    request = SimpleNamespace(
        run_id="run-1",
        turn_id="turn-1",
        user_id="operator-1",
        tenant_id="tenant-1",
        execution_mode=mode,
        principal=RequestPrincipal(
            user_id="operator-1",
            tenant_id="tenant-1",
            permissions=frozenset({"agent.schedule.write"}),
        ),
        context={},
    )
    return ToolCallContext(
        request=request,
        assistant_message=None,
        tool_call=ToolCall(
            id=call_id,
            name=definition.name,
            arguments={"prompt": "Check campaign status"},
        ),
        state=None,
        tool_definition=definition,
    )


@pytest.mark.parametrize("mode", ["dry_run", "live"])
def test_internal_write_uses_permissions_and_durable_idempotency_without_provider_gates(mode):
    store = IdempotencyStore()
    policy = ToolExecutionPolicy(
        allow_live_writes=False,
        write_guard_configured=False,
        idempotency_store=store,
    )
    definition = _internal_write_definition()

    first = _call_context(definition, call_id="call-1", mode=mode)
    duplicate = _call_context(definition, call_id="call-2", mode=mode)

    assert policy.before_tool_call(first) is None
    rejected = policy.before_tool_call(duplicate)
    assert rejected["block"] is True
    assert "Duplicate internal Tool request" in rejected["reason"]
    assert len(store.keys) == 1
