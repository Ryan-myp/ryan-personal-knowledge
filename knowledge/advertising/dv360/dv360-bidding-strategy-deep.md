# DV360 竞价策略深度解析（Bid Surge / Auto-bidding / Target CPA / Target ROAS / 程序化保量）

> **领域**: 广告投放 / 竞价策略
> **深度**: ⭐⭐⭐⭐⭐ 实战级指南
> **标签**: dv360, bidding, auto-bidding, target-cpa, target-roas, bid-surge, programmatic-guaranteed
> **更新时间**: 2026-08-14
> **类型**: 深度文档

---

## 一、核心概念与架构

### 1.1 引言：为什么竞价策略是 DV360 投放成败的分水岭

在程序化广告投放中，**定向（Targeting）决定了你看到谁，而竞价（Bidding）决定了你用多少钱去赢得一次展示**。大多数投放团队把 80% 的时间花在定向、创意、素材上，却把出价当作"填一个数字"的例行公事。这是最常见的错误认知。

在 DV360（Display & Video 360）中，出价策略（Bidding Strategy）位于投放链路的核心位置：它一端连接广告主的业务目标（KPI），另一端连接实时竞价拍卖（RTB Auction）。出价策略的错误选择，会在整个投放生命周期中被无限放大：

- 出价太高 → 预算过早耗尽（pacing over-delivery）、CPA 飙升、ROAS 崩塌；
- 出价太低 → 拿不到量、竞争力不足、交付率（delivery rate）不达标；
- 出价波动过大 → 学习期（learning period）反复重新开始，模型始终无法收敛；
- 出价策略与应用场景错配 → 品牌保量单用了效果出价，效果单用了手动出价，双双失败。

本份文档将系统性地拆解 DV360 的竞价策略体系，覆盖：手动出价与自动出价的取舍、自动出价能力矩阵（Maximize Conversions / Target CPA / Target ROAS / Viewable CPM / Bid Surge）、拍卖机制（第一价格与第二价格）、Auto-bidding 的内部机器学习原理、oCPM 公式推导、程序化保量（PG）的固定价格与保量算法、以及 Go 实现的竞价优化引擎与 pacing 算法。所有内容均结合真实 API 方法名（`dv360_list_bidding_strategies`、`dv360_get_pacing_rate`、`dv360_create_line_item`、`dv360_update_line_item_budget` 等）和真实投放踩坑经验。

### 1.2 DV360 出价策略全景

DV360 的出价策略从宏观上可以划分为两个大类：**手动出价（Manual Bidding）** 与 **自动出价（Automated Bidding）**。它们并非相互替代的关系，而是针对不同业务目标、不同数据成熟度的互补工具。

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                          DV360 出价策略全景                                   │
│                                                                              │
│  ┌────────────────────────────┐        ┌──────────────────────────────┐      │
│  │  手动出价 (Manual)          │        │  自动出价 (Automated)          │      │
│  │                            │        │                              │      │
│  │  • Fixed CPM (sCPM)        │        │  • Maximize Conversions      │      │
│  │  • Fixed CPC               │        │  • Maximize Clicks           │      │
│  │  • Fixed CPV               │        │  • Target CPA / tCPA        │      │
│  │  • Viewable CPM (手动档)    │        │  • Target ROAS / tROAS      │      │
│  │  • Bid Surge (手动出价的    │        │  • Optimized CPM (oCPM)     │      │
│  │    增强剂，作用于已有出价)    │        │  • Viewable CPM (自动优化档)  │      │
│  │                            │        │  • Bid Surge (自动出价叠加)   │      │
│  └────────────┬───────────────┘        └─────────────┬────────────────┘      │
│               │                                      │                       │
│   控制力强/可预测                       数据驱动/自动优化                     │
│   需高频手动调优                         需历史数据 + 学习期                   │
│                  └──────────┬───────────┘                                    │
│                             ▼                                                │
│              ┌─────────────────────────────────────┐                        │
│              │     实时竞价拍卖 (RTB Auction)        │                        │
│              │  first-price / second-price 机制     │                        │
│              └─────────────────────────────────────┘                        │
└──────────────────────────────────────────────────────────────────────────────┘
```

#### 1.2.1 手动出价（Manual Bidding）

**Fixed CPM（固定千次展示出价，也常被称为 Standard CPM / sCPM）**：广告主为每次千次展示机会设定一个固定的出价金额。DV360 会在该固定出价基础上参与每一次拍卖。这是最传统、最直观的出价方式。

- **适用场景**：程序化保量交易（PG）以外的常规 RTB 投放；对单次展示价值有清晰认知的成熟投放；需要严格预算与成本控制的场景。
- **优点**：完全可控、可预测、易解释；不依赖历史转化数据；对刚上线的 Campaign 友好。
- **缺点**：无法区分高价值与低价值的单次展示；需要人工频繁根据表现调价；在竞争激烈的流量上容易"要么拿不到量要么成本虚高"。

**Fixed CPC（固定每次点击出价）**：广告主为每次点击设定固定出价，DV360 在内部将其按预估点击率转换成等效 CPM 去参与拍卖。适用于以点击为 KPI 的线索收集型投放。

**Fixed CPV（固定每次观看出价）**：只适用于视频广告，广告主为每次视频观看（通常定义为播放 2 秒或到达一定可见比例）设定出价。适用于品牌视频投放、以观看量为目标的 Campaign。

**手动出价的共同本质**：出价金额是一个**常量或由广告主决定的外生变量**，DV360 不（或只做极轻微）根据单次展示的价值预估动态调整。这是它与自动出价最根本的区别。

#### 1.2.2 自动出价（Automated Bidding）

自动出价下，广告主只需要设定**业务目标**（例如"最大化转化量"或"目标 CPA = 50 元"），DV360 的机器学习引擎会在每一次拍卖前动态计算一个**最优出价**，以在给定预算约束和流量条件下，最大化业务目标的达成率。

这样做的核心逻辑是：**不同的展示机会价值不同**。同样一个 banner，展示给"已经把商品加入购物车但未下单的用户"和展示给"只看过首页的新用户"，其预期转化价值可能相差 10 倍以上。手动出价无法区分它们，而自动出价可以。

```
┌────────────────────────────────────────────────────────────────┐
│              手动出价 vs 自动出价 决策链路对比                   │
│                                                                │
│  手动出价:                                                     │
│  广告主设定固定出价 $8 CPM ──► 每次机会都用 $8 ──► 赢得优质机会    │
│       └─────────────── 无法区分机会价值 ───────────────┘         │
│                                                                │
│  自动出价:                                                     │
│  广告主设定目标 CPA $50 ──► 模型预测 pCVR ──► 动态出价            │
│       ┌─ 高价值机会 (pCVR=3%)  → 出价 $X 高                       │
│       ├─ 中价值机会 (pCVR=1%)  → 出价 $Y 中                       │
│       └─ 低价值机会 (pCVR=0.1%)→ 出价 $Z 低/不出价                │
│                                                                │
│  → 同样的平均出价下，自动出价把预算花在更有价值的展示上            │
└────────────────────────────────────────────────────────────────┘
```

### 1.3 自动出价能力矩阵

DV360 的自动出价覆盖了从"宽度/量"到"深度/质"的完整目标光谱。下表是自动出价能力矩阵：

| 出价策略 | 优化目标 | 广告主需要设置 | 数据需求 | 适用 KPI | 典型场景 |
|---------|---------|--------------|---------|---------|---------|
| **Maximize Conversions** | 在预算内最大化转化量 | 预算 | 高（需转化回传） | 转化量 | 预算固定、想要最多转化的效果投放 |
| **Maximize Clicks** | 在预算内最大化点击量 | 预算 | 中 | 点击量/流量 | 电商流量获取、内容分发 |
| **Target CPA (tCPA)** | 在目标 CPA 内最大化转化量 | 目标 CPA + 预算 | 高（需历史转化数据） | CPA | 效果投放、线索收集 |
| **Target ROAS (tROAS)** | 在目标 ROAS 下最大化收入 | 目标 ROAS + 预算 | 高（需价值回传） | ROAS/收入 | 电商、应用内购 |
| **Viewable CPM** | 在目标可见 CPM 内最大化可见展示 | 目标 vCPM | 中 | 可见性/品牌曝光 | 品牌展示投放 |
| **Optimized CPM (oCPM)** | 在目标 CPA 内最大化转化 | 目标 CPA | 高 | CPA | 无清晰 ROAS 但想自动优化的效果投放 |
| **Bid Surge** | 在高峰期临时抬高竞争力的叠加增强 | 百分比（+50%~+200%） | 中 | 拿量/品牌冲刺 | 大促、新品、事件报道窗口 |

> 注意：**Bid Surge 不是独立的出价策略**，而是作用在既有出价之上的"增强器（booster）"。它既可以在手动出价上叠加，也可以作为自动出价的修正。1.5 节与第二章会深入展开。

### 1.4 拍卖机制：第一价格 vs 第二价格

理解 DV360 的出价策略之前，必须先理解它运行的拍卖环境。DV360 与众多供应方（SSP / Ad Exchange / 供应方交易）连接，而不同交易所采用的清算（clearing）机制不同。

**第二价格拍卖（Second-Price Auction）**：赢家按**第二高出价**（而非自己的出价）支付。这是历史上的主流通用拍卖机制。在第二价格下，广告主的最优策略是"真实报价"——报出你对一次展示的真实估值，因为你不必担心多付，出价只决定"能否赢"，不决定"花多少"。

**第一价格拍卖（First-Price Auction）**：赢家按**自己的出价**支付。随着 Opengate、双边 auction 的普及，以及 Google 对 Open Bidding 的推动，第一价格正成为主流。在第一价格下，广告主有"出高价但少付"的博弈冲动，会策略性压价（bid shading）。

```
┌──────────────────────────────────────────────────────────────────────┐
│  第二价格拍卖 (Second-Price)         第一价格拍卖 (First-Price)          │
│                                                                        │
│  你出价 $10                          你出价 $10                          │
│  对手最高出价 $8                      对手最高出价 $8                      │
│  ─────────────────────               ─────────────────────             │
│  你赢，支付 $8（第二高）              你赢，支付 $10（你的出价）            │
│  最优策略: 报真实估值                 最优策略: 真实估值 − 博弈余地         │
│  多出价不会多花钱                     多出价 = 多花钱                      │
└──────────────────────────────────────────────────────────────────────┘
```

**对出价策略的影响**：

1. **自动出价在第二价格下更从容**：机器学习只需估计"这个展示值多少"，出价就是估值本身。
2. **自动出价在第一价格下需要处理 bid shading**：DV360 的引擎会学习"在该机会上需要出到多少才能赢且不过付"，从而把出价压低到接近"必要获胜价"。
3. **手动出价在第一价格下极易过付**：一个"高一点的固定出价"在第一价格下意味着"每次成交都多付"，成本会被系统性推高。这也是为什么 DV360 强烈推荐在第一价格库存上使用自动出价。
4. **对 Bid Surge 的双刃剑效应**：Bid Surge 本质是"无脑抬高出价"，在第一价格环境下会直接放大成本，必须与 bid floor 意识和预算控制配合。

### 1.5 优化目标层级：从 Partner 到单次展示

DV360 的竞价优化不是孤立的，它位于一个完整的层级结构中。理解这个层级，才知道出价策略该配置在哪一层、如何被上层传递下来。

```
┌─────────────────────────────────────────────────────────────┐
│              DV360 账户与优化目标层级                          │
│                                                              │
│  Partner (合作伙伴/代理)                                      │
│   └── Advertiser (广告主)                                     │
│        ├── 预算分配 (Budget Allocation)                       │
│        │    └── 总额度在多个 IO 间分配                         │
│        └── Insertion Order (IO / 广告系列)                    │
│             ├── 目标: CPA / ROAS / 预算上限 / 排期             │
│             └── Line Item (媒体购买/线条项目)                  │
│                  ├── 出价策略 (Bidding Strategy) ← 核心         │
│                  ├── 定向 (Targeting)                         │
│                  ├── 预算 (Budget) + 流速 (Pacing)            │
│                  └── 创意 (Creative)                          │
│                       └── 单次拍卖机会 (Impression Opportunity)│
│                            └── 动态出价 (Dynamic Bid)          │
└─────────────────────────────────────────────────────────────┘
```

**关键点**：

- **出价策略是 Line Item 级的属性**，不是 Advertiser 或 IO 级的。同一 IO 下的不同 Line Item 可以使用不同出价策略。
- **预算 pacing 是独立于出价策略的第二个优化维度**。pacing 管"今天花多少"，出价管"每次机会出多少"。两者必须协同：若 pacing 收紧而出价过高，会导致预算过早耗尽；若 pacing 放松而出价过低，则花不完预算。
- **上层目标向下传递**：IO 的安全预算、频率上限（frequency cap）、排期会约束 Line Item 的出价自由度。自动出价引擎需要在满足上层约束的前提下做最优化。

### 1.6 关键 API 方法速查

在我们进入原理之前，先列出本分档会反复引用的真实 DV360 API 方法（来自 `scripts/ad_platform_api.py` 与 `scripts/dv360_api.py`）：

| API 方法 | 作用 | 在本文档中的切入章节 |
|---------|------|--------------------|
| `dv360_list_bidding_strategies(advertiser_id)` | 列出某广告主下所有出价策略 | 1.2 / 3.1 |
| `dv360_get_pacing_rate(advertiser_id, line_item_id)` | 获取指定 Line Item 的投放流速/pacing 率 | 2.8 / 4.3 |
| `dv360_create_line_item(advertiser_id, name, **kwargs)` | 创建媒体购买 Line Item（可带出价策略） | 3.1 / 3.4 |
| `dv360_update_line_item(advertiser_id, line_item_id, **kwargs)` | 更新 Line Item（切换出价策略） | 3.1 / 3.5 |
| `dv360_update_line_item_budget(line_item_id, budget_micros)` | 更新 Line Item 预算 | 3.2 / 3.5 |
| `dv360_list_budget_allocations(advertiser_id)` | 列出预算分配 | 1.5 / 3.2 |
| `dv360_get_line_item_performance(line_item_id, date_range)` | 获取 Line Item 表现数据 | 3.3 / 4.x |
| `dv360_list_recommendations(advertiser_id)` | 列出 DV360 的优化建议 | 3.6 |
| `dv360_apply_recommendation(recommendation_id)` | 应用某条优化建议 | 3.6 |
| `dv360_get_bid_strategy_options()` → `get_bid_strategy_options()` | 返回官方出价策略选项（CPM/CPC/CPV/oCPM/CPA） | 1.2 / 2.4 |

其中，`get_bid_strategy_options()` 的实现返回如下（出自 `scripts/dv360_api.py`）：

```python
def get_bid_strategy_options(self) -> List[Dict]:
    """获取官方出价策略选项"""
    return [
        {'code': 'CPM', 'name': 'CPM', 'description': '按千次展示计费'},
        {'code': 'CPC', 'name': 'CPC', 'description': '按点击计费'},
        {'code': 'CPV', 'name': 'CPV', 'description': '按视频观看计费'},
        {'code': 'OCPM', 'name': 'OCPM', 'description': '优化千次展示'},
        {'code': 'CPA', 'name': 'CPA', 'description': '按转化计费'}
    ]
