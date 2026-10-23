---
schema_version: "1"
id: google-ads-entity
title: Google Ads
layer: platform
wiki_type: entity
knowledge_type: general
platform: google-ads
source: 项目内已复核的 Google Ads Runbook
source_ref: platforms/google/canonical-campaign-and-search-runbook.md
source_kind: internal
authority: repository
evidence_level: reviewed
last_verified_at: "2026-10-18"
version: "1.1.0"
confidence: 0.93
updated_at: "2026-10-18"
tags: [google-ads, google, Google广告, 广告平台, 渠道介绍, 基础知识, campaign, search, shopping, performance-max]
status: published
---

# Google 广告平台

Google Ads 是覆盖搜索、购物、应用、视频和自动化投放等场景的广告平台。基础资源关系通常从 Customer 开始，经由 Campaign、Ad Group 连接到 Ad、Keyword 或素材资源；具体子资源取决于 Campaign 类型。

Search 以搜索意图、关键词、广告相关性和落地页为核心；Shopping 与 Performance Max 更依赖 Merchant Center 商品数据，PMax 还使用 Asset Group 等素材与商品资源。平台原生支持不代表本 Agent 已开放相同范围的执行 Tool；动态字段、账户资格和实际可执行能力以当前 Tool schema 与账户回读为准。

## 知识入口

- [[Google Ads Campaign 与 Search 实战操作手册]]：资源关系、创建前检查、执行顺序与回读。
- [[Google Search 关键词、广告相关性与查询优化]]：Search 结构、搜索词与相关性诊断。
- [[Google Shopping 与 PMax 商品源、资产组和放量方法]]：商品 Feed、Listing Group、Asset Group 与价值评估。
- [[Google Ads API 资源操作、GAQL 与报表方法]]：GAQL、分页、报表口径和 API 错误处理。
