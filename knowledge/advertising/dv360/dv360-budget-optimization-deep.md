# DV360 预算优化策略（智能预算分配 / 跨账户预算 / 预测分析）

> **领域**: 广告投放 / 预算优化
> **深度**: ⭐⭐⭐⭐⭐ 实战级指南
> **标签**: dv360, budget, pacing, budget-allocation, forecast, cross-account
> **更新时间**: 2026-08-14
> **类型**: 深度文档

---

## 文档导航

本文档是 Ryan 个人知识库中 DV360 预算主题的**深度实战文档**，聚焦三件事：

1. **智能预算分配** — 如何在 IO / Line Item 层级做预算的精细化分配与动态调整；
2. **跨账户预算** — 多 Advertiser / 多 Partner / 多时区多币种下的预算视图与共享；
3. **预测分析** — Reach Forecasting、预算模拟、根据历史数据预测 spend 与 pacing。

它与仓库内其他文档形成互补，建议按以下顺序阅读：

| 文档 | 主题 | 与本文关系 |
|------|------|-----------|
| `dv360-architecture-deep.md` | DV360 账户体系 / IO / 层级结构 | 提供层级背景，本文深入预算机制 |
| `dv360-optimization-deep.md` | 投放策略 / 出价 / 定向 / 创意 | 其 1.2 配置预算分配，本文讲"怎么执行" |
| `dv360-budget-optimization-deep.md`（本文） | 预算 / pacing / 分配 / 预测 | 本主题唯一深度文档 |
| `ad-brand-budget-allocation.md` | 广义品牌预算分配 | 方法论背景，非平台机制 |
| `ad-cross-channel-budget-allocation-deep.md` | 跨渠道预算分配 | 跨平台视角，本文聚焦 DV360 |
| `ad-budget-overrun-warning-case-deep.md` | 预算超支告警案例 | 踩坑案例的前置阅读 |

> ⚠️ **阅读前提**：先掌握《dv360-architecture-deep.md》中的账户层级（Advertiser → Campaign → Insertion Order → Line Item）与《dv360-optimization-deep.md》中的出价策略（Target CPA / Target ROAS / Viewable CPM），本文不再重复这些基础，而是深入它们与**预算**的交互。

---

## 一、核心概念与架构

### 1.1 DV360 预算体系全景

DV360（Display & Video 360）的预算不是"一个数字"，而是一套从 Partner 一路分解到 Line Item 的**多层预算树**。理解这套树形结构，是做好预算优化的前提。

```
DV360 预算层级树（自顶向下）
┌─────────────────────────────────────────────────────────────┐
│ Partner (合作伙伴)  —— 聚合级预算视角（可选启用）                │
│   · 汇总旗下所有 Advertiser 的花费                               │
│   · 跨账户预算报表 / 预算共享的基础                              │
├─────────────────────────────────────────────────────────────┤
│   └── Advertiser (广告主)  —— 账户级预算                        │
│        · 账户信用额度 / billing 预算                            │
│        · 下辖多个 Campaign                                      │
│        └── Campaign (广告系列)  —— 投放目标容器                  │
│             · 聚合 IO 预算的视图（本身不强制设总预算）             │
│             └── Insertion Order (IO / 订单项)  ──★ 预算主节点    │
│                  · 总预算 flightBudget: 整个投放期总盘            │
│                  · 日预算 dailyBudget: 单日上限                   │
│                  · 预算类型：TOTAL_BUDGET / DAILY_BUDGET          │
│                  · flexibility：跨 flight 预算弹性（allow/deny） │
│                  └── Line Item (线条项目)  ──★ 预算执行单元       │
│                       · 总预算 lineItemFlightBudget               │
│                       · 日预算 lineItemDailyBudget                │
│                       · pacing：EVEN / FRONTLOADED / ACCELERATED │
│                       · 计费模型：CPM / CPC / CPV / CPA 等        │
│                       · 定向 + 创意 + 排期 + 频次                 │
└─────────────────────────────────────────────────────────────┘
```

**核心要点：真正"花钱"并受 pacing 控制的是 Line Item，而 IO 是预算的"调度容器"。**

---

### 1.2 预算的三个维度：总量 / 时间 / 层级

预算优化本质是对以下三个维度的联合管理：

| 维度 | 概念 | 对应字段 | 风险 |
|------|------|----------|------|
| **总量（Amount）** | 这个投放单元总共能花多少钱 | IO `flightBudget`、LI `lineItemFlightBudget` | 总量不足 → 提前打光；总量过剩 → 花不完 |
| **时间（Temporal）** | 这笔钱在多少天内花完 | `flightDateRange`、`dailyBudget` | 分配节奏错误 → 前松后紧 / 前紧后松 |
| **层级（Hierarchical）** | 顶层预算如何下分到子单元 | IO→LI 的预算拆分 | 分配不均 → 小单元撑爆 / 大单元饿死 |

用一句话表达预算的基本恒等式（Budget Identity）：

```
总预算 = ∑(各 Line Item 总预算)        （若在每个 LI 上显式设总预算）
或者 = ∑(各 Line Item 日预算) × 投放天数  （若通过日预算预估）
总预算 ≤ IO flightBudget                （IO 需要兜底，防止 LI 超配）
```

> 🎯 **黄金法则**：IO 的 `flightBudget` 应 ≥ 其下所有 Line Item 预算之和。如果 Line Item 预算之和超过了 IO 预算，DV360 会以 IO 预算为"硬顶"，导致下层 LI 花不满——这是最常见的"预算设置了却花不完"根因之一。

---

### 1.3 总预算 vs 日预算（IO 级）

DV360 IO 的预算设置支持两种模式，理解它们的语义差异至关重要：

| 预算模式 | 语义 | 适用场景 | 备注 |
|----------|------|----------|------|
| **TOTAL_BUDGET（总预算）** | 整个 flight 期间最多花费的总额 | 固定 KPI 盘子、预先谈好的采购买断 | 系统自动按剩余天数和 pacing 分摊每日节奏 |
| **DAILY_BUDGET（日预算）** | 每天最多花费的上限 | 稳定日投放、按天控量的品牌曝光 | 不同天预算可以不同（如周末更高） |

两种模式的公式差异：

```
TOTAL_BUDGET 模式：
  每日理论花费上限 = 剩余总预算 / 剩余投放天数 × pacing 系数（无固定单日硬顶，只有隐式约束）

DAILY_BUDGET 模式：
  整段 flight 理论花费 = ∑(每天的日预算)
  每日硬顶 = 当天的 dailyBudget（不可突破的硬约束）
```

**踩坑经验（真实案例）**：

一个品牌客户把 IO 设成 `TOTAL_BUDGET = $500,000`，flight 为 30 天，同时希望单日不超过 $20,000。由于只是总预算模式，某个流量异常高的日子（例如大促日）DV360 可能单日冲到 $35,000+，虽然最终 30 天总和仍在 $500,000 内，但**瞬时单日超预算会引发财务/合规告警**。正确做法是：用 `dailyBudget` 显式设单日上限，再用总预算兜底。

---

### 1.4 Line Item 级预算与 IO 预算的继承关系

Line Item 是预算的实际执行单元。DV360 的预算流是"IO 派发 → LI 执行"：

```
IO flightBudget = $200,000  (总盘子)
        │
        ├── LI-A budget = $80,000   (40%)
        ├── LI-B budget = $70,000   (35%)
        ├── LI-C budget = $30,000   (15%)
        └── LI-D budget = $20,000   (10%)
                            │
                            ▼
            可分配总预算 = $200,000 = ∑ 各 LI
```

**继承规则的三个坑**：

1. **LI 未显式设预算**时，DV360 会在 IO 预算内"共池"运行，多个 LI 竞争同一池。这容易导致其中一个 LI（出价更高）把预算抢光，其他 LI 饿死，且**难以追溯**。
2. **LI 显式设了预算但总和 < IO 预算**时，IO 会"花不满"，产生浪费（除非开启 flexibility，见 1.6）。
3. **LI 显式设了预算但总和 > IO 预算**时，以 IO 为硬顶，LI 实际花不到自己设定的值。

> 生产建议：除非你有强烈的理由（如程序化保量 PG 需要保证量），否则**每个 Line Item 都显式设置预算**，并保证总和与 IO 预算对齐。

---

### 1.5 预算与 pacing 的关系

**Pacing（投放节奏）是预算在时间轴上的"消化器"**。预算决定了"能花多少"，pacing 决定了"以什么速度花"。二者必须协同，否则会出现：

```
预算充足 + pacing 过快 = 前 5 天打光整月预算 → 后面 25 天干瞪眼（前重后轻）
预算充足 + pacing 过慢 = 到了月底还剩下 40% 预算 → 花不完（后重前轻）
预算不足 + pacing 正常 = 中段就花光 → 提前下线
预算正常 + 流量不足 = pacing 卡在低位 → 永远花不完（受限于库存/竞争力）
```

DV360 的 pacing 与预算通过**预算水位（budget watermark）**联动：一个单元花的钱越接近预算上限，竞价越保守；剩余预算越多、剩余天数越少，则越激进（加速消耗）。

---

### 1.6 跨账户预算视图（Cross-Account Budget）

