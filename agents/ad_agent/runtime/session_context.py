"""In-memory session state used by the generic Agent Runtime."""

from __future__ import annotations

import re
from typing import Any

from ..core.interfaces import ChatMessage, ToolContext, ToolResult


class SessionContext:
    """Conversation messages and provider-neutral protected references."""

    def __init__(self, session_id: str, ctx: ToolContext):
        self.session_id = session_id
        self.ctx = ctx
        self.messages: list[dict] = []
        self.tool_results: dict[str, ToolResult] = {}
        self.protected_state: dict[str, Any] = {}

    def add_message(self, message: dict) -> None:
        self.messages.append(message)
        self.ctx.messages = list(self.messages)

    def save_result(
        self, tool_name: str, result: ToolResult, platform: str = None
    ) -> None:
        self.tool_results[tool_name] = result
        keys = [
            "campaign_id", "ad_set_id", "adset_id", "ad_group_id", "adgroup_id",
            "creative_id", "io_id", "line_item_id", "ad_id",
        ]
        declared = (
            result.data.get("resource_id_field")
            if isinstance(result.data, dict) else None
        )
        if (
            isinstance(declared, str)
            and re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*_id", declared)
            and declared not in keys
        ):
            keys.append(declared)
        for key in keys:
            if key in result.data:
                self.protected_state[key] = result.data[key]
                if platform:
                    self.protected_state[f"{platform}:{key}"] = result.data[key]

    def get_protected(self, key: str, default=None) -> Any:
        return self.protected_state.get(key, default)

    def to_chat_messages(self) -> list[ChatMessage]:
        return [
            ChatMessage(role=message["role"], content=message["content"])
            for message in self.messages
        ]
