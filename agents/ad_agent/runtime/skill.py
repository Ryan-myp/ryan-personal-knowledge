"""
runtime/skill.py - Skill 加载与执行

借鉴 DAP Agent internal/skill/loader.go
每个平台 Skill 是一个独立的工具集合。SKILL.md 提供自然语言专家上下文；
可执行 Tool 由 Capability/plugin 自注册并携带自己的结构化元数据。
"""

import os
import re
import yaml
from dataclasses import dataclass, field
from typing import Any, Optional
from pathlib import Path
from ..core.interfaces import (
    ToolDefinition, ToolHandler, ToolSchema, Skill, ToolContext,
    SkillWorkflow, SkillWorkflowStep,
)


# ─── Skill 声明解析 ─────────────────────────────────────────────

@dataclass
class SkillTrigger:
    """Skill 触发词"""
    keywords: list[str] = field(default_factory=list)
    patterns: list[str] = field(default_factory=list)


@dataclass
class SkillCapability:
    """单个工具的能力声明"""
    name: str
    description: str
    required_params: list[str] = field(default_factory=list)
    optional_params: list[str] = field(default_factory=list)
    risk_level: str = "low"
    effect: str = "read"  # read | write | external_write
    # Preserve the declarative schema when a Skill is loaded from
    # contract.yaml/tools/*.yaml.  Older versions only retained required
    # parameter names, silently dropping enums and provider conditions.
    input_schema: dict[str, Any] = field(default_factory=dict)
    live_support: bool = True
    required_permissions: list[str] = field(default_factory=list)
    action: str = ""
    resource_type: str = ""
    parent_resource_type: Optional[str] = None
    intent_types: list[str] = field(default_factory=list)


