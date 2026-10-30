"""Late workers must not replace a recovered task's current owner or outcome."""

import threading
from unittest.mock import Mock

import pytest

from agents.agent_platform.infrastructure.durable import TaskExecutor
from agents.agent_platform.infrastructure.durable.sqlite_store import SQLiteTaskQueueStore
from agents.agent_platform.infrastructure.durable.task import TaskSubmission
from agents.applications.advertising.persistence.store import AdAgentStore


@pytest.fixture(params=[AdAgentStore, SQLiteTaskQueueStore])
def store(request):
    backend = request.param(':memory:')
    yield backend
    backend.close()


def take_over(store, task_id):
    assert store.update_task(task_id, 'recovery_required', expected_statuses=['running'])
    assert store.requeue_recovery_task(task_id, recovery_reference='offline-verified')
    assert store.claim_task(task_id, 'replacement', 60)


@pytest.mark.parametrize('failure', [False, True])
def test_late_handler_cannot_finish_the_replacement_run(store, failure):
    executor = TaskExecutor(store, max_workers=1, max_queue=0)

    def handler(context):
        take_over(store, context.task_id)
        if failure:
            raise ValueError('old failure')
        return {'reply': 'old result'}

    executor.register_handler('offline', handler)
    try:
        task, _ = executor.submit('offline', {}, tenant_id='t', user_id='u')
        executor.shutdown(wait=True)
        current = store.get_task(task.task_id)
        assert current.status == 'running'
        assert current.lease_owner == 'replacement'
        assert current.result is None and current.error is None
    finally:
        executor.shutdown(wait=True)


def test_update_fence_is_checked_on_the_write(store):
    store.create_task(TaskSubmission(task_id='task', kind='offline', tenant_id='t', user_id='u', status='queued', payload={}))
    store.claim_task('task', 'original', 60)
    assert not store.update_task('task', 'succeeded', lease_owner='other')
    assert store.get_task('task').status == 'running'
    assert store.update_task('task', 'succeeded', lease_owner='original')


def test_pre_execution_failure_cannot_overwrite_new_owner(store):
    def prepare(context):
        take_over(store, context.task_id)
        raise ValueError('hook failed after takeover')

    executor = TaskExecutor(store, before_execute=prepare)
    handler = Mock(return_value={'ok': True})
    executor.register_handler('offline', handler)
    try:
        task, _ = executor.submit('offline', {}, tenant_id='t', user_id='u')
        executor.shutdown(wait=True)
        assert store.get_task(task.task_id).lease_owner == 'replacement'
        handler.assert_not_called()
    finally:
        executor.shutdown(wait=True)


def test_inflight_heartbeat_cannot_turn_uncertain_completion_into_success(store, monkeypatch):
    entered, resume = threading.Event(), threading.Event()
    finished = threading.Event()

    def heartbeat(*_args):
        entered.set()
        assert resume.wait(4)
        finished.set()
        return False

    monkeypatch.setattr(store, 'heartbeat_task', heartbeat)
    executor = TaskExecutor(store, max_workers=1, lease_seconds=0.1)

    def handler(_context):
        assert entered.wait(2)
        return {'reply': 'completed before heartbeat resolved'}

    executor.register_handler('offline', handler)
    try:
        task, _ = executor.submit('offline', {}, tenant_id='t', user_id='u')
        executor._pool.shutdown(wait=True)
        assert store.get_task(task.task_id).status == 'recovery_required'
    finally:
        resume.set()
        if entered.is_set():
            assert finished.wait(2)
        executor.shutdown(wait=True)


def test_hook_takeover_stops_execution_even_without_an_exception(store):
    executor = TaskExecutor(store, before_execute=lambda context: take_over(store, context.task_id))
    handler = Mock(return_value={'ok': True})
    executor.register_handler('offline', handler)
    try:
        task, _ = executor.submit('offline', {}, tenant_id='t', user_id='u')
        executor.shutdown(wait=True)
        handler.assert_not_called()
        assert store.get_task(task.task_id).lease_owner == 'replacement'
    finally:
        executor.shutdown(wait=True)


def test_cancellation_does_not_hide_an_explicit_uncertain_outcome(store):
    executor = TaskExecutor(store)

    def handler(context):
        store.cancel_task(context.task_id)
        return {'status': 'recovery_required', 'recovery_required': True, 'effect_state': 'unknown'}

    executor.register_handler('offline', handler)
    try:
        task, _ = executor.submit('offline', {}, tenant_id='t', user_id='u')
        executor.shutdown(wait=True)
        assert store.get_task(task.task_id).status == 'recovery_required'
    finally:
        executor.shutdown(wait=True)
