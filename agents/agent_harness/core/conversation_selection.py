"""Resolve short user follow-ups against bounded prior Tool interactions."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from typing import Any

from agents.agent_harness.redaction import redact_for_persistence


def _tool_message_content(message: Any) -> Mapping[str, Any] | None:
    content = getattr(message, "content", None)
    if isinstance(content, str) and len(content) <= 32_000:
        try:
            content = json.loads(content)
        except ValueError:
            return None
    return content if isinstance(content, Mapping) else None


def _offered_choices(message: Any) -> list[str] | None:
    content = _tool_message_content(message)
    metadata = getattr(message, "metadata", {}) or {}
    metadata_needs_input = (
        isinstance(metadata, Mapping) and metadata.get("needs_input") is True
    )
    if content is None and not metadata_needs_input:
        return None
    if (
        content is not None
        and content.get("needs_input") is not True
        and not metadata_needs_input
    ):
        return None
    data = content.get("data") if content is not None else None
    choices = data.get("choices") if isinstance(data, Mapping) else None
    if not isinstance(choices, list):
        return []
    return [
        item.strip() for item in choices[:32]
        if isinstance(item, str) and item.strip()
    ]


def _matching_offer_index(
    choice: str,
    transcript: Sequence[Any],
    before_index: int,
) -> int | None:
    for index in range(min(before_index, len(transcript)) - 1, -1, -1):
        message = transcript[index]
        if getattr(message, "role", "") != "tool":
            continue
        choices = _offered_choices(message)
        if choices is None:
            continue
        return index if choice in choices else None
    return None


def _source_user_index(offer_index: int, transcript: Sequence[Any]) -> int | None:
    turn_id = str(getattr(transcript[offer_index], "turn_id", "") or "")
    if not turn_id:
        return None
    for index in range(offer_index - 1, -1, -1):
        message = transcript[index]
        if (
            getattr(message, "role", "") == "user"
            and str(getattr(message, "turn_id", "") or "") == turn_id
        ):
            return index
    return None


def _clarification_chain(
    choice: str,
    turn_id: str,
    transcript: Sequence[Any],
) -> tuple[int, str] | None:
    """Find the root user turn for a bounded chain of offered choices."""
    choice = str(choice or "").strip()
    if not choice or len(choice) > 256:
        return None
    messages = list(transcript)
    current_turn_index = next(
        (
            index for index in range(len(messages) - 1, -1, -1)
            if turn_id and getattr(messages[index], "turn_id", "") == turn_id
        ),
        len(messages),
    )
    candidate = choice
    before_index = current_turn_index
    first_offer = True
    for _depth in range(8):
        offer_index = _matching_offer_index(candidate, messages, before_index)
        if offer_index is None:
            return None
        source_index = _source_user_index(offer_index, messages)
        if source_index is None:
            return None
        if first_offer:
            latest_user_index = next(
                (
                    index for index in range(before_index - 1, -1, -1)
                    if getattr(messages[index], "role", "") == "user"
                ),
                None,
            )
            if latest_user_index != source_index:
                return None
            first_offer = False
        source = str(getattr(messages[source_index], "content", "") or "").strip()
        if not source or len(source) > 1200:
            return None
        if len(source) > 256:
            return source_index, source[:1200]
        previous_offer = _matching_offer_index(source, messages, source_index)
        if previous_offer is None:
            return source_index, source
        candidate = source
        before_index = source_index
    return None


def clarification_origin(
    choice: str,
    turn_id: str,
    transcript: Sequence[Any],
) -> str:
    """Recover the root request when a user selects a shown option."""
    result = _clarification_chain(choice, turn_id, transcript)
    return result[1] if result else ""


def clarification_context(
    choice: str,
    turn_id: str,
    transcript: Sequence[Any],
    *,
    max_messages: int = 12,
    max_chars: int = 3600,
) -> tuple[str, ...]:
    """Return bounded user context preceding the root of a choice chain."""
    if max_messages <= 0 or max_chars <= 0:
        return ()
    root = _clarification_chain(choice, turn_id, transcript)
    if root is None:
        return ()
    root_index, _origin = root
    prior = [
        str(getattr(message, "content", "") or "").strip()
        for message in transcript[:root_index]
        if getattr(message, "role", "") == "user"
        and str(getattr(message, "content", "") or "").strip()
    ][-max_messages:]
    selected: list[str] = []
    remaining = max_chars
    for value in reversed(prior):
        if remaining <= 0:
            break
        safe = str(redact_for_persistence(value)).strip()
        bounded = safe[-remaining:]
        if bounded:
            selected.append(bounded)
            remaining -= len(bounded)
    return tuple(reversed(selected))


def _pending_tool_record(message: Any) -> dict[str, Any] | None:
    metadata = getattr(message, "metadata", {}) or {}
    if not isinstance(metadata, Mapping) or not metadata.get("needs_input"):
        return None
    interaction = metadata.get("interaction")
    if interaction is not None and (
        not isinstance(interaction, Mapping)
        or not isinstance(interaction.get("payload"), Mapping)
    ):
        return None
    tool_name = str(getattr(message, "name", "") or "")
    if not tool_name:
        return None
    return {
        "turn_id": str(getattr(message, "turn_id", "") or ""),
        "tool_name": tool_name,
        "interaction": interaction,
    }


def pending_input_interaction(
    turn_id: str,
    transcript: Sequence[Any],
    *,
    choice: str = "",
    response: Mapping[str, Any] | None = None,
) -> Mapping[str, Any] | None:
    """Return only the most recent, explicitly paused Tool interaction."""
    pending: dict[str, Any] | None = None
    repeated_choices = 0
    for message in reversed(transcript):
        if turn_id and getattr(message, "turn_id", "") == turn_id:
            continue
        role = getattr(message, "role", "")
        if role == "user":
            metadata = getattr(message, "metadata", {}) or {}
            origin = metadata.get("interaction_origin") if isinstance(
                metadata, Mapping,
            ) else None
            if (
                pending is None and choice
                and (
                    str(getattr(message, "content", "") or "").strip() == choice
                    or (
                        isinstance(response, Mapping)
                        and isinstance(origin, Mapping)
                        and origin.get("turn_id") == response.get("turn_id")
                        and origin.get("tool_name") == response.get("tool_name")
                    )
                )
                and repeated_choices < 2
            ):
                repeated_choices += 1
                continue
            if pending and pending["turn_id"] == getattr(message, "turn_id", ""):
                source = str(getattr(message, "content", "") or "").strip()
                if source and len(source) <= 1200:
                    return {**pending, "source_input": source}
            return None
        if role != "tool":
            continue
        if pending:
            continue
        pending = _pending_tool_record(message)
        if pending is None:
            return None
    return None


def catalog_selection_input(
    choice: str,
    turn_id: str,
    transcript: Sequence[Any],
    tools: Sequence[Any],
) -> tuple[str, str]:
    """Resolve a selected row to the matching registered detail Tool."""
    choice = str(choice or "").strip()
    if not choice or len(choice) > 320:
        return "", ""
    normalized_choice = _normalize(choice)
    if len(normalized_choice) < 4:
        return "", ""
    definitions = {
        str(getattr(tool, "name", "") or ""): tool
        for tool in tools if getattr(tool, "name", None)
    }
    prior_lists = _recent_list_results(turn_id, transcript, definitions)
    matches = _matching_rows(normalized_choice, prior_lists)
    if len(matches) != 1:
        return "", ""
    list_definition, row, label = matches[0]
    target = _matching_detail_tool(list_definition, row, tools)
    if target is None:
        return "", ""
    aliases = getattr(target, "intent_aliases", ()) or ()
    prefix = next(
        (str(alias).strip() for alias in aliases if str(alias).strip()),
        f"get {getattr(target, 'resource_type', '')}",
    )
    identifiers = {
        field: row[field]
        for field in getattr(list_definition, "result_id_fields", ()) or ()
        if row.get(field) not in (None, "")
    }
    identity = json.dumps(identifiers, ensure_ascii=False)
    return f"{prefix} {label} {identity} {choice}", str(getattr(target, "name", "") or "")


def _normalize(value: str) -> str:
    return re.sub(r"[\W_]+", "", str(value or "").casefold())


def _recent_list_results(
    turn_id: str,
    transcript: Sequence[Any],
    definitions: Mapping[str, Any],
) -> list[tuple[Any, Mapping[str, Any]]]:
    results = []
    for message in reversed(transcript):
        if turn_id and getattr(message, "turn_id", "") == turn_id:
            continue
        role = getattr(message, "role", "")
        if role == "user":
            break
        metadata = getattr(message, "metadata", {}) or {}
        if role != "tool" or metadata.get("is_error"):
            continue
        definition = definitions.get(str(getattr(message, "name", "") or ""))
        if (
            definition is None
            or str(getattr(definition, "action", "")).lower() != "list"
        ):
            continue
        content = _tool_message_content(message)
        if content is None or content.get("success") is False:
            continue
        results.append((definition, content))
        if len(results) >= 8:
            break
    return results


def _matching_rows(
    normalized_choice: str,
    list_results: Sequence[tuple[Any, Mapping[str, Any]]],
) -> list[tuple[Any, Mapping[str, Any], str]]:
    matches = []
    for definition, content in list_results:
        data = content.get("data")
        items_key = str(getattr(definition, "result_items_key", "") or "")
        rows = data.get(items_key) if isinstance(data, Mapping) else None
        if not isinstance(rows, list):
            continue
        for row in rows[:100]:
            if not isinstance(row, Mapping):
                continue
            for key in ("name", "title", "label", "display_name"):
                label = str(row.get(key) or "").strip()
                normalized_label = _normalize(label)
                if len(normalized_label) >= 4 and (
                    normalized_label in normalized_choice
                    or normalized_choice in normalized_label
                ):
                    matches.append((definition, row, label))
                    break
    identities = {
        (
            str(getattr(definition, "namespace", "")),
            _result_identity(definition, row, label),
        ): (definition, row, label)
        for definition, row, label in matches
    }
    return list(identities.values())


def _result_identity(definition: Any, row: Mapping[str, Any], label: str) -> Any:
    fields = getattr(definition, "result_id_fields", ()) or ()
    identity = tuple(
        (field, str(row.get(field) or ""))
        for field in fields if row.get(field) not in (None, "")
    )
    return identity or (label,)


def _matching_detail_tool(
    list_definition: Any,
    row: Mapping[str, Any],
    tools: Sequence[Any],
) -> Any | None:
    namespace = str(getattr(list_definition, "namespace", "") or "").casefold()
    resource = str(getattr(list_definition, "resource_type", "") or "").casefold()
    result_ids = set(getattr(list_definition, "result_id_fields", ()) or ())
    targets = []
    for tool in tools:
        schema = getattr(tool, "input_schema", None)
        required = set(getattr(schema, "required", ()) or ())
        if (
            str(getattr(tool, "namespace", "") or "").casefold() == namespace
            and str(getattr(tool, "resource_type", "") or "").casefold() == resource
            and str(getattr(tool, "action", "") or "").lower()
            in {"get", "detail", "retrieve"}
            and required & result_ids & set(row)
            and bool(getattr(tool, "is_read_tool", False))
        ):
            targets.append(tool)
    return targets[0] if len(targets) == 1 else None
