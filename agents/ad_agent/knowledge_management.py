"""Tenant-scoped Markdown LLM Wiki management and retrieval.

Managed knowledge is stored as Markdown content plus explicit frontmatter
metadata in the persistence backend.  It is advisory context only: publishing
it never creates a Tool, permission, credential or execution path.
"""

from __future__ import annotations

import re
import json
import threading
import time
import uuid
from collections import OrderedDict
from datetime import datetime
from typing import Any, Iterable, Mapping, Optional

from .domain.ad.knowledge import (
    KnowledgeDocument,
    MarkdownWikiKnowledgeProvider,
    WIKI_LAYERS,
    WIKI_STATUSES,
)
from .core.context import ContextQuery
from .core.namespace import normalize_namespace as normalize_platform
from .persistence.models import KnowledgeDocumentRecord
from .persistence.errors import PersistenceConflictError
from .persistence.interfaces import KnowledgeStorePort


class KnowledgeDocumentError(ValueError):
    """Raised when a submitted Wiki document is invalid or unsafe."""


_SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$"
)
_CREDENTIAL_ASSIGNMENT_RE = re.compile(
    r"(?im)(?:access[_-]?token|refresh[_-]?token|developer[_-]?token|"
    r"client[_-]?(?:id|secret)|app[_-]?secret|private[_-]?key|"
    r"authorization|credentials?|partner[_-]?id|perter[_-]?id|"
    r"bc[_-]?id|mcc|login[_-]?customer[_-]?id|manager[_-]?customer[_-]?id)"
    r"\s*[:=]"
)
_MAX_CONTENT_CHARS = 60_000
_WIKI_TYPES = {"entity", "concept", "comparison", "query"}
_KNOWLEDGE_TYPES = {
    "hierarchy", "constraint", "parameter", "workflow", "best_practice",
    "error_pattern", "case_study", "tip", "general", "bidding_strategy",
    "targeting_strategy", "creative_guide", "business_strategy",
}


def _clean_text(value: Any, field: str, max_length: int) -> str:
    text = str(value or "").strip()
    if not text:
        raise KnowledgeDocumentError(f"{field} 不能为空")
    if len(text) > max_length:
        raise KnowledgeDocumentError(f"{field} 超过 {max_length} 个字符")
    if "\x00" in text:
        raise KnowledgeDocumentError(f"{field} 不能包含 NUL")
    return text


def _safe_platform(value: Any) -> str:
    text = str(value or "all").strip().lower()
    if text == "all":
        return "all"
    normalized = normalize_platform(text)
    if not normalized:
        raise KnowledgeDocumentError("platform 不合法")
    return normalized


