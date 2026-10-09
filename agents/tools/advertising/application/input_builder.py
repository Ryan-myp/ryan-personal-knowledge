"""Schema-driven Tool input construction from generic Agent state."""

from __future__ import annotations

import copy
import re
from typing import Any, Callable, Iterable, Optional

from agents.agent_harness.core.interfaces import ToolContext
from agents.agent_harness.core.tool_registry import validate_tool_input
from .parameter_selection import ParameterSelectionService


class ToolInputBuilder:
    """Project publisher-declared input metadata into validated Tool inputs."""

    def __init__(
        self,
        services: Any,
        *,
        scope_field_names: Iterable[str] = (),
        scope_value_resolver: Optional[Callable[[ToolContext], Any]] = None,
    ):
        self.services = services
        self.scope_field_names = tuple(
            dict.fromkeys(str(item) for item in (scope_field_names or ()) if str(item))
        )
        self.scope_value_resolver = scope_value_resolver
        self.parameter_selection = ParameterSelectionService(
            services,
            scope_value_resolver=scope_value_resolver,
        )

    def scope_value(self, ctx: Optional[ToolContext]) -> Any:
        if ctx is None or not callable(self.scope_value_resolver):
            return None
        return self.scope_value_resolver(ctx)

    def platform_params_for_intent(
        self, intent: Any, platform: str,
    ) -> dict[str, Any]:
        requested = self.services.normalize_namespace(platform)
        merged: dict[str, Any] = {}
        scoped = getattr(intent, "scoped_parameters", {}) or {}
        for raw_platform, values in scoped.items():
            if self.services.normalize_namespace(str(raw_platform)) != requested:
                continue
            if not isinstance(values, dict):
                continue
            for key, value in values.items():
                if isinstance(value, dict) and isinstance(merged.get(key), dict):
                    merged[key] = {**merged[key], **copy.deepcopy(value)}
                else:
                    merged[key] = copy.deepcopy(value)
        return merged

    @staticmethod
    def platform_date_range(
        platform: str,
        date_range: Any,
        tool_def: Any = None,
        field_name: str = "date_preset",
    ) -> Any:
        del platform
        if not isinstance(date_range, str) or tool_def is None:
            return date_range
        properties = getattr(
            getattr(tool_def, "input_schema", None), "properties", {}
        ) or {}
        field_schema = properties.get(field_name, {})
        if not isinstance(field_schema, dict):
            return date_range
        mapping = field_schema.get("intent_map") or {}
        return mapping.get(date_range, mapping.get(date_range.upper(), date_range))

    @staticmethod
    def normalize_provider_updates(
        tool_def: Any, updates: dict[str, Any],
    ) -> dict[str, Any]:
        normalized = dict(updates)
        if "status" not in normalized:
            return normalized
        properties = getattr(tool_def.input_schema, "properties", {}) or {}
        update_schema = properties.get("updates") or {}
        status_schema = (update_schema.get("properties") or {}).get("status", {})
        status = str(normalized.get("status", "")).upper()
        status_map = status_schema.get("intent_status_map") or {}
        status_field = status_schema.get("intent_status_field", "status")
        if status in status_map:
            if status_field != "status":
                normalized.pop("status", None)
            normalized[status_field] = status_map[status]
        return normalized

    @staticmethod
    def _normalize_input_field(value: Any) -> str:
        return re.sub(r"[^a-z0-9]", "", str(value or "").lower())

    def input_candidates(
        self,
        field_name: str,
        field_schema: Any,
        available_keys: Any = (),
        declared_fields: Any = (),
    ) -> list[str]:
        candidates = [str(field_name)]
        if isinstance(field_schema, dict):
            candidates.extend(
                str(value) for value in field_schema.get("input_aliases", []) or []
            )
            candidates.extend(
                str(value) for value in field_schema.get("intent_aliases", []) or []
            )
        keys = [str(key) for key in (available_keys or ())]
        normalized = self._normalize_input_field(field_name)
        scope_fields = {
            self._normalize_input_field(value) for value in self.scope_field_names
        }
        declared = {
            self._normalize_input_field(value)
            for value in (declared_fields or ())
            if str(value) != str(field_name)
        }
        for key in keys:
            key_normalized = self._normalize_input_field(key)
            if key_normalized == normalized:
                candidates.append(key)
            elif field_name == "name" and key_normalized.endswith("name"):
                candidates.append(key)
            elif key_normalized == normalized + "s" and key_normalized not in declared:
                candidates.append(key)
            elif normalized in scope_fields and key_normalized in scope_fields:
                candidates.append(key)
        return list(dict.fromkeys(candidates))

    def build(
        self,
        tool_def: Any,
        intent: Any,
        platform: str,
        ctx: Optional[ToolContext] = None,
    ) -> dict[str, Any]:
        services = self.services
        platform_params = self.platform_params_for_intent(intent, platform)
        actual_platform = services.normalize_namespace(platform)
        tool_input: dict[str, Any] = {}
        properties = getattr(tool_def.input_schema, "properties", {}) or {}
        specific_params = platform_params.get(tool_def.name, {})
        unknown_specific_params: list[str] = []
        if isinstance(specific_params, dict):
            platform_params = {**platform_params, **specific_params}
            accepted = set(tool_def.input_schema.properties)
            accepted.update(self.scope_field_names + ("selection_tokens",))
            for field_name, schema in tool_def.input_schema.properties.items():
                accepted.update(self.input_candidates(
                    field_name,
                    schema,
                    specific_params.keys(),
                    declared_fields=properties,
                ))
            unknown_specific_params = sorted(
                key for key in specific_params if key not in accepted
            )

        trusted_state_fields: set[str] = set()
        for field_name, schema in properties.items():
            for candidate in self.input_candidates(
                field_name, schema, platform_params.keys(), declared_fields=properties,
            ):
                if candidate in platform_params and platform_params[candidate] not in (None, ""):
                    tool_input[field_name] = platform_params[candidate]
                    break

        scope_value = self.scope_value(ctx)
        if scope_value not in (None, ""):
            for scope_field in self.scope_field_names:
                if scope_field in properties and scope_field not in tool_input:
                    tool_input[scope_field] = scope_value
                    break

        if ctx:
            protected = getattr(ctx, "protected_state", {}) or {}
            scoped_keys_exist = any(":" in key for key in protected)
            state_fields = [str(key).rsplit(":", 1)[-1] for key in protected]
            for field_name, schema in properties.items():
                if field_name in tool_input:
                    continue
                for candidate in self.input_candidates(
                    field_name, schema, state_fields, declared_fields=properties,
                ):
                    scoped_value = next((
                        protected[key]
                        for key in (
                            f"{actual_platform}:{candidate}",
                            f"{platform}:{candidate}",
                        )
                        if key in protected and protected[key] not in (None, "")
                    ), None)
                    if scoped_value is not None:
                        tool_input[field_name] = scoped_value
                        trusted_state_fields.add(field_name)
                        break
                    if (
                        not scoped_keys_exist
                        and candidate in protected
                        and protected[candidate] not in (None, "")
                    ):
                        tool_input[field_name] = protected[candidate]
                        trusted_state_fields.add(field_name)
                        break

        intent_values = dict(getattr(intent, "attributes", {}) or {})
        for field_name, schema in properties.items():
            if field_name in tool_input or not isinstance(schema, dict):
                continue
            intent_field = str(schema.get("intent_field") or field_name)
            candidates = [intent_field]
            aliases = schema.get("intent_aliases", []) or []
            if isinstance(aliases, (list, tuple, set, frozenset)):
                candidates.extend(str(alias) for alias in aliases)
            for candidate in candidates:
                value = intent_values.get(candidate)
                if value in (None, "", {}, []):
                    continue
                mapping = schema.get("intent_map") or {}
                if isinstance(mapping, dict):
                    value = mapping.get(
                        str(value).lower(), mapping.get(str(value).upper(), value),
                    )
                tool_input[field_name] = copy.deepcopy(value)
                break

        intent_type = str(getattr(intent, "intent_type", "") or "")
        for field_name, schema in properties.items():
            if field_name in tool_input or not isinstance(schema, dict):
                continue
            defaults = schema.get("intent_defaults")
            default = defaults.get(intent_type) if isinstance(defaults, dict) else None
            if isinstance(default, dict):
                tool_input[field_name] = copy.deepcopy(default)

        for field_name, schema in properties.items():
            if field_name not in tool_input and isinstance(schema, dict) and "default" in schema:
                tool_input[field_name] = copy.deepcopy(schema["default"])

        if "name" in tool_def.input_schema.required and "name" not in tool_input:
            if services.is_dry_run() and getattr(tool_def, "parent_resource_type", None):
                resource_type = getattr(tool_def, "resource_type", "") or "resource"
                tool_input["name"] = (
                    f"{actual_platform}_dry_run_{str(resource_type).replace(' ', '_')}"
                )
        if isinstance(tool_input.get("updates"), dict) and "status" in tool_input["updates"]:
            tool_input["updates"] = self.normalize_provider_updates(
                tool_def, tool_input["updates"],
            )

        selection_errors = (
            self.parameter_selection.apply_selection_tokens(
                tool_def,
                tool_input,
                platform_params,
                ctx,
                trusted_state_fields=trusted_state_fields,
            )
            if ctx is not None else []
        )
        missing = [
            field_name for field_name in (tool_def.input_schema.required or [])
            if field_name not in tool_input
        ]
        for rule in tool_def.input_schema.conditional_rules or []:
            if not isinstance(rule, dict):
                continue
            conditions = rule.get("if", rule.get("when", {}))
            if not isinstance(conditions, dict) or any(
                tool_input.get(key) != expected
                for key, expected in conditions.items()
            ):
                continue
            for required in rule.get("required", rule.get("required_fields", [])) or []:
                if required not in tool_input and required not in missing:
                    missing.append(required)
        if missing:
            tool_input["_missing_params"] = missing
        if unknown_specific_params:
            tool_input["_unknown_params"] = unknown_specific_params
        if selection_errors:
            tool_input["_selection_errors"] = selection_errors
        return tool_input

    def validate_platform_parameter_contract(
        self, intent: Any, tool_plan: dict[str, list[Any]],
    ) -> list[str]:
        services = self.services
        errors: list[str] = []
        intent_fields = set(vars(intent)) if hasattr(intent, "__dict__") else set()
        common = intent_fields | set(self.scope_field_names) | {"selection_tokens"}
        for platform, values in (getattr(intent, "scoped_parameters", {}) or {}).items():
            if str(platform).startswith("_") or not isinstance(values, dict):
                continue
            canonical = services.normalize_namespace(platform)
            tools = [
                tool
                for routed_platform, routed_tools in tool_plan.items()
                if services.normalize_namespace(routed_platform) == canonical
                for tool in routed_tools
            ]
            registered_tools = getattr(services.registry, "list_by_namespace", None)
            if callable(registered_tools):
                tools.extend(registered_tools(canonical))
            tools = list({tool.name: tool for tool in tools}.values())
            tool_names = {tool.name for tool in tools}

            def declares_key(tool: Any, key: str) -> bool:
                properties = getattr(tool.input_schema, "properties", {}) or {}
                return any(
                    key in self.input_candidates(
                        field_name, schema, [key], declared_fields=properties,
                    )
                    for field_name, schema in properties.items()
                )

            for key in values:
                if key.startswith("_") or key in common or key in tool_names:
                    continue
                if not any(declares_key(tool, key) for tool in tools):
                    errors.append(f"{platform}.{key} 未被当前工具链声明")
            for tool in tools:
                scoped = values.get(tool.name)
                if not isinstance(scoped, dict):
                    continue
                properties = getattr(tool.input_schema, "properties", {}) or {}
                for key in scoped:
                    if key == "selection_tokens":
                        continue
                    if not any(
                        key in self.input_candidates(
                            field_name, schema, [key], declared_fields=properties,
                        )
                        for field_name, schema in properties.items()
                    ):
                        errors.append(
                            f"{platform}.{tool.name}.{key} 未被工具 Schema 声明"
                        )
        return errors[:20]


__all__ = ["ToolInputBuilder"]
