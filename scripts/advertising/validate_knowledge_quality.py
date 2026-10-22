"""Validate Markdown Wiki quality and retrieval cases."""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.applications.advertising.knowledge.wiki import MarkdownWikiKnowledgeProvider
from agents.applications.advertising.persistence.store import AdAgentStore
from agents.agent_platform.data.semantic import (
    HashEmbeddingProvider,
    InMemorySemanticIndex,
)


CANONICAL_IDS = {
    "google-canonical-campaign-and-search-runbook",
    "meta-canonical-campaign-and-adset-runbook",
    "tiktok-canonical-campaign-and-adgroup-runbook",
    "dv360-canonical-io-lineitem-runbook",
    "four-platform-ad-agent-handbook",
}


@dataclass
class _RetrievalMetrics:
    reciprocal_ranks: list[float] = field(default_factory=list)
    positive_cases: int = 0
    negative_cases: int = 0
    negative_failures: int = 0
    empty_query_cases: int = 0
    empty_query_failures: int = 0
    top1_cases: int = 0
    top1_hits: int = 0
    leakage: int = 0
    link_only_section_leakage: int = 0
    recalls: list[float] = field(default_factory=list)
    ndcgs: list[float] = field(default_factory=list)
    latencies_ms: list[float] = field(default_factory=list)


def _constraint_metrics(
    case: dict,
    results: list,
    *,
    evaluate_empty_queries: bool,
) -> tuple[bool, bool, int, int]:
    """Return negative-case, failure, empty-case, and empty-failure values."""
    is_negative = bool(
        case.get("expect_empty")
        or case.get("forbidden_platforms")
        or case.get("forbidden_wiki_types")
        or case.get("forbidden_statuses")
    )
    if not is_negative:
        return False, False, 0, 0

    empty_case = int(bool(case.get("expect_empty")))
    empty_failure = int(
        bool(case.get("expect_empty") and results and evaluate_empty_queries)
    )
    forbidden_platforms = {
        str(item).strip().lower()
        for item in case.get("forbidden_platforms", [])
    }
    forbidden_wiki_types = {
        str(item).strip().lower()
        for item in case.get("forbidden_wiki_types", [])
    }
    forbidden_statuses = {
        str(item).strip().lower()
        for item in case.get("forbidden_statuses", [])
    }
    forbidden_failure = any(
        result.platform in forbidden_platforms
        or result.wiki_type in forbidden_wiki_types
        or result.status in forbidden_statuses
        for result in results
    )
    return (
        True,
        bool(empty_failure or forbidden_failure),
        empty_case,
        empty_failure,
    )


def _platform_leakage(query: str, results: list) -> int:
    platform_terms = {
        "google": "google-ads",
        "meta": "meta",
        "tiktok": "tiktok",
        "dv360": "dv360",
    }
    normalized_query = query.lower()
    requested = next(
        (
            platform
            for term, platform in platform_terms.items()
            if term in normalized_query
        ),
        "",
    )
    return int(
        bool(requested)
        and any(
            result.platform not in {requested, "all"}
            for result in results[:1]
        )
    )


