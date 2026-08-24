"""
skills/loader.py - Skill 加载器

支持动态加载 skills/ 目录下的 Skill 定义
每个 Skill 包含：
- SKILL.md: Skill 定义（tools + 专家知识）
- tools/: Tool 实现
- expert/: 专家知识文档
"""

import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

import yaml


@dataclass
class ToolDefinition:
    """Tool 定义"""
    name: str
    description: str
    platform: str
    risk_level: str = "low"
    params: Dict[str, Any] = field(default_factory=dict)
    expert_tips: str = ""


@dataclass
class SkillDefinition:
    """Skill 定义"""
    name: str
    version: str
    description: str
    platform: str
    tools: List[ToolDefinition] = field(default_factory=list)
    expert_knowledge: Dict[str, str] = field(default_factory=dict)
    skill_file: Path = None


class SkillLoader:
    """Skill 加载器"""
    
    def __init__(self, skills_root: str = None):
        self.skills_root = Path(skills_root) if skills_root else self._default_skills_root()
        self._skills: Dict[str, SkillDefinition] = {}
        
    def _default_skills_root(self) -> Path:
        """默认 skills 目录"""
        return Path(__file__).parent.parent / "skills"
    
    def load_all(self) -> Dict[str, SkillDefinition]:
        """加载所有 Skill"""
        if not self.skills_root.exists():
            return self._skills
        
        for skill_dir in self.skills_root.iterdir():
            if skill_dir.is_dir() and (skill_dir / "SKILL.md").exists():
                skill = self._load_skill(skill_dir)
                if skill:
                    self._skills[skill.name] = skill
        
        return self._skills
    
    def _load_skill(self, skill_dir: Path) -> Optional[SkillDefinition]:
        """加载单个 Skill"""
        skill_file = skill_dir / "SKILL.md"
        
        try:
            with open(skill_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 解析 YAML 头部
            if content.startswith('```yaml'):
                match = re.search(r'```yaml\s*\n(.*?)\n\s*```', content, re.DOTALL)
                if match:
                    metadata = yaml.safe_load(match.group(1))
                else:
                    metadata = {}
            else:
                metadata = yaml.safe_load(content.split('\n\n')[0]) if '\n\n' in content else {}
            
            skill = SkillDefinition(
                name=metadata.get('skill', {}).get('name', skill_dir.name),
                version=metadata.get('skill', {}).get('version', '1.0'),
                description=metadata.get('skill', {}).get('description', ''),
                platform=metadata.get('skill', {}).get('platform', ''),
                skill_file=skill_file,
            )
            
            # 加载 tools
            tools_dir = skill_dir / "tools"
            if tools_dir.exists():
                for tool_file in tools_dir.glob("*.py"):
                    tool_name = tool_file.stem
                    skill.tools.append(ToolDefinition(
                        name=f"{skill.platform}_{tool_name}",
                        description=f"{skill.platform} {tool_name} tool",
                        platform=skill.platform,
                    ))
            
            # 加载 expert knowledge
            expert_dir = skill_dir / "expert"
            if expert_dir.exists():
                for md_file in expert_dir.glob("*.md"):
                    with open(md_file, 'r', encoding='utf-8') as f:
                        skill.expert_knowledge[md_file.stem] = f.read()
            
            return skill
            
        except Exception as e:
            print(f"❌ 加载 Skill {skill_dir.name} 失败: {e}")
            return None
    
    def get_skill(self, name: str) -> Optional[SkillDefinition]:
        """获取指定 Skill"""
        return self._skills.get(name)
    
    def get_tools_by_platform(self, platform: str) -> List[ToolDefinition]:
        """获取指定平台的所有 Tools"""
        tools = []
        for skill in self._skills.values():
            if skill.platform == platform:
                tools.extend(skill.tools)
        return tools
    
    def get_all_tools(self) -> List[ToolDefinition]:
        """获取所有 Tools"""
        return [tool for skill in self._skills.values() for tool in skill.tools]
    
    def search_tools(self, keyword: str) -> List[ToolDefinition]:
        """搜索 Tools"""
        results = []
        keyword = keyword.lower()
        for tool in self.get_all_tools():
            if keyword in tool.name.lower() or keyword in tool.description.lower():
                results.append(tool)
        return results


# 全局实例
_skill_loader: Optional[SkillLoader] = None


def get_skill_loader() -> SkillLoader:
    """获取全局 Skill 加载器"""
    global _skill_loader
    if _skill_loader is None:
        _skill_loader = SkillLoader()
        _skill_loader.load_all()
    return _skill_loader


def register_skill(skill: SkillDefinition):
    """注册 Skill"""
    global _skill_loader
    if _skill_loader is None:
        _skill_loader = SkillLoader()
    _skill_loader._skills[skill.name] = skill
