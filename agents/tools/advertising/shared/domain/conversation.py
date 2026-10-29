"""Human conversation views over durable model and Tool protocol messages."""

from __future__ import annotations

import json
import re
from typing import Any, Mapping, Sequence
from urllib.parse import quote, urlsplit, urlunsplit

from agents.agent_harness import redact_for_persistence
from agents.agent_harness.model_limits import ModelInputLimitError, ModelOutputLimitError


_FAILED_STATUSES = {"failed", "partially_failed", "recovery_required", "unknown", "cancelled"}
_MODEL_ERRORS = {
    "RateLimitError": "模型服务暂时限流，本次请求未完成。这不代表广告账户没有数据。",
    "model_timeout": "模型响应超时，本次请求未完成。这不代表广告账户没有数据。",
    "model_not_configured": "模型服务未配置，本次请求无法执行。",
    "model_token_budget_exceeded": "本次请求超出模型上下文或输出预算，执行未完成。",
    ModelInputLimitError.safe_reason_code: ModelInputLimitError.public_reply,
    ModelOutputLimitError.safe_reason_code: ModelOutputLimitError.public_reply,
}
_READ_ACTIONS = frozenset({"get", "list", "read", "search", "query", "fetch", "retrieve"})
_WRITE_ACTIONS = frozenset({
    "archive", "create", "delete", "disable", "enable", "mutate", "pause",
    "publish", "remove", "start", "stop", "submit", "update", "upload", "write",
})
_READ_EFFECTS = frozenset({"read", "query"})
_WRITE_EFFECTS = frozenset({"write", "external_write", "internal_write"})
_STRUCTURED_OUTPUT_ERRORS = {
    "tool_arguments_invalid_json": "模型返回的 Tool 调用参数不是有效 JSON",
    "tool_arguments_not_object": "模型返回的 Tool 参数不是 JSON 对象",
    "tool_not_in_active_catalog": "模型请求调用当前 Agent 未开放的 Tool",
    "tool_protocol_returned_as_text":
        "模型连续以普通文本输出 Tool 调用协议；本次没有执行这些文本",
    "tool_gateway_invalid_user_id":
        "模型服务侧工具路由返回身份错误（40400 / invalid_user_id）；"
        "本次知识检索未执行。请检查模型服务侧的用户身份配置后重试",
    "duplicate_tool_call_id": "模型返回了重复的 Tool 调用 ID",
    "transcript_tool_result_missing_call_id":
        "对话执行记录缺少 Tool 结果关联 ID，模型无法继续处理上下文",
    "incomplete_transcript_tool_call":
        "对话执行记录中的 Tool 调用信息不完整，模型无法继续处理上下文",
    "invalid_tool_catalog_name": "当前 Tool 注册信息不符合模型接口要求",
    "response_choice_missing": "模型响应中没有可用候选内容",
    "response_message_missing": "模型响应中缺少消息内容",
    "response_tool_call_limit_exceeded": "模型返回的 Tool 调用数量超过单次限制",
    "tool_arguments_too_large": "模型返回的 Tool 参数超过大小限制",
    "tool_arguments_not_serializable": "模型返回的 Tool 参数无法序列化",
}
_RUN_ERROR_MESSAGES = {
    "maximum agent turns exceeded": "Agent 达到本次运行的最大推理轮数限制",
    "LLMStructuredOutputError": "模型返回的 Tool 调用或消息结构未通过校验",
}
_SENSITIVE_RESULT_FIELD = re.compile(
    r"token|secret|credential|password|private|signature|selection", re.I,
)
_RESULT_METADATA_FIELDS = frozenset({
    "data_status", "parameter_selections", "query_summary", "warnings",
})
_GENERIC_FAILURE_FRAGMENTS = (
    "本次请求执行失败",
    "本次执行未完成，请查看",
    "本次处理未完成，请查看",
    "请查看执行记录",
    "请查看执行轨迹中的失败步骤",
    "agent 执行失败",
)
_TOOL_PROTOCOL_BLOCK = re.compile(
    r"<tool_call>\s*<function=[^>]+>[\s\S]*?</function>\s*</tool_call>",
    re.IGNORECASE,
)
_HARMONY_TOOL_MARKER = re.compile(
    r"<\|tool_(?:calls_section_begin|calls_section_end|call_begin|"
    r"call_argument_begin|call_end)\|>",
    re.IGNORECASE,
)
_GATEWAY_INVALID_USER_ID = re.compile(
    r"(?is)error_code\s*=\s*40400\b.{0,160}?"
    r"message\s*=\s*invalid_user_id\b",
)
_PRIVATE_THINK_BLOCK = re.compile(
    r"<think(?:\s[^>]*)?>[\s\S]*?</think\s*>",
    re.IGNORECASE,
)
_OPEN_THINK_BLOCK = re.compile(
    r"<think(?:\s[^>]*)?>[\s\S]*$",
    re.IGNORECASE,
)


