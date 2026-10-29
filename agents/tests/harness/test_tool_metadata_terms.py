"""Tool scoring caches metadata while observing changed declarations."""

from types import SimpleNamespace

from agents.agent_harness.core import tool_selection as selection


def test_schema_scoring_reads_properties_without_serializing_whole_schema():
    class Schema:
        properties = {"date": {"description": "reporting window"}}

        def to_dict(self):
            raise AssertionError("ranking must not copy the complete schema")

    tool = SimpleNamespace(name="read", input_schema=Schema())
    assert selection._relevance_score({"reporting"}, tool) == 1


def test_metadata_edits_are_visible_and_cached_terms_cannot_be_mutated():
    tool = {"name": "read_record", "description": "historical report"}
    before = selection._relevance_score({"historical"}, tool)
    tool["description"] = "current inventory"
    assert selection._relevance_score({"historical"}, tool) < before
    assert selection._relevance_score({"inventory"}, tool) > 0
    assert selection._metadata_terms("current inventory") == frozenset({"current", "inventory"})


def test_query_terms_are_not_retained_in_metadata_cache():
    selection._cached_metadata_terms.cache_clear()
    tool = {"name": "read_record", "description": "reporting"}
    selection._relevance_score(selection._terms("reporting private-query-84919"), tool)
    before = selection._cached_metadata_terms.cache_info()
    selection._terms("reporting another-private-query")
    after = selection._cached_metadata_terms.cache_info()
    assert before == after
    for _ in range(4):
        selection._relevance_score({"reporting"}, tool)
    assert selection._cached_metadata_terms.cache_info().hits > before.hits


def test_large_metadata_is_not_retained_and_legacy_schema_stays_supported():
    before = selection._cached_metadata_terms.cache_info()
    selection._metadata_terms("metadata " * 1000)
    assert selection._cached_metadata_terms.cache_info() == before

    class Schema:
        def to_dict(self):
            return {"properties": {"scope": {"description": "reporting range"}}}

    assert selection._relevance_score({"reporting"}, {"input_schema": Schema()}) == 1
