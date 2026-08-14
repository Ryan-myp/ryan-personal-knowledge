# 私有市场交易（PMP）深度指南（Day 6）

> **领域**: 广告投放 / 私有市场
> **深度**: ⭐⭐⭐⭐⭐ 实战级指南
> **标签**: dv360, pmp, private-marketplace, deal, preferred-deal
> **更新时间**: 2026-08-14
> **类型**: 学习笔记

---

## 一、核心概念与架构

### 1.1 什么是 PMP（Private Marketplace，私有市场）

私有市场（PMP，Private Marketplace）是**邀请制**的程序化交易模式：发布商（Publisher / Seller）把一部分**优质库存**（Premium Inventory）从公开竞价市场隔离出来，仅对**受邀的少数买方**（DSP / Advertiser）开放竞价。买方通过一个**私有交易（Private Deal）**拿到访问这批库存的"入场券"，用**固定的底价（Floor Price）**和邀请环境参与竞价。

PMP 的本质是"把公开竞价的两个缺点修复掉"：

| 公开竞价的缺点 | PMP 的解决方案 |
|--------------|--------------|
| 库存质量参差不齐（长尾、低质、欺诈窗口大） | 发布商手动圈定优质广告位，质量可控、可附带品牌安全上下文 |
| 无底价保护，优质库存被低价买到 | 每个 deal 带固定 floor，低于底价不成交，保护发布商收入 |
| 买方与发布商无直接关系，拿不到一手数据 | 直接向受邀买方开放，可共享受众、上下文、价格与排期信息 |
| 普通买方可能被品牌安全策略挡在外面 | PMP 是品牌旗舰投放最常用的"安全 + 优质"组合 |

从 DV360 事务类型（transaction type）的官方视角看，DV360 把所有采购方式分成四类，PMP 是其中一种：

| transaction type 代码 | 名称 | 简述 |
|---------------------|------|------|
| `PROGRAMMATIC_GUARANTEED` | 程序化保量（PG） | 保证展示量与费用的固定交易 |
| `PRIVATE_MARKETPLACE` | 私有市场（PMP） | 邀请制、有底价、多买方竞价的优质库存交易 |
| `PREFERRED_DEAL` | 优先交易（Preferred Deal） | 单一买方有优先购买权、"先到先得"的非竞拍交易 |
| `OPEN_AUCTION` | 公开竞价（Open Auction） | 常规公开市场竞价，任何人都可以参与 |

这些在 `get_transaction_type_options()` 里被一一返回，是 DV360 官方认可的枚举值，也对应 `dv360_create_line_item(..., type=...)` 里可以选择的 `type`。**理解这四种类型，是把 DV360 用好的一半**——很多"跑到一半没量/成本失控"的问题，根源都是交易类型选错了。

### 1.2 为什么要用 PMP：价值与应用场景

PMP 并不是"更贵"的代名词，而是**更可控**的代名词。它在以下场景几乎是刚需：

1. **品牌旗舰投放（Brand Campaign）**：客户对流量质量敏感，需要避开低质长尾、制止广告出现在不合适页面。通过 publisher 手动筛选的 PMP，可以显著降低 GIVT（一般无效流量）与品牌安全风险。
2. **头部媒体直采的数字化**：过去品牌方要买某头部媒体的优质资源，只能线下谈 CPM 签 IO（Insertion Order）。现在媒体把优质位放进 PMP deal，招标线上化，但买方仍保留"看库、谈价"的线下协商入口。
3. **独家/优先资源**：某些数据或资源（如某 App 的开屏、某视频平台的前贴片）只对特定合作方开放，PMP 是最小成本实现"半封闭"的通道。
4. **可控频控与排期**：PMP 有清晰的一方按下 plan 的排期，方便与媒体配合做新内容发布、大促集中引爆。
5. **卖方第一方数据处理**：发布商可以在 deal 上附加 context / signals，买方可以直接消费这些增强信号来优化出价。

一句话：**公开竞价买"量"，PMP 买"质 + 可控性"，PG 买"确定性"，Preferred Deal 买"优先权"**。

### 1.3 PMP vs 公开竞价 vs PG vs Preferred Deal 对比表

| 维度 | 公开竞价 Open Auction | PMP（Private Marketplace） | PG 程序化保量 | Preferred Deal 优先交易 |
|------|---------------------|---------------------------|--------------|------------------------|
| 参与方式 | 全部买方 | 官方受邀买方 | 单一买方（一对一） | 单一买方（一对一，可选多个） |
| 是否需要邀请 | 否 | 是，需要 seller 邀请 | 是，双边确认 | 是，卖方定向邀请 |
| 拍卖机制 | 第一/第二价格公开拍卖 | 竞拍（第二价格），仅受邀方 | 不竞拍，注定成交 | 不竞拍，先到先得 |
| 底价（floor） | 无强约束 / 公开市场价 | 有明确 floor（固定） | 按约定费率 | 有 floor（通常是固定价） |
| 量保障 | 无 | 无（不保证量，fill 取决于出价与竞价） | **有**（保证量，≤ 一定量必成交） | 无（先到先得，库存不保证） |
| 费用 | 市场出价 | 高于 floor 的出价竞争 | 固定的约定价格 | 基本等于 floor |
| 定价权 | 市场 | 卖方设 floor，买方出价 | 双边约定 | 卖方设价，买方是否接受 |
| 品牌可控性 | 低 | 高 | 最高 | 高 |
| 典型适用 | 效果投放、长尾补量 | 品牌旗舰、优质媒体直采 | 必达量的品牌大促 | 优先抢量、媒体自有资源的预定 |
| DV360 transaction_type | `OPEN_AUCTION` | `PRIVATE_MARKETPLACE` | `PROGRAMMATIC_GUARANTEED` | `PREFERRED_DEAL` |

在某些语境下，PMP 与 Preferred Deal 经常混用，但严格来说它们是**两种不同的 deal 类型**：

- **PMP（Private Auction）**：对**多个**受邀买方开放，多个买方出价，价高者得（仍是第二价格拍卖）。优于 Open Auction，因为它有 floor + 只有受邀者参与；但买方之间仍要竞争，卖方看重的是"在封闭圈子里获得最优出价"。
- **Preferred Deal（PD）**：只对**一个买方**开放（或极少数买方），买方只要出价达到 floor，就能**抢在公开市场之前**以该价格买下库存。非竞拍、先到先得，卖方牺牲"竞价抬价"换"确定性快速成交"。

