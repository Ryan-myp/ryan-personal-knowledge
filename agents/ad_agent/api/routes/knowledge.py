"""Knowledge Wiki and Memory routes."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from agents.ad_agent.api.context import ApiContext
from agents.ad_agent.api.models import (
    KnowledgeDocumentRequest,
    MemoryWriteRequest,
    RawKnowledgeUploadRequest,
)
from agents.ad_agent.core.memory import MEMORY_KINDS
from agents.ad_agent.knowledge_ingest import (
    KnowledgeIngestError,
    RawKnowledgeManager,
)
from agents.ad_agent.knowledge_management import (
    KnowledgeDocumentError,
    ManagedKnowledgeManager,
)


def create_knowledge_router(context: ApiContext) -> APIRouter:
    router = APIRouter()

    def store():
        value = (
            context.persistence_store_getter()
            if context.persistence_store_getter else None
        )
        if value is None:
            raise HTTPException(status_code=503, detail="知识库存储未初始化")
        return value

    @router.get("/knowledge/search", tags=["knowledge"])
    async def search_knowledge(
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
        query: str = Query("", max_length=2000),
        platform: Optional[str] = Query(None, max_length=64),
        knowledge_type: Optional[str] = Query(None, max_length=64),
        limit: int = Query(10, ge=1, le=50),
        summarize: bool = Query(False),
    ):
        principal = context.authorize_request(x_api_key, http_request)
        context.require_permission(principal, "ads.read")
        runtime = context.runtime()
        if not runtime or not callable(getattr(runtime, "search_knowledge", None)):
            raise HTTPException(status_code=503, detail="知识库未初始化")
        documents = await run_in_threadpool(
            runtime.search_knowledge,
            query,
            tenant_id=principal.tenant_id,
            platform=platform,
            knowledge_type=knowledge_type,
            limit=limit,
            max_excerpt_chars=1200,
        )
        summary = await run_in_threadpool(
            runtime.summarize_knowledge, query, documents, use_llm=summarize
        )
        return {
            "query": query,
            "summary": summary,
            "summary_mode": "llm" if summarize else "lexical",
            "results": documents,
        }

    @router.get("/knowledge/catalog", tags=["knowledge"])
    async def catalog_knowledge(
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
        platform: Optional[str] = Query(None, max_length=64),
        knowledge_type: Optional[str] = Query(None, max_length=64),
        limit: int = Query(100, ge=1, le=200),
    ):
        principal = context.authorize_request(x_api_key, http_request)
        context.require_permission(principal, "ads.read")
        runtime = context.runtime()
        if not runtime or not callable(getattr(runtime, "catalog_knowledge", None)):
            raise HTTPException(status_code=503, detail="知识库未初始化")
        documents = await run_in_threadpool(
            runtime.catalog_knowledge,
            tenant_id=principal.tenant_id,
            platform=platform,
            knowledge_type=knowledge_type,
            limit=limit,
        )
        tree: dict[str, dict[str, Any]] = {}
        for document in documents:
            provider = str(document.get("platform") or "all")
            category = str(
                document.get("category")
                or document.get("layer")
                or "general"
            )
            subcategory = str(
                document.get("subcategory")
                or document.get("knowledge_type")
                or "general"
            )
            provider_node = tree.setdefault(
                provider, {"key": provider, "count": 0, "categories": {}}
            )
            provider_node["count"] += 1
            category_node = provider_node["categories"].setdefault(
                category, {"key": category, "count": 0, "documents": []}
            )
            category_node["count"] += 1
            category_node["documents"].append({
                "document_id": document.get("document_id"),
                "title": document.get("title") or document.get("topic"),
                "subcategory": subcategory,
                "knowledge_type": document.get("knowledge_type") or "general",
            })
        tree_payload = []
        for provider_key in sorted(tree):
            provider_node = tree[provider_key]
            categories = []
            for category_key in sorted(provider_node["categories"]):
                category_node = provider_node["categories"][category_key]
                category_node["documents"].sort(
                    key=lambda item: str(item.get("title") or "")
                )
                categories.append(category_node)
            tree_payload.append({
                "key": provider_node["key"],
                "count": provider_node["count"],
                "categories": categories,
            })
        return {
            "platform": platform or "",
            "knowledge_type": knowledge_type or "",
            "count": len(documents),
            "documents": documents,
            "tree": tree_payload,
        }

    @router.get("/knowledge/raw", tags=["knowledge"])
    async def list_raw_knowledge_sources(
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
        status: Optional[str] = Query(None, max_length=32),
        limit: int = Query(100, ge=1, le=200),
    ):
        principal = context.authorize_request(x_api_key, http_request)
        context.require_permission(principal, "knowledge.read")
        records = await run_in_threadpool(
            RawKnowledgeManager(store()).store.list_raw_knowledge_sources,
            principal.tenant_id,
            status=status,
            limit=limit,
        )
        return {
            "tenant_id": principal.tenant_id,
            "sources": [
                {
                    key: value
                    for key, value in record.to_dict().items()
                    if key != "content"
                }
                for record in records
            ],
        }

    @router.post("/knowledge/raw", tags=["knowledge"])
    async def upload_raw_knowledge_source(
        body: RawKnowledgeUploadRequest,
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    ):
        principal = context.authorize_request(x_api_key, http_request)
        context.require_permission(principal, "knowledge.write")
        manager = RawKnowledgeManager(store())
        runtime = context.runtime()
        try:
            source = await run_in_threadpool(
                manager.create_source,
                tenant_id=principal.tenant_id,
                filename=body.filename,
                content=body.content,
                created_by=principal.user_id,
                media_type=body.media_type,
                source_ref=body.source_ref,
            )
            if not runtime or not callable(
                getattr(runtime, "submit_knowledge_ingest", None)
            ):
                raise RuntimeError("异步知识 ingest 执行器未初始化")
            task, created = await run_in_threadpool(
                runtime.submit_knowledge_ingest,
                source["source_id"],
                principal=principal,
            )
        except (KnowledgeIngestError, ValueError, TypeError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except RuntimeError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
        return JSONResponse(
            status_code=202,
            content={"source": source, "task": task, "created": created},
        )

    @router.get("/knowledge/raw/{source_id}", tags=["knowledge"])
    async def get_raw_knowledge_source(
        source_id: str,
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    ):
        principal = context.authorize_request(x_api_key, http_request)
        context.require_permission(principal, "knowledge.read")
        result = await run_in_threadpool(
            RawKnowledgeManager(store()).get_source,
            source_id,
            tenant_id=principal.tenant_id,
        )
        if not result:
            raise HTTPException(status_code=404, detail="raw 文档不存在或无权访问")
        return result

    @router.get("/knowledge/documents", tags=["knowledge"])
    async def list_knowledge_documents(
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
        status: Optional[str] = Query(None, max_length=32),
        limit: int = Query(100, ge=1, le=200),
    ):
        principal = context.authorize_request(x_api_key, http_request)
        context.require_permission(principal, "ads.read")
        result = await run_in_threadpool(
            ManagedKnowledgeManager(store()).list_documents,
            principal.tenant_id,
            status=status,
            limit=limit,
        )
        return {"tenant_id": principal.tenant_id, "documents": result}

    @router.post("/knowledge/documents", tags=["knowledge"])
    async def create_knowledge_document(
        body: KnowledgeDocumentRequest,
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    ):
        principal = context.authorize_request(x_api_key, http_request)
        context.require_permission(principal, "knowledge.write")
        try:
            result = await run_in_threadpool(
                ManagedKnowledgeManager(store()).create_document,
                principal.tenant_id,
                body.model_dump(),
                principal.user_id,
            )
        except KnowledgeDocumentError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return JSONResponse(status_code=201, content=result)

    @router.get("/knowledge/documents/{document_id}", tags=["knowledge"])
    async def get_knowledge_document(
        document_id: str,
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    ):
        principal = context.authorize_request(x_api_key, http_request)
        context.require_permission(principal, "knowledge.read")
        result = await run_in_threadpool(
            ManagedKnowledgeManager(store()).get_document,
            principal.tenant_id,
            document_id,
        )
        if not result:
            raise HTTPException(status_code=404, detail="知识文档不存在或无权访问")
        return result

    @router.put("/knowledge/documents/{document_id}", tags=["knowledge"])
    async def update_knowledge_document(
        document_id: str,
        body: KnowledgeDocumentRequest,
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    ):
        principal = context.authorize_request(x_api_key, http_request)
        context.require_permission(principal, "knowledge.write")
        try:
            result = await run_in_threadpool(
                ManagedKnowledgeManager(store()).update_document,
                principal.tenant_id,
                document_id,
                body.model_dump(),
                principal.user_id,
            )
        except KnowledgeDocumentError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        if not result:
            raise HTTPException(
                status_code=404,
                detail="知识文档不存在、已废弃或无权访问",
            )
        return result

    @router.delete("/knowledge/documents/{document_id}", tags=["knowledge"])
    async def delete_knowledge_document(
        document_id: str,
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    ):
        principal = context.authorize_request(x_api_key, http_request)
        context.require_permission(principal, "knowledge.write")
        result = await run_in_threadpool(
            ManagedKnowledgeManager(store()).delete_document,
            principal.tenant_id,
            document_id,
        )
        if not result:
            raise HTTPException(status_code=404, detail="知识文档不存在或无权访问")
        return result

    @router.post("/knowledge/documents/{document_id}/publish", tags=["knowledge"])
    async def publish_knowledge_document(
        document_id: str,
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    ):
        principal = context.authorize_request(x_api_key, http_request)
        context.require_permission(principal, "knowledge.write")
        result = await run_in_threadpool(
            ManagedKnowledgeManager(store()).publish,
            principal.tenant_id,
            document_id,
        )
        if not result:
            raise HTTPException(
                status_code=404,
                detail="知识文档不存在、已废弃或无权访问",
            )
        return result

    @router.post("/knowledge/documents/{document_id}/unpublish", tags=["knowledge"])
    async def unpublish_knowledge_document(
        document_id: str,
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    ):
        principal = context.authorize_request(x_api_key, http_request)
        context.require_permission(principal, "knowledge.write")
        result = await run_in_threadpool(
            ManagedKnowledgeManager(store()).unpublish,
            principal.tenant_id,
            document_id,
        )
        if not result:
            raise HTTPException(
                status_code=404,
                detail="知识文档不是当前发布状态或无权访问",
            )
        return result

    @router.get("/memory", tags=["memory"])
    async def recall_memory(
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
        query: str = Query("", max_length=2000),
        session_id: Optional[str] = Query(None, max_length=200),
        kinds: Optional[list[str]] = Query(None),
        limit: int = Query(10, ge=1, le=20),
    ):
        principal = context.authorize_request(x_api_key, http_request)
        context.require_permission(principal, "memory.read")
        runtime = context.runtime()
        manager = getattr(runtime, "memory_manager", None) if runtime else None
        if manager is None:
            raise HTTPException(status_code=503, detail="Memory 未初始化")
        selected_kinds = None
        if kinds:
            selected_kinds = tuple(dict.fromkeys(
                str(kind).strip().lower() for kind in kinds if str(kind).strip()
            ))
            if any(kind not in MEMORY_KINDS for kind in selected_kinds):
                raise HTTPException(status_code=422, detail="unsupported memory kind")
        records = await run_in_threadpool(
            manager.recall,
            query,
            tenant_id=principal.tenant_id,
            user_id=principal.user_id,
            session_id=session_id,
            kinds=selected_kinds,
            limit=limit,
        )
        return {"memories": [record.to_context_dict() for record in records]}

    @router.post("/memory", tags=["memory"])
    async def write_memory(
        body: MemoryWriteRequest,
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    ):
        principal = context.authorize_request(x_api_key, http_request)
        context.require_permission(principal, "memory.write")
        if body.kind.lower() not in MEMORY_KINDS:
            raise HTTPException(status_code=422, detail="unsupported memory kind")
        runtime = context.runtime()
        manager = getattr(runtime, "memory_manager", None) if runtime else None
        if manager is None:
            raise HTTPException(status_code=503, detail="Memory 未初始化")
        try:
            record = await run_in_threadpool(
                manager.remember,
                body.content,
                tenant_id=principal.tenant_id,
                user_id=principal.user_id,
                kind=body.kind,
                session_id=body.session_id,
                tags=body.tags,
                importance=body.importance,
                confidence=body.confidence,
                memory_key=body.memory_key,
                source="api_explicit",
            )
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return JSONResponse(status_code=201, content=record.to_context_dict())

    @router.delete("/memory/{memory_id}", tags=["memory"])
    async def delete_memory(
        memory_id: str,
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    ):
        principal = context.authorize_request(x_api_key, http_request)
        context.require_permission(principal, "memory.write")
        runtime = context.runtime()
        manager = getattr(runtime, "memory_manager", None) if runtime else None
        if manager is None:
            raise HTTPException(status_code=503, detail="Memory 未初始化")
        deleted = await run_in_threadpool(
            manager.forget,
            memory_id,
            tenant_id=principal.tenant_id,
            user_id=principal.user_id,
        )
        if not deleted:
            raise HTTPException(status_code=404, detail="Memory not found")
        return {"deleted": True, "memory_id": memory_id}

    return router


__all__ = ["create_knowledge_router"]
