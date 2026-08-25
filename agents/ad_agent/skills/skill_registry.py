"""
skills/skill_registry.py - Skill 动态注册器

实现 Skills → Capabilities → Tools 的动态加载机制：
1. 从 SKILL.md 解析 Skill 定义（元信息）
2. 根据 Skill 定义动态创建/查找对应的 Handler
3. 将工具注册到 ToolRegistry
4. 构建系统提示词，注入相关 Skill 信息

核心设计原则：
- Skills 定义能力边界和流程
- Capabilities 提供具体实现
- Handlers 执行实际操作
- SkillRegistry 负责动态装配
"""

import os
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field

from ..core.interfaces import (
    ToolDefinition, ToolHandler, ToolResult, ToolContext,
    RiskLevel, ToolEffect
)
from ..runtime.skill import Skill, SkillLoader, SkillContract

logger = logging.getLogger(__name__)


@dataclass
class SkillBinding:
    """Skill 绑定信息"""
    skill: Skill
    platform: str
    handler_factory: Callable[[Any], ToolHandler]  # 工厂函数，根据 API Client 创建 Handler
    is_enabled: bool = True


class SkillRegistry:
    """
    Skill 动态注册器
    
    职责：
    1. 加载所有 Skills（从 SKILL.md）
    2. 根据 Skill 定义动态绑定 Handlers
    3. 注册工具到 ToolRegistry
    4. 提供系统提示词构建
    """
    
    def __init__(self, skill_roots: List[str] = None):
        """
        Args:
            skill_roots: Skill 目录根路径列表
        """
        self._skill_roots = skill_roots or []
        self._skills: Dict[str, Skill] = {}
        self._bindings: Dict[str, SkillBinding] = {}  # skill_name -> SkillBinding
        self._handler_factories: Dict[str, Callable] = {}  # tool_name -> factory
        self._api_clients: Dict[str, Any] = {}  # platform -> api_client
        
    def add_root(self, root: str) -> None:
        """添加 Skill 根目录"""
        if root not in self._skill_roots:
            self._skill_roots.append(root)
    
    def register_api_client(self, platform: str, client: Any) -> None:
        """注册 API 客户端（用于真实模式）"""
        self._api_clients[platform] = client
        # 重新加载相关 Skill 的 Handlers
        self._reload_skill_handlers(platform)
    
    def load_all(self) -> Dict[str, Skill]:
        """
        加载所有 Skills
        
        Returns:
            {skill_name: Skill, ...}
        """
        loader = SkillLoader(self._skill_roots)
        for root in self._skill_roots:
            loader.add_root(root)
        
        self._skills = loader.load_all()
        logger.info(f"✅ 已加载 {len(self._skills)} 个 Skills: {list(self._skills.keys())}")
        
        return self._skills
    
    def register_skill_handlers(self, skill: Skill, platform: str) -> None:
        """
        为指定 Skill 注册 Handlers
        
        Args:
            skill: Skill 对象
            platform: 平台名称
        """
        # 查找对应的 Handler 工厂
        factory = self._find_handler_factory(skill, platform)
        if not factory:
            logger.warning(f"⚠️ 未找到 Skill '{skill.name}' 的 Handler 工厂")
            return
        
        # 创建 SkillBinding
        binding = SkillBinding(
            skill=skill,
            platform=platform,
            handler_factory=factory,
            is_enabled=True
        )
        self._bindings[skill.name] = binding
        
        # 注册所有工具
        for tool_def in skill.get_tools():
            api_client = self._api_clients.get(platform)
            handler = factory(api_client) if api_client else factory(None)
            self._handler_factories[tool_def.name] = lambda _, h=handler: h
        
        logger.info(f"✅ 已注册 Skill '{skill.name}' 的 {len(skill.get_tools())} 个工具")
    
    def _find_handler_factory(self, skill: Skill, platform: str) -> Optional[Callable]:
        """
        查找 Skill 对应的 Handler 工厂
        
        策略：
        1. 优先查找 platform_capability 模块中的工厂函数
        2. 回退到默认工厂（Mock 模式）
        """
        from ..capabilities import meta_capability, platform_capabilities
        
        # 根据平台名称选择对应的 capability 模块
        platform_map = {
            'meta': ('meta', meta_capability),
            'google-ads': ('google', platform_capabilities),
            'tiktok': ('tiktok', platform_capabilities),
            'dv360': ('dv360', platform_capabilities),
        }
        
        module_key = platform_map.get(platform)
        if not module_key:
            return None
        
        module_name, module = module_key
        
        # 尝试查找工厂函数
        factory_names = [
            f'create_{module_name}_capability',
            f'create_{platform}_capability',
        ]
        
        for name in factory_names:
            if hasattr(module, name):
                return getattr(module, name)
        
        return None
    
    def _reload_skill_handlers(self, platform: str) -> None:
        """重新加载指定平台的 Skill Handlers"""
        for skill_name, binding in self._bindings.items():
            if binding.platform == platform:
                self.register_skill_handlers(binding.skill, platform)
    
    def get_skill(self, name: str) -> Optional[Skill]:
        """获取指定 Skill"""
        return self._skills.get(name)
    
    def get_skills_by_platform(self, platform: str) -> List[Skill]:
        """获取指定平台的所有 Skills"""
        return [s for s in self._skills.values() if s.platform == platform]
    
    def get_enabled_skills(self) -> List[Skill]:
        """获取所有启用的 Skills"""
        return [s for s in self._skills.values() if self._bindings.get(s.name, SkillBinding(s, "", lambda x: None)).is_enabled]
    
    def build_system_prompt(self, user_input: str = None, intent_type: str = None) -> str:
        """
        构建系统提示词
        
        Args:
            user_input: 用户输入（可选，用于相关 Skill 推荐）
            intent_type: 意图类型（可选）
        
        Returns:
            系统提示词字符串
        """
        # 获取所有启用的 Skills
        skills = self.get_enabled_skills()
        
        if not skills:
            return "你是广告投放专家助手。"
        
        # 构建 Skill 摘要
        skill_summaries = []
        for skill in skills:
            tools = skill.get_tools()
            tool_names = [t.name for t in tools[:5]]  # 只显示前5个
            summary = f"\n- **{skill.name}** ({skill.platform}): {skill.description[:80]}..."
            summary += f"\n  工具: {', '.join(tool_names)}{'...' if len(tools) > 5 else ''}"
            skill_summaries.append(summary)
        
        prompt = """你是专业的广告投放助手，精通 Meta、Google Ads、TikTok Ads、DV360 四大广告平台。

## 可用渠道能力
"""
        prompt += "\n".join(skill_summaries)
        
        if user_input:
            prompt += f"\n\n## 用户当前需求\n{user_input}\n\n请根据用户需求和上述能力，选择合适的工具完成操作。"
        
        return prompt
    
    def get_tool_definitions(self) -> List[ToolDefinition]:
        """获取所有已注册的工具定义"""
        all_tools = []
        for skill in self.get_enabled_skills():
            all_tools.extend(skill.get_tools())
        return all_tools


# 全局实例
_registry: Optional[SkillRegistry] = None


def get_skill_registry() -> SkillRegistry:
    """获取全局 Skill 注册器"""
    global _registry
    if _registry is None:
        _registry = SkillRegistry()
    return _registry


def init_skill_registry(skill_roots: List[str]) -> SkillRegistry:
    """
    初始化 Skill 注册器
    
    Args:
        skill_roots: Skill 目录根路径列表
    """
    global _registry
    _registry = SkillRegistry(skill_roots)
    _registry.load_all()
    return _registry
