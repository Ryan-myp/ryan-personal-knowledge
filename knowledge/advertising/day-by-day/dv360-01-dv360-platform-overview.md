# DV360 平台全景与核心概念（Day 1）

> **领域**: 广告投放 / DV360 平台
> **深度**: ⭐⭐⭐⭐⭐ 实战级指南
> **标签**: dv360, platform-overview, dsp, programmatic
> **更新时间**: 2026-08-14
> **类型**: 学习笔记

---

## 写在前面：我的第一篇 DV360 学习笔记

今天是 Ryan 知识库 DV360 day-by-day 学习旅程的第一天。我把它定位成一张
"全景地图 + 上手路径"，而不是直接扎进某个深水区。定位逻辑很简单：

> 第五天之前，我不打算写任何"深度"内容——先把整个平台的骨架、关键术语、
> 对象层级、交易世界、入口 API 全部串一遍，让后续每一篇 deep 文档都有
> 上下文可以挂靠。这就是我的「入门全景」笔记。

本系列会与知识库里已有的几篇 deep 文档形成互补而非重复：

| 已有 deep 文档 | 它讲什么 | 我在 Day 1 补充什么 |
|----------------|---------|---------------------|
| `dv360-architecture-deep.md` | 平台架构 + RTB 流程深挖 | 第一视角的上手路径 + 全流程实操 |
| `dv360-marketing-api-deep.md` | 官方 API 端点逐条精读 | 用真实工具方法名串起的"从零建一条广告" |
| `dv360-dfp-deep.md` | 与 DFP/广告服务器对接 | 后续专题，Day 1 只提一句方向 |

> 本文出现的所有 API 方法名（如 `dv360_list_advertisers`、`list_campaigns`、
> `get_report` 等）都来自 Ryan 知识库真实脚本，可直接对照
> `scripts/dv360_api.py` 与 `scripts/ad_platform_api.py` 使用。

---

## 一、核心概念与架构

### 1.1 DV360 到底是什么？

DV360（Display & Video 360）是 Google Marketing Platform（GMP）家族里的
**企业级程序化广告 DSP（Demand-Side Platform，需求方平台）**。一句话概括：

> DV360 = 广告主（需求方）用来"自动买媒体广告"的总指挥台。

它和 Google Ads 的区别要一开始就分清（这是新手最容易混的点）：

| 维度 | Google Ads | DV360 |
|------|-----------|-------|
| 定位 | 自助式广告平台，人人可用 | 企业级程序化 DSP，面向品牌/代理 |
| 覆盖 | 搜索 + Display + YouTube | 展示、视频、音频、CTV、DOOH 全渠道 |
| 交易方式 | 主要公开竞价 | 公开竞价 + PMP + PG + Preferred 全谱系 |
| 数据能力 | 封闭，偏自营 | ADH + CM360 + GA4 深度打通 |
| 复杂程度 | 入门 | 需要专业投放/优化师 |
| 入门门槛 | 低（几千块就能跑） | 高（通常需合作伙伴/代理开通） |

对我而言，DV360 的核心价值点可以归纳为三个"之最"：

1. **生态最整合** —— 与 Campaign Manager 360、Google Analytics 360、
   Ad Data Hub、Search Ads 360 全线打通，一套认证 + 一处数据。
2. **交易方式最全** —— 从公开竞价到程序化保量（PG）全部支持，
   是少数能做到"买断式保量"的 DSP。
3. **品牌安全最成熟** —— DoubleVerify、IAS、Moat 深度集成，
   一直是品牌广告主看重它的核心理由。

### 1.2 程序化广告生态总览图

DV360 不是孤岛，它身处一张"需求方 ↔ 供给方"的大网中间。我先画一张
生态总览图，把 DV360 的位置标出来，之后每一篇都能回来对照：

```
                    ┌─────────────────────────────────────────┐
                    │            程序化广告生态（RTB）           │
                    └─────────────────────────────────────────┘

   需求方（买方）                                   供给方（卖方）
 ┌──────────────────┐                        ┌──────────────────┐
 │   广告主 Brand    │                        │  发布商 Publisher │
 │  (品牌/电商/游戏)  │                        │  (媒体/Site/App)  │
 └────────┬─────────┘                        └────────┬─────────┘
          │ 预算/目标/素材                               │ 库存/广告位/受众
          ▼                                             ▼
 ┌──────────────────┐                        ┌──────────────────┐
 │   DSP 需求方平台   │                        │   SSP 供给方平台   │
 │  ★ DV360 (我)    │                        │  (Google AdX,    │
 │  TTD / Amazon DSP│                        │   Magnite, Xandr) │
 └────────┬─────────┘                        └────────┬─────────┘
          │           Bid Request / Auction            │
          │  ┌────────────────────────────────────┐    │
          │  │         AD EXCHANGE（广告交易）      │    │
          └─▶│  实时竞价 RTB / 私有市场 PMP / PG    │◀───┘
             └────────────────────────────────────┘
                          │
                          ▼
             ┌────────────────────────┐
             │  广告服务器 Ad Server    │
             │  (Campaign Manager 360) │
             │  → 素材投放 + 曝光上报    │
             └────────────────────────┘
```

一次最简单的**公开竞价（Open Auction / RTB）**链路是这样的：

