"""HTTP contract tests for the ad-agent ASGI entrypoint.

These tests replace the Runtime with a local fake and never create Provider
clients or call an external advertising API.
"""

import json

import pytest

from fastapi.testclient import TestClient

from agents.ad_agent import api_server


def _chat_page_javascript() -> str:
    """Read the bootstrap and split bundles as one browser contract."""
    names = [
        "chat.js", "chat-state.js", "chat-workbench.js", "chat-workspace.js", "chat-knowledge.js",
        "chat-trace.js", "chat-requests.js", "chat-blueprint-core.js",
        "chat-blueprint-editor.js", "chat-skills.js", "chat-creation.js",
        "chat-messages.js",
    ]
    return "\n".join(
        (api_server.STATIC_PATH / "js" / name).read_text(encoding="utf-8")
        for name in names
    )


def _chat_page_styles() -> str:
    """Read the CSS bootstrap and split bundles as one browser contract."""
    names = [
        "chat.css", "chat-foundation.css", "chat-workspaces.css",
        "chat-creation.css", "chat-overrides.css",
    ]
    return "\n".join(
        (api_server.STATIC_PATH / "css" / name).read_text(encoding="utf-8")
        for name in names
    )


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
    allow_live_writes = False
    _read_only_mode = False

    def __init__(self):
        self.registry = FakeRegistry()
        self.calls = []
        self.recovery_calls = []
        self.parameter_option_calls = []
        self.execution_mode = "dry_run"
        self.allow_live_writes = False
        self._read_only_mode = False

    def set_execution_mode(self, mode):
        if mode not in {"dry_run", "live"}:
            raise ValueError(f"Unsupported execution_mode: {mode}")
        self.execution_mode = mode

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

    def list_creation_blueprints(self, provider=None, ad_format=None, selector_dimension=None, selector_value=None):
        return [{
            "id": "demo.search",
            "provider": provider or "google-ads",
            "ad_format": ad_format or "SEARCH",
            "selector": {"dimension": "ad_format", "field": "campaign.advertising_channel_type", "values": ["SEARCH"]},
        }]

    def resolve_creation_blueprint(self, provider, *, selector_values=None, values=None, version=None):
        if (selector_values or {}).get("ad_format") != "SEARCH":
            return None
        return {
            "id": "demo.search",
            "provider": provider,
            "ad_format": "SEARCH",
            "version": version or "1.0.0",
        }

    def list_plugins(self, tenant_id=None):
        return [{
            "manifest": {
                "plugin_id": "renderer:ad-agent",
                "source": "builtin",
                "metadata": {},
            },
            "state": "active",
        }]

    def recover_task(self, task_id, **kwargs):
        self.recovery_calls.append((task_id, kwargs))
        if kwargs["tenant_id"] != "tenant-a":
            return None
        if not kwargs["provider_verified"]:
            raise ValueError("provider_verified=true is required before task recovery")
        return {"task_id": task_id, "status": "queued"}


@pytest.fixture
def fake_server(monkeypatch):
    fake = FakeRuntime()
    monkeypatch.setattr(api_server, "runtime", fake)
    monkeypatch.setattr(api_server, "API_KEY", "test-key")
    monkeypatch.setattr(api_server, "ALLOW_UNAUTHENTICATED", False)
    return fake


