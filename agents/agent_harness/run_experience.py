"""Bounded numeric experience metrics; no prompts, reasoning or Tool data retained."""

from collections import deque
from dataclasses import dataclass
import math
from threading import RLock
import time


@dataclass
class _Run:
    started: float
    first_progress_ms: float | None = None
    first_text_ms: float | None = None
    model_attempts: int = 0
    prompt_chars_peak: int = 0


class RunExperienceMetrics:
    def __init__(self, capacity: int = 256):
        if type(capacity) is not int or not 1 <= capacity <= 4096:
            raise ValueError("experience capacity must be between 1 and 4096")
        self.capacity = capacity
        self._lock = RLock()
        self._active = {}
        self._samples = {name: deque(maxlen=capacity) for name in (
            "first_progress_ms", "first_text_ms", "total_ms", "model_attempts", "prompt_chars_peak",
        )}
        self._dropped = 0

    def observe(self, event):
        run_id, kind = event.get("run_id"), event.get("type")
        if not isinstance(run_id, str) or not 1 <= len(run_id) <= 200:
            return
        now = time.monotonic()
        with self._lock:
            if kind == "agent_start" and run_id not in self._active:
                if len(self._active) >= self.capacity:
                    self._dropped += 1
                else:
                    self._active[run_id] = _Run(now)
            run = self._active.get(run_id)
            if run is not None:
                self._observe_run(run_id, run, kind, event, now)

    def _observe_run(self, run_id, run, kind, event, now):
        elapsed = round(max(0.0, (now - run.started) * 1000), 3)
        delta = event.get("delta")
        text = (kind == "model_delta" and isinstance(delta, str) and bool(delta.strip())) or (
            kind == "model_end" and event.get("has_content") is True
        )
        if text and run.first_text_ms is None:
            run.first_text_ms = elapsed
        if (text or kind == "tool_execution_start") and run.first_progress_ms is None:
            run.first_progress_ms = elapsed
        if kind == "model_start":
            run.model_attempts += 1
            chars = event.get("message_chars")
            if type(chars) is int and 0 <= chars <= 100_000_000:
                run.prompt_chars_peak = max(run.prompt_chars_peak, chars)
        if kind == "agent_end":
            self._active.pop(run_id)
            for name, bucket in self._samples.items():
                value = elapsed if name == "total_ms" else getattr(run, name)
                if value is not None:
                    bucket.append(value)

    def snapshot(self):
        with self._lock:
            return {
                "scope": "process_recent_completed_runs", "capacity": self.capacity,
                "clock_origin": "agent_start_excludes_queue_wait",
                "active_runs": len(self._active), "dropped_runs": self._dropped,
                **{name: self._percentiles(values) for name, values in self._samples.items()},
            }

    @staticmethod
    def _percentiles(values):
        values = sorted(values)
        return {"samples": len(values), **{
            f"p{percent}": values[math.ceil(len(values) * percent / 100) - 1] if values else None
            for percent in (50, 95)
        }}

    def reset(self):
        with self._lock:
            self._active.clear()
            self._dropped = 0
            for values in self._samples.values():
                values.clear()
