# Google Ads Performance Max 暗箱解析：资产组、信号、GMX、Performance Planner、跨渠道归因

> **领域**: 广告投放 / GOOGLE_ADS
> **深度**: ⭐⭐⭐⭐⭐ 实战级指南
> **标签**: GOOGLE_ADS, 广告投放
> **更新时间**: 2026-08-14
> **类型**: 深度知识文档

---

## 一、核心概念与架构

Performance Max（简称 PMax）是 Google Ads 体系里最容易让人"又爱又恨"的产品。

爱它，是因为它把搜索、购物、展示、视频、Discovery、Gmail、地图七大渠道
揉进同一个 campaign，用一套素材和信号就让系统自动跑通全链路，ROAS 通常
能比手动系列高 15%–40%。

恨它，是因为它是一台实实在在的"暗箱"：你看不到关键词、看不到精确的渠道
花费归属、看不到每次点击到底为哪条路径付费。投放经理面对的是一个"半盲"
系统，只能通过资产组、受众信号、预算与出价这类"旋钮"去间接影响算法。

本篇文档的目标，是把这台暗箱从结构、原理、归因到落地完整拆给你看。
我们会用真实的 GAQL、Python、Go 代码，以及美妆 D2C、电商 GMX、游戏增长、
直播带货等具体业务案例，讲清楚每一层黑盒背后的"为什么"。

---

### 1.1 PMax 的本质：目标驱动的跨渠道智能投放

PMax 与"传统手动系列"最大的差别，不是渠道多，而是**控制面完全反转**。

在搜索广告里，你告诉系统"哪些词、匹配到什么程度、出多少钱、预算花在哪"，
系统照着执行。控制权在你手上，系统只是执行器。

在 PMax 里，你把控制权交给系统，只告诉系统两件事：

1. **你要什么结果**（最大化转化、最大化转化价值、目标 ROAS、目标 CPA）。
2. **你有哪些素材和线索**（资产组 assets + 受众信号 signals + 商品 feed）。

剩下的，由系统在七大渠道之间实时分配预算、组合素材、寻找用户、动态出价。

```
传统 SERP 手动系列控制面 vs PMax 控制面
─────────────────────────────────────────────────────────────

 手动 Search Campaign                     PMax Campaign
 ─────────────────────────               ─────────────────────────
 关键词        ✅ 你全权控制              ❌ 无关键词，系统自选
 匹配类型      ✅ 你全权控制              ❌ 不存在
 广告组结构    ✅ 你定义                  ⚠️ 改为资产组(Asset Group)
 出价          ✅ CPC/CPA 手动+智能         ✅ 仅智能(非可选的自动出价)
 素材          ✅ 按关键词投放             ⚠️ 上传到资产组供系统组合
 渠道          ✅ 仅 Search               ✅ Search/Shopping/Display/
                                            Video/Discovery/Gmail/Map
 预算分配      ✅ 你定                    ❌ 系统跨渠道动态分配
 可见性        ✅ 词级/广告组级报表完整     ⚠️ 渠道级花费聚合，无词级
```

这个反差正是"暗箱"一词的来源：**决策权移交得越多，可见性就越低**。
而商业上，Google 愿意用"更优秀的自动化"来交换"更少的透明度"。

> 关键认知：PMax 不是"搜索广告的强化版"，而是一个**全新的品类**。
> 它接管了原来的智能购物（Smart Shopping，已停用）、部分应用广告，
> 并用全新的架构统一了所有效果类渠道。

---

### 1.2 PMax 的完整架构与数据流

从账户根节点往下看，PMax 的层级非常清晰：广告系列 → 资产组 → 资产 / 信号。
这份层级跟传统 Search（系列 → 广告组 → 关键词/广告）是两套不同体系。

```
PMax 账户结构总览
────────────────────────────────────────────────────────────────────
                              Google Ads Account
                                     │
         ┌───────────────────────────┼───────────────────────────┐
         │                           │                           │
    Campaign A (PMax)          Campaign B (PMax)          Campaign C (PMax)
   PERFORMANCE_MAX_           PERFORMANCE_MAX_           PERFORMANCE_MAX_
   FOR_GOALS                 FOR_GOALS                  FOR_GOALS
         │                           │                           │
   ┌─────┴─────┐              ┌──────┴──────┐              ┌─────┴─────┐
   │           │              │             │              │           │
Asset Group  Asset Group    Asset Group   Asset Group    Asset Group  Asset Group
   (洗护)       (美妆)         (连衣裙)       (套装)          (新客)       (老客召回)
         │
   ┌─────┴────────────────┬──────────────────────┬─────────────┐
   │                      │                      │             │
 Assets(素材)         Signals(信号)          Final URL     URL Options
 图片/Logo/视频/       Custom Segment       落地页         移动/桌面 URL
 标题/描述/商品       In-Market/相似/再营销    ...
        │
   ┌────┴────────┬────────────┬─────────────┐
 IMAGE  TEXT  HEADLINE  YOUTUBE_VIDEO  ...
 ────────────────────────────────────────────────────────────────────
```

数据流方向是这样的：素材与信号从资产组向上"喂"给系统，系统在后台把
它们输入模型，同时在七大渠道投放、收集点击与转化信号，再用转化数据
反向更新出价与组合策略，形成闭环。

```
PMax 运行闭环数据流
────────────────────────────────────────────────────────────────────

  [投放前的输入]                     [运行时决策]               [学习反馈]
 ┌───────────────┐               ┌────────────────┐        ┌──────────────┐
 │ Asset Group    │               │ 跨渠道投放引擎   │        │ 转化回传      │
 │  - 素材         │  ──输入──▶    │  Search         │        │ (pixels/tag) │
 │  - 受众信号     │               │  Shopping       │        │  → GA4       │
 │  - final_url    │               │  Display        │        │  → 出价模型   │
 │  - 商品 feed    │               │  YouTube        │        │  → 素材组合   │
 └───────────────┘               │  Discovery/Gmail │        └──────────────┘
                                 │  Maps            │               ▲
                                 └────────┬───────┘               │
                                          │ 曝光/点击/浏览         │
                                          ▼                       │
                                 ┌────────────────┐               │
                                 │ 实时出价:       │               │
                                 │ bid = f(上下文, │               │
                                 │  用户特征, 资产)│────转化价值───┘
                                 │  tROAS 约束      │
                                 └────────────────┘
```

理解这条闭环，是后面所有优化动作的地基。

很多投放经理犯的错误，是把 PMax 当成了一个"设置了就放的机器"，
或者反过来频繁改素材、改预算，破坏了模型的学习连续性。
真正的高手，是把这条闭环的每一个输入点都当成可控旋钮，系统化地调。

---

### 1.3 PMax vs 标准系列：一张对照表

为了让你一眼看到差异，这里给出完整的对照表。这张表是面试和方案设计里
最高频被问到的素材。

| 维度 | PMax (PERFORMANCE_MAX) | 标准 Search Campaign | 标准 Display Campaign |
|------|------------------------|----------------------|----------------------|
| 营销目标 | 转化/转化价值（效果为主） | 转化 + 点击 + 展示份额 | 品牌曝光/转化 |
| 可用渠道 | 7 大渠道自动分发 | 仅 Search | 仅 Display Network |
| 关键词 | 无（由资产+信号推断） | 必须（核心控制单元） | 无 |
| 广告组 | 资产组 Asset Group | 广告组 Ad Group | 广告组 Ad Group |
| 受众定向 | 信号(提示)+广泛匹配 AI | 关键词+受众精细控制 | 受众精细控制 |
| 素材类型 | 图片/标题/描述/Logo/视频/商品 | 扩展文字广告/自适应搜索广告 | 自适应展示广告 |
| 出价方式 | 强制自动出价(tROAS/MaxConv) | 手动/增强/目标CPA可选 | 自动或手动 |
| 渠道花费可见性 | 聚合，不可见单渠道精确花费 | 完整可见 | 完整可见 |
| 词级报告 | 无 | 有 | 无 |
| 适用场景 | 效果规模化、全链路转化 | 精确意图精准收割 | 品牌再营销 |
| 学习周期 | 7-14 天（新账户可能更长） | 数天 | 数天 |
| 素材强度要求 | 高（直接影响算法自由组合） | 中 | 中 |

这张表最关键的一行是"渠道花费可见性"：PMax 把七大渠道的预算分配当成
内部优化秘密，只给你聚合数字。

这意味着你不能简单地问"我 YouTube 花了多少钱"——系统要么不给，
要么只给出一个大范围估算。这是设计使然，不是 Bug。

---

### 1.4 广告系列子类型矩阵

API 视角里，PMax 不是一个孤零零的子类型，而是一个"家族"。
每一种子类型对应不同的业务诉求和可用的附加能力（如商品、应用、旅游）。

| 子类型(advertising_channel_sub_type) | 定位 | 典型业务 | 依托的资产/数据 |
|--------------------------------------|------|----------|----------------|
| PERFORMANCE_MAX_FOR_GOALS | 通用效果型 PMax | 电商/线索/品牌通用 | 资产组 + 可选 URL |
| PERFORMANCE_MAX_FOR_TRAVEL_GOALS | PMax 旅游 | 酒店/机票/旅游平台 | 旅游 feed + 航班/酒店数据 |
| SHOPPING_GOALS | 购物目标 PMax | 标准电商(带 Shopping feed) | Merchant Center feed |
| PERFORMANCE_MAX_FOR_ANDROID_APPS | PMax Android 应用 | 手游/应用增长 | 应用转化 + 商店素材 |
| APP_CAMPAIGN | 旧式应用广告(迁移中) | 存量应用账户 | App 素材 |

> 迁移提示：老的 APP_CAMPAIGN（即 Universal App Campaign，UAC）正在被
> PERFORMANCE_MAX_FOR_ANDROID_APPS 取代。Google 推出了"一键迁移"，
> 把 UAC 升级为 PMax for apps，以统一资产组与信号体系。

写 GAQL 时，我们可以直接用 `campaign.advertising_channel_type = PERFORMANCE_MAX`
搭配 `campaign.advertising_channel_sub_type` 过滤出具体子类型。
下一节我们先建立账户级结构，第二章再给完整代码。

---

### 1.5 PMax 与相邻产品的体系关系

PMax 并不是凭空出现的，它是从一串旧产品演进而来。
理清这条演进线，能帮你理解"为什么 PMax 长这样"。

```
PMax 产品演进路线
────────────────────────────────────────────────────────────────────
  2015  Shopping (standard)         → Merchant Center + 商品
  2018  Smart Shopping              → 自动出价 + 商品, 无素材自由控制
  2019  Universal App Campaign      → App 自动化
  2021  Performance Max (初版)      → 统一 7 渠道 + 资产组
  2022  PMax 各种 ROI/CPA 功能      → 素材强度、组合实验、
                                       客户生命周期价值(CLV)目标
  2023-24  持续增强                 → 品牌隔离、负向信号、搜索词洞见、
                                       Performance Planner 联动、
                                       GMX(通用商品体验) 深化
```

与它相邻的系统有：

- **Smart Bidding**：PMax 内部依赖的自适应出价引擎，也是它的"大脑"。
- **Merchant Center**：电商版 PMax（Shopping 目标）的数据源，负责商品 feed。
- **Google Analytics 4 (GA4)**：转化数据的采集与跨渠道归因的决策引擎。
- **Google Signals**：GA4 里跨设备、跨账户的用户统一标识，影响归因。
- **Privacy Sandbox**：第三方 Cookie 退场后，广告定向与测量的替代方案。

可以这样理解它们的从属关系：

```
   Google Signal / Privacy Sandbox   → 用户识别的底座
   GA4                               → 转化数据 + 跨渠道归因决策
   Merchant Center                   → 商品数据(电商)
   ┌───────────────────────────────────────────────────┐
   │  PMax  =  Smart Bidding(出价)                      │
   │          +  Asset Group(素材组合)                   │
   │          +  7 渠道分发                               │
   │          +  转化目标(归因后的转化价值)               │
   │          +  Performance Planner(预测与模拟)         │
   └───────────────────────────────────────────────────┘
   Performance Planner = PMax 的"前置推演器"
```

第二章我们会深入每一个引擎的原理，包括 Performance Planner 的预测数学。

---

### 1.6 "暗箱"的本质：为什么不可见

