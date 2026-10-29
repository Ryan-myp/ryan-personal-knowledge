"""Sidebar reads stay bounded independently of conversation history length."""

from datetime import datetime, timedelta, timezone

import pytest

from agents.applications.advertising.composition.ad_application import AdvertisingComposition
from agents.applications.advertising.persistence.models import ConversationMessageRecord
from agents.applications.advertising.persistence.store import AdAgentStore


@pytest.fixture
def runtime():
    owner = AdvertisingComposition(
        require_llm=False, offline_mode=True, features=[],
        persistence_store=AdAgentStore(":memory:"), start_background_workers=False,
    )
    yield owner
    owner.close(wait=True)


def record_history(runtime, session_id, *, user="operator", tenant="tenant", turns=3):
    runtime._ensure_session(session_id, user, None, None, tenant_id=tenant)
    start = datetime(2026, 10, 1, tzinfo=timezone.utc)
    for index in range(turns):
        for offset, (role, content) in enumerate((
            ("user", f"question-{index}"), ("assistant", f"answer-{index}"),
        )):
            runtime.persistence_store.record_conversation_message(ConversationMessageRecord(
                message_id=f"{session_id}-{index:04d}-{role}", session_id=session_id,
                turn_id=f"turn-{index}", role=role, content=content,
                created_at=(start + timedelta(seconds=index * 2 + offset)).isoformat(),
            ))


def test_sidebar_uses_persisted_visible_window_without_reloading_protocol(runtime, monkeypatch):
    session = runtime._ensure_session("cached", "operator", None, None, tenant_id="tenant")
    runtime.persistence_services.persist_conversation_turn(
        session, "turn", "帮我分析报表", "已核对数据范围，结果如下。",
    )
    monkeypatch.setattr(
        runtime._session_manager, "list_conversation_messages",
        lambda *_args, **_kwargs: pytest.fail("sidebar must not reload each transcript"),
    )
    monkeypatch.setattr(
        runtime._session_manager, "list_conversation_preview_messages",
        lambda *_args, **_kwargs: pytest.fail("cached sidebar needs no history query"),
    )

    summaries = runtime.list_conversations(user_id="operator", tenant_id="tenant")

    assert len(summaries) == 1
    assert summaries[0]["preview"] == "已核对数据范围，结果如下。"
    assert summaries[0]["message_count"] == 2


def test_legacy_sidebar_uses_one_bounded_batch_and_keeps_original_title(runtime, monkeypatch):
    for index in range(4):
        record_history(runtime, f"legacy-{index}", turns=80)
    monkeypatch.setattr(
        runtime._session_manager, "list_conversation_messages",
        lambda *_args, **_kwargs: pytest.fail("legacy summaries must use a batch read"),
    )
    queries = []
    runtime.persistence_store._get_conn().set_trace_callback(queries.append)
    try:
        summaries = runtime.list_conversations(user_id="operator", tenant_id="tenant")
    finally:
        runtime.persistence_store._get_conn().set_trace_callback(None)

    assert len(summaries) == 4
    assert all(row["preview"] == "answer-79" for row in summaries)
    assert all("question-0" in row["title"] for row in summaries)
    assert all("message_count" not in row for row in summaries)
    reads = [query for query in queries if "conversation_messages" in query.lower()]
    assert len(reads) == 1


def test_preview_batch_checks_identity_and_bounds_each_session(runtime):
    record_history(runtime, "visible", turns=80)
    record_history(runtime, "other-user", user="other")
    record_history(runtime, "other-tenant", tenant="other")

    pages = runtime.persistence_store.list_conversation_preview_messages(
        ["visible", "other-user", "other-tenant"],
        user_id="operator", tenant_id="tenant", limit_per_session=4,
    )

    assert set(pages) == {"visible"}
    assert len(pages["visible"].records) <= 5
    assert pages["visible"].records[0].content == "question-0"
    assert pages["visible"].records[-1].content == "answer-79"
    assert pages["visible"].has_more is True
    assert runtime.persistence_store.list_conversation_preview_messages(
        [], user_id="operator", tenant_id="tenant",
    ) == {}


def test_preview_batch_failure_does_not_rewrite_history_and_is_retryable(runtime, monkeypatch):
    record_history(runtime, "legacy")
    original = runtime.persistence_store.list_conversation_preview_messages

    def unavailable(*_args, **_kwargs):
        raise RuntimeError("storage unavailable")

    monkeypatch.setattr(
        runtime.persistence_store, "list_conversation_preview_messages",
        unavailable,
    )
    with pytest.raises(RuntimeError, match="storage unavailable"):
        runtime.list_conversations(user_id="operator", tenant_id="tenant")
    monkeypatch.setattr(runtime.persistence_store, "list_conversation_preview_messages", original)

    assert runtime.list_conversations(user_id="operator", tenant_id="tenant")[0]["preview"] == "answer-2"
    assert len(runtime.persistence_store.list_conversation_messages("legacy")) == 6


def test_empty_presentation_cache_does_not_hide_a_durable_visible_reply(runtime):
    record_history(runtime, "empty-cache", turns=1)
    runtime.persistence_store.update_session("empty-cache", {
        "tenant_id": "tenant", "messages": [
            {"role": "user", "content": "question-0"},
            {"role": "assistant", "content": ""},
        ],
    })

    summary = runtime.list_conversations(user_id="operator", tenant_id="tenant")[0]

    assert summary["preview"] == "answer-0"
