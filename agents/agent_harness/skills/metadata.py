"""Bounded parsing and immutable advisory metadata for standard Skill packages."""

from collections.abc import Mapping
import math
from pathlib import Path
import re
from types import MappingProxyType
from typing import Any

import yaml

from ..core.plugins import normalize_plugin_version


MAX_SKILL_TEXT_CHARS = 100_000


def instruction_body(content: str) -> str:
    """Keep package metadata out of the model's advisory instruction budget."""
    return re.sub(
        r"\A---[ \t]*\r?\n.*?\r?\n---[ \t]*(?:\r?\n|\Z)", "", content,
        count=1, flags=re.DOTALL,
    ).strip()


def instruction_budget(remaining: int, slots: int, minimum_share: int) -> int:
    """Prefer the most relevant Skill while reserving space for other matches."""
    if slots <= 0 or remaining <= 0:
        return 0
    return max(remaining // slots, min(remaining // 2, remaining - minimum_share * (slots - 1)))


def immutable_metadata(value: Mapping[str, Any]) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("Skill metadata must be a mapping")
    remaining = [4096]

    def freeze(item: Any, depth: int) -> Any:
        remaining[0] -= 1
        if depth > 8 or remaining[0] < 0:
            raise ValueError("Skill metadata exceeds structural limits")
        if isinstance(item, Mapping):
            if any(not isinstance(key, str) for key in item):
                raise ValueError("Skill metadata keys must be strings")
            return MappingProxyType({key: freeze(child, depth + 1) for key, child in item.items()})
        if isinstance(item, (tuple, list)):
            return tuple(freeze(child, depth + 1) for child in item)
        if item is None or isinstance(item, (str, bool, int)):
            return item
        if isinstance(item, float) and math.isfinite(item):
            return item
        raise ValueError("Skill metadata must contain finite data values only")

    return freeze(value, 0)


def read_skill_text(path: Path) -> str:
    if path.is_symlink():
        raise ValueError("Skill instruction file cannot be a symlink")
    try:
        with path.open(encoding="utf-8") as handle:
            content = handle.read(MAX_SKILL_TEXT_CHARS + 1)
    except (OSError, UnicodeError) as error:
        raise ValueError(f"Unable to read UTF-8 Skill instructions ({type(error).__name__})") from None
    if len(content) > MAX_SKILL_TEXT_CHARS:
        raise ValueError("Skill instructions exceed the text limit")
    return content


def _selection_keywords(fields: Mapping[str, Any]) -> tuple[str, ...]:
    """Keep literal package triggers as advisory selection data, never code."""
    aliases = fields.get("aliases", ())
    triggers = fields.get("triggers", ())
    groups = [aliases] if isinstance(aliases, (list, tuple)) else []
    if isinstance(triggers, (list, tuple)):
        groups.extend(triggers)
    keywords = []
    for group in groups[:128]:
        if isinstance(group, Mapping):
            group = group.get("keywords", ())
        values = [group] if isinstance(group, str) else group
        if not isinstance(values, (list, tuple)):
            continue
        keywords.extend(value.strip()[:200] for value in values[:128]
                        if isinstance(value, str) and value.strip())
    return tuple(dict.fromkeys(keywords))[:128]


def skill_identity(content: str, directory_name: str) -> dict[str, Any]:
    header = re.match(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)", content, re.DOTALL)
    fields: Mapping[str, Any] = {}
    if content.startswith(("---\n", "---\r\n")):
        if header is None:
            raise ValueError("Skill frontmatter is not closed")
        try:
            raw = yaml.safe_load(header.group(1))
        except (yaml.YAMLError, RecursionError) as error:
            raise ValueError(f"Invalid Skill frontmatter ({type(error).__name__})") from None
        if not isinstance(raw, Mapping):
            raise ValueError("Skill frontmatter must be a mapping")
        fields = raw.get("skill", raw)
        if not isinstance(fields, Mapping):
            raise ValueError("Skill identity must be a mapping")
    metadata = immutable_metadata(fields.get("metadata") or {})
    keywords = _selection_keywords(fields)
    if keywords:
        metadata = immutable_metadata({**metadata, "selection_keywords": keywords})
    heading = re.search(r"(?m)^#\s+(.+?)\s*$", content)
    name = fields.get("name", directory_name)
    description = fields.get("description", heading.group(1).strip() if heading else "")
    if not isinstance(name, str) or not name.strip() or len(name) > 200:
        raise ValueError("Skill name must be bounded nonempty text")
    if not isinstance(description, str) or len(description) > 4000:
        raise ValueError("Skill description must be bounded text")
    try:
        version = normalize_plugin_version(fields.get("version", metadata.get("version", "1.0.0")))
    except (ValueError, TypeError):
        raise ValueError("Skill version must be valid semantic version data") from None
    return {
        "name": name.strip(), "description": description,
        "version": version,
        "metadata": metadata,
    }
