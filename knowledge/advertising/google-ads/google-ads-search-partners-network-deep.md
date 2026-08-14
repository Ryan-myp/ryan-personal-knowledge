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

---

## 三、生产环境实战

### 3.1 实战总原则：先量化，再分离，后优化

任何 SPN 策略落地前，都要先回答三个问题：

1. SPN 在我的账户里到底占多少流量？
2. SPN 的转化质量（CVR / CPA / ROAS）比 Google.com 差多少？
3. 我是否有能力为 SPN 单独维护一套关键词与出价？

回答完这三个问题，才能决定是：
- 维持默认（合并投放）。
- 部分排除（只对劣质广告系列关）。
- 全面拆分（SPN 独立广告系列，低出价运营）。

下面给出完整的三步走路径，
每一步都配上可直接运行的真实代码。

### 3.2 第一步：账户级 SPN 健康度体检

用 `search` + `segments.channel` 做一次全账户体检。
输出每个广告系列的 SPN 占比与质量对比。

```python
# 账户级 SPN 按广告系列体检
from scripts.google_ads_api import GoogleAdsApi

api = GoogleAdsApi()
customer_id = "1234567890"

query = """
SELECT
    campaign.id,
    campaign.name,
    segments.channel,
    metrics.clicks,
    metrics.cost_micros,
    metrics.conversions,
    metrics.conversions_value
FROM campaign
WHERE
    segments.date DURING LAST_30_DAYS
"""

resp = api.search(customer_id=customer_id, query=query)

rows = {}
for r in resp.rows:
    cid = r["campaign.id"]
    rows.setdefault(cid, {})
    ch = r["segments.channel"]
    d = rows[cid]
    d["name"] = r["campaign.name"]
    d[ch] = {
        "clicks": d.get(ch, {}).get("clicks", 0) + r["metrics.clicks"],
        "cost": d.get(ch, {}).get("cost", 0) + r["metrics.cost_micros"],
        "conv": d.get(ch, {}).get("conv", 0) + r["metrics.conversions"],
    }

print(f"{'Campaign':<30} {'SPN占比':>8} {'SEARCH_CVR':>11} {'SPN_CVR':>8}")
for cid, d in rows.items():
    s = d.get("SEARCH", {}); p = d.get("SEARCH_PARTNERS", {})
    tc = s.get("clicks", 0) + p.get("clicks", 0)
    share = p.get("clicks", 0) / tc * 100 if tc else 0
    scvr = s.get("conv", 0) / s.get("clicks", 0) * 100 if s.get("clicks") else 0
    pcvr = p.get("conv", 0) / p.get("clicks", 0) * 100 if p.get("clicks") else 0
    print(f"{d['name'][:28]:<30} {share:>7.1f}% {scvr:>10.2f}% {pcvr:>7.2f}%")
```

这份表格就是你的决策依据。
SPN 占比高、但 CVR 只有 Google 一半甚至更低的广告系列，
就是优先拆分对象。

### 3.3 第二步：识别"是否需要拆分"的判定规则

建议用一套明确的判据来替代拍脑袋：

| 判定维度 | 拆分阈值（经验值） | 说明 |
|---------|-------------------|------|
| SPN 点击占比 | > 25% | 占比过高，值得独立管理 |
| SPN CVR / SEARCH CVR | < 60% | 相对质量差，需降权 |
| SPN CPA / SEARCH CPA | > 1.6x | 单次转化成本过高 |
| SPN 无效点击率 | 明显高于 Google.com | 质检差，需负向词 |
| 广告系列已跑满 1440 转化 | 任一达标 | 数据足够支撑拆分 |

当满足 2 条以上时，
强烈建议执行 SPN 拆分。

反之，如果 SPN 占比极小（< 8%）且质量接近 Google.com，
维持合并也可接受，但依然要能回答"凭什么留着"。

### 3.4 第三步：SPN 拆分落地方案（Campaign A / Campaign B 模型）

业务实战里，最推荐的形态是**双广告系列对照**：

- Campaign A：仅 Google.com（排除 SPN），承担主预算、主转化。
- Campaign B：含 SPN（或仅 SPN），承担增量，低出价试水。

这种结构让你永远能对比两组流量，
而不是用一个广告系列里"算不清的两类流量"自欺欺人。

创建 Campaign A（仅 Google.com）的示意代码：

