---
schema_version: "1"
id: dv360-deals-auctions-and-bid-strategy
title: DV360 Deal、竞价与库存放量方法
layer: platform
knowledge_type: best_practice
category: optimization
subcategory: deals-auctions-and-bid-strategy
platform: dv360
source: Display & Video 360 官方文档
source_ref: "https://support.google.com/displayvideo/topic/6048435"
version: "1.0.0"
confidence: 0.89
updated_at: "2026-09-08"
tags: [dv360, deals, auction, bidding, inventory, pacing, supply-path]
status: published
source_kind: "official"
authority: "official"
evidence_level: "reviewed"
last_verified_at: "2026-09-08"
---

# DV360 Deal、竞价与库存放量方法

DV360 的规模与效率来自“可用库存 × 资格过滤 × 竞价竞争 × 预算节奏 × 测量质量”的乘积。Deal、开放竞价、定向、品牌安全和出价策略会在不同层级共同作用；只调高 bid 不一定增加有效交付。

## 采购对象

先确认库存来源、Exchange、Deal 或 Package、媒体环境、设备、地域、格式、飞行时间和审批。Deal 可能有固定价格、底价、优先级、最低量或独立的媒体质量特征；不能把 Deal 的高完成率或低 CPA 无条件推广到开放库存。

| 交付问题 | 先拆分 | 可能动作 |
|---|---|---|
| 无展示 | 资格、Deal 状态、日期、审批、定向 | 修正资源或等待生效 |
| 资格有但竞价输 | bid、底价、竞争、质量 | 小幅测试出价与边际成本 |
| 花费不足 | 库存规模、频控、品牌安全、目标约束 | 逐个放宽可接受约束 |
| 花费过快 | pacing、库存集中、频次和出价 | 限制节奏并保留质量护栏 |
| 转化不稳 | Floodlight、供应商、版位和延迟 | 先查测量再动策略 |

## 出价决策

出价调整要同时看 win rate、有效展示、可见性、完成率、频次、边际 CPA/价值和库存质量。平均 CPA 低但增量库存质量差时，不应继续放量；出价高而无展示，优先确认是资格限制还是竞价竞争。

一次只改变一个主要约束，记录基线、变化量、观察窗口、保护指标和回退条件。预算、出价、定向、品牌安全和频控不要同步大改，否则无法知道哪一项改变了库存或效率。

## 库存质量

供应路径、可见性、无效流量、品牌安全、内容分类、站点/应用、设备和频次要按投放目标设为护栏。质量指标可能来自不同测量供应商，需保留测量定义、样本和延迟；不要把一个供应商的分数当作绝对真相。

频次控制要按用户、设备、渠道、Line Item 和活动目标确认范围。频次过高可能是人群过窄或供应集中，也可能是报告去重口径不同；先拆分再调频控。

## Deal 变更流程

发布前确认 Deal ID、买卖双方、有效期、媒体格式、价格、库存、审批和 Line Item 绑定。变更后分别记录 API 响应成功、线上状态变化、首次可竞价和报表可见四个时间点。超时或重复提交时先读取现状，不能盲目重复创建。

## API 与报告

报表任务需保存 definition、状态、生成时间、分页和下载校验；未完成不能当空数据。读取与写入分离，使用有界日期、字段和并发。具体 Deal、Targeting、Bid Strategy 和 Line Item 字段以当前 API schema 与账号能力为准。

## 竞价资格分层

```text
广告对象有效
  -> 飞行/预算/状态有效
  -> Deal 或 Exchange 可用
  -> Line Item 定向与品牌安全通过
  -> 库存格式、设备、地域和频控通过
  -> 出价进入竞价
  -> 赢标并产生有效展示
  -> 可见性/完成/转化/业务价值评估
```

“没有展示”必须定位到哪一层被过滤。资格失败不是提高 bid 能解决的；竞价输掉也不一定说明要无限加价，还要看底价、质量、竞争和边际价值。

## Deal 变更卡片

每次 Deal 变更至少记录：Deal ID、买卖双方、有效期、媒体格式、价格/底价、库存预期、Line Item 绑定、审批状态、品牌安全规则、预期生效时间和回退动作。变更后分开验证 API 响应、线上状态、首次可竞价和报告可见时间。

## 出价诊断

| 现象 | 证据顺序 | 决策 |
|---|---|---|
| win rate 低 | 底价、bid、竞争、质量 | 小步测试，观察边际成本 |
| win rate 高但转化差 | 供应商、版位、可见性、频次、Floodlight | 先拆质量，不盲目扩量 |
| Deal 花不出 | Deal 状态、库存、审批、定向、频控 | 修资格或分层扩库存 |
| 预算集中少数站点 | 供应路径、品牌安全、频次 | 设质量护栏和排除规则 |
| 频次过高 | 去重范围、用户容量、Line Item 叠加 | 调整频控或拆对象 |

## 典型案例：高质量 Deal 规模不足

先确认是库存有限、定向过窄、Deal 未生效还是竞价输掉；然后只放宽一个边界，例如设备或地域，保持品牌安全和可见性护栏。用新增展示的边际 CPA、可见性、完成率和有效转化评估，而不是拿 Deal 平均 CPA 与开放竞价平均 CPA 直接比较。

## 报告与恢复

异步报告失败时保留 query definition、任务 ID、状态、生成时间和原始错误；超时先查询原任务。下载失败只重试下载，不能重复创建购买或报告任务。Line Item 修改后等待报告刷新，分别标记 API 成功、投放生效和数据成熟。

## 官方参考

- [Display & Video 360 Help](https://support.google.com/displayvideo/topic/6048435)
- [Display & Video 360 API](https://developers.google.com/display-video/api)
- [Programmatic guaranteed and deals](https://support.google.com/displayvideo/answer/6208973)