这一小节把"不可见"讲透。PMax 刻意隐藏了四类信息，四类的动机各不相同。

**第一类：关键词与查询。**
PMax 没有关键词，但 Google 的 Search 部分仍按查询匹配。你只能通过
"搜索词洞见（Search Terms Insights）"看到聚合的查询主题，看不到每条词，
因为系统在广告竞价中同时考虑海量信号，把词级归因公开会泄露竞价机密。

**第二类：精确渠道花费。**
系统在七渠道之间实时分配预算。它只给你"渠道级聚合花费"或不给精确值，
因为预算分配是最核心的优化权。公开它，广告主会去手动调频道，反而破坏
模型的全局最优。

**第三类：受众定向的最终边界。**
受众信号是"提示"不是"硬限制"。系统可能投到信号之外的人群。
这不透明，因为 Google 想通过扩大探测范围来找到高转化的新客。

**第四类：每次竞价的实时出价。**
你看不到 PMax 在每次展示时到底出了多少钱，只有聚合的 avg cpc / cpm。

```
PMax 可见性光谱
──────────────────────────────────────────────────────────────
 可见 ✅                      半可见 ⚠️             不可见 ❌
 总花费                      渠道聚合花费(估算)        词级查询
 总转化/ROAS                 搜索词主题                精确渠道花费
 资产组级表现                优化分数(0-100)          单次实时出价
 素材强度(四档)              学习期状态                 受众最终边界
 素材/信号诊断建议           转化时间窗口影响            跨渠道路径明细
```

理解这个可见性光谱，是"接受不可控，专注可控"的开始。
下面进入第二章：这些引擎背后到底怎么工作。

---

## 二、深度原理解析

这一章从算法与工程层面拆解 PMax 的内核。我们不满足于"Google 会自动优化"
这种空话，而是把出价、跨渠道分发、信号建模、转化归因的数学与代码讲清楚。

---

### 2.1 智能出价引擎：Target ROAS / 最大化转化价值

PMax 的默认目标通常是 **最大化转化价值（maximize conversion value）**，
并可选地配一个 Target ROAS（tROAS）作为硬约束。API 里对应
`MAXIMIZE_CONVERSION_VALUE` 与 `TARGET_ROAS`。

它的出价问题，可以形式化为一个受约束的实时优化：

```
目标:   max Σ_p  E[ConvValue_p | ctx] · x_p          (最大化总转化价值)
约束:   s.t. Σ_p  E[Cost_p] · x_p ≤ Budget          (不超每日预算)
       且(可选) Σ ConvValue_p / Σ Cost_p ≥ tROAS    (ROAS 底线)

其中:
  p        = 每个 auction/机会(一次展示机会)
  x_p      = 是否参与该次竞价 (0/1), 由出价决定
  E[ConvValue] = 模型预测的该次展示转化价值
  E[Cost]   = 模型预测的该次点击成本
```

在 tROAS 模式下，系统会做**跨时段的全局规划**：它不只优化当下这一次竞价，
而是把一整天、数天的预算放在一个"预算池"里统筹。
这就解释了为什么 PMax 的每日花费会有波动——某天多花、某天少花，
只要在更长时间窗内满足 ROAS 和预算约束即可。

```
tROAS 的"预算池"调度示意
────────────────────────────────────────────────────────────
  Day  预算  实际花费   ROAS    说明
  Mon   800    640     4.9    保守, 出价偏低
  Tue   800    920     4.6    探测高价值机会, 略超当日
  Wed   800   1080     5.2    学习到高价值时段, 加码
  Thu   800    560     5.5    依赖积累, 减少低效花费
  ────────────────────────────────────────────
 周期内 4000   3200     5.0   池内统筹, 满足 tROAS=5.0
```

因为存在这种池化，投放经理常犯的错误是"用单日 ROAS 去评判 PMax"。
正确的做法是用 **7 天或 30 天滚动窗口** 评估，才不会被单日波动误导。

**出价分层**：PMax 的自动出价实际上是多层的：

```
出价决策分层
────────────────────────────────────────────────────────────
  层1 Campaign 级 tROAS / MaxConvValue 目标
  层2 跨渠道预算分配: Search/Shopping/Display/YouTube 各分多少
  层3 机会级(impression opportunity)预测:
        P(conv) × 转化价值(或 CPA 目标换算)
  层4 实时 bid 计算(带 pacing 限速防超预算)
```

每一层都吃同一份特征（用户、设备、时段、素材、上下文），层层递归优化。

---

### 2.2 跨渠道分发引擎

PMax 在七大渠道之间分配预算，背后是一个**多臂老虎机（Multi-Armed Bandit，MAB）**
叠加**上下文学习**的系统。

简化模型：每个渠道可以看作一只"臂"，系统要决定把预算喂给哪只臂。
但它不是普通 MAB——因为各渠道的用户和竞价环境差异巨大，系统必须
根据上下文（上下文 = 用户意图、时段、素材、商品）做**上下文相关**的分配。

```
跨渠道分配的 Contextual Bandit 视角
────────────────────────────────────────────────────────────

  渠道(臂)         平均 eCPM  平均 CVR   风险    系统分配偏置
  Search           高        中-高      低      意图最强, 优先
  Shopping         中        高(商品)   中      电商核心
  Display(再营销)  低        高(老客)   低      老客收割
  Display(发现)    低        低         高      新客探测
  YouTube          中        低-中      高      品牌+上漏斗
  Discovery/Gmail  中        中         中      增补触达

  分配策略 = ε-贪心 或 Thompson Sampling
    - 大部分预算(如 80%) 投给当前预测价值最高的渠道
    - 一小部分预算(ε) 去"探测"次优渠道, 避免陷入局部最优
```

这套机制解释了 PMax 的两个反直觉现象：

1. **渠道占比会漂移**：某天 YouTube 突然占 50%，过几天又回到 Search。
   这是系统在探测与利用之间切换，不代表你"该把预算搬到 YouTube"。
2. **强渠道越强**：Search 因意图信号强，通常稳定占据 30%–40%，
   接近我们的经验值。如果某渠道长期超过 60%，通常说明素材或信号
   在某场景失衡，值得用排除文件或素材调整去干预。

**预算 pacing**：PMax 的 daily 花费不会匀速。系统按"全天可用机会的
价值分布"来决定花多快。新品冷启动期，它常先"快花"来快速学习；
学习稳定后转为按价值 pacing。

---

### 2.3 受众信号如何变成"特征"

受众信号（Audience Signal）不是硬定向，而是给模型的"种子提示"。
这一步要把这句话翻译成工程语言。

当你在资产组里加入一批自定义受众、再营销受众、相似受众时，
系统的做法不是"只投这些人"，而是：

```
受众信号 → 模型特征 的转化
────────────────────────────────────────────────────────────

  信号(种子集)                模型侧动作
  ──────────────             ──────────────
  Custom Segment(关键词)    → 生成一个"意图向量", 用于查询-资产匹配
  Custom Segment(URL)       → 抓取该 URL 的语义, 扩展意图
  网站再营销受众(30天)       → 作为"种子用户", 训练相似度度量
  相似/兴趣(In-Market)       → 用作冷启动先验分布
  YouTube 再营销            → 视频观看意图信号

  关键点:
  1. 信号只初始化"先验分布", 不是"筛选后的终选集合"
  2. 系统在竞价中用实时特征(竞价信号)重新打分, 往往跳出信号范围
  3. 信号集合越小/越窄, 系统越倾向于守住信号; 越大越泛, 越靠模型
```

工程上，这就是"信号先验 + 在线后验"的贝叶斯更新：

```
P(高转化价值 | 该用户, 信号先验) ∝  P(该用户|信号) · P(高转化价值|用户特征)

先验(信号) 决定"从哪开始找"
似然(用户→转化价值的实时预测) 决定"继续找还是换方向"
```

所以正确实践是：**提供 3-5 组代表核心客户的信号，但留足自由度**，
让模型基于实时信号去扩展。过度收窄信号会让系统失去扩展能力，
反而降低新客获取。

---

### 2.4 用 GAQL + Python 创建 PMax 系列与资产组

这一节给出真实可跑的 Python 代码，使用脚本里 `google_ads_api.py` 的
方法。我们创建一个 `PERFORMANCE_MAX_FOR_GOALS` 系列，并给它挂上资产组。

先从查询当前 PMax 系列开始：

```python
# -*- coding: utf-8 -*-
"""
创建 PMax 系列 + 资产组 的完整示例
依赖: scripts/google_ads_api.py 中的 GoogleAdsClient
"""
import json
from google_ads_api import GoogleAdsClient

CUSTOMER_ID = "1234567890"
MAX_CUSTOMER = "8765432"          # 用于展示目标(conversion goal)

def load_client() -> GoogleAdsClient:
    with open("credentials.json") as f:
        creds = json.load(f)
    return GoogleAdsClient(creds)

client = load_client()

# ---------- Step 0: 先看账户里已有的 PMax 系列 ----------
gaql_pmax = (
    "SELECT campaign.id, campaign.name, campaign.status, "
    "campaign.advertising_channel_type, "
    "campaign.advertising_channel_sub_type, "
    "campaign.optimization_score "
    "FROM campaign "
    "WHERE campaign.advertising_channel_type = 'PERFORMANCE_MAX'"
)
resp = client.search(CUSTOMER_ID, gaql_pmax)
for row in (resp.data or {}).get("results", []):
    print(row)

# ---------- Step 1: 创建 PMax 系列 ----------
campaign_body = {
    "name": "Q3 美妆 D2C - PMax 全渠道",
    "advertising_channel_type": "PERFORMANCE_MAX",
    "advertising_channel_sub_type": "PERFORMANCE_MAX_FOR_GOALS",
    "status": "PAUSED",                      # 先暂停, 配好资产组再启用
    # 预算(可选: 用 shared 预算或 campaign_budget)
    "bidding_strategy": {
        # 目标 ROAS 示例; 也可用 MAXIMIZE_CONVERSION_VALUE
        "target_roas": {"target_roas_micros": 5000000}  # 5.0 ROAS
    },
    "conversion_goal": f"customers/{CUSTOMER_ID}/conversionGoals/1",
    "campaign_budget": {
        "amount_micros": 500000000,          # 500 元 / 天
        "delivery_method": "STANDARD",
    },
}
create_resp = client.create_campaign(CUSTOMER_ID, campaign_body)
print("create_campaign ->", create_resp.data)

# ---------- Step 2: 创建资产组(Asset Group) ----------
asset_group_body = {
    "name": "AG_洁面乳_新客",
    "status": "ENABLED",
    "campaign": f"customers/{CUSTOMER_ID}/campaigns/<CAMPAIGN_ID>",
    "final_mobile_urls": ["https://shop.example.com/cleanser"],
    "final_urls": ["https://shop.example.com/cleanser"],
    # 资产: 标题/描述/图片/视频/Logo(逐项)
    "headlines": [
        {"text": "敏感肌专用洁面乳"},
        {"text": "温和不紧绷, 锁水保湿"},
        {"text": "限时 7 折, 立即抢购"},
    ],
    "descriptions": [
        {"text": "氨基酸温和配方, 敏感肌友好, 深层清洁同时锁水。"},
        {"text": "30 天无理由退换, 顺丰包邮, 今日下单立减。"},
    ],
    "images": [
        {"image_url": "https://img.example.com/cleanser-1.jpg"},
        {"image_url": "https://img.example.com/cleanser-2.png"},
    ],
    "logos": [
        {"image_url": "https://img.example.com/logo.png"},
    ],
    # 受众信号: 提示而非限制
    "audience": {
        "audiences": [
            # 自定义细分(意向)
            {"custom_audience": {"members": [
                {"keyword": "氨基酸洁面"},
                {"keyword": "敏感肌 洗面奶"},
                {"url": "https://rival-cosmetics.com"},
            ]}},
            # 再营销: 网站访客 30 天
            {"user_list": {"user_list_memberships": [
                {"user_list_id": "<REMARKETING_LIST_ID>"},
            ]}},
        ]
    },
}
ag_resp = client.create_ad_group(CUSTOMER_ID, asset_group_body)
print("create_asset_group ->", ag_resp.data)
```

