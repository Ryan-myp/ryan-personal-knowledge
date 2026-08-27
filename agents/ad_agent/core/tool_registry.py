"""
core/tool_registry.py - 工具注册表实现

借鉴 DAP Agent internal/core/registry/registry.go
线程安全的工具注册与执行中心，所有平台 Skill 的工具最终都注册到这里。
"""

import hashlib
import json
import logging
import threading
from typing import Any, Optional
from .interfaces import (
    ToolDefinition, ToolHandler, ToolRegistry, ToolResult,
    ToolContext, RiskLevel, ToolEffect, ReplayPolicy, ToolSchema
)


logger = logging.getLogger(__name__)


class SimpleToolRegistry(ToolRegistry):
    """
    简单的工具注册表实现。
    
    特点：
    - 线程安全（读写锁）
    - 支持按平台/Skill 查询
    - 执行前自动 Schema 校验
    - 支持幂等键生成（用于 WriteGuard 检查）
    """
    
    def __init__(self):
        self._lock = threading.RLock()
        self._tools: dict[str, tuple[ToolDefinition, ToolHandler]] = {}
        self._by_skill: dict[str, list[str]] = {}  # skill_name -> [tool_names]
        self._by_platform: dict[str, list[str]] = {}  # platform -> [tool_names]
        self._skill_tool_defs: dict[str, list[ToolDefinition]] = {}  # skill_name -> [tool_defs]
    
    def register(self, definition: ToolDefinition, handler: ToolHandler) -> None:
        """注册一个工具"""
        with self._lock:
            if definition.name in self._tools:
                raise ValueError(f"Tool '{definition.name}' already registered")

            self._tools[definition.name] = (definition, handler)

            # 更新索引
            skill = definition.skill or definition.platform
            self._by_skill.setdefault(skill, []).append(definition.name)
            self._by_platform.setdefault(definition.platform, []).append(definition.name)

            # 记录 Skill 的工具定义（用于动态加载/卸载）
            if skill not in self._skill_tool_defs:
                self._skill_tool_defs[skill] = []
            if definition not in self._skill_tool_defs[skill]:
                self._skill_tool_defs[skill].append(definition)
    
    def get(self, name: str) -> tuple[ToolDefinition, ToolHandler]:
        """获取工具定义和处理器"""
        with self._lock:
            if name not in self._tools:
                raise KeyError(f"Tool '{name}' not found")
            return self._tools[name]
    
    def list_by_platform(self, platform: str) -> list[ToolDefinition]:
        """列出某平台所有工具"""
        with self._lock:
            return [
                self._tools[name][0]
                for name in self._by_platform.get(platform, [])
                if name in self._tools
            ]
    
    def list_by_skill(self, skill_name: str) -> list[ToolDefinition]:
        """列出某 Skill 所有工具"""
        with self._lock:
            return [
                self._tools[name][0]
                for name in self._by_skill.get(skill_name, [])
                if name in self._tools
            ]
    
    def load_skill_tools(self, skill_name: str, tool_defs: list[ToolDefinition], 
                         handler_factory: callable) -> None:
        """
        动态加载某个 Skill 的所有工具
        
        Args:
            skill_name: Skill 名称
            tool_defs: 工具定义列表
            handler_factory: 工厂函数，根据 tool_def 创建 handler
        """
        for tool_def in tool_defs:
            try:
                handler = handler_factory(tool_def)
                if handler:
                    self.register(tool_def, handler)
            except Exception as e:
                logger.warning(f"加载工具 {tool_def.name} 失败: {e}")
        
        logger.info(f"已动态加载 Skill '{skill_name}'，共 {len(tool_defs)} 个工具")
    
    def unload_skill_tools(self, skill_name: str) -> None:
        """
        卸载某个 Skill 的所有工具

        Args:
            skill_name: Skill 名称
        """
        tool_names = self._by_skill.get(skill_name, []).copy()
        for name in tool_names:
            if name in self._tools:
                # 先获取 definition，再从 registry 删除
                defn, _ = self._tools.pop(name)
                # 从 platform 索引中移除
                platform_tools = self._by_platform.get(defn.platform, [])
                if name in platform_tools:
                    platform_tools.remove(name)

        # 清理索引
        self._by_skill.pop(skill_name, None)
        self._skill_tool_defs.pop(skill_name, None)

        logger.info(f"已卸载 Skill '{skill_name}'，移除 {len(tool_names)} 个工具")
    
    def get_skill_tool_defs(self, skill_name: str) -> list[ToolDefinition]:
        """获取 Skill 的工具定义（未注册前）"""
        return self._skill_tool_defs.get(skill_name, [])
    
    def list_all(self) -> list[ToolDefinition]:
        """列出所有工具"""
        with self._lock:
            return [defn for defn, _ in self._tools.values()]

    def list_all_platforms(self) -> list[str]:
        """列出所有已注册的平台"""
        with self._lock:
            return list(self._by_platform.keys())

    def unregister(self, tool_name: str) -> None:
        """从注册表中移除工具"""
        with self._lock:
            if tool_name not in self._tools:
                return
            defn, _ = self._tools.pop(tool_name)
            # 清理索引
            skill = defn.skill or defn.platform
            if tool_name in self._by_skill.get(skill, []):
                self._by_skill[skill].remove(tool_name)
            if tool_name in self._by_platform.get(defn.platform, []):
                self._by_platform[defn.platform].remove(tool_name)
            # 清理空列表
            if skill in self._by_skill and not self._by_skill[skill]:
                del self._by_skill[skill]
            if defn.platform in self._by_platform and not self._by_platform[defn.platform]:
                del self._by_platform[defn.platform]
    
    def execute(
        self,
        ctx: ToolContext,
        tool_name: str,
        input_data: dict[str, Any]
    ) -> ToolResult:
        """
        执行工具
        
        执行链：
        1. 查找工具定义
        2. Schema 校验（如有）
        3. 调用 handler.execute()
        """
        defn, handler = self.get(tool_name)
        
        # 所有工具统一执行 Schema 校验，避免只依赖 Handler 自己实现校验。
        if defn.input_schema:
            errors = validate_tool_input(defn.input_schema, input_data)
            if errors:
                return ToolResult.error(f"Input validation failed: {errors}")

        if hasattr(handler, "execute"):
            return handler.execute(ctx, input_data)
        if callable(handler):
            return handler(ctx, input_data)
        return ToolResult.error(f"Tool '{tool_name}' has no executable handler")
    
    def generate_idempotency_key(
        self,
        tool_name: str,
        input_data: dict[str, Any],
        user_id: str
    ) -> str:
        """
        生成幂等键，用于 WriteGuard 的重复提交检查
        
        格式：sha256(user_id + tool_name + sorted_input)
        """
        input_str = json.dumps(input_data, sort_keys=True, default=str)
        raw = f"{user_id}:{tool_name}:{input_str}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]


