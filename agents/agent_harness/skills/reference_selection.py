"""Bounded lexical selection for standard Skill reference documents."""

from __future__ import annotations

import re
from typing import Collection, Mapping

import yaml


_REFERENCE_STOPWORDS = frozenset({
    "a", "an", "and", "are", "as", "at", "based", "by", "can", "for",
    "from", "guidance", "guide", "how", "in", "into", "is", "it", "of",
    "on", "or", "should", "the", "then", "this", "to", "use", "using",
    "via", "when", "with", "account", "audit", "coverage", "diagnosis",
    "diagnostic", "diagnostics", "evidence", "fail", "inferred", "pass",
    "performance", "report", "status", "stale", "unknown", "verified",
})


def reference_terms(
    value: str, *, stopwords: Collection[str] = _REFERENCE_STOPWORDS,
) -> set[str]:
    text = str(value or "").casefold()
    terms = {
        term for term in re.findall(r"\w{2,}", text)
        if term not in stopwords
    }
    for run in re.findall(r"[\u3400-\u9fff]+", text):
        terms.update(run[index:index + 2] for index in range(len(run) - 1))
    return terms


def _reference_body(value: str, request: str) -> str:
    match = re.match(r"\A---\s*\n(.*?)\n---\s*\n", value, re.DOTALL)
    if not match:
        return value
    if match.end() > 4096:
        return ""
    try:
        metadata = yaml.safe_load(match.group(1))
    except yaml.YAMLError:
        return ""
    if not isinstance(metadata, dict):
        return ""
    scopes = metadata.get("reference_scope")
    if scopes is not None:
        if not isinstance(scopes, list) or not scopes or any(
            not isinstance(scope, str) or not scope.strip() for scope in scopes
        ):
            return ""
        normalized = request.casefold()
        if not any(
            re.search(
                r"(?<![a-z0-9_])" + re.escape(scope.casefold()) + r"(?![a-z0-9_])",
                normalized,
            )
            for scope in scopes
        ):
            return ""
    return value[match.end():]


def select_reference_excerpts(
    query: str,
    documents: Mapping[str, str],
    *,
    max_documents: int = 2,
    max_chars: int = 1600,
    scope_query: str | None = None,
) -> str:
    """Choose bounded reference passages by lexical relevance to one request."""
    if max_documents <= 0 or max_chars <= 0 or not isinstance(documents, Mapping):
        return ""
    terms = reference_terms(query)
    if not terms:
        return ""
    ranked: list[tuple[int, str, str]] = []
    for path, raw_content in documents.items():
        content = _reference_body(str(raw_content or ""), str(scope_query if scope_query is not None else query))
        if not content.strip():
            continue
        path_hits = len(terms & reference_terms(str(path)))
        paragraphs = [
            item.strip()
            for item in re.split(r"\n\s*\n", content)
            if item.strip()
        ] or [content]
        scored = [
            (len(terms & reference_terms(paragraph)), paragraph)
            for paragraph in paragraphs
        ]
        paragraph_score, excerpt = max(
            scored,
            key=lambda item: (item[0], min(len(item[1]), 1200)),
        )
        score = paragraph_score + path_hits
        if score:
            ranked.append((score, str(path), excerpt))
    ranked.sort(key=lambda item: (-item[0], item[1]))

    blocks: list[str] = []
    remaining = max_chars
    for index, (_score, path, excerpt) in enumerate(ranked[:max_documents]):
        slots_left = min(max_documents, len(ranked)) - index
        budget = max(1, remaining // max(slots_left, 1))
        block = f"[{path}]\n{excerpt}"[:budget]
        if not block:
            break
        blocks.append(block)
        remaining -= len(block)
        if remaining <= 0:
            break
    return "\n\n".join(blocks)[:max_chars]


__all__ = ["reference_terms", "select_reference_excerpts"]
