"""Advertising Tool Source lifecycle composition.

Provider registration, Skill lifecycle, plugin verification, credential
binding, and directory discovery are separate application services. The
generic Agent Runtime still receives one already assembled Tool registry.
"""

from .ad_provider_runtime_services import AdProviderRuntimeServicesMixin
from .ad_skill_discovery import AdSkillDiscoveryMixin
from .ad_skill_lifecycle import AdSkillLifecycleMixin
from .ad_skill_plugins import AdSkillPluginMixin
from .ad_tool_source_registration import AdToolSourceRegistrationMixin


class AdToolSourceLifecycleMixin(
    AdToolSourceRegistrationMixin,
    AdSkillLifecycleMixin,
    AdSkillPluginMixin,
    AdProviderRuntimeServicesMixin,
    AdSkillDiscoveryMixin,
):
    """Public Tool Source and Skill lifecycle surface."""


__all__ = ["AdToolSourceLifecycleMixin"]
