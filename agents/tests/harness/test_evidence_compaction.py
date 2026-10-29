"""Long runs preserve protocol, scope and facts while shrinking read previews."""

from copy import deepcopy
from dataclasses import replace
import json

import pytest

from agents.agent_harness import AgentApplication, AgentMessage, StaticToolSource, ToolBinding
from agents.agent_harness.messages import ModelTurn, ToolCall
from agents.agent_harness.evidence_compaction import compact_read_messages


DEFINITION = {
    "name": "lookup", "effect_class": "read", "result_items_key": "records",
    "result_id_fields": ["record_id"], "result_summary_fields": ["status"],
}


def content_size(message):
    return len(str(message.content))


def exchange(call_id, *, body_size=800, count=8, content_patch=None):
    content = {
        "success": True, "data_status": "simulated",
        "data": {
            "records": [{"record_id": f"{call_id}-{i}", "status": "PAUSED",
                         "body": "明细" * body_size} for i in range(count)],
            "query_context": {"account_id": "test-account", "date_preset": "yesterday"},
            "query_summary": {"returned_count": count, "context_count": count,
                              "context_truncated": False, "scope": "returned_page"},
            "has_more": True, "next_cursor": "cursor-unchanged",
        },
    }
    content.update(content_patch or {})
    return [
        AgentMessage.assistant("", metadata={"tool_calls": [
            {"id": call_id, "name": "lookup", "arguments": {"page": call_id}},
        ]}),
        AgentMessage.tool(content, tool_call_id=call_id, name="lookup"),
    ]


def compact(messages, limit=3000, definitions=(DEFINITION,)):
    return compact_read_messages(
        messages, definitions, max_chars=limit, message_size=content_size,
    )


def test_old_reads_shrink_first_and_keep_scope_ids_and_latest_evidence():
    messages = [AgentMessage.user("保持暂停状态，分析昨天数据"), *exchange("old"),
                *exchange("latest", body_size=5, count=2)]
    original = deepcopy(messages)
    bounded = compact(messages)
    assert sum(map(content_size, bounded)) <= 3000
    assert bounded[-1] == messages[-1]
    assert [item.message_id for item in bounded] == [item.message_id for item in messages]
    assert bounded[1].metadata == messages[1].metadata
    result = bounded[2].content
    assert result["data_status"] == "simulated"
    assert result["data"]["query_context"] == original[2].content["data"]["query_context"]
    assert result["data"]["next_cursor"] == "cursor-unchanged"
    assert result["data"]["query_summary"]["returned_count"] == 8
    assert result["data"]["query_summary"]["context_truncated"] is True
    assert result["data"]["query_summary"]["context_count"] == len(result["data"]["records"])
    assert result["data"]["records"][0]["record_id"] == "old-0"
    assert result["context_compaction"]["original_context_count"] == 8
    assert messages == original


def test_oversized_rows_keep_exact_declared_identity_and_mark_omitted_fields():
    messages = [AgentMessage.user("查一下"), *exchange("large", body_size=8000)]
    bounded = compact(messages, 1800)
    result = bounded[-1].content
    assert sum(map(content_size, bounded)) <= 1800
    assert result["data"]["records"][0] == {"record_id": "large-0", "status": "PAUSED"}
    assert result["context_compaction"]["fields_omitted"] is True
    assert result["context_compaction"]["original_context_count"] == 8


@pytest.mark.parametrize("patch", [
    {"success": False}, {"needs_input": True}, {"needs_confirmation": True},
    {"effect_state": "unknown"}, {"requires_reconciliation": True},
    {"recovery_required": True}, {"interaction": {"type": "choice"}},
    {"error": "not a clean success"}, {"cancelled": True},
])
def test_failed_uncertain_and_interactive_results_are_never_compacted(patch):
    messages = [AgentMessage.user("task"), *exchange("protected", content_patch=patch)]
    assert compact(messages, 1000) == messages


@pytest.mark.parametrize("definition", [
    {**DEFINITION, "effect_class": "write"},
    {**DEFINITION, "effect_class": "unknown"},
    {**DEFINITION, "result_items_key": "other"},
    {"name": "lookup", "result_items_key": "records"},
])
def test_only_explicitly_declared_read_collections_can_shrink(definition):
    messages = [AgentMessage.user("task"), *exchange("protected")]
    assert compact(messages, 1000, (definition,)) == messages


