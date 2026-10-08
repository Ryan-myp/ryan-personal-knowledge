---
schema_version: "1"
id: google-campaign-hierarchy
title: Google Ads Campaign 层级结构
layer: platform
knowledge_type: hierarchy
platform: google-ads
source: Google Ads 官方文档 + API 实测
source_ref: "repository://ad-agent/knowledge/google-campaign-hierarchy"
version: "1.0.0"
confidence: 0.95
updated_at: "2026-08-26"
tags: [google, campaign, hierarchy]
status: published
source_kind: "code"
authority: "repository"
evidence_level: "reviewed"
last_verified_at: "2026-08-26"
---

# Google Ads Campaign 层级结构

> **来源**: 官方文档 + API 实测
> **更新时间**: 2026-08-26

## 层级概览

```
Customer (客户)
└── Campaign (广告系列)
    └── AdGroup (广告组)
        ├── Keywords (关键词)
        ├── Ads (广告创意)
        └── Assets (素材组 - PMax)
```

## Campaign 层级参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| customer_id | string | ✅ | 客户 ID |
| name | string | ✅ | 广告系列名称 (最大 60 字符) |
| advertising_channel_type | enum | ✅ | SEARCH/DISPLAY/SHOPPING/VIDEO/APP/MULTI_CHANNEL |
| status | enum | ✅ | ENABLED/PAUSED/REMOVED |
| campaign_budget | string | ❌ | 预算资源名称 |
| advertising_channel_type | enum | ✅ | 广告渠道类型 |

### Campaign 类型

| 类型 | 代码 | 说明 |
|------|------|------|
| 搜索广告 | SEARCH | 文本搜索广告 |
| 展示广告 | DISPLAY | 图片/视频展示广告 |
| 购物广告 | SHOPPING | 商品目录广告 |
| 视频广告 | VIDEO | YouTube 广告 |
| 应用广告 | APP | 应用安装广告 |
| 性能最大化 | MAX | 跨渠道智能投放 |

## AdGroup 层级参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| campaign | string | ✅ | 广告系列资源名称 |
| name | string | ✅ | 广告组名称 |
| status | enum | ✅ | ENABLED/PAUSED |
| cpc_bid_cents_micros | int | ❌ | 目标 CPC (单位: micros) |

### 关联资源

- **Keywords**: 关键词列表
- **Ads**: 广告创意列表
- **Assets**: PMax 素材组

## 约束规则

1. **Campaign Budget**: 只能有一个 CampaignBudget 关联到多个 Campaign
2. **Bidding Strategy**: 每个 Campaign 只能有一个 BiddingStrategy
3. **AdGroup Budget**: 不支持 AdGroup 级别预算

## 参考

- [Google Ads API 官方文档](https://developers.google.com/google-ads/api/docs/campaigns/overview)
- [Campaign 创建示例](https://developers.google.cn/google-ads/api/samples/add-search-campaign)
