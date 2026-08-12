---
name: ad-attribution-expert
description: "广告归因专家技能 — 归因模型、增量测量、LTV/CAC、ROI 优化、数据回流"
version: 1.0.0
author: ryan
tags: [advertising, attribution, ltv, cac, roi, analytics, expert]
---

# 广告归因专家技能

> 从归因模型到增量测量，掌握广告效果评估的核心方法论

## 核心能力

### 1. 归因模型
- 最后点击归因（Last Click）
- 首次点击归因（First Click）
- 线性归因（Linear）
- 时间衰减归因（Time Decay）
- 位置归因（Position Based）
- 数据驱动归因（Data-Driven）
- Shapley Value 归因
- Markov Chain 归因

### 2. 增量测量
- A/B Test 设计
- Holdout 实验
- Geo-based 实验
- 合成控制法（Synthetic Control）
- Causal Inference

### 3. 用户价值
- LTV (Lifetime Value) 计算
- CAC (Customer Acquisition Cost)
- ROMI (Return on Marketing Investment)
- Payback Period
- Cohort Analysis

### 4. 数据回流
- 服务器端回传（Server-Side）
- 匹配用户 ID
- 延迟转化处理
- 跨设备归因

## 知识库引用

| 主题 | 文档 |
|------|------|
| 归因模型 | `knowledge/advertising/ad-attribution-model-deep.md` |
| 归因系统 | `knowledge/advertising/attribution-system-deep.md` |
| Shapley-Markov | `knowledge/advertising/ad-attribution-shapley-markov-deep.md` |
| 跨渠道归因 | `knowledge/advertising/ad-cross-channel-attribution-case-deep.md` |
| 增量测量 | `knowledge/advertising/day-by-day/06-ad-incremental-measurement.md` |
| 归因不一致 | `knowledge/advertising/ad-attribution-inconsistency.md` |
| 预算分配 | `knowledge/advertising/ad-cross-channel-budget-allocation-deep.md` |
| LTV/CAC | `knowledge/growth-plan/ad-growth-ltv-cac-retention-deep.md` |

## 使用场景

### 场景 1: 选择归因模型
1. 明确业务目标（品牌 vs 效果）
2. 查看 `knowledge/advertising/ad-attribution-model-deep.md`
3. 根据数据可用性选择模型
4. 考虑 Shapley/Markov 等高级模型

### 场景 2: 排查归因不一致
1. 查看 `knowledge/advertising/ad-attribution-inconsistency.md`
2. 检查数据回流链路
3. 对比不同平台的归因窗口

### 场景 3: 优化 ROI
1. 计算 LTV/CAC 比率
2. 识别高价值用户 cohort
3. 优化预算分配

## 关键指标公式

```
LTV = ARPU × Gross Margin × (1 / Churn Rate)
CAC = Total Marketing Spend / New Customers
ROMI = (Revenue - Marketing Cost) / Marketing Cost
Payback Period = CAC / Monthly Revenue per User
```

## 自测题

<details>
<summary>Q1: Shapley Value 归因和 Markov Chain 归因有什么区别？</summary>

**答案**：
- **Shapley Value**：基于合作博弈论，计算每个 touchpoint 的平均边际贡献
- **Markov Chain**：基于状态转移概率，移除某状态后看转化率的下降
- **区别**：Shapley 考虑所有排列组合，更准确但计算复杂；Markov 更直观，适合长路径

</details>

<details>
<summary>Q2: 为什么需要增量测量而不是只看归因？</summary>

**答案**：
1. **归因偏差**：最后点击会高估近距离 touchpoint 的作用
2. **虚假转化**：自然转化被误认为是广告效果
3. **增量的真实价值**：没有广告时的转化差异才是广告的真实贡献
4. **预算优化**：增量测量帮助识别真正有效的投放渠道

</details>

<details>
<summary>Q3: LTV/CAC 比率多少算健康？</summary>

**答案**：
- **LTV/CAC > 3**：非常健康，可以加大投放
- **LTV/CAC = 2-3**：健康，持续增长
- **LTV/CAC = 1-2**：临界，需要优化
- **LTV/CAC < 1**：亏损，立即停止投放
- **理想 payback period**：< 12 个月（SaaS）或 < 3 个月（电商）

</details>
