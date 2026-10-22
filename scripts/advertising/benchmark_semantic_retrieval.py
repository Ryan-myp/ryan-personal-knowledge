"""Bounded local vector-cache benchmark, not Provider or model quality evidence."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.agent_platform.data.persistent_semantic_index import PersistentSemanticIndex
from agents.applications.advertising.persistence.store import AdAgentStore


def benchmark(*, records: int = 2000, dimensions: int = 64, repetitions: int = 20) -> dict:
    if not 1 <= records <= 10_000 or not 2 <= dimensions <= 128:
        raise ValueError("benchmark corpus exceeds local bounds")
    if not 1 <= repetitions <= 100:
        raise ValueError("benchmark repetitions must be between 1 and 100")
    corpus = [
        {"chunk_id": f"chunk-{index:06d}", "document_id": f"doc-{index:06d}",
         "vector": [float(column == index % dimensions) for column in range(dimensions)]}
        for index in range(records)
    ]
    query = [1.0] + [0.0] * (dimensions - 1)
    store = AdAgentStore(":memory:")
    try:
        store.rebuild_knowledge_semantic_index(corpus, scope="benchmark", fingerprint="v1")
        index = PersistentSemanticIndex(store)
        started = time.perf_counter()
        first = index.search(query, scope="benchmark", limit=10)
        cold_ms = (time.perf_counter() - started) * 1000
        elapsed = []
        for _ in range(repetitions):
            started = time.perf_counter()
            index.search(query, scope="benchmark", limit=10)
            elapsed.append((time.perf_counter() - started) * 1000)
        restarted = PersistentSemanticIndex(store)
        same = first == restarted.search(query, scope="benchmark", limit=10)
        return {
            "mode": "local_synthetic_vectors", "provider_calls": 0,
            "records": records, "dimensions": dimensions, "queries": repetitions,
            "cold_ms": round(cold_ms, 3),
            "warm_p50_ms": round(sorted(elapsed)[math.ceil(repetitions * 0.5) - 1], 3),
            "warm_p95_ms": round(sorted(elapsed)[math.ceil(repetitions * 0.95) - 1], 3),
            "rank_consistent_after_restart": same, "index_metrics": index.metrics(),
            "algorithm": "exact_cosine_cached_snapshot_not_ann",
        }
    finally:
        store.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--max-p95-ms", type=float, default=500.0)
    args = parser.parse_args()
    if not math.isfinite(args.max_p95_ms) or args.max_p95_ms <= 0:
        raise ValueError("p95 latency budget must be positive and finite")
    report = benchmark()
    report["gate_passed"] = bool(
        report["rank_consistent_after_restart"]
        and report["index_metrics"]["snapshot_loads"] == 1
        and report["warm_p95_ms"] <= args.max_p95_ms
    )
    rendered = json.dumps(report, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if report["gate_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
