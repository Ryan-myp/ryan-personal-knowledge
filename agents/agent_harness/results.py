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
    data: Mapping[str, Any] = field(default_factory=dict)

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
            or source.get("effect_state") in {"unknown", "recovery_required"}
        )
        needs_input = bool(
            source.get("needs_input") or source.get("needs_confirmation")
        )
        if recovery:
            status = RunStatus.RECOVERY_REQUIRED
        elif needs_input:
            status = RunStatus.AWAITING_INPUT
        elif status_value in {item.value for item in RunStatus}:
            status = RunStatus(status_value)
        elif (
            source.get("success") is False
            or bool(source.get("policy_errors"))
            or bool(source.get("error"))
        ):
            status = RunStatus.FAILED
        else:
            results = [
                item for item in (source.get("results") or [])
                if isinstance(item, Mapping)
            ]
            failures = sum(item.get("success") is False for item in results)
            successes = sum(item.get("success") is True for item in results)
            if failures and successes:
                status = RunStatus.PARTIALLY_FAILED
            elif failures:
                status = RunStatus.FAILED
            else:
                status = RunStatus.SUCCEEDED

        return cls(
            run_id=str(source.get("run_id") or ""),
            turn_id=str(source.get("turn_id") or ""),
            status=status,
            reply=str(source.get("reply") or ""),
            needs_input=needs_input,
            effect_state=str(source.get("effect_state") or "none"),
            recovery_required=recovery,
            data=source,
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
        })
        return result


__all__ = ["RunResult", "RunStatus"]
