# DV360 媒体购买全流程深度解析（IO / LineItem / 创意 / 出价 / 排期 / 预算）

> **领域**: 广告投放 / 媒体购买
> **深度**: ⭐⭐⭐⭐⭐ 实战级指南
> **标签**: dv360, media-buying, insertion-order, line-item, flight, budget
> **更新时间**: 2026-08-14
> **类型**: 深度文档

---

本文将 DV360（Display & Video 360）从 "媒体购买" 的角度做一次端到端的拆解。与同目录下其它文档的分工如下：

| 文档 | 侧重点 | 与本文的关系 |
|------|--------|--------------|
| `dv360-architecture-deep.md` | 平台概述、RTB 生态、账户层级、Go 广告请求引擎 | 本文聚焦媒体购买全流程，架构图更细到 "可执行" |
| `dv360-optimization-deep.md` | 投放策略、预算分配、智能出价优化 | 本文补充预算模型 / pacing / 排期的机制层细节 |
| `dv360-marketing-api-deep.md` | API 端点、认证、客户端封装 | 本文给出可直接复刻的 Python/Go 源码客户端 |
| `dv360-creative-brand-safety-deep.md` | 创意格式、品牌安全、可见性 | 本文只讲创意与 LineItem 的关联、上传与审批流转 |
| `dv360-measurement-attribution-deep.md` | 归因、转化追踪 | 本文不展开归因，只引用 floodlight 配置 |
| **本文** | **媒体购买全流程** | **IO → LineItem → Creative → 出价 → 排期 → 预算的完整闭环** |

核心问题贯穿全文：**"一笔钱怎么按结构、按时间、按节奏精确地花出去，并且能被 API 完整地创建、查询、暂停、恢复和排错。"**

---

## 一、核心概念与架构

### 1.1 媒体购买的完整层级图

DV360 的账户树从上到下依次是：Partner → Advertiser → Campaign → Insertion Order → Line Item → Creative。每一个层级都有严格的生命周期和归属约束，任何一次 API 调用都必须携带正确的父级 ID 才能定位实体。先用一张 ASCII 图把全貌铺开：

```
┌──────────────────────────────────────────────────────────────────────┐
│                           Partner (合作伙伴)                           │
│   拥有多重货币、时区、出价结算属性；是整个账户树的根                    │
├──────────────────────────────────────────────────────────────────────┤
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │                    Advertiser (广告主)                          │  │
│  │   计费主体：人民币/美元/欧元；拥有自己的 floodlight 配置          │  │
│  │   API 资源路径: /advertisers/{advertiserId}                    │  │
│  │                                                                │  │
│  │  ├── Campaign (广告系列)                                      │  │
│  │  │    业务目标容器：曝光、转化、品牌                                          │  │
│  │  │    API: /advertisers/{adv}/campaigns/{campaignId}           │  │
│  │  │                                                                │  │
│  │  │  └── Insertion Order (IO, 订单项 / 媒体采购单)              │  │
│  │  │       花钱的"合同"，含总预算、排期窗口、预算分配、灵活性      │  │
│  │  │        API: /advertisers/{adv}/insertionOrders/{ioId}       │  │
│  │  │                                                              │  │
│  │  │        └── Line Item (线条项目 / 媒体购买)                  │  │
│  │  │             真正参与竞价的最小逻辑单元，含出价、定向、排期     │  │
│  │  │              API: /advertisers/{adv}/insertionOrders/{io}/   │  │
│  │  │                    lineItems/{lineItemId}                    │  │
│  │  │                                                              │  │
│  │  │              └── Creative (创意)                            │  │
│  │  │                    通过 LineItem 关联上传的素材，参与审批      │  │
│  │  │                     API: /advertisers/{adv}/creatives/       │  │
│  │  │                          {creativeId}                        │  │
│  │  │                                                              │  │
│  │  │  Flight (投放周期) = 是 LineItem 的"时间段 + 预算" 视图      │  │
│  │  │        在 DV360 中 LineItem 可以拆成多个 flight 排期         │  │
│  │  └── Floodlight / Audiences / Placements / 定向数据源          │  │
│  └────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
```

### 1.2 官方 API 资源路径 vs. 常见误区

很多初学者把 "IO" 和 "Campaign" 混为一谈。这里给一张对照表，并标注对应的真实 API 方法名（来自 `dv360_api.py` 的 `DV360Client` 类与 `ad_platform_api.py` 的 `dv360_*` 系列）：

| 层级 | 语义 | 所属父级 | 关键字段 | dv360_api.py | ad_platform_api.py |
|------|------|----------|----------|--------------|--------------------|
| Partner | 合作伙伴/代理商账户 | 无（根） | 默认货币/时区 | `list_advertisers(partner_id)` | `dv360_list_advertisers` |
| Advertiser | 广告主（计费主体） | Partner | currency_code, partner_id | `get_advertiser` | `dv360_get_advertiser`, `dv360_validate_advertiser` |
| Campaign | 广告系列（业务目标） | Advertiser | goal, budget | `list_campaigns`, `create_campaign`, `pause_campaign` | `dv360_list_campaigns` 系列 |
| IO | 订单项/媒体采购单（花钱合同） | Advertiser | budget, frequency_cap, targeting | `list_insertion_orders`, `create_insertion_order` | `dv360_list_insertion_orders`, `dv360_list_insertion_order_flexibility` |
| Line Item | 线条项目/媒体购买（竞价单元） | IO | type, flight, bid, targeting | `list_line_items`, `create_line_item` | `dv360_create_line_item`, `dv360_update_line_item`, `dv360_get_pacing_rate` |
| Creative | 创意素材 | Line Item | format, media_file | `list_creatives`, `create_creative` | `dv360_create_creative`, `dv360_list_creatives` |

