"""Read-only Google Search Console site discovery and traffic reports."""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote, urlsplit

import requests

from agents.agent_harness import ToolBinding
from agents.agent_harness.core.interfaces import ToolResult, ToolSchema
from agents.tools.marketing_analytics.shared import (
    AnalyticsToolError,
    bounded_int,
    GoogleReadonlyClient,
    MAX_ROWS,
    _safe_string,
    create_source,
    date_time_metadata,
    error_result,
    safe_number,
    tool_definition,
    ToolContract,
    tool_schema,
    validate_date_range,
)


SEARCH_CONSOLE_SCOPE = "https://www.googleapis.com/auth/webmasters.readonly"
SEARCH_CONSOLE_API_ROOT = "https://www.googleapis.com/webmasters/v3"
MAX_ROW_OFFSET = 25_000
_DOMAIN_PROPERTY = re.compile(r"^sc-domain:[A-Za-z0-9.-]+$")
_DIMENSIONS = frozenset({
    "country",
    "date",
    "device",
    "page",
    "query",
    "searchAppearance",
})
_SEARCH_TYPES = frozenset({
    "web",
    "image",
    "video",
    "news",
    "discover",
    "googleNews",
})


def _site_url(value: Any) -> str:
    if not isinstance(value, str):
        raise AnalyticsToolError("Search Console site_url 必须是属性 URL。")
    candidate = value.strip()
    if not candidate or len(candidate) > 2048:
        raise AnalyticsToolError("Search Console site_url 长度无效。")
    if _DOMAIN_PROPERTY.fullmatch(candidate):
        domain = candidate.removeprefix("sc-domain:")
        labels = domain.split(".")
        if len(labels) < 2 or any(
            not label or label.startswith("-") or label.endswith("-")
            for label in labels
        ):
            raise AnalyticsToolError("Search Console Domain Property 格式无效。")
        return f"sc-domain:{domain.lower()}"
    try:
        parsed = urlsplit(candidate)
        if (
            parsed.scheme.lower() not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or parsed.port not in (None, 80, 443)
            or _control_character(candidate)
        ):
            raise AnalyticsToolError("Search Console URL-prefix Property 格式无效。")
    except ValueError as error:
        raise AnalyticsToolError("Search Console URL-prefix Property 格式无效。") from error
    return candidate


def _control_character(value: str) -> bool:
    return any(ord(character) < 32 or ord(character) == 127 for character in value)


class _SearchConsoleExecutor:
    def __init__(self, client: GoogleReadonlyClient) -> None:
        self._client = client

    @staticmethod
    def _error(error: Exception) -> ToolResult:
        return error_result(error)


class _ListSitesExecutor(_SearchConsoleExecutor):
    def execute(self, _context: Any, _arguments: dict[str, Any]) -> ToolResult:
        endpoint = f"{SEARCH_CONSOLE_API_ROOT}/sites"
        try:
            response = self._client.get_json(endpoint)
            raw_sites = response.get("siteEntry", [])
            if not isinstance(raw_sites, list):
                raise AnalyticsToolError("Search Console 返回了无效的站点列表。")
            sites = []
            for site in raw_sites[:200]:
                if not isinstance(site, Mapping):
                    continue
                site_url = _safe_string(site.get("siteUrl"), 2048)
                if not site_url:
                    continue
                sites.append({
                    "site_url": site_url,
                    "permission_level": _safe_string(
                        site.get("permissionLevel"), 80,
                    ),
                })
            return ToolResult.ok({
                **date_time_metadata(
                    source="Google Search Console API",
                    source_url=endpoint,
                ),
                "sites": sites,
            })
        except (AnalyticsToolError, requests.RequestException, TypeError, ValueError) as error:
            return self._error(error)


