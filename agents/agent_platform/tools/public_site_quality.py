"""Bounded, read-only PageSpeed Insights API Tool for public pages."""

from __future__ import annotations

import ipaddress
import re
from collections.abc import Mapping
from typing import Any, Callable
from urllib.parse import parse_qsl, urlsplit, urlunsplit

from agents.agent_harness import StaticToolSource, ToolBinding
from agents.agent_harness.core.interfaces import ToolDefinition, ToolResult
from agents.agent_platform.tools.public_data import (
    _PublicDataError,
    _PublicDataExecutor,
    _PublicDataHttpClient,
    _PublicDataToolSpec,
    _schema,
)
from agents.agent_platform.tools.public_reference_common import (
    clean_text,
    number,
    result_metadata,
    string_schema,
    tool_definition,
)


_PAGE_SPEED_ENDPOINT = (
    "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
)
_PAGE_SPEED_DOCS = (
    "https://developers.google.com/speed/docs/insights/v5/get-started"
)
_PAGE_SPEED_TIMEOUT = (5, 45)
_PAGE_SPEED_STRATEGIES = frozenset({"desktop", "mobile"})
_PAGE_SPEED_CATEGORIES = (
    "performance",
    "accessibility",
    "best-practices",
    "seo",
)
_PAGE_SPEED_AUDITS = (
    "first-contentful-paint",
    "largest-contentful-paint",
    "speed-index",
    "total-blocking-time",
    "cumulative-layout-shift",
    "interactive",
    "server-response-time",
    "document-title",
    "meta-description",
    "is-crawlable",
    "robots-txt",
    "http-status-code",
    "crawlable-anchors",
    "link-text",
    "image-alt",
    "canonical",
)
_FIELD_METRICS = (
    "CUMULATIVE_LAYOUT_SHIFT_SCORE",
    "EXPERIMENTAL_TIME_TO_FIRST_BYTE",
    "FIRST_CONTENTFUL_PAINT_MS",
    "FIRST_INPUT_DELAY_MS",
    "INTERACTION_TO_NEXT_PAINT",
    "LARGEST_CONTENTFUL_PAINT_MS",
)
_SENSITIVE_QUERY_KEYS = frozenset({
    "token",
    "accesstoken",
    "refreshtoken",
    "apikey",
    "secret",
    "clientsecret",
    "signature",
    "auth",
    "authorization",
    "session",
    "sessionid",
    "password",
    "credential",
    "accesskey",
    "code",
    "authcode",
    "oauthcode",
    "authorizationcode",
})
_LOCALE = re.compile(r"^[a-z]{2}(?:-[A-Z]{2})?$")
_PRIVATE_HOST_SUFFIXES = (
    ".localhost",
    ".local",
    ".internal",
    ".test",
)
_MAX_URL_CHARS = 2048


def _validate_public_url(value: Any) -> str:
    if not isinstance(value, str):
        raise _PublicDataError("url 必须是公开网页 URL")
    candidate = value.strip()
    if (
        not candidate
        or len(candidate) > _MAX_URL_CHARS
        or any(ord(character) < 32 for character in candidate)
    ):
        raise _PublicDataError("url 必须是有效的公开网页 URL")
    try:
        parsed = urlsplit(candidate)
        host = (parsed.hostname or "").lower().rstrip(".")
        port = parsed.port
    except ValueError as error:
        raise _PublicDataError("url 必须是有效的公开网页 URL") from error

    try:
        ipaddress.ip_address(host)
        is_ip = True
    except ValueError:
        is_ip = False
    if (
        parsed.scheme.lower() not in {"http", "https"}
        or not host
        or parsed.username
        or parsed.password
        or is_ip
        or "." not in host
        or host == "localhost"
        or host.endswith(_PRIVATE_HOST_SUFFIXES)
        or port not in (None, 80, 443)
        or (port == 80 and parsed.scheme.lower() == "https")
        or (port == 443 and parsed.scheme.lower() == "http")
    ):
        raise _PublicDataError("PageSpeed 仅接受标准端口上的公开网页 URL")
    if _has_sensitive_query(parsed.query):
        raise _PublicDataError(
            "url 查询参数疑似包含凭证；请移除敏感参数后重试"
        )
    return urlunsplit((
        parsed.scheme.lower(),
        parsed.netloc,
        parsed.path or "/",
        parsed.query,
        "",
    ))