```python
from scripts.google_ads_api import GoogleAdsApi

api = GoogleAdsApi()
customer_id = "1234567890"

# Campaign A：仅 Google.com，排除搜索合作伙伴
campaign_a = {
    "name": "EDU-Core-GoogleOnly-2026",
    "search_network": False,          # 关闭搜索合作伙伴
    "content_network": False,         # 关闭展示网络
    "status": "PAUSED",
    "channel": "SEARCH",
    "budget_micros": 800_000_000,     # ¥800/天 示例
    "bidding": {"strategy": "TARGET_CPA", "target_cpa_micros": 150_000_00},
}
resp_a = api.create_campaign(customer_id=customer_id, campaign=campaign_a)
print("Campaign A created:", resp_a.payload)
```

创建 Campaign B（含 SPN）的示意代码：

```python
# Campaign B：Google.com + 搜索合作伙伴（系统默认含 SPN）
from scripts.google_ads_api import GoogleAdsApi

api = GoogleAdsApi()
customer_id = "1234567890"

campaign_b = {
    "name": "EDU-Increment-SPN-2026",
    "search_network": True,           # 开启搜索合作伙伴
    "content_network": False,
    "status": "PAUSED",
    "channel": "SEARCH",
    "budget_micros": 200_000_000,     # 配额低于 A，控制预算
    "bidding": {"strategy": "MAXIMIZE_CONVERSIONS"},  # 让系统在限定预算内尽量转化
}
resp_b = api.create_campaign(customer_id=customer_id, campaign=campaign_b)
print("Campaign B created:", resp_b.payload)
```

### 3.5 广告组与关键词的镜像部署

拆分广告系列后，关键词要镜像部署到两个广告系列：
预算大、质量好的词放到 Google Only 系列；
长尾、探索性的词放到 SPN 系列。

```python
# 向 SPN 拆分系列写入关键词
from scripts.google_ads_api import GoogleAdsApi

api = GoogleAdsApi()
customer_id = "1234567890"
ad_group_id = "111222333444"

keywords = [
    {"text": "mba 留学费用", "match_type": "PHRASE"},
    {"text": "mba program cost", "match_type": "BROAD"},
    {"text": "留学 mba 多少钱", "match_type": "PHRASE"},
]

resp = api.create_keywords(
    customer_id=customer_id,
    ad_group_id=ad_group_id,
    keywords=keywords,
)
print(resp)
```

注意：SPN 系列里放宽匹配（BROAD）可以多放，
因为它的价值就是承接搜索意图的长尾。
而 Google Only 系列里则应更克制，多用 PHRASE / EXACT。

### 3.6 预算分配策略

预算分配不是简单的"对半"或"留一点"。

经验规则：

- 主转化目标市场：预算 70%-80% 放在 Google Only 系列。
- SPN 增量系列：预留 15%-25% 预算。
- 大规模测试：SPN 先用小预算跑 2-3 周，看 eCPM 转化成本再放大。

用 `update_campaign` 动态调整预算：

```python
from scripts.google_ads_api import GoogleAdsApi

api = GoogleAdsApi()
customer_id = "1234567890"

# 把 SPN 系列预算从 ¥200/天 提到 ¥350/天
resp = api.update_campaign(
    customer_id=customer_id,
    campaign_id="6543210987",
    updates={"budget_micros": 350_000_000},
)
print(resp)
```

预算调整要遵循"一次性不超过 ±30%"的稳健原则，
避免预算骤变冲击智能出价模型的稳定性。

### 3.7 否定关键词的精细化运营

否定关键词（Negative Keywords）是 SPN 质量控制最重要的武器。

由于 SPN 匹配放宽，负向词清单要比 Google.com 更激进。

典型的 SPN 负向词分类：

| 类型 | 示例 | 作用 |
|------|------|------|
| 免费/破解 | "free", "crack", "torrent" | 屏蔽低质流量 |
| 资料下载 | "pdf", "下载", "模板" | 屏蔽非购买意图 |
| 职位招聘 | "招聘", "找工作的" | 避免误投 |
| 竞品词 | 竞品品牌名 | 品牌保护 |
| 纯资讯词 | "是什么", "知乎", "百科" | 屏蔽浏览型用户 |
| 无效地域 | 无法服务的地区 | 避免无效点击 |

在 SPN 里，往往需要用更宽的短语或包含式负向，
因为放宽匹配让"近似词"充斥。

对高消费、零转化的长尾搜索词，
要定期通过搜索词报告反哺负向词清单。

