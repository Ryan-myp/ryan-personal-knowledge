---
schema_version: "1"
id: tiktok-canonical-campaign-and-adgroup-runbook
title: TikTok Campaign、Ad Group 与创意安全操作手册
layer: platform
knowledge_type: workflow
category: campaign_operations
subcategory: canonical-campaign-and-adgroup-runbook
platform: tiktok
source: TikTok Marketing API 官方文档与当前 Tool Source 约束
source_ref: "https://business-api.tiktok.com/portal/docs?id=1738865457882113"
version: "1.0.0"
confidence: 0.88
updated_at: "2026-09-08"
tags: [tiktok, advertiser, campaign, ad-group, ad, creative, smart-plus, spark, reporting]
status: published
source_kind: "official"
authority: "official"
evidence_level: "reviewed"
last_verified_at: "2026-09-08"
---

# TikTok Campaign、Ad Group 与创意安全操作手册

TikTok 的 Campaign 负责业务目标，Ad Group 负责预算、排期、定向、版位、优化和出价，Ad/Creative 负责素材、身份、落地页和追踪。Smart+ 会扩大系统自动探索，Spark Ads 会引入有机帖子和身份授权，两种模式不能用同一套创意验收。

## 资源关系

```text
Business Center / Advertiser
  -> Campaign（objective、状态）
      -> Ad Group（budget、schedule、placement、targeting、optimization、bid）
          -> Ad（creative、identity、landing page、tracking）
              -> Video/Image/Spark Identity/Creative Portfolio
  -> Pixel / Events API / MMP
  -> Report（dimensions、metrics、date）
```

| 资源 | 主要职责 | 依赖 |
|---|---|---|
| Advertiser | 账户、币种、时区、权限和数据归属 | principal、白名单和账户状态 |
| Campaign | objective、名称、状态和整体边界 | 目标必须与业务结果一致 |
| Ad Group | 预算、排期、版位、受众、优化和出价 | 事件、市场、库存和素材供给 |
| Ad | 身份、Creative、页面和追踪 | 素材、授权、审核和链接 |
| Pixel/Events API | 事件与归因信号 | event_id、时间、金额、Consent |
| Report | 交付与结果聚合 | advertiser、层级、维度、分页和延迟 |

## 创建前决策表

| 输入 | 要落到的字段族 | 必须补齐的证据 |
|---|---|---|
| 业务目标 | Campaign objective | 购买、Lead、App、流量或品牌目标 |
| 优化事件 | Ad Group optimization | 事件密度、后端质量、延迟和去重 |
| 预算约束 | budget mode、budget、schedule | 日内节奏、币种、容量和护栏 |
| 受众市场 | location、language、device、audience | 合规、容量、重叠和排除 |
| 素材模式 | single video、Spark、Smart+ 等 | 授权、身份、音乐、页面和版位 |
| 成功标准 | report metrics + CRM/MMP | 归因窗口、有效结果和 cohort |

## 标准创建顺序

1. 读取 Advertiser、Campaign、Ad Group、Pixel、Identity、Creative 和账户能力。
2. 明确 objective、预算类型、优化事件、出价类型、市场和素材模式。
3. 生成父子资源图和字段依赖检查，默认 dry-run。
4. 依赖顺序创建 Campaign、Ad Group、Creative/Identity、Ad，并保留响应。
5. 回读审核、授权、线上状态、事件接收、首个报告和数据延迟。
6. 通过固定观察窗口确认交付和有效结果，再决定是否调整。

## Smart+ 与普通投放

Smart+ 的价值是扩大自动探索，不是免除素材、事件和业务边界。创建前至少记录可探索变量和不可突破的边界：

| 变量 | 可探索示例 | 保护边界 |
|---|---|---|
| 受众 | 广泛兴趣或自动扩展 | 市场、合规、排除和年龄限制 |
| 素材 | 多角度视频组合 | 品牌资产、授权和内容政策 |
| 预算 | 系统在对象间分配 | 日预算、利润和库存容量 |
| 事件 | 优化深层结果 | 去重、价值、延迟和后端质量 |

## Spark Ads 专项检查

- 原帖、身份、授权码/授权状态和授权期限可回读。
- 原帖内容、评论、音乐、商标、达人权益和品牌安全已经确认。
- 原帖删除、编辑或授权失效时有暂停和替换流程。
- 追踪链接、落地页、事件和后端订单与有机内容承诺一致。
- 超时或未知状态先查询线上 Ad/Creative，不重复创建。

## 素材测试单元

把 Hook、场景、痛点、证明、产品演示、优惠和 CTA 分成变量；记录素材 ID、版本、首发时间、市场、身份、版位和事件。高播放只说明内容被看见，不能替代点击、转化、有效率和留存。

## 更新边界

预算、目标事件、出价、版位、受众、身份和素材的变更会分别影响学习、资格、审核或报告。每次更新只改变一个主变量，保存旧值、变更原因、预期方向、保护指标和回退动作。平台动态枚举、字段条件和可写范围必须以当前 Tool schema 为准。

## 报表与数据延迟

报告固定 advertiser、对象层级、dimensions、metrics、日期粒度、时区、归因窗口和分页。`pending`、`partial`、`empty`、`failed` 和 `success` 不可混用；未完成报告不能当作零花费或零转化。

## 失败恢复

| 现象 | 先查 | 恢复 |
|---|---|---|
| Campaign 创建失败 | objective、账户状态、字段组合 | 修 schema，不重复提交 |
| Ad Group 花不出 | 审核、预算、事件、定向、库存 | 定位资格与竞价边界 |
| Spark 失效 | 原帖、身份、授权、音乐和页面 | 暂停失效创意，重新验证 |
| 事件翻倍 | event_id、重试和批量发送 | 回查状态，按事件幂等恢复 |
| 报表不完整 | 分页、任务状态、时区和延迟 | 从最后完整页恢复 |

## 上线验收

- Advertiser、Campaign、Ad Group、Ad 和 Creative 父子关系闭环。
- 预算、排期、市场、版位、优化事件和出价与计划一致。
- Spark/普通素材的身份、授权、链接、审核和版本可追溯。
- Pixel/Events API/MMP 事件有稳定 ID、去重、价值和后端对账。
- 报告查询可复现，数据状态和延迟已标记。
- 每次变更都有 dry-run、确认、审计、幂等和回退记录。

## 官方参考

- [TikTok Business API](https://business-api.tiktok.com/portal/docs)
- [Reporting API](https://business-api.tiktok.com/portal/docs?id=1738865457882113)
- [Spark Ads](https://ads.tiktok.com/business/help/article/spark-ads)
- [TikTok Business Help Center](https://ads.tiktok.com/business/help)
