import time

import pytest

from agents.agent_harness import (
    AgentApplication,
    BoundedContextProvider,
    MCPToolExecutor,
    MCPToolSource,
    ModelTurn,
    StaticToolSource,
    ToolBinding,
    ToolCall,
    ToolArgumentBinding,
    TurnRequest,
)
from agents.agent_harness.tool_execution import ToolExecutionCoordinator


def test_tool_calls_are_executed_in_dependency_batches():
    calls = []

    class Model:
        def __init__(self):
            self.turn = 0

        def complete(self, _messages, _tools, _request):
            self.turn += 1
            if self.turn == 1:
                return ModelTurn(tool_calls=(
                    ToolCall("lookup", "lookup", {"value": "x"}),
                    ToolCall("publish", "publish", {"value": "x"}, depends_on=("lookup",)),
                    ToolCall("audit", "audit", {"value": "x"}),
                ))
            return "done"

    app = AgentApplication.create(model=Model(), max_turns=3)
    app.register_tool_source(StaticToolSource(
        "tools",
        [
            ToolBinding({"name": "lookup"}, lambda _ctx, value: calls.append(("lookup", value)) or {"ok": True}),
            ToolBinding({"name": "publish"}, lambda _ctx, value: calls.append(("publish", value)) or {"ok": True}),
            ToolBinding({"name": "audit"}, lambda _ctx, value: calls.append(("audit", value)) or {"ok": True}),
        ],
    ))
    try:
        result = app.prompt("run")
        assert result.status.value == "succeeded"
        names = [name for name, _value in calls]
        assert names.index("publish") > names.index("lookup")
        assert set(names[:2]) == {"lookup", "audit"}
    finally:
        app.close()


def test_dependency_binding_uses_prior_tool_output_without_domain_runtime():
    executed = []

    class Model:
        def __init__(self):
            self.turn = 0

        def complete(self, _messages, _tools, _request):
            self.turn += 1
            if self.turn == 1:
                return ModelTurn(tool_calls=(
                    ToolCall("parent", "create_parent", {"name": "parent"}),
                    ToolCall(
                        "child", "create_child", {"name": "child"},
                        depends_on=("parent",),
                        argument_bindings=(ToolArgumentBinding(
                            target_field="parent_id",
                            source_call_id="parent",
                            source_path="data.id",
                        ),),
                    ),
                ))
            return "done"

    app = AgentApplication.create(model=Model(), tool_execution="sequential")
    app.register_tool_source(StaticToolSource(
        "resources",
        [
            ToolBinding(
                {"name": "create_parent"},
                lambda _ctx, value: executed.append(("parent", value)) or {
                    "success": True, "data": {"id": "resource-42"},
                },
            ),
            ToolBinding(
                {
                    "name": "create_child",
                    "input_schema": {"properties": {
                        "name": {}, "parent_id": {},
                    }},
                },
                lambda _ctx, value: executed.append(("child", value)) or {
                    "success": True,
                },
            ),
        ],
    ))
    try:
        result = app.prompt("create a parent and child")
        assert result.status.value == "succeeded"
        assert executed == [
            ("parent", {"name": "parent"}),
            ("child", {"name": "child", "parent_id": "resource-42"}),
        ]
    finally:
        app.close()


def test_unresolved_dependency_binding_fails_closed_before_child_execution():
    child_calls = []

    class Model:
        def __init__(self):
            self.turn = 0

        def complete(self, _messages, _tools, _request):
            self.turn += 1
            if self.turn == 1:
                return ModelTurn(tool_calls=(
                    ToolCall("parent", "create_parent", {}),
                    ToolCall(
                        "child", "create_child", {},
                        depends_on=("parent",),
                        argument_bindings=(ToolArgumentBinding(
                            target_field="parent_id",
                            source_call_id="parent",
                            source_path="data.id",
                        ),),
                    ),
                ))
            return "done"

    app = AgentApplication.create(model=Model(), tool_execution="sequential")
    app.register_tool_source(StaticToolSource(
        "resources",
        [
            ToolBinding({"name": "create_parent"}, lambda _ctx, _value: {
                "success": True, "data": {},
            }),
            ToolBinding(
                {
                    "name": "create_child",
                    "input_schema": {"properties": {"parent_id": {}}},
                },
                lambda _ctx, value: child_calls.append(value),
            ),
        ],
    ))
    try:
        result = app.prompt("create a parent and child")
        tool_results = result.data["tool_results"]
        assert child_calls == []
        assert tool_results[1]["is_error"] is True
        assert tool_results[1]["runtime_signals"][
            "tool_argument_binding_error"
        ] is True
    finally:
        app.close()


