import pytest

from agents.deployments.advertising.api.progress import (
    StreamExecutionSummaries, public_execution_events, public_run_view, progress_language,
)
from types import SimpleNamespace


@pytest.mark.parametrize("language", ["zh", "en"])
def test_progress_is_grounded_in_actual_events_and_never_echoes_model_scratchpad(language):
    progress = StreamExecutionSummaries(language)
    first = progress.for_event({"type": "model_start"})
    assert first["language_code"] == language
    assert first["content_type"] == "execution_summary"
    assert progress.for_event({
        "type": "model_reasoning_delta",
        "delta": "The user is asking to query reports. Private model scratchpad.",
    }) is None
    start = progress.for_event({
        "type": "tool_execution_start", "tool_name": "google_get_campaign_report",
        "tool_call_id": "call-1", "arguments": {"access_token": "never-show-this"},
    })
    assert "google_get_campaign_report" in start["content"]
    assert "never-show-this" not in str(start)
    done = progress.for_event({
        "type": "tool_execution_end", "tool_name": "google_get_campaign_report",
        "tool_call_id": "call-1",
        "result": {"success": True, "data": {"query_summary": {"returned_count": 3}}},
    })
    assert "3" in done["content"]
    assert progress.for_event({"type": "model_start"})["content"] != first["content"]


def test_confirmation_is_not_described_as_successful_external_execution():
    progress = StreamExecutionSummaries("zh")
    event = progress.for_event({
        "type": "tool_execution_end", "tool_name": "create",
        "result": {"success": False, "needs_confirmation": True},
    })
    assert "确认" in event["content"]
    assert "尚未" in event["content"]
    assert "已完成" not in event["content"]


def test_execution_summary_explains_tool_selection_from_registered_contract():
    definition = SimpleNamespace(
        intent_aliases=["知识库检索", "搜索知识库"],
        intent_types=["knowledge_search"],
        namespace="agent_platform",
        resource_type="knowledge",
        action="search",
        result_items_key="results",
    )
    registry = SimpleNamespace(get=lambda _name: (definition, object()))
    progress = StreamExecutionSummaries("zh", registry=registry)

    started = progress.for_event({
        "type": "tool_execution_start",
        "tool_name": "agent_knowledge_search",
        "arguments": {"query": "给我详细讲一下 API", "access_token": "secret"},
    })
    assert "知识库检索" in started["content"]
    assert "返回结果" in started["content"]
    assert "secret" not in started["content"]

    completed = progress.for_event({
        "type": "tool_execution_end",
        "tool_name": "agent_knowledge_search",
        "result": {
            "success": True,
            "data": {"query_summary": {"returned_count": 4}},
        },
    })
    assert "4 项" in completed["content"]
    assert "整理答复" in completed["content"]


def test_english_execution_summary_uses_registered_english_alias():
    definition = SimpleNamespace(
        intent_aliases=["查询 Meta Campaign 列表", "list Meta campaigns"],
        intent_types=["list_campaigns"],
        namespace="meta",
        resource_type="campaign",
        action="list",
    )
    registry = SimpleNamespace(get=lambda _name: (definition, object()))
    progress = StreamExecutionSummaries("en", registry=registry)
    event = progress.for_event({
        "type": "tool_execution_start", "tool_name": "meta_list_campaigns",
    })
    assert "list Meta campaigns" in event["content"]
    assert "gather the relevant information" in event["content"]


def test_model_completion_summary_reports_the_observed_next_step():
    progress = StreamExecutionSummaries("zh")
    event = progress.for_event({
        "type": "model_end", "tool_call_count": 2, "has_content": False,
    })
    assert "2 个工具" in event["content"]
    assert "执行并核验实际结果" in event["content"]


def test_chinese_summary_keeps_fallback_explanation_in_chinese():
    definition = SimpleNamespace(
        intent_aliases=["list campaigns"],
        intent_types=["list_campaigns"],
        namespace="meta",
        resource_type="campaign",
        action="list",
    )
    registry = SimpleNamespace(get=lambda _name: (definition, object()))
    progress = StreamExecutionSummaries("zh", registry=registry)
    event = progress.for_event({
        "type": "tool_execution_start", "tool_name": "meta_list_campaigns",
    })
    assert "当前步骤调用 Tool" in event["content"]
    assert "实际返回结果" in event["content"]


def test_raw_progress_events_are_removed_without_modifying_runtime_events():
    events = [
        {"type": "model_start", "seq": 1},
        {"type": "model_reasoning_delta", "seq": 2, "delta": "private"},
        {"type": "model_delta", "seq": 3, "delta": "<analysis>private"},
        {"type": "agent_end", "seq": 4},
    ]
    public = public_execution_events(events)
    assert [event["seq"] for event in public] == [1, 4]
    assert len(events) == 4


def test_history_filter_keeps_cursor_and_never_rewrites_private_stored_events():
    raw = {
        "latest_seq": 3,
        "events": [{"type": "model_reasoning_delta", "seq": 3, "delta": "private"}],
        "execution_traces": {"turn": {"events": [{"type": "model_delta", "delta": "private"}]}},
    }
    public = public_run_view(raw)
    assert public["latest_seq"] == 3
    assert public["events"] == []
    assert public["execution_traces"]["turn"]["events"] == []
    assert raw["events"][0]["delta"] == "private"


def test_numeric_progress_uses_scoped_user_history_not_other_principals():
    seen = []

    def get_conversation(**kwargs):
        seen.append(kwargs)
        return {"messages": [
            {"role": "user", "content": "Please update the budget."},
            {"role": "assistant", "content": "请补充预算"},
        ]}

    language = progress_language(
        SimpleNamespace(get_conversation=get_conversation), "50", "session",
        SimpleNamespace(user_id="operator", tenant_id="tenant"),
    )
    assert language == "en"
    assert seen == [{
        "session_id": "session", "user_id": "operator", "tenant_id": "tenant", "limit": 2,
    }]
