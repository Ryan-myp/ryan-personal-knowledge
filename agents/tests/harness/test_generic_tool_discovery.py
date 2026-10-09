from __future__ import annotations

from types import SimpleNamespace

from agents.agent_harness import (
    AgentApplication,
    StaticToolSource,
    ToolBinding,
    TurnRequest,
)
from agents.agent_harness.core.interfaces import ToolDefinition, ToolSchema
from agents.agent_harness.core.llm_client import LLMClient
from agents.agent_harness.core.tool_selection import ToolSelector
from agents.agent_harness.messages import ModelTurn, ToolCall


def _definition(
    name: str,
    *,
    namespace: str,
    action: str,
    resource: str,
    description: str,
    intent_types: tuple[str, ...] = (),
    properties: dict | None = None,
) -> ToolDefinition:
    return ToolDefinition(
        name=name,
        skill=namespace,
        namespace=namespace,
        description=description,
        input_schema=ToolSchema(properties=properties or {}),
        action=action,
        resource_type=resource,
        intent_types=list(intent_types),
    )


def test_relevant_tool_selection_uses_publisher_metadata_and_is_bounded():
    tools = [
        _definition(
            "find_campaigns",
            namespace="google-ads",
            action="list",
            resource="campaign",
            description="列出广告系列及其投放状态",
            intent_types=("list_campaigns",),
        ),
        _definition(
            "update_campaign_budget",
            namespace="google-ads",
            action="update",
            resource="campaign",
            description="Update a campaign daily budget",
            properties={"campaign_id": {"type": "string"}},
        ),
        *[
            _definition(
                f"read_invoice_{index}",
                namespace="billing",
                action="get",
                resource="invoice",
                description="Read one invoice by identifier",
            )
            for index in range(20)
        ],
    ]

    selected = ToolSelector().select_relevant(
        "列出 Google Ads campaigns", tools, limit=2,
    )

    assert [item.name for item in selected] == ["find_campaigns", "update_campaign_budget"]


def test_relevant_tool_selection_returns_empty_for_unmatched_request():
    tools = [
        _definition(
            "read_invoice",
            namespace="billing",
            action="get",
            resource="invoice",
            description="Read one invoice by identifier",
        ),
    ]

    assert ToolSelector().select_relevant("Tell me a joke", tools) == []


def test_relevant_tool_selection_rejects_non_positive_limit():
    selector = ToolSelector()

    try:
        selector.select_relevant("read record", [], limit=0)
    except ValueError as error:
        assert "limit" in str(error)
    else:
        raise AssertionError("non-positive limit should be rejected")


class _Completions:
    def __init__(self, tool_name="lookup_record"):
        self.requests = []
        self.responses = [
            SimpleNamespace(
                choices=[SimpleNamespace(
                    message=SimpleNamespace(
                        content="",
                        tool_calls=[SimpleNamespace(
                            id="call-1",
                            function=SimpleNamespace(
                                name=tool_name,
                                arguments='{"record_id":"r-17"}',
                            ),
                        )],
                    ),
                    finish_reason="tool_calls",
                )],
                usage=None,
            ),
            SimpleNamespace(
                choices=[SimpleNamespace(
                    message=SimpleNamespace(content="Record r-17 is ready.", tool_calls=[]),
                    finish_reason="stop",
                )],
                usage=None,
            ),
        ]

    def create(self, **kwargs):
        self.requests.append(kwargs)
        return self.responses.pop(0)


def test_generic_model_tool_call_runs_through_harness_and_returns_result_to_model():
    completions = _Completions()
    client = LLMClient(model="test-model", api_key="test-only")
    client._client = SimpleNamespace(
        chat=SimpleNamespace(completions=completions),
    )
    definition = _definition(
        "lookup_record",
        namespace="records",
        action="get",
        resource="record",
        description="Look up one record by identifier",
        properties={"record_id": {"type": "string"}},
    )
    executed = []
    preflight = []

    def execute(_context, values):
        executed.append(dict(values))
        return {"success": True, "data": {"record_id": values["record_id"]}}

    def before_tool_call(context):
        preflight.append(context.tool_call.name)

    app = AgentApplication.create(
        model=client,
        tool_selector=lambda request, tools: ToolSelector().select_relevant(
            request.user_input, tools, limit=4,
        ),
        before_tool_call=before_tool_call,
        tool_execution="sequential",
    )
    app.register_tool_source(StaticToolSource(
        "records",
        [ToolBinding(definition, execute)],
    ))
    try:
        result = app.runtime.run(TurnRequest(
            user_input="Look up record r-17",
            session_id="session-1",
            user_id="user-1",
            tenant_id="tenant-1",
        ))

        assert result.status.value == "succeeded", result.to_dict()
        assert result.reply == "Record r-17 is ready."
        assert executed == [{"record_id": "r-17"}]
        assert preflight == ["lookup_record"]
        assert len(completions.requests) == 2
        assert completions.requests[1]["messages"][-1]["role"] == "tool"
        assert completions.requests[1]["messages"][-1]["content"].find("r-17") >= 0
        assert result.run_id
        assert result.turn_id
    finally:
        app.close()


