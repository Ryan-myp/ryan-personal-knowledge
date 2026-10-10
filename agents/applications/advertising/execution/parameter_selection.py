"""Resolve schema-declared lookup results into scoped selection tokens."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from agents.agent_harness.core.interfaces import ToolContext, ToolResult


class ParameterSelectionService:
    """Own lookup-field discovery, signed picker options and token checks."""

    def __init__(
        self,
        services: Any,
        *,
        scope_value_resolver: Optional[Callable[[ToolContext], Any]] = None,
    ) -> None:
        self.services = services
        self.scope_value_resolver = scope_value_resolver

    def _scope_value(self, context: ToolContext) -> Any:
        if not callable(self.scope_value_resolver):
            return None
        return self.scope_value_resolver(context)

    @staticmethod
    def lookup_tool_for_field(field_schema: Any) -> Optional[str]:
        if not isinstance(field_schema, dict):
            return None
        lookup_tool = field_schema.get("lookup_tool")
        if not lookup_tool and isinstance(field_schema.get("lookup"), dict):
            lookup_tool = field_schema["lookup"].get("tool")
        return str(lookup_tool) if lookup_tool else None

    @staticmethod
    def _schema_at_path(properties: Any, field_name: str) -> dict[str, Any]:
        current = properties
        for part in str(field_name or "").split("."):
            if not part or not isinstance(current, dict):
                return {}
            if "properties" in current and isinstance(current.get("properties"), dict):
                current = current["properties"]
            current = current.get(part)
        return current if isinstance(current, dict) else {}

    @staticmethod
    def value_at_path(mapping: Any, field_name: str) -> Any:
        current = mapping
        for part in str(field_name or "").split("."):
            if not part or not isinstance(current, dict) or part not in current:
                return None
            current = current[part]
        return current

    @classmethod
    def iter_schema_fields(
        cls, properties: Any, prefix: str = "",
    ) -> list[tuple[str, dict[str, Any]]]:
        fields: list[tuple[str, dict[str, Any]]] = []
        if not isinstance(properties, dict):
            return fields
        for name, schema in properties.items():
            if not isinstance(schema, dict):
                continue
            path = f"{prefix}.{name}" if prefix else str(name)
            fields.append((path, schema))
            if schema.get("type") == "object":
                fields.extend(cls.iter_schema_fields(schema.get("properties"), path))
        return fields

    def _lookup_targets_for_tool(
        self, source_tool_name: str,
    ) -> list[tuple[Any, str, dict[str, Any]]]:
        targets = []
        for candidate in self.services.registry.list_all():
            schema = getattr(candidate, "input_schema", None)
            for field_name, field_schema in self.iter_schema_fields(
                getattr(schema, "properties", {}) or {}
            ):
                if self.lookup_tool_for_field(field_schema) == source_tool_name:
                    targets.append((candidate, field_name, field_schema))
        return targets

    @staticmethod
    def _lookup_result_key(
        source_tool_name: str, field_schema: dict[str, Any],
    ) -> str:
        configured = field_schema.get("lookup_result_key")
        if configured:
            return str(configured)
        marker = "_list_"
        return (
            source_tool_name.split(marker, 1)[1]
            if marker in source_tool_name else source_tool_name
        )

    @staticmethod
    def _selection_value_fields(
        field_name: str, field_schema: dict[str, Any],
    ) -> list[str]:
        configured = field_schema.get("selection_value_fields")
        if isinstance(configured, (list, tuple)):
            return [str(value) for value in configured]
        leaf_name = field_name.rsplit(".", 1)[-1]
        singular = leaf_name[:-1] if leaf_name.endswith("_ids") else leaf_name
        return [singular, "id", "value", "code"]

    @staticmethod
    def _selection_label_fields(field_schema: dict[str, Any]) -> list[str]:
        configured = field_schema.get("selection_label_fields")
        if isinstance(configured, (list, tuple)):
            return [str(value) for value in configured]
        return [
            "name", "label", "display_name", "app_name",
            "location_name", "country_name",
        ]

    def _selection_scope_key(
        self, field_schema: dict[str, Any], context: ToolContext,
    ) -> str:
        if field_schema.get("lookup_account_required") is False:
            return ""
        return str(self._scope_value(context) or "")

    @classmethod
    def _extract_selection_option(
        cls, item: Any, field_name: str, field_schema: dict[str, Any],
    ) -> tuple[Any, str] | None:
        if isinstance(item, dict):
            item_schema = (
                field_schema.get("items")
                if field_schema.get("type") == "array" else None
            )
            item_properties = (
                item_schema.get("properties")
                if isinstance(item_schema, dict) else None
            )
            value = next((
                item[key]
                for key in cls._selection_value_fields(field_name, field_schema)
                if item.get(key) not in (None, "")
            ), None)
            if value in (None, ""):
                return None
            label = next((
                item[key]
                for key in cls._selection_label_fields(field_schema)
                if item.get(key) not in (None, "")
            ), value)
            if isinstance(item_properties, dict):
                structured_value = {
                    str(key): item[key]
                    for key in item_properties
                    if item.get(key) not in (None, "")
                }
                if structured_value:
                    return structured_value, str(label)
            return value, str(label)
        if item not in (None, "") and isinstance(item, (str, int, float)):
            return item, str(item)
        return None

    def decorate_lookup_result(
        self,
        tool_def: Any,
        result: ToolResult,
        context: ToolContext,
        platform: str,
        target_tool_name: Optional[str] = None,
        target_field: Optional[str] = None,
    ) -> ToolResult:
        if not result.success or not isinstance(result.data, dict):
            return result
        if str(result.data.get("data_status", "")).lower() != "live":
            return result
        selections: list[dict[str, Any]] = []
        for target_tool, field_name, field_schema in self._lookup_targets_for_tool(
            tool_def.name
        ):
            if target_tool_name and target_tool.name != target_tool_name:
                continue
            if target_field and field_name != target_field:
                continue
            field_type = field_schema.get("type")
            field_types = (
                field_type if isinstance(field_type, (list, tuple, set, frozenset))
                else (field_type,)
            )
            supported_types = {
                item for item in field_types
                if isinstance(item, str)
                and item in {"string", "number", "integer", "array"}
            }
            if not supported_types:
                continue
            result_key = self._lookup_result_key(tool_def.name, field_schema)
            values = result.data.get(result_key)
            if not isinstance(values, list):
                continue
            options: list[dict[str, Any]] = []
            seen: set[str] = set()
            expires_at = 0
            for item in values:
                if len(options) >= 20:
                    break
                extracted = self._extract_selection_option(
                    item, field_name, field_schema,
                )
                if extracted is None:
                    continue
                value, label = extracted
                identity = json.dumps(
                    value, ensure_ascii=False, sort_keys=True, default=str,
                )
                if identity in seen:
                    continue
                seen.add(identity)
                token, expires_at = self.services.selection_signer.issue(
                    session_id=context.session_id,
                    user_id=context.user_id,
                    scope_key=self._selection_scope_key(field_schema, context),
                    platform=platform,
                    tool_name=target_tool.name,
                    field=field_name,
                    source_tool=tool_def.name,
                    value=value,
                )
                options.append({
                    "value": value,
                    "label": label,
                    "selection_token": token,
                })
            if options:
                selections.append({
                    "tool_name": target_tool.name,
                    "platform": target_tool.namespace,
                    "field": field_name,
                    "source_tool": tool_def.name,
                    "expires_at": datetime.fromtimestamp(
                        expires_at, tz=timezone.utc,
                    ).isoformat(),
                    "options": options,
                })
        if selections:
            result.data = {**result.data, "parameter_selections": selections}
        return result

    def apply_selection_tokens(
        self,
        tool_def: Any,
        tool_input: dict[str, Any],
        platform_params: dict[str, Any],
        context: ToolContext,
        trusted_state_fields: Optional[set[str]] = None,
    ) -> list[str]:
        trusted_state_fields = trusted_state_fields or set()
        raw_tokens = platform_params.get("selection_tokens") or {}
        if not isinstance(raw_tokens, dict):
            return ["selection_tokens must be an object"]
        errors: list[str] = []
        properties = getattr(tool_def.input_schema, "properties", {}) or {}
        for raw_field_name, token_input in raw_tokens.items():
            field_name = str(raw_field_name)
            field_schema = self._schema_at_path(properties, field_name)
            source_tool = self.lookup_tool_for_field(field_schema)
            if not source_tool:
                errors.append(
                    f"{field_name} does not accept a provider selection token"
                )
                continue
            field_type = field_schema.get("type")
            if field_type not in {"string", "number", "integer", "array"}:
                errors.append(
                    f"selection_tokens.{field_name} must target a scalar or array field"
                )
                continue
            is_array = field_type == "array"
            tokens = token_input if is_array else [token_input]
            if (
                not isinstance(tokens, list) or not tokens
                or any(not isinstance(token, str) for token in tokens)
            ):
                errors.append(
                    f"selection_tokens.{field_name} must match the field shape"
                )
                continue
            resolved: list[Any] = []
            for token in tokens:
                try:
                    resolved.append(self.services.selection_signer.verify(
                        token,
                        session_id=context.session_id,
                        user_id=context.user_id,
                        scope_key=self._selection_scope_key(field_schema, context),
                        platform=self.services.normalize_namespace(tool_def.namespace),
                        tool_name=tool_def.name,
                        field=field_name,
                        source_tool=source_tool,
                    ))
                except ValueError as exc:
                    errors.append(f"selection_tokens.{field_name}: {exc}")
            if len(resolved) != len(tokens):
                continue
            value = resolved if is_array else resolved[0]
            path_parts = [part for part in field_name.split(".") if part]
            current = tool_input
            for part in path_parts[:-1]:
                current = current.get(part) if isinstance(current, dict) else None
            current_value = (
                current.get(path_parts[-1])
                if path_parts and isinstance(current, dict) else None
            )
            if current_value is not None and current_value != value:
                errors.append(f"{field_name} does not match its selection token")
                continue
            target = tool_input
            for part in path_parts[:-1]:
                child = target.get(part)
                if not isinstance(child, dict):
                    child = {}
                    target[part] = child
                target = child
            if path_parts:
                target[path_parts[-1]] = value

        if (
            self.services.execution_mode == "live"
            and tool_def.is_write_tool
            and str(getattr(tool_def, "action", "")).lower() in {"create", "upload"}
        ):
            for field_name, field_schema in self.iter_schema_fields(properties):
                if (
                    self.lookup_tool_for_field(field_schema)
                    and field_schema.get("type")
                    in {"string", "number", "integer", "array"}
                    and self.value_at_path(tool_input, field_name) is not None
                    and field_name not in raw_tokens
                    and field_name not in trusted_state_fields
                ):
                    errors.append(
                        f"live 写入字段 {field_name} 必须使用 provider lookup 返回的 selection_token"
                    )
        return errors


__all__ = ["ParameterSelectionService"]
