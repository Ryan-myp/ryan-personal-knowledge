"""Shared bounded Google OAuth and HTTP primitives for analytics Tools."""

from __future__ import annotations

import json
import math
import re
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

import requests

from agents.agent_harness import StaticToolSource, ToolBinding
from agents.agent_harness.core.interfaces import (
    ReplayPolicy,
    RiskLevel,
    ToolDefinition,
    ToolEffect,
    ToolResult,
    ToolSchema,
)
from agents.agent_harness.core.security import redact_sensitive_text


GOOGLE_IDENTITY_HOST = "https://oauth2.googleapis.com"
CONNECTOR_TIMEOUT = (3, 15)
MAX_RESPONSE_BYTES = 512_000
MAX_OUTPUT_BYTES = 24_000
MAX_ROWS = 1_000
_PROPERTY_ID = re.compile(r"^[1-9][0-9]{0,19}$")
_API_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_:]{0,99}$")
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")


class AnalyticsToolError(ValueError):
    """Expected provider, configuration, or input failure safe for Tool output."""


def _read_json_response(response: Any) -> Mapping[str, Any]:
    status = int(getattr(response, "status_code", 0))
    if status != 200:
        if status == 400:
            message = "Google OAuth 凭证失效或授权范围不匹配，请重新授权。"
        elif status in {401, 403}:
            message = "Google 拒绝了请求，请检查 API 是否启用以及账号/站点权限。"
        elif status == 404:
            message = "Google 找不到目标资源，请核对 Property ID 或 Search Console 属性。"
        elif status == 429:
            message = "Google API 当前限流，请缩小查询范围后重试。"
        elif status >= 500:
            message = "Google API 暂时不可用，请稍后重试。"
        else:
            message = f"Google API 返回 HTTP {status}，请检查查询参数。"
        raise AnalyticsToolError(message)

    headers = getattr(response, "headers", {}) or {}
    content_length = headers.get("Content-Length") if hasattr(headers, "get") else None
    try:
        declared_size = int(content_length) if content_length else None
    except (TypeError, ValueError):
        declared_size = None
    if declared_size is not None and declared_size > MAX_RESPONSE_BYTES:
        raise AnalyticsToolError("Google API 响应超过大小限制。")

    body = bytearray()
    iterator = getattr(response, "iter_content", None)
    if callable(iterator):
        chunks = iterator(chunk_size=16_384)
    else:
        raw = getattr(response, "content", b"")
        chunks = (raw,) if isinstance(raw, bytes) else ()
    for chunk in chunks:
        if not chunk:
            continue
        if not isinstance(chunk, bytes):
            raise AnalyticsToolError("Google API 返回了无效响应。")
        body.extend(chunk)
        if len(body) > MAX_RESPONSE_BYTES:
            raise AnalyticsToolError("Google API 响应超过大小限制。")
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AnalyticsToolError("Google API 返回了无效 JSON。") from error
    if not isinstance(payload, Mapping):
        raise AnalyticsToolError("Google API 返回了不支持的数据结构。")
    return payload