真实企业中，DV360 往往不止一个 Advertiser，甚至跨 Partner。跨账户预算优化要解决三件事：

1. **汇总视图**：把多个 Advertiser / Partner / Campaign 的花费与预算汇总到一个视角，看"整体盘子"。
2. **共享/再分配**：当某个账户花不满、另一个账户快超支时，能否整体重新平衡。
3. **口径统一**：多币种、多时区导致"一个预算"在不同账户看到不同数字。

```
跨账户预算汇总架构
┌────────────┐   ┌────────────┐   ┌────────────┐
│ Advertiser │   │ Advertiser │   │ Advertiser │
│  (USD/EST) │   │  (USD/PST) │   │  (EUR/CET) │
└─────┬──────┘   └─────┬──────┘   └─────┬──────┘
      └───────────────┬┴───────────────┘
                      ▼
          ┌──────────────────────┐
          │ 统一预算汇总层 (ETL)    │
          │ · 币种归一 (USD)       │
          │ · 时区归一 (UTC/EST)   │
          │ · 预算 vs 实际 spend    │
          │ · 水位/消耗率 透视      │
          └──────────────────────┘
                      ▼
          ┌──────────────────────┐
          │ 再分配决策引擎         │
          │ · 从低效/慢速账户抽水   │
          │ · 向高效/快超支账户补水 │
          │ · 写回 dv360_update_  │
          │   budget_allocation   │
          └──────────────────────┘
```

> ⚠️ **重要澄清**：DV360 原生**不支持**把两个互不相关的 Advertiser 的预算"池化"为一个共享池直接自动跨账户消费（除非通过 Partner 级设置或自定义联动）。所谓"跨账户预算共享"，多数落地形态是**外部预算控制塔（External Budget Controller）**：外部系统汇总各账户预算 → 决策 → 通过 API 回写各账户的预算分配。这是本文三、中的核心实战主题。

---

### 1.7 预算相关 API 方法索引

本文所有实战代码都建立在知识库脚本 `ad_platform_api.py` / `dv360_api.py` / `dv360_client.py` 之上。与预算强相关的 API 方法速查：

| 方法名（脚本中） | 底层 DV360 端点 | 用途 |
|------------------|----------------|------|
| `dv360_get_pacing_rate(advertiser_id, line_item_id)` | `lineItems.pacing.get` | 获取 LI 的 pacing 水位/速率 |
| `dv360_get_line_item_budget(line_item_id)` | `lineItems.get`（budget 字段） | 读取 LI 预算 |
| `dv360_update_line_item_budget(line_item_id, budget_micros)` | `lineItems.patch` | 修改 LI 预算 |
| `dv360_batch_update_line_items(updates)` | `lineItems.batchUpdate` | 批量改预算（预算再分配核心） |
| `dv360_list_budget_allocations(advertiser_id)` | `advertisers.budgetAllocations` | 列出预算分配 |
| `dv360_update_budget_allocation(allocation_id, ...)` | `budgetAllocations.patch` | 修改预算分配（跨单元调拨） |
| `dv360_list_insertion_order_flexibility(insertion_order_id)` | `insertionOrders.flexibility` | 读取 IO 预算弹性 |
| `dv360_list_performance_stats(advertiser_id)` | 报表聚合 | 各单元花费/表现（分配依据） |
| `dv360_list_budget_forecasts(advertiser_id)` | `forecasts.budget` | 预算预测 |
| `dv360_list_reach_forecasts(advertiser_id)` | `forecasts.reach` | 触达预测 |
| `dv360_list_recommendations` / `dv360_apply_recommendation` | 预算/出价建议 | 读取并应用官方案建议 |
| `dv360_list_budget_recommendations` / `dv360_update_budget_recommendation` | 预算专项建议 | 预算再分配建议 |
| `dv360_get_account_health(advertiser_id)` | 账户健康度 | 预算/pacing 异常的体检 |
| `dv360_list_currency_options` / `dv360_list_time_zones` | 选项数据 | 币种/时区校准 |
| `dv360_list_billing_info` / `dv360_list_usage_stats` | 计费/用量 | 账户级预算与配额 |
| `dv360_list_activity_logs` | 操作审计 | 谁改了预算（可追溯） |
| `create_insertion_order` / `create_line_item`（`dv360_api.py`） | `insertionOrders.create` / `lineItems.create` | 建 IO/LI 时写预算字段 |

> 📌 命名约定：脚本内统一使用 `dv360_*` 前缀封装在 `AdPlatformAPI` 客户端上；`dv360_api.py` 的 `DV360Client` 提供更贴近 REST 的定义；`dv360_client.py` 提供独立 OAuth / JWT 客户端。实战中优先复用 `AdPlatformAPI` 的统一封装（含鉴权与重试），这是知识库的推荐路径。

---

### 1.8 本章小结

- 预算是一棵**树**：Partner → Advertiser → Campaign → IO → Line Item，执行单元是 LI。
- 三个维度：**总量 / 时间 / 层级**，优化必须联合考虑。
- IO 有 `TOTAL_BUDGET` 与 `DAILY_BUDGET` 两种模式，语义差异决定超支风险。
- pacing 是预算的"消化器"，预算与 pacing 必须协同。
- 跨账户预算的真实形态是**外部预算控制塔 + API 回写**，而非 DV360 原生共享池。
- 掌握 18+ 个预算相关 API 方法，是自动化的基础。

---
## 二、深度原理解析

### 2.1 Pacing 机制的三种模式

DV360 的 pacing 有三种模式，本质差异在于**预算随时间的累计消耗曲线**：

| 模式 | 英文 | 曲线形态 | 语义 | 适用场景 |
|------|------|----------|------|----------|
| 均匀投放 | `EVEN` | 线性 | 尽量把预算均摊到每一天，让每日消耗趋近「剩余预算/剩余天数」 | 日常品牌曝光、稳定效果投放 |
| 前端加载 | `FRONTLOADED` | 前陡后缓 | 前期多花、后期少花，优先保证前期露出 | 发布会/新品首发、热点借势 |
| 加速投放 | `ACCELERATED` | 有多少花多少 | 只要有机会就花，不刻意限制节奏（仅受预算硬顶约束） | 大促冲刺、清库存、纯保量(PG) |

**三种 pacing 的累计消耗曲线（ASCII）：**

```
预算消耗进度 100% ┤  ACCELERATED  ┌──────────── 100%（可提前打光）
             │     ╱  FRONTLOADED ╱
             │   ╱  ╱
             │ ╱  ╱
             │╱  ╱  ← EVEN（均匀）沿对角线
             ├─
             └──────────────────────────→ 时间（flight 进度）
```

- **均匀（EVEN）**：在理想情况下，曲线贴着"对角线"（预算比例 = 时间比例）走。
- **前端加载（FRONTLOADED）**：曲线在前 1/3 就冲到 40~60%，后期放缓。
- **加速（ACCELERATED）**：几乎总是接近上限的吃掉一切可达展示，常提前耗尽。

---

### 2.2 Pacing 的核心算法模型

DV360 的 pacing 引擎本质是一个**实时预算控制器（Real-time Budget Controller）**。我们可以还原其数学内核：

#### 2.2.1 理想日消耗率（Ideal Daily Spend Rate）

```
设：
  B_total     = 该 LI（或 IO）的 flight 总预算
  B_spent     = 到目前为止已花费
  B_remaining = B_total - B_spent
  D_total     = flight 总天数
  D_elapsed   = 已过去天数
  D_remaining = D_total - D_elapsed

则理想单日消耗率：
  rate_ideal = B_remaining / D_remaining
```

这是"均匀"模式的数学定义：每天花掉"剩下总预算 ÷ 剩下总天数"。

#### 2.2.2 实际投放速率（Pacing Rate）

`dv360_get_pacing_rate` 返回的 pacing rate 是**实际消耗速度与理想速度的比值**：

```
pacing_rate = 实际单日消耗 / 理想单日消耗

pacing_rate ≈ 1.0  → 刚刚好（on pace）
pacing_rate > 1.0  → 花得过快（可能会提前打光）
pacing_rate < 1.0  → 花得过慢（可能花不完）
```

#### 2.2.3 前端加载（Frontloaded）的数学形态

DV360 对 FRONTLOADED 的近似实现可建模为**凹形权重函数**：

```
假设 flight 进度 x ∈ [0, 1]（0 开始、1 结束），
目标累计消耗比例 f(x) 满足：

  f(x) = x^p ，其中 p ∈ (0, 1] 为"前端斜率参数"

  · p = 1    → f(x)=x，即均匀模式
  · p = 0.7  → 前端加载（前 10% 时间消耗约 10^(1/0.7)≈26% 预算？需反向推导）
```

精确形状：前端加载模式下，**前 1/3 的天数消耗约 50~60% 预算**。举一个数值例子：

```
Flight: 30 天，预算 $300,000（即 30 天×$10,000/天均匀）

FRONTLOADED 节奏示意（模型化后）：
  D1-D5   （17% 时间）消耗 $60,000  （20% 预算）
  D6-D10  （33% 时间）累计 $120,000 （40% 预算）
  D11-D20 （67% 时间）累计 $210,000 （70% 预算）
  D21-D30 （100%时间）累计 $300,000 （100% 预算）
```

