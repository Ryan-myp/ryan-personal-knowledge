"""Backward-compatible entry point for advertising turn execution.

New code enters through :class:`AdTurnPipeline`. This function remains only
for callers that imported the old module directly.
"""

from __future__ import annotations

from typing import Any

from agents.agent_harness.runtime_kernel import TurnRequest

from .ad_turn_pipeline import AdTurnPipeline


def execute(runtime: Any, **kwargs: Any) -> dict[str, Any]:
    context = dict(kwargs)
    request = TurnRequest(
        user_input=str(context.pop("user_input", "")),
        session_id=context.pop("session_id", None),
        run_id=context.pop("run_id", None),
        turn_id=context.pop("turn_id", None),
        user_id=str(context.pop("user_id", "anonymous")),
        tenant_id=str(context.pop("tenant_id", "default") or "default"),
        context=context,
    )
    return AdTurnPipeline(runtime).execute(request)


__all__ = ["execute"]
