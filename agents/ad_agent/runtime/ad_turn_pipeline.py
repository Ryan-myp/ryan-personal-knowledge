"""Advertising application's stage composition root.

The generic Agent Harness owns the Run/Session lifecycle. This module only
assembles advertising-owned stages and translates the opaque request context
into the application flow's explicit inputs.
"""

from __future__ import annotations

from typing import Any

from agents.agent_harness.turn_pipeline import SequentialTurnPipeline

from ..core.runtime_kernel import TurnRequest
from .ad_turn_stages import (
    ExecutionStage,
    IntentStage,
    PlanningStage,
    RequestValidationStage,
    ResponseStage,
    SessionContextStage,
)


class AdTurnPipeline:
    """Compose the advertising application stages over the generic harness."""

    stage_names = (
        "request_validation",
        "session_context",
        "intent",
        "planning",
        "execution",
        "response",
    )

    def __init__(self, runtime: Any):
        self.runtime = runtime
        self._pipeline = SequentialTurnPipeline(
            [
                RequestValidationStage(),
                SessionContextStage(),
                IntentStage(),
                PlanningStage(),
                ExecutionStage(runtime),
                ResponseStage(),
            ]
        )

    def execute(self, request: TurnRequest) -> dict[str, Any]:
        return self._pipeline.execute(request)


__all__ = ["AdTurnPipeline"]
