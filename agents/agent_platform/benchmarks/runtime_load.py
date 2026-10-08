"""Measured offline concurrency baseline for the generic Agent Run path."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import statistics
import time
from typing import Any

from agents.agent_harness import AgentApplication, RunResult, TurnRequest


def _percentile(values: list[float], percentage: int) -> float:
    ordered = sorted(values)
    rank = max(0, min(len(ordered) - 1, (len(ordered) * percentage + 99) // 100 - 1))
    return round(ordered[rank], 3)


def run_load(
    *, iterations: int = 100, concurrency: int = 8,
    model_delay_seconds: float = 0.001,
) -> dict[str, Any]:
    """Measure real Run scheduling overhead without model or Provider network."""
    if not 1 <= iterations <= 10_000:
        raise ValueError("iterations must be between 1 and 10000")
    if not 1 <= concurrency <= 128:
        raise ValueError("concurrency must be between 1 and 128")
    if not 0 <= model_delay_seconds <= 1:
        raise ValueError("model_delay_seconds must be between 0 and 1")

    def model(_messages: Any, _tools: Any, _request: Any) -> str:
        if model_delay_seconds:
            time.sleep(model_delay_seconds)
        return "ok"

    application = AgentApplication.create(model=model)

    def one_run(index: int) -> tuple[float, bool]:
        started = time.perf_counter()
        result = application.runtime.run(TurnRequest(
            user_input="status",
            session_id=f"load-session-{index}",
        ))
        elapsed_ms = (time.perf_counter() - started) * 1000
        normalized = RunResult.from_payload(result)
        return elapsed_ms, normalized.status.value == "succeeded"

    started = time.perf_counter()
    try:
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            samples = list(pool.map(one_run, range(iterations)))
    finally:
        application.close()
    wall_seconds = max(time.perf_counter() - started, 1e-9)
    latencies = [elapsed for elapsed, _success in samples]
    failures = sum(not success for _elapsed, success in samples)
    return {
        "scope": "offline_generic_run",
        "iterations": iterations,
        "concurrency": concurrency,
        "model_delay_seconds": model_delay_seconds,
        "completed": len(samples),
        "failed": failures,
        "latency_ms": {
            "p50": _percentile(latencies, 50),
            "p95": _percentile(latencies, 95),
            "max": round(max(latencies), 3),
            "mean": round(statistics.mean(latencies), 3),
        },
        "wall_seconds": round(wall_seconds, 3),
        "throughput_runs_per_second": round(len(samples) / wall_seconds, 3),
        "provider_calls": 0,
        "production_capacity_attested": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=int, default=100)
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--model-delay-seconds", type=float, default=0.001)
    args = parser.parse_args()
    report = run_load(
        iterations=args.iterations,
        concurrency=args.concurrency,
        model_delay_seconds=args.model_delay_seconds,
    )
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