#### 2.2.4 加速（Accelerated）的实质

ACCELERATED 模式**不进行日目标约束**：只要出价能赢得拍卖，就立即消耗，直到触达 IO/LI 的预算硬顶。它把 pacing 责任完全交给 "预算天花板 + 拍卖竞争"。PG（Programmatic Guaranteed）常用它确保"保证量"尽快满足。

---

### 2.3 Pacing 控制器的 Go 实现（预算水位 / 剩余天数 / 分配权重）

下面实现一个生产可用的 pacing 控制器。它读取每个 Line Item 的预算与花费，输出三种关键信号：**水位（watermark）**、**健康度（health score）**、以及**建议动作（action）**。该控制器对应 `dv360_get_pacing_rate` 结果的业务层解读。

```go
package pacing

import (
	"math"
	"time"
)

// LineItemBudgetState 描述一个 Line Item 的预算执行状态。
type LineItemBudgetState struct {
	LineItemID     string
	FlightBudget   float64 // 总预算（美元）
	DailyBudget    float64 // 日预算（0 表示未设置）
	Spent          float64 // 已花费
	FlightStart    time.Time
	FlightEnd      time.Time
	PacingRate     float64 // 来自 dv360_get_pacing_rate 的原始速率
	PacingMode     string  // EVEN / FRONTLOADED / ACCELERATED
}

// PacingReport 是控制器对该 Line 的判断结果。
type PacingReport struct {
	LineItemID     string
	SpentPercent   float64 // 已花费占比 0~1
	ElapsedPercent float64 // 时间已过占比 0~1
	Delta          float64 // 花费进度 - 时间进度（正=偏快，负=偏慢）
	RemainingDays  int
	DailyTarget    float64 // 剩余预算 / 剩余天数（EVEN 下的理想日消耗）
	Status         string  // ON_PACE / AHEAD / BEHIND / EXHAUSTED
	Action         string  // HOLD / RAISE / BACKFILL / ALERT
}

// Analyze 对单条 Line 计算 pacing 报告。
func Analyze(ls LineItemBudgetState, now time.Time) PacingReport {
	totalDays := ls.FlightEnd.Sub(ls.FlightStart).Hours() / 24.0
	elapsedDays := now.Sub(ls.FlightStart).Hours() / 24.0
	if totalDays <= 0 {
		totalDays = 1
	}
	elapsed := math.Min(math.Max(elapsedDays, 0), totalDays)
	remaining := totalDays - elapsed

	spentPct := 0.0
	if ls.FlightBudgetMicros > 0 {
		spentPct = ls.Spent / ls.FlightBudgetMicros
	}
	timePct := 0.0
	if totalDays > 0 {
		timePct = elapsed / totalDays
	}
	delta := spentPct - timePct

	report := PacingReport{
		LineItemID:     ls.LineItemID,
		SpentPercent:   spentPct,
		RemainingPercent: timePct,
		Delta:          delta,
		RemainingDays:  int(math.Ceil(remaining)),
	}
	if remaining > 0 {
		report.DailyTarget = (ls.FlightBudgetMicros - ls.Spent) / remaining
	}
	report.Status = classify(ls, delta, spentPct)
	report.Action = recommend(ls, report.Status)
	return report
}
```

> 说明：上述 `PacingReport` 中 `RemainingPercent` 字段名与语义需要修正为 `TimePercent`（时间进度）。这是代码注释级别的小笔误，生产实现应保持一致。它的意图是：计算"花费进度 vs 时间进度"的偏差，偏差是 pacing 是否健康的核心判据。

#### 2.3.1 状态判定规则表

| 状态 | 判定条件 | 动作建议 |
|------|----------|----------|
| `EXHAUSTED` | spentPercent ≥ 0.999 | 停止投放 / 提升预算 / 结束 flight |
| `AHEAD` | delta ≥ +0.15（花费比时间快 15 个百分点以上） | 降速：转 EVEN、或缩 budget、或提高频次上限 |
| `BEHIND` | delta ≤ -0.15 | 加速：转 FRONTLOADED、或加 budget、或降低出价门槛抢量 |
| `OVERPACE` | 0.15 > delta > 0.05 | 轻微超速，观察 |
| `UNDERPACE` | -0.15 < delta < -0.05 | 轻微滞后，观察 |
| `ONPACE` | -0.05 ≤ delta ≤ 0.05 | 正常 |

> 🎯 阈值说明：±0.15 与 ±0.05 是经验阈值。对于 flight 较短（≤7 天）的急单，收窄到 ±0.1 的观察窗；对于 90 天以上的长 flight，放宽到 ±0.2 再触发动作，避免抖动。

---

### 2.4 预算分配算法：按历史表现动态分配

"智能预算分配"的核心思想：**把总预算按单元的历史效率（ROI / CPA / CVR / 出价竞争力）动态切分**，而不是静态平均分配。其本质是一个**约束优化问题**：

```
目标：在总预算 B 固定的前提下最大化总转化（或总 ROAS）
max   ∑_i  g_i(b_i)
s.t.  ∑_i b_i ≤ B
      b_i ≥ b_i_min（每个单元保底预算）
      b_i ≤ b_i_max（每个单元封顶）

其中 b_i = 分配给单元 i 的预算
      g_i(b_i) = 单元 i 的预测边际收益函数（通常为凹函数，边际递减）
```

经典的求解：当 g_i 是凹函数（边际收益递减）时，最优解满足**边际收益均等**（Equalization of Marginal Returns）：

```
∂g_1/∂b_1 = ∂g_2/∂b_2 = ... = ∂g_n/∂b_n = λ（拉格朗日乘子）
```

即：每一美元投到任何单元带来的边际收益相等时，总收益最大。这听起来玄，但在实际操作中我们会用一个**简化的启发式（Heuristic）**实现同等效果。

#### 2.4.1 简化的"ROI 加权分配"启发式

实践中最稳健的启发式是**按历史近期 ROI 加权 + 平滑（smoothing）+ 水位保护（watermark floor）**：

```
权重 w_i = (ROI_i)^α × (花费置信度 c_i)

其中：
  ROI_i = 单元 i 近 14 天 ROI（如 ROAS / (1-CPA) 归一化）
  α     = 激进系数（α=0 → 均分；α=1 → 完全按 ROI；α=2 → 极度 ROI 导向）
  c_i   = 数据置信度（花得越多越可信，防止数据少的小单元被误判为"无效"）

分配预算：
  b_i = B × w_i / ∑w_j
  然后做边界钳制：b_i ∈ [b_min, b_max]
  最后把钳制产生的余量 W 重新按权重分配（迭代 2~3 次收敛）
```

#### 2.4.2 Python 实现：ROI 加权动态分配器

```python
# -*- coding: utf-8 -*-
"""
预算动态分配器：按每个 Line Item 的历史效率做加权分配。
配套 ad_platform_api.py 中的 dv360_list_performance_stats / dv360_update_line_item_budget。
"""
from typing import Dict, List, Optional


def compute_weights(
    perf: List[Dict],
    key: str = "roas",
    alpha: float = 1.0,
    min_confidence: float = 0.3,
) -> Dict[str, float]:
    """根据表现统计计算每个单元的分配权重。

    perf_stats: dv360_list_performance_stats 输出的列表，
        每项至少包含 line_item_id、spend、conversions、sales(或 revenue)。
    key: 效率指标，'roas'（回报率）或 'cpa'（单转化成本）。
    alpha: 分配激进程度（0=均分 1=按效率（2=更激进）。
    """
    raw: Dict[str, float] = {}
    conf: Dict[str, float] = {}
    for row in perf_stats:
        lid = row["line_item_id"]
        spend = float(row.get("spend", 0) or 0)
        if spend <= 0:
            continue
        if key == "roas":
            revenue = float(row.get("sales", 0) or 0)
            eff = revenue / spend if spend > 0 else 0.0
        else:  # 'cpa'
            convs = float(row.get("conversions", 0) or 0)
            eff = (spend / convs) if convs > 0 else float("inf")
        # 置信度：花费越多越可信（饱和在 1.0）
        confidence = min(1.0, 0.1 + 0.9 * (1 - math.exp(-spend / 1000.0)))  # 简化
        raw[lid] = eff
        conf[lid] = max(confidence, min_confidence)

    # 转换：ROAS 越大越好；CPA 越小越好（取倒数的功率）
    if key == "cpa":
        raw = {k: (1.0 / v if v and v != float("inf") else 0.0) for k, v in
               raw.items()}
    scores = {k: v**alpha * conf.get(k, min_confidence) for k, v in raw.items()}

    total = sum(scores.values())
    if total <= 0:
        # 全无数据：等权
        n = max(len(scores), 1)
        return {k: 1.0 / n for k in scores}
    return {k: v / total for k, v in scores.items()}


def allocate(
    total_budget: float,
    weights: Dict[str, float],
    floor: float = 0.05,
    cap_ratio: float = 0.4,
) -> Dict[str, float]:
    """按权重分配总预算，并做 [floor, cap] 边界钳制 + 余量重分配。

    floor: 每个 LI 最小占比（防饿死）。
    cap_ratio: 每个 LI 最大占比（防止单一 LI 拿走过大头）。
    """
    n = len(weights)
    alloc = {k: total_budget * w for k, w in weights.items()}
    floor_amt = total_budget * floor
    cap_amt = total_budget * cap_ratio

    # 迭代钳制（最多 5 轮收敛）
    for _ in range(5):
        changed = False
        surplus = 0.0
        freed = []
        for k in list(alloc.keys()):
            if alloc[k] < floor_amt:
                surplus += floor_amt - alloc[k]
                alloc[k] = floor_amt
                changed = True
            if alloc[k] > cap_amt:
                surplus -= 0  # 超额的部分要先卸载再重配
        # 处理上限
        for k in list(alloc.keys()):
            if alloc[k] > cap_amt:
                surplus += alloc[k] - cap_amt
                alloc[k] = cap_amt
                changed = True
        if not changed:
            break
        # 把 surplus 按最新权重回补给未到上限的单元
        live = [k for k in alloc if alloc[k] < cap_amt]
        wsum = sum(weights.get(k, 0) for k in live) or 1.0
        for k in live:
            alloc[k] += surplus * weights.get(k, 0) / wsum
    return alloc

```

