---
schema_version: "1"
id: dv360-floodlight-conversions-and-attribution
title: DV360 Floodlight 转化、受众与归因口径
layer: platform
knowledge_type: workflow
category: measurement
subcategory: floodlight-conversions-and-attribution
platform: dv360
source: Display & Video 360 与 Campaign Manager 360 官方文档
source_ref: "https://developers.google.com/display-video/api/guides/how-tos/floodlight"
version: "1.0.0"
confidence: 0.89
updated_at: "2026-09-08"
tags: [dv360, floodlight, conversion, attribution, campaign-manager, audience]
status: published
source_kind: "official"
authority: "official"
evidence_level: "reviewed"
last_verified_at: "2026-09-08"
---

# DV360 Floodlight 转化、受众与归因口径

DV360 的转化测量通常涉及 Floodlight 配置、活动、标签或服务器事件、Campaign Manager 360 关联、受众和报表。排查时必须区分“事件发生”“被 Floodlight 接收”“被归因到展示/点击”“进入优化和报告”几个状态。

## Floodlight 结构

先确认 Partner/Advertiser、Floodlight 配置、活动组、活动名称、计数方式、价值和去重规则的归属。购买优化使用的转化活动必须与业务目标、资源层级、日期、时区和账户权限一致；测试活动不要混入生产优化目标。

| 对象 | 作用 | 诊断重点 |
|---|---|---|
| 配置 | 定义测量与关联边界 | 归属、版本、权限和关联状态 |
| 活动组 | 归类转化动作 | primary/secondary 语义和漏斗 |
| 活动 | 采集具体业务事件 | 标签、参数、计数、价值和去重 |
| 报表 | 展示交付与归因 | 时间、模型、延迟和过滤 |
| 受众 | 用于再营销或排除 | 入池延迟、资格和隐私限制 |

## 数据质量排查

1. 用测试流确认事件触发、传输和接收。
2. 对照订单或 CRM 的事件 ID、发生时间、状态和金额。
3. 检查 Floodlight 活动映射、计数方式、标签版本和 Consent。
4. 检查 Campaign Manager 360、DV360 和外部报表的归因窗口。
5. 等待报告回补后，再看 Line Item、媒体、设备和供应商分解。

平台转化少于后端时，先查标签/服务器事件、同意、匹配和活动配置；平台转化多于后端时，查重复、取消、测试流量和计数规则。差异要按口径差异、延迟差异和真正链路故障分类。

## 归因与优化

DV360 归因结果适合优化购买和比较媒体交付，不直接证明增量。报告必须声明归因模型、窗口、去重、跨设备/跨环境限制和是否包含建模数据。预算迁移前要结合后端收入、边际效率、品牌安全、可见性和增量实验。

## 受众使用边界

再营销、相似或受控名单的规模会受到同意、匹配、入池延迟、地域政策和最小规模限制。受众变小先查资格和刷新状态，不先放宽所有品牌安全或隐私边界。受众包含与排除规则应写入变更计划，避免跨层级继承造成不可解释的库存收缩。

## API 边界

读取按 Partner、Advertiser、Floodlight、Line Item 和报表任务分层，有界分页和异步状态必须保存。任何配置、活动或优化目标变更都先生成 dry-run，列出父资源、影响范围、幂等键、审批和回退条件；具体字段以当前 DV360 API schema 为准。

## 对象与数据流

```text
Partner / Advertiser
  -> Floodlight Configuration
      -> Activity Group -> Activity / tag / server event
  -> Campaign / IO / Line Item
      -> impression / click / conversion
  -> report / audience / optimization
  -> CRM / order / incrementality
```

Floodlight 活动的归属、计数和价值要与购买目标对应。活动接收成功、被广告触点归因、进入 Line Item 优化和在报告中可见是四个不同状态。

## 计数与价值检查

| 检查项 | 需要问清 | 典型影响 |
|---|---|---|
| 计数方式 | 每次、每次用户还是业务去重 | 转化量和 CPA 不可比 |
| 活动归属 | Partner/Advertiser/配置是否一致 | 事件进错账户或无法优化 |
| 价值 | 收入、毛利、固定值还是预测值 | ROAS 与财务口径偏离 |
| 时间 | 发生日、触达日、报告日和时区 | 最近日期看起来偏低 |
| 同意 | Web/App/地区的 Consent 状态 | 匹配与建模发生变化 |

订单、线索和退款应使用不同事件语义；更新订单状态时不能重复创建新的购买事件。离线或服务器事件要有稳定业务 ID、入队时间、接收状态和失败分类。

## 典型案例：DV360 转化比 CRM 高

先按活动、计数方式和日期拆分，确认是否把每次事件当成用户唯一；再核对测试流量、重复标签、取消订单、归因窗口和跨设备建模。若平台口径正确但 CRM 只统计成交，差异属于漏斗定义；若同一订单多次归因，修复去重和活动映射。不要用一个全局比例校正全部 Line Item。

## 受众与优化边界

用 Floodlight 受众前确认同意、入池延迟、最小规模、地域政策和排除关系。受众规模变小先查事件与资格，不盲目放宽品牌安全。转化目标变更要保留旧活动的历史报告，分批迁移并等待完整窗口。

## 官方参考

- [Display & Video 360 API](https://developers.google.com/display-video/api)
- [Floodlight guides](https://developers.google.com/display-video/api/guides/how-tos/floodlight)
- [Campaign Manager 360 Floodlight](https://support.google.com/campaignmanager/answer/2829346)
