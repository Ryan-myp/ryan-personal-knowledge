from types import SimpleNamespace

from scripts.advertising.validate_knowledge_quality import evaluate_cases, _metrics_pass


class _Provider:
    def __init__(self, results):
        self.results = results

    def query(self, _query, limit):
        return self.results[:limit]


def _result(
    document_id="google-guide",
    platform="google-ads",
    wiki_type="runbook",
    status="published",
    section="Campaign setup",
):
    return SimpleNamespace(
        document_id=document_id,
        platform=platform,
        wiki_type=wiki_type,
        status=status,
        section=section,
    )


def test_mixed_case_scores_expected_retrieval_and_forbidden_platforms():
    metrics = evaluate_cases(
        _Provider([_result()]),
        [{
            "query": "Google campaign setup",
            "expected": ["google-guide"],
            "forbidden_platforms": ["meta", "tiktok"],
        }],
    )

    assert metrics["positive_cases"] == 1
    assert metrics["negative_cases"] == 1
    assert metrics["hit_at_3"] == 1.0
    assert metrics["mrr"] == 1.0
    assert metrics["negative_failures"] == 0


def test_multiple_forbidden_violations_count_as_one_failed_case():
    metrics = evaluate_cases(
        _Provider([_result(platform="meta", wiki_type="raw", status="draft")]),
        [{
            "query": "Google campaign setup",
            "expected": ["google-guide"],
            "forbidden_platforms": ["meta"],
            "forbidden_wiki_types": ["raw"],
            "forbidden_statuses": ["draft"],
        }],
    )

    assert metrics["negative_failures"] == 1
    assert metrics["positive_cases"] == 1
    assert metrics["hit_at_3"] == 1.0


def test_negative_only_case_does_not_dilute_positive_retrieval_metrics():
    metrics = evaluate_cases(
        _Provider([]),
        [{
            "query": "How do I bake a cake?",
            "expected": [],
            "expect_empty": True,
        }],
    )

    assert metrics["positive_cases"] == 0
    assert metrics["negative_cases"] == 1
    assert metrics["hit_at_3"] == 0.0
    assert metrics["mrr"] == 0.0
    assert metrics["negative_failures"] == 0


def test_synthetic_semantic_embedding_does_not_claim_out_of_domain_validation():
    metrics = evaluate_cases(
        _Provider([_result()]),
        [{
            "query": "How do I bake a cake?",
            "expected": [],
            "expect_empty": True,
        }],
        evaluate_empty_queries=False,
    )

    assert metrics["empty_query_assessment"] == "not_assessed"
    assert metrics["empty_query_failures"] == 0
    assert metrics["negative_failures"] == 0


def test_retrieval_reports_recall_ndcg_and_latency_separately():
    metrics = evaluate_cases(
        _Provider([_result("wrong"), _result("wanted")]),
        [{"query": "budget", "expected": ["wanted", "missing"]}],
    )
    assert metrics["hit_at_3"] == 1.0
    assert metrics["recall_at_3"] == 0.5
    assert metrics["ndcg_at_3"] == 0.387
    assert metrics["latency_samples"] == 1
    assert metrics["latency_p95_ms"] >= 0


def test_retrieval_gate_checks_ranking_not_just_one_hit():
    report = evaluate_cases(
        _Provider([_result("wrong"), _result("wanted")]),
        [{"query": "budget", "expected": ["wanted"]}],
    )
    assert report["hit_at_3"] == 1
    assert report["mrr"] == 0.5
    assert _metrics_pass({mode: dict(report) for mode in ("lexical", "semantic", "hybrid")}) is False
