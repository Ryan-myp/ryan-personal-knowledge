---
name: google-ads-api
description: Google Ads API 工具集 - 支持 Campaign/Ad Group/Keyword/Ad 管理、智能出价、报表查询等功能
version: 1.0.0
author: Ryan
tags: [google, ads, api, campaign, keyword, bidding, reporting]
---

# Google Ads API 工具集

## 🛠️ 可用 Tools

| Tool | 功能 | 参数 |
|------|------|------|
| `google_list_campaigns` | 列出广告系列 | customer_id, limit, filter |
| `google_get_campaign` | 获取广告系列详情 | campaign_id |
| `google_create_campaign` | 创建广告系列 | customer_id, name, budget, bidding_strategy |
| `google_list_ad_groups` | 列出广告组 | campaign_id, limit |
| `google_get_ad_group` | 获取广告组详情 | ad_group_id |
| `google_create_ad_group` | 创建广告组 | campaign_id, name, cpc_bid |
| `google_add_keywords` | 添加关键词 | ad_group_id, keywords, match_type |
| `google_list_ads` | 列出广告创意 | ad_group_id, limit |
| `google_get_ad` | 获取广告创意详情 | ad_id |
| `google_create_ad` | 创建广告创意 | ad_group_id, ads_config |
| `google_list_asset_groups` | 列出 Asset Group | campaign_id, limit |
| `google_get_asset_group` | 获取 Asset Group 详情 | asset_group_id |
| `google_get_campaign_report` | 查询报表数据 | customer_id, date_range, metrics |
| `google_set_bidding` | 设置出价策略 | campaign_id, strategy_type, target_cpa |
| `google_pause_campaign` | 暂停广告系列 | campaign_resource_name |
| `google_enable_campaign` | 启用广告系列 | campaign_resource_name |

## 📚 参考

- [Google Ads API 官方文档](https://developers.google.com/google-ads/api/docs/start)
- [专家知识库](../../../knowledge/skills/google-ads-api-expert/SKILL.md) - 详细 API 指南、最佳实践、常见问题
