#!/usr/bin/env python3.13
"""Run a no-network preflight before a controlled real-account API test."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.ad_agent.domain.ad.provider_preflight import build_provider_preflight  # noqa: E402
from agents.ad_agent.runtime.account_policy import AccountWhitelistValidator  # noqa: E402
from agents.ad_agent.runtime.runtime import AdvertisingComposition  # noqa: E402
from agents.ad_agent.tools.providers.source_factory import (  # noqa: E402
    discover_tool_source_factory,
    normalize_platform,
)


def _load_mapping(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return value if isinstance(value, dict) else {}


def _credential_configured(path: Path, platform: str) -> bool:
    if not path.exists():
        return False
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    if not isinstance(value, dict):
        return False
    wanted = normalize_platform(platform)
    return any(normalize_platform(str(key)) == wanted and isinstance(item, dict) and bool(item) for key, item in value.items())


def build_runtime(config_path: Path) -> AdvertisingComposition:
    config = _load_mapping(config_path)
    runtime = AdvertisingComposition(
        require_llm=False,
        offline_mode=True,
        enforce_account_scope=True,
        execution_mode=str(config.get("execution_mode", "dry_run")),
        allow_live_writes=bool(config.get("allow_live_writes", False)),
        live_approved_tools=set(config.get("live_approved_tools", []) or []),
        granted_permissions=set(config.get("granted_permissions", ["ads.read", "ads.plan"]) or []),
        whitelist_validator=AccountWhitelistValidator(str(config_path)),
    )
    for path in sorted(
        (ROOT / "agents" / "ad_agent" / "tools" / "providers").iterdir()
    ):
        if not path.is_dir() or path.name.startswith("_") or not (path / "provider.py").is_file():
            continue
        factory = discover_tool_source_factory(path.name)
        if callable(factory):
            runtime.register_tool_source(factory())
    return runtime


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", required=True)
    parser.add_argument("--tool", action="append", dest="tools", help="Tool name; repeatable")
    parser.add_argument("--account-id", default="")
    parser.add_argument("--live", action="store_true", help="check live gates; still never calls a provider")
    parser.add_argument("--config", type=Path, default=ROOT / "agents" / "ad_agent" / "config.yaml")
    parser.add_argument("--credentials-file", type=Path, default=ROOT / "config" / "ad_platform_credentials.json")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    runtime = build_runtime(args.config)
    try:
        report = build_provider_preflight(
            runtime,
            platform=args.platform,
            tool_names=args.tools,
            account_id=args.account_id,
            credential_configured=_credential_configured(args.credentials_file, args.platform),
            live_requested=args.live,
            live_environment_enabled=os.environ.get("AD_AGENT_ENABLE_LIVE") == "1",
        )
    finally:
        runtime.close(wait=True)
    encoded = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    else:
        print(encoded, end="")
    return 0 if report["status"] != "blocked" else 1


if __name__ == "__main__":
    raise SystemExit(main())
