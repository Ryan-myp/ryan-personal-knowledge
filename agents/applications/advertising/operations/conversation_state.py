"""Bounded, source-backed user notes for advisory conversation continuity."""

from __future__ import annotations

import re
from typing import Any, Mapping

from agents.agent_harness import AgentMessage
from agents.agent_harness.conversation_recall import relevant_user_requests
from agents.agent_harness.redaction import redact_for_persistence


_MAX_ENTRIES = 8
_MAX_TEXT = 240
_EXPLICIT = re.compile(
    r"必须|始终|保持|不要|不允许|以后|记住|决定|"
    r"\b(?:must|always|never|remember|decided|keep)\b",
    re.IGNORECASE,
)
_QUESTION = re.compile(r"[?？]|是否|能不能|\b(?:whether|should I)\b", re.IGNORECASE)
_DECISION = re.compile(r"决定|\bdecided\b", re.IGNORECASE)
_TURN_ID = re.compile(r"[A-Za-z0-9_.:-]{1,200}\Z")


def valid_conversation_state(value: Any) -> dict[str, list[dict[str, str]]]:
    """Validate persisted metadata; it is context, never execution authority."""
    raw = value.get("entries") if isinstance(value, Mapping) else None
    entries: list[dict[str, str]] = []
    if not isinstance(raw, list):
        return {"entries": entries}
    for item in raw[-_MAX_ENTRIES:]:
        if not isinstance(item, Mapping) or item.get("source_role") != "user":
            continue
        kind, text, turn = (
            item.get("kind"), item.get("text"), item.get("source_turn_id"),
        )
        if (
            kind not in {"constraint", "decision"}
            or not isinstance(text, str) or not 1 <= len(text) <= _MAX_TEXT
            or not isinstance(turn, str) or not _TURN_ID.fullmatch(turn)
        ):
            continue
        safe = str(redact_for_persistence(text))
        if safe != text:
            continue
        entries.append({
            "kind": kind, "text": safe, "source_turn_id": turn,
            "source_role": "user",
        })
    return {"entries": entries}


def update_conversation_state(
    state: Any, user_input: str, turn_id: str,
) -> dict[str, list[dict[str, str]]]:
    result = valid_conversation_state(state)
    text = " ".join(str(user_input or "").split())
    if (
        not _EXPLICIT.search(text) or _QUESTION.search(text)
        or not isinstance(turn_id, str) or not _TURN_ID.fullmatch(turn_id)
    ):
        return result
    text = text[:_MAX_TEXT]
    safe = str(redact_for_persistence(text))
    if safe != text:
        return result
    entry = {
        "kind": "decision" if _DECISION.search(text) else "constraint",
        "text": safe, "source_turn_id": turn_id, "source_role": "user",
    }
    result["entries"] = [
        item for item in result["entries"] if item["text"] != safe
    ][-_MAX_ENTRIES + 1:] + [entry]
    return result


def render_conversation_state(state: Any, current_input: str) -> str:
    """Return only topical user-sourced notes, without granting permissions."""
    entries = valid_conversation_state(state)["entries"]
    matched = relevant_user_requests(
        current_input,
        [AgentMessage.user(item["text"], turn_id=item["source_turn_id"])
         for item in entries],
        limit=4, max_chars=1200,
    )
    if not matched:
        return ""
    return "\n".join(
        f"- {item['kind']} [user turn {item['source_turn_id']}]: {item['text']}"
        for item in entries if item["text"] in matched
    )[:1600]
