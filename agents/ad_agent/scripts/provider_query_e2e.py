#!/usr/bin/env python3
"""Verify fixed read-only Provider Tools against configured test accounts."""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import time
from datetime import date
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import yaml

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.ad_agent.core.interfaces import ToolContext, ToolEffect  # noqa: E402
from agents.ad_agent.core.namespace import normalize_namespace  # noqa: E402
from agents.ad_agent.core.tool_registry import validate_tool_input  # noqa: E402
from agents.ad_agent.domain.ad.provider_evidence import (  # noqa: E402
    build_provider_evidence_report,
    validate_provider_evidence,
)
from agents.ad_agent.runtime.account_policy import AccountWhitelistValidator  # noqa: E402
from agents.ad_agent.runtime.runtime import AdvertisingComposition  # noqa: E402
from agents.ad_agent.tools.providers.source_factory import create_tool_source  # noqa: E402


DEFAULT_OUTPUT = ROOT / "agents" / "ad_agent" / "contracts" / "provider_query_e2e_evidence.json"
QUERY_TOOLS = {
    "google-ads": (
        "google_list_campaigns",
        "google_list_ad_groups",
        "google_list_ads",
        "google_get_campaign_report",
        "google_get_ad",
        "google_get_ad_group",
        "google_get_adgroup_report",
        "google_get_asset",
        "google_get_asset_group",
        "google_get_asset_group_listing_group_filter",
        "google_get_bidding_strategy",
        "google_get_campaign",
        "google_get_campaign_budget",
        "google_get_campaign_criterion",
        "google_get_conversion_action",
        "google_get_experiment",
        "google_get_product_group",
        "google_get_user_list",
        "google_list_asset_group_assets",
        "google_list_asset_group_listing_group_filters",
        "google_list_asset_groups",
        "google_list_assets",
        "google_list_bidding_strategies",
        "google_list_campaign_assets",
        "google_list_campaign_budgets",
        "google_list_campaign_conversion_goals",
        "google_list_campaign_criteria",
        "google_list_conversion_actions",
        "google_list_customer_clients",
        "google_list_customer_conversion_goals",
        "google_list_experiment_arms",
        "google_list_experiments",
        "google_list_keywords",
        "google_list_product_groups",
        "google_list_user_lists",
    ),
    "meta": (
        "meta_get_account",
        "meta_list_campaigns",
        "meta_list_creatives",
        "meta_list_ad_sets",
        "meta_list_ads",
        "meta_get_campaign_report",
        "meta_get_ad",
        "meta_get_ad_report",
        "meta_get_adset",
        "meta_get_adset_report",
        "meta_get_audience",
        "meta_get_business",
        "meta_get_campaign",
        "meta_get_catalog",
        "meta_get_creative",
        "meta_get_custom_conversion",
        "meta_get_lead",
        "meta_get_lead_form",
        "meta_get_pixel",
        "meta_get_product_set",
        "meta_list_accounts",
        "meta_list_audiences",
        "meta_list_businesses",
        "meta_list_catalogs",
        "meta_list_custom_conversions",
        "meta_list_image_assets",
        "meta_list_lead_forms",
        "meta_list_leads",
        "meta_list_pages",
        "meta_list_pixels",
        "meta_list_product_sets",
        "meta_list_video_assets",
        "meta_lookup_adset",
        "meta_lookup_creative",
        "meta_search_targeting_options",
    ),
    "tiktok": (
        "tiktok_get_account",
        "tiktok_list_campaigns",
        "tiktok_list_adgroups",
        "tiktok_list_ads",
        "tiktok_get_campaign_report",
        "tiktok_get_ad",
        "tiktok_get_adgroup",
        "tiktok_get_adgroup_report",
        "tiktok_get_audience",
        "tiktok_get_brand_safety_partner_status",
        "tiktok_get_campaign",
        "tiktok_get_catalog",
        "tiktok_get_creative",
        "tiktok_get_creative_portfolio",
        "tiktok_get_identity",
        "tiktok_get_identity_video_info",
        "tiktok_get_image",
        "tiktok_get_interest_category",
        "tiktok_get_pixel",
        "tiktok_get_product_set",
        "tiktok_get_report",
        "tiktok_get_video",
        "tiktok_list_accounts",
        "tiktok_list_action_categories",
        "tiktok_list_apps",
        "tiktok_list_audiences",
        "tiktok_list_carriers",
        "tiktok_list_catalogs",
        "tiktok_list_creatives",
        "tiktok_list_device_models",
        "tiktok_list_identities",
        "tiktok_list_images",
        "tiktok_list_interest_categories",
        "tiktok_list_languages",
        "tiktok_list_os_versions",
        "tiktok_list_pixels",
        "tiktok_list_product_sets",
        "tiktok_list_regions",
        "tiktok_list_videos",
        "tiktok_preview_creative_portfolio",
        "tiktok_recommend_interest_keywords",
        "tiktok_search_locations",
        "tiktok_validate_product_selection",
    ),
}
PROVIDER_CONFIG = {
    "google-ads": {"credential": "google", "test_account_keys": ("google", "google-ads")},
    "meta": {"credential": "meta", "test_account_keys": ("meta",)},
    "tiktok": {"credential": "tiktok", "test_account_keys": ("tiktok",)},
}
SAFETY = {
    "test_accounts_only": True,
    "new_resources_paused": True,
    "deleted": False,
    "credentials_included": False,
    "raw_provider_responses_included": False,
}
QUERY_TIMEOUT_SECONDS = 15.0
PROVIDER_QUERY_TIMEOUT_SECONDS = {"meta": 30.0}
QUERY_SKIP_REASONS = {
    "missing_parent_resource",
    "no_safe_input",
    "sensitive_data",
    "test_scope_unverifiable",
    "unsupported_scope",
}
RESOURCE_ID_FIELDS = {
    "account": ("account_id", "id"),
    "campaign": ("campaign_id", "id", "resource_name"),
    "ad_group": ("ad_group_id", "adgroup_id", "id", "resource_name"),
    "ad_set": ("adset_id", "ad_set_id", "id"),
    "ad": ("ad_id", "id"),
    "creative": ("creative_id", "ad_id", "id"),
    "asset": ("asset_id", "id", "resource_name"),
    "asset_group": ("asset_group_id", "id", "resource_name"),
    "listing_group_filter": ("listing_group_filter_id", "id", "resource_name"),
    "bidding_strategy": ("bidding_strategy_id", "id", "resource_name"),
    "campaign_budget": ("budget_id", "campaign_budget_id", "id", "resource_name"),
    "campaign_criterion": ("criterion_id", "campaign_criterion_id", "id"),
    "conversion_action": ("conversion_action_id", "id", "resource_name"),
    "experiment": ("experiment_id", "id", "resource_name"),
    "product_group": ("product_group_id", "id", "resource_name"),
    "user_list": ("user_list_id", "id", "resource_name"),
    "audience": ("audience_id", "custom_audience_id", "id"),
    "catalog": ("catalog_id", "id"),
    "custom_conversion": ("custom_conversion_id", "id"),
    "pixel": ("pixel_id", "id", "code"),
    "product_set": ("product_set_id", "id"),
    "page": ("page_id", "id"),
    "lead_form": ("form_id", "lead_form_id", "id"),
    "lead": ("lead_id", "id"),
    "image_asset": ("image_hash", "image_id", "hash", "id"),
    "image": ("image_id", "id"),
    "video_asset": ("video_id", "id"),
    "video": ("video_id", "id"),
    "identity": ("identity_id", "id"),
    "interest_category": ("interest_category_id", "category_id", "id"),
    "creative_portfolio": ("creative_portfolio_id", "id"),
}
RESOURCE_PARENT_ID_FIELDS = {
    "campaign": ("campaign_id", "campaignId"),
    "ad_group": ("adgroup_id", "ad_group_id", "adgroupId", "adGroupId"),
    "ad_set": ("adset_id", "ad_set_id", "adsetId", "adSetId"),
    "asset_group": ("asset_group_id", "assetGroupId"),
    "listing_group_filter": ("asset_group_id", "assetGroupId"),
    "product_group": ("ad_group_id", "adgroup_id", "adGroupId"),
    "catalog": ("catalog_id", "catalogId"),
    "page": ("page_id", "pageId"),
    "lead_form": ("form_id", "lead_form_id", "leadFormId"),
    "identity": ("identity_id", "identityId"),
}
RESOURCE_INPUT_TYPES = {
    "campaign_id": "campaign",
    "campaign_ids": "campaign",
    "ad_group_id": "ad_group",
    "adgroup_id": "ad_group",
    "ad_set_id": "ad_set",
    "adset_id": "ad_set",
    "ad_id": "ad",
    "ad_ids": "ad",
    "creative_id": "creative",
    "asset_id": "asset",
    "asset_group_id": "asset_group",
    "listing_group_filter_id": "listing_group_filter",
    "bidding_strategy_id": "bidding_strategy",
    "budget_id": "campaign_budget",
    "campaign_budget_id": "campaign_budget",
    "criterion_id": "campaign_criterion",
    "campaign_criterion_id": "campaign_criterion",
    "conversion_action_id": "conversion_action",
    "experiment_id": "experiment",
    "product_group_id": "product_group",
    "user_list_id": "user_list",
    "audience_id": "audience",
    "catalog_id": "catalog",
    "custom_conversion_id": "custom_conversion",
    "pixel_id": "pixel",
    "product_set_id": "product_set",
    "page_id": "page",
    "form_id": "lead_form",
    "lead_form_id": "lead_form",
    "lead_id": "lead",
    "image_id": "image",
    "image_ids": "image",
    "video_id": "video",
    "identity_id": "identity",
    "interest_category_id": "interest_category",
    "category_id": "interest_category",
    "creative_portfolio_id": "creative_portfolio",
}
RESOURCE_INPUT_TYPE_FALLBACKS = {
    ("tiktok", "creative_id"): ("ad",),
}
SENSITIVE_QUERY_TOOLS = {
    "google_list_user_lists",
    "google_get_user_list",
    "meta_list_audiences",
    "meta_get_audience",
    "meta_list_leads",
    "meta_get_lead",
    "tiktok_list_audiences",
    "tiktok_get_audience",
    "tiktok_list_identities",
    "tiktok_get_identity",
    "tiktok_get_identity_video_info",
}
OUT_OF_SCOPE_QUERY_TOOLS = {
    "google_list_customer_clients",
    "meta_list_accounts",
    "meta_list_businesses",
    "meta_get_business",
}
SAFE_QUERY_INPUTS = {
    "meta_search_targeting_options": {"query": "travel"},
    "tiktok_get_brand_safety_partner_status": {"partner": "Zefr"},
    "tiktok_list_os_versions": {"os_type": "ANDROID"},
    "tiktok_list_regions": {
        "placements": ["PLACEMENT_TIKTOK"],
        "objective_type": "TRAFFIC",
    },
    "tiktok_recommend_interest_keywords": {"keyword": "travel"},
    "tiktok_search_locations": {"keyword": "California"},
}