> 说明：上面 `create_ad_group` 在 PMax 语境里实际对应的是创建资产组
> （Asset GroupService 的 CREATE 操作）。脚本为通用性复用了 ad_group 端点，
> 实战中应调用 `AssetGroupService.MutateAssetGroups`；这里展示方法名与
> 数据形状即可。

**创建素材的补充**：除了资产组内联素材，你还可以单独上传图片/视频资产，
再用 `asset_group_asset` 绑定。这样便于复用同一张图到多个资产组。

```python
# ---------- Step 3: 单独上传资产并绑定到资产组 ----------
# 上传一张图片资产
upload_body = {
    "type_": "IMAGE",
    "image_asset": {
        "image_url": "https://img.example.com/new-prime.jpg",
        "mime_type": "image/jpeg",
    },
}
client.create_ad(  # 复用 ad 端点做演示, 实战用 AssetService
    CUSTOMER_ID, upload_body
)

# asset_group_asset 绑定(资产组与资产是多对多)
# 可用 GAQL 查询当前资产组里的资产:
resp2 = client.search(
    CUSTOMER_ID,
    "SELECT asset_group.id, asset_group.name, "
    "      asset_group_asset.asset, asset_group_asset.field_type "
    "FROM asset_group_asset "
    "WHERE asset_group.id = <AG_ID>"
)
for row in (resp2.data or {}).get("results", []):
    print("asset binding:", row)
```

---

### 2.5 用 generate_report 拉取 PMax 诊断

脚本里的 `generate_report(customer_id, date_range)` 方法会生成一个基础报表。
但 PMax 诊断通常需要更细的字段，所以我们既用它，也用更完整的 GAQL。

```python
# -*- coding: utf-8 -*-
"""PMax 级报表与资产组级诊断"""
from google_ads_api import GoogleAdsClient
import json

CUSTOMER_ID = "1234567890"

def load_client() -> GoogleAdsClient:
    with open("credentials.json") as f:
        return GoogleAdsClient(json.load(f))

client = load_client()

# ---------- 用法一: generate_report 基础报表 ----------
date_range = {"start": "2026-08-01", "end": "2026-08-14"}
report = client.generate_report(CUSTOMER_ID, date_range)
for row in (report.data or {}).get("results", []):
    print(row)

# ---------- 用法二: 资产组级诊断(核心) ----------
gaql_asset_group = (
    "SELECT campaign.name, "
    "       asset_group.name, asset_group.id, asset_group.status, "
    "       metrics.impressions, metrics.clicks, "
    "       metrics.cost_micros, "
    "       metrics.conversions, metrics.all_conversions, "
    "       metrics.conversions_value, "
    "       metrics.ctr, metrics.cpc_micros, "
    "       metrics.optimization_score_weight "
    "FROM asset_group "
    "WHERE segments.date DURING LAST_14_DAYS "
    "AND campaign.advertising_channel_type = 'PERFORMANCE_MAX'"
)
ag_resp = client.search(CUSTOMER_ID, gaql_asset_group)
for row in (ag_resp.data or {}).get("results", []):
    print(row)

# ---------- 用法三: 素材强度与素材级表现 ----------
gaql_assets = (
    "SELECT asset.id, asset.name, asset.type, "
    "       asset_group_asset.performance_label, "   # 素材强度
    "       asset_group_asset.policy_summary_info.review_status, "
    "       metrics.impressions "
    "FROM asset_group_asset "
    "WHERE segments.date DURING LAST_14_DAYS"
)
assets_resp = client.search(CUSTOMER_ID, gaql_assets)
for row in (assets_resp.data or {}).get("results", []):
    print(row)

# ---------- 用法四: 渠道维度(聚合可见性) ----------
gaql_channel = (
    "SELECT campaign.name, segments.ad_network_type, "
    "       metrics.impressions, metrics.clicks, metrics.cost_micros, "
    "       metrics.conversions, metrics.conversions_value "
    "FROM campaign "
    "WHERE segments.date DURING LAST_14_DAYS "
    "AND campaign.advertising_channel_type = 'PERFORMANCE_MAX' "
    "AND segments.ad_network_type != 'UNKNOWN'"
)
chan_resp = client.search(CUSTOMER_ID, gaql_channel)
for row in (chan_resp.data or {}).get("results", []):
    print(row)
```

> 注意：`segments.ad_network_type` 对 PMax 常返回聚合（如把多个渠道并入
> `CONTENT` 或 `SEARCH` 展示）。这正印证了上一章的"可见性光谱"——
> 渠道维度只能看到系统愿意给你的粒度。

---

### 2.6 用 Go 检查素材强度与资产组合

Python 适合快速探查，生产级自动化常用 Go。这一节给出 Go 版素材强度检查。
Google 的 Go 客户端是 `github.com/googleapis/google-ads-go`，配合
REST 调用也可。这里用更轻的方式：直接手写 GAQL 请求，依赖注入 token。

```go
// materials_strength.go
// 用 Go 检查 PMax 素材强度(asset strength) 与资产分布
package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"time"
)

const (
	baseURL = "https://googleads.googleapis.com/v24"
	customerID = "1234567890"
)

type gaqlRequest struct {
	Query string `json:"query"`
}

type gaqlResponse struct {
	Results []map[string]interface{} `json:"results"`
}

// search 执行一条 GAQL 查询
func search(token, query string) (*gaqlResponse, error) {
	body, _ := json.Marshal(gaqlRequest{Query: query})
	req, _ := http.NewRequest(
		"POST",
		fmt.Sprintf("%s/customers/%s:search", baseURL, customerID),
		bytes.NewReader(body),
	)
	req.Header.Set("Authorization", "Bearer "+token)
	req.Header.Set("developer-token", os.Getenv("DEVELOPER_TOKEN"))
	req.Header.Set("login-customer-id", os.Getenv("LOGIN_CUSTOMER_ID"))
	req.Header.Set("Content-Type", "application/json")

	client := &http.Client{Timeout: 30 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	data, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, err
	}
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("HTTP %d: %s", resp.StatusCode, string(data))
	}
	var out gaqlResponse
	if err := json.Unmarshal(data, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

// AssetStrength 素材强度档位映射 map[int]string
func assetStrengthLabel(s float64) string {
	switch {
	case s >= 80:
		return "优秀 Excellent"
	case s >= 50:
		return "良好 Good"
	case s >= 20:
		return "一般 Average"
	default:
		return "待改进 Poor"
	}
}

func main() {
	token := os.Getenv("ACCESS_TOKEN")
	q := `
		SELECT campaign.name,
		       asset_group.name,
		       asset_group.id,
		       asset_group_asset.asset,
		       asset_group_asset.field_type,
		       asset_group_asset.performance_label,
		       metrics.impressions
		FROM asset_group_asset
		WHERE segments.date DURING LAST_14_DAYS
	`
	resp, err := search(token, q)
	if err != nil {
		fmt.Fprintln(os.Stderr, "search failed:", err)
		os.Exit(1)
	}

	// 按资产组聚合素材强度与数量
	byGroup := map[string]map[string]int{}
	for _, r := range resp.Results {
		ag := fmt.Sprint(r["asset_group"])
		if byGroup[ag] == nil {
			byGroup[ag] = map[string]int{}
		}
		ft := fmt.Sprint(r["asset_group_asset.field_type"])
		byGroup[ag][ft]++
	}

	fmt.Printf("%-28s %-10s %s\n", "AssetGroup", "Strengths", "AssetMix")
	for ag, mix := range byGroup {
		fmt.Printf("%-28s %-10v %v\n", ag, assetStrengthLabel(0), mix)
	}
}
```

> 实战提示：`asset_group_asset.performance_label` 会给出每个素材的
> `LOW / GOOD / BEST` 档位，这是识别"素材强度"的 API 侧主要依据，
> 配合 UI 里的"素材强度：优秀/良好/一般/待改进"使用。
> Go 版同样要处理分页（`next_page_token`）与限流重试，此处为简洁略写。

---

### 2.7 学习期与 optimization_score 的算法原理

**学习期（Learning Period）**：PMax 每次发生"显著变化"都会触发重新学习。
显著变化包括：更改出价策略/目标、大幅调整预算、替换大部分素材、
更改转化目标、更改商品集等。

```
学习期触发源与重置
────────────────────────────────────────────────────────────
  触发源                    是否重置    建议
  预算 ±10% 内             通常否      允许
  预算 ±20%+               可能否/是   谨慎
  出价目标 tROAS ±10%      影响小      观察
  替换 >50% 素材           是          避免频繁
  新建资产组               该 AG 重学   分批上线
  更换转化行为             是          慎重
  暂停/重新启用            可能否       少做

  学习期时长经验:
    新账户 + 无历史   = 更长(可达 14-30 天)
    有历史数据账户    = 3-7 天
    高预算(>5k/天)    = 1-3 天(数据多收敛快)
    低预算(<500/天)   = 潜伏期更长
```

**optimization_score（优化分数）**：0-100 的账户/系列级健康分，
由 Google 根据"当前配置距离理想配置的差距"计算。数值越高越好。

```
optimization_score 的构成直觉
────────────────────────────────────────────────────────────
  score 接近 100       配置几乎无优化空间
  score 60-85         良好, 仍有预算/素材优化点
  score 40-60         存在明显问题(如素材不足/预算受限)
  score <40           结构性问题(如仅一个资产组/缺转换目标)

  改善优化分数的动作:
  - 增加资产组数量与素材多样性
  - 预算充足(避免"预算受限"警告)
  - 使用目标 CPA/ROAS 而非最大化点击
  - 启用搜索词洞见并优化排除
  - 合并稀碎的小系列, 集中数据
```

`optimization_score` 对 PMax 尤其有用，因为它给了暗箱一个"健康度仪表盘"，
让我们在看不到词级/渠道级细节的情况下仍能判断"系统状态是否健康"。

---

### 2.8 Performance Planner 的预测与模拟模型

Performance Planner 是 Google Ads 的前瞻性工具，专为回答
"如果我增加/减少预算或调整出价，ROAS、点击、转化会变成多少？"。

它的核心是一个**经济计量模型（econometric model）**，分三层：

```
Performance Planner 三层预测模型
────────────────────────────────────────────────────────────

  层1 需求(impression supply)预测
       - 该系列/关键词在未来 googles 会获得多少可用的展示机会
       - 基于历史季节性 + 市场趋势 + 用户规模变化

  层2 成本与点击响应(CPC<->impression share 的 bid-response 曲线)
       - 估算"提高出价 X% → 展示份额提升 → 点击量提升"的边际曲线
       - 本质是一组 bid/impression_share 的弹性估计

  层3 转化与价值(conversion 与 ROAS 映射)
       - 点击 → 转化率(考虑转化时间窗归因)
       - 转化 → 转化价值(考虑不同渠道组合)

  输出:
   - 预算预算下的预估点击/转化/花费/ROAS
   - "关键点(knee point)": 继续加预算 ROAS 开始显著下降的最优点
```

Planner 之所以好用，是因为它能给你每档预算下的边际 ROAS，
帮你找到 **"再加 1000 元预算，能换回多少净转化价值"** 的答案——
这正是季度预算规划（Budget Allocation）的基础。

```
预算-ROAS 响应的"关键点"示意
────────────────────────────────────────────────────────────
 预算(日)   预估花费    ROAS      边际ROAS    判断
  500        460        5.8       -           起点
  1000       940        5.4       5.0        健康
  1500       1410       5.0       4.2        接近关键点
  2000       1880       4.4       2.8        ROI下降
  2500       2350       3.8       1.2        过度投放
                ──▲──
                 关键点 kink: <此点加预算划算, >此点 ROAS 坍塌
```

Planner 也有局限：它基于过往数据外推，遇到大促（双十一、黑五）的剧烈
需求波动时预测会偏乐观。所以实战中，Planner 的产出要叠加上"季节性系数"
与"增量观测"再落地。第三章的美妆 D2C 案例会完整演示。

---

### 2.9 转化时间窗口与归因数学（承上启下）

归因是 PMax 暗箱的最后一层，也是"为什么花费看起来漂移"的最大解释变量。
我们把它放到第五部分专门展开，但先在这里给出一个引子：**转化时间窗口
（conversion window）** 决定了一次点击/曝光后的转化"记到谁头上、记多久"。

