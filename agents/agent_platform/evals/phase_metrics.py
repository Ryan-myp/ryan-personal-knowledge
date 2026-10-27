"""Bounded numeric-only wall and Tool timing from existing Run events."""

from __future__ import annotations

import time
from threading import Lock
from typing import Any, Mapping


class PhaseMetrics:
    def __init__(self, *, max_calls: int = 128) -> None:
        if not 1 <= max_calls <= 1024:
            raise ValueError("max_calls must be between 1 and 1024")
        self._limit = max_calls
        self._lock = Lock()
        self._runs: dict[str, float] = {}
        self._calls: dict[tuple[str, str], float] = {}
        self._run_ms = 0.0
        self._tool_ms = 0.0
        self._completed_runs = 0
        self._completed_calls = 0
        self._truncated = False

    def __call__(self, event: Mapping[str, Any]) -> None:
        kind = event.get("type")
        run = event.get("run_id")
        if not isinstance(run, str) or not 1 <= len(run) <= 200:
            return
        now = time.monotonic()
        with self._lock:
            if kind == "agent_start":
                if run in self._runs:
                    return
                if len(self._runs) >= self._limit:
                    self._truncated = True
                else:
                    self._runs[run] = now
            elif kind == "agent_end":
                started = self._runs.pop(run, None)
                if started is not None:
                    self._run_ms += max(0.0, (now - started) * 1000)
                    self._completed_runs += 1
            elif kind in {"tool_execution_start", "tool_execution_end"}:
                call = event.get("tool_call_id")
                if not isinstance(call, str) or not 1 <= len(call) <= 200:
                    return
                key = (run, call)
                if kind == "tool_execution_start":
                    if key in self._calls:
                        return
                    if len(self._calls) >= self._limit:
                        self._truncated = True
                    else:
                        self._calls[key] = now
                else:
                    started = self._calls.pop(key, None)
                    if started is not None:
                        self._tool_ms += max(0.0, (now - started) * 1000)
                        self._completed_calls += 1

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "runs": self._completed_runs,
                "incomplete_runs": len(self._runs),
                "tool_calls": self._completed_calls,
                "incomplete_tool_calls": len(self._calls),
                "run_wall_ms": round(self._run_ms, 3),
                "tool_duration_ms_sum": round(self._tool_ms, 3),
                "truncated": self._truncated,
            }
