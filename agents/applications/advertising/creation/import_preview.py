"""Validate bounded CSV/XLSX rows against a registered creation Blueprint."""

from __future__ import annotations

import json
import math
from typing import Any, Mapping, Sequence


MAX_PREVIEW_ROWS = 100
MAX_PREVIEW_COLUMNS = 80
MAX_CELL_CHARS = 20_000


def preview_creation_rows(
    runtime: Any,
    *,
    blueprint_id: str,
    version: str | None,
    headers: Sequence[str],
    rows: Sequence[Sequence[Any]],
    column_mapping: Mapping[str, str],
) -> dict[str, Any]:
    """Map cells to Blueprint fields and evaluate each row without execution."""
    if len(rows) > MAX_PREVIEW_ROWS:
        raise ValueError("单次最多预览 100 行")
    if not headers or len(headers) > MAX_PREVIEW_COLUMNS:
        raise ValueError("表格列数必须在 1 到 80 列之间")
    if not isinstance(column_mapping, Mapping) or not column_mapping:
        raise ValueError("请至少映射一个 Blueprint 字段")

    blueprints = getattr(runtime, "creation_blueprints", None)
    getter = getattr(blueprints, "get", None)
    blueprint = getter(blueprint_id, version) if callable(getter) else None
    if blueprint is None:
        raise ValueError("广告创建 Blueprint 不存在或版本不可用")
    fields = _blueprint_fields(blueprint)
    fields_by_path = {str(field["path"]): field for field in fields}
    header_indexes = {str(header): index for index, header in enumerate(headers)}

    mapping: dict[str, str] = {}
    for field_path, header in column_mapping.items():
        normalized_path = str(field_path or "").strip()
        normalized_header = str(header or "").strip()
        if normalized_path not in fields_by_path:
            raise ValueError(f"未知的 blueprint field: {normalized_path}")
        if normalized_header not in header_indexes:
            raise ValueError(f"column 不存在: {normalized_header}")
        mapping[normalized_path] = normalized_header

    evaluations = getattr(runtime, "evaluate_creation_blueprint", None)
    if not callable(evaluations):
        raise RuntimeError("Blueprint 校验服务不可用")

    previews = []
    ready_count = 0
    invalid_count = 0
    for row_number, row in enumerate(rows, start=1):
        if not isinstance(row, (list, tuple)):
            raise ValueError(f"第 {row_number} 行格式无效")
        values: dict[str, Any] = {}
        field_errors: dict[str, str] = {}
        if len(row) > len(headers):
            field_errors["$row"] = "该行的单元格数量超过表头列数"
        for field_path, header in mapping.items():
            column_index = header_indexes[header]
            if column_index >= len(row):
                field_errors[field_path] = "该行缺少已映射的单元格"
                continue
            raw_value = row[column_index]
            if raw_value is None or not str(raw_value).strip():
                continue
            cell = str(raw_value).strip()
            if len(cell) > MAX_CELL_CHARS:
                field_errors[field_path] = "单元格超过长度限制"
                continue
            field = fields_by_path[field_path]
            schema = _field_schema(runtime, str(field.get("tool_ref") or ""))
            try:
                converted = _convert_cell(cell, schema)
                _validate_converted(converted, schema)
            except (TypeError, ValueError, json.JSONDecodeError) as error:
                field_errors[field_path] = _safe_validation_message(error)
                continue
            _set_nested_value(values, field_path, converted)

        evaluation = evaluations(
            blueprint_id,
            values,
            version=version,
        )
        evaluation = evaluation if isinstance(evaluation, Mapping) else {}
        invalid_fields = list(dict.fromkeys([
            *field_errors,
            *[
                str(item)
                for item in (evaluation.get("invalid_fields") or [])
                if str(item).strip()
            ],
        ]))
        missing_fields = [
            str(item)
            for item in (evaluation.get("missing_fields") or [])
            if str(item).strip()
        ]
        ready = bool(evaluation.get("ready")) and not invalid_fields
        if ready:
            ready_count += 1
        if invalid_fields or missing_fields:
            invalid_count += 1
        previews.append({
            "row_number": row_number,
            "values": values,
            "ready": ready,
            "missing_fields": missing_fields,
            "invalid_fields": invalid_fields,
            "field_errors": field_errors,
        })

    return {
        "preview_only": True,
        "blueprint_id": str(blueprint_id),
        "version": str(getattr(blueprint, "version", version or "")),
        "row_count": len(previews),
        "ready_count": ready_count,
        "invalid_count": invalid_count,
        "rows": previews,
    }


