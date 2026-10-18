from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from agents.agent_harness.core.interfaces import ToolDefinition, ToolSchema
from agents.agent_harness.core.llm_client import LLMClient, LLMStructuredOutputError
from agents.agent_harness.messages import AgentMessage, ModelTurn, ToolCall
from agents.agent_harness.runtime_kernel import TurnRequest
from agents.agent_harness.tool_execution import ToolExecutionCoordinator


def _tool(name: str = "lookup_record") -> ToolDefinition:
    return ToolDefinition(
        name=name,
        skill="records",
        namespace="records",
        description="Look up one record by its identifier.",
        input_schema=ToolSchema(
            required=["record_id"],
            properties={
                "record_id": {"type": "string", "description": "Record ID"},
                "page_size": {"type": "integer", "default": 20},
            },
            requires=["registered_only"],
            conditional_rules=[{"if": "private", "then": "deny"}],
        ),
        action="get",
        resource_type="record",
        intent_types=["get_record"],
    )


class _Completions:
    def __init__(self, response):
        self.response = response
        self.requests = []

    def create(self, **kwargs):
        self.requests.append(kwargs)
        return self.response


class _QueuedCompletions:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests = []

    def create(self, **kwargs):
        self.requests.append(kwargs)
        index = min(len(self.requests) - 1, len(self.responses) - 1)
        return self.responses[index]


def _client(message, *, usage=None):
    completions = _Completions(SimpleNamespace(
        choices=[SimpleNamespace(message=message, finish_reason="tool_calls")],
        usage=usage or SimpleNamespace(prompt_tokens=11, completion_tokens=7),
    ))
    api = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    client = LLMClient(model="test-model", api_key="test-only")
    client._client = api
    return client, completions


def test_llm_client_implements_generic_harness_model_tool_call_contract():
    response_message = SimpleNamespace(
        content="先查询记录。",
        tool_calls=[SimpleNamespace(
            id="call-1",
            type="function",
            function=SimpleNamespace(
                name="lookup_record",
                arguments='{"record_id":"r-17","page_size":5}',
            ),
        )],
    )
    client, completions = _client(response_message)
    messages = [
        AgentMessage.system("Use declared tools only."),
        AgentMessage.user("Find record r-17."),
    ]

    result = client.complete(
        messages,
        [_tool()],
        TurnRequest(user_input="Find record r-17.", context={"max_output_tokens": 80}),
    )

    assert isinstance(result, ModelTurn)
    assert result.content == "先查询记录。"
    assert result.tool_calls == (
        ToolCall(
            id="call-1",
            name="lookup_record",
            arguments={"record_id": "r-17", "page_size": 5},
        ),
    )
    request = completions.requests[0]
    assert request["tool_choice"] == "auto"
    assert request["messages"] == [
        {"role": "system", "content": "Use declared tools only."},
        {"role": "user", "content": "Find record r-17."},
    ]
    function = request["tools"][0]["function"]
    assert function["name"] == "lookup_record"
    assert function["parameters"] == {
        "type": "object",
        "properties": {
            "record_id": {"type": "string", "description": "Record ID"},
            "page_size": {"type": "integer", "default": 20},
        },
        "required": ["record_id"],
        "additionalProperties": False,
    }
    assert result.usage["input_tokens"] == 11
    assert result.usage["output_tokens"] == 7


def test_llm_client_honors_required_initial_tool_choice():
    client, completions = _client(SimpleNamespace(content="", tool_calls=[]))

    client.complete(
        [AgentMessage.user("Create from the selected blueprint.")],
        [_tool()],
        TurnRequest(
            user_input="Create from the selected blueprint.",
            initial_tool_choice="required",
        ),
    )

    assert completions.requests[0]["tool_choice"] == "required"


def test_llm_client_honors_an_explicit_named_initial_tool_choice():
    client, completions = _client(SimpleNamespace(content="", tool_calls=[]))
    choice = {"type": "function", "function": {"name": "lookup_record"}}
    client.complete(
        [AgentMessage.user("Resume the confirmed action.")],
        [_tool()],
        TurnRequest(user_input="Resume the confirmed action.", initial_tool_choice=choice),
    )
    assert completions.requests[0]["tool_choice"] == choice


