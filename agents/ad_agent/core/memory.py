"""Application-neutral Agent Memory contracts and policy.

Memory is deliberately separate from the Markdown Wiki, session state and
tool audit.  The Runtime may recall bounded, tenant/user-scoped records, but a
memory record can never grant a Tool, permission, scope or credential.
"""

from __future__ import annotations

import hashlib
import re
import threading
import time
import uuid
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable, Optional, Protocol

from .security import redact_sensitive_text


MEMORY_KINDS = {"working", "semantic", "episodic", "procedural"}
LONG_TERM_MEMORY_KINDS = frozenset({"semantic", "episodic", "procedural"})
MEMORY_STATUSES = {"active", "superseded", "deleted"}
AUTO_EPISODIC_EVENT_TYPES = frozenset({
    "confirmation_completed",
    "operation_succeeded",
    "operation_failed",
    "recovery_required",
    "validation_failed",
})
MEMORY_SOURCE_PRIORITIES = {
    "api_explicit": 100,
    "user_explicit": 100,
    "user_explicit_procedure": 100,
    "user_explicit_episode": 100,
    "user_procedure": 95,
    "runtime_episode": 60,
    "runtime_automatic": 40,
}


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

    def purge_memories(self, *, before: str, expired_before: str) -> int: ...


class MemoryManager:
    """Safe policy layer over the backend-neutral memory contract."""

    _EXPLICIT_MEMORY_RE = re.compile(
        r"(?is)^(?:请)?(?:记住|记一下|保存|牢记|remember|save)\s*(?:我)?(?:的)?[：:\s]*(.+)$"
    )
    _EXPLICIT_PROCEDURE_RE = re.compile(
        r"(?is)^(?:请)?(?:记住|记一下|保存|牢记|remember|save)\s*"
        r"(?:这个|该)?(?:流程|步骤|操作方法|规则)[：:\s]*(?P<content>.+)$"
    )
    _EXPLICIT_EPISODE_RE = re.compile(
        r"(?is)^(?:请)?(?:记住|记一下|保存|牢记|remember|save)\s*"
        r"(?:这次|本次|刚才这次)(?:操作|事件|结果|经历)?[：:\s]*(?P<content>.+)$"
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

    def __init__(
        self,
        store: MemoryStore,
        *,
        cache_ttl_seconds: float = 5.0,
        max_cache_entries: int = 256,
        auto_capture_enabled: bool = True,
        auto_episode_ttl_days: int = 90,
    ):
        self.store = store
        if cache_ttl_seconds < 0:
            raise ValueError("cache_ttl_seconds cannot be negative")
        if max_cache_entries <= 0:
            raise ValueError("max_cache_entries must be positive")
        if auto_episode_ttl_days <= 0:
            raise ValueError("auto_episode_ttl_days must be positive")
        self._cache_ttl_seconds = float(cache_ttl_seconds)
        self._max_cache_entries = int(max_cache_entries)
        self._auto_capture_enabled = bool(auto_capture_enabled)
        self._auto_episode_ttl_days = int(auto_episode_ttl_days)
        self._recall_cache: OrderedDict[
            tuple[str, str, Optional[str], tuple[str, ...], str, int],
            tuple[float, tuple[MemoryRecord, ...]],
        ] = OrderedDict()
        self._cache_lock = threading.RLock()
        self._cache_hits = 0
        self._cache_misses = 0
        self._cache_evictions = 0
        self._cache_invalidations = 0

    @property
    def auto_capture_enabled(self) -> bool:
        """Whether runtime events may be promoted to episodic memory."""
        return self._auto_capture_enabled

    def set_auto_capture_enabled(self, enabled: bool) -> None:
        """Change automatic capture policy without changing explicit writes."""
        self._auto_capture_enabled = bool(enabled)

    @staticmethod
    def _scope_value(value: Any, default: str) -> str:
        return str(value or default).strip() or default

    @classmethod
    def _cache_query_key(
        cls,
        query: str,
        *,
        tenant_id: str,
        user_id: str,
        session_id: Optional[str],
        kinds: Optional[Iterable[str]],
        limit: int,
    ) -> tuple[str, str, Optional[str], tuple[str, ...], str, int]:
        normalized_kinds = tuple(sorted({
            str(kind).strip().lower()
            for kind in (kinds or [])
            if str(kind).strip()
        }))
        normalized_query = " ".join(str(query or "")[:2000].lower().split())
        return (
            cls._scope_value(tenant_id, "default"),
            cls._scope_value(user_id, "anonymous"),
            str(session_id) if session_id else None,
            normalized_kinds,
            normalized_query,
            min(max(int(limit), 0), 20),
        )

    def _invalidate_cache_scope(self, tenant_id: str, user_id: str) -> None:
        scope = (
            self._scope_value(tenant_id, "default"),
            self._scope_value(user_id, "anonymous"),
        )
        with self._cache_lock:
            keys = [
                key for key in self._recall_cache
                if key[0] == scope[0] and key[1] == scope[1]
            ]
            for key in keys:
                self._recall_cache.pop(key, None)
            if keys:
                self._cache_invalidations += len(keys)

    def cache_metrics(self) -> dict[str, Any]:
        """Expose bounded, non-sensitive cache health metrics."""
        with self._cache_lock:
            return {
                "entries": len(self._recall_cache),
                "max_entries": self._max_cache_entries,
                "ttl_seconds": self._cache_ttl_seconds,
                "hit_total": self._cache_hits,
                "miss_total": self._cache_misses,
                "eviction_total": self._cache_evictions,
                "invalidation_total": self._cache_invalidations,
            }

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
        text = redact_sensitive_text(text)
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

    @staticmethod
    def _source_priority(source: str) -> int:
        return int(MEMORY_SOURCE_PRIORITIES.get(str(source or "").strip().lower(), 50))

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
        if normalized_kind in {"working", "episodic"} and not str(session_id or "").strip():
            raise ValueError(f"{normalized_kind} memory requires session_id")
        safe_content = self._safe_content(content)
        normalized_key = self._safe_memory_key(memory_key, safe_content)
        scope_tenant = str(tenant_id or "default")
        scope_user = str(user_id or "anonymous")
        normalized_source = str(source or "unknown")[:200]
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
            if (
                existing
                and self._source_priority(normalized_source)
                < self._source_priority(existing.source)
                and existing.status == "active"
            ):
                # Automatic extraction is advisory. It may never overwrite a
                # stronger explicit user/API fact under the same logical key.
                return existing
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
            source=normalized_source,
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
        self._invalidate_cache_scope(scope_tenant, scope_user)
        return record

    def remember_procedure(
        self,
        content: str,
        *,
        tenant_id: str,
        user_id: str,
        procedure_key: str,
        tags: Optional[Iterable[str]] = None,
        importance: float = 0.75,
        confidence: float = 0.9,
        source: str = "user_procedure",
    ) -> MemoryRecord:
        """Store a user-specific procedure as advisory long-term memory.

        Procedural memory describes a preferred way of working. It never
        registers a Tool, changes permissions, or overrides a Skill.
        """
        key = self._safe_memory_key(procedure_key, content)
        return self.remember(
            content,
            tenant_id=tenant_id,
            user_id=user_id,
            kind="procedural",
            source=source,
            tags=("procedure", *(tags or ())),
            importance=importance,
            confidence=confidence,
            memory_key=f"procedure:{key}",
        )

    def remember_episode(
        self,
        content: str,
        *,
        tenant_id: str,
        user_id: str,
        session_id: str,
        event_type: str,
        outcome: Optional[str] = None,
        tags: Optional[Iterable[str]] = None,
        importance: float = 0.55,
        confidence: float = 0.85,
        source: str = "runtime_episode",
        memory_key: Optional[str] = None,
        expires_at: Optional[str] = None,
    ) -> MemoryRecord:
        """Store one session-bound event summary for later recall.

        Episodes are summaries, not raw Tool payloads. The caller must provide
        a session so an event cannot silently become tenant-global memory.
        """
        safe_event_type = re.sub(
            r"[^a-z0-9._:-]+", "-", str(event_type or "").strip().lower()
        ).strip("-")
        if not safe_event_type:
            raise ValueError("event_type cannot be empty")
        if not str(session_id or "").strip():
            raise ValueError("episodic memory requires session_id")
        episode_tags = [
            "episode",
            f"event:{safe_event_type}",
        ]
        if outcome:
            episode_tags.append(
                f"outcome:{self._safe_memory_key(outcome, outcome)}"
            )
        episode_tags.extend(tags or ())
        event_key = memory_key or (
            f"episode:{safe_event_type}:{self._content_fingerprint(content)}"
        )
        return self.remember(
            content,
            tenant_id=tenant_id,
            user_id=user_id,
            kind="episodic",
            source=source,
            session_id=session_id,
            tags=episode_tags,
            importance=importance,
            confidence=confidence,
            memory_key=event_key,
            expires_at=expires_at,
        )

    def remember_runtime_event(
        self,
        summary: str,
        *,
        tenant_id: str,
        user_id: str,
        session_id: str,
        event_type: str,
        dedupe_key: str,
        outcome: Optional[str] = None,
        tags: Optional[Iterable[str]] = None,
        importance: float = 0.55,
        confidence: float = 0.8,
    ) -> Optional[MemoryRecord]:
        """Capture one allowlisted, sanitized runtime event.

        Automatic capture is intentionally narrower than ``remember``:
        only high-value lifecycle events are accepted, every event is bound
        to a session, and a caller-provided dedupe key makes persistence
        idempotent across retry/replay of the same turn. The summary is the
        only retained payload; raw Tool input/output never enters memory.
        """
        if not self._auto_capture_enabled:
            return None
        normalized_event = re.sub(
            r"[^a-z0-9._:-]+", "-", str(event_type or "").strip().lower()
        ).strip("-")
        if normalized_event not in AUTO_EPISODIC_EVENT_TYPES:
            return None
        normalized_dedupe = re.sub(
            r"[^a-z0-9._:-]+", "-", str(dedupe_key or "").strip().lower()
        ).strip("-")
        if not normalized_dedupe:
            raise ValueError("dedupe_key cannot be empty")
        expiry = datetime.now(timezone.utc).timestamp() + (
            self._auto_episode_ttl_days * 86400
        )
        expires_at = datetime.fromtimestamp(
            expiry, tz=timezone.utc
        ).isoformat()
        event_tags = [
            "auto",
            f"event:{normalized_event}",
        ]
        event_tags.extend(tags or ())
        return self.remember_episode(
            summary,
            tenant_id=tenant_id,
            user_id=user_id,
            session_id=session_id,
            event_type=normalized_event,
            outcome=outcome,
            tags=event_tags,
            importance=importance,
            confidence=confidence,
            source="runtime_automatic",
            memory_key=f"runtime:{normalized_event}:{normalized_dedupe}",
            expires_at=expires_at,
        )

    @classmethod
    def extract_candidates(cls, user_input: str) -> list[dict[str, Any]]:
        """Extract only high-confidence preference-like memory candidates.

        Automatic memory is intentionally conservative: ordinary questions,
        external results and assistant prose are never promoted. Explicit
        ``请记住`` requests always win; the other patterns cover stable user
        preferences without adding an LLM call to every turn.
        """
        text = str(user_input or "").strip()
        if not text:
            return []
        explicit = cls.explicit_memory_text(text)
        procedure_match = cls._EXPLICIT_PROCEDURE_RE.match(text)
        if procedure_match:
            content = cls._safe_content(procedure_match.group("content"))
            return [{
                "content": content,
                "kind": "procedural",
                "source": "user_explicit_procedure",
                "importance": 0.8,
                "confidence": 0.95,
                "memory_key": f"procedure:{cls._content_fingerprint(content)}",
            }]
        episode_match = cls._EXPLICIT_EPISODE_RE.match(text)
        if episode_match:
            content = cls._safe_content(episode_match.group("content"))
            return [{
                "content": content,
                "kind": "episodic",
                "source": "user_explicit_episode",
                "importance": 0.6,
                "confidence": 0.9,
                "memory_key": f"episode:{cls._content_fingerprint(content)}",
                "session_bound": True,
            }]
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

    def recall_long_term(
        self,
        query: str,
        *,
        tenant_id: str,
        user_id: str,
        session_id: Optional[str] = None,
        kinds: Optional[Iterable[str]] = None,
        limit: int = 5,
    ) -> list[MemoryRecord]:
        """Recall only durable semantic, procedural and episodic memory."""
        selected = tuple(
            kind for kind in (kinds or LONG_TERM_MEMORY_KINDS)
            if str(kind).strip().lower() in LONG_TERM_MEMORY_KINDS
        )
        return self.recall(
            query,
            tenant_id=tenant_id,
            user_id=user_id,
            session_id=session_id,
            kinds=selected,
            limit=limit,
        )

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
        normalized_limit = min(int(limit), 20)
        scope_tenant = self._scope_value(tenant_id, "default")
        scope_user = self._scope_value(user_id, "anonymous")
        normalized_kinds = tuple(sorted({
            str(kind).strip().lower()
            for kind in (kinds or [])
            if str(kind).strip()
        }))
        key = self._cache_query_key(
            query,
            tenant_id=scope_tenant,
            user_id=scope_user,
            session_id=session_id,
            kinds=normalized_kinds,
            limit=normalized_limit,
        )
        now = time.monotonic()
        with self._cache_lock:
            cached = self._recall_cache.get(key)
            if cached is not None:
                expires_at, records = cached
                if self._cache_ttl_seconds == 0 or expires_at <= now:
                    self._recall_cache.pop(key, None)
                else:
                    self._recall_cache.move_to_end(key)
                    self._cache_hits += 1
                    return list(records)
            self._cache_misses += 1
        records = self.store.search_memories(
            str(query or "")[:2000],
            tenant_id=scope_tenant,
            user_id=scope_user,
            session_id=session_id,
            kinds=normalized_kinds,
            limit=normalized_limit,
        )
        safe_records = tuple(records or ())
        if self._cache_ttl_seconds > 0:
            with self._cache_lock:
                self._recall_cache[key] = (
                    time.monotonic() + self._cache_ttl_seconds,
                    safe_records,
                )
                self._recall_cache.move_to_end(key)
                while len(self._recall_cache) > self._max_cache_entries:
                    self._recall_cache.popitem(last=False)
                    self._cache_evictions += 1
        return list(safe_records)

    def build_context(
        self,
        query: str,
        *,
        tenant_id: str,
        user_id: str,
        session_id: Optional[str] = None,
        max_chars: int = 2400,
    ) -> tuple[list[dict[str, Any]], str]:
        records = self.recall_long_term(
            query,
            tenant_id=tenant_id,
            user_id=user_id,
            session_id=session_id,
            limit=5,
        )
        bounded_max_chars = max(0, min(int(max_chars), 2400))
        context = "\n\n".join(
            f"[memory:{record.kind}] {record.content} "
            f"(source={record.source}, confidence={record.confidence:.2f})"
            for record in records
        )[:bounded_max_chars]
        return [record.to_context_dict() for record in records], context

    def forget(self, memory_id: str, *, tenant_id: str, user_id: str) -> bool:
        deleted = self.store.delete_memory(
            str(memory_id), tenant_id=str(tenant_id or "default"), user_id=str(user_id or "anonymous")
        )
        if deleted:
            self._invalidate_cache_scope(tenant_id, user_id)
        return deleted

    def purge_memories(self, *, retention_days: int = 30) -> int:
        """Remove expired records and old tombstones through the store seam."""
        if retention_days < 0:
            raise ValueError("retention_days cannot be negative")
        purge = getattr(self.store, "purge_memories", None)
        if not callable(purge):
            return 0
        now = datetime.now(timezone.utc)
        before = (now.timestamp() - retention_days * 86400)
        # Existing SQLite/MySQL adapters store lifecycle timestamps in both
        # naive and offset-aware ISO forms. Use a normalized naive boundary
        # for the persistence comparison; expiry values remain interpreted
        # by the backend's existing recall policy.
        before_iso = datetime.fromtimestamp(
            before, tz=timezone.utc
        ).replace(tzinfo=None).isoformat()
        expired_before = now.replace(tzinfo=None).isoformat()
        removed = int(purge(before=before_iso, expired_before=expired_before) or 0)
        if removed:
            with self._cache_lock:
                self._recall_cache.clear()
        return removed

    @classmethod
    def explicit_memory_text(cls, user_input: str) -> Optional[str]:
        match = cls._EXPLICIT_MEMORY_RE.match(str(user_input or "").strip())
        return cls._safe_content(match.group(1)) if match else None
