"""Standard Skill directory discovery for the advertising application."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class AdSkillDiscoveryMixin:
    def auto_load_skills(
        self,
        skills_root: str,
        credentials: dict = None,
        *,
        allow_executable_plugins: bool = False,
        allow_provider_tool_discovery: bool = False,
    ) -> int:
        """Discover standard Skills and activate only trusted executable paths."""
        loaded_count = 0
        credentials = self._credentials if credentials is None else credentials
        credentials = credentials or {}
        if credentials:
            self._credentials = self._copy_credentials(credentials)
        self.skill_loader.add_root(skills_root)
        self.skill_loader.load_all()
        for skill_dir in self.skill_loader.iter_skill_dirs([skills_root]):
            try:
                loaded_skill = self.skill_loader.load_skill_dir(skill_dir)
                if loaded_skill is None or bool(
                    getattr(loaded_skill, "context_only", False)
                ):
                    continue
                platform = loaded_skill.namespace
                provider_credentials = (
                    self._credentials_for_platform(platform, credentials)
                    if (allow_executable_plugins or allow_provider_tool_discovery)
                    else {}
                )
                api_client = None
                if provider_credentials and (
                    allow_executable_plugins or allow_provider_tool_discovery
                ):
                    try:
                        api_client = self.provider_bindings.create_client(
                            platform, provider_credentials
                        )
                    except Exception as exc:
                        logger.debug("创建 %s API Client 失败: %s", platform, exc)
                plugin_skill = (
                    self._load_skill_plugin(skill_dir, api_client)
                    if allow_executable_plugins else None
                )
                if plugin_skill is not None:
                    before_tool_count = len(self.registry.list_all())
                    registered = self.register_skill(
                        plugin_skill, platform, api_client
                    )
                    if not registered:
                        logger.warning(
                            "⚠️ Skill plugin '%s' 未注册任何可执行工具",
                            plugin_skill.name,
                        )
                        continue
                    loaded_count += 1
                    logger.info(
                        "✅ 自动加载 Skill plugin: %s (%s, %s executable tools)",
                        plugin_skill.name,
                        platform,
                        len(self.registry.list_all()) - before_tool_count,
                    )
                    continue
                if not allow_provider_tool_discovery:
                    continue
                canonical = self._canonical_platform(platform)
                tool_source = self._discover_tool_source(canonical, api_client)
                if tool_source is None:
                    tool_source = self.provider_bindings.create_tool_source(
                        canonical, api_client
                    )
                before_tool_count = len(self.registry.list_all())
                self.register_provider_tool_source(tool_source)
                registered_count = len(self.registry.list_all()) - before_tool_count
                if registered_count <= 0:
                    logger.warning(
                        "⚠️ Tool Source '%s' 未注册任何可执行工具", canonical
                    )
                    continue
                loaded_count += 1
                logger.info(
                    "✅ 自动加载 Tool Source: %s (%s executable tools)",
                    platform,
                    registered_count,
                )
            except ValueError:
                logger.debug("未找到平台 Tool Source: %s", skill_dir)
            except Exception as exc:
                logger.warning(
                    "⚠️ 解析 Skill %s/SKILL.md 失败: %s",
                    skill_dir.name,
                    exc,
                )
        logger.info("✅ 自动加载完成，共加载 %s 个 Skills", loaded_count)
        return loaded_count

    def _copy_credentials(self, credentials: dict) -> dict:
        """Keep credential copying behind the provider adapter boundary."""
        import copy

        return copy.deepcopy(credentials)


__all__ = ["AdSkillDiscoveryMixin"]