def _flatten_strings(value: Any) -> set[str]:
    if isinstance(value, Mapping):
        flattened = {str(key).strip() for key in value if str(key).strip()}
        for child in value.values():
            flattened.update(_flatten_strings(child))
        return flattened
    if isinstance(value, (list, tuple, set)):
        flattened: set[str] = set()
        for child in value:
            flattened.update(_flatten_strings(child))
        return flattened
    if isinstance(value, (str, int)) and not isinstance(value, bool):
        text = str(value).strip()
        return {text} if text else set()
    return set()


def select_test_account(
    allowlisted_accounts: Sequence[Any],
    configured_test_accounts: Any,
) -> str:
    """Require one account to be present in both trusted configuration sets."""
    allowlist = {
        str(account).strip()
        for account in allowlisted_accounts
        if str(account).strip()
    }
    matches = sorted(allowlist.intersection(_flatten_strings(configured_test_accounts)))
    if len(matches) != 1:
        raise ValueError("expected exactly one configured test account in the allowlist")
    return matches[0]


def count_result_rows(
    payload: Any,
    result_key: str,
    resource_type: str = "",
) -> int:
    """Count returned rows without treating an empty live result as a failure."""
    return len(_rows(payload, result_key, resource_type))


def classify_query_failure(message: str, status_code: int | None = None) -> str:
    """Map untrusted Provider errors to the bounded evidence vocabulary."""
    text = str(message or "").casefold()
    try:
        status = int(status_code or 0)
    except (TypeError, ValueError):
        status = 0
    auth_terms = (
        "invalid access token",
        "authentication",
        "token expired",
        "page access token",
        "invalid token type",
    )
    if status == 401 or any(word in text for word in auth_terms):
        return "credential_error"
    if "plugin not found" in text:
        return "provider_error"
    permission_terms = ("permission", "unauthorized", "forbidden")
    if status == 403 or any(word in text for word in permission_terms):
        return "provider_permission"
    if status == 404 or "not found" in text:
        return "provider_not_found"
    if status == 429 or "rate limit" in text or "too many requests" in text:
        return "provider_rate_limit"
    if "timeout" in text or "timed out" in text or "deadline" in text:
        return "provider_timeout"
    if status >= 500:
        return "provider_unavailable"
    if status == 400 or "invalid" in text or "validation" in text:
        return "provider_validation"
    return "provider_error"