class _SearchAnalyticsExecutor(_SearchConsoleExecutor):
    def execute(self, _context: Any, arguments: dict[str, Any]) -> ToolResult:
        try:
            query = _build_search_query(arguments)
            response = self._client.post_json(query.endpoint, payload=query.payload)
            return ToolResult.ok(_search_result(response, query))
        except (AnalyticsToolError, requests.RequestException, TypeError, ValueError) as error:
            return self._error(error)


@dataclass(frozen=True)
class _SearchQuery:
    site_url: str
    start_date: str
    end_date: str
    dimensions: list[str]
    search_type: str
    row_limit: int
    start_row: int
    endpoint: str
    payload: dict[str, Any]


def _build_search_query(arguments: Mapping[str, Any]) -> _SearchQuery:
    site = _site_url(arguments.get("site_url"))
    start_date, end_date = validate_date_range(
        arguments.get("start_date"), arguments.get("end_date"),
    )
    dimensions = _dimensions(arguments.get("dimensions", []))
    search_type = str(arguments.get("search_type") or "web").strip()
    if search_type not in _SEARCH_TYPES:
        raise AnalyticsToolError("search_type 不受支持。")
    row_limit = bounded_int(arguments.get("row_limit", 500), "row_limit", 1, MAX_ROWS)
    start_row = bounded_int(
        arguments.get("start_row", 0), "start_row", 0, MAX_ROW_OFFSET,
    )
    endpoint = (
        f"{SEARCH_CONSOLE_API_ROOT}/sites/{quote(site, safe='')}"
        "/searchAnalytics/query"
    )
    payload = {
        "startDate": start_date,
        "endDate": end_date,
        "dimensions": dimensions,
        "type": search_type,
        "rowLimit": row_limit,
        "startRow": start_row,
        "dataState": "final",
    }
    return _SearchQuery(
        site, start_date, end_date, dimensions, search_type,
        row_limit, start_row, endpoint, payload,
    )


def _search_result(
    response: Mapping[str, Any], query: _SearchQuery,
) -> dict[str, Any]:
    raw_rows = response.get("rows", [])
    if not isinstance(raw_rows, list):
        raise AnalyticsToolError("Search Console 返回了无效的报告行。")
    rows = [
        _map_search_row(row, query.dimensions)
        for row in raw_rows[:query.row_limit]
        if isinstance(row, Mapping)
    ]
    return {
        **date_time_metadata(
            source="Google Search Console Search Analytics API",
            source_url=query.endpoint,
        ),
        "site_url": query.site_url,
        "date_range": {
            "start_date": query.start_date,
            "end_date": query.end_date,
        },
        "search_type": query.search_type,
        "dimensions": query.dimensions,
        "row_limit": query.row_limit,
        "start_row": query.start_row,
        "returned_rows": len(rows),
        "rows": rows,
        "coverage_note": (
            "Search Console 可能省略匿名或低频查询以及部分长尾行；"
            "API 结果不保证包含全部搜索数据。"
        ),
    }


def _map_search_row(row: Mapping[str, Any], dimensions: list[str]) -> dict[str, Any]:
    keys = row.get("keys", [])
    if not isinstance(keys, list):
        keys = []
    mapped = {
        dimension: _safe_string(keys[index], 500)
        if index < len(keys) else ""
        for index, dimension in enumerate(dimensions)
    }
    mapped.update({
        "clicks": safe_number(row.get("clicks")),
        "impressions": safe_number(row.get("impressions")),
        "ctr": safe_number(row.get("ctr")),
        "position": safe_number(row.get("position")),
    })
    return mapped