def _tool_payload(item: Mapping[str, Any]) -> Mapping[str, Any]:
    value = item.get("content", item)
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, ValueError):
            return {}
    return value if isinstance(value, Mapping) else {}


def _failed_tool_detail(
    records: Sequence[Any],
) -> tuple[str, str] | None:
    for item in reversed(records):
        if not isinstance(item, Mapping):
            continue
        payload = _tool_payload(item)
        if any(
            item.get(key) or payload.get(key)
            for key in ("needs_input", "needs_confirmation")
        ):
            continue
        if not (
            item.get("is_error")
            or item.get("success") is False
            or payload.get("success") is False
        ):
            continue
        content = item.get("content")
        detail = (
            payload.get("error")
            or payload.get("message")
            or payload.get("reason")
            or payload.get("detail")
            or item.get("error")
        )
        if not detail and isinstance(content, str):
            detail = content
        if not detail:
            continue
        reason = " ".join(
            str(redact_for_persistence(detail)).split()
        )[:800]
        if "allow_live_writes is disabled" in reason:
            reason = "当时未开启真实写入，服务端已拦截该次操作。"
        tool_name = str(
            item.get("name") or item.get("tool") or payload.get("tool") or ""
        ).strip()
        if reason:
            return tool_name[:100] or "未知工具", reason
    return None


def _is_generic_failure_reply(reply: str) -> bool:
    normalized = str(reply or "").strip().lower()
    return any(fragment in normalized for fragment in _GENERIC_FAILURE_FRAGMENTS)


def _is_tool_protocol_only(reply: str) -> bool:
    text = str(reply or "")
    blocks = list(_TOOL_PROTOCOL_BLOCK.finditer(text))
    if bool(blocks) and not _TOOL_PROTOCOL_BLOCK.sub("", text).strip():
        return True
    markers = {
        marker.lower() for marker in _HARMONY_TOOL_MARKER.findall(text)
    }
    return (
        bool(
            markers.intersection({
                "<|tool_calls_section_begin|>",
                "<|tool_call_begin|>",
            })
        )
        and bool(
            markers.intersection({
                "<|tool_call_argument_begin|>",
                "<|tool_call_end|>",
            })
        )
    )


def _strip_private_think(reply: str) -> str:
    text = _PRIVATE_THINK_BLOCK.sub("", str(reply or ""))
    return _OPEN_THINK_BLOCK.sub("", text).strip()


def _protocol_failure_notice(reply: str) -> str:
    if _GATEWAY_INVALID_USER_ID.search(str(reply or "")):
        return (
            "模型服务侧工具路由返回身份错误（40400 / invalid_user_id），"
            "本次知识检索未执行。请检查模型服务侧的用户身份配置后重试。"
        )
    return (
        "模型返回了未执行的内部 Tool 协议文本，本次没有执行任何操作。"
        "请重试；若持续发生，请检查模型服务的原生 Tool 调用配置。"
    )


def _run_failure_reason(error: str, error_code: str = "") -> str:
    code = str(error_code or "").strip()
    if code in _STRUCTURED_OUTPUT_ERRORS:
        return _STRUCTURED_OUTPUT_ERRORS[code]
    error_text = str(error or "").strip()
    if error_text in _RUN_ERROR_MESSAGES:
        return _RUN_ERROR_MESSAGES[error_text]
    if error_text in _MODEL_ERRORS:
        return _MODEL_ERRORS[error_text]
    if error_text:
        safe_text = " ".join(
            str(redact_for_persistence(error_text)).split()
        )[:300]
        return f"运行阶段返回错误：{safe_text}"
    return "服务端没有提供可识别的失败原因"