```
转化时间窗口(Conversion Window)
────────────────────────────────────────────────────────────
  默认点击后 30 天 / 展示后(浏览型) 1 天(可配置)
  - 点击转化窗口: 点击后 30 天内产生的转化都归因给该点击
  - 浏览转化窗口: 曝光的"查看后"转化(不点击), 默认短(通常为 1 天)

  窗口长度的影响:
  长窗口(30天)  → 归因更多"延迟转化", ROAS 表面更高, 但更难实时反馈
  短窗口(7天)   → 反馈更快, 但漏掉长决策周期(LTV 高)的用户

  PMax 中的 tROAS 使用 "转化价值" 累加, 若窗口短会低估慢决策类目。
```

对 DDA（数据驱动归因）的完整推导，请看 2.10 起的跨渠道归因专节。
那里会用到马尔可夫链、Shapley 值等数学工具，把"Google 怎么分功劳"
讲到底。

---

### 2.10 跨渠道归因（数学推导）：功劳如何分配

归因是 PMax 暗箱的最后一层：一次转化往往由多次跨渠道、跨设备交互触发，
Google 必须决定功劳分给谁、分多少。这一节从形式化定义出发，完整推导
数据驱动归因（DDA）的 Shapley 值公式，并讲清转化时间窗口、Google Signals
与隐私沙盒对测量与优化的影响。

（本节与第四部分 4.12 呼应：理解归因口径差异，是判断 PMax ROAS 可信度的前提。）
### 2.11 归因问题的形式化

一次转化（如购买）可能由多次曝光/点击触发，分布在多个渠道、多个设备、
多天。归因要回答：**这 $N$ 种因素分别贡献了多大比例？**

设用户路径为一个时间有序的事件序列：

```
path = [e1, e2, e3, ..., eK]   (ei = 渠道/设备/素材 上的曝光或点击)
```

我们定义一个**转化结果函数** F：

- F(path) = 1, 表示产生转化
- F(path) = 0, 表示未转化

归因模型给每条路径K个系数 α_ei ≥ 0，满足 Σ α_ei = 1。

**Last Click（末次点击）** 是最简单的模型：

```
α_eK = 1,  其它 α_ei = 0

即: 只有最后一次点击拿到全部功劳
```

```
路径:   Search点击 → Display曝光 → YouTube点击 → [购买]
LastClick分配:                          ↑ 100% YouTube
```

Last Click 的优点：可解释、与"转化当天行为"强相关。
缺点：完全忽略漏斗上方的功劳，会系统性系统性低估上漏斗渠道，
恰好是 PMax 这种多渠道产品的死穴。

**数据驱动归因（DDA）**：用机器学习从数据中学习 α_ei，
不靠人工设定权重。下节给出数学。

---

### 2.12 数据驱动归因（DDA）的数学推导

Google Ads 的 DDA 采用的是**基于 Shapley 值**（源自合作博弈论）的归因。
Shapley 值的核心思想：给渠道分配的功劳，等于"该渠道在所有可能的
渠道组合中的边际贡献"取平均。

假设渠道集合 S = {A, B, C}（三个渠道），转化实际发生。
Shapley 值对渠道 i 的定义：

```
φ_i = Σ_{T ⊆ S \ {i}}  [ |T|! · (|S|-|T|-1)! / |S|! ] · ( v(T∪{i}) - v(T) )

其中:
  v(T) = 仅由 T 中渠道组成的用户集合的实际转化率
  |T|  = 子集 T 的渠道数量
  |S|  = 总渠道数
  v(T∪{i}) - v(T) = 渠道 i 加入子集 T 后带来的转化率增量(边际贡献)
```

直观解释：Shapley 值把每个渠道的功劳计算为"把它加进每一个可能的
已有渠道组合时，转化率的提升量"在所有排列顺序上的平均。

**三渠道例子**：

```
渠道: A, B, C。设转化率 v():
  v(∅)=0, v({A})=0.3, v({B})=0.5, v({C})=0.2
  v({A,B})=0.7, v({A,C})=0.4, v({B,C})=0.8
  v({A,B,C})=1.0

计算 B 的 Shapley 值 φ_B(需要遍历所有不含 B 的子集):
  子集 T=∅:   v({B}) - v(∅)        = 0.5 - 0    = 0.5   权重 1/3
  子集 T={A}: v({A,B}) - v({A})     = 0.7 - 0.3 = 0.4   权重 1/6
  子集 T={C}: v({B,C}) - v({C})     = 0.8 - 0.2 = 0.6   权重 1/6
  子集 T={A,C}:v({A,B,C}) - v({A,C})= 1.0 - 0.4 = 0.6   权重 1/3

  φ_B = 0.5·(1/3) + 0.4·(1/6) + 0.6·(1/6) + 0.6·(1/3)
      = 0.1667 + 0.0667 + 0.1 + 0.2
      ≈ 0.533

同理可得 φ_A、φ_C, 三者之和 ≈ 1。B 贡献最大, 因为它叠加后转化率涨幅最稳。
```

这套计算的工程实现，需要对每个渠道组合用真实转化数据估计 v(T)。
Google 在 PMax/广告系列报表里，就是用这种 DDA 把一次转化价值的功劳
同时分配给整条路径上的多个渠道——这也解释了为什么 PMax 的 ROAS 是
"多渠道分摊"后的结果，而不是 last click 口径。

---

### 2.13 归因时间窗与衰减（Attribution Window）

除了功劳分配，归因还涉及"时间窗"（多久内的转化算这次点击的）。

```
转化时间窗(常用配置)
────────────────────────────────────────────────────────────
  点击转化窗   7天 / 30天(可配)   ← 点击后多久内转化归属
  浏览转化窗   1天(展示后不点击)  ← 曝光后1天内的"查看后转化"

  时间窗对 ROI 的影响:
  长窗(30天)   ROAS 更高(收纳更多延迟转化), 但反馈慢, 波动大
  短窗(7天)    反馈快, 适合快速迭代, 但漏掉慢决策用户

  衰减(decay) 可选: 距交互越近, 功劳越大(triangle decay 等)
```

**时间窗与 PMax 出价的联动**：PMax 的 tROAS 用的是"窗口内判定"的转化
价值累加。若你的用户决策慢（如大件/高客单），30 天窗会显著抬升表面
ROAS，但你要意识到：**更高的表面 ROAS 不代表每一分钱都真正赚到**，
因为里面包含大量在未来 30 天才确认的延迟转化。

实战建议：
- 决策周期短（快消）→ 7 天窗 + 快速迭代。
- 决策周期长（高客单/车房/教育）→ 30 天窗，但用增量测量验证。

---

### 2.14 Google Signals：跨设备归因的底座

Google Signals 是 GA4 里的一项设置，本质是**利用已登录用户的跨设备、
跨浏览器标识**来把同一用户的匿名化轨迹拼合起来。

```
Google Signals 的作用
────────────────────────────────────────────────────────────
  → 跨设备(手机/平板/桌面)识别同一用户
  → 跨会话合并用户旅程, 改善归因与受众
  → 增强"跨渠道转化"的判定, 支撑 DDA 训练
  → 提供更准确的用户画像(需符合隐私红线)

  注意:
  - Signals 需要用户同意(在欧洲需 CMP/Consent Mode v2)
  - 是"抽样增强", 不是 100% 全量拼接
  - 广告报告可能出现"增强转化"与基础口径差异
```

对 PMax 而言，Signals 让系统能更准确地看到"用户在不同设备上看了广告、
最后在另一个设备转化"，从而把功劳分得更合理，也提升自动出价的训练质量。

---

### 2.15 隐私沙盒（Privacy Sandbox）对归因的影响

Chrome 正在移除第三方 Cookie，隐私沙盒提供替代的测量与定向机制。
对 PMax 与归因的影响要提前认知：

```
隐私沙盒相关组件与影响
────────────────────────────────────────────────────────────
  Topics API        → 兴趣定向替代(Cookie-based interest)
  Protected Audience→ 再营销(FLEDGE)替代
  Attribution Reporting API (ARA)
                    → 跨站转化测量的替代, 提供汇总报告
  Shared Storage    → 跨站状态(频率/频控)

  对归因的影响:
  1. 跨站追踪颗粒度下降(RA/汇总级别, 面向隐私)
  2. 依赖第一方数据(自有站/App)的归因更稳
  3. 延迟归因的精确匹配更难 → 需用建模补偿
  4. 用户同意(Consent Mode v2) 成为基准
```

**给 PMax 运营者的对冲建议**：

```
隐私时代的归因对冲清单
────────────────────────────────────────────────────────────
  - 强化第一方数据: 站内注册/CRM/忠诚度, 建自有用户库
  - 启用 Consent Mode v2: 部分数据可用时做建模补全
  - 用 GA4 + BigQuery 自存原始事件, 脱离第三方依赖
  - 用增量测量(Geo/CAA/开-关实验) 替代对报表 ROAS 的迷信
  - 关注 Google 在各广告平台的"建模转化"补充口径
```

---

## 三、生产环境实战

前两章是"理论"，这一章全是"战壕里的打法"。我们会用四个真实业务场景——
美妆 D2C 电商、GMX 电商、游戏 APP 增长、直播带货/品牌——把 PMax 落地
的每一步、每一份代码、每一个量化指标讲清楚。

---

### 3.1 场景一：美妆 D2C 站用 PMax + Performance Planner 做季度预算规划（完整案例）

**业务背景**：
某美妆 D2C 品牌（自有商城，无线下店），客单价 ¥180，历史转化率 3.2%，
当前日均预算 ¥4000，日均 ROAS 约 4.2。Q3 要冲 300 万营业额，品牌方正
纠结"预算加到多少、分到哪些目标、什么时候加"。

**目标拆解**：

```
Q3 营业额目标拆解
────────────────────────────────────────────────────────────
  目标: Q3(90天) 营业 300 万
  日均营业额 = 300万 / 90 = ¥33,333
  当前 ROAS 4.2 → 需要的日均花费 = 33333 / 4.2 ≈ ¥7,937
  当前日均花费 4000 → 需要提高到 7937 左右(约 +98%)

  风险: 直接把预算翻倍, ROAS 常会下降(边际递减)。
        所以要用 Planner 找到"关键点", 而不是盲目翻倍。
```

**第一步：用 Performance Planner 生成预测表**

我们用 GAQL / Planner 概念，把 4 档预算的边际 ROAS 模拟出来：

```
Performance Planner 预测表(美妆案例, 概念示范)
────────────────────────────────────────────────────────────
  日预算     预估日花费    预估 ROAS    边际ROAS     日净价值(花费*ROAS-花费)
  4000       3820         4.2          -           12,224
  6000       5750         4.1          3.4         17,825
  8000       7630         3.9          2.6         22,127
  10000      9480         3.6          1.8         24,648   ← 关键点附近
  12000      11250        3.2          1.0         24,750   ← 接近盈亏平衡
```

> 关键点推断：边际 ROAS 在 8000→10000 档从 2.6 掉到 1.8，
> 且净价值增速趋缓，说明"再多投的每一块钱，ROI 已经很薄"。
> 对美妆这种低客单、高复购品，我们会停在 **日预算 8000** 左右，
> 而不是追到 12000。

**第二步：决定如何"加预算"——不是一次性翻倍**

一次性翻倍最容易触发学习期重置 + ROAS 坍塌。正确打法是**阶梯式加码**：

```
阶梯式加预算节奏(建议)
────────────────────────────────────────────────────────────
  第 0 周   日预算 4000(基线)
  第 1 周   日预算 5000 (+25%)   观察 7 天
  第 2 周   日预算 6500 (+30%)   若 ROAS ≥ 3.8 则继续
  第 3 周   日预算 8000 (+23%)   停止加码, 进入稳定期
  第 4+ 周  按 Planner 微调      ±10% 内做节奏优化

  加码守则:
  - 每次增幅控制在 20%-30%, 不要翻倍
  - 每档至少观察 5-7 天, 用 7 天滚动 ROAS 判断
  - 加预算后 tROAS 可先不变, 等稳定再尝试下调
```

**第三步：用 Python 脚本驱动预算阶梯**

