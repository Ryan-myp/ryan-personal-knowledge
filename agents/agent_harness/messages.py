"""Application-neutral transcript and model turn contracts."""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal, Mapping, Sequence

MessageRole = Literal["system", "user", "assistant", "tool"]


def _json_safe(value: Any) -> Any:
    """Keep transcript metadata serializable without executing user code."""
    try:
        json.dumps(value, ensure_ascii=False)
        return value
    except (TypeError, ValueError):
        return str(value)


@dataclass(frozen=True)
class AgentMessage:
    """One durable message in an Agent transcript."""

    role: MessageRole
    content: Any = ""
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    run_id: str = ""
    turn_id: str = ""
    tool_call_id: str | None = None
    name: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    @classmethod
    def system(cls, content: Any, **kwargs: Any) -> "AgentMessage":
        return cls(role="system", content=content, **kwargs)

    @classmethod
    def user(cls, content: Any, **kwargs: Any) -> "AgentMessage":
        return cls(role="user", content=content, **kwargs)

    @classmethod
    def assistant(cls, content: Any, **kwargs: Any) -> "AgentMessage":
        return cls(role="assistant", content=content, **kwargs)

    @classmethod
    def tool(
        cls, content: Any, *, tool_call_id: str, name: str, **kwargs: Any,
    ) -> "AgentMessage":
        return cls(
            role="tool",
            content=content,
            tool_call_id=tool_call_id,
            name=name,
            **kwargs,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "content": _json_safe(self.content),
            "message_id": self.message_id,
            "run_id": self.run_id,
            "turn_id": self.turn_id,
            "tool_call_id": self.tool_call_id,
            "name": self.name,
            "metadata": _json_safe(dict(self.metadata)),
            "timestamp": self.timestamp,
        }


@dataclass(frozen=True)
class ToolCall:
    """A model-requested tool invocation."""

    id: str
    name: str
    arguments: Mapping[str, Any] = field(default_factory=dict)
    depends_on: Sequence[str] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "depends_on",
            tuple(
                str(item).strip()
                for item in (self.depends_on or ())
                if str(item).strip()
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        value = {
            "id": self.id,
            "name": self.name,
            "arguments": _json_safe(dict(self.arguments)),
        }
        if self.depends_on:
            value["depends_on"] = list(self.depends_on)
        return value


@dataclass(frozen=True)
class ModelTurn:
    """Normalized response from any model/provider adapter."""

    content: Any = ""
    tool_calls: Sequence[ToolCall] = field(default_factory=tuple)
    stop_reason: str = "stop"
    usage: Mapping[str, Any] = field(default_factory=dict)
    context_updates: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "tool_calls", tuple(self.tool_calls or ()))
        object.__setattr__(
            self, "context_updates", dict(self.context_updates or {})
        )


__all__ = ["AgentMessage", "MessageRole", "ModelTurn", "ToolCall"]
