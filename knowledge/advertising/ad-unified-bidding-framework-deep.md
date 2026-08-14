# 跨平台统一出价框架设计

> **领域**: 广告投放 / 跨平台
> **深度**: ⭐⭐⭐⭐⭐ 实战级指南
> **标签**: cross-platform, unified-bidding, bandit, reinforcement-learning, production
> **更新时间**: 2026-08-14
> **类型**: architecture/production

---

## 一、核心概念与架构

### 1.1 为什么需要统一出价框架

现代广告投放早已不是"单平台单策略"的时代。一家出海游戏发行商、一家跨境电商卖家、或者一家品牌广告主，往往需要同时在 **Google Ads、Meta (Facebook/Instagram)、TikTok Ads、DV360 (Display & Video 360)** 等多个平台上进行投放。每个平台都有自己的出价体系、归因窗口、报表口径、预算节奏和优化算法。

在这种多平台背景下，广告投放团队面临一系列难以回避的问题：

1. **出价口径不一致**：Google 用 vCPM / H-iMax，Meta 用 Optimized Bidding + CBO，TikTok 用 oCPM，DV360 用 Target CPM / Custom Bidding。同样的"目标 ROAS"，在不同平台上的表达方式、约束方式、可调参数完全不同。运营同学需要把同一目标翻译成四种不同的"平台黑话"。

2. **预算分配是静态的**：很多团队按天、按周的固定比例把预算分到各个平台，缺乏对这些平台"边际收益"的实时感知。当一个平台的 eCPM 突然上涨、另一个平台正好有流量红利时，静态比例分配会白白浪费预算。

3. **缺乏统一的跨平台视角**：各平台自带的报表相互独立，归因模型可能各自为政。同一个用户的转化可能是 Google 承接的，也可能是 Meta 或 TikTok 带来的，但各平台都在"邀功"，导致重复计费与虚假的规模感。

4. **优化算法各自为战**：每个平台都在用各自的机器学习模型做"智能出价"。广告主无法把这些平台的出价行为纳入统一的风控、ROAS 约束和预算节奏之中，也无法用自己的第一方数据（转化、LTV、App 内行为）反过来校准各平台的预估。

5. **无法实现"平台级套利"**：在信息差的窗口期，有的平台流量便宜、有的平台转化质量好。没有统一出价框架，就无法把这种套利机会系统化、自动化地捕捉到。

**统一出价框架 (Unified Bidding Framework, UBF)** 的使命，就是把这四类平台背后的出价能力抽象成"一份逻辑、多个适配器"，让上层业务（预算分配、ROAS 目标、LTV 优化、风控）只用面对一套统一的出价接口与数据模型，由框架负责把统一指令翻译成各平台原生 API 调用、并把各平台的原生结果归一化回统一数据模型。

> **一句话定位**：统一出价框架不是要取代平台内部的智能出价算法（也取代不了），而是要在平台之上做"统一的目标表达、统一的预算节奏、统一的约束控制、统一的效果归因与闭环调参"。

### 1.2 统一出价框架的整体定位与边界

在深入架构之前，先明确 UBF 的位置和边界，避免"什么都往里塞"的架构膨胀。

```
                    ┌─────────────────────────────────────────────┐
                    │          上层业务 / 决策层                    │
                    │  预算分配 · ROAS 目标 · LTV 优化 · 风控决策     │
                    └─────────────────────────────────────────────┘
                                      │ 统一目标 / 预算 / 约束
                                      ▼
              ┌─────────────────────────────────────────────────┐
              │           统一出价框架 (UBF)                      │
              │  ┌───────────┐  ┌───────────────────────────┐    │
              │  │ 统一出价层   │  │  智能出价 Agent (Bidding   │    │
              │  │ (Bid API /  │  │   Orchestrator)            │    │
              │  │  参数归一化) │  │   · Bandit               │    │
              │  │            │  │   · Contextual RL          │    │
              │  └───────────┘  │   · Constraints             │    │
              │                 └───────────────────────────┘    │
              │  ┌───────────────────────────────────────────┐   │
              │  │  平台适配层 / 归因闭环                      │    │
              │  │  Google │ Meta │ TikTok │ DV360 适配器     │    │
              │  └───────────────────────────────────────────┘   │
              └─────────────────────────────────────────────────┘
                                      │ 平台原生 API
              ┌───────────────────────┼───────────────────────┐
              ▼                       ▼                       ▼
          Google Ads               Meta Ads               TikTok Ads
          (H-iMax / vCPM)    (Optimized+CBO/Advantage+)   (oCPM)
                                        ▼
                                     DV360
                               (Target CPM / Custom Bid)
```

边界划分原则：

- **UBF 负责 "跨平台编排"**：目标翻译、预算节奏、约束控制、Agent 决策、归因闭环。
- **UBF 不负责 "平台内部排期"**：平台竞价系统的 auction、rank、quality score 是平台内的事，UBF 尊重平台的原生算法。
- **UBF 提供 "统一意图 + 旁路微调"**：既能以"目标导向"调用平台算法（告诉平台"我的 ROAS 目标是 2.5"），也能在平台支持的情况下做"出价补偿 / bid multiplier" 的旁路微调。
- **UBF 是 "控制面 + 数据面" 混合**：控制面负责发指令，数据面负责把各平台原生结果拉回合流成统一指标。

### 1.3 核心概念定义

统一出价框架涉及一组需要严格定义的概念。概念不统一，后面的数据模型和算法就会混乱。

| 概念 | 英文 | 定义 | 示例 |
| --- | --- | --- | --- |
| 出价 | Bid | 对一次展示机会愿意支付的最高价格 | 0.85 美元 / 千次展示 |
| 千次展示出价 | CPM Bid | 每千次展示的付费出价 | 5.0 USD CPM |
| 有效千次展示成本 | eCPM | 实际支付的有效成本 = 花费 / 展示 × 1000 | 4.7 USD |
| 每次点击成本 | CPC | 单次点击成本 | 0.42 USD |
| 每行动成本 | CPA | 单次转化行动成本 | 18.5 USD |
| 广告支出回报 | ROAS | 收入 / 花费 | 3.2x |
| 转化率 | CVR | 转化 / 点击（或转化/展示） | 4.2% |
| 点击率 | CTR | 点击 / 展示 | 1.8% |
| 预算节奏 | Budget Pacing | 预算在时间上的消耗曲线 | 均匀 / 前倾 / 昼行 |
| 目标导向出价 | Goal-based Bidding | 把目标交给平台算法去实现 | 目标 CPA = 18 USD |
| 外部微调 | Bid Multiplier | 对平台出价的百分比增减 | 出价 ×1.15 |
| 归因窗口 | Attribution Window | 转化回溯追认的时间窗口 | 7 天点击 / 1 天浏览 |
| LTV | Lifetime Value | 用户生命周期价值 | 首月 LTV = 9.4 USD |

### 1.4 整体架构与数据流

```
 [上游]                         [UBF 控制面]                        [平台]
业务目标/预算 ──> 统一出价层 ──> 智能出价 Agent ──> 平台适配器 ──> 各平台 API
                    │              │    ▲
                    │              │    │ 效果反馈 (转化/收入/花费)
                    ▼              ▼    │
               统一数据模型      归因闭环 <──────── 平台报表 + 第一方归因
                   │                   ▲
                   ▼                   │
              [下游] 决策引擎 / 报表 / 风控 / 告警
```

一次完整请求的数据流可以拆成 7 个步骤：

1. **意图进入**：上层业务下达统一目标，例如"本周在 US 市场，跨平台总预算 $50k，目标 ROAS ≥ 3.0，节奏均匀"。
2. **目标分解**：UBF 把总预算与 ROAS 目标分解到平台维度（下一章详述分解算法）。
3. **上下文感知**：UBF 从统一数据模型读取历史效果、实时 eCPM、时段、受众人群、LTV 等上下文。
4. **Agent 决策**：智能出价 Agent 决定每个平台、每个 campaign 在本时段的出价目标与出价 multiplier。
5. **归一化出价**：统一出价层把 Agent 决策归一化成各平台原生参数（如 Google 设置 tROAS，Meta 设置 bid strategy + target，TikTok 设置 oCPM 出价上限等）。
6. **平台执行**：平台适配器调用平台 API 应用参数。
7. **闭环反馈**：平台报表 + 第一方归因数据回流，归因闭环更新各平台的效果估计，供 Agent 下一轮决策。

### 1.5 模块划分与职责

| 模块 | 职责 | 关键技术点 |
| --- | --- | --- |
| 统一出价层 (Uniform Bid Layer) | 目标归一化、参数消毒、平台无关的出价意图表达 | Bid Intent 抽象、货币/时区归一化、约束校验 |
| 平台适配器 (Platform Adapter) | 把统一意图翻译成平台原生 API 调用，处理各平台差异 | 适配器模式、重试/限流/熔断封装 |
| 智能出价 Agent (Bidding Agent) | 在约束下做多平台出价决策 | Bandit、Contextual RL、约束求解 |
| 归因闭环 (Attribution Loop) | 跨平台效果的归并与校准 | 泊松回归、贝叶斯更新、去重标识 |
| 统一数据模型 (Unified Data Model) | 跨平台的指标口径统一定义 | 维度/指标建模、幂等、时区一致性 |
| 治理与控制面 (Governance/Control) | 预算闸门、ROAS 硬约束、告警、灰度 | 预算池、熔断闸门、开关 |

### 1.6 关键术语表（跨平台口径）

统一出价框架最先要立的规矩就是"口径统一"。下表列出最容易因口径不一致出问题的指标，以及 UBF 的统一口径定义：

| 指标 | Google 口径 | Meta 口径 | TikTok 口径 | UBF 统一口径 |
| --- | --- | --- | --- | --- |
| 转化 | 转化（google_conversion） | 转化（purchase 事件） | 转化事件 | 以第一方归因表中唯一 conversion_id 去重后的转化数 |
| ROAS | 转化价值 / 花费 | 转化价值 / 花费 | 转化价值 / 花费 | 同左，但价值统一折算为功能货币 |
| 花费 | 花费（Client/Server currency） | 花费 | 花费 | 统一折算为基础货币 USD |
| 展示 | 广告展示 | 展示 | 展示 | 统一为"有效展示"（排除 viewability 过滤差异需声明） |
| 归因窗口 | 默认 30 天（可配） | 默认 7 天点击/1 天浏览 | 默认 7 天 | UBF 统一配置的窗口（如 7d click/1d view）取并集上报 |
| 统计时区 | 账户时区 | 账户时区 | 账户时区 | UBF 统一使用 UTC 或指定业务日历 |

> **经验**：口径统一是比算法更难的事。建议在 UBF 上线前先做一次"跨平台报表口径对齐专项"，把每个平台报表的时区、币种、归因窗口、去重逻辑全部标注清楚，形成口径字典，否则后面的统一数据模型就是"鸡同鸭讲"。

### 1.7 与现有系统的集成

UBF 不是孤岛，它需要与以下系统集成：

```
┌────────────┐   ┌────────────┐   ┌────────────┐   ┌────────────┐
│  预算管理系统 │   │  第一方归因  │   │  LTV/用户数据 │   │  告警/观测   │
│ (budget mgmt)│   │ (attribution)│  │ (LTV/user)  │   │ (monitoring) │
└─────┬──────┘   └─────┬──────┘   └─────┬──────┘   └─────┬──────┘
      │ 预算上限         │ 转化/收入        │ LTV 预测        │ 指标/trace
      ▼                 ▼                 ▼                 ▼
          ┌──────────── 统一出价框架 (UBF) ────────────┐
          │ 统一出价层 → 智能出价Agent → 平台适配器      │
          │               归因闭环                      │
          └───────────────────────────────────────────┘
```

集成点详细说明：

- **预算系统**：UBF 从预算系统读取"预算池"与"预算节奏策略"，并在预算即将耗尽时接收预警，触发降速（pacing down）。
- **第一方归因**：UBF 依赖归因结果判断各平台的"真实贡献"，避免被平台自带归因误导。归因更新应为增量、幂等。
- **LTV 系统**：把收入价值从"短窗口转化价值"升级为"LTV 价值"，供 ROAS 目标和 Agent 收益函数使用。
- **观测系统**：UBF 的每个决策节点都要埋点，观测指标进入 Prometheus/Grafana。

---

## 二、深度原理解析

### 2.1 各平台出价模型横向对比

这是 UBF 的基石：不深刻理解各平台出价模型的工作原理，就无法设计出正确的归一化与适配层。

#### 2.1.1 Google Ads —— Max Performance / H-iMax / vCPM

**vCPM（viewable CPM）** 是 Google 对"可见展示"进行出价与计费的模型。与传统 CPM 不同，vCPM 只对"看得见的展示"计费。广告主可以对可见展示设定出价上限，Google 的拍卖在此基础上运作。

**H-iMax（Hybrid Maximize 系列的混合模式）** 属于 Google 的转化最大化（Maximize Conversions）与目标型出价的演进产品线。H-iMax 的核心思想是"混合"：在最大化转化数的同时，尝试逼近一个目标 CPA/ROAS 约束，它是在 **Maximize Conversions**（无条件最大化）与 **Target CPA/ROAS**（硬性约束优化）之间的一种混合形态，用于最大程度利用预算而又不失控。

**Google Labs 的 bidding 能力要点**：

- **目标 CPA 出价 (tCPA)**：平台为每次拍卖估算 pCVR（预测转化率）与实际转化价值，选择出价使期望成本趋近目标。
- **目标 ROAS 出价 (tROAS)**：平台使用转化价值估算，调整出价使 ROAS 趋近目标。
- **Maximize Conversions**：无显式目标，平台尽力在给定预算内买最多的转化。
- **Maximize Conversion Value**：尽力在预算内最大化转化价值。
- **Enhanced CPC**：人工出价 + 平台自动上调/下调。

Google 出价核心公式（示意）：

```
对于每个拍卖机会 a 和广告 a_i：
    bid(a_i) = 目标eCPM * f(pCTR(a_i), pCVR(a_i), pValue(a_i))
其中：
    f 是 Google 用于把"转化目标"映射到"每次拍卖出价"的调度函数
    出价受到 budget pacing 与 bid ceiling 约束
    pay_price = 次高价 + 0.01（第二价格拍卖，广义第二价格）
```

**H-iMax 的工程直觉**：当平台观察到"ecpm 偏低且预算充足"时，更偏向 maximize；当"ecpm 偏高或接近目标上限"时，更偏向约束目标。它是一种在两个目标面之间平滑游走的策略。广告主通常不改底层公式，而是通过设置 **目标 ROAS / 目标 CPA + 预算** 与 **Devices/Networks 等投放维度** 来间接影响。

#### 2.1.2 Meta（Facebook/Instagram）—— Optimized Bidding + CBO + Advantage+

**Optimized Bidding (OCPM/ODM)**：Meta 的默认出价方式是"优化型出价"，其核心是让 Meta 根据广告目标（转化、链接点击、应用安装等）与预算自动决策出价，尽量在预算内实现最多目标事件。它实际上是一种 **oCPM 类**的模型：广告主不直接对每次展示出价，而是给出目标成本/预算，Meta 按其预估转化率与价值模型来出价，并对成功转化的事件计费。

**CBO（Campaign Budget Optimization，广告系列预算优化）**：Meta 将预算从广告系列(campaign)级别自动在多个 ad set 之间动态分配，让 Meta 的模型决定钱该流向表现更好的 ad set，而非在创建时静态分配。CBO 与"ad set 预算"互斥（在一个 campaign 上二选一）。

**Advantage+（Advantage Plus）**：是 Meta 更进一步的自动优化产品线，例如 **Advantage+ Shopping Campaigns**：把受众定向、创意选择、预算分配、出价全部交给 Meta 自动完成，广告主只需提供素材库、目标 ROAS/CPA 与预算。它的价值主张是"少设参数、多用信号"，依赖 Meta 强大的模型与足够的转化数据。

**Meta 出价核心机制**：

```
对于每个 auction (bid request)：
    Meta 内部用 "value-based + 概率" 模型估算：
        pConversion(广告, 用户, 上下文)
    "目标ROAS型出价"：
        出价目的：使每花费 1 元产生的转化价值 ≥ 目标ROAS
        平台据此决定是否参与该竞拍及出价额度
    "目标CPA型出价" / "最低成本" / "最高价值" 由 campaign 目标决定
```

Meta 与 Google 的显著差异：

| 维度 | Google Ads | Meta Ads |
| --- | --- | --- |
| 主要出价族 | maximize / tCPA / tROAS / vCPM | 优化型出价 (最低成本/目标成本/最高价值/目标ROAS) |
| 预算层级 | campaign 预算为主 | CBO 在 campaign 层自动分配 ad set |
| 受众定向 | 关键词 + 受众 | 受众受众（lookalike/custom audience）+ Advantage+ |
| 价值信号 | 转化价值、客单价 | 转化价值 + App 内/站内价值信号 |
| 出价表达 | tROAS / tCPA 数值 | 目标ROAS / 目标成本 数值 |
| 自动程度 | 中 | 高（Advantage+ 更高） |