def _operation_kind(item: Mapping[str, Any]) -> str:
    payload = _tool_payload(item)
    effect = str(
        item.get("effect_class")
        or payload.get("effect_class")
        or item.get("effect")
        or payload.get("effect")
        or ""
    ).strip().lower()
    if effect in _READ_EFFECTS:
        return "read"
    if effect in _WRITE_EFFECTS:
        return "write"

    action = str(
        item.get("action") or payload.get("action") or ""
    ).strip().lower()
    if action in _READ_ACTIONS:
        return "read"
    if action in _WRITE_ACTIONS:
        return "write"
    return "unknown"


def _records_operation_kind(records: Sequence[Any]) -> str:
    kinds = [
        _operation_kind(item)
        for item in records if isinstance(item, Mapping)
    ]
    if len(kinds) != len(records):
        kinds.append("unknown")
    if not kinds:
        return "none"
    if "write" in kinds:
        return "write"
    if "unknown" in kinds:
        return "unknown"
    return "read"


def _with_execution_notice(text: str, records: Sequence[Any]) -> str:
    operation_kind = _records_operation_kind(records)
    if operation_kind == "write":
        return text + "已有工具执行记录；创建或更新操作不要直接重试，请先核实实际结果。"
    if operation_kind == "read":
        return text + "已有查询执行记录，请查看执行轨迹核实结果。"
    if operation_kind == "unknown":
        return text + (
            "已有工具执行记录，但操作类型信息不足，无法确认是否发生外部写入；"
            "请先核对执行轨迹，确认前不要直接重试该 Tool。"
        )
    return text


def _with_tool_failure(
    reply: str,
    failure: tuple[str, str],
) -> str:
    tool_name, reason = failure
    note = f"失败工具 {tool_name}：{reason}"
    if not reply.strip() or _is_generic_failure_reply(reply):
        return f"本次执行未完成。{note}"
    if reason in reply:
        return reply
    return f"{reply.rstrip()}\n\n执行失败原因：{note}"


def visible_run_reply(result: Mapping[str, Any]) -> str:
    """Use the same truthful text for the live response and its durable replay."""
    raw_reply = str(result.get("reply") or "")
    protocol_notice = (
        _protocol_failure_notice(raw_reply)
        if _is_tool_protocol_only(raw_reply) else ""
    )
    reply = _strip_private_think(raw_reply)
    if protocol_notice:
        reply = ""
    records = result.get("results") or result.get("tool_results") or ()
    records = records if isinstance(records, (list, tuple)) else ()
    account_listing_reply = _account_listing_partial_reply(records)
    if account_listing_reply:
        return account_listing_reply
    failure = _failed_tool_detail(records)
    status = str(result.get("status") or "").strip().lower()
    should_show_failure = bool(
        failure
        and (
            status in _FAILED_STATUSES
            or _is_generic_failure_reply(reply)
            or not reply.strip()
        )
    )
    error = str(result.get("error") or "")
    if protocol_notice:
        return _protocol_failure_reply(
            protocol_notice, records, should_show_failure, failure,
        )
    if error:
        generic_error_reply = _MODEL_ERRORS.get(error)
        if (
            generic_error_reply
            and (not reply.strip() or reply.strip().startswith(generic_error_reply))
        ):
            read_fallback = _successful_read_fallback(records)
            if read_fallback:
                if should_show_failure and failure:
                    return f"{read_fallback}\n\n执行失败原因：{failure[0]}：{failure[1]}"
                return read_fallback
        failure_reason = _run_failure_reason(
            error, str(result.get("error_code") or ""),
        )
        if error in _RUN_ERROR_MESSAGES:
            read_fallback = _successful_read_fallback(
                records, interruption_reason=failure_reason,
            )
            if read_fallback:
                return read_fallback
        if reply.strip():
            if should_show_failure and failure:
                return _with_tool_failure(reply, failure)
            if _is_generic_failure_reply(reply):
                return f"本次请求执行失败。失败原因：{failure_reason}。"
            if generic_error_reply and reply.strip().startswith(generic_error_reply):
                return _with_execution_notice(reply, records)
            return reply
        text = _MODEL_ERRORS.get(
            error, f"本次请求执行失败。失败原因：{failure_reason}。",
        )
        if should_show_failure and failure:
            return _with_tool_failure(text, failure)
        return _with_execution_notice(text, records)
    if should_show_failure and failure:
        return _with_tool_failure(reply, failure)
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


