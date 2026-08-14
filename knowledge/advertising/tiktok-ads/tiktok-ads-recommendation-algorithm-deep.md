# TikTok 推荐算法深度解析：协同过滤、内容理解、冷启动

> **领域**: 广告投放 / TIKTOK_ADS
> **深度**: ⭐⭐⭐⭐⭐ 实战级指南
> **标签**: TIKTOK_ADS, 广告投放
> **更新时间**: 2026-08-14
> **类型**: 深度知识文档

---

> **阅读定位**
> 本文件是全站最深入的 **算法层** 解读文档。
> 它不重复 `day-by-day/tiktok-01-tiktok-recommendation-engine.md` 那篇浅层双塔概览。
> 本文聚焦：协同过滤 CF、矩阵分解（SVD/ALS）、ANN 向量检索（HNSW/IVF）、
> 冷启动、内容理解（多模态）、特征工程、评估指标与广告联动，
> 并展开完整的数学公式与可直接运行的 Python/Go 实现。
>
> **目标读者**
> - 负责 TikTok 投放的优化师 / 代理商操盘手：理解"为什么这个广告跑得起来"。
> - 广告平台的算法 / 数据工程师：拿到可落地的召回-粗排-精排-重排参考实现。
> - 产品 / 增长经理：把模型术语翻译成可度量的业务指标（ROAS / CPA / CTR / CVR / eCPM）。
>
> **阅读时长**: 约 90 分钟（含代码推演）。
> **前置知识**: 线性代数基础、概率论基础、Python 基础、Go 基础。

---

## 目录

