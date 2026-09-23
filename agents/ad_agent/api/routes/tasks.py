"""Asynchronous task and schedule routes."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from agents.ad_agent.api.context import ApiContext
from agents.ad_agent.api.models import (
    ScheduleCreateRequest,
    TaskRecoveryRequest,
    TaskSubmitRequest,
)


def create_tasks_router(context: ApiContext) -> APIRouter:
    router = APIRouter()

    @router.post("/tasks", tags=["tasks"])
    async def submit_task(
        body: TaskSubmitRequest,
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
        idempotency_header: Optional[str] = Header(None, alias="Idempotency-Key"),
    ):
        principal = context.authorize_request(x_api_key, http_request)
        context.require_permission(principal, "ads.plan")
        runtime = context.runtime()
        if not runtime or not callable(getattr(runtime, "submit_task", None)):
            raise HTTPException(status_code=503, detail="异步任务执行器未初始化")
        context.activate_tenant_skills(principal)
        try:
            task, created = await run_in_threadpool(
                runtime.submit_task,
                body.kind,
                body.payload,
                principal=principal,
                idempotency_key=idempotency_header or body.idempotency_key,
            )
        except (ValueError, TypeError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except RuntimeError as error:
            status = 429 if "queue is full" in str(error) else 503
            raise HTTPException(status_code=status, detail=str(error)) from error
        return JSONResponse(
            status_code=202,
            content={"task": task, "created": created},
        )

    @router.get("/tasks/{task_id}", tags=["tasks"])
    async def get_task(
        task_id: str,
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    ):
        principal = context.authorize_request(x_api_key, http_request)
        context.require_permission(principal, "ads.read")
        runtime = context.runtime()
        if not runtime or not callable(getattr(runtime, "get_task", None)):
            raise HTTPException(status_code=503, detail="异步任务执行器未初始化")
        task = await run_in_threadpool(
            runtime.get_task,
            task_id,
            user_id=principal.user_id,
            tenant_id=principal.tenant_id,
        )
        if not task:
            raise HTTPException(status_code=404, detail="task not found")
        return task

    @router.get("/tasks", tags=["tasks"])
    async def list_tasks(
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
        status: Optional[str] = Query(None, max_length=200),
        limit: int = Query(50, ge=1, le=200),
    ):
        principal = context.authorize_request(x_api_key, http_request)
        context.require_permission(principal, "ads.read")
        runtime = context.runtime()
        if not runtime or not callable(getattr(runtime, "list_tasks", None)):
            raise HTTPException(status_code=503, detail="异步任务执行器未初始化")
        statuses = (
            [item.strip() for item in status.split(",") if item.strip()]
            if status else None
        )
        tasks = await run_in_threadpool(
            runtime.list_tasks,
            user_id=principal.user_id,
            tenant_id=principal.tenant_id,
            statuses=statuses,
            limit=limit,
        )
        return {"tasks": tasks}

    async def _task_action(
        task_id: str,
        http_request: Request,
        x_api_key: Optional[str],
        action: str,
    ):
        principal = context.authorize_request(x_api_key, http_request)
        context.require_permission(principal, "ads.plan")
        runtime = context.runtime()
        handler = getattr(runtime, action, None) if runtime else None
        if not callable(handler):
            raise HTTPException(status_code=503, detail="异步任务执行器未初始化")
        task = await run_in_threadpool(
            handler,
            task_id,
            user_id=principal.user_id,
            tenant_id=principal.tenant_id,
        )
        if not task:
            raise HTTPException(status_code=404, detail="task not found")
        return task

    @router.post("/tasks/{task_id}/pause", tags=["tasks"])
    async def pause_task(
        task_id: str,
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    ):
        task = await _task_action(task_id, http_request, x_api_key, "pause_task")
        if task.get("status") == "running":
            raise HTTPException(status_code=409, detail="运行中的任务不能被强制暂停")
        return task

    @router.post("/tasks/{task_id}/resume", tags=["tasks"])
    async def resume_task(
        task_id: str,
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    ):
        return await _task_action(task_id, http_request, x_api_key, "resume_task")

    @router.post("/tasks/{task_id}/recover", tags=["tasks"])
    async def recover_task(
        task_id: str,
        body: TaskRecoveryRequest,
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    ):
        principal = context.authorize_request(x_api_key, http_request)
        context.require_permission(principal, "ads.reconcile")
        runtime = context.runtime()
        if not runtime or not callable(getattr(runtime, "recover_task", None)):
            raise HTTPException(status_code=503, detail="异步任务执行器未初始化")
        try:
            task = await run_in_threadpool(
                runtime.recover_task,
                task_id,
                user_id=principal.user_id,
                tenant_id=principal.tenant_id,
                recovery_reference=body.recovery_reference,
                provider_verified=body.provider_verified,
                permissions=principal.permissions,
            )
        except PermissionError as error:
            raise HTTPException(status_code=403, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        if not task:
            raise HTTPException(
                status_code=404,
                detail="task not found or task is not recoverable",
            )
        return task

    @router.delete("/tasks/{task_id}", tags=["tasks"])
    async def cancel_task(
        task_id: str,
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    ):
        return await _task_action(task_id, http_request, x_api_key, "cancel_task")

    @router.post("/schedules", tags=["schedules"])
    async def create_schedule(
        body: ScheduleCreateRequest,
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    ):
        principal = context.authorize_request(x_api_key, http_request)
        context.require_permission(principal, "ads.plan")
        runtime = context.runtime()
        if not runtime or not callable(getattr(runtime, "create_schedule", None)):
            raise HTTPException(status_code=503, detail="定时任务服务未初始化")
        try:
            schedule = await run_in_threadpool(
                runtime.create_schedule,
                name=body.name,
                prompt=body.prompt,
                cron_expression=body.cron_expression,
                timezone=body.timezone,
                session_id=body.session_id,
                account_id=body.account_id,
                platform_params=body.platform_params,
                principal=principal,
            )
        except (ValueError, TypeError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except RuntimeError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
        return {"schedule": schedule}

    @router.get("/schedules", tags=["schedules"])
    async def list_schedules(
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
        status: Optional[str] = Query(None, max_length=200),
        limit: int = Query(100, ge=1, le=500),
    ):
        principal = context.authorize_request(x_api_key, http_request)
        context.require_permission(principal, "ads.read")
        runtime = context.runtime()
        if not runtime:
            raise HTTPException(status_code=503, detail="服务未初始化")
        statuses = (
            [item.strip() for item in status.split(",") if item.strip()]
            if status else None
        )
        schedules = await run_in_threadpool(
            runtime.list_schedules,
            user_id=principal.user_id,
            tenant_id=principal.tenant_id,
            statuses=statuses,
            limit=limit,
        )
        return {"schedules": schedules}

    async def _schedule(
        schedule_id: str,
        http_request: Request,
        x_api_key: Optional[str],
        action: str,
    ):
        principal = context.authorize_request(x_api_key, http_request)
        context.require_permission(principal, "ads.plan")
        runtime = context.runtime()
        handler = getattr(runtime, action, None) if runtime else None
        if not callable(handler):
            raise HTTPException(status_code=503, detail="定时任务服务未初始化")
        schedule = await run_in_threadpool(
            handler,
            schedule_id,
            user_id=principal.user_id,
            tenant_id=principal.tenant_id,
        )
        if not schedule:
            raise HTTPException(status_code=404, detail="schedule not found")
        return schedule

    @router.get("/schedules/{schedule_id}", tags=["schedules"])
    async def get_schedule(
        schedule_id: str,
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    ):
        principal = context.authorize_request(x_api_key, http_request)
        context.require_permission(principal, "ads.read")
        runtime = context.runtime()
        if not runtime:
            raise HTTPException(status_code=503, detail="服务未初始化")
        schedule = await run_in_threadpool(
            runtime.get_schedule,
            schedule_id,
            user_id=principal.user_id,
            tenant_id=principal.tenant_id,
        )
        if not schedule:
            raise HTTPException(status_code=404, detail="schedule not found")
        runs = await run_in_threadpool(
            runtime.list_schedule_runs,
            schedule_id=schedule_id,
            user_id=principal.user_id,
            tenant_id=principal.tenant_id,
            limit=50,
        )
        return {"schedule": schedule, "runs": runs}

    @router.get("/schedules/{schedule_id}/runs", tags=["schedules"])
    async def list_schedule_runs(
        schedule_id: str,
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
        limit: int = Query(100, ge=1, le=500),
    ):
        principal = context.authorize_request(x_api_key, http_request)
        context.require_permission(principal, "ads.read")
        runtime = context.runtime()
        if not runtime:
            raise HTTPException(status_code=503, detail="服务未初始化")
        schedule = await run_in_threadpool(
            runtime.get_schedule,
            schedule_id,
            user_id=principal.user_id,
            tenant_id=principal.tenant_id,
        )
        if not schedule:
            raise HTTPException(status_code=404, detail="schedule not found")
        runs = await run_in_threadpool(
            runtime.list_schedule_runs,
            schedule_id=schedule_id,
            user_id=principal.user_id,
            tenant_id=principal.tenant_id,
            limit=limit,
        )
        return {"runs": runs}

    @router.post("/schedules/{schedule_id}/pause", tags=["schedules"])
    async def pause_schedule(
        schedule_id: str,
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    ):
        return {"schedule": await _schedule(
            schedule_id, http_request, x_api_key, "pause_schedule"
        )}

    @router.post("/schedules/{schedule_id}/resume", tags=["schedules"])
    async def resume_schedule(
        schedule_id: str,
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    ):
        return {"schedule": await _schedule(
            schedule_id, http_request, x_api_key, "resume_schedule"
        )}

    @router.post("/schedules/{schedule_id}/run-now", tags=["schedules"])
    async def run_schedule_now(
        schedule_id: str,
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    ):
        principal = context.authorize_request(x_api_key, http_request)
        context.require_permission(principal, "ads.plan")
        runtime = context.runtime()
        if not runtime or not callable(getattr(runtime, "run_schedule_now", None)):
            raise HTTPException(status_code=503, detail="定时任务服务未初始化")
        task = await run_in_threadpool(
            runtime.run_schedule_now,
            schedule_id,
            user_id=principal.user_id,
            tenant_id=principal.tenant_id,
        )
        if not task:
            raise HTTPException(status_code=404, detail="schedule not found")
        return {"task": task}

    @router.delete("/schedules/{schedule_id}", tags=["schedules"])
    async def delete_schedule(
        schedule_id: str,
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    ):
        principal = context.authorize_request(x_api_key, http_request)
        context.require_permission(principal, "ads.plan")
        runtime = context.runtime()
        if not runtime or not callable(getattr(runtime, "delete_schedule", None)):
            raise HTTPException(status_code=503, detail="定时任务服务未初始化")
        deleted = await run_in_threadpool(
            runtime.delete_schedule,
            schedule_id,
            user_id=principal.user_id,
            tenant_id=principal.tenant_id,
        )
        if not deleted:
            raise HTTPException(status_code=404, detail="schedule not found")
        return {"deleted": True}

    return router


__all__ = ["create_tasks_router"]
