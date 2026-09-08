"""Provider-neutral identifier normalization.

Provider identity and natural-language aliases are published by the active
Skill/Capability lifecycle. Core only normalizes an identifier; it never
scans the repository or maintains a provider catalogue.
"""

from __future__ import annotations

import re


def normalize_platform(platform: str) -> str:
    """Return a deterministic provider identifier for storage and lookup."""
    value = str(platform or "").strip().casefold()
    if not value:
        return ""
    return re.sub(r"[\s_]+", "-", value)


def platform_slug(platform: str) -> str:
    """Convert a normalized provider identifier into a module/package slug."""
    return re.sub(r"[^a-z0-9]+", "_", normalize_platform(platform)).strip("_")
