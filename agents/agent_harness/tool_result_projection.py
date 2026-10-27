"""Project retained Tool results into a bounded, model-facing view."""

from __future__ import annotations

from typing import Any, Callable, Mapping


def _value(definition: Any, name: str, default: Any = None) -> Any:
    return definition.get(name, default) if isinstance(definition, Mapping) else (
        getattr(definition, name, default)
    )


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


def model_tool_content(
    value: Any,
    definition: Any,
    *,
    bound_output: Callable[[Any], Any],
    is_write: bool,
) -> Any:
    data = value.get("data") if isinstance(value, Mapping) else None
    if isinstance(data, Mapping) and isinstance(data.get("parameter_selections"), list):
        # Selection proofs stay in the retained result, outside model context.
        value = dict(value)
        value["data"] = {
            key: item for key, item in data.items()
            if key != "parameter_selections"
        }
    collection = _value(definition, "result_items_key")
    data = value.get("data") if isinstance(value, Mapping) else None
    rows = data.get(collection) if isinstance(data, Mapping) and collection else None
    if not isinstance(rows, list) or is_write:
        return bound_output(value)

    summary = {
        "collection": collection, "returned_count": len(rows),
        "context_count": len(rows), "context_truncated": False,
        "scope": "returned_page",
    }
    facets, other_counts = _categorical_facets(
        rows, _value(definition, "result_summary_fields", ()) or (),
    )
    if facets:
        summary["facets"] = facets
    if other_counts:
        summary["facet_other_counts"] = other_counts

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
