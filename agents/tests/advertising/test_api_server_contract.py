"""HTTP contract tests for the ad-agent ASGI entrypoint.

These tests replace the Runtime with a local fake and never create Provider
clients or call an external advertising API.
"""

import json
import re
import subprocess
import threading
import asyncio
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from agents.applications.advertising.integrations.skill_evaluation import advertising_evaluation_engines
import yaml

from fastapi import FastAPI
from fastapi.testclient import TestClient

import agents.deployments.advertising.api_server as api_server
from agents.deployments.advertising.api.context import ApiContext
from agents.deployments.advertising.api.routes.chat import create_chat_router
from agents.deployments.advertising.api.routes.catalog import create_catalog_router
from agents.deployments.advertising.api.chat_media import ChatMediaStore
from agents.agent_platform.governance.identity.principal import RequestPrincipal


def _chat_page_javascript() -> str:
    """Read the bootstrap and split bundles as one browser contract."""
    names = [
        "chat.js", "chat-markdown.js", "chat-queue.js", "chat-state.js",
        "chat-catalog-loading.js", "chat-resource-catalogs.js", "chat-management-catalogs.js", "chat-mcp.js",
        "chat-workbench.js", "chat-workspace.js", "chat-schedules.js", "chat-knowledge.js",
        "chat-feedback.js",
        "chat-media.js",
        "chat-trace.js", "chat-requests.js", "chat-blueprint-core.js",
        "chat-settings.js",
        "chat-blueprint-editor.js", "chat-creation-import.js",
        "chat-skills.js", "chat-creation.js",
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
        "chat-creation.css", "chat-overrides.css", "chat-media.css",
        "chat-feedback.css", "chat-management.css", "chat-catalogs.css",
    ]
    return "\n".join(
        (api_server.STATIC_PATH / "css" / name).read_text(encoding="utf-8")
        for name in names
    )


def test_streamed_model_failure_after_tool_execution_does_not_offer_blind_retry():
    from agents.deployments.advertising.api.routes.chat import _chat_reply_content

    text = _chat_reply_content({
        "status": "failed",
        "error": "RateLimitError",
        "results": [{"tool": "create_resource", "success": True}],
    })
    assert "限流" in text
    assert "不要直接重试" in text


@pytest.mark.parametrize("result,expected", [
    ({"reply": "A real reply", "error": "RateLimitError"}, "A real reply"),
    ({}, ""),
    ({"error": "model_timeout"}, "模型响应超时"),
    ({"error": "model_not_configured"}, "模型服务未配置"),
    ({"error": "model_token_budget_exceeded"}, "预算"),
    ({"error": "UnknownError"}, "执行失败"),
])
def test_chat_failure_copy_uses_safe_codes_and_preserves_existing_replies(result, expected):
    from agents.deployments.advertising.api.routes.chat import _chat_reply_content

    assert expected in _chat_reply_content(result)

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


def test_service_config_path_can_be_overridden_for_isolated_local_runs(
    tmp_path, monkeypatch
):
    config_path = tmp_path / "isolated-config.yaml"
    monkeypatch.setenv("AD_AGENT_CONFIG_PATH", str(config_path))

    assert api_server._configured_config_path() == config_path.resolve()


def test_service_config_path_defaults_to_checked_in_safe_config(monkeypatch):
    monkeypatch.delenv("AD_AGENT_CONFIG_PATH", raising=False)

    assert api_server._configured_config_path() == api_server.CONFIG_PATH.resolve()


def test_model_defaults_use_the_supported_agnes_three_flash_identifier():
    deployment_config = yaml.safe_load(
        api_server.CONFIG_PATH.read_text(encoding="utf-8")
    )
    test_config_path = api_server.project_root / "agents" / "ad_agent" / "config.test-live.yaml"
    test_config = yaml.safe_load(test_config_path.read_text(encoding="utf-8"))
    env_example = (
        api_server.project_root / "agents" / "ad_agent" / ".env.example"
    ).read_text(encoding="utf-8")
    template = api_server.TEMPLATE_PATH.read_text(encoding="utf-8")

    assert deployment_config["models"]["default"] == "agnes-3.0-flash"
    assert test_config["models"]["default"] == "agnes-3.0-flash"
    assert "LLM_MODEL=agnes-3.0-flash" in env_example
    assert 'placeholder="例如：agnes-3.0-flash"' in template


def test_runtime_initialization_uses_isolated_config_account_allowlist(
    tmp_path, monkeypatch
):
    config_path = tmp_path / "isolated-config.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "allowed_accounts": {"meta": ["isolated-test-account"]},
                "execution_mode": "dry_run",
                "allow_live_writes": False,
                "live_approved_tools": [],
                "granted_permissions": ["ads.read", "ads.plan"],
                "models": {"default": "agnes-3.0-flash"},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("AD_AGENT_CONFIG_PATH", str(config_path))
    monkeypatch.setenv("AD_AGENT_DB_PATH", str(tmp_path / "isolated.db"))
    monkeypatch.setenv("OPENAI_API_KEY", "test-llm-key")
    monkeypatch.setattr(api_server, "runtime", None)
    monkeypatch.setattr(
        api_server,
        "runtime_status",
        {"state": "not_initialized", "error": None},
    )

    runtime = api_server._init_runtime()
    try:
        assert runtime is not None
        assert runtime.whitelist_validator.get_allowed_accounts("meta") == [
            "isolated-test-account"
        ]
        assert runtime.whitelist_validator.get_allowed_accounts("google-ads") == []
        assert runtime.whitelist_validator.get_allowed_accounts("tiktok") == []
    finally:
        if runtime is not None:
            runtime.close(wait=True)


def test_chat_routes_are_owned_by_a_dedicated_route_module():
    routes = list(api_server.app.routes)
    for included in routes:
        original = getattr(included, "original_router", None)
        if original is not None:
            routes.extend(original.routes)
    chat_routes = {
        route.path: route.endpoint.__module__
        for route in routes
        if getattr(route, "path", None) in {
            "/chat", "/chat/cancel", "/chat/stream",
        }
    }

    assert chat_routes == {
        "/chat": "agents.deployments.advertising.api.routes.chat",
        "/chat/cancel": "agents.deployments.advertising.api.routes.chat",
        "/chat/stream": "agents.deployments.advertising.api.routes.chat",
    }


def test_chat_cancel_uses_authenticated_identity_and_session(fake_server, monkeypatch):
    calls = []
    fake_server.cancel_run = lambda session_id, **kwargs: (
        calls.append((session_id, kwargs)) or True
    )
    monkeypatch.setenv(
        "AD_AGENT_API_KEY_PRINCIPALS",
        json.dumps({
            "operator-key": {
                "user_id": "operator",
                "tenant_id": "tenant-a",
                "permissions": ["ads.read"],
            }
        }),
    )

    with TestClient(api_server.app) as client:
        response = client.post(
            "/chat/cancel",
            headers={"X-API-Key": "operator-key"},
            json={
                "session_id": "session-a",
                "user_id": "forged-user",
                "tenant_id": "forged-tenant",
            },
        )

    assert response.status_code == 202
    assert response.json() == {"status": "cancellation_requested"}
    assert calls == [(
        "session-a",
        {"user_id": "operator", "tenant_id": "tenant-a"},
    )]


def test_chat_cancel_reports_no_active_run_without_leaking_other_sessions(
    fake_server, monkeypatch,
):
    calls = []
    fake_server.cancel_run = lambda session_id, **kwargs: (
        calls.append((session_id, kwargs)) or False
    )
    monkeypatch.setenv(
        "AD_AGENT_API_KEY_PRINCIPALS",
        json.dumps({
            "operator-key": {
                "user_id": "operator",
                "tenant_id": "tenant-a",
                "permissions": ["ads.read"],
            }
        }),
    )

    with TestClient(api_server.app) as client:
        response = client.post(
            "/chat/cancel",
            headers={"X-API-Key": "operator-key"},
            json={"session_id": "session-not-running"},
        )

    assert response.status_code == 200
    assert response.json() == {"status": "not_running"}
    assert calls == [(
        "session-not-running",
        {"user_id": "operator", "tenant_id": "tenant-a"},
    )]


def test_chat_cancel_maps_runtime_state_errors_to_service_unavailable(
    fake_server, monkeypatch,
):
    def fail_cancel(_session_id, **_identity):
        raise RuntimeError("runtime unavailable")

    fake_server.cancel_run = fail_cancel
    monkeypatch.setenv(
        "AD_AGENT_API_KEY_PRINCIPALS",
        json.dumps({
            "operator-key": {
                "user_id": "operator",
                "tenant_id": "tenant-a",
                "permissions": ["ads.read"],
            }
        }),
    )

    with TestClient(api_server.app) as client:
        response = client.post(
            "/chat/cancel",
            headers={"X-API-Key": "operator-key"},
            json={"session_id": "session-a"},
        )

    assert response.status_code == 503


def test_chat_ui_exposes_stop_and_bounded_queue_contract():
    javascript = _chat_page_javascript()
    template = api_server.TEMPLATE_PATH.read_text(encoding="utf-8")
    styles = _chat_page_styles()

    assert 'id="stopBtn"' in template
    assert 'id="chatQueuePanel"' in template
    assert "requestChatCancellation" in javascript
    assert "processNextQueuedMessage" in javascript
    assert "MAX_CHAT_QUEUE_SIZE = 10" in javascript
    assert ".chat-stop-btn" in styles
    assert ".chat-queue-panel" in styles

    subprocess.run(
        [
            "node",
            "--test",
            str(Path(__file__).parent / "static" / "test_chat_queue.js"),
            str(Path(__file__).parent / "static" / "test_chat_queue_ui.js"),
        ],
        check=True,
        timeout=30,
    )


def test_execution_trace_is_opt_in_while_creation_workbench_remains_available():
    javascript = _chat_page_javascript()
    template = api_server.TEMPLATE_PATH.read_text(encoding="utf-8")

    assert "function shouldOpenTraceForEvent" not in javascript
    assert "function applyExecutionEvent(event)" in javascript
    event_handler = javascript.split("function applyExecutionEvent(event)", 1)[1]
    assert "openAgentWorkbench" not in event_handler
    assert 'onclick="openTraceWorkbench()"' in template
    assert "function openTraceWorkbench()" in javascript
    assert "function openCreationWorkbench" in javascript
    assert "function openConfirmationWorkbench" in javascript


def test_chat_messages_include_persistent_assistant_feedback_controls():
    javascript = _chat_page_javascript()
    styles = _chat_page_styles()

    assert "submitAssistantFeedback" in javascript
    assert "/turns/${encodeURIComponent(turnId)}/feedback" in javascript
    assert "feedback_rating" in javascript
    assert "['positive', '👍'" in javascript
    assert "['negative', '👎'" in javascript
    assert "保存失败：" in javascript
    assert ".message-feedback" in styles


