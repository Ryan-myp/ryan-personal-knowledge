import threading

from agents.agent_harness import (
    Agent,
    AgentMessage,
    AgentRuntime,
    InMemoryToolCatalog,
    ModelTurn,
    StaticToolSource,
    ToolBinding,
    ToolCall,
    TurnRequest,
)
from agents.agent_harness import RuntimePorts
from contextvars import ContextVar


class EchoTool:
    name = "echo"

    def execute(self, _context, input_data):
        return {"echo": input_data["text"]}


class ScriptedModel:
    def __init__(self):
        self.calls = 0

    def complete(self, messages, tools, _request):
        self.calls += 1
        if self.calls == 1:
            assert messages[-1].role == "user"
            assert [item["name"] for item in tools] == ["echo"]
            return ModelTurn(
                content="",
                tool_calls=[ToolCall(id="call-1", name="echo", arguments={"text": "hi"})],
            )
        assert messages[-1].role == "tool"
        return ModelTurn(content="finished")


def test_agent_loop_owns_transcript_tool_turns_and_events():
    events = []
    model = ScriptedModel()
    catalog = InMemoryToolCatalog()
    catalog.register_source(
        StaticToolSource("local", [ToolBinding({"name": "echo"}, EchoTool())])
    )
    agent = Agent(
        model=model,
        tool_catalog=catalog,
        max_turns=4,
        event_callback=events.append,
    )

    result = agent.run(TurnRequest(user_input="say hi"))

    assert result.status.value == "succeeded"
    assert result.reply == "finished"
    assert [message.role for message in agent.state.messages] == [
        "user", "assistant", "tool", "assistant",
    ]
    assert [event["type"] for event in events] == [
            "agent_start",
            "turn_start",
            "message_end",
            "message_end",
            "tool_execution_start",
        "tool_execution_end",
        "message_end",
        "turn_end",
        "turn_start",
        "message_end",
        "turn_end",
        "agent_end",
    ]


def test_agent_loop_can_block_tool_and_cancel_before_next_model_turn():
    events = []
    model = ScriptedModel()
    catalog = InMemoryToolCatalog()
    catalog.register_source(
        StaticToolSource("local", [ToolBinding({"name": "echo"}, EchoTool())])
    )
    cancelled = threading.Event()
    agent = Agent(
        model=model,
        tool_catalog=catalog,
        event_callback=events.append,
        before_tool_call=lambda _context: {
            "block": True,
            "reason": "blocked",
            "terminate": True,
        },
    )

    result = agent.run(
        TurnRequest(user_input="say hi", cancellation_event=cancelled)
    )

    assert result.status.value == "succeeded"
    assert result.data["tool_results"][0]["is_error"] is True
    assert model.calls == 1
    assert events[-1]["type"] == "agent_end"


def test_agent_message_is_json_safe_and_runtime_request_ids_are_preserved():
    message = AgentMessage.user("hello", run_id="run-1", turn_id="turn-1")
    assert message.to_dict()["role"] == "user"
    assert message.to_dict()["run_id"] == "run-1"


def test_agent_can_be_embedded_directly_in_the_generic_runtime():
    agent = Agent(model=lambda messages, _tools, _request: "done")
    runtime = AgentRuntime(
        agent=agent,
        ports=RuntimePorts(
            session_manager=None,
            session_locks={},
            session_locks_guard=threading.RLock(),
            lease_owner="test",
            lease_seconds=30,
            mode_context=ContextVar("agent_loop_runtime_mode", default=None),
            validate_mode=lambda value: value or "dry_run",
            resolve_mode=lambda _tenant, _user, _requested: "dry_run",
            assert_ready=lambda: None,
            ensure_session=lambda _request: None,
        ),
    )

    result = runtime.run(TurnRequest(user_input="hello"))

    assert result.reply == "done"
    assert result.run_id


def test_agent_prompt_and_subscribe_are_reusable_interactive_apis():
    events = []
    agent = Agent(model=lambda _messages, _tools, _request: "done")
    unsubscribe = agent.subscribe(events.append)

    result = agent.prompt("hello")
    unsubscribe()

    assert result.reply == "done"
    assert any(event["type"] == "agent_end" for event in events)
