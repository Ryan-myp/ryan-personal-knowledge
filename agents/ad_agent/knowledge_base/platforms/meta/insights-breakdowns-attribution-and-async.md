---
schema_version: "1"
id: meta-insights-breakdowns-attribution-and-async
title: Meta Insights 分层报表、Breakdown 与异步查询
layer: platform
knowledge_type: workflow
category: measurement
subcategory: insights-breakdowns-attribution-and-async
platform: meta
source: Meta Marketing API 官方文档
source_ref: https://developers.facebook.com/docs/marketing-api/insights
version: "1.0.0"
confidence: 0.9
updated_at: "2026-09-08"
tags: [meta, insights, breakdowns, attribution, async, pagination, reporting]
status: published
---

# Meta Insights 分层报表、Breakdown 与异步查询

Meta Insights 是按请求契约返回的聚合视图，不是一个永远固定的事实表。level、fields、breakdowns、time_range、time_increment、action_breakdowns 和 attribution settings 改变后，结果的粒度、可加性和含义都会变化。

## 报表请求契约

每个结果保存账户、对象层级、对象 ID、日期范围、账户时区、币种、字段、breakdown、归因设置、分页游标、拉取时间和数据新鲜度。比较两个周期前先确认请求契约一致，否则“指标变化”可能只是报表定义变化。

| 目的 | 推荐主层级 | 需要特别注明 |
|---|---|---|
| 预算节奏 | Campaign/Ad Set + day | 账户时区和当天不完整数据 |
| 素材筛选 | Ad + creative | 素材不是独立随机实验单元 |
| 受众诊断 | Ad Set + audience breakdown | 重叠与归因不可直接相加 |
| 事件漏斗 | action breakdown | 事件发生和归因口径 |
| 跨期复盘 | 固定层级与字段 | 归因窗口和回补延迟 |

## Breakdown 与重复计数

年龄、性别、地域、版位、设备、平台和行动类型会把同一对象拆成多行。独立覆盖人数、频次和归因转化不能在不同 breakdown 行之间简单求和；花费、展示和点击也要确认维度是否互斥。报告层应保存原始行和聚合规则，不能用去重脚本掩盖粒度错误。

出现总数与分 breakdown 汇总不一致时，依次检查非互斥维度、estimated metrics、归因回补、字段定义和时间范围。若 breakdown 组合不受 API 支持，应修改查询契约，而不是把错误响应当成空数据。

## 异步与分页

大范围 Insights 查询可能需要异步任务。任务状态、结果分页、生成时间和请求定义必须持久化；未完成、失败、权限错误、空结果和确实没有数据是不同状态。网络超时后先查询原任务状态，带幂等标识，不能不确定时重复创建任务。

游标分页要持续读取直到没有下一页，并设置最大页数、最大字节数和超时。导出文件应记录校验信息和数据版本；部分下载不能被标记为成功报表。

## 归因解释

平台归因反映 Meta 在所选窗口和设置下分配的结果，不等同于增量。iOS、同意、建模、跨设备和事件回传都会影响可见性。出现 Meta、MMP、CRM 数字差异时，先对齐事件名、发生时间、时区、去重、归因窗口、过滤器和退款，再做业务判断。

## 诊断流程

1. 复现同一请求契约，确认账户与资源权限。
2. 用小日期和最小字段集验证资源有数据。
3. 逐个增加 breakdown 与 action breakdown，定位不兼容组合。
4. 对比 raw rows、汇总规则、分页完整性和任务状态。
5. 标记数据延迟、建模和归因回补，再进入优化决策。

## API 边界

字段和 breakdown 的合法组合以当前 Marketing API 版本 schema 为准；本篇不注册能力、不替代权限校验。读取默认有界并缓存可复用元数据，写入必须走已注册 Tool 的 dry-run、live gate、确认、幂等和审计链路。

## API 请求与结果模型

常见读取边界是 Ad Account、Campaign、Ad Set、Ad、Creative 与 Insights。每次请求把对象层级、字段、breakdown、日期、时区、归因设置和分页游标当作一个不可拆的查询版本。对象列表与 Insights 结果不要默认一对一 join：对象状态可能实时变化，报表可能延迟回补。

| 阶段 | 应保存的证据 | 失败恢复 |
|---|---|---|
| 请求创建 | account/object、query 摘要、时间范围 | 参数/权限错误直接修复 |
| 分页读取 | cursor、页序、行数、响应时间 | 从最后完整页恢复 |
| 异步任务 | task ID、状态、definition、生成时间 | 先查原任务，禁止盲目重建 |
| 聚合入库 | 原始行、粒度、去重和公式 | partial 不得覆盖 success |
| 对账 | 平台、MMP/CRM、订单快照 | 标记延迟与口径差异 |

## Breakdown 可加性矩阵

| 指标 | 通常可在互斥维度求和 | 需要谨慎 |
|---|---|---|
| spend、impressions | 在相同日期和互斥粒度 | 过滤器、估算和舍入 |
| clicks、link clicks | 先确认指标定义 | 不同 click 类型可能重叠 |
| conversions | 通常不可跨 action 直接相加 | 事件去重、归因窗口、回补 |
| reach、frequency | 不可简单跨对象相加 | 去重范围和估算方法 |
| revenue、purchase value | 需固定订单与币种 | 退款、重复购买和价值延迟 |

## 典型案例：Ad Set 汇总大于 Campaign

先确认 Campaign 与 Ad Set 查询是否在同一日期、字段、归因设置和账户时区；再检查 Ad Set 是否存在重叠 breakdown、估算指标或分页漏读。不要用 `DISTINCT` 直接压平，因为这可能删掉合法的分段行。输出应同时给出原始总量、分段总量、不可加指标和差异原因；无法证明可加时标记为不可用于预算调度。

## 异步任务恢复策略

任务状态必须至少区分 pending、running、completed、failed、expired 和 partial。客户端重启后根据 definition hash 找回未完成任务；同一任务已完成则复用结果，下载失败只重试下载，不重复创建报表。报告文件保存大小、页数、校验信息和生成时间，部分文件不覆盖上一份完整快照。

## 官方参考

- [Insights API](https://developers.facebook.com/docs/marketing-api/insights)
- [Insights breakdowns](https://developers.facebook.com/docs/marketing-api/insights/breakdowns)
- [Ads insights attribution](https://developers.facebook.com/docs/marketing-api/insights/parameters)