def test_chat_request_preparation_does_not_block_the_event_loop():
    main_thread = threading.get_ident()
    callback_threads = []
    principal = RequestPrincipal(
        user_id="user-a",
        tenant_id="tenant-a",
        permissions=frozenset({"ads.read"}),
    )

    class Runtime:
        calls = []

        def run(self, **_kwargs):
            self.calls.append(dict(_kwargs))
            return {"success": True, "reply": "ok", "results": []}

    runtime = Runtime()
    context = ApiContext(
        runtime_getter=lambda: runtime,
        authorize_request=lambda *_args: principal,
        require_permission=lambda *_args: None,
        activate_tenant_skills=lambda _principal: callback_threads.append(
            ("skills", threading.get_ident())
        ),
        sync_tenant_extensions=lambda _principal: callback_threads.append(
            ("mcp", threading.get_ident())
        ),
        safe_exception_text=lambda error: str(error),
        redact=lambda value: value,
    )
    app = FastAPI()
    app.include_router(create_chat_router(context))

    with TestClient(app) as client:
        response = client.post(
            "/chat",
            json={
                "user_input": "hello",
                "tool_allowlist": ["read_record"],
            },
        )

    assert response.status_code == 200, response.text
    assert runtime.calls[0]["tool_allowlist"] == ["read_record"]
    assert {name for name, _thread_id in callback_threads} == {"skills", "mcp"}
    assert all(thread_id != main_thread for _name, thread_id in callback_threads)


def test_chat_media_upload_is_identity_scoped_and_reaches_the_model_runtime(tmp_path):
    principal = RequestPrincipal(
        user_id="media-user",
        tenant_id="media-tenant",
        permissions=frozenset({"ads.read"}),
    )

    class Runtime:
        calls = []

        def run(self, **kwargs):
            self.calls.append(kwargs)
            return {"success": True, "reply": "看到了图片", "results": []}

    runtime = Runtime()
    store = ChatMediaStore(tmp_path)
    context = ApiContext(
        runtime_getter=lambda: runtime,
        authorize_request=lambda *_args: principal,
        require_permission=lambda *_args: None,
        activate_tenant_skills=lambda _principal: None,
        sync_tenant_extensions=lambda _principal: None,
        safe_exception_text=lambda error: str(error),
        redact=lambda value: value,
        chat_media_store_getter=lambda: store,
    )
    app = FastAPI()
    app.include_router(create_chat_router(context))
    session_id = "media-session"
    png = (
        b"\x89PNG\r\n\x1a\n"
        b"\x00\x00\x00\rIHDR"
        b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00"
    )

    with TestClient(app) as client:
        uploaded = client.post(
            f"/chat/media?session_id={session_id}&filename=creative.png",
            content=png,
            headers={"Content-Type": "image/png"},
        )
        assert uploaded.status_code == 201, uploaded.text
        attachment = uploaded.json()

        image_response = client.get(
            f"/chat/media/{attachment['id']}?session_id={session_id}"
        )
        assert image_response.status_code == 200
        assert image_response.content == png
        assert image_response.headers["content-type"] == "image/png"

        chat = client.post(
            "/chat",
            json={
                "user_input": "请看这张图片",
                "session_id": session_id,
                "media_ids": [attachment["id"]],
            },
        )

    assert chat.status_code == 200, chat.text
    attached = runtime.calls[0]["input_media"]
    assert len(attached) == 1
    assert attached[0].attachment_id == attachment["id"]
    assert attached[0].content == png

    with TestClient(app) as client:
        removed = client.delete(
            f"/chat/media/{attachment['id']}?session_id={session_id}"
        )
        missing = client.get(
            f"/chat/media/{attachment['id']}?session_id={session_id}"
        )
    assert removed.status_code == 204
    assert missing.status_code == 404


def test_chat_document_upload_is_identity_scoped_and_reaches_the_model_runtime(tmp_path):
    principal = RequestPrincipal(
        user_id="document-user",
        tenant_id="document-tenant",
        permissions=frozenset({"ads.read"}),
    )

    class Runtime:
        def __init__(self):
            self.calls = []

        def run(self, **kwargs):
            self.calls.append(kwargs)
            return {"success": True, "reply": "已读取 CSV", "results": []}

    runtime = Runtime()
    context = ApiContext(
        runtime_getter=lambda: runtime,
        authorize_request=lambda *_args: principal,
        require_permission=lambda *_args: None,
        activate_tenant_skills=lambda _principal: None,
        sync_tenant_extensions=lambda _principal: None,
        safe_exception_text=lambda error: str(error),
        redact=lambda value: value,
        chat_media_store_getter=lambda: ChatMediaStore(tmp_path),
    )
    app = FastAPI()
    app.include_router(create_chat_router(context))

    with TestClient(app) as client:
        uploaded = client.post(
            "/chat/media?session_id=document-session&filename=report.csv",
            content=b"campaign,spend\nSpring,125.5\n",
            headers={"Content-Type": "text/csv"},
        )
        assert uploaded.status_code == 201, uploaded.text
        attachment = uploaded.json()
        response = client.post(
            "/chat",
            json={
                "user_input": "分析这份报表",
                "session_id": "document-session",
                "media_ids": [attachment["id"]],
            },
        )

    assert response.status_code == 200, response.text
    document = runtime.calls[0]["input_media"][0]
    assert document.filename == "report.csv"
    assert document.media_type == "text/csv"
    assert "Spring | 125.5" in document.extracted_text


@pytest.mark.parametrize("stream", [False, True])
def test_pending_chat_continuation_restores_recent_user_attachments(
    tmp_path, stream,
):
    principal = RequestPrincipal(
        user_id="continuation-user",
        tenant_id="continuation-tenant",
        permissions=frozenset({"ads.read"}),
    )

    class Runtime:
        def __init__(self):
            self.calls = []
            self.messages = []
            self.pending = False

        def run(self, **kwargs):
            self.calls.append(kwargs)
            self.messages = [{
                "role": "user",
                "content": kwargs["user_input"],
                "attachments": [
                    media.to_metadata() for media in kwargs["input_media"]
                ],
            }]
            self.pending = True
            return {
                "run_id": f"run-{len(self.calls)}",
                "session_id": "continuation-session",
                "turn_id": f"turn-{len(self.calls)}",
                "status": "awaiting_input",
                "needs_input": True,
                "reply": "请补充说明。",
                "results": [],
            }

        def get_latest_run(self, **kwargs):
            assert kwargs["user_id"] == "continuation-user"
            assert kwargs["tenant_id"] == "continuation-tenant"
            return {"status": "awaiting_input"} if self.pending else None

        def get_conversation(self, **kwargs):
            assert kwargs["user_id"] == "continuation-user"
            assert kwargs["tenant_id"] == "continuation-tenant"
            assert kwargs["session_id"] == "continuation-session"
            return {"messages": self.messages}

    runtime = Runtime()
    context = ApiContext(
        runtime_getter=lambda: runtime,
        authorize_request=lambda *_args: principal,
        require_permission=lambda *_args: None,
        activate_tenant_skills=lambda _principal: None,
        sync_tenant_extensions=lambda _principal: None,
        safe_exception_text=lambda error: str(error),
        redact=lambda value: value,
        chat_media_store_getter=lambda: ChatMediaStore(tmp_path),
    )
    app = FastAPI()
    app.include_router(create_chat_router(context))
    png = (
        b"\x89PNG\r\n\x1a\n"
        b"\x00\x00\x00\rIHDR"
        b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00"
    )

    with TestClient(app) as client:
        uploaded = client.post(
            "/chat/media?session_id=continuation-session&filename=flow.png",
            content=png,
            headers={"Content-Type": "image/png"},
        )
        assert uploaded.status_code == 201, uploaded.text
        media_id = uploaded.json()["id"]
        first = client.post("/chat", json={
            "user_input": "请看图里的流程",
            "session_id": "continuation-session",
            "media_ids": [media_id],
        })
        assert first.status_code == 200, first.text

        path = "/chat/stream" if stream else "/chat"
        second = client.post(path, json={
            "user_input": "我指的是图里的这个创建流程",
            "session_id": "continuation-session",
        })

    assert second.status_code == 200, second.text
    assert len(runtime.calls) == 2
    assert [item.attachment_id for item in runtime.calls[1]["input_media"]] == [
        media_id,
    ]


def test_chat_does_not_restore_attachment_without_pending_input(tmp_path):
    principal = RequestPrincipal(
        user_id="continuation-user",
        tenant_id="continuation-tenant",
        permissions=frozenset({"ads.read"}),
    )

    class Runtime:
        def __init__(self):
            self.calls = []

        def get_latest_run(self, **_kwargs):
            return {"status": "succeeded"}

        def get_conversation(self, **_kwargs):
            raise AssertionError("completed runs must not load old attachment history")

        def run(self, **kwargs):
            self.calls.append(kwargs)
            return {"success": True, "reply": "已处理", "results": []}

    runtime = Runtime()
    context = ApiContext(
        runtime_getter=lambda: runtime,
        authorize_request=lambda *_args: principal,
        require_permission=lambda *_args: None,
        activate_tenant_skills=lambda _principal: None,
        sync_tenant_extensions=lambda _principal: None,
        safe_exception_text=lambda error: str(error),
        redact=lambda value: value,
        chat_media_store_getter=lambda: ChatMediaStore(tmp_path),
    )
    app = FastAPI()
    app.include_router(create_chat_router(context))

    with TestClient(app) as client:
        response = client.post("/chat", json={
            "user_input": "继续",
            "session_id": "continuation-session",
        })

    assert response.status_code == 200, response.text
    assert runtime.calls[0]["input_media"] == ()


def test_chat_stream_preserves_media_gallery_in_reply_ui(tmp_path):
    principal = RequestPrincipal(
        user_id="media-user",
        tenant_id="media-tenant",
        permissions=frozenset({"ads.read"}),
    )

    class Runtime:
        def run(self, **_kwargs):
            return {
                "session_id": "media-session",
                "turn_id": "turn-1",
                "status": "succeeded",
                "reply": "找到一张图片",
                "results": [{
                    "success": True,
                    "data": {
                        "image_assets": [{
                            "id": "image-1",
                            "name": "Creative",
                            "url": "https://cdn.example.test/image.jpg",
                        }],
                    },
                }],
                "ui": {
                    "media_gallery": [{
                        "kind": "image",
                        "id": "image-1",
                        "name": "Creative",
                        "url": "https://cdn.example.test/image.jpg",
                    }],
                },
            }

    context = ApiContext(
        runtime_getter=Runtime,
        authorize_request=lambda *_args: principal,
        require_permission=lambda *_args: None,
        activate_tenant_skills=lambda _principal: None,
        sync_tenant_extensions=lambda _principal: None,
        safe_exception_text=lambda error: str(error),
        redact=lambda value: value,
        chat_media_store_getter=lambda: ChatMediaStore(tmp_path),
    )
    app = FastAPI()
    app.include_router(create_chat_router(context))

    with TestClient(app) as client:
        response = client.post(
            "/chat/stream",
            json={"user_input": "查询图片素材"},
        )

    assert response.status_code == 200
    reply = next(
        json.loads(line.removeprefix("data: "))
        for line in response.text.splitlines()
        if line.startswith("data: ") and '"type": "reply"' in line
    )
    assert reply["ui"]["media_gallery"][0]["url"].endswith("/image.jpg")


