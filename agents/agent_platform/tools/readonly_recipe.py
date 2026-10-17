"""Bounded declarative JSON transforms for read-only Tool results."""

from __future__ import annotations

import json
import math
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any

from agents.agent_harness import StaticToolSource, ToolBinding
from agents.agent_harness.core.interfaces import (
    ReplayPolicy,
    RiskLevel,
    ToolDefinition,
    ToolEffect,
    ToolResult,
    ToolSchema,
)
from agents.agent_harness.core.security import (
    is_sensitive_field,
    redact_sensitive_text,
)


MAX_RECORDS = 200
MAX_STEPS = 10
MAX_INPUT_BYTES = 256_000
MAX_OUTPUT_BYTES = 32_000
MAX_JSON_DEPTH = 8
MAX_JSON_NODES = 20_000
MAX_ROW_FIELDS = 100
MAX_FIELD_PATH_CHARS = 128
MAX_SELECT_FIELDS = 32

_STEP_FIELDS = {
    "filter": {"op", "field", "operator", "value"},
    "select": {"op", "fields"},
    "sort": {"op", "field", "direction"},
    "limit": {"op", "limit"},
    "group_count": {"op", "field"},
    "aggregate": {"op", "function", "field"},
}
_FILTER_OPERATORS = {"eq", "neq", "contains", "in", "gt", "gte", "lt", "lte", "exists"}
_AGGREGATES = {"sum", "avg", "min", "max", "count"}


class _RecipeInputError(ValueError):
    pass


def _json_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, OverflowError) as error:
        raise _RecipeInputError("输入必须是有效的 JSON 数据") from error


def _validate_json(
    value: Any,
    *,
    depth: int = 0,
    counter: list[int] | None = None,
) -> None:
    if counter is None:
        counter = [0]
    counter[0] += 1
    if counter[0] > MAX_JSON_NODES or depth > MAX_JSON_DEPTH:
        raise _RecipeInputError("JSON 数据结构超过允许的复杂度")
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise _RecipeInputError("数值必须是有限数字")
        return
    if isinstance(value, Mapping):
        if len(value) > MAX_ROW_FIELDS:
            raise _RecipeInputError("单条记录字段过多")
        for key, item in value.items():
            if not isinstance(key, str):
                raise _RecipeInputError("对象字段名称必须是字符串")
            name = key
            if is_sensitive_field(name):
                raise _RecipeInputError("输入包含禁止处理的凭证字段")
            if "__" in name or len(name) > 128:
                raise _RecipeInputError("输入包含不安全的字段名称")
            _validate_json(item, depth=depth + 1, counter=counter)
        return
    if isinstance(value, (list, tuple)):
        if len(value) > MAX_RECORDS:
            raise _RecipeInputError("数组项目过多")
        for item in value:
            _validate_json(item, depth=depth + 1, counter=counter)
        return
    raise _RecipeInputError("输入只支持 JSON 基础类型")


def _field_path(value: Any) -> tuple[str, ...]:
    path = str(value or "").strip()
    parts = path.split(".")
    if (
        not path
        or len(path) > MAX_FIELD_PATH_CHARS
        or any(
            not part
            or len(part) > 64
            or "__" in part
            or is_sensitive_field(part)
            for part in parts
        )
    ):
        raise _RecipeInputError("字段路径不合法或包含敏感字段")
    return tuple(parts)


