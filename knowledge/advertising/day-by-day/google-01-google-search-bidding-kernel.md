# Google Ads — 搜索广告竞价内核：从匹配算法到实时竞价

> 创建日期: 2026-06-09
> 作者: Ryan
> 定位: 资深专家级

---

## 第一部分：关键词匹配内核 — 从 BM25 到语义匹配

### 1.1 广告匹配的演进路径

```
Google 搜索广告匹配经历了三个大的阶段：

1998-2010: 精确匹配时代 (Exact Match Era)
├─ 规则匹配: Query 必须完全包含关键词
├─ 简单同义词扩展
└─ 缺陷: 无法理解语义，只能匹配字面相同

2010-2020: 语义匹配时代 (Semantic Match Era)
├─ BM25 相关性排序
├─ Query Expansion (查询扩展): 同义词、拼写纠正
├─ Neural Ranking Models (神经排序模型)
└─ 缺陷: 仍然依赖关键词重叠，泛化能力有限

2020-至今: 深度学习时代 (Deep Learning Era)
├─ BERT 预训练 + 广告 Fine-tune
├─ Dual-encoder (双塔) 架构
├─ Dense retrieval (密集检索)
└─ Google 私有模型: BM25 + Neural Hybrid
```

### 1.2 BM25 公式推导

```
BM25 (Best Matching 25) 是 Google 搜索广告的基线匹配模型。

公式：
BM25(q, d) = Σ [IDF(q_i) × (f(q_i, d) × (k1 + 1)) / (f(q_i, d) + k1 × (1 - b + b × |d|/avgdl))]

其中：
├─ q: 查询词
├─ d: 广告文档（关键词+广告文案）
├─ q_i: 查询中的第 i 个词
├─ f(q_i, d): 词 qi 在文档 d 中的词频
├─ IDF(q_i): 逆文档频率 = ln(N / df(q_i))
│   └─ N: 总文档数
│   └─ df(q_i): 包含 qi 的文档数
├─ k1: 词频饱和参数（通常 1.2-2.0）
├─ b: 文档长度归一化参数（通常 0.75）
└─ |d|/avgdl: 文档长度与平均文档长度之比

Google 广告场景的特殊调参：
├─ k1 = 1.5（广告中避免过度偏向高频词）
├─ b = 0.75（广告文案长度差异大，需要归一化）
└─ IDF 使用逆广告数而非逆文档数（广告数量远小于网页）
```

### 1.3 BM25 在广告场景的缺陷

```
问题 1: 同义词无法匹配
示例: "iPhone 15 手机壳" 无法匹配 "iPhone 15 case"
影响: 错失大量搜索量

问题 2: 拼写错误无法容忍
示例: "iphone 15 case" 无法匹配 "iPhone 15 case"
影响: 搜索量损失约 5-10%

问题 3: 语义理解为零
示例: "best phone to take photos" 无法匹配 "camera phone"
影响: 错失意图明确的搜索

问题 4: 语言泛化差
示例: "phone cas" 无法匹配 "phone case"
影响: 拼写纠错依赖额外模块

问题 5: 长尾查询处理差
示例: "cheap waterproof phone case for iPhone 15 with screen protector"
影响: BM25 只能匹配包含的关键词，忽略整体语义
```

### 1.4 BERT 广告匹配模型

```
Google 的广告匹配现在使用基于 Transformer 的双塔架构：

┌─────────────────────────────────────────────────────────┐
│              Dual-Encoder Architecture                   │
│                                                         │
│  Query Tower          Ad Tower                          │
│  ┌─────────────┐      ┌─────────────┐                  │
│  │     Q       │      │     A       │                  │
│  │  Transformer │      │Transformer │                  │
│  │             │      │             │                  │
│  │   [CLS] → e │      │   [CLS] → e │                  │
│  │  768-dim    │      │  768-dim    │                  │
│  └─────────────┘      └─────────────┘                  │
│       │                    │                            │
│       └────────────────────┴─→ Cosine Similarity       │
│                                   Score ∈ [-1, 1]      │
└─────────────────────────────────────────────────────────┘

训练数据：
├─ Positive pairs: 用户点击的广告
├─ Negative pairs: 广告展示但未点击
├─ Hard negatives: 广告相关但未转化
└─ 训练损失: 三元组损失 (Triplet Loss)

loss = max(0, margin + score(q, a_neg) - score(q, a_pos))
```

### 1.5 检索加速：ANN + 近似最近邻