def test_chat_media_route_rejects_cross_user_and_cross_tenant_reads(tmp_path):
    image = ChatMediaStore(tmp_path).save(
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
        b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00",
        filename="creative.png",
        content_type="image/png",
        session_id="media-session",
        tenant_id="tenant-a",
        user_id="user-a",
    )
    principal = RequestPrincipal(
        user_id="user-b",
        tenant_id="tenant-b",
        permissions=frozenset({"ads.read"}),
    )

    class Runtime:
        def run(self, **_kwargs):
            return {"success": True, "reply": "ok", "results": []}

    context = ApiContext(
        runtime_getter=Runtime,
        authorize_request=lambda *_args: principal,
        require_permission=lambda *_args: None,
        activate_tenant_skills=lambda _principal: None,
        sync_tenant_extensions=lambda _principal: None,
        safe_exception_text=lambda error: str(error),
        redact=lambda value: value,
        chat_media_store_getter=lambda: ChatMediaStore(tmp_path),
    )
    app = FastAPI()
    app.include_router(create_chat_router(context))

    with TestClient(app) as client:
        response = client.get(
            f"/chat/media/{image['id']}?session_id=media-session"
        )

    assert response.status_code == 404


def test_creation_import_preview_is_scoped_authorized_and_never_executes_tools(tmp_path):
    from types import SimpleNamespace

    from fastapi import HTTPException

    media_store = ChatMediaStore(tmp_path / "media")
    attachment = media_store.save(
        b"Campaign\nSpring\n",
        filename="campaigns.csv",
        content_type="text/csv",
        session_id="session-a",
        tenant_id="tenant-a",
        user_id="owner-a",
    )
    principals = {
        "owner-key": RequestPrincipal(
            user_id="owner-a",
            tenant_id="tenant-a",
            permissions=frozenset({"ads.plan"}),
        ),
        "reader-key": RequestPrincipal(
            user_id="reader-a",
            tenant_id="tenant-a",
            permissions=frozenset({"ads.read"}),
        ),
        "other-user-key": RequestPrincipal(
            user_id="other-user",
            tenant_id="tenant-a",
            permissions=frozenset({"ads.plan"}),
        ),
        "other-tenant-key": RequestPrincipal(
            user_id="owner-a",
            tenant_id="tenant-b",
            permissions=frozenset({"ads.plan"}),
        ),
    }
    blueprint = SimpleNamespace(
        blueprint_id="demo.search",
        version="1.0.0",
        fields=({
            "path": "campaign.name",
            "label": "Campaign 名称",
            "tool_ref": "create_campaign.name",
        },),
    )
    evaluation_calls = []

    class Runtime:
        creation_blueprints = SimpleNamespace(
            get=lambda blueprint_id, version=None: (
                blueprint
                if blueprint_id == "demo.search" and version in {None, "1.0.0"}
                else None
            ),
        )

        @staticmethod
        def _get_registered_tool(_name):
            return (
                SimpleNamespace(input_schema={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "minLength": 1},
                    },
                }),
                lambda **_kwargs: pytest.fail("preview must not execute a Tool"),
            )

        @staticmethod
        def evaluate_creation_blueprint(blueprint_id, values, **_kwargs):
            evaluation_calls.append((blueprint_id, values))
            return {
                "ready": bool(values.get("campaign", {}).get("name")),
                "missing_fields": [],
                "invalid_fields": [],
            }

        @staticmethod
        def run(**_kwargs):
            pytest.fail("preview must not start an Agent run")

    def authorize(api_key, _request):
        principal = principals.get(api_key)
        if principal is None:
            raise HTTPException(status_code=401, detail="unauthorized")
        return principal

    def require_permission(principal, permission):
        if permission not in principal.permissions:
            raise HTTPException(status_code=403, detail="forbidden")

    context = ApiContext(
        runtime_getter=Runtime,
        authorize_request=authorize,
        require_permission=require_permission,
        activate_tenant_skills=lambda _principal: None,
        sync_tenant_extensions=lambda _principal: None,
        safe_exception_text=lambda error: str(error),
        redact=lambda value: value,
        chat_media_store_getter=lambda: media_store,
    )
    app = FastAPI()
    app.include_router(create_catalog_router(context))
    request_payload = {
        "session_id": "session-a",
        "attachment_id": attachment["id"],
        "blueprint_id": "demo.search",
        "version": "1.0.0",
        "column_mapping": {"campaign.name": "Campaign"},
    }

    with TestClient(app) as client:
        inspect = client.post(
            "/creation-import/inspect",
            headers={"X-API-Key": "owner-key"},
            json={key: value for key, value in request_payload.items()
                  if key != "column_mapping"},
        )
        preview = client.post(
            "/creation-import/preview",
            headers={"X-API-Key": "owner-key"},
            json=request_payload,
        )
        denied = client.post(
            "/creation-import/preview",
            headers={"X-API-Key": "reader-key"},
            json=request_payload,
        )
        cross_user = client.post(
            "/creation-import/inspect",
            headers={"X-API-Key": "other-user-key"},
            json=request_payload,
        )
        cross_tenant = client.post(
            "/creation-import/inspect",
            headers={"X-API-Key": "other-tenant-key"},
            json=request_payload,
        )

    assert inspect.status_code == 200, inspect.text
    assert inspect.json()["preview_only"] is True
    assert inspect.json()["headers"] == ["Campaign"]
    assert preview.status_code == 200, preview.text
    assert preview.json()["preview_only"] is True
    assert preview.json()["rows"][0]["values"] == {
        "campaign": {"name": "Spring"},
    }
    assert denied.status_code == 403
    assert cross_user.status_code == 404
    assert cross_tenant.status_code == 404
    assert evaluation_calls == [(
        "demo.search",
        {"campaign": {"name": "Spring"}},
    )]


def test_operational_routes_are_owned_by_dedicated_route_modules():
    routes = list(api_server.app.routes)
    for included in routes:
        original = getattr(included, "original_router", None)
        if original is not None:
            routes.extend(original.routes)
    route_modules = {
        route.path: route.endpoint.__module__
        for route in routes
        if getattr(route, "path", None) in {
            "/sessions", "/tasks", "/schedules",
            "/knowledge/search", "/memory",
        }
    }

    assert route_modules["/sessions"] == "agents.deployments.advertising.api.routes.sessions"
    assert route_modules["/tasks"] == "agents.deployments.advertising.api.routes.tasks"
    assert route_modules["/schedules"] == "agents.deployments.advertising.api.routes.tasks"
    assert route_modules["/knowledge/search"] == "agents.deployments.advertising.api.routes.knowledge"
    assert route_modules["/memory"] == "agents.deployments.advertising.api.routes.knowledge"


def test_management_and_catalog_routes_are_owned_by_dedicated_route_modules():
    routes = list(api_server.app.routes)
    for included in routes:
        original = getattr(included, "original_router", None)
        if original is not None:
            routes.extend(original.routes)
    route_modules = {
        route.path: route.endpoint.__module__
        for route in routes
        if getattr(route, "path", None) in {
            "/creation-templates",
            "/plugins/packages",
            "/mcp/servers",
            "/skills",
            "/tools",
            "/parameter-options",
            "/workflows/{workflow_id}",
        }
    }

    assert route_modules["/creation-templates"] == "agents.deployments.advertising.api.routes.catalog"
    assert route_modules["/plugins/packages"] == "agents.deployments.advertising.api.routes.plugins"
    assert route_modules["/mcp/servers"] == "agents.deployments.advertising.api.routes.mcp"
    assert route_modules["/skills"] == "agents.deployments.advertising.api.routes.skills"
    management_source = Path(
        api_server.project_root / "agents/deployments/advertising/api/routes/management.py"
    )
    assert len(management_source.read_text(encoding="utf-8").splitlines()) <= 80
    assert route_modules["/tools"] == "agents.deployments.advertising.api.routes.catalog"
    assert route_modules["/parameter-options"] == "agents.deployments.advertising.api.routes.catalog"
    assert route_modules["/workflows/{workflow_id}"] == "agents.deployments.advertising.api.routes.workflows"


