"""Declarative ad-creation blueprints and cascade evaluation.

Blueprints describe how a creation surface is presented and how fields depend
on one another.  They are provider-owned metadata, not executable workflows:
the final request contract remains the registered ToolSchema and all external
calls still go through the Runtime execution boundary.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import json
import re
import threading
from typing import Any, Iterable, Mapping, Optional


class BlueprintValidationError(ValueError):
    """Raised when a blueprint is malformed or references an invalid Tool."""


_SAFE_SOURCES = {"tool_schema", "enum", "lookup", "static"}
_FORBIDDEN_KEYS = {
    "script", "scripts", "command", "commands", "exec", "execute",
    "eval", "expression", "python", "javascript", "mcp", "handler",
    "provider_client", "credentials", "access_token", "refresh_token",
}


def _require_non_empty(value: Any, name: str) -> str:
    result = str(value or "").strip()
    if not result:
        raise BlueprintValidationError(f"{name} must be a non-empty string")
    return result


def _copy_json(value: Any) -> Any:
    try:
        return deepcopy(value)
    except Exception as exc:  # pragma: no cover - defensive for callers
        raise BlueprintValidationError("blueprint contains non-copyable data") from exc


def _check_safe_data(value: Any, location: str = "blueprint") -> None:
    """Reject executable escape hatches while retaining JSON flexibility."""
    if isinstance(value, Mapping):
        for key, child in value.items():
            normalized = str(key).strip().lower()
            if normalized in _FORBIDDEN_KEYS:
                raise BlueprintValidationError(
                    f"{location}.{key} is not allowed in a declarative blueprint"
                )
            _check_safe_data(child, f"{location}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _check_safe_data(child, f"{location}[{index}]")


def _validate_condition(condition: Any, location: str) -> None:
    if not isinstance(condition, Mapping):
        raise BlueprintValidationError(f"{location} must be an object")
    if "all" in condition:
        items = condition["all"]
        if not isinstance(items, list) or not items:
            raise BlueprintValidationError(f"{location}.all must be a non-empty list")
        for index, item in enumerate(items):
            _validate_condition(item, f"{location}.all[{index}]")
        return
    if "any" in condition:
        items = condition["any"]
        if not isinstance(items, list) or not items:
            raise BlueprintValidationError(f"{location}.any must be a non-empty list")
        for index, item in enumerate(items):
            _validate_condition(item, f"{location}.any[{index}]")
        return
    if "not" in condition:
        _validate_condition(condition["not"], f"{location}.not")
        return
    field = condition.get("field")
    if not isinstance(field, str) or not field.strip():
        raise BlueprintValidationError(f"{location}.field is required")
    supported = {"field", "equals", "in", "not_in", "exists", "changed", "contains"}
    unknown = set(condition) - supported
    if unknown:
        raise BlueprintValidationError(
            f"{location} contains unsupported operators: {sorted(unknown)}"
        )
    if not any(key in condition for key in ("equals", "in", "not_in", "exists", "changed", "contains")):
        raise BlueprintValidationError(f"{location} needs a comparison operator")


def _condition_fields(condition: Mapping[str, Any]) -> set[str]:
    if "all" in condition:
        return {field for item in condition["all"] for field in _condition_fields(item)}
    if "any" in condition:
        return {field for item in condition["any"] for field in _condition_fields(item)}
    if "not" in condition:
        return _condition_fields(condition["not"])
    return {str(condition["field"])}


def _version_key(version: str) -> tuple[Any, ...]:
    """Sort semantic versions numerically while keeping non-semver versions safe."""
    match = re.fullmatch(r"v?(\d+)(?:\.(\d+))?(?:\.(\d+))?(?:-([0-9A-Za-z.-]+))?", version)
    if not match:
        return (0, version)
    major, minor, patch, prerelease = match.groups()
    return (
        1,
        int(major),
        int(minor or 0),
        int(patch or 0),
        0 if not prerelease else -1,
        prerelease or "",
    )


@dataclass(frozen=True)
class AdCreationBlueprint:
    """Immutable, JSON-backed description of one ad creation surface."""

    blueprint_id: str
    version: str
    provider: str
    ad_format: str
    title: str
    tools: tuple[str, ...]
    fields: tuple[dict[str, Any], ...]
    rules: tuple[dict[str, Any], ...]
    selector: Optional[dict[str, Any]]
    raw: dict[str, Any]

    @classmethod
    def from_dict(cls, document: Mapping[str, Any]) -> "AdCreationBlueprint":
        if not isinstance(document, Mapping):
            raise BlueprintValidationError("blueprint must be an object")
        _check_safe_data(document)
        blueprint_id = _require_non_empty(document.get("id"), "id")
        if not re.fullmatch(r"[a-z0-9][a-z0-9._-]*", blueprint_id):
            raise BlueprintValidationError("id must contain lowercase letters, digits, '.', '_' or '-'")
        version = _require_non_empty(document.get("version"), "version")
        provider = _require_non_empty(document.get("provider"), "provider")
        ad_format = _require_non_empty(document.get("ad_format"), "ad_format")
        title = str(document.get("title") or blueprint_id).strip()

        tools_value = document.get("tools")
        if not isinstance(tools_value, list) or not tools_value:
            raise BlueprintValidationError("tools must be a non-empty list")
        tools = tuple(_require_non_empty(item, "tools[]") for item in tools_value)
        if len(set(tools)) != len(tools):
            raise BlueprintValidationError("tools must not contain duplicates")

        fields_value = document.get("fields")
        if not isinstance(fields_value, list) or not fields_value:
            raise BlueprintValidationError("fields must be a non-empty list")
        fields: list[dict[str, Any]] = []
        field_paths: set[str] = set()
        for index, item in enumerate(fields_value):
            location = f"fields[{index}]"
            if not isinstance(item, Mapping):
                raise BlueprintValidationError(f"{location} must be an object")
            path = _require_non_empty(item.get("path"), f"{location}.path")
            tool_ref = _require_non_empty(item.get("tool_ref"), f"{location}.tool_ref")
            if "." not in tool_ref:
                raise BlueprintValidationError(f"{location}.tool_ref must be '<tool>.<field>'")
            if path in field_paths:
                raise BlueprintValidationError(f"duplicate blueprint field path: {path}")
            field_paths.add(path)
            source = str(item.get("source", "tool_schema")).strip().lower()
            if source not in _SAFE_SOURCES:
                raise BlueprintValidationError(f"{location}.source is unsupported: {source}")
            normalized = dict(item)
            normalized["path"] = path
            normalized["tool_ref"] = tool_ref
            normalized["source"] = source
            if "options" in normalized:
                options = normalized["options"]
                if not isinstance(options, list) or not options:
                    raise BlueprintValidationError(f"{location}.options must be a non-empty list")
                if len({json.dumps(value, sort_keys=True) for value in options}) != len(options):
                    raise BlueprintValidationError(f"{location}.options must not contain duplicates")
                if any(isinstance(value, (Mapping, list, tuple, set)) for value in options):
                    raise BlueprintValidationError(f"{location}.options must contain scalar values")
                normalized["options"] = _copy_json(options)
            if "visible_when" in normalized:
                _validate_condition(normalized["visible_when"], f"{location}.visible_when")
            if "required_when" in normalized:
                _validate_condition(normalized["required_when"], f"{location}.required_when")
            fields.append(normalized)

        field_paths = {str(item["path"]) for item in fields}

        selector_value = document.get("selector")
        selector: Optional[dict[str, Any]] = None
        if selector_value is not None:
            if not isinstance(selector_value, Mapping):
                raise BlueprintValidationError("selector must be an object")
            dimension = _require_non_empty(selector_value.get("dimension"), "selector.dimension")
            if not re.fullmatch(r"[a-z][a-z0-9_.-]*", dimension):
                raise BlueprintValidationError(
                    "selector.dimension must contain lowercase letters, digits, '.', '_' or '-'"
                )
            selector_field = _require_non_empty(selector_value.get("field"), "selector.field")
            values_value = selector_value.get("values")
            if not isinstance(values_value, list) or not values_value:
                raise BlueprintValidationError("selector.values must be a non-empty list")
            if len({json.dumps(value, sort_keys=True) for value in values_value}) != len(values_value):
                raise BlueprintValidationError("selector.values must not contain duplicates")
            if any(isinstance(value, (Mapping, list, tuple, set)) for value in values_value):
                raise BlueprintValidationError("selector.values must contain scalar values")
            normalized_selector = dict(selector_value)
            normalized_selector["dimension"] = dimension
            normalized_selector["field"] = selector_field
            normalized_selector["values"] = _copy_json(values_value)
            if "options" in normalized_selector:
                options = normalized_selector["options"]
                if not isinstance(options, list) or not all(isinstance(item, Mapping) for item in options):
                    raise BlueprintValidationError("selector.options must be a list of objects")
                for index, option in enumerate(options):
                    if "value" not in option or "label" not in option:
                        raise BlueprintValidationError(
                            f"selector.options[{index}] needs value and label"
                        )
                normalized_selector["options"] = _copy_json(options)
            selector = normalized_selector
            if selector_field not in field_paths:
                raise BlueprintValidationError(
                    f"selector.field references unknown field: {selector_field}"
                )

        for index, field in enumerate(fields):
            for condition_key in ("visible_when", "required_when"):
                condition = field.get(condition_key)
                if condition is None:
                    continue
                unknown = _condition_fields(condition) - field_paths
                if unknown:
                    raise BlueprintValidationError(
                        f"fields[{index}].{condition_key} references unknown fields: {sorted(unknown)}"
                    )

        rules_value = document.get("rules", [])
        if not isinstance(rules_value, list):
            raise BlueprintValidationError("rules must be a list")
        rules: list[dict[str, Any]] = []
        for index, item in enumerate(rules_value):
            location = f"rules[{index}]"
            if not isinstance(item, Mapping):
                raise BlueprintValidationError(f"{location} must be an object")
            if "when" not in item:
                raise BlueprintValidationError(f"{location}.when is required")
            _validate_condition(item["when"], f"{location}.when")
            normalized = dict(item)
            for effect in ("reset", "revalidate", "preserve", "ask"):
                if effect in normalized:
                    values = normalized[effect]
                    if not isinstance(values, list) or not all(isinstance(value, str) and value.strip() for value in values):
                        raise BlueprintValidationError(f"{location}.{effect} must be a list of field paths")
                    normalized[effect] = [str(value).strip() for value in values]
            rules.append(normalized)

        for index, rule in enumerate(rules):
            unknown = _condition_fields(rule["when"]) - field_paths
            if unknown:
                raise BlueprintValidationError(
                    f"rules[{index}].when references unknown fields: {sorted(unknown)}"
                )
            for effect in ("reset", "revalidate", "preserve", "ask"):
                unknown_targets = set(rule.get(effect, [])) - field_paths
                if unknown_targets:
                    raise BlueprintValidationError(
                        f"rules[{index}].{effect} references unknown fields: {sorted(unknown_targets)}"
                    )

        raw = _copy_json(dict(document))
        raw["id"] = blueprint_id
        raw["version"] = version
        raw["provider"] = provider
        raw["ad_format"] = ad_format
        raw["title"] = title
        raw["tools"] = list(tools)
        raw["fields"] = fields
        raw["rules"] = rules
        if selector is not None:
            raw["selector"] = _copy_json(selector)
        else:
            raw.pop("selector", None)
        return cls(
            blueprint_id=blueprint_id,
            version=version,
            provider=provider,
            ad_format=ad_format,
            title=title,
            tools=tools,
            fields=tuple(_copy_json(fields)),
            rules=tuple(_copy_json(rules)),
            selector=_copy_json(selector) if selector is not None else None,
            raw=raw,
        )

    def to_dict(self) -> dict[str, Any]:
        return _copy_json(self.raw)


def load_blueprint_file(path: Any) -> AdCreationBlueprint:
    """Load one JSON blueprint file; no code or custom loader is executed."""
    try:
        with open(path, "r", encoding="utf-8") as file:
            document = json.load(file)
    except (OSError, ValueError, TypeError) as exc:
        raise BlueprintValidationError(f"unable to load blueprint {path}: {exc}") from exc
    return AdCreationBlueprint.from_dict(document)


def _tool_definition(tool_registry: Any, name: str) -> Any:
    getter = getattr(tool_registry, "get", None)
    if not callable(getter):
        raise BlueprintValidationError("tool registry must expose get(name)")
    try:
        value = getter(name)
    except (KeyError, LookupError):
        value = None
    if isinstance(value, tuple):
        return value[0] if value else None
    return value


def _schema_at_path(properties: Mapping[str, Any], path: str) -> Optional[Mapping[str, Any]]:
    """Resolve a possibly nested JSON-schema property without provider logic."""
    current: Any = properties
    parts = [part for part in str(path or "").split(".") if part]
    if not parts:
        return None
    for index, part in enumerate(parts):
        if not isinstance(current, Mapping) or part not in current:
            return None
        candidate = current[part]
        if index == len(parts) - 1:
            return candidate if isinstance(candidate, Mapping) else None
        if not isinstance(candidate, Mapping):
            return None
        current = candidate.get("properties", {})
    return None


def validate_blueprint_against_tools(
    blueprint: AdCreationBlueprint, tool_registry: Any
) -> None:
    """Ensure every declarative field points to a registered Tool schema."""
    registered = set(blueprint.tools)
    field_schemas: dict[str, Mapping[str, Any]] = {}
    for index, field in enumerate(blueprint.fields):
        tool_ref = str(field["tool_ref"])
        # Tool names are opaque identifiers; the remainder is a schema path so
        # nested provider objects can be represented without a Core/provider
        # branch (for example ``targeting.age_groups``).
        tool_name, schema_field = tool_ref.split(".", 1)
        if tool_name not in registered:
            raise BlueprintValidationError(
                f"fields[{index}] references Tool outside blueprint.tools: {tool_name}"
            )
        definition = _tool_definition(tool_registry, tool_name)
        if definition is None:
            raise BlueprintValidationError(f"blueprint Tool is not registered: {tool_name}")
        schema = getattr(definition, "input_schema", None)
        properties = getattr(schema, "properties", {}) if schema is not None else {}
        field_schema = _schema_at_path(properties or {}, schema_field)
        if field_schema is None:
            raise BlueprintValidationError(
                f"fields[{index}] references missing Tool field: {tool_ref}"
            )
        if isinstance(field_schema, Mapping):
            field_schemas[str(field["path"])] = field_schema
            declared_options = field.get("options")
            if isinstance(declared_options, list):
                allowed = field_schema.get("enum")
                if not isinstance(allowed, list) and isinstance(field_schema.get("items"), Mapping):
                    allowed = field_schema["items"].get("enum")
                if isinstance(allowed, list):
                    unsupported = set(declared_options) - set(allowed)
                    if unsupported:
                        raise BlueprintValidationError(
                            f"unsupported options for {tool_ref}: {sorted(unsupported, key=str)}"
                        )
        if str(getattr(definition, "platform", "")).strip().lower() != blueprint.provider.lower():
            raise BlueprintValidationError(
                f"blueprint provider {blueprint.provider!r} does not match {tool_name}"
            )
        if field.get("source") == "lookup":
            lookup_tool = field.get("lookup_tool")
            schema_field_spec = field_schema
            schema_lookup = schema_field_spec.get("lookup_tool")
            if isinstance(schema_field_spec.get("lookup"), Mapping):
                schema_lookup = schema_lookup or schema_field_spec["lookup"].get("tool")
            if lookup_tool and schema_lookup and str(lookup_tool) != str(schema_lookup):
                raise BlueprintValidationError(
                    f"lookup Tool mismatch for {tool_ref}: {lookup_tool!r} != {schema_lookup!r}"
                )
            lookup_name = str(lookup_tool or schema_lookup or "").strip()
            if not lookup_name:
                raise BlueprintValidationError(f"lookup field has no lookup Tool: {tool_ref}")
            lookup_definition = _tool_definition(tool_registry, lookup_name)
            if lookup_definition is None:
                raise BlueprintValidationError(f"lookup Tool is not registered: {lookup_name}")
            if not getattr(lookup_definition, "is_read_tool", False):
                raise BlueprintValidationError(f"lookup Tool must be read-only: {lookup_name}")
    if blueprint.selector is not None:
        selector_schema = field_schemas.get(str(blueprint.selector["field"]))
        allowed = selector_schema.get("enum") if selector_schema else None
        if not isinstance(allowed, list) and selector_schema and isinstance(selector_schema.get("items"), Mapping):
            allowed = selector_schema["items"].get("enum")
        if isinstance(allowed, list):
            unsupported = set(blueprint.selector["values"]) - set(allowed)
            if unsupported:
                raise BlueprintValidationError(
                    f"unsupported selector values for {blueprint.selector['field']}: "
                    f"{sorted(unsupported, key=str)}"
                )


class BlueprintRegistry:
    """Process-local registry populated by Capability plugins at startup."""

    def __init__(self) -> None:
        self._items: dict[tuple[str, str], AdCreationBlueprint] = {}
        self._owners: dict[tuple[str, str], str] = {}
        self._lock = threading.RLock()

    def register(
        self,
        blueprint: AdCreationBlueprint,
        *,
        owner: Optional[str] = None,
        tool_registry: Any = None,
    ) -> None:
        if not isinstance(blueprint, AdCreationBlueprint):
            raise TypeError("blueprint must be an AdCreationBlueprint")
        if tool_registry is not None:
            validate_blueprint_against_tools(blueprint, tool_registry)
        key = (blueprint.blueprint_id, blueprint.version)
        with self._lock:
            previous = self._items.get(key)
            if previous is not None and previous.to_dict() != blueprint.to_dict():
                raise BlueprintValidationError(
                    f"conflicting blueprint version: {blueprint.blueprint_id}@{blueprint.version}"
                )
            self._items[key] = blueprint
            if owner:
                self._owners[key] = str(owner)

    def register_many(
        self,
        blueprints: Iterable[AdCreationBlueprint],
        *,
        owner: Optional[str] = None,
        tool_registry: Any = None,
    ) -> None:
        values = list(blueprints or [])
        for blueprint in values:
            if tool_registry is not None:
                validate_blueprint_against_tools(blueprint, tool_registry)
        for blueprint in values:
            self.register(blueprint, owner=owner, tool_registry=None)

    def remove_owner(self, owner: str) -> None:
        owner = str(owner)
        with self._lock:
            keys = [key for key, value in self._owners.items() if value == owner]
            for key in keys:
                self._items.pop(key, None)
                self._owners.pop(key, None)

    def snapshot(self) -> tuple[dict[tuple[str, str], AdCreationBlueprint], dict[tuple[str, str], str]]:
        with self._lock:
            return dict(self._items), dict(self._owners)

    def restore(self, snapshot: tuple[dict[tuple[str, str], AdCreationBlueprint], dict[tuple[str, str], str]]) -> None:
        with self._lock:
            self._items = dict(snapshot[0])
            self._owners = dict(snapshot[1])

    def list(
        self, provider: Optional[str] = None, ad_format: Optional[str] = None,
        selector_dimension: Optional[str] = None,
        selector_value: Any = None,
    ) -> list[AdCreationBlueprint]:
        provider = str(provider).strip().lower() if provider else None
        ad_format = str(ad_format).strip() if ad_format else None
        selector_dimension = str(selector_dimension).strip() if selector_dimension else None
        with self._lock:
            values = [
                blueprint for blueprint in self._items.values()
                if (provider is None or blueprint.provider.lower() == provider)
                and (ad_format is None or blueprint.ad_format == ad_format)
                and (
                    selector_dimension is None
                    or (
                        blueprint.selector is not None
                        and blueprint.selector.get("dimension") == selector_dimension
                        and (
                            selector_value is None
                            or selector_value in blueprint.selector.get("values", [])
                        )
                    )
                )
            ]
        return sorted(values, key=lambda item: (item.provider, item.ad_format, item.blueprint_id, item.version))

    def resolve(
        self,
        provider: str,
        *,
        selector_values: Optional[Mapping[str, Any]] = None,
        values: Optional[Mapping[str, Any]] = None,
        version: Optional[str] = None,
    ) -> Optional[AdCreationBlueprint]:
        """Resolve a provider-owned Blueprint from its declared selector.

        The registry deliberately has no provider branches.  A caller supplies
        selector values such as ``{"objective": "OUTCOME_LEADS"}`` or
        ``{"ad_format": "SEARCH"}``; the Blueprint declares how that value is
        read and which values it accepts.
        """
        provider_key = str(provider or "").strip().lower()
        requested = dict(selector_values or {})
        nested_values = values if isinstance(values, Mapping) else {}
        with self._lock:
            candidates = [
                blueprint for blueprint in self._items.values()
                if blueprint.provider.lower() == provider_key
                and (version is None or blueprint.version == str(version))
            ]
        matching: list[AdCreationBlueprint] = []
        for blueprint in candidates:
            selector = blueprint.selector
            if selector is None:
                if not requested:
                    matching.append(blueprint)
                continue
            dimension = str(selector["dimension"])
            selected = requested.get(dimension)
            if selected is None:
                selected = _value_at(nested_values, str(selector["field"]))
            if selected in selector.get("values", []):
                matching.append(blueprint)
        if not matching:
            return None
        # Multiple immutable versions of the same Blueprint ID resolve to the
        # newest version. Different IDs remain ambiguous rather than silently
        # selecting a provider-specific default.
        by_id: dict[str, AdCreationBlueprint] = {}
        for blueprint in matching:
            current = by_id.get(blueprint.blueprint_id)
            if current is None or _version_key(blueprint.version) > _version_key(current.version):
                by_id[blueprint.blueprint_id] = blueprint
        if len(by_id) != 1:
            return None
        return next(iter(by_id.values()))

    def get(self, blueprint_id: str, version: Optional[str] = None) -> Optional[AdCreationBlueprint]:
        with self._lock:
            if version is not None:
                return self._items.get((str(blueprint_id), str(version)))
            candidates = [
                blueprint for (item_id, _), blueprint in self._items.items()
                if item_id == str(blueprint_id)
            ]
        if not candidates:
            return None
        return sorted(candidates, key=lambda item: _version_key(item.version))[-1]

    def to_dict(
        self, provider: Optional[str] = None, ad_format: Optional[str] = None,
        selector_dimension: Optional[str] = None, selector_value: Any = None,
    ) -> list[dict[str, Any]]:
        return [
            blueprint.to_dict()
            for blueprint in self.list(provider, ad_format, selector_dimension, selector_value)
        ]


def _value_at(values: Mapping[str, Any], path: str) -> Any:
    if path in values:
        return values[path]
    current: Any = values
    for part in str(path).split("."):
        if not isinstance(current, Mapping) or part not in current:
            return None
        current = current[part]
    return current


def _has_value(value: Any) -> bool:
    return value is not None and value != "" and value != []


def _condition_matches(condition: Mapping[str, Any], values: Mapping[str, Any], changed: set[str]) -> bool:
    if "all" in condition:
        return all(_condition_matches(item, values, changed) for item in condition["all"])
    if "any" in condition:
        return any(_condition_matches(item, values, changed) for item in condition["any"])
    if "not" in condition:
        return not _condition_matches(condition["not"], values, changed)
    field = str(condition["field"])
    value = _value_at(values, field)
    if "equals" in condition and value != condition["equals"]:
        return False
    if "in" in condition and value not in condition["in"]:
        return False
    if "not_in" in condition and value in condition["not_in"]:
        return False
    if "exists" in condition and _has_value(value) != bool(condition["exists"]):
        return False
    if "changed" in condition and (field in changed) != bool(condition["changed"]):
        return False
    if "contains" in condition:
        if not isinstance(value, (list, tuple, set, str)) or condition["contains"] not in value:
            return False
    return True


class BlueprintCascadeEngine:
    """Deterministic evaluator for visibility, requiredness and field impact."""

    def evaluate(
        self,
        blueprint: AdCreationBlueprint,
        values: Mapping[str, Any],
        *,
        previous_values: Optional[Mapping[str, Any]] = None,
        changed_fields: Optional[Iterable[str]] = None,
    ) -> dict[str, Any]:
        current = values if isinstance(values, Mapping) else {}
        previous = previous_values if isinstance(previous_values, Mapping) else {}
        changed = {str(path) for path in (changed_fields or ())}
        if previous_values is not None and changed_fields is None:
            for field in blueprint.fields:
                path = str(field["path"])
                if _value_at(previous, path) != _value_at(current, path):
                    changed.add(path)

        reset: list[str] = []
        revalidate: list[str] = []
        preserve: list[str] = []
        ask: list[str] = []
        active_rules: list[str] = []
        for index, rule in enumerate(blueprint.rules):
            if not _condition_matches(rule["when"], current, changed):
                continue
            active_rules.append(str(rule.get("id") or f"rule-{index + 1}"))
            for target, output in (("reset", reset), ("revalidate", revalidate), ("preserve", preserve), ("ask", ask)):
                output.extend(str(path) for path in rule.get(target, []) or [])

        def unique(items: list[str]) -> list[str]:
            return list(dict.fromkeys(items))

        field_states: list[dict[str, Any]] = []
        missing: list[str] = []
        invalid: list[str] = []
        for field in blueprint.fields:
            path = str(field["path"])
            visible = True
            if "visible_when" in field:
                visible = _condition_matches(field["visible_when"], current, changed)
            required = bool(field.get("required", False)) if visible else False
            if visible and "required_when" in field:
                required = _condition_matches(field["required_when"], current, changed)
            value = _value_at(current, path)
            is_invalid = (
                visible
                and
                _has_value(value)
                and isinstance(field.get("options"), list)
                and value not in field["options"]
            )
            if is_invalid:
                invalid.append(path)
            is_missing = visible and required and not _has_value(value)
            if is_missing:
                missing.append(path)
            state = "hidden" if not visible else ("invalid" if is_invalid else "missing" if is_missing else "set" if _has_value(value) else "optional")
            item = {
                "path": path,
                "tool_ref": field["tool_ref"],
                "label": field.get("label", path),
                "description": field.get("description", ""),
                "visible": visible,
                "required": required,
                "state": state,
                "value": _copy_json(value),
                "source": field.get("source", "tool_schema"),
            }
            if "options" in field:
                item["options"] = _copy_json(field["options"])
            if "options_from" in field:
                item["options_from"] = _copy_json(field["options_from"])
            field_states.append(item)

        reset = unique(reset)
        revalidate = unique(revalidate)
        preserve = unique(preserve)
        ask = unique(ask)
        return {
            "blueprint_id": blueprint.blueprint_id,
            "blueprint_version": blueprint.version,
            "provider": blueprint.provider,
            "ad_format": blueprint.ad_format,
            "selector": _copy_json(blueprint.selector),
            "fields": field_states,
            "changed_fields": sorted(changed),
            "active_rules": active_rules,
            "reset_fields": reset,
            "revalidate_fields": revalidate,
            "preserve_fields": preserve,
            "ask_fields": ask,
            "missing_fields": missing,
            "invalid_fields": invalid,
            "ready": not missing and not invalid,
        }
