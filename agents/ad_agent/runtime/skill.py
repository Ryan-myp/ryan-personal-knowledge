"""
runtime/skill.py - Skill 加载与执行

借鉴 DAP Agent internal/skill/loader.go
每个平台 Skill 是一个独立的工具集合。SKILL.md 提供自然语言专家上下文；
可执行 Tool 由 Capability/plugin 自注册并携带自己的结构化元数据。
"""

from __future__ import annotations

import os
import re
import logging
import math
import yaml
from dataclasses import dataclass, field
from typing import Any, Optional, Union
from pathlib import Path
from ..core.interfaces import (
    RiskLevel, ReplayPolicy, ToolDefinition, ToolEffect, ToolHandler, ToolSchema, Skill,
)
from ..core.platform import normalize_platform
from ..core.plugins import normalize_plugin_version


logger = logging.getLogger(__name__)


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
    # Declarative Skill contracts must opt in explicitly before a Tool can
    # participate in a future live-write approval.
    live_support: bool = False
    required_permissions: list[str] = field(default_factory=list)
    action: str = ""
    resource_type: str = ""
    parent_resource_type: Optional[str] = None
    resource_id_field: Optional[str] = None
    parent_resource_id_field: Optional[str] = None
    readback_tool: Optional[str] = None
    intent_types: list[str] = field(default_factory=list)
    intent_aliases: list[str] = field(default_factory=list)
    replay_policy: str = ""
    traits: list[str] = field(default_factory=list)
    timeout_seconds: float = 30.0
    max_output_bytes: int = 1_000_000
    contract_version: str = "1"
    provider_api_version: Optional[str] = None
    result_items_key: Optional[str] = None
    result_id_fields: list[str] = field(default_factory=list)
    related_resource_type: Optional[str] = None
    related_resource_id_fields: list[str] = field(default_factory=list)


