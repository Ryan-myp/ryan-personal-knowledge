"""Provider parameter option catalogs.

The Runtime should not own Meta/Google/TikTok/DV360 enum tables.  A Skill can
publish a static catalog for values that are fixed by the provider contract,
or a lookup descriptor for values that depend on an account or campaign.
This module gives both cases one JSON-safe interface for UI, LLM context and
future provider-backed resolvers.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import threading
from typing import Any, Optional
from .platform import normalize_platform


@dataclass(frozen=True)
class ParameterOption:
    value: Any
    label: str = ""
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        result = {"value": self.value, "label": self.label or str(self.value)}
        if self.description:
            result["description"] = self.description
        return result


@dataclass(frozen=True)
class ParameterCatalog:
    """A Skill-owned parameter catalog.

    ``source`` is either ``static``/``tool_schema`` or ``lookup``.  Dynamic
    catalogs intentionally return a descriptor rather than making network
    calls from the schema endpoint.
    """

    platform: str
    field: str
    options: tuple[ParameterOption, ...] = ()
    source: str = "static"
    version: str = "1"
    lookup_tool: Optional[str] = None
    description: str = ""
    tool_name: Optional[str] = None
    # Provider-owned lookup UX metadata.  These are data contracts only: the
    # Runtime still validates the source Tool and builds its input from the
    # declared schema before executing it.
    account_required: Optional[bool] = None
    dependencies: tuple[dict[str, Any], ...] = ()
    manual_entry: Optional[dict[str, Any]] = None
    query_field: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        result = {
            "platform": self.platform,
            "field": self.field,
            "source": self.source,
            "version": self.version,
            "dynamic": self.source == "lookup",
            "options": [option.to_dict() for option in self.options],
        }
        if self.tool_name:
            result["tool_name"] = self.tool_name
        if self.lookup_tool:
            result["lookup_tool"] = self.lookup_tool
            if self.account_required is not None:
                result["account_required"] = bool(self.account_required)
            if self.dependencies:
                result["dependencies"] = [dict(item) for item in self.dependencies]
            if self.manual_entry:
                result["manual_entry"] = dict(self.manual_entry)
            if self.query_field:
                result["query_field"] = self.query_field
        if self.description:
            result["description"] = self.description
        return result


class ParameterCatalogRegistry:
    """Thread-safe-by-construction registry owned by one Runtime.

    Registration is deterministic: later Skill registrations replace a
    catalog with the same ``(platform, tool, field)`` key, which keeps
    same-named fields at different resource levels from overwriting one
    another.
    """

    def __init__(self) -> None:
        self._catalogs: dict[tuple[str, str, Optional[str]], ParameterCatalog] = {}
        self._lock = threading.RLock()

    @staticmethod
    def _normalize_platform(platform: str) -> str:
        return normalize_platform(platform)

    def register(self, catalog: ParameterCatalog) -> None:
        if not isinstance(catalog, ParameterCatalog):
            raise TypeError("parameter catalog must be a ParameterCatalog")
        platform = self._normalize_platform(catalog.platform)
        if not platform or not catalog.field:
            raise ValueError("parameter catalog requires platform and field")
        if catalog.source == "lookup" and not catalog.lookup_tool:
            raise ValueError("lookup catalog requires lookup_tool")
        with self._lock:
            tool_name = str(catalog.tool_name) if catalog.tool_name else None
            self._catalogs[(platform, str(catalog.field), tool_name)] = ParameterCatalog(
                platform=platform,
                field=str(catalog.field),
                options=tuple(catalog.options),
                source=catalog.source,
                version=str(catalog.version),
                lookup_tool=catalog.lookup_tool,
                description=catalog.description,
                account_required=catalog.account_required,
                dependencies=tuple(dict(item) for item in catalog.dependencies),
                manual_entry=(
                    dict(catalog.manual_entry)
                    if catalog.manual_entry is not None else None
                ),
                query_field=catalog.query_field,
                tool_name=tool_name,
            )

    def register_many(self, catalogs: list[ParameterCatalog] | tuple[ParameterCatalog, ...]) -> None:
        for catalog in catalogs or ():
            self.register(catalog)

    def remove_tools(self, tool_names: list[str] | tuple[str, ...] | set[str]) -> None:
        """Remove catalogs published by Tools that are no longer registered."""
        names = {str(name) for name in (tool_names or ())}
        if not names:
            return
        with self._lock:
            self._catalogs = {
                key: catalog
                for key, catalog in self._catalogs.items()
                if catalog.tool_name not in names
            }

    def register_tool_schema(
        self, platform: str, properties: dict[str, Any],
        tool_name: Optional[str] = None,
    ) -> None:
        """Derive static catalogs from a ToolSchema enum.

        This makes existing provider Capabilities discoverable immediately;
        a Skill can later replace the generated catalog with richer labels or
        a versioned provider catalog.
        """
        normalized = self._normalize_platform(platform)

        def register_spec(field: str, spec: Any) -> None:
            if not isinstance(spec, dict):
                return
            enum = spec.get("enum")
            items = spec.get("items")
            # Expose array item enums under the array field itself so callers
            # can ask for ``operating_systems`` without knowing the JSON
            # Schema spelling ``items.enum``.
            if enum is None and isinstance(items, dict):
                enum = items.get("enum")
            if enum is not None:
                labels = spec.get("option_labels") or {}
                self.register(
                    ParameterCatalog(
                        platform=normalized,
                        field=str(field),
                        options=tuple(
                            ParameterOption(
                                value=item,
                                label=str(labels.get(str(item), item))
                                if isinstance(labels, dict) else str(item),
                            )
                            for item in enum
                        ),
                        source="tool_schema",
                        version=str(spec.get("version", "schema")),
                        description=str(spec.get("description", "")),
                        tool_name=tool_name,
                    )
                )
            lookup_tool = spec.get("lookup_tool")
            if not lookup_tool and isinstance(spec.get("lookup"), dict):
                lookup_tool = spec["lookup"].get("tool")
            if lookup_tool:
                self.register(
                    ParameterCatalog(
                        platform=normalized,
                        field=str(field),
                        source="lookup",
                        version=str(spec.get("version", "provider")),
                        lookup_tool=str(lookup_tool),
                        description=str(spec.get("description", "")),
                        account_required=spec.get("lookup_account_required"),
                        dependencies=tuple(
                            dict(item) for item in (spec.get("lookup_dependencies") or [])
                            if isinstance(item, dict)
                        ),
                        manual_entry=(
                            dict(spec["manual_entry"])
                            if isinstance(spec.get("manual_entry"), dict) else None
                        ),
                        query_field=(
                            str(spec["lookup_query_field"])
                            if spec.get("lookup_query_field") else None
                        ),
                        tool_name=tool_name,
                    )
                )
            for child, child_spec in (spec.get("properties") or {}).items():
                register_spec(f"{field}.{child}", child_spec)

        for field, spec in (properties or {}).items():
            register_spec(str(field), spec)

    def get(
        self, platform: str, field: str, tool_name: Optional[str] = None,
    ) -> Optional[ParameterCatalog]:
        with self._lock:
            normalized = self._normalize_platform(platform)
            if tool_name is not None:
                return self._catalogs.get((normalized, str(field), str(tool_name)))
            matches = [catalog for (item_platform, item_field, _), catalog in self._catalogs.items()
                       if item_platform == normalized and item_field == str(field)]
            return matches[0] if len(matches) == 1 else None

    def list(
        self, platform: Optional[str] = None, field: Optional[str] = None,
        tool_name: Optional[str] = None,
    ) -> list[ParameterCatalog]:
        with self._lock:
            normalized = self._normalize_platform(platform) if platform is not None else None
            return [
                catalog for (item_platform, item_field, item_tool), catalog
                in self._catalogs.items()
                if (normalized is None or item_platform == normalized)
                and (field is None or item_field == str(field))
                and (tool_name is None or item_tool == str(tool_name))
            ]

    def to_dict(
        self, platform: Optional[str] = None, field: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        return [catalog.to_dict() for catalog in self.list(platform, field)]


def now_utc_iso() -> str:
    """Small shared helper for future cache/expiry metadata."""
    return datetime.now(timezone.utc).isoformat()
