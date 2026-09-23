"""Composition root for management-plane HTTP routes."""

from __future__ import annotations

from fastapi import APIRouter

from agents.ad_agent.api.context import ApiContext

from .mcp import create_mcp_router
from .plugins import create_plugin_router
from .skills import create_skill_router


def create_management_router(context: ApiContext) -> APIRouter:
    """Compose Plugin, MCP and Skill routes under the shared API surface."""
    router = APIRouter()
    router.include_router(create_plugin_router(context))
    router.include_router(create_mcp_router(context))
    router.include_router(create_skill_router(context))
    return router


__all__ = ["create_management_router"]