def test_terminal_dependency_policy_gate_propagates_to_dependent_calls():
    child_calls = []

    class Model:
        def complete(self, _messages, _tools, _request):
            return ModelTurn(tool_calls=(
                ToolCall("parent", "create_parent", {}),
                ToolCall(
                    "child", "create_child", {}, depends_on=("parent",),
                ),
            ))

    def before_tool_call(context):
        if context.tool_call.name == "create_parent":
            return {
                "block": True,
                "terminate": True,
                "needs_confirmation": True,
                "confirmation_payload": {"type": "confirm_write"},
            }
        return None

    app = AgentApplication.create(
        model=Model(),
        tool_execution="sequential",
        before_tool_call=before_tool_call,
    )
    app.register_tool_source(StaticToolSource(
        "resources",
        [
            ToolBinding({"name": "create_parent"}, lambda _ctx, _value: {
                "success": True,
            }),
            ToolBinding(
                {"name": "create_child"},
                lambda _ctx, value: child_calls.append(value),
            ),
        ],
    ))
    try:
        result = app.prompt("create a parent and child")
        results = result.data["tool_results"]
        assert result.status.value == "awaiting_input"
        assert child_calls == []
        assert results[0]["needs_confirmation"] is True
        assert results[1]["terminate"] is True
    finally:
        app.close()


def test_read_tool_timeout_is_retried_but_write_timeout_is_unknown():
    attempts = {"read": 0, "write": 0}

    def slow_read(_ctx, _value):
        attempts["read"] += 1
        if attempts["read"] == 1:
            time.sleep(0.05)
        return {"read": True}

    def slow_write(_ctx, _value):
        attempts["write"] += 1
        time.sleep(0.05)
        return {"write": True}

    class ReadModel:
        def __init__(self):
            self.turn = 0

        def complete(self, _messages, _tools, _request):
            self.turn += 1
            if self.turn == 1:
                return ModelTurn(tool_calls=(ToolCall("read", "read", {}),))
            return "done"

    app = AgentApplication.create(
        model=ReadModel(),
        tool_timeout_seconds=0.01,
        tool_max_retries=1,
        tool_retry_delay_seconds=0,
        max_turns=3,
    )
    app.register_tool_source(StaticToolSource(
        "read",
        [ToolBinding({"name": "read", "effect_class": "read"}, slow_read)],
    ))
    try:
        result = app.prompt("read")
        assert result.status.value == "succeeded"
        assert attempts["read"] == 2
        tool_result = result.data["tool_results"][0]
        assert tool_result["retry_count"] == 1
    finally:
        app.close()

    class WriteModel:
        def complete(self, _messages, _tools, _request):
            return ModelTurn(tool_calls=(ToolCall("write", "write", {}),))

    app = AgentApplication.create(
        model=WriteModel(),
        tool_timeout_seconds=0.01,
        tool_max_retries=3,
        max_turns=1,
    )
    app.register_tool_source(StaticToolSource(
        "write",
        [ToolBinding({"name": "write", "effect_class": "write"}, slow_write)],
    ))
    try:
        result = app.prompt("write")
        tool_result = result.data["tool_results"][0]
        assert attempts["write"] == 1
        assert tool_result["recovery_required"] is True
        assert tool_result["effect_state"] == "unknown"
    finally:
        app.close()


