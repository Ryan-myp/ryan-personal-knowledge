"""Shared contracts and bounded-result helpers for public reference Tools."""

from __future__ import annotations

import math
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any, Mapping
from urllib.parse import urlsplit

from agents.agent_harness.core.interfaces import ToolDefinition
from agents.agent_harness.core.security import redact_sensitive_text
from agents.agent_platform.tools.public_data import (
    _PublicDataError,
    _PublicDataToolSpec,
    _definition,
    _schema,
)


MAX_QUERY_CHARS = 300
MAX_RESULTS = 10
CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")


class HTMLTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def clean_text(value: Any, limit: int = 500) -> str:
    if not isinstance(value, str):
        return ""
    parser = HTMLTextParser()
    try:
        parser.feed(value)
        parser.close()
        text = " ".join(parser.parts)
    except (ValueError, AssertionError):
        text = value
    return " ".join(redact_sensitive_text(text).split())[:limit].strip()


def validate_query(value: Any, name: str = "query") -> str:
    if not isinstance(value, str):
        raise _PublicDataError(f"{name} 必须是文本")
    normalized = value.strip()
    if not normalized or len(normalized) > MAX_QUERY_CHARS:
        raise _PublicDataError(
            f"{name} 长度需在 1 至 {MAX_QUERY_CHARS} 个字符之间"
        )
    if CONTROL_CHARS.search(normalized):
        raise _PublicDataError(f"{name} 包含不支持的控制字符")
    return normalized


def validate_limit(value: Any, *, default: int = 5) -> int:
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, int):
        raise _PublicDataError("结果数量必须是整数")
    if value < 1 or value > MAX_RESULTS:
        raise _PublicDataError(f"结果数量需在 1 至 {MAX_RESULTS} 之间")
    return value


def require_list(payload: Any, key: str, api_name: str) -> list[Any]:
    if not isinstance(payload, Mapping) or not isinstance(payload.get(key), list):
        raise _PublicDataError(f"{api_name} 返回了不支持的数据结构")
    return payload[key]


def first_text(value: Any, *, limit: int = 120) -> str:
    if not isinstance(value, list) or not value:
        return ""
    first = value[0]
    if isinstance(first, Mapping):
        first = first.get("value")
    return clean_text(first, limit)


def number(value: Any, *, integer: bool = False) -> int | float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(parsed):
        return None
    return int(parsed) if integer else parsed


def safe_https_url(value: Any, *, max_length: int = 2048) -> str:
    if not isinstance(value, str):
        return ""
    candidate = value.strip()
    if not candidate or len(candidate) > max_length:
        return ""
    try:
        parsed = urlsplit(candidate)
        if (
            parsed.scheme.lower() != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
        ):
            return ""
        parsed.port
    except ValueError:
        return ""
    return redact_sensitive_text(candidate)


def result_metadata(
    *,
    source: str,
    source_url: str,
    data: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "source": source,
        "source_url": source_url,
        "data_status": "live_external",
        **data,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
    }


def string_schema(
    description: str,
    *,
    minimum: int = 1,
    maximum: int = MAX_QUERY_CHARS,
) -> dict[str, Any]:
    return {
        "type": "string",
        "minLength": minimum,
        "maxLength": maximum,
        "description": description,
    }


def tool_definition(
    spec: _PublicDataToolSpec,
    permission: str,
) -> ToolDefinition:
    definition = _definition(spec, permission)
    definition.traits.extend(("structured_public_api", "untrusted_external_content"))
    return definition


__all__ = [
    "MAX_QUERY_CHARS",
    "MAX_RESULTS",
    "clean_text",
    "first_text",
    "number",
    "require_list",
    "result_metadata",
    "safe_https_url",
    "string_schema",
    "tool_definition",
    "validate_limit",
    "validate_query",
]
