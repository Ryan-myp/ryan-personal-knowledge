"""Atomic Tool Source registration for the advertising application."""

from __future__ import annotations

import copy
import logging
from functools import wraps
from typing import Any

from ..core.interfaces import ToolSourceModule, ToolSourceRuntime
from ..core.plugins import PluginKind
from ..domain.ad.contracts import AdFormatCoverage
from .skill import Skill
from .tool_source_context import ToolSourceContextWrapper

logger = logging.getLogger(__name__)


def serialize_skill_lifecycle(method):
    """Serialize registry and ownership-index mutations in one Runtime."""
    @wraps(method)
    def wrapped(self, *args, **kwargs):
        lock = getattr(self, "_skill_lifecycle_lock", None)
        if lock is None:
            return method(self, *args, **kwargs)
        with lock:
            return method(self, *args, **kwargs)
    return wrapped


class AdToolSourceRegistrationMixin:
    @serialize_skill_lifecycle
    def register_provider_tool_source(
        self, module: ToolSourceModule
    ) -> ToolSourceRuntime:
        """Register a Tool Source atomically and roll back derived indexes."""
        before_tool_names = {
            definition.name for definition in self.registry.list_all()
        }
        before_formats = copy.deepcopy(self.ad_format_catalogs)
        before_provider_versions = copy.deepcopy(self.provider_version_contracts)
        before_provider_surfaces = copy.deepcopy(self.provider_api_surfaces)
        before_blueprints = self.creation_blueprints.snapshot()
        try:
            runtime = self._register_provider_tool_source_unchecked(module)
            platform = self._canonical_platform(getattr(module, "platform_name", ""))
            if platform:
                self._register_builtin_plugin(
                    f"provider-tools:{platform}",
                    module,
                    (PluginKind.TOOL_SOURCE.value,),
                    version=str(
                        getattr(module, "tool_source_version", "1.0.0") or "1.0.0"
                    ),
                    description=f"Provider tool_source {platform}",
                )
            return runtime
        except Exception:
            current_tool_names = {
                definition.name for definition in self.registry.list_all()
            }
            added_tool_names = current_tool_names - before_tool_names
            for name in added_tool_names:
                self.registry.unregister(name)
            self.parameter_catalogs.remove_tools(list(added_tool_names))
            for skill_key, tool_names in list(self._skill_tool_names.items()):
                if not (set(tool_names) & added_tool_names):
                    continue
                platform = self._skill_namespaces.pop(skill_key, None)
                self._skill_tool_names.pop(skill_key, None)
                self._skill_objects.pop(skill_key, None)
                self._skill_format_ids.pop(skill_key, None)
                if platform:
                    canonical = self._canonical_platform(platform)
                    keys = [
                        key for key in self._skill_keys_by_platform.get(canonical, [])
                        if key != skill_key
                    ]
                    if keys:
                        self._skill_keys_by_platform[canonical] = keys
                    else:
                        self._skill_keys_by_platform.pop(canonical, None)
            self.ad_format_catalogs = before_formats
            self.provider_version_contracts = before_provider_versions
            self.provider_api_surfaces = before_provider_surfaces
            self.creation_blueprints.restore(before_blueprints)
            platform = self._canonical_platform(getattr(module, "platform_name", ""))
            if platform:
                self.plugin_registry.unregister(f"provider-tools:{platform}")
            try:
                self._refresh_parser_catalog()
            except Exception:
                logger.exception("Tool Source rollback could not refresh parser catalog")
            raise

    def _register_provider_tool_source_unchecked(
        self, module: ToolSourceModule
    ) -> ToolSourceRuntime:
        before_tool_names = {
            definition.name for definition in self.registry.list_all()
        }
        context = ToolSourceContextWrapper(self.registry)
        runtime = module.configure(context)
        for definition in self.registry.list_all():
            self.parameter_catalogs.register_tool_schema(
                definition.namespace,
                getattr(definition.input_schema, "properties", {})
                if definition.input_schema else {},
                tool_name=definition.name,
            )
        self.parameter_catalogs.register_many(
            getattr(runtime, "parameter_catalogs", []) or []
        )
        platform = self._canonical_platform(getattr(module, "platform_name", ""))
        blueprints = getattr(runtime, "creation_blueprints", []) or []
        if blueprints:
            self.creation_blueprints.register_many(
                blueprints, owner=platform or None, tool_registry=self.registry
            )
        self._register_ad_format_catalog(
            getattr(module, "platform_name", "") or "",
            getattr(runtime, "ad_format_catalogs", []) or [],
        )
        provider_contract_getter = getattr(module, "get_provider_version_contract", None)
        if callable(provider_contract_getter) and platform:
            self.provider_version_contracts[platform] = copy.deepcopy(
                provider_contract_getter()
            )
        provider_surface_getter = getattr(module, "get_api_surface", None)
        if callable(provider_surface_getter) and platform:
            self.provider_api_surfaces[platform] = copy.deepcopy(
                provider_surface_getter()
            )
        self._validate_parameter_lookup_contract()
        if self._read_only_mode:
            self._filter_write_tools()
        register_tools = getattr(self.intent_parser, "register_tool_definitions", None)
        if callable(register_tools):
            register_tools(self.registry.list_all())
        if getattr(module, "platform_name", None):
            canonical_namespace = self._canonical_platform(module.platform_name)
            skill_candidates = self.skill_loader.get_by_namespace(canonical_namespace)
            primary_skill = skill_candidates[0] if skill_candidates else None
            skill_key = (
                str(getattr(primary_skill, "name", "") or canonical_namespace)
                if primary_skill is not None
                else f"{canonical_namespace}:provider-tools:{id(module)}"
            )
            registered_names = sorted(
                definition.name
                for definition in self.registry.list_all()
                if definition.name not in before_tool_names
            )
            if registered_names:
                self._skill_tool_names[skill_key] = registered_names
                self._skill_namespaces[skill_key] = canonical_namespace
                if primary_skill is not None:
                    self._skill_objects[skill_key] = primary_skill
                self._skill_keys_by_platform.setdefault(
                    canonical_namespace, []
                ).append(skill_key)
                self._skill_format_ids[skill_key] = {
                    str(item.get("format_id"))
                    for item in (getattr(runtime, "ad_format_catalogs", []) or [])
                    if isinstance(item, dict) and item.get("format_id")
                }
        self._refresh_parser_catalog()
        self._background_tasks.extend(runtime.background_tasks)
        if runtime.write_guard:
            self.write_guard = runtime.write_guard
            if self._session_manager and hasattr(self.write_guard, "bind_store"):
                self.write_guard.bind_store(self._session_manager.store)
        self._refresh_unbound_clients()
        return runtime

    def _register_ad_format_catalog(
        self, platform: str, catalogs: list[dict[str, Any]]
    ) -> None:
        """Validate and index declarative format metadata."""
        if not catalogs:
            return
        canonical = self._canonical_platform(platform)
        allowed = {item.value for item in AdFormatCoverage}
        existing = {
            str(item.get("format_id")): item
            for item in self.ad_format_catalogs.get(canonical, [])
        }
        normalized = list(self.ad_format_catalogs.get(canonical, []))
        for item in catalogs:
            if not isinstance(item, dict):
                raise ValueError(f"{canonical}: ad format catalog entry must be an object")
            entry = dict(item)
            format_id = str(entry.get("format_id", "")).strip()
            status = str(entry.get("coverage", "")).strip().lower()
            if not format_id:
                raise ValueError(f"{canonical}: ad format catalog entry needs format_id")
            if status not in allowed:
                raise ValueError(f"{canonical}.{format_id}: unsupported coverage {status!r}")
            if not str(entry.get("category", "")).strip():
                raise ValueError(f"{canonical}.{format_id}: category is required")
            if not str(entry.get("resource_type", "")).strip():
                raise ValueError(f"{canonical}.{format_id}: resource_type is required")
            tool_names = entry.get("tool_names", []) or []
            if not isinstance(tool_names, list) or not all(
                isinstance(name, str) and name for name in tool_names
            ):
                raise ValueError(f"{canonical}.{format_id}: tool_names must be a string list")
            entry["format_id"] = format_id
            entry["coverage"] = status
            entry["tool_names"] = list(dict.fromkeys(tool_names))
            entry["live_support"] = bool(entry.get("live_support", False))
            registered_tools = {
                definition.name for definition in self.registry.list_all()
            }
            missing_tools = sorted(set(entry["tool_names"]) - registered_tools)
            if missing_tools:
                raise ValueError(
                    f"{canonical}.{format_id}: unknown tool_names: {', '.join(missing_tools)}"
                )
            if entry["live_support"]:
                raise ValueError(
                    f"{canonical}.{format_id}: ad-format live_support must remain false; "
                    "live enablement is a separate deployment approval"
                )
            if (
                status == AdFormatCoverage.SUPPORTED_DRY_RUN.value
                and not entry.get("payload_adapter")
            ):
                raise ValueError(
                    f"{canonical}.{format_id}: supported_dry_run needs payload_adapter"
                )
            previous = existing.get(format_id)
            if previous is not None and previous != entry:
                raise ValueError(f"{canonical}.{format_id}: conflicting catalog entry")
            if previous is None:
                existing[format_id] = entry
                normalized.append(entry)
        self.ad_format_catalogs[canonical] = normalized

    def _register_skill(self, skill: Skill) -> None:
        register_aliases = getattr(self.intent_parser, "register_namespace_aliases", None)
        if callable(register_aliases):
            register_aliases(skill.namespace, skill.namespace_aliases or [])
        registered_names: list[str] = []
        for tool_def in skill.get_tools():
            skill_namespace = self._canonical_platform(skill.namespace)
            tool_namespace = self._canonical_platform(tool_def.namespace)
            if tool_namespace != skill_namespace:
                raise ValueError(
                    f"Tool '{tool_def.name}' namespace '{tool_namespace}' "
                    f"does not match Skill namespace '{skill_namespace}'"
                )
            if self._read_only_mode and tool_def.is_write_tool:
                continue
            handler = skill.get_tool_handler(tool_def.name)
            if handler:
                self.registry.register(tool_def, handler)
                registered_names.append(tool_def.name)
        if registered_names:
            skill_key = str(getattr(skill, "name", "") or skill.namespace)
            self._skill_tool_names[skill_key] = registered_names
            self._skill_namespaces[skill_key] = skill.namespace
            self._skill_objects[skill_key] = skill
            namespace_key = self._canonical_platform(skill.namespace)
            keys = self._skill_keys_by_platform.setdefault(namespace_key, [])
            if skill_key not in keys:
                keys.append(skill_key)
            register_tools = getattr(self.intent_parser, "register_tool_definitions", None)
            if callable(register_tools):
                register_tools([
                    self.registry.get(name)[0] for name in registered_names
                ])


__all__ = ["AdToolSourceRegistrationMixin", "serialize_skill_lifecycle"]
