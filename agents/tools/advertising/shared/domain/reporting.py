"""Provider-neutral reporting context for bounded read Tools."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def build_report_context(
    *,
    provider: str,
    resource_level: str,
    input_data: Mapping[str, Any],
    rows: Any,
    default_period: Any,
    default_limit: int,
) -> dict[str, Any]:
    """Describe a report request without inferring unavailable account settings."""
    period, period_source = _requested_period(input_data, default_period)
    row_count = _count_rows(rows)
    row_limit = _positive_integer(input_data.get("limit"), default_limit)
    may_be_truncated = row_limit is not None and row_count >= row_limit

    return {
        "provider": str(provider or "unknown").strip().lower(),
        "resource_level": str(resource_level or "unknown").strip().lower(),
        "period": {"value": period, "source": period_source},
        "account_timezone": {"value": None, "status": "unknown"},
        "account_currency": {"value": None, "status": "unknown"},
        "attribution": {"value": None, "status": "not_returned_by_tool"},
        "completeness": {
            "returned_rows": row_count,
            "row_limit": row_limit,
            "may_be_truncated": may_be_truncated,
            "status": (
                "empty"
                if row_count == 0
                else "possibly_truncated"
                if may_be_truncated
                else "within_limit"
            ),
        },
    }


def _requested_period(
    input_data: Mapping[str, Any],
    default_period: Any,
) -> tuple[Any, str]:
    start = input_data.get("start_date", input_data.get("date_from"))
    end = input_data.get("end_date", input_data.get("date_to"))
    if start not in (None, "") or end not in (None, ""):
        return {
            "start_date": start,
            "end_date": end,
        }, "tool_input"

    for field in ("date_range", "date_preset"):
        value = input_data.get(field)
        if value not in (None, ""):
            return _copy_period(value), "tool_input"
    return _copy_period(default_period), "provider_default"


def _copy_period(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): child for key, child in value.items()}
    if isinstance(value, (list, tuple)):
        return list(value)
    return value


def _count_rows(rows: Any) -> int:
    if isinstance(rows, (list, tuple)):
        return len(rows)
    if isinstance(rows, Mapping):
        for key in ("rows", "results", "data", "list"):
            nested = rows.get(key)
            if isinstance(nested, (list, tuple)):
                return len(nested)
        return 1 if rows else 0
    return 0


def _positive_integer(value: Any, default: int) -> int | None:
    for candidate in (value, default):
        if isinstance(candidate, bool):
            continue
        try:
            normalized = int(candidate)
        except (TypeError, ValueError):
            continue
        if normalized > 0:
            return normalized
    return None