def redact_error(
    message: str,
    *,
    secret_values: Iterable[str] = (),
    resource_ids: Iterable[str] = (),
) -> str:
    """Remove credentials and account/resource identifiers from CLI errors."""
    value = str(message or "")
    for secret in sorted(
        {str(item) for item in secret_values if str(item)},
        key=len,
        reverse=True,
    ):
        value = value.replace(secret, "<redacted>")
    for identifier in sorted(
        {str(item) for item in resource_ids if str(item)},
        key=len,
        reverse=True,
    ):
        value = value.replace(identifier, "<redacted>")
    value = re.sub(r"\b\d{6,}\b", "<redacted>", value)
    value = re.sub(
        r"(?i)(access[_ -]?token|refresh[_ -]?token|client[_ -]?secret|"
        r"app[_ -]?secret|developer[_ -]?token)(\s*[:=]\s*)[^\s,;]+",
        r"\1\2<redacted>",
        value,
    )
    return re.sub(r"https?://\S+", "<provider-url>", value)[:240]


def _configured_test_refs(
    credentials: Mapping[str, Any],
    provider: str,
) -> Any:
    test_accounts = credentials.get("test_accounts", {})
    spec = PROVIDER_CONFIG[provider]
    if not isinstance(test_accounts, Mapping):
        return None
    values = [
        test_accounts[key]
        for key in spec["test_account_keys"]
        if key in test_accounts
    ]
    return values


def _collect_secret_values(value: Any, key: str = "") -> list[str]:
    secrets: list[str] = []
    normalized_key = str(key).casefold()
    contains_secret = any(
        label in normalized_key
        for label in (
            "token", "secret", "private_key", "password",
            "developer_token",
        )
    )

    def nested_strings(item: Any) -> Iterable[str]:
        if isinstance(item, Mapping):
            for child in item.values():
                yield from nested_strings(child)
        elif isinstance(item, list):
            for child in item:
                yield from nested_strings(child)
        elif isinstance(item, str) and len(item) >= 5:
            yield item

    if contains_secret:
        secrets.extend(nested_strings(value))
    if isinstance(value, Mapping):
        for child_key, child in value.items():
            normalized = str(child_key).casefold()
            secrets.extend(_collect_secret_values(child, normalized))
    elif isinstance(value, list):
        for child in value:
            secrets.extend(_collect_secret_values(child, key))
    return list(dict.fromkeys(secrets))


def _matches_resource_row(value: Mapping[str, Any], resource_type: str) -> bool:
    fields = RESOURCE_ID_FIELDS.get(
        resource_type,
        ("id", "resource_name", "account_id", "customer_id"),
    )
    return any(value.get(field) not in (None, "") for field in fields)


def _rows_from_value(value: Any, resource_type: str) -> list[Any]:
    if isinstance(value, list):
        return value
    if not isinstance(value, Mapping):
        return []
    for key in ("data", "rows", "results", "list", "report_data"):
        rows = value.get(key)
        if isinstance(rows, list):
            return rows
    if _matches_resource_row(value, resource_type):
        return [value]
    return []


def _rows(
    payload: Any,
    result_key: str,
    resource_type: str = "",
) -> list[Any]:
    if not isinstance(payload, Mapping):
        return payload if isinstance(payload, list) else []
    if result_key:
        return _rows_from_value(payload.get(result_key), resource_type)
    for key, candidate in payload.items():
        if key in {"data_status", "simulated", "account_id", "customer_id"}:
            continue
        if isinstance(candidate, list):
            return candidate
        if isinstance(candidate, Mapping):
            rows = _rows_from_value(candidate, resource_type)
            if rows or _matches_resource_row(candidate, resource_type):
                return rows
    return []


def _resource_ids(
    payload: Any,
    result_key: str,
    fields: Sequence[str],
) -> list[str]:
    found = []
    for row in _rows(payload, result_key):
        if not isinstance(row, Mapping):
            continue
        value = next(
            (
                row[field]
                for field in fields
                if row.get(field) not in (None, "")
            ),
            None,
        )
        if value is not None:
            found.append(str(value))
    return found


def _ids_for_resource(payload: Any, result_key: str, resource_type: str) -> list[str]:
    fields = RESOURCE_ID_FIELDS.get(resource_type, ("id",))
    values: list[str] = []
    for row in _rows(payload, result_key, resource_type):
        if not isinstance(row, Mapping):
            continue
        for field in fields:
            value = row.get(field)
            if value in (None, ""):
                continue
            text = str(value).strip()
            if field == "resource_name":
                text = text.rsplit("/", 1)[-1]
            if text and text not in values:
                values.append(text)
            break
    return values


