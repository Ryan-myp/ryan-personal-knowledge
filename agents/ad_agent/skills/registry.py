"""
skills/registry.py - Skill 工具注册器

从 SKILL.md 解析工具定义并注册到 ToolRegistry
支持 Skill 热加载和动态扩展
"""

import re
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

from ..core.interfaces import (
    ToolDefinition, ToolHandler, ToolSchema, ToolResult,
    ToolContext, RiskLevel, ToolEffect, ReplayPolicy
)
from ..core.tool_registry import SimpleToolRegistry

logger = logging.getLogger(__name__)


@dataclass
class SkillTool:
    """Skill 中的工具定义"""
    name: str
    description: str
    platform: str
    params: Dict[str, Any] = field(default_factory=dict)
    expert_tips: str = ""
    risk_level: str = "low"


class SkillRegistry:
    """Skill 工具注册器"""
    
    def __init__(self, registry: SimpleToolRegistry):
        self.registry = registry
        self._skill_tools: Dict[str, List[SkillTool]] = {}
    
    def register_skill_tools(self, skill_dir: Path, skill_name: str):
        """注册 Skill 中的所有工具"""
        tools = self._parse_skill_file(skill_dir / "SKILL.md")
        
        if tools:
            self._skill_tools[skill_name] = tools
            for tool in tools:
                self._register_tool(tool)
            logger.info(f"✅ 已注册 Skill: {skill_name} ({len(tools)} 个工具)")
        
        return tools
    
    def _parse_skill_file(self, skill_file: Path) -> List[SkillTool]:
        """解析 SKILL.md 文件"""
        if not skill_file.exists():
            return []
        
        # 从文件路径推断平台
        platform = skill_file.parent.name
        
        # 尝试从 YAML 头部读取 platform 字段（规范化平台名称）
        content = skill_file.read_text(encoding='utf-8')
        if content.startswith('---'):
            try:
                import yaml
                yaml_content = content.split('---')[1]
                metadata = yaml.safe_load(yaml_content)
                if metadata and 'skill' in metadata and 'platform' in metadata['skill']:
                    platform = metadata['skill']['platform']
            except:
                pass
        tools = []
        
        # 提取 YAML 头部中的工具列表
        # 格式: #### tool_name\n- **描述**: xxx\n- **参数**: ...\n- **专家提示**: ...\n
        
        current_tool = None
        in_tools_section = False
        
        for line in content.split('\n'):
            line = line.strip()
            
            # 检测工具标题 (#### meta_create_campaign)
            if line.startswith('#### '):
                if current_tool:
                    tools.append(current_tool)
                tool_name = line[5:].strip()
                current_tool = SkillTool(name=tool_name, platform=platform, description="")
                in_tools_section = True
                continue
            
            # 提取描述
            if in_tools_section and '**描述**:' in line:
                desc = line.split('**描述**:')[-1].strip()
                if current_tool:
                    current_tool.description = desc
                continue
            
            # 提取专家提示
            if in_tools_section and '**专家提示**:' in line:
                tips = line.split('**专家提示**:')[-1].strip()
                if current_tool:
                    current_tool.expert_tips = tips
                continue
            
            # 空行结束当前工具
            if in_tools_section and not line:
                if current_tool:
                    tools.append(current_tool)
                    current_tool = None
                in_tools_section = False
        
        # 添加最后一个工具
        if current_tool:
            tools.append(current_tool)
        
        return tools
    
    def _register_tool(self, tool: SkillTool):
        """注册单个工具"""
        # 创建简单的 handler（实际调用会由具体实现处理）
        handler = self._create_handler(tool)
        
        definition = ToolDefinition(
            name=tool.name,
            skill=tool.platform,
            platform=tool.platform,
            description=tool.description,
            input_schema=ToolSchema(properties=tool.params),
            risk_level=self._parse_risk(tool.risk_level),
            effect_class=ToolEffect.EXTERNAL_WRITE,
            replay_policy=ReplayPolicy.UNSAFE,
            traits=[tool.platform, "campaign"],
        )
        
        self.registry.register(definition, handler)
    
    def _create_handler(self, tool: SkillTool) -> ToolHandler:
        """创建声明性兼容处理器。

        This legacy registry parses Skill markdown for backwards-compatible
        discovery only.  It must never claim that a provider operation was
        executed; executable handlers come from ``capabilities/`` and are
        dispatched by ``AgentRuntime``.
        """
        class GenericHandler(ToolHandler):
            def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
                return ToolResult.error(
                    f"Skill declaration '{tool.name}' has no executable Capability handler; "
                    "register a provider-backed Capability before execution"
                )
        
        return GenericHandler()
    
    def _parse_risk(self, risk_str: str) -> RiskLevel:
        """解析风险等级"""
        mapping = {
            "low": RiskLevel.LOW,
            "medium": RiskLevel.MEDIUM,
            "high": RiskLevel.HIGH,
        }
        return mapping.get(risk_str.lower(), RiskLevel.LOW)
    
    def get_skill_tools(self, skill_name: str) -> List[SkillTool]:
        """获取指定 Skill 的工具"""
        return self._skill_tools.get(skill_name, [])
    
    def get_all_tools(self) -> List[SkillTool]:
        """获取所有 Skill 的所有工具"""
        all_tools = []
        for tools in self._skill_tools.values():
            all_tools.extend(tools)
        return all_tools
    
    def get_all_registered_tools(self) -> List[Any]:
        """获取所有已注册到 ToolRegistry 的工具定义"""
        return self.registry.list_all()
    
    def get_all_skills(self) -> Dict[str, List[SkillTool]]:
        """获取所有 Skill 的工具"""
        return self._skill_tools
    
    def search_tools(self, keyword: str) -> List[SkillTool]:
        """搜索工具"""
        results = []
        keyword = keyword.lower()
        for skill_name, tools in self._skill_tools.items():
            for tool in tools:
                if keyword in tool.name.lower() or keyword in tool.description.lower():
                    results.append(tool)
        return results


