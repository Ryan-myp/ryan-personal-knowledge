import threading

from contextvars import ContextVar

from agents.agent_harness import (
    Agent,
    AgentApplication,
    AgentMessage,
    AgentRuntime,
    InMemoryToolCatalog,
    ModelTurn,
    StaticToolSource,
    ToolBinding,
    ToolCall,
    TurnRequest,
    RuntimePorts,
)


def test_cancelled_non_interruptible_write_requires_recovery():
    cancellation = threading.Event()

    class Model:
        def complete(self, _messages, _tools, _request):
            return ModelTurn(
                tool_calls=(ToolCall("call-1", "publish", {}),),
            )

    def publish(context, _data):
        context.request.cancellation_event.set()
        return {"ok": True}

    app = AgentApplication.create(model=Model(), max_turns=1)
    app.register_tool_source(StaticToolSource(
        "writes",
        [ToolBinding({
            "name": "publish",
            "effect_class": "write",
            "cancellation_mode": "cooperative",
        }, publish)],
    ))
    try:
        result = app.prompt("publish", cancellation_event=cancellation)
        assert result.status.value == "recovery_required"
        assert result.recovery_required is True
        assert result.runtime_signals["effect_state"] == "unknown"
    finally:
        app.close()
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


class LifecycleAwareModel:
    def __init__(self):
        self.cleaned = []

    def complete(self, _messages, _tools, _request):
        return ModelTurn(content="finished")

    def on_run_end(self, request, _model_turn, _tool_results, _state):
        return {"intent": "demo", "run_id": request.run_id}

    def on_run_cleanup(self, request, _state):
        self.cleaned.append(request.run_id)


class LifecycleAwareContext:
    def __init__(self):
        self.cleaned = []

    def build_context(self, request, _messages):
        return {"prompt": "context"}

    def cleanup(self, request, _state):
        self.cleaned.append(request.run_id)


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
            "model_start",
            "model_end",
            "message_end",
            "tool_execution_start",
        "tool_execution_end",
        "message_end",
        "turn_end",
        "turn_start",
        "model_start",
        "model_end",
        "message_end",
        "turn_end",
        "agent_end",
    ]


def test_initial_tool_choice_applies_only_to_first_model_turn():
    class InitialToolChoiceModel:
        def __init__(self):
            self.choices = []

        def complete(self, _messages, _tools, request):
            self.choices.append(getattr(request, "initial_tool_choice", None))
            if len(self.choices) == 1:
                return ModelTurn(
                    tool_calls=(
                        ToolCall("call-1", "echo", {"text": "hi"}),
                    ),
                )
            return ModelTurn(content="finished")

    model = InitialToolChoiceModel()
    catalog = InMemoryToolCatalog()
    catalog.register_source(
        StaticToolSource("local", [ToolBinding({"name": "echo"}, EchoTool())])
    )
    agent = Agent(model=model, tool_catalog=catalog, max_turns=3)

    result = agent.run(TurnRequest(
        user_input="say hi",
        initial_tool_choice="required",
    ))

    assert result.status.value == "succeeded"
    assert model.choices == ["required", None]


def test_agent_marks_a_missing_required_tool_call_as_failed():
    class MissingToolCallModel:
        def complete(self, _messages, _tools, _request):
            return ModelTurn(
                content="The required tool call did not succeed.",
                stop_reason="required_tool_failed",
            )

    catalog = InMemoryToolCatalog()
    catalog.register_source(StaticToolSource(
        "lookup",
        [ToolBinding({"name": "lookup_record"}, EchoTool())],
    ))
    agent = Agent(model=MissingToolCallModel(), tool_catalog=catalog)

    result = agent.run(TurnRequest(
        user_input="Look up record r-17.",
        initial_tool_choice="required",
    ))

    assert result.status.value == "failed"
    assert result.reply == "The required tool call did not succeed."
    assert result.runtime_signals["required_tool_call_failed"] is True


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

    assert result.status.value == "failed"
    assert result.data["tool_results"][0]["is_error"] is True
    assert model.calls == 1
    assert events[-1]["type"] == "agent_end"


def test_agent_exposes_application_data_and_cleans_run_scoped_adapters():
    model = LifecycleAwareModel()
    context = LifecycleAwareContext()
    agent = Agent(model=model, context_provider=context)

    result = agent.run(TurnRequest(user_input="hello"))

    assert result.application_data["intent"] == "demo"
    assert "application_data" not in result.to_dict()
    assert model.cleaned == [result.run_id]
    assert context.cleaned == [result.run_id]


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


def test_generic_runtime_cancels_only_the_active_matching_session():
    results = {}
    agent = Agent(model=lambda _messages, _tools, _request: "done")
    runtime = AgentRuntime(
        agent=agent,
        ports=RuntimePorts(
            session_manager=None,
            session_locks={},
            session_locks_guard=threading.RLock(),
            lease_owner="test",
            lease_seconds=30,
            mode_context=ContextVar("agent_loop_cancel_wrong_identity", default=None),
            validate_mode=lambda value: value or "dry_run",
            resolve_mode=lambda _tenant, _user, _requested: "dry_run",
            assert_ready=lambda: None,
            ensure_session=lambda _request: None,
        ),
    )
    cancel_results = []

    def request_wrong_identity(payload):
        if payload["type"] == "agent_start":
            cancel_results.append(runtime.cancel_run(
                "session-a", user_id="other-user", tenant_id="tenant-a",
            ))

    agent.event_callback = request_wrong_identity
    try:
        results["wrong_identity"] = runtime.run(TurnRequest(
            user_input="hello",
            session_id="session-a",
            user_id="user-a",
            tenant_id="tenant-a",
        ))
        results["inactive"] = runtime.cancel_run(
            "session-a", user_id="user-a", tenant_id="tenant-a",
        )
    finally:
        runtime.close()

    assert cancel_results == [False]
    assert results["wrong_identity"].status.value == "succeeded"
    assert results["inactive"] is False