```python
# -*- coding: utf-8 -*-
"""美妆 D2C 季度预算规划落地: 阶梯加预算 + 监控"""
from google_ads_api import GoogleAdsClient
import json, time

CUSTOMER_ID = "1234567890"
PM_CAMPAIGN_ID = "9876543210"

def load_client() -> GoogleAdsClient:
    with open("credentials.json") as f:
        return GoogleAdsClient(json.load(f))

client = load_client()

STEPS = [5_000_000_000, 6_500_000_000, 8_000_000_000]  # 500/650/800元(微)

def get_7d_roas() -> float:
    q = (
        "SELECT metrics.cost_micros, metrics.conversions_value "
        "FROM campaign WHERE segments.date DURING LAST_7_DAYS "
        f"AND campaign.id = {PM_CAMPAIGN_ID}"
    )
    r = client.search(CUSTOMER_ID, q)
    for row in (r.data or {}).get("results", []):
        cost = int(row["metrics"]["costMicros"])
        val = int(row["metrics"]["conversionsValue"])
        return (val / cost) if cost else 0.0
    return 0.0

for new_budget in STEPS:
    # 1) 先记录当前 ROAS
    roas_before = get_7d_roas()

    # 2) 更新预算
    upd = {
        "campaign_budget": {
            "amount_micros": new_budget,
            "delivery_method": "STANDARD",
        }
    }
    print(f"[STEP] 预算 -> ¥{new_budget//1_000_000_000}")
    resp = client.update_campaign(CUSTOMER_ID, PM_CAMPAIGN_ID, upd)
    print("  update_campaign ->", resp.data)

    # 3) 人工观察 7 天(脚本中可用 schedule; 这里示意等待)
    time.sleep(7 * 24 * 3600)

    roas_after = get_7d_roas()
    print(f"  ROAS {roas_before:.2f} -> {roas_after:.2f}")

    # 4) 若 ROAS 显著跌破目标(3.5), 停止加码并标记预警
    if roas_after < 3.5:
        print("  ⚠️ ROAS 跌破 3.5, 暂停加码, 回退上一档")
        break

print("[DONE] 季度预算阶梯执行完成")
```

> 提示：真实生产中 `time.sleep(7天)` 不可行，应把"加档"做成定时任务
>（如 cron / 工作流调度），每档执行一次更新 + 记录，由人审阅后再手动
> 触发下一档。这里为演示把节奏写在一个脚本里。

**第四步：把预算拆分到多个资产组/目标**

光加总预算不够，还要决定钱分给谁。美妆场景我们通常拆三个 PMax 系列：

```
预算分配矩阵(美妆 D2C)
────────────────────────────────────────────────────────────
  系列                   目标        预算占比   素材重点
  PMax_新客_搜索(类目)   新客获取     45%       通用卖点+自定义细分(意向)
  PMax_老客_再营销        复购/召回   35%       会员素材+再营销受众
  PMax_爆品_单品          单品冲刺     20%       爆品素材+新品信号

  ROAS 参考:
  再营销目标 ROAS 通常可设更高(5-6), 新客目标 ROAS 设较低(3-4)
  整体按"新客优先 + 老客护盘"加权
```

**第五步：用排除文件 + 搜索词洞见 做防守**

加预算后常遇到"低质流量变多"。防守手段是把搜索词洞见里"与业务无关"
的查询批量排除（见下一节与第四章排查）。

---

### 3.2 场景二：GMX 电商（Merchant Center 集成 + 商品分组）

GMX（General Merchandise experience）是 PMax 在电商侧的深化，核心是
把 Merchant Center 的 **商品粒度** 数据和 PMax 的全渠道自动化打通。

**Merchant Center 集成流程**：

```
GMX + Merchant Center 数据流
────────────────────────────────────────────────────────────
  1. 商品主数据(ERP/PIM) ──▶ 内容 API / SFTP / 自动提报
  2. Merchant Center feed 字段校验
  3. feee 进入 Google Shopping / PMax(Shopping 目标)
  4. PMax 按商品分组(品类/价格带/利润带)决定素材与出价
  5. 转化回传 → 商品级表现报告 → 反哺 feed 优化

  feed 必备字段:
   id, title, description, link, image_link,
   price, availability, condition, brand,
   gtin, mpn, google_product_category,
   item_group_id(颜色/尺寸归组)
```

**Feed 字段与质量检查清单**（决定商品能否被有效投放）：

| feed 字段 | 作用 | 质量要点 |
|-----------|------|----------|
| id | 唯一标识 | 稳定, 不与 SKU 冲突 |
| title | 匹配与投放核心 | 含"品牌+类型+关键属性" |
| description | 长尾匹配 | 自然嵌入卖点与场景词 |
| image_link | 主图 | 白底 1080x1080 以上, 无水印 |
| google_product_category | 商品分类 | 尽量细分类目 |
| price / sale_price | 价格与促销 | 促销需在 feed 更新 sale_price |
| availability | 库存 | 缺货及时改为 out_of_stock |
| item_group_id | 变体归组 | 颜色/规格同组便于展示切换 |

**商品分组（Product Groups）实战**：

GMX 允许你把商品集（product feeds）映射到不同资产组，实现"分组投放"。
常见分组维度：品类、价格带、利润带、新旧品、库存深度。

```
商品分组策略示例(美妆/服装)
────────────────────────────────────────────────────────────
  资产组A  "高毛利爆品"     = 价格 ¥150-300 + 利润>=40% 的商品
  资产组B  "引流入门款"     = 价格 <¥100 的平价单品
  资产组C  "清仓尾货"       = 有折扣 sale_price 的库存
  资产组D  "新品首发"       = 近 14 天上架的商品

  分组目的:
  - 高毛利品 → 目标 tROAS 可设高, 冲利润
  - 引流款   → 拉新客, 保转化种子
  - 尾货     → 快速去库存, 容忍较低 ROAS
  - 新品     → 学习期保护, 给足预算
```

**用 GAQL 看商品级表现**：

```python
# -*- coding: utf-8 -*-
"""GMX 商品级表现查询"""
from google_ads_api import GoogleAdsClient
import json

CUSTOMER_ID = "1234567890"

def load_client() -> GoogleAdsClient:
    with open("credentials.json") as f:
        return GoogleAdsClient(json.load(f))

client = load_client()

# 商品级表现(基于 shopping product)
gaql_product = (
    "SELECT segments.product_item_id, "
    "       segments.product_title, "
    "       segments.product_type_l1, segments.product_type_l2, "
    "       metrics.impressions, metrics.clicks, "
    "       metrics.cost_micros, metrics.conversions, "
    "       metrics.conversions_value, "
    "       metrics.ctr, metrics.cpc_micros "
    "FROM shopping_product "
    "WHERE segments.date DURING LAST_30_DAYS "
    "ORDER BY metrics.cost_micros DESC"
)
resp = client.search(CUSTOMER_ID, gaql_product)
for row in (resp.data or {}).get("results", []):
    print(row)
```

**价格与促销的最佳实践**：

```
GMX 价格/促销实践
────────────────────────────────────────────────────────────
  - sale_price 必须在 feed 中显式声明, 且 ≤ 原价
  - 促销标签(如"限时7折") 建议用 asset_group_asset 的
    CALLOUT / PRICE 素材呈现, 而不是只靠价格本身
  - 大促前用 Performance Planner 预演预算, 避免当日超预算被系统
    自动降低出价
  - 价格波动频繁的商品, 同步 feed 频率要快(支持实时/2-4h回查)
  - 避免"永远促销": 长期低价会拉低体验与感知价值
```

**GMX 与标准 PMax 的取舍**：

| 维度 | 标准 PMax (FOR_GOALS) | GMX / Shopping 目标 |
|------|----------------------|--------------------|
| Feed 依赖 | 可选(可仅用 URL+资产) | 必须(Merchant Center) |
| 商品粒度 | 无 | 有, 商品级出价/报告 |
| 商品分组 | 无 | 支持, 映射资产组 |
| 适用 | 服务、线索、泛电商 | 标准 SKU 电商 |
| 素材 | 标题/描述/图片/视频 | 商品图+促销素材 |

击点：**做标准 SKU 电商，优先上 Shopping 目标的 GMX；做服务/线索/无 SKU
业务，用通用 PMax。**

---

### 3.3 场景三：游戏 / APP 增长（PMax for Android Apps）

游戏和 APP 增长走 `PERFORMANCE_MAX_FOR_ANDROID_APPS` 或升级自老的
APP_CAMPAIGN。它的特点是优化目标是**应用内转化**（安装、注册、付费、
LTV），素材以**商店素材**和**试玩素材**为主。

**APP 场景的 PMax 特点与打法**：

```
APP 增长 PMax 要点
────────────────────────────────────────────────────────────
  目标类型:
   - 安装(install)           → 拉量
   - 注册/首充/关卡通过       → 高质量用户
   - LTV / 付费事件           → 变现导向

  素材:
   - 商店素材(Play Store listing): 图标/截图/视频/简介
   - 试玩素材(Playable): 可交互 demo, 对转化率影响极大
   - 横竖屏双版本

  出价:
   - app target CPA(tCPA) 或按 ROAS
   - 有条件用 LTV 目标(客户生命周期价值) 做变现优化

  报表:
   - 安装/注册/付费/每安装成本(CPI)/ROAS
   - 用 conversion cross-device 数据修正
```

**代码：创建 PMax for Android Apps 系列 + 应用内转化目标**：

```python
# -*- coding: utf-8 -*-
"""创建 PMax for Android Apps(游戏) 系列"""
from google_ads_api import GoogleAdsClient
import json

CUSTOMER_ID = "1234567890"

def load_client() -> GoogleAdsClient:
    with open("credentials.json") as f:
        return GoogleAdsClient(json.load(f))

client = load_client()

# 1) 查看已配置的转化行为(找安装/付费事件)
convs = client.list_conversion_actions(CUSTOMER_ID)
for c in (convs.data or {}).get("results", []):
    print("conversion:", c)

# 2) 创建 PMax for Apps
body = {
    "name": "SLG手游 东南亚-PMax",
    "advertising_channel_type": "PERFORMANCE_MAX",
    "advertising_channel_sub_type": "PERFORMANCE_MAX_FOR_ANDROID_APPS",
    "status": "PAUSED",
    "app_campaign_setting": {
        "app_id": "com.example.slg",
        "app_vendor": "GOOGLE_PLAY",
    },
    "bidding_strategy": {
        # 按跑ROAS(安装后LTV) 或 tCPA; 这里用 MaxConv 值示例
        "maximize_conversion_value": {}
    },
    "campaign_budget": {
        "amount_micros": 300000000,   # 300 元/天
        "delivery_method": "STANDARD",
    },
}
resp = client.create_campaign(CUSTOMER_ID, body)
print("create PMax-for-apps ->", resp.data)

# 3) 查看该 APP 系列的素材/视频表现
gaql_video = (
    "SELECT video.id, video.name, video.duration_millis, "
    "       metrics.impressions, metrics.clicks, "
    "       metrics.cost_micros, metrics.conversions "
    "FROM video "
    "WHERE segments.date DURING LAST_14_DAYS"
)
vr = client.search(CUSTOMER_ID, gaql_video)
for row in (vr.data or {}).get("results", []):
    print("video:", row)
```

游戏场景的**量化指标**我们通常这样设红线：

```
游戏增长关键红线(参考)
────────────────────────────────────────────────────────────
  安装成本 CPI    休闲<¥3, 中重度<¥10(按品类)
  注册率           安装→注册 ≥ 25%-40%
  首充率           注册→首充 ≥ 5%-8%
  7日LTV           ≥ CPI 才有规模化意义
  D7 留存          休闲≥8%, 中重度≥12%(视品类)
  PMax ROAS       首月 D30 ROAS 目标通常 60-100%+
```

> 提示：游戏 PMax 的 tCPA 建议从"历史 CPI × 1.2"起步，给算法留足
> 学习空间，7 天后若 CPI 过高再逐步收紧。

---

### 3.4 场景四：直播带货 / 品牌 / 线索（代理商视角）

这一节覆盖三小类：直播带货联动、品牌纯曝光、线索（Lead Gen）代理。

**直播带货与 PMax 的联动**：
直播间不是 PMax 的直接投放单元，但 PMax 可以负责"直播间引流"和"直播后
转化"。常见组合：

```
直播带货 × PMax 组合打法
────────────────────────────────────────────────────────────
  直播前 1-3 天: PMax 预热素材(预告+加购), 积累兴趣人群
  直播进行中:   PMax 目标改为"直播间进入/下单", 素材用直播截图
  直播结束后:   PMax 收割"看过+未买"人群, 素材换成"回放/限时"
  指标: 直播 GMV, 观众→下单转化, 拉新率(新客占比)
```