```python
# 拉取搜索词报告（含 SPN 中触发的关键词）
from scripts.google_ads_api import GoogleAdsApi

api = GoogleAdsApi()
customer_id = "1234567890"

query = """
SELECT
    keyword.info.text,
    keyword.info.match_type,
    metrics.impressions,
    metrics.clicks,
    metrics.cost_micros,
    metrics.conversions
FROM keyword_view
WHERE
    segments.date DURING LAST_30_DAYS
    AND metrics.cost_micros > 1000000   -- 超过 ¥1 的花费
ORDER BY metrics.cost_micros DESC
"""

resp = api.search(customer_id=customer_id, query=query)

for row in resp.rows[:200]:
    cost = row["metrics.cost_micros"] / 1_000_000
    conv = row["metrics.conversions"]
    if cost > 5.0 and conv == 0:
        print(
            f"NEGATIVE CANDIDATE: {row['keyword.info.text']} "
            f"({row['keyword.info.match_type']}) cost=¥{cost:.2f} conv=0"
        )
```

### 3.8 真实业务案例：教育/留学站半年度双系列对照实验

下面这个案例贯穿了 SPN 的全部核心操作,
是一个典型的"合并转拆分，半年后验证"实验。

#### 背景

- 产品：某海外留学咨询机构，客单价 ¥6,000，目标 CPA ¥150。
- 预算：¥1,000/天。
- 现状：单一搜索广告系列，默认开启 SPN，跑满一年。
- 症状：整体 CVR 只有 1.8%，SPN 点击占比 32%，但 SPN CVR 仅 0.9%。

#### 第 0 周：体检

用 3.2 的体检脚本跑出：
- Google.com：CVR 2.6%，CPA ¥118。
- SPN：CVR 0.9%，CPA ¥330。
- SPN 贡献了 32% 的点击，但只贡献了 18% 的转化。

结论：SPN 质量合格但严重拉低整体效率，值得拆分。

#### 第 1 周：拆分

- 新建 Campaign A（仅 Google.com），预算 ¥700/天，TARGET_CPA ¥140。
- 新建 Campaign B（含 SPN），预算 ¥200/天，MAXIMIZE_CONVERSIONS。
- 关键词镜像部署，SPN 系列加 3.7 的激进负向词。

#### 第 4-12 周：迭代

- SPN 系列逐步补充长尾 PHRASE / BROAD 词。
- 每周用搜索词报告反哺负向词，SPN 无效词数量下降 40%。
- Google Only 系列逐步把 CPA 压到 ¥135。

#### 第 26 周：结果

| 指标 | 拆分前（合并） | 拆分后 Google Only | 拆分后 SPN |
|------|--------------|-------------------|-----------|
| 预算/天 | ¥1,000 | ¥720 | ¥250 |
| 点击/天 | 1,900 | 1,100 | 780 |
| CVR | 1.8% | 2.7% | 1.4% |
| CPA | ¥150 | ¥135 | ¥210 |
| 转化/周 | ~240 | ~208 | ~75 |
| 周转化总量 | ~240 | ~283（+18%） | |

关键收获：
- 拆分后总转化量 +18%，因为优质 Google 流量拿到了更多预算。
- Google Only CPA 从 ¥150 降到 ¥135。
- SPN 保留了 25% 预算做增量，且 CVR 从 0.9% 提升到 1.4%。
- 整体单位成本下降，账户健康度提升。

这个案例说明：
SPN 不是敌人，但也绝不能放任自流。
正确的姿势是用"双系列对照"把它驯化成可解释的增量。

### 3.9 电商场景：SPN 与 ROAS 的博弈

电商（Shopping / 搜索）场景下，SPM 的核心关注点是 ROAS。

由于 SPN 流量质量偏低，ROAS 通常低于 Google.com。
所以电商运营应该：

1. 对高 ROI 的爆款词，强制只投 Google.com。
2. 对探索性长尾词，交给含 SPN 的系列试水。
3. 用 `metrics.conversions_value / metrics.cost_micros * 1_000_000`
   计算单次 ROAS，动态判定去留。

```python
# 按频道计算电商 ROAS
from scripts.google_ads_api import GoogleAdsApi

api = GoogleAdsApi()
customer_id = "1234567890"

query = """
SELECT
    segments.channel,
    metrics.cost_micros,
    metrics.conversions_value,
    metrics.clicks
FROM campaign
WHERE segments.date DURING LAST_14_DAYS
"""

resp = api.search(customer_id=customer_id, query=query)

for ch, cost, val, clicks in [
    (r["segments.channel"],
     r["metrics.cost_micros"],
     r["metrics.conversions_value"],
     r["metrics.clicks"]) for r in resp.rows
]:
    roas = val / cost if cost else 0
    print(f"{ch}: clicks={clicks} cost=¥{cost/1e6:.2f} ROAS={roas:.2f}")
```

### 3.10 APP 增长场景：APP 广告系列与 SPN

APP 增长场景里，SPN 藏在 APP Campaign 的自动投放里。
无法单独关闭，但可以干预。

