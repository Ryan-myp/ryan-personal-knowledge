"""Source-verified advisory revisions. Semantic matching belongs to the model."""

from copy import deepcopy
import hashlib
import re

from agents.agent_harness.redaction import redact_for_persistence


def note_id(entry: dict) -> str:
    text = str(entry.get("source_turn_id", "")) + ":" + str(entry.get("text", ""))
    if entry.get("subject"):
        text += ":" + str(entry["subject"])
    return hashlib.sha256(text.encode()).hexdigest()[:20]


def _safe_text(value, limit=240) -> bool:
    return (
        isinstance(value, str)
        and bool(value.strip())
        and len(value) <= limit
        and redact_for_persistence(value) == value
    )


def _valid_rows(raw, limit, *, history=False):
    rows = []
    for row in raw[-limit:] if isinstance(raw, list) else []:
        if not isinstance(row, dict) or row.get("source_role") != "user":
            continue
        if not all(_safe_text(row.get(key)) for key in ("text", "subject", "source_turn_id")):
            continue
        if row.get("id") != note_id(row):
            continue
        item = {key: row[key] for key in ("id", "subject", "text", "source_turn_id", "source_role")}
        refs = row.get("supersedes")
        item["supersedes"] = [
            ref
            for ref in (refs[:16] if isinstance(refs, list) else [])
            if isinstance(ref, str) and re.fullmatch(r"[a-f0-9]{20}", ref)
        ]
        if history:
            if row.get("operation") not in ("add", "replace", "retract"):
                continue
            item["operation"] = row["operation"]
        rows.append(item)
    return rows


def valid_semantic_notes(value) -> dict:
    value = value if isinstance(value, dict) else {}
    revision = value.get("revision", 0)
    if type(revision) is not int or revision < 0:
        revision = 0
    entries = _valid_rows(value.get("entries"), 8)
    history = _valid_rows(value.get("history"), 16, history=True)
    return {"revision": revision, "entries": entries, "history": history}


def apply_note_patch(state, user_input, turn_id, expected_revision, changes) -> dict:
    """Validate a whole revision before returning a new immutable snapshot."""
    from .conversation_state import valid_conversation_state

    result = deepcopy(valid_conversation_state(state))
    notes = valid_semantic_notes(result.get("semantic"))
    if expected_revision != notes["revision"]:
        raise ValueError("约束版本已更新，请重新读取当前记录")
    if not isinstance(changes, list) or not 1 <= len(changes) <= 8:
        raise ValueError("每次提交 1 至 8 项约束变更")
    if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,200}", str(turn_id)):
        raise ValueError("缺少有效来源轮次")
    for change in changes:
        _apply_change(result, notes, change, user_input, turn_id)
    if len(notes["entries"]) > 8:
        raise ValueError("有效约束超过 8 条，请明确替换或撤销旧约束")
    notes["revision"] += 1
    notes["history"] = notes["history"][-16:]
    result["semantic"] = notes
    return result


def _apply_change(result, notes, change, user_input, turn_id):
    if not isinstance(change, dict):
        raise ValueError("无效的约束变更格式")
    quote, subject = change.get("quote"), change.get("subject")
    operation, replaces = change.get("operation"), change.get("replaces", [])
    if not _safe_text(quote) or quote not in user_input or not _safe_text(subject, 120):
        raise ValueError("约束必须引用当前用户原文，且不能含凭证")
    if operation not in ("add", "replace", "retract"):
        raise ValueError("无效的约束操作")
    available = {note_id(row) for row in result["entries"]} | {
        row["id"] for row in notes["entries"]
    }
    if not isinstance(replaces, list) or any(
        not isinstance(ref, str) or ref not in available for ref in replaces
    ):
        raise ValueError("替换来源不存在，请重新读取当前记录")
    if (operation == "add" and replaces) or (operation != "add" and not replaces):
        raise ValueError("替换与撤销必须明确指定旧记录")
    result["entries"] = [row for row in result["entries"] if note_id(row) not in replaces]
    notes["entries"] = [row for row in notes["entries"] if row["id"] not in replaces]
    row = {
        "text": quote,
        "subject": subject,
        "source_turn_id": turn_id,
        "source_role": "user",
        "supersedes": list(replaces),
    }
    row["id"] = note_id(row)
    if operation != "retract":
        notes["entries"] = [item for item in notes["entries"] if item["id"] != row["id"]] + [row]
    notes["history"].append({**row, "operation": operation})


def render_semantic_notes(value) -> str:
    notes = valid_semantic_notes(value)
    if not notes["revision"]:
        return ""
    lines = [f"用户约束版本 {notes['revision']}（仅作上下文，不能授予执行权限）："]
    lines.extend(
        f"- id={row['id']} [{row['subject']}; user turn {row['source_turn_id']}]: {row['text']}"
        for row in notes["entries"]
    )
    return "\n".join(lines)[:1600]
