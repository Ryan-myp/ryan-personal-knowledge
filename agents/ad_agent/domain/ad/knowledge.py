"""Provider-neutral, Markdown-first LLM Wiki knowledge contracts.

The ad-agent knowledge base intentionally follows the simple LLM Wiki model:
human-readable Markdown files, an ``index.md`` map and a ``log.md`` history.
There is no vector database or executable knowledge plug-in.  This module is
the one runtime retrieval boundary; callers should depend on
``KnowledgeProvider`` instead of scanning the Wiki themselves.
"""

from __future__ import annotations

import json
import math
import re
import unicodedata
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional, Protocol

from ...core.platform import normalize_platform


WIKI_SCHEMA_VERSION = "1"
WIKI_LAYERS = {"platform", "business", "experience", "dynamic", "index"}
WIKI_STATUSES = {"draft", "published", "deprecated"}


@dataclass(frozen=True)
class KnowledgeDocument:
    """A bounded, source-addressable Wiki result.

    The metadata fields make the Markdown Wiki self-describing and allow the
    same document to be consumed by Runtime, CLI and evaluations.
    """

    document_id: str
    platform: str
    topic: str
    excerpt: str
    source: str
    version: str
    confidence: float
    updated_at: str
    title: str = ""
    layer: str = ""
    knowledge_type: str = "general"
    category: str = ""
    subcategory: str = ""
    source_ref: str = ""
    tags: tuple[str, ...] = field(default_factory=tuple)
    status: str = "published"
    schema_version: str = WIKI_SCHEMA_VERSION
    score: float = 0.0
    section: str = ""
    heading_path: tuple[str, ...] = field(default_factory=tuple)
    chunk_index: int = 0
    chunk_count: int = 1
    retrieval_method: str = "lexical_bm25"
    chunk_id: str = ""
    matched_terms: tuple[str, ...] = field(default_factory=tuple)
    match_coverage: float = 0.0

    @property
    def citation(self) -> dict[str, Any]:
        """Return a stable citation without exposing the full document."""
        citation = {
            "document_id": self.document_id,
            "title": self.title or self.topic,
            "source": self.source,
            "source_ref": self.source_ref or self.source,
            "version": self.version,
            "updated_at": self.updated_at,
        }
        if self.section:
            citation["section"] = self.section
            citation["chunk_index"] = self.chunk_index
            citation["chunk_count"] = self.chunk_count
        return citation

    def to_dict(self) -> dict[str, Any]:
        return {
            "document_id": self.document_id,
            "platform": self.platform,
            "topic": self.topic,
            "title": self.title or self.topic,
            "layer": self.layer,
            "knowledge_type": self.knowledge_type,
            "category": self.category,
            "subcategory": self.subcategory,
            "excerpt": self.excerpt,
            "source": self.source,
            "source_ref": self.source_ref or self.source,
            "version": self.version,
            "confidence": self.confidence,
            "updated_at": self.updated_at,
            "tags": list(self.tags),
            "status": self.status,
            "schema_version": self.schema_version,
            "score": self.score,
            "section": self.section,
            "heading_path": list(self.heading_path),
            "chunk_index": self.chunk_index,
            "chunk_count": self.chunk_count,
            "retrieval_method": self.retrieval_method,
            "matched_terms": list(self.matched_terms),
            "match_coverage": self.match_coverage,
            "citation": self.citation,
        }


class KnowledgeProvider(Protocol):
    """Read-only provider used to build bounded model context."""

    def query(
        self,
        query: str,
        *,
        platforms: Optional[Iterable[str]] = None,
        intent_type: Optional[str] = None,
        knowledge_types: Optional[Iterable[str]] = None,
        limit: int = 4,
        max_excerpt_chars: int = 1200,
    ) -> list[KnowledgeDocument]:
        ...

    def catalog(
        self,
        *,
        platforms: Optional[Iterable[str]] = None,
        knowledge_types: Optional[Iterable[str]] = None,
        limit: int = 100,
    ) -> list[KnowledgeDocument]:
        ...


