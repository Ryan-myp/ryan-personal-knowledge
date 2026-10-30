"""Shared JSON-safe Tool evidence bounds, independent of execution policy."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any


_PRIORITY = {
    "id": 0, "resource_id": 0,
    "type": 0, "kind": 1, "question": 2, "prompt": 3,
    "needs_input": 4, "needs_confirmation": 5, "confirmation_payload": 6, "payload": 7,
    "success": 0, "error": 1, "data_status": 2, "execution_status": 3, "effect_state": 4,
    "requires_reconciliation": 5, "query_summary": 6, "total_count": 6,
    "total": 7, "count": 8, "has_more": 9, "next_page": 10, "page_info": 11, "data": 12,
    "next_cursor": 10, "next_page_token": 10, "nextpagetoken": 10,
    "paging": 11, "pagination": 11,
}

# Continuation values are opaque API input. A shortened token is a different
# token, so omit it explicitly when it cannot fit instead of inventing a value.
_PAGINATION_FIELDS = {
    "next_cursor", "next_page_token", "nextpagetoken", "next_page",
    "page_info", "paging", "pagination",
}


def serialize_tool_value(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    except (TypeError, ValueError):
        return json.dumps(str(value), ensure_ascii=False)


def truncate_tool_text(value: str, budget: int) -> str:
    marker = "\n...[tool output truncated]"
    low, high, best = 0, len(value), ""
    while low <= high:
        middle = (low + high) // 2
        candidate = value[:middle] + (marker if middle < len(value) else "")
        if len(serialize_tool_value(candidate)) <= budget:
            best, low = candidate, middle + 1
        else:
            high = middle - 1
    return best


def compact_tool_value(value: Any, budget: int, path: str) -> tuple[Any, list[str]]:
    if len(serialize_tool_value(value)) <= budget:
        return value, []
    if isinstance(value, Mapping):
        return _compact_mapping(value, budget, path)
    if isinstance(value, (list, tuple)):
        return _compact_sequence(value, budget, path)
    return truncate_tool_text(str(value), budget), [path or "$"]


def _compact_mapping(value: Mapping, budget: int, path: str) -> tuple[dict, list[str]]:
    result, paths, size = {}, [], 2
    keys = sorted(value, key=lambda key: (_PRIORITY.get(str(key).lower(), 100), str(key).lower()))
    for key in keys:
        field = str(key)
        child_path = f"{path}.{field}" if path else field
        overhead = len(serialize_tool_value(field)) + 2 + (2 if result else 0)
        remaining = budget - size - overhead
        if remaining < 2:
            paths.append(child_path)
            continue
        if (field.lower() in _PAGINATION_FIELDS
                and len(serialize_tool_value(value[key])) > remaining):
            paths.append(child_path)
            continue
        child, truncated = compact_tool_value(value[key], remaining, child_path)
        child_size = len(serialize_tool_value(child))
        if size + overhead + child_size > budget:
            paths.append(child_path)
            continue
        result[field] = child
        size += overhead + child_size
        paths.extend(truncated)
    return result, paths


def _compact_sequence(value: list | tuple, budget: int, path: str) -> tuple[list, list[str]]:
    result, paths, size = [], [], 2
    for index, raw in enumerate(value):
        overhead = 2 if result else 0
        if budget - size - overhead < 2:
            break
        child, truncated = compact_tool_value(raw, budget - size - overhead, f"{path}[{index}]")
        extra = len(serialize_tool_value(child)) + overhead
        if size + extra > budget:
            break
        result.append(child)
        size += extra
        paths.extend(truncated)
    if len(result) < len(value):
        paths.append(path or "$")
    return result, paths


def bound_tool_output(value: Any, max_chars: int) -> Any:
    if type(max_chars) is not int or max_chars <= 0:
        raise ValueError("Tool output budget must be a positive integer")
    text = value if isinstance(value, str) else serialize_tool_value(value)
    if len(text) <= max_chars:
        return value
    if isinstance(value, str):
        return truncate_tool_text(value, max_chars)
    max_paths = min(8, max(1, max_chars // 512))
    path_chars = 32 if max_chars < 512 else 96
    reserve = len(serialize_tool_value({
        "output_truncated": True, "truncated_fields": ["x" * path_chars] * max_paths,
    }))
    bounded, truncated = compact_tool_value(value, max(2, max_chars - reserve), "")
    paths = [path[:path_chars] for path in dict.fromkeys(truncated)][:max_paths] or ["$"]
    if isinstance(bounded, Mapping):
        return _fit_structured_output({
            **bounded, "output_truncated": True, "truncated_fields": paths,
        }, max_chars)
    if isinstance(value, (list, tuple)):
        return _fit_structured_output({
            "items": bounded, "output_truncated": True, "truncated_fields": paths,
        }, max_chars)
    return bounded


def _fit_structured_output(value: Mapping, budget: int) -> Mapping:
    for candidate in (value, {"output_truncated": True}, {}):
        if len(serialize_tool_value(candidate)) <= budget:
            return candidate
    raise ValueError("Structured Tool output needs a budget of at least two characters")