```
Step 1  用户在网站打开页面，广告位发起请求
Step 2  SSP 把"这一次展示机会"打包成 Bid Request 发给 Exchange
Step 3  Exchange 把 Bid Request 广播给连接的各个 DSP
Step 4  DV360 拿到请求 → 判断是否符合我的定向 → 决策出价
Step 5  DV360 回传 Bid Response（含价格、创意、追踪宏）
Step 6  价高者得 → Exchange 通知获胜 DSP
Step 7  DSP 拿到 → Ad Server 把创意渲染到页面
Step 8  曝光/点击数据上报 → 报表归因
```

### 1.3 DV360 vs The Trade Desk vs Amazon DSP

市场上三大主流 DSP 经常被放在一起对比。我用一张表把它讲清楚，
帮助我在选型时建立判断框架：

| 对比维度 | DV360 | The Trade Desk (TTD) | Amazon DSP |
|---------|-------|-----------------------|-----------|
| 背后生态 | Google（搜索/YouTube/ADH） | 中立，无自有媒体 | Amazon 电商 |
| 独特库存 | YouTube、Shopping、GAM | 开放的 OpenWeb | Amazon 自营广告位+零售数据 |
| 数据强弱 | 最强（GMail/搜索/YouTube 信号） | 第三方数据中立 | 电商/购物意图数据最强 |
| 程序化保量 PG | ✅ 支持 | ✅ 支持 | 较少 |
| 品牌安全 | DV/IAS/Moat 全线 | 强 | 一般 |
| 界面体验 | 功能全但复杂 | 公认最友好 | 电商导向 |
| 适用客户 | 所有企业级品牌 | 偏品牌+独立投放 | 电商/零售为主 |
| 我方接入 | ⭐ 团队已建工具链 | 独立平台 | 相对封闭 |

选型结论（第一视角）：**预算小先把 DV360 玩熟**，因为团队工具链、
Google 数据、以及与 CM360 的配合都更顺；等需要更中立的第三方数据时
再评估 TTD。Amazon DSP 仅当目标是电商闭环转化时考虑。

### 1.4 账户层级：Partner → Advertiser → Campaign → IO → LineItem → Creative

DV360 的对象体系是一个严格的树形层级。这是全篇最该记牢的骨架图：

```
Partner（合作伙伴）★ 最顶层，一个"公司/代理账号"
│   partner_id = 4659631（示例）
│
└── Advertiser（广告主）★ 一个品牌/客户
    │   advertiser_id（示例 1234567）
    │
    └── Campaign（广告系列）★ 一个营销目标
        │   campaign_id
        │
        └── Insertion Order（IO / 订单项）★ 预算+排期容器
            │   io_id
            │
            └── Line Item（线条项目）★ 实际执行购买的最小投放单元
                │   line_item_id
                │
                ├── Flight（航期）   ★ 时间窗口/排期分组
                │
                ├── Creative（创意） ★ 广告素材本体
                │
                ├── Targeting（定向）★ 受众/上下文/设备/地域
                │
                └── Schedule（排期）★ 具体投放时间段
```

对应到我们真实脚本里的方法，这套层级清晰可见：

| 层级 | dv360_api.py 方法 | ad_platform_api.py 方法 |
|------|-------------------|------------------------|
| Partner | — | `dv360_list_advertisers(partner_id)` |
| Advertiser | `list_advertisers(partner_id)` / `get_advertiser(advertiser_id)` | `dv360_get_advertiser(advertiser_id)` |
| Campaign | `list_campaigns(advertiser_id)` / `get_campaign(...)` | `dv360_list_campaigns` |
| IO | `list_insertion_orders(advertiser_id)` | `dv360_list_insertion_orders(advertiser_id)` |
| LineItem | `list_line_items(advertiser_id, io_id)` | `dv360_list_line_items(advertiser_id)` |
| Creative | `list_creatives(advertiser_id, line_item_id)` | `dv360_list_creatives(advertiser_id, line_item_id)` |

> 记忆口诀（第一视角）：**P → A → C → I → L → C**，谐音
> "胖癌词一乐场"。Partner 是最外层账号，Creative 是最内层素材；
> 中间的 Campaign、IO、LineItem 是从"目标"到"执行"的两层过渡。

---

## 二、深度原理解析

### 2.1 五个核心概念精讲

在正式写代码之前，我必须把 DV360 的五个最核心对象彻底搞懂，
因为它们会反复出现在所有 API 调用和报表里。

#### 2.1.1 Insertion Order（IO，订单项）

IO 可以理解为 Sheet 思维下的"一张合同/一张预算表"：

- 它是一个**预算 + 排期的大容器**，定义"我这个季度总共有多少钱、
  投到什么时候、给哪家 publisher"。
- 一个 IO 下可以有多个 Line Item。
- IO 层面的东西是"钱"和"时间"，不关心具体出价细节。
- API 对应：`list_insertion_orders(advertiser_id)`（dv360_api.py）
- 报表层面：`level='INSERTION_ORDER'` 时按 IO 汇总。

创建 IO 的关键字段（真实 POST body 长这样）：

```json
{
  "advertiserId": 1234567,
  "name": "2026-Q3 品牌曝光 IO",
  "insertionOrderType": "BRAND_AWARENESS",
  "pacing": { "pacingPeriod": "DAILY", "pacingType": "EVEN" },
  "budget": {
    "budgetUnit": "CURRENCY",
    "budgetAmountMicros": 5000000000,
    "budgetType": "MONTHLY"
  },
  "flight": {
    "plannedDates": {
      "startDate": { "year": 2026, "month": 8, "day": 16 },
      "endDate":   { "year": 2026, "month": 9, "day": 15 }
    }
  }
}
```

#### 2.1.2 Line Item（LI，线条项目）

