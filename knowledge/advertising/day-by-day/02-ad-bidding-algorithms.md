# 广告竞价算法深度：GSP/VCG/Quality Score 数学推导

> 创建日期: 2026-06-10
> 作者: Ryan
> 定位: 资深专家级 — 竞价算法核心

---

## 第一部分：拍卖理论基础

### 1.1 为什么需要拍卖理论

```
广告竞价本质上是资源分配问题：

┌──────────────────────────────────────────────────────────────┐
│              拍卖理论核心问题                                   │
│                                                              │
│  资源: 每次展示 (Ad Slot)                                     │
│  ├── 有限的广告位 (通常 1-3 个/页面)                           │
│  └─ 无限的需求 (多个广告主竞争)                                 │
│                                                              │
│  参与者:                                                     │
│  ├── 卖家 (Publisher/平台) — 提供广告位                        │
│  └─ 买家 (Advertiser/DSP) — 请求广告位                        │
│                                                              │
│  目标:                                                       │
│  ├── 最大化卖家收益 (Revenue Maximization)                     │
│  ├── 最大化社会福利 (Social Welfare Maximization)              │
│  └─ 保证策略性 (Strategy-Proof / Incentive Compatible)       │
│                                                              │
│  关键概念:                                                   │
│  ├── Value (真实估值) — 广告主对每次展示的估值                  │
│  ├── Bid (出价) — 广告主报出的价格                              │
│  ├── Payment (支付) — 中标后实际支付的价格                      │
│  └─ Utility (效用) — Bidder 获得的收益 = Value - Payment     │
└──────────────────────────────────────────────────────────────┘
```

### 1.2 四种经典拍卖机制

```
┌──────────────────────────────────────────────────────────────┐
│              四种经典拍卖机制                                   │
│                                                              │
│  | 机制     | 定价方式        | 策略性      | 收入       │
│  |---------|-------------|-----------|-----------|
│  | 第一价格   | 支付自己出价    | 需 Bid Shading | 高 (可调节) |
│  | 第二价格   | 支付第二高出价  |  truthful    | 中等       │
│  | VCG      | 支付外部性     | truthful    | 中等       │
│  | 荷兰式    | 价格从高到低    | 需计算      | 低-中      │
│                                                              │
│  Truthful (真实出价) 意味着:                                   │
│  ├── 最优策略是报出真实估值                                     │
│  ├── 无需猜测他人出价                                          │
│  └─ 简化了投标决策                                             │
└──────────────────────────────────────────────────────────────┘
```

---

## 第二部分：Generalized Second-Price (GSP)

### 2.1 GSP 机制定义

```
GSP (广义第二价格拍卖) 是 Google Ads 使用的核心机制:

设定:
├─ N 个广告位 (slots), 按位置质量 s1 > s2 > ... > sN
├─ M 个广告主 (bidders), M ≥ N
├─ 每个广告主 i 的估值为 vi (每次点击的价值)
└─ 每个广告主 i 的出价为 bi

出价排序:
b1 ≥ b2 ≥ ... ≥ bN (前 N 个中标)

GSP 定价:
├─ 第 k 位中标者的 CPC = b(k+1) (第 k+1 位的出价)
├─ 第 N 位中标者的 CPC = 底价 (reserve price)
└─ 如果只有一位中标者 (k=N)，CPC = 底价

示例:
3 个广告位 (s1=1.0, s2=0.5, s3=0.3)
4 个广告主出价:

| Bidder | 估值 vi | 出价 bi | 排名 | 展示量 si | CPC | 效用 (vi-bi)×si |
|--------|---------|---------|------|----------|-----|-----------------|
| A      | 10.0    | 8.0     | 1    | 1.0      | 6.0 | (10-8)×1 = 2.0 |
| B      | 7.0     | 6.0     | 2    | 0.5      | 4.0 | (7-6)×0.5 = 0.5|
| C      | 5.0     | 4.0     | 3    | 0.3      | 3.0 | (5-4)×0.3 = 0.3|
| D      | 3.0     | 3.0     | -    | -        | -   | 0               |

广告主 A: 排名1 (最高出价), CPC = 6.0 (B 的出价)
广告主 B: 排名2, CPC = 4.0 (C 的出价)
广告主 C: 排名3, CPC = 3.0 (底价)
广告主 D: 未中标
```

### 2.2 GSP 的均衡分析

