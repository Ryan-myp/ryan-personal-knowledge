from __future__ import annotations

import json
from types import SimpleNamespace

from agents.agent_harness.core.interfaces import ReplayPolicy, RiskLevel, ToolEffect
from agents.agent_platform.tools.public_site_quality import (
    public_site_quality_tool_source,
)


class FakeResponse:
    def __init__(self, payload=None, *, status_code=200):
        self.status_code = status_code
        self.headers = {}
        self.body = json.dumps(payload or {}).encode("utf-8")
        self.closed = False

    def iter_content(self, chunk_size):
        for offset in range(0, len(self.body), chunk_size):
            yield self.body[offset:offset + chunk_size]

    def close(self):
        self.closed = True


def _bindings(request_get=None, *, api_key=None):
    source = public_site_quality_tool_source(
        required_permission="ads.read",
        request_get=request_get,
        api_key=api_key,
    )
    return source, {
        binding.definition.name: binding
        for binding in source.list_bindings()
    }


def _execute(binding, arguments):
    context = SimpleNamespace(
        request=SimpleNamespace(
            principal=SimpleNamespace(
                user_id="operator",
                tenant_id="tenant-a",
                permissions=frozenset({"ads.read"}),
            ),
        ),
    )
    return binding.executor.execute(context, arguments)


def test_pagespeed_tool_has_bounded_read_only_seo_contract():
    source, bindings = _bindings()

    assert source.source_id == "agent-platform:public-site-quality"
    assert set(bindings) == {"public_site_quality_pagespeed"}
    definition = bindings["public_site_quality_pagespeed"].definition
    assert definition.namespace == "public-site-quality"
    assert definition.action == "inspect"
    assert definition.resource_type == "public_web_page"
    assert definition.effect_class is ToolEffect.READ
    assert definition.risk_level is RiskLevel.LOW
    assert definition.replay_policy is ReplayPolicy.SAFE
    assert definition.intent_types == ["page_quality_audit"]
    assert definition.skill_refs == ["seo-growth", "web-research"]
    assert definition.required_permissions == ["ads.read"]
    assert definition.scope_required is False
    assert definition.input_schema.additional_properties is False
    assert definition.input_schema.required == ["url"]
    assert definition.input_schema.properties["strategy"]["enum"] == [
        "desktop",
        "mobile",
    ]
    assert definition.timeout_seconds <= 60
    assert definition.max_output_bytes <= 32_000
    assert "external_public_data" in definition.traits


