"""Provider read-back reconcilers for uncertain workflow outcomes."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from ..core.interfaces import (
    ProviderReconciler,
    ReconciliationContext,
    ReconciliationObservation,
)


READBACK_TOOLS: dict[str, dict[str, str]] = {
    "meta": {
        "meta_create_campaign": "meta_get_campaign",
        "meta_update_campaign": "meta_get_campaign",
        "meta_create_adset": "meta_get_adset",
        "meta_update_adset": "meta_get_adset",
        "meta_create_ad": "meta_get_ad",
        "meta_update_ad": "meta_get_ad",
    },
    "google-ads": {
        "google_create_campaign": "google_get_campaign",
        "google_update_campaign": "google_get_campaign",
        "google_create_ad_group": "google_get_ad_group",
        "google_update_ad_group": "google_get_ad_group",
        "google_create_ad": "google_get_ad",
        "google_update_ad": "google_get_ad",
    },
    "tiktok": {
        "tiktok_create_campaign": "tiktok_get_campaign",
        "tiktok_update_campaign": "tiktok_get_campaign",
        "tiktok_create_adgroup": "tiktok_get_adgroup",
        "tiktok_update_adgroup": "tiktok_get_adgroup",
        "tiktok_create_ad": "tiktok_get_ad",
        "tiktok_update_ad": "tiktok_get_ad",
    },
    "dv360": {
        "dv360_create_campaign": "dv360_get_campaign",
        "dv360_update_campaign": "dv360_get_campaign",
        "dv360_create_io": "dv360_get_io",
        "dv360_update_io": "dv360_get_io",
        "dv360_create_line_item": "dv360_get_line_item",
        "dv360_update_line_item": "dv360_get_line_item",
    },
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ToolReadbackReconciler(ProviderReconciler):
    """Resolve a write by invoking the provider's read-only tool.

    The mapping is provider-owned data. The shared Runtime only supplies the
    callback, so the read-back still passes through normal schema, account,
    permission, timeout and client boundaries.
    """

    def __init__(self, platform: str, readback_tools: Mapping[str, str] | None = None):
        self.platform = platform
        self.readback_tools = dict(readback_tools or READBACK_TOOLS.get(platform, {}))

    def reconcile(self, context: ReconciliationContext) -> ReconciliationObservation:
        sequence = int(context.item.get("sequence"))
        write_tool = str(context.item.get("tool_name") or "")
        read_tool = self.readback_tools.get(write_tool)
        if not read_tool:
            return self._unknown(
                sequence,
                "no verified read-back tool is registered for this write tool",
            )

        read_input, resource_id = self._read_input(read_tool, context.item)
        if not read_input:
            return self._unknown(
                sequence,
                "workflow item has no provider resource identity for read-back",
            )
        try:
            result = context.execute_read(read_tool, read_input)
        except Exception as exc:
            return self._unknown(sequence, f"provider read-back failed: {exc}")

        data = result.data if isinstance(result.data, dict) else {}
        if (
            not result.success
            or result.simulated
            or data.get("simulated") is True
            or str(data.get("data_status") or "").startswith("offline")
        ):
            return self._unknown(
                sequence,
                result.error or "provider read-back did not return live data",
            )

        resource = self._extract_resource(data)
        if not resource:
            return self._unknown(sequence, "provider read-back returned no resource")
        observed_id = self._resource_id(resource)
        if resource_id and observed_id and str(observed_id) != str(resource_id):
            return self._unknown(
                sequence,
                "provider read-back resource identity did not match the workflow item",
            )
        return ReconciliationObservation(
            sequence=sequence,
            status="succeeded",
            verified=True,
            source=f"provider_readback:{read_tool}",
            observed_at=_now(),
            output_data={
                "read_tool": read_tool,
                "resource": resource,
                "provider_resource_id": observed_id or resource_id,
            },
            provider_resource_id=str(observed_id or resource_id or "") or None,
        )

    @staticmethod
    def _read_input(read_tool: str, item: Mapping[str, Any]) -> tuple[dict[str, Any], str | None]:
        source: dict[str, Any] = {}
        for key in ("input_data", "output_data"):
            value = item.get(key)
            if isinstance(value, dict):
                source.update(value)
        nested = source.get("result")
        if isinstance(nested, dict):
            source.update(nested)

        resource_key = {
            "meta_get_campaign": "campaign_id",
            "meta_get_adset": "adset_id",
            "meta_get_ad": "ad_id",
            "google_get_campaign": "campaign_id",
            "google_get_ad_group": "ad_group_id",
            "google_get_ad": "ad_id",
            "tiktok_get_campaign": "campaign_id",
            "tiktok_get_adgroup": "adgroup_id",
            "tiktok_get_ad": "ad_id",
            "dv360_get_campaign": "campaign_id",
            "dv360_get_io": "io_id",
            "dv360_get_line_item": "line_item_id",
        }.get(read_tool)
        resource_id = source.get(resource_key) if resource_key else None
        if resource_id is None:
            resource_id = source.get("resource_id") or source.get("id")
        if resource_id is not None:
            return {resource_key or "resource_id": str(resource_id)}, str(resource_id)
        if read_tool.endswith("get_campaign") and source.get("name"):
            return {"campaign_name": source["name"]}, None
        return {}, None

    @staticmethod
    def _extract_resource(data: Mapping[str, Any]) -> dict[str, Any]:
        for key in ("campaign", "adset", "ad_group", "ad", "io", "line_item"):
            resource = data.get(key)
            if isinstance(resource, dict) and resource:
                return resource
        return data if data.get("id") or data.get("resourceName") else {}

    @staticmethod
    def _resource_id(resource: Mapping[str, Any]) -> str | None:
        for key in ("id", "campaign_id", "campaignId", "adset_id", "ad_group_id", "adGroupId", "ad_id", "adId", "io_id", "line_item_id", "resourceName", "name"):
            if resource.get(key) is not None:
                value = str(resource[key])
                return value.split("/")[-1] if "/" in value else value
        return None

    @staticmethod
    def _unknown(sequence: int, error: str) -> ReconciliationObservation:
        return ReconciliationObservation(
            sequence=sequence,
            status="unknown",
            verified=True,
            source="provider_readback",
            observed_at=_now(),
            error=error,
        )
