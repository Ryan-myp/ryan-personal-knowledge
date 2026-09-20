---
schema_version: "1"
id: dv360-canonical-io-lineitem-runbook
title: DV360 IO、Line Item、Deal 与定向安全操作手册
layer: platform
knowledge_type: workflow
category: campaign_operations
subcategory: canonical-io-lineitem-runbook
platform: dv360
source: Display & Video 360 官方文档与当前 Capability 约束
source_ref: "https://developers.google.com/display-video/api"
version: "1.0.0"
confidence: 0.9
updated_at: "2026-09-08"
tags: [dv360, advertiser, campaign, insertion-order, line-item, deal, targeting, floodlight, report]
status: published
source_kind: "official"
authority: "official"
evidence_level: "reviewed"
last_verified_at: "2026-09-08"
---

# DV360 IO、Line Item、Deal 与定向安全操作手册

DV360 的采购控制分布在 Campaign、Insertion Order、Line Item、Creative、Targeting Assignment、Deal 和 Floodlight 等资源。排查和变更必须先定位设置所在层级；“Line Item 没展示”不是一个足够具体的故障描述。

## 对象关系

```text
Partner
  -> Advertiser
      -> Campaign
          -> Insertion Order（预算、日期、目标）
              -> Line Item（竞价、节奏、定向、频控）
                  -> Ad / Creative
                  -> Targeting Assignment
      -> Deal / Exchange / Inventory
      -> Floodlight Configuration / Activity
      -> Report Query / Async Report
```

| 资源 | 主要职责 | 变更前必查 |
|---|---|---|
| Partner/Advertiser | 账户范围、币种、时区、权限 | principal、父子关系和状态 |
| Campaign | 业务活动和时间边界 | 归属、日期和报告口径 |
| IO | 预算、飞行、目标和预算层级 | 预算、日期、费用和父 Campaign |
| Line Item | 出价、pacing、定向、频控和库存 | 状态、类型、父 IO 和当前配置 |
| Creative | 素材、格式、审批和落地页 | 规格、政策、关联和状态 |
| Targeting Assignment | 地域、设备、受众、内容、Deal 等 | 包含/排除、继承和冲突 |
| Deal | 私有库存、价格、买卖双方和有效期 | Deal 状态、库存、审批和绑定 |
| Floodlight | 转化活动、计数和值 | 配置归属、活动、去重和 Consent |

## “无展示”四分法

```text
资源无效？ -> 状态、日期、预算、审批、父级
库存无资格？ -> Deal、格式、地域、设备、品牌安全、定向
有资格但竞价输？ -> bid、底价、竞争、质量、频控
展示有但结果差？ -> 可见性、完成率、频次、Floodlight、业务质量
```

每一类都需要不同动作。提高 bid 只能尝试竞价层，不能修复 Creative 审核、Deal 失效或 Floodlight 丢失。

## 标准采购流程

1. 确认 Partner、Advertiser、Campaign、IO、Line Item 和采购目标。
2. 读取预算、飞行日期、币种、竞价策略、频控、定向、Deal、Creative 和 Floodlight。
3. 建立包含继承关系的 dry-run 配置图，识别包含/排除冲突。
4. 按父子依赖创建或更新，Targeting Assignment 和 Creative 变更单独审计。
5. 回读 API 状态、线上生效、首次可竞价、首次展示和报告可见时间。
6. 在成熟窗口内比较 spend、win rate、viewability、frequency、conversion 和业务价值。

## 定向与库存设计

定向叠加会缩小库存，排除可能与包含规则或父级继承冲突。每次改变一个主要边界，并预估库存、频次、质量和成本变化。

| 定向族 | 适用目的 | 诊断问题 |
|---|---|---|
| 地域/设备/环境 | 市场和媒介适配 | 是否把有效库存过滤掉 |
| 受众 | 再营销、名单或增量 | 入池延迟、同意和最小规模 |
| 内容/品牌安全 | 风险控制 | 质量提升是否牺牲过多规模 |
| Deal/Exchange | 采购路径和媒体质量 | Deal 是否有效、库存是否可竞价 |
| 频控 | 控制疲劳和用户体验 | Line Item/IO/Campaign 是否叠加 |

质量护栏应包含可见性、无效流量、内容风险、供应商集中、频次和有效转化，而不是只看 CPA。

## Deal 变更卡

变更前记录 Deal ID、买卖双方、有效期、价格/底价、格式、库存预期、审批、Line Item 绑定和回退方案。变更后分别记录 API 响应、线上状态、首次可竞价、首次展示和报告可见，不把接口成功当成媒体已生效。

## Floodlight 与优化

转化活动要明确事件名、计数方式、价值、发生时间、时区、Consent、订单 ID 和活动归属。Floodlight 接收、归因、进入优化和报告可见是不同状态；平台转化高于 CRM 时先查重复、计数、测试流量、退款和归因窗口。

## 报表任务与恢复

异步报告保存 query definition、任务 ID、状态、生成时间、页数、下载结果和校验信息。`pending`/`running` 不能当空数据；下载超时只重试下载，不重复创建报告任务；部分文件不能覆盖上一份完整快照。

## 更新边界

IO 预算和飞行、Line Item 出价和节奏、Targeting Assignment、Deal 绑定、Creative 审批和 Floodlight 目标应分开变更。每次变更有明确父资源、字段差异、影响范围、保护指标和回退条件；当前 API schema 与账户能力优先于本篇的概念映射。

## 失败恢复

| 错误类别 | 典型原因 | 恢复动作 |
|---|---|---|
| 父资源错误 | Advertiser/IO/Line Item 关系不对 | 重新读取层级，不猜 ID |
| 资格失败 | 状态、日期、审批、Deal 或定向 | 修资格，再检查库存 |
| 竞价失败 | bid、底价、竞争或质量 | 小步测试，保留质量护栏 |
| 报告未完成 | 异步任务或下载不完整 | 查询原任务，按页恢复 |
| 转化差异 | Floodlight、计数、归因、退款 | 对账后再改优化目标 |
| 状态未知 | 超时或重复提交风险 | 回读，不盲目重建/删除 |

## 上线验收

- Partner、Advertiser、Campaign、IO、Line Item 和 Creative 关系可回读。
- 预算、飞行、竞价、pacing、频控和定向符合 dry-run 计划。
- Deal、Targeting Assignment、品牌安全和审批状态可追踪。
- Floodlight 事件、计数、价值、去重和 CRM 对账闭环。
- 报告任务有完整 definition、状态、分页、下载校验和成熟度。
- API 成功、线上生效、首次交付和报告可见时间分别记录。

## 官方参考

- [Display & Video 360 API](https://developers.google.com/display-video/api)
- [Resources and methods](https://developers.google.com/display-video/api/reference/rest)
- [Targeting](https://developers.google.com/display-video/api/guides/how-tos/targeting)
- [Reports](https://developers.google.com/display-video/api/guides/how-tos/reports)
