"""Generic namespace normalization for Core contracts.

Core uses a namespace as an opaque scope published by an extension.  It is
not a catalogue of vendors, channels, or business domains; the embedding
application decides what a namespace means and how natural-language aliases
are published.
"""

from __future__ import annotations

import re


def normalize_namespace(value: str) -> str:
    """Return a deterministic identifier suitable for registry lookups."""
    normalized = str(value or "").strip().casefold()
    return re.sub(r"[\s_]+", "-", normalized) if normalized else ""


def namespace_slug(value: str) -> str:
    """Convert a namespace identifier into a stable package/module slug."""
    return re.sub(r"[^a-z0-9]+", "_", normalize_namespace(value)).strip("_")
