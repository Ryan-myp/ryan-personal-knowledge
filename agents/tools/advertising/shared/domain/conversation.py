"""Human conversation views over durable model and Tool protocol messages."""

from __future__ import annotations

import json
from typing import Any, Mapping, Sequence


_FAILED_STATUSES = {"failed", "partially_failed", "recovery_required", "unknown", "cancelled"}
_MODEL_ERRORS = {
    "RateLimitError": "模型服务暂时限流，本次请求未完成。这不代表广告账户没有数据。",
    "model_timeout": "模型响应超时，本次请求未完成。这不代表广告账户没有数据。",
    "model_not_configured": "模型服务未配置，本次请求无法执行。",
    "model_token_budget_exceeded": "本次请求超出模型上下文或输出预算，执行未完成。",
}


def _tool_payload(item: Mapping[str, Any]) -> Mapping[str, Any]:
    value = item.get("content", item)
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, ValueError):
            return {}
    return value if isinstance(value, Mapping) else {}


def visible_run_reply(result: Mapping[str, Any]) -> str:
    """Use the same truthful text for the live response and its durable replay."""
    reply = str(result.get("reply") or "")
    if reply.strip():
        return reply
    records = result.get("results") or result.get("tool_results") or ()
    records = records if isinstance(records, (list, tuple)) else ()
    error = str(result.get("error") or "")
    if error:
        text = _MODEL_ERRORS.get(error, "本次请求执行失败，请查看执行记录。")
        if records:
            text += "已有工具执行记录；创建或更新操作不要直接重试，请先核实实际结果。"
        return text
    confirmation = result.get("confirmation_payload")
    if isinstance(confirmation, Mapping) and confirmation.get("question"):
        return str(confirmation["question"])
    for item in reversed(records):
        if not isinstance(item, Mapping):
            continue
        payload = _tool_payload(item)
        interaction = item.get("interaction") or payload.get("interaction")
        if isinstance(interaction, Mapping) and interaction.get("prompt"):
            return str(interaction["prompt"])
        confirmation = item.get("confirmation_payload") or payload.get("confirmation_payload")
        if isinstance(confirmation, Mapping) and confirmation.get("question"):
            return str(confirmation["question"])
        if item.get("needs_confirmation") or payload.get("needs_confirmation"):
            return "请确认本回合的执行计划；尚未提交真实写入。"
        if item.get("needs_input") or payload.get("needs_input"):
            return "本回合还需要补充参数，请根据创建草稿或执行记录继续。"
        if not (item.get("is_error") or payload.get("success") is False):
            continue
        reason = str(payload.get("error") or item.get("error") or item.get("content") or "")
        if "allow_live_writes is disabled" in reason:
            reason = "当时未开启真实写入，服务端已拦截该次操作。"
        if reason.strip():
            return "本次执行未完成：" + reason
    ui = result.get("ui")
    if isinstance(ui, Mapping) and ui.get("cards"):
        return "已恢复创建草稿，请确认参数；尚未创建广告。"
    status = str(result.get("status") or "")
    if status in {"recovery_required", "unknown"}:
        return "本次执行状态尚未确认，请先核实实际结果，不要直接重复创建或更新。"
    if status == "cancelled":
        return "本次执行已取消；已发生的外部操作不会自动回滚，请核实实际状态。"
    if status in {"failed", "partially_failed"}:
        return "本次执行未完成，请查看执行轨迹中的失败步骤。"
    if records:
        return "本回合已有工具执行记录，但没有最终文字说明。请先核实实际结果，不要直接重复创建或更新。"
    return ""


def _metadata(record: Mapping[str, Any]) -> Mapping[str, Any]:
    value = record.get("metadata")
    return value if isinstance(value, Mapping) else {}


def _history_tool(record: Mapping[str, Any]) -> dict[str, Any]:
    metadata = _metadata(record)
    return {
        "content": record.get("content", ""),
        "is_error": bool(metadata.get("is_error")),
        **{
            key: metadata[key] for key in (
                "needs_input", "needs_confirmation", "confirmation_payload",
            ) if key in metadata
        },
    }


def _tool_badges(records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    badges: dict[str, dict[str, Any]] = {}
    for record in records:
        item = _history_tool(record)
        payload = _tool_payload(item)
        if any(item.get(key) or payload.get(key) for key in ("needs_input", "needs_confirmation")):
            continue
        name = str(record.get("name") or "")
        if name:
            badges[name] = {
                "tool": name,
                "success": not item["is_error"] and payload.get("success") is not False,
            }
    return list(badges.values())


def _visible_turn(
    records: Sequence[Mapping[str, Any]], stored_ui: Any,
) -> list[dict[str, Any]]:
    visible = [
        {key: record.get(key) for key in ("role", "content", "created_at", "turn_id")}
        for record in records if record.get("role") == "user"
    ]
    assistants = [row for row in records if row.get("role") == "assistant"]
    tools = [row for row in records if row.get("role") == "tool"]
    presented = [row for row in assistants if str(_metadata(row).get("display_reply") or "").strip()]
    native = [
        row for row in assistants
        if not _metadata(row).get("tool_calls") and str(row.get("content") or "").strip()
    ]
    candidate = (presented or native or assistants or tools or [{}])[-1]
    metadata = _metadata(candidate)
    reply = str(metadata.get("display_reply") or (candidate.get("content") if native and not presented else "") or "")
    ui = next((
        _metadata(row)["ui"] for row in reversed(assistants)
        if isinstance(_metadata(row).get("ui"), Mapping) and _metadata(row)["ui"]
    ), stored_ui)
    ui = ui if isinstance(ui, Mapping) else {}
    tool_results = [_history_tool(row) for row in tools]
    if not reply.strip():
        reply = visible_run_reply({"tool_results": tool_results, "ui": ui})
    if not reply.strip() and not ui:
        return visible
    status = str(metadata.get("display_status") or "")
    waiting = bool(tool_results) and any(
        tool_results[-1].get(key) or _tool_payload(tool_results[-1]).get(key)
        for key in ("needs_input", "needs_confirmation")
    )
    is_error = (
        status in _FAILED_STATUSES if status
        else bool(tool_results and tool_results[-1].get("is_error")) and not waiting
    )
    visible.append({
        "role": "assistant", "content": reply,
        "turn_id": candidate.get("turn_id"), "created_at": candidate.get("created_at"),
        "is_error": is_error,
        **({"ui": dict(ui)} if ui else {}),
        **({"tools": badges} if (badges := _tool_badges(tools)) else {}),
    })
    return visible


def project_conversation_messages(
    records: Sequence[Mapping[str, Any]],
    ui_by_turn: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Keep protocol evidence intact while returning one human reply per turn."""
    groups: dict[str, list[Mapping[str, Any]]] = {}
    for index, record in enumerate(records):
        key = str(record.get("turn_id") or f"message-{index}")
        groups.setdefault(key, []).append(record)
    ui_by_turn = ui_by_turn if isinstance(ui_by_turn, Mapping) else {}
    return [
        message
        for turn_id, rows in groups.items()
        for message in _visible_turn(rows, ui_by_turn.get(turn_id))
    ]
