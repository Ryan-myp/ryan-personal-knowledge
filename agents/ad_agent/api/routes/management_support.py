"""Shared dependencies for management-plane route groups."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from agents.ad_agent.api.context import ApiContext
from agents.ad_agent.domain.ad.auth import RequestPrincipal
from agents.ad_agent.plugin_management import PluginPackageManager
from agents.ad_agent.skill_management import ManagedSkillManager


class ManagementRouteSupport:
    """Resolve management services through one application-owned context."""

    def __init__(self, context: ApiContext) -> None:
        self.context = context

    def store(self) -> Any:
        getter = self.context.persistence_store_getter
        value = getter() if getter else None
        if value is None:
            raise HTTPException(status_code=503, detail="管理存储未初始化")
        return value

    def plugin_manager(self) -> PluginPackageManager:
        return PluginPackageManager(self.store())

    def skill_manager(self) -> ManagedSkillManager:
        return ManagedSkillManager(self.store())

    def mcp_manager(self) -> Any:
        getter = self.context.mcp_manager_getter
        manager = getter() if getter else None
        if manager is None or self.context.runtime() is None:
            raise HTTPException(status_code=503, detail="MCP 管理服务未初始化")
        return manager

    def runtime_mcp_servers(self) -> Any:
        getter = self.context.runtime_mcp_servers_getter
        return getter() if getter else None

    def builtin_skill_catalog(self) -> Any:
        getter = self.context.builtin_skill_catalog_getter
        catalog = getter() if getter else None
        if catalog is None:
            raise HTTPException(status_code=503, detail="Builtin Skill 目录未初始化")
        return catalog

    @staticmethod
    def require_permission(
        principal: RequestPrincipal, permission: str, label: str,
    ) -> None:
        if permission not in principal.permissions and "admin" not in principal.permissions:
            raise HTTPException(
                status_code=403,
                detail=f"缺少 {label} 管理权限：{permission}",
            )


__all__ = ["ManagementRouteSupport"]