class SkillContract:
    """
    Skill 合约定义 - 对应 Go 的 skill.Contract
    
    从 SKILL.md frontmatter + YAML 合约文件加载。
    """
    
    def __init__(self, skill_dir: str):
        self.skill_dir = skill_dir
        self.name: str = ""
        self.version: str = "1.0"
        self.description: str = ""
        self.platform: str = ""
        self.triggers: list[SkillTrigger] = []
        self.capabilities: dict[str, SkillCapability] = {}
        self.workflows: dict[str, SkillWorkflow] = {}
        self.references: dict[str, str] = {}  # ref_name -> file_path
        self.expert_knowledge: dict[str, str] = {}
        self.raw_md: str = ""
        self.raw_yaml: dict = {}
    
    def load(self) -> "SkillContract":
        """从文件系统加载 Skill 合约"""
        # 1. 加载 SKILL.md
        skill_md_path = os.path.join(self.skill_dir, "SKILL.md")
        if os.path.exists(skill_md_path):
            self._load_skill_md(skill_md_path)
            # A workflow file is an optional Skill-owned orchestration
            # contract. It is never required for ordinary channel Skills and
            # is kept separate from the natural-language SKILL.md body.
            self._load_workflow_file(skill_md_path)
        
        # 2. 加载 YAML 合约（如有）
        yaml_path = os.path.join(self.skill_dir, "contract.yaml")
        if os.path.exists(yaml_path):
            self._load_contract_yaml(yaml_path)
        
        # 3. 加载工具合约
        tools_dir = os.path.join(self.skill_dir, "tools")
        if os.path.isdir(tools_dir):
            self._load_tools_from_directory(tools_dir)

        expert_dir = os.path.join(self.skill_dir, "expert")
        if os.path.isdir(expert_dir):
            for filename in sorted(os.listdir(expert_dir)):
                if not filename.endswith(".md"):
                    continue
                try:
                    with open(os.path.join(expert_dir, filename), "r", encoding="utf-8") as file:
                        self.expert_knowledge[Path(filename).stem] = file.read()
                except OSError:
                    continue

        return self
    
    def _load_skill_md(self, path: str) -> None:
        """解析 SKILL.md 文件"""
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        self.raw_md = content
        
        # 解析 frontmatter（YAML 块）- 支持两种格式：
        # 1. 直接格式: name: xxx, description: xxx
        # 2. 嵌套格式: skill: {name: xxx, description: xxx}
        fm_match = re.match(r'^---\n(.*?)\n---\n', content, re.DOTALL)
        if fm_match:
            fm_yaml = yaml.safe_load(fm_match.group(1))
            fm_yaml = fm_yaml if isinstance(fm_yaml, dict) else {}
            
            # 尝试嵌套格式 skill: {...}
            if 'skill' in fm_yaml:
                self.name = fm_yaml['skill'].get('name', '')
                self.version = str(fm_yaml['skill'].get('version', '1.0'))
                self.description = fm_yaml['skill'].get('description', '')
                self.platform = fm_yaml['skill'].get('platform', '')
            # 尝试直接格式 {name: ..., description: ...}
            else:
                self.name = fm_yaml.get('name', '')
                self.version = str(fm_yaml.get('version', '1.0'))
                self.description = fm_yaml.get('description', '')
                # 使用目录名作为默认平台
                self.platform = fm_yaml.get('platform', os.path.basename(os.path.dirname(path)))
            
            # 解析 triggers
            triggers = fm_yaml.get('triggers', [])
            if isinstance(triggers, list):
                self.triggers = [
                    SkillTrigger(keywords=t if isinstance(t, list) else [t])
                    for t in triggers
                ]
            elif isinstance(triggers, dict):
                for key, val in triggers.items():
                    self.triggers.append(SkillTrigger(
                        keywords=val if isinstance(val, list) else [val],
                        patterns=[key]
                    ))

        # SKILL.md is intentionally natural-language guidance plus identity
        # metadata. Markdown headings/tables never become executable Tools.

    def _load_workflows(self, workflows: Any) -> None:
        """Load workflow declarations from a dedicated workflow contract."""
        if not isinstance(workflows, dict):
            return
        for name, raw in workflows.items():
            if isinstance(raw, list):
                raw = {"tools": raw}
            if not isinstance(raw, dict):
                continue
            raw_steps = raw.get("steps")
            if raw_steps is None:
                raw_steps = raw.get("tools", [])
            if not isinstance(raw_steps, list):
                raw_steps = []
            steps = self._parse_workflow_steps(raw_steps, self.platform or None)
            raw_platforms = raw.get("platforms", {})
            if isinstance(raw_platforms, dict):
                for platform, names in raw_platforms.items():
                    if isinstance(names, str):
                        names = [names]
                    if isinstance(names, list):
                        steps.extend(self._parse_workflow_steps(names, str(platform)))
            workflow = SkillWorkflow(
                name=str(name),
                steps=tuple(steps),
                description=str(raw.get("description", "")),
            )
            errors = workflow.validation_errors()
            if errors:
                raise ValueError("; ".join(errors))
            self.workflows[str(name)] = workflow

    def _load_workflow_file(self, skill_md_path: str) -> None:
        """Load an optional special-case DAG beside ``SKILL.md``.

        This is not part of normal Tool discovery. A Skill without this file
        is the normal case and is driven by its natural-language SOP and
        registered self-described Tools.
        """
        skill_dir = Path(skill_md_path).parent
        for filename in ("workflow.yaml", "workflows.yaml"):
            workflow_path = skill_dir / filename
            if not workflow_path.exists():
                continue
            try:
                with workflow_path.open("r", encoding="utf-8") as file:
                    raw = yaml.safe_load(file) or {}
            except (OSError, yaml.YAMLError) as exc:
                raise ValueError(f"Invalid Skill workflow contract {workflow_path}: {exc}") from exc
            if isinstance(raw, dict) and isinstance(raw.get("workflows"), dict):
                raw = raw["workflows"]
            self.workflows = {}
            self._load_workflows(raw)
            return

    @staticmethod
    def _parse_workflow_steps(raw_steps: list[Any], platform: Optional[str]) -> list[SkillWorkflowStep]:
        parsed: list[SkillWorkflowStep] = []
        for index, item in enumerate(raw_steps):
            if isinstance(item, str):
                tool_name = item
                spec: dict[str, Any] = {}
            elif isinstance(item, dict) and item.get("tool"):
                tool_name = str(item["tool"])
                spec = item
            else:
                continue
            default_prefix = platform or "step"
            step_id = str(
                spec.get("id") or f"{default_prefix}_step_{len(parsed) + 1}"
            )
            depends_on = spec.get("depends_on", spec.get("after", [])) or []
            if isinstance(depends_on, str):
                depends_on = [depends_on]
            required_inputs = spec.get("required_inputs", spec.get("requires", [])) or []
            if isinstance(required_inputs, str):
                required_inputs = [required_inputs]
            when = spec.get("when", {}) or {}
            input_mapping = spec.get("input_mapping", spec.get("input_map", {})) or {}
            output_mapping = spec.get("output_mapping", spec.get("output_map", {})) or {}
            parsed.append(SkillWorkflowStep(
                id=step_id,
                tool=tool_name,
                platform=str(spec.get("platform") or platform or "") or None,
                depends_on=tuple(str(value) for value in depends_on),
                when=dict(when) if isinstance(when, dict) else {},
                required_inputs=tuple(str(value) for value in required_inputs),
                input_mapping={str(key): str(value) for key, value in input_mapping.items()}
                if isinstance(input_mapping, dict) else {},
                output_mapping={str(key): str(value) for key, value in output_mapping.items()}
                if isinstance(output_mapping, dict) else {},
                on_error=str(spec.get("on_error", "stop")),
                requires_confirmation=bool(spec.get("requires_confirmation", spec.get("confirmation", False))),
            ))
        return parsed
    
    def _load_contract_yaml(self, path: str) -> None:
        """加载 contract.yaml"""
        with open(path, 'r', encoding='utf-8') as f:
            self.raw_yaml = yaml.safe_load(f) or {}
        self.version = str(self.raw_yaml.get('version', self.version))
        
        # 合并到 capabilities
        tools = self.raw_yaml.get('tools', {})
        for name, spec in tools.items():
            self.capabilities[name] = SkillCapability(
                name=name,
                description=spec.get('description', name),
                required_params=spec.get('required', []),
                optional_params=spec.get('optional', []),
                risk_level=spec.get('risk', 'low'),
                effect=spec.get('effect', 'read'),
                input_schema=spec.get('input_schema', {}) or {},
                live_support=bool(spec.get('live_support', True)),
                required_permissions=list(spec.get('required_permissions', []) or []),
                action=str(spec.get('action', '') or ''),
                resource_type=str(spec.get('resource_type', '') or ''),
                parent_resource_type=spec.get('parent_resource_type'),
                intent_types=list(spec.get('intent_types', []) or []),
            )
    
    def _load_tools_from_directory(self, tools_dir: str) -> None:
        """
        从 tools/ 目录加载工具定义。
        每个 .yaml/.json 文件定义一个 ToolDefinition。
        """
        for filename in os.listdir(tools_dir):
            if not filename.endswith(('.yaml', '.yml', '.json')):
                continue
            filepath = os.path.join(tools_dir, filename)
            with open(filepath, 'r', encoding='utf-8') as f:
                if filename.endswith('.json'):
                    import json as json_mod
                    spec = json_mod.load(f)
                else:
                    spec = yaml.safe_load(f)
            
            if spec and 'name' in spec:
                tool_name = spec['name']
                schema = spec.get('input_schema', {})
                self.capabilities[tool_name] = SkillCapability(
                    name=tool_name,
                    description=spec.get('description', ''),
                    required_params=schema.get('required', []),
                    optional_params=[
                        name for name in schema.get('properties', {})
                        if name not in schema.get('required', [])
                    ],
                    risk_level=spec.get('risk_level', 'low'),
                    effect=spec.get('effect_class', 'read'),
                    input_schema=schema,
                    live_support=bool(spec.get('live_support', True)),
                    required_permissions=list(spec.get('required_permissions', []) or []),
                    action=str(spec.get('action', '') or ''),
                    resource_type=str(spec.get('resource_type', '') or ''),
                    parent_resource_type=spec.get('parent_resource_type'),
                    intent_types=list(spec.get('intent_types', []) or []),
                )


