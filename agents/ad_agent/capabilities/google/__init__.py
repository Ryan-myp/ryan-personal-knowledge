"""
capabilities/google/__init__.py
"""
from .campaigns import (
    GoogleListCampaignsHandler,
    GoogleGetCampaignHandler,
    GoogleCreateCampaignHandler,
)
from .ad_groups import (
    GoogleListAdGroupsHandler,
    GoogleGetAdGroupHandler,
    GoogleCreateAdGroupHandler,
)
from .ads import (
    GoogleListAdsHandler,
    GoogleGetAdHandler,
    GoogleCreateAdHandler,
)
from .assets import (
    GoogleListAssetGroupsHandler,
    GoogleGetAssetGroupHandler,
)
from .reports import GoogleGetReportHandler
from .keywords import GoogleListKeywordsHandler
from .capability import GoogleCapability, create_google_capability

__all__ = [
    "GoogleCapability",
    "GoogleListCampaignsHandler",
    "GoogleGetCampaignHandler",
    "GoogleCreateCampaignHandler",
    "GoogleListAdGroupsHandler",
    "GoogleGetAdGroupHandler",
    "GoogleCreateAdGroupHandler",
    "GoogleListAdsHandler",
    "GoogleGetAdHandler",
    "GoogleCreateAdHandler",
    "GoogleListAssetGroupsHandler",
    "GoogleGetAssetGroupHandler",
    "GoogleGetReportHandler",
    "GoogleListKeywordsHandler",
]
