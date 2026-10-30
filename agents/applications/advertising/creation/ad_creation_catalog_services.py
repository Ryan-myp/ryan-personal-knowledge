"""Catalog and support metadata services for advertising creation."""

from __future__ import annotations

from typing import Any, Mapping, Optional

from agents.tools.advertising.shared.domain.contracts import AdFormatCoverage
from agents.tools.advertising.shared.domain.blueprint import (
    BlueprintCascadeEngine,
)


class AdCreationCatalogServicesMixin:
    def list_ad_formats(
        self, platform: Optional[str] = None, coverage: Optional[str] = None
    ) -> list[dict[str, Any]]:
        """Return JSON-safe format coverage metadata for UI/planners."""
        if coverage is not None:
            coverage = str(coverage).strip().lower()
            if coverage not in {item.value for item in AdFormatCoverage}:
                raise ValueError(f"unsupported ad format coverage: {coverage}")
        platforms = [self._canonical_platform(platform)] if platform else sorted(
            self.ad_format_catalogs
        )
        result: list[dict[str, Any]] = []
        for current in platforms:
            for entry in self.ad_format_catalogs.get(current, []):
                if coverage and entry.get("coverage") != coverage:
                    continue
                result.append({"platform": current, **dict(entry)})
        return result

    def list_parameter_options(
        self, platform: Optional[str] = None, field: Optional[str] = None,
        tool_name: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Return JSON-safe static or dynamic provider parameter metadata."""
        return [
            catalog.to_dict()
            for catalog in self.parameter_catalogs.list(
                platform=platform, field=field, tool_name=tool_name
            )
        ]

    def list_creation_blueprints(
        self, provider: Optional[str] = None, ad_format: Optional[str] = None,
        selector_dimension: Optional[str] = None, selector_value: Any = None,
    ) -> list[dict[str, Any]]:
        """Return provider-owned creation metadata without network calls."""
        result = []
        for blueprint in self.creation_blueprints.list(
            provider, ad_format, selector_dimension, selector_value
        ):
            expanded = self.creation_card_builder.expand_blueprint(blueprint)
            document = expanded.to_dict()
            document["support"] = self._creation_blueprint_support(expanded)
            result.append(document)
        return result

    def list_creation_catalog(
        self,
        provider: Optional[str] = None,
        *,
        ad_format: Optional[str] = None,
        selector_dimension: Optional[str] = None,
        selector_value: Any = None,
        account_id: Optional[str] = None,
        account_scope: Any = None,
        tenant_id: str = "default",
        user_id: str = "anonymous",
    ) -> dict[str, Any]:
        """Return the provider-neutral creation entry catalog."""
        blueprints = self.list_creation_blueprints(
            provider, ad_format, selector_dimension, selector_value,
        )
        templates = self.list_creation_templates(
            provider=provider,
            account_id=account_id,
            account_scope=account_scope,
            tenant_id=tenant_id,
            user_id=user_id,
        )
        templates_by_blueprint: dict[str, list[dict[str, Any]]] = {}
        for template in templates:
            templates_by_blueprint.setdefault(
                str(template.get("blueprint_id") or ""), []
            ).append(template)
        verification_weights = {
            "live_verified": 30,
            "live_verified_with_provider_limits": 22,
            "partial_live_verified": 16,
            "dry_run_only": 8,
            "provider_limited": 4,
        }
        ad_types: list[dict[str, Any]] = []
        for blueprint in blueprints:
            blueprint_id = str(blueprint.get("id") or "")
            required_inputs = [
                {
                    "path": str(field.get("path") or ""),
                    "label": str(field.get("label") or field.get("path") or ""),
                    "required": True,
                    "conditional": bool(field.get("required_when")),
                    "source": str(field.get("source") or "tool_schema"),
                }
                for field in blueprint.get("fields") or ()
                if isinstance(field, Mapping)
                and bool(field.get("required") or field.get("required_when"))
                and field.get("presentation") != "derived_readonly"
            ]
            options: list[dict[str, Any]] = []
            for template in templates_by_blueprint.get(blueprint_id, []):
                values = template.get("values")
                values = values if isinstance(values, Mapping) else {}
                pinned = self.creation_blueprints.get(
                    blueprint_id, str(template.get("blueprint_version") or ""),
                )
                if pinned is None:
                    continue
                pinned = self.creation_card_builder.expand_blueprint(pinned)
                evaluated = BlueprintCascadeEngine().evaluate(pinned, values)
                required_paths = {
                    field["path"] for field in pinned.fields
                    if field.get("required") or field.get("required_when")
                }
                missing = [path for path in evaluated["missing_fields"] if path in required_paths]
                template_account = str(template.get("account_id") or "")
                account_score = (
                    100 if account_id and template_account == str(account_id)
                    else 35 if not template_account else 0
                )
                covered = len(required_paths) - len(missing)
                coverage_score = int(20 * covered / max(len(required_paths), 1))
                verification_score = verification_weights.get(
                    str(template.get("verification_status") or ""), 0,
                )
                options.append({
                    **template,
                    "missing_inputs": missing,
                    "missing_input_count": len(missing),
                    "upgrade_available": pinned.version != blueprint["version"],
                    "latest_blueprint_version": blueprint["version"],
                    "recommendation_score": (
                        account_score
                        + coverage_score
                        + verification_score
                        - len(missing) * 5
                    ),
                })
            options.sort(key=lambda item: (
                -int(item.get("recommendation_score") or 0),
                int(item.get("missing_input_count") or 0),
                str(item.get("name") or ""),
            ))
            ad_types.append({
                "blueprint_id": blueprint_id,
                "blueprint_version": blueprint.get("version"),
                "provider": blueprint.get("provider"),
                "ad_format": blueprint.get("ad_format"),
                "title": blueprint.get("title") or blueprint_id,
                "description": blueprint.get("description") or "",
                "selector": blueprint.get("selector"),
                "required_inputs": required_inputs,
                "template_options": options,
                "template_optional": True,
                "support": blueprint.get("support") or {},
            })
        return {
            "schema_version": "1.0",
            "provider": provider,
            "account_id": account_id,
            "template_optional": True,
            "ad_types": ad_types,
        }

    def _creation_blueprint_support(self, blueprint: Any) -> dict[str, Any]:
        """Use provider-declared relationships; word overlap is not evidence."""
        candidates = [
            entry for entry in self.ad_format_catalogs.get(blueprint.provider, [])
            if isinstance(entry, Mapping)
            and blueprint.blueprint_id in entry.get("blueprint_ids", [])
        ]
        if not candidates:
            return {
                "level": "contract_only",
                "label": "已接入字段合同",
                "catalog_match": False,
                "gaps": ["尚未关联渠道广告类型目录"],
            }
        entry = sorted(candidates, key=lambda item: (
            item.get("resource_type") != "campaign",
            len(item.get("blueprint_ids", [])),
            str(item.get("format_id")),
        ))[0]
        limitation = entry.get("creation_limitation")
        if entry.get("creation_available") is False and limitation:
            return {
                "level": "platform_restricted", "label": "当前接口不支持新建",
                "creation_available": False, "limitation": dict(limitation),
                "catalog_match": True, "catalog_format": entry.get("format_id"),
                "gaps": list(entry.get("gaps") or ())[:8],
            }
        coverage = str(entry.get("coverage") or "contract_only")
        labels = {
            "supported_dry_run": "支持草稿校验",
            "partial_dry_run": "部分支持草稿",
            "declared_only": "暂不支持向导创建",
            "contract_only": "已接入字段合同",
        }
        return {
            "level": coverage,
            "label": labels.get(coverage, coverage),
            "catalog_match": True,
            "catalog_format": entry.get("format_id"),
            "dependencies": list(entry.get("dependencies") or ())[:8],
            "gaps": list(entry.get("gaps") or ())[:8],
        }


__all__ = ["AdCreationCatalogServicesMixin"]
