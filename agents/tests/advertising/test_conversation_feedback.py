from types import SimpleNamespace

import pytest

from agents.applications.advertising.operations.ad_conversation_services import (
    AdConversationServices,
)
from agents.applications.advertising.persistence.session_manager import (
    SessionManager,
)
from agents.applications.advertising.persistence.store import AdAgentStore
from agents.tools.advertising.shared.domain.conversation import (
    project_conversation_messages,
)


class _SessionManager:
    def __init__(self, *, session=None, update_count=1):
        self.session = session
        self.update_count = update_count
        self.lookup_calls = []
        self.save_calls = []

    def save_conversation_feedback(
        self, session_id, turn_id, *, user_id, tenant_id, feedback,
    ):
        self.save_calls.append((session_id, turn_id, user_id, tenant_id, feedback))
        return self.update_count if self.session is not None else 0


def test_feedback_is_scoped_to_owned_session_and_assistant_turn():
    session_manager = _SessionManager(session={"session_id": "session-a"})
    runtime = SimpleNamespace(
        _session_manager=session_manager,
        _redact_for_persistence=lambda value: value.replace(
            "sk-live-secret", "[REDACTED]"
        ),
    )
    service = AdConversationServices(runtime)

    saved = service.submit_conversation_feedback(
        session_id="session-a",
        turn_id="turn-a",
        rating="negative",
        reason="Missing metric; key=sk-live-secret",
        user_id="user-a",
        tenant_id="tenant-a",
    )

    assert saved is True
    assert len(session_manager.save_calls) == 1
    session_id, turn_id, user_id, tenant_id, feedback = session_manager.save_calls[0]
    assert (session_id, turn_id, user_id, tenant_id) == (
        "session-a", "turn-a", "user-a", "tenant-a",
    )
    assert feedback["rating"] == "negative"
    assert feedback["reason"] == "Missing metric; key=[REDACTED]"
    assert feedback["submitted_at"]


def test_feedback_write_is_rejected_when_session_is_outside_principal_scope():
    session_manager = _SessionManager(session=None)
    service = AdConversationServices(SimpleNamespace(
        _session_manager=session_manager,
        _redact_for_persistence=lambda value: value,
    ))

    saved = service.submit_conversation_feedback(
        session_id="session-a",
        turn_id="turn-a",
        rating="positive",
        reason=None,
        user_id="other-user",
        tenant_id="other-tenant",
    )

    assert saved is False
    assert session_manager.save_calls[0][2:4] == ("other-user", "other-tenant")


def test_feedback_does_not_write_when_turn_has_no_assistant_message():
    session_manager = _SessionManager(
        session={"session_id": "session-a"}, update_count=0,
    )
    service = AdConversationServices(SimpleNamespace(
        _session_manager=session_manager,
        _redact_for_persistence=lambda value: value,
    ))

    saved = service.submit_conversation_feedback(
        session_id="session-a",
        turn_id="user-turn",
        rating="positive",
        reason=None,
        user_id="user-a",
        tenant_id="tenant-a",
    )

    assert saved is False
    assert session_manager.save_calls[0][1] == "user-turn"


def test_feedback_service_rejects_unrecognized_rating_before_storage_access():
    session_manager = _SessionManager(session={"session_id": "session-a"})
    service = AdConversationServices(SimpleNamespace(
        _session_manager=session_manager,
        _redact_for_persistence=lambda value: value,
    ))

    with pytest.raises(ValueError, match="rating"):
        service.submit_conversation_feedback(
            session_id="session-a",
            turn_id="turn-a",
            rating="unknown",
            reason=None,
            user_id="user-a",
            tenant_id="tenant-a",
        )

    assert session_manager.save_calls == []


def test_history_projection_exposes_only_saved_feedback_rating():
    messages = project_conversation_messages([{
        "role": "assistant",
        "content": "已完成。",
        "turn_id": "turn-a",
        "created_at": "2026-10-20T09:00:00+00:00",
        "metadata": {
            "display_reply": "已完成。",
            "user_feedback": {
                "rating": "negative",
                "reason": "private reason",
            },
        },
    }])

    assert messages == [{
        "role": "assistant",
        "content": "已完成。",
        "turn_id": "turn-a",
        "created_at": "2026-10-20T09:00:00+00:00",
        "is_error": False,
        "feedback_rating": "negative",
    }]


def test_feedback_round_trips_through_existing_sqlite_transcript_store():
    store = AdAgentStore(":memory:")
    try:
        manager = SessionManager(store)
        manager.create_session(
            "session-a",
            "user-a",
            metadata={"tenant_id": "tenant-a"},
        )
        manager.record_conversation_message(
            "session-a",
            "turn-a",
            "assistant",
            "已完成。",
        )
        service = AdConversationServices(SimpleNamespace(
            _session_manager=manager,
            _redact_for_persistence=lambda value: value,
        ))

        saved = service.submit_conversation_feedback(
            session_id="session-a",
            turn_id="turn-a",
            rating="positive",
            reason=None,
            user_id="user-a",
            tenant_id="tenant-a",
        )
        records = manager.list_conversation_messages("session-a", limit=10)
        history = project_conversation_messages(
            [record.to_dict() for record in records]
        )

        assert saved is True
        assert records[-1].metadata["user_feedback"]["rating"] == "positive"
        assert history[-1]["feedback_rating"] == "positive"
        assert service.submit_conversation_feedback(
            session_id="session-a",
            turn_id="turn-a",
            rating="negative",
            reason="cross-user update",
            user_id="other-user",
            tenant_id="tenant-a",
        ) is False
        assert records[-1].metadata["user_feedback"]["rating"] == "positive"
    finally:
        store.close()


