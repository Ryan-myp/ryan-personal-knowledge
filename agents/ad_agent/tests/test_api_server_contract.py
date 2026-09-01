"""HTTP contract tests for the ad-agent ASGI entrypoint.

These tests replace the Runtime with a local fake and never create Provider
clients or call an external advertising API.
"""

import json

import pytest

from fastapi.testclient import TestClient

from agents.ad_agent import api_server


def test_local_env_file_is_loaded_without_overriding_process_environment(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "# comment\n"
        "export TEST_AD_AGENT_LOCAL=from-file\n"
        "TEST_AD_AGENT_QUOTED='quoted value'\n"
        "TEST_AD_AGENT_EXISTING=from-file\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("TEST_AD_AGENT_EXISTING", "from-process")

    api_server.load_local_env_file(env_file)

    assert api_server.os.environ["TEST_AD_AGENT_LOCAL"] == "from-file"
    assert api_server.os.environ["TEST_AD_AGENT_QUOTED"] == "quoted value"
    assert api_server.os.environ["TEST_AD_AGENT_EXISTING"] == "from-process"


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
        self.parameter_option_calls = []

    def run(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "success": True,
            "reply": "local fake response",
            "results": [],
        }

    def resolve_parameter_options(self, **kwargs):
        self.parameter_option_calls.append(kwargs)
        return {
            "tool_name": kwargs["tool_name"],
            "field": kwargs["field"],
            "options": [{"value": "app-1", "label": "Demo App"}],
        }

    def list_ad_formats(self, platform=None, coverage=None):
        return [{
            "format_id": "demo",
            "platform": platform or "demo",
            "coverage": coverage or "declared_only",
        }]

    def list_plugins(self, tenant_id=None):
        return [{
            "manifest": {
                "plugin_id": "renderer:ad-agent",
                "source": "builtin",
                "metadata": {},
            },
            "state": "active",
        }]


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


def test_plugins_exposes_only_safe_lifecycle_metadata(fake_server):
    with TestClient(api_server.app) as client:
        response = client.get("/plugins", headers={"X-API-Key": "test-key"})
    assert response.status_code == 200
    assert response.json()["plugins"][0]["state"] == "active"
    assert "contribution" not in response.json()["plugins"][0]


def test_skill_management_ui_covers_standard_package_lifecycle(fake_server):
    """Keep the shipped UI aligned with the tenant-scoped Skill API surface."""
    with TestClient(api_server.app) as client:
        response = client.get("/")

    assert response.status_code == 200
    html = response.text
    for marker in (
        "Skills 管理", "SKILL.md", "references/", "scripts/", "assets/", "evals/",
        "保存为新版本", "ZIP 导入", "Skill-up 评测", "发布 / 回滚", "下线",
        "/skills?limit=200", "/versions/archive", "/evaluate", "/evaluations/",
        "X-API-Key", "let streamError = ''", "streamError || '事件流未返回最终回复'",
        "最近对话", "服务已连接", "grid-template-columns: 68px minmax(0, 1fr) minmax(320px, 360px)",
    ):
        assert marker in html
    # The browser may hold the service API key in memory, but the page must
    # never offer fields or examples for advertising-provider credentials.
    for forbidden in ("access_token", "refresh_token", "client_secret", "developer_token"):
        assert forbidden not in html


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
    assert fake_server.calls[0]["principal"].user_id == "ad-agent-service"
    assert "user_id" not in fake_server.calls[0]


def test_chat_page_does_not_turn_http_errors_into_operation_complete(fake_server):
    html = api_server.TEMPLATE_PATH.read_text(encoding="utf-8")
    assert "if (!response.ok)" in html
    assert "data.detail || data.error" in html


def test_api_key_principal_replaces_request_user_id(monkeypatch, fake_server):
    monkeypatch.setenv(
        "AD_AGENT_API_KEY_PRINCIPALS",
        json.dumps({
            "scoped-key": {
                "user_id": "gateway-user",
                "tenant_id": "tenant-a",
                "permissions": ["ads.read"],
                "account_scope": {"meta": ["m1"]},
            }
        }),
    )
    with TestClient(api_server.app) as client:
        response = client.post(
            "/chat",
            headers={"X-API-Key": "scoped-key"},
            json={
                "user_input": "查询 Meta campaign",
                "user_id": "forged-user",
                "account_id": "m1",
            },
        )
    assert response.status_code == 200
    principal = fake_server.calls[0]["principal"]
    assert principal.user_id == "gateway-user"
    assert principal.tenant_id == "tenant-a"
    assert principal.allows_account("meta", "m1") is True


def test_reconcile_endpoint_requires_recovery_permission(monkeypatch, fake_server):
    monkeypatch.setenv(
        "AD_AGENT_API_KEY_PRINCIPALS",
        json.dumps({
            "read-only-key": {
                "user_id": "gateway-user",
                "tenant_id": "tenant-a",
                "permissions": ["ads.read"],
                "account_scope": {"meta": ["m1"]},
            }
        }),
    )
    with TestClient(api_server.app) as client:
        response = client.post(
            "/workflows/w1/reconcile",
            headers={"X-API-Key": "read-only-key"},
            json={"observations": [{"sequence": 1, "status": "unknown", "verified": True}]},
        )
    assert response.status_code == 403
    assert fake_server.calls == []


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


def test_chat_stream_forwards_runtime_events_without_inventing_steps(fake_server):
    def run(**kwargs):
        observe = kwargs["event_callback"]
        observe({"type": "start", "event_type": "start", "status": "running"})
        observe({
            "type": "plan", "event_type": "plan", "status": "planned",
            "execution_plan": {
                "schema_version": "1.0", "intent_type": "list_campaigns",
                "nodes": [{
                    "node_id": "node-0001", "platform": "meta",
                    "tool": "meta.list_campaigns", "action": "list",
                    "resource_type": "campaign", "depends_on": [],
                }],
            },
        })
        observe({
            "type": "node_started", "event_type": "node_started",
            "node_id": "node-0001", "platform": "meta",
            "tool": "meta.list_campaigns", "status": "running",
        })
        observe({
            "type": "node_status", "event_type": "node_status",
            "node_id": "node-0001", "platform": "meta",
            "tool": "meta.list_campaigns", "status": "succeeded",
        })
        observe({"type": "done", "event_type": "done", "status": "succeeded"})
        return {
            "session_id": "s1", "turn_id": "t1", "reply": "完成",
            "results": [{"tool": "meta.list_campaigns", "platform": "meta", "success": True}],
        }

    fake_server.run = run
    with TestClient(api_server.app) as client:
        response = client.post(
            "/chat/stream",
            headers={"X-API-Key": "test-key"},
            json={"user_input": "查询 Meta campaign"},
        )
    body = response.text
    assert '"node_id": "node-0001"' in body
    assert '"type": "thinking"' not in body
    assert '"type": "tool_status"' not in body
    assert body.index('"type": "node_started"') < body.index('"type": "reply"') < body.index('"type": "done"')


def test_chat_stream_exposes_runtime_error_event(fake_server):
    def run(**kwargs):
        raise RuntimeError("provider request failed")

    fake_server.run = run
    with TestClient(api_server.app) as client:
        response = client.post(
            "/chat/stream",
            headers={"X-API-Key": "test-key"},
            json={"user_input": "查询 Meta campaign"},
        )
    assert response.status_code == 200
    assert '"type": "error"' in response.text
    assert "provider request failed" in response.text
    assert '"type": "done"' in response.text


def test_runtime_initialization_registers_all_builtin_capabilities(monkeypatch, tmp_path):
    monkeypatch.setenv("AD_AGENT_DB_PATH", str(tmp_path / "runtime.db"))
    monkeypatch.setenv("OPENAI_API_KEY", "test-llm-key")
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
    assert len(runtime.registry.list_all()) >= 124
    runtime._session_manager.store.close()


def test_runtime_initialization_fails_without_llm(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("AD_AGENT_DB_PATH", str(tmp_path / "runtime.db"))
    monkeypatch.setattr(api_server, "runtime", None)
    monkeypatch.setattr(
        api_server,
        "runtime_status",
        {"state": "not_initialized", "error": None},
    )

    assert api_server._init_runtime() is None
    assert api_server.runtime_status["state"] == "failed"
    assert "必须配置 LLM" in api_server.runtime_status["error"]


def test_tools_endpoint_exposes_parameter_schema_and_enum_catalog(monkeypatch):
    from agents.ad_agent import AgentRuntime
    from agents.ad_agent.capabilities.tiktok import create_tiktok_capability

    runtime = AgentRuntime(require_llm=False, offline_mode=True)
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

    runtime = AgentRuntime(require_llm=False, offline_mode=True)
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


def test_parameter_options_resolve_uses_authenticated_principal(monkeypatch, fake_server):
    monkeypatch.setenv(
        "AD_AGENT_API_KEY_PRINCIPALS",
        json.dumps({
            "scoped-key": {
                "user_id": "gateway-user",
                "tenant_id": "tenant-a",
                "permissions": ["ads.read"],
                "account_scope": {"tiktok": ["t1"]},
            }
        }),
    )
    with TestClient(api_server.app) as client:
        response = client.get(
            "/parameter-options/resolve",
            headers={"X-API-Key": "scoped-key"},
            params={
                "platform": "tiktok",
                "field": "app_id",
                "tool_name": "tiktok_create_adgroup",
                "account_id": "t1",
                "session_id": "selection-session",
            },
        )

    assert response.status_code == 200
    assert response.json()["options"][0]["value"] == "app-1"
    call = fake_server.parameter_option_calls[0]
    assert call["user_id"] == "gateway-user"
    assert call["tenant_id"] == "tenant-a"
    assert call["account_scope"] == {"tiktok": frozenset({"t1"})}
    assert call["granted_permissions"] == frozenset({"ads.read"})


def test_ad_formats_endpoint_exposes_metadata_only(fake_server):
    with TestClient(api_server.app) as client:
        response = client.get(
            "/ad-formats",
            headers={"X-API-Key": "test-key"},
            params={"platform": "tiktok", "coverage": "partial_dry_run"},
        )

    assert response.status_code == 200
    assert response.json()["formats"][0]["format_id"] == "demo"


def test_parameter_options_resolve_requires_account_id(fake_server):
    with TestClient(api_server.app) as client:
        response = client.get(
            "/parameter-options/resolve",
            headers={"X-API-Key": "test-key"},
            params={
                "platform": "tiktok",
                "field": "app_id",
                "tool_name": "tiktok_create_adgroup",
            },
        )
    assert response.status_code == 422
    assert fake_server.parameter_option_calls == []


def test_managed_skill_api_versions_and_publishing_are_tenant_scoped(monkeypatch, tmp_path):
    from agents.ad_agent import AgentRuntime
    from agents.ad_agent.persistence.store import AdAgentStore

    store = AdAgentStore(str(tmp_path / "skills.db"))
    managed_runtime = AgentRuntime(require_llm=False, persistence_store=store, offline_mode=True)
    monkeypatch.setattr(api_server, "runtime", managed_runtime)
    monkeypatch.setattr(api_server, "API_KEY", "")
    monkeypatch.setattr(api_server, "ALLOW_UNAUTHENTICATED", False)
    monkeypatch.setenv(
        "AD_AGENT_API_KEY_PRINCIPALS",
        json.dumps({
            "skill-key": {
                "user_id": "editor",
                "tenant_id": "tenant-a",
                "permissions": ["skills.read", "skills.write"],
            }
        }),
    )
    files = {
        "SKILL.md": (
            "---\nname: growth-skill\ndescription: Growth guidance\n"
            "platform: multi_platform\n---\n\nUse safe planning.\n"
        ),
        "scripts/check.py": "print('package file')\n",
        "assets/logo.bin": {"encoding": "base64", "content": "AAEC"},
    }
    headers = {"X-API-Key": "skill-key"}

    with TestClient(api_server.app) as client:
        response = client.post(
            "/skills/growth-skill/versions",
            headers=headers,
            json={"version": "1.0.0", "files": files},
        )
        assert response.status_code == 201
        assert response.json()["files"] == sorted(files)

        response = client.get("/skills/growth-skill/versions/1.0.0", headers=headers)
        assert response.status_code == 200
        assert response.json()["files"]["assets/logo.bin"]["encoding"] == "base64"

        response = client.post(
            "/skills/growth-skill/versions/1.0.0/publish", headers=headers
        )
        assert response.status_code == 200
        assert response.json()["status"] == "published"

        response = client.get("/skills", headers=headers)
        assert response.status_code == 200
        assert response.json()["skills"][0]["status"] == "published"

    assert "growth-skill" in managed_runtime.get_managed_skills()
    assert managed_runtime.registry.list_all() == []
    store.close()


def test_chat_activates_published_skill_for_authenticated_request_tenant(monkeypatch, tmp_path):
    from agents.ad_agent import AgentRuntime
    from agents.ad_agent.core.interfaces import ParsedIntent
    from agents.ad_agent.persistence.store import AdAgentStore
    from agents.ad_agent.skill_management import ManagedSkillManager

    store = AdAgentStore(str(tmp_path / "multi-tenant-skills.db"))
    managed_runtime = AgentRuntime(
        require_llm=False, persistence_store=store, offline_mode=True
    )
    manager = ManagedSkillManager(store)
    manager.create_version(
        "tenant-b",
        "tenant-guidance",
        "1.0.0",
        {
            "SKILL.md": (
                "---\nname: tenant-guidance\ndescription: Tenant guidance\n"
                "platform: multi_platform\n---\n\nUse the tenant policy.\n"
            )
        },
        "editor",
    )
    manager.publish("tenant-b", "tenant-guidance", "1.0.0")

    class Parser:
        def __init__(self):
            self.context = None

        def parse(self, _text, context):
            self.context = context.metadata.get("skill_context", {})
            return ParsedIntent("chat", "查询广告", [])

    parser = Parser()
    managed_runtime.intent_parser = parser
    monkeypatch.setattr(api_server, "runtime", managed_runtime)
    monkeypatch.setattr(api_server, "API_KEY", "tenant-key")
    monkeypatch.setattr(api_server, "ALLOW_UNAUTHENTICATED", False)
    monkeypatch.setenv(
        "AD_AGENT_API_KEY_PRINCIPALS",
        json.dumps({
            "tenant-key": {
                "user_id": "tenant-user",
                "tenant_id": "tenant-b",
                "permissions": ["ads.read"],
            }
        }),
    )

    with TestClient(api_server.app) as client:
        response = client.post(
            "/chat",
            headers={"X-API-Key": "tenant-key"},
            json={"user_input": "查询广告"},
        )

    assert response.status_code == 200
    assert parser.context is not None
    assert "tenant-guidance" in parser.context.get("expert_knowledge", "")
    assert "tenant-guidance" in managed_runtime.get_managed_skills("tenant-b")
    assert manager.activate_published("tenant-b", managed_runtime) == 0
    store.close()
