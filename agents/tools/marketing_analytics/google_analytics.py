"""Read-only Google Analytics 4 property discovery and Data API reports."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

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
    property_id,
    require_mapping,
    safe_number,
    scalar_list,
    tool_definition,
    ToolContract,
    tool_schema,
    validate_date_range,
    validate_name_list,
)


ANALYTICS_SCOPE = "https://www.googleapis.com/auth/analytics.readonly"
ADMIN_API_ROOT = "https://analyticsadmin.googleapis.com/v1beta"
DATA_API_ROOT = "https://analyticsdata.googleapis.com/v1beta"
MAX_PROPERTIES_PER_PAGE = 100
MAX_METADATA_FIELDS = 250


class _AnalyticsExecutor:
    def __init__(self, client: GoogleReadonlyClient) -> None:
        self._client = client

    @staticmethod
    def _error(error: Exception) -> ToolResult:
        return error_result(error)


class _ListPropertiesExecutor(_AnalyticsExecutor):
    def execute(self, _context: Any, arguments: dict[str, Any]) -> ToolResult:
        page_token = str(arguments.get("page_token") or "").strip()
        if len(page_token) > 512:
            return ToolResult.error("GA4 page_token 超过长度限制。")
        params: dict[str, Any] = {"pageSize": MAX_PROPERTIES_PER_PAGE}
        if page_token:
            params["pageToken"] = page_token
        try:
            response = self._client.get_json(
                f"{ADMIN_API_ROOT}/accountSummaries",
                params=params,
            )
            properties = self._properties(response.get("accountSummaries", []))
            next_page_token = _safe_string(response.get("nextPageToken"), 512)
            return ToolResult.ok({
                **date_time_metadata(
                    source="Google Analytics Admin API",
                    source_url=f"{ADMIN_API_ROOT}/accountSummaries",
                ),
                "properties": properties,
                "next_page_token": next_page_token or None,
                "has_more": bool(next_page_token),
            })
        except (AnalyticsToolError, requests.RequestException, TypeError, ValueError) as error:
            return self._error(error)

    @staticmethod
    def _properties(accounts: Any) -> list[dict[str, str]]:
        if not isinstance(accounts, list):
            raise AnalyticsToolError("GA4 返回了无效的账号列表。")
        properties = []
        for account in accounts:
            if not isinstance(account, Mapping):
                continue
            account_id = _safe_string(account.get("account"), 120)
            account_name = _safe_string(account.get("displayName"), 160)
            summaries = account.get("propertySummaries", [])
            if not isinstance(summaries, list):
                continue
            properties.extend(
                _property_summaries(account_id, account_name, summaries)
            )
            if len(properties) >= MAX_PROPERTIES_PER_PAGE:
                break
        return properties[:MAX_PROPERTIES_PER_PAGE]


def _property_summaries(
    account_id: str,
    account_name: str,
    summaries: list[Any],
) -> list[dict[str, str]]:
    results = []
    for summary in summaries:
        if not isinstance(summary, Mapping):
            continue
        resource_name = _safe_string(summary.get("property"), 100)
        selected_id = resource_name.removeprefix("properties/")
        if not selected_id.isdigit():
            continue
        results.append({
            "account": account_id,
            "account_name": account_name,
            "property_id": selected_id,
            "property_name": _safe_string(summary.get("displayName"), 160),
        })
    return results


class _GetMetadataExecutor(_AnalyticsExecutor):
    def execute(self, _context: Any, arguments: dict[str, Any]) -> ToolResult:
        try:
            selected_id = property_id(arguments.get("property_id"))
            endpoint = f"{DATA_API_ROOT}/properties/{selected_id}/metadata"
            response = self._client.get_json(endpoint)
            dimensions = scalar_list(
                response.get("dimensions", []),
                maximum=MAX_METADATA_FIELDS,
                label="dimension",
            )
            metrics = scalar_list(
                response.get("metrics", []),
                maximum=MAX_METADATA_FIELDS,
                label="metric",
            )
            return ToolResult.ok({
                **date_time_metadata(
                    source="Google Analytics Data API metadata",
                    source_url=endpoint,
                ),
                "property_id": selected_id,
                "dimensions": [
                    _metadata_item(item)
                    for item in dimensions
                    if item.get("apiName")
                ],
                "metrics": [
                    _metadata_item(item)
                    for item in metrics
                    if item.get("apiName")
                ],
                "truncated": (
                    _list_length(response.get("dimensions")) > MAX_METADATA_FIELDS
                    or _list_length(response.get("metrics")) > MAX_METADATA_FIELDS
                ),
            })
        except (AnalyticsToolError, requests.RequestException, TypeError, ValueError) as error:
            return self._error(error)


@dataclass(frozen=True)
class _ReportQuery:
    property_id: str
    start_date: str
    end_date: str
    dimensions: list[str]
    metrics: list[str]
    limit: int
    offset: int
    endpoint: str
    payload: dict[str, Any]


def _build_report_query(arguments: Mapping[str, Any]) -> _ReportQuery:
    selected_id = property_id(arguments.get("property_id"))
    start_date, end_date = validate_date_range(
        arguments.get("start_date"), arguments.get("end_date"),
    )
    dimensions = validate_name_list(
        arguments.get("dimensions"), label="dimensions", required=False,
        maximum=9,
    )
    metrics = validate_name_list(
        arguments.get("metrics"), label="metrics", required=True, maximum=10,
    )
    limit = bounded_int(arguments.get("limit", 500), "limit", 1, MAX_ROWS)
    offset = bounded_int(arguments.get("offset", 0), "offset", 0, 250_000)
    payload: dict[str, Any] = {
        "dateRanges": [{"startDate": start_date, "endDate": end_date}],
        "dimensions": [{"name": name} for name in dimensions],
        "metrics": [{"name": name} for name in metrics],
        "limit": limit,
        "offset": offset,
    }
    _add_currency(payload, arguments.get("currency_code"))
    endpoint = f"{DATA_API_ROOT}/properties/{selected_id}:runReport"
    return _ReportQuery(
        selected_id, start_date, end_date, dimensions, metrics,
        limit, offset, endpoint, payload,
    )


def _add_currency(payload: dict[str, Any], value: Any) -> None:
    currency = str(value or "").strip().upper()
    if not currency:
        return
    if len(currency) != 3 or not currency.isascii() or not currency.isalpha():
        raise AnalyticsToolError("currency_code 必须是 ISO 4217 三位代码。")
    payload["currencyCode"] = currency


def _safe_row_count(value: Any) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError, OverflowError):
        return 0


class _RunReportExecutor(_AnalyticsExecutor):
    def execute(self, _context: Any, arguments: dict[str, Any]) -> ToolResult:
        try:
            query = _build_report_query(arguments)
            response = self._client.post_json(query.endpoint, payload=query.payload)
            return ToolResult.ok(self._report_result(response, query))
        except (AnalyticsToolError, requests.RequestException, TypeError, ValueError) as error:
            return self._error(error)

    @classmethod
    def _report_result(
        cls,
        response: Mapping[str, Any],
        query: "_ReportQuery",
    ) -> dict[str, Any]:
        raw_rows = response.get("rows", [])
        if not isinstance(raw_rows, list):
            raise AnalyticsToolError("GA4 返回了无效的报告行。")
        row_count = _safe_row_count(response.get("rowCount", 0))
        rows = [
            cls._map_row(row, query.dimensions, query.metrics)
            for row in raw_rows[:query.limit]
            if isinstance(row, Mapping)
        ]
        next_offset = query.offset + len(rows)
        return {
            **date_time_metadata(
                source="Google Analytics Data API",
                source_url=query.endpoint,
            ),
            "property_id": query.property_id,
            "date_range": {
                "start_date": query.start_date,
                "end_date": query.end_date,
            },
            "dimensions": query.dimensions,
            "metrics": query.metrics,
            "row_count": row_count,
            "returned_rows": len(rows),
            "offset": query.offset,
            "next_offset": next_offset if next_offset < row_count else None,
            "rows": rows,
        }

    @staticmethod
    def _map_row(
        row: Mapping[str, Any],
        dimensions: list[str],
        metrics: list[str],
    ) -> dict[str, Any]:
        dimension_values = row.get("dimensionValues", [])
        metric_values = row.get("metricValues", [])
        if not isinstance(dimension_values, list):
            dimension_values = []
        if not isinstance(metric_values, list):
            metric_values = []
        result = {}
        for index, name in enumerate(dimensions):
            value = dimension_values[index] if index < len(dimension_values) else {}
            result[name] = _safe_string(
                value.get("value") if isinstance(value, Mapping) else "",
                500,
            )
        for index, name in enumerate(metrics):
            value = metric_values[index] if index < len(metric_values) else {}
            result[name] = safe_number(
                value.get("value") if isinstance(value, Mapping) else None
            )
        return result


def _metadata_item(item: Mapping[str, Any]) -> dict[str, str]:
    result = {
        "name": _safe_string(item.get("apiName"), 100),
        "label": _safe_string(item.get("uiName"), 200),
    }
    category = _safe_string(item.get("category"), 100)
    if category:
        result["category"] = category
    return result


def _list_length(value: Any) -> int:
    return len(value) if isinstance(value, list) else 0


def _property_schema() -> ToolSchema:
    return tool_schema({
        "page_token": {
            "type": "string",
            "maxLength": 512,
            "description": "可选，上一页返回的 next_page_token。",
        },
    }, [])


def _metadata_schema() -> ToolSchema:
    return tool_schema({
        "property_id": {
            "type": "string",
            "pattern": "^[1-9][0-9]{0,19}$",
            "description": "GA4 Property ID，使用纯数字，不含 properties/ 前缀。",
        },
    }, ["property_id"])


def _report_schema() -> ToolSchema:
    return tool_schema({
        "property_id": {
            "type": "string",
            "pattern": "^[1-9][0-9]{0,19}$",
            "description": "GA4 Property ID，使用纯数字，不含 properties/ 前缀。",
        },
        "start_date": {"type": "string", "format": "date"},
        "end_date": {"type": "string", "format": "date"},
        "dimensions": {
            "type": "array",
            "maxItems": 9,
            "items": {"type": "string", "maxLength": 100},
            "description": "先通过 ga4_get_metadata 查询当前 Property 支持的字段；可省略。",
        },
        "metrics": {
            "type": "array",
            "minItems": 1,
            "maxItems": 10,
            "items": {"type": "string", "maxLength": 100},
            "description": "至少一个指标；建议从 ga4_get_metadata 返回的指标中选择。",
        },
        "limit": {
            "type": "integer",
            "minimum": 1,
            "maximum": MAX_ROWS,
            "default": 500,
        },
        "offset": {
            "type": "integer",
            "minimum": 0,
            "maximum": 250_000,
            "default": 0,
        },
        "currency_code": {
            "type": "string",
            "pattern": "^[A-Za-z]{3}$",
            "description": "可选，ISO 4217 三位币种代码。",
        },
    }, ["property_id", "start_date", "end_date", "metrics"])


def _properties_binding(client: GoogleReadonlyClient) -> ToolBinding:
    contract = ToolContract(
        name="ga4_list_properties",
        description=(
            "列出当前 OAuth 授权账号可访问的 GA4 Account 和 Property。用于发现可查询的"
            " Property ID；只读，不会修改 Google Analytics 配置。需要 GA4 OAuth 授权。"
        ),
        action="list",
        resource_type="analytics_property",
        intent_type="list_analytics_properties",
        aliases=("查询 GA4 属性", "列出 GA4 Property", "查询 Google Analytics 账号"),
        schema=_property_schema(),
        result_items_key="properties",
        summary_fields=("property_id", "property_name", "account_name"),
        skill_refs=_shared_skill_refs(),
        integration_api_version="v1beta",
    )
    return ToolBinding(tool_definition(contract), _ListPropertiesExecutor(client))


def _metadata_binding(client: GoogleReadonlyClient) -> ToolBinding:
    contract = ToolContract(
        name="ga4_get_metadata",
        description=(
            "查询一个 GA4 Property 当前可用的 dimensions 和 metrics；"
            "运行报告前先核对字段。只读，不提供用户级事件明细。"
        ),
        action="get",
        resource_type="analytics_metadata",
        intent_type="get_analytics_metadata",
        aliases=("查询 GA4 字段", "GA4 支持哪些维度指标", "查看 Analytics metadata"),
        schema=_metadata_schema(),
        skill_refs=_shared_skill_refs(),
        integration_api_version="v1beta",
    )
    return ToolBinding(tool_definition(contract), _GetMetadataExecutor(client))


def _report_binding(client: GoogleReadonlyClient) -> ToolBinding:
    contract = ToolContract(
        name="ga4_run_report",
        description=(
            "查询 GA4 汇总报告。需要 Property ID、精确日期范围、至少一个 metric；"
            "dimensions 和 metrics 应先通过 ga4_get_metadata 校验。支持来源/媒介、campaign、"
            "落地页、会话、关键事件和收入等 GA4 可用字段；只返回聚合行。"
        ),
        action="report",
        resource_type="analytics_report",
        intent_type="query_analytics_report",
        aliases=("查询 GA4 报表", "分析网站转化", "查询落地页会话", "GA4 campaign 报告"),
        schema=_report_schema(),
        result_items_key="rows",
        summary_fields=(
            "sessionSourceMedium", "sessionCampaignName", "sessions", "keyEvents",
        ),
        skill_refs=(*_shared_skill_refs(), "influencer-partnerships"),
        integration_api_version="v1beta",
    )
    return ToolBinding(tool_definition(contract), _RunReportExecutor(client))


def _shared_skill_refs() -> tuple[str, ...]:
    return (
        "measurement-instrumentation",
        "measurement-attribution",
        "account-diagnostics",
        "seo-growth",
    )


def google_analytics_tool_source(
    *,
    configuration_provider: Callable[[], Mapping[str, Any]],
    request_get: Callable[..., Any] | None = None,
    request_post: Callable[..., Any] | None = None,
):
    """Publish bounded GA4 account discovery, metadata, and report Tools."""
    client = GoogleReadonlyClient(
        configuration_provider,
        scope=ANALYTICS_SCOPE,
        service_name="Google Analytics",
        request_get=request_get,
        request_post=request_post,
    )
    bindings = [
        _properties_binding(client),
        _metadata_binding(client),
        _report_binding(client),
    ]
    return create_source("marketing:google-analytics", bindings)


__all__ = ["ANALYTICS_SCOPE", "google_analytics_tool_source"]
