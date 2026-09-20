"""Advertising application's adapter to the generic TurnPipeline contract.

The generic Runtime owns the public ``run`` lifecycle.  This adapter is the
only advertising-specific bridge left between that lifecycle and the current
advertising turn implementation; it can be replaced incrementally by
advertising-owned pipeline stages without changing Core.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..core.runtime_kernel import TurnRequest


class AdTurnPipeline:
    """Adapt the legacy advertising turn services to the generic pipeline."""

    def __init__(self, runtime: Any):
        self.runtime = runtime

    def execute(self, request: TurnRequest) -> dict[str, Any]:
        runtime = self.runtime
        request_context = (
            request.context if isinstance(request.context, Mapping) else {}
        )
        principal = request.principal
        permissions = (
            principal.permissions
            if principal is not None else runtime._granted_permissions
        )
        account_scope = principal.account_scope if principal is not None else None
        result = runtime._run_unlocked(
            user_input=request.user_input,
            session_id=request.session_id,
            run_id=request.run_id,
            turn_id=request.turn_id,
            user_id=request.user_id,
            account_id=request_context.get("account_id"),
            credentials=request_context.get("credentials"),
            platform_params=request_context.get("platform_params"),
            confirmed=bool(request_context.get("confirmed", False)),
            confirmation_payload=request_context.get("confirmation_payload"),
            creation_blueprint_id=request_context.get("creation_blueprint_id"),
            creation_blueprint_version=request_context.get("creation_blueprint_version"),
            granted_permissions=permissions,
            account_scope=account_scope,
            tenant_id=request.tenant_id,
            cancellation_event=request.cancellation_event,
            lease_lost_event=request.lease_lost_event,
            event_callback=request.event_callback,
            task_id=request.task_id,
        )
        if request.lease_lost_event is not None and request.lease_lost_event.is_set():
            # The application run may already have crossed an external side
            # effect boundary. Preserve the result, but mark it uncertain so
            # recovery can reconcile instead of retrying blindly.
            signals = (
                dict(result.get("runtime_signals") or {})
                if isinstance(result, dict) else {}
            )
            signals["session_lease_lost"] = True
            if isinstance(result, dict):
                result["runtime_signals"] = signals
                run_id = result.get("run_id")
                updater = getattr(
                    runtime._session_manager, "update_execution_run", None
                )
                if run_id and callable(updater):
                    updater(
                        str(run_id),
                        status="recovery_required",
                        metadata={
                            "effect_state": "unknown",
                            "session_lease_lost": True,
                        },
                    )
        return result


__all__ = ["AdTurnPipeline"]
