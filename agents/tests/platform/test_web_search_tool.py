from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
import requests
from ddgs.exceptions import DDGSException, RatelimitException, TimeoutException

from agents.agent_harness.core.interfaces import ReplayPolicy, RiskLevel, ToolEffect
from agents.agent_harness.core.tool_selection import ToolSelector
from agents.applications.advertising.composition.ad_application import (
    AdvertisingComposition,
)
from agents.agent_platform.tools.web_search import (
    MAX_RESPONSE_BYTES,
    web_search_tool_source,
)


class FakeResponse:
    def __init__(
        self,
        payload=None,
        *,
        status_code=200,
        headers=None,
        body=None,
    ):
        self.status_code = status_code
        self.headers = headers or {}
        self._body = (
            body if body is not None
            else json.dumps(payload or {}).encode("utf-8")
        )
        self.closed = False

    def iter_content(self, chunk_size):
        for offset in range(0, len(self._body), chunk_size):
            yield self._body[offset:offset + chunk_size]

    def close(self):
        self.closed = True


class BrokenStreamResponse(FakeResponse):
    def iter_content(self, chunk_size):
        raise requests.ConnectionError("upstream-secret")


class FakeDDGS:
    def __init__(self, result, *, timeout):
        self.result = result
        self.timeout = timeout
        self.calls = []

    def factory(self, **kwargs):
        self.timeout = kwargs["timeout"]
        return self

    def text(self, query, **kwargs):
        self.calls.append((query, kwargs))
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


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


def _brave_configuration():
    return {
        "provider": "brave",
        "api_key": "private-brave-key",
    }


def _duckduckgo_configuration():
    return {"provider": "duckduckgo"}


def test_web_search_publishes_generic_bounded_read_tool_contract():
    source = web_search_tool_source(
        configuration_provider=_brave_configuration,
        required_permission="ads.read",
    )
    definition = source.list_bindings()[0].definition

    assert source.source_id == "agent-platform:web-search"
    assert definition.name == "agent_web_search"
    assert definition.namespace == "agent-platform"
    assert definition.action == "search"
    assert definition.resource_type == "web"
    assert definition.intent_types == ["web_search"]
    assert definition.risk_level is RiskLevel.LOW
    assert definition.effect_class is ToolEffect.READ
    assert definition.replay_policy is ReplayPolicy.SAFE
    assert definition.required_permissions == ["ads.read"]
    assert definition.scope_required is False
    assert definition.timeout_seconds <= 20
    assert definition.input_schema.properties["query"]["maxLength"] == 600
    assert definition.input_schema.additional_properties is False


def test_web_search_sends_bounded_request_and_projects_cited_results():
    response = FakeResponse({
        "web": {
            "results": [
                {
                    "title": "Official guide",
                    "url": "https://example.com/guide#section",
                    "description": "A useful current guide.",
                    "age": "2 days ago",
                    "extra": "must not leak",
                    "api_key": "must-not-leak",
                },
                {
                    "title": "Duplicate",
                    "url": "https://example.com/guide#other",
                    "description": "Duplicate URL.",
                },
                {
                    "title": "Unsafe",
                    "url": "javascript:alert(1)",
                    "description": "Must be omitted.",
                },
            ],
        },
    })
    calls = []

    def request_get(url, **kwargs):
        calls.append((url, kwargs))
        return response

    source = web_search_tool_source(
        configuration_provider=_brave_configuration,
        required_permission="ads.read",
        request_get=request_get,
    )
    result = _execute(source, {
        "query": "current advertising API guidance",
        "limit": 8,
        "country": "CA",
        "freshness": "pw",
    })

    assert result.success is True
    assert result.data["provider"] == "brave"
    assert result.data["data_status"] == "web"
    assert result.data["count"] == 1
    assert result.data["results"] == [{
        "title": "Official guide",
        "url": "https://example.com/guide",
        "snippet": "A useful current guide.",
        "age": "2 days ago",
    }]
    assert "private-brave-key" not in repr(result.data)
    assert "must-not-leak" not in repr(result.data)
    url, request = calls[0]
    assert url == "https://api.search.brave.com/res/v1/web/search"
    assert request["headers"]["X-Subscription-Token"] == "private-brave-key"
    assert request["params"] == {
        "q": "current advertising API guidance",
        "count": 8,
        "country": "CA",
        "freshness": "pw",
    }
    assert request["timeout"] == (5, 12)
    assert request["allow_redirects"] is False
    assert response.closed is True


