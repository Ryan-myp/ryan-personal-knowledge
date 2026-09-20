---
schema_version: "1"
id: google-conversion-tracking-and-enhanced-conversions
title: Google 转化追踪、增强型转化与离线回传
layer: platform
knowledge_type: workflow
category: measurement
subcategory: conversion-tracking-and-enhanced-conversions
platform: google-ads
source: Google Ads API 与 Google Ads 官方文档
source_ref: "https://developers.google.com/google-ads/api/docs/conversions/overview"
version: "1.0.0"
confidence: 0.9
updated_at: "2026-09-08"
tags: [google-ads, conversion, enhanced-conversions, offline-conversion, consent, deduplication]
status: published
source_kind: "official"
authority: "official"
evidence_level: "reviewed"
last_verified_at: "2026-09-08"
---

# Google 转化追踪、增强型转化与离线回传

Google Ads 的转化数据不是一个单独开关，而是“转化动作定义 → 事件采集 → 身份匹配 → 归因入模 → 报表呈现”的链路。优化前必须先确认使用的是哪一类转化动作、哪个来源和哪个归因口径；不能看到转化数下降就直接改出价。

## 转化动作设计

| 层级 | 需要确认 | 常见错误 |
|---|---|---|
| 业务目标 | 购买、有效线索、安装、订阅还是利润 | 把页面浏览当最终 KPI |
| 转化动作 | 名称、来源、类别、计数方式、价值 | 同一事件创建多个 primary |
| 优化状态 | primary/secondary、纳入账户级目标 | 报表有数但出价没有使用 |
| 价值 | 金额、币种、税费、退款和毛利口径 | 用固定微小价值代替真实差异 |
| 时间 | 发生时间、上传时间、回传延迟 | 用上传日替代转化发生日 |

电商优先使用订单级价值和稳定订单 ID；Lead Gen 要把线索提交与 CRM 合格、成交分层。短期可用于诊断的 secondary 事件不应未经验证就升级为 bidding 的 primary 目标。

## 事件链路排查

1. 确认网页、App、服务器或离线导入的来源与适用范围。
2. 检查事件是否在正确账户、客户层级和时区下产生。
3. 检查金额与币种，确认货币换算、退款、取消和重复订单处理。
4. 检查事件 ID、订单 ID、转化动作和去重规则，保存原始事件快照。
5. 对比事件接收、匹配、归因和报告可见四个时间点，不把延迟当丢失。
6. 最后才比较点击、成本、转化和价值，并标记数据成熟度。

## 增强型转化与同意

增强型转化会使用经允许的第一方数据帮助匹配转化，但它不是绕过 Consent 或隐私规则的补丁。接入前应确认同意状态、数据最小化、哈希/传输边界、地区政策和保留周期；不要把原始邮箱、手机号或其他敏感身份写入知识、日志或模型上下文。

出现匹配率或转化量变化时，先比较同意率、字段填充率、规范化、哈希方式、事件 ID、站点改版和浏览器限制。匹配率提升也不等于增量提升，仍要结合后端订单和实验评估。

## 离线转化回传

离线回传适合 CRM 合格线索、成交、退款修正等发生在广告点击之后的结果。每条记录应保留可审计的广告点击标识或受控匹配标识、转化动作、发生时间、价值、币种、业务状态和去重键。回传失败时按可重试、永久无效、过期或重复分类；不要无限重试过期或格式错误的记录。

## 诊断决策表

| 现象 | 优先验证 | 不要直接做 |
|---|---|---|
| 点击稳定、转化突然归零 | 事件触发、标签、Consent、目标状态、延迟 | 立即放宽目标 CPA |
| 平台转化高、订单低 | 去重、退款、订单状态、归因窗口 | 直接按平台收入扩预算 |
| 订单有、平台转化少 | 点击标识、匹配、服务器链路、导入状态 | 重复发送全部历史订单 |
| 价值波动大 | 币种、金额精度、订单取消、样本成熟度 | 用单日 ROAS 判定策略 |

## API 边界

读取时按 Customer、Conversion Action、数据诊断和报告资源分层查询，限定日期、字段和分页。任何转化动作或回传变更先生成 dry-run 计划，展示资源 ID、旧值、新值、影响范围、幂等键和回退条件；当前 Tool schema、账户权限和 API 版本优先于本知识文档。

## 从业务事件到 API 资源

| 业务动作 | Google Ads 资源 | 关键核对 |
|---|---|---|
| 定义优化目标 | `ConversionAction`、Customer/CustomerConversionGoal | action type、status、primary/secondary、价值设置 |
| 网站或 App 事件 | Tag、SDK 或服务器事件 | 事件名、时间、同意、去重和来源 |
| 点击后成交 | Click ID 相关上传资源 | click 标识、转化动作、发生时间、价值、币种 |
| 线索质量 | Offline conversion action | CRM 状态、回传延迟、重复与无效线索 |
| 业务报表 | `customer_*`、`campaign_*` 等 GAQL 资源 | 资源粒度、日期、分段、归因字段 |

资源表只是定位依据，不代表当前 Agent 已实现每个动作。具体读写能力要以 Registry Tool、账户权限和 API 版本为准。

## 状态机与回查

```text
业务事件发生
  -> 采集/排队
  -> 发送或导入
  -> 平台接收
  -> 匹配与去重
  -> 进入转化动作
  -> 归因/建模
  -> 报表回补
  -> 后端对账与优化
```

每个阶段都保存状态、时间戳和错误分类。`accepted` 不等于 `attributed`，`attributed` 不等于 `reported`；报表没有立即出现并不证明回传失败。重试只针对明确的暂时错误，并以业务事件 ID 保持幂等。

## 变更前后检查

**变更前**

- 导出当前 Conversion Action、目标设置、价值规则和最近成熟窗口。
- 明确本次是修采集、换 primary、调整价值，还是新增转化动作。
- 预估会影响哪些 Campaign/出价策略，设置保护指标和回退条件。

**变更后**

- 用受控测试事件验证接收、匹配、去重和价值。
- 对比事件接收量、有效订单/线索和平台报告，不只看接口 200。
- 等待一个完整归因窗口，并在记录中标明未成熟数据。
- 若失败，先回到上一个可验证配置，不删除已有历史动作。

## 典型案例：线索量没变但 CPA 飙升

先查 CRM 合格率是否下降，再查 Conversion Action 是否把低质量提交升级为 primary；之后核对 Consent、事件 ID 和离线成交回传延迟。若平台转化稳定而合格线索下降，问题不应归因于竞价；若平台转化也下降，才继续查事件触发、目标状态、预算和出价学习。结论需同时列出平台证据和业务证据。

## 官方参考

- [Google Ads API conversions overview](https://developers.google.com/google-ads/api/docs/conversions/overview)
- [Enhanced conversions](https://support.google.com/google-ads/answer/9888656)
- [Offline conversion imports](https://developers.google.com/google-ads/api/docs/conversions/upload-clicks)
