"""Run unchanged qguard rules against HEAD and current changed Python sources."""

from __future__ import annotations

import argparse
from collections import Counter
from fnmatch import fnmatchcase
import hashlib
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]


def _fingerprint(source: str, issue) -> tuple[str, str, str]:
    lines = source.splitlines()
    text = lines[issue.line - 1] if 0 < issue.line <= len(lines) else ""
    digest = hashlib.sha256(text.strip().encode("utf-8")).hexdigest()
    return issue.rule_id, issue.severity.value, digest


def compare_findings(before: str, old_issues, after: str, new_issues) -> list[dict]:
    """Keep legacy debt visible while rejecting additional findings."""
    remaining = Counter(_fingerprint(before, issue) for issue in old_issues)
    added = []
    for issue in new_issues:
        key = _fingerprint(after, issue)
        if remaining[key]:
            remaining[key] -= 1
            continue
        added.append({
            "rule_id": key[0], "severity": key[1],
            "source_hash": key[2], "line": issue.line,
        })
    return added


def _git(root: Path, *arguments: str, check: bool = True):
    return subprocess.run(
        ["git", "-C", str(root), *arguments],
        check=check, capture_output=True, timeout=30,
    )


def changed_sources(root: Path, ignored) -> list[Path]:
    changed = _git(root, "diff", "--name-only", "-z", "HEAD", "--", "*.py")
    untracked = _git(root, "ls-files", "--others", "--exclude-standard", "-z", "--", "*.py")
    names = {
        name.decode("utf-8") for name in
        (changed.stdout + untracked.stdout).split(b"\0") if name
    }
    return [
        root / name for name in sorted(names)
        if (root / name).is_file()
        and not any(
            fnmatchcase(name, pattern) or fnmatchcase(Path(name).name, pattern)
            for pattern in ignored
        )
    ]


def analyze_delta(root: Path, analyzer, ignored) -> dict:
    files = changed_sources(root, ignored)
    new_findings = []
    old_count = 0
    current_count = 0
    for path in files:
        relative = path.relative_to(root).as_posix()
        path.resolve().relative_to(root.resolve())
        previous = _git(root, "show", f"HEAD:{relative}", check=False)
        tracked = _git(
            root, "ls-files", "--error-unmatch", relative, check=False,
        ).returncode == 0
        if previous.returncode and tracked:
            raise RuntimeError("unable to read tracked baseline source")
        before = previous.stdout.decode("utf-8") if previous.returncode == 0 else ""
        after = path.read_text(encoding="utf-8")
        old = analyzer.analyze(before, path)
        current = analyzer.analyze(after, path)
        old_count += len(old)
        current_count += len(current)
        new_findings.extend(
            {"file": relative, **row}
            for row in compare_findings(before, old, after, current)
        )
    return {
        "scope": "changed_python_sources_vs_HEAD",
        "files_scanned": len(files), "baseline_findings": old_count,
        "current_findings": current_count, "new_findings": new_findings,
        "gate_passed": not new_findings,
        "whole_repository_gate": "not_assessed_by_delta_gate",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--qguard-home", type=Path,
        default=Path.home() / ".codex/skills/code-quality-guard",
    )
    args = parser.parse_args()
    try:
        home = args.qguard_home.expanduser().resolve()
        if not (home / "engines/enhanced_analyzer.py").is_file():
            raise RuntimeError("qguard is unavailable; the delta gate cannot run")
        sys.path.insert(0, str(home))
        from engines.enhanced_analyzer import EnhancedAnalyzer
        from engines.spec_parser import SpecParser
        spec = SpecParser().auto_generate(ROOT)
        result = analyze_delta(ROOT, EnhancedAnalyzer(spec), spec.security.ignore_patterns)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["gate_passed"] else 1
    except (
        OSError, ValueError, SyntaxError, ImportError,
        RuntimeError, subprocess.SubprocessError,
    ) as error:
        print(f"Quality delta scan failed: {type(error).__name__}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
