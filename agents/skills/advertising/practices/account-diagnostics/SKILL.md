---
name: account-diagnostics
description: "基于当前账户报表和可追溯证据进行广告账户审计、效果诊断与数据解读 (evidence-led ad account audit and performance diagnosis)"
version: "1.1.0"
namespace: advertising
triggers:
  - [账户诊断, 账户审计, 广告账户体检, 广告账户审计, 广告账户做审计, 账户表现诊断, account audit, account diagnosis, performance diagnosis, performance audit]
  - [搜索词报告, search terms report, wasted spend, 浪费预算, 报表可信度, conversions 为零, 广告效果下降, why performance dropped]
  - [Meta Insights, Meta 广告报表, Meta Ads report, action_breakdowns, Meta breakdown, Meta 转化报表]
---

# 广告账户诊断与数据解读

本 Skill 用于解释当前广告账户查询结果、审计数据覆盖情况，并提出可验证的下一步检查。它补充 `evidence-driven-performance-diagnosis` 和渠道 Skill，不复制账户报表或渠道 API 能力。

## 诊断顺序

1. **确认数据来源。** 只把当前 Run 中已完成的只读 Tool 结果作为本次账户事实。确认账户范围来自可信 principal、报告属于预期渠道和层级，并查看结果是否明确标记为实时、模拟、缓存或部分完成。`simulated: true`、`data_status: offline_no_client`、固定测试夹具或无来源的手工汇总都不能作为真实账户证据。来源状态缺失时标为 Unknown。
2. **固定报告口径。** 写明渠道/账户范围、资源层级、日期区间及其时区、币种、归因设置、指标定义、过滤条件、分段维度、分页/异步状态和拉取时间。任一关键项不可确认时，限制比较结论。
3. **先判断报告完整性，再判断投放表现。** 区分真实零值、空结果、错误、未完成、部分页面、隐私省略、模拟结果和未知来源。报表调用成功不等于结果完整或适合决策。
4. **拆解异常并核对分母。** 先看交付和资格，再看点击/到站/转化/业务价值。每个比率都写清分子、分母、时间窗口与来源；分母缺失或为零时写“不可计算”，不得补成 0。
5. **提出最小、可证伪的后续检查。** 观察事实、推断、未知项分开陈述。每项建议写出支持它的证据、还缺的来源、影响层级和回看条件；数据不足时先补证据，不直接建议暂停、加预算或修改策略。

按需加载 references：

- `references/google-report-interpretation.md`：Google Ads 搜索词、转化和日期口径。
- `references/meta-insights-interpretation.md`：Meta Insights 分层指标、actions/action_values、归因与当前 Tool 查询边界。

## 证据标签

- **Verified**：本次 Run 的当前只读结果，来源和口径明确，且不是模拟或未完成结果。
- **Inferred**：由已核验结果推导，但仍有其他可能解释。
- **Stale**：来自历史报告、文档或用户回忆，必须附原始日期。
- **Unknown**：数据、权限、范围、成熟度或报告完整性不足以判断。

不能把 Inferred 或 Stale 写成 Verified；不能把 Unknown 计为 Fail 或零表现。

审计清单中的 **Pass/Fail** 必须由证据支持；**Unknown** 表示缺少证据并降低覆盖率，不降低健康度；**N/A** 不进入健康度或覆盖率。健康度和证据覆盖率按 Wiki 中的项目约定分开呈现。

## 执行边界

- 只使用当前 Registry 已注册并获准的只读 Tools，以及用户明确提供并标注来源的材料。每个要检查的项目都要先确认有对应证据来源。
- 当前没有可用 Tool、请求失败、结果模拟或所需字段缺失时，说明缺口和所需证据；不得声称已查询、已审计或已验证。
- Skill 只提供诊断建议，不创建、更新、暂停或发布广告。任何外部写入仍须通过当前 Tool schema 和 Runtime 权限、确认、幂等及审计门禁。
- 不使用未经账户数据验证的行业基准、固定点击/转化阈值、暂停规则或预算扩量百分比。

## 输出要求

简洁给出：数据来源和口径、报告是否完整、已核验发现、主要推断、Unknown/N/A 项、下一步只读检查及其目的。若证据不支持性能结论，明确说“当前不能判断”，不要用通用建议填补证据空白。