def _successful_read_fallback(
    records: Sequence[Any],
    *,
    interruption_reason: str = "",
) -> str:
    reads = []
    failed_reads = 0
    for item in records:
        if (
            not isinstance(item, Mapping)
            or _operation_kind(item) != "read"
        ):
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
        platform = str(item.get("platform") or item.get("namespace") or "").strip()
        if platform:
            resource = f"{platform} · {resource}"
        tool_name = str(item.get("tool") or item.get("name") or "")
        if tool_name == "agent_web_search":
            source = "网页搜索"
            summary = _format_web_search_results(data)
        else:
            data_status = str(data.get("data_status") or "")
            source = "真实渠道 API" if data_status == "live" else "查询工具"
            summary = _format_read_data(resource, data)
        if summary:
            summaries.append(f"**{resource}**（{source}）\n\n{summary}")
    if not summaries:
        return ""
    failure_details = []
    for item in records:
        if not isinstance(item, Mapping):
            continue
        detail = _failed_tool_detail([item])
        if detail:
            failure_details.append(f"- {detail[0]}：{detail[1]}")
    if failed_reads:
        opening = f"部分查询已成功，另有 {failed_reads} 项查询失败。"
        if interruption_reason:
            opening += f"{interruption_reason}，以下仅列出成功结果：\n\n"
        else:
            opening += "模型摘要服务暂时不可用，以下仅列出成功结果：\n\n"
    else:
        opening = "查询已成功。"
        if interruption_reason:
            opening += (
                f"{interruption_reason}，未能完成后续分析；"
                "以下内容直接来自本次工具结果：\n\n"
            )
        else:
            opening += (
                "模型摘要服务暂时不可用，以下内容直接来自本次工具结果：\n\n"
            )
    if failure_details:
        opening += "失败项详情：\n" + "\n".join(failure_details) + "\n\n"
    return (
        opening + "\n\n".join(summaries)
    )


def _account_listing_partial_reply(records: Sequence[Any]) -> str:
    """Render partial account-list results without inferring failed counts."""
    items = [item for item in records if isinstance(item, Mapping)]
    if not items or len(items) != len(records):
        return ""
    for item in items:
        payload = _tool_payload(item)
        action = str(item.get("action") or payload.get("action") or "").lower()
        resource = str(
            item.get("resource_type") or payload.get("resource_type") or ""
        ).lower()
        if (
            _operation_kind(item) != "read"
            or action != "list"
            or resource not in {"account", "advertiser", "customer_client"}
        ):
            return ""

    failed_items = [
        item for item in items
        if (
            item.get("is_error")
            or item.get("success") is False
            or _tool_payload(item).get("success") is False
        )
    ]
    if not failed_items:
        return ""

    rows: list[str] = []
    failure_details: list[str] = []
    successful_count = 0
    labels = {
        "google-ads": "Google Ads",
        "meta": "Meta",
        "tiktok": "TikTok",
    }
    for item in items:
        payload = _tool_payload(item)
        platform = str(
            item.get("platform") or item.get("namespace")
            or payload.get("platform") or payload.get("namespace") or ""
        ).strip()
        label = labels.get(platform.casefold(), platform or "未知平台")
        failed = (
            item.get("is_error")
            or item.get("success") is False
            or payload.get("success") is False
        )
        if failed:
            category, reason = _account_list_failure(item, payload)
            count = "未能读取"
            account_text = "未返回账户列表"
            failure_details.append(
                _format_account_list_failure(label, category, reason)
            )
        else:
            data = item.get("data")
            if not isinstance(data, Mapping):
                data = payload.get("data")
            data = data if isinstance(data, Mapping) else {}
            returned_count = _account_list_returned_count(data)
            count = str(returned_count) if returned_count is not None else "未知"
            account_text = _account_list_account_labels(data)
            successful_count += 1
        rows.append(
            "| "
            + " | ".join((
                _escape_cell(label),
                _escape_cell(
                    category if failed else "查询成功"
                ),
                _escape_cell(count),
                _escape_cell(account_text),
            ))
            + " |"
        )

    title = (
        "账户查询部分完成"
        if successful_count
        else "账户查询未成功"
    )
    summary = (
        f"已从 {successful_count} 个渠道读取账户信息；"
        f"{len(failed_items)} 个渠道未能读取。"
        if successful_count
        else f"{len(failed_items)} 个渠道的账户查询失败。"
    )
    output = [
        f"## {title}",
        "",
        summary,
        "",
        "| 平台 | 查询状态 | 数量 | 账户 |",
        "| --- | --- | --- | --- |",
        *rows,
    ]
    if failure_details:
        output.extend(["", "失败详情：", *failure_details])
    return "\n".join(output)


