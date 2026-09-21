"""Application-neutral advisory context provider contract."""

from __future__ import annotations

from typing import Any, Mapping, Protocol, Sequence

from .messages import AgentMessage
from .runtime_kernel import TurnRequest


class ContextProvider(Protocol):
    """Build bounded, non-executable context for one model turn."""

    def build_context(
        self,
        request: TurnRequest,
        messages: Sequence[AgentMessage],
    ) -> Mapping[str, Any]:
        ...


def context_prompt(value: Mapping[str, Any]) -> str:
    """Read an optional provider-rendered prompt without defining its schema."""
    for key in ("prompt", "text", "instructions"):
        text = value.get(key)
        if isinstance(text, str) and text.strip():
            return text.strip()
    return ""


__all__ = ["ContextProvider", "context_prompt"]
