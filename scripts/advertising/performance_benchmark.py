#!/usr/bin/env python3.13
"""Bounded, no-network Harness benchmark for local regression checks.

This is intentionally a smoke benchmark, not a production capacity claim.
It injects a fixed, trusted ModelAdapter turn to measure Harness lifecycle and
Tool execution overhead. It does not benchmark model latency or parse prompts.
It never loads credentials and never calls a Provider.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.evals.advertising.skill_up_engine import run as run_case  # noqa: E402
from agents.agent_harness.messages import ModelTurn, ToolCall  # noqa: E402


class _BenchmarkModel:
    """Issue one fixed read call; this is a benchmark fixture, not an LLM."""

    def __init__(self) -> None:
        self._turn = 0

    def complete(self, _messages, tools, _request):
        self._turn += 1
        if self._turn == 1:
            available = {getattr(tool, "name", "") for tool in tools}
            if "tiktok_list_apps" not in available:
                raise RuntimeError("benchmark Tool is missing from the catalog")
            return ModelTurn(tool_calls=(ToolCall(
                "benchmark-apps-query",
                "tiktok_list_apps",
                {"account_id": "7397068114548195329"},
            ),))
        return ModelTurn(content="Benchmark fixture completed one app lookup.")


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((percentile / 100) * (len(ordered) - 1)))))
    return ordered[index]


def bounded_iterations(value: int) -> int:
    return max(1, min(int(value), 100))


def run_benchmark(iterations: int = 10) -> dict:
    iterations = bounded_iterations(iterations)
    durations: list[float] = []
    failures = 0
    max_tool_calls = 0
    prompt = "查询 TikTok 可用应用列表"
    started = time.monotonic()
    for index in range(iterations):
        case_started = time.monotonic()
        result = run_case({
            "case_id": f"benchmark-{index}",
            "workspace": "/tmp/ad-agent-benchmark",
            "messages": [{"role": "user", "content": prompt}],
        }, model_adapter=_BenchmarkModel())
        durations.append((time.monotonic() - case_started) * 1000)
        if result.get("exit_code") != 0:
            failures += 1
        evidence = (result.get("metadata") or {}).get("runtime_result") or {}
        plan = evidence.get("tool_plan") or {}
        max_tool_calls = max(
            max_tool_calls,
            sum(len(values) for values in plan.values() if isinstance(values, list)),
        )
    total_ms = (time.monotonic() - started) * 1000
    return {
        "format_version": 1,
        "iterations": iterations,
        "prompt_class": "offline_lookup",
        "model_adapter": "trusted scripted benchmark fixture",
        "latency_ms": {
            "p50": round(_percentile(durations, 50), 2),
            "p95": round(_percentile(durations, 95), 2),
            "min": round(min(durations), 2),
            "max": round(max(durations), 2),
            "mean": round(statistics.mean(durations), 2),
        },
        "failed_iterations": failures,
        "max_observed_tool_calls": max_tool_calls,
        "configured_tool_call_limit": 32,
        "total_ms": round(total_ms, 2),
        "provider_calls": 0,
        "network_called": False,
        "note": "Harness smoke benchmark only; excludes model latency and Provider capacity",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=int, default=10)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    report = run_benchmark(args.iterations)
    encoded = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    else:
        print(encoded, end="")
    return 0 if report["failed_iterations"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
