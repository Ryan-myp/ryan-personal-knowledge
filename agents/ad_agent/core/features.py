"""Generic Runtime feature contracts.

Features are optional domain extensions. The Runtime discovers and invokes
them through this small protocol, without importing a business workflow or
provider implementation.
"""

from __future__ import annotations

from typing import Any, Protocol


class RuntimeFeature(Protocol):
    """A domain workflow extension owned by a Skill/feature package."""

    feature_name: str

    def can_handle(self, intent: Any) -> bool:
        """Return whether this feature owns the intent/workflow."""

    def is_batch_intent(self, intent: Any) -> bool:
        """Return whether the feature owns a planning-only batch path."""

    def handles_creation_preflight(self, intent: Any) -> bool:
        """Return whether the feature owns creation preflight for the intent."""
