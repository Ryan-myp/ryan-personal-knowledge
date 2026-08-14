# IO / LineItem 工作流深度解析（Day 2）

> **领域**: 广告投放 / 媒体购买工作流
> **深度**: ⭐⭐⭐⭐⭐ 实战级指南
> **标签**: dv360, insertion-order, line-item, workflow, flight
> **更新时间**: 2026-08-14
> **类型**: 学习笔记

---

## 学习旅程定位（本节导读）

这是 Day-2 的学习笔记，承接 Day-1 的《DV360 平台全景与核心概念》（`dv360-01-dv360-platform-overview.md`）。

- **Day-1** 认识了 DV360 是什么、账户层级长什么样、能做什么。
- **Day-2（本文）** 开始动手：把 **Insertion Order（IO / 订单项 / 媒体采购单）** 和 **Line Item（线条项目 / 媒体购买）** 从「创建」→「投放」→「优化」→「关停」的完整生命周期走一遍，全部配真实 API 方法与可跑的代码。

与深度文档的分工：

| 文档 | 侧重点 | Day-2 如何互补 |
|------|--------|----------------|
| `dv360-media-buying-deep.md` | 媒体购买全流程原理（IO→LineItem→创意→出价→排期→预算） | 本文按「学习旅程」组织，重点给**可复刻的端到端脚本**与**状态机** |
| `dv360-architecture-deep.md` | 平台架构、RTB、Go 广告请求引擎 | 本文聚焦 IO/LineItem 的业务工作流而非底层引擎 |
| `dv360-marketing-api-deep.md` | API 端点、认证、客户端封装 | 本文引用其客户端，但侧重**具体字段值**与**状态流转** |

> **一句话主线**：一笔预算，如何通过 `IO`（管钱、管时间、管总目标）和 `LineItem`（管出价、管定向、管每一场 flight）分层、分时、分节奏地花出去，并且全程能被 API 创建、查询、暂停、恢复、纠错。

所有示例都基于本仓库的两个真实脚本：

- `scripts/dv360_api.py` → 直接封装 REST 端点（`list_insertion_orders` / `create_insertion_order` / `list_line_items` / `create_line_item` / `create_campaign` 等）。
- `scripts/ad_platform_api.py` → 统一平台客户端（`dv360_create_line_item` / `dv360_update_line_item` / `dv360_list_flights` / `dv360_get_line_item` / `dv360_pause_line_item` / `dv360_resume_line_item` / `dv360_batch_update_line_items` / `dv360_list_insertion_orders` / `dv360_list_insertion_order_flexibility` 等）。

---

## 一、核心概念与架构

### 1.1 IO 与 LineItem 的关系：一句话模型

先给一个直觉模型，比任何定义都好记：

> **IO 是「合同」+「总盘子」，LineItem 是「具体执行的每一笔投放」。**

- **Insertion Order（IO）**：一张「花多少钱、在什么时间段花、为了什么目的」的排期合同。它把预算切成若干份，一份一份派给下面的 LineItem。
- **Line Item（LineItem）**：真正下场参与竞价的最小逻辑单元。它决定「这次竞价出价多少、定向哪些人、用什么创意、在哪个时间段（flight）投、每天花多少」。

一条 IO 下面可以挂几十上百个 LineItem；一个 LineItem 只能属于一个 IO（当然也能属于一个 Campaign 主站，归属链是固定的）。

```
一个广告主的投放树（聚焦 IO 与 LineItem）：

Partner   (资金池、时区、币种根节点)
│
└─ Advertiser  (计费主体、floodlight 配置)
   │
   └─ Campaign  (业务目标容器：品牌曝光 / 效果转化)
      │
      └─ Insertion Order (IO)  ← 重点①：管钱管时间管总目标
         ├─ 总预算 / 排期窗口 / 预算分配 / 灵活性(Flexibility)
         │
         └─ Line Item #1  ← 重点②：管出价管定向管 flight
         │    ├─ 出价策略(CPM/CPC/CPV/OCPM/CPA)
         │    ├─ 定向(GEO/AGE/GENDER/INTEREST/PLACEMENT...)
         │    ├─ 创意关联
         │    ├─ 频次上限 / 投放速率(pacing)
         │    └─ Flight 时间段(可多个)
         │
         └─ Line Item #2
              └─ ...（可继续扩展）
```

### 1.2 为什么要有两层「钱」？

这是新手最容易困惑的点：**为什么 IO 有预算，LineItem 也有预算？**

关键在「两层控制」：

```
预算控制的层次关系
─────────────────────────────────────────────────────────────
IO 层  (总盘子)
  ├── 总预算 budget                —— 整个 IO 至多花这么多
  ├── 排期窗口 dateRange           —— 什么时候能花
  └── 预算分配 budgetAllocation    —— 可以按比例/优先级分给 LineItem
       └── 灵活性(IO Flexibility)  —— 子项花不完，钱能否挪给别的子项

LineItem 层 (每次竞价)
  ├── 自己的 budget               —— 单个 LineItem 的花费上限
  ├── 自己的 flight 时间段        —— 每个 flight 的起止
  └── 每日每天投放的速率(pacing)
      └── 总的目标：既不超花，也不浪费
─────────────────────────────────────────────────────────────
```

- **IO 管「上限与方向」**：告诉我总共能花多少、什么时候、花向什么大目标。
- **LineItem 管「执行的每一口」**：每一次竞价用它自己的出价、定向、flight 去花 IO 分给它的那部分钱。

这两个层级互相约束：**LineItem 的预算总和不能超过 IO 的预算**；LineItem 的 flight 必须在 IO 的排期窗口之内；IO 暂停，下面的 LineItem 全部停止出价。

### 1.3 IO 的核心属性拆解

IO 的属性可以归成四大类：**预算 / 排期 / 交易类型 / 目标**。