def _get_path(record: Mapping[str, Any], path: tuple[str, ...]) -> tuple[bool, Any]:
    value: Any = record
    for part in path:
        if not isinstance(value, Mapping) or part not in value:
            return False, None
        value = value[part]
    return True, value


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _redact_output(value: Any) -> Any:
    if isinstance(value, str):
        return redact_sensitive_text(value)
    if isinstance(value, Mapping):
        return {key: _redact_output(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_redact_output(item) for item in value]
    return value


def _matches(record: Mapping[str, Any], step: Mapping[str, Any]) -> bool:
    exists, actual = _get_path(record, _field_path(step.get("field")))
    operator = str(step.get("operator") or "")
    expected = step.get("value")
    if operator == "exists":
        if not isinstance(expected, bool):
            raise _RecipeInputError("exists 操作的 value 必须是布尔值")
        return exists is expected
    if not exists:
        return operator == "eq" and expected is None
    if operator == "eq":
        return actual == expected
    if operator == "neq":
        return actual != expected
    if operator == "contains":
        if isinstance(actual, str):
            if not isinstance(expected, str):
                raise _RecipeInputError("字符串 contains 的 value 必须是字符串")
            return expected in actual
        if isinstance(actual, (list, tuple)):
            return expected in actual
        return False
    if operator == "in":
        if not isinstance(expected, (list, tuple)):
            raise _RecipeInputError("in 操作的 value 必须是数组")
        return actual in expected
    if operator in {"gt", "gte", "lt", "lte"}:
        if isinstance(actual, bool) or isinstance(expected, bool):
            return False
        if not isinstance(actual, (int, float, str)) or not isinstance(
            expected, type(actual)
        ):
            return False
        return {
            "gt": lambda: actual > expected,
            "gte": lambda: actual >= expected,
            "lt": lambda: actual < expected,
            "lte": lambda: actual <= expected,
        }[operator]()
    raise _RecipeInputError("filter 操作符不支持")


def _sort_key(record: Mapping[str, Any], path: tuple[str, ...]) -> tuple[int, Any]:
    exists, value = _get_path(record, path)
    if not exists or value is None:
        return (0, "")
    if isinstance(value, bool):
        return (1, int(value))
    if isinstance(value, (int, float)):
        return (2, value)
    if isinstance(value, str):
        return (3, value.casefold())
    return (4, _canonical(value))


def _validate_step(step: Any) -> tuple[str, Mapping[str, Any]]:
    if not isinstance(step, Mapping):
        raise _RecipeInputError("每个步骤都必须是对象")
    operation = str(step.get("op") or "").strip()
    if operation not in _STEP_FIELDS:
        raise _RecipeInputError(f"操作不支持：{operation or '未指定'}")
    if set(step) - _STEP_FIELDS[operation]:
        raise _RecipeInputError("步骤包含不支持的字段")
    if operation == "filter":
        if str(step.get("operator") or "") not in _FILTER_OPERATORS:
            raise _RecipeInputError("filter 操作符不支持")
        if "value" not in step:
            raise _RecipeInputError("filter 步骤缺少 value")
        _field_path(step.get("field"))
    elif operation in {"sort", "group_count"}:
        _field_path(step.get("field"))
        if operation == "sort" and str(
            step.get("direction") or "asc"
        ).lower() not in {"asc", "desc"}:
            raise _RecipeInputError("sort direction 必须是 asc 或 desc")
    elif operation == "select":
        fields = step.get("fields")
        if (
            not isinstance(fields, list)
            or not fields
            or len(fields) > MAX_SELECT_FIELDS
        ):
            raise _RecipeInputError("select fields 必须是 1 到 32 个字段")
        for field in fields:
            _field_path(field)
    elif operation == "limit":
        value = step.get("limit")
        if isinstance(value, bool) or not isinstance(value, int):
            raise _RecipeInputError("limit 必须是整数")
        if value < 0 or value > MAX_RECORDS:
            raise _RecipeInputError("limit 超出允许范围")
    elif operation == "aggregate":
        if str(step.get("function") or "") not in _AGGREGATES:
            raise _RecipeInputError("aggregate function 不支持")
        _field_path(step.get("field"))
    return operation, step


def _aggregate(
    rows: Sequence[Mapping[str, Any]],
    function: str,
    path: tuple[str, ...],
    field_name: str,
) -> dict[str, Any]:
    values = [
        value
        for row in rows
        for present, value in [_get_path(row, path)]
        if present and value is not None
    ]
    if function == "count":
        result: Any = len(values)
    else:
        if any(
            isinstance(value, bool) or not isinstance(value, (int, float))
            for value in values
        ):
            raise _RecipeInputError("数值聚合字段必须只包含数字")
        numbers = [float(value) for value in values]
        if function == "sum":
            result = sum(numbers)
        elif not numbers:
            result = None
        elif function == "avg":
            result = sum(numbers) / len(numbers)
        elif function == "min":
            result = min(numbers)
        else:
            result = max(numbers)
    return {
        "function": function,
        "field": field_name,
        "value": result,
        "sample_count": len(values),
    }


class _ReadonlyRecipeExecutor:
    def execute(self, _context: Any, arguments: dict[str, Any]) -> ToolResult:
        try:
            return self._execute(arguments)
        except _RecipeInputError as error:
            return ToolResult.error(f"只读数据整理失败：{error}")

    def _execute(self, arguments: Mapping[str, Any]) -> ToolResult:
        if set(arguments) - {"records", "steps"}:
            raise _RecipeInputError("输入包含不支持的字段")
        raw_records = arguments.get("records", [])
        raw_steps = arguments.get("steps", [])
        if not isinstance(raw_records, list) or len(raw_records) > MAX_RECORDS:
            raise _RecipeInputError("records 必须是最多 200 条记录的数组")
        if not isinstance(raw_steps, list) or len(raw_steps) > MAX_STEPS:
            raise _RecipeInputError("steps 必须是最多 10 个操作的数组")
        _validate_json(raw_records)
        _validate_json(raw_steps)
        if len(_json_bytes({"records": raw_records, "steps": raw_steps})) > MAX_INPUT_BYTES:
            raise _RecipeInputError("输入数据超过 256 KB")
        rows: list[dict[str, Any]] = []
        for item in raw_records:
            if not isinstance(item, Mapping):
                raise _RecipeInputError("records 中的每一项都必须是对象")
            rows.append(dict(item))

        aggregate_result = None
        for raw_step in raw_steps:
            operation, step = _validate_step(raw_step)
            if operation == "filter":
                rows = [row for row in rows if _matches(row, step)]
            elif operation == "select":
                paths = [
                    (str(field), _field_path(field))
                    for field in step["fields"]
                ]
                selected_rows = []
                for row in rows:
                    selected: dict[str, Any] = {}
                    for field_name, path in paths:
                        present, value = _get_path(row, path)
                        if present:
                            selected[field_name] = value
                    selected_rows.append(selected)
                rows = selected_rows
            elif operation == "sort":
                path = _field_path(step.get("field"))
                rows.sort(
                    key=lambda row: _sort_key(row, path),
                    reverse=str(step.get("direction") or "asc").lower() == "desc",
                )
            elif operation == "limit":
                rows = rows[:int(step["limit"])]
            elif operation == "group_count":
                field_name = str(step.get("field") or "")
                path = _field_path(field_name)
                counts: Counter[str] = Counter()
                values_by_key: dict[str, Any] = {}
                for row in rows:
                    present, value = _get_path(row, path)
                    value = value if present else None
                    key = _canonical(value)
                    counts[key] += 1
                    values_by_key[key] = value
                groups = sorted(
                    counts,
                    key=lambda key: (-counts[key], key),
                )
                rows = [
                    {"value": values_by_key[key], "count": counts[key]}
                    for key in groups
                ]
            else:
                field_name = str(step.get("field") or "")
                aggregate_result = _aggregate(
                    rows,
                    str(step["function"]),
                    _field_path(field_name),
                    field_name,
                )

        result: dict[str, Any] = {
            "records": _redact_output(rows),
            "count": len(rows),
            "steps_applied": len(raw_steps),
            "data_status": "local",
        }
        if aggregate_result is not None:
            result["aggregate"] = _redact_output(aggregate_result)
        if len(_json_bytes(result)) > MAX_OUTPUT_BYTES:
            raise _RecipeInputError(
                "结果超过 32 KB，请先使用 limit 或 select 缩小结果"
            )
        return ToolResult.ok(result)


def readonly_recipe_tool_source(
    *,
    required_permission: str,
) -> StaticToolSource:
    """Publish only fixed, bounded JSON operations; never evaluate source code."""
    permission = str(required_permission or "").strip()
    if not permission:
        raise ValueError("required_permission is required")

    definition = ToolDefinition(
        name="agent_readonly_recipe",
        skill="agent-readonly-recipe",
        namespace="agent_platform",
        description=(
            "Transform JSON records already present in this Run. Supported steps: "
            "filter (eq, neq, contains, in, gt, gte, lt, lte, exists), select, "
            "sort, limit, group_count, aggregate (sum, avg, min, max, count). "
            "Steps execute in order. This Tool never runs code, calls other Tools, "
            "accesses files/network, or changes source data. Keep inputs within "
            "the published record, step, and output bounds."
        ),
        input_schema=ToolSchema(
            properties={
                "records": {
                    "type": "array",
                    "maxItems": MAX_RECORDS,
                    "items": {
                        "type": "object",
                        "additional_properties": True,
                    },
                    "description": "JSON object records produced in the current Run",
                },
                "steps": {
                    "type": "array",
                    "maxItems": MAX_STEPS,
                    "description": (
                        "Ordered declarative operations; each operation is "
                        "validated against its exact allowed fields at execution"
                    ),
                },
            },
            required=["records"],
            additional_properties=False,
        ),
        action="transform",
        resource_type="json_records",
        intent_types=["readonly_data_transform"],
        intent_aliases=[
            "汇总这些结果",
            "汇总刚才查询的结果",
            "统计这些结果",
            "筛选这些结果",
            "整理查询结果",
            "对查询结果分组",
            "aggregate these results",
            "filter these records",
            "group these records",
        ],
        risk_level=RiskLevel.LOW,
        effect_class=ToolEffect.READ,
        replay_policy=ReplayPolicy.SAFE,
        traits=["read_only", "declarative", "bounded_input", "bounded_output"],
        timeout_seconds=10,
        max_output_bytes=MAX_OUTPUT_BYTES,
        required_permissions=[permission],
        scope_required=False,
        result_items_key="records",
        contract_version="1.0.0",
    )
    return StaticToolSource(
        "agent-platform:readonly-recipe",
        [ToolBinding(definition, _ReadonlyRecipeExecutor())],
    )


__all__ = ["readonly_recipe_tool_source"]