def test_tool_circuit_breaker_blocks_after_repeated_failures():
    calls = []

    class Model:
        def __init__(self):
            self.turn = 0

        def complete(self, _messages, _tools, _request):
            self.turn += 1
            return ModelTurn(tool_calls=(
                ToolCall("call-1", "broken", {}),
                ToolCall("call-2", "broken", {}),
            ))

    def broken(_ctx, _value):
        calls.append(True)
        raise TimeoutError("temporary")

    app = AgentApplication.create(
        model=Model(),
        tool_max_retries=0,
        tool_circuit_failure_threshold=1,
        tool_circuit_reset_seconds=60,
        max_turns=3,
    )
    app.register_tool_source(StaticToolSource(
        "broken",
        [ToolBinding({"name": "broken", "effect_class": "read"}, broken)],
    ))
    try:
        result = app.prompt("run")
        assert len(calls) == 1
        assert any(
            item.get("runtime_signals", {}).get("tool_circuit_open") is True
            for item in result.data["tool_results"]
        )
    finally:
        app.close()


def test_bounded_context_provider_combines_advisory_knowledge_and_memory():
    class Knowledge:
        def search(self, query, *, tenant_id, user_id, limit):
            assert tenant_id == "tenant-a"
            assert user_id == "user-a"
            assert limit == 4
            return [{"title": "Guide", "excerpt": f"for {query}", "source": "wiki"}]

    class Memory:
        def recall(self, query, *, tenant_id, user_id, session_id, limit):
            assert tenant_id == "tenant-a"
            assert user_id == "user-a"
            assert session_id == "session-a"
            assert limit == 4
            return [{"content": f"preference for {query}", "kind": "semantic"}]

    provider = BoundedContextProvider(
        knowledge=Knowledge(),
        memory=Memory(),
        max_items=4,
        max_chars=400,
    )
    value = provider.build_context(
        TurnRequest(
            user_input="campaign",
            tenant_id="tenant-a",
            user_id="user-a",
            session_id="session-a",
        ),
        (),
    )
    assert "Guide" in value["prompt"]
    assert "preference for campaign" in value["prompt"]
    assert value["advisory"] is True
    assert {item["kind"] for item in value["sources"]} == {"knowledge", "memory"}


def test_generic_mcp_source_exposes_remote_tools_as_normal_bindings():
    class Client:
        def list_tools(self):
            return [{
                "name": "lookup",
                "description": "Look up a record",
                "inputSchema": {"type": "object", "properties": {"id": {"type": "string"}}},
                "annotations": {"readOnlyHint": True},
            }]

        def call_tool(self, name, arguments):
            assert name == "lookup"
            return {"structuredContent": {"id": arguments["id"]}}

    source = MCPToolSource("mcp:test", Client(), tenant_id="tenant-a")
    bindings = source.list_bindings()
    assert len(bindings) == 1
    result = MCPToolExecutor(
        Client(), "lookup", tenant_id="tenant-a", write_effect=False,
    ).execute(
        type("Context", (), {"request": TurnRequest(user_input="", tenant_id="tenant-a")})(),
        {"id": "r-1"},
    )
    assert result["structured_content"] == {"id": "r-1"}


def test_generic_mcp_source_does_not_trust_remote_read_only_hint():
    class Client:
        def list_tools(self):
            return [{
                "name": "publish",
                "inputSchema": {"type": "object", "properties": {}},
                "annotations": {"readOnlyHint": True},
            }]

        def call_tool(self, _name, _arguments):
            pytest.fail("remote readOnlyHint must not authorize a call")

    binding = MCPToolSource("mcp:untrusted", Client()).list_bindings()[0]

    assert binding.definition["effect_class"] == "external_write"
    assert binding.definition["replay_policy"] == "unsafe"
    assert binding.definition["live_support"] is False


def test_generic_mcp_write_is_not_called_in_default_dry_run():
    calls = []

    class Client:
        def call_tool(self, name, arguments):
            calls.append((name, arguments))
            return {"structuredContent": {"published": True}}

    request = TurnRequest(
        user_input="publish",
        tenant_id="tenant-a",
        execution_mode="dry_run",
    )
    result = MCPToolExecutor(
        Client(),
        "publish",
        tenant_id="tenant-a",
        write_effect=True,
        live_write_allowed=True,
    ).execute(
        type("Context", (), {"request": request})(),
        {"record_id": "r-1"},
    )

    assert calls == []
    assert result["success"] is True
    assert result["executed"] is False
    assert result["execution_status"] == "dry_run_only"
    assert result["effect_state"] == "not_started"


