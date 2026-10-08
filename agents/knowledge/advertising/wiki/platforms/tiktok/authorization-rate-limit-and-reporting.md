---
schema_version: "1"
id: tiktok-authorization-rate-limit-and-reporting
title: TikTok Ads API 授权、限流与报表排障手册
layer: platform
knowledge_type: error_pattern
category: diagnostics
subcategory: authorization-rate-limit-and-reporting
platform: tiktok
source: TikTok for Business API 官方文档
source_ref: "https://business-api.tiktok.com/portal/docs"
version: "1.0.0"
confidence: 0.9
updated_at: "2026-09-08"
tags: [tiktok, ads-api, authorization, rate-limit, reports, async]
status: published
source_kind: "official"
authority: "official"
evidence_level: "reviewed"
last_verified_at: "2026-09-08"
---

# TikTok Ads API 授权、限流与报表排障手册

TikTok Ads API 的 Advertiser、Campaign、Ad Group、Ad、Creative、Pixel 和 Catalog 有不同的访问边界。接口返回成功不等于广告已交付；创建、审核、学习、报告可见是不同阶段，Agent 要把状态拆开记录。

## 读取与写入边界

- 读取前确认 Advertiser 范围、账户时区、币种、状态过滤和分页游标。
- 创建前确认 Campaign objective、预算模式、优化事件、定向、身份素材和追踪参数的组合约束。
- Spark、应用、商品和线索场景需要额外确认授权内容、应用/商品资产、事件和落地承接。
- 写入使用幂等键；超时后先读取目标对象，不能因为没有即时响应就重复创建。

## 报表一致性

报告至少要保留 advertiser、时间窗口、时区、指标、维度、归因口径和数据更新时间。按日、广告组、素材或版位拆分时，行粒度已经变化，不能与汇总接口直接相加。平台归因、事件接收、MMP/后端订单和退款是不同数据层，不能用其中一层替代另一层。

## 常见异常决策树

| 现象 | 先检查 | 不要做 |
|---|---|---|
| 花费为零 | 审核、排期、预算、库存、定向和账户状态 | 不要先判断接口失效 |
| 报表为空 | 日期时区、分页、维度组合和数据延迟 | 不要用空结果覆盖历史 |
| 转化少 | Pixel/CAPI/SDK 事件、去重、延迟和事件映射 | 不要马上切深层目标 |
| 请求被限流 | 并发、页大小、重复读取和窗口 | 不要无限重试 |
| 素材审核失败 | 资产、文案、落地页和政策类别 | 不要改成无关素材绕过审核 |

## 失败恢复

将错误分为参数、权限、策略/审核、限流、网络暂时异常和未知状态。只有最后两类中明确可重试的部分使用带上限的退避；未知状态先做 readback。批量动作出现部分成功时，按广告对象重读状态，分别输出成功、可重试和人工处理队列。

## 官方参考

- [TikTok for Business API portal](https://business-api.tiktok.com/portal/docs)
- [Business API rate limits](https://business-api.tiktok.com/portal/docs?id=1738373164385281)