这个区别对谈判非常重要：PMP 里你的出价要"赢"才有量，PD 里你只要"到价"就有量（前提是库存没有被别人/此前排期抢完）。后文 2.2 会详细展开这两种 deal 的原始语义。

### 1.4 买卖双方 deal 架构总览

```
                        ┌─────────────────────────────────────────────┐
                        │            卖方（Seller / Publisher）         │
                        │  GAM / Ad Manager 网络   │   SSP / Exchange   │
                        │  ┌───────────────┐       │                    │
                        │  │ 优质 Ad Unit  │       │  创建 Private Deal │
                        │  │ 圈定成 Deal    │──────▶ │  (Deal ID, floor, │
                        │  └───────────────┘       │   Buyer 邀请)      │
                        └─────────────────────────┼────────────────────┘
                                                  │  Deal ID / Proposal
                                                  │  通过 Negotiation / Exchange 传递
                                                  ▼
                        ┌─────────────────────────────────────────────┐
                        │            买方（Buyer / Advertiser）         │
                        │  DV360（Partner → Advertiser → IO → LineItem）│
                        │  ┌────────────────────────────────────────┐  │
                        │  │ 1. dv360_list_sellers() 找卖家           │  │
                        │  │ 2. dv360_list_proposals() 列出提案       │  │
                        │  │ 3. dv360_accept_proposal() /             │  │
                        │  │    reject_proposal() 接受/拒绝           │  │
                        │  │ 4. dv360_create_line_item(type=...)       │  │
                        │  │    绑定 deal ID 到 LineItem              │  │
                        │  │ 5. 出价 ≥ floor 参与拍卖                 │  │
                        │  └────────────────────────────────────────┘  │
                        └─────────────────────────────────────────────┘
                                         │
                                         ▼
                        ┌─────────────────────────────────────────────┐
                        │               拍卖 / 成交                       │
                        │  请求到达 → Exchange 匹配 Deal → 分发到受邀 DSP  │
                        │  DSP 出价 → 是否 ≥ floor → 竞拍 → 最高出价成交   │
                        │  （PMP: 第二价格 | PD: 到价即抢 → 结算）         │
                        └─────────────────────────────────────────────┘
```

### 1.5 DV360 里的层级关系

买方侧，PMP deal 最终要落到一个** LineItem 记 unit** 上。DV360 的对象层级是：

```
Partner（合作伙伴）
 └── Advertiser（广告主）        ← dv360_list_advertisers()
      └── Insertion Order (IO)  ← dv360_list_insertion_orders()
           └── LineItem（投放单元）← dv360_create_line_item() / list_line_items()
                └── Flight（投放航次）← dv360_list_flights()
                └── Creative（创意） ← dv360_list_creatives()
```

deal（交易）本身是**绑定在 LineItem 层面**的：一个 LineItem 可以绑定一个或多个 deal，出价时 DV360 会优先尝试在这些私有交易里购买，拿不到才回落到公开竞价（取决于设置的 bidding/exchange 策略）。这与 GAM 侧的 Order → LineItem 结构是对偶的——卖方在 GAM 里建 deal，买方在 DV360 里绑 deal，靠 Exchange（Ad Manager）完成匹配。

---
## 二、深度原理解析

### 2.1 deal（交易）的本质：一个"带门槛的拍卖入口"

在 Ad Exchange（Ad Manager / AdX）的语境里，deal 本质是**一条供给侧的竞价规则**：当一次广告请求命中某个广告位，Exchange 先检查这条请求上是否挂了 deal（按 deal ID 匹配），如果挂了，则只把这次竞价机会发给**该 deal 邀请的买方**，并附上底价 floor。

```
广告请求（含 Ad Unit / 上下文 / 用户信息）
        │
        ▼
┌──────────────────────────────────────────────┐
│ Exchange 竞价路由                              │
│  1. 请求是否命中 Deal 配置？（dealId 匹配）       │
│     ├─ 命中 → 私有竞价通道                      │
│     │    ├─ 只通知受邀 DSP（Deal Buyers）        │
│     │    └─ 携带 floorPrice 出价约束             │
│     └─ 未命中 → 公开竞价通道                    │
│          └─ 通知所有 DSP（含受邀方作为兜底）       │
└──────────────────────────────────────────────┘
        │
        ▼
    受邀 DSP 出价（bid ≥ floor 才有资格）
        │
        ▼
    第二价格拍卖：最高出价者成交，支付次高出价
```

关键结论：

1. **floor 是硬约束**：出价低于 floor 的请求根本不会成交（在某些实现里甚至不会收到竞价请求，或收到但被 Exchange 直接判负）。所以在 PMP 里"出低价搏量"是无效的，必须出到 floor 之上。
2. **受邀者数量决定了竞争度**：PMP 邀请越多买方，竞争越激烈，成交价越接近 floor 之上的市场价；PD 只邀请一个买方，竞争为零，到 floor 即可成交。
3. **deal 不保证量**：即便 deal 存在、你有量可投，能否成交还取决于：库存是否真实出现、你的出价是否赢过其他受邀买方、定向条件是否重叠。**这是 PMP fill 率低的根本原因**，详见 3.4 踩坑。

### 2.2 交易类型再辨析：Private Auction vs Preferred Deal 的 nuance

很多资料把 PMP 和 Preferred Deal 混为一谈，这里把边界讲清楚：

| 语义维度 | Private Auction（PMP） | Preferred Deal（PD） |
|---------|----------------------|---------------------|
| 买方数量 | 多个受邀买方 | 通常 1 个（可配多个，但每个 buyer 都独立优先） |
| 成交条件 | 出价最高者赢（第二价格） | 出价 ≥ floor 即成交（先到先得） |
| 卖方收益逻辑 | 竞争抬价，收益最大化 | 确定性优先，接受固定价 |
| 买方收益逻辑 | 在优质库存里竞价，仍有"赢"的悬念 | 几乎必得，适合必须拿下的资源 |
| 是否有保量 | 无 | 无（库存耗尽即止） |
| floor 的含义 | 参与竞价的资格线 | 直接成交的单价 |
| DV360 枚举 | `PRIVATE_MARKETPLACE` | `PREFERRED_DEAL` |
| 谈判姿态 | "我们出到 floor 以上，请多邀请我们" | "请只给我们，我们愿意接受你的 floor" |