def test_cors_allows_existing_mutation_methods_and_request_headers(fake_server):
    with TestClient(api_server.app) as client:
        response = client.options(
            "/knowledge/documents/example",
            headers={
                "Origin": "http://localhost:8765",
                "Access-Control-Request-Method": "PUT",
                "Access-Control-Request-Headers": (
                    "content-type,x-api-key,idempotency-key"
                ),
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:8765"
    assert "PUT" in response.headers["access-control-allow-methods"]
    allowed_headers = response.headers["access-control-allow-headers"].lower()
    assert "idempotency-key" in allowed_headers


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
        self._live_approved_tools = {"create_test"}
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
    monkeypatch.delenv("AD_AGENT_ENABLE_LIVE", raising=False)
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


def test_agent_runtime_metrics_are_authenticated_and_credential_free(
    fake_server, monkeypatch,
):
    class Metrics:
        @staticmethod
        def snapshot():
            return {
                "version": 1,
                "counters": {
                    "runs_started": 4,
                    "runs_finished.succeeded": 3,
                    "tool_calls_failed": 1,
                },
                "durations": {},
                "in_flight": 0,
            }

    fake_server.metrics = Metrics()
    monkeypatch.setenv(
        "AD_AGENT_API_KEY_PRINCIPALS",
        json.dumps({
            "observer-key": {
                "user_id": "observer",
                "tenant_id": "tenant-a",
                "permissions": ["ads.read"],
            },
            "reader-key": {
                "user_id": "reader",
                "tenant_id": "tenant-a",
                "permissions": ["knowledge.read"],
            },
        }),
    )

    with TestClient(api_server.app) as client:
        denied = client.get(
            "/monitoring/agent-runtime",
            headers={"X-API-Key": "reader-key"},
        )
        accepted = client.get(
            "/monitoring/agent-runtime",
            headers={"X-API-Key": "observer-key"},
        )

    assert denied.status_code == 403
    assert accepted.status_code == 200
    payload = accepted.json()
    assert payload["scope"] == "process_aggregate"
    assert payload["metrics"]["counters"]["runs_started"] == 4
    serialized = json.dumps(payload)
    assert "run_id" not in serialized
    assert "access_token" not in serialized


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
        planner_denied = client.post(
            "/settings/execution-mode",
            headers={"X-API-Key": "plan-key"},
            json={"mode": "live"},
        )
        writer_denied = client.post(
            "/settings/execution-mode",
            headers={"X-API-Key": "write-key"},
            json={"mode": "live"},
        )
    assert planner_denied.status_code == 403
    assert writer_denied.status_code == 409
    assert "live 环境开关" in writer_denied.json()["detail"]
    assert fake_server.execution_mode == "dry_run"


def test_execution_mode_rejects_live_when_no_tools_are_approved(monkeypatch, fake_server):
    fake_server.allow_live_writes = True
    fake_server._live_approved_tools = set()
    monkeypatch.setenv("AD_AGENT_ENABLE_LIVE", "1")
    monkeypatch.setenv("AD_AGENT_API_KEY_PRINCIPALS", json.dumps({
        "write-key": {
            "user_id": "operator", "tenant_id": "tenant",
            "permissions": ["ads.plan", "ads.write"],
        },
    }))
    with TestClient(api_server.app) as client:
        status = client.get("/settings/execution-mode", headers={"X-API-Key": "write-key"})
        response = client.post(
            "/settings/execution-mode", headers={"X-API-Key": "write-key"},
            json={"mode": "live"},
        )
    assert status.json()["live_mode_available"] is False
    assert response.status_code == 409
    assert "Tool" in response.json()["detail"]
    assert fake_server.execution_mode == "dry_run"


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
        "X-API-Key", "streamChatRequest", "chatStreamUncertain",
            "最近对话", "服务已连接", "grid-template-columns: 228px minmax(0, 1fr) minmax(450px, 460px)",
        "global-action-label", "知识库", "/sessions?limit=50",
        "/sessions/${encodeURIComponent(targetSessionId)}?limit=10",
        "before_message_id",
        "loadOlderConversationMessages",
        "conversationHistoryPagination",
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
        "waitForKnowledgeIngest", "view-hidden", "返回知识列表",
        "knowledgeCatalog", "knowledge-reader-actions", "复制为我的草稿", "编辑文档", "全文检索",
        "skillsCatalog", "mcpCatalog", "resourceCatalogPage", "resumeResourceDraft",
        "knowledge-table-wrap", "knowledge-task", "knowledge-render-v3",
        "themeToggleButton", "light-theme", "ad-agent-theme", "toggleTheme",
        "executionModeSelect", "/settings/execution-mode", "live_mode_available",
        "live_mode_reason", "应用模式", "live · 受控执行", "handleWorkspaceModeChange",
        "系统运维", "systemOpsMenu", "toggleSystemOpsMenu", "运行监控", "/monitoring/overview", "monitoringTaskBars",
        "monitoringLeaseList", "Tool 调用审计", "当前实例",
        "反馈趋势", "/feedback/trend", "feedbackTrendChart",
        "主动提交", "data-feedback-days",
        "sidebar > .new-chat-btn", "nav-icon", "blueprintOverlay",
        "!event.target.closest('.blueprint-overlay')",
        "closeBlueprintManager()", "event.stopPropagation()",
        "agentWorkbench", "workbench-tab-creation", "workbench-tab-trace",
        "openCreationWorkbench", "closeCreationWorkbench",
        "reopenCreationCard", "creation-workbench-host",
        "message-card-launcher", "右侧工作区",
        'id="chatMediaInput"', "handleChatMediaSelection", "handleChatPaste",
        "media_ids", "media_gallery", "renderMessageAttachments",
        "/chat/media/", "video/mp4", "video/webm",
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "CHAT_DOCUMENT_EXTENSIONS", "chatDocumentTypeLabel",
    ):
        assert marker in html
    # Credential field names are exposed only by the settings manager; values
    # are never returned by the status API or rendered into the page.
    template = api_server.TEMPLATE_PATH.read_text(encoding="utf-8")
    settings_js = (
        api_server.STATIC_PATH / "js" / "chat-settings.js"
    ).read_text(encoding="utf-8")
    for credential_field in (
        "access_token", "refresh_token", "client_secret", "developer_token",
    ):
        assert credential_field not in template
        assert credential_field in settings_js
    assert "api_key_configured" in settings_js
    assert "input.value = profile.api_key" not in settings_js


def test_chat_requires_api_key(fake_server):
    with TestClient(api_server.app) as client:
        response = client.post("/chat", json={"user_input": "查询 Meta campaign"})
    assert response.status_code == 401
    assert fake_server.calls == []


def test_shared_unauthenticated_local_and_remote_clients_share_session_scope(
    fake_server, monkeypatch,
):
    monkeypatch.setattr(api_server, "ALLOW_UNAUTHENTICATED", True)
    monkeypatch.setenv(
        "AD_AGENT_API_KEY_PRINCIPALS",
        json.dumps({
            "separate-user-key": {
                "user_id": "separate-user",
                "tenant_id": "separate-tenant",
                "permissions": ["ads.read"],
            }
        }),
    )
    fake_server._granted_permissions = {"ads.read", "ads.plan"}
    calls = []
    fake_server.list_conversations = lambda **kwargs: (
        calls.append(kwargs)
        or [{
            "session_id": "shared-session",
            "title": "Shared history",
            "updated_at": "2026-10-19T10:00:00+00:00",
        }]
    )

    async def get_sessions(client_host, port):
        transport = httpx.ASGITransport(
            app=api_server.app,
            client=(client_host, port),
        )
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://ad-agent.test",
        ) as client:
            return await client.get("/sessions")

    async def get_both():
        return await asyncio.gather(
            get_sessions("127.0.0.1", 51001),
            get_sessions("10.53.48.25", 51002),
        )

    local_response, remote_response = asyncio.run(get_both())

    assert local_response.status_code == remote_response.status_code == 200
    assert local_response.json() == remote_response.json()
    assert [call["user_id"] for call in calls] == [
        "ad-agent-service",
        "ad-agent-service",
    ]
    assert [call["tenant_id"] for call in calls] == ["default", "default"]


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


def test_chat_never_returns_unexecuted_tool_protocol_as_assistant_text(fake_server):
    fake_server.run = lambda **_kwargs: {
        "status": "succeeded",
        "reply": (
            "<think>正在搜索</think>"
            "<|tool_calls_section_end|> API Error: channel_id=\"\" "
            "error_code=40400 message=invalid_user_id "
            "<|tool_call_begin|> agent-platform:knowledge_search "
            "<|tool_call_argument_begin|>{\"query\":\"Meta 广告\"}"
            "<|tool_call_end|>"
        ),
        "results": [],
    }

    with TestClient(api_server.app) as client:
        response = client.post(
            "/chat",
            headers={"X-API-Key": "test-key"},
            json={"user_input": "讲下 Meta 广告吧"},
        )

    assert response.status_code == 200
    reply = response.json()["reply"]
    assert "<think>" not in reply
    assert "<|" not in reply
    assert "40400 / invalid_user_id" in reply
    assert "未执行" in reply


def test_chat_hides_tool_calls_section_begin_protocol(fake_server):
    fake_server.run = lambda **_kwargs: {
        "status": "succeeded",
        "reply": (
            "<|tool_calls_section_begin|> meta_list_creation_templates "
            "<|tool_call_argument_begin|> "
            "{\"account_id\":\"account-1\",\"query\":\"Canvas\"} "
            "<|tool_call_end|>"
        ),
        "results": [],
    }

    with TestClient(api_server.app) as client:
        response = client.post(
            "/chat",
            headers={"X-API-Key": "test-key"},
            json={"user_input": "查找 Canvas 广告创建 API 示例"},
        )

    assert response.status_code == 200
    reply = response.json()["reply"]
    assert "<|tool_" not in reply
    assert "meta_list_creation_templates" not in reply
    assert "account-1" not in reply
    assert "没有执行任何操作" in reply


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
            "has_more": True,
            "next_cursor": "cursor-1",
        }

    fake_server.list_conversations = list_conversations
    fake_server.get_conversation = get_conversation
    with TestClient(api_server.app) as client:
        listing = client.get("/sessions", headers={"X-API-Key": "scoped-key"})
        detail = client.get(
            "/sessions/session-a",
            headers={"X-API-Key": "scoped-key"},
            params={
                "user_id": "forged-user",
                "limit": 7,
                "before_message_id": "cursor-1",
            },
        )

    assert listing.status_code == 200
    assert listing.json()["sessions"][0]["session_id"] == "session-a"
    assert detail.status_code == 200
    assert detail.json()["messages"][0]["content"] == "查询 Meta 广告系列"
    assert calls[0][1]["user_id"] == "gateway-user"
    assert calls[0][1]["tenant_id"] == "tenant-a"
    assert calls[1][1]["user_id"] == "gateway-user"
    assert calls[1][1]["tenant_id"] == "tenant-a"
    assert calls[1][1]["limit"] == 7
    assert calls[1][1]["before_message_id"] == "cursor-1"
    assert detail.json()["has_more"] is True


def test_session_list_returns_and_consumes_scoped_keyset_cursor(
    monkeypatch,
    fake_server,
):
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
    sessions = [
        {
            "session_id": "session-c",
            "updated_at": "2026-10-19T12:00:00+00:00",
        },
        {
            "session_id": "session-b",
            "updated_at": "2026-10-19T12:00:00+00:00",
        },
        {
            "session_id": "session-a",
            "updated_at": "2026-10-19T11:00:00+00:00",
        },
    ]

    def list_conversations(**kwargs):
        calls.append(kwargs)
        if kwargs.get("before_session_id") == "session-b":
            return sessions[2:]
        return sessions

    fake_server.list_conversations = list_conversations
    with TestClient(api_server.app) as client:
        first = client.get(
            "/sessions",
            headers={"X-API-Key": "scoped-key"},
            params={"limit": 2, "user_id": "untrusted-user"},
        )
        cursor = first.json()["next_cursor"]
        second = client.get(
            "/sessions",
            headers={"X-API-Key": "scoped-key"},
            params={
                "limit": 2,
                "before_updated_at": cursor["updated_at"],
                "before_session_id": cursor["session_id"],
            },
        )
        partial_cursor = client.get(
            "/sessions",
            headers={"X-API-Key": "scoped-key"},
            params={"before_session_id": "session-b"},
        )

    assert first.status_code == 200
    assert [row["session_id"] for row in first.json()["sessions"]] == [
        "session-c",
        "session-b",
    ]
    assert first.json()["has_more"] is True
    assert cursor == {
        "updated_at": "2026-10-19T12:00:00+00:00",
        "session_id": "session-b",
    }
    assert second.status_code == 200
    assert [row["session_id"] for row in second.json()["sessions"]] == ["session-a"]
    assert second.json()["has_more"] is False
    assert calls[0]["limit"] == 3
    assert calls[0]["user_id"] == "gateway-user"
    assert calls[0]["tenant_id"] == "tenant-a"
    assert calls[0]["before_updated_at"] is None
    assert calls[1]["before_updated_at"] == cursor["updated_at"]
    assert calls[1]["before_session_id"] == cursor["session_id"]
    assert partial_cursor.status_code == 422


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


