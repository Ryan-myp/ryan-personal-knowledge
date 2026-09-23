"""MCP server and Tool management routes."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Request, Query
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from agents.ad_agent.api.context import ApiContext
from agents.ad_agent.api.models import (
    MCPServerPatchRequest,
    MCPServerRequest,
    MCPToolMetadataPatchRequest,
    MCPToolTestRequest,
    MCPValidationRequest,
)
from agents.ad_agent.domain.ad.auth import RequestPrincipal
from agents.ad_agent.mcp_management import MCPManagementError

from .management_support import ManagementRouteSupport


def create_mcp_router(context: ApiContext) -> APIRouter:
    router = APIRouter()
    support = ManagementRouteSupport(context)

    @router.get("/mcp/servers", tags=["mcp"])
    async def list_mcp_servers(
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
        limit: int = Query(50, ge=1, le=200),
    ):
        principal = context.authorize_request(x_api_key, http_request)
        support.require_permission(principal, "mcp.read", "MCP")
        runtime = context.runtime()
        channels = support.runtime_mcp_servers()
        channel_servers = (
            channels.list_servers(runtime, principal)
            if channels and runtime else []
        )
        external_servers = await run_in_threadpool(
            support.mcp_manager().list_servers,
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
        support.require_permission(principal, "mcp.manage", "MCP")
        try:
            result = await run_in_threadpool(
                support.mcp_manager().create_server,
                principal.tenant_id,
                body.model_dump(),
                principal.user_id,
            )
        except MCPManagementError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return JSONResponse(status_code=201, content=result)

    def runtime_mcp_server(server_id: str, principal: RequestPrincipal):
        runtime = context.runtime()
        channels = support.runtime_mcp_servers()
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
        support.require_permission(principal, "mcp.read", "MCP")
        channel_server = runtime_mcp_server(server_id, principal)
        if channel_server:
            return channel_server
        result = await run_in_threadpool(
            support.mcp_manager().get_server,
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
        support.require_permission(principal, "mcp.manage", "MCP")
        if runtime_mcp_server(server_id, principal):
            raise HTTPException(
                status_code=422,
                detail="Runtime MCP Server 由 Registry 管理，不能在此修改",
            )
        try:
            return await run_in_threadpool(
                support.mcp_manager().update_server,
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
        support.require_permission(principal, "mcp.manage", "MCP")
        if runtime_mcp_server(server_id, principal):
            raise HTTPException(
                status_code=422,
                detail="Runtime MCP Server 随 Registry 自动校验，无需单独校验",
            )
        try:
            return await run_in_threadpool(
                support.mcp_manager().validate_server,
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
        support.require_permission(principal, "mcp.manage", "MCP")
        if runtime_mcp_server(server_id, principal):
            raise HTTPException(
                status_code=422,
                detail="Runtime MCP Server 不能单独修改",
            )
        try:
            handler = (
                support.mcp_manager().enable_server
                if enabled else support.mcp_manager().disable_server
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
        support.require_permission(principal, "mcp.manage", "MCP")
        if runtime_mcp_server(server_id, principal):
            raise HTTPException(
                status_code=422,
                detail="Runtime MCP Server 由 Registry 管理，不能移除",
            )
        try:
            return await run_in_threadpool(
                support.mcp_manager().delete_server,
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
        support.require_permission(principal, "mcp.manage", "MCP")
        if runtime_mcp_server(server_id, principal):
            raise HTTPException(
                status_code=422,
                detail="Runtime MCP Server 的 Tool 随 Registry 自动启用，不能单独修改",
            )
        try:
            handler = (
                support.mcp_manager().enable_tool
                if enabled else support.mcp_manager().disable_tool
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
        support.require_permission(principal, "mcp.manage", "MCP")
        channels = support.runtime_mcp_servers()
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
                support.mcp_manager().test_tool,
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
        support.require_permission(principal, "mcp.manage", "MCP")
        if runtime_mcp_server(server_id, principal):
            raise HTTPException(
                status_code=422,
                detail="Runtime Registry Tool 不能在管理台修改，请修改其 Tool Source/Skill 发布定义",
            )
        try:
            return await run_in_threadpool(
                support.mcp_manager().update_tool_metadata,
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

    return router


__all__ = ["create_mcp_router"]
