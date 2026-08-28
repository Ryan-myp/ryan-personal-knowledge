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
from typing import Any, Optional
from ..core.platform import normalize_platform, platform_slug


def _module_slug(platform: str) -> str:
    return platform_slug(platform)


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
    # Built-in and lightweight provider clients may expose exactly one client
    # class without a factory function. Keep the package convention useful
    # without adding another central provider map; ambiguous modules must
    # publish an explicit ``create_<platform>_client`` factory.
    classes = [
        value for value in vars(module).values()
        if inspect.isclass(value)
        and value.__module__ == module.__name__
        and value.__name__.lower().endswith("client")
    ]
    if len(classes) == 1:
        return lambda credentials, client_class=classes[0]: client_class(credentials)
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
    return None