def test_llm_client_round_trips_assistant_tool_call_and_tool_result_messages():
    client, completions = _client(SimpleNamespace(content="Done.", tool_calls=[]))
    messages = [
        AgentMessage.assistant(
            "", metadata={
                "tool_calls": [{
                    "id": "call-1",
                    "name": "lookup_record",
                    "arguments": {"record_id": "r-17"},
                }],
            },
        ),
        AgentMessage.tool(
            json.dumps({"id": "r-17"}),
            tool_call_id="call-1",
            name="lookup_record",
        ),
    ]

    result = client.complete(messages, [_tool()], TurnRequest(user_input="Find it"))

    assert result.content == "Done."
    assert completions.requests[0]["messages"] == [
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [{
                "id": "call-1",
                "type": "function",
                "function": {
                    "name": "lookup_record",
                    "arguments": '{"record_id":"r-17"}',
                },
            }],
        },
        {
            "role": "tool",
            "tool_call_id": "call-1",
            "name": "lookup_record",
            "content": '{"id": "r-17"}',
        },
    ]


def test_model_facing_lookup_result_omits_signed_selection_catalog():
    executor = object.__new__(ToolExecutionCoordinator)
    executor.max_tool_result_chars = 32_000
    result = {
        "success": True,
        "data": {
            "identities": [{"identity_id": "identity-1", "display_name": "Shop"}],
            "parameter_selections": [{
                "tool_name": "create_ad",
                "field": "identity_id",
                "options": [{
                    "value": "identity-1",
                    "label": "Shop",
                    "selection_token": "signed-proof",
                }],
            }],
        },
    }
    definition = SimpleNamespace(
        result_items_key="identities",
        is_write_tool=False,
    )

    model_content = executor._query_content(result, definition)

    assert "parameter_selections" not in model_content["data"]
    assert model_content["data"]["identities"] == result["data"]["identities"]
    assert "signed-proof" not in json.dumps(model_content)
    assert result["data"]["parameter_selections"][0]["options"][0][
        "selection_token"
    ] == "signed-proof"


@pytest.mark.parametrize(
    "arguments",
    ["not-json", "[]", "null", "\"value\""],
)
def test_llm_client_rejects_non_object_tool_arguments(arguments):
    message = SimpleNamespace(
        content=None,
        tool_calls=[SimpleNamespace(
            id="call-1",
            function=SimpleNamespace(name="lookup_record", arguments=arguments),
        )],
    )
    client, _completions = _client(message)

    with pytest.raises(LLMStructuredOutputError):
        client.complete([AgentMessage.user("find it")], [_tool()], TurnRequest("find it"))


def test_llm_client_rejects_a_tool_not_in_the_active_catalog(caplog):
    message = SimpleNamespace(
        content=None,
        tool_calls=[SimpleNamespace(
            id="call-1",
            function=SimpleNamespace(name="delete_everything", arguments="{}"),
        )],
    )
    client, _completions = _client(message)

    with pytest.raises(LLMStructuredOutputError):
        client.complete([AgentMessage.user("do it")], [_tool()], TurnRequest("do it"))

    assert "LLM Tool-call response rejected" in caplog.text
    assert "tool_not_in_active_catalog" in caplog.text
    assert "delete_everything" not in caplog.text


def test_llm_client_retries_unknown_tool_once_without_executing_it():
    rejected = SimpleNamespace(
        content="",
        tool_calls=[SimpleNamespace(
            id="bad-call",
            function=SimpleNamespace(
                name="tiktok_unknown_tool",
                arguments='{"account_id":"must-not-be-forwarded"}',
            ),
        )],
    )
    accepted = SimpleNamespace(
        content="TikTok 目标应根据你要优化的业务结果来选。",
        tool_calls=[],
    )
    responses = [
        SimpleNamespace(
            choices=[SimpleNamespace(message=rejected, finish_reason="tool_calls")],
            usage=SimpleNamespace(prompt_tokens=11, completion_tokens=7),
        ),
        SimpleNamespace(
            choices=[SimpleNamespace(message=accepted, finish_reason="stop")],
            usage=SimpleNamespace(prompt_tokens=13, completion_tokens=5),
        ),
    ]
    completions = _QueuedCompletions(*responses)
    client = LLMClient(model="test-model", api_key="test-only")
    client._client = SimpleNamespace(
        chat=SimpleNamespace(completions=completions),
    )

    result = client.complete(
        [AgentMessage.user("tiktok ads 呢")],
        [_tool()],
        TurnRequest(user_input="tiktok ads 呢"),
    )

    assert result.content == "TikTok 目标应根据你要优化的业务结果来选。"
    assert result.tool_calls == ()
    assert len(completions.requests) == 2
    retry_messages = completions.requests[1]["messages"]
    assert any(
        "not included in the active Tool list" in str(item.get("content", ""))
        for item in retry_messages
    )
    assert "must-not-be-forwarded" not in json.dumps(retry_messages)
    assert result.usage["input_tokens"] == 24
    assert result.usage["output_tokens"] == 12
    assert result.usage["llm_requests"] == 2