def _row_resource_id(row: Mapping[str, Any], resource_type: str) -> str:
    for field in RESOURCE_ID_FIELDS.get(resource_type, ("id",)):
        value = row.get(field)
        if value in (None, ""):
            continue
        text = str(value).strip()
        return text.rsplit("/", 1)[-1] if field == "resource_name" else text
    return ""


def _row_parent_resource_id(
    row: Mapping[str, Any],
    parent_resource_type: str,
) -> str:
    for field in RESOURCE_PARENT_ID_FIELDS.get(parent_resource_type, ()):
        value = row.get(field)
        if value not in (None, ""):
            return str(value).strip()
    nested_parent = row.get(parent_resource_type)
    if isinstance(nested_parent, Mapping):
        value = nested_parent.get("id")
        if value not in (None, ""):
            return str(value).strip()
    return ""


def seed_created_resources_from_evidence(
    suite: ReadOnlyQueryRun,
    evidence: Mapping[str, Any],
) -> int:
    """Seed read-only query IDs and unambiguous parents from the same test run."""
    if validate_provider_evidence(evidence):
        raise ValueError("invalid provider evidence")
    safety = evidence.get("safety")
    if (
        not isinstance(safety, Mapping)
        or safety.get("test_accounts_only") is not True
        or safety.get("new_resources_paused") is not True
    ):
        raise ValueError("invalid provider evidence safety scope")

    seeded = 0
    parent_edges: dict[str, set[tuple[str, str]]] = {}
    for provider in suite.accounts:
        edges: set[tuple[str, str]] = set()
        for tool in QUERY_TOOLS.get(provider, ()):
            definition, _handler = suite.runtime._get_registered_tool(tool)
            child_type = str(
                getattr(definition, "resource_type", "") or ""
            ).strip()
            parent_type = str(
                getattr(definition, "parent_resource_type", "") or ""
            ).strip()
            if child_type and parent_type:
                edges.add((child_type, parent_type))
        parent_edges[provider] = edges

    def visit(
        resources: Mapping[str, Any],
        provider: str,
        path: tuple[str, ...] = (),
    ) -> dict[tuple[str, ...], dict[str, list[str]]]:
        nonlocal seeded
        scoped_resources: dict[tuple[str, ...], dict[str, list[str]]] = {}
        for name, value in resources.items():
            if not isinstance(value, Mapping):
                continue
            if "create" in value or "update" in value:
                resource_type = str(name).strip().lower()
                resource_id = str(value.get("id") or "").strip()
                if value.get("create") == "passed" and resource_id:
                    pool = suite.resource_pools[provider].setdefault(
                        resource_type,
                        [],
                    )
                    if resource_id not in pool:
                        pool.append(resource_id)
                        seeded += 1
                    branch = path
                    branch_resources = scoped_resources.setdefault(branch, {})
                    ids = branch_resources.setdefault(resource_type, [])
                    if resource_id not in ids:
                        ids.append(resource_id)
                continue
            child_resources = visit(value, provider, (*path, str(name)))
            for branch, resources_by_type in child_resources.items():
                target = scoped_resources.setdefault(branch, {})
                for resource_type, resource_ids in resources_by_type.items():
                    values = target.setdefault(resource_type, [])
                    values.extend(
                        resource_id
                        for resource_id in resource_ids
                        if resource_id not in values
                    )
        return scoped_resources

    for run in evidence.get("runs", []):
        if not isinstance(run, Mapping):
            continue
        provider = normalize_namespace(str(run.get("provider") or ""))
        account_id = str(run.get("test_account") or "").strip()
        if (
            provider not in suite.accounts
            or account_id != suite.accounts[provider]
        ):
            continue
        resources = run.get("resources")
        if isinstance(resources, Mapping):
            scoped_resources = visit(resources, provider)
            for resources_by_type in scoped_resources.values():
                for child_type, parent_type in parent_edges.get(provider, set()):
                    child_ids = resources_by_type.get(child_type, [])
                    parent_ids = resources_by_type.get(parent_type, [])
                    if not child_ids or len(parent_ids) != 1:
                        continue
                    relationships = suite.resource_relationships[provider].setdefault(
                        child_type,
                        [],
                    )
                    known = {
                        (
                            item["resource_id"],
                            item["parent_resource_id"],
                        )
                        for item in relationships
                    }
                    for child_id in child_ids:
                        pair = (child_id, parent_ids[0])
                        if pair in known:
                            continue
                        relationships.append({
                            "resource_id": child_id,
                            "parent_resource_type": parent_type,
                            "parent_resource_id": parent_ids[0],
                        })
                        known.add(pair)
    return seeded


