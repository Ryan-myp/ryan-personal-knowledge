"""Provider identity helpers shared by Runtime, Skills and adapters.

Platform identity is data owned by a provider Skill, not a Core channel
registry.  ``SKILL.md`` frontmatter may declare natural-language aliases and
an optional parser-facing label.  Core only supplies the generic lookup and
normalization mechanics, so adding a provider does not require editing this
module.

The built-in Skill metadata is loaded lazily for compatibility with callers
that normalize a platform outside ``AgentRuntime`` (for example the
authorization and persistence helpers).  Runtime-managed Skills still
publish their aliases directly to the parser lifecycle; aliases are never
used to create executable Tools or grant permissions.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import re
from typing import Any, Mapping, Optional

import yaml


def _token(value: Any) -> str:
    """Normalize an identity token for case-insensitive lookup."""
    return str(value or "").strip().lower()


def _read_skill_identity(skill_file: Path) -> Optional[dict[str, Any]]:
    """Read only provider identity metadata from a standard ``SKILL.md``."""
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
        if not isinstance(aliases, list):
            aliases = []
        # A Skill name is useful for model recognition, but it is not a
        # canonical provider ID and must not replace ``platform``.
        skill_name = _token(identity.get("name"))
        aliases = [_token(alias) for alias in aliases if _token(alias)]
        if skill_name:
            aliases.append(skill_name)
        parser_platform = _token(
            identity.get("parser_platform") or identity.get("parser_label")
        )
        return {
            "platform": platform,
            "aliases": tuple(dict.fromkeys(aliases)),
            "parser_platform": parser_platform,
        }
    except (OSError, ValueError, yaml.YAMLError, UnicodeError):
        # SkillLoader performs strict validation.  This compatibility lookup
        # must never make an otherwise usable Runtime fail during import.
        return None


@lru_cache(maxsize=1)
def _declared_identity_maps() -> tuple[dict[str, str], dict[str, str]]:
    """Return ``alias -> canonical`` and ``canonical -> parser label`` maps.

    Discovery is convention-based and deliberately does not enumerate any
    provider names.  A new channel becomes visible by mounting its standard
    Skill directory and declaring its own identity metadata.
    """
    channels_root = Path(__file__).resolve().parent.parent / "skills" / "channels"
    aliases: dict[str, str] = {}
    parser_labels: dict[str, str] = {}
    if not channels_root.is_dir():
        return aliases, parser_labels
    for skill_file in sorted(channels_root.rglob("SKILL.md")):
        identity = _read_skill_identity(skill_file)
        if not identity:
            continue
        canonical = identity["platform"]
        aliases.setdefault(canonical, canonical)
        for alias in identity["aliases"]:
            aliases.setdefault(alias, canonical)
        parser_platform = identity.get("parser_platform")
        if parser_platform:
            parser_labels[canonical] = parser_platform
    return aliases, parser_labels


def refresh_declared_platform_identities() -> None:
    """Invalidate the lazy Skill identity snapshot after a package change."""
    _declared_identity_maps.cache_clear()


def normalize_platform(
    platform: str,
    aliases: Optional[Mapping[str, str]] = None,
) -> str:
    """Return a stable provider identifier without a Core provider table.

    ``aliases`` is an optional caller-owned overlay, useful for dynamically
    mounted Skills.  Values declared by the provider Skill are the default;
    an overlay wins only for the current call and is never persisted here.
    """
    value = _token(platform)
    if not value:
        return ""
    declared_aliases, _ = _declared_identity_maps()
    normalized_aliases = dict(declared_aliases)
    normalized_aliases.update(
        {
            _token(key): _token(value)
            for key, value in (aliases or {}).items()
            if _token(key) and _token(value)
        }
    )
    return normalized_aliases.get(value, value)


def parser_platform(platform: str) -> str:
    """Return a provider-declared parser-facing label when one exists."""
    normalized = normalize_platform(platform)
    _, parser_labels = _declared_identity_maps()
    return parser_labels.get(normalized, normalized)


def declared_platforms() -> frozenset[str]:
    """Return provider identities declared by the loaded Skill catalog."""
    aliases, _ = _declared_identity_maps()
    return frozenset(value for value in aliases.values() if value and value != "all")


def platform_slug(platform: str) -> str:
    """Convert a provider identifier into a Python package/module slug."""
    return re.sub(r"[^a-z0-9]+", "_", normalize_platform(platform)).strip("_")


def recognition_aliases(platform: str) -> set[str]:
    """Return generic and provider-declared spellings for a provider."""
    normalized = normalize_platform(platform)
    declared_aliases, _ = _declared_identity_maps()
    aliases = {
        normalized,
        normalized.replace("-", " "),
        normalized.replace("_", " "),
    }
    aliases.update(
        alias for alias, target in declared_aliases.items() if target == normalized
    )
    return {alias for alias in aliases if alias}
