"""Small provider-neutral reliability primitives for Tool execution."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass


@dataclass
class CircuitState:
    failures: int = 0
    opened_at: float = 0.0


class ToolCircuitBreaker:
    """Per-tool failure gate that prevents a broken dependency storm."""

    def __init__(self, failure_threshold: int = 5, reset_seconds: float = 30.0):
        if failure_threshold <= 0:
            raise ValueError("failure_threshold must be positive")
        if reset_seconds <= 0:
            raise ValueError("reset_seconds must be positive")
        self.failure_threshold = int(failure_threshold)
        self.reset_seconds = float(reset_seconds)
        self._states: dict[str, CircuitState] = {}
        self._lock = threading.RLock()

    def allow(self, key: str) -> bool:
        with self._lock:
            state = self._states.get(str(key))
            if state is None or not state.opened_at:
                return True
            if time.monotonic() - state.opened_at >= self.reset_seconds:
                state.opened_at = 0.0
                state.failures = 0
                return True
            return False

    def record_success(self, key: str) -> None:
        with self._lock:
            self._states.pop(str(key), None)

    def record_failure(self, key: str) -> None:
        with self._lock:
            normalized = str(key)
            state = self._states.setdefault(normalized, CircuitState())
            state.failures += 1
            if state.failures >= self.failure_threshold:
                state.opened_at = time.monotonic()

    def snapshot(self) -> dict[str, dict[str, float | int]]:
        with self._lock:
            return {
                key: {
                    "failures": state.failures,
                    "opened_at": state.opened_at,
                }
                for key, state in self._states.items()
            }


__all__ = ["CircuitState", "ToolCircuitBreaker"]
