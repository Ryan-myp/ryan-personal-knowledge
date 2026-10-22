"""Run fixed conversation assertions; only explicit model mode calls an LLM."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import tempfile
import time
from typing import Any, Callable, Mapping

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pydantic import BaseModel, ConfigDict, Field
from agents.agent_platform.evals.regression import RegressionAssertions, evaluate_regression


class RegressionCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=200, pattern=r"^[\w.:-]+$")
    input: str = Field(min_length=1, max_length=4000)
    expected_behavior: str = Field(default="", max_length=2000)
    previous_output: str = Field(default="", max_length=4000)
    assertions: RegressionAssertions = Field(default_factory=RegressionAssertions)
    runnable: bool | None = None


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
) -> dict[str, Any]:
    results = []
    for case in cases:
        started = time.perf_counter()
        if not case.assertions.executable:
            result = {"status": "ungraded", "checks": 0, "failures": []}
        else:
            try:
                result = evaluate_regression(execute(case), case.assertions)
            except (OSError, RuntimeError, ValueError, KeyError, TypeError) as error:
                result = {"status": "error", "checks": 0, "failures": [type(error).__name__]}
        results.append({
            "id": case.id, **result,
            "duration_ms": round((time.perf_counter() - started) * 1000, 3),
        })
    totals = {
        status: sum(result["status"] == status for result in results)
        for status in ("passed", "failed", "ungraded", "error")
    }
    return {
        "schema_version": "agent-regression-report/v1", "mode": mode,
        "provider_e2e": False, "total": len(results), **totals, "cases": results,
        "gate_passed": totals["passed"] == len(results) and bool(results),
    }


def _model_response(case: RegressionCase) -> Mapping[str, Any]:
    from agents.evals.advertising.skill_up_engine import run

    with tempfile.TemporaryDirectory(prefix="agent-regression-") as directory:
        result = run({"case_id": case.id, "prompt": case.input, "workspace": directory})
    return result["metadata"]["runtime_result"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--model-backed", action="store_true")
    mode.add_argument("--responses", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    cases = load_cases(args.cases)
    if args.model_backed:
        report = run_suite(cases, _model_response, mode="model_backed_offline_providers")
    else:
        if args.responses.stat().st_size > 4_194_304:
            raise ValueError("response evidence exceeds 4 MiB")
        responses = json.loads(args.responses.read_text(encoding="utf-8"))
        report = run_suite(cases, lambda case: responses[case.id], mode="replay_assertions")
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if report["gate_passed"] else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError) as error:
        print(f"regression runner failed ({type(error).__name__})", file=sys.stderr)
        raise SystemExit(2) from None
