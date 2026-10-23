from agents.agent_harness import (
    AgentApplication,
    AgentMessage,
    AgentState,
    ModelTurn,
    StaticToolSource,
    ToolBinding,
    ToolCall,
    TurnRequest,
)
from agents.agent_harness.tool_execution import ToolCallContext
from agents.agent_platform.tools.policy import ToolExecutionPolicy


def context(effect, arguments=None, schema=None):
    return ToolCallContext(
        request=TurnRequest(user_input="test", run_id="r", turn_id="t"),
        assistant_message=AgentMessage.assistant(""),
        tool_call=ToolCall("c", "test_tool", arguments or {}),
        state=AgentState(),
        tool_definition={
            "name": "test_tool",
            "effect_class": effect,
            "input_schema": schema or {},
        },
    )


def test_failed_read_does_not_claim_an_uncertain_external_write():
    result = ToolExecutionPolicy().after_tool_call(
        context("read"), {"success": False, "is_error": True}
    )
    assert result is None


def test_uncertain_write_still_requires_reconciliation():
    result = ToolExecutionPolicy().after_tool_call(
        context("write"),
        {
            "success": False,
            "is_error": False,
            "data": {"execution_status": "unknown"},
        },
    )
    assert result["recovery_required"] is True


def test_extra_model_argument_can_be_repaired_without_requesting_user_input():
    call_context = context(
        "read",
        {"value": "given", "account_id": "extra"},
        schema={
            "type": "object",
            "properties": {"value": {"type": "string"}},
            "required": ["value"],
            "additionalProperties": False,
        },
    )
    blocked = ToolExecutionPolicy().before_tool_call(call_context)
    assert blocked["block"] is True
    assert blocked["needs_input"] is False
    assert blocked["terminate"] is False


def test_missing_required_value_still_requires_user_input():
    call_context = context(
        "read",
        schema={
            "type": "object",
            "properties": {"value": {"type": "string"}},
            "required": ["value"],
            "additionalProperties": False,
        },
    )
    blocked = ToolExecutionPolicy().before_tool_call(call_context)
    assert blocked["needs_input"] is True
    assert blocked["terminate"] is True


def test_trusted_argument_resolver_runs_before_schema_and_executor():
    executed = []

    class Model:
        called = False

        def complete(self, _messages, _tools, _request):
            if not self.called:
                self.called = True
                return ModelTurn(tool_calls=(ToolCall("resolved", "read", {}),))
            return ModelTurn(content="done")

    def resolve_arguments(context):
        return {
            **dict(context.tool_call.arguments),
            "value": "resolved-from-trusted-context",
        }

    app = AgentApplication.create(
        model=Model(),
        max_turns=3,
        tool_policy=ToolExecutionPolicy(argument_resolver=resolve_arguments),
    )
    app.register_tool_source(
        StaticToolSource(
            "read-source",
            [
                ToolBinding(
                    {
                        "name": "read",
                        "effect_class": "read",
                        "input_schema": {
                            "type": "object",
                            "properties": {"value": {"type": "string"}},
                            "required": ["value"],
                            "additionalProperties": False,
                        },
                    },
                    lambda _ctx, values: executed.append(values) or {"success": True},
                ),
            ],
        )
    )
    try:
        result = app.prompt("read using selected context")
        assert result.status.value == "succeeded"
        assert executed == [{"value": "resolved-from-trusted-context"}]
    finally:
        app.close()


