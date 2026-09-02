"""Provider-neutral, Markdown-first LLM Wiki knowledge contracts.

The ad-agent knowledge base intentionally follows the simple LLM Wiki model:
human-readable Markdown files, an ``index.md`` map and a ``log.md`` history.
There is no vector database or executable knowledge plug-in.  This module is
the one runtime retrieval boundary; callers should depend on
``KnowledgeProvider`` instead of scanning the Wiki themselves.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Optional, Protocol

from .platform import declared_platforms, normalize_platform


WIKI_SCHEMA_VERSION = "1"
WIKI_LAYERS = {"platform", "business", "experience", "dynamic", "index"}
WIKI_STATUSES = {"draft", "published", "deprecated"}


@dataclass(frozen=True)
class KnowledgeDocument:
    """A bounded, source-addressable Wiki result.

    The first fields remain source-compatible with the original Runtime
    contract.  The metadata fields make the Markdown Wiki self-describing and
    allow the same document to be consumed by Runtime, CLI and evaluations.
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
    source_ref: str = ""
    tags: tuple[str, ...] = field(default_factory=tuple)
    status: str = "published"
    schema_version: str = WIKI_SCHEMA_VERSION
    score: float = 0.0

    @property
    def citation(self) -> dict[str, Any]:
        """Return a stable citation without exposing the full document."""
        return {
            "document_id": self.document_id,
            "title": self.title or self.topic,
            "source": self.source,
            "source_ref": self.source_ref or self.source,
            "version": self.version,
            "updated_at": self.updated_at,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "document_id": self.document_id,
            "platform": self.platform,
            "topic": self.topic,
            "title": self.title or self.topic,
            "layer": self.layer,
            "knowledge_type": self.knowledge_type,
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

    Retrieval is deliberately lexical and deterministic: exact phrase,
    metadata, title and token matches are scored without embeddings.  This is
    appropriate for the requested Markdown-only Wiki and leaves the
    provider-neutral contract open for a future backend if needed.
    """

    _SENSITIVE_TERMS = re.compile(
        r"(?i)\b(?:access[_ -]?token|refresh[_ -]?token|developer[_ -]?token|"
        r"private[_ -]?key|client[_ -]?(?:id|secret)|authorization|credentials?|"
        r"partner(?:[_ -]?id)?|perter(?:[_ -]?id)?|bc[_ -]?id|mcc)\w*\b"
    )
    _TOKEN_RE = re.compile(r"[\u4e00-\u9fff]{2,}|[a-z0-9_]{2,}")

    def __init__(self, base_path: str | Path):
        self.base_path = Path(base_path).resolve()
        self._documents: list[KnowledgeDocument] = []
        self._load()

    @property
    def documents(self) -> tuple[KnowledgeDocument, ...]:
        return tuple(self._documents)

    def _load(self) -> None:
        self._documents = []
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
            self._documents.append(
                KnowledgeDocument(
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
                    source_ref=source_ref,
                    tags=tuple(_as_list(metadata.get("tags"))),
                    status=status,
                    schema_version=str(metadata.get("schema_version") or WIKI_SCHEMA_VERSION),
                )
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
    def _normalize_platform(platform: str) -> str:
        value = str(platform or "all").strip().lower()
        return "all" if value == "all" else normalize_platform(value)

    @classmethod
    def _terms(cls, query: str, intent_type: Optional[str]) -> list[str]:
        text = f"{query or ''} {intent_type or ''}".lower()
        terms: list[str] = []
        for token in cls._TOKEN_RE.findall(text):
            terms.append(token)
            if re.fullmatch(r"[\u4e00-\u9fff]+", token) and len(token) > 2:
                terms.extend(token[index:index + 2] for index in range(len(token) - 1))
        return list(dict.fromkeys(terms))

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
        known.update(declared_platforms())
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
        allowed = self._effective_platforms(query, self._documents, platforms)
        allowed_types = {str(item).strip().lower() for item in (knowledge_types or []) if item}
        terms = self._terms(query, intent_type)
        phrase = str(query or "").strip().lower()
        ranked: list[tuple[float, KnowledgeDocument]] = []
        for document in self._documents:
            if document.status != "published":
                continue
            doc_platform = self._normalize_platform(document.platform)
            # Once a platform is explicit or inferred from the query, keep
            # universal documents out of the result set as well. Universal
            # Wiki pages often contain sections for several channels; using
            # them here can make a Meta query appear to return Google facts.
            # Error references are intentionally cross-platform documents in
            # the current Wiki; retain them for the dedicated error lookup
            # compatibility path. General platform searches stay strict.
            universal_error_reference = (
                doc_platform == "all" and allowed_types == {"error_pattern"}
            )
            if allowed and doc_platform not in allowed and not universal_error_reference:
                continue
            if allowed_types and document.knowledge_type not in allowed_types:
                continue
            searchable = " ".join((document.title, document.topic, document.excerpt, *document.tags)).lower()
            score = 0.0
            if phrase and phrase in searchable:
                score += 4.0
            score += sum(1.0 for term in terms if term in searchable)
            if allowed and doc_platform in allowed:
                score += 1.0
            if not terms and not phrase:
                score = 0.1
            if score <= 0:
                continue
            ranked.append((score * max(document.confidence, 0.01), document))
        ranked.sort(key=lambda item: (-item[0], item[1].document_id))
        results = []
        for score, document in ranked[:limit]:
            results.append(
                KnowledgeDocument(
                    **{
                        **document.__dict__,
                        "excerpt": self._SENSITIVE_TERMS.sub(
                            "<redacted>", document.excerpt[:max_excerpt_chars]
                        ),
                        "score": round(score, 6),
                    }
                )
            )
        return results

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


# Backward-compatible name for callers that already injected the local Wiki
# provider.  It is an alias, not a second implementation.
LocalMarkdownKnowledgeProvider = MarkdownWikiKnowledgeProvider


def load_markdown_wiki(base_path: str | Path) -> MarkdownWikiKnowledgeProvider:
    """Factory used by management/CLI code without exposing implementation details."""
    return MarkdownWikiKnowledgeProvider(base_path)