def test_request_validator_rejects_before_model_and_keeps_run_identity():
    calls = []

    def model(_messages, _tools, _request):
        calls.append("called")
        return "must not run"

    app = AgentApplication.create(
        model=model,
        request_validator=lambda _request: "request is outside policy",
    )
    try:
        result = app.runtime.run(TurnRequest(
            user_input="do work",
            session_id="session-1",
            user_id="user-1",
            tenant_id="tenant-1",
        ))

        assert result.status.value == "failed"
        assert result.reply == "request is outside policy"
        assert result.run_id
        assert result.turn_id
        assert result.data["request_validation_error"] == "request is outside policy"
        assert calls == []
    finally:
        app.close()


def test_run_tool_call_budget_rejects_oversized_batch_atomically():
    calls = []

    class Model:
        def __init__(self):
            self.invocations = 0

        def complete(self, _messages, _tools, _request):
            self.invocations += 1
            return ModelTurn(tool_calls=(
                ToolCall("call-1", "read_first", {}),
                ToolCall("call-2", "read_second", {}),
            ))

    model = Model()
    app = AgentApplication.create(
        model=model,
        max_tool_calls_per_run=1,
        tool_execution="sequential",
    )
    definition = _definition(
        "read_first", namespace="records", action="get", resource="record",
        description="Read the first record",
    )
    second = _definition(
        "read_second", namespace="records", action="get", resource="record",
        description="Read the second record",
    )

    def execute(_context, _input):
        calls.append(True)
        return {"success": True}

    app.register_tool_source(StaticToolSource("records", [
        ToolBinding(definition, execute),
        ToolBinding(second, execute),
    ]))
    try:
        result = app.runtime.run(TurnRequest(user_input="read records"))

        assert result.status.value == "failed"
        assert result.runtime_signals["tool_call_budget_exceeded"] is True
        assert result.data["tool_call_count"] == 0
        assert len(result.data["tool_results"]) == 2
        assert all(item["is_error"] for item in result.data["tool_results"])
        assert calls == []
        assert model.invocations == 1
    finally:
        app.close()


def test_run_tool_call_budget_applies_across_model_turns():
    calls = []

    class Model:
        def __init__(self):
            self.turns = iter((
                ModelTurn(tool_calls=(ToolCall("call-1", "read_first", {}),)),
                ModelTurn(tool_calls=(ToolCall("call-2", "read_second", {}),)),
            ))
            self.invocations = 0

        def complete(self, _messages, _tools, _request):
            self.invocations += 1
            return next(self.turns)

    model = Model()
    app = AgentApplication.create(
        model=model,
        max_tool_calls_per_run=1,
        tool_execution="sequential",
    )
    bindings = []
    for name in ("read_first", "read_second"):
        definition = _definition(
            name, namespace="records", action="get", resource="record",
            description=f"Read {name.replace('_', ' ')}",
        )

        def execute(_context, _input, tool_name=name):
            calls.append(tool_name)
            return {"success": True}

        bindings.append(ToolBinding(definition, execute))
    app.register_tool_source(StaticToolSource("records", bindings))
    try:
        result = app.runtime.run(TurnRequest(user_input="read records"))

        assert result.status.value == "failed"
        assert result.runtime_signals["tool_call_budget_exceeded"] is True
        assert result.data["tool_call_count"] == 1
        assert calls == ["read_first"]
        assert model.invocations == 2
    finally:
        app.close()


def test_generic_model_tool_call_confirmation_gate_prevents_executor_run():
    completions = _Completions(tool_name="publish_record")
    client = LLMClient(model="test-model", api_key="test-only")
    client._client = SimpleNamespace(
        chat=SimpleNamespace(completions=completions),
    )
    definition = _definition(
        "publish_record",
        namespace="records",
        action="publish",
        resource="record",
        description="Publish a record",
        properties={"record_id": {"type": "string"}},
    )
    executed = []

    def execute(_context, values):
        executed.append(dict(values))
        return {"success": True}

    app = AgentApplication.create(
        model=client,
        before_tool_call=lambda _context: {
            "block": True,
            "needs_confirmation": True,
            "confirmation_payload": {"question": "Confirm publish?"},
        },
        tool_execution="sequential",
    )
    app.register_tool_source(StaticToolSource(
        "records",
        [ToolBinding(definition, execute)],
    ))
    try:
        result = app.runtime.run(TurnRequest(
            user_input="Publish record r-17",
            session_id="session-2",
            execution_mode="live",
        ))

        assert result.status.value == "awaiting_input", result.to_dict()
        assert result.needs_input is True
        assert result.reply == "Confirm publish?"
        assert executed == []
    finally:
        app.close()