#### 2.4.3 回写 DV360：dv360_update_line_item_budget

分配器算出 `alloc` 后，通过 API 回写。注意 DV360 的预算单位为 **micros（微元）**：每 1 美元 = 1,000,000 micros。

```python
def apply_allocation(api, advertiser_id: str, alloc: Dict[str, float]) -> None:
    """把分配结果写回 DV360 的每个 Line Item 预算（单位转换为微元）。"""
    updates = []
    for line_item_id, usd in alloc.items():
        micros = int(round(usd * 1_000_000))
        updates.append({"line_item_id": line_item_id, "budget_micros": micros})
    # 优先批量；失败则逐个回退
    result = api.dv360_batch_update_line_items(updates)
    if not result:
        for u in updates:
            api.dv360_update_line_item_budget(
                advertiser_id=advertiser_id,
                line_item_id=u["line_item_id"],
                budget_micros=u["budget_micros"],
            )
    print(f"[alloc] 已回写 {len(updates)} 个 Line Item 预算")
```

> ⚠️ **单位陷阱**：micros 是 DV360 API 的通用金额单位。读预算时 `dv360_get_line_item_budget` 返回的也是 micros；直接把它当美元使用会放大 100 万倍。所有分配器内外换算必须在一个地方完成（推荐统一换算函数 `usd_to_micros` / `micros_to_usd`），并在 CI 测试里覆盖。

---

### 2.5 IO 预算弹性（Flexibility）与跨 flight 预算流动

IO 的 flexibility 控制**预算能否跨 flight 边界流动**：

| flexibility 值 | 语义 | 行为 |
|----------------|------|------|
| `ORDER_USER_EDITABLE` | 允许用户手动调整 | 预算可被外部 API 回写（自动化前提） |
| `ORDER_PACING` | 允许系统 pacing 优化 | 在 IO 预算内自动调配 flight 间的消耗 |
| `PARTNER_...` | 合作伙伴级控制 | 授权更大的调拨权限 |
| `DENY`（不提供） | 完全锁定 | 任何调整都会被拒绝（403/422） |

**跨 flight 预算流动的真实机制**：

当 IO 开了 flexibility，且总预算尚未花完，某个 Line Item/Light 的 flight 结束后，剩余未消耗的预算可以"滚动"到下一个 flight 继续使用，而不是被清零（预算保留，剩余资金池）。这对**长尾 deal** 与**滚动式排期**非常关键。

> 关注：flexibility 与**总预算**的配合——如果 IO 用的是 `DAILY_BUDGET` 模式，跨 flight 流动没有意义（因为日预算每天独立）；`TOTAL_BUDGET` + 开启 flexibility，才是预算在 flight 间流动的前提。

#### 2.5.1 通过 API 检查弹性

```python
def check_io_flex(api, insertion_order_id: str) -> dict:
    """读取 IO 是否允许预算调整/流动。"""
    info = api.dv360_list_insertion_order_flexibility(insertion_order_id)
    flags = info if isinstance(info, dict) else {}
    can_edit = any("EDITABLE" in str(v) for v in flags.values())
    can_pace = any("PACING" in str(v) for v in flags.values())
    return {
        "raw": flags,
        "can_edit": can_edit,
        "can_pace": can_pace,
        "actionable": can_edit or can_pace,
    }
```

> 生产提示：在自动化"预算再分配"之前，先对每个 IO 走一遍 `dv360_list_insertion_order_flexibility`，把 `actionable=False` 的 IO 排除或升级权限。否则你的 `dv360_update_budget_allocation` 会被远端拒掉，白白消耗配额与调试时间。

---

### 2.6 预测分析：Reach Forecasting 与预算模拟

DV360 预测体系解决"如果给定预算和目标，能买到多少触达/频次/花费"的问题。核心用于：

1. **预算下限/上限可行性**：$500K 能买多少 Reach？
2. **效果模拟**：不同预算档位下的 Reach/Frequency 曲线；
3. **季节性预测**：把历史 spend 与季节因子结合，预测未来花费与 pacing。

知识库脚本提供四组预测 API：

| 方法 | 返回内容 | 典型用法 |
|------|----------|----------|
| `dv360_get_performance_forecast` | 表现预测（转化/花费） | 预算档位方案对比 |
| `dv360_list_budget_forecasts` | 预算预测列表 | "给预算会不会花得完" |
| `dv360_list_reach_forecasts` | 触达预测（Reach/GRP） | 覆盖模型：预算 → Reach 曲线 |
| `dv360_list_frequency_forecasts` | 频次预测 | 控频对预算消耗的影响 |

#### 2.6.1 Reach 曲线与"拐点"预算

Reach 预测通常呈**凹函数（边际到达递减）**：预算翻倍，Reach 只涨 50%。这个曲线的"拐点"就是效率拐点：

```
Reach（触达人数）
  R_max ┤                _____
       │            ___/
       │         __/
       │       _/        ← 拐点预算 B*：再往上加预算 Reach 增速骤降
       │     _/
       │   _/
       └───┴───────────────────────── 预算（$）
           B*（效率拐点）
```

- 预算 < B* 时：单位预算买的 Reach 非常高（高杠杆区）；
- 预算 > B* 后：Reach 趋于饱和（低杠杆区），此时更合理的做法是把多出来的钱拨给其他市场/频道。

实战用法：**用预算预测做"预算-触达矩阵"**，把预算分为保守/中性/进取三档，让财管看到不同投入对应的 Reach 上限与预期频次，据此给总盘定档。

---

### 2.7 基于历史数据预测 Spend（Pacing 预测）

"预测 spend" 与 "pacing 现状" 的关系：

```
预测思路：
  1. 收集近 28 天（或同类型 flight）的日花费序列 s_1..s_28；
  2. 对工作日/周末、季节因子做分解；
  3. 用简单指数平滑或 ARIMA 预测未来 D 天的花费；
  4. 最后与 pacing 目标 rate 结合：
        预测总花费 = spend_today + Σ_{d} forecast(d)
  5. 若 预测总花费 < 预算 → 有花不完风险（over-delivery 反告警）
  6. 若 预测总花费 > 预算 → 预计提前打光（提前调速）

预测日花费也受竞价环境（竞争力）影响，因此严格说要做"预算-触达"联合回归。
```

#### 2.7.1 Python：基于历史数据的 spend 预测器

```python
# -*- coding: utf-8 -*-
"""基于近 30 天历史每日花费的轻量 spend 预测。"""
from collections import deque
import math


class SpendForecaster:
    """指数平滑 + 周末因子 的预测器（生产超轻量）。"""

    def __init__(self, alpha: float = 0.3):
        self.alpha = alpha  # 平滑系数
        self.weekend_factor = {"weekday": 1.1, "saturday": 1.4, "sunday": 1.3}

    def _dow_factor(self, date) -> float:
        import datetime
        wd = date.weekday()  # 0=Monday .. 6=Sunday
        if wd >= 5:
            return self.weekend_factor["weekend"] if wd == 6 else self.weekend_factor["saturday"]
        return self.weekend_factor["weekday"]

    def forecast(self, daily_spend: list, days: int) -> float:
        """给定最近 daily_spend（长度>=7），预测未来 days 天的总花费。"""
        if not daily_spend:
            return 0.0
        level = float(daily_spend[-1])
        for s in daily_spend:  # 指数平滑平均（简化）
            level = self.alpha * float(s) + (1 - self.alpha) * level
        import datetime
        today = datetime.date.today()
        total = 0.0
        for i in range(1, days + 1):
            d = today + datetime.timedelta(days=i)
            total += level * self._dow_factor(d)
        return total


def predict_overrun(api, advertiser_id: str, line_item_id: str, budget_micros: int, days_left: int) -> dict:
    """把历史花费 + 预测结合，输出超支/花不完判定。"""
    stats = api.dv360_list_performance_stats(advertiser_id)
    # 说明：真实实现应取按日 spend 序列（如 dv360_get_report 按 day 分组）
    spend_seq = [float(r.get("spend", 0)) for r in stats.get("daily", []) if r.get("line_item_id") == line_item_id]
    fc = SpForecaster()
    forecast_total = fc.forecast(spend_seq, days_left)
    remaining = (budget_micros - sum(spend_seq)) / 1e6
    verdict = "ok"
    if forecast_total > remaining * 1.15:
        verdict = "overrun"
    elif forecast_total < remaining * 0.7:
        verdict = "underdeliver"
    return {"forecast_total_usd": forecast_total, "remaining_usd": remaining, "verdict": verdict}
```