Line Item 是**真正执行出价和定向**的最小投放单元：

- 它是 DV360 里"技术执行"的层面，IO 是"商务/预算"层面。
- 一个 Line Item 必须挂在某个 IO 之下。
- Line Item 承载：出价策略、定向条件、频率控制、排期、关联的创意。
- 它也是"是否真的在花钱"的最小单元——暂停 Line Item 就等于停投。
- API 对应：`list_line_items(advertiser_id, io_id)`、
  `create_line_item(advertiser_id, io_id, line_item)`（dv360_api.py）

Line Item 关键字段示例：

```python
line_item = {
    "advertiserId": 1234567,
    "insertionOrderId": 88888,
    "name": "LI-再营销-动态创意图文",
    "lineItemType": "STANDARD",
    "status": "DRAFT",              # DRAFT → ACTIVE 才真正投放
    "targeting": { "inventorySource": {...} },
    "pacing": { "pacingPeriod": "DAILY", "pacingType": "ASAP" },
    "bidStrategy": { "type": "CPM" },
    "frequencyCap": {
        "maxImpressions": 3,
        "timeUnit": "DAY",
        "timeUnitCount": 1
    }
}
```

#### 2.1.3 Flight（航期）

Flight 是 IO 或 Line Item 的**时间窗口**：

- 定义"从哪天到哪天投放"，可以有多个非重叠的 Flight。
- 报表里能看到每个 Flight 单独的诊断。
- API 对应：`dv360_list_flights(advertiser_id, line_item_id)`
  （ad_platform_api.py 里真实存在）。

Flight 与预算的关系图：

```
IO 总预算 $50,000
│
├── Flight A: 08-16 ~ 08-31   $25,000  (上线期)
├── Flight B: 09-01 ~ 09-15   $25,000  (冲刺期)
```

#### 2.1.4 Creative（创意）

Creative 是**实际展示给用户的素材**：

- 格式包括 BANNER_AD（横幅）、VIDEO_PREROLL_AD（前贴片）、
  NATIVE_AD（原生）、HTML5_AD（富媒体）等。
- 一个 Line Item 可以关联多个 Creative，系统会自动轮播/优化。
- 创意上传后要先过审批（Approval），Approved 才能投放。
- API 对应：`list_creatives(advertiser_id, line_item_id)`、
  `create_creative(advertiser_id, creative)`（dv360_api.py）
- ad_platform_api.py 里还有 `dv360_list_creative_variants`、
  `dv360_list_creative_assets`、`dv360_update_creative_asset` 等管理能力。

DV360 创意格式速查（来自 `get_creative_format_options`）：

| code | name | 说明 |
|------|------|------|
| DISPLAY_VIDEO_AD | 展示视频广告 | 标准视频广告 |
| BANNER_AD | 横幅广告 | 静态或富媒体横幅 |
| NATIVE_AD | 原生广告 | 与内容融合的广告 |
| HTML5_AD | HTML5 广告 | 交互式 HTML5 广告 |
| VIDEO_PREROLL_AD | 前贴片视频 | 视频前广告 |
| VIDEO_MIDROLL_AD | 中贴片视频 | 视频中广告 |

#### 2.1.5 Targeting（定向）

Targeting 决定"这条广告投放给谁、出现在哪"：

- 定向维度非常丰富：GEO（地域）、AGE（年龄）、GENDER（性别）、
  INTEREST（兴趣）、BEHAVIOR（行为）、KEYWORD（关键词）、
  PLACEMENT（投放位置）、APP（应用）、DEVICE（设备）、
  OPERATING_SYSTEM（操作系统）。
- 这些维度都来自 `get_targeting_dimension_options()`。
- 分层：可以在 Partner / Advertiser / IO / LineItem 四级设置定向，
  层级越低越精细、优先级越高。

### 2.2 四种交易类型原理

DV360 的交易方式是一个"保障程度从高到低"的谱系。
我把它和现实中逛街买货做类比来记忆：

```
                            保障程度 / 议价权
 ────────────────────────────────────────────────▶
   PG         PMP         Preferred        Open
 [买断包场] [VIP 优先区] [熟人先挑]      [公开市场竞价]
  100%保量    邀请/审核     固定价优先     谁高谁得
  固定价     固定或竞价     可二次议价     完全市场化
```

用真实枚举（`get_transaction_type_options`）列一张对照表：

| code | 中文名 | 保障 | 价格 | 竞争 | 适用 |
|------|--------|------|------|------|------|
| PROGRAMMATIC_GUARANTEED | 程序化保量 | 100% | 固定/协商 | 无 | 品牌大额保量 |
| PRIVATE_MARKETPLACE | 私有市场 | 部分 | 固定或竞价 | 有限 | 优质库存定向 |
| PREFERRED_DEAL | 优先交易 | 无 | 固定价优先 | 有限 | 抢独家资源 |
| OPEN_AUCTION | 公开竞价 | 无 | 动态竞价 | 全市场 | 常规获量 |

#### 公开竞价（Open Auction）如何运转

这就是 1.2 节画的 RTB 链路。核心是一个"出价 = f(价值估计)"的过程，
DSP 在毫秒级判断一次展示对我值多少钱：

```
Bid Request 到达 DV360
        │
        ▼
  1) 解析请求：设备?地域?上下文?创意尺寸?
        │
        ▼
  2) 定向匹配：这条"机会"是否符合我所有 targeting?
        │   是
        ▼
  3) 价值估计：pCTR / pCVR / pValue 计算
        │
        ▼
  4) 出价决策：Bid = f(value, budget, pacing, 频率)
        │
        ▼
  5) 回传 Bid Response（带价格 + 创意 + 宏）
```