def _parse_scalar(value: str) -> Any:
    """Parse the small YAML subset used in Markdown frontmatter.

    A full YAML dependency is unnecessary for this file-based Wiki.  We still
    accept JSON-like lists and booleans so metadata remains deterministic and
    easy to edit by hand.
    """
    value = value.strip().strip('"').strip("'")
    if not value:
        return ""
    if value.startswith("[") and value.endswith("]"):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed]
        except (TypeError, ValueError):
            return [item.strip().strip('"').strip("'") for item in value[1:-1].split(",") if item.strip()]
    if value.lower() in {"true", "false"}:
        return value.lower() == "true"
    return value


def parse_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """Parse flat frontmatter and return ``(metadata, Markdown body)``."""
    if not content.startswith("---"):
        return {}, content.strip()
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", content, re.DOTALL)
    if not match:
        return {}, content.strip()
    metadata: dict[str, Any] = {}
    for line in match.group(1).splitlines():
        if not line.strip() or line.lstrip().startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = _parse_scalar(value)
    return metadata, match.group(2).strip()


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in str(value).split(",") if item.strip()]


class MarkdownWikiKnowledgeProvider:
    """Canonical read-only provider for the checked-in LLM Wiki.

    Retrieval is deliberately sparse and deterministic: Markdown is indexed by
    section, then exact phrases, weighted fields and BM25-style token scores
    are combined without embeddings. This keeps the Wiki local and portable
    while avoiding the coarse behavior of scoring an entire long document.
    """

    _SENSITIVE_TERMS = re.compile(
        r"(?i)\b(?:access[_ -]?token|refresh[_ -]?token|developer[_ -]?token|"
        r"private[_ -]?key|client[_ -]?(?:id|secret)|authorization|credentials?|"
        r"partner(?:[_ -]?id)?|perter(?:[_ -]?id)?|bc[_ -]?id|mcc)\w*\b"
    )
    _TOKEN_RE = re.compile(r"[\u4e00-\u9fff]+|[a-z0-9_]+")
    _HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
    _CHUNK_SIZE = 1800
    _CHUNK_OVERLAP = 180
    _CONTROL_DOCUMENTS = frozenset({
        "ARCHITECTURE.md", "SCHEMA.md", "UPGRADE_SUMMARY.md",
        "USAGE_GUIDE.md", "QUALITY_STANDARD.md", "index.md", "log.md",
    })
    _STOPWORDS = {
        "and", "are", "for", "from", "how", "into", "that", "the", "this",
        "what", "when", "where", "with", "广告", "一个", "什么", "怎么", "如何",
        "哪些", "是否", "以及", "可以", "需要", "请问",
    }

    def __init__(self, base_path: str | Path, search_index: Any = None):
        self.base_path = Path(base_path).resolve()
        self.search_index = search_index
        self._fts_scope = "builtin"
        self._fts_available = False
        self._documents: list[KnowledgeDocument] = []
        self._chunks: list[KnowledgeDocument] = []
        self._load()

    @property
    def documents(self) -> tuple[KnowledgeDocument, ...]:
        return tuple(self._documents)

    @property
    def chunks(self) -> tuple[KnowledgeDocument, ...]:
        return tuple(self._chunks)

    def _load(self) -> None:
        self._documents = []
        self._chunks = []
        if not self.base_path.is_dir():
            return
        for path in sorted(self.base_path.rglob("*.md")):
            if not path.is_file():
                continue
            try:
                content = path.read_text(encoding="utf-8")
                stat = path.stat()
            except OSError:
                continue
            relative = path.relative_to(self.base_path)
            if relative.as_posix() in self._CONTROL_DOCUMENTS:
                continue
            metadata, body = parse_frontmatter(content)
            parts = relative.parts
            platform = str(metadata.get("platform") or "")
            if not platform and len(parts) > 2 and parts[0] == "platforms":
                platform = parts[1]
            platform = self._normalize_platform(platform or "all")
            layer = str(metadata.get("layer") or self._derive_layer(parts))
            knowledge_type = str(
                metadata.get("knowledge_type")
                or metadata.get("type")
                or self._derive_type(path.name)
            ).strip().lower()
            category = str(
                metadata.get("category")
                or self._derive_category(parts, path.name, layer, knowledge_type)
            ).strip().lower()
            subcategory = str(
                metadata.get("subcategory") or self._derive_subcategory(path.name, knowledge_type)
            ).strip().lower()
            title = str(metadata.get("title") or self._title_from_body(body) or path.stem)
            source_ref = str(metadata.get("source_ref") or relative.as_posix())
            source = str(metadata.get("source") or metadata.get("来源") or source_ref)
            version = str(metadata.get("version") or "local")
            updated_at = str(metadata.get("updated_at") or metadata.get("updated") or stat.st_mtime)
            status = str(metadata.get("status") or "published").lower()
            if status not in WIKI_STATUSES:
                status = "published"
            confidence = self._confidence(metadata.get("confidence"), 1.0)
            document_id = str(metadata.get("id") or f"{platform}:{relative.as_posix()}")
            document = KnowledgeDocument(
                document_id=document_id,
                platform=platform,
                topic=path.stem,
                excerpt=body,
                source=source,
                version=version,
                confidence=confidence,
                updated_at=updated_at,
                title=title,
                layer=layer,
                knowledge_type=knowledge_type,
                category=category,
                subcategory=subcategory,
                source_ref=source_ref,
                tags=tuple(_as_list(metadata.get("tags"))),
                status=status,
                schema_version=str(metadata.get("schema_version") or WIKI_SCHEMA_VERSION),
            )
            self._documents.append(document)
            self._chunks.extend(self._chunk_document(document, scope=self._fts_scope))
        self._fts_available = self._rebuild_search_index(
            self._chunks, scope=self._fts_scope
        )

    @staticmethod
    def _confidence(value: Any, default: float) -> float:
        try:
            return max(0.0, min(1.0, float(value)))
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _title_from_body(body: str) -> str:
        for line in body.splitlines():
            match = re.match(r"^#\s+(.+?)\s*$", line)
            if match:
                return match.group(1)
        return ""

    @staticmethod
    def _derive_layer(parts: tuple[str, ...]) -> str:
        mapping = {"platforms": "platform", "business": "business", "expertise": "experience", "dynamic": "dynamic"}
        return mapping.get(parts[0], "index" if len(parts) == 1 else "experience")

    @staticmethod
    def _derive_type(filename: str) -> str:
        name = filename.lower()
        for marker, value in (
            ("campaign", "hierarchy"), ("hierarchy", "hierarchy"),
            ("workflow", "workflow"), ("constraint", "constraint"),
            ("parameter", "parameter"), ("best-practice", "best_practice"),
            ("best_practice", "best_practice"), ("error", "error_pattern"),
            ("case", "case_study"), ("bidding", "bidding_strategy"),
            ("targeting", "targeting_strategy"), ("creative", "creative_guide"),
            ("tip", "tip"),
        ):
            if marker in name:
                return value
        return "general"

    @staticmethod
    def _derive_category(
        parts: tuple[str, ...], filename: str, layer: str, knowledge_type: str,
    ) -> str:
        """Derive a stable navigation category for metadata-light Markdown."""
        name = filename.lower()
        if not parts:
            if knowledge_type == "hierarchy":
                return "platform_foundation"
            if knowledge_type in {"constraint", "parameter", "workflow"}:
                return "campaign_operations"
            if knowledge_type in {"bidding_strategy", "targeting_strategy"}:
                return "budget_bidding" if knowledge_type == "bidding_strategy" else "audience_targeting"
            if knowledge_type == "creative_guide":
                return "creative"
            if knowledge_type == "error_pattern":
                return "diagnostics"
            if knowledge_type == "best_practice":
                return "optimization"
            if layer == "business":
                return "cross_platform_foundation"
        if parts and parts[0] == "platforms":
            if knowledge_type == "hierarchy":
                return "platform_foundation"
            if knowledge_type in {"constraint", "parameter", "workflow"}:
                return "campaign_operations"
            if "measurement" in name or "diagnostic" in name:
                return "measurement"
            if knowledge_type in {"best_practice", "strategy"} or "optimization" in name:
                return "optimization"
            return "platform_foundation"
        if parts and parts[0] == "business":
            for marker, category in (
                ("industry", "industry_playbooks"),
                ("bidding", "budget_bidding"),
                ("targeting", "audience_targeting"),
                ("creative", "creative"),
                ("measurement", "measurement"),
                ("hierarchy", "cross_platform_foundation"),
            ):
                if marker in name:
                    return category
            return "cross_platform_foundation"
        if parts and parts[0] == "expertise":
            if knowledge_type == "error_pattern" or "diagnostic" in name:
                return "diagnostics"
            if "experiment" in name:
                return "experimentation"
            return "optimization"
        if layer == "index":
            return "system"
        return "general"

    @staticmethod
    def _derive_subcategory(filename: str, knowledge_type: str) -> str:
        stem = Path(filename).stem.lower().replace("_", "-")
        if stem:
            return stem
        return knowledge_type or "general"

    @staticmethod
    def _normalize_platform(platform: str) -> str:
        value = str(platform or "all").strip().lower()
        return "all" if value == "all" else normalize_platform(value)

    @classmethod
    @lru_cache(maxsize=8192)
    def _normalise_text(cls, value: str) -> str:
        text = unicodedata.normalize("NFKC", str(value or "")).lower()
        text = re.sub(r"[_-]+", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    @classmethod
    @lru_cache(maxsize=8192)
    def _tokenize(cls, value: str) -> list[str]:
        text = cls._normalise_text(value)
        terms: list[str] = []
        for token in cls._TOKEN_RE.findall(text):
            if re.fullmatch(r"[\u4e00-\u9fff]+", token):
                terms.append(token)
                terms.extend(token[index:index + 2] for index in range(len(token) - 1))
            else:
                terms.append(token)
        return terms

    @classmethod
    @lru_cache(maxsize=8192)
    def _term_frequency(cls, value: str) -> tuple[tuple[str, int], ...]:
        counts: dict[str, int] = {}
        for term in cls._tokenize(value):
            counts[term] = counts.get(term, 0) + 1
        return tuple(counts.items())

    @classmethod
    def _terms(cls, query: str, intent_type: Optional[str]) -> list[str]:
        terms = [
            term for term in cls._tokenize(f"{query or ''} {intent_type or ''}")
            if term not in cls._STOPWORDS and len(term) > 1
        ]
        return list(dict.fromkeys(terms))

    @classmethod
    def _split_section_text(cls, text: str) -> list[str]:
        paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
        if not paragraphs:
            return [text.strip()] if text.strip() else []
        chunks: list[str] = []
        current = ""
        for paragraph in paragraphs:
            if len(paragraph) > cls._CHUNK_SIZE:
                if current:
                    chunks.append(current.strip())
                    current = ""
                start = 0
                while start < len(paragraph):
                    end = min(start + cls._CHUNK_SIZE, len(paragraph))
                    chunks.append(paragraph[start:end].strip())
                    if end >= len(paragraph):
                        break
                    start = max(start + 1, end - cls._CHUNK_OVERLAP)
                continue
            candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph
            if current and len(candidate) > cls._CHUNK_SIZE:
                chunks.append(current.strip())
                current = paragraph
            else:
                current = candidate
        if current:
            chunks.append(current.strip())
        return chunks

    @classmethod
    def _chunk_document(
        cls, document: KnowledgeDocument, *, scope: str = "builtin",
    ) -> list[KnowledgeDocument]:
        lines = document.excerpt.strip().splitlines()
        sections: list[tuple[tuple[str, ...], str, list[str]]] = []
        heading_stack: list[str] = []
        current_heading: tuple[str, ...] = ()
        current_lines: list[str] = []

        def flush() -> None:
            nonlocal current_lines
            body = "\n".join(current_lines).strip()
            if body:
                sections.append((current_heading, body, []))
            current_lines = []

        for line in lines:
            match = cls._HEADING_RE.match(line.strip())
            if match:
                flush()
                level = len(match.group(1))
                heading = match.group(2).strip()
                heading_stack[:] = heading_stack[:level - 1]
                heading_stack.append(heading)
                current_heading = tuple(heading_stack)
                continue
            current_lines.append(line)
        flush()
        if not sections and document.excerpt.strip():
            sections = [((), document.excerpt.strip(), [])]

        chunks: list[KnowledgeDocument] = []
        for heading_path, section_body, _ in sections:
            heading_prefix = f"## {heading_path[-1]}\n\n" if heading_path else ""
            for part in cls._split_section_text(section_body):
                excerpt = f"{heading_prefix}{part}".strip()
                chunks.append(
                    KnowledgeDocument(
                        **{
                            **document.__dict__,
                            "excerpt": excerpt,
                            "section": heading_path[-1] if heading_path else "",
                            "heading_path": heading_path,
                            "chunk_index": len(chunks),
                            "chunk_count": 0,
                            "chunk_id": cls._chunk_id(scope, document, len(chunks)),
                        }
                    )
                )
        chunk_count = len(chunks) or 1
        return [
            KnowledgeDocument(**{**chunk.__dict__, "chunk_count": chunk_count})
            for chunk in chunks
        ] or [
            KnowledgeDocument(
                **{
                    **document.__dict__,
                    "chunk_count": 1,
                    "chunk_id": cls._chunk_id(scope, document, 0),
                }
            )
        ]

    @staticmethod
    def _chunk_id(scope: str, document: KnowledgeDocument, chunk_index: int) -> str:
        return f"{scope}:{document.document_id}:{chunk_index}"

    @classmethod
    def _index_payloads(
        cls, chunks: Iterable[KnowledgeDocument],
    ) -> list[dict[str, Any]]:
        payloads = []
        for chunk in chunks:
            clean = lambda value: cls._SENSITIVE_TERMS.sub("<redacted>", str(value or ""))
            payloads.append(
                {
                    "chunk_id": chunk.chunk_id,
                    "document_id": chunk.document_id,
                    "title": " ".join(cls._tokenize(clean(chunk.title))),
                    "heading_path": " ".join(cls._tokenize(clean(" ".join(chunk.heading_path)))),
                    "tags": " ".join(cls._tokenize(clean(" ".join(chunk.tags)))),
                    "category": " ".join(cls._tokenize(clean(chunk.category))),
                    "subcategory": " ".join(cls._tokenize(clean(chunk.subcategory))),
                    "content": " ".join(cls._tokenize(clean(chunk.excerpt))),
                    "platform": chunk.platform,
                    "knowledge_type": chunk.knowledge_type,
                    "status": chunk.status,
                    "confidence": chunk.confidence,
                }
            )
        return payloads

    def _rebuild_search_index(
        self, chunks: Iterable[KnowledgeDocument], *, scope: str,
    ) -> bool:
        method = getattr(self.search_index, "rebuild_knowledge_search_index", None)
        if not callable(method):
            return False
        try:
            return bool(method(self._index_payloads(chunks), scope=scope))
        except (OSError, RuntimeError, TypeError, ValueError):
            return False

    def _search_index_hits(
        self, query: str, terms: Iterable[str], *, scopes: list[str],
    ) -> Optional[dict[str, float]]:
        if not self._fts_available:
            return None
        method = getattr(self.search_index, "search_knowledge_search_index", None)
        if not callable(method):
            return None
        safe_terms = [
            term for term in terms
            if re.fullmatch(r"[\u4e00-\u9fff]+|[a-z0-9_]+", term)
        ]
        if not safe_terms:
            return None
        fts_query = " OR ".join(f'"{term}"' for term in dict.fromkeys(safe_terms))
        try:
            rows = method(fts_query, scopes=scopes, limit=500)
        except (OSError, RuntimeError, TypeError, ValueError):
            self._fts_available = False
            return None
        return {
            str(row.get("chunk_id")): max(0.0, -float(row.get("rank", 0.0)))
            for row in rows
            if isinstance(row, Mapping) and row.get("chunk_id")
        }

    @classmethod
    def _effective_platforms(
        cls,
        query: str,
        documents: Iterable[KnowledgeDocument],
        platforms: Optional[Iterable[str]] = None,
    ) -> set[str]:
        """Resolve explicit or query-implied platform constraints.

        The UI may leave the platform selector at ``all`` while the user
        still asks for a specific channel (for example, ``Meta 广告类型``).
        In that case lexical ranking alone is unsafe: a Google document that
        happens to mention Meta can outrank the requested platform.  Infer
        only from platform identities already declared by the Wiki/provider;
        this remains provider-neutral and does not add a channel table to the
        Runtime.
        """
        explicit = {
            cls._normalize_platform(item)
            for item in (platforms or [])
            if item and cls._normalize_platform(item) != "all"
        }
        if explicit:
            return explicit

        known = {
            cls._normalize_platform(document.platform)
            for document in documents
            if document.platform and cls._normalize_platform(document.platform) != "all"
        }
        if not known:
            return set()
        query_text = str(query or "").strip().lower()
        terms = cls._terms(query, None)
        inferred: set[str] = set()
        for platform in known:
            platform_text = platform.lower()
            if platform_text in query_text or any(
                cls._normalize_platform(term) == platform for term in terms
            ):
                inferred.add(platform)
        return inferred

    def query(
        self,
        query: str,
        *,
        platforms: Optional[Iterable[str]] = None,
        intent_type: Optional[str] = None,
        knowledge_types: Optional[Iterable[str]] = None,
        limit: int = 4,
        max_excerpt_chars: int = 1200,
    ) -> list[KnowledgeDocument]:
        if limit <= 0 or max_excerpt_chars <= 0:
            return []
        terms = self._terms(query, intent_type)
        fts_hits = self._search_index_hits(
            query, terms, scopes=[self._fts_scope]
        )
        return self._query_chunks(
            self._chunks,
            self._documents,
            query,
            platforms=platforms,
            intent_type=intent_type,
            knowledge_types=knowledge_types,
            limit=limit,
            max_excerpt_chars=max_excerpt_chars,
            fts_hits=fts_hits,
        )

    def catalog(
        self,
        *,
        platforms: Optional[Iterable[str]] = None,
        knowledge_types: Optional[Iterable[str]] = None,
        limit: int = 100,
    ) -> list[KnowledgeDocument]:
        """Return complete published documents for navigation, not chunks."""
        if limit <= 0:
            return []
        allowed_platforms = {
            self._normalize_platform(item)
            for item in (platforms or [])
            if item and self._normalize_platform(item) != "all"
        }
        allowed_types = {
            str(item).strip().lower()
            for item in (knowledge_types or [])
            if item
        }
        documents: list[KnowledgeDocument] = []
        for document in self._documents:
            if document.status != "published":
                continue
            if allowed_platforms and self._normalize_platform(document.platform) not in allowed_platforms:
                continue
            if allowed_types and document.knowledge_type not in allowed_types:
                continue
            documents.append(document)
            if len(documents) >= limit:
                break
        return documents

    @classmethod
    def _query_chunks(
        cls,
        chunks: Iterable[KnowledgeDocument],
        documents: Iterable[KnowledgeDocument],
        query: str,
        *,
        platforms: Optional[Iterable[str]] = None,
        intent_type: Optional[str] = None,
        knowledge_types: Optional[Iterable[str]] = None,
        limit: int = 4,
        max_excerpt_chars: int = 1200,
        fts_hits: Optional[Mapping[str, float]] = None,
    ) -> list[KnowledgeDocument]:
        if limit <= 0 or max_excerpt_chars <= 0:
            return []
        document_list = list(documents)
        chunk_list = list(chunks)
        allowed = cls._effective_platforms(query, document_list, platforms)
        allowed_types = {str(item).strip().lower() for item in (knowledge_types or []) if item}
        terms = cls._terms(query, intent_type)
        phrase = cls._normalise_text(query)
        filtered: list[KnowledgeDocument] = []
        for chunk in chunk_list:
            if chunk.status != "published":
                continue
            doc_platform = cls._normalize_platform(chunk.platform)
            universal_error_reference = (
                doc_platform == "all" and allowed_types == {"error_pattern"}
            )
            if allowed and doc_platform not in allowed and not universal_error_reference:
                continue
            if allowed_types and chunk.knowledge_type not in allowed_types:
                continue
            if fts_hits is not None and chunk.chunk_id not in fts_hits:
                continue
            filtered.append(chunk)
        if not filtered:
            return []

        corpus_terms = [set(cls._tokenize(chunk.excerpt)) for chunk in filtered]
        document_frequency: dict[str, int] = {}
        for tokens in corpus_terms:
            for term in tokens:
                document_frequency[term] = document_frequency.get(term, 0) + 1
        average_length = sum(len(tokens) for tokens in corpus_terms) / max(len(corpus_terms), 1)
        total_chunks = len(filtered)
        ranked: list[tuple[float, KnowledgeDocument]] = []
        for index, document in enumerate(filtered):
            title = cls._normalise_text(document.title)
            topic = cls._normalise_text(document.topic)
            headings = cls._normalise_text(" ".join(document.heading_path))
            tags = cls._normalise_text(" ".join(document.tags))
            category = cls._normalise_text(document.category)
            subcategory = cls._normalise_text(document.subcategory)
            body = cls._normalise_text(document.excerpt)
            searchable = " ".join((title, topic, headings, tags, category, subcategory, body))
            score = 0.0
            if fts_hits is not None:
                score += min(12.0, fts_hits.get(document.chunk_id, 0.0))
            if phrase and phrase in searchable:
                score += 6.0
            if phrase and phrase in title:
                score += 8.0
            elif phrase and phrase in headings:
                score += 5.0
            token_counts = dict(cls._term_frequency(body))
            body_length = max(len(corpus_terms[index]), 1)
            matched_terms: list[str] = []
            for term in terms:
                count = token_counts.get(term, 0)
                metadata_match = (
                    term in title or term in headings or term in tags
                    or term in category or term in subcategory or term in topic
                )
                if count or metadata_match:
                    matched_terms.append(term)
                if not count:
                    if term in title:
                        score += 5.0
                    elif term in headings:
                        score += 3.5
                    elif term in tags:
                        score += 2.5
                    elif term in category or term in subcategory:
                        score += 2.5
                    elif term in topic:
                        score += 2.0
                    continue
                frequency = document_frequency.get(term, 0)
                idf = math.log(1.0 + (total_chunks - frequency + 0.5) / (frequency + 0.5))
                saturation = (count * 2.2) / (
                    count + 1.2 * (0.65 + 0.35 * body_length / max(average_length, 1.0))
                )
                score += idf * saturation
                if term in title:
                    score += 5.0
                if term in headings:
                    score += 3.5
                if term in tags:
                    score += 2.5
                if term in category or term in subcategory:
                    score += 2.5
                if term in topic:
                    score += 2.0
            match_coverage = (
                len(set(matched_terms)) / len(terms) if terms else 1.0
            )
            if terms:
                score += 4.0 * match_coverage
            doc_platform = cls._normalize_platform(document.platform)
            if allowed and doc_platform in allowed:
                score += 1.5
            if not terms and not phrase:
                score = 0.1
            if score <= 0:
                continue
            ranked.append((score * max(document.confidence, 0.01), document))
        ranked.sort(key=lambda item: (-item[0], item[1].document_id))
        results = []
        seen_documents: set[str] = set()
        for score, document in ranked:
            if document.document_id in seen_documents:
                continue
            seen_documents.add(document.document_id)
            results.append(
                KnowledgeDocument(
                    **{
                        **document.__dict__,
                        "excerpt": cls._SENSITIVE_TERMS.sub(
                            "<redacted>", cls._relevant_excerpt(
                                document.excerpt, query, max_excerpt_chars
                            )
                        ),
                        "score": round(score, 6),
                        "retrieval_method": (
                            "sqlite_fts5_bm25" if fts_hits is not None else document.retrieval_method
                        ),
                        "matched_terms": tuple(dict.fromkeys(matched_terms)),
                        "match_coverage": round(match_coverage, 4),
                    }
                )
            )
            if len(results) >= limit:
                break
        return results

    @classmethod
    def _relevant_excerpt(cls, text: str, query: str, max_chars: int) -> str:
        value = str(text or "").strip()
        if len(value) <= max_chars:
            return value
        normalised_query = cls._normalise_text(query)
        normalised_value = cls._normalise_text(value)
        position = normalised_value.find(normalised_query) if normalised_query else -1
        if position < 0:
            for term in cls._terms(query, None):
                position = normalised_value.find(cls._normalise_text(term))
                if position >= 0:
                    break
        if position < 0:
            return value[:max_chars].rstrip() + "…"
        start = max(0, position - max_chars // 3)
        end = min(len(value), start + max_chars)
        if start > 0:
            line_start = value.find("\n", start)
            start = line_start + 1 if line_start >= 0 else start
        excerpt = value[start:end].strip()
        return ("…" if start > 0 else "") + excerpt + ("…" if end < len(value) else "")

    def validate(self) -> list[dict[str, Any]]:
        """Validate Wiki metadata without requiring an external parser."""
        issues: list[dict[str, Any]] = []
        for document in self._documents:
            if not document.document_id or not document.title:
                issues.append({"document_id": document.document_id, "error": "id/title required"})
            if document.layer not in WIKI_LAYERS:
                issues.append({"document_id": document.document_id, "error": "invalid layer"})
            if not document.source_ref:
                issues.append({"document_id": document.document_id, "error": "source_ref required"})
        return issues


def load_markdown_wiki(base_path: str | Path) -> MarkdownWikiKnowledgeProvider:
    """Factory used by management/CLI code without exposing implementation details."""
    return MarkdownWikiKnowledgeProvider(base_path)
