"""Run fixed conversation assertions; only explicit model mode calls an LLM."""

from __future__ import annotations

import argparse
from itertools import product
from dataclasses import dataclass
from functools import partial
import json
import math
from pathlib import Path
import re
import sys
import tempfile
import time
from typing import Any, Callable, Mapping

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pydantic import BaseModel, ConfigDict, Field, field_validator
from agents.agent_platform.evals.regression import RegressionAssertions, evaluate_regression
from agents.agent_platform.evals.execution_evidence import regression_calls, run_status_evidence
from agents.deployments.advertising.local_config import load_default_local_env
from agents.evals.advertising.skill_up_engine import configured_model_adapter


class RegressionCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=200, pattern=r"^[\w.:-]+$")
    input: str = Field(min_length=1, max_length=4000)
    history: list[str] = Field(default_factory=list, max_length=11)
    expected_behavior: str = Field(default="", max_length=2000)
    previous_output: str = Field(default="", max_length=4000)
    assertions: RegressionAssertions = Field(default_factory=RegressionAssertions)
    runnable: bool | None = None

    @field_validator("history")
    @classmethod
    def validate_history(cls, value: list[str]) -> list[str]:
        if sum(len(item) for item in value) > 30_000 or any(
            not item.strip() or len(item) > 4000 for item in value
        ):
            raise ValueError("history exceeds the bounded user-turn limit")
        return value


@dataclass(frozen=True)
class ReleaseGate:
    min_cases: int
    max_p95_ms: float

    def __post_init__(self) -> None:
        if type(self.min_cases) is not int or not 1 <= self.min_cases <= 100:
            raise ValueError("min_cases must be between 1 and 100")
        try:
            limit = float(self.max_p95_ms) if type(self.max_p95_ms) in (int, float) else -1
        except OverflowError:
            limit = -1
        if not math.isfinite(limit) or limit < 0:
            raise ValueError("max_p95_ms must be a non-negative finite number")


