"""Summarize measured, read-only test-account Provider Tool latency."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

from agents.tools.advertising.shared.domain.provider_evidence import validate_provider_evidence


def _percentile(values: list[float], percentage: int) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, (len(ordered) * percentage + 99) // 100 - 1))
    return round(ordered[index], 3)


def summarize_evidence(raw: Mapping[str, Any]) -> dict[str, Any]:
    if raw.get("scope") != "provider_query_e2e":
        raise ValueError("read-only query evidence is required")
    errors = validate_provider_evidence(raw)
    if errors:
        raise ValueError(f"provider query evidence is invalid ({len(errors)} errors)")
    providers: dict[str, dict[str, Any]] = {}
    for run in raw.get("runs", []):
        name = str(run["provider"])
        queries = run["queries"]
        measured = [
            float(item["latency_ms"])
            for item in queries
            if item["outcome"] == "passed" and "latency_ms" in item
        ]
        providers[name] = {
            "passed": sum(item["outcome"] == "passed" for item in queries),
            "failed": sum(item["outcome"] == "failed" for item in queries),
            "skipped": sum(item["outcome"] == "skipped" for item in queries),
            "measured": len(measured),
            "p50_ms": _percentile(measured, 50),
            "p95_ms": _percentile(measured, 95),
            "max_ms": round(max(measured), 3) if measured else None,
        }
    return {
        "scope": "read_only_test_account_provider_queries",
        "generated_at": raw.get("generated_at"),
        "providers": providers,
        "production_capacity_attested": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence", type=Path)
    args = parser.parse_args()
    raw = json.loads(args.evidence.read_text(encoding="utf-8"))
    print(json.dumps(summarize_evidence(raw), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
