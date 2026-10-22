"""Bounded, whole-record knowledge context and delivery receipts, not grounding claims."""

from dataclasses import dataclass
import hashlib
import json
import math
from typing import Any, Mapping, Sequence

from agents.agent_harness.redaction import redact_for_persistence


@dataclass(frozen=True)
class RenderedKnowledgeContext:
    text: str
    documents: tuple[dict[str, Any], ...]


_TEXT_LIMITS = {
    "document_id": 200, "title": 300, "namespace": 100, "topic": 300,
    "source": 500, "source_ref": 500, "version": 100, "section": 300,
    "authority": 100, "evidence_level": 100, "last_verified_at": 100,
    "excerpt": 1200,
}


def _encode(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _record(raw: Mapping[str, Any]) -> dict[str, Any]:
    citation = raw.get("citation")
    citation = citation if isinstance(citation, Mapping) else {}
    record = {
        key: redact_for_persistence(value)[:limit]
        for key, limit in _TEXT_LIMITS.items()
        if isinstance((value := raw.get(key) or citation.get(key)), str) and value
    }
    for key in ("confidence", "score"):
        value = raw.get(key)
        if type(value) not in (int, float):
            continue
        try:
            number = float(value)
        except OverflowError:
            continue
        if math.isfinite(number):
            record[key] = number
    return record


def _fit_record(row: dict[str, Any], max_chars: int) -> str | None:
    encoded = _encode(row)
    if len(encoded) <= max_chars:
        return encoded
    excerpt = row["excerpt"]
    low, high = 1, len(excerpt)
    fitted = None
    while low <= high:
        middle = (low + high) // 2
        row["excerpt"] = excerpt[:middle]
        encoded = _encode(row)
        if len(encoded) <= max_chars:
            fitted = encoded
            low = middle + 1
        else:
            high = middle - 1
    return fitted


def render_knowledge_context(
    records: Sequence[Any], *, max_chars: int = 4000,
) -> RenderedKnowledgeContext:
    """Receipt hashes cover only sanitized records actually delivered to the model."""
    if max_chars < 2:
        return RenderedKnowledgeContext("", ())
    encoded_rows: list[str] = []
    receipts: list[dict[str, Any]] = []
    used = 2
    for raw in records[:8]:
        if not isinstance(raw, Mapping):
            continue
        row = _record(raw)
        if not row.get("document_id", "").strip() or not row.get("excerpt", "").strip():
            continue
        separator_chars = int(bool(encoded_rows))
        encoded = _fit_record(row, max_chars - used - separator_chars)
        if encoded is None:
            continue
        delivered = json.loads(encoded)
        encoded_rows.append(encoded)
        used += len(encoded) + separator_chars
        receipts.append({
            "document_id": delivered["document_id"],
            "source_ref": delivered.get("source_ref") or delivered.get("source", ""),
            "version": delivered.get("version", ""),
            "sha256": hashlib.sha256(encoded.encode("utf-8")).hexdigest(),
            "excerpt_chars": len(delivered["excerpt"]),
        })
    return RenderedKnowledgeContext("[" + ",".join(encoded_rows) + "]", tuple(receipts))
