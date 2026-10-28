"""Domain-owned memory store operations behind the persistence facade."""

from __future__ import annotations
import json
import math
import re
from datetime import datetime, timezone
from typing import Any, Optional, List
from agents.agent_harness.core.memory import MEMORY_SOURCE_PRIORITIES, MemoryRecord

_MAX_MEMORY_QUERY_CHARS = 4000


def _query_terms(query: str) -> tuple[str, ...]:
    """Build a bounded, de-duplicated lexical query for English and Chinese."""
    terms: list[str] = []
    seen: set[str] = set()
    bounded_query = str(query or "")[:_MAX_MEMORY_QUERY_CHARS].lower()
    for term in re.findall(
        r"[\u4e00-\u9fff]{2,}|[a-z0-9_]{2,}", bounded_query,
    ):
        candidates = [term]
        if re.fullmatch(r"[\u4e00-\u9fff]+", term) and len(term) > 2:
            candidates.extend(term[index:index + 2] for index in range(len(term) - 1))
        for candidate in candidates:
            if candidate not in seen:
                seen.add(candidate)
                terms.append(candidate)
    return tuple(terms)


def _lexical_match_terms(text: str) -> tuple[set[str], set[str]]:
    """Return exact Latin tokens and searchable CJK runs/bigrams."""
    lowered = str(text or "").lower()
    latin = set(re.findall(r"[a-z0-9_]{2,}", lowered))
    cjk: set[str] = set()
    for group in re.findall(r"[\u4e00-\u9fff]+", lowered):
        if len(group) >= 2:
            cjk.add(group)
            cjk.update(group[index:index + 2] for index in range(len(group) - 1))
    return latin, cjk


def _contains_phrase(text: str, phrase: str) -> bool:
    if not phrase:
        return False
    if re.search(r"[a-z0-9_]", phrase):
        pattern = rf"(?<![a-z0-9_]){re.escape(phrase)}(?![a-z0-9_])"
        return re.search(pattern, text) is not None
    return phrase in text


