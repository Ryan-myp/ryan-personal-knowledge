# 广告匹配引擎：从 BM25 到 BERT 语义匹配

> 创建日期: 2026-06-10
> 作者: Ryan
> 定位: 资深专家级 — 广告匹配与召回排序

---

## 第一部分：广告匹配 Pipeline 总览

### 1.1 匹配系统的核心目标

```
广告匹配的核心目标:

┌──────────────────────────────────────────────────────────────┐
│              匹配系统目标                                       │
│                                                              │
│  核心任务:                                                   │
│  ├── Query (用户搜索) → Keywords (广告关键词) 匹配              │
│  ├── Query → Ad Creative (广告创意) 匹配                      │
│  ├── User → Ad Creative (用户画像 → 广告) 匹配                │
│  └─ Content → Ad (页面内容 → 广告) 匹配                        │
│                                                              │
│  关键指标:                                                   │
│  ├── Relevance (相关性): 广告与查询/内容的相关性               │
│  ├── Recall (召回率): 相关广告被召回的比例                     │
│  ├── Precision (精确率): 召回广告中相关广告的比例               │
│  └─ NDCG (归一化折损累计增益): 排序质量                        │
└──────────────────────────────────────────────────────────────┘
```

### 1.2 搜索广告匹配 Pipeline

```
搜索广告匹配的标准 Pipeline:

┌──────────────────────────────────────────────────────────────┐
│              广告匹配 Pipeline                                  │
│                                                              │
│  1. Query Understanding (查询理解)                              │
│     ├── 分词 (Tokenization) — BPE / SentencePiece            │
│     ├── 拼写纠错 (Spelling Correction)                        │
│     ├── 查询扩展 (Query Expansion)                            │
│     ├── 实体识别 (NER)                                        │
│     └─ 意图识别 (Intent Classification)                       │
│                                                              │
│  2. Candidate Generation (召回 / Candidate Generation)         │
│     ├── 倒排索引 (Inverted Index) — BM25                     │
│     ├── 向量检索 (Vector Search) — ANN / HNSW / IVF           │
│     ├── 关键词匹配 (Keyword Match) — Exact/Phrase/Broad      │
│     ├── 语义匹配 (Semantic Match) — DSSM / SimCSE            │
│     └─ 用户-广告协同过滤 (User-Ad CF)                         │
│                                                              │
│  3. Candidate Ranking (排序 / Candidate Ranking)              │
│     ├── Feature Engineering (特征工程)                         │
│     ├── Two-Tower Model (双塔模型)                             │
│     ├── DeepFM / DCN / Deep & Wide                          │
│     ├── Attention-based Ranking                              │
│     └─ Multi-Task Learning (MMOE / ESMM)                      │
│                                                              │
│  4. Re-Ranking (重排序)                                       │
│     ├── Diversity (多样性): 避免同类广告过多                    │
│     ├── Frequency Capping (频次控制)                           │
│     ├── Business Rules (业务规则) — 品牌保护                  │
│     ├── Boost/Penalize (升降权) — 预算/质量                  │
│     └─ Final Bid × QS × Rank Score → 竞价排序                 │
└──────────────────────────────────────────────────────────────┘
```

---

## 第二部分：召回层 (Candidate Generation)

### 2.1 BM25 倒排索引

```
BM25 (Best Matching 25) 是搜索广告召回的核心算法:

BM25 公式:
├─ BM25(q, d) = Σ_i IDF(q_i) × f(q_i, d) × (k1 + 1) / (f(q_i, d) + k1 × (1 - b + b × |d|/avgdl))
│   │   │   │
│   │   │   └─ 词频 (term frequency)
│   │   │   └─ 缩放因子 (k1: 通常 1.2-2.0)
│   │   │   └─ 文档长度归一化 (b: 通常 0.75)
│   │   └─ 词频 (归一化)
│   └─ 逆文档频率 (IDF) = log((N - n + 0.5) / (n + 0.5) + 1)
│       │   │
│       │   └─ N = 总文档数
│       └─ n = 包含该词的文档数
└─ d = 查询/广告/关键词, q = 用户查询

BM25 的优点:
├─ 简单高效: O(|q|) 时间复杂度                              │
├─ 不需要训练数据                                             │
├─ 可解释性强: IDF 衡量词的重要性                              │
└─ 实际效果: 仍然是搜索召回的 base line

BM25 的局限:
├─ 无法捕捉语义 (同义词/上下文)                                │
├─ 无法捕捉用户意图                                             │
├─ 无法捕捉长尾效果                                            │
└─ 需要依赖精确匹配                                            │

实际使用:
├─ Google: BM25 + BERT (Hybrid)                               │
├─ 分词: BPE / WordPiece                                      │
├─ 索引: Lucene / Elasticsearch                               │
├─ 召回 Top K (K=1000-10000)                                   │
└─ 传递给排序层                                               │
```