**实战 nuance 1——PD 的"抢"是全局的**：PD 只在"广告位可用且库存未在更早排期被锁定"时成立。同一块库存，卖方可能同时开了一个 PD 和若干公开竞价；PD 买方在请求到达时只要出价到 floor 就会被 Exchange 优先判定成交（preferred 的语义就是"你有权在公开竞价之前以约定价拿走"）。所以 PD 的 fill 上限受库存真实容量限制，不是"要多少有多少"。

**实战 nuance 2——PMP 里的"价格太高"常是 floor 惹的祸**：PMP 的成交价下限就是 floor，如果卖方把 floor 定得远高于市场均价，受邀买方要么不出价（fill 低），要么被迫高溢价成交（成本高）。谈 PMP 的本质是谈 floor，而不是谈"能不能进"。

**实战 nuance 3——混用买法**：一条 LineItem 可以同时绑 PMP deal + 公开竞价（fallback）。出价策略上，可以先尝试 deal（高 CPM 预算），deal 不成交再回落公开竞价补量。这是品牌投放最常见的"质 + 量"组合打法。

### 2.3 PMP deal 的创建与协商流程（Proposal）

PMP deal 的建立，在 DV360 侧主要通过 **Proposal（提案）** 工作流完成。整体生命周期：

```
阶段 A：发现
  卖方在 GAM 创建 Deal（圈广告位、定 floor、选邀请的 Buyer 账户）
        │
        ▼
阶段 B：提案（Proposal）
  1. dv360_list_sellers()          → 看有哪些卖家、卖家信息
  2. dv360_list_proposals()        → 看收到的提案（含 deal 详情、状态）
  3. 逐条审查：deal 名、广告位范围、floor、时间窗、量级
        │
        ▼
阶段 C：决策
  4. 接受：dv360_accept_proposal(proposal_id)
     → deal 进入"已接受/激活"状态，可被 LineItem 绑定
  5. 拒绝：dv360_reject_proposal(proposal_id)
     → 附理由回绝（可能触发卖方重新谈价）
        │
        ▼
阶段 D：落地
  6. dv360_create_line_item(advertiser_id, name, type='DISPLAY', ...)
     → 创建 LineItem，并把 deal id 写进 exchange 配置/绑定
  7. 出价 ≥ floor，开始竞拍/成交
        │
        ▼
阶段 E：监控
  8. dv360_get_report() 拉 fill / 成本 / 量级
  9. 不达标 → dv360_update_line_item() 调出价、调定向
  10. 谈崩/到期 → 回到阶段 B 重新谈或换 deal
```

一个**真实的协商对话流**（线下 + 线上并行）：

```
广告主/Agency ──── 线下沟通 ────▶ 媒体销售
      │                              │
      │  提出需求：目标人群、量级、    │
      │  预算、品牌安全要求、期望 CPM   │
      │                              │
      │◀──── 报价与库存说明（floor、量级、排期）───│
      │                              │
      │  讨价还价：floor 下探 /        │
      │  量级承诺 / 附加定向 / 素材要求  │
      │                              │
      │◀──── 最终 Proposal（deal 配置好）───────│
      ▼                              ▼
  DV360 侧：dv360_list_proposals() 看到提案
      │
      ├─ 接受 → dv360_accept_proposal()
      └─ 拒绝 → dv360_reject_proposal() + 反馈
```

### 2.4 deal 定价（floor）与拍卖语义

**floor 的几种形态：**

| 形态 | 说明 | 使用场景 |
|------|------|---------|
| 固定 floor | 一个固定 CPM，任何成交价 ≥ floor | 最常用，PMP 标配 |
| 区间 floor | 按定向/库存分段给不同 floor | 复杂媒体，如分端（移动/桌面） |
| 动态 floor | 按流量质量实时调整（Seller-defined） | 部分 SSP 高级能力，DV360 侧需配合 |

**拍卖语义（以第二价格为例）：**

```
受邀买方：A 出 $8，B 出 $6，C 出 $4，floor = $5
  → A 出价 $8 ≥ floor ✓  → A 获胜
  → 成交价 = 第二高价 = max($6, floor) = $6
  → 所以 floor 不仅仅是最低门槛，还在"只有一个买方出价"时
     成为实际成交价（此时第二高价 < floor，取 floor）
```

这就是为什么 PMP 里 **floor 几乎是"保底成交价"**：只要有一个受邀买方出价，成交价至少是 floor。买方如果想压成本，谈判的核心就是压低 floor；卖方想保收入，核心就是守住 floor。双方在 floor 上的博弈是 PMP 交易的真正战场。

**DV360 出价与 floor 的关系：**
- DV360 的出价单位按 IO/LineItem 的出价策略设置（CPM 或优化 CPM）。
- 若 LineItem 同时绑了多个 deal，DV360 会在每个 deal 上独立评估：出价 ≥ floor 才参与该 deal 的竞拍。
- 优化出价（Optimized CPM / OCPM）会把 deal floor 纳入模型约束，避免"出价低于 floor 导致 0 fill"。

### 2.5 如何查看可用 PMP deals 并绑定 LineItem（Python 实战）

DV360 的 deal 在 API 侧通常通过 **proposal 与 lineItem 的 exchange 配置**暴露。结合本知识库脚本 `ad_platform_api.py`，推荐的工作流如下：

