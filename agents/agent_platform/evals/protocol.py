"""Data-only helpers for the skill-up SessionInput/SessionResult protocol."""

import json
from typing import Any, Mapping


def session_messages(session_input: Mapping[str, Any]) -> list[dict[str, str]]:
    messages = session_input.get("messages")
    if not isinstance(messages, list) or not messages:
        prompt = session_input.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("SessionInput.messages or SessionInput.prompt is required")
        return [{"role": "user", "content": prompt}]
    result = []
    for item in messages:
        if not isinstance(item, Mapping):
            raise ValueError("SessionInput.messages entries must be objects")
        role = str(item.get("role", "")).strip()
        content = item.get("content", "")
        if role not in {"system", "user", "assistant", "tool"}:
            raise ValueError(f"unsupported SessionInput message role: {role}")
        if not isinstance(content, str):
            raise ValueError("SessionInput message content must be a string")
        result.append({"role": role, "content": content})
    return result


def session_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
