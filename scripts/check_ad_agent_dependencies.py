#!/usr/bin/env python3
"""Report missing distributions declared by the ad-agent requirements file."""

from __future__ import annotations

import argparse
import importlib.metadata
import os
import re
import sys
from pathlib import Path


REQUIREMENT_NAME = re.compile(r"^([A-Za-z0-9][A-Za-z0-9_.-]*)")


def read_requirement_names(path: Path) -> list[tuple[str, str]]:
    requirements: list[tuple[str, str]] = []
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        requirement = raw_line.split("#", 1)[0].strip()
        if not requirement:
            continue
        match = REQUIREMENT_NAME.match(requirement)
        if not match:
            raise ValueError(f"Unsupported requirement at {path}:{line_number}: {requirement}")
        requirements.append((match.group(1), requirement))
    return requirements


def find_missing_requirements(path: Path) -> list[str]:
    missing: list[str] = []
    seen: set[str] = set()
    for package_name, requirement in read_requirement_names(path):
        normalized_name = re.sub(r"[-_.]+", "-", package_name).lower()
        if normalized_name in seen:
            continue
        seen.add(normalized_name)
        try:
            importlib.metadata.distribution(package_name)
        except importlib.metadata.PackageNotFoundError:
            missing.append(requirement)
    return missing


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--requirements",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "requirements.txt",
    )
    args = parser.parse_args()

    try:
        missing = find_missing_requirements(args.requirements)
    except (OSError, ValueError) as error:
        print(f"Unable to check ad-agent dependencies: {error}", file=sys.stderr)
        return 2

    if missing:
        print(
            f"Missing ad-agent dependencies for {sys.executable}:",
            file=sys.stderr,
        )
        for requirement in missing:
            print(f"  - {requirement}", file=sys.stderr)
        if os.environ.get("AD_AGENT_PYTHON"):
            print(
                "AD_AGENT_PYTHON is set, so this check is using that interpreter "
                "instead of the project .venv. Either install requirements into "
                "that interpreter, or unset AD_AGENT_PYTHON and run "
                "'make ad-agent-install'.",
                file=sys.stderr,
            )
        else:
            print(
                "Run 'make ad-agent-install' to install them into the project .venv.",
                file=sys.stderr,
            )
        return 1

    print(f"All ad-agent requirements are installed for {sys.executable}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
