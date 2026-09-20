#!/usr/bin/env python3
"""Normalize provenance metadata on legacy Markdown Wiki pages.

The command is intentionally conservative: it only fills missing governance
fields and replaces self-referential source references with an explicit
repository/internal provenance URI. It never changes page content, title,
version, confidence, status or publication state.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.ad_agent.knowledge_audit import infer_source_kind
from agents.ad_agent.domain.ad.knowledge import parse_frontmatter


_FRONTMATTER_RE = re.compile(r"\A---\n(?P<body>.*?)\n---(?P<tail>\n|$)", re.DOTALL)
_CONTROL_NAMES = {
    "ARCHITECTURE.md",
    "SCHEMA.md",
    "UPGRADE_SUMMARY.md",
    "USAGE_GUIDE.md",
    "QUALITY_STANDARD.md",
    "README.md",
    "index.md",
    "log.md",
}
_PROVENANCE_FIELDS = (
    "source_kind",
    "authority",
    "evidence_level",
    "last_verified_at",
)


def _is_content_page(path: Path, root: Path, metadata: dict[str, object]) -> bool:
    relative = path.relative_to(root)
    if path.name in _CONTROL_NAMES or not metadata:
        return False
    return str(metadata.get("wiki_type") or "").strip().lower() != "raw"


def _yaml_value(value: object) -> str:
    return json.dumps(str(value), ensure_ascii=False)


def _replace_or_append_fields(
    frontmatter: str,
    values: dict[str, str],
) -> str:
    lines = frontmatter.splitlines()
    replaced: set[str] = set()
    output: list[str] = []
    for line in lines:
        match = re.match(r"^(?P<key>[A-Za-z_][A-Za-z0-9_-]*)\s*:", line)
        key = match.group("key") if match else ""
        if key in values:
            output.append(f"{key}: {_yaml_value(values[key])}")
            replaced.add(key)
        else:
            output.append(line)
    for key in values:
        if key not in replaced:
            output.append(f"{key}: {_yaml_value(values[key])}")
    return "\n".join(output)


def _normalise_page(path: Path, root: Path, *, today: str) -> tuple[str, list[str]]:
    raw = path.read_text(encoding="utf-8")
    match = _FRONTMATTER_RE.match(raw)
    if not match:
        return raw, []
    metadata, _body = parse_frontmatter(raw)
    if not _is_content_page(path, root, metadata):
        return raw, []

    relative = path.relative_to(root).as_posix()
    document_id = str(metadata.get("id") or path.stem).strip()
    source_ref = str(metadata.get("source_ref") or "").strip()
    source = str(metadata.get("source") or "").strip()
    changes: list[str] = []

    self_reference = source_ref == relative or source_ref.endswith(relative)
    if self_reference:
        if relative.startswith(("business/", "expertise/")):
            source_ref = f"internal://ad-agent/playbook/{document_id}"
        else:
            source_ref = f"repository://ad-agent/knowledge/{document_id}"
        changes.append("source_ref")

    inferred_kind = infer_source_kind(source_ref, source)
    if self_reference:
        inferred_kind = "internal" if relative.startswith(
            ("business/", "expertise/")
        ) else "code"

    authority_by_kind = {
        "official": "official",
        "code": "repository",
        "internal": "operator",
        "user": "operator",
        "inferred": "llm",
    }
    evidence_by_kind = {
        "official": "reviewed",
        "code": "reviewed",
        "internal": "provisional",
        "user": "provisional",
        "inferred": "provisional",
    }
    updated_at = str(metadata.get("updated_at") or "").strip().strip('"').strip("'")
    values = {
        "source_ref": source_ref,
        "source_kind": str(metadata.get("source_kind") or inferred_kind),
        "authority": str(
            metadata.get("authority") or authority_by_kind.get(inferred_kind, "operator")
        ),
        "evidence_level": str(
            metadata.get("evidence_level")
            or evidence_by_kind.get(inferred_kind, "provisional")
        ),
        "last_verified_at": str(metadata.get("last_verified_at") or updated_at or today),
    }
    for key in _PROVENANCE_FIELDS:
        if not metadata.get(key):
            changes.append(key)
    if self_reference or changes:
        new_frontmatter = _replace_or_append_fields(match.group("body"), values)
        updated = f"---\n{new_frontmatter}\n---{match.group('tail')}{raw[match.end():]}"
        return updated, list(dict.fromkeys(changes))
    return raw, []


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--knowledge-root", default="agents/ad_agent/knowledge_base")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    root = Path(args.knowledge_root).resolve()
    changed = []
    for path in sorted(root.rglob("*.md")):
        updated, fields = _normalise_page(path, root, today=date.today().isoformat())
        if not fields or updated == path.read_text(encoding="utf-8"):
            continue
        changed.append({"path": path.relative_to(root).as_posix(), "fields": fields})
        if args.write:
            path.write_text(updated, encoding="utf-8")
    print(json.dumps({"write": args.write, "changed": changed}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