```
问题：如果有 100 亿个广告，对每个查询做 100 亿次 cosine 计算
耗时：100 亿 × 768 维向量计算 ≈ 300ms（不可接受）

解决方案：Approximate Nearest Neighbor (ANN)

Google 使用的索引结构：
├─ HNSW (Hierarchical Navigable Small World)
│   └─ 图索引，O(log n) 查询复杂度
├─ ScaNN (Scalable Nearest Neighbors Compass)
│   └─ Google 自研，向量量化 + 乘积量化
└─ FAISS (Facebook AI Similarity Search)
    └─ 社区广泛使用，多种索引方式

ScaNN 的量化策略：
1. 量化降维: 768 → 64 (PCA)
2. 标量量化: float32 → int8 (8 倍压缩)
3. 重打分 (Rescore): 只对 Top-K 精确计算

效果：
├─ 索引大小: 7680 GB → 120 GB (64 倍压缩)
├─ 查询延迟: 300ms → 5ms (60 倍加速)
└─ 召回率: 95% (Top-100 召回率)
```

### 1.6 实战：关键词匹配策略优化

```python
# 搜索词报告分析 - 识别匹配问题
# 这是生产环境的核心工具

from collections import Counter
import re

class SearchTermAnalyzer:
    """
    搜索词报告分析器
    
    分析搜索词与关键词的匹配关系：
    1. 识别 High-CTR Low-Conv 搜索词 → 需要否定
    2. 识别 High-Conv 搜索词 → 需要添加为关键词
    3. 识别未匹配搜索词 → 发现新机会
    """
    
    def analyze(self, search_terms: list) -> dict:
        """
        分析搜索词报告
        
        参数:
        └── search_terms: 搜索词数据列表
        
        返回:
        └── 分析报告
        """
        results = {
            'negatives': [],  # 建议否定的搜索词
            'new_keywords': [],  # 建议添加的新关键词
            'unmatched': [],  # 未匹配的搜索词
        }
        
        for term in search_terms:
            # 高曝光、高点击、零转化 → 建议否定
            if (term['impressions'] > 1000 and
                term['clicks'] > 50 and
                term['conversions'] == 0):
                
                cpa_estimate = term['spend'] / max(term['clicks'], 1)
                results['negatives'].append({
                    'search_term': term['query'],
                    'impressions': term['impressions'],
                    'clicks': term['clicks'],
                    'cost': term['spend'],
                    'reason': f"高消耗低价值，建议否定",
                })
            
            # 高转化 → 建议添加为关键词
            if (term['conversions'] > 5 and
                term['cost_per_conversion'] < term['target_cpa']):
                
                results['new_keywords'].append({
                    'search_term': term['query'],
                    'conversions': term['conversions'],
                    'cost_per_conversion': term['cost_per_conversion'],
                    'match_type': 'exact',  # 建议精确匹配
                })
        
        return results
```

---

## 第二部分：Ad Auction 完整流程与数学推导

### 2.1 Google 竞价的双重拍卖机制

```
Google Ads 的竞价机制称为 "Double Auction"：

┌─────────────────────────────────────────────────────┐
│              Double Auction 机制                     │
│                                                     │
│  第一层：搜索广告拍卖 (Search Ad Auction)            │
│  ──────────────────────────────────────────────       │
│  1. 用户输入搜索词                                    │
│  2. 系统召回候选广告（基于关键词匹配）                │
│  3. 计算每个广告的 Ad Rank                           │
│  4. 按 Ad Rank 排序                                  │
│  5. 胜出者按第二价格付费                              │
│                                                     │
│  第二层：展示广告拍卖 (Display Ad Auction / RTB)     │
│  ──────────────────────────────────────────────       │
│  1. 用户访问网站                                     │
│  2. 网站向 Ad Exchange 发出请求                       │
│  3. Ad Exchange 同时向多个需求方平台 (SSP) 发出竞价请求  │
│  4. 每个 SSP 向广告主出价                             │
│  5. 最高出价者获胜                                    │
│  6. 第二价格结算                                      │
└─────────────────────────────────────────────────────┘

关键概念：
├─ Second Price Auction: 胜出者支付第二高出价 + $0.01
├─ Generalized Second Price (GSP): 多广告位时，每个位置支付该位置的
│   下一名出价
└─ Vickrey-Clarke-Groves (VCG): 理论上更优，Google 未完全采用
```

### 2.2 Ad Rank 完整公式