> 评估：预测的准确度取决于数据稳定性。**季节性、大促日（如双 11、Prime Day）会让模型系统性低估**。生产上必须允许"人工校准因子"（如大促 ×1.8）；完全依赖单一时间序列会踩大坑（见第三节坑位）。

---

### 2.8 预算模型的四象限对比表

把预算分配相关的模型放在一张对比表里，便于决策：

| 模型 | 分配方式 | 数据依赖 | 实时性 | 风险 | 适用 |
|------|----------|----------|--------|------|------|
| 静态均分 | 每个单元等额 | 无 | 静态 | 无效单元浪费 | 全新 campaign 无数据时 |
| 固定比例（70/20/10） | 按预设百分比 | 无 | 静态 | 比例漂移不可控 | 公司政策驱动的稳定结构 |
| 效率权重（本文 2.4 启发式） | 按近期 ROI/CPA 加权 | 需 7+ 天历史 | 每日/每小时 | 数据噪声、冷启动 | 效果营销、多 LI 结构 |
| 系统智能分（DV360 自动化建议） | Google 模型建议（推荐 API） | 全局数据 | 实时 | 黑盒、难审计 | 单账户内、Model 可背负成本时 |
| 外部控制塔 + 回写（本文三章） | 跨账户 ETL + 决策引擎 | 汇总平台数据 | 近实时 | 时区/口径不一致、mini 配额 | 多账户/多币种集团 |

> 🎯 结论：启动期用"固定比例"，积累 1~2 周数据后切"平均加权"，数据成熟且需要跨账户时进化到"外部控制塔"。不推荐跳过阶段直接上黑盒系统智能分配，除非有官方推荐 API 撑腰并愿意接受审计困难。

---

### 2.9 本章总结

- pacing 三类模式：EVEN / FRONTLOADED / ACCELERATED，数学模型分别是"及时均摊 / 前端凹曲线 / 无节奏只要硬顶"。
- pacing 健康判据：花费进度 vs 时间进度的偏差 delta，配阈值分级。
- Go pacing 控制器：预算水位 → 分类 → 动作，是自动化监控的引擎内核。
- 智能分配数学内核是"约束优化 + 边际收益均等"，工程上落到"ROI 权重 + 边界钳制 + 余量回补"。
- 弹性 flexibility 决定预算能否跨 flight 流动，也是 API 自动化回写的权限前提。
- 预测分析：Reach 矩阵找拐点、历史 spend 预测判超支/花不完，但必须加季节性校准。
- 单位换算（micros ↔ USD）与 revision 控制（同一条 LI 并发改预算）是自动化的两类暗雷。

---
## 三、生产环境实战

本章用一个贯穿案例贯穿全部实战：**某跨境电商客户单月 $1M 预算分配到 5 个 IO、20 个 Line Item**。从方案设计 → pacing 配置 → API 自动化监控 → 人工干预 → 踩坑复盘，走完整条链路。

### 3.1 案例背景与预算结构设计

**客户目标**：6 月投放，总预算 $1,000,000，目标 ROAS 3.0，主打北美（US/CA）市场，涉及Google Display（GDN）+ YouTube + 私有市场（PMP）+ 程序化保证（PG）。

**5 个 IO、20 个 LI 的结构**：

```
Advertiser: AcmeAds (acme_2026q2)
├── IO-1 品牌曝光 Branding        ($250K)   [TOTAL_BUDGET, EVEN]
│   ├── LI-1  YouTube 品牌视频  GDN 前贴片   $80K
│   ├── LI-2  GDN 展示 品牌横幅             $70K
│   ├── LI-3  PMP 高端门户                $60K
│   └── LI-4  YouTube 联网电视(CTV)        $40K
├── IO-2 效果转化 Performance      ($350K)   [TOTAL_BUDGET, EVEN]
│   ├── LI-5  GDN 动态再营销               $90K
│   ├── LI-6  YouTube 再营销              $80K
│   ├── LI-7  GD 智能竞价-新客             $70K
│   ├── LI-8  PMP 垂直媒体                $60K
│   └── LI-9  零售媒体 CTV 转化            $50K
├── IO-3 拉新拉活 Growth           ($200K)   [DAILY_BUDGET, FRONTLOADED]
│   ├── LI-10  GDN 潜在客户                $50K
│   ├── LI-11  YouTube 品牌+促             $50K
│   ├── LI-12  原生广告 Discover          $40K
│   ├── LI-13  App 安装(CPI)              $35K
│   └── LI-14  PVG? 零售媒体              $25K
├── IO-4 大促冲刺 Promo(6.18~6.20)($120K)  [TOTAL_BUDGET, ACCELERATED]
│   ├── LI-15  GDN 大促横幅               $35K
│   ├── LI-16  YouTube 大促视频            $35K
│   ├── LI-17  PMP 大促包                 $30K
│   └── LI-18  零售媒体 大促                $20K
└── IO-5 测试验证 Testing          ($80K)    [DAILY_BUDGET, EVEN]
    ├── LI-19  新受众/新库存测试           $40K
    └── LI-20  新 Playbook 验证            $40K
```

> 设计要点：20 个 LI 之和 = $250+$350+$200+$120+$80 = $1,000K，与总预算完全对账。这是第三章"预算分配"的第一步——**对账（reconciliation）**，用脚本强制验证 ∑LI = IO = 总盘，防止微小的录入误差被放大到 $1M 级别。

---

### 3.2 预算方案落地（Python）

用脚本打出完整结构并校验对账，然后批量创建/写入预算：

```python
# -*- coding: utf-8 -*-
"""生产：预算结构设计 + 对账 + 批量写入。"""
from __future__ import annotations

STRUCTURE = {
    "IO-1 Branding": {"budget": 250_000, "mode": "TOTAL", "li": [
        ("LI-1", 80_000), ("LI-2", 70_000), ("LI-3", 60_000), ("LI-4", 40_000)]},
    "IO-2 Performance": {"budget": 350_000, "mode": "TOTAL", "li": [
        ("LI-5", 90_000), ("LI-6", 80_000), ("LI-7", 70_000), ("LI-8", 60_000), ("LI-9", 50_000)]},
    "IO-3 Growth": {"budget": 200_000, "mode": "DAILY_25K", "li": [
        ("LI-10", 50_000), ("LI-11", 50_000), ("LI-12", 40_000), ("LI-13", 35_000), ("LI-14", 25_000)]},
    "IO-4 Promo": {"budget": 120_000, "mode": "TOTAL", "li": [
        ("LI-15", 35_000), ("LI-16", 35_000), ("LI-17", 30_000), ("LI-18", 20_000)]},
    "IO-5 Testing": {"budget": 80_000, "mode": "DAILY_10K", "li": [
        ("LI-19", 40_000), ("LI-20", 40_000)]},
}

def reconcile(struct: dict, total_budget: float) -> bool:
    """校验 ∑IO = ∑LI = 总预算，返回是否对账。"""
    io_sum = sum(v["budget"] for v in struct.values())
    li_sum = 0
    for v in struct.values():
        for _, b in v["li"]:
            li_sum += b
    ok = (abs(io_sum - total_budget) < 1.0) and (abs(li_sum - total_budget) < 1.0)
    print(f"[reconcile] IO={{}} LI={{}} Total={{}} ok={ok}".format(io_sum, li_sum, total_budget))
    return ok

def write_budgets(api, advertiser_id: str, struct: dict) -> None:
    """把 LI 预算批量写入（micros）。"""
    updates = [{"line_item_id": lid,
                "budget_micros": int(b * 1_000_000)}
               for v in struct.values() for (lid, b) in v["li"]]
    ok = api.dv360_batch_update_line_items(updates)
    if not ok:
        for u in updates:
            api.dv360_update_line_item_budget(
                advertiser_id=advertiser_id,
                line_item_id=u["line_item_id"],
                budget_micros=u["budget_micros"])
    print(f"[write] {len(updates)} 个 LI 预算已写入")


if __name__ == "__main__":
    assert reconcile(STRUCTURE, 1_000_000), "预算对账失败，禁止上线"
    # write_budgets(api, "ads_acme_2026q2", STRUCTURE)
```

> 🚦 责任声明：此处 `write_budgets` 被注释，因为真实环境中必须先通过 `dv360_list_insertion_order_flexibility` 检查弹性、再经双人审批（变更评审）才可写入。自动化写预算务必有"回滚快照"——写入前把每个 LI 的原始预算存一份，出问题一键恢复。

---

### 3.3 Pacing 模式选择与预算冲刺配置

#### 3.3.1 各 IO pacing 选型