**品牌纯曝光场景**：
品牌客户可能部分用 PMax 补量，但纯品牌更适合用 Video / Display / Demand
Gen。PMax 擅长效果，不擅长"纯曝光不计转化"的品牌任务。需求不匹配时，
不要硬塞给 PMax——用覆盖目标与 CPV/CPM 类系列更合适。

**线索（Lead Gen）代理视角**：
代理商跑大量客户，需要标准化 PMax 模板 + 自动化监控。要点：

```
代理 PMax 运营最佳实践
────────────────────────────────────────────────────────────
  - 模板化: 同一行业用固定资产组/素材/出价模板, 快速冷启
  - 自动化: 用脚本/工作流批量创建 series + 日报, 降低人效
  - 分层: 各客户按预算与目标分级(旗舰/标准/实验)
  - 数据透明: 用报表导出给客户的"词级不可见"解释要预先准备
  - 账期预警: 预算超支/ROAS 下滑的自动告警
```

代理视角尤其要用好**排除文件**与**优化分数**，因为看的是多账户大盘。

---

### 3.5 资产组结构化拆分：实操与代码

资产组拆分是 PMax 优化里"颗粒度管理"的核心手段。原则：**按业务可解释
的维度切分，保证每个资产组主题一致、素材聚焦。**

```
资产组拆分维度优先级(自高到低)
────────────────────────────────────────────────────────────
 1. 产品品类/系列       (美妆→洁面/精华/面霜)
 2. 价格带              (入门/中端/高端)
 3. 客户生命周期         (新客/老客/高价值)
 4. 营销主题/促销         (618/黑五/新品)
 5. 地域分层              (高ROAS区/低ROAS区, 用独立系列)

 反面案例(应避免):
 - 一个资产组塞 20 个品类 → 素材互斥, 模型困惑
 - 素材与信号不匹配      → 意图与创意脱节
 - 过度拆分(每个AG只有1-2素材) → 学习数据不足
```

**用 Python 批量创建一批主题一致的资产组**：

```python
# -*- coding: utf-8 -*-
"""批量创建主题化资产组: 按品类×新客/老客 拆 6 个 AG"""
from google_ads_api import GoogleAdsClient
import json

CUSTOMER_ID = "1234567890"
PM_CAMPAIGN = f"customers/{CUSTOMER_ID}/campaigns/9876543210"

def load_client() -> GoogleAdsClient:
    with open("credentials.json") as f:
        return GoogleAdsClient(json.load(f))

client = load_client()

# 主题: (AG名, 品类关键词, 图片集, 目标)
AG_PLAN = [
    ("AG_洁面_新客", "氨基酸洁面", ["cleanser1.jpg","cleanser2.jpg"], "CLEANSER"),
    ("AG_洁面_老客", "回购洁面",   ["cleanser3.jpg"],               "CLEANSER"),
    ("AG_精华_新客", "抗老精华",   ["serum1.jpg","serum2.jpg"],     "SERUM"),
    ("AG_精华_老客", "回购精华",   ["serum3.jpg"],                  "SERUM"),
    ("AG_面霜_新客", "保湿面霜",   ["cream1.jpg","cream2.png"],     "CREAM"),
    ("AG_面霜_老客", "回购面霜",   ["cream3.jpg"],                  "CREAM"),
]

for name, kw, imgs, cat in AG_PLAN:
    body = {
        "name": name,
        "status": "ENABLED",
        "campaign": PM_CAMPAIGN,
        "final_urls": [f"https://shop.example.com/{cat.lower()}"],
        "headlines": [
            {"text": f"【{cat}系列】今日特惠"},
            {"text": "温和不刺激, 敏感肌可用"},
            {"text": "限时 7 折, 顺丰包邮"},
        ],
        "descriptions": [
            {"text": f"{kw}专研, 深层修护, 敏感肌友好, 30天无理由退换。"},
        ],
        "images": [{"image_url": f"https://img.example.com/{i}"} for i in imgs],
        "logos": [{"image_url": "https://img.example.com/logo.png"}],
    }
    resp = client.create_ad_group(CUSTOMER_ID, body)
    print(f"created {name} ->", resp.data)
```

> 最佳实践总结：资产组数量没有绝对标准，但通常**一个系列 2-6 个资产组**
> 较健康。过少（1 个）会让模型缺少主题区分；过多（>10）会稀释每个
> 资产组的学习数据。小预算账户偏向少而精，大预算可以多而专。

---

### 3.6 素材强度检查清单（Asset Strength）

素材强度是 PMax 可用的、最接近"可见诊断"的维度之一。它把"你的素材
组合得够不够好，让系统有足够的自由组合空间"量化成四档：
优秀(Excellent) / 良好(Good) / 一般(Average) / 待改进(Poor)。

```
素材强度检查清单
────────────────────────────────────────────────────────────
 一、数量维度
   ☐ 图片 ≥ 10 张(不同尺寸/场景)         腰, 只给3张(低) 
   ☐ 视频 ≥ 1-2 个(15s+30s)              无视频(低)
   ☐ 标题 ≥ 5 个/推荐 10-15              只有3个(低)
   ☐ 描述 ≥ 3 个/推荐 5-8                只有1条(低)
   ☐ Logo 1-3 个(透明底)                 缺 Logo(低)

 二、多样性维度
   ☐ 图片含: 产品白底 + 场景 + 卖点特写   全是白底图(差)
   ☐ 标题覆盖: 卖点/价格/痛点/信任/应季   全是同一种文案(差)
   ☐ 描述含 CTA 变化(立即/今日/限时/了解)  单一 CTA(差)
   ☐ 视频时长/节奏有层次(快剪 vs 讲解)    只有一种风格(差)

 三、相关性维度
   ☐ 素材与资产组主题匹配(洁面AG不放面霜素材)
   ☐ 标题避免堆砌无意义关键词
   ☐ 素材符合政策(无违规, review_status 通过)

 四、可操作动作(依据 performance_label)
   - LOW 素材: 替换或重做
   - GOOD: 保留并补充搭配
   - BEST: 保持, 作为方向参考
```

**用代码拉取素材强度并给出行动项**（Go + Python 双实现，Go 版见 2.6）：

```python
# -*- coding: utf-8 -*-
"""素材强度体检: 输出每资产组的素材数量与强度诊断"""
from google_ads_api import GoogleAdsClient
import json
from collections import defaultdict

CUSTOMER_ID = "1234567890"

def load_client() -> GoogleAdsClient:
    with open("credentials.json") as f:
        return GoogleAdsClient(json.load(f))

client = load_client()

gaql = (
    "SELECT asset_group.name, asset_group_asset.field_type, "
    "       asset_group_asset.performance_label, "
    "       COUNT(asset.id) AS cnt "
    "FROM asset_group_asset "
    "WHERE segments.date DURING LAST_14_DAYS "
    "GROUP BY asset_group.name, asset_group_asset.field_type, "
    "         asset_group_asset.performance_label"
)
resp = client.search(CUSTOMER_ID, gaql)

stats = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
for row in (resp.data or {}).get("results", []):
    ag = row["assetGroup"]["name"]
    ft = row["assetGroupAsset"]["fieldType"]
    lbl = row["assetGroupAsset"]["performanceLabel"]
    stats[ag][ft][lbl] = row["metrics"]["count"]

def field_label(ft: str) -> str:
    return {
        "HEADLINE_4": "标题", "DESCRIPTION_2": "描述",
        "IMAGE_1": "图片", "YOUTUBE_VIDEO": "视频",
        "LOGO_4": "Logo",
    }.get(ft, ft)

for ag, fields in stats.items():
    print(f"\n### {ag}")
    for ft, counts in fields.items():
        total = sum(counts.values())
        best = counts.get("BEST", 0)
        low = counts.get("LOW", 0)
        ratio = best / total if total else 0
        flag = "✅" if ratio >= 0.5 else ("⚠️" if low else "◻️")
        print(f"  {flag} {field_label(ft):<6} 共{total:>2} "
              f"BEST={best} LOW={low}")
```

---

### 3.7 账户级诊断脚本（健康大盘）

PMax 运营者最需要的是一套"账户级健康体检"，把散在各个维度的信号聚合成
一张可读的报告。这个脚本把我们前面所有查询组合起来，生成一个结构化诊断。

```python
# -*- coding: utf-8 -*-
"""
账户级 PMax 健康诊断脚本
输出: 1) 各系列汇总  2) 资产组健康  3) 素材强度  4) 转化目标  5) 优化分数
"""
from google_ads_api import GoogleAdsClient
import json

CUSTOMER_ID = "1234567890"

def load_client() -> GoogleAdsClient:
    with open("credentials.json") as f:
        return GoogleAdsClient(json.load(f))

client = load_client()

def report(title, rows):
    print(f"\n===== {title} =====")
    for r in rows or []:
        print(json.dumps(r, ensure_ascii=False))

# 1) 系列级健康(优化分数 + 预算受限)
r1 = client.search(CUSTOMER_ID,
    "SELECT campaign.name, campaign.status, "
    "       campaign.optimization_score, campaign.optimization_score_weight, "
    "       campaign_budget.amount_micros, campaign_budget.explicitly_shared, "
    "       metrics.cost_micros, metrics.conversions, metrics.conversions_value "
    "FROM campaign "
    "WHERE campaign.advertising_channel_type = 'PERFORMANCE_MAX' "
    "AND segments.date DURING LAST_14_DAYS "
    "ORDER BY metrics.cost_micros DESC")
report("系列级健康", (r1.data or {}).get("results", []))

# 2) 资产组健康
r2 = client.search(CUSTOMER_ID,
    "SELECT asset_group.name, asset_group.status, "
    "       metrics.impressions, metrics.clicks, metrics.cost_micros, "
    "       metrics.conversions, metrics.conversions_value, "
    "       metrics.ctr "
    "FROM asset_group "
    "WHERE campaign.advertising_channel_type = 'PERFORMANCE_MAX' "
    "AND segments.date DURING LAST_14_DAYS")
report("资产组健康", (r2.data or {}).get("results", []))

# 3) 转化目标清单
r3 = client.list_conversion_actions(CUSTOMER_ID)
report("转化目标", (r3.data or {}).get("results", []))

# 4) 排除文件/关键词(若存在)
r4 = client.search(CUSTOMER_ID,
    "SELECT keyword.text, keyword.match_type, ad_group_criterion.negative, "
    "       campaign.name "
    "FROM ad_group_criterion "
    "WHERE ad_group_criterion.type = 'KEYWORD' "
    "AND ad_group_criterion.negative = TRUE")
report("负向关键词", (r4.data or {}).get("results", []))

# 5) 出价策略概览
for opt in client.get_bid_strategy_options():
    if opt["code"] in ("TARGET_ROAS", "MAXIMIZE_CONVERSION_VALUE"):
        print("可参考出价策略:", opt)
```

这个脚本的输出可以直接喂给内部看板（存成 JSON / 写库），让团队每天
用同一套口径看 PMax 大盘，避免口径不一致。

---

### 3.8 季度预算规划落地（Performance Planner 全流程）

把第二章的理论和 3.1 的案例串起来，这里给一套可复用的年/季度规划 SOP：

```
季度预算规划 SOP
────────────────────────────────────────────────────────────
  Step 0  目标设定
          从业务目标(营业额/新客数/毛利)反推 PMax 需要的 ROAS/花费
  Step 1  Performance Planner 模拟
          列 4-6 档预算, 拉取对应预估 ROAS/点击/转化, 找关键点
  Step 2  增量判断
          结合 last-click vs 增量(Geo/CAA) 判断"Planner 是否乐观"
  Step 3  预算分配
          把预算按 新客/老客/爆品 分配到多个系列(见3.1矩阵)
  Step 4  阶梯上量
          每档 +20-30%, 每档观察 5-7 天, 防学习期重置
  Step 5  监控与回授
          用 3.7 诊断脚本 + 7 天滚动 ROAS 护栏, 超限自动告警
  Step 6  季度复盘
          用 GA4/归因数据验证 Planner 偏差, 校准下一季参数
```

**关键护栏指标**（写进监控系统）：

