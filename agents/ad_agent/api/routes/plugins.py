"""Plugin package management routes."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Request, Query
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from agents.ad_agent.api.context import ApiContext, read_request_body_limited
from agents.ad_agent.api.models import PluginPackageRequest
from agents.ad_agent.core.plugin_package import PluginPackageError

from .management_support import ManagementRouteSupport


_MAX_ARCHIVE_BODY_BYTES = 16 * 1024 * 1024


def create_plugin_router(context: ApiContext) -> APIRouter:
    router = APIRouter()
    support = ManagementRouteSupport(context)

    @router.get("/plugins", tags=["info"])
    async def get_plugins(
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    ):
        principal = context.authorize_request(x_api_key, http_request)
        runtime = context.runtime()
        if not runtime:
            return {"plugins": []}
        return {
            "plugins": await run_in_threadpool(
                runtime.list_plugins, principal.tenant_id
            ),
        }

    @router.get("/plugins/packages", tags=["plugins"])
    async def list_plugin_packages(
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
        plugin_id: Optional[str] = Query(None, max_length=128),
        limit: int = Query(50, ge=1, le=200),
    ):
        principal = context.authorize_request(x_api_key, http_request)
        support.require_permission(principal, "plugins.read", "Plugin")
        packages = await run_in_threadpool(
            support.plugin_manager().list_packages,
            principal.tenant_id,
            plugin_id,
            limit,
        )
        return {"tenant_id": principal.tenant_id, "packages": packages}

    @router.post("/plugins/packages", tags=["plugins"])
    async def create_plugin_package(
        body: PluginPackageRequest,
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    ):
        principal = context.authorize_request(x_api_key, http_request)
        support.require_permission(principal, "plugins.write", "Plugin")
        try:
            result = await run_in_threadpool(
                support.plugin_manager().create_package,
                principal.tenant_id,
                body.manifest,
                body.files,
                principal.user_id,
            )
        except PermissionError as error:
            raise HTTPException(status_code=403, detail=str(error)) from error
        except PluginPackageError as error:
            status = 409 if "already exists" in str(error) else 422
            raise HTTPException(status_code=status, detail=str(error)) from error
        return JSONResponse(status_code=201, content=result)

    @router.post("/plugins/packages/archive", tags=["plugins"])
    async def upload_plugin_package_archive(
        request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    ):
        principal = context.authorize_request(x_api_key, request)
        support.require_permission(principal, "plugins.write", "Plugin")
        try:
            result = await run_in_threadpool(
                support.plugin_manager().create_archive,
                principal.tenant_id,
                await read_request_body_limited(
                    request, max_bytes=_MAX_ARCHIVE_BODY_BYTES
                ),
                principal.user_id,
            )
        except PermissionError as error:
            raise HTTPException(status_code=403, detail=str(error)) from error
        except PluginPackageError as error:
            status = 409 if "already exists" in str(error) else 422
            raise HTTPException(status_code=status, detail=str(error)) from error
        return JSONResponse(status_code=201, content=result)

    @router.get(
        "/plugins/packages/{plugin_id:path}/versions/{version}",
        tags=["plugins"],
    )
    async def get_plugin_package(
        plugin_id: str,
        version: str,
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    ):
        principal = context.authorize_request(x_api_key, http_request)
        support.require_permission(principal, "plugins.read", "Plugin")
        result = await run_in_threadpool(
            support.plugin_manager().get_package,
            principal.tenant_id,
            plugin_id,
            version,
            include_files=True,
        )
        if not result:
            raise HTTPException(status_code=404, detail="Plugin package not found")
        return result

    @router.get(
        "/plugins/packages/{plugin_id:path}/versions/{version}/health",
        tags=["plugins"],
    )
    async def health_plugin_package(
        plugin_id: str,
        version: str,
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    ):
        principal = context.authorize_request(x_api_key, http_request)
        support.require_permission(principal, "plugins.read", "Plugin")
        result = await run_in_threadpool(
            support.plugin_manager().health,
            principal.tenant_id,
            plugin_id,
            version,
        )
        if not result:
            raise HTTPException(status_code=404, detail="Plugin package not found")
        return result

    @router.post(
        "/plugins/packages/{plugin_id:path}/versions/{version}/activate",
        tags=["plugins"],
    )
    async def activate_plugin_package(
        plugin_id: str,
        version: str,
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    ):
        principal = context.authorize_request(x_api_key, http_request)
        support.require_permission(principal, "plugins.write", "Plugin")
        try:
            result = await run_in_threadpool(
                support.plugin_manager().activate,
                principal.tenant_id,
                plugin_id,
                version,
            )
        except PluginPackageError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        if not result:
            raise HTTPException(status_code=404, detail="Plugin package not found")
        return result

    @router.post(
        "/plugins/packages/{plugin_id:path}/versions/{version}/deactivate",
        tags=["plugins"],
    )
    async def deactivate_plugin_package(
        plugin_id: str,
        version: str,
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    ):
        principal = context.authorize_request(x_api_key, http_request)
        support.require_permission(principal, "plugins.write", "Plugin")
        result = await run_in_threadpool(
            support.plugin_manager().deactivate,
            principal.tenant_id,
            plugin_id,
            version,
        )
        if not result:
            raise HTTPException(
                status_code=409,
                detail="Plugin package is not the active release",
            )
        return result

    @router.delete(
        "/plugins/packages/{plugin_id:path}/versions/{version}",
        tags=["plugins"],
    )
    async def uninstall_plugin_package(
        plugin_id: str,
        version: str,
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    ):
        principal = context.authorize_request(x_api_key, http_request)
        support.require_permission(principal, "plugins.write", "Plugin")
        result = await run_in_threadpool(
            support.plugin_manager().uninstall,
            principal.tenant_id,
            plugin_id,
            version,
        )
        if not result:
            raise HTTPException(status_code=404, detail="Plugin package not found")
        return result

    return router


__all__ = ["create_plugin_router"]