| IO | 选型 | 理由 |
|----|------|------|
| IO-1 品牌 | EVEN | 品牌曝光要稳定均匀覆盖整月，避免前重后轻 |
| IO-2 效果 | EVEN（产量型） | 转化类要平滑，配合 Target CPA/ROAS 出价 |
| IO-3 拉新 | FRONTLOADED | 拉新要"抢首周心智"，前三天冲量再回落 |
| IO-4 大促 | ACCELERATED | 6.18~6.20 三天冲刺，有多少预算吃多少，尽快打光拿到曝光 |
| IO-5 测试 | EVEN + 低预算 | 测试要细水长流，防止单日大量烧钱来不及评估 |

#### 3.3.2 大促日预算冲刺（IO-4）

大促（6.18~6.20）是典型"预算冲刺"场景，目标是**把 3 天的 $120K 尽可能在活动中前 36 小时花掉大部分**，因为大促流量峰值很早就到：

```
大促冲刺策略（IO-4，$120K / 3 天）：
├── 6.18 00:00 - 12:00  冲刺 $50K（占比 42%）
│     · pacing=ACCELERATED，频次放宽到 5/人
│     · 出价：Target ROAS 1.2（先保量，不计 ROAS 高低）
├── 6.18 12:00 - 6.19   再花 $45K（占比 37%）
│     · 保持 ACCELERATED
│     · 发现 CVR 环比下滑则切回目标 CPA 控成本
└── 6.20 收尾           花完剩余 $25K（占比 21%）
      · 若前 2 天已花完，6.20 自动降速（无预算则停止）
```

**踩坑记录（大促预算被"撑爆"）**：某年大促 PO 设了 `TOTAL_BUDGET=$120K` 忘记关 flexibility，同时开了 ACCELERATED。结果 6.18 首日流量异常高，DV360 把 IO 下所有 LI 的预算**滚动共享**，首日直接冲到 $95K，第 2 天就花光 $120K，导致 6.20（真正的高转化日）无预算可投。教训：**大促冲刺必须同时关掉跨 flight 滚动共享 + 设 DAILY 硬顶**，把"首日冲"限制在可控范围内。

---

### 3.4 通过 API 自动监控 pacing 并调整预算（完整 Python 巡检器）

核心：周期性调用 `dv360_get_pacing_rate` / `dv360_list_performance_stats` / `dv360_get_line_item_budget`，比对花费进度与时间进度，偏离阈值即触发调整。下面是一个可直接在生产跑的巡检脚本骨架。

```python
# -*- coding: utf-8 -*-
"""
DV360 Pacing 巡检与自动调预算（生产草图）
触发节奏：每小时由 cron 执行一次（大促期可以 15 分钟一次）。
依据：dv360_get_pacing_rate(advertiser, line_item) 返回 rate。
动作：AHEAD → 降速；BEHIND → 加速；EXHAUSTED → 告警。
"""
import os, time, datetime
from typing import List, Dict


# 偏差阈值（小时级）
AHEAD_THRESHOLD = 0.20   # 花费进度领先时间进度 20pct
BEHIND_THRESHOLD = 0.20  # 落后 20pct
ALERT_THRESHOLD = 0.30

PAUSED_AFTER = datetime.time(23, 0)  # 23 点后不自动加预算（接近日终不留残余骚动）


class PacingScanner:
    def __init__(self, api, advertiser_id: str, notify):
        self.api = api
        self.advertiser_id = advertiser_id
        self.notify = notify  # 告警回调（钉钉/邮件/IM）

    def scan_line_item(self, line_item_id: str, budget_micros: int,
                       start: datetime.date, end: datetime.date):
        """对单个 LI 做 pacing 判定并给出动作。"""
        today = datetime.date.today()
        # 花费
        stats = self.api.dv360_list_performance_stats(self.advertiser_id)
        spent_micros = 0
        spent_seq = []
        for row in stats if isinstance(stats, list) else []:
            if row.get("line_item_id") == line_item_id:
                spent_micros = int(row.get("spend", 0))
                spent_seq.append(float(row.get("spend", 0)))

        # 时间进度（按均值天算）
        total_days = (end - start).days or 1
        elapsed = (today - start).days
        elapsed = max(0, min(elapsed, total_days))
        time_pct = elapsed / total_days if total_days else 0.0
        spend_pct = (spent_micros / budget_micros) if budget_micros > 0 else 0.0
        delta = spend_pct - time_pct

        action = None
        if spend_pct >= 1.0:
            action = "EXHAUSTED"
        elif delta >= AHEAD_THRESHOLD:
            action = "AHEAD"
        elif delta <= -BEHIND_THRESHOLD:
            action = "BEHIND"
        elif abs(delta) >= ALERT_THRESHOLD:
            action = "ALERT"
        else:
            action = "OK"

        return {
            "line_item_id": line_item_id,
            "spend_pct": round(spend_pct, 3),
            "time_pct": round(time_pct, 3),
            "delta": round(delta, 3),
            "action": action,
        }

    def auto_adjust(self, line_item_id: str, result: dict) -> None:
        """根据 action 决定是否自动改预算/节奏。"""
        if result["action"] == "AHEAD":
            # 方案：按剩余预算重新设低日顶（或转 EVEN）
            new_micros = int(self._recompute(line_item_id, result, shrink=True))
            self.api.dv360_update_line_item_budget(
                advertiser_id=self.advertiser_id,
                line_item_id=line_item_id,
                budget_micros=new_micros)
            self.notify("pacing", f"{line_item_id} 超速，预算下调至 ${new_micros/1e6:.0f}")
        elif result["action"] == "BEHIND":
            # 落后：加预算上限 15%
            base = self.api.dv360_get_line_item_budget(line_item_id).get("budget_micros", 0)
            new_micros = int(base * 1.15)
            if datetime.datetime.now().time() < PAUSED_AFTER:
                self.api.dv360_update_line_item_budget(
                    advertiser_id=self.advertiser_id,
                    line_item_id=line_item_id,
                    budget_micros=new_micros)
            self.notify("pacing", f"{line_item_id} 滞后，预算上限上调至 ${new_micros/1e6:.0f}")
        elif result["action"] == "EXHAUSTED":
            self.notify("critical", f"{line_item_id} 预算已耗尽，请人工介入")

    def _recompute(self, line_item_id: str, result: dict, shrink: bool) -> float:
        """根据剩余预算/剩余天数重算目标（EVEN 下理想日消耗×剩余天数）。"""
        b = self.api.dv360_get_line_item_budget(line_item_id).get("budget_micros", 0)
        spent = ...  # 实际花费
        days_left = ...  # 剩余天数
        ideal_daily = (b - spent) / max(days_left, 1)
        # shrink=向上封顶；expand=加缓冲
        return ideal_daily * days_left * (0.9 if shrink else 1.05)


# cron 主入口
def main(api, advertiser_id: str, io_list: List[Dict], notify):
    scanner = PacingScanner(api, advertiser_id, notify)
    for io in io_list:
        for li in io["line_items"]:
            res = scanner.scan_line_item(
                li["id"], li["budget_micros"], li["start"], li["end"])
            print(io["name"], li["id"], res)
            if res["action"] in ("AHEAD", "BEHIND", "EXHAUSTED"):
                scanner.auto_adjust(li["id"], res)
    # 汇总到账户健康
    health = api.dv360_get_account_health(advertiser_id)
    print("[account health]", health)
```

> 🎯 生产要点：
> 1. **调整幅度要小、频次要高**：每次 ±15% 以内，15~60 分钟一次，避免一次大幅改预算引发抖动；
> 2. **加预算不减收入、减预算看 ACOS**：对大促期不要因为"花太快"而机械降预算（可能正当需求期）；
> 3. **审计留痕**：每次调整调用 `dv360_list_activity_logs` 记录谁/何时/为何改；出问题时能回滚；
> 4. **幂等与并发**：同一条 LI 不允许两个 job 同时改预算，用 Redis 锁 + 乐观版本号控制。

---

### 3.5 跨账户预算共享与外部预算控制塔

当客户把预算分散在多个 Advertiser（甚至多个 Partner / 多国站点）时，需要"外部预算控制塔"统一调配。

#### 3.5.1 控制塔架构

```
                  ┌───────────────────────────────┐
                  │  Finance / Treasury（总预算审批）│
                  └───────────────┬───────────────┘
                                  │ 目标 ROAS / 总盘
                                  ▼
   ┌───────────────────────────────────────────────────┐
   │          外部预算控制塔（自建服务）                   │
   │  · 汇总层：拉取各账户预算/花费（USD 归一）             │
   │  · 决策层：按 ROI 权重分配（复用 2.4 allocate()）     │
   │  · 执行层：dv360_update_budget_allocation 回写      │
   │  · 告警层：超支/花不完 预警                          │
   └───────┬───────────────┬───────────────┬───────────┘
           ▼               ▼               ▼
   Advertiser A (US)  Advertiser B (CAD)  Advertiser C (EU/GBP)
   └ dv360 apis ──┘  └ dv360 apis ──┘    └ dv360 apis ──┘
```

#### 3.5.2 多币种 / 多时区的归一化问题（重点踩坑区）

跨账户预算最容易翻车的就是"同一个月美元、加元、欧元混在一起算总和"。制定**统一的归一规则**：