def test_generic_mcp_reads_require_host_trust_and_keep_tenant_scope():
    calls = []

    class Client:
        def list_tools(self):
            return [{
                "name": "lookup",
                "inputSchema": {"type": "object", "properties": {}},
                "annotations": {"readOnlyHint": False},
            }]

        def call_tool(self, name, arguments):
            calls.append((name, arguments))
            return {"structuredContent": {"ok": True}}

    source = MCPToolSource(
        "mcp:trusted",
        Client(),
        tenant_id="tenant-a",
        trusted_read_tools={"lookup"},
    )
    binding = source.list_bindings()[0]
    assert binding.definition["effect_class"] == "read"

    denied = binding.executor.execute(
        type(
            "Context",
            (),
            {"request": TurnRequest(user_input="", tenant_id="tenant-b")},
        )(),
        {},
    )
    assert denied["success"] is False
    assert calls == []

    allowed = binding.executor.execute(
        type(
            "Context",
            (),
            {"request": TurnRequest(user_input="", tenant_id="tenant-a")},
        )(),
        {},
    )
    assert allowed["success"] is True
    assert calls == [("lookup", {})]


def test_generic_mcp_live_write_requires_explicit_host_allowlist():
    calls = []

    class Client:
        def call_tool(self, name, arguments):
            calls.append((name, arguments))
            return {"structuredContent": {"ok": True}}

    context = type(
        "Context",
        (),
        {
            "request": TurnRequest(
                user_input="publish",
                tenant_id="tenant-a",
                execution_mode="live",
            ),
        },
    )()
    denied = MCPToolExecutor(
        Client(),
        "publish",
        tenant_id="tenant-a",
        write_effect=True,
    ).execute(context, {})
    assert denied["success"] is False
    assert denied["execution_status"] == "blocked_untrusted_write"
    assert calls == []

    allowed = MCPToolExecutor(
        Client(),
        "publish",
        tenant_id="tenant-a",
        write_effect=True,
        live_write_allowed=True,
        idempotency_key_field="request_id",
    ).execute(context, {"request_id": "publish-1"})
    assert allowed["success"] is True
    assert calls == [("publish", {"request_id": "publish-1"})]


def test_generic_mcp_live_write_requires_a_host_declared_schema_key():
    class Client:
        def list_tools(self):
            return [{
                "name": "publish",
                "inputSchema": {
                    "type": "object",
                    "required": ["request_id"],
                    "properties": {"request_id": {"type": "string"}},
                },
            }]

        def call_tool(self, _name, _arguments):
            pytest.fail("this test must not call the remote tool")

    with pytest.raises(ValueError, match="idempotency field"):
        MCPToolSource(
            "mcp:missing-key",
            Client(),
            live_write_tools={"publish"},
        )

    with pytest.raises(ValueError, match="host-declared string idempotency field"):
        MCPToolSource(
            "mcp:optional-key",
            type(
                "OptionalKeyClient",
                (),
                {
                    "list_tools": lambda self: [{
                        "name": "publish",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"request_id": {"type": "string"}},
                        },
                    }],
                },
            )(),
            live_write_tools={"publish"},
            idempotency_key_fields={"publish": "request_id"},
        ).list_bindings()

    source = MCPToolSource(
        "mcp:declared-key",
        Client(),
        live_write_tools={"publish"},
        idempotency_key_fields={"publish": "request_id"},
    )
    binding = source.list_bindings()[0]
    assert binding.definition["idempotency_key_field"] == "request_id"