```python
# -*- coding: utf-8 -*-
"""
PMP deal 全流程：发现 → 审查 → 接受 → 绑定 LineItem → 监控
运行前提：config/ad_platform_credentials.json 中已配置 dv360 凭证
"""
import json
from ad_platform_api import AdPlatformClient

client = AdPlatformClient()
ADVERTISER_ID = "123456789"   # 替换为你的 advertiser id
IO_ID = "987654321"           # 目标 Insertion Order

# ── 1. 找卖家（发布商）──
sellers = client.dv360_list_sellers()
print(f"[Sellers] 共 {len(sellers)} 个卖家")
for s in sellers[:10]:
    print("  ", s.get('sellerId'), s.get('displayName', s.get('name', '')))

# ── 2. 列出收到的提案（deal 入口）──
proposals = client.dv360_list_proposals(ADVERTISER_ID)
print(f"\n[Proposals] 共 {len(proposals)} 个提案")
for p in proposals:
    print(json.dumps({
        'proposalId': p.get('proposalId'),
        'name': p.get('name'),
        'status': p.get('status'),
        'dealType': p.get('dealType'),       # 可能为 PRIVATE_MARKETPLACE / PREFERRED_DEAL
        'floor': p.get('floorPrice'),
        'start': p.get('startDate'),
        'end': p.get('endDate'),
    }, ensure_ascii=False))

# ── 3. 审查后接受 / 拒绝 ──
# 只看 PMP / Preferred Deal 类型的提案
pmp_proposals = [p for p in proposals
                 if p.get('dealType') in ('PRIVATE_MARKETPLACE', 'PREFERRED_DEAL')]
if pmp_proposals:
    target = pmp_proposals[0]
    if target.get('status') in ('PENDING', 'DRAFT', 'AWAITING_ACCEPTANCE'):
        result = client.dv360_accept_proposal(target['proposalId'])
        print(f"\n[Accept] proposal {target['proposalId']} → {result}")
    else:
        print(f"\n[Skip] proposal {target['proposalId']} 状态 {target.get('status')}")

# ── 4. 创建 LineItem 并绑定 deal（type 决定交易类型）──
line_item = client.dv360_create_line_item(
    ADVERTISER_ID,
    name="PMP_Brand_Aug_Display",
    type="DISPLAY",                     # LineItem 的展示类型
    deal_id=target.get('dealId'),       # 绑定 deal（如有该字段）
    exchange_id="google_ad_manager",    # 与卖方同一 Exchange
)
print(f"\n[LineItem] created: {line_item.get('lineItemId', line_item)}")

# ── 5. 拉报表监控 fill / 成本 ──
report = client.dv360_get_report(
    ADVERTISER_ID,
    dimensions=['LINE_ITEM', 'DEAL'],
    metrics=['IMPRESSIONS', 'CLICKS', 'SPEND', 'MEDIA_COST'],
    date_range={'start': '2026-08-01', 'end': '2026-08-14'},
)
print(f"\n[Report] 成交行数: {len(report.get('rows', []))}")
```

> 注意：脚本中 `dv360_list_proposals` / `dv360_accept_proposal` / `dv360_reject_proposal` 目前是**桩实现**（返回空列表/空字典），说明提案 API 尚未接入真实凭证。生产环境请替换为真实 Display & Video 360 API 调用（`displayvideo.googleapis.com/v3` 的 `proposals` 资源），字段名以官方 proto 为准。脚本的价值在于**流程骨架 + 字段约定**，接入真实 API 时只需替换数据源。

### 2.6 真实 API 对象速查表

| 脚本方法 | 对应 DV360 资源 | 用途（PMP 场景） |
|---------|----------------|-----------------|
| `dv360_list_sellers()` | `sellers` | 查看可交易的卖家/发布商 |
| `dv360_list_proposals(advertiser_id)` | `proposals` | 列出收到的提案（含 deal 信息） |
| `dv360_accept_proposal(proposal_id)` | `proposals.accept` | 接受 deal 提案 |
| `dv360_reject_proposal(proposal_id)` | `proposals.reject` | 拒绝 deal 提案 |
| `dv360_list_placements(advertiser_id)` | `placements` | 查看可投放的位次（确认 deal 覆盖的广告位） |
| `dv360_list_placements_by_line_item(line_item_id)` | `placements` | 查看某 LineItem 关联的位次 |
| `dv360_list_line_items(advertiser_id)` | `lineItems` | 列出 LineItem，检查 deal 绑定情况 |
| `dv360_get_line_item(advertiser_id, line_item_id)` | `lineItems.get` | 查看单个 LineItem 的 exchange/deal 配置 |
| `dv360_create_line_item(advertiser_id, name, type=...)` | `lineItems.create` | 创建 LineItem，type 可指定 DISPLAY/VIDEO 等 |
| `dv360_update_line_item(...)` | `lineItems.update` | 调出价、换 deal、改状态 |
| `dv360_pause_line_item / dv360_resume_line_item` | `lineItems.update` | 暂停/恢复投放 |
| `dv360_get_report(advertiser_id, ...)` | `reports.generate` | 拉 fill、成本、量级报表 |
| `dv360_list_reach_forecasts(advertiser_id)` | `reachForecasts` | 预估触达/量级，评估 deal 容量 |
| `get_transaction_type_options()`（dv360_api.py） | 官方枚举 | 获取 `PRIVATE_MARKETPLACE` / `PREFERRED_DEAL` 等交易类型 |
| `list_line_items / create_line_item`（dv360_api.py） | `partners/.../lineItems` | 同一对象的另一套封装（v4 风格） |

### 2.7 代码示例：deal 与定向叠加的正确姿势

PMP 里最常见的错误是**定向与 deal 互相打架**（deal 本身已经圈定了一批广告位，LineItem 又叠加了过窄的定向，导致两个集合的交集几乎为零）。正确的叠加姿势：

```python
"""
deal 与定向叠加的两种策略对比
策略 A（推荐）：deal 管"在哪买"，定向管"买给谁"，交集尽量大
策略 B（危险）：deal 管"在哪买"，定向又强行圈"哪些位次"，交集可能为空
"""
from ad_platform_api import AdPlatformClient

client = AdPlatformClient()
ADVERTISER_ID = "123456789"
IO_ID = "987654321"

# 策略 A：deal 只负责库存范围，定向专注人群
deal_li = client.dv360_create_line_item(
    ADVERTISER_ID,
    name="PMP_StrategyA_AudienceFocus",
    type="DISPLAY",
    # deal_id 由提案接受后得到，绑定到 LineItem 的 exchange 配置
    deal_id="deal_88888888",
)
# 人群定向：宽泛但精准（不要把位次/内容定向也叠加进来）
client.dv360_update_line_item(
    ADVERTISER_ID, deal_li['lineItemId'],
    targeting={
        'geo': ['CN', 'HK', 'TW'],
        'age': ['18-24', '25-34'],
        'gender': ['MALE', 'FEMALE'],
        # 注意：这里不再放 placement/app 定向，避免与 deal 圈定的位次冲突
    },
)

# 策略 B（反面教材）：deal + 位次定向双重收紧
bad_li = client.dv360_create_line_item(
    ADVERTISER_ID,
    name="PMP_StrategyB_TightPlacement",
    type="DISPLAY",
    deal_id="deal_88888888",
)
client.dv360_update_line_item(
    ADVERTISER_ID, bad_li['lineItemId'],
    targeting={
        'geo': ['CN'],
        'placements': ['publisher-a.com/sports', 'publisher-a.com/news'],
        # deal 已经圈定 publisher-a.com 的体育/新闻位，
        # 再叠加同维度定向 = 双重约束，fill 断崖下跌
    },
)
```

