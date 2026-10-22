from agents.applications.advertising.knowledge.wiki import (
    KnowledgeDocument, MarkdownWikiKnowledgeProvider,
)


def test_each_ranked_document_keeps_its_own_matched_terms():
    def document(identifier, text):
        return KnowledgeDocument(
            document_id=identifier, platform="all", topic="", excerpt=text,
            source="fixture", version="1", confidence=1.0, updated_at="",
            chunk_id=identifier,
        )

    chunks = [
        document("both", "budget creative budget creative"),
        document("one", "budget guidance"),
    ]
    results = MarkdownWikiKnowledgeProvider._query_chunks(
        chunks, chunks, "budget creative", limit=2,
    )
    by_id = {item.document_id: item for item in results}
    assert by_id["both"].matched_terms == ("budget", "creative")
    assert by_id["both"].match_coverage == 1.0
    assert by_id["one"].matched_terms == ("budget",)
    assert by_id["one"].match_coverage == 0.5