| 指标 | 护栏 | 触发动作 |
|------|------|----------|
| 7 天滚动 ROAS | < 目标×0.85 | 降预算 20% / 收紧排除 |
| 优化分数 | < 60 | 补素材/合并稀碎系列 |
| 学习期状态 | 持续 >14 天 | 检查是否频繁改配置 |
| 预算受限警告 | 出现 | 加预算或降 tROAS |
| 素材强度 | 一般/待改进 | 补足素材多样性 |

---

### 3.9 排除文件（Exclusions）与负向信号实战

PMax 的可见性有限，负向控制（exclusions）是少数"可见的防守工具"。
投放经理必须把这套工具用足，去对冲暗箱带来的"低质流量污染"。

**PMax 支持的负向控制面**：

```
可用(按账户/Campaign)                 不可用(PMax 局限)
────────────────────────────          ────────────────────────────
 排除品牌词(品牌搜索)                   精确的广告组级负向关键词
 负向关键词列表(账户级→应用到PMax)     展示/YouTube 定向排除(部分受限)
 排除特定受众(品牌安全/环境)           部分内容类别排除需账户设置
 地域排除                             素材级定向(由系统决定)

 负向关键词在 PMax 上的写法特殊:
 不能直接在资产组里加"negative keyword"
 要用 "账户级 Negative Keyword List" → 应用到 PMax Campaign 级
```

**排除品牌词的实战价值**：
电商/品牌通常"Search 品牌系列"和"PMax"并存。
若 PMax 也去抢品牌词，会与品牌系列自我竞价，抬高品牌 CPC。
正确分工：

```
品牌词分工(防自我蚕食)
────────────────────────────────────────────────────────────
  品牌搜索系列(手动/智能)   = 收割品牌词, 控制品牌 CPC
  PMax(非品牌)             = 排除品牌词, 专注探索+全渠道拉新

  操作: 在 PMax 系列挂一个"排除品牌词"的负向关键词列表,
        让 PMax 不碰 brand 查询, 把品牌意向留给品牌系列。
```

**负向关键词列表实战（Python）**：
脚本里的 `create_keywords` 走的是 `adGroupCriteria:mutate`；
PMax 的负向需要账户级列表。这里用真实的 `NegativeKeywordList` +
`CampaignNegativeKeyword` 形态演示，同时展示脚本方法名。

```python
# -*- coding: utf-8 -*-
"""PMax 负向关键词列表实战"""
from google_ads_api import GoogleAdsClient
import json

CUSTOMER_ID = "1234567890"

def load_client() -> GoogleAdsClient:
    with open("credentials.json") as f:
        return GoogleAdsClient(json.load(f))

client = load_client()

# 1) 账户级负向关键词列表(品牌词排除)
NEGATIVE_WORDS = [
    "我们的竞品A", "我们的竞品B", "低质词-免费", "无关词-下载",
]

# 实践中由 NegativeKeywordListService 创建并加 word,
# 这里用 create_keywords 的方法名与 mutate 形态演示
neg_ops = [
    {"keyword": {"text": w, "match_type": "PHRASE"}}
    for w in NEGATIVE_WORDS
]
resp = client.create_keywords(CUSTOMER_ID, "<AG_ID>", neg_ops)
print("negative keyword ops ->", resp.data)

# 2) 把负向列表应用到 PMax Campaign(减法/关联)
# 用 update_campaign 关联账户级负向列表(CampaignNegativeKeyword)
campaign_updates = {
    "campaign_negative_keywords": [
        {"keyword_text": w, "match_type": "PHRASE"}
        for w in NEGATIVE_WORDS
    ]
}
upd = client.update_campaign(CUSTOMER_ID, "9876543210", campaign_updates)
print("attach negatives ->", upd.data)

# 3) 复查系列里的负向关键词
chk = client.search(
    CUSTOMER_ID,
    "SELECT campaign.name, campaign_negative_keyword.keyword.text, "
    "       campaign_negative_keyword.match_type "
    "FROM campaign_negative_keyword "
    "WHERE campaign.id = 9876543210"
)
for row in (chk.data or {}).get("results", []):
    print("negative:", row)
```

**负向信号的运营守则**：

```
排除文件/负向最佳实践
────────────────────────────────────────────────────────────
  1. 基于搜索词洞见的"高花费低转化"主题做排除, 而非拍脑袋
  2. 品牌词排除: 一旦跑品牌搜索系列, 务必从 PMax 剔品牌词
  3. 定期(每月)清理: 负向词太多会过度收紧, 反而抑制扩展
  4. 竞品词: 视策略(抢竞品流量可选保留, 注意政策)
  5. 用"观察期"验证负向效果: 排除后看 7 天转化是否改善
```

这部分配合第四部分 4.1 / 4.6 使用，是"暗箱防守"的完整闭环。

---

## 四、常见问题与排查

这一章给出投放与工程两个视角的高频问题。每个问题都尽量给到
"现象 → 原因 → 排查步骤 → 解决方案"四段式。

---

### 4.1 Q：PMax 看不到关键词，我怎么知道系统在投什么词？

**现象**：报表里没有关键词维度，投放经理感觉"失控"。

**原因**：PMax 用资产组+信号替代关键词，Search 部分按查询实时匹配，
词级归因被隐藏。

**排查**：
1. 用"搜索词洞见（Search terms insights）"看聚合主题。
2. 用排除文件加负向词（部分 PMax 支持排除关键词）。

**解决**：
- 定期导出搜索词洞见，梳理"高花费低转化"主题。
- 与品牌词/竞品词的监控服务（如 SEMrush）结合，间接观察。

---

### 4.2 Q：为什么我的 PMax 某天 80% 预算花在 YouTube，第二天又回到 Search？

**现象**：渠道占比剧烈漂移。

**原因**：这是跨渠道 Bandit 在"探测与利用"间切换的正常现象，不是故障。

**排查**：
1. 看 7/30 天聚合占比，而非单日。
2. 检查是否有素材/信号失衡导致某场景被偏爱。

**解决**：
- 用 7 天滚动口径评估，不因单日恐慌。
- 若某渠道长期 >60% 且 ROAS 下降，用排除文件或素材调整干预。

---

### 4.3 Q：PMax 一直提示"预算受限（Budget Limited）"，我该怎么办？

**现象**：系列出现 "Limited by Budget" 警告，曝光受限。

**原因**：系统判断"多给预算能带来额外转化"，当前预算已经买满。

**排查**：
1. 确认预算确实吃满（每日花费 ≈ 预算）。
2. 用 Performance Planner 看"追加预算的边际 ROAS"。

**解决**：
- 若边际 ROAS 仍达标 → 阶梯加预算（+20-30%/档）。
- 若 ROAS 已在下降 → 保持预算，优化素材提升效率。

---

### 4.4 Q：新 PMax 的学习期到底要多久？为什么一直波动？

**现象**：新系列 CPA/ROAS 忽高忽低，不敢动。

**原因**：系统在探索（探测新用户/素材组合）与利用之间收敛，阶段不稳定。

**排查**：
1. 记录启动以来的配置变更史（是否频繁改素材/预算）。
2. 看是否有"显著变更"不断重置学习期。

**解决**：
- 学习期尽量"少打扰"，给 7-14 天稳定期。
- 变更分批做，避免一次改太多。
- 用优化分数而非单日 ROAS 判断健康度。

---

### 4.5 Q：audience signal 我给了精确受众，为什么 PMax 还投到别的人？

**现象**：系统明显超出信号人群投放。

**原因**：信号是"先验提示"不是"硬限制"，系统用实时特征扩展目标。

**排查**：确认你把信号理解成"种子"而非"白名单"。

**解决**：
- 若要更"守信号"，用更贴近核心客户的信号并配合更严的素材主题。
- 若想做广泛新客探测，其实可以放心让它扩展。

---

### 4.6 Q：PMax ROAS 达标但销售额没增长，怎么回事？

**现象**：ROAS 好看，但 GMV/订单量不涨。

**原因**：ROAS = 转化价值/花费。若只提价上 ROAS，可能牺牲订单量
（高 ROAS 常伴随更少的低价订单）。

**排查**：拆开看订单数、客单价、转化数，别只看 ROAS 单一指标。

**解决**：
- 明确原始目标：若目标是"收入"，设 tROAS 别设太高，保证量。
- 用多指标（订单数×客单价）联合评估，避免被 ROAS 迷惑。

---

### 4.7 Q：PMax 和普通搜索广告会不会互相抢量（自我蚕食）？

**现象**：同时跑 Search 和 PMax，担心预算打架、转化重复计。

**原因**：确实可能发生自我竞价与转化重叠。

**排查**：
1. 用增量测试（如停止其一做对比）看整体是否提升。
2. 检查转化去重（GA4 归因）是否已处理跨系列重复。

**解决**：
- 用 PMax 的"Search 补充"逻辑：PMax 通常不会抢品牌词（可设品牌排除）。
- 明确分工：Search 守明确意图，PMax 做探索+全渠道，减少重叠。

---

### 4.8 Q：GMX 的商品一直没有曝光，feed 也上传了，怎么办？

**现象**：SKU 商品几乎无展示。

**原因**：feed 质量问题、商品被拒审、分组/出价过低、库存状态错误。

**排查**：
1. Merchant Center 诊断：检查商品状态（拒审/缺字段/重复）。
2. 看 ShoppingProduct 报告是否有数据。
3. 检查价格与库存（availability）是否已同步。

**解决**：
- 修复 feed 字段（见 3.2 检查清单）。
- 给新商品"学习期保护"，保证预算。
- 用商品分组把重点 SKU 独立出来给足出价。

---

### 4.9 Q：素材强度显示"待改进"，但我素材很多，为什么？

**现象**：素材数量不少，但强度评分低。

**原因**：强度不只看数量，更看多样性与相关性。

**排查**：
1. 看是数量不足还是多样性不足（全是白底图？标题同质？）。
2. 看是否有违规/审核中素材拖累。

**解决**：
- 按 3.6 清单补多样性与相关性。
- 清理 LOW / 审核失败素材，替换新角度。

---

### 4.10 Q：Performance Planner 预测的 ROAS 和我实际跑出来差很多，正常吗？

**现象**：Planer 的模拟结果与实际偏差 20-40%。

**原因**：Planner 基于历史外推，未充分建模大促/季节性/竞争突变。

**排查**：
1. 看预测是否是在大促/剧烈市场变化前做的。
2. 对比"Planner 假设"与"实际转化行为"（转化时间窗、新客比例）。

**解决**：
- 把 Planner 当"方向参考"而非"精确承诺"。
- 对季节性业务，叠加季节性系数做折扣。
- 落地后用增量观测（Geo/CAA）校验，再校准参数。

---

### 4.11 Q：我把转化目标从"购买"改成"加购"，ROAS 崩了，为什么？

**现象**：改了转化目标后 ROAS 大跌。

**原因**：转化目标改变 = 算法优化的"北极星"变了，加购价值远低于购买，
且触发学习期。

**排查**：确认目标价值设定是否合理（加购价值要给对）。

**解决**：
- 若目标是"最终购买"，建议以"购买"或"购买的底层事件"为转化目标，
  不要用低价值的加购做 tROAS 主目标。
- 若非改不可，给足学习期并重新校准 tROAS。

---

### 4.12 Q：跨渠道归因下，PMax 的 ROAS 数字到底可信吗？

**现象**：PMax 报表 ROAS 与 GA4 / 内部财报 ROAS 对不上。

**原因**：口径不同——Google 用其 DDA + 转化时间窗；内部可能用 last-click
或自建归因；且存在跨设备/隐私沙盒误差。

**排查**：
1. 确认两侧"转化定义 + 时间窗 + 去重 + 跨设备"是否一致。
2. 用增量测量（Geo test）而非报表绝对值做决策依据。

**解决**：
- 以"增量"为决策核心，不以任何一方的报表 ROAS 绝对值为准。
- 统一口径后再对比，避免拿苹果比橘子。

---



## 五、自测题

### Q1：PMax 中的受众信号到底是"硬限制"还是"提示"？它如何在算法层生效？

<details><summary>答案</summary>

受众信号是**提示（先验）而非硬限制**。

在算法层，信号被建模为一个"先验分布"：
P(高转化价值 | 该用户) ∝ P(该用户|信号先验) · P(高转化价值|用户实时特征)。
信号决定"从哪开始找"，而系统在竞价中用实时特征重新打分，往往会跳出信号
范围去扩展。这与贝叶斯更新的"先验+似然"思想一致。

