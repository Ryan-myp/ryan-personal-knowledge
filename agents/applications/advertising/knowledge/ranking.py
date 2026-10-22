"""Lexical/semantic ranking and per-result match evidence for Wiki chunks."""

from collections import Counter
from dataclasses import dataclass, replace
import math
from typing import Any, Iterable, Mapping


@dataclass(frozen=True)
class RankingOptions:
    platforms: Iterable[str] | None = None
    intent_type: str | None = None
    knowledge_types: Iterable[str] | None = None
    limit: int = 4
    max_excerpt_chars: int = 1200
    fts_hits: Mapping[str, float] | None = None
    semantic_hits: Mapping[str, float] | None = None


class WikiRanking:
    def __init__(self, lexical: Any, query: str, options: RankingOptions) -> None:
        self.lexical = lexical
        self.query = query
        self.options = options
        self.terms = lexical._terms(query, options.intent_type)
        self.phrase = lexical._normalise_text(query)
        self.allowed: set[str] = set()
        self.allowed_types = {
            str(item).strip().lower() for item in (options.knowledge_types or []) if item
        }
        self.frequencies: Counter = Counter()
        self.average_length = 0.0
        self.total_chunks = 0

    def _eligible(self, chunk: Any) -> bool:
        platform = self.lexical._normalize_platform(chunk.platform)
        universal = platform == "all" and self.allowed_types == {"error_pattern"}
        if chunk.status != "published":
            return False
        if self.allowed and platform not in self.allowed and not universal:
            return False
        if self.allowed_types and chunk.knowledge_type not in self.allowed_types:
            return False
        sources = [
            hits for hits in (self.options.fts_hits, self.options.semantic_hits)
            if hits is not None
        ]
        return not sources or any(chunk.chunk_id in hits for hits in sources)

    def rank(self, chunks: Iterable[Any], documents: Iterable[Any]) -> list[Any]:
        if self.options.limit <= 0 or self.options.max_excerpt_chars <= 0:
            return []
        self.allowed = self.lexical._effective_platforms(
            self.query, list(documents), self.options.platforms,
        )
        filtered = [chunk for chunk in chunks if self._eligible(chunk)]
        tokens = [set(self.lexical._tokenize(chunk.excerpt)) for chunk in filtered]
        self.frequencies.update(term for row in tokens for term in row)
        self.total_chunks = len(filtered)
        self.average_length = sum(map(len, tokens)) / max(len(tokens), 1)
        scored = [
            self._score(chunk, len(words))
            for chunk, words in zip(filtered, tokens)
        ]
        scored.sort(key=lambda row: (-row[0], row[1].document_id))
        results = []
        seen = set()
        for score, chunk, matched, coverage in scored:
            if score <= 0 or chunk.document_id in seen:
                continue
            seen.add(chunk.document_id)
            results.append(self._result(score, chunk, matched, coverage))
            if len(results) >= self.options.limit:
                break
        return results

    def _fields(self, chunk: Any) -> tuple[str, ...]:
        return tuple(self.lexical._normalise_text(value) for value in (
            chunk.title, " ".join(chunk.heading_path), " ".join(chunk.tags),
            f"{chunk.category} {chunk.subcategory}", chunk.topic,
        ))

    @staticmethod
    def _metadata_score(term: str, fields: tuple, *, first_only: bool) -> float:
        weights = [weight for text, weight in zip(fields, (5, 3.5, 2.5, 2.5, 2)) if term in text]
        return (weights[0] if weights else 0.0) if first_only else sum(weights)

    def _base_score(self, chunk: Any, fields: tuple, body: str) -> float:
        score = 0.0
        fts, semantic = self.options.fts_hits, self.options.semantic_hits
        if fts is not None:
            score += min(12.0, fts.get(chunk.chunk_id, 0.0))
        if semantic is not None and chunk.chunk_id in semantic:
            score += max(0.0, (semantic[chunk.chunk_id] + 1.0) / 2.0) * 8.0
        if self.phrase and self.phrase in " ".join((*fields, body)):
            score += 6.0
        if self.phrase and self.phrase in fields[0]:
            score += 8.0
        elif self.phrase and self.phrase in fields[1]:
            score += 5.0
        return score

    def _score(self, chunk: Any, body_length: int) -> tuple:
        fields = self._fields(chunk)
        body = self.lexical._normalise_text(chunk.excerpt)
        counts = dict(self.lexical._term_frequency(body))
        score = self._base_score(chunk, fields, body)
        matched = []
        for term in self.terms:
            count = counts.get(term, 0)
            if count or any(term in text for text in fields):
                matched.append(term)
            score += self._metadata_score(term, fields, first_only=not count)
            if count:
                frequency = self.frequencies.get(term, 0)
                idf = math.log(1 + (self.total_chunks - frequency + 0.5) / (frequency + 0.5))
                saturation = count * 2.2 / (
                    count + 1.2 * (0.65 + 0.35 * max(body_length, 1)
                                   / max(self.average_length, 1.0))
                )
                score += idf * saturation
        coverage = len(set(matched)) / len(self.terms) if self.terms else 1.0
        if self.terms:
            score += 4.0 * coverage
        if self.allowed and self.lexical._normalize_platform(chunk.platform) in self.allowed:
            score += 1.5
        if not self.terms and not self.phrase:
            score = 0.1
        score *= max(chunk.confidence, 0.01) * self.lexical._retrieval_quality(chunk)
        return score, chunk, tuple(dict.fromkeys(matched)), coverage

    def _result(self, score: float, chunk: Any, matched: tuple, coverage: float) -> Any:
        fts, semantic = self.options.fts_hits, self.options.semantic_hits
        method = (
            "hybrid" if fts is not None and semantic is not None
            else "sqlite_fts5_bm25" if fts is not None
            else "semantic_vector" if semantic is not None else chunk.retrieval_method
        )
        excerpt = self.lexical._relevant_excerpt(
            chunk.excerpt, self.query, self.options.max_excerpt_chars,
        )
        return replace(
            chunk, excerpt=self.lexical._SENSITIVE_TERMS.sub("<redacted>", excerpt),
            score=round(score, 6), retrieval_method=method,
            matched_terms=matched, match_coverage=round(coverage, 4),
        )