**规则总结：**
1. **deal 管供给（在哪买），定向管需求（买给谁），两维度尽量正交。**
2. 位次（placement）、APP、内容类目这类**供给侧维度**，交给 deal 去圈；人口、兴趣、行为、设备这类**需求侧维度**，放在 LineItem 定向里。
3. 如果 deal 已经圈到"位次"级别，LineItem 里**不要再写同样的位次定向**；否则交集为空。
4. 需要验证交集大小时，先跑 `dv360_list_reach_forecasts()` 看量级预估，再决定是否收窄定向。

---
## 三、生产环境实战

### 3.1 实战场景 1：品牌方采购头部媒体优质库存（PMP 全流程）

**背景**：某国际美妆品牌要做 8 月新品上市，需要在一家头部时尚媒体（自营流量）首页 + 频道首屏买到"既有质又有量"的库存。媒体明确表示"这批位子不进公开竞价，只走 PMP"。Agency 需要在 DV360 里完成从提案到投放的完整闭环。

**最终配置：**

```
Advertiser : BrandCosmetics_CN
IO         : Aug_NewProduct_Launch（预算 $400K，2026-08-01 → 2026-08-31）
LineItem   : PMP_Homepage_Brand_Display   type=DISPLAY  OCPM 出价
  Deal      : MediaA_Homepage_PMP  (deal_66668888)
              floor=$4.5 CPM
              覆盖：首页 970x250 / 300x600 / 首屏 300x250
              邀请：本品牌 + 2 个竞品外品牌
  Fallback  : Open Auction（兜底补量）
  定向       : geo=CN 一线城市 | age=20-35 女性 | interest=美妆/时尚
  频控       : 1 个用户 / 3 天 / 1 次（3-day 1+）
```

**落地步骤（配合脚本方法）：**

```python
from ad_platform_api import AdPlatformClient

client = AdPlatformClient()
AD_ID, IO_ID = "20011100", "30022200"

# 1) 确认卖家与提案
sellers = client.dv360_list_sellers()
media_a = next((s for s in sellers if "MediaA" in s.get('displayName', '')), None)
print("卖家:", media_a.get('sellerId') if media_a else "未找到")

proposals = client.dv360_list_proposals(AD_ID)
deal = next((p for p in proposals if p.get('floorPrice') == 4500), None)  # 微元 4500 = $4.5
if deal and deal.get('status') in ('PENDING', 'DRAFT'):
    client.dv360_accept_proposal(deal['proposalId'])
    print("已接受 PMP 提案:", deal.get('dealId'))

# 2) 创建并绑定 LineItem，开 OCPM 出价
li = client.dv360_create_line_item(AD_ID, name="PMP_Homepage_Brand_Display", type="DISPLAY")
client.dv360_update_line_item(
    AD_ID, li['lineItemId'],
    deal_id=deal.get('dealId'),
    bidding_strategy="OPTIMIZED_CPM",
    budget={
        'io_id': IO_ID,
        'planned_spend_amount': 400000 * 1000000,  # 微美元
    },
    pacing="EVEN",
    frequency_cap=[{'max_impressions': 1, 'time_unit': 'TIME_UNIT_DAYS', 'time_amount': 3}],
)

# 3) 量级预估（对照 deal 容量）
forecast = client.dv360_list_reach_forecasts(AD_ID)
print("预估触达(千):", forecast.get('reach'))

# 4) 每日监控
report = client.dv360_get_report(
    AD_ID,
    dimensions=['LINE_ITEM', 'DEAL'],
    metrics=['IMPRESSIONS', 'CLICKS', 'SPEND', 'MEDIA_COST', 'AVERAGE_CPM'],
    date_range={'start': '2026-08-01', 'end': '2026-08-14'},
)
for row in report.get('rows', []):
    print(row)
```

**最佳实践清单（品牌 PMP）：**

| 环节 | 最佳实践 | 原因 |
|------|---------|------|
| 入口 | 先 `list_sellers` + `list_proposals` 看清再下手 | 避免瞎创建 deal |
| 出价 | OCPM（优化出价）而非固定 CPM | 自动贴合 deal floor，兼顾 fill 与成本 |
| 频控 | 按"3 天 1 次"起步，逐步放开 | 频控太严会拉低 fill，太松伤品牌 |
| 兜底 | 必配 Open Auction fallback | PMP 不保量，兜底保证整体 fill |
| 预算 | 先小预算试跑 3 天再放量 | 验证 fill 与 viewability 再烧钱 |
| 品牌安全 | 配合 brand safety + viewability provider 验证 | 买"质"的核心是验证而非信任 |

### 3.2 实战场景 2：deal 与定向叠加的正确工程化

复用 2.7 的策略 A，工程化落地一个"多层定向叠加"的 LineItem 模板：

```python
def build_pmp_lineitem(client, ad_id, io_id, deal_id, name, **kw):
    """通用 PMP LineItem 工厂：deal 管供给，定向管需求"""
    li = client.dv360_create_line_item(ad_id, name=name, type=kw.get('type', 'DISPLAY'))
    targeting = {'geo': kw.get('geo') or []}
    if kw.get('audience_segment_ids'):
        targeting['audience'] = kw['audience_segment_ids']
    if kw.get('device_types'):
        targeting['device'] = kw['device_types']
    client.dv360_update_line_item(
        ad_id, li['lineItemId'],
        deal_id=deal_id,
        bidding_strategy=kw.get('bidding', 'OPTIMIZED_CPM'),
        pacing=kw.get('pacing', 'EVEN'),
        targeting=targeting,
    )
    return li

# 用法
client = AdPlatformClient()
li = build_pmp_lineitem(
    client, "20011100", "30022200", "deal_66668888",
    name="PMP_Mobile_Travelers", type="DISPLAY",
    geo=['CN'],
    audience_segment_ids=['high_intent_traveler'],
    device_types=['PHONE_TABLET'],
)
print("LineItem:", li.get('lineItemId'))
```