| 属性 | 字段/枚举 | 说明 |
|------|-----------|------|
| **预算** | `budget.budgetAmountMicros` | 该 IO 的货币预算（微单位，1 元 = 1,000,000 micros） |
| | `budget.budgetUnit` | `CURRENCY`（按货币）或 `IMPRESSIONS`（按展示） |
| | `budget.budgetAllocationType` | 按比例分配 / 按固定金额分配 |
| **排期** | `dateRange.startDate` / `endDate` | IO 整体投放窗口（外框） |
| | `pacing` | 投放速率：`EVEN`/`ASAP`/`AHEAD` 等 |
| **交易类型** | `insertionOrderType` | 参考 `PROGRAMMATIC_GUARANTEED` / `PRIVATE_MARKETPLACE` / `PREFERRED_DEAL` / `OPEN_AUCTION` |
| **目标** | `goal` | 本次 IO 的核心目标（如曝光、转化、品牌提升） |
| **状态** | `entityStatus` | `ENTITY_STATUS_ACTIVE` / `ENTITY_STATUS_PAUSED` / `ENTITY_STATUS_DRAFT` 等 |

> ⚠️ 货币单位：DV360 所有金额字段都用**微单位 `micros`**（`budgetAmountMicros`）。1 元人民币 = 1,000,000 micros，1 美元同样 = 1,000,000 micros。写 API 时千万别直接把「5000 元」填进去，否则等于只给了 0.005 元——这是真实踩过的大坑！

### 1.4 LineItem 的核心属性拆解

LineItem 的属性可以归成：**定向 / 创意 / 出价 / 频控 / flight** 五大类。

| 属性 | 字段/枚举 | 说明 |
|------|-----------|------|
| **定向** | targeting 子资源 | 地理、年龄、性别、兴趣、行为、关键词、投放位置、App、设备、操作系统等 |
| **创意** | creativeIds | 关联到该 LineItem 的创意 ID 列表 |
| **出价** | `bidStrategy` | `CPM` / `CPC` / `CPV` / `OCPM` / `CPA` |
| | `maxBidAmountMicros` | 出价上限（微单位） |
| **频控** | `frequencyCap` | 每用户/每周期最大触达次数 |
| **flight** | flights[] | 投放时间段，可多个；每个 flight 有起止日期，可选预算 |

> 定向与被排除定向的关系：LineItem 的 `targeting` 定义了「要哪些」，同时还有 `negativeTargeting`（排除项）。真实场景里「排除比纳入更重要」——比如排除 App 内嵌浏览器、排除低质库存、排除竞对关键词。

### 1.5 ASCII：IO→LineItem→Flight 的嵌套关系总览

下面这张图把「IO 排期窗口」和「LineItem 的多个 flight」画在一张时间轴上：

```
时间轴:  2026-08-01 ──────────────────────────────── 2026-09-30
IO 排期窗口: ┌──────────────────────────────────────────────┐
             │           IO: 夏促品牌推广 (总预算 50万)      │
             └──────────────────────────────────────────────┘

LineItem A (视频前贴片, CPM)  ▼ flight1
  flight1: ┌───────┐
           │08-01~08-15│
           └───────┘

LineItem B (展示横幅, OCPM)  ▼ flight1        ▼ flight2
  flight1:          ┌────────┐
                    │08-10~08-25│
                    └────────┘      ┌────────┐
  flight2:                          │09-01~09-15│
                                    └────────┘

关键约束:
  ✅ 每一个 flight 都必须落在 IO 排期窗口内
  ✅ 同一个 LineItem 的多个 flight 不能互相重叠
  ✅ LineItem 预算总和 ≤ IO 预算
  ✅ IO 暂停 → 所有 LineItem 全部停投
```

---

## 二、深度原理解析
### 2.1 IO 目标与预算设定原理

IO 的「目标」（`goal`）和「预算」（`budget`）不是孤立的两个字段，而是**互为因果的漏斗**：目标决定你买什么，预算决定你买多少。

#### 2.1.1 目标（Goal）——决定你买什么

IO 的 goal 可以理解为「这笔钱是为了达成什么生意结果」。常见目标类型：

| 目标类型 | 本质 | 典型指标 | 适合场景 |
|----------|------|----------|----------|
| `TRADITIONAL`（传统展示） | 追求曝光/规模 | Impressions, Reach | 品牌曝光、新品上市 |
| `EFFECTIVE`（效果） | 追求转化 | CPA, Conversions | 效果营销、App 下载、电商 |
| `AWARENESS`（品牌认知） | 追求心智 | Viewability, Completion | 品牌记忆提升 |

目标会**向下传导**，影响下层 LineItem 应该怎么出价：

```
IO 目标 = 品牌曝光(TRADITIONAL)
   ↓ 传导
LineItem 出价 = CPM 或 vCPM，追求便宜的可视曝光
   ↓
优化指标 = Impressions / Viewable Impressions

─────────────────────────────

IO 目标 = 效果转化(EFFECTIVE)
   ↓ 传导
LineItem 出价 = OCPM/CPA，追求转化成本最低
   ↓
优化指标 = Conversions / CPA
```

> 踩坑：IO 的目标如果设成 `EFFECTIVE`，但下面的 LineItem 却是纯 `CPM` 出价、也没有配 Floodlight 转化追踪，系统会「想优化转化却没数据」，结果投放往往是空跑或出价失控。**目标和下面的执行层必须匹配**。

#### 2.1.2 预算（Budget）——决定买多少

IO 预算有几种设定维度，先看枚举：

| 维度 | 枚举/字段 | 说明 |
|------|-----------|------|
| 预算单位 | `budgetUnit = CURRENCY` / `IMPRESSIONS` | 按钱花，还是按展示量花 |
| 金额 | `budgetAmountMicros` | 微单位金额 |
| 预算分配类型 | `budgetAllocationType` | 决定钱如何分给 LineItem |
| 灵活性 | IO 的 Flexibility | 子项花不完的钱能不能挪走 |

**两种预算分配类型（核心概念）**：

```
① 按比例分配 (PROPORTIONAL / percentage)
   IO 预算 50万
   ├── LineItem A: 40%  → 20万
   ├── LineItem B: 35%  → 17.5万
   └── LineItem C: 25%  → 12.5万
   特点: 改 IO 总预算，子项自动等比变化

② 按固定金额分配 (FIXED / explicit amounts)
   IO 预算 50万
   ├── LineItem A: 固定 20万
   ├── LineItem B: 固定 10万
   └── LineItem C: 固定 5万
   特点: 数字写死，子项不随 IO 总预算自动变
```

> 踩坑：用「固定金额」分配时，LineItem 的预算之和可以小于 IO 总预算（留了 slack），但**绝不能大于** IO 预算，否则会被拒绝或运行时报错。规划时先用 `dv360_list_insertion_order_flexibility` 检查 IO 的灵活性设置，确认子项之间是否允许互相挪用。

