"""Convention-based discovery for optional Runtime features."""

from __future__ import annotations

import importlib
import inspect
import pkgutil

from agents.agent_harness.core.features import RuntimeFeature


def discover_features() -> list[RuntimeFeature]:
    """Discover feature factories/classes without a central business table."""
    package = importlib.import_module(__package__)
    features: list[RuntimeFeature] = []
    for module_info in pkgutil.iter_modules(getattr(package, "__path__", ())):
        if module_info.name.startswith("_") or module_info.name == "factory":
            continue
        module = importlib.import_module(f"{__package__}.{module_info.name}")
        candidates = [
            value for value in vars(module).values()
            if inspect.isclass(value)
            and value.__module__ == module.__name__
            and callable(getattr(value, "can_handle", None))
            and str(getattr(value, "feature_name", "") or "").strip()
        ]
        for candidate in sorted(candidates, key=lambda value: value.__name__):
            feature = candidate()
            if callable(getattr(feature, "can_handle", None)):
                features.append(feature)
    return features