def test_pagespeed_tool_requests_fixed_api_and_projects_a_bounded_report():
    response = FakeResponse({
        "lighthouseResult": {
            "requestedUrl": "https://example.com/pricing?token=private",
            "finalUrl": "https://example.com/pricing?token=private",
            "categories": {
                "performance": {"score": 0.91},
                "accessibility": {"score": 0.98},
                "best-practices": {"score": 1},
                "seo": {"score": 0.89},
            },
            "audits": {
                "largest-contentful-paint": {
                    "title": "Largest Contentful Paint",
                    "score": 0.8,
                    "scoreDisplayMode": "numeric",
                    "displayValue": "2.1 s",
                    "description": "Largest Contentful Paint timing.",
                },
                "meta-description": {
                    "title": "Meta description",
                    "score": 0,
                    "scoreDisplayMode": "binary",
                    "displayValue": None,
                    "description": "Add a meta description.",
                },
                "unrelated-audit": {
                    "title": "Unrelated",
                    "description": "Must not be projected.",
                    "score": 0,
                },
            },
        },
        "loadingExperience": {
            "overall_category": "AVERAGE",
            "metrics": {
                "LARGEST_CONTENTFUL_PAINT_MS": {
                    "percentile": 1700,
                    "category": "FAST",
                    "extra": "must not leak",
                },
            },
        },
        "unrelated": "must not leak",
    })
    calls = []
    _, bindings = _bindings(
        lambda url, **kwargs: calls.append((url, kwargs)) or response,
    )

    result = _execute(bindings["public_site_quality_pagespeed"], {
        "url": (
            "https://example.com/pricing?country_code=us"
            "&utm_source=newsletter"
        ),
        "strategy": "mobile",
        "locale": "en-US",
    })

    assert result.success is True
    assert result.data["source"] == "Google PageSpeed Insights"
    assert result.data["analyzed_url"] == "https://example.com/pricing"
    assert result.data["strategy"] == "mobile"
    assert result.data["categories"] == {
        "performance": 91,
        "accessibility": 98,
        "best-practices": 100,
        "seo": 89,
    }
    assert result.data["audits"][0] == {
        "id": "largest-contentful-paint",
        "title": "Largest Contentful Paint",
        "score": 0.8,
        "score_display_mode": "numeric",
        "display_value": "2.1 s",
        "description": "Largest Contentful Paint timing.",
    }
    assert result.data["field_data"]["overall_category"] == "AVERAGE"
    assert result.data["field_data"]["metrics"] == {
        "LARGEST_CONTENTFUL_PAINT_MS": {
            "percentile": 1700,
            "category": "FAST",
        },
    }
    assert "unrelated-audit" not in repr(result.data)
    assert "token=private" not in repr(result.data)

    url, options = calls[0]
    assert url == (
        "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
    )
    assert options["params"] == {
        "url": (
            "https://example.com/pricing?country_code=us"
            "&utm_source=newsletter"
        ),
        "strategy": "mobile",
        "locale": "en-US",
        "category": [
            "performance",
            "accessibility",
            "best-practices",
            "seo",
        ],
    }
    assert "key" not in options["params"]
    assert options["allow_redirects"] is False
    assert options["timeout"] == (5, 45)
    assert response.closed is True


def test_pagespeed_uses_optional_api_key_without_exposing_it():
    response = FakeResponse({
        "lighthouseResult": {
            "categories": {"seo": {"score": 0.92}},
            "audits": {},
        },
    })
    calls = []
    secret = "test-pagespeed-key"
    _, bindings = _bindings(
        lambda url, **kwargs: calls.append((url, kwargs)) or response,
        api_key=secret,
    )

    result = _execute(bindings["public_site_quality_pagespeed"], {
        "url": "https://example.com/",
    })

    assert result.success is True
    assert calls[0][1]["params"]["key"] == secret
    assert secret not in repr(result.data)
    assert secret not in repr(result.error)


def test_pagespeed_tool_rejects_private_or_secret_urls_before_network_call():
    calls = []
    _, bindings = _bindings(
        lambda url, **kwargs: calls.append((url, kwargs)),
    )
    binding = bindings["public_site_quality_pagespeed"]

    for url in (
        "file:///etc/passwd",
        "http://localhost",
        "http://127.0.0.1/",
        "https://user:password@example.com/",
        "https://example.com/?access_token=secret",
        "https://example.com/?country_code=us&client_secret=secret",
    ):
        result = _execute(binding, {"url": url})
        assert result.success is False, url

    assert calls == []


def test_pagespeed_tool_reports_upstream_errors_and_invalid_shapes():
    _, bindings = _bindings(
        lambda *_args, **_kwargs: FakeResponse(status_code=429),
    )
    result = _execute(bindings["public_site_quality_pagespeed"], {
        "url": "https://example.com/",
    })
    assert result.success is False
    assert "HTTP 429" in result.error
    assert "配额" in result.error or "限流" in result.error
    assert "GOOGLE_PAGESPEED_API_KEY" in result.error

    _, bindings = _bindings(lambda *_args, **_kwargs: FakeResponse({
        "lighthouseResult": [],
    }))
    result = _execute(bindings["public_site_quality_pagespeed"], {
        "url": "https://example.com/",
    })
    assert result.success is False
    assert "不支持的数据结构" in result.error
