"""Localized, bounded user-facing execution summaries from real Run events."""

from __future__ import annotations

from typing import Any, Mapping

from agents.agent_harness.core.response_language import infer_response_language


_PRIVATE_EVENTS = frozenset({"model_reasoning_delta", "model_delta"})


def private_progress_event(event: Mapping[str, Any]) -> bool:
    kind = str(event.get("type") or event.get("event_type") or "")
    return kind in _PRIVATE_EVENTS or (
        kind == "reasoning_delta" and event.get("content_type") != "execution_summary"
    )


def public_execution_events(events) -> list:
    return [
        event for event in events
        if isinstance(event, Mapping)
        and not private_progress_event(event)
    ]


def public_run_view(value: Mapping[str, Any]) -> dict:
    public = dict(value)
    if isinstance(value.get("events"), list):
        public["events"] = public_execution_events(value["events"])
    if isinstance(value.get("execution_traces"), Mapping):
        public["execution_traces"] = {
            turn_id: public_run_view(trace) if isinstance(trace, Mapping) else trace
            for turn_id, trace in value["execution_traces"].items()
        }
    return public


def progress_language(runtime: Any, user_input: str, session_id: str | None, principal: Any) -> str:
    current = infer_response_language(user_input, default="")
    if current:
        return current
    previous = []
    get_conversation = getattr(runtime, "get_conversation", None)
    if session_id and callable(get_conversation):
        conversation = get_conversation(
            session_id=session_id, user_id=principal.user_id,
            tenant_id=principal.tenant_id, limit=2,
        ) or {}
        previous = [
            message["content"] for message in conversation.get("messages", [])
            if message.get("role") == "user" and isinstance(message.get("content"), str)
        ]
    return infer_response_language(user_input, previous)


class StreamExecutionSummaries:
    def __init__(self, language: str):
        self.language = language
        self.has_tool_result = False
        self._last_summary = ""

    def _text(self, chinese: str, english: str) -> str:
        return chinese if self.language == "zh" else english

    def for_event(self, event: Mapping[str, Any]) -> dict | None:
        kind = str(event.get("type") or event.get("event_type") or "")
        name = str(event.get("tool_name") or "")[:120]
        summary = ""
        if kind == "model_start":
            summary = self._text(
                "正在根据工具返回的信息整理下一步答复。" if self.has_tool_result
                else "正在检查请求所需的信息与当前可用工具。",
                "Preparing a response from the returned tool information." if self.has_tool_result
                else "Checking the request requirements and currently available tools.",
            )
        elif kind == "tool_execution_start":
            summary = self._text(f"正在执行工具：{name}。", f"Running tool: {name}.")
        elif kind == "tool_execution_end":
            self.has_tool_result = True
            summary = self._tool_summary(name, event)
        if not summary or summary == self._last_summary:
            return None
        self._last_summary = summary
        return {
            "type": "reasoning_delta", "event_type": "reasoning_delta",
            "content_type": "execution_summary", "language_code": self.language,
            "status": "running", "content": summary + "\n",
        }

    def _tool_summary(self, name: str, event: Mapping[str, Any]) -> str:
        result = event.get("result")
        result = result if isinstance(result, Mapping) else {}
        if result.get("needs_confirmation") or result.get("requires_confirmation"):
            return self._text(
                f"工具 {name} 需要确认，尚未提交本次写入。",
                f"Tool {name} requires confirmation; this write has not been submitted.",
            )
        if result.get("needs_input"):
            return self._text(
                f"工具 {name} 需要补充输入后继续。",
                f"Tool {name} requires additional input before continuing.",
            )
        if event.get("is_error") or result.get("success") is False:
            return self._text(
                f"工具 {name} 返回错误；当前步骤未完成。",
                f"Tool {name} returned an error; this step is incomplete.",
            )
        summary = self._text(f"工具 {name} 已返回结果。", f"Tool {name} returned a result.")
        data = result.get("data")
        query = data.get("query_summary", {}) if isinstance(data, Mapping) else {}
        count = query.get("returned_count") if isinstance(query, Mapping) else None
        if type(count) is int and count >= 0:
            summary += self._text(f"本次实际返回 {count} 项。", f"Returned {count} items.")
        return summary