```
Ad Rank 的完整公式（非官方，基于逆向工程）：

Ad_Rank = Bid × pCTR × pCVR × QS_factor × Format_adj × Other_adjustments

分解：
├─ Bid: 你的出价（手动 CPC / tCPA 转换后的 CPC / tROAS 转换后的 CPC）
├─ pCTR: 点击率预测概率
│   └─ 输入特征: 查询、广告、用户、上下文
│   └─ 模型: DeepCTR (DNN + CTR 预测)
├─ pCVR: 转化率预测概率
│   └─ 输入特征: 用户、广告、落地页
│   └─ 模型: DNN (与 pCTR 共享部分网络)
├─ QS_factor: 质量分因子（1-10 缩放）
│   └─ QS = f(pCTR, ad_relevance, lpe)
├─ Format_adj: 广告格式调整因子
│   └─ Shopping: 1.3x
│   └─ Video: 1.2x
│   └─ Image: 1.1x
│   └─ Text: 1.0x
└─ Other_adjustments: 其他调整
    └─ Bid modifiers (设备、时段、地域)
    └─ Ad schedule
    └─ Location targeting
```

### 2.3 实际 CPC 的数学推导

```
第二价格拍卖的实际 CPC 公式：

Actual_CPC = (Next_Advertiser_AdRank / My_QS) + $0.01

推导：
1. 广告 A: AdRank_A = Bid_A × QS_A
2. 广告 B: AdRank_B = Bid_B × QS_B
3. 如果 AdRank_A > AdRank_B，A 获胜
4. A 需要支付的 CPC 应刚好让 A 的 AdRank = B 的 AdRank

AdRank_A = CPC_actual × QS_A = AdRank_B
CPC_actual = AdRank_B / QS_A = (Bid_B × QS_B) / QS_A

所以：
CPC_actual = (Next_Advertiser_Bid × Next_Advertiser_QS) / My_QS + $0.01
```

### 2.4 Enhanced CPC 的底层逻辑

```
Enhanced CPC (ECPC) 的工作原理：

ECPC = Manual_CPC × (1 + α × (pCVR - expected_CVR))

其中：
├─ Manual_CPC: 你设置的基础出价
├─ α: 调整因子（0-1，默认 0.5）
├─ pCVR: 本次展示的预测转化率
└─ expected_CVR: 历史平均转化率

举例：
├─ 基础出价: $2.00
├─ 平均 pCVR: 2%
├─ 本次 pCVR: 5%（高价值用户）
├─ α: 0.5
├─ ECPC = 2.00 × (1 + 0.5 × (0.05 - 0.02))
│        = 2.00 × (1 + 0.015)
│        = 2.00 × 1.015
│        = $2.03（略高，捕捉高价值点击）

└─ 如果 pCVR: 0.5%（低价值用户）
   ECPC = 2.00 × (1 + 0.5 × (0.005 - 0.02))
        = 2.00 × (1 - 0.0075)
        = 2.00 × 0.9925
        = $1.99（略低，避免低价值点击）
```

---

## 第三部分：智能竞价策略的数学推导

### 3.1 tCPA 的出价优化器

```
tCPA (Target Cost Per Acquisition) 的底层优化：

目标：
Minimize: Σ (Cost_i - Target_CPA × Conversion_i)²
Subject to: Budget ≤ Daily_Budget

求解：
Bid_i = Target_CPA × pCVR_i × β

其中 β 是预算调整因子，通过梯度下降优化：

β_{t+1} = β_t - η × ∂L/∂β

损失函数 L:
L = Σ (Bid_i × pCTR_i × pCVR_i - Target_CPA × pCVR_i)²

预算约束通过 Lagrange multiplier 处理：
L_aug = L + λ × (Σ Bid_i × pCTR_i - Budget)

其中 λ 是拉格朗日乘子，控制预算消耗速度。

生产实现：
├─ 在线优化: 每 100ms 更新一次出价
├─ 离线训练: 每天更新一次 pCVR 模型
├─ 探索: ε-greedy (5% 的出价用于探索)
└─ 收敛: 约 15 次转化后稳定
```

### 3.2 tROAS 的约束优化

