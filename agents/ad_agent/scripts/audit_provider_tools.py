#!/usr/bin/env python3.13
"""Audit metadata-driven ad-agent Tool Sources without provider I/O.

The audit discovers packages by the same convention as Runtime:
``tools/providers/<platform>/provider.py`` plus a ``create_*_tool_source``
factory. It is deliberately a report/release-gate tool, not a second
registry. Adding a provider therefore changes the audit output automatically
and does not require editing a central channel list.
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.ad_agent.tools.providers.source_factory import discover_tool_source_factory  # noqa: E402
from agents.ad_agent.tools.providers.api_surface import (  # noqa: E402
    IMPLEMENTED,
    NOT_APPLICABLE,
    build_inventory_report,
    select_readiness_surface,
    validate_inventory,
    validate_readiness_actions,
    validate_readiness_metadata,
    validate_surface,
)
from agents.ad_agent.core.interfaces import ReplayPolicy, ToolEffect  # noqa: E402
from agents.ad_agent.domain.ad.contracts import AdFormatCoverage  # noqa: E402
from agents.ad_agent.domain.ad.provider_evidence import load_provider_evidence  # noqa: E402
from agents.ad_agent.runtime.runtime import AdvertisingComposition  # noqa: E402
from agents.ad_agent.skill_management import (  # noqa: E402
    SkillPackageError,
    _validate_no_credential_assignments,
)


def discover_platform_slugs() -> list[str]:
    """Return installed tool_source package slugs, excluding Python caches."""
    providers_root = (
        Path(__file__).resolve().parents[1] / "tools" / "providers"
    )
    return sorted(
        path.name
        for path in providers_root.iterdir()
        if path.is_dir()
        and not path.name.startswith("_")
        and (path / "provider.py").is_file()
    )


def _schema_properties(definition: Any) -> dict[str, Any]:
    schema = getattr(definition, "input_schema", None)
    return getattr(schema, "properties", {}) or {}


def _covered_tool_names(coverage: dict[str, Any]) -> set[str]:
    """Return the executable Tool names represented by method coverage."""
    return {
        str(tool_name)
        for tool_names in (coverage or {}).values()
        for tool_name in (
            tool_names
            if isinstance(tool_names, (list, tuple, set))
            else [tool_names]
        )
        if str(tool_name).strip()
    }


def _evidence_actions_for_surface(action: str) -> set[str]:
    """Expand a surface write label to the explicit evidence action labels."""
    normalized = str(action or "").strip().lower()
    if normalized == "crud" or normalized == "mutate":
        return {"create", "update"}
    if normalized == "live_create" or normalized.startswith("create_"):
        return {"create"}
    if normalized.startswith("update_"):
        return {"update"}
    return {normalized}


def _link_operation_evidence(
    operation: dict[str, Any],
    evidence_operations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Link only exact registered Tool names and matching write actions."""
    category = operation.get("readiness_category")
    if category == "query":
        accepted_actions = {str(operation.get("action") or "").strip().lower()}
        evidence_category = "query"
    elif category == "managed_write":
        accepted_actions = _evidence_actions_for_surface(
            str(operation.get("action") or "")
        )
        evidence_category = "managed_write"
    else:
        return []
    registered_tools = set(operation.get("tools") or [])
    return [
        evidence
        for evidence in evidence_operations
        if evidence.get("readiness_category") == evidence_category
        and evidence.get("tool") in registered_tools
        and evidence.get("action") in accepted_actions
        and (
            category != "query"
            or evidence.get("resource") == operation.get("resource")
        )
    ]


