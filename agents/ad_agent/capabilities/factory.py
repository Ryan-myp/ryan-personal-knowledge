"""Canonical Capability construction for the ad-agent runtime.

The runtime used to keep a second namespace-to-module map in addition to the
public capability factories.  That made dynamic Skill loading subtly
different from the CLI/API registration path.  This module is the single
construction seam for namespace capabilities; it only constructs Python
objects and never performs network I/O.
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
from typing import Any, Optional
from ..core.namespace import normalize_namespace as normalize_namespace, namespace_slug


def _module_slug(namespace: str) -> str:
    """Convert a namespace identifier into its package/module spelling."""
    return namespace_slug(namespace)


def _discover_noncanonical_module(canonical: str):
    """Find a provider package by its declared identity, not a central map."""
    package = importlib.import_module(__package__)
    for module_info in pkgutil.iter_modules(getattr(package, "__path__", ())):
        if not module_info.ispkg or module_info.name.startswith("_"):
            continue
        module_name = f"{__package__}.{module_info.name}.capability"
        try:
            module = importlib.import_module(module_name)
        except ModuleNotFoundError as exc:
            if exc.name in {module_name, module_name.rsplit(".", 1)[0]}:
                continue
            raise
        if not any(
            inspect.isclass(value)
            and normalize_namespace(getattr(value, "platform_name", "")) == canonical
            for value in vars(module).values()
        ):
            continue
        factories = sorted(
            value for name, value in vars(module).items()
            if name.startswith("create_")
            and name.endswith("_capability")
            and callable(value)
        )
        if factories:
            return factories[0]
    return None


def discover_capability_factory(namespace: str):
    """Find a Capability factory by package convention.

    A provider package owns its executable surface.  The shared runtime first
    tries the conventional package/factory name, then discovers a package
    whose Capability declares the requested namespace identity.
    """
    canonical = normalize_namespace(namespace)
    slug = _module_slug(canonical)
    module_name = f"{__package__}.{slug}.capability"
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        # A missing provider module means the channel is not installed. Do not
        # hide a dependency failure raised from inside an installed provider.
        missing_names = {module_name, module_name.rsplit(".", 1)[0]}
        if exc.name in missing_names:
            return _discover_noncanonical_module(canonical)
        raise

    candidates = [f"create_{slug}_capability"]
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


def create_capability(namespace: str, api_client: Optional[Any] = None):
    """Create a namespace Capability through its public factory.

    ``api_client`` is injected as-is.  Capability construction is deliberately
    side-effect free; a handler may perform network I/O only when Runtime
    executes a read tool or an explicitly approved live write.
    """
    canonical = normalize_namespace(namespace)
    factory = discover_capability_factory(canonical)
    if not callable(factory):
        raise ValueError(
            f"Unsupported ad namespace '{namespace}'. "
            "Add capabilities/<namespace>/capability.py with a "
            "create_<namespace>_capability factory."
        )
    return factory(api_client)