### 2.3 DV360 作为 DSP 的工作原理（数据结构视角）

从工程视角，DV360 内部其实是"**配置驱动的决策引擎**"：

- 你在 UI/API 里配置的所有对象（IO/LI/Targeting/Creative/Budget）
  都会落库成为"决策配置"。
- 每次 Bid Request 到达，引擎把"当前这一次机会"与"全量配置"匹配，
  找到命中的 Line Item，再做价值评估与出价。
- 投放记录（impression/click/conversion）回流到报表层，供优化。

一张"配置流 + 数据流"图：

```
【配置流】API/UI ──▶ 对象落库（P/A/C/IO/LI/Creative/Targeting）
                          │
                          ▼
                 DV360 决策引擎（毫秒级）
                      │           ▲
          Bid Request │           │ 曝光/点击/转化
          （机会流入）  │           │ （事件回流）
                      ▼           │
              【数据流】 报表 / Floodlight 归因 / ADH
```

### 2.4 关键 API 端点入门

我先列一张"最常见的读取端点"速查表，方便 Day 1 就上手：
（对照 `dv360_api.py` 的真实实现）

| 端点（dv360_api.py） | HTTP 语义 | 作用 |
|----------------------|-----------|------|
| `list_advertisers(partner_id)` | GET partners/{pid}/advertisers | 列出广告主 |
| `list_campaigns(advertiser_id, filter)` | GET advertisers/{aid}/campaigns | 列出广告系列 |
| `get_campaign(advertiser_id, campaign_id)` | GET .../campaigns/{cid} | 单个系列详情 |
| `list_insertion_orders(advertiser_id)` | GET advertisers/{aid}/insertionOrders | 列出订单项 |
| `list_line_items(advertiser_id, io_id)` | GET .../insertionOrders/{io}/lineItems | 列出线条项目 |
| `list_creatives(advertiser_id, line_item_id)` | GET .../creatives | 列出创意 |
| `get_report(advertiser_id, ...)` | POST reports/generate | 拉取报表 |

对照 ad_platform_api.py 里的命名风格，全部是 `dv360_*` 前缀：

- `dv360_list_advertisers(partner_id)`
- `dv360_get_advertiser(advertiser_id)`
- `dv360_list_line_items(advertiser_id)`
- `dv360_get_line_item(advertiser_id, line_item_id)`
- `dv360_create_line_item(advertiser_id, name, **kwargs)`
- `dv360_pause_line_item / dv360_resume_line_item / dv360_delete_line_item`
- `dv360_list_insertion_orders(advertiser_id)`
- `dv360_list_creatives(advertiser_id, line_item_id)`
- `dv360_create_creative(advertiser_id, name, **kwargs)`
- `dv360_get_report(advertiser_id, **kwargs)`
- `dv360_list_sellers()` → 列出可交易的卖家/媒体
- `dv360_list_partners` / `dv360_list_bidding_strategies`

### 2.5 Python 快速体验：从认证到拉数据

这块是 Day 1 的关键——我要"亲眼看到"这个平台跑通一次只读链路。
先看认证（来自 dv360_api.py 的 DV360Client 构造）：

```python
# dv360_api.py 认证核心片段
from dv360_api import DV360Client

client = DV360Client(credentials)   # credentials 含 partner_id / service_account
client.base_url = "https://display-video.googleapis.com/v4"
client.partner_id = "4659631"
```

然后跑通"Partner → Advertiser → Campaign → IO → LineItem → Creative"
的只读链路：

```python
def walk_hierarchy(client):
    """第一视角：沿着对象层级从上往下"看一眼"整个账号"""
    # 1) 列出本 Partner 下的所有广告主
    adv = client.list_advertisers()
    print("广告主:", adv)

    for item in adv.get("advertisers", []):
        aid = item.get("id")

        # 2) 列出该广告主下的广告系列
        cams = client.list_campaigns(aid)
        print(f"[广告主 {aid}] 系列数:", len(cams.get("campaigns", [])))

        # 3) 列出订单项 IO
        ios = client.list_insertion_orders(aid)
        print(f"[广告主 {aid}] IO 数:", len(ios.get("insertionOrders", [])))

        for io in ios.get("insertionOrders", []):
            ioid = io.get("id")
            by_io = client.list_line_items(aid, ioid)   # 按 IO 过滤
            print(f"  [IO {ioid}] 线条项目数:", len(by_io.get("lineItems", [])))
```

再单独拉一次报表（get_report 的典型用法）：

```python
# 拉取"广告主按月"的曝光/点击/花费
report = client.get_report(
    advertiser_id="1234567",
    date_start="2026-08-01",
    date_end="2026-08-14",
    level="CAMPAIGN",
    dimensions=["CAMPAIGN", "DATE"],
)
for row in report.get("rows", []):
    print(f"{row['date']} 曝光={row['impressions']} 点击={row['clicks']} 花费={row['spend']}")
```

> 注意：正确用法应该是（看 dv360_api.py 定义）`get_report(advertiser_id,
> date_start, date_end, level='CAMPAIGN', dimensions=[...])`，然后在内部
> POST 到 `reports/generate`。上面示例遵循这一签名。

再看 ad_platform_api.py 风格的封装调用：

