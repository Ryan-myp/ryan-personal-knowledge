"""Resolve schema-declared lookup results into scoped selection tokens."""

from __future__ import annotations

import json
from collections import OrderedDict
from datetime import datetime, timezone
from threading import RLock
from typing import Any, Callable, Optional

from agents.agent_harness.core.interfaces import ToolContext, ToolResult


class ParameterSelectionService:
    """Own lookup-field discovery, signed picker options and token checks."""

    _MAX_PROOFS_PER_FIELD = 64

    def __init__(
        self,
        services: Any,
        *,
        scope_value_resolver: Optional[Callable[[ToolContext], Any]] = None,
    ) -> None:
        self.services = services
        self.scope_value_resolver = scope_value_resolver
        self._lookup_proofs: OrderedDict[tuple[str, ...], list[dict[str, Any]]] = OrderedDict()
        self._proof_lock = RLock()

    def _proof_key(self, context: ToolContext, tool: Any, field: str, schema: dict) -> tuple[str, ...]:
        return (
            str(context.session_id), str(context.user_id),
            str(context.metadata.get("tenant_id") or "default"),
            str(self._scope_value(context) or ""),
            self._selection_scope_key(schema, context),
            str(tool.namespace), str(tool.name), field,
        )

    def _remember_lookup(
        self, context: ToolContext, tool: Any, field: str, schema: dict,
        options: list[dict[str, Any]], *, invalidate_empty: bool = False,
    ) -> None:
        key = self._proof_key(context, tool, field, schema)
        with self._proof_lock:
            if invalidate_empty:
                proofs = []
            else:
                by_value: OrderedDict[str, dict[str, Any]] = OrderedDict()
                existing = self._lookup_proofs.get(key, ())
                for option in existing:
                    identity = json.dumps(
                        option["value"],
                        ensure_ascii=False,
                        sort_keys=True,
                        default=str,
                    )
                    by_value[identity] = option
                for option in options:
                    identity = json.dumps(
                        option["value"],
                        ensure_ascii=False,
                        sort_keys=True,
                        default=str,
                    )
                    by_value[identity] = {
                        "value": option["value"],
                        "selection_token": option["selection_token"],
                    }
                    by_value.move_to_end(identity)
                proofs = list(by_value.values())[-self._MAX_PROOFS_PER_FIELD:]
                if not proofs:
                    return
            self._lookup_proofs[key] = proofs
            self._lookup_proofs.move_to_end(key)
            while len(self._lookup_proofs) > 256:
                self._lookup_proofs.popitem(last=False)

    def _lookup_tokens(
        self, tool: Any, tool_input: dict[str, Any], context: ToolContext,
    ) -> dict[str, Any]:
        tokens = {}
        properties = getattr(tool.input_schema, "properties", {}) or {}
        for field, schema in self.iter_schema_fields(properties):
            value = self.value_at_path(tool_input, field)
            if value is None or not self.lookup_tool_for_field(schema):
                continue
            key = self._proof_key(context, tool, field, schema)
            with self._proof_lock:
                options = self._lookup_proofs.get(key, ())
            is_array = schema.get("type") == "array"
            values = value if is_array and isinstance(value, list) else [value]
            matched = [
                [option["selection_token"] for option in options if option["value"] == item]
                for item in values
            ]
            if matched and all(len(matches) == 1 for matches in matched):
                proof = [matches[0] for matches in matched]
                tokens[field] = proof if is_array else proof[0]
        return tokens

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
        query: Optional[str] = None,
        selected_value: Any = None,
    ) -> ToolResult:
        if not result.success or not isinstance(result.data, dict):
            return result
        if str(result.data.get("data_status", "")).lower() != "live":
            return result
        search = str(query or "").strip().casefold()
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
            if isinstance(values, dict):
                values = [values] if values else []
            if not isinstance(values, list):
                continue
            candidates: list[tuple[str, Any, str]] = []
            seen: set[str] = set()
            allowed_asset_types = {
                str(item).strip().upper()
                for item in field_schema.get("lookup_asset_types", ())
                if str(item).strip()
            }
            for item in values:
                if allowed_asset_types and (
                    not isinstance(item, dict)
                    or str(item.get("type") or "").strip().upper()
                    not in allowed_asset_types
                ):
                    continue
                extracted = self._extract_selection_option(
                    item, field_name, field_schema,
                )
                if extracted is None:
                    continue
                value, label = extracted
                if search and not any(
                    search in str(part).casefold() for part in (value, label)
                ):
                    continue
                identity = json.dumps(
                    value, ensure_ascii=False, sort_keys=True, default=str,
                )
                if identity in seen:
                    continue
                seen.add(identity)
                candidates.append((identity, value, label))

            selected_values = (
                selected_value if isinstance(selected_value, list)
                else [selected_value]
            )
            selected_identities = {
                json.dumps(
                    value, ensure_ascii=False, sort_keys=True, default=str,
                )
                for value in selected_values
                if value not in (None, "")
            }
            preferred = [
                candidate for candidate in candidates
                if candidate[0] in selected_identities
            ]
            remaining = [
                candidate for candidate in candidates
                if candidate[0] not in selected_identities
            ]
            options: list[dict[str, Any]] = []
            expires_at = 0
            for _identity, value, label in (preferred + remaining)[:20]:
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
            self._remember_lookup(
                context,
                target_tool,
                field_name,
                field_schema,
                options,
                invalidate_empty=not values,
            )
            if options or (target_tool_name and target_field):
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
        supplied_tokens = platform_params.get("selection_tokens") or {}
        if not isinstance(supplied_tokens, dict):
            return ["selection_tokens must be an object"]
        # Native Tool calls keep proofs server-side; both paths still verify
        # the signed user/session/account/Tool/field claims and selected value.
        cached_tokens = (
            self._lookup_tokens(tool_def, tool_input, context)
            if self.services.execution_mode == "live" else {}
        )
        raw_tokens = {**cached_tokens, **supplied_tokens}
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