**工程要点：**

1. **把"供给侧定向"与"需求侧定向"拆到两个配置位**，避免在代码里混写。
2. 对每个 deal 配一个"家族"（多个同 deal 的 LineItem，定向互斥、覆盖不同人群），用容量切分实现"deal 最大化利用"。
3. 用 `dv360_list_reach_forecasts` 在**上线前**校验每个定向组合的量级，站在数据上做决定。
4. 对每个 LineItem 的 deal 单独记录 `deal_id`，方便报表按 deal 拆解归因。

### 3.3 fill / 成本优化（以 PMP 为对象）

**fill 优化三板斧：**

```
┌─────────────────────────────────────────────────────────┐
│  PMP fill 低时按顺序排查                                  │
│                                                          │
│  ① 出价是否 ≥ floor？                                    │
│     → 出价 < floor：全部请求被判负，fill≈0                │
│     │   解法：把出价提到 floor 上 5%-15%；或谈低 floor     │
│  ② 定向是否与 deal 库存交集太小？                          │
│     → 越窄交集 fill 越低                                   │
│     │   解法：放开供给侧维度，收敛需求侧维度                │
│  ③ 晚间/周末 库存峰谷？                                   │
│     → 某些媒体夜间库存锐减                                 │
│     │   解法：按小时报表看峰谷，预算集中白天                │
│  ④ 是否只有你一个受邀方在出价？                            │
│     → 竞争少时 fill 也未必高（卖方库存总量固定）            │
│     │   解法：与卖方确认实际可消耗量级                     │
└─────────────────────────────────────────────────────────┘
```

**成本优化要点：**

| 手段 | 说明 | 风险 |
|------|------|------|
| 谈低 floor | 直接压低成交价下限 | 卖方可能拒绝或缩库存 |
| 用 OCPM 优化出价 | 让模型按 floor 自动定价，避免出价过高 | 模型波动期可能 fill 不稳 |
| 收紧需求侧定向 | 只投高 LTV 人群，摊薄 CPM | 量级变小 |
| 分 CPM 阶梯测试 | 同 deal 多档出价 A/B，找到"量/价平衡点" | 需要足够流量做测试 |
| 投放后归因 | 用 NCPI/ROAS 衡量 deal 真正价值 | 归因窗口与数据延迟 |

### 3.4 踩坑实录（真实经验，务必规避）

**坑 1：deal 获取难 / 拿不到 volume**
- **现象**：确认 deal 存在、已接受、出价也过了 floor，但每天只有极少量展示。
- **根因**：卖方给的 deal 只是"入口"，实际可消耗量受媒体真实库存、定向交集、受邀买方数共同决定；另外很多媒体嘴上承诺的量与实际开放的量偏差很大。
- **解法**：签约前让卖方提供**该 deal 的可消耗量级预估**；上线先 `dv360_list_reach_forecasts` 对标；量级不达标宁可换 deal 或转 PG。

**坑 2：价格太高（floor 过高）**
- **现象**：deal 成交 CPM 比公开竞价高出一大截，ROAS 打不平。
- **根因**：floor 就是保底成交价，单一受邀方时成交价≈floor；卖方把 floor 定在溢价区间。
- **解法**：谈判时把 floor 当作核心条款压；用数据（benchmark CPM、viewability、LTV）说服卖方降 floor；若仍是高，则限量投放，只在高价值时段/人群用。

**坑 3：fill 低**
- **现象**：预算花不完，LineItem 一直 underdeliver。
- **根因**：见 3.3 的四板斧——最常见的是**出价 < floor**（新手 90% 栽在这）和**定向叠加过窄**。
- **解法**：先查出价 vs floor；再查定向交集；最后查响应行业库存峰谷。

**坑 4：deal 过期**
- **现象**：投放中途突然无量，报表显示 deal fill 0。
- **根因**：deal 有 start/end 时间窗，或卖方单方面关闭/下架 deal，买方没收到通知。
- **解法**：建立 deal 到期日历，提前 3-5 天续约；用脚本定时 `dv360_list_proposals` 检查 deal 状态；一旦发现失效，立即启用 fallback + 申请新 deal。

**坑 5：追不到量（post-bid 与 pre-bid 数据不一致）**
- **现象**：预估/媒体承诺的量级很大，实际成交很小。
- **根因**：pre-bid（请求侧）与 post-bid（成交侧）天然有 gap；媒体给的"请求量"≠"可成交量"。
- **解法**：以 `dv360_get_report` 的实际成交（impressions）为准，不要信 pre-bid 预估；按成交数据反推真实 fill，再决定是否加预算。

**坑 6：deal 绑定错 LineItem / 忘记绑定**
- **现象**：deal 接受成功但一直没量，查发现 LineItem 根本没绑 deal，只是走公开竞价。
- **根因**：`accept_proposal` 只是接受提案，**不等于**把 deal 绑到 LineItem；绑定是在 `dv360_create_line_item` / `dv360_update_line_item` 时写入 deal_id。
- **解法**：在每个 LineItem 上显式检查 `get_line_item` 返回里的 deal 配置；报表按 DEAL 维度拆，确认成交都挂在目标 deal 下。

**坑 7：一个 deal 被多个 LineItem 重复绑定导致频控打架**
- **现象**：同用户被多个 LineItem 反复触达，品牌反感。
- **根因**：多 LineItem 共用同一 deal，各自有独立频控，跨 LineItem 频控失效。
- **解法**：同一 deal 的家族 LineItem 用**统一频控 + 同一 floodlight 归因**；或在 IO 层做全局频控。