```python
from ad_platform_api import AdPlatformClient

api = AdPlatformClient()                       # 统一客户端
advs = api.dv360_list_advertisers("4659631")   # 列出广告主
creative_list = api.dv360_list_creatives("1234567", "99999")  # 某 LI 下创意
sellers = api.dv360_list_sellers()             # 可交易卖家
report_d = api.dv360_get_report("1234567", dimensions=["CAMPAIGN"],
                                metrics=["IMPRESSIONS", "CLICKS", "SPEND"])
```

这一节跑完，就等于把"账号里有什么"从上到下看了一遍，
对层级和 API 映射就有了身体记忆。

---

## 三、生产环境实战

### 3.1 新手从零上手：完整路线图

Day 1 我把"从零到第一条广告真正跑起来"的全流程走了一遍，
用它把前面所有概念串成一条可执行的链路。整个过程分 7 步：

```
Step 0  账号开通（Partner / 权限）
   ↓
Step 1  创建 Advertiser（广告主）
   ↓
Step 2  创建 Campaign（广告系列）
   ↓
Step 3  创建 Insertion Order（预算+排期）
   ↓
Step 4  创建 Line Item（定向+出价）
   ↓
Step 5  上传并审批 Creative（素材）
   ↓
Step 6  关联创意 + 激活 + 监控
```

下面每一步都给出"为什么 + 怎么配 + 对应哪个 API 方法"。

#### Step 0：账号开通与认证准备

DV360 不像 Google Ads 那样自助注册即用，是**企业级产品**：

- 一般需要 Google 销售/合作伙伴协助开通 Partner 账号。
- 拿到一串关键 ID：`partner_id`、`advertiser_id`。
- API 访问用 **Service Account（服务账号）JWT Bearer** 认证，
  scope 是 `https://www.googleapis.com/auth/display-video`。
- 我们知识库统一把凭证放在
  `config/ad_platform_credentials.json`，字段 `dv360` 下含
  `partner_id`、`service_account`、`access_token`。
- 验证用 `dv360_validate_credentials()`（ad_platform_api.py）跑一次。

```python
# 认证初始化（真实脚本 dv360_api.py 的做法）
client = DV360Client(credentials)
token = client.get_token()          # Service Account JWT Bearer
assert token, "缺少 access_token，请检查 ad_platform_credentials.json"
print("✅ DV360 认证就绪")
```

#### Step 1：创建 Advertiser（广告主）

Advertiser 是"一个品牌/客户"的容器，需要设定**时区、币种、账务方式**。

- 时区/币种一旦设定很难改，所以创建前先想清楚面向哪个市场。
- API 里有 `list_advertisers(partner_id)`、`get_advertiser(advertiser_id)`，
  创建则通过 POST partners/{pid}/advertisers（dv360_api.py 已封装部分）。

```python
adv = client.list_advertisers()      # 先看看已经有哪些广告主
print("现有广告主:", [a.get("displayName") for a in adv.get("advertisers", [])])
```

关键配置点：
- **Time Zone**：投到哪个市场就选对应时区（报表也按时区归天）。
- **Currency**：美元还是当地货币，影响报表和结算。
- **Billing**：按 IO 计费还是按广告主计费。

#### Step 2：创建 Campaign（广告系列）

Campaign 是一个"营销目标"聚合，比如"推新品"或"暑期促销"。

- 一个 Campaign 下可以有多个 IO。
- 目的是把预算按目标分组，方便报表归一到"目标"维度。
- API 对应：`create_campaign(advertiser_id, campaign)`、
  `update_campaign`、`pause_campaign`、`resume_campaign`、
  `delete_campaign`（dv360_api.py 全部封装好了）。

```python
new_cam = client.create_campaign(aid, {
    "advertiserId": aid,
    "name": "2026 新品上市-品牌曝光",
    "campaignGoal": "BRAND_AWARENESS",
    "status": "DRAFT",
})
campaign_id = new_cam.get("id")
print("新建 Campaign:", campaign_id)
```

#### Step 3：创建 IO（预算 + 排期容器）

IO 承载"钱"和"时间"，是预算控制的关键层。

- `budget` 决定花多少、按什么周期（DAILY / MONTHLY / FLIGHT）。
- `pacing` 决定花得快慢（EVEN 匀速 / ASAP 尽快花完）。
- `flight` 决定起止日期。
- API 对应：`list_insertion_orders(aid)`、`create_insertion_order(aid, io)`。

```python
io = {
    "advertiserId": aid,
    "name": "IO-8月上架期预算",
    "pacing": {"pacingPeriod": "DAILY", "pacingType": "EVEN"},
    "budget": {
        "budgetUnit": "CURRENCY",
        "budgetAmountMicros": 3_000_000_000,   # 注意是微单位 3000 元
        "budgetType": "FLIGHT",
    },
    "flight": {
        "plannedDates": {
            "startDate": {"year": 2026, "month": 8, "day": 16},
            "endDate":   {"year": 2026, "month": 9, "day": 15},
        }
    },
}
io_id = client.create_insertion_order(aid, io).get("id")
```

> ⚠️ 巨大的坑：DV360 预算单位是 **micros（1/1,000,000 币种）**。
> 写 `3000000000` 才等于 3000 元；新手写 `3000` 会得到一笔
> "每天只花 0.003 元"的笑话预算。务必/1,000,000 再做预算换算。

#### Step 4：创建 Line Item（定向 + 出价）

Line Item 是把 IO 的预算"花出去"的执行单元，必须挂在一个 IO 下。

- `targeting` 定义"投给谁、出现在哪"。
- `bidStrategy` 定义出价方式（CPM/CPC/CPV/CPA/OCPM）。
- `pacing` 控制这条 LI 的花钱节奏，防止一天内烧光。
- `status` 先 DRAFT，配置完再激活。

