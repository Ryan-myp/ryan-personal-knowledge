"""Controlled raw-document ingestion for the tenant Markdown Wiki.

Raw uploads are immutable context data. They are never exposed through the
Runtime knowledge provider; the ingest worker converts them into validated
draft pages that still require explicit publication.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Mapping, Optional

from .knowledge_management import (
    KnowledgeDocumentError,
    ManagedKnowledgeManager,
)
from .persistence.errors import PersistenceConflictError
from .persistence.interfaces import KnowledgeStorePort
from .persistence.models import KnowledgeDocumentRecord, RawKnowledgeSourceRecord


class KnowledgeIngestError(ValueError):
    """Raised when raw Wiki ingestion cannot satisfy its contract."""


logger = logging.getLogger(__name__)

_MAX_RAW_CHARS = 120_000
_MAX_FILENAME_CHARS = 240
_MAX_PAGES = 12
_ALLOWED_MEDIA_TYPES = {
    "text/plain",
    "text/markdown",
    "text/x-markdown",
    "application/json",
}
_RAW_STATUSES = {"received", "ingesting", "draft_ready", "failed"}
_SENSITIVE_ASSIGNMENT_RE = re.compile(
    r"(?im)(?:access[_-]?token|refresh[_-]?token|developer[_-]?token|"
    r"client[_-]?(?:id|secret)|app[_-]?secret|private[_-]?key|"
    r"authorization|credentials?|partner[_-]?id|perter[_-]?id|"
    r"bc[_-]?id|mcc)\s*[:=]"
)
_SEMVER_RE = re.compile(
    r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
    r"(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$"
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_error(exc: BaseException) -> str:
    """Keep model/provider exception details out of persisted user data."""
    return f"{type(exc).__name__}: ingestion failed"


class RawKnowledgeManager:
    """Validate, persist and expose immutable raw source records."""

    def __init__(self, store: KnowledgeStorePort):
        self.store = store

    @staticmethod
    def _public(record: RawKnowledgeSourceRecord) -> dict[str, Any]:
        value = record.to_dict()
        value.pop("content", None)
        return value

    @staticmethod
    def _validate_filename(filename: Any) -> str:
        value = str(filename or "").strip()
        if not value or len(value) > _MAX_FILENAME_CHARS:
            raise KnowledgeIngestError("filename 不能为空且长度不能超过 240 个字符")
        if "\x00" in value or "/" in value or "\\" in value or value in {".", ".."}:
            raise KnowledgeIngestError("filename 不能包含路径或控制字符")
        return value

    @staticmethod
    def _validate_content(content: Any) -> str:
        if not isinstance(content, str) or not content.strip():
            raise KnowledgeIngestError("raw 文档内容不能为空")
        if len(content) > _MAX_RAW_CHARS:
            raise KnowledgeIngestError("raw 文档超过 120000 个字符")
        if "\x00" in content:
            raise KnowledgeIngestError("raw 文档不能包含 NUL")
        if _SENSITIVE_ASSIGNMENT_RE.search(content):
            raise KnowledgeIngestError("raw 文档不能包含凭证字段或认证配置")
        return content

    @staticmethod
    def _validate_media_type(media_type: Any) -> str:
        value = str(media_type or "text/markdown").strip().lower()
        if value not in _ALLOWED_MEDIA_TYPES:
            raise KnowledgeIngestError("当前只支持纯文本、Markdown 或 JSON 文档")
        return value

    def create_source(
        self,
        *,
        tenant_id: str,
        filename: str,
        content: str,
        created_by: str,
        media_type: str = "text/markdown",
        source_ref: str = "",
    ) -> dict[str, Any]:
        tenant = str(tenant_id or "default").strip() or "default"
        safe_filename = self._validate_filename(filename)
        safe_content = self._validate_content(content)
        safe_media_type = self._validate_media_type(media_type)
        digest = hashlib.sha256(safe_content.encode("utf-8")).hexdigest()
        existing = self.store.find_raw_knowledge_source_by_hash(tenant, digest)
        if existing:
            result = self._public(existing)
            result["duplicate"] = True
            return result
        source_id = uuid.uuid4().hex
        now = _now()
        record = RawKnowledgeSourceRecord(
            source_id=source_id,
            tenant_id=tenant,
            filename=safe_filename,
            media_type=safe_media_type,
            content=safe_content,
            sha256=digest,
            source_ref=str(source_ref or "").strip()[:500] or f"upload://{source_id}",
            created_by=str(created_by or "").strip(),
            created_at=now,
            updated_at=now,
        )
        try:
            saved = self.store.create_raw_knowledge_source(record)
        except PersistenceConflictError:
            existing = self.store.find_raw_knowledge_source_by_hash(tenant, digest)
            if not existing:
                raise
            result = self._public(existing)
            result["duplicate"] = True
            return result
        result = self._public(saved)
        result["duplicate"] = False
        return result

    def get_source(
        self, source_id: str, *, tenant_id: str, include_content: bool = False,
    ) -> Optional[dict[str, Any]]:
        record = self.store.get_raw_knowledge_source(
            source_id, tenant_id=str(tenant_id or "default")
        )
        if not record:
            return None
        result = record.to_dict()
        if not include_content:
            result.pop("content", None)
        return result

    def update_source(
        self, source_id: str, *, tenant_id: str, content: Optional[str] = None,
        **data: Any,
    ) -> dict[str, Any]:
        if content is not None or any(
            key in data for key in ("filename", "media_type", "sha256", "source_ref")
        ):
            raise KnowledgeIngestError("raw 文档不可修改，只能更新 ingest 状态")
        if "status" in data and str(data["status"]) not in _RAW_STATUSES:
            raise KnowledgeIngestError("raw 文档状态不合法")
        record = self.store.update_raw_knowledge_source(
            source_id,
            tenant_id=str(tenant_id or "default"),
            data={key: value for key, value in data.items() if value is not None},
        )
        if not record:
            raise KnowledgeIngestError("raw 文档不存在或无权访问")
        return record.to_dict()


class KnowledgeIngestService:
    """Turn one raw source into bounded, reviewable Wiki draft pages."""

    def __init__(
        self, *, store: KnowledgeStorePort, llm: Any,
        knowledge_manager: ManagedKnowledgeManager,
        knowledge_provider: Any = None, stale_after_seconds: float = 900.0,
    ):
        self.store = store
        self.llm = llm
        self.knowledge_manager = knowledge_manager
        self.knowledge_provider = knowledge_provider
        self.stale_after_seconds = max(1.0, float(stale_after_seconds))
        self.raw_manager = RawKnowledgeManager(store)

    def _catalog(self, tenant_id: str) -> list[dict[str, str]]:
        records = self.store.list_knowledge_documents(
            str(tenant_id or "default"), status="published", limit=100
        )
        catalog = [
            {
                "document_id": str(record.document_id),
                "title": str(record.title),
                "wiki_type": str(record.wiki_type),
                "content": str(record.content)[:1000],
            }
            for record in records
        ]
        provider_catalog = getattr(self.knowledge_provider, "catalog", None)
        if callable(provider_catalog):
            try:
                builtins = provider_catalog(
                    tenant_id=str(tenant_id or "default"), limit=100
                )
            except TypeError:
                builtins = provider_catalog(limit=100)
            for document in builtins or []:
                if str(getattr(document, "wiki_type", "")) == "raw":
                    continue
                catalog.append({
                    "document_id": str(getattr(document, "document_id", "")),
                    "title": str(getattr(document, "title", "") or getattr(document, "topic", "")),
                    "wiki_type": str(getattr(document, "wiki_type", "concept")),
                    "content": str(getattr(document, "excerpt", ""))[:1000],
                })
        return catalog[:200]

    @staticmethod
    def _page_payload(
        page: Mapping[str, Any], *, source_id: str, raw_sha256: str,
        defaults: Optional[Mapping[str, Any]] = None,
    ) -> dict[str, Any]:
        allowed = {
            "document_id", "title", "content", "platform", "layer",
            "knowledge_type", "version", "confidence", "tags", "wiki_type",
            "wikilinks",
        }
        unknown = sorted(set(page) - allowed)
        if unknown:
            raise KnowledgeIngestError(
                "LLM 页面包含不支持的字段：" + ", ".join(unknown)
            )
        if page.get("document_id") and (
            not isinstance(page["document_id"], str)
            or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", page["document_id"])
        ):
            raise KnowledgeIngestError("LLM 页面 document_id 不合法")
        inherited = dict(defaults or {})

        def value(name: str, fallback: Any) -> Any:
            return page[name] if name in page else inherited.get(name, fallback)

        return {
            "title": value("title", None),
            "content": value("content", None),
            "platform": value("platform", "all"),
            "layer": value("layer", "business"),
            "knowledge_type": value("knowledge_type", "general"),
            "version": value("version", "1.0.0"),
            "confidence": value("confidence", 0.7),
            "tags": value("tags", []),
            "wiki_type": value("wiki_type", "concept"),
            "wikilinks": value("wikilinks", []),
            "source": "llm_ingest",
            "source_ref": f"raw://{source_id}",
            "derived_from": source_id,
            "raw_sha256": raw_sha256,
        }

    @staticmethod
    def _next_patch_version(version: Any) -> str:
        """Create a deterministic draft version for a published-page update."""
        match = _SEMVER_RE.fullmatch(str(version or "").strip())
        if not match:
            return "1.0.1"
        return (
            f"{match.group('major')}.{match.group('minor')}."
            f"{int(match.group('patch')) + 1}"
        )

    @staticmethod
    def _record_payload(record: KnowledgeDocumentRecord) -> dict[str, Any]:
        """Project a stored document back into the manager's update contract."""
        return {
            "title": record.title,
            "content": record.content,
            "platform": record.platform,
            "layer": record.layer,
            "knowledge_type": record.knowledge_type,
            "source": record.source,
            "source_ref": record.source_ref,
            "version": record.version,
            "confidence": record.confidence,
            "tags": list(record.tags or []),
            "wiki_type": record.wiki_type,
            "derived_from": record.derived_from,
            "raw_sha256": record.raw_sha256,
            "wikilinks": list(record.wikilinks or []),
        }

    @classmethod
    def _validate_response(cls, value: Any) -> tuple[list[Mapping[str, Any]], list[Mapping[str, Any]]]:
        if not isinstance(value, dict):
            raise KnowledgeIngestError("LLM ingest 输出必须是 JSON 对象")
        pages_to_create = value.get("pages_to_create", [])
        pages_to_update = value.get("pages_to_update", [])
        if not isinstance(pages_to_create, list) or not isinstance(pages_to_update, list):
            raise KnowledgeIngestError("LLM ingest 页面列表格式不合法")
        if len(pages_to_create) + len(pages_to_update) > _MAX_PAGES:
            raise KnowledgeIngestError("单次 ingest 最多生成 12 个页面")
        for page in [*pages_to_create, *pages_to_update]:
            if not isinstance(page, dict):
                raise KnowledgeIngestError("LLM ingest 页面必须是对象")
        return pages_to_create, pages_to_update

    def ingest(
        self, source_id: str, *, tenant_id: str, created_by: str,
        task_id: Optional[str] = None,
    ) -> dict[str, Any]:
        source = self.store.get_raw_knowledge_source(
            source_id, tenant_id=str(tenant_id or "default")
        )
        if not source:
            raise KnowledgeIngestError("raw 文档不存在或无权访问")
        if source.status == "ingesting":
            self.store.recover_stale_raw_knowledge_sources(
                tenant_id=str(tenant_id or "default"),
                stale_after_seconds=self.stale_after_seconds,
                recovered_at=_now(),
            )
            source = self.store.get_raw_knowledge_source(
                source_id, tenant_id=str(tenant_id or "default")
            )
            if source is None or source.status == "ingesting":
                raise KnowledgeIngestError("raw 文档正在 ingest")
        if source.status == "draft_ready":
            raise KnowledgeIngestError("raw 文档已完成 ingest，不能重复处理")
        started_at = _now()
        source = self.store.claim_raw_knowledge_source(
            source_id,
            tenant_id=str(tenant_id or "default"),
            task_id=task_id,
            started_at=started_at,
        )
        if source is None:
            current = self.store.get_raw_knowledge_source(
                source_id, tenant_id=str(tenant_id or "default")
            )
            if current and current.status == "ingesting":
                raise KnowledgeIngestError("raw 文档正在 ingest")
            if current and current.status == "draft_ready":
                raise KnowledgeIngestError("raw 文档已完成 ingest，不能重复处理")
            raise KnowledgeIngestError("raw 文档无法领取 ingest 任务")
        created_ids: list[str] = []
        updated_ids: list[str] = []
        rollback_drafts: dict[str, KnowledgeDocumentRecord] = {}
        try:
            catalog = self._catalog(tenant_id)
            messages = [
                {
                    "role": "system",
                    "content": (
                        "你是受控 Wiki 编辑器。只能返回 JSON，不得返回路径、脚本、"
                        "工具调用或凭证。所有页面都只是待审核 draft。"
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "raw_source": {
                                "filename": source.filename,
                                "media_type": source.media_type,
                                "sha256": source.sha256,
                                "content": source.content,
                            },
                            "published_catalog": catalog,
                            "output_contract": {
                                "pages_to_create": [
                                    {
                                        "title": "string",
                                        "wiki_type": "entity|concept|comparison|query",
                                        "content": "markdown",
                                        "platform": "all|provider",
                                        "layer": "platform|business|experience|dynamic",
                                        "knowledge_type": "general or known knowledge type",
                                        "version": "semver",
                                        "confidence": "0..1",
                                        "tags": ["string"],
                                        "wikilinks": ["[[Title]]"],
                                    }
                                ],
                                "pages_to_update": [
                                    {
                                        "document_id": "existing document id",
                                        "title": "string",
                                        "content": "markdown",
                                    }
                                ],
                                "summary": "string",
                                "contradictions": ["string"],
                            },
                        },
                        ensure_ascii=False,
                    ),
                },
            ]
            if not callable(getattr(self.llm, "call_json", None)):
                raise KnowledgeIngestError("LLM 客户端不支持结构化 JSON 输出")
            response = self.llm.call_json(messages, temperature=0.1)
            pages_to_create, pages_to_update = self._validate_response(response)

            # Validate every page before creating any draft to avoid partial
            # ingestion when the model returns one malformed page.
            create_payloads = [
                self._page_payload(page, source_id=source.source_id, raw_sha256=source.sha256)
                for page in pages_to_create
            ]
            update_payloads: list[
                tuple[Mapping[str, Any], dict[str, Any], KnowledgeDocumentRecord]
            ] = []
            for page in pages_to_update:
                if not page.get("document_id"):
                    raise KnowledgeIngestError("更新页面必须提供 document_id")
                existing = self.store.get_knowledge_document(
                    str(page["document_id"]), tenant_id=str(tenant_id)
                )
                if not existing:
                    raise KnowledgeIngestError("更新目标页面不存在或无权访问")
                if existing.status == "deprecated":
                    raise KnowledgeIngestError("不能更新已废弃页面")
                payload = self._page_payload(
                    page,
                    source_id=source.source_id,
                    raw_sha256=source.sha256,
                    defaults=existing.to_dict(),
                )
                if (
                    existing.status == "published"
                    and payload["version"] == existing.version
                ):
                    payload["version"] = self._next_patch_version(existing.version)
                update_payloads.append((page, payload, existing))

            for payload in create_payloads:
                created = self.knowledge_manager.create_document(
                    tenant_id, payload, created_by
                )
                created_ids.append(str(created["document_id"]))
            for page, payload, existing in update_payloads:
                if existing.status == "draft":
                    rollback_drafts[existing.document_id] = existing
                updated = self.knowledge_manager.update_document(
                    tenant_id, str(page["document_id"]), payload, created_by
                )
                if not updated:
                    raise KnowledgeIngestError("更新目标页面失败")
                updated_ids.append(str(updated["document_id"]))
        except Exception as exc:
            for document_id in [*created_ids, *updated_ids]:
                if document_id in rollback_drafts:
                    continue
                try:
                    self.knowledge_manager.delete_document(tenant_id, document_id)
                except Exception:
                    logger.warning(
                        "failed to remove partial knowledge draft",
                        extra={"tenant_id": tenant_id, "document_id": document_id},
                        exc_info=True,
                    )
            for document_id, original in rollback_drafts.items():
                try:
                    self.store.update_knowledge_document(
                        document_id,
                        tenant_id=str(tenant_id),
                        data=self._record_payload(original),
                    )
                except Exception:
                    logger.warning(
                        "failed to restore knowledge draft after ingest failure",
                        extra={"tenant_id": tenant_id, "document_id": document_id},
                        exc_info=True,
                    )
            finished_at = _now()
            try:
                self.raw_manager.update_source(
                    source_id, tenant_id=tenant_id, status="failed",
                    updated_at=finished_at, ingest_error=_safe_error(exc),
                    ingest_finished_at=finished_at,
                )
            except Exception:
                logger.warning(
                    "failed to persist raw knowledge ingest failure",
                    extra={"tenant_id": tenant_id, "source_id": source_id},
                    exc_info=True,
                )
            if isinstance(exc, KnowledgeIngestError):
                raise
            if isinstance(exc, KnowledgeDocumentError):
                raise KnowledgeIngestError(str(exc)) from exc
            raise KnowledgeIngestError("LLM ingest 失败") from exc

        finished_at = _now()
        try:
            self.raw_manager.update_source(
                source_id, tenant_id=tenant_id, status="draft_ready",
                updated_at=finished_at, ingest_error=None,
                ingest_finished_at=finished_at,
            )
        except Exception as exc:
            logger.warning(
                "failed to persist raw knowledge ingest completion",
                extra={"tenant_id": tenant_id, "source_id": source_id},
                exc_info=True,
            )
            raise KnowledgeIngestError(
                "知识 ingest 已生成 draft，但状态记录失败，需要人工核对"
            ) from exc
        return {
            "source_id": source_id,
            "status": "draft_ready",
            "created_document_ids": created_ids,
            "updated_document_ids": updated_ids,
            "summary": str(response.get("summary") or "")[:2000],
            "contradictions": [
                str(item)[:500] for item in (response.get("contradictions") or [])[:20]
            ],
        }


__all__ = [
    "KnowledgeIngestError",
    "KnowledgeIngestService",
    "RawKnowledgeManager",
]
