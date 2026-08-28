#!/usr/bin/env python3
"""Audit metadata-driven ad-agent capabilities without provider I/O.

The audit discovers packages by the same convention as Runtime:
``capabilities/<platform>/capability.py`` plus a ``create_*_capability``
factory. It is deliberately a report/release-gate tool, not a second
registry. Adding a provider therefore changes the audit output automatically
and does not require editing a central channel list.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.ad_agent.capabilities.factory import discover_capability_factory  # noqa: E402
from agents.ad_agent.core.interfaces import AdFormatCoverage, ReplayPolicy, ToolEffect  # noqa: E402
from agents.ad_agent.runtime.runtime import AgentRuntime  # noqa: E402


def discover_platform_slugs() -> list[str]:
    """Return installed capability package slugs, excluding Python caches."""
    capabilities_root = Path(__file__).resolve().parents[1] / "capabilities"
    return sorted(
        path.name
        for path in capabilities_root.iterdir()
        if path.is_dir()
        and not path.name.startswith("_")
        and (path / "capability.py").is_file()
    )


def _schema_properties(definition: Any) -> dict[str, Any]:
    schema = getattr(definition, "input_schema", None)
    return getattr(schema, "properties", {}) or {}


def audit_capabilities() -> dict[str, Any]:
    """Build a JSON-safe capability report without constructing API clients."""
    report: dict[str, Any] = {"platforms": {}, "issues": []}
    runtime = AgentRuntime(offline_mode=True, enforce_account_scope=False)

    for slug in discover_platform_slugs():
        try:
            factory = discover_capability_factory(slug)
            if not callable(factory):
                report["issues"].append(f"{slug}: capability factory not found")
                continue
            capability = factory()
            runtime.register_capability(capability)
            client_class = getattr(capability, "provider_client_class", None)
            coverage = getattr(capability, "provider_method_coverage", {}) or {}
            exclusions = set(getattr(capability, "provider_method_exclusions", set()) or set())
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
            report["issues"].append(f"{slug}: failed to load capability: {exc}")
    all_names: list[str] = []
    definitions_by_platform: dict[str, list[Any]] = {}
    for definition in runtime.registry.list_all():
        definitions_by_platform.setdefault(str(definition.platform), []).append(definition)

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
                    "provider_required": list(getattr(schema, "provider_required", []) or []),
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
            "issues": platform_issues,
        }
        report["issues"].extend(f"{platform}: {issue}" for issue in platform_issues)

    duplicate_names = sorted(name for name, count in Counter(all_names).items() if count > 1)
    report["duplicate_tool_names"] = duplicate_names
    report["tool_count"] = len(all_names)
    report["issues"].extend(f"duplicate tool name: {name}" for name in duplicate_names)
    return report


def _print_text(report: dict[str, Any]) -> None:
    print(f"capabilities: {len(report['platforms'])}, tools: {report['tool_count']}")
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
        for issue in details["issues"]:
            print(f"  ISSUE: {issue}")
    if report["issues"]:
        print(f"\nFAILED: {len(report['issues'])} issue(s)")
    else:
        print("\nOK: no capability contract issues")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit JSON instead of text")
    args = parser.parse_args(argv)
    report = audit_capabilities()
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        _print_text(report)
    return 1 if report["issues"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