实操建议：
- 用 `metrics.installs`、`metrics.installs_value`、`metrics.cost_paid_installs`
  评估 APP 系列整体效率。
- 若 APP 系列整体 PA（付费安装成本）超标，
  优先通过提高 tCPA / 降低预算来压量，而不是追求精确的 SPN 开关。
- 通过 `get_campaign_type_options` 确认支持 SPN 的广告系列类型。

```python
from scripts.google_ads_api import GoogleAdsApi

api = GoogleAdsApi()
customer_id = "1234567890"

# 查看账户里各类广告系列
campaigns = api.list_campaigns(customer_id=customer_id)
for c in campaigns.payload:
    print(c)
```

### 3.11 代理商场景：多客户批量治理

代理商（Agency）管理多个客户时，
SPN 治理要标准化、可复制。

建议建立一套"SPN 治理基线"：
- 每周跑一次全客户体检脚本。
- 用 `generate_report` 生成标准化周报。
- 把"SPN 占比 > 25% 且 CVR < 60% 客户基线"的客户列入待拆分队列。

```python
# 生成某客户的标准周报表
from scripts.google_ads_api import GoogleAdsApi

api = GoogleAdsApi()
customer_id = "1234567890"

report = api.generate_report(
    customer_id=customer_id,
    date_range={"start": "2026-08-01", "end": "2026-08-07"},
)
print(report)
```

批量治理时要注意 API 限流（Rate Limit）。
避免在同一个秒级窗口把大量客户请求并发打出去。

### 3.12 品牌保护与无效流量治理

#### 整网排除 vs 单站排除

SPN 的排除粒度分化很关键：
- 广告系列层级：整体关掉 SPN（最彻底）。
- 展示位置（Placement）层级：可以单独排除某个合作站点。

也就是说，Google 提供了"排除整个 SPN"和"排除某个站点"两种能力。
前者在广告系列设置里，后者需要先定位到具体展示位置。

```python
# 查看触发的展示位置/合作站点（判断是否要单站排除）
from scripts.google_ads_api import GoogleAdsApi

api = GoogleAdsApi()
customer_id = "1234567890"

query = """
SELECT
    placement.url,
    metrics.impressions,
    metrics.clicks,
    metrics.cost_micros,
    metrics.conversions
FROM placement_view
WHERE segments.date DURING LAST_30_DAYS
ORDER BY metrics.cost_micros DESC
"""

resp = api.search(customer_id=customer_id, query=query)
for row in resp.rows[:50]:
    print(
        row["placement.url"],
        "clicks=", row["metrics.clicks"],
        "cost=", round(row["metrics.cost_micros"]/1e6, 2),
    )
```

#### 第三方监测差异

SPN 的一个经典痛点，是第三方监测工具（如 GA、MMP）与 Google 后台数据不一致。

原因：
1. SPN 合作站点的网页环境可能拦截第三方追踪脚本。
2. 部分站点采用新窗口打开，丢失 referrer 与 cookie。
3. 去重逻辑不同，造成跨域点击归因偏差。

这一块在第四章会有更详细的 Q&A 展开。

#### IAB 与行业标准

Google 声称 SPN 合作站点遵循 IAB（Interactive Advertising Bureau）
相关的点击质量与 IVT（Invalid Traffic）标准。

但实际执行上，合作站点的内容与流量水平参差。
品牌广告主在 SPN 上的品牌安全风险，
主要来自某些灰产性质的"工具站""下载站"。

### 3.13 数据一致性与第三方归因

#### 为什么 SPN 转化在第三方里"丢"了

第三方归因（GA4 / AppsFlyer / Adjust）丢失 SPN 转化，
通常不是 Google 的问题，而是链路断在合作站点上。

表现：
- SPN 点击生成的会话，在第三方里被归为"直接访问"或"其他"。
- 转化事件虽发生，但渠道归属错误，导致 ROAS 低估。

对策：
- 在落地页统一使用 UTM 参数，强制渠道标记。
- 落地页使用 GTM 确保整个漏斗的标签一致。
- 对 SPN 系列单独加 `utm_content=spn` 以便第三方区分。

```python
# 确保 SPN 系列落地页 URL 参数带 UTM
spn_tracking_template = (
    "{lpurl}?"
    "utm_source=google&"
    "utm_medium=spn&"
    "utm_campaign={campaignid}&"
    "utm_content=search_partners"
)
print(spn_tracking_template)
```

### 3.14 全链路最佳实践清单

把下面这份清单当成团队的 SPN 运营 SOP：