1. [一、核心概念与架构](#一核心概念与架构)
2. [二、深度原理解析](#二深度原理解析)
3. [三、生产环境实战](#三生产环境实战)
4. [四、常见问题与排查](#四常见问题与排查)
5. [五、自测题](#五自测题)

---

## 一、核心概念与架构

### 1.1 一句话定位

TikTok 的推荐系统本质上是一个 **多路召回 + 实时重排的多目标学习框架**。

用户在 For You 页（FYP）上每刷一条视频，系统都要在 **毫秒级** 内完成：

1. 从数十亿条内容/广告中召回候选；
2. 用粗排模型粗筛到几千条；
3. 用精排模型逐条打分排序；
4. 用重排做多样性 / 商业化 / 探索的融合；
5. 返回给客户端渲染。

广告的本质是：**在有机推荐序列里插入一条"带着出价和广告主目标的候选"**，
并参与同一套打分排序体系，只是在精排目标里叠加了 **商业化收益项**。

> 关键心智：TikTok 刷出的广告，**不是独立的广告推送链路**，
> 而是"广告即内容"，与有机内容走同一套理解、召回、排序、重排的管线。

---

### 1.2 全链路架构总览（ASCII）

```
┌────────────────────────────────────────────────────────────────────────────┐
│                          TikTok 推荐系统全链路                                │
│                        (For You Page / 广告混排)                            │
└────────────────────────────────────────────────────────────────────────────┘
     │
     ▼ 用户请求 (User Request: user_id, device, context, 上滑时间窗)
┌────────────────────────────────────────────────────────────────────────────┐
│ ① CONTENT UNDERSTANDING  内容理解(离线+近线)                                  │
│    • 多模态编码: 视频帧/音频/ASR字幕/OCR/图像文本 → 多模态 Embedding          │
│    • 语义标签/分类/去重/降质检测                                               │
└────────────────────────────────────────────────────────────────────────────┘
     │  Item Embedding  (内容向量库, 数十亿)
     ▼
┌────────────────────────────────────────────────────────────────────────────┐
│ ② RECALL  召回(多路并行, ~1000-10000 候选)                                    │
│    • U2I: User-Item 双塔向量 ANN 检索 (HNSW / IVF-PQ)                         │
│    • I2I: Item-Item 相似 (看了A → 推B): CF / 向量 / 规则                      │
│    • U2U→U2I: 相似用户喜欢的内容                                               │
│    • 热门兜底 / 同领域 / 关注作者 / 广告池分离                                 │
└────────────────────────────────────────────────────────────────────────────┘
     ▼  合并去重 (dedup) + 粗剪(规则/粗排模型)
┌────────────────────────────────────────────────────────────────────────────┐
│ ③ COARSE RANK  粗排  (几千 → 几百)                                            │
│    • 轻量双塔 / 向量内积快速打分 (FTRL / 简单 MLP)                             │
│    • 保证批次一致性与吞吐量, 每秒数百万级                                     │
└────────────────────────────────────────────────────────────────────────────┘
     ▼
┌────────────────────────────────────────────────────────────────────────────┐
│ ④ FINE RANK  精排  (每 user → 评分)                                           │
│    • 双塔多目标学习: 完播率/点赞/关注/分享/点击/转化                             │
│    • 模型: 双塔(DSSM) / 多任务(MMoE / ESMM / ShareBottom)                      │
│    • 特征: 用户特征+内容特征+上下文特征+交叉特征 (亿级稀疏)                     │
│    • 广告在此叠加商业化价值: score = f(engagement, conversion, revenue)       │
└────────────────────────────────────────────────────────────────────────────┘
     ▼  N 条排序结果
┌────────────────────────────────────────────────────────────────────────────┐
│ ⑤ RERANK  重排                                                              │
│    • 多样性控制 (类目/作者/cta 去重)                                          │
│    • 商业化插槽 (Ad slot 频控/预算/出价)                                       │
│    • 探索与利用 (EE: epsilon-greedy / Thompson / UCB / Bandit)               │
│    • 位置偏移校准 (position bias correction)                                  │
└────────────────────────────────────────────────────────────────────────────┘
     ▼
┌────────────────────────────────────────────────────────────────────────────┐
│ ⑥ 播出 → 行为回流 (展示/播放/完播/点赞/转化/负反馈)                            │
│    → 写日志 → 训练样本 → 更新 Embedding 与排序模型 → 回到 ①                   │
└────────────────────────────────────────────────────────────────────────────┘
```

**全链路一句话**：内容理解把"非结构化"变成"向量 + 标签"，
召回负责"大概率猜中"，精排负责"精确排序"，
重排负责"商业与体验的平衡"，行为回流负责"让模型持续进化"。

---

### 1.3 双塔模型（DSSM）—— 全链路的地基

双塔（Two-Tower / DSSM）是 TikTok 召回与早期粗排的核心结构。

核心思想：
- 把 **用户** 编码成一个向量 `u`（用户塔），把 **内容/广告** 编码成一个向量 `v`（物品塔）。
- 两者通过 **内积**（或余弦）计算相关性得分。

```
用户塔 User Tower                        物品塔 Item Tower
┌──────────────────┐                    ┌──────────────────┐
│  user_id          │                    │  video id        │
│  age/gender/geo   │                    │  category 标签    │
│  历史点击序列      │                    │  多模态embedding   │
│  兴趣标签(稀疏)    │                    │  广告特征(出价/cta) │
│      │            │                    │      │           │
│      ▼            │                    │      ▼           │
│  Embedding 层     │                    │  Embedding 层     │
│  (查表/聚合)       │                    │  (查表/聚合)        │
│      │            │                    │      │           │
│      ▼            │                    │      ▼           │
│  全连接 MLP        │                    │  全连接 MLP        │
│      │            │                    │      │           │
│      ▼            │                    │      ▼           │
│  用户向量 u  ∈ R^d │                    │  物品向量 v ∈ R^d  │
└────────┬─────────┘                    └────────┬─────────┘
         │                                       │
         └───────────────► 内积 ◄───────────────┘
                          score = <u, v>
                          P(click) = σ(<u,v>)
```

双塔的优点：
- 用户塔与物品塔 **可以离线预计算**，在线只做一次向量检索（ANN），延迟极低。
- 方便做 **大规模召回**：把全部物品向量建索引，按当前用户向量做近邻检索。

双塔的缺点：
- 用户与物品 **缺少特征交叉**（只能在内积处交互），表达能力弱于深度交叉模型。
- 因此精排阶段通常用 **更重的模型**（含交叉特征 / Transformer / 多目标）来弥补。

> 演进路线：双塔（召回/粗排）→ 精排用 DeepFM / DIN / DCN / MMoE / ESMM 等多目标深度模型，
> 再往后 TikTok 会引入多模态大模型、序列建模（Transformer）、联邦学习（隐私）等方向。

---

### 1.4 广告在推荐中的位置：广告即内容

在有机推荐里，候选是"创作者上传的视频"；
在广告场景，候选是"广告主的广告创意（视频/图片/直播/Spark）"。

广告与有机走**同一套召回与排序**，区别在于：

| 维度 | 有机内容 | 广告 |
|------|----------|------|
| 来源 | 创作者上传 | 广告主通过 Marketing API 提交 |
| 排序目标 | 完播/点赞/关注/分享 | 转化/安装/购买/加购 + 平台收益 |
| 关键信号 | 用户互动 | 出价(bid) + 预算 + 转化目标 + CVR 预估 |
| 商业化项 | 无 | score 里叠加 revenue/adSpend 期望 |
| 频控 | 少 | 严格频控(同广告不连续刷到) |
| 负反馈 | 不感兴趣 | 广告负反馈(隐藏/举报)同样记录 |

**广告打分融合示意（精排）**

```
final_score(user, ad) =
    w1 * engagement_model(user, ad)     # 完播/点赞/分享 (有机侧)
  + w2 * conversion_model(user, ad)     # CTR * CVR (转化侧)
  + w3 * revenue_model(user, ad)        # 竞拍价值 / 出价 * 期望转化
  - w4 * negative_feedback_penalty      # 负向信号惩罚
其中权重 w1..w4 由业务/平台目标动态调节，并受广告主出价约束。
```

广告主能直接影响的环节：
- **出价策略**（`get_bid_strategy_options`：AUTO_BID / MAXIMIZE_CONVERSIONS / MANUAL / CPA）。
- **优化目标**（`get_campaign_objective_options` / `optimization_goal`：CONVERT / APP_INSTALL / CLICK / COMPLETE_PAYMENT 等）。
- **定向** 不直接控制算法，但能缩小召回范围（受众/年龄段/地区/兴趣）。

> 广告主视角的"算法攻略"：**你改不了模型，但你能改变喂给模型的特征与目标。**
> 提供高 CVR 的转化回传、给足数据量、让出价匹配真实转化价值，
> 算法自然会把你的广告推给最可能转化的人。

---

### 1.5 冷启动在整体链路中的位置

冷启动分为三层，对应不同对象：

| 冷启动对象 | 含义 | 关键难点 |
|-----------|------|---------|
| 新用户 (New User) | 无历史行为 | 无法召回个性化内容 → 用规则/热门/兴趣建模 |
| 新视频 (New Item) | 无互动数据 | 无法估分 → 用内容理解 + 少量探索试探 |
| 新广告 (New Campaign) | 广告无转化数据 | 无法估 CVR → 用定向 + 相似受众 + 小预算试探 |

广告冷启动尤其重要：新广告组没有转化回传，系统只能靠 **内容理解 + 受众相似度** 估分，
所以 TikTok 优化师常说"新广告要过冷启动期（learning phase）"。

**广告冷启动期（Learning Phase）**

| 阶段 | 行为 | 系统状态 |
|------|------|---------|
| 探索期 | 系统广撒网找人 | 数据不足, 出价高于稳态 |
| 学习期 | 积累 50 个转化(标准) 或若干转化 | 模型学习 CVR |
| 稳定期 | 模型收敛, 成本回归 | 正常出价, 稳定投放 |

> 关键量化指标：TikTok 认为一个新广告组大约需要 **积累 50 个优化事件** 才能退出学习期。
> 若长期（如 72 小时）无法积累转化，广告会进入 **learning phase stalled（学习停滞）**，成本失控。

---

### 1.6 核心评估维度（业务量化）

在往下钻算法原理前，先建立统一的"业务语言"。

| 指标 | 全称/含义 | 公式要点 | 广告场景解读 |
|------|----------|---------|-------------|
| CTR | Click-Through Rate 点击率 | 点击/展示 | 素材吸引力 + 人群匹配度 |
| CVR | Conversion Rate 转化率 | 转化/点击 | 落地页 + 受众 + 期望 |
| eCPM | 每千次展示有效收入 | 1000*Revenue/Impression | 平台收益视角 |
| CPA | Cost Per Action 单转化成本 | spend/conversions | 广告主花钱买结果 |
| ROAS | Return On Ad Spend 广告支出回报 | revenue/spend | 电商核心指标 |
| 完播率 | Completion Rate | 完播/播放 | 内容质量关键 |
| HitRate / Recall@K | 命中率 | 推荐里命中真值的比例 | 离线评估用 |
| Gini / 多样性 | 推荐多样性 | 类目/作者分布 | 体验指标 |

> 下方的 API 示例都会围绕这些指标展开。
> 记住：**一个指标改不动算法，但多个指标 + 预算 + 出价 = 模型的学习信号。**
> 你给系统喂什么目标，系统就优化什么。

---

## 二、深度原理解析

### 2.1 协同过滤（Collaborative Filtering, CF）

协同过滤是推荐系统的"老祖宗"，
核心假设：**志趣相投的人会喜欢相似的东西**。

它分两大类：
- **User-based CF**：找"与我相似的用户"，推荐他们喜欢的而我未看过的。
- **Item-based CF**：找"与我点过的物品相似的物品"。

#### 2.1.1 数学形式化

记用户集合 `U = {u1, u2, ..., um}`，物品集合 `I = {i1, i2, ..., in}`。

构建 **用户-物品交互矩阵 R**（m×n），其中：

```
R[u][i] =
    1    用户 u 对物品 i 有正向交互(点击/完播/点赞)
    0    无交互(未看 / 未交互)
    [-1, 1]  如果是评分数据(如点赞+1, 不感兴趣-1)
```

矩阵通常是 **极度稀疏** 的：
- 真实点击率低于 5%，意味着矩阵 95%+ 是 0。
- 直接存稠密矩阵不现实，必须用 **稀疏存储**。

#### 2.1.2 相似度度量

**余弦相似度（Cosine Similarity）**

```
              u · v
sim(u,v) = ─────────────
           ‖u‖ · ‖v‖
```

对用户 u 与 v，把它们在所有物品上的行为向量看成两个高维向量，
余弦夹角越小越相似。

**皮尔逊相关系数（Pearson Correlation）**

先去均值（消除用户打分整体偏高/偏低的影响）再算：

```
              Σ_i (r_ui - r̄_u)(r_vi - r̄_v)
sim(u,v) = ─────────────────────────────────────────────
           sqrt(Σ_i (r_ui - r̄_u)²) · sqrt(Σ_i (r_vi - r̄_v)²)
```

其中 `r̄_u` 是用户 u 的平均分。
皮尔逊适合 **评分型** 数据，能抵消"手松的都给高分"这类系统性偏差。
余弦适合 **隐式交互(0/1)** 数据。

#### 2.1.3 User-based CF 预测

用户 u 对物品 i 的预测分：

```
                 Σ_{v ∈ N(u)} sim(u,v) · r_vi
pred(u, i) = ─────────────────────────────────────
                 Σ_{v ∈ N(u)} |sim(u,v)|

N(u) = 与 u 最相似的前 K 个用户 (KNN)
```

含义：找出与 u 最像的 K 个邻居，他们对 i 的评分的加权平均，权重就是相似度。

#### 2.1.4 Item-based CF 预测

用户 u 对物品 i 的预测分（j 是 u 交互过的物品）：

```
                 Σ_{j ∈ I(u)} sim(i,j) · r_uj
pred(u, i) = ─────────────────────────────────────
                 Σ_{j ∈ I(u)} |sim(i,j)|
```

#### 2.1.5 ItemCF Python 实现（可直接运行）

```python
"""
Item-based Collaborative Filtering
基于隐式交互(0/1)的 ItemCF 的最小可用实现。
矩阵极小, 用 dict of dict 存储稀疏矩阵, 避免 O(n²) 内存。
"""
from collections import defaultdict
import math


def build_item_similarity(user_item: dict) -> dict:
    """
    user_item: {user: {item: interaction_weight}}
    返回 {item_a: {item_b: sim}} 的稀疏相似度矩阵。
    """
    # 1. 统计每个物品被多少人交互过
    item_pop = defaultdict(int)
    for user, items in user_item.items():
        for item in items:
            item_pop[item] += 1

    # 2. 统计物品对共现次数 (协同过滤的"共同喜欢"信号)
    co_count = defaultdict(lambda: defaultdict(int))
    for user, items in user_item.items():
        item_list = list(items.keys())
        for i in range(len(item_list)):
            wi = item_list[i]
            for j in range(i + 1, len(item_list)):
                wj = item_list[j]
                co_count[wi][wj] += 1
                co_count[wj][wi] += 1

    # 3. 归一化相似度 (用两人气物品做惩罚, 避免热门物品主导)
    sim = {}
    for wi, wjs in co_count.items():
        sim[wi] = {}
        for wj, cnt in wjs.items():
            denom = math.sqrt(item_pop[wi] * item_pop[wj])
            sim[wi][wj] = cnt / denom if denom > 0 else 0.0
    return sim


def recommend(user_item: dict, sim: dict, user: str, top_k: int = 5) -> list:
    """
    给 user 推荐 top_k 个物品。
    思路: 对每件用户交互过的物品 a, 累加它相似物品 b 的分数。
    """
    interacted = set(user_item.get(user, {}).keys())
    scores = defaultdict(float)
    for a in interacted:
        for b, s in sim.get(a, {}).items():
            if b in interacted:
                continue  # 已交互, 不重复推荐
            scores[b] += s
    ranked = sorted(scores.items(), key=lambda x: -x[1])[:top_k]
    return [item for item, _ in ranked]


if __name__ == "__main__":
    # 玩具数据: 5 个用户, 6 个物品
    data = {
        "u1": {"A": 1, "B": 1, "C": 1},
        "u2": {"A": 1, "B": 1},
        "u3": {"B": 1, "C": 1},
        "u4": {"A": 1, "D": 1, "E": 1},
        "u5": {"D": 1, "E": 1, "F": 1},
    }
    sim = build_item_similarity(data)
    rec = recommend(data, sim, user="u3", top_k=3)
    print("u3 的推荐:", rec)
    # 预期: 与 u3 交互过 B,C 相似的是 A (u2,u1 共同), 所以 A 分最高
```

**用户偏移注意**：真实 ItemCF 在物品量大时稀疏矩阵也很大，
线上通常用 **Presto/离线任务** 周期重建相似度表，
再下发到 Redis/向量库做在线查询，而不是在线实时算相似度。

#### 2.1.6 UserCF Python 实现

```python
"""
UserCF 最小实现: 用户相似度 + KNN 邻居加权预测。
与 ItemCF 的差别在于以"用户"为单位聚合。
"""
from collections import defaultdict
import math


def build_user_similarity(user_item: dict) -> dict:
    # 每个用户的行为向量
    users = list(user_item.keys())
    sim = {}
    # 简单实现 O(U²·|I|), 线上需优化
    for i in range(len(users)):
        ua = users[i]
        set_a = set(user_item[ua].keys())
        sim[ua] = {}
        for j in range(i + 1, len(users)):
            ub = users[j]
            set_b = set(user_item[ub].keys())
            inter = set_a & set_b
            if not inter:
                continue
            cosine = len(inter) / math.sqrt(len(set_a) * len(set_b))
            sim[ua][ub] = cosine
            sim[ub][ua] = cosine
    return sim


def recommend_usercf(user_item, sim, user, top_k=5, n_neighbors=3):
    interacted = set(user_item[user].keys())
    neighbors = sorted(sim.get(user, {}).items(), key=lambda x: -x[1])[:n_neighbors]
    scores = defaultdict(float)
    for nb, s in neighbors:
        for item in user_item[nb]:
            if item in interacted:
                continue
            scores[item] += user_item[nb][item] * s
    return [x for x, _ in sorted(scores.items(), key=lambda x: -x[1])[:top_k]]


if __name__ == "__main__":
    data = {
        "u1": {"A": 1, "B": 1, "C": 1},
        "u2": {"A": 1, "B": 1, "D": 1},
        "u3": {"B": 1, "C": 1},
        "u4": {"A": 1, "E": 1},
    }
    sim = build_user_similarity(data)
    print("u2 的推荐:", recommend_usercf(data, sim, "u2", top_k=3))
```

> CF 的致命弱点：**稀疏性与冷启动**。
> 新用户、新物品没有历史交互，CF 完全失效——这正是下文矩阵分解 + 侧路召回 + 冷启动要解决的问题。

---

### 2.2 矩阵分解（MF）：SVD / ALS

CF 的直接相似度计算在稀疏矩阵上很脆弱。
矩阵分解（Matrix Factorization, MF）把 m×n 的交互矩阵 **分解** 成两个低秩矩阵的乘积：

```
R[m×n] ≈ P[m×k] · Q[k×n]

P 的每一行 = 用户 u 的隐向量 (latent vector) p_u ∈ R^k
Q 的每一列 = 物品 i 的隐向量 q_i ∈ R^k
预测: r̂_ui = p_u · q_i   (内积)
```

k 是隐因子数量（超参数，通常 8~256）。
MF 的本质：把"用户对物品的评分"建模为 **用户隐向量与物品隐向量的内积**。

#### 2.2.1 SVD / Funk SVD（隐式反馈改进版）

经典 SVD 要求矩阵完整，不适合稀疏。
Funk SVD（Simon Funk 在 Netflix 竞赛提出）只对 **已观测** 的 (u,i) 优化：

```
损失函数:
min  Σ_{(u,i) ∈ R_obs} (r_ui - p_u·q_i)²  +  λ( ‖p_u‖² + ‖q_i‖² )

λ 是正则化系数, 防止过拟合。
```

用 **随机梯度下降 SGD** 迭代：

```
误差 e_ui = r_ui - p_u·q_i
梯度:
  ∂L/∂p_u = -2·e_ui·q_i + 2λ·p_u
  ∂L/∂q_i = -2·e_ui·p_u + 2λ·q_i

更新(学习率 α):
  p_u ← p_u + α · (e_ui·q_i - λ·p_u)
  q_i ← q_i + α · (e_ui·p_u - λ·q_i)
```

#### 2.2.2 ALS（交替最小二乘）Python 实现

ALS（Alternating Least Squares）是 Spark 里 `ALS` 模块的经典算法。
核心思想：固定一个矩阵，另一个就是 **可解析求解的最小二乘问题**，交替优化两个矩阵。

```python
"""
ALS (Alternating Least Squares) 矩阵分解的最小实现。
用于隐式反馈: 用置信度加权而非 0/1, 近似 Spark MLLib ALS。
"""
import numpy as np


def als_implicit(
    R,               # 稀疏交互: dict {user: {item: count}}, count 为交互次数
    n_factors=20,    # 隐因子维度 k
    alpha=40.0,      # 置信度缩放
    regularization=0.1,
    n_iterations=20,
    seed=42,
):
    users, items = [], []
    for u in R:
        users.append(u)
        for it in R[u]:
            items.append(it)
    users = sorted(set(users)); items = sorted(set(items))
    u_idx = {u: i for i, u in enumerate(users)}
    i_idx = {it: i for i, it in enumerate(items)}
    n_u, n_i = len(users), len(items)

    rng = np.random.RandomState(seed)
    X = rng.rand(n_u, n_factors) * 0.01   # 用户因子矩阵 P
    Y = rng.rand(n_i, n_factors) * 0.01   # 物品因子矩阵 Q

    # 置信度: c_ui = 1 + alpha * count   (越多交互越确信喜欢)
    # 损失: min Σ c_ui (p_ui - x_u·y_i)² + λ(‖x‖²+‖y‖²)
    # 其中 p_ui = 1 if 有交互 else 0
    for _ in range(n_iterations):
        # 固定 Y, 解 X: x_u = (Yᵀ C_u Y + λI)⁻¹ Yᵀ C_u p_u
        for u in users:
            i = u_idx[u]
            interacted = list(R[u].keys())
            j = [i_idx[it] for it in interacted]
            conf = np.array([1.0 + alpha * R[u][it] for it in interacted])
            Y_j = Y[j]                       # (n_int, k)
            C = conf[:, None]                # 置信度权重
            # A = YᵀC Y + λI,  b = Yᵀ C * 1
            A = (Y_j * C).T @ Y_j + regularization * np.eye(n_factors)
            b = (Y_j * C).T @ np.ones(len(interacted))
            X[i] = np.linalg.solve(A, b)

        # 固定 X, 解 Y
        for it in items:
            j = i_idx[it]
            interacted_users = [u for u in users if it in R[u]]
            i = [u_idx[u] for u in interacted_users]
            conf = np.array([1.0 + alpha * R[u][it] for u in interacted_users])
            X_i = X[i]
            A = (X_i * conf[:, None]).T @ X_i + regularization * np.eye(n_factors)
            b = (X_i * conf[:, None]).T @ np.ones(len(interacted_users))
            Y[j] = np.linalg.solve(A, b)

    return users, items, X, Y  # 用户列表, 物品列表, P, Q


def predict(users, items, X, Y, user, item):
    return float(X[users.index(user)] @ Y[items.index(item)])


if __name__ == "__main__":
    R = {
        "u1": {"A": 5, "B": 3},
        "u2": {"A": 1, "C": 2},
        "u3": {"B": 4, "D": 5},
    }
    users, items, X, Y = als_implicit(R, n_factors=10, n_iterations=30)
    print("u1 对 C 的预测分:", round(predict(users, items, X, Y, "u1", "C"), 4))
```

> 生产提示：
> 1. 用 `sign` 把交互次数 `alpha` 缓存成常数，避免每次重建。
> 2. 隐因子 `k` 越大表达能力越强但也越慢、越容易过拟合，实际取 32~128。
> 3. Spark `ALS` / `MatrixFactorizationModel` 就是这个思路的工程化版本，支持超大矩阵并行。

---

### 2.3 矩阵分解 vs 双塔：同一个内积家族

值得注意的是，**MF 和双塔其实是同一撮血统**：

| 维度 | 矩阵分解 MF | 双塔 DSSM |
|------|------------|-----------|
| 用户侧表示 | 用户隐向量 p_u | 用户塔输出 u (MLP碾压特征) |
| 物品侧表示 | 物品隐向量 q_i | 物品塔输出 v (多模态) |
| 打分 | 内积 p·q | 内积 u·v |
| 侧信息 | 几乎无 | 可吃任意特征 |
| 冷启动 | 弱(无向量) | 强(靠内容特征可估) |
| 定位 | 传统Baseline | 现代主力(召回/精排) |

> 结论：现代 TikTok 用双塔替代了纯 MF，但 **MF/ALS 仍是离线评估、冷启动兜底、相似度计算** 的重要工具。
> 双塔的"用户向量 - 物品向量"结构在数学上与 MF 一脉相承。

---

### 2.4 召回（Recall）详解

#### 2.4.1 召回的目标

召回的目标不是"精确"，而是 **高召回率（Recall）**：
把用户可能感兴趣的内容尽可能都捞出来，宁可多捞（宁滥勿缺），交给精排去排序。

量化目标：Recall@5000 ≥ 0.9（即真实会点击的，90% 都被捞进 top5000 候选）。

#### 2.4.2 多路召回（Candidate Recall Channels）

只用一路召回会漏掉大量可能相关的内容，工业界用 **多路召回** 拼乐高：

```
                    ┌─────────────────────────────┐
                    │  多路召回 (每路产出候选集合)   │
                    └─────────────────────────────┘
   ┌────────┬────────┬────────┬────────┬────────┬──────────┐
   │        │        │        │        │        │          │
   ▼        ▼        ▼        ▼        ▼        ▼
  U2I      I2I      U2U     热门     同领域    作者订阅   广告候选池
 (user→   (item→   (user→   (Popular  (领域/    (Followed   (广告定向
  item)    item)    item)    兜底)    主题)     creators)   召回)
   │        │        │        │        │        │          │
   ▼        ▼        ▼        ▼        ▼        ▼          ▼
  ANN检索   相似度   邻居用户   全局/     主题向量  关注的     定向条件
  (双塔)    (CF/向量) 喜欢的内容  分域热门   检索      作者内容    + 出价过滤
   └────────┴────────┴────────┴────────┴────────┴──────────┘
                          ↓ 全部合并 (union)
                  去重 + 粗剪(负向过滤/硬规则)
                          ↓ 混合后送粗排
```

#### 2.4.3 U2I（User → Item）召回：双塔 + ANN

U2I 是最主流的一路：
- 用户塔算出用户向量 `u`。
- 物品塔算出所有物品向量 `v`（离线算好入库）。
- 在线用 ANN 检索"与 u 内积最大的 top K 个 v"。

```python
"""
双塔 U2I 召回的离线训练 + 在线近邻检索 PyTorch 示意。
展示结构: 用户塔 / 物品塔 各自 MLP → L2归一化 → 内积打分。
"""
import torch
import torch.nn as nn


class TwoTower(nn.Module):
    """双塔模型: 用于召回(训练), 输出用户/物品向量与内积。"""

    def __init__(self, n_users, n_items, n_factors=64,
                 user_feat_dim=32, item_feat_dim=48):
        super().__init__()
        # 可学习 ID Embedding (纯 MF 分量)
        self.user_emb = nn.Embedding(n_users, n_factors)
        self.item_emb = nn.Embedding(n_items, n_factors)
        # 用户塔: 聚合连续特征 → MLP
        self.user_tower = nn.Sequential(
            nn.Linear(n_factors + user_feat_dim, 128),
            nn.ReLU(),
            nn.Linear(128, 64),
            nn.Linear(64, n_factors),
        )
        # 物品塔: 多模态/文本特征 → MLP
        self.item_tower = nn.Sequential(
            nn.Linear(n_factors + item_feat_dim, 128),
            nn.ReLU(),
            nn.Linear(128, 64),
            nn.Linear(64, n_factors),
        )

    def get_user_vec(self, user_id, user_feat):
        h = torch.cat([self.user_emb(user_id), user_feat], dim=-1)
        return nn.functional.normalize(self.user_tower(h), dim=-1)

    def get_item_vec(self, item_id, item_feat):
        h = torch.cat([self.item_emb(item_id), item_feat], dim=-1)
        return nn.functional.normalize(self.item_tower(h), dim=-1)

    def forward(self, user_id, user_feat, item_id, item_feat):
        u = self.get_user_vec(user_id, user_feat)
        v = self.get_item_vec(item_id, item_feat)
        return (u * v).sum(dim=-1)   # 内积 → logit


# 采样批(uv) 的正负样本
def sample_batch(user_ids, pos_items, neg_items, **feats):
    batch = {
        "user_id": torch.tensor(user_ids),
        "item_id_pos": torch.tensor(pos_items),
        "item_id_neg": torch.tensor(neg_items),
    }
    return batch


def train_step(model, opt, batch, user_feat_dim, item_feat_dim):
    opt.zero_grad()
    u = model.get_user_vec(batch["user_id"],
                           torch.zeros(len(batch["user_id"]), user_feat_dim))
    vp = model.get_item_vec(batch["item_id_pos"],
                            torch.zeros(len(batch["item_id_pos"]), item_feat_dim))
    vn = model.get_item_vec(batch["item_id_neg"],
                            torch.zeros(len(batch["item_id_neg"]), item_feat_dim))
    pos_logit = (u * vp).sum(-1)          # 正样本内积
    neg_logit = (u * vn).sum(-1)          # 负样本内积
    # BPR loss: -log σ(pos - neg), 让正样本得分高于负样本
    loss = -torch.log(torch.sigmoid(pos_logit - neg_logit)).mean()
    loss.backward()
    opt.step()
    return loss.item()
```

#### 2.4.4 双塔如何做在线 ANN 检索

训练好双塔后，把物品向量 `v` 全部写入 **ANN 索引**，
在线按用户向量 `u` 检索 top K：

```
流程:
1. 离线: forward 一遍全量物品 → 得到全量 item embedding
         → 写入 HNSW / IVF-PQ 索引 (向量 + 内积度量)
2. 在线: 用户请求到 → 用户塔算 u
         → ANN 检索出 top K 个内积最大的 item id
         → 取 item 元数据 → 进精排

度量: 内积(Inner Product) 或 余弦(Cosine), 取决于归一化。
```

#### 2.4.5 ANN 索引：HNSW / IVF（近似最近邻）

精确 KNN 在大规模(亿级)下不可行（O(N) 扫描太慢），
工业界用 **ANN（近似最近邻）** 在"召回率 vs 速度"之间取舍。

**a) HNSW（Hierarchical Navigable Small World）**

多层跳表思想的可导航小世界图：

```
HNSW 多层图结构示意 (层数越高跳得越快)

Layer 2:      A ───── B                (高层: 粗粒度, 长距离跳)
               \     /
Layer 1:      A ── C ── B ── D
               \   |       |
Layer 0:      A ─ X ─ C ─ Y ─ B ─ Z ─ D   (底层: 细粒度, 精确邻居)

检索: 从顶层粗跳到目标区域, 逐层下探到底层精细搜索
```

- 优点：召回率接近精确 KNN、检索快、支持增量插入。
- 内存占用：图本身较大，适合几十万~千万级。
- 常用库：`hnswlib`、`faiss.IndexHNSWFlat`。

**b) IVF（Inverted File）+ PQ（乘积量化）**

倒排文件 + 乘积量化，是 Faiss 里最常用的压缩索引：

```
IVF 倒排索引示意

            K 个聚类中心 (粗聚类, 如 K=4096)
         ┌────┐ ┌────┐ ... ┌────┐
         │ C1 │ │ C2 │      │ CK │
         └────┘ └────┘      └────┘
           ▼      ▼           ▼
       倒排列表(桶) 每个桶存: 经 PQ 量化的向量压缩码
       list1: (id, 压缩码)...  list2: ...  listK: ...

检索: 1. 把查询向量 u 归到最近的几个桶(nprobe, 如 nprobe=16)
     2. 只在桶内做精确 / 量化距离计算
     3. PQ: 向量切成 m 段, 每段用码本查距离表, 加速距离计算
```

- 优点：内存极省（PQ 压缩 8~32 倍）、支持亿万级。
- 缺点：召回率略低于 HNSW、需离线建聚类（增量难度大）。
- 常用：`faiss.IndexIVFPQ`。

**Faiss 建 IVFPQ 索引代码（Python）**

```python
import faiss
import numpy as np

def build_ivfpq_index(embeddings: np.ndarray, nlist=4096, m=32, nbits=8, seed=7):
    """
    训练并构建 IVF-PQ 索引。
    embeddings: (N, d) float32, 需 L2 归一化后使用内积。
    """
    d = embeddings.shape[1]
    quantizer = faiss.IndexFlatL2(d)                 # 粗量化器(聚类)
    index = faiss.IndexIVFPQ(quantizer, d, nlist, m, nbits)
    rng = np.random.RandomState(seed)
    sample_idx = rng.choice(len(embeddings), min(1_000_000, len(embeddings)))
    index.train(embeddings[sample_idx])              # 训练聚类中心 + PQ码本
    index.add(embeddings)                            # 加入全量向量
    return index

def recall_topk(index, query_vec, k=100, nprobe=32):
    index.nprobe = nprobe  # 检索的桶数, 越大召回越高越慢
    scores, ids = index.search(query_vec, k)
    return ids[0], scores[0]

# 使用
# emb = np.random.randn(2_000_000, 64).astype("float32")
# emb = emb / np.linalg.norm(emb, axis=1, keepdims=True)
# idx = build_ivfpq_index(emb)
# ids, scores = recall_topk(idx, emb[[0]])
```

**HNSW 用 hnswlib（Python）**

```python
import hnswlib
import numpy as np

def build_hnsw(embeddings: np.ndarray, M=48, ef_construction=200, ef=100):
    dim = embeddings.shape[1]
    index = hnswlib.Index(space="cosine", dim=dim)
    index.init_index(max_elements=len(embeddings) + 1000, ef_construction=ef_construction, M=M)
    index.add_items(embeddings)
    index.set_ef(ef)               # 检索精度
    return index

def recall_hnsw(index, query_vec, k=100):
    ids, distances = index.knn_query(query_vec, k=k)
    return ids[0]
```

> **工程选型建议**（给工程师）：
>
> | 规模 | 推荐方案 | 原因 |
> |------|---------|------|
> | < 10^6 | HNSW (hnswlib) | 召回高、快、易增量 |
> | 10^6 ~ 10^8 | IVF-PQ (faiss) | 内存可控、可上亿级 |
> | > 10^9 | 分片 + IVF-PQ / HNSW 集群 | 单机装不下, 需要分布式 |

#### 2.4.6 I2I（Item → Item）召回

用户看视频 A 后，推荐与 A 相似的 B。

- **基于相似度**：内容标签 / 多模态向量余弦相似。
- **基于共现（CF）**：看完 A 也看完 B 的用户多 → B 相似。
- **基于主题/同作者**：同领域、同一博主。

```
I2I 召回示意

 用户看过的视频 A
    │
    ├─► 向量相似: A 的 embedding 在 ANN 里检索最接近的 B, C, D
    ├─► 标签相似: 与 A 同 cat/同话题 的高分内容
    └─► 共现(cf): 看了 A 的用户还看了 B,C
```

#### 2.4.7 U2U（User → User → Item）与邻居召回

用 UserCF 找"与我相似的用户"，再推荐他们喜欢而我没看过的。
这也是冷启动期给活跃用户的常用补位。

#### 2.4.8 探索与利用（Exploration vs Exploitation, EE）

推荐不能只推"最可能点"的（利用），那会陷入 **信息茧房 / 同质化**，
还需要 **探索** 新内容、新作者、新广告来发现用户的潜在兴趣。

经典算法：

**a) ε-greedy（ε 贪心）**

```
以概率 ε 随机探索(推荐随机/新内容), 以概率 1-ε 用模型打分(利用)
ε 通常 0.01 ~ 0.1, 广告场景取低值控制成本。
```

**b) Upper Confidence Bound（UCB）**

```
对每个候选保持 收益均值 μ 和 尝试次数 n:
   score = μ + c · sqrt( ln(total_n) / n )
         └  利用 ┘  └──── 探索(置信区间上界) ────┘
越少尝试的候选, 第二项越大 → 鼓励多探索
```

**c) Thompson Sampling（汤普森采样，贝叶斯）**