#### 2.1.3 灵活性（Flexibility）——钱能互相挪用吗

用 `dv360_list_insertion_order_flexibility` 可以读取一个 IO 的灵活性配置：

- **预算灵活性（budget flexibility）**：IO 分配给各子项的预留额度是否共享。若共享，某个 LineItem 花不完，另一条可以借用。
- **时间灵活性（time flexibility）**：排期是否允许提前/延后。

```
灵活性示意：
┌─ IO: 夏促推广 (总预算 50万) ─────────────────┐
│  灵活性: 子项之间 budget 可互相挪用(even)   │
│                                            │
│  LineItem A (预定 20万) 只花了 12万         │
│                                      ↓ 挪用
│  LineItem B (预定 20万) 可额外借用 8万      │
│            → B 实际可花 28 万               │
└────────────────────────────────────────────┘
```

好处是**弹性**，坏处是**不可控**：一旦 B 挪用后花了 A 的钱，报表层面就会出现「A 只花了 12 万、B 花了 28 万」的所谓「超预算」。排查时不要只看单条 LineItem 预算，要先看 IO 的灵活性。

### 2.2 LineItem 类型与配置原理

LineItem 的类型决定了「以什么形式去买」和「按什么计费」。

#### 2.2.1 类型（type）枚举

参考 `dv360_create_line_item` 的 `type` 参数与 Day-1 学的创意格式：

| LineItem 类型 | 说明 | 计费 | 常见出价 |
|---------------|------|------|----------|
| `DISPLAY` | 标准展示广告（横幅） | CPM | CPM / OCPM |
| `VIDEO` | 视频广告 | CPV / CPM | CPM / CPV / OCPM |
| `AUDIO` | 音频广告 | CPM | CPM |
| `NATIVE` | 原生广告 | CPM | CPM / OCPM |

> 注意：`dv360_create_line_item` 里 `type` 默认给的是 `DISPLAY`。如果要做视频前贴片，必须显式传 `VIDEO`，否则创建出来的 LineItem 根本不匹配视频创意。

#### 2.2.2 出价策略（bid strategy）

出价策略分成「固定出价」和「智能出价」两大类：

```
固定出价 (Fixed Bid)
  CPM — 每次千次展示固定出价
  CPV — 每次观看固定出价
  CPC — 每次点击固定出价

智能出价 (Automatic / Optimized)
  OCPM — 优化千次展示(按转化目标自动调价)
  CPA — 按转化成本目标出价(tCPA)
  ROAS — 按广告支出回报率出价(tROAS)
```

**关键洞察**：智能出价（OCPM/CPA）本质是让 DV360 的机器学习在**预算约束 + 目标约束**下，为每次竞价估算一个「期望转化价值」，从而动态决定该次出价。它需要：

1. Floodlight 转化追踪正确配置；
2. 至少有一定的历史转化数据（冷启动阶段效果会差）；
3. 预算要足够让模型探索（太小的预算喂不饱模型）。

| 场景 | 推荐出价 | 原因 |
|------|----------|------|
| 新品品牌曝光 | CPM | 要的是规模，不需要转化信号 |
| 效果投放已有转化数据 | OCPM/CPA | 用数据驱动压低成本 |
| 视频观看为目标 | CPV | 按完成的观看付费 |
| 电商 ROAS 目标 | tROAS | 直接对着回报率优化 |

### 2.3 Flight（投放周期）管理原理

Flight 是「时间段 + 预算」的可执行切片。它是 LineItem 实际跑量时系统逐日检验的最小单位。

#### 2.3.1 Flight 的结构

```
Flight 本质 = { 开始日期, 结束日期, 可选预算 }

LineItem 生命周期里，flight 的三种状态(可用 `dv360_list_flights` 列出)：

  A. 未来 flight (upcoming)   —— 尚未开始
  B. 当前 flight (current)    —— 正在投放
  C. 已结束 flight (past)     —— 投放完毕
```

#### 2.3.2 Flight 与 Pacing（投放速率）

DV360 按 flight 的预算和时长，算出**每日应投的速率（pacing）**，逐日控制花费，避免「月初花光、月底没量」或「某天突发超预算」。

```
Pacing 模式：
  EVEN (均匀) — 每天花差不多，最稳，适合长期保量
  ASAP (尽快) — 抢量，接近投放开始就快速花完预算
  AHEAD (提前) — 略微激进，前半程多花一点

用 `dv360_get_pacing_rate` 可读取某个 LineItem 的实时投放速率
（预算消耗速度 vs 预期），判断是否「跑快了」或「跑慢了」。
```

> 踩坑：当 LineItem 日均跑速远高于预期（比如预算一天就花了 50%），要么是 pacing 设成了 ASAP/AHEAD，要么是 flight 预算没有配置，导致系统按「尽快花完整个 IO 预算」跑。检查 flight 时务必同时看**每个 flight 是否给了明确预算**。

### 2.4 API 数据结构（真实字段）

下面是一个 LineItem 创建请求的**核心数据结构**，字段与官方 `lineItems.create` 资源一致：

```json
{
  "advertiserId": "1234567",
  "insertionOrderId": "987654",
  "name": "夏促-视频前贴片-华东",
  "entityStatus": "ENTITY_STATUS_DRAFT",
  "lineItemType": "LINE_ITEM_TYPE_DISPLAY",
  "budget": {
    "budgetUnit": "CURRENCY",
    "budgetAmountMicros": "20000000000",
    "budgetAllocationType": "FIXED",
    "dateRange": { "startDate": "2026-08-01", "endDate": "2026-08-15" }
  },
  "pacing": { "pacingPeriod": "DAILY", "pacingType": "EVEN" },
  "bidStrategy": {
    "fixedBid": { "maxBidAmountMicros": "3000000" }
  },
  "flights": [
    { "dateRange": { "startDate": "2026-08-01", "endDate": "2026-08-15" },
      "budgetAmountMicros": "20000000000" }
  ],
  "frequencyCap": { "maxImpressions": 4, "timeUnit": "TIME_UNIT_PER_DAY" },
  "targeting": {
    "includedTargeting": {
      "geo": { "geo": [ { "targetingType": "TARGETING_TYPE_GEO", "geoRegionId": "1000" } ] },
      "age": { "ageRange": [ { "targetingType": "TARGETING_TYPE_AGE", "ageRange": "AGE_RANGE_18_24" } ] }
    }
  }
}
```

