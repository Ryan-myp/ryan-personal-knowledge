#!/usr/bin/env python3
"""Run package integrity/trust preflight without importing Plugin code."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.ad_agent.core.plugin_preflight import build_plugin_preflight  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--require-signature", action="store_true")
    parser.add_argument("--signing-key-env", default="AD_AGENT_PLUGIN_SIGNING_KEY")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    key = os.environ.get(args.signing_key_env)
    report = build_plugin_preflight(
        args.directory,
        signing_key=key,
        require_signature=args.require_signature,
    )
    encoded = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    else:
        print(encoded, end="")
    return 0 if report["status"] != "blocked" else 1


if __name__ == "__main__":
        raise SystemExit(main())
