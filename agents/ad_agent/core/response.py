"""Generic response rendering contract for Agent Runtime."""

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