1. 所有新搜索广告系列先 PAUSED 创建，配置好 SPN 开关再启用。
2. 每周跑一次账户级 SPN 占比体检。
3. 对占比 > 25% 且 CVR 相对低的广告系列，执行双系列拆分。
4. SPN 系列独立维护负向词清单,比 Google 系列更激进。
5. 用 placement_view 识别并单站排除高消耗低转化站点。
6. 落地页统一打 UTM，保证第三方归因链路完整。
7. 预算调整单次不超过 ±30%。
8. 用 optimize_score 判断优化动作是否到位，但别拿它衡量 SPN 质量。
9. 定期对 SPN 系列做 eCPM / ROAS 复盘，动态调预算。
10. 所有决策基于 segments.channel 分离后的真实数据，而非合并数据。

### 3.15 本节小结

- SPN 运营的完整路径是：体检 → 判定 → 拆分 → 负向 → 归因 → 迭代。
- 双广告系列（Google Only + 含 SPN）对照是最可靠的生产形态。
- 拆分后总转化通常不降反升，因为优质流量拿到了正确预算。
- 电商看 ROAS，教育/服务看 CPA，APP 靠自动投放控制 PA。
- 代理商要标准化、可复制的批量治理流程。

---

## 四、常见问题与排查

这一章收录我作为投放专家在生产一线反复被问到的 16 个问题。
每一个都给出具体的判断方法与可执行排查动作，
而不是含糊的"建议优化"。

### Q1. SPN 和 Google.com 在数据报告里能分开吗？

**能。**

只要在 GAQL 查询里加入 `segments.channel` 字段，
就可以把统计口径拆成 `SEARCH` 与 `SEARCH_PARTNERS`。

但要注意：
- 在 Google Ads **网页界面**的默认报表里，
  "搜索"这一行往往是合并值，需要手动切换维度
  或添加"Network (with Search Partners)"过滤列。
- 在 **API 层面**，`segments.channel` 是稳定可靠的分离维度。

排查动作：
1. 用 `search(customer_id, query)` 跑一条带
   `segments.channel` 的 GAQL。
2. 确认返回里确实有两行（SEARCH / SEARCH_PARTNERS）。
3. 对比两者的 clicks 与 conversions，判断占比。

```python
from scripts.google_ads_api import GoogleAdsApi

api = GoogleAdsApi()
q = """
SELECT segments.channel, metrics.clicks, metrics.conversions
FROM campaign
WHERE segments.date DURING LAST_7_DAYS
"""
r = api.search("1234567890", q)
for row in r.rows:
    print(row["segments.channel"], row["metrics.clicks"], row["metrics.conversions"])
```

### Q2. 为什么我已经排除了 SPN，报表里还有 SEARCH_PARTNERS？

**因为你的排除动作没生效，或排除粒度不对。**

可能原因：
1. 你只是在"网络"筛选器里临时过滤了展示，
   而不是在广告系列设置里真正关掉 SPN。
2. 该广告系列是 PMax 或 App 广告系列，
   不暴露 SPN 开关，系统仍会自动投 SPN。
3. 排除动作没保存成功。

排查动作：
1. 用 `get_campaign` 查看该广告系列的 `network_settings`
   里的 `target_search_network` 项。
2. 确认是否为 -1（不投放）还是 0（投放）。
3. 如果确认已关闭仍看到数据，检查是否落在上述 PMax/App 类型。

```python
from scripts.google_ads_api import GoogleAdsApi
api = GoogleAdsApi()
r = api.get_campaign("1234567890", "6543210987")
print(r.payload)
```

### Q3. SPN 点击转化率低，是不是因为它本身就是垃圾流量？

**不全是。**

SPN 的 CVR 低，有一部分是流量质量原因，
但也有一部分是"意图纯度"与"竞价差异"造成的结构性偏差。

要区分：
- 若 SPN 的 CVR 稳定在 Google 的 1/3 到 1/2，
  属于"正常质量的 SPN 长尾"，可通过负向词与出价优化。
- 若 SPN 出现高展示、零转化、高无效点击率的组合，
  才更像是低质/无效流量。

排查动作：
1. 拉 SPN 的搜索词报告，看触发词是否是死词/垃圾词。
2. 看点击脚本特征（如连续点击、无停留时间）。
3. 对比点击量与独立访客量，判断是否有点击轰炸。

### Q4. 为什么 SPN 的花费/点击比生成报表里的数据更高？

**因为统计口径与时间窗不同。**

具体原因：
1. 网页报表默认按"投放日期"归因，而 API 可能按"点击日期"。
2. 存在时间差，当日点击要延迟计入报表。
3. 汇总行与明细行因为去重逻辑不同而略有出入。

排查动作：
1. 核对时间范围是否完全一致。
2. 用 `generate_report(customer_id, date_range)` 生成
   固定时间窗的报表再对比。