```
tROAS (Target Return On Ad Spend) 的底层优化：

目标：
Maximize: Σ (Revenue_i × pCVR_i)
Subject to: Σ (Cost_i) ≤ Budget
        AND: Σ (Cost_i) / Σ (Revenue_i) ≤ 1/Target_ROAS

推导：
Revenue_i = Revenue_per_conversion × pCVR_i
Cost_i = Bid_i × pCTR_i

最优出价：
Bid_i = Target_ROAS × Revenue_per_conversion × pCVR_i × pCTR_i / pCTR_i
      = Target_ROAS × Revenue_per_conversion × pCVR_i

关键点：
├─ Revenue_per_conversion: 每个转化的平均收入
│   └─ 电商: 平均订单价值
│   └─ SaaS: LTV (客户终身价值)
├─ pCVR: 预测转化率
└─ Target_ROAS: 目标 ROAS (400% = 4.0)
```

### 3.3 Max Conversions 的贪心策略

```
Max Conversions (最大化转化数)：

策略：
在预算约束下，贪心地选择 ROI 最高的点击

贪心选择准则：
每次展示按 ROI 排序：
ROI_i = (Revenue × pCVR_i) / (Bid_i × pCTR_i)

按 ROI 降序出价，直到预算耗尽。

实现：
├─ 按 ROI 排序所有候选展示
├─ 从高 ROI 到低 ROI 依次出价
├─ 当预算不足以支付下一个展示时停止
└─ 动态调整：每 5 分钟重新计算一次排序

问题：
├─ 贪心策略可能过早耗尽预算
├─ 解决：预算 pacing 算法（见下）
```

### 3.4 预算 pacing 算法

```
预算 pacing（控制预算消耗速度）：

问题：如果上午就把预算花光，下午就完全没有展示

解决方案：Smooth Pacing

策略函数：
Bid_adjustment(t) = Target_Rate / Actual_Rate(t)

其中：
├─ Target_Rate = Daily_Budget / Expected_Impr_Possible
├─ Actual_Rate(t) = Spend(t) / Time_Proportion(t)

平滑策略：
Bid_adjustment(t) = max(0.1, min(2.0, Target_Rate / Actual_Rate(t)))

实现：
├─ 每 5 分钟重新计算一次 pacing
├─ 使用指数平滑避免剧烈波动
├─ 最终出价 = Base_Bid × Bid_adjustment(t)
└─ 边界：0.1x ~ 2.0x（防止出价过激）
```

---

## 第四部分：生产实战 — 排障与优化

### 4.1 搜索词报告分析流程

```
搜索词报告 (Search Terms Report) 是 Google Ads 中最常被忽视的优化工具。

分析流程：
1. 导出过去 30 天的搜索词报告
2. 按消费降序排列
3. 识别问题搜索词：
   a. 高消费、零转化 → 立即否定
   b. 高消费、低转化 → 降低出价
   c. 高转化、低消费 → 提高出价或添加为关键词
   d. 无展示 → 检查关键词匹配
4. 分析匹配问题：
   a. Broad match 匹配了不相关词 → 加否定
   b. Phrase match 匹配了部分词 → 加否定
   c. Exact match 未匹配相关搜索 → 添加 broad
5. 添加否定关键词：
   a. Exact negative: 完全否定某个词
   b. Phrase negative: 否定包含某个词组
   c. Broad negative: 否定相关词（高级）
```

### 4.2 Quality Score 提升实操

```
Quality Score (QS) 由三个维度组成：

1. Expected CTR (20% 权重)
   ─────────────────────────────
   提升方法：
   ├── 使用关键词在广告文案中
   ├── 使用数字和卖点增强吸引力
   ├── A/B 测试标题（带关键词 vs 不带）
   ├── 使用 Ad Extensions (附加信息)
   └── 保持广告组内关键词主题一致

2. Ad Relevance (20% 权重)
   ─────────────────────────────
   提升方法：
   ├── 每个广告组 5-20 个相关关键词
   ├── 广告文案必须包含关键词
   ├── 使用动态关键词插入 (DKI)
   └── 广告标题包含搜索词

3. Landing Page Experience (60% 权重)
   ─────────────────────────────────
   提升方法：
   ├── 页面加载速度 < 3s (Core Web Vitals)
   ├── 移动端友好 (Mobile First)
   ├── 内容与广告高度相关
   ├── 清晰的 CTA
   ├── 隐私政策和条款
   ├── 页面结构清晰
   └── 减少弹窗干扰

3 天见效方案：
├─ Day 1: 添加扩展 (Extensions) + 优化标题
├─ Day 2: 优化落地页 (速度 + 相关性)
└─ Day 3: 检查并添加否定关键词
```

### 4.3 预算耗尽排障

