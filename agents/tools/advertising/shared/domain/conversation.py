"""Human conversation views over durable model and Tool protocol messages."""

from __future__ import annotations

import json
import re
from typing import Any, Mapping, Sequence


_FAILED_STATUSES = {"failed", "partially_failed", "recovery_required", "unknown", "cancelled"}
_MODEL_ERRORS = {
    "RateLimitError": "模型服务暂时限流，本次请求未完成。这不代表广告账户没有数据。",
    "model_timeout": "模型响应超时，本次请求未完成。这不代表广告账户没有数据。",
    "model_not_configured": "模型服务未配置，本次请求无法执行。",
    "model_token_budget_exceeded": "本次请求超出模型上下文或输出预算，执行未完成。",
}
_READ_ACTIONS = frozenset({"get", "list", "read", "search", "query", "fetch", "retrieve"})
_SENSITIVE_RESULT_FIELD = re.compile(
    r"token|secret|credential|password|private|signature|selection", re.I,
)
_RESULT_METADATA_FIELDS = frozenset({
    "data_status", "parameter_selections", "query_summary", "warnings",
})


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
    records = result.get("results") or result.get("tool_results") or ()
    records = records if isinstance(records, (list, tuple)) else ()
    error = str(result.get("error") or "")
    if error:
        generic_error_reply = _MODEL_ERRORS.get(error)
        if (
            generic_error_reply
            and (not reply.strip() or reply.strip().startswith(generic_error_reply))
        ):
            read_fallback = _successful_read_fallback(records)
            if read_fallback:
                return read_fallback
        if reply.strip():
            return reply
        text = _MODEL_ERRORS.get(error, "本次请求执行失败，请查看执行记录。")
        if records and _contains_write_record(records):
            text += "已有工具执行记录；创建或更新操作不要直接重试，请先核实实际结果。"
        elif records:
            text += "已有查询执行记录，请查看执行轨迹核实结果。"
        return text
    if reply.strip():
        return reply
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


def _contains_write_record(records: Sequence[Any]) -> bool:
    for item in records:
        if not isinstance(item, Mapping):
            return True
        if str(item.get("action") or "").strip().lower() not in _READ_ACTIONS:
            return True
    return False


def _successful_read_fallback(records: Sequence[Any]) -> str:
    reads = []
    failed_reads = 0
    for item in records:
        if not isinstance(item, Mapping):
            return ""
        action = str(item.get("action") or "").strip().lower()
        if action not in _READ_ACTIONS:
            return ""
        if item.get("is_error") or item.get("success") is False:
            failed_reads += 1
            continue
        if item.get("success") is not True:
            return ""
        data = item.get("data")
        if isinstance(data, Mapping):
            reads.append((item, data))
    if not reads:
        return ""

    summaries = []
    for item, data in reads:
        resource = str(item.get("resource_type") or "查询结果")
        data_status = str(data.get("data_status") or "")
        source = "真实渠道 API" if data_status == "live" else "查询工具"
        summary = _format_read_data(resource, data)
        if summary:
            summaries.append(f"**{resource}**（{source}）\n\n{summary}")
    if not summaries:
        return ""
    if failed_reads:
        opening = (
            f"部分查询已成功，另有 {failed_reads} 项查询失败。"
            "模型摘要服务暂时不可用，以下仅列出成功结果：\n\n"
        )
    else:
        opening = (
            "查询已成功。模型摘要服务暂时不可用，"
            "以下内容直接来自本次工具结果：\n\n"
        )
    return (
        opening + "\n\n".join(summaries)
    )


def _format_read_data(resource: str, data: Mapping[str, Any]) -> str:
    rows = _read_rows(resource, data)
    if not rows:
        collections = [
            value for key, value in data.items()
            if key not in _RESULT_METADATA_FIELDS and isinstance(value, list)
        ]
        if collections:
            count = sum(
                isinstance(row, Mapping)
                for collection in collections
                for row in collection
            )
            return f"共 {count} 条。"
        return "查询已返回数据。"

    columns = _read_columns(rows[0])
    if not columns:
        return "查询已返回数据。"
    if len(rows) == 1:
        cells = [
            f"| {_escape_cell(_field_label(key))} | {_escape_cell(rows[0][key])} |"
            for key in columns
        ]
        return "| 字段 | 值 |\n| --- | --- |\n" + "\n".join(cells)

    headers = [_field_label(key) for key in columns]
    lines = [
        "| " + " | ".join(_escape_cell(value) for value in headers) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    lines.extend(
        "| " + " | ".join(_escape_cell(row.get(key, "")) for key in columns) + " |"
        for row in rows[:10]
    )
    if len(rows) > 10:
        lines.append(f"\n仅展示前 10 条，共 {len(rows)} 条。")
    else:
        lines.append(f"\n共 {len(rows)} 条。")
    return "\n".join(lines)


def _read_rows(resource: str, data: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    candidates = [
        [row for row in value if isinstance(row, Mapping)]
        for key, value in data.items()
        if key not in _RESULT_METADATA_FIELDS
        and isinstance(value, list)
        and value
        and all(isinstance(row, Mapping) for row in value)
    ]
    if candidates:
        return max(candidates, key=len)

    nested = [
        value for value in data.values()
        if isinstance(value, Mapping)
        and any(key == "id" or key.endswith("_id") for key in value)
    ]
    if nested:
        return [nested[0]]
    if any(key == "id" or key.endswith("_id") for key in data):
        return [data]
    return []


def _read_columns(row: Mapping[str, Any]) -> list[str]:
    scalar_fields = [
        str(key) for key, value in row.items()
        if not _SENSITIVE_RESULT_FIELD.search(str(key))
        and not isinstance(value, (Mapping, list, tuple, set))
        and value is not None
    ]
    preferred = ("id", "name", "status", "operation_status")
    selected = [key for key in preferred if key in scalar_fields]
    selected.extend(
        key for key in scalar_fields
        if key not in selected and key.endswith("_id")
    )
    selected.extend(key for key in scalar_fields if key not in selected)
    return selected[:6]


def _field_label(value: str) -> str:
    labels = {
        "id": "ID",
        "name": "名称",
        "status": "状态",
        "operation_status": "操作状态",
    }
    return labels.get(value, value.replace("_", " "))


def _escape_cell(value: Any) -> str:
    text = ("" if value is None else str(value)).replace("\r", " ").replace("\n", " ")
    return (
        text[:180]
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("|", "\\|")
    )


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