### 2.2 向量检索 (Semantic Matching)

```
向量检索是语义匹配的核心:

双塔模型 (Dual-Encoder / DSSM):

架构:
├─ Query Tower: 用户查询 → 嵌入向量 e_q
├─ Ad Tower: 广告 → 嵌入向量 e_a
└─ 相似度: sim(e_q, e_a) = cosine(e_q, e_a)

训练:
├─ 负采样: 随机采样无关广告作为负样本                           │
├─ 损失函数: InfoNCE / Contrastive Loss                       │
│   └─ L = -log(exp(sim(q,a+)*τ) / Σ_exp(sim(q,a_i)*τ))       │
├─ 模型: Transformer (BERT) / ResNet / Dense                  │
└─ 嵌入维度: 128/256/768

ANN (Approximate Nearest Neighbor) 索引:

1. HNSW (Hierarchical Navigable Small World):
   ├── 图结构: 多层图，高层跳得快，低层搜得准
   ├── 构建: O(N log N)
   ├── 查询: O(log N)
   └─ 推荐: Google/FAISS

2. IVF (Inverted File Index):
   ├── 聚类: K-Means 将向量分组
   ├── 搜索: 只搜索最近的 K 个 cluster
   ├── 可并行: 每个 cluster 独立搜索
   └─ 推荐: 大规模场景

3. PQ (Product Quantization):
   ├── 量化: 将向量分解为子向量分别量化
   ├── 压缩: 每个向量 ~64 bytes (128d → 8 bytes)
   ├── 索引: 码本 (codebook)
   └─ 推荐: 内存受限场景

实际使用:
├─ Google: HNSW + DSSM (BERT-based)                           │
├─ Meta: DSSM + HNSW                                          │
├─ TikTok: DSSM + IVF-PQ                                      │
└─ 召回 Top 1000-10000 → 传给排序层                            │
```

---

## 第三部分：排序层 (Ranking)

### 3.1 特征工程

```
广告排序特征体系:

┌──────────────────────────────────────────────────────────────┐
│              广告排序特征                                      │
│                                                              │
│  查询特征 (Query Features):                                   │
│  ├── 查询文本: TF-IDF / BERT Embedding                        │
│  ├── 查询长度 (词数/字符数)                                    │
│  ├── 查询意图: 商业/信息/导航                                  │
│  ├── 查询热度 (搜索量)                                        │
│  └─ 查询新鲜度 (新查询/历史查询)                               │
│                                                              │
│  广告特征 (Ad Features):                                      │
│  ├── 广告文案: TF-IDF / BERT Embedding                        │
│  ├── 广告类型: Search/Display/Video                           │
│  ├── 广告历史 CTR/CVR                                         │
│  ├── 广告主质量分数                                           │
│  ├── 广告质量 Score (QS)                                      │
│  └─ 广告落地页特征                                            │
│                                                              │
│  用户特征 (User Features):                                    │
│  ├── 用户画像: 年龄/性别/收入/兴趣                             │
│  ├── 用户行为: 历史点击/购买/浏览                              │
│  ├── 用户状态: 新用户/老用户/流失预警                           │
│  ├── 设备: 手机/平板/桌面                                     │
│  └─ 上下文: 时间/位置/网络                                    │
│                                                              │
│  交叉特征 (Cross Features):                                   │
│  ├── Query × Ad: 关键词匹配/文本相似度                          │
│  ├── Query × User: 用户兴趣匹配                                │
│  ├── Ad × User: 用户历史对该广告主的互动                         │
│  ├── Ad × Context: 广告在特定场景下的表现                       │
│  └─ Query × Ad × User: 三维交叉                               │
│                                                              │
│  上下文特征 (Context Features):                               │
│  ├── 页面: URL/内容/类别/广告数量                              │
│  ├── 时间: 小时/星期/季节                                      │
│  ├── 位置: 城市/地区/国家                                      │
│  └─ 网络: WiFi/4G/5G                                         │
└──────────────────────────────────────────────────────────────┘
```

### 3.2 排序模型

```
广告排序模型演进:

1. LR (Logistic Regression) — 2010 前:
   ├── 简单: O(x^T w)
   ├── 线性模型
   └─ 只能捕捉线性关系

2. GBDT + LR — 2010-2015:
   ├── GBDT 做特征工程
   ├── LR 做最终预测
   └─ Facebook 2014 论文

3. DeepFM / DCN — 2016-2019:
   ├── DeepFM: FM (特征交叉) + Deep (非线性)
   ├── DCN: Cross Network (特征交叉) + Deep Network
   └─ Google 2017, Tencent 2017

4. Multi-Task — 2019-Present:
   ├── MMOE: Multi-gate Mixture of Experts
   ├── ESMM: Entire Space Multi-Task Model
   ├── Share-Bottom / PLE (Progressive Layered Extraction)
   └─ 同时优化 CTR/CVR/CPA/ROI

Google Ads 排序模型 (Current):
├─ 多任务学习: CTR + CVR + CPA + ROI
├─ Transformer 架构 (BERT-like)
├─ 实时特征 (Real-time Features)
├─ 在线学习 (Online Learning)
└─ 端侧推理 (On-Device Inference for Privacy)
```

