from scripts.advertising.benchmark_semantic_retrieval import benchmark


def test_warm_semantic_queries_reuse_one_persisted_snapshot():
    report = benchmark(records=100, dimensions=16, repetitions=5)
    assert report["provider_calls"] == 0
    assert report["index_metrics"]["snapshot_loads"] == 1
    assert report["index_metrics"]["cache_hits"] == 5
    assert report["rank_consistent_after_restart"] is True
    assert report["warm_p95_ms"] >= 0
