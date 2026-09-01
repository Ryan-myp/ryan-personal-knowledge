"""HTTP task contract tests with local Runtime only."""

import json
import time

from fastapi.testclient import TestClient

from agents.ad_agent import AdAgentStore, AgentRuntime
from agents.ad_agent import api_server


def _wait_terminal(client, task_id, headers):
    for _ in range(100):
        response = client.get(f"/tasks/{task_id}", headers=headers)
        if response.status_code == 200 and response.json()["status"] in {
            "succeeded", "failed", "cancelled", "recovery_required",
        }:
            return response
        time.sleep(0.01)
    return response


def test_task_api_queues_runtime_turn_and_returns_result(monkeypatch):
    runtime = AgentRuntime(
        require_llm=False,
        persistence_store=AdAgentStore(":memory:"),
        enforce_account_scope=False,
    )
    monkeypatch.setattr(api_server, "runtime", runtime)
    monkeypatch.setattr(api_server, "API_KEY", "task-key")
    monkeypatch.setattr(api_server, "ALLOW_UNAUTHENTICATED", False)
    monkeypatch.delenv("AD_AGENT_API_KEY_PRINCIPALS", raising=False)

    with TestClient(api_server.app) as client:
        response = client.post(
            "/tasks",
            headers={"X-API-Key": "task-key", "Idempotency-Key": "turn-1"},
            json={"kind": "agent.turn", "payload": {"user_input": "你好"}},
        )
        assert response.status_code == 202
        task = response.json()["task"]
        assert task["kind"] == "agent.turn"
        assert task["tenant_id"] == "default"
        assert "credentials" not in json.dumps(task)
        listed = client.get("/tasks", headers={"X-API-Key": "task-key"})
        assert listed.status_code == 200
        assert listed.json()["tasks"][0]["task_id"] == task["task_id"]

        duplicate = client.post(
            "/tasks",
            headers={"X-API-Key": "task-key"},
            json={
                "kind": "agent.turn", "idempotency_key": "turn-1",
                "payload": {"user_input": "different input"},
            },
        )
        assert duplicate.status_code == 202
        assert duplicate.json()["created"] is False
        assert duplicate.json()["task"]["task_id"] == task["task_id"]

        final = _wait_terminal(
            client, task["task_id"], {"X-API-Key": "task-key"}
        )
        assert final.status_code == 200
        assert final.json()["status"] == "succeeded"
    runtime.task_executor.shutdown()


def test_task_api_rejects_credentials_and_enforces_principal_scope(monkeypatch):
    runtime = AgentRuntime(
        require_llm=False,
        persistence_store=AdAgentStore(":memory:"),
        enforce_account_scope=False,
    )
    monkeypatch.setattr(api_server, "runtime", runtime)
    monkeypatch.setattr(api_server, "API_KEY", "")
    monkeypatch.setattr(api_server, "ALLOW_UNAUTHENTICATED", False)
    monkeypatch.setenv(
        "AD_AGENT_API_KEY_PRINCIPALS",
        json.dumps({
            "owner-key": {
                "user_id": "owner", "tenant_id": "tenant-a",
                "permissions": ["ads.read", "ads.plan"],
            },
            "other-key": {
                "user_id": "other", "tenant_id": "tenant-b",
                "permissions": ["ads.read", "ads.plan"],
            },
        }),
    )

    with TestClient(api_server.app) as client:
        rejected = client.post(
            "/tasks", headers={"X-API-Key": "owner-key"},
            json={
                "kind": "agent.turn",
                "payload": {"user_input": "query", "credentials": {"token": "secret"}},
            },
        )
        assert rejected.status_code == 422

        created = client.post(
            "/tasks", headers={"X-API-Key": "owner-key"},
            json={"payload": {"user_input": "你好"}},
        )
        assert created.status_code == 202
        task_id = created.json()["task"]["task_id"]
        hidden = client.get(f"/tasks/{task_id}", headers={"X-API-Key": "other-key"})
        assert hidden.status_code == 404
    runtime.task_executor.shutdown()