#### 2.1.3 TikTok Ads —— oCPM

**oCPM（Optimized Cost per Mille）** 是 TikTok 的核心出价模型，全称是"优化型千次展示成本"。它的工作方式是：广告主设定一个"目标成本"（通常是目标 CPA 或目标长尾转化成本），TikTok 通过实时预估每个用户的转化概率，把出价集中在"可能转化的用户"上，以实现目标成本。

**oCPM 的计费含义**：虽然名字里有"每千次展示"，但 oCPM 是 **按目标行动（conversion/install）为导向的优化出价**，账单上以展示计费（实际以 CPM 展示计费、按点击/转化优化）。

**TikTok 出价要点**：

```
oCPM 工作流：
1. 广告主设目标成本（如目标 CPA = 20 元，或目标安装成本）。
2. TikTok 实时算每个用户的 pAction（转化概率）。
3. 系统在保留预算节奏的前提下，把出价分配给高 pAction 用户。
4. 计费按展示、优化按行动。
也支持 tCPA / tROAS（部分地区/目标），以及智能竞价 (Smart+ / Complete) 
与 Manual 出价模式。
```

值得注意的趋势：TikTok 也在推出 **Smart+（TikTok 的全自动投放方案）**，类比 Meta 的 Advantage+，把受众、创意、出价全部自动优化，同时提供目标 ROAS 目标。

#### 2.1.4 DV360（Display & Video 360）—— Target CPM / Custom Bidding

DV360 是 Google 的 DSP（Demand-Side Platform，需求方平台），主要服务品牌投放、程序化广告、RTB（实时竞价），对广告主暴露出价控制的程度比 Meta/TikTok 更高。

**Target CPM (目标 CPM)**：广告主为一次展示机会设定愿意支付的目标 eCPM。DV360 在脚动 CPM 与完全自动之间提供 **目标 CPM 模式**，让 DSC 用机器学习在拍卖中尽量接近该目标 CPM 达成购买，同时允许设置 **最大 CPM（Max CPM）** 硬上限。

**Custom Bidding（自定义出价）**：DV360 最强大的出价能力之一，允许广告主上传 **自定义信号（custom bidding signals）**，并在 DV360 中定义 **一定的目标**（如"最大化某自定义指标"或"在约束下最大化价值"），平台综合你的自定义信号与目标模型来生成出价。它实际上是"广告主自行提供价值信号 + DV360 负责拍卖出价执行"。

**手动出价 / 固定出价**：DV360 也支持纯粹的手动 CPM 出价（脚动 C价）用于品牌、KPI 兼容等稳定投放。

DV360 出价核心：

```
RTB 环境下，对每个 exchange 的 bid request：
    出价 = f(自定义信号, 目标, 上下文)
    DV360 既可能是第一价格也可能是第二价格拍卖（受制于 exchange）
    Max CPM 为硬约束；Target CPM 为软目标
    Custom Bidding 允许广告主以 first-party 信号驱动出价
```

#### 2.1.5 四平台横向对比总表

| 维度 | Google Ads | Meta Ads | TikTok Ads | DV360 |
| --- | --- | --- | --- | --- |
| 主要出价模型 | Max(h-iMax)/tCPA/tROAS/vCPM | Optimized Bidding (OCPM/ODM) + CBO + Advantage+ | oCPM (+tCPA/tROAS, Smart+) | Target CPM / Max CPM / Custom Bidding / Manual |
| 出价决策层级 | keyword/ad group/campaign | campaign (CBO) → ad set | campaign/ad group | line item |
| 预算自动化 | campaign 预算（支持 pacing） | CBO 自动分配 ad set 预算 | 预算 + 智能分配 | line item budget / flight pacing |
| 出价表达物 | tROAS/tCPA 数值、目标 eCPM | 目标成本/目标ROAS/最低成本/最高价值 | 目标 CPA/tROAS、成本上限 | 目标 CPM、Max CPM、Custom 目标 |
| 用户价值信号 | 转化价值、客单价、第一方转化 | App 内/站内转化价值 | 转化事件、价值 | 自定义 bidding signals |
| 拍卖类型 | 第二价格为主 | 内部拍卖 | 内部拍卖/竞价 | RTB，第一/第二价格混合 |
| 自动化程度 | 中高 | 高（Advantage+） | 高（Smart+） | 中（自定义程度高） |
| 受众/创意自动 | 有限 | Advantage+ 高自动 | Smart+ 高自动 | 手动为主、可自定义 |
| 对广告主的出价透明度 | 中 | 低 | 中 | 高 |
| 计费基准 | 可见展示/点击/转化 | 展示/转化 | 展示(优化按行动) | 展示(CPM 为主) |
| 典型 KPI | ROAS/CPA/Install | ROAS/CPA | CPA/ROAS/Install | 品牌触达/CPM/CTR |

> **关键洞察**：四个平台共同点是"都朝着 oCPM/价值驱动出价演进，平台内部都用机器学习预测转化概率并据此出价"。差异在于：**表达层级**（keyword vs ad set vs ad group vs line item）、**预算自动化程度**（CBO/Advantage+/Smart+ vs 手动）、**出价透明度**（DV360 最透明）、以及 **价值信号来源**（平台内 vs 自定义）。UBF 必须同时驾驭"平台自动出价"与"广告主旁路微调"两种模式。

#### 2.1.6 各平台出价"目标映射"速查

UBF 在做归一化时，需要一张"统一目标 → 各平台原生参数"的映射表：

| 统一意图 | Google 参数 | Meta 参数 | TikTok 参数 | DV360 参数 |
| --- | --- | --- | --- | --- |
| 目标 ROAS = R | campaign 目标 ROAS | Advantage+CBO target_roas / bid strategy{TARGET_ROAS, ROAS} | 目标 ROAS（若支持） | Custom Bidding 目标 ROAS |
| 目标 CPA = C | 目标 CPA | 目标成本（CPA） | 目标 CPA（oCPM） | 目标 CPA 类 custom |
| 最大化价值 | Maximize Conversion Value | 最高价值 | 最高价值 (Maximize) | Custom bidding 最大化价值 |
| 最大化转化 | Maximize Conversions | 最低成本（最大转化量） | 最大限度转化 | 最大化转化 custom |
| CPM 品牌触达 | vCPM | 展示量/目标 | 展示量 | 目标 CPM / Max CPM |
| 旁路微调 | bid multiplier (部分产品) | （有限） | bid 提升/成本上限 | bid multiplier |

> **注意**：此表是"逻辑映射"，具体 API 字段名、可用性、地区差异需要以各平台的当期 API 文档为准。UBF 的适配器应在配置中维护这张映射表，并支持白名单校验。

### 2.2 统一出价层设计

#### 2.2.1 设计目标与非目标

**目标**：
- 平台无关的**出价意图**表达（Bid Intent）。
- 参数**归一化**：货币、时区、目标、约束统一。
- 一个清晰的**统一数据模型**（Unified Data Model）承载结果。
- 可插拔的**适配器**，新增平台不污染核心逻辑。

**非目标**：
- 不试图抽象掉平台的全部差异（不可能也不必要）。
- 不复制平台内部拍卖逻辑。
- 不在这一层做效果优化（那属于 Agent 层）。

#### 2.2.2 Bid Intent（统一出价意图）抽象

统一出价层用一个 **BidIntent** 结构体承载"这次要干嘛"。它必须是平台无关的、自描述的、强类型的。

```
BidIntent {
    action:      MAXIMIZE_VALUE | MAXIMIZE_CONVERSIONS | TARGET_ROAS
                 | TARGET_CPA | TARGET_CPM | TARGET_CPC
    target:      <数值，含义由 action 决定>        // 例 ROAS=3.0, CPA=18
    budget: {
        amount:   <金额>
        currency: USD
        period:   DAILY | TOTAL
        pacing:   EVEN | FRONT_LOADED | BACK_LOADED | DAYPART
    }
    constraints: {
        max_cpm:     <数值>
        max_cpa:     <数值>
        min_roas:    <数值>        // 硬约束
        flight_dates:[start, end]
        geo_whitelist / geo_blacklist
        spend_cap:   <数值>        // 平台级闸门
    }
    adjustment: {
        bid_multiplier: 1.15        // 旁路微调，默认 1.0
        multiplier_window: [0, 23]  // 可按时段
    }
    metadata: {
        campaign_id / ad_group_id / line_item_id 引用
        source: "<归属的决策来源>"
        seek: "<时间戳>"
    }
}
```

#### 2.2.3 参数归一化

**（1）货币归一化**：UBF 内部统一使用基础货币（Base Currency，如 USD），所有平台报表与出价参数在进入统一数据模型前先按当日汇率折算。

```
汇率处理原则：
- 出价指令向下到达平台时，使用"出价货币"（平台原生币种）。
- 指标向上聚合时，使用"功能货币"（UBF 统一币种）。
- 汇率使用交易日收盘价快照，避免盘中波动造成口径抖动。
- 同一时刻只允许一个汇率版本，保证前后可对账。
```

**（2）时区归一化**：平台账户各有其时区。UBF 统一使用 UTC 存储事件，并在展示/聚合时使用业务日历换算。

```
事件存储：一律 UTC（时间戳带 UTC 标注）。
业务聚合：按业务所在时区（如 US-Pacific / 中国 GMT+8）切日。
出价节奏：折算为平台账户时区的当地时间，避免"跨日切预算"失控。
```

**（3）目标归一化**：把上层"业务语言目标"归一化为平台原生目标值。例如：

```
业务目标 ROAS = 3.0  →  各平台原生目标映射：
   Google:          campaign 级 target_roas = 3.0（货币已归一）
   Meta:            bid strategy target ROAS = 3.0（若支持）
   TikTok:          目标 ROAS = 3.0（若支持）
   DV360:           Custom Bidding 目标值（按价值单位归一）
归一化器还需执行值域校验：
   ROAS ∈ [0.1, 20]；CPA ≥ 0；CPM ≥ 0；multiplier ∈ [0.5, 3.0]
```

**（4）约束归一化**：把统一的约束（max_cpm、预算节奏）翻译成各平台的约束表达（可能需要捏合多个 API 参数）。

```
统一约束 → 平台约束示例：
  max_cpm = 8 USD →
      Google: 部分产品设出价上限；否则仅作为内部 Advice
      Meta:   预算/成本相关, max 可能通过 bid cap 表达（若该产品支持）
      TikTok: 出价上限（bid cap / cost cap）
      DV360:  max_cpm 原生支持
约束无法表达时，适配器应在结果状态里打 WARN，并降级为软约束。
```

#### 2.2.4 统一数据模型（Unified Data Model）

统一数据模型定义跨平台结果的"统一行结构"。核心是 **fact/metric 与 dimension 分离**，并保证幂等与可对账。

```
UnifiedReportRow {
    platform:        GOOGLE | META | TIKTOK | DV360
    campaign_external_id: <各平台 campaigns 的外部 ID 或 UBF 统一键>
    dims: {
        date:        YYYY-MM-DD (UTC)
        country:     US
        campaign_type: ...
        device:      iOS | Android | Web
        ...
    }
    metrics: {
        impressions:    45000
        viewable_impressions: 41000
        clicks:          780
        ctr:             0.0173
        cost:            642.5          // 统一货币
        conversions:     35             // 第一方去重后转化
        conversion_value: 1927.0        // 统一价值
        roas: 3.0
        ...
    }
    confidence: { /* 归因置信度，见归因闭环章节 */ }
    _meta: {
        currency: USD
        timezone: UTC
        source_report_id: <平台报表导出批次的幂等键>
        updated_at: <时间戳>
    }
}
```

**幂等设计**：每个平台报表批次都要有唯一的 `source_report_id`，UBF 使用它做 upsert（插入或更新），重复拉取同一批次不会产生脏数据。写入统一数据仓库（如 BigQuery / ClickHouse）时使用 `platform + source_report_id + dims` 作为去重键。

#### 2.2.5 跨平台 Bid API 接口设计

设计一套平台无关的 Bid API，供上层与 Agent 调用。下面用 **Go interface、Python ABC、以及 JSON Schema** 三份展示同一契约。

##### Go 接口

```go
// bid.go —— 统一出价层接口

package ubid

import "context"

// Action 出价动作类型
type Action string

const (
	ActionMaximizeValue      Action = "MAXIMIZE_VALUE"
	ActionMaximizeConversions Action = "MAXIMIZE_CONVERSIONS"
	ActionTargetROAS         Action = "TARGET_ROAS"
	ActionTargetCPA          Action = "TARGET_CPA"
	ActionTargetCPM          Action = "TARGET_CPM"
	ActionManualCPM          Action = "MANUAL_CPM"
)

// Money 归一化金额
type Money struct {
	Amount   float64 `json:"amount"`
	Currency string  `json:"currency"` // 统一为 ISO 4217
}

// Budget 预算节奏
type Budget struct {
	Amount Money   `json:"amount"`
	Period string  `json:"period"` // DAILY | TOTAL
	Pacing string  `json:"pacing"` // EVEN | FRONT_LOADED | BACK_LOADED
}

// BidIntent 平台无关的出价意图（见上文结构）
type BidIntent struct {
	Action      Action        `json:"action"`
	Target      float64       `json:"target"`
	Budget      Budget        `json:"budget"`
	MaxCPM      *float64      `json:"max_cpm,omitempty"`
	MinROAS     *float64      `json:"min_roas,omitempty"`
	Multiplier  float64       `json:"bid_multiplier,omitempty"`
	CampaignRef string        `json:"campaign_ref"` // UBF 统一 campaign 键
}

// ApplyResult 应用结果
type ApplyResult struct {
	OK        bool              `json:"ok"`
	Status    string            `json:"status"` // APPLIED | WARN | REJECTED
	Warnings  []string          `json:"warnings,omitempty"`
	AppliedAt string            `json:"applied_at"`
	PlatformParams map[string]any `json:"platform_params,omitempty"`
}

// PlatformAdapter 每个平台适配器都实现此接口
type PlatformAdapter interface {
	// Apply 把统一出价意图应用到平台
	Apply(ctx context.Context, intent *BidIntent) (*ApplyResult, error)
}

// Registry 适配器注册表
type Registry struct{ adapters map[string]PlatformAdapter }

func (r *Registry) Register(platform string, a PlatformAdapter) {
	r.adapters[platform] = a
}

func (r *Registry) Get(platform string) (PlatformAdapter, bool) {
	a, ok := r.adapters[platform]
	return a, ok
}
```

##### Python 抽象基类

```python
# bid.py —— 统一出价层接口 (Python)
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, Any


class Action(str, Enum):
    MAXIMIZE_VALUE = "MAXIMIZE_VALUE"
    MAXIMIZE_CONVERSIONS = "MAXIMIZE_CONVERSIONS"
    TARGET_ROAS = "TARGET_ROAS"
    TARGET_CPA = "TARGET_CPA"
    TARGET_CPM = "TARGET_CPM"
    MANUAL_CPM = "MANUAL_CPM"


@dataclass
class Money:
    amount: float
    currency: str = "USD"


@dataclass
class Budget:
    amount: Money
    period: str = "DAILY"     # DAILY | TOTAL
    pacing: str = "EVEN"      # EVEN | FRONT_LOADED | BACK_LOADED


@dataclass
class BidIntent:
    action: Action
    target: float
    budget: Budget
    max_cpm: Optional[float] = None
    min_roas: Optional[float] = None
    bid_multiplier: float = 1.0
    campaign_ref: str = ""
    extras: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ApplyResult:
    ok: bool
    status: str               # APPLIED | WARN | REJECTED
    warnings: list = field(default_factory=list)
    applied_at: str = ""
    platform_params: Dict[str, Any] = field(default_factory=dict)


class PlatformAdapter(ABC):
    """每个平台适配器的统一契约。"""

    @abstractmethod
    async def apply(self, intent: BidIntent) -> ApplyResult:
        ...

    @property
    @abstractmethod
    def platform_name(self) -> str:
        ...
```

