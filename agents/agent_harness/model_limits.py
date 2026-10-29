"""Provider-neutral model payload bounds, measured in serialized characters."""

from __future__ import annotations

import json
from typing import Any, Mapping, Sequence

from .messages import AgentMessage, ModelTurn
from .evidence_compaction import compact_read_messages
from .tool_schema_projection import model_tool_payload

DEFAULT_MODEL_INPUT_CHARS = 256_000
DEFAULT_MODEL_OUTPUT_CHARS = 128_000
DEFAULT_STREAM_CHUNKS = 10_000


class ModelTimeoutError(TimeoutError):
    """The provider exceeded the configured invocation deadline."""


class ModelLimitError(RuntimeError):
    """A local resource limit, not a retryable provider failure."""

    safe_reason_code = "model_limit_exceeded"
    public_reply = "本次请求超过处理上限，请缩小范围后重试。"

    def __init__(self) -> None:
        super().__init__(self.safe_reason_code)


class ModelInputLimitError(ModelLimitError):
    safe_reason_code = "model_input_limit_exceeded"
    public_reply = "本次输入与必要上下文超过处理上限，请缩小请求范围或分批提交。"


class ModelOutputLimitError(ModelLimitError):
    safe_reason_code = "model_output_limit_exceeded"
    public_reply = "模型输出超过本次处理上限，已停止继续处理，请缩小范围后重试。"

class ModelInvocationStoppedError(ModelLimitError):
    safe_reason_code = "model_invocation_stopped"
    public_reply = "本次任务已停止，不再继续请求模型服务。"


def positive_integer(name: str, value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


def serialized_chars(value: Any) -> int:
    return sum(len(part) for part in json.JSONEncoder(
        ensure_ascii=False, separators=(",", ":"), allow_nan=False,
    ).iterencode(value))


def _message_payload(message: AgentMessage) -> dict[str, Any]:
    value = {"role": message.role, "content": message.content}
    if message.role == "assistant" and message.metadata.get("tool_calls"):
        value["tool_calls"] = message.metadata["tool_calls"]
    if message.role == "tool":
        value.update(tool_call_id=message.tool_call_id, name=message.name)
    return value


def _tool_payload(tool: Any) -> dict[str, Any]:
    return model_tool_payload(tool)


def _input_sizes(
    messages: Sequence[AgentMessage], tools: Sequence[Any],
) -> tuple[int, list[int]]:
    try:
        sizes = [model_message_chars(message) for message in messages]
        fixed = serialized_chars({
            "messages": [], "tools": [_tool_payload(tool) for tool in tools],
        })
        return fixed, sizes
    except (TypeError, ValueError, RecursionError) as error:
        raise ModelInputLimitError() from error


def model_input_chars(messages: Sequence[AgentMessage], tools: Sequence[Any]) -> int:
    fixed, sizes = _input_sizes(messages, tools)
    return fixed + sum(sizes) + max(0, len(sizes) - 1)


def model_message_chars(message: AgentMessage) -> int:
    return serialized_chars(_message_payload(message))


def bound_model_messages(
    messages: Sequence[AgentMessage], tools: Sequence[Any], *, max_chars: int,
    evidence_definitions: Sequence[Any] = (),
) -> list[AgentMessage]:
    """Evict oldest user-led groups, never policy or the current user group."""
    positive_integer("max_model_input_chars", max_chars)
    fixed, sizes = _input_sizes(messages, tools)
    retained = [True] * len(messages)
    total = fixed + sum(sizes) + max(0, len(sizes) - 1)
    user_starts = [index for index, message in enumerate(messages) if message.role == "user"]
    # A transcript window may begin in the middle of an older Tool exchange.
    # Its orphan prefix is not valid model history, even when it fits.
    prefix_end = user_starts[0] if user_starts else 0
    groups = [(0, prefix_end), *zip(user_starts, user_starts[1:])]
    for start, end in groups:
        if start >= prefix_end and total <= max_chars:
            break
        for index in range(start, end):
            if messages[index].role == "system":
                continue
            retained[index] = False
            total -= sizes[index] + 1
    result = [message for index, message in enumerate(messages) if retained[index]]
    if not result:
        total = fixed
    if total > max_chars and evidence_definitions:
        message_budget = max_chars - fixed - max(0, len(result) - 1)
        if message_budget > 0:
            result = compact_read_messages(
                result, evidence_definitions, max_chars=message_budget,
                message_size=model_message_chars,
            )
            total = model_input_chars(result, tools)
    if total > max_chars:
        raise ModelInputLimitError()
    return result


def provider_input_chars(messages: Sequence[Mapping[str, Any]], tools: Any) -> int:
    """Count final SDK text/schema payload, not binary image transport or tokens."""
    projected = []
    for message in messages:
        value = dict(message)
        content = value.get("content")
        if isinstance(content, list):
            value["content"] = [_text_part(part) for part in content]
        projected.append(value)
    return serialized_chars({"messages": projected, "tools": tools or []})


def _text_part(part: Any) -> Any:
    if not isinstance(part, Mapping) or part.get("type") != "image_url":
        return part
    image = part.get("image_url")
    if not isinstance(image, Mapping) or not str(image.get("url", "")).startswith("data:"):
        return part
    return {**part, "image_url": {**image, "url": "[binary image]"}}


def model_output_chars(turn: ModelTurn) -> int:
    try:
        return (
            len(turn.content) if isinstance(turn.content, str)
            else serialized_chars(turn.content)
        ) + sum(serialized_chars(call.to_dict()) for call in turn.tool_calls) + (
            serialized_chars(dict(turn.context_updates)) if turn.context_updates else 0
        )
    except (TypeError, ValueError, RecursionError) as error:
        raise ModelOutputLimitError() from error
