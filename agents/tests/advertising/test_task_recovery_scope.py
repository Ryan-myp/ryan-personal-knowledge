"""Recovery must retain trusted identity scope on both database operations."""

import pytest

from agents.applications.advertising.persistence.models import TaskRecord
from agents.applications.advertising.persistence.store import AdAgentStore


@pytest.fixture
def store():
    backend = AdAgentStore(":memory:")
    backend.create_task(TaskRecord(
        task_id="recover", tenant_id="tenant", user_id="user",
        kind="local", status="recovery_required", error="uncertain",
        result={"old": True}, lease_owner="old-worker",
    ))
    yield backend
    backend.close()


@pytest.mark.parametrize("scope", [
    {}, {"tenant_id": "tenant"}, {"user_id": "user"},
    {"tenant_id": "tenant", "user_id": "user"},
])
def test_recovery_requeues_with_optional_identity_scope(store, scope):
    record = store.requeue_recovery_task(
        "recover", recovery_reference="offline-readback", **scope,
    )
    assert record.status == "queued"
    assert record.error is None and record.result is None
    assert record.lease_owner is None
    assert record.metadata["recovery_reference"] == "offline-readback"


@pytest.mark.parametrize("scope", [
    {"tenant_id": "other", "user_id": "user"},
    {"tenant_id": "tenant", "user_id": "other"},
])
def test_recovery_rejects_another_identity(store, scope):
    before = store.get_task("recover").to_dict()
    assert store.requeue_recovery_task(
        "recover", recovery_reference="offline-readback", **scope,
    ) is None
    assert store.get_task("recover").to_dict() == before


def test_recovery_update_rechecks_scope_after_read(store):
    # Simulate an identity change between SELECT and UPDATE on this in-memory
    # connection. Removing surplus parameters without fencing the write fails.
    connection = store._get_conn()

    # Use a connection proxy to inject the change after the scoped read.
    class ConnectionProxy:
        def execute(self, query, parameters=()):
            cursor = connection.execute(query, parameters)
            if query.startswith("SELECT metadata FROM tasks"):
                row = cursor.fetchone()
                connection.execute(
                    "UPDATE tasks SET user_id = ? WHERE task_id = ?",
                    ("new-user", "recover"),
                )
                return RowCursor(row)
            return cursor

        def commit(self):
            connection.commit()

    class RowCursor:
        def __init__(self, row):
            self.row = row

        def fetchone(self):
            return self.row

    original = store._get_conn
    store._get_conn = lambda: ConnectionProxy()
    try:
        assert store.requeue_recovery_task(
            "recover", recovery_reference="offline-readback",
            tenant_id="tenant", user_id="user",
        ) is None
    finally:
        store._get_conn = original
    assert store.get_task("recover").status == "recovery_required"
    assert store.get_task("recover").user_id == "new-user"
