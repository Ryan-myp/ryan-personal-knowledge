"""Tool-schema contract validation used by advertising creation."""

from __future__ import annotations

import copy
import re
import uuid
from typing import Any, Iterable, Mapping, Optional

from ..core.interfaces import ParsedIntent
from ..core.tool_registry import validate_tool_input


class AdCreationContractServicesMixin:
    def _creation_contract_preflight(
        self,
        intent: ParsedIntent,
        tool_plan: Mapping[str, Iterable[Any]],
        session: "SessionContext",
        account_id: str,
    ) -> list[dict[str, Any]]:
        """Validate the complete creation chain before any Tool is executed."""
        issues: list[dict[str, Any]] = []
        original_account = session.ctx.account_id
        session.ctx.account_id = account_id
        try:
            for platform, tools in tool_plan.items():
                actual_platform = self._canonical_platform(platform)
                for tool_def in tools:
                    if not tool_def.is_write_tool or not tool_def.input_schema:
                        continue
                    tool_input = self.input_builder.build(
                        tool_def, intent, platform, session.ctx
                    )
                    unknown = tool_input.pop("_unknown_params", []) or []
                    selection_errors = tool_input.pop("_selection_errors", []) or []
                    missing = list(tool_input.pop("_missing_params", []) or [])

                    parent_field = self._parent_resource_id_field_for_tool(tool_def)
                    if parent_field in missing:
                        tool_input[parent_field] = f"__planned_{parent_field}__"
                        missing.remove(parent_field)
                    for field_name in missing:
                        issues.append({
                            "tool": tool_def.name,
                            "platform": actual_platform,
                            "field": str(field_name),
                            "message": f"Missing required field: {field_name}",
                        })
                    for field_name in unknown:
                        issues.append({
                            "tool": tool_def.name,
                            "platform": actual_platform,
                            "field": str(field_name),
                            "message": f"Field '{field_name}' is not allowed",
                        })
                    for message in selection_errors:
                        issues.append({
                            "tool": tool_def.name,
                            "platform": actual_platform,
                            "field": "selection",
                            "message": str(message),
                        })
                    schema_errors = validate_tool_input(
                        tool_def.input_schema,
                        tool_input,
                        include_tool_requirements=True,
                    )
                    for message in schema_errors:
                        field_match = re.search(r"Field '([^']+)'", str(message))
                        if field_match is None:
                            field_match = re.search(
                                r"Provider contract requires field:\s*([A-Za-z0-9_.-]+)",
                                str(message),
                            )
                        issues.append({
                            "tool": tool_def.name,
                            "platform": actual_platform,
                            "field": field_match.group(1) if field_match else "",
                            "message": str(message),
                        })
        finally:
            session.ctx.account_id = original_account
        return issues

    @staticmethod
    def _creation_contract_reply(
        ui: Mapping[str, Any], issues: Iterable[Mapping[str, Any]]
    ) -> str:
        """Turn schema errors into concise operator-facing corrections."""
        label_by_key: dict[tuple[str, str], str] = {}
        for card in ui.get("cards", []) if isinstance(ui, Mapping) else []:
            if not isinstance(card, Mapping):
                continue
            for field in card.get("fields", []) or []:
                if not isinstance(field, Mapping):
                    continue
                label = str(field.get("label") or field.get("path") or "参数")
                tool = str(field.get("tool") or "")
                provider_field = str(field.get("provider_field") or "")
                path = str(field.get("path") or "")
                for key in (
                    (tool, provider_field),
                    (tool, path),
                    ("", provider_field),
                    ("", path),
                ):
                    if key[1]:
                        label_by_key.setdefault(key, label)

        details: list[str] = []
        issue_list = [item for item in issues if isinstance(item, Mapping)]
        exact_fields = {str(item.get("field") or "") for item in issue_list}
        for issue in issue_list:
            tool = str(issue.get("tool") or "")
            field = str(issue.get("field") or "")
            message = str(issue.get("message") or "")
            if "[" in field and field.split("[", 1)[0] in exact_fields:
                continue
            label = label_by_key.get((tool, field)) or label_by_key.get(("", field))
            count_match = re.search(r"at least (\d+) items?/characters", message)
            if count_match and label:
                detail = f"{label}至少需要 {count_match.group(1)} 项"
            elif message.startswith("Missing required field:") and label:
                detail = f"请补充{label}"
            elif "Provider contract requires field:" in message and label:
                detail = f"请补充{label}"
            elif label:
                detail = f"{label}需要调整"
            else:
                detail = "有一项创建参数不符合平台要求"
            if detail not in details:
                details.append(detail)
        details = details[:8]
        return (
            "提交前检查发现以下内容还不符合当前广告类型的要求："
            + "；".join(details)
            + "。本次没有创建任何广告资源，请返回卡片补充或调整后再提交。"
        )

    def resolve_parameter_options(
        self,
        platform: str,
        field: str,
        tool_name: str,
        account_id: Optional[str] = None,
        *,
        session_id: Optional[str] = None,
        user_id: str = "parameter-options",
        tenant_id: str = "default",
        account_scope: Optional[Mapping[str, set[str]]] = None,
        granted_permissions: Optional[set[str] | frozenset[str]] = None,
        lookup_context: Optional[Mapping[str, Any]] = None,
        query: Optional[str] = None,
    ) -> dict[str, Any]:
        """Resolve one dynamic catalog through a registered read Tool."""
        actual_platform = self._canonical_platform(platform)
        catalog = self.parameter_catalogs.get(actual_platform, field, tool_name)
        if catalog is None:
            raise KeyError(
                f"parameter catalog not found for {actual_platform}.{field} ({tool_name})"
            )
        if catalog.source != "lookup":
            return catalog.to_dict()
        source_tool = str(catalog.lookup_tool or "")
        definition, _handler = self._get_registered_tool(source_tool)
        if not definition.is_read_tool:
            raise PermissionError("parameter lookup source must be read-only")
        if self._canonical_platform(definition.namespace) != actual_platform:
            raise ValueError("parameter lookup source belongs to a different platform")
        account_value = str(account_id or "").strip()
        source_properties = getattr(definition.input_schema, "properties", {}) or {}
        source_required = set(getattr(definition.input_schema, "required", []) or [])
        account_fields = {"account_id", "advertiser_id", "customer_id"}
        account_required = (
            bool(catalog.account_required)
            if catalog.account_required is not None
            else bool(source_required.intersection(account_fields))
        )
        if account_required and not account_value:
            raise ValueError("该查询需要先提供广告账户 ID，才能加载可用选项")
        if account_value:
            allowed, account_error = self._validate_account_with_principal(
                actual_platform, account_value, False, account_scope
            )
            if not allowed:
                raise PermissionError(account_error)
        permissions = (
            self._granted_permissions
            if granted_permissions is None else frozenset(granted_permissions)
        )
        permission_error = self._check_tool_permissions(definition, permissions)
        if permission_error:
            raise PermissionError(permission_error)

        session = self._ensure_session(
            session_id or str(uuid.uuid4()), user_id, account_value,
            None, tenant_id=tenant_id,
        )
        session.ctx.account_id = account_value
        input_data: dict[str, Any] = {}
        properties = source_properties
        for account_field in ("account_id", "advertiser_id", "customer_id"):
            if account_field in properties and account_value:
                input_data[account_field] = account_value
                break
        for field_name, default_value in (catalog.lookup_defaults or {}).items():
            if field_name in properties and field_name not in input_data:
                input_data[str(field_name)] = copy.deepcopy(default_value)
        context_values = dict(lookup_context or {})
        for dependency in list(catalog.dependencies or ()):
            if not isinstance(dependency, Mapping):
                raise ValueError("lookup dependency metadata must be an object")
            input_field = str(
                dependency.get("input_field") or dependency.get("field") or ""
            ).strip()
            value_path = str(
                dependency.get("value_path") or dependency.get("source_field")
                or input_field
            ).strip()
            if not input_field or input_field not in properties:
                raise ValueError(
                    f"lookup dependency points to undeclared source field: {input_field or value_path}"
                )
            value = context_values.get(value_path)
            if value is None and "." in value_path:
                value = self.input_builder._value_at_path(context_values, value_path)
            if value in (None, "", [], {}):
                if dependency.get("required", True):
                    label = str(dependency.get("label") or value_path)
                    raise ValueError(f"请先选择或填写{label}，再加载当前字段的可用选项")
                continue
            input_data[input_field] = value
        query_field = catalog.query_field
        if query and query_field:
            if query_field not in properties:
                raise ValueError(
                    f"lookup query field is not declared by source Tool: {query_field}"
                )
            input_data[query_field] = str(query).strip()
        missing_source = sorted(
            field_name for field_name in source_required
            if field_name not in input_data
            and not (
                field_name in account_fields
                and catalog.account_required is False
            )
        )
        if missing_source:
            raise ValueError(
                "当前查询还缺少必要的上级条件：" + "、".join(missing_source)
            )
        result = self.tool_executor.execute(session.ctx, source_tool, input_data)
        result = self.input_builder.decorate_lookup_result(
            definition, result, session.ctx, actual_platform,
            target_tool_name=tool_name,
            target_field=field,
        )
        result = self.security.enforce_result_limit(result, definition)
        if not result.success:
            raise RuntimeError(result.error or "parameter lookup failed")
        for selection in result.data.get("parameter_selections", []):
            if (
                selection.get("tool_name") == tool_name
                and selection.get("field") == field
            ):
                return selection
        raise RuntimeError(
            f"provider lookup {source_tool} returned no options for {tool_name}.{field}"
        )

    def _validate_parameter_lookup_contract(self) -> None:
        """Ensure dynamic fields point to executable same-provider read tools."""
        definitions = {tool.name: tool for tool in self.registry.list_all()}
        errors: list[str] = []
        for tool in definitions.values():
            properties = getattr(tool.input_schema, "properties", {}) or {}
            for field_name, field_schema in self.input_builder._iter_schema_fields(properties):
                lookup_tool = self.input_builder.lookup_tool_for_schema_field(
                    field_schema
                )
                if not lookup_tool:
                    continue
                source = definitions.get(lookup_tool)
                if source is None:
                    errors.append(
                        f"{tool.name}.{field_name} references unknown lookup tool {lookup_tool}"
                    )
                    continue
                tool_platform = self._canonical_platform(tool.namespace)
                source_platform = self._canonical_platform(source.namespace)
                if tool_platform != source_platform:
                    errors.append(
                        f"{tool.name}.{field_name} lookup tool {lookup_tool} "
                        f"belongs to {source_platform}, not {tool_platform}"
                    )
                if not source.is_read_tool:
                    errors.append(
                        f"{tool.name}.{field_name} lookup tool {lookup_tool} must be read-only"
                    )
        if errors:
            raise ValueError("Invalid parameter lookup contract: " + "; ".join(errors[:20]))


__all__ = ["AdCreationContractServicesMixin"]
