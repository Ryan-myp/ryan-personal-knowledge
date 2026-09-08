---
schema_version: "1"
id: tiktok-ads-hierarchy-and-objectives
title: TikTok Ads 账户、层级与投放目标
layer: platform
knowledge_type: hierarchy
platform: tiktok
source: TikTok for Business API 官方文档 + TikTok Capability/Skill
source_ref: https://business-api.tiktok.com/portal/docs?id=1739373164384257
version: "1.0.0"
confidence: 0.88
updated_at: "2026-09-08"
tags: [tiktok, advertiser, campaign, ad-group, ad, smart-plus, spark]
status: published
---

# TikTok Ads 账户、层级与投放目标

## 资源树

```text
Advertiser Account
  └── Campaign（objective / campaign type / budget boundary）
         └── Ad Group（promotion、预算、排期、版位、定向、优化、出价）
                └── Ad（视频/图片/轮播、身份、文案、CTA、追踪）
Assets: video / image / creative portfolio / identity
Commerce: catalog ── product set
Measurement: pixel ── events / audience
App: app ── install / in-app event
```

Campaign 是业务目标与预算模式的上层容器，Ad Group 是可投放策略单元，Ad 是素材和身份单元。Campaign、Ad Group、Ad 的父级必须属于同一 advertiser；不能把 TikTok item、Spark 内容、上传视频、identity、Pixel、Catalog 的 ID 混用。

## 目标与 promotion

常见方向包括 Reach、Traffic、Video Views、Community Interaction、Lead Generation、App Promotion、Web Conversion、Product Sales 等。名称和可用组合随地区、账户和 API 版本变化，始终以当前 Tool schema 的 `objective_type`、`promotion_type`、`optimization_goal`、`billing_event` 枚举为准。

| 目标 | 主要信号 | 投放前提 |
|---|---|---|
| Reach/Views | reach、impressions、视频观看 | 素材、频控与品牌安全 |
| Traffic | clicks、landing page view | 页面、追踪与加载性能 |
| Lead | 表单/线索事件 | 隐私政策、表单与线索回传 |
| App | install、注册、付费事件 | app_id、商店/深链与 MMP/事件 |
| Product Sales | 商品/购买价值 | Catalog、Product Set、商品状态 |

Smart+、Automated/AI 形态可能把更多控制权交给系统。它们不是“普通 Campaign 改个名字”，要单独检查当前账号资格、接口版本、可控字段和 live 状态。

## 当前能力边界

当前项目覆盖 advertiser、Campaign、Ad Group、Ad、素材、Creative Portfolio、Identity、Audience、Pixel/Event、Catalog/Product Set lookup、App、Report、定向参考和 Brand Safety 等已注册能力；Catalog/Product Set 写入、某些自动化规则和 Pixel 删除仍应按 surface inventory 的 planned/not_applicable 标记处理，不可从知识文档推断为可执行。