def test_conversation_feedback_uses_authenticated_scope_and_hides_reason(
    monkeypatch, fake_server,
):
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

    def submit_feedback(**kwargs):
        calls.append(kwargs)
        return True

    fake_server.submit_conversation_feedback = submit_feedback
    with TestClient(api_server.app) as client:
        response = client.post(
            "/sessions/session-a/turns/turn-a/feedback",
            headers={"X-API-Key": "scoped-key"},
            json={
                "rating": "negative",
                "reason": "结果缺少预算说明",
            },
        )

    assert response.status_code == 200, response.text
    assert response.json() == {
        "saved": True,
        "session_id": "session-a",
        "turn_id": "turn-a",
        "rating": "negative",
    }
    assert calls == [{
        "session_id": "session-a",
        "turn_id": "turn-a",
        "rating": "negative",
        "reason": "结果缺少预算说明",
        "user_id": "gateway-user",
        "tenant_id": "tenant-a",
    }]


def test_conversation_feedback_rejects_invalid_rating_and_unauthorized_principal(
    monkeypatch, fake_server,
):
    monkeypatch.setenv(
        "AD_AGENT_API_KEY_PRINCIPALS",
        json.dumps({
            "readless-key": {
                "user_id": "gateway-user",
                "tenant_id": "tenant-a",
                "permissions": ["ads.plan"],
            }
        }),
    )
    calls = []
    fake_server.submit_conversation_feedback = lambda **kwargs: calls.append(kwargs)

    with TestClient(api_server.app) as client:
        invalid = client.post(
            "/sessions/session-a/turns/turn-a/feedback",
            headers={"X-API-Key": "readless-key"},
            json={"rating": "maybe"},
        )
        denied = client.post(
            "/sessions/session-a/turns/turn-a/feedback",
            headers={"X-API-Key": "readless-key"},
            json={"rating": "positive"},
        )

    assert invalid.status_code == 422
    assert denied.status_code == 403
    assert calls == []


def test_feedback_trend_uses_authenticated_scope_and_supported_windows(
    monkeypatch, fake_server,
):
    monkeypatch.setenv(
        "AD_AGENT_API_KEY_PRINCIPALS",
        json.dumps({
            "scoped-key": {
                "user_id": "gateway-user",
                "tenant_id": "tenant-a",
                "permissions": ["ads.read"],
            },
            "readless-key": {
                "user_id": "other-user",
                "tenant_id": "tenant-a",
                "permissions": ["ads.plan"],
            },
        }),
    )
    calls = []

    def get_feedback_trend(**kwargs):
        calls.append(kwargs)
        return {
            "days": kwargs["days"],
            "total": 1,
            "positive": 1,
            "negative": 0,
            "positive_rate": 1.0,
            "daily": [{
                "date": "2026-10-20",
                "positive": 1,
                "negative": 0,
                "total": 1,
            }],
        }

    fake_server.get_conversation_feedback_trend = get_feedback_trend
    with TestClient(api_server.app) as client:
        response = client.get(
            "/feedback/trend?days=7",
            headers={"X-API-Key": "scoped-key"},
        )
        unsupported_window = client.get(
            "/feedback/trend?days=14",
            headers={"X-API-Key": "scoped-key"},
        )
        denied = client.get(
            "/feedback/trend?days=30",
            headers={"X-API-Key": "readless-key"},
        )

    assert response.status_code == 200, response.text
    assert response.json()["total"] == 1
    assert "reason" not in response.text
    assert "session_id" not in response.text
    assert unsupported_window.status_code == 422
    assert denied.status_code == 403
    assert calls == [{
        "days": 7,
        "user_id": "gateway-user",
        "tenant_id": "tenant-a",
    }]


def test_feedback_review_pages_enforce_permission_scope_and_valid_filters(monkeypatch, fake_server):
    monkeypatch.setenv('AD_AGENT_API_KEY_PRINCIPALS', json.dumps({
        'review-key': {'user_id': 'reviewer', 'tenant_id': 'tenant-a', 'permissions': ['feedback.review']},
        'read-key': {'user_id': 'reader', 'tenant_id': 'tenant-a', 'permissions': ['ads.read']},
    }))
    calls = []

    def page_feedback(filters):
        calls.append(filters)
        return {'items': [{'reason': 'access_token=private-value'}],
                'pagination': {'page': 2, 'limit': 10, 'total': 15, 'pages': 2}}

    fake_server.page_conversation_feedback_review_queue = page_feedback
    with TestClient(api_server.app) as client:
        headers = {'X-API-Key': 'review-key'}
        response = client.get('/feedback/review', headers=headers, params={
            'page': 2, 'limit': 10, 'status': 'all', 'q': '预算', 'tenant_id': 'other',
            'since': '2026-10-01T08:00:00+08:00',
        })
        assert response.status_code == 200
        assert response.json()['pagination']['total'] == 15
        assert 'private-value' not in response.text
        assert calls[0].tenant_id == 'tenant-a'
        assert calls[0].search == '预算'
        assert calls[0].page == 2
        assert calls[0].since == '2026-10-01T00:00:00+00:00'
        denied = client.get('/feedback/review?page=1', headers={'X-API-Key': 'read-key'})
        assert denied.status_code == 403
        for params in [{'page': 0}, {'page': 10001}, {'limit': 101}, {'status': 'invalid'},
                       {'q': 'x'*201}, {'since': 'not-a-date'},
                       {'since': '2026-10-03', 'until': '2026-10-02'}]:
            assert client.get('/feedback/review', params=params, headers=headers).status_code == 422
        assert len(calls) == 1

        def unavailable(filters):
            raise RuntimeError('store unavailable')
        fake_server.page_conversation_feedback_review_queue = unavailable
        assert client.get('/feedback/review?page=1', headers=headers).status_code == 503


def test_feedback_review_requires_permission_and_exports_only_curated_cases(
    monkeypatch, fake_server,
):
    monkeypatch.setenv(
        "AD_AGENT_API_KEY_PRINCIPALS",
        json.dumps({
            "review-key": {
                "user_id": "reviewer-a",
                "tenant_id": "tenant-a",
                "permissions": ["feedback.review"],
            },
            "read-key": {
                "user_id": "reader-a",
                "tenant_id": "tenant-a",
                "permissions": ["ads.read"],
            },
        }),
    )
    queue_calls = []
    review_calls = []

    def list_feedback(*, tenant_id, status, limit):
        queue_calls.append((tenant_id, status, limit))
        return [
            {
                "feedback_id": "feedback-a",
                "tenant_id": tenant_id,
                "review_status": status,
                "user_input": "分析 access_token=private-value 的报表",
                "assistant_reply": "请核对 access_token=private-value",
                "reason": "缺少数据区间",
                "assertions": {"max_tool_calls": 1},
                "expected_behavior": (
                    "先说明统计日期，且不得回显 access_token=private-value"
                    if status == "candidate" else ""
                ),
            },
            {
                "feedback_id": "feedback-incomplete",
                "review_status": "candidate",
                "user_input": "不应导出",
                "assistant_reply": "未完成审核",
                "reason": "",
                "expected_behavior": "",
            },
        ]

    def review_feedback(feedback_id, **kwargs):
        review_calls.append((feedback_id, kwargs))
        return True

    fake_server.list_conversation_feedback_review_queue = list_feedback
    fake_server.review_conversation_feedback = review_feedback
    with TestClient(api_server.app) as client:
        denied = client.get(
            "/feedback/review?status=pending",
            headers={"X-API-Key": "read-key"},
        )
        queue = client.get(
            "/feedback/review?status=pending&limit=20",
            headers={"X-API-Key": "review-key"},
        )
        reviewed = client.put(
            "/feedback/review/feedback-a",
            headers={"X-API-Key": "review-key"},
            json={
                "review_status": "candidate",
                "expected_behavior": "先说明统计区间，再解释指标。",
            },
        )
        exported = client.get(
            "/feedback/regression-cases/export",
            headers={"X-API-Key": "review-key"},
        )

    assert denied.status_code == 403
    assert queue.status_code == 200
    assert "private-value" not in queue.text
    assert reviewed.status_code == 200
    assert review_calls == [(
        "feedback-a",
        {
            "tenant_id": "tenant-a",
            "reviewer_id": "reviewer-a",
            "review_status": "candidate",
            "expected_behavior": "先说明统计区间，再解释指标。",
            "assertions": {},
        },
    )]
    assert exported.status_code == 200
    assert exported.headers["content-type"].startswith("application/json")
    export_payload = exported.json()
    assert len(export_payload["cases"]) == 1
    assert export_payload["cases"][0]["input"].startswith("分析")
    assert export_payload["cases"][0]["expected_behavior"].startswith("先说明")
    assert export_payload["cases"][0]["runnable"] is True
    assert export_payload["cases"][0]["assertions"] == {"max_tool_calls": 1}
    assert "feedback_id" not in exported.text
    assert "reviewer-a" not in exported.text
    assert "private-value" not in exported.text
    assert queue_calls == [
        ("tenant-a", "pending", 20),
        ("tenant-a", "candidate", 100),
    ]