##### JSON Schema（请求契约）

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://ubf.example/bid-intent.schema.json",
  "title": "BidIntent",
  "type": "object",
  "required": ["action", "target", "budget", "campaign_ref"],
  "properties": {
    "action": {
      "type": "string",
      "enum": [
        "MAXIMIZE_VALUE", "MAXIMIZE_CONVERSIONS",
        "TARGET_ROAS", "TARGET_CPA", "TARGET_CPM", "MANUAL_CPM"
      ]
    },
    "target": { "type": "number", "minimum": 0 },
    "budget": {
      "type": "object",
      "required": ["amount"],
      "properties": {
        "amount": {
          "type": "object",
          "required": ["amount", "currency"],
          "properties": {
            "amount": { "type": "number", "minimum": 0 },
            "currency": { "type": "string", "minLength": 3, "maxLength": 3 }
          }
        },
        "period": { "type": "string", "enum": ["DAILY", "TOTAL"] },
        "pacing": { "type": "string", "enum": ["EVEN", "FRONT_LOADED", "BACK_LOADED"] }
      }
    },
    "max_cpm": { "type": "number", "minimum": 0 },
    "min_roas": { "type": "number", "minimum": 0 },
    "bid_multiplier": { "type": "number", "minimum": 0.5, "maximum": 3.0 },
    "campaign_ref": { "type": "string" }
  }
}
```

#### 2.2.6 适配器实现要点（以 Meta 为例）

以 Meta 适配器为例展示"统一意图 → 原生 API 参数"的翻译：

```python
# adapters/meta.py
from .base import PlatformAdapter, BidIntent, ApplyResult, Action


class MetaAdapter(PlatformAdapter):
    platform_name = "META"

    def __init__(self, api_client):
        self.api = api_client

    async def apply(self, intent: BidIntent) -> ApplyResult:
        # 1. 翻译 action -> Meta bid strategy / optimization goal
        if intent.action == Action.TARGET_ROAS:
            strategy = {"bid_strategy": "BID_STRATEGY_LOWEST_COST_WITHOUT_CAP"}
            # 若平台支持 target ROAS：
            # strategy = {"bid_strategy": "BID_STRATEGY_TARGET_ROAS",
            #             "target_roas": intent.target}
            payload = {
                "campaign_id": intent.campaign_ref,
                "bid_strategy": strategy.get("bid_strategy"),
            }
        elif intent.action == Action.TARGET_CPA:
            payload = {
                "campaign_id": intent.campaign_ref,
                "bid_strategy": "BID_STRATEGY_LOWEST_COST_WITH_BID_CAP",
                "bid_cap": {"value": intent.target, "currency": "USD"},
            }
        elif intent.action == Action.MAXIMIZE_CONVERSIONS:
            payload = {
                "campaign_id": intent.campaign_ref,
                "bid_strategy": "BID_STRATEGY_LOWEST_COST_WITHOUT_CAP",
            }
        else:
            return ApplyResult(ok=False, status="REJECTED",
                               warnings=[f"unsupported action {intent.action}"])

        # Meta 的 bid multiplier 支持有限，这里做 WARN 提示
        warnings = []
        if intent.bid_multiplier != 1.0:
            warnings.append("Meta does not expose bid multiplier; ignored")

        resp = await self.api.ads_pacing_update(**payload)
        if not resp.get("success"):
            return ApplyResult(ok=False, status="REJECTED",
                               warnings=["api error"] + warnings)
        return ApplyResult(ok=True, status="APPLIED",
                           warnings=warnings,
                           platform_params=payload)
```

#### 2.2.7 适配器的防御性设计

统一出价层在调用平台 API 时必须做防御：

1. **白名单校验**：在翻译前校验 `intent.action` 是否是该平台支持的动作。
2. **值域校验**：`target`、`budget`、`bid_multiplier` 必须在合理区间。
3. **降级策略**：当平台不支持某个约束时，返回 `WARN` 而非 `REJECTED`（除非是硬约束）。
4. **幂等键**：每个 `Apply` 请求携带 `applied_at` 与请求指纹，重复调用避免重复设置。
5. **错误分类**：把平台 API 错误分为"可重试（限流/超时）"、"不可重试（参数错误）"、"需人工（权限/审核）"三类。

```
错误分类示例：
  429 限流                -> 可重试（指数退避）
  5xx 服务端错误          -> 可重试（短退避）
  timeout                -> 可重试（谨慎）
  400 参数错误            -> 不可重试，回查归一化器
  403 权限/授权           -> 需人工
  DISABLED / 广告被拒     -> 需人工
```

### 2.3 智能出价 Agent 架构

统一出价层负责"翻译与执行"，而**智能出价 Agent** 负责"决策"：在跨平台、跨预算、跨时间、含约束的场景下，决定给每个平台/campaign 出什么样的目标与出价。这是 UBF 的大脑。

#### 2.3.1 Agent 的输入 / 输出

```
输入（上下文 / Context）：
  - 各平台当前效果估计（eCPM、CPA、ROAS，来自归因闭环）
  - 各平台可用预算与剩余预算、节奏进度
  - 时段 / 日期 / 季节 / 事件（促销、上新）
  - 受众与用户价值（LTV / 首日 ROAS）
  - 全局约束（总预算、总 ROAS 硬下限、风控规则）

输出（决策 / Decision）：
  - 每个平台、每个 campaign 的出价目标（tROAS / tCPA / multiplier）
  - 预算在平台间的分配比例
  - 是否暂停 / 降速 / 提价某个 campaign
  - 每个决策附带的置信度与原因
```

#### 2.3.2 决策问题的数学建模

把跨平台出价建模成**带约束的在线决策**问题。为简化，先定义：

- 时段 $t \in \{1, \dots, T\}$（例如每小时或每日）。
- 平台/行动集合 $\mathcal{A} = \{a_1, \dots, a_K\}$（K 个 platform-campaign 组合）。
- 每个行动的未知价值 $r_t(a)$（例如该行动在时段 t 的边际 ROAS）。
- 每个行动的未知代价 $c_t(a)$（该行动在时段 t 的边际 eCPM 或 CPA）。
- 总预算约束 $B$，目标 ROAS 下限 $R_{min}$。

目标：在预算与 ROAS 约束下，选择在何时、把多少预算分配到哪个行动，以最大化总价值（收入或 LTV）。

```
maximize    Σ_t Σ_a  value_t(a)
subject to  Σ_t Σ_a  cost_t(a)  ≤ B          (预算约束)
            ROAS_total ≥ R_min               (ROAS 硬约束)
            per-platform pacing 约束 / cap
```

由于 `value_t(a)` 和 `cost_t(a)` 都是**未知且动态变化**的，这正是一个 **Contextual Multi-Armed Bandit with Constraints (CMAB-C)** 问题。Agent 既要在"探索（exploration）"与"利用（exploitation）"之间权衡，又要满足预算与 ROAS 约束。

#### 2.3.3 从 Multi-Armed Bandit 开始

**Multi-Armed Bandit（MAB）** 是最基础的在线决策框架：K 台老虎机（K 个行动），每次拉一个，得到随机奖励，目标是最大化累计奖励。

**UCB1（Upper Confidence Bound）** 是经典 MAB 算法：

- 为每个行动维护经验均值 $\hat{\mu}_a$ 与选择次数 $n_a$。
- 每个行动的 UCB 值：$\bar{x}_a + c \sqrt{\frac{\ln N}{n_a}}$
  其中 $N = \sum_a n_a$ 为总选择次数，$c$ 为探索常数。
- 每轮选择 UCB 值最大的行动。

**UCB1 伪代码**：

```
输入：行动数 K，探索常数 c
初始化：每个行动 a 选择次数 n_a = 0，累计奖励 S_a = 0
for t = 1, 2, ...:
    若存在 n_a == 0 的行动：选择它（保证每个都试一次）
    否则：
        N = sum(n_a)
        msg_a = S_a/n_a + c * sqrt(ln(N) / n_a)   // 上置信界
        选择 a* = argmax_a msg_a
        观察奖励 r_t
        n_{a*} += 1 ;  S_{a*} += r_t
```

**UCB1 Go 实现**：

```go
package bandit

import "math"

// UCB1 经典多臂老虎机
type UCB1 struct {
	counts        []float64 // 每个臂被选择的次数
	rewards       []float64 // 每个臂累计奖励
	exploration   float64   // c 常数
	arms          int
}

func NewUCB1(arms int, c float64) *UCB1 {
	return &UCB1{
		counts:      make([]float64, arms),
		rewards:     make([]float64, arms),
		exploration: c,
		arms:        arms,
	}
}

// Select 返回本轮应选择的臂下标
func (u *UCB1) Select() int {
	// 每个臂先试一次：arm exploration
	for i := 0; i < u.arms; i++ {
		if u.counts[i] == 0 {
			return i
		}
	}
	total := 0.0
	for _, n := range u.counts {
		total += n
	}
	logN := math.Log(total)
	best, bestVal := -1, math.Inf(-1)
	for i := 0; i < u.arms; i++ {
		mean := u.rewards[i] / u.counts[i]
		ucb := mean + u.exploration*math.Sqrt(logN/u.counts[i])
		if ucb > bestVal {
			bestVal = ucb
			best = i
		}
	}
	return best
}

// Update 记录选择 arm 后的实际奖励
func (u *UCB1) Update(arm int, reward float64) {
	u.counts[arm]++
	u.rewards[arm] += reward
}
```

**复杂度分析**：
- 时间：每轮选择为 $O(K)$，更新为 $O(1)$。
- 空间：$O(K)$。
- 遗憾上界：UCB1 的累积遗憾期望为 $O(\sqrt{K N \ln N})$，其中 N 为轮数。

**对广告场景的直觉**：把"每个平台-campaign"当作一只臂，奖励可以是"该行动本时段的边际 ROAS"或"每预算单位的转化价值"。UCB 会自然地把预算导向"上置信界最高"的行动——既照顾了还不确定的高潜力行动（探索），也压住表现差的行动（利用）。但 UCB1 是**非上下文（non-contextual）**的，它不利用时段、受众等特征，所以广告出价更常用下一节的 contextual bandit。

#### 2.3.4 Contextual Multi-Armed Bandit（上下文多臂老虎机）

Contextual Bandit 每个轮次都有**上下文特征 $x_t$**（时段、国家、设备、ecpm、剩余预算比...），奖励分布 $r_t(a|x_t)$ 依赖上下文。算法要学一个"特征 → 行动价值"的映射。

**LinUCB（Linear UCB）** 是最常用的 ctx bandit 之一：假设每个行动 a 的价值是特征的线性函数 $r_a(x) = \theta_a^T x$，用岭回归（Ridge Regression）估计参数并给出上置信界。

**LinUCB 核心公式**：

```
对行动 a 维护：
    A_a = X_a^T X_a + λ I   (d×d 矩阵，X_a 为行动 a 已见特征)
    b_a = X_a^T y_a         (d 维向量，y_a 为对应奖励)
    参数估计 θ_a = A_a^{-1} b_a
    上置信界：p_a(x) = θ_a^T x + α sqrt(x^T A_a^{-1} x)
每轮选择 p_a(x) 最大的行动
```

**LinUCB 伪代码**：

```
输入：行动数 K，特征维度 d，正则 λ，置信参数 α
初始化：A_a = λI, b_a = 0, 对每个 a
for t = 1, 2, ...:
    观察上下文 x_t ∈ R^d
    for each a:
        θ_a = A_a^{-1} b_a
        p_a = θ_a^T x_t + α * sqrt(x_t^T A_a^{-1} x_t)
    选择 a* = argmax_a p_a
    执行 a*，观察奖励 r_t
    A_{a*} += x_t x_t^T
    b_{a*} += r_t x_t
```

**LinUCB Python 实现**：

```python
import numpy as np


class LinUCB:
    """Contextual linear bandit (LinUCB / disjoint model)."""

    def __init__(self, num_arms: int, dim: int, alpha: float = 0.3,
                 lam: float = 1.0, rng: np.random.Generator = None):
        self.K = num_arms
        self.d = dim
        self.alpha = alpha
        self.lam = lam
        self.rng = rng or np.random.default_rng()
        # 每个臂的 A 矩阵与 b 向量
        self.A = [lam * np.eye(dim) for _ in range(num_arms)]
        self.b = [np.zeros(dim) for _ in range(num_arms)]

    def select(self, x: np.ndarray) -> int:
        p = np.zeros(self.K)
        for a in range(self.K):
            Aa, ba = self.A[a], self.b[a]
            theta_a = np.linalg.solve(Aa, ba)          # A^{-1} b
            mean = theta_a @ x
            # x^T A^{-1} x
            unc = self.alpha * np.sqrt(x @ np.linalg.solve(Aa, x))
            p[a] = mean + unc
        return int(np.argmax(p))

    def update(self, a: int, x: np.ndarray, reward: float):
        Aa, ba = self.A[a], self.b[a]
        self.A[a] = Aa + np.outer(x, x)
        self.b[a] = ba + reward * x
```

**复杂度**：
- 每次选择需要逆矩阵 $A_a^{-1}$，直接求逆为 $O(d^3)$，K 个臂为 $O(K d^3)$。可优化：用 **Sherman-Morrison 公式**增量更新 $A^{-1}$，把单臂更新降到 $O(d^2)$；或用卡尔曼式流式估计。
- 实际广告系统 d 通常几十到几百，$O(K d^2)$ 的增量版本可在毫秒级完成，足够放在每次决策回路里（不是每次展示，而是每时段每 campaign 决策）。

**广告场景映射**：

```
上下文 x_t 示例：
  [剩余预算比例, 当前eCPM, 预测CTR, 时段特征(one-hot), 国家, 设备,
   近7日ROAS, 距活动开始小时数, ...]

行动 set：
  每个"平台 × 目标档位 × campaign" 组合当一个 ctx-bandit 臂；
  或把"目标 ROAS 档位"当臂（例如 ROAS∈{2.0,2.5,3.0,3.5}）让 Agent 学哪个档位好

奖励：
  边际转化价值 / 花费（即本时段 ROAS）
  或 归一化的 LTV 增量
```

#### 2.3.5 从 Bandit 到深度强化学习（DRL）

当状态空间很大、动作连续（例如"任意 ROAS 出价值"）、且需要长期收益（把今日的好效果留到明日）时，Bandit 的独立轮次假设就不够了，需要**强化学习**。

**术语对照**（RL ↔ 出价）：

| RL 术语 | 出价场景含义 |
| --- | --- |
| State $s_t$ | 当前投放状态：预算剩余、时间、各平台效果、受众上下文 |
| Action $a_t$ | 本时段每个平台/campaign 的出价目标（ROAS/CPA/multiplier）、预算分配 |
| Reward $r_t$ | 本时段获得的转化价值 / LTV（扣减成本） |
| Policy $\pi(a\|s)$ | 给定状态选择出价动作的策略 |
| Value $Q(s,a)$ | 状态-动作价值：长期期望回报 |
| Discount $\gamma$ | 对未来收益的折扣（出价常设为接近 1 或按预算周期） |

**（A）DQN（Deep Q-Network）**——价值型方法，适合**有限/离散动作**。

DQN 用神经网络近似 $Q(s,a)$，通过贝尔曼更新训练：

```
Q 学习更新目标：
    Q(s_t, a_t) ← Q(s_t, a_t)
        + α [ r_t + γ max_{a'} Q(s_{t+1}, a') − Q(s_t, a_t) ]

DQN 三点工程技巧：
1. 经验回放 (Experience Replay)：从记忆缓冲随机采样，打破时间相关性。
2. 目标网络 (Target Network)：用另一份延迟更新的 Q 网络计算 TD 目标，稳定训练。
3. ε-greedy 探索：以概率 ε 随机选动作，其余按 Q 值贪心。
```

**（B）PPO（Proximal Policy Optimization）**——策略梯度方法，支持**连续动作**，更适合出价。

PPO 的目标函数（裁剪版 surrogate objective）：

```
L^{CLIP}(θ) = E_t[ min( r_t(θ) A_t ,
                        clip(r_t(θ), 1−ε, 1+ε) A_t ) ]

其中：
    r_t(θ) = π_θ(a_t|s_t) / π_old(a_t|s_t)      // 新旧策略概率比
    A_t    为优势函数估计（如 GAE）
    ε      为裁剪系数（通常 0.2）
clip 项防止策略一次更新过大，保证训练稳定。
```

**从 Bandit 到 RL 的选型建议**：

| 场景 | 推荐 | 理由 |
| --- | --- | --- |
| 冷启动、数据少、行动少 | UCB1 / Thompson | 简单高效、无需特征 |
| 有上下文特征、行动有限 | LinUCB | 利用特征、可解释 |
| 状态/行动空间大、动作离散 | DQN | 近似价值函数 |
| 动作连续、需要稳定策略 | PPO / 基于策略 | 连续 ROAS 出价值 |
| 需严格预算/ROAS 约束 | CMAB-C / 带约束 RL（后述） | 硬约束 |

> **工程提醒**：DRL 在真实广告出价里比论文里难得多——数据分布偏移、奖励稀疏、延迟归因、离线评估困难。实战上**强烈建议从 Bandit 起步**，用 Contextual Bandit + 约束层解决 80% 的需求，只有当你确实需要"连续出价值 + 长期依赖"时才引入 DQN/PPO，且必须做好 offline evaluation（见 2.3.9）。

#### 2.3.6 带约束的多臂老虎机（Bandit with Constraints）

纯 bandit / RL 只优化"累计奖励"，但广告出价有**硬约束**：预算不能超出、ROAS 不能低于下限、单平台花费不能失衡。需要 **Constrained Bandit / CMAB-C**。

**约束处理的两层结构**：

```
┌─────────────────────────────────────────────┐
│ 无约束的 Bandit / RL 决策                     │
│   → 输出"理想分配" / "理想出价"                │
└────────────────────┬────────────────────────┘
                     ▼
