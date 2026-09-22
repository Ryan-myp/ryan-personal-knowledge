"""Advertising scenario application assembled on the generic Agent Platform."""

from __future__ import annotations

from typing import Any

from agents.agent_platform import PlatformApplication

from .runtime.ad_application import AdvertisingComposition as _AdvertisingComposition


class AdvertisingApplication:
    """Application boundary for the advertising scenario.

    The composition object is an internal provider/data assembly. Run
    lifecycle, transcript, Tool loop and policy execution are owned by the
    ``PlatformApplication`` created during that assembly.
    """

    def __init__(self, **options: Any) -> None:
        composition = _AdvertisingComposition(**options)
        platform = getattr(composition, "_platform_application", None)
        if not isinstance(platform, PlatformApplication):
            composition.close(wait=True)
            raise RuntimeError("advertising application was not assembled by AgentPlatform")
        self._composition = composition
        self.platform: PlatformApplication = platform

    @property
    def application(self) -> PlatformApplication:
        return self.platform

    def run(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return self._composition.run(*args, **kwargs)

    def close(self, wait: bool = False) -> None:
        self._composition.close(wait=wait)

    def __getattr__(self, name: str) -> Any:
        # Management APIs (knowledge, tasks, schedules and monitoring) are
        # application services, while turn execution stays on ``platform``.
        return getattr(self._composition, name)


def create_advertising_application(**options: Any) -> AdvertisingApplication:
    """Create the advertising scenario through the generic platform assembly."""
    return AdvertisingApplication(**options)


__all__ = ["AdvertisingApplication", "create_advertising_application"]