```

> 注意：上表中的 `OCPM`/`CPA` 是"计费/定价模式"层面的官方选项；在 DV360 出价策略层面，`oCPM`/`Target CPA` 等以"优化目标"的形式存在。二者关系在 2.4 节 oCPM 公式中澄清。

### 1.7 本章小结

- 出价策略 = 连接"业务 KPI"与"RTB 拍卖"的枢纽。
- 手动出价（CPM/CPC/CPV）可控但僵化；自动出价（Maximize / Target CPA / Target ROAS / Viewable CPM / oCPM）数据驱动但依赖历史数据与学习期。
- **Bid Surge 是叠加在既有出价上的增强器，而非独立策略**。
- 拍卖机制（第一/第二价格）深刻影响出价策略的效果，第一价格下自动出价通常优于手动出价。
- 出价策略是 Line Item 级属性，需与预算 pacing、上层目标协同。

---

## 二、深度原理解析

### 2.1 Bid Surge 原理与触发条件

#### 2.1.1 什么是 Bid Surge

Bid Surge（出价激增/出价飙升）是 DV360 提供的一种**临时性出价增强工具**，允许广告主在特定时间窗口内，将 Line Item 的出价**成比例地提高**，从而在短期内获得更强的竞价竞争力。它不是一种独立的出价策略，而是叠加在既有出价（手动或自动）之上的修正因子。

```
┌────────────────────────────────────────────────────────────────────┐
│                    Bid Surge 作用原理                               │
│                                                                    │
│  正常窗口:  出价 = 基准出价 (base bid)                               │
│              └── 例如手动 CPM $8 / 或自动出价引擎给出的动态值         │
│                                                                    │
│  Surge 窗口: 出价 = 基准出价 × (1 + surge_pct)                      │
│              └── 例如 surge_pct = 100% → 出价翻倍为 $16             │
│                                                                    │
│  时间轴:                                                           │
│   ├── 00:00 ───────── 目标日期前 ─────── Surge 窗口 ──→ 恢复         │
│   │                                           │                    │
│   │                             出价 × (1 + surge_pct)             │
│   └───────────────────────────────────────────┴────────────────────┘
└────────────────────────────────────────────────────────────────────┘
```

**Bid Surge 的关键参数**：

| 参数 | 说明 | 典型取值 |
|-----|------|---------|
| **Surge 百分比** | 在基准出价上提高的百分比 | +50%、+100%、+200% |
| **Surge 窗口** | 生效的时间窗（日期/小时） | 促销当日、大促前 3 天 |
| **目标** | Surge 的对象（通常绑定到某个 Line Item） | 品牌冲刺 Line Item |

#### 2.1.2 Bid Surge 的触发条件

DV360 官方对 Bid Surge 的使用给出明确约束，常见的"适合触发"与"不适合触发"条件如下：

**适合使用的条件**：
1. **品牌可见度冲刺期**：新品上市、双十一/黑五大促、超级碗、春节等事件窗口，需要短时间内提升可见度时。
2. **竞争异常加剧**：监测到某段时间竞争对手投放强度显著上升，导致 win rate 下降时。
3. **目标库存稀缺**：在某优质流量（如特定首页、特定时段视频前贴片）上，用正常出价难以中标时。
4. **重新进入流量池**：当 Line Item 因出价过低长期"饿死"、需要快速重建权重时。

**不适合使用的条件**：
1. **效果投放且 CPA 敏感**：Surge 会无差别抬高出价，效果投放的 CPA 会立刻恶化。
2. **预算本来就紧绷**：Surge 会加快预算消耗（pacing over-delivery），如果预算是硬约束，会过早烧完。
3. **无明确时间窗口需求**：如果只是"长期拿不到量"，应该调整基准出价或换自动出价，而不是用 Surge。
4. **覆盖可预测的自然波动**：Surge 是"临时应急"，不应作为日常手段。

#### 2.1.3 Bid Surge 的使用场景

**场景 A：大促日品牌冲刺**
某美妆品牌在 618 当天想确保自己的品牌广告在核心 App 的开屏位上保持高曝光。平时手动 CPM 出价 $10，在 618 当天 0 点-24 点设置 Bid Surge +100%，使该窗口出价达 $20，确保在竞品涌入时仍能拿到足量且竞争激烈的库存。

**场景 B：新品发布会窗口**
某手机厂商在新品发布会（例如 20:00-21:00）的 1 小时内想最大化视频前贴片的可见度，设置 Surge +150% 集中在发布会前后 2 小时。

**场景 C：优质库存稀缺时**
某金融 App 发现目标投放位（某财经网站首页）后台 win rate 从 40% 跌到 15%，通过 DV360 报表确认竞品加价，临时设置 Surge +80% 直至该位置竞争回落。

#### 2.1.4 Bid Surge 的风险与代价

Bid Surge 是一把双刃剑，使用不当会带来严重代价：

| 风险 | 表现 | 缓解措施 |
|-----|------|---------|
| **成本失控** | 第一价格拍卖下加倍出价=加倍花费 | 只用于非效果/品牌目标；设预算上限 |
| **CPA 恶化** | 效果单 Surge 后 CPA 飙升 | 效果投放禁用 Surge |
| **过度交付** | Surge 窗口预算提前烧光，后半段无投放 | 合理排期 Surge 窗口，留出缓冲 |
| **数据污染** | Surge 期间的出价数据扰动模型学习 | 学习期内不叠加 Surge；切换后留观察期 |
| **频率超限** | 高竞争力下同用户被多次触达，体验差 | 配合 frequency cap 使用 |

**踩坑实录**：
> 某电商在双十一当天对同一个 ROI 效果 Line Item 叠加 +200% Bid Surge，结果当天预算在下午 3 点就耗尽，晚上 8 点-12 点黄金时段无流量可投，且由于 Surge 期间把高价值流量以过高价格买下，当天实际 CPA 比平时高出 2.8 倍。**教训：Surge 必须与效果目标隔离，且要为黄金时段预留预算缓冲。**

### 2.2 Auto-bidding 的内部机制：预测 → 出价 → pacing

Auto-bidding（自动出价）的核心是一条**"预测 → 出价 → pacing"**的闭环流水线。理解了这条流水线，就理解了自动出价为什么"智能"以及它的局限在哪。

```
        ┌──────────────────────────────────────────────────────────┐
        │                    Auto-bidding 闭环                       │
        │                                                          │
        │   每次拍卖机会                                          │
        │      │                                                   │
        │      ▼                                                   │
        │  ┌───────────┐    ┌───────────┐    ┌───────────┐        │
        │  │ 预测阶段    │───▶│ 出价阶段   │───▶│ pacing阶段 │        │
        │  │ pCVR/pCTR  │    │ bid = f() │    │ 预算/流速  │        │
        │  └───────────┘    └───────────┘    └───────────┘        │
        │        ▲                                │                │
        │        │           反馈/学习              │                │
        │        └────────────────────────────────▼                │
        │             模型更新 / 校准 / 目标调整                      │
        └──────────────────────────────────────────────────────────┘