# ─── Skill 实现 ────────────────────────────────────────────────

class BaseSkill(Skill):
    """
    Skill 基类 - 对应 Go 的 skill.Contract + loader
    
    所有平台 Skill 继承此类，实现工具注册和执行。
    """
    
    def __init__(self, contract: SkillContract):
        self._contract = contract
        self._handlers: dict[str, ToolHandler] = {}
    
    @property
    def name(self) -> str:
        return self._contract.name
    
    @property
    def platform(self) -> str:
        return self._contract.platform
    
    @property
    def description(self) -> str:
        return self._contract.description

    @property
    def version(self) -> str:
        return self._contract.version

    @property
    def expert_knowledge(self) -> dict[str, str]:
        return self._contract.expert_knowledge

    @property
    def tools(self) -> list[ToolDefinition]:
        """Declarative view used by the canonical loader and selector."""
        return self.get_tools()
    
    def register_handler(self, tool_name: str, handler: ToolHandler) -> None:
        """注册工具处理器"""
        self._handlers[tool_name] = handler
    
    def get_tools(self) -> list[ToolDefinition]:
        """返回此 Skill 的所有工具定义"""
        tools = []
        for name, cap in self._contract.capabilities.items():
            declared_schema = cap.input_schema if isinstance(cap.input_schema, dict) else {}
            schema = ToolSchema(
                type=declared_schema.get("type", "object"),
                required=list(declared_schema.get("required", cap.required_params) or []),
                properties=(
                    declared_schema.get("properties")
                    or self._build_properties(name)
                ),
                provider_required=list(declared_schema.get("provider_required", []) or []),
                provider_any_of=[
                    list(group) for group in (declared_schema.get("provider_any_of", []) or [])
                ],
                conditional_rules=list(declared_schema.get("conditional_rules", []) or []),
                additional_properties=bool(
                    declared_schema.get(
                        "additional_properties",
                        declared_schema.get("additionalProperties", False),
                    )
                ),
            )
            tools.append(ToolDefinition(
                name=name,
                skill=self.name,
                platform=self.platform,
                description=cap.description,
                input_schema=schema,
                risk_level=self._parse_risk(cap.risk_level),
                effect_class=self._parse_effect(cap.effect),
                live_support=cap.live_support,
                required_permissions=list(cap.required_permissions),
                action=cap.action,
                resource_type=cap.resource_type,
                parent_resource_type=cap.parent_resource_type,
                intent_types=list(cap.intent_types),
            ))
        return tools
    
    def get_tool_handler(self, tool_name: str) -> Optional[ToolHandler]:
        """返回指定工具的执行器"""
        return self._handlers.get(tool_name)

    def get_workflows(self) -> dict[str, SkillWorkflow]:
        return dict(self._contract.workflows)

    def get_workflow_mappings(self) -> dict[str, dict[str, list[str]]]:
        """Expose only the Skill's declarative orchestration plan."""
        result: dict[str, dict[str, list[str]]] = {}
        for name, workflow in self._contract.workflows.items():
            mapping = workflow.tool_mapping()
            if "" in mapping and self.platform:
                mapping = {self.platform: list(mapping[""])}
            if mapping:
                result[name] = mapping
        return result
    
    def _build_properties(self, tool_name: str) -> dict[str, Any]:
        """构建工具输入参数的 JSON Schema properties"""
        cap = self._contract.capabilities.get(tool_name)
        if not cap:
            return {}
        
        properties = {}
        for param in cap.required_params:
            properties[param] = {"type": "string", "description": f"Required: {param}"}
        for param in cap.optional_params:
            properties[param] = {"type": "string", "description": f"Optional: {param}"}
        
        # 通用字段
        properties["creative_materials"] = {
            "type": "array",
            "description": "投放素材列表",
        }
        properties["budget"] = {
            "type": "number",
            "description": "每日预算（元）",
        }
        return properties
    
    def _parse_risk(self, level: str) -> 'RiskLevel':
        from ..core.interfaces import RiskLevel
        mapping = {
            "low": RiskLevel.LOW,
            "medium": RiskLevel.MEDIUM,
            "high": RiskLevel.HIGH,
            "critical": RiskLevel.CRITICAL,
        }
        return mapping.get(level, RiskLevel.LOW)
    
    def _parse_effect(self, effect: str) -> 'ToolEffect':
        from ..core.interfaces import ToolEffect
        mapping = {
            "read": ToolEffect.READ,
            "write": ToolEffect.WRITE,
            "external_write": ToolEffect.EXTERNAL_WRITE,
        }
        return mapping.get(effect, ToolEffect.READ)


