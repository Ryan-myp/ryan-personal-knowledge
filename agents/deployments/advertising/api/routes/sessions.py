"""Durable session and Run history routes."""

from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Header, HTTPException, Path, Query, Request
from starlette.concurrency import run_in_threadpool

from agents.deployments.advertising.api.context import ApiContext
from agents.deployments.advertising.api.models import (
    ConversationFeedbackRequest,
    SessionDeleteRequest,
    SessionRenameRequest,
)


def create_sessions_router(context: ApiContext) -> APIRouter:
    router = APIRouter()

    def delete_session_media(session_ids: list[str], principal: object) -> None:
        store = context.chat_media_store()
        if store is None:
            return
        for session_id in session_ids:
            store.delete_session(
                str(session_id),
                tenant_id=principal.tenant_id,
                user_id=principal.user_id,
            )

    @router.get("/sessions", tags=["sessions"])
    async def list_sessions(
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
        limit: int = Query(50, ge=1, le=200),
        before_updated_at: Optional[str] = Query(None, min_length=1, max_length=64),
        before_session_id: Optional[str] = Query(None, min_length=1, max_length=200),
    ):
        principal = context.authorize_request(x_api_key, http_request)
        context.require_permission(principal, "ads.read")
        if (before_updated_at is None) != (before_session_id is None):
            raise HTTPException(
                status_code=422,
                detail="会话游标必须同时包含更新时间和会话 ID",
            )
        runtime = context.runtime()
        if not runtime or not callable(getattr(runtime, "list_conversations", None)):
            raise HTTPException(status_code=503, detail="会话存储未初始化")
        conversations = await run_in_threadpool(
            runtime.list_conversations,
            user_id=principal.user_id,
            tenant_id=principal.tenant_id,
            limit=limit + 1,
            before_updated_at=before_updated_at,
            before_session_id=before_session_id,
        )
        has_more = len(conversations) > limit
        page = conversations[:limit]
        last_session = page[-1] if page else {}
        next_cursor = (
            {
                "updated_at": last_session.get("updated_at"),
                "session_id": last_session.get("session_id"),
            }
            if has_more and last_session.get("updated_at") and last_session.get("session_id")
            else None
        )
        return {
            "sessions": page,
            "has_more": bool(has_more and next_cursor),
            "next_cursor": next_cursor,
        }

    @router.get("/sessions/{session_id}", tags=["sessions"])
    async def get_session_history(
        session_id: str,
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
        limit: int = Query(10, ge=1, le=100),
        before_message_id: Optional[str] = Query(None, min_length=1, max_length=128),
    ):
        principal = context.authorize_request(x_api_key, http_request)
        context.require_permission(principal, "ads.read")
        runtime = context.runtime()
        if not runtime or not callable(getattr(runtime, "get_conversation", None)):
            raise HTTPException(status_code=503, detail="会话存储未初始化")
        try:
            conversation = await run_in_threadpool(
                runtime.get_conversation,
                session_id=session_id,
                user_id=principal.user_id,
                tenant_id=principal.tenant_id,
                limit=limit,
                before_message_id=before_message_id,
            )
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
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

    @router.post(
        "/sessions/{session_id}/turns/{turn_id}/feedback",
        tags=["sessions"],
    )
    async def submit_conversation_feedback(
        session_id: Annotated[str, Path(min_length=1, max_length=200)],
        turn_id: Annotated[str, Path(min_length=1, max_length=128)],
        body: ConversationFeedbackRequest,
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    ):
        principal = context.authorize_request(x_api_key, http_request)
        context.require_permission(principal, "ads.read")
        runtime = context.runtime()
        submit = getattr(runtime, "submit_conversation_feedback", None)
        if not callable(submit):
            raise HTTPException(status_code=503, detail="会话反馈服务未初始化")
        try:
            saved = await run_in_threadpool(
                submit,
                session_id=session_id,
                turn_id=turn_id,
                rating=body.rating,
                reason=body.reason,
                user_id=principal.user_id,
                tenant_id=principal.tenant_id,
            )
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except RuntimeError as error:
            raise HTTPException(
                status_code=503,
                detail="会话反馈存储暂不可用",
            ) from error
        if not saved:
            raise HTTPException(status_code=404, detail="会话或 assistant 回合不存在")
        return {
            "saved": True,
            "session_id": session_id,
            "turn_id": turn_id,
            "rating": body.rating,
        }

    @router.get("/feedback/trend", tags=["sessions"])
    async def get_conversation_feedback_trend(
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
        days: int = Query(30, ge=7, le=90),
    ):
        principal = context.authorize_request(x_api_key, http_request)
        context.require_permission(principal, "ads.read")
        if days not in {7, 30, 90}:
            raise HTTPException(
                status_code=422,
                detail="统计范围仅支持 7、30 或 90 天",
            )
        runtime = context.runtime()
        getter = getattr(runtime, "get_conversation_feedback_trend", None)
        if not callable(getter):
            raise HTTPException(status_code=503, detail="反馈趋势服务未初始化")
        try:
            return await run_in_threadpool(
                getter,
                days=days,
                user_id=principal.user_id,
                tenant_id=principal.tenant_id,
            )
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except RuntimeError as error:
            raise HTTPException(
                status_code=503,
                detail="反馈趋势存储暂不可用",
            ) from error

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
        await run_in_threadpool(delete_session_media, deleted_session_ids, principal)
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
        await run_in_threadpool(delete_session_media, [str(session_id)], principal)
        return {"deleted": True, "deleted_session_id": str(session_id)}

    return router


__all__ = ["create_sessions_router"]
