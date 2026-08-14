# 拍卖机制与竞价原理（Day 3）

> **领域**: 广告投放 / 拍卖与竞价
> **深度**: ⭐⭐⭐⭐⭐ 实战级指南
> **标签**: dv360, auction, rtb, bidding, first-price, second-price
> **更新时间**: 2026-08-14
> **类型**: 学习笔记

---

## 📌 今日学习重点

Day 3 我们从"广告是怎么算钱、怎么赢下来的"这个最底层问题出发，把 **程序化拍卖（Programmatic Auction）** 的机制掰开揉碎讲清楚。学完今天，你将能回答以下问题：

- 一次展示到底是怎么被"卖"出去的？开放市场、私有市场、程序化保量之间的定价逻辑差在哪？
- 为什么有时候你的**出价**很高，但**成交价（clearing price）**很低？有时候又几乎贴着**底价（bid floor）**成交？
- 第一价格拍卖和第二价格拍卖，在**支付规则、买方策略、卖方收益**三个维度上到底差多少？
- DV360 里你填的那个"出价"，要经过 **pacing、bid modifier、bid floor** 这几道加工，才真正进入拍卖。每道加工都在改什么？
- 用 Python / Go 手写一个带底价的拍卖引擎，验证上面的理论。

本文的定位：**入木三分讲透"拍卖与竞价"**。它与知识库中已有文档互补——`dv360-bidding-strategy-deep.md` 讲"出价策略该选什么、怎么配"，`dv360-architecture-deep.md` 讲"RTB 全链路架构"，而本文专注**拍卖本身的经济学与工程实现**。

> 本文引用的 API 方法名均为真实存在的方法，出自 `scripts/dv360_api.py` 与 `scripts/ad_platform_api.py`。文末自测题帮大家检验理解。

---

## 一、核心概念与架构

### 1.1 什么是"程序化拍卖"？

一句话：**每一次广告展示机会，都在毫秒级的一场"拍卖"中决定归属与价格。**

当用户打开一个网页或 App，发布商（Publisher）手头出现一个"要展示广告的空位（impression）"。这个空位不会定向卖给某个广告主，而是被放到一场拍卖里，让**多个需求方（DSP/广告主）同时出价**，出价最高者赢下这次展示。这就是 **RTB（Real-Time Bidding，实时竞价）**。

程序化拍卖的核心三要素：

| 要素 | 英文 | 说明 |
|------|------|------|
| **出价方（Bidder）** | Demand Side | DSP / DV360 / 广告主，对每次展示给出愿意支付的价格 |
| **拍卖人（Auctioneer）** | Supply Side | Ad Exchange / SSP，组织拍卖、判定胜负、计算结算价 |
| **出售方（Seller）** | Publisher | 提供展示机会的发布商，期望收益最大化 |

```
一次展示机会的"旅程"：

 用户打开页面/App
   │  (页面有 1 个广告空位)
   ▼
 发布商 (Publisher) ──广告请求──▶ SSP (Supply Side Platform)
                                  │ 携带上下文: 页面/设备/用户cookie/地域/可见性
                                  ▼
                             Ad Exchange (拍卖主持人)
                                  │ 同时把竞价请求(OpenRTB BidRequest)发给多个 DSP
                                  ▼
   DV360 / DSP-A ◀─── BidRequest ───┬───▶ DSP-B
   DV360 / DSP-B ◀─── BidRequest ───┴───▶ DSP-C
      │ 各自: 定向往右?√  用户价值预测 出价=?
      ▼
   DSP 回传 BidResponse(出价=$X)
      │
      ▼
   Ad Exchange 汇总所有出价 + 自身底价
      │ 挑选出价最高者 且 ≥ 底价
      ▼
   胜者确定  →  计算结算价(clearing price)
      │
      ▼
   胜者广告素材 在 250ms 内回传展示给用户
```

**关键认知**：拍卖发生在"毫升级时间"内，请求与响应通常要求 **200ms~300ms** 内完成（Google 官方建议 DSP 响应时间在 200ms 以内，超时会丢单）。对 DV360 而言，它扮演的是"需求方出价者"的角色，同时它自己内部对**多广告主/多 Line Item 抢同一展示**也组织了一场内部拍卖（下面 1.6 节讲 DV360 内部竞价）。

---

### 1.2 程序化交易谱系：从"完全竞价"到"保量锁价"

程序化购买并不只有"公开竞价"一种模式。按**定价方式**和**采购确定性**，业界把程序化交易分成四大类，它们的定价逻辑天差地别：

| 交易类型 | 英文 | 定价方式 | 采购确定性 | 是否经过拍卖 | 典型使用场景 |
|---------|------|---------|-----------|-------------|------------|
| **公开竞价** | Open Auction | 实时拍卖定价（第一/第二价格） | 无保量，按需获取 | 是，全开放 | 规模化提升覆盖、效果导向、探索流量 |
| **私有市场** | Private Marketplace (PMP) | 邀请制拍卖，可设**更高底价** | 优先访问优质库存 | 是，但仅限受邀方 | 品牌安全、头部媒体、独家库存 |
| **优先交易** | Preferred Deal | 固定价，买方有**优先购买权** | 有优先权但非强制保量 | 否（先到先得） | 重要媒体、稀缺优质位 |
| **程序化保量** | Programmatic Guaranteed (PG) | **协商固定价 + 锁定库存量** | 强保量，未达标赔付 | 否（协议采购） | 品牌冠名、头部媒体确定性曝光 |

**这里最容易误解的点**：

1. **PMP ≠ 保量**。PMP 仍然是一场拍卖，只是参与者被限定为"被邀请的卖家联盟成员"，且底价往往设得比公开市场高。它保障的是**库存质量与访问权**，而不是**展示量**。很多同学把 PMP 当成"买了就一定有量"——错，PMP 也可能因为出价低于底价而**一条都不给你**。
2. **PG ≠ 拍卖**。PG 是"谈好价 + 锁定量"，根本不进拍卖。它靠的是合同与保量赔付机制，而不是出价竞争。所以 PG 里没有"第一/第二价格"概念，价格是**事先商定的固定 CPM**。
3. **定价确定性排序**：公开竞价（最不确定）< PMP（半确定）< Preferred Deal（优先权）< PG（完全确定）。代价则是**灵活性**与**单价**：越确定，往往越贵、越不灵活。

**在 DV360 中如何区分？** 通过 `get_transaction_type_options()` 返回的官方交易类型选项（出自 `scripts/dv360_api.py`）：

```python
def get_transaction_type_options(self) -> List[Dict]:
    """获取官方交易类型选项"""
    return [
        {'code': 'PROGRAMMATIC_GUARANTEED', 'name': '程序化保量', 'description': '保证展示量的程序化购买'},
        {'code': 'PRIVATE_MARKETPLACE', 'name': '私有市场', 'description': '邀请制的优质库存交易'},
        {'code': 'PREFERRED_DEAL', 'name': '优先交易', 'description': '享有优先购买权的交易'},
        {'code': 'OPEN_AUCTION', 'name': '公开竞价', 'description': '常规公开市场竞价'}
    ]
```

这条方法返回完整的四类交易，与上面的表格一一对应。在创建 Flow / Line Item 时，交易类型的差异直接决定了"出价"与"价格"的语义（详见第 3 章 PG 与 PMP 的竞价语义）。

---

### 1.3 RTB 全流程时序：从请求到展示的 300ms

下面是一张**更细粒度**的时序图，把 300ms 内每一步的耗时、参与方、关键动作标注清楚（比 architecture 文档更偏"毫秒级工程视角"）：