┌─────────────────────────────────────────────┐
│ 约束求解层 (Constraint Enforcer)             │
│   · 预算投影 (Budget Projection)             │
│   · ROAS 下限投影                            │
│   · 平台花费 cap 投影                         │
│   → 输出"可行解"，再转成出价指令               │
└─────────────────────────────────────────────┘
```

**核心思想（Lagrangian / 投影法）**：把约束写成惩罚项或对偶变量，或者直接做"可行域投影"。

**方法一：拉格朗日法（Lagrangian / primal-dual）**：

```
最大化总价值：
    max Σ_t Σ_a value_t(a)
受约束于：
    Σ cost ≤ B  ； ROAS 总 ≥ Rmin

构造拉格朗日：
    L = Σ value_t(a) − λ (Σ cost_t(a) − B)
        − μ (Rmin − Σ value_t(a)/Σ cost_t(a) 的线性化)

对偶变量更新（在线梯度）：
    λ ← max(0, λ + η (Σ cost − B))        // 预算违反时升λ，惩罚"贵"的行动
    μ ← max(0, μ + η (Rmin − ROAS))       // ROAS 不达标时升μ，惩罚ROAS低的行动

每轮选择"净价值"最大的行动：
    a* = argmax_a [ value_t(a) − λ·cost_t(a) − μ·(Rmin_相关项) ]
```

这个方法的直觉非常优雅：**当预算告急（cost 超B）就提高 λ，让"贵"的行动变得不划算；当 ROAS 低于下限就提高 μ，让"低ROAS"的行动被惩罚**。λ、μ 就是"市场定价的隐式出价调整"。

**方法二：预算投影（Budget Projection / Knapsack 近似）**：

若已估计出每个行动的**期望单位成本**与**单位价值**，预算分配变成了"分数背包问题"的在线版本：按"单位价值的性价比（每花 1 元产生的价值）"从高到低分配，直到预算用完。

```
性价比排序分配：
1. 对每个行动估计：value_per_dollar_a = 边际价值 / 边际成本
2. 按 value_per_dollar 降序排列行动
3. 从性价比最高的行动开始分配预算，直到总预算 B 耗尽
4. 边界行动按剩余预算做比例分配（分数背包）
5. 每时段用实际反馈修正 value_per_dollar 估计（self-correcting，见2.4）
```

**带约束的 UCB（Constrained UCB）伪代码**：

```
输入：预算 B，ROAS 下限 Rmin，成本/价值区间估计
for t = 1, 2, ...:
    观察上下文与剩余预算 B_t
    计算各行动'无约束UCB估值' v_a（如 LinUCB 的上置信界）
    计算各行动'期望成本' uc_a（eCPM 估计）
    # 拉格朗日修正
    λ_t 由预算违约深度决定；μ_t 由ROAS违约深度决定
    净价值 g_a = v_a − λ_t·uc_a − μ_t·(roas_penalty_a)
    选择满足可行集的行 a* = argmax g_a
    观察奖励与成本，更新各行动统计
    更新 λ_t, μ_t（在线梯度/对偶上升）
```

**工程上约束层的安全性保证**：
- **预算闸门**：在执行任何平台出价变更前，检查平台级 spend_cap 与全局预算剩余，超限则拒绝（保守优先）。
- **ROAS 硬下限**：min_roas 被设为硬约束；若多数行动在可行 ROAS 下无解，优先"降低出价/缩量"而非"突破 ROAS 下限"。
- **降速规则**：当预算消耗过快（pacing ahead），对 multiplier 施加向下的线性衰减，或切换到更低目标档位。

#### 2.3.7 Agent 决策伪代码（综合版）

把 2.3.3~2.3.6 综合成一个可工程化的决策主循环：

```
def bidding_cycle(t, state, budget_ctx, model_mgr):
    """每个决策周期(如每30分钟)执行一次。"""
    # 1. 构建上下文
    x = build_context(state, budget_ctx)      # 时段/ecpm/预算比/受众
    # 2. 无约束建议
    suggestions = []                          # (action_ref, value_est, cost_est)
    for arm in model_mgr.arms:                # 每个平台-campaign-目标档位
        value = model_mgr.ucb_value(arm, x)   # LinUCB 上置信界估值
        cost  = model_mgr.cost_est(arm, x)    # eCPM 期望
        suggestions.append((arm, value, cost))
    # 3. 约束求解（拉格朗日 + 背包投影）
    plan = solve_constrained(suggestions,
                             budget=budget_ctx.remaining,
                             min_roas=budget_ctx.min_roas,
                             caps=budget_ctx.platform_caps)
    # 4. 转成出价指令（归一化层做最终翻译）
    intents = to_bid_intents(plan)            # 每平台 BidIntent
    return intents
```

#### 2.3.8 Bandit 参数学习 / 推荐的 Go 实现片段

下面给一个"每平台一个 LinUCB + 拉格朗日预算约束"的可运行 Go 骨架（教学简化版）。

```go
package agent

import (
	"math"
	"gonum.org/v1/gonum/mat"
)

// LinUCBArm 单臂的线性模型（简化）
type LinUCBArm struct {
	A *mat.Dense // d×d
	b *mat.VecDense
	theta *mat.VecDense
}

// AgentCtxBandit 带预算约束的上下文 bandit
type AgentCtxBandit struct {
	arms  []*LinUCBArm
	dim   int
	alpha float64
	lam   float64

	// 约束对偶变量
	lambda float64 // 预算违约惩罚
	mu     float64 // ROAS 违约惩罚
	budget float64
	minROAS float64
}

func NewAgent(dim, numArms int, alpha, lam float64) *AgentCtxBandit {
	a := &AgentCtxBandit{dim: dim, alpha: alpha, lam: lam}
	for i := 0; i < numArms; i++ {
		A := mat.NewDense(dim, dim, nil)
		for j := 0; j < dim; j++ {
			A.Set(j, j, lam)
		}
		a.arms = append(a.arms, &LinUCBArm{
			A: A, b: mat.NewVecDense(dim, nil),
			theta: mat.NewVecDense(dim, nil),
		})
	}
	return a
}

// value 返回第 i 臂的 UCB 估值（这里省略成本项，仅示意）
func (a *AgentCtxBandit) value(i int, x *mat.VecDense) float64 {
	arm := a.arms[i]
	var theta mat.VecDense
	theta.SolveVec(arm.A, arm.b) // θ = A^{-1}b
	var mean float64
	for j := 0; j < a.dim; j++ {
		mean += theta.AtVec(j) * x.AtVec(j)
	}
	// x^T A^{-1} x
	var AinvX mat.VecDense
	AinvX.SolveVec(arm.A, x)
	var u float64
	for j := 0; j < a.dim; j++ {
		u += x.AtVec(j) * AinvX.AtVec(j)
	}
	return mean + a.alpha*math.Sqrt(u)
}

// Select 返回考虑预算约束后的最优臂
func (a *AgentCtxBandit) Select(x *mat.VecDense, cost []float64) int {
	best, bestVal := -1, math.Inf(-1)
	for i := 0; i < len(a.arms); i++ {
		v := a.value(i, x) - a.lambda*cost[i]
		if v > bestVal {
			bestVal = v
			best = i
		}
	}
	return best
}

// Update 拉格朗日更新：预算违约则提高 λ
func (a *AgentCtxBandit) Update(arm int, x *mat.VecDense, reward, cost float64,
	eta float64, totalCost float64) {
	// 更新臂的参数
	xxT := mat.NewDense(a.dim, a.dim, nil)
	for p := 0; p < a.dim; p++ {
		for q := 0; q < a.dim; q++ {
			xxT.Set(p, q, x.AtVec(p)*x.AtVec(q))
		}
	}
	arm := a.arms[arm]
	arm.A.Add(arm.A, xxT)
	arm.b.AddVec(arm.b, x) // 简化：b += x（未乘 reward，完整版需 reward*x）
	// 预算约束对偶更新
	a.lambda = math.Max(0, a.lambda+eta*(totalCost-a.budget))
	_ = reward
}
```

> **注意**：以上片段为教学骨架，省略了严格线代符号（`_ = reward` 处为占位以防编译问题）。生产实现请结合 `gonum` 的 `mat` 包正确求解、用 Sherman-Morrison 增量更新逆矩阵，并做单元测试与数值稳定性检查。**不要把这节代码直接用作生产代码**——它旨在说明"参数如何组织、对偶变量如何更新"。

#### 2.3.9 离线评估（Offline Evaluation）——上线前必做

RL/Bandit 模型最大的风险是"线上回不去"。上线前必须做**离线评估**：

**（1）反事实评估（Off-policy evaluation, OPE）**：用历史"日志策略"采集的数据，估计新策略的表现。

**IPS（Inverse Propensity Scoring）估计**：

```
V̂_IPS(π_e) = (1/N) Σ_t [ r_t · (π_e(a_t|x_t) / π_b(a_t|x_t)) ]

其中：
    π_b 是历史数据收集时的行为策略
    π_e 是待评估的新策略
    r_t 是历史实际奖励
加权分母是行为概率，避免"新策略集中在高样本行动"造成偏差
```

**（2）离线回放（Replay）**：用历史随机化日志，模拟"若当时用新策略会选什么、拿到什么奖励"。适合 Bandit，但要保证日志里有足够的随机化（建议初始期用 ε-greedy 采集）。

**（3）指标**：离线 ROAS、预算利用度、约束满足率、与基线（当前策略）的差异显著性。

> **工程铁律**：DRL/复杂的 Bandit 模型，上线前一定要用 OPE/回放给出"不劣于线上基线的证据"，并且逐日监控线上 vs 离线的一致性（drift）。

#### 2.3.10 Agent 的冷启动与探索策略

- **冷启动阶段**（新 campaign / 新平台）：用 ε-greedy（ε=0.2~0.3）或 UCB 强制探索；数据不足时用保守目标档位。
- **探索预算**：内容预算中划出固定比例（如 5%~10%）用于"探索性投放"，作为离线/在线评估的随机化数据来源。
- **沙盒白名单**：探索不触及硬约束（ROAS 下限、风控规则），探索只发生在"安全行动子集"。
- **退避策略**：当某行动连续 N 轮 ROAS < 下限 70% 时，强制暂停该 arm，避免失控。

### 2.4 跨平台归因到出价的闭环

**归因循环（Attribution → Bid Adjustment）** 是 UBF 区别于"一堆平台 API 封装"的关键。没有闭环，Agent 就是瞎猜；没有归因，闭环就是错乱。

#### 2.4.1 闭环全貌

```
                ┌──────────────────────────────────────────┐
                │                归因闭环                    │
                │                                            │
  平台报表 ──>  │ 原始事件汇聚 ──> 归属判定 ──> 转化价值计算    │
  第一方事件 ──>  │                 │   │                    │
                │                 ▼   ▼                    │
                │         平台贡献估计 (每平台 ROAS/CPA)      │
                └──────────────────┬────────────────────────┘
                                   │ 效果估计 → 置信度
                                   ▼
                       智能出价 Agent（收紧/放松预算与出价）
                                   │
                                   ▼
                       统一出价层 → 平台适配器 → 平台出价调整
                                   │
                                   └──── 观察结果 ────┘ (回到顶部)
```

#### 2.4.2 归属判定：如何把转化归给平台

现实中一个用户可能被 Google、Meta、TikTok 都触达过，最后的转化到底是"谁带来的"？UBF 需要一种**归属判定的默认规则**，避免各平台重复邀功。

**常见归属规则**：

| 规则 | 描述 | 优点 | 缺点 |
| --- | --- | --- | --- |
| 末次点击 (Last Click) | 转化归给最后一次点击的平台 | 简单、易实现 | 忽略前期影响 |
| 首次点击 (First Click) | 归给第一次点到的平台 | 重视拉新 | 忽略促成转化那次 |
| 线性 (Linear) | 通路中每个触点均分 | 公平 | 稀释每个平台贡献 |
| 位置衰减 (Position-based) | 首次/末次给更高权重 | 折中 | 权重参数主观 |
| 数据驱动 (Data-driven) | 用模型学习各触点贡献 | 准确 | 复杂、依赖数据量 |
| 媒体混合 / Shapley | 用合作博弈 Shapley 值 | 理论完备 | 计算开销大 |

**UBF 的工程建议**：在**闭环调参**阶段使用"末次点击 + 自定义窗口"为主（稳定、可解释、与平台自带归因差异最小），把"数据驱动/Shapley"作为**报表与预算分配**阶段的参考（更合理但不直接进闭环，避免放大噪声）。

#### 2.4.3 泊松 / 贝叶斯更新

**问题**：平台报表的转化数常有延迟（attribution lag）和噪声。例如 TikTok 的转化可能要 24~72 小时才回满，导致"今天的转化数被低估"。UBF 需要**在线估计每个平台的真实转化率/ROAS**，并对延迟进行校正。

**泊松模型**：把"某平台在时段 t 的转化数"建模为泊松随机变量：

```
C_t ~ Poisson(λ_t · spend_t)

其中：
    C_t   时段 t 的转化数
    spend_t 时段 t 的花费
    λ_t   单位花费的转化率参数（每花费1元的期望转化数）
若进一步用"转化价值"：
    Value_t ~ 转化数 × 平均客单价
```

**贝叶斯共轭更新（Gamma-Poisson）**：

```
先验： λ ~ Gamma(α₀, β₀)
似然： C_t ~ Poisson(λ · spend_t)
后验： λ | data ~ Gamma(α₀ + Σ C_t, β₀ + Σ spend_t)

后验均值： E[λ] = (α₀ + Σ C_t) / (β₀ + Σ spend_t)
后验方差： Var[λ] = (α₀ + Σ C_t) / (β₀ + Σ spend_t)^2

优点：共轭 → 解析可算、在线增量更新，不需 MCMC。
用途：给 Agent 一个"带不确定性的转化率/ROAS 估计"。
```

**Gamma-Poisson 在线更新 Python 实现**：

```python
class GammaPoisson:
    """Gamma-Poisson 共轭在线贝叶斯估计。
    估计单位花费的转化率（每花费1元的期望转化）λ。
    """

    def __init__(self, alpha0=1.0, beta0=100.0):
        # 弱信息先验
        self.alpha = alpha0
        self.beta = beta0

    def observe(self, conversions: float, spend: float):
        """在线增量更新后验 Gamma(alpha, beta)。"""
        self.alpha += conversions
        self.beta += spend

    def mean(self) -> float:
        """后验均值 E[λ] = alpha / beta"""
        return self.alpha / self.beta

    def std(self) -> float:
        """后验标准差"""
        return (self.alpha ** 0.5) / self.beta

    def sample(self, rng):
        """后验采样（Thompson 采样用）。"""
        import numpy as np
        return float(np.random.gamma(self.alpha, 1.0 / self.beta))
```

**延迟校正（Attribution Lag Correction / self-correcting）**：因为转化会延迟回满，直接拿"到账的转化"会低估。常用**马尔可夫/折现**校正或按平台历史延迟曲线外推。

**延迟校正的折现（discounted）模型**：

```
观察到截至当前 t 的实际转化 C_t^obs，估计"最终"转化：
    C_t^est = C_t^obs / d(t)      // 反"回满比例"
其中 d(t) 是平台历史"从 t 时刻起转化回满的比例"（回满曲线）
d(t) 用历史样本统计：d(t) = 平均(在 t 后窗口内最终转化) 中，截至t已到的占比
```

> **self-correcting（自校正）思想**：每当真实数据（完整回满后的转化）到达，就刷新该平台/该属性的"回满曲线"与 λ 后验。系统对自己的估计偏差不断纠错，而不是一成不变。

#### 2.4.4 eCPM / 出价补偿（Bid Compensation）

闭环的一个重要输出是 **eCPM 变化与出价补偿**。当平台 eCPM 波动时，Agent 需要决定"是否补偿（提价/降价）以维持目标 ROAS/流量"。

**eCPM 计算**：

```
eCPM = cost / impressions × 1000
```

**目标校准（Target Calibration）**：当平台实际 eCPM 高于目标时，Agent 的判断依据是"ROAS 是否仍达标"。出价补偿原则：

```
补偿逻辑（示例）：
- 若 eCPM 上升但 ROAS >= 目标：维持或微调，享受流量红利。
- 若 eCPM 上升且 ROAS 下滑：降低出价/缩小目标，或暂停该平台。
- 若 eCPM 下降且 ROAS 仍高：可适度加码、提高出价，抢占便宜流量。
- 补偿量由 "需要保持的 ROAS 与可承受的 CPA" 决定，不是盲目跟随 eCPM。
```

**Bayesian 出价补偿**：把"当前平台状态"看作带不确定性的估计，补偿决策用 posterior 做。例如用 Thompson Sampling：对每个候选出价档位，从其 posterior 分布采样 ROAS，选"ROAS≥目标且价值最大"的档位。

**补偿的数学表达（简化）**：

```
假设目标 ROAS = R_target
当前平台估计边际 ROAS 的后验 ~ Gamma(α, β)（按花费归一）
我们想要选择出价 multiplier m 使：
    P( 边际ROAS(m) ≥ R_target ) ≥ 1 − δ      // 高置信达标

