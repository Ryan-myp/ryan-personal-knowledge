"""Safe, provider-neutral UI metadata for conversational ad creation.

The objects produced here are A2UI-style descriptions, not executable UI
code.  They are derived from the provider-owned Blueprint and Tool schema so
the Runtime does not need a channel-specific form or field table.
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Optional

from .blueprint import (
    AdCreationBlueprint,
    BlueprintCascadeEngine,
    BlueprintRegistry,
    _schema_at_path,
    _value_at,
)
from .interfaces import ParsedIntent
from .platform import normalize_platform


_MAX_CARDS = 8
_MAX_FIELDS = 80
_MAX_OPTIONS = 100
_PRESENTATIONS = {
    "text_list", "asset_picker", "file_reference", "derived_readonly",
}
_SENSITIVE_FIELD = re.compile(
    r"(?:access[_-]?token|refresh[_-]?token|client[_-]?secret|app[_-]?secret|"
    r"private[_-]?key|developer[_-]?token|bc[_-]?id|partner[_-]?id|perter[_-]?id|mcc)",
    re.IGNORECASE,
)
def _tool_definition(tool_registry: Any, name: str) -> Any:
    getter = getattr(tool_registry, "get", None)
    if not callable(getter):
        return None
    try:
        value = getter(name)
    except (KeyError, LookupError):
        return None
    return value[0] if isinstance(value, tuple) and value else value


def _provider_values(intent: ParsedIntent, provider: str) -> dict[str, Any]:
    target = normalize_platform(provider)
    merged: dict[str, Any] = {}
    for raw_platform, values in (getattr(intent, "platform_params", {}) or {}).items():
        if normalize_platform(raw_platform) != target or not isinstance(values, Mapping):
            continue
        for key, value in values.items():
            if isinstance(value, Mapping) and isinstance(merged.get(key), Mapping):
                merged[key] = {**merged[key], **value}
            else:
                merged[key] = value
    return merged


def _schema_for_ref(tool_registry: Any, tool_ref: str) -> tuple[str, str, dict[str, Any]]:
    tool_name, schema_path = str(tool_ref).split(".", 1)
    definition = _tool_definition(tool_registry, tool_name)
    schema = getattr(definition, "input_schema", None) if definition else None
    properties = getattr(schema, "properties", {}) if schema else {}
    field_schema = _schema_at_path(properties or {}, schema_path) or {}
    return tool_name, schema_path, dict(field_schema) if isinstance(field_schema, Mapping) else {}


def _options(field: Mapping[str, Any], schema: Mapping[str, Any]) -> list[Any]:
    declared = field.get("options")
    if isinstance(declared, list) and declared:
        return list(declared)[:_MAX_OPTIONS]
    enum = schema.get("enum")
    if isinstance(enum, list):
        return list(enum)[:_MAX_OPTIONS]
    items = schema.get("items")
    if isinstance(items, Mapping) and isinstance(items.get("enum"), list):
        return list(items["enum"])[:_MAX_OPTIONS]
    return []


def _control_for(field: Mapping[str, Any], schema: Mapping[str, Any], options: list[Any]) -> str:
    presentation = str(field.get("presentation") or "").strip().lower()
    if presentation in _PRESENTATIONS:
        return presentation
    lookup_tool = schema.get("lookup_tool")
    if not lookup_tool and isinstance(schema.get("lookup"), Mapping):
        lookup_tool = schema["lookup"].get("tool")
    if str(field.get("source") or "").lower() == "lookup" or lookup_tool:
        return "lookup"
    if options:
        return "multiselect" if schema.get("type") == "array" else "select"
    field_type = schema.get("type")
    if field_type in ("number", "integer"):
        return "number"
    if field_type == "boolean":
        return "checkbox"
    if field_type == "object":
        return "object_editor"
    if field_type == "array" and isinstance(schema.get("items"), Mapping):
        if schema["items"].get("type") == "string":
            return "text_list"
    if field_type in ("object", "array") or isinstance(field_type, list):
        return "json"
    return "text"


def _selector_options(selector: Mapping[str, Any]) -> list[dict[str, Any]]:
    declared = selector.get("options")
    if isinstance(declared, list):
        values = []
        for item in declared[:_MAX_OPTIONS]:
            if isinstance(item, Mapping) and "value" in item:
                values.append({
                    "value": item.get("value"),
                    "label": str(item.get("label") or item.get("value")),
                })
        if values:
            return values
    return [{"value": value, "label": str(value)} for value in selector.get("values", [])[:_MAX_OPTIONS]]


def _normalized(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().replace("_", " ").split())


def _lookup_metadata(tool_registry: Any, schema: Mapping[str, Any]) -> dict[str, Any]:
    """Return provider-owned lookup metadata plus the source Tool contract.

    The source Tool is intentionally inspected here instead of inferred from
    a field name.  This means a provider can use a non-standard identifier or
    swap its endpoint without adding a Runtime/provider branch.
    """
    lookup = schema.get("lookup") if isinstance(schema.get("lookup"), Mapping) else {}
    lookup_tool = schema.get("lookup_tool") or lookup.get("tool")
    if not lookup_tool:
        return {}
    result: dict[str, Any] = {"tool": str(lookup_tool), "read_only": True}
    for source_key, result_key in (
        ("lookup_result_key", "result_key"),
        ("lookup_account_required", "account_required"),
        ("lookup_dependencies", "dependencies"),
        ("lookup_query_field", "query_field"),
    ):
        value = schema.get(source_key)
        if value is None and isinstance(lookup, Mapping):
            value = lookup.get(result_key)
        if value is not None:
            result[result_key] = value
    manual_entry = schema.get("manual_entry")
    if isinstance(manual_entry, Mapping):
        result["manual_entry"] = dict(manual_entry)

    definition = _tool_definition(tool_registry, str(lookup_tool))
    if definition is not None:
        required = set(getattr(getattr(definition, "input_schema", None), "required", []) or [])
        if "account_required" not in result:
            result["account_required"] = bool(
                required.intersection({"account_id", "advertiser_id", "customer_id"})
            )
    return result


class CreationCardBuilder:
    """Build bounded parameter cards from registered declarative metadata."""

    def __init__(
        self,
        blueprint_registry: BlueprintRegistry,
        tool_registry: Any,
        cascade: Optional[BlueprintCascadeEngine] = None,
    ) -> None:
        self.blueprints = blueprint_registry
        self.tools = tool_registry
        self.cascade = cascade or BlueprintCascadeEngine()

    @staticmethod
    def is_creation_intent(intent: ParsedIntent) -> bool:
        value = str(getattr(intent, "intent_type", "") or "").strip().lower()
        return value == "create_campaign" or value.startswith("create_")

    def llm_context(self, max_chars: int = 3500) -> str:
        """Return bounded Blueprint metadata for intent parsing only."""
        lines: list[str] = []
        for blueprint in self.blueprints.list()[:40]:
            selector = blueprint.selector or {}
            selector_text = ""
            if selector:
                selector_text = (
                    f"; selector={selector.get('dimension')}:{selector.get('values', [])}"
                )
            fields = []
            for field in blueprint.fields[:30]:
                tool_name, schema_path, schema = _schema_for_ref(self.tools, field["tool_ref"])
                if _SENSITIVE_FIELD.search(str(field.get("path"))) or _SENSITIVE_FIELD.search(schema_path):
                    continue
                field_type = schema.get("type", "string")
                fields.append(
                    f"{field['path']}->{tool_name}.{schema_path}"
                    f"({field_type}{',required' if field.get('required') else ''}"
                    f"{',options=' + str(_options(field, schema)[:12]) if _options(field, schema) else ''})"
                )
            lines.append(
                f"provider={blueprint.provider}; id={blueprint.blueprint_id}; "
                f"title={blueprint.title}{selector_text}; fields=" + ", ".join(fields)
            )
        return "\n".join(lines)[:max_chars]

    def _field_value(
        self, intent: ParsedIntent, provider_values: Mapping[str, Any], field: Mapping[str, Any]
    ) -> Any:
        tool_name, schema_path, _schema = _schema_for_ref(self.tools, field["tool_ref"])
        # Form submissions keep values both at the provider-neutral top level
        # and under the authoritative Tool name. Prefer the scoped copy so a
        # repeated field such as ``name`` cannot be overwritten by another
        # resource in the same Blueprint.
        scoped_values = provider_values.get(tool_name)
        value = (
            _value_at(scoped_values, schema_path)
            if isinstance(scoped_values, Mapping)
            else None
        )
        if value is None:
            value = _value_at(provider_values, schema_path)
        if value is None and "." in schema_path:
            value = _value_at(provider_values, schema_path.rsplit(".", 1)[-1])
        # Generic intent values can seed only the corresponding selector
        # dimension. They never invent a provider payload value.
        if value is None:
            if schema_path in {"objective", "objective_type"}:
                value = getattr(intent, "objective", None)
            elif schema_path in {"campaign_type", "advertising_channel_type"}:
                value = getattr(intent, "campaign_type", None)
        return value

    def _resolve(self, intent: ParsedIntent, provider: str) -> tuple[Optional[AdCreationBlueprint], Any, dict[str, Any]]:
        provider_values = _provider_values(intent, provider)
        candidates = self.blueprints.list(provider=provider)
        for blueprint in candidates:
            selector = blueprint.selector
            if selector is None:
                continue
            selected = None
            for field in blueprint.fields:
                if str(field.get("path")) == str(selector.get("field")):
                    selected = self._field_value(intent, provider_values, field)
                    break
            if selected is None:
                dimension = str(selector.get("dimension") or "")
                selected = provider_values.get(dimension)
                if selected is None and dimension == "objective":
                    selected = getattr(intent, "objective", None)
                if selected is None and dimension in {"ad_format", "campaign_type"}:
                    selected = getattr(intent, "campaign_type", None)
            if selected in selector.get("values", []):
                return blueprint, provider_values, selected
            for option in _selector_options(selector):
                if _normalized(selected) in {_normalized(option["value"]), _normalized(option["label"])}:
                    return blueprint, provider_values, option["value"]
        if len(candidates) == 1 and candidates[0].selector is None:
            return candidates[0], provider_values, None
        return None, provider_values, None

    def _selector_card(
        self, intent: ParsedIntent, provider: str, provider_values: Mapping[str, Any]
    ) -> Optional[dict[str, Any]]:
        candidates = [item for item in self.blueprints.list(provider=provider) if item.selector]
        if not candidates:
            return None
        dimensions: dict[str, dict[str, Any]] = {}
        for blueprint in candidates:
            selector = blueprint.selector or {}
            dimension = str(selector.get("dimension") or "")
            if not dimension:
                continue
            entry = dimensions.setdefault(dimension, {
                "path": selector.get("field", dimension),
                "provider_field": dimension,
                "label": selector.get("label") or dimension,
                "options": [],
            })
            for field in blueprint.fields:
                if str(field.get("path")) == str(selector.get("field")):
                    _tool_name, schema_path, _schema = _schema_for_ref(self.tools, field["tool_ref"])
                    entry["provider_field"] = schema_path
                    break
            for option in _selector_options(selector):
                if option not in entry["options"]:
                    entry["options"].append(option)
        if not dimensions:
            return None
        fields = []
        for dimension, item in list(dimensions.items())[:8]:
            current = provider_values.get(item["provider_field"])
            if current is None and item["provider_field"] != dimension:
                current = provider_values.get(dimension)
            if current is None:
                current = getattr(intent, "objective", None) if dimension == "objective" else getattr(intent, "campaign_type", None)
            valid_values = {option.get("value") for option in item["options"]}
            is_valid = current in valid_values or any(
                _normalized(current) == _normalized(option.get("value"))
                or _normalized(current) == _normalized(option.get("label"))
                for option in item["options"]
            )
            fields.append({
                "path": item["path"], "provider_field": item["provider_field"],
                "tool": "", "label": item["label"], "control": "select",
                "required": True, "state": "missing" if current is None else "set" if is_valid else "invalid",
                "value": current, "options": item["options"], "source": "blueprint",
            })
        return {
            "type": "ad_creation_selector", "version": "1.0", "id": f"{provider}.creation-selector",
            "title": f"选择 {provider} 广告创建类型", "provider": provider, "mode": "draft",
            "fields": fields,
            "missing_fields": [item["path"] for item in fields if item["value"] is None or item["state"] == "invalid"],
            "invalid_fields": [item["path"] for item in fields if item["state"] == "invalid"],
            "ready": False,
            "account_id": None,
            "account_required": True,
            "actions": [
                {"id": "continue_chat", "label": "继续用文字补充"},
                {"id": "open_form", "label": "打开填写表单"},
            ],
        }

    def _form_card(
        self, intent: ParsedIntent, blueprint: AdCreationBlueprint,
        provider_values: Mapping[str, Any], selector_value: Any,
    ) -> dict[str, Any]:
        values: dict[str, Any] = {}
        for field in blueprint.fields[:_MAX_FIELDS]:
            if _SENSITIVE_FIELD.search(str(field.get("path"))):
                continue
            values[str(field["path"])] = self._field_value(intent, provider_values, field)
        evaluation = self.cascade.evaluate(blueprint, values)
        state_by_path = {item["path"]: item for item in evaluation.get("fields", [])}
        fields: list[dict[str, Any]] = []
        for field in blueprint.fields[:_MAX_FIELDS]:
            path = str(field["path"])
            tool_name, schema_path, schema = _schema_for_ref(self.tools, field["tool_ref"])
            if _SENSITIVE_FIELD.search(path) or _SENSITIVE_FIELD.search(schema_path):
                continue
            state = dict(state_by_path.get(path) or {})
            options = _options(field, schema)
            value = values.get(path)
            if value is None:
                # Cascade-derived readonly fields (for example a Google
                # video ad-group type) are resolved from Blueprint metadata,
                # not selected again by the user.
                value = state.get("value")
            presentation = str(field.get("presentation") or "").strip().lower()
            if value is None and presentation == "derived_readonly" and len(options) == 1:
                # A one-option provider value is a contract default, not a
                # user decision. Include it in the draft and readiness state.
                value = options[0]
                values[path] = value
            item = {
                "path": path,
                "provider_field": schema_path,
                "tool": tool_name,
                "label": str(field.get("label") or path),
                "description": str(field.get("description") or schema.get("description") or ""),
                "control": _control_for(field, schema, options),
                "lookup_multiple": schema.get("type") == "array",
                "required": bool(state.get("required", field.get("required", False))),
                "visible": bool(state.get("visible", True)),
                "state": state.get("state", "optional"),
                "value": value,
                "source": field.get("source", "tool_schema"),
            }
            for metadata_key in ("presentation", "value_shape", "accept"):
                if field.get(metadata_key) is not None:
                    item[metadata_key] = field[metadata_key]
            if options:
                item["options"] = [
                    {"value": option, "label": str(option)} for option in options
                ]
            if item["control"] == "object_editor":
                properties = schema.get("properties") or {}
                item["object_properties"] = {
                    str(name): {
                        key: value
                        for key, value in {
                        "type": spec.get("type", "string"),
                            "description": spec.get("description", ""),
                            "enum": spec.get("enum"),
                            "items": spec.get("items"),
                            "lookup_tool": spec.get("lookup_tool"),
                            "lookup_result_key": spec.get("lookup_result_key"),
                            "selection_value_fields": spec.get("selection_value_fields"),
                            "selection_label_fields": spec.get("selection_label_fields"),
                            "lookup_account_required": spec.get("lookup_account_required"),
                            "lookup_dependencies": spec.get("lookup_dependencies"),
                            "lookup_query_field": spec.get("lookup_query_field"),
                            "manual_entry": spec.get("manual_entry"),
                            "required": name in (schema.get("required") or []),
                        }.items()
                        if value not in (None, "", {}, [])
                    }
                    for name, spec in properties.items()
                    if isinstance(spec, Mapping) and not _SENSITIVE_FIELD.search(str(name))
                }
            if item["control"] == "lookup":
                item["lookup"] = {
                    **_lookup_metadata(self.tools, schema),
                    "status": "available_without_call",
                }
            elif isinstance(field.get("manual_entry"), Mapping):
                item["manual_entry"] = dict(field["manual_entry"])
            elif isinstance(schema.get("manual_entry"), Mapping):
                item["manual_entry"] = dict(schema["manual_entry"])
            fields.append(item)
        return {
            "type": "ad_creation_form", "version": "1.0",
            "id": f"{blueprint.blueprint_id}@{blueprint.version}",
            "title": blueprint.title, "provider": blueprint.provider,
            "blueprint_id": blueprint.blueprint_id,
            "blueprint_version": blueprint.version, "mode": "draft",
            "selector": {"dimension": (blueprint.selector or {}).get("dimension"), "value": selector_value},
            "fields": fields,
            "missing_fields": list(evaluation.get("missing_fields", [])),
            "invalid_fields": list(evaluation.get("invalid_fields", [])),
            "ready": bool(evaluation.get("ready")),
            "account_id": None,
            "account_required": True,
            "actions": [
                {"id": "continue_chat", "label": "继续用文字补充"},
                {"id": "validate", "label": "检查参数"},
                {"id": "preview", "label": "生成预览"},
                {"id": "submit_create", "label": "提交创建"},
            ],
        }

    def build(self, intent: ParsedIntent) -> list[dict[str, Any]]:
        if not self.is_creation_intent(intent):
            return []
        cards: list[dict[str, Any]] = []
        for provider in list(getattr(intent, "platforms", []) or [])[:_MAX_CARDS]:
            canonical = normalize_platform(provider)
            blueprint, values, selector_value = self._resolve(intent, canonical)
            if blueprint is None:
                selector_card = self._selector_card(intent, canonical, values)
                if selector_card:
                    cards.append(selector_card)
                continue
            cards.append(self._form_card(intent, blueprint, values, selector_value))
        return cards[:_MAX_CARDS]