class GoogleReadonlyClient:
    """Fixed-host Google API client using a cached, read-only OAuth grant."""

    def __init__(
        self,
        configuration_provider: Callable[[], Mapping[str, Any]],
        *,
        scope: str,
        service_name: str = "Google API",
        request_get: Callable[..., Any] | None = None,
        request_post: Callable[..., Any] | None = None,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._configuration_provider = configuration_provider
        self._scope = scope
        self._service_name = str(service_name or "Google API").strip()
        self._request_get = request_get or requests.get
        self._request_post = request_post or requests.post
        self._monotonic = monotonic
        self._lock = threading.Lock()
        self._access_token = ""
        self._expires_at = 0.0

    def _credentials(self) -> dict[str, str]:
        try:
            raw = self._configuration_provider()
        except (OSError, RuntimeError, TypeError, ValueError) as error:
            raise AnalyticsToolError("Google 数据源凭证配置暂时不可用。") from error
        if not isinstance(raw, Mapping):
            raise AnalyticsToolError("Google OAuth 凭证尚未配置。")
        values = {
            field: str(raw.get(field) or "").strip()
            for field in ("client_id", "client_secret", "refresh_token")
        }
        if not all(values.values()):
            raise AnalyticsToolError(
                "尚未配置 OAuth 凭证，请在设置页填写 Client ID、Client Secret 和 Refresh Token。"
            )
        return values

    def _token(self) -> str:
        now = self._monotonic()
        with self._lock:
            if self._access_token and now < self._expires_at - 60:
                return self._access_token
            credentials = self._credentials()
            response = None
            try:
                response = self._request_post(
                    f"{GOOGLE_IDENTITY_HOST}/token",
                    data={
                        "client_id": credentials["client_id"],
                        "client_secret": credentials["client_secret"],
                        "refresh_token": credentials["refresh_token"],
                        "grant_type": "refresh_token",
                        "scope": self._scope,
                    },
                    timeout=CONNECTOR_TIMEOUT,
                    allow_redirects=False,
                    stream=True,
                )
                payload = _read_json_response(response)
            except requests.Timeout as error:
                raise AnalyticsToolError("Google OAuth 请求超时。") from error
            except requests.RequestException as error:
                raise AnalyticsToolError("Google OAuth 暂时无法连接。") from error
            finally:
                close = getattr(response, "close", None)
                if callable(close):
                    close()

            token = payload.get("access_token")
            expires_in = payload.get("expires_in", 3600)
            try:
                expires_seconds = int(expires_in)
            except (TypeError, ValueError, OverflowError) as error:
                raise AnalyticsToolError("Google OAuth 返回了无效的有效期。") from error
            if not isinstance(token, str) or not token.strip() or expires_seconds <= 60:
                raise AnalyticsToolError("Google OAuth 未返回有效的访问令牌。")
            self._access_token = token.strip()
            self._expires_at = self._monotonic() + min(expires_seconds, 86_400)
            return self._access_token

    def get_json(
        self,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]:
        return self._request_json("GET", url, params=params)

    def post_json(
        self,
        url: str,
        *,
        payload: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        return self._request_json("POST", url, payload=payload)

    def _request_json(
        self,
        method: str,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        payload: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]:
        token = self._token()
        response = None
        try:
            request = self._request_get if method == "GET" else self._request_post
            kwargs: dict[str, Any] = {
                "headers": {
                    "Accept": "application/json",
                    "Authorization": f"Bearer {token}",
                },
                "timeout": CONNECTOR_TIMEOUT,
                "allow_redirects": False,
                "stream": True,
            }
            if params is not None:
                kwargs["params"] = dict(params)
            if payload is not None:
                kwargs["json"] = dict(payload)
            response = request(url, **kwargs)
            return _read_json_response(response)
        except requests.Timeout as error:
            raise AnalyticsToolError(f"{self._service_name} 查询超时。") from error
        except requests.RequestException as error:
            raise AnalyticsToolError(f"{self._service_name} 暂时无法连接。") from error
        finally:
            close = getattr(response, "close", None)
            if callable(close):
                close()


def error_result(error: Exception) -> ToolResult:
    if isinstance(error, AnalyticsToolError):
        message = str(error)
    else:
        message = "Google 数据查询失败，请核对参数和授权后重试。"
    return ToolResult.error(redact_sensitive_text(message))


def property_id(value: Any) -> str:
    candidate = str(value or "").strip()
    if not _PROPERTY_ID.fullmatch(candidate):
        raise AnalyticsToolError("GA4 Property ID 必须是纯数字 ID。")
    return candidate


def validate_date_range(start_value: Any, end_value: Any) -> tuple[str, str]:
    start_text = str(start_value or "").strip()
    end_text = str(end_value or "").strip()
    try:
        start_date = date.fromisoformat(start_text)
        end_date = date.fromisoformat(end_text)
    except (TypeError, ValueError) as error:
        raise AnalyticsToolError("开始和结束日期都必须使用 YYYY-MM-DD 格式。") from error
    if start_date > end_date:
        raise AnalyticsToolError("开始日期不能晚于结束日期。")
    return start_text, end_text


def bounded_int(value: Any, label: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool):
        raise AnalyticsToolError(f"{label} 必须是整数。")
    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise AnalyticsToolError(f"{label} 必须是整数。") from error
    if number < minimum or number > maximum:
        raise AnalyticsToolError(f"{label} 必须在 {minimum} 至 {maximum} 之间。")
    return number


def validate_name_list(
    value: Any,
    *,
    label: str,
    required: bool,
    maximum: int,
) -> list[str]:
    if value is None and not required:
        return []
    if not isinstance(value, list):
        raise AnalyticsToolError(f"{label} 必须是数组。")
    if required and not value:
        raise AnalyticsToolError(f"至少需要选择一个{label}。")
    if len(value) > maximum:
        raise AnalyticsToolError(f"{label}最多支持 {maximum} 项。")
    normalized = []
    for item in value:
        if not isinstance(item, str) or not _API_NAME.fullmatch(item.strip()):
            raise AnalyticsToolError(f"{label}包含无效的 Google Analytics 字段名。")
        normalized.append(item.strip())
    if len(set(normalized)) != len(normalized):
        raise AnalyticsToolError(f"{label}不能重复。")
    return normalized


def date_time_metadata(*, source: str, source_url: str) -> dict[str, str]:
    return {
        "source": source,
        "source_url": source_url,
        "data_status": "live_external",
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
    }


def safe_number(value: Any) -> int | float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(number):
        return None
    return int(number) if number.is_integer() else number


def tool_schema(
    properties: dict[str, Any],
    required: list[str],
) -> ToolSchema:
    return ToolSchema(
        properties=properties,
        required=required,
        additional_properties=False,
    )


@dataclass(frozen=True)
class ToolContract:
    name: str
    description: str
    action: str
    resource_type: str
    intent_type: str
    aliases: tuple[str, ...]
    schema: ToolSchema
    result_items_key: str | None = None
    summary_fields: tuple[str, ...] = ()
    skill_refs: tuple[str, ...] = ()
    integration_api_version: str | None = None


def tool_definition(contract: ToolContract) -> ToolDefinition:
    return ToolDefinition(
        name=contract.name,
        skill="marketing-analytics",
        namespace="marketing_analytics",
        description=contract.description,
        input_schema=contract.schema,
        action=contract.action,
        resource_type=contract.resource_type,
        intent_types=[contract.intent_type],
        intent_aliases=list(contract.aliases),
        skill_refs=list(contract.skill_refs),
        risk_level=RiskLevel.LOW,
        effect_class=ToolEffect.READ,
        replay_policy=ReplayPolicy.SAFE,
        traits=[
            "structured_analytics_data",
            "external_private_data",
            "read_only",
            "bounded_output",
            "untrusted_external_content",
        ],
        timeout_seconds=25,
        max_output_bytes=MAX_OUTPUT_BYTES,
        required_permissions=["analytics.read"],
        integration_api_version=contract.integration_api_version,
        scope_required=False,
        result_items_key=contract.result_items_key,
        result_summary_fields=list(contract.summary_fields),
        contract_version="1.0.0",
    )


def create_source(source_id: str, bindings: list[ToolBinding]) -> StaticToolSource:
    return StaticToolSource(source_id, bindings)


def _safe_string(value: Any, limit: int = 300) -> str:
    if not isinstance(value, str):
        return ""
    cleaned = _CONTROL_CHARS.sub(" ", redact_sensitive_text(value))
    return " ".join(cleaned.split())[:limit]


def require_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise AnalyticsToolError(f"Google Analytics 返回了无效的{label}结构。")
    return value


def scalar_list(value: Any, *, maximum: int, label: str) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        raise AnalyticsToolError(f"Google Analytics 返回了无效的{label}列表。")
    return [item for item in value[:maximum] if isinstance(item, Mapping)]