```

#### 2.2.1 预测阶段（Prediction）：pCVR 与 pCTR

自动出价的第一步是预测单次展示的价值。DV360 的机器学习模型会对每次拍卖机会产生两个核心概率估计：

- **pCTR（Predicted Click-Through Rate，预测点击率）**：该展示被点击的概率。
- **pCVR（Predicted Conversion Rate，预测转化率）**：该展示点击后被转化的概率。

这些预测基于海量特征：用户画像、设备、地域、上下文页面、时段、天气、历史行为（是否访问过网站、是否加购）、广告位质量、创意与用户的相关性等。DV360 背后是类似"广告相关性评分 + 转化概率模型"的大规模 ML 系统，在实时拍卖的亚秒级延迟内完成推断。

```
单次展示价值估算（效果导向，转化价值 = conversion_value）:
  expected_value = pCVR × conversion_value          # 转化期望价值
  expected_ctr_click = pCTR                          # 点击期望

在产品/内容广告中，价值主要来自转化 (电商/App)：
  value = pCVR × conversion_value

在流量/线索导向中，价值同时来自点击与转化：
  value = pCTR × (点击价值) + pCVR × conversion_value
```

示例：
- 目标 CPA = $50，某机会 pCVR = 2%（0.02）
- 期望转化价值 = 0.02 × $50 = $1 / 次展示（按千次=$1000 CPM 的隐含价值）
- 若 pCVR = 0.2%（0.002），则期望价值 = 0.002×$50 = $0.1，出价应显著下降。

#### 2.2.2 出价阶段（Bidding）：目标驱动的报价

预测出价值后，出价引擎根据所选策略把"目标"与"预测价值"映射为具体出价：

```
Target CPA (tCPA):
  bid_CPM = (target_CPA × pCVR) × 1000

Target ROAS (tROAS):
  # tROAS = revenue / cost，例如 400% 表示每花 $1 赚 $4
  # 期望收益 = pCVR × revenue_value
  allowed_cost_per_impression = expected_revenue / tROAS
  bid_CPM = allowed_cost_per_impression × 1000

Maximize Conversions:
  # 无固定目标，在预算约束下尽量多赢取高价值机会
  bid 由"预算还剩多少 + 剩余时间 + 可用机会的价值分布"共同决定

Viewable CPM:
  优化可见展示，出价与可见性概率 (pViewable) 挂钩
```

#### 2.2.3 pacing 阶段（预算流速控制）

pacing（投放节奏）解决"在预算约束下，把这个 Line Item 的预算在排期内平滑花出去，而不是过早或过晚耗尽"的问题。它是独立于单次出价的第二个控制器。

```
pacing 的本质问题:
  目标: 在 [start, end] 排期内花完 budget，尽量平滑，不早花完不晚花完
  约束: 每天有最大可花额 / 每天的目标花费曲线

常见 pacing 策略:
  1. 匀速 pacing (even pacing): 每天花 budget / 天数，均匀分布
  2. 前载 pacing (front-loaded): 前期多花，用于抢量/冲刺
  3. 后置 pacing (back-loaded): 前期少花，观察后集中投放
  4. 动态 pacing: 根据实时交付进度动态调整当天可花额
```

DV360 提供了 `dv360_get_pacing_rate` 来读取 Line Item 的当前 pacing 状态：

```python
def dv360_get_pacing_rate(self, advertiser_id: str, line_item_id: str, **kwargs) -> Dict:
    """获取投放速率"""
    service = self.get_client('dv360')
    pacing = service.users().me().lineItems().pacing().get(
        advertiserId=advertiser_id,
        lineItemId=line_item_id
    ).execute()
    return pacing
```

返回的 pacing 信息通常包含：
- **pacing_mode**：`PACING_MODE_ASAP`（尽快花完）、`PACING_MODE_EVEN`（匀速）等
- **pacingStatus**：`PACED`、`UNDELIVERED`、`OVERDELIVERED` 等
- **pacingRateType**、**currentRate** 等用于节奏计算的字段

#### 2.2.4 反馈与学习（Feedback & Learning）

每次拍卖的结果（是否中拍、成本多少、是否产生点击/转化/收入）都会回流到模型，用于：
- 校准预测（calibration）：如果 pCVR 系统性高估，模型会调整；
- 更新特征权重：哪些特征更能预测转化；
- 调整出价策略：在目标与实际表现之间做平衡。

**学习期（Learning Period）**：模型在数据不足时不置信，因此自动出价通常有学习期（一般 3-7 天，视转化频率而定）。学习期内模型探索性投放，表现可能不稳定，CPA 可能偏高。频繁调整目标会重置学习期。

### 2.3 Target CPA / Target ROAS 的数学与取舍

#### 2.3.1 Target CPA（目标每次转化费用）

**数学模型**：
设目标 CPA 为 `C*`，某展示机会的预测转化概率为 `pCVR`，展示总数为 1000，则该机会的期望转化数为 `1000 × pCVR`。为了让"期望花费 / 期望转化数 = C*"，出价应为：

```
Target CPA 出价公式:

  期望花费 = 出价(CPM) × (1000 展示)
  期望转化 = 1000 × pCVR
  目标:  期望花费 / 期望转化 = C*
  =>    出价(CPM) / (1000 × pCVR) 中最优设为目标 CPA 下的每转化成本
  =>    出价(CPM) = C* × pCVR × 1000
```

**示例**：
- 目标 CPA = $50
- 机会 A：pCVR = 2%（0.02）→ 出价 CPM = $50 × 0.02 × 1000 = **$1000**
- 机会 B：pCVR = 0.5%（0.005）→ 出价 CPM = $50 × 0.005 × 1000 = **$250**

**取舍（Trade-off）**：

| 目标 CPA 设定 | 行为 | 后果 |
|-------------|------|------|
| **过低**（远低于实际可达到） | 引擎几乎对所有机会都出低价 | 拿不到量，交付率低，长期饿死 |
| **合理**（贴近市场实际） | 引擎在高质量机会上出价高、低质量出价低 | 在目标附近达成 CPA，量质平衡 |
| **过高**（明显高于实际） | 引擎轻易获胜，成本虚高 | 达成率高但浪费预算，CPA 高于必要 |

**核心取舍**：Target CPA 是在**"成本上限"与"量"之间做权衡**。即使不设预算上限，过低的目标 CPA 也会自然限制可获得的转化量，因为值得出价的机会变少了。这也是"目标 CPA 其实充当了隐变量"——它同时决定了取舍 Witness 与花费水平。

#### 2.3.2 Target ROAS（目标广告支出回报率）

**数学模型**：
设目标 ROAS 为 `R*`（例如 4.0 表示每花 1 元赚 4 元），某机会的预测转化价值（收入）为 `expected_revenue = pCVR × conversion_value`，则允许花费的上限为：

```
Target ROAS 出价公式:

  目标:  ROAS = revenue / cost ≥ R*
  =>    cost ≤ revenue / R*
  每次展示允许花费 ≤ expected_revenue / R*
       = (pCVR × conversion_value) / R*

  出价(CPM) = allowed_cost_per_impression × 1000
            = (pCVR × conversion_value / R*) × 1000