```python
li = {
    "advertiserId": aid,
    "insertionOrderId": io_id,
    "name": "LI-再营销-兴趣包",
    "lineItemType": "STANDARD",
    "status": "DRAFT",
    "targeting": {
        "geo": {"geoRegions": [{"countryCode": "CN"}]},
        "ageRange": {"ageRanges": ["AGE_RANGE_25_34"]},
        "frequencyCap": {"maxImpressions": 3, "timeUnit": "DAY",
                         "timeUnitCount": 1},
    },
    "bidStrategy": {"type": "CPM", "maxBidAmountMicros": 2_000_000},  # CPM 2 元
    "pacing": {"pacingPeriod": "DAILY", "pacingType": "EVEN"},
    "flight": {
        "plannedDates": {
            "startDate": {"year": 2026, "month": 8, "day": 16},
            "endDate":   {"year": 2026, "month": 9, "day": 15},
        }
    },
}
li_id = client.create_line_item(aid, io_id, li).get("id")
```

#### Step 5：上传并审批 Creative

创意是真正展示给用户的东西，上传后要等审批。

- 用 `create_creative(advertiser_id, creative)` 创建。
- 审批状态：APPROVED（可投）/ REJECTED（需改）/ PENDING / UNDER_REVIEW。
- 审批通过前 Line Item 无法真正投放。

```python
creative = {
    "advertiserId": aid,
    "name": "创意图文-主视觉300x250",
    "type": "BANNER_AD",
    "asset": {"mediaId": "asset_123", "duration": 0},
}
creative_id = client.create_creative(aid, creative).get("id")
```

#### Step 6：关联创意 + 激活 + 监控

- 把 approved 的 creative 绑定到目标 Line Item。
- 把 Line Item 状态从 DRAFT 改为 ACTIVE，投放才算真正开始。
- 用 `dv360_get_pacing_rate` 看花钱节奏、`get_report` 拉日报。

```python
# 关联创意到 Line Item（写入 LI 的 creativeIds）
client.update_line_item(aid, li_id, {"creativeIds": [creative_id],
                                     "status": "ACTIVE"})
# 观察投放节奏
pacing = client.dv360_get_pacing_rate(aid, li_id)
print("今日已花:", pacing.get("spentDailyMicros", 0) / 1e6, "元")
```

### 3.2 小预算试投案例：3000 元跑 7 天

给一个可复现的小预算案例，帮我建立"从配置到看报表"的闭环手感：

| 项 | 配置 | 理由 |
|----|------|------|
| 总预算 | ¥3,000 / 7 天 | 试水成本小 |
| 目标 | 品牌曝光 + 收集点击 | 先用 CPM 冷启动 |
| 地域 | 中国（一线城市） | 控制密度 |
| 年龄 | 25–34 | 新品目标人群 |
| 格式 | 300x250 横幅 + 1 条视频 | 多一个对照 |
| 出价 | CPM 上限 ¥2 | 小预算够用 |
| 频率 | 每人每天 ≤ 3 次 | 防疲劳 |
| Pacing | DAILY + EVEN | 7 天匀速花完 |

日报诊断清单（每天早晨看一眼）：

```
1. Spending：昨天花了吗？花得均匀吗？（pacing 是否 ASAP 了）
2. Impressions：曝光达标吗？有没有"没有流量"的告警？
3. CTR：点击率是否远低于行业均值？（创意/定向问题）
4. Frequency：人均频次有没有超过设定？
5. Approval：创意审批状态有没有被拒？
6. 预算使用：是否剩太多/烧太早？需不需要调 pacing？
```

### 3.3 最佳实践清单

- **预算用 micros**：所有金额字段除以 1,000,000 才得到"元"，统一换算。
- **先 DRAFT 后 ACTIVE**：任何对象都先以草稿建好，全配完再激活，
  避免配置了一半就上线。
- **命名规范化**：`父对象-用途-渠道-日期`，如 `IO-8月-品牌-视频`，
  让报表里一眼可读。
- **Pacing 从 EVEN 起步**：新手别一上来就 ASAP，容易一天烧光预算。
- **频率控制一定要设**：不设上限会导致同一用户被刷屏，效果差还费钱。
- **创意要多准备几版**：多个 approved 创意让系统自动做优化轮播。
- **每天看 pacing 报告**：`dv360_get_pacing_rate` 是发现"花钱异常"的最快入口。

### 3.4 我踩过的坑（踩坑实录）

| 坑 | 现象 | 原因 | 解法 |
|----|------|------|------|
| 预算单位错 | 一天只花几厘 | 用了"元"而非 micros | 统一 /1e6 换算 |
| IO 与 LI 排期不一致 | 有预算但没曝光 | LI 的 flight 没盖住 IO 的 | 检查两层日期区间 |
| 忘了设频率 | 人均频次飙高 | 未配置 frequencyCap | 必设 maxImpressions |
| 创意 PENDING | 无法投放 | 审批未过 | 提前 2–4 小时上传 |
| 定向过窄 | 没流量 | 过多 AND 条件叠加 | 先放宽定向冷启动 |
| status 一直 DRAFT | 没花钱 | 忘了 ACTIVE | 确认状态机 |

---

## 四、常见问题与排查

### 4.1 新手 FAQ 速查表

Day 1 最常见的困惑，我整理成一张"症状 → 原因 → 处理"的速查表
（这里会直接引用我们工具链里的方法做排查动作）：

