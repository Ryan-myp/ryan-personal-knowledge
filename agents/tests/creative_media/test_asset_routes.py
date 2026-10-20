from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from agents.agent_platform.governance.identity.principal import RequestPrincipal
from agents.deployments.advertising.api.context import ApiContext
from agents.deployments.advertising.api.routes.creative import (
    create_creative_router,
)
from agents.agent_platform.infrastructure.durable.filesystem_asset_store import (
    FilesystemCreativeAssetStore,
)


PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR"
    b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00"
)


def test_creative_asset_read_is_scoped_to_authenticated_principal(tmp_path):
    principal = RequestPrincipal(
        user_id="asset-user",
        tenant_id="asset-tenant",
        permissions=frozenset({"ads.read"}),
    )
    store = FilesystemCreativeAssetStore(tmp_path)
    saved = store.put(
        PNG_BYTES,
        filename="generated.png",
        media_type="image/png",
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        metadata={"kind": "image", "status": "ready"},
    )

    context = ApiContext(
        runtime_getter=lambda: None,
        authorize_request=lambda *_args: principal,
        require_permission=lambda current, permission: (
            None if permission in current.permissions else (_ for _ in ()).throw(
                PermissionError("permission denied")
            )
        ),
        activate_tenant_skills=lambda _principal: None,
        sync_tenant_extensions=lambda _principal: None,
        safe_exception_text=lambda error: str(error),
        redact=lambda value: value,
        creative_asset_store_getter=lambda: store,
    )
    app = FastAPI()
    app.include_router(create_creative_router(context))

    with TestClient(app) as client:
        response = client.get(f"/creative/assets/{saved['asset_id']}")

    assert response.status_code == 200
    assert response.content == PNG_BYTES
    assert response.headers["content-type"] == "image/png"
    assert response.headers["x-content-type-options"] == "nosniff"


def test_creative_asset_route_returns_not_found_for_other_identity(tmp_path):
    store = FilesystemCreativeAssetStore(tmp_path)
    saved = store.put(
        PNG_BYTES,
        filename="private.png",
        media_type="image/png",
        tenant_id="tenant-a",
        user_id="user-a",
        metadata={"kind": "image", "status": "ready"},
    )
    principal = RequestPrincipal(
        user_id="user-b",
        tenant_id="tenant-b",
        permissions=frozenset({"ads.read"}),
    )
    context = ApiContext(
        runtime_getter=lambda: None,
        authorize_request=lambda *_args: principal,
        require_permission=lambda *_args: None,
        activate_tenant_skills=lambda _principal: None,
        sync_tenant_extensions=lambda _principal: None,
        safe_exception_text=lambda error: str(error),
        redact=lambda value: value,
        creative_asset_store_getter=lambda: store,
    )
    app = FastAPI()
    app.include_router(create_creative_router(context))

    with TestClient(app) as client:
        response = client.get(f"/creative/assets/{saved['asset_id']}")

    assert response.status_code == 404
