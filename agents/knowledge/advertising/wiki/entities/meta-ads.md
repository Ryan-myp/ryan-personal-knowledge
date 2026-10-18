---
schema_version: "1"
id: meta-ads-entity
title: Meta Ads
layer: platform
wiki_type: entity
knowledge_type: general
platform: meta
source: 项目内已复核的 Meta Ads Runbook
source_ref: platforms/meta/canonical-campaign-and-adset-runbook.md
source_kind: internal
authority: repository
evidence_level: reviewed
last_verified_at: "2026-10-18"
version: "1.1.0"
confidence: 0.93
updated_at: "2026-10-18"
tags: [meta, facebook ads, Instagram广告, 广告平台, 渠道介绍, 基础知识, campaign, ad-set, creative, advantage-plus]
status: published
---

# Meta Ads

Meta Ads 覆盖 Facebook、Instagram 等 Meta 媒体上的广告投放。常见资源链路是 Ad Account → Campaign → Ad Set → Ad；Creative 承载素材、文案、身份、链接和追踪信息。

Campaign 表达业务目标和上层预算策略；Ad Set 负责预算/排期、受众、版位与优化事件；Ad 和 Creative 负责具体呈现。Catalog Sales、线索、应用推广等是业务场景，不能只凭名称推断它们对应独立 Campaign objective；需要结合目标映射与 Ad Set 优化设置理解。

平台原生能力与本 Agent 当前注册的 Tool 覆盖范围是两回事；字段、权限和可执行能力以当前 Tool schema 与账户回读为准。

## 知识入口

- [[Meta Campaign、Ad Set 与广告安全操作手册]]：资源层级、创建依赖、更新边界和失败恢复。
- [[Meta 投放目标选择：从业务结果到 Campaign Objective]]：业务结果、Campaign objective 与 Ad Set 优化目标的关系。
- [[Meta Catalog、Lead 与转化质量运营]]：商品目录和线索场景的主要前置条件。
- [[Meta Insights 分层报表、Breakdown 与异步查询]]：报表粒度、归因窗口和异步查询边界。