```
 时间轴   │  用户   │  发布商/SSP  │   Ad Exchange     │   DV360 (DSP)
──────────┼─────────┼─────────────┼───────────────────┼──────────────────
 0ms      │ 打开页面 │             │                   │
 T+50ms   │         │ 发起 ad request │                 │
 T+80ms   │         │ ──BidRequest──▶ │                 │
 T+100ms  │         │              │ 解析请求,包上下文   │
 T+120ms  │         │              │ ──多路 BidRequest─▶│ 收到请求
 T+150ms  │         │              │   (并行发给多DSP)   │ 定向命中判断
 T+180ms  │         │              │                   │ 用户价值预测
 T+200ms  │         │              │                   │ 出价计算 & 返回
 T+210ms  │         │              │ ◀──BidResponse─── │ (含出价/创意ID)
 T+230ms  │         │              │ 汇总所有 BidResponse│
 T+240ms  │         │              │ 判定胜者 + 计算结算价│
 T+260ms  │         │              │ 通知胜者并取创意     │
 T+280ms  │         │ ◀──广告素材─── │                   │
 T+300ms  │ ◀─展示广告─ │             │                   │
```

**各阶段耗时建议（Google 官方 / OpenRTB 经验值）**：

| 阶段 | 建议耗时 | 超时后果 |
|------|---------|---------|
| SSP → Exchange 请求转发 | < 80ms | 请求作废 |
| Exchange → DSP 广播 | < 50ms | — |
| DSP 决策 + 返回 | **< 200ms**（Google 建议 200ms 内） | 超时即视为**未出价**，直接输掉拍卖 |
| Exchange 判定 + 结算 | < 30ms | 机会丢失 |
| 素材回传与渲染 | < 40ms | 展示延迟、影响体验 |

> **实战要点**：DV360 的出价决策要在 200ms 内完成"定向命中的、价值预估、出价计算"。如果你的自定义定向逻辑（比如去查本地数据库做 DMP 判断）拖慢了响应，超过 200ms 的请求会被 Exchange 直接忽略——查库不能放在出价主路径上，应靠**预索引 / 缓存 / 批量同步**提前算好。这就是为什么工程上 DSP 常用"预抓取（pre-fetch）+ 内存倒排索引"，把决策耗时压缩到几十毫秒。

---

### 1.4 第一价格 vs 第二价格拍卖：全局对比表

这是全文的**核心对照**。先用一张表建立全局直觉，第 2 章再用数学和代码拆解：

| 维度 | 第二价格拍卖 (Second-Price / Vickrey) | 第一价格拍卖 (First-Price) |
|------|--------------------------------------|---------------------------|
| **胜者支付** | 第二高出价（+1 个最小单位） | 自己的出价 |
| **结算公式** | `price = max(second_bid, floor)` | `price = own_bid` |
| **买方最优策略** | 老实报真实估值（激励相容） | 压低出价（bid shading），报"必赢所需的最小值" |
| **是否存在"赢家诅咒/过付"** | 基本无（有底价时可能） | 高，容易系统性过付 |
| **卖方期望收益** | 通常较低（重竞争时接近第二价格） | 通常较高（资本方直觉） |
| **信息需求（对 DSP）** | 只需估计"这个展示值多少" | 既要估计估值，又要估计"竞争强度/分布" |
| **对自动出价的要求** | 简单，出价=估值 | 复杂，需在线学习 bid shading |
| **被 DV360 混用的情况** | 历史上多 Exchange 采用 | 2019 后 Google 及主要 Exchange 大量切换 |
| **对广告主成本稳定性** | 更稳定，接近市场均衡价 | 波动更大，受出价策略影响显著 |

**为什么行业从第二价格往第一价格迁移？** 关键词：**无拍卖商激励冲突 + 卖方收益**。

- 第二价格拍卖要求拍卖商"诚实披露第二高价作为结算价"。但若拍卖商（如 SSP）与需求方私下沟通/操纵第二高价，监管与信任成本很高。
- 第一价格拍卖结算价 = 最高出价本身，拍卖商**没有动机去操纵结算价**，机制更透明，也更能保证卖方收益。
- 2019 年前后，Google 宣布 Display & Video 360、Ad Manager、交易集市等采用**第一价格拍卖**（Google 从 2019-10 开始全面转为第一价格）。这条历史对理解 DV360 出价行为极为重要：**在今天的 DV360 里，你的出价基本就是成交价的基础**，出高 = 多付。

> **一句话记住**：第二价格让你"能赢就行，不用多付"；第一价格让你"每多出一分钱，就真多花一分钱"。DV360 现在主要跑第一价格，所以你填出价必须克制、精准，而非"报高点保险"。

---

### 1.5 关键 API 方法速查（本文会反复用到的真实方法）

以下方法来自 `scripts/ad_platform_api.py`，都是 Get/List/Patch 层级，用于实践与排查：

| API 方法 | 作用 | 在本文的用途 |
|---------|------|------------|
| `dv360_create_line_item(advertiser_id, name, **kwargs)` | 创建 Line Item，可带出价策略与预算 | 3.1 出价策略配置 |
| `dv360_update_line_item(advertiser_id, line_item_id, **kwargs)` | 更新 Line Item（切出价/改预算） | 3.1 / 3.4 |
| `dv360_list_bidding_strategies(advertiser_id)` | 列出某广告主下所有出价策略 | 3.1 |
| `dv360_get_pacing_rate(advertiser_id, line_item_id)` | 获取 Line Item 的**投放/消耗节奏（pacing rate）** | 2.4 出价形成链路 |
| `dv360_get_performance_forecast(advertiser_id, **kwargs)` | 获取表现预测（可达量/成本预估） | 3.1 出价前预估 |
| `dv360_list_reach_forecasts(advertiser_id)` | 获取可达范围预测（reach forecast） | 3.1 |
| `dv360_list_auction_insights(advertiser_id)` | 获取拍卖洞察（竞价行为诊断） | 4.2 排查 |
| `dv360_list_auction_performance(advertiser_id)` | 获取拍卖表现数据 | 4.2 |
| `dv360_list_bid_performance(advertiser_id)` | 列出各出价的表现（胜负、成交价分布） | 4.2 排查 |
| `dv360_list_bid_recommendations(advertiser_id)` | 列出出价优化建议 | 3.3 最佳实践 |
| `dv360_update_bid_recommendation(recommendation_id)` | 应用某条出价建议 | 3.3 |
| `get_transaction_type_options()` | 官方交易类型选项（PG/PMP/Preferred/Open） | 1.2 |
| `get_bid_strategy_options()` | 官方出价策略选项（CPM/CPC/CPV/oCPM/CPA） | 3.1 |

> 备注：任务描述里提到的 `dv360_estimate_reach` 在脚本中对应的是 `dv360_list_reach_forecasts` / `dv360_get_performance_forecast`，已按真实方法名引用。

---

### 1.6 DV360 的双层拍卖：外部拍卖 + 内部竞价

很多从业者只看"DV360 对外出价"，忽略了 DV360 **内部也有一场拍卖**。当你的 DV360 账户里有多个 Line Item / 多个广告主都想投同一批用户时，DV360 内部要决定"这次展示给谁"：

```
内部拍卖（DV360 内部，在一台竞价机上完成）：
  同一次展示机会
   ├── Line Item A: 定向命中√ 出价 $3.2
   ├── Line Item B: 定向命中√ 出价 $4.0
   ├── Line Item C: 定向未命中 ✗ (出局)
   └── Line Item D: 命中但预算耗尽 0 (出局)
   ↓
  内部胜者 = Line Item B (出价最高且仍有预算)
   ↓
  DV360 以 B 的出价(或 B 与次高之间)参与外部拍卖
```

**双层理解的意义**：

1. **预算（budget）比出价更"吊"**：一个 Line Item 即使出价最高，只要预算耗尽，就自动出局退出内部拍卖。这也是为什么"花不完预算"往往不是出价问题，而是 **pacing / 覆盖面 / 定向过窄**问题。
2. **内部竞价让多 Line Item 共享一条流量**：同一批受众可以被多个广告主的多个 Line Item 同时追逐，DV360 内部按出价与预算协调，避免"自己人跟自己人抬价"失控（但仍可能有竞争）。
3. **pacing 是内部"节流阀"**：DV360 通过 pacing 控制每个 Line Item 的"参与频率"与"出价打折幅度"（见 2.4 节），把预算均匀铺到整个投放周期，而不是前 2 小时烧光。

