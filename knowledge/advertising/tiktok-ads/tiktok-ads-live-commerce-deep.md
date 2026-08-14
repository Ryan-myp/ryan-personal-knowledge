# TikTok 直播带货广告深度实战：Live Shopping、商品橱窗、达人合作、实时转化追踪

> **领域**: 广告投放 / TIKTOK_ADS
> **深度**: ⭐⭐⭐⭐⭐ 实战级指南
> **标签**: TIKTOK_ADS, 广告投放
> **更新时间**: 2026-08-14
> **类型**: 深度知识文档

---

> **文档定位**
> 本文件是 TikTok 直播带货广告(Live Commerce Ads)的专项深度文档。
> 它不重复品牌系列文档的宽泛直播章节(品牌自播/一般投放节奏),
> 而是把焦点收窄到"直播广告专项": LIVE 广告产品细节、直播间实时投流、
> 实时转化追踪与归因、达人合作、直播数据指标体系。
> 全部代码示例基于 scripts/tiktok_api.py 提供的 TikTok Marketing API v1.3 方法,
> 可直接落地到生产环境。
>
> **阅读前置**
> 建议先读 tiktok-ads-architecture-deep.md 建立账户/层级/报表基础,
> 再读本文件理解"直播这个特殊的广告形态"如何在 TIKTOK_ADS 产品体系内运作。
> 直播广告与普通 In-Feed 广告最大的区别在于三个"实时":
> 流量实时、转化实时、调优实时。整个文档都围绕这三个实时展开。

---

## 一、核心概念与架构

### 1.1 直播电商生态全景

直播带货(Live Commerce)不是单纯"多了一种广告位", 而是把
"内容消费""商品交易""即时互动"三者压缩进同一个时间窗口的完整商业形态。

在 TikTok 体系内, 直播带货生态由这些实体组成:

```
                    TikTok Live Commerce 生态全景图

 ┌──────────────────────────────────────────────────────────────────────┐
 │                        内容层 (Content Layer)                         │
 │                                                                      │
 │  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐          │
 │  │ 品牌自播  │   │  达人直播 │   │ 明星直播  │   │ MCN 直播 │          │
 │  │ BrandLive │   │ Creator  │   │ Celebrity│   │ 机构矩阵  │          │
 │  └────┬─────┘   └────┬─────┘   └────┬─────┘   └────┬─────┘          │
 │       │              │              │              │                 │
 ̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲̲
 │                               ▼                                    │
 │   ┌───────────────────────────┴───────────────────────────┐        │
 │   │               直播间实体 (Live Room)                    │        │
 │   │  直播画面 / 口播 / 互动 / 商品卡片 / 优惠券 / 购物车     │        │
 │   └───────────────────────────┬───────────────────────────┘        │
 └───────────────────────────────┼────────────────────────────────────┘
                                 │
 ┌───────────────────────────────┼────────────────────────────────────┐
 │                       交易层 (Transaction Layer)                    │
 │                                 ▼                                  │
 │   ┌────────────────────┐    ┌──────────────────────┐               │
 │   │   TikTok Shop      │    │   商品橱窗 / 展示柜    │               │
 │   │  (商城/购物车/支付) │    │  (Showcase / 图文/视频挂橱窗)│          │
 │   └────────────────────┘    └──────────────────────┘               │
 │                                 │                                  │
 │   ┌────────────────────┐    ┌──────────────────────┐               │
 │   │   联盟带货           │    │   订单/售后/履约       │               │
 │   │  (Affiliate 分佣)   │    │  (Order/Return/Logistics)│           │
 │   └────────────────────┘    └──────────────────────┘               │
 └───────────────────────────────┼────────────────────────────────────┘
                                 │
 ┌───────────────────────────────┼────────────────────────────────────┐
 │                       广告层 (Ads Layer)                             │
 │                                 ▼                                  │
 │   ┌────────────────────────────────────────────────────────────┐   │
 │   │  LIVE_2_SHOP 直播购物广告 / 直播推广 / 购物车广告            │   │
 │   │  Spark Ads + LIVE / 短视频挂直播预告 / 直播间引流             │   │
 │   └────────────────────────────────────────────────────────────┘   │
 │       |                                                          │   │
 │       +--> TikTok Marketing API (business-api.tiktok.com)        │   │
 │              ├─ 广告管理(campaign/adgroup/ad)                    │   │
 │              ├─ 转化追踪(Pixel / CAPI / 自定义转化)              │   │
 │              └─ 实时报表(report/get)                             │   │
 └───────────────────────────────────────────────────────────────────┘
```

整个生态的运转逻辑可以概括为一句:
**用内容层的直播建立信任, 用交易层完成转化, 用广告层放大流量。**

三层缺一不可:

| 层级 | 核心产出 | 失败时会怎样 |
|------|---------|-------------|
| 内容层 | 观看、停留、互动、信任 | 直播无聊, 进来的人秒退, 转化无从谈起 |
| 交易层 | 下单、支付、GMV、履约 | 商品不行/价格不优, 有流量也没成交 |
| 广告层 | 精准且实时的流量放大 | 没投流, 只靠自然流量, 场观天花板极低 |

广告投放负责的角色, 是"在正确的时间, 把直播间推给正确的人,
并让这些人的转化数据实时回流, 反向驱动出价"。

这就是直播广告有别于普通广告的核心:
**它服务的是一个有时限的、活着的、正在变化的"商品+人+场"。**

### 1.2 直播广告流量矩阵

直播间的流量来源不是单一的。付费流量与自然流量相互配合,
不同来源的流量质量和成本差异巨大。

```
               直播间流量来源矩阵 (Traffic Source Matrix)

 ┌─────────────────────────────────────────────────────────────────┐
 │                        自然流量 (Organic)                        │
 │                                                                 │
 │  • 关注 Tab / 关注流 (Following Feed)                            │
 │  • 推荐流人工推荐 (For You Page 自然浮现)                        │
 │  • 直播 Tab / LIVE 专题页                                         │
 │  • 搜索流 (Search: 搜品类词/达人名)                              │
 │  • 达人主页进入 (Profile Entry)                                  │
 │  • 转评赞带来的二次分发 (Post 与 Comment 回流)                    │
 │                                                                 │
 ├─────────────────────────────────────────────────────────────────┤
 │                        付费流量 (Paid)                           │
 │                                                                 │
 │  • LIVE 直播间直投 (Live Ads)                                    │
 │  • 短视频挂直播 (In-Feed + LIVE Link / Spark Ads + LIVE)         │
 │  • TopView / Branded 开屏直播预告                                │
 │  • 搜索广告挂直播 (Search Ads + LIVE)                            │
 │  • Marketplace 商城直播位 (Placement Marketplace)                │
 │  • Smart+ 智能直播投放                                          │
 │                                                                 │
 └─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
                    ┌─────────────────────────┐
                    │  直播间总场观 (Total)     │
                    │  来源占比分析 YOY         │
                    └─────────────────────────┘
```

付费与自然的核心关系是"撬动杠杆"。
投流不只是买流量, 更是在给自然推荐流"喂信号"。

当付费人群在直播间产生停留、互动、下单,
算法会认为这个直播间"值得推荐",
进而用自然流量免费给你更多相似人群。

这就是大家常说的"付费撬自然"——
用一个好公式表达:

```
总场观 = 付费场观 + 自然场观
自然场观 ≈ f(付费人群互动率, 停留时长, 转化率, 复播率)

当 付费人群互动率/停留 > 阈值 时:
    自然场观份额 ↑, 总 CPM 摊薄 ↓
```

所以直播投流不等于"无脑花钱"。
它是一场"给算法喂样本"的游戏:
**付费买来的人, 是为了教会算法"什么样的用户会买我的东西"。**

投得准 + 接得住(直播间能留人), 才有复利。
投不准 + 接不住, 就是纯成本。

### 1.3 商品橱窗 / 购物展示机制

商品橱窗(在 TikTok 上体现为商品展示柜 / Product Showcase / 购物车)
是直播间"边看边买"的交易载体。它有几个关键概念:

```
               商品橱窗机制 (Shopping Mechanism)

 ┌───────────────────────────────────────────────────────────────┐
 │  ① 商品上架 (Product Listing)                                  │
 │     • 商家把 SKU 挂到 TikTok Shop 后台                         │
 │     • 设置标题/主图/详情/价格/库存/物流模板                     │
 │     • 审核通过后进入商品池                                     │
 │                                                               │
 │  ② 橱窗挂载 (Display)                                        │
 │     • 达人/品牌把商品加入自己的"橱窗/展示柜"                   │
 │     • 直播过程中商品卡片会轮播/置顶显示                        │
 │     • 可以设置"主推款"ON TOP + "搭配款"联推                    │
 │                                                               │
 │  ③ 直播间商品卡片 (Live Product Card)                         │
 │     • 用户点击卡片 → 商品详情浮层 → 加购/立即购买              │
 │     • 支持优惠券、限时价、尺码选择                             │
 │     • 用户"边看主播讲解边点进商品"                             │
 │                                                               │
 │  ④ 成交 (Checkout)                                           │
 │     • 站内支付 (TikTok Shop 内完成)                           │
 │     • 或跳转三方(独立站/小程序, 看区域与方案)                  │
 └───────────────────────────────────────────────────────────────┘
```

橱窗商品与"正在讲哪个品"要一一对应。
专业直播间会把直播脚本和橱窗商品顺序做成映射表,
主播讲 A 品时就把 A 品置顶。

商品卡片是实时的转化入口。
它的数据(点击、加购、下单)会以事件形式回流到转化追踪体系,
成为广告模型判断"哪类用户值得买"的重要输入。

几个橱窗运营要点:

| 运营项 | 实战建议 | 量化参考 |
|--------|---------|---------|
| 主推款 | 每场锁定 1-3 个爆款, 置顶展示 | 贡献 GMV 60%+ |
| 橱窗商品数 | 不要过多, 15-30 个为宜 | 过多稀释点击 |
| 价格阶梯 | 引流款 + 利润款 + 超高客单款 | 客单价梯队 1:3:5 |
| 优惠券 | 直播间专属券, 限时限量 | 提加购率 20-40% |
| 库存预警 | 报备充足库存, 防超卖 | 退款率 < 3% |

