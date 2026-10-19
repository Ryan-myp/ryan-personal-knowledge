"""Chat HTTP routes.

This module translates HTTP requests into the generic Runtime contract. It
does not parse intent, execute Tools, or reconstruct execution traces.
"""

from __future__ import annotations

import asyncio
import json
import queue
from typing import Any, Mapping, Optional

from fastapi import APIRouter, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse
from starlette.concurrency import run_in_threadpool

from agents.deployments.advertising.api.context import (
    ApiContext,
    read_request_body_limited,
)
from agents.deployments.advertising.api.models import ChatRequest, ChatStreamRequest
from agents.tools.advertising.shared.domain.conversation import visible_run_reply

_STREAM_RUN_STATUSES = frozenset({
    "awaiting_confirmation",
    "awaiting_input",
    "cancelled",
    "failed",
    "partially_failed",
    "recovery_required",
    "succeeded",
    "unknown",
})
_STREAM_TERMINAL_STATUSES = _STREAM_RUN_STATUSES - {"succeeded"}


def _confirmation_payload_for_response(context: ApiContext, value: Any) -> Any:
    """Expose the one-time confirmation credential only in the API response."""
    if not isinstance(value, dict):
        return context.redact(value)
    safe_payload = context.redact(value)
    if not isinstance(safe_payload, dict):
        return safe_payload
    token = value.get("confirmation_token")
    if isinstance(token, str) and token:
        safe_payload["confirmation_token"] = token
    return safe_payload


def _chat_result_for_response(context: ApiContext, result: Any) -> Any:
    """Redact a Run result while preserving its top-level confirmation token."""
    safe_result = context.redact(result)
    if not isinstance(result, dict) or not isinstance(safe_result, dict):
        return safe_result
    visible_reply = _chat_reply_content(safe_result)
    if visible_reply:
        safe_result["reply"] = context.redact(visible_reply)
    if isinstance(result.get("confirmation_payload"), dict):
        safe_result["confirmation_payload"] = _confirmation_payload_for_response(
            context, result["confirmation_payload"],
        )
    return safe_result


def _stream_run_status(
    result: Mapping[str, Any],
    final_event: Optional[Mapping[str, Any]],
) -> str:
    """Use the completed Run result as the terminal status source of truth."""
    result_status = str(result.get("status") or "").strip().lower()
    if result_status in _STREAM_TERMINAL_STATUSES:
        return result_status
    if result.get("needs_confirmation"):
        return "awaiting_confirmation"
    if result.get("needs_input"):
        return "awaiting_input"

    items = [
        item for item in (result.get("results") or [])
        if isinstance(item, Mapping)
        and not item.get("skipped")
        and not item.get("needs_input")
        and not item.get("needs_confirmation")
    ]
    failures = sum(item.get("success") is False for item in items)
    successes = sum(item.get("success") is True for item in items)
    if failures and successes:
        return "partially_failed"
    if failures:
        return "failed"
    if result.get("success") is False:
        return "failed"
    if result_status == "succeeded":
        return result_status

    event_status = str((final_event or {}).get("status") or "").strip().lower()
    return event_status if event_status in _STREAM_RUN_STATUSES else "succeeded"


def _chat_reply_content(result: Mapping[str, Any]) -> str:
    """Preserve a safe Run failure reason when no model reply was produced."""
    return visible_run_reply(result)


def _validated_user_input(user_input: str, media_ids: list[str]) -> str:
    content = str(user_input or "")
    if not content.strip() and not media_ids:
        raise HTTPException(
            status_code=422,
            detail="请输入消息，或先添加图片/视频附件",
        )
    return content


def _load_chat_input_media(
    context: ApiContext,
    media_ids: list[str],
    *,
    session_id: Optional[str],
    principal: Any,
) -> tuple[Any, ...]:
    if not media_ids:
        return ()
    if not str(session_id or "").strip():
        raise HTTPException(
            status_code=422,
            detail="使用附件时必须指定 session_id",
        )
    store = context.chat_media_store()
    if store is None:
        raise HTTPException(status_code=503, detail="聊天附件存储未初始化")
    try:
        return store.load_for_model(
            media_ids,
            session_id=session_id,
            tenant_id=principal.tenant_id,
            user_id=principal.user_id,
        )
    except FileNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail="附件不存在或无权访问",
        ) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