| 踩坑速查表 | 现象 | 首要排查 | 应急 |
|-----------|------|---------|------|
| 拿不到量 | 有 deal 但量极少 | 可消耗库存/受邀竞争 | 换 deal 或转 PG |
| 太贵 | CPM 虚高 | floor 与成交价关系 | 谈判压 floor |
| fill 低 | 预算花不完 | 出价 vs floor + 定向交集 | 提高出价/放开定向 |
| 过期 | 突然无量 | deal 时间窗/状态 | 续约 + fallback |
| 追不到量 | 承诺量 ≠ 成交 | pre/post-bid gap | 以实际成交为准 |
| 忘绑定 | deal 接受了没量 | LineItem 的 deal 配置 | 显式绑定 + 检查 |
| 频控打架 | 反复触达 | 跨 LineItem 频控 | IO 层统一频控 |

---
## 四、常见问题与排查（FAQ）

### Q1：为什么我在 DV360 里"找不到 deal"？

**场景**：卖家说已经把 PMP 开给我了，但我列表里看不到任何 deal。

**排查路径：**

```
卖家已开 deal？
  ├─ 否 → 让卖家确认 Deal 已被创建且 Buyer 账户写的是你
  │         （deal 必须显式邀请你的 DV360 Buyer，否则你看不到）
  ├─ 是 → 检查是哪个层级看不到
  │        ├─ Partner 层 -> 需要 Partner 管理员确认 exchange 账号
  │        ├─ Advertiser 层 -> dv360_list_proposals 是否含该 deal
  │        └─ 你的 DV360 是否连到同一 Exchange（GAM/AdX）？
  └─ 都是 → 问：是不是跨 Exchange？跨国/跨区权限？
```

**常见根因**：
1. **Buyer 账户没被邀请**：deal 的 buyer 列表里没有你这个 DV360 账户，自然看不到。
2. **Exchange 不匹配**：买卖双方必须在同一/可互通的 Exchange（例如都走 Google Ad Manager），否则 deal 无法同步。
3. **审批/权限不足**：提案属于 Partner 或更高权限账户，你的账号没读权限。
4. **del 名称/筛选**：列表按名字过滤可能漏掉。

**解法**：用 `dv360_list_proposals(advertiser_id)` 拉全量检查；联系卖方确认 buyer invitation；检查 Partner 的 exchange 配置。

### Q2：deal 显示"无效/不可用"（invalid / unavailable）是什么原因？

**常见原因：**

| 状态 | 含义 | 处理 |
|------|------|------|
| `EXPIRED` | deal 超出 end date | 续约或申请新 deal |
| `PAUSED` / `DEACTIVATED` | 卖方暂时关闭 | 联系卖方确认 |
| `ARCHIVED` | 卖方下架 | 换 deal |
| `AWAITING_ACCEPTANCE` | 待你接受 | 调 `dv360_accept_proposal` |
| `REJECTED` | 被拒或有争议 | 沟通或走新提案 |
| Buyer 未受邀 | 权限外不可见 | 让卖方补邀 |

**解法**：`dv360_list_proposals` 看每条 deal 的 `status` 字段，对照上表处理；不要盲删 LineItem 重建（会丢排期和历史）。

### Q3：fill 太低、预算花不完怎么办？

**分诊清单（由高到低优先级）：**

```
□ ① 出价是否 < floor？          → 调到 floor 上 5%-15%
□ ② 定向是否过度叠加？           → 放开供给侧维度
□ ③ 频控是否太严？               → 放宽到 3 天 1 次起
□ ④ 预算/排期是否过短？           → 拉长排期平滑填充
□ ⑤ 是否同时段被其他受邀方抢？     → 联系卖方提高受邀份额
□ ⑥ deal 是否接近过期/容量耗尽？   → 续约/加 deal
```

**如果都排完仍低**：可能卖方实际库存就这么多，量级是卖方夸大的。此时不要死磕这一点 PMP，叠加 Open Auction fallback 或转 PG 保量。

### Q4：成本太高（CPM 超预期）怎么谈价？

**谈判优先级：**
1. **压 floor**：floor 是保底成交价，谈成即全局受益（最有效）。
2. **换更宽量的 deal**：扩大供给侧（更多广告位/更长排期）摊薄平均价。
3. **拿数据谈判**：用 viewability、brand safety、LTV、竞品 benchmark 说服卖方"你的库存值这个价吗"。
4. **承诺量级换价**：承诺"最低消耗量"换卖方降 floor 或加量。

**不可取的**：把出价压到 floor 以下"试试看"——只会归零 fill，不会得到低价量。

### Q5：PMP 到期/过期，现有 LineItem 还要继续投怎么办？

1. 申请新 deal（同配置但新时间窗），`accept_proposal` 接受。
2. `dv360_update_line_item` 把新 `deal_id` 绑到原 LineItem，尽量保留历史与排期。
3. 若新 deal 配置有变（floor/位次），同步调整出价与定向。
4. fallback 公开竞价保持开启，避免断量。

### Q6：我想拿 PMP 的量做程序化保量（PG），能直接用吗？

**不能**。PMP 是竞拍、不保量；PG 是固定交易、保量。两者在 DV360 是不同 `transaction_type`（`PRIVATE_MARKETPLACE` vs `PROGRAMMATIC_GUARANTEED`），结算、量级承诺、费率逻辑完全不同。如果预算必须"必达"，请单独走 PG 流程，不要指望 PMP 兜量。

### Q7：一个 deal 可以绑多个 LineItem 吗？有什么坑？

可以。一个 deal（一次竞拍入口）可以被买方侧多个 LineItem 引用。坑是：
- **频控打架**：跨 LineItem 频控需在 IO/账户层统一。
- **预算内耗**：多个 LineItem 抢同一 deal 的预算，互不知情。
- **定向混乱**：不同 LineItem 定向重叠，重复出价拉高成本。
建议：同一 deal 用一个"家族"管理，定向互斥、预算集中。

### Q8：如何量化一个 PMP deal 到底"值不值"？

**核心指标：**

| 指标 | 意义 | 与公开竞价对比的依据 |
|------|------|---------------------|
| Viewability Rate | 可见率更高？ | 应明显优于 Open Auction |
| Brand Safety Pass Rate | 安全通过率 | 应 > 95% |
| CTV/IAB 上下文质量 | 内容环境是否匹配 | 逐条审核 |
| LTV / NCPI | 质量流量的真实价值 | 利润口径而非 CPM 口径 |
| Fill / Delivery | 实际可量化 | 承诺量 vs 实际成交 |
| 无效流量（GIVT） | 欺诈比例 | 应显著低于公开竞价 |

