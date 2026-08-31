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
from ..core.parameter_selection import ParameterSelectionError
from ..core.tool_registry import validate_tool_input


class ToolInputBuilder:
    """Build and validate provider Tool inputs from generic Agent state."""

    ACCOUNT_FIELDS = (
        "account_id", "ad_account_id", "advertiser_id", "customer_id",
    )

    def __init__(self, services: Any):
        self.services = services

    def platform_params_for_intent(self, intent: Any, platform: str) -> dict[str, Any]:
        requested = self.services.canonical_platform(platform)
        merged: dict[str, Any] = {}
        for raw_platform, values in (getattr(intent, "platform_params", {}) or {}).items():
            if self.services.canonical_platform(str(raw_platform)) != requested:
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
    def lookup_tools_for_fields(tool_def: Any, fields: list[str]) -> dict[str, str]:
        properties = getattr(tool_def.input_schema, "properties", {}) or {}
        result: dict[str, str] = {}
        for field in fields or []:
            spec = properties.get(field, {})
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
            for field_name, field_schema in (
                getattr(schema, "properties", {}) or {}
            ).items():
                if "." in str(field_name) or not isinstance(field_schema, dict):
                    continue
                if self.lookup_tool_for_schema_field(field_schema) == source_tool_name:
                    targets.append((candidate, str(field_name), field_schema))
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
        singular = field_name[:-1] if field_name.endswith("_ids") else field_name
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

    @classmethod
    def _extract_selection_option(
        cls, item: Any, field_name: str, field_schema: dict[str, Any],
    ) -> tuple[Any, str] | None:
        if isinstance(item, dict):
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
            return value, str(label)
        if item not in (None, "") and isinstance(item, (str, int, float)):
            return item, str(item)
        return None

    def decorate_lookup_result(
        self, tool_def: Any, result: ToolResult, ctx: ToolContext,
        platform: str,
    ) -> ToolResult:
        if not result.success or not isinstance(result.data, dict):
            return result
        if str(result.data.get("data_status", "")).lower() != "live":
            return result
        selections: list[dict[str, Any]] = []
        for target_tool, field_name, field_schema in self._lookup_targets_for_tool(
            tool_def.name
        ):
            field_type = field_schema.get("type")
            item_schema = field_schema.get("items") if field_type == "array" else None
            if field_type not in {"string", "number", "integer", "array"}:
                continue
            if (
                field_type == "array" and item_schema
                and item_schema.get("type") not in {"string", "number", "integer"}
            ):
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
                    account_id=str(ctx.account_id or ""),
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
    ) -> list[str]:
        raw_tokens = platform_params.get("selection_tokens") or {}
        if not isinstance(raw_tokens, dict):
            return ["selection_tokens must be an object"]
        errors: list[str] = []
        properties = getattr(tool_def.input_schema, "properties", {}) or {}
        for raw_field_name, token_input in raw_tokens.items():
            field_name = str(raw_field_name)
            field_schema = properties.get(field_name)
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
                            account_id=str(ctx.account_id or ""),
                            platform=self.services.canonical_platform(
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
            if field_name in tool_input and tool_input[field_name] != value:
                errors.append(f"{field_name} does not match its selection token")
                continue
            tool_input[field_name] = value

        if self.services.execution_mode == "live" and tool_def.is_write_tool:
            for field_name, field_schema in properties.items():
                if (
                    self.lookup_tool_for_schema_field(field_schema)
                    and field_schema.get("type")
                    in {"string", "number", "integer", "array"}
                    and field_name in tool_input
                    and field_name not in raw_tokens
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
        actual_platform = services.canonical_platform(platform)
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
                        break
                    if (
                        not scoped_keys_exist
                        and candidate in protected
                        and protected[candidate] not in (None, "")
                    ):
                        tool_input[field_name] = protected[candidate]
                        break

        budget = getattr(intent, "budget", None)
        if budget is not None:
            tool_input.setdefault("budget", budget)
            if "daily_budget" in properties:
                tool_input.setdefault("daily_budget", budget)
        if tool_input.get("budget") not in (None, "") and "daily_budget" in properties:
            tool_input.setdefault("daily_budget", tool_input["budget"])

        objective = getattr(intent, "objective", None)
        if objective:
            for field_name, schema in properties.items():
                if field_name in tool_input or not isinstance(schema, dict):
                    continue
                if schema.get("intent_field") == "objective":
                    tool_input[field_name] = (
                        schema.get("intent_map", {}).get(
                            str(objective).lower(), objective
                        )
                    )
            if "objective" in properties:
                tool_input.setdefault("objective", objective)

        campaign_type = getattr(intent, "campaign_type", None)
        if campaign_type and "campaign_type" in properties:
            tool_input.setdefault("campaign_type", campaign_type)
        if campaign_type:
            for field_name, schema in properties.items():
                if field_name in tool_input or not isinstance(schema, dict):
                    continue
                if schema.get("intent_field") == "campaign_type":
                    tool_input[field_name] = schema.get("intent_map", {}).get(
                        str(campaign_type).upper(), campaign_type
                    )

        date_range = getattr(intent, "date_range", None)
        if date_range:
            if "date_range" in properties:
                tool_input.setdefault("date_range", date_range)
            if "date_preset" in properties:
                tool_input.setdefault(
                    "date_preset",
                    self.platform_date_range(platform, date_range, tool_def),
                )
        materials = getattr(intent, "creative_materials", None)
        if materials and "creative_materials" not in tool_input:
            tool_input["creative_materials"] = materials

        for field_name, schema in properties.items():
            if field_name not in tool_input and isinstance(schema, dict) and "default" in schema:
                tool_input[field_name] = copy.deepcopy(schema["default"])

        if "name" in properties and "name" not in tool_input:
            campaign_name = platform_params.get("campaign_name")
            if campaign_name:
                tool_input["name"] = campaign_name
        if "name" in tool_def.input_schema.required and "name" not in tool_input:
            resource_type = getattr(tool_def, "resource_type", "")
            if services.is_dry_run() and resource_type in {"ad_set", "ad_group", "line_item"}:
                tool_input["name"] = f"{platform}_dry_run_{resource_type}"

        if "updates" in tool_def.input_schema.required:
            intent_type = getattr(intent, "intent_type", "")
            if intent_type in {"pause_campaign", "resume_campaign"}:
                tool_input["updates"] = {
                    "status": "PAUSED" if intent_type == "pause_campaign" else "ACTIVE"
                }
        if isinstance(tool_input.get("updates"), dict) and "status" in tool_input["updates"]:
            tool_input["updates"] = self.normalize_provider_updates(
                tool_def, tool_input["updates"]
            )

        selection_errors = self.apply_selection_tokens(
            tool_def, tool_input, platform_params, ctx
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
        common = {
            "budget", "daily_budget", "objective", "campaign_type",
            "date_range", "date_preset", "creative_materials", "campaign_id",
            "campaign_ids", *self.ACCOUNT_FIELDS,
        }
        for platform, values in (getattr(intent, "platform_params", {}) or {}).items():
            if str(platform).startswith("_") or not isinstance(values, dict):
                continue
            canonical = services.canonical_platform(platform)
            tools = [
                tool
                for routed_platform, routed_tools in tool_plan.items()
                if services.canonical_platform(routed_platform) == canonical
                for tool in routed_tools
            ]
            tool_names = {tool.name for tool in tools}
            for key in values:
                if key.startswith("_") or key in common or key == "selection_tokens":
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
