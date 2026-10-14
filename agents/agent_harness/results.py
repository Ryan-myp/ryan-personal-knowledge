"""Stable result envelope for application-specific Agent Runs."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Optional


class RunStatus(str, Enum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    AWAITING_INPUT = "awaiting_input"
    RECOVERY_REQUIRED = "recovery_required"
    CANCELLED = "cancelled"
    PARTIALLY_FAILED = "partially_failed"


def _tool_succeeded(row: Mapping[str, Any]) -> bool:
    content = row.get("result", row.get("content", row))
    content = content if isinstance(content, Mapping) else {}
    return not (row.get("is_error") or content.get("success") is False)


def tool_outcome_status(results: Any) -> RunStatus:
    """Summarize execution evidence, excluding prompts and coalesced repeats."""
    rows = [row for row in results or () if isinstance(row, Mapping)]
    successful_names = {
        row.get("name") for row in rows if _tool_succeeded(row)
    }
    outcomes = []
    for row in rows:
        content = row.get("result", row.get("content", row))
        content = content if isinstance(content, Mapping) else {}
        signals = row.get("runtime_signals") or {}
        if any(row.get(key) or content.get(key) for key in (
            "needs_input", "needs_confirmation", "skipped",
        )):
            continue
        if isinstance(signals, Mapping) and any(signals.get(key) for key in (
            "duplicate_read_coalesced", "duplicate_write_coalesced",
        )):
            continue
        if (
            isinstance(signals, Mapping)
            and signals.get("tool_input_repairable")
            and row.get("name") in successful_names
        ):
            continue
        outcomes.append(_tool_succeeded(row))
    failures = outcomes.count(False)
    if failures and any(outcomes):
        return RunStatus.PARTIALLY_FAILED
    return RunStatus.FAILED if failures else RunStatus.SUCCEEDED


@dataclass(frozen=True)
class RunResult:
    """Common Run outcome while preserving application payload in ``data``."""

    run_id: str = ""
    turn_id: str = ""
    status: RunStatus = RunStatus.SUCCEEDED
    reply: str = ""
    needs_input: bool = False
    effect_state: str = "none"
    recovery_required: bool = False
    runtime_signals: Mapping[str, Any] = field(default_factory=dict)
    data: Mapping[str, Any] = field(default_factory=dict)
    application_data: Mapping[str, Any] = field(default_factory=dict)
    interactions: tuple[Mapping[str, Any], ...] = ()

    @classmethod
    def from_payload(cls, payload: Any) -> "RunResult":
        if isinstance(payload, RunResult):
            return payload
        if not isinstance(payload, Mapping):
            return cls(data={"value": payload})

        source = dict(payload)
        signals = source.get("runtime_signals")
        signals = signals if isinstance(signals, Mapping) else {}
        status_value = str(source.get("status") or "").strip().lower()
        recovery = bool(
            source.get("recovery_required")
            or signals.get("session_lease_lost")
            or signals.get("task_lease_lost")
            or signals.get("run_store_error")
            or signals.get("audit_error")
            or source.get("effect_state") in {"unknown", "recovery_required"}
        )
        needs_input = bool(
            source.get("needs_input") or source.get("needs_confirmation")
        )
        interactions = tuple(
            dict(item)
            for item in (source.get("interactions") or ())
            if isinstance(item, Mapping)
        )
        if recovery:
            status = RunStatus.RECOVERY_REQUIRED
        elif needs_input:
            status = RunStatus.AWAITING_INPUT
        elif status_value in {
            item.value for item in RunStatus if item != RunStatus.SUCCEEDED
        }:
            status = RunStatus(status_value)
        elif (
            source.get("success") is False
            or bool(source.get("policy_errors"))
            or bool(source.get("error"))
        ):
            status = RunStatus.FAILED
        else:
            status = tool_outcome_status(
                source.get("results") or source.get("tool_results") or (),
            )

        return cls(
            run_id=str(source.get("run_id") or ""),
            turn_id=str(source.get("turn_id") or ""),
            status=status,
            reply=str(source.get("reply") or ""),
            needs_input=needs_input,
            effect_state=str(source.get("effect_state") or "none"),
            recovery_required=recovery,
            runtime_signals=dict(signals),
            data=source,
            interactions=interactions,
        )

    def to_dict(self) -> dict[str, Any]:
        result = dict(self.data)
        result.update({
            "run_id": self.run_id,
            "turn_id": self.turn_id,
            "status": self.status.value,
            "reply": self.reply,
            "needs_input": self.needs_input,
            "effect_state": self.effect_state,
            "recovery_required": self.recovery_required,
            "runtime_signals": dict(self.runtime_signals),
            "interactions": [dict(item) for item in self.interactions],
        })
        return result


__all__ = ["RunResult", "RunStatus"]