def _write_report(path: Path, rendered: str) -> None:
    """Replace a report atomically, retaining the previous file on failure."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent,
            prefix=f".{path.name}.", delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(rendered)
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


class RegressionProgressWriter:
    """Retain safe case evidence while a long suite is still in progress."""

    def __init__(self, output: Path | None, *, total: int, mode: str):
        self.output, self.total, self.mode = output, total, mode
        self.cases: list[dict[str, Any]] = []
        self._save()

    def _save(self) -> None:
        if self.output is not None:
            _write_report(self.output, json.dumps({
                "schema_version": "agent-regression-report/v1", "mode": self.mode,
                "provider_e2e": False, "complete": False, "total": self.total,
                "completed_cases": len(self.cases), "cases": self.cases,
                "gate_passed": False, "release_ready": False,
                "release_blockers": ["suite_incomplete"],
            }, ensure_ascii=False, indent=2) + "\n")

    def record(self, case: Mapping[str, Any]) -> None:
        self.cases.append(dict(case))
        self._save()
        print(
            f"评测 {len(self.cases)}/{self.total}: {case['id']} ({case['status']})",
            file=sys.stderr, flush=True,
        )


_SAFE_TOOL_NAME = re.compile(r"[A-Za-z][A-Za-z0-9_.:-]{0,119}\Z")
_PHASE_FIELDS = {
    "run_wall": ("phase_metrics", "run_wall_ms"),
    "tool_duration_sum": ("phase_metrics", "tool_duration_ms_sum"),
    "model": ("model_metrics", "duration_ms"),
    "model_prepare": ("model_metrics", "prepare_duration_ms"),
    "context_build": ("phase_metrics", "phase_duration_ms_sum.context_build"),
    "run_event_persistence": (
        "phase_metrics", "phase_duration_ms_sum.run_event_persistence",
    ),
}


def _safe_phase_timings(response: Mapping[str, Any]) -> dict[str, float]:
    timings = {}
    for label, (group, key) in _PHASE_FIELDS.items():
        source = response.get(group)
        value = source
        for segment in key.split("."):
            value = value.get(segment) if isinstance(value, Mapping) else None
        if type(value) not in (int, float):
            continue
        try:
            duration = float(value)
        except OverflowError:
            continue
        if math.isfinite(duration) and 0 <= duration <= 1_000_000_000:
            timings[label] = round(duration, 3)
    return timings


def load_cases(path: Path) -> list[RegressionCase]:
    if path.stat().st_size > 1_048_576:
        raise ValueError("regression dataset exceeds 1 MiB")
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw = payload.get("cases") if isinstance(payload, dict) else payload
    if not isinstance(raw, list) or not 1 <= len(raw) <= 100:
        raise ValueError("regression dataset requires 1 to 100 cases")
    cases = [RegressionCase.model_validate(case) for case in raw]
    if len({case.id for case in cases}) != len(cases):
        raise ValueError("regression case IDs must be unique")
    return cases


def run_suite(
    cases: list[RegressionCase],
    execute: Callable[[RegressionCase], Mapping[str, Any]],
    *,
    mode: str,
    release_gate: ReleaseGate | None = None,
    on_case_complete: Callable[[Mapping[str, Any]], None] | None = None,
    repeats: int = 1,
) -> dict[str, Any]:
    if type(repeats) is not int or not 1 <= repeats <= 5:
        raise ValueError("repeats must be between 1 and 5")
    results = []
    for attempt, case in product(range(1, repeats + 1), cases):
        started = time.perf_counter()
        tool_names: list[str] = []
        tool_call_count = 0
        phase_ms: dict[str, float] = {}
        runtime_state: dict[str, Any] = {}
        execution_states: list[str] = []
        execution_evidence: list[dict[str, Any]] = []
        if not case.assertions.executable:
            result = {"status": "ungraded", "checks": 0, "failures": []}
        else:
            try:
                response = execute(case)
                phase_ms = _safe_phase_timings(response)
                calls = regression_calls(response)
                if "status" in response:
                    runtime_state["status"] = run_status_evidence(response["status"])
                runtime_state.update({
                    key: response[key] for key in ("needs_input", "needs_confirmation")
                    if type(response.get(key)) is bool
                })
                execution_states = [str(call.get("state") or "unknown") for call in calls]
                execution_evidence = [{
                    "tool": (
                        str(call.get("tool")) if _SAFE_TOOL_NAME.fullmatch(str(call.get("tool")))
                        else "<invalid>"
                    ),
                    **{
                        key: call[key] for key in ("success", "state", "argument_fingerprints")
                        if key in call
                    },
                } for call in calls]
                tool_call_count = len(calls)
                tool_names = [
                    name if _SAFE_TOOL_NAME.fullmatch(name) else "<invalid>"
                    for call in calls[:64]
                    if isinstance(call, Mapping)
                    for name in [str(call.get("tool") or "")]
                ]
                result = evaluate_regression(response, case.assertions)
            except (OSError, RuntimeError, ValueError, KeyError, TypeError) as error:
                result = {"status": "error", "checks": 0, "failures": [type(error).__name__]}
        results.append({
            "id": case.id, "attempt": attempt, **result,
            "tool_call_count": tool_call_count,
            "tool_names": tool_names,
            "phase_ms": phase_ms,
            "runtime_state": runtime_state, "execution_states": execution_states,
            "tool_execution_evidence": execution_evidence,
            "duration_ms": round((time.perf_counter() - started) * 1000, 3),
        })
        if on_case_complete is not None:
            on_case_complete(dict(results[-1]))
    totals = {
        status: sum(result["status"] == status for result in results)
        for status in ("passed", "failed", "ungraded", "error")
    }
    durations = sorted(
        result["duration_ms"] for result in results
        if result["status"] in {"passed", "failed"}
    )
    p95_ms = durations[math.ceil(len(durations) * 0.95) - 1] if durations else None
    blockers: list[str] = []
    if release_gate is not None:
        if mode != "model_backed_offline_providers":
            blockers.append("model_backed_required")
        graded_ids = {row["id"] for row in results if row["status"] in {"passed", "failed"}}
        if len(graded_ids) < release_gate.min_cases:
            blockers.append("insufficient_samples")
        if totals["passed"] != len(results):
            blockers.append("case_failures")
        if p95_ms is None or p95_ms > release_gate.max_p95_ms:
            blockers.append("latency_p95_exceeded")
    return {
        "schema_version": "agent-regression-report/v1", "mode": mode,
        "unique_cases": len(cases), "repeats": repeats,
        "complete": True, "completed_cases": len(results),
        "provider_e2e": False, "total": len(results), **totals, "cases": results,
        "gate_passed": totals["passed"] == len(results) and bool(results),
        "latency_samples": len(durations),
        "latency_p50_ms": durations[math.ceil(len(durations) * 0.5) - 1] if durations else None,
        "latency_p95_ms": p95_ms,
        "release_ready": release_gate is not None and not blockers,
        "release_blockers": blockers if release_gate is not None else ["release_gate_not_configured"],
        "phase_p95_ms": {
            label: (
                sorted(samples)[math.ceil(len(samples) * 0.95) - 1]
                if samples else None
            )
            for label in _PHASE_FIELDS
            for samples in [[
                case["phase_ms"][label] for case in results
                if case["status"] in {"passed", "failed"}
                and label in case["phase_ms"]
            ]]
        },
    }


def _model_response(
    case: RegressionCase, *, model_adapter: Any,
) -> Mapping[str, Any]:
    from agents.evals.advertising.skill_up_engine import run

    with tempfile.TemporaryDirectory(prefix="agent-regression-") as directory:
        result = run(
            {
                "case_id": case.id, "prompt": case.input, "workspace": directory,
                **({"messages": [
                    *({"role": "user", "content": text} for text in case.history),
                    {"role": "user", "content": case.input},
                ]} if case.history else {}),
            },
            model_adapter=model_adapter,
        )
    return result["metadata"]["runtime_result"]


def _suite_executor(args):
    if args.model_backed:
        load_default_local_env()
        adapter = configured_model_adapter()
        if adapter is None:
            raise RuntimeError("model evaluation is not configured")
        return partial(_model_response, model_adapter=adapter)
    if args.responses.stat().st_size > 4_194_304:
        raise ValueError("response evidence exceeds 4 MiB")
    responses = json.loads(args.responses.read_text(encoding="utf-8"))
    return lambda case: responses[case.id]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--model-backed", action="store_true")
    mode.add_argument("--responses", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--release-gate", action="store_true")
    parser.add_argument("--min-cases", type=int, default=6)
    parser.add_argument("--max-p95-ms", type=float)
    parser.add_argument("--repeats", type=int, choices=range(1, 6), default=1)
    args = parser.parse_args()
    if args.release_gate and (not args.model_backed or args.max_p95_ms is None):
        parser.error("--release-gate requires --model-backed and --max-p95-ms")
    release_gate = (
        ReleaseGate(args.min_cases, args.max_p95_ms)
        if args.release_gate else None
    )
    cases = load_cases(args.cases)
    progress = RegressionProgressWriter(
        args.output, total=len(cases) * args.repeats,
        mode="model_backed_offline_providers" if args.model_backed else "replay_assertions",
    )
    report = run_suite(
        cases, _suite_executor(args),
        mode="model_backed_offline_providers" if args.model_backed else "replay_assertions",
        release_gate=release_gate, on_case_complete=progress.record, repeats=args.repeats,
    )
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        _write_report(args.output, rendered + "\n")
    print(rendered)
    passed = report["release_ready"] if release_gate else report["gate_passed"]
    return 0 if passed else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError) as error:
        print(f"regression runner failed ({type(error).__name__})", file=sys.stderr)
        raise SystemExit(2) from None
