import time

from agents.agent_harness import (
    AgentApplication,
    BoundedContextProvider,
    MCPToolExecutor,
    MCPToolSource,
    ModelTurn,
    StaticToolSource,
    ToolBinding,
    ToolCall,
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
