"""Provider-neutral clarification metadata for incomplete Agent actions.

The Runtime must ask for information before it materializes an execution
plan.  This module only reads the selected Tool contracts and turns missing
schema fields into bounded UI metadata; it never calls a lookup, Provider or
handler and it does not contain channel-specific routing rules.
"""

from __future__ import annotations

import re
from typing import Any, Callable, Iterable, Mapping, Optional

from .tool_registry import validate_tool_input


_EMPTY = (None, "", {}, [])
_MAX_FIELDS = 12
def _is_empty(value: Any) -> bool:
    return value in _EMPTY


def _value_at(value: Any, path: str) -> Any:
    current = value
    for part in str(path or "").split("."):
        if not part or not isinstance(current, Mapping) or part not in current:
            return None
        current = current[part]
    return current


def _schema_at(properties: Any, path: str) -> dict[str, Any]:
    current: Any = properties
    for part in str(path or "").split("."):
        if not part or not isinstance(current, Mapping):
            return {}
        if isinstance(current.get("properties"), Mapping):
            current = current["properties"]
        current = current.get(part)
    return dict(current) if isinstance(current, Mapping) else {}


def _field_from_error(error: str) -> str:
    text = str(error or "")
    patterns = (
        r"Field '([^']+)'",
        r"Missing required field:\s*([A-Za-z0-9_.-]+)",
        r"Provider contract requires field:\s*([A-Za-z0-9_.-]+)",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    for marker in (
        "Provider contract requires one of:",
        "Provider contract requires exactly one of:",
    ):
        if marker in text:
            return "one_of:" + text.split(marker, 1)[1].strip()
    return ""


def _display_action(action: str) -> str:
    return {
        "list": "查询列表",
        "get": "查询详情",
        "report": "查询报表",
        "update": "更新",
        "delete": "删除",
        "pause": "暂停",
        "resume": "恢复",
        "create": "创建",
    }.get(str(action or "").lower(), "执行")


def _display_field(path: str, spec: Mapping[str, Any]) -> str:
    """Use publisher metadata first, then stable generic operator wording."""
    configured = spec.get("label") or spec.get("title")
    if configured:
        return str(configured)
    leaf = str(path or "").rsplit(".", 1)[-1]
    return leaf.replace("_", " ").strip().title() or str(path or "参数")


class ActionClarificationBuilder:
    """Build a bounded clarification response from selected Tool contracts."""

    def __init__(
        self,
        *,
        field_labeler: Optional[Callable[[str, Mapping[str, Any]], Optional[str]]] = None,
        field_hint_builder: Optional[Callable[[str, Mapping[str, Any]], Optional[str]]] = None,
    ) -> None:
        # Presentation vocabulary is supplied by the embedding application.
        # Core only knows how to render a schema field and never owns domain
        # labels such as an advertising account or campaign identifier.
        self.field_labeler = field_labeler
        self.field_hint_builder = field_hint_builder

    def build(
        self,
        intent: Any,
        tool_plan: Mapping[str, Iterable[Any]],
        input_builder: Any,
        context: Any,
        account_by_platform: Optional[Mapping[str, Optional[str]]] = None,
    ) -> dict[str, Any]:
        fields: list[dict[str, Any]] = []
        errors: list[str] = []
        account_by_platform = account_by_platform or {}
        original_account = getattr(context, "account_id", None)
        try:
            for platform, tools in tool_plan.items():
                canonical = str(
                    input_builder.services.canonical_platform(str(platform))
                    if getattr(input_builder, "services", None) is not None
                    else platform
                )
                # Do not let a persisted session account satisfy a write
                # request that was not explicit in the current turn.
                context.account_id = account_by_platform.get(canonical)
                for tool in tools or ():
                    schema = getattr(tool, "input_schema", None)
                    if schema is None:
                        continue
                    built = input_builder.build(tool, intent, platform, context)
                    missing = list(built.pop("_missing_params", []) or [])
                    unknown = list(built.pop("_unknown_params", []) or [])
                    selection_errors = list(built.pop("_selection_errors", []) or [])
                    schema_errors = validate_tool_input(
                        schema, built, include_provider_contract=True
                    )
                    for field_name in missing + unknown + selection_errors:
                        if str(field_name) not in errors:
                            errors.append(str(field_name))
                    for error in schema_errors:
                        field_name = _field_from_error(error)
                        if field_name and field_name not in errors:
                            errors.append(field_name)
                    for field_name in missing:
                        self._add_field(fields, tool, field_name, platform, schema)
                    for error in schema_errors:
                        field_name = _field_from_error(error)
                        if field_name:
                            self._add_field(fields, tool, field_name, platform, schema)
                    for field_name in unknown:
                        self._add_field(
                            fields, tool, field_name, platform, schema,
                            invalid=True,
                        )
        finally:
            context.account_id = original_account

        if not fields and not errors:
            return {}

        visible = fields[:_MAX_FIELDS]
        action = next(
            (
                _display_action(getattr(tool, "action", ""))
                for tools in tool_plan.values()
                for tool in tools or ()
                if getattr(tool, "action", "")
            ),
        )
        resource = next(
            (
                str(getattr(tool, "resource_type", "") or "资源")
                for tools in tool_plan.values()
                for tool in tools or ()
                if getattr(tool, "resource_type", "")
            ),
        )
        labels = [str(item.get("label") or item.get("path")) for item in visible]
        detail = "、".join(dict.fromkeys(labels))
        if len(fields) > len(visible):
            detail += f"等另外 {len(fields) - len(visible)} 项"
        question = f"为了{action}{resource}，还需要补充：{detail or '参数'}。"
        return {
            "kind": "action_clarification",
            "reason": "required_parameters" if fields else "invalid_parameters",
            "question": question,
            "intent_type": str(getattr(intent, "intent_type", "") or ""),
            "platforms": [str(item) for item in tool_plan],
            "fields": visible,
            "errors": errors[:_MAX_FIELDS],
            "hint": "请直接用文字补充，例如“账户 ID 是 …，Campaign ID 是 …”；动态资源 ID 需要来自你的明确输入或列表选择，系统不会猜测。",
        }

    def _add_field(
        self,
        fields: list[dict[str, Any]],
        tool: Any,
        field_name: str,
        platform: str,
        schema: Any,
        *,
        invalid: bool = False,
    ) -> None:
        raw_name = str(field_name or "").strip()
        if not raw_name or raw_name.startswith("one_of:"):
            if raw_name.startswith("one_of:"):
                names = [item.strip() for item in raw_name[7:].split(",") if item.strip()]
                for name in names:
                    self._add_field(fields, tool, name, platform, schema, invalid=invalid)
            return
        if any(item.get("tool") == getattr(tool, "name", "") and item.get("path") == raw_name for item in fields):
            return
        spec = _schema_at(getattr(schema, "properties", {}) or {}, raw_name)
        options = spec.get("enum") if isinstance(spec.get("enum"), list) else []
        lookup = spec.get("lookup_tool")
        if not lookup and isinstance(spec.get("lookup"), Mapping):
            lookup = spec["lookup"].get("tool")
        label = (
            self.field_labeler(raw_name, spec)
            if self.field_labeler is not None else None
        ) or _display_field(raw_name, spec)
        item = {
            "path": raw_name,
            "label": label[:160],
            "platform": str(platform),
            "tool": str(getattr(tool, "name", "") or ""),
            "required": True,
            "source": "lookup" if lookup else "enum" if options else "text",
            "state": "invalid" if invalid else "missing",
        }
        if options:
            item["options"] = options[:20]
        if lookup:
            item["lookup_tool"] = str(lookup)
        description = spec.get("description")
        if description and str(description) != label:
            item["hint"] = str(description)[:240]
        if self.field_hint_builder is not None:
            hint = self.field_hint_builder(raw_name, spec)
            if hint:
                item["hint"] = str(hint)[:240]
        fields.append(item)