def test_web_search_defaults_to_duckduckgo_without_api_key_or_service():
    client = FakeDDGS(
        [{
            "title": "DuckDuckGo result",
            "href": "https://example.com/article",
            "body": "A current public web result.",
        }],
        timeout=0,
    )
    source = web_search_tool_source(
        configuration_provider=lambda: {},
        required_permission="ads.read",
        ddgs_factory=client.factory,
    )
    result = _execute(source, {"query": "latest advertising guidance"})

    assert result.success is True
    assert result.data == {
        "provider": "duckduckgo",
        "data_status": "web",
        "count": 1,
        "results": [{
            "title": "DuckDuckGo result",
            "url": "https://example.com/article",
            "snippet": "A current public web result.",
        }],
    }
    query, options = client.calls[0]
    assert query == "latest advertising guidance"
    assert options == {
        "region": "us-en",
        "safesearch": "moderate",
        "timelimit": None,
        "max_results": 5,
        "backend": "duckduckgo",
    }
    assert client.timeout <= 15


def test_web_search_maps_duckduckgo_freshness_and_projects_safe_results():
    client = FakeDDGS(
        [
            {
                "title": "Official source",
                "href": "https://example.com/article?utm_source=search#section",
                "body": "Evidence from a public result.",
                "api_key": "must-not-leak",
            },
            {
                "title": "Duplicate",
                "href": "https://example.com/article?utm_source=search#other",
                "body": "Duplicate URL.",
            },
            {
                "title": "Unsafe",
                "href": "javascript:alert(1)",
                "body": "Must be omitted.",
            },
        ],
        timeout=0,
    )
    source = web_search_tool_source(
        configuration_provider=_duckduckgo_configuration,
        required_permission="ads.read",
        ddgs_factory=client.factory,
    )

    result = _execute(
        source,
        {
            "query": "research",
            "country": "CA",
            "freshness": "pw",
            "limit": 2,
        },
    )

    assert result.success is True
    assert result.data["provider"] == "duckduckgo"
    assert result.data["count"] == 1
    assert result.data["results"] == [{
        "title": "Official source",
        "url": "https://example.com/article?utm_source=search",
        "snippet": "Evidence from a public result.",
    }]
    assert "must-not-leak" not in repr(result.data)
    assert "#section" not in repr(result.data)
    assert client.calls[0][1] == {
        "region": "ca-en",
        "safesearch": "moderate",
        "timelimit": "w",
        "max_results": 2,
        "backend": "duckduckgo",
    }


@pytest.mark.parametrize(
    "exception,expected",
    [
        (RatelimitException("429"), "DuckDuckGo 搜索当前触发限流"),
        (TimeoutException("timeout"), "DuckDuckGo 搜索请求超时"),
    ],
)
def test_web_search_maps_duckduckgo_rate_limit_and_timeout(
    exception,
    expected,
):
    client = FakeDDGS(exception, timeout=0)
    source = web_search_tool_source(
        configuration_provider=_duckduckgo_configuration,
        required_permission="ads.read",
        ddgs_factory=client.factory,
    )

    result = _execute(source, {"query": "current advertising news"})

    assert result.success is False
    assert expected in str(result.error)
    assert "429" not in str(result.error)


def test_web_search_does_not_report_upstream_no_results_as_a_valid_answer():
    client = FakeDDGS(DDGSException("No results found."), timeout=0)
    source = web_search_tool_source(
        configuration_provider=_duckduckgo_configuration,
        required_permission="ads.read",
        ddgs_factory=client.factory,
    )

    result = _execute(source, {"query": "current advertising news"})

    assert result.success is False
    assert "可能触发了上游限制或验证" in str(result.error)


def test_web_search_accepts_the_documented_maximum_query_length():
    calls = []
    source = web_search_tool_source(
        configuration_provider=_brave_configuration,
        required_permission="ads.read",
        request_get=lambda _url, **kwargs: (
            calls.append(kwargs) or FakeResponse({"web": {"results": []}})
        ),
    )

    result = _execute(source, {"query": "q" * 600})

    assert result.success is True
    assert len(calls) == 1
    assert len(calls[0]["params"]["q"]) == 600


def test_web_search_rejects_unavailable_or_unknown_backend_configuration():
    source = web_search_tool_source(
        configuration_provider=lambda: {"provider": "unsupported"},
        required_permission="ads.read",
        request_get=lambda *_args, **_kwargs: pytest.fail(
            "network must not be called for an unknown backend"
        ),
    )

    result = _execute(source, {"query": "latest ad platform changes"})

    assert result.success is False
    assert "搜索后端配置无效" in str(result.error)


