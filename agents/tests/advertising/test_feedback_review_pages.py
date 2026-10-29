from datetime import datetime, timedelta, timezone

import pytest

from agents.applications.advertising.persistence.feedback_review_pages import FeedbackReviewQuery
from agents.applications.advertising.persistence.session_manager import SessionManager
from agents.applications.advertising.persistence.store import AdAgentStore


@pytest.fixture
def store():
    database = AdAgentStore(':memory:')
    manager = SessionManager(database)
    for session, user, tenant in [('main', 'user', 'tenant'), ('peer', 'peer', 'tenant'),
                                  ('other', 'user', 'other')]:
        manager.create_session(session, user, metadata={'tenant_id': tenant})
    start = datetime(2026, 10, 1, tzinfo=timezone.utc)
    for i in range(126):
        session = 'main' if i < 124 else 'peer' if i == 124 else 'other'
        user, tenant = ('peer' if session == 'peer' else 'user',
                        'other' if session == 'other' else 'tenant')
        turn = f'turn-{i:03}'
        manager.record_conversation_message(session, turn, 'user', f'问题 question-only-{i:03}')
        manager.record_conversation_message(session, turn, 'assistant', f'回答 answer-only-{i:03}')
        manager.save_conversation_feedback(session, turn, user_id=user, tenant_id=tenant,
            feedback={'rating': 'positive' if i == 123 else 'negative',
                      'reason': '100%_coverage!' if i == 0 else f'预算异常 {i:03}',
                      'submitted_at': (start + timedelta(hours=i)).isoformat()})
    yield database
    database.close()


def query(**kwargs):
    return FeedbackReviewQuery(tenant_id='tenant', **kwargs)


def test_pages_reach_past_old_limit_and_use_tenant_review_scope(store):
    first = store.page_conversation_feedback_review_queue(query(limit=50))
    last = store.page_conversation_feedback_review_queue(query(page=3, limit=50))
    assert first['pagination']['total'] == 124
    assert len(last['items']) == 24
    assert first['items'][0]['session_id'] == 'peer'
    assert all(item['session_id'] != 'other' for item in first['items'])
    assert {item['feedback_id'] for item in first['items']}.isdisjoint(
        item['feedback_id'] for item in last['items'])
    assert first == store.page_conversation_feedback_review_queue(query(limit=50))


def test_review_filters_count_and_page_recovery_after_review(store):
    page = store.page_conversation_feedback_review_queue(query(page=13, limit=10))
    for item in page['items']:
        store.review_conversation_feedback(item['feedback_id'], tenant_id='tenant',
            reviewer_id='reviewer', review_status='candidate', expected_behavior='核实成本口径',
            reviewed_at='2026-10-29T00:00:00+00:00')
    remaining = store.page_conversation_feedback_review_queue(query(page=13, limit=10))
    assert remaining['pagination']['page'] == 12
    assert remaining['pagination']['total'] == 120
    candidates = store.page_conversation_feedback_review_queue(query(status='candidate', search='核实成本'))
    assert candidates['pagination']['total'] == 4
    assert store.page_conversation_feedback_review_queue(query(status='all'))['pagination']['total'] == 124


@pytest.mark.parametrize('text', ['question-only-011', 'answer-only-011', '预算异常 011'])
def test_search_matches_feedback_and_its_turn_text(store, text):
    page = store.page_conversation_feedback_review_queue(query(search=text))
    assert page['pagination']['total'] == 1
    assert page['items'][0]['turn_id'] == 'turn-011'


def test_search_is_literal_and_dates_have_inclusive_start_exclusive_end(store):
    assert store.page_conversation_feedback_review_queue(query(search='100%_coverage!'))['pagination']['total'] == 1
    assert store.page_conversation_feedback_review_queue(query(search="' OR 1=1 --"))['pagination']['total'] == 0
    page = store.page_conversation_feedback_review_queue(query(
        since='2026-10-01T01:00:00+00:00', until='2026-10-01T03:00:00+00:00'))
    assert [row['turn_id'] for row in page['items']] == ['turn-002', 'turn-001']
    empty = store.page_conversation_feedback_review_queue(query(status='dismissed', page=999))
    assert empty['pagination']['page'] == 1
    assert empty['pagination']['total'] == 0


@pytest.mark.parametrize('values', [{'page': 0}, {'page': 10001}, {'limit': 0}, {'limit': 101},
    {'search': 'x' * 201}, {'status': 'other'}, {'tenant_id': ''},
    {'since': '2026-10-02', 'until': '2026-10-01'}])
def test_invalid_filters_are_rejected(values):
    with pytest.raises(ValueError):
        FeedbackReviewQuery(**{'tenant_id': 'tenant', **values})