用 Thompson 采样：
    sample roas_posterior → 选使 (期望价值 − 惩罚违反约束) 最大的档位
```

**补偿的约束**：补偿必须服从 2.3 的约束层——不得在预算吃紧时无脑提价，不得突破 max_cpm。

#### 2.4.5 闭环的时序与触发

UBF 的闭环不是连续实时地打 API（平台对频繁 API 调用很敏感、也是成本），而是**周期性批次 + 事件触发**：

```
周期（例如每 30 分钟）：
  1. 拉取各平台最近报表（增量）
  2. 拉取第一方归因/转化事件
  3. 增量更新 Gamma-Poisson 后验、回满曲线
  4. 重算各平台/各campaign 的估计 ROAS/CPA 与置信度
  5. 调用 Agent 决策 → 形成 BidIntent 批次
  6. 经归一化层翻译，向各平台 adapter 批量 apply

事件触发（立即）：
  - 预算将尽 → 触发全局降速
  - ROAS 硬下限被突破 → 触发暂停低效 campaign
  - 平台 API 熔断/故障 → 触发该平台出价冻结
  - 重大活动/风控 → 触发一次性调整
```

#### 2.4.6 闭环的防偏与风控

- **避免循环放大**：闭环最怕"自证预言"——平台报表高 ROAS 就提高出价，出价提高又虚增 ROAS，回归后崩盘。缓解：用**延迟校正后的保守估计**进入决策，且对高置信度阈值过滤小样本。
- **统计显著性门槛**：只有样本量足够（如 spend 达到最小阈值）时才根据 ROAS 调整出价；样本少时保持原目标。
- **异构归因 vs 出价**：不要让闭环同时用"异构归因"与"末次点击"两种标准，避免 Agent 无所适从。先在闭环里锁一种稳定口径。

---

## 三、生产环境实战

### 3.1 生产级 Go 实现：并发、限流、重试、熔断

统一出价框架在**控制面**是低频（周期批次决策），但**数据面**（拉取报表、接收事件回传）可能是高频并发。生产实现要同时照顾两类负载。

#### 3.1.1 整体并发模型

```
                 ┌──────────────┐
 调度器 (cron) ──>│ 决策 Worker   │──> 归一化 → adapter apply（串行按平台）
 事件回传 ─────> │ (每30min)     │
                 └──────────────┘
                 ┌──────────────┐
 报表拉取 ──────>│ 数据面 Worker  │──> 入统一数据模型（并发批次）
 归因事件 ──────>│ (worker pool) │
                 └──────────────┘
```

**Go 并发原语选型**：

| 需求 | Go 原语 |
| --- | --- |
| 并发拉取多平台报表 | `sync.WaitGroup` + goroutine pool |
| 结果聚合 | channel + fan-in |
| 请求级超时 | `context.WithTimeout` |
| 共享指标/计数 | `sync/atomic` 或 `sync.RWMutex` |
| 周期性调度 | time.Ticker / 外部 cron |
| 限流 | `golang.org/x/time/rate` 或令牌桶 |
| 重试 | 自研重试器（指数退避 + 抖动） |
| 熔断 | 自研或 `sony/gobreaker` |

#### 3.1.2 并发拉取多平台报表（worker pool 示例）

```go
package pipeline

import (
	"context"
	"sync"
)

// Job 一次报表拉取任务
type Job struct {
	Platform string
	ReportID string
}

// Result 一次拉取结果
type Result struct {
	Platform string
	Rows     []Row // 统一数据模型行
	Err      error
}

// rowFetcher 平台无关的拉取函数（内部转 adapter）
type rowFetcher func(ctx context.Context, j Job) ([]Row, error)

// RunConcurrent 并发拉取，等全部结束返回
func RunConcurrent(ctx context.Context, jobs []Job,
	fetch rowFetcher, workers int) []Result {
	jobCh := make(chan Job)
	resCh := make(chan Result, len(jobs))
	var wg sync.WaitGroup

	// 启动 worker pool
	for w := 0; w < workers; w++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for j := range jobCh {
				rows, err := fetch(ctx, j)
				resCh <- Result{Platform: j.Platform, Rows: rows, Err: err}
			}
		}()
	}
	// 派发任务
	go func() {
		for _, j := range jobs {
			jobCh <- j
		}
		close(jobCh)
	}()
	// 等待 worker 结束并关闭结果信道
	go func() { wg.Wait(); close(resCh) }()

	var results []Result
	for r := range resCh {
		results = append(results, r)
	}
	return results
}
```

> 说明：并发数 `workers` 受平台 API 限流约束。Google/Meta/TikTok/DV360 都有 QPS 限制，worker 数不要盲目开大，需要配合下面的限流器。

#### 3.1.3 限流（Rate Limiting）

统一出价层调用平台 API 前必须限流，避免触发平台 429。用 `golang.org/x/time/rate` 做**每平台独立**的限流器。

```go
package ratelimit

import (
	"context"
	"golang.org/x/time/rate"
)

// PerPlatformLimiter 每平台一个令牌桶限流器
type PerPlatformLimiter struct {
	limiters map[string]*rate.Limiter
}

func NewPerPlatform(perSec map[string]float64, burst map[string]int) *PerPlatformLimiter {
	l := &PerPlatformLimiter{limiters: map[string]*rate.Limiter{}}
	for p, rps := range perSec {
		b := 1
		if v, ok := burst[p]; ok {
			b = v
		}
		l.limiters[p] = rate.NewLimiter(rate.Limit(rps), b)
	}
	return l
}

func (p *PerPlatformLimiter) Wait(ctx context.Context, platform string) error {
	lim, ok := p.limiters[platform]
	if !ok {
		return nil
	}
	return lim.Wait(ctx)
}
```

**限流策略细化**：

| 平台 | 默认限流建议 | 说明 |
| --- | --- | --- |
| Google Ads API | 遵循开发人员令牌配额 | 通常 ~15-20 QPS，重活报错 |
| Meta Marketing API | 遵循 app-level & ad-account-level 限额 | 注意 error code 429 / 80004 |
| TikTok Marketing API | 遵循 app 配额 | 分 endpoint 配额 |
| DV360 API | 遵循 QPS 配额 | 大报表尽量用异步导出 |

#### 3.1.4 重试（Retry）——指数退避 + 抖动

```go
package retry

import (
	"context"
	"math/rand"
	"time"
)

// Policy 重试策略
type Policy struct {
	MaxAttempts int
	BaseDelay   time.Duration
	MaxDelay    time.Duration
	Factor      float64
}

func DefaultPolicy() Policy {
	return Policy{MaxAttempts: 4, BaseDelay: 200 * time.Millisecond,
		MaxDelay: 5 * time.Second, Factor: 2.0}
}

// Do 带指数退避+抖动的重试执行
func Do[T any](ctx context.Context, p Policy, fn func(context.Context) (T, error)) (T, error) {
	var zero T
	delay := p.BaseDelay
	var lastErr error
	for attempt := 0; attempt < p.MaxAttempts; attempt++ {
		if attempt > 0 {
			// 抖动：delay * [0.5, 1.5)
			jitter := 0.5 + rand.Float64()
			wait := time.Duration(float64(delay) * jitter)
			select {
			case <-ctx.Done():
				return zero, ctx.Err()
			case <-time.After(wait):
			}
		}
		v, err := fn(ctx)
		if err == nil {
			return v, nil
		}
		lastErr = err
		delay = time.Duration(float64(delay) * p.Factor)
		if delay > p.MaxDelay {
			delay = p.MaxDelay
		}
	}
	return zero, lastErr
}
```

**重试的守则**：
- 只重试**可重试错误**（429/5xx/timeout），不要重试 400/403。
- **幂等优先**：重试请求必须可幂等（用请求指纹/批处理幂等键）。
- **上下文控制**：整个批次有总超时，防重试拖垮。
- **重试预算**：对单个 batch 设置最大重试次数，防止无限循环。

#### 3.1.5 熔断（Circuit Breaker）

当一个平台持续故障时，熔断器"打开"，快速失败，避免雪崩。用 `sony/gobreaker` 或自研。

```go
package breaker

import (
	"time"

	"github.com/sony/gobreaker"
)

// New 为一个平台创建熔断器
func New(platform string) *gobreaker.CircuitBreaker {
	settings := gobreaker.Settings{
		Name:        platform,
		MaxRequests: 5,             // half-open 时允许探测的请求数
		Interval:    60 * time.Second, // 清空计数的周期
		Timeout:     30 * time.Second, // open -> half-open 等待
		ReadyToTrip: func(counts gobreaker.Counts) bool {
			// 连续失败达到阈值即熔断
			return counts.ConsecutiveFailures >= 8
		},
	}
	return gobreaker.NewCircuitBreaker(settings)
}
```

**熔断状态机**：

```
   ┌────────────────────────────────────────────────┐
   │   Closed (闭合)                                 │
   │   正常放行；失败计数累积                         │
   └───────────────────────┬────────────────────────┘
       连续失败 ≥ 阈值        │
                           ▼
   ┌────────────────────────────────────────────────┐
   │   Open (打开)                                   │
   │   快速失败，不再调用平台；计时 Timeout           │
   └───────────────────────┬────────────────────────┘
       Timeout 到期(进入 half-open) │
                           ▼
   ┌────────────────────────────────────────────────┐
   │   Half-Open (半开)                              │
   │   放行少量探测请求；成功→Closed，失败→Open       │
   └────────────────────────────────────────────────┘
```

**熔断与出价安全带**：当某平台熔断时，UBF 应当"冻结"该平台出价（不再 apply），并把这部分预算转给其他平台（或暂缓），而不是让该平台出价停在"即将失效"状态。

#### 3.1.6 服务端幂等与对账

统一出价层所有写操作要幂等：

```go
// 幂等键：platform + campaign_ref + intent 指纹 + applied_at 时段
func idempotencyKey(intent *BidIntent, t string) string {
	return fmt.Sprintf("%s|%s|%s|%s", intent.CampaignRef,
		intent.Action, roundTarget(intent.Target), t)
}
```

- 写之前查"本周期是否已应用"，已应用则跳过（防重复应用导致目标被来回改）。
- 每天做一次"期望目标 vs 平台实际目标"的对账，输出不一致告警。

### 3.2 性能优化：缓存、异步、批量

#### 3.2.1 缓存策略

UBF 中，**静态/低频变化数据**要缓存，**决策相关的高频数据**要谨慎（避免读到过期出价）。

| 数据 | 缓存策略 | TTL | 失效方式 |
| --- | --- | --- | --- |
| 平台 API token / 认证 | 内存缓存 | 平台 token 有效期 | 刷新时替换 |
| 平台账户元数据（campaign 列表、目标） | 本地缓存 | 5~15 分钟 | 周期刷新 + 失效事件 |
| 汇率快照 | 缓存 | 交易日 | 交易日开始失效 |
| 口径字典 / 配置 | 内存 + etcd | 长 | 配置变更推送 |
| 实时 eCPM / ROAS 后验 | 不缓存（读最新） | - | - |
| 归因回满曲线 | 缓存（低频更新） | 小时级 | 收到新完整数据时更新 |

**缓存实现的坑**：
- **缓存击穿**：请求并发命中同一失效 key → 用 singleflight 合并请求。
- **缓存穿透**：不存在的 key 被反复查询 → 布隆过滤或空值缓存。
- **缓存雪崩**：大量 key 同时过期 → 给 TTL 加随机抖动。

**singleflight 示例（防击穿）**：

```go
import "golang.org/x/sync/singleflight"

var sf singleflight.Group

func fetchCampaignList(ctx context.Context, platform string) ([]Campaign, error) {
	v, err, _ := sf.Do("campaigns:"+platform, func() (any, error) {
		return platformRepo.ListCampaigns(ctx, platform)
	})
	if err != nil {
		return nil, err
	}
	return v.([]Campaign), nil
}
```

#### 3.2.2 异步化

- **报表拉取 → 入仓**：拉回到统一数据模型后异步写入数仓（如 ClickHouse/BigQuery），写失败进死信队列重试，不阻塞控制面。
- **事件回传**：第一方转化/归因事件用消息队列（Kafka/Pub/Sub）异步消费，解耦。
- **决策 apply**：同一周期多个平台的 apply 之间无强依赖，可异步并行，但受平台限流约束。

```
数据面架构（异步）：
  平台报表 →(adapter)→ 统一Row → 消息队列 → 异步消费者 → 数仓 + 指标 + 归因闭环
                                              ↓
                                        更新 Gamma-Poisson 后验 → 供 Agent 读取
```

#### 3.2.3 批量（Batch）优化

- **批量 API**：各平台都支持批量更新/report，尽量用批量而非逐条。
  - Google Ads：BatchJob / GoogleAdsService.Mutate 批量。
  - Meta：批量请求 / 分页 report。
  - TikTok：批量报表 / 批量上传。
  - DV360：批量 line items / 报表异步导出。
- **批量归并语义冲突**：跨平台批量的粒度不同——用统一 campaign_ref 映射，文档化每平台的"一个 batch 最多多少条"上限。
- **报表异步导出**：大 range 报表用平台异步导出（如 DV360 的 async job），避免同步超时。

#### 3.2.4 性能预算与基准

| 环节 | 目标延迟 | 优化手段 |
| --- | --- | --- |
| 决策周期（Agent 计算） | < 500ms | 特征缓存、bandit 增量更新、预计算 |
| 报表拉取（一批） | < 2min | 并行 + batch + 异步导出 |
| 归一化 + apply（多平台） | 周期内完成 | 并行 + 限流 + 批次 |
| 数据入仓可见 | < 5min | 异步管道、增量 upsert |

**性能指标建议**：
- P99 决策延迟、P99 单次平台 API 延迟。
- 每周期"实际完成 apply 数 / 应完成数"（成功率）。
- 平台 API 429 率、熔断打开时长。

### 3.3 Rollout 与灰度

UBF 这种"含决策模型 + 真金白银预算"的系统，**绝不能一把梭**。必须灰度、可回滚、有护栏。

#### 3.3.1 灰度层次

```
阶段 0: 影子（Shadow）—— 只读旁路，不真改平台出价
阶段 1: 拉量（Staged）—— 只对"预算小、非核心"的 campaign 启用
阶段 2: 分平台（Per-platform）—— 先上1个平台，验证后再扩
阶段 3: 分受众/时段（Segment）—— 只对特定 geo/device/时段启用
阶段 4: 全量（GA）—— 全量启用，保留紧急回滚
```

**阶段 0 影子模式（关键）**：UBF 全程"记日志不执行"，把 Agent 决策结果与"线上实际采用的原策略"做对比，离线评估新增价值与违反约束情况，跑 1~2 周再进阶段 1。

#### 3.3.2 灰度开关实现

使用统一 **Feature Flag / 动态配置**（etcd/Argo CD ConfigMap/开源 feature flag 服务）：

```go
// flags.go —— 灰度配置读取（示意）
type Flags struct {
	UBFEnabled        bool    `json:"ubf_enabled"`         // 总开关（阶段>=1）
	ShadowOnly        bool    `json:"shadow_only"`        // 阶段0 影子
	PlatformEnabled   map[string]bool `json:"platform_enabled"`
	MaxSpendPerCycle  float64 `json:"max_spend_per_cycle"` // 单周期花费上限护栏
	MinROASHard       float64 `json:"min_roas_hard"`      // 硬 ROAS 下限
	AllowedCampaigns  []string `json:"allowed_campaigns"` // 白名单 campaign
}
```

**开关的工程要求**：
- **动态生效**：改了 flag 立即生效，不需重启。
- **可秒级回滚**：一键把 `UBFEnabled=false` 或 `ShadowOnly=true`，系统应停掉 apply、保留原目标（把"平台目标恢复出厂/最后已知安全值"作为回滚动作）。
- **审计日志**：每次开关变化、每次 apply、每次回滚都记审计日志。

#### 3.3.3 灰度护栏（Guardrails）

无论灰度到哪个阶段，都要有**硬性护栏**，防止 Agent 或平台失控：

| 护栏 | 规则 | 触发动作 |
| --- | --- | --- |
| 单平台单日花费上限 | cost_platform > cap | 暂停该平台 apply、告警 |
| 全局日花费上限 | Σ cost > global_cap | 全场降速、告警 |
| ROAS 硬下限 | 过去 7 日 ROAS < Rmin×0.8 | 暂停低效 campaign |
| 单周期异常抖动 | 单周期花费环比 > +50% 且无理由 | 冻结该平台 |
| 预算节奏失控 | pacing 偏移 > 阈值 | 恢复均匀节奏 |
| Agent 数值漂移 | multiplier 或目标档位漂移异常 | 回退到上一安全快照 |

#### 3.3.4 回滚方案

- **快速回滚**：保留"上一个安全目标快照"，回滚=把各平台目标批量恢复到快照值 + 关闭 apply。
- **自然回滚**：先 `ShadowOnly=true`，让系统停止真改、但仍观察，确认安全后再全关。
- **回滚演练**：上线前做"熔断演练 + 回滚演练"，验证回滚动作在 5 分钟内完成。

### 3.4 监控指标

UBF 是"牵一发动全身"的控制系统，监控要覆盖**决策、执行、数据、护栏**四个面。

#### 3.4.1 指标清单

| 类别 | 指标 | 说明 / 告警阈值 |
| --- | --- | --- |
| 决策面 | Agent 决策延迟 P99 | > 500ms 告警 |
| 决策面 | 决策周期是否准时 | 周期漂移 → 告警 |
| 决策面 | 各平台建议目标/出价分布 | 分布异常（漂移）→ 注意 |
| 执行面 | 平台 API 成功率 | < 99% 告警 |
| 执行面 | 平台 API 429 率 | > 1% 注意，> 5% 告警 |
| 执行面 | 熔断打开次数 / 时长 | > 0 打开即告警 |
| 执行面 | apply 成功/失败/拒绝计数 | 拒绝率高 → 检查归一化 |
| 数据面 | 报表入仓延迟 | > 5min 注意 |
| 数据面 | 归因延迟（回满时差） | 平台间不一致 → 注意 |
| 数据面 | 数据幂等校验失败数 | > 0 告警 |
| 增益面 | 各平台实际 ROAS / 花费 / 出价 | 与目标对比 |
| 增益面 | 统一 ROAS vs 人工基线 | 需显著不劣于基线 |
| 护栏面 | 花费自动闸门触发次数 | > 0 告警 |
| 护栏面 | ROAS 硬下限突破次数 | > 0 告警 |
| 护栏面 | 回滚执行次数 | 记录成功/失败 |

#### 3.4.2 监控埋点与告警示例（Prometheus 风格）

```go
// metrics.go —— 关键指标定义（Prometheus client 示意）
import "github.com/prometheus/client_golang/prometheus"

