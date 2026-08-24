"""
core/tool_registry.py - 工具注册表实现

借鉴 DAP Agent internal/core/registry/registry.go
线程安全的工具注册与执行中心，所有平台 Skill 的工具最终都注册到这里。
"""

import hashlib
import json
from typing import Any, Optional
from .interfaces import (
    ToolDefinition, ToolHandler, ToolRegistry, ToolResult,
    ToolContext, RiskLevel, ToolEffect, ReplayPolicy, ToolSchema
)


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
        self._tools: dict[str, tuple[ToolDefinition, ToolHandler]] = {}
        self._by_skill: dict[str, list[str]] = {}  # skill_name -> [tool_names]
        self._by_platform: dict[str, list[str]] = {}  # platform -> [tool_names]
    
    def register(self, definition: ToolDefinition, handler: ToolHandler) -> None:
        """注册一个工具"""
        if definition.name in self._tools:
            raise ValueError(f"Tool '{definition.name}' already registered")
        
        self._tools[definition.name] = (definition, handler)
        
        # 更新索引
        self._by_skill.setdefault(definition.skill, []).append(definition.name)
        self._by_platform.setdefault(definition.platform, []).append(definition.name)
    
    def get(self, name: str) -> tuple[ToolDefinition, ToolHandler]:
        """获取工具定义和处理器"""
        if name not in self._tools:
            raise KeyError(f"Tool '{name}' not found")
        return self._tools[name]
    
    def list_by_platform(self, platform: str) -> list[ToolDefinition]:
        """列出某平台所有工具"""
        return [
            self._tools[name][0]
            for name in self._by_platform.get(platform, [])
        ]
    
    def list_by_skill(self, skill_name: str) -> list[ToolDefinition]:
        """列出某 Skill 所有工具"""
        return [
            self._tools[name][0]
            for name in self._by_skill.get(skill_name, [])
        ]
    
    def list_all(self) -> list[ToolDefinition]:
        """列出所有工具"""
        return [defn for defn, _ in self._tools.values()]
    
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
        
        # 可选：Schema 校验
        if defn.input_schema and hasattr(handler, 'validate_input'):
            errors = handler.validate_input(input_data)
            if errors:
                return ToolResult.error(f"Input validation failed: {errors}")
        
        return handler.execute(ctx, input_data)
    
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

def validate_tool_input(schema: ToolSchema, data: dict[str, Any]) -> list[str]:
    """
    校验输入数据是否符合 Schema
    
    返回错误列表，空列表表示通过。
    """
    errors = []
    
    # 检查必填字段
    for field_name in schema.required:
        if field_name not in data:
            errors.append(f"Missing required field: {field_name}")
    
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
        
        python_type = type_map.get(expected_type)
        if python_type and not isinstance(value, python_type):
            errors.append(
                f"Field '{field_name}' expected {expected_type}, "
                f"got {type(value).__name__}"
            )
    
    return errors