橱窗不是"把商品堆上去"就完事。
它是一场围绕"点击→加购→下单"的实时运营。

### 1.4 联盟带货与分佣体系

联盟带货(Affiliate / 带货分佣)是直播电商扩张货盘的核心杠杆。
品牌不只是自己播, 更要借助大量达人(尤其腰尾部 KOC)分销。

```
            联盟带货分佣体系 (Affiliate Commission)

 ┌───────────────────────────────────────────────────────────┐
 │                      角色与利益                            │
 │                                                           │
 │  商家 (Merchant)                                          │
 │   ├─ 发布商品 + 设定佣金率 (Commission Rate)               │
 │   └─ 提供样品/优惠/素材, 审核达人                         │
 │                                                           │
 │  达人 (Creator / 带货方)                                  │
 │   ├─ 选品加入橱窗, 挂商品链接                             │
 │   └─ 直播/短视频讲解, 成交后拿佣金                        │
 │                                                           │
 │  TikTok (平台撮合)                                        │
 │   ├─ 佣金结算、订单归因、售后仲裁                          │
 │   └─ 优选联盟/达人广场撮合                                │
 │                                                           │
 │  结算公式:                                                 │
 │  达人佣金 = 订单实付金额 × 佣金率                          │
 │  常见佣金率: 10% - 30% (美妆/服饰偏高, 标品偏低)           │
 └───────────────────────────────────────────────────────────┘
```

联盟业务里广告投放的场景很特殊:
**投流方往往是达人自己或 MCN, 而不是品牌。**
达人用自己的广告账户给直播间投流, 成交后拿佣金,
类似"自己给自己打付费投手"。

这套逻辑下, 分佣不仅仅是渠道成本, 更是**投流决策的激励对齐**:
谁投流, 谁承担广告费, 谁享受 GMV 分成,
就会倒逼投得准、控成本。

两类常见联盟投放模式:

| 模式 | 投放主体 | 广告账户 | ROAS 目标 |
|------|---------|---------|----------|
| 品牌自营投流 | 品牌方 | 品牌广告账户 | 1.8 - 3.0x |
| 达人/联盟投流 | 达人/MCN | 达人授权账户 | 按佣金反推 ≥ 1/(佣金率) |

达人自己的反推 ROAS 很容易算:
若佣金率 20%, 那 ROAS 至少要 > 5x 才不亏(因为达人只拿 20% 的 GMV)。
这就是为什么达人投商业直播比品牌更激进地追求"高 GMV 低广告费"。

### 1.5 核心角色与职责边界

直播带货是"多角色协作"的实时生意。
广告投手只是其中一环, 但必须清楚每个角色的 KPI 边界:

```
 角色          │  核心 KPI                    │  与广告的关系
───────────────┼──────────────────────────────┼──────────────────────────
 主播 Shop     │ 停留、互动率、讲解转化        │ 承接付费流量, 决定 CVR
 运营 Operation│ 场观、节奏、商品编排           │ 决定是否需要加投/减投
 投手 Ad Ops   │ CPA / ROAS / eCPM / 消耗       │ 投放与实时调优主责
 选品 Buyer    │ 商品点击率、退款率              │ 决定商品承接力
 客服 CS       │ 咨询响应、售后                │ 影响复购与口碑
 供应链 SC     │ 库存、履约时效                │ 影响超卖与退款
```

一个常见的协作错误是:
投手背了"全场的 ROAS"指标, 但主播不行、选品不行、价格不行,
投手再努力也是白搭。

正确的做法是**分工归因**:
- 投手只对"付费流量的 CPA / 付费 ROAS"负责
- 主播对"承接率 / 互动率"负责
- 选品对"商品点击率 / 客单价 / 转化率"负责

这样每一项都能找到优化责任人, 复盘才不是一团浆糊。

### 1.6 直播广告产品地图与客观约束

TikTok 直播广告天然依托 TikTok Shop 与 LIVE 生态。
核心广告产品与它们的目标(objective)映射如下:

```
                   直播广告产品地图 (Live-Ad Product Map)

 ┌──────────────────────────────────────────────────────────────────────┐
 │  广告产品               │  广告目标 objective │  优化目标 optimization │
 ├─────────────────────────┼────────────────────┼───────────────────────┤
 │  直播推广 LIVE_2_SHOP   │  PRODUCT_SALES      │  COMPLETE_PAYMENT     │
 │  (促进入直播间成交)      │                     │  (下单支付)           │
 ├─────────────────────────┼────────────────────┼───────────────────────┤
 │  直播推广(场观/互动型)   │  ENGINEERING/       │  VIEW_CONTENT /       │
 │  LIVE 直投              │  LIVE 目标          │  ENGAGEMENT           │
 ├─────────────────────────┼────────────────────┼───────────────────────┤
 │  短视频挂直播间          │  SALES /            │  COMPLETE_PAYMENT /   │
 │  (Post + LIVE Link)     │  PRODUCT_SALES      │  VIEW_CONTENT         │
 ├─────────────────────────┼────────────────────┼───────────────────────┤
 │  Spark Ads + LIVE       │  SALES /            │  COMPLETE_PAYMENT     │
 │  (达人原生切片+直播)     │  TRAFFIC            │                       │
 ├─────────────────────────┼────────────────────┼───────────────────────┤
 │  购物车广告             │  PRODUCT_SALES      │  COMPLETE_PAYMENT     │
 │  (Shoppable / 商城位)    │                     │                       │
 └─────────────────────────┴────────────────────┴───────────────────────┘
```

重要提示:
**不同的 objective 对应不同的优化目标(optimization_goal)**,
而优化目标是广告模型"往哪个方向使劲"的直接指令。

直播带货最核心的是 PRODUCT_SALES / SALES,
配合优化目标 COMPLETE_PAYMENT(支付完成)。
因为直播生意的成败最终落在 GMV, 而不是点击或观看。

但冷启动阶段, 全场直接跑 COMPLETE_PAYMENT 可能因为信号太少而不起量。
这时需要"阶梯式"，先跑沉浸/互动, 积累了转化样本后再切支付目标。

这部分在第二章会展开讲原理, 第三章会给代码与实战节奏。

### 1.7 直播广告全链路架构图(汇总)

把广告层与实时转化串联起来, 整条链路是这样:

```
  直播广告实时闭环架构 (Live-Ad Real-time Closed Loop)

              ┌──────────────────────────────────────┐
              │      TikTok Marketing API (v1.3)     │
              │   business-api.tiktok.com            │
              └───────┬──────────────────────┬───────┘
                      │                      │
        create_campaign│               get_report
        create_adgroup │               (实时维度)
        create_ad      │                      │
                      ▼                      ▼
        ┌──────────────────┐      ┌───────────────────┐
        │  广告投放引擎      │      │  转化数据回流       │
        │  (LIVE 出价)      │      │  (CVR/GMV 信号)    │
        └────────┬─────────┘      └─────────┬─────────┘
                 │                          │
                 ▼                          ▼
        ┌────────────────────────────────────────────┐
        │              直播间实体 (Live Room)          │
        │                                               │
        │  付费流量 ──┐                                  │
        │  自然流量 ──┼──▶ 观看 ─▶ 互动 ─▶ 点商品       │
        │  粉丝回流 ──┘              │                   │
        │                            ▼                   │
        │                     加购 ─▶ 下单 ─▶ 支付       │
        │                            │                   │
        │                    (事件经 Pixel/CAPI 上报)    │
        └────────────────────────────┬──────────────────┘
                                     ▼
        ┌────────────────────────────────────────────┐
        │     归因 + 出价模型 (Attribution & Bidding)  │
        │  • Click 后 7 天 / 观看后 1 天窗口            │
        │  • 用回流的 COMPLETE_PAYMENT 训练模型         │
        │  • 实时调整出价 eCPM / CPA                   │
        └────────────────────────────────────────────┘
```

这张图是全文档的骨架。
第三章的所有实战动作, 都是在"往左上角建广告、往右上角拉报表、
往下面喂转化"这三件事里循环。

---

## 二、深度原理解析

### 2.1 LIVE 广告目标与 objective 映射原理

理解直播广告, 先要理解 TikTok 广告账户的三个层级与 objective 的关系:

```
 Campaign(广告系列)        ← objective_type 在此层定义
   ├─ Ad Group(广告组)     ← targeting / bid_strategy / optimization_goal
   │    ├─ Ad(广告创意)    ← 素材 / 直播链接 / 商品卡片
   │    └─ Ad(广告创意)
   └─ Ad Group(广告组)
```

直播广告的 objective_type 主要集中在:
- PRODUCT_SALES(商品销售)
- SALES(销售, 通常对应本站/独立站)
- TRAFFIC(流量, 用于预热与冷启动)
- ENGAGEMENT / VIDEO_VIEWS(互动/观看, 用于造势与冷启)

每种 objective 需要配合对应的优化目标(optimization_goal):

| objective_type | 适用阶段 | optimization_goal | 说明 |
|----------------|---------|-------------------|------|
| PRODUCT_SALES  | 开播中主投 | COMPLETE_PAYMENT | 直接优化支付, 冲 GMV |
| SALES          | 开播中主投 | COMPLATE_PAYMENT / VIEW_CONTENT | 电商站内 |
| TRAFFIC        | 预热/冷启 | CLICK / VIEW_CONTENT | 攒人群与样本 |
| ENGINEERING(碰撞) | 造势 | ENGAGEMENT | 拉互动量与场观 |

一个核心原理: **广告模型只能在"有数据"的方向上优化。**
- 如果你选 COMPLETE_PAYMENT, 但直播间转化样本极少, 模型学不出来, 就出不了量。
- 所以冷启动的策略是"先跑宽目标攒样本, 样本足够后再切窄目标控成本"。

用一张表说明"样本量→可优化目标"的爬坡:

```
  样本/天        │ 建议 optimization_goal           │ 说明
────────────────┼──────────────────────────────────┼──────────────────
  < 10 支付      │ ENGAGEMENT / VIEW_CONTENT        │ 样本太少, 先攒人
  10 - 50 支付   │ VIEW_CONTENT / 开始COMPLETE_PAY  │ 有基础样本, 逐步收窄
  > 50 支付      │ COMPLETE_PAYMENT                 │ 全力冲 GMV 与 ROAS
```

