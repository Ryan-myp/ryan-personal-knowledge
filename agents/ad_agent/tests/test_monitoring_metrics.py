"""Regression coverage for the durable monitoring snapshot and its HTTP seam."""

from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from agents.ad_agent import AdAgentStore, AgentRuntime
from agents.ad_agent import api_server
from agents.ad_agent.persistence.models import ExecutionRunRecord, TaskRecord, ToolCallRecord


def test_monitoring_snapshot_reports_queue_lease_recovery_and_scope():
    store = AdAgentStore(":memory:")
    now = datetime.now()
    old = (now - timedelta(minutes=8)).isoformat()
    store.create_task(TaskRecord(
        task_id="queued-visible", tenant_id="tenant-a", user_id="user-a",
        kind="agent.turn", status="queued", created_at=old, updated_at=old,
    ))
    store.create_task(TaskRecord(
        task_id="running-visible", tenant_id="tenant-a", user_id="user-a",
        kind="agent.turn", status="running", created_at=old, updated_at=old,
        lease_owner="worker-a", lease_expires_at=old,
    ))
    store.create_task(TaskRecord(
        task_id="recovery-hidden", tenant_id="tenant-b", user_id="user-b",
        kind="agent.turn", status="recovery_required", created_at=old, updated_at=old,
    ))
    store.create_session("session-a", "user-a", metadata={"tenant_id": "tenant-a"})
    tool_started = (now - timedelta(minutes=2)).isoformat()
    tool_ended = (now - timedelta(minutes=1, seconds=59)).isoformat()
    store.record_tool_call(ToolCallRecord(
        id="tool-visible", session_id="session-a", turn_id="turn-a",
        tool_name="meta_list_accounts", platform="meta", input_data={},
        output_data={}, started_at=tool_started, ended_at=tool_ended,
    ))
    store.create_execution_run(ExecutionRunRecord(
        run_id="run-visible", session_id="session-a", turn_id="turn-a",
        user_id="user-a", tenant_id="tenant-a", status="recovery_required",
        created_at=old, updated_at=old,
    ))

    snapshot = store.get_monitoring_snapshot(
        tenant_id="tenant-a", user_id="user-a", stale_after_seconds=300,
    )

    assert snapshot["tasks"]["queued_depth"] == 1
    assert snapshot["tasks"]["queued_oldest_age_seconds"] >= 8 * 60
    assert snapshot["tasks"]["leases"]["expired"] == 1
    assert snapshot["tasks"]["stale_running"] == 1
    assert snapshot["runs"]["by_status"]["recovery_required"] == 1
    assert snapshot["alerts"]["recovery_required"] == 1
    assert snapshot["status"] == "critical"
    assert snapshot["tools"]["total"] == 1
    assert len(snapshot["tools"]["timeline"]) == 12
    assert sum(item["calls"] for item in snapshot["tools"]["timeline"]) == 1
    assert any(item["avg_latency_ms"] is not None for item in snapshot["tools"]["timeline"])

    unscoped = store.get_monitoring_snapshot()
    assert unscoped["tasks"]["by_status"]["recovery_required"] == 1
    store.close()


def test_monitoring_http_endpoint_is_authenticated_and_scoped(monkeypatch):
    runtime = AgentRuntime(
        require_llm=False,
        persistence_store=AdAgentStore(":memory:"),
        enforce_account_scope=False,
    )
    monkeypatch.setattr(api_server, "runtime", runtime)
    monkeypatch.setattr(api_server, "API_KEY", "monitor-key")
    monkeypatch.setattr(api_server, "ALLOW_UNAUTHENTICATED", False)
    try:
        with TestClient(api_server.app) as client:
            unauthorized = client.get("/monitoring/overview")
            assert unauthorized.status_code == 401
            response = client.get(
                "/monitoring/overview", headers={"X-API-Key": "monitor-key"}
            )
            assert response.status_code == 200
            payload = response.json()
            assert payload["backend"] == "sqlite"
            assert payload["scope"] == {"tenant_id": "default", "user_id": "ad-agent-service"}
            assert "instance" in payload
            assert "tasks" in payload and "outbox" in payload and "tools" in payload
            assert "backend_health" in payload
    finally:
        if api_server.runtime is runtime:
            runtime.close(wait=True)
        monkeypatch.setattr(api_server, "runtime", None)
