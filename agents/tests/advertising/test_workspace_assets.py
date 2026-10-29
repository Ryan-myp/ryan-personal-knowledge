from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

from agents.deployments.advertising.workspace_assets import WorkspaceAssets


def fixture_files(tmp_path):
    static = tmp_path / "static"
    (static / "js").mkdir(parents=True)
    (static / "css").mkdir()
    (static / "js/chat.js").write_text("load();")
    (static / "js/chat-state.js").write_text("let oldState = 1;")
    (static / "css/chat.css").write_text(
        "@import url('/static/css/child.css?v=__WORKSPACE_ASSET_VERSION__');"
    )
    (static / "css/child.css").write_text("body { color: black; }")
    template = tmp_path / "chat.html"
    template.write_text('<script src="/static/js/chat.js?v=__WORKSPACE_ASSET_VERSION__"></script>')
    return static, template


def test_asset_version_changes_when_any_dependency_changes(tmp_path):
    static, template = fixture_files(tmp_path)
    first = WorkspaceAssets(static)
    assert first.version == WorkspaceAssets(static).version
    # A dependency changes, even though the loader itself is untouched.
    (static / "js/chat-state.js").write_text("const renderedAssistantTurnIds = new Set();")
    second = WorkspaceAssets(static)
    assert first.version != second.version
    assert second.version in second.page(template).body.decode()
    assert "__WORKSPACE_ASSET_VERSION__" not in second.page(template).body.decode()


def test_page_and_modules_cannot_reuse_unvalidated_browser_cache(tmp_path):
    static, template = fixture_files(tmp_path)
    assets = WorkspaceAssets(static)
    app = FastAPI()
    app.mount("/static", assets)

    @app.get("/")
    def index():
        return assets.page(template)

    with TestClient(app) as client:
        assert client.get("/").headers["cache-control"] == "no-store"
        module = client.get(f"/static/js/chat-state.js?v={assets.version}")
        assert module.headers["cache-control"] == "no-cache"
        unchanged = client.get("/static/js/chat-state.js", headers={"If-None-Match": module.headers["etag"]})
        assert unchanged.status_code == 304
        assert unchanged.headers["cache-control"] == "no-cache"
        style = client.get(f"/static/css/chat.css?v={assets.version}")
        assert f"child.css?v={assets.version}" in style.text
        assert "text/css" in style.headers["content-type"]
        head = client.head(f"/static/css/chat.css?v={assets.version}")
        assert head.content == b""
        assert head.headers["content-length"] == style.headers["content-length"]
        assert client.get("/static/missing.js").status_code == 404


def test_real_page_uses_content_version_for_loader_and_styles():
    root = Path(__file__).resolve().parents[2] / "deployments/advertising"
    assets = WorkspaceAssets(root / "static")
    page = assets.page(root / "templates/chat.html").body.decode()
    assert f'chat.js?v={assets.version}' in page
    assert f'chat.css?v={assets.version}' in page