正确实践：
1. 提供 3-5 组贴近核心客户的信号（Custom Segment 关键词/URL、再营销、相似）。
2. 把信号当"学习种子"，不要当"白名单"。
3. 若想更守信号，用更贴近客户的信号 + 更聚焦的素材主题。
4. 若做新客扩展，反而要留足自由度。

过度收窄信号会抑制系统扩展能力，导致新客获取下降。
</details>

---

### Q2：为什么 PMax 看不到词级/精确渠道花费？"暗箱"的动机是什么？运营上如何应对？

<details><summary>答案</summary>

PMax 刻意隐藏四类信息，动机各异：
1. 词级查询：避免泄露竞价匹配机密。
2. 精确渠道花费：把跨渠道预算分配作为核心优化权保护，防止广告主手动
   调配破坏全局最优。
3. 受众最终边界：保留新客探测空间。
4. 单次实时出价：智能化竞价机密。

运营应对（"接受不可控，专注可控"）：
- 用优化分数(optimization_score)当健康仪表盘。
- 用素材强度检查素材组合充分度。
- 用搜索词洞见看聚合主题，间接观察查询。
- 用 Performance Planner 做预算模拟，替代"猜渠道"。
- 用增量测量(Geo/CAA)验证真实效果，而非迷信报表 ROAS。
</details>

---

### Q3：请用数学写出数据驱动归因(DDA)的 Shapley 值公式，并解释三渠道例子中 B 渠道的功劳怎么算？

<details><summary>答案</summary>

Shapley 值公式（渠道 i 在渠道集合 S 中的功劳）：

```
φ_i = Σ_{T ⊆ S\{i}} [ |T|!·(|S|-|T|-1)! / |S|! ] · ( v(T∪{i}) - v(T) )

v(T) = 仅由子集 T 中渠道组成的用户的实际转化率
v(T∪{i}) - v(T) = 渠道i加入组合T的边际贡献
权重 = |T|!·(|S|-|T|-1)! / |S|!   (对所有排列取平均)
```

三渠道例子（S={A,B,C}，总转化率假设归一化到 1）：
- v({B})=0.5, v({A,B})=0.7, v({B,C})=0.8, v({A,B,C})=1.0
- 子集T=∅:   增量 0.5, 权 1/3 → 0.1667
- 子集T={A}: 增量 0.4, 权 1/6 → 0.0667
- 子集T={C}: 增量 0.6, 权 1/6 → 0.1
- 子集T={A,C}:增量 0.6, 权 1/3 → 0.2
- φ_B ≈ 0.533

B 贡献最大，因为它叠加任一渠道组合后转化率提升都稳定最大。
工程上 Google 从真实转化数据估计各子集 v(T)，再用 Shapley 平均，
把功劳同时分给路径上多个渠道，这就是 DDA。
</details>

---

### Q4：在带 GMX 的购物场景，为什么我 SKU 没曝光？请给排查顺序。

<details><summary>答案</summary>

排查顺序（按最可能到最少）：
1. Merchant Center 诊断：商品是否拒审/缺字段/重复/错误价格或库存。
2. ShoppingProduct 报表：该 SKU 是否有数据，判断是否被系统"选中"。
3. 商品分组与出价：该 SKU 所在分组出价是否过低，或分组素材冲突。
4. feed 同步：价格/库存是否频繁不同步，availability 是否正确。

修复：
- 按 feed 质量清单（id/title/image/google_product_category/price/
  availability/item_group_id）修复字段。
- 给重点 SKU 独立资产组/分组并保证出价与预算。
- 大促/新品给学习期保护，别马上判定"没量"就砍。
</details>

---

### Q5：为什么我同时加预算"翻倍"后 ROAS 暴跌？正确的上量方式是什么？

<details><summary>答案</summary>

一次性翻倍预算的问题：
1. 触发学习期重置或长时间重新收敛，期间 ROAS 波动大。
2. 系统把新增预算投到"边际 ROAS 很低"的新机会，稀释整体 ROAS。
3. 触达更大范围后混合了低质流量，优化分数可能暂时下降。

正确上量方式（阶梯式）：
1. 用 Performance Planner 找"关键点（kink）"：哪一档预算后 ROAS 开始
   显著塌陷，就停在那之前。
2. 每档预算 +20%-30%。
3. 每档观察 5-7 天，用 7 天滚动 ROAS 判断是否继续。
4. 若 ROAS 跌破护栏（如目标×0.85）则回退上一档或优化素材。
</details>

---

## 六、综合大表与速查

这一章把全文的核心结论压缩成几张速查表，方便投放经理和工程师日常查用。

### 6.1 PMax 配置速查

| 配置项 | 推荐值 | 说明 |
|--------|--------|------|
| 出价目标 | MaxConvValue + tROAS | 效果优先 |
| tROAS 起步 | 历史 ROAS × 0.8-1.0 | 留学习空间 |
| 预算增幅 | 每次 +20-30% | 防学习期重建 |
| 资产组数 | 2-6/系列 | 主题聚焦 |
| 图片数/AG | 10-15 | 多样化 |
| 视频数/AG | 1-2 | 15s+30s |
| 信号组数/AG | 3-5 | 核心先验 |
| 评估口径 | 7-30 天滚动 | 勿看单日 |

### 6.2 常见指标解读

| 指标 | 含义 | 健康参考 |
|------|------|----------|
| optimization_score | 账户健康分 | ≥60 良好 |
| 素材强度 | 素材组合充分度 | 良好/优秀 |
| 7天滚动ROAS | 中期趋势 | 与目标比 |
| 预算受限 | 吃满预算 | 看边际ROAS |
| 学习期 | 收敛阶段 | <14天 |
| 转化时间窗 | 归因窗口 | 按品类 |

---

## 七、总结

| 主题 | 关键要点 |
|------|----------|
| PMax 本质 | 目标驱动跨渠道智能投放，决策权移交换取自动化 |
| 暗箱 | 词级/精确渠道花费/受众边界/实时出价不可见 |
| 资产组 | 核心执行单元，素材+信号+URL，2-6 个/系列 |
| 信号 | 先验提示非硬限制，3-5 组核心先验 |
| GMX | 电商深化，SKU 级分组/出价/报告 |
| Planner | 预算-ROAS 模拟，找关键点，阶梯上量 |
| DDA | Shapley 值分配功劳，多渠道分摊 |
| 时间窗 | 按品类选 7/30 天，影响表面 ROAS |
| 隐私 | Signals/沙盒，靠第一方数据+增量测量对冲 |
| 诊断 | 优化分数+素材强度+搜索词洞见 |

---

*本文档为 Google Ads Performance Max 暗箱深度解析，结合 PMax 资产组、
受众信号、GMX、Performance Planner 与跨渠道归因，构建可落地的实战体系。
建议结合实际账户数据、GAQL 查询与增量测量不断验证与校准。*

---

## 附录：GAQL 常用查询速查与指标口径

这一附录把全文用到的 GAQL 查询、脚本方法与指标口径汇总成速查表，
方便投放经理与工程师复制到生产环境。

### A.1 脚本方法 → 端点速查

| 脚本方法 | REST 端点 | 用途 |
|----------|-----------|------|
| `search(customer_id, query)` | POST customers/{id}:search | 执行 GAQL 查询 |
| `list_campaigns` | search + campaign 查询 | 列出广告系列 |
| `create_campaign` | POST customers/{id}/campaigns | 创建 PMax 系列 |
| `update_campaign` | PATCH campaigns/{id} | 更新预算/出价/状态 |
| `pause_campaign / resume_campaign` | PATCH | 暂停/恢复系列 |
| `list_ad_groups` | search + ad_group 查询 | 列出资产组 |
| `create_ad_group` | POST adGroups | 创建资产组(PMax) |
| `create_keywords` | POST adGroupCriteria:mutate | 负向词/关键词 |
| `list_conversion_actions` | search | 转化行为清单 |
| `get_bid_suggestion` | search keyword_view | 出价建议 |
| `generate_report(customer_id, date_range)` | search campaign | 基础报表 |
| `get_asset_type_options` | 本地映射 | 素材类型选项 |

### A.2 PMax 核心 GAQL 查询速查

```sql
-- 1) 列出所有 PMax 系列 + 优化分数
SELECT campaign.id, campaign.name, campaign.status,
       campaign.optimization_score,
       campaign.advertising_channel_sub_type
FROM campaign
WHERE campaign.advertising_channel_type = 'PERFORMANCE_MAX'

-- 2) 资产组级表现(近14天)
SELECT campaign.name, asset_group.name, asset_group.status,
       metrics.impressions, metrics.clicks, metrics.cost_micros,
       metrics.conversions, metrics.conversions_value, metrics.ctr
FROM asset_group
WHERE segments.date DURING LAST_14_DAYS
  AND campaign.advertising_channel_type = 'PERFORMANCE_MAX'

-- 3) 素材强度与素材绑定
SELECT asset_group.name, asset_group_asset.field_type,
       asset_group_asset.performance_label,
       asset_group_asset.policy_summary_info.review_status
FROM asset_group_asset
WHERE segments.date DURING LAST_14_DAYS

-- 4) 受众信号清单
SELECT asset_group.name, asset_group_signal.audience.id,
       asset_group_signal.audience.name
FROM asset_group_signal
WHERE asset_group.status = 'ENABLED'

-- 5) 跨渠道(聚合可见性)
SELECT campaign.name, segments.ad_network_type,
       metrics.impressions, metrics.cost_micros,
       metrics.conversions_value
FROM campaign
WHERE segments.date DURING LAST_14_DAYS
  AND campaign.advertising_channel_type = 'PERFORMANCE_MAX'

-- 6) 转化行为清单
SELECT conversion_action.id, conversion_action.name,
       conversion_action.type, conversion_action.status
FROM conversion_action

-- 7) 负向关键词(账户/系列级)
SELECT campaign.name, campaign_negative_keyword.keyword.text,
       campaign_negative_keyword.match_type
FROM campaign_negative_keyword
WHERE campaign.id = 9876543210

-- 8) 预算与预算受限
SELECT campaign.name, campaign_budget.amount_micros,
       campaign_budget.explicitly_shared,
       campaign_budget.status
FROM campaign
WHERE campaign.id = 9876543210
```

### A.3 指标口径速查（跨系统对比）

| 指标 | Google Ads/PMax 口径 | GA4 口径 | 差异来源 |
|------|----------------------|----------|----------|
| 转化(Conversion) | 按转化行为+时间窗 | 会话级/事件级 | 定义不同 |
| 转化价值(Value) | 目标价值配置 | 事件参数值 | 赋值规则 |
| ROAS | 价值/花费(DDA归因) | 自行计算 | 归因模型不同 |
| 点击 | 广告点击 | 会话跳转 | 去重/渠道 |
| 展示 | 广告曝光 | 广告曝光(部分) | 计数口径 |
| CTR | 点击/展示 | 同 | 基本一致 |
| CPC | 花费/点击 | - | 仅广告口径 |
| 跨设备 | Signals 增强 | Signals 增强 | 抽样范围 |

> 黄金法则：跨系统对账时，先对齐"转化定义 + 时间窗 + 去重 + 跨设备";
> 若仍对不上，用增量测量(Geo test / CAA)做最终裁决，
> 不迷信任何单一报表的 ROAS 绝对值。

### A.4 提交前的文档一致性自检

```
PMax 文档自检清单
────────────────────────────────────────────────────────────
  ☐ 五大章节齐全: 一 核心概念 / 二 原理 / 三 实战 / 四 Q&A / 五 自测题
  ☐ 一含 ASCII 架构图
  ☐ 二含 Python + Go 真实代码(方法名 = 脚本 google_ads_api.py)
  ☐ 三含 4+ 真实业务场景 + 量化指标(ROAS/CPA/CTR/CVR)
  ☐ 四含 ≥10 个具体 Q&A
  ☐ 五含 3-5 自测题, 答案在 <details><summary>答案</summary>
  ☐ 归因纳入"二、深度原理解析"(2.10-2.15), 含 DDA/Shapley 推导
  ☐ 综合大表与速查置于五之后作为附录级速查
```

---

*附录结束。本文件是 PMax 暗箱从架构到归因、从代码到业务的完整指南。*