def _account_list_failure(
    item: Mapping[str, Any],
    payload: Mapping[str, Any],
) -> tuple[str, str]:
    detail = item.get("error_detail") or payload.get("error_detail")
    detail = detail if isinstance(detail, Mapping) else {}
    category = str(detail.get("category") or "").strip().lower()
    failure = _failed_tool_detail([item])
    reason = failure[1] if failure else str(
        payload.get("error") or item.get("error") or "账户查询失败"
    )
    normalized = reason.casefold()
    if (
        category in {"scope_denied", "scope_mismatch", "account_scope_denied"}
        or "账户不在当前身份的授权范围" in reason
        or "not in the current identity's authorized scope" in normalized
    ):
        return "应用账户范围拒绝", reason
    if (
        category == "provider_permission"
        or "caller does not have permission" in normalized
        or "permission denied" in normalized
        or "not authorized" in normalized
        or "http 403" in normalized
    ):
        return "Provider API 权限拒绝", reason
    return "查询失败", reason


def _account_list_returned_count(data: Mapping[str, Any]) -> int | None:
    summary = data.get("query_summary")
    summary = summary if isinstance(summary, Mapping) else {}
    for value in (summary.get("returned_count"), data.get("total_count")):
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            return value
    for key in ("accounts", "customer_clients", "advertisers"):
        values = data.get(key)
        if isinstance(values, list):
            return sum(isinstance(value, Mapping) for value in values)
    return None


def _account_list_account_labels(data: Mapping[str, Any]) -> str:
    values: list[Mapping[str, Any]] = []
    for key in ("accounts", "customer_clients", "advertisers"):
        rows = data.get(key)
        if isinstance(rows, list):
            values = [row for row in rows if isinstance(row, Mapping)]
            if values:
                break
    labels: list[str] = []
    for account in values[:5]:
        account_id = next((
            str(account[key]).strip()
            for key in ("account_id", "advertiser_id", "customer_id", "id")
            if account.get(key) not in (None, "")
        ), "")
        name = str(account.get("name") or "").strip()
        label = account_id or _display_text(name, 100)
        if account_id and name:
            label += f" ({_display_text(name, 100)})"
        if label:
            labels.append(label)
    if not labels:
        return "无账户" if _account_list_returned_count(data) == 0 else "未返回账户详情"
    count = _account_list_returned_count(data)
    if count is not None and count > len(labels):
        labels.append(f"另有 {count - len(labels)} 个")
    return "; ".join(labels)


def _format_account_list_failure(
    platform: str,
    category: str,
    reason: str,
) -> str:
    safe_reason = _display_text(reason, 500) or "工具没有提供错误详情"
    if category == "Provider API 权限拒绝":
        explanation = (
            "Provider API 返回权限拒绝，因此账户数量未知；"
            "这不能证明应用侧 account scope "
            "不包含该账户，也无法仅凭此错误确定具体授权配置原因。"
        )
    elif category == "应用账户范围拒绝":
        explanation = (
            "应用侧 principal account scope 拒绝了请求，因此账户数量未知；"
            "这次没有证据表明 Provider API 已被调用。"
        )
    else:
        explanation = "查询未返回账户列表，因此账户数量未知。"
    return (
        f"- **{_escape_inline(platform)}**：{explanation} "
        f"原始错误：`{_escape_inline(safe_reason)}`"
    )