def _has_sensitive_query(query: str) -> bool:
    for key, _value in parse_qsl(query, keep_blank_values=True):
        normalized = re.sub(r"[^a-z0-9]", "", key.lower())
        if normalized in _SENSITIVE_QUERY_KEYS or normalized.endswith(
            ("token", "secret", "signature")
        ):
            return True
    return False


def _validate_strategy(value: Any) -> str:
    strategy = str(value or "mobile").strip().lower()
    if strategy not in _PAGE_SPEED_STRATEGIES:
        raise _PublicDataError("strategy 只支持 mobile 或 desktop")
    return strategy


def _validate_locale(value: Any) -> str:
    locale = str(value or "en-US").strip()
    if not _LOCALE.fullmatch(locale):
        raise _PublicDataError("locale 格式应为 en 或 en-US")
    return locale


def _validate_api_key(value: Any) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValueError("PageSpeed API key configuration is invalid")
    api_key = value.strip()
    if len(api_key) > 512 or any(ord(character) < 32 for character in api_key):
        raise ValueError("PageSpeed API key configuration is invalid")
    return api_key


def _score_percent(value: Any) -> int | None:
    score = number(value)
    if score is None or not 0 <= score <= 1:
        return None
    return round(score * 100)


def _project_categories(value: Any) -> dict[str, int | None]:
    categories = value if isinstance(value, Mapping) else {}
    return {
        category: _score_percent(
            categories.get(category, {}).get("score")
            if isinstance(categories.get(category), Mapping) else None
        )
        for category in _PAGE_SPEED_CATEGORIES
    }


def _project_audits(value: Any) -> list[dict[str, Any]]:
    audits = value if isinstance(value, Mapping) else {}
    projected = []
    for audit_id in _PAGE_SPEED_AUDITS:
        audit = audits.get(audit_id)
        if not isinstance(audit, Mapping):
            continue
        score = number(audit.get("score"))
        projected.append({
            "id": audit_id,
            "title": clean_text(audit.get("title"), 120),
            "score": score if score is not None and 0 <= score <= 1 else None,
            "score_display_mode": clean_text(
                audit.get("scoreDisplayMode"), 32
            ),
            "display_value": clean_text(audit.get("displayValue"), 160),
            "description": clean_text(audit.get("description"), 400),
        })
    return projected