### 2.2 实时转化追踪链路(Pixel + CAPI + 自定义转化)

直播带货最讲究"实时"。转化追踪的链路决定了:
- 广告模型能否及时学习
- 投手能否实时看到 CVR / GMV
- 归因是否准确

追踪链路分三块(可叠加):

```
  实时转化追踪链路 (Real-time Conversion Tracking)

  ┌──────────────────────┐      ┌──────────────────────┐
  │   TikTok Pixel       │      │  CAPI / Server Event │
  │   (浏览器端/客户端)    │      │  (服务端直传, 准且稳) │
  │                      │      │                      │
  │  浏览器 JS 上报        │      │  服务端 API 直传       │
  │  event:              │      │  event:             │
  │   PageView           │      │   ViewContent       │
  │   ViewContent        │      │   Click             │
  │   ClickProduct       │      │   InitiateCheckout  │
  │   AddToCart          │      │   CompletePayment   │
  │   CompletePayment    │      │   + user_data(SHA256)│
  └──────────┬───────────┘      └──────────┬───────────┘
             │                             │
             └──────────────┬──────────────┘
                            ▼
              ┌────────────────────────────────┐
              │ TikTok 事件中心 (Events Manager)│
              │  • 事件去重 & 匹配(SHA256 用户) │
              │  • 支持自定义转化               │
              │  • 供广告系统回流学习            │
              └────────────────────────────────┘
```

为什么必须 "Pixel + CAPI" 双通道?

| 通道 | 优势 | 劣势 |
|------|------|------|
| Pixel(客户端) | 免开发, 快 | iOS 隐私限制丢单, 广告拦截丢单 |
| CAPI(服务端) | 全量、稳定、准 | 需要开发与脏数据治理 |

美妆/高客单直播间, 支付动作往往发生在 App 内或落地站,
客户端 Pixel 常丢 iOS 数据。
所以生产环境标准做法是**双通道 + 去重**:
客户端和服务端各报一份, 由 TikTok 按用户哈希去重,
取"任何一端报到的为准", 最大化信号完整度。

自定义转化(Custom Conversion)用于把"模糊行为"变成"精准优化事件"。
比如你可以创建一个自定义转化:
"直播间加入购物车后 30 分钟内完成支付的人群",
然后把它作为独立优化事件。

对应的 API 方法:
- list_conversion_events(advertiser_id)         拉取现有转化事件
- create_custom_conversion(advertiser_id, conv)  创建自定义转化

### 2.3 归因模型与时间窗口

直播广告的归因与普通广告最大的差异是**时间窗口短、强度高**。
因为直播间是"当下冲动消费"场景, 判定哪个广告带来了这笔支付, 需要窗口。

TikTok 直播广告典型的归因窗口:
- Click(点击)后 7 天
- View(观看)后 1 天
- 不同 objective / 优化目标可能有默认窗口

```
  归因窗口示意 (Attribution Window)

  广告展现 ──┬── 观看(1天) ────────────────┐
            │                              ▼
  广告点击 ──┴── 点击(7天) ──▶ 进入直播间 ──▶ 下单 ──▶ 支付
                                         │
                                         ▼
                         归因给"最后一次有效触点"
                         按窗口内的触点优先级判定
```

关键原理: **同一笔支付, 可能被多个广告争抢归因。**
TikTok 的默认模型偏重"last-touch + 窗口限制"。
这意味着:
- 用户先点了 A 广告进入直播间, 又点了 B 广告,
  最终支付会归因到更接近支付的触点。
- 归因结果决定了"这笔 GMV 记在哪个 Campaign/AdGroup 头上"。

对投手的意义:
1. 不要只看单广告组 ROI, 要看"直播间整体归因 GMV"。
2. 投流要"托底": 让用户反复看到你, 直到下单。
3. 复盘时区分"窗口内完整归因"与"点击归因"，避免被误导。

### 2.4 竞价与出价原理(LIVE 场景)

直播广告的出价与普通广告不同, 因为它追求的是"实时场观 + 转化"双目标。
TikTok 直播广告可用出价策略(bid_strategy):

- MAXIMIZE_CONVERSIONS(最低成本/最多转化)
- MAXIMIZE_CLICKS(最多点击)
- MANUAL(手动出价 / 设置目标 bid)
- CPA(目标每次转化费用 bid)

直播商家最常用的是 **MAXIMIZE_CONVERSIONS(冲 GMV)** 与 **CPA(控成本)**。

需要理解的核心是 eCPM 定价: 广告系统按"预估点击率 × 转化价值"来排价。

```
  eCPM ≈ 1000 × CTR × CVR × 客单价价值(价值出价时)
  或
  eCPM ≈ 1000 × (期望行动价值的加权)

  模型的最终目标不是"最便宜", 而是:
  在预算约束下, 让"预估总转化价值"最大化。
```

用 Go 写一个"出价策略转化为 eCPM 预估"的示意:

```go
package livebid

import "math"

// EstimateEcpM 预估千次展示成本
// clickRate: 预估点击率(0-1), convRate: 预估转化率(0-1), aov: 客单价
// valueMode: 是否按转化价值出价
func EstimateEcpM(clickRate, convRate, aov float64, valueMode bool) float64 {
	if valueMode {
		// 价值出价: 按预估 GMV 价值排价
		expectedValuePerImp := clickRate * convRate * aov
		return expectedValuePerImp * 1000
	}
	// 无价值出价: 按成本出价(如 CPA)
	// 在 CPA 模式下, eCPM ≈ 1000 * CTR * CVR * targetCPA
	return clickRate * convRate * 0 * 1000 // 占位, 由上层注入 targetCPA
}

// BidCostPerImpression 预算角度: 出价就是"系统为你买流量的意愿"
func BidCostPerImpression(expectedValue float64, targetRoas float64) float64 {
	// 若要求 ROAS >= targetRoas, 则单次展示愿意付出的钱有上限
	return expectedValue / targetRoas
}

// Guard 防止超预算: 动态闸门
func Guard(budgetRemain, spentThisHour, desiredSpend float64) float64 {
	if budgetRemain <= 0 {
		return 0
	}
	maxSpend := math.Min(desiredSpend, budgetRemain)
	return maxSpend
}
```

直播投放的一个反常识点: **直播间越热闹, 出价越便宜。**
因为直播间人气旺、停留长、转化好,
算法给直播间的"转化预估"就高,
同样的出价能买到更多、更准的流量。

所以投流有一个"断层"现象:
- 人气好的直播间, 付费 ROI 高, 折扣买流量
- 人气差的直播间, 付费 ROI 低, 越投越亏
- 于是"强者愈强, 弱者愈弱"

这也是为什么"开播先自然养人气, 再做付费放大"是普遍打法。

### 2.5 用 Python 创建直播 Campaign(代码实战)

这里展示用 scripts/tiktok_api.py 创建一场 "PRODUCT_SALES / LIVE" 直播 campaign 的完整代码。
注意方法名严格按照 tiktok_api.py 的真实签名。

```python
# -*- coding: utf-8 -*-
"""
创建 TikTok 直播带货广告 Campaign(实战示例)

依赖: scripts/tiktok_api.py 中的 TikTokClient
方法: list_accounts / create_campaign / get_bid_strategy_options /
      get_campaign_objective_options / create_adgroup / create_ad /
      get_placement_options / list_conversion_events
"""
import json
import os

from tiktok_api import TikTokClient


def load_credentials():
    """生产环境从加密配置/环境变量读取, 不要硬编码 token"""
    # 演示: 从环境变量读取
    token = os.environ.get("TIKTOK_ACCESS_TOKEN", "")
    return {"tiktok": {"access_token": token}}


def create_live_campaign(advertiser_id: str):
    client = TikTokClient(load_credentials())

    # 0) 校验账户
    acct = client.list_accounts(advertiser_id)
    if not acct.success:
        print("账户校验失败:", acct.error)
        return None
    print("账户 OK:", acct.data)

    # 1) 确认目标选项(信息性打印)
    objs = client.get_campaign_objective_options()
    for o in objs:
        print("objective 选项:", o["code"], "-", o["name"])

    bids = client.get_bid_strategy_options()
    for b in bids:
        print("bid 策略选项:", b["code"], "-", b["name"], "-", b["description"])

    # 2) 创建 Campaign: PRODUCT_SALES, 目标支付
    campaign_payload = {
        "campaign_group_type": "PRODUCT_SALES",
        "objective_type": "PRODUCT_SALES",
        # 也可以使用 SALES 目标(对应已有 STORE_TRAFFIC 等)
        "operation_system": None,          # iOS/Android, 默认自动
        "campaign_name": "LiveMaster-美妆-0719-20H",
        "budget_mode": "BUDGET_MODE_DAY",
        "daily_budget": 2000,              # 日预算 $2000
        "attribution": {
            "attribution_type": "TT",
            # 点击 7 天 / 观看 1 天
        },
        "auto_targeting_enabled": True,    # 打开自动定向
        "smart_optimization_enabled": True # Smart+ 样式优化(如可用)
    }
    resp = client.create_campaign(advertiser_id, campaign_payload)
    if not resp.success:
        print("创建 campaign 失败:", resp.error)
        return None
    campaign_id = resp.data.get("campaign_id")
    print("创建 Campaign 成功, campaign_id =", campaign_id)
    return campaign_id


def create_live_adgroup(advertiser_id: str, campaign_id: str):
    client = TikTokClient(load_credentials())

    # 直播广告组: 用 LIVE 相关关键词与定向
    adgroup = {
        "adgroup_name": "Live-美妆-18-40-女性-东南亚",
        "campaign_id": campaign_id,
        "placement_type": "PLACEMENT_TYPE_TIKTOK",
        "operation_system": "BOTH",
        # 定向: 18-40 岁, 结合自定义受众
        "targeting": {
            "age": ["AGE_18_24", "AGE_25_34", "AGE_35_44"],
            "gender": ["FEMALE"],
            "locations": [
                {"location_type": "REGION", "id": "1213"},  # 示例: 泰国
            ],
        },
        # 优化目标: 支付完成
        "optimization_goal": "COMPLETE_PAYMENT",
        "bid_strategy": "AUTO_BID_TYPE_VALUE_MAXIMIZE_CONVERSIONS",
        # 目标 CPA(若用手动/CPA 则填 bid_amount)
        "bid_amount": 18.0,
        "campaign_sub_type": "LIVE_2_SHOP",   # 直播电商子类型
        "deep_bid_type": "BID_TYPE_VALUE_COMPLETE_PAYMENT",
        "action_delay": "ACTION_DELAY_7D",
        "schedule": {
            "start_time": XXXX,          # 开播前 30 分钟开投
            "end_time": XXXX             # 下播后 10 分钟停投
        }
    }
    resp = client.create_adgroup(advertiser_id, adgroup)
    if not resp.success:
        print("创建 adgroup 失败:", resp.error)
        return None
    adgroup_id = resp.data.get("ad_group_id")
    print("创建 AdGroup 成功, adgroup_id =", adgroup_id)
    return adgroup_id


def create_live_ad(advertiser_id: str, adgroup_id: str):
    client = TikTokClient(load_credentials())
    ad = {
        "adgroup_id": adgroup_id,
        "creatives": [
            {
                "ad_name": "Live-素材A-口播款",
                "identity_type": "CUSTOMIZED_USER",
                "creative_type": "LIVE",          # 直播素材
                "live_stream_id": "live_room_xxx", # 绑定的直播间
                "display_name": "官方美妆直播间",
                "user_name": "official_beauty_live",
                "video": {
                    "video_url": "https://cdn.brand.com/live-intro.mp4"
                },
                "landing_page_url": "https://shop.tiktok.com/xxx",
                "call_to_action": "SHOP_NOW"
            }
        ]
    }
    resp = client.create_ad(advertiser_id, ad)
    if not resp.success:
        print("创建 ad 失败:", resp.error)
        return None
    print("创建 Ad 成功:", resp.data)
    return resp.data


def main(advertiser_id: str):
    cid = create_live_campaign(advertiser_id)
    if not cid:
        return
    gid = create_live_adgroup(advertiser_id, cid)
    if not gid:
        return
    create_live_ad(advertiser_id, gid)


if __name__ == "__main__":
    main(os.environ.get("TIKTOK_ADVERTISER_ID", "0"))
```

