"""Small provider-neutral reliability primitives for Tool execution."""

from __future__ import annotations

import threading
import time
import math
from collections import OrderedDict
from dataclasses import dataclass

from .core.timeouts import DEFAULT_EXECUTION_TIMEOUT_SECONDS


@dataclass
class CircuitState:
    failures: int = 0
    opened_at: float = 0.0
    probe_started_at: float | None = None


class ToolCircuitBreaker:
    """Per-tool failure gate that prevents a broken dependency storm."""

    def __init__(
        self, failure_threshold: int = 5, reset_seconds: float = 30.0,
        *, max_entries: int = 4096,
        probe_timeout_seconds: float = DEFAULT_EXECUTION_TIMEOUT_SECONDS,
    ):
        if type(failure_threshold) is not int or failure_threshold <= 0:
            raise ValueError("failure_threshold must be positive")
        if (
            type(reset_seconds) not in (int, float)
            or not math.isfinite(reset_seconds) or reset_seconds <= 0
        ):
            raise ValueError("reset_seconds must be positive")
        if type(max_entries) is not int or max_entries <= 0:
            raise ValueError("max_entries must be positive")
        if (
            type(probe_timeout_seconds) not in (int, float)
            or not math.isfinite(probe_timeout_seconds) or probe_timeout_seconds <= 0
        ):
            raise ValueError("probe_timeout_seconds must be positive")
        self.failure_threshold = int(failure_threshold)
        self.reset_seconds = float(reset_seconds)
        self.max_entries = max_entries
        self.probe_timeout_seconds = float(probe_timeout_seconds)
        self._states: OrderedDict[str, CircuitState] = OrderedDict()
        self._lock = threading.RLock()

    def allow(self, key: str) -> bool:
        with self._lock:
            state = self._states.get(str(key))
            if state is None or state.failures < self.failure_threshold:
                return True
            now = time.monotonic()
            if state.probe_started_at is not None:
                if now - state.probe_started_at < self.probe_timeout_seconds:
                    return False
            elif now - state.opened_at < self.reset_seconds:
                return False
            state.probe_started_at = now
            self._states.move_to_end(str(key))
            return True

    def record_success(self, key: str) -> None:
        with self._lock:
            self._states.pop(str(key), None)

    def record_failure(self, key: str) -> None:
        with self._lock:
            normalized = str(key)
            if normalized not in self._states and len(self._states) >= self.max_entries:
                self._states.popitem(last=False)
            state = self._states.setdefault(normalized, CircuitState())
            self._states.move_to_end(normalized)
            state.failures += 1
            state.probe_started_at = None
            if state.failures >= self.failure_threshold:
                state.opened_at = time.monotonic()

    def abandon_probe(self, key: str) -> None:
        """Release a cancelled or unadmitted probe without counting a failure."""
        with self._lock:
            state = self._states.get(str(key))
            if state is not None and state.probe_started_at is not None:
                state.probe_started_at = None
                state.opened_at = time.monotonic()

    def snapshot(self) -> dict[str, dict[str, float | int]]:
        with self._lock:
            return {
                key: {
                    "failures": state.failures,
                    "opened_at": state.opened_at,
                    "recovering": state.probe_started_at is not None,
                }
                for key, state in self._states.items()
            }


__all__ = ["CircuitState", "ToolCircuitBreaker"]