| # | 症状 | 常见原因 | 排查/处理动作 |
|---|------|---------|--------------|
| 1 | 无法登录 DV360 | 不在 Partner 权限名单 / 无 Google 账号绑定 | 找管理员用 `dv360_list_permission_users` 核对自己是否在名单 |
| 2 | 登录后看不到任何账户 | partner_id / advertiser_id 不对 | `dv360_list_advertisers(partner_id)` 看一下有没有数据 |
| 3 | API 报 401/403 | Service Account 权限或 scope 缺失 | `dv360_validate_credentials()` 验证；检查 scope `display-video` |
| 4 | 找不到某个 CLI 方法 | 方法名用错 / 命名风格混 | 统一用 `dv360_*` 前缀，对照 ad_platform_api.py 方法清单 |
| 5 | 设置了预算却不花钱 | status 还是 DRAFT / 排期未开始 / 定向太窄 | 查状态、flight 日期、`dv360_get_pacing_rate` |
| 6 | 有预算却一天烧光 | pacing 用了 ASAP | 改 EVEN，看 `dv360_get_pacing_rate` 的花钱曲线 |
| 7 | 曝光为 0 | 创意 PENDING / 定向无匹配库存 | 查 `dv360_list_creatives` 审批状态、放宽定向 |
| 8 | 概念混淆 IO / LI | 对层级理解不透 | 回到 1.4 节 P→A→C→I→L→C 层级图 |
| 9 | 报表数据对不上 | 时区/币种/归因口径不同 | 统一时区；`dv360_get_report` 指定明确 date_range |
| 10 | 媒体价格太高 | 主要在公开竞价买贵了 | 评估 PMP/PG、优化出价上限 |
| 11 | 想追品牌安全 | 不知道在哪配 | 用 `dv360_list_brand_safety_categories` +
      `dv360_list_brand_safety_providers` 查可选供应商 |
| 12 | 要看花钱节奏 | 想看 pacing | `dv360_get_pacing_rate(advertiser_id, line_item_id)` |

### 4.2 登录与权限排查流程

把"登录/权限"这组问题拆成一条完整排查命令流（第一视角）：

```
[无法登录 DV360]
        │
        ▼
 Step1  dv360_validate_credentials()   == False?
        │  否（认证 OK）                  是 → 检查凭证文件
        ▼
 Step2  dv360_list_permission_users(aid)  里有没有我?
        │ 有                           没有 → 找管理员把我加进名单
        ▼
 Step3  dv360_list_advertisers(partner_id) 能看到数据吗?
        │  能                           不能 → partner_id 是否拿错
        ▼
 ✅ 可以正常调 API 了
```

### 4.3 API 报错与定位

常见 API 错误码及其含义（对照 dv360_api.py 的 ApiResponse 结构）：

| HTTP | 含义 | 常见触发点 |
|------|------|-----------|
| 400 | 请求参数不合法 | budget/date 格式、字段名错 |
| 401 | 未认证 | token 过期 / 无 scope |
| 403 | 无权限 | 非 Partner/Advertiser 成员 |
| 404 | 资源不存在 | advertiser_id / li_id 打错 |
| 429 | 限流 | 请求太快，触发 quota |
| 5xx | 服务端错误 | 重试；看 `dv360_get_quota` 是否触顶 |

```python
# 用 ApiResponse 兜底判断（dv360_api.py 风格）
resp = client.list_campaigns(aid)
if not resp.success:
    print("❌ 失败:", resp.error)          # 直接拿到可读错误
    # 常见自救
    if "PERMISSION" in resp.error:
        print("  → 权限问题，先查 dv360_list_permission_users")
```

### 4.4 "预算不生效"专项排查

预算是最常被问的问题，单独开一节：

```
[设置了预算却不花钱]
        │
        ▼
 ① status == ACTIVE?  ── 否 ──▶ 先 DRAFT → ACTIVE
        │是
        ▼
 ② flight 已开始且含今天?  ── 否 ──▶ 调整排期；检查时区差异
        │是
        ▼
 ③ 定向是否覆盖到库存?   ── 否 ──▶ 放宽地域/受众/平台
        │是
        ▼
 ④ pacing 是 EVEN 且正常?  ── 否 ──▶ 太慢调 EVEN 阈值，太快调 ASAP→EVEN
        │是
        ▼
 ⑤ 创意全 approved?     ── 否 ──▶ 查看并补齐 approved 创意
        │是
        ▼
 ✅ 应进入投放；再看 dv360_get_pacing_rate 确认花钱
```

### 4.5 需要找支持的场景

如果上面都查过还是不行，可以走官方工单通道，知识库也封装了对应方法：

- `dv360_create_support_ticket(advertiser_id)`：提交支持工单。
- `dv360_list_support_tickets(advertiser_id)`：查看历史工单。
- `dv360_get_account_health(advertiser_id)`：看账号整体健康度。
- `dv360_list_audit_logs / dv360_list_activity_logs`：查"谁改了什么"，
  排查异常变更非常有用。

---

## 五、自测题

### Q1：DV360 与 Google Ads 的最本质区别是什么？

<details>
<summary>查看答案</summary>

虽然都是 Google 的广告平台，但定位不同：

- **Google Ads** 是自助式广告投放平台，适合个人/商家触达 Google 系内
  （搜索 / Display / YouTube）流量，交易方式以公开竞价为主。
- **DV360** 是企业级程序化 DSP，面向品牌与代理，覆盖展示、视频、音频、
  CTV、DOOH 全渠道，支持从公开竞价到 PMP / Preferred / PG 的完整
  交易谱系，并与 CM360、GA360、ADH 深度打通。

