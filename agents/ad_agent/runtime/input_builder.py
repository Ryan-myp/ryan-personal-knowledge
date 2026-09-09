"""Schema-driven Tool input construction and parameter selection.

This service is deliberately independent of business workflows. It translates
the common ParsedIntent shape into a selected Tool's declared schema and
delegates account, execution and security decisions back to the Runtime.
Provider-specific aliases and enum mappings remain in Tool metadata.
"""

from __future__ import annotations

import copy
import json
import re
from datetime import datetime, timezone
from typing import Any, Optional

from ..core.interfaces import ToolContext, ToolResult
from ..domain.ad.parameter_selection import ParameterSelectionError
from ..core.tool_registry import validate_tool_input


class ToolInputBuilder:
    """Build and validate provider Tool inputs from generic Agent state."""

    ACCOUNT_FIELDS = (
        "account_id", "ad_account_id", "advertiser_id", "customer_id",
    )

    def __init__(self, services: Any):
        self.services = services

    def platform_params_for_intent(self, intent: Any, platform: str) -> dict[str, Any]:
        requested = self.services.normalize_namespace(platform)
        merged: dict[str, Any] = {}
        for raw_platform, values in (getattr(intent, "platform_params", {}) or {}).items():
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
        platform: str, date_range: Any, tool_def: Any = None,
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
        tool_def: Any, updates: dict[str, Any]
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

    @classmethod
    def input_candidates(
        cls, field_name: str, field_schema: Any, available_keys: Any = (),
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
        normalized = cls._normalize_input_field(field_name)
        account_fields = {
            "accountid", "adaccountid", "advertiserid", "customerid",
        }
        for key in keys:
            key_normalized = cls._normalize_input_field(key)
            if key_normalized == normalized:
                candidates.append(key)
            elif field_name == "name" and key_normalized.endswith("name"):
                candidates.append(key)
            elif key_normalized == normalized + "s":
                # Plural collection inputs (for example a batch of resource
                # IDs) may feed a singular Tool field when that is the only
                # field declared by the selected Tool. This is a generic
                # shape compatibility rule, not a resource-name table.
                candidates.append(key)
            elif normalized in account_fields and key_normalized in account_fields:
                candidates.append(key)
        return list(dict.fromkeys(candidates))

    @staticmethod
    def lookup_tool_for_schema_field(field_schema: Any) -> Optional[str]:
        if not isinstance(field_schema, dict):
            return None
        lookup_tool = field_schema.get("lookup_tool")
        if not lookup_tool and isinstance(field_schema.get("lookup"), dict):
            lookup_tool = field_schema["lookup"].get("tool")
        return str(lookup_tool) if lookup_tool else None

    @staticmethod
    def _schema_at_path(properties: Any, field_name: str) -> dict[str, Any]:
        """Resolve a dotted property path without provider-specific branches."""
        current = properties
        for part in str(field_name or "").split("."):
            if not part or not isinstance(current, dict):
                return {}
            # ``properties`` starts at the ToolSchema top level, while an
            # object-valued field stores its children below a nested
            # ``properties`` key.  Enter that object schema before resolving
            # the next path segment.  Without this generic step, signed
            # selections such as ``promoted_object.pixel_id`` were rejected
            # even though the provider schema declared their lookup tool.
            if "properties" in current and isinstance(current.get("properties"), dict):
                current = current["properties"]
            current = current.get(part)
        return current if isinstance(current, dict) else {}

    @staticmethod
    def _value_at_path(mapping: Any, field_name: str) -> Any:
        """Read a dotted value path from a provider input object."""
        current = mapping
        for part in str(field_name or "").split("."):
            if not part or not isinstance(current, dict) or part not in current:
                return None
            current = current[part]
        return current

    @classmethod
    def _iter_schema_fields(
        cls, properties: Any, prefix: str = "",
    ) -> list[tuple[str, dict[str, Any]]]:
        """Flatten object properties so nested lookup fields stay addressable."""
        fields: list[tuple[str, dict[str, Any]]] = []
        if not isinstance(properties, dict):
            return fields
        for name, schema in properties.items():
            if not isinstance(schema, dict):
                continue
            path = f"{prefix}.{name}" if prefix else str(name)
            fields.append((path, schema))
            if schema.get("type") == "object":
                fields.extend(cls._iter_schema_fields(schema.get("properties"), path))
        return fields

    @staticmethod
    def lookup_tools_for_fields(tool_def: Any, fields: list[str]) -> dict[str, str]:
        properties = getattr(tool_def.input_schema, "properties", {}) or {}
        result: dict[str, str] = {}
        for field in fields or []:
            spec = ToolInputBuilder._schema_at_path(properties, field)
            lookup_tool = ToolInputBuilder.lookup_tool_for_schema_field(spec)
            if lookup_tool:
                result[field] = lookup_tool
        return result

    def _lookup_targets_for_tool(
        self, source_tool_name: str
    ) -> list[tuple[Any, str, dict[str, Any]]]:
        targets = []
        for candidate in self.services.registry.list_all():
            schema = getattr(candidate, "input_schema", None)
            for field_name, field_schema in self._iter_schema_fields(
                getattr(schema, "properties", {}) or {}
            ):
                if self.lookup_tool_for_schema_field(field_schema) == source_tool_name:
                    targets.append((candidate, field_name, field_schema))
        return targets

    @staticmethod
    def _lookup_result_key(
        source_tool_name: str, field_schema: dict[str, Any]
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
        field_name: str, field_schema: dict[str, Any]
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

    @staticmethod
    def _selection_account_id(field_schema: dict[str, Any], ctx: ToolContext) -> str:
        """Return the account binding used by a provider selection token.

        A provider-owned catalog can explicitly be global (for example a
        TikTok App or location catalog).  Such a selection is intentionally
        portable across the account chosen later in the creation form.  All
        other selections remain bound to the active account.
        """
        if field_schema.get("lookup_account_required") is False:
            return ""
        return str(ctx.account_id or "")

    @classmethod
    def _extract_selection_option(
        cls, item: Any, field_name: str, field_schema: dict[str, Any],
    ) -> tuple[Any, str] | None:
        if isinstance(item, dict):
            # Some provider targeting contracts accept an array of structured
            # references (for example Meta's ``custom_audiences`` expects
            # ``[{"id": ..., "name": ...}]``). Keep the provider's allowed
            # object shape in the signed selection instead of flattening it to
            # a bare ID that would fail the ToolSchema at submit time.
            item_schema = field_schema.get("items") if field_schema.get("type") == "array" else None
            item_properties = item_schema.get("properties") if isinstance(item_schema, dict) else None
            value = next(
                (
                    item[key]
                    for key in cls._selection_value_fields(field_name, field_schema)
                    if item.get(key) not in (None, "")
                ),
                None,
            )
            if value in (None, ""):
                return None
            label = next(
                (
                    item[key]
                    for key in cls._selection_label_fields(field_schema)
                    if item.get(key) not in (None, "")
                ),
                value,
            )
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
        self, tool_def: Any, result: ToolResult, ctx: ToolContext,
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
            # An explicit picker only needs one target field. Decorating a
            # large provider catalog for every creation Tool multiplies the
            # short-lived signed tokens and can exceed the result budget
            # before the caller gets its options. The conversational path
            # keeps the all-target behavior; the picker path narrows it.
            if target_tool_name and target_tool.name != target_tool_name:
                continue
            if target_field and field_name != target_field:
                continue
            field_type = field_schema.get("type")
            item_schema = field_schema.get("items") if field_type == "array" else None
            if field_type not in {"string", "number", "integer", "array"}:
                continue
            values = result.data.get(
                self._lookup_result_key(tool_def.name, field_schema)
            )
            if not isinstance(values, list):
                continue
            options: list[dict[str, Any]] = []
            seen: set[str] = set()
            for item in values:
                extracted = self._extract_selection_option(
                    item, field_name, field_schema
                )
                if extracted is None:
                    continue
                value, label = extracted
                identity = json.dumps(
                    value, ensure_ascii=False, sort_keys=True, default=str
                )
                if identity in seen:
                    continue
                seen.add(identity)
                token, expires_at = self.services.parameter_selection_signer.issue(
                    session_id=ctx.session_id,
                    user_id=ctx.user_id,
                    account_id=self._selection_account_id(field_schema, ctx),
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
                    "platform": target_tool.platform,
                    "field": field_name,
                    "source_tool": tool_def.name,
                    "expires_at": datetime.fromtimestamp(
                        expires_at, tz=timezone.utc
                    ).isoformat(),
                    "options": options,
                })
        if selections:
            result.data = {**result.data, "parameter_selections": selections}
        return result

    def apply_selection_tokens(
        self, tool_def: Any, tool_input: dict[str, Any],
        platform_params: dict[str, Any], ctx: ToolContext,
        trusted_state_fields: Optional[set[str]] = None,
    ) -> list[str]:
        """Resolve picker tokens and enforce dynamic-ID provenance.

        IDs copied directly from a request must be attested by a provider
        lookup before a live create/upload.  A parent ID produced by an
        earlier successful create in the same Runtime session is already a
        trusted provider result, however, and must be allowed to flow to the
        next node of the same creation chain without forcing the user to
        select the newly-created resource again.
        """
        trusted_state_fields = trusted_state_fields or set()
        raw_tokens = platform_params.get("selection_tokens") or {}
        if not isinstance(raw_tokens, dict):
            return ["selection_tokens must be an object"]
        errors: list[str] = []
        properties = getattr(tool_def.input_schema, "properties", {}) or {}
        for raw_field_name, token_input in raw_tokens.items():
            field_name = str(raw_field_name)
            field_schema = self._schema_at_path(properties, field_name)
            source_tool = self.lookup_tool_for_schema_field(field_schema)
            if not source_tool:
                errors.append(
                    f"{field_name} does not accept a provider selection token"
                )
                continue
            field_type = field_schema.get("type") if isinstance(field_schema, dict) else None
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
                    resolved.append(
                        self.services.parameter_selection_signer.verify(
                            token,
                            session_id=ctx.session_id,
                            user_id=ctx.user_id,
                            account_id=self._selection_account_id(field_schema, ctx),
                            platform=self.services.normalize_namespace(
                                tool_def.platform
                            ),
                            tool_name=tool_def.name,
                            field=field_name,
                            source_tool=source_tool,
                        )
                    )
                except ParameterSelectionError as exc:
                    errors.append(f"selection_tokens.{field_name}: {exc}")
            if len(resolved) != len(tokens):
                continue
            value = resolved if is_array else resolved[0]
            current = tool_input
            path_parts = [part for part in field_name.split(".") if part]
            for part in path_parts[:-1]:
                current = current.get(part) if isinstance(current, dict) else None
            current_value = (
                current.get(path_parts[-1])
                if path_parts and isinstance(current, dict)
                else None
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

        # Resource identifiers on update/delete/pause operations may be
        # entered by an operator and are still protected by the normal live
        # confirmation and write gates.  Provider lookup attestations are
        # mandatory for creation/upload payloads, where an unverified
        # external identifier could otherwise be silently attached to a new
        # resource.  Keeping this distinction also preserves manual ID
        # workflows for existing-resource operations while allowing the UI to
        # offer the same lookup picker everywhere.
        if (
            self.services.execution_mode == "live"
            and tool_def.is_write_tool
            and str(getattr(tool_def, "action", "")).lower() in {"create", "upload"}
        ):
            for field_name, field_schema in self._iter_schema_fields(properties):
                if (
                    self.lookup_tool_for_schema_field(field_schema)
                    and field_schema.get("type")
                    in {"string", "number", "integer", "array"}
                    and self._value_at_path(tool_input, field_name) is not None
                    and field_name not in raw_tokens
                    and field_name not in trusted_state_fields
                ):
                    errors.append(
                        f"live 写入字段 {field_name} 必须使用 provider lookup 返回的 selection_token"
                    )
        return errors

    def build(
        self, tool_def: Any, intent: Any, platform: str,
        ctx: Optional[ToolContext] = None,
    ) -> dict[str, Any]:
        services = self.services
        platform_params = self.platform_params_for_intent(intent, platform)
        actual_platform = services.normalize_namespace(platform)
        tool_input: dict[str, Any] = {}
        specific_params = platform_params.get(tool_def.name, {})
        unknown_specific_params: list[str] = []
        if isinstance(specific_params, dict):
            platform_params = {**platform_params, **specific_params}
            accepted = set(tool_def.input_schema.properties)
            accepted.update(self.ACCOUNT_FIELDS + ("selection_tokens",))
            for field_name, schema in tool_def.input_schema.properties.items():
                accepted.update(self.input_candidates(
                    field_name, schema, specific_params.keys()
                ))
            unknown_specific_params = sorted(
                key for key in specific_params if key not in accepted
            )

        properties = getattr(tool_def.input_schema, "properties", {}) or {}
        trusted_state_fields: set[str] = set()
        for field_name, schema in properties.items():
            for candidate in self.input_candidates(
                field_name, schema, platform_params.keys()
            ):
                if candidate in platform_params and platform_params[candidate] not in (None, ""):
                    tool_input[field_name] = platform_params[candidate]
                    break

        if ctx and ctx.account_id:
            for account_field in self.ACCOUNT_FIELDS:
                if account_field in properties and account_field not in tool_input:
                    tool_input[account_field] = ctx.account_id
                    break

        if ctx:
            protected = getattr(ctx, "protected_state", {}) or {}
            scoped_keys_exist = any(":" in key for key in protected)
            state_fields = [str(key).rsplit(":", 1)[-1] for key in protected]
            for field_name, schema in properties.items():
                if field_name in tool_input:
                    continue
                for candidate in self.input_candidates(field_name, schema, state_fields):
                    scoped_value = next(
                        (
                            protected[key]
                            for key in (
                                f"{actual_platform}:{candidate}",
                                f"{platform}:{candidate}",
                            )
                            if key in protected and protected[key] not in (None, "")
                        ),
                        None,
                    )
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

        # Project the generic ParsedIntent fields only through metadata owned
        # by the selected Tool.  A provider may map an input field to a
        # different intent field and/or publish an enum translation through
        # ``intent_field`` and ``intent_map``.  Runtime does not need to know
        # whether that field means budget, objective, campaign type, date
        # range, or something introduced by a future Skill.
        # Intent-level values are publisher-owned extensions.  Read the
        # generic attribute bag instead of inspecting ParsedIntent's storage
        # layout, so adding a new Skill field does not require a Runtime edit.
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
                        str(value).lower(),
                        mapping.get(str(value).upper(), value),
                    )
                tool_input[field_name] = copy.deepcopy(value)
                break

        # Provider contracts may publish intent-scoped defaults for a
        # structured field such as ``updates``.  The builder only interprets
        # this generic metadata; it does not know which actions or wire values
        # a provider uses.
        intent_type = str(getattr(intent, "intent_type", "") or "")
        for field_name, schema in properties.items():
            if field_name in tool_input or not isinstance(schema, dict):
                continue
            defaults = schema.get("intent_defaults")
            if not isinstance(defaults, dict):
                continue
            default = defaults.get(intent_type)
            if isinstance(default, dict):
                tool_input[field_name] = copy.deepcopy(default)

        for field_name, schema in properties.items():
            if field_name not in tool_input and isinstance(schema, dict) and "default" in schema:
                tool_input[field_name] = copy.deepcopy(schema["default"])

        if "name" in tool_def.input_schema.required and "name" not in tool_input:
            # Child resources can be planned before their provider parent is
            # created.  A generic hierarchy-based placeholder keeps dry-run
            # planning possible without naming any advertising resource types.
            if services.is_dry_run() and getattr(tool_def, "parent_resource_type", None):
                resource_type = getattr(tool_def, "resource_type", "") or "resource"
                tool_input["name"] = (
                    f"{actual_platform}_dry_run_{str(resource_type).replace(' ', '_')}"
                )
        if isinstance(tool_input.get("updates"), dict) and "status" in tool_input["updates"]:
            tool_input["updates"] = self.normalize_provider_updates(
                tool_def, tool_input["updates"]
            )

        selection_errors = self.apply_selection_tokens(
            tool_def, tool_input, platform_params, ctx,
            trusted_state_fields=trusted_state_fields,
        ) if ctx is not None else []
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
        self, intent: Any, tool_plan: dict[str, list[Any]]
    ) -> list[str]:
        services = self.services
        errors: list[str] = []
        intent_fields = set(vars(intent)) if hasattr(intent, "__dict__") else set()
        common = intent_fields | set(self.ACCOUNT_FIELDS) | {"selection_tokens"}
        for platform, values in (getattr(intent, "platform_params", {}) or {}).items():
            if str(platform).startswith("_") or not isinstance(values, dict):
                continue
            canonical = services.normalize_namespace(platform)
            tools = [
                tool
                for routed_platform, routed_tools in tool_plan.items()
                if services.normalize_namespace(routed_platform) == canonical
                for tool in routed_tools
            ]
            # The parser may extract a parent/context identifier that is not
            # an input of the final action Tool. Treat it as valid only when
            # another registered Tool in the same provider package declares
            # the field or one of its aliases. This keeps the contract closed
            # without maintaining a central list of advertising field names.
            registered_tools = getattr(services.registry, "list_by_platform", None)
            if callable(registered_tools):
                tools.extend(registered_tools(canonical))
            tools = list({tool.name: tool for tool in tools}.values())
            tool_names = {tool.name for tool in tools}
            for key in values:
                if key.startswith("_") or key in common:
                    continue
                if key in tool_names:
                    continue
                if any(
                    any(
                        key in self.input_candidates(field_name, schema, [key])
                        for field_name, schema in (
                            getattr(tool.input_schema, "properties", {}) or {}
                        ).items()
                    )
                    for tool in tools
                ):
                    continue
                errors.append(f"{platform}.{key} 未被当前工具链声明")
            for tool in tools:
                scoped = values.get(tool.name)
                if not isinstance(scoped, dict):
                    continue
                for key in scoped:
                    if key == "selection_tokens":
                        continue
                    properties = getattr(tool.input_schema, "properties", {}) or {}
                    if not any(
                        key in self.input_candidates(field_name, schema, [key])
                        for field_name, schema in properties.items()
                    ):
                        errors.append(f"{platform}.{tool.name}.{key} 未被工具 Schema 声明")
        return errors[:20]
