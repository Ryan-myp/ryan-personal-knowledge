"""Read-only catalogs and creation-template routes."""

from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from agents.ad_agent.api.context import ApiContext
from agents.ad_agent.api.models import (
    BlueprintEvaluationRequest,
    BlueprintResolveRequest,
    CreationTemplateDuplicateRequest,
    CreationTemplateRequest,
    CreationTemplateUpdateRequest,
)
from agents.ad_agent.creation_templates import (
    CreationTemplateError,
    CreationTemplateManager,
    creation_template_manager_for_runtime,
)
from agents.ad_agent.domain.ad.auth import RequestPrincipal


def create_catalog_router(context: ApiContext) -> APIRouter:
    router = APIRouter()

    def runtime_or_503():
        runtime = context.runtime()
        if runtime is None:
            raise HTTPException(status_code=503, detail="服务未初始化")
        return runtime

    def creation_template_manager(
        principal: Optional[RequestPrincipal] = None,
    ) -> CreationTemplateManager:
        runtime = runtime_or_503()
        store = (
            context.persistence_store_getter()
            if context.persistence_store_getter else None
        )
        if store is None:
            raise HTTPException(status_code=503, detail="创建模板存储未初始化")
        try:
            validator = getattr(runtime, "whitelist_validator", None)
            configured_accounts = (
                getattr(validator, "allowed_accounts", {})
                if validator else {}
            )
            principal_scope = (
                getattr(principal, "account_scope", None) if principal else None
            )
            if not any(configured_accounts.values()):
                principal_scope = None
            return creation_template_manager_for_runtime(
                runtime,
                account_scope=principal_scope,
            )
        except CreationTemplateError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error

    @router.get("/creation-templates", tags=["creation-templates"])
    async def list_creation_templates(
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
        provider: Optional[str] = Query(None, max_length=64),
        blueprint_id: Optional[str] = Query(None, max_length=200),
        status: Optional[str] = Query(None, max_length=16),
        query: Optional[str] = Query(None, max_length=120),
        limit: int = Query(100, ge=1, le=200),
    ):
        principal = context.authorize_request(x_api_key, http_request)
        context.require_permission(principal, "ads.read")
        if status and status not in {"active", "inactive", "archived"}:
            raise HTTPException(status_code=422, detail="模板状态不合法")
        manager = creation_template_manager(principal)
        templates = await run_in_threadpool(
            manager.list,
            principal.tenant_id,
            principal.user_id,
            provider=provider,
            blueprint_id=blueprint_id,
            status=status,
            query=query,
            limit=limit,
        )
        return {
            "tenant_id": principal.tenant_id,
            "user_id": principal.user_id,
            "templates": templates,
        }

    @router.post("/creation-templates", tags=["creation-templates"])
    async def create_creation_template(
        body: CreationTemplateRequest,
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    ):
        principal = context.authorize_request(x_api_key, http_request)
        context.require_permission(principal, "ads.plan")
        try:
            result = await run_in_threadpool(
                creation_template_manager(principal).create,
                principal.tenant_id,
                principal.user_id,
                body.model_dump(),
            )
        except CreationTemplateError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return JSONResponse(status_code=201, content=result)

    @router.get("/creation-templates/{template_id}", tags=["creation-templates"])
    async def get_creation_template(
        template_id: str,
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    ):
        principal = context.authorize_request(x_api_key, http_request)
        context.require_permission(principal, "ads.read")
        result = await run_in_threadpool(
            creation_template_manager(principal).get,
            principal.tenant_id,
            principal.user_id,
            template_id,
        )
        if not result:
            raise HTTPException(status_code=404, detail="创建模板不存在或无权访问")
        return result

    @router.patch("/creation-templates/{template_id}", tags=["creation-templates"])
    async def update_creation_template(
        template_id: str,
        body: CreationTemplateUpdateRequest,
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    ):
        principal = context.authorize_request(x_api_key, http_request)
        context.require_permission(principal, "ads.plan")
        try:
            result = await run_in_threadpool(
                creation_template_manager(principal).update,
                principal.tenant_id,
                principal.user_id,
                template_id,
                body.model_dump(exclude_unset=True),
            )
        except CreationTemplateError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        if not result:
            raise HTTPException(status_code=404, detail="创建模板不存在或无权访问")
        return result

    @router.delete("/creation-templates/{template_id}", tags=["creation-templates"])
    async def delete_creation_template(
        template_id: str,
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    ):
        principal = context.authorize_request(x_api_key, http_request)
        context.require_permission(principal, "ads.plan")
        result = await run_in_threadpool(
            creation_template_manager(principal).delete,
            principal.tenant_id,
            principal.user_id,
            template_id,
        )
        if not result:
            raise HTTPException(status_code=404, detail="创建模板不存在或无权访问")
        return result

    @router.post(
        "/creation-templates/{template_id}/duplicate",
        tags=["creation-templates"],
    )
    async def duplicate_creation_template(
        template_id: str,
        body: CreationTemplateDuplicateRequest,
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    ):
        principal = context.authorize_request(x_api_key, http_request)
        context.require_permission(principal, "ads.plan")
        try:
            result = await run_in_threadpool(
                creation_template_manager(principal).duplicate,
                principal.tenant_id,
                principal.user_id,
                template_id,
                body.name,
            )
        except CreationTemplateError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        if not result:
            raise HTTPException(status_code=404, detail="创建模板不存在或无权访问")
        return JSONResponse(status_code=201, content=result)

    @router.post(
        "/creation-templates/{template_id}/apply",
        tags=["creation-templates"],
    )
    async def apply_creation_template(
        template_id: str,
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    ):
        principal = context.authorize_request(x_api_key, http_request)
        context.require_permission(principal, "ads.plan")
        result = await run_in_threadpool(
            creation_template_manager(principal).apply,
            principal.tenant_id,
            principal.user_id,
            template_id,
        )
        if not result:
            raise HTTPException(
                status_code=404,
                detail="模板不存在、已停用或无权访问",
            )
        return result

    @router.get("/platforms", tags=["info"])
    async def get_platforms(
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    ):
        context.authorize_request(x_api_key, http_request)
        runtime = context.runtime()
        if not runtime:
            return {"platforms": []}
        return {"platforms": runtime.registry.list_all_namespaces()}

    @router.get("/tools", tags=["info"])
    async def get_tools(
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    ):
        context.authorize_request(x_api_key, http_request)
        runtime = context.runtime()
        if not runtime:
            return {"tools": []}
        tools = runtime.registry.list_all()
        return {
            "tools": [
                {
                    "name": tool.name,
                    "platform": tool.namespace,
                    "skill": tool.skill,
                    "description": tool.description,
                    "action": tool.action,
                    "resource_type": tool.resource_type,
                    "parent_resource_type": tool.parent_resource_type,
                    "intent_types": list(tool.intent_types),
                    "risk_level": tool.risk_level.value,
                    "effect_class": tool.effect_class.value,
                    "replay_policy": tool.replay_policy.value,
                    "traits": list(tool.traits),
                    "live_support": tool.live_support,
                    "cancellation_mode": tool.cancellation_mode,
                    "timeout_seconds": tool.timeout_seconds,
                    "max_output_bytes": tool.max_output_bytes,
                    "required_permissions": list(tool.required_permissions),
                    "contract_version": tool.contract_version,
                    "integration_api_version": tool.integration_api_version,
                    "input_schema": (
                        tool.input_schema.to_dict()
                        if tool.input_schema else None
                    ),
                }
                for tool in tools
            ],
        }

    @router.get("/ad-formats", tags=["info"])
    async def get_ad_formats(
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
        platform: Optional[str] = Query(None, max_length=50),
        coverage: Optional[str] = Query(None, max_length=40),
    ):
        context.authorize_request(x_api_key, http_request)
        runtime = context.runtime()
        if not runtime:
            return {"formats": []}
        try:
            return {
                "platform": platform,
                "coverage": coverage,
                "formats": runtime.list_ad_formats(platform, coverage),
            }
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @router.get("/creation-blueprints", tags=["info"])
    async def get_creation_blueprints(
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
        provider: Optional[str] = Query(None, max_length=50),
        ad_format: Optional[str] = Query(None, max_length=80),
        selector_dimension: Optional[str] = Query(None, max_length=40),
        selector_value: Optional[str] = Query(None, max_length=120),
    ):
        context.authorize_request(x_api_key, http_request)
        runtime = context.runtime()
        if not runtime:
            return {"blueprints": []}
        return {
            "provider": provider,
            "ad_format": ad_format,
            "selector_dimension": selector_dimension,
            "selector_value": selector_value,
            "formats": (
                runtime.list_ad_formats(provider)
                if provider else runtime.list_ad_formats()
            ),
            "blueprints": runtime.list_creation_blueprints(
                provider, ad_format, selector_dimension, selector_value
            ),
        }

    @router.get("/creation-catalog", tags=["info"])
    async def get_creation_catalog(
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
        provider: Optional[str] = Query(None, max_length=50),
        ad_format: Optional[str] = Query(None, max_length=80),
        account_id: Optional[str] = Query(None, max_length=200),
        selector_dimension: Optional[str] = Query(None, max_length=40),
        selector_value: Optional[str] = Query(None, max_length=120),
    ):
        principal = context.authorize_request(x_api_key, http_request)
        context.require_permission(principal, "ads.read")
        runtime = runtime_or_503()
        validator = getattr(runtime, "whitelist_validator", None)
        configured_accounts = (
            getattr(validator, "allowed_accounts", {}) if validator else {}
        )
        account_scope = getattr(principal, "account_scope", None)
        if not any(configured_accounts.values()):
            account_scope = None
        return runtime.list_creation_catalog(
            provider,
            ad_format=ad_format,
            selector_dimension=selector_dimension,
            selector_value=selector_value,
            account_id=account_id,
            account_scope=account_scope,
            tenant_id=principal.tenant_id,
            user_id=principal.user_id,
        )

    @router.post("/creation-blueprints/resolve", tags=["info"])
    async def resolve_creation_blueprint(
        body: BlueprintResolveRequest,
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    ):
        context.authorize_request(x_api_key, http_request)
        runtime = runtime_or_503()
        blueprint = runtime.resolve_creation_blueprint(
            body.provider,
            selector_values=body.selector_values,
            values=body.values,
            version=body.version,
        )
        if blueprint is None:
            raise HTTPException(
                status_code=404,
                detail="未找到匹配当前选择的广告创建蓝图",
            )
        return {"blueprint": blueprint}

    @router.post(
        "/creation-blueprints/{blueprint_id}/evaluate",
        tags=["info"],
    )
    async def evaluate_creation_blueprint(
        blueprint_id: str,
        body: BlueprintEvaluationRequest,
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    ):
        context.authorize_request(x_api_key, http_request)
        runtime = runtime_or_503()
        try:
            return runtime.evaluate_creation_blueprint(
                blueprint_id,
                body.values,
                version=body.version,
                previous_values=body.previous_values,
                changed_fields=body.changed_fields,
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @router.get("/parameter-options", tags=["info"])
    async def get_parameter_options(
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
        platform: Optional[str] = Query(None, max_length=50),
        field: Optional[str] = Query(None, max_length=100),
        tool_name: Optional[str] = Query(None, max_length=150),
    ):
        context.authorize_request(x_api_key, http_request)
        runtime = context.runtime()
        if not runtime:
            return {"options": []}
        return {
            "platform": platform,
            "field": field,
            "tool_name": tool_name,
            "options": runtime.list_parameter_options(
                platform, field, tool_name
            ),
        }

    @router.get("/parameter-options/resolve", tags=["info"])
    async def resolve_parameter_options(
        http_request: Request,
        platform: str = Query(..., min_length=1, max_length=50),
        field: str = Query(..., min_length=1, max_length=100),
        tool_name: str = Query(..., min_length=1, max_length=150),
        account_id: Optional[str] = Query(None, max_length=200),
        lookup_context: Optional[str] = Query(None, max_length=8000),
        query: Optional[str] = Query(None, max_length=200),
        session_id: Optional[str] = Query(None, max_length=200),
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    ):
        principal = context.authorize_request(x_api_key, http_request)
        runtime = runtime_or_503()
        try:
            resolved_context = {}
            if lookup_context:
                try:
                    decoded = json.loads(lookup_context)
                except (TypeError, ValueError) as error:
                    raise HTTPException(
                        status_code=422,
                        detail="查询上下文不是有效的 JSON",
                    ) from error
                if not isinstance(decoded, dict):
                    raise HTTPException(
                        status_code=422,
                        detail="查询上下文必须是对象",
                    )
                resolved_context = decoded
            return await run_in_threadpool(
                runtime.resolve_parameter_options,
                platform=platform,
                field=field,
                tool_name=tool_name,
                account_id=account_id,
                lookup_context=resolved_context,
                query=query,
                session_id=session_id,
                user_id=principal.user_id,
                tenant_id=principal.tenant_id,
                account_scope=principal.account_scope,
                granted_permissions=principal.permissions,
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except PermissionError as error:
            raise HTTPException(status_code=403, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except RuntimeError as error:
            raise HTTPException(
                status_code=502,
                detail=context.safe_exception_text(error),
            ) from error

    return router


__all__ = ["create_catalog_router"]
