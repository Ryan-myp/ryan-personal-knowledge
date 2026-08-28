"""Provider identity helpers shared by Runtime, Skills and adapters.

Provider packages own their aliases.  The small compatibility set below is
only for the public Google naming used by the existing API surface; it is not
a provider routing table.  Any other platform is normalized by convention
and therefore requires no core change when it is added.
"""

from __future__ import annotations

import re
from typing import Mapping, Optional


# Compatibility aliases for the public Google Ads identifier.  Keep this in
# one place so authorization, discovery and parameter catalogs cannot drift.
COMPATIBILITY_ALIASES = {
    "google": "google-ads",
    "google_ads": "google-ads",
    "google ads": "google-ads",
    "google-ads": "google-ads",
}


def normalize_platform(platform: str, aliases: Optional[Mapping[str, str]] = None) -> str:
    """Return a stable provider identifier without knowing provider classes."""
    value = str(platform or "").strip().lower()
    if not value:
        return ""
    normalized_aliases = dict(COMPATIBILITY_ALIASES)
    normalized_aliases.update(
        {str(key).strip().lower(): str(value).strip().lower() for key, value in (aliases or {}).items()}
    )
    return normalized_aliases.get(value, value)


def parser_platform(platform: str) -> str:
    """Return the historical parser-facing Google label.

    The external parser contract currently exposes ``google`` in natural
    language intents while Tool/Client/authorization contracts use
    ``google-ads``. Keeping this compatibility conversion here avoids copying
    the alias map into parser methods.
    """
    normalized = normalize_platform(platform)
    return "google" if normalized == "google-ads" else normalized


def platform_slug(platform: str) -> str:
    """Convert a provider identifier into a Python package/module slug."""
    return re.sub(r"[^a-z0-9]+", "_", normalize_platform(platform)).strip("_")


def recognition_aliases(platform: str) -> set[str]:
    """Return generic natural-language spellings for a provider identifier."""
    normalized = normalize_platform(platform)
    aliases = {
        normalized,
        normalized.replace("-", " "),
        normalized.replace("_", " "),
    }
    for alias, target in COMPATIBILITY_ALIASES.items():
        if target == normalized:
            aliases.add(alias)
    return {alias for alias in aliases if alias}
