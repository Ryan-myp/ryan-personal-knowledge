"""Explicit state carried by one advertising application turn.

The generic harness intentionally keeps its turn envelope opaque. This state
belongs to the advertising application and is the only place where
advertising-specific planning, workflow and response fields meet.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from agents.agent_harness.runtime_kernel import TurnRequest


@dataclass
class AdTurnState:
    """Mutable application state shared by advertising turn stages."""

    request: TurnRequest
    request_context: Mapping[str, Any] = field(default_factory=dict)
    safe_user_input: str = ""
    session: Any = None
    trace: Any = None
    intent: Any = None
    tool_plan: dict[str, list[Any]] = field(default_factory=dict)
    execution_plan: Any = None
    results: list[dict[str, Any]] = field(default_factory=list)
    response: Any = None
    response_source: Optional[str] = None
    workflow_id: Optional[str] = None
    stage_metadata: dict[str, dict[str, Any]] = field(default_factory=dict)
    terminal_reason: Optional[str] = None

    @classmethod
    def from_request(cls, request: TurnRequest) -> "AdTurnState":
        context = request.context if isinstance(request.context, Mapping) else {}
        return cls(
            request=request,
            request_context=dict(context),
            safe_user_input=str(request.user_input or ""),
        )

    def capture_response(self, response: Any) -> Any:
        self.response = response
        if isinstance(response, dict):
            self.results = list(response.get("results") or [])
            self.workflow_id = response.get("workflow_id")
            self.response_source = response.get("response_source")
            intent = response.get("intent")
            if intent is not None:
                self.intent = intent
        return response

    def mark_stage(self, name: str, **metadata: Any) -> None:
        self.stage_metadata[str(name)] = dict(metadata)


__all__ = ["AdTurnState"]
