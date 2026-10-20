"""Identity-scoped access to generated creative media."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Request
from starlette.concurrency import run_in_threadpool
from starlette.responses import FileResponse

from agents.deployments.advertising.api.context import ApiContext


def create_creative_router(context: ApiContext) -> APIRouter:
    router = APIRouter()

    @router.get("/creative/assets/{asset_id}", tags=["creative"])
    async def get_creative_asset(
        asset_id: str,
        http_request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    ):
        principal = context.authorize_request(x_api_key, http_request)
        context.require_permission(principal, "ads.read")
        store = context.creative_asset_store()
        if store is None:
            raise HTTPException(status_code=503, detail="创意素材存储未初始化")
        try:
            asset = await run_in_threadpool(
                store.get,
                asset_id,
                tenant_id=principal.tenant_id,
                user_id=principal.user_id,
                include_content=False,
            )
        except FileNotFoundError as error:
            raise HTTPException(
                status_code=404,
                detail="创意素材不存在或无权访问",
            ) from error
        except (OSError, RuntimeError) as error:
            raise HTTPException(status_code=503, detail="创意素材暂时无法读取") from error
        if asset.content is not None or asset.path is None:
            raise HTTPException(status_code=409, detail="创意素材尚未生成完成")
        return FileResponse(
            asset.path,
            media_type=asset.metadata["media_type"],
            content_disposition_type="inline",
            headers={
                "Cache-Control": "private, no-store",
                "X-Content-Type-Options": "nosniff",
            },
        )

    return router


__all__ = ["create_creative_router"]