**判断准则**：PMP 贵不贵，**不能只看 CPM 贵了多少**，要看"每千次有效展示的品牌价值提升是否覆盖了溢价"。若 Viewability 升 20%、GIVT 降 30%，即使 CPM 贵 30%，很多品牌仍认为值得。

### Q9：买卖双方角色混淆——我自己既当买方又当卖方？

作为 Agency/品牌，DV360 里你多数是**买方**，通过 `dv360_list_sellers` 找发布商、`dv360_list_proposals` 收提案。如果你同时在 GAM（卖方侧）管理库存，注意：PMP deal 的"创建"通常在 GAM/Exchange 侧完成，DV360 侧是"接受 + 绑定"。职责不要混，否则容易出现"两边都建、结果 deal 不生效"的错乱。

### Q10：跨媒体（非 Google）的 PMP 也能在 DV360 里买吗？

**可以，但受限较多**。DV360 对接多种 Exchange/SSP（OpenX、Rubicon、Index Exchange 等），跨 Exchange 的 PMP 需要：
1. 该 Exchange 已开通 DV360 对接。
2. deal 的 buyer 账户在 DV360 侧已正确关联到该 Exchange。
3. 该 Exchange 支持 DV360 的出价协议。
跨 Exchange 的 deal 往往同步慢、fill 不稳定，建议优先使用与 Google Ad Manager 直连的 deal，跨媒体 PMP 作为补充。排查时用 `dv360_list_sellers` 看卖家属于哪个 Exchange。

---

## 五、自测题

### 题目 1：概念辨析
PMP（Private Marketplace）与 Preferred Deal（PREFERRED_DEAL）的核心区别是什么？为什么说"读源码时它们是两个不同的枚举"？

<details><summary>查看答案</summary>

**PMP** 是**多买方竞拍**：多个受邀买方出价，价高者得（第二价格），有 floor 作为参与门槛，量不保证。**Preferred Deal** 是**单一买方先到先得**：一个买方出价 ≥ floor 即成交，非竞拍，优先于公开市场。二者在 DV360 中是两个独立枚举：`PRIVATE_MARKETPLACE` 与 `PREFERRED_DEAL`（见 `get_transaction_type_options()`），谈判、定价、fill 行为都不同，混用会导致成交语义错判。
</details>

### 题目 2：floor 的作用
为什么说"PMP 里出价低于 floor 等于没出价"？当只有一个受邀方出价时，成交价等于多少？

<details><summary>查看答案</summary>

floor 是硬性参与资格线，出价 < floor 的请求被 Exchange 直接判负，fill ≈ 0，所以"低价搏量"无效。第二价格拍卖下，当只有一个买方出价（设为 B）且 B ≥ floor 时，成交价 = max(次高价, floor) = floor（因为此时次高价 < floor）。因此 **floor 是单一买方场景下的实际保底成交价**，这也是谈 PMP 的核心是压 floor 的原因。
</details>

### 题目 3：定向叠加
为什么"deal 已经圈定广告位 + LineItem 又叠加同维度位次定向"会导致 fill 断崖？

<details><summary>查看答案</summary>

这是"双重供给侧约束"。deal 圈定的是"哪些广告位参与竞拍"，LineItem 上再叠加同样的位次定向，就变成"既要属于 deal 的位次，又要命中 LineItem 圈定的位次"，两个集合即使不完全相等，交集也会被严重收窄甚至为空。正确做法是：**deal 管供给（在哪买），LineItem 定向管需求（买给谁），两维度尽量正交**；位次/APP/内容类目留给 deal，人群/兴趣/设备放在 LineItem 定向里。
</details>

### 题目 4：流程顺序
"接受提案"和"把 deal 绑定到 LineItem"是同一件事吗？漏了哪一步会导致 deal 被接受了却一直没有量？

<details><summary>查看答案</summary>

**不是同一件事**。`dv360_accept_proposal(proposal_id)` 只是接受卖方提案、让 deal 进入可用状态；把 deal 真正用于投放，需要在 `dv360_create_line_item` 或 `dv360_update_line_item` 时把 `deal_id` 写入 LineItem 的 exchange 配置。标准化流程：`dv360_list_sellers` → `dv360_list_proposals` → `dv360_accept_proposal`/`reject_proposal` → `dv360_create_line_item`（绑 deal）→ `dv360_get_report` 监控。漏掉第 4 步绑定，deal 就只是个"接受了但没接线的 deal"，LineItem 只走公开竞价，自然没有 PMP 的量。
</details>

### 题目 5：优化判断
PMP fill 低的"第一顺位排查项"是什么？为什么 90% 的新手都栽在这里？

<details><summary>查看答案</summary>

第一顺位排查**出价是否 ≥ floor**。因为 floor 是硬门槛，出价 < floor 的请求 100% 判负，fill 直接归零。新手最容易犯的错是"用公开竞价的习惯压低出价去 PMP 里搏量"，结果一个都成交不了。正确姿势：先把出价提到 floor 上 5%-15%，再看定向交集与行业峰谷，最后看 deal 容量与受邀竞争。
</details>

---

## 附：本章方法论速记

```
一句话：PMP = 邀请制 + 底价 + 竞拍的优质库存通道。
四步闭环：发现(卖家/提案) → 决策(接受/拒绝) → 落地(绑 LineItem)
          → 监控(fill/成本/量级)。
三不混：PMP≠Preferred Deal（竞拍 vs 先到先得）；
        接受提案≠绑定 LineItem；PMP≠PG（不保量）。
两正交：deal 管供给，定向管需求，不要叠加同维度。
一核心：谈 PMP 就是谈 floor。
```

> 延伸阅读：本文与 `dv360-architecture-deep.md`（交易类型总览）、`dv360-dfp-deep.md`（GAM/SDC 对接）互补；本文聚焦买家侧 PMP 落地全流程，前两文聚焦架构与卖买对接。姊妹篇 `dv360-05-programmatic-guaranteed`（如已存在）覆盖 PG 保量流程，可对照阅读。
