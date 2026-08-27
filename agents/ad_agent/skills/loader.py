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
        self._roots: list = []
        if skills_root:
            self._roots = [Path(skills_root)]
        else:
            self._roots = [self._default_skills_root()]
        self._skills: Dict[str, SkillDefinition] = {}
        
    def _default_skills_root(self) -> Path:
        """默认 skills 目录"""
        return Path(__file__).parent.parent / "skills"
    
    def add_root(self, root: str) -> None:
        """添加 Skill 根目录"""
        self._roots.append(Path(root))
    
    def load_all(self) -> Dict[str, SkillDefinition]:
        """加载所有 Skill"""
        for root in self._roots:
            if not root.exists():
                continue
            
            # Skills are commonly grouped below channels/ and businesses/.
            # Walk recursively so the selector can actually resolve the
            # platform expert material instead of loading only a top-level
            # cross-channel file.
            for skill_file in root.rglob("SKILL.md"):
                skill = self._load_skill(skill_file.parent)
                if skill:
                    self._skills[skill.name] = skill

        return self._skills
    
    def _load_skill(self, skill_dir: Path) -> Optional[SkillDefinition]:
        """加载单个 Skill"""
        skill_file = skill_dir / "SKILL.md"
        
        try:
            with open(skill_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 解析 YAML frontmatter (---...---)
            metadata = {}
            if content.startswith('---'):
                # 提取 frontmatter
                match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
                if match:
                    yaml_content = match.group(1)
                    try:
                        # 使用 safe_load 解析单个 YAML 文档
                        metadata = yaml.safe_load(yaml_content) or {}
                    except yaml.YAMLError as e:
                        print(f"❌ 解析 {skill_dir.name}/SKILL.md 失败: {e}")
                        return None
            
            # 提取 skill 名称和平台。兼容当前渠道 Skill 使用的扁平
            # frontmatter，以及 cross-channel/扩展 Skill 常用的
            # ``skill: {...}`` 嵌套格式。
            metadata = metadata if isinstance(metadata, dict) else {}
            skill_metadata = metadata.get('skill', {})
            skill_metadata = skill_metadata if isinstance(skill_metadata, dict) else {}
            skill_name = (
                metadata.get('name')
                or skill_metadata.get('name')
                or skill_dir.name
            )
            skill_platform = (
                metadata.get('platform')
                or skill_metadata.get('platform')
                or skill_dir.name
            )
            skill_description = (
                metadata.get('description')
                or skill_metadata.get('description')
                or ''
            )
            skill_version = (
                metadata.get('version')
                or skill_metadata.get('version')
                or '1.0'
            )
            
            skill = SkillDefinition(
                name=skill_name,
                version=skill_version,
                description=skill_description,
                platform=skill_platform,
                skill_file=skill_file,
            )
            
            # 加载 tools (从 Markdown 表格解析)
            skill.tools = self._parse_tools_from_markdown(content, skill_platform)
            
            # 加载 expert knowledge (如果存在)
            expert_dir = skill_dir / "expert"
            if expert_dir.exists():
                for md_file in expert_dir.glob("*.md"):
                    with open(md_file, 'r', encoding='utf-8') as f:
                        skill.expert_knowledge[md_file.stem] = f.read()
            
            return skill
            
        except Exception as e:
            print(f"❌ 加载 Skill {skill_dir.name} 失败: {e}")
            return None
    
    def _parse_tools_from_markdown(self, content: str, platform: str) -> List['ToolDefinition']:
        """
        从 Markdown 表格解析工具定义
        
        支持两种格式：
        1. 表格格式: \n| Tool | 功能 | 参数 |\n|------|------|------|\n| meta_xxx | ... | ... |\n        2. 标题格式: ### meta_create_campaign\n
        """
        tools = []
        lines = content.split('\n')
        
        # 尝试从表格中提取
        in_table = False
        table_headers = []
        tool_data = []
        
        for line in lines:
            # 检测表格开始
            if '| Tool |' in line or '| 工具 |' in line or '| tool |' in line:
                in_table = True
                table_headers = [h.strip() for h in line.split('|')]
                continue
            
            # 跳过分隔行
            if re.match(r'^\|[-:|\s]+\|$', line):
                continue
            
            # 解析表格数据行
            if in_table and line.startswith('|'):
                cells = [c.strip() for c in line.split('|')]
                cells = [c for c in cells if c]  # 过滤空单元格
                
                if len(cells) >= 2:
                    tool_name = cells[0].replace('`', '')  # 去掉 markdown 代码标记
                    tool_desc = cells[1] if len(cells) > 1 else ''
                    tool_params = cells[2] if len(cells) > 2 else ''
                    
                    # 跳过非工具行（如平台说明）
                    if not tool_name.startswith('Tool') and not tool_name.startswith('工具'):
                        tools.append(self._create_tool_def(tool_name, tool_desc, platform))
                continue
            
            # 表格结束（空行或新章节）
            if in_table and (not line.startswith('|') or line.strip() == ''):
                in_table = False
                continue
        
        return tools
    
    def _create_tool_def(self, name: str, description: str, platform: str) -> 'ToolDefinition':
        """创建 ToolDefinition"""
        from dataclasses import field
        return ToolDefinition(
            name=name,
            description=description,
            platform=platform,
            risk_level="medium",
            params={},
        )
    
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