对应到我们脚本里的封装：

- `dv360_create_line_item(advertiser_id, name, type='DISPLAY', ...)` —— 对应上面 body 的核心字段。
- `dv360_update_line_item(advertiser_id, line_item_id, **kwargs)` —— 后续改出价/预算/状态。
- `dv360_get_line_item(advertiser_id, line_item_id)` —— 读取完整资源核实字段。
- `dv360_list_flights(advertiser_id, line_item_id)` —— 读取 flight 列表。

### 2.5 IO↔LineItem 生命周期状态机

DV360 里实体状态用 `entityStatus` 表达，含 `ENTITY_STATUS_DRAFT`（草稿）→ `ENTITY_STATUS_ACTIVE`（活跃）→ `ENTITY_STATUS_PAUSED`（暂停）等。加上"未投放/已投放/已结束"的业务阶段，组成完整状态机：

```
                    ┌────────────────────────────┐
                    │   DRAFT (草稿)             │
                    │   只占位，不出价            │
                    └────────────┬───────────────┘
                                 │ 启动 activate
                                 ▼
                    ┌────────────────────────────┐
        resume ───► │   ACTIVE (活跃)            │────► pause
   (dv360_resume_)  │   参与竞价，跑 flight       │  (dv360_pause_)
                    └────────────┬───────────────┘
                                 │ flight 结束 / 预算耗尽
                                 ▼
                    ┌────────────────────────────┐
                    │   COMPLETED (投放完毕)      │
                    │   IO 或 LineItem 关停      │
                    └────────────────────────────┘

业务阶段并行的另一条线：
  UPCOMING (未开始) --> CURRENT (投放中) --> PAST (已结束)
  由 flight 的开始/结束时间驱动，与 entityStatus 正交。
```

**状态机的关键规则**：

1. 新建时默认 `DRAFT`（`dv360_create_line_item` 里 `status` 默认给 `DRAFT`），不会出价；
2. 必须显式置为 `ACTIVE`（`dv360_resume_line_item` / `status='ACTIVE'`）才会真正跑量；
3. `ACTIVE` 且当前时间落入某个 flight → 系统按 pacing 出价；
4. `ACTIVE` 但所有 flight 都没开始（`UPCOMING`）→ 状态活跃但"等待投放"；
5. 暂停（`PAUSED`）→ 立即停止出价，但 flight 时间照走，预算也不会自动延期；
6. IO 一旦 `PAUSED`，其下所有 LineItem 即便各自 `ACTIVE` 也不会出价（父级优先级更高）。

```
父级状态对子级的影响(优先级)：
  IO: ACTIVE         ──┐
                       ├─► LineItem 出价?  = IO状态 && LineItem状态 && flight窗口
  LineItem: ACTIVE   ──┘
  三者必须同时满足，任一不满足 → 不出价
```

### 2.6 Python：创建完整 LineItem 的端到端代码

结合 `scripts/dv360_api.py` 的 `create_campaign` / `create_insertion_order` / `create_line_item`，写出从 Campaign 开始的完整链路：

```python
# scripts/dv360_api.py 的用法示例：从 Campaign 到 LineItem 全链路
from dv360_api import DV360Client

# 假设 credentials 已从配置加载
client = DV360Client(credentials)
ADVERTISER = "1234567"   # 广告主 ID

# 1) 创建 Campaign（业务容器）
campaign = {
    "name": "2026 夏促-品牌推广",
    "advertiserId": ADVERTISER,
    "entityStatus": "ENTITY_STATUS_ACTIVE",
}
resp = client.create_campaign(ADVERTISER, campaign)
campaign_id = resp.data["campaign"]["campaignId"]
print("Campaign created:", campaign_id)

# 2) 创建 Insertion Order（IO：管钱管时间）
io = {
    "name": "夏促-IO-总盘子",
    "campaignId": campaign_id,
    "advertiserId": ADVERTISER,
    "entityStatus": "ENTITY_STATUS_ACTIVE",
    "budget": {
        "budgetUnit": "CURRENCY",
        # 50万元 = 50 * 1e6 micros
        "budgetAmountMicros": "500000000000",
        "budgetAllocationType": "PROPORTIONAL",
        "dateRange": {"startDate": "2026-08-01", "endDate": "2026-09-30"},
    },
    "pacing": {"pacingType": "EVEN"},
}
resp = client.create_insertion_order(ADVERTISER, io)
io_id = resp.data["insertionOrder"]["insertionOrderId"]
print("IO created:", io_id)

# 3) 创建 LineItem（真正的执行单元）
line_item = {
    "name": "夏促-视频前贴片-华东",
    "insertionOrderId": io_id,
    "advertiserId": ADVERTISER,
    "entityStatus": "ENTITY_STATUS_DRAFT",   # 先草稿，避免误伤
    "lineItemType": "LINE_ITEM_TYPE_DISPLAY",
    "budget": {
        "budgetUnit": "CURRENCY",
        "budgetAmountMicros": "200000000000",   # 20万
        "budgetAllocationType": "FIXED",
        "dateRange": {"startDate": "2026-08-01", "endDate": "2026-08-15"},
    },
    "pacing": {"pacingType": "EVEN"},
    "bidStrategy": {"fixedBid": {"maxBidAmountMicros": "3000000"}},
    "flights": [
        {"dateRange": {"startDate": "2026-08-01", "endDate": "2026-08-15"},
         "budgetAmountMicros": "200000000000"}
    ],
}
resp = client.create_line_item(ADVERTISER, io_id, line_item)
li_id = resp.data["lineItem"]["lineItemId"]
print("LineItem created:", li_id)
```

> 用 `scripts/dv360_api.py` 的封装时，`create_insertion_order` 和 `create_line_item` 已经把 POST 端点 `/advertisers/{adv}/insertionOrders`、`/advertisers/{adv}/insertionOrders/{io}/lineItems` 包好了，你只需要传递数据字典。

### 2.7 Go：实现工作流状态机

用一个 Go 状态机把 LineItem 的「创建 → 激活 → 暂停 → 恢复 → 关停」建模，方便在服务端做幂等控制：