```
GSP 的 Nash Equilibrium (纳什均衡):

GSP 不是 Truthful Bidding，因此需要找均衡点:

Vickrey 结论: GSP 没有严格 truthful 的 Nash Equilibrium

但在实际中，GSP 存在 "symmetric equilibrium":

假设:
├─ 广告位价值: s1 > s2 > ... > sN
├─ 广告主估值: v1 > v2 > ... > vM
└─ 均衡出价: b*k = v(k+1) + (vk - v(k+1)) × s(k+1)/sk

均衡条件:
├─ 每个 bidder 的出价等于其 "effective value"                │
├─ 均衡时，bidder i 的出价 ≈ vi - (vi-v(i+1))×(1-s(i+1)/s(i))
└─ 出价低于真实估值 (bid shading)

经济直觉:
├─ 排名靠前的广告位更珍贵，出价更接近真实估值                   │
├─ 排名靠后的广告位，出价更低 (因为容易失去位置)                │
└─ 最终均衡时，每个 bidder 的出价 = 使其刚好不被超越的价格       │
```

### 2.3 GSP 收入分析

```
GSP 的收入 = Σ(k=1 to N) b(k) × s(k)

与 Second-Price 比较:
├─ GSP 通常产生更高收入 (因为出价更接近估值)
├─ GSP 可能导致 "winner's curse" (赢家诅咒)
└─ GSP 可能产生较低收入如果 bidder 理性 shading

Google 从 GSP 转向 "enhanced GSP" (2013+):
├─ 引入 Quality Score
├─ 优化排序公式: Score = bid × quality_score
└─ 排序用 Score，定价用 GSP
```

---

## 第三部分：VCG (Vickrey-Clarke-Groves)

### 3.1 VCG 机制定义

```
VCG 是 "truthful" 拍卖机制:

核心思想: 中标者支付的是其对其他 bidder 造成的外部性

定价公式:
├─ 广告位 k 的支付 = 如果没有 bidder i，第 k 位的出价 - 如果没有 bidder i，第 k+1 位的出价
├─ Paymenti = Social Welfare(-i) - Social Welfare(-i, i)
└─ 即: 中标者支付的 = 其入选导致其他 bidder 社会福利的减少

示例 (3 个广告位):

原始情况:
| Bidder | 估值 vi | 出价 bi | 排名 | 展示量 si | 支付 pi | 效用 |
|--------|---------|---------|------|----------|---------|------|
| A      | 10      | 10      | 1    | 1.0      | 3.0     | 7.0  |
| B      | 7       | 7       | 2    | 0.5      | 2.0     | 1.5  |
| C      | 5       | 5       | 3    | 0.3      | 0       | 1.5  |

VCG 定价:
├─ A 的支付 = (B的1位效用 + C的2位效用) - (B的2位效用 + D的3位效用)
│   = (7×0.5 + 5×0.3) - (5×0.3 + 0)
│   = 3.5 + 1.5 - 1.5 - 0 = 3.5
├─ B 的支付 = (A的2位效用 + C的3位效用) - (A的1位效用 + D的3位效用)
│   = (10×0.5 + 5×0.3) - (10×1.0 + 0)
│   = 5.0 + 1.5 - 10.0 = 0 (负的外部性，不需要支付)
└─ C 的支付 = 底价

VCG 的性质:
├─ Truthful: 报真实估值是最优策略 ✓
├─ Efficiency: 社会福利最大化 ✓
├─ 收入可能低于 GSP ✗
└─ 复杂: 计算外部性需要重新排序 ✗
```

### 3.2 VCG 为什么更优

```
VCG 的理论优势:

1. Strategy-Proof (策略性):
   ├── 报真实估值 vi 是最优策略
   └─ 无需猜测他人出价

2. Social Welfare Maximization (社会福利最大):
   ├── 排序基于真实估值 vi，而非出价 bi
   ├── 高价值 bidder 获得高排名
   └─ 最大化 Σ(vi × si)

3. Revenue Comparison:
   ├── VCG 收入 ≥ Second-Price 收入
   ├── VCG 收入 ≤ GSP 收入 (通常)
   └─ 实际中 Google 选择 GSP+QualityScore

为什么不全用 VCG?
├─ 复杂: 需要重新计算
├─ 收入不稳定: 取决于竞价分布
├─ 广告主困惑: "为什么我的支付这么低?"
└─ 商家偏好 GSP (收入更高)
```

---

## 第四部分：Quality Score 数学模型

### 4.1 Quality Score 定义

