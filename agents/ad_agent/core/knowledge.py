"""Read-only knowledge context contracts for the ad-agent runtime.

Knowledge is advisory input for intent parsing and user-facing explanations.
It is deliberately not coupled to ToolRegistry, permissions, approvals, or
workflow execution.  Providers can later be replaced by a search service or
database without changing the Runtime contract.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Optional, Protocol


@dataclass(frozen=True)
class KnowledgeDocument:
    """A bounded, source-addressable knowledge result."""

    document_id: str
    platform: str
    topic: str
    excerpt: str
    source: str
    version: str
    confidence: float
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "document_id": self.document_id,
            "platform": self.platform,
            "topic": self.topic,
            "excerpt": self.excerpt,
            "source": self.source,
            "version": self.version,
            "confidence": self.confidence,
            "updated_at": self.updated_at,
        }


class KnowledgeProvider(Protocol):
    """Read-only provider used to build bounded model context."""

    def query(
        self,
        query: str,
        *,
        platforms: Optional[Iterable[str]] = None,
        intent_type: Optional[str] = None,
        limit: int = 4,
        max_excerpt_chars: int = 1200,
    ) -> list[KnowledgeDocument]:
        ...


class LocalMarkdownKnowledgeProvider:
    """Safe local Markdown provider for the checked-in ad-agent KB.

    The provider only reads files below ``base_path``.  It exposes excerpts
    and provenance, never arbitrary file contents or write operations.
    """

    _ALIASES = {"google": "google", "google-ads": "google", "google_ads": "google"}
    _SENSITIVE_TERMS = re.compile(
        r"(?i)\b(?:access[_ -]?token|refresh[_ -]?token|developer[_ -]?token|"
        r"private[_ -]?key|client[_ -]?(?:id|secret)|authorization|credentials?|"
        r"partner(?:[_ -]?id)?|perter(?:[_ -]?id)?|bc[_ -]?id|mcc)\w*\b"
    )

    def __init__(self, base_path: str | Path):
        self.base_path = Path(base_path).resolve()
        self._documents: list[KnowledgeDocument] = []
        self._load()

    def _load(self) -> None:
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
            parts = relative.parts
            platform = parts[1] if len(parts) > 2 and parts[0] == "platforms" else "all"
            topic = path.stem
            metadata, body = self._frontmatter(content)
            source = str(metadata.get("source") or metadata.get("来源") or relative)
            version = str(metadata.get("version") or "local-markdown")
            updated_at = str(
                metadata.get("updated_at")
                or metadata.get("updated")
                or stat.st_mtime
            )
            self._documents.append(
                KnowledgeDocument(
                    document_id=f"{platform}:{relative.as_posix()}",
                    platform=platform,
                    topic=topic,
                    excerpt=body,
                    source=source,
                    version=version,
                    confidence=1.0,
                    updated_at=updated_at,
                )
            )

    @staticmethod
    def _frontmatter(content: str) -> tuple[dict[str, Any], str]:
        if not content.startswith("---"):
            return {}, content
        match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", content, re.DOTALL)
        if not match:
            return {}, content
        metadata: dict[str, Any] = {}
        for line in match.group(1).splitlines():
            if ":" in line:
                key, value = line.split(":", 1)
                metadata[key.strip()] = value.strip().strip('"')
        return metadata, match.group(2)

    @classmethod
    def _normalize_platform(cls, platform: str) -> str:
        value = str(platform or "all").lower()
        return cls._ALIASES.get(value, value)

    @staticmethod
    def _terms(query: str, intent_type: Optional[str]) -> list[str]:
        text = f"{query or ''} {intent_type or ''}".lower()
        # Keep CJK words whole enough for substring matching while handling
        # normal English tool/field terms as separate tokens.
        terms = re.findall(r"[\u4e00-\u9fff]{2,}|[a-z0-9_]{2,}", text)
        return list(dict.fromkeys(terms))

    def query(
        self,
        query: str,
        *,
        platforms: Optional[Iterable[str]] = None,
        intent_type: Optional[str] = None,
        limit: int = 4,
        max_excerpt_chars: int = 1200,
    ) -> list[KnowledgeDocument]:
        if limit <= 0 or max_excerpt_chars <= 0:
            return []
        allowed = {
            self._normalize_platform(platform)
            for platform in (platforms or [])
            if platform
        }
        terms = self._terms(query, intent_type)
        ranked: list[tuple[int, KnowledgeDocument]] = []
        for document in self._documents:
            document_platform = self._normalize_platform(document.platform)
            if allowed and document_platform not in allowed and document_platform != "all":
                continue
            haystack = f"{document.topic} {document.excerpt}".lower()
            score = sum(1 for term in terms if term in haystack)
            if score == 0 and terms:
                continue
            if document_platform != "all" and document_platform in allowed:
                score += 1
            ranked.append((score, document))
        ranked.sort(key=lambda item: (-item[0], item[1].document_id))
        return [
            KnowledgeDocument(
                **{
                    **document.__dict__,
                    "excerpt": self._SENSITIVE_TERMS.sub(
                        "<redacted>", document.excerpt[:max_excerpt_chars]
                    ),
                }
            )
            for _, document in ranked[:limit]
        ]