def _metric_report(
    metrics: _RetrievalMetrics,
    *,
    evaluate_empty_queries: bool,
) -> dict[str, float | int | str]:
    hits = sum(value > 0 for value in metrics.reciprocal_ranks)
    return {
        "expected_set_semantics": "acceptable_references_not_mandatory_coverage",
        "positive_cases": metrics.positive_cases,
        "negative_cases": metrics.negative_cases,
        "hit_at_3": (
            round(hits / metrics.positive_cases, 3)
            if metrics.positive_cases else 0.0
        ),
        "mrr": (
            round(sum(metrics.reciprocal_ranks) / metrics.positive_cases, 3)
            if metrics.positive_cases
            else 0.0
        ),
        "recall_at_3": round(sum(metrics.recalls) / len(metrics.recalls), 3)
        if metrics.recalls else 0.0,
        "ndcg_at_3": round(sum(metrics.ndcgs) / len(metrics.ndcgs), 3)
        if metrics.ndcgs else 0.0,
        "latency_samples": len(metrics.latencies_ms),
        "latency_p50_ms": _percentile(metrics.latencies_ms, 0.50),
        "latency_p95_ms": _percentile(metrics.latencies_ms, 0.95),
        "leakage": metrics.leakage,
        "negative_failures": metrics.negative_failures,
        "empty_query_assessment": (
            "enforced" if evaluate_empty_queries else "not_assessed"
        ),
        "empty_query_cases": metrics.empty_query_cases,
        "empty_query_failures": metrics.empty_query_failures,
        "top1_cases": metrics.top1_cases,
        "top1_accuracy": (
            round(metrics.top1_hits / metrics.top1_cases, 3)
            if metrics.top1_cases else 1.0
        ),
        "link_only_section_leakage": metrics.link_only_section_leakage,
    }


def _percentile(samples: list[float], fraction: float) -> float:
    if not samples:
        return 0.0
    return round(sorted(samples)[max(0, math.ceil(len(samples) * fraction) - 1)], 3)


def _accumulate_case_metrics(
    metrics: _RetrievalMetrics,
    case: dict,
    results: list,
    *,
    evaluate_empty_queries: bool = True,
) -> None:
    expected_top = str(case.get("expected_top") or "").strip()
    if expected_top:
        metrics.top1_cases += 1
        metrics.top1_hits += int(
            bool(results and results[0].document_id == expected_top)
        )
    forbidden_sections = {
        str(item).strip().casefold()
        for item in case.get("forbidden_sections", [])
    }
    metrics.link_only_section_leakage += int(any(
        result.section.strip().casefold() in forbidden_sections
        for result in results
    ))
    is_negative, failed, empty_case, empty_failure = _constraint_metrics(
        case, results, evaluate_empty_queries=evaluate_empty_queries
    )
    if is_negative:
        metrics.negative_cases += 1
        metrics.negative_failures += int(failed)
        metrics.empty_query_cases += empty_case
        metrics.empty_query_failures += empty_failure

    expected = set(case.get("expected") or [])
    if expected:
        metrics.positive_cases += 1
        rank = next(
            (
                index + 1
                for index, result in enumerate(results)
                if result.document_id in expected
            ),
            0,
        )
        metrics.reciprocal_ranks.append(1.0 / rank if rank else 0.0)
        relevant = [result.document_id in expected for result in results[:3]]
        metrics.recalls.append(
            len({result.document_id for result in results[:3]} & expected) / len(expected)
        )
        dcg = sum(int(hit) / math.log2(index + 2) for index, hit in enumerate(relevant))
        ideal = sum(1 / math.log2(index + 2) for index in range(min(3, len(expected))))
        metrics.ndcgs.append(dcg / ideal if ideal else 0.0)
        metrics.leakage += _platform_leakage(case["query"], results)


def evaluate_cases(
    current_provider: MarkdownWikiKnowledgeProvider,
    cases: list[dict],
    *,
    evaluate_empty_queries: bool = True,
) -> dict[str, float | int | str]:
    """Score retrieval relevance and safety constraints independently."""
    metrics = _RetrievalMetrics()
    for case in cases:
        started = time.perf_counter()
        results = current_provider.query(case["query"], limit=3)
        metrics.latencies_ms.append((time.perf_counter() - started) * 1000)
        _accumulate_case_metrics(
            metrics, case, results,
            evaluate_empty_queries=evaluate_empty_queries,
        )

    return _metric_report(
        metrics,
        evaluate_empty_queries=evaluate_empty_queries,
    )