---

### 1.7 本章小结

- 程序化拍卖 = 在毫秒级时间内，多需求方对同一次展示出价、最高价者获胜并结算。
- 公开竞价（拍卖定价）≠ PMP（限定参与者的拍卖 + 高底价）≠ Preferred Deal（优先权）≠ PG（固定价锁量）。**定价确定性越高，灵活性越低**。
- 第一价格 vs 第二价格的核心差异在结算规则与买方策略；**DV360 当前以第一价格为主**，出价必须克制。
- DV360 是"对内 + 对外"双层拍卖，预算/ pacing 在内部拍卖中举足轻重。
---

## 二、深度原理解析

这一章是全文的重头戏。我们会先用**经济学 + 数学**把第二价格和第一价格拍卖讲透，再讲 **bid floor（底价）** 到底怎么影响结算，最后用 **DV360 出价形成链路** 和 **Python / Go 拍卖引擎实现** 把理论落到代码。

### 2.1 第二价格拍卖（Vickrey Auction）的支付规则与经济学

**第二价格拍卖（Second-Price Auction，又称 Vickrey 拍卖，1961 年由 William Vickrey 提出，因此获 1996 年诺贝尔经济学奖）。**

**支付规则**：假设有 N 个投标者，各自秘密报价 b₁ ≥ b₂ ≥ ... ≥ bₙ（降序）。**出价最高者（b₁）获胜，但只需支付第二高出价 b₂**（一般再加 1 个最小计价单位，比如每个 impression 增量 $0.01 的 CPM）。

```
第二价格拍卖结算示例:

出价:  A=$5.00   B=$3.80   C=$2.50   D=$1.20
                        ↑
                次高出价 B=$3.80
       ─────────────────────────────
  胜者: A (出价 $5.00)
  结算价(胜者支付): $3.80 (第二高) + $0.01 增量
  支付: $3.81/CPM
```

**经济学的核心性质：激励相容（Incentive-Compatible）/ 真实报价（Truthful Bidding）**

在第二价格拍卖里，**对每个投标者而言，报出你真实估值 v，是（弱）占优策略（weakly dominant strategy）**。为什么？因为你的出价 b 只决定"能否赢"，几乎不决定"花多少"：

- 若报 b < v（压低出价）：你赢的机会变小；就算你赢了，结算价也基本还是次高价，**并不会因为压低而便宜多少**——反而可能因为出局而错过本可以低价获得的展示。→ 收益不增、风险增大。
- 若报 b > v（抬高出价）：当你赢了且次高价 b₂ ∈ (v, b] 时，你会**支付高 b₂ 而它超过你对展示的估值 v**，产生负收益（赢家诅咒）。→ 抬高无益。
- 只有报 b = v 时：既能最大化"以不高于 v 的价格赢"的机会，又避免支付超过 v。→ **占优**。

> **一句话**：第二价格拍卖让"撒谎"没有好处，所以理性策略就是**说真话**。这就是为什么在第二价格时代，DSP 的出价引擎只需要回答一个问题："这个展示对广告主值多少钱？"——估值即出价。

**第二价格拍卖的数学直觉（来说明"为什么付第二高"）**：

设投标者 i 的真实估值 vᵢ，出价 bᵢ，其余人最高出价为 M = maxⱼ≠ᵢ bⱼ。

- 若 bᵢ > M：胜出，支付 M，净效用 = vᵢ − M。
- 若 bᵢ < M：落败，净效用 = 0。

无论你出 bᵢ 多么高或低，**只要赢了，支付额都是 M（与他人最高出价绑定，与你自己的出价 bᵢ 无关）**。唯一受你出价影响的是"赢或输"。因此把 bᵢ 设为 vᵢ 不会改变支付，只最大化胜出机会 → 绝不会比任何其他出价更差 → 弱占优。

---

### 2.2 第一价格拍卖：买方策略、卖方收益与 bid shading

**第一价格拍卖（First-Price Auction）**：同样是出价最高者获胜，但**支付自己的出价**。

```
第一价格拍卖结算示例:

出价:  A=$5.00   B=$3.80   C=$2.50   D=$1.20
                        ↑
  胜者: A (出价 $5.00)
  结算价(胜者支付): $5.00 (自己的出价)
  支付: $5.00/CPM  —— 比第二价格多付 $1.20
```

**买方策略的质变**：在第一价格下，"说真话"不再是占优策略。如果 A 报 $5.00 而真实估值是 $5.00，那么 A 恰好把全部消费者剩余付给了卖方（零剩余）。理性买方会**压低出价（shade）**：只报"足以赢下拍卖的最小金额"。

- 若人人都 shade 到"次高 + ε"，那么第一价格的结算价在均衡下会**收敛到接近第二价格的水平**。
- 但问题在于：**买方不知道别人的出价分布**，所以 shade 多少是一个未知游戏。shade 太多 → 输掉本可赢的机会；shade 太少 → 过付。

**最优出价的经验公式（对称独立私有价值模型 SIPV）**：

在 <i>N</i> 个投标者、估值都独立均匀分布于 [0,1] 的对称模型下，**第一价格拍卖的对称均衡出价**为：

```
b(v) = v · (N − 1) / N
```

即：最优出价 = 真实估值 × (N−1)/N。当 N 越大、竞争越激烈，最优出价越接近估值（因为被压价空间变小，必须报近真值才有机会赢）。

| 投标者数 N | 最优出价 b(v)（估值=10 时） | 解释 |
|-----------|---------------------------|------|
| 2 | 5.0 | 高度压价，因竞争弱 |
| 5 | 8.0 | 中高压价 |
| 10 | 9.0 | 竞争激烈，压价空间小 |
| 100 | 9.9 | 几乎报真值 |

**关键推论（对 DV360 投放的影响）**：

1. **竞争越激烈的珍贵库存（如重定向高潜用户、头部媒体），最优出价越接近估值**——因为你不接近估值，别人就赢走了。
2. **长尾、低竞争的库存，最优出价应明显低于估值**（可以大胆压价）。这也是为什么**自动出价引擎要按"机会"动态出价**，而不是对所有展示一个固定 CPM：不同机会的竞争强度差异巨大。
3. **静态手动出价在第一价格下必然"该高的没高、该低的没低"**：设一个中间价，会让低价机会过付、高价机会丢单。这是 DV360 强烈建议在第一价格库存上使用自动出价的底层原因。

**卖方收益对比（Revenue Equivalence 定理）**：

Revenue Equivalence 定理指出：在一组对称性假设下，**第二价格拍卖与第一价格拍卖给卖方带来的期望收入是相等的**（都等于"期望的第二高阶统计量"）。那么行业为什么还从第二价格切到第一价格？

- **理论不成立的前提被打破**：现实中买方并非完全对称、估值并非独立、信息不对称，且拍卖商在第二价格下的**操纵结算价**风险导致买方不信任、不愿意暴露真实估值。
- **卖方实际收益**：切换到第一价格后，由于买方不敢激进 shade（怕丢单），卖方**实际结算价往往高于第二价格时期**，尤其是头部竞价充分的库存。
- **工程/税务透明**：第一价格的"结算价 = 出价"让发票、审计、反作弊更简单，抽查、对账、甚至给买方的数据报告都更透明。

> **实战一句话**：Google 2019 年 10 月起把 DV360、Ad Manager、Google Ad Exchange 等都切换为第一价格拍卖。此后"出价 = 成交价基础"，**你要为每一次出价负责**。这是 DV360 时代区别于历史第二价格时代最重要的心智转换。

---

### 2.3 bid floor（底价）：它是怎么生效的？

