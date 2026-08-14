# Google 搜索合作伙伴网络(Search Partners Network)深度指南：扩展流量、质量控制、排除策略

> **领域**: 广告投放 / GOOGLE_ADS
> **深度**: ⭐⭐⭐⭐⭐ 实战级指南
> **标签**: GOOGLE_ADS, 广告投放
> **更新时间**: 2026-08-14
> **类型**: 深度知识文档

---

## 一、核心概念与架构

### 1.1 什么是 Google 搜索合作伙伴网络

Google 搜索合作伙伴网络（Google Search Partners Network，简称 GSPN 或 SPN）
是 Google Ads 提供的一项流量扩展能力。

它允许广告主的搜索广告，在 Google 自有搜索渠道之外，
投放到一大批经过 Google 审核与筛选的第三方合作站点上。

这些合作站点本质上都是"搜索行为驱动"的页面，
而不是像展示网络那样纯粹靠内容匹配。

所以从流量属性上看，SPN 介于"纯 Google 搜索"与"展示广告"之间。
它保留了一部分搜索意图的纯度，同时又引入了大量非 Google 站点的长尾流量。

理解这一点的关键，是区分两个容易混淆的维度：

1. **Google.com（自有搜索）**：Google 搜索引擎主站与其他自有搜索属性。
2. **Search Partners（搜索合作伙伴）**：非 Google 自有的一大批第三方站点。

这两者在报告里可以分离开来看，
但默认情况下它们会被合并到同一个"搜索"频道里。

### 1.2 一个被长期低估的流量池

很多投放团队把 SPN 当成一个默认开关，从不单独分析。
这是很大的误区。

实际上 SPN 能为很多账户贡献 10% 到 30% 的搜索点击量，
个别垂直领域甚至超过 40%。

对于教育、留学、本地服务、工具类 APP 这类产品，
SPN 往往承载了大量被 Google.com 竞价挤掉的尾量。

但它也是一把双刃剑：

- 好处：点击量、曝光量、转化量的天然增量。
- 坏处：点击质量参差不齐，无效流量比例更高，
  第三方归因差异大，跨渠道数据对不齐。

所以专业投放者的目标不是"开"或"关"，
而是"知道它贡献了多少、质量如何、如何精确控制"。

### 1.3 架构总览

下面这张 ASCII 架构图，把整个搜索生态的流量流向画清楚了。
请重点关注 SEARCH 与 SEARCH_PARTNERS 两条路径如何分叉与合并。

```
                    ┌─────────────────────────────────────────────┐
                    │             Google Ads 账户 (Customer)       │
                    │                                             │
                    │   ┌─────────────────────────────────────┐   │
                    │   │   Campaign (广告系列)               │   │
                    │   │   「搜索」广告系列 = 搜索 + SPN 流量 │   │
                    │   │   - 广告系列层级开启/排除 SPN       │   │
                    │   └─────────────────────────────────────┘   │
                    │                     │                        │
                    │    ┌────────────────┴──────────────────┐     │
                    │    ▼                                   ▼     │
                    │ ① Google 自有搜索               ② Search Partners │
                    │   Google.com / 本地化搜索        第三方合作站点   │
                    │   (SEARCH 频道)                (SEARCH_PARTNERS) │
                    │    - Google 主站                     │         │
                    │    - Google 新闻                     ├─ 新闻/门户 │
                    │    - 其他 Google 搜索属性           ├─ 比价/导购 │
                    │                                     ├─ 垂直社区 │
                    │                                     ├─ 工具站   │
                    │                                     └─ 其他审核站│
                    └──────────────────┬──────────────────────────────┘
                                       ▼
                    ┌──────────────────────────────────────────────┐
                    │      服务端数据 (Google 服务器选择广告)      │
                    │  quality score / 出价 / 广告相关性共同决定    │
                    └──────────────────────────────────────────────┘
                                       ▼
                    ┌──────────────────────────────────────────────┐
                    │   报告维度 segments.channel = SEARCH          │
                    │   或 SEARCH_PARTNERS (可通过 GAQL 分离)      │
                    └──────────────────────────────────────────────┘
```

关键洞察是：
**同一条广告、同一个关键词池、同一套出价逻辑，
会同时流向两条不同的物理路径。**

报告层虽然能通过 `segments.channel` 把它们分开，
但默认的"搜索"维度是合并展示的。

这就是为什么无数投放者被"看似漂亮的搜索 ROI"误导——
因为里面混着质量参差的 SPN 流量。

### 1.4 架构中的三层分离模型

#### 第一层：流量物理来源分离

物理来源天然分两类：

1. Google.com（含本地化域名如 google.co.jp）。
2. 第三方合作站点（如某个垂直比价网站）。

