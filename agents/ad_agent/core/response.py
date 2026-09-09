"""Generic response rendering contracts for an Agent Runtime."""

from __future__ import annotations

from typing import Any, Protocol


class ResponseRenderer(Protocol):
    """Render a turn result without participating in execution or routing."""

    renderer_name: str

    def render(
        self,
        intent: Any,
        results: list[dict[str, Any]],
        needs_confirmation: bool,
        analysis: dict[str, Any] | None = None,
    ) -> str:
        ...

    def render_chat(self, user_input: str) -> str:
        ...


class ResponseSynthesizer(Protocol):
    """Model-backed final-answer boundary, separate from execution."""

    def synthesize(
        self,
        llm: Any,
        *,
        user_input: str,
        intent: Any,
        results: list[dict[str, Any]],
        knowledge: list[dict[str, Any]] | None,
        analysis: dict[str, Any] | None,
        fallback_reply: str,
        needs_confirmation: bool = False,
        memory: list[dict[str, Any]] | None = None,
    ) -> str | None:
        ...


__all__ = ["ResponseRenderer", "ResponseSynthesizer"]