@pytest.mark.parametrize(
    "arguments",
    [
        {},
        {"query": "   "},
        {"query": "q" * 601},
        {"query": "ok", "limit": True},
        {"query": "ok", "limit": 11},
        {"query": "ok", "country": "USA"},
        {"query": "ok", "freshness": "today"},
        {"query": "ok", "freshness": []},
        {"query": "ok", "unexpected": "field"},
    ],
)
def test_web_search_rejects_invalid_inputs_without_network_calls(arguments):
    called = False

    def request_get(*_args, **_kwargs):
        nonlocal called
        called = True
        return FakeResponse({"web": {"results": []}})

    source = web_search_tool_source(
        configuration_provider=_brave_configuration,
        required_permission="ads.read",
        request_get=request_get,
    )

    result = _execute(source, arguments)

    assert result.success is False
    assert called is False


@pytest.mark.parametrize(
    "status_code,expected",
    [
        (401, "认证失败"),
        (403, "认证失败"),
        (429, "限流"),
        (503, "暂时不可用"),
    ],
)
def test_web_search_maps_upstream_failures_without_echoing_response(
    status_code,
    expected,
):
    source = web_search_tool_source(
        configuration_provider=_brave_configuration,
        required_permission="ads.read",
        request_get=lambda *_args, **_kwargs: FakeResponse(
            status_code=status_code,
            body=b'{"error":"refresh_token=upstream-secret"}',
        ),
    )

    result = _execute(source, {"query": "latest policy"})

    assert result.success is False
    assert expected in str(result.error)
    assert "upstream-secret" not in str(result.error)


def test_web_search_handles_timeout_invalid_json_and_oversized_body():
    timeout_source = web_search_tool_source(
        configuration_provider=_brave_configuration,
        required_permission="ads.read",
        request_get=lambda *_args, **_kwargs: (_ for _ in ()).throw(
            requests.Timeout()
        ),
    )
    invalid_json_source = web_search_tool_source(
        configuration_provider=_brave_configuration,
        required_permission="ads.read",
        request_get=lambda *_args, **_kwargs: FakeResponse(body=b"not-json"),
    )
    oversized_source = web_search_tool_source(
        configuration_provider=_brave_configuration,
        required_permission="ads.read",
        request_get=lambda *_args, **_kwargs: FakeResponse(
            headers={"Content-Length": str(MAX_RESPONSE_BYTES + 1)},
        ),
    )

    assert "超时" in str(
        _execute(timeout_source, {"query": "latest policy"}).error
    )
    assert "无效响应" in str(
        _execute(invalid_json_source, {"query": "latest policy"}).error
    )
    assert "响应超过" in str(
        _execute(oversized_source, {"query": "latest policy"}).error
    )


def test_web_search_maps_stream_disconnect_to_a_safe_error():
    response = BrokenStreamResponse()
    source = web_search_tool_source(
        configuration_provider=_brave_configuration,
        required_permission="ads.read",
        request_get=lambda *_args, **_kwargs: response,
    )

    result = _execute(source, {"query": "latest policy"})

    assert result.success is False
    assert "无法连接" in str(result.error)
    assert "upstream-secret" not in str(result.error)
    assert response.closed is True


def test_web_search_is_selected_for_online_lookup_not_local_knowledge_search():
    source = web_search_tool_source(
        configuration_provider=_brave_configuration,
        required_permission="ads.read",
    )
    definition = source.list_bindings()[0].definition
    selected = ToolSelector().select_relevant(
        "联网搜索一下最近的广告平台 API 变更",
        [definition],
    )

    assert [tool.name for tool in selected] == ["agent_web_search"]


def test_web_search_can_be_registered_into_the_existing_application_runtime():
    runtime = AdvertisingComposition(
        require_llm=False,
        offline_mode=True,
        start_background_workers=False,
    )
    source = web_search_tool_source(
        configuration_provider=_brave_configuration,
        required_permission="ads.read",
    )
    try:
        registered = runtime.register_tool_source(source)

        assert registered == ["agent_web_search"]
        assert "agent-platform:web-search" in (
            runtime.platform_application.tool_source_ids
        )
        assert runtime.registry.get("agent_web_search")[0] is (
            source.list_bindings()[0].definition
        )
        selected = ToolSelector().select_relevant(
            "联网搜索最近的广告平台 API 更新",
            runtime.registry.list_all(),
        )
        assert "agent_web_search" in [tool.name for tool in selected]
    finally:
        runtime.close(wait=True)