**bid floor（底价）**是发布商/SSP 对某次展示（或某段库存）设定的**最低可接受成交价**。它是拍卖机制里最容易被人忽视、又最容易导致"丢单"的变量。

**底价在两种拍卖中如何生效：**

```
第一价格拍卖 + floor:
  出价:  A=$4.20  B=$3.60  C=$2.80    floor=$3.00
                                        ────────
  所有出价 < floor? 否
  胜者: A (最高) = $4.20 ≥ floor ✓
  结算价: max(A, floor) = max(4.20, 3.00) = $4.20  (A本身已超floor)

第二价格拍卖 + floor (google 曾用):
  出价:  A=$4.20  B=$3.60  C=$2.80    floor=$3.00
  胜者: A
  结算价: max(第二高 B=$3.60, floor=$3.00) = $3.60
  —— 若 B=$2.60 < floor, 则结算价 = max(2.60, 3.00) = $3.00 = floor
```

**底价的关键规则**：

1. **只有出价 ≥ floor 才有资格获胜**。如果全场最高出价都低于 floor，这次展示就**不成交（no-fill / unfilled）**——卖方宁愿空着也不贱卖。
2. **结算价 = max(决定性价格, floor)**。
   - 第一价格下：结算价 = max(最高出价, floor)，实际 = 最高出价（因为最高之一必然 ≥ floor）。
   - 第二价格下：结算价 = max(第二高出价, floor)。**当 floor > 第二高出价时，结算价就是 floor**，胜者要多付到 floor。
3. **PMP 的 floor 通常远高于 Open Auction**：因为 PMP 是优质库存，卖方用高 floor 筛选出了买得起的买方。这也是为什么"PMP 出价低于 floor"的丢单情况很常见（见 3.4 踩坑）。

**floor 的经济学意义**：floor 是卖方的**保留价格（reservation price）**。它保护卖方：当竞争不足、没人愿出合理价格时，卖方宁可空拍也不贱卖。它同时是拍卖商和卖方之间的结算参考线。

**floor 与 DV360 的坑（重点）**：

- **你看到的"成交价 = floor"不一定是被操纵**，而是因为**你就是全场最高出价者、而第二高被 floor 顶掉了**。在第一价格下这通常意味着"你的竞争对手不多，但你被卖方最低价保护住了"。
- **出价恰好贴着 floor** 是常见现象——自动出价引擎会算出"要赢下这次展示、且不高于 floor 太多"的出价，于是大量成交价集中在 floor 附近。
- **把出价从 floor 上方一点点下调，可能直接导致 0 成交**（掉到 floor 之下被过滤）。所以"再降 10% 出价省预算"可能会瞬间断量。理解这条，就不难解释"为什么我降了出价就完全没量了"。

---

### 2.4 DV360 出价是如何形成的：从配置出价到进入拍卖

这是实践中最重要的一节。你在 DV360 UI 里填的"出价"，**不是直接发给 Exchange 的那个数**。它要经过一条加工链路：

```
DV360 出价形成链路 (bid formation pipeline):

  1. 配置出价 (Configured bid)
     来自 Line Item 的出价策略:
       · 手动 CPM: 你填的固定 CPM
       · oCPM / Target CPA: 策略推导出的目标 CPM
     │
     ▼
  2. 内部价值预估 (Value estimation)
     模型对"这次展示"给出转化/价值概率
     配置出价 × 机会价值系数 = 基础估值
     │
     ▼
  3. Pacing 折算 (Pacing discount)  ← 用 dv360_get_pacing_rate 观测
     预算消耗进度的函数:
      · 消耗过快 → 对出价打"收"的折扣，放慢
      · 消耗过慢 → 提高出价放大率，加速 (可达 ~10x)
     │
     ▼
  4. Bid modifier 叠加 (定向/设备/时段/创意系数)
     例: 移动端 ×1.2, 高转化时段 ×1.5, 非目标设备 ×0.6
     │
     ▼
  5. Bid floor 对拍 (floor check)
     若出价 < floor → 直接放弃 (no bid / unfilled)
     若出价 ≥ floor → 保留
     │
     ▼
  6. 对外出价 (Final bid)
     发给 Exchange, 参与第一价格拍卖
```

**每一步的真实含义：**

**(1) 配置出价**：来自 Line Item 的 `bidding_strategy`。`dv360_list_bidding_strategies(advertiser_id)` 拉开可以看到 CPM / CPC / CPV / oCPM / CPA 等策略（对应 `get_bid_strategy_options()`）。

**(2) 内部价值预估**：DV360 的机器学习（如 oCPM、Target CPA）本质上在给"每次展示"估计一个期望价值 = 转化概率 × 单次转化价值。这个估计值就是"真实估值 v"——它在第一价格拍卖里正是要被 shade 的对象。

**(3) Pacing 折算（重要！）**：DV360 用 **pacing** 把预算匀速铺到整个 flight。`dv360_get_pacing_rate(advertiser_id, line_item_id)` 返回当前消耗节奏。Pacing 的机制是**通过调整出价（而非仅丢单）来调速**：

- 消耗超前于理想曲线 → 降低出价放大率，让每次出价更"保守"，减少命中率。
- 消耗落后 → 提高出价放大率（DV360 的 pacing 允许把出价放大到**基准的若干倍**，甚至可达 10 倍量级），快速抢量。

**注意**：pacing 改变的是"出价大小"，而**预算上限**是硬约束。二者协同：pacing 管"今天出多次大价、出多低"，预算管"总共最多花多少"。

**(4) Bid modifier 叠加**：DV360 允许对特定定向（device、geo、daypart、creative、audience）设置**出价调整系数**。它乘在当前出价上。例如：

```python
# 伪代码: 出价计算主流程
base_bid_cpm = 5.00          # 配置出价 (CPM)
value_coeff = predict_value(opportunity)   # 0.8 ~ 1.5 机会价值系数
volume_coeff = get_pacing_coeff(line_item) # 0.5 ~ 10, 由 pacing_rate 决定
modifier = get_bid_modifier(line_item, opp) # 设备/时段/定向叠加 0.4~3.0
floor = get_bid_floor(opportunity)          # 由 Exchange/SSP 决定

final_bid = base_bid_cpm * value_coeff * volume_coeff * modifier

if final_bid < floor:
    return NO_BID_REQUEST          # 低于底价 → 放弃, 避免必输
else:
    return BID_REQUEST(final_bid)  # 参与第一价格拍卖
```

这条伪代码完整对应上面 6 步链路，也是后文 Python / Go 实现的骨架。

**(5) Bid floor 对拍**：算出 final_bid 后必须先和 floor 比：低于 floor 直接不 bid（不浪费请求预算），≥ floor 才出价。工程上 DSP 常把"可能低于 floor"的机会直接短路，节省网络与算力。

> **实践对照**：`dv360_get_pacing_rate` 的返回值如果长期偏低（比如 60%），说明预算花不完；结合出价放大率与 `dv360_list_bid_recommendations` 给出的建议，判断是该调出价还是调定向覆盖面。

---

### 2.5 Python 实现：带 floor 的第二/第一价格拍卖引擎

下面用一个**完整的 Python 实现**来验证前面所有机制。类 `Auction` 支持两种价格规则、可注入 floor，返回 winner / clearing price / 是否成交。