def _blueprint_fields(blueprint: Any) -> list[dict[str, Any]]:
    fields = getattr(blueprint, "fields", None)
    if not isinstance(fields, (list, tuple)):
        raise ValueError("Blueprint 字段定义无效")
    result = []
    for field in fields:
        if isinstance(field, Mapping) and field.get("path") and field.get("tool_ref"):
            result.append(dict(field))
    if not result:
        raise ValueError("Blueprint 没有可导入的字段")
    return result


def _field_schema(runtime: Any, tool_ref: str) -> Mapping[str, Any]:
    if "." not in tool_ref:
        raise ValueError("Blueprint field 的 Tool 引用无效")
    tool_name, field_path = tool_ref.split(".", 1)
    registered = getattr(runtime, "_get_registered_tool", None)
    if not callable(registered):
        raise ValueError("无法读取 Tool schema")
    try:
        definition, _handler = registered(tool_name)
    except (KeyError, LookupError, TypeError, ValueError) as error:
        raise ValueError("Blueprint 引用的 Tool schema 不可用") from error
    input_schema = getattr(definition, "input_schema", None)
    if isinstance(input_schema, Mapping):
        properties = input_schema.get("properties", {})
    else:
        properties = getattr(input_schema, "properties", {})
    schema: Any = properties
    parts = [part for part in field_path.split(".") if part]
    if not parts:
        return {}
    for index, part in enumerate(parts):
        if not isinstance(schema, Mapping):
            return {}
        schema = schema.get(part)
        if not isinstance(schema, Mapping):
            return {}
        if index < len(parts) - 1:
            schema = schema.get("properties", {})
    return schema if isinstance(schema, Mapping) else {}


def _convert_cell(value: str, schema: Mapping[str, Any]) -> Any:
    declared_type = schema.get("type", "string")
    types = (
        [item for item in declared_type if item != "null"]
        if isinstance(declared_type, list)
        else [declared_type]
    )
    value_type = str(types[0] if types else "string")
    if value_type == "integer":
        return int(value)
    if value_type == "number":
        number = float(value)
        if not math.isfinite(number):
            raise ValueError("需要有限数值")
        return number
    if value_type == "boolean":
        normalized = value.casefold()
        if normalized in {"true", "1", "yes", "是"}:
            return True
        if normalized in {"false", "0", "no", "否"}:
            return False
        raise ValueError("需要布尔值")
    if value_type in {"array", "object"}:
        parsed = json.loads(value)
        if value_type == "array" and not isinstance(parsed, list):
            raise ValueError("需要 JSON 数组")
        if value_type == "object" and not isinstance(parsed, dict):
            raise ValueError("需要 JSON 对象")
        return parsed
    if value_type == "null":
        raise ValueError("该字段不接受非空值")
    return value


def _validate_converted(value: Any, schema: Mapping[str, Any]) -> None:
    enum = schema.get("enum")
    if isinstance(enum, (list, tuple)) and value not in enum:
        raise ValueError("不属于允许的选项")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        minimum = schema.get("minimum")
        maximum = schema.get("maximum")
        if minimum is not None and value < float(minimum):
            raise ValueError("小于允许的最小值")
        if maximum is not None and value > float(maximum):
            raise ValueError("超过允许的最大值")
    if isinstance(value, str):
        min_length = schema.get("minLength")
        max_length = schema.get("maxLength")
        if min_length is not None and len(value) < int(min_length):
            raise ValueError("文本长度不足")
        if max_length is not None and len(value) > int(max_length):
            raise ValueError("文本超过长度限制")


def _safe_validation_message(error: Exception) -> str:
    if isinstance(error, json.JSONDecodeError):
        return "需要有效的 JSON 值"
    if isinstance(error, (TypeError, ValueError)):
        message = str(error)
        if "invalid literal" in message or "could not convert" in message:
            return "单元格类型与字段要求不匹配"
        return message[:160] or "单元格无效"
    return "单元格无效"


def _set_nested_value(target: dict[str, Any], path: str, value: Any) -> None:
    parts = [part for part in str(path).split(".") if part]
    if not parts:
        return
    current = target
    for part in parts[:-1]:
        child = current.get(part)
        if not isinstance(child, dict):
            child = {}
            current[part] = child
        current = child
    current[parts[-1]] = value


__all__ = ["MAX_PREVIEW_ROWS", "preview_creation_rows"]
