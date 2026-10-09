"""Explicit model fixtures for advertising Runs through the generic Harness."""

from __future__ import annotations

from typing import Any

from agents.agent_harness.messages import ModelTurn, ToolCall


class ScriptedHarnessModel:
    """Return declared model turns and reject calls outside the active catalog."""

    def __init__(self, *turns: ModelTurn) -> None:
        self.turns = list(turns)
        self.messages: list[list[Any]] = []
        self.tool_names: list[tuple[str, ...]] = []

    def complete(self, messages: Any, tools: Any, _request: Any) -> ModelTurn:
        self.messages.append(list(messages))
        self.tool_names.append(tuple(
            str(getattr(tool, "name", "") or "")
            for tool in (tools or ())
        ))
        if not self.turns:
            raise AssertionError("Harness requested an unscripted model turn")
        turn = self.turns.pop(0)
        available = {
            str(getattr(tool, "name", "")) for tool in (tools or ())
        }
        unavailable = sorted({
            call.name for call in turn.tool_calls if call.name not in available
        })
        if unavailable:
            raise AssertionError(
                "model requested Tools outside the active catalog: "
                + ", ".join(unavailable)
            )
        return turn


def call(
    name: str,
    arguments: dict[str, Any] | None = None,
    *,
    call_id: str = "scripted-call",
    depends_on: tuple[str, ...] = (),
) -> ToolCall:
    return ToolCall(
        call_id,
        name,
        arguments or {},
        depends_on=depends_on,
    )


def install(runtime: Any, *turns: ModelTurn) -> ScriptedHarnessModel:
    model = ScriptedHarnessModel(*turns)
    runtime.platform_application.agent.model = model
    return model


__all__ = ["ScriptedHarnessModel", "call", "install"]