def _safe_tags(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        values = [item.strip() for item in value.split(",")]
    elif isinstance(value, (list, tuple, set)):
        values = [str(item).strip() for item in value]
    else:
        raise KnowledgeDocumentError("tags 必须是字符串数组")
    values = [item for item in values if item]
    if len(values) > 20 or any(len(item) > 64 for item in values):
        raise KnowledgeDocumentError("tags 最多 20 个，每个不超过 64 个字符")
    return list(dict.fromkeys(values))


def _safe_links(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        values = [value]
    elif isinstance(value, (list, tuple, set)):
        values = [str(item) for item in value]
    else:
        raise KnowledgeDocumentError("wikilinks 必须是字符串数组")
    values = [item.strip() for item in values if item.strip()]
    if len(values) > 30 or any(len(item) > 200 for item in values):
        raise KnowledgeDocumentError("wikilinks 最多 30 个，每个不超过 200 个字符")
    if any(not item.startswith("[[") or not item.endswith("]]") for item in values):
        raise KnowledgeDocumentError("wikilinks 必须使用 [[页面标题]] 格式")
    return list(dict.fromkeys(values))


class ManagedKnowledgeManager:
    """CRUD and publication facade for tenant-owned Wiki documents."""

    def __init__(self, store: KnowledgeStorePort):
        self.store = store

    @staticmethod
    def _public(record: KnowledgeDocumentRecord, include_content: bool = False) -> dict[str, Any]:
        value = record.to_dict()
        if not include_content:
            value.pop("content", None)
        value["markdown"] = ManagedKnowledgeManager.to_markdown(record)
        if not include_content:
            value.pop("markdown", None)
        return value

    @staticmethod
    def to_markdown(record: KnowledgeDocumentRecord) -> str:
        tags = json.dumps(record.tags or [], ensure_ascii=False)
        frontmatter = (
            "---\n"
            f'schema_version: "1"\n'
            f"id: {json.dumps(record.document_id, ensure_ascii=False)}\n"
            f"title: {json.dumps(record.title, ensure_ascii=False)}\n"
            f"layer: {json.dumps(record.layer, ensure_ascii=False)}\n"
            f"knowledge_type: {json.dumps(record.knowledge_type, ensure_ascii=False)}\n"
            f"platform: {json.dumps(record.platform, ensure_ascii=False)}\n"
            f"source: {json.dumps(record.source, ensure_ascii=False)}\n"
            f"source_ref: {json.dumps(record.source_ref, ensure_ascii=False)}\n"
            f"version: {json.dumps(record.version, ensure_ascii=False)}\n"
            f"confidence: {record.confidence}\n"
            f"wiki_type: {json.dumps(record.wiki_type, ensure_ascii=False)}\n"
            f"derived_from: {json.dumps(record.derived_from, ensure_ascii=False)}\n"
            f"raw_sha256: {json.dumps(record.raw_sha256, ensure_ascii=False)}\n"
            f"updated_at: {record.updated_at[:10]}\n"
            f"tags: {tags}\n"
            f"wikilinks: {json.dumps(record.wikilinks or [], ensure_ascii=False)}\n"
            f"status: {record.status}\n"
            "---\n\n"
        )
        return frontmatter + record.content.strip() + "\n"

    def validate_payload(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, Mapping):
            raise KnowledgeDocumentError("知识文档必须是对象")
        title = _clean_text(payload.get("title"), "title", 200)
        content = _clean_text(payload.get("content"), "content", _MAX_CONTENT_CHARS)
        metadata_text = "\n".join(
            (title, content, str(payload.get("source") or ""),
             str(payload.get("source_ref") or ""),
             " ".join(str(item) for item in (payload.get("tags") or [])))
        )
        if _CREDENTIAL_ASSIGNMENT_RE.search(metadata_text):
            raise KnowledgeDocumentError("知识文档不能包含凭证字段或认证配置")
        layer = str(payload.get("layer") or "business").strip().lower()
        if layer not in WIKI_LAYERS:
            raise KnowledgeDocumentError("layer 不合法")
        knowledge_type = str(payload.get("knowledge_type") or "general").strip().lower()
        if knowledge_type not in _KNOWLEDGE_TYPES:
            raise KnowledgeDocumentError("knowledge_type 不合法")
        version = str(payload.get("version") or "1.0.0").strip()
        if not _SEMVER_RE.fullmatch(version):
            raise KnowledgeDocumentError("version 必须是语义化版本，例如 1.0.0")
        try:
            confidence = max(0.0, min(1.0, float(payload.get("confidence", 0.8))))
        except (TypeError, ValueError) as exc:
            raise KnowledgeDocumentError("confidence 必须是 0 到 1 之间的数字") from exc
        wiki_type = str(payload.get("wiki_type") or "concept").strip().lower()
        if wiki_type not in _WIKI_TYPES:
            raise KnowledgeDocumentError("wiki_type 不合法")
        return {
            "title": title,
            "content": content,
            "platform": _safe_platform(payload.get("platform", "all")),
            "layer": layer,
            "knowledge_type": knowledge_type,
            "source": _clean_text(payload.get("source", "user"), "source", 200),
            "source_ref": str(payload.get("source_ref") or "").strip()[:500],
            "version": version,
            "confidence": confidence,
            "tags": _safe_tags(payload.get("tags")),
            "wiki_type": wiki_type,
            "derived_from": str(payload.get("derived_from") or "").strip()[:200],
            "raw_sha256": str(payload.get("raw_sha256") or "").strip()[:128],
            "wikilinks": _safe_links(payload.get("wikilinks")),
        }

    def create_document(
        self, tenant_id: str, payload: Mapping[str, Any], created_by: str,
    ) -> dict[str, Any]:
        data = self.validate_payload(payload)
        existing = self.store.list_knowledge_documents(
            str(tenant_id or "default"), limit=500
        )
        if any(
            item.title == data["title"] and item.version == data["version"]
            for item in existing
        ):
            raise KnowledgeDocumentError(
                "同一知识标题的版本已存在，请递增 version 后再保存"
            )
        document_id = uuid.uuid4().hex
        now = datetime.now().isoformat()
        data["source_ref"] = data["source_ref"] or f"managed://{document_id}"
        record = KnowledgeDocumentRecord(
            document_id=document_id,
            tenant_id=str(tenant_id or "default"),
            created_by=str(created_by),
            status="draft",
            created_at=now,
            updated_at=now,
            **data,
        )
        try:
            saved = self.store.create_knowledge_document(record)
        except PersistenceConflictError as exc:
            raise KnowledgeDocumentError(
                "同一知识标题的版本已存在，请递增 version 后再保存"
            ) from exc
        return self._public(saved, include_content=True)

    def update_document(
        self, tenant_id: str, document_id: str, payload: Mapping[str, Any], created_by: str,
    ) -> Optional[dict[str, Any]]:
        existing = self.store.get_knowledge_document(
            document_id, tenant_id=str(tenant_id or "default")
        )
        if not existing:
            return None
        data = self.validate_payload(payload)
        siblings = self.store.list_knowledge_documents(
            str(tenant_id or "default"), limit=500
        )
        if any(
            item.document_id != existing.document_id
            and item.title == data["title"]
            and item.version == data["version"]
            and item.status != "deprecated"
            for item in siblings
        ):
            raise KnowledgeDocumentError(
                "同一知识标题的版本已存在，请递增 version 后再保存"
            )
        if existing.status == "published":
            now = datetime.now().isoformat()
            new_id = uuid.uuid4().hex
            if not data["source_ref"] or data["source_ref"].startswith("managed://"):
                data["source_ref"] = f"managed://{new_id}"
            record = KnowledgeDocumentRecord(
                document_id=new_id,
                tenant_id=str(tenant_id or "default"),
                created_by=str(created_by),
                status="draft",
                created_at=now,
                updated_at=now,
                **data,
            )
            try:
                saved = self.store.create_knowledge_document(record)
            except PersistenceConflictError as exc:
                raise KnowledgeDocumentError(
                    "同一知识标题的版本已存在，请递增 version 后再保存"
                ) from exc
            result = self._public(saved, include_content=True)
            result["versioned_from"] = existing.document_id
            result["version_mode"] = "new_draft"
            return result
        updated = self.store.update_knowledge_document(
            document_id, tenant_id=str(tenant_id or "default"), data=data
        )
        return self._public(updated, include_content=True) if updated else None

    def delete_document(
        self, tenant_id: str, document_id: str,
    ) -> Optional[dict[str, Any]]:
        existing = self.store.get_knowledge_document(
            document_id, tenant_id=str(tenant_id or "default")
        )
        if not existing:
            return None
        result = self.store.delete_knowledge_document(
            document_id, tenant_id=str(tenant_id or "default")
        )
        if not result:
            return None
        response = self._public(result, include_content=False)
        response["deleted"] = True
        response["archived"] = existing.status == "published"
        response["hard_deleted"] = existing.status != "published"
        return response

    def list_documents(
        self, tenant_id: str, status: Optional[str] = None, limit: int = 100,
    ) -> list[dict[str, Any]]:
        records = self.store.list_knowledge_documents(
            str(tenant_id or "default"), status=status, limit=limit
        )
        return [self._public(record) for record in records]

    def get_document(self, tenant_id: str, document_id: str) -> Optional[dict[str, Any]]:
        record = self.store.get_knowledge_document(
            document_id, tenant_id=str(tenant_id or "default")
        )
        return self._public(record, include_content=True) if record else None

    def publish(self, tenant_id: str, document_id: str) -> Optional[dict[str, Any]]:
        record = self.store.publish_knowledge_document(
            document_id, tenant_id=str(tenant_id or "default")
        )
        return self._public(record, include_content=True) if record else None

    def unpublish(self, tenant_id: str, document_id: str) -> Optional[dict[str, Any]]:
        record = self.store.unpublish_knowledge_document(
            document_id, tenant_id=str(tenant_id or "default")
        )
        return self._public(record, include_content=True) if record else None


class ManagedKnowledgeProvider:
    """Merge built-in Wiki docs with published tenant-owned documents."""

    def __init__(self, base: MarkdownWikiKnowledgeProvider, store: KnowledgeStorePort):
        self.base = base
        self.store = store
        self._tenant_cache: OrderedDict[
            str,
            tuple[
                tuple[tuple[str, str, str], ...],
                list[KnowledgeDocument],
                list[KnowledgeDocument],
            ],
        ] = OrderedDict()
        self._tenant_cache_lock = threading.RLock()
        self._tenant_cache_max_entries = int(
            getattr(base, "_tenant_cache_max_entries", 256)
        )
        self._query_cache_ttl_seconds = getattr(
            base, "_query_cache_ttl_seconds", 5.0
        )
        self._query_cache_max_entries = getattr(
            base, "_query_cache_max_entries", 256
        )
        self._query_cache: OrderedDict[
            tuple[Any, ...], tuple[float, tuple[KnowledgeDocument, ...]]
        ] = OrderedDict()
        self._query_cache_hits = 0
        self._query_cache_misses = 0
        self._query_cache_evictions = 0
        self.base.search_index = store
        self.base._fts_scope = "builtin"
        self.base._fts_available = self.base._rebuild_search_index(
            self.base.chunks, scope=self.base._fts_scope
        )

    def cache_metrics(self) -> dict[str, Any]:
        base_metrics = self.base.cache_metrics()
        with self._tenant_cache_lock:
            return {
                **base_metrics,
                "tenant_query_entries": len(self._query_cache),
                "tenant_query_hit_total": self._query_cache_hits,
                "tenant_query_miss_total": self._query_cache_misses,
                "tenant_query_eviction_total": self._query_cache_evictions,
                "tenant_context_entries": len(self._tenant_cache),
            }

    def clear_query_cache(self) -> None:
        self.base.clear_query_cache()
        with self._tenant_cache_lock:
            self._query_cache.clear()

    def clear_tenant_cache(self, tenant_id: Optional[str] = None) -> None:
        """Invalidate one tenant or all managed context caches."""
        with self._tenant_cache_lock:
            if tenant_id is None:
                self._tenant_cache.clear()
                self._query_cache.clear()
                return
            tenant_key = str(tenant_id or "default")
            self._tenant_cache.pop(tenant_key, None)
            stale_keys = [
                key for key in self._query_cache
                if key and key[0] == tenant_key
            ]
            for key in stale_keys:
                self._query_cache.pop(key, None)

    @property
    def documents(self):
        return self.base.documents

    def _managed_document(self, record: KnowledgeDocumentRecord) -> KnowledgeDocument:
        source_kind = MarkdownWikiKnowledgeProvider._source_kind(
            "", record.source_ref, record.source
        )
        return KnowledgeDocument(
            document_id=f"managed:{record.document_id}",
            platform=record.platform,
            topic=record.title,
            excerpt=record.content,
            source=record.source,
            version=record.version,
            confidence=record.confidence,
            updated_at=record.updated_at,
            title=record.title,
            layer=record.layer,
            knowledge_type=record.knowledge_type,
            category=MarkdownWikiKnowledgeProvider._derive_category(
                (), record.title, record.layer, record.knowledge_type,
            ),
            subcategory=MarkdownWikiKnowledgeProvider._derive_subcategory(
                record.title, record.knowledge_type,
            ),
            source_ref=record.source_ref,
            tags=tuple(record.tags),
            status=record.status,
            wiki_type=record.wiki_type,
            derived_from=record.derived_from,
            raw_sha256=record.raw_sha256,
            wikilinks=tuple(record.wikilinks),
            source_kind=source_kind,
            authority=MarkdownWikiKnowledgeProvider._authority(
                "", source_kind
            ),
            evidence_level=MarkdownWikiKnowledgeProvider._evidence_level(
                "", source_kind
            ),
            last_verified_at=record.updated_at,
        )

    def catalog(
        self,
        *,
        platforms: Optional[Iterable[str]] = None,
        knowledge_types: Optional[Iterable[str]] = None,
        wiki_types: Optional[Iterable[str]] = None,
        limit: int = 100,
        tenant_id: Optional[str] = None,
    ) -> list[KnowledgeDocument]:
        """Return complete built-in and tenant documents for the Wiki catalog."""
        if limit <= 0:
            return []
        documents = self.base.catalog(
            platforms=platforms,
            knowledge_types=knowledge_types,
            wiki_types=wiki_types,
            limit=limit,
        )
        if tenant_id:
            records = self.store.list_knowledge_documents(
                str(tenant_id), status="published", limit=limit
            )
            managed = [self._managed_document(record) for record in records]
            allowed_platforms = {
                MarkdownWikiKnowledgeProvider._normalize_platform(item)
                for item in (platforms or [])
                if item and MarkdownWikiKnowledgeProvider._normalize_platform(item) != "all"
            }
            allowed_types = {
                str(item).strip().lower()
                for item in (knowledge_types or [])
                if item
            }
            allowed_wiki_types = {
                str(item).strip().lower()
                for item in (wiki_types or [])
                if item
            }
            managed = [
                document for document in managed
                if (not allowed_platforms or document.platform in allowed_platforms)
                and (not allowed_types or document.knowledge_type in allowed_types)
                and (not allowed_wiki_types or document.wiki_type in allowed_wiki_types)
            ]
            documents.extend(managed)
        return documents[:limit]

    def _published_tenant_context(
        self, tenant_id: str,
    ) -> tuple[list[KnowledgeDocument], list[KnowledgeDocument]]:
        """Build tenant chunks once per document revision, then reuse them."""
        tenant_key = str(tenant_id or "default")
        records = self.store.list_knowledge_documents(
            tenant_key, status="published", limit=500
        )
        signature = tuple(
            sorted(
                (
                    str(record.document_id),
                    str(record.updated_at),
                    str(record.version),
                )
                for record in records
            )
        )
        with self._tenant_cache_lock:
            cached = self._tenant_cache.get(tenant_key)
            if cached and cached[0] == signature:
                self._tenant_cache.move_to_end(tenant_key)
                return cached[1], cached[2]
            stale_keys = [
                key for key in self._query_cache
                if key and key[0] == tenant_key
            ]
            for key in stale_keys:
                self._query_cache.pop(key, None)
            managed = [self._managed_document(record) for record in records]
            managed_chunks = [
                chunk
                for document in managed
                for chunk in MarkdownWikiKnowledgeProvider._chunk_document(
                    document, scope=f"tenant:{tenant_key}"
                )
            ]
            fts_available = self.base._rebuild_search_index(
                managed_chunks, scope=f"tenant:{tenant_key}"
            )
            if fts_available:
                self.base._fts_available = True
            self._tenant_cache[tenant_key] = (signature, managed, managed_chunks)
            self._tenant_cache.move_to_end(tenant_key)
            while len(self._tenant_cache) > self._tenant_cache_max_entries:
                evicted_tenant, _ = self._tenant_cache.popitem(last=False)
                stale_keys = [
                    key for key in self._query_cache
                    if key and key[0] == evicted_tenant
                ]
                for key in stale_keys:
                    self._query_cache.pop(key, None)
            return managed, managed_chunks

    def query(
        self, query: str, *, namespaces: Optional[Iterable[str]] = None,
        platforms: Optional[Iterable[str]] = None,
        intent_type: Optional[str] = None,
        knowledge_types: Optional[Iterable[str]] = None,
        limit: int = 4, max_excerpt_chars: int = 1200,
        tenant_id: Optional[str] = None,
    ) -> list[KnowledgeDocument]:
        if not tenant_id:
            selected_platforms = namespaces if namespaces is not None else platforms
            return self.base.query(
                query, namespaces=selected_platforms, intent_type=intent_type,
                knowledge_types=knowledge_types, limit=limit,
                max_excerpt_chars=max_excerpt_chars,
            )
        if limit <= 0 or max_excerpt_chars <= 0:
            return []
        tenant_key = str(tenant_id)
        managed, managed_chunks = self._published_tenant_context(tenant_key)
        effective_limit = min(int(limit), 100)
        effective_excerpt_chars = min(
            int(max_excerpt_chars), MarkdownWikiKnowledgeProvider._CHUNK_SIZE
        )
        with self._tenant_cache_lock:
            tenant_signature = self._tenant_cache.get(tenant_key, ((), [], []))[0]
        selected_platforms = namespaces if namespaces is not None else platforms
        normalized_platforms = tuple(sorted({
            MarkdownWikiKnowledgeProvider._normalize_platform(item)
            for item in (selected_platforms or [])
            if str(item).strip()
        }))
        normalized_types = tuple(sorted({
            str(item).strip().lower()
            for item in (knowledge_types or [])
            if str(item).strip()
        }))
        cache_key = (
            tenant_key,
            tenant_signature,
            MarkdownWikiKnowledgeProvider._normalise_text(query),
            normalized_platforms,
            str(intent_type or "").strip().lower(),
            normalized_types,
            effective_limit,
            effective_excerpt_chars,
        )
        now = time.monotonic()
        with self._tenant_cache_lock:
            cached = self._query_cache.get(cache_key)
            if cached is not None:
                expires_at, documents = cached
                if self._query_cache_ttl_seconds == 0 or expires_at <= now:
                    self._query_cache.pop(cache_key, None)
                else:
                    self._query_cache.move_to_end(cache_key)
                    self._query_cache_hits += 1
                    return list(documents)
            self._query_cache_misses += 1
        all_documents = [*self.base.documents, *managed]
        managed_scope = f"tenant:{tenant_key}"
        all_chunks = [
            *self.base.chunks,
            *managed_chunks,
        ]
        terms = MarkdownWikiKnowledgeProvider._terms(query, intent_type)
        fts_hits = self.base._search_index_hits(
            query, terms, scopes=["builtin", managed_scope]
        )
        result = MarkdownWikiKnowledgeProvider._query_chunks(
            all_chunks,
            all_documents,
            query,
            platforms=selected_platforms,
            intent_type=intent_type,
            knowledge_types=knowledge_types,
            limit=effective_limit,
            max_excerpt_chars=effective_excerpt_chars,
            fts_hits=fts_hits,
        )
        if self._query_cache_ttl_seconds > 0:
            with self._tenant_cache_lock:
                self._query_cache[cache_key] = (
                    time.monotonic() + self._query_cache_ttl_seconds,
                    tuple(result),
                )
                self._query_cache.move_to_end(cache_key)
                while len(self._query_cache) > self._query_cache_max_entries:
                    self._query_cache.popitem(last=False)
                    self._query_cache_evictions += 1
        return list(result)

    def query_context(self, request: ContextQuery) -> list[KnowledgeDocument]:
        """Implement the provider-neutral advisory context contract."""
        filters = request.filters if isinstance(request.filters, Mapping) else {}
        return self.query(
            request.text,
            namespaces=request.namespaces,
            intent_type=request.intent_type or None,
            knowledge_types=filters.get("knowledge_types"),
            limit=request.limit,
            max_excerpt_chars=request.max_excerpt_chars,
            tenant_id=request.tenant_id,
        )

    def catalog_context(self, request: ContextQuery) -> list[KnowledgeDocument]:
        """Return built-in and tenant navigation documents."""
        filters = request.filters if isinstance(request.filters, Mapping) else {}
        return self.catalog(
            platforms=request.namespaces,
            knowledge_types=filters.get("knowledge_types"),
            wiki_types=filters.get("wiki_types"),
            limit=request.limit,
            tenant_id=request.tenant_id,
        )
