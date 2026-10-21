"""Application-neutral transcript and model turn contracts."""

from __future__ import annotations

import json
import math
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal, Mapping, Sequence

MessageRole = Literal["system", "user", "assistant", "tool"]
_SUPPORTED_MEDIA_TYPES = frozenset({
    "image/jpeg", "image/png", "image/gif", "image/webp",
    "video/mp4", "video/quicktime", "video/webm",
    "text/csv", "text/markdown", "text/plain", "application/pdf",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
})
_DOCUMENT_MEDIA_TYPES = frozenset({
    "text/csv",
    "text/markdown",
    "text/plain",
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
})
_MAX_EXTRACTED_DOCUMENT_CHARS = 24_000


@dataclass(frozen=True)
class MediaFrame:
    """One bounded image frame derived from a video input."""

    timestamp_seconds: float
    media_type: str
    content: bytes

    def __post_init__(self) -> None:
        if (
            not isinstance(self.timestamp_seconds, (int, float))
            or isinstance(self.timestamp_seconds, bool)
            or not math.isfinite(self.timestamp_seconds)
            or self.timestamp_seconds < 0
        ):
            raise ValueError(
                "media frame timestamp must be finite and non-negative"
            )
        if self.media_type not in {
            "image/jpeg", "image/png", "image/gif", "image/webp",
        }:
            raise ValueError("media frame must use a supported image media type")
        if not isinstance(self.content, bytes) or not self.content:
            raise ValueError("media frame content must be non-empty bytes")


@dataclass(frozen=True)
class InputMedia:
    """Ephemeral user attachment passed to a model adapter for one Run."""

    attachment_id: str
    filename: str
    media_type: str
    content: bytes
    frames: Sequence[MediaFrame] = field(default_factory=tuple)
    extracted_text: str = ""

    def __post_init__(self) -> None:
        if not str(self.attachment_id or "").strip():
            raise ValueError("input media attachment_id must be non-empty")
        if not str(self.filename or "").strip():
            raise ValueError("input media filename must be non-empty")
        if self.media_type not in _SUPPORTED_MEDIA_TYPES:
            raise ValueError(f"unsupported input media type: {self.media_type}")
        if not isinstance(self.content, bytes) or not self.content:
            raise ValueError("input media content must be non-empty bytes")
        extracted_text = self.extracted_text
        if not isinstance(extracted_text, str):
            raise TypeError("input media extracted_text must be a string")
        if len(extracted_text) > _MAX_EXTRACTED_DOCUMENT_CHARS:
            raise ValueError("input media extracted text exceeds 24000 characters")
        if (
            self.media_type in _DOCUMENT_MEDIA_TYPES
            and not extracted_text.strip()
        ):
            raise ValueError("document input media must contain extracted text")
        if (
            self.media_type not in _DOCUMENT_MEDIA_TYPES
            and extracted_text
        ):
            raise ValueError("only document input media may contain extracted text")
        frames = tuple(self.frames or ())
        if len(frames) > 8:
            raise ValueError("input media frame limit is 8")
        if self.media_type.startswith("image/") and frames:
            raise ValueError("image input media cannot contain video frames")
        if self.media_type.startswith("video/") and any(
            not isinstance(frame, MediaFrame) for frame in frames
        ):
            raise TypeError("video frames must use the MediaFrame contract")
        object.__setattr__(self, "frames", frames)

    def to_metadata(self) -> dict[str, Any]:
        """Return the small transcript-safe attachment reference."""
        return {
            "id": str(self.attachment_id),
            "filename": str(self.filename),
            "media_type": str(self.media_type),
            "size": len(self.content),
        }


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
class ToolArgumentBinding:
    """Copy one value from a completed Tool dependency into a Tool input."""

    target_field: str
    source_call_id: str
    source_path: str

    def __post_init__(self) -> None:
        for name in ("target_field", "source_call_id", "source_path"):
            value = str(getattr(self, name) or "").strip()
            if not value or any(not part for part in value.split(".")):
                raise ValueError(f"{name} must be a non-empty field path")
            object.__setattr__(self, name, value)

    def to_dict(self) -> dict[str, str]:
        return {
            "target_field": self.target_field,
            "source_call_id": self.source_call_id,
            "source_path": self.source_path,
        }


@dataclass(frozen=True)
class ToolCall:
    """A model-requested tool invocation."""

    id: str
    name: str
    arguments: Mapping[str, Any] = field(default_factory=dict)
    depends_on: Sequence[str] = field(default_factory=tuple)
    argument_bindings: Sequence[ToolArgumentBinding] = field(default_factory=tuple)

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
        bindings = tuple(
            item if isinstance(item, ToolArgumentBinding)
            else ToolArgumentBinding(**dict(item))
            for item in (self.argument_bindings or ())
        )
        dependencies = set(self.depends_on)
        if any(item.source_call_id not in dependencies for item in bindings):
            raise ValueError("argument binding source must be a declared dependency")
        object.__setattr__(self, "argument_bindings", bindings)

    def to_dict(self) -> dict[str, Any]:
        value = {
            "id": self.id,
            "name": self.name,
            "arguments": _json_safe(dict(self.arguments)),
        }
        if self.depends_on:
            value["depends_on"] = list(self.depends_on)
        if self.argument_bindings:
            value["argument_bindings"] = [
                item.to_dict() for item in self.argument_bindings
            ]
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


__all__ = [
    "AgentMessage",
    "MessageRole",
    "ModelTurn",
    "ToolArgumentBinding",
    "ToolCall",
]
