---
schema_version: "1"
id: google-campaign-hierarchy
title: Google Ads Campaign 层级与资源模型
layer: platform
knowledge_type: hierarchy
platform: google-ads
source: Google Ads API Campaigns 官方文档
source_ref: "https://developers.google.com/google-ads/api/docs/campaigns/overview"
version: "1.1.0"
confidence: 0.96
updated_at: "2026-10-19"
tags: [google, campaign, hierarchy, ad-group, asset-group, performance-max, shopping]
status: published
source_kind: "official"
authority: "official"
evidence_level: "reviewed"
last_verified_at: "2026-10-19"
---

# Google Ads Campaign 层级与资源模型

Google Ads 的 Campaign 不只是名称和目标。Campaign type 决定可用的广告对象模型、网络、字段和竞价能力。下方是理解对象关系的导航，不是完整 API schema；具体字段、动态枚举、账户资格和当前项目可写能力要以对应 API 版本、账户查询和 Tool schema 为准。

## 两种主要对象模型

### Ad Group 模型

```text
Customer
  └── Campaign
      ├── CampaignBudget (资源，可按配置被多个 Campaign 共用)
      ├── CampaignCriterion / CampaignAsset
      └── AdGroup
          ├── AdGroupCriterion (关键词、受众或其他资格条件)
          ├── AdGroupAd
          └── AdGroupAsset
```

标准 Search 等采用 Ad Group 模型：Ad Group 组织广告和定向条件；Campaign 组织预算、网络/地域设置、出价和其他系列级配置。搜索关键词与广告并非可在任意层级互换的附件，要检查其父资源和资源名称。

### Asset Group 模型

```text
Customer
  └── Campaign (PERFORMANCE_MAX)
      ├── CampaignBudget
      ├── AssetGroup
      │   └── AssetGroupAsset (标题、描述、图片、视频等素材关联)
      ├── AssetGroupListingGroupFilter (商品范围/商品分组)
      └── CampaignCriterion / CampaignAsset
```

Performance Max 使用 `PERFORMANCE_MAX` Campaign 和 `AssetGroup`，不能将其误建成普通 Search Ad Group 后再塞入一条传统广告。商品投放还要核对 Merchant Center、Listing Group 和商品资格；资产组可用不等于商品获批或已经交付。

其他 Campaign 类型可能使用 Ad Group、Asset Group 或混合资产关联方式。即使 UI 有某个投放类型，API 的读取/创建/更新能力也可能不同；先查看当前类型对应的 API 指南和 Tool Source，不从名称相似推断支持。

## 资源职责与关系校验

| 资源 | 主要职责 | 创建或更新前检查 |
|---|---|---|
| Customer | 账户与访问范围 | trusted account scope、时区、币种、账户状态与权限 |
| Campaign | 类型、主要配置、预算引用和投放状态 | 当前类型、必需字段、父级、目标地区、当前 API 版本 |
| CampaignBudget | 预算金额与相关预算设置 | 币种/金额单位、是否共享、当前引用者及账户限制 |
| AdGroup | 传统广告组对象及其出价/投放设置 | 父 Campaign 类型、状态、投放条件和预算归属 |
| Criterion | 关键词、地域、受众等资格条件 | 资源层级、ID/枚举来源、匹配范围、重复和资格 |
| AdGroupAd / AssetGroup | 传统广告组合或自动化素材组合 | 广告类型、素材要求、最终 URL、审核与资产关联 |
| Asset / AssetGroupAsset | 可复用素材及其与资源的关联 | 类型、媒体状态、文本规格、所有权、政策与关联结果 |

名称不是稳定 ID。读回时要保留 resource name、父资源和账户 scope；跨账户只凭名称匹配会产生错误关联。

## 字段与枚举的使用规则

- `advertising_channel_type` 描述 Campaign 的 API 类型；当前官方文档列出的 Performance Max 值为 `PERFORMANCE_MAX`，不要使用历史笔记里的 `MAX`。
- Campaign type 决定后续可用字段和资源。不能把 UI 的目标向导、Campaign type、出价策略和转化目标当成一个枚举。
- `CampaignBudget` 是独立资源，可能被多个 Campaign 共享；更改前必须读取共享关系并评估影响范围。
- 状态、子类型、出价策略、字段长度、可修改性和资源限制随 API 版本及对象类型变化。调用前以当前 API reference / Tool schema 为准，不把旧表格中的固定枚举或数值当成实时事实。
- API 创建/更新支持范围不必等于 UI 支持范围；遇到历史 Video、特殊 Campaign 或新功能，先验证当前 API capability。

## 查询和变更顺序

1. 通过可信配置确定 Customer scope，并读取 Campaign、预算和父子关系。
2. 确认用户说的是 Campaign、Ad Group、Criterion、Ad、Asset 还是 Asset Group。
3. 从 Campaign type 选择对应对象模型，再读取当前 Tool schema 和动态 lookup。
4. 对写入构造依赖图和 dry-run；预算共享、不可变字段、部分成功和幂等键都纳入计划。
5. live 完成后按资源名称回读对象、状态、审核信息、素材关系和实际投放数据。

本页最后核验：2026-10-19。动态字段和 API 能力要随账户与 API 版本复核。

## 官方参考

- [Campaigns overview and resource models](https://developers.google.com/google-ads/api/docs/campaigns/overview)
- [Campaign types and `advertising_channel_type`](https://developers.google.com/google-ads/api/docs/campaigns/overview#campaign_types)
- [Performance Max campaigns](https://developers.google.com/google-ads/api/docs/performance-max/overview)
- [Campaign budgets](https://developers.google.com/google-ads/api/docs/campaigns/budgets/overview)