var (
	ApplyTotal = prometheus.NewCounterVec(
		prometheus.CounterOpts{
			Name: "ubf_apply_total",
			Help: "UBF apply calls",
		},
		[]string{"platform", "status"},
	)
	ApplyLatency = prometheus.NewHistogramVec(
		prometheus.HistogramOpts{
			Name:    "ubf_apply_duration_seconds",
			Help:    "UBF apply latency",
			Buckets: []float64{0.1, 0.5, 1, 2, 5, 10},
		},
		[]string{"platform"},
	)
	DecisionLatency = prometheus.NewHistogram(
		prometheus.HistogramOpts{
			Name:    "ubf_decision_duration_seconds",
			Help:    "Agent decision latency",
			Buckets: []float64{0.05, 0.1, 0.2, 0.5, 1},
		},
	)
	BreakerOpen = prometheus.NewGaugeVec(
		prometheus.GaugeOpts{
			Name: "ubf_breaker_open",
			Help: "circuit breaker open state",
		},
		[]string{"platform"},
	)
)
```

**告警分级建议**：

```
P0（立即响应）: 花费闸门误触发 / ROAS 硬下限突破 / 熔断长时间打开
P1（快速响应）: 平台 API 成功率下降 / 归因数据断流 / 决策延迟恶化
P2（关注）   : 429 率上升 / 入仓延迟 / 指标漂移
```

#### 3.4.3 观测面板（Dashboard）维度

- **跨平台总览**：总花费、总转化、统一 ROAS、预算利用度。
- **分平台视图**：每个平台的 eCPM/CPA/ROAS、实际 vs 目标、出价 multiplier。
- **决策视图**：Agent 每周期决策的分布、约束违反次数。
- **健康视图**：成功率的熔断/限流/重试、入仓延迟。

### 3.5 部署与运维要点

- **形态**：UBF 作为独立服务（或模块）部署，与平台 SDK/API 客户端解耦部署。
- **多活 / 灾备**：关键状态（配置、灰度开关、预算闸门）放强一致存储（etcd/DB）；Agent 状态可分区、可重建。
- **配置化**：平台配额、汇率、口径、灰度、护栏全部下沉配置，避免改代码。
- **混沌/演练**：定期演练"平台 API 故障""预算闸门""回滚"，验证护栏真能兜住。
- **安全**：平台 API token 用密钥管理（KMS/Vault），不落硬编码；最小权限访问各平台账户。

---

## 四、常见问题与排查

### 4.1 各平台出价不一致 / 目标"翻译错位"

**现象**：统一设了"目标 ROAS = 3.0"，但各平台实际出价水平大相径庭，有的过猛、有的过绵。
**根因**：
- 各平台 ROAS 口径不同（转化价值定义、归因窗口不同）。
- 平台原生参数的"目标值"与"业务 ROAS"不是同一个数（例如 tROAS 用的是平台算的转化价值，可能与第一方价值不一致）。
- 归一化器把 ROAS 当成了标准单位直接透传，没有做平台系数校准。
**排查**：
1. 先在统一数据模型里核对每平台"实际 ROAS"是否都按统一口径（第一方转化价值）。
2. 核对平台原生参数值与日志中的 `platform_params`。
3. 检查是否缺平台系数校准（scale factor）。
**解决**：在归一化层为每平台加 `roas_scale_factor`（平台价值口径 / 第一方价值口径），目标 = 业务目标 × scale。并在 shadow 模式下做校准。

### 4.2 预算被"瞬间打光" / 节奏失控

**现象**：日预算在开场几小时就耗尽，后期没量，或某平台独吞预算。
**根因**：pacing 未生效 / 预算闸门未生效 / Agent 把预算集中压到单平台。
**排查**：
1. 检查护栏：`max_spend_per_cycle`、平台 caps 是否触发过（看审计日志）。
2. 检查 pacing 计算：`已花/时间进度` 对比 `预算/总周期`。
3. 检查 Agent 是否给了某平台过大 multiplier。
**解决**：启用"均匀/日间节奏"硬约束；对单平台单周期花费设硬 cap；Agent 分配相加必须 = 总预算（约束求解层保证）。

### 4.3 归因延迟导致的"低估转化 → 误砍预算"

**现象**：某平台转化回满慢（如 TikTok 延迟 48h），闭环基于"当前不到账转化"判断 ROAS 低，把该平台预算砍掉，结果它其实是好渠道。
**根因**：未做延迟校正，用了"观测值/当前"而非"估计最终值"。
**排查**：看该平台"回满曲线 d(t)"与"折现校正是否启用"。
**解决**：启用 Gamma-Poisson + 回满曲线校正；对高延迟平台设置"更长的评估窗口才允许调预算"；小样本时冻结调整。

### 4.4 Agent 模型"过拟合到当前 ecpm / 自证预言"

**现象**：模型越跑，某个平台出价越高、ROAS 看起来越高，但整体 ROI 没变甚至变差。
**根因**：闭环正反馈 + 未做统计显著性过滤 + 用平台自带归因（虚增）。
**排查**：用第一方归因对照"平台声称 ROAS vs 第一方 ROAS"。
**解决**：决策只用第一方归因的滞后校准后估值；提升显著性门槛；对"高 ROAS 但样本小"的行动引入线性衰减的探索惩罚。

### 4.5 平台 API 429 限流 / 熔断导致"出价没跟上"

**现象**：某平台频繁 429，熔断打开，出价被冻结在某个旧值。
**根因**：worker 并发太大 / 未限流 / token 配额不足。
**排查**：看 429 率、熔断记录、限流命中。
**解决**：降并发、加每平台限流、用批量 API、合理配置熔断参数（不要一失败就开）。

### 4.6 数据幂等 / 重复计数导致对账不平

**现象**：数仓里花费或转化重复、与平台报表对不上。
**根因**：同一平台报表批次被重复 upsert，或跨平台归因未去重。
**排查**：检查 `source_report_id` 去重键、累积逻辑。
**解决**：所有写入用 `(platform, source_report_id, dims)` 去重；归因用唯一 `conversion_id` 先全局去重再归属。

### 4.7 灰度阶段"影子结果与真实施工不一致"

**现象**：影子模式离线评估很好，实际启用后效果差异大。
**根因**：影子决策未真正影响预算/流量 → 反事实评估有偏差（off-policy bias），或上线时数据分布变化。
**排查**：检查 OPE 的倾向分、是否有分布偏移告警。
**解决**：影子阶段多跑 1~2 周；进入真实施工后先用"分平台/分受众"的小量级，做 A/B 对比（实验组 vs 对照组），再逐步放大。

### 4.8 常见问题排查速查表

| 症状 | 可能根因 | 首选排查动作 |
| --- | --- | --- |
| 出价不一致 | 平台系数/口径未校准 | 查 roas_scale_factor |
| 预算打光 | 护栏/闸门未生效 | 审护栏日志 |
| 误砍好渠道 | 归因延迟未校正 | 查回满曲线 |
| 模型过fit | 闭环正反馈/小样本 | 查显著性门槛 |
| 频繁429 | 并发过大/未限流 | 查429率、限流 |
| 对账不平 | 重复写入/未去重 | 查幂等键 |
| 影子vs实工出入 | off-policy bias/偏移 | 查分布告警、A/B |

---

## 五、自测题

> 覆盖：平台出价模型、统一出价层、Agent 算法、归因闭环、生产实践。

### 5.1 题目

**Q1.** 从出价模型角度，Meta 的 CBO + Advantage+、Google 的 H-iMax、TikTok 的 oCPM 各自的核心机制差异是什么？UBF 归一化层为什么不能把"目标 ROAS"当标准单位直接透传给各平台？

**Q2.** LinUCB 与 UCB1 的核心区别是什么？在什么情境下应优先选 LinUCB？请给出 LinUCB 的线上复杂度量级，并指出一个优化方法。

**Q3.** 请解释"带约束的拉格朗日 bandit"里 λ 和 μ 的含义：当预算接近耗尽时 λ 变大还是变小？它对"贵"的行动产生什么影响？为什么这样能保证不发生全局超支？

**Q4.** 归因闭环里 Gamma-Poisson 共轭贝叶斯估计的参数更新公式是什么？"回满曲线校正"解决的是广告出价的哪个具体问题？什么情况下小样本会误导 Agent，如何避免？

**Q5.** 生产实践中，为什么"影子模式 + 灰度 + 护栏 + 可回滚"对 UBF 几乎不可或缺？请各举一个"没有它会出事"的具体场景。

<details>
<summary>点击查看答案</summary>

**A1.**
- **Meta CBO + Advantage+**：预算在 campaign 层由 Meta 自动分配给 ad set，配合 Advantage+ 把受众/创意/出价全部交给 Meta 自动优化，依赖平台强大的模型与足够转化信号，广告主介入少。
- **Google H-iMax**：在"最大化转化/价值"与"逼近目标 CPA/ROAS"之间混合游走，根据预算与 ecpm 状态在最大化与约束之间切换，属于 Google 转化最大化的演进形态。
- **TikTok oCPM**：广告主设目标成本（如目标 CPA），TikTok 实时预测每个用户转化概率，把出价集中到高转化概率用户；名字带 CPM 但实际操作是"按展示计费、按行动优化"。
- **不能直接透传的原因**：各平台"转化价值/ROAS 口径"（转化价值定义、归因窗口、价值币种）不一致；平台原生 tROAS/目标成本 用的是平台自己的价值模型，与第一方转化价值可能差一个系数。需要为每平台配置 `roas_scale_factor` 等校准系数，把"业务 ROAS"翻译成"该平台原生目标值"，否则会错位。

**A2.**
- **区别**：UCB1 是**非上下文**多臂老虎机，只用每个臂的历史累计奖励/次数；LinUCB 是**上下文**线性 bandit，利用特征向量 x，假设奖励是特征的线性函数，用岭回归估计参数并给出上置信界。
- **选 LinUCB 的情境**：有可用的上下文特征（时段、国家、设备、ecpm、剩余预算比等），且各行动价值确实受特征影响的场景；此时 LinUCB 比 UCB1 显著降低遗憾、更快收敛。
- **复杂度**：选择一次为 O(K·d³)（每个臂求逆）。**优化**：用 Sherman-Morrison 公式增量更新 A⁻¹，单臂更新降为 O(d²)，整体可到 O(K·d²)；或用卡尔曼式流式估计，避免每轮重求逆。

**A3.**
- λ 是**预算约束的对偶变量/拉格朗日乘子**。当预算接近耗尽（Σcost > B）时，在线更新 λ ← max(0, λ + η(Σcost−B))，所以 **λ 变大**。
- λ 变大后，净价值 g = value − λ·cost，**"花费高（贵）"的行动减分更多**，Agent 会更倾向选择"便宜且价值不差"的行动，从而抑制高成本采购。
- 因为 λ 随预算违约深度单调上升，维持"超支越大、惩罚越重"的负反馈，从机制上保证系统不会无限度超支；配合预算闸门硬 cap 双保险，确保全局不超预算。

**A4.**
- Gamma-Poisson 更新：先验 λ~Gamma(α₀,β₀)，观察到 C_t 转化与 spend_t 花费后，后验 λ~Gamma(α₀+ΣC_t, β₀+Σspend_t)。后验均值 E[λ]=(α₀+ΣC_t)/(β₀+Σspend_t)。共轭 → 解析在线增量更新。
- **回满曲线校正**解决的是"归因/转化延迟"问题：平台的转化数要若干小时后才回满，直接用当前到账值会低估真实转化率，导致 Agent 误判 ROAS 偏低。用 C_t^est = C_t^obs / d(t)（d(t) 为截止 t 的回满比例）来估计最终转化。
- **小样本误导**：样本极少时 ROAS 后验方差极大，Agent 可能因一个随机高/低值就大幅调预算。避免方法：设置最小样本/最小 spend 门槛，不足则冻结调整；使用后验高置信区间（如 Thompson 采样或下置信界）而非点估计；并加入探索惩罚/线性衰减。

**A5.**
- **影子模式**（不真改出价只记录/A-B）没它：Agent 有 bug 但未验证就真金白银改出价，可能瞬间打光预算或走飞。影子模式先用离线收益证据把关。
- **灰度/分平台**没它：一刀切全量，单平台适配器 bug 会波及其他平台，无法在"1 个平台出错"时收窄爆炸半径。
- **护栏**（花费闸门/ROAS 硬下限）没它：Agent 或平台异常会导致日花费超预算、ROAS 跌穿，真金白银损失且无兜底。
- **可回滚**没它：上线后若发现明显问题，无法快速恢复"最后已知安全目标"，只能等待人工逐平台恢复，期间持续失控。
- 示例：曾有影子评估通过，但真实施工时某平台 429 熔断 → 出价冻结旧值；若没有护栏与回滚，会持续以错误出价投放数小时。护栏兜底 + 一键回滚止损，正是这道防线。

</details>

---
> 本文深度覆盖了跨平台统一出价框架的**模型原理、统一抽象、决策算法、归因闭环与生产落地**。核心要点：**理解各平台出价模型差异是归一化的前提；统一出价层负责"翻译与执行"、Agent 负责"决策"、归因闭环负责"校准"；从 Bandit 起步、用带约束的方法满足预算与 ROAS 硬约束；生产落地必须靠影子-灰度-护栏-回滚**。祝落地顺利。

---

## 附录 A：各平台出价 API 实战示例

> 本章给出四个平台的"统一意图 → 原生 API 调用"实战示例。示例代码为**教学级**，字段名以各平台当期 API 文档为准，重点展示 UBF 适配器里"翻译逻辑"的写法与常见坑。

### A.1 Google Ads API：设置目标 ROAS / 目标 CPA

Google Ads API (v17+) 中，campaign 的 bidding strategy 通过 `CampaignBiddingStrategy` 设置。tROAS 与 tCPA 属于 `TargetRoas` / `TargetCpa` 类型的 bidding strategy。

**请求 JSON（示意）**：

```json
{
  "campaign": {
    "resourceName": "customers/1234567890/campaigns/111222333",
    "campaignBudget": "customers/1234567890/campaignBudgets/444555666",
    "biddingStrategy": {
      "targetRoas": {
        "targetRoas": 3.2,
        "targetRoasMilliMicros": 3200000
      }
    }
  },
  "updateMask": "biddingStrategy"
}
```

**Go 调用片段（示意）**：

```go
// google_roas.go —— 设置 tROAS
import (
	"context"
	"google.golang.org/api/googleads/v17"
	"google.golang.org/api/option"
)