要点说明:

| 步骤 | 方法 | 关键点 |
|------|------|--------|
| 建 Campaign | create_campaign | objective=PRODUCT_SALES, 日预算 |
| 建 AdGroup | create_adgroup | optimization_goal=COMPLETE_PAYMENT, bid=MAXIMIZE_CONVERSIONS |
| 建 Ad | create_ad | creative_type=LIVE, 绑定直播间 |

**工期排程是关键:**
- 开播前 30 分钟开投(预铺流量)
- 下播后 10 分钟停投(避免下播后还在花钱)

### 2.6 拉取实时直播报表(代码实战)

投流过程中, 投手要实时看"每分钟/每小时的 CPA / GMV / ROAS"。
用 get_report 按不同 level 拉取。

```python
# -*- coding: utf-8 -*-
"""实时拉取直播广告报表, 用于投流中决策"""
from datetime import datetime, timedelta

from tiktok_api import TikTokClient


def pull_live_report(advertiser_id: str, level: str = "CAMPAIGN"):
    client = TikTokClient({"tiktok": {"access_token": os.environ.get("TOKEN")}})
    today = datetime.utcnow().strftime("%Y-%m-%d")
    yesterday = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")

    insights = [
        "campaign_id", "campaign_name", "objective_type",
        "spend", "impressions", "clicks", "ctr", "cpc",
        "cpm", "cpa", "conversion", "conversion_rate", "cvr",
        "cost_per_conversion", "roas", "gmv",
        "video_play", "average_video_play"
    ]
    resp = client.get_report(
        advertiser_id,
        date_start=yesterday,
        date_end=today,     # 时间窗: 昨天到今天, 直播结束时拉全量
        level=level,
        insights=insights
    )
    if not resp.success:
        print("拉取报表失败:", resp.error)
        return []
    rows = resp.data.get("list", [])
    for r in rows:
        print(
            f"{r.get('campaign_name')} | spend={r.get('spend')} "
            f"gmv={r.get('gmv')} | roas={r.get('roas')} | "
            f"cpa={r.get('cpa')} | cvr={r.get('cvr')}"
        )
    return rows


def alert_on_poor_roas(rows, min_roas=1.8):
    """投流中实时告警: 某 campaign ROAS 低于门槛即提示砍量"""
    for r in rows:
        roas = float(r.get("roas") or 0)
        if 0 < roas < min_roas:
            cid = r.get("campaign_id")
            print(f"[ALERT] campaign {cid} ROAS={roas} 低于 {min_roas}, 建议缩量/暂停")
```

为什么用"昨天到今天"而不是"实时秒级"?
- 直播间的 GMV 归因需要时间窗收敛(点击窗口 7 天)
- Report API 是批量聚合, 实时性通常是 15-60 分钟的粒度
- 投流决策的精度在"分钟到小时级"就够, 没必要秒级

真正"秒级"的是直播间自身的在线人数与互动, 那些在直播数据后台看,
广告报表用 get_report 看小时级即可。

### 2.7 数据事件与 CAPI 上报(服务端)

直播间的转化事件(加购、下单、支付)最好服务端直传 CAPI,
避免 iOS 丢失。用 Python 演示服务端上报的事件结构:

```python
# -*- coding: utf-8 -*-
"""CAPI 服务端事件上报示例(直播支付事件)"""
import hashlib
import json
import time
import requests


def sha256(value: str) -> str:
    return hashlib.sha256(value.strip().lower().encode("utf-8")).hexdigest()


def build_server_event(order: dict, pixel_id: str, token: str) -> dict:
    """
    order: {
      "user_email": ...,
      "user_phone": ...,
      "order_id": ...,
      "total_value": ...,
      "currency": "USD",
      "item_count": ...,
      "product_ids": [...],
      "live_room_id": ...,
    }
    """
    # 用户数据标准化: 小写 + SHA256, 与 Pixel 端对齐便于去重
    user_data = {
        "email": [sha256(order["user_email"])] if order.get("user_email") else None,
        "phone_number": [sha256(order["user_phone"])] if order.get("user_phone") else None,
        "external_id": [sha256(order.get("user_id", ""))],
    }
    event_data = {
        "content_type": "product",
        "contents": [
            {"id": pid, "quantity": 1} for pid in order.get("product_ids", [])
        ],
        "value": order["total_value"],
        "currency": order["currency"],
        "content_category": "beauty",
    }
    return {
        "event_name": "CompletePayment",           # 支付完成
        "event_time": int(time.time()),            # 事件发生时间(秒)
        "user": {"ttclid": order.get("ttclid")},   # 广告点击 ID
        "user_data": user_data,
        "page": {"url": order.get("landing_url", "")},
        "custom_data": {
            "order_id": order["order_id"],
            "live_room_id": order.get("live_room_id", ""),
            "payment_timestamp": int(time.time()),
        },
    }


def send_capi(payload, pixel_id, access_token):
    """调用 TikTok CAPI /event 接口(此处用 requests 演示)"""
    url = "https://business-api.tiktok.com/open_api/v1.3/event/track/"
    headers = {
        "Access-Token": access_token,
        "Content-Type": "application/json",
    }
    body = {
        "pixel_code": pixel_id,
        "event": payload,
        "test_event_code": None,   # 测试时填 test code 可验证
    }
    return requests.post(url, headers=headers, json=body, timeout=10)
```

CAPI 上报的正确性直接决定归因和模型的准度。
生产级要点:

| 项 | 要求 |
|----|------|
| 字段 | event_time 必须真实, 不要批量补传旧事件 |
| 去重 | external_id + ttclid 配合, 防重复计费 |
| 加密 | 用户 PII 一律 SHA256, 不传明文 |
| 幂等 | 同一 order_id 只报一次, 防止重复 |
| 时序 | 支付事件晚于下单, 别乱序 |

### 2.8 直播间承接指标与广告指标的关系(归因视角)

直播间的"承接力"会直接放大或缩小广告效率。
把广告侧指标与直播间侧指标串起来的公式, 是投手复盘的核心工具:

```
付费 GMV = 付费观看 × 停留率 × 商品点击率 × 加购率 × 下单率 × 支付率 × 客单价

其中:
  停留率     = 停留用户数 / 进入用户数
  商品点击率 = 点商品卡片人数 / 停留用户数
  加购率     = 加购人数 / 点商品人数
  下单率     = 下单人数 / 加购人数
  支付率     = 支付人数 / 下单人数
  客单价     = GMV / 支付人数
```

投手真正能直接控制的是"付费观看"和"买到什么样的人"。
而停留率之后的所有环节, 取决于直播间话术、选品、价格、主播状态。

所以一个专业投手的复盘动作是:
**把 GMV 拆到每一环, 找出"最差的一环"再决定谁去优化。**

举例:

```
某场美妆直播, 付费流量 10,000 观看
付费 GMV 目标 = 10,000 × 0.35(停留) × 0.20(点品)
              × 0.25(加购) × 0.30(下单) × 0.85(支付) × 25(客单价)
            ≈ $1,113

若实际只有 $600, 拆下来发现"下单率"只有 0.12:
→ 问题在"转化话术/价格", 归主播与选品
若"停留率"只有 0.15:
→ 问题在"进来的流量不匹配/开场话术", 归投流定向 + 主播

由此决定: 是调定向, 还是调主播话术, 而不是一味加预算。
```

这一节是全文档的"核心思维模型"。
用公式拆解, 会让你在直播间的每一个决策都有数据依据,
而不是拍脑袋加预算。

### 2.9 直播时段与流量波峰原理

直播间的流量不是一个均匀的"平流", 而是有明显的波峰波谷。
理解波峰原理, 才知道什么时候加投、什么时候减投。

```
  直播间流量波形 (Live Traffic Waveform)

        流量
         ▲
         │            ___
         │       ____/   \____
         │  ____/            \____
         │ /                      \
         └──────────────────────────────▶ 时间
          开场    高潮期   疲惫期   收尾
          (预热)  (冲转化) (维持)  (促单)
```

流量曲线的两个驱动因素:
1. 用户作息(目标市场的在线高峰)
2. 直播间内容节奏(每 15-20 分钟一个讲解循环)