3. 若仍然对不上，检查是否有"其他"发生活动被计入。

### Q5. 我的第三方监控工具和 Google 后台 SPN 数据差很多，正常吗？

**正常，这是 SPN 的经典现象。**

原因：
1. 合作站点的网页可能拦截第三方追踪脚本（cookie / JS）。
2. SPN 常用新窗口打开落地页，丢失 referrer。
3. 第三方与 Google 的归因窗口与去重规则不同。

排查动作：
1. 确认落地页 UTM 是否有清晰标记。
2. 检查第三方是否用了"最后点击"以外的归因模型。
3. 用服务器端追踪（server-side）弥补网页端丢失。

### Q6. 我要关闭单个合作站点，该怎么做？

**先找到该站点的展示位置，再在展示位置层级排除。**

步骤：
1. 用 `placement_view` 查询找出高消耗、低转化的合作站点 URL。
2. 在广告系列或账户层级的"排除展示位置"里加该 URL。
3. 也可以在 API 里对该 placement 做负向处理。

注意：单站排除比"整网关闭"更精细，
适合只对个别劣质站点做定向治理的场景。

```python
# 找到应排除的 placement
from scripts.google_ads_api import GoogleAdsApi
api = GoogleAdsApi()
q = """
SELECT placement.url, metrics.cost_micros, metrics.conversions
FROM placement_view
WHERE segments.date DURING LAST_30_DAYS
  AND metrics.conversions = 0
ORDER BY metrics.cost_micros DESC
"""
r = api.search("1234567890", q)
for row in r.rows[:20]:
    print(row["placement.url"], round(row["metrics.cost_micros"]/1e6, 2))
```

### Q7. 整网关闭 SPN 会影响 PMax 吗？

**不会直接影响。**

- 传统搜索广告系列的 SPN 开关，是独立的设置。
- PMax 的流量分配由系统决定，
  你关掉传统搜索的 SPN，并不会让 PMax 停止投 SPN。

如果你希望"整个账户都不投 SPN"，
需要同时处理传统搜索系列的 SPN 开关，
并接受 PMax / App 系列仍会用到搜索伙伴这一点。

### Q8. 我的 SPN 出价太高，怎么把成本压下来？

**核心是把它跟 Google.com 解耦，再单独压低出价。**

因为同一广告系列里无法对 SPN 单独出价，
所以必须走拆分。

步骤：
1. 把 SPN 流量拆到独立广告系列。
2. 对 SPN 系列用更低的 tCPA 或更小的预算。
3. 加激进负向词，砍掉高消费零转化词。
4. 观察 1-2 周，逐步把 SPN CPA 压到可接受范围。

### Q9. 搜索词报告显示一堆和业务无关的词，怎么办？

**这说明 SPN 的放宽匹配触发了无关词，需要用负向词收敛。**

排查动作：
1. 拉一个月的搜索词报告，按花费降序。
2. 找出"高展示高消费但零转化"且语义无关的词。
3. 逐个加入负向词（短语/包含式）。
4. 持续迭代，直到 SPN 无关词占比降到可接受水平。

```python
from scripts.google_ads_api import GoogleAdsApi
api = GoogleAdsApi()
q = """
SELECT search_term_view.search_term,
       metrics.clicks, metrics.cost_micros, metrics.conversions
FROM search_term_view
WHERE segments.date DURING LAST_30_DAYS
  AND metrics.cost_micros > 2000000
ORDER BY metrics.cost_micros DESC
"""
r = api.search("1234567890", q)
for row in r.rows:
    print(row["search_term_view.search_term"],
          row["metrics.clicks"],
          round(row["metrics.cost_micros"]/1e6, 2),
          row["metrics.conversions"])
```

### Q10. 为什么关了 SPN 之后整体转化率反而上升？

**因为优质流量的相对权重上升了。**

关闭 SPN 后，预算全部回到 Google.com 系列，
而 Google.com 的 CVR / 客单价更高。

所以即便总点击量下降，总转化与 ROAS 往往更健康。
这正是拆分（而非放任）价值的直接体现。

### Q11. SPN 会产生无效点击/点击轰炸吗？如何防护？

**部分灰产合作站点存在此类风险。**

防护手段：
1. 在广告系列层级关闭 SPN（最彻底）。
2. 保留管理时，用 placement_view 主动单站排除。
3. 落地页加反扒（爬虫/机器人）防护。
4. 关注异常高点击量、异常低转化、极高 IP 重复率的时段。

### Q12. 我的 SPN 和 Google.com 用了不同落地页，可以吗？

