"""Authenticated model and provider-credential management routes."""

from __future__ import annotations

import ipaddress
from typing import Literal, Optional

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field

from agents.deployments.advertising.api.context import ApiContext
from agents.deployments.advertising.settings import SettingsVaultError


class ModelProfileRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    model: str = Field(min_length=1, max_length=160)
    base_url: str = Field(default="", max_length=2048)
    api_key: str = Field(default="", max_length=8192)
    purpose: Literal["chat", "image_generation", "video_generation"] = "chat"


class ProviderCredentialsRequest(BaseModel):
    fields: dict[str, str] = Field(default_factory=dict, max_length=20)
    clear_fields: list[str] = Field(default_factory=list, max_length=20)


class WebSearchCredentialsRequest(BaseModel):
    provider: str | None = Field(default=None, max_length=40)
    api_key: str = Field(default="", max_length=8192)
    clear: bool = False


def _require_secure_secret_transport(request: Request) -> None:
    if request.url.scheme == "https":
        return
    client = request.client
    host = str(client.host if client else "").strip().lower()
    if host == "localhost":
        return
    try:
        if ipaddress.ip_address(host).is_loopback:
            return
    except ValueError:
        pass
    raise HTTPException(
        status_code=400,
        detail="密钥只能通过 HTTPS 或本机回环连接写入",
    )


def create_settings_router(context: ApiContext) -> APIRouter:
    router = APIRouter()

    def authorize(http_request: Request, api_key: Optional[str]):
        principal = context.authorize_request(api_key, http_request)
        context.require_permission(principal, "settings.manage")
        return principal

    def service():
        result = context.settings_service()
        if result is None:
            raise HTTPException(status_code=503, detail="设置服务未初始化")
        return result

    def invoke(operation):
        try:
            return operation()
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except SettingsVaultError as error:
            raise HTTPException(
                status_code=503,
                detail="加密设置存储不可用，请检查部署密钥配置",
            ) from error
        except RuntimeError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error

    @router.get("/settings", tags=["settings"])
    async def get_settings(
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    ):
        authorize(http_request, x_api_key)
        return service().snapshot()

    @router.post("/settings/models", tags=["settings"])
    async def create_model_profile(
        body: ModelProfileRequest,
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    ):
        authorize(http_request, x_api_key)
        _require_secure_secret_transport(http_request)
        profile_id = invoke(lambda: service().save_model_profile(**body.model_dump()))
        return {"profile_id": profile_id, "settings": service().snapshot()}

    @router.put("/settings/models/{profile_id}", tags=["settings"])
    async def update_model_profile(
        profile_id: str,
        body: ModelProfileRequest,
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    ):
        authorize(http_request, x_api_key)
        _require_secure_secret_transport(http_request)
        result = invoke(
            lambda: service().save_model_profile(
                profile_id=profile_id,
                **body.model_dump(),
            )
        )
        return {"profile_id": result, "settings": service().snapshot()}

    @router.post("/settings/models/{profile_id}/activate", tags=["settings"])
    async def activate_model_profile(
        profile_id: str,
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    ):
        authorize(http_request, x_api_key)
        invoke(lambda: service().activate_model_profile(profile_id))
        return service().snapshot()

    @router.delete("/settings/models/{profile_id}", tags=["settings"])
    async def delete_model_profile(
        profile_id: str,
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    ):
        authorize(http_request, x_api_key)
        invoke(lambda: service().delete_model_profile(profile_id))
        return service().snapshot()

    @router.put("/settings/providers/{provider}", tags=["settings"])
    async def update_provider_credentials(
        provider: str,
        body: ProviderCredentialsRequest,
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    ):
        authorize(http_request, x_api_key)
        _require_secure_secret_transport(http_request)
        return invoke(
            lambda: service().update_provider_credentials(
                provider,
                body.fields,
                clear_fields=body.clear_fields,
            )
        )

    @router.put("/settings/web-search", tags=["settings"])
    async def update_web_search_credentials(
        body: WebSearchCredentialsRequest,
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    ):
        authorize(http_request, x_api_key)
        if body.api_key or body.clear:
            _require_secure_secret_transport(http_request)
        return invoke(
            lambda: service().update_web_search_credentials(
                provider=body.provider,
                api_key=body.api_key,
                clear=body.clear,
            )
        )

    return router


__all__ = [
    "ModelProfileRequest",
    "ProviderCredentialsRequest",
    "WebSearchCredentialsRequest",
    "_require_secure_secret_transport",
    "create_settings_router",
]