def test_knowledge_semantic_index_endpoints_use_explicit_tenant_permissions(
    monkeypatch, fake_server,
):
    monkeypatch.setenv(
        "AD_AGENT_API_KEY_PRINCIPALS",
        json.dumps({
            "read-key": {
                "user_id": "reader-a",
                "tenant_id": "tenant-a",
                "permissions": ["knowledge.read"],
            },
            "write-key": {
                "user_id": "operator-a",
                "tenant_id": "tenant-a",
                "permissions": ["knowledge.write"],
            },
            "other-tenant-key": {
                "user_id": "operator-b",
                "tenant_id": "tenant-b",
                "permissions": ["knowledge.write"],
            },
        }),
    )
    status_calls = []
    rebuild_calls = []
    fake_server.get_knowledge_semantic_index_status = lambda *, tenant_id: (
        status_calls.append(tenant_id)
        or {"tenant_id": tenant_id, "configured": True, "current": True}
    )
    fake_server.rebuild_knowledge_semantic_index = lambda *, tenant_id: (
        rebuild_calls.append(tenant_id)
        or {"tenant_id": tenant_id, "available": True}
    )

    with TestClient(api_server.app) as client:
        status = client.get(
            "/knowledge/semantic-index/status",
            headers={"X-API-Key": "read-key"},
        )
        denied_read = client.get(
            "/knowledge/semantic-index/status",
            headers={"X-API-Key": "write-key"},
        )
        rebuilt = client.post(
            "/knowledge/semantic-index/rebuild",
            headers={"X-API-Key": "write-key"},
        )
        other_tenant_rebuild = client.post(
            "/knowledge/semantic-index/rebuild",
            headers={"X-API-Key": "other-tenant-key"},
        )

    assert status.status_code == 200
    assert status.json()["tenant_id"] == "tenant-a"
    assert denied_read.status_code == 403
    assert rebuilt.status_code == 200
    assert rebuilt.json()["tenant_id"] == "tenant-a"
    assert other_tenant_rebuild.status_code == 200
    assert status_calls == ["tenant-a"]
    assert rebuild_calls == ["tenant-a", "tenant-b"]


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
    from agents.applications.advertising.composition.ad_application import AdvertisingComposition
    from agents.applications.advertising.persistence.store import AdAgentStore

    store = AdAgentStore(":memory:")
    managed_runtime = AdvertisingComposition(
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
    from agents.applications.advertising.persistence.store import AdAgentStore

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


def test_template_creation_context_survives_chat_followup_and_confirmation():
    from agents.tests.advertising.test_google_confirmation_flow import (
        test_confirmation_frontend_regressions,
    )

    static = api_server.STATIC_PATH / "js"
    blueprint_editor = (static / "chat-blueprint-editor.js").read_text(
        encoding="utf-8",
    )
    creation = (static / "chat-creation.js").read_text(encoding="utf-8")

    assert "creation_template_id: blueprintState.templates.find(" in blueprint_editor
    assert "pendingBlueprintRequest = creationContextForCard(card)" in creation
    assert "creation_template_id: card.template_id || null" in creation
    test_confirmation_frontend_regressions()


def test_history_cards_restore_as_launchers_without_opening_workbench():
    html = _chat_page_javascript()
    assert "function renderUiCards(ui, options = {})" in html
    assert "const openWorkbench = options.openWorkbench !== false;" in html
    assert "if (openWorkbench && typeof renderCreationCardInWorkbench === 'function')" in html
    assert "openWorkbench: false" in html
    assert "function clearCreationWorkbenchDraft()" in html
    assert "clearCreationWorkbenchDraft();" in html


def test_creation_card_uses_provider_resource_hierarchy_for_all_field_groups():
    html = _chat_page_javascript()
    assert "function creationFieldGroups(fields)" in html
    assert "blueprintHierarchyInfo(field)" in html
    assert "BLUEPRINT_HIERARCHY_GROUPS" in html
    assert "CREATION_FIELD_GROUPS" not in html
    for resource_level in ("Campaign", "Ad Set", "Ad Group", "Line Item", "Asset Group", "Product Group", "Ad", "Creative"):
        assert resource_level in html
    assert "系列基础" not in html
    assert "受众与版位" not in html
    assert "素材与落地页" not in html
    assert "转化与追踪" not in html
    assert "高级设置" not in html


def test_workbench_is_on_demand_and_normalizes_generic_harness_events():
    """The browser must not reserve the workbench for empty or query turns."""
    html = (
        api_server.TEMPLATE_PATH.read_text(encoding="utf-8")
        + "\n"
        + _chat_page_javascript()
        + "\n"
        + _chat_page_styles()
    )
    assert "body:not(.workbench-open)" in html
    assert "function closeAgentWorkbench()" in html
    assert "tool_execution_start" in html
    assert "tool_execution_end" in html
    assert "function normalizeExecutionEvent" in html
    assert "shouldOpenTraceForEvent" not in html
    assert "function openTraceWorkbench()" in html
    assert 'onclick="openTraceWorkbench()"' in html


def test_chat_renders_scoped_account_choices_and_avoids_false_creation_fallback():
    javascript = _chat_page_javascript()

    assert "function renderAccountSelection" in javascript
    assert "ui?.account_selection" in javascript
    assert "data-account-id" in javascript
    assert "account_id: selectedId" in javascript
    assert "暂时无法确认本次执行结果" in javascript
    assert "已整理好这次广告创建需要的参数" not in javascript


def test_workspace_does_not_present_unavailable_live_preference_as_executable():
    javascript = _chat_page_javascript()

    assert "liveSelected && !workspaceMode.liveAvailable" in javascript
    assert "live · 不可用" in javascript
    assert "live 写入当前不可用" in javascript
    assert "liveOption.disabled = !liveAvailable" in javascript


def test_chat_template_busts_cached_assets_after_conversation_ui_changes():
    template = api_server.workspace_assets.page(api_server.TEMPLATE_PATH).body.decode()
    bootstrap = (
        api_server.STATIC_PATH / "js" / "chat.js"
    ).read_text(encoding="utf-8")

    css_version = re.search(
        r'href="/static/css/chat\.css\?v=([^"]+)"',
        template,
    )
    js_version = re.search(
        r'src="/static/js/chat\.js\?v=([^"]+)"',
        template,
    )

    assert css_version is not None
    assert js_version is not None
    assert css_version.group(1) == js_version.group(1)
    assert js_version.group(1) == api_server.workspace_assets.version
    assert "document.currentScript.src" in bootstrap
    assert "?v=${version}" in bootstrap


def test_chat_template_uses_shared_access_without_service_key_ui():
    template = api_server.TEMPLATE_PATH.read_text(encoding="utf-8")
    javascript = _chat_page_javascript()
    requests = (
        api_server.STATIC_PATH / "js" / "chat-requests.js"
    ).read_text(encoding="utf-8")
    settings = (
        api_server.STATIC_PATH / "js" / "chat-settings.js"
    ).read_text(encoding="utf-8")

    assert 'id="serviceAuthButton"' not in template
    assert 'id="serviceAuthOverlay"' not in template
    assert 'id="serviceApiKeyInput"' not in template
    assert "sessionStorage" not in requests
    assert "headers.set('X-API-Key'" not in requests
    assert "headers.delete('X-API-Key')" in requests
    assert "async function serviceFetch(" in requests
    assert 'id="skillApiKey"' not in template
    assert 'id="knowledgeApiKey"' not in template
    assert 'id="agentSettingsOverlay"' in template
    assert 'id="agentModelForm"' in template
    assert 'id="agentProviderForm"' in template
    assert "function saveAgentModelProfile(event)" in javascript
    assert "function saveAgentProviderCredentials(event)" in javascript
    assert "input.value = profile.api_key" not in settings


def test_pending_chat_media_is_positioned_above_the_input_box():
    template = api_server.TEMPLATE_PATH.read_text(encoding="utf-8")
    input_area = template.split('<div class="input-area">', 1)[1].split(
        '<aside class="right-panel"', 1
    )[0]

    assert input_area.index('id="chatMediaPending"') < input_area.index(
        'class="input-container"'
    )


def test_chat_markdown_dependencies_load_before_messages_and_history():
    bootstrap = (api_server.STATIC_PATH / "js" / "chat.js").read_text(encoding="utf-8")
    assert bootstrap.index("vendor/marked-18.1.1.umd.js") < bootstrap.index("chat-markdown.js")
    assert bootstrap.index("vendor/purify-3.4.17.min.js") < bootstrap.index("chat-markdown.js")
    assert bootstrap.index("chat-markdown.js") < bootstrap.index("chat-requests.js")
    messages = (api_server.STATIC_PATH / "js" / "chat-messages.js").read_text(encoding="utf-8")
    history = (api_server.STATIC_PATH / "js" / "chat-requests.js").read_text(encoding="utf-8")
    assert "formatContent(content)" in messages
    assert "function formatContent(" not in messages
    assert "markdownPreview(conversation.preview)" in history


def test_mermaid_diagrams_use_a_lazy_local_renderer_and_svg_sanitizer():
    markdown = (
        api_server.STATIC_PATH / "js" / "chat-markdown.js"
    ).read_text(encoding="utf-8")
    vendor = (
        api_server.STATIC_PATH / "js" / "vendor" / "mermaid-tiny-12.2.0.js"
    )
    license_file = vendor.with_name("mermaid-tiny-12.2.0.LICENSE")

    assert "vendor/mermaid-tiny-12.2.0.js" in markdown
    assert "securityLevel: 'strict'" in markdown
    assert "DOMPurify.sanitize(result.svg" in markdown
    assert vendor.is_file()
    assert license_file.is_file()


def test_mermaid_inline_preview_has_readable_width_and_non_overlapping_zoom_control():
    styles = (
        api_server.STATIC_PATH / "css" / "chat-markdown.css"
    ).read_text(encoding="utf-8")

    assert ".message.agent:has(.mermaid-diagram)" in styles
    assert "align-self: stretch" in styles
    assert ".mermaid-diagram-zoom" in styles
    assert "position: static" in styles


def test_chat_svg_previews_are_sanitized_and_connected_to_agent_messages():
    markdown = (
        api_server.STATIC_PATH / "js" / "chat-markdown.js"
    ).read_text(encoding="utf-8")
    messages = (
        api_server.STATIC_PATH / "js" / "chat-messages.js"
    ).read_text(encoding="utf-8")
    styles = (
        api_server.STATIC_PATH / "css" / "chat-markdown.css"
    ).read_text(encoding="utf-8")

    assert "function sanitizeSvgSource(source)" in markdown
    assert "USE_PROFILES: { svg: true }" in markdown
    assert "FORBID_TAGS" in markdown and "foreignObject" in markdown
    assert "removeUnsafeSvgReferences(sanitized)" in markdown
    assert "renderSvgImages(" in messages
    assert ".svg-image-preview-artwork svg" in styles
    assert ".svg-image-source-details" in styles


def test_chat_messages_embed_supported_facebook_video_links_in_replayed_history():
    messages = (
        api_server.STATIC_PATH / "js" / "chat-messages.js"
    ).read_text(encoding="utf-8")
    media = (
        api_server.STATIC_PATH / "js" / "chat-media.js"
    ).read_text(encoding="utf-8")

    assert "renderFacebookVideoEmbeds(" in messages
    assert "msg.querySelector('.message-body')" in messages
    assert "facebookVideoPermalinksFromText(content)" in media
    assert "chatFacebookVideoFrame(facebookPermalink)" in media


def test_conversation_replay_does_not_render_internal_tool_or_system_messages():
    history = (api_server.STATIC_PATH / "js" / "chat-requests.js").read_text(encoding="utf-8")
    assert "if (!['user', 'assistant'].includes(message.role)) continue;" in history
    assert "restoreExecutionTrace(data.execution_traces)" in history


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


def test_confirmed_chat_without_tool_execution_cannot_claim_success(fake_server):
    fake_server.run = lambda **_kwargs: {
        "success": True,
        "status": "succeeded",
        "reply": "已完成更新，updated_count: 1",
        "results": [],
        "tool_call_count": 0,
    }
    with TestClient(api_server.app) as client:
        response = client.post(
            "/chat",
            headers={"X-API-Key": "test-key"},
            json={
                "user_input": "更新测试 Campaign 名称",
                "confirmed": True,
                "confirmation_payload": {
                    "type": "confirm_write",
                    "confirmation_token": "test-confirmation-token",
                },
            },
        )
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is False
    assert payload["status"] == "failed"
    assert "未执行" in payload["reply"]
    assert "updated_count" not in payload["reply"]


def test_confirmed_stream_without_tool_execution_cannot_claim_success(fake_server):
    fake_server.run = lambda **_kwargs: {
        "success": True,
        "status": "succeeded",
        "reply": "已完成更新",
        "results": [],
        "tool_call_count": 0,
    }
    with TestClient(api_server.app) as client:
        response = client.post(
            "/chat/stream",
            headers={"X-API-Key": "test-key"},
            json={
                "user_input": "更新测试 Campaign 名称",
                "confirmed": True,
                "confirmation_payload": {
                    "type": "confirm_write",
                    "confirmation_token": "test-confirmation-token",
                },
            },
        )
    events = [
        json.loads(line.removeprefix("data: "))
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]
    reply = next(event for event in events if event["type"] == "reply")
    assert reply["status"] == "failed"
    assert "未执行" in reply["content"]
    assert events[-1]["status"] == "failed"


def test_confirmed_single_tool_resumes_the_signed_tool_choice():
    from agents.applications.advertising.run.ad_run_service import AdvertisingRunService

    service = AdvertisingRunService.__new__(AdvertisingRunService)
    payload = {"type": "confirm_write", "tool": "tiktok_update_ad"}
    assert service._initial_tool_choice(
        None, None, True, payload, ["tiktok_update_ad"]
    ) == {"type": "function", "function": {"name": "tiktok_update_ad"}}
    assert service._initial_tool_choice(
        None, None, True, payload, ["meta_update_ad"]
    ) is None
    assert service._initial_tool_choice(
        None, None, False, payload, ["tiktok_update_ad"]
    ) is None


def test_confirmed_chain_resumes_only_allowlisted_pending_tool():
    from agents.applications.advertising.run.ad_run_service import AdvertisingRunService

    service = AdvertisingRunService.__new__(AdvertisingRunService)
    payload = {
        "type": "confirm_write_plan",
        "preview": {"pending_tool": "meta_create_traffic_ad"},
    }
    expected = {"type": "function", "function": {"name": "meta_create_traffic_ad"}}
    assert service._initial_tool_choice(
        None, None, True, payload, ["meta_create_traffic_ad"]
    ) == expected
    assert service._initial_tool_choice(
        None, None, True, payload, ["meta_create_campaign"]
    ) is None
    assert service._initial_tool_choice(
        None, None, False, payload, ["meta_create_traffic_ad"]
    ) is None
    assert service._initial_tool_choice(None, None, True, payload, None) is None


def test_chat_returns_only_the_top_level_confirmation_token_unredacted(fake_server):
    confirmation_payload = {
        "type": "confirm_write",
        "confirmation_token": "one-time-confirmation-token",
        "account_id": "test-account",
    }
    fake_server.run = lambda **_kwargs: {
        "success": True,
        "needs_confirmation": True,
        "confirmation_payload": confirmation_payload,
        "results": [{
            "needs_confirmation": True,
            "confirmation_payload": confirmation_payload,
            "data": {"access_token": "provider-token"},
        }],
        "messages": [{
            "metadata": {"confirmation_payload": confirmation_payload},
        }],
    }

    with TestClient(api_server.app) as client:
        response = client.post(
            "/chat",
            headers={"X-API-Key": "test-key"},
            json={"user_input": "create test campaign"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert (
        payload["confirmation_payload"]["confirmation_token"]
        == "one-time-confirmation-token"
    )
    assert response.text.count("one-time-confirmation-token") == 1
    assert (
        api_server.redact_for_persistence(confirmation_payload)
        ["confirmation_token"] == "<redacted>"
    )
    assert (
        payload["results"][0]["confirmation_payload"]["confirmation_token"]
        == "<redacted>"
    )
    assert payload["results"][0]["data"]["access_token"] == "<redacted>"
    assert (
        payload["messages"][0]["metadata"]["confirmation_payload"]
        ["confirmation_token"] == "<redacted>"
    )


def test_chat_stream_returns_confirmation_token_only_in_confirmation_field(
    fake_server,
):
    confirmation_payload = {
        "type": "confirm_write",
        "confirmation_token": "one-time-stream-confirmation-token",
        "account_id": "test-account",
    }
    fake_server.run = lambda **_kwargs: {
        "success": True,
        "needs_confirmation": True,
        "confirmation_payload": confirmation_payload,
        "reply": "Waiting for confirmation",
        "results": [{
            "tool": "test_create_campaign",
            "needs_confirmation": True,
            "confirmation_payload": confirmation_payload,
        }],
    }

    with TestClient(api_server.app) as client:
        response = client.post(
            "/chat/stream",
            headers={"X-API-Key": "test-key"},
            json={"user_input": "create test campaign"},
        )

    assert response.status_code == 200
    reply = next(
        json.loads(line.removeprefix("data: "))
        for line in response.text.splitlines()
        if line.startswith("data: ")
        and '"type": "reply"' in line
    )
    assert (
        reply["confirmation_payload"]["confirmation_token"]
        == "one-time-stream-confirmation-token"
    )
    assert response.text.count("one-time-stream-confirmation-token") == 1
    assert "confirmation_payload" not in reply["results"][0]


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


def test_chat_stream_reports_runtime_failure_instead_of_success(fake_server):
    def run(**kwargs):
        kwargs["event_callback"]({
            "type": "done",
            "event_type": "done",
            "status": "succeeded",
        })
        return {
            "status": "failed",
            "success": False,
            "reply": "账户范围校验未通过。",
            "results": [],
        }

    fake_server.run = run
    with TestClient(api_server.app) as client:
        response = client.post(
            "/chat/stream",
            headers={"X-API-Key": "test-key"},
            json={"user_input": "创建 Meta campaign"},
        )

    events = [
        json.loads(line.removeprefix("data: "))
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]
    reply = next(item for item in events if item["type"] == "reply")
    done = next(item for item in events if item["type"] == "done")
    assert reply["status"] == "failed"
    assert done["status"] == "failed"


def test_chat_stream_does_not_hide_failed_tool_behind_succeeded_run(fake_server):
    fake_server.run = lambda **_kwargs: {
        "status": "succeeded",
        "reply": "已完成。",
        "results": [{
            "tool": "meta_list_campaigns",
            "success": False,
            "error": "account scope denied",
        }],
    }
    with TestClient(api_server.app) as client:
        response = client.post(
            "/chat/stream",
            headers={"X-API-Key": "test-key"},
            json={"user_input": "查询 Meta campaign"},
        )

    events = [
        json.loads(line.removeprefix("data: "))
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]
    reply = next(item for item in events if item["type"] == "reply")
    done = next(item for item in events if item["type"] == "done")
    assert reply["status"] == "failed"
    assert done["status"] == "failed"


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


@pytest.mark.parametrize("user_input,language,summary", [
    ("执行这个任务", "zh", "正在梳理请求目标"),
    ("Please query the reports.", "en", "Clarifying the request"),
])
def test_chat_stream_forwards_model_lifecycle_but_never_model_deltas(
    fake_server, user_input, language, summary,
):
    received = {}
    protocol_text = (
        "<|tool_calls_section_end|> API Error: channel_id=\"\" "
        "error_code=40400 message=invalid_user_id "
        "<|tool_call_begin|> agent-platform:knowledge_search "
        "<|tool_call_argument_begin|>{\"query\":\"Meta Canvas\"}"
        "<|tool_call_end|>"
    )
    fake_server.registry.get = lambda _name: (
        SimpleNamespace(
            intent_aliases=["知识库检索", "search knowledge base"],
            intent_types=["knowledge_search"],
            namespace="agent_platform",
            resource_type="knowledge",
            action="search",
        ),
        object(),
    )

    def run(**kwargs):
        received.update(kwargs)
        observe = kwargs["event_callback"]
        observe({
            "type": "model_start",
            "provider": "configured-model",
            "provider_index": 0,
            "attempt": 1,
        })
        observe({
            "type": "model_delta",
            "delta": protocol_text,
        })
        observe({
            "type": "model_reasoning_delta",
            "delta": "The user is asking to query reports. Private scratchpad.",
        })
        observe({
            "type": "model_end",
            "provider": "configured-model",
            "provider_index": 0,
            "usage": {"input_tokens": 12, "output_tokens": 4},
        })
        observe({
            "type": "tool_execution_start",
            "tool_name": "agent_knowledge_search",
            "arguments": {"query": "private query text"},
        })
        return {"status": "failed", "reply": protocol_text, "results": []}

    fake_server.run = run
    with TestClient(api_server.app) as client:
        response = client.post(
            "/chat/stream",
            headers={"X-API-Key": "test-key"},
            json={"user_input": user_input},
        )

    assert response.status_code == 200
    assert callable(received["event_callback"])
    assert received["streaming"] is True
    assert '"type": "model_start"' in response.text
    assert '"type": "model_end"' in response.text
    assert '"type": "reasoning_delta"' in response.text
    assert '"content_type": "execution_summary"' in response.text
    assert f'"language_code": "{language}"' in response.text
    assert summary in response.text
    assert (
        ("知识库检索" if language == "zh" else "search knowledge base")
        in response.text
    )
    summary_events = [
        json.loads(line.removeprefix("data: "))
        for line in response.text.splitlines()
        if line.startswith("data: ")
        and '"content_type": "execution_summary"' in line
    ]
    assert all("private query text" not in item["content"] for item in summary_events)
    assert "Private scratchpad" not in response.text
    assert "<|tool_" not in response.text
    assert "API Error:" not in response.text
    assert "40400 / invalid_user_id" in response.text
    assert "本次知识检索未执行" in response.text


@pytest.mark.parametrize("path,method,nested", [
    ("/sessions/session-a", "get_conversation", True),
    ("/sessions/session-a/runs/latest", "get_latest_run", False),
    ("/runs/run-a/events?after_seq=1", "get_run_events", False),
])
def test_public_history_filters_private_deltas_without_losing_cursor(
    fake_server, monkeypatch, path, method, nested,
):
    monkeypatch.setenv("AD_AGENT_API_KEY_PRINCIPALS", json.dumps({
        "scoped-key": {
            "user_id": "operator", "tenant_id": "tenant",
            "permissions": ["ads.read"],
        },
    }))
    events = [
        {"type": "model_start", "seq": 1},
        {"type": "model_reasoning_delta", "delta": "private-scratchpad", "seq": 2},
        {"type": "model_delta", "delta": "private-model-text", "seq": 3},
    ]
    stored = {"events": events, "latest_seq": 3}
    if nested:
        stored = {"execution_traces": {"turn-a": stored}, "messages": []}
    seen = []

    def read(**kwargs):
        seen.append(kwargs)
        return stored

    setattr(fake_server, method, read)
    with TestClient(api_server.app) as client:
        response = client.get(path, headers={"X-API-Key": "scoped-key"})
    assert response.status_code == 200
    assert "private-scratchpad" not in response.text
    assert "private-model-text" not in response.text
    view = response.json()["execution_traces"]["turn-a"] if nested else response.json()
    assert view["latest_seq"] == 3
    assert [event["seq"] for event in view["events"]] == [1]
    assert len(events) == 3
    assert seen[0]["user_id"] == "operator"
    assert seen[0]["tenant_id"] == "tenant"


def test_schedule_run_list_is_available_as_one_scoped_collection(fake_server, monkeypatch):
    calls = []
    monkeypatch.setenv(
        "AD_AGENT_API_KEY_PRINCIPALS",
        json.dumps({
            "test-key": {
                "user_id": "ad-agent-service",
                "tenant_id": "default",
                "permissions": ["ads.read", "ads.plan"],
            }
        }),
    )
    fake_server.list_schedule_runs = lambda **kwargs: (
        calls.append(kwargs) or [{
            "schedule_run_id": "run-1",
            "schedule_id": "schedule-1",
            "status": "queued",
        }]
    )
    fake_server.run_schedule_now = lambda schedule_id, **kwargs: {
        "task": {"task_id": "task-1", "status": "queued"},
        "run": {"schedule_id": schedule_id, "task_id": "task-1", "status": "queued"},
        "created": True,
    }
    with TestClient(api_server.app) as client:
        response = client.get(
            "/schedule-runs?limit=25",
            headers={"X-API-Key": "test-key"},
        )
        run_response = client.post(
            "/schedules/schedule-1/run-now",
            headers={"X-API-Key": "test-key"},
        )
    assert response.status_code == 200
    assert response.json()["runs"][0]["schedule_run_id"] == "run-1"
    assert calls == [{
        "user_id": "ad-agent-service",
        "tenant_id": "default",
        "limit": 25,
    }]
    assert run_response.status_code == 200
    assert run_response.json()["task"]["task_id"] == "task-1"
    assert run_response.json()["run"]["schedule_id"] == "schedule-1"


def test_schedule_patch_uses_authenticated_scope_and_returns_updated_record(
    fake_server, monkeypatch,
):
    calls = []
    monkeypatch.setenv(
        "AD_AGENT_API_KEY_PRINCIPALS",
        json.dumps({
            "test-key": {
                "user_id": "operator-1",
                "tenant_id": "tenant-1",
                "permissions": ["ads.read", "ads.plan"],
            }
        }),
    )
    fake_server.update_schedule = lambda schedule_id, **kwargs: (
        calls.append((schedule_id, kwargs))
        or {
            "schedule_id": schedule_id,
            "tenant_id": kwargs["tenant_id"],
            "user_id": kwargs["user_id"],
            "name": kwargs["name"],
            "prompt": kwargs["prompt"],
            "cron_expression": kwargs["cron_expression"],
            "timezone": kwargs["timezone"],
        }
    )
    with TestClient(api_server.app) as client:
        response = client.patch(
            "/schedules/schedule-1",
            headers={"X-API-Key": "test-key"},
            json={
                "name": "Weekly report",
                "prompt": "Summarize paid campaign results",
                "cron_expression": "0 10 * * 1",
                "timezone": "America/Los_Angeles",
            },
        )

    assert response.status_code == 200
    assert response.json()["schedule"]["name"] == "Weekly report"
    assert calls == [(
        "schedule-1",
        {
            "name": "Weekly report",
            "prompt": "Summarize paid campaign results",
            "cron_expression": "0 10 * * 1",
            "timezone": "America/Los_Angeles",
            "user_id": "operator-1",
            "tenant_id": "tenant-1",
        },
    )]


def test_schedule_pages_and_detail_use_principal_scope(fake_server, monkeypatch):
    monkeypatch.setenv('AD_AGENT_API_KEY_PRINCIPALS', json.dumps({
        'test-key': {'user_id':'operator', 'tenant_id':'tenant', 'permissions':['ads.read']},
    }))
    calls = []
    fake_server.page_schedules = lambda filters: calls.append(filters) or {
        'schedules': [], 'pagination': {'page': filters.page, 'total': 0},
    }
    fake_server.page_schedule_runs = lambda filters: calls.append(filters) or {'runs': []}
    fake_server.get_schedule = lambda schedule_id, **scope: (
        {'schedule_id': schedule_id, 'name':'Task'} if schedule_id == 'mine' else None
    )
    fake_server.list_schedule_runs = lambda **kwargs: pytest.fail('unexpected eager run load')
    fake_server.get_schedule_run = lambda schedule_id, run_id, **scope: (
        calls.append((schedule_id, run_id, scope)) or {'schedule_run_id':run_id}
    )
    headers = {'X-API-Key':'test-key'}
    with TestClient(api_server.app) as client:
        response = client.get('/schedules?page=2&limit=10&q=日报&status=paused&tenant_id=other', headers=headers)
        assert response.status_code == 200
        filters = calls[-1]
        assert (filters.tenant_id, filters.user_id, filters.page, filters.search) == (
            'tenant', 'operator', 2, '日报',
        )
        assert filters.statuses == ('paused',)
        response = client.get('/schedules/mine?include_runs=false', headers=headers)
        assert response.status_code == 200 and 'runs' not in response.json()
        response = client.get('/schedules/mine/runs?page=1&status=failed&since=2026-10-01T08:00:00%2B08:00', headers=headers)
        assert response.status_code == 200
        assert calls[-1].since == '2026-10-01T00:00:00+00:00'
        assert calls[-1].schedule_id == 'mine'
        count = len(calls)
        assert client.get('/schedules/other/runs?page=1', headers=headers).status_code == 404
        assert len(calls) == count
        assert client.get('/schedules?page=0', headers=headers).status_code == 422
        assert client.get('/schedules/mine/runs?page=1&since=invalid', headers=headers).status_code == 422
        assert client.get('/schedules/mine/runs/r-1', headers=headers).status_code == 200
        assert calls[-1] == ('mine', 'r-1', {'tenant_id':'tenant','user_id':'operator'})


def test_chat_progress_and_schedule_ui_node_contracts():
    javascript_tests = [
        Path(__file__).parent / "static" / "test_chat_trace_progress.js",
        Path(__file__).parent / "static" / "test_chat_gap_workflows.js",
    ]
    subprocess.run(
        ["node", "--test", *(str(test) for test in javascript_tests)],
        check=True,
        timeout=30,
    )


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
                "creation_template_id": "google-test-search",
            },
        )
    assert response.status_code == 200
    assert fake_server.calls[-1]["creation_blueprint_id"] == "google-ads.search"
    assert fake_server.calls[-1]["creation_blueprint_version"] == "1.0.0"
    assert fake_server.calls[-1]["creation_template_id"] == "google-test-search"


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
    monkeypatch.setenv(
        "AD_AGENT_CREATIVE_ASSET_PATH",
        str(tmp_path / "creative-assets"),
    )
    monkeypatch.setenv("OPENAI_API_KEY", "test-llm-key")
    monkeypatch.setenv("GOOGLE_PAGESPEED_API_KEY", "test-pagespeed-key")
    pagespeed_configuration = []
    actual_pagespeed_source = api_server.public_site_quality_tool_source

    def capture_pagespeed_configuration(**kwargs):
        pagespeed_configuration.append(kwargs.get("api_key"))
        return actual_pagespeed_source(**kwargs)

    monkeypatch.setattr(
        api_server,
        "public_site_quality_tool_source",
        capture_pagespeed_configuration,
    )
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
        "agent-platform", "advertising", "meta", "google-ads", "tiktok", "dv360",
        "creative-media", "public-calendar", "public-economics", "public-finance",
        "public-environment", "public-knowledge", "public-research", "public-trends",
        "public-weather", "public-app-research", "public-site-quality",
            "data-analysis", "marketing-analytics",
    }
    definitions = runtime.registry.list_all()
    assert any(item.name == "agent_chat_table_analyze" for item in definitions)
    assert len(definitions) >= 128
    assert {
        "creative_generate_image",
        "creative_submit_video",
        "creative_check_video",
        "creative_list_assets",
        "public_calendar_bank_holidays",
        "public_economics_country_indicator",
        "public_finance_exchange_rate",
        "public_weather_lookup",
        "public_environment_earthquakes",
        "public_environment_7timer_forecast",
        "public_knowledge_wikipedia_search",
        "public_knowledge_open_library_search",
        "public_research_crossref_search",
        "public_research_arxiv_search",
        "public_trends_hackernews_search",
        "public_app_research_app_store_search",
        "public_app_research_app_store_lookup",
        "public_site_quality_pagespeed",
        "agent_web_fetch",
    } <= {definition.name for definition in definitions}
    assert "creative.generate" in runtime._granted_permissions
    assert "creative-production" in runtime._composition.skill_loader.list_all()
    assert pagespeed_configuration == ["test-pagespeed-key"]
    assert api_server.creative_asset_store.root == (
        tmp_path / "creative-assets"
    ).resolve()
    runtime._session_manager.store.close()


