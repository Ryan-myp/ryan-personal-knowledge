from types import SimpleNamespace

from agents.applications.advertising.knowledge.semantic_retrieval import (
    WikiSemanticRetrieval,
)
from agents.agent_platform.data.semantic import InMemorySemanticIndex


def chunk(identifier):
    return SimpleNamespace(
        chunk_id=identifier, document_id=identifier, title=identifier,
        heading_path=(), tags=(), category="", subcategory="", excerpt="budget",
    )


class Embeddings:
    fingerprint = "model-v1"
    configured = True

    def __init__(self):
        self.calls = 0
        self.fail_next = False

    def embed(self, texts):
        self.calls += 1
        if self.fail_next:
            self.fail_next = False
            raise RuntimeError("private upstream body")
        return [[1.0, 0.0] for _ in texts]


def retrieval():
    provider = Embeddings()
    service = WikiSemanticRetrieval(
        provider, InMemorySemanticIndex(), sanitize=lambda text: text,
        retry_after_seconds=0,
    )
    return service, provider


def test_transient_query_failure_recovers_without_rebuilding_or_affecting_other_scope():
    service, provider = retrieval()
    chunks = [chunk("private")]
    assert service.rebuild(chunks, scope="tenant:a")
    assert service.rebuild(chunks, scope="tenant:b")
    provider.fail_next = True

    assert service.search("first", chunks, scope="tenant:a") is None
    assert service.status(chunks, scope="tenant:a")["error_type"] == "RuntimeError"
    assert service.status(chunks, scope="tenant:b")["error_type"] is None
    assert service.search("next", chunks, scope="tenant:b") == {"private": 1.0}
    assert service.search("retry", chunks, scope="tenant:a") == {"private": 1.0}
    assert service.status(chunks, scope="tenant:a")["error_type"] is None


def test_query_embedding_is_reused_across_scopes_but_not_across_models():
    service, provider = retrieval()
    chunks = [chunk("guide")]
    service.rebuild(chunks, scope="builtin")
    service.rebuild(chunks, scope="tenant:a")
    before = provider.calls
    service.search("same query", chunks, scope="builtin")
    service.search("same query", chunks, scope="tenant:a")
    assert provider.calls == before + 1

    provider.fingerprint = "model-v2"
    assert service.status(chunks, scope="builtin")["current"] is False
    assert service.search("same query", chunks, scope="builtin") is None
    service.rebuild(chunks, scope="builtin")
    before = provider.calls
    assert service.search("same query", chunks, scope="builtin")
    assert provider.calls == before + 1