class SkillLoader:
    """
    Skill 加载器 - 对应 Go 的 skill.Loader
    
    从文件系统加载 SKILL.md + YAML 合约，实例化 Skill 对象。
    """
    
    def __init__(self, skill_roots: list[str] = None):
        default_root = Path(__file__).resolve().parent.parent / "skills"
        if isinstance(skill_roots, (str, Path)):
            skill_roots = [skill_roots]
        self._roots = [Path(root) for root in (skill_roots or [default_root])]
        self._skills: dict[str, Skill] = {}
    
    def add_root(self, root: str) -> None:
        """添加 Skill 根目录"""
        root_path = Path(root)
        if root_path not in self._roots:
            self._roots.append(root_path)
    
    def load_all(self) -> dict[str, Skill]:
        """加载所有根目录下的 Skills"""
        for root in self._roots:
            self._load_from_root(root)
        return self._skills
    
    def _load_from_root(self, root: str) -> None:
        """从根目录递归加载 Skills"""
        root_path = Path(root)
        if not root_path.is_dir():
            return

        for skill_file in root_path.rglob("SKILL.md"):
            self._load_single_skill(str(skill_file.parent))
    
    def _is_skill_dir(self, path: str) -> bool:
        """判断是否为 Skill 目录（必须有 SKILL.md）"""
        return os.path.exists(os.path.join(path, "SKILL.md"))
    
    def _load_single_skill(self, skill_dir: str) -> None:
        """加载单个 Skill"""
        contract = SkillContract(skill_dir).load()
        if not contract.name:
            return  # 跳过无名称的目录
        
        skill = BaseSkill(contract)
        self._skills[contract.name] = skill
    
    def get(self, name: str) -> Optional[Skill]:
        """获取已加载的 Skill"""
        return self._skills.get(name)

    def get_skill(self, name: str) -> Optional[Skill]:
        """获取已加载的 Skill（显式命名入口）"""
        return self.get(name)
    
    def get_by_platform(self, platform: str) -> list[Skill]:
        """获取某平台的所有 Skills"""
        return [s for s in self._skills.values() if s.platform == platform]

    def get_tools_by_platform(self, platform: str) -> list[ToolDefinition]:
        """获取某平台的所有工具"""
        return [tool for skill in self.get_by_platform(platform) for tool in skill.get_tools()]