```
对每个候选假设 收益为 beta(α, β) 分布:
  score = beta 分布随机采样一次
候选的 α/(α+β) 大 → 常被选中; 但每次采样有随机性 → 自然带探索
效果稳健, 常用于广告 CTV/CPM 到价控制。
```

**广告 EE 的实际约束**：广告的探索受 **成本上限** 硬约束——
探索 = 花预算试不同人群，若成本超 CPA 目标会立即限流。

> **广告 EE 落地**：新广告用 **自动出价 + 小预算** 过冷启动，
> 等于让系统在成本护栏内做探索；当模型学会 CVR 后，再逐渐加预算提量。

---

### 2.5 冷启动（Cold Start）

冷启动是推荐系统最难啃的骨头之一，
因为 **没有行为数据就没有个性化**。

#### 2.5.1 三类冷启动对象

| 对象 | 无数据 | 应对策略 |
|------|--------|---------|
| 新用户 | 无历史行为 | 兴趣建模(注册信息/设备/首刷行为) + 冷热门兜底 |
| 新视频 | 无互动 | 内容理解估分 + 少量探索(小流量试探) |
| 新广告 | 无转化回传 | 定向缩小人群 + 相似受众 + 小预算 + 自动出价过渡 |

#### 2.5.2 新用户冷启动策略

