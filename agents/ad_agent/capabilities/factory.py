"""Canonical Capability construction for the ad-agent runtime.

The runtime used to keep a second platform-to-module map in addition to the
public capability factories.  That made dynamic Skill loading subtly
different from the CLI/API registration path.  This module is the single
construction seam for platform capabilities; it only constructs Python
objects and never performs network I/O.
"""

from __future__ import annotations

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
    """Return the canonical Runtime platform name."""
    value = str(platform or "").strip().lower()
    return PLATFORM_ALIASES.get(value, value)


def _module_slug(platform: str) -> str:
    """Convert a platform identifier into its package/module spelling."""
    canonical = normalize_platform(platform)
    # The existing package is named ``google`` while the public platform ID
    # is ``google-ads``. Keep this package spelling local to discovery rather
    # than making every caller carry a special case.
    if canonical == "google-ads":
        return "google"
    return re.sub(r"[^a-z0-9]+", "_", canonical).strip("_")


def discover_capability_factory(platform: str):
    """Find a Capability factory by package convention.

    A provider package owns its executable surface.  The shared runtime only
    knows the convention ``capabilities/<platform>/capability.py`` and the
    factory name ``create_<platform>_capability``.  The built-in ``google``
    package is the one deliberate alias because its public platform ID is
    ``google-ads``.
    """
    canonical = normalize_platform(platform)
    slug = _module_slug(canonical)
    module_name = f"{__package__}.{slug}.capability"
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        # A missing provider module means the channel is not installed. Do not
        # hide a dependency failure raised from inside an installed provider.
        missing_names = {module_name, module_name.rsplit(".", 1)[0]}
        if exc.name in missing_names:
            return None
        raise

    candidates = [f"create_{slug}_capability"]
    if canonical == "google-ads":
        candidates.append("create_google_capability")
    for name in candidates:
        factory = getattr(module, name, None)
        if callable(factory):
            return factory
    return next(
        (
            value for name, value in vars(module).items()
            if name.startswith("create_")
            and name.endswith("_capability")
            and callable(value)
        ),
        None,
    )


def _call_factory(factory: Any, api_client: Optional[Any]) -> Any:
    """Call either the one-argument or zero-argument package factory.

    Inspecting the signature avoids treating a real TypeError inside a
    provider factory as evidence that it does not accept ``api_client``.
    """
    try:
        signature = inspect.signature(factory)
    except (TypeError, ValueError):
        return factory(api_client)
    try:
        signature.bind(api_client)
    except TypeError:
        return factory()
    return factory(api_client)


def create_capability(platform: str, api_client: Optional[Any] = None):
    """Create a platform Capability through its public factory.

    ``api_client`` is injected as-is.  Capability construction is deliberately
    side-effect free; a handler may perform network I/O only when Runtime
    executes a read tool or an explicitly approved live write.
    """
    canonical = normalize_platform(platform)
    factory = discover_capability_factory(canonical)
    if not callable(factory):
        raise ValueError(
            f"Unsupported ad platform '{platform}'. "
            "Add capabilities/<platform>/capability.py with a "
            "create_<platform>_capability factory."
        )
    return _call_factory(factory, api_client)


def capability_platform(platform: str) -> str:
    """Compatibility helper used by Skill binding code."""
    return normalize_platform(platform)
