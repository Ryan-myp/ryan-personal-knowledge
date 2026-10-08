---
schema_version: "1"
id: google-canonical-campaign-and-search-runbook
title: Google Ads Campaign 与 Search 实战操作手册
layer: platform
knowledge_type: workflow
category: campaign_operations
subcategory: canonical-campaign-and-search-runbook
platform: google-ads
source: Google Ads API 官方文档与当前 Tool Source 约束
source_ref: "https://developers.google.com/google-ads/api/docs/campaigns/overview"
version: "1.0.0"
confidence: 0.91
updated_at: "2026-09-08"
tags: [google-ads, campaign, ad-group, search, keyword, responsive-search-ad, mutate, dry-run]
status: published
source_kind: "official"
authority: "official"
evidence_level: "reviewed"
last_verified_at: "2026-09-08"
---

# Google Ads Campaign 与 Search 实战操作手册

本篇把 Google Search 从需求澄清到上线验证拆成可重放的步骤。它区分“业务要达成什么”“Google 资源如何承载”“当前 Tool 是否允许执行”三个问题，避免把知识建议误当成可直接发送的 API 请求。

## 资源关系

```text
Customer / Manager
  -> Campaign + CampaignBudget + BiddingStrategy
      -> AdGroup
          -> AdGroupCriterion（Keyword / Negative / Audience 等）
          -> AdGroupAd -> Ad / ResponsiveSearchAd
      -> CampaignCriterion（地域、语言等）
      -> CampaignAsset / Asset
  -> ConversionAction / CustomerConversionGoal
```

| 资源 | 主要职责 | 变更前必查 |
|---|---|---|
| Customer | 账户、时区、币种和权限边界 | customer ID、manager 关系、账户状态 |
| Campaign | 目标、网络、状态、预算和策略 | advertising channel、目标、状态、策略类型 |
| CampaignBudget | 日预算和共享关系 | 是否被多个 Campaign 共享、币种和当前值 |
| AdGroup | 查询意图和广告承接单元 | 父 Campaign、状态、默认出价和名称 |
| Criterion | 关键词、否定、地域和其他资格 | 绑定层级、匹配范围、重复和状态 |
| AdGroupAd | 广告状态和广告类型 | 父 AdGroup、policy 状态、资产组合 |
| ConversionAction | 优化信号和价值 | primary/secondary、状态、来源和延迟 |

名称只用于展示，资源 ID 和 resource name 才是关系事实。创建、更新、暂停、恢复和删除前都要读取现状，不能用用户输入的名称推断唯一对象。

## 创建前决策表

| 业务输入 | 需要转换成 | 缺失时的处理 |
|---|---|---|
| 业务目标 | Campaign 类型、目标和优化事件 | 先澄清，不创建通用 Campaign |
| 市场范围 | 地域、语言、时区和落地页 | 检查合规与页面可用性 |
| 获客目标 | Keyword/Ad Group 主题和否定词 | 生成关键词草案供确认 |
| 成本约束 | Budget、bid strategy、目标成本 | 说明目标不是保证值 |
| 素材 | 标题、描述、最终 URL 和资产 | 校验数量、长度、政策和 URL |
| 业务结果 | Conversion Action、价值和去重 | 先修测量，不用点击替代成交 |

## 标准创建顺序

1. 读取 Customer、已有 Campaign、预算、转化动作和当前 Tool schema。
2. 对名称、父资源、币种、日期、URL、目标和字段依赖做 preflight。
3. 生成 Campaign、Budget、Ad Group、Criterion 和 Ad 的 dry-run 资源图。
4. 在明确 live、权限、白名单、确认和幂等键后按父子依赖提交。
5. 保存每个 operation 的资源 ID、partial failure、request context 和审计摘要。
6. 回读资源状态、审核状态、广告资产状态和报告可见性。

写入对象初始建议保持可控状态，待页面、转化和审核验证后再进入正式交付；具体状态字段以当前 schema 为准。

## 关键词与广告组设计

广告组的边界应由搜索意图、落地页承诺和可解释的预算/报表需求决定。过度拆分会稀释学习，完全混合会让否定词、文案和页面无法解释。

| 检查 | 通过标准 | 常见问题 |
|---|---|---|
| 意图 | 关键词与页面解决同一任务 | 信息型词直接导向购买页面 |
| 匹配 | 匹配范围与获客风险相称 | 只依赖宽泛匹配而没有否定体系 |
| 否定 | 误触发主题有可审计记录 | 否定词误伤高价值查询 |
| 文案 | 标题/描述与意图、页面一致 | 只堆关键词，不提供证据 |
| 页面 | URL、速度、移动端、事件可用 | 点击有量但转化链路断裂 |

新增关键词不能只看单日 CTR；要结合查询质量、转化成熟度、有效线索/订单和边际成本。

## 更新边界

**可以小步更新**：文案变体、资产补充、单个否定词、页面追踪参数和明确错误的标签配置。

**需要谨慎更新**：Campaign 预算、出价目标、优化事件、匹配范围、地域、语言和大量关键词。一次只改变一个主变量并设置回退。

**不能假设可更新**：已创建资源的不可变字段、平台审核结果、动态枚举、账户级目标和跨资源继承关系。先查询当前 Tool schema，不用文档字段猜测能力。

## 失败恢复

| 错误类别 | 是否重试 | 恢复方式 |
|---|---:|---|
| 网络超时/暂时服务错误 | 有上限重试 | 先用幂等键或回读确认是否已生效 |
| 字段/组合不合法 | 否 | 依据 schema 修正后重新生成计划 |
| 权限/客户关系错误 | 否 | 检查 principal、manager 和账户范围 |
| policy/审核失败 | 否 | 修复资产或提交审核，不重复创建 |
| partial failure | 只重试失败项 | 保留成功资源，按 operation 定位 |
| 状态未知 | 先回读 | 不做重复创建或删除 |

## 上线验收

- Campaign、Budget、Ad Group、Criterion 和 Ad 的父子关系可回读。
- 预算、时区、币种、状态和目标与 dry-run 计划一致。
- 广告审核状态、最终 URL 和追踪参数已验证。
- 转化事件接收、去重、价值和 primary/secondary 口径已确认。
- 第一份报表保存查询契约、日期、时区、分段和数据成熟度。
- 任何问题都能通过 resource ID、operation、时间和审计记录定位。

## 官方参考

- [Campaigns overview](https://developers.google.com/google-ads/api/docs/campaigns/overview)
- [Ad groups and ads](https://developers.google.com/google-ads/api/docs/campaigns/ad-groups)
- [Keywords](https://developers.google.com/google-ads/api/docs/campaigns/targeting/keywords)
- [Mutate guide](https://developers.google.com/google-ads/api/docs/mutation/overview)
