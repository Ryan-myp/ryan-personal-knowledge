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
    _copy_json,
    _schema_at_path,
    _value_at,
)
from .interfaces import ParsedIntent
from .platform import normalize_platform


_MAX_CARDS = 8
# Creation forms must not silently truncate a provider contract.  The largest
# current Blueprint is TikTok Product Sales; keep a generous hard bound for a
# hostile/custom Capability while preserving a finite response size.
_MAX_FIELDS = 160
_MAX_OPTIONS = 100
_PRESENTATIONS = {
    "text_list", "asset_picker", "file_reference", "derived_readonly",
}
_SENSITIVE_FIELD = re.compile(
    r"(?:access[_-]?token|refresh[_-]?token|client[_-]?secret|app[_-]?secret|"
    r"private[_-]?key|developer[_-]?token|bc[_-]?id|partner[_-]?id|perter[_-]?id|mcc)",
    re.IGNORECASE,
)

# These values are execution context, not user-editable campaign parameters.
# Account scope is rendered once on the card and hierarchy parent IDs are
# produced by the preceding create step.  Provider-owned schemas may mark
# additional context-only fields with ``ui_hidden`` without changing Runtime.
_CONTEXT_FIELDS = {
    "account_id", "advertiser_id", "customer_id", "manager_customer_id",
}


def _humanize_field_name(name: str) -> str:
    """Create a stable fallback label when a Tool schema has no title."""
    return " ".join(
        part.upper() if len(part) <= 3 else part.capitalize()
        for part in str(name).replace("-", "_").split("_")
        if part
    ) or str(name)


def _schema_field_source(schema: Mapping[str, Any]) -> str:
    lookup_tool = schema.get("lookup_tool")
    if not lookup_tool and isinstance(schema.get("lookup"), Mapping):
        lookup_tool = schema["lookup"].get("tool")
    if lookup_tool:
        return "lookup"
    if isinstance(schema.get("enum"), list):
        return "enum"
    if isinstance(schema.get("items"), Mapping) and isinstance(schema["items"].get("enum"), list):
        return "enum"
    return "tool_schema"


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


def _schema_constraints(schema: Mapping[str, Any]) -> dict[str, Any]:
    """Expose non-executable validation facts to the form consumer."""
    keys = (
        "minLength", "maxLength", "minimum", "maximum", "exclusiveMinimum",
        "exclusiveMaximum", "minItems", "maxItems", "pattern", "format",
        "default", "known_values", "allow_custom",
    )
    result = {
        key: _copy_json(schema[key])
        for key in keys
        if schema.get(key) is not None
    }
    items = schema.get("items")
    if isinstance(items, Mapping):
        item_constraints = {
            key: _copy_json(items[key])
            for key in keys
            if items.get(key) is not None
        }
        if item_constraints:
            result["items"] = item_constraints
    return result


def _constraint_hint(schema: Mapping[str, Any]) -> str:
    """Make provider limits legible in the existing field-help UI."""
    hints: list[str] = []
    if schema.get("minItems") is not None:
        hints.append(f"至少 {schema['minItems']} 项")
    if schema.get("maxItems") is not None:
        hints.append(f"最多 {schema['maxItems']} 项")
    if schema.get("minLength") is not None:
        hints.append(f"最少 {schema['minLength']} 个字符")
    if schema.get("maxLength") is not None:
        hints.append(f"最多 {schema['maxLength']} 个字符")
    items = schema.get("items")
    if isinstance(items, Mapping):
        if items.get("minLength") is not None:
            hints.append(f"每项最少 {items['minLength']} 个字符")
        if items.get("maxLength") is not None:
            hints.append(f"每项最多 {items['maxLength']} 个字符")
    if schema.get("minimum") is not None:
        hints.append(f"最小值 {schema['minimum']}")
    if schema.get("maximum") is not None:
        hints.append(f"最大值 {schema['maximum']}")
    if schema.get("known_values") and schema.get("allow_custom"):
        hints.append("可选标准事件，也可填写自定义事件")
    return "；".join(hints)


