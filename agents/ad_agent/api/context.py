"""Dependencies shared by HTTP route modules.

Route groups receive stable callbacks instead of importing the application
bootstrap module. This keeps registration reusable and lets tests replace the
Runtime without rebuilding the FastAPI app.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional

from fastapi import HTTPException

from agents.ad_agent.domain.ad.auth import RequestPrincipal


async def read_request_body_limited(request: Any, *, max_bytes: int) -> bytes:
    """Read an ASGI request body without buffering beyond the declared limit."""
    limit = int(max_bytes)
    if limit <= 0:
        raise ValueError("max_bytes must be positive")
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > limit:
                raise HTTPException(
                    status_code=413,
                    detail="request body exceeds the allowed size",
                )
        except ValueError:
            # The ASGI server may still enforce framing. Continue with the
            # streaming counter so malformed or chunked requests stay bounded.
            pass

    chunks: list[bytes] = []
    total = 0
    async for chunk in request.stream():
        if not chunk:
            continue
        total += len(chunk)
        if total > limit:
            raise HTTPException(
                status_code=413,
                detail="request body exceeds the allowed size",
            )
        chunks.append(bytes(chunk))
    return b"".join(chunks)


@dataclass(frozen=True)
class ApiContext:
    """Application services required by a route group."""

    runtime_getter: Callable[[], Any]
    authorize_request: Callable[
        [Optional[str], Any], RequestPrincipal
    ]
    require_permission: Callable[[RequestPrincipal, str], None]
    activate_tenant_skills: Callable[[RequestPrincipal], None]
    sync_tenant_extensions: Callable[[RequestPrincipal], None]
    safe_exception_text: Callable[[Exception], str]
    redact: Callable[[Any], Any]
    persistence_store_getter: Callable[[], Any] | None = None
    mcp_manager_getter: Callable[[], Any] | None = None
    runtime_mcp_servers_getter: Callable[[], Any] | None = None
    builtin_skill_catalog_getter: Callable[[], Any] | None = None

    def runtime(self) -> Any:
        return self.runtime_getter()


__all__ = ["ApiContext", "read_request_body_limited"]