```
症状：预算上午花完，下午没有展示

原因排查：
1. Budget pacing 是否正常？
   ── 检查实际消费速度 vs 目标速度
   ── 如果上午消费速度过快 → pacing 算法过激

2. 是否有高 ROI 的展示机会？
   ── 检查高 pCVR 的展示是否被竞争对手抢走
   ── 考虑提高出价以竞争高价值展示

3. 竞争环境变化？
   ── 检查竞争对手是否增加了预算或出价
   ── 检查市场季节性变化

4. 预算设置是否过小？
   ── 如果预算 < 15 × target_cpa → 系统无法学习
   ── 建议：日预算 ≥ 30 × target_cpa

解决方案：
├─ 提高日预算（至少 2× 当前预算）
├─ 检查并调整 pacing 算法参数
├─ 降低 target_cpa（给算法更多空间）
└─ 扩展受众（更多展示机会）
```

---

## 第五部分：搜索广告底层数据结构

### 5.1 广告召回 (Candidate Generation)

```
搜索广告召回流程：

Query → 候选广告召回 → Ad Rank → 实际 CPC

第一步：候选召回
├─ 输入：搜索词 + 用户上下文
├─ 输出：约 1000-5000 个候选广告
├─ 召回策略：
│   ├── 精确召回: 关键词精确匹配
│   ├── 同义词召回: 通过词向量召回
│   ├── 扩展召回: Query expansion
│   └─ 神经召回: Dual-encoder 召回
└─ 时间预算：20ms（总竞价预算 50ms）

第二步：预排序 (Pre-ranking)
├─ 输入：1000-5000 个候选
├─ 输出：约 100 个
├─ 使用轻量级模型快速打分
└─ 时间预算：15ms

第三步：精排序 (Ranking)
├─ 输入：约 100 个
├─ 输出：约 20 个（最终展示的广告）
├─ 使用完整 DNN 模型
├─ 计算完整 pCTR × pCVR × QS
└─ 时间预算：15ms

总预算：50ms（搜索响应时限）
```

### 5.2 实时特征注入

```
竞价时实时注入的特征：

实时特征 (Real-time Features):
├─ 用户设备: 手机/平板/PC
├─ 用户位置: 城市/区域/国家
├─ 时间: 小时/星期几
├─ 搜索历史: 最近 5 次搜索
├─ 浏览器: Chrome/Safari/Firefox
├─ 网络: WiFi/4G/5G
└─ Cookie ID / GAID / IDFA

离线特征 (Offline Features):
├─ 用户画像: 年龄/性别/兴趣
├─ 广告历史: 该广告的历史 CTR/CVR
├─ 关键词: 关键词的历史表现
└─ 广告文案: 文案特征
```

---

## 第六部分：Google 算法更新逆向工程

### 6.1 Broad Match 的工作原理

```
Broad Match 的运作机制：

Broad Match = 词向量相似性 + 语义理解 + Query Expansion

1. 词向量模型 (Word2Vec/BERT)
   ─────────────────────────────
   "running shoes" → 相似词: "jogging sneakers", "athletic footwear"
   
2. 语义理解 (BERT)
   ─────────────────────────────
   "best shoes for running" → 匹配: "running shoes"
   
3. 查询扩展 (Query Expansion)
   ─────────────────────────────
   "iphone case" → 扩展: "iphone 15 case", "iphone 14 case", "iphone cover"

4. 拼写纠错
   ─────────────────────────────
   "iphon case" → "iphone case"

5. 同义词扩展
   ─────────────────────────────
   "cell phone" → "mobile phone", "smartphone"

Broad Match 的失控场景：
├─ 匹配了品牌词 → 与品牌广告冲突
├─ 匹配了不相关产品 → 浪费预算
├─ 匹配了竞品词 → 法律风险
└─ 必须配合否定关键词使用
```

### 6.2 Smart Bidding 的学习过程

```
Smart Bidding (tCPA/tROAS) 的学习曲线：

第 1-3 天: 探索期 (Exploration)
├─ 系统广泛测试不同出价
├─ 转化率波动大
├─ 预算消耗可能不均匀
└─ 不要调整出价！让系统学习

第 4-7 天: 收敛期 (Convergence)
├─ 出价开始稳定
├─ 转化率趋于目标
├─ 预算消耗趋于均匀
└─ 仍然不要大幅调整

第 7-14 天: 稳定期 (Stability)
├─ 系统掌握出价模式
├─ 转化率接近目标 CPA
├─ 可以小幅调整（±10%）
└─ 如果调整太大，重新进入探索期

15 conversions 的理论依据：
├─ 统计显著性: 15 次转化可以估计 CPA 的 95% 置信区间
├─ 模型复杂度: tCPA 模型约 10 个自由参数
├─ 经验法则: 参数数的 1.5 倍
└─ 低于 15 次: 模型过拟合风险高
```