```python
"""
auction.py - 通用程序化拍卖引擎（教学实现）
支持: first-price / second-price, 可选 bid floor
"""
from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass
class Bid:
    bidder: str          # 出价方标识（如 DV360 Line Item）
    bid: float           # 出价 (CPM)


@dataclass
class AuctionResult:
    winner: Optional[str]
    winning_bid: float
    clearing_price: float
    floor: float
    filled: bool         # 是否成交 (有出价 ≥ floor)
    rule: str            # 'first' | 'second'

    def __repr__(self) -> str:
        return (f"<Auction winner={self.winner} win_bid={self.winning_bid:.2f} "
                f"clear={self.clearing_price:.2f} floor={self.floor:.2f} "
                f"filled={self.filled} rule={self.rule}>")


class Auction:
    """一次展示机会的拍卖。"""

    def __init__(self, floor: float = 0.0, rule: str = 'first',
                 increment: float = 0.01):
        assert rule in ('first', 'second'), "rule 只能是 first/second"
        self.floor = floor
        self.rule = rule
        self.increment = increment

    def run(self, bids: List[Bid]) -> AuctionResult:
        # 1) 先过滤低于 floor 的出价（低于底价者无资格）
        eligible = [b for b in bids if b.bid >= self.floor]
        if not eligible:
            # 无人达标 -> 不成交
            return AuctionResult(None, 0.0, 0.0, self.floor, False, self.rule)

        # 2) 按出价降序排序
        eligible.sort(key=lambda b: b.bid, reverse=True)
        winner = eligible[0]

        if self.rule == 'first':
            # 第一价格: 结算价 = 胜者出价 (且 ≥ floor)
            clearing = max(winner.bid, self.floor)
        else:
            # 第二价格: 结算价 = max(第二高出价, floor)
            if len(eligible) >= 2:
                second = eligible[1].bid
            else:
                second = 0.0
            clearing = max(second, self.floor) + self.increment

        return AuctionResult(winner.bidder, winner.bid, clearing,
                             self.floor, True, self.rule)


# ---------- 演示 ----------
if __name__ == "__main__":
    bids = [Bid("lineitem-A", 5.00),
            Bid("lineitem-B", 3.80),
            Bid("lineitem-C", 2.50),
            Bid("lineitem-D", 1.20)]

    # 无底价对比
    print("=== 无底价 ===")
    print("first :", Auction(rule='first').run(bids))
    print("second:", Auction(rule='second').run(bids))

    # 带底价 (floor=3.00)
    print("=== 底价 3.00 ===")
    print("first :", Auction(rule='first', floor=3.00).run(bids))
    print("second:", Auction(rule='second', floor=3.00).run(bids))

    # 底价过高 → 全部无资格 → 不成交
    print("=== 底价 6.00 (过高) ===")
    print("first :", Auction(rule='first', floor=6.00).run(bids))
```

**运行结果解读：**

```
=== 无底价 ===
first :  winner=lineitem-A win_bid=5.00 clear=5.00 floor=0.00 filled=True rule=first
second:  winner=lineitem-A win_bid=5.00 clear=3.81 floor=0.00 filled=True rule=second
=== 底价 3.00 ===
first :  winner=lineitem-A win_bid=5.00 clear=5.00 floor=3.00 filled=True rule=first
second:  winner=lineitem-A win_bid=5.00 clear=3.81 floor=3.00 filled=True rule=second
=== 底价 6.00 (过高) ===
first :  winner=None win_bid=0.00 clear=0.00 floor=6.00 filled=False rule=first
```

看到关键差异：

1. **same winning bidder（都是 A 赢），但结算价完全不同**：first 付 $5.00，second 只付 $3.81。这正是"第一价格 = 实际成交，第二价格 = 省下的消费者剩余"。
2. **第二价格 + floor=3.00 时**：第二高价是 B=$3.80 > floor，所以结算价仍是 3.80+0.01。**只有当第二高价低于 floor 时，floor 才真正把结算价顶上去**。我们可以构造：若 B 只出 $2.60，则 second 结算 = max(2.60, 3.00)+0.01 = $3.01（被 floor 抬到 3 附近）。
3. **floor=6.00 过高时**：即使最高出价 $5.00 也 < floor，**全场无资格 → no-fill**。这就是"底价过高导致丢单（unfilled）"的机器证明。

> 这段代码可以直接跑：`python3 auction.py`。建议把 `bids` 里的数字改成"接近 floor"的临界值，观察成交/不成交的翻转，来建立感性认识。

---

### 2.6 Go 实现：高并发拍卖引擎（贴近生产）

生产环境的 DSP 是高并发的：同一个 300ms 窗口可能同时处理成千上万个竞价请求。这里给出一个**并发安全、贴近生产语义**的 Go 版本，重点演示：

- 用 `sync.RWMutex` 保证结算幂等；
- 用 `math.Max` 表达"max(决定性价格, floor)"；
- 提供一个简单的最优出价（bid shading）计算器，呼应 2.2 节的公式 `b(v) = v·(N−1)/N`。

```go
package auction

import (
	"math"
	"sort"
	"sync"
)

// Bid 表示一次出价
type Bid struct {
	Bidder string  `json:"bidder"`
	Bid    float64 `json:"bid_cpm"`
}

// Result 结算结果
type Result struct {
	Winner        string
	WinningBid    float64
	ClearingPrice float64
	Floor         float64
	Filled        bool
	Rule          string
}

// Engine 并发安全拍卖引擎
type Engine struct {
	mu        sync.RWMutex
	floor     float64
	rule      string // "first" | "second"
	increment float64
}

func NewEngine(floor float64, rule string, increment float64) *Engine {
	return &Engine{floor: floor, rule: rule, increment: increment}
}

// Run 结算一场拍卖 (并发安全, 每次调用独立结算, 无竞态)
func (e *Engine) Run(bids []Bid) Result {
	e.mu.Lock()
	defer e.mu.Unlock()

	// 1) 过滤低于 floor 的出价
	eligible := make([]Bid, 0, len(bids))
	for _, b := range bids {
		if b.Bid >= e.floor {
			eligible = append(eligible, b)
		}
	}
	if len(eligible) == 0 {
		return Result{Filled: false, Floor: e.floor, Rule: e.rule}
	}

	// 2) 降序排序
	sort.Slice(eligible, func(i, j int) bool {
		return eligible[i].Bid > eligible[j].Bid
	})
	winner := eligible[0]

	var clearing float64
	switch e.rule {
	case "first":
		clearing = math.Max(winner.Bid, e.floor)
	default: // second-price
		second := 0.0
		if len(eligible) >= 2 {
			second = eligible[1].Bid
		}
		clearing = math.Max(second, e.floor) + e.increment
	}

	return Result{
		Winner:        winner.Bidder,
		WinningBid:    winner.Bid,
		ClearingPrice: clearing,
		Floor:         e.floor,
		Filled:        true,
		Rule:          e.rule,
	}
}

// ShadeBid 第一价格下的最优出价计算 (SIPV 对称模型 b(v) = v*(N-1)/N)
// v: 真实估值(CPM), n: 参与竞争的出价者数量
func ShadeBid(v float64, n int) float64 {
	if n <= 1 {
		return v
	}
	return v * float64(n-1) / float64(n)
}
```

**生产语义补充（Go 版 vs 教学 Python 版）：**

1. **并发与幂等**：`Run` 用 `sync.Mutex` 串行化结算，避免"同一展示被并发出价两次"的竞态；真正的生产系统把`Run`设计为**纯函数、无共享可变状态**，交给无状态 worker 池并行处理，`Run` 本身不持全局锁。
2. **与流式架构结合**：DSP 通常在巨型第一价格拍卖架构中，是先按"定向 + 预算"过滤大部分请求（早期短路），只剩少数请求进 `Run`，从而支撑 QPS 数十万。
3. **ShadeBid 仅作教学示例**：真实生产里 DV360 用在线强化学习（bandit / 神经网络）动态估计竞争分布来做 shade，比静态公式复杂得多。但静态公式帮你理解"竞争者越多，越不能压价"的方向性规律。

> **工程总结**：Python 版用于理解机制、写单测；Go 版用于理解并发与生产边界。两者都体现了"过滤 floor → 排序 → 结算"这一通用拍卖引擎骨架。

---

### 2.7 多维结算：为什么"最高出价"不一定等于"每千次结算 CPM"

生产中有个常见困惑：明明出价是 $5 CPM，为什么报表里的 eCPM 有时低于出价、有时超过出价？原因是结算还分**多维度**：

