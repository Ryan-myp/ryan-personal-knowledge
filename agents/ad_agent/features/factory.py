"""Convention-based discovery for optional Runtime features."""

from __future__ import annotations

import importlib
import inspect
import pkgutil
from typing import Any

from ..core.features import RuntimeFeature


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


def feature_for_intent(
    features: list[RuntimeFeature],
    intent: Any,
) -> RuntimeFeature | None:
    """Resolve one feature; ambiguity remains a configuration error."""
    matches = [
        feature for feature in features
        if bool(feature.can_handle(intent))
    ]
    return matches[0] if len(matches) == 1 else None


def discover_response_renderer() -> Any:
    """Discover the application response renderer by package convention."""
    package = importlib.import_module(__package__)
    candidates: list[type] = []
    for module_info in pkgutil.iter_modules(getattr(package, "__path__", ())):
        if module_info.name.startswith("_") or module_info.name == "factory":
            continue
        module = importlib.import_module(f"{__package__}.{module_info.name}")
        candidates.extend(
            value for value in vars(module).values()
            if inspect.isclass(value)
            and value.__module__ == module.__name__
            and str(getattr(value, "renderer_name", "") or "").strip()
            and callable(getattr(value, "render", None))
            and callable(getattr(value, "render_chat", None))
        )
    if len(candidates) != 1:
        return None
    return candidates[0]()