---

## 自测题（专家级）

### 问题 1
假设某广告主设置 Manual CPC = $2.00，目标 CPA = $20。
广告 A: Bid=$2.00, QS=8, pCTR=0.03
广告 B: Bid=$1.50, QS=6, pCTR=0.04
请计算两者的 Ad Rank 和实际 CPC。

<details>
<summary>查看答案</summary>

```
广告 A:
AdRank_A = 2.00 × 8 × 0.03 = 0.48

广告 B:
AdRank_B = 1.50 × 6 × 0.04 = 0.36

广告 A 排名更高。
实际 CPC_A = (AdRank_B / QS_A) + $0.01 = (0.36 / 8) + 0.01 = $0.055
```
</details>

### 问题 2
tCPA 系统中，如果目标 CPA 设置过低（远低于实际 CPA），会发生什么？

<details>
<summary>查看答案</summary>

1. 系统出价会降低 → 广告展示减少
2. 预算可能花不完 → 错失转化机会
3. 转化量下降 → 学习数据减少
4. 最终可能进入"负反馈循环"：低展示 → 低数据 → 更低的出价

正确做法：目标 CPA 略高于实际 CPA（如 110-120%），让系统充分获取转化
</details>

### 问题 3
为什么 Google 的 Broad Match 需要搭配否定关键词？请举例说明。

<details>
<summary>查看答案</summary>

Broad Match 使用语义理解扩展匹配范围，但也可能匹配不相关搜索词。

例子：
- 关键词: "apple pie recipe"
- Broad Match 可能匹配: "apple company news" (Apple 公司相关新闻)
- 这是不相关的 → 需要添加否定关键词: "apple company", "apple news"
</details>

---

## 动手验证

### 5.1 搜索词分析工具

```python
from collections import Counter

# 模拟搜索词报告数据
search_terms = [
    {'query': 'running shoes men', 'impressions': 5000, 'clicks': 150, 
     'conversions': 12, 'cost': 300},
    {'query': 'shoes', 'impressions': 10000, 'clicks': 200,
     'conversions': 2, 'cost': 500},  # 高消耗低转化
    {'query': 'best running shoes for men 2024', 'impressions': 1000,
     'clicks': 50, 'conversions': 8, 'cost': 160},  # 高转化
    {'query': 'cheap shoes', 'impressions': 8000, 'clicks': 100,
     'conversions': 0, 'cost': 200},  # 高消耗零转化
]

analyzer = SearchTermAnalyzer()
results = analyzer.analyze(search_terms)

print("建议否定:")
for neg in results['negatives']:
    print(f"  {neg['search_term']} (点击:{neg['clicks']}, 花费:${neg['cost']})")

print("\n建议添加为关键词:")
for kw in results['new_keywords']:
    print(f"  {kw['search_term']} (转化:{kw['conversions']}, CPA:${kw['cost_per_conversion']:.2f})")
```

### 搜索广告竞价内核的 Go 实现