**可以，而且推荐。**

拆分的好处之一，
就是能为两类流量定制不同落地页与落地页参数。

- Google.com 落地页：强调转化、首屏 CTA 前置。
- SPN 落地页：可以加品牌背书以对冲较低意图,
  或加简单问卷来过滤低质流量。

用 UTM / 落地页参数区分，便于归因与 A/B 测试。

### Q13. 有没有办法在关键词层级控制 SPN？

**没有。**

SPN 的开关粒度固定在广告系列层级。
你无法对同一个广告系列里的关键词单独指定投不投 SPN。

这是平台限制，不是设置遗漏。
因此想要关键词级控制，只能通过"不同广告系列挂不同关键词"来实现。

### Q14. 为什么我的 SPN 报表里 conversions_value 很低或为 0？

**可能原因：**

1. 转化回传依赖落地页，部分 SPN 流量被截断。
2. `conversions_value` 只在配置了"价值"的转化行为才有值。
3. 若用 `generate_report` 默认排除了部分转化，会导致数值偏低。

排查动作：
1. 检查转化行为是否配置了 value。
2. 核对 `all_conversions` 与 `conversions` 口径。
3. 检查归因窗口是否覆盖 SPN 的延迟转化。

```python
from scripts.google_ads_api import GoogleAdsApi
api = GoogleAdsApi()
q = """
SELECT segments.channel,
       metrics.conversions,
       metrics.all_conversions,
       metrics.conversions_value
FROM campaign
WHERE segments.date DURING LAST_14_DAYS
"""
r = api.search("1234567890", q)
for row in r.rows:
    print(row["segments.channel"],
          row["metrics.conversions"],
          row["metrics.all_conversions"],
          row["metrics.conversions_value"])
```

### Q15. eCPM 在 SPN 场景下怎么看？

**eCPM 更适合衡量展示广告，SPN 是搜索型流量。**

对 SPN 更合理的指标是：
- 点击成本 CPA。
- 点击率 CTR。
- 转化价值 ROAS。

若确实要参考 eCPM，可自行计算：
`eCPM = cost / (impressions/1000)`，
用于对比不同站点/关键词的展示效率，辅助单站排除。

### Q16. 用什么频率复盘 SPN 最合理？

**建议分级复盘：**

| 频率 | 动作 | 目标 |
|------|------|------|
| 每日 | 看异常（点击轰炸、预算爆单） | 止损 |
| 每周 | 体检 SPN 占比、负向词、单站排除 | 控质量 |
| 每月 | 整账户 SPN 拆分与预算再分配 | 调结构 |
| 每季度 | 双系列对照实验总结、SOP 迭代 | 沉淀方法论 |

### Q17. 我的广告系列是 MAXIMIZE_CONVERSIONS，SPN 还是投了，正常吗？

**正常。**

`MAXIMIZE_CONVERSIONS` 会让系统在预算内尽量多拿转化。
系统发现 SPN 有机会带来转化时，就会继续投放。

如果你不想它在 SPN 上抢量，
就在广告系列设置里显式关闭 SPN，
或用更低的预算限定它的发挥空间。

### Q18. 拆分 SPN 后，老广告系列的历史数据会丢吗？

**不会丢。**

历史数据保留在原广告系列里。
拆分是"新建系列承接新流量",
不影响已发生数据的查看与审计。

建议在拆分时：
1. 保留原系列用于历史对照（可暂停不改动）。
2. 新建 A/B 两个系列承接未来的 Google 与 SPN 流量。
3. 沿用统一的命名规范，便于报表聚合。

### Q19. SPN 和再营销（Remarketing）能不能叠加？

**能，但要分清渠道。**

SPN 属于搜索伙伴的搜索型流量；
再营销是可以作用在搜索、展示等多个渠道上的受众策略。
两者可以同时存在。

但在 SPN 拆分治理时，
要避免对同一受众在 Google.com 与 SPN 系列里重复出价内耗。
建议把再营销受众主要用在 Google Only 系列上。

### Q20. 有没有一劳永逸的办法？

**没有一劳永逸，但有稳定基线。**

SPN 是动态的：合作站点在变、流量质量在变、关键词匹配在变。
能做的，是建立一套可重复的治理流程（见 3.14 SOP），
让 SPN 始终处于"已知、可解释、可控"的状态，
而不是放任不管地"听天由命"。

---

## 五、自测题

### 题目 1：报告分离

假设你的账户报告里只看到一行"搜索"数据，
你如何在不增加预算的前提下，
确认其中有多少是来自 SPN 的点击？

请写出具体的 GAQL 维度与判断思路。

<details><summary>答案</summary>

