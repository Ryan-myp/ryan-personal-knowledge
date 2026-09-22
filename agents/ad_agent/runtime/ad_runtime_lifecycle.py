"""Plugin and managed-Skill lifecycle service for the advertising app."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from ..core.plugins import manifest_for_builtin, manifest_for_managed_skill
from .skill import BaseSkill, Skill, SkillContract


class AdvertisingLifecycleService:
    """Own executable plugin metadata and tenant-scoped advisory Skills."""

    def __init__(self, runtime: Any) -> None:
        self.runtime = runtime

    def register_builtin_plugin(
        self,
        plugin_id: str,
        contribution: Any,
        kinds: tuple[str, ...] | list[str],
        *,
        version: str = "1.0.0",
        description: str = "",
        replace: bool = False,
    ) -> None:
        runtime = self.runtime
        manifest = manifest_for_builtin(
            plugin_id,
            version,
            kinds=tuple(kinds),
            description=description,
        )
        runtime.plugin_loader.install(
            manifest,
            contribution=contribution,
            replace=replace,
        )
        runtime.plugin_registry.activate(manifest.plugin_id)

    def list_plugins(self, tenant_id: Optional[str] = None) -> list[dict[str, Any]]:
        runtime = self.runtime
        snapshots = runtime.plugin_registry.snapshot()
        if tenant_id is None:
            return snapshots
        tenant = str(tenant_id or "default").strip().lower()
        return [
            item
            for item in snapshots
            if item.get("manifest", {}).get("source") != "managed"
            or item.get("manifest", {})
            .get("metadata", {})
            .get("tenant_id") == tenant
        ]

    def load_managed_skill(
        self,
        skill_dir: str,
        tenant_id: str = "default",
    ) -> bool:
        runtime = self.runtime
        tenant_id = str(tenant_id or "default")
        directory = Path(skill_dir).resolve()
        if not directory.is_dir() or not (directory / "SKILL.md").is_file():
            raise ValueError("managed Skill directory must contain SKILL.md")
        contract = SkillContract(str(directory)).load()
        if contract.context_only or not contract.name:
            raise ValueError("managed Skill must be a standalone Skill with a name")
        skill = BaseSkill(contract)
        setattr(skill, "skill_dir", str(directory))

        with runtime._managed_skill_lock:
            if contract.name in runtime._skill_objects:
                raise ValueError(
                    "managed Skill name conflicts with executable Skill: "
                    f"{contract.name}"
                )
            runtime._managed_context_skills.setdefault(
                tenant_id, {}
            )[contract.name] = skill
            managed_manifest = manifest_for_managed_skill(
                tenant_id,
                contract.name,
                contract.version,
                description=contract.description,
            )
            runtime.plugin_loader.install(
                managed_manifest,
                contribution=skill,
                replace=True,
            )
            runtime.plugin_registry.activate(managed_manifest.plugin_id)
            if hasattr(runtime.tool_selector, "register_context_skill"):
                runtime.tool_selector.register_context_skill(
                    skill,
                    tenant_id=tenant_id,
                )
            runtime._refresh_parser_catalog()
        return True

    def unload_managed_skill(
        self,
        skill_name: str,
        tenant_id: str = "default",
    ) -> bool:
        runtime = self.runtime
        key = str(skill_name or "")
        tenant_id = str(tenant_id or "default")
        with runtime._managed_skill_lock:
            tenant_skills = runtime._managed_context_skills.get(tenant_id)
            skill = tenant_skills.pop(key, None) if tenant_skills else None
            if skill is None:
                return False
            if hasattr(runtime.tool_selector, "unregister_context_skill"):
                runtime.tool_selector.unregister_context_skill(
                    key,
                    tenant_id=tenant_id,
                )
            runtime.plugin_registry.unregister(
                manifest_for_managed_skill(
                    tenant_id,
                    key,
                    "1.0.0",
                ).plugin_id
            )
            if not tenant_skills:
                runtime._managed_context_skills.pop(tenant_id, None)
            runtime._refresh_parser_catalog()
            return True

    def get_managed_skills(
        self,
        tenant_id: Optional[str] = None,
    ) -> dict[str, Skill]:
        runtime = self.runtime
        with runtime._managed_skill_lock:
            if tenant_id is not None:
                return dict(
                    runtime._managed_context_skills.get(
                        str(tenant_id or "default"),
                        {},
                    )
                )
            if len(runtime._managed_context_skills) == 1:
                return dict(next(iter(runtime._managed_context_skills.values())))
            if "default" in runtime._managed_context_skills:
                return dict(runtime._managed_context_skills["default"])
            return {}


__all__ = ["AdvertisingLifecycleService"]
