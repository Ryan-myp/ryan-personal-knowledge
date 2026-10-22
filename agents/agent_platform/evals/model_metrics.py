"""Numeric-only, bounded model-attempt diagnostics for controlled evaluations."""

import math
from threading import Lock
from typing import Any, Mapping


def _number(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0.0
    try:
        number = float(value)
    except OverflowError:
        return 0.0
    return number if math.isfinite(number) and number >= 0 else 0.0


class ModelMetrics:
    def __init__(self, *, max_attempts: int = 128) -> None:
        if not 1 <= max_attempts <= 1024:
            raise ValueError("max_attempts must be between 1 and 1024")
        self._limit = max_attempts
        self._lock = Lock()
        self._attempts: dict[str, dict[str, Any]] = {}
        self._truncated = False

    def __call__(self, event: Mapping[str, Any]) -> None:
        event_type = event.get("type")
        call_id = event.get("model_call_id")
        if not isinstance(call_id, str) or not call_id or len(call_id) > 200:
            return
        with self._lock:
            if event_type == "model_start":
                self._start(call_id, event)
            elif event_type in {"model_end", "model_error"}:
                row = self._attempts.get(call_id)
                if row is not None and row["status"] == "running":
                    row["status"] = "completed" if event_type == "model_end" else "failed"
                    row["duration_ms"] = _number(event.get("duration_ms"))

    def _start(self, call_id: str, event: Mapping[str, Any]) -> None:
        if call_id in self._attempts:
            return
        if len(self._attempts) >= self._limit:
            self._truncated = True
            return
        self._attempts[call_id] = {
            "status": "running", "duration_ms": 0.0,
            **{key: _number(event.get(key)) for key in (
                "message_chars", "message_count", "tool_count", "prepare_duration_ms",
            )},
        }

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            rows = list(self._attempts.values())
            return {
                "attempts": len(rows),
                "completed": sum(row["status"] == "completed" for row in rows),
                "failed": sum(row["status"] == "failed" for row in rows),
                "incomplete": sum(row["status"] == "running" for row in rows),
                "duration_ms": round(sum(row["duration_ms"] for row in rows), 3),
                "prepare_duration_ms": round(sum(row["prepare_duration_ms"] for row in rows), 3),
                "message_chars_total": int(sum(row["message_chars"] for row in rows)),
                "message_chars_peak": int(max((row["message_chars"] for row in rows), default=0)),
                "tool_count_peak": int(max((row["tool_count"] for row in rows), default=0)),
                "truncated": self._truncated,
            }
