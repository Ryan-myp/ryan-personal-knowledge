---
schema_version: "1"
id: google-api-operations-and-reporting
title: Google Ads API 资源操作、GAQL 与报表方法
layer: platform
knowledge_type: workflow
category: platform_foundation
subcategory: api-operations-and-reporting
platform: google-ads
source: Google Ads API 官方文档
source_ref: https://developers.google.com/google-ads/api/docs/start
version: "1.0.0"
confidence: 0.94
updated_at: "2026-09-08"
tags: [google-ads, api, gaql, mutate, reporting, quota]
status: published
---

# Google Ads API 资源操作、GAQL 与报表方法

Google Ads API 是资源图谱和批量变更接口，不是把网页端按钮逐一搬到 API 的简单封装。任何 Agent 操作都应先定位资源名称、确认父子关系，再决定使用读取、规划还是变更能力。

## 资源与服务边界

常见资源关系是 `Customer → Campaign → AdGroup → Ad/AdGroupCriterion`，预算、资产、转化动作和受众通常通过资源名称关联。读取时优先使用 Customer 级别的查询服务，写入时按资源归属选择对应服务；不要用用户提供的字符串直接拼接跨账户资源名称。

| 业务目的 | 典型资源 | 先确认的约束 |
|---|---|---|
| 账户发现 | CustomerClient | 登录账户是否有访问关系 |
| 投放结构 | Campaign、AdGroup | 父资源、状态、渠道类型 |
| 流量入口 | AdGroupCriterion、Keyword | 匹配类型、语言、地域、政策 |
| 创意资产 | Ad、Asset、AssetGroup | 字段可变性、审核状态、关联关系 |
| 转化测量 | ConversionAction | 转化来源、归因窗口、主次转化 |
| 经营分析 | 报表资源 | 日期范围、分段字段、指标兼容性 |

## GAQL 查询原则

GAQL 查询由资源、字段、过滤、排序和分页组成。`SELECT` 字段必须满足该资源的字段兼容性，不能把任意指标和任意分段自由拼在一起。生产查询应固定字段白名单，并在发送前做语法、日期和账户范围校验。

1. 先确定主资源，再添加必要的属性字段和指标。
2. 日期范围使用明确的账户时区语义，跨天报表不要混用本地时间和 UTC。
3. 先用小范围日期和少量字段验证，再扩大到完整报表。
4. 大结果集使用分页或流式读取，设置上限并记录查询摘要，不把全量数据放进模型上下文。
5. 查询失败时保留资源、字段、日期和 request context 的安全摘要，禁止把认证配置写入错误信息。

## Mutate 变更流程

变更通常以一组操作提交。Agent 生成变更计划时要列出资源名称、字段掩码、父资源和变更前后的值。更新只发送确实改变的字段；字段掩码遗漏会导致更新不生效，错误覆盖则可能破坏未意图修改的设置。

推荐流程：

1. 读取目标资源和关键父资源，确认账户、状态与当前版本。
2. 在本地完成枚举、必填字段、父子关系和字段可变性校验。
3. 先生成 dry-run 对比，包含影响资源数量、预算/出价变化和风险提示。
4. 用户确认后再通过统一 live gate 提交，写入使用幂等键并保存审计摘要。
5. 对部分失败结果逐项重读，区分已成功、可重试和需人工处理的资源，不声称整批自动回滚。

批量操作不是无条件原子事务。需要原子语义时明确使用服务支持的失败策略；对于跨服务或跨资源的连续变更，必须按步骤记录状态并设计恢复动作。

## 报表与优化闭环

报表字段要服务于决策，而不是追求字段数量。常见分析顺序是：花费与展示 → 点击与互动 → 转化数量 → 转化价值 → 成本与边际变化。分段字段会改变聚合粒度，加入设备、网络或日期分段后不要直接与未分段结果相加。

| 诊断信号 | 优先检查 | 不要直接下结论 |
|---|---|---|
| 花费为零 | 状态、预算、审核、日期与投放资格 | 不要立刻判断 API 失效 |
| 点击有、转化无 | 转化动作、Tag、延迟和归因窗口 | 不要只调低出价 |
| 成本突然升高 | 日期口径、分段变化、流量混合 | 不要把一天波动当趋势 |
| API 与界面不一致 | 账户时区、归因更新、数据刷新时间 | 不要混合不同时间点快照 |

## 配额、错误与版本

将错误分为认证/权限、参数校验、资源状态、配额限流、暂时性网络和未知服务错误。只有明确可重试的暂时性错误使用指数退避；参数错误先修正计划，权限错误不能通过重复请求解决。Google Ads API 版本升级时，检查字段弃用、枚举变化、服务方法和客户端版本，保留契约版本而不是静默改变语义。

## 官方参考

- [Getting started](https://developers.google.com/google-ads/api/docs/start)
- [Google Ads Query Language](https://developers.google.com/google-ads/api/docs/query/overview)
- [Mutate requests](https://developers.google.com/google-ads/api/docs/mutating/overview)
- [Reporting concepts](https://developers.google.com/google-ads/api/docs/reporting/overview)
- [Error codes](https://developers.google.com/google-ads/api/docs/errors/error-codes)
