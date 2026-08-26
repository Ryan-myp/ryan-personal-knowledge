---
name: meta-marketing-api
description: Meta Marketing API 工具集 - 支持 Campaign/Ad Set/Ad 管理、Pixel 追踪、Conversion API、受众管理等功能
version: 1.0.0
author: Ryan
tags: [meta, facebook, instagram, marketing-api, pixel, capi, audiences]
---

# Meta Marketing API 工具集

## 🛠️ 可用 Tools

| Tool | 功能 | 参数 |
|------|------|------|
| `meta_list_campaigns` | 列出广告系列 | account_id, limit, fields |
| `meta_get_campaign` | 获取广告系列详情 | campaign_id |
| `meta_create_campaign` | 创建广告系列 | account_id, name, objective, status |
| `meta_list_ad_sets` | 列出广告组 | campaign_id, limit |
| `meta_get_adset` | 获取广告组详情 | adset_id |
| `meta_create_adset` | 创建广告组 | campaign_id, name, targeting, budget |
| `meta_list_ads` | 列出广告创意 | adset_id, limit |
| `meta_get_ad` | 获取广告创意详情 | ad_id |
| `meta_create_ad` | 创建广告创意 | adset_id, name, creative, status |
| `meta_track_pixel` | 追踪 Pixel 事件 | pixel_id, event_name, event_data |
| `meta_send_capi` | 发送 Conversion API 事件 | pixel_id, user_data, custom_data |
| `meta_create_audience` | 创建自定义受众 | account_id, name, rules |
| `meta_create_lookalike` | 创建 Lookalike 受众 | source_audience_id, location, percent |
| `meta_query_insights` | 查询广告洞察 | account_id, date_preset, fields |

## 📚 参考

- [Meta Marketing API 官方文档](https://developers.facebook.com/docs/marketing-api)
- [专家知识库](../../../knowledge/skills/meta-marketing-api-expert/SKILL.md) - 详细 API 指南、最佳实践、常见问题
