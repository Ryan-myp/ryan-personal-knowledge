"""Durable workflow recovery routes."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Request
from starlette.concurrency import run_in_threadpool

from agents.ad_agent.api.context import ApiContext
from agents.ad_agent.api.models import WorkflowReconcileRequest


def create_workflows_router(context: ApiContext) -> APIRouter:
    router = APIRouter()

    def runtime_or_503():
        runtime = context.runtime()
        if runtime is None:
            raise HTTPException(status_code=503, detail="服务未初始化")
        return runtime

    @router.get("/workflows/{workflow_id}", tags=["workflows"])
    async def get_workflow(
        workflow_id: str,
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    ):
        principal = context.authorize_request(x_api_key, http_request)
        try:
            workflow = await run_in_threadpool(
                runtime_or_503().get_workflow,
                workflow_id,
                user_id=principal.user_id,
                tenant_id=principal.tenant_id,
            )
        except PermissionError as error:
            raise HTTPException(status_code=403, detail=str(error)) from error
        if not workflow:
            raise HTTPException(status_code=404, detail="workflow not found")
        return workflow

    @router.delete("/workflows/{workflow_id}", tags=["workflows"])
    async def cancel_workflow(
        workflow_id: str,
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    ):
        principal = context.authorize_request(x_api_key, http_request)
        try:
            cancelled = await run_in_threadpool(
                runtime_or_503().cancel_workflow,
                workflow_id,
                user_id=principal.user_id,
                tenant_id=principal.tenant_id,
            )
        except PermissionError as error:
            raise HTTPException(status_code=403, detail=str(error)) from error
        if not cancelled:
            raise HTTPException(
                status_code=404,
                detail="workflow not found or not cancellable",
            )
        return {"workflow_id": workflow_id, "status": "cancelled"}

    @router.get("/workflows/{workflow_id}/resume-plan", tags=["workflows"])
    async def get_workflow_resume_plan(
        workflow_id: str,
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    ):
        principal = context.authorize_request(x_api_key, http_request)
        try:
            return await run_in_threadpool(
                runtime_or_503().get_workflow_resume_plan,
                workflow_id,
                user_id=principal.user_id,
                tenant_id=principal.tenant_id,
            )
        except PermissionError as error:
            raise HTTPException(status_code=403, detail=str(error)) from error
        except KeyError as error:
            raise HTTPException(status_code=404, detail="workflow not found") from error

    @router.post(
        "/workflows/{workflow_id}/reconcile",
        tags=["workflows"],
    )
    async def reconcile_workflow(
        workflow_id: str,
        body: WorkflowReconcileRequest,
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    ):
        principal = context.authorize_request(x_api_key, http_request)
        context.require_permission(principal, "ads.reconcile")
        if not isinstance(body.observations, (list, dict)):
            raise HTTPException(
                status_code=422,
                detail="observations must be an array or object",
            )
        try:
            return await run_in_threadpool(
                runtime_or_503().reconcile_workflow,
                workflow_id,
                body.observations,
                user_id=principal.user_id,
                tenant_id=principal.tenant_id,
            )
        except PermissionError as error:
            raise HTTPException(status_code=403, detail=str(error)) from error
        except KeyError as error:
            raise HTTPException(status_code=404, detail="workflow not found") from error
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @router.post(
        "/workflows/{workflow_id}/reconcile/provider",
        tags=["workflows"],
    )
    async def reconcile_workflow_from_provider(
        workflow_id: str,
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    ):
        principal = context.authorize_request(x_api_key, http_request)
        context.require_permission(principal, "ads.reconcile")
        try:
            return await run_in_threadpool(
                runtime_or_503().reconcile_workflow_from_provider,
                workflow_id=workflow_id,
                principal=principal,
            )
        except PermissionError as error:
            raise HTTPException(status_code=403, detail=str(error)) from error
        except KeyError as error:
            raise HTTPException(status_code=404, detail="workflow not found") from error
        except (RuntimeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    return router


__all__ = ["create_workflows_router"]