在 GAQL 查询中加入 `segments.channel` 维度，
把统计按 `SEARCH` 与 `SEARCH_PARTNERS` 拆开。

示例：

```python
SELECT
    segments.channel,
    metrics.clicks,
    metrics.cost_micros,
    metrics.conversions
FROM campaign
WHERE segments.date DURING LAST_30_DAYS
```

返回里会出现两行：
- `SEARCH`：Google.com 流量。
- `SEARCH_PARTNERS`：搜索合作伙伴流量。

用 `clicks` 或 `cost_micros` 计算 SPN 占比：
`SPN占比 = SPN_clicks / (SEARCH_clicks + SPN_clicks) * 100`。

这就是"零预算增量"地量化 SPN 的第一步。
</details>

### 题目 2：拆分决策

一个教育广告系列合并投放时整体 CVR 为 1.8%，
拆分后 Google Only CVR 为 2.7%、SPN CVR 为 1.4%。

请问为什么拆分后整体效率反而上升？
你认为"是否值得拆分"应看哪些量化指标？

<details><summary>答案</summary>

拆分后整体效率上升的原因：
预算从低质量的 SPN 流量回流到高质量的 Google.com 流量上，
优质流量拿到了更多预算与更多转化机会，
即便总点击量下降，总转化与 ROAS 仍更健康。

是否值得拆分的量化判据：
1. SPN 点击占比（>25% 值得考虑）。
2. SPN CVR / SEARCH CVR（<60% 说明相对质量差）。
3. SPN CPA / SEARCH CPA（>1.6x 说明单位成本过高）。
4. SPN 无效点击率是否明显偏高。
5. 拆分后总转化量是否不降反升（案例中 +18%）。

当满足 2 条以上时，建议执行拆分。
</details>

### 题目 3：排除粒度

为什么"在广告系列层级关闭 SPN"比"在报告里过滤 SEARCH_PARTNERS 行"更彻底？
两者在数据上有什么本质区别？

<details><summary>答案</summary>

区别在"是否影响真实流量投放"：

1. 在报告里过滤 SEARCH_PARTNERS 行，只是"展示层"的隐藏，
   广告依然会真实投放到 SPN 站点上并产生点击与费用。
2. 在广告系列层级关闭 SPN，是"投放层"的阻断，
   Google 不再把广告投放到搜索伙伴站点，流量不再产生。

所以：
- 报告过滤 → 只改变"你看到的数"，不改变"实际发生的费用"。
- 层级关闭 → 从源头掐断 SPN 流量，真实减少 SPN 花费。

想要真正治理 SPN，必须用投放层动作（关闭/拆系列），
而不是只靠报告过滤自欺欺人。
</details>

### 题目 4：负向词策略

SPN 引入了大量放宽匹配的长尾词与无关词。
请说明为什么 SPN 系列需要"比 Google.com 更激进"的负向词清单，
并给出至少两类典型需要屏蔽的词。

<details><summary>答案</summary>

原因：
SPN 站点上的相关性判定比 Google.com 更宽松，
放宽匹配更容易触发近似词、错拼、语义衍生。
这些长尾与噪音词点击成本高、转化率低，
若不做收敛会严重拉低 SPN 系列效率。

典型需要屏蔽的词：
1. 免费/破解类：free、crack、torrent、注册码。
2. 资料/下载类：pdf、模板、下载、网盘。
3. 求职/招聘类：招聘、找工作的。
4. 纯资讯/对比类：知乎、百科、是什么。
5. 无法服务的地域词或竞品品牌词。

做法：
用短语或包含式负向词收敛，
并每周用搜索词报告反哺负向词清单，
持续把高消费零转化词剔除。
</details>

### 题目 5：第三方归因差异

为什么 SPN 的转化在第三方监控工具里常常"丢失"或归因错误？
请列出至少 3 个原因，并给出对应的缓解措施。

<details><summary>答案</summary>

三个主要原因：
1. 合作站点环境可能拦截第三方追踪脚本（cookie / JS），
   导致第三方无法完成转化回传。
2. SPN 常用新窗口打开落地页，丢失 referrer 与部分会话上下文，
   第三方归因时被归为"直接访问"或"其他"。
3. 归因窗口与去重规则不同（Google vs 第三方），
   造成跨渠道数字不一致。

缓解措施：
1. 落地页统一打清晰 UTM 参数（utm_source/medium/campaign/content）。
2. 使用服务器端转化追踪，弥补网页端被截断的丢失。
3. 对 SPN 系列单独标记（如 utm_content=search_partners），
   便于第三方准确区分渠道。
4. 明确归因窗口口径并统一到同一时间范围后再对比。
</details>