def _evidence_for_readiness_category(
    readiness_category: str,
    *,
    write_evidence: list[dict[str, Any]],
    query_evidence: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if readiness_category == "query":
        return query_evidence
    if readiness_category == "managed_write":
        return write_evidence
    return []


def _audit_skill_context(report: dict[str, Any]) -> None:
    """Reject credential-shaped assignments in built-in Skill context.

    Skills are supplied to the LLM as context.  This check keeps the same
    assignment-level redline used for managed Skill uploads applied to the
    repository-owned packages as well; prose may explain that Runtime owns
    credentials, but a Skill must not contain a config snippet for them.
    """
    skills_root = Path(__file__).resolve().parents[1] / "skills"
    skill_issues: list[str] = []
    for skill_file in sorted(skills_root.rglob("SKILL.md")):
        try:
            skill_dir = skill_file.parent
            files = {
                path.relative_to(skill_dir).as_posix(): path.read_bytes()
                for path in sorted(skill_dir.rglob("*"))
                if path.is_file() and not path.is_symlink()
            }
            _validate_no_credential_assignments(files)
        except (OSError, SkillPackageError) as exc:
            skill_issues.append(f"{skill_file.relative_to(skills_root)}: {exc}")
    report["skill_context_issues"] = skill_issues
    report["issues"].extend(f"skill context: {issue}" for issue in skill_issues)


def audit_provider_tools(evidence_path: str | Path | None = None) -> dict[str, Any]:
    """Build a JSON-safe tool_source report without constructing API clients."""
    report: dict[str, Any] = {
        "platforms": {},
        "readiness_scope": {},
        "provider_evidence_errors": [],
        "issues": [],
    }
    _audit_skill_context(report)
    resolved_evidence_path = Path(evidence_path) if evidence_path else (
        Path(__file__).resolve().parents[1] / "contracts" / "provider_e2e_evidence.json"
    )
    if resolved_evidence_path.is_file():
        evidence = load_provider_evidence(resolved_evidence_path)
        report["provider_evidence"] = {
            **evidence,
            "path": str(resolved_evidence_path),
        }
        report["provider_evidence_errors"].extend(
            f"provider evidence: {error}"
            for error in evidence.get("errors", [])
        )
    else:
        report["provider_evidence"] = {
            "format_version": 1,
            "valid": False,
            "errors": ["受控 Provider E2E 证据文件不存在"],
            "run_count": 0,
            "providers": {},
            "path": str(resolved_evidence_path),
        }
        report["provider_evidence_errors"].append(
            "provider evidence: 受控 Provider E2E 证据文件不存在"
        )
    runtime = AdvertisingComposition(offline_mode=True, enforce_account_scope=False)

    for slug in discover_platform_slugs():
        try:
            factory = discover_tool_source_factory(slug)
            if not callable(factory):
                report["issues"].append(f"{slug}: tool_source factory not found")
                continue
            tool_source = factory()
            runtime.register_tool_source(tool_source)
            client_class = getattr(tool_source, "provider_client_class", None)
            provider_contract = getattr(tool_source, "get_provider_version_contract", None)
            if callable(provider_contract):
                version_contract = provider_contract()
                report.setdefault("provider_version_contracts", {})[str(
                    getattr(tool_source, "platform_name", slug)
                )] = version_contract
                for issue in version_contract.get("issues", []):
                    report["issues"].append(f"{slug}: Provider API version contract: {issue}")
            coverage = getattr(tool_source, "provider_method_coverage", {}) or {}
            exclusions = set(getattr(tool_source, "provider_method_exclusions", set()) or set())
            surface_module_name = f"{type(tool_source).__module__.rsplit('.', 1)[0]}.api_surface"
            try:
                surface_module = importlib.import_module(surface_module_name)
                surface = list(getattr(surface_module, "API_SURFACE", []) or [])
                inventory = list(getattr(surface_module, "OFFICIAL_INVENTORY", []) or [])
                provider_metadata = dict(
                    getattr(surface_module, "PROVIDER_METADATA", {}) or {}
                )
            except (ImportError, AttributeError) as exc:
                surface = []
                inventory = []
                provider_metadata = {}
                report["issues"].append(f"{slug}: provider API surface unavailable: {exc}")
            surface_errors = validate_surface(surface)
            report["issues"].extend(f"{slug}: {error}" for error in surface_errors)
            inventory_errors = validate_inventory(inventory, provider_metadata)
            report["issues"].extend(f"{slug}: {error}" for error in inventory_errors)
            readiness_metadata_errors = validate_readiness_metadata(provider_metadata)
            report["issues"].extend(
                f"{slug}: {error}" for error in readiness_metadata_errors
            )
            readiness_action_errors = validate_readiness_actions(
                surface,
                provider_metadata,
            )
            report["issues"].extend(
                f"{slug}: {error}" for error in readiness_action_errors
            )
            if not inventory:
                report["issues"].append(
                    f"{slug}: OFFICIAL_INVENTORY is required for a provider tool_source"
                )
            for metadata_field in (
                "provider", "api_version", "source_url", "inventory_scope", "completeness"
            ):
                if not str(provider_metadata.get(metadata_field) or "").strip():
                    report["issues"].append(
                        f"{slug}: provider metadata field {metadata_field!r} is required"
                    )
            platform_key = str(getattr(tool_source, "platform_name", slug))
            registered_names = {
                definition.name for definition in runtime.registry.list_all()
                if str(definition.namespace) == platform_key
            }
            covered_tool_names = _covered_tool_names(coverage)
            surface_gaps: list[str] = []
            planned_entries: list[dict[str, Any]] = []
            not_applicable_entries: list[dict[str, Any]] = []
            implemented_surface = 0
            implemented_surface_methods: set[str] = set()
            for entry in surface:
                if not isinstance(entry, dict):
                    continue
                if entry.get("status") != IMPLEMENTED:
                    if entry.get("status") == "planned":
                        planned_entries.append(entry)
                    elif entry.get("status") == NOT_APPLICABLE:
                        not_applicable_entries.append(entry)
                    continue
                implemented_surface += 1
                method_name = str(entry.get("method") or "")
                if method_name:
                    implemented_surface_methods.add(method_name)
                if client_class is not None and not callable(getattr(client_class, method_name, None)):
                    surface_gaps.append(
                        f"{entry.get('resource')}:{entry.get('action')} method {method_name} is not on Client"
                    )
                mapped_tools = coverage.get(method_name, [])
                if isinstance(mapped_tools, str):
                    mapped_tools = [mapped_tools]
                missing_tools = sorted(set(mapped_tools or []) - registered_names)
                if not mapped_tools:
                    surface_gaps.append(
                        f"{entry.get('resource')}:{entry.get('action')} method {method_name} has no coverage mapping"
                    )
                elif missing_tools:
                    surface_gaps.append(
                        f"{entry.get('resource')}:{entry.get('action')} missing Tools: {', '.join(missing_tools)}"
                    )
            unmapped_tools = sorted(registered_names - covered_tool_names)
            if unmapped_tools:
                surface_gaps.append(
                    "registered Tools missing provider method coverage: "
                    + ", ".join(unmapped_tools)
                )
            coverage_without_surface = sorted(
                set(str(method) for method in coverage if str(method).strip())
                - implemented_surface_methods
            )
            if coverage_without_surface:
                surface_gaps.append(
                    "provider methods missing API Surface entries: "
                    + ", ".join(coverage_without_surface)
                )
            report.setdefault("surface_gaps", {})[platform_key] = surface_gaps
            report.setdefault("surface_planned", {})[platform_key] = planned_entries
            report.setdefault("surface_not_applicable", {})[
                platform_key
            ] = not_applicable_entries
            scoped_entries = select_readiness_surface(surface, provider_metadata)
            scoped_operations: list[dict[str, Any]] = []
            provider_evidence = report.get("provider_evidence", {})
            provider_evidence_details = (
                provider_evidence.get("providers", {}).get(platform_key, {})
                if isinstance(provider_evidence, dict)
                else {}
            )
            operation_evidence = provider_evidence_details.get(
                "operation_evidence", []
            )
            if not isinstance(operation_evidence, list):
                operation_evidence = []
            query_evidence = provider_evidence_details.get("query_evidence", [])
            if not isinstance(query_evidence, list):
                query_evidence = []
            for entry in scoped_entries:
                method_name = str(entry.get("method") or "")
                mapped_tools = coverage.get(method_name, [])
                if isinstance(mapped_tools, str):
                    mapped_tools = [mapped_tools]
                mapped_tools = [str(name) for name in (mapped_tools or [])]
                method_available = bool(
                    client_class is not None
                    and method_name
                    and callable(getattr(client_class, method_name, None))
                )
                contract_covered = bool(
                    entry.get("status") == IMPLEMENTED
                    and method_available
                    and mapped_tools
                    and set(mapped_tools).issubset(registered_names)
                )
                operation = {
                    "resource": str(entry.get("resource") or ""),
                    "action": str(entry.get("action") or ""),
                    "method": method_name,
                    "status": str(entry.get("status") or ""),
                    "readiness_category": str(entry["readiness_category"]),
                    "evidence_level": str(entry.get("evidence_level") or "unknown"),
                    "execution_status": str(
                        entry.get("execution_status") or "unknown"
                    ),
                    "contract_covered": contract_covered,
                    "tools": mapped_tools,
                }
                linked_evidence = _link_operation_evidence(
                    operation,
                    _evidence_for_readiness_category(
                        str(entry["readiness_category"]),
                        write_evidence=operation_evidence,
                        query_evidence=query_evidence,
                    ),
                )
                if any(
                    item.get("evidence_level") == "provider_e2e"
                    for item in linked_evidence
                ):
                    operation["evidence_level"] = "provider_e2e"
                if any(
                    item.get("execution_status") == "live_verified"
                    for item in linked_evidence
                ):
                    operation["execution_status"] = "live_verified"
                operation["evidence_records"] = [
                    {
                        "resource": item.get("resource"),
                        "action": item.get("action"),
                        "tool": item.get("tool"),
                        "campaign_types": list(item.get("campaign_types") or []),
                        "outcome": item.get("outcome"),
                        "readback": item.get("readback"),
                        "evidence_level": item.get("evidence_level"),
                        "execution_status": item.get("execution_status"),
                    }
                    for item in linked_evidence
                ]
                scoped_operations.append(operation)
            query_operations = [
                item for item in scoped_operations
                if item["readiness_category"] == "query"
            ]
            managed_write_operations = [
                item for item in scoped_operations
                if item["readiness_category"] == "managed_write"
            ]
            scoped_total = len(scoped_operations)
            scoped_covered = sum(
                int(item["contract_covered"]) for item in scoped_operations
            )
            readiness_scope_report = {
                "included": provider_metadata.get("readiness_enabled") is True,
                "exclusion_reason": str(
                    provider_metadata.get("readiness_exclusion_reason") or ""
                ),
                "scope": "all_queries_and_campaign_hierarchy_create_update",
                "total": scoped_total,
                "covered": scoped_covered,
                "gaps": scoped_total - scoped_covered,
                "coverage_ratio": (
                    round(scoped_covered / scoped_total, 4)
                    if scoped_total
                    else (1.0 if provider_metadata.get("readiness_enabled") is False else 0.0)
                ),
                "query_total": len(query_operations),
                "query_covered": sum(
                    int(item["contract_covered"]) for item in query_operations
                ),
                "managed_write_total": len(managed_write_operations),
                "managed_write_covered": sum(
                    int(item["contract_covered"])
                    for item in managed_write_operations
                ),
                "managed_write_provider_e2e": sum(
                    int(item["evidence_level"] == "provider_e2e")
                    for item in managed_write_operations
                ),
                "managed_write_live_verified": sum(
                    int(item["execution_status"] == "live_verified")
                    for item in managed_write_operations
                ),
                "query_provider_e2e": sum(
                    int(item["evidence_level"] == "provider_e2e")
                    for item in query_operations
                ),
                "operations": scoped_operations,
            }
            report.setdefault("readiness_scope", {})[platform_key] = readiness_scope_report
            inventory_report = build_inventory_report(
                surface, inventory, provider_metadata
            )
            inventory_claim_gaps = [
                entry
                for entry in inventory_report.get("gaps_entries", [])
                if entry.get("status") == IMPLEMENTED
            ]
            for entry in inventory_claim_gaps:
                report["issues"].append(
                    f"{slug}: official inventory claims implemented but has no Surface coverage: "
                    f"{entry.get('resource')}:{entry.get('action')}"
                )
            report.setdefault("official_inventory", {})[platform_key] = inventory_report
            report.setdefault("surface_summary", {})[platform_key] = {
                "implemented": implemented_surface,
                "planned": len(planned_entries),
                "total": len(surface),
            }
            report.setdefault("provider_method_coverage", {})[platform_key] = {
                str(method): {
                    "tools": list(
                        coverage[method]
                        if isinstance(coverage[method], (list, tuple, set))
                        else [coverage[method]]
                    ),
                    "surface_entries": [
                        {
                            "resource": entry.get("resource"),
                            "action": entry.get("action"),
                            "status": entry.get("status"),
                        }
                        for entry in surface
                        if isinstance(entry, dict)
                        and entry.get("method") == method
                    ],
                }
                for method in sorted(coverage)
            }
            report["issues"].extend(f"{slug}: API surface gap: {gap}" for gap in surface_gaps)
            if client_class is not None:
                public_methods = {
                    name for name, member in vars(client_class).items()
                    if callable(member) and not name.startswith("_") and name not in exclusions
                }
                uncovered = sorted(public_methods - set(coverage))
                if uncovered:
                    report["issues"].append(
                        f"{slug}: provider methods without Tool coverage: {', '.join(uncovered)}"
                    )
                missing_tools = sorted(
                    tool_name
                    for tool_names in coverage.values()
                    for tool_name in (tool_names if isinstance(tool_names, (list, tuple, set)) else [tool_names])
                    if tool_name not in {definition.name for definition in runtime.registry.list_all()}
                )
                if missing_tools:
                    report["issues"].append(
                        f"{slug}: coverage references unregistered Tools: {', '.join(dict.fromkeys(missing_tools))}"
                    )
        except Exception as exc:  # pragma: no cover - surfaced by release gate
            report["issues"].append(f"{slug}: failed to load provider-tools: {exc}")
    all_names: list[str] = []
    definitions_by_platform: dict[str, list[Any]] = {}
    for definition in runtime.registry.list_all():
        definitions_by_platform.setdefault(str(definition.namespace), []).append(definition)

    for platform, definitions in sorted(definitions_by_platform.items()):
        actions: Counter[str] = Counter()
        creation_chain: list[dict[str, Any]] = []
        live_read_tools: list[str] = []
        live_write_tools: list[str] = []
        platform_issues: list[str] = []

        for definition in definitions:
            name = str(definition.name)
            all_names.append(name)
            action = str(getattr(definition, "action", ""))
            resource = str(getattr(definition, "resource_type", ""))
            actions[f"{action}:{resource}"] += 1
            intent_types = [
                str(intent).strip()
                for intent in (getattr(definition, "intent_types", []) or [])
                if str(intent).strip()
            ]
            properties = _schema_properties(definition)
            parent_field = getattr(definition, "parent_resource_id_field", None)

            if not intent_types:
                platform_issues.append(
                    f"{name}: intent_types is empty; Tool cannot be discovered by Router"
                )
            if not definition.required_permissions:
                platform_issues.append(f"{name}: required_permissions is empty")
            if definition.is_write_tool and definition.replay_policy != ReplayPolicy.UNSAFE:
                platform_issues.append(f"{name}: write tool is replay-safe")
            if definition.effect_class == ToolEffect.READ and "ads.read" not in definition.required_permissions:
                platform_issues.append(f"{name}: read tool lacks ads.read")
            if definition.is_write_tool and "ads.plan" not in definition.required_permissions:
                platform_issues.append(f"{name}: write tool lacks ads.plan")
            if parent_field and parent_field not in properties:
                platform_issues.append(
                    f"{name}: parent_resource_id_field '{parent_field}' is not in Schema"
                )
            if action == "create" and getattr(definition, "parent_resource_type", None) and not parent_field:
                platform_issues.append(f"{name}: parent resource has no parent ID field")
            if action == "update" and "updates" not in properties:
                platform_issues.append(f"{name}: update tool has no updates object")

            if definition.live_support and definition.is_read_tool:
                live_read_tools.append(name)
            if definition.live_support and definition.is_write_tool:
                live_write_tools.append(name)
                # A live write must have an explicit, unambiguous recovery
                # read. The resolver validates platform/resource/parent
                # compatibility and rejects ambiguous candidates; this keeps
                # a future live enablement from silently weakening recovery.
                if not getattr(definition, "readback_tool", None):
                    platform_issues.append(
                        f"{name}: live write must declare readback_tool explicitly"
                    )
                elif getattr(runtime, "_resolve_readback_definition", lambda _n: None)(name) is None:
                    platform_issues.append(
                        f"{name}: declared readback_tool is missing or incompatible"
                    )
            if action == "create":
                schema = getattr(definition, "input_schema", None)
                creation_chain.append({
                    "tool": name,
                    "resource_type": resource,
                    "parent_resource_type": getattr(definition, "parent_resource_type", None),
                    "resource_id_field": getattr(definition, "resource_id_field", None),
                    "parent_resource_id_field": parent_field,
                    "intent_types": intent_types,
                    "required": list(getattr(schema, "required", []) or []),
                    "requires": list(getattr(schema, "requires", []) or []),
                    "conditional_rules": len(getattr(schema, "conditional_rules", []) or []),
                    "live_support": bool(definition.live_support),
                })

        ad_formats = [dict(item) for item in runtime.ad_format_catalogs.get(platform, [])]
        format_issues: list[str] = []
        definition_names = {definition.name for definition in definitions}
        for entry in ad_formats:
            missing = sorted(set(entry.get("tool_names", [])) - definition_names)
            if missing:
                format_issues.append(
                    f"{entry.get('format_id')}: unknown Tools: {', '.join(missing)}"
                )
            if (
                entry.get("coverage") == AdFormatCoverage.SUPPORTED_DRY_RUN.value
                and not str(entry.get("payload_adapter") or "").strip()
            ):
                format_issues.append(
                    f"{entry.get('format_id')}: supported_dry_run has no payload_adapter"
                )
            if entry.get("live_support"):
                format_issues.append(
                    f"{entry.get('format_id')}: format live_support must be false"
                )
        platform_issues.extend(format_issues)
        report["platforms"][platform] = {
            "tool_count": len(definitions),
            "actions": dict(sorted(actions.items())),
            "creation_chain": creation_chain,
            "ad_formats": ad_formats,
            "ad_format_coverage": dict(sorted(Counter(
                str(entry.get("coverage")) for entry in ad_formats
            ).items())),
            "live_read_tools": sorted(live_read_tools),
            "live_write_tools": sorted(live_write_tools),
            "api_surface": report.get("surface_summary", {}).get(platform, {}),
            "api_surface_gaps": report.get("surface_gaps", {}).get(platform, []),
            "api_surface_planned": report.get("surface_planned", {}).get(platform, []),
            "api_surface_not_applicable": report.get(
                "surface_not_applicable", {}
            ).get(platform, []),
            "official_inventory": report.get("official_inventory", {}).get(platform, {}),
            "readiness_scope": report.get("readiness_scope", {}).get(platform, {}),
            "provider_method_coverage": report.get(
                "provider_method_coverage", {}
            ).get(platform, {}),
            "issues": platform_issues,
        }
        report["issues"].extend(f"{platform}: {issue}" for issue in platform_issues)

    duplicate_names = sorted(name for name, count in Counter(all_names).items() if count > 1)
    report["duplicate_tool_names"] = duplicate_names
    report["tool_count"] = len(all_names)
    report["issues"].extend(f"duplicate tool name: {name}" for name in duplicate_names)
    return report


def _print_text(report: dict[str, Any]) -> None:
    print(f"tool_sources: {len(report['platforms'])}, tools: {report['tool_count']}")
    for platform, details in report["platforms"].items():
        print(f"\n[{platform}] {details['tool_count']} tools")
        print("  matrix: " + ", ".join(
            f"{key}={value}" for key, value in details["actions"].items()
        ))
        for item in details["creation_chain"]:
            parent = item["parent_resource_type"] or "root"
            parent_field = item["parent_resource_id_field"] or "-"
            print(
                f"  create {item['resource_type']} <- {parent} "
                f"(parent_id={parent_field}, live={item['live_support']})"
            )
        if details.get("ad_formats"):
            print("  ad formats: " + ", ".join(
                f"{item['format_id']}={item['coverage']}"
                for item in details["ad_formats"]
            ))
        if details["live_read_tools"]:
            print(f"  live reads: {len(details['live_read_tools'])}")
        if details["live_write_tools"]:
            print(f"  live writes: {len(details['live_write_tools'])}")
        surface = details.get("api_surface", {})
        if surface:
            print(
                "  api surface: "
                f"implemented={surface.get('implemented', 0)}, "
                f"planned={surface.get('planned', 0)}, total={surface.get('total', 0)}"
            )
        scope = details.get("readiness_scope", {})
        if scope:
            if scope.get("included"):
                print(
                    "  readiness scope: "
                    f"covered={scope.get('covered', 0)}/{scope.get('total', 0)}, "
                    f"queries={scope.get('query_covered', 0)}/"
                    f"{scope.get('query_total', 0)}, "
                    f"campaign writes={scope.get('managed_write_covered', 0)}/"
                    f"{scope.get('managed_write_total', 0)}"
                )
            else:
                print(
                    "  readiness scope: excluded"
                    + (
                        f" ({scope['exclusion_reason']})"
                        if scope.get("exclusion_reason")
                        else ""
                    )
                )
        inventory = details.get("official_inventory", {})
        if inventory:
            print(
                "  official inventory: "
                f"covered={inventory.get('covered', 0)}, "
                f"gaps={inventory.get('gaps', 0)}, "
                f"total={inventory.get('total', 0)}, "
                f"ratio={inventory.get('coverage_ratio', 0):.1%}, "
                f"scope={inventory.get('completeness', 'unknown')}"
            )
            if inventory.get("execution_statuses"):
                print(
                    "  covered execution: "
                    + ", ".join(
                        f"{key}={value}"
                        for key, value in inventory["execution_statuses"].items()
                    )
                )
            if inventory.get("evidence_levels"):
                print(
                    "  inventory evidence: "
                    + ", ".join(
                        f"{key}={value}"
                        for key, value in inventory["evidence_levels"].items()
                    )
                )
            if inventory.get("evidence_gaps"):
                print(
                    "  evidence gaps: "
                    f"{len(inventory['evidence_gaps'])} entries need operation-specific source or E2E"
                )
            if inventory.get("not_applicable_entries"):
                print(
                    "  inventory not applicable: "
                    f"{len(inventory['not_applicable_entries'])} entries excluded by provider API version"
                )
            for entry in inventory.get("gaps_entries", []):
                print(
                    f"  inventory gap: {entry.get('resource')}:{entry.get('action')} - "
                    f"{entry.get('provider_operation')}"
                )
        coverage = details.get("provider_method_coverage", {})
        if coverage:
            print(
                "  provider methods: "
                f"mapped={len(coverage)}, "
                f"surface={sum(bool(item.get('surface_entries')) for item in coverage.values())}"
            )
        for entry in details.get("api_surface_planned", []):
            print(
                f"  planned gap: {entry.get('resource')}:{entry.get('action')} - "
                f"{entry.get('gap')}"
            )
        for issue in details["issues"]:
            print(f"  ISSUE: {issue}")
    evidence = report.get("provider_evidence") or {}
    if evidence:
        print(
            "\nprovider evidence: "
            f"valid={evidence.get('valid', False)}, "
            f"runs={evidence.get('run_count', 0)}, "
            f"path={evidence.get('path', '-')}"
        )
        for provider, details in (evidence.get("providers") or {}).items():
            print(
                f"  [{provider}] fully_verified={details.get('fully_verified_runs', 0)}, "
                f"partial={details.get('partial_runs', 0)}, "
                f"limited={details.get('limited_runs', 0)}"
            )
    for error in report.get("provider_evidence_errors", []):
        print(f"  EVIDENCE ISSUE: {error}")
    if report["issues"]:
        print(f"\nFAILED: {len(report['issues'])} issue(s)")
    elif report.get("provider_evidence_errors"):
        print(
            f"\nFAILED: {len(report['provider_evidence_errors'])} "
            "Provider evidence issue(s)"
        )
    else:
        print("\nOK: no tool_source contract issues")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit JSON instead of text")
    parser.add_argument(
        "--evidence",
        help="path to a controlled Provider E2E evidence JSON file",
    )
    args = parser.parse_args(argv)
    report = audit_provider_tools(args.evidence)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        _print_text(report)
    return 1 if report["issues"] or report.get("provider_evidence_errors") else 0


if __name__ == "__main__":
    raise SystemExit(main())
