"""Durable session and Run history routes."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Query, Request
from starlette.concurrency import run_in_threadpool

from agents.ad_agent.api.context import ApiContext
from agents.ad_agent.api.models import SessionDeleteRequest, SessionRenameRequest


def create_sessions_router(context: ApiContext) -> APIRouter:
    router = APIRouter()

    @router.get("/sessions", tags=["sessions"])
    async def list_sessions(
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
        limit: int = Query(50, ge=1, le=200),
    ):
        principal = context.authorize_request(x_api_key, http_request)
        context.require_permission(principal, "ads.read")
        runtime = context.runtime()
        if not runtime or not callable(getattr(runtime, "list_conversations", None)):
            raise HTTPException(status_code=503, detail="会话存储未初始化")
        conversations = await run_in_threadpool(
            runtime.list_conversations,
            user_id=principal.user_id,
            tenant_id=principal.tenant_id,
            limit=limit,
        )
        return {"sessions": conversations}

    @router.get("/sessions/{session_id}", tags=["sessions"])
    async def get_session_history(
        session_id: str,
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
        limit: int = Query(500, ge=1, le=1000),
    ):
        principal = context.authorize_request(x_api_key, http_request)
        context.require_permission(principal, "ads.read")
        runtime = context.runtime()
        if not runtime or not callable(getattr(runtime, "get_conversation", None)):
            raise HTTPException(status_code=503, detail="会话存储未初始化")
        conversation = await run_in_threadpool(
            runtime.get_conversation,
            session_id=session_id,
            user_id=principal.user_id,
            tenant_id=principal.tenant_id,
            limit=limit,
        )
        if not conversation:
            raise HTTPException(status_code=404, detail="会话不存在或无权访问")
        return conversation

    @router.patch("/sessions/{session_id}", tags=["sessions"])
    async def rename_session(
        session_id: str,
        body: SessionRenameRequest,
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    ):
        principal = context.authorize_request(x_api_key, http_request)
        context.require_permission(principal, "ads.read")
        runtime = context.runtime()
        if not runtime or not callable(getattr(runtime, "rename_conversation", None)):
            raise HTTPException(status_code=503, detail="会话存储未初始化")
        try:
            conversation = await run_in_threadpool(
                runtime.rename_conversation,
                session_id=session_id,
                title=body.title,
                user_id=principal.user_id,
                tenant_id=principal.tenant_id,
            )
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        if not conversation:
            raise HTTPException(status_code=404, detail="会话不存在或无权访问")
        return conversation

    @router.get("/sessions/{session_id}/runs/latest", tags=["runs"])
    async def get_latest_session_run(
        session_id: str,
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    ):
        principal = context.authorize_request(x_api_key, http_request)
        context.require_permission(principal, "ads.read")
        runtime = context.runtime()
        if not runtime or not callable(getattr(runtime, "get_latest_run", None)):
            raise HTTPException(status_code=503, detail="运行状态存储未初始化")
        run = await run_in_threadpool(
            runtime.get_latest_run,
            session_id=session_id,
            user_id=principal.user_id,
            tenant_id=principal.tenant_id,
        )
        if not run:
            raise HTTPException(status_code=404, detail="运行记录不存在或无权访问")
        return run

    @router.get("/runs/{run_id}/events", tags=["runs"])
    async def get_run_events(
        run_id: str,
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
        after_seq: int = Query(0, ge=0),
        limit: int = Query(256, ge=1, le=512),
    ):
        principal = context.authorize_request(x_api_key, http_request)
        context.require_permission(principal, "ads.read")
        runtime = context.runtime()
        if not runtime or not callable(getattr(runtime, "get_run_events", None)):
            raise HTTPException(status_code=503, detail="运行状态存储未初始化")
        run = await run_in_threadpool(
            runtime.get_run_events,
            run_id=run_id,
            user_id=principal.user_id,
            tenant_id=principal.tenant_id,
            after_seq=after_seq,
            limit=limit,
        )
        if not run:
            raise HTTPException(status_code=404, detail="运行记录不存在或无权访问")
        return run

    @router.delete("/sessions", tags=["sessions"])
    async def delete_sessions(
        body: SessionDeleteRequest,
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    ):
        principal = context.authorize_request(x_api_key, http_request)
        context.require_permission(principal, "ads.read")
        runtime = context.runtime()
        if not runtime or not callable(getattr(runtime, "delete_conversations", None)):
            raise HTTPException(status_code=503, detail="会话存储未初始化")
        deleted_session_ids = await run_in_threadpool(
            runtime.delete_conversations,
            session_ids=body.session_ids,
            user_id=principal.user_id,
            tenant_id=principal.tenant_id,
        )
        if not deleted_session_ids:
            raise HTTPException(status_code=404, detail="没有找到可删除的会话")
        return {
            "deleted": True,
            "deleted_session_ids": deleted_session_ids,
            "deleted_count": len(deleted_session_ids),
        }

    @router.delete("/sessions/{session_id}", tags=["sessions"])
    async def delete_session(
        session_id: str,
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    ):
        principal = context.authorize_request(x_api_key, http_request)
        context.require_permission(principal, "ads.read")
        runtime = context.runtime()
        if not runtime or not callable(getattr(runtime, "delete_conversation", None)):
            raise HTTPException(status_code=503, detail="会话存储未初始化")
        deleted = await run_in_threadpool(
            runtime.delete_conversation,
            session_id=session_id,
            user_id=principal.user_id,
            tenant_id=principal.tenant_id,
        )
        if not deleted:
            raise HTTPException(status_code=404, detail="会话不存在或无权访问")
        return {"deleted": True, "deleted_session_id": str(session_id)}

    return router


__all__ = ["create_sessions_router"]