class ReadOnlyQueryRun:
    """Execute a fixed Provider query suite through the registered Runtime."""

    def __init__(
        self,
        runtime: AdvertisingComposition,
        accounts: Mapping[str, str],
        granted_permissions: set[str],
        secret_values: Sequence[str],
    ) -> None:
        self.runtime = runtime
        self.accounts = dict(accounts)
        self.granted_permissions = set(granted_permissions)
        self.secret_values = list(secret_values)
        self.resource_ids = list(accounts.values())
        self.resource_pools: dict[str, dict[str, list[str]]] = {
            provider: {} for provider in QUERY_TOOLS
        }
        self.resource_relationships: dict[
            str, dict[str, list[dict[str, str]]]
        ] = {provider: {} for provider in QUERY_TOOLS}
        self.queries: dict[str, list[dict[str, Any]]] = {
            provider: [] for provider in QUERY_TOOLS
        }
        self.errors: list[tuple[str, str, str]] = []

    def _read_tool(self, provider: str, tool: str) -> Any:
        if tool not in QUERY_TOOLS.get(provider, ()):
            raise RuntimeError("query Tool is not in the fixed read-only allowlist")
        definition, handler = self.runtime._get_registered_tool(tool)
        if definition.effect_class != ToolEffect.READ or definition.is_write_tool:
            raise RuntimeError(f"refusing non-read Tool {tool}")
        if "ads.read" not in self.granted_permissions:
            raise RuntimeError("ads.read permission is not granted")
        if set(definition.required_permissions) - self.granted_permissions:
            raise RuntimeError(f"required permissions are missing for {tool}")
        if getattr(handler, "client", None) is None:
            raise RuntimeError(f"Provider Client is not bound for {tool}")
        return definition

    def preflight(self) -> None:
        """Validate every fixed Tool and account before the first API call."""
        for provider, account_id in self.accounts.items():
            allowed, _ = self.runtime.whitelist_validator.validate_account(
                provider,
                account_id,
            )
            if not allowed:
                raise RuntimeError(f"test account is outside the {provider} allowlist")
            for tool in QUERY_TOOLS[provider]:
                self._read_tool(provider, tool)

    def _record_success(
        self,
        provider: str,
        definition: Any,
        payload: Mapping[str, Any],
        result_key: str,
        input_data: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        resource_type = str(definition.resource_type or "").strip()
        self.queries[provider].append({
            "resource": resource_type or "resource",
            "action": definition.action or "query",
            "tool": definition.name,
            "outcome": "passed",
            "row_count": count_result_rows(payload, result_key, resource_type),
        })
        resource_ids = _ids_for_resource(payload, result_key, resource_type)
        self.resource_pools[provider].setdefault(resource_type, []).extend(
            value
            for value in resource_ids
            if value not in self.resource_pools[provider].get(resource_type, [])
        )
        parent_resource_type = str(
            getattr(definition, "parent_resource_type", "") or ""
        ).strip()
        if parent_resource_type:
            parent_field = str(
                getattr(definition, "parent_resource_id_field", "") or ""
            ).strip()
            filtered_parent = (
                input_data.get(parent_field)
                if input_data and parent_field
                else None
            )
            filtered_parent_id = (
                str(filtered_parent).strip()
                if isinstance(filtered_parent, (str, int))
                and not isinstance(filtered_parent, bool)
                else ""
            )
            relationships = self.resource_relationships[provider].setdefault(
                resource_type,
                [],
            )
            known_relationships = {
                (
                    item["resource_id"],
                    item["parent_resource_id"],
                )
                for item in relationships
            }
            for row in _rows(payload, result_key, resource_type):
                if not isinstance(row, Mapping):
                    continue
                row_id = _row_resource_id(row, resource_type)
                row_parent_id = _row_parent_resource_id(
                    row,
                    parent_resource_type,
                )
                if (
                    row_parent_id
                    and filtered_parent_id
                    and row_parent_id != filtered_parent_id
                ):
                    continue
                parent_id = row_parent_id or filtered_parent_id
                pair = (row_id, parent_id)
                if row_id and parent_id and pair not in known_relationships:
                    relationships.append({
                        "resource_id": row_id,
                        "parent_resource_type": parent_resource_type,
                        "parent_resource_id": parent_id,
                    })
                    known_relationships.add(pair)
        self.resource_ids.extend(resource_ids)
        return {"ok": True, "data": dict(payload)}

    @staticmethod
    def _context(account_id: str, provider: str) -> ToolContext:
        timeout_seconds = PROVIDER_QUERY_TIMEOUT_SECONDS.get(
            provider,
            QUERY_TIMEOUT_SECONDS,
        )
        return ToolContext(
            session_id="provider-query-e2e",
            user_id="local-read-only-verification",
            scope={
                "account_id": account_id,
                "customer_id": account_id,
                "advertiser_id": account_id,
            },
            metadata={
                "execution_mode": "dry_run",
                "granted_permissions": ["ads.read"],
                "turn_deadline": time.monotonic() + timeout_seconds,
            },
        )

    def _record_result(
        self,
        provider: str,
        definition: Any,
        result: Any,
        result_key: str,
        input_data: Mapping[str, Any],
    ) -> dict[str, Any]:
        payload = result.data if isinstance(result.data, Mapping) else {}
        if (
            result.success
            and payload.get("data_status") == "live"
            and not result.simulated
        ):
            return self._record_success(
                provider,
                definition,
                payload,
                result_key,
                input_data,
            )

        detail = getattr(result, "error_detail", None)
        status_code = getattr(detail, "status_code", None) if detail else None
        message = str(result.error or "provider returned non-live or empty status")
        category = (
            "provider_timeout"
            if payload.get("execution_status") == "timed_out"
            else classify_query_failure(message, status_code)
        )
        if result.success:
            category = "response_shape"
        self._record_failure(provider, definition, category, message)
        return {"ok": False, "data": {}}

    def execute(
        self,
        provider: str,
        tool: str,
        input_data: dict[str, Any],
        result_key: str,
    ) -> dict[str, Any]:
        account_id = self.accounts[provider]
        if not self.runtime.whitelist_validator.validate_account(
            provider,
            account_id,
        )[0]:
            raise RuntimeError("test account no longer matches the runtime allowlist")
        definition = self._read_tool(provider, tool)

        schema_errors = validate_tool_input(
            definition.input_schema,
            input_data,
            include_tool_requirements=True,
        )
        if schema_errors:
            self._record_failure(
                provider,
                definition,
                "local_contract",
                "; ".join(schema_errors),
            )
            return {"ok": False, "data": {}}

        print(f"query-start {provider} {tool}", flush=True)
        query_count = len(self.queries[provider])
        started = time.perf_counter()
        result = self.runtime.tool_executor.execute(
            self._context(account_id, provider),
            tool,
            input_data,
        )
        latency_ms = round((time.perf_counter() - started) * 1000, 3)
        recorded = self._record_result(
            provider,
            definition,
            result,
            result_key,
            input_data,
        )
        if len(self.queries[provider]) > query_count:
            self.queries[provider][-1]["latency_ms"] = latency_ms
        outcome = "passed" if recorded["ok"] else "failed"
        print(f"query-result {provider} {tool} {outcome}", flush=True)
        return recorded

    def _record_failure(
        self,
        provider: str,
        definition: Any,
        category: str,
        message: str,
    ) -> None:
        self.queries[provider].append({
            "resource": definition.resource_type or "resource",
            "action": definition.action or "query",
            "tool": definition.name,
            "outcome": "failed",
            "failure_category": category,
        })
        self.errors.append((
            provider,
            definition.name,
            redact_error(
                message,
                secret_values=self.secret_values,
                resource_ids=self.resource_ids,
            ),
        ))

    def record_skip(
        self,
        provider: str,
        tool: str,
        reason: str = "missing_parent_resource",
    ) -> None:
        if reason not in QUERY_SKIP_REASONS:
            raise ValueError("unsupported query skip reason")
        definition, _ = self.runtime._get_registered_tool(tool)
        print(f"query-skip {provider} {tool} {reason}", flush=True)
        self.queries[provider].append({
            "resource": definition.resource_type or "resource",
            "action": definition.action or "query",
            "tool": tool,
            "outcome": "skipped",
            "skip_reason": reason,
        })


def _resource_pool_for_input(
    suite: ReadOnlyQueryRun,
    provider: str,
    field: str,
) -> list[str]:
    resource_type = RESOURCE_INPUT_TYPES.get(field)
    if not resource_type:
        return []
    fallback_types = RESOURCE_INPUT_TYPE_FALLBACKS.get((provider, field), ())
    values = [
        value
        for candidate_type in (resource_type, *fallback_types)
        for value in suite.resource_pools[provider].get(candidate_type, [])
    ]
    return list(dict.fromkeys(values))


def _select_resource_parent_pair(
    suite: ReadOnlyQueryRun,
    provider: str,
    definition: Any,
    properties: Mapping[str, Any],
    values: dict[str, Any],
) -> set[str] | None:
    resource_id_field = str(
        getattr(definition, "resource_id_field", "") or ""
    ).strip()
    parent_id_field = str(
        getattr(definition, "parent_resource_id_field", "") or ""
    ).strip()
    if (
        not resource_id_field
        or not parent_id_field
        or resource_id_field not in properties
        or parent_id_field not in properties
    ):
        return set()

    resource_type = str(getattr(definition, "resource_type", "") or "").strip()
    parent_type = str(
        getattr(definition, "parent_resource_type", "") or ""
    ).strip()
    if not resource_type or not parent_type:
        return None
    relationships = (
        getattr(suite, "resource_relationships", {})
        .get(provider, {})
        .get(resource_type, [])
    )
    expected_resource_id = str(values.get(resource_id_field) or "").strip()
    expected_parent_id = str(values.get(parent_id_field) or "").strip()
    for relationship in relationships:
        if relationship.get("parent_resource_type") != parent_type:
            continue
        resource_id = str(relationship.get("resource_id") or "").strip()
        parent_id = str(relationship.get("parent_resource_id") or "").strip()
        if not resource_id or not parent_id:
            continue
        if expected_resource_id and resource_id != expected_resource_id:
            continue
        if expected_parent_id and parent_id != expected_parent_id:
            continue
        values[resource_id_field] = resource_id
        values[parent_id_field] = parent_id
        return {resource_id_field, parent_id_field}
    return None


def _build_safe_query_input(
    suite: ReadOnlyQueryRun,
    provider: str,
    tool: str,
    definition: Any,
) -> tuple[dict[str, Any] | None, str | None]:
    schema = definition.input_schema.to_dict()
    properties = schema.get("properties", {})
    required = list(schema.get("required", [])) + list(schema.get("requires", []))
    values = dict(SAFE_QUERY_INPUTS.get(tool, {}))
    account = suite.accounts[provider]

    for key in ("account_id", "customer_id", "advertiser_id"):
        if key in properties:
            values[key] = account
    paired_fields = _select_resource_parent_pair(
        suite,
        provider,
        definition,
        properties,
        values,
    )
    if paired_fields is None:
        return None, "missing_parent_resource"
    if "limit" in properties:
        values["limit"] = min(
            int(properties["limit"].get("maximum", 10) or 10),
            10,
        )
    for field, property_schema in properties.items():
        if field in values or field in paired_fields:
            continue
        if (
            field == "advertiser_ids"
            and property_schema.get("type") == "array"
        ):
            max_items = int(property_schema.get("maxItems", 1) or 1)
            values[field] = [account][:max(1, max_items)]
            continue
        resource_values = _resource_pool_for_input(suite, provider, field)
        if not resource_values:
            continue
        if property_schema.get("type") == "array":
            values[field] = resource_values[:3]
        else:
            values[field] = resource_values[0]
    for field, property_schema in properties.items():
        if field in values:
            continue
        if "default" in property_schema:
            values[field] = property_schema["default"]

    resource_id_field = str(
        getattr(definition, "resource_id_field", "") or ""
    ).strip()
    if resource_id_field in properties and resource_id_field not in values:
        return None, "missing_parent_resource"

    for group in schema.get("requires_any_of", []):
        if not any(field in values for field in group):
            candidate = next(
                (
                    field for field in group
                    if _resource_pool_for_input(suite, provider, field)
                ),
                None,
            )
            if candidate is None:
                return None, "no_safe_input"
            pool = _resource_pool_for_input(suite, provider, candidate)
            prop = properties.get(candidate, {})
            values[candidate] = pool[:3] if prop.get("type") == "array" else pool[0]

    for group in schema.get("requires_exactly_one_of", []):
        selected = [field for field in group if field in values]
        if len(selected) > 1:
            for field in selected[1:]:
                values.pop(field, None)
        if not selected:
            candidate = next(
                (
                    field for field in group
                    if _resource_pool_for_input(suite, provider, field)
                ),
                None,
            )
            if candidate is None:
                return None, "no_safe_input"
            pool = _resource_pool_for_input(suite, provider, candidate)
            prop = properties.get(candidate, {})
            values[candidate] = pool[:3] if prop.get("type") == "array" else pool[0]

    missing = [field for field in required if field not in values]
    if missing:
        return None, "missing_parent_resource" if all(
            field in RESOURCE_INPUT_TYPES for field in missing
        ) else "no_safe_input"
    if "query" in required and "query" not in values:
        return None, "no_safe_input"
    return values, None


def _run_remaining_queries(suite: ReadOnlyQueryRun) -> None:
    """Exercise safe fixed READ Tools using only IDs returned by this test account."""
    for provider, tools in QUERY_TOOLS.items():
        completed = {
            item["tool"] for item in suite.queries[provider]
        }
        pending = [tool for tool in tools if tool not in completed]
        while pending:
            deferred: list[str] = []
            progressed = False
            for tool in pending:
                if tool in SENSITIVE_QUERY_TOOLS:
                    suite.record_skip(provider, tool, "sensitive_data")
                    progressed = True
                    continue
                if tool in OUT_OF_SCOPE_QUERY_TOOLS:
                    suite.record_skip(provider, tool, "test_scope_unverifiable")
                    progressed = True
                    continue
                definition, _handler = suite.runtime._get_registered_tool(tool)
                inputs, reason = _build_safe_query_input(
                    suite,
                    provider,
                    tool,
                    definition,
                )
                if reason:
                    deferred.append(tool)
                    continue
                suite.execute(provider, tool, inputs or {}, "")
                progressed = True
            if not deferred:
                break
            if not progressed:
                for tool in deferred:
                    definition, _handler = suite.runtime._get_registered_tool(tool)
                    schema = definition.input_schema.to_dict()
                    required = list(schema.get("required", [])) + list(schema.get("requires", []))
                    reason = (
                        "missing_parent_resource"
                        if required and all(
                            field in RESOURCE_INPUT_TYPES
                            for field in required
                            if field not in {"account_id", "customer_id", "advertiser_id"}
                        )
                        else "no_safe_input"
                    )
                    suite.record_skip(provider, tool, reason)
                break
            pending = deferred


def _ensure_query_coverage(suite: ReadOnlyQueryRun) -> None:
    """Require exactly one terminal evidence outcome for every fixed query Tool."""
    for provider, tools in QUERY_TOOLS.items():
        seen: set[str] = set()
        for query in suite.queries[provider]:
            tool = query["tool"]
            if tool in seen:
                raise RuntimeError(f"duplicate query evidence for {tool}")
            seen.add(tool)
        for tool in tools:
            if tool in seen:
                continue
            reason = (
                "sensitive_data" if tool in SENSITIVE_QUERY_TOOLS
                else "test_scope_unverifiable" if tool in OUT_OF_SCOPE_QUERY_TOOLS
                else "no_safe_input"
            )
            suite.record_skip(provider, tool, reason)


def _run_google(suite: ReadOnlyQueryRun) -> None:
    provider = "google-ads"
    account = suite.accounts[provider]
    campaigns = suite.execute(
        provider,
        "google_list_campaigns",
        {"customer_id": account, "limit": 10},
        "campaigns",
    )
    campaign_ids = (
        _resource_ids(campaigns["data"], "campaigns", ("id", "campaign_id"))
        if campaigns["ok"] else []
    )
    if campaign_ids:
        suite.execute(
            provider,
            "google_list_ad_groups",
            {"campaign_id": campaign_ids[0], "limit": 10},
            "ad_groups",
        )
    else:
        suite.record_skip(provider, "google_list_ad_groups")
    suite.execute(provider, "google_list_ads", {"limit": 10}, "ads")
    suite.execute(
        provider,
        "google_get_campaign_report",
        {
            "customer_id": account,
            "campaign_ids": campaign_ids[:3],
            "date_range": "LAST_7_DAYS",
            "limit": 10,
        },
        "report",
    )


def _run_meta(suite: ReadOnlyQueryRun) -> None:
    provider = "meta"
    account = suite.accounts[provider]
    suite.execute(provider, "meta_get_account", {"account_id": account}, "account")
    campaigns = suite.execute(
        provider,
        "meta_list_campaigns",
        {"account_id": account, "limit": 10},
        "campaigns",
    )
    suite.execute(
        provider,
        "meta_list_creatives",
        {"account_id": account, "limit": 10},
        "creatives",
    )
    campaign_ids = (
        _resource_ids(campaigns["data"], "campaigns", ("id", "campaign_id"))
        if campaigns["ok"] else []
    )
    _run_meta_children(suite, campaign_ids)


def _run_meta_children(
    suite: ReadOnlyQueryRun,
    campaign_ids: Sequence[str],
) -> None:
    provider = "meta"
    ad_sets = (
        suite.execute(
            provider,
            "meta_list_ad_sets",
            {"campaign_id": campaign_ids[0], "limit": 10},
            "ad_sets",
        )
        if campaign_ids else None
    )
    ad_set_ids = (
        _resource_ids(
            ad_sets["data"],
            "ad_sets",
            ("id", "adset_id", "ad_set_id"),
        )
        if ad_sets and ad_sets["ok"] else []
    )
    if ad_set_ids:
        suite.execute(
            provider,
            "meta_list_ads",
            {"adset_id": ad_set_ids[0], "limit": 10},
            "ads",
        )
    else:
        suite.record_skip(provider, "meta_list_ads")
    account = suite.accounts[provider]
    suite.execute(
        provider,
        "meta_get_campaign_report",
        {
            "campaign_ids": campaign_ids[:3],
            "date_preset": "LAST_7_DAYS",
            "limit": 10,
        },
        "report",
    )


def _run_tiktok(suite: ReadOnlyQueryRun) -> None:
    provider = "tiktok"
    account = suite.accounts[provider]
    suite.execute(provider, "tiktok_get_account", {"account_id": account}, "account")
    campaigns = suite.execute(
        provider,
        "tiktok_list_campaigns",
        {"account_id": account, "limit": 10},
        "campaigns",
    )
    campaign_ids = (
        _resource_ids(campaigns["data"], "campaigns", ("campaign_id", "id"))
        if campaigns["ok"] else []
    )
    groups = (
        suite.execute(
            provider,
            "tiktok_list_adgroups",
            {"campaign_id": campaign_ids[0], "limit": 10},
            "adgroups",
        )
        if campaigns["ok"] and campaign_ids else None
    )
    group_ids = (
        _resource_ids(
            groups["data"],
            "adgroups",
            ("adgroup_id", "ad_group_id", "id"),
        )
        if groups and groups["ok"] else []
    )
    if group_ids:
        suite.execute(
            provider,
            "tiktok_list_ads",
            {"adgroup_id": group_ids[0], "limit": 10},
            "ads",
        )
    else:
        suite.record_skip(provider, "tiktok_list_ads")
    suite.execute(
        provider,
        "tiktok_get_campaign_report",
        {
            "account_id": account,
            "campaign_ids": campaign_ids[:3],
            "date_range": "LAST_7_DAYS",
            "limit": 10,
        },
        "report",
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--confirm-read-only-provider-calls",
        action="store_true",
        help="explicitly authorize the fixed read-only test-account query suite",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=ROOT / "agents" / "ad_agent" / "config.yaml",
    )
    parser.add_argument(
        "--credentials-file",
        type=Path,
        default=ROOT / "config" / "ad_platform_credentials.json",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser


def _load_run_inputs(
    config_path: Path,
    credentials_path: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, str]]:
    config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    credentials = json.loads(credentials_path.read_text(encoding="utf-8"))
    accounts: dict[str, str] = {}
    for provider, spec in PROVIDER_CONFIG.items():
        credential_key = spec["credential"]
        provider_credentials = credentials.get(credential_key)
        if not isinstance(provider_credentials, Mapping) or not provider_credentials:
            raise ValueError(f"missing configured credentials for {provider}")
        accounts[provider] = select_test_account(
            config.get("allowed_accounts", {}).get(provider, []),
            _configured_test_refs(credentials, provider),
        )
    return config, credentials, accounts


def _create_runtime(
    config: Mapping[str, Any],
    credentials: Mapping[str, Any],
    config_path: Path,
) -> AdvertisingComposition:
    runtime = AdvertisingComposition(
        require_llm=False,
        offline_mode=False,
        execution_mode="dry_run",
        read_only_mode=True,
        enforce_account_scope=True,
        whitelist_validator=AccountWhitelistValidator(str(config_path)),
        granted_permissions=set(config.get("granted_permissions", [])),
        allow_live_writes=False,
        start_background_workers=False,
    )
    for provider in PROVIDER_CONFIG:
        runtime.register_tool_source(create_tool_source(provider))
    runtime.set_credentials({
        provider: credentials[spec["credential"]]
        for provider, spec in PROVIDER_CONFIG.items()
    })
    return runtime


def _build_evidence(
    suite: ReadOnlyQueryRun,
    accounts: Mapping[str, str],
) -> dict[str, Any]:
    evidence = {
        "schema_version": "1.0",
        "generated_at": date.today().isoformat(),
        "scope": "provider_query_e2e",
        "safety": SAFETY,
        "runs": [],
    }
    for provider, queries in suite.queries.items():
        all_passed = bool(queries) and all(
            query["outcome"] == "passed" for query in queries
        )
        evidence["runs"].append({
            "provider": provider,
            "test_account": f"test-account-{accounts[provider][-4:]}",
            "campaign_type": "READ_ONLY_QUERY",
            "status": "read_verified" if all_passed else "provider_limited",
            "resources": {},
            "queries": queries,
        })
    return evidence


def _write_evidence(evidence: Mapping[str, Any], output_path: Path) -> bool:
    report = build_provider_evidence_report(evidence)
    if not report["valid"]:
        print("blocked: generated query evidence failed schema validation")
        return False
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(evidence, ensure_ascii=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"evidence: {output_path.relative_to(ROOT)}; "
        f"live query runs={len(evidence['runs'])}"
    )
    return True


def _print_summary(suite: ReadOnlyQueryRun) -> None:
    for provider in PROVIDER_CONFIG:
        results = suite.queries[provider]
        passed = sum(item["outcome"] == "passed" for item in results)
        failed = sum(item["outcome"] == "failed" for item in results)
        skipped = sum(item["outcome"] == "skipped" for item in results)
        print(f"{provider}: passed={passed}; failed={failed}; skipped={skipped}")
    for provider, tool, error in suite.errors:
        print(f"  {provider} {tool}: {error}")


def _run_suites(suite: ReadOnlyQueryRun) -> None:
    _run_google(suite)
    _run_meta(suite)
    _run_tiktok(suite)
    _run_remaining_queries(suite)
    _ensure_query_coverage(suite)


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if not args.confirm_read_only_provider_calls:
        print(
            "blocked: pass --confirm-read-only-provider-calls "
            "to enable live reads"
        )
        return 2
    output_path = args.output.resolve()
    if not output_path.is_relative_to(ROOT):
        print("blocked: evidence output must remain inside the repository")
        return 2

    try:
        config, credentials, accounts = _load_run_inputs(
            args.config,
            args.credentials_file,
        )
        seed_evidence = json.loads(
            (
                ROOT
                / "agents"
                / "ad_agent"
                / "contracts"
                / "provider_e2e_evidence.json"
            ).read_text(encoding="utf-8")
        )
        if not isinstance(seed_evidence, Mapping):
            raise ValueError("provider resource seed evidence must be an object")
    except (OSError, ValueError, TypeError) as exc:
        print(f"blocked: unable to load controlled test configuration ({type(exc).__name__})")
        return 2

    runtime = _create_runtime(config, credentials, args.config)
    try:
        suite = ReadOnlyQueryRun(
            runtime,
            accounts,
            set(config.get("granted_permissions", [])),
            _collect_secret_values(credentials),
        )
        suite.preflight()
        seeded_resources = seed_created_resources_from_evidence(
            suite,
            seed_evidence,
        )
        print(f"query-resource-seeds={seeded_resources}", flush=True)
        _run_suites(suite)
        evidence = _build_evidence(suite, accounts)
        if not _write_evidence(evidence, output_path):
            return 2
        _print_summary(suite)
        return int(bool(suite.errors) or any(
            item["outcome"] == "skipped"
            for queries in suite.queries.values()
            for item in queries
        ))
    finally:
        runtime.close(wait=True)


if __name__ == "__main__":
    logging.disable(logging.CRITICAL)
    raise SystemExit(main())
