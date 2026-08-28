#!/usr/bin/env python3
"""Validate the executable ad-agent tool contract without provider I/O.

This is intentionally a release gate rather than a unit-test helper.  It
loads the same built-in Capabilities through AgentRuntime, so a new Skill or
Tool must satisfy the same registration boundary used by the service.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.ad_agent import AgentRuntime  # noqa: E402
from agents.ad_agent.capabilities.factory import (  # noqa: E402
    discover_capability_factory,
)
from agents.ad_agent.scripts.audit_capabilities import discover_platform_slugs  # noqa: E402
from agents.ad_agent.core.interfaces import ReplayPolicy, ToolEffect  # noqa: E402
from agents.ad_agent.persistence.store import AdAgentStore  # noqa: E402


# Built-in capabilities are a regression baseline, not a closed-world count.
# Additional Skill-owned tools must be allowed without editing this release
# gate; every discovered tool is still checked below for its contract.
MINIMUM_COUNTS = {"meta": 16, "google-ads": 18, "tiktok": 24, "dv360": 14}
PROTECTED_FIELDS = {
    "token", "accesstoken", "refreshtoken", "developertoken", "clientid",
    "clientsecret", "apikey", "appsecret", "secretkey", "privatekey",
    "privatekeyid", "serviceaccount", "serviceaccountemail", "saemail",
    "developerkey", "bcid", "partnerid", "mcc",
    "authorization", "credential", "credentials", "perterid",
}


def _walk_keys(value, path=""):
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key)
            normalized = "".join(char for char in key_text.lower() if char.isalnum())
            current = f"{path}.{key_text}" if path else key_text
            yield normalized, current
            yield from _walk_keys(child, current)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk_keys(child, f"{path}[{index}]")


def build_runtime() -> AgentRuntime:
    """Build the same no-I/O runtime used by the release contract gate."""
    store = AdAgentStore(":memory:")
    runtime = AgentRuntime(persistence_store=store, offline_mode=True)
    for slug in discover_platform_slugs():
        factory = discover_capability_factory(slug)
        if callable(factory):
            runtime.register_capability(factory())
    # Keep the in-memory backend reachable for callers that want to close it
    # after inspecting the runtime without changing AgentRuntime's public API.
    runtime._contract_gate_store = store
    return runtime


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def build_contract_snapshot(runtime: AgentRuntime) -> dict:
    """Return a deterministic, JSON-safe snapshot of executable contracts.

    This is a release artifact, not Runtime configuration.  A new Capability
    is discovered by convention and appears in the snapshot automatically;
    updating the checked-in artifact is the deliberate review step for a
    contract change.
    """
    definitions_by_platform: dict[str, list[dict]] = {}
    for definition in runtime.registry.list_all():
        contract = definition.to_dict()
        contract["timeout_seconds"] = definition.timeout_seconds
        contract["max_output_bytes"] = definition.max_output_bytes
        definitions_by_platform.setdefault(str(definition.platform), []).append(contract)

    platforms: dict[str, dict] = {}
    for platform, contracts in sorted(definitions_by_platform.items()):
        tools = sorted(contracts, key=lambda item: item["name"])
        platforms[platform] = {
            "tool_count": len(tools),
            "digest": _digest(tools),
            "tools": tools,
        }
    body = {
        "format_version": 1,
        "tool_count": sum(item["tool_count"] for item in platforms.values()),
        "platforms": platforms,
    }
    return {**body, "digest": _digest(body)}


def _snapshot_body(snapshot: dict) -> dict:
    return {
        key: value for key, value in snapshot.items() if key != "digest"
    }


def _snapshot_differences(expected: dict, actual: dict) -> list[str]:
    differences: list[str] = []
    expected_platforms = expected.get("platforms", {})
    actual_platforms = actual.get("platforms", {})
    for platform in sorted(set(expected_platforms) | set(actual_platforms)):
        expected_tools = {
            tool.get("name"): tool
            for tool in expected_platforms.get(platform, {}).get("tools", [])
        }
        actual_tools = {
            tool.get("name"): tool
            for tool in actual_platforms.get(platform, {}).get("tools", [])
        }
        for name in sorted(set(expected_tools) - set(actual_tools)):
            differences.append(f"{platform}: removed tool {name}")
        for name in sorted(set(actual_tools) - set(expected_tools)):
            differences.append(f"{platform}: added tool {name}")
        for name in sorted(set(expected_tools) & set(actual_tools)):
            if expected_tools[name] != actual_tools[name]:
                differences.append(f"{platform}: changed contract {name}")
    if not differences and expected.get("digest") != actual.get("digest"):
        differences.append("snapshot digest changed without a tool-level diff")
    return differences


def verify_snapshot(path: Path, actual: dict) -> list[str]:
    """Validate a checked-in snapshot and return human-readable drift errors."""
    try:
        expected = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"cannot read contract snapshot {path}: {exc}"]
    if not isinstance(expected, dict):
        return [f"contract snapshot {path} must contain a JSON object"]

    errors: list[str] = []
    expected_digest = expected.get("digest")
    if expected_digest != _digest(_snapshot_body(expected)):
        errors.append(f"contract snapshot {path} has an invalid embedded digest")
    if actual.get("digest") != _digest(_snapshot_body(actual)):
        errors.append("generated contract snapshot has an invalid embedded digest")
    if expected != actual:
        errors.extend(_snapshot_differences(expected, actual))
        if not errors or errors[-1] != "contract snapshot content differs":
            errors.append("contract snapshot content differs")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--snapshot",
        type=Path,
        help="write the discovered contract snapshot to this path",
    )
    group.add_argument(
        "--check-snapshot",
        type=Path,
        help="fail when the discovered contract differs from this snapshot",
    )
    args = parser.parse_args(argv)

    runtime = build_runtime()

    errors: list[str] = []
    tools = runtime.registry.list_all()
    names = [tool.name for tool in tools]
    if len(names) != len(set(names)):
        errors.append("tool names must be globally unique")
    for platform, minimum in MINIMUM_COUNTS.items():
        actual = len(runtime.registry.list_by_platform(platform))
        if actual < minimum:
            errors.append(f"{platform}: expected at least {minimum} built-in tools, got {actual}")

    for tool in tools:
        try:
            json.dumps(tool.input_schema.to_dict(), ensure_ascii=False)
        except (TypeError, ValueError) as exc:
            errors.append(f"{tool.name}: schema is not JSON serializable: {exc}")
        if not tool.required_permissions:
            errors.append(f"{tool.name}: required_permissions is empty")
        if tool.is_write_tool and tool.replay_policy != ReplayPolicy.UNSAFE:
            errors.append(f"{tool.name}: write tools must be unsafe to replay")
        if tool.effect_class == ToolEffect.READ and "ads.read" not in tool.required_permissions:
            errors.append(f"{tool.name}: read tool must require ads.read")
        if tool.is_write_tool and "ads.plan" not in tool.required_permissions:
            errors.append(f"{tool.name}: write tool must require ads.plan")
        properties = getattr(tool.input_schema, "properties", {}) or {}
        parent_field = getattr(tool, "parent_resource_id_field", None)
        if parent_field and parent_field not in properties:
            errors.append(
                f"{tool.name}: parent_resource_id_field '{parent_field}' "
                "must be declared in input_schema.properties"
            )
        if tool.action == "create" and tool.parent_resource_type and not parent_field:
            errors.append(
                f"{tool.name}: create tool with parent_resource_type "
                "must declare parent_resource_id_field"
            )
        for normalized, path in _walk_keys(tool.input_schema.to_dict()):
            if normalized in PROTECTED_FIELDS:
                errors.append(f"{tool.name}: protected field declared in schema at {path}")

    snapshot = build_contract_snapshot(runtime)
    if args.snapshot:
        args.snapshot.parent.mkdir(parents=True, exist_ok=True)
        args.snapshot.write_text(
            json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    if args.check_snapshot:
        errors.extend(verify_snapshot(args.check_snapshot, snapshot))

    contract_store = getattr(runtime, "_contract_gate_store", None)
    if contract_store is not None:
        contract_store.close()
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    if args.check_snapshot:
        print(
            f"validated {len(tools)} tools across "
            f"{len(runtime.registry.list_all_platforms())} platforms; "
            f"snapshot {args.check_snapshot} is current"
        )
    elif args.snapshot:
        print(
            f"validated {len(tools)} tools across "
            f"{len(runtime.registry.list_all_platforms())} platforms; "
            f"wrote {args.snapshot}"
        )
    else:
        print(f"validated {len(tools)} tools across {len(runtime.registry.list_all_platforms())} platforms")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
