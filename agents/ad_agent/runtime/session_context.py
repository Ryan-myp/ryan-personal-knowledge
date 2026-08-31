"""In-memory session state used by the generic Agent Runtime."""

from __future__ import annotations

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
        declared = (
            result.data.get("resource_id_field")
            if isinstance(result.data, dict) else None
        )
        if not isinstance(declared, str) or not declared:
            return
        if not isinstance(result.data, dict) or declared not in result.data:
            return
        self.protected_state[declared] = result.data[declared]
        if platform:
            self.protected_state[f"{platform}:{declared}"] = result.data[declared]

    def get_protected(self, key: str, default=None) -> Any:
        return self.protected_state.get(key, default)

    def to_chat_messages(self) -> list[ChatMessage]:
        return [
            ChatMessage(role=message["role"], content=message["content"])
            for message in self.messages
        ]
