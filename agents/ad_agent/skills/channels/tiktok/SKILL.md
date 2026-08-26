---
name: tiktok-ads-api
description: TikTok Ads API 工具集 - 支持 Campaign/Ad Group/Ad 管理、Spark Ads、Pixel 追踪、Conversion API、报表查询等功能
version: 1.0.0
author: Ryan
tags: [tiktok, ads, api, spark-ads, pixel, conversion-api, short-video]
---

# TikTok Ads API 工具集

## 🛠️ 可用 Tools

| Tool | 功能 | 参数 |
|------|------|------|
| `tiktok_list_campaigns` | 列出广告系列 | account_id, limit, page_token |
| `tiktok_get_campaign` | 获取广告系列详情 | campaign_id |
| `tiktok_create_campaign` | 创建广告系列 | account_id, name, budget, bid_type |
| `tiktok_list_adgroups` | 列出广告组 | campaign_id, limit |
| `tiktok_get_adgroup` | 获取广告组详情 | adgroup_id |
| `tiktok_create_adgroup` | 创建广告组 | campaign_id, name, targeting, bid |
| `tiktok_list_ads` | 列出广告创意 | adgroup_id, limit |
| `tiktok_get_ad` | 获取广告创意详情 | ad_id |
| `tiktok_create_ad` | 创建广告创意 | adgroup_id, name, tracking_url |
| `tiktok_create_spark_ad` | 创建 Spark Ads | adgroup_id, video_id, creator_id |
| `tiktok_track_pixel` | 追踪 Pixel 事件 | pixel_id, event_name, event_data |
| `tiktok_send_capi` | 发送 Conversion API 事件 | pixel_id, user_data, custom_data |
| `tiktok_query_report` | 查询报表数据 | account_id, date_range, fields |
| `tiktok_get_account` | 获取账户信息 | account_id |

## 📚 参考

- [TikTok Ads API 官方文档](https://business-api.tiktok.com/portal/docs)
- [专家知识库](../../../knowledge/skills/tiktok-ads-expert/SKILL.md) - 详细 API 指南、最佳实践、常见问题