```go
package main

import "fmt"

// LineItemState 定义 LineItem 的实体状态
type LineItemState string

const (
	StateDraft     LineItemState = "ENTITY_STATUS_DRAFT"
	StateActive    LineItemState = "ENTITY_STATUS_ACTIVE"
	StatePaused    LineItemState = "ENTITY_STATUS_PAUSED"
	StateCompleted LineItemState = "ENTITY_STATUS_COMPLETED"
)

// transition 是状态迁移表：from -> 合法 to 集合
var transition = map[LineItemState][]LineItemState{
	StateDraft:     {StateActive, StatePaused},
	StateActive:    {StatePaused, StateDraft},
	StatePaused:    {StateActive},
	StateCompleted: {}, // 终态，不可再转
}

func canTransition(from, to LineItemState) bool {
	for _, s := range transition[from] {
		if s == to {
			return true
		}
	}
	return false
}

func main() {
	li := StateDraft
	fmt.Printf("初始: %s\n", li)

	// 尝试直接跳到 Paused（非法）
	if canTransition(li, StatePaused) {
		li = StatePaused
	} else {
		fmt.Println("DRAFT -> PAUSED 非法，需先激活")
	}

	// 合法路径: DRAFT -> ACTIVE -> PAUSED -> ACTIVE
	if canTransition(li, StateActive) {
		li = StateActive
		fmt.Println("已激活:", li)
	}
	if canTransition(li, StatePaused) {
		li = StatePaused
		fmt.Println("已暂停:", li)
	}
	if canTransition(li, StateActive) {
		li = StateActive
		fmt.Println("已恢复:", li)
	}
}
```

> 生产上：状态迁移前先调用 `dv360_get_line_item` 拉真实状态，再决定是否 `dv360_pause_line_item` / `dv360_resume_line_item`，避免重复暂停/恢复造成 400 报错。


---

## 三、生产环境实战

### 3.1 从 0 到投放的实操流程（建 Campaign → IO → LineItem → 绑创意 → 启动）

完整流程用一张流程图串起来，再配逐步代码。**每步都强调"先验证再继续"**，这是生产环境最重要的纪律。

```
从0到投放的标准流水线

 Step1   Check: 校验广告主/时区/币种/Floodlight 配置
         ↓
 Step2   Create Campaign —— 业务容器
         ↓  校验 campaignId
 Step3   Create IO —— 定总预算/排期窗口/预算分配/灵活性
         ↓  校验 ioId + 读灵活性(dv360_list_insertion_order_flexibility)
 Step4   Create LineItem(一个或多个) —— 定出价/定向/flight
         ↓  校验 lineItemId + 读 flights(dv360_list_flights)
 Step5   绑创意(creativeIds) —— 确保创意已审批通过
         ↓  校验创意状态
 Step6   全员 ACTIVE —— 启动
         ↓  用 dv360_get_pacing_rate 观察是否正常跑量
 Step7   投放中 —— 监控/优化/暂停恢复
```

#### Step1-3 真实代码（校验 + 建 Campaign + 建 IO）

```python
# Step1: 先验证广告主与配置（防止建到错误主体上）
advertisers = client.list_advertisers(PARTNER)   # dv360_list_advertisers
# 确认目标广告主存在于返回列表中

# Step2: 建 Campaign
campaign_resp = client.create_campaign(ADVERTISER, {...如上章...})
campaign_id = campaign_resp.data["campaign"]["campaignId"]

# Step3: 建 IO
io_resp = client.create_insertion_order(ADVERTISER, {...如上章...})
io_id = io_resp.data["insertionOrder"]["insertionOrderId"]

# 校验 IO 的灵活性（决定子项预算能否挪用，直接影响后续排期）
flex = client.dv360_list_insertion_order_flexibility(io_id)
print("IO flexibility:", flex)
```

#### Step4-6 真实代码（建 LineItem + 绑创意 + 启动）

```python
# Step4: 建 LineItem（多个同构 LineItem 用循环批量建）
li_ids = []
for name in ["夏促-视频前贴片-华东", "夏促-视频前贴片-华南", "夏促-展示-全国"]:
    li = {
        "name": name,
        "insertionOrderId": io_id,
        "advertiserId": ADVERTISER,
        "entityStatus": "ENTITY_STATUS_DRAFT",
        "lineItemType": "LINE_ITEM_TYPE_VIDEO",
        "budget": {"budgetUnit": "CURRENCY",
                   "budgetAmountMicros": "200000000000",
                   "budgetAllocationType": "FIXED",
                   "dateRange": {"startDate": "2026-08-01", "endDate": "2026-08-15"}},
        "pacing": {"pacingType": "EVEN"},
        "bidStrategy": {"fixedBid": {"maxBidAmountMicros": "3000000"}},
        "flights": [{"dateRange": {"startDate": "2026-08-01", "endDate": "2026-08-15"},
                     "budgetAmountMicros": "200000000000"}],
    }
    resp = client.create_line_item(ADVERTISER, io_id, li)
    li_ids.append(resp.data["lineItem"]["lineItemId"])

# Step5: 绑创意。先确认创意已审批(APPROVED)，未审批绑不上
creatives = client.list_creatives(ADVERTISER, li_ids[0])
approved = [c["creativeId"] for c in creatives
            if c.get("creativeStatus") == "APPROVED"] if creatives else []
# 用 dv360_update_line_item 把 approved 创意绑定到每个 LineItem
for li_id in li_ids:
    client.dv360_update_line_item(ADVERTISER, li_id, creativeIds=approved) \
        if hasattr(client, 'dv360_update_line_item') else None

# Step6: 全部激活启动
for li_id in li_ids:
    client.dv360_resume_line_item(ADVERTISER, li_id)   # status -> ACTIVE

# Step7: 观察投放速率，确认在正常节奏
pacing = client.dv360_get_pacing_rate(ADVERTISER, li_ids[0])
print("pacing:", pacing)
```

> 上面的 `client` 在真实项目里可以是 `ad_platform_api` 的统一客户端（`dv360_*` 方法）或 `dv360_api.DV360Client` 的封装，二者混用只是示例——生产环境请统一一个入口。

### 3.2 批量创建案例（mass creation）

当一单 IO 下面需要几十上百个 LineItem（比如按城市/按店铺/按素材拆）时，手工一个个创建不可行。套路：**先建 Lane 模板，再用循环+批量接口铺开**。

