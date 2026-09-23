"""Advertising-domain UI metadata for conversational resource creation.

The objects produced here are A2UI-style descriptions, not executable UI
code.  They are derived from the provider-owned Blueprint and Tool schema so
the Runtime does not need a channel-specific form or field table.
"""

from __future__ import annotations

import re
import json
from datetime import datetime
from typing import Any, Callable, Mapping, Optional

from .blueprint import (
    AdCreationBlueprint,
    BlueprintCascadeEngine,
    BlueprintRegistry,
    _copy_json,
    _schema_at_path,
    _value_at,
)
from ...core.interfaces import ParsedIntent
from ...core.namespace import normalize_namespace as normalize_platform


_MAX_CARDS = 8
# Creation forms must not silently truncate a provider contract.  The largest
# current Blueprint is TikTok Product Sales; keep a generous hard bound for a
# hostile/custom Tool Source while preserving a finite response size.
_MAX_FIELDS = 160
_MAX_OPTIONS = 100
_PRESENTATIONS = {
    "text_list", "asset_picker", "file_reference", "derived_readonly",
    "object_editor", "advanced_json",
}

_INPUT_MODES = {
    "user_required", "user_optional", "auto_default", "auto_derived",
    "context_required", "asset_required",
}
_USER_INPUT_MODES = {"user_required", "context_required", "asset_required"}


_HIERARCHY_LABELS = {
    "campaign": "Campaign",
    "campaigns": "Campaign",
    "ad_set": "Ad Set",
    "adset": "Ad Set",
    "ad_group": "Ad Group",
    "adgroup": "Ad Group",
    "ad": "Ad",
    "insertion_order": "Insertion Order",
    "line_item": "Line Item",
    "creative": "Creative",
    "asset_group": "Asset Group",
    "product_group": "Product Group",
    "listing_group_filter": "Listing Group",
}


def _blueprint_contract_metadata(
    blueprint: AdCreationBlueprint, fields: list[Mapping[str, Any]],
) -> dict[str, Any]:
    """Publish bounded quality metadata for the wizard and template UI.

    This is presentation metadata only.  The Tool schema and Runtime remain
    authoritative for validation and execution; the summary makes coverage
    and the amount of advanced configuration explicit to a human user.
    """
    hierarchy_order: list[str] = []
    hierarchy_counts: dict[str, int] = {}
    required_count = 0
    conditional_count = 0
    lookup_count = 0
    default_count = 0
    advanced_count = 0
    derived_count = 0
    for field in fields:
        path = str(field.get("path") or "")
        root = path.split(".", 1)[0].lower()
        hierarchy = _HIERARCHY_LABELS.get(root, root.replace("_", " ").title() or "通用")
        if hierarchy not in hierarchy_counts:
            hierarchy_order.append(hierarchy)
            hierarchy_counts[hierarchy] = 0
        hierarchy_counts[hierarchy] += 1
        if field.get("required") or field.get("required_when"):
            required_count += 1
        if field.get("required_when") or field.get("visible_when") or field.get("option_rules"):
            conditional_count += 1
        if field.get("source") == "lookup" or field.get("lookup_tool"):
            lookup_count += 1
        if "default" in field or field.get("default_strategy"):
            default_count += 1
        auto_advanced = (
            field.get("auto_exposed")
            and not field.get("required")
            and not field.get("required_when")
            and not field.get("lookup_tool")
            and field.get("presentation") not in {"asset_picker", "file_reference"}
        )
        if field.get("presentation") == "advanced_json" or field.get("advanced") or auto_advanced:
            advanced_count += 1
        if field.get("presentation") == "derived_readonly":
            derived_count += 1
    return {
        "field_count": len(fields),
        "required_count": required_count,
        "conditional_count": conditional_count,
        "lookup_count": lookup_count,
        "declared_default_count": default_count,
        "advanced_count": advanced_count,
        "derived_count": derived_count,
        "hierarchies": [
            {"name": name, "field_count": hierarchy_counts[name]}
            for name in hierarchy_order
        ],
        "template": {
            "supported": True,
            "version_locked": True,
            "stores_only_declared_fields": True,
        },
    }


def _json_shape(field: Mapping[str, Any], schema: Mapping[str, Any]) -> Optional[str]:
    """Return the declared JSON container shape for an editable payload.

    Advanced payload fields are intentionally open-ended, but their outer
    JSON container is still known from the Provider Tool schema.  Publishing
    that small piece of metadata lets a client catch object/array swaps before
    the draft reaches the server without duplicating provider rules in UI.
    """
    declared = str(field.get("json_shape") or schema.get("json_shape") or "").strip().lower()
    if declared in {"object", "array", "object_or_array"}:
        return declared
    schema_type = schema.get("type")
    if schema_type == "object":
        return "object"
    if schema_type == "array":
        return "array"
    if isinstance(schema_type, list):
        types = {str(item).lower() for item in schema_type}
        if {"object", "array"}.issubset(types):
            return "object_or_array"
    return None


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
    for raw_platform, values in (getattr(intent, "scoped_parameters", {}) or {}).items():
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


def _field_name(field: Mapping[str, Any], schema: Mapping[str, Any]) -> str:
    return str(
        field.get("provider_field")
        or field.get("path", "").rsplit(".", 1)[-1]
        or schema.get("title", "")
    ).strip().lower()


def _generated_name(intent: ParsedIntent, provider_values: Mapping[str, Any], field: Mapping[str, Any]) -> str:
    """Generate a readable, editable resource name without provider guesses."""
    objective = (
        getattr(intent, "objective", None)
        or provider_values.get("objective")
        or provider_values.get("objective_type")
        or provider_values.get("campaign_type")
        or "广告"
    )
    resource = str(field.get("path", "resource")).split(".", 1)[0]
    resource_label = {
        "campaign": "Campaign", "ad_group": "Ad Group", "ad_set": "Ad Set",
        "ad": "Ad", "line_item": "Line Item", "insertion_order": "Insertion Order",
    }.get(resource, resource.replace("_", " ").title())
    date_label = datetime.now().strftime("%Y%m%d")
    return f"{str(objective).replace('_', ' ')} · {resource_label} · {date_label}"


