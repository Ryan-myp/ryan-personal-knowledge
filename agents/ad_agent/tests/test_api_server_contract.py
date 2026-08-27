"""HTTP contract tests for the ad-agent ASGI entrypoint.

These tests replace the Runtime with a local fake and never create Provider
clients or call an external advertising API.
"""

import pytest

from fastapi.testclient import TestClient

from agents.ad_agent import api_server


class FakeRegistry:
    def list_all(self):
        return []

    def list_all_platforms(self):
        return []


class FakeRuntime:
    execution_mode = "dry_run"

    def __init__(self):
        self.registry = FakeRegistry()
        self.calls = []

    def run(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "success": True,
            "reply": "local fake response",
            "results": [],
        }


@pytest.fixture
def fake_server(monkeypatch):
    fake = FakeRuntime()
    monkeypatch.setattr(api_server, "runtime", fake)
    monkeypatch.setattr(api_server, "API_KEY", "test-key")
    monkeypatch.setattr(api_server, "ALLOW_UNAUTHENTICATED", False)
    return fake


def test_health_is_safe_and_does_not_require_api_key(fake_server):
    with TestClient(api_server.app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["execution_mode"] == "dry_run"


def test_chat_requires_api_key(fake_server):
    with TestClient(api_server.app) as client:
        response = client.post("/chat", json={"user_input": "查询 Meta campaign"})
    assert response.status_code == 401
    assert fake_server.calls == []


def test_chat_forwards_request_to_runtime(fake_server):
    with TestClient(api_server.app) as client:
        response = client.post(
            "/chat",
            headers={"X-API-Key": "test-key"},
            json={
                "user_input": "查询 Meta campaign",
                "user_id": "u1",
                "account_id": "m1",
            },
        )
    assert response.status_code == 200
    assert response.json()["reply"] == "local fake response"
    assert fake_server.calls[0]["user_input"] == "查询 Meta campaign"
    assert fake_server.calls[0]["account_id"] == "m1"


def test_confirmed_chat_requires_confirmation_payload(fake_server):
    with TestClient(api_server.app) as client:
        response = client.post(
            "/chat",
            headers={"X-API-Key": "test-key"},
            json={"user_input": "更新 Meta campaign", "confirmed": True},
        )
    assert response.status_code == 400
    assert fake_server.calls == []


def test_chat_stream_returns_sse_lifecycle_events(fake_server):
    with TestClient(api_server.app) as client:
        response = client.post(
            "/chat/stream",
            headers={"X-API-Key": "test-key"},
            json={"user_input": "查询 Meta campaign"},
        )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    body = response.text
    assert '"type": "start"' in body
    assert '"type": "reply"' in body
    assert '"type": "done"' in body