```

**示例**：
- 目标 ROAS = 400%（R* = 4.0）
- 机会 A：pCVR = 2%，conversion_value = $200 → 期望收入 = $4 → 允许花费 = $1 → 出价 CPM = $1000
- 机会 B：pCVR = 1%，conversion_value = $50 → 期望收入 = $0.5 → 允许花费 = $0.125 → 出价 CPM = $125

**tROAS vs tCPA 的取舍对比**：

| 维度 | Target ROAS | Target CPA |
|------|------------|-----------|
| 价值单位 | 收入/转化价值（需回传 value） | 转化本身（每次转化等值） |
| 需要数据 | 转化 + 收入价值回传 | 只需转化回传 |
| 对高价值转化 | 自适应调高出价 | 一视同仁 |
| 适用 | 电商、有明确客单价 | 线索、无明确价值差异 |
| 风险 | 若价值回传不准确会系统性失真 | 无法区分高/低价值转化 |

**关键点**：tROAS 高度依赖**准确的转化价值回传**。如果转化价值（order value、LTV）没有被正确回传（例如动态价值缺失、货币单位错误），引擎会基于错误的价值信号出价，导致 ROAS 目标失真。这是 tROAS 落地中最常见的踩坑点。

#### 2.3.3 Maximize Conversions 的内部机制

当广告主选择 Maximize Conversions 时，引擎在**给定预算**下尽可能多地产生转化。此时出价公式不再是"目标驱动"，而是"预算驱动 + 价值排序"：

```
Maximize Conversions 逻辑:

  1. 对每个机会预测 pCVR
  2. 把机会按"价值密度"(pCVR / 竞争力成本) 排序
  3. 在预算约束下，优先出价最高价值密度的机会
  4. pacing 决定"今天能花多少、哪些机会值得抢"

  本质: 预算固定 → 拍卖机制自动竞拍到预算耗尽
  配套: 通常配合相对竞价上限 (bid ceiling) 防止单次出价失控
```

Maximize Conversions 不需要设定目标数值，但需要**明确的预算**。若预算过低，转化量自然受限；若预算过高，可能无法填满或成本上升。

### 2.4 oCPM 公式：bid = f(expected actions)

**oCPM（Optimized CPM，优化千次观看/优化千次展示）** 是 DV360 计费/定价模式与优化目标的结合点。它本质上是"按照 CPM 计费，但由系统自动优化每一次展示的出价以追求转化目标"。

**oCPM 出价公式（与 2.3.1 一致，只是从 oCPM 视角表述）**：

```
oCPM = (eCPA / pCVR) × 1000

其中:
  eCPA  = 广告主设定的目标每次转化费用 (expected CPA)
  pCVR  = 模型预测的转化概率 (predicted conversion rate)
  1000  = 每千次展示单位

直观含义:
  出价 = 目标的每转化成本 × 期望在这千次展示中获得的转化数
       = eCPA × (1000 × pCVR)
```

**数值示例**（与 dv360-dfp-deep.md 中 4.1 节呼应）：
- 目标 CPA = $20
- DV360 预测 pCVR = 2%（0.02）
- 出价 CPM = $20 / 0.02 × 1000 = **$1000 CPM**
- 若 pCVR 降到 1% → 出价 CPM = $2000（因为每次千次展示只能期望 10 次转化，要达到同 CPA 需更高... 注意此逻辑：pCVR 越低，为维持每转化成本需付的较低、但要赢得该低转化机会所需出价在第二价格逻辑下…详见下文风险）

这里需要澄清一个直觉陷阱：

> **pCVR 越高，出价越高（更容易在优质机会上出高价）；pCVR 越低，出价越低（不值为低转化机会出高价）**。上面的公式本身是"维持固定每转化成本"的关系：`CPM = eCPA×pCVR×1000`。所以 pCVR 从 2% 降到 1%，出价从 $1000 降到 $500，而不是升到 $2000。dv360-dfp-deep.md 里那个"反之升到 $2000"的表述应理解为"若用除法 `eCPA/pCVR` 形式且固定 eCPA 与除法关系"，两种形式数值方向相反，本文档采用乘法形式 `CPM = eCPA × pCVR × 1000`（这也是 DV360 内部优化引擎更常见的实现方向：价值高机会出价高）。

`get_bid_strategy_options()` 返回的 `OCPM` 与 `CPA` 分别是"定价模式"与"目标模式"的标签，落地时应把二者结合：**以 oCPM 计费 + 以 Target CPA 为目标**。

### 2.5 程序化保量（Programmatic Guaranteed, PG）固定价格与保量算法

#### 2.5.1 什么是 PG

**Programmatic Guaranteed（程序化保量）** 是 DV360 与供应方（Publisher）之间的一种**直接、程序化、保量**的交易方式。它不同于公开竞价（Open Auction）或私有市场（PMP）——在 PG 中，广告主与发布商通过交易提案（Proposal / Deal）事先约定：

- **固定数量（Guaranteed Quantity）**：承诺的展示次数（impressions）。
- **固定价格（Fixed CPM Price）**：约定的千次展示单价。
- **承诺的定向/库存**：特定广告位、特定目标人群、特定排期。

```
┌────────────────────────────────────────────────────────────────────┐
│                  PG 交易与传统 RTB 对比                             │
│                                                                    │
│  传统 RTB (Open Auction):                                         │
│    需求方(DV360) ──实时竞价──► 供应方(SSP/Exchange)                  │
│    无承诺、无固定价格、每次机会动态竞价                               │
│                                                                    │
│  程序化保量 (PG):                                                   │
│    广告主 ⇄ 发布商 签订 Deal (Proposal)                             │
│         ├─ fixed quantity (量)                                     │
│         ├─ fixed CPM (价)                                          │
│         └─ guaranteed delivery (保量, 类似传统 I/O 直采)             │
│    DV360 按约定出价，供应方承诺交付约定数量                           │
│    若供应方未足量交付 → 违约/补偿机制                                │
└────────────────────────────────────────────────────────────────────┘
```

#### 2.5.2 PG 的固定价格与出价行为

在 PG 中，Line Item 的出价行为与 RTB 不同：因为价格是**事先固定**的，不存在"出价竞争"的博弈空间。DV360 会：

1. 按 Deal 约定的 fixed CPM 出价；
2. 通过匹配规则（deal targeting）确保只对满足 Deal 条件的库存出价；
3. 追求的是**交付率（delivery）**与**排期内的展示数达标**，而非"赢得尽可能多的低价机会"。

这也是为什么 PG Line Item 通常配合**手动出价（等于约定的 CPM）**或**特定的 PG 保量出价**，而不是 Target CPA——因为价格被锁定，优化目标转为"按时足量交付 + 在允许的定向内尽量达标"。

```
PG Line Item 出价行为:
  出价 = Deal 约定的 fixed CPM (常量)
  目标 = 排期内交付约定的 impression 数量 (delivery)
  控制 = pacing 保证"不提前耗尽、不拖后爆量"
  优化 = 尽量在 Deal 允许的 inventory 内高效交付

用 dv360_create_line_item 创建 PG 类型:
  type = 'PROGRAMMATIC_GUARANTEED'
```

#### 2.5.3 保量算法（Guaranteed Delivery Algorithm）

供应方（尤其是使用 GAM/DFP 的发布商）在保量场景下执行**保量投放算法**，其核心是"在承诺的排期内，保证约定的量能足额、平滑地交付，同时不严重超量"：

```
供应方保量算法简化流程:

  1. 为每个保量 Line Item 计算"今日需交付量"
     today_target = (remaining_quantity) / (remaining_days)
  2. 预测今日可用流量 (该 Deal 定向下预计可展示的机会)
  3. 在每个机会上按优先级(priority) 决定是否投放:
     保量 Line Item 通常有最高优先级 (priority 最高)
  4. pacing: 若超前(提前超量) → 降低参与度/暂停参与高价值机会
            若落后(可能不足量) → 提高参与度/放松限制
  5. 结算: 统计足量交付 (makegood 机制补偿欠量)
```

**关键概念**：
- **Priority（优先级）**：保量 Line Item 优先级高，天然优先于竞价的 RTB Line Item。
- **Pacing（供应方侧）**：供应方同样需要 pacing，避免过早用尽约定展示导致后半段无货可交。
- **Under-delivery / Over-delivery**：交付不足或超量。PG 协议通常规定一个容差（如 ±10%），超量部分可能不计费或按比例计费。
- **Makegood（补量）**：当供应方无法足量交付时，通常需要在后续排期补足，或提供其他库存补偿。

#### 2.5.4 PG 出价策略的选择建议

| 场景 | 建议出价策略 | 理由 |
|-----|------------|------|
| 纯品牌保量、价格固定 | 手动 CPM = 约定价 | 简单可控，不引入自动优化噪声 |
| 保量 + 希望优化可见性 | Viewable CPM | 在约定库存内优先可见展示 |
| 保量 + 效果双目标 | 谨慎使用自动出价 | 价格已被 Deal 锁定，自动出价空间有限 |
| 交付率不达标 | 优先检查 pacing/定向/价格 | 出价策略不是主因 |

### 2.6 bid floor / 第二价格对出价的影响

#### 2.6.1 bid floor（出价底价/底价）

**bid floor** 是供应方（卖方）设定的**最低出价**——只有出价高于 floor 的请求才能参与该机会的竞价。floor 是 DV360 出价策略的重要外部约束：

```
bid floor 示意:
  某广告位的 floor = $5 CPM
  你出价 $8  → ≥ floor，可参与竞价
  你出价 $3  → < floor，直接被拒，不参与竞价