def _safe_default(
    intent: ParsedIntent,
    provider_values: Mapping[str, Any],
    field: Mapping[str, Any],
    schema: Mapping[str, Any],
    options_override: Optional[list[Any]] = None,
) -> tuple[Any, Optional[str], Optional[str]]:
    """Resolve only provider-neutral, reversible defaults.

    Account-owned resources, geography, URLs and assets deliberately have no
    fallback here. Their absence must remain visible as a user/context input.
    """
    if "default" in field:
        return _copy_json(field["default"]), "blueprint", str(
            field.get("default_reason") or "按当前广告蓝图预设，可在高级设置中修改。"
        )
    if "default" in schema:
        return _copy_json(schema["default"]), "tool_schema", str(
            field.get("default_reason") or "按渠道 Tool Schema 默认值填充，可修改。"
        )
    strategy = str(field.get("default_strategy") or schema.get("default_strategy") or "").strip().lower()
    field_name = _field_name(field, schema)
    if strategy == "generated_name" or field_name in {"name", "campaign_name", "campaignname", "adgroup_name", "ad_name"}:
        return _generated_name(intent, provider_values, field), "generated", "系统按推广目标、广告层级和日期生成，可修改。"

    options = list(options_override) if options_override else _options(field, schema)
    if not options:
        return None, None, None
    if field.get("presentation") == "derived_readonly" and len(options) == 1:
        return _copy_json(options[0]), "derived", "由当前创建类型自动匹配。"

    normalized = field_name.replace("-", "_")
    if normalized in {"buying_type", "purchase_type"} and "AUCTION" in options:
        return "AUCTION", "policy", "默认采用竞价购买，适用于大多数自动优化场景。"
    if normalized in {"bid_type", "deep_bid_type"}:
        no_bid = next((value for value in options if "NO_BID" in str(value)), None)
        if no_bid is not None:
            return _copy_json(no_bid), "policy", "默认不设置人工出价上限，让平台自动探索，可修改。"
    if normalized in {"budget_mode", "budgetmode"}:
        daily = next((value for value in options if any(token in str(value).upper() for token in ("DYNAMIC_DAILY", "_DAY", "DAILY"))), None)
        if daily is not None:
            return _copy_json(daily), "policy", "默认使用日预算，便于按天控制花费，可修改。"
    if normalized in {"schedule_type", "scheduletype"}:
        from_now = next((value for value in options if "FROM_NOW" in str(value).upper()), None)
        if from_now is not None:
            return _copy_json(from_now), "policy", "默认从开始时间起立即进入投放，可修改。"
    if normalized in {"gender", "gender_type"}:
        unlimited = next((value for value in options if "UNLIMITED" in str(value).upper()), None)
        if unlimited is not None:
            return _copy_json(unlimited), "policy", "默认不限性别，避免系统替你缩窄受众。"
    if normalized in {"placement_type", "placement_mode"}:
        automatic = next((value for value in options if "AUTOMATIC" in str(value).upper()), None)
        if automatic is not None:
            return _copy_json(automatic), "policy", "默认使用自动版位，让平台分配流量。"
    if normalized in {"optimization_goal", "optimization_event"}:
        preferred = (
            "LANDING_PAGE_VIEWS", "OFFSITE_CONVERSIONS", "CONVERT",
            "MAXIMIZE_CONVERSIONS", "LINK_CLICKS", "CLICK", "REACH",
        )
        selected = next((value for wanted in preferred for value in options if str(value).upper() == wanted), None)
        if selected is not None:
            return _copy_json(selected), "policy", "默认选择与当前推广目标匹配的优化方向，可修改。"
    if normalized in {"billing_event", "billingevent"}:
        selected = next((value for wanted in ("IMPRESSIONS", "OCPM", "CPM") for value in options if str(value).upper() == wanted), None)
        if selected is not None:
            return _copy_json(selected), "policy", "默认采用平台常用计费事件，可修改。"
    if normalized in {"bid_strategy", "bidding_strategy"}:
        selected = next((value for value in options if str(value).upper() == "LOWEST_COST_WITHOUT_CAP"), None)
        if selected is not None:
            return _copy_json(selected), "policy", "默认采用最低成本策略，不设置人工上限，可修改。"
    if normalized in {"contains_eu_political_advertising", "eu_political_advertising"}:
        safe = next((value for value in options if "DOES_NOT_CONTAIN" in str(value).upper()), None)
        if safe is not None:
            return _copy_json(safe), "policy", "默认声明不包含欧盟政治广告，可按实际情况修改。"
    if normalized in {"budget_optimize_on", "catalog_enabled", "brand_guidelines_enabled"} and False in options:
        return False, "policy", "默认关闭可选增强能力，避免未准备资源时产生额外约束。"
    if normalized == "special_ad_categories":
        none_value = next((value for value in options if str(value).upper() == "NONE"), None)
        if none_value is not None:
            return [none_value], "policy", "默认声明不属于特殊广告类别，可按业务实际情况修改。"
    schema_type = schema.get("type")
    is_array = schema_type == "array" or (
        isinstance(schema_type, list) and "array" in schema_type
    )
    if normalized == "age_groups" and is_array:
        age_options = [value for value in options if str(value).upper().startswith("AGE_")]
        if age_options:
            return _copy_json(age_options), "policy", "默认覆盖全部年龄段，避免系统替你缩窄受众。"
    if len(options) == 1 and field.get("source") != "lookup":
        return _copy_json(options[0]), "derived", "当前创建类型只有一个合法选项，系统自动匹配。"
    return None, None, None


def _input_mode(field: Mapping[str, Any], schema: Mapping[str, Any], default_source: Optional[str]) -> str:
    declared = str(field.get("input_mode") or schema.get("input_mode") or "").strip().lower()
    if declared in _INPUT_MODES:
        return declared
    if field.get("presentation") == "derived_readonly":
        return "auto_derived"
    if default_source:
        return "auto_default"
    lookup_tool = schema.get("lookup_tool") or (
        schema.get("lookup", {}).get("tool") if isinstance(schema.get("lookup"), Mapping) else None
    )
    if lookup_tool or field.get("source") == "lookup":
        return "context_required" if field.get("required") or field.get("required_when") else "user_optional"
    return "user_required" if field.get("required") or field.get("required_when") else "user_optional"


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