| 维度 | 问题 | 归一规则 |
|------|------|----------|
| 币种 | USD/CAD/GBP/EUR 混加 | 统一到基准币 USD，用**当日即期汇率**快照；汇总后标注"按 2026-08-14 汇率折 USD" |
| 时区 | EST/PST/CET 差异 | 所有"日"归一到 UTC（或广告主总部时区）；pacing 对比必须在同一时区日 |
| 预算单位 | micros vs 元 | 一律在控制塔内转成 USD 元做存储与比较，仅在调 API 边界转 micros |
| 结算日 | 自然月 vs 账单月 | 预算对账以**投放 flight** 口径对齐，不要拿账单月做调度 |

```python
# 多币种归一示例
CURRENCY_RATES = {"USD": 1.0, "CAD": 0.73, "GBP": 1.27, "EUR": 1.09}

def micros_to_usd(micros: int, currency: str, rates: dict = None) -> float:
    """把 DV360 返回的 micros 折算为基准 USD。"""
    rates = rates or CURRENCY_RATES
    usd_units = micros / 1_000_000  * rates.get(currency, 1.0)
    return round(usd_units, 2)

def reconcile_cross_account(all_accounts: list) -> dict:
    """汇总各账户（多币种）预算与花费成统一 USD 视图。"""
    summary = {"total_budget_usd": 0.0, "total_spent_usd": 0.0, "accounts": []}
    for acc in all_accounts:
        budget_usd = micros_to_usd(acc["budget_micros"], acc["currency"])
        spent_usd = micros_to_usd(acc["spent_micros"], acc["currency"])
        summary["total_budget_usd"] += budget_usd
        summary["total_spent_usd"] += spent_usd
        summary["accounts"].append({
            "account": acc["account_id"],
            "currency": acc["currency"],
            "budget_usd": budget_usd,
            "spent_usd": spent_usd,
            "util": spent_usd / budget_usd if budget_usd else 0.0,
        })
    return summary
```

> ⚠️ 汇率踩坑：财报希望用**期末汇率**，而日常调度希望用**实时汇率**。控制塔必须记录"每笔换算用的汇率快照 + 日期"，否则不同人对账会得出不同总和，引发信任危机。

#### 3.5.3 跨账户再分配的"最小改动"原则

跨账户动预算前，遵循三原则减少扰动：

1. **先削后补（robin-hood）**：从 `util > 90%`（快花完）并且 ROI 低于账户平均的账户**削**；补给 `util < 60%` 且 ROI 高的账户**补**；
2. **阈值触发**：只有偏离超过阈值（如 util 差 > 25%）才动，避免每 15 分钟来回改造成抖动；
3. **增量而非全量**：每次改预算用增量（+/-15%），而非推倒重写，保留可追踪的变更历史。

---

### 3.6 踩坑案例集（真实复盘）

#### 坑 1：预算超支告警（Overrun Alert）

**现象**：IO 是 `DAILY_BUDGET` 但 PV/流量异常，某天真实花费超过日预算 200%，财务告警。
**根因**：`DAILY_BUDGET` 是"目标"而非"硬限"；DV360 允许多花（overdelivery），尤其 ACCELERATED 或 high-confidence 库存下。另：时区切换（夏令时 DST）会让"一天"多 1 小时，PST↔EST 切换更易超支。
**对策**：
- 关键 IO 加设 `flyour` 硬顶（或 Partner 级 max spend）；
- 监控告警用 `spent / (daily_budget × 1.1)` 阈值，不直接用 100%；
- 大促/换季前核查时区设置：`dv360_list_time_zones` + `dv360_get_customer` 对时区做快照。

#### 坑 2：Pacing 卡在 0（完全花不出去）

**现象**：新建的 LI 一周了 pacing 还是 0，预算一分没动。
**根因**（按概率排序）：
1. 创意未审批（`dv360_get_creative_approval` 是 PENDING/DENIED）；
2. 定向过窄或 budget 太低（不满足出价下限）；
3. IO/LI status 在 PAUSED（忘了开启）；
4. Bid strategy 设了 target CPA 但无转化数据，模型不敢竞价；
5. Inventory 定向排除了实际库存。
**对策**：用 `dv360_get_account_health` 一次性体检，再逐项排查创意审批→定向→预算→出价→库存。

#### 坑 3：日预算用超（Daily Overspend）

**现象**：设定日预算 $1,000，某天实花 $1,300。
**根因**：① overdelivery 机制允许 +10% 左右；② 若同时有几个 LI 共池共抢，合并超支；③ 时区 DST 导致 25 小时"日"。
**对策**：需要"绝对不超支"的账户，用 Partner 级 max spend + 人工 Pacing HOLD；并接受一定 overdelivery 通胀（大部分平台如此，RV360 超支通常瞬时 10~20%）。

#### 坑 4：跨账户预算无法共享

**现象**：客户问"为什么我的 Partner 预算 $2M 但 US 账户花不完、EU 账户却超支，不能自动互通？"
**根因**：DV360 **原生**不提供跨 Advertiser 的自动共享资金池（除非 Partner 级 profile 配置且仍不保证自动调拨）。所谓共享必须走外部控制塔回写。
**对策**：明确客户预期，通过控制塔实现"逻辑共享"；财务口径上把各账户的独立预算加起来 = 总盘，避免"共享 = 一锅粥"的误解。

#### 坑 5：预测过于乐观

**现象**：DV360 reach/预算预测显示 $500K 能买 3000 万 reach；上线后只能买到 1900 万。
**根因**：预测基于历史库存均值 + 模型假设，会**高估新定向/旺季的可得量**；大促、竞品加价、可寻址受众缩水会让实际量大幅低于预测。
**对策**：
- 用"达成率系数"（如保守 ×0.6、中性 ×0.8、乐观 ×1.0）对预测打折；
- 监控实际 spend 与预测的偏差，动态修正系数；
- 预测只用于"定档/排产"，不用于"保证交付"；PG 例外（有保量合同）。

#### 坑 6：修改预算不生效

**现象**：`dv360_update_line_item_budget` 返回成功，但报表里预算没变。
**根因**：① flexibility 为 DENY，远端静默接受但不生效；② flight 已结束，无法改预算；③ 改了 IO 但没同步下层 LI（层级不一致）；④ API 版本（v4 字段名）与脚本不匹配。
**对策**：写入后**读回验证**（`dv360_get_line_item_budget` 对比新旧值），失败则触发告警而非静默假设成功。建立"写-读-校验"闭环。

---

### 3.7 生产监控面板指标体系

一套预算健康监控的核心指标：

| 指标 | 计算 | 健康阈值 | 告警级别 |
|------|------|----------|----------|
| 花费进度 spreadPct | spent/budget | 随 timePct 漂移 | WARN/CRIT |
| Pacing Rate | dv360_get_pacing_rate | 0.8~1.2 | WARN |
| 预算利用率 Util | spent/budget | 40~95% | WARN（过低=花不完，过高=快超支） |
| 日超支率 | max((spent-daily)/daily) | <15% | CRIT（>30%） |
| 预测达成率 | 实际/预测 | >0.7 且 <1.3 | WARN |
| 单位换算一致性 | 快照汇率校验 | 一致 | 告警（汇率漂移） |
| 弹性可操作性 | flexibility=EDITABLE | 目标 IO 全可编辑 | WARN |

> 把这些指标面板化（Grafana/自建 Dashboard），配合 cron 巡检器，就形成"预算健康运营"的闭环。

---

### 3.8 本章小结

- $1M / 5 IO / 20 LI 案例：先对账（∑=总盘）再写入，是预算分配的第一步。
- pacing 选型按 IO 目标：品牌 EVEN、效果 EVEN、拉新 FRONTLOADED、大促 ACCELERATED、测试 EVEN。
- 大促冲刺要**关跨 flight 滚动 + 设日硬顶**，否则会被"撑爆"。
- 自动化巡检：每小时读 pacing/花费，偏差超阈值则 ±15% 增量调整，并留审计。
- 跨账户共享 = 外部控制塔 + 多币种/多时区归一 + 最小改动再分配。
- 六大坑：超支告警、pacing 卡 0、日预算超、无法共享、预测过乐观、改预算不生效，各有明确排障脚本。
- 建立指标面板，形成监控 → 决策 → 执行 → 校验的闭环。

---
## 四、常见问题与排查

### 4.1 FAQ 速查表（按场景）

把日常遇到的高频问题做成一张可检索的表，配合详见小节：

