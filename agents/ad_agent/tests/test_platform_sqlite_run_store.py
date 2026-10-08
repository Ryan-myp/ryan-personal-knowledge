"""SQLite Run history is durable, scoped, and redacted by the platform."""

import json

from agents.agent_platform.infrastructure.durable.sqlite_run_store import SQLiteRunStore


def test_run_events_survive_reopen_and_sensitive_data_is_redacted(tmp_path):
    path = tmp_path / "runs.sqlite3"
    first = SQLiteRunStore(path)
    assert first.start_run(
        run_id="run-1", turn_id="turn-1", session_id="session-1",
        tenant_id="tenant-a", user_id="user-a", execution_mode="dry_run",
    )
    assert not first.start_run(
        run_id="run-1", turn_id="turn-1", session_id="session-1",
        tenant_id="tenant-a", user_id="user-a", execution_mode="dry_run",
    )
    assert first.append_event("run-1", {
        "seq": 1, "type": "tool_result", "access_token": "never-store-this",
    })
    assert first.append_event("run-1", {
        "seq": 1, "type": "assistant_message", "text": "done",
    })
    assert first.finish_run(
        "run-1", status="succeeded", metadata={"refresh_token": "also-secret"},
    )
    first.close()

    second = SQLiteRunStore(path)
    try:
        run = second.get_run("run-1", tenant_id="tenant-a", user_id="user-a")
        assert run["status"] == "succeeded"
        assert run["metadata"]["refresh_token"] == "<redacted>"
        assert second.get_run("run-1", tenant_id="tenant-b") is None
        events = second.list_run_events("run-1", tenant_id="tenant-a", user_id="user-a")
        assert [entry["seq"] for entry in events] == [1, 2]
        assert events[0]["event"]["access_token"] == "<redacted>"
        serialized = json.dumps({"run": run, "events": events})
        assert "never-store-this" not in serialized
        assert "also-secret" not in serialized
        assert not second.append_event("run-1", {"type": "late_event"})
    finally:
        second.close()


def test_run_store_requires_run_start_before_events_and_finish(tmp_path):
    store = SQLiteRunStore(tmp_path / "missing.sqlite3")
    try:
        assert not store.append_event("missing", {"seq": 1, "type": "event"})
        assert not store.finish_run("missing", status="failed")
        assert store.list_run_events("missing") == []
    finally:
        store.close()