这一层是客观事实，Google 服务器知道流量从哪来，
只是默认不给你在界面上分开展示。

#### 第二层：报告维度分离

Google Ads API 提供 `segments.channel` 枚举字段。
它取值 `SEARCH` 或 `SEARCH_PARTNERS`，
可以把统计口径拆开。

这是专业投放者做 SPN 分析的核心抓手。
绝大多数 SPN 精细化运营，都建立在这个字段之上。

#### 第三层：投放策略分离

有了数据分离能力之后，策略上就能做"物理隔离"：
把 SPN 流量从主广告系列里拆出来，
放进专门的、可控的、低出价的广告系列里单独运营。

这叫做 **SPN 分割（SPN split campaign）**。
是本文后面会反复强调的最佳实践之一。

### 1.5 GSPN 与展示网络的本质区别

很多人问：SPN 和 GDN（Google Display Network）有什么区别？

核心区别在于触发逻辑：

| 维度 | Search Partners (SPN) | Display Network (GDN) |
|------|-----------------------|----------------------|
| 触发逻辑 | 用户的搜索词/关键词意图 | 内容主题/兴趣/再营销 |
| 流量属性 | 搜索行为驱动 (search-like) | 内容浏览驱动 (content-based) |
| 广告形式 | 主要是文字广告 | 文字/图片/视频/富媒体 |
| 出价方式 | 搜索出价逻辑 (CPC) | 展示出价逻辑 (CPM/eCPM) |
| 点击意图 | 较高，用户在找东西 | 较低，用户在浏览 |
| 质量控制 | 事件触发，接近搜索 | 主题触发，差异大 |
| 报告频道 | SEARCH_PARTNERS | DISPLAY |

结论：SPN 是"借别人的壳，装搜索的芯"。
所以它的转化率通常远高于 GDN，
但 QC（点击质量）又明显低于 Google.com。

### 1.6 为什么默认是开启的

新创建的搜索广告系列，默认会勾选"包含搜索合作伙伴"选项。

这意味着绝大多数普通投放者，
从一开始就在为 SPN 流量买单，
却不知道自己为"非 Google 站点"的点击付了费。

默认开启的底层逻辑是：
Google 希望给广告主更多增量流量、更快花完预算，
从而获得更多信号来优化出价。

但对转化目标族（TARGET_CPA / MAXIMIZE_CONVERSIONS）来说，
SPN 的低质点击会拉高整体 CPC、稀释 CVR，
从而让智能出价模型产生"被污染"的训练信号。

### 1.7 本节小结

- GSPN 是搜索广告向第三方合作站点扩展的流量池。
- 它介于纯搜索与展示之间，意图纯度高于 GDN，低于 Google.com。
- 报告维度 `segments.channel` 支持把 SEARCH 与 SEARCH_PARTNERS 分开。
- 默认开启，专业账户必须显式管理而不是放任不管。
- 三层分离模型（物理来源/报告维度/投放策略）是运营 GSPN 的地基。

---

## 二、深度原理解析

### 2.1 服务器选择机制：广告如何在 SPN 站点被选中

Google 在一套统一的竞价机制里，同时处理 Google.com 与 SPN 的请求。

当一个用户到达一个合作站点并执行搜索,
站点会把这次搜索请求转发给 Google 的广告服务器。

Google 服务器会根据以下因素，决定展示哪些广告：

1. 用户的搜索词（query）。
2. 广告主的关键词匹配（broad / phrase / exact）。
3. 广告质量得分（Quality Score）。
4. 广告主对该关键词的出价。
5. 预算与广告系列的可用性。

值得强调的是：
**SPN 站点上的广告选择，并不完全等同于 Google.com 上的逻辑。**

Google 对 SPN 使用的相关性判断往往是"更宽松"的扩展匹配。
同一关键词，在 Google.com 上可能是精确匹配，
在某个合作伙伴站点上可能被扩展到近义词、错拼、语义衍生。

这就是为什么 SPN 的关键词点击会呈现更高比例的长尾与噪音词。

### 2.2 匹配类型的"隐形放宽"效应

在 SPN 上,即便你只放了精确匹配关键词，
Google 也倾向于做更宽的语义处理。

实操上的表现是：
一个精确匹配词 "MBA 留学费用",
在 Google.com 上几乎只命中高度相关查询，
但在某个教育比价站上可能命中 "mba program cost"、
"留学 mba 多少钱"、甚至 "mba 学费 知乎" 这类近似词。

这个放宽效应，是 SPN 点击量往往远超 Google.com 的核心原因之一，
也是无效流量（垃圾流量、误点）的主要来源。

