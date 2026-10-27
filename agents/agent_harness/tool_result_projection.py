"""Project retained Tool results into a bounded, model-facing view."""

from __future__ import annotations

from typing import Any, Callable, Mapping


def _value(definition: Any, name: str, default: Any = None) -> Any:
    return definition.get(name, default) if isinstance(definition, Mapping) else (
        getattr(definition, name, default)
    )


def _requested_page_size(
    arguments: Mapping[str, Any] | None, definition: Any,
) -> tuple[str, int] | None:
    if not isinstance(arguments, Mapping):
        return None
    schema = _value(definition, "input_schema")
    properties = _value(schema, "properties", {})
    if not isinstance(properties, Mapping):
        return None
    for field in ("limit", "page_size", "pageSize", "max_results"):
        spec = properties.get(field)
        value = arguments.get(field)
        if (
            isinstance(spec, Mapping)
            and spec.get("type") == "integer"
            and type(value) is int
            and value > 0
        ):
            return field, value
    return None


def _explicit_has_more(data: Mapping[str, Any]) -> bool | None:
    containers = [data]
    containers.extend(
        value for key in ("query_summary", "query_context", "page_info")
        if isinstance((value := data.get(key)), Mapping)
    )
    for container in containers:
        for key in ("has_more", "has_next_page", "hasNextPage"):
            value = container.get(key)
            if type(value) is bool:
                return value
        for key in ("next_page_token", "nextPageToken", "next_cursor"):
            if container.get(key) not in (None, "", [], {}):
                return True
    return None


def _explicit_truncation(data: Mapping[str, Any]) -> bool | None:
    for key in ("query_context", "query_summary"):
        context = data.get(key)
        value = context.get("may_be_truncated") if isinstance(context, Mapping) else None
        if type(value) is bool:
            return value
    value = data.get("may_be_truncated")
    return value if type(value) is bool else None


def _categorical_facets(
    rows: list[Any], fields: list[str],
) -> tuple[dict[str, dict[str, int]], dict[str, int]]:
    facets: dict[str, dict[str, int]] = {}
    other_counts: dict[str, int] = {}
    for field in fields[:4]:
        counts: dict[str, int] = {}
        other = 0
        for row in rows:
            raw = row.get(field) if isinstance(row, Mapping) else None
            label = (
                str(raw)
                if isinstance(raw, (str, int)) and not isinstance(raw, bool)
                else ""
            )
            if not label or len(label) > 64:
                other += 1
            elif label in counts:
                counts[label] += 1
            elif len(counts) < 16:
                counts[label] = 1
            else:
                other += 1
        if other:
            other_counts[field] = other
        facets[field] = counts
    return facets, other_counts


def _pagination_summary(
    data: Mapping[str, Any],
    rows: list[Any],
    page_size: tuple[str, int] | None,
) -> dict[str, Any]:
    explicit_has_more = _explicit_has_more(data)
    provider_truncation = _explicit_truncation(data)
    if explicit_has_more is True:
        may_be_truncated: bool | None = True
    elif provider_truncation is not None:
        may_be_truncated = provider_truncation
    elif explicit_has_more is not None:
        may_be_truncated = explicit_has_more
    elif page_size and len(rows) >= page_size[1]:
        may_be_truncated = True
    else:
        may_be_truncated = None
    summary: dict[str, Any] = {}
    if page_size:
        summary["requested_page_size"] = page_size[1]
        summary["page_size_field"] = page_size[0]
    if explicit_has_more is not None:
        summary["provider_has_more"] = explicit_has_more
    if may_be_truncated is not None:
        summary["may_be_truncated"] = may_be_truncated
    summary["completeness"] = (
        "possibly_truncated" if may_be_truncated
        else "page_complete" if (
            provider_truncation is False or explicit_has_more is False
        )
        else "within_requested_limit" if page_size
        else "unknown"
    )
    return summary


def _query_summary(
    data: Mapping[str, Any],
    rows: list[Any],
    definition: Any,
    arguments: Mapping[str, Any] | None,
    collection: str,
) -> dict[str, Any]:
    provider_summary = data.get("query_summary")
    provider_summary = provider_summary if isinstance(provider_summary, Mapping) else {}
    summary = {
        "collection": collection, "returned_count": min(len(rows), 1_000_000),
        "context_count": len(rows), "context_truncated": False,
        "scope": "returned_page",
    }
    summary.update(_pagination_summary(
        data, rows, _requested_page_size(arguments, definition),
    ))
    total_count = data.get(
        "total_count", data.get("total", provider_summary.get("total_count")),
    )
    if type(total_count) is int and total_count >= 0:
        summary["total_count"] = min(total_count, 1_000_000)
    facets, other_counts = _categorical_facets(
        rows, _value(definition, "result_summary_fields", ()) or (),
    )
    if facets:
        summary["facets"] = facets
    if other_counts:
        summary["facet_other_counts"] = other_counts
    return summary


def _without_parameter_selections(value: Any) -> Any:
    data = value.get("data") if isinstance(value, Mapping) else None
    if isinstance(data, Mapping) and isinstance(data.get("parameter_selections"), list):
        # Selection proofs stay in the retained result, outside model context.
        value = dict(value)
        value["data"] = {
            key: item for key, item in data.items()
            if key != "parameter_selections"
        }
    return value


def model_tool_content(
    value: Any,
    definition: Any,
    *,
    bound_output: Callable[[Any], Any],
    is_write: bool,
    arguments: Mapping[str, Any] | None = None,
) -> Any:
    value = _without_parameter_selections(value)
    collection = _value(definition, "result_items_key")
    data = value.get("data") if isinstance(value, Mapping) else None
    rows = data.get(collection) if isinstance(data, Mapping) and collection else None
    if not isinstance(rows, list) or is_write:
        return bound_output(value)
    summary = _query_summary(data, rows, definition, arguments, str(collection))
    content = bound_output({
        **value, "data": {**data, "query_summary": summary},
    })
    preview = content.get("data") if isinstance(content, Mapping) else None
    visible_summary = preview.get("query_summary") if isinstance(preview, Mapping) else None
    if isinstance(visible_summary, dict):
        visible_rows = preview.get(collection)
        visible_summary["context_count"] = (
            len(visible_rows) if isinstance(visible_rows, list) else 0
        )
        visible_summary["context_truncated"] = bool(content.get("output_truncated"))
    return content
