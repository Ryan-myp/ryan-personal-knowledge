---
schema_version: "1"
id: dv360-programmatic-buying-and-quality
title: DV360 程序化采购、库存质量与品牌安全
layer: platform
knowledge_type: best_practice
platform: dv360
source: Display & Video 360 官方文档 + 程序化投放方法论
source_ref: "https://support.google.com/displayvideo/topic/6042460"
version: "1.0.0"
confidence: 0.84
updated_at: "2026-09-08"
tags: [dv360, programmatic, open-auction, deal, inventory, brand-safety, viewability, frequency]
status: published
source_kind: "official"
authority: "official"
evidence_level: "reviewed"
last_verified_at: "2026-09-08"
---

# DV360 程序化采购、库存质量与品牌安全

## 采购选择

| 采购路径 | 适用判断 | 主要风险 |
|---|---|---|
| Open Auction | 需要规模与可探索库存 | 质量、价格和供给波动 |
| Preferred Deal | 有议价库存、需要优先机会 | 价格、交付和受众限制 |
| Programmatic Guaranteed | 有确定库存/交付承诺 | 排期、素材和变更灵活性较低 |
| 私有市场/定向供应 | 重视媒体环境或特定受众 | 可扩量规模与数据权限 |

采购类型不是 Line Item 名称的装饰字段，它会影响库存、出价、定向、预算、创意和交付承诺。选择前确认 partner/advertiser、deal/inventory source、媒体格式、时间、货币和责任方。

## 质量指标

不要以 CTR 单独评价程序化媒体。至少同时看可见性、视频完成、无效流量/品牌安全、reach/frequency、媒体成本、增量转化和落地页质量。供应商、测量方案、去重方式和费用口径不同，指标不可直接相加；报告应保留原始来源。

## 品牌安全层次

品牌安全、敏感内容、库存级别、排除名单、频控和地域是不同控制面。先确定品牌风险容忍度与行业政策，再配置可验证的 targeting/assignment；不能笼统写“已开启品牌安全”而不说明具体类型、层级、来源和覆盖。

## 交付诊断

```text
Line Item active?
  -> flight / budget / pacing valid?
  -> creative approved and associated?
  -> targeting option valid and not over-constrained?
  -> eligible inventory / deal available?
  -> bid competitive and frequency not exhausted?
```

每一层都要有证据。仅增加预算或提高出价可能扩大成本而不解决创意审核、库存稀缺或定向冲突。

## 频控与触达

频控要结合目标：品牌触达关注有效覆盖与频次分布，转化关注重复曝光收益和边际 CPA。频次过低可能无法形成记忆，过高可能造成浪费和负反馈。按人群、设备、环境、市场和时间窗口拆分分析，避免把不同口径混成一个平均值。

## 当前执行边界

项目当前覆盖 Advertiser、IO、Line Item、Creative、Targeting Assignment 和 Report 的基础 Tool；Audience、Inventory Source、更多格式与 Campaign 创建存在 planned/未覆盖边界，不能把本文采购建议直接变成未注册动作。