专业做法：不能用同一个负向词清单来同时约束 Google.com 和 SPN。
需要针对 SPN 单独维护一套更激进的关键词负向策略。

### 2.3 GAQL 频道维度：把两类流量拆开

Google Ads API 的核心能力，是 `segments.channel` 字段。

它在 GAQL 查询里可以当做分组与过滤维度使用。
取值如下：

- `SEARCH`：来自 Google 自有搜索（Google.com 等）。
- `SEARCH_PARTNERS`：来自搜索合作伙伴站点。
- `DISPLAY`、`YOUTUBE`、`SHOPPING` 等：其他频道。

下面是一段用 `search` 方法跑 GAQL 的真实示例，
把某广告系列的流量按 channel 拆开统计。

```python
# scripts/google_ads_api.py 的 search 方法示例
from scripts.google_ads_api import GoogleAdsApi

api = GoogleAdsApi()

customer_id = "1234567890"
campaign_id = "6543210987"

# GAQL: 按 segments.channel 拆分展示量、点击、花费、转化
query = f"""
SELECT
    campaign.id,
    segments.channel,           -- SEARCH / SEARCH_PARTNERS
    metrics.impressions,
    metrics.clicks,
    metrics.cost_micros,
    metrics.conversions,
    metrics.conversions_value
FROM campaign
WHERE
    campaign.id = {campaign_id}
    AND segments.date DURING LAST_30_DAYS
"""

resp = api.search(customer_id=customer_id, query=query)

for row in resp.rows:
    channel = row["segments.channel"]            # SEARCH or SEARCH_PARTNERS
    cost = row["metrics.cost_micros"] / 1_000_000
    cvr = 0.0
    if row["metrics.clicks"]:
        cvr = row["metrics.conversions"] / row["metrics.clicks"] * 100
    print(
        f"channel={channel} "
        f"impressions={row['metrics.impressions']} "
        f"clicks={row['metrics.clicks']} "
        f"cost=¥{cost:.2f} "
        f"conversions={row['metrics.conversions']} "
        f"CVR={cvr:.2f}%"
    )
```

运行这段代码，你会直接看到
同一个广告系列里 SEARCH 与 SEARCH_PARTNERS 各自的健康度。

这是做 SPN 决策的第一步：
先量化，再判断。

### 2.4 频道级流量占比的量化方法

光看单一广告系列不够，要从账户全貌判断 SPN 的影响。

建议跑一个跨账户、按频道聚类的查询，
计算出 SPN 占整个搜索流量的比例。

```python
# 账户级 SPN 占比分析
from scripts.google_ads_api import GoogleAdsApi

api = GoogleAdsApi()
customer_id = "1234567890"

query = """
SELECT
    segments.channel,
    metrics.impressions,
    metrics.clicks,
    metrics.cost_micros,
    metrics.conversions,
    metrics.conversions_value
FROM campaign
WHERE
    segments.date DURING LAST_28_DAYS
"""

resp = api.search(customer_id=customer_id, query=query)

# 只保留搜索系频道
agg = {"SEARCH": {}, "SEARCH_PARTNERS": {}}
for row in resp.rows:
    ch = row["segments.channel"]
    if ch not in agg:
        continue
    d = agg[ch]
    d["impr"] = d.get("impr", 0) + row["metrics.impressions"]
    d["clicks"] = d.get("clicks", 0) + row["metrics.clicks"]
    d["cost"] = d.get("cost", 0) + row["metrics.cost_micros"]
    d["conv"] = d.get("conv", 0) + row["metrics.conversions"]

total_clicks = agg["SEARCH"]["clicks"] + agg["SEARCH_PARTNERS"]["clicks"]
sp_share = agg["SEARCH_PARTNERS"]["clicks"] / total_clicks * 100 if total_clicks else 0

print(f"Google.com 点击: {agg['SEARCH']['clicks']}")
print(f"SPN 点击:        {agg['SEARCH_PARTNERS']['clicks']}")
print(f"SPN 点击占比:    {sp_share:.2f}%")

# 对比转化成本
for ch in ("SEARCH", "SEARCH_PARTNERS"):
    d = agg[ch]
    if d["clicks"]:
        cpa = d["cost"] / d["conv"] if d["conv"] else float("inf")
        cvr = d["conv"] / d["clicks"] * 100
        print(f"{ch}: CVR={cvr:.2f}%  CPA=¥{cpa:.2f}")
```

如果发现 SPN 的 CVR 明显低于 Google.com、CPA 明显更高,
就需要果断采取排除或降权动作。

### 2.5 get_bid_suggestion 与出价建议参考

Google Ads API 提供了 `get_bid_suggestion` 方法，
可以基于模型给出关键词的建议出价。