```go
// 搜索广告竞价内核: 从关键词匹配到 Ad Auction
// 覆盖 BM25 匹配、Quality Score 计算、Ad Rank、出价优化
package searchbidding

import (
	"math"
	"sort"
	"strings"
	"sync"
)

// ==================== 关键词匹配 ====================

// KeywordMatcher 关键词匹配引擎
type KeywordMatcher struct {
	// 倒排索引: term -> []keyword
	index map[string][]string
	// 关键词到广告组的映射
	kwToAdGroups map[string][]string
	// BM25 参数
	k float64 // 词长归一化因子 (默认 1.2)
	b float64 // 长度衰减因子 (默认 0.75)
}

// NewKeywordMatcher 创建关键词匹配器
func NewKeywordMatcher(k, b float64) *KeywordMatcher {
	if k == 0 {
		k = 1.2
	}
	if b == 0 {
		b = 0.75
	}
	return &KeywordMatcher{
		index:        make(map[string][]string),
		kwToAdGroups: make(map[string][]string),
		k:            k,
		b:            b,
	}
}

// AddKeyword 注册关键词及其关联的广告组
func (m *KeywordMatcher) AddKeyword(keyword, adGroup string) {
	m.kwToAdGroups[keyword] = append(m.kwToAdGroups[keyword], adGroup)
	// 分词并建立倒排
	for _, token := range tokenize(keyword) {
		m.index[token] = append(m.index[token], keyword)
	}
}

// Match 搜索查询 → 匹配的关键词 (BM25 打分)
func (m *KeywordMatcher) Match(query string, limit int) []MatchResult {
	queryTokens := tokenize(query)
	if len(queryTokens) == 0 {
		return nil
	}

	scores := make(map[string]float64)

	// BM25 打分
	for _, qToken := range queryTokens {
		if keywords, ok := m.index[qToken]; ok {
			for _, kw := range keywords {
				scores[kw] += bm25Score(query, queryTokens, kw, m.k, m.b)
			}
		}
	}

	// 按分数排序
	type scoreItem struct {
		Keyword string
		Score   float64
	}
	results := make([]scoreItem, 0, len(scores))
	for kw, score := range scores {
		results = append(results, scoreItem{kw, score})
	}
	sort.Slice(results, func(i, j int) bool {
		return results[i].Score > results[j].Score
	})

	limit = min(limit, len(results))
	out := make([]MatchResult, limit)
	for i := 0; i < limit; i++ {
		out[i] = MatchResult{
			Keyword: results[i].Keyword,
			Score:   results[i].Score,
		}
	}
	return out
}

// bm25Score BM25 相关性打分
func bm25Score(query string, queryTokens []string, doc string, k, b float64) float64 {
	docTokens := tokenize(doc)
	docLen := float64(len(docTokens))
	qLen := float64(len(queryTokens))

	var score float64
	// 去重查询词
	seen := make(map[string]bool)
	for _, t := range queryTokens {
		if seen[t] {
			continue
		}
		seen[t] = true

		// TF: 词在文档中出现次数
		var tf float64
		for _, dt := range docTokens {
			if dt == t {
				tf++
			}
		}
		tf = tf / docLen

		// IDF
		// (简化: 假设所有词在索引中均匀分布)
		idf := math.Log(1.0 + 1.0/(1.0+tf))

		// BM25 公式
		score += idf * (tf * (k + 1.0)) / (tf + k*(1.0-b+b*docLen/qLen))
	}
	return score
}

// ==================== 质量得分 ====================

// QualityScore 质量得分组件
type QualityScore struct {
	ExpectedCTR    float64 // 预期点击率 (0-1)
	LandingPageExp float64 // 落地页体验 (1-10)
	AdRelevance    float64 // 广告相关性 (1-10)
	Overall        float64 // 综合质量得分 (1-10)
}

// CalculateQualityScore 计算质量得分
func CalculateQualityScore(
	historicalCTR float64,
	landingPageScore float64,
	adRelevance float64,
) QualityScore {
	// 预期点击率: 基于历史数据 + 上下文
	expectedCTR := min(historicalCTR, 0.15) // 上限 15%

	// 综合质量 = 加权平均 (CTR 权重最高)
	overall := expectedCTR*10.0*0.5 +
		landingPageScore*0.3 +
		adRelevance*0.2

	if overall > 10 {
		overall = 10
	}

	return QualityScore{
		ExpectedCTR:    expectedCTR,
		LandingPageExp: landingPageScore,
		AdRelevance:    adRelevance,
		Overall:        overall,
	}
}

// ==================== Ad Auction ====================

// AdCandidate 候选广告
type AdCandidate struct {
	AdID         string
	Keyword      string
	Bid          float64          // 关键词出价
	QualityScore QualityScore     // 质量得分
	AdGroup      string
}

// AdRankResult 竞价结果
type AdRankResult struct {
	Ad       *AdCandidate
	AdRank   float64    // 广告排名分数
	BidPrice float64    // 实际支付价格
	Position int        // 广告位置 (1=顶部)
}

// RunAuction 执行 Ad Auction
func RunAuction(candidates []*AdCandidate, positionLimit int) []AdRankResult {
	if len(candidates) == 0 {
		return nil
	}

	// 计算每个候选的 Ad Rank
	type rankedAd struct {
		Ad     *AdCandidate
		AdRank float64
	}
	ranked := make([]rankedAd, len(candidates))
	for i, c := range candidates {
		// Ad Rank = Bid × Quality Score
		ranked[i] = rankedAd{
			Ad:     c,
			AdRank: c.Bid * c.QualityScore.Overall,
		}
	}

	// 按 Ad Rank 降序排列
	sort.Slice(ranked, func(i, j int) bool {
		return ranked[i].AdRank > ranked[j].AdRank
	})

	// 确定排名和实际价格 (第二价格机制)
	results := make([]AdRankResult, min(positionLimit, len(ranked)))
	for i, r := range ranked {
		if i >= positionLimit {
			break
		}

		results[i] = AdRankResult{
			Ad:     r.Ad,
			AdRank: r.AdRank,
			Position: i + 1,
		}

		// 实际价格: 下一名 Ad Rank / 自己的质量得分 + 最小增量
		if i+1 < len(ranked) {
			minBid := ranked[i+1].AdRank / r.Ad.QualityScore.Overall
			results[i].BidPrice = minBid + 0.01
		} else {
			results[i].BidPrice = r.Ad.Bid // 最后一名用自己的出价
		}
	}

	return results
}

// ==================== 实时出价优化 ====================

// RealTimeBidOptimizer 实时出价优化器
type RealTimeBidOptimizer struct {
	historicalData map[string][]BidHistory // adID -> 历史出价记录
	mu             sync.RWMutex
}

type BidHistory struct {
	BidPrice  float64
	Clicked   bool
	Converted bool
	Revenue   float64
	Timestamp time.Time
}

// OptimizeBid 根据历史数据优化出价
func (o *RealTimeBidOptimizer) OptimizeBid(
	adID, keyword string,
	baseBid float64,
	targetCPA float64,
) float64 {
	o.mu.RLock()
	defer o.mu.RUnlock()

	history, ok := o.historicalData[adID]
	if !ok || len(history) < 10 {
		return baseBid // 数据不足，用基准出价
	}

	// 计算该关键词的转化率和平均 CPA
	var clicks, conversions int
	var totalCost, totalRevenue float64
	recent := history[len(history)-100:] // 最近 100 次
	for _, h := range recent {
		totalCost += h.BidPrice
		if h.Clicked {
			clicks++
			if h.Converted {
				conversions++
				totalRevenue += h.Revenue
			}
		}
	}

	ctr := float64(clicks) / float64(len(recent))
	cvr := float64(conversions) / float64(clicks)
	actualCPA := 0.0
	if conversions > 0 {
		actualCPA = totalCost / float64(conversions)
	}

	// 出价调整
	adjustedBid := baseBid
	if actualCPA > targetCPA {
		// CPA 偏高 → 降低出价
		ratio := targetCPA / actualCPA
		adjustedBid *= 0.5 + ratio*0.5 // 0.5 ~ 1.0 之间
	} else if ctr < 0.01 {
		// CTR 太低 → 降低出价
		adjustedBid *= 0.8
	}

	return max(adjustedBid, 0.01) // 最低 $0.01
}

// RecordHistory 记录出价历史
func (o *RealTimeBidOptimizer) RecordHistory(adID string, h BidHistory) {
	o.mu.Lock()
	defer o.mu.Unlock()
	o.historicalData[adID] = append(o.historicalData[adID], h)
}

// ==================== 工具函数 ====================

func tokenize(s string) []string {
	// 简单分词: 转小写 + 按空格分割
	lower := strings.ToLower(s)
	return strings.Fields(lower)
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}

func max(a, b float64) float64 {
	if a > b {
		return a
	}
	return b
}

// MatchResult 关键词匹配结果
type MatchResult struct {
	Keyword string
	Score   float64
}

// 使用示例
func main() {
	// 1. 关键词匹配
	matcher := NewKeywordMatcher(1.2, 0.75)
	matcher.AddKeyword("best running shoes", "ag_001")
	matcher.AddKeyword("cheap running shoes", "ag_002")
	matcher.AddKeyword("buy running shoes online", "ag_003")

	results := matcher.Match("best running shoes for sale", 3)
	for _, r := range results {
		fmt.Printf("  %s (score: %.2f)\n", r.Keyword, r.Score)
	}

	// 2. Ad Auction
	candidates := []*AdCandidate{
		{AdID: "ad1", Bid: 2.0, QualityScore: QualityScore{Overall: 8.0}},
		{AdID: "ad2", Bid: 1.5, QualityScore: QualityScore{Overall: 9.0}},
		{AdID: "ad3", Bid: 3.0, QualityScore: QualityScore{Overall: 5.0}},
	}
	results2 := RunAuction(candidates, 3)
	for _, r := range results2 {
		fmt.Printf("  Ad %s: AdRank=%.2f, Bid=$%.3f, Pos=%d\n",
			r.Ad.AdID, r.AdRank, r.BidPrice, r.Position)
	}
}