class SkillContract:
    """
    Skill 合约定义 - 对应 Go 的 skill.Contract
    
    从 SKILL.md frontmatter + YAML 合约文件加载。
    """
    
    def __init__(self, skill_dir: str):
        self.skill_dir = skill_dir
        self.name: str = ""
        self.version: str = "1.0.0"
        self.description: str = ""
        self.platform: str = ""
        self.platform_aliases: list[str] = []
        self.triggers: list[SkillTrigger] = []
        self.capabilities: dict[str, SkillCapability] = {}
        self.references: dict[str, str] = {}  # ref_name -> file_path
        self.reference_documents: dict[str, str] = {}
        self.expert_knowledge: dict[str, str] = {}
        self.raw_md: str = ""
        self.raw_yaml: dict = {}
        # Business files are context-only declarations.  They deliberately
        # use a ``business:`` frontmatter block instead of the Skill identity
        # contract and must not be reported as malformed executable Skills.
        self.context_only: bool = False

    @staticmethod
    def _string_list(value: Any, field_name: str) -> list[str]:
        """Parse a scalar-or-list string field without coercing bad input."""
        if value is None:
            return []
        values = [value] if isinstance(value, str) else value
        if not isinstance(values, list):
            raise ValueError(f"Skill {field_name} must be a string or list of strings")
        result: list[str] = []
        for item in values:
            if not isinstance(item, str) or not item.strip():
                raise ValueError(f"Skill {field_name} must contain non-empty strings")
            result.append(item.strip())
        return result

    @staticmethod
    def _mapping(value: Any, field_name: str) -> dict[str, Any]:
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise ValueError(f"Skill {field_name} must be an object")
        return value

    @classmethod
    def _input_schema(cls, value: Any, field_name: str) -> dict[str, Any]:
        """Validate the JSON-Schema subset accepted by ToolSchema."""
        schema = cls._mapping(value, field_name)
        if schema.get("type", "object") != "object":
            raise ValueError(f"Skill {field_name}.type must be 'object'")
        required = schema.get("required", []) or []
        if not isinstance(required, list) or not all(
            isinstance(item, str) and item.strip() for item in required
        ):
            raise ValueError(f"Skill {field_name}.required must be a list of strings")
        properties = schema.get("properties", {}) or {}
        if not isinstance(properties, dict):
            raise ValueError(f"Skill {field_name}.properties must be an object")
        for property_name, property_schema in properties.items():
            if not isinstance(property_name, str) or not property_name.strip():
                raise ValueError(f"Skill {field_name}.properties has an invalid field name")
            if not isinstance(property_schema, dict):
                raise ValueError(
                    f"Skill {field_name}.properties.{property_name} must be an object"
                )
        provider_required = schema.get("provider_required", []) or []
        if not isinstance(provider_required, list) or not all(
            isinstance(item, str) and item.strip() for item in provider_required
        ):
            raise ValueError(
                f"Skill {field_name}.provider_required must be a list of strings"
            )
        provider_any_of = schema.get("provider_any_of", []) or []
        if not isinstance(provider_any_of, list) or any(
            not isinstance(group, list)
            or not group
            or not all(isinstance(item, str) and item.strip() for item in group)
            for group in provider_any_of
        ):
            raise ValueError(
                f"Skill {field_name}.provider_any_of must be a list of string lists"
            )
        provider_exactly_one_of = schema.get("provider_exactly_one_of", []) or []
        if not isinstance(provider_exactly_one_of, list) or any(
            not isinstance(group, list)
            or not group
            or not all(isinstance(item, str) and item.strip() for item in group)
            for group in provider_exactly_one_of
        ):
            raise ValueError(
                f"Skill {field_name}.provider_exactly_one_of must be a list of string lists"
            )
        conditional_rules = schema.get("conditional_rules", []) or []
        if not isinstance(conditional_rules, list) or any(
            not isinstance(rule, dict) for rule in conditional_rules
        ):
            raise ValueError(
                f"Skill {field_name}.conditional_rules must be a list of objects"
            )
        for additional_name in ("additional_properties", "additionalProperties"):
            if additional_name in schema and not isinstance(schema[additional_name], bool):
                raise ValueError(f"Skill {field_name}.{additional_name} must be boolean")
        return schema

    @classmethod
    def _capability(cls, name: Any, spec: Any, source: str) -> SkillCapability:
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"Skill tool name in {source} must be a non-empty string")
        if not isinstance(spec, dict):
            raise ValueError(f"Skill tool {name} in {source} must be an object")
        description = spec.get("description", name)
        if not isinstance(description, str):
            raise ValueError(f"Skill tool {name}.description must be a string")
        required_params = cls._string_list(
            spec.get("required", []), f"tool {name}.required"
        )
        optional_params = cls._string_list(
            spec.get("optional", []), f"tool {name}.optional"
        )
        if set(required_params) & set(optional_params):
            raise ValueError(f"Skill tool {name}.required and optional overlap")
        risk_level = spec.get("risk", spec.get("risk_level", "low"))
        effect = spec.get("effect", spec.get("effect_class", "read"))
        if risk_level not in {"low", "medium", "high", "critical"}:
            raise ValueError(f"Skill tool {name} has invalid risk level: {risk_level}")
        if effect not in {"read", "write", "external_write"}:
            raise ValueError(f"Skill tool {name} has invalid effect: {effect}")
        input_schema = cls._input_schema(
            spec.get("input_schema", {}), f"tool {name}.input_schema"
        )
        live_support = spec.get("live_support", False)
        if not isinstance(live_support, bool):
            raise ValueError(f"Skill tool {name}.live_support must be boolean")
        replay_policy = spec.get("replay_policy", "") or ""
        if replay_policy not in {"", "safe", "unsafe"}:
            raise ValueError(f"Skill tool {name} has invalid replay_policy: {replay_policy}")
        traits = cls._string_list(spec.get("traits", []), f"tool {name}.traits")
        permissions = cls._string_list(
            spec.get("required_permissions", []), f"tool {name}.required_permissions"
        )
        timeout_seconds = spec.get("timeout_seconds", 30.0)
        max_output_bytes = spec.get("max_output_bytes", 1_000_000)
        if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float)):
            raise ValueError(f"Skill tool {name}.timeout_seconds must be a number")
        if not math.isfinite(float(timeout_seconds)) or float(timeout_seconds) <= 0:
            raise ValueError(f"Skill tool {name}.timeout_seconds must be positive and finite")
        if isinstance(max_output_bytes, bool) or not isinstance(max_output_bytes, int):
            raise ValueError(f"Skill tool {name}.max_output_bytes must be an integer")
        if max_output_bytes <= 0:
            raise ValueError(f"Skill tool {name}.max_output_bytes must be positive")
        contract_version = spec.get("contract_version", "1")
        if not isinstance(contract_version, (str, int, float)) or isinstance(contract_version, bool):
            raise ValueError(f"Skill tool {name}.contract_version must be scalar")
        provider_api_version = spec.get("provider_api_version")
        if provider_api_version is not None and (
            not isinstance(provider_api_version, (str, int, float))
            or isinstance(provider_api_version, bool)
        ):
            raise ValueError(f"Skill tool {name}.provider_api_version must be scalar")
        def optional_string(field_name: str) -> Optional[str]:
            value = spec.get(field_name)
            if value is None or value == "":
                return None
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"Skill tool {name}.{field_name} must be a string")
            return value.strip()

        result_items_key = optional_string("result_items_key")
        result_id_fields = cls._string_list(
            spec.get("result_id_fields", []), f"tool {name}.result_id_fields"
        )
        related_resource_type = optional_string("related_resource_type")
        related_resource_id_fields = cls._string_list(
            spec.get("related_resource_id_fields", []),
            f"tool {name}.related_resource_id_fields",
        )

        return SkillCapability(
            name=name.strip(), description=description,
            required_params=required_params, optional_params=optional_params,
            risk_level=risk_level, effect=effect, input_schema=input_schema,
            live_support=live_support, required_permissions=permissions,
            action=optional_string("action") or "",
            resource_type=optional_string("resource_type") or "",
            parent_resource_type=optional_string("parent_resource_type"),
            resource_id_field=optional_string("resource_id_field"),
            parent_resource_id_field=optional_string("parent_resource_id_field"),
            readback_tool=optional_string("readback_tool"),
            intent_types=cls._string_list(
                spec.get("intent_types", []), f"tool {name}.intent_types"
            ),
            intent_aliases=cls._string_list(
                spec.get("intent_aliases", []), f"tool {name}.intent_aliases"
            ),
            replay_policy=replay_policy, traits=traits,
            timeout_seconds=float(timeout_seconds), max_output_bytes=max_output_bytes,
            contract_version=str(contract_version),
            provider_api_version=(
                str(provider_api_version) if provider_api_version is not None else None
            ),
            result_items_key=result_items_key,
            result_id_fields=result_id_fields,
            related_resource_type=related_resource_type,
            related_resource_id_fields=related_resource_id_fields,
        )
    
    def load(self) -> "SkillContract":
        """从文件系统加载 Skill 合约"""
        # 1. 加载 SKILL.md
        skill_md_path = os.path.join(self.skill_dir, "SKILL.md")
        if os.path.exists(skill_md_path):
            self._load_skill_md(skill_md_path)
            if self.context_only:
                return self
        
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

        # Standard Agent Skills commonly keep detailed guidance under
        # references/. Preserve text references as advisory data; scripts and
        # assets remain package files and are never imported by the Runtime.
        references_dir = Path(self.skill_dir) / "references"
        if references_dir.is_dir():
            for reference_path in sorted(references_dir.rglob("*")):
                if not reference_path.is_file() or reference_path.suffix.lower() not in {
                    ".md", ".markdown", ".txt", ".yaml", ".yml", ".json",
                }:
                    continue
                try:
                    content = reference_path.read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError):
                    continue
                relative = str(reference_path.relative_to(self.skill_dir))
                self.reference_documents[relative] = content[:100_000]

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
            if not isinstance(fm_yaml, dict):
                raise ValueError("Skill frontmatter must be an object")
            nested = fm_yaml.get("skill")
            if nested is not None and not isinstance(nested, dict):
                raise ValueError("Skill frontmatter.skill must be an object")
            metadata = nested if isinstance(nested, dict) else fm_yaml

            # ``businesses/*/SKILL.md`` is a policy/context package consumed by
            # the Skill-owned policy adapter. It is intentionally not a normal
            # executable Skill and therefore has no Tool registration metadata.
            if not nested and isinstance(fm_yaml.get("business"), dict):
                self.context_only = True
                self.raw_yaml = fm_yaml
                return

            name = metadata.get("name", "")
            if not isinstance(name, str) or not name.strip():
                raise ValueError("Skill frontmatter requires a non-empty name")
            description = metadata.get("description", "")
            if not isinstance(description, str):
                raise ValueError("Skill frontmatter.description must be a string")
            platform = metadata.get(
                "platform", os.path.basename(os.path.dirname(path))
            )
            if not isinstance(platform, str) or not platform.strip():
                raise ValueError("Skill frontmatter.platform must be a non-empty string")
            version = metadata.get("version", "1.0.0")
            if not isinstance(version, (str, int, float)) or isinstance(version, bool):
                raise ValueError("Skill frontmatter.version must be scalar")

            self.name = name.strip()
            self.version = normalize_plugin_version(version)
            self.description = description
            self.platform = platform.strip().lower()

            # Metadata belongs either at the root or under ``skill``. Root
            # values remain accepted for existing Skills; nested values win.
            aliases = metadata.get("aliases", fm_yaml.get("aliases", []))
            self.platform_aliases = [
                alias.lower() for alias in self._string_list(aliases, "aliases")
            ]
            triggers = metadata.get("triggers", fm_yaml.get("triggers", []))
            self.triggers = self._parse_triggers(triggers)

        # SKILL.md is intentionally natural-language guidance plus identity
        # metadata. Markdown headings/tables never become executable Tools.

    @classmethod
    def _parse_triggers(cls, triggers: Any) -> list[SkillTrigger]:
        """Parse optional trigger metadata while keeping it non-executable."""
        if triggers is None:
            return []
        if isinstance(triggers, str):
            return [SkillTrigger(keywords=[triggers.strip()])]
        if isinstance(triggers, list):
            result: list[SkillTrigger] = []
            for item in triggers:
                if isinstance(item, str):
                    result.append(SkillTrigger(keywords=[item.strip()]))
                elif isinstance(item, list):
                    result.append(SkillTrigger(keywords=cls._string_list(item, "triggers")))
                elif isinstance(item, dict):
                    keywords = cls._string_list(item.get("keywords", []), "trigger.keywords")
                    patterns = cls._string_list(item.get("patterns", []), "trigger.patterns")
                    if not keywords and not patterns:
                        raise ValueError("Skill trigger must define keywords or patterns")
                    result.append(SkillTrigger(keywords=keywords, patterns=patterns))
                else:
                    raise ValueError("Skill triggers must contain strings, lists or objects")
            return result
        if isinstance(triggers, dict):
            result = []
            for pattern, keywords in triggers.items():
                if not isinstance(pattern, str) or not pattern.strip():
                    raise ValueError("Skill trigger pattern must be a non-empty string")
                result.append(SkillTrigger(
                    keywords=cls._string_list(keywords, "trigger.keywords"),
                    patterns=[pattern.strip()],
                ))
            return result
        raise ValueError("Skill triggers must be a string, list or object")

    def _load_contract_yaml(self, path: str) -> None:
        """加载 contract.yaml"""
        with open(path, 'r', encoding='utf-8') as f:
            self.raw_yaml = yaml.safe_load(f) or {}
        if not isinstance(self.raw_yaml, dict):
            raise ValueError("Skill contract must be an object")
        self.version = normalize_plugin_version(
            self.raw_yaml.get("version", self.version)
        )
        
        # 合并到 capabilities
        tools = self.raw_yaml.get('tools', {})
        if not isinstance(tools, dict):
            raise ValueError("Skill contract tools must be an object")
        for name, spec in tools.items():
            if name in self.capabilities:
                raise ValueError(f"Skill tool {name} is declared more than once")
            self.capabilities[name] = self._capability(name, spec, path)
    
    def _load_tools_from_directory(self, tools_dir: str) -> None:
        """
        从 tools/ 目录加载工具定义。
        每个 .yaml/.json 文件定义一个 ToolDefinition。
        """
        for filename in sorted(os.listdir(tools_dir)):
            if not filename.endswith(('.yaml', '.yml', '.json')):
                continue
            filepath = os.path.join(tools_dir, filename)
            with open(filepath, 'r', encoding='utf-8') as f:
                if filename.endswith('.json'):
                    import json as json_mod
                    spec = json_mod.load(f)
                else:
                    spec = yaml.safe_load(f)
            
            if not isinstance(spec, dict) or not spec.get("name"):
                raise ValueError(f"Skill tool file {filepath} must define a name")
            tool_name = spec["name"]
            if tool_name in self.capabilities:
                raise ValueError(f"Skill tool {tool_name} is declared more than once")
            normalized = dict(spec)
            if "risk_level" in normalized and "risk" not in normalized:
                normalized["risk"] = normalized["risk_level"]
            if "effect_class" in normalized and "effect" not in normalized:
                normalized["effect"] = normalized["effect_class"]
            schema = self._input_schema(
                normalized.get("input_schema", {}),
                f"tool {tool_name}.input_schema",
            )
            normalized["input_schema"] = schema
            normalized.setdefault("required", schema.get("required", []))
            normalized.setdefault(
                "optional",
                [
                    field_name for field_name in schema.get("properties", {})
                    if field_name not in schema.get("required", [])
                ],
            )
            self.capabilities[tool_name] = self._capability(
                tool_name, normalized, filepath
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
    def raw_markdown(self) -> str:
        """Return the natural-language body for bounded Agent context."""
        return self._contract.raw_md

    @property
    def reference_documents(self) -> dict[str, str]:
        """Return text references; package scripts/assets stay non-executable."""
        return dict(self._contract.reference_documents)

    @property
    def version(self) -> str:
        return self._contract.version

    @property
    def platform_aliases(self) -> list[str]:
        return list(self._contract.platform_aliases)

    @property
    def triggers(self) -> list[SkillTrigger]:
        """Expose declarative context triggers to the bounded selector."""
        return list(self._contract.triggers)

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
                provider_exactly_one_of=[
                    list(group) for group in (
                        declared_schema.get("provider_exactly_one_of", []) or []
                    )
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
                resource_id_field=cap.resource_id_field,
                parent_resource_id_field=cap.parent_resource_id_field,
                readback_tool=cap.readback_tool,
                intent_types=list(cap.intent_types),
                intent_aliases=list(cap.intent_aliases),
                replay_policy=self._parse_replay_policy(cap.replay_policy, cap.effect),
                traits=list(cap.traits),
                timeout_seconds=cap.timeout_seconds,
                max_output_bytes=cap.max_output_bytes,
                contract_version=cap.contract_version,
                provider_api_version=cap.provider_api_version,
                result_items_key=cap.result_items_key,
                result_id_fields=list(cap.result_id_fields),
                related_resource_type=cap.related_resource_type,
                related_resource_id_fields=list(cap.related_resource_id_fields),
            ))
        return tools
    
    def get_tool_handler(self, tool_name: str) -> Optional[ToolHandler]:
        """返回指定工具的执行器"""
        return self._handlers.get(tool_name)

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
        mapping = {
            "low": RiskLevel.LOW,
            "medium": RiskLevel.MEDIUM,
            "high": RiskLevel.HIGH,
            "critical": RiskLevel.CRITICAL,
        }
        return mapping.get(level, RiskLevel.LOW)
    
    def _parse_effect(self, effect: str) -> 'ToolEffect':
        mapping = {
            "read": ToolEffect.READ,
            "write": ToolEffect.WRITE,
            "external_write": ToolEffect.EXTERNAL_WRITE,
        }
        return mapping.get(effect, ToolEffect.READ)

    @staticmethod
    def _parse_replay_policy(policy: str, effect: str) -> ReplayPolicy:
        """Make declarative write Tools unsafe to replay by default."""
        value = str(policy or "").strip().lower()
        if value == ReplayPolicy.SAFE.value:
            return ReplayPolicy.SAFE
        if value == ReplayPolicy.UNSAFE.value:
            return ReplayPolicy.UNSAFE
        effect_value = str(effect or "").strip().lower()
        return ReplayPolicy.UNSAFE if effect_value != ToolEffect.READ.value else ReplayPolicy.SAFE


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
        self._errors: dict[str, str] = {}
    
    def add_root(self, root: str) -> None:
        """添加 Skill 根目录"""
        root_path = Path(root)
        if root_path not in self._roots:
            self._roots.append(root_path)
    
    def load_all(self) -> dict[str, Skill]:
        """加载所有根目录下的 Skills"""
        for root in self._roots:
            self._load_from_root(root)
        return self.list_all()

    @property
    def roots(self) -> tuple[Path, ...]:
        """Return the configured discovery roots as an immutable snapshot.

        Runtime and selectors should not depend on the loader's private index
        or mutate its roots in place.  The loader remains the owner of both
        discovery configuration and the loaded Skill cache.
        """
        return tuple(self._roots)

    def list_all(self) -> dict[str, Skill]:
        """Return a snapshot of all successfully loaded Skills."""
        return dict(self._skills)

    def load_skill_dir(self, skill_dir: str | Path) -> Optional[Skill]:
        """Load one standard Skill directory through the public loader seam.

        The operation is idempotent for the same Skill name and source path;
        malformed packages still raise so callers that explicitly request a
        package can report the validation error.
        """
        self._load_single_skill(str(skill_dir))
        directory = str(Path(skill_dir).expanduser().resolve())
        for skill in self._skills.values():
            if str(getattr(skill, "skill_dir", "")) == directory:
                return skill
        return None

    def unload(self, name: str) -> bool:
        """Unload a Skill by name and report whether it was present."""
        return self._skills.pop(str(name), None) is not None

    def iter_skill_dirs(self, roots: Optional[list[Union[str, Path]]] = None) -> list[Path]:
        """Return every standard Skill directory discovered under the roots.

        A standard Agent Skill is identified by the presence of ``SKILL.md``;
        its parent directory may be the root itself or any nested directory.
        Keeping this discovery rule here prevents Runtime callers from
        assuming a repository-specific layout such as ``channels/`` or
        ``businesses/``.  The returned paths are deterministic and deduplicated
        when multiple roots overlap.
        """
        discovered: set[Path] = set()
        scan_roots = self._roots if roots is None else [Path(root) for root in roots]
        for raw_root in scan_roots:
            root = Path(raw_root)
            if not root.is_dir():
                continue
            for skill_file in root.rglob("SKILL.md"):
                if skill_file.is_file():
                    discovered.add(skill_file.parent.resolve())
        return sorted(discovered, key=lambda path: str(path))

    @property
    def errors(self) -> dict[str, str]:
        """Return rejected Skill paths and reasons for diagnostics."""
        return dict(self._errors)
    
    def _load_from_root(self, root: str) -> None:
        """从根目录递归加载 Skills"""
        root_path = Path(root)
        if not root_path.is_dir():
            return

        for skill_file in sorted(root_path.rglob("SKILL.md")):
            skill_dir = str(skill_file.parent)
            try:
                self._load_single_skill(skill_dir)
                self._errors.pop(skill_dir, None)
            except Exception as exc:
                # One malformed/third-party Skill must not prevent the Runtime
                # from loading the remaining trusted Skills. Direct callers
                # of _load_single_skill still receive the exception.
                self._errors[skill_dir] = str(exc)
                logger.warning("拒绝加载 Skill %s: %s", skill_dir, exc)
    
    def _is_skill_dir(self, path: str) -> bool:
        """判断是否为 Skill 目录（必须有 SKILL.md）"""
        return os.path.exists(os.path.join(path, "SKILL.md"))
    
    def _load_single_skill(self, skill_dir: str) -> None:
        """加载单个 Skill"""
        # Roots can be mounted through different spellings (for example an
        # absolute path during Runtime construction and a relative path from
        # an embedding application's reload call).  Compare canonical paths
        # so the same standard Skill remains reloadable and is not reported
        # as a duplicate package.
        canonical_dir = str(Path(skill_dir).expanduser().resolve())
        contract = SkillContract(canonical_dir).load()
        if contract.context_only:
            return
        if not contract.name:
            return  # 跳过无名称的目录

        skill = BaseSkill(contract)
        existing = self._skills.get(contract.name)
        existing_dir = getattr(existing, "skill_dir", None)
        if existing is not None and existing_dir:
            existing_canonical = str(Path(existing_dir).expanduser().resolve())
        else:
            existing_canonical = existing_dir
        if existing is not None and existing_canonical != canonical_dir:
            raise ValueError(
                f"duplicate Skill name '{contract.name}' in {canonical_dir}"
            )
        # Keep the source directory on the loaded object for deterministic
        # duplicate detection when multiple roots are configured.
        setattr(skill, "skill_dir", canonical_dir)
        self._skills[contract.name] = skill
    
    def get(self, name: str) -> Optional[Skill]:
        """获取已加载的 Skill"""
        return self._skills.get(name)

    def get_skill(self, name: str) -> Optional[Skill]:
        """获取已加载的 Skill（显式命名入口）"""
        return self.get(name)
    
    def get_by_platform(self, platform: str) -> list[Skill]:
        """获取某平台的所有 Skills"""
        normalized = normalize_platform(platform)
        return [
            s for s in self._skills.values()
            if normalize_platform(s.platform) == normalized
        ]

    def get_tools_by_platform(self, platform: str) -> list[ToolDefinition]:
        """获取某平台的所有工具"""
        return [tool for skill in self.get_by_platform(platform) for tool in skill.get_tools()]