```
新用户冷启动漏斗

注册/首刷
   │
   ▼
① 兴趣建模 (内容理解兜底)
   注册信息: 国家/语言/设备/年龄
   首刷 3-5 条: 即时反馈(看完停留/上滑速度) → 快速更新
   │
   ▼
② 冷门热混合
   热门区域内容(保证不会太差) + 少量新内容(试探)
   │
   ▼
③ 探索优先
   用 UCB/Thompson 对新用户多做探索, 快速建立兴趣画像
   │
   ▼
④ 收敛
   行为足够 → 转正常个性化双塔
```

#### 2.5.3 新视频（新内容）冷启动

新视频没有任何互动，估分只能靠 **内容理解**：

```
视频上传
   │
   ▼
① 内容理解(离线):
   多模态编码 → embedding; 打标签/分类; 质检(低质阈值)
   │
   ▼
② 试探投放(探索):
   把新视频 push 给部分高活跃/中性用户 (少量流量)
   │
   ▼
③ 反馈评估:
   完播率/点赞/上滑速度/观看时长 达到阈值?
   是 → 扩大投放; 否 → 降权/撤除
   │
   ▼
④ 门槛(护栏):
   视频有"初始流量池", 通过率低会被移除; 外包拍摄/搬运会被检测
```

#### 2.5.4 新广告冷启动（广告重点）

广告冷启动 = 新广告组没有转化回传，CVR 模型估不准。

```
新广告冷启动(学习期)

创建 Ad Group
   │
   ▼
① 关键条件:
   - 优化的转化目标(如 CONVERT/COMPLETE_PAYMENT)
   - 预算 ≥ 系统建议 (如日预算 ≥ 50×目标CPA)
   - 无硬性定向过窄(否则没流量学习)
   │
   ▼
② 探索阶段(系统广撒网):
   自动出价+相似受众 → 找"可能转化的人"
   │
   ▼
③ 学习期(Learning Phase):
   目标: 积累 50 个转化(标准), 模型学 CVR
   期间不要频繁改素材/出价/定向(会打断学习)
   │
   ▼
④ 退出学习期 → 稳定投放
   不能积累转化 → learning stalled → 重新构思素材/定向
```

**广告冷启动护栏（Guardrail）**

| 护栏 | 做法 | 目的 |
|------|------|------|
| 预算下限 | 日预算 ≥ 系统建议(如 ≥50/CPA) | 保证转化样本量 |
| 频控 | 同广告 24h 内限次展示 | 防撑ak出、防用户疲劳 |
| 负反馈惩罚 | 隐藏/举报→降权 | 保体验 |
| 成本控制 | 超 CPA 目标自动缩量 | 保盈利 |
| 学习期保护 | 学习期少动素材/出价 | 防模型反复重置 |

**TikTok Marketing API 创建冷启动广告组示例**

```python
# 当广告组处于冷启动: 用自动出价+转化目标+合理预算, 最大化学习流量
from tiktok_api import TikTokClient

client = TikTokClient({"access_token": "YOUR_ACCESS_TOKEN"})

# 1. 查当前 campaign 的 objective 选项 (确认支持 CONVERSIONS 目标)
options = client.get_campaign_objective_options()
for opt in options:
    print("objective:", opt.get("objective_type"),
          "optimization_goals:", opt.get("optimization_goals"))

# 2. 创建转化目标广告组 (过冷启动)
resp = client.create_adgroup(
    advertiser_id="YOUR_ADVERTISER_ID",
    adgroup={
        "campaign_id": "CAMPAIGN_ID",
        "name": "cold_start_adgroup",
        "budget": 200.0,
        "budget_mode": "BUDGET_MODE_DAY",
        "bid_type": "AUTO_BID_TYPE_VALUE_MAXIMIZE_CONVERSIONS",  # 自动出价
        "optimization_goal": "COMPLETE_PAYMENT",
        "objective_type": "CONVERSIONS",
        "placement_type_list": ["PLACEMENT_TYPE_TIKTOK"],
        "targeting": {
            "age": ["18", "24", "25", "34"],
            "gender": ["MALE", "FEMALE"],
        },
    },
)
print("cold start adgroup:", resp)
```

> 冷启动最优实践（优化师必读）：
> 1. **转化事件要准确**：Pixel/CAPI 回传的转化必须是"真转化"，虚增会误导算法。
> 2. **一个广告组一个素材/一个受众**：让系统学习关系纯净。
> 3. **学习期别乱动**：改出价/暂停会重置学习进度。
> 4. **用相似受众**：`create_audience` 建 Lookalike 缩小探索空间。

---

### 2.6 内容理解（Content Understanding）

TikTok 的核心竞争力之一：**多模态内容理解**。
把一段"看不懂"的视频，转成"机器能用的向量 + 标签"。

```
┌──────────────────────────────────────────────────────┐
│          内容理解管线 (Content Understanding Pipeline)  │
└──────────────────────────────────────────────────────┘
               视频 / 音频 / 图片 / 文本(字幕)
                        │
      ┌─────────────────┼──────────────────┐
      ▼                 ▼                  ▼
 视觉帧理解          音频理解          文本理解
 (Video Frames)      (Audio)           (Text)
      │                 │                  │
      ▼                 ▼                  ▼
 关键帧抽取          音乐分类/        ASR 语音转文字
 图像分类/检测       音色/情绪          (字幕)
 场景识别            检测              OCR 画面文字
 人脸/物体/动作                        语义标签
      │                 │                  │
      └─────────────────┴──────────────────┘
                        ▼
             多模态特征融合 (early/late fusion)
                        ▼
              ┌─────────────────┐
              │ 多模态 Embedding  │  → 向量检索/精排特征
              │  (dense vector) │
              └─────────────────┘
                        ▼
              ┌─────────────────┐
              │ 语义标签/分类     │  → 召回筛选/去重/规则
              │ (sparse label)  │
              └─────────────────┘
```

#### 2.6.1 各模态能力

**a) 视觉（视频帧）**
- 关键帧采样（抽帧）→ 图像分类 / 检测（物体、场景、人脸、动作）。
- 用预训练 CNN / ViT 提帧级特征 → 时序聚合 → 视频向量。

**b) 音频**
- 音乐/背景音检测（很多 TikTok 爆款靠对口型+音乐）。
- 音色、情绪、语速、是否有原声。
- 音频特征 → 辅助语义。

**c) 文本（ASR 字幕 / OCR 画面文字）**
- ASR：把语音转文字，做语义标签（NLP）。
- OCR：识别画面里的文字（如品牌名、口播关键词）。
- 文本 embedding → 语义向量。

#### 2.6.2 多模态 Embedding 生成（示意）

```python
"""
多模态内容 embedding 生成示意(PyTorch + 抽象接口)。
真实 TikTok 用自研多模态模型(文本/视觉/音频各一分支)后期融合。
"""
import torch
import torch.nn as nn


class MultimodalEncoder(nn.Module):
    """多模态编码: 文本(ASR) + 视觉(帧) + 音频 → 融合 embedding。"""

    def __init__(self, text_dim=512, frame_dim=2048, audio_dim=128,
                 fusion_dim=256):
        super().__init__()
        # 各模态自己的降维投影
        self.text_proj = nn.Linear(text_dim, fusion_dim)
        self.visual_proj = nn.Linear(frame_dim, fusion_dim)
        self.audio_proj = nn.Linear(audio_dim, fusion_dim)
        # 融合层
        self.attn = nn.MultiheadAttention(fusion_dim, num_heads=4)
        self.fusion = nn.Sequential(nn.Linear(fusion_dim, fusion_dim), nn.ReLU())

    def forward(self, text_vec, visual_vecs, audio_vec, n_frames=8):
        """
        text_vec: (B, text_dim)          ASR/OCR 文本向量
        visual_vecs: (B, n_frames, frame_dim)  抽帧向量
        audio_vec: (B, audio_dim)        音频向量
        """
        t = self.text_proj(text_vec)                 # (B, F)
        a = self.audio_proj(audio_vec)               # (B, F)
        v = self.visual_proj(visual_vecs)            # (B, nf, F)
        v = v.mean(dim=1)                            # 帧池化 → (B, F)
        # 简单融合(可换成 attention 加权)
        fused = t + a + v                            # (B, F)
        fused = self.fusion(fused)
        fused = nn.functional.normalize(fused, dim=-1)
        return fused
```

#### 2.6.3 去重与降质（内容治理）

- **去重（Dedup）**：同视频/近似视频（搬运、二创）只保留一条或合并，防止刷屏。
- **降质（Low-quality 过滤）**：低分辨率、模糊、无信息量、违规视频不进推荐。
- **同质化控制**：同一作者/同一风格/同一话题限频，保证多样性。

去重常见做法：视频指纹（感知哈希 / 帧特征）做近似去重。

```python
"""
基于感知哈希(PHash)的视频近似去重示意。
"""
import hashlib


def frame_phash(frame_gray_8x8):
    """64位感知哈希: 用 8x8 灰度均值量化, 生成 64-bit 指纹。"""
    bits = []
    mean = sum(frame_gray_8x8) / len(frame_gray_8x8)
    for g in frame_gray_8x8:
        bits.append(1 if g >= mean else 0)
    return int("".join(map(str, bits)), 2)


def hamming_distance(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


def dedup(video_hashes, threshold=12):
    """threshold 以内视为近似重复, 保留第一条。"""
    kept = []
    seen = []
    for h, vid in video_hashes:
        if any(hamming_distance(h, s) <= threshold for s in seen):
            continue  # 近似重复, 丢弃
        kept.append(vid)
        seen.append(h)
    return kept
```

---

### 2.7 特征工程（Feature Engineering）

特征 = 模型的"输入原料"。TikTok 双塔/精排模型的特征规模可达 **亿级稀疏**。

#### 2.7.1 特征分层

```
特征金字塔
┌──────────────────────────────────────┐
│ 用户特征 (User)                       │
│  user_id, 性别/年龄/地区/语言/设备     │
│  历史观看序列, 兴趣标签, 互动统计      │
├──────────────────────────────────────┤
│ 内容特征 (Item)                       │
│  video_id, 多模态embedding, 类目/标签  │
│  作者, 时长, 音乐, 字幕关键词, 热度     │
├──────────────────────────────────────┤
│ 上下文特征 (Context)                  │
│  时间(时段/星期), 网络, 位置, 场景      │
│  上一次滑到的时间/位置, 设备           │
├──────────────────────────────────────┤
│ 交叉特征 (Cross)                      │
│  用户类目 × 内容类目                    │
│  用户年龄 × 内容类型                    │
│  广告特征 × 用户特征 (广告专用)         │
└──────────────────────────────────────┘
```

#### 2.7.2 用户行为序列（Sequence）

用户最近的行为序列是极强特征（DIN 注意力）：

```
序列: <v1, v2, v3, ..., vT>   (用户最近看的视频 id / 类别)
用序列建模: 平均池化 / GRU / Transformer / DIN(注意力加权)
```

**DIN 注意力思路**：对候选内容做注意力，突出与候选相关的历史行为。