投流匹配的原则:
- 开场前 30 分钟: 用 TRAFFIC/ENGAGEMENT 预铺, 拉初始在线人数
- 高潮期(爆款讲解): 切换 PRODUCT_SALES/COMPLETE_PAYMENT 集中转化
- 疲惫期: 降预算, 保自然流量, 或切互动目标维持热度
- 收尾(最后 30 分钟): 再打一波转化, 冲单日 GMV 峰值

这个"投流节奏"会在第三章扩展成一张可操作的表。

---

## 三、生产环境实战

### 3.1 直播投放全生命周期:预热 → 开播 → 调优 → 复盘

直播投放不是"开播那一刻才开始",
而是一个跨越开播前后 48-72 小时的完整作战周期。
按阶段划分, 每个阶段的动作、预算、目标都不同。

```
  直播投放全生命周期 (Live-Ad Full Lifecycle)

  预热期               开播期              收尾/复盘期
  (开播前 24-72h)      (直播进行中)        (下播后 24h)
  ──────────────────  ─────────────────  ─────────────────
  ① 素材与直播间预热    ④ 实时投流          ⑦ 归因与数据验收
  ② 人群与受众池准备    ⑤ 分时调优          ⑧ ROI/ROAS 复盘
  ③ 预算与节奏排期      ⑥ 应急管理          ⑨ 经验沉淀与建模
```

下面逐阶段展开, 并在 3.7 给出"美妆直播间"完整案例。

### 3.2 预热期(开播前 24-72 小时)

预热的核心目标: **让算法认识你, 让潜在买家人群预埋进直播间,**
避免开播时"冷场 + 无转化样本"。

#### 3.2.1 素材与直播间预热

| 动作 | 目的 | 落地方式 |
|------|------|---------|
| 发布直播预告短视频 | 提前获客 + 攒人群 | 短视频挂"开播提醒/预约" |
| 往期高光切片投放 | 让老粉回流 | Spark Ads 投放高光切片 |
| 装修直播间 | 提升停留 | 主推款置顶、优惠信息横幅 |
| 设定预约人数目标 | 锁场 | 引导用户预约开播提醒 |

预热期可以先用 TRAFFIC / VIDEO_VIEWS 这类宽目标,
把"看过你、对你感兴趣"的人放进兴趣池。

#### 3.2.2 准备受众池与自定义/相似受众

预热期是用 create_audience 建兴趣池的好时机:

```python
# -*- coding: utf-8 -*-
"""预热期: 创建自定义受众池"""
from tiktok_api import TikTokClient

client = TikTokClient({"tiktok": {"access_token": TOKEN}})
adv_id = ADVERTISER_ID

# 1) 商品浏览人群(最近 30 天看过商品页的人)
browsers = client.create_audience(adv_id, {
    "name": "Live-商品浏览-30D",
    "audience_type": "CUSTOM",
    "rules": [
        {
            "field": "event",
            "event": "ViewContent",
            "time_range": "30d"
        }
    ],
    "retention_in_days": 30,
})

# 2) 直播间互动人群(最近 7 天进过直播间的人)
interactors = client.create_audience(adv_id, {
    "name": "Live-直播互动-7D",
    "audience_type": "CUSTOM",
    "rules": [
        {
            "field": "event",
            "event": "LiveView",
            "time_range": "7d"
        }
    ],
    "retention_in_days": 7,
})

# 预热期用这些池子做"开播提醒召回"
print("浏览池:", browsers.data, "互动池:", interactors.data)
```

#### 3.2.3 预算排期与备战

预热期不建议高强度烧钱, 关键是把"作战计划"定好:

| 项 | 建议 | 量化 |
|----|------|------|
| 预热预算 | 占整场 10-20% | 例如总 $3000 → 预热 $400 |
| 开播预算 | 占整场 60-70% | 主力投放 |
| 收尾预算 | 占整场 10-20% | 冲峰值 GMV |
| 开播前开投时间 | 开播前 30 分钟 | 提前铺场 |
| 下播停投时间 | 下播后 10 分钟 | 防浪费 |

### 3.3 开播期:实时投流的作战指挥

开播后, 投手的角色从"建广告"切换到"实时指挥"。
每一轮决策都在 15-30 分钟内完成。

#### 3.3.1 投流节奏表(可按小时执行)

```
  单场 2 小时直播的标准投流节奏 (Sample 2h Live Pacing)

  时段          动作                    目标/出价          预算比例
  ─────────────────────────────────────────────────────────────
  -30~0 分钟   预热已开投(TRAFFIC)     拉初始在线         预热预算
  0~15 分钟    开场: 互动目标          留人+拉场观        低量
  15~60 分钟   高潮: 切支付目标        冲 GMV             60%主投
  60~90 分钟   疲惫: 降预算+互动      保自然流量          降 30-50%
  90~120 分钟  收尾: 再切支付目标      冲峰值 GMV         增投 30%
  120+10 分钟  停投                     避免浪费           停
```

这个节奏不是死板规则, 而是"内容与预算匹配"的模板。
具体每个品牌根据流量波峰与主播状态微调。

#### 3.3.2 实时调优开关

投流中核心可调的参数:

```
  可调开关                    操作                   生效时效
  ──────────────────────────────────────────────
  预算加减 (daily_budget)    加/减               分钟级
  出价/策略 (bid_strategy)   切目标              分钟级
  广告组开关 (pause/resume)  暂停/恢复           即时
  素材/广告 (pause/resume)   停高 CPA 素材       即时
  定向 (targeting)           缩人群              较慢
  受众池 (audience)          换池/加排除         分钟级
```

投流中优先级最高、反应最快的是"广告组/广告的暂停与恢复"。

用代码实现"按 ROAS 自动开关广告组":

```python
# -*- coding: utf-8 -*-
"""开播期: 按实时 ROAS 自动暂停低效广告组"""
import time
from tiktok_api import TikTokClient

client = TikTokClient({"tiktok": {"access_token": TOKEN}})
adv_id = ADVERTISER_ID

MIN_ROAS = 1.8          # 低于则暂停
OBSERVE_MIN = 10         # 至少观察多少分钟
CHECK_INTERVAL = 15      # 每 15 分钟巡检一次


def monitor_and_trim(campaign_id):
    while True:
        # 拉取当前 campaign 下的广告组实时数据
        adgroups = client.list_adgroups(adv_id, campaign_id)
        for g in adgroups.data.get("list", []):
            gid = g.get("ad_group_id")
            report = client.get_report(
                adv_id, DATE_START, DATE_END,
                level="ADGROUP",
                insights=["adgroup_id", "spend", "gmv", "roas"]
            )
            for row in report.data.get("list", []):
                if str(row.get("adgroup_id")) != str(gid):
                    continue
                roas = float(row.get("roas") or 0)
                spend = float(row.get("spend") or 0)
                # spend 过小且观察时间不足, 暂不动
                if spend < OBSERVE_MIN:
                    continue
                if roas < MIN_ROAS:
                    print(f"[TRIM] 暂停 adgroup {gid}, roas={roas}")
                    client.pause_adgroup(adv_id, gid)
        time.sleep(CHECK_INTERVAL * 60)
```

真正生产环境会加"单次暂停上限 / 冷却时间 / 人工确认阀",
避免系统过度自动化把整个计划打空。

#### 3.3.3 冷启动的"阶梯目标"策略

直播间如果直接从 COMPLETE_PAYMENT 起投, 因为样本少会不起量。
标准做法是"阶梯爬坡":

```
  阶段1: 互动/观看目标(样本少时)
     ▶ 让直播间有基础人群与热度
  阶段2: VIEW_CONTENT(有观看转化样本)
     ▶ 开始向"有效观看"优化
  阶段3: COMPLETE_PAYMENT(有支付样本)
     ▶ 全力冲 GMV / ROAS
```

当某个阶段获取的转化样本数达到阈值(比如每天 > 50 支付),
就切换到更窄、更值钱的目标。

### 3.4 直播中数据看板与实时监控

投手需要一个"实时驾驶舱":
广告侧(get_report 小时级) + 直播间侧(在线/互动/GMV)。

```
  实时驾驶舱字段 (Real-time Dashboard)

  广告侧(Report API / 小时级):
    spend, impressions, clicks, ctr
    conversion, cvr, cpa
    gmv, roas
    cost_per_conversion

  直播间侧(直播后台/秒级):
    online(在线人数), new_follower(新增粉丝)
    like, comment, share(互动)
    product_clicks, add_to_cart(商品互动)
    order_count, gmv(下单与成交)

  衍生决策指标:
    付费 ROAS    = 付费归因 GMV / 付费消耗
    综合 ROAS    = (付费 GMV + 自然 GMV) / 付费消耗
    GPM          = 每千次观看成交额
    UV 价值      = 单用户价值 = GMV / 观看人次
```

"综合 ROAS"与"付费 ROAS"要分开看:

| 指标 | 定义 | 用途 |
|------|------|------|
| 付费 ROAS | 只算付费归因 GMV | 判断投流本身赚不赚 |
| 综合 ROAS | 含自然撬动 GMV | 判断整场生意值不值 |

很多成熟的直播间, 付费广告本身可能刚打平甚至略亏,
但付费带来的自然流与复购让"综合 ROAS"很好看。
投手要跟老板对齐用的是哪一个口径, 避免口径打架。

### 3.5 达人合作机制与 Spark Ads 授权

达人合作是直播带货的核心放大器。
与达人合作有两层目标:
1. 达人自有粉丝进直播间(信任杠杆)
2. 达人内容/直播切片可投流(Spark Ads)

#### 3.5.1 达人分级与评估

不是一个"粉丝多就投多", 而是按"带货承接力"分级:

| 达人层级 | 粉丝量 | 特点 | 合作方式 | 佣金 |
|---------|--------|------|---------|------|
| 头部 KOL | 100W+ | 曝光大, 但转化不一定高 | 品牌联合/首发 | 高保底+佣金 |
| 腰部 KOC | 5W-100W | 垂直度高, 转化好 | 佣金为主 | 15-30% |
| 素人 UGC | <5W | 成本低, 铺量 | 样品+低佣 | 10-20% |

