"""Meta Creative capability handlers."""

from typing import Optional

from ...api_clients.meta_client import MetaAPIClient
from ...core.interfaces import ToolContext, ToolHandler, ToolResult


class MetaCreateCreativeHandler(ToolHandler):
    """Create a Meta Creative when an explicitly approved live path exists.

    The normal Runtime intercepts this write in dry-run mode.  Keeping the
    provider call in a dedicated handler makes the capability extensible and
    allows later white-listed adapter verification without changing routing.
    """

    def __init__(self, api_client: Optional[MetaAPIClient] = None):
        self.client = api_client

    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        if not self.client or not ctx.account_id:
            return ToolResult.error("Meta client not configured or account_id missing")
        try:
            creative_id = self.client.create_creative(
                ctx.account_id,
                {
                    key: value
                    for key, value in input_data.items()
                    if key != "account_id"
                },
            )
            return ToolResult.ok({
                "creative_id": creative_id,
                "name": input_data.get("name"),
            })
        except Exception as exc:
            return ToolResult.error(f"Failed to create Meta creative: {exc}")


class MetaLookupCreativeHandler(ToolHandler):
    """Resolve one Creative into the Runtime's provider-selection catalog.

    Account Creative edges can be large and a newly-created object may not be
    on their first page.  The handler intentionally wraps the exact object in
    a one-item list because lookup catalogs are list-shaped and the Runtime
    will mint the context-bound selection token.
    """

    def __init__(self, api_client: Optional[MetaAPIClient] = None):
        self.client = api_client

    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        creative_id = input_data.get("creative_id")
        if self.client and ctx.account_id and creative_id:
            try:
                # MetaAPIClient.get_creative performs the account-ownership
                # check as part of the exact read. Avoid a second Graph call
                # here; replaceable clients keep ownership responsibility in
                # their own adapter contract.
                creative = self.client.get_creative(
                    ctx.account_id,
                    creative_id,
                    fields=input_data.get("fields"),
                )
                return ToolResult.ok({
                    "creatives": [creative],
                    "creative": creative,
                    "data_status": "live",
                })
            except Exception as exc:
                return ToolResult.error(f"Failed to lookup Meta creative: {exc}")
        return ToolResult.ok({
            "creatives": [],
            "account_id": ctx.account_id,
            "data_status": "offline_no_client",
            "simulated": True,
        })
