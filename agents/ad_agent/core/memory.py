"""Provider-neutral Agent Memory contracts and policy.

Memory is deliberately separate from the Markdown Wiki, session state and
tool audit.  The Runtime may recall bounded, tenant/user-scoped records, but a
memory record can never grant a Tool, permission, account or credential.
"""

from __future__ import annotations

import hashlib
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
    memory_key: Optional[str] = None
    superseded_by: Optional[str] = None
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
            "memory_key": self.memory_key,
            "superseded_by": self.superseded_by,
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
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "status": self.status,
            "memory_key": self.memory_key,
            "superseded_by": self.superseded_by,
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

    def find_active_memory(
        self, memory_key: str, *, tenant_id: str, user_id: str,
    ) -> Optional[MemoryRecord]: ...

    def supersede_memory(
        self, memory_id: str, superseded_by: str, *, tenant_id: str, user_id: str,
    ) -> bool: ...


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
    _AUTO_MEMORY_PATTERNS = (
        ("preference", re.compile(
            r"(?is)^(?:我的|我们(?:团队)?的)?(?:偏好|习惯)(?:是|为)?[：:\s]*(?P<content>.+)$"
        )),
        ("default", re.compile(
            r"(?is)^默认(?:使用|采用|选择)?[：:\s]*(?P<content>.+)$"
        )),
        ("follow_up_preference", re.compile(
            r"(?is)^(?:以后|后续|接下来)(?:请|都)?[：:\s]*(?P<content>(?:使用|优先|采用|选择|按|不要|避免).+)$"
        )),
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

    @staticmethod
    def _content_fingerprint(content: str) -> str:
        normalized = " ".join(str(content or "").strip().lower().split())
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:32]

    @classmethod
    def _safe_memory_key(cls, memory_key: Optional[str], content: str) -> str:
        value = str(memory_key or "").strip().lower()
        if not value:
            return f"content:{cls._content_fingerprint(content)}"
        value = re.sub(r"[^a-z0-9._:/-]+", "-", value)
        return value[:120] or f"content:{cls._content_fingerprint(content)}"

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
        memory_key: Optional[str] = None,
    ) -> MemoryRecord:
        normalized_kind = str(kind or "semantic").strip().lower()
        if normalized_kind not in MEMORY_KINDS:
            raise ValueError(f"unsupported memory kind: {kind}")
        safe_content = self._safe_content(content)
        normalized_key = self._safe_memory_key(memory_key, safe_content)
        scope_tenant = str(tenant_id or "default")
        scope_user = str(user_id or "anonymous")
        # Older embedding/test backends may implement the original memory
        # contract without versioning. They remain usable; conflict handling
        # is enabled automatically when the optional methods are present.
        find_active = getattr(self.store, "find_active_memory", None)
        existing = find_active(
            normalized_key, tenant_id=scope_tenant, user_id=scope_user,
        ) if callable(find_active) else None
        now = datetime.now(timezone.utc).isoformat()
        next_memory_id = str(memory_id or uuid.uuid4())
        if existing and existing.content.strip().lower() == safe_content.strip().lower():
            next_memory_id = existing.memory_id
            created_at = existing.created_at or now
        else:
            created_at = now
            if existing:
                supersede = getattr(self.store, "supersede_memory", None)
                if callable(supersede):
                    supersede(
                        existing.memory_id, next_memory_id,
                        tenant_id=scope_tenant, user_id=scope_user,
                    )
        record = MemoryRecord(
            memory_id=next_memory_id,
            tenant_id=scope_tenant,
            user_id=scope_user,
            kind=normalized_kind,
            content=safe_content,
            source=str(source or "unknown")[:200],
            session_id=str(session_id) if session_id else None,
            tags=tuple(dict.fromkeys(str(tag).strip() for tag in (tags or []) if str(tag).strip()))[:20],
            importance=self._bounded(importance, 0.5),
            confidence=self._bounded(confidence, 1.0),
            created_at=created_at,
            updated_at=now,
            expires_at=expires_at,
            memory_key=normalized_key,
        )
        self.store.save_memory(record)
        return record

    @classmethod
    def extract_candidates(cls, user_input: str) -> list[dict[str, Any]]:
        """Extract only high-confidence preference-like memory candidates.

        Automatic memory is intentionally conservative: ordinary questions,
        provider results and assistant prose are never promoted. Explicit
        ``请记住`` requests always win; the other patterns cover stable user
        preferences without adding an LLM call to every turn.
        """
        text = str(user_input or "").strip()
        if not text:
            return []
        explicit = cls.explicit_memory_text(text)
        if explicit:
            return [{
                "content": explicit, "kind": "semantic", "source": "user_explicit",
                "importance": 0.85, "confidence": 1.0,
                "memory_key": f"explicit:{cls._content_fingerprint(explicit)}",
            }]
        for category, pattern in cls._AUTO_MEMORY_PATTERNS:
            match = pattern.match(text)
            if not match:
                continue
            content = cls._safe_content(match.group("content"))
            if len(content) < 2:
                continue
            return [{
                "content": content, "kind": "semantic", "source": "auto_preference",
                "importance": 0.7, "confidence": 0.86,
                "memory_key": f"{category}:{cls._content_fingerprint(content)}",
            }]
        return []

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
