---
schema_version: "1"
id: dv360-optimization-and-measurement
title: DV360 采购、品牌安全与报表优化
layer: platform
knowledge_type: best_practice
platform: dv360
source: Display & Video 360 官方文档 + DV360 运营 Skill
source_ref: https://developers.google.com/display-video/api/concepts/reporting
version: "1.0.0"
confidence: 0.88
updated_at: "2026-09-08"
tags: [dv360, programmatic, viewability, reach, frequency, reporting, optimization]
status: published
---

# DV360 采购、品牌安全与报表优化

## 优化顺序

```text
tracking / cost definition
  -> delivery eligibility
  -> inventory quality and brand safety
  -> reach / frequency / viewability
  -> creative and landing page
  -> bid / budget / targeting experiment
```

先确认是否真的有资格交付，再讨论效率。低交付可能来自预算、飞行、创意审核、库存、定向过窄、出价竞争或频控；不能看到 spend 低就直接抬价。

## 关键指标

| 方向 | 指标 | 解读注意 |
|---|---|---|
| 交付 | impressions、reach、frequency、spend | 明确去重口径、币种和时间窗口 |
| 媒体质量 | viewability、video completion、brand safety | 供应商和测量方案可能不同 |
| 流量 | clicks、CTR、CPC | 点击不代表有效访问 |
| 转化 | conversions、CPA、revenue/ROAS | 归因来源、窗口和延迟必须标注 |
| 增量 | lift、实验组/对照组差异 | 不能用平台归因替代增量 |

## 报告生命周期

```text
report definition -> accepted -> running -> result ready/failed -> export/interpretation
```

Report definition 创建成功不代表结果可读，结果可读也不代表数据已最终结算。每次报告固定 advertiser、日期/时区、维度、指标、过滤、币种、数据新鲜度和异步状态；不同 partner、advertiser、媒体类型或费用口径的数据不能直接相加。

## 实验与决策

用 IO/Line Item 做可解释的策略切片，控制单次只改变一个变量。先设定成功指标、保护指标、最小花费/样本、运行周期和停止规则；素材、供应、定向、出价和品牌安全不要同时大范围改动。对 reach/frequency、viewability 和转化效率要按漏斗阶段平衡，不以单一 CTR 代表媒体价值。
