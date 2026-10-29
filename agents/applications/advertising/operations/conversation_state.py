"""Bounded, source-backed user notes for advisory conversation continuity."""

from __future__ import annotations

import re
from typing import Any, Mapping

from agents.agent_harness import AgentMessage
from agents.agent_harness.conversation_recall import (
    relevant_user_requests, is_contextual_followup, has_recall_terms,
)
from agents.agent_harness.redaction import redact_for_persistence
from .semantic_constraints import (
    valid_semantic_notes, render_semantic_notes, note_id,
)


_MAX_ENTRIES = 8
_MAX_TEXT = 240
_EXPLICIT = re.compile(
    r"必须|始终|保持|不要|不允许|以后|记住|决定|改为|改成|调整为|"
    r"\b(?:must|always|never|remember|decided|keep)\b",
    re.IGNORECASE,
)
_QUESTION = re.compile(r"[?？]|是否|能不能|\b(?:whether|should I)\b", re.IGNORECASE)
_DECISION = re.compile(r"决定|\bdecided\b", re.IGNORECASE)
_REVISION = re.compile(r"改为|改成|调整为")
_RETRACTION = re.compile(r"^\s*(?:取消|撤销)|不再")
_SUBJECT_PREFIX = re.compile(r"^(?:(?:将|把|取消|撤销|不再|之前|此前|先前|原来)\s*)+")
_SUBJECT_END = re.compile(r"必须|保持|改为|改成|调整为|约束|不再")
_TURN_ID = re.compile(r"[A-Za-z0-9_.:-]{1,200}\Z")
_FOLLOWUP_WORDS = frozenset({"继续", "之前", "刚才", "上面", "这个", "那个", "接着"})


def _statement_key(text: str) -> str:
    subject = _SUBJECT_PREFIX.sub("", text).strip()
    subject = _SUBJECT_END.split(subject, maxsplit=1)[0]
    return re.sub(r"[\s的:：,，。]+", "", subject).casefold()[:160]


def _topic_bigrams(text: str) -> set[str]:
    return {
        group[index:index + 2]
        for group in re.findall(r"[\u3400-\u9fff]+", text)
        for index in range(len(group) - 1)
        if group[index:index + 2] not in _FOLLOWUP_WORDS
    }


def valid_conversation_state(value: Any) -> dict[str, list[dict[str, str]]]:
    """Validate persisted metadata; it is context, never execution authority."""
    raw = value.get("entries") if isinstance(value, Mapping) else None
    entries: list[dict[str, str]] = []
    if not isinstance(raw, list):
        raw = []
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
    result = {"entries": entries}
    if isinstance(value, Mapping) and "semantic" in value:
        result["semantic"] = valid_semantic_notes(value["semantic"])
    return result


def update_conversation_state(
    state: Any, user_input: str, turn_id: str,
) -> dict[str, list[dict[str, str]]]:
    result = valid_conversation_state(state)
    history = result.get("semantic", {}).get("history", [])
    if any(row.get("source_turn_id") == turn_id for row in history):
        return result
    text = " ".join(str(user_input or "").split())
    if (
        _QUESTION.search(text)
        or not isinstance(turn_id, str) or not _TURN_ID.fullmatch(turn_id)
    ):
        return result
    text = text[:_MAX_TEXT]
    safe = str(redact_for_persistence(text))
    if safe != text:
        return result
    key = _statement_key(safe)
    if _RETRACTION.search(safe):
        if key:
            result["entries"] = [
                item for item in result["entries"]
                if _statement_key(item["text"]) != key
            ]
        return result
    if not _EXPLICIT.search(safe) or (_REVISION.search(safe) and not key):
        return result
    entry = {
        "kind": "decision" if _DECISION.search(text) else "constraint",
        "text": safe, "source_turn_id": turn_id, "source_role": "user",
    }
    result["entries"] = [
        item for item in result["entries"]
        if item["text"] != safe
        and not (
            _REVISION.search(safe) and key
            and _statement_key(item["text"]) == key
        )
    ][-_MAX_ENTRIES + 1:] + [entry]
    return result


def render_conversation_state(state: Any, current_input: str) -> str:
    """Return only topical user-sourced notes, without granting permissions."""
    entries = valid_conversation_state(state)["entries"]
    query_terms = _topic_bigrams(current_input)
    candidates = [
        item for item in entries
        if not query_terms or not _topic_bigrams(item["text"])
        or query_terms & _topic_bigrams(item["text"])
    ]
    matched = relevant_user_requests(
        current_input,
        [AgentMessage.user(item["text"], turn_id=item["source_turn_id"])
         for item in candidates],
        limit=4, max_chars=1200,
    )
    if is_contextual_followup(current_input) and not has_recall_terms(current_input):
        matched = tuple(item["text"] for item in candidates[-4:])
    legacy = [
        f"- {item['kind']} [id={note_id(item)}; user turn {item['source_turn_id']}]: {item['text']}"
        for item in reversed(candidates) if item["text"] in matched
    ]
    return render_semantic_notes(
        state.get("semantic") if isinstance(state, Mapping) else None, legacy_lines=legacy,
    )
