"""Model-facing JSON Schema projection; execution contracts remain unchanged."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


# Only presentation annotations are removable. Lookup dependencies and all
# validation keywords remain available to the model and the executor.
_PRESENTATION_FIELDS = frozenset({
    "presentation", "selection_label_fields", "selection_value_fields", "option_labels",
})
_SCHEMA_MAPS = frozenset({
    "properties", "patternProperties", "$defs", "definitions", "dependentSchemas",
})
_SCHEMA_LISTS = frozenset({"allOf", "anyOf", "oneOf", "prefixItems"})
_SCHEMA_VALUES = frozenset({
    "items", "additionalItems", "additionalProperties", "unevaluatedProperties",
    "unevaluatedItems", "contains", "propertyNames", "not", "if", "then", "else",
})
_EXECUTOR_FIELDS = frozenset({
    "requires", "requires_any_of", "requires_exactly_one_of", "conditional_rules",
    "additional_properties",
})


def _schema_map(key: str, value: Mapping[str, Any]) -> dict[str, Any]:
    return {
        name: _project_schema(child)
        for name, child in value.items()
        if not (
            key == "properties" and isinstance(child, Mapping)
            and child.get("ui_hidden") is True
        )
    }


def _project_schema(schema: Any) -> Any:
    if not isinstance(schema, Mapping):
        return schema
    result = {}
    for key, value in schema.items():
        if key.startswith("ui_") or key in _PRESENTATION_FIELDS:
            continue
        if key in _SCHEMA_MAPS and isinstance(value, Mapping):
            value = _schema_map(key, value)
        elif key in _SCHEMA_LISTS and isinstance(value, list):
            value = [_project_schema(item) for item in value]
        elif key in _SCHEMA_VALUES:
            value = (
                [_project_schema(item) for item in value]
                if isinstance(value, list) else _project_schema(value)
            )
        result[key] = value
    properties = schema.get("properties")
    if isinstance(properties, Mapping) and isinstance(schema.get("required"), list):
        hidden = set(properties) - set(result["properties"])
        result["required"] = [key for key in schema["required"] if key not in hidden]
    return result


def model_parameters(raw_schema: Any) -> dict[str, Any]:
    if callable(getattr(raw_schema, "to_dict", None)):
        raw_schema = raw_schema.to_dict()
    schema = dict(raw_schema) if isinstance(raw_schema, Mapping) else {}
    # These are executor-only live gates, not JSON Schema keywords. They were
    # never model parameters; their authoritative validation stays server-side.
    schema = {key: value for key, value in schema.items() if key not in _EXECUTOR_FIELDS}
    schema.setdefault("type", "object")
    schema.setdefault("properties", {})
    schema.setdefault("required", [])
    schema.setdefault("additionalProperties", False)
    return _project_schema(schema)


def model_tool_payload(tool: Any) -> dict[str, Any]:
    def field(name: str, default: Any) -> Any:
        return (
            tool.get(name, default)
            if isinstance(tool, Mapping) else getattr(tool, name, default)
        )

    return {"type": "function", "function": {
        "name": str(field("name", "") or "").strip(),
        "description": str(field("description", "") or "")[:1200],
        "parameters": model_parameters(field("input_schema", {})),
    }}
