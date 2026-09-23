"""Skill registration and lifecycle management for the advertising app."""

from __future__ import annotations

import logging
from typing import Optional

from .ad_tool_source_registration import serialize_skill_lifecycle
from .skill import Skill

logger = logging.getLogger(__name__)


class AdSkillLifecycleMixin:
    @serialize_skill_lifecycle
    def register_skill(self, skill: Skill, platform: str, api_client=None) -> bool:
        """Register a Skill through the canonical Tool Source boundary."""
        canonical_namespace = self.provider_bindings.normalize_namespace(platform)
        declared_namespace = self.provider_bindings.normalize_namespace(
            getattr(skill, "namespace", "")
        )
        if declared_namespace and declared_namespace != canonical_namespace:
            raise ValueError(
                f"Skill '{getattr(skill, 'name', '')}' namespace "
                f"'{declared_namespace}' does not match requested namespace "
                f"'{canonical_namespace}'"
            )
        skill_key = str(
            getattr(skill, "name", "") or f"{canonical_namespace}:{id(skill)}"
        )
        if skill_key in self._skill_tool_names:
            logger.info("ⓘ Skill '%s' 已加载，跳过重复注册", skill_key)
            return True

        declared_tools = []
        get_tools = getattr(skill, "get_tools", None)
        get_handler = getattr(skill, "get_tool_handler", None)
        if callable(get_tools) and callable(get_handler):
            try:
                declared_tools = list(get_tools() or [])
            except Exception as exc:
                logger.warning("解析 Skill '%s' 工具声明失败: %s", skill_key, exc)

        tool_source = self._discover_tool_source(canonical_namespace, api_client)
        if tool_source is None:
            try:
                tool_source = self.provider_bindings.create_tool_source(
                    canonical_namespace, api_client
                )
            except ValueError:
                if not declared_tools:
                    logger.warning(
                        "⚠️ 未找到平台 '%s' 的 Tool Source，且 Skill 没有声明可执行工具",
                        platform,
                    )
                    return False

        tool_source_tools = {
            definition.name: (definition, handler)
            for definition, handler in tool_source.register_tools()
        } if tool_source is not None else {}
        tools = []
        if declared_tools:
            for declared in declared_tools:
                declared_tool_namespace = self.provider_bindings.normalize_namespace(
                    getattr(declared, "namespace", "")
                )
                if declared_tool_namespace != canonical_namespace:
                    raise ValueError(
                        f"Tool '{declared.name}' namespace "
                        f"'{declared_tool_namespace}' does not match requested "
                        f"'{canonical_namespace}'"
                    )
                handler = get_handler(declared.name)
                if handler is None and declared.name in tool_source_tools:
                    _, handler = tool_source_tools[declared.name]
                if handler is not None:
                    tools.append((declared, handler))
            if not tools:
                logger.warning(
                    "⚠️ Skill '%s' 的工具均没有可执行 Handler，未注册",
                    skill_key,
                )
                return False
        else:
            tools = list(tool_source_tools.values())
        if not tools:
            logger.warning("⚠️ Tool Source '%s' 没有定义任何工具", platform)
            return False

        registered_count = 0
        for tool_def, handler in tools:
            tool_namespace = self.provider_bindings.normalize_namespace(
                getattr(tool_def, "namespace", "")
            )
            if tool_namespace != canonical_namespace:
                raise ValueError(
                    f"Tool '{tool_def.name}' namespace '{tool_namespace}' "
                    f"does not match requested '{canonical_namespace}'"
                )
            metadata_errors = tool_def.routing_metadata_errors()
            if metadata_errors:
                raise ValueError(
                    f"Skill '{skill_key}' Tool '{tool_def.name}' is missing explicit "
                    "routing metadata: " + ", ".join(metadata_errors)
                )
            if self._read_only_mode and tool_def.is_write_tool:
                continue
            if not tool_def.scope_fields:
                tool_def.scope_type = tool_def.scope_type or "account"
                tool_def.scope_fields = [
                    "account_id", "ad_account_id", "advertiser_id", "customer_id",
                ]
                tool_def.scope_required = True
            if tool_def.is_write_tool and not tool_def.live_permission:
                tool_def.live_permission = "ads.write"
            if not tool_def.required_permissions:
                tool_def.required_permissions = [
                    "ads.plan" if tool_def.is_write_tool else "ads.read"
                ]
            try:
                self.registry.register(tool_def, handler)
                self.parameter_catalogs.register_tool_schema(
                    tool_def.namespace,
                    getattr(tool_def.input_schema, "properties", {})
                    if tool_def.input_schema else {},
                    tool_name=tool_def.name,
                )
                registered_count += 1
            except Exception as exc:
                logger.warning("⚠️ 注册工具失败 '%s': %s", tool_def.name, exc)
        if registered_count == 0:
            logger.warning("⚠️ Skill '%s' 没有实际注册任何工具", skill_key)
            return False
        self._validate_parameter_lookup_contract()
        register_tools = getattr(self.intent_parser, "register_tool_definitions", None)
        if callable(register_tools):
            register_tools(self.registry.list_all())
        self._skill_tool_names[skill_key] = [
            tool_def.name for tool_def, _ in tools
        ]
        self._skill_namespaces[skill_key] = canonical_namespace
        self._skill_objects[skill_key] = skill
        keys = self._skill_keys_by_platform.setdefault(canonical_namespace, [])
        if skill_key not in keys:
            keys.append(skill_key)
        self._refresh_parser_catalog()
        self._register_builtin_plugin(
            f"skill:{skill_key}",
            skill,
            ("skill", "tool_source"),
            version=str(getattr(skill, "version", "1.0.0") or "1.0.0"),
            description=str(getattr(skill, "description", "") or ""),
        )
        logger.info("✅ 已动态注册 Skill '%s'，共 %s 个工具", skill.name, registered_count)
        return True

    @serialize_skill_lifecycle
    def load_skill(self, platform: str, skill: Skill, api_client=None) -> bool:
        skill_key = str(getattr(skill, "name", "") or platform)
        if skill_key in self._skill_tool_names:
            logger.info("ⓘ Skill '%s' 已加载，跳过", skill_key)
            return True
        try:
            return bool(self.register_skill(skill, platform, api_client))
        except Exception as exc:
            logger.error("❌ 加载 Skill '%s' 失败: %s", platform, exc)
            return False

    @serialize_skill_lifecycle
    def unload_skill(self, platform: str, skill_name: Optional[str] = None) -> bool:
        """Unload a Skill atomically and restore all indexes on failure."""
        canonical_namespace = self._canonical_platform(platform)
        candidates = list(self._skill_keys_by_platform.get(canonical_namespace, []))
        if not candidates:
            return True
        target_key = ""
        tool_names: list[str] = []
        try:
            target_key = (
                skill_name
                if skill_name in candidates
                else ("" if skill_name else candidates[0])
            )
            if not target_key:
                return False
            tool_names = list(self._skill_tool_names.get(target_key, []))
            target_skill = self._skill_objects.get(target_key)
            registry_snapshot = self.registry._snapshot_tools(
                tool_names, _execution_token=self._registry_execution_token
            )
            parameter_snapshot = self.parameter_catalogs.snapshot()
            blueprint_snapshot = self.creation_blueprints.snapshot()
            loaded_skill_snapshot = self.skill_loader.snapshot()
            skill_tool_snapshot = {
                key: list(value) for key, value in self._skill_tool_names.items()
            }
            skill_namespace_snapshot = dict(self._skill_namespaces)
            skill_object_snapshot = dict(self._skill_objects)
            skill_keys_snapshot = {
                key: list(value) for key, value in self._skill_keys_by_platform.items()
            }
            skill_format_snapshot = {
                key: set(value) for key, value in self._skill_format_ids.items()
            }
            format_catalog_snapshot = __import__("copy").deepcopy(
                self.ad_format_catalogs
            )
            context_service = getattr(self, "_context_service", None)
            context_snapshot = (
                context_service().snapshot()
                if callable(context_service) else None
            )
            for name in dict.fromkeys(tool_names):
                self.registry.unregister(name)
            self.parameter_catalogs.remove_tools(tool_names)
            format_ids = self._skill_format_ids.pop(target_key, set())
            if format_ids:
                self.ad_format_catalogs[canonical_namespace] = [
                    entry for entry in self.ad_format_catalogs.get(canonical_namespace, [])
                    if str(entry.get("format_id")) not in format_ids
                ]
                if not self.ad_format_catalogs[canonical_namespace]:
                    self.ad_format_catalogs.pop(canonical_namespace, None)
            self._skill_tool_names.pop(target_key, None)
            self._skill_namespaces.pop(target_key, None)
            self._skill_objects.pop(target_key, None)
            if target_skill is not None:
                self.skill_loader.unload(getattr(target_skill, "name", ""))
            remaining = [key for key in candidates if key != target_key]
            if remaining:
                self._skill_keys_by_platform[canonical_namespace] = remaining
            else:
                self._skill_keys_by_platform.pop(canonical_namespace, None)
                self.creation_blueprints.remove_owner(canonical_namespace)
            self._refresh_parser_catalog()
            self.plugin_registry.unregister(f"skill:{target_key}")
            logger.info(
                "✅ 已卸载 Skill '%s' (platform=%s)，移除 %s 个工具",
                target_key, canonical_namespace, len(set(tool_names)),
            )
            return True
        except Exception as exc:
            logger.error("❌ 卸载 Skill '%s' 失败: %s", platform, exc)
            try:
                if target_key:
                    self.registry._restore_tools(
                        registry_snapshot,
                        _execution_token=self._registry_execution_token,
                    )
                    self.parameter_catalogs.restore(parameter_snapshot)
                    self.creation_blueprints.restore(blueprint_snapshot)
                    self.skill_loader.restore(loaded_skill_snapshot)
                    self._skill_tool_names = skill_tool_snapshot
                    self._skill_namespaces = skill_namespace_snapshot
                    self._skill_objects = skill_object_snapshot
                    self._skill_keys_by_platform = skill_keys_snapshot
                    self._skill_format_ids = skill_format_snapshot
                    self.ad_format_catalogs = format_catalog_snapshot
                    if context_snapshot is not None:
                        context_service = getattr(self, "_context_service", None)
                        if callable(context_service):
                            context_service().restore(context_snapshot)
                    self._refresh_parser_catalog()
            except Exception:
                logger.exception(
                    "❌ Skill '%s' 卸载回滚失败，Runtime 需要重新加载",
                    target_key or platform,
                )
            return False

    def get_loaded_skills(self) -> dict[str, Skill]:
        return self._skill_objects.copy()

    def get_available_skills(self) -> dict[str, Skill]:
        for skill_dir in self.skill_loader.iter_skill_dirs():
            try:
                self.skill_loader.load_skill_dir(skill_dir)
            except Exception as exc:
                logger.debug("加载可用 Skill 失败 %s: %s", skill_dir, exc)
        return self.skill_loader.list_all()

    def _load_required_skills(self, platforms: list[str]) -> None:
        if not platforms:
            return
        for platform in platforms:
            actual_platform = self._canonical_platform(platform)
            if self._skill_keys_by_platform.get(actual_platform):
                continue
            skill = self._find_skill_by_platform(actual_platform)
            if not skill:
                logger.warning("未找到平台 '%s' 的 Skill 定义", actual_platform)
                continue
            self.load_skill(actual_platform, skill, self._get_api_client(platform))

    def _find_skill_by_platform(self, platform: str) -> Skill:
        canonical_namespace = self._canonical_platform(platform)
        for skill_key in self._skill_keys_by_platform.get(canonical_namespace, []):
            skill = self._skill_objects.get(skill_key)
            if skill is not None:
                return skill
        candidates = self.skill_loader.get_by_namespace(canonical_namespace)
        return candidates[0] if candidates else None


__all__ = ["AdSkillLifecycleMixin"]
