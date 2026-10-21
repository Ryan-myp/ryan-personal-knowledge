from __future__ import annotations

import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace

import requests
import pytest

from agents.agent_harness.core.interfaces import ReplayPolicy, RiskLevel, ToolEffect
from agents.agent_harness.core.tool_selection import ToolSelector
from agents.agent_platform.tools import web_fetch as web_fetch_module
from agents.agent_platform.tools.web_fetch import (
    web_fetch_tool_source,
)


class FakeResponse:
    def __init__(self, body=b"", *, status_code=200, headers=None):
        self.status_code = status_code
        self.headers = headers or {"Content-Type": "text/html; charset=utf-8"}
        self.body = body
        self.closed = False

    def iter_content(self, chunk_size):
        for offset in range(0, len(self.body), chunk_size):
            yield self.body[offset:offset + chunk_size]

    def close(self):
        self.closed = True


def _execute(source, arguments):
    binding = source.list_bindings()[0]
    context = SimpleNamespace(
        request=SimpleNamespace(
            principal=SimpleNamespace(
                user_id="user-a",
                tenant_id="tenant-a",
                permissions=frozenset({"ads.read"}),
            ),
        ),
    )
    return binding.executor.execute(context, arguments)


def _source(request_get, resolve_host=None):
    return web_fetch_tool_source(
        required_permission="ads.read",
        request_get=request_get,
        resolve_host=resolve_host or (lambda _host, _port: ["93.184.216.34"]),
    )


def test_web_fetch_registers_a_bounded_read_only_url_tool():
    source = _source(lambda *_args, **_kwargs: FakeResponse())
    definition = source.list_bindings()[0].definition

    assert source.source_id == "agent-platform:web-fetch"
    assert definition.name == "agent_web_fetch"
    assert definition.action == "fetch"
    assert definition.resource_type == "web_page"
    assert definition.intent_types == ["web_fetch"]
    assert definition.risk_level is RiskLevel.LOW
    assert definition.effect_class is ToolEffect.READ
    assert definition.replay_policy is ReplayPolicy.SAFE
    assert definition.required_permissions == ["ads.read"]
    assert definition.input_schema.required == ["url"]
    assert definition.input_schema.additional_properties is False


def test_web_fetch_extracts_wechat_article_body_and_safe_metadata():
    body = """
    <html><head>
      <title>公众号文章标题</title>
      <meta name="description" content="文章摘要">
    </head><body>
      <nav>登录 注册 导航内容</nav>
      <div id="js_content"><p>这是文章正文。</p>
        <p>第二段内容。</p><script>ignore_this_script()</script>
      </div>
    </body></html>
    """.encode()
    response = FakeResponse(body)
    calls = []
    source = _source(
        lambda url, **kwargs: calls.append((url, kwargs)) or response,
    )

    result = _execute(source, {
        "url": "https://mp.weixin.qq.com/s/article-id",
    })

    assert result.success is True, result.error
    assert result.data["title"] == "公众号文章标题"
    assert result.data["description"] == "文章摘要"
    assert "这是文章正文。" in result.data["content"]
    assert "第二段内容。" in result.data["content"]
    assert "ignore_this_script" not in result.data["content"]
    assert "登录 注册 导航内容" not in result.data["content"]
    assert result.data["source_url"] == "https://mp.weixin.qq.com/s/article-id"
    assert calls[0][1]["allow_redirects"] is False
    assert calls[0][1]["stream"] is True
    assert response.closed is True


def test_web_fetch_extracts_semantic_article_and_open_graph_title():
    response = FakeResponse(
        b"""
        <html><head>
          <meta property="og:title" content="Open Graph article">
        </head><body>
          <nav>Top navigation</nav>
          <main><article><h1>Article heading</h1>
            <p>Readable article body.</p>
            <aside>Related links</aside>
          </article></main>
        </body></html>
        """,
    )
    source = _source(lambda *_args, **_kwargs: response)

    result = _execute(source, {"url": "https://public.example/story"})

    assert result.success is True, result.error
    assert result.data["title"] == "Open Graph article"
    assert "Readable article body." in result.data["content"]
    assert "Top navigation" not in result.data["content"]
    assert "Related links" not in result.data["content"]


def test_explicit_article_url_read_selects_fetch_tool():
    source = _source(lambda *_args, **_kwargs: FakeResponse())
    definition = source.list_bindings()[0].definition

    selected = ToolSelector().select_relevant(
        "请读取这个微信公众号文章并总结："
        "https://mp.weixin.qq.com/s/example-article",
        [definition],
    )

    assert [tool.name for tool in selected] == ["agent_web_fetch"]


def test_web_fetch_checks_private_hosts_before_any_network_request():
    requests_made = []
    source = _source(
        lambda *args, **kwargs: requests_made.append((args, kwargs)),
        resolve_host=lambda _host, _port: ["10.0.0.7"],
    )

    result = _execute(source, {"url": "https://private.example/article"})

    assert result.success is False
    assert requests_made == []
    assert "公开" in result.error or "无法访问" in result.error


