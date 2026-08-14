# 跨平台广告战略级选型与整合指南

> **领域**: 广告投放 / 跨平台
> **深度**: ⭐⭐⭐⭐⭐ 实战级指南
> **标签**: cross-platform, platform-selection, strategy, google-ads, meta-ads, tiktok-ads, dv360, budget-allocation, migration, org-scale
> **更新时间**: 2026-08-14
> **类型**: strategy/production

---

## 目录

- [一、核心概念与架构](#一核心概念与架构)
- [二、深度原理解析](#二深度原理解析)
- [三、生产环境实战](#三生产环境实战)
- [四、常见问题与排查](#四常见问题与排查)
- [五、自测题](#五自测题)

---

## 一、核心概念与架构

### 1.1 为什么要做跨平台战略选型

在 2026 年的数字广告生态中，没有任何单一平台能够覆盖一个品牌的完整增长曲线。用户的决策旅程已经碎片化为"搜索—社交—短视频—程序化展示"多重触点交叉的复杂网络。**跨平台广告战略选型**的本质，不是简单地把预算平摊到四个平台，而是回答四个核心问题：

```
┌──────────────────────────────────────────────────────────────────┐
│              CROSS-PLATFORM STRATEGY 四大灵魂拷问                    │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Q1 在每个用户决策节点，哪个平台是"生产效率最高"的？                 │
│      → 对应平台定位矩阵（搜索 vs 社交 vs 短视频 vs 程序化）           │
│                                                                  │
│  Q2 每个平台在能力维度上到底强在哪、弱在哪？                         │
│      → 对应平台能力雷达图（触达/数据/自动化/创意/转化）               │
│                                                                  │
│  Q3 手上的预算应该按什么规则分配到各平台？                           │
│      → 对应预算分配策略（目标×行业×地区）                           │
│                                                                  │
│  Q4 如何把人力、基建、归因从单一平台平滑迁移到多平台？                 │
│      → 对应平台迁移路径 + 组织架构适配                             │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

**为什么"单平台内卷"会触顶？**

```
单平台增长曲线（示意）

  投入产出
   ▲
   │              ╭─────────────── 平台内竞争加剧，CPM/CPC 上涨
   │            ╭╯
   │          ╭╯    ← 平台优化算法学习完成，进入平台级瓶颈
   │        ╭╯
   │      ╭╯
   │    ╭╯
   │  ╭╯
   │╭╯
   ┼──────────────────────────► 投放量
   └── 冷启动期  放量期处   平台饱和期
```

关键洞察：

1. **归因天花板** — 单一平台只给"自己的功劳"打分，看不到跨平台的真实贡献。Google 会说"转化都是我的"，Meta 也会说"都是我的"，但真实情况是两者合力。
2. **人群重叠率** — 四大平台用户高度重叠（抽样显示重叠率可达 40%~60%），不加频控与去重，就会在重复触达同一批人上浪费预算。
3. **创意折旧** — 同一套素材在某个平台跑 3~6 周后 CTR 衰减（creative fatigue），跨平台轮换可以延长素材生命周期。
4. **政策与合规波动** — Apple ATT、GDPR、中国版个人信息保护法（PIPL）、TikTok 禁令不确定性，让"单一平台押注"风险极高。

### 1.2 四大平台的本质定位

在深入之前，先建立一个**思维模型**：四个平台对应四种不同的"用户心智触发点"。

| 平台 | 一句话定位 | 用户心智 | 决策阶段 | 核心广告单元 |
|------|-----------|---------|---------|-------------|
| **Google Ads** | 搜索意图引擎 | "我要找..." | 需求已明确（Bottom Funnel） | Search / Performance Max / YouTube |
| **Meta Ads** | 社交兴趣引擎 | "我在刷..." | 需求启发与比较（Mid Funnel） | Feed / Reels / Advantage+ / Stories |
| **TikTok Ads** | 短视频注意力引擎 | "我在看..." | 需求激发（Top Funnel 种草） | In-Feed / Spark Ads / TikTok Shop |
| **DV360** | 程序化品牌引擎 | "我在买..."（媒体包） | 品牌触达与全漏斗覆盖 | Programmatic Display / Video / Audio / CTV |

```
决策漏斗 × 平台覆盖图

   Top of Funnel (认知)      TikTok 种草、DV360 品牌展示、YouTube 品牌广告
      │
      ▼
   Mid of Funnel (兴趣/比较)  Meta Feed/Reels、Google Display/YouTube、TikTok 达人
      │
      ▼
   Bottom of Funnel (意图/行动) Google Search、Google Shopping/PMax、Meta 再营销、TikTok Shop
```

**为什么这个定位重要？**

因为**预算应该跟随用户心智，而不是跟随平台功能清单**。一个"我要买"的用户，你在 TikTok 上给他种草是没有效率的；一个"我还在种草期"的用户，你在 Google 上投品牌词等于浪费钱（因为他还不会搜）。

### 1.3 平台定位矩阵（横向深度版）

| 维度 | Google Ads | Meta Ads | TikTok Ads | DV360 |
|------|-----------|----------|-----------|-------|
| **引擎类型** | 搜索意图引擎 | 社交兴趣引擎 | 短视频注意力引擎 | 程序化品牌引擎 |
| **匹配逻辑** | 关键词 + 用户搜索时点 | 兴趣 + 行为 + 相似人群 | 内容 + 病毒系数 + 社交图谱 | 上下文 + 受众包 + 媒体包 |
| **意图强弱** | ⭐⭐⭐⭐⭐ 强意图 | ⭐⭐⭐ 中意图 | ⭐⭐ 弱意图(种草) | ⭐⭐⭐⭐ 可控意图 |
| **触达广度** | ⭐⭐⭐⭐ 90%+ 搜索覆盖 | ⭐⭐⭐⭐⭐ 最大社交图谱 | ⭐⭐⭐⭐ 年轻用户强 | ⭐⭐⭐⭐⭐ 全互联网库存 |
| **决策路径长度** | 短（直接转化） | 中（启发后转化） | 中长（种草后转化） | 中长（品牌覆盖） |
| **典型 KPI** | ROAS / CPA / CPL | ROAS / CTR / 互动 | CPR / 播放 / 互动 | Reach / VCR / 品牌提升 |
| **必备工具** | GA4 + Search Console + BigQuery | Meta Pixel + CAPI + Events API | TikTok Pixel + Events API + Branded Mission | ADH + CM360 + SA360 |
| **付费模式** | CPC / CPM / ROAS 出价 | CPC / CPM / CPA 优化 | CPV / CPM / CPA | CPM / CPCV / 程序化担保(PD) |
| **预算门槛** | 中小规模可入门 | 低门槛但放量快 | 低门槛、年轻人 | 高门槛（企业级） |
| **学习曲线** | 中等 | 较低 | 中等 | 陡峭 |
| **数据封闭性** | 中（GA4 半开放） | 高（墙内花园） | 高（墙内花园） | 低（可通过 ADH 深度整合） |
| **API 成熟度** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| **对 DTC/电商** | 核心引擎 | 核心引擎 | 增长引擎 | 品牌放大 |

#### 1.3.1 用户规模对比

```
平台规模快照 (2026 年参考)

  用户规模
    ▲
  40亿│  ███
      │  ███ Meta 生态 (FB+IG+WA 月活约 39亿)
  30亿│  ███ ███
      │  ███ ███
  20亿│  ███ ███ ███
      │  ███ ███ ███ TikTok (月活约 18-20亿)
  10亿│  ███ ███ ███ ███
      │  ███ ███ ███ ███  Google (搜索月活约 40亿, 无直接可比)
      └───┬────┬────┬────►
          Google Meta TikTok DV360
                         (依托 Web 全库存, 间接覆盖 90%+)
```

#### 1.3.2 预算门槛与 ROI 特征

| 平台 | 月预算门槛 | 放量速度 | 冷启动周期 | 单量成本基准（参考） |
|------|-----------|---------|-----------|---------------------|
| Google Search | $1,000+ | 快 | 3~7 天 | CPC 视行业 $1~$10 |
| Google PMax | $3,000+ | 中 | 7~14 天 | 依赖 feed 质量 |
| Meta | $1,000+ | 很快 | 3~5 天 | CPA 视品类 |
| TikTok | $1,000+ | 很快 | 3~5 天 | CPV $0.01~0.05 |
| DV360 | $10,000+/月 | 中 | 30 天+ | CPM $3~$15 |

### 1.4 平台能力雷达图对比

这是文档中最具决策价值的一张图。我们把每个平台在 **五个核心能力维度**上打分（满分 10）：

| 维度 | Google Ads | Meta Ads | TikTok Ads | DV360 |
|------|:---------:|:--------:|:----------:|:-----:|
| 触达规模 | 8 | 9 | 8 | 9 |
| 数据精度 | 9 | 8 | 6 | 7 |
| 自动化程度 | 9 | 9 | 8 | 7 |
| 创意灵活性 | 6 | 9 | 10 | 6 |
| 转化追踪 | 9 | 7 | 5 | 6 |

**ASCII 雷达图（文字版星形图）**

```
能力雷达图（星形展开，★=高分）

                  [触达规模]              Google ─── ●
                    ▲  ●                  Meta   ─── ▲
                   ╱│                       TikTok ─── ■
                  ╱ │                       DV360 ─── ◆
        [创意灵活性]◄──┼──► [自动化]
                  ╲ │
                   ╲│
                    ▼
                [数据精度]    [转化追踪]

  评分分布（每条 = 平台在该维度的分，满 10）：

  维度           Google    Meta    TikTok   DV360
  触达规模       ████████  █████████ ████████ █████████
  数据精度       █████████ ████████  ██████   ███████
  自动化         █████████ █████████ ████████ ███████
  创意灵活性     ██████    █████████ ████████████████████
  转化追踪       █████████ ███████   █████    ██████
```

**评分依据说明（每个维度的打分逻辑）：**

- **触达规模（Google 8 / Meta 9 / TikTok 8 / DV360 9）**
  Google 搜索覆盖率广但广告位天然受限（只覆盖"在搜索的人"）；Meta 有最大社交图谱；TikTok 在年轻人中激增但在 35+ 人群中偏弱；DV360 依托全互联网 Web/安卓/CTV 库存，触达最广。
- **数据精度（Google 9 / Meta 8 / TikTok 6 / DV360 7）**
  Google 有最强搜索意图信号（用户主动表达需求）;Meta 靠兴趣+行为图谱但受 ATT 影响；TikTok 兴趣信号与转化归因都弱（user-side data 受限）；DV360 数据精度取决于你上传的受众包与 DMP 数据质量。
- **自动化程度（Google 9 / Meta 9 / TikTok 8 / DV360 7）**
  Google Performance Max 和 Meta Advantage+ 都是全自动化黑盒；TikTok 的自动化在快速追赶（Automated Creative Optimization, Smart+ Campaigns）；DV360 偏"半自动"——需要人力配置交易与 pacing，自动化程度取决于脚本化能力。
- **创意灵活性（Google 6 / Meta 9 / TikTok 10 / DV360 6）**
  Google 搜索基本是纯文本，PMax 依赖素材上传但创意空间有限；Meta 支持多种版位原生创意；TikTok 是创意为王的平台（原生短视频、音乐、特效、达人共创）；DV360 创意规范严格且品牌安全约束多。
- **转化追踪（Google 9 / Meta 7 / TikTok 5 / DV360 6）**
  Google 有最强转化追踪能力（Google Ads Conversion / GA4 深度打通）;Meta 有 CAPI/Conversion API 补充但受 ATT 限制；TikTok 归因窗口短、数据缺失率高；DV360 主要做 view-through 与媒体层归因，转化可追溯但不如 Search 精准。

#### 1.4.1 雷达图 → 平台选型的直接读法

```
雷达图 → 平台选型速查

  "我要直接转化，ROAS 要稳"        → 选 Google（转化追踪 9 + 自动化 9）
  "我要大规模触达 + 再营销"        → 选 Meta（触达 9 + 创意 9）
  "我要新品种草 + 年轻人群"        → 选 TikTok（创意 10 + 触达 8）
  "我要全漏斗品牌覆盖 + 企业级控制" → 选 DV360（触达 9 + 数据 7 + 控制强）
```

### 1.5 跨平台整体架构（宏观视图）

一个成熟的跨平台投放团队，其系统/数据架构通常呈如下形态：

```
┌─────────────────────────────────────────────────────────────────────┐
│                      CROSS-PLATFORM AD ARCHITECTURE                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  战略层  Strategy Layer                                               │
│  ┌────────────────────────────────────────────────────────────┐      │
│  │  平台定位矩阵   │  能力雷达图   │  预算分配模型   │  目标设定  │      │
│  └────────────────────────────────────────────────────────────┘      │
│                        │  ↓ 决策                                    │
│  平台层  Platform Layer                                               │
│  ┌─────────┬─────────┬─────────┬─────────┐                         │
│  │ Google  │  Meta   │ TikTok  │  DV360  │  ← 各平台独立 API/界面     │
│  │ Ads/PMax│  Ads    │  Ads    │  DSP    │                          │
│  └─────────┴─────────┴─────────┴─────────┘                         │
│                        │  ↓ 事件流（Server-Side / CAPI 等）           │
│  数据层  Data Layer                                                    │
│  ┌────────────────────────────────────────────────────────────┐      │
│  │  第一方数据仓库（BigQuery / Snowflake）                       │      │
│  │  ├── 点击/曝光事件表  ├── 转化事件表  ├── 归因结果表           │      │
│  │  ├── 素材/创意表      ├── 预算分配表  ├── 用户频控去重表       │      │
│  └────────────────────────────────────────────────────────────┘      │
│                        │  ↓ 建模                                    │
│  分析层  Analytic Layer                                               │
│  ┌────────────────────────────────────────────────────────────┐      │
│  │  MMM建模 │ MTA归因 │ 频控优化 │ 创意疲劳检测 │ 预算重分配引擎 │      │
│  └────────────────────────────────────────────────────────────┘      │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘
```

**架构要点：**

1. **战略层只做"分配决策"**，不直接操作平台，保证决策与执行解耦。
2. **平台层保持原生 API 接入**，避免为了统一而牺牲各平台原生能力。
3. **数据层是所有跨平台能力的地基**——没有统一的事件模型，就没有跨平台归因、频控、创意疲劳检测。
4. **分析层把数据变成行动**——最终输出"预算重分配指令"回流到平台层。

### 1.6 跨平台技术基建清单

| 模块 | 推荐技术 | 作用 |
|------|---------|------|
| 事件收集 | Google Tag / Meta Pixel / TikTok Pixel + Server-Side GTM / CAPI | 统一采集点击与转化 |
| 数据仓库 | BigQuery / Snowflake / Redshift | 跨平台数据汇聚 |
| 归因引擎 | 自建 MTA + 媒体渠道 MMM | 真实贡献评估 |
| 频控去重 | CM360 / ADH / 自建 ID 映射 | 跨平台去重 |
| 报表平台 | Looker / Tableau / 自建 Dash | 看板与告警 |
| API 编排 | Python / Go + 各平台 SDK | 批量操作与自动化 |
| 预算决策 | 自建分配算法（见第三节） | 动态预算分配 |

### 1.7 关键术语表（跨平台语境）

| 术语 | 全称/含义 | 所属平台 |
|------|----------|---------|
| PMax | Performance Max 效果最大化 | Google |
| H-iMax | High-Intent Performance Max（高意图 PMax） | Google |
| SA360 | Search Ads 360 搜索广告管理平台 | Google |
| CM360 | Campaign Manager 360 媒体管理平台 | Google |
| Advantage+ | Meta 全自动投放系列 | Meta |
| CAPI | Conversions API 服务端转化 API | Meta |
| Spark Ads | 达人原生内容推广 | TikTok |
| Smart+ | TikTok 自动化投放 | TikTok |
| ADH | Ads Data Hub 广告数据中心 | Google/DV360 |
| DSP | Demand-Side Platform 需求方平台 | DV360 |
| PD | Programmatic Direct 程序化直采 | DV360 |
| MMM | Marketing Mix Modeling 营销组合模型 | 跨平台 |
| MTA | Multi-Touch Attribution 多触点归因 | 跨平台 |

---

## 二、深度原理解析

### 2.1 Google Ads：搜索意图引擎的原理

#### 2.1.1 产品矩阵

```
Google Ads 产品矩阵

  效果广告（Direct Response）            品牌广告（Brand）
  ┌────────────────────┬──────────────────────────────┐
  │ Search 搜索广告      │ YouTube 视频广告              │
  │   - 品牌词           │   - In-stream (可跳过/不可跳过) │
  │   - 品类词           │   - In-feed (Shorts)         │
  │   - 长尾词           │   - Bumper (6秒)             │
  ├────────────────────┼──────────────────────────────┤
  │ Performance Max    │ Display 展示广告（GDN）         │
  │   - 全渠道自动化     │   - 自适应展示广告              │
  │   - H-iMax 高意图    │   - 再营销                   │
  │   - 全素材全版位     │                              │
  ├────────────────────┼──────────────────────────────┤
  │ Shopping 购物广告    │ App Campaigns (UAC)          │
  │   - 标准购物         │                              │
  │   - Shopping 再营销  │                              │
  ├────────────────────┼──────────────────────────────┤
  │ Demand Gen (原视频)  │                              │
  │   - Discovery       │                              │
  │   - YouTube 信息流   │                              │
  └────────────────────┴──────────────────────────────┘
```

#### 2.1.2 Search 的竞价原理

Google Search 的核心是 **Ad Rank**：

```
Ad Rank = 出价 × 质量分 (Quality Score) × 预期点击率加成

  质量分 (0~10) 由三部分组成：
  ├── 预期点击率 (Expected CTR)：广告与关键词的相关性
  ├── 广告相关性 (Ad Relevance)：广告文案与搜索词匹配度
  └── 落地页体验 (Landing Page Experience)：落地页速度与相关度
```

**实际每次展示的成本：**

```
CPC(实际) = 广告排名所需最低价 / 质量分权重
         ≈ 下一名 AdRank 所需 + $0.01（简化模型）
```

**跨平台战略意义：** 搜索是"确定性最强的转化渠道"，因为用户意图已被显性化。所以在任何预算分配模型里，Google Search 通常作为"锚定渠道"（ защиты最低 ROAS 的底仓）。

#### 2.1.3 Performance Max / H-iMax 原理

PMax 是一个"全自动化、全生态、全漏斗"的广告系列：

```
Performance Max 输入 → 输出

  输入（你给的）：
  ├── 素材（文案/图片/视频/Logo）
  ├── 转化目标（购买/加购/注册...）
  ├── 预算
  ├── 受众信号（可选，不是硬定向）
  └── 商品 Feed（电商）
     │
     ▼
  Google 的自动化（黑盒）：
  ├── 自动出价（目标 ROAS / 最大化转化）
  ├── 自动定向（实时判断最可能转化的人群）
  ├── 自动版位（Search/Display/YouTube/Gmail/Discover）
  ├── 自动创意组合（用你给的素材拼装）
     │
     ▼
  输出（你看到的）：
  ├── 跨渠道转化
  ├── 各 asset group 表现
  ├── 搜索词表现（部分可见）
  └── 无法控制的细节
```

**H-iMax（High-Intent Performance Max）** 是 Google 对纯"高意图"场景的优化版本——它聚焦在搜索/购物等高意图库存上，降低对低意图展示版位的花费，适合"以转化为目标、不希望被品牌版位稀释 ROAS"的广告主。

**PMax 的跨平台战略意义：**
- PMax 是"吸收尾量流量的自动收割机"，把 Search 投不满的长尾意图都收进来。
- 局限：它是黑盒，你看到的归因会被"Google 视角"扭曲——几乎所有转化都被记为 PMax 的功劳，容易造成对 Google 效果的**过度高估**。

#### 2.1.4 YouTube 广告原理

```
YouTube 广告漏斗

  认知阶段        →  In-Stream 可跳过 / Bumper / Masthead(大促)
  兴趣阶段        →  In-Feed / Shorts / 再营销
  行动阶段        →  Demand Gen + 购物深度链接
```

**YouTube 的独特价值：**
- 与 Google 搜索/展示共享 **同一套用户 ID 与兴趣体系**（Google 生态互联）。
- 长视频是"种草"的最佳载体之一，尤其适合产品深度讲解、品牌故事、评测。

### 2.2 Meta Ads：社交兴趣引擎的原理

#### 2.2.1 产品矩阵

```
Meta 产品矩阵（2026）

  社交平台：  Facebook / Instagram / WhatsApp / Messenger / Reels / Threads
  ┌─────────────────────────────────────────────────────────────┐
  │ 版位 (Placements)                                           │
  │  ├── Feed（信息流）                                          │
  │  ├── Stories（快拍）                                         │
  │  ├── Reels（短视频）  ← 2026 增长最快版位                      │
  │  ├── In-stream（插播视频）                                    │
  │  ├── Marketplace（电商）                                     │
  │  ├── Messenger / WhatsApp（消息广告）                         │
  │  └── Audience Network（第三方 App 网络）                       │
  │                                                             │
  │ 广告目标 (Objectives)                                        │
  │  ├── 品牌认知 (Brand Awareness)                              │
  │  ├── 互动 (Engagement)                                       │
  │  ├── 流量 (Traffic)                                          │
  │  ├── 潜在客户 (Leads)                                        │
  │  ├── 应用推广 (App Promotion)                                │
  │  └── 销售 (Sales / Conversions)                              │
  ├─────────────────────────────────────────────────────────────┤
  │ 自动化产品                                                    │
  │  ├── Advantage+ Shopping Campaigns（电商全自动）              │
  │  ├── Advantage+ App Campaigns（App全自动）                    │
  │  ├── Advantage+ Creative（创意增强）                           │
  │  ├── Advantage Detailed Targeting（放宽定向）                  │
  │  ├── Automated Rules（自动规则）                               │
  │  └── Campaign Budget Optimization (CBO)                       │
  └─────────────────────────────────────────────────────────────┘
```

#### 2.2.2 Meta 的兴趣匹配与受众体系

Meta 的核心资产是**庞大的社交图谱（Social Graph）**——它知道"谁认识谁、谁喜欢什么、谁最近关注了什么"。基于此它构建了四层受众：

```
Meta 受众金字塔

         ┌────────────────────┐
         │  核心受众 (Core)     │ ← 你手动定的人生/兴趣/行为/地域
         ├────────────────────┤
         │  自定义受众 (Custom) │ ← 第一方数据上传（列表/像素/App事件）
         ├────────────────────┤
         │  相似受众 (Lookalike)│ ← 基于种子人群拓展 1%~10%
         ├────────────────────┤
         │  自动定向           │ ← Advantage+ 全自动
         └────────────────────┘
```

**跨平台战略意义：** Meta 的"再营销 + 相似人群"能力是它区别于 TikTok 的核心。在跨平台组合里，Meta 通常承担"承接 Google/TikTok 带来的兴趣，再营销转化 + 扩展相似人群"的角色。

#### 2.2.3 Advantage+ 自动化原理

Advantage+ 是 Meta 版本的全自动化：

```
Advantage+ Shopping Campaigns 原理

  输入：商品目录(Catalog) + 预算 + 目标 ROAS + 最低水平素材
     │
     ▼
  Meta 自动化：
  ├── 自动定向（不锁死受众，让算法自己找人）
  ├── 自动版位（Feed/Reels/Stories...）
  ├── 自动创意（把上传素材/目录商品动态组合）
  ├── 自动出价（动态 ROAS 优化）
     │
     ▼
  特点：
  ├── 冷启动期短（有 Catalog 数据支撑）
  ├── 学习期波动（前 1-2 周不稳定）
  └── 报告颗粒度粗（不要指望看到精确到版位的出价）
```

**Advantage+ 的跨平台战略意义：** Meta 的自动化成熟度不输 Google，但它同样是"黑盒归因"——倾向于把所有功劳归于 Meta。跨平台配置时要注意，不要因为 Meta 自己的报表好看了就忽略 Google 的真实贡献。

#### 2.2.4 Reels 与短视频化

```
Reels 短视频的跨平台角色

  Reels ≈ 版位里的"TikTok 竞品"
  ├── 原生沉浸式短视频
  ├── 算法优先推非关注人群（破圈）
  ├── Creative 音乐/特效/模板丰富
  └── 与 Feed 共享转化优化器

  跨平台洞察：
  ├── 如果你已经在 TikTok 上投放短视频，Reels 可以复用同批素材
  ├── 但注意格式差异（分辨率、时长、文案密度）
  └── Reels 是 Meta 对抗 TikTok 抢占年轻用户注意力的关键
```

### 2.3 TikTok Ads：短视频注意力引擎的原理

#### 2.3.1 产品矩阵

```
TikTok 产品矩阵（2026）

  广告目标 (Campaign Objectives)
  ├── Awareness（认知）—— 覆盖/触达
  ├── Consideration（考虑）—— 流量/互动/视频浏览/粉丝
  └── Conversion（转化）—— 转化/应用安装/商品销量

  广告形式
  ├── In-Feed Ads（信息流原生广告）—— 核心形式
  ├── Spark Ads（达人原生内容推广）—— 核心增长形式
  ├── TopView（首刷开屏）
  ├── Branded Mission / Challenge（品牌挑战赛）
  ├── Branded Effects（品牌特效）
  ├── TikTok Shop Ads（商城广告）
  └── Search Ads Toggle（搜索广告）

  自动化
  ├── Smart+ Campaigns（全自动化，对标 PMax/Advantage+）
  ├── Automated Creative Optimization (ACO)
  ├── Dynamic Creative Optimization
  └── Target ROAS / Max Conversion 出价
```

#### 2.3.2 Spark Ads 原理：达人共创

Spark Ads 是 TikTok 独有的、也是跨平台战略价值最高的产品之一：

```
Spark Ads 原理

  1. 达人生成原生内容（带货视频/评测/种草）
  2. 品牌通过 Spark Ads 把这支"原生视频"作为广告投放
     （视频显示达人账号，看起来像普通内容，信任感强）
  3. 可以放大、再定向、投放到意向人群
     │
     ▼
  优势：
  ├── 原生感强 → CTR/互动率远高于普通 In-Feed
  ├── 自带达人背书 → 转化率高
  ├── 复用达人 UGC → 创意成本低
  └── 评论区活跃 → 社交验证

  跨平台战略意义：
  ├── Spark Ads = "内容营销 + 付费放大"的结合
  ├── 适合新品种草、需要建立信任的品类（美妆/3C/食品/时尚）
  └── 是 TikTok 区别于 Meta/Google 的核心差异化能力
```

#### 2.3.3 TikTok Shop 广告

TikTok Shop 广告把"种草→下单"闭环在站内完成：

```
TikTok Shop 闭环

  看视频 → 点商品卡 → 进 TikTok Shop 详情页 → 下单

  广告形式：
  ├── Video Shopping Ads（视频购物）
  ├── Product Shopping Ads（商品卡购物）
  └── LIVE Shopping Ads（直播购物）

  跨平台战略意义：
  ├── 对 DTC 品牌，TikTok Shop 提供一个"站内闭环"渠道
  ├── 别把 TikTok 只当"种草"，它有直接的交易属性
  └── 需评估 TikTok Shop 的履约/退货/手续费与自建站的成本比较
```

#### 2.3.4 TikTok 的归因与数据弱点

注意：TikTok 在**转化追踪**维度我们给了 5 分（最低），原因如下：

```
TikTok 归因弱项

  ├── 归因窗口短（默认 7 天点击/1 天浏览，通常早于 Meta/Google）
  ├── 像素数据缺失率高（user-side 数据被隐私限制）
  ├── 无法看到完整的用户行为链
  ├── 跨设备追踪弱
  └── 大量"模糊归因/模型推断"

  应对：
  ├── 用 Server-Side Events API + CAPI 类服务端接入弥补
  ├── 延长归因窗口（如配置 7-day click + 1-day view）
  ├── 配合 MMM 做宏观归因，别只看 TikTok 内部报表
  └── 拆分 test vs control 做增量验证
```

### 2.4 DV360：程序化品牌引擎的原理

#### 2.4.1 产品定位与层级

DV360（Display & Video 360）是 Google Marketing Platform 的企业级 DSP：

```
DV360 对象层级

  Advertiser（广告主账户）
   ├── Campaign（营销活动）
   │    ├── Insertion Order（媒介排期单 / IO）
   │    │    ├── Line Item（订单/line item）
   │    │    │    ├── Targeting（定向配置）
   │    │    │    ├── Budget & Pacing（预算与节奏）
   │    │    │    └── Creatives（创意）
   │    │    └── ...
   │    └── ...
   └── ...

  交易类型：
  ├── Auction（公开竞价 RTB）
  ├── Private Auction（私有竞价）
  ├── Preferred Deal（优选交易）
  └── Programmatic Guaranteed / PD（程序化直采/保量）
```

#### 2.4.2 DV360 的独有能力

DV360 与另外三个平台最大的差异在于：**它是个"企业级控制塔"，而不是单一媒体源**。

```
DV360 独有能力

  1. 媒体库（Media Library）
     ├── 覆盖全互联网 Web 库存
     ├── 主流 App（通过 AdMob/AdSense/第三方 SDK）
     ├── CTV（联网电视）— 大屏覆盖
     ├── Audio（播客/广播）
     └── 出价的跨媒介整合

  2. 受众管理（Audience 360）
     ├── 上传第一方受众
     ├── 接入第三方数据（DMP / 数据供应商）
     ├── 基于上下文定向（contextual）
     └── 与 Google 生态受众互通

  3. 品牌安全（Brand Safety）
     ├── 品牌安全排除（成人/暴力/仇恨内容）
     ├── 敏感类别控制
     ├── 频次上限（Frequency Cap）
     └── 落地页体验评分

  4. 测量整合（Measurement）
     ├── 接入 CM360 归因
     ├── 接入 ADH（Ads Data Hub）做深度数据整合
     ├── Brand Lift 品牌提升研究
     └── Viewability（可见度）测量

  5. Programmatic 控制
     ├── 全站频次控制
     ├── 跨交易去重
     ├── Pacing 节奏控制
     └── 精细预算控制
```

#### 2.4.3 DV360 与 Google 生态的关系

```
DV360 在 Google 生态中的角色

  品牌方
    │
    ├── 媒体计划 → DV360（执行 DSP）
    ├── 归因测量 → CM360（Campaign Manager）
    ├── 搜索管理 → SA360（Search Ads 360）
    ├── 数据分析 → ADH / BigQuery
    └── 内容 → YouTube（通过 DV360 投放）
```

**关键洞察：** DV360 与 Google 付费搜索/YouTube 是"不同决策单元"。DV360 管的是**全互联网程序化品牌库存**，而 Google Ads 管的是**Google 自有生态**。一个品牌可以同时用 Google Ads 投搜索 + DV360 投品牌展示，两者不冲突而是互补。

#### 2.4.4 DV360 的"品牌优先"属性

| 维度 | DV360 导向 | 对比（效果平台） |
|------|-----------|----------------|
| 主要 KPI | Reach, VCR, Viewability, Brand Lift | ROAS / CPA |
| 计费 | 主要 CPM/CPCV | CPC/CPA |
| 优化目标 | 覆盖与品牌健康 | 直接转化 |
| 决策周期 | 季度媒体计划 | 周/日优化 |
| 预算规模 | 大（$10K+/月） | 中 |
| 数据深度 | ADH 可做用户级分析 | 黑盒归因 |

### 2.5 跨平台归因与增量（原理核心）

跨平台战略的"地基"是**归因与增量**。如果四个平台各自报功，你永远不知道真相。

#### 2.5.1 归因模型谱系

```
归因模型谱系

  单触点模型                      多触点模型
  ├── 最后点击 (Last Click)        ├── 线性 (Linear)
  ├── 首次点击 (First Click)       ├── 时间衰减 (Time Decay)
                                  ├── 位置模型 (Position Based)
                                  ├── 数据驱动 (Data-Driven / MTA)
                                  └── Shapley / Markov（更严谨）

  媒体效果归因（宏观）
  ├── MMM（Marketing Mix Modeling）—— 以天/周为粒度的统计归因
  └── Geo Lift / Incrementality Test —— 地理增量实验
```

#### 2.5.2 为什么单一平台归因会误导预算分配

```
单一平台归因的"自我中心"问题

  用户路径：Google 搜索看到 → Meta 再营销 → 在 TikTok 种草视频下单

  Google 报表：这条转化归我（最后点击？其实不是）— 高估 Google
  Meta 报表：归我（点击了再营销）—— 高估 Meta
  TikTok 报表：归我（最后转化在我的视频）—— 高估 TikTok

  → 三个平台加起来 > 100%，这就是"归因膨胀"
```

**跨平台战略要求统一归因视角**（第一方数据仓库 + MMM + 增量实验）。

#### 2.5.3 增量测试（incrementality）原理

```
Geo Incrementality 实验（经典）

  把同质市场分成 Test / Control 两组：
  ├── Test：正常投放某平台广告
  └── Control：关闭该平台广告（或降低 50%）

  对比两组销售差异 = 该平台的"增量贡献"

  优点：排除"即使不投广告也会买的自然转化"
  缺点：成本高、周期长（需要足够统计功效）

  Constraints：
  ├── 需要足够大的地理单元
  ├── 需要 2~4 周以上
  └── 需要考虑外部变量（seasonality, promos）
```

**跨平台战略建议：** 不要过度依赖任何单平台的归因报表。每年做 1~2 轮 geo incrementality 测试，校准各平台的真实增量率（incremental ROAS），用校准后的数据驱动预算分配。

### 2.6 四平台算法/自动化哲学对比

| 维度 | Google | Meta | TikTok | DV360 |
|------|--------|------|--------|-------|
| 自动化产品 | PMax / H-iMax / Smart Bidding | Advantage+ / CBO | Smart+ / ACO | 无同级黑盒 |
| 自动化哲学 | "把控制交给算法以最大化转化" | "放宽定向让算法找对的人" | "让内容算法决定爆款" | "人驱动媒体计划，脚本辅助执行" |
| 出价方式 | Max Conversion / Target ROAS / Target CPA | CBO + 目标 ROAS/CPA | Target ROAS / Max Conversion | 手动 CPM + pacing |
| 黑盒程度 | 高 | 高 | 中高 | 低 |
| 学习期 | 7-14 天 | 3-7 天 | 3-5 天 | N/A |
| 是否适合小团队 | 是（全自动） | 是（全自动） | 是 | 否（需专人） |

### 2.7 跨平台事件的统一数据模型

这是"深度原理解析"里最工程化的一节。要实现跨平台比较，必须先把四平台的原始事件统一成**标准事件模型**。

```
统一事件模型 (UTM + 平台事件映射)

  原始事件（四平台）：
  ├── GoogleAds: Click, Conversion(w/ conversion_action_id, gclid)
  ├── Meta:      Click, View, Purchase(w/ fbclid)
  ├── TikTok:    Click, View, Conversion(w/ ttclid)
  └── DV360:     Impression, Click, View(w/ dclid)

  标准化后（存 BigQuery）：
  ┌──────────────────────────────────────────────────┐
  │ events_staging                                    │
  ├──────────────────────────────────────────────────┤
  │ event_id        STRING                            │
  │ platform        STRING   (google/meta/tiktok/dv360)│
  │ campaign_id     STRING                            │
  │ adset_id        STRING                            │
  │ ad_id           STRING                            │
  │ user_cookie/id  STRING   (第一方拼接)               │
  │ event_type      STRING   (impression/click/conversion) │
  │ conversion_type STRING   (purchase/lead/signup)   │
  │ utm_source      STRING                            │
  │ utm_medium      STRING                            │
  │ utm_campaign    STRING                            │
  │ event_ts        TIMESTAMP                         │
  │ device          STRING                            │
  │ amount_usd      FLOAT                             │
  └──────────────────────────────────────────────────┘
```

```
UTM 规范示例（跨平台统一埋点）

  https://yourdomain.com/landing?
    utm_source=google|meta|tiktok|dv360
    utm_medium=cpc|video|display
    utm_campaign=campaign_name
    utm_content=ad_variant
    utm_term=keyword_or_placement
```

**为什么 UTM 规范如此重要？** 如果四个平台埋点的 UTM 命名不一致，统一报表根本无法聚合，跨平台比较就是空谈。

```sql
-- 统一跨平台漏斗查询（BigQuery 示例）
SELECT
  utm_source,
  COUNTIF(event_type = 'impression') AS impressions,
  COUNTIF(event_type = 'click')      AS clicks,
  COUNTIF(event_type = 'conversion') AS conversions,
  SUM(IF(event_type='conversion', amount_usd, 0)) AS revenue
FROM `your_project.ads.events_staging`
WHERE event_ts >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
GROUP BY utm_source
ORDER BY revenue DESC;
```

### 2.8 跨平台创意疲劳与素材轮换原理

```
创意生命周期曲线

  表现
   ▲
   │      ╭─ 上升期（学习+新鲜感）
   │    ╭╯  ╲ 成熟期
   │  ╭╯     ╲── 疲劳期（CTR/CPM 恶化）
   │╭╯          ╲
   ┼──────────────────────► 时间
   0    1~2周    3~6周

  跨平台素材轮换策略：
  ├── 同一素材在 A 平台疲劳后，换到 B 平台可能有"新鲜人群"余量
  ├── 但要注意跨平台疲劳间隔：避免同一批人看到同一素材
  └── 用统一创意库管理每个素材在各平台的表现
```

**创意疲劳检测公式（跨平台通用）：**

```
Creative Fatigue Score = f(曝光期间 CTR 衰减率, CPM 上升率, 互动率下降)

  经验阈值：
  ├── CTR 相对峰值下降 > 30% 且持续 3 天 → 需刷新素材
  ├── CPM 相对基准上升 > 20% → 可能消耗了重叠人群
  └── 单素材曝光量 > 单平台人群池的一定比例 → 高频暴露
```

### 2.9 跨平台频次控制与去重原理

```
跨平台频次问题

  同一用户可能在一天内：
  ├── Google 搜了 3 次 → 看到 3 次搜索广告
  ├── Meta 刷了 20 条 → 看到 5 条 Meta 广告
  ├── TikTok 刷了 30 条 → 看到 4 条 TikTok 广告
  └── 网页上被 DV360 投了 10 次展示
  ─────────────────────────────
  合计触达该用户 22 次 → 过度曝光，CPM 浪费+负面体验

  解决方案：
  ├── 平台内频控（各平台自己的 frequency cap）
  ├── 跨平台频控（需要统一 ID / CM360 / ADH + 私有数据）
  └── 数据驱动的受众去重（见第三节代码）
```

### 2.10 跨平台决策树总览

把前文原理浓缩成一张决策树：

```
跨平台选型决策树（First Cut）

  你的核心目标是什么？
     │
     ├─ 直接转化/ROAS → Google (Search + PMax)
     │     ├─ 是电商？ → 加 PMax/Shopping
     │     └─ 是 B2B/线索？ → 加 Search + Demand Gen
     │
     ├─ 增长与规模 + 兴趣人群 → Meta (Advantage+/Feed/Reels)
     │     └─ 需要再营销？ → 加 Meta 自定义+相似受众
     │
     ├─ 新品种草 + 年轻人群 → TikTok (In-Feed + Spark Ads)
     │     └─ 有达人资源？ → 优先 Spark Ads
     │
     └─ 品牌覆盖 + 全漏斗 + 企业级 → DV360 (程序化品牌)
           ├─ 需要 CTV/大屏？ → 用 DV360
           └─ 需要品牌安全/频控？ → 用 DV360

  然后进入"预算分配四象限"（见第三节）
```

---

## 三、生产环境实战

### 3.1 预算分配策略总览

预算分配是跨平台战略里"最需要方法论、也最容易被拍脑袋"的环节。本节给出可落地的三层方法：
1. **按目标分配**（品牌 vs 效果）
2. **按行业分配**（电商 vs 游戏 vs 金融）
3. **按地区分配**（成熟市场 vs 新兴市场）

以及一个**动态重分配算法**。

#### 3.1.1 预算分配的数学框架

我们先把"预算分配"形式化为一个**约束优化问题**：

```
目标：在给定总预算 B 下，最大化整体目标函数（ROAS / 有效触达 / 综合效用）

max  Σ_i  w_i · U_i(b_i)
s.t. Σ_i  b_i = B
     b_i ≥ b_i^min           （各平台最低预算门槛）
     b_i ≤ b_i^max           （各平台消化上限）

其中：
  b_i   = 分配给平台 i 的预算
  U_i   = 平台 i 的效用函数（随预算递减——边际回报递减）
  w_i   = 业务权重（品牌目标时品牌平台权重大，效果目标时效果平台权重大）
```

**边际回报递减（diminishing returns）**是预算分配的第一性原理：

```
边际回报曲线

  每元预算带来的增量转化
   ▲
   │╲
   │ ╲
   │  ╲     ← 边际回报递减，第二跑不如第一跑划算
   │   ╲
   │    ╲
   ┼───────╲────────────────► 累计预算
   └────────────────────
        优化点：让各平台边际回报趋近相等（否则把钱从低效端挪到高效端）

  分配最优条件（等边际原则）：
  MU_google / Cost_google = MU_meta / Cost_meta = MU_tiktok / Cost_tiktok = ...
```

#### 3.1.2 目标导向：品牌 vs 效果

先定义两类目标，再给分配指导：

| 目标类型 | 核心 KPI | 典型平台组合 | 分配逻辑 |
|---------|---------|-------------|---------|
| **纯效果** | ROAS / CPA / CPL | Google Search/PMax + Meta 再营销 | 效果平台 ≥ 85%，品牌 ≤ 15% |
| **品牌为主** | Reach / VCR / Brand Lift / Share of Voice | DV360 + YouTube + TikTok 品牌 | 品牌平台 ≥ 60%，效果兜底 |
| **混合** | 全漏斗 | 四平台全线 | 按漏斗路径分配 |
| **新品上市** | 认知 + 首单 | TikTok 种草 + Meta 放大 + Google 承接 | 认知 40% + 放大 35% + 承接 25% |

**品牌 vs 效果预算切换信号：**

```
什么时候把预算从效果平台挪向品牌平台？
├── 品牌搜索词量长期持平/下降（自然搜索量 = 品牌健康度信号）
├── 规模化增长遇到瓶颈：加大效果预算不再带来等比例转化
├── 要进入新品类/新市场，需要先建立心智
└── 竞品声量明显上升，需争夺 Share of Voice

什么时候从品牌挪回效果？
├── 营销活动有明确 ROI 考核、转化下滑
├── 现金流紧张，需要短期见效
└── 品牌提升已足够，转向收割
```

**品牌 vs 效果联动（full-funnel 比例示例，混合目标）：**

| 预算段 | 阶段 | Google | Meta | TikTok | DV360 |
|--------|------|:------:|:----:|:------:|:-----:|
| 1 | 认知（Top） | 5% | 10% | 15% | 15% |
| 2 | 兴趣（Mid） | 10% | 20% | 10% | 0% |
| 3 | 承接（Bottom） | 25% | 10% | 0% | 0% |
| 合计 | | 40% | 40% | 25% | 15% → 需归一化 |

> 注：上面是"份额示意"，实际需归一化到 100%（示例内部 5+10+25=40, 10+20+10=40, 15+10=25, 15=15 → 合计 120，需按各段权重归一）。

#### 3.1.3 行业适配：电商 vs 游戏 vs 金融

不同行业对四个平台的匹配度差异巨大。这里给出三个重点行业的分配建议。

##### 3.1.3.1 电商（DTC / E-commerce）

```
电商平台适配矩阵

  平台    适配度  理由                          主要目标
  Google   ⭐⭐⭐⭐⭐ 搜索+购物意图最强            ROAS 收割
  Meta     ⭐⭐⭐⭐⭐ 再营销+相似人群+目录广告      转化+放大
  TikTok   ⭐⭐⭐⭐  新品种草+年轻+Spark/Shop      种草+新客
  DV360    ⭐⭐⭐   品牌大促声量+全漏斗            品牌覆盖
```

**电商（月预算 $100K，成熟期）示例分配：**

| 平台 | 占比 | 月预算 | 具体做法 | 目标 |
|------|:----:|:------:|---------|------|
| Google PMax | 30% | $30K | 全渠道收割、feed 优化 | ROAS 3.5x+ |
| Google Search | 15% | $15K | 品牌词+品类词拦截 | ROAS 5x+ |
| Meta Advantage+ Shopping | 20% | $20K | 目录广告+再营销 | ROAS 3x+ |
| TikTok In-Feed+Spark | 20% | $20K | 新品种草+达人放大 | 新客 CPNA |
| DV360 | 10% | $10K | 大促/品牌提升 | Reach+VCR |
| 预留（测试） | 5% | $5K | 新平台/新素材实验 | 学习预算 |

**电商分配关键点：**
- **Google 是"确定性收割机"**：代购代收、搜索意图明确，ROAS 最稳定。
- **Meta 是"放大器"**：承接浏览未购人群中再营销。
- **TikTok 是"流量引擎"**：投新品种草，靠 Spark Ads 降低获客成本。
- **DV360 是"声量工具"**：大促前 2~4 周开启，为 Search/Meta 打底。

##### 3.1.3.2 游戏（Gaming / Mobile Games）

```
游戏平台适配矩阵

  平台    适配度  理由                             主要目标
  Google   ⭐⭐⭐⭐ 搜索+UAC(Universal App Campaign) 安装+付费
  Meta     ⭐⭐⭐⭐⭐ 兴趣+受众网络+高买量规模         安装+ROAS
  TikTok   ⭐⭐⭐⭐⭐ 短视频试玩+病毒传播             安装+长线LTV
  DV360    ⭐⭐⭐   品牌+大IP联动+跨屏提升           品牌声量

  （注：游戏行业核心指标是 CPI/CPA + ROAS at D7/D30 + LTV:CAC）
```

**游戏（月预算 $80K，买量为主）示例分配：**

| 平台 | 占比 | 月预算 | 具体做法 | 目标 |
|------|:----:|:------:|---------|------|
| Google UAC | 20% | $16K | 全自动安装/付费优化 | CPI/ROAS |
| Meta | 25% | $20K | Advantage+ App + Audience Network | 规模+ROAS |
| TikTok | 35% | $28K | 试玩广告+达人+Spark | CPI+病毒效应 |
| DV360 | 10% | $8K | 品牌+预注册+跨屏 | 品牌声量 |
| 测试预算 | 10% | $8K | 新素材/新市场实验 | 净PR |

**游戏分配关键点：**
- 游戏高度依赖 **LTV 模型**：买量只看 CPI 会亏，必须用 D7/D30 ROAS + LTV:CAC。
- **TikTok 在游戏买量的占比通常最高**——短视频试玩广告是游戏最佳展示形态。
- 用 **SKAdNetwork / 服务端回调**统一 iOS 归因，跨平台比较才有意义。
- DV360 用于买量前的"预注册 + 品牌造势"，为买量提升转化率。

##### 3.1.3.3 金融（Finance / Fintech）

```
金融平台适配矩阵

  平台    适配度  理由                             主要目标
  Google   ⭐⭐⭐⭐⭐ 高意图搜索（借贷/投资/保险）      线索+专业感
  Meta     ⭐⭐⭐⭐  精准人群+线索收集表单             线索+品牌
  TikTok   ⭐⭐⭐   年轻客群知识科普种草              认知+兴趣
  DV360    ⭐⭐⭐⭐  合规可靠的品牌展示+信任背书       品牌信任

  （注：金融行业转化路径长、监管严格、隐私敏感、CPA 高）
```

**金融（月预算 $60K）示例分配：**

| 平台 | 占比 | 月预算 | 具体做法 | 目标 |
|------|:----:|:------:|---------|------|
| Google Search | 35% | $21K | 品牌词+产品词+长尾意图 | CPL 最低 |
| Google Demand Gen/Display | 10% | $6K | 再营销+兴趣扩展 | 中间转化 |
| Meta Lead Gen | 25% | $15K | 线索表单+相似人群 | CPL |
| TikTok | 10% | $6K | 金融知识科普+年轻客群 | 认知+兴趣 |
| DV360 | 15% | $9K | 品牌背书+合规展示+CTV | 信任度 |
| 测试 | 5% | $3K | 新渠道实验 | 学习 |

**金融分配关键点：**
- 金融是**信任敏感型**行业，转化路径长、需多次触达。DV360 做"信任背书式展示"很有价值。
- **Google Search 主导**：用户主动搜"XX理财"，意图极强，CPL 质量最高。
- **Meta Lead Gen 表单**降低落地摩擦，适合收集潜在客户信息。
- 合规第一：金融广告受严格监管（借贷利率披露、牌照要求），各平台审核流程都要预留时间。

#### 3.1.4 地区适配：成熟 vs 新兴

```
地区维度平台权衡

  成熟市场（北美/西欧/日韩）
  ├── Google/Meta 用户基数高、付费意愿强、数据基础设施完善
  ├── Google Search + Meta 是绝对主力
  ├── DV360 用于品牌和 CTV 覆盖
  └── TikTok 在成熟市场同样重要（美国月活庞大）

  新兴市场（东南亚/拉美/中东/非洲）
  ├── 移动优先、信用卡渗透低、社交媒体渗透高
  ├── TikTok/Meta 触达远好于传统搜索（很多人"不搜直接刷"）
  ├── Google 效果打折（搜索习惯弱、广告技术水平低）
  └── DV360 覆盖有限（digi ads infrastructure 弱）

  中国大陆（特例）
  ├── 四大海外平台基本不可用
  ├── 需用巨量引擎/腾讯广告/百度/抖音信息流
  └── 海外知识库不适用，另案处理
```

**地区分配示意（同样是 $100K，两种市场）：**

| 地区 | Google | Meta | TikTok | DV360 | 说明 |
|------|:------:|:----:|:------:|:-----:|------|
| **北美成熟** | 40% | 30% | 15% | 15% | 搜索高意图为主 |
| **东南亚新兴** | 15% | 40% | 35% | 10% | 社交+短视频主导 |
| **拉美新兴** | 20% | 35% | 30% | 15% | 移动社交为主 |
| **中东** | 25% | 40% | 20% | 15% | 高净值+品牌兼顾 |

**地区决策核心变量（Checklist）：**

```
地区预算分配 Checklist
□ 该市场搜索广告的成熟度？（发达搜索→Google；弱搜索→社交）
□ 信用卡/支付渗透率？（低→需 TikTok Shop/本地闭环）
□ 语言/内容本地化能力？（决定 TikTok/Reels 素材成本）
□ 当地法规与数据合规？（GDPR/PIPL/本地隐私法）
□ 品牌 vs 效果优先级在该市场如何？
□ TikTok 在该市场是否可用/被限制？(部分地区曾被禁用风险)
```

#### 3.1.5 动态预算重分配算法（生产可落地）

静态分配表适合"期初"，但跨平台运营必须**按天/周动态重分配**。给出一段可用的 Python 参考实现（挂在数据仓库上跑）：

```python
"""
跨平台预算动态重分配器（示意实现）
输入：各平台 7 天 ROAS / 转化数据（来自统一事件模型）
输出：下一周期的预算分配建议（等边际回报原则 + 学习预算保底）
"""
from dataclasses import dataclass
from typing import Dict

@dataclass
class PlatformPerf:
    name: str
    budget: float          # 当前预算
    roas: float            # 7 天 ROAS
    conversions: int
    min_budget: float      # 平台最低门槛
    max_budget: float      # 平台消化上限

def allocate_budget(
    perfs: Dict[str, PlatformPerf],
    total_budget: float,
    learning_pool: float = 0.05,
) -> Dict[str, float]:
    """
    等边际回报 + 学习预算保底的分配。
    简化：以 ROAS 作为"单位预算回报"的代理，
          结合 learning_pool 保护新平台/新素材探索。
    """
    # 1. 预留学习预算（探索新平台/新素材）
    learning = total_budget * learning_pool
    effective = total_budget - learning

    # 2. 按当前 ROAS 加权分配（更高 ROAS 给更多预算）
    total_roas = sum(max(p.roas, 0.01) for p in perfs.values())
    raw = {
        name: effective * (max(p.roas, 0.01) / total_roas)
        for name, p in perfs.items()
    }

    # 3. 应用各平台上下限（保底 + 封顶）
    result: Dict[str, float] = {}
    for name, p in perfs.items():
        result[name] = min(max(raw[name], p.min_budget), p.max_budget)

    # 4. 归一化回 total_budget - learning
    total_alloc = sum(result.values())
    if total_alloc > 0:
        for name in result:
            result[name] *= (effective / total_alloc)

    # 5. learning budget 按需给新平台或测试组
    result["__learning_pool__"] = learning
    return result


if __name__ == "__main__":
    perfs = {
        "google":  PlatformPerf("google",  40000, 4.2, 1500, 2000, 45000),
        "meta":    PlatformPerf("meta",    30000, 3.1, 1200, 1500, 35000),
        "tiktok":  PlatformPerf("tiktok",  20000, 2.4, 800,  500,  25000),
        "dv360":   PlatformPerf("dv360",   10000, 1.6, 300,  3000, 12000),
    }
    alloc = allocate_budget(perfs, 100000)
    for k, v in alloc.items():
        print(f"{k:16s} -> ${v:,.0f}")
```

**分配原则（补充）：**

```
1. 等边际原则      —— 把预算从边际回报低的平台挪向高的，直至趋近相等。
2. 学习预算保底    —— 永远留 5% 用于新平台/新素材/新市场实验，避免短视。
3. 上下限约束      —— 尊重平台最低门槛（<门槛没意义）与消化上限。
4. 频度            —— 周维度重分配较稳；日维度看告警触发时再动。
5. 不要高频率大跳   —— 大比例重分配会让平台进入学习期，得不偿失。
```

#### 3.1.6 预算分配的常见陷阱

| 陷阱 | 表现 | 纠正 |
|------|------|------|
| 拍脑袋均分 | 四平台各 25% | 用等边际原则+ROAS 数据驱动 |
| 被单一平台报表绑架 | 平台报表好看就加预算 | 用统一事件模型+增量测试校准 |
| 忽略学习预算 | 从不投新渠道 | 预留 5%+ 学习池 |
| 无视最低门槛 | 预算分得太碎 | 设置 min budget 约束 |
| 频繁大调 | 预算在平台间大进大出 | 周维度小幅调整 |
| 只盯 ROAS 忽略品牌 | 品牌资产衰减 | 结合品牌健康度指标双轨评估 |

### 3.2 平台切换 / 迁移策略：从单一平台到多平台

很多团队是从"单平台（通常是 Google 或 Meta）"起步的。本篇给出从单平台平滑扩展为多平台的**路径、阶段、风险控制**。

#### 3.2.1 迁移路径总览：三步走

```
跨平台迁移三步走

  阶段一：单平台跑通（MVP）
  └── 在单一平台把转化、归因、素材、数据闭环跑通
      → 建立"基线 ROAS/CPA"（用于后续增量对照）

  阶段二：双平台验证（加第二个平台）
  └── 在验证 ROAS 的平台外，选"补充型"平台
      → 做增量测试，确认第二个平台带来的是增量而非蚕食
      → 迁移基建：统一 UTM、统一事件表、统一归因

  阶段三：多平台规模化
  └── 扩展到第 3、4 个平台 + 品牌平台
      → 建立预算分配引擎 + 动态重分配
      → 建立跨平台频控/去重/创意库
```

#### 3.2.2 扩展顺序建议（基于平台互补性）

不是随便加平台，而是按**互补性**扩展：

```
扩展顺序决策树

  我现在的平台是？
    │
    ├─ Google 起步（效果型）
    │   ├─ 下一步加 Meta  → 理由：Meta 承接兴趣+再营销，与搜索互补
    │   │     └─ 再下一步加 TikTok → 新品种草，年轻增量
    │   │           └─ 最后加大型品牌平台 DV360
    │   └─ 若 B2B → 加 LinkedIn（不在本四平台范围，但值得提）
    │
    ├─ Meta 起步
    │   ├─ 下一步加 Google Search → 理由：锁定高意图搜索，收割 Meta 种草
    │   └─ 再下一步加 TikTok/DV360
    │
    ├─ TikTok 起步（新品种草）
    │   ├─ 下一步加 Google Search → 承接搜索意图收割
    │   └─ 再下一步加 Meta → 再营销放大
    │
    └─ DV360 起步（品牌）
        ├─ 下一步加 Search → 收割品牌声量带来的搜索
        └─ 再下一步加 Meta/TikTok → 兴趣与种草放大

  ⚠ 通用原则：先补"漏斗的另一端"（效果端↔品牌端互补），
    不要同时加两个同质平台（如同时加 Google 和 Bing，增益有限）。
```

#### 3.2.3 增量验证：如何确认"新平台真的带来增量"

每次加一个新平台，都应该先做**增量测试**，防止出现"越加越亏"的假象。

```
新平台增量测试流程

  Step 1 基线：单平台期记录 4 周的转化/ROAS 基线
  Step 2 分组：把目标人群/地域随机分 Test(开新平台) vs Control(维持原样)
  Step 3 运行：Test 组在两个平台投，Control 组只在原平台投，跑 2~4 周
  Step 4 对比：
      增量转化 = Test 转化 − Control 转化（排除自然波动）
      增量 ROAS = 增量收入 / 新平台花费
  Step 5 决策：
      增量 ROAS > 阈值（如 1.5x）→ 正式扩展
      增量 ROAS ≈ 0 或 <1 → 新平台只是在"抢原有漏斗"，暂停
```

```python
# 增量测试显著性判断（简化 t 检验示意）
from scipy import stats

def incrementality_test(test_conv, control_conv, alpha=0.05):
    """
    对比 Test 组与 Control 组转化是否显著不同。
    输入为两组转化率样本（如按天的转化率序列）。
    返回 p 值与结论。
    """
    t, p = stats.ttest_ind(test_conv, control_conv)
    significant = p < alpha
    return {
        "t": t,
        "p": p,
        "test_mean": sum(test_conv) / len(test_conv),
        "control_mean": sum(control_conv) / len(control_conv),
        "significant": significant,
        "conclusion": "存在显著增量" if significant else "差异不显著，谨慎扩展",
    }

# 示例：Test（开新平台）按天转化率 vs Control（原平台）
result = incrementality_test(
    test_conv=[3.2, 3.5, 3.8, 3.6, 3.9, 4.1],
    control_conv=[3.0, 2.9, 3.1, 3.0, 3.2, 3.1],
)
print(result)
```

#### 3.2.4 迁移期间的基建改造 Checklist

```
跨平台迁移基建改造 Checklist（关键，容易漏）

□ UTM 规范统一 —— utm_source/medium/campaign/content/term 五件套
□ 统一事件表 —— 四平台事件归一（见 2.7 节的 events_staging 表）
□ 统一归因口径 —— 决定用 last click / data-driven / MMM 作为"决策口径"
□ 第一方 ID 打通 —— 至少能拼 cookie-level / device-level 跨平台去重
□ 频控工具 —— 跨平台频控（CM360/ADH 或自建）
□ 创意资产管理 —— 统一创意库，记录每个素材在各平台的版本
□ 报表看板 —— 跨平台统一看板，不再分平台看孤岛数据
□ 告警 —— 各平台 CPA/ROAS 异常告警统一收口
□ 权限与审批 —— 多平台账户与权限矩阵（见 3.3 组织适配）
□ 预算审批流 —— 动态重分配有审批与回滚机制
```

#### 3.2.5 Google → Meta → TikTok 迁移实战案例

**案例背景：** 某 DTC 美妆品牌，原只投 Google（Search + PMax），月预算 $30K，ROAS 稳定在 3.8x。增长见顶，希望扩展。

```
阶段一：Google 单平台（基线）
  ┌──────────────────────────────────┐
  │ Google Search  40%  ROAS 5.2x     │
  │ Google PMax    60%  ROAS 3.2x     │
  │ 合计           $30K ROAS 3.8x     │
  └──────────────────────────────────┘

阶段二：加 Meta（增量验证，2 周）
  ├── Test 组：Google+Meta  控制组：仅 Google
  ├── 结果：Meta 带来 18% 增量收入，增量 ROAS 3.1x
  └── 决策：正式扩展 Meta

阶段三：Google + Meta 双平台（月$60K）
  ├── Google Search/PMax   $33K  优化收割
  ├── Meta Advantage+      $27K  再营销 + 相似人群
  └── 统一 UTM + BigQuery 归因，发现真实贡献
       Google 45% / Meta 40% / 未归因 15%

阶段四：加 TikTok（新品种草，年轻客群）
  ├── 用 Spark Ads 放大达人爆款视频
  ├── 冷启动 4 周，目标新客占比提升
  └── 评估：TikTok 新客占比 62%，补充 Google/Meta 老客为主的结构

阶段五：品牌放大（若预算够，加 DV360）
  ├── 大促前启动品牌展示 + 再营销
  └── 用 ADH 做频控，避免和 Meta/TikTok 重复触达
```

**案例经验总结：**

```
1. 先补互补端：效果(G) → 兴趣/再营销(M) → 种草(T) → 品牌(D)
2. 每个平台加之前做增量验证，防止"假增量"
3. 基建先行：UTM/统一数据/归因口径，否则无法比较
4. 冷启动要耐心：新平台 2~6 周学习期，别过早下结论
5. 用"新客占比"而非只看 ROAS 评估平台价值
```

#### 3.2.6 平台下撤 / 关停策略

迁移不只是"加平台"，有时也要"撤平台"。

```
平台下撤决策流程

  触发信号：
  ├── 连续 4 周，某平台 ROAS 显著低于全渠道且无恢复迹象
  ├── 该平台与另一平台"纯粹蚕食"（增量 ROAS < 1）
  ├── 政策/合规风险（如平台被禁、隐私新规）
  └── 平台效率结构性下降（CPM 疯涨、创意全面疲劳）

  下撤步骤：
  1. 逐步降价 → 观察是否影响整体量（评估它到底贡献多少增量）
  2. 降预算百分比（如 50%%）→ 观察全渠道转化变化
  3. 若全渠道转化基本不变 → 说明其是"蚕食型"，可安全撤回
  4. 停投前半量，把预算移到效率最高的平台
  5. 复盘并记录原因（供未来策略决策）
```

```shell
# 预算迁移的"止血"脚本示意（把某平台预算部分切给最优平台）
# 实际生产中用各平台 API / Bulk File 执行
PLATFORM_TO_REDUCE="tiktok"
REDUCE_PCT=50
TARGET_PLATFORM="meta"

# 读取当前预算（示意）
CURRENT=$(python3 -c "
import json
d=json.load(open('budget.json'))
print(d['$PLATFORM_TO_REDUCE'])
")
REDUCED=$((CURRENT * (100 - REDUCE_PCT) / 100))
echo "将 $PLATFORM_TO_REDUCE 预算从 $CURRENT 降到 $REDUCED，差额划给 $TARGET_PLATFORM"
```

#### 3.2.7 反向案例：盲目多平台扩张的教训

```
反例：某电商品牌"四平台全上"踩坑

  行为：一上来四平台全开，每平台预算分得很碎（各 8%~12%）
  结果：
  ├── 四个平台都在"冷启动 + 学习期"，没有一个跑过学习期
  ├── 数据分散，无法判断哪个平台有效
  ├── 统一归因没做，四平台报表各自为政，CEO 看到"四份都好看的报表"
  ├── 实际上总 ROAS 反而低于原来单平台
  └── 18% 预算被各平台学习期"试错"烧掉

  教训：
  1. 从单平台到多平台要"逐个加、验证后再加"
  2. 预算分太碎会让每个平台都失败
  3. 学习预算单独划，不要让探索挤占主力预算
```

### 3.3 组织架构适配：小 / 中 / 大团队

跨平台投放的最终执行者是"人 + 组织"。不同规模的团队，平台运营的组织方式完全不同。

#### 3.3.1 组织规模三维度

我们按团队规模分成三档：**小团队、中团队、大团队**，各对应不同的平台组合、角色分工、工具链、汇报结构。

```
组织规模分档

  小团队 (1~5人)     中团队 (6~20人)     大团队 (20人+)
  一人多岗            角色初分化            专业角色专职
  依赖自动化           专门优化师            平台专家 + 数据科学家
  SMB/早期品牌          成长型品牌             集团/大品牌
```

#### 3.3.2 小团队（1~5 人）：用自动化扛全局

```text
小团队组织架构（示意）

  创始人 / 市场负责人（1 人，战略+审批）
    │
    ├── 投放运营（1~2 人）—— 兼管 Google+Meta+TikTok
    │      用自动化产品扛量：PMax / Advantage+ / Smart+
    │      依赖平台黑盒自动化，少手工调优
    │
    └── 数据分析/外包（兼职）—— 统一报表 + 预算分配
          用现成工具（Looker/Supermetrics/Sheet 自动拉数）

  适用平台：
  ├── Google (Search + PMax)   ← 自动化主力
  ├── Meta (Advantage+)        ← 自动化主力
  ├── TikTok (Smart+/Spark)    ← 若有新品种草需求
  └── DV360：不推荐单独上手（人力成本太高），
      除非有企业级账号且愿意外包给代理商
```

**小团队平台策略要点：**

```
小团队策略
├── 人少 → 依赖自动化产品为主，减少手工
├── 每平台用"主力自动化 campaign"，靠算法，不靠人肉
├── 数据层：用托管工具（Supermetrics 拉进 Sheets/BigQuery）
├── 预算分配：用"固定比例 + 周度人工校准"，不搞复杂算法
└── DV360：小团队通常跳过，或交给媒介代理商(PubMatic等Partner)
```

#### 3.3.3 中团队（6~20 人）：角色初分化 + 数据驱动

```text
中团队组织架构（示意）

  市场负责人 / Performance Lead（1 人，跨渠道统筹）
    │
    ├── Google 优化师 (1~2人)   —— Search/PMax/YouTube
    ├── Meta 优化师 (1人)       —— Feed/Reels/Advantage+
    ├── TikTok 优化师 (1人)     —— In-Feed/Spark/Shop
    ├── 数据分析师 (1~2人)      —— 统一归因/报表/预算模型
    ├── 创意/素材 (1人+外包)    —— 各平台专属素材 + A/B
    └── （可选）媒介人员（DV360 外包或专人 0.5人）

  特点：
  ├── 按平台分"渠道 Owner"，但受"跨渠道统筹人"管理
  ├── 有专门数据分析师，能跑统一归因与预算分配
  ├── DV360 可以开始自营，但通常配"媒介经理"或借助 Partner
  └── 周例会：跨渠道复盘 + 预算重分配决策
```

**中团队关键机制：**

```
中团队跨渠道治理机制
├── 渠道 Owner 制：每人对某平台预算/ROAS 负责
├── 统一数据底座：数据仓库 + 统一归因口径（防止各自为政）
├── 周度预算重分配会：用数据驱动，而非拍脑袋
├── 素材共享池：创意由专人管理，跨平台复用按格式适配
└── 权限分级：owner 能改本平台，统筹人能跨平台/批预算
```

```python
# 中团队周度跨渠道复盘模板（数据输入示例）
weekly_review = [
    {
        "platform": "google",
        "spend": 45000,
        "revenue": 189000,
        "roas": 4.2,
        "conversions": 1200,
        "cpa": 37.5,
        "owner": "Alice",
        "action": "PMax 提高目标ROAS 0.2，Search 补充长尾词",
    },
    {
        "platform": "meta",
        "spend": 34000,
        "revenue": 105400,
        "roas": 3.1,
        "conversions": 860,
        "cpa": 39.5,
        "owner": "Bob",
        "action": "新增 3 条 Reels 素材，刷新疲劳素材",
    },
    {
        "platform": "tiktok",
        "spend": 21000,
        "revenue": 50400,
        "roas": 2.4,
        "conversions": 490,
        "cpa": 42.9,
        "owner": "Carol",
        "action": "放大跑量 Spark Ad，替换低效 In-Feed",
    },
]
for p in weekly_review:
    print(f"{p['platform']:8s} 预算${p['spend']:>7,} "
          f"营收${p['revenue']:>8,} ROAS{p['roas']:.1f} | {p['action']}")
```

#### 3.3.4 大团队（20 人+）：专业分工 + 数据科学 + 平台专家

```text
大团队组织架构（示意）

  首席营销官 / Media Director（战略层）
    │
    ├── 效果营销团队 (Performance)
    │   ├── Google 专家（Search/PMax/YouTube 细分）
    │   ├── Meta 专家（Advantage+/Reels/目录）
    │   ├── TikTok 专家（Spark/Shop/达人管理）
    │   └── 移动增长专家（App/UAC/SKAd）
    │
    ├── 品牌与程序化团队 (Brand & Programmatic)
    │   └── DV360 媒体经理 + 品牌安全 + 交易管理
    │
    ├── 数据科学团队 (Data Science)
    │   ├── 归因建模 (MTA/MMM)
    │   ├── 增量实验 (incrementality)
    │   ├── 预算优化算法
    │   └── 数据工程（事件表/仓库/管道）
    │
    ├── 创意团队 (Creative Studio)
    │   ├── 各平台素材定制
    │   ├── 素材管理平台 (DAM)
    │   └── 素材疲劳/A-B 测试
    │
    └── 运营与合规 (Ops & Compliance)
        ├── 账户/权限管理
        ├── 财务核对 (reconciliation)
        └── 隐私合规 (GDPR/PIPL/审核)

  特点：
  ├── 平台专家专职化：每人只盯一个平台的深度
  ├── 数据科学驱动决策：统一归因 + MMM 分析
  ├── DV360 独立成团队
  └── 关键汇报：Media Director 统一看跨渠道健康度
```

**大团队跨渠道治理核心：**

```
大团队核心治理
├── 平台专家 → 单平台深度优化（不要跨平台一把抓）
├── 数据科学家 → 独立于渠道，提供"中立"的跨平台评估
├── 预算决策 → 上移到 Media Director，用算法建议 + 人工拍板
├── 数据中台 → 全平台事件统一，唯一事实源 (Single Source of Truth)
├── 素材资产化 → DAM 统一管理，跨平台按格式分发
└── 双轨绩效考核 → 既有单平台 KPI，也有全渠道健康度
```

#### 3.3.5 三种团队规模对比表

| 维度 | 小团队 | 中团队 | 大团队 |
|------|--------|--------|--------|
| 人数 | 1~5 | 6~20 | 20+ |
| 是否自营 DV360 | 否（外包） | 可（配媒介经理） | 是（独立团队） |
| 自动化依赖 | 极高 | 高 | 中（专业人调优） |
| 数据能力 | 托管工具 | 数据分析师 | 数据科学团队 |
| 归因 | 平台报表 | 统一归因 | MTA + MMM + 增量 |
| 预算分配 | 固定比例+人工 | 数据驱动+周度 | 算法 + 决策层 |
| 素材 | 通用复用 | 专人适配 | 平台定制化 + DAM |
| 决策权 | 创始人 | 统筹人 | Media Director |

#### 3.3.6 组织/权限矩阵（跨平台账户治理）

```
平台账户权限矩阵（原则）

  权限层级：
  L1 只读       —— 只看报表，不能改
  L2 投放操作    —— 能建/改广告，不能动预算上限
  L3 预算审批    —— 能改预算，需记录
  L4 管理员      —— 账户设置/人员管理

  建议矩阵：
  角色          Google  Meta  TikTok  DV360   报表
  创始人/总监    L3     L3     L3     L3      L1
  渠道 Owner    L2     L2     L2     L1      L1
  优化师        L2     L2     L2     L1      L1
  数据分析师    L1     L1     L1     L1      L3
  财务          L1     L1     L1     L1      L1
  合规/审计     L1     L1     L1     L1      L1

  原则：
  ├── 最小权限：默认只读，按需提升
  ├── 预算变更留痕（audit trail）
  ├── 离职/转岗及时回收权限
  └── 用 MFA/二次验证保护管理员账户
```

#### 3.3.7 组织演进路线图

```
组织演进路线图: 小 → 中 → 大

  小团队(MVP)
   │  一人多岗 + 自动化扛量 + 外包DV360
   ▼
  中团队(成长)
   │  渠道Owner化 + 数据分析师 + 统一归因 + DV360入局
   ▼
  大团队(成熟)
   │  平台专家专职 + 数据科学团队 + 品牌程序化团队 + 中台

  演进触发点：
  ├── 预算跨过门槛（如月$50K+）→ 需要专职
  ├── 平台数量 ≥3 → 需要统一归因与跨渠道统筹
  ├── 开始做品牌(需DV360) → 需要程序化团队
  ├── 数据复杂度高 → 需要数据科学
  └── 合规/审计需求 → 需要合规岗位
```

### 3.4 真实跨平台投放场景案例

本节提供可完整照做的三个实战场景，覆盖"新品冷启、成熟期扩张、品牌+效果整合"三类典型需求。

#### 3.4.1 场景 A：新品冷启动（DTC 品牌新品上市）

```
场景：某 DTC 咖啡机品牌推新品，月预算 $50K，目标 3 个月建立认知并起量

阶段 1（第 1-4 周）：认知 + 种草
  ├── TikTok：Spark Ads 让 20 位咖啡达人种草，$12K（24%）
  │     KPI：播放量、互动、新客占比
  ├── Meta：品牌+兴趣+Reels 扩大触达，$10K（20%）
  │     KPI：Reach、VCR、互动
  └── DV360（若有）：品牌展示+CTV 造势，$5K（10%）

阶段 2（第 5-10 周）：承接 + 收割
  ├── Google Search：品牌词+咖啡机品类词，$8K（16%）
  ├── Google PMax：全渠道收割商品，$7K（14%）
  └── Meta 再营销：浏览未购人群，$5K（10%）

阶段 3（第 11-12 周）：结合品牌 + 效果
  ├── 大促预热：DV360 品牌提升 + 全平台再营销
  └── 把种子期爆款素材全平台复用（注意格式适配）

分配演进：
  认知期  品牌端 54% / 效果端 46%
  收割期  品牌端 10% / 效果端 90%
  大促期  品牌端 25% / 效果端 75%
```

#### 3.4.2 场景 B：成熟期跨平台 ROAS 优化（电商月 $100K）

```
场景：成熟 DTC 电商，四平台已开，但总 ROAS 2.1x 低于目标 3x，需挖增量

诊断（统一数据层）：
  ├── Google PMax 占了 40% 预算但最近 ROAS 掉到 2.5x
  ├── 发现 PMax"抢收"了很多本属 Search 的品牌意图
  ├── TikTok 新客占比高但主页承接弱，加购流失
  └── Meta 与 TikTok 人群重叠 45%，频控不足

优化动作：
  1. 拆分品牌专属 Campaign：品牌词单独跑（保护高意图）
  2. 限制 PMax 范围/用 H-iMax，避免吸走 Search 品牌流量
  3. TikTok 加"落地页优化 + 深度链接"，提升加购→下单
  4. 跨平台频控：CM360/ADH 做去重，Meta 与 TikTok 重叠低频
  5. 素材疲劳：疲劳平台(CTR降30%)素材换到新鲜人群平台
  6. 重分配：把 TikTok 低效 In-Feed 预算挪到 Spark 达人 + PMax

结果（8 周）：
  ├── 总 ROAS 从 2.1x → 3.2x
  ├── PMax 抢量问题缓解，Search 品牌 ROAS 恢复 5x+
  ├── 频控后 CPM 综合下降 12%
  └── 新客占比从 38% 提升到 46%
```

#### 3.4.3 场景 C：品牌 + 效果整合（快消大品牌）

```
场景：某快消大品牌，季度预算 $1M，需在"品牌声量"与"效果转化"间平衡

预算框架（季度）：
  ├── 品牌端（$600K / 60%）：DV360 + YouTube + TikTok TopView
  │     KPI：Reach, VCR, Brand Lift, Share of Voice
  ├── 效果端（$300K / 30%）：Google Search/PMax + Meta 再营销
  │     KPI：ROAS, CPA
  └── 测试端（$100K / 10%）：新品实验 + 增量测试

品牌↔效果联动：
  ├── DV360/YouTube 造势后，品牌搜索量上升 → Search 收割
  ├── 用增量测试量化品牌广告对 Search 转化的提升
  ├── 频控保证：同一用户品牌端 + 效果端加起来不超阈值
  └── ADH 打通品牌曝光与转化，做真实全漏斗归因

汇报：
  ├── Media Director 统一看"全渠道健康度"
  ├── 品牌与效果两个 KPI 分别汇报，避免互相打架
  └── 季度复盘 + 下季度重分配
```

### 3.5 跨平台运营的工程化：用代码批量操作四平台

跨平台运营到规模后，手工操作不可行。本节给出**用各平台API做批量操作与统一巡检**的工程范式。

#### 3.5.1 统一巡检框架

```
跨平台每日巡检（Mock 流程）

  每天 9:00 触发
    │
    ├── Google Ads API   拉取 Search/PMax 昨日花费/转化/ROAS
    ├── Meta API         拉取 Advantage+ 花费/转化/ROAS
    ├── TikTok API       拉取 In-Feed/Spark 花费/转化
    ├── DV360 API        拉取 Line Item 花费/Reach/VCR
    │
    ▼
  统一写入 events/metrics 表（BigQuery）
    │
    ▼
  告警引擎检查：
  ├── ROAS < 阈值 → 告警
  ├── CPA > 阈值 → 告警
  ├── 预算超支 → 告警
  ├── 素材疲劳（CTR下降） → 提示
  └── 频率超限 → 提示
    │
    ▼
  收口到 Slack/飞书 + 看板
```

#### 3.5.2 （示例）用 Google Ads API 拉取 PMax 效果

以下为**示意代码**（需在真实环境配 OAuth 与配置）：

```python
# 示意：拉取 Google 广告系列昨日指标（依赖 google-ads-api 客户端）
# from google.ads.googleads.client import GoogleAdsClient

def fetch_google_performance(config, customer_id, days=1):
    """
    示意函数：拉取指定客户账户近几日的花费/转化/ROAS。
    生产环境需初始化 client 并处理分页/限流。
    """
    client = GoogleAdsClient.load_from_dict(config)
    ga_service = client.get_service("GoogleAdsService")

    query = f"""
        SELECT
          campaign.id,
          campaign.name,
          campaign.status,
          metrics.cost_micros,
          metrics.conversions,
          metrics.conversions_value
        FROM campaign
        WHERE segments.date DURING LAST_{days}_DAYS
          AND campaign.status != 'REMOVED'
    """
    rows = ga_service.search(customer_id=customer_id, query=query)
    out = []
    for row in rows:
        cost_usd = row.metrics.cost_micros / 1_000_000
        revenue = row.metrics.conversions_value
        conv = row.metrics.conversions
        out.append({
            "platform": "google",
            "campaign": row.campaign.name,
            "status": row.campaign.status.name,
            "spend": cost_usd,
            "conversions": conv,
            "revenue": revenue,
            "roas": (revenue / cost_usd) if cost_usd else 0,
        })
    return out
```

#### 3.5.3 （示例）用 Meta Marketing API 拉取 Advantage+ 数据

```python
# 示意：Meta 账户级每日汇总（需 access_token 与 ad_account_id）
# import requests

def fetch_meta_daily(ad_account_id, access_token, date_preset="yesterday"):
    """
    示意：拉取 Meta 广告账户昨日花费与购买。
    生产环境建议用 Marketing API SDK 并处理分页。
    """
    url = (
        f"https://graph.facebook.com/v19.0/{ad_account_id}/insights"
        f"?fields=spend,purchase_roas,actions"
        f"&date_preset={date_preset}"
        f"&access_token={access_token}"
    )
    # resp = requests.get(url).json()
    # 返回示意结构
    return {
        "platform": "meta",
        "spend": 34000.0,
        "purchase_roas": 3.1,
        "purchases": 860,
        "date_preset": date_preset,
    }
```

#### 3.5.4 （示例）TikTok Ad Manager API 拉取效果

```python
# 示意：TikTok 报表（需 advertiser_id 与 access_token）
# import requests

def fetch_tiktok_report(advertiser_id, access_token, report_date="2026-08-01"):
    """
    示意：TikTok 指定日期广告效果。先创建报表任务再轮询获取（TikTok 为异步）。
    """
    headers = {"Access-Token": access_token, "Content-Type": "application/json"}
    # 1. 创建报表任务
    create_payload = {
        "advertiser_id": advertiser_id,
        "report_type": "BASIC",
        "dimensions": ["stat_time_day", "ad_id"],
        "data_level": "AUCTION_AD",
        "start_date": report_date,
        "end_date": report_date,
        "metrics": ["spend", "conversion", "complete_payment_roas"],
    }
    # resp = requests.post(
    #     "https://business-api.tiktok.com/open_api/v1.3/report/integrated/get",
    #     headers=headers, json=create_payload).json()
    # 生产环境：异步任务需轮询 report 结果
    return {
        "platform": "tiktok",
        "spend": 21000.0,
        "conversion": 490,
        "roas": 2.4,
        "report_date": report_date,
    }
```

#### 3.5.5 （示例）DV360 API 拉取 IO/LineItem 花费

```python
# 示意：DV360 通过 Bulk/API 拉取投放数据（依赖 Google Ads Data Transfer / DisplayVideoAPI）
# from google.ads.googleads.util import ...  (DV360 用 DisplayVideo API)

def fetch_dv360_line_item(config, partner_id, days=7):
    """
    示意：拉取 DV360 各 Line Item 花费与展示。
    生产环境需用 DisplayVideo API 的 GoogleAdsDataTransfer 或 LineItems.list。
    """
    # 读取 Partner 下所有 IO 与 LineItem 的花费指标
    return [
        {
            "platform": "dv360",
            "line_item": "Brand_Awareness_Q3",
            "spend": 9500.0,
            "impressions": 2500000,
            "clicks": 30000,
            "ctr": 0.012,
            "vcr": 0.65,
        },
        {
            "platform": "dv360",
            "line_item": "Retargeting_Display",
            "spend": 5000.0,
            "impressions": 1200000,
            "clicks": 18000,
            "ctr": 0.015,
            "vcr": 0.40,
        },
    ]
```

#### 3.5.6 统一落库（BigQuery insert schema）

```sql
-- 跨平台每日指标落地表（metrics_daily）
CREATE OR REPLACE TABLE `your_project.ads.metrics_daily` (
  metric_date     DATE,
  platform        STRING,          -- google/meta/tiktok/dv360
  campaign_id     STRING,
  campaign_name   STRING,
  spend_usd       FLOAT64,
  impressions     INT64,
  clicks          INT64,
  conversions     FLOAT64,         -- 统一口径的转化数
  revenue_usd     FLOAT64,
  roas            FLOAT64,
  new_customers   INT64,           -- 新客数（可选）
  loaded_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
)
PARTITION BY metric_date;
```

```sql
-- 统一跨平台日报（四平台并排对比）
SELECT
  metric_date,
  platform,
  SUM(spend_usd)   AS spend,
  SUM(revenue_usd) AS revenue,
  SAFE_DIVIDE(SUM(revenue_usd), SUM(spend_usd)) AS roas,
  SUM(conversions) AS conversions
FROM `your_project.ads.metrics_daily`
WHERE metric_date = CURRENT_DATE() - 1
GROUP BY metric_date, platform
ORDER BY roas DESC;
```

#### 3.5.7 跨平台告警规则（生产建议）

```
告警规则（经验阈值，按行业调整）

  ├── ROAS 周线漏斗：ROAS 环比跌 >20% 连续 3 天 → P1 告警
  ├── CPA 单日超目标 1.5x → P2 告警
  ├── 预算花费进度：月初过半已花 80% → P2 告警（避免预算前紧后松）
  ├── 素材疲劳：某素材 CTR 降 30% 持续 3 天 → P3 提示
  ├── 频控超标：单一用户平均触达 > 8 次/天 → P3 提示
  ├── 转化事件流中断：某平台转化上报停机 > 2h → P1 告警
  └── 归因异常：三平台归因合计 > 130% → P2 告警（归因膨胀）
```

#### 3.5.8 自动化执行引擎（可落地的控制循环）

```
跨平台"感知-决策-执行"闭环

  感知层 Sensory
  └── 拉取四平台指标 → 统一落库（metrics_daily）
        │
  决策层 Decision
  └── 规则引擎 + 预算重分配算法（见 3.1.5）
        │
  执行层 Actuation
  └── 调用各平台 API 修改预算/暂停/启动物料
        │
  校验层 Verify
  └── 校验 API 是否生效、回滚机制
```

```python
# 控制循环简化骨架（决策可用 3.1.5 的 allocate_budget）
def run_cross_platform_control_cycle(perfs, total_budget):
    # 感知
    metrics = {p.name: p for p in perfs}
    # 决策
    alloc = allocate_budget(metrics, total_budget, learning_pool=0.05)
    # 执行（示意：打印要写入各平台 API 的预算；生产用各平台 update API）
    for name, budget in alloc.items():
        if name == "__learning_pool__":
            continue
        print(f"[ACTUATE] set {name.upper()} daily_budget = ${budget:,.0f}")
    # 校验
    print("[VERIFY] budget allocation validated, changes logged")
    return alloc

perfs = [
    PlatformPerf("google", 40000, 4.2, 1500, 2000, 45000),
    PlatformPerf("meta",   30000, 3.1, 1200, 1500, 35000),
    PlatformPerf("tiktok", 20000, 2.4, 800,  500,  25000),
    PlatformPerf("dv360",  10000, 1.6, 300,  3000, 12000),
]
run_cross_platform_control_cycle(perfs, 100000)
```

### 3.6 跨平台测量与 MMM 建模

#### 3.6.1 为什么单平台数据不够决定预算

平台报表只能告诉你"在它自己视角下的表现"，跨平台决策必须用**第一方数据 + 统计模型**校准。

```
测量分层金字塔

  最上（战略）   MMM（营销组合模型）—— 品牌+媒体宏观贡献
                   │ 季度/月度粒度
  中层           MTA（多触点归因）—— 用户级路径贡献
                   │ 周/日粒度
  最下（执行）     平台数据 + 统一事件 —— 日常优化
                （分平台前台指标 + 统一 Daily 报表）
```

#### 3.6.2 MMM 建模原理与跨平台应用

MMM（Marketing Mix Modeling）用**历史媒体花费 + 销售数据**回归估计各媒体贡献：

```
MMM 基本形式（对数/饱和模型）

  Sales_t = Base
            + β_google · f(spend_google_t, saturation)
            + β_meta    · f(spend_meta_t, saturation)
            + β_tiktok  · f(spend_tiktok_t, saturation)
            + β_dv360   · f(spend_dv360_t, saturation)
            + γ · control（季节性/价格/促销/竞品）
            + ε

  每种媒体常用饱和/衰减函数（Adstock + Diminishing Returns）：
  f(spend) = α · spend / (1 + β · spend)         （Michaelis-Menten 型）
  f(spend) = α · (1 - e^{-β·spend})              （指数饱和型）

  Adstock(广告记忆延续)：
  transform(t) = gamma · raw(t) + (1 - gamma) · transform(t-1)
```

```python
# MMM 简化示例：线性 + 饱和项 拟合（示意，生产用 statsmodels/pymc）
import numpy as np
import statsmodels.api as sm

def prepare_adstock(x, gamma=0.4):
    """广告记忆延续（Adstock）变换"""
    y = np.zeros_like(x, dtype=float)
    carry = 0.0
    for i, v in enumerate(x):
        carry = gamma * v + (1 - gamma) * carry
        y[i] = carry
    return y

def saturate(x, alpha=1.0, beta=1.0):
    """饱和（Diminishing Returns）：alpha*x/(1+beta*x)"""
    return alpha * x / (1 + beta * x)

# 示意数据：四个平台的周花费 + 销售
# spend_df 含 google_spend, meta_spend, tiktok_spend, dv360_spend, sales
# features = np.column_stack([
#     saturate(prepare_adstock(spend_df.google_spend)),
#     saturate(prepare_adstock(spend_df.meta_spend)),
#     saturate(prepare_adstock(spend_df.tiktok_spend)),
#     saturate(prepare_adstock(spend_df.dv360_spend)),
#     spend_df.seasonality,
# ])
# model = sm.OLS(spend_df.sales, sm.add_constant(features)).fit()
# print(model.summary())
```

**MMM 对跨平台战略的价值：**

```
MMM 输出的决策价值
├── 各平台"增量弹性"（哪个平台再多花一元最划算）
├── 饱和拐点（在哪个预算水平边际回报归零 → 该平台封顶）
├── 品牌与效果的结构性贡献
├── 进行"预算重分配模拟"（What-if：把 20% 从 A 挪到 B，销售额会怎样变化）
└── 为按季度预算分配提供科学依据
```

```
MMM 在跨平台流程中的位置

  Metrics_daily(平台数据)  → 周度

  MMM 模型（季度校准） → 季度预算框架

  增量实验（年度 1~2 轮）→ 校准 MMM 参数/验证
  ─────────────────────────────────
  三者汇合 → 形成"科学决策闭环"
```

#### 3.6.3 MTA（多触点归因）与跨平台路径

MTA 用用户点击/曝光序列归属转化。这是"用户路径级"的跨平台分析。

```sql
-- MTA 输入：用户路径表（拼装自 events 表）
-- 每行 = 一个用户的转化路径（按时间排序的触点序列）
CREATE OR REPLACE TABLE `your_project.ads.user_paths` AS
WITH clicks AS (
  SELECT
    user_id,
    event_ts,
    REGEXP_EXTRACT(utm_source, '[^/]+') AS source,
    ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY event_ts) AS seq
  FROM `your_project.ads.events_staging`
  WHERE event_type = 'click'
),
paths AS (
  SELECT
    user_id,
    STRING_AGG(source, ' > ' ORDER BY event_ts) AS path
  FROM clicks
  GROUP BY user_id
)
SELECT * FROM paths;
```

```sql
-- 常见路径频次统计：哪些"跨平台路径"转化最多
SELECT
  path,
  COUNT(*) AS conversions
FROM `your_project.ads.conversions_with_path`   -- 带回转化标记的路径表
GROUP BY path
ORDER BY conversions DESC
LIMIT 20;
```

**MTA 对跨平台战略的价值：** 它告诉你"真实的用户路径长什么样"。例如发现"Google 搜索 → Meta 再营销 → TikTok 种草 → 下单"是高转化路径，就可以针对性地设计漏斗（让四个平台各司其职）。

#### 3.6.4 测量结论如何回流到预算决策

```
测量 → 预算 回流闭环

  1. MMM 输出各平台增量弹性 e_i
  2. 归因输出各平台在成交路径中的出现率
  3. 增量实验验证关键分歧点
  4. 综合 → 调整各平台"权重 w_i"（3.1.1 中的效用权重）
  5. 权重进入 allocate_budget → 周度重分配
  6. 季度重新校准权重
```

### 3.7 跨平台创意与素材管理

#### 3.7.1 创意格式适配矩阵

同一创意策略跨平台落地，必须做格式适配，否则素材会被裁剪/压字幕/低互动。

| 维度 | Google | Meta | TikTok | DV360 |
|------|--------|------|--------|-------|
| 主素材格式 | 横版视频/图片/文字+feed | 方图+9:16 Reels | 9:16 竖版原生 | 16:9 横版视频/展示 |
| 视频时长偏好 | 15s~2min | 15~30s Reels/更长 feed | 9~30s 原生 | 15~30s 品牌视频 |
| 字幕 | 可不带 | 建议带 | 必带（静音观看多） | 品牌样式 |
| 音乐 | 弱 | 中 | 强（平台音乐库） | 品牌音乐 |
| 互动要素 | 弱 | 中（CTA） | 强（评论/特效/挑战） | 弱（品牌曝光） |
| 落地页 | 深度链接 | 站内/落地页 | TikTok Shop/落地 | 品牌站 |

```
素材创造与分发流程

  Brand Creative Brief（品牌创意简报）
       │
       ▼
  基础素材库（通用概念/产品图/视频片段）＝ Master
       │
       ├── 适配 Google：横版 16:9 + 文字叠加 + 落地页
       ├── 适配 Meta：方图 1:1 / 9:16 Reels + CTA
       ├── 适配 TikTok：9:16 原生 + 音乐 + 字幕 + Spark 达人版
       └── 适配 DV360：16:9 品牌安全合规版
       │
       ▼
  各平台 Campaign 内做 A/B（大标题/素材/CTA 变体）
```

#### 3.7.2 素材疲劳的跨平台管理

```
素材疲劳生命周期管理（跨平台）

  Phase 1 新鲜（0~1 周）：跑量测试，观察 CTR
  Phase 2 上升（1~3 周）：达到了峰值 CTR，放量
  Phase 3 衰退（3~6 周）：CTR 下降，降频/换人群
  Phase 4 轮换（6 周+）：从疲劳平台下线，按需试新平台/压仓

  跨平台复用规则：
  ├── 同一视觉在不同平台的"新鲜期"不同（平台人群池不同）
  ├── 但重叠用户会"串平台疲劳"→ 需要跨平台频控
  └── 素材库记录每个素材的：平台、版本、上线日、当前阶段
```

```python
# 素材疲劳检测（读统一创意库表现）
def detect_creative_fatigue(creative_history, window_days=3, ctr_drop_pct=0.30):
    """
    输入：某个素材每日表现序列 [{date, ctr, cpm}]
    输出：是否疲劳（CTR 较峰值下降超过阈值且持续窗口）
    """
    peak_ctr = max(h["ctr"] for h in creative_history)
    recent = creative_history[-window_days:]
    if not recent or peak_ctr == 0:
        return False
    avg_recent = sum(h["ctr"] for h in recent) / len(recent)
    dropped = (peak_ctr - avg_recent) / peak_ctr
    return {
        "fatigued": dropped > ctr_drop_pct,
        "ctr_drop_pct": round(dropped, 3),
        "peak_ctr": peak_ctr,
        "avg_recent_ctr": round(avg_recent, 5),
    }

# 示例
creative_history = [
    {"date": f"2026-08-{d:02d}", "ctr": ctr, "cpm": 5 + (8 - d)}
    for d, ctr in [(1, 0.030), (2, 0.028), (3, 0.021), (4, 0.019), (5, 0.018)]
]
print(detect_creative_fatigue(creative_history))
```

### 3.8 合规、隐私与风险的跨平台考量

#### 3.8.1 隐私与数据合规

跨平台投放涉及多国多平台数据，合规是硬约束。

```
隐私合规要点（跨平台）

  ├── 美国：CCPA/CPRA（加州）+ 联邦不统一 → 遵循平台政策
  ├── 欧盟：GDPR + ePrivacy（cookie 同意）
  ├── 中国：PIPL（个人信息保护法）+ 网信办新规
  ├── Apple ATT（iOS 14.5+）：限制 IDFA → 影响 Meta/TikTok 定向粒度
  ├── Google 隐私沙盒：第三方 cookie 逐步淘汰 → 影响 DV360 重定向
  └── Meta：EU-US Data Privacy Framework

  跨平台数据最小化原则：
  ├── 只收集达成广告目的所必需的数据
  ├── 用户画像脱敏/去标识化
  ├── 明确同意机制（同意管理平台 CMP）
  └── 保留期合理设置，定期清理
```

#### 3.8.2 各平台审核与素材风险

| 平台 | 审核严格度 | 高敏行业 | 常见驳回原因 |
|------|:--------:|---------|-------------|
| Google | 高 | 金融/医疗/博彩/成人 | 落地页问题、夸张宣称、个人化宣称 |
| Meta | 高 | 政策敏感类目 | 落地页不匹配、误导性、健康宣称 |
| TikTok | 中高 | 金融/药品/食品 | 画面剪辑、未授权音乐、药品宣称 |
| DV360 | 高 | 品牌安全敏感 | 品牌安全设置、内容合规 |

```
素材审核风险 Checklist
□ 落地页与广告内容一致（政策一致性）
□ 无夸大/虚假/绝对化宣称（"最便宜/最好"谨慎）
□ 金融类披露牌照与利率信息
□ 健康/医疗不在无资质宣称疗效
□ 音乐/素材版权合法（用平台授权曲库）
□ 未成年人/敏感人群素材合规
□ 药品/医疗需行业资质
```

#### 3.8.3 平台依赖与风险分散

```
平台风险分散策略（"别把鸡蛋放一个篮子"）

  ├── 政策风险：某平台政策突变/被禁（TikTok 部分地区被禁用风险）
  ├── 算法风险：平台算法大改导致效果骤降
  ├── 隐私风险：新隐私法规削弱某平台定向能力
  ├── 账号风险：某平台账号被封/申诉无门
  └── 归因风险：某平台报表不可信

  降低策略：
  ├── 跨平台配额：单一平台占比不超过 50%（成熟期）
  ├── 保持第一方数据资产（不依赖单一平台数据）
  ├── 备份渠道：即便主平台出问题，有可选替代
  ├── 账号 AB 账户：避免单账户风险（大额预算可拆分）
  └── 定期做"平台失效演练"：假设某平台停 2 周，预算如何重分配
```

### 3.9 跨平台实操 Checklist（投放前 / 中 / 后）

#### 3.9.1 投放前

```
投放前 Checklist
□ 明确目标（品牌/效果/混合）与核心 KPI
□ 用定位矩阵选平台组合（并非四平台都要）
□ 预算：按目标×行业×地区设定分配基线
□ 预留学习预算（5%+）
□ 统一 UTM / 事件埋点方案
□ 建立 metrics_daily 与 events_staging 表
□ 确认归因口径（决策用）
□ 素材按平台格式适配
□ 设定跨平台频控方案
□ 各平台账户/权限/资质就绪
□ 设定告警规则
```

#### 3.9.2 投放中（日常 + 周度）

```
日常（每日）：
□ 看 metrics_daily 异常（ROAS/CPA/预算进度）
□ 处理 P1/P2 告警
□ 确认转化事件流无中断

周度：
□ 跨渠道复盘会（中/大团队）
□ 预算重分配（若数据显著变化）
□ 素材疲劳检测 + 上新刷新
□ 检查频控与预算进度
□ 记录 learnings

月度：
□ 平台表现健康度周报
□ 深度归因复盘（MMM/增量）
□ 素材总结 + 下月创意方向
□ 预算框架回顾
```

#### 3.9.3 投放后 / 季度

```
季度复盘 Checklist
□ 全渠道 ROAS / CPA 达成 vs 目标
□ 各平台增量贡献（MMM/增量实验校准）
□ 预算分配是否最优（再利用等边际原则）
□ 品牌资产指标（品牌搜索量/声量份额）变化
□ 损益（spend vs revenue）与预算效率
□ 平台依赖风险回顾
□ 下季度策略与重分配
□ 技术与流程复盘（哪些 automation 有效）
```

### 3.10 跨平台 KPI 体系

跨平台运营需要一套"分层 KPI 体系"，避免只看单平台或只看总盘子。

```
分层 KPI 金字塔

  顶层（战略）      业务目标：营收 / 净利 / 市场份额 / 品牌健康
  中层（跨渠道）    全渠道 ROAS、增量 ROAS、新客占比、频控达标率、归因可信度
  底层（平台）      Google ROAS / Meta CPA / TikTok 新客CPNA / DV360 VCR+Reach

  平台 KPI ↔ 跨渠道 KPI ↔ 业务 KPI 逐层对齐

  关键补充指标：
  ├── 增量 ROAS (Incremental ROAS) —— 排除自然转化的真实 ROAS
  ├── 新客占比 (New Customer Ratio) —— 健康增长信号
  ├── 品牌搜索量指数 —— 品牌广告投资回报证据
  └── 归因膨胀率 —— 各平台合计 vs 实际转化（>130% 需警惕）
```

```python
def kpi_summary(platform_rows):
    """
    汇总跨平台 KPI。
    platform_rows: [{platform, spend, revenue, conversions, new_customers}]
    """
    total_spend = sum(r["spend"] for r in platform_rows)
    total_revenue = sum(r["revenue"] for r in platform_rows)
    total_conv = sum(r["conversions"] for r in platform_rows)
    total_new = sum(r["new_customers"] for r in platform_rows)

    # 归因膨胀示意：用"各平台 claim 之和"与"真实总转化(假设来自统一数据)"比较
    platform_claims = sum(r["conversions"] for r in platform_rows)
    true_total = total_conv  # 统一口径下的真实转化（示意相等）
    inflation = platform_claims / true_total if true_total else 1.0

    return {
        "total_spend": total_spend,
        "total_revenue": total_revenue,
        "total_roas": total_revenue / total_spend if total_spend else 0,
        "total_conversions": total_conv,
        "new_customer_ratio": total_new / total_conv if total_conv else 0,
        "attribution_inflation": round(inflation, 2),
    }
```

---

## 四、常见问题与排查

### 4.1 排查方法论总览

跨平台问题千奇百怪，但排查路径是固定的。先给出**通用排查框架**：

```
跨平台问题通用排查框架（5W1H + 分层）

  1. What   什么问题？（效果差/数据异常/预算异常/素材被拒/账号问题）
  2. Where  哪个平台/哪个层？（平台层/数据层/分析层/组织层）
  3. When   何时开始？（突发 vs 渐变；与时间事件关联）
  4. Who    谁受影响？（全部用户 vs 部分市场/人群）
  5. How    如何复现/验证？
  6. Help   影响范围与优先级（P0~P3）

  分层定位：
  ┌─ 平台层：该平台自身报表是否异常？（先看平台原生视角）
  ├─ 数据层：事件是否正常上报？（像素/服务器事件/CAPI）
  ├─ 分析层：统一报表是否正确聚合？（UTM 规范/时区/去重）
  └─ 组织层：是否流程/权限/职责导致（人肉因素）
```

### 4.2 高频问题分类表

| 问题分类 | 典型表现 | 最可能根因 | 排查入口 |
|---------|---------|-----------|---------|
| ROAS 下滑 | 各平台 ROAS 普遍下跌 | 大盘环境/季节性/素材疲劳/转化口径变化 | 先看大盘与同期对比 |
| 单平台异常 | 只有 Meta 变差 | 该平台学习期/竞价环境/素材 | 平台原生报表细分 |
| 数据不一致 | 平台报表 vs 统一报表对不上 | 归因口径/时区/UTM 不规范 | 数据层核查 |
| 归因膨胀 | 三平台合计 >130% | 各自为政的归因 | 统一归因口径 |
| 预算花不出去 | 有预算但无消耗 | 出价过低/定向过窄/审核/库存 | 平台投放状态 |
| 预算烧太快 | 预算提前花光 | 出价过高/频控失效/版位过宽 | 花费进度与频控 |
| 素材被拒 | 广告未过审 | 政策问题/落地页不符/素材违规 | 平台审核原因 |
| 转化追踪丢失 | 转化数骤降 | 像素/事件失效/归因窗口/隐私 | 事件流监控 |
| 冷启动失败 | 新平台学不会 | 预算过低/转化事件稀疏/目标不清晰 | 冷启动检查 |
| 学习期反复 | 自动化一直"学习中" | 频繁修改/预算波动/数据不足 | 减少变更 |

### 4.3 ROAS 下滑排查（跨平台通用）

ROAS 下滑是最高频问题。给出分步排查树：

```
ROAS 下滑排查树

  Q1 是全平台还是单平台下滑？
   ├─ 全平台 → 外部因素优先：
   │     ├─ 季节/节日波动？（对比去年同期）
   │     ├─ 大盘竞价上涨？（CPM 全局上行）
   │     ├─ 转化口径变化？（GA4/像素更新）
   │     ├─ 竞品大量入场？
   │     └─ 价格/库存/落地页变化？
   └─ 单平台 → 平台内部因素：
         ├─ 素材疲劳？（CTR 下降 → 刷新素材）
         ├─ 学习期？（新 campaign/频繁改动）
         ├─ 竞价环境？（同品类预算涌入）
         ├─ 定向问题？（人群池耗尽/过窄）
         └─ 版位变化？（自动化把预算挪到低效版位）

  Q2 转化量降了还是花费涨了？
   ├─ 转化降 → 看流量与转化率分段定位
   ├─ 花费涨 → 看出价/CPM/频次
   └─ 双降 → 更可能是素材/落地页/大盘

  Q3 是"报表 ROAS"降还是"真实业务 ROAS"降？
   └─ 用统一数据 + MMM 校准，排除归因假象
```

```python
def diagnose_roas_drop(current, baseline, window_days=7):
    """
    简单诊断：对比当前与基线，输出初步判断。
    current/baseline: {"spend":..,"revenue":..,"conversions":..,"clicks":..,"impressions":..}
    """
    def roas(d): return d["revenue"] / d["spend"] if d["spend"] else 0
    def ctr(d): return d["clicks"] / d["impressions"] if d["impressions"] else 0
    def cvr(d): return d["conversions"] / d["clicks"] if d["clicks"] else 0

    roas_delta = (roas(current) - roas(baseline)) / roas(baseline) if roas(baseline) else 0
    ctr_delta = (ctr(current) - ctr(baseline)) / ctr(baseline) if ctr(baseline) else 0
    cvr_delta = (cvr(current) - cvr(baseline)) / cvr(baseline) if cvr(baseline) else 0

    hints = []
    if ctr_delta < -0.15:
        hints.append("CTR 显著下滑 → 优先检查素材疲劳/创意质量/定向")
    if cvr_delta < -0.15:
        hints.append("CVR 显著下滑 → 优先检查落地页/价格/转化事件")
    if roas_delta < -0.2:
        hints.append("ROAS 下滑超 20% → 检查大盘/竞价/频控")
    if abs(ctr_delta) < 0.1 and abs(cvr_delta) < 0.1:
        hints.append("CTR/CVR 稳定但 ROAS 降 → 检查花费端（出价/CPM）")

    return {"roas_delta": round(roas_delta, 3), "ctr_delta": round(ctr_delta, 3),
            "cvr_delta": round(cvr_delta, 3), "hints": hints}

print(diagnose_roas_drop(
    current={"spend": 50000, "revenue": 120000, "conversions": 900, "clicks": 30000, "impressions": 1000000},
    baseline={"spend": 45000, "revenue": 140000, "conversions": 1000, "clicks": 28000, "impressions": 900000},
))
```

### 4.4 单平台效果异常的专项排查

#### 4.4.1 Google 专项

```
Google 效果异常排查

  症状：Search/PMax ROAS 下滑
  排查：
  ├── 1. 查看 Search Terms 报告：是否被无关搜索词吃掉预算？
  │        （PMax 只显示部分搜索词 → 用 brand/non-brand 拆分验证）
  ├── 2. 质量分：关键词质量分是否下降？（相关性/落地页）
  ├── 3. 转化跟踪：GA4/Google Ads conversion 是否被改动？
  ├── 4. PMax 抢量：品牌词流量是否被 PMax 吸走？（→ 拆分品牌专属 campaign）
  ├── 5. 学习期：近期是否大幅改预算/素材/目标？
  ├── 6. 竞价：竞品是否抬价？（auction insights）
  └── 7. 归因：GA4 数据驱动归因 vs 平台最后点击差异
```

#### 4.4.2 Meta 专项

```
Meta 效果异常排查

  症状：Advantage+ CPA 上涨 / ROAS 下降
  排查：
  ├── 1. 学习期状态：campaign 是否在 Learning Limited？
  ├── 2. 素材疲劳：CTR 是否持续下滑？（Advantage+ 需要新鲜素材）
  ├── 3. 定向：Advantage Detailed Targeting 是否把人群扩到低质？
  ├── 4. 版位：预算是否被挪到 Audience Network/低效版位？
  ├── 5. 转化事件：Pixel/CAPI 事件是否正常？Conversion API 匹配率？
  ├── 6. 频控：是否过度触达老客（重复曝光 CPM 高）
  ├── 7. 人群池：相似受众是否被重复利用过度（lookalike fatigue）
  └── 8. 外部：ATT 影响 iOS 数据可用性 → 依赖建模转化
```

#### 4.4.3 TikTok 专项

```
TikTok 效果异常排查

  症状：CPM 上升 / 转化差
  排查：
  ├── 1. 素材新鲜度：短视频生命周期短，3~7 天就疲劳
  ├── 2. Spark Ads 状态：达人授权是否过期？
  ├── 3. 定向：兴趣包是否过窄/过宽？
  ├── 4. 归因窗口：是否因窗口短低估转化？
  ├── 5. 像素：TikTok Pixel / Events API 事件是否正常？
  ├── 6. 版位：自动版位是否大量投到低质位置？
  └── 7. 人群重叠：与 Meta 重叠用户重复触达
```

#### 4.4.4 DV360 专项

```
DV360 效果异常排查

  症状：CPM 上涨 / 可见度低 / VCR 差
  排查：
  ├── 1. Line Item pacing：是否 overspend/underspend？
  ├── 2. 交易类型：auction vs PD 的实际拿量
  ├── 3. 定向：是否定向过窄导致竞价不足
  ├── 4. 频控：是否全局频控被某交易突破
  ├── 5. 可见度：viewability 是否被低质库存拉低
  ├── 6. 品牌安全：排除设置是否过严导致拿不到优质库存
  └── 7. 创意：是否规范不符被拒/降权
```

### 4.5 数据不一致与归因问题排查

跨平台最头疼的往往不是投放，而是**数据对不上**。

```
数据不一致排查（四平台 vs 统一报表）

  常见根因：
  ├── 1. UTM 命名不规范 → 统一报表聚合错乱
  │      检查：抽查落地页 URL 的 UTM 是否规范
  ├── 2. 时区差异：平台默认时区 vs 报表时区
  ├── 3. 归因窗口：last click 窗口/模型不一致
  ├── 4. 转化定义：各平台 conversion event 定义不同
  ├── 5. 去重：同一用户多设备/多平台重复计数
  ├── 6. 数据延迟：各平台数据落库延迟不同
  └── 7. 采样/建模：平台"建模转化" vs 真实转化

  排查顺序：
  1. 先查 UTM → 2. 再查时区 → 3. 查转化定义
  4. 查归因模型 → 5. 查去重 → 6. 查数据管道延迟
```

```
归因膨胀排查

  场景：三平台各自报表合计转化 > 实际转化 30%+
  根因：每平台用自己的归因模型，且多平台触达同一用户
  处理：
  ├── 1. 建立"唯一事实源"（统一事件表 + 统一归因口径）
  ├── 2. 用 MMM 做宏观校准（季度）
  ├── 3. 用增量实验做"锚点"验证
  └── 4. 向管理层解释"平台报表 vs 事实源"的差异
```

### 4.6 预算相关问题排查

```
预算"花不出去"排查
├── 1. 出价过低：低于平台最低/竞价水平（查 auction insights）
├── 2. 定向过窄：人群池太小（查 reach 估计）
├── 3. 审核中：素材/广告还在审核
├── 4. 库存不足：版位/库存限制
├── 5. 学习期：算法还在探索，花费不稳定
└── 6. 频率限制：已达用户频控上限

预算"烧太快"排查
├── 1. 出价过高（如目标 ROAS 设太低 → 疯狂花钱）
├── 2. 版位过宽：自动版位覆盖低效流量
├── 3. 频控失效：同一用户被反复触达
├── 4. 无上限：Campaign 预算未设置/过高
└── 5. 异常事件：转化事件断流导致算法"只管花钱不看转化"
```

```
预算节奏问题（月初快/月底慢）

  原因：各平台默认"均匀花钱" vs 人工"月底冲量"
  处理：
  ├── 用 pacing 目标/加速投放控制
  ├── 按周设置 spending schedule
  └── 监控 daily budget utilization
```

### 4.7 冷启动问题排查

```
冷启动失败排查（新平台/新 campaign）

  表现：学不会、转化少、花费不稳
  排查：
  ├── 1. 转化事件是否足够？<10~15 次/周 → 事件太少学不动
  ├── 2. 预算是否够冷启动？过低 → 样本不足
  ├── 3. 是否频繁改动？（每次改动重置学习期）
  ├── 4. 目标设置是否合理？（目标 ROAS 过高 → 无法放量）
  ├── 5. 素材数量与质量？
  ├── 6. 归因窗口/转化延迟？（转化延迟导致算法反馈滞后）
  └── 7. 出价方式是否适合该目标？

  缓解：
  ├── 先跑"最大化转化"而非"目标 ROAS"度过冷启动
  ├── 冷启动期（2~6 周）不轻易改结构
  ├── 提供足够转化数据（考虑先投"低门槛事件"如加购）
  └── 预留专门冷启动预算（学习预算）
```

### 4.8 素材被拒/审核问题排查

```
素材被拒通用排查

  ├── 1. 看平台给出的"拒绝原因"（policy 名称）
  ├── 2. 检查落地页：是否与广告内容一致、可访问、合规
  ├── 3. 检查文案：夸张宣称/绝对化/敏感词
  ├── 4. 检查素材：音乐版权/画面/人群
  ├── 5. 行业资质：金融/医疗/药品需资质文件
  └── 6. 申诉流程：准备好证据重新提交

  各平台申诉差异：
  ├── Google：政策中心申诉 + 重新提交审核
  ├── Meta：账户质量页面申诉
  ├── TikTok：广告管理后台申诉
  └── DV360：客服/Partner 渠道处理
```

### 4.9 转化追踪问题排查

```
转化追踪异常排查（跨平台）

  症状：某平台转化数骤降/归零
  排查：
  ├── 1. 像素/事件是否被移除或损坏？（检查 Tag Assistant / Meta Pixel Helper）
  ├── 2. 服务端事件（CAPI/Events API）是否正常？（匹配率如何）
  ├── 3. 归因窗口是否被改？
  ├── 4. 隐私设置：ATT/同意横幅是否导致事件丢
  ├── 5. 平台侧设置：conversion action 是否被暂停
  ├── 6. 落地页改版导致转化事件丢失
  └── 7. 浏览器/广告拦截影响 client-side 事件

  最佳实践：
  ├── client-side + server-side 双通道（如 CAPI）
  ├── 事件监控：每平台事件延迟/量级告警
  └── 归因口径固定后不要频繁切换
```

### 4.10 组织/流程类问题

```
组织类常见问题

  ├── 问题：渠道 Owner 各自为政，抢预算
  │   处理：跨渠道统筹人 + 统一归因口径 + 双轨考核
  ├── 问题：数据分析师成了"取数工"而非决策支持
  │   处理：建自动化报表，让分析师做分析而非拉数
  ├── 问题：平台专家离职带走知识
  │   处理：文档化（本知识库）+ 账号权限回收 + 交接
  ├── 问题：管理层只看平台报表（被单平台"好看报表"误导）
  │   处理：统一看板 + 增量口径培训
  └── 问题：外包/代理商与 in-house 分工不清
        处理：明确双方职责边界与验收标准
```

### 4.11 排查总结速查卡

```
跨平台问题速查卡（打印版）

  效果差   → ROAS/CPA 下滑：先分"全平台 vs 单平台"，再按 4.3 树排查
  数据乱   → UTM → 时区 → 转化定义 → 归因 → 去重（4.5）
  预算怪   → 花不出去（出价/定向/审核）；烧太快（出价/版位/频控）（4.6）
  学习不动 → 事件量/预算/改动频率/目标设置（4.7）
  被拒     → 政策原因 → 落地页 → 文案 → 素材 → 资质（4.8）
  追踪丢   → 像素/CAPI/窗口/隐私/落地页（4.9）
  组织乱   → 统筹人/统一口径/文档化/权限（4.10）
```

---

## 五、自测题

> 以下 5 道题覆盖本文档的核心知识点。先独立作答，再展开 `<details>` 查看答案与解析。

### 题目 1：平台定位矩阵

某 DTC 3C 品牌，新品上市 3 个月，目标是**最快建立认知并起量**，团队人手有限（小团队）。请根据平台定位矩阵选择**优先级最高的两个平台组合**，并说明理由。

<details>
<summary>查看答案</summary>

**推荐：TikTok + Google Search**

解析：
- 新品上市需要"认知 + 收割"双管齐下。
- **TikTok**（短视频注意力引擎）负责快速种草、建立认知，Spark Ads 用达人放大，是新品冷启动 T0 阶段的性价比之选。
- **Google Search**（搜索意图引擎）负责承接——当用户在 TikTok 看到后去搜索品牌/品类词，Google Search 精准收割。
- 为什么不优先 Meta？小团队人力有限，一次上太多平台反而学不深；Meta 放在第二阶段（再营销放大）更合适。
- 为什么 DV360 放最后？企业级品牌平台对预算/人力门槛高，小团队冷启动阶段不匹配。

**决策逻辑回顾：** 预算跟随用户心智——先满足"认知(种草)"与"意图(收割)"两大缺口，再做兴趣(meta)与品牌(dv360)扩展。

</details>

### 题目 2：能力雷达图与平台选型

有一家连锁餐饮（多门店品牌），预算充足，目标是**季度性大促期间最大化本地触达 + 品牌声量**，同时希望**企业级频控与品牌安全控制**。请基于能力雷达图（触达/数据/自动化/创意/转化）选择最合适的平台，并说明它在你评估维度里的优劣势。

<details>
<summary>查看答案</summary>

**推荐：DV360（为主）+ Google（搜索/本地收割为辅）**

解析（对照雷达图五维）：
- **触达规模 9**：DV360 依托全互联网 + CTV/本地库存，本地大促触达广，符合"最大化本地触达"。
- **数据精度 7**：需要你上传第一方客群/门店数据，精度取决于数据质量；本地定向（线下/POI）能力强。
- **自动化 7**：非全黑盒，但可用脚本化 + pacing 控制节奏，符合"企业级控制"需求。
- **创意灵活性 6**：品牌展示创意受品牌安全/格式限制较多，正好匹配"需要品牌安全控制"的目标。
- **转化追踪 6**：DV360 强在媒体层归因与 view-through，直接转化追踪弱于 Search，故辅以 Google 搜索做本地收割。

**关键：** 品牌大促场景下，"控制力 + 触达 + 品牌安全"比"直接转化追踪"更重要，这正是 DV360 的用武之地。

</details>

### 题目 3：预算分配策略

某零售品牌月预算 $80K，处于成熟期，追求**均衡的全漏斗增长（品牌 + 效果兼顾）**。你手上四个平台的 7 天 ROAS 分别为：Google 4.0、Meta 2.8、TikTok 2.2、DV360 1.6。请给出分配建议，并说明为什么**不能只按当前 ROAS 线性分配**。

<details>
<summary>查看答案</summary>

**建议分配（示意，需 + 学习预算）：**

```
原则：ROAS 越高给越多预算 + 预留学习预算 + 品牌考虑

  Google  40%  ($32K)  效果主力，ROAS 高
  Meta    28%  ($22.4K) 再营销+增长，ROAS 中高
  TikTok  17%  ($13.6K) 新品种草，新客价值
  DV360   10%  ($8K)    品牌覆盖，ROAS 低但不可用 ROAS 衡量
  学习池   5%  ($4K)    新平台/新素材探索
```

**为什么不能纯按 ROAS 线性分配：**
1. **边际回报递减**：ROAS 高的平台给越多预算，其边际回报会下降（投入回报没用那么多）。线性分配忽略了饱和效应。
2. **不同平台的 KPI 属性不同**：DV360 是品牌平台，用 ROAS 衡量不公平——它的价值在 Reach/品牌提升，不能只用转化 ROAS 评估。
3. **品牌投资有"滞后/溢出"**：品牌广告对后续搜索/转化的提升不会被"当期 ROAS"体现。
4. **新客价值**：TikTok 当期 ROAS 低，但它带来更高新客占比，长期价值被低估。
5. **学习预算**：不预留探索预算会错过未来的增长机会。

**正确做法：** 用等边际原则 + 增量 ROAS（排除自然转化）+ 品牌价值加权的综合效用模型，而非单一 ROAS 线性分配。

</details>

### 题目 4：平台迁移

一个已经稳定投放 Google（Search+PMax）的团队，想扩展第二个平台。请说明**选择 Meta 还是 TikTok 的理由、扩展前必须做好的基建改造、以及如何验证第二个平台是"真增量"而非"蚕食"。**

<details>
<summary>查看答案</summary>

**选 Meta 还是 TikTok：**
- 若目标是从"搜索收割型"补足"兴趣/再营销型" → 先 **Meta**（与搜索互补：搜索解决"我要买"，Meta 解决"我在刷/启发/再营销"）。
- 若目标是**新品种草 + 年轻客群新客**，且产品适合短视频 → 先 **TikTok**（Spark Ads 达人种草，新客占比高）。
- 通用扩展顺序（3.2.2）：从效果端(Google)出发，先补"漏斗另一端/互补端"，即 Meta(兴趣/再营销) 或抖音式种草(TikTok)，而不是再加一个同质搜索平台。

**扩展前必做基建改造（Checklist，3.2.4）：**
- 统一 UTM 规范（utm_source/medium/campaign/content/term）
- 统一事件表（events_staging，四平台事件归一）
- 统一归因口径（决定决策用 last click 还是 data-driven/MMM）
- 第一方 ID 打通（至少 cookie/device 级，做跨平台去重）
- 跨平台频控方案（CM360/ADH 或自建）
- 统一创意库（记录素材各平台版本）
- 统一报表看板 + 告警

**如何验证"真增量"（3.2.3）：**
- 先记录 Google 单平台 4 周基线。
- 把人群/地域随机分 Test（开 Meta）+ Control（仅 Google）。
- 跑 2~4 周，对比增量转化 = Test − Control（排除自然波动）。
- 计算增量 ROAS = 增量收入 / 新平台花费。
- 若增量 ROAS > 阈值（如 1.5x）→ 正式扩展；若 ≈0 或 <1 → 该平台只是在"抢原有漏斗"，暂停。
- 用 t 检验判断差异显著性（见代码示例 incrementality_test）。

</details>

### 题目 5：组织架构适配

一个 3 人小团队想同时运营 Google、Meta、TikTok 三个平台，并希望未来扩展 DV360。请给出**组织/运营策略建议**（自动化依赖、DV360 处理、数据基建、分工），并说明从中团队演进到大团队的关键触发条件。

<details>
<summary>查看答案</summary>

**3 人小团队策略：**
- **自动化扛量**：Google 用 PMax、Meta 用 Advantage+、TikTok 用 Smart+/Spark——让平台算法负责绝大部分优化，人只做策略与异常处理。
- **分工**（3.3.2）：创始人/负责人做战略+审批；1~2 人做投放运营（三平台都管，靠自动化）；数据分析用托管工具（Supermetrics→Sheets/BigQuery）。
- **DV360 处理**：小团队**不自营**，交给媒介代理商（PubMatic/Google Partner）负责，或用企业级账号 + 外包，避免高人力门槛。
- **数据基建**：即便人少，也要尽早建统一 UTM + metrics 表（哪怕用 Sheet），否则后期返工成本高。
- **预算分配**：固定比例 + 周度人工校准，不搞复杂算法（小团队没必要）。

**关键触发条件（3.3.7 演进到中/大团队）：**
- 月预算跨过门槛（如 $50K+）→ 需要专职投放。
- 平台数量 ≥ 3 → 需要统一归因 + 跨渠道统筹人（否则各自为政）。
- 开始做品牌/上 DV360 → 需要程序化团队或媒介人员。
- 数据复杂度高/需要 MMM/增量实验 → 需要数据科学角色。
- 合规/审计需求上升 → 需要合规岗位。

**演进路线：** 小(一人多岗+自动化+外包DV360) → 中(渠道Owner+数据分析师+统一归因+DV360入局) → 大(平台专家专职+数据科学团队+品牌程序化团队+中台)。

</details>

---

## 附录 A：本文关键方法论汇总

```
跨平台战略六大方法论（速览）

  1. 平台定位矩阵  —— 搜索(Google)/社交(Meta)/短视频(TikTok)/程序化品牌(DV360)
  2. 能力雷达图    —— 触达/数据/自动化/创意/转化 五维 0-10 打分
  3. 预算分配模型  —— 目标×行业×地区 + 等边际原则 + 学习预算
  4. 增量验证      —— Geo/人群增量测试，区分"真增量 vs 蚕食"
  5. 统一数据底座  —— UTM + 统一事件表 + 统一归因口径
  6. 组织适配      —— 小/中/大团队的平台运营与分工策略
```

## 附录 B：四平台产品/术语速查表

| 关键词 | 所属平台 | 说明 |
|--------|---------|------|
| H-iMax | Google | 高意图 Performance Max |
| PMax | Google | Performance Max 全自动广告 |
| SA360 | Google | Search Ads 360 搜索管理 |
| CM360 | Google | Campaign Manager 360 媒体管理/归因 |
| ADH | Google | Ads Data Hub 数据整合 |
| Advantage+ | Meta | 全自动投放系列 |
| CAPI | Meta | Conversions API 服务端转化 |
| Reels | Meta | Instagram 短视频版位 |
| Spark Ads | TikTok | 达人原生内容推广 |
| Smart+ | TikTok | 全自动化投放 |
| TikTok Shop | TikTok | 站内电商闭环 |
| DV360 | Google | Display & Video 360 DSP |
| DSP | DV360 | Demand-Side Platform |
| PD | DV360 | Programmatic Direct 程序化直采 |

## 附录 C：公式速查表

| 公式 | 含义 |
|------|------|
| ROAS = Revenue / Spend | 投入产出比 |
| CPA = Spend / Conversions | 单转化成本 |
| CTR = Clicks / Impressions | 点击率 |
| CVR = Conversions / Clicks | 转化率 |
| Ad Rank = 出价 × 质量分 | Google 搜索排序 |
| 增量 ROAS = 增量收入 / 新平台花费 | 排除自然转化的真实 ROAS |
| 饱和函数 f(spend)=α·spend/(1+β·spend) | MM 饱和/递减回报 |
| Adstock(t)=γ·raw(t)+(1-γ)·Adstock(t-1) | 广告记忆延续 |
| 等边际条件 MU_i/Cost_i 相等 | 预算最优分配 |

## 参考与延伸阅读

本文是跨平台战略顶层文档，建议结合以下平台深度文档阅读：

- **Google Ads**：`google-ads/` 目录下的 Search Masterclass / PMax / Architecture 文档
- **Meta Ads**：`meta-ads/` 目录下的 Advantage+ / Targeting / Optimization 文档
- **TikTok Ads**：`tiktok-ads/` 目录下的 In-Feed/Spark / Shop / Optimization 文档
- **DV360**：`dv360/` 目录下的 Architecture / Programmatic / Measurement 文档
- **跨渠道优化**：`cross-channel-optimization/cross-channel-budget-allocation-deep.md`
- **归因**：`ad-cross-platform-attribution-deep.md`、`ad-attribution-shapley-markov-deep.md`
- **隐私合规**：`privacy-first-party-data.md`、`capi-deep-dive.md`
- **API 实操**：`google-ads-api/`、`meta-ads-api/`、`tiktok-ads-api/` 下的 API 文档

> 更多平台级深度文档见 `google-ads/`、`meta-ads/`、`tiktok-ads/`、`dv360/` 目录，以及 `cross-channel-optimization/` 下的跨渠道专题。

---

*文档结束。本文试图把"跨平台广告战略"从选型、原理、预算、迁移到组织适配全链路讲透，供实战团队直接参考落地。*