对出价策略的影响:
  - 自动出价引擎必须感知 floor：若目标 CPA 太低导致出价普遍低于 floor，
    则几乎没有机会能参与 → 交付率为 0，看似"没量"
  - 手动出价若长期低于 floor，也会"饿死"
  - 很多"没量/CPA 虚高到拿不到量"的问题，本质是出价低于 floor
```

**踩坑实录**：
> 某线索投放把 Target CPA 设得极低（$15），但因该品类优质流量 floor 普遍在 CPM $30 以上，导致引擎对所有机会的出价都低于 floor，14 天交付率不足 5%。排查 DV360 `dv360_get_line_item_performance` 后发现大量请求因 bid floor 被拒。**教训：设置 Target CPA 前应用 floor 意识——目标过低会系统性低于 floor 而无量可投。**

#### 2.6.2 第二价格对出价的影响

如 1.4 节所述，第二价格拍卖下赢家按第二高出价支付。这带来两个重要影响：

1. **出价 = 真实价值，无需多付**：在第二价格下，只要你的出价是"你对该机会的真实估值"，你就能避免多付（因为你只支付第二高）。DV360 的自动出价引擎若面对纯第二价格环境，倾向直接报估值。
2. **floor 与第二价格的组合**：即使第二价格机制让你只付第二高，你仍需至少高于 floor 才能中标。若 floor 高于第二高竞价，你实际支付的可能是 floor 而非次高出价。

```python
# 第二价格支付规则 (概念示意)
winning = (my_bid >= floor) and (my_bid > second_highest)
if winning:
    pay = max(floor, second_highest)
```

#### 2.6.3 对 DV360 出价策略的实战启示

- 面对较低 floor 且第二价格的环境，手动出价也能取得不错效果（真实报价即可）。
- 面对第一价格 + 高 floor，自动出价（含 bid shading）显著优于手动出价。
- 排查"拿到量但成本异常"时，要区分：是 floor 抬高成本，还是竞争抬高成本，还是竞价机制（第一价格过付）抬高成本。

### 2.7 Go 实现竞价优化引擎（预测 → 出价 → pacing）

下面用一个可运行的 Go 示例，实现一个简化但结构完整的竞价引擎：**输入预测值 → 按策略计算动态出价 → 受 pacing 与 floor 约束 → 返回最终出价**。这与 DV360 内部引擎的职责划分一致，可用于帮助理解自动出价的工作方式、也可作为自研 DSP 的参考。

```go
package main

import (
	"fmt"
	"math"
	"time"
)

// BiddingStrategyType 出价策略类型
type BiddingStrategyType int

const (
	StrategyManualCPM BiddingStrategyType = iota
	StrategyTargetCPA
	StrategyTargetROAS
	StrategyMaximizeConversions
)

// StrategyConfig 出价策略配置
type StrategyConfig struct {
	Type         BiddingStrategyType
	TargetCPA    float64 // 目标 CPA (美元/转化)
	TargetROAS   float64 // 目标 ROAS (例如 4.0 = 400%)
	ManualCPM    float64 // 手动出价 CPM
	BidCeiling   float64 // 出价上限 CPM
	BidFloorRef  float64 // 参考 floor CPM
	SurgePercent float64 // Bid Surge 百分比 (0.0=无，1.0=+100%)
}

// Opportunity 单次拍卖机会
type Opportunity struct {
	ID                    string
	PredictedCTR          float64 // pCTR
	PredictedCVR          float64 // pCVR
	ConversionValue       float64 // 单次转化价值
	PredictedViewability  float64 // 可见性概率
	BidFloor              float64 // 该机会的 floor (CPM)
}

// PacingState pacing 状态
type PacingState struct {
	BudgetMicros     float64 // 总预算
	SpentMicros      float64 // 已花费
	FlightStart      time.Time
	FlightEnd        time.Time
	AllowedSpendRate float64 // 当前允许的花费速率
}

// BiddingEngine 竞价引擎
type BiddingEngine struct {
	Config StrategyConfig
	Pacing PacingState
}

// computeBid 计算给定机会的动态出价 (CPM, 美元)
func (e *BiddingEngine) computeBid(opp Opportunity) float64 {
	var bid float64

	switch e.Config.Type {
	case StrategyManualCPM:
		// 手动出价: 使用配置的固定 CPM
		bid = e.Config.ManualCPM

	case StrategyTargetCPA:
		// tCPA: CPM = targetCPA * pCVR * 1000
		bid = e.Config.TargetCPA * opp.PredictedCVR * 1000.0

	case StrategyTargetROAS:
		// tROAS: allowedCost = expectedRev/ROAS → CPM = allowedCost*1000
		expectedRev := opp.PredictedCVR * opp.ConversionValue
		allowedCost := expectedRev / e.Config.TargetROAS
		bid = allowedCost * 1000.0

	case StrategyMaximizeConversions:
		// 最大化转化: 按价值密度出价，受预算和 pacing 约束
		valueDensity := opp.PredictedCVR // 简化: 以 pCVR 为价值代理
		base := valueDensity * e.availableBudgetFactor()
		bid = base * 1000.0
	}

	// 应用 Bid Surge 增强
	if e.Config.SurgePercent > 0 {
		bid = bid * (1.0 + e.Config.SurgePercent)
	}

	// 应用出价上限
	if e.Config.BidCeiling > 0 && bid > e.Config.BidCeiling {
		bid = e.Config.BidCeiling
	}

	// floor 约束: 出价不能低于机会的 floor
	if bid < opp.BidFloor {
		bid = 0 // 出价低于 floor，直接放弃该机会
	}

	return math.Round(bid*100) / 100
}

// availableBudgetFactor 根据预算与 pacing 返回可选花费因子 (0~inflated)
func (e *BiddingEngine) availableBudgetFactor() float64 {
	remaining := e.Pacing.BudgetMicros - e.Pacing.SpentMicros
	if remaining <= 0 {
		return 0
	}
	// 简化: 剩余预算越大、越接近到期，因子越高
	now := time.Now()
	total := e.Pacing.FlightEnd.Sub(e.Pacing.FlightStart).Hours()
	left := e.Pacing.FlightEnd.Sub(now).Hours()
	if total <= 0 || left <= 0 {
		return remaining / 1000.0
	}
	// 前载倾向: 越接近 deadline 越激进
	return (remaining / 1000.0) * (total / left)
}

func (e *BiddingEngine) recordSpend(amount float64) {
	e.Pacing.SpentMicros += amount
}

func main() {
	eng := &BiddingEngine{
		Config: StrategyConfig{
			Type:       StrategyTargetCPA,
			TargetCPA:  50.0,
			BidCeiling: 2000.0,
		},
		Pacing: PacingState{
			BudgetMicros:    1000000, // $1000
			SpentMicros:     200000,  // $200 已花
			FlightStart:     time.Now().Add(-time.Hour),
			FlightEnd:       time.Now().Add(7 * 24 * time.Hour),
		},
	}

	opps := []Opportunity{
		{ID: "A", PredictedCVR: 0.02, BidFloor: 5},
		{ID: "B", PredictedCVR: 0.005, BidFloor: 5},
		{ID: "C", PredictedCVR: 0.02, BidFloor: 30}, // 高 floor
		{ID: "D", PredictedCVR: 0.0005, BidFloor: 5},
	}

	for _, o := range opps {
		bid := eng.computeBid(o)
		fmt.Printf("机会 %s: pCVR=%.4f floor=%.0f → 出价 CPM=$%.2f\n",
			o.ID, o.PredictedCVR, o.BidFloor, bid)
	}
}
```

**运行结果预期**：
```
机会 A: pCVR=0.0200 floor=5 → 出价 CPM=$1000.00
机会 B: pCVR=0.0050 floor=5 → 出价 CPM=$250.00
机会 C: pCVR=0.0200 floor=30 → 出价 CPM=$1000.00
机会 D: pCVR=0.0005 floor=5 → 出价 CPM=$25.00
```

这个引擎清晰地展示了：**高转化价值机会（A）比低价值机会（D）出价高 40 倍**，这正是自动出价比手动出价高效的核心。它也展示了 floor 约束：若某机会 floor 高于计算出价，引擎会放弃（出价 0）。

### 2.8 pacing 深入：如何用 dv360_get_pacing_rate 诊断交付问题

pacing 是自动出价成功的前提。即使出价策略完美，如果 pacing 配置错误，也会导致过早耗尽或交付不足。DV360 提供 pacing 相关 API 用于诊断：

```python
def diagnose_pacing(advertiser_id, line_item_id):
    """用 dv360_get_pacing_rate 诊断 Line Item 的 pacing 健康度"""
    pacing = client.dv360_get_pacing_rate(advertiser_id, line_item_id)

    status = pacing.get('pacingStatus')     # PACED / UNDELIVERED / OVERDELIVERED
    mode = pacing.get('pacingMode')         # PACING_MODE_EVEN / PACING_MODE_ASAP
    current = pacing.get('currentRate')     # 当前流速

    print(f"Line Item {line_item_id}:")
    print(f"  pacingStatus = {status}")
    print(f"  pacingMode   = {mode}")
    print(f"  currentRate  = {current}")

    if status == 'OVERDELIVERED':
        print("⚠️ 交付过快，预算可能提前耗尽。")
        print("   建议: 提高 pacing 平滑度，或检查是否叠加了 Bid Surge。")
    elif status == 'UNDELIVERED':
        print("⚠️ 交付不足，量未达标。")
        print("   建议: 检查出价是否低于 floor，或受众/定向是否过窄，或预算是否过低。")
    else:
        print("✅ pacing 正常。")