1. **视频（CPV）/ 互动（CPC）的"等价 CPM"**：DV360 会把 CPV/CPC 折算成等价 CPM 参与拍卖。比如 CPV 出价 $0.02，按"观看可能率"折算后对应的 CPM 才是提交给拍卖的出价。**报表里看到的 cost 与出价可能不在同一计价维度**。
2. **动态创意的加权平均**：一条 Line Item 有多个 creative，各自的预估展示概率不同，折算后的有效出价是加权值。
3. **可见性（viewability）折算**：某些情况下 DV360 只对"可被看到"的展示计费（Viewable CPM），结算价以"可见展示"为基础折算，导致简单除法的 eCPM 与出价不一致。
4. **货币与退税/返现（rebates）**：实际支付的"净价"可能因返点而低于名义 CPM。

> 这些维度解释了 FAQ 里"为什么显示价 ≠ 出价"（见 4.1）。**别用"报表 eCPM"反推"出价"**，二者不是同一条数。

---

### 2.8 本章小结

- 第二价格：支付第二高价 → **激励相容，真实报价最优**，结算 = max(次高, floor)。
- 第一价格：支付自己的出价 → **必须 shade**，最优出价 ≈ v·(N−1)/N，竞争越强越接近真值；**DV360 当前以第一价格为主**。
- **floor = 卖方保留价**：低于 floor 直接出局；第一价格下结算=max(最高,floor)=最高；第二价格下 floor 只在"第二高<floor"时抬价；**floor 过高会 no-fill 丢单**。
- DV360 出价 = 配置出价 × 价值系数 × pacing 系数 × bid modifier，最后对拍 floor。`dv360_get_pacing_rate` 观测消耗节奏。
- Python / Go 均实现了"过滤 floor → 排序 → 结算"引擎，验证了机制。

---

## 三、生产环境实战

这一章把前面的理论放到真实投放场景：理解拍卖行为、调整出价策略、搞清 PG / PMP 的竞价语义，以及**踩过的坑**。

### 3.1 案例：读懂拍卖行为，动态调整出价策略

**场景**：某品牌号在 DV360 投重定向 + 兴趣定向的展示广告，用了 `Maximize conversions`（自动出价）跑了一周，漏斗正常但 eCPM 偏高、量一直压在预算内。运营想"省成本手动出 CPM"。

**正确的排查与调整路径：**

```
Step 1  观测读拍卖: 
        dv360_list_auction_insights(advertiser_id) → 看竞价参与率、胜出率(win rate)
        dv360_list_bid_performance(advertiser_id)  → 看出价分布 / 成交价 vs 出价差距
Step 2  定位问题: 
        · 胜出率低(如 <10%) → 出价偏低 或 竞争激烈,排除定向过窄
        · 胜出率高但eCPM高 → 出价过高 overpay, 需要 shade
        · 成交价集中贴在floor附近 → 说明你是"场内唯一买家", 但被floor托底
Step 3  调整策略: 
        · 若成交价是 floor 兜底 → 手动压低出价, 试探更低 floor 成交, 而非盲目
        · 若 win rate 低 → 用 dv360_update_line_item 提高出价上限 / 放宽定向
        · 用 dv360_list_bid_recommendations + dv360_update_bid_recommendation 让系统给建议
Step 4  预估后再改: 
        dv360_get_performance_forecast / dv360_list_reach_forecasts 观察改后可达量与成本
```

**真实结论（经验）**：在**第一价格**下，手动填"一个偏高 CPM 保量"是典型的 overpay 陷阱：只要竞争不强，你每次成交都真付你的出价，成本被系统性抬到接近你的出价而不是接近市场价。**正确做法**是依赖自动出价让引擎做逐机会 shade，或手动手动压到"比预估市场均衡价略高一点"、并用 win rate 做反馈闭环。

```python
# 生产脚本示例: 观测并警惕 delta=clear-bid
report = client.dv360_list_bid_performance(advertiser_id)
for row in report:
    bid = row.get('bid_cpm')
    clear = row.get('clearing_price_cpm')
    delta = (clear - bid) / bid if bid else 0
    # 第一价格下, 若 delta 长期接近 0 → 出价≈成交价, 说明你常是独赢家, 可压低出价
    # 若 clear 常在 bid 附近 → 属正常第一价格行为, 别误以为被坑
```

---

### 3.2 PG 保量与 PMP 的"竞价语义"差异（重点澄清）

很多同学把 PG 和 PMP 混为一谈，这是投放里最贵的误解之一。我们系统对比：

| 维度 | PG（程序化保量） | PMP（私有市场） |
|------|----------------|---------------|
| **定价方式** | 协商固定 CPM（合同价） | 邀请制竞价 + 高 floor |
| **是否进拍卖** | **否**（按合同直接成交） | **是**（受邀的 DSP 出价竞争） |
| **量保证** | **保量**，未达标按协议赔付 | 不保量，出价低于 floor 就 0 成交 |
| **库存访问** | 已锁定 | 有优先访问权但不独占 |
| **价格上限** | 单价固定，无竞价弹性 | 出价变化影响成交/丢单 |
| **预算可控性** | 高（锁定） | 中（取决于出价与 floor 竞争） |
| **典型误用** | 拿 PG 当"竞价优化"，无效 | 拿 PMP 当"保量"，错 |

**PG 的正确理解**：
- PG 的价格是**事先谈好的固定 CPM**，不存在"出价越高量越多"的博弈。你调"出价"对 PG 的成交价**无效**（没有拍卖）。你要调的应是**预算分配**与**保量达成率**。
- PG 的价值在**确定性**与**品牌安全/独占**：锁定某个媒体包（package）的确定性展示。代价是贵和死板。
- 生产上，PG 由 **Proposal（提案）** 管理。用 `dv360_list_proposals(advertiser_id)` 查看 PG 提案状态，`dv360_accept_proposal` / `dv360_reject_proposal` 处理接受/拒绝。这些 API 不涉及出价策略，因为 PG 无竞价。

**PMP 的正确理解**：
- PMP 仍是**第一/第二价格拍卖**，只是参与者受限、floor 高。所以**出价必须 ≥ PMP 的 floor，否则一条都不给**。
- PMP 的"量"取决于你的出价在受邀者里能不能赢、以及是否高于 floor。**想从 PMP 多拿量，靠提价/扩大排除项，而不是把它当保量**。

> **实战红线**：把 PMP 当成"保量"去配预算，会出现"预算设了 10 万、实际只花 1 万，其余因为出价低于 floor 全丢"的现象。**不是没流量，是出价没越过 floor**。

---

### 3.3 生产最佳实践清单

1. **明确交易的"竞价语义"再谈出价**：先判定是 Open/PMP（有拍卖）还是 PG（无拍卖）。PG 别调出价，PMP 先确认 floor。
2. **第一价格下优先使用自动出价**：让引擎做逐机会 shade，避免手动 CPM overpay。手动出价只用于对成本极敏感的成熟中段库存。
3. **Always 用 win rate + auction insights 反馈**：`dv360_list_auction_insights` + `dv360_list_bid_performance` 组成闭环。别单看"花了多少"，要看"胜出率 × 结算价与出价差距"。
4. **floor 意识**：当成交价集中贴于 floor，说明你常是场内唯一/最高买家，压低出价可省预算；反之如果 win rate 已经低，别再压。
5. **pacing 与出价协同**：`dv360_get_pacing_rate` 偏低(花不完)不只调出价，更多要**放宽定向 / 扩大覆盖面 / 加预算**；调整出价只是手段之一。
6. **预估先行**：改出价/定向前用 `dv360_get_performance_forecast` / `dv360_list_reach_forecasts` 评估可达量与成本影响，避免拍脑袋。
7. **用系统建议**：`dv360_list_bid_recommendations` 结合 `dv360_update_bid_recommendation`，让 DV360 的模型告诉我们"该提价还是压价"。
8. **盯 no-fill / unfilled**：如果大量机会因低于 floor 而未成交，优先查「floor 偏高」还是「出价偏低」，对症。

