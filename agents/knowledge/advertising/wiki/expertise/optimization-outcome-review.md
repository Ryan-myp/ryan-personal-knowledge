---
schema_version: "1"
id: advertising-optimization-outcome-review
title: 广告优化效果复盘：成熟窗口、回读和同口径比较
layer: experience
knowledge_type: best_practice
platform: all
source: 本仓库优化复盘契约与离线回归用例
source_ref: agents/tests/advertising/test_optimization_reviews.py
version: "1.0.0"
confidence: 0.85
updated_at: "2026-10-29"
tags: [optimization, measurement, baseline, attribution, cooldown]
status: published
source_kind: code
authority: repository
evidence_level: reviewed
last_verified_at: "2026-10-29"
review_interval_days: 60
---

# 从建议到效果复盘

适用于同一 account / campaign 或下层资源的单变量调整。先保存建议与基线，再关联实际执行、
回读和观察期结果。多变量同时变化、归因口径变更、不同币种或窗口未成熟时，不直接解释为优化收益。

## 指标和窗口

CPA = spend / conversions，分母必须采用同一 conversion 定义。ROAS = conversion_value / spend，
收入定义、去重和退款处理保持一致。用户提供的数据与平台审计证据分开标记，不能因完成登记就声称已验真。

默认复盘至少包含七天观察，基线与观察等长，观察起始日必须晚于实际执行日期。平台报表可回补，
因此窗口结束后等待归因天数加七天再比较。这是本系统的保守复盘门槛，不是各平台通用 SLA。

## 已验证的离线案例

以下是契约测试的合成数据，不是真实广告收益：

| 场景 | 输入 | 系统处理 |
|---|---|---|
| 同口径成熟比较 | USD/UTC、七天窗口，CPA 从10到8 | 绝对变化 -2，相对变化 -20%，不作因果结论 |
| 币种变化 | 基线 USD、观察 EUR | 拒绝直接比较 |
| 未成熟 | 观察期刚结束、归因七天 | 等待成熟，不报告提升 |
| 无执行证据 | 只有“已修改”的文本 | 保持建议状态，要求审计与回读 |
| 重复建议 | 相同账户、资源、字段及方案 | 返回已有记录，避免重复登记 |
| 并发更新 | 修改时版本已过期 | 拒绝覆盖，重新读取最新版本 |

这些行为由 source_ref 中的离线测试验证；测试不访问渠道、不证明真实 API 可用，也不代表模型
在所有自然语言表达下都能准确选择 Tool。

## 解读和下一步

“调整后 CPA 降低20%”只描述观察值，不证明调整造成改善。应同时检查 CPM、CTR、CVR、
转化延迟、预算消耗、客群组成、创意变更和季节变化。确认增量需要随机实验或适合的因果设计。

冷却期内优先观察；只有达到异常护栏且有明确授权才另作处置。写结果未知时先回读，不盲目重放。
参阅 [[advertising-optimization-diagnostic-framework]]。
