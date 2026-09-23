"""Validate Markdown Wiki quality and retrieval cases."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.ad_agent.domain.ad.knowledge import MarkdownWikiKnowledgeProvider
from agents.ad_agent.persistence.store import AdAgentStore
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--knowledge-root", default="agents/ad_agent/knowledge_base")
    parser.add_argument(
        "--cases", default="agents/ad_agent/evals/knowledge_retrieval_cases.json"
    )
    args = parser.parse_args()

    provider = MarkdownWikiKnowledgeProvider(args.knowledge_root)
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

    cases = json.loads(Path(args.cases).read_text(encoding="utf-8"))

    def evaluate(current_provider: MarkdownWikiKnowledgeProvider) -> dict[str, float | int]:
        reciprocal_ranks: list[float] = []
        hits = 0
        leakage = 0
        negative_cases = 0
        negative_failures = 0
        for case in cases:
            expected = set(case["expected"])
            results = current_provider.query(case["query"], limit=3)
            result_ids = [result.document_id for result in results]
            is_negative = bool(
                case.get("expect_empty")
                or case.get("forbidden_platforms")
                or case.get("forbidden_wiki_types")
                or case.get("forbidden_statuses")
            )
            if is_negative:
                negative_cases += 1
                if case.get("expect_empty") and results:
                    negative_failures += 1
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
                if any(result.platform in forbidden_platforms for result in results):
                    negative_failures += 1
                if any(result.wiki_type in forbidden_wiki_types for result in results):
                    negative_failures += 1
                if any(result.status in forbidden_statuses for result in results):
                    negative_failures += 1
                continue
            rank = next(
                (index + 1 for index, item in enumerate(results)
                 if item.document_id in expected),
                0,
            )
            hits += bool(rank)
            reciprocal_ranks.append(1.0 / rank if rank else 0.0)
            query = case["query"].lower()
            if any(term in query for term in ("google", "meta", "tiktok", "dv360")):
                platform_terms = {
                    "google": "google-ads",
                    "meta": "meta",
                    "tiktok": "tiktok",
                    "dv360": "dv360",
                }
                requested = next(
                    (value for key, value in platform_terms.items() if key in query),
                    "",
                )
                if requested and any(
                    result.platform not in {requested, "all"} for result in results[:1]
                ):
                    leakage += 1
        positive_total = len(cases) - negative_cases or 1
        return {
            "positive_cases": positive_total,
            "negative_cases": negative_cases,
            "hit_at_3": round(hits / positive_total, 3),
            "mrr": round(sum(reciprocal_ranks) / positive_total, 3),
            "leakage": leakage,
            "negative_failures": negative_failures,
        }

    semantic_provider = MarkdownWikiKnowledgeProvider(
        args.knowledge_root,
        embedding_provider=HashEmbeddingProvider(),
        semantic_index=InMemorySemanticIndex(),
    )
    fts_store = AdAgentStore(":memory:")
    hybrid_provider = MarkdownWikiKnowledgeProvider(
        args.knowledge_root,
        search_index=fts_store,
        embedding_provider=HashEmbeddingProvider(),
        semantic_index=InMemorySemanticIndex(),
    )
    metrics = {
        "lexical": evaluate(provider),
        "semantic": evaluate(semantic_provider),
        "hybrid": evaluate(hybrid_provider),
    }
    fts_store.close()

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"documents={len(provider.documents)} chunks={len(provider.chunks)}")
    print(f"canonical={len(CANONICAL_IDS)}")
    for mode, values in metrics.items():
        print(
            f"{mode}={json.dumps(values, ensure_ascii=False, sort_keys=True)}"
        )
    lexical = metrics["lexical"]
    if (
        lexical["hit_at_3"] < 0.9
        or lexical["leakage"] > 1
        or lexical["negative_failures"]
        or metrics["semantic"]["leakage"] > 1
        or metrics["semantic"]["negative_failures"]
        or metrics["hybrid"]["leakage"] > 1
        or metrics["hybrid"]["negative_failures"]
    ):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