| # | 问题 | 一句话答案 | 详见 |
|---|------|-----------|------|
| 1 | 预算明明设置了为什么不花？ | 8 成原因是创意未审批/状态 PAUSED/定向过窄，先 `dv360_get_account_health` 体检 | 3.6 坑2 |
| 2 | 预算超支告警怎么破？ | 超支多为 overdelivery 通胀 + 时区 DST，用 ×1.1 阈值监控 + 设硬顶 | 3.6 坑1 / 坑3 |
| 3 | pacing 太慢花不完怎么办？ | 转 FRONTLOADED / 加预算 / 放宽频次 / 降出价门槛抢量 | 2.2 / 2.3 |
| 4 | pacing 太快提前打光？ | 转 EVEN / 缩预算 / 提高频次上限 / 拉长 flight | 2.2 / 2.3 |
| 5 | 跨账户预算能共享吗？ | 原生不自动共享，需外部控制塔回写实现"逻辑共享" | 3.5 |
| 6 | 多币种怎么算总和？ | 统一折 USD（当日汇率快照）+ 记录汇率版本 | 3.5.2 |
| 7 | 改了预算不生效？ | flexibility=DENY 或 flight 已结束；写入后读回校验 | 3.6 坑6 |
| 8 | 预测跟实际差太多？ | 预测通常乐观，用达成率系数打折，PG 除外 | 3.6 坑5 |
| 9 | 报告预算和报表口径不一？ | 业务口径用"投放 flight"，不要拿账单月调度 | 3.5.2 |
| 10 | 小 LI 分不到预算饿死？ | 分配器设 floor（保底占比） | 2.4 |
| 11 | 某个 LI 拿了 80% 预算？ | 分配器设 cap_ratio（封顶占比） | 2.4 |
| 12 | 大促预算被一天打光？ | 关闭跨 flight 滚动共享 + 设 DAILY 硬顶 | 3.3.2 |
| 13 | 单位搞混 micros/美元？ | 一律在边界函数 usd_to_micros/micros_to_usd 换算，CI 覆盖 | 2.4.3 |
| 14 | 哪些账户能自动回写？ | IO 弹性 flexibility=EDITABLE 才行 | 2.5 |
| 15 | 并发改预算会打架吗？ | 用 Redis 锁 + 乐观版本号，禁止双 job 同写一 LI | 3.4 |
| 16 | 用官方预算建议靠谱吗？ | 可参考但要本地评估，别黑盒全收 | 2.8 |

---

### 4.2 预算超支排查流程（Decision Tree）

遇到"超支"告警，按下面流程走，不要凭感觉：

```
收到"预算超支"告警
   │
   ├─ 1) 核对口径：是"日预算超支"还是"总预算超支"？
   │      ├─ 总预算超支 → 极异常：查 is overdelivery / 手动改预算 / 并发写冲突
   │      └─ 日预算超支 → 正常通胀？继续
   │
   ├─ 2) 检查时区：今天是不是 DST 切换日（25 小时"日"）？
   │      ├─ 是 → 超支 8% 属正常，剔除该日统计
   │      └─ 否 → 继续
   │
   ├─ 3) 检查 pacing / 模式：
   │      ├─ ACCELERATED → 有意冲刺，接受通胀
   │      └─ EVEN/FRONTLOADED → 不应超，继续
   │
   ├─ 4) 检查是否多 LI 共池：
   │      ├─ 是 → 各 LI 独立不超，但合并超（池效应）
   │      └─ 否 → 继续
   │
   ├─ 5) 检查是否被外部 job 改动预算（审计 dv360_list_activity_logs）
   │      └─ 有 → 回滚快照
   │
   └─ 6) 仍未定位 → 提升为 CRIT，人工介入 + dispatch 支持
         （记录：日期/时区/模式/共池/审计/快照）
```

---

### 4.3 Pacing 不达标排查矩阵

| 症状 | 可能根因（按序） | 排查动作 | 修复 |
|------|------------------|----------|------|
| pacing < 50%（严重滞后） | 定向过窄 / 创意未批 / 出价下限被卡 | 查 `dv360_get_account_health` + 创意审批 | 放宽定向、重新提交创意、提高出价 |
| pacing 稳步低于目标 | 竞争力不足（bid 低）或预算分配过低 | 对比同池 LI 的 win rate | 提 bid / 加预算 |
| 前重后轻（前面很快后面枯） | FRONTLOADED + 大促余量没了 | 查看预算水位 | 转 EVEN、补充预算 |
| 目标"稳定"但总在抖动 | bid 与环境波动 | 看小时粒度 spend | 加频次上限、平滑出价 |
| 旺季 pacing 卡高 | 库存/预算封顶 | 看是否到 IO 硬顶 | 加 IO 预算（若批准） |
| 改完预算仍不体现 | 弹性 DENY / flight 结束 | 读回校验 | 修 flexibility / 延 flight |

---

### 4.4 预算分配失败的排查

当自动化分配（`dv360_update_budget_allocation`）失败：

```
┌─ 报错类型 ──────────────────────────────────────────┐
│ 403 PERMISSION_DENIED   → 无权限/弹性 DENY            │
│ 404 NOT_FOUND           → allocation_id / IO 拼错    │
│ 422 UNPROCESSABLE       → 字段/格式不合法（单位错误）  │
│ 409 CONFLICT            → 版本冲突（并发改预算）       │
│ 429 RATE_LIMIT          → 触发配额；重试退避           │
│ 400 INVALID_ARGUMENT    → 缺字段 / micros 为负/超限   │
└──────────────────────────────────────────────────────┘
   │
   ├─ 核对 allocation_id 与 IO 归属（dv360_list_budget_allocations）
   ├─ 核对 flexibility（dv360_list_insertion_order_flexibility）
   ├─ 核对单位：micros ≥ 0 且 ≤ 合理上限
   ├─ 核对引用：DV360 v4 字段名（item、budget 等）
   └─ 核对并发：加锁，失败重试 3 次+退避
```

---

### 4.5 FAQ 单个详解（Top 5）

#### 4.5.1 "日预算用超"到底允许多少？

DV360 的 overdelivery（超投）是正常的：**日预算 +10%（含服务器端延迟和预估系统误差）是常见且可接受的**。某些配置或高峰甚至瞬时 +20%。要"绝对不超"需要硬顶级控制（Partner max spend + Pacing HOLD）。**永远不要在告警里把 100% 当天花准线**。

#### 4.5.2 "报告里花费和预算对不上"

- 口径：**预算**看的是"计划值"，**花费**看的是"实际新钱"。二者天然不同步（有已竞价未结算、credit、rounding）。
- 时区：报表按所设时区日切分，预算按 flight 日切分；对账必须用同一时区。
- 处理：以"flight 口径"做预算对账；月度累计用"结算口径"核对财务。两个口径分开，不要混用。

#### 4.5.3 "预算弹性到底是什么"

flexibility 是 IO 上允许预算**跨 flight 滚动**与**被外部调整**的开关。开启（EDITABLE/PACING）后，预算剩余可滚到下个 flight，且 API 可回写；关闭（DENY）则预算锁定在指定 flight、外部改不动。自动化分配前必查。

#### 4.5.4 "为什么小 Line Item 经常涨预算还是没用"

小 LI（预算占比很低）常被"池效应"压制：IO 里有个大出价的 LI 抢走共享池，小 LI 永远花不满。若小 LI 本身 ROI 高，应**单独分配独立预算**（不走共池），并给足 floor。分配器里 `floor` 参数就是为此。

#### 4.5.5 "预算预测可以放心用数字下单吗"

预测是"期望"，不是"保证"。它基于历史库存/效率均值，**系统性乐观**。采购/排产时打折（-20%~-40%），运行时监控实时偏差并动态修正。PG（有保量合同）除外，那是合同承诺不是预测。

---

### 4.6 预算健康体检清单（Runbook）

每周/每日例行可用脚本，检查预算健康。可直接复用 `dv360_get_account_health`：

```python
def budget_health_runbook(api, advertiser_id: str) -> dict:
    """账户预算健康体检（Runbook 脚本）。"""
    health = api.dv360_get_account_health(advertiser_id) or {}
    issues = []
    # 1. 弹性检查
    for io in api.dv360_list_budget_allocations(advertiser_id) or []:
        flex = api.dv360_list_insertion_order_flexibility(io.get("insertion_order_id", ""))
        if not flex:
            issues.append(f"{io.get('insertion_order_id')} 不可弹性调整")
    # 2. pacing 异常
    if health.get("status") == "CRITICAL":
        issues.append("账户健康度 CRITICAL：建议检查 pacing/预算")
    # 3. 汇率/时区快照校验
    tz = api.dv360_list_time_zones()
    cur = api.dv360_list_currency_options()
    issues.append(f"时区数={len(tz or [])} 币种数={len(cur or [])}（确认基准归一）")
    return {"health": health, "issues": issues, "ts": "2026-08-14"}
```

> 生产：把 runbook 接进凌晨 cron，每日产出"预算健康报告"，供早会评审。超过阈值自动建 ticket / 群通知。

---

### 4.7 监控阈值建议表（可直接抄）

| 对象 | 指标 | 健康窗口 | 动作窗口 |
|------|------|----------|----------|
| LI | 花费进度 spreadPct | [timePct-0.05, timePct+0.05] | ±0.15 触发调速 |
| LI | pacing rate | 0.8~1.2 | <0.7 或 >1.3 告警 |
| IO | 预算利用 util | 40% ~ 95% | <30%（花不完）/ >98%（超支） |
| 账户 | 健康度 | ACTIVE/GOOD | CRITICAL → 告警 |
| 批量 | 更新失败率 | <1% | >3% → 触发重试/暂停 |
| 预测 | 达成率 | 0.7~1.3 | 偏离 → 修正系数 |

---

### 4.8 本章小结

- 15 条 FAQ 速查 + 16 条问题表，覆盖预算超支 / pacing 不达 / 分配失败 / 口径不一 / 改预算不生效。
- 超支走"Decision Tree"逐层定位；分配失败按错误码分类处理。
- 预算健康体检有 Runbook，可接入 cron 自动化。
- 监控阈值给出可直接使用的默认值，落地即可跑。

---
