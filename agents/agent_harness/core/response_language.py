"""Small language hints based on user prose, never on Tool or document text."""

from __future__ import annotations

import re
from typing import Any, Sequence


def _prose_language(text: str) -> str:
    text = str(text or "")[:2400]
    text = re.sub(r"```[\s\S]*?```|`[^`]*`|https?://\S+", " ", text)
    text = re.sub(r'"[^"]*"|“[^”]*”', " ", text)
    chinese = len(re.findall(r"[\u3400-\u9fff]", text))
    words = [
        word for word in re.findall(r"(?<![\w])[a-zA-Z]{2,}(?![\w])", text)
        if not word.isupper()
    ]
    if chinese and not (len(words) >= 6 and sum(map(len, words)) > chinese * 4):
        return "zh"
    return "en" if words else ""


def infer_response_language(
    user_input: str, previous_inputs: Sequence[str] = (), *, default: str = "zh",
) -> str:
    current = _prose_language(user_input)
    if current:
        return current
    for text in reversed(tuple(previous_inputs)[-8:]):
        language = _prose_language(text)
        if language:
            return language
    return default


def response_language_instruction(request: Any, messages: Sequence[Any]) -> str:
    previous = [
        str(message.content) for message in messages
        if getattr(message, "role", "") == "user" and isinstance(message.content, str)
    ]
    language = infer_response_language(
        str(getattr(request, "user_input", "") or ""), previous, default="en",
    )
    if language == "zh":
        return (
            "本轮用户使用简体中文。界面可见的简短执行说明和最终答复使用简体中文，"
            "不要夹杂英文叙述。API 字段、代码、Tool 名称和专有名称保留原样。"
            "若用户明确指定其他输出语言，优先遵从该要求。"
            "不要输出内部思维链、草稿推演或逐步私有分析；只提供简短执行说明与结论。"
        )
    return (
        "Use English for brief user-visible execution summaries and the final answer. "
        "Follow any explicit language preference in the latest user request instead. "
        "Preserve API fields, code, Tool names and proper names. "
        "Do not expose internal chain-of-thought, scratchpads or private step-by-step analysis."
    )
