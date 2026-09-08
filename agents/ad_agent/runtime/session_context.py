"""In-memory session state used by the generic Agent Runtime."""

from __future__ import annotations

from typing import Any

from ..core.interfaces import ChatMessage, ToolContext, ToolResult


class SessionContext:
    """Conversation messages and provider-neutral protected references."""

    # The durable conversation_messages table remains the source of truth;
    # this bounded window is the only raw transcript kept in process memory
    # and sent to the model on the next turn.
    MAX_MESSAGES = 20
    # A message-count-only window is not enough: one report or model answer
    # can otherwise consume the entire context budget. The durable message
    # table still keeps the complete sanitized transcript; this is only the
    # bounded working-memory copy.
    MAX_CONTEXT_CHARS = 16_000
    MAX_MESSAGE_CHARS = 2_400
    _TRUNCATION_MARKER = "\n…[上下文已裁剪]…\n"

    def __init__(self, session_id: str, ctx: ToolContext):
        self.session_id = session_id
        self.ctx = ctx
        self.messages: list[dict] = []
        self.tool_results: dict[str, ToolResult] = {}
        self.protected_state: dict[str, Any] = {}

    @classmethod
    def _compact_content(cls, content: Any) -> str:
        text = str(content or "")
        if len(text) <= cls.MAX_MESSAGE_CHARS:
            return text
        marker_size = len(cls._TRUNCATION_MARKER)
        available = max(cls.MAX_MESSAGE_CHARS - marker_size, 2)
        head = max(1, int(available * 0.65))
        tail = max(1, available - head)
        return text[:head] + cls._TRUNCATION_MARKER + text[-tail:]

    @classmethod
    def _bounded_messages(cls, messages: list[dict]) -> tuple[list[dict], list[dict]]:
        """Return the working window and messages evicted from its front."""
        bounded = []
        for raw in messages:
            if not isinstance(raw, dict):
                continue
            bounded.append({
                "role": str(raw.get("role") or "user"),
                "content": cls._compact_content(raw.get("content", "")),
            })

        evicted: list[dict] = []
        while len(bounded) > cls.MAX_MESSAGES:
            evicted.append(bounded.pop(0))
        while bounded and sum(len(str(item.get("content") or "")) for item in bounded) > cls.MAX_CONTEXT_CHARS:
            evicted.append(bounded.pop(0))
        return bounded, evicted

    def add_message(self, message: dict) -> list[dict]:
        """Append a message and return anything evicted from working memory."""
        bounded, evicted = self._bounded_messages([*self.messages, message])
        self.messages = bounded
        self.ctx.messages = list(self.messages)
        return evicted

    def replace_messages(self, messages: list[dict]) -> list[dict]:
        """Restore a bounded working window from durable conversation data."""
        self.messages, evicted = self._bounded_messages(list(messages or []))
        self.ctx.messages = list(self.messages)
        return evicted

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
