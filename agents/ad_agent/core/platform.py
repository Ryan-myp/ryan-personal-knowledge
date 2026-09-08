"""Provider identity helpers shared by Runtime, Skills and adapters."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import re
from typing import Any, Mapping, Optional

import yaml


def _token(value: Any) -> str:
    return str(value or "").strip().casefold()


def _read_skill_identity(skill_file: Path) -> Optional[dict[str, Any]]:
    try:
        text = skill_file.read_text(encoding="utf-8")
        if not text.startswith("---"):
            return None
        parts = text.split("---", 2)
        if len(parts) != 3:
            return None
        metadata = yaml.safe_load(parts[1]) or {}
        if not isinstance(metadata, dict):
            return None
        identity = metadata.get("skill", metadata)
        if not isinstance(identity, dict):
            return None
        platform = _token(identity.get("platform") or skill_file.parent.name)
        if not platform:
            return None
        aliases = identity.get("aliases", [])
        if isinstance(aliases, str):
            aliases = [aliases]
        aliases = aliases if isinstance(aliases, list) else []
        aliases = [_token(alias) for alias in aliases if _token(alias)]
        name = _token(identity.get("name"))
        if name:
            aliases.append(name)
        return {
            "platform": platform,
            "aliases": tuple(dict.fromkeys(aliases)),
            "parser_platform": _token(identity.get("parser_platform") or identity.get("parser_label")),
        }
    except (OSError, ValueError, UnicodeError, yaml.YAMLError):
        return None


@lru_cache(maxsize=1)
def _declared_identity_maps() -> tuple[dict[str, str], dict[str, str]]:
    """Read provider identity from mounted standard Skill metadata."""
    root = Path(__file__).resolve().parent.parent / "skills" / "channels"
    aliases: dict[str, str] = {}
    labels: dict[str, str] = {}
    files = sorted(root.rglob("SKILL.md")) if root.is_dir() else []
    for skill_file in files:
        identity = _read_skill_identity(skill_file)
        if not identity:
            continue
        canonical = identity["platform"]
        aliases.setdefault(canonical, canonical)
        for alias in identity["aliases"]:
            aliases.setdefault(alias, canonical)
        if identity["parser_platform"]:
            labels[canonical] = identity["parser_platform"]
    return aliases, labels


def refresh_declared_platform_identities() -> None:
    _declared_identity_maps.cache_clear()


def normalize_platform(
    platform: str, aliases: Optional[Mapping[str, str]] = None
) -> str:
    value = _token(platform)
    if not value:
        return ""
    declared, _ = _declared_identity_maps()
    declared.update({
        _token(key): _token(target)
        for key, target in (aliases or {}).items()
        if _token(key) and _token(target)
    })
    return declared.get(value, re.sub(r"[\s_]+", "-", value))


def parser_platform(platform: str) -> str:
    normalized = normalize_platform(platform)
    _, labels = _declared_identity_maps()
    return labels.get(normalized, normalized)


def declared_platforms() -> frozenset[str]:
    aliases, _ = _declared_identity_maps()
    return frozenset(value for value in aliases.values() if value and value != "all")


def platform_slug(platform: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", normalize_platform(platform)).strip("_")


def recognition_aliases(platform: str) -> set[str]:
    normalized = normalize_platform(platform)
    declared, _ = _declared_identity_maps()
    aliases = {normalized, normalized.replace("-", " "), normalized.replace("_", " ")}
    aliases.update(alias for alias, target in declared.items() if target == normalized)
    return {alias for alias in aliases if alias}