def test_feedback_trend_is_daily_and_scoped_without_exposing_reasons():
    from datetime import datetime, timedelta, timezone

    store = AdAgentStore(":memory:")
    try:
        manager = SessionManager(store)
        scopes = [
            ("session-a", "user-a", "tenant-a", ("turn-now", "turn-yesterday", "turn-old")),
            ("session-b", "user-b", "tenant-a", ("turn-other-user",)),
            ("session-c", "user-a", "tenant-b", ("turn-other-tenant",)),
        ]
        for session_id, user_id, tenant_id, turn_ids in scopes:
            manager.create_session(
                session_id, user_id, metadata={"tenant_id": tenant_id},
            )
            for turn_id in turn_ids:
                manager.record_conversation_message(
                    session_id, turn_id, "assistant", "回答",
                )

        now = datetime.now(timezone.utc)
        feedbacks = [
            ("session-a", "turn-now", "user-a", "tenant-a", "positive", now),
            ("session-a", "turn-yesterday", "user-a", "tenant-a", "negative", now - timedelta(days=1)),
            ("session-b", "turn-other-user", "user-b", "tenant-a", "positive", now),
            ("session-c", "turn-other-tenant", "user-a", "tenant-b", "positive", now),
            ("session-a", "turn-old", "user-a", "tenant-a", "positive", now - timedelta(days=8)),
        ]
        for session_id, turn_id, user_id, tenant_id, rating, submitted_at in feedbacks:
            assert manager.save_conversation_feedback(
                session_id,
                turn_id,
                user_id=user_id,
                tenant_id=tenant_id,
                feedback={
                    "rating": rating,
                    "reason": "private feedback reason",
                    "submitted_at": submitted_at.isoformat(),
                },
            )

        trend = manager.get_conversation_feedback_trend(
            days=7, user_id="user-a", tenant_id="tenant-a",
        )

        assert trend["total"] == 2
        assert trend["positive"] == 1
        assert trend["negative"] == 1
        assert trend["positive_rate"] == 0.5
        assert len(trend["daily"]) == 7
        assert sum(point["total"] for point in trend["daily"]) == 2
        assert all(
            set(point) == {"date", "positive", "negative", "total"}
            for point in trend["daily"]
        )
        assert "reason" not in str(trend)
        assert all("session" not in str(point) for point in trend["daily"])
    finally:
        store.close()


def test_feedback_resubmission_replaces_existing_rating_and_empty_rate_is_null():
    store = AdAgentStore(":memory:")
    try:
        manager = SessionManager(store)
        manager.create_session(
            "session-a", "user-a", metadata={"tenant_id": "tenant-a"},
        )
        manager.record_conversation_message(
            "session-a", "turn-a", "assistant", "回答",
        )

        for rating in ("positive", "negative"):
            assert manager.save_conversation_feedback(
                "session-a",
                "turn-a",
                user_id="user-a",
                tenant_id="tenant-a",
                feedback={
                    "rating": rating,
                    "reason": None,
                    "submitted_at": "2026-10-20T00:00:00+00:00",
                },
            )

        trend = manager.get_conversation_feedback_trend(
            days=7, user_id="nobody", tenant_id="tenant-a",
        )
        updated = manager.get_conversation_feedback_trend(
            days=7, user_id="user-a", tenant_id="tenant-a",
        )

        assert trend["total"] == 0
        assert trend["positive_rate"] is None
        assert updated["total"] == 1
        assert updated["positive"] == 0
        assert updated["negative"] == 1
    finally:
        store.close()


def test_feedback_migration_backfills_existing_transcript_ratings(tmp_path):
    database = tmp_path / "feedback-migration.db"
    store = AdAgentStore(str(database))
    manager = SessionManager(store)
    manager.create_session(
        "session-a", "user-a", metadata={"tenant_id": "tenant-a"},
    )
    manager.record_conversation_message(
        "session-a", "turn-a", "assistant", "回答",
    )
    manager.update_conversation_message_metadata(
        "session-a",
        "turn-a",
        "assistant",
        {"user_feedback": {
            "rating": "positive",
            "reason": "legacy reason should not be copied",
            "submitted_at": "2026-10-20T00:00:00+00:00",
        }},
    )
    store._get_conn().execute(
        "DELETE FROM schema_migrations WHERE version = 23"
    )
    store._get_conn().commit()
    store.close()

    upgraded = AdAgentStore(str(database))
    try:
        trend = SessionManager(upgraded).get_conversation_feedback_trend(
            days=7, user_id="user-a", tenant_id="tenant-a",
        )
        assert trend["total"] == 1
        assert trend["positive"] == 1
        assert trend["negative"] == 0
        assert "reason" not in str(trend)
    finally:
        upgraded.close()


@pytest.mark.parametrize("days", [0, 14, 91])
def test_feedback_trend_rejects_unsupported_windows(days):
    store = AdAgentStore(":memory:")
    try:
        with pytest.raises(ValueError, match="days"):
            store.get_conversation_feedback_trend(
                days=days, user_id="user-a", tenant_id="tenant-a",
            )
    finally:
        store.close()