```

**pacing 状态字典**：

| pacingStatus | 含义 | 处理建议 |
|-------------|------|---------|
| `PACED` | pacing 正常，按计划交付 | 无需干预 |
| `OVERDELIVERED` | 超前交付 | 平滑 pacing；排查 Surge / 出价过高 / ASAP 模式 |
| `UNDELIVERED` | 交付不足 | 检查出价 vs floor、定向宽窄、预算、库存 |
| `DELIVERED` | 已足量交付完成 | 任务结束，评估是否扩量 |

### 2.9 本章小结

- **Bid Surge**：临时型出价增强器，适合品牌冲刺，禁用效果/预算紧张场景；第一价格下有成本放大风险。
- **Auto-bidding 闭环**：预测 pCVR/pCTR → 按策略出价 → pacing 平滑 → 反馈学习；学习期 3-7 天，频繁改动会重置。
- **tCPA / tROAS**：一个是"成本上限导向"，一个是"收入回报导向"；tROAS 依赖准确价值回传。
- **oCPM**：`CPM = eCPA × pCVR × 1000`，"按 CPM 计费 + 自动优化转化目标"。
- **PG 保量**：固定价格 + 保量算法，目标从"赢竞价"变为"按时足量交付"。
- **floor / 第二价格**：floor 过低目标会"饿死无量"，第二价格下可报真实估值，第一价格下自动出价更有优势。
- **Go 引擎**：预测→出价→约束（ceiling/floor/surge/pacing）的完整职责分离模型。


---

## 三、生产环境实战

### 3.1 从手动出价迁移到自动出价：完整案例

#### 3.1.1 案例背景

某跨境电商团队运营一个 Retail 品类 DV360 账户，过去一直用**手动 CPM 出价**投放效果 Line Item，表现如下：
- 日均预算：$2,000
- 平均 CPM：$12
- 平均 CTR：0.8%
- 平均 CVR：1.2%
- 平均 CPA：约 $125（ROAS 约 2.5x）

团队发现：手动出价下大量预算花在低转化机会上，CPA 长期在 $120-$140 间波动，且高峰时段经常抢不到量。他们决定把一个测试班次迁移到自动出价，逐步验证。

#### 3.1.2 迁移前的数据准备

迁移前必须确认：
1. **有足够的转化数据**：该 Line Item 近 30 天至少几百次转化，否则 ML 无从学习；
2. **转化回传准确**：Floodlight 转化标签正确埋点；
3. **选定合适的初始目标**：参考历史实际 CPA/ROAS 设定一个"合理但略紧"的目标。

```python
from ad_platform_api import AdPlatformAPI

client = AdPlatformAPI()
adv = '123456'          # 广告主 ID
io = 'io_789'           # 广告系列 ID

# 第一步: 读取历史表现, 确定基准 CPA / ROAS
perf = client.dv360_get_line_item_performance(
    line_item_id='li_effect_001',
    date_range={'start': '2026-07-01', 'end': '2026-07-30'}
)
hist_cpa = perf['total_cost'] / (perf['conversions'] or 1)
hist_roas = perf['revenue'] / (perf['total_cost'] or 1)
print(f"历史 CPA ≈ ${hist_cpa:.1f}, ROAS ≈ {hist_roas:.2f}x")

# 第二步: 列出当前出价策略, 确认切换前状态
strategies = client.dv360_list_bidding_strategies(adv)
for s in strategies:
    print(s['name'], s['type'])
```

#### 3.1.3 策略选择与切换

**策略选择矩阵（针对本案例）**：

| 业务目标 | 推荐初始出价策略 | 初始目标 |
|---------|----------------|---------|
| 想降低成本（CPA 导向） | Target CPA | 历史 CPA 的 85%（略紧） |
| 想提升回报（ROAS 导向） | Target ROAS | 历史 ROAS 的 120%（略高） |
| 想最大化转化量 | Maximize Conversions | 固定预算 |
| 尚未确定方向 | 先用 Maximize Conversions | 固定预算 |

本例团队选择了 **Target CPA = $110**（历史 $125 的 ~88%，略紧但可行），并保留手动出价 Line Item 作为对照组进行 A/B 对比。

**切换操作**（不要删除重建，用 update 保持连续性与学习数据）：

```python
# 将既有 Line Item 的出价策略切换为 Target CPA
client.dv360_update_line_item(
    advertiser_id=adv,
    line_item_id='li_effect_001',
    bidding_strategy={
        'type': 'BIDDING_STRATEGY_TYPE_TARGET_CPA',
        'targetCpaMicros': 110_000_000   # $110
    }
)
```

> **关键坑**：不要为了换出价策略而删除旧 Line Item 重建。删除重建会丢失历史转化数据、重置学习期，且 DV360 的历史表现与信誉会清零。用 `dv360_update_line_item` 原地切换是标准做法。

#### 3.1.4 学习期管理

切换后进入学习期（约 3-7 天），此时：
- 表现可能波动，CPA 可能暂时高于目标；
- **不要频繁改目标**（每次改动重置学习期）；
- 用对照组（手动出价 Line Item）做同期对比，判断自动出价是否真的更优。

```python
def monitor_learning_period(adv, li, days=7):
    """学习期监控: 记录每日 CPA 并预警异常"""
    for d in range(1, days + 1):
        dom = f"2026-08-{d:02d}"
        perf = client.dv360_get_line_item_performance(
            line_item_id=li,
            date_range={'start': dom, 'end': dom}
        )
        cpa = perf['total_cost'] / (perf['conversions'] or 1)
        status = "⚠️学习期波动" if d <= 5 else "✅趋于收敛"
        print(f"Day{d} {dom}: CPA=${cpa:.1f} conversions={perf['conversions']} {status}")
```

#### 3.1.5 迁移结果与经验

经过 2 周对照，结果：
- 自动出价 Line Item：CPA 收敛到 $94（较手动 $125 下降 25%），转化量提升 18%；
- 手动出价对照组：CPA 仍约 $122；
- **结论：保留 Target CPA 自动出价，批量迁移同品类其他 Line Item，同时把手动出价降级为备份/特殊用途**。

**迁移经验总结**：
1. 数据是第一前提：转化不足或回传不准时强行上自动出价会翻车；
2. 目标从历史值"略微收紧"起步，给模型留学习空间；
3. 用对照组隔离验证，避免拍脑袋；
4. 学习期（3-7 天）内不改目标、不叠加 Bid Surge；
5. 使用 update 而非 delete+create 保住历史与信誉。

### 3.2 不同 KPI 的策略选择指南

业务目标不同，出价策略完全不同。下表是实战选型指南：

| 业务 KPI | 推荐出价策略 | 说明 |
|---------|------------|------|
| 品牌可见度（GRP/Reach/频次） | 手动 CPM / Viewable CPM | 关注曝光与可见性，无需转化数据 |
| 品牌 + 可见性优化 | Viewable CPM | 在可见 CPM 目标下优化可见展示 |
| 视频观看量 | Fixed CPV | 按观看计费，品牌视频 |
| 点击/流量获取 | Maximize Clicks 或 Fixed CPC | 以点击量为目标 |
| 效果转化（成本导向） | Target CPA | 有明确单次转化成本上限 |
| 效果转化（回报导向/电商） | Target ROAS | 有准确价值回传 |
| 效果转化（量最大） | Maximize Conversions | 预算固定想最多转化 |
| 大促/事件冲刺 | 现有策略 + Bid Surge | 临时提升竞争力 |
| 保量品牌单 | 手动 CPM = 约定价 | PG 价格固定 |
| 再营销高意向 | Target CPA（略紧）/ROAS | 高 pCVR，自动出价有优势 |

**选型决策树**：
```
开始
├─ 目标是品牌曝光/可见性? 
│   └─ Yes → 手动 CPM / Viewable CPM
├─ 目标是视频观看? 
│   └─ Yes → Fixed CPV / 视频 Viewable
├─ 有转化数据 + 效果目标?
│   ├─ 有明确单次成本上限 → Target CPA
│   ├─ 有价值回传 + 电商 → Target ROAS
│   └─ 只想最多转化 → Maximize Conversions
├─ 有大促/冲刺需求? 
│   └─ 在现有策略上叠加 Bid Surge
└─ 数据不足?
    └─ 先用手动出价收集数据 → 再切自动出价