```
批量创建的分层思想：
  IO (总盘子，1 个)
   └── LineItem 模板 (先建 1 个作为"样式样本")
         └── 用模板复制 N 个 (改名字/改定向/改预算)
```

#### 批量 + 批量更新

```python
import itertools

base_names = ["华东", "华南", "华北", "西南"]          # 地域维度
creative_variants = ["v1", "v2"]                        # 素材维度

li_ids = []
for region, variant in itertools.product(base_names, creative_variants):
    li = {
        "name": f"夏促-{variant}-{region}",
        "insertionOrderId": io_id,
        "advertiserId": ADVERTISER,
        "entityStatus": "ENTITY_STATUS_DRAFT",
        "lineItemType": "LINE_ITEM_TYPE_DISPLAY",
        "budget": {"budgetUnit": "CURRENCY",
                   "budgetAmountMicros": "50000000000",   # 5万/条
                   "budgetAllocationType": "FIXED",
                   "dateRange": {"startDate": "2026-08-01", "endDate": "2026-08-15"}},
        "bidStrategy": {"fixedBid": {"maxBidAmountMicros": "3000000"}},
        "flights": [{"dateRange": {"startDate": "2026-08-01", "endDate": "2026-08-15"},
                     "budgetAmountMicros": "50000000000"}],
    }
    resp = client.create_line_item(ADVERTISER, io_id, li)
    li_ids.append(resp.data["lineItem"]["lineItemId"])

# 批量更新（改出价/暂停等）：dv360_batch_update_line_items 收集一批 diff
updates = []
for li_id in li_ids:
    updates.append({"lineItemId": li_id,
                    "bidStrategy": {"fixedBid": {"maxBidAmountMicros": "5000000"}}})
result = client.dv360_batch_update_line_items(updates)
print("batch update:", result)
```

> 踩坑：批量更新时，如果 `updates` 里混有已经 `PAUSED` 的 LineItem 又想改它，DV360 会返回部分成功（partial success）。**一定要解析批量响应的 per-item 结果**，把失败的挑出来单独重试，不能当整批全成功。

### 3.3 排期管理：Flight 拆分与暂停恢复

#### 3.3.1 多 Flight 排期

一个常见的真实需求：同一素材先打一波（拉新），停一周，再打一波（促活）。这就要在**同一个 LineItem 上配两个 flight**：

```
LineItem: 夏促-双波段
  flight1: 08-01 ~ 08-10   (拉新冲刺)
  空窗:   08-11 ~ 08-20   (暂停不投，素材发酵)
  flight2: 08-21 ~ 08-30   (促活召回)
```

创建时 `flights` 数组放两个元素，但**两个 flight 不能重叠**。若需要中间空窗，直接不排 flight 即可（空窗期该 LineItem 即使 ACTIVE 也不出价，因为没有任何当前 flight）。

```python
li = {
    "name": "夏促-双波段",
    "insertionOrderId": io_id,
    "advertiserId": ADVERTISER,
    "entityStatus": "ENTITY_STATUS_ACTIVE",
    "lineItemType": "LINE_ITEM_TYPE_DISPLAY",
    "bidStrategy": {"fixedBid": {"maxBidAmountMicros": "3000000"}},
    "flights": [
        {"dateRange": {"startDate": "2026-08-01", "endDate": "2026-08-10"},
         "budgetAmountMicros": "100000000000"},   # 波段1：10万
        {"dateRange": {"startDate": "2026-08-21", "endDate": "2026-08-30"},
         "budgetAmountMicros": "100000000000"},   # 波段2：10万
    ],
}
```

#### 3.3.2 手动暂停/恢复的两种方式

**方式 A：更新 entityStatus**（推荐，最标准）

| 操作 | 方法 | 效果 |
|------|------|------|
| 暂停 | `dv360_pause_line_item(adv, li_id)` → `status='PAUSED'` | 立即停投 |
| 恢复 | `dv360_resume_line_item(adv, li_id)` → `status='ACTIVE'` | 重新参与竞价 |

**方式 B：改 flight / 预算**（软暂停）

有时不想动状态（避免审批链），而是把预算或 flight 调成 0 / 往后挪，实现"软暂停"。但要注意：**改 flight 生效可能需要几分钟同步**，不像 entityStatus 那样即时。

```
暂停的两种力度：
  硬暂停 (entityStatus=PAUSED) —— 立即、彻底、恢复也快
  软暂停 (flight后移/预算=0)   —— 温和、可用于"hold"但生效延迟
```

> 关键差异表：硬暂停不保留"当前 flight 剩余预算"的投放节奏，恢复后会重新起账；软暂停则希望飞行时间顺延。语义不同，按需选择。

### 3.4 踩坑实录（真实经验）

这里收集我实际踩过的坑，按严重程度排序：

#### 坑1：金额用了"元"而非"微单位" 🔴

```python
# ❌ 错误：直接填了 5000（元）
"budgetAmountMicros": "5000"
# ✅ 正确：50万 => 500000*1e6
"budgetAmountMicros": "500000000000"
```
5 万块被写成 5 块，预算肉眼可见地"见底"。**所有金额字段都必须 ×1,000,000**，写个工具函数封装转换。

#### 坑2：LineItem 建完是 DRAFT 却"看不到量" 🔴

新建的 LineItem `entityStatus` 默认 `DRAFT`，**DRAFT 不出价**。很多配置看着都对，就是没量，一查状态还是 DRAFT。必须显式 `dv360_resume_line_item`（置 ACTIVE）。

```
排查"没量"的铁律顺序：
 1) entityStatus == ACTIVE ?
 2) 父级 IO == ACTIVE ?（IO 暂停会压死所有子项）
 3) 当前时间是否落在某个 flight 内 ?
 4) 创意是否绑定且已 APPROVED ?
 5) 定向是否过窄导致没库存 ?
 6) pacing 是否过快已把预算打穿 ?
```

#### 坑3：同一 LineItem 的 flight 重叠 🟠

```
❌ flight1: 08-01~08-15
   flight2: 08-10~08-25   ← 重叠了！
✅ flight1: 08-01~08-15
   flight2: 08-21~08-30   ← 不重叠
```
重叠 flight 创建会被拒绝或行为异常。创建前按日期排序校验相邻 flight 首尾不重叠。

