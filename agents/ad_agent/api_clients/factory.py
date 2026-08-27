"""Platform API client construction.

This module is deliberately side-effect free: constructing a client never
performs a network request.  Keeping construction in one place prevents the
CLI, HTTP server, and Runtime from interpreting credential dictionaries as
already-built clients in different ways.
"""

from __future__ import annotations

import copy
from typing import Any, Optional


PLATFORM_ALIASES = {
    "google": "google-ads",
    "google-ads": "google-ads",
}


def normalize_platform(platform: str) -> str:
    return PLATFORM_ALIASES.get(platform, platform)


def create_platform_client(platform: str, credentials: Optional[dict[str, Any]] = None):
    """Create the requested platform client without mutating ``credentials``.

    ``None`` is returned for missing credentials.  Importing client classes is
    lazy so offline/dry-run usage does not require credentials or instantiate
    an unnecessary provider adapter.
    """
    credentials = copy.deepcopy(credentials or {})
    if not credentials:
        return None

    platform = normalize_platform(platform)
    if platform == "meta":
        from .meta_client import MetaAPIClient
        return MetaAPIClient(credentials)
    if platform == "google-ads":
        from .google_ads_client import GoogleAdsAPIClient
        return GoogleAdsAPIClient(credentials)
    if platform == "tiktok":
        from .tiktok_client import TikTokAPIClient
        return TikTokAPIClient(credentials)
    if platform == "dv360":
        from .dv360_client import DV360APIClient
        return DV360APIClient(credentials)
    return None
