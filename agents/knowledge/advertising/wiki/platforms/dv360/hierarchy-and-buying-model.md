---
schema_version: "1"
id: dv360-hierarchy-and-buying-model
title: DV360 Partner、Advertiser、IO 与 Line Item 层级
layer: platform
knowledge_type: hierarchy
platform: dv360
source: Display & Video 360 API 官方文档 + DV360 Tool Source/Skill
source_ref: "https://developers.google.com/display-video/api/concepts/structure"
version: "1.0.0"
confidence: 0.88
updated_at: "2026-09-08"
tags: [dv360, partner, advertiser, campaign, insertion-order, line-item, hierarchy]
status: published
source_kind: "official"
authority: "official"
evidence_level: "reviewed"
last_verified_at: "2026-09-08"
---

# DV360 Partner、Advertiser、IO 与 Line Item 层级

## 资源树

```text
Partner / Organization
  └── Advertiser（账户、币种、权限边界）
         ├── Campaign（组织与报告分组）
         ├── Insertion Order（预算、时间、购买方向）
         │      └── Line Item（出价、定向、库存、频控、创意关联）
         ├── Creative / Asset
         └── Report definition ── async run ── Report result
```

Campaign 通常用于组织和报告，IO 管理预算/飞行和购买方向，Line Item 承载具体执行策略。DV360 与 Google Ads 的 Campaign/Ad Group 不能直接类比：不要把 Google 的 AdGroup、关键词或 PMax 资产组字段映射到 DV360 Line Item。

## 采购模型

Open Auction、Preferred Deal、Programmatic Guaranteed 等采购路径的库存、交付承诺、议价和可用设置不同。选择前确认媒体供应、库存来源、购买类型、品牌安全、频控、可见性和预算责任层级；名称相同不代表执行字段相同。

## 关键状态

对象已创建不等于可投放。至少区分：父级存在、IO/Line Item 配置完整、定向已分配、创意已关联、创意审核通过、对象已激活、开始时间已到和有实际交付。跨 advertiser 复用 ID、只凭名称找父级或跳过 readback 都会造成误操作。

## 当前能力边界

当前项目覆盖 Advertiser/Campaign 查询、IO、Line Item、Creative、Targeting assignment 和异步 Report 的已注册基础能力；Campaign 创建、完整受众、库存来源和更多格式处于 planned 或未覆盖范围时，应明确告诉用户，不能以知识文档模拟成功。

## 预算与控制层映射

| 控制 | 优先定位 | 诊断问题 |
|---|---|---|
| 活动归属 | Campaign | 是否跨 IO 混淆复盘范围 |
| 总预算/飞行 | IO | 日期、预算、费用和 pacing 是否一致 |
| 竞价/定向/频控 | Line Item | 是否过窄、叠加或与 Deal 冲突 |
| 素材/格式 | Creative/Ad | 审批、规格、落地页和身份是否通过 |
| 结果/转化 | Floodlight/Report | 计数、归因、延迟和后端是否一致 |

同一个 Line Item 可能同时继承 IO、Campaign、Deal 和 Targeting Assignment 的限制。变更前画出父级和继承关系，变更后分别回读配置与交付，不用单个 UI 状态判断全链路生效。
