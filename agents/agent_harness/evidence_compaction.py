"""Shrink completed read previews without rewriting execution or user facts."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from typing import Any, Callable, Mapping, Sequence

from .messages import AgentMessage


@dataclass(frozen=True)
class _PreviewSource:
    message: AgentMessage
    content: Mapping[str, Any]
    collection: str
    original_count: int


def _field(value: Any, key: str, default: Any = None) -> Any:
    return value.get(key, default) if isinstance(value, Mapping) else getattr(value, key, default)


def _protected(value: Mapping[str, Any]) -> bool:
    flags = (
        "is_error", "needs_input", "needs_confirmation", "requires_confirmation",
        "recovery_required", "requires_reconciliation", "interaction", "confirmation_payload",
        "error", "error_detail", "terminate", "cancelled",
    )
    return any(value.get(key) for key in flags) or any(
        value.get(key) == "unknown" for key in ("effect_state", "execution_status")
    )


def _read_collection(message: AgentMessage, definition: Any) -> tuple | None:
    effect = _field(definition, "effect_class", _field(definition, "effect"))
    if getattr(effect, "value", effect) != "read" or _protected(message.metadata):
        return None
    content = message.content
    if isinstance(content, str):
        try:
            content = json.loads(content)
        except (ValueError, RecursionError):
            return None
    if not isinstance(content, Mapping) or content.get("success") is not True:
        return None
    data = content.get("data")
    if not isinstance(data, Mapping) or _protected(content) or _protected(data):
        return None
    collection = _field(definition, "result_items_key")
    rows = data.get(collection) if isinstance(collection, str) else None
    if not isinstance(rows, list) or not rows:
        return None
    return content, collection, rows


def _declared_calls(message: AgentMessage) -> dict[str, str]:
    return {
        str(call["id"]): str(call["name"])
        for call in message.metadata.get("tool_calls", ())
        if isinstance(call, Mapping) and call.get("id") and call.get("name")
    }


def _completed_reads(messages: Sequence[AgentMessage], definitions: Sequence[Any]):
    catalog = {_field(item, "name"): item for item in definitions}
    pending: dict[str, str] = {}
    for index, message in enumerate(messages):
        if message.role == "user":
            pending.clear()
        elif message.role == "assistant":
            pending.update(_declared_calls(message))
        elif message.role == "tool":
            name = pending.pop(str(message.tool_call_id or ""), None)
            definition = catalog.get(name)
            if name == message.name and definition is not None:
                yield index, definition


def _preview(
    content: Mapping[str, Any], collection: str, rows: list, *,
    original_count: int, fields_omitted: bool,
) -> dict[str, Any]:
    data = content["data"]
    original_summary = data.get("query_summary")
    summary = dict(original_summary) if isinstance(original_summary, Mapping) else {}
    summary.update(context_count=len(rows), context_truncated=True)
    return {
        **content,
        "data": {**data, collection: rows, "query_summary": summary},
        "context_compaction": {
            "method": "read_collection_preview", "original_context_count": original_count,
            "omitted_rows": original_count - len(rows), "fields_omitted": fields_omitted,
            "source_tool_message_preserved": True,
        },
    }


def _preview_message(
    source: _PreviewSource, rows: list, *, fields_omitted: bool,
) -> AgentMessage:
    message = source.message
    value = _preview(source.content, source.collection, rows,
                     original_count=source.original_count, fields_omitted=fields_omitted)
    if isinstance(message.content, str):
        value = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return replace(message, content=value, metadata={
        **message.metadata,
        "read_compaction": {
            "original_count": source.original_count, "fields_omitted": fields_omitted,
        },
    })


def _fit_rows(
    source: _PreviewSource, rows: list, *, fields_omitted: bool, limit: int,
    message_size: Callable[[AgentMessage], int],
) -> AgentMessage | None:
    low, high, best = 1, len(rows), None
    while low <= high:
        count = (low + high) // 2
        candidate = _preview_message(
            source, rows[:count], fields_omitted=fields_omitted,
        )
        if message_size(candidate) <= limit:
            best, low = candidate, count + 1
        else:
            high = count - 1
    return best


def _identity_rows(rows: list, definition: Any) -> list[dict[str, Any]]:
    ids = _field(definition, "result_id_fields", ()) or ()
    fields = (*ids, *(_field(definition, "result_summary_fields", ()) or ()))
    if not ids or any(not isinstance(row, Mapping) for row in rows):
        return []
    if any(not any(row.get(key) not in (None, "") for key in ids) for row in rows):
        return []
    return [{key: row[key] for key in fields if key in row} for row in rows]


def _shrink_read(
    message: AgentMessage, definition: Any, limit: int,
    message_size: Callable[[AgentMessage], int],
) -> AgentMessage:
    collection_data = _read_collection(message, definition)
    if collection_data is None:
        return message
    content, collection, rows = collection_data
    previous = message.metadata.get("read_compaction") or {}
    original_count = previous.get("original_count", len(rows))
    fields_omitted = bool(previous.get("fields_omitted"))
    source = _PreviewSource(message, content, collection, original_count)
    result = _fit_rows(
        source, rows,
        fields_omitted=fields_omitted, limit=limit, message_size=message_size,
    )
    if result is None:
        identities = _identity_rows(rows, definition)
        result = _fit_rows(
            source, identities, fields_omitted=True,
            limit=limit, message_size=message_size,
        )
        if result is None:
            # The remaining deficit can be shared with later read messages.
            # Keep at least one exact row/identity even when its envelope is
            # larger than this message's target share.
            result = _preview_message(
                source, (identities or rows)[:1], fields_omitted=bool(identities) or fields_omitted,
            )
    return result or message


def compact_read_messages(
    messages: Sequence[AgentMessage], definitions: Sequence[Any], *, max_chars: int,
    message_size: Callable[[AgentMessage], int],
) -> list[AgentMessage]:
    """Prefer latest evidence; preserve every call pair and non-read outcome.

    Only registered read collections with a successful completed call can be
    projected. Policy, user requests, call arguments, writes, failures, unknown
    outcomes and interaction payloads remain exact. If the protected minimum
    cannot fit, the caller must retain its normal fail-closed admission check.
    """
    if type(max_chars) is not int or max_chars <= 0:
        raise ValueError("evidence budget must be a positive integer")
    result = list(messages)
    sizes = [message_size(message) for message in result]
    total = sum(sizes)
    for index, definition in _completed_reads(messages, definitions):
        if total <= max_chars:
            break
        limit = max(512, sizes[index] - (total - max_chars))
        if limit >= sizes[index]:
            continue
        candidate = _shrink_read(result[index], definition, limit, message_size)
        new_size = message_size(candidate)
        if new_size < sizes[index]:
            result[index] = candidate
            total -= sizes[index] - new_size
    return result if total <= max_chars else list(messages)