def _knowledge_search_fallback(records: Sequence[Any]) -> str:
    collected = _collect_knowledge_search_results(records)
    if not isinstance(collected, tuple):
        return ""
    results, failed_searches = collected
    unique_results = _unique_knowledge_results(results)
    return _format_knowledge_search_results(
        unique_results, failed_searches,
    )


def _collect_knowledge_search_results(
    records: Sequence[Any],
) -> tuple[list[Mapping[str, Any]], int] | None:
    results: list[Mapping[str, Any]] = []
    successful_search = False
    failed_searches = 0
    for item in records:
        if not isinstance(item, Mapping):
            continue
        payload = _tool_payload(item)
        is_knowledge_search = (
            str(item.get("tool") or item.get("name") or "")
            == "agent_knowledge_search"
            or str(item.get("resource_type") or "") == "knowledge"
        )
        if not is_knowledge_search:
            return None
        data = item.get("data")
        if not isinstance(data, Mapping):
            data = payload.get("data")
        failed = (
            item.get("is_error")
            or item.get("success") is False
            or payload.get("success") is False
        )
        if failed:
            failed_searches += 1
            continue
        if not isinstance(data, Mapping):
            continue
        successful_search = True
        candidates = data.get("results")
        if isinstance(candidates, list):
            results.extend(
                value for value in candidates if isinstance(value, Mapping)
            )
    if not successful_search:
        return None
    return results, failed_searches