```python
"""
DIN (Deep Interest Network) 的注意力池化示意。
让候选向量去"挑选"用户历史里相关的部分。
"""
import torch
import torch.nn as nn


class DIN(nn.Module):
    def __init__(self, candidate_dim=64, hist_emb_dim=64):
        super().__init__()
        self.attn_fc = nn.Sequential(
            nn.Linear(candidate_dim * 2 + 1, 64),  # 候选cat + 历史cat + 差
            nn.ReLU(),
            nn.Linear(64, 1),
        )
        self.hist_proj = nn.Linear(hist_emb_dim, candidate_dim)

    def forward(self, candidate, hist_seq):
        # candidate: (B, d); hist_seq: (B, T, d)
        cand = candidate.unsqueeze(1).expand_as(hist_seq)   # (B,T,d)
        diff = candidate.unsqueeze(1) - hist_seq            # 差值
        feat = torch.cat([cand, hist_seq, diff], dim=-1)    # (B,T,2d+1)
        attn = torch.softmax(self.attn_fc(feat).squeeze(-1), dim=1)  # (B,T)
        out = (hist_seq * attn.unsqueeze(-1)).sum(dim=1)    # 加权求和
        return out
```

#### 2.7.3 时序特征与新鲜度

- **时间衰减**：越近的行为权重越高。
- **新鲜度**：新内容有探索加成（很多平台对新内容有"流量扶持期"）。
- **时段**：早/午/晚不同内容偏好不同。

```
时间衰减权重:
  w(t) = exp(-λ · (now - t))
用户历史行为按 w(t) 加权, 近的行为权重高。
```

#### 2.7.4 Embedding 如何用于特征

- **离散稀疏特征**：查表得到稠密向量（Embedding lookup）。
- **多模态稠密特征**：直接用内容理解产出的向量。
- 最终拼接成模型的输入 vector。

```python
# 一个典型精排特征构造示例
import numpy as np

def build_feature(user_embed, item_embed, context, cat_embed):
    """把 用户/内容/上下文/交叉 特征拼成一条训练样本。"""
    return {
        "dense": np.concatenate([
            user_embed, item_embed, context, cat_embed
        ]).astype("float32"),
        # 稀疏特征用 id + 查表, 这里示意
        "sparse": {
            "user_id": 10001,
            "item_id": 88231,
            "category": 23,
            "device": 2,
            "hour": 21,
        },
        "label": 1,  # 是否点击/完播
    }
```

---

### 2.8 评估指标（Metrics）

推荐模型离线与线上都要评估。以下是最常用的几组。

#### 2.8.1 排序类指标

**Precision@K（精度@K）**

```
Precision@K = (前 K 个推荐里命中的数量) / K
含义: 推荐了 K 个, 里面有多个是用户真正喜欢的。
```

**Recall@K（召回@K）**

```
Recall@K = (前 K 个推荐里命中的数量) / (用户真实喜欢的总数)
含义: 用户真正想要的, 你捞到几成。
```

**HitRate@K（命中率）**

```
HitRate@K = (至少命中 1 个的用户数) / (总用户数)
含义: 多少用户"至少被推荐中一次"。
```

**NDCG@K（归一化折损累积增益）**

```
DCG@K = Σ_{pos=1..K} rel_pos / log2(pos + 1)     # 位置越靠前权重越大
NDCG@K = DCG@K / IDCG@K                          # 除以理想排序的 DCG
含义: 命中的越靠前, 得分越高。推荐排序质量的核心指标。
```

**GAUC（Group AUC，用户组内 AUC）**

AUC 衡量排序随机把正样本排到负样本前面的概率。
GAUC 是 **按用户/组别平均的 AUC**，能减去用户偏差：

```
GAUC = (1/|U|) Σ_u AUC_u
AUC_u: 在用户 u 的行为样本里算 AUC
```

#### 2.8.2 Python 计算示例

```python
"""
排序评估指标: Precision@K / Recall@K / NDCG@K / HitRate@K 计算。
"""
import math


def hit_at_k(relevant, pred, k):
    pred_k = pred[:k]
    return 1 if any(item in relevant for item in pred_k) else 0


def precision_at_k(relevant, pred, k):
    pred_k = set(pred[:k])
    return len(pred_k & relevant) / k


def recall_at_k(relevant, pred, k):
    pred_k = set(pred[:k])
    return len(pred_k & relevant) / len(relevant) if relevant else 0.0


def dcg_at_k(relevant, pred, k):
    dcg = 0.0
    for pos, item in enumerate(pred[:k], start=1):
        if item in relevant:
            dcg += 1.0 / math.log2(pos + 1)
    return dcg


def ndcg_at_k(relevant, pred, k):
    dcg = dcg_at_k(relevant, pred, k)
    # 理想排序: 命中的都排最前
    ideal = [1.0] * min(k, len(relevant))
    idcg = sum(1.0 / math.log2(pos + 1) for pos in range(1, len(ideal) + 1))
    return dcg / idcg if idcg > 0 else 0.0


def evaluate_all(relevant, pred, k=10):
    return {
        "hit@k": hit_at_k(relevant, pred, k),
        "precision@k": precision_at_k(relevant, pred, k),
        "recall@k": recall_at_k(relevant, pred, k),
        "ndcg@k": ndcg_at_k(relevant, pred, k),
    }


if __name__ == "__main__":
    relevant = {3, 7}
    pred = [3, 1, 2, 7, 5]
    print(evaluate_all(relevant, pred, k=5))
```

#### 2.8.3 线上 A/B 测试

离线指标好 ≠ 线上收益好。必须 A/B 验证：

```
线上 A/B 测试流程

随机分桶 (实验组/对照组, 保证同质)
   │
   ▼
对照组: 线上老模型;  实验组: 新模型
   │
   ▼
观察核心业务指标(CTR/完播/时长/收入) 与 护栏(多样性/负反馈)
   │
   ▼
统计显著性(如 p<0.05) + 效果量 > 阈值 → 全量上线
```

**A/B 设计要点**
- **同质分桶**：按 user_id hash 分层，保证用户行为可比的实验/对照。
- **隔离实验**：同一用户在实验期间不能被多个实验同时影响（避免污染）。
- **样本量**：效应越小需要样本越大，用功效分析预估。
- **护栏指标**：防止指标提升但体验变差（如只推爆款提升点击但用户流失）。

---

### 2.9 广告与推荐联动（Ad-Recommendation 联动）

#### 2.9.1 广告混排的收益模型

精排里广告的最终得分融合了 **用户体验 + 商业化收益**：

```
最终价值 V(ad) 与有机内容的比较逻辑:

有机内容得分:    engage(model)         # 完播/点赞/关注
广告内容得分:    a·engage(ad) + b·revenue(ad)

其中 revenue(ad) 与广告主出价 bid、预估转化率 eCVR 相关:
   revenue(ad) ≈ bid × P(convert | user, ad) × (展示后转化概率)

平台的权衡: 广告边际收入 vs 用户体验下降(负反馈) 的平衡点。
```

#### 2.9.2 广告负向信号

- 用户对广告"隐藏"、"举报"、秒刷（快速上滑）= **负向信号**。
- 负向信号进精排目标，惩罚该广告对该用户的投放。
- 广告主能改进：素材质量、定向精准度、避免"标题党"。

#### 2.9.3 跑量 holdout 与进化

- 新广告新算法会先做 **holdout（小流量灰度）**，验证收益后再全量。
- 广告系统的模型（CVR 预估、出价控制）也在持续迭代，
  通过 **预算/出价/频控** 多层控制把成本锁在广告主可接受区间。
- "跑量"的本质：让算法在当前预算约束下 **花完预算且尽量 CPA 低**。

> 广告主视角：**跑量靠的是"给足线索+合理出价+过冷启动"**，
> 不是靠"不停建新广告"。
> 兜底逻辑见 `tiktok-ads-optimization-deep.md` / `tiktok-ads-troubleshooting-deep.md`。

---

> 第二部分小结：掌握
> ① CF（userCF/itemCF + 余弦/皮尔逊）
> ② MF（SVD/ALS）
> ③ 双塔 + ANN（HNSW/IVF）
> ④ 多路召回 + EE
> ⑤ 三类冷启动 + 广告学习期
> ⑥ 多模态内容理解
> ⑦ 特征工程（序列/时序/embedding/交叉）
> ⑧ 评估指标（P/R/NDCG/HitRate/GAUC + A/B）
> ⑨ 广告联动（收益模型/负向信号/holdout）
>
> 下一部分进入生产环境实战：用真实业务场景 + TikTok Marketing API 落地这些理论。

---

## 三、生产环境实战

> 本章把第二部分的算法原理,翻译成广告投放的真实业务动作。
> 每个场景都给出: 业务背景 → 量化目标 → 操作步骤 → 可运行代码 → 效果校验。
> 所有代码均使用 `scripts/tiktok_api.py` 中的真实方法名
> （`TikTokClient` 封装了 `business-api.tiktok.com/open_api/v1.3`）。

### 3.1 场景一：美妆品牌 TikTok 冷启动定向实操（品牌）

#### 3.1.1 业务背景

某美妆品牌（客单价 ¥220，毛利率 60%），
目标市场：东南亚（印尼/泰国/越南），
投放目标：新客拉新 + 加购，要求 ROAS ≥ 2.5。

问题：品牌新开户、无历史转化数据，新广告组 100% 冷启动。

#### 3.1.2 量化基线（行业参考）

| 指标 | 行业参考值 | 本案例目标 |
|------|-----------|-----------|
| CTR（视频素材） | 1.0% ~ 2.5% | ≥ 1.8% |
| CVR（落地页） | 1.5% ~ 4% | ≥ 2.5% |
| eCPM | $8 ~ $25 | ≤ $18 |
| CPA | 取决于客单 | ≤ ¥88 |
| 冷启动时长 | 24 ~ 72h | ≤ 48h 出学习期 |
| 冷启动转化积累 | 50 个优化事件 | 7 天达 50 转化 |

#### 3.1.3 操作步骤（5 步过冷启动）

```
第1步: 打通转化回传 (Pixel/CAPI) —— 没转化信号, 算法学不到东西
第2步: 建受众: 兴趣人群 + 相似受众(Lookalike) —— 缩小探索空间
第3步: 建转化广告系列: 自动出价 + 日预算≥建议值 —— 保证学习流量
第4步: 素材测试: 3-5 条素材 × 1 受众组 —— 纯净归因, 找到素材王
第5步: 48h 后看结果: 出学习期 → 加预算提量; 未出 → 换素材重来
```

#### 3.1.4 代码实现（Python，真实 API 方法）

```python
"""
美妆品牌冷启动: 创建受众 → 转化系列 → 广告组 → 素材 → 广告 → 报表校验
"""
from tiktok_api import TikTokClient

client = TikTokClient({"access_token": "YOUR_ACCESS_TOKEN"})
ADVERTISER_ID = "YOUR_ADVERTISER_ID"

# ---- 1. 先看账户与已有受众 (避免重复建) ----
accounts = client.list_accounts(ADVERTISER_ID)
print("accounts:", accounts)

audiences = client.list_audiences(ADVERTISER_ID)
print("existing audiences:", len(audiences.data or []))

# ---- 2. 创建"加购人群"自定义受众 (用 Pixel 事件回溯) ----
resp_aud = client.create_audience(
    advertiser_id=ADVERTISER_ID,
    audience={
        "name": "beauty_add_to_cart_30d",
        "audience_type": "CUSTOM_AUDIENCE",
        "rule": {
            "event_sources": ["PIXEL_ID"],
            "retention_days": 30,
            "rules": [
                {"event_type": "AddToCart", "filters": [{"field": "event", "value": "AddToCart"}]}
            ],
        },
    },
)
audience_id = resp_aud.data.get("audience_id")
print("created audience:", audience_id)

# ---- 3. 创建转化目标广告系列 (SALES) ----
resp_campaign = client.create_campaign(
    advertiser_id=ADVERTISER_ID,
    campaign={
        "objective_type": "PRODUCT_SALES",   # 电商走 PRODUCT_SALES
        "name": "beauty_cold_start_0814",
        "budget": 100.0,
        "budget_mode": "BUDGET_MODE_DAY",
        "bid_strategy": "LOWEST_COST",
    },
)
campaign_id = resp_campaign.data.get("campaign_id")

# ---- 4. 创建广告组: 自动出价 + 相似受众 + 宽定向 ----
resp_adgroup = client.create_adgroup(
    advertiser_id=ADVERTISER_ID,
    adgroup={
        "campaign_id": campaign_id,
        "name": "adg_lookalike_t1",
        "budget": 100.0,
        "budget_mode": "BUDGET_MODE_DAY",
        "bid_type": "AUTO_BID_TYPE_VALUE_MAXIMIZE_CONVERSIONS",
        "optimization_goal": "COMPLETE_PAYMENT",
        "placement_type_list": ["PLACEMENT_TYPE_TIKTOK"],
        "targeting": {
            "audience_ids": [audience_id],       # 相似/自定义受众
            "age": ["18", "24", "25", "34"],
            "gender": ["FEMALE"],
            "locations": [{"country": "ID"}, {"country": "TH"}],
        },
    },
)
adgroup_id = resp_adgroup.data.get("adgroup_id")

# ---- 5. 上传素材并建广告 ----
media = client.get_media_library(ADVERTISER_ID)
print("media library items:", len(media.data or []))

ad_resp = client.create_ad(
    advertiser_id=ADVERTISER_ID,
    ad={
        "adgroup_id": adgroup_id,
        "name": "ad_beauty_v1_lipstick",
        "creatives": [
            {
                "video_id": "VIDEO_ID_FROM_MEDIA_LIBRARY",
                "identity_id": "BRAND_IDENTITY_ID",
                "display_name": "BeautyBrand",
                "call_to_action": "SHOP_NOW",
            }
        ],
    },
)
ad_id = ad_resp.data.get("ad_id")
print("created ad:", ad_id)

# ---- 6. 48h 后拉报表校验: CTR / CVR / CPA / ROAS ----
report = client.get_report(
    advertiser_id=ADVERTISER_ID,
    date_start="2026-08-01",
    date_end="2026-08-14",
    level="AD",
    insights=["spend", "impressions", "clicks", "conversions", "ctr",
              "cvr", "cpa", "total_complete_payment_rate"],
)
for row in (report.data or [])[:10]:
    print(row)
```

