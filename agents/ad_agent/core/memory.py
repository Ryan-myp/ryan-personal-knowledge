"""Provider-neutral Agent Memory contracts and policy.

Memory is deliberately separate from the Markdown Wiki, session state and
tool audit.  The Runtime may recall bounded, tenant/user-scoped records, but a
memory record can never grant a Tool, permission, account or credential.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable, Optional, Protocol


MEMORY_KINDS = {"working", "semantic", "episodic", "procedural"}
MEMORY_STATUSES = {"active", "superseded", "deleted"}


@dataclass(frozen=True)
class MemoryRecord:
    memory_id: str
    tenant_id: str
    user_id: str
    kind: str
    content: str
    source: str
    session_id: Optional[str] = None
    tags: tuple[str, ...] = field(default_factory=tuple)
    importance: float = 0.5
    confidence: float = 1.0
    created_at: str = ""
    updated_at: str = ""
    expires_at: Optional[str] = None
    status: str = "active"
    score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "memory_id": self.memory_id,
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "kind": self.kind,
            "content": self.content,
            "source": self.source,
            "session_id": self.session_id,
            "tags": list(self.tags),
            "importance": self.importance,
            "confidence": self.confidence,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "expires_at": self.expires_at,
            "status": self.status,
            "score": self.score,
        }

    def to_context_dict(self) -> dict[str, Any]:
        """Public/LLM-safe view; scope identifiers stay in the backend boundary."""
        return {
            "memory_id": self.memory_id,
            "kind": self.kind,
            "content": self.content,
            "source": self.source,
            "session_id": self.session_id,
            "tags": list(self.tags),
            "importance": self.importance,
            "confidence": self.confidence,
            "updated_at": self.updated_at,
            "score": self.score,
        }


class MemoryStore(Protocol):
    """Persistence contract; implementations may be SQLite/MySQL/etc."""

    def save_memory(self, record: MemoryRecord) -> None: ...

    def search_memories(
        self,
        query: str,
        *,
        tenant_id: str,
        user_id: str,
        session_id: Optional[str] = None,
        kinds: Optional[Iterable[str]] = None,
        limit: int = 10,
    ) -> list[MemoryRecord]: ...

    def delete_memory(self, memory_id: str, *, tenant_id: str, user_id: str) -> bool: ...


class MemoryManager:
    """Safe policy layer over the backend-neutral memory contract."""

    _SECRET_RE = re.compile(
        r"(?i)(?:access[_ -]?token|refresh[_ -]?token|developer[_ -]?token|"
        r"client[_ -]?(?:secret|id)|app[_ -]?secret|private[_ -]?key|"
        r"authorization|password|credentials?|bc[_ -]?id|mcc|partner[_ -]?id)"
        r"\s*[:=]\s*[^\s,;]+"
    )
    _EXPLICIT_MEMORY_RE = re.compile(
        r"(?is)^(?:请)?(?:记住|记一下|保存|牢记|remember|save)\s*(?:我)?(?:的)?[：:\s]*(.+)$"
    )

    def __init__(self, store: MemoryStore):
        self.store = store

    @staticmethod
    def _bounded(value: Any, default: float) -> float:
        try:
            return max(0.0, min(1.0, float(value)))
        except (TypeError, ValueError):
            return default

    @classmethod
    def _safe_content(cls, content: str) -> str:
        text = str(content or "").strip()
        if not text:
            raise ValueError("memory content cannot be empty")
        # Never retain a credential-looking value.  Redaction keeps an audit-
        # safe trace while making the write policy fail closed for secrets.
        text = cls._SECRET_RE.sub("<redacted>", text)
        return text[:4000]

    def remember(
        self,
        content: str,
        *,
        tenant_id: str,
        user_id: str,
        kind: str = "semantic",
        source: str = "user_explicit",
        session_id: Optional[str] = None,
        tags: Optional[Iterable[str]] = None,
        importance: float = 0.5,
        confidence: float = 1.0,
        memory_id: Optional[str] = None,
        expires_at: Optional[str] = None,
    ) -> MemoryRecord:
        normalized_kind = str(kind or "semantic").strip().lower()
        if normalized_kind not in MEMORY_KINDS:
            raise ValueError(f"unsupported memory kind: {kind}")
        now = datetime.now(timezone.utc).isoformat()
        record = MemoryRecord(
            memory_id=str(memory_id or uuid.uuid4()),
            tenant_id=str(tenant_id or "default"),
            user_id=str(user_id or "anonymous"),
            kind=normalized_kind,
            content=self._safe_content(content),
            source=str(source or "unknown")[:200],
            session_id=str(session_id) if session_id else None,
            tags=tuple(dict.fromkeys(str(tag).strip() for tag in (tags or []) if str(tag).strip()))[:20],
            importance=self._bounded(importance, 0.5),
            confidence=self._bounded(confidence, 1.0),
            created_at=now,
            updated_at=now,
            expires_at=expires_at,
        )
        self.store.save_memory(record)
        return record

    def recall(
        self,
        query: str,
        *,
        tenant_id: str,
        user_id: str,
        session_id: Optional[str] = None,
        kinds: Optional[Iterable[str]] = None,
        limit: int = 5,
    ) -> list[MemoryRecord]:
        if limit <= 0:
            return []
        return self.store.search_memories(
            str(query or "")[:2000],
            tenant_id=str(tenant_id or "default"),
            user_id=str(user_id or "anonymous"),
            session_id=session_id,
            kinds=kinds,
            limit=min(int(limit), 20),
        )

    def build_context(
        self,
        query: str,
        *,
        tenant_id: str,
        user_id: str,
        session_id: Optional[str] = None,
        max_chars: int = 2400,
    ) -> tuple[list[dict[str, Any]], str]:
        records = self.recall(
            query,
            tenant_id=tenant_id,
            user_id=user_id,
            session_id=session_id,
            limit=5,
        )
        context = "\n\n".join(
            f"[memory:{record.kind}] {record.content} "
            f"(source={record.source}, confidence={record.confidence:.2f})"
            for record in records
        )[:max(0, int(max_chars))]
        return [record.to_context_dict() for record in records], context

    def forget(self, memory_id: str, *, tenant_id: str, user_id: str) -> bool:
        return self.store.delete_memory(
            str(memory_id), tenant_id=str(tenant_id or "default"), user_id=str(user_id or "anonymous")
        )

    @classmethod
    def explicit_memory_text(cls, user_input: str) -> Optional[str]:
        match = cls._EXPLICIT_MEMORY_RE.match(str(user_input or "").strip())
        return cls._safe_content(match.group(1)) if match else None