class MemoryRepository:
    def __init__(self, connection_provider, lock):
        self._get_conn = connection_provider
        self._lock = lock

    @staticmethod
    def _memory_from_row(row: Any, score: float = 0.0) -> MemoryRecord:
        data = dict(row)
        try:
            tags = json.loads(data.get("tags") or "[]")
        except (TypeError, ValueError):
            tags = []
        if not isinstance(tags, list):
            tags = []
        return MemoryRecord(
            memory_id=str(data["memory_id"]),
            tenant_id=str(data["tenant_id"]),
            user_id=str(data["user_id"]),
            kind=str(data["kind"]),
            content=str(data["content"]),
            source=str(data["source"]),
            session_id=data.get("session_id"),
            tags=tuple(str(tag) for tag in tags),
            importance=float(data.get("importance") or 0.5),
            confidence=float(data.get("confidence") or 1.0),
            created_at=str(data.get("created_at") or ""),
            updated_at=str(data.get("updated_at") or ""),
            expires_at=data.get("expires_at"),
            status=str(data.get("status") or "active"),
            memory_key=data.get("memory_key"),
            superseded_by=data.get("superseded_by"),
            score=score,
        )

    def save_memory(self, record: MemoryRecord) -> None:
        """Persist one already-policy-checked memory record."""
        if not isinstance(record, MemoryRecord):
            raise TypeError("record must be a MemoryRecord")
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                """INSERT OR REPLACE INTO memories
                (memory_id, tenant_id, user_id, session_id, kind, content, source,
                 tags, importance, confidence, created_at, updated_at, expires_at,
                 status, memory_key, superseded_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    record.memory_id, record.tenant_id, record.user_id,
                    record.session_id, record.kind, record.content, record.source,
                    json.dumps(list(record.tags), ensure_ascii=False), record.importance,
                    record.confidence, record.created_at, record.updated_at,
                    record.expires_at, record.status,
                    record.memory_key, record.superseded_by,
                ),
            )
            conn.commit()

    def find_active_memory(
        self, memory_key: str, *, tenant_id: str, user_id: str,
    ) -> Optional[MemoryRecord]:
        """Find the current version of one scoped logical memory."""
        with self._lock:
            row = self._get_conn().execute(
                """SELECT * FROM memories
                   WHERE tenant_id = ? AND user_id = ? AND memory_key = ?
                     AND status = 'active'
                   ORDER BY updated_at DESC LIMIT 1""",
                (str(tenant_id), str(user_id), str(memory_key)),
            ).fetchone()
            return self._memory_from_row(row) if row else None

    def supersede_memory(
        self, memory_id: str, superseded_by: str, *, tenant_id: str, user_id: str,
    ) -> bool:
        """Close an older logical version while retaining its audit history."""
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute(
                """UPDATE memories
                   SET status = 'superseded', superseded_by = ?, updated_at = ?
                   WHERE memory_id = ? AND tenant_id = ? AND user_id = ?
                     AND status = 'active'""",
                (
                    str(superseded_by), datetime.now(timezone.utc).isoformat(),
                    str(memory_id), str(tenant_id), str(user_id),
                ),
            )
            conn.commit()
            return cursor.rowcount > 0

    def search_memories(
        self, query: str, *, tenant_id: str, user_id: str,
        session_id: Optional[str] = None, kinds: Optional[List[str]] = None,
        limit: int = 10,
    ) -> List[MemoryRecord]:
        """Scope memory first, then perform deterministic lexical ranking."""
        if limit <= 0:
            return []
        params: list[Any] = [str(tenant_id), str(user_id)]
        query_sql = (
            "SELECT * FROM memories WHERE tenant_id = ? AND user_id = ? "
            "AND status = 'active'"
        )
        if session_id:
            query_sql += " AND (session_id = ? OR session_id IS NULL)"
            params.append(str(session_id))
        normalized_kinds = [str(kind).strip().lower() for kind in (kinds or []) if str(kind).strip()]
        if normalized_kinds:
            placeholders = ",".join("?" for _ in normalized_kinds)
            query_sql += f" AND kind IN ({placeholders})"
            params.extend(normalized_kinds)
        candidate_limit = max(20, min(200, int(limit) * 10))
        priority_sources = [
            source for source, priority in MEMORY_SOURCE_PRIORITIES.items()
            if priority >= 95
        ]
        recent_query = query_sql + " ORDER BY updated_at DESC LIMIT ?"
        priority_query = ""
        if priority_sources:
            placeholders = ",".join("?" for _ in priority_sources)
            priority_query = (
                query_sql + f" AND source IN ({placeholders}) "
                "ORDER BY importance DESC, updated_at DESC LIMIT ?"
            )
        # Keep recent context and explicit long-term memories in separate,
        # bounded candidate pools so routine events cannot evict saved notes.
        priority_limit = min(50, max(10, int(limit) * 5))
        # Ranking remains backend-owned and can later become a MySQL full-text query.
        terms = _query_terms(query)
        phrase = str(query or "")[:_MAX_MEMORY_QUERY_CHARS].strip().lower()
        ranked: list[tuple[float, float, MemoryRecord]] = []
        half_life_days = {
            "working": 2.0,
            "episodic": 14.0,
            "semantic": 45.0,
            "procedural": 120.0,
        }
        now = datetime.now(timezone.utc)
        with self._lock:
            conn = self._get_conn()
            recent_rows = conn.execute(
                recent_query, [*params, candidate_limit],
            ).fetchall()
            rows_by_id = {str(row["memory_id"]): row for row in recent_rows}
            if priority_query:
                priority_rows = conn.execute(
                    priority_query,
                    [*params, *priority_sources, priority_limit],
                ).fetchall()
                rows_by_id.update({
                    str(row["memory_id"]): row for row in priority_rows
                })
            rows = list(rows_by_id.values())
        for row in rows:
            expires_at = row["expires_at"]
            if expires_at:
                try:
                    expiry = datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
                    if expiry.tzinfo is None:
                        expiry = expiry.replace(tzinfo=timezone.utc)
                    if expiry <= now:
                        continue
                except (TypeError, ValueError, OverflowError):
                    # Invalid expiry is safer treated as expired than recalled.
                    continue
            record = self._memory_from_row(row)
            content = str(record.content or "").lower()
            tags = " ".join(record.tags).lower()
            searchable = f"{content} {tags}"
            score = 0.0
            if _contains_phrase(searchable, phrase):
                score += 3.0
            content_latin, content_cjk = _lexical_match_terms(content)
            tag_latin, tag_cjk = _lexical_match_terms(tags)
            matched_terms = 0
            for term in terms:
                cjk_term = bool(re.fullmatch(r"[\u4e00-\u9fff]+", term))
                content_match = (
                    term in content_cjk if cjk_term else term in content_latin
                )
                tag_match = term in tag_cjk if cjk_term else term in tag_latin
                if content_match:
                    score += 1.0
                    matched_terms += 1
                elif tag_match:
                    score += 0.75
                    matched_terms += 1
            if terms and matched_terms:
                score += 2.0 * matched_terms / len(terms)
            if not terms and not phrase:
                score = 0.1
            if score <= 0:
                continue
            try:
                updated_at = datetime.fromisoformat(
                    str(record.updated_at).replace("Z", "+00:00")
                )
                if updated_at.tzinfo is None:
                    updated_at = updated_at.replace(tzinfo=timezone.utc)
                age_days = max(0.0, (now - updated_at).total_seconds() / 86400.0)
                updated_at_rank = updated_at.timestamp()
            except (OSError, TypeError, ValueError, OverflowError):
                age_days = 3650.0
                updated_at_rank = 0.0
            half_life = half_life_days.get(record.kind, 30.0)
            recency = math.pow(0.5, age_days / half_life)
            source_priority = MEMORY_SOURCE_PRIORITIES.get(record.source, 50)
            source_weight = 0.75 + 0.25 * max(
                0.0, min(1.0, source_priority / 100.0)
            )
            score = (
                score * (0.7 + 0.3 * recency) * source_weight
                + record.importance * 0.5
                + record.confidence * 0.5
            )
            ranked.append((score, updated_at_rank, record))
        ranked.sort(key=lambda item: (-item[0], -item[1], item[2].memory_id))
        return [
            MemoryRecord(**{**record.__dict__, "score": round(score, 6)})
            for score, _updated_at, record in ranked[: int(limit)]
        ]

    def delete_memory(self, memory_id: str, *, tenant_id: str, user_id: str) -> bool:
        """Tombstone a record; a tenant/user can never delete another scope."""
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute(
                "UPDATE memories SET status = 'deleted', updated_at = ? "
                "WHERE memory_id = ? AND tenant_id = ? AND user_id = ? AND status != 'deleted'",
                (
                    datetime.now(timezone.utc).isoformat(),
                    str(memory_id),
                    str(tenant_id),
                    str(user_id),
                ),
            )
            conn.commit()
            return cursor.rowcount > 0

    def purge_memories(self, *, before: str, expired_before: str) -> int:
        """Bounded lifecycle cleanup for expired records and old tombstones."""
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute(
                """DELETE FROM memories
                   WHERE (status IN ('deleted', 'superseded') AND updated_at < ?)
                      OR (status = 'active' AND expires_at IS NOT NULL
                          AND expires_at <= ?)""",
                (str(before), str(expired_before)),
            )
            conn.commit()
            return int(cursor.rowcount or 0)