#### 坑4：创意未关联 / 未审批就激活 🟠

LineItem 激活时若没有已审批的创意，会进入"无素材可投"状态，白跑不产出。**先绑创意并确认 APPROVED，再激活**。

#### 坑5：IO 预算不足 🟠

LineItem 预算总和超过 IO 总预算时，财务/预算校验会失败。用 `dv360_list_insertion_orders` 先读 IO `budget`，`sum(LineItem_budget) <= IO_budget` 再动工。

#### 坑6：灵活性导致的"超预算"假象 🟡

IO 开了子项预算共享（flexibility），某子项花超、别子项挪用，报表出现单条超预算。排查时先关掉 flexibility 或下调分配。

#### 坑7：暂停后 flight 时间照走 🟡

`PAUSED` 只是停出价，**flight 的日历照常往前走**。恢复时如果原 flight 已结束，需要**新建/后移 flight**，否则恢复也是空的（没 flight 覆盖当前时间）。

| 坑 | 优先级 | 一句话解决 |
|----|--------|-----------|
| 金额没乘 1e6 | 🔴 | 封装 micros 转换函数 |
| LineItem 停留 DRAFT | 🔴 | 显式置 ACTIVE |
| flight 重叠 | 🟠 | 校验相邻 flight 日期 |
| 创意未绑/未批 | 🟠 | 先绑+等 APPROVED 再激活 |
| IO 预算不足 | 🟠 | sum(budget) <= IO budget |
| 灵活性超预算假象 | 🟡 | 检查 IO flexibility |
| 暂停后 flight 过期 | 🟡 | 恢复前新建/后移 flight |


---

## 四、常见问题与排查

### 4.1 FAQ 总表（先看结论）

| # | 问题 | 一句话答案 | 详细排查 |
|---|------|-----------|---------|
| 1 | IO 显示 ACTIVE 但没量 | 检查子级 LineItem 是否 ACTIVE、flight 是否覆盖当前时间 | 见 4.2 |
| 2 | LineItem 不出量 | 按"铁律顺序"逐项排查状态/父级/flight/创意/定向/pacing | 见 4.3 |
| 3 | 两个 flight 同时生效 | flight 重叠，创建时就要校验 | 见 4.4 |
| 4 | 预算"超花"或"不够" | 检查 micros 换算、IO 灵活性、子项总和 | 见 4.5 |
| 5 | 创意绑定失败 | 创意未审批 / ID 不属于该广告主 / 格式不匹配 | 见 4.6 |
| 6 | 暂停了还在扣钱 | 暂停有延迟、或还有"在途"曝光结算 | 见 4.7 |
| 7 | 恢复后仍不跑 | flight 已结束需重建 / IO 仍暂停 | 见 4.8 |

### 4.2 FAQ1：IO 状态与"没有量"

```
诊断流程（IO 维度）：
  dv360_list_insertion_orders(adv)
    → 找到目标 IO
    → 读 entityStatus
       ├─ 非 ACTIVE        → 置 ACTIVE（dv360_resume 对应 IO）
       ├─ ACTIVE 但子项全 DRAFT → 子项逐个激活
       └─ ACTIVE 且子项 OK → 看 flight 是否覆盖当前日期
```

### 4.3 FAQ2：LineItem 不出量的五步排查

用 `dv360_get_line_item` 和 `dv360_list_flights` 拉数据，按下面表格逐项核对：

| 步骤 | 检查项 | 数据来源 | 通过标准 |
|------|--------|----------|---------|
| 1 | entityStatus | `dv360_get_line_item` | `ACTIVE` |
| 2 | 父级 IO 状态 | `dv360_list_insertion_orders` | `ACTIVE` |
| 3 | flight 覆盖今天 | `dv360_list_flights` | 存在 current flight |
| 4 | 创意已绑定且 APPROVED | `dv360_list_creatives` | creativeStatus=APPROVED |
| 5 | pacing 未打穿预算 | `dv360_get_pacing_rate` | 消耗 < 100% 且未异常 |

```
示例排查输出（伪代码）：
  li = dv360_get_line_item(adv, li_id)
  if li["entityStatus"] != "ENTITY_STATUS_ACTIVE":
      print("先激活:", li_id)
  flights = dv360_list_flights(adv, li_id)
  today = "2026-08-10"
  if not any(f["dateRange"]["startDate"] <= today <= f["dateRange"]["endDate"]
             for f in flights):
      print("当前无有效 flight，需要新建/后移 flight")
```

### 4.4 FAQ3：Flight 冲突（重叠 / 超窗）

Flight 校验规则：

1. 同一 LineItem 内 flight 不能重叠；
2. 每个 flight 必须在所属 IO 的 dateRange 之内；
3. 同一时间点只能有一个 current flight。

```python
def check_flight_overlap(flights):
    """返回第一个重叠对；无重叠返回 None"""
    ordered = sorted(flights, key=lambda f: f["dateRange"]["startDate"])
    for i in range(len(ordered) - 1):
        a_end = ordered[i]["dateRange"]["endDate"]
        b_start = ordered[i + 1]["dateRange"]["startDate"]
        if b_start <= a_end:      # 后一个的开始 ≤ 前一个的结束 → 重叠
            return (ordered[i], ordered[i + 1])
    return None
```

> 若 IO 的排期窗口是 08-01~09-30，而某个 LineItem 的 flight 写到了 10-05，创建会被拒。**flight 永远不能越出 IO 的墙**。

### 4.5 FAQ4：预算类问题

#### 4.5.1 金额换算排查

```
常见翻车点：
  预算字段用了"元/美元"原值  → 应 ×1e6 微单位
  出价字段 maxBidAmountMicros 同理会犯
  → 统一走 micros 工具函数
```

#### 4.5.2 超预算 / 挪用排查

```
现象：报表里 LineItem B 花费 > 它的预算
排查：dv360_list_insertion_order_flexibility(io_id)
      → 若 flexibility 允许挪用，B 借用了 A 的额度 → 属正常现象
处理：按需求下调 flexibility 或调整 A/B 分配比例
```

### 4.6 FAQ5：创意绑定失败

