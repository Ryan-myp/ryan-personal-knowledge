"""DV360 API surface and provider-owned official inventory."""

from ..api_surface import materialize_inventory, materialize_surface
from ._surface_data import API_SURFACE as _API_SURFACE
from ._surface_data import OFFICIAL_INVENTORY, PROVIDER_METADATA

API_SURFACE = materialize_surface(_API_SURFACE, PROVIDER_METADATA)
OFFICIAL_INVENTORY = materialize_inventory(OFFICIAL_INVENTORY, PROVIDER_METADATA)

__all__ = ["API_SURFACE", "OFFICIAL_INVENTORY", "PROVIDER_METADATA"]