func ApplyTargetROAS(ctx context.Context, client *googleads.Service,
	customerID, campaignResource string, roas float64) error {
	// 构造 campaign 更新
	milli := int64(roas * 1000000) // tROAS 用 milliMicros 表达
	op := &googleads.CampaignOperation{
		Update: &googleads.Campaign{
			ResourceName: campaignResource,
			BiddingStrategy: &googleads.CampaignBiddingStrategy{
				TargetRoas: &googleads.TargetRoas{
					TargetRoasMilliMicros: milli,
				},
			},
		},
		UpdateMask: "biddingStrategy",
	}
	req := &googleads.MutateCampaignsRequest{
		CustomerId:   customerID,
		Operations:   []*googleads.CampaignOperation{op},
	}
	_, err := client.Customers.Campaigns.Mutate(customerID, req).Do()
	return err
}
```

**常见坑**：

1. `updateMask` 必须显式列出要更新的字段，漏了字段 = 不更新。
2. tROAS 从"广告主口径"到"Google 口径"可能需要系数校准（见 2.2.3）。
3. Google 要求 campaign 与 budget 绑定；改 bidding strategy 时别把 budget 一起改坏。
4. 若 campaign 启用了 Portfolio bidding strategy，不能在 campaign 级别直接设置，需改 portfolio 对象。

### A.2 Meta Marketing API：CBO / 目标 ROAS / Advantage+

Meta 中 campaign 有 `bid_strategy` 字段，ad set 有 `bid_amount` / `bid_constraints`；CBO 由 campaign 的 `daily_budget` / `lifetime_budget` 表达（campaign 层有预算 = CBO 开启）。

**设置 campaign 目标 ROAS（示意 JSON）**：

```json
{
  "name": "UBF_TROAS_Campaign",
  "objective": "OUTCOME_PURCHASES",
  "status": "ACTIVE",
  "special_ad_categories": [],
  "daily_budget": 500,
  "bid_strategy": "LOWEST_COST_WITH_BID_CAP",
  "bid_constraints": {
    "roas_min": { "value": 3.0 }
  },
  "campaign_budget_optimization": true
}
```

**Python 调用片段（示意）**：

```python
# meta_troas.py —— 更新 campaign bid 约束
from facebook_business.adobjects.campaign import Campaign


def apply_troas(campaign_id: str, min_roas: float) -> None:
    campaign = Campaign(campaign_id)
    campaign.update({
        "bid_strategy": "LOWEST_COST_WITH_BID_CAP",
        "bid_constraints": {
            "roas_min": {"value": min_roas},
        },
    })
```

**常见坑**：

1. `bid_strategy` 的取值受 objective 限制；`OUTCOME_PURCHASES` 才支持 ROAS 类约束。
2. Meta 的 `roas_min` 是"最低 ROAS 约束"而非"目标 ROAS"语义，翻译时注意方向。
3. CBO 开启后 ad set 级 budget 会被忽略——UBF 若在 ad set 上做 pacing 会无效，必须先查 campaign 是否 CBO。
4. Advantage+ campaign 很多字段由 Meta 托管，UBF 只宜设"目标类"参数，不宜细调受众/创意。

### A.3 TikTok Marketing API：oCPM / 目标成本

TikTok 的 campaign/ad group 上有 `optimization_goal`（如 `CONVERSIONS`）与 `bid_type`（`BID_TYPE_OCPM`），出价目标表达为 `bid`（按转化计费的目标成本）或 `deep_bid_type`。

**创建 ad group 的 JSON（示意）**：

```json
{
  "adgroup_name": "UBF_oCPM_AdGroup",
  "campaign_id": "1841234567890",
  "optimization_goal": "CONVERSIONS",
  "bid_type": "BID_TYPE_OCPM",
  "bid": 18.5,
  "deep_bid_type": "BID_TYPE_MINIMIZE_COST",
  "budget": 100.0,
  "budget_mode": "BUDGET_MODE_DAY",
  "targeting": { "geo": ["US"], "age": ["18-65"] }
}
```

**常见坑**：

1. `bid` 语义随 `optimization_goal` 变化（CPA / 安装成本 / 展示成本），翻译前必须明确目标类型。
2. `deep_bid_type`（如 `BID_TYPE_TARGET_ROAS`）是否可用取决于目标与地区。
3. TikTok 的转化回填延迟大，闭环必须用回满曲线校正（见 2.4.3），否则 Agent 会被"假低转化"误导。
4. 部分地区（如中国出海账户）币种与结算单位不同，注意货币归一化。

### A.4 DV360 API：目标 CPM / Custom Bidding

DV360 中 line item 支持 `pacing`、`budget`，出价通过 `targetCpm` / `maxCpm` / `customBidding` 表达。

**更新 line item 目标 CPM（示意 JSON）**：

```json
{
  "lineItemId": "lineItems/778899001",
  "lineItem": {
    "pacing": { "pacingType": "EVEN", "dailyTargetAmountMicros": "5000000000000" },
    "bidStrategy": {
      "fixedBid": null,
      "targetCpm": { "targetAmountMicros": "5500000000000" },
      "maxCpm": { "maxAmountMicros": "8000000000000" }
    }
  },
  "updateMask": "bidStrategy.targetCpm,bidStrategy.maxCpm"
}
```

**Custom Bidding 的步骤（示意）**：

```
1. 上传自定义信号 schema（定义信号字段，如 user_value_score, install_likelihood）
2. 通过 API 写入每个 bid request 的自定义信号值
3. 在 DV360 UI/API 中定义 custom bidding 目标（如"最大化信号A约束B"）
4. DV360 模型使用信号学习"高价值流量"的出价
5. UBF 适配器只需管理"信号更新"与"目标配置"，拍卖由 DV360 执行
```

**常见坑**：

1. DV360 金额字段多为 micros（百万分之一），注意 `* 1000000` 换算，容易差 6 个零。
2. `updateMask` 同样必须显式声明。
3. Custom Bidding 需要足够的信号数据量，冷启动阶段慎用。
4. RTB 环境中第一价格/第二价格拍卖由 exchange 决定，DV360 侧无法强制第二价格，eCPM 波动更大。

### A.5 适配器翻译对照速查（含单位换算）

| 平台 | 统一意图 | 原生表达 | 单位换算 |
| --- | --- | --- | --- |
| Google | TARGET_ROAS | target_roas_milli_micros | ×1,000,000 |
| Google | TARGET_CPA | target_cpa_micros | ×1,000,000 |
| Meta | TARGET_ROAS(约束) | bid_constraints.roas_min | 直接浮点 |
| Meta | TARGET_CPA | bid_amount / bid_cap | 直接金额 |
| TikTok | TARGET_CPA(oCPM) | bid (per conversion) | 直接金额 |
| TikTok | TARGET_ROAS | deep_bid_type + 目标 | 视 API 版本 |
| DV360 | TARGET_CPM | target_cpm.target_amount_micros | ×1,000,000 |
| DV360 | MAX_CPM | max_cpm.max_amount_micros | ×1,000,000 |

> **结论**：每个平台的"数值语义"（浮点 vs micros vs 约束方向）都必须有适配器内映射与单元测试覆盖。建议为适配器写"黄金用例"测试：同一 BidIntent 输入，断言各平台输出的 `platform_params` 与期望 JSON 完全一致。

---

## 附录 B：预算分配与节奏控制算法深度

### B.1 预算在平台间的分配（Budget Allocation）

统一预算到达 UBF 后，需要分解到平台。分配的核心原则：**按边际收益分配**，而不是按历史比例。

**静态比例 vs 边际收益分配**：

| 方法 | 原理 | 优点 | 缺点 |
| --- | --- | --- | --- |
| 固定比例 | 按运营经验固定 40/30/20/10 | 简单、可控 | 不随市场变化 |
| 历史 ROAS 加权 | 按近 7 日 ROAS 比例加权 | 简单、自动 | 滞后、未考虑边际递减 |
| 边际 ROAS 分配 | 用"最后 1 元预算的 ROAS"决定 | 理论最优 | 需要边际估计 |
| 背包/拉格朗日 | 在线分数背包求解 | 约束可嵌入 | 需要成本/价值估计 |

**边际 ROAS 分配的数学直觉**：

```
若某平台预算为 b，其"总价值函数" V_p(b) 是凹函数（边际递减）：
    边际价值 MVP_p(b) = dV_p(b)/db
最优分配满足：
    MVP_p(b_p) 对所有 p 相等（等边际原理）
    且 Σ b_p = B
否则可以把预算从"低边际"平台挪到"高边际"平台提升总价值。

工程近似：
    每周期用"最近 N 时段的边际 ROAS"估计 MVP_p(b_p)
    用坐标下降/牛顿法逼近等边际点
```

**预算分配伪代码（等边际近似）**：

```
输入：平台列表 P，总预算 B，各平台当前分配 b_p，边际估计函数 MVP_p(b)
输出：新分配 b'_p，Σ b'_p = B