def test_agent_persists_turn_checkpoints_and_clears_successful_run():
    class Checkpoints:
        def __init__(self):
            self.saved = []
            self.cleared = []

        def save_checkpoint(self, run_id, checkpoint):
            self.saved.append((run_id, dict(checkpoint)))

        def clear_checkpoint(self, run_id):
            self.cleared.append(run_id)

    checkpoints = Checkpoints()

    class Model:
        def __init__(self):
            self.turn = 0

        def complete(self, _messages, _tools, _request):
            self.turn += 1
            return ModelTurn(
                content="done" if self.turn == 2 else "",
                tool_calls=(
                    (ToolCall("call-1", "lookup", {}),)
                    if self.turn == 1 else ()
                ),
            )

    app = AgentApplication.create(
        model=Model(),
        checkpoint_store=checkpoints,
        max_turns=3,
    )
    app.register_tool_source(StaticToolSource(
        "lookup",
        [ToolBinding({"name": "lookup"}, lambda _ctx, _value: {"ok": True})],
    ))
    try:
        result = app.prompt("run")
        assert result.status.value == "succeeded"
        assert checkpoints.saved
        assert checkpoints.cleared == [result.run_id]
        assert checkpoints.saved[-1][1]["turn_index"] == 1
    finally:
        app.close()


def test_agent_can_explicitly_resume_a_durable_checkpoint():
    class Checkpoints:
        def __init__(self):
            self.values = {}
            self.cleared = []

        def save_checkpoint(self, run_id, checkpoint):
            self.values[str(run_id)] = dict(checkpoint)

        def load_checkpoint(self, run_id):
            return self.values.get(str(run_id))

        def clear_checkpoint(self, run_id):
            self.cleared.append(str(run_id))
            self.values.pop(str(run_id), None)

    checkpoints = Checkpoints()
    first = AgentApplication.create(
        model=lambda *_args: "paused",
        checkpoint_store=checkpoints,
    )
    try:
        first.agent._save_checkpoint(
            TurnRequest(user_input="resume me", run_id="old-run", turn_id="old-turn"),
            first.agent._state_for(None),
            turn_index=0,
            tool_results=(),
        )
    finally:
        first.close()

    seen = []

    def model(messages, _tools, _request):
        seen.append([item.content for item in messages])
        return "resumed"

    second = AgentApplication.create(
        model=model,
        checkpoint_store=checkpoints,
    )
    try:
        result = second.prompt(
            "continue",
            context={
                "resume_from_checkpoint": True,
                "resume_run_id": "old-run",
            },
        )
        assert result.reply == "resumed"
        assert "continue" in seen[-1]
        assert "old-run" in checkpoints.cleared
    finally:
        second.close()


def test_tool_execution_coordinator_preserves_dependency_and_event_order():
    calls = []
    events = []

    class Model:
        def complete(self, _messages, _tools, _request):
            return "unused"

    app = AgentApplication.create(model=Model(), max_turns=1)
    app.register_tool_source(StaticToolSource(
        "tools",
        [
            ToolBinding(
                {"name": "first", "effect_class": "read"},
                lambda _ctx, _args: calls.append("first") or {"success": True},
            ),
            ToolBinding(
                {"name": "second", "effect_class": "read"},
                lambda _ctx, _args: calls.append("second") or {"success": True},
            ),
        ],
    ))
    coordinator = ToolExecutionCoordinator(
        tool_catalog=app.tools,
        emit=lambda event, _request, **payload: events.append((event, payload)),
        interrupt_reason=lambda _request: None,
        assert_not_interrupted=lambda _request: None,
        tool_execution="sequential",
        max_parallel_tools=1,
        max_tool_result_chars=200,
    )
    try:
        request = TurnRequest(user_input="run")
        assistant = type("Assistant", (), {})()
        state = type("State", (), {})()
        results = coordinator.execute_tools(
            request,
            assistant,
            (
                ToolCall("first-id", "first", {}),
                ToolCall("second-id", "second", {}, depends_on=("first-id",)),
            ),
            state,
        )
        assert calls == ["first", "second"]
        assert [item["name"] for item in results] == ["first", "second"]
        assert [event[0] for event in events] == [
            "tool_execution_start", "tool_execution_end",
            "tool_execution_start", "tool_execution_end",
        ]
    finally:
        app.close()
