"""Tool catalog and namespace discovery service for the advertising app."""

from __future__ import annotations

from typing import Any

from ..core.interfaces import ToolDefinition
from .provider_bindings import ProviderBindings


class AdvertisingCatalogService:
    """Keep registry-derived discovery state outside the Run facade."""

    def __init__(self, runtime: Any) -> None:
        self.runtime = runtime

    @staticmethod
    def canonical_platform(platform: str) -> str:
        return ProviderBindings.normalize_namespace(platform)

    def resolve_platform_identifier(self, platform: str) -> str:
        raw = str(platform or "").strip().casefold()
        normalized = self.canonical_platform(raw)
        if not raw:
            return ""
        runtime = self.runtime
        for skill in runtime.skill_loader.list_all().values():
            canonical = self.canonical_platform(
                getattr(skill, "namespace", "")
            )
            aliases = {
                str(getattr(skill, "platform", "") or "").strip().casefold(),
                canonical,
                canonical.replace("-", " "),
            }
            aliases.update(
                str(alias or "").strip().casefold()
                for alias in (getattr(skill, "namespace_aliases", []) or [])
            )
            aliases.update(self.canonical_platform(alias) for alias in list(aliases))
            if raw in aliases or normalized in aliases:
                return canonical
        for definition in runtime.registry.list_all():
            canonical = self.canonical_platform(
                getattr(definition, "namespace", "")
            )
            if normalized == canonical:
                return canonical
        return normalized

    def refresh_parser_catalog(self) -> None:
        runtime = self.runtime
        runtime._context_service().clear()
        definitions = runtime.registry.list_all()
        refresh_catalog = getattr(runtime.intent_parser, "refresh_tool_catalog", None)
        if callable(refresh_catalog):
            refresh_catalog(definitions)
        for feature in runtime.features:
            register_descriptors = getattr(
                runtime.intent_parser,
                "register_intent_descriptors",
                None,
            )
            if callable(register_descriptors):
                register_descriptors(feature.intent_descriptors())
        for skill in list(runtime._skill_objects.values()):
            register_aliases = getattr(
                runtime.intent_parser,
                "register_namespace_aliases",
                None,
            )
            if callable(register_aliases):
                register_aliases(
                    skill.namespace,
                    skill.namespace_aliases or [],
                )

    def on_tool_catalog_changed(self) -> None:
        runtime = self.runtime
        for definition in runtime.registry.list_all():
            runtime.parameter_catalogs.register_tool_schema(
                definition.namespace,
                getattr(definition.input_schema, "properties", {})
                if definition.input_schema
                else {},
                tool_name=definition.name,
            )
        self.refresh_parser_catalog()

    def register_tool(
        self,
        definition: ToolDefinition,
        executor: Any,
        *,
        source_id: str = "local",
    ) -> None:
        runtime = self.runtime
        if isinstance(definition, ToolDefinition):
            runtime.registry.register(definition, executor)
            self.on_tool_catalog_changed()
            return
        runtime._platform_application.register_tool(
            definition,
            executor,
            source_id=source_id,
        )

    def register_tool_source(self, source: Any) -> list[str]:
        runtime = self.runtime
        if callable(getattr(source, "configure", None)):
            return runtime.register_provider_tool_source(source)
        bindings = getattr(source, "list_bindings", None)
        if callable(bindings):
            values = list(bindings())
            if all(
                isinstance(item.definition, ToolDefinition)
                for item in values
            ):
                names = runtime.registry.register_source(source)
                self.on_tool_catalog_changed()
                return names
        return runtime._platform_application.register_tool_source(source)

    def unregister_tool_source(self, source_id: str) -> list[str]:
        runtime = self.runtime
        names = runtime.registry.unregister_source(source_id)
        if names:
            self.on_tool_catalog_changed()
            return names
        return runtime._platform_application.unregister_tool_source(source_id)


__all__ = ["AdvertisingCatalogService"]