#### 3.1.5 决策规则（可写成脚本自动跑）

```python
def evaluate_cold_start(report_rows, cpa_target=88.0, ctr_target=0.018):
    """冷启动结果评估: 出/不出学习期, 加量/换素材。"""
    decisions = []
    for row in report_rows:
        cpa = row.get("cpa") or float("inf")
        ctr = row.get("ctr") or 0.0
        conv = row.get("conversions") or 0
        if conv >= 50 and cpa <= cpa_target:
            decisions.append(("SCALE_UP", row.get("ad_id"), cpa))   # 加预算
        elif ctr >= ctr_target and cpa > cpa_target * 1.3:
            decisions.append(("NEW_MATERIAL", row.get("ad_id"), cpa))  # 换素材
        elif ctr < ctr_target:
            decisions.append(("KILL", row.get("ad_id"), cpa))          # 停投
        else:
            decisions.append(("WAIT", row.get("ad_id"), cpa))          # 继续学
    return decisions
```

---

### 3.2 场景二：休闲游戏 APP 拉新（APP 增长）

#### 3.2.1 业务背景

某休闲游戏（LTV 30 天 ≈ $1.2），
目标：iOS/Android 双端安装，考核 CPA ≤ $0.45，次留 ≥ 25%。

冷启动难点：游戏目标人群是"泛用户"，宽定向效果好但转化信号稀疏。

#### 3.2.2 量化基线

| 指标 | 基线 | 达标线 |
|------|------|--------|
| 安装 CPA | ≤ $0.6 | ≤ $0.45 |
| 次留率 D1 | ≥ 22% | ≥ 25% |
| CVR(安装/点击) | 1% ~ 3% | ≥ 1.8% |
| 冷启动转化 | 50 安装 | 3 天达标 |
| 素材完播率 | 30%+ | 40%+ |

#### 3.2.3 代码实现（APP_INSTALL 目标）

```python
"""
休闲游戏拉新: APP_PROMOTION 目标 + 自动出价 + 按安装优化。
"""
from tiktok_api import TikTokClient

client = TikTokClient({"access_token": "YOUR_ACCESS_TOKEN"})
ADVERTISER_ID = "YOUR_ADVERTISER_ID"

# 目标枚举确认
options = client.get_campaign_objective_options()
print([o.get("objective_type") for o in options])
# 预期包含: APP_INSTALL / APP_RETARGETING / ...

# 创建 APP 安装系列
camp = client.create_campaign(
    advertiser_id=ADVERTISER_ID,
    campaign={
        "objective_type": "APP_INSTALL",
        "name": "game_install_ios_0814",
        "budget": 300.0,
        "budget_mode": "BUDGET_MODE_DAY",
    },
)
campaign_id = camp.data.get("campaign_id")

# 广告组: APP 安装 + 自动出价
ag = client.create_adgroup(
    advertiser_id=ADVERTISER_ID,
    adgroup={
        "campaign_id": campaign_id,
        "name": "adg_game_install",
        "budget": 300.0,
        "budget_mode": "BUDGET_MODE_DAY",
        "bid_type": "AUTO_BID_TYPE_VALUE_MAXIMIZE_CONVERSIONS",
        "optimization_goal": "APP_INSTALL",
        "objective_type": "APP_INSTALL",
        "app_id": "IOS_APP_ID",
        "placement_type_list": ["PLACEMENT_TYPE_TIKTOK",
                                "PLACEMENT_TYPE_GLOBAL_APP_SITE_ANDROID"],
        "targeting": {
            "age": ["18", "24", "25", "34", "35", "44"],
            "gender": ["MALE", "FEMALE"],
            "languages": [{"id": "en"}, {"id": "id"}],
        },
    },
)
adgroup_id = ag.data.get("adgroup_id")

# 建 3 条素材测试
for i, video_id in enumerate(["VIDEO_A", "VIDEO_B", "VIDEO_C"]):
    client.create_ad(
        advertiser_id=ADVERTISER_ID,
        ad={
            "adgroup_id": adgroup_id,
            "name": f"ad_game_{i}_hook",
            "creatives": [{
                "video_id": video_id,
                "identity_id": "APP_IDENTITY_ID",
                "display_name": "FunGame",
                "call_to_action": "INSTALL_NOW",
            }],
        },
    )

# 72h 后拉安装报表
report = client.get_report(
    advertiser_id=ADVERTISER_ID,
    date_start="2026-08-11",
    date_end="2026-08-14",
    level="ADGROUP",
    insights=["spend", "impressions", "clicks", "conversions",
              "cpa", "ctr", "cvr", "cost_per_install"],
)
for row in (report.data or [])[:10]:
    print(row)
```

#### 3.2.4 素材王筛选（结果驱动）

```
规则:
1. 安装 CPA ≤ $0.45 且 转化 ≥ 50 → 保留并加预算 30%~50%
2. CPA $0.45~0.6 且完播高 → 保留观察 24h, 不出学习期则砍
3. CPA > $0.6 → 直接停
4. 每小时拉一次报表, 用 get_report 做监控看板
```

---

### 3.3 场景三：电商大促（代理商的预算分配）

#### 3.3.1 业务背景

代理商管理 5 个电商客户（客单价 $30~$120），
大促期间预算 $50,000/天，
考核：整体 ROAS ≥ 3.0，同时各客户 CPA 不爆。

核心矛盾：**预算有限，如何把预算分给"算法跑得好"的广告？**

#### 3.3.2 预算分配的"算法视角"

预算分配本质是 **优化问题**：

```
最大化 Σ_c 广告系列收益 (revenue)
约束:
  Σ_c budget_c ≤ 总预算
  budget_c ≥ 客户最低预算(冷启动需要)
  budget_c ≤ 客户上限(风险控制)

经验法则: 边际 ROAS 递减 —— 越加预算, 增量 ROAS 越低
分配策略: 把预算从 边际ROAS 低的广告 挪向 边际ROAS 高的广告
```

#### 3.3.3 代码实现（Go：预算再分配 + 停投巡检）

```go
// budget-allocator.go
// 代理商预算分配巡检: 读报表 → 计算边际ROAS → 输出调整指令
package main

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"sort"
	"strconv"
	"time"
)

const (
	apiBase  = "business-api.tiktok.com/open_api/v1.3"
	tokenEnv = "TIKTOK_ACCESS_TOKEN"
	totalCap = 50000.0 // 每日总预算上限 $
	roasGoal = 3.0     // 目标整体 ROAS
)

type ReportRow struct {
	AdvertiserID string  `json:"advertiser_id"`
	CampaignID   string  `json:"campaign_id"`
	Spend        float64 `json:"spend"`
	Revenue      float64 `json:"total_complete_payment_rate_micro"` // 示意字段
	Conversions  float64 `json:"conversions"`
	CostPerConv  float64 `json:"cost_per_conversion"`
}

// fetchReport 调用 /report/get/ (与 get_report 同语义的 HTTP 实现)
func fetchReport(advertiserID, dateStart, dateEnd string) ([]ReportRow, error) {
	token := os.Getenv(tokenEnv)
	url := fmt.Sprintf("https://%s/report/get/?advertiser_id=%s&date_start=%s&date_end=%s&level=CAMPAIGN&service_type=AUCTION",
		apiBase, advertiserID, dateStart, dateEnd)
	req, _ := http.NewRequest("GET", url, nil)
	req.Header.Set("Access-Token", token)
	req.Header.Set("Content-Type", "application/json")
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	var payload struct {
		Data struct {
			List []ReportRow `json:"list"`
		} `json:"data"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&payload); err != nil {
		return nil, err
	}
	return payload.Data.List, nil
}

// marginalROAS: 用近 7 天数据粗估边际 ROAS (分段斜率)
func marginalROAS(rows []ReportRow) map[string]float64 {
	// 简化: 用 ROAS 近似边际, 生产环境用增量实验/分桶归因
	out := make(map[string]float64)
	for _, r := range rows {
		if r.Spend > 0 {
			out[r.CampaignID] = r.Revenue / r.Spend
		}
	}
	return out
}

func main() {
	advertisers := []string{"CLIENT_1", "CLIENT_2", "CLIENT_3", "CLIENT_4", "CLIENT_5"}
	now := time.Now()
	dateStart := now.AddDate(0, 0, -7).Format("2006-01-02")
	dateEnd := now.Format("2006-01-02")

	type alloc struct {
		CampaignID string
		ROAS       float64
		Spend      float64
	}
	var all []alloc
	for _, adv := range advertisers {
		rows, err := fetchReport(adv, dateStart, dateEnd)
		if err != nil {
			log.Printf("report failed for %s: %v", adv, err)
			continue
		}
		mr := marginalROAS(rows)
		for _, r := range rows {
			if roas, ok := mr[r.CampaignID]; ok {
				all = append(all, alloc{r.CampaignID, roas, r.Spend})
			}
		}
	}
	// 按 ROAS 降序
	sort.Slice(all, func(i, j int) bool { return all[i].ROAS > all[j].ROAS })

	// 贪心分配: 优先给高 ROAS 广告, 直到预算耗尽
	remaining := totalCap
	fmt.Println("=== 预算分配方案 (每日) ===")
	for _, a := range all {
		if remaining <= 0 {
			break
		}
		next := a.Spend * 0.8 // 按当前消耗的 80% 作为增量配额
		if next > remaining {
			next = remaining
		}
		remaining -= next
		fmt.Printf("campaign=%s roas=%.2f budget_delta=$%.0f\n",
			a.CampaignID, a.ROAS, next)
	}
	fmt.Println("=== 停投建议 ===")
	for _, a := range all {
		if a.ROAS < 1.5 { // 低于 1.5 的广告直接停
			fmt.Printf("PAUSE campaign=%s roas=%.2f spend=$%.0f\n",
				a.CampaignID, a.ROAS, a.Spend)
		}
	}
	_ = strconv.Itoa // 保留 import, 生产代码里用于格式化金额
}
```

#### 3.3.4 代理商巡检最佳实践

| 动作 | 频率 | 工具 |
|------|------|------|
| 拉全账户报表 | 每小时 | `get_report` |
| 停投 ROAS<1.5 广告 | 每 2h | `pause_campaign` / `pause_adgroup` |
| 预算再分配 | 每日 2 次 | 上表 Go 脚本 |
| 异常 CPA 告警 | 实时 | 阈值规则 + 告警 |
| 冷启动广告保护 | 24h 内不动 | 人工确认 |

---

### 3.4 场景四：品牌形象 + 直播带货双线打法（直播电商）

#### 3.4.1 业务背景

某服装品牌同时做：
- 品牌线：品宣视频（考核完播率 + 互动率，CPM 控制）。
- 直播线：直播间引流（考核 GPM = GMV/千次观看，ROAS ≥ 2.2）。

#### 3.4.2 两条线的算法差异

| 维度 | 品牌线（品宣） | 直播线（带货） |
|------|--------------|---------------|
| 优化目标 | VIDEO_VIEWS / ENGAGEMENT | LIVE 转化 / COMPLETE_PAYMENT |
| 出价 | 低预算, 控 CPM | 自动出价, 冲 GMV |
| 素材 | 品牌故事, 高完播 | 直播切片, 强 CTA |
| 关键指标 | 完播率 / 互动率 | GPM / ROAS / 在线人数峰值 |
| 冷启动 | 快(互动信号多) | 慢(转化信号少) |

#### 3.4.3 代码实现（直播引流 + 关键词 + 转化事件）

```python
"""
直播电商: LIVE 目标广告组 + 关键词 + 自定义转化事件。
"""
from tiktok_api import TikTokClient

client = TikTokClient({"access_token": "YOUR_ACCESS_TOKEN"})
ADVERTISER_ID = "YOUR_ADVERTISER_ID"

# 1. 直播系列 (STORE_TRAFFIC / LIVE 场景)
camp = client.create_campaign(
    advertiser_id=ADVERTISER_ID,
    campaign={
        "objective_type": "STORE_TRAFFIC",
        "name": "live_fashion_0814",
        "budget": 800.0,
        "budget_mode": "BUDGET_MODE_DAY",
    },
)
campaign_id = camp.data.get("campaign_id")

