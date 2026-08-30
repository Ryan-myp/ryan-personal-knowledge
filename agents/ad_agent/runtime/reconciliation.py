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
    """Resolve an uncertain write through a provider-owned read Tool.

    The Runtime supplies the selected read Tool's definition. Identity and
    input fields therefore come from Tool metadata/schema, not from channel
    names, resource names, or a fixed list of advertising objects.
    """

    def __init__(self, platform: str, readback_tools: Mapping[str, str] | None = None):
        self.platform = platform
        # This is an optional compatibility seam for providers with an
        # exceptional write->read edge. The mapping is still provider-owned;
        # Runtime never derives it from a Tool name.
        self.readback_tools = dict(readback_tools or {})

    def reconcile(self, context: ReconciliationContext) -> ReconciliationObservation:
        sequence = int(context.item.get("sequence"))
        write_tool = str(context.item.get("tool_name") or "")
        read_tool = self.readback_tools.get(write_tool)
        read_definition = None

        if read_tool and context.resolve_tool:
            try:
                read_definition = context.resolve_tool(read_tool)
            except (KeyError, TypeError):
                read_definition = None
        if not read_tool and context.resolve_read_tool:
            read_definition = context.resolve_read_tool(write_tool)
            if read_definition is not None:
                read_tool = str(getattr(read_definition, "name", read_definition))
        if not read_tool or read_definition is None:
            return self._unknown(
                sequence,
                "no verified read-back Tool metadata is registered for this write Tool",
            )
        if not getattr(read_definition, "is_read_tool", False):
            return self._unknown(sequence, "read-back Tool is not read-only")
        item_platform = str(context.item.get("platform") or "").strip().lower()
        definition_platform = str(
            getattr(read_definition, "platform", "") or ""
        ).strip().lower()
        if item_platform and definition_platform != item_platform:
            return self._unknown(sequence, "read-back Tool belongs to a different platform")
        item_resource = str(context.item.get("resource_type") or "").strip().lower()
        definition_resource = str(
            getattr(read_definition, "resource_type", "") or ""
        ).strip().lower()
        if item_resource and definition_resource != item_resource:
            return self._unknown(sequence, "read-back Tool targets a different resource type")

        read_input, resource_id = self._read_input(read_definition, context.item)
        if not read_input or not resource_id:
            return self._unknown(
                sequence,
                "workflow item has no declared provider resource identity for read-back",
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

        id_field = self._resource_id_field(read_definition)
        resource = self._extract_resource(data, id_field)
        if not resource:
            return self._unknown(sequence, "provider read-back returned no declared resource")
        observed_id = self._resource_id(resource, id_field)
        if not observed_id:
            return self._unknown(
                sequence,
                f"provider read-back returned no value for declared identity field {id_field}",
            )
        if str(observed_id) != str(resource_id):
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
                "provider_resource_id": observed_id,
            },
            provider_resource_id=str(observed_id),
        )

    @classmethod
    def _read_input(
        cls, read_definition: Any, item: Mapping[str, Any]
    ) -> tuple[dict[str, Any], str | None]:
        source: dict[str, Any] = {}
        for key in ("input_data", "output_data"):
            value = item.get(key)
            if isinstance(value, dict):
                source.update(value)
        # account_id is persisted on the workflow item, not necessarily in
        # the original provider payload. It is safe to make it available by
        # its canonical workflow field; provider-specific aliases must still
        # be declared in the read Tool's required/schema fields.
        if item.get("account_id") not in (None, ""):
            source.setdefault("account_id", item.get("account_id"))
        nested = source.get("result")
        if isinstance(nested, dict):
            source.update(nested)

        schema = getattr(read_definition, "input_schema", None)
        properties = getattr(schema, "properties", {}) if schema else {}
        required = list(getattr(schema, "required", []) or []) if schema else []
        id_field = cls._resource_id_field(read_definition)
        parent_field = str(
            getattr(read_definition, "parent_resource_id_field", "") or ""
        ).strip()
        # The persistence layer stores the normalized provider identity at
        # item level as well as inside provider output. Feed that value back
        # through the declared field so a custom handler may return only its
        # normalized result envelope.
        if id_field and source.get(id_field) in (None, ""):
            if item.get("provider_resource_id") not in (None, ""):
                source[id_field] = item.get("provider_resource_id")
        if parent_field and source.get(parent_field) in (None, ""):
            if item.get("parent_resource_id") not in (None, ""):
                source[parent_field] = item.get("parent_resource_id")
        fields = list(dict.fromkeys(
            [str(field) for field in required]
            + ([id_field] if id_field else [])
            + ([parent_field] if parent_field else [])
        ))
        # Only send fields declared by the read Tool. A required provider
        # account alias such as advertiser_id/customer_id is already part of
        # the provider-owned schema and is therefore handled normally.
        declared = set(str(field) for field in properties) if isinstance(properties, dict) else set()
        if declared:
            fields = [field for field in fields if field in declared]
        read_input = {
            field: str(source[field])
            for field in fields
            if source.get(field) not in (None, "")
        }
        return read_input, cls._source_value(source, id_field)

    @staticmethod
    def _resource_id_field(read_definition: Any) -> str:
        return str(getattr(read_definition, "resource_id_field", "") or "").strip()

    @staticmethod
    def _source_value(source: Mapping[str, Any], field: str) -> str | None:
        if not field or source.get(field) in (None, ""):
            return None
        return ToolReadbackReconciler._normalize_identifier(source[field])

    @classmethod
    def _extract_resource(
        cls, data: Mapping[str, Any], id_field: str
    ) -> dict[str, Any]:
        """Find a resource object by the declared identity field."""
        if not id_field:
            return {}
        if id_field in data:
            return dict(data)
        for value in data.values():
            if isinstance(value, dict):
                resource = cls._extract_resource(value, id_field)
                if resource:
                    return resource
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        resource = cls._extract_resource(item, id_field)
                        if resource:
                            return resource
        return {}

    @staticmethod
    def _resource_id(resource: Mapping[str, Any], id_field: str) -> str | None:
        return ToolReadbackReconciler._normalize_identifier(resource.get(id_field))

    @staticmethod
    def _normalize_identifier(value: Any) -> str | None:
        if value in (None, ""):
            return None
        text = str(value)
        return text.rsplit("/", 1)[-1] if "/" in text else text

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