def test_llm_client_recovers_from_unoffered_tool_call_when_catalog_is_empty():
    rejected = SimpleNamespace(
        content="",
        tool_calls=[SimpleNamespace(
            id="bad-call",
            function=SimpleNamespace(
                name="tiktok_list_targeting_options",
                arguments='{"account_id":"must-not-be-forwarded"}',
            ),
        )],
    )
    accepted = SimpleNamespace(
        content="定向设置用于约束广告触达的人群范围。",
        tool_calls=[],
    )
    completions = _QueuedCompletions(
        SimpleNamespace(
            choices=[SimpleNamespace(message=rejected, finish_reason="tool_calls")],
            usage=SimpleNamespace(prompt_tokens=11, completion_tokens=7),
        ),
        SimpleNamespace(
            choices=[SimpleNamespace(message=accepted, finish_reason="stop")],
            usage=SimpleNamespace(prompt_tokens=13, completion_tokens=5),
        ),
    )
    client = LLMClient(model="test-model", api_key="test-only")
    client._client = SimpleNamespace(
        chat=SimpleNamespace(completions=completions),
    )

    result = client.complete(
        [AgentMessage.user("定向设置详解")],
        [],
        TurnRequest(user_input="定向设置详解"),
    )

    assert result.content == "定向设置用于约束广告触达的人群范围。"
    assert result.tool_calls == ()
    assert len(completions.requests) == 2
    assert all("tools" not in request for request in completions.requests)
    retry_messages = completions.requests[1]["messages"]
    assert any(
        "not included in the active Tool list" in str(item.get("content", ""))
        for item in retry_messages
    )
    assert "must-not-be-forwarded" not in json.dumps(retry_messages)


def test_llm_client_stops_after_one_failed_unknown_tool_repair(caplog):
    invalid = SimpleNamespace(
        content="",
        tool_calls=[SimpleNamespace(
            id="bad-call",
            function=SimpleNamespace(name="private_write", arguments="{}"),
        )],
    )
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=invalid, finish_reason="tool_calls")],
        usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1),
    )
    completions = _QueuedCompletions(response)
    client = LLMClient(model="test-model", api_key="test-only")
    client._client = SimpleNamespace(
        chat=SimpleNamespace(completions=completions),
    )

    with pytest.raises(LLMStructuredOutputError):
        client.complete(
            [AgentMessage.user("do it")],
            [_tool()],
            TurnRequest(user_input="do it"),
        )

    assert len(completions.requests) == 2
    assert "private_write" not in caplog.text


def test_llm_client_rejects_duplicate_tool_call_ids():
    call = SimpleNamespace(
        id="call-1",
        function=SimpleNamespace(name="lookup_record", arguments="{}"),
    )
    client, _completions = _client(SimpleNamespace(
        content="",
        tool_calls=[call, call],
    ))

    with pytest.raises(LLMStructuredOutputError, match="duplicate"):
        client.complete([AgentMessage.user("find it")], [_tool()], TurnRequest("find it"))


def test_llm_client_rejects_unbounded_tool_call_batches():
    calls = [
        SimpleNamespace(
            id=f"call-{index}",
            function=SimpleNamespace(name="lookup_record", arguments="{}"),
        )
        for index in range(65)
    ]
    client, _completions = _client(SimpleNamespace(content="", tool_calls=calls))

    with pytest.raises(LLMStructuredOutputError, match="too many"):
        client.complete([AgentMessage.user("find it")], [_tool()], TurnRequest("find it"))


def test_llm_client_rejects_response_without_choices():
    client = LLMClient(model="test-model", api_key="test-only")
    client._client = SimpleNamespace(
        chat=SimpleNamespace(completions=_Completions(SimpleNamespace(
            choices=[], usage=None,
        ))),
    )

    with pytest.raises(LLMStructuredOutputError, match="choice"):
        client.complete([AgentMessage.user("find it")], [_tool()], TurnRequest("find it"))
