"""Canonical Capability construction for the ad-agent runtime.

The runtime used to keep a second platform-to-module map in addition to the
public capability factories.  That made dynamic Skill loading subtly
different from the CLI/API registration path.  This module is the single
construction seam for platform capabilities; it only constructs Python
objects and never performs network I/O.
"""

from __future__ import annotations

from typing import Any, Optional


PLATFORM_ALIASES = {
    "google": "google-ads",
    "google_ads": "google-ads",
    "google-ads": "google-ads",
}

SUPPORTED_PLATFORMS = ("meta", "google-ads", "tiktok", "dv360")


def normalize_platform(platform: str) -> str:
    """Return the canonical Runtime platform name."""
    value = str(platform or "").strip().lower()
    return PLATFORM_ALIASES.get(value, value)


def create_capability(platform: str, api_client: Optional[Any] = None):
    """Create a platform Capability through its public factory.

    ``api_client`` is injected as-is.  Capability construction is deliberately
    side-effect free; a handler may perform network I/O only when Runtime
    executes a read tool or an explicitly approved live write.
    """
    canonical = normalize_platform(platform)
    if canonical == "meta":
        from .meta import create_meta_capability
        return create_meta_capability(api_client)
    if canonical == "google-ads":
        from .google import create_google_capability
        return create_google_capability(api_client)
    if canonical == "tiktok":
        from .tiktok import create_tiktok_capability
        return create_tiktok_capability(api_client)
    if canonical == "dv360":
        from .dv360 import create_dv360_capability
        return create_dv360_capability(api_client)
    raise ValueError(
        f"Unsupported ad platform '{platform}'. "
        f"Supported platforms: {', '.join(SUPPORTED_PLATFORMS)}"
    )


def capability_platform(platform: str) -> str:
    """Compatibility helper used by Skill binding code."""
    return normalize_platform(platform)
