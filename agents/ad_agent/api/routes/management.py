"""Plugin, MCP and Skill management routes."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from agents.ad_agent.api.context import ApiContext
from agents.ad_agent.api.models import (
    MCPServerPatchRequest,
    MCPServerRequest,
    MCPToolMetadataPatchRequest,
    MCPToolTestRequest,
    MCPValidationRequest,
    PluginPackageRequest,
    SkillVersionRequest,
)
from agents.ad_agent.core.plugin_package import PluginPackageError
from agents.ad_agent.mcp_management import MCPManagementError
from agents.ad_agent.plugin_management import PluginPackageManager
from agents.ad_agent.skill_management import ManagedSkillManager, SkillPackageError
from agents.ad_agent.domain.ad.auth import RequestPrincipal


def create_management_router(context: ApiContext) -> APIRouter:
    router = APIRouter()

    def store():
        value = (
            context.persistence_store_getter()
            if context.persistence_store_getter else None
        )
        if value is None:
            raise HTTPException(status_code=503, detail="管理存储未初始化")
        return value

    def plugin_manager() -> PluginPackageManager:
        return PluginPackageManager(store())

    def skill_manager() -> ManagedSkillManager:
        return ManagedSkillManager(store())

    def mcp_manager():
        manager = (
            context.mcp_manager_getter()
            if context.mcp_manager_getter else None
        )
        if manager is None or context.runtime() is None:
            raise HTTPException(status_code=503, detail="MCP 管理服务未初始化")
        return manager

    def runtime_mcp_servers():
        return (
            context.runtime_mcp_servers_getter()
            if context.runtime_mcp_servers_getter else None
        )

    def builtin_skill_catalog():
        catalog = (
            context.builtin_skill_catalog_getter()
            if context.builtin_skill_catalog_getter else None
        )
        if catalog is None:
            raise HTTPException(status_code=503, detail="Builtin Skill 目录未初始化")
        return catalog

    def require_permission(principal: RequestPrincipal, permission: str, label: str):
        if permission not in principal.permissions and "admin" not in principal.permissions:
            raise HTTPException(status_code=403, detail=f"缺少 {label} 管理权限：{permission}")

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
        require_permission(principal, "plugins.read", "Plugin")
        packages = await run_in_threadpool(
            plugin_manager().list_packages,
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
        require_permission(principal, "plugins.write", "Plugin")
        try:
            result = await run_in_threadpool(
                plugin_manager().create_package,
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
        require_permission(principal, "plugins.write", "Plugin")
        try:
            result = await run_in_threadpool(
                plugin_manager().create_archive,
                principal.tenant_id,
                await request.body(),
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
        require_permission(principal, "plugins.read", "Plugin")
        result = await run_in_threadpool(
            plugin_manager().get_package,
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
        require_permission(principal, "plugins.read", "Plugin")
        result = await run_in_threadpool(
            plugin_manager().health,
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
        require_permission(principal, "plugins.write", "Plugin")
        try:
            result = await run_in_threadpool(
                plugin_manager().activate,
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
        require_permission(principal, "plugins.write", "Plugin")
        result = await run_in_threadpool(
            plugin_manager().deactivate,
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
        require_permission(principal, "plugins.write", "Plugin")
        result = await run_in_threadpool(
            plugin_manager().uninstall,
            principal.tenant_id,
            plugin_id,
            version,
        )
        if not result:
            raise HTTPException(status_code=404, detail="Plugin package not found")
        return result

    @router.get("/mcp/servers", tags=["mcp"])
    async def list_mcp_servers(
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
        limit: int = Query(50, ge=1, le=200),
    ):
        principal = context.authorize_request(x_api_key, http_request)
        require_permission(principal, "mcp.read", "MCP")
        runtime = context.runtime()
        channels = runtime_mcp_servers()
        channel_servers = (
            channels.list_servers(runtime, principal)
            if channels and runtime else []
        )
        external_servers = await run_in_threadpool(
            mcp_manager().list_servers,
            principal.tenant_id,
            limit,
        )
        return {
            "tenant_id": principal.tenant_id,
            "servers": [*channel_servers, *external_servers],
        }

    @router.post("/mcp/servers", tags=["mcp"])
    async def create_mcp_server(
        body: MCPServerRequest,
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    ):
        principal = context.authorize_request(x_api_key, http_request)
        require_permission(principal, "mcp.manage", "MCP")
        try:
            result = await run_in_threadpool(
                mcp_manager().create_server,
                principal.tenant_id,
                body.model_dump(),
                principal.user_id,
            )
        except MCPManagementError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return JSONResponse(status_code=201, content=result)

    def runtime_mcp_server(server_id: str, principal: RequestPrincipal):
        runtime = context.runtime()
        channels = runtime_mcp_servers()
        if channels and runtime:
            return channels.get_server(server_id, runtime, principal)
        return None

    @router.get("/mcp/servers/{server_id}", tags=["mcp"])
    async def get_mcp_server(
        server_id: str,
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    ):
        principal = context.authorize_request(x_api_key, http_request)
        require_permission(principal, "mcp.read", "MCP")
        channel_server = runtime_mcp_server(server_id, principal)
        if channel_server:
            return channel_server
        result = await run_in_threadpool(
            mcp_manager().get_server,
            principal.tenant_id,
            server_id,
        )
        if not result:
            raise HTTPException(status_code=404, detail="MCP Server not found")
        return result

    @router.patch("/mcp/servers/{server_id}", tags=["mcp"])
    async def patch_mcp_server(
        server_id: str,
        body: MCPServerPatchRequest,
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    ):
        principal = context.authorize_request(x_api_key, http_request)
        require_permission(principal, "mcp.manage", "MCP")
        if runtime_mcp_server(server_id, principal):
            raise HTTPException(
                status_code=422,
                detail="Runtime MCP Server 由 Registry 管理，不能在此修改",
            )
        try:
            return await run_in_threadpool(
                mcp_manager().update_server,
                principal.tenant_id,
                server_id,
                body.model_dump(exclude_unset=True),
                context.runtime(),
            )
        except KeyError as error:
            raise HTTPException(
                status_code=404, detail="MCP Server not found"
            ) from error
        except MCPManagementError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @router.post("/mcp/servers/{server_id}/validate", tags=["mcp"])
    async def validate_mcp_server(
        server_id: str,
        body: MCPValidationRequest,
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    ):
        principal = context.authorize_request(x_api_key, http_request)
        require_permission(principal, "mcp.manage", "MCP")
        if runtime_mcp_server(server_id, principal):
            raise HTTPException(
                status_code=422,
                detail="Runtime MCP Server 随 Registry 自动校验，无需单独校验",
            )
        try:
            return await run_in_threadpool(
                mcp_manager().validate_server,
                principal.tenant_id,
                server_id,
                body.checks,
                context.runtime(),
            )
        except KeyError as error:
            raise HTTPException(
                status_code=404, detail="MCP Server not found"
            ) from error
        except MCPManagementError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    async def set_mcp_server_state(
        server_id: str,
        enabled: bool,
        http_request: Request,
        x_api_key: Optional[str],
    ):
        principal = context.authorize_request(x_api_key, http_request)
        require_permission(principal, "mcp.manage", "MCP")
        if runtime_mcp_server(server_id, principal):
            raise HTTPException(
                status_code=422,
                detail="Runtime MCP Server 不能单独修改",
            )
        try:
            handler = (
                mcp_manager().enable_server
                if enabled else mcp_manager().disable_server
            )
            return await run_in_threadpool(
                handler,
                principal.tenant_id,
                server_id,
                context.runtime(),
            )
        except KeyError as error:
            raise HTTPException(
                status_code=404, detail="MCP Server not found"
            ) from error
        except MCPManagementError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @router.post("/mcp/servers/{server_id}/enable", tags=["mcp"])
    async def enable_mcp_server(
        server_id: str,
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    ):
        return await set_mcp_server_state(
            server_id, True, http_request, x_api_key
        )

    @router.post("/mcp/servers/{server_id}/disable", tags=["mcp"])
    async def disable_mcp_server(
        server_id: str,
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    ):
        return await set_mcp_server_state(
            server_id, False, http_request, x_api_key
        )

    @router.delete("/mcp/servers/{server_id}", tags=["mcp"])
    async def delete_mcp_server(
        server_id: str,
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    ):
        principal = context.authorize_request(x_api_key, http_request)
        require_permission(principal, "mcp.manage", "MCP")
        if runtime_mcp_server(server_id, principal):
            raise HTTPException(
                status_code=422,
                detail="Runtime MCP Server 由 Registry 管理，不能移除",
            )
        try:
            return await run_in_threadpool(
                mcp_manager().delete_server,
                principal.tenant_id,
                server_id,
                context.runtime(),
            )
        except KeyError as error:
            raise HTTPException(
                status_code=404, detail="MCP Server not found"
            ) from error

    async def set_mcp_tool_state(
        server_id: str,
        tool_id: str,
        enabled: bool,
        http_request: Request,
        x_api_key: Optional[str],
    ):
        principal = context.authorize_request(x_api_key, http_request)
        require_permission(principal, "mcp.manage", "MCP")
        if runtime_mcp_server(server_id, principal):
            raise HTTPException(
                status_code=422,
                detail="Runtime MCP Server 的 Tool 随 Registry 自动启用，不能单独修改",
            )
        try:
            handler = (
                mcp_manager().enable_tool
                if enabled else mcp_manager().disable_tool
            )
            return await run_in_threadpool(
                handler,
                principal.tenant_id,
                server_id,
                tool_id,
                context.runtime(),
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail="MCP Tool not found") from error
        except MCPManagementError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @router.post(
        "/mcp/servers/{server_id}/tools/{tool_id}/enable",
        tags=["mcp"],
    )
    async def enable_mcp_tool(
        server_id: str,
        tool_id: str,
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    ):
        return await set_mcp_tool_state(
            server_id, tool_id, True, http_request, x_api_key
        )

    @router.post(
        "/mcp/servers/{server_id}/tools/{tool_id}/disable",
        tags=["mcp"],
    )
    async def disable_mcp_tool(
        server_id: str,
        tool_id: str,
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    ):
        return await set_mcp_tool_state(
            server_id, tool_id, False, http_request, x_api_key
        )

    @router.post(
        "/mcp/servers/{server_id}/tools/{tool_id}/test",
        tags=["mcp"],
    )
    async def test_mcp_tool(
        server_id: str,
        tool_id: str,
        body: MCPToolTestRequest,
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    ):
        principal = context.authorize_request(x_api_key, http_request)
        require_permission(principal, "mcp.manage", "MCP")
        channels = runtime_mcp_servers()
        try:
            if runtime_mcp_server(server_id, principal):
                return await run_in_threadpool(
                    channels.test_tool,
                    server_id,
                    tool_id,
                    context.runtime(),
                    principal,
                    body.input,
                    account_id=body.account_id,
                )
            return await run_in_threadpool(
                mcp_manager().test_tool,
                principal.tenant_id,
                server_id,
                tool_id,
                context.runtime(),
                principal,
                body.input,
                account_id=body.account_id,
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail="MCP Tool not found") from error
        except PermissionError as error:
            raise HTTPException(status_code=403, detail=str(error)) from error
        except MCPManagementError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @router.patch(
        "/mcp/servers/{server_id}/tools/{tool_id}",
        tags=["mcp"],
    )
    async def patch_mcp_tool_metadata(
        server_id: str,
        tool_id: str,
        body: MCPToolMetadataPatchRequest,
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    ):
        principal = context.authorize_request(x_api_key, http_request)
        require_permission(principal, "mcp.manage", "MCP")
        if runtime_mcp_server(server_id, principal):
            raise HTTPException(
                status_code=422,
                detail="Runtime Registry Tool 不能在管理台修改，请修改其 Tool Source/Skill 发布定义",
            )
        try:
            return await run_in_threadpool(
                mcp_manager().update_tool_metadata,
                principal.tenant_id,
                server_id,
                tool_id,
                body.model_dump(exclude_unset=True),
                context.runtime(),
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail="MCP Tool not found") from error
        except MCPManagementError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @router.get("/skills", tags=["skills"])
    async def list_managed_skills(
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
        skill_name: Optional[str] = Query(None, max_length=64),
        limit: int = Query(50, ge=1, le=200),
    ):
        principal = context.authorize_request(x_api_key, http_request)
        require_permission(principal, "skills.read", "Skill")
        managed = await run_in_threadpool(
            skill_manager().list_versions,
            principal.tenant_id,
            skill_name,
            limit,
        )
        builtin = await run_in_threadpool(
            builtin_skill_catalog().list_versions,
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
        require_permission(principal, "skills.write", "Skill")
        try:
            result = await run_in_threadpool(
                skill_manager().create_version,
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
        require_permission(principal, "skills.write", "Skill")
        try:
            result = await run_in_threadpool(
                skill_manager().create_version_archive,
                principal.tenant_id,
                skill_name,
                version,
                await request.body(),
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
        require_permission(principal, "skills.read", "Skill")
        versions = await run_in_threadpool(
            skill_manager().list_versions,
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
        require_permission(principal, "skills.read", "Skill")
        result = await run_in_threadpool(
            builtin_skill_catalog().get_version,
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
        require_permission(principal, "skills.read", "Skill")
        result = await run_in_threadpool(
            skill_manager().get_version,
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
        require_permission(principal, "skills.write", "Skill")
        handler = skill_manager().publish if publish else skill_manager().unpublish
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
        require_permission(principal, "skills.evaluate", "Skill")
        try:
            result = await run_in_threadpool(
                skill_manager().start_evaluation,
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
        require_permission(principal, "skills.read", "Skill")
        result = await run_in_threadpool(
            skill_manager().get_evaluation,
            principal.tenant_id,
            run_id,
        )
        if not result:
            raise HTTPException(status_code=404, detail="Skill evaluation not found")
        return result

    return router


__all__ = ["create_management_router"]