广告投放的"达人杠杆":
- 头部达人的直播间, 广告投放 ROAS 未必好(粉丝杂)
- 腰部垂直达人, 转化率高, 打"达人人群复制"很划算
- 素人 UGC, 用来做素材铺量与人群沉淀

#### 3.5.2 佣金策略与激励对齐

佣金率与广告投放是联合决策:

```
  品牌视角:
    综合利润 = GMV × 毛利率 - 广告费 - 佣金 - 履约成本
    若想保净利 15%:
      广告占 GMV ≤ 20%, 佣金 ≤ 20%, 毛利率 ≥ 55%

  达人视角:
    达人净赚 = GMV × 佣金率 - 达人投流成本 - 履约
    达人盈亏 ROAS = 1 / 佣金率
    佣金 20% → 达人投流 ROAS 至少要 5x 不亏
```

所以在"分佣 + 达人自投"模式下,
达人为了不亏, 只会给"高转化潜力的直播间"投,
这反过来倒逼品牌把直播间做得能承接。

#### 3.5.3 Spark Ads 授权与投流

Spark Ads(达人原生内容广告)让品牌可以用达人的账号身份投放原生内容,
保留达人主页、点赞评论等社交元素, 信任度更高。

与直播结合时, Spark Ads + LIVE 的典型用法:
- 把达人直播切片做成 Spark Ads, 让人看切片时能一键进直播间
- 或投放达人的预告短视频, 引导预约开播

Spark Ads 使用的素材通常来自创作者, 需要授权。

```
  Spark Ads + LIVE 工作流

  ① 达人发布直播切片/预告短视频(原生)
  ② 达人在创作者后台授权给品牌账号
  ③ 品牌用 create_ad(identity=达人头像)投放 Spark Ads
  ④ 广告点击后直达直播间(挂 live link)
  ⑤ 归因: 切片观看/点击 → 直播间进入 → 支付
```

Spark Ads 的 CTA 与直播链接要把"进直播间的理由"讲清楚:
- 切片里展示"本场爆款在直播"
- CTA 用 SHOP_NOW / WATCH_LIVE
- 直播期间投放, 下播即停(避免导向已结束的直播间)

### 3.6 直播后复盘:归因、数据校验与建模

下播后的复盘决定下一场的优化方向。复盘的输入是"归因后的数据"。

#### 3.6.1 归因与数据验收

直播广告归因有时间窗(点击 7 天 / 观看 1 天),
所以**刚下播的数据还不"完整"**:
- 还有一部分用户是点击广告后, 过了几小时/几天才支付
- 所以 GMV 会在归因窗口内逐步收敛

复盘建议:
- 下播后立即看"直播间后台 GMV"(已成交)
- 24 小时后看"广告归因 GMV"(纳入窗口内归因)
- 7 天后最终验收(点击 7 天窗口收敛)

#### 3.6.2 复盘指标模板

```
  直播复盘看板 (Post-Live Review)

  流量:
    总观看 | 峰值在线 | 平均在线
    付费观看占比 | 自然观看占比
    流量来源分布(关注流/推荐流/直播页/短视频挂/广告)

  互动:
    新粉 | 评论数 | 点赞数 | 分享数
    平均停留时长 | 互动率

  转化(漏斗):
    商品点击率 | 加购率 | 下单率 | 支付率
    客单价 | GMV | 退款率

  广告:
    付费消耗 | 付费归因 GMV | 付费 ROAS
    各 AdGroup ROAS | 各素材 CVR | eCPM | CPA

  结论三问:
    ① 哪一环节最差?(停留/点品/加购/下单/支付)
    ② 哪个人群/素材最值得放大?
    ③ 整场净利是正是负? 下一场主攻哪里?
```

#### 3.6.3 经验沉淀为受众与模型

复盘的产出不只是表格, 更要沉淀为"下一场的弹药":

```
  复盘 → 沉淀:
    高 ROAS 人群     → 保存为受众池, 下场直接复用
    高 CVR 素材      → 延长投放/复制变体
    爆款商品         → 下一场主推款
    最佳时段         → 排期优化
    高 ROI 达人      → 复投/加码
    差表现素材       → 直接下线, 不再复用
```

这一套"复盘→沉淀→复用"的循环, 让每场直播都在为下一场降本增效。

### 3.7 实战案例:美妆直播间全流程投流

用一场真实的模拟案例, 把上面的方法串起来。
背景: 某国产美妆品牌, TikTok 东南亚市场, 主打口红与底妆。

#### 3.7.1 基础设定

| 项 | 数值 |
|----|------|
| 目标市场 | 泰国(示例) |
| 目标人群 | 女性 18-40 |
| 场次 | 晚 20:00-22:00(当地时间) |
| 总广告预算 | $3,000 |
| 客单价 | $25 |
| 目标综合 ROAS | 3.0x |
| 佣金(达人分销) | 20% |
| 毛利率 | 60% |

#### 3.7.2 预热期动作(开播前 48h)

- D-3: 发布 3 条直播预告短视频, 挂"开播提醒"
- D-2: 用 create_audience 建"商品浏览 30D""直播互动 7D"两个池
- D-1: 用 TRAFFIC 目标投放预告短视频, 攒兴趣人群
- D-Day 开播前 30 分钟: 开启直播间预热投流

预热预算: $400(TRAFFIC), 目标是把开播前的"预约/感兴趣"人群养起来。

#### 3.7.3 开播期投流(20:00-22:00)

按 3.3.1 节奏执行:

```
  20:00  开播, 预热流量已在, 在线人数 800
  20:15  切 COMPLETE_PAYMENT 目标, 主推款口红讲解, 预算 $600/h
  20:45  直播间在线 2500, 商品点击率 4%, 加购率 6%
  21:00  疲惫期, 降预算到 $400/h, 互动目标维持
  21:20  报爆款福利, 切换支付目标增投 $900/h
  21:45  在线峰值 4000, GMV 快速爬升
  22:00  收尾促单, 开始停投, 22:10 全部停
```

全程用 get_report 每 15 分钟巡检:
- 某 AdGroup ROAS 掉到 1.5, 暂停
- 某素材 CVR 低, 暂停, 换高 CVR 素材

#### 3.7.4 开播当日实时数据快照

```
  指标              值
  ─────────────────────────────
  总观看          45,000
  峰值在线         4,000
  付费观看        18,000 (40%)
  平均停留         3.5 分钟
  商品点击率       3.8%
  加购率           5.5%
  下单率           28%
  支付率           85%
  客单价           $25
  成交单数         1,150
  直播间 GMV       $28,750
  付费消耗         $3,000
  付费归因 GMV     $22,000
  自然撬动 GMV     $6,750
  付费 ROAS        7.3x
  综合 ROAS        9.6x
  CPA               $2.6
  eCPM             $8.5
```

这份数据看起来很好, 原因是"直播间能承接 + 客单价适中 + 损失控制好"。

#### 3.7.5 复盘与沉淀

- 下单率 28%、支付率 85%, 很健康, 问题不大
- 商品点击率 3.8% 略低, 下专场优化商品卡片首图与讲解顺序
- 高 ROAS 人群池保存, 下场直接复用
- 20:45-21:00 阶段 ROAS 最高, 下一场把主力预算放到这个时段
- 佣金 20% + 广告 10%(3000/28750), 净利可算:

```
  净利估算 = GMV × 毛利率 - 广告 - 佣金 - 履约
          = 28750 × 0.60 - 3000 - 28750×0.20 - 履约
          = 17250 - 3000 - 5750 - 履约
          ≈ 8500 - 履约(假设 1000)
          ≈ $7,500 净利
  非常健康的直播场次。
```

如果出现负净利, 就要从"佣金比例 / 广告占比 / 毛利率"三项里找。

### 3.8 多行业直播投放要点

除了美妆, 各行业的直播广告打法有别。
这里给出五个场景(游戏/电商/APP增长/代理商/品牌直播带货)的要领。

#### 3.8.1 电商(独立站/本土电商)

| 维度 | 要点 |
|------|------|
| 目标 | PRODUCT_SALES / SALES |
| 优化目标 | COMPLETE_PAYMENT |
| 出价 | MAXIMIZE_CONVERSIONS 或 CPA |
| 关键 | 商品卡片承接 + 价格力 + 物流时效 |
| 埋点 | Pixel + CAPI 双通道, 支付事件必报 |

#### 3.8.2 游戏(直播展示玩法/转化下载)

游戏直播广告不是"带货"而是"带玩与带下":

| 维度 | 要点 |
|------|------|
| 目标 | APP_PROMOTION / VIDEO_VIEWS |
| 优化目标 | APP_INSTALL(安装) |
| 出价 | CPA(按安装) |
| 关键 | 直播展示真实玩法, CTA 引导下载 |
| 衡量 | 安装成本 / 次留 / 付费率 |

游戏的"直播"更多是"主播试玩 + 引导下载",
直播间是转化入口而非交易闭环, 归因到 APP_INSTALL。

#### 3.8.3 APP 增长(买量场景)

直播广告在 APP 增长里常用作"内容化买量":
- 用达人直播切片做 Spark Ads, 分散到各大广告位
- 优化事件从安装到注册、到付费逐层爬坡
- eCPM 与次日留存并重, 避免"买来不玩"

| 优化目标 | 适用阶段 |
|---------|---------|
| APP_INSTALL | 放量 |
| REGISTRATION | 转化提质 |
| VIEW_CONTENT(付费相关) | ROAS 优化 |

#### 3.8.4 代理商(代运营多直播间)

代理商同时管理多个品牌/直播间, 核心是"规模化 + 标准化":

```
  多直播间投放的标准化:
  ① 统一受众池与素材库(复用)
  ② 统一复盘模板(横向对比)
  ③ 统一的 ROAS 告警与自动调优规则
  ④ 分账户预算隔离, 防串量
```

代理商要能横向对比"哪个直播间的承接力强",
把预算更多配置到高 ROAS 的直播间, 提升整体组合回报。

#### 3.8.5 品牌直播带货(自营)

品牌自营直播间追求"品牌调性 + 稳定产销":
- 不追求单场爆量, 而是"稳定复播"
- 用会员/私域沉淀老粉, 直播间做粉丝运营
- 投流更看重"长效 LTV"而非单场 ROAS

