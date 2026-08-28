"""Provider read-back reconcilers for uncertain workflow outcomes."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, Optional

from ..core.interfaces import (
    ProviderReconciler,
    ReconciliationContext,
    ReconciliationObservation,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ToolReadbackReconciler(ProviderReconciler):
    """Resolve a write by invoking the provider's read-only tool.

    A provider may pass an explicit mapping for an exceptional API contract.
    Otherwise Runtime resolves the matching read Tool from registered
    metadata, so adding a provider does not require a shared channel table.
    """

    def __init__(self, platform: str, readback_tools: Mapping[str, str] | None = None):
        self.platform = platform
        self.readback_tools = dict(readback_tools or {})

    def reconcile(self, context: ReconciliationContext) -> ReconciliationObservation:
        sequence = int(context.item.get("sequence"))
        write_tool = str(context.item.get("tool_name") or "")
        read_tool = self.readback_tools.get(write_tool)
        read_definition = None
        if not read_tool and context.resolve_read_tool:
            read_definition = context.resolve_read_tool(write_tool)
            if read_definition is not None:
                read_tool = str(getattr(read_definition, "name", read_definition))
        if not read_tool:
            return self._unknown(
                sequence,
                "no verified read-back tool is registered for this write tool",
            )

        read_input, resource_id = self._read_input(
            read_tool,
            context.item,
            getattr(getattr(read_definition, "input_schema", None), "properties", None),
            getattr(getattr(read_definition, "input_schema", None), "required", None),
        )
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
    def _read_input(
        read_tool: str,
        item: Mapping[str, Any],
        properties: Optional[Mapping[str, Any]] = None,
        required: Optional[list[str]] = None,
    ) -> tuple[dict[str, Any], str | None]:
        source: dict[str, Any] = {}
        for key in ("input_data", "output_data"):
            value = item.get(key)
            if isinstance(value, dict):
                source.update(value)
        nested = source.get("result")
        if isinstance(nested, dict):
            source.update(nested)

        fields = list(properties or {})
        if not fields:
            suffix = read_tool.rsplit("_get_", 1)[-1]
            fields = [f"{suffix}_id"]
        required_fields = list(required or [])
        identifier_fields = [field for field in fields if str(field).endswith("_id")]
        ordered_fields = list(dict.fromkeys(required_fields + identifier_fields))
        read_input: dict[str, Any] = {}
        for field in ordered_fields:
            value = ToolReadbackReconciler._find_source_value(
                source,
                field,
                generic_fallback=not properties or len(identifier_fields) == 1,
            )
            if value is not None:
                read_input[field] = str(value)
        if read_input:
            resource_id = ToolReadbackReconciler._resource_id_for_tool(
                read_tool, read_input
            )
            return read_input, resource_id
        if read_tool.endswith("get_campaign") and source.get("name"):
            return {"campaign_name": source["name"]}, None
        return {}, None

    @staticmethod
    def _find_source_value(
        source: Mapping[str, Any], field: str, *, generic_fallback: bool = True,
    ) -> Any:
        if source.get(field) is not None:
            return source[field]
        normalized = str(field).replace("_", "").lower()
        for key, value in source.items():
            if str(key).replace("_", "").lower() == normalized and value is not None:
                return value
        if generic_fallback and field.endswith("_id"):
            return source.get("resource_id") or source.get("id")
        return None

    @staticmethod
    def _resource_id_for_tool(read_tool: str, values: Mapping[str, Any]) -> str | None:
        suffix = read_tool.rsplit("_get_", 1)[-1].replace("_", "").lower()
        candidates = [
            (key, value) for key, value in values.items()
            if str(key).replace("_", "").lower().endswith(suffix + "id")
        ]
        if candidates:
            return str(candidates[0][1])
        return next((str(value) for value in values.values() if value is not None), None)

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