def _merge_conditions(*conditions: Any) -> Optional[dict[str, Any]]:
    """Combine provider applicability and workflow visibility declaratively."""
    normalized = [
        _copy_json(condition)
        for condition in conditions
        if isinstance(condition, Mapping) and condition
    ]
    if not normalized:
        return None

    # A Blueprint may already describe the same condition that a Provider
    # schema publishes.  Keep the composition semantics (all conditions must
    # hold), but flatten and de-duplicate equivalent clauses so clients do not
    # receive noisy ``all: [same, same]`` metadata.
    clauses: list[dict[str, Any]] = []
    for condition in normalized:
        if isinstance(condition.get("all"), list):
            clauses.extend(
                item for item in condition["all"]
                if isinstance(item, Mapping) and item
            )
        else:
            clauses.append(condition)
    unique: list[dict[str, Any]] = []
    seen: set[str] = set()
    for clause in clauses:
        key = json.dumps(clause, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        if key not in seen:
            seen.add(key)
            unique.append(clause)
    if len(unique) == 1:
        return unique[0]
    return {"all": unique}


class CreationCardBuilder:
    """Build bounded parameter cards from registered declarative metadata."""

    def __init__(
        self,
        blueprint_registry: BlueprintRegistry,
        tool_registry: Any,
        cascade: Optional[BlueprintCascadeEngine] = None,
        *,
        account_provider: Optional[Callable[[str, Any], list[Any]]] = None,
        template_provider: Optional[Callable[..., list[Mapping[str, Any]]]] = None,
    ) -> None:
        self.blueprints = blueprint_registry
        self.tools = tool_registry
        self.cascade = cascade or BlueprintCascadeEngine()
        self.account_provider = account_provider
        self.template_provider = template_provider

    def _account_options(
        self, provider: str, account_scope: Any,
    ) -> list[dict[str, Any]]:
        if not callable(self.account_provider):
            return []
        try:
            raw = self.account_provider(provider, account_scope) or []
        except Exception:
            return []
        options: list[dict[str, Any]] = []
        for item in raw[:100]:
            if isinstance(item, Mapping):
                value = str(item.get("value") or item.get("account_id") or "").strip()
                label = str(item.get("label") or value)
            else:
                value = str(item or "").strip()
                label = f"账户 {value}"
            if value:
                options.append({"value": value, "label": label})
        return options

    def _template_options(
        self,
        provider: str,
        account_id: Optional[str],
        account_scope: Any,
        tenant_id: str,
        user_id: str,
    ) -> list[dict[str, Any]]:
        if not callable(self.template_provider):
            return []
        try:
            raw = self.template_provider(
                provider,
                account_id,
                account_scope,
                tenant_id,
                user_id,
            ) or []
        except Exception:
            return []
        options: list[dict[str, Any]] = []
        for item in raw[:100]:
            if not isinstance(item, Mapping):
                continue
            # Values remain server-side. The selector only needs immutable
            # identity and bounded explanation metadata.
            options.append({
                key: _copy_json(item[key])
                for key in (
                    "template_id", "name", "description", "provider",
                    "blueprint_id", "blueprint_version", "ad_format",
                    "scope_type", "account_id", "verification_status",
                    "verified_scope", "required_inputs", "tags", "source",
                    "template_kind", "is_default", "covered_fields",
                )
                if key in item
            })
        return options

    @staticmethod
    def _account_from_values(
        provider_values: Mapping[str, Any],
        explicit_account_id: Optional[str],
    ) -> Optional[str]:
        if explicit_account_id not in (None, ""):
            return str(explicit_account_id).strip()
        for key in ("account_id", "ad_account_id", "advertiser_id", "customer_id"):
            value = provider_values.get(key)
            if value not in (None, ""):
                return str(value).strip()
        return None

    def _attach_creation_context(
        self,
        card: dict[str, Any],
        *,
        provider: str,
        provider_values: Mapping[str, Any],
        account_scope: Any,
        tenant_id: str,
        user_id: str,
        explicit_account_id: Optional[str],
    ) -> dict[str, Any]:
        account_options = self._account_options(provider, account_scope)
        account_id = self._account_from_values(provider_values, explicit_account_id)
        card["account_options"] = account_options
        card["account_id"] = account_id
        card["account_required"] = True
        template_options = self._template_options(
            provider,
            account_id,
            account_scope,
            tenant_id,
            user_id,
        )
        if card.get("blueprint_id"):
            template_options = [
                item for item in template_options
                if item.get("blueprint_id") == card.get("blueprint_id")
            ]
        card["template_options"] = template_options
        return card

    @staticmethod
    def _blueprint_condition(
        condition: Any, prefix: str, known_paths: Optional[set[str]] = None,
        alias_paths: Optional[Mapping[str, str]] = None,
        field_paths: Optional[Mapping[str, str]] = None,
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
                        value, prefix, known_paths, alias_paths, field_paths
                    )
                    for value in condition.get("all", [])
                ) if item is not None
            ]
            return {"all": items} if items else None
        if "any" in condition:
            items = [
                item for item in (
                    CreationCardBuilder._blueprint_condition(
                        value, prefix, known_paths, alias_paths, field_paths
                    )
                    for value in condition.get("any", [])
                ) if item is not None
            ]
            return {"any": items} if items else None
        if "not" in condition:
            nested = CreationCardBuilder._blueprint_condition(
                condition.get("not"), prefix, known_paths, alias_paths, field_paths
            )
            return {"not": nested} if nested else None
        if "field" in condition:
            field = str(condition.get("field") or "").strip()
            if not field:
                return None
            result = dict(condition)
            result["field"] = CreationCardBuilder._condition_path(
                field, prefix, known_paths, alias_paths, field_paths
            )
            return result
        if not condition:
            return None
        return {
            "all": [
                {
                    "field": CreationCardBuilder._condition_path(
                        field, prefix, known_paths, alias_paths, field_paths
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
        field_paths: Optional[Mapping[str, str]] = None,
    ) -> str:
        if "." in field:
            return field
        explicit_path = (field_paths or {}).get(field)
        if explicit_path:
            return explicit_path
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
                ("any_of", getattr(schema, "requires_any_of", []) or []),
                ("exactly_one_of", getattr(schema, "requires_exactly_one_of", []) or []),
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
                        # contract for Tool Source/Blueprint authors to fix.
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

    def _schema_visibility(
        self,
        schema: Mapping[str, Any],
        prefix: str,
        known_paths: set[str],
        alias_paths: Mapping[str, str],
        field_paths: Optional[Mapping[str, str]] = None,
    ) -> Optional[dict[str, Any]]:
        """Translate provider-owned UI applicability into Blueprint paths.

        ``ui_visible_when`` is metadata, not executable logic.  It uses the
        same compact condition vocabulary as ToolSchema conditional rules,
        but is intentionally consumed only by the presentation layer.  The
        provider can therefore keep one field contract while each creation
        surface hides parameters that do not belong to the selected format.
        """
        condition = schema.get("ui_visible_when")
        if not isinstance(condition, Mapping):
            return None
        return self._blueprint_condition(
            condition, prefix, known_paths, alias_paths, field_paths
        )

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
        explicit_field_paths: dict[str, dict[str, list[str]]] = {}
        for field in existing_fields:
            tool_name, schema_path, _ = _schema_for_ref(
                self.tools, str(field.get("tool_ref"))
            )
            path = str(field.get("path") or "")
            if tool_name and "." in path:
                prefix_by_tool.setdefault(tool_name, path.split(".", 1)[0])
                field_name = schema_path.rsplit(".", 1)[-1]
                explicit_field_paths.setdefault(tool_name, {}).setdefault(
                    field_name, []
                ).append(path)

        # A single Tool may intentionally be presented at multiple hierarchy
        # levels (for example one atomic provider operation may expose
        # campaign, ad_group and ad fields).  Keep the explicit Blueprint
        # placement for condition translation instead of assuming that the
        # first prefix is the correct owner of every field.
        unique_field_paths: dict[str, dict[str, str]] = {
            tool_name: {
                field_name: paths[0]
                for field_name, paths in fields.items()
                if len(set(paths)) == 1
            }
            for tool_name, fields in explicit_field_paths.items()
        }

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
            field_paths = unique_field_paths.get(tool_name, {})
            required = set(getattr(schema_object, "required", []) or [])
            required.update(getattr(schema_object, "requires", []) or [])
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
                visibility = self._schema_visibility(
                    raw_schema, prefix, known_paths, alias_paths, field_paths
                )
                if visibility is not None:
                    field["visible_when"] = visibility
                for key in (
                    "default", "option_labels", "option_aliases", "manual_entry", "lookup_tool",
                    "lookup_result_key", "selection_value_fields", "selection_label_fields",
                    "lookup_account_required", "lookup_dependencies", "lookup_query_field",
                    "lookup_defaults",
                    "accept", "presentation", "value_shape", "json_shape",
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
                        known_paths, alias_paths, field_paths,
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
            "default", "option_labels", "option_aliases", "manual_entry", "lookup_tool",
            "lookup_result_key", "selection_value_fields", "selection_label_fields",
            "lookup_account_required", "lookup_dependencies", "lookup_query_field",
            "lookup_defaults", "accept", "presentation", "value_shape", "json_shape",
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
            required.update(getattr(schema_object, "requires", []) or [])
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

            provider_visibility = self._schema_visibility(
                schema,
                prefix_by_tool.get(tool_name, "resource"),
                known_paths,
                alias_paths,
                unique_field_paths.get(tool_name, {}),
            )
            if provider_visibility is not None:
                merged_visibility = _merge_conditions(
                    field.get("visible_when"), provider_visibility
                )
                if merged_visibility is not None:
                    field["visible_when"] = merged_visibility

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
                        unique_field_paths.get(tool_name, {}),
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
        document["ui_contract"] = _blueprint_contract_metadata(blueprint, all_fields)
        return AdCreationBlueprint.from_dict(document)

    def is_creation_intent(
        self,
        intent: ParsedIntent,
        tool_plan: Optional[Mapping[str, Any]] = None,
    ) -> bool:
        """Determine creation from the active Tool contract.

        The interaction surface follows ``ToolDefinition.action`` rather
        than an intent-name prefix. A Tool Source can therefore publish a
        custom intent such as ``launch_asset`` without a Core change.
        """
        candidates: list[Any] = []
        if isinstance(tool_plan, Mapping):
            candidates = [
                tool
                for tools in tool_plan.values()
                for tool in (tools or [])
            ]
        else:
            intent_type = str(getattr(intent, "intent_type", "") or "").strip()
            list_by_namespace = getattr(self.tools, "list_by_namespace", None)
            if callable(list_by_namespace):
                for platform in getattr(intent, "namespaces", []) or []:
                    try:
                        definitions = list_by_namespace(normalize_platform(platform))
                    except (KeyError, LookupError, TypeError):
                        definitions = []
                    candidates.extend(
                        definition for definition in definitions
                        if intent_type in set(
                            getattr(definition, "intent_types", []) or []
                        )
                    )
        return any(
            str(getattr(tool, "action", "") or "").strip().lower() == "create"
            for tool in candidates
        )

    def _selector_text_matches(
        self, text: str, provider: str,
    ) -> list[tuple[int, AdCreationBlueprint, Mapping[str, Any], Any, str]]:
        """Find an explicit selector choice from provider-owned metadata.

        This is intentionally separate from ``_resolve``.  It is used when a
        short follow-up (for example ``流量广告``) should continue a persisted
        creation draft.  Only selector options and Blueprint ``match_terms``
        are accepted; Runtime never maintains a provider/action synonym map.
        """
        normalized_text = _normalized(text)
        if not normalized_text:
            return []
        matches: list[tuple[int, AdCreationBlueprint, Mapping[str, Any], Any, str]] = []
        for blueprint in self.blueprints.list(provider=provider):
            selector = blueprint.selector or {}
            if not selector:
                continue
            best: tuple[int, Any, str] | None = None
            phrases: list[tuple[str, Any]] = []
            for option in _selector_options(selector):
                phrases.extend([
                    (str(option.get("value") or ""), option.get("value")),
                    (str(option.get("label") or ""), option.get("value")),
                ])
            phrases.extend((str(term), None) for term in blueprint.match_terms)
            for phrase, option_value in phrases:
                normalized_phrase = _normalized(phrase)
                # Very short phrases such as a one-letter campaign code are
                # not safe natural-language selectors.
                if len(normalized_phrase) < 2 or normalized_phrase not in normalized_text:
                    continue
                value = option_value
                if value is None and len(selector.get("values", [])) == 1:
                    value = selector["values"][0]
                if value is None:
                    continue
                candidate = (len(normalized_phrase), value, phrase)
                if best is None or candidate[0] > best[0]:
                    best = candidate
            if best is not None:
                matches.append((best[0], blueprint, selector, best[1], best[2]))
        return matches

    def merge_pending_intent(
        self, pending: ParsedIntent, follow_up: ParsedIntent, follow_up_text: str,
    ) -> Optional[ParsedIntent]:
        """Merge a deterministic follow-up into a persisted creation draft.

        The pending intent is the source of the original operation and
        platform.  The follow-up can contribute explicitly parsed values or a
        selector phrase declared by a Blueprint.  A free-form short answer
        cannot change the platform or invent an account/resource ID.
        """
        if not self.is_creation_intent(pending):
            return None
        merged = _copy_json(pending.to_dict())
        merged["raw_input"] = (
            f"{pending.raw_input}\n{str(follow_up_text or '').strip()}"
        ).strip()
        current_params = merged.get("scoped_parameters")
        if not isinstance(current_params, Mapping):
            current_params = merged.get("scoped_parameters")
        if not isinstance(current_params, Mapping):
            current_params = {}
        current_params = _copy_json(current_params)
        changed = False

        follow_up_params = getattr(follow_up, "scoped_parameters", {}) or {}
        for raw_platform, values in follow_up_params.items():
            if not isinstance(values, Mapping):
                continue
            target_platform = normalize_platform(raw_platform)
            if target_platform not in {
                normalize_platform(item) for item in (pending.namespaces or [])
            }:
                continue
            destination = dict(current_params.get(target_platform, {}) or {})
            for key, value in values.items():
                if value not in (None, "", {}, []):
                    if destination.get(key) != value:
                        destination[str(key)] = _copy_json(value)
                        changed = True
            current_params[target_platform] = destination

        for provider in list(pending.namespaces or []):
            canonical = normalize_platform(provider)
            matches = self._selector_text_matches(follow_up_text, canonical)
            if not matches:
                continue
            best_score = max(item[0] for item in matches)
            best = [item for item in matches if item[0] == best_score]
            if len(best) != 1:
                continue
            _score, blueprint, selector, selector_value, _phrase = best[0]
            destination = dict(current_params.get(canonical, {}) or {})
            for field in blueprint.fields:
                if str(field.get("path")) != str(selector.get("field")):
                    continue
                _tool_name, schema_path, _schema = _schema_for_ref(
                    self.tools, field["tool_ref"]
                )
                if destination.get(schema_path) != selector_value:
                    destination[schema_path] = selector_value
                    changed = True
                break
            dimension = str(selector.get("dimension") or "")
            if dimension and destination.get(dimension) != selector_value:
                destination[dimension] = selector_value
                changed = True
            current_params[canonical] = destination
            attributes = dict(merged.get("attributes") or {})
            if dimension and attributes.get(dimension) != selector_value:
                attributes[dimension] = selector_value
                merged["attributes"] = attributes
                changed = True

        # Explicit scalar values from a structured follow-up are safe to
        # carry forward; the original creation intent and platform stay fixed.
        for field_name, value in (getattr(follow_up, "attributes", {}) or {}).items():
            if value not in (None, "", [], {}):
                attributes = dict(merged.get("attributes") or {})
                if attributes.get(field_name) != value:
                    attributes[field_name] = _copy_json(value)
                    merged["attributes"] = attributes
                    changed = True
        if not changed:
            return None
        merged["scoped_parameters"] = current_params
        return ParsedIntent(**{
            key: value for key, value in merged.items()
            if key in ParsedIntent.__dataclass_fields__
        })

    def build_clarification(self, intent: ParsedIntent) -> dict[str, Any]:
        """Return a text/choice clarification without a creation form.

        A selector is deliberately not rendered as a parameter card.  The
        user must first choose a concrete Blueprint branch; only then can the
        full Campaign/Ad Group/Ad form be shown.
        """
        selector_cards = [
            card for card in self.build(intent)
            if card.get("type") == "ad_creation_selector"
        ]
        if not selector_cards:
            return {}
        selector = selector_cards[0]
        options: list[dict[str, Any]] = []
        for field in selector.get("fields", []):
            for option in field.get("options", []):
                if not isinstance(option, Mapping):
                    continue
                item = dict(option)
                item["field"] = field.get("path")
                item["field_label"] = field.get("label")
                if item not in options:
                    options.append(item)
        provider = str(selector.get("provider") or "广告平台")
        return {
            "kind": "creation_clarification",
            "provider": provider,
            "question": f"请先确定要创建的 {provider} 广告推广目标或广告类型。",
            "options": options[:_MAX_OPTIONS],
            "reason": "creation_selector_required",
        }

    def llm_context(
        self,
        max_chars: int = 3500,
        providers: Optional[list[str] | tuple[str, ...] | set[str]] = None,
    ) -> str:
        """Return bounded Blueprint metadata for intent parsing only.

        When a channel has already been mentioned, keep the same bounded
        context budget but spend it on that channel's complete creation
        catalog. Without this scope, a large multi-provider catalog can be
        truncated before the relevant Blueprint and force the LLM to guess a
        format that the UI could have declared exactly.
        """
        lines: list[str] = []
        provider_set = {
            normalize_platform(str(provider))
            for provider in (providers or ())
            if str(provider or "").strip()
        }
        blueprints = self.blueprints.list()
        if provider_set:
            scoped = [
                item for item in blueprints
                if normalize_platform(item.provider) in provider_set
            ]
            if scoped:
                blueprints = scoped
        for raw_blueprint in blueprints[:40]:
            blueprint = self.expand_blueprint(raw_blueprint)
            selector = blueprint.selector or {}
            selector_text = ""
            if selector:
                selector_text = (
                    f"; selector={selector.get('dimension')}:{selector.get('values', [])}"
                )
            if blueprint.match_terms:
                selector_text += f"; match_terms={list(blueprint.match_terms)}"
            fields = []
            for field in blueprint.fields[:30]:
                tool_name, schema_path, schema = _schema_for_ref(self.tools, field["tool_ref"])
                if _SENSITIVE_FIELD.search(str(field.get("path"))) or _SENSITIVE_FIELD.search(schema_path):
                    continue
                field_type = schema.get("type", "string")
                options = _options(field, schema)
                option_labels = field.get("option_labels") or schema.get("option_labels") or {}
                option_aliases = field.get("option_aliases") or schema.get("option_aliases") or {}
                option_context = []
                for option in options[:12]:
                    label = (
                        option_labels.get(str(option), option)
                        if isinstance(option_labels, Mapping) else option
                    )
                    aliases = (
                        option_aliases.get(str(option), [])
                        if isinstance(option_aliases, Mapping) else []
                    )
                    if isinstance(aliases, str):
                        aliases = [aliases]
                    option_context.append({
                        "value": option,
                        "label": label,
                        "aliases": list(aliases)[:4]
                        if isinstance(aliases, (list, tuple, set)) else [],
                    })
                required_suffix = ",required" if field.get("required") else ""
                options_suffix = f",options={option_context}" if option_context else ""
                fields.append(
                    f"{field['path']}->{tool_name}.{schema_path}"
                    f"({field_type}{required_suffix}{options_suffix})"
                )
            lines.append(
                f"provider={blueprint.provider}; id={blueprint.blueprint_id}; "
                f"title={blueprint.title}{selector_text}; fields=" + ", ".join(fields)
            )
        return "\n".join(lines)[:max_chars]

    def _provided_field_value(
        self, intent: ParsedIntent, provider_values: Mapping[str, Any], field: Mapping[str, Any]
    ) -> Any:
        tool_name, schema_path, schema = _schema_for_ref(self.tools, field["tool_ref"])
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

    def _field_value(
        self, intent: ParsedIntent, provider_values: Mapping[str, Any], field: Mapping[str, Any]
    ) -> Any:
        _tool_name, _schema_path, schema = _schema_for_ref(self.tools, field["tool_ref"])
        value = self._provided_field_value(intent, provider_values, field)
        # Selector resolution must inspect the caller's value, not a
        # presentation-only single-option value from a different Blueprint.
        # Derived defaults are materialized only after the concrete Blueprint
        # has been selected in _form_card.
        if value is None and field.get("presentation") == "derived_readonly":
            return None
        if value is None:
            value, _source, _reason = _safe_default(intent, provider_values, field, schema)
        return value

    def _resolve(self, intent: ParsedIntent, provider: str) -> tuple[Optional[AdCreationBlueprint], Any, dict[str, Any]]:
        provider_values = _provider_values(intent, provider)
        candidates = self.blueprints.list(provider=provider)
        # A caller may already know the provider-owned format (for example
        # ``DEMAND_GEN_CAROUSEL``).  This is more specific than the campaign
        # channel selector and must win before natural-language matching.
        explicit_format = provider_values.get("ad_format")
        if explicit_format is not None:
            explicit_matches = [
                blueprint for blueprint in candidates
                if _normalized(explicit_format) == _normalized(blueprint.ad_format)
            ]
            if len(explicit_matches) == 1:
                return explicit_matches[0], provider_values, explicit_matches[0].ad_format

        matching: list[tuple[AdCreationBlueprint, Any]] = []
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
                matching.append((blueprint, selected))
                continue
            for option in _selector_options(selector):
                if _normalized(selected) in {_normalized(option["value"]), _normalized(option["label"])}:
                    matching.append((blueprint, option["value"]))
                    break

        if len(matching) == 1:
            blueprint, selector_value = matching[0]
            return blueprint, provider_values, selector_value

        # Blueprint authors can declare format-specific phrases without
        # adding provider/channel branches to Runtime.  Only a unique best
        # match is accepted; a generic request such as "Demand Gen" remains
        # a selector card instead of silently choosing a creative variant.
        raw_input = str(getattr(intent, "raw_input", "") or "")
        scored: list[tuple[int, AdCreationBlueprint, Any]] = []
        # Evaluate declared natural-language terms against the full candidate
        # set, not only against selector matches.  This is what lets a user
        # say “App conversion” before a provider-specific canonical enum has
        # been emitted by the parser.  A term may choose a Blueprint, but it
        # still must resolve to one legal selector value.
        for blueprint in candidates:
            selector = blueprint.selector or {}
            selector_options = _selector_options(selector)
            selector_value = None
            selector_scores: list[int] = []
            for option in selector_options:
                for phrase in (option.get("value"), option.get("label")):
                    normalized_phrase = _normalized(phrase)
                    if normalized_phrase and normalized_phrase in _normalized(raw_input):
                        selector_scores.append(len(normalized_phrase))
                        selector_value = option.get("value")
            if selector_value is None and len(selector.get("values", [])) == 1:
                selector_value = selector["values"][0]
            term_scores = [
                len(_normalized(term))
                for term in blueprint.match_terms
                if _normalized(term) and _normalized(term) in _normalized(raw_input)
            ]
            if term_scores and selector_value is not None:
                scored.append((max(term_scores + selector_scores), blueprint, selector_value))
        if scored:
            best_score = max(item[0] for item in scored)
            best = [item for item in scored if item[0] == best_score]
            if len(best) == 1:
                _, blueprint, selector_value = best[0]
                return blueprint, provider_values, selector_value

        if len(candidates) == 1 and candidates[0].selector is None:
            return candidates[0], provider_values, None
        return None, provider_values, None

    def _selector_card(
        self, intent: ParsedIntent, provider: str, provider_values: Mapping[str, Any],
        *,
        account_scope: Any = None,
        tenant_id: str = "default",
        user_id: str = "anonymous",
        account_id: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        candidates = [item for item in self.blueprints.list(provider=provider) if item.selector]
        if not candidates:
            return None
        # If the conversation already supplied a valid parent selector, keep
        # the card scoped to that branch.  Invalid or unknown values retain
        # the full catalog so the user can correct them instead of receiving
        # an empty card.  This is generic over selector dimensions and does
        # not contain provider/channel names.
        scoped: list[AdCreationBlueprint] = []
        for blueprint in candidates:
            selector = blueprint.selector or {}
            dimension = str(selector.get("dimension") or "")
            selected = provider_values.get(dimension)
            if dimension == "ad_format" and provider_values.get("ad_format") is not None:
                if _normalized(provider_values.get("ad_format")) == _normalized(blueprint.ad_format):
                    scoped.append(blueprint)
                continue
            if selected is None:
                for field in blueprint.fields:
                    if str(field.get("path")) == str(selector.get("field")):
                        selected = self._field_value(intent, provider_values, field)
                        break
            options = _selector_options(selector)
            if selected is None:
                continue
            if selected in selector.get("values", []) or any(
                _normalized(selected) in {
                    _normalized(option["value"]), _normalized(option["label"])
                }
                for option in options
            ):
                scoped.append(blueprint)
        if scoped:
            candidates = scoped
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
                entry.setdefault("blueprint_options", []).append({
                    "blueprint_id": blueprint.blueprint_id,
                    "label": blueprint.title,
                    "selector_value": option.get("value"),
                })
        if not dimensions:
            return None
        fields = []
        for dimension, item in list(dimensions.items())[:8]:
            current = provider_values.get(item["provider_field"])
            if current is None and item["provider_field"] != dimension:
                current = provider_values.get(dimension)
            if current is None:
                current = getattr(intent, "objective", None) if dimension == "objective" else getattr(intent, "campaign_type", None)
            blueprint_options = item.get("blueprint_options", [])
            duplicated_values = {
                value for value in (
                    option.get("selector_value") for option in blueprint_options
                )
                if sum(
                    1 for option in blueprint_options
                    if option.get("selector_value") == value
                ) > 1
            }
            if duplicated_values:
                # Keep the underlying provider selector value in metadata,
                # but use the immutable Blueprint ID as the UI value so two
                # variants sharing one campaign type remain selectable.
                options = [
                    {
                        "value": option["blueprint_id"],
                        "label": option["label"],
                        "blueprint_id": option["blueprint_id"],
                        "selector_value": option["selector_value"],
                    }
                    for option in blueprint_options
                ]
                selection_kind = "blueprint_variant"
            else:
                options = item["options"]
                selection_kind = "provider_selector"
            valid_values = {option.get("value") for option in item["options"]}
            is_valid = current in valid_values or any(
                _normalized(current) == _normalized(option.get("value"))
                or _normalized(current) == _normalized(option.get("label"))
                for option in item["options"]
            )
            # A shared provider value (such as DEMAND_GEN) identifies the
            # campaign family, not the concrete Blueprint.  Do not count it
            # as a completed choice when the card must ask for a variant.
            card_value = (
                None if selection_kind == "blueprint_variant" else current
            )
            fields.append({
                "path": item["path"], "provider_field": item["provider_field"],
                "tool": "", "label": item["label"], "control": "select",
                "required": True, "state": "missing" if card_value is None else "set" if is_valid else "invalid",
                "value": card_value, "options": options, "source": "blueprint",
                "selection_kind": selection_kind,
            })
        card = {
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
                {"id": "skip_template", "label": "不使用模板"},
            ],
        }
        return self._attach_creation_context(
            card,
            provider=provider,
            provider_values=provider_values,
            account_scope=account_scope,
            tenant_id=tenant_id,
            user_id=user_id,
            explicit_account_id=account_id,
        )

    def _account_selector_card(
        self,
        intent: ParsedIntent,
        provider: str,
        provider_values: Mapping[str, Any],
        blueprint: AdCreationBlueprint,
        selector_value: Any,
        *,
        account_scope: Any = None,
        tenant_id: str = "default",
        user_id: str = "anonymous",
        account_id: Optional[str] = None,
    ) -> dict[str, Any]:
        selector = blueprint.selector or {}
        field_path = str(selector.get("field") or selector.get("dimension") or "")
        provider_field = str(selector.get("dimension") or field_path)
        for field in blueprint.fields:
            if str(field.get("path")) != field_path:
                continue
            if "." in str(field.get("tool_ref") or ""):
                _tool_name, provider_field, _schema = _schema_for_ref(
                    self.tools, str(field["tool_ref"])
                )
            break
        option = {
            "value": selector_value,
            "label": blueprint.title,
            "blueprint_id": blueprint.blueprint_id,
            "selector_value": selector_value,
        }
        card = {
            "type": "ad_creation_selector",
            "version": "1.0",
            "id": f"{provider}.creation-context-selector",
            "title": f"先选择 {provider} 广告账户和创建方式",
            "provider": provider,
            "mode": "draft",
            "blueprint_id": blueprint.blueprint_id,
            "blueprint_version": blueprint.version,
            "selector": {
                "dimension": selector.get("dimension"),
                "value": selector_value,
            },
            "fields": [{
                "path": field_path,
                "provider_field": provider_field,
                "tool": "",
                "label": selector.get("label") or blueprint.title,
                "control": "select",
                "required": True,
                "state": "set",
                "value": selector_value,
                "options": [option],
                "source": "blueprint",
                "selection_kind": "blueprint",
            }],
            "missing_fields": [],
            "invalid_fields": [],
            "ready": False,
            "actions": [
                {"id": "continue_chat", "label": "继续用文字补充"},
                {"id": "skip_template", "label": "不使用模板"},
            ],
        }
        return self._attach_creation_context(
            card,
            provider=provider,
            provider_values=provider_values,
            account_scope=account_scope,
            tenant_id=tenant_id,
            user_id=user_id,
            explicit_account_id=account_id,
        )

    def _form_card(
        self, intent: ParsedIntent, blueprint: AdCreationBlueprint,
        provider_values: Mapping[str, Any], selector_value: Any,
    ) -> dict[str, Any]:
        blueprint = self.expand_blueprint(blueprint)
        values: dict[str, Any] = {}
        for field in blueprint.fields[:_MAX_FIELDS]:
            if _SENSITIVE_FIELD.search(str(field.get("path"))):
                continue
            value = self._field_value(intent, provider_values, field)
            if value is None:
                _tool_name, _schema_path, schema = _schema_for_ref(self.tools, field["tool_ref"])
                if schema.get("type") == "boolean":
                    value = False
            values[str(field["path"])] = value
        option_sources: dict[str, list[Any]] = {}
        for field in blueprint.fields[:_MAX_FIELDS]:
            _tool_name, _schema_path, schema = _schema_for_ref(self.tools, field["tool_ref"])
            schema_options = _options(field, schema)
            if schema_options:
                option_sources[str(field["path"])] = schema_options
            # Resolve one-value derived fields before evaluating visibility.
            # Otherwise a format-specific field such as Search headlines is
            # evaluated against a missing ``ad_type`` and is hidden even
            # though the Blueprint has already fixed that value.
            path = str(field["path"])
            if (
                values.get(path) is None
                and field.get("presentation") == "derived_readonly"
                and len(schema_options) == 1
            ):
                values[path] = schema_options[0]
        evaluation = self.cascade.evaluate(blueprint, values, option_sources=option_sources)
        # Some safe defaults depend on a parent selection (for example Meta's
        # optimization goal depends on the campaign objective). Resolve those
        # after the first cascade pass, then evaluate once more so readiness
        # and conditional fields use the same materialized draft.
        dependent_defaults_changed = False
        initial_states = {item["path"]: item for item in evaluation.get("fields", [])}
        for field in blueprint.fields[:_MAX_FIELDS]:
            path = str(field["path"])
            if values.get(path) is not None:
                continue
            _tool_name, _schema_path, schema = _schema_for_ref(self.tools, field["tool_ref"])
            candidate, _source, _reason = _safe_default(
                intent, provider_values, field, schema,
                options_override=list(initial_states.get(path, {}).get("options") or []),
            )
            if candidate is not None:
                values[path] = candidate
                dependent_defaults_changed = True
        if dependent_defaults_changed:
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
            _default_value, default_source, default_reason = _safe_default(
                intent, provider_values, field, schema,
                options_override=options,
            )
            input_mode = _input_mode(field, schema, default_source)
            item["input_mode"] = input_mode
            item["user_required"] = input_mode in _USER_INPUT_MODES
            item["advanced"] = bool(
                field.get("advanced", input_mode in {"auto_default", "auto_derived", "user_optional"})
            )
            item["auto_filled"] = bool(
                default_source and value is not None
                and self._provided_field_value(intent, provider_values, field) is None
            )
            if default_source:
                item["default_source"] = default_source
            if default_reason:
                item["default_reason"] = default_reason
            if field.get("visible_when") is not None:
                item["visible_when"] = _copy_json(field["visible_when"])
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
            json_shape = _json_shape(field, schema)
            if json_shape and item["control"] in {"json", "advanced_json"}:
                item["json_shape"] = json_shape
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
                option_aliases = field.get("option_aliases") or schema.get("option_aliases")
                if isinstance(option_aliases, Mapping):
                    item["option_aliases"] = {
                        str(option): _copy_json(option_aliases[str(option)])
                        for option in options
                        if str(option) in option_aliases
                    }
            if field.get("options_from"):
                item["options_from"] = list(field["options_from"])
            if state.get("options_state"):
                item["options_state"] = state["options_state"]
                item["missing_option_dependencies"] = list(
                    state.get("missing_option_dependencies") or []
                )
            if item["control"] == "object_editor":
                # An object editor may represent one object or a collection of
                # objects (for example a Meta carousel or TikTok media list).
                # In the latter case the item schema is the editor contract.
                object_schema = schema
                if (
                    schema.get("type") == "array"
                    and isinstance(schema.get("items"), Mapping)
                ):
                    object_schema = schema["items"]
                properties = object_schema.get("properties") or {}
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
                            "option_aliases": spec.get("option_aliases"),
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
                            # Nested editors use the same declarative contract
                            # as top-level fields.  Keep presentation and
                            # provider applicability here instead of forcing a
                            # frontend to fall back to an opaque JSON editor.
                            "presentation": spec.get("presentation"),
                            "value_shape": spec.get("value_shape"),
                            "accept": spec.get("accept"),
                            "ui_visible_when": spec.get("ui_visible_when"),
                            "default": spec.get("default"),
                            "minLength": spec.get("minLength"),
                            "maxLength": spec.get("maxLength"),
                            "minimum": spec.get("minimum"),
                            "maximum": spec.get("maximum"),
                            "constraints": _schema_constraints(spec),
                            "properties": _copy_json(spec.get("properties") or {})
                            if isinstance(spec.get("properties"), Mapping) else None,
                            "additional_properties": spec.get("additionalProperties"),
                            "required": name in (object_schema.get("required") or []),
                        }.items()
                        if value not in (None, "", {}, [])
                    }
                    for name, spec in properties.items()
                    if isinstance(spec, Mapping) and not _SENSITIVE_FIELD.search(str(name))
                }
                if schema.get("type") == "array":
                    item["object_shape"] = "array"
                    item["object_min_items"] = schema.get("minItems")
                    item["object_max_items"] = schema.get("maxItems")
            elif (
                schema.get("type") == "array"
                and isinstance(schema.get("items"), Mapping)
                and isinstance(schema["items"].get("properties"), Mapping)
            ):
                # Preserve nested controls even when the collection itself is
                # rendered by a specialized asset picker.
                item["item_properties"] = _copy_json(schema["items"]["properties"])
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
        defaulted_fields = [
            {
                "path": item["path"], "label": item["label"],
                "value": _copy_json(item["value"]),
                "source": item.get("default_source"),
                "reason": item.get("default_reason"),
            }
            for item in fields if item.get("auto_filled")
        ]
        advanced_fields = [item["path"] for item in fields if item.get("advanced")]
        user_input_fields = [
            item["path"] for item in fields
            if item.get("user_required") and item.get("visible", True)
        ]
        return {
            "type": "ad_creation_form", "version": "1.0",
            "id": f"{blueprint.blueprint_id}@{blueprint.version}",
            "title": blueprint.title, "provider": blueprint.provider,
            "blueprint_id": blueprint.blueprint_id,
            "blueprint_version": blueprint.version, "mode": "draft",
            "selector": {"dimension": (blueprint.selector or {}).get("dimension"), "value": selector_value},
            "fields": fields,
            "user_input_fields": user_input_fields,
            "advanced_fields": advanced_fields,
            "auto_filled_count": len(defaulted_fields),
            "defaulted_fields": defaulted_fields[:_MAX_FIELDS],
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

    def build(
        self,
        intent: ParsedIntent,
        tool_plan: Optional[Mapping[str, Any]] = None,
        *,
        account_scope: Any = None,
        tenant_id: str = "default",
        user_id: str = "anonymous",
        account_id: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        if not self.is_creation_intent(intent, tool_plan=tool_plan):
            return []
        cards: list[dict[str, Any]] = []
        for provider in list(getattr(intent, "namespaces", []) or [])[:_MAX_CARDS]:
            canonical = normalize_platform(provider)
            blueprint, values, selector_value = self._resolve(intent, canonical)
            if blueprint is None:
                selector_card = self._selector_card(
                    intent,
                    canonical,
                    values,
                    account_scope=account_scope,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    account_id=account_id,
                )
                if selector_card:
                    cards.append(selector_card)
                continue
            account_options = self._account_options(canonical, account_scope)
            selected_account = self._account_from_values(values, account_id)
            if not selected_account and account_options:
                cards.append(self._account_selector_card(
                    intent,
                    canonical,
                    values,
                    blueprint,
                    selector_value,
                    account_scope=account_scope,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    account_id=account_id,
                ))
                continue
            card = self._attach_creation_context(
                self._form_card(intent, blueprint, values, selector_value),
                provider=canonical,
                provider_values=values,
                account_scope=account_scope,
                tenant_id=tenant_id,
                user_id=user_id,
                explicit_account_id=account_id,
            )
            metadata = getattr(intent, "metadata", {}) or {}
            if metadata.get("creation_template_id"):
                card["template_id"] = str(metadata["creation_template_id"])
                card["template_source"] = str(
                    metadata.get("creation_template_source") or "user"
                )
            cards.append(card)
        return cards[:_MAX_CARDS]
