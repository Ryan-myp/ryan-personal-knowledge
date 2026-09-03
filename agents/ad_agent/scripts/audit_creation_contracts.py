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


def _field_source(spec: Mapping[str, Any], inherited: bool = False) -> str:
    if _lookup_name(spec):
        return "lookup"
    if isinstance(spec.get("manual_entry"), Mapping):
        return "manual_entry"
    if inherited:
        return "inherited"
    if spec.get("ui_hidden"):
        return "hidden"
    if str(spec.get("type") or "") in {"file", "file_reference"}:
        return "upload"
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
        own_source = bool(_field_source(raw_spec))
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


def audit_creation_contracts(runtime: AgentRuntime) -> dict[str, Any]:
    issues: list[str] = []
    lookup_contracts: list[dict[str, Any]] = []
    unresolved_fields: list[dict[str, str]] = []
    selector_groups: dict[tuple[str, str, tuple[Any, ...]], list[Any]] = {}
    creation_tools = [
        definition
        for definition in runtime.registry.list_all()
        if str(getattr(definition, "action", "")) == "create"
    ]

    for blueprint in runtime.creation_blueprints.list():
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
            lookup_name = _lookup_name(spec)
            if lookup_name:
                lookup = _tool_definition(runtime.registry, lookup_name)
                lookup_contracts.append({
                    "tool": definition.name,
                    "field": path,
                    "lookup_tool": lookup_name,
                    "read_only": bool(lookup and getattr(lookup, "effect_class", None) == ToolEffect.READ),
                })
                if lookup is None:
                    issues.append(f"{definition.name}.{path}: lookup Tool is not registered: {lookup_name}")
                elif getattr(lookup, "effect_class", None) != ToolEffect.READ:
                    issues.append(f"{definition.name}.{path}: lookup Tool must be read-only: {lookup_name}")
            if _needs_source(path, spec) and not inherited_source:
                unresolved_fields.append({"tool": definition.name, "field": path})

    for item in unresolved_fields:
        issues.append(
            f"{item['tool']}.{item['field']}: provider resource field needs lookup_tool or manual_entry"
        )

    blueprint_coverage = _audit_blueprint_coverage(runtime)
    return {
        "creation_tool_count": len(creation_tools),
        "blueprint_count": len(runtime.creation_blueprints.list()),
        "lookup_contract_count": len(lookup_contracts),
        "lookup_contracts": lookup_contracts,
        "selector_overlaps": selector_overlaps,
        "unresolved_fields": unresolved_fields,
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
