---
schema_version: "1"
id: meta-ads-hierarchy-and-objectives
title: Meta Ads 账户、层级与目标体系
layer: platform
knowledge_type: hierarchy
platform: meta
source: Meta Marketing API 官方文档 + Meta Capability/Skill
source_ref: https://developers.facebook.com/docs/marketing-api/campaign-structure
version: "1.0.0"
confidence: 0.9
updated_at: "2026-09-08"
tags: [meta, facebook, instagram, campaign, ad-set, ad, odax, hierarchy]
status: published
---

# Meta Ads 账户、层级与目标体系

## 资源树

```text
Business / Business Manager
  ├── Ad Account
  │     └── Campaign（目标、特殊广告类别）
  │            └── Ad Set（预算、排期、受众、版位、优化、出价）
  │                   └── Ad（身份、创意、链接、追踪）
  ├── Page / Instagram identity
  ├── Pixel / Conversions API / Custom Conversion
  ├── Catalog / Product Set
  └── Custom / Lookalike / Website Audience
```

Campaign 是目标与实验的组织边界，Ad Set 是投放策略和预算边界，Ad 是创意与身份边界。一个 Ad Set 可以承载多个 Ad 做创意比较，但不应把完全不同的目标、国家、漏斗阶段或成本模型混在一个学习单元里。

## 目标选择

Meta 常用 ODAX 目标包括 Awareness、Traffic、Engagement、Leads、App promotion、Sales；实际名称、可用优化事件和 Advantage+ 形态会随账户、地区和 API 版本变化，必须以当前 Tool enum 为准。

| 结果 | 常见目标 | 优化事件示例 |
|---|---|---|
| 触达认知 | Awareness | reach、impressions、ad recall 等 |
| 访问/内容消费 | Traffic/Engagement | landing page view、video view、post engagement |
| 线索 | Leads | lead、qualified lead、conversion lead |
| 应用增长 | App promotion | install、registration、purchase |
| 交易 | Sales | add to cart、purchase、value |

目标不是文案标签，而是决定可用的 Ad Set 优化、计费、受众扩量和报告解释。若用户只说“投转化广告”，至少还需确认业务结果、Pixel/事件、网站或 App、国家、预算和素材身份。

## 资产依赖

Page/Instagram identity、Pixel、Catalog、Product Set、Lead Form、Custom Conversion 的所有权和状态独立于 Campaign。名称不能替代 ID；创建 Ad 前要逐项 lookup、校验账户归属、权限、审核和可投放状态。Catalog Ad 还要确认商品源、商品集、商品状态和落地页。

## 当前平台边界

当前 Capability 覆盖 Campaign、Ad Set、Ad、Creative、资产、Audience、Catalog/Product Set、Page、Pixel/CAPI、Lead、Insights 等一组已注册动作；具体字段和可写范围以 Registry Tool contract 为准。知识库不凭空增加 Graph API endpoint，也不把 Skill 中的建议当作 Tool。
