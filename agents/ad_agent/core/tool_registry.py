"""
core/tool_registry.py - 工具注册表实现

借鉴 DAP Agent internal/core/registry/registry.go
线程安全的工具注册与执行中心，所有扩展 Skill 的工具最终都注册到这里。
"""

import hashlib
import json
import logging
import math
import re
import threading
from typing import Any, Callable, Optional
from .interfaces import (
    ToolDefinition, ToolHandler, ToolRegistry, ToolResult,
    ToolContext, RiskLevel, ToolEffect, ReplayPolicy, ToolSchema
)
from agents.agent_harness import ToolBinding, ToolSource
from .namespace import normalize_namespace


logger = logging.getLogger(__name__)


class SimpleToolRegistry(ToolRegistry):
    """
    简单的工具注册表实现。
    
    特点：
    - 线程安全（读写锁）
    - 支持按 namespace/Skill 查询
    - 执行前自动 Schema 校验
    - 支持幂等键生成（用于 WriteGuard 检查）
    """
    
    def __init__(self):
        self._lock = threading.RLock()
        self._tools: dict[str, tuple[ToolDefinition, ToolHandler]] = {}
        self._by_skill: dict[str, list[str]] = {}  # skill_name -> [tool_names]
        self._by_namespace: dict[str, list[str]] = {}  # namespace -> [tool_names]
        self._skill_tool_defs: dict[str, list[ToolDefinition]] = {}  # skill_name -> [tool_defs]
        self._by_source: dict[str, list[str]] = {}
    
    def register(self, definition: ToolDefinition, handler: ToolHandler) -> None:
        """注册一个工具"""
        with self._lock:
            if definition.name in self._tools:
                existing = self._tools[definition.name][0]
                if existing.contract_hash != definition.contract_hash:
                    raise ValueError(
                        f"Tool '{definition.name}' contract hash mismatch: "
                        f"registered={existing.contract_hash}, "
                        f"incoming={definition.contract_hash}"
                    )
                raise ValueError(f"Tool '{definition.name}' already registered")

            self._tools[definition.name] = (definition, handler)

            # 更新索引
            skill = definition.skill or definition.namespace
            self._by_skill.setdefault(skill, []).append(definition.name)
            self._by_namespace.setdefault(definition.namespace, []).append(definition.name)

            # 记录 Skill 的工具定义（用于动态加载/卸载）
            if skill not in self._skill_tool_defs:
                self._skill_tool_defs[skill] = []
            if definition not in self._skill_tool_defs[skill]:
                self._skill_tool_defs[skill].append(definition)

    def register_binding(self, binding: ToolBinding) -> None:
        """Register an application-neutral contract/executor pair."""
        if not isinstance(binding, ToolBinding):
            raise TypeError("register_binding expects a ToolBinding")
        self.register(binding.definition, binding.executor)

    def register_source(self, source: ToolSource) -> list[str]:
        """Atomically register every binding published by one source."""
        source_id = str(getattr(source, "source_id", "") or "").strip()
        list_bindings = getattr(source, "list_bindings", None)
        if not source_id or not callable(list_bindings):
            raise TypeError("Tool source must expose source_id and list_bindings()")
        bindings = list(list_bindings())
        if source_id in self._by_source:
            raise ValueError(f"Tool source '{source_id}' already registered")
        registered: list[str] = []
        with self._lock:
            try:
                for binding in bindings:
                    self.register_binding(binding)
                    registered.append(binding.definition.name)
                self._by_source[source_id] = registered
            except Exception:
                for name in reversed(registered):
                    self.unregister(name)
                raise
        return list(registered)
    
    def get(self, name: str) -> tuple[ToolDefinition, ToolHandler]:
        """获取工具定义和处理器"""
        with self._lock:
            if name not in self._tools:
                raise KeyError(f"Tool '{name}' not found")
            return self._tools[name]
    
    def list_by_namespace(self, namespace: str) -> list[ToolDefinition]:
        """列出某 namespace 的所有工具。"""
        namespace = normalize_namespace(namespace)
        with self._lock:
            return [
                self._tools[name][0]
                for name in self._by_namespace.get(namespace, [])
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
    
    def load_skill_tools(
        self,
        skill_name: str,
        tool_defs: list[ToolDefinition],
        handler_factory: Callable[[ToolDefinition], ToolHandler],
    ) -> None:
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
        with self._lock:
            tool_names = self._by_skill.get(skill_name, []).copy()
            for name in tool_names:
                if name in self._tools:
                    # 先获取 definition，再从 registry 删除
                    defn, _ = self._tools.pop(name)
                    # 从 namespace 索引中移除
                    namespace_tools = self._by_namespace.get(defn.namespace, [])
                    if name in namespace_tools:
                        namespace_tools.remove(name)
                    if not namespace_tools:
                        self._by_namespace.pop(defn.namespace, None)

            # 清理索引
            self._by_skill.pop(skill_name, None)
            self._skill_tool_defs.pop(skill_name, None)

        logger.info(f"已卸载 Skill '{skill_name}'，移除 {len(tool_names)} 个工具")
    
    def get_skill_tool_defs(self, skill_name: str) -> list[ToolDefinition]:
        """获取 Skill 的工具定义（未注册前）"""
        with self._lock:
            return list(self._skill_tool_defs.get(skill_name, []))
    
    def list_all(self) -> list[ToolDefinition]:
        """列出所有工具"""
        with self._lock:
            return [defn for defn, _ in self._tools.values()]

    def list_all_namespaces(self) -> list[str]:
        """列出所有已注册的 namespace。"""
        with self._lock:
            return list(self._by_namespace.keys())

    def unregister(self, tool_name: str) -> None:
        """从注册表中移除工具"""
        with self._lock:
            if tool_name not in self._tools:
                return
            defn, _ = self._tools.pop(tool_name)
            # 清理索引
            skill = defn.skill or defn.namespace
            if tool_name in self._by_skill.get(skill, []):
                self._by_skill[skill].remove(tool_name)
            if tool_name in self._by_namespace.get(defn.namespace, []):
                self._by_namespace[defn.namespace].remove(tool_name)
            # 清理空列表
            if skill in self._by_skill and not self._by_skill[skill]:
                del self._by_skill[skill]
            if defn.namespace in self._by_namespace and not self._by_namespace[defn.namespace]:
                del self._by_namespace[defn.namespace]
            definitions = self._skill_tool_defs.get(skill, [])
            self._skill_tool_defs[skill] = [
                item for item in definitions if item.name != tool_name
            ]
            if not self._skill_tool_defs[skill]:
                del self._skill_tool_defs[skill]
            for source_id, names in list(self._by_source.items()):
                if tool_name not in names:
                    continue
                remaining = [name for name in names if name != tool_name]
                if remaining:
                    self._by_source[source_id] = remaining
                else:
                    self._by_source.pop(source_id, None)

    def unregister_source(self, source_id: str) -> list[str]:
        """Remove all Tools owned by a source and return removed names."""
        source_key = str(source_id or "").strip()
        with self._lock:
            names = list(self._by_source.get(source_key, []))
            for name in names:
                self.unregister(name)
            self._by_source.pop(source_key, None)
            return names

    def _snapshot_tools(self, tool_names: list[str] | tuple[str, ...]) -> list[tuple[ToolDefinition, ToolHandler]]:
        """Capture opaque Tool handlers for an owning lifecycle transaction."""
        with self._lock:
            return [
                self._tools[name]
                for name in dict.fromkeys(str(item) for item in (tool_names or ()))
                if name in self._tools
            ]

    def _restore_tools(
        self,
        entries: list[tuple[ToolDefinition, ToolHandler]],
    ) -> None:
        """Restore Tool definitions and handlers as one registry operation."""
        with self._lock:
            names = {definition.name for definition, _handler in entries}
            for name in names:
                if name in self._tools:
                    self.unregister(name)
            for definition, handler in entries:
                self.register(definition, handler)
    
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
            # A direct registry call is an execution seam, not a dry-run
            # preview. Write Tools must enforce their requirements here
            # too, otherwise a caller could reach an argument builder with a
            # missing requirement (or a live adapter) outside Runtime's
            # normal policy path.
            errors = validate_tool_input(
                defn.input_schema,
                input_data,
                include_tool_requirements=bool(defn.is_write_tool),
            )
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


class GuardedToolRegistry(ToolRegistry):
    """Runtime-facing registry that removes the unsafe direct execute path.

    ``SimpleToolRegistry`` remains useful as a low-level unit-test registry.
    Production Runtime instances wrap it so callers cannot reach an external
    Handler by invoking ``runtime.registry.execute`` and bypassing Runtime's
    scope, mode, approval and idempotency gates.
    """

    def __init__(self, inner: ToolRegistry):
        self._inner = inner
        # The token is held by the owning application Runtime and is required
        # for every internal execution seam. Public callers can inspect
        # definitions, but cannot obtain a live Handler or invoke the
        # authorized path by accident.
        self._execution_token = object()

    def register(self, definition: ToolDefinition, handler: ToolHandler) -> None:
        self._inner.register(definition, handler)

    def register_binding(self, binding: ToolBinding) -> None:
        register_binding = getattr(self._inner, "register_binding", None)
        if callable(register_binding):
            register_binding(binding)
            return
        self._inner.register(binding.definition, binding.executor)

    def register_source(self, source: ToolSource) -> list[str]:
        register_source = getattr(self._inner, "register_source", None)
        if callable(register_source):
            return register_source(source)
        bindings = list(source.list_bindings())
        registered: list[str] = []
        try:
            for binding in bindings:
                self.register_binding(binding)
                registered.append(binding.definition.name)
        except Exception:
            for name in reversed(registered):
                self._inner.unregister(name)
            raise
        return registered

    def get(self, name: str) -> tuple[ToolDefinition, ToolHandler]:
        definition, _handler = self._inner.get(name)
        return definition, _BlockedToolHandler()

    def get_authorized(
        self, name: str, _execution_token: object = None,
    ) -> tuple[ToolDefinition, ToolHandler]:
        """Return the raw Handler only to the owning Runtime seam."""
        if _execution_token is not self._execution_token:
            raise PermissionError("Raw tool handlers are only available to the owning Runtime")
        return self._inner.get(name)

    def list_by_namespace(self, namespace: str) -> list[ToolDefinition]:
        return self._inner.list_by_namespace(normalize_namespace(namespace))

    def list_by_skill(self, skill_name: str) -> list[ToolDefinition]:
        return self._inner.list_by_skill(skill_name)

    def unregister(self, tool_name: str) -> None:
        self._inner.unregister(tool_name)

    def unregister_source(self, source_id: str) -> list[str]:
        unregister_source = getattr(self._inner, "unregister_source", None)
        if callable(unregister_source):
            return unregister_source(source_id)
        return []

    def _snapshot_tools(
        self,
        tool_names: list[str] | tuple[str, ...],
        _execution_token: object = None,
    ) -> list[tuple[ToolDefinition, ToolHandler]]:
        if _execution_token is not self._execution_token:
            raise PermissionError("Tool lifecycle snapshots are only available to the owning Runtime")
        snapshot = getattr(self._inner, "_snapshot_tools", None)
        if not callable(snapshot):
            return [
                self._inner.get(name)
                for name in dict.fromkeys(str(item) for item in (tool_names or ()))
            ]
        return snapshot(tool_names)

    def _restore_tools(
        self,
        entries: list[tuple[ToolDefinition, ToolHandler]],
        _execution_token: object = None,
    ) -> None:
        if _execution_token is not self._execution_token:
            raise PermissionError("Tool lifecycle restore is only available to the owning Runtime")
        restore = getattr(self._inner, "_restore_tools", None)
        if callable(restore):
            restore(entries)
            return
        names = [definition.name for definition, _handler in entries]
        for name in names:
            self._inner.unregister(name)
        for definition, handler in entries:
            self._inner.register(definition, handler)

    def execute(self, ctx: ToolContext, tool_name: str, input_data: dict[str, Any]) -> ToolResult:
        return ToolResult.error(
            "Direct registry execution is disabled; execute tools through the owning Runtime"
        )

    def execute_authorized(
        self, ctx: ToolContext, tool_name: str, input_data: dict[str, Any],
        _execution_token: object = None,
    ) -> ToolResult:
        """Internal Runtime seam after all policy gates have passed."""
        if _execution_token is not self._execution_token:
            return ToolResult.error(
                "Authorized registry execution is only available to the owning Runtime"
            )
        return self._inner.execute(ctx, tool_name, input_data)

    def list_all(self) -> list[ToolDefinition]:
        return self._inner.list_all()

    def list_all_namespaces(self) -> list[str]:
        return self._inner.list_all_namespaces()

    def generate_idempotency_key(
        self, tool_name: str, input_data: dict[str, Any], user_id: str
    ) -> str:
        generator = getattr(self._inner, "generate_idempotency_key", None)
        if callable(generator):
            return generator(tool_name, input_data, user_id)
        input_str = json.dumps(input_data, sort_keys=True, default=str)
        return hashlib.sha256(
            f"{user_id}:{tool_name}:{input_str}".encode()
        ).hexdigest()[:16]


class _BlockedToolHandler:
    """Non-executable public view returned by GuardedToolRegistry.get()."""

    def execute(self, _ctx: ToolContext, _input_data: dict[str, Any]) -> ToolResult:
        return ToolResult.error(
            "Direct handler execution is disabled; execute tools through the owning Runtime"
        )


# ─── Schema 校验工具 ────────────────────────────────────────────

def validate_tool_input(
    schema: ToolSchema,
    data: dict[str, Any],
    include_tool_requirements: bool = False,
) -> list[str]:
    """
    校验输入数据是否符合 Schema
    
    返回错误列表，空列表表示通过。
    """
    errors = []

    if not isinstance(data, dict):
        return [f"Input must be an object, got {type(data).__name__}"]
    
    def is_missing(value: Any) -> bool:
        return value in (None, "", {}, [])

    def value_at(path: str) -> Any:
        """Read a dotted field path for cross-object conditional rules."""
        value: Any = data
        for part in str(path).split("."):
            if not isinstance(value, dict) or part not in value:
                return None
            value = value[part]
        return value

    def validate_finite_numbers(value: Any, path: str = "") -> None:
        """Reject non-JSON numeric values even inside open extension objects."""
        if isinstance(value, bool):
            return
        if isinstance(value, (int, float)) and not math.isfinite(value):
            errors.append(
                f"Field '{path or '<input>'}' must be a finite number"
            )
            return
        if isinstance(value, dict):
            for key, item in value.items():
                child_path = f"{path}.{key}" if path else str(key)
                validate_finite_numbers(item, child_path)
        elif isinstance(value, (list, tuple)):
            for index, item in enumerate(value):
                validate_finite_numbers(item, f"{path}[{index}]")

    validate_finite_numbers(data)

    # 检查必填字段
    for field_name in schema.required:
        if field_name not in data or is_missing(data.get(field_name)):
            errors.append(f"Missing required field: {field_name}")

    if include_tool_requirements:
        for field_name in schema.requires:
            if data.get(field_name) in (None, ""):
                errors.append(f"Tool requirements require field: {field_name}")
        for alternatives in schema.requires_any_of:
            if not any(
                data.get(field_name) not in (None, "", {}, [])
                for field_name in alternatives
            ):
                errors.append(
                    "Tool requirements require one of: "
                    + ", ".join(alternatives)
                )
        for alternatives in getattr(schema, "requires_exactly_one_of", []) or []:
            present = [
                field_name for field_name in alternatives
                if data.get(field_name) not in (None, "", {}, [])
            ]
            if len(present) != 1:
                errors.append(
                    "Tool requirements require exactly one of: "
                    + ", ".join(alternatives)
                )

    # Closed-world tool contracts prevent a caller from believing an
    # unsupported parameter was applied when a Handler simply ignored it.
    # Open-ended extension objects remain possible by setting
    # ``additional_properties=True`` on the top-level schema, or by using a
    # field-level object schema with its own explicit policy.
    if (
        schema.additional_properties is False
        and isinstance(schema.properties, dict)
    ):
        unknown = sorted(set(data) - set(schema.properties))
        for field_name in unknown:
            errors.append(f"Field '{field_name}' is not allowed")

    # Conditional rules model extension relationships such as
    # objective_type=APP_PROMOTION -> promotion_type must be APP_ANDROID and
    # app_id/deep_bid_type are required. The compact operators are data-only
    # and shared with declarative conditions, so a publisher can publish a
    # complete allowed-value matrix without a Core-specific branch.
    def condition_matches(conditions: Any) -> bool:
        if not isinstance(conditions, dict):
            return False
        if "all" in conditions:
            return all(condition_matches(item) for item in conditions["all"])
        if "any" in conditions:
            return any(condition_matches(item) for item in conditions["any"])
        if "not" in conditions:
            return not condition_matches(conditions["not"])
        for field_name, expected in conditions.items():
            actual = value_at(field_name)
            if isinstance(expected, dict):
                if "equals" in expected and actual != expected["equals"]:
                    return False
                if "in" in expected and actual not in expected["in"]:
                    return False
                if "not_in" in expected and actual in expected["not_in"]:
                    return False
                if "exists" in expected:
                    present = not is_missing(actual)
                    if present != bool(expected["exists"]):
                        return False
                if "contains" in expected:
                    if not isinstance(actual, (list, tuple, set, str)):
                        return False
                    if expected["contains"] not in actual:
                        return False
            elif actual != expected:
                return False
        return True

    for rule in schema.conditional_rules:
        if not isinstance(rule, dict):
            continue
        conditions = rule.get("if", rule.get("when", {}))
        if not condition_matches(conditions):
            continue

        for field_name in rule.get("required", rule.get("required_fields", [])) or []:
            if is_missing(value_at(field_name)):
                errors.append(
                    rule.get("message")
                    or f"Field '{field_name}' is required when {conditions}"
                )

        allowed = rule.get("allowed", rule.get("enum", {}))
        if isinstance(allowed, dict):
            for field_name, values in allowed.items():
                field_value = value_at(field_name)
                if isinstance(field_value, (list, tuple, set)):
                    valid = all(item in values for item in field_value)
                else:
                    valid = field_value in values
                if field_value is not None and not valid:
                    errors.append(
                        rule.get("message")
                        or f"Field '{field_name}' must be one of {list(values)} when {conditions}"
                    )

        for field_name in rule.get("forbidden", rule.get("forbidden_fields", [])) or []:
            if not is_missing(value_at(field_name)):
                errors.append(
                    rule.get("message")
                    or f"Field '{field_name}' is not allowed when {conditions}"
                )
    
    def validate_value(path: str, value: Any, field_schema: dict[str, Any]) -> None:
        """Validate the small JSON-Schema subset used by ToolSchema.

        Nested validation is important for ``updates``: accepting only an
        outer object previously allowed arbitrary extension fields to bypass
        the contract and fail much later in a live adapter.
        """
        if not isinstance(field_schema, dict):
            return
        expected_type = field_schema.get("type", "string")
        type_map = {
            "string": str,
            "number": (int, float),
            "integer": int,
            "boolean": bool,
            "array": list,
            "object": dict,
        }
        if isinstance(expected_type, (list, tuple, set)):
            python_types = tuple(
                type_map[item] for item in expected_type if item in type_map
            )
            python_type = python_types or None
        else:
            python_type = type_map.get(expected_type)
        numeric_types = (
            set(expected_type)
            if isinstance(expected_type, (list, tuple, set))
            else {expected_type}
        )
        invalid_bool = bool(numeric_types & {"number", "integer"}) and isinstance(value, bool)
        if python_type and (invalid_bool or not isinstance(value, python_type)):
            errors.append(
                f"Field '{path}' expected {expected_type}, got {type(value).__name__}"
            )
            return

        enum = field_schema.get("enum")
        if enum is not None and value not in enum:
            errors.append(f"Field '{path}' must be one of {list(enum)}, got {value!r}")

        pattern = field_schema.get("pattern")
        if pattern is not None and isinstance(value, str):
            try:
                matches = re.fullmatch(str(pattern), value)
            except re.error:
                errors.append(f"Field '{path}' has an invalid validation pattern")
            else:
                if matches is None:
                    errors.append(
                        f"Field '{path}' does not match the required format"
                    )

        if isinstance(value, (str, list, dict)):
            min_length = field_schema.get("minLength", field_schema.get("minItems"))
            max_length = field_schema.get("maxLength", field_schema.get("maxItems"))
            if min_length is not None and len(value) < min_length:
                errors.append(
                    f"Field '{path}' must contain at least {min_length} items/characters"
                )
            if max_length is not None and len(value) > max_length:
                errors.append(
                    f"Field '{path}' must contain at most {max_length} items/characters"
                )

        minimum = field_schema.get("minimum")
        if minimum is not None and not isinstance(value, bool):
            try:
                if value < minimum:
                    errors.append(f"Field '{path}' must be >= {minimum}")
            except TypeError:
                pass

        maximum = field_schema.get("maximum")
        if maximum is not None and not isinstance(value, bool):
            try:
                if value > maximum:
                    errors.append(f"Field '{path}' must be <= {maximum}")
            except TypeError:
                pass

        if isinstance(value, list):
            item_schema = field_schema.get("items")
            if isinstance(item_schema, dict):
                for index, item in enumerate(value):
                    validate_value(f"{path}[{index}]", item, item_schema)

        if isinstance(value, dict):
            nested_properties = field_schema.get("properties", {})
            if not isinstance(nested_properties, dict):
                nested_properties = {}
            for required_name in field_schema.get("required", []) or []:
                if required_name not in value or is_missing(value.get(required_name)):
                    errors.append(f"Missing required field: {path}.{required_name}")
            if (
                field_schema.get("additional_properties") is False
                or field_schema.get("additionalProperties") is False
            ):
                unknown = sorted(set(value) - set(nested_properties))
                for key in unknown:
                    errors.append(f"Field '{path}.{key}' is not allowed")
            for key, child_schema in nested_properties.items():
                if key in value:
                    validate_value(f"{path}.{key}", value[key], child_schema)

    # Check field types and nested tool requirements.
    for field_name, field_schema in schema.properties.items():
        if field_name in data:
            validate_value(field_name, data[field_name], field_schema)
    
    return errors