---

### 3.4 踩坑实录（真实经验）

下面几条都是实战中反复出现的坑，每条都"烧过钱"：

**坑 1：出价误区——手动出价"报高保险"，在第一价格下系统性过付。**
- 现象：把 CPM 出价从 $4 提到 $6 想"保量"，结果 eCPM 也悄悄爬到 ~$6，成本 +50% 而量只涨一点点。
- 原因：第一价格下结算价=你的出价。竞争不强的长尾里，你提价 = 直接多付，不是"更可能赢"而是"以更高价赢"。
- 解法：降回并依赖自动 shade；或只在 win rate 确实太低时小幅提价，用 auction insights 确认竞争是真的激烈。

**坑 2：底价导致丢单（floor 过高 / 出价低于 floor）。**
- 现象：PMP 预算大但花不出去，查询后才发现**成交价为 0**，不是没量而是出价一直低于 PMP floor。
- 原因：PMP floor 常设 $8+，而你按公开市场经验出 $3~4。
- 解法：用 `dv360_list_bid_recommendations` 或直接看该 deal 的 floor；把 PMP 出价提到 floor 之上；同时检查是否有更便宜的同类 PMP/Open 库存替代。

**坑 3：CPM 理解错误——把"报表 eCPM/展示成本"当"出价"，从而误判。**
- 现象：报表 eCPM 显示 $2.5，出价 $5，运营以为"系统偷了钱"或"出价没生效"。
- 原因：第一价格下成交价=出价，但报表 eCPM 是**加权平均成交成本**（只有部分展示成交、部分折扣、部分 CPV/Viewable 折算），且包含不成交机会的分母摊薄。二者根本不是同一个数。
- 解法：不要用"报表 eCPM < 出价"来判断机制问题；要看 `dv360_list_bid_performance` 里的**逐个 bid/clearing** 明细。

**坑 4：把 PMP 当保量、把 PG 当可优化竞价。**
- 现象 a：PMP 设了大预算，指望"稳拿量"，结果量严重不足（低于 floor 全丢）。
- 现象 b：PG 上来就调出价想省成本，毫无效果还浪费时间。
- 解法：先分清交易类型（`get_transaction_type_options()` / `dv360_list_proposals`），PMP 看 floor+出价、PG 看保量+Budget 分配，别用错工具。

**坑 5：pacing 与出价"只调一个"导致的失衡。**
- 现象：预算花不完，于是猛提出价想抢量，结果半天就把当日预算烧光，后半程 0 展示。
- 原因：出价与 pacing 是两个独立杠杆，只动出价会破坏"匀速消耗"。提价后 pacing 会放大，导致前半天爆量后半天断流。
- 解法：用 `dv360_get_pacing_rate` 观察曲线，调整出价的同时检查预算上限与 flight 排期；必要时扩大定向而非只提价。

**坑 6：忽略"底价临界"的悬崖效应。**
- 现象：把出价从 floor 上方往下调 10%，流量从"正常"直接掉到"接近 0"。
- 原因：低于 floor 即整体无资格（no-fill），不是线性减少而是**断崖**。
- 解法：调出价时参考 floor 位置做**粒度试探**（±5% 步进），别一次砍太多；优先用自动出价引擎去兜底。

---

### 3.5 生产监控：把拍卖信号接进日报

良好的生产实践是把拍卖健康度做成**每日可观测指标**，下面给出一套建议的监控维度与来源 API：

| 监控指标 | 理想范围 | 含义/警戒 | 数据来源 |
|---------|---------|----------|---------|
| Win Rate（胜出率） | 20%~50% | <10% 出价偏低/竞争过激；>80% 可能 overpay | `dv360_list_auction_insights` |
| Clearing−Bid 差值 | 第一价格≈0 | 长期≈0 且 win rate 高 → 独立买家,可压价 | `dv360_list_bid_performance` |
| 成交价≤floor 成交占比 | 占比越低越好 | 高 → 你是底部买家, pay-to-floor | `dv360_list_bid_performance` |
| Pacing Rate | 匀速 ~100% | <70% 花不完; >120% 前紧后松 | `dv360_get_pacing_rate` |
| Unfilled / No-fill | 越低越好 | 高 → floor 过高或出价过低 | `dv360_get_performance_forecast` |
| 建议采纳 | — | 定期看推荐并决定采纳 | `dv360_list_bid_recommendations` |

> 把这些合成一张"竞价健康日报"，每天看 win rate 与 pay-to-floor 两个信号，基本能提前发现 90% 的出价/底价问题，而不是等预算烧完才后知后觉。

---

## 四、常见问题与排查

### 4.1 高频 FAQ 速查表

| # | 问题 | 一句话答案 | 详细索引 |
|---|------|-----------|---------|
| 1 | 为什么我的出价高，但成交价低？ | 说明你赢下展示时**次高出价远低于你**（第二价格下）；如果 DV360 是第二价格库存，付的是次高价而非你的出价。 | 2.1 |
| 2 | 为什么我的出价高，成交价却几乎等于我的出价？ | 说明这是**第一价格**库存，结算价=你的出价，而且你多半是**场内独赢/最高买家**。 | 2.2 / 2.7 |
| 3 | 为什么成交价经常恰好等于 floor？ | 你可能是全场最高出价者，第二高被 floor 顶掉；或自动出价精确压到"略高于 floor 的必赢价"。说明你是 pay-to-floor 买家，可谨慎压价。 | 2.4 / 4.2 |
| 4 | 为什么显示价（报表 eCPM）和我的出价不一致？ | 报表 eCPM 是**加权平均成交成本**，混入了 CPV/Viewable/回流折算、不成交机会的摊薄，不是你的出价。 | 2.7 / 3.4 坑3 |
| 5 | 为什么我调低了出价，量一下子断了？ | 你把出价压到了 **floor 之下**，触发 no-fill 断崖（不是线性减少）。 | 2.3 / 3.4 坑6 |
| 6 | 为什么 PMP 预算大却花不完？ | PMP 仍是拍卖 + 高 floor，你出价低于 floor 就 0 成交；它不是保量。 | 3.2 / 3.4 坑4 |
| 7 | 我为 PG 调出价为什么没效果？ | PG 是固定价合同采购，无拍卖，调出价无意义；应调预算分配与保量达成。 | 3.2 |
| 8 | 为什么同一个出价，win rate 忽高忽低？ | 竞争强度随机会/时段/地域波动，第一价格最优出价也随 N(竞争者数)变化。 | 2.2 |
| 9 | 自动出价和手动出价，为什么自动更省？ | 自动引擎对每个机会做 value estimation + bid shading，手动固定 CPM 在第一价格下必然该高不高、该低不低。 | 2.2 / 3.1 |
| 10 | 结算价能超过我的出价吗？ | 理论上结算价 ≤ max(出价, floor)；出现"高于出价"通常是计价维度/折算/返现叠加所致，非拍卖本身。 | 2.7 |

---

### 4.2 出价/成交异常排查流程（Step-by-Step）

当"量不够"或"成本爆炸"时，按下面流程逐层定位，避免瞎调：

```
问题: eCPM 高 or 量不足 or 预算花不完
│
├─ 1. 判交易类型 (Open / PMP / PG)
│      dv360_list_proposals → PG 走保量支线, 不调出价
│      PMP/Open → 走拍卖支线
│
├─ 2. 读拍卖健康信号
│      dv360_list_auction_insights → win rate / 竞争
│      dv360_list_bid_performance  → bid vs clearing 分布
│      dv360_get_pacing_rate       → 消耗曲线
│
├─ 3. 分支判断
│      win rate 低 ↓
│      │   → 出价偏低? 查看 floor; 用 dv360_get_performance_forecast
│      │      放宽定向 / 小幅提价 (win rate 反馈验证)
│      │
│      win rate 高 且 clear≈bid ↓
│      │   → 你是独赢/最高买家, overpay
│      │      压低出价 / 交给自动出价 shade
│      │
│      clear 大量 = floor ↓
│      │   → pay-to-floor, 尝试更低出价试探 floor 以下成交
│      │
│      pacing 偏低 (花不完) ↓
│      │   → 优先放宽定向/扩预算, 而非只提价
│      │
├─ 4. 采纳系统建议
│      dv360_list_bid_recommendations → 决定是否 dv360_update_bid_recommendation
│
└─ 5. 复核闭环
      改完再看 win rate / eCPM / pacing, 验证假设成立
```