# 2. 直播广告组: 优化直播观看/进入直播间
ag = client.create_adgroup(
    advertiser_id=ADVERTISER_ID,
    adgroup={
        "campaign_id": campaign_id,
        "name": "adg_live_entrance",
        "budget": 800.0,
        "budget_mode": "BUDGET_MODE_DAY",
        "bid_type": "AUTO_BID_TYPE_VALUE_MAXIMIZE_CONVERSIONS",
        "optimization_goal": "LIVE_VIEW",   # 直播观看目标
        "objective_type": "STORE_TRAFFIC",
        "live_enter_setting": {"is_live_enter": True},
        "placement_type_list": ["PLACEMENT_TYPE_TIKTOK",
                                "PLACEMENT_TYPE_PANDA"],
        "targeting": {
            "age": ["18", "24", "25", "34"],
            "gender": ["FEMALE"],
            "interest_keywords": ["fashion", "dress", "ootd"],
        },
    },
)
adgroup_id = ag.data.get("adgroup_id")

# 3. 给广告组挂关键词 (扩大相关召回)
kw = client.create_keywords(
    advertiser_id=ADVERTISER_ID,
    adgroup_id=adgroup_id,
    keywords=[
        {"keyword": "summer dress", "match_type": "BROAD"},
        {"keyword": "outfit", "match_type": "PHRASE"},
    ],
)
print("keywords:", kw)

# 4. 建"直播间支付"自定义转化事件 (如果 Pixel 没有该事件)
conv = client.create_custom_conversion(
    advertiser_id=ADVERTISER_ID,
    conversion={
        "name": "live_purchase",
        "event_source": "PIXEL",
        "pixel_id": "PIXEL_ID",
        "event_type": "PURCHASE",
    },
)
print("custom conversion:", conv)

# 5. 建直播广告素材 (直播间封面/切片)
ad = client.create_ad(
    advertiser_id=ADVERTISER_ID,
    ad={
        "adgroup_id": adgroup_id,
        "name": "ad_live_slice_v1",
        "creatives": [{
            "video_id": "LIVE_SLICE_VIDEO",
            "identity_id": "BRAND_IDENTITY_ID",
            "display_name": "FashionBrand",
            "call_to_action": "SHOP_NOW",
            "live_video_id": "LIVE_VIDEO_ID",
        }],
    },
)
print("live ad:", ad.data)

# 6. 直播结束拉 GPM 报表
report = client.get_report(
    advertiser_id=ADVERTISER_ID,
    date_start="2026-08-14",
    date_end="2026-08-14",
    level="AD",
    insights=["spend", "impressions", "clicks", "conversions",
              "gross_merchandise_value", "roas", "gpm"],
)
for row in (report.data or [])[:5]:
    print(row)
```

#### 3.4.4 直播 GPM 诊断

```
GPM = GMV / (impressions / 1000)

低 GPM 排查链:
① 素材进直播间率低 → 素材问题 (换直播切片/口播)
② 进直播间但不买 → 直播间承接问题 (话术/价格/库存)
③ 买了但客单低 → 选品/定价问题
④ 在线人数峰值短 → 开播时段/预告问题
分别对应: 换素材 / 调直播 / 换品 / 改时段, 不是算法问题
```

---

### 3.5 场景五：广告与有机协同（品牌自播 + Spark Ads）

#### 3.5.1 业务背景

品牌发现：**自然流量与付费流量互相影响**。
Spark Ads（用达人原声内容投流）因"原生感"常获得更高 CTR，
且达人内容本身就是有机生态的一部分。

#### 3.5.2 协同逻辑

```
有机内容(达人视频) 火爆 → 信号进入算法 → 算法认为该内容/该品类有热度
  → Spark Ads 投相似内容 → 更快过冷启动, CTR 更高
  → 付费流量反哺达人账号权重 → 更多自然曝光
  → 正向飞轮
```

**量化数据（行业经验）**：

| 指标 | 普通广告 | Spark Ads |
|------|---------|-----------|
| CTR 提升 | 基线 | +15% ~ +40% |
| CPM 降低 | 基线 | -10% ~ -25% |
| 完播率 | 基线 | +20% 左右 |
| 冷启动时长 | 24~72h | 可缩短 30% |

#### 3.5.3 代码实现（Spark Ads 授权查询 + 投放）

```python
"""
Spark Ads: 查询可用达人内容 → 创建 Spark 广告。
"""
from tiktok_api import TikTokClient

client = TikTokClient({"access_token": "YOUR_ACCESS_TOKEN"})
ADVERTISER_ID = "YOUR_ADVERTISER_ID"

# 1. 媒体库看可用的达人视频 (需达人授权)
media = client.get_media_library(ADVERTISER_ID)
for item in (media.data or [])[:5]:
    print("media item:", item.get("id"), item.get("video_title"))

# 2. 创建 Spark 广告组
camp = client.create_campaign(
    advertiser_id=ADVERTISER_ID,
    campaign={"objective_type": "CONVERSIONS",
              "name": "spark_fashion_0814",
              "budget": 200.0, "budget_mode": "BUDGET_MODE_DAY"},
)
campaign_id = camp.data.get("campaign_id")

ag = client.create_adgroup(
    advertiser_id=ADVERTISER_ID,
    adgroup={
        "campaign_id": campaign_id,
        "name": "adg_spark_t1",
        "budget": 200.0,
        "budget_mode": "BUDGET_MODE_DAY",
        "bid_type": "AUTO_BID_TYPE_VALUE_MAXIMIZE_CONVERSIONS",
        "optimization_goal": "COMPLETE_PAYMENT",
        "objective_type": "CONVERSIONS",
        "placement_type_list": ["PLACEMENT_TYPE_TIKKTOK"],
        "targeting": {"age": ["18", "24", "25", "34", "35", "44"]},
    },
)
adgroup_id = ag.data.get("adgroup_id")

# 3. 建 Spark Ad (引用达人视频 + 达人身份)
spark = client.create_ad(
    advertiser_id=ADVERTISER_ID,
    ad={
        "adgroup_id": adgroup_id,
        "name": "ad_spark_v1",
        "creatives": [{
            "spark_ads_video_id": "CREATOR_VIDEO_ID",
            "identity_id": "CREATOR_IDENTITY_ID",   # 达人授权身份
            "display_name": "CreatorName",
            "call_to_action": "SHOP_NOW",
        }],
    },
)
print("spark ad:", spark.data)

# 4. 与普通广告对比 CTR
report = client.get_report(
    advertiser_id=ADVERTISER_ID,
    date_start="2026-08-14", date_end="2026-08-14",
    level="AD", insights=["spend", "impressions", "clicks", "ctr", "cpm"],
)
for row in (report.data or [])[:10]:
    print(row)
```

---

### 3.6 通用实战清单：把算法知识变成投放动作

| 算法概念 | 广告侧动作 | 工具/API |
|---------|-----------|---------|
| 冷启动/学习期 | 自动出价 + 日预算≥50×目标CPA + 少动广告 | `create_adgroup` + `AUTO_BID_TYPE_VALUE_MAXIMIZE_CONVERSIONS` |
| 探索与利用 | 素材测试 3-5 条/组, 用预算做探索护栏 | `create_ad` + 分素材报表 |
| 内容理解 | 用高完播素材, 让算法学得更准 | `get_media_library` 对比素材 |
| 特征/受众 | 相似受众 + 兴趣定向缩小探索空间 | `create_audience` |
| 转化目标 | 回传真实转化, 让 CVR 模型学得准 | Pixel / `create_custom_conversion` |
| 负向信号 | 避免标题党/虚假承诺, 降低负反馈 | 素材质量 |
| 频控/预算 | 预算上限防花超, 频控防疲劳 | `update_campaign` 预算 |
| 评估 | CTR/CVR/CPA/ROAS 全维度看, 不看单一指标 | `get_report` |
| 跑量 | 出学习期后每次加预算 ≤20~30%, 防成本跳变 | `update_campaign` / `update_adgroup` |

> 最终心法：**算法给你的是"概率"，你用"预算、出价、素材、转化信号"去喂养这个概率。**
> 不要跟算法对抗（比如频繁暂停重启），要顺着学习机制给足稳定的训练信号。


---

---

### 3.7 广告生命周期管理与素材上传（API 全量操作）

> 前面场景覆盖了"创建 + 报表 + 关键词 + 受众 + 转化事件"，
> 本小节补齐 **查询 / 暂停 / 恢复 / 删除 / 素材上传 / 定向与出价选项** 的完整生命周期，
> 覆盖 `TikTokClient` 其余方法，形成一套可运维的工具链。

```python
"""
广告账号全生命周期运维脚本: 查 → 传素材 → 查询/暂停/恢复 → 清理。
"""
from tiktok_api import TikTokClient

client = TikTokClient({"access_token": "YOUR_ACCESS_TOKEN"})
ADVERTISER_ID = "YOUR_ADVERTISER_ID"

# ---- 1. 查询: 商务部/系列/广告组/广告 四层 ----
accounts = client.list_accounts(ADVERTISER_ID)
# 确认 objective / 定向 / 出价枚举再往下建, 避免参数错误
obj_opts = client.get_campaign_objective_options()
print("supported objectives:", [o.get("objective_type") for o in obj_opts])
bid_opts = client.get_bid_strategy_options()
print("supported bid types:", [b.get("bid_type") for b in bid_opts])
placements = client.get_placement_options()
print("placements:", placements)          # Feed/Search/Post/Marketplace/Series/Live...

camps = client.list_campaigns(ADVERTISER_ID)
campaign_id = camps.data[0]["campaign_id"]
camp = client.get_campaign(ADVERTISER_ID, campaign_id)
print("campaign detail:", camp.data.get("name"))

adgroups = client.list_adgroups(ADVERTISER_ID, campaign_id)
adgroup_id = adgroups.data[0]["adgroup_id"]
ads = client.list_ads(ADVERTISER_ID, adgroup_id)
print("ads under adgroup:", [a.get("id") for a in (ads.data or [])])

# ---- 2. 素材上传: 图片 ----
media = client.get_media_library(ADVERTISER_ID)
uploaded = client.upload_image(
    advertiser_id=ADVERTISER_ID,
    image_data={"image_file": "path/to/banner.png",
                "image_name": "banner_0814"},
)
image_id = uploaded.data.get("image_id")
print("uploaded image:", image_id)

# ---- 3. 生命周期: 暂停 / 恢复 / 删除 (三层各自有对应方法) ----
client.pause_adgroup(ADVERTISER_ID, adgroup_id)      # 临时控量
client.resume_adgroup(ADVERTISER_ID, adgroup_id)     # 恢复
client.pause_campaign(ADVERTISER_ID, campaign_id)    # 大促结束整体停
client.resume_campaign(ADVERTISER_ID, campaign_id)   # 再开
client.pause_ad(ADVERTISER_ID, adgroup_id,
                [a["id"] for a in (ads.data or [])]) # 停素材王以外的素材

# 彻底清理测试用资产 (生产慎用, 先确认无误)
# client.delete_keywords(ADVERTISER_ID, ["KEYWORD_ID"])
# client.delete_audience(ADVERTISER_ID, "AUDIENCE_ID")
# client.delete_adgroup(ADVERTISER_ID, adgroup_id)
# client.delete_ad(ADVERTISER_ID, adgroup_id, ["AD_ID"])
# client.delete_campaign(ADVERTISER_ID, campaign_id)

# ---- 4. 转化事件清单 ----
events = client.list_conversion_events(ADVERTISER_ID)
print("conversion events:", [e.get("event_type") for e in (events.data or [])])