def _option_label(field: Mapping[str, Any], option: Any) -> str:
    labels = field.get("option_labels")
    if isinstance(labels, Mapping):
        label = labels.get(str(option))
        if label is None:
            try:
                label = labels.get(option)
            except TypeError:
                label = None
        if label:
            return str(label)
    return str(option)


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


def _lookup_metadata(
    tool_registry: Any,
    schema: Mapping[str, Any],
    field: Optional[Mapping[str, Any]] = None,
) -> dict[str, Any]:
    """Return provider-owned lookup metadata plus the source Tool contract.

    The source Tool is intentionally inspected here instead of inferred from
    a field name.  This means a provider can use a non-standard identifier or
    swap its endpoint without adding a Runtime/provider branch.
    """
    lookup = schema.get("lookup") if isinstance(schema.get("lookup"), Mapping) else {}
    field = field if isinstance(field, Mapping) else {}
    lookup_tool = (
        schema.get("lookup_tool")
        or lookup.get("tool")
        or field.get("lookup_tool")
    )
    if not lookup_tool:
        return {}
    result: dict[str, Any] = {"tool": str(lookup_tool), "read_only": True}
    for source_key, result_key in (
        ("lookup_result_key", "result_key"),
        ("lookup_account_required", "account_required"),
        ("lookup_dependencies", "dependencies"),
        ("lookup_query_field", "query_field"),
        ("lookup_defaults", "lookup_defaults"),
    ):
        value = schema.get(source_key)
        if value is None and isinstance(lookup, Mapping):
            value = lookup.get(result_key)
        if value is None:
            value = field.get(source_key)
            if value is None and isinstance(field.get("lookup"), Mapping):
                value = field["lookup"].get(result_key)
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
    def _blueprint_condition(
        condition: Any, prefix: str, known_paths: Optional[set[str]] = None,
        alias_paths: Optional[Mapping[str, str]] = None,
    ) -> Optional[dict[str, Any]]:
        """Translate a ToolSchema condition into a Blueprint condition.

        Provider Tools use a compact same-tool shape such as
        ``{"budget_mode": "DAILY"}``, while Blueprints use explicit field
        paths.  This adapter is data-driven and does not know provider names.
        """
        if not isinstance(condition, Mapping):
            return None
        if "all" in condition:
            items = [
                item for item in (
                    CreationCardBuilder._blueprint_condition(
                        value, prefix, known_paths, alias_paths
                    )
                    for value in condition.get("all", [])
                ) if item is not None
            ]
            return {"all": items} if items else None
        if "any" in condition:
            items = [
                item for item in (
                    CreationCardBuilder._blueprint_condition(
                        value, prefix, known_paths, alias_paths
                    )
                    for value in condition.get("any", [])
                ) if item is not None
            ]
            return {"any": items} if items else None
        if "not" in condition:
            nested = CreationCardBuilder._blueprint_condition(
                condition.get("not"), prefix, known_paths, alias_paths
            )
            return {"not": nested} if nested else None
        if "field" in condition:
            field = str(condition.get("field") or "").strip()
            if not field:
                return None
            result = dict(condition)
            result["field"] = CreationCardBuilder._condition_path(
                field, prefix, known_paths, alias_paths
            )
            return result
        if not condition:
            return None
        return {
            "all": [
                {
                    "field": CreationCardBuilder._condition_path(
                        field, prefix, known_paths, alias_paths
                    ),
                    "equals": value,
                }
                for field, value in condition.items()
            ]
        }

    @staticmethod
    def _condition_path(
        field: str, prefix: str, known_paths: Optional[set[str]] = None,
        alias_paths: Optional[Mapping[str, str]] = None,
    ) -> str:
        if "." in field:
            return field
        candidate = f"{prefix}.{field}"
        if not known_paths or candidate in known_paths:
            return candidate
        alias_target = (alias_paths or {}).get(field)
        if alias_target and (not known_paths or alias_target in known_paths):
            return alias_target
        # A provider may use a same-named field in another Tool without
        # declaring an alias.  Only resolve an unambiguous leaf match; an
        # ambiguous match remains invalid instead of silently choosing a
        # different resource field.
        matches = sorted(
            path for path in known_paths
            if path.rsplit(".", 1)[-1] == field
        )
        return matches[0] if len(matches) == 1 else candidate

    @staticmethod
    def _condition_paths(condition: Any) -> set[str]:
        if not isinstance(condition, Mapping):
            return set()
        if "all" in condition or "any" in condition:
            key = "all" if "all" in condition else "any"
            return {
                path for item in condition.get(key, [])
                for path in CreationCardBuilder._condition_paths(item)
            }
        if "not" in condition:
            return CreationCardBuilder._condition_paths(condition.get("not"))
        field = condition.get("field")
        return {str(field)} if field else set()

    @staticmethod
    def _value_present(value: Any) -> bool:
        if value is None or value == "" or value == [] or value == {}:
            return False
        if isinstance(value, Mapping):
            return bool(value)
        if isinstance(value, (list, tuple, set)):
            return bool(value)
        return True

    def _contract_constraints(
        self, blueprint: AdCreationBlueprint, values: Mapping[str, Any]
    ) -> tuple[list[dict[str, Any]], list[str]]:
        """Project Tool any-of constraints onto visible Blueprint fields.

        Required/conditional fields are already represented on each field. A
        Tool-level source group (media vs. creative, daily vs. lifetime
        budget, etc.) needs a card-level explanation so a user does not have
        to understand the provider's wire schema. Only provider-declared
        constraints are projected; this method does not infer business rules.
        """
        field_index: dict[tuple[str, str], dict[str, Any]] = {}
        for field in blueprint.fields:
            tool_name, schema_path, _schema = _schema_for_ref(
                self.tools, str(field.get("tool_ref"))
            )
            field_index[(tool_name, schema_path)] = field

        constraints: list[dict[str, Any]] = []
        blocking: list[str] = []
        for tool_name in blueprint.tools:
            definition = _tool_definition(self.tools, tool_name)
            if definition is None:
                continue
            schema = getattr(definition, "input_schema", None)
            if schema is None:
                continue
            for constraint_type, groups in (
                ("any_of", getattr(schema, "provider_any_of", []) or []),
                ("exactly_one_of", getattr(schema, "provider_exactly_one_of", []) or []),
            ):
                for group in groups:
                    entries = []
                    for provider_field in group:
                        field = field_index.get((tool_name, str(provider_field)))
                        if field is None:
                            continue
                        path = str(field["path"])
                        entries.append({
                            "path": path,
                            "provider_field": str(provider_field),
                            "label": str(field.get("label") or provider_field),
                        })
                    if not entries:
                        # Do not make an unrendered provider alternative look
                        # satisfiable. It remains visible as an unresolved
                        # contract for Capability/Blueprint authors to fix.
                        entries = [{
                            "path": None,
                            "provider_field": str(provider_field),
                            "label": str(provider_field),
                        } for provider_field in group]
                    present = [
                        entry for entry in entries
                        if entry["path"] and self._value_present(values.get(entry["path"]))
                    ]
                    satisfied = (
                        bool(present) if constraint_type == "any_of"
                        else len(present) == 1
                    )
                    labels = "、".join(str(entry["label"]) for entry in entries)
                    if constraint_type == "any_of":
                        message = f"至少提供一项：{labels}"
                    else:
                        message = f"只能选择一项：{labels}"
                    item = {
                        "type": constraint_type,
                        "tool": tool_name,
                        "fields": entries,
                        "satisfied": satisfied,
                        "message": message,
                    }
                    constraints.append(item)
                    if not satisfied:
                        first_path = next(
                            (entry["path"] for entry in entries if entry["path"]),
                            None,
                        )
                        if first_path and first_path not in blocking:
                            blocking.append(first_path)
        return constraints, blocking

    def expand_blueprint(self, blueprint: AdCreationBlueprint) -> AdCreationBlueprint:
        """Expose every safe top-level create parameter in a Blueprint form.

        A Blueprint remains the place for ordering, copy and business-level
        cascades.  ToolSchema is the authoritative fallback for parameters,
        enums, defaults, conditional requirements and lookup descriptors.  A
        provider therefore adds a new field once, next to its Tool contract;
        the UI does not need a second manually maintained field inventory.
        """
        existing_fields = [dict(field) for field in blueprint.fields]
        known_refs = {str(field.get("tool_ref")) for field in existing_fields}
        declared_refs = set(known_refs)
        declared_paths = {str(field.get("path")) for field in existing_fields}
        known_paths = {str(field.get("path")) for field in existing_fields}
        prefix_by_tool: dict[str, str] = {}
        for field in existing_fields:
            tool_name, _, _ = _schema_for_ref(self.tools, str(field.get("tool_ref")))
            path = str(field.get("path") or "")
            if tool_name and "." in path:
                prefix_by_tool.setdefault(tool_name, path.split(".", 1)[0])

        # Build the complete safe path catalog before translating conditional
        # rules.  Tool schemas are allowed to declare a condition on a field
        # that appears later in ``properties``; validation must still see that
        # path as part of this Blueprint.
        definitions: dict[str, Any] = {}
        properties_by_tool: dict[str, Mapping[str, Any]] = {}
        for tool_name in blueprint.tools:
            definition = _tool_definition(self.tools, tool_name)
            if definition is None:
                continue
            definitions[tool_name] = definition
            schema_object = getattr(definition, "input_schema", None)
            properties = getattr(schema_object, "properties", {}) or {}
            if not isinstance(properties, Mapping):
                continue
            properties_by_tool[tool_name] = properties
            prefix = prefix_by_tool.get(tool_name)
            if not prefix:
                prefix = re.sub(
                    r"[^a-z0-9]+", "_",
                    str(getattr(definition, "resource_type", "resource") or "resource").lower(),
                ).strip("_") or "resource"
                prefix_by_tool[tool_name] = prefix

            parent_field = str(getattr(definition, "parent_resource_id_field", "") or "")
            resource_id_field = str(getattr(definition, "resource_id_field", "") or "")
            for field_name, raw_schema in properties.items():
                if not isinstance(raw_schema, Mapping):
                    continue
                field_name = str(field_name)
                if (
                    field_name in _CONTEXT_FIELDS
                    or field_name in {parent_field, resource_id_field}
                    or raw_schema.get("ui_hidden") is True
                ):
                    continue
                known_paths.add(f"{prefix}.{field_name}")

        # Resolve provider-declared input aliases to the canonical field path.
        # This keeps compatibility aliases out of the user form while allowing
        # conditional rules to refer to the same logical value across Tools.
        alias_paths: dict[str, str] = {}
        for tool_name, properties in properties_by_tool.items():
            prefix = prefix_by_tool[tool_name]
            for field_name, raw_schema in properties.items():
                if not isinstance(raw_schema, Mapping):
                    continue
                canonical_path = f"{prefix}.{field_name}"
                aliases = raw_schema.get("input_aliases")
                if isinstance(aliases, (list, tuple)) and canonical_path in known_paths:
                    for alias in aliases:
                        alias_name = str(alias).strip()
                        if alias_name and alias_name not in alias_paths:
                            alias_paths[alias_name] = canonical_path

        generated: list[dict[str, Any]] = []
        for tool_name in blueprint.tools:
            definition = definitions.get(tool_name)
            if definition is None:
                continue
            schema_object = getattr(definition, "input_schema", None)
            properties = properties_by_tool.get(tool_name, {})
            prefix = prefix_by_tool[tool_name]
            required = set(getattr(schema_object, "required", []) or [])
            required.update(getattr(schema_object, "provider_required", []) or [])
            parent_field = str(getattr(definition, "parent_resource_id_field", "") or "")
            resource_id_field = str(getattr(definition, "resource_id_field", "") or "")
            conditional_rules = getattr(schema_object, "conditional_rules", []) or []

            for field_name, raw_schema in properties.items():
                field_name = str(field_name)
                if not isinstance(raw_schema, Mapping):
                    continue
                if field_name in _CONTEXT_FIELDS or field_name in {parent_field, resource_id_field}:
                    continue
                if raw_schema.get("ui_hidden") is True:
                    continue
                tool_ref = f"{tool_name}.{field_name}"
                path = f"{prefix}.{field_name}"
                if tool_ref in declared_refs or path in declared_paths:
                    continue

                field: dict[str, Any] = {
                    "path": path,
                    "tool_ref": tool_ref,
                    "label": str(raw_schema.get("title") or _humanize_field_name(field_name)),
                    "description": str(raw_schema.get("description") or ""),
                    "required": field_name in required,
                    "source": _schema_field_source(raw_schema),
                    "auto_exposed": True,
                }
                for key in (
                    "default", "option_labels", "manual_entry", "lookup_tool",
                    "lookup_result_key", "selection_value_fields", "selection_label_fields",
                    "lookup_account_required", "lookup_dependencies", "lookup_query_field",
                    "lookup_defaults",
                    "accept", "presentation", "value_shape",
                ):
                    if key == "presentation" and raw_schema.get(key) not in _PRESENTATIONS:
                        continue
                    if raw_schema.get(key) is not None:
                        field[key] = _copy_json(raw_schema[key])

                required_conditions: list[dict[str, Any]] = []
                option_rules: list[dict[str, Any]] = []
                for rule in conditional_rules:
                    if not isinstance(rule, Mapping):
                        continue
                    condition = self._blueprint_condition(
                        rule.get("if", rule.get("when", {})), prefix,
                        known_paths, alias_paths,
                    )
                    if condition is None:
                        continue
                    if field_name in (rule.get("required") or rule.get("required_fields") or []):
                        required_conditions.append(condition)
                    allowed = rule.get("allowed")
                    if isinstance(allowed, Mapping) and isinstance(allowed.get(field_name), list):
                        option_rules.append({
                            "when": condition,
                            "options": _copy_json(allowed[field_name]),
                        })
                if required_conditions:
                    required_when = (
                        required_conditions[0]
                        if len(required_conditions) == 1
                        else {"any": required_conditions}
                    )
                    field["visible_when"] = _copy_json(required_when)
                    field["required_when"] = _copy_json(required_when)
                    field["options_from"] = sorted({
                        path for condition in required_conditions
                        for path in self._condition_paths(condition)
                    })
                if option_rules:
                    field["option_rules"] = option_rules
                    if "options_from" not in field:
                        field["options_from"] = sorted({
                            path for rule in option_rules
                            for path in self._condition_paths(rule.get("when"))
                        })
                generated.append(field)
                known_refs.add(tool_ref)
                known_paths.add(path)
                declared_refs.add(tool_ref)
                declared_paths.add(path)

        # Blueprint JSON intentionally keeps the human workflow concise, but
        # older/provider-authored files may already declare a field without
        # repeating every Tool contract attribute.  Enrich declared fields in
        # exactly the same way as auto-exposed fields so a lookup, enum,
        # default, conditional requirement, or input guide can never be lost
        # merely because the field was listed in the Blueprint.  This is also
        # what makes a provider contract the single source of truth for both
        # the form and execution validation.
        all_fields = existing_fields + generated
        field_metadata = (
            "default", "option_labels", "manual_entry", "lookup_tool",
            "lookup_result_key", "selection_value_fields", "selection_label_fields",
            "lookup_account_required", "lookup_dependencies", "lookup_query_field",
            "lookup_defaults", "accept", "presentation", "value_shape",
        )
        for field in all_fields:
            tool_ref = str(field.get("tool_ref") or "")
            if not tool_ref:
                continue
            tool_name, schema_path, schema = _schema_for_ref(self.tools, tool_ref)
            definition = definitions.get(tool_name)
            if definition is None or not schema:
                continue
            field_name = schema_path.rsplit(".", 1)[-1]
            schema_object = getattr(definition, "input_schema", None)
            required = set(getattr(schema_object, "required", []) or [])
            required.update(getattr(schema_object, "provider_required", []) or [])
            if field_name in required:
                field["required"] = True
            if not field.get("description"):
                field["description"] = str(schema.get("description") or "")
            if not field.get("source") or field.get("source") == "tool_schema":
                field["source"] = _schema_field_source(schema)
            for key in field_metadata:
                if key == "presentation" and schema.get(key) not in _PRESENTATIONS:
                    continue
                if field.get(key) is None and schema.get(key) is not None:
                    field[key] = _copy_json(schema[key])

            # A declared field may omit a provider conditional because the
            # Blueprint only described its happy path.  Project the schema's
            # declarative rule when the Blueprint has not provided one.
            if (
                not field.get("required_when")
                and not field.get("option_rules")
            ):
                prefix = prefix_by_tool.get(tool_name, "resource")
                conditional_rules = getattr(schema_object, "conditional_rules", []) or []
                required_conditions: list[dict[str, Any]] = []
                option_rules: list[dict[str, Any]] = []
                for rule in conditional_rules:
                    if not isinstance(rule, Mapping):
                        continue
                    condition = self._blueprint_condition(
                        rule.get("if", rule.get("when", {})), prefix,
                        known_paths, alias_paths,
                    )
                    if condition is None:
                        continue
                    if field_name in (rule.get("required") or rule.get("required_fields") or []):
                        required_conditions.append(condition)
                    allowed = rule.get("allowed")
                    # An explicit Blueprint option list is the workflow's
                    # initial domain (often fixed by its selector).  Do not
                    # replace it with an "awaiting dependency" state merely
                    # because a provider validation rule narrows that domain
                    # after another field is selected.
                    if (
                        "options" not in field
                        and isinstance(allowed, Mapping)
                        and isinstance(allowed.get(field_name), list)
                    ):
                        option_rules.append({
                            "when": condition,
                            "options": _copy_json(allowed[field_name]),
                        })
                if required_conditions:
                    required_when = (
                        required_conditions[0]
                        if len(required_conditions) == 1
                        else {"any": required_conditions}
                    )
                    field["visible_when"] = _copy_json(required_when)
                    field["required_when"] = _copy_json(required_when)
                    field["options_from"] = sorted({
                        path for condition in required_conditions
                        for path in self._condition_paths(condition)
                    })
                if option_rules:
                    field["option_rules"] = option_rules
                    if "options_from" not in field:
                        field["options_from"] = sorted({
                            path for rule in option_rules
                            for path in self._condition_paths(rule.get("when"))
                        })

        if not all_fields:
            return blueprint
        document = blueprint.to_dict()
        document["fields"] = all_fields
        return AdCreationBlueprint.from_dict(document)

    @staticmethod
    def is_creation_intent(intent: ParsedIntent) -> bool:
        value = str(getattr(intent, "intent_type", "") or "").strip().lower()
        return value == "create_campaign" or value.startswith("create_")

    def llm_context(self, max_chars: int = 3500) -> str:
        """Return bounded Blueprint metadata for intent parsing only."""
        lines: list[str] = []
        for raw_blueprint in self.blueprints.list()[:40]:
            blueprint = self.expand_blueprint(raw_blueprint)
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
        blueprint = self.expand_blueprint(blueprint)
        values: dict[str, Any] = {}
        for field in blueprint.fields[:_MAX_FIELDS]:
            if _SENSITIVE_FIELD.search(str(field.get("path"))):
                continue
            values[str(field["path"])] = self._field_value(intent, provider_values, field)
        option_sources: dict[str, list[Any]] = {}
        for field in blueprint.fields[:_MAX_FIELDS]:
            _tool_name, _schema_path, schema = _schema_for_ref(self.tools, field["tool_ref"])
            schema_options = _options(field, schema)
            if schema_options:
                option_sources[str(field["path"])] = schema_options
        evaluation = self.cascade.evaluate(blueprint, values, option_sources=option_sources)
        state_by_path = {item["path"]: item for item in evaluation.get("fields", [])}
        fields: list[dict[str, Any]] = []
        for field in blueprint.fields[:_MAX_FIELDS]:
            path = str(field["path"])
            tool_name, schema_path, schema = _schema_for_ref(self.tools, field["tool_ref"])
            if _SENSITIVE_FIELD.search(path) or _SENSITIVE_FIELD.search(schema_path):
                continue
            state = dict(state_by_path.get(path) or {})
            options = (
                list(state["options"])
                if "options" in state
                else _options(field, schema)
            )
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
                "control": (
                    "select"
                    if field.get("option_rules")
                    and state.get("options_state") in {"awaiting_dependency", "no_matching_rule"}
                    else _control_for(field, schema, options)
                ),
                "lookup_multiple": schema.get("type") == "array",
                "required": bool(state.get("required", field.get("required", False))),
                "visible": bool(state.get("visible", True)),
                "state": state.get("state", "optional"),
                "value": value,
                "source": field.get("source", "tool_schema"),
            }
            constraints = _schema_constraints(schema)
            if constraints:
                item["constraints"] = constraints
            hint = _constraint_hint(schema)
            if hint and hint not in item["description"]:
                item["description"] = (
                    f"{item['description']}（参数限制：{hint}）"
                    if item["description"] else f"参数限制：{hint}"
                )
            for metadata_key in ("presentation", "value_shape", "accept"):
                if field.get(metadata_key) is not None:
                    item[metadata_key] = field[metadata_key]
            if options:
                item["options"] = [
                    # ``label`` remains the stable wire-facing value for
                    # existing A2UI consumers. ``option_labels`` carries the
                    # provider-owned human label without changing that
                    # compatibility contract.
                    {"value": option, "label": str(option)} for option in options
                ]
                if isinstance(field.get("option_labels"), Mapping):
                    item["option_labels"] = {
                        str(option): _option_label(field, option) for option in options
                        if str(option) in field["option_labels"]
                    }
            if field.get("options_from"):
                item["options_from"] = list(field["options_from"])
            if state.get("options_state"):
                item["options_state"] = state["options_state"]
                item["missing_option_dependencies"] = list(
                    state.get("missing_option_dependencies") or []
                )
            if item["control"] == "object_editor":
                properties = schema.get("properties") or {}
                item["object_properties"] = {
                    str(name): {
                        key: value
                        for key, value in {
                            "type": spec.get("type", "string"),
                            "description": spec.get("description", ""),
                            "title": spec.get("title"),
                            "source": _schema_field_source(spec),
                            "enum": spec.get("enum"),
                            "option_labels": spec.get("option_labels"),
                            "items": spec.get("items"),
                            "lookup_tool": spec.get("lookup_tool"),
                            "lookup_result_key": spec.get("lookup_result_key"),
                            "selection_value_fields": spec.get("selection_value_fields"),
                            "selection_label_fields": spec.get("selection_label_fields"),
                            "lookup_account_required": spec.get("lookup_account_required"),
                            "lookup_dependencies": spec.get("lookup_dependencies"),
                            "lookup_query_field": spec.get("lookup_query_field"),
                            "lookup_defaults": spec.get("lookup_defaults"),
                            "manual_entry": spec.get("manual_entry"),
                            "constraints": _schema_constraints(spec),
                            "properties": _copy_json(spec.get("properties") or {})
                            if isinstance(spec.get("properties"), Mapping) else None,
                            "additional_properties": spec.get("additionalProperties"),
                            "required": name in (schema.get("required") or []),
                        }.items()
                        if value not in (None, "", {}, [])
                    }
                    for name, spec in properties.items()
                    if isinstance(spec, Mapping) and not _SENSITIVE_FIELD.search(str(name))
                }
            if item["control"] == "lookup":
                item["lookup"] = {
                    **_lookup_metadata(self.tools, schema, field),
                    "status": "available_without_call",
                }
            elif isinstance(field.get("manual_entry"), Mapping):
                item["manual_entry"] = dict(field["manual_entry"])
            elif isinstance(schema.get("manual_entry"), Mapping):
                item["manual_entry"] = dict(schema["manual_entry"])
            fields.append(item)
        constraints, blocking = self._contract_constraints(blueprint, values)
        missing_fields = list(evaluation.get("missing_fields", []))
        for path in blocking:
            if path not in missing_fields:
                missing_fields.append(path)
        return {
            "type": "ad_creation_form", "version": "1.0",
            "id": f"{blueprint.blueprint_id}@{blueprint.version}",
            "title": blueprint.title, "provider": blueprint.provider,
            "blueprint_id": blueprint.blueprint_id,
            "blueprint_version": blueprint.version, "mode": "draft",
            "selector": {"dimension": (blueprint.selector or {}).get("dimension"), "value": selector_value},
            "fields": fields,
            "missing_fields": missing_fields,
            "invalid_fields": list(evaluation.get("invalid_fields", [])),
            "ready": bool(evaluation.get("ready")) and not blocking,
            "constraints": constraints,
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