# 全局实例
_skill_registry: Optional[SkillRegistry] = None


def get_skill_registry() -> SkillRegistry:
    """获取全局 Skill 注册器"""
    global _skill_registry
    if _skill_registry is None:
        _skill_registry = SkillRegistry(SimpleToolRegistry())
    return _skill_registry


def register_skill(skill_dir: Path, skill_name: str = None):
    """注册单个 Skill"""
    global _skill_registry
    if _skill_registry is None:
        _skill_registry = SkillRegistry(SimpleToolRegistry())
    
    if skill_name is None:
        skill_name = skill_dir.name
    
    return _skill_registry.register_skill_tools(skill_dir, skill_name)


def load_all_skills(skills_root: Path) -> Dict[str, List[SkillTool]]:
    """加载所有 Skills（递归扫描子目录，只解析不注册到全局 registry）"""
    # 创建临时 registry 用于解析
    temp_registry = SkillRegistry(SimpleToolRegistry())
    
    all_tools = {}
    if not skills_root.exists():
        return all_tools
    
    # 递归扫描所有子目录
    for skill_dir in sorted(skills_root.rglob('*')):
        if skill_dir.is_dir() and (skill_dir / "SKILL.md").exists():
            # 生成 skill_name: 使用相对路径
            rel_path = skill_dir.relative_to(skills_root)
            skill_name = "/".join(rel_path.parts)
            
            tools = temp_registry.register_skill_tools(skill_dir, skill_name)
            if tools:
                all_tools[skill_name] = tools
    
    return all_tools


def load_all_skills_and_register(skills_root: Path) -> Dict[str, List[SkillTool]]:
    """加载所有 Skills 并注册到全局 registry（向后兼容）"""
    global _skill_registry
    if _skill_registry is None:
        _skill_registry = SkillRegistry(SimpleToolRegistry())
    
    all_tools = {}
    if not skills_root.exists():
        return all_tools
    
    for skill_dir in sorted(skills_root.rglob('*')):
        if skill_dir.is_dir() and (skill_dir / "SKILL.md").exists():
            rel_path = skill_dir.relative_to(skills_root)
            skill_name = "/".join(rel_path.parts)
            
            tools = _skill_registry.register_skill_tools(skill_dir, skill_name)
            if tools:
                all_tools[skill_name] = tools
    
    return all_tools
