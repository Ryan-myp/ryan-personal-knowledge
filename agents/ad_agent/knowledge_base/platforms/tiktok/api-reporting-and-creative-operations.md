---
schema_version: "1"
id: tiktok-api-reporting-and-creative-operations
title: TikTok Marketing API 报表、素材与投放操作方法
layer: platform
knowledge_type: workflow
category: platform_foundation
subcategory: api-reporting-and-creative-operations
platform: tiktok
source: TikTok for Business API 官方文档
source_ref: https://business-api.tiktok.com/portal/docs
version: "1.0.0"
confidence: 0.9
updated_at: "2026-09-08"
tags: [tiktok, marketing-api, reporting, creative, spark-ads, events]
status: published
---

# TikTok Marketing API 报表、素材与投放操作方法

TikTok Ads 的 API 操作围绕 Advertiser、Campaign、Ad Group、Ad 和 Creative 展开，素材、身份、Pixel、Catalog 与受众是相互关联的资产。不同目标和产品线会改变必填字段与可用优化事件，不能用普通 Web Conversion 的参数模板覆盖 App、Lead、Commerce 或 Spark Ads。

## 层级与前置依赖

典型结构是 `Advertiser → Campaign → Ad Group → Ad`。Campaign 选择营销目标和预算策略；Ad Group 承载版位、定向、排期、出价、优化事件和素材使用条件；Ad 连接创意、身份、落地页与跟踪配置。

创建顺序应是：

1. 校验 advertiser 访问范围、时区、币种和账户状态。
2. 根据目标选择对应的 Campaign 类型和预算模型。
3. 创建 Ad Group，校验地域、年龄、设备、版位、排期、出价与优化事件。
4. 准备视频、图片、文案、展示名和身份资产，等待上传/审核状态可用。
5. 创建 Ad 并读取最终状态，确认跟踪 URL、Pixel/Event API 和落地页一致。

API 返回的状态不等于已经稳定交付。审核、学习、预算受限、素材疲劳和事件延迟都需要结合报表与诊断信息判断。

## 报表查询与分页

报表接口通常由 advertiser、dimensions、metrics、时间范围、粒度和过滤条件共同决定。先固定一套最小可用字段，再按 Campaign → Ad Group → Ad 下钻，避免一次请求过多维度导致响应慢或结果难以解释。

报表规范：

- 统一时区、日期边界、归因口径和货币单位。
- 分页读取时设置 page size、最大页数、超时和总行数上限。
- 把 spend、impressions、reach、clicks、CTR、conversions、CPA/ROAS 和 video play signals 分成经营、交付、创意三组。
- 以报表更新时间标注数据新鲜度，不把实时指标与归因完成数据混为一谈。
- 导出大报表时使用任务状态和下载生命周期，完成后只保留安全摘要和引用，不把全量明细塞进 Prompt。

## 创意与 Spark Ads

普通创意和 Spark Ads 的身份授权、帖子标识、使用期限、评论/互动语义不同。Spark Ads 需要确认授权状态、身份归属、帖子可用性和广告账户范围；不能把一个视频素材 ID 当作可任意复用的帖子授权。

创意测试按“角度 → 前三秒 → 叙事 → CTA → 落地页”拆分变量。保持受众、预算和优化事件稳定，给素材足够的观察窗口；将审核失败、低质量流量、播放完成率下降和转化率下降分开诊断。

## 事件与转化质量

Pixel 与 Events API 的事件名、事件时间、页面/应用来源、内容参数、货币和价值要保持一致。事件发送要做去重、重试上限和敏感字段保护。广告优化事件必须能在报表中稳定回流，否则先解决事件链路和归因配置，不要直接增加预算。

## 变更、限流与恢复

写入前必须完成 dry-run：列出目标对象、当前状态、计划状态、预算/出价差异、素材影响、预计学习期和失败处理。限流或网络超时只能在幂等保护下有限重试；参数、权限、审核和业务规则错误需要修正计划。部分成功后重新拉取 Campaign、Ad Group 和 Ad 状态，再决定补偿动作。

## 官方参考

- [TikTok for Business API 文档](https://business-api.tiktok.com/portal/docs)
- [Campaign Management](https://business-api.tiktok.com/portal/docs?id=1739373164384257)
- [Reporting](https://business-api.tiktok.com/portal/docs?id=1738865680951297)
- [Events API](https://business-api.tiktok.com/portal/docs?id=1738865671534594)
- [Creative Center](https://ads.tiktok.com/business/creativecenter/inspiration)