def create_chat_router(context: ApiContext) -> APIRouter:
    """Build the chat route group against application-owned callbacks."""
    router = APIRouter()

    @router.post("/chat/media", status_code=201, tags=["chat"])
    async def upload_chat_media(
        http_request: Request,
        session_id: str = Query(min_length=1, max_length=200),
        filename: str = Query(min_length=1, max_length=240),
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    ):
        principal = context.authorize_request(x_api_key, http_request)
        context.require_permission(principal, "ads.read")
        store = context.chat_media_store()
        if store is None:
            raise HTTPException(status_code=503, detail="聊天附件存储未初始化")
        content = await read_request_body_limited(
            http_request,
            max_bytes=int(store.max_video_bytes),
        )
        try:
            metadata = await run_in_threadpool(
                store.save,
                content,
                filename=filename,
                content_type=http_request.headers.get("content-type", ""),
                session_id=session_id,
                tenant_id=principal.tenant_id,
                user_id=principal.user_id,
            )
        except ValueError as error:
            message = str(error)
            status_code = (
                413
                if "size limit" in message
                or "storage limit" in message
                or "at most 50 attachments" in message
                else 415
            )
            raise HTTPException(status_code=status_code, detail=message) from error
        return metadata

    @router.get("/chat/media/{attachment_id}", tags=["chat"])
    async def get_chat_media(
        attachment_id: str,
        http_request: Request,
        session_id: str = Query(min_length=1, max_length=200),
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    ):
        principal = context.authorize_request(x_api_key, http_request)
        context.require_permission(principal, "ads.read")
        store = context.chat_media_store()
        if store is None:
            raise HTTPException(status_code=503, detail="聊天附件存储未初始化")
        try:
            media = await run_in_threadpool(
                store.load,
                attachment_id,
                session_id=session_id,
                tenant_id=principal.tenant_id,
                user_id=principal.user_id,
            )
        except FileNotFoundError as error:
            raise HTTPException(
                status_code=404,
                detail="附件不存在或无权访问",
            ) from error
        return Response(
            content=media.content,
            media_type=media.metadata["media_type"],
            headers={
                "Cache-Control": "private, no-store",
                "X-Content-Type-Options": "nosniff",
                "Content-Disposition": "inline",
            },
        )

    @router.delete(
        "/chat/media/{attachment_id}",
        status_code=204,
        tags=["chat"],
    )
    async def delete_chat_media(
        attachment_id: str,
        http_request: Request,
        session_id: str = Query(min_length=1, max_length=200),
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    ):
        principal = context.authorize_request(x_api_key, http_request)
        context.require_permission(principal, "ads.read")
        store = context.chat_media_store()
        if store is None:
            raise HTTPException(status_code=503, detail="聊天附件存储未初始化")
        try:
            deleted = await run_in_threadpool(
                store.delete,
                attachment_id,
                session_id=session_id,
                tenant_id=principal.tenant_id,
                user_id=principal.user_id,
            )
        except FileNotFoundError as error:
            raise HTTPException(
                status_code=404,
                detail="附件不存在或无权访问",
            ) from error
        if not deleted:
            raise HTTPException(status_code=404, detail="附件不存在或无权访问")
        return Response(status_code=204)

    @router.post("/chat", tags=["chat"])
    async def chat(
        request: ChatRequest,
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    ):
        runtime = context.runtime()
        if not runtime:
            raise HTTPException(status_code=503, detail="服务未初始化")
        try:
            principal = context.authorize_request(x_api_key, http_request)
            user_input = _validated_user_input(request.user_input, request.media_ids)
            input_media = await run_in_threadpool(
                _load_chat_input_media,
                context,
                request.media_ids,
                session_id=request.session_id,
                principal=principal,
            )
            await run_in_threadpool(
                context.activate_tenant_skills, principal
            )
            await run_in_threadpool(
                context.sync_tenant_extensions, principal
            )
            if request.confirmed and not request.confirmation_payload:
                raise HTTPException(
                    status_code=400,
                    detail="confirmed=true 必须携带与当前计划匹配的 confirmation_payload",
                )
            result = await run_in_threadpool(
                runtime.run,
                user_input=user_input,
                session_id=request.session_id,
                account_id=request.account_id or None,
                input_media=input_media,
                platform_params=request.platform_params,
                confirmed=request.confirmed,
                confirmation_payload=request.confirmation_payload,
                creation_blueprint_id=request.creation_blueprint_id,
                creation_blueprint_version=request.creation_blueprint_version,
                creation_template_id=request.creation_template_id,
                execution_mode=request.execution_mode,
                tool_allowlist=request.tool_allowlist,
                principal=principal,
            )
            return JSONResponse(
                content=_chat_result_for_response(context, result)
            )
        except HTTPException:
            raise
        except PermissionError as error:
            raise HTTPException(status_code=403, detail=str(error)) from error
        except RuntimeError as error:
            message = str(error)
            if "session is busy" in message:
                raise HTTPException(
                    status_code=409,
                    detail="会话正在其他实例执行，请稍后重试",
                ) from error
            if "durable Agent run persistence" in message:
                raise HTTPException(
                    status_code=503,
                    detail="运行状态存储暂不可用，请稍后重试",
                ) from error
            return JSONResponse(
                content={
                    "success": False,
                    "error": context.safe_exception_text(error),
                },
                status_code=500,
            )
        except Exception as error:
            return JSONResponse(
                content={
                    "success": False,
                    "error": context.safe_exception_text(error),
                },
                status_code=500,
            )

    @router.post("/chat/stream", tags=["chat"])
    async def chat_stream(
        request: ChatStreamRequest,
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    ):
        """Stream safe Runtime events over SSE."""
        runtime = context.runtime()
        if not runtime:
            return JSONResponse(
                content={"success": False, "error": "服务未初始化"},
                status_code=503,
            )
        try:
            principal = context.authorize_request(x_api_key, http_request)
            user_input = _validated_user_input(request.user_input, request.media_ids)
            input_media = await run_in_threadpool(
                _load_chat_input_media,
                context,
                request.media_ids,
                session_id=request.session_id,
                principal=principal,
            )
            await run_in_threadpool(
                context.activate_tenant_skills, principal
            )
            await run_in_threadpool(
                context.sync_tenant_extensions, principal
            )
            if request.confirmed and not request.confirmation_payload:
                raise HTTPException(
                    status_code=400,
                    detail="confirmed=true 必须携带与当前计划匹配的 confirmation_payload",
                )

            async def generate():
                def event(payload: dict[str, Any]) -> str:
                    return (
                        f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                    )

                event_queue: queue.Queue[dict[str, Any]] = queue.Queue(
                    maxsize=256
                )
                yield event({
                    "type": "start",
                    "event_type": "start",
                    "status": "running",
                    "safe_metadata": {"source": "stream_gateway"},
                })

                def observe(payload: dict[str, Any]) -> None:
                    try:
                        event_queue.put_nowait(payload)
                    except queue.Full:
                        return

                task = asyncio.create_task(run_in_threadpool(
                    runtime.run,
                    user_input=user_input,
                    session_id=request.session_id,
                    account_id=request.account_id or None,
                    input_media=input_media,
                    platform_params=request.platform_params,
                    confirmed=request.confirmed,
                    confirmation_payload=request.confirmation_payload,
                    creation_blueprint_id=request.creation_blueprint_id,
                    creation_blueprint_version=request.creation_blueprint_version,
                    creation_template_id=request.creation_template_id,
                    execution_mode=request.execution_mode,
                    tool_allowlist=request.tool_allowlist,
                    principal=principal,
                    event_callback=observe,
                ))
                final_event = None
                reply_marker = None
                try:
                    while True:
                        try:
                            payload = await asyncio.to_thread(
                                event_queue.get, True, 0.25
                            )
                        except queue.Empty:
                            if task.done():
                                break
                            continue
                        if payload.get("type") == "done":
                            final_event = payload
                        elif payload.get("type") == "reply":
                            reply_marker = payload
                        else:
                            yield event(payload)
                    result = await task
                except Exception as error:
                    yield event({
                        "type": "error",
                        "event_type": "error",
                        "status": "failed",
                        "safe_metadata": {"reason": "runtime_error"},
                        "error": context.safe_exception_text(error),
                    })
                    yield event({"type": "done", "status": "failed"})
                    return

                safe_results = []
                for item in (
                    result.get("results", [])
                    if isinstance(result, dict) else []
                ):
                    if not isinstance(item, dict):
                        continue
                    safe_results.append({
                        key: context.redact(item.get(key))
                        for key in (
                            "tool", "platform", "resource_type", "success",
                            "error", "needs_confirmation", "skipped", "data",
                        )
                        if key in item
                    })
                run_id = result.get("run_id") if isinstance(result, dict) else None
                run_result = result if isinstance(result, Mapping) else {}
                run_status = _stream_run_status(run_result, final_event)
                get_latest_run = getattr(runtime, "get_latest_run", None)
                if (
                    not run_id
                    and isinstance(result, dict)
                    and result.get("session_id")
                    and callable(get_latest_run)
                ):
                    latest = await run_in_threadpool(
                        get_latest_run,
                        session_id=result.get("session_id"),
                        user_id=principal.user_id,
                        tenant_id=principal.tenant_id,
                    )
                    run_id = (latest or {}).get("run_id")
                yield event({
                    "type": "reply",
                    "event_type": "reply",
                    "trace_id": (reply_marker or {}).get("trace_id"),
                    "seq": (reply_marker or {}).get("seq"),
                    "status": run_status,
                    "content": context.redact(_chat_reply_content(run_result)),
                    "error": context.redact(run_result.get("error")),
                    "session_id": result.get("session_id"),
                    "turn_id": result.get("turn_id"),
                    "run_id": run_id,
                    "needs_confirmation": bool(
                        result.get("needs_confirmation")
                    ),
                    "confirmation_payload": _confirmation_payload_for_response(
                        context, result.get("confirmation_payload"),
                    ),
                    "results": safe_results,
                    "ui": context.redact(result.get("ui") or {}),
                })
                terminal_event = dict(final_event or {})
                terminal_event.update({
                    "type": "done",
                    "event_type": "done",
                    "status": run_status,
                })
                yield event(terminal_event)

            return StreamingResponse(
                generate(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                },
            )
        except HTTPException:
            raise
        except Exception as error:
            return JSONResponse(
                content={
                    "success": False,
                    "error": context.safe_exception_text(error),
                },
                status_code=500,
            )

    return router


__all__ = ["create_chat_router"]
