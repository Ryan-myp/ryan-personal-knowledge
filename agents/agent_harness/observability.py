"""Small, application-neutral metrics sink for Agent Runs.

Metrics are derived from lifecycle events only. The collector never stores
prompts, Tool arguments, Tool results, exceptions, or credentials.
"""

from __future__ import annotations

from collections import Counter
import threading
import time
from dataclasses import dataclass
from typing import Any, Mapping, Protocol


class MetricsSink(Protocol):
    """Observer contract for bounded, non-sensitive Run metrics."""

    def observe(self, event: Mapping[str, Any]) -> None:
        ...


class TraceSink(Protocol):
    """Application-neutral trace export port."""

    def emit(self, event: Mapping[str, Any]) -> None:
        ...


class AlertSink(Protocol):
    """Application-neutral operational alert port."""

    def publish(self, alert: Mapping[str, Any]) -> None:
        ...


class CredentialProvider(Protocol):
    """Resolve deployment-owned credentials without exposing their values."""

    def healthcheck(self) -> Mapping[str, Any]:
        ...

    def resolve(self, reference: str) -> Mapping[str, Any]:
        ...


class QuotaProvider(Protocol):
    """Expose provider-neutral quota/rate-limit state."""

    def snapshot(self) -> Mapping[str, Any]:
        ...


@dataclass(frozen=True)
class HealthCheck:
    """One bounded deployment health result."""

    name: str
    status: str
    required: bool = True
    details: Mapping[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": str(self.status or "unknown"),
            "required": bool(self.required),
            "details": dict(self.details or {}),
        }


@dataclass(frozen=True)
class DeploymentHealth:
    """Common readiness shape shared by local and production deployments."""

    ready: bool
    status: str
    checks: Mapping[str, HealthCheck]
    blocking_checks: tuple[str, ...] = ()

    @classmethod
    def from_checks(cls, checks: list[HealthCheck] | tuple[HealthCheck, ...]) -> "DeploymentHealth":
        normalized = {
            str(item.name): item
            for item in checks
            if str(item.name).strip()
        }
        blocking = tuple(sorted(
            name
            for name, item in normalized.items()
            if item.required and str(item.status).lower()
            not in {"healthy", "ready", "ok", "configured", "disabled"}
        ))
        ready = not blocking
        return cls(
            ready=ready,
            status="ready" if ready else "not_ready",
            checks=normalized,
            blocking_checks=blocking,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "ready": self.ready,
            "status": self.status,
            "blocking_checks": list(self.blocking_checks),
            "checks": {
                name: check.to_dict()
                for name, check in sorted(self.checks.items())
            },
        }


class InMemoryMetrics:
    """Thread-safe lifecycle metrics suitable for tests and local monitoring."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._counters: Counter[str] = Counter()
        self._durations: dict[str, dict[str, float]] = {}
        self._started: dict[tuple[str, str], float] = {}

    def observe(self, event: Mapping[str, Any]) -> None:
        event_type = str(event.get("type") or event.get("event_type") or "").strip()
        if not event_type:
            return
        run_id = str(event.get("run_id") or "")
        tool_name = str(event.get("tool_name") or "")
        now = time.monotonic()
        with self._lock:
            self._counters["events_total"] += 1
            self._counters[f"events.{event_type}"] += 1
            if event_type in {"agent_start", "start"}:
                self._counters["runs_started"] += 1
                if run_id:
                    self._started[("run", run_id)] = now
            elif event_type in {"agent_end", "done"}:
                status = str(event.get("status") or "unknown")
                if status == "awaiting_confirmation":
                    status = "awaiting_input"
                self._counters[f"runs_finished.{status}"] += 1
                self._finish_duration("run", run_id, now)
            elif event_type == "tool_execution_start":
                self._counters["tool_calls_started"] += 1
                self._started[("tool", f"{run_id}:{tool_name}")] = now
            elif event_type == "tool_execution_end":
                self._counters["tool_calls_finished"] += 1
                if bool(event.get("is_error")):
                    self._counters["tool_calls_failed"] += 1
                self._finish_duration("tool", f"{run_id}:{tool_name}", now)

    def _finish_duration(self, kind: str, key: str, now: float) -> None:
        started = self._started.pop((kind, key), None)
        if started is None:
            return
        elapsed_ms = max((now - started) * 1000.0, 0.0)
        bucket = self._durations.setdefault(
            f"{kind}_duration",
            {"count": 0.0, "total_ms": 0.0, "max_ms": 0.0},
        )
        bucket["count"] += 1.0
        bucket["total_ms"] += elapsed_ms
        bucket["max_ms"] = max(bucket["max_ms"], elapsed_ms)

    def snapshot(self) -> dict[str, Any]:
        """Return a safe, JSON-compatible snapshot."""
        with self._lock:
            durations = {}
            for name, value in self._durations.items():
                count = value["count"]
                durations[name] = {
                    "count": int(count),
                    "total_ms": round(value["total_ms"], 2),
                    "max_ms": round(value["max_ms"], 2),
                    "avg_ms": round(value["total_ms"] / count, 2)
                    if count else None,
                }
            return {
                "version": 1,
                "counters": dict(sorted(self._counters.items())),
                "durations": durations,
                "in_flight": len(self._started),
            }

    def reset(self) -> None:
        with self._lock:
            self._counters.clear()
            self._durations.clear()
            self._started.clear()


__all__ = [
    "AlertSink",
    "CredentialProvider",
    "DeploymentHealth",
    "HealthCheck",
    "InMemoryMetrics",
    "MetricsSink",
    "QuotaProvider",
    "TraceSink",
]
