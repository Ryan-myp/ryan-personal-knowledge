---
schema_version: "1"
id: dv360-reporting-and-diagnostics
title: DV360 报表生命周期、费用口径与诊断
layer: platform
knowledge_type: workflow
platform: dv360
source: Display & Video 360 API Reporting 官方文档 + 当前 Capability
source_ref: https://developers.google.com/display-video/api/concepts/reporting
version: "1.0.0"
confidence: 0.86
updated_at: "2026-09-08"
tags: [dv360, report, async, dimensions, metrics, cost, attribution, diagnostics]
status: published
---

# DV360 报表生命周期、费用口径与诊断

## 三阶段状态

```text
创建 report definition -> 异步运行 -> result ready/failed -> 下载/解释
```

Definition 创建成功不等于报告结果生成，result 可读不等于数据已最终结算。每次查询保存 advertiser、日期/时区、维度、指标、过滤、币种、费用口径、数据 freshness、run/result 关系和轮询边界。

## 指标分组

| 指标组 | 用途 | 必须补充 |
|---|---|---|
| Delivery | impressions、spend、reach、frequency | 去重、币种、媒体成本定义 |
| Media quality | viewability、completion、invalid traffic | 测量供应商、分母和可用样本 |
| Engagement | clicks、CTR、video interaction | 点击有效性与页面到达 |
| Conversion | conversions、CPA、revenue | 归因窗口、来源、延迟与去重 |
| Business | margin、qualified lead、LTV | 后端数据、cohort、增量设计 |

## 费用口径

媒体成本、平台服务费、数据费、技术费和总成本可能是不同字段。预算 pacing、媒体效率和财务结算不能用同一个 spend 字段代替；跨 IO、Line Item 或 partner 汇总前先确认币种、时区、层级和费用口径。

## 报表为空或不一致

1. 查 advertiser/partner 权限与资源归属。
2. 查时间窗口、账户时区、过滤和维度指标兼容性。
3. 查 report definition、运行状态、result 是否 ready 以及异步超时。
4. 查数据 freshness、归因延迟、时段切分和分页/导出限制。
5. 与交付日志、平台界面、后端转化和订单/CRM 对账。

空结果不是零投放；异步未完成不能补零；平台归因不等于增量。报告解释中明确“未生成”“无匹配”“数据尚未最终结算”三种状态。

## 优化反馈

把报告变成动作需要连接对象层级：Campaign/IO 判断预算与方向，Line Item 判断出价/库存/定向，Creative 判断审核与素材，业务后端判断价值和增量。每次动作记录假设、字段、风险、观察窗口、回滚和审计 ID。

## 当前执行边界

当前 Capability 支持部分异步报告创建/读取和 Line Item 报告。具体可用的 report definition、维度/指标组合、导出和 live 状态以当前 Tool schema 与账户权限为准。