def _project_field_data(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        return None
    metrics = value.get("metrics")
    metrics = metrics if isinstance(metrics, Mapping) else {}
    projected_metrics = {}
    for metric_name in _FIELD_METRICS:
        metric = metrics.get(metric_name)
        if not isinstance(metric, Mapping):
            continue
        projected_metrics[metric_name] = {
            "percentile": number(metric.get("percentile"), integer=True),
            "category": clean_text(metric.get("category"), 24),
        }
    if not projected_metrics and not value.get("overall_category"):
        return None
    return {
        "overall_category": clean_text(value.get("overall_category"), 24),
        "metrics": projected_metrics,
    }


def _display_url(value: str) -> str:
    parsed = urlsplit(value)
    return urlunsplit((
        parsed.scheme,
        parsed.netloc,
        parsed.path,
        "",
        "",
    ))


class _PageSpeedExecutor(_PublicDataExecutor):
    def __init__(
        self,
        client: _PublicDataHttpClient,
        *,
        api_name: str,
        endpoint: str,
        api_key: str,
    ) -> None:
        super().__init__(client, api_name=api_name, endpoint=endpoint)
        self._api_key = api_key

    def execute(self, _context: Any, arguments: dict[str, Any]) -> ToolResult:
        try:
            target_url = _validate_public_url(arguments.get("url"))
            strategy = _validate_strategy(arguments.get("strategy"))
            locale = _validate_locale(arguments.get("locale"))
            params = {
                "url": target_url,
                "strategy": strategy,
                "locale": locale,
                "category": list(_PAGE_SPEED_CATEGORIES),
            }
            if self._api_key:
                params["key"] = self._api_key
            payload = self._client.get_json(
                self._endpoint,
                params=params,
                timeout=_PAGE_SPEED_TIMEOUT,
            )
            lighthouse = (
                payload.get("lighthouseResult")
                if isinstance(payload, Mapping) else None
            )
            if not isinstance(lighthouse, Mapping):
                raise _PublicDataError(
                    "PageSpeed Insights 返回了不支持的数据结构"
                )
            result = result_metadata(
                source="Google PageSpeed Insights",
                source_url=_PAGE_SPEED_DOCS,
                data={
                    "analyzed_url": _display_url(target_url),
                    "strategy": strategy,
                    "categories": _project_categories(
                        lighthouse.get("categories")
                    ),
                    "audits": _project_audits(lighthouse.get("audits")),
                    "field_data": _project_field_data(
                        payload.get("loadingExperience")
                    ),
                    "origin_field_data": _project_field_data(
                        payload.get("originLoadingExperience")
                    ),
                    "limitations": (
                        "Lighthouse 检查不是完整站点爬取或 Search Console "
                        "数据；字段数据仅在 Google 返回时提供。"
                    ),
                },
            )
            return ToolResult.ok(result)
        except (TypeError, ValueError, OverflowError) as error:
            return self._error(error)

    def _error(self, error: Exception) -> ToolResult:
        if isinstance(error, _PublicDataError) and "HTTP 429" in str(error):
            return ToolResult.error(
                "PageSpeed Insights：上游 HTTP 429，可能是请求限流或配额不足；"
                "稍后重试，或配置 GOOGLE_PAGESPEED_API_KEY 并检查 Google API 配额。"
            )
        return super()._error(error)


def _pagespeed_definition(permission: str) -> ToolDefinition:
    spec = _PublicDataToolSpec(
        name="public_site_quality_pagespeed",
        skill="seo-growth",
        namespace="public_site_quality",
        description=(
            "Run a bounded Google PageSpeed Insights Lighthouse audit for a "
            "public, unauthenticated page URL. Returns performance, accessibility, "
            "best-practices and limited SEO checks, plus field data only when "
            "the API returns it. The URL is sent to Google; never send private, "
            "signed or credential-bearing URLs. This is not a full-site crawl, "
            "Search Console report, ranking check or guarantee. Low-volume API "
            "requests can be made without a key; upstream quotas still apply."
        ),
        action="inspect",
        resource_type="public_web_page",
        intent_type="page_quality_audit",
        intent_aliases=(
            "网站 SEO 诊断",
            "页面 SEO 检查",
            "网页性能检测",
            "网站速度测试",
            "Core Web Vitals 页面检测",
            "PageSpeed Insights",
            "Lighthouse page audit",
            "page experience audit",
        ),
        schema=_schema({
            "url": string_schema(
                "Public unauthenticated http(s) URL; sent to Google's API. "
                "Do not include credentials or sensitive query parameters.",
                maximum=_MAX_URL_CHARS,
            ),
            "strategy": {
                "type": "string",
                "enum": sorted(_PAGE_SPEED_STRATEGIES),
                "default": "mobile",
                "description": "Lighthouse device strategy.",
            },
            "locale": {
                "type": "string",
                "pattern": r"^[a-z]{2}(-[A-Z]{2})?$",
                "default": "en-US",
                "description": "Lighthouse report locale, such as en-US or zh-CN.",
            },
        }, ["url"]),
        result_items_key="audits",
        timeout_seconds=60,
    )
    definition = tool_definition(spec, permission)
    definition.skill_refs = ["seo-growth", "web-research"]
    definition.max_output_bytes = 24_000
    definition.traits.append("mcp_public_api")
    return definition


def public_site_quality_tool_source(
    *,
    required_permission: str,
    request_get: Callable[..., Any] | None = None,
    api_key: str | None = None,
) -> StaticToolSource:
    permission = str(required_permission or "").strip()
    if not permission:
        raise ValueError("required_permission is required")
    configured_api_key = _validate_api_key(api_key)
    client = _PublicDataHttpClient(request_get)
    return StaticToolSource(
        "agent-platform:public-site-quality",
        [ToolBinding(
            _pagespeed_definition(permission),
            _PageSpeedExecutor(
                client,
                api_name="PageSpeed Insights",
                endpoint=_PAGE_SPEED_ENDPOINT,
                api_key=configured_api_key,
            ),
        )],
    )


__all__ = ["public_site_quality_tool_source"]
