"""Capture safe, verified outcomes from live advertising write Runs."""

from __future__ import annotations

import logging
from typing import Any, Mapping, Sequence


logger = logging.getLogger(__name__)

_MEMORY_ERROR_CODES = frozenset({
    "AUTH_EXPIRED",
    "TIMEOUT",
    "RATE_LIMIT",
    "PROVIDER_RESULT_UNKNOWN",
    "PROVIDER_TEMPORARY_ERROR",
    "PROVIDER_5XX",
    "INVALID_REQUEST",
    "TOOL_EXECUTION_ERROR",
})


class AdvertisingRunMemoryRecorder:
    """Store only concise, allowlisted outcomes of non-simulated live writes."""

    def __init__(self, runtime: Any) -> None:
        self.runtime = runtime

    def capture(
        self,
        results: Sequence[Mapping[str, Any]],
        *,
        execution_mode: Any,
        run_id: str,
        session_id: str,
        user_id: str,
        tenant_id: str,
    ) -> None:
        manager = getattr(self.runtime, "_memory_manager", None)
        remember = getattr(manager, "remember_runtime_event", None)
        mode = str(getattr(execution_mode, "value", execution_mode) or "")
        if (
            not callable(remember)
            or mode.strip().lower() != "live"
            or not run_id
            or not session_id
        ):
            return
        for index, result in enumerate(results or ()):
            self._capture_one(
                remember,
                result,
                index=index,
                run_id=run_id,
                session_id=session_id,
                user_id=user_id,
                tenant_id=tenant_id,
            )

    def _capture_one(
        self,
        remember: Any,
        result: Mapping[str, Any],
        *,
        index: int,
        run_id: str,
        session_id: str,
        user_id: str,
        tenant_id: str,
    ) -> None:
        name = str(result.get("tool") or "").strip()
        if not name:
            return
        try:
            definition, _handler = self.runtime.registry.get(name)
        except (KeyError, AttributeError):
            return
        if not getattr(definition, "is_write_tool", False):
            return
        event = self._event_summary(definition, result)
        if event is None:
            return
        event_type, summary, outcome = event
        try:
            remember(
                summary,
                tenant_id=tenant_id,
                user_id=user_id,
                session_id=session_id,
                event_type=event_type,
                dedupe_key=f"{run_id}:{name}:{index}",
                outcome=outcome,
                tags=[f"tool:{name}", f"channel:{definition.namespace}"],
            )
        except Exception as error:
            logger.debug("runtime event memory write failed: %s", type(error).__name__)

    @staticmethod
    def _event_summary(
        definition: Any,
        result: Mapping[str, Any],
    ) -> tuple[str, str, str] | None:
        data = result.get("data")
        data = data if isinstance(data, Mapping) else {}
        if (
            result.get("simulated")
            or data.get("simulated")
            or str(data.get("mode") or "").strip().lower() == "dry_run"
            or result.get("requires_confirmation")
            or result.get("needs_confirmation")
            or result.get("needs_input")
        ):
            return None
        name = str(definition.name)
        namespace = str(definition.namespace)
        if result.get("success"):
            return (
                "operation_succeeded",
                f"Live write succeeded: {name} on {namespace}.",
                "succeeded",
            )
        detail = result.get("error_detail")
        code = str(detail.get("code") or "") if isinstance(detail, Mapping) else ""
        if code not in _MEMORY_ERROR_CODES:
            return None
        return (
            "operation_failed",
            f"Live write failed: {name} on {namespace}; code={code}.",
            code,
        )


__all__ = ["AdvertisingRunMemoryRecorder"]