def test_argument_resolution_failure_blocks_execution_and_emits_safe_audit():
    audit_events = []

    def fail_resolution(_context):
        raise RuntimeError("private template detail")

    policy = ToolExecutionPolicy(
        argument_resolver=fail_resolution,
        audit_sink=audit_events.append,
    )
    call_context = context(
        "read",
        schema={
            "type": "object",
            "properties": {"value": {"type": "string"}},
            "required": ["value"],
            "additionalProperties": False,
        },
    )

    blocked = policy.before_tool_call(call_context)

    assert blocked["block"] is True
    assert blocked["terminate"] is True
    assert blocked["runtime_signals"]["tool_argument_resolution_error"] is True
    assert blocked["runtime_signals"]["tool_argument_resolution_error_type"] == "RuntimeError"
    assert "private template detail" not in repr(blocked)
    assert audit_events == [{
        "run_id": "r",
        "turn_id": "t",
        "tool_name": "test_tool",
        "decision": "blocked",
        "reason_code": "argument_resolution_failed",
    }]


def test_known_argument_validation_failure_returns_only_safe_actionable_text():
    from agents.agent_platform.tools.policy import ToolArgumentValidationError

    def fail_resolution(_context):
        raise ToolArgumentValidationError("素材字段尚未通过当前账户资源查询校验，请重新选择素材。")

    policy = ToolExecutionPolicy(argument_resolver=fail_resolution)
    blocked = policy.before_tool_call(context("read"))
    assert blocked["block"] is True
    assert "重新选择素材" in blocked["reason"]
    assert blocked["needs_input"] is True


def test_harness_reenters_model_after_extra_argument_without_executing_invalid_call():
    executed = []

    class Model:
        turn = 0

        def complete(self, _messages, _tools, _request):
            self.turn += 1
            if self.turn == 1:
                return ModelTurn(
                    tool_calls=(
                        ToolCall("bad", "read", {"value": "given", "extra": "invalid"}),
                    )
                )
            if self.turn == 2:
                return ModelTurn(
                    tool_calls=(ToolCall("good", "read", {"value": "given"}),)
                )
            return "done"

    app = AgentApplication.create(
        model=Model(), max_turns=3, tool_policy=ToolExecutionPolicy()
    )
    app.register_tool_source(
        StaticToolSource(
            "read-source",
            [
                ToolBinding(
                    {
                        "name": "read",
                        "effect_class": "read",
                        "input_schema": {
                            "type": "object",
                            "properties": {"value": {"type": "string"}},
                            "required": ["value"],
                            "additionalProperties": False,
                        },
                    },
                    lambda _ctx, values: executed.append(values) or {"success": True},
                ),
            ],
        )
    )
    try:
        result = app.prompt("read given")
        assert result.status.value == "succeeded"
        assert executed == [{"value": "given"}]
    finally:
        app.close()


def test_harness_stops_after_repeating_the_same_schema_repairable_call():
    class Model:
        turn = 0

        def complete(self, _messages, _tools, _request):
            self.turn += 1
            if self.turn <= 3:
                return ModelTurn(tool_calls=(
                    ToolCall(
                        f"bad-{self.turn}",
                        "read",
                        {"value": "given", "extra": "invalid"},
                    ),
                ))
            return "This should not be reached."

    executions = []
    model = Model()
    app = AgentApplication.create(
        model=model, max_turns=6, tool_policy=ToolExecutionPolicy()
    )
    app.register_tool_source(
        StaticToolSource(
            "read-source",
            [
                ToolBinding(
                    {
                        "name": "read",
                        "effect_class": "read",
                        "input_schema": {
                            "type": "object",
                            "properties": {"value": {"type": "string"}},
                            "required": ["value"],
                            "additionalProperties": False,
                        },
                    },
                    lambda _ctx, values: executions.append(values) or {
                        "success": True,
                    },
                ),
            ],
        )
    )
    try:
        result = app.prompt("read the record")
        tool_results = result.data["tool_results"]

        assert result.status.value == "failed"
        assert model.turn == 2
        assert len(tool_results) == 2
        assert tool_results[-1]["terminate"] is True
        assert tool_results[-1]["runtime_signals"][
            "schema_repair_retry_exhausted"
        ] is True
        assert "Field 'extra' is not allowed" in result.reply
        assert executions == []
    finally:
        app.close()
