"""Evidence-based terminal outcomes for trusted background task handlers."""

from __future__ import annotations

from typing import Any, Mapping

from agents.agent_harness.results import RunResult, RunStatus

TASK_OUTCOME_STATUSES = frozenset(status.value for status in RunStatus)
_FLAGS = (
    "success", "is_error", "needs_input", "needs_confirmation",
    "requires_confirmation", "recovery_required", "cancelled",
)


class TaskOutcomeContractError(ValueError):
    def __init__(self) -> None:
        super().__init__("task outcome control fields are invalid")


def _validate_control_fields(value: Mapping[str, Any]) -> None:
    for name in _FLAGS:
        if name in value and type(value[name]) is not bool:
            raise TaskOutcomeContractError()
    for name in ("status", "task_status"):
        if name in value and (
            not isinstance(value[name], str)
            or value[name] not in TASK_OUTCOME_STATUSES
        ):
            raise TaskOutcomeContractError()
    if "effect_state" in value and not isinstance(value["effect_state"], str):
        raise TaskOutcomeContractError()
    if "runtime_signals" in value:
        signals = value["runtime_signals"]
        if not isinstance(signals, Mapping):
            raise TaskOutcomeContractError()
        for name in ("session_lease_lost", "task_lease_lost"):
            if name in signals and type(signals[name]) is not bool:
                raise TaskOutcomeContractError()


def _own_status(value: Mapping[str, Any]) -> str:
    signals = value.get("runtime_signals") or {}
    statuses = {value.get("status"), value.get("task_status")}
    if (
        value.get("recovery_required") is True
        or value.get("effect_state") in {"unknown", "recovery_required"}
        or signals.get("session_lease_lost") is True
        or signals.get("task_lease_lost") is True
        or "recovery_required" in statuses
    ):
        return "recovery_required"
    if (
        value.get("error") or "failed" in statuses
    ):
        return "failed"
    if "partially_failed" in statuses:
        return "partially_failed"
    if value.get("cancelled") is True or "cancelled" in statuses:
        return "cancelled"
    if any(value.get(key) is True for key in (
        "needs_input", "needs_confirmation", "requires_confirmation",
    )) or "awaiting_input" in statuses:
        return "awaiting_input"
    if value.get("success") is False or value.get("is_error") is True:
        return "failed"
    return "succeeded"


def task_outcome_status(result: Any) -> str:
    """Opaque results mean handler completion, never an external API attestation."""
    if isinstance(result, RunResult):
        result = result.to_dict()
    if not isinstance(result, Mapping):
        return "succeeded"
    _validate_control_fields(result)
    own_status = _own_status(result)
    children = []
    for name in ("results", "tool_results"):
        rows = result.get(name, [])
        if not isinstance(rows, list):
            raise TaskOutcomeContractError()
        for row in rows:
            if not isinstance(row, Mapping):
                raise TaskOutcomeContractError()
            _validate_control_fields(row)
            children.append(_own_status(row))
    if own_status == "recovery_required" or "recovery_required" in children:
        return "recovery_required"
    if own_status in {"failed", "partially_failed"}:
        return own_status
    if "failed" in children or "partially_failed" in children:
        return "partially_failed" if "succeeded" in children else "failed"
    if own_status == "cancelled" or "cancelled" in children:
        return "cancelled"
    if own_status == "awaiting_input" or "awaiting_input" in children:
        return "awaiting_input"
    return "succeeded"