在处理 SPN 时，这个建议通常对应的是"合并流量"下的出价水平。
而 SPN 与 Google.com 的质量不同，
理论上需要不同的出价水平。

由于 SPN 与 Google.com 在同一个广告系列时无法分别出价，
唯一的出路就是把它们拆到不同广告系列。

```python
from scripts.google_ads_api import GoogleAdsApi

api = GoogleAdsApi()
customer_id = "1234567890"
campaign_id = "6543210987"

# 获取系统建议出价（仅搜索广告系列可用）
resp = api.get_bid_suggestion(
    customer_id=customer_id,
    campaign_id=campaign_id,
)

print(resp.payload)
```

### 2.6 智能出价在 SPN 上的信号污染问题

智能出价（Smart Bidding）依赖转化信号训练模型。

当 SPN 流量与 Google.com 流量混在一个广告系列时，
模型会把这些信号混在一起做统一优化。

问题在于：
SPN 点击的转化率系统性偏低（低至 Google.com 的 1/3 到 1/2 是常态），
但成本却按同一出价逻辑去竞价。

结果就是：
- 模型为了在 SPN 上抢量，可能被低质信号带偏。
- CPA 目标被稀释，Google.com 优质流量反而被"让利"。
- 预算被 SPN 消耗，优质流量得不到预算。

这就是"物理隔离"（拆广告系列）比"归因调整"更根本的原因。

### 2.7 SPN 拆分为只用 Google.com 的广告系列

拆分的思路很简单：
新建一个广告系列，在创建时把"搜索合作伙伴"项设为排除。
这样该广告系列就只会获得 `SEARCH` 流量。

```python
# 创建仅 Google.com 的搜索广告系列（排除 SPN）
from scripts.google_ads_api import GoogleAdsApi

api = GoogleAdsApi()
customer_id = "1234567890"

campaign = {
    "name": "Core Search - Google Only",
    # 广告系列层级：排除搜索合作伙伴
    "search_network": False,
    # 搜索广告根源（Search 类型，可含搜索伙伴，这里关闭）
    "status": "PAUSED",  # 先暂停，配置好再启用
    "channel": "SEARCH",  # 广告系列类型
    "budget_micros": 500_000_000,  # 示例 ¥500/天
    "bidding": {"strategy": "TARGET_CPA", "target_cpa_micros": 200_000_00},
}

resp = api.create_campaign(customer_id=customer_id, campaign=campaign)
print(resp)
```

实际运行时要按 `google_ads_api.py` 的入参结构来组装
`campaign` 字典（字段名以工具定义的 schema 为准）。

这里强调的是"广告系列层级存在关闭 SPN 的开关"这一事实。

### 2.8 一次限制：为什么不能在关键词层级开关 SPN

很多新手会误以为可以针对单个关键词排除 SPN。
这是做不到的。

SPN 的开关粒度是 **广告系列（campaign）层级**，
不是关键词层级、也不是广告组层级。

也就是说：
- 要么整个广告系列投 Google.com + SPN（合并）。
- 要么整个广告系列只投 Google.com（排除 SPN）。
- 不能在一个广告系列里选几个词只投 Google.com。

这一限制，决定了所有 SPN 精细化控制，
都必须走"拆广告系列"这条路。

### 2.9 广告系列子类型对 SPN 的影响

不同广告系列子类型对 SPN 的支持不同。

- 传统搜索广告系列：支持 SPN，有开关。
- 效果最大化（Performance Max，PMax）：不单独暴露 SPN 开关，
  其流量分配由系统决定，SPN 藏在"搜索 + 探索"里。
- APP 广告系列（App Campaign）：系统自动投放到多个 Google 属性，
  包含搜索伙伴，但不可单独关。
- Shopping 广告系列：默认不投 SPN。

所以在讲到 SPN 精确控制时，主要指传统搜索广告系列。

### 2.10 optimize_score 与 SPN 的关系

`campaign.optimization_score` 是 Google 给出的账户优化健康分。
它只反映"优化建议的采纳程度"，并不代表 SPN 流量的质量。

也就是说，一个 optimization_score 很高的账户，
可能依然被 SPN 低质流量拖累。
两者是正交的维度。

不要把优化分当成 SPN 质量好坏的代理指标。

### 2.11 本节小结

- SPN 的本质是"同一出价机制下的放宽匹配"。
- `segments.channel` 是分离 SEARCH / SEARCH_PARTNERS 的核心维度。
- 智能出价会被 SPN 低质信号污染，物理隔离是根治手段。
- SPN 开关粒度在广告系列层级，不能按关键词控制。
- PMax / App 广告系列不暴露 SPN 开关，需另作评估。
