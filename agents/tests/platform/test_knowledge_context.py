import hashlib
import json

import pytest

from agents.agent_platform.data.knowledge_context import render_knowledge_context


def document(index=0, **values):
    return {
        "document_id": f"doc-{index}", "title": "Knowledge",
        "excerpt": "Evidence " * 300, "source": "local/reference",
        "version": "1.0", **values,
    }


@pytest.mark.parametrize("budget", [0, 1, 2, 30, 500, 1700, 4000])
def test_context_is_valid_whole_record_json_with_exact_character_bound(budget):
    rendered = render_knowledge_context(
        [document(index) for index in range(12)], max_chars=budget,
    )
    assert len(rendered.text) <= budget
    rows = json.loads(rendered.text) if rendered.text else []
    assert len(rows) <= 8
    assert len(rendered.documents) == len(rows)
    for row, receipt in zip(rows, rendered.documents):
        assert receipt["document_id"] == row["document_id"]
        assert receipt["excerpt_chars"] == len(row["excerpt"])
        assert receipt["sha256"] == hashlib.sha256(
            json.dumps(row, ensure_ascii=False, separators=(",", ":")).encode()
        ).hexdigest()
        assert row["excerpt"]


def test_receipts_only_describe_delivered_nonempty_documents_and_omit_secrets():
    rendered = render_knowledge_context([
        document(excerpt="access_token=private-value", client_secret="private-value"),
        document(1, excerpt=""),
        {"excerpt": "anonymous snippet"},
        "not a record",
    ])
    assert len(rendered.documents) == 1
    assert "private-value" not in rendered.text
    assert "private-value" not in str(rendered.documents)
    assert "client_secret" not in rendered.text
    assert "anonymous snippet" not in rendered.text


def test_oversized_record_does_not_hide_later_usable_evidence():
    rendered = render_knowledge_context([
        document(document_id="d" * 500, title="t" * 500, source="s" * 500),
        document(1, excerpt="short"),
    ], max_chars=180)
    assert [item["document_id"] for item in rendered.documents] == ["doc-1"]


def test_context_preserves_finite_confidence_and_score_without_coercing_strings():
    rendered = render_knowledge_context([
        document(confidence=0.9, score=3.5),
        document(1, confidence=True, score="100"),
        document(2, confidence=float("nan"), score=float("inf")),
    ])
    rows = json.loads(rendered.text)
    assert rows[0]["confidence"] == 0.9
    assert rows[0]["score"] == 3.5
    assert all("confidence" not in row and "score" not in row for row in rows[1:])
