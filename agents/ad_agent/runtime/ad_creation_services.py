"""Advertising creation service composition.

The application facade exposes one creation surface, while each concern is
implemented by a focused mixin. None of these services owns the generic Run
Kernel or executes Provider clients directly.
"""

from .ad_creation_blueprint_services import AdCreationBlueprintServicesMixin
from .ad_creation_contract_services import AdCreationContractServicesMixin
from .ad_creation_response_services import AdCreationResponseServicesMixin
from .ad_creation_state_services import AdCreationStateServicesMixin
from .ad_creation_template_services import AdCreationTemplateServicesMixin
from .ad_creation_ui_services import AdCreationUIServicesMixin
from .ad_scheduling_preflight import AdSchedulingPreflightMixin


class AdCreationServicesMixin(
    AdCreationStateServicesMixin,
    AdCreationTemplateServicesMixin,
    AdCreationBlueprintServicesMixin,
    AdCreationUIServicesMixin,
    AdCreationContractServicesMixin,
    AdCreationResponseServicesMixin,
    AdSchedulingPreflightMixin,
):
    """Public advertising creation surface assembled from focused services."""


__all__ = ["AdCreationServicesMixin"]
