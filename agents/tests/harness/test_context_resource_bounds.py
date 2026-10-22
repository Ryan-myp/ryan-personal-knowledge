import json

from agents.agent_harness import BoundedContextProvider, TurnRequest


def test_context_does_not_drain_a_provider_iterator_past_its_limit():
    read = []

    class Source:
        def search(self, *_args, **_kwargs):
            for index in range(100):
                read.append(index)
                if index >= 3:
                    raise AssertionError("source was consumed beyond the requested limit")
                yield {"document_id": str(index), "excerpt": "evidence"}

    value = BoundedContextProvider(knowledge=Source(), max_items=3).build_context(
        TurnRequest(user_input="question"), (),
    )
    assert read == [0, 1, 2]
    assert len(value["sources"]) == 3


def test_sources_report_only_delivered_records_and_never_copy_large_provider_metadata():
    class Source:
        def search(self, *_args, **_kwargs):
            return [
                {"title": "First", "document_id": "first", "excerpt": "x" * 100_000,
                 "private_payload": "not for model " * 100_000},
                {"title": "Second", "document_id": "second", "excerpt": "last record"},
            ]

    value = BoundedContextProvider(
        knowledge=Source(), max_items=2, max_chars=200,
    ).build_context(TurnRequest(user_input="question"), ())
    assert len(value["prompt"]) <= 200
    assert "last record" not in value["prompt"]
    assert len(value["sources"]) == 1
    assert len(json.dumps(value, ensure_ascii=False)) < 1500
    assert "private_payload" not in str(value)


def test_context_records_error_types_without_private_error_details():
    class Source:
        def search(self, *_args, **_kwargs):
            raise RuntimeError("access_token=private-value")

    value = BoundedContextProvider(knowledge=Source()).build_context(
        TurnRequest(user_input="question"), (),
    )
    assert value["errors"] == [{"source": "knowledge", "error_type": "RuntimeError"}]
    assert "private-value" not in str(value)
    assert value["sources"] == []


def test_unsupported_context_items_do_not_create_empty_source_claims():
    class Source:
        def search(self, *_args, **_kwargs):
            return [None, 3, {"private_payload": "not for context"}]

    value = BoundedContextProvider(knowledge=Source()).build_context(
        TurnRequest(user_input="question"), (),
    )
    assert value["sources"] == []


def test_plain_text_context_is_bounded_and_redacted():
    class Source:
        def search(self, *_args, **_kwargs):
            return ["client_secret=PRIVATE " + "content " * 1000]

    value = BoundedContextProvider(knowledge=Source(), max_chars=180).build_context(
        TurnRequest(user_input="question"), (),
    )
    assert "PRIVATE" not in str(value)
    assert len(value["prompt"]) <= 180
    assert len(value["sources"]) == 1