def _unique_knowledge_results(
    results: Sequence[Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    unique_results: list[Mapping[str, Any]] = []
    seen: set[str] = set()
    for item in results:
        key = str(
            item.get("document_id")
            or (
                f"{item.get('title', '')}|{item.get('source_ref', '')}"
                f"|{item.get('excerpt', '')}"
            )
        )
        if key in seen:
            continue
        seen.add(key)
        unique_results.append(item)
    return unique_results


def _format_knowledge_search_results(
    results: Sequence[Mapping[str, Any]],
    failed_searches: int,
) -> str:
    if not results:
        if failed_searches:
            return (
                f"知识库检索部分完成，另有 {failed_searches} 项检索失败，"
                "未找到可展示的条目。"
            )
        return "知识库检索已完成，没有找到相关内容。"

    lines = [f"知识库检索到 {len(results)} 条相关内容："]
    for index, item in enumerate(results[:5], start=1):
        title = _display_text(
            item.get("title") or item.get("topic") or "知识条目", 300,
        )
        excerpt = _display_text(item.get("excerpt") or "", 1200)
        citation = item.get("citation")
        citation = citation if isinstance(citation, Mapping) else {}
        section = _display_text(citation.get("section") or "", 200)
        source = _display_text(
            item.get("source_ref") or citation.get("source_ref")
            or citation.get("source") or "",
            500,
        )
        lines.append(f"\n### {index}. {title}")
        if excerpt:
            lines.append(f"\n{excerpt}")
        details = []
        if section:
            details.append(f"章节：`{_escape_inline(section)}`")
        if source:
            details.append(f"来源：`{_escape_inline(source)}`")
        if details:
            lines.append("\n\n" + " · ".join(details))
    if failed_searches:
        lines.append(f"\n\n另有 {failed_searches} 项检索未完成。")
    return "\n".join(lines)


def _protocol_failure_reply(
    protocol_notice: str,
    records: Sequence[Any],
    should_show_failure: bool,
    failure: tuple[str, str] | None,
) -> str:
    if should_show_failure and failure:
        return _with_tool_failure("", failure)
    for fallback in (
        _knowledge_search_fallback(records),
        _successful_read_fallback(records),
    ):
        if fallback:
            return f"{fallback}\n\n{protocol_notice}"
    return protocol_notice


def _display_text(value: Any, limit: int) -> str:
    if not isinstance(value, str):
        return ""
    return str(redact_for_persistence(value)).strip()[:limit]


def _escape_inline(value: str) -> str:
    return str(value).replace("\\", "\\\\").replace("`", "\\`")


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


def _format_web_search_results(data: Mapping[str, Any]) -> str:
    candidates = data.get("results")
    results = (
        [item for item in candidates if isinstance(item, Mapping)]
        if isinstance(candidates, list) else []
    )
    if not results:
        return "网页搜索已完成，没有找到相关结果。"

    lines = [f"网页搜索找到 {len(results)} 条结果："]
    for index, item in enumerate(results[:5], start=1):
        title = _display_text(item.get("title") or "网页来源", 300)
        snippet = _display_text(item.get("snippet") or "", 1200)
        url = _safe_markdown_url(item.get("url"))
        age = _display_text(item.get("age") or "", 100)
        heading = f"### {index}. [{title}]({url})" if url else f"### {index}. {title}"
        lines.extend(["", heading])
        if snippet:
            lines.extend(["", snippet])
        if age:
            lines.extend(["", f"时间：{age}"])
    return "\n".join(lines)


def _safe_markdown_url(value: Any) -> str:
    if not isinstance(value, str) or len(value) > 2048:
        return ""
    try:
        parsed = urlsplit(value.strip())
        if (
            parsed.scheme.lower() not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
        ):
            return ""
        parsed.port
    except ValueError:
        return ""
    normalized = urlunsplit((
        parsed.scheme.lower(),
        parsed.netloc,
        parsed.path,
        parsed.query,
        "",
    ))
    return quote(normalized, safe=":/?#[]@!$&+,;=%-._~")


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
    name = str(record.get("name") or "")
    payload = _tool_payload(record)
    result = {
        "name": name,
        "content": record.get("content", ""),
        "is_error": bool(metadata.get("is_error")),
        **{
            key: metadata[key] for key in (
                "needs_input", "needs_confirmation", "confirmation_payload",
            ) if key in metadata
        },
    }
    if name == "agent_knowledge_search":
        result.update({
            "action": "search",
            "effect_class": "read",
            "resource_type": "knowledge",
        })
    if name == "agent_web_search":
        result.update({
            "action": "search",
            "effect_class": "read",
            "resource_type": "web",
        })
    if isinstance(payload, Mapping):
        for key in ("success", "data", "error"):
            if key in payload:
                result[key] = payload[key]
    return result


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
        {
            **{
                key: record.get(key)
                for key in ("role", "content", "created_at", "turn_id")
            },
            **(
                {"attachments": list(_metadata(record)["attachments"])}
                if isinstance(_metadata(record).get("attachments"), list)
                else {}
            ),
        }
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
    raw_reply = _stored_turn_reply(metadata, candidate, native, presented)
    reply = _strip_private_think(raw_reply)
    ui = next((
        _metadata(row)["ui"] for row in reversed(assistants)
        if isinstance(_metadata(row).get("ui"), Mapping) and _metadata(row)["ui"]
    ), stored_ui)
    ui = ui if isinstance(ui, Mapping) else {}
    tool_results = [_history_tool(row) for row in tools]
    if not reply.strip() or _is_tool_protocol_only(raw_reply):
        reply = visible_run_reply({
            "reply": raw_reply,
            "tool_results": tool_results,
            "ui": ui,
            "status": metadata.get("display_status"),
        })
    if not reply.strip() and not ui:
        return visible
    status = str(metadata.get("display_status") or "")
    user_feedback = metadata.get("user_feedback")
    feedback_rating = (
        str(user_feedback.get("rating") or "")
        if isinstance(user_feedback, Mapping)
        else ""
    )
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
        **(
            {"feedback_rating": feedback_rating}
            if feedback_rating in {"positive", "negative"}
            else {}
        ),
        **({"ui": dict(ui)} if ui else {}),
        **({"tools": badges} if (badges := _tool_badges(tools)) else {}),
    })
    return visible


def _stored_turn_reply(
    metadata: Mapping[str, Any],
    candidate: Mapping[str, Any],
    native: Sequence[Mapping[str, Any]],
    presented: Sequence[Mapping[str, Any]],
) -> str:
    value = metadata.get("display_reply")
    if not value and native and not presented:
        value = candidate.get("content")
    return str(value or "")


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