| 维度 | 品牌自营直播 |
|------|------------|
| 主要目标 | 成交 + 品牌 + 复购 |
| 看板指标 | ROAS + 复购率 + 新客占比 |
| 投放策略 | 常态化预算, 配合大促波峰 |
| 人群 | 老粉召回 + 相似人群放量 |

### 3.9 生产环境工程化最佳实践

最后把工程侧的最佳实践收拢, 方便落地到代码:

```
  工程化清单 (Engineering Checklist)

  □ 凭证: token 从 KMS/Env 读取, 不硬编码
  □ 限流: 请求加指数退避重试, 规避 rate limit
  □ 幂等: 建广告带 client 幂等键, 防重复
  □ 实时: get_report 定时任务, 投流中每 15min 拉一次
  □ 告警: ROAS/CPA 触发阈值 → 通知 + 自动暂停
  □ 归因: 订单带 ttclid, CAPI 双通道去重
  □ 校验: 口径统一(付费 vs 综合 ROAS)
  □ 复盘: 数据落库, 沉淀人群与素材库
```

生产环境的"自动化"要带闸门:
- 自动暂停可, 自动加投须人工确认(防止预算爆表)
- 自动切换目标要设冷却时间
- 每次自动动作都留审计日志

---

## 四、常见问题与排查

直播广告的坑比普通广告多, 因为"实时"放大了每个决策的代价。
下面是 14 个高频问题, 每个都给"现象 → 排查 → 解法"。

### Q1: 直播间广告开投了, 但就是不出量(花钱慢/花不出去)

- 现象: 广告在线很久, spend 几乎不动, 或者出价很高仍没曝光。
- 排查顺序:
  1. 直播间是否处于"可投"状态(开播了吗? 直播间 id 有效吗?)
  2. objective / optimization_goal 是否匹配(COMPLETE_PAYMENT 样本太少会卡量)
  3. 预算是否过低(日预算 < 最低起投)
  4. 定向是否过窄(年龄/性别/地域/受众池太窄)
  5. 素材 / creative 是否 Live 绑定成功
- 解法:
  - 冷启动先放宽目标(互动/观看), 攒样本
  - 放大定向(开自动定向 auto_targeting)
  - 提高预算或在高峰时段投放
  - 确认直播间状态与广告绑定

### Q2: 付费 ROAS 很低(烧钱不出 GMV)

- 现象: 流量进来了, 但成交少, 付费 ROAS 低于门槛。
- 排查:
  1. 先看"直播间转化漏斗", 是哪一环最差?
  2. 是不是流量不精准(定向太宽 / 买错人群)?
  3. 是不是直播间承接差(主播不讲解、商品没置顶)?
  4. 是不是价格/佣金/优惠没有竞争力?
- 解法:
  - 漏斗最差在"停留/点品" → 调定向 + 调整主播话术
  - 漏斗最差在"下单/支付" → 优化价格/优惠/信任话术
  - 引入相似人群(把高复购人群做 lookalike)
  - 不要盲目加预算, 先找"最差一环"再决定优化谁

### Q3: 直播间人气旺, 但转化(商品点击/下单)特别低

- 现象: 在线人数高、互动热闹, 但商品点击率 / 下单率都低。
- 排查:
  1. 商品卡片是否没置顶主推款?
  2. 价格是否有吸引力? 有没有直播间专享价?
  3. 主播是否明确引导"点击下方购物袋"?
  4. 商品详情页 / 首图是否清晰?
- 解法:
  - 主推款置顶, 讲解时实验室口播引导
  - 上直播专享优惠券/限时价, 提升加购
  - 优化商品卡片首图与卖点
  - 若"人气旺但转化低", 先解决承接, 再往外放量

### Q4: 广告花了钱, 但"下播后还有点击/消费"导致浪费

- 现象: 下播了直播间关了, 广告还在跑, 点击导向无效直播间。
- 排查: 是否按计划在下播后及时 pause?
- 解法:
  - 用 schedule 设定 end_time(下播 + 10 分钟自动停)
  - 投流中用定时任务在下播时刻 pause_adgroup / pause_ad
  - 建立"下播停投"的 SOP 与提醒

```python
# -*- coding: utf-8 -*-
"""按计划停投: 下播后暂停所有相关广告组"""
from datetime import datetime
from tiktok_api import TikTokClient

client = TikTokClient({"tiktok": {"access_token": TOKEN}})
adv_id = ADVERTISER_ID
campaign_id = LIVE_CAMPAIGN_ID

def stop_all_at(live_end_hour, live_end_minute):
    now = datetime.now()
    if (now.hour, now.minute) >= (live_end_hour, live_end_minute + 10):
        ads = client.list_adgroups(adv_id, campaign_id)
        for g in ads.data.get("list", []):
            client.pause_adgroup(adv_id, g["ad_group_id"])
        print(f"[STOP] {now} 已暂停全部广告组")
```

### Q5: iOS 端转化丢失, 支付数据对不上账

- 现象: 直播间后台 GMV 高, 但广告归因 GMV 明显偏低, 尤其 iOS 用户。
- 排查:
  1. 是否只用了客户端 Pixel? iOS 隐私限制会丢。
  2. 是否做了 CAPI 服务端上报?
  3. 用户身份(邮件/手机哈希)是否匹配?
- 解法:
  - 双通道 Pixel + CAPI, 用 SHA256 哈希对账去重
  - 服务端完整上报, 保证 iOS 事件不全丢
  - 用 ttclid / external_id 辅助归因
- 这也是为什么生产环境强烈建议"服务端 CAPI"。

### Q6: 同一笔支付被多个广告争抢归因, GMV 重复/归属不清

- 现象: 各 Campaign/AdGroup 的 GMV 之和 > 直播间总 GMV。
- 排查:
  1. 是否投了多个入口(有的按点击归因, 有的按观看)
  2. 是否存在重复上报同一 order_id
- 解法:
  - 明确"直播间总 GMV"与"广告归因 GMV"是两个口径
  - 广告侧以 TikTok 归因为准, 与直播间总 GMV 分开呈现
  - 服务端按 order_id 幂等, 防重复计费
  - 复盘以"综合 ROAS"(付费+自然)为准, 避免单广告组口径打架

### Q7: 某 AdGroup 起量后又突然掉量(CVR 波动大)

- 现象: 前 1 小时转化不错, 后面突然不出量 / 成本飙升。
- 排查:
  1. 是否触碰了定向/预算瓶颈?
  2. 直播间转化窗口波动(主播状态、时段)
  3. 广告组是否进入了"重新学习期"
- 解法:
  - 避免频繁改动单广告组(改动会重置学习)
  - 用"加新计划"代替"反复改旧计划"
  - 高峰期(波峰)加大预算, 低谷期保自然与互动
  - 关注直播间的时段协同, 而非只看单广告组瞬时波动

### Q8: 冷启动 COMPLETE_PAYMENT 完全不起量

- 现象: 一上来直接跑支付目标, 一直没量。
- 排查: 支付样本太少, 模型训练不出来。
- 解法:
  - 用"阶梯目标": 互动/观看 → VIEW_CONTENT → COMPLETE_PAYMENT
  - 先用素材/达人切片积累转化样本
  - 样本 ≥ 50 支付/天 再切支付目标
  - 开启自动定向 + 放宽预算

### Q9: 直播中途想换主推款, 但广告还按旧商品优化

- 现象: 换品了, 但广告仍在优化旧商品的转化。
- 排查: optimization_goal / 商品卡片是否同步更新?
- 解法:
  - 换主推款时, 同步更新商品卡片与广告素材
  - 若目标没变(仍是 COMPLETE_PAYMENT), 只需换素材与置顶款
  - 避免"广告还在讲旧品、直播间已换新品"导致的承接断裂

### Q10: 达人切片投放(Spark Ads)点击进直播, 但停留很短

- 现象: 点了进直播的人多, 但 CVR 低, 停留极短。
- 排查:
  1. 切片讲的内容与当前直播内容是否一致?
  2. 进直播后商品是否就位? 主播是否接住?
  3. 切片里的优惠/福利是否真在直播间兑现?
- 解法:
  - 切片与直播内容强对齐, 不"货不对板"
  - 切片 CTA 讲清"进直播间看什么/拿什么福利"
  - 进直播后的承接(口播、置顶)与切片承诺一致
  - 这是"承接一致性"问题, 不是单纯广告问题

### Q11: 达人分佣模式下, 达人不愿投流(怕亏)

- 现象: 想借助达人自投, 但达人觉得佣金低、风险大。
- 排查/解法:
  - 佣金率是否达到达人盈亏线(反推 ROAS ≥ 1/佣金率)
  - 给达人提供"直播间高承接"的保障(价格/优惠)
  - 品牌可提供"达人多投返佣 / 保底激励", 降低达人风险
  - 用"达人人群复制"而非全靠达人自投

### Q12: 多个广告位同时投, 直播间自然流反而下降

- 现象: 付费量大了, 但自然场观反而掉了。
- 排查:
  1. 是否"付费买来了低质量人群(只看不买)"污染了直播间数据?
  2. 直播间承接是否被稀释(承接不住涌入的人)?
- 解法:
  - 用排除/定向避免无价值人群(例如排除已购用户不重复打扰)
  - 优先保"承接力"再放量, 而不是盲目加大预算
  - 观察"付费人群互动率/停留", 若低于阈值就缩量或缩人群
  - 让直播间保持高信号(停留/互动/转化), 保护自然推荐

### Q13: 复盘 GMV 数据与直播间后台对不上

- 现象: 广告归因 GMV 与直播间后台成交额差异大。
- 排查:
  1. 归因窗口未收敛(点击 7 天 / 观看 1 天)
  2. 口径不同(直播间后台 vs 广告归因)
  3. 部分订单走独立站/三方核销, 未进广告归因
- 解法:
  - 给归因设定"看板时间": 下播/24h/7天三个节点
  - 区分"直播间总 GMV / 付费归因 GMV / 综合 GMV"
  - 三方订单用 CAPI 回传确保归因可追踪

### Q14: 多直播间/多账户投放, 预算串了/报表分不清

