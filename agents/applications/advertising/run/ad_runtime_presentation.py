"""Advertising presentation adapters kept outside the Run facade."""

from __future__ import annotations

from typing import Mapping, Optional


class AdvertisingPresentationService:
    """Map declarative input fields to concise operator-facing labels."""

    @staticmethod
    def clarification_field_label(
        path: str,
        spec: Mapping[str, Any],
    ) -> Optional[str]:
        configured = spec.get("label") or spec.get("title")
        if configured:
            return str(configured)
        return {
            "account_id": "广告账户 ID",
            "ad_account_id": "广告账户 ID",
            "advertiser_id": "广告主 ID",
            "customer_id": "客户账户 ID",
            "campaign_id": "Campaign ID",
            "campaign_ids": "Campaign ID 列表",
            "ad_group_id": "Ad Group ID",
            "adgroup_id": "Ad Group ID",
            "ad_id": "Ad ID",
        }.get(str(path or "").rsplit(".", 1)[-1])

    @staticmethod
    def clarification_field_hint(
        path: str,
        _spec: Mapping[str, Any],
    ) -> Optional[str]:
        if str(path or "").rsplit(".", 1)[-1] in {
            "account_id",
            "ad_account_id",
            "advertiser_id",
            "customer_id",
        }:
            return "请填写当前渠道的广告账户 ID，不能用其他渠道账户代替。"
        return None
__all__ = ["AdvertisingPresentationService"]