**要点**：Campaign 与 IO 是一对多；IO 与 Line Item 是一对多；Line Item 与 Creative 是一对多（但 Creative 先在 advertiser 级创建，再挂到 LineItem 上）。

### 1.3 IO 与 Line Item 的关系 —— 谁是"合同"，谁是"执行"

这是媒体购买中最容易混淆的一层，也是团队里 PM（媒介采购）与优化师最容易吵架的分界：

- **IO（Insertion Order）** 是**合同 / 下单层面**的实体：它定义了一笔媒体购买的**总预算**、**排期窗口（start/end）**、**频率上限**、**预算分配的灵活性（flexibility）**。它自己**不直接竞价**，只是把一笔钱"框"起来。
- **Line Item（线条项目）** 是**执行 / 竞价层面**的实体：它定义**用什么类型的库存**（PG/PMP/Open Auction）、**出价策略与出价金额**、**定向**、以及**具体的 flight 时间段与预算**。真正进拍卖的是 Line Item，不是 IO。
- **Flight** 是 Line Item 的**拆段投放**：同一个 Line Item 可以有多个 flight，每个 flight 各有一段时间窗口与一份预算，从而把总量按阶段切分（例如预热期 / 爆发期 / 收尾期）。

用一张 "谁负责什么" 的表：

| 维度 | IO 负责 | Line Item 负责 | Flight 负责 |
|------|---------|----------------|-------------|
| 预算 | 总预算（IO level） | 每个 Line Item 的预算上限 | 每个 flight 的段预算 |
| 时间 | IO 起止日期（整体窗口） | Line Item 起止 | flight 的细分起止 |
| 竞价 | 不竞价 | 出价策略 + 出价金额 | 只切时间，不切竞价 |
| 定向 | 很少放（一般留空给子级） | 核心定向全在这 | 无定向 |
| 频率 | frequency_cap（IO 级跨 LineItem） | 可另设 | 无 |

### 1.4 交易类型与媒体购买类型（transaction type）

Line Item 的 `type`（交易类型）决定了它如何获取库存。下面的枚举来自 `dv360_api.py` 的 `get_transaction_type_options()`：

```
PROGRAMMATIC_GUARANTEED  →  程序化保量（保证量 + 固定 CPM，直接与 publisher 谈）
PRIVATE_MARKETPLACE     →  私有市场（邀请制优质库存，竞价但排除开放竞争）
PREFERRED_DEAL          →  优先交易（publisher 优先给 DV360 选择权，非保量）
OPEN_AUCTION            →  公开竞价（Google AdX 及开放式交易所，动态出价）
```

| 类型 | 保量？ | 计价 | 适用场景 | 特点 / 坑 |
|------|--------|------|----------|-----------|
| PROGRAMMATIC_GUARANTEED | ✅ 保证 | 固定 CPM | 大促保量、品牌曝光、重点 Deal | 剂量必须精确，否则要么赔钱要么量不足 |
| PRIVATE_MARKETPLACE | ❌（但竞争小） | 动态 CPM | 品牌安全优先、优质库存 | 流跌价快，pacing 容易跟不上 |
| PREFERRED_DEAL | 🟡 优先权 | 动态 CPM | 优质位置优先测试 | 非保量，可能饿死 |
| OPEN_AUCTION | ❌ | 动态 CPM | 效果投放、量大便宜 | pacing 波动大，需广告主合理出价 |

### 1.5 预算模型：三层预算谁说了算

DV360 的预算有明确的层级与优先级。理解这条链，是避免 "预算超支 / 少投" 的关键：

```
IO 总预算（Budget of Insertion Order）
   ↓ 约束下属
Line Item 预算（每个 LineItem 各有 budget）
   ├── 总预算（无 flight 拆分时）  ← 最常见
   └── 按 flight 拆分：flight1 预算 + flight2 预算 = LineItem 预算上限
```

**预算优先级（谁能 limit 谁）**：

1. **IO 预算** 是所有子 Line Item 的**总上限**——即使所有 Line Item 单独设了大预算，IO 一收紧，整体就被卡住。
2. **Line Item 预算** 是单条 Line Item 的独立上限。
3. **Flight 预算** 是 Line Item 在某一段时间的上限。

> 实务坑：很多团队只调 Line Item 预算而忘了 IO 预算没放大，导致 "看起来预算加满了但整体就是放不出来"，这就是经典的 **IO 预算成为隐性瓶颈**。

### 1.6 排期模型：单一窗口 vs. flight 拆段

Line Item 有**两种时间模型**，媒体购买团队必须一开始就定好，因为中途改窗口会影响 pacing 与预算均摊：

| 模型 | 说明 | 典型场景 | 风险 |
|------|------|----------|------|
| 单一窗口 | LineItem 一个 start/end，预算在整个窗口均摊 | 常规月投放 | pacing 波动会集中在收尾 |
| 多 flight | 一个 LineItem 多个 flight，各自窗口+预算 | 双11预热/爆发/返场 | flight 之间衔接断层、重复计费 |

flight 的时间与预算拆分的 ASCII 示意：

```
LineItem: "双11 大促全量"
├── Flight 1 预热   : 11-01 ~ 11-09  预算 30%   (探量、蓄水)
├── Flight 2 爆发   : 11-10 ~ 11-11  预算 50%   (主战场，高 COP)
└── Flight 3 返场   : 11-12 ~ 11-15  预算 20%   (清尾、再营销)
```

至此我们建立了整个媒体购买的骨架：**IO 管钱，Line Item 管竞价，Flight 切时间，Creative 提供素材，Budget/Pacing 决定钱怎么花，出价策略决定花多少钱换多少量。** 下一章深入每个机制的原理与可执行代码。

---