def test_creative_asset_route_is_mounted_in_api_server():
    routes = list(api_server.app.routes)
    for included in routes:
        original = getattr(included, "original_router", None)
        if original is not None:
            routes.extend(original.routes)

    assert any(
        getattr(route, "path", None) == "/creative/assets/{asset_id}"
        and route.endpoint.__module__
        == "agents.deployments.advertising.api.routes.creative"
        for route in routes
    )


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
    from agents.applications.advertising.composition.ad_application import AdvertisingComposition
    from agents.tools.advertising.providers.tiktok import create_tiktok_tool_source

    runtime = AdvertisingComposition(require_llm=False, offline_mode=True)
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
    from agents.applications.advertising.composition.ad_application import AdvertisingComposition
    from agents.tools.advertising.providers.tiktok import create_tiktok_tool_source

    runtime = AdvertisingComposition(require_llm=False, offline_mode=True)
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
    from agents.applications.advertising.composition.ad_application import AdvertisingComposition
    from agents.applications.advertising.persistence.store import AdAgentStore

    store = AdAgentStore(str(tmp_path / "skills.db"))
    managed_runtime = AdvertisingComposition(require_llm=False, persistence_store=store, offline_mode=True)
    registered_tool_names = {
        definition.name for definition in managed_runtime.registry.list_all()
    }
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
            "/skills/builtin/google-ads-api-expert/versions/2.1.0",
            headers=headers,
        )
        assert response.status_code == 200
        assert response.json()["editable"] is False
        assert response.json()["files"]["SKILL.md"]["encoding"] == "base64"

    assert "growth-skill" in managed_runtime.get_managed_skills()
    assert {
        definition.name for definition in managed_runtime.registry.list_all()
    } == registered_tool_names
    store.close()


def test_chat_activates_published_skill_for_authenticated_request_tenant(monkeypatch, tmp_path):
    from agents.applications.advertising.composition.ad_application import AdvertisingComposition
    from agents.agent_harness.messages import ModelTurn
    from agents.applications.advertising.persistence.store import AdAgentStore
    from agents.agent_platform.management.skill_management import ManagedSkillManager
    from agents.tests.advertising.harness_models import ScriptedHarnessModel

    store = AdAgentStore(str(tmp_path / "multi-tenant-skills.db"))
    managed_runtime = AdvertisingComposition(
        require_llm=False, persistence_store=store, offline_mode=True
    )
    manager = ManagedSkillManager(store, evaluation_engines=advertising_evaluation_engines())
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

    model = ScriptedHarnessModel(ModelTurn(content="我会遵循当前租户的 Skill 指引。"))
    managed_runtime.platform_application.agent.model = model
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

    assert response.status_code == 200, response.text
    assert model.messages
    assert "tenant-guidance" in "\n".join(
        str(message.content) for message in model.messages[0]
    )
    assert "tenant-guidance" in managed_runtime.get_managed_skills("tenant-b")
    assert manager.activate_published("tenant-b", managed_runtime) == 0
    store.close()
