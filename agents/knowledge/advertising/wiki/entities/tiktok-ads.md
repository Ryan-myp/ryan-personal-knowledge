---
schema_version: "1"
id: tiktok-ads-entity
title: TikTok Ads
layer: platform
wiki_type: entity
knowledge_type: general
platform: tiktok
source: 项目内已复核的 TikTok Ads Runbook
source_ref: platforms/tiktok/canonical-campaign-and-adgroup-runbook.md
source_kind: internal
authority: repository
evidence_level: reviewed
last_verified_at: "2026-10-18"
version: "1.1.0"
confidence: 0.93
updated_at: "2026-10-18"
tags: [tiktok, TikTok广告, 广告平台, 渠道介绍, 基础知识, campaign, ad-group, creative, spark, smart-plus]
status: published
---

# TikTok Ads

TikTok Ads 通过 Advertiser 账户管理广告。常见资源链路是 Advertiser → Campaign → Ad Group → Ad：Campaign 确定业务目标，Ad Group 配置预算、排期、受众、版位、优化和出价，Ad/Creative 承载素材、身份、落地页与追踪。

普通广告、Smart+ 和 Spark Ads 的素材来源、自动化程度与授权要求不同，不能使用同一套验收条件。Pixel、Events API 或 MMP 事件还要与优化目标、去重和后端业务结果对齐。

平台原生能力不等于 Agent 当前可执行能力；动态枚举、账户资格和写入范围以当前 Tool schema 与账户回读为准。

## 知识入口

- [[TikTok Campaign、Ad Group 与创意安全操作手册]]：层级、创建前决策、更新和回读。
- [[TikTok Smart+、Spark Ads 与创意规模化方法]]：自动探索、Spark 身份授权和创意测试。
- [[TikTok 创意生命周期、Spark 与素材测试]]：素材状态、变量设计和表现诊断。
- [[TikTok Pixel、Events API 与归因信号]]：事件、去重、身份和归因边界。