1. 初始化 b'_p = b_p
2. 计算所有 MVP_p(b'_p)
3. 若 max MVP − min MVP < ε：停止
4. 否则：把预算从"MVP 最小"的平台挪 Δ 到"MVP 最大"的平台
5. 限制 Δ 不超过平台 cap 与剩余预算；回到 2
```

**工程注意**：

- 边际估计用"滑动窗口回归"或"差分法"（对比相邻时段花费增量与价值增量）。
- 分配变化要**平滑**：每周期最多调整 ±20%，避免预算大进大出造成平台模型紊乱。
- 平台有最小可投预算（如 Meta 每日 $5），低于下限的平台直接不分配。

### B.2 预算节奏控制（Budget Pacing）

**目标**：在预算周期内按节奏消耗预算，避免"前紧后松"或"打光即停"。

**常见节奏曲线**：

```
EVEN（均匀）       : 每时段消耗 = B / T
FRONT_LOADED（前倾）: 前期消耗更多（活动开场冲量）
BACK_LOADED（后倾） : 后期消耗更多（需要数据积累再放量）
DAYPART（分时段）  : 按业务活跃时段加权（如 18-24 点权重 2x）
```

**Pacing 控制算法（反馈式）**：

```
每时段 t 开始时：
    已消耗 C_t，已过时段比例 p_t = t / T
    目标消耗 G_t = pacing_curve(p_t) * B
    偏差 d_t = (C_t - G_t) / G_t          // >0 超前，<0 滞后

    若 d_t > 阈值（超前）：
        出价 multiplier *= (1 - k_p * d_t)     // 降速
        或降低目标档位
    若 d_t < -阈值（滞后）：
        出价 multiplier *= (1 + k_p * |d_t|)   // 提速（在 ROAS 约束内）
        或提高目标档位（保守）
    multiplier 限制在 [0.5, 3.0]，且服从 max_cpm 硬约束
```

**Pacing 参数**：

- `k_p`：反馈增益，太大易震荡，太小响应慢；通常 0.2~0.5。
- 更新频率：每 30 分钟 ~ 每小时一次。
- 保护：当剩余预算 < 总预算 5% 时，无论节奏如何，切换到"极速消耗+风控锁定"模式。

**Go 实现（pacing controller 示意）**：

```go
package pacing

import "math"

// Controller 节奏控制器（反馈式）
type Controller struct {
	TotalBudget  float64
	TargetCurve  func(p float64) float64 // 目标消耗比例曲线
	Gain         float64                 // k_p
	MinMultiplier float64
	MaxMultiplier float64
}

// NextMultiplier 计算下一时段的 multiplier
func (c *Controller) NextMultiplier(spent, elapsedRatio float64) float64 {
	target := c.TargetCurve(elapsedRatio) * c.TotalBudget
	if target <= 0 {
		return c.MinMultiplier
	}
	dev := (spent - target) / target
	if dev > 0 {
		// 超前 → 降速
		return math.Max(c.MinMultiplier, 1-c.Gain*dev)
	}
	// 滞后 → 提速（注意别超上限）
	return math.Min(c.MaxMultiplier, 1+c.Gain*(-dev))
}
```

### B.3 目标分解（从总 ROAS 到平台 ROAS）

上层给的常是"跨平台总 ROAS 目标"，需要分解为"每平台 ROAS 目标"，否则平台级目标没法设定。

**目标分解的约束方程**：

```
总花费 = Σ_p spend_p
总收入 = Σ_p spend_p * ROAS_p
总 ROAS = 总收入 / 总花费 = Σ_p w_p * ROAS_p ≥ R_target
其中 w_p = spend_p / 总花费（平台花费权重）

已知平台能力估计 ROAS_p（来自归因闭环），要求：
    存在权重 w_p（Σ w_p = 1）满足加权平均 ≥ R_target
    且 w_p 在平台上下限之间
```

**求解**：线性规划或贪心：

```
贪心分解：
1. 按 ROAS_p 从高到低排序平台
2. 尽量把预算给高 ROAS 平台（提高加权平均）
3. 若加权平均仍 < R_target：说明目标不可达
   → 要么降低总目标，要么提高低 ROAS 平台（成本更高）
4. 给每个平台的 ROAS 目标设为其当前估计 ROAS（或略高于，用于牵引）
```

**注意**：目标分解的结果要回写为每平台的 `BidIntent.target`，但各平台能否真正实现该 ROAS 取决于平台算法——UBF 只能"尽力牵引 + 监控偏差 + 必要时调整权重"。

---

## 附录 C：Agent 算法进阶与变体对比

### C.1 Thompson Sampling（汤普森采样）

与 UCB 的"上置信界"思路不同，Thompson Sampling 从后验分布**采样**并选择采样值最大的臂，是贝叶斯方法，与 2.4.3 的 Gamma-Poisson 天然契合。

**Thompson Sampling 伪代码（Beta-Bernoulli）**：

```
输入：K 个臂，每个维护 Beta(α_a, β_a) 后验
for t = 1, 2, ...:
    for each a:
        θ_a ~ Beta(α_a, β_a)          // 从后验采样
    选择 a* = argmax_a θ_a
    观察奖励 r_t ∈ {0,1}
    若 r_t=1: α_{a*} += 1 否则 β_{a*} += 1
```

**对广告出价的适配**：奖励为"连续值"（ROAS）时，用 Gamma-Poisson 后验采样（见 2.4.3 的 `sample` 方法），每个候选出价档位一个后验，采样选最大。

**UCB1 vs Thompson vs LinUCB 对比**：

| 维度 | UCB1 | Thompson | LinUCB |
| --- | --- | --- | --- |
| 类型 | 频率派 | 贝叶斯 | 频率派（上下文） |
| 上下文 | 否 | 否 | 是 |
| 奖励类型 | 任意实数 | 常为 0/1 或 Gamma | 实数 |
| 探索机制 | 上置信界 | 后验采样 | 上置信界（特征空间） |
| 计算量 | O(K) | O(K)（采样） | O(K·d²) |
| 冷启动 | 每臂先试一次 | 先验驱动 | 每臂至少一个样本 |
| 适合场景 | 极简单 | 有贝叶斯先验/连续ROAS | 特征丰富 |

### C.2 ε-greedy 与衰减探索

最简单的探索策略，适合作为冷启动兜底与"探索预算"的随机化来源。

```
ε-greedy：
    with prob ε: 随机选一个臂（探索）
    with prob 1−ε: 选经验均值最大的臂（利用）

衰减探索：
    ε_t = ε_0 / (1 + t / τ)
    或 ε_t = max(ε_min, ε_0 * decay^t)
```

### C.3 贝叶斯 Logistic Contextual Bandit（进阶）

当奖励是 0/1（是否转化）且要利用上下文时，可用 **Logistic regression + Laplace 近似**的 contextual bandit：

```
对每个臂 a：p(转化|x) = sigmoid(θ_a^T x)
后验近似：θ_a ~ N(θ̂_a, (X^T W X + λI)^{-1})
其中 W 是逻辑回归的权重矩阵（迭代重加权最小二乘 IRLS）

选择规则（Thompson 化）：
    θ̃_a ~ N(θ̂_a, Σ_a)           // 从后验采样
    选择 argmax_a sigmoid(θ̃_a^T x)（或期望价值）
```

**何时用**：转化是 0/1、且特征能解释转化概率、样本量较大（每臂 ≥ 100 次曝光）时。实现复杂度显著高于 LinUCB，需谨慎上线。

### C.4 DQN / PPO 的实现注意（工程向）

如果确实要上 DRL，注意以下工程点（论文里不会写）：

1. **奖励形状**：广告出价奖励稀疏且延迟，建议用"时段聚合"奖励（每时段一次 reward），并把归因延迟折现处理。
2. **状态归一化**：预算、花费、ecpm 量纲差异大，先归一化到 [0,1] 或 z-score。
3. **动作空间**：出价目标用"离散档位"比连续动作更稳（DQN 可用），连续动作再用 PPO。
4. **环境模拟器**：强烈建议先用"模拟器"（基于历史数据拟合的假环境）训练与验证，再上真实环境（safe RL / 隔离）。
5. **安全层**：RL 输出必须过约束层（同 2.3.6），RL 是"建议者"，约束层是"决策者"，防止策略崩坏时真金白银失控。

### C.5 算法选型决策树

```
有特征且行动有限？ ── 是 ──> LinUCB（默认推荐）
        │否
有贝叶斯先验或连续ROAS？ ── 是 ──> Thompson Sampling
        │否
行动少且数据少？ ── 是 ──> UCB1 / ε-greedy
        │否
需要连续出价值 + 长期依赖？ ── 是 ──> 先模拟器，再 PPO；否则 DQN（离散化）
        │
所有情况都要叠加：约束层（预算闸门 + ROAS 硬下限）+ 影子模式验证
```

---

## 附录 D：实验评估与 A/B 框架

### D.1 为什么出价系统必须做实验

出价系统直接花预算，任何模型改动都必须用实验证明"不劣于当前基线"，否则一次模型 bug 可能烧掉整周预算。实验是 UBF 的"质量门"。

### D.2 实验分层与隔离

```
实验分层（用户/流量维度）：
  L1: 预算池层（按预算池隔离）
  L2: 平台层（分平台隔离，防止平台间串扰）
  L3: campaign 层（实验 campaign vs 对照 campaign）

注意：出价实验不能只按用户分桶——同一 campaign 的用户被不同策略处理会互相污染平台学习；
更稳的做法是"campaign 级分桶"（同一 campaign 只归一个策略组）。
```

**campaign 级实验的不足**：不同 campaign 流量不均 → 需要协变量调整（CUPED）或用匹配对。

### D.3 实验指标

| 指标类型 | 指标 | 说明 |
| --- | --- | --- |
| 主指标 | 统一 ROAS（第一方口径） | 核心效果 |
| 辅指标 | CPA / 花费 / 转化数 | 分解效果 |
| 约束指标 | 预算利用度、ROAS 硬下限违反 | 安全性 |
| 健康指标 | 平台 API 成功率、入仓延迟 | 系统健康 |
| 护栏指标 | 花费闸门触发、熔断时长 | 兜底 |

### D.4 实验流程

```
1. 立项：定义假设、主指标、样本量与试验时长（用历史方差估算）
2. 影子：模型在影子模式跑 1~2 周，离线 OPE 评估
3. 小流量：5%~10% campaign 进入实验组，跑至少 2 个完整预算周期
4. 分析：显著性检验（t 检验 / 贝叶斯），多指标视角
5. 决策：显著优 → 放量；不显著 → 保留或回退；显著劣 → 立即回退
6. 监控：上线后持续监控指标漂移（psa / 前后对比）
```

**实验守则**：

- 一次只改一个变量（模型版本、约束、节奏），否则无法归因。
- 样本量估算：ROAS 方差大，通常需要单组 ≥ 20~30 个 campaign 或足够花费量。
- 遇到大促/流量波动，暂停实验结论，等稳定后再下结论。

---

## 附录 E：术语表与设计决策记录

### E.1 术语表（补充）

| 术语 | 英文 | 说明 |
| --- | --- | --- |
| 探索 | Exploration | 尝试未知行动的阶段 |
| 利用 | Exploitation | 使用已知最优行动 |
| 遗憾 | Regret | 最优策略与所采用策略的累计收益差 |
| 边际 ROAS | Marginal ROAS | 增加 1 元花费带来的增量收益 |
| 出价补偿 | Bid Compensation | 因 ecpm/市场波动对出价的调整 |
| 回满曲线 | Fill-up Curve | 转化随时间回满的比例曲线 |
| 预算闸门 | Spend Cap | 防止超支的硬上限 |
| 反事实评估 | Off-policy Evaluation | 用历史数据评估新策略 |
| 协同方差缩减 | CUPED | 用协变量降低实验方差 |

### E.2 关键设计决策记录（ADR）

| # | 决策 | 理由 | 备选方案与取舍 |
| --- | --- | --- | --- |
| ADR-01 | 闭环调参用"末次点击 + 统一窗口" | 稳定可解释、与平台差异最小 | 数据驱动归因更准但噪声大，仅用于报表 |
| ADR-02 | 决策模型从 Bandit 起步，DRL 需模拟器验证 | 上线风险与维护成本可控 | DRL 能力强但难评估、易崩 |
| ADR-03 | 约束用"拉格朗日对偶 + 硬闸门"双层 | 对偶平滑牵引 + 闸门兜底 | 纯对偶可能违约；纯闸门太僵硬 |
| ADR-04 | 每平台独立限流 + 熔断 | 单平台故障不拖垮全局 | 共享限流简单但会把故障扩散 |
| ADR-05 | 归因回满曲线按平台×属性分桶缓存 | 延迟差异大，分桶更准 | 全局一条曲线简单但误伤 |
| ADR-06 | 影子模式跑 1~2 周再上真实施工 | 降低 off-policy 风险 | 时间成本高，但值得 |

### E.3 上线 Checklist

```
□ 口径字典：各平台时区/币种/归因窗口/去重逻辑已标注
□ 适配器黄金用例测试通过（同一 BidIntent → 各平台期望 JSON）
□ 归一化校验：值域/白名单/约束降级逻辑
□ Agent：离线 OPE 评估通过（不劣于基线）
□ 归因闭环：回满曲线 + Gamma-Poisson 更新 + 延迟校正已启用
□ 护栏：花费闸门 / ROAS 硬下限 / 熔断 / 降速规则已配置
□ 灰度开关：影子模式 → 小流量 → 分平台 → 全量，每步有回滚预案
□ 监控：决策/执行/数据/护栏四类指标面板 + P0/P1/P2 告警
□ 实验：A/B 计划、样本量、显著性门槛
□ 回滚演练：5 分钟内恢复最后安全快照
□ 安全：token 入 KMS，最小权限
```

---

---

## 一、补充：一个完整的跨平台出价场景演练

> 用一条"从业务目标到平台执行再到闭环复盘"的完整走查，把前文所有概念串起来。场景：某出海手游发行商，目标市场 US，日总预算 $10,000，目标综合 ROAS ≥ 3.0，周期 24 小时，均匀节奏。

### 1.1 场景输入

```
业务目标（上层下达）：
  region  = US
  budget  = $10,000 / day
  min_roas = 3.0
  pacing  = EVEN

当前平台配置：
  Google：  campaign G-1（tROAS 由 UBF 管理），预算 $4,000
  Meta：    campaign M-1（CBO + Advantage+，预算 $3,000）
  TikTok：  campaign T-1（oCPM，预算 $2,000）
  DV360：   line item D-1（Target CPM 品牌触达，预算 $1,000）
```

### 6.2 时段 0（00:00，决策周期开始）

**上下文构建**：

```
x_t = [
  剩余预算比例 = 1.0,
  当前 eCPM: G=6.5, M=9.2, T=11.0, D=4.1,
  近 7 日 ROAS: G=3.4, M=2.8, T=3.1, D=2.2,
  时段 one-hot: [0,0,0,...], 国家=US, 设备=混合,
  事件标志: 无大促,
]
```

**Agent 无约束估值（示意，LinUCB 上置信界）**：

```
行动            估值(期望价值)   期望成本    net = value − λ·cost
G_002 (ROAS档3.0)   3.45          6.8      3.45 − 0.02×6.8 = 3.31
M_001 (ROAS档2.8)   2.85          9.2      2.85 − 0.02×9.2 = 2.67
T_001 (ROAS档3.1)   3.12         11.0      3.12 − 0.02×11.0= 2.90
D_001 (CPM触达)     2.20          4.1      2.20 − 0.02×4.1 = 2.12
```

λ 初始很小（预算充足），决策按净价值排序：G > T > M > D。

**约束层处理**：

```
预算分配（背包近似，按 value_per_dollar）：
  value_per_dollar: G=0.51, T=0.28, M=0.31, D=0.54
  排序：D(0.54) > G(0.51) > M(0.31) > T(0.28)
  等等——品牌线 D 虽然 ROAS 低但价值密度高？
  实际上 D 的价值口径不同（品牌触达），需要单独处理：
  UBF 把"品牌触达"与"效果 ROAS"分成两个预算池，
  这里只对 ROAS 池 ($9,000) 做分配：
  分配：G 45% ($4,050)，M 30% ($2,700)，T 25% ($2,250)
  （受平台 caps 约束微调后：G 4,000 / M 2,700 / T 2,300）
```

**决策产出（BidIntent 集合）**：

```
G_002: TARGET_ROAS target=3.2  budget=4050
M_001: TARGET_ROAS(min) target=2.9  budget=2700
T_001: TARGET_ROAS(target) target=3.1  budget=2250
D_001: TARGET_CPM target=4.5  max_cpm=8  budget=1000
```

**归一化 → 平台 API（示意，见附录 A 具体实现）**：

```
Google:  target_roas_milli_micros = 3,100,000
Meta:    bid_constraints.roas_min = 2.9 + Advantage+ 目标
TikTok:  deep_bid_type=TARGET_ROAS, 目标=3.1
DV360:   target_cpm = 4.5 USD, max_cpm = 8.0 USD
```

### 6.3 时段 6~10（预算紧张检测）

**pacing 反馈**：

```
已花费 $6,400 / 目标 $5,000（6/24 时间比例 25%，均匀目标 $2,500 + 波动）
超前 d = (6400−5000)/5000 = +0.28 → 超过阈值 0.15
→ 各平台 multiplier ×0.85，G 的目标 ROAS 略升（3.1→3.2）降速
```

**约束对偶**：λ 从 0.02 升到 0.35，G 的净价 3.31−0.35×6.8=0.93，T 的净价 2.90−0.35×11.0=**−0.95**，按净价排序 T 被降权，预算向 G 和 D 倾斜。

### 6.4 时段 12（夜间低谷）

夜间转化概率整体下降，ecpm 也下降：

```
ecpm: G=4.2, M=6.0, T=7.5, D=3.0
ROAS 估计（延迟校正后）：
  G=3.8, M=3.0, T=3.4, D=2.5
→ Agent 判定"便宜且 ROAS 高" → 适度提价 T（乘 1.2）
  但整体受 ROAS 硬下限 3.0 约束：D 维持品牌池不超支
```

### 6.5 时段 18~24（收尾）

```
剩余预算 $1,400 / 剩余时间 25%：
  切换为"完成预算优先"模式，但 ROAS 硬下限仍然拉住：
  若当前累计 ROAS 3.2 ≥ 3.0，可用剩余预算提量（multiplier ×1.5 上限）
  若 ROAS < 3.0，则继续降速保护 ROI
```

### 6.6 日终复盘（闭环更新）

```
当日最终：
  总花费 $10,078（1.8% 超支 —— 触发预算闸门告警，人工确认）
  总转化价值 $31,400
  综合 ROAS = 3.12 ≥ 3.0 ✓（但花费超支需修正）

闭环更新：
  - 更新各平台 Gamma-Poisson 后验与回满曲线（TikTok 转化延迟 48h 未回满，
    用回满曲线校正后 T 的真实 ROAS 预计 3.6）
  - 边际价值估计更新：D 池价值密度下降（品牌触达完成），下周 B 轮分配下调 D
  - Agent 参数（α 超参数）随新数据微调
  - 超支原因：Meta CBO 在末端急拉（平台策略），UBF 需在晚 8 点后
    对 M 施加更紧的 pacing 上限
```

### 6.7 场景关键结论

| 点 | 教训 |
| --- | --- |
| 归因延迟 | TikTok 转化回满慢，未校正会低估 T → 误砍预算 |
| 超支 | pacing 反馈 + API 层限流之外还防平台自身"临门一脚"，需要夜间护栏 |
| 品牌/效果分池 | 不同类型目标混在一个 ROAS 池会互相污染 |
| 对偶变量 | 预算紧时 λ 让 T 砍单，保护整体 ROAS |
| 实验 | 上述所有调整都以"分平台灰度"逐步上线，避免一次改全局 |

---

## 四、补充：生产故障排查 Scenario（F4 + 附录）

### 4.9 出价一直没变化（apply 静默失败）

**现象**：平台报表显示目标是旧值，UBF 日志显示 APPLIED。
**根因排查顺序**：
1. `ApplyResult.OK` 与平台 API 返回是否一致（有些平台"更新成功"但实际被风控忽略）。
2. 平台侧**审核/风控状态**：campaign 被 review / 被 pause，apply 不会报错但目标不生效。
3. 幂等键撞键：同一周期重复 apply 被跳过（检查 `applied_at` 窗口）。
4. 平台同步延迟（如 DV360 变更要 5~30 分钟生效）。
**解决**：apply 后读回平台实参（read-back），与期望值对比，不一致记 WARN + 重试一次；仍不一致上报人工核对。

### 4.10 多个活动同时跑，Agent 预算打架

**现象**：两个 campaign（A：新客拉新，B：老客召回）同属一个预算池，Agent 把预算全给了 A。
**根因**：统一数据模型未按 campaign 目的分桶，Agent 把两类目标混在一个 reward 里（ROAS 高就全都冲）。
**解决**：为不同 campaign 打 `goal_tag`（acquisition / retention / brand），Agent 分层：先按 goal 分桶预算，再在桶内 bandit 分配；桶间跨目标比较用统一的"价值函数"（如 LTV 折算）再比较。

### 4.11 新平台接入（平台适配器扩展流程）

```
1. 按附录 A 示例开发适配器（get / list / apply / report）
2. 写黄金用例测试（BidIntent → 原生 JSON 断言）
3. 影子模式接入，观察 1~2 周
4. 归一化层补充：币种 / 时区 / 系数 / 错误分类
5. 限流 / 熔断 / 重试参数配置
6. 小流量灰度 → 分平台全量
```

### 4.12 归因被平台"重复记账"导致的 ROAS 虚高

**现象**：各平台自带归因都高 ROAS，第一方归因却低很多。
**根因**：用户被多平台触达后转化，各平台自报 top 1%/last click 重复。
**解决**：闭环只用第一方归因；报表层保留"平台自报 / 第一方"双列；定期对比，差异过大 → 提示归因策略调整。

---

## 五、自测题（补充）

### 5.2 补充题目

**Q6.** 场景题：某平台即时 ROAS 很好但转化量少，另一平台 ROAS 略低但转化量大。预算有限时你会如何分配？请用 2.3.6 的概念（边际分、等边际原理）说明理由。

<details>
<summary>点击查看答案</summary>

**A6.** 应该按**边际 ROAS**（最后 1 元预算的增量回报）而不是平均 ROAS 分配。高 ROAS 平台若已接近饱和（边际递减），再投 1 元的增量回报可能已低于低 ROAS 平台的边际回报；此时应把预算从"高平均、低边际"的平台挪到"低平均、高边际"的平台，直到各平台边际回报相等（等边际原理）。具体做法：用滑动窗口差分估计每平台 MVP_p(b)，用 B.1 的等边际坐标下降迭代分配，并受平台 caps 与最小可投预算约束。

</details>

**Q7.** 如何用 CUPED（协变量方差缩减）提升出价 A/B 实验的统计功效？给出一个可用协变量。

<details>
<summary>点击查看答案</summary>

**A7.** CUPED 用实验前（pre-period）的相关协变量调整实验期主指标：

```
调整后指标：Y_adjusted = Y − θ·X_pre
其中 θ = Cov(Y, X_pre) / Var(X_pre)

用调整后指标做 A/B 比较，方差可显著下降（相关系数高时），
从而用更少样本 / 更短时间得出显著结论。

可用协变量示例：实验前 7 日 ROAS、前 7 日花费、campaign 历史 CVR。
注意：协变量必须不受实验处理影响（必须在实验开始前固化）。
```

</details>

**Q8.** TikTok 转化延迟大，而你正要决定它的次日预算。如何用"回满曲线 + Gamma-Poisson"做决策，而不是被 24h 内低转化误导？

<details>
<summary>点击查看答案</summary>

**A8.**

```
1. 用回满曲线 d_h(t)：TikTok 事件在 24h/48h/72h 分别回满的比例（来自历史）
2. 对每个时段 t：用 Gamma-Poisson 对"(转化/花费)"维护后验，
   观测到 C_t^obs 后用 C_t^est = C_t^obs / d(t) 作为"估计最终转化"
3. 更新后验：alpha += C_t^est，beta += spend
4. 决策：用后验均值（或保守下置信界）评估 T 的 ROAS，低于下限才减预算；
5. 同时设置"评估窗口"：距离转化（回满曲线尾部）足够长才允许较大调整；
6. 样本太少的时段冻结调整（最小样本门槛），防止 1~2 条转化就大改预算。
```

</details>

---
