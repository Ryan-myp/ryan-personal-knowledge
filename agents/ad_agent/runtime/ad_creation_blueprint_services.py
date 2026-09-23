"""Blueprint resolution and cascade evaluation services for advertising."""

from __future__ import annotations

import logging
from typing import Any, Iterable, Mapping, Optional

from ..core.intent import SimpleIntentRouter
from ..core.interfaces import ParsedIntent
from ..domain.ad.blueprint import _schema_at_path

logger = logging.getLogger(__name__)


class AdCreationBlueprintServicesMixin:
    def resolve_creation_blueprint(
        self,
        provider: str,
        *,
        selector_values: Optional[Mapping[str, Any]] = None,
        values: Optional[Mapping[str, Any]] = None,
        version: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        """Resolve provider-owned creation metadata from declarative selectors."""
        blueprint = self.creation_blueprints.resolve(
            provider,
            selector_values=selector_values,
            values=values,
            version=version,
        )
        return (
            self.creation_card_builder.expand_blueprint(blueprint).to_dict()
            if blueprint is not None else None
        )

    def evaluate_creation_blueprint(
        self,
        blueprint_id: str,
        values: Mapping[str, Any],
        *,
        version: Optional[str] = None,
        previous_values: Optional[Mapping[str, Any]] = None,
        changed_fields: Optional[Iterable[str]] = None,
    ) -> dict[str, Any]:
        """Evaluate cascade state for a registered Blueprint deterministically."""
        blueprint = self.creation_blueprints.get(blueprint_id, version)
        if blueprint is None:
            raise KeyError(
                f"creation blueprint not found: {blueprint_id}@{version or 'latest'}"
            )
        blueprint = self.creation_card_builder.expand_blueprint(blueprint)
        option_sources: dict[str, list[Any]] = {}
        for field in blueprint.fields:
            tool_name, schema_path = str(field["tool_ref"]).split(".", 1)
            try:
                definition, _handler = self._get_registered_tool(tool_name)
            except (KeyError, LookupError, ValueError):
                continue
            properties = getattr(
                getattr(definition, "input_schema", None), "properties", {}
            ) or {}
            schema = _schema_at_path(properties, schema_path) or {}
            enum = schema.get("enum") if isinstance(schema, Mapping) else None
            if (
                not isinstance(enum, list)
                and isinstance(schema, Mapping)
                and isinstance(schema.get("items"), Mapping)
            ):
                enum = schema["items"].get("enum")
            if isinstance(enum, list):
                option_sources[str(field["path"])] = list(enum)
        return self.blueprint_cascade.evaluate(
            blueprint,
            values,
            previous_values=previous_values,
            changed_fields=changed_fields,
            option_sources=option_sources,
        )

    def build_creation_ui(
        self,
        intent: ParsedIntent,
        tool_plan: Optional[Mapping[str, Any]] = None,
        *,
        account_scope: Any = None,
        tenant_id: str = "default",
        user_id: str = "anonymous",
        account_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Build safe conversational creation cards without executing Tools."""
        try:
            cards = self.creation_card_builder.build(
                intent,
                tool_plan=tool_plan,
                account_scope=account_scope,
                tenant_id=tenant_id,
                user_id=user_id,
                account_id=account_id,
            )
        except Exception:
            logger.exception("构建广告创建参数卡失败")
            cards = []
        if not cards:
            return {}
        return self._redact_for_persistence({
            "cards": cards,
            "schema_version": "1.0",
            "needs_input": any(
                bool(
                    card.get("missing_fields")
                    or card.get("invalid_fields")
                    or (
                        card.get("account_required")
                        and not str(card.get("account_id") or "").strip()
                    )
                )
                for card in cards
            ),
        })

    @staticmethod
    def _is_campaign_only_plan(
        tool_plan: Optional[Mapping[str, Any]],
        intent: Optional[Any] = None,
    ) -> bool:
        """Return whether a provider-declared plan contains only Campaign."""
        tools = [
            tool
            for routed in (tool_plan or {}).values()
            for tool in (routed or ())
        ]
        intent_type = str(getattr(intent, "intent_type", "") or "").strip()
        explicit_scope = any(
            intent_type in {
                str(item).strip()
                for item in (getattr(tool, "intent_types", []) or [])[1:]
            }
            for tool in tools
        )
        return bool(tools) and explicit_scope and all(
            str(getattr(tool, "action", "") or "").strip().lower() == "create"
            and str(getattr(tool, "resource_type", "") or "").strip().lower()
            == "campaign"
            and "campaign_only" in {
                str(item).strip().lower()
                for item in (getattr(tool, "traits", []) or [])
            }
            for tool in tools
        )

    def _creation_blueprint_tool_plan(
        self,
        blueprint_id: Optional[str],
        blueprint_version: Optional[str],
        intent: ParsedIntent,
    ) -> tuple[Optional[dict[str, list[Any]]], Optional[str]]:
        """Resolve a submitted Blueprint into its declared Tool composition."""
        if not blueprint_id:
            return None, None
        blueprint = self.creation_blueprints.get(blueprint_id, blueprint_version)
        if blueprint is None:
            return None, (
                f"广告创建蓝图不存在：{blueprint_id}@"
                f"{blueprint_version or 'latest'}"
            )
        requested_platforms = {
            self._canonical_platform(platform)
            for platform in (getattr(intent, "namespaces", []) or [])
        }
        blueprint_platform = self._canonical_platform(blueprint.provider)
        if requested_platforms and requested_platforms != {blueprint_platform}:
            return None, "广告创建蓝图与当前请求的平台不一致，请重新打开对应向导。"
        definitions = []
        missing_tools = []
        for tool_name in blueprint.tools:
            try:
                definition, _handler = self.registry.get(tool_name)
            except (KeyError, LookupError):
                missing_tools.append(str(tool_name))
                continue
            if self._canonical_platform(definition.namespace) != blueprint_platform:
                missing_tools.append(str(tool_name))
                continue
            definitions.append(definition)
        if missing_tools:
            return None, "广告创建蓝图依赖的能力暂不可用：" + ", ".join(
                missing_tools[:8]
            )
        if not definitions:
            return None, "广告创建蓝图没有可用的创建能力。"
        ordered = SimpleIntentRouter._order_by_resource_dependencies(definitions)
        return {blueprint_platform: ordered}, None


__all__ = ["AdCreationBlueprintServicesMixin"]
