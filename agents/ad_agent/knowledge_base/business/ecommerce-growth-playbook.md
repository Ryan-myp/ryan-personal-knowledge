---
schema_version: "1"
id: ecommerce-growth-playbook
title: 电商广告增长深度打法：商品、漏斗与利润
layer: business
knowledge_type: business_strategy
platform: all
source: 电商增长方法论 + 四平台商品广告能力
source_ref: "internal://ad-agent/playbook/ecommerce-growth-playbook"
version: "1.0.0"
confidence: 0.82
updated_at: "2026-09-08"
tags: [ecommerce, catalog, product-feed, funnel, margin, ltv, roas, retention]
status: published
source_kind: "internal"
authority: "operator"
evidence_level: "provisional"
last_verified_at: "2026-09-08"
---

# 电商广告增长深度打法：商品、漏斗与利润

## 业务模型

```text
可投商品供给 -> 曝光/点击 -> 商品详情 -> 加购 -> 结账 -> 支付 -> 复购
      |             |          |        |       |       |
   feed质量       创意/价格    页面     信任    支付    CRM/LTV
```

商品广告的第一优化对象不是出价，而是“用户看到的商品是否真实可买”。商品 ID、标题、图片、价格、库存、配送、退货政策、类目和落地页要在 Merchant Center/Catalog/商品集之间一致。缺库存、价格变化或商品 ID 不匹配时，平台可能继续有曝光但最终无法转化。

## 商品分层

| 分层 | 目的 | 关键变量 |
|---|---|---|
| 引流商品 | 低门槛获得新客 | 毛利、价格、库存、首购率 |
| 利润商品 | 承接贡献利润 | 毛利率、客单价、退款率 |
| 爆品/季节品 | 争取规模和市场窗口 | 供给、库存周转、促销周期 |
| 复购/订阅品 | 提升 LTV | 复购间隔、续订率、流失 |
| 清库存商品 | 释放库存风险 | 剩余天数、折扣、售后成本 |

不能用统一目标 ROAS 覆盖全部商品。高毛利商品可承受不同 CPA，爆品和清库存商品的目标也不同；拆分必须有足够供给和独立预算/报告意义。

## 经济指标

```text
贡献利润 = 收入 - 商品成本 - 折扣 - 履约 - 支付费 - 退款损失
允许 CPA = 单笔可贡献利润 × 可接受获客比例
贡献利润 ROAS = 贡献利润 / 广告花费
LTV:CAC = 预期生命周期贡献利润 / 获客成本
```

平台归因收入只能作为运营信号。复盘必须补订单去重、退款取消、新老客、自然转化、促销补贴和毛利；平台 ROAS 上升但贡献利润下降时，应限制放量并重新检查商品组合。

## 漏斗诊断

| 现象 | 重点检查 | 可能动作 |
|---|---|---|
| 曝光少 | 商品批准、库存、国家、feed 错误 | 修复商品源和资格 |
| CTR 低 | 首图、价格、标题、卖点、受众 | 重做商品创意与卖点 |
| 详情到加购低 | 页面速度、价格承诺、评价、配送 | 优化页面和信任组件 |
| 加购到支付低 | 运费、支付、优惠、库存锁定 | 查结账失败与价格变化 |
| Purchase 有量无价值 | value/currency/order ID | 对账事件与订单系统 |
| ROAS 好但新客少 | 品牌/再营销占比、受众排除 | 拆新客与增量评估 |

## 预算与促销

促销期间同时变化价格、素材、库存和预算，结果难以归因。提前记录促销窗口、基线、库存、预计毛利和售后能力；放量按商品供给和边际利润阶梯执行。促销结束后不要立即沿用高预算，观察需求回落和归因延迟。

## 跨平台使用

Google Shopping/PMax、Meta Catalog 和 TikTok Product Sales 都依赖商品源，但字段、商品集、身份、事件与报告口径不同。统一层只保存业务商品 ID、商品分层、利润和事件字典；平台层分别维护其 Catalog/Product Set/Listing Group Tool 依赖。