```
Quality Score 是 Google Ads 的核心机制:

原始 GSP: 按 bid 排序
GSP + QS: 按 bid × QS 排序

Quality Score 组成:
├─ Expected Click-Through Rate (预期点击率) — 40%
├─ Ad Relevance (广告相关性) — 30%
└─ Landing Page Experience (落地页体验) — 30%

排序公式:
├─ Ad Rank = bid × Quality Score
├─ Quality Score ∈ [1, 10] (Google 官方范围)
├─ 实际 QS 是连续值，映射到 1-10
└─ QS 每天更新 (基于最近 7-30 天数据)

实际排序:
├─ Scorei = bid_i × QS_i
├─ 按 Score 降序排列
└─ 前 N 名中标

GSP + QS 定价:
├─ 第 k 位的实际 CPC 满足:
│   bid_k × QS_k = bid_(k+1) × QS_(k+1)
│   CPC_k = bid_(k+1) × QS_(k+1) / QS_k
├─ 高质量 QS 的广告主可以用更低的 bid 获得相同排名
└─ 低 QS 的广告主需要出更高价才能竞争

经济意义:
├─ QS 本质上是 "效率因子" — 衡量每次展示的社会价值          │
├─ 高 QS = 用户更喜欢此广告 = 更高的社会价值                  │
├─ Google 通过 QS 引导广告主优化广告质量                      │
└─ QS 也保护用户体验 (低质广告被惩罚)
```

### 4.2 Quality Score 计算推导

```
Quality Score 的数学模型:

QS_i = α × eCTR_i + β × adRelevance_i + γ × lpe_i
其中: α + β + γ = 1, 通常 α=0.4, β=0.3, γ=0.3

eCTR 模型:
├─ eCTR_i = P(click | impression) 基于历史数据和上下文         │
├─ 使用 logistic regression / GBDT / DeepFM                   │
├─ 特征: 关键词、广告文案、历史CTR、用户属性、上下文             │
└─ eCTR 更新频率: 每小时/每天

Ad Relevance:
├─ 广告文案与关键词的语义相似度                                 │
├─ 使用 BM25 / BERT / 深度学习模型                              │
└─ 更新频率: 实时 (基于每次展示)

Landing Page Experience:
├─ 页面加载速度 (PageSpeed)                                    │
├─ 移动端适配 (Mobile Friendliness)                            │
├─ 内容相关性 (Content Relevance)                              │
├─ 安全性 (Safety / Malware)                                   │
└─ 更新频率: 每天/每周

优化循环:
├─ 低 QS → 需要更高 bid 才能竞争                                │
├─ 广告主有动机优化广告质量 → QS 上升                           │
├─ QS 上升 → 同等 bid 排名更高 → 更便宜 CPC                    │
└─ 最终: 广告质量提升 + 用户体验提升 + Google 收入提升 (Win-Win-Win)
```

---

## 第五部分：Smart Bidding 数学推导

### 5.1 tCPA (Target CPA) 推导

```
tCPA 优化目标:

给定:
├─ Target CPA = T (目标每次转化成本)
├─ 每次展示的 pCTR = p(click|show)
├─ 每次点击的 pCVR = p(convert|click)
└─ 每次展示的预期转化 = pCTR × pCVR = pAction

最优出价:
├─ Maximize: Σ_i bid_i × pAction_i, s.t. 总成本 ≤ 预算
├─ 拉格朗日: L = Σ bid_i × pAction_i - λ(Σ bid_i - Budget)
├─ FOC: pAction_i = λ
└─ 最优 bid_i = T × pAction_i = T × pCTR_i × pCVR_i

实现:
├─ bid_i = T × pCTR_i × pCVR_i
├─ pCTR 和 pCVR 由模型预测
├─ T = 目标 CPA
└─ 实际中加上 β 因子: bid = T × pCTR × pCVR × β

预算消耗控制:
├─ pacing 算法控制消耗速率                                    │
├─ 剩余预算 / 剩余时间 = 目标消耗速率                           │
└─ 根据实际消耗调整 β: β = pacing_factor × T                  │
```

### 5.2 tROAS (Target ROAS) 推导

```
tROAS 优化目标:

给定:
├─ Target ROAS = R (目标广告回报率)
├─ 每次转化的预期价值 = v_i
├─ pAction_i = pCTR_i × pCVR_i
└─ 每次展示的预期收入 = v_i × pAction_i

最优出价:
├─ Maximize: Σ_i bid_i × pAction_i × v_i, s.t. 收入/成本 ≥ R
├─ 拉格朗日: L = Σ bid_i × pAction_i × v_i - μ(Σ bid_i - Budget)
├─ FOC: pAction_i × v_i = μ
└─ 最优 bid_i = (R/100) × v_i × pAction_i = (R/100) × v_i × pCTR_i × pCVR_i

实际中:
├─ bid_i = (target_roas/100) × value_i × pCTR_i × pCVR_i
├─ value_i = 转化价值 (由模型预测)
├─ pCTR, pCVR 由模型预测
└─ 加上 pacing: bid = pacing_factor × (roas/100) × value × pCTR × pCVR

关键差异:
├─ tCPA: bid = T × pAction — 只关注转化次数
├─ tROAS: bid = (ROAS/100) × value × pAction — 关注转化价值
├─ tROAS 对高价值转化出价更高
└─ tROAS 需要转化价值数据 (e.g. 购买金额)
```