@pytest.mark.parametrize(
    ("scheme", "port"),
    [("http", 80), ("https", 443)],
)
def test_web_fetch_pins_the_checked_public_ip_for_the_actual_connection(
    monkeypatch, scheme, port,
):
    observed = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            observed["host"] = self.headers.get("Host")
            observed["path"] = self.path
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write("从已校验的目标读取正文".encode())

        def log_message(self, *_args):
            return

    connection_targets = []
    real_create_connection = socket.create_connection
    with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()

        def connect_to_test_server(address, timeout=None, source_address=None):
            connection_targets.append(address)
            assert address == ("93.184.216.34", port)
            return real_create_connection(
                server.server_address,
                timeout=timeout,
                source_address=source_address,
            )

        if scheme == "https":
            class TestTlsContext:
                def wrap_socket(self, raw_socket, *, server_hostname):
                    observed["tls_server_name"] = server_hostname
                    return raw_socket

            monkeypatch.setattr(
                web_fetch_module.ssl,
                "create_default_context",
                TestTlsContext,
            )
        monkeypatch.setattr(
            web_fetch_module.socket,
            "create_connection",
            connect_to_test_server,
        )
        source = web_fetch_tool_source(
            required_permission="ads.read",
            resolve_host=lambda _host, _port: ["93.184.216.34"],
        )
        try:
            result = _execute(source, {
                "url": f"{scheme}://public.example/article?q=1",
            })
        finally:
            server.shutdown()
            server_thread.join(timeout=2)

    assert result.success is True, result.error
    assert "从已校验的目标读取正文" in result.data["content"]
    assert connection_targets == [("93.184.216.34", port)]
    assert observed["host"] == "public.example"
    assert observed["path"] == "/article?q=1"
    if scheme == "https":
        assert observed["tls_server_name"] == "public.example"


def test_web_fetch_rejects_mixed_public_and_private_dns_answers():
    requests_made = []
    source = _source(
        lambda *args, **kwargs: requests_made.append((args, kwargs)),
        resolve_host=lambda _host, _port: [
            "93.184.216.34",
            "10.0.0.7",
        ],
    )

    result = _execute(source, {"url": "https://public.example/article"})

    assert result.success is False
    assert requests_made == []


def test_web_fetch_rejects_literal_private_addresses_and_credentials():
    requests_made = []
    source = _source(
        lambda *args, **kwargs: requests_made.append((args, kwargs)),
    )

    for url in (
        "http://127.0.0.1/admin",
        "http://169.254.169.254/latest/meta-data/",
        "https://user:secret@example.com/article",
        "file:///etc/passwd",
    ):
        result = _execute(source, {"url": url})
        assert result.success is False

    assert requests_made == []


def test_web_fetch_revalidates_redirect_targets_before_following():
    first = FakeResponse(
        status_code=302,
        headers={"Location": "http://127.0.0.1/private"},
    )
    calls = []
    source = _source(
        lambda url, **kwargs: calls.append(url) or first,
    )

    result = _execute(source, {"url": "https://public.example/article"})

    assert result.success is False
    assert calls == ["https://public.example/article"]
    assert first.closed is True


def test_web_fetch_rejects_oversized_and_non_html_responses(monkeypatch):
    monkeypatch.setattr(
        "agents.agent_platform.tools.web_fetch.MAX_RESPONSE_BYTES",
        5,
    )
    oversized = FakeResponse(
        b"0123456789",
        headers={
            "Content-Type": "text/html",
            "Content-Length": "10",
        },
    )
    source = _source(lambda *_args, **_kwargs: oversized)
    result = _execute(source, {
        "url": "https://public.example/article",
    })
    assert result.success is False
    assert oversized.closed is True

    binary = FakeResponse(
        b"\x00\x01\x02",
        headers={"Content-Type": "application/octet-stream"},
    )
    source = _source(lambda *_args, **_kwargs: binary)
    result = _execute(source, {"url": "https://public.example/file"})
    assert result.success is False
    assert binary.closed is True


def test_web_fetch_rejects_compressed_responses_to_keep_body_limit_effective():
    response = FakeResponse(
        b"compressed",
        headers={
            "Content-Type": "text/html",
            "Content-Encoding": "gzip",
        },
    )
    result = _execute(
        _source(lambda *_args, **_kwargs: response),
        {"url": "https://public.example/article"},
    )

    assert result.success is False
    assert "压缩传输" in result.error
    assert response.closed is True


def test_web_fetch_maps_timeout_to_a_safe_failure():
    def timeout(*_args, **_kwargs):
        raise requests.Timeout("https://public.example/?access_token=secret")

    result = _execute(
        _source(timeout),
        {"url": "https://public.example/article"},
    )

    assert result.success is False
    assert "access_token" not in result.error
    assert "secret" not in result.error