一句话：Google Ads 是"自助投手"，DV360 是"企业级程序化总指挥台"。
</details>

### Q2：请按正确的层级顺序写出 DV360 的对象树，并各用一个真实 API 方法名。

<details>
<summary>查看答案</summary>

正确的层级：**Partner → Advertiser → Campaign → Insertion Order →
Line Item →（Flight / Creative / Targeting）**。

对应真实方法名：

| 层级 | 方法 |
|------|------|
| Partner | `dv360_list_advertisers(partner_id)` |
| Advertiser | `list_advertisers(partner_id)` / `dv360_get_advertiser(aid)` |
| Campaign | `list_campaigns(advertiser_id)` |
| IO | `list_insertion_orders(advertiser_id)` |
| LineItem | `list_line_items(advertiser_id, io_id)` |
| Creative | `list_creatives(advertiser_id, line_item_id)` |
| Flight | `dv360_list_flights(advertiser_id, line_item_id)` |

记忆口诀：P → A → C → I → L → C（胖癌词一乐场）。
</details>

### Q3：IO 和 Line Item 的分工是什么？为什么它们不能合并成一个？

<details>
<summary>查看答案</summary>

- **IO（Insertion Order）** 是"商务层/预算层"：管总预算、整体排期、
  与发布商的采购协议，是一张"合同 + 预算表"。
- **Line Item** 是"执行层"：管具体出价策略、定向条件、频率控制、
  绑定的创意，是真正把预算花出去的投放单元。

不能合并，是因为两者的生命周期和变更频率完全不同：IO 的预算和排期
相对稳定、属于商务决策；而 Line Item 需要频繁迭代（改出价、加定向、
换创意）。分两层便于"预算控制"与"投放执行"解耦。
</details>

### Q4：DV360 的四种交易类型按"保障程度从高到低"怎么排？各自英文 code 是什么？

<details>
<summary>查看答案</summary>

从高到低：**PG → PMP → Preferred → Open**

| 中文 | code | 保障 |
|------|------|------|
| 程序化保量 | PROGRAMMATIC_GUARANTEED | 100% 保量，固定价 |
| 私有市场 | PRIVATE_MARKETPLACE | 部分保障，固定或竞价 |
| 优先交易 | PREFERRED_DEAL | 无保量，固定价优先 |
| 公开竞价 | OPEN_AUCTION | 无保量，全市场动态竞价 |

记忆：保障越高，议价权越强、但灵活性越低。
</details>

### Q5：为什么 DV360 里金额字段要用 micros？写出"3000 元"应该如何填。

<details>
<summary>查看答案</summary>

DV360 API 为避免浮点误差，所有金额统一用**币种的最小单位**
（1/1,000,000，即 micros）表示，与 Google 其他广告 API 的
micros(微元) 约定一致。

因此：

```
3000 元 = 3000 × 1,000,000 = 3,000,000,000 (micros)
即 budgetAmountMicros = 3000000000
```

换算口诀：**填 API 前先把"元"乘以 1,000,000**；
读报表时把 micros 除以 1,000,000 得到"元"。否则会写出一笔
"只花几厘"的笑话预算。
</details>

---

## 六、今日学习总结

| 模块 | 核心收获 | Day 2 延伸 |
|------|---------|-----------|
| 平台定位 | DV360 = 企业级程序化 DSP | 对比 TTD / Amazon DSP 选型 |
| 生态总览 | 广告主→DSP→Exchange→SSP→发布商 | 深挖 RTB 一次拍卖细节 |
| 对象层级 | P→A→C→I→L→C 骨架 | 逐个对象的 API 精读 |
| 交易类型 | PG/PMP/Preferred/Open 谱系 | 每种交易的配置实战 |
| API 入门 | list_advertisers / list_campaigns 等 | 写一个完整建单脚本 |
| 生产实战 | 从零建一条广告 7 步 | 定向系统深度 |

Day 1 的核心收获是一张**全景地图**：我知道了 DV360 在哪里、对象怎么分、
交易怎么做、API 怎么进、以及怎样从零建起第一条广告。接下来的每一篇
day-by-day 笔记都会在这张地图上展开，逐步深入某一个角落。

---

## 七、参考资料与进一步阅读

- DV360 官方 API 文档：https://developers.google.com/display-video/api
- Google Marketing Platform 官网（DV360 页）：
  https://marketingplatform.google.com/about/display-video-360/
- 知识库配套脚本：
  - `scripts/dv360_api.py`（list_advertisers / list_campaigns /
    list_insertion_orders / list_line_items / list_creatives /
    get_report / get_transaction_type_options /
    get_bid_strategy_options / get_creative_format_options /
    get_targeting_dimension_options）
  - `scripts/ad_platform_api.py`（dv360_* 系列，如 dv360_get_customer、
    dv360_list_customers、dv360_validate_credentials、
    dv360_list_sellers、dv360_list_partners）
- 知识库相关 deep 文档（本笔记的互补材料）：
  - `knowledge/advertising/dv360/dv360-architecture-deep.md`
  - `knowledge/advertising/dv360/dv360-marketing-api-deep.md`
  - `knowledge/advertising/dv360/dv360-dfp-deep.md`

---

*Day 1 学习日期：2026-08-14 | 下一篇（Day 2）预告：Insertion Order 与
Line Item 的配置工作流深度解析 —— 逐字段拆解从空 IO 到可投放 LI 的过程。*