### 5.3 Max Conversions 推导

```
Max Conversions 优化:

目标: 最大化 Σ_i pAction_i × bid_i, s.t. 总成本 ≤ Budget

拉格朗日优化:
├─ L = Σ_i pAction_i × bid_i - λ(Σ_i bid_i - Budget)
├─ FOC: pAction_i = λ (对所有中标者)
└─ 最优: 所有中标者的 pAction 相等

实现:
├─ bid_i = β × pAction_i
├─ β 由预算和竞价强度决定                                    │
├─ 预算充足: β 增大 → 出价更高 → 更多展示                     │
├─ 预算不足: β 减小 → 出价降低 → 只抢高价值展示                 │
└─ 自动调整 β 以保持预算消耗

Budget Pacing:
├─ pacing_factor(t) = min(1.0, (Budget_t - Spent_t) / (Budget_t × (1-t/T)))
├─ β(t) = base_bid × pacing_factor(t)
├─ pacing 确保预算均匀消耗                                    │
└─ 防止预算提前耗尽
```

---

## 第六部分：Bid Shading (出价衰减)

### 6.1 Bid Shading 推导

```
Bid Shading 在 First Price 拍卖中的优化:

问题:
├─ 第一价格拍卖: 中标 = 支付自己的出价                         │
├─ 最优策略: 出价 = 最低能中标的价格                            │
└─ 即: bid* = min(value, expected_second_price)

Bid Shading 公式:
├─ bid_i* = min(v_i, E[b_(k+1) | b_i, history])
├─ E[b_(k+1)] = 第二高出的期望值                              │
└─ bid_i* = v_i × shade_factor (0 < shade_factor ≤ 1)

估算第二高价:
├─ 方法 1: 历史统计 — P(b_(k+1) > x) = 1 - F(x)^(N-1)      │
│   └─ F(x) = 历史竞价的经验分布                               │
├─ 方法 2: 参数拟合 — 拟合竞价分布 (Beta/LogNormal)             │
├─ 方法 3: 机器学习 — 训练竞价预测模型                         │
└─ 方法 4: 在线学习 — 自适应更新                              │

Bid Shading 优化:
├─ Maximize: E[(v_i - bid*) × I(win)]                           │
│   └─ I(win) = 1 if bid* ≥ b_(k+1), 0 otherwise               │
├─ FOC: v_i - bid* = bid* × f(bid*) / (1-F(bid*)) × (N-1)      │
│   └─ f = 概率密度, F = 累积分布                                │
└─ 解: bid* = v_i / (1 + 1/(λ(bid*)))                           │
    └─ λ = hazard rate = f/F

实际实现:
├─ 使用 Beta 分布拟合竞价                                      │
├─ 实时估算第二高价                                            │
├─ 计算 shade_factor = E[b_(k+1)] / v_i                        │
└─ bid = shade_factor × v_i
```

---

## 第七部分：竞价算法对比

```
┌────────────────────────────────────────────────────────────────┐
│              竞价算法对比                                        │
│                                                                │
│  | 算法       | Truthful | 收入  | 复杂度 | 实际使用     │
│  |-----------|---------|-------|-------|------------|
│  | First Price | 否     | 高    | 中     | AdX (2020+)  │
│  | Second Price| 是     | 中    | 低     | AdSense      │
│  | VCG       | 是       | 中-低  | 高     | 学术/极少      │
│  | GSP       | 否      | 中-高  | 低     | Google Ads    │
│  | GSP+QS    | 否      | 高     | 中     | Google Ads    │
│  | SmartBid  | N/A     | 最优   | 高     | 所有平台      │
└────────────────────────────────────────────────────────────────┘
```

---

## 第八部分：自测题

### 问题 1
GSP 中第 k 位中标者的 CPC 如何计算？

<details>
<summary>查看答案</summary>

CPC_k = bid_(k+1) × QS_(k+1) / QS_k (GSP + Quality Score)
传统 GSP: CPC_k = bid_(k+1)
</details>

### 问题 2
tCPA 和 tROAS 的最优出价公式有什么区别？

<details>
<summary>查看答案</summary>

tCPA: bid = T × pCTR × pCVR (只看转化次数)
tROAS: bid = (ROAS/100) × value × pCTR × pCVR (看转化价值)
关键区别: tROAS 乘了转化价值 value
</details>

### 问题 3
Bid Shading 在 First Price 拍卖中的最优出价公式是什么？

<details>
<summary>查看答案</summary>

bid* = min(v, E[b_(k+1)])
其中 E[b_(k+1)] 是第二高出的期望值
通过历史竞价分布 (Beta/LogNormal) 或机器学习预测
</details>

---

*今天花 90 分钟：深入掌握广告竞价算法数学推导*
*答不出自测题？回去重读对应章节。*
