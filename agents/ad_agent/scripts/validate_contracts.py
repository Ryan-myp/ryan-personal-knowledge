#!/usr/bin/env python3
"""Validate the executable ad-agent tool contract without provider I/O.

This is intentionally a release gate rather than a unit-test helper.  It
loads the same built-in Capabilities through AgentRuntime, so a new Skill or
Tool must satisfy the same registration boundary used by the service.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.ad_agent import AgentRuntime  # noqa: E402
from agents.ad_agent.capabilities.dv360 import create_dv360_capability  # noqa: E402
from agents.ad_agent.capabilities.google import create_google_capability  # noqa: E402
from agents.ad_agent.capabilities.meta import create_meta_capability  # noqa: E402
from agents.ad_agent.capabilities.tiktok import create_tiktok_capability  # noqa: E402
from agents.ad_agent.core.interfaces import ReplayPolicy, ToolEffect  # noqa: E402
from agents.ad_agent.persistence.store import AdAgentStore  # noqa: E402


EXPECTED_COUNTS = {"meta": 16, "google-ads": 18, "tiktok": 24, "dv360": 14}
PROTECTED_FIELDS = {
    "token", "accesstoken", "refreshtoken", "developertoken", "clientid",
    "clientsecret", "privatekey", "bcid", "partnerid", "mcc",
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


def main() -> int:
    store = AdAgentStore(":memory:")
    runtime = AgentRuntime(persistence_store=store, offline_mode=True)
    for factory in (
        create_meta_capability,
        create_google_capability,
        create_tiktok_capability,
        create_dv360_capability,
    ):
        runtime.register_capability(factory())

    errors: list[str] = []
    tools = runtime.registry.list_all()
    names = [tool.name for tool in tools]
    if len(names) != len(set(names)):
        errors.append("tool names must be globally unique")
    for platform, expected in EXPECTED_COUNTS.items():
        actual = len(runtime.registry.list_by_platform(platform))
        if actual != expected:
            errors.append(f"{platform}: expected {expected} tools, got {actual}")

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
        for normalized, path in _walk_keys(tool.input_schema.to_dict()):
            if normalized in PROTECTED_FIELDS:
                errors.append(f"{tool.name}: protected field declared in schema at {path}")

    store.close()
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"validated {len(tools)} tools across {len(EXPECTED_COUNTS)} platforms")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
