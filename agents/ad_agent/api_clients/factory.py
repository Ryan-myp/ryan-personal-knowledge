"""Platform API client construction.

This module is deliberately side-effect free: constructing a client never
performs a network request.  Keeping construction in one place prevents the
CLI, HTTP server, and Runtime from interpreting credential dictionaries as
already-built clients in different ways.
"""

from __future__ import annotations

import copy
import importlib
import inspect
import re
from typing import Any, Optional


PLATFORM_ALIASES = {
    "google": "google-ads",
    "google_ads": "google-ads",
    "google-ads": "google-ads",
}


def normalize_platform(platform: str) -> str:
    value = str(platform or "").strip().lower()
    return PLATFORM_ALIASES.get(value, value)


def _module_slug(platform: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", normalize_platform(platform)).strip("_")


def discover_client_factory(platform: str):
    """Discover an optional provider client factory by package convention."""
    canonical = normalize_platform(platform)
    slug = _module_slug(canonical)
    try:
        module = importlib.import_module(f"{__package__}.{slug}_client")
    except ModuleNotFoundError as exc:
        module_name = f"{__package__}.{slug}_client"
        # No same-name client module is a valid dry-run configuration. An
        # installed client with a missing dependency is an actionable error
        # and must not be silently downgraded to "no client".
        missing_names = {module_name, module_name.rsplit(".", 1)[0]}
        if exc.name in missing_names:
            return None
        raise
    names = [f"create_{slug}_client"]
    if canonical == "google-ads":
        names.append("create_google_ads_client")
    for name in names:
        factory = getattr(module, name, None)
        if callable(factory):
            return factory
    return None


def _call_factory(factory: Any, credentials: dict[str, Any]) -> Any:
    """Invoke a provider factory without masking its internal TypeError."""
    try:
        signature = inspect.signature(factory)
    except (TypeError, ValueError):
        return factory(credentials)
    try:
        signature.bind(credentials)
    except TypeError:
        return factory()
    return factory(credentials)


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
    discovered = discover_client_factory(platform)
    if callable(discovered):
        return _call_factory(discovered, credentials)
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
