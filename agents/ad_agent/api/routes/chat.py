"""Chat HTTP routes.

This module translates HTTP requests into the generic Runtime contract. It
does not parse intent, execute Tools, or reconstruct execution traces.
"""

from __future__ import annotations

import asyncio
import json
import queue
from typing import Any, Optional

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.concurrency import run_in_threadpool

from agents.ad_agent.api.context import ApiContext
from agents.ad_agent.api.models import ChatRequest, ChatStreamRequest


def create_chat_router(context: ApiContext) -> APIRouter:
    """Build the chat route group against application-owned callbacks."""
    router = APIRouter()

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
            context.activate_tenant_skills(principal)
            context.sync_tenant_extensions(principal)
            if request.confirmed and not request.confirmation_payload:
                raise HTTPException(
                    status_code=400,
                    detail="confirmed=true 必须携带与当前计划匹配的 confirmation_payload",
                )
            result = await run_in_threadpool(
                runtime.run,
                user_input=request.user_input,
                session_id=request.session_id,
                account_id=request.account_id or None,
                platform_params=request.platform_params,
                confirmed=request.confirmed,
                confirmation_payload=request.confirmation_payload,
                creation_blueprint_id=request.creation_blueprint_id,
                creation_blueprint_version=request.creation_blueprint_version,
                creation_template_id=request.creation_template_id,
                execution_mode=request.execution_mode,
                principal=principal,
            )
            return JSONResponse(content=result)
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
            context.activate_tenant_skills(principal)
            context.sync_tenant_extensions(principal)
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
                    user_input=request.user_input,
                    session_id=request.session_id,
                    account_id=request.account_id or None,
                    platform_params=request.platform_params,
                    confirmed=request.confirmed,
                    confirmation_payload=request.confirmation_payload,
                    creation_blueprint_id=request.creation_blueprint_id,
                    creation_blueprint_version=request.creation_blueprint_version,
                    creation_template_id=request.creation_template_id,
                    execution_mode=request.execution_mode,
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
                    "status": (
                        "awaiting_confirmation"
                        if result.get("needs_confirmation")
                        else "succeeded"
                    ),
                    "content": context.redact(result.get("reply", "")),
                    "session_id": result.get("session_id"),
                    "turn_id": result.get("turn_id"),
                    "run_id": run_id,
                    "needs_confirmation": bool(
                        result.get("needs_confirmation")
                    ),
                    "confirmation_payload": context.redact(
                        result.get("confirmation_payload")
                    ),
                    "results": safe_results,
                    "ui": context.redact(result.get("ui") or {}),
                })
                yield event(final_event or {
                    "type": "done",
                    "event_type": "done",
                    "status": (
                        "awaiting_confirmation"
                        if result.get("needs_confirmation")
                        else "succeeded"
                    ),
                })

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