def _dimensions(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise AnalyticsToolError("dimensions 必须是数组。")
    if len(value) > len(_DIMENSIONS):
        raise AnalyticsToolError("Search Console dimensions 最多支持 6 项。")
    dimensions = []
    for item in value:
        selected = str(item or "").strip()
        if selected not in _DIMENSIONS:
            raise AnalyticsToolError(
                "Search Console dimension 不受支持，可选 date、query、page、country、device、searchAppearance。"
            )
        dimensions.append(selected)
    if len(set(dimensions)) != len(dimensions):
        raise AnalyticsToolError("dimensions 不能重复。")
    return dimensions


def _site_schema() -> ToolSchema:
    return tool_schema({}, [])


def _search_analytics_schema() -> ToolSchema:
    return tool_schema({
        "site_url": {
            "type": "string",
            "maxLength": 2048,
            "description": "从 gsc_list_sites 返回的 URL-prefix Property 或 sc-domain:example.com。",
        },
        "start_date": {"type": "string", "format": "date"},
        "end_date": {"type": "string", "format": "date"},
        "dimensions": {
            "type": "array",
            "maxItems": 6,
            "items": {
                "type": "string",
                "enum": sorted(_DIMENSIONS),
            },
            "description": "可选分组：date、query、page、country、device、searchAppearance。",
        },
        "search_type": {
            "type": "string",
            "enum": sorted(_SEARCH_TYPES),
            "default": "web",
        },
        "row_limit": {
            "type": "integer",
            "minimum": 1,
            "maximum": MAX_ROWS,
            "default": 500,
        },
        "start_row": {
            "type": "integer",
            "minimum": 0,
            "maximum": MAX_ROW_OFFSET,
            "default": 0,
        },
    }, ["site_url", "start_date", "end_date"])


def _search_console_skill_refs() -> tuple[str, ...]:
    return (
        "seo-growth",
        "generative-search-visibility",
        "keyword-research",
        "measurement-attribution",
    )


def _sites_binding(client: GoogleReadonlyClient) -> ToolBinding:
    contract = ToolContract(
        name="gsc_list_sites",
        description=(
            "列出当前 OAuth 授权账号可访问的 Google Search Console Property。"
            "用于发现后续查询需要的 site_url；只读，不会添加或删除站点。"
        ),
        action="list",
        resource_type="search_console_property",
        intent_type="list_search_console_sites",
        aliases=("查询 Search Console 站点", "列出 GSC 属性", "查询站长工具网站"),
        schema=_site_schema(),
        result_items_key="sites",
        summary_fields=("site_url", "permission_level"),
        skill_refs=_search_console_skill_refs(),
        integration_api_version="v3",
    )
    return ToolBinding(tool_definition(contract), _ListSitesExecutor(client))


def _search_analytics_binding(client: GoogleReadonlyClient) -> ToolBinding:
    contract = ToolContract(
        name="gsc_search_analytics",
        description=(
            "查询 Google Search Console 搜索表现汇总，可按 query、page、date、country、device "
            "和 searchAppearance 分组。需要从 gsc_list_sites 取得 site_url 和 YYYY-MM-DD 日期。"
            "只读；Search Console 可能省略匿名/低频查询及部分长尾数据，不能把返回行当成全量。"
        ),
        action="report",
        resource_type="search_console_report",
        intent_type="query_search_console_report",
        aliases=("查询自然搜索报表", "GSC query 报告", "搜索词点击和曝光", "查询自然流量数据"),
        schema=_search_analytics_schema(),
        result_items_key="rows",
        summary_fields=("query", "page", "clicks", "impressions"),
        skill_refs=_search_console_skill_refs(),
        integration_api_version="v3",
    )
    return ToolBinding(tool_definition(contract), _SearchAnalyticsExecutor(client))


def search_console_tool_source(
    *,
    configuration_provider: Callable[[], Mapping[str, Any]],
    request_get: Callable[..., Any] | None = None,
    request_post: Callable[..., Any] | None = None,
):
    """Publish bounded Search Console site discovery and report Tools."""
    client = GoogleReadonlyClient(
        configuration_provider,
        scope=SEARCH_CONSOLE_SCOPE,
        service_name="Google Search Console",
        request_get=request_get,
        request_post=request_post,
    )
    bindings = [_sites_binding(client), _search_analytics_binding(client)]
    return create_source("marketing:search-console", bindings)


__all__ = ["SEARCH_CONSOLE_SCOPE", "search_console_tool_source"]