def test_generic_runtime_cooperatively_cancels_the_active_run():
    agent = Agent(model=lambda _messages, _tools, _request: "done")
    runtime = AgentRuntime(
        agent=agent,
        ports=RuntimePorts(
            session_manager=None,
            session_locks={},
            session_locks_guard=threading.RLock(),
            lease_owner="test",
            lease_seconds=30,
            mode_context=ContextVar("agent_loop_cancel_active", default=None),
            validate_mode=lambda value: value or "dry_run",
            resolve_mode=lambda _tenant, _user, _requested: "dry_run",
            assert_ready=lambda: None,
            ensure_session=lambda _request: None,
        ),
    )
    cancel_results = []

    def request_cancel(payload):
        if payload["type"] == "agent_start":
            cancel_results.append(runtime.cancel_run(
                "session-a", user_id="user-a", tenant_id="tenant-a",
            ))

    agent.event_callback = request_cancel
    try:
        result = runtime.run(TurnRequest(
            user_input="hello",
            session_id="session-a",
            user_id="user-a",
            tenant_id="tenant-a",
        ))
    finally:
        runtime.close()

    assert cancel_results == [True]
    assert result.status.value == "cancelled"


def test_generic_runtime_stops_waiting_for_a_cancelled_model_call():
    model_started = threading.Event()
    release_model = threading.Event()
    results = []
    agent = Agent(model=lambda *_args: "done")
    agent.model = type("BlockingModel", (), {
        "complete": lambda _self, *_args: (
            model_started.set(),
            release_model.wait(3),
            "done",
        )[-1],
    })()
    runtime = AgentRuntime(
        agent=agent,
        ports=RuntimePorts(
            session_manager=None,
            session_locks={},
            session_locks_guard=threading.RLock(),
            lease_owner="test",
            lease_seconds=30,
            mode_context=ContextVar("agent_loop_cancel_blocked_model", default=None),
            validate_mode=lambda value: value or "dry_run",
            resolve_mode=lambda _tenant, _user, _requested: "dry_run",
            assert_ready=lambda: None,
            ensure_session=lambda _request: None,
        ),
    )
    worker = threading.Thread(target=lambda: results.append(runtime.run(
        TurnRequest(
            user_input="hello",
            session_id="session-a",
            user_id="user-a",
            tenant_id="tenant-a",
        )
    )))

    try:
        worker.start()
        assert model_started.wait(1)
        assert runtime.cancel_run(
            "session-a", user_id="user-a", tenant_id="tenant-a",
        ) is True
        worker.join(timeout=1)
        assert not worker.is_alive()
        assert results[0].status.value == "cancelled"
    finally:
        release_model.set()
        worker.join(timeout=3)
        runtime.close()


def test_cancelling_an_inflight_write_returns_recovery_and_keeps_signal_set():
    tool_started = threading.Event()
    release_tool = threading.Event()
    tool_finished = threading.Event()
    observed_cancel = []
    results = []

    class Model:
        def complete(self, _messages, _tools, _request):
            return ModelTurn(
                tool_calls=(ToolCall("write-1", "publish", {}),),
            )

    class BlockingWrite:
        def execute(self, context, _arguments):
            tool_started.set()
            release_tool.wait(3)
            observed_cancel.append(context.request.cancellation_event.is_set())
            tool_finished.set()
            return {"success": True}

    app = AgentApplication.create(model=Model(), max_turns=1)
    app.register_tool_source(StaticToolSource(
        "writes",
        [ToolBinding({
            "name": "publish",
            "effect_class": "write",
            "cancellation_mode": "interruptible",
        }, BlockingWrite())],
    ))
    runtime = app.runtime
    worker = threading.Thread(target=lambda: results.append(runtime.run(
        TurnRequest(
            user_input="publish",
            session_id="session-a",
            user_id="user-a",
            tenant_id="tenant-a",
        )
    )))

    try:
        worker.start()
        assert tool_started.wait(1)
        assert runtime.cancel_run(
            "session-a", user_id="user-a", tenant_id="tenant-a",
        ) is True
        worker.join(timeout=1)
        assert not worker.is_alive()
        assert results[0].status.value == "recovery_required"
        assert results[0].recovery_required is True
    finally:
        release_tool.set()
        worker.join(timeout=3)
        assert tool_finished.wait(1)
        app.close()

    assert observed_cancel == [True]


def test_agent_prompt_and_subscribe_are_reusable_interactive_apis():
    events = []
    agent = Agent(model=lambda _messages, _tools, _request: "done")
    unsubscribe = agent.subscribe(events.append)

    result = agent.prompt("hello")
    unsubscribe()

    assert result.reply == "done"
    assert any(event["type"] == "agent_end" for event in events)
