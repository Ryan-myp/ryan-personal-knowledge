---
schema_version: "1"
id: cross-platform-ad-hierarchy
title: 四平台广告层级对照与账户设计
layer: business
knowledge_type: general
platform: all
source: 四平台官方文档 + 当前 ad_agent Capability/Skill
source_ref: agents/ad_agent/capabilities/*/_surface_data.py
version: "1.0.0"
confidence: 0.9
updated_at: "2026-09-08"
tags: [cross-platform, hierarchy, account-structure, campaign, ad-group, ad-set, line-item]
status: published
---

# 四平台广告层级对照与账户设计

## 统一抽象

```text
身份/账户 scope
  -> 目标与预算组织层（Campaign 或同类容器）
  -> 策略执行层（Ad Group / Ad Set / IO-Line Item）
  -> 创意与追踪层（Ad / Creative / Asset）
  -> 测量与回传（Conversion / Pixel / CAPI / Report）
```

这只是业务抽象，不是 API 字段映射。任何写入仍需使用对应渠道的 Tool schema、父级 ID 和权限门禁。

## 层级对照

| 平台 | 账户边界 | 主要投放层级 | 策略/预算位置 | 创意关系 |
|---|---|---|---|---|
| Google Ads | Customer | Campaign → AdGroup → Ad/Keyword | Campaign Budget + Campaign bidding | Ad/Asset；PMax 使用 Asset Group |
| Meta | Business/Ad Account | Campaign → Ad Set → Ad | Campaign 或 Ad Set，视预算模式 | Ad → Creative，依赖 Page/IG/素材 |
| TikTok | Advertiser | Campaign → Ad Group → Ad | Ad Group 为主要策略单元 | Ad 内素材/身份/追踪，Spark 为授权内容 |
| DV360 | Partner → Advertiser | Campaign/IO → Line Item | IO 与 Line Item 分担预算/飞行 | Creative 关联到 Line Item |

## 设计原则

- 一个策略单元只承载一个主要业务目标、优化事件、地区/时区和成本模型；需要严格对照的变量拆开，需要规模的变量不要无限拆分。
- 父级只解决组织，不代表子级一定可投放。审核、资产、定向、事件、预算、日期和权限都要单独通过。
- 账户命名至少包含业务、市场、漏斗、目标、平台原生层级和版本；不要把易变的预算、状态写进唯一身份。
- 统一看板可以抽象成 spend、impressions、clicks、conversions、value，但原始字段、归因窗口、币种和数据延迟必须保留。
- 跨平台复制的是业务意图和实验设计，不是 objective、placement、bid 或 targeting 枚举的字符串。

## 建议的最小规划卡

每次创建前先形成一张卡：业务目标、主转化/价值、平台与账户、市场/时区、预算与周期、漏斗阶段、受众假设、素材来源、归因方案、成功/保护指标、当前 Tool 覆盖、dry-run 与回滚方式。缺任一关键字段时进入 needs_input，不用默认值“猜”出投放方案。
