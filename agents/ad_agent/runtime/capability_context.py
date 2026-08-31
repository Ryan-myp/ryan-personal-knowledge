"""Capability configuration context."""

from __future__ import annotations

from typing import Any

from ..core.interfaces import Skill, ToolRegistry


class CapabilityContextWrapper:
    """Small adapter passed to Capability.configure()."""

    def __init__(self, registry: ToolRegistry):
        self.registry = registry
        self.skills: dict[str, Skill] = {}
        self.config: dict[str, Any] = {}

    def register_skill(self, skill: Skill) -> None:
        self.skills[skill.name] = skill