# ─── Schema 校验工具 ────────────────────────────────────────────

def validate_tool_input(
    schema: ToolSchema,
    data: dict[str, Any],
    include_provider_contract: bool = False,
) -> list[str]:
    """
    校验输入数据是否符合 Schema
    
    返回错误列表，空列表表示通过。
    """
    errors = []
    
    # 检查必填字段
    for field_name in schema.required:
        if field_name not in data:
            errors.append(f"Missing required field: {field_name}")

    if include_provider_contract:
        for field_name in schema.provider_required:
            if data.get(field_name) in (None, ""):
                errors.append(f"Provider contract requires field: {field_name}")
        for alternatives in schema.provider_any_of:
            if not any(
                data.get(field_name) not in (None, "", {}, [])
                for field_name in alternatives
            ):
                errors.append(
                    "Provider contract requires one of: "
                    + ", ".join(alternatives)
                )
    
    # 检查字段类型
    for field_name, field_schema in schema.properties.items():
        if field_name not in data:
            continue
        value = data[field_name]
        expected_type = field_schema.get("type", "string")
        
        type_map = {
            "string": str,
            "number": (int, float),
            "integer": int,
            "boolean": bool,
            "array": list,
            "object": dict,
        }
        
        # A small subset of JSON Schema used by provider contracts needs to
        # accept more than one JSON type (for example DV360 date_range may be
        # a preset string or an explicit {start_date, end_date} object).
        if isinstance(expected_type, (list, tuple, set)):
            python_types = tuple(
                type_map[item] for item in expected_type if item in type_map
            )
            python_type = python_types or None
        else:
            python_type = type_map.get(expected_type)
        # bool is a subclass of int in Python, but it is never a valid
        # monetary/integer API field for an advertising payload.
        numeric_types = set(expected_type) if isinstance(expected_type, (list, tuple, set)) else {expected_type}
        invalid_bool = bool(numeric_types & {"number", "integer"}) and isinstance(value, bool)
        if python_type and (invalid_bool or not isinstance(value, python_type)):
            errors.append(
                f"Field '{field_name}' expected {expected_type}, "
                f"got {type(value).__name__}"
            )

        enum = field_schema.get("enum")
        if enum is not None and value not in enum:
            errors.append(
                f"Field '{field_name}' must be one of {list(enum)}, got {value!r}"
            )

        minimum = field_schema.get("minimum")
        if minimum is not None and not isinstance(value, bool):
            try:
                if value < minimum:
                    errors.append(f"Field '{field_name}' must be >= {minimum}")
            except TypeError:
                pass
    
    return errors
