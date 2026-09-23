"""Managed and Builtin Skill management routes."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from agents.ad_agent.api.context import ApiContext, read_request_body_limited
from agents.ad_agent.api.models import SkillVersionRequest
from agents.ad_agent.skill_management import SkillPackageError

from .management_support import ManagementRouteSupport


_MAX_ARCHIVE_BODY_BYTES = 16 * 1024 * 1024


def create_skill_router(context: ApiContext) -> APIRouter:
    router = APIRouter()
    support = ManagementRouteSupport(context)

    @router.get("/skills", tags=["skills"])
    async def list_managed_skills(
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
        skill_name: Optional[str] = Query(None, max_length=64),
        limit: int = Query(50, ge=1, le=200),
    ):
        principal = context.authorize_request(x_api_key, http_request)
        support.require_permission(principal, "skills.read", "Skill")
        managed = await run_in_threadpool(
            support.skill_manager().list_versions,
            principal.tenant_id,
            skill_name,
            limit,
        )
        builtin = await run_in_threadpool(
            support.builtin_skill_catalog().list_versions,
            skill_name,
            limit,
        )
        return {
            "tenant_id": principal.tenant_id,
            "skills": managed + builtin,
            "managed_skills": managed,
            "builtin_skills": builtin,
        }

    @router.post("/skills/{skill_name}/versions", tags=["skills"])
    async def create_managed_skill_version(
        skill_name: str,
        body: SkillVersionRequest,
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    ):
        principal = context.authorize_request(x_api_key, http_request)
        support.require_permission(principal, "skills.write", "Skill")
        try:
            result = await run_in_threadpool(
                support.skill_manager().create_version,
                tenant_id=principal.tenant_id,
                skill_name=skill_name,
                version=body.version,
                raw_files=body.files,
                created_by=principal.user_id,
            )
        except SkillPackageError as error:
            status = 409 if "already exists" in str(error) else 422
            raise HTTPException(status_code=status, detail=str(error)) from error
        return JSONResponse(status_code=201, content=result)

    @router.post(
        "/skills/{skill_name}/versions/archive",
        tags=["skills"],
    )
    async def upload_managed_skill_archive(
        skill_name: str,
        request: Request,
        version: str = Query(..., min_length=5, max_length=80),
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    ):
        principal = context.authorize_request(x_api_key, request)
        support.require_permission(principal, "skills.write", "Skill")
        try:
            result = await run_in_threadpool(
                support.skill_manager().create_version_archive,
                principal.tenant_id,
                skill_name,
                version,
                await read_request_body_limited(
                    request, max_bytes=_MAX_ARCHIVE_BODY_BYTES
                ),
                principal.user_id,
            )
        except SkillPackageError as error:
            status = 409 if "already exists" in str(error) else 422
            raise HTTPException(status_code=status, detail=str(error)) from error
        return JSONResponse(status_code=201, content=result)

    @router.get("/skills/{skill_name}/versions", tags=["skills"])
    async def list_managed_skill_versions(
        skill_name: str,
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
        limit: int = Query(50, ge=1, le=200),
    ):
        principal = context.authorize_request(x_api_key, http_request)
        support.require_permission(principal, "skills.read", "Skill")
        versions = await run_in_threadpool(
            support.skill_manager().list_versions,
            principal.tenant_id,
            skill_name,
            limit,
        )
        return {
            "tenant_id": principal.tenant_id,
            "skill_name": skill_name,
            "versions": versions,
        }

    @router.get(
        "/skills/builtin/{skill_name}/versions/{version}",
        tags=["skills"],
    )
    async def get_builtin_skill_version(
        skill_name: str,
        version: str,
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    ):
        principal = context.authorize_request(x_api_key, http_request)
        support.require_permission(principal, "skills.read", "Skill")
        result = await run_in_threadpool(
            support.builtin_skill_catalog().get_version,
            skill_name,
            version,
        )
        if not result:
            raise HTTPException(
                status_code=404,
                detail="Builtin Skill version not found",
            )
        return result

    @router.get(
        "/skills/{skill_name}/versions/{version}",
        tags=["skills"],
    )
    async def get_managed_skill_version(
        skill_name: str,
        version: str,
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    ):
        principal = context.authorize_request(x_api_key, http_request)
        support.require_permission(principal, "skills.read", "Skill")
        result = await run_in_threadpool(
            support.skill_manager().get_version,
            principal.tenant_id,
            skill_name,
            version,
            include_files=True,
        )
        if not result:
            raise HTTPException(status_code=404, detail="Skill version not found")
        return result

    async def publish_skill(
        skill_name: str,
        version: str,
        publish: bool,
        http_request: Request,
        x_api_key: Optional[str],
    ):
        principal = context.authorize_request(x_api_key, http_request)
        support.require_permission(principal, "skills.write", "Skill")
        handler = (
            support.skill_manager().publish
            if publish else support.skill_manager().unpublish
        )
        try:
            result = await run_in_threadpool(
                handler,
                principal.tenant_id,
                skill_name,
                version,
                runtime=context.runtime(),
            )
        except PermissionError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        except SkillPackageError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        if not result:
            raise HTTPException(
                status_code=409 if not publish else 404,
                detail=(
                    "Skill version is not the current published release"
                    if not publish else "Skill version not found"
                ),
            )
        return result

    @router.post(
        "/skills/{skill_name}/versions/{version}/publish",
        tags=["skills"],
    )
    async def publish_managed_skill_version(
        skill_name: str,
        version: str,
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    ):
        return await publish_skill(
            skill_name, version, True, http_request, x_api_key
        )

    @router.post(
        "/skills/{skill_name}/versions/{version}/unpublish",
        tags=["skills"],
    )
    async def unpublish_managed_skill_version(
        skill_name: str,
        version: str,
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    ):
        return await publish_skill(
            skill_name, version, False, http_request, x_api_key
        )

    @router.post(
        "/skills/{skill_name}/versions/{version}/evaluate",
        tags=["skills"],
    )
    async def evaluate_managed_skill_version(
        skill_name: str,
        version: str,
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    ):
        principal = context.authorize_request(x_api_key, http_request)
        support.require_permission(principal, "skills.evaluate", "Skill")
        try:
            result = await run_in_threadpool(
                support.skill_manager().start_evaluation,
                principal.tenant_id,
                skill_name,
                version,
            )
        except KeyError as error:
            raise HTTPException(
                status_code=404, detail="Skill version not found"
            ) from error
        except SkillPackageError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return JSONResponse(status_code=202, content=result)

    @router.get("/skills/evaluations/{run_id}", tags=["skills"])
    async def get_managed_skill_evaluation(
        run_id: str,
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    ):
        principal = context.authorize_request(x_api_key, http_request)
        support.require_permission(principal, "skills.read", "Skill")
        result = await run_in_threadpool(
            support.skill_manager().get_evaluation,
            principal.tenant_id,
            run_id,
        )
        if not result:
            raise HTTPException(status_code=404, detail="Skill evaluation not found")
        return result

    return router


__all__ = ["create_skill_router"]
