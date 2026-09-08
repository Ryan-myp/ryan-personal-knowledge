---
schema_version: "1"
id: b2b-lead-generation-playbook
title: B2B Lead Gen 深度打法：线索质量、CRM 与销售闭环
layer: business
knowledge_type: business_strategy
platform: all
source: B2B 增长方法论 + 四平台 Lead/Conversion 能力
source_ref: agents/ad_agent/knowledge_base/business/b2b-lead-generation-playbook.md
version: "1.0.0"
confidence: 0.82
updated_at: "2026-09-08"
tags: [b2b, lead-generation, crm, mql, sql, pipeline, offline-conversion, cpl]
status: published
---

# B2B Lead Gen 深度打法：线索质量、CRM 与销售闭环

## 线索价值链

```text
impression -> click -> form submit -> lead accepted -> contacted
  -> MQL -> SQL -> opportunity -> closed-won / revenue
```

表单提交不是最终转化。每个阶段要定义准入标准、唯一 lead ID、时间戳、来源、销售负责人、失效原因和回传事件。没有 CRM 闭环时，平台会持续优化到“容易提交但不会成交”的人群。

## 表单设计

低摩擦表单提高数量，资格字段提高质量，二者要通过实验而不是争论决定。根据销售流程选择行业、公司规模、地区、预算、需求时间和联系方式等最小必要字段；隐私政策和数据用途要清晰。原生表单、网站表单和预约页应分别记录，不把它们混成一个 lead 事件。

## 指标与经济模型

```text
有效率 = accepted leads / submitted leads
MQL率 = MQL / accepted leads
SQL率 = SQL / MQL
成交率 = closed-won / SQL
有效线索成本 = spend / accepted leads
商机成本 = spend / opportunities
获客成本 = spend / closed-won
预期收入 = leads × 各阶段概率 × 阶段价值
```

销售周期长时使用 cohort 和滞后曲线，不用当天 CPL 判断渠道质量。按地区、行业、公司规模、素材角度、平台和销售团队拆解，避免整体平均数掩盖某个高价值细分市场。

## 平台优化事件

先稳定 lead 事件、去重和 consent，再逐步回传 qualified lead、SQL 或 opportunity。深层事件量不足时，系统可能无法学习；可以保留浅层优化与后端质量评估并行，而不是传入不完整或重复的离线事件。

## 销售与媒体协同

| 信号 | 可能原因 | 协同动作 |
|---|---|---|
| CPL 低、有效率低 | 表单过宽、承诺不符 | 修改资格条件与创意 |
| 有效率好、联系率低 | 销售 SLA、号码质量 | 优化分配和响应速度 |
| MQL 多、SQL 少 | 评分规则或需求不匹配 | 对齐 MQL 定义与素材承诺 |
| SQL 好、成交少 | 产品、报价、销售流程 | 不把问题归因给媒体 |
| 平台转化少、CRM 有量 | 回传延迟/匹配失败 | 查 click ID、时间窗、去重 |

## 实验方案

测试素材角度、行业分层、表单长度、落地页、CTA 和后续销售速度时，一次只改变一个主变量。主指标用合格线索/商机/成交，保护指标用 CPL、无效率、客服负荷和品牌政策；写明最小线索量、销售观察期和停止规则。

## 隐私与安全

最小化收集个人信息，限制访问和保留周期；原始邮箱/电话不进入知识库、Prompt、日志和普通报表。哈希、匹配和离线回传只在受控 Tool/数据边界完成，平台“接收成功”不等于线索已归因或成交。