### 3.3 ESMM (Entire Space Multi-Task Model)

```
ESMM 解决 CTCCV (Click-Through and Conversion) 问题:

问题:
├─ CTR 数据丰富 (每次展示都有 click 信号)
├─ CVR 数据稀疏 (只有点击后有 conversion 信号)
└─ 直接用 CVR 建模: 样本偏差 + 数据稀疏

ESMM 方案:
├─ 同时建模三个任务:                                         │
│   ├── P(click) = CTR                                        │
│   ├── P(conversion) = CVR                                   │
│   └─ P(ctcvr) = P(click) × P(conversion|click) = CTR × CVR  │
│                                                              │
├─ 共享底层:                                                  │
│   ├── Base Layer: 输入所有特征                                │
│   ├── Shared Encoder: 共享表示                               │
│   └─ Task-Specific Towers: CTR Tower / CTCVR Tower           │
│                                                              │
├─ 损失函数:                                                  │
│   ├── L_CTR = -Σ(y_i log(ŷ_i) + (1-y_i) log(1-ŷ_i))       │
│   ├── L_CTCVR = -Σ(z_i log(ẑ_i) + (1-z_i) log(1-ẑ_i))     │
│   └─ L_Total = L_CTR + α × L_CTCVR                         │
│                                                              │
└─ 推论: P(CVR) = P(CTCVR) / P(CTR)                          │
    └─ 利用 CTR 模型约束 CVR 预测，缓解稀疏问题                  │
```

---

## 第四部分：重排序 (Re-Ranking)

### 4.1 Re-Ranking 策略

```
Re-Ranking 是最终广告选择:

┌──────────────────────────────────────────────────────────────┐
│              Re-Ranking 流程                                   │
│                                                              │
│  输入: 排序后的 Top K 广告 (K=50-200)                          │
│                                                              │
│  Step 1: 多样性控制 (Diversity)                               │
│  ├── MMR (Maximal Marginal Relevance):                       │
│  │   └─ Re-rank = λ × relevance - (1-λ) × max_similarity    │
│  ├── 同类广告去重 (同一广告主最多 2 个)                         │
│  └─ 广告格式多样化 (Search/Display/Video 混合)                 │
│                                                              │
│  Step 2: 业务规则 (Business Rules)                            │
│  ├── 品牌保护 (Brand Safety): 过滤不适当广告                   │
│  ├── 广告主黑名单: 排除特定广告主                               │
│  ├── 预算控制: 高消耗广告主降权                                │
│  ├── 广告轮换 (Ad Rotation): 均匀展示多个广告                    │
│  └─ 合规检查: GDPR/CCPA 限制                                  │
│                                                              │
│  Step 3: 竞价排序 (Bid Sorting)                               │
│  ├── Final Score = bid × QS × rank_score × pacing_factor     │
│  ├── 按 Score 降序排列                                         │
│  └─ 前 N 名中标 (N = 广告位数量)                               │
│                                                              │
│  Step 4: 最终选择                                             │
│  ├── 填充: 如果不足 N 个广告 → 使用空占位符                     │
│  ├── 广告位: 首页/侧边栏/底部                                  │
│  └─ 创意: 根据用户/上下文选择最佳创意                           │
└──────────────────────────────────────────────────────────────┘
```

---

## 第五部分：自测题

### 问题 1
BM25 公式中 IDF 的作用是什么？

<details>
<summary>查看答案</summary>

IDF 衡量词的重要性。稀有词 (出现在少量文档中) 的 IDF 值高，权重更高；常见词 IDF 低，权重低。
IDF = log((N - n + 0.5) / (n + 0.5) + 1)
</details>

### 问题 2
ESMM 如何解决 CVR 数据稀疏问题？

<details>
<summary>查看答案</summary>

- 同时建模 CTR 和 CTCVR (Click-Through-and-Conversion-Rate)
- 利用 CTR 模型丰富训练信号
- 推论: P(CVR) = P(CTCVR) / P(CTR)
- 缓解样本偏差和数据稀疏问题
</details>

### 问题 3
Re-Ranking 的主要策略有哪些？

<details>
<summary>查看答案</summary>

1. 多样性控制 (MMR/去重)
2. 业务规则 (品牌保护/预算控制)
3. 竞价排序 (bid × QS × rank_score × pacing)
4. 广告轮换
</details>

---

*今天花 90 分钟：深入掌握广告匹配引擎技术*
*答不出自测题？回去重读对应章节。*