```

### 3.3 学习期处理（自动出价的成长期）

**学习期（Learning Period）** 是自动出价模型积累信号、建立置信度的时间窗口（典型 3-7 天）。学习期管理是自动出价成功率的关键。

#### 3.3.1 怎么判断还在不在学习期

- DV360 UI 与报表会标注 Line Item 是否仍处于"学习/探索"状态；
- 时段表现明显不稳、CPA 偏高、转化零散；
- 通过 `dv360_get_line_item_performance` 观察日粒度波动。

#### 3.3.2 学习期注意事项（Do & Don't）

| 动作 | 建议 |
|-----|------|
| ✅ 保持目标稳定 | 学习期内不调目标，改动会重置 |
| ✅ 保持预算充足 | 预算过小 → 转化数据不足 → 学不动 |
| ✅ 保持定向稳定 | 频繁改定向也扰动学习 |
| ❌ 叠加 Bid Surge | Surge 抬高出价，污染"真实价值"信号 |
| ❌ 频繁暂停/重启 | 中断学习信号 |
| ❌ 过早下结论 | 表现差可能只是学习期探索成本，需等收敛 |

#### 3.3.3 学习期失败场景与应对

**场景 1：学习期结束后依旧 CPA 超目标**
- 可能原因：目标设得过低（低于市场实际可达）、转化回传有问题、定向过宽导致 pCVR 被稀释。
- 应对：先检查回传；再适度放宽目标（如从 $110 调到 $120）；扩大高意向受众。

**场景 2：学习期后无量（交付为 0）**
- 可能原因：出价普遍低于 floor、定向过窄、预算太低。
- 应对：用 `dv360_get_pacing_rate` + floor 意识排查；放宽定向；提高目标。

**场景 3：学习期反复重置**
- 原因：频繁改目标/定向/暂停导致模型始终无法收敛。
- 应对：冻结配置，给足 7-14 天稳定窗口。

### 3.4 Bid Surge 在品牌冲刺期的应用：实战配方

#### 3.4.1 完整实施步骤

以"黑五品牌冲刺"为例：

```
Step 1: 确认场景
  - 目标: 黑五当周品牌可见度最大化
  - 载体: 独立品牌 Line Item (与效果单隔离!)，手动 CPM 出价

Step 2: 设定基准出价
  - 用 dv360_create_line_item 创建/复用品牌 Line Item
  - 手动 CPM 设为近期稳定且可盈利的水平 $10

Step 3: 规划 Surge 窗口
  - 黑五 00:00-24:00 叠加 +150%
  - 为避免预算过早耗尽, 为 Surge 日单独提高预算或日预算

Step 4: 用 API 配置/监控
  - dv360_update_line_item 配置 surge 相关字段
  - 监控 dv360_get_pacing_rate 防止 OVERDELIVERED
  - 监控 dv360_get_line_item_performance 检查 CPA/曝光

Step 5: 结束评估
  - 恢复基准出价 (移除 Surge)
  - 对比 Surge 日 vs 常规日: 曝光增量、CPM 涨幅、品牌指标
```

```python
def apply_bid_surge(adv, brand_li, surge_pct=1.5, start='2026-11-27', end='2026-11-27'):
    """为品牌 Line Item 配置 Bid Surge 窗口 (概念示例)"""
    client.dv360_update_line_item(
        advertiser_id=adv,
        line_item_id=brand_li,
        bid_surge={
            'enabled': True,
            'surgePercentage': surge_pct,       # 1.5 = +150%
            'startDate': start,
            'endDate': end,
            # 实际字段以 DV360 API 版本为准
        }
    )
    print(f"Bid Surge 已开启: {surge_pct*100:.0f}%, 窗口 {start}~{end}")
```

#### 3.4.2 Bid Surge 最佳实践清单

1. **与效果单隔离**：Surge 只用品牌/冲刺 Line Item，绝不用于 CPA/ROAS 效果单。
2. **预算匹配**：Surge 会提速消耗，Surge 日前要确认预算充足，或单独加预算。
3. **控制 Surge 幅度**：从 +50% 起步、观察 win rate 与成本再上调；单次最高建议控制在 +100%~+200%，避免失控。
4. **错峰使用**：Surge 只覆盖目标时段，避免 24h 无差别抬价。
5. **配合 frequency cap**：防止同一用户被频繁高强度触达。
6. **Surge 后观察期**：结束 Surge 后留 1-2 天观察，确认回落正常、未污染长期模型。

#### 3.4.3 踩坑：Surge 与自动出价的冲突

> **关键认知**：Bid Surge 与自动出价叠加时要非常小心。自动出价本身会基于价值动态调价，Surge 若再成比例抬价，可能导致引擎在高价值机会上以远超真实价值的价格成交（第一价格下尤其严重），且会反向污染模型的成本信号。若必须同时用，应：a) Surge 幅度控制在低档（如 +50%）；b) 设出价上限（bid ceiling）；c) 严格限时。**黄金法则：效果目标 ≠ Surge 场景。**

### 3.5 预算与出价策略的协同

#### 3.5.1 预算矛盾问题

自动出价与预算之间存在常见矛盾：**出价策略决定"每次机会出多少"，预算与 pacing 决定"能花多少"**。二者需协同，否则：

| 矛盾 | 表现 | 根因 |
|-----|------|------|
| 出价过高 + 预算小 | 预算瞬时烧光，后半段无投放 | 出价策略与预算不匹配 |
| 出价过低 + 预算大 | 预算花不完，量不足 | 出价 < floor 或竞争力不足 |
| Surge + 固定预算 | Surge 日预算提前耗尽 | Surge 加剧消耗 |
| 目标 CPA 过低 + 预算大 | 有预算但无合格机会 | 目标过低无量可投 |

#### 3.5.2 协同策略

```python
def align_budget_and_bid(adv, li, budget_micros, optimal_bid_cpm):
    """确保预算与出价策略协同 (示例)"""
    # 1. 更新预算
    client.dv360_update_line_item_budget(
        line_item_id=li,
        budget_micros=budget_micros
    )
    # 2. 校验出价在合理范围 (相对 floor 与市场)
    if optimal_bid_cpm < 5:   # 极低, 可能低于 floor
        print("⚠️ 出价过低, 检查 floor 与目标设置")
    # 3. 确认 pacing 模式 (EVEN vs ASAP)
    pacing = client.dv360_get_pacing_rate(adv, li)
    print("pacing:", pacing.get('pacingStatus'))
```

**实践建议**：
- 自动出价场景优先 `PACING_MODE_EVEN`（匀速），除非有明确冲刺需求；
- Surge 日前单独复核预算，必要时临时扩预算后再恢复；
- 用 `dv360_list_budget_allocations` 检查 IO/账户层预算分配，避免 Line Item 预算被上层卡死。

### 3.6 用 Recommendations（智能优化建议）辅助出价策略调优

DV360 会基于账户表现生成优化建议（Recommendations），其中包含出价策略相关的建议（如"可提升出价""建议切换到 Target ROAS""预算建议"）。可用 API 拉取并批量评估。

```python
def review_bid_recommendations(adv):
    """列出并评估 DV360 出价相关优化建议"""
    recs = client.dv360_list_recommendations(adv)
    actionable = []
    for r in recs:
        kind = r.get('type', '')
        # 仅关注出价/预算相关的建议，过滤掉无关项
        if any(k in kind.upper() for k in ['BID', 'BUDGET', 'PACING', 'TARGET']):
            actionable.append(r)
            print(f"[{r['id']}] {r.get('name')} → {r.get('description')}")

    return actionable

# 注意: 不建议盲目 apply。每条建议都要人工判断是否与业务目标一致。
# recs = review_bid_recommendations('123456')
# client.dv360_apply_recommendation('rec_120938')
```

> **风险提示（踩坑）**：DV360 Recommendations 的"提升出价""增加预算"类建议通常会最大化曝光/转化，但可能推高成本、破坏既有 CPA/ROAS 目标。**务必人工审查每条建议的业务一致性后再 `dv360_apply_recommendation`，不建议全盘自动应用。** 曾有团队盲目 apply "提高出价"建议，CPA 在一周内飙高 60%。

### 3.7 生产环境最佳实践清单（Checklist）

**出价策略设定 Checklist**：
- [ ] 明确业务 KPI（成本/回报/量/品牌）
- [ ] 确认转化与价值回传准确
- [ ] 确认历史数据量足够（几百次转化以上）
- [ ] 从历史值略微收紧设定初始目标
- [ ] 保留对照组（手动 vs 自动 / 不同目标）
- [ ] 学习期内冻结配置，不改目标
- [ ] 用 floor 意识验证目标可实现性
- [ ] 设置出价上限（bid ceiling）防失控
- [ ] 协调预算与 pacing 模式（EVEN 优先）
- [ ] Bid Surge 仅用于品牌/冲刺，与效果单隔离

**运营节奏建议**：
- 日：检查 pacing（`dv360_get_pacing_rate`）、交付率、预算消耗；
- 周：评估 CPA/ROAS 相对目标偏离度，做小幅微调；
- 月：全账户出价策略健康审计，对比不同策略 ROI；
- 事件前/中/后：Surge 与预算调配、恢复与复盘。

### 3.8 本章小结

- 手动→自动迁移的核心是"数据足够 + 历史基准 + 对照组 + 学习期管理 + update 而非 delete"。
- 用"业务 KPI → 出价策略"选型矩阵，避免"一刀切"。
- 学习期 3-7 天应冻结配置，杜绝 Surge/频繁改动。
- Bid Surge 是品牌冲刺利器，但需与效果单隔离、预算匹配、控制幅度。
- 用 API（`dv360_get_pacing_rate`、`dv360_get_line_item_performance`、`dv360_list_recommendations`）做常态化监控与调优。


---

## 四、常见问题与排查

### 4.1 FAQ 速查表

下面汇总 DV360 竞价策略相关的**高频问题与排查要点**：

| # | 问题 | 快速结论 | 排查切入 |
|---|------|---------|---------|
| 1 | 自动出价好像"没生效"，出价没变化 | 可能仍在学习期，或目标导致所有机会都被拒 | 检查学习期标志、floor、delivery |
| 2 | 出价异常偏高/偏低 | 目标设错、价值回传错误、Surge 误开、floor 影响 | 核对目标、回传、Surge、pacing |
| 3 | pacing 卡住/交付停滞 | 出价 < floor、定向过窄、预算过低、库存缺失 | `dv360_get_pacing_rate` |
| 4 | CPA 突然飙升 | Surge 叠加、目标被改、价值回传错误、竞争加剧 | 检查 Surge、目标改动、回传与市场 |
| 5 | 切换出价策略失败 | 参数错误、类型不兼容、无 update 权限 | 校验 API 字段、权限 |
| 6 | Target ROAS 表现差 | 价值回传不准确或缺失 | 检查 conversion_value 回传 |
| 7 | Bid Surge 没效果 | 幅度太小、窗口错、被 bedrock/预算限制 | 检查 Surge 幅度、窗口、预算 |
| 8 | 交付不足但出价已很高 | 库存稀缺 / 优质流量被竞品抢 | 检查 win rate、库存、换 pmp |
| 9 | 预算快速耗尽 | pacing ASAP 或 Surge 或出价过高 | 换 EVEN、去 Surge、降出价 |
| 10 | 不知道选哪种出价策略 | 用 KPI 选型矩阵（见 3.2） | 明确业务 KPI + 数据成熟度 |

### 4.2 问题 1：自动出价似乎没生效

**现象**：设置了 Target CPA / Maximize Conversions，但表现和手动出价差不多，甚至没变化。

**排查步骤**：
1. **确认 Line Item 确实用了自动出价**（检查 `dv360_update_line_item`/`dv360_list_bidding_strategies` 所设策略）；
2. **确认是否仍在学习期**：学习期模型在探索，可能看不出明显差异；
3. **确认转化回传**：若 Floodlight 转化没回传或回传量极少，ML 无信号，自动出价退化为近手动的随机行为；
4. **确认目标可实现**：目标 CPA 设得过低 → 几乎所有机会出价都低于 floor → 无量、看起来"没生效"；
5. **看 delivery 而非只看出价**：自动出价的价值在于"把预算花在更值的机会上"，可能单次出价看似没变，但成交的价值结构变了。

```python
def check_autobid_effective(adv, li):
    perf = client.dv360_get_line_item_performance(
        line_item_id=li,
        date_range={'start': '2026-08-01', 'end': '2026-08-14'}
    )
    conv = perf.get('conversions', 0)
    cost = perf.get('total_cost', 0)
    cpa = cost / conv if conv else None
    print(f"转化={conv}, 花费=${cost:.0f}, CPA={'$%.1f'%cpa if cpa else 'N/A'}")
    print("若转化过少(<30/周) → 模型学不动, 自动出价效果难显现")
    print("若 Delivery/Impressions 很低 → 检查目标是否低于 floor")