def _canonical_document_errors(
    provider: MarkdownWikiKnowledgeProvider,
) -> list[str]:
    documents = {document.document_id: document for document in provider.documents}
    errors: list[str] = []
    for document_id in CANONICAL_IDS:
        document = documents.get(document_id)
        if not document:
            errors.append(f"missing canonical document: {document_id}")
            continue
        if len(document.excerpt) < 2400:
            errors.append(f"canonical document too short: {document_id}")
        if document.excerpt.count("## ") < 5:
            errors.append(f"canonical document lacks sections: {document_id}")
        if "官方参考" not in document.excerpt:
            errors.append(f"canonical document lacks sources: {document_id}")
    return errors


def _evaluate_modes(
    knowledge_root: str,
    cases: list[dict],
) -> dict[str, dict[str, float | int | str]]:
    lexical_provider = MarkdownWikiKnowledgeProvider(knowledge_root)
    semantic_provider = MarkdownWikiKnowledgeProvider(
        knowledge_root,
        embedding_provider=HashEmbeddingProvider(),
        semantic_index=InMemorySemanticIndex(),
    )
    fts_store = AdAgentStore(":memory:")
    hybrid_provider = MarkdownWikiKnowledgeProvider(
        knowledge_root,
        search_index=fts_store,
        embedding_provider=HashEmbeddingProvider(),
        semantic_index=InMemorySemanticIndex(),
    )
    try:
        return {
            "lexical": evaluate_cases(lexical_provider, cases),
            # HashEmbeddingProvider is a deterministic test double, not a
            # calibrated model; it cannot validate semantic rejection thresholds.
            "semantic": evaluate_cases(
                semantic_provider, cases, evaluate_empty_queries=False
            ),
            "hybrid": evaluate_cases(
                hybrid_provider, cases, evaluate_empty_queries=False
            ),
        }
    finally:
        fts_store.close()


def _metrics_pass(metrics: dict[str, dict[str, float | int | str]]) -> bool:
    lexical = metrics["lexical"]
    return not (
        lexical["hit_at_3"] < 0.95
        or lexical["mrr"] < 0.95
        or lexical["leakage"] > 1
        or lexical["negative_failures"]
        or lexical["empty_query_failures"]
        or lexical["top1_accuracy"] < 1.0
        or lexical["link_only_section_leakage"]
        or metrics["semantic"]["leakage"] > 1
        or metrics["semantic"]["negative_failures"]
        or metrics["semantic"]["link_only_section_leakage"]
        or metrics["hybrid"]["leakage"] > 1
        or metrics["hybrid"]["negative_failures"]
        or metrics["hybrid"]["link_only_section_leakage"]
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--knowledge-root", default="agents/knowledge/advertising/wiki")
    parser.add_argument(
        "--cases", default="agents/evals/advertising/knowledge_retrieval_cases.json"
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--max-p95-ms", type=float, default=2000.0)
    args = parser.parse_args()
    provider = MarkdownWikiKnowledgeProvider(args.knowledge_root)
    errors = _canonical_document_errors(provider)
    cases = json.loads(Path(args.cases).read_text(encoding="utf-8"))
    metrics = _evaluate_modes(args.knowledge_root, cases)
    if not math.isfinite(args.max_p95_ms) or args.max_p95_ms <= 0:
        raise ValueError("latency budget must be positive and finite")
    if metrics["lexical"]["latency_p95_ms"] > args.max_p95_ms:
        errors.append("lexical retrieval exceeded p95 latency budget")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps({
            "mode": "offline_retrieval", "provider_e2e": False,
            "semantic_embedding": "synthetic_contract_only",
            "metrics": metrics, "errors": errors,
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
    print(f"documents={len(provider.documents)} chunks={len(provider.chunks)}")
    print(f"canonical={len(CANONICAL_IDS)}")
    for mode, values in metrics.items():
        print(
            f"{mode}={json.dumps(values, ensure_ascii=False, sort_keys=True)}"
        )
    return 0 if not errors and _metrics_pass(metrics) else 1


if __name__ == "__main__":
    raise SystemExit(main())
