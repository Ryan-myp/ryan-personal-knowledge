"""Localized, bounded user-facing execution summaries from real Run events."""

from __future__ import annotations

import re
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
    def __init__(self, language: str, *, registry: Any = None):
        self.language = language
        self.registry = registry
        self.has_tool_result = False
        self._last_summary = ""
        self._tool_labels: dict[str, str] = {}

    def _text(self, chinese: str, english: str) -> str:
        return chinese if self.language == "zh" else english

    def for_event(self, event: Mapping[str, Any]) -> dict | None:
        kind = str(event.get("type") or event.get("event_type") or "")
        name = str(event.get("tool_name") or "")[:120]
        if kind == "model_start":
            return self._publish(self._model_start_summary())
        if kind == "model_end":
            return self._publish(self._model_end_summary(event))
        if kind == "tool_execution_start":
            return self._publish(self._tool_start_summary(name))
        if kind == "tool_execution_end":
            self.has_tool_result = True
            return self._publish(self._tool_summary(name, event))
        return None

    def _publish(self, summary: str) -> dict | None:
        if not summary or summary == self._last_summary:
            return None
        self._last_summary = summary
        return {
            "type": "reasoning_delta", "event_type": "reasoning_delta",
            "content_type": "execution_summary", "language_code": self.language,
            "status": "running", "content": summary + "\n",
        }

    def _model_start_summary(self) -> str:
        if self.has_tool_result:
            return self._text(
                "已收到工具结果，正在核对结果范围与来源，再整理答复。",
                "Checking the scope and source of the returned information "
                "before composing the answer.",
            )
        return self._text(
            "正在梳理请求目标，并依据当前可用能力判断合适的信息来源。",
            "Clarifying the request and selecting a suitable available "
            "information source.",
        )

    def _model_end_summary(self, event: Mapping[str, Any]) -> str:
        tool_count = event.get("tool_call_count")
        if type(tool_count) is int and tool_count > 0:
            return self._text(
                f"已确定需要调用 {tool_count} 个工具补充依据；接下来执行并核验实际结果。",
                f"Selected {tool_count} Tool call(s) to gather evidence; "
                "next I’ll run them and verify their results.",
            )
        if event.get("has_content") is True:
            return self._text(
                "当前问题已完成分析，正在把要点整理成答复。",
                "The request has been analyzed; I’m organizing the key points "
                "into an answer.",
            )
        return self._text(
            "当前模型调用尚未形成答复，正在继续处理。",
            "This model call did not produce an answer yet; processing will continue.",
        )

    def _tool_start_summary(self, name: str) -> str:
        label = self._registered_tool_label(name)
        if not label:
            return self._text(
                f"当前步骤调用 Tool「{name}」获取所需信息；我会根据实际返回结果作答。",
                f"Running Tool “{name}” to gather the needed information; "
                "I’ll answer from its actual result.",
            )
        self._tool_labels[name] = label
        return self._text(
            f"当前步骤采用「{label}」：先获取相关资料或记录，再根据返回结果组织答复。",
            f"Selected “{label}” for this step. I’ll gather the relevant "
            "information, then build the answer from the result.",
        )

    def _registered_tool_label(self, name: str) -> str:
        getter = getattr(self.registry, "get", None)
        if not name or not callable(getter):
            return ""
        try:
            definition, _handler = getter(name)
        except (AttributeError, KeyError, TypeError, ValueError):
            return ""
        aliases = getattr(definition, "intent_aliases", ()) or ()
        aliases = [self._safe_label(value) for value in aliases]
        aliases = [value for value in aliases if value]
        if self.language == "zh":
            localized = next(
                (value for value in aliases if re.search(r"[\u3400-\u9fff]", value)),
                "",
            )
        else:
            localized = next(
                (value for value in aliases if not re.search(r"[\u3400-\u9fff]", value)),
                "",
            )
        if localized:
            return localized
        if self.language == "zh":
            return ""
        intents = getattr(definition, "intent_types", ()) or ()
        intent = next((self._safe_label(value) for value in intents if value), "")
        if intent:
            return intent.replace("_", " ").strip().title()
        resource = self._safe_label(getattr(definition, "resource_type", ""))
        action = self._safe_label(getattr(definition, "action", ""))
        if resource and action:
            return f"{action} {resource}".strip()
        return ""

    @staticmethod
    def _safe_label(value: Any) -> str:
        if not isinstance(value, str):
            return ""
        label = " ".join(value.split())
        if len(label) > 100 or any(ord(char) < 32 for char in label):
            return ""
        return label

    def _tool_summary(self, name: str, event: Mapping[str, Any]) -> str:
        label = self._tool_labels.get(name, "")
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
        if label:
            summary = self._text(
                f"「{label}」已返回结果；我正在核对本次结果范围并整理答复。",
                f"“{label}” returned information; I’m checking its scope "
                "before composing the answer.",
            )
        else:
            summary = self._text(f"工具 {name} 已返回结果。", f"Tool {name} returned a result.")
        data = result.get("data")
        query = data.get("query_summary", {}) if isinstance(data, Mapping) else {}
        count = query.get("returned_count") if isinstance(query, Mapping) else None
        if type(count) is int and count >= 0:
            summary += self._text(
                f"本次实际返回 {count} 项；我会按这批结果的范围作答。",
                f"It returned {count} items; I’ll answer within that result scope.",
            )
        return summary
