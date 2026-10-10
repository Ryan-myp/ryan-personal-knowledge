"""Advertising creation service composition.

The application facade exposes one creation surface, while each concern is
implemented by a focused mixin. None of these services owns the generic Run
Kernel or executes Provider clients directly.
"""

from .ad_creation_blueprint_services import AdCreationBlueprintServicesMixin
from .ad_creation_catalog_services import AdCreationCatalogServicesMixin
from .ad_creation_contract_services import AdCreationContractServicesMixin
from .ad_creation_template_services import AdCreationTemplateServicesMixin
from .ad_creation_ui_services import AdCreationUIServicesMixin


class AdCreationServicesMixin(
    AdCreationTemplateServicesMixin,
    AdCreationCatalogServicesMixin,
    AdCreationBlueprintServicesMixin,
    AdCreationUIServicesMixin,
    AdCreationContractServicesMixin,
):
    """Blueprint, template, and schema services for advertising creation."""


__all__ = ["AdCreationServicesMixin"]