def test_health_is_safe_and_does_not_require_api_key(fake_server, monkeypatch):
    monkeypatch.delenv("AD_AGENT_ENABLE_LIVE", raising=False)
    with TestClient(api_server.app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["execution_mode"] == "dry_run"
    assert payload["execution_mode_options"] == ["dry_run", "live"]
    assert payload["live_mode_available"] is False
    assert payload["live_mode_reason"] == "服务未开启 live 环境开关"


def test_execution_mode_read_uses_authenticated_principal_scope(fake_server, monkeypatch):
    fake_server.get_execution_mode = lambda tenant_id=None, user_id=None: (
        "live" if (tenant_id, user_id) == ("tenant-a", "operator") else "dry_run"
    )
    monkeypatch.setenv(
        "AD_AGENT_API_KEY_PRINCIPALS",
        json.dumps({
            "operator-key": {
                "user_id": "operator",
                "tenant_id": "tenant-a",
                "permissions": ["ads.plan"],
            }
        }),
    )
    with TestClient(api_server.app) as client:
        response = client.get(
            "/settings/execution-mode", headers={"X-API-Key": "operator-key"}
        )
    assert response.status_code == 200
    assert response.json()["mode"] == "live"
    assert response.json()["live_mode_reason"] == "服务未开启 live 环境开关"


def test_execution_mode_read_reports_principal_live_permission_gap(fake_server, monkeypatch):
    fake_server.allow_live_writes = True
    monkeypatch.setenv("AD_AGENT_ENABLE_LIVE", "1")
    monkeypatch.setenv(
        "AD_AGENT_API_KEY_PRINCIPALS",
        json.dumps({
            "plan-key": {
                "user_id": "planner",
                "tenant_id": "tenant-a",
                "permissions": ["ads.plan"],
            }
        }),
    )
    with TestClient(api_server.app) as client:
        response = client.get(
            "/settings/execution-mode", headers={"X-API-Key": "plan-key"}
        )
    assert response.status_code == 200
    assert response.json()["live_mode_available"] is False
    assert response.json()["live_mode_reason"] == "当前身份缺少 live 执行权限：ads.write"


def test_readiness_exposes_model_and_runtime_gate_without_provider_calls(fake_server):
    fake_server.registry.list_all = lambda: [object()]
    with TestClient(api_server.app) as client:
        response = client.get("/readyz")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["checks"]["runtime"] is True
    assert payload["checks"]["llm"] is True
    assert payload["checks"]["tool_registry"] is True


def test_readiness_rejects_missing_required_model(fake_server):
    fake_server.registry.list_all = lambda: [object()]
    fake_server.require_llm = True
    fake_server._llm = None
    with TestClient(api_server.app) as client:
        response = client.get("/readyz")
    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"
    assert response.json()["checks"]["llm"] is False


def test_execution_mode_change_requires_planning_permission(monkeypatch, fake_server):
    monkeypatch.setenv(
        "AD_AGENT_API_KEY_PRINCIPALS",
        json.dumps({
            "read-key": {
                "user_id": "reader",
                "tenant_id": "tenant-a",
                "permissions": ["ads.read"],
            }
        }),
    )
    with TestClient(api_server.app) as client:
        response = client.post(
            "/settings/execution-mode",
            headers={"X-API-Key": "read-key"},
            json={"mode": "dry_run"},
        )
    assert response.status_code == 403
    assert fake_server.execution_mode == "dry_run"


def test_task_recovery_api_enforces_proof_permission_and_tenant_scope(
    monkeypatch, fake_server,
):
    monkeypatch.setenv(
        "AD_AGENT_API_KEY_PRINCIPALS",
        json.dumps({
            "read-key": {
                "user_id": "reader", "tenant_id": "tenant-a",
                "permissions": ["ads.read"],
            },
            "reconcile-key": {
                "user_id": "operator", "tenant_id": "tenant-a",
                "permissions": ["ads.reconcile"],
            },
            "other-key": {
                "user_id": "other", "tenant_id": "tenant-b",
                "permissions": ["ads.reconcile"],
            },
        }),
    )
    with TestClient(api_server.app) as client:
        denied = client.post(
            "/tasks/task-1/recover", headers={"X-API-Key": "read-key"},
            json={"recovery_reference": "provider-readback-1", "provider_verified": True},
        )
        unverified = client.post(
            "/tasks/task-1/recover", headers={"X-API-Key": "reconcile-key"},
            json={"recovery_reference": "provider-readback-1"},
        )
        missing_reference = client.post(
            "/tasks/task-1/recover", headers={"X-API-Key": "reconcile-key"},
            json={"provider_verified": True},
        )
        recovered = client.post(
            "/tasks/task-1/recover", headers={"X-API-Key": "reconcile-key"},
            json={"recovery_reference": "provider-readback-1", "provider_verified": True},
        )
        hidden = client.post(
            "/tasks/task-1/recover", headers={"X-API-Key": "other-key"},
            json={"recovery_reference": "provider-readback-1", "provider_verified": True},
        )
    assert denied.status_code == 403
    assert unverified.status_code == 422
    assert missing_reference.status_code == 422
    assert recovered.status_code == 200
    assert recovered.json()["status"] == "queued"
    assert hidden.status_code == 404
    assert fake_server.recovery_calls[-1][1]["tenant_id"] == "tenant-b"


def test_execution_mode_switch_does_not_grant_live_write_permission(
    monkeypatch, fake_server
):
    fake_server.allow_live_writes = True
    monkeypatch.delenv("AD_AGENT_ENABLE_LIVE", raising=False)
    monkeypatch.setenv(
        "AD_AGENT_API_KEY_PRINCIPALS",
        json.dumps({
            "plan-key": {
                "user_id": "planner",
                "tenant_id": "tenant-a",
                "permissions": ["ads.plan"],
            },
            "write-key": {
                "user_id": "operator",
                "tenant_id": "tenant-a",
                "permissions": ["ads.plan", "ads.write"],
            },
        }),
    )
    with TestClient(api_server.app) as client:
        planner_can_select_live = client.post(
            "/settings/execution-mode",
            headers={"X-API-Key": "plan-key"},
            json={"mode": "live"},
        )
        writer_can_select_live = client.post(
            "/settings/execution-mode",
            headers={"X-API-Key": "write-key"},
            json={"mode": "live"},
        )
    assert planner_can_select_live.status_code == 200
    assert planner_can_select_live.json()["mode"] == "live"
    assert planner_can_select_live.json()["live_mode_available"] is False
    assert planner_can_select_live.json()["live_mode_reason"] == "服务未开启 live 环境开关"
    assert writer_can_select_live.status_code == 200
    assert writer_can_select_live.json()["mode"] == "live"
    assert fake_server.execution_mode == "live"


def test_execution_mode_can_switch_live_then_return_to_dry_run(monkeypatch, fake_server):
    fake_server.allow_live_writes = True
    monkeypatch.setenv("AD_AGENT_ENABLE_LIVE", "1")
    monkeypatch.setenv(
        "AD_AGENT_API_KEY_PRINCIPALS",
        json.dumps({
            "write-key": {
                "user_id": "operator",
                "tenant_id": "tenant-a",
                "permissions": ["ads.plan", "ads.write"],
            }
        }),
    )
    with TestClient(api_server.app) as client:
        live = client.post(
            "/settings/execution-mode",
            headers={"X-API-Key": "write-key"},
            json={"mode": "live"},
        )
        dry_run = client.post(
            "/settings/execution-mode",
            headers={"X-API-Key": "write-key"},
            json={"mode": "dry_run"},
        )
    assert live.status_code == 200
    assert live.json()["mode"] == "live"
    assert live.json()["live_mode_available"] is True
    assert "仍需账户、权限和二次确认" in live.json()["message"]
    assert dry_run.status_code == 200
    assert dry_run.json()["mode"] == "dry_run"
    assert fake_server.execution_mode == "dry_run"


def test_plugins_exposes_only_safe_lifecycle_metadata(fake_server):
    with TestClient(api_server.app) as client:
        response = client.get("/plugins", headers={"X-API-Key": "test-key"})
    assert response.status_code == 200
    assert response.json()["plugins"][0]["state"] == "active"
    assert "contribution" not in response.json()["plugins"][0]


def test_creation_blueprint_selector_endpoints_are_metadata_only(fake_server):
    with TestClient(api_server.app) as client:
        listing = client.get(
            "/creation-blueprints",
            headers={"X-API-Key": "test-key"},
            params={"provider": "google-ads", "selector_dimension": "ad_format", "selector_value": "SEARCH"},
        )
        resolved = client.post(
            "/creation-blueprints/resolve",
            headers={"X-API-Key": "test-key"},
            json={"provider": "google-ads", "selector_values": {"ad_format": "SEARCH"}},
        )
        missing = client.post(
            "/creation-blueprints/resolve",
            headers={"X-API-Key": "test-key"},
            json={"provider": "google-ads", "selector_values": {"ad_format": "VIDEO"}},
        )
    assert listing.status_code == 200
    assert listing.json()["blueprints"][0]["selector"]["dimension"] == "ad_format"
    assert resolved.status_code == 200
    assert resolved.json()["blueprint"]["id"] == "demo.search"
    assert missing.status_code == 404


def test_skill_management_ui_covers_standard_package_lifecycle(fake_server):
    """Keep the shipped UI aligned with the tenant-scoped Skill API surface."""
    with TestClient(api_server.app) as client:
        response = client.get("/")

    assert response.status_code == 200
    html = response.text + "\n" + _chat_page_javascript() + "\n" + _chat_page_styles()
    for marker in (
        "Skills 管理", "SKILL.md", "references/", "scripts/", "assets/", "evals/",
        "保存为新版本", "ZIP 导入", "Skill-up 评测", "发布 / 回滚", "下线",
        "/skills?limit=200", "/versions/archive", "/evaluate", "/evaluations/",
        "X-API-Key", "let streamError = ''", "streamError || '事件流未返回最终回复'",
            "最近对话", "服务已连接", "grid-template-columns: 228px minmax(0, 1fr) minmax(450px, 460px)",
        "global-action-label", "知识库", "/sessions?limit=50",
        "/sessions/${encodeURIComponent(targetSessionId)}?limit=500",
        "refreshConversationHistory", "loadConversation", "检索总结",
        "historyManageButton", "toggleHistorySelectionMode", "deleteSelectedConversations",
        "historySearchInput", "filterConversationHistory", "最近 7 天", "更早",
        "requestConversationDeletion", "openHistoryDeleteDialog", "confirmHistoryDeletion",
        "requestConversationRename", "confirmHistoryRename", "重命名对话", "method: 'PATCH'",
        "deleted_session_ids", "仅影响本地历史记录",
        "保存并发布", "/knowledge/documents", "formatKnowledgeMarkdown",
        "knowledgeOverlay", "knowledge-console", "内置 · 只读", "复制为新版本",
        "/skills/builtin/", "managed_skills", "builtin_skills",
        "knowledgeFileInput", "handleKnowledgeFileUpload", "/knowledge/raw",
        "waitForKnowledgeIngest", "view-hidden", "返回目录",
        "knowledgeCatalogToggle", "knowledge-reader-actions", "复制为我的草稿", "编辑文档", "管理文档",
        "knowledge-table-wrap", "knowledge-task", "knowledge-render-v3",
        "themeToggleButton", "light-theme", "ad-agent-theme", "toggleTheme",
        "executionModeSelect", "/settings/execution-mode", "live_mode_available",
        "live_mode_reason", "应用模式", "live · 受控执行", "handleWorkspaceModeChange",
        "系统运维", "systemOpsMenu", "toggleSystemOpsMenu", "运行监控", "/monitoring/overview", "monitoringTaskBars",
        "monitoringLeaseList", "Tool 调用审计", "当前实例",
        "sidebar > .new-chat-btn", "nav-icon", "blueprintOverlay",
        "!event.target.closest('.blueprint-overlay')",
        "closeBlueprintManager()", "event.stopPropagation()",
        "agentWorkbench", "workbench-tab-creation", "workbench-tab-trace",
        "openCreationWorkbench", "closeCreationWorkbench",
        "reopenCreationCard", "creation-workbench-host",
        "message-card-launcher", "右侧工作区",
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


def test_session_endpoints_use_authenticated_user_and_tenant_scope(monkeypatch, fake_server):
    monkeypatch.setenv(
        "AD_AGENT_API_KEY_PRINCIPALS",
        json.dumps({
            "scoped-key": {
                "user_id": "gateway-user",
                "tenant_id": "tenant-a",
                "permissions": ["ads.read"],
            }
        }),
    )
    calls = []

    def list_conversations(**kwargs):
        calls.append(("list", kwargs))
        return [{
            "session_id": "session-a",
            "title": "查询 Meta 广告系列",
            "preview": "已找到 2 个广告系列",
            "message_count": 2,
        }]

    def get_conversation(**kwargs):
        calls.append(("get", kwargs))
        if kwargs["user_id"] != "gateway-user" or kwargs["tenant_id"] != "tenant-a":
            return None
        return {
            "session_id": kwargs["session_id"],
            "title": "查询 Meta 广告系列",
            "preview": "已找到 2 个广告系列",
            "message_count": 2,
            "messages": [
                {"role": "user", "content": "查询 Meta 广告系列"},
                {"role": "assistant", "content": "已找到 2 个广告系列"},
            ],
        }

    fake_server.list_conversations = list_conversations
    fake_server.get_conversation = get_conversation
    with TestClient(api_server.app) as client:
        listing = client.get("/sessions", headers={"X-API-Key": "scoped-key"})
        detail = client.get(
            "/sessions/session-a",
            headers={"X-API-Key": "scoped-key"},
            params={"user_id": "forged-user"},
        )

    assert listing.status_code == 200
    assert listing.json()["sessions"][0]["session_id"] == "session-a"
    assert detail.status_code == 200
    assert detail.json()["messages"][0]["content"] == "查询 Meta 广告系列"
    assert calls[0][1]["user_id"] == "gateway-user"
    assert calls[0][1]["tenant_id"] == "tenant-a"
    assert calls[1][1]["user_id"] == "gateway-user"
    assert calls[1][1]["tenant_id"] == "tenant-a"


def test_session_detail_hides_other_principal_sessions(monkeypatch, fake_server):
    monkeypatch.setenv(
        "AD_AGENT_API_KEY_PRINCIPALS",
        json.dumps({
            "scoped-key": {
                "user_id": "gateway-user",
                "tenant_id": "tenant-a",
                "permissions": ["ads.read"],
            }
        }),
    )
    fake_server.get_conversation = lambda **kwargs: None
    with TestClient(api_server.app) as client:
        response = client.get(
            "/sessions/not-owned",
            headers={"X-API-Key": "scoped-key"},
        )
    assert response.status_code == 404


def test_session_delete_endpoints_use_authenticated_user_and_tenant_scope(monkeypatch, fake_server):
    monkeypatch.setenv(
        "AD_AGENT_API_KEY_PRINCIPALS",
        json.dumps({
            "scoped-key": {
                "user_id": "gateway-user",
                "tenant_id": "tenant-a",
                "permissions": ["ads.read"],
            }
        }),
    )
    calls = []

    def delete_conversation(**kwargs):
        calls.append(("single", kwargs))
        return kwargs["user_id"] == "gateway-user" and kwargs["tenant_id"] == "tenant-a"

    def delete_conversations(**kwargs):
        calls.append(("batch", kwargs))
        return ["session-a", "session-b"]

    fake_server.delete_conversation = delete_conversation
    fake_server.delete_conversations = delete_conversations
    with TestClient(api_server.app) as client:
        single = client.delete(
            "/sessions/session-a", headers={"X-API-Key": "scoped-key"}
        )
        batch = client.request(
            "DELETE", "/sessions", headers={"X-API-Key": "scoped-key"},
            json={"session_ids": ["session-a", "session-b"]},
        )

    assert single.status_code == 200
    assert single.json() == {"deleted": True, "deleted_session_id": "session-a"}
    assert batch.status_code == 200
    assert batch.json()["deleted_session_ids"] == ["session-a", "session-b"]
    assert calls[0][1]["user_id"] == "gateway-user"
    assert calls[0][1]["tenant_id"] == "tenant-a"
    assert calls[1][1]["session_ids"] == ["session-a", "session-b"]
    assert calls[1][1]["user_id"] == "gateway-user"
    assert calls[1][1]["tenant_id"] == "tenant-a"


def test_session_rename_uses_authenticated_user_and_tenant_scope(monkeypatch, fake_server):
    monkeypatch.setenv(
        "AD_AGENT_API_KEY_PRINCIPALS",
        json.dumps({
            "scoped-key": {
                "user_id": "gateway-user",
                "tenant_id": "tenant-a",
                "permissions": ["ads.read"],
            }
        }),
    )
    calls = []

    def rename_conversation(**kwargs):
        calls.append(kwargs)
        return {
            "session_id": kwargs["session_id"],
            "title": kwargs["title"],
        }

    fake_server.rename_conversation = rename_conversation
    with TestClient(api_server.app) as client:
        response = client.patch(
            "/sessions/session-a",
            headers={"X-API-Key": "scoped-key"},
            json={"title": "Meta 广告系列报表"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "session_id": "session-a", "title": "Meta 广告系列报表"
    }
    assert calls[0]["user_id"] == "gateway-user"
    assert calls[0]["tenant_id"] == "tenant-a"


def test_knowledge_document_can_be_saved_as_draft_and_published(monkeypatch):
    from agents.ad_agent import AgentRuntime
    from agents.ad_agent.persistence.store import AdAgentStore

    store = AdAgentStore(":memory:")
    managed_runtime = AgentRuntime(
        require_llm=False, persistence_store=store, features=[]
    )
    monkeypatch.setattr(api_server, "runtime", managed_runtime)
    monkeypatch.setattr(api_server, "API_KEY", "knowledge-key")
    monkeypatch.setattr(api_server, "ALLOW_UNAUTHENTICATED", False)
    monkeypatch.setenv(
        "AD_AGENT_API_KEY_PRINCIPALS",
        json.dumps({
            "knowledge-key": {
                "user_id": "knowledge-user",
                "tenant_id": "tenant-a",
                "permissions": ["ads.read", "knowledge.write"],
            }
        }),
    )
    headers = {"X-API-Key": "knowledge-key"}
    try:
        with TestClient(api_server.app) as client:
            created = client.post(
                "/knowledge/documents",
                headers=headers,
                json={
                    "title": "团队 Meta 投放经验",
                    "content": "# 经验\n\n优先根据目标选择广告类型。",
                    "platform": "meta",
                    "knowledge_type": "best_practice",
                },
            )
            assert created.status_code == 201
            document_id = created.json()["document_id"]
            before_publish = client.get(
                "/knowledge/search",
                headers=headers,
                params={"query": "团队 Meta 投放经验"},
            )
            assert before_publish.status_code == 200
            assert not any(
                item["document_id"] == f"managed:{document_id}"
                for item in before_publish.json()["results"]
            )

            published = client.post(
                f"/knowledge/documents/{document_id}/publish",
                headers=headers,
            )
            assert published.status_code == 200
            after_publish = client.get(
                "/knowledge/search",
                headers=headers,
                params={"query": "团队 Meta 投放经验"},
            )
            assert after_publish.status_code == 200
            managed_result = next(
                item for item in after_publish.json()["results"]
                if item["document_id"] == f"managed:{document_id}"
            )
            assert managed_result["title"] == "团队 Meta 投放经验"
            assert after_publish.json()["summary"]
            assert after_publish.json()["summary_mode"] == "lexical"

            catalog = client.get("/knowledge/catalog", headers=headers)
            assert catalog.status_code == 200
            assert catalog.json()["count"] >= 1
            assert any(
                item["document_id"] == f"managed:{document_id}"
                for item in catalog.json()["documents"]
            )
            builtin = next(
                item for item in catalog.json()["documents"]
                if item["document_id"] == "google-campaign-hierarchy"
            )
            assert "AdGroup" in builtin["excerpt"]
    finally:
        managed_runtime.task_executor.shutdown(wait=True)
        store.close()


def test_raw_knowledge_upload_persists_source_before_queueing_ingest(monkeypatch):
    from agents.ad_agent.persistence.store import AdAgentStore

    store = AdAgentStore(":memory:")

    class RawRuntime:
        persistence_store = store

        def submit_knowledge_ingest(self, source_id, *, principal):
            return (
                {
                    "task_id": "task-raw-1",
                    "kind": "knowledge.ingest",
                    "status": "queued",
                    "payload": {"source_id": source_id},
                },
                True,
            )

    monkeypatch.setattr(api_server, "runtime", RawRuntime())
    monkeypatch.setattr(api_server, "API_KEY", "raw-key")
    monkeypatch.setattr(api_server, "ALLOW_UNAUTHENTICATED", False)
    monkeypatch.setenv(
        "AD_AGENT_API_KEY_PRINCIPALS",
        json.dumps({
            "raw-key": {
                "user_id": "raw-user",
                "tenant_id": "tenant-a",
                "permissions": ["knowledge.read", "knowledge.write"],
            }
        }),
    )
    headers = {"X-API-Key": "raw-key"}
    try:
        with TestClient(api_server.app) as client:
            response = client.post(
                "/knowledge/raw",
                headers=headers,
                json={
                    "filename": "team-notes.md",
                    "content": "# Team notes\n\nUse a stable test cell.",
                },
            )
            assert response.status_code == 202
            payload = response.json()
            assert payload["task"]["kind"] == "knowledge.ingest"
            assert payload["source"]["status"] == "received"
            assert payload["source"]["sha256"]
            assert "content" not in payload["source"]

            listed = client.get("/knowledge/raw", headers=headers)
            assert listed.status_code == 200
            assert len(listed.json()["sources"]) == 1
            assert "content" not in listed.json()["sources"][0]

            fetched = client.get(
                f"/knowledge/raw/{payload['source']['source_id']}",
                headers=headers,
            )
            assert fetched.status_code == 200
            assert "content" not in fetched.json()
    finally:
        store.close()


def test_chat_page_does_not_turn_http_errors_into_operation_complete(fake_server):
    html = api_server.TEMPLATE_PATH.read_text(encoding="utf-8") + "\n" + _chat_page_javascript()
    assert "if (!response.ok)" in html
    assert "data.detail || data.error" in html


def test_creation_cards_are_declared_as_a_right_side_workbench_contract():
    """Creation UI stays in the shared workbench instead of owning chat layout."""
    html = (
        api_server.TEMPLATE_PATH.read_text(encoding="utf-8")
        + "\n"
        + _chat_page_javascript()
        + "\n"
        + _chat_page_styles()
    )
    assert 'id="agentWorkbench"' in html
    assert 'id="creation-workbench-host"' in html
    assert "renderCreationCardInWorkbench" in html
    assert "renderCreationCardLauncher" in html
    assert "ui?.cards?.length" in html
    assert "message-card-launcher" in html


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
            "safe_input": {"customer_id": "123"},
        })
        observe({
            "type": "node_status", "event_type": "node_status",
            "node_id": "node-0001", "platform": "meta",
            "tool": "meta.list_campaigns", "status": "succeeded",
            "safe_output": {"success": True, "row_count": 2},
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
    assert '"safe_input": {"customer_id": "123"}' in body
    assert '"safe_output": {"success": true, "row_count": 2}' in body
    assert '"type": "thinking"' not in body
    assert '"type": "tool_status"' not in body
    assert body.index('"type": "node_started"') < body.index('"type": "reply"') < body.index('"type": "done"')


def test_chat_stream_forwards_creation_blueprint_context(fake_server):
    with TestClient(api_server.app) as client:
        response = client.post(
            "/chat/stream",
            headers={"X-API-Key": "test-key"},
            json={
                "user_input": "按已确认参数创建 Google Ads 广告系列",
                "account_id": "test-account",
                "creation_blueprint_id": "google-ads.search",
                "creation_blueprint_version": "1.0.0",
            },
        )
    assert response.status_code == 200
    assert fake_server.calls[-1]["creation_blueprint_id"] == "google-ads.search"
    assert fake_server.calls[-1]["creation_blueprint_version"] == "1.0.0"


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


def test_runtime_initialization_registers_all_builtin_tool_sources(monkeypatch, tmp_path):
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
    assert set(runtime.registry.list_all_namespaces()) == {
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
    from agents.ad_agent.tools.providers.tiktok import create_tiktok_tool_source

    runtime = AgentRuntime(require_llm=False, offline_mode=True)
    runtime.register_tool_source(create_tiktok_tool_source())
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
    from agents.ad_agent.tools.providers.tiktok import create_tiktok_tool_source

    runtime = AgentRuntime(require_llm=False, offline_mode=True)
    runtime.register_tool_source(create_tiktok_tool_source())
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


def test_parameter_options_resolve_allows_global_catalog_without_account_id(fake_server):
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
    assert response.status_code == 200
    assert response.json()["options"][0]["value"] == "app-1"
    assert fake_server.parameter_option_calls[0]["account_id"] is None


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
        assert response.json()["managed_skills"][0]["source"] == "managed"
        assert any(item["source"] == "builtin" for item in response.json()["builtin_skills"])

        response = client.get(
            "/skills/builtin/google-ads-api-expert/versions/2.0.0",
            headers=headers,
        )
        assert response.status_code == 200
        assert response.json()["editable"] is False
        assert response.json()["files"]["SKILL.md"]["encoding"] == "base64"

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
