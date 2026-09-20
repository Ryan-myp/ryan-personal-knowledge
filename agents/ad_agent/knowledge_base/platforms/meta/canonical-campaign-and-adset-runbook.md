---
schema_version: "1"
id: meta-canonical-campaign-and-adset-runbook
title: Meta Campaign、Ad Set 与广告安全操作手册
layer: platform
knowledge_type: workflow
category: campaign_operations
subcategory: canonical-campaign-and-adset-runbook
platform: meta
source: Meta Marketing API 官方文档与当前 Capability 约束
source_ref: "https://developers.facebook.com/docs/marketing-api/campaigns"
version: "1.0.0"
confidence: 0.9
updated_at: "2026-09-08"
tags: [meta, campaign, ad-set, ad, creative, objective, optimization-goal, graph-api, dry-run]
status: published
source_kind: "official"
authority: "official"
evidence_level: "reviewed"
last_verified_at: "2026-09-08"
---

# Meta Campaign、Ad Set 与广告安全操作手册

Meta 的 Campaign、Ad Set、Ad 和 Creative 是不同职责的资源。Campaign 目标决定上层方向，Ad Set 控制预算、排期、受众和优化事件，Ad/Creative 承载素材、身份、链接和追踪。不要用 Campaign 名称或广告页面展示顺序替代资源关系。

## 资源关系与依赖

```text
Business / Ad Account / Page / Pixel or Dataset
  -> Campaign（objective、status、budget strategy）
      -> Ad Set（budget、schedule、targeting、optimization、promoted object）
          -> Ad（creative、tracking、status）
              -> Creative（object story、素材、文案、链接、身份）
```

| 资源 | 核心字段族 | 依赖/边界 |
|---|---|---|
| Campaign | objective、status、buying type、预算分配方式 | 目标与特殊广告类别可能限制下层选项 |
| Ad Set | daily/lifetime budget、schedule、targeting、optimization goal、billing | 预算与优化事件必须匹配目标和信号 |
| Ad | creative、tracking、status、Ad Set ID | Creative、页面/身份和链接必须可用 |
| Creative | 素材、文案、对象故事、CTA、URL | 素材审批、版位适配和政策约束 |
| Pixel/Dataset | 事件、参数、去重和来源 | 事件必须与 Ad Set 优化语义一致 |
| Insights | level、fields、breakdowns、time range | 结果受归因设置、延迟和分页影响 |

## 创建前澄清

| 问题 | 为什么必须问 |
|---|---|
| 业务结果是购买、有效线索、安装还是互动？ | 决定 objective、优化事件和后端验收 |
| 使用 Campaign 预算还是 Ad Set 预算？ | 决定预算控制边界和实验隔离方式 |
| 是否属于特殊广告类别？ | 可能改变受众、地域和素材约束 |
| 页面、Instagram 身份、Pixel/Dataset 是否可用？ | 决定 Creative、追踪和事件能否交付 |
| 事件是否有稳定 event_id 和价值？ | 决定是否可安全用于优化 |
| 目标受众是否需要排除、再营销或增量测试？ | 防止广泛探索吞掉业务边界 |

## 标准创建顺序

1. 在可信账户范围内读取 Campaign、Ad Set、Page、Creative、Dataset 和事件状态。
2. 确定 objective、特殊广告类别、预算分配方式、优化事件和素材身份。
3. 校验 Ad Set 的预算、排期、受众、版位、推广对象和事件依赖。
4. 创建 Campaign 后再创建 Ad Set、Creative 和 Ad；新对象先保持可控状态。
5. 保存 Graph object ID、请求摘要、响应、审核状态、幂等键和 partial failure。
6. 回读线上状态、审核、事件接收和 Insights 可见性，不以接口成功作为上线完成。

## 预算和优化事件组合

预算与优化事件不是独立下拉框。选择深层事件时要确认事件密度、延迟、去重、价值、退款和 CRM 质量；选择浅层事件时要说明它可能带来更多样本但更弱的业务意图。

| 情况 | 优先动作 | 不要做 |
|---|---|---|
| 事件稳定且业务价值清楚 | 小步使用深层事件 | 同时大改预算和受众 |
| 事件稀疏但页面正常 | 先验证链路与窗口 | 用虚假 micro event 充量 |
| 购买有量但退款高 | 接入后端质量和价值 | 只看平台 ROAS 放量 |
| 多 Ad Set 需要严格隔离 | 使用明确预算边界 | 让自动分配破坏实验设计 |
| 需要探索新受众 | 记录扩展边界和排除 | 把自动扩展当作无约束 |

## Creative 与 Ad 更新边界

补充新素材通常比覆盖线上 winner 更容易回退；替换素材、修改身份、落地页、CTA、追踪或推广对象会改变学习与审核。每次更新保存旧 Creative ID、素材版本、页面、事件和生效时间。

不要通过删除重建来解决未知状态。超时先查询 Ad/Creative 状态；审核失败先读取错误详情；页面或素材变更后重新验证版位、政策和事件。

## Insights 报告契约

报告必须记录 Ad Account、level、fields、breakdowns、time_range、time_increment、归因设置、时区、币种、分页和任务状态。Reach、frequency、conversions 和 value 的可加性要单独注明；不能把 Ad、Ad Set 和 Campaign 三个层级结果直接相加。

## 失败恢复

| 现象 | 第一定位 | 恢复方式 |
|---|---|---|
| 创建失败 | 目标、类别、权限、父 ID 和字段组合 | 修计划，不重复提交 |
| 审核失败 | Creative、文案、页面和政策 | 修素材或页面，保留版本 |
| 花费不足 | 预算、目标成本、受众容量、事件 | 一次放宽一个边界 |
| CAPI 事件翻倍 | event_id、事件名和订单 ID | 修去重，冻结扩量 |
| Insights 为空 | 日期、层级、breakdown、分页/异步 | 区分空结果与未完成 |
| 超时未知 | 回读对象或任务状态 | 幂等恢复，不盲目重建 |

## 上线验收

- Campaign objective、类别、预算分配和状态与计划一致。
- Ad Set 的预算、排期、受众、版位、优化事件和推广对象可回读。
- Ad、Creative、Page/Identity、URL、参数和审核状态闭环。
- Pixel/CAPI 事件能按 event_id 去重，后端订单或线索可对账。
- Insights 查询可复现，分页完整，数据延迟与归因口径已标记。
- 变更可通过旧版本、资源 ID、审计记录和回退条件恢复。

## 官方参考

- [Marketing API](https://developers.facebook.com/docs/marketing-api)
- [Campaigns](https://developers.facebook.com/docs/marketing-api/campaigns)
- [Ad sets](https://developers.facebook.com/docs/marketing-api/adsets)
- [Ads and creatives](https://developers.facebook.com/docs/marketing-api/ads)
