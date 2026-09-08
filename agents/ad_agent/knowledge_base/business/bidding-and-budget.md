---
schema_version: "1"
id: cross-platform-bidding-and-budget
title: 跨平台预算分配与出价策略
layer: business
knowledge_type: bidding_strategy
platform: all
source: 广告平台官方出价文档 + 增长投放方法论
source_ref: agents/ad_agent/knowledge_base/business/bidding-and-budget.md
version: "1.0.0"
confidence: 0.84
updated_at: "2026-09-08"
tags: [budget, bidding, target-cpa, target-roas, cost-cap, bid-cap, marginal-roas]
status: published
---

# 跨平台预算分配与出价策略

## 先统一经济目标

```text
CTR = clicks / impressions
CVR = conversions / clicks
CPC = spend / clicks
CPA = spend / conversions
ROAS = attributed revenue / spend
contribution ROAS = contribution profit / spend
```

广告目标应从业务可承受成本倒推：目标 CPA 不能高于单次转化可贡献的毛利/生命周期价值；目标 ROAS 要考虑退款、折扣、平台费、履约和增量折损。跨币种、不同归因窗口和不同收入定义的数据不可直接排序。

## 出价策略的通用理解

| 策略族 | 系统倾向 | 适合场景 | 风险 |
|---|---|---|---|
| 流量/点击最大化 | 扩大访问量 | 事件尚未稳定、上层漏斗 | 可能带来低质量流量 |
| 转化最大化 | 在预算内找更多转化 | 事件量稳定、追求规模 | 价值差异大时需分层 |
| 目标 CPA/成本控制 | 围绕成本目标探索 | 有稳定历史与合理目标 | 目标过紧会花不出去 |
| 目标 ROAS/价值优化 | 追求价值效率 | 价值回传可靠 | 小样本价值波动大 |
| 手动/硬 bid cap | 强控制单次竞价 | 供应/实验边界明确 | 容易限制交付与学习 |

不同平台对策略命名和字段依赖不同；Google 的 bidding、Meta 的 cost/bid cap、TikTok 的 bid type、DV360 的 Line Item bid 不能互换。

## 预算分配

先分“探索预算”和“稳定预算”，再按边际收益而非历史平均 ROAS 分配。探索预算需要保护学习和新素材，稳定预算承接已验证的目标。预算放大时优先观察边际 CPA/ROAS、转化延迟、受众增量与频次，而不是只看总量。

## 放量与降量规则

- 单次改动保持可归因，预先写明幅度、观察窗口和回滚阈值。
- 花不出去先排查资格、审核、定向、出价、事件和库存，不要盲目抬预算。
- CPA 变差先拆解曝光成本、点击率、转化率、客单价与新客比例，再决定是改素材、页面、定向还是出价。
- ROAS 变好但增量/利润变差时，不能继续无条件放量。
- 预算计划输出日预算、周期总预算、账户币种、时区、pacing、上限和异常处理，而不是只给一个数字。