def test_orphan_tool_result_is_not_compacted():
    messages = [AgentMessage.user("task"), exchange("orphan")[-1]]
    assert compact(messages, 1000) == messages


def test_json_string_representation_and_metadata_are_preserved():
    messages = [AgentMessage.user("task"), *exchange("string")]
    messages[-1] = replace(messages[-1], content=json.dumps(messages[-1].content))
    result = compact(messages, 2000)[-1]
    assert isinstance(result.content, str)
    assert json.loads(result.content)["context_compaction"]["original_context_count"] == 8
    assert result.tool_call_id == "string"


def test_minimum_evidence_does_not_fit_keeps_original_instead_of_empty_success():
    messages = [AgentMessage.user("task"), *exchange("protected")]
    assert compact(messages, 20) == messages


def test_repeated_projection_keeps_original_counts_and_protected_policy():
    messages = [AgentMessage.system("不能执行写操作"), AgentMessage.user("task"),
                *exchange("repeated", body_size=8000)]
    first = compact(messages, 2000)
    second = compact(first, 1300)
    assert second[0] == messages[0]
    assert second[-1].content["context_compaction"]["original_context_count"] == 8
    assert second[-1].content["context_compaction"]["fields_omitted"] is True
    assert second[-1].content["context_compaction"]["omitted_rows"] == (
        8 - len(second[-1].content["data"]["records"])
    )


def test_model_payload_budget_compacts_after_old_turn_eviction():
    from agents.agent_harness.model_limits import bound_model_messages, model_input_chars

    messages = [AgentMessage.system("policy"), AgentMessage.user("old task"),
                AgentMessage.assistant("old answer"), AgentMessage.user("current"),
                *exchange("current")]
    result = bound_model_messages(messages, (), max_chars=2200, evidence_definitions=(DEFINITION,))
    assert model_input_chars(result, ()) <= 2200
    assert result[0] == messages[0]
    assert all(item.content != "old task" for item in result)
    assert result[-1].tool_call_id == "current"
    assert result[-1].content["context_compaction"]


def test_model_payload_budget_still_rejects_large_user_input_or_write_results():
    from agents.agent_harness.model_limits import bound_model_messages, ModelInputLimitError

    for messages, definitions in (
        ([AgentMessage.user("large user content" * 1000)], (DEFINITION,)),
        ([AgentMessage.user("task"), *exchange("write")], ({**DEFINITION, "effect_class": "write"},)),
    ):
        with pytest.raises(ModelInputLimitError):
            bound_model_messages(messages, (), max_chars=2000, evidence_definitions=definitions)


@pytest.mark.parametrize("limit", [0, -1, True, 1.2])
def test_invalid_compaction_budget_is_rejected(limit):
    with pytest.raises(ValueError):
        compact([], limit)


def test_long_current_run_completes_without_rereading_or_mutating_durable_results():
    calls, inputs, events = [], [], []

    class Model:
        def complete(self, messages, _tools, _request):
            inputs.append(messages)
            if messages[-1].role == "user":
                return ModelTurn(tool_calls=tuple(
                    ToolCall(f"lookup-{i}", "lookup", {"page": i}) for i in range(3)
                ))
            return "三页已经读取，按实际返回范围汇总。"

    def lookup(_context, arguments):
        calls.append(arguments["page"])
        return exchange(str(arguments["page"]), body_size=180, count=6)[-1].content

    app = AgentApplication.create(
        model=Model(), max_transcript_chars=6500, max_model_input_chars=20_000,
        event_callback=events.append,
    )
    app.register_tool_source(StaticToolSource("reader", [ToolBinding(DEFINITION, lookup)]))
    try:
        result = app.prompt("保持暂停，只分析数据", session_id="long")
        assert result.status.value == "succeeded"
        assert sorted(calls) == [0, 1, 2]
        assert len(result.data["tool_results"]) == 3
        raw = [m for m in app.agent._state_for("long").messages if m.role == "tool"]
        assert all(len(m.content["data"]["records"]) == 6 for m in raw)
        assert any(m.content.get("context_compaction") for m in inputs[-1] if m.role == "tool")
        event = next(item for item in events if item["type"] == "tool_evidence_compacted")
        assert event["compacted_messages"] > 0
        assert "test-account" not in str(event)
    finally:
        app.close()
