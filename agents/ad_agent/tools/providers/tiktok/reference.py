"""TikTok reference-data and conversion query handlers."""

import inspect
from typing import Optional

from ....api_clients.tiktok_client import TikTokAPIClient
from ....core.interfaces import ToolContext, ToolHandler, ToolResult


class _TikTokReferenceHandler(ToolHandler):
    def __init__(self, api_client: Optional[TikTokAPIClient], method_name: str, result_key: str):
        self.client = api_client
        self.method_name = method_name
        self.result_key = result_key

    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        if self.client:
            try:
                method = getattr(self.client, self.method_name)
                if self.method_name in {"list_conversions", "list_catalogs"}:
                    value = method(
                        ctx.account_id,
                        filtering=input_data.get("filtering"),
                        page_size=input_data.get("limit", 20),
                    )
                elif self.method_name == "list_locations":
                    value = method(location_type=input_data.get("location_type"))
                elif self.method_name == "list_regions":
                    value = method(
                        ctx.account_id,
                        placements=input_data["placements"],
                        objective_type=input_data["objective_type"],
                        promotion_target_type=input_data.get("promotion_target_type"),
                        operating_system=input_data.get("operating_system"),
                        brand_safety_type=input_data.get("brand_safety_type"),
                        brand_safety_partner=input_data.get("brand_safety_partner"),
                        level_range=input_data.get("level_range"),
                        rf_campaign_type=input_data.get("rf_campaign_type"),
                    )
                elif self.method_name == "list_apps":
                    # App lookup is explicitly portable: the provider client
                    # may use an advertiser ID from trusted credentials, while
                    # lightweight injected clients often expose only the
                    # documented filtering/page_size arguments.  Select the
                    # compatible call shape without catching a provider
                    # TypeError raised from inside the method.
                    kwargs = {
                        "filtering": input_data.get("filtering"),
                        "page_size": input_data.get("limit", 20),
                    }
                    try:
                        inspect.signature(method).bind(
                            advertiser_id=ctx.account_id, **kwargs
                        )
                    except (TypeError, ValueError):
                        value = method(**kwargs)
                    else:
                        value = method(advertiser_id=ctx.account_id, **kwargs)
                else:
                    value = method()
                return ToolResult.ok({self.result_key: value, "data_status": "live"})
            except Exception as exc:
                return ToolResult.error(f"Failed to query TikTok {self.result_key}: {exc}")
        return ToolResult.ok({
            self.result_key: [],
            "data_status": "offline_no_client",
            "simulated": True,
        })


class TikTokListConversionsHandler(_TikTokReferenceHandler):
    def __init__(self, api_client: Optional[TikTokAPIClient] = None):
        super().__init__(api_client, "list_conversions", "conversions")


class TikTokListLocationsHandler(_TikTokReferenceHandler):
    def __init__(self, api_client: Optional[TikTokAPIClient] = None):
        super().__init__(api_client, "list_locations", "locations")


class TikTokListDevicesHandler(_TikTokReferenceHandler):
    def __init__(self, api_client: Optional[TikTokAPIClient] = None):
        super().__init__(api_client, "list_devices", "devices")


class TikTokListCatalogsHandler(_TikTokReferenceHandler):
    def __init__(self, api_client: Optional[TikTokAPIClient] = None):
        super().__init__(api_client, "list_catalogs", "catalogs")


class TikTokListAppsHandler(_TikTokReferenceHandler):
    def __init__(self, api_client: Optional[TikTokAPIClient] = None):
        super().__init__(api_client, "list_apps", "apps")


class TikTokListBrandSafetyHandler(_TikTokReferenceHandler):
    def __init__(self, api_client: Optional[TikTokAPIClient] = None):
        super().__init__(api_client, "list_brand_safety", "brand_safety")
