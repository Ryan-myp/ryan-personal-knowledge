import pytest

from agents.applications.advertising.persistence.models import (
    ScheduledTaskRecord, ScheduledTaskRunRecord,
)
from agents.applications.advertising.persistence.schedule_pages import SchedulePageQuery
from agents.applications.advertising.persistence.store import AdAgentStore


@pytest.fixture
def store():
    database = AdAgentStore(':memory:')
    for i in range(25):
        database.create_scheduled_task(ScheduledTaskRecord(
            schedule_id=f's-{i:02}', tenant_id='tenant', user_id='user',
            name=f'日报 {i:02}', prompt='分析' * 1000, cron_expression='0 9 * * *',
            next_run_at='2026-10-29T01:00:00+00:00',
            status='active' if i % 2 else 'paused',
        ))
    for tenant, user in [('other', 'user'), ('tenant', 'other')]:
        database.create_scheduled_task(ScheduledTaskRecord(
            schedule_id=f'{tenant}-{user}', tenant_id=tenant, user_id=user,
            name='private', prompt='secret', cron_expression='0 9 * * *',
        ))
    for i in range(35):
        date = f'2026-10-{1 + i // 2:02}T{(i % 2) * 12:02}:00:00+00:00'
        database.create_scheduled_task_run(ScheduledTaskRunRecord(
            schedule_run_id=f'r-{i:02}', schedule_id='s-00',
            tenant_id='tenant', user_id='user', scheduled_for=date,
            task_id=f'task-{i}', status='failed' if i % 2 else 'succeeded',
            error='test 100%_error' if i % 2 else None,
            result={'response': 'large response' * 10000},
        ))
    yield database
    database.close()


def query(**kwargs):
    return SchedulePageQuery(tenant_id='tenant', user_id='user', **kwargs)


def test_task_pages_are_scoped_deterministic_and_summaries_only(store):
    first = store.page_scheduled_tasks(query(limit=10))
    second = store.page_scheduled_tasks(query(page=2, limit=10))
    assert first['pagination']['total'] == 25
    assert first['pagination']['has_next'] is True
    assert [row['schedule_id'] for row in first['schedules']] == [f's-{i:02}' for i in range(10)]
    assert first['schedules'][-1]['schedule_id'] != second['schedules'][0]['schedule_id']
    assert 'payload' not in first['schedules'][0]
    assert 'prompt' not in first['schedules'][0]
    assert len(first['schedules'][0]['prompt_preview']) <= 280
    assert first['schedules'][0]['latest_run_status'] == 'succeeded'


def test_filter_counts_and_out_of_range_page_recover_after_deletions(store):
    page = store.page_scheduled_tasks(query(page=99, limit=5, statuses=('paused',), search='日报'))
    assert page['pagination']['total'] == 13
    assert page['pagination']['page'] == 3
    assert len(page['schedules']) == 3
    assert store.page_scheduled_tasks(query(search="' OR 1=1 --"))['pagination']['total'] == 0


def test_instance_pages_filter_by_parent_status_date_and_literal_search(store):
    page = store.page_scheduled_task_runs(query(
        schedule_id='s-00', limit=5, statuses=('failed',), search='100%_error',
        since='2026-10-04T00:00:00+00:00', until='2026-10-08T00:00:00+00:00',
    ))
    assert page['pagination']['total'] == 4
    assert len(page['runs']) == 4
    assert all('result' not in run for run in page['runs'])
    assert all(run['status'] == 'failed' for run in page['runs'])
    assert store.page_scheduled_task_runs(query(schedule_id='s-01'))['pagination']['total'] == 0
    assert store.page_scheduled_task_runs(SchedulePageQuery(
        tenant_id='other', user_id='user', schedule_id='s-00',
    ))['pagination']['total'] == 0


def test_single_run_read_requires_matching_parent_and_identity(store):
    assert store.get_scheduled_task_run(
        's-00', 'r-01', tenant_id='tenant', user_id='user',
    ).result['response'].startswith('large response')
    for parent, tenant, user in [('s-01','tenant','user'), ('s-00','other','user'),
                                 ('s-00','tenant','other')]:
        assert store.get_scheduled_task_run(
            parent, 'r-01', tenant_id=tenant, user_id=user,
        ) is None


@pytest.mark.parametrize('changes', [{'limit':0}, {'limit':501}, {'page':0}, {'search':'x'*201}])
def test_invalid_pagination_is_rejected(changes):
    with pytest.raises(ValueError):
        query(**changes)
