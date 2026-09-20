---
schema_version: "1"
id: dv360-line-item-targeting-and-supply-quality
title: DV360 Line Item 定向、库存质量与频次控制
layer: platform
knowledge_type: best_practice
category: optimization
subcategory: line-item-targeting-and-supply-quality
platform: dv360
source: Display & Video 360 官方文档
source_ref: "https://support.google.com/displayvideo"
version: "1.0.0"
confidence: 0.9
updated_at: "2026-09-08"
tags: [dv360, line-item, targeting, inventory, viewability, frequency, brand-safety]
status: published
source_kind: "official"
authority: "official"
evidence_level: "reviewed"
last_verified_at: "2026-09-08"
---

# DV360 Line Item 定向、库存质量与频次控制

DV360 的预算、出价、定向、库存、频控和品牌安全通常在 IO 与 Line Item 之间共同生效。排查交付时必须先定位设置属于哪一层，再确认 assignment、deal、库存资格和审批状态；不能把 Line Item 结果简单归因给一个定向字段。

## 交付排查路径

1. 查 Partner/Advertiser、Campaign/IO/Line Item 的状态、飞行日期、预算和币种。
2. 查 Line Item 出价策略、频次、定向 assignment、版位、设备、地域和库存来源。
3. 查 Deal/Exchange、品牌安全、内容分类、可见性和素材审批是否共同限制资格。
4. 查展示、花费、reach、frequency、viewability、视频完成和转化，并固定供应商与归因口径。
5. 对修改后的对象记录生效时间，等待报告数据刷新后再判断结果。

## 定向不是越多越好

定向层叠可能把可用库存压得过窄，排除规则也可能与包含规则冲突。每次调整只改变一个主要边界，记录预期影响、库存规模、频次和保护指标。先区分“没有资格”与“竞价输掉”：前者看设置、审批和库存，后者看出价、质量、竞争和边际成本。

## 质量与频次

| 目标 | 主要指标 | 解读边界 |
|---|---|---|
| 规模 | impressions、reach、spend | 明确去重口径和飞行节奏 |
| 媒体质量 | viewability、completion、brand safety | 测量供应商和样本可能不同 |
| 控制疲劳 | frequency、unique reach、CTR/CVR | 频次上升要结合创意和人群容量 |
| 结果效率 | conversions、CPA、revenue/ROAS | 固定归因窗口、延迟和币种 |

品牌安全和库存质量不是事后报表装饰，而是预算放量的保护条件。出现低可见性、异常站点、频次集中或转化质量恶化时，先拆供应商、库存、设备、地域和素材，再决定收紧或扩展。

## API 与异步报告

读取和变更分开规划；报告任务要保存 definition、状态、生成时间、分页和下载结果。异步任务超时先读取状态，不能把未 ready 当空数据，也不能重复创建同一报告。Line Item 更新完成后，分别记录 API 成功、线上状态和报告可见三个时间点。

## 官方参考

- [Display & Video 360 Help](https://support.google.com/displayvideo)
- [Display & Video 360 API](https://developers.google.com/display-video/api)
- [Reports API](https://developers.google.com/display-video/api/guides/how-tos/reports)