- 现象: 同时管几个直播间, 不知道哪个计划属于哪场直播。
- 排查: 命名与标签不统一。
- 解法:
  - 命名规范: `Live-{品}-{日期}-{时段}`
  - 在 campaign_name 中带"直播间/场次"标识
  - 用统一的受众池、素材库、复盘模板, 横向对比承接力
  - 分账户预算隔离, 防止窜量

### 排查方法论小结

直播广告问题十有八九不在广告本身, 而在"广告与直播间的协同"。
给一个通用的排查优先级:

```
  排查优先级 (Troubleshooting Priority)
  1 ► 直播间状态与绑定(在播? id 对?)  —— 最基础
  2 ► 转化漏斗最差一环(承接问题)     —— 决定要不要投
  3 ► 目标/出价匹配(样本够吗)        —— 决定起不起量
  4 ► 定向与人群(流量准不准)         —— 决定成本
  5 ► 归因与对账(口径对不对)         —— 决定复盘准不准
```

先查"承接", 再查"流量", 最后查"归因",
避免一上来就抓预算和出价。

---

## 五、自测题

下面的题目用于检验对直播广告核心原理与实战的理解。
每题附完整答案, 建议先自己作答再看。

### 自测题 1: 直播广告与普通 In-Feed 广告的本质区别是什么?

<details>
<summary>答案</summary>

直播广告服务的是一个"有时限、活着、正在变化"的直播间,
与普通品牌展示广告有三点本质不同:

1. **时间实时性**:
   广告点击直达"正在进行的直播间", 下播即失效。
   它要配合直播场的开播/下播时刻来排程，而不是长期投放。

2. **转化实时性**:
   直播间"边看边买", 支付事件实时回流(进店/点击/加购/下单/支付)。
   广告模型能实时学习哪类人值得买, 出价实时调整。

3. **调优实时性**:
   投手在直播过程中可以秒级/分钟级暂停、恢复、加预算。
   它是一场"实时作战", 而非"设置好就跑"。

另外直播广告是"三层闭环": 内容层(直播建立信任) + 交易层(完成转化)
+ 广告层(实时放大流量), 三层实时联动。
这是普通 In-Feed 广告不具备的。
</details>

### 自测题 2: 为什么冷启动时直接跑 COMPLETE_PAYMENT 可能不出量? 该怎么处理?

<details>
<summary>答案</summary>

原因: 广告系统只能在"有足够样本"的方向上优化。
直播刚开始时, 支付样本极少(可能每天 < 10 笔),
模型无法从"支付信号"里学好流量人群,
于是系统为了控制风险会限制放量, 导致不出量或成本极高。

正确处理是"阶梯式爬坡目标":

```
  阶段1: 互动/观看目标      —— 拉基础人群与热度
  阶段2: VIEW_CONTENT       —— 有有效观看样本后优化观看转化
  阶段3: COMPLETE_PAYMENT   —— 支付样本 ≥ 50/天 后全力冲 GMV
```

当某个阶段的转化样本达标, 再切换到更窄、更值钱的目标。
同时可开启自动定向(auto_targeting)、放宽预算、叠加达人切片,
加速积累样本。
</details>

### 自测题 3: 付费 ROAS 与综合 ROAS 有什么区别? 为什么必须分开看?

<details>
<summary>答案</summary>

- **付费 ROAS = 付费归因 GMV / 付费广告消耗**
  它只反映"广告本身赚不赚", 是判断投放效率的直接指标。

- **综合 ROAS = (付费 GMV + 自然撬动 GMV) / 付费广告消耗**
  它把"付费带来的自然流与复购"也计入, 反映整场生意的真实价值。

为什么必须分开看:
1. 一个好承接、高互动的直播间, 付费广告往往会"撬动自然流量",
   付费本身可能刚打平(付费 ROAS ≈ 1-2x),
   但综合 ROAS 能达到 3-5x, 整场是赚钱的。
2. 如果只用综合 ROAS 决策, 可能掩盖"广告其实在烧钱、靠自然在补"的事实;
   如果只用付费 ROAS 决策, 可能误杀本可以"撬自然"的好直播间。
3. 所以要对齐口径: 投手对"付费 ROAS"负责,
   老板看"综合 ROAS(整场)净利"。两个口径缺一不可。

用公式拆解 GMV 到各环节(停留→点品→加购→下单→支付→客单价),
能进一步定位是"流量"问题还是"承接"问题。
</details>

### 自测题 4: 用 tiktok_api.py 的方法, 简述创建一场直播带货广告要按什么顺序调用哪些方法?

<details>
<summary>答案</summary>

按"账户检查 → 建 Campaign → 建 AdGroup → 建 Ad → 绑定直播间 → 实时报表 → 复盘"顺序:

1. **账户检查**:
   `client.list_accounts(advertiser_id)` 确认账户与 token 有效。

2. **确认目标/出价选项**(信息性):
   `client.get_campaign_objective_options()` 与
   `client.get_bid_strategy_options()` 打印可选值。

3. **创建广告系列 Campaign**:
   `client.create_campaign(advertiser_id, campaign)`，
   关键字段:
   - `objective_type = "PRODUCT_SALES"`
   - `daily_budget`(日预算)
   - `budget_mode=DAY`
   - `attribution`(点击 7 天 / 观看 1 天)

4. **创建广告组 AdGroup**:
   `client.create_adgroup(advertiser_id, adgroup)`，
   关键字段:
   - `campaign_id`(挂在上面建好的 campaign 下)
   - `optimization_goal = "COMPLETE_PAYMENT"`
   - `bid_strategy = MAXIMIZE_CONVERSIONS` 或 CPA
   - `campaign_sub_type = "LIVE_2_SHOP"`
   - `schedule`(开播前 30 分钟 ~ 下播后 10 分钟)

5. **创建广告创意 Ad**:
   `client.create_ad(advertiser_id, ad)`，
   关键字段:
   - `adgroup_id`
   - `creative_type = "LIVE"` 且绑定 `live_stream_id`
   - 素材、CTA(video/landing_page/call_to_action)

6. **实时报表与调优**:
   `client.get_report(advertiser_id, date_start, date_end, level, insights)`
   按 CAMPAIGN/ADGROUP 维度拉 spend/gmv/roas/cpa/cvr。
   必要时 `client.pause_adgroup(...)` / `resume_adgroup(...)` 实时调优。

7. **转化事件**:
   用 `client.list_conversion_events` / `create_custom_conversion`
   确认或创建自定义转化作为优化事件。

顺序本质是:**先账户, 再 Campaign(定目标/预算), 再 AdGroup(定人群/出价),
再 Ad(定素材/直播间绑定)**, 逐层向下, 与层级结构一致。
</details>

### 自测题 5: 一场直播间付费 GMV 不达预期, 你要如何系统性地诊断并决定优化动作?

<details>
<summary>答案</summary>

系统性诊断分四步, 遵循"先承接、再流量、再归因"的优先级:

**第一步: 拆转化漏斗找最差一环**
```
付费 GMV = 付费观看 × 停留率 × 商品点击率 × 加购率 × 下单率 × 支付率 × 客单价
```
逐项拉数据, 找出"明显低于健康值"的一环:
- 停留率低     → 定向不匹配 / 开场话术差
- 商品点击率低 → 商品卡片未置顶 / 主播未引导 / 首图差
- 加购率低     → 价格/优惠没吸引力
- 下单率高、支付率低 → 信任 / 支付流程 / 到付问题

**第二步: 判断是"流量"还是"承接"**
- 若最差在"停留/点品"之前 → 是流量不精准或买错人群(调定向)
- 若最差在"下单/支付" → 是承接/货/价的问题(归主播与选品)

**第三步: 对广告侧做体检**
- objective / optimization_goal 是否匹配当下阶段
- 样本量是否够(不够则退到宽目标)
- AdGroup/Ad 是否频繁改动导致重新学习
- 定向是否过宽/过窄、是否有排除列表

**第四步: 核对归因与口径**
- 归因窗口是否收敛(下播/24h/7d)
- 付费 vs 综合 ROAS 分开看
- 是否有重复上报 / iOS 丢失(检查 CAPI)

**结论动作示例**
- 接不住(停留低) → 调定向 + 主播开场, 别急着加预算
- 转化率低但流量准 → 优化价格/优惠/信任话术
- 流量不准(CVR 全面低) → 换人群/相似人群/排除已购
- 只是归因窗口未收敛 → 等 24h/7d 再下结论, 别误暂停

这套"漏斗拆解 + 承接/流量归因"的方法,
保证优化动作落在真正的短板, 而不是盲目加减预算。
</details>

---

## 六、总结与口诀

把整份文档压缩成几条便于记忆与执行的要点:

| 主题 | 核心要点 |
|------|---------|
| 生态 | 内容层 + 交易层 + 广告层 三层闭环 |
| 广告产品 | LIVE_2_SHOP / 直播推广 / 购物车广告 / Spark Ads+LIVE |
| 目标 | PRODUCT_SALES / SALES, 优化 COMPLETE_PAYMENT |
| 出价 | MAXIMIZE_CONVERSIONS 或 CPA |
| 追踪 | Pixel + CAPI 双通道, 点击 7 天/观看 1 天归因 |
| 节奏 | 预热(30 分钟)→ 开播(峰谷调优)→ 收尾(冲峰值)→ 下播停投 |
| 复盘 | 漏斗拆解定短板 + 付费 vs 综合 ROAS 分开看 |

**投手口诀(六句)**
```
直播间活着, 广告才有意义;      —— 先确认在播与绑定
承接不住, 再准的流量也浪费;    —— 先解决最差一环
样本太少, 越窄的目标越不出量;  —— 阶梯式爬坡
高峰加投, 低谷保自然;          —— 流量波形协同
下播即停, 别让钱流进死直播间;  —— 排程与停投
归因要等窗口, 口径要统一;      —— 24h/7d + 付费vs综合
```

这套"三层闭环 + 实时作战 + 漏斗拆解"的方法论,
是让 TikTok 直播带货广告从"靠感觉烧钱"
升级为"靠数据实时调控、逐场提效"的关键。

---

*本文档为 TikTok 直播带货广告专项深度实战指南,
代码均基于 scripts/tiktok_api.py 的真实方法(TikTok Marketing API v1.3)。
实际投放请以 TikTok 官方当前产品为准, 并结合品牌自身数据校验。*