# ---- 5. 关键词查询 ----
kws = client.list_keywords(ADVERTISER_ID, adgroup_id)
print("keywords on adgroup:", len(kws.data or []))
```

> **运维提醒**：`pause_*` / `resume_*` / `delete_*` 是三类不同的语义，
> 暂停可用于"控量/止损"，恢复用于"再启动"，删除才是彻底移除。
> 频繁暂停-恢复会引发广告重启学习（见 Q12），自动化脚本务必加最小间隔保护。

## 四、常见问题与排查

> 以下 12 个问题按"算法 → 广告"两条线汇总，
> 对应优化师 / 工程师最容易踩的坑，每个都给了排查路径与结论。

### Q1：新广告组一直没有转化，怎么判断"还差一步"还是"彻底没戏"？

**排查路径**
1. 看是否还有展示/播放（impressions > 0）？
   - 没有展示 → 定向过窄或预算过低或素材不过审。
   - 有点击没转化 → 落地页/CVR 问题，不是算法问题。
   - 有转化但少 → 处于冷启动，需要时间与预算。
2. 看学习进度：是否已积累 **50 个优化事件**？
   - 未满 50 → 还没退出学习期，继续观察，别急着改。
   - 满 50 仍无效果 → 换素材或换定向。
3. 看 CPA 与目标：CPA 是目标 2 倍以上且持续 72h → 停投重建。

**结论**：先分"展示→点击→转化"三漏斗定位，再决定去留。别一上来就删。

### Q2：为什么我同时建 20 个广告组，只有 2 个在跑量？

**原理**：系统把预算集中投给"当前表现最好"的广告（赢者通吃机制）。
20 个广告组会抢同一个目标人群，互相挤占预算。

**最佳实践**
- 同一人群/素材用 1~2 个广告组足够，别自我消耗。
- 想测素材，用 **同一广告组里多个广告** 或 **分素材测试**，而不是堆广告组。
- 有预算能力再用不同受众/不同地区做横向扩展。

### Q3：为什么改了一次出价，广告就中断/成本跳变？

**原理**：修改预算/出价/优化目标会让广告 **重新进入学习期**（模型部分重置）。
频繁改动 → 模型永远学不稳 → 成本忽高忽低。

**最佳实践**
- 冷启动期（未出学习期）**不要动** 预算/出价/素材/定向。
- 加预算 **每次不超过 20%~30%**，且加完观察几小时。
- 必须改时，选低峰期改，避免与系统学习冲突。

### Q4：为什么 CTR 高但转化（CVR）极低？

**排查**
- CTR 高 = 素材吸睛；CVR 低 = 点进来不转化。
- 常见原因：落地页加载慢 / 价格与素材不符 / 购买流程复杂 / 受众是"看热闹"的泛流量。

**结论**：CTR 与 CVR 是两个漏斗，分别优化。
- CTR 问题 → 换素材、换开头 hook。
- CVR 问题 → 优化落地页、降低期望、加优惠券、明确 CTA。

### Q5：ROAS 低，一定是算法问题吗？

**不一定是**。ROAS = revenue / spend，高收入依赖：
- 受众精准（算法管）→ 出价合理（广告主管）→ 转化率高（落地页管）→ 客单价与复购（产品管）。

**排查优先级**：先看 CPA 是否合理 → 再看客单价/复购 → 再看受众。
若 CPA 正常但客单低，是选品/返点问题，不是算法问题。

### Q6：为什么"相似受众（Lookalike）"有时冷启动很慢？

**原理**：Lookalike 基于种子人群学相似特征，但也可能把人群推得太"泛"，导致转化信号稀疏。

**排查**
- 种子人群太小（< 几百人）→ Lookalike 学不出稳定模式。
- Lookalike 比例设太大（如 5%）→ 人群过泛。
- 种子本身质量差（非核心买家）→ 学偏。

**最佳实践**：种子用"高价值用户"（已购买/高 LTV），比例从 1%~3% 起，与宽定向做对比。

### Q7：为什么同一个广告，iOS 和 Android 表现差很多？

**正常**。iOS 因 ATT 隐私限制，转化回传数据少（SKAdNetwork 延迟），
CVR 模型学习更弱，成本往往更高、归因更滞后。

**排查**
- iOS 用 Conversion API/聚合测量补数据，启用 SKAN 4。
- 分端观察，别用一个节奏管两端。
- iOS 冷启动通常需要更多耐心与预算。

### Q8：多模态内容理解到底对投放有什么用？（非技术人员问）

**一句话**：内容理解让系统"看懂"你的广告，从而精准打分与召回。

- 广告素材会被转成向量 + 标签（口播关键词、画面、音乐、品类）。
- 系统能把你的广告推给"之前看过类似内容的人"。
- 素材越清晰、信息越明确（有字幕、明确的品类信号），系统理解越准，投放越稳。

**行动**：素材里说清楚的品类/卖点、加字幕、别用模糊表达，都是"帮算法理解"。

### Q9：为什么我的广告能进认真学习期，但之后立刻质量下降/成本翻倍？

**可能原因**
1. 广告主/竞价环境变化（旺季抢量）。
2. 素材疲劳（同素材被刷到太多次，点击率衰减）。
3. 改出价/加预算幅度过大，触发重启学习。
4. 转化回传一时波动，模型短时间内漂移。

**排查**：拉分时段报表，看是"全程缓慢下滑"还是"某次改动后骤降"，
前者多因素材疲劳，后者多因操作/环境变化。

### Q10：负反馈（用户隐藏/举报）会怎样影响我的投放？

**原理**：负向信号会进入精排目标，直接降低该广告对该类人群的得分。

**后果**：若广告负反馈率高，系统会把预算转移到体验更好的广告，你的广告逐渐跑不动。

**预防**
- 避免标题党、擦边、夸大承诺。
- 素材与落地页内容一致（别点进去货不对板）。
- 对人群精准一点，别大量打扰不相关用户。

### Q11：集成 Marketing API 报错/限流怎么办？

**排查路径**
1. 403/401：`Access-Token` 过期或权限不足 → 重新 `get_token`。
2. 429 限流：请求过频 → 退避重试（2 的指数退避，上限 60s）。
3. 参数错误：objective/optimization_goal 枚举不合法 →
   先调 `get_campaign_objective_options` / `get_bid_strategy_options` 校验。
4. 响应里 `code != 0`：读 `message` 字段定位具体参数。

**代码骨架**（与 skill 中的 safe_request 一致）

```python
import time

def safe_request(client, func, *args, retries=4, **kwargs):
    for attempt in range(retries):
        resp = func(*args, **kwargs)
        code = getattr(resp, "code", 0)
        if code == 0:
            return resp
        msg = getattr(resp, "message", "")
        if "rate" in msg.lower() or code in (42901, 42900):
            time.sleep(min(2 ** attempt, 60))
            continue
        # 其他错误直接抛, 由上层处理
        raise RuntimeError(f"code={code} msg={msg}")
    raise RuntimeError("retries exhausted")
```

### Q12：为什么 shutdown 后重启广告，早期成本特别高？

**原理**：广告停止会清空部分在线学习状态，重启后重新进入探索/学习期，
系统先"广撒网"，成本自然高于稳态。

**最佳实践**
- 避免频繁暂停/恢复（尤其同一天反复操作）。
- 真要控量，优先用 **下调预算** 而不是完全暂停。
- 重启后给足 24~48h 让模型重新收敛，不要一看成本高立刻又暂停。

---

## 五、自测题

> 自测建议：先独立作答，再看 `<details>` 里的答案。
> 覆盖本文核心：CF、矩阵分解、ANN、冷启动、评估、广告联动。

### 题 1：算法原理选择题

双塔（DSSM）在召回阶段采用的核心打分结构是下列哪一种，为什么适合大规模召回？

A. 用户特征与物品特征全交叉后过深层 MLP
B. 用户向量与物品向量的内积（可配合 ANN 近邻检索）
C. 两两样本对比训练的分类树
D. 用户-物品全矩阵的精确 KNN 扫描

<details>
<summary>答案</summary>

**选 B。**

双塔把用户与物品各自编码成向量 u、v，用内积 `<u, v>` 打分。
- 因为用户塔/物品塔都可以 **离线预计算**，在线只需把当前用户向量拿去
  对预建好的物品向量索引做 **ANN（HNSW/IVF）近邻检索**，延迟极低。
- A 的深度全交叉表达能力更强，但这种模型在线对每个候选都要重算，
  不适合百万~亿级的召回，一般用于精排。
- D 的精确 KNN 在大规模下 O(N) 扫描不可行。
</details>

### 题 2：矩阵分解推导题

写出矩阵分解（MF / ALS）把用户-物品交互矩阵 R 分解成的形式，
并说明 ALS 相比 SGD 在工程上的主要优势。

<details>
<summary>答案</summary>

MF 把 m×n 交互矩阵分解为两个低秩矩阵乘积：

```
R[m×n] ≈ P[m×k] · Q[k×n]
P 的每行 = 用户隐向量 p_u;  Q 的每列 = 物品隐向量 q_i
预测: r̂_ui = p_u · q_i  (内积)
```

目标是最小化已观测项的平方误差 + 正则化：

```
min Σ_{(u,i)∈obs} (r_ui - p_u·q_i)² + λ(‖p_u‖² + ‖q_i‖²)
```

**ALS 相比 SGD 的优势**
- 固定一个矩阵时，另一个矩阵的最优解是 **线性最小二乘的解析解**，
  可并行、可分区计算，适合 Spark 等分布式处理超大矩阵。
- 避免 SGD 的调参（学习率、minibatch、收敛抖动），
  迭代更稳定、易于工程化。

**劣势**：每轮都要做一次矩阵求逆运算，耗内存；但也因此更可预测。
</details>

### 题 3：冷启动场景题（应用题）

某新开户的电商广告主，把日预算设为 $20，CPM 出价，投放 7 天，
CTA 用 SHOP_NOW，结果 $140 花完但只有 12 个转化、CPA $11.7 远高于目标。
请从"冷启动 + 出价 + 目标"角度诊断至少 3 个问题，并给出修正动作。

<details>
<summary>答案</summary>

**诊断（至少 3 点）**

1. **优化目标/出价不匹配**：
   用 CPM（展示）出价，系统优化"展示成本"而不是"转化"，
   不会主动找高转化人群，导致转化稀疏、CPA 高。
   → 改为 `AUTO_BID_TYPE_VALUE_MAXIMIZE_CONVERSIONS` + `optimization_goal` 选转化目标。

2. **预算不足、无法积累 50 个优化事件**：
   日均 $20 太少，难以在合理时间内积累 50 个转化退出学习期，
   冷启动又长又贵。
   → 提高日预算到 ≥ 50 × 目标 CPA，给足学习流量。

3. **冷启动期目标/出价/预算频繁变动或不合理**：
   若期间改过 CTA/出价/暂停，会反复重置学习进度。
   → 冷启动期稳定投放，加预算时每次 ≤20%~30%。

4. **转化回传信号质量**：
   若 Pixel/CAPI 没有准确回传"购买"事件，
   系统学不到真实 CVR。
   → 确认转化事件准确、用高价值事件（PURCHASE/COMPLETE_PAYMENT）做目标。

**修正动作汇总**
- 换自动出价 + 转化目标，日预算提到 ≥50×目标CPA。
- 确认转化回传准确，素材/落地页一致。
- 冷启动期别乱改，出学习期后再提量。
</details>

### 题 4：评估指标选择题

在 A/B 对比两个推荐排序模型时，以下哪个指标最能反映"把命中的结果排序放到更靠前位置"的效果？

A. Precision@K
B. Recall@K
C. NDCG@K
D. HitRate@K

<details>
<summary>答案</summary>

**选 C：NDCG@K。**

- Precision@K 只看"前K个里命中几个"，不看命中的先后位置。
- Recall@K 只看"捞到了用户喜欢里的几成"，同样不看位置。
- HitRate@K 只看"是否至少命中一个"。
- **NDCG@K** 用 `log2(pos+1)` 给加权折损，命中的越靠前得分越高，
  能直接反映"排序质量"，最能区分两个模型的"排序能力"。

> 提示：GAUC（组内 AUC）也常用于排序评估，它衡量"随机把正排到负前面的概率"，
> 与 NDCG 各有侧重，实战常两者都看。
</details>

### 题 5：广告联动理解题（判断题）

判断下面说法是否正确，并说明理由：
"广告只要出价够高，就一定能把预算跑完并排在推荐的最前面。"

<details>
<summary>答案</summary>

**说法不准确。**

广告的最终排序得分是 **多重目标加权**（不是纯出价最高者赢）：

```
final_score(ad) = a·engagement(ad) + b·conversion(ad) + c·revenue(ad)
                - d·negative_feedback(ad)
```

- 出价高只提升 `revenue` 这一项，但如果：
  - 预估 CVR 很低（内容/落地页差）→ 转化项低；
  - 用户对该广告负反馈多 → 负向惩罚大；
  - 素材 CTR 低 → 连展示流量都分不到。
- 那么即便出价高，系统也可能 **不给你量**，或给量但成本失控。

此外系统还会进行 **频控 / 预算约束 / 负反馈压制**，
并非"价高者得"。真正跑量要靠：
**合理出价 + 高 CVR 转化回传 + 优质素材 + 健康的人群匹配 + 过冷启动**。
</details>

---

> 全文完。
> 本文为算法层深度文档，建议配合以下文档交叉阅读：
> - `../tiktok-ads/tiktok-ads-architecture-deep.md`（架构与实践）
> - `../tiktok-ads/tiktok-ads-optimization-deep.md`（投放优化）
> - `../tiktok-ads/tiktok-ads-troubleshooting-deep.md`（故障排查）
> - `../tiktok-ads/tiktok-ads-marketing-api-deep.md`（API 工程）
> - `day-by-day/tiktok-01-tiktok-recommendation-engine.md`（浅层双塔概览，本文为深化）
>
> 文中所有 API 方法名均来自 `scripts/tiktok_api.py` 的 `TikTokClient`。