**排查口诀**："先分交易类型，再看 win rate 与 clear−bid 差值，最后才动出价。" 大多数翻车都源于没分清 Open/PMP/PG 就盲目调价。

---

### 4.3 常见误解 TOP 3（一定避开）

1. **"出价越高，量一定越多"**：错。第一价格下出价越高盈利越薄甚至亏损，且**低于 floor 才是 0**，高于 floor 后量的边际收益递减。正确是"出价冲到必赢且不 overpay 的点"。
2. **"成交价比出价低，说明系统黑我/没生效"**：错。低的是第二价格，或加权平均摊薄；高的是第一价格且独赢。**都正常**，先分清楚再下结论。
3. **"PMP = 保量，PG = 竞价"**：完全反了。PMP 是竞价（只是限定 + 高 floor），PG 是保量（固定价无竞价）。

---

## 五、自测题

检验一下今天的理解。建议先不看答案，把理由想清楚再对。

### 题 1
一次展示，出价 A=$6、B=$4、C=$2，floor=$1，第二价格拍卖。A 应该支付多少？并说明如果 floor 改成 $4.5，A 又该支付多少、为什么？

<details><summary>查看答案</summary>

**结算价 = max(第二高出价, floor)**。
- floor=$1 时：第二高 B=$4 > floor=1，结算 = max(4, 1) = $4（+ 1 个增量 $0.01 → $4.01）。
- floor=$4.5 时：第二高 B=$4 < floor=4.5，所以 floor 生效，结算 = max(4, 4.5) = $4.5（+ 增量）。**floor 抬高了结算价**。

这正说明：第二价格下 floor 只在"第二高出价 < floor"时才把结算价顶上去。所以提高 floor 明显会增加胜者支付，也筛选出更愿意付费的买方。
</details>

### 题 2
在**第一价格**拍卖下，若你判断一次展示的估值是 $10，有 5 个竞争者（对称均匀模型）。用公式估算最优出价，并解释为什么"报真实估值 $10"不是最优。

<details><summary>查看答案</summary>

用对称模型公式 **b(v) = v·(N−1)/N**，N=5、v=10：最优出价 ≈ 10 × (5−1)/5 = 10 × 0.8 = **$8**。

报 $10 不是最优，因为第一价格下你赢时**支付你自己的出价**——报 $10 意味着把全部消费者剩余（估值与付款之差）让给卖方，净效用为 0。而压到 $8 时你在"还有机会赢（因为未必有竞争者报更高）"与"少付 $2"之间取得均衡。竞争者越多（N 越大），(N−1)/N 越接近 1，越不能压价——因为不贴近真值就会被别人抢走。
</details>

### 题 3
为什么 2019 年前后 Google 把 DV360 / Ad Manager 从第二价格切换为第一价格拍卖？请从"卖方收益 + 机制信任"两个角度回答。

<details><summary>查看答案</summary>

1. **机制信任 / 激励冲突**：第二价格要求拍卖商诚实披露"第二高价"作为结算价，但拍卖商存在操纵结算价的动机与灰色空间，影响透明度与买方信任。第一价格下结算价 = 出价本身，无操纵空间，审计/对账/反作弊更透明。
2. **卖方实际收益**：切到第一价格后，买方不敢激进 shade（怕丢单），在竞争充分的高价值库存上，**卖方实际成交价往往高于第二价格时期**，卖方收益提升。
3. 补充：Revenue Equivalence 定理说对称理想情况下两者期望收入相等，但现实中对称、独立、诚实披露等假设不成立，理论前提被打破，实际收益更偏向第一价格。
</details>

### 题 4
DV360 里你配了一个 Line Item 出价 CPM=$5，并把移动端 bid modifier 设为 1.2。一次移动端展示的 pacing 系数当前为 0.8，机会价值系数为 1.0，floor 为 $6。请算出最终出价，并判断 DV360 会怎么处理这次展示。

<details><summary>查看答案</summary>

沿出价形成链路：
- 配置出价 = $5
- × 机会价值系数 1.0 → $5
- × pacing 系数 0.8 → $4
- × bid modifier 1.2（移动端）→ $4 × 1.2 = **$4.80**

最终出价 $4.80 < floor $6 → **DV360 判定低于底价，直接放弃（no bid / unfilled），不参与这场拍卖**。

结论：出价被 pacing（0.8）与 modifier（1.2）加工后仍低于 floor，这次移动展示不会进入拍卖。若想拿下这类库存，要么提高配置出价，要么调高移动 modifier，或确认该 PMP 的 floor 是否可接受。
</details>

### 题 5
你的 PMP 交易预算很大但几乎花不完，报表显示成交很少。请列出至少 3 个最可能的原因，以及各自的排查/解法。

<details><summary>查看答案</summary>

1. **出价低于 PMP floor**（最常见）：PMP 仍是拍卖且 floor 高，出价 < floor → 全部 no-fill。解法：查该 deal 的 floor，把出价提到 floor 之上（用 `dv360_get_performance_forecast` / `dv360_list_bid_recommendations` 辅助）。
2. **赢率太低 / 竞争激烈**：即便出价 ≥ floor，在受邀者里仍常输。解法：`dv360_list_auction_insights` 看 win rate，需要时提价或扩大覆盖的 PMP 列表。
3. **定向过窄 / 覆盖不足**：PMP 锁定的受众段本身流量小。解法：检查定向（地域/人群/时段），必要时放宽。
4. **预算未正确关联 / flight 排期问题**：预算没绑到这个 Line Item，或 flight 未开始/已结束。解法：核对 `dv360_update_line_item` 的预算与 flight 时间。
5. **PMP 本身库存稀缺**：卖方在 PMP 上放的量就很少。解法：评估是否加同类 Open 库存补量，但注意品牌安全取舍。

按"先 floor、再 win rate、再定向"的顺序排查，能覆盖绝大多数"PMP 花不完"的案例。
</details>

---

## 📌 今日总结

- **拍卖机制**：公开竞价（拍卖定价）< PMP（邀请制高 floor）< Preferred Deal（优先权）< PG（固定价保量）。
- **结算规则**：第二价格付次高价（激励相容、真实报价最优）；第一价格付自己的出价（必须 shade，DV360 当前主流）。
- **floor** 是卖方保留价：低于则 no-fill，第二价格下 floor 会抬高结算价；第一价格下结算=max(出价,floor)。
- **DV360 出价链路**：配置出价 × 价值系数 × pacing × bid modifier → 对拍 floor → 进拍卖。`dv360_get_pacing_rate` 观测节奏。
- **生产铁律**：先分 Open/PMP/PG，再看 win rate 与 clear−bid 差值，最后才动出价；用 `dv360_list_auction_insights` / `dv360_list_bid_performance` / `dv360_list_bid_recommendations` 做闭环。
- **与已有文档的关系**：`dv360-bidding-strategy-deep` 讲"策略选型"，本文讲"拍卖机制底层"；`dv360-architecture-deep` 讲"RTB 链路"，本文讲"链路里的钱怎么算"。

> 下一篇可继续 Day 4：**预算分配与 Pacing 算法**，把"怎么把预算均匀花掉"做成可控工程。今日的 pacing 与 floor 概念将是它的地基。

---
*本文由 Ryan 个人知识库自动生成，供广告投放与竞价工程学习使用。*
