---
schema_version: "1"
id: google-workflows
title: Google Ads API 工作流
layer: platform
knowledge_type: workflow
platform: google-ads
source: Google Ads API 官方文档
source_ref: "repository://ad-agent/knowledge/google-workflows"
version: "1.0.0"
confidence: 0.9
updated_at: "2026-08-26"
tags: [google, workflow, api]
status: published
source_kind: "code"
authority: "repository"
evidence_level: "reviewed"
last_verified_at: "2026-08-26"
---

# Google Ads API 工作流

这份文档描述 Google Ads 从读取、规划到提交变更的标准工作流。Agent 应先确认账户范围、资源层级和执行模式，再生成可审计的操作计划；默认只做 dry-run，不直接修改线上账户。

## 一、先确认账户与目标

1. 明确客户账户、目标平台、时区、币种和业务目标。账户身份来自可信配置，不从用户输入中推断。
2. 区分查询、诊断、规划和写入请求。只读请求可以直接检索；写入请求必须先输出变更计划和影响范围。
3. 确认资源层级：`Customer → Campaign → AdGroup → Ad/Keyword/Asset`。预算、出价和素材不能脱离所属 Campaign 判断。
4. 对转化、价值和成本目标先确认归因窗口与数据延迟，避免用未成熟数据调整出价。

## 二、读取与诊断顺序

建议按以下顺序查询，减少重复请求并保证上下文完整：

| 步骤 | 读取内容 | 目的 |
|------|----------|------|
| 1 | Customer 与可访问账户 | 确认账户范围和权限 |
| 2 | Campaign 状态、类型、预算、出价 | 判断投放结构和预算约束 |
| 3 | AdGroup、关键词、素材 | 找到流量与创意层面的瓶颈 |
| 4 | ConversionAction 与近期开关 | 判断转化信号是否可靠 |
| 5 | 报表与诊断结果 | 形成带时间窗口的优化结论 |

诊断时至少保留日期范围、归因模型、时区、过滤条件和数据更新时间。没有这些上下文的单一指标不应直接作为调价依据。

## 三、写入前的 dry-run 流程

1. 将用户目标转换为结构化意图，例如“暂停低转化广告组”或“调整 Campaign 日预算”。
2. 校验资源 ID、父子关系、状态枚举、预算单位和字段可变性。
3. 生成变更前后对比、预计影响、风险等级和幂等键。
4. 默认返回 dry-run 计划，等待用户明确确认后才进入 live gate。
5. live 写入必须经过测试账号白名单、权限、确认、超时和审计记录；部分失败时保留成功与失败项，不声称自动回滚。

## 四、常见优化闭环

- **搜索广告**：先看搜索词与匹配类型，再看广告相关性、落地页和转化质量，最后评估出价策略。
- **Performance Max**：同时检查素材资产、Listing Group、受众信号、品牌流量和转化价值，避免只看 Campaign 总体 CPA。
- **预算调整**：先检查预算受限、展示份额和边际转化，再做小幅度调整；学习期内避免频繁修改。
- **素材迭代**：保留稳定对照组，单次只改变一个主要变量，并记录开始时间、样本量和停止规则。

## 五、失败处理与回滚边界

API 报错时先按 request ID、资源层级和可重试性分类。网络超时可以在幂等保护下重试；参数校验失败应修正计划后重新确认；部分成功必须重新读取线上状态。Google Ads 的部分资源字段不可变，不能把“更新”假设为通用能力，必要时应创建新资源并切换关联关系。

## 参考

- [Google Ads API Campaigns](https://developers.google.com/google-ads/api/docs/campaigns/overview)
- [Google Ads API Reporting](https://developers.google.com/google-ads/api/docs/reporting/overview)
- [Google Ads API Mutate Requests](https://developers.google.com/google-ads/api/docs/mutating/overview)
