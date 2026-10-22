from __future__ import annotations

import pytest

from agents.agent_platform.data.embeddings import OpenAICompatibleEmbeddingProvider
from agents.applications.advertising.persistence.store import AdAgentStore


class _Response:
    def __init__(self, payload, status_error=None):
        self.payload = payload
        self.status_error = status_error

    def raise_for_status(self):
        if self.status_error:
            raise self.status_error

    def json(self):
        return self.payload


class _Client:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def post(self, url, *, headers, json, timeout):
        self.calls.append({
            "url": url,
            "headers": headers,
            "json": json,
            "timeout": timeout,
        })
        return self.response


def test_openai_compatible_embeddings_preserve_response_order():
    client = _Client(_Response({
        "data": [
            {"index": 1, "embedding": [0.0, 1.0]},
            {"index": 0, "embedding": [1.0, 0.0]},
        ],
    }))
    provider = OpenAICompatibleEmbeddingProvider(
        lambda: {
            "model": "embed-v1",
            "base_url": "https://models.example/v1",
            "api_key": "secret-token",
        },
        client=client,
    )

    vectors = provider.embed(["first", "second"])

    assert vectors == [[1.0, 0.0], [0.0, 1.0]]
    assert client.calls[0]["url"] == "https://models.example/v1/embeddings"
    assert client.calls[0]["headers"]["Authorization"] == "Bearer secret-token"
    assert client.calls[0]["json"] == {
        "model": "embed-v1",
        "input": ["first", "second"],
    }


@pytest.mark.parametrize(
    "payload",
    [
        {"data": [{"index": 0, "embedding": []}]},
        {"data": [{"index": 0, "embedding": [float("nan")]}]},
        {"data": [{"index": 1, "embedding": [1.0]}]},
        {"data": [{"index": 0, "embedding": [1.0]}]},
    ],
)
def test_openai_compatible_embeddings_reject_malformed_vectors(payload):
    provider = OpenAICompatibleEmbeddingProvider(
        lambda: {
            "model": "embed-v1",
            "base_url": "https://models.example/v1",
            "api_key": "secret-token",
        },
        client=_Client(_Response(payload)),
    )

    with pytest.raises((RuntimeError, ValueError)):
        provider.embed(["first", "second"])


def test_embedding_errors_do_not_include_response_body_or_secret():
    client = _Client(_Response(
        {"error": {"message": "secret-token private provider details"}},
        RuntimeError("upstream error"),
    ))
    provider = OpenAICompatibleEmbeddingProvider(
        lambda: {
            "model": "embed-v1",
            "base_url": "https://models.example/v1",
            "api_key": "secret-token",
        },
        client=client,
    )

    with pytest.raises(RuntimeError) as error:
        provider.embed(["query"])

    assert "secret-token" not in str(error.value)
    assert "private provider details" not in str(error.value)


def test_persistent_semantic_vectors_are_scoped_and_replaced_atomically():
    store = AdAgentStore(":memory:")
    try:
        first = [
            {"chunk_id": "doc-a:0", "document_id": "doc-a", "vector": [1.0, 0.0]},
            {"chunk_id": "doc-b:0", "document_id": "doc-b", "vector": [0.0, 1.0]},
        ]
        assert store.rebuild_knowledge_semantic_index(
            first,
            scope="builtin",
            fingerprint="revision-a",
        )

        matches = store.search_knowledge_semantic_index(
            [1.0, 0.0], scope="builtin", limit=5,
        )
        other_scope = store.search_knowledge_semantic_index(
            [1.0, 0.0], scope="tenant:other", limit=5,
        )

        assert [item["chunk_id"] for item in matches] == ["doc-a:0", "doc-b:0"]
        assert other_scope == []
        assert store.is_knowledge_semantic_index_current(
            scope="builtin",
            fingerprint="revision-a",
        )
        assert not store.is_knowledge_semantic_index_current(
            scope="builtin",
            fingerprint="revision-b",
        )

        assert store.rebuild_knowledge_semantic_index(
            [{"chunk_id": "doc-c:0", "document_id": "doc-c", "vector": [1.0, 1.0]}],
            scope="builtin",
            fingerprint="revision-b",
        )
        assert [
            item["chunk_id"]
            for item in store.search_knowledge_semantic_index(
                [1.0, 1.0], scope="builtin", limit=5,
            )
        ] == ["doc-c:0"]
    finally:
        store.close()
