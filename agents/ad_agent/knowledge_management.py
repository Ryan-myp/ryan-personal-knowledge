"""Tenant-scoped Markdown LLM Wiki management and retrieval.

Managed knowledge is stored as Markdown content plus explicit frontmatter
metadata in the persistence backend.  It is advisory context only: publishing
it never creates a Tool, permission, credential or execution path.
"""

from __future__ import annotations

import re
import json
import threading
import uuid
from datetime import datetime
from typing import Any, Iterable, Mapping, Optional

from .domain.ad.knowledge import (
    KnowledgeDocument,
    MarkdownWikiKnowledgeProvider,
    WIKI_LAYERS,
    WIKI_STATUSES,
)
from .core.platform import normalize_platform
from .persistence.models import KnowledgeDocumentRecord
from .persistence.errors import PersistenceConflictError


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


class ManagedKnowledgeManager:
    """CRUD and publication facade for tenant-owned Wiki documents."""

    def __init__(self, store: Any):
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
            f"updated_at: {record.updated_at[:10]}\n"
            f"tags: {tags}\n"
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

    def __init__(self, base: MarkdownWikiKnowledgeProvider, store: Any):
        self.base = base
        self.store = store
        self._tenant_cache: dict[str, tuple[tuple[tuple[str, str, str], ...], list[KnowledgeDocument], list[KnowledgeDocument]]] = {}
        self._tenant_cache_lock = threading.RLock()
        self.base.search_index = store
        self.base._fts_scope = "builtin"
        self.base._fts_available = self.base._rebuild_search_index(
            self.base.chunks, scope=self.base._fts_scope
        )

    @property
    def documents(self):
        return self.base.documents

    def _managed_document(self, record: KnowledgeDocumentRecord) -> KnowledgeDocument:
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
        )

    def catalog(
        self,
        *,
        platforms: Optional[Iterable[str]] = None,
        knowledge_types: Optional[Iterable[str]] = None,
        limit: int = 100,
        tenant_id: Optional[str] = None,
    ) -> list[KnowledgeDocument]:
        """Return complete built-in and tenant documents for the Wiki catalog."""
        if limit <= 0:
            return []
        documents = self.base.catalog(
            platforms=platforms, knowledge_types=knowledge_types, limit=limit
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
            managed = [
                document for document in managed
                if (not allowed_platforms or document.platform in allowed_platforms)
                and (not allowed_types or document.knowledge_type in allowed_types)
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
                return cached[1], cached[2]
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
            return managed, managed_chunks

    def query(
        self, query: str, *, platforms: Optional[Iterable[str]] = None,
        intent_type: Optional[str] = None,
        knowledge_types: Optional[Iterable[str]] = None,
        limit: int = 4, max_excerpt_chars: int = 1200,
        tenant_id: Optional[str] = None,
    ) -> list[KnowledgeDocument]:
        if not tenant_id:
            return self.base.query(
                query, platforms=platforms, intent_type=intent_type,
                knowledge_types=knowledge_types, limit=limit,
                max_excerpt_chars=max_excerpt_chars,
            )
        managed, managed_chunks = self._published_tenant_context(str(tenant_id))
        all_documents = [*self.base.documents, *managed]
        managed_scope = f"tenant:{tenant_id}"
        all_chunks = [
            *self.base.chunks,
            *managed_chunks,
        ]
        terms = MarkdownWikiKnowledgeProvider._terms(query, intent_type)
        fts_hits = self.base._search_index_hits(
            query, terms, scopes=["builtin", managed_scope]
        )
        return MarkdownWikiKnowledgeProvider._query_chunks(
            all_chunks,
            all_documents,
            query,
            platforms=platforms,
            intent_type=intent_type,
            knowledge_types=knowledge_types,
            limit=limit,
            max_excerpt_chars=max_excerpt_chars,
            fts_hits=fts_hits,
        )
