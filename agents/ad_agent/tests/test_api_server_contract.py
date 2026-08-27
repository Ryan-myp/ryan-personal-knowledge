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


def test_runtime_initialization_registers_all_builtin_capabilities(monkeypatch, tmp_path):
    monkeypatch.setenv("AD_AGENT_DB_PATH", str(tmp_path / "runtime.db"))
    monkeypatch.setattr(api_server, "runtime", None)
    monkeypatch.setattr(
        api_server,
        "runtime_status",
        {"state": "not_initialized", "error": None},
    )

    runtime = api_server._init_runtime()

    assert runtime is not None
    assert api_server.runtime_status["state"] == "ready"
    assert set(runtime.registry.list_all_platforms()) == {
        "meta", "google-ads", "tiktok", "dv360"
    }
    assert len(runtime.registry.list_all()) == 72
    runtime._session_manager.store.close()


def test_tools_endpoint_exposes_parameter_schema_and_enum_catalog(monkeypatch):
    from agents.ad_agent import AgentRuntime
    from agents.ad_agent.capabilities.tiktok import create_tiktok_capability

    runtime = AgentRuntime(offline_mode=True)
    runtime.register_capability(create_tiktok_capability())
    monkeypatch.setattr(api_server, "runtime", runtime)
    monkeypatch.setattr(api_server, "API_KEY", "test-key")
    monkeypatch.setattr(api_server, "ALLOW_UNAUTHENTICATED", False)

    with TestClient(api_server.app) as client:
        response = client.get("/tools", headers={"X-API-Key": "test-key"})

    assert response.status_code == 200
    tools = {item["name"]: item for item in response.json()["tools"]}
    adgroup_schema = tools["tiktok_create_adgroup"]["input_schema"]
    assert "APP_ANDROID" in adgroup_schema["properties"]["promotion_type"]["enum"]
    assert adgroup_schema["properties"]["app_id"]["lookup_tool"] == "tiktok_list_apps"
    assert adgroup_schema["conditional_rules"]


def test_parameter_options_endpoint_can_scope_same_field_to_tool(monkeypatch):
    from agents.ad_agent import AgentRuntime
    from agents.ad_agent.capabilities.tiktok import create_tiktok_capability

    runtime = AgentRuntime(offline_mode=True)
    runtime.register_capability(create_tiktok_capability())
    monkeypatch.setattr(api_server, "runtime", runtime)
    monkeypatch.setattr(api_server, "API_KEY", "test-key")
    monkeypatch.setattr(api_server, "ALLOW_UNAUTHENTICATED", False)

    with TestClient(api_server.app) as client:
        response = client.get(
            "/parameter-options",
            headers={"X-API-Key": "test-key"},
            params={
                "platform": "tiktok",
                "field": "budget_mode",
                "tool_name": "tiktok_create_adgroup",
            },
        )

    assert response.status_code == 200
    options = response.json()["options"]
    assert len(options) == 1
    assert options[0]["tool_name"] == "tiktok_create_adgroup"
    assert "BUDGET_MODE_TOTAL" not in {
        item["value"] for item in options[0]["options"]
    }
