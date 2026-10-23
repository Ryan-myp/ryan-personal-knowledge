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