| 失败原因 | 表现 | 解决 |
|----------|------|------|
| 创意还在 PENDING_REVIEW | 绑定后不出量 | 等审批通过 |
| 创意被拒（REJECTED） | 绑定报错 | 修改素材重新上传 |
| 创意不属于该广告主 | 404/权限错误 | 用对 advertiserId |
| 创意格式与 LineItem 类型不匹配（如视频创意绑到 DISPLAY） | 运行时无库存 | 匹配 type |

### 4.7 FAQ6：暂停了还在扣钱

暂停（`dv360_pause_line_item`）是**尽力而为**的：已进入结算的在途曝光/点击仍会计费，报表同步也有延迟。若想"秒停"，还需要配合：IO 也暂停 + 把 flight 预算降为 0 + 停止素材服务。

```
"秒停"组合拳（按效果递减）：
  1. pause LineItem  (立即停新竞价)
  2. pause IO        (封死整条链路)
  3. flight 预算=0   (从源头掐预算)
  4. 等报表同步      (在途量清算)
```

### 4.8 FAQ7：恢复后仍不跑

`dv360_resume_line_item` 恢复的是 `entityStatus`，**不恢复 flight**。如果原 flight 已结束，恢复后没有任何 current flight，依然不出量。

```python
# 恢复前先看 flight 状态
flights = dv360_list_flights(adv, li_id)
if 无 current flight:
    # 需要调用 update 重建 flight 或把结束日期后移
    dv360_update_line_item(adv, li_id,
        flights=[{"dateRange": {"startDate": "2026-08-01",
                                "endDate": "2026-08-31"},
                  "budgetAmountMicros": "..."}])
# 再恢复
dv360_resume_line_item(adv, li_id)
```

---

## 五、自测题

### 题1（概念）：IO 和 LineItem 的职责边界

用不超过 3 句话说明：为什么 DV360 要分成 IO 和 LineItem 两层，而不是一层？

<details><summary>查看答案</summary>

**答**：IO 是"合同层"——管总预算、总排期窗口和业务目标，是花钱的上限与方向；LineItem 是"执行层"——管每一次竞价的出价、定向、创意和 flight。分层让"资金审批"与"投放执行"解耦：预算审批只看 IO，执行优化只动 LineItem，二者各自独立变更、互不牵连，同时父级又能在全局暂停时一键压死所有子项。
</details>

### 题2（数值）：micros 换算

一个 LineItem 的出价上限要设成 3.5 元，`maxBidAmountMicros` 应该填多少？如果误填成 `3500000`，实际出价是多少？

<details><summary>查看答案</summary>

**答**：3.5 元 × 1,000,000 = **3,500,000 micros**。误填 3,500,000 反而是正确值本身——真正容易犯的错是把 3.5 直接填成 `3` 或 `350`。换算口诀：**所有金额字段一律 ×1,000,000**，并在代码里封装 `yuan_to_micros()` 工具函数，禁止手写。
</details>

### 题3（状态机）：为什么 LineItem 配置全对却不跑量？

一个 LineItem：entityStatus=ACTIVE、IO=ACTIVE、创意已 APPROVED、定向也正常，但就是不出量。最可能的原因是什么？如何验证？

<details><summary>查看答案</summary>

**答**：最可能是**当前时间没有落在任何 flight 内**（例如 flight 还未开始或已结束）。验证方法：调用 `dv360_list_flights(advertiser_id, line_item_id)`，检查是否存在覆盖今天的 current flight；若没有，则需要新建或后移 flight。第二个可能原因是 pacing 把预算提前打穿，可用 `dv360_get_pacing_rate` 查看消耗节奏。
</details>

### 题4（排查）：IO 暂停的影响范围

如果 IO 被暂停（PAUSED），其下某个 LineItem 恰好是 ACTIVE 且处于当前 flight，它会继续出价吗？

<details><summary>查看答案</summary>

**答**：不会。父子状态的语义是 AND 关系：**IO 状态 && LineItem 状态 && flight 覆盖当前时间**，三者必须同时满足才会出价。IO 暂停会像"总闸"一样压死下面所有子项，即使子项各自 ACTIVE 也不会参与竞价。恢复时也要先恢复 IO，再逐条恢复 LineItem。
</details>

### 题5（实战）：多 flight 排期的正确姿势

要做一个"拉新（08-01~08-10）→ 停 10 天 → 促活（08-21~08-30）"的双波段投放，应该怎么配 flight？直接配两个重叠 flight 会怎样？

<details><summary>查看答案</summary>

**答**：在同一个 LineItem 的 `flights` 数组里配置两个**不重叠**的 flight：`08-01~08-10` 和 `08-21~08-30`，中间 10 天没有 flight 覆盖，系统自然空窗不投。如果配成重叠（如 `08-01~08-15` 和 `08-10~08-25`），创建会被拒绝或行为异常——创建前用日期排序校验相邻 flight 首尾不重叠（`b_start <= a_end` 即冲突）。
</details>

---

## 六、总结与下一步

### 6.1 今日要点回顾

```
Day-2 收获清单：
  ✅ IO = 合同层（总预算/排期窗口/目标/灵活性）
  ✅ LineItem = 执行层（出价/定向/创意/频控/flight）
  ✅ 父子状态 AND 语义 + 状态机(DRAFT→ACTIVE→PAUSED→COMPLETED)
  ✅ 金额一律 ×1e6 micros
  ✅ flight 不重叠、不越 IO 窗
  ✅ 7 个真实踩坑及解法
```

### 6.2 下一步建议

- **Day-3 预告**：创意上传、审批流转与品牌安全（承接本笔记"创意未审批就激活"的坑）。
- 实战建议：用 `scripts/dv360_api.py` 在你的测试广告主下建一个"微型 IO + 2 个 LineItem"，完整跑一遍创建→激活→暂停→恢复→关停，把状态机变成肌肉记忆。
- 排查工具箱：`dv360_get_line_item`（单查）、`dv360_list_flights`（flight 视图）、`dv360_get_pacing_rate`（节奏）、`dv360_list_insertion_order_flexibility`（预算挪用）、`dv360_batch_update_line_items`（批量改）。

> 本篇为学习笔记，与 `dv360-media-buying-deep.md` 等深度文档互为补充：深度文档给原理，本笔记给"今天就能照着做的路"。遇到 API 细节问题，回查 `dv360-marketing-api-deep.md` 与官方文档：https://developers.google.com/display-video/api/reference/rest/v4