```

### 4.3 问题 2：出价异常偏高或偏低

**偏高可能原因**：
- Bid Surge 误开或幅度过大；
- 第一价格环境下手动出价过付；
- 价值回传被放大（如重复回传、金额单位错误）；
- Target ROAS 设得太低（导致允许成本上限虚高）。

**偏低可能原因**：
- Target CPA 太低（价值信号压缩出价）；
- 预测模型判定该机会价值低；
- floor 正好卡在计算出价之上，导致整体无量。

**排查动作**：
```python
# 排查出价异常: 检查 Surge 与 pacing
pacing = client.dv360_get_pacing_rate(adv, li)
print("pacing:", pacing.get('pacingStatus'), pacing.get('pacingMode'))
# Surge 应只在特定窗口, 排查是否残留开启
```

### 4.4 问题 3：pacing 卡住 / 交付停滞

**常见根因与解法**：

| 根因 | 判断方法 | 解法 |
|-----|---------|------|
| 出价 < floor | 大量请求被拒，delivery≈0 | 提高出价/调目标，确认 floor |
| 定向过窄 | 覆盖人群太小，无合格机会 | 放宽定向、扩大受众 |
| 预算过低 | pacing 模式 ASAP 但预算太小 | 加预算，或确认量与预算匹配 |
| 优质库存缺失 | 特定广告位/时段无货 | 换库存、加 PMP |
| 目标 CPA 过低 | 出价系统性低于市场 | 调高目标至合理区间 |

**诊断脚本**：
```python
def diagnose_stalled(adv, li):
    pacing = client.dv360_get_pacing_rate(adv, li)
    perf = client.dv360_get_line_item_performance(
        line_item_id=li, date_range={'start': '2026-08-07', 'end': '2026-08-14'}
    )
    print("pacingStatus:", pacing.get('pacingStatus'))
    print("impressions:", perf.get('impressions'))
    print("bid requests / matches 需看 detailed 报表")
    if perf.get('impressions', 0) == 0:
        print("→ 可能原因: floor 过高 / 定向过窄 / 目标过低")
```

### 4.5 问题 4：CPA 突然飙升

**系统性排查清单**（按概率排序）：

1. **是否叠加了 Bid Surge？** Surge 抬高出价 → 成本上升 → CPA 恶化。→ 移除或降低 Surge。
2. **是否有人在学习期内改了目标？** 改动会重置模型、引入探索成本。→ 恢复目标并冻结。
3. **转化价值回传是否出错？** 若 ROAS/cost 信号被破坏，模型乱出价。→ 核对 Floodlight/revenue 回传。
4. **竞品是否加价？** 外部竞争推高成本。→ 观察 win rate 与市场，考虑加预算/换库存。
5. **是否存在转化归因延迟/回填？** 转化延迟导致 CPA 统计失真（近期看起来高，之后回填）。→ 给予归因窗口，避免误判。
6. **pacing 是否过早耗尽优质机会？** OVERDELIVERED 导致后半段只能低价补量。→ 平滑 pacing。

**决策表**：

| 症状 | 大概率根因 | 立即动作 |
|-----|----------|---------|
| CPA 飙升 + 曝光也升 | Surge 或出价过高 | 去 Surge / 降出价 |
| CPA 飙升 + 曝光降 | floor/定向问题 | 调目标 / 松弛定向 |
| CPA 飙升 + 转化也升 | 归因延迟 / 目标放宽 | 看归因窗口 |
| CPA 飙升 + 回传没问题 | 竞争加剧 | 观察/加预算/换库存 |

### 4.6 问题 5：切换出价策略失败

**常见报错与处理**：

| 报错/现象 | 原因 | 处理 |
|---------|------|------|
| 400 参数校验失败 | `bidding_strategy` 结构不对或字段名错 | 对照 API schema 校验字段名 |
| 策略类型不兼容 | 某些 Line Item 类型（如 PG）不接受某自动策略 | 确认 PG 用固定出价 |
| 403 权限不足 | 无 update 权限 | 检查服务账号角色 |
| 无响应/超时 | API 限流 | 重试、退避、分批 |

```python
def safe_switch_strategy(adv, li, new_strategy):
    """安全切换出价策略, 带错误处理"""
    try:
        client.dv360_update_line_item(
            advertiser_id=adv, line_item_id=li, bidding_strategy=new_strategy
        )
        print("切换成功")
        return True
    except Exception as e:
        print(f"切换失败: {e}")
        # 常见: PG 类型不支持自动策略 → 需先确认 Line Item type
        return False
```

### 4.7 问题 6：Target ROAS 表现差 / 不达标

ROAS 目标的成败高度依赖**价值回传的准确性**。排查：
- 转化是否带有动态 value（订单金额）？
- value 货币单位是否正确？
- 是否出现同一笔收入多次计数（去重问题）？
- model 是否在校准中？

**最佳实践**：ROAS 上线前先做 value 回传验证，用报表交叉核对"转化 count 与 value sum"是否与业务系统一致。

### 4.8 问题 7：Bid Surge 没效果

- **幅度太小**：+10% 在激烈竞争下几乎无感 → 加大到 +50%~+100%；
- **窗口不对**：目标时段未覆盖为 Surge 窗口 → 核对时区与日期；
- **预算限制**：预算已将可花额卡死，Surge 抬价但总量没变 → 扩预算；
- **被 pace / bedrock 限制**：顶部安全预算或 pacing 压住 → 检查上层与 pacing。

### 4.9 问题 8：为什么 Discovery 与命中率低（配合地板）

**现象**：报表里 bid requests 不少，但 match/win 很少，impressions 低。
**根因**：出价普遍低于 floor（或被各交易所 floor 覆盖）。
**解法**：
- 用 floor 意识调整目标/出价；
- 若某交易所 floor 异常高，考虑从 Leo/库存策略规避；
- 适当放宽定向以进入更低 floor 的库存池。

### 4.10 排查方法论总结

统一排查流程（适用所有出价问题）：
```
1. 明确现象 (出价? CPA? 交付? 曝光?)
2. 用 API 拉数据: dv360_get_pacing_rate + dv360_get_line_item_performance
3. 分层归因:
   a. 策略层: 出价策略类型是否正确 / 目标是否合理
   b. 成本层: Surge / floor / 第一价格过付 / 竞争
   c. 交付层: pacing / 预算 / 定向宽度 / 库存
   d. 数据层: 转化回传 / 价值回传 / 归因窗口
4. 单变量调整 (一次只改一个), 观察 3-7 天效果
5. 保留基线对照, 避免凭感觉
```

### 4.11 本章小结

- 绝大多数出价问题可归为四类：**策略误配、成本失控（Surge/floor/第一价格）、交付受阻（pacing/定向/预算）、数据失真（回传/归因）**。
- 排查要用数据说话：`dv360_get_pacing_rate`、`dv360_get_line_item_performance` 是核心诊断工具。
- 一次只改一个变量，保留对照，观察学习期后再下结论。

