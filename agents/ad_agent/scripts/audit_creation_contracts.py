#!/usr/bin/env python3
"""Audit declarative ad-creation contracts without provider I/O.

This is the creation-form counterpart to ``audit_capabilities.py``.  It
checks the contract chain that is easy to break when a provider adds a field:

``Blueprint -> create Tool schema -> lookup Tool/manual source -> read-only``

The audit only imports built-in Capability metadata.  It never executes a
Tool, constructs a provider client, or makes a network request.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.ad_agent.capabilities.factory import (  # noqa: E402
    discover_capability_factory,
)
from agents.ad_agent.scripts.audit_capabilities import discover_platform_slugs  # noqa: E402
from agents.ad_agent.core.blueprint import (  # noqa: E402
    validate_blueprint_against_tools,
)
from agents.ad_agent.core.interfaces import ToolEffect  # noqa: E402
from agents.ad_agent.persistence.store import AdAgentStore  # noqa: E402
from agents.ad_agent.runtime.runtime import AgentRuntime  # noqa: E402


_RESOURCE_FIELD = re.compile(
    r"(?:^|_)(?:id|ids|hash)$|(?:_id|_ids|_hash)$", re.IGNORECASE
)
_RESOURCE_NAMES = {
    "app_id", "asset_id", "business_id", "creative_id", "event_source_group",
    "hotel_center_id", "image_hash", "merchant_id", "page_id", "post_id",
    "store_id", "topic_id", "travel_account_id", "user_interest_id", "video_id",
    # Resource containers and nested provider asset references.  These names
    # do not end in ``_id`` but still represent provider-owned objects rather
    # than arbitrary user text.
    "creative", "creatives", "image", "images", "image_asset",
    "images_asset", "logo_image", "logo_images", "logos", "media",
    "marketing_image_asset", "square_marketing_image_asset",
    "portrait_marketing_image_asset", "marketing_images",
    "square_marketing_images", "portrait_marketing_images",
    "tall_portrait_marketing_images", "classic_display_images",
    "companion_banners", "call_to_actions", "videos",
}
_PARENT_OR_CONTEXT_FIELDS = {
    "account_id", "advertiser_id", "customer_id", "manager_customer_id",
    "campaign_id", "ad_group_id", "adgroup_id", "adset_id", "ad_id",
    "asset_group_id", "budget_id", "criterion_id", "feed_id", "lead_id",
    "io_id", "line_item_id",
    "form_id", "experiment_id", "creative_portfolio_id", "product_group_id",
    "conversion_action_id", "bidding_strategy_id", "audience_id",
}
_UPLOAD_FIELDS = {
    "file_path", "file_paths", "file_url", "image_url", "video_url", "image_uri",
}
_SOURCE_KINDS = (
    "enum", "lookup", "manual_entry", "upload", "context", "inherited",
    "free_text", "structured", "unclassified",
)


def _tool_definition(registry: Any, name: str) -> Any:
    try:
        result = registry.get(name)
    except (KeyError, LookupError, ValueError):
        return None
    return result[0] if isinstance(result, tuple) else result


def _lookup_name(spec: Mapping[str, Any]) -> str:
    lookup = spec.get("lookup")
    value = spec.get("lookup_tool")
    if not value and isinstance(lookup, Mapping):
        value = lookup.get("tool")
    return str(value or "").strip()


def _has_static_options(spec: Mapping[str, Any]) -> bool:
    """Return whether a schema publishes a finite provider-owned option set."""
    if isinstance(spec.get("enum"), list):
        return True
    items = spec.get("items")
    if isinstance(items, Mapping) and isinstance(items.get("enum"), list):
        return True
    # ``known_values`` is used for provider vocabularies that intentionally
    # also accept a custom value (for example a custom conversion event).  It
    # is still a discoverable enum source; the report preserves allow_custom.
    return isinstance(spec.get("known_values"), list)


def _explicit_field_source(spec: Mapping[str, Any]) -> bool:
    """Whether a parent object should pass a source hint to nested fields."""
    lookup = _lookup_name(spec)
    return bool(
        lookup
        or _has_static_options(spec)
        or isinstance(spec.get("manual_entry"), Mapping)
        or str(spec.get("type") or "") in {"file", "file_reference"}
    )


def _field_source(
    spec: Mapping[str, Any],
    field_name: str = "",
    inherited: bool = False,
) -> str:
    """Classify how a creation field can obtain its value.

    This is deliberately an audit taxonomy, not Runtime routing.  It makes a
    provider contract legible to a form/LLM consumer while keeping ordinary
    user-entered names, dates and numbers distinct from provider-owned IDs.
    Explicit schema metadata always wins over the conservative name-based
    context fallback.
    """
    if _lookup_name(spec):
        return "lookup"
    if _has_static_options(spec):
        return "enum"
    if isinstance(spec.get("manual_entry"), Mapping):
        return "manual_entry"
    leaf = str(field_name or "").rsplit(".", 1)[-1].replace("[]", "")
    if leaf in _PARENT_OR_CONTEXT_FIELDS:
        return "context"
    if leaf in _UPLOAD_FIELDS or str(spec.get("type") or "") in {"file", "file_reference"}:
        return "upload"
    if inherited:
        return "inherited"
    if spec.get("ui_hidden"):
        return "context"
    field_type = spec.get("type")
    if isinstance(field_type, str) and field_type in {"string", "number", "integer", "boolean"}:
        return "free_text"
    if (isinstance(field_type, str) and field_type in {"object", "array"}) or isinstance(field_type, list):
        return "structured"
    return ""


def _iter_fields(
    properties: Mapping[str, Any],
    *,
    prefix: str = "",
    inherited_source: bool = False,
) -> Iterable[tuple[str, Mapping[str, Any], bool]]:
    for name, raw_spec in properties.items():
        if not isinstance(raw_spec, Mapping):
            continue
        path = f"{prefix}.{name}" if prefix else str(name)
        own_source = _explicit_field_source(raw_spec)
        yield path, raw_spec, inherited_source or own_source
        nested = raw_spec.get("properties")
        if isinstance(nested, Mapping):
            yield from _iter_fields(
                nested,
                prefix=path,
                inherited_source=inherited_source or own_source,
            )
        items = raw_spec.get("items")
        if isinstance(items, Mapping) and isinstance(items.get("properties"), Mapping):
            yield from _iter_fields(
                items["properties"],
                prefix=f"{path}[]",
                inherited_source=inherited_source or own_source,
            )


def _needs_source(path: str, spec: Mapping[str, Any]) -> bool:
    name = path.rsplit(".", 1)[-1].replace("[]", "")
    if name in _PARENT_OR_CONTEXT_FIELDS or name in _UPLOAD_FIELDS:
        return False
    return bool(_RESOURCE_FIELD.search(name) or name in _RESOURCE_NAMES)


def _source_details(spec: Mapping[str, Any]) -> dict[str, Any]:
    """Expose only safe, declarative facts useful for contract review."""
    details: dict[str, Any] = {}
    enum = spec.get("enum")
    if isinstance(enum, list):
        details["option_count"] = len(enum)
    items = spec.get("items")
    if isinstance(items, Mapping) and isinstance(items.get("enum"), list):
        details["option_count"] = len(items["enum"])
    if isinstance(spec.get("known_values"), list):
        details["known_value_count"] = len(spec["known_values"])
    if spec.get("allow_custom") is not None:
        details["allow_custom"] = bool(spec["allow_custom"])
    lookup_name = _lookup_name(spec)
    if lookup_name:
        details["lookup_tool"] = lookup_name
    if isinstance(spec.get("manual_entry"), Mapping):
        manual = spec["manual_entry"]
        details["manual_entry"] = {
            key: value for key, value in manual.items()
            if key in {"source", "instructions", "example", "format"}
        }
    if spec.get("minItems") is not None:
        details["min_items"] = spec["minItems"]
    if spec.get("maxItems") is not None:
        details["max_items"] = spec["maxItems"]
    return details


def _is_opaque_structured_field(spec: Mapping[str, Any]) -> bool:
    """Whether a structured field has no child contract for a guided form."""
    field_type = spec.get("type")
    if field_type == "object":
        return not isinstance(spec.get("properties"), Mapping)
    if field_type != "array":
        return False
    items = spec.get("items")
    if not isinstance(items, Mapping):
        return True
    item_type = items.get("type")
    if item_type == "object":
        return not isinstance(items.get("properties"), Mapping)
    if isinstance(item_type, list):
        # ``["string", "object"]`` is a deliberate provider shorthand for
        # text-or-asset references and is already renderable as a text/asset
        # picker.  Only a pure object union is opaque here.
        normalized_types = {str(value) for value in item_type}
        if normalized_types == {"object"}:
            return not isinstance(items.get("properties"), Mapping)
    return False


def _format_tokens(value: Any) -> set[str]:
    """Return comparable tokens for provider format identifiers.

    Format identifiers intentionally remain provider-owned.  This helper is
    only for reporting whether a catalog entry has a Blueprint candidate; it
    does not create a routing alias or make the Runtime infer a provider
    format.  For example, ``link_traffic`` and ``traffic`` can be shown as a
    related family while still remaining distinct contracts.
    """
    return {
        token
        for token in re.split(r"[^a-z0-9]+", str(value or "").casefold())
        if token
    }


def _blueprint_match_score(entry: Mapping[str, Any], blueprint: Any) -> int:
    """Score a non-authoritative catalog-to-Blueprint relationship.

    Exact and family matches are preferred.  Shared Tool references are a
    useful fallback for formats such as TikTok App/Lead variants, whose
    Blueprint selects the family through an objective rather than repeating
    the catalog's format id.  The score is surfaced as audit evidence only.
    """
    format_id = str(entry.get("format_id") or "")
    category = str(entry.get("category") or "")
    blueprint_format = str(getattr(blueprint, "ad_format", "") or "")
    if format_id.casefold() == blueprint_format.casefold():
        return 100
    if category and category.casefold() == blueprint_format.casefold():
        return 80
    entry_tokens = _format_tokens(format_id) | _format_tokens(category)
    blueprint_tokens = _format_tokens(blueprint_format)
    if entry_tokens & blueprint_tokens:
        return 60
    entry_tools = {str(item) for item in (entry.get("tool_names") or [])}
    blueprint_tools = {str(item) for item in (getattr(blueprint, "tools", ()) or ())}
    if entry_tools & blueprint_tools:
        return 20
    return 0


def _audit_blueprint_coverage(runtime: AgentRuntime) -> dict[str, Any]:
    """Report format-to-Blueprint coverage without changing execution rules.

    A catalog can legitimately be partial or declared-only, so missing
    Blueprint mappings are gaps rather than hard contract errors.  Keeping
    them explicit prevents the UI/planner from presenting a format as a
    guided creation flow merely because a broad Tool exists.
    """
    by_provider: dict[str, dict[str, Any]] = {}
    for provider in sorted(getattr(runtime, "ad_format_catalogs", {}) or {}):
        catalogs = runtime.list_ad_formats(platform=provider)
        blueprints = runtime.creation_blueprints.list(provider=provider)
        rows: list[dict[str, Any]] = []
        missing_guided: list[str] = []
        for entry in catalogs:
            candidates = sorted(
                (
                    (score, blueprint)
                    for blueprint in blueprints
                    if (score := _blueprint_match_score(entry, blueprint)) > 0
                ),
                key=lambda item: (-item[0], item[1].blueprint_id, item[1].version),
            )
            mapped = [
                {
                    "blueprint_id": blueprint.blueprint_id,
                    "version": blueprint.version,
                    "score": score,
                }
                for score, blueprint in candidates
            ]
            coverage = str(entry.get("coverage") or "")
            if coverage in {
                "supported_dry_run", "partial_dry_run"
            } and not mapped:
                missing_guided.append(str(entry.get("format_id") or ""))
            rows.append({
                "format_id": entry.get("format_id"),
                "coverage": coverage,
                "blueprints": mapped,
            })
        mapped_count = sum(1 for row in rows if row["blueprints"])
        by_provider[provider] = {
            "format_count": len(rows),
            "mapped_count": mapped_count,
            "unmapped_guided_formats": missing_guided,
            "formats": rows,
        }
    return by_provider


def _blueprint_required_field_gaps(
    runtime: AgentRuntime, blueprint: Any,
) -> list[dict[str, str]]:
    """Check that a Blueprint's effective form contains required Tool fields.

    ``CreationCardBuilder.expand_blueprint`` is the supported composition
    point: a concise provider Blueprint may inherit safe schema fields there.
    The audit checks the expanded result, so it catches a real missing field
    without forcing every provider to duplicate its Tool schema in JSON.
    """
    try:
        expanded = runtime.creation_card_builder.expand_blueprint(blueprint)
    except Exception as exc:
        return [{"tool": "<blueprint>", "field": f"expansion failed: {exc}"}]
    refs = {str(field.get("tool_ref")) for field in expanded.fields}
    gaps: list[dict[str, str]] = []
    for tool_name in blueprint.tools:
        definition = _tool_definition(runtime.registry, tool_name)
        if definition is None:
            continue
        schema = getattr(definition, "input_schema", None)
        properties = getattr(schema, "properties", {}) or {}
        required = set(getattr(schema, "required", []) or [])
        required.update(getattr(schema, "provider_required", []) or [])
        parent_field = str(getattr(definition, "parent_resource_id_field", "") or "")
        resource_id_field = str(getattr(definition, "resource_id_field", "") or "")
        for field_name in sorted(required):
            spec = properties.get(field_name)
            if not isinstance(spec, Mapping):
                continue
            if (
                field_name in _PARENT_OR_CONTEXT_FIELDS
                or field_name in {parent_field, resource_id_field}
                or spec.get("ui_hidden") is True
            ):
                continue
            tool_ref = f"{tool_name}.{field_name}"
            if tool_ref not in refs:
                gaps.append({"tool": tool_name, "field": field_name})
    return gaps


def audit_creation_contracts(runtime: AgentRuntime) -> dict[str, Any]:
    issues: list[str] = []
    lookup_contracts: list[dict[str, Any]] = []
    unresolved_fields: list[dict[str, str]] = []
    source_counts: dict[str, Counter[str]] = defaultdict(Counter)
    field_sources: list[dict[str, Any]] = []
    unclassified_fields: list[dict[str, str]] = []
    structured_guidance_gaps: list[dict[str, Any]] = []
    blueprint_required_gaps: list[dict[str, str]] = []
    blueprint_field_usage: dict[str, list[str]] = defaultdict(list)
    selector_groups: dict[tuple[str, str, tuple[Any, ...]], list[Any]] = {}
    creation_tools = [
        definition
        for definition in runtime.registry.list_all()
        if str(getattr(definition, "action", "")) == "create"
    ]

    for blueprint in runtime.creation_blueprints.list():
        blueprint_key = f"{blueprint.blueprint_id}@{blueprint.version}"
        try:
            expanded = runtime.creation_card_builder.expand_blueprint(blueprint)
            for field in expanded.fields:
                tool_ref = str(field.get("tool_ref") or "")
                if tool_ref and blueprint_key not in blueprint_field_usage[tool_ref]:
                    blueprint_field_usage[tool_ref].append(blueprint_key)
        except Exception:
            # The required-field helper below records expansion failures as a
            # contract issue; do not duplicate that error in this index.
            pass
        selector = blueprint.selector or {}
        if selector:
            selector_groups.setdefault(
                (
                    blueprint.provider,
                    str(selector.get("dimension") or ""),
                    tuple(selector.get("values") or []),
                ),
                [],
            ).append(blueprint)
        try:
            validate_blueprint_against_tools(blueprint, runtime.registry)
        except Exception as exc:
            issues.append(f"{blueprint.blueprint_id}@{blueprint.version}: {exc}")
        for gap in _blueprint_required_field_gaps(runtime, blueprint):
            item = {
                "blueprint": f"{blueprint.blueprint_id}@{blueprint.version}",
                **gap,
            }
            blueprint_required_gaps.append(item)
            issues.append(
                f"{item['blueprint']}: required Tool field is absent from effective Blueprint: "
                f"{item['tool']}.{item['field']}"
            )

    selector_overlaps: list[dict[str, Any]] = []
    for (provider, dimension, values), blueprints in selector_groups.items():
        if len(blueprints) < 2:
            continue
        selector_overlaps.append({
            "provider": provider,
            "dimension": dimension,
            "values": list(values),
            "blueprints": [blueprint.blueprint_id for blueprint in blueprints],
        })
        for blueprint in blueprints:
            if not blueprint.match_terms:
                issues.append(
                    f"{blueprint.blueprint_id}@{blueprint.version}: overlapping selector needs match_terms"
                )

    for definition in creation_tools:
        properties = getattr(getattr(definition, "input_schema", None), "properties", {})
        for path, spec, inherited_source in _iter_fields(properties or {}):
            source = _field_source(spec, path, inherited_source)
            provider = str(getattr(definition, "platform", "") or "")
            source_counts[provider][source or "unclassified"] += 1
            field_item = {
                "provider": provider,
                "tool": definition.name,
                "field": path,
                "source": source or "unclassified",
                "type": spec.get("type"),
                "required": path.rsplit(".", 1)[-1].replace("[]", "") in set(
                    getattr(getattr(definition, "input_schema", None), "required", []) or []
                ) | set(
                    getattr(getattr(definition, "input_schema", None), "provider_required", []) or []
                ),
            }
            details = _source_details(spec)
            if details:
                field_item["details"] = details
            field_sources.append(field_item)
            if (
                _is_opaque_structured_field(spec)
                and not isinstance(spec.get("manual_entry"), Mapping)
                and spec.get("ui_hidden") is not True
            ):
                structured_guidance_gaps.append({
                    "provider": provider,
                    "tool": definition.name,
                    "field": path,
                    "required": field_item["required"],
                    "blueprints": list(blueprint_field_usage.get(
                        f"{definition.name}.{path}", []
                    )),
                    "additional_properties": spec.get("additionalProperties"),
                    "description_present": bool(str(spec.get("description") or "").strip()),
                })
            if not source:
                unclassified_fields.append({
                    "tool": definition.name,
                    "field": path,
                })
            if _needs_source(path, spec) and source not in {
                "lookup", "manual_entry", "upload", "context", "inherited",
            }:
                unresolved_fields.append({
                    "tool": definition.name,
                    "field": path,
                    "source": source or "unclassified",
                })
            lookup_name = _lookup_name(spec)
            if lookup_name:
                lookup = _tool_definition(runtime.registry, lookup_name)
                lookup_contracts.append({
                    "tool": definition.name,
                    "field": path,
                    "lookup_tool": lookup_name,
                    "read_only": bool(lookup and getattr(lookup, "effect_class", None) == ToolEffect.READ),
                    "same_provider": bool(
                        lookup and str(getattr(lookup, "platform", "")).casefold()
                        == provider.casefold()
                    ),
                })
                if lookup is None:
                    issues.append(f"{definition.name}.{path}: lookup Tool is not registered: {lookup_name}")
                elif getattr(lookup, "effect_class", None) != ToolEffect.READ:
                    issues.append(f"{definition.name}.{path}: lookup Tool must be read-only: {lookup_name}")
                elif str(getattr(lookup, "platform", "")).casefold() != provider.casefold():
                    issues.append(
                        f"{definition.name}.{path}: lookup Tool must belong to provider "
                        f"{provider}: {lookup_name}"
                    )

    for item in unresolved_fields:
        issues.append(
            f"{item['tool']}.{item['field']}: provider resource field needs lookup_tool or manual_entry"
        )

    blueprint_coverage = _audit_blueprint_coverage(runtime)
    source_count_dict = {
        provider: {
            source: counts.get(source, 0)
            for source in _SOURCE_KINDS
            if counts.get(source, 0)
        }
        for provider, counts in sorted(source_counts.items())
    }
    return {
        "creation_tool_count": len(creation_tools),
        "blueprint_count": len(runtime.creation_blueprints.list()),
        "lookup_contract_count": len(lookup_contracts),
        "lookup_contracts": lookup_contracts,
        "field_source_counts": source_count_dict,
        "field_source_total": sum(sum(counts.values()) for counts in source_counts.values()),
        "field_sources": field_sources,
        "unclassified_fields": unclassified_fields,
        "structured_guidance_gaps": structured_guidance_gaps,
        "selector_overlaps": selector_overlaps,
        "unresolved_fields": unresolved_fields,
        "blueprint_required_gaps": blueprint_required_gaps,
        "blueprint_coverage": blueprint_coverage,
        "issues": issues,
    }


def build_runtime() -> AgentRuntime:
    runtime = AgentRuntime(
        persistence_store=AdAgentStore(":memory:"),
        offline_mode=True,
        enforce_account_scope=False,
    )
    for slug in discover_platform_slugs():
        factory = discover_capability_factory(slug)
        if callable(factory):
            runtime.register_capability(factory())
    return runtime


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="print the full JSON report")
    parser.add_argument(
        "--strict-guided",
        action="store_true",
        help="fail when a supported/partial ad format has no Blueprint candidate",
    )
    args = parser.parse_args(argv)
    report = audit_creation_contracts(build_runtime())
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(
            f"创建契约审计：{report['creation_tool_count']} create tools, "
            f"{report['blueprint_count']} blueprints, "
            f"{report['lookup_contract_count']} lookup contracts"
        )
        for provider, coverage in report["blueprint_coverage"].items():
            missing = coverage["unmapped_guided_formats"]
            suffix = f"；待补 Blueprint: {', '.join(missing)}" if missing else ""
            print(
                f"- {provider}: {coverage['mapped_count']}/{coverage['format_count']} "
                f"formats mapped{suffix}"
            )
        print("字段来源分布：")
        for provider, counts in report["field_source_counts"].items():
            summary = ", ".join(f"{source}={count}" for source, count in counts.items())
            print(f"- {provider}: {summary}")
        if report["unclassified_fields"]:
            print(
                f"未分类字段：{len(report['unclassified_fields'])}；"
                "请补充 enum/lookup/manual_entry 或明确字段类型"
            )
        if report["structured_guidance_gaps"]:
            print(
                "结构化引导缺口："
                f"{len(report['structured_guidance_gaps'])} 个 object/对象数组缺少子字段 Schema "
                "或人工录入说明"
            )
        if report["issues"]:
            print("发现问题：")
            for issue in report["issues"]:
                print(f"- {issue}")
    guided_gaps = [
        f"{provider}:{format_id}"
        for provider, coverage in report["blueprint_coverage"].items()
        for format_id in coverage["unmapped_guided_formats"]
    ]
    if args.strict_guided and guided_gaps:
        print("缺少引导 Blueprint：" + ", ".join(guided_gaps))
        return 1
    return 1 if report["issues"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
