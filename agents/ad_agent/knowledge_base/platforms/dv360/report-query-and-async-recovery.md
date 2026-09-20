---
schema_version: "1"
id: dv360-report-query-and-async-recovery
title: DV360 报表查询、异步任务与数据一致性手册
layer: platform
knowledge_type: error_pattern
category: diagnostics
subcategory: report-query-and-async-recovery
platform: dv360
source: Display & Video 360 API 官方文档
source_ref: "https://developers.google.com/display-video/api"
version: "1.0.0"
confidence: 0.93
updated_at: "2026-09-08"
tags: [dv360, reporting, asynchronous, line-item, brand-safety, recovery]
status: published
source_kind: "official"
authority: "official"
evidence_level: "reviewed"
last_verified_at: "2026-09-08"
---

# DV360 报表查询、异步任务与数据一致性手册

DV360 的 Partner、Advertiser、Campaign、Insertion Order、Line Item、Creative 和 Targeting Assignment 处于不同资源层级。报告和投放资源也不是同一套生命周期：对象可能已经创建，但仍在审核、排期、库存匹配或数据刷新阶段。

## 报告任务生命周期

1. 先确认 Partner/Advertiser 范围、时区、币种和可访问资源。
2. 定义报表的主体资源、维度、指标、过滤、日期范围和归因口径。
3. 创建或读取 report definition，保存任务标识和契约摘要。
4. 轮询任务状态时使用固定间隔、总超时和最大次数，状态未就绪不能当作空数据。
5. 结果 ready 后分批读取或导出，记录生成时间、行数、分页和失败分片。

## 口径与排障

| 问题 | 优先检查 | 结论边界 |
|---|---|---|
| 无展示或花费 | 飞行日期、IO/Line Item 状态、预算、定向、库存 | 先区分资格不足与报告延迟 |
| 报告为空 | 任务状态、过滤、维度兼容、时区和日期 | 空结果不等于零交付 |
| 指标跳变 | 分段粒度、费用口径、归因窗口和刷新时间 | 不要把不同快照直接拼接 |
| 素材不投放 | 审核、格式、关联、落地页和品牌安全 | 不要只改出价 |
| 任务超时 | 结果规模、查询复杂度、轮询预算 | 缩小查询后重新规划 |

## 恢复与优化

异步任务超时后先读取任务状态；若状态未知，不能重复创建同一报告。报告下载失败时保留任务标识并从失败分片恢复。Line Item 的出价、频控、库存和定向修改要区分计划、线上生效和报告反映三个时间点；优化建议需带观察窗口和数据新鲜度。

跨平台比较时保留 DV360 的供应商、去重、可见性、品牌安全和归因口径。CPM、CTR、转化和 ROAS 只有在日期、币种、事件定义和窗口一致时才可以进入统一决策。

## 官方参考

- [Display & Video 360 API](https://developers.google.com/display-video/api)
- [Reports API](https://developers.google.com/display-video/api/guides/how-tos/reports)
- [Line items](https://developers.google.com/display-video/api/reference/rest/v3/advertisers.lineItems)
