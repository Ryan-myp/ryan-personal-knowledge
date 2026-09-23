"""Dependencies shared by HTTP route modules.

Route groups receive stable callbacks instead of importing the application
bootstrap module. This keeps registration reusable and lets tests replace the
Runtime without rebuilding the FastAPI app.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional

from agents.ad_agent.domain.ad.auth import RequestPrincipal


@dataclass(frozen=True)
class ApiContext:
    """Application services required by a route group."""

    runtime_getter: Callable[[], Any]
    authorize_request: Callable[
        [Optional[str], Any], RequestPrincipal
    ]
    activate_tenant_skills: Callable[[RequestPrincipal], None]
    sync_tenant_extensions: Callable[[RequestPrincipal], None]
    safe_exception_text: Callable[[Exception], str]
    redact: Callable[[Any], Any]

    def runtime(self) -> Any:
        return self.runtime_getter()


__all__ = ["ApiContext"]
