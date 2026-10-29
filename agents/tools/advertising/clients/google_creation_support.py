"""Platform restrictions on new campaigns; existing resource reads stay available."""

GOOGLE_CAMPAIGN_CREATION_LIMITS = {
    "VIDEO": {
        "reason": "Google Ads API 不支持新建传统 Video Campaign；请使用 Demand Gen。",
        "alternative": "DEMAND_GEN",
        "source_url": "https://developers.google.com/google-ads/api/docs/video/overview",
    },
    "SMART": {
        "reason": "Google 自 2026-09-23 起停止新建 Smart Campaign；请使用 Performance Max。",
        "alternative": "PERFORMANCE_MAX",
        "source_url": (
            "https://developers.google.com/google-ads/api/docs/smart-campaigns/create-campaign"
        ),
    },
}
