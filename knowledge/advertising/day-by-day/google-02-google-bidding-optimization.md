# Google Ads — 竞价策略与深度优化

> 创建日期: 2026-06-09
> 作者: Ryan

---

## 第一部分：竞价策略深度解析

### 1.1 Google Ads 竞价机制

```
Google Ads 采用的是广义第二价格拍卖 (GSP)
但实际机制比简单 GSP 复杂得多

┌─────────────────────────────────────────────────────┐
│              Google Ads 竞价流程                      │
│                                                     │
│  1. 用户搜索关键词                                    │
│       │                                              │
│       ▼                                              │
│  2. Google 召回候选广告                               │
│     - 基于关键词匹配                                  │
│     - 基于历史表现                                    │
│     - 基于相关性                                      │
│       │                                              │
│       ▼                                              │
│  3. 计算 Quality Score                                │
│     ┌──────────────────────────────────────┐         │
│     │ QS = f(CTR预测, 落地页体验, 广告相关性) │         │
│     └──────────────────────────────────────┘         │
│       │                                              │
│       ▼                                              │
│  4. 计算 Ad Rank                                      │
│     Ad Rank = Bid × QS                                │
│       │                                              │
│       ▼                                              │
│  5. 排序并展示                                        │
│     - Ad Rank 最高的排第一                             │
│     - 实际出价 = 下一名的 Ad Rank / 自己的 QS + $0.01  │
└─────────────────────────────────────────────────────┘
```

### 1.2 竞价策略类型详解

```
┌──────────────────────────────────────────────────────────┐
│                  Google Ads 竞价策略                       │
│                                                          │
│  手动竞价 (Manual Bidding):                               │
│  ├── CPC (每次点击付费)                                    │
│  │   ├── 手动 CPC: 自己设定最高出价                         │
│  │   └── 增强型 CPC (ECPC): 系统自动调整                    │
│  ├── CPM (每千次展示付费): 品牌广告                         │
│  ├── CPA (每次行动付费): 手动目标 CPA                       │
│  └── vCPM (可展示次数): 品牌广告                          │
│                                                          │
│  智能竞价 (Smart Bidding):                                │
│  ├── tCPA: 目标每次转化费用                                │
│  ├── tROAS: 目标广告支出回报率                              │
│  ├── Max Conversions: 最大化转化次数                        │
│  ├── Max Conversions with tCPA: 带 tCPA 上限的             │
│  ├── Max Clicks: 最大化点击数                              │
│  └── Target Impression Share: 目标展示份额                 │
└──────────────────────────────────────────────────────────┘
```

### 1.3 Quality Score 源码级分析

```python
# google_ads/quality_score.py
# Quality Score 计算源码分析

class QualityScoreModel:
    """
    Quality Score 计算模型
    
    虽然 Google 不公开完整公式，但通过逆向工程和
    公开信息，可以确定 QS 主要受三个因素影响:
    
    1. Expected Click-Through Rate (CTR)
    2. Ad Relevance (广告相关性)
    3. Landing Page Experience (落地页体验)
    
    每个因素的范围是: 低于平均 / 平均 / 高于平均
    最终 QS 范围: 1-10
    """
    
    def calculate_quality_score(self, 
                                 expected_ctr: float,  # 预测 CTR
                                 ad_relevance: float,   # 广告相关性分数
                                 landing_page_experience: float) -> int:
        """
        计算 Quality Score
        
        简化公式 (实际 Google 用复杂的机器学习模型):
        
        QS = floor((expected_ctr_norm * ad_rel_norm * lpe_norm) * 9) + 1
        
        其中每个分量被归一化到 [0, 1] 范围
        """
        # 归一化各维度 (0=低于平均, 0.5=平均, 1=高于平均)
        ctr_score = self._normalize_ctr(expected_ctr)
        ad_score = self._normalize_ad_relevance(ad_relevance)
        lpe_score = self._normalize_lpe(landing_page_experience)
        
        # 综合计算
        qs = (ctr_score * ad_score * lpe_score) * 9 + 1
        
        return max(1, min(10, int(qs)))
    
    def _normalize_ctr(self, expected_ctr: float) -> float:
        """
        归一化 CTR 分数
        
        Google 使用对数尺度:
        - 低于历史平均 CTR: 0.0-0.33
        - 平均 CTR: 0.33-0.66
        - 高于历史 CTR: 0.66-1.0
        """
        # 假设历史平均 CTR 为 2%
        avg_ctr = 0.02
        
        if expected_ctr < avg_ctr * 0.5:
            return 0.2
        elif expected_ctr < avg_ctr:
            return 0.4
        elif expected_ctr < avg_ctr * 1.5:
            return 0.6
        elif expected_ctr < avg_ctr * 2.0:
            return 0.8
        else:
            return 1.0
    
    def _normalize_ad_relevance(self, relevance_score: float) -> float:
        """
        归一化广告相关性
        
        基于关键词与广告的匹配程度:
        - 精确匹配 + 包含关键词: 高相关
        - 词组匹配: 中等相关
        - 广泛匹配: 低相关
        """
        if relevance_score >= 0.8:
            return 1.0
        elif relevance_score >= 0.5:
            return 0.5
        else:
            return 0.2
    
    def _normalize_lpe(self, lpe_score: float) -> float:
        """
        归一化落地页体验
        
        基于:
        - 页面加载速度
        - 移动端适配
        - 内容相关性
        - 导航性
        """
        if lpe_score >= 0.8:
            return 1.0
        elif lpe_score >= 0.5:
            return 0.5
        else:
            return 0.2


# 使用示例
model = QualityScoreModel()
qs = model.calculate_quality_score(
    expected_ctr=0.04,        # 预测 CTR 4%
    ad_relevance=0.85,        # 高相关性
    landing_page_experience=0.75,
)
print(f"Quality Score: {qs}")  # 8 或 9
```

### 1.4 Ad Rank 源码分析

```python
# google_ads/ad_rank.py
# Ad Rank 计算源码

class AdRankCalculator:
    """
    Ad Rank 计算
    
    公式: Ad Rank = Bid × Quality Score
    
    但实际计算更复杂:
    - Bid 使用 micros 单位
    - QS 经过缩放
    - 考虑广告格式调整因子
    
    实际排名:
    - 按 Ad Rank 降序排列
    - Ad Rank 相同看广告格式 (视频 > 图片 > 文本)
    """
    
    def calculate_ad_rank(self, bid_micros: int, 
                          quality_score: int,
                          ad_format_bonus: float = 1.0) -> float:
        """
        计算 Ad Rank
        
        参数:
        ├── bid_micros: 出价（micros 单位）
        ├── quality_score: 质量得分 (1-10)
        └── ad_format_bonus: 广告格式调整因子
            - 文本广告: 1.0
            - 图片广告: 1.1
            - 视频广告: 1.2
            - 购物广告: 1.3
        
        返回:
        └── Ad Rank 分数
        """
        # QS 缩放到 [0.1, 1.0] 范围
        qs_normalized = quality_score / 10.0
        
        # Ad Rank = Bid × QS × 格式因子
        ad_rank = bid_micros * qs_normalized * ad_format_bonus
        
        return ad_rank
    
    def calculate_actual_cpc(self, current_ad_rank: float,
                             next_advertiser_rank: float,
                             own_quality_score: float) -> float:
        """
        计算实际 CPC (每次点击费用)
        
        Google 采用广义第二价格拍卖:
        实际出价 = (下一名 Ad Rank) / (自己的 QS) + $0.01
        
        这就是为什么高质量得分可以降低 CPC!
        """
        from google_ads.utils.micros import MicrosConverter
        
        # 实际 CPC (micros)
        actual_cpc_micros = (next_advertiser_rank / own_quality_score) + MicrosConverter.to_micros(0.01)
        
        return MicrosConverter.from_micros(actual_cpc_micros)


# 使用示例
calc = AdRankCalculator()

# 广告 A: bid=$2.00, QS=8
ad_a_rank = calc.calculate_ad_rank(
    bid_micros=MicrosConverter.to_micros(2.00),
    quality_score=8,
    ad_format_bonus=1.0,
)

# 广告 B: bid=$3.00, QS=4
ad_b_rank = calc.calculate_ad_rank(
    bid_micros=MicrosConverter.to_micros(3.00),
    quality_score=4,
    ad_format_bonus=1.0,
)

print(f"广告 A Ad Rank: {ad_a_rank}")    # 16000000
print(f"广告 B Ad Rank: {ad_b_rank}")    # 12000000
# 广告 A 排名更高！即使出价更低
```

---

## 第二部分：智能竞价策略源码

### 2.1 tCPA 目标每次转化费用

```python
# google_ads/bidding/tcpa.py
# tCPA (Target Cost Per Acquisition) 竞价

class TargetCPABidder:
    """
    tCPA 竞价器
    
    工作原理:
    1. 系统预测每次展示的转化概率 P(conversion | impression)
    2. 基于目标 CPA 计算最优出价:
       optimal_bid = target_cpa × P(conversion) × bid_multiplier
    3. 考虑竞争环境和预算约束调整
    
    优化目标:
    ├── 在目标 CPA 约束下最大化转化次数
    └── 预算消耗速度控制
    """
    
    def __init__(self, target_cpa_micros: int, 
                 budget_micros: int,
                 learning_period_hours: int = 7 * 24):
        """
        初始化 tCPA 竞价器
        
        参数:
        ├── target_cpa_micros: 目标 CPA (micros)
        ├── budget_micros: 日预算 (micros)
        └── learning_period_hours: 学习期 (小时)
            - Google 需要 ~15 次转化来学习
            - 通常在 2-7 天内完成
        """
        self.target_cpa_micros = target_cpa_micros
        self.budget_micros = budget_micros
        self.learning_period = learning_period_hours
        self.conversion_count = 0
        self.is_learning = True
    
    def calculate_bid(self, 
                      ad_group_id: str,
                      keyword_id: str,
                      predicted_conversions: float,  # 预测转化数
                      predicted_ctr: float,          # 预测 CTR
                      competition_level: str = 'MEDIUM') -> int:
        """
        计算优化出价
        
        流程:
        1. 获取预测值
        2. 计算出价
        3. 应用调整因子
        4. 返回 bid_micros
        
        参数:
        ├── predicted_conversions: 预测转化数
        ├── predicted_ctr: 预测点击率
        └── competition_level: 竞争程度 (LOW/MEDIUM/HIGH)
        
        返回:
        └── bid_micros (最高出价)
        """
        from google_ads.utils.micros import MicrosConverter
        
        if self.is_learning:
            # 学习期使用保守出价
            bid = int(self.target_cpa_micros * 0.5 * predicted_conversions)
        else:
            # 正常竞价
            bid = self._calculate_optimal_bid(
                predicted_conversions=predicted_conversions,
                predicted_ctr=predicted_ctr,
                competition_level=competition_level,
            )
        
        return bid
    
    def _calculate_optimal_bid(self, predicted_conversions: float,
                                predicted_ctr: float,
                                competition_level: str) -> int:
        """
        计算最优出价
        
        核心公式:
        optimal_bid = target_cpa × predicted_conversions × adjustment
        
        adjustment 考虑:
        ├── 竞争程度 (HIGH: × 1.2, MEDIUM: × 1.0, LOW: × 0.8)
        ├── 时间调整 (高峰时段 × 1.1)
        ├── 设备调整 (移动端 × 0.9)
        └── 位置调整 (地理)
        """
        competition_multipliers = {
            'LOW': 0.8,
            'MEDIUM': 1.0,
            'HIGH': 1.2,
        }
        
        adj = competition_multipliers.get(competition_level, 1.0)
        
        # 基于预测转化概率计算出价
        bid_micros = int(self.target_cpa_micros * predicted_conversions * adj)
        
        return max(0, bid_micros)
    
    def update(self, impressions: int, clicks: int, 
               conversions: float, spend_micros: int):
        """
        更新模型
        
        记录每次竞价结果，优化预测模型
        """
        self.conversion_count += int(conversions)
        
        if self.conversion_count >= 15:  # 至少 15 次转化
            self.is_learning = False
    
    def adjust_for_budget(self, current_spend: int) -> float:
        """
        根据预算消耗调整出价
        
        预算充足: × 1.0
        预算紧张: × 0.5-0.8
        预算快用完: × 0.1
        """
        budget_utilization = current_spend / self.budget_micros
        
        if budget_utilization > 0.95:
            return 0.1
        elif budget_utilization > 0.8:
            return 0.5
        elif budget_utilization > 0.5:
            return 0.8
        else:
            return 1.0
```

### 2.2 tROAS 目标广告支出回报率

```python
# google_ads/bidding/troas.py
# tROAS (Target Return On Ad Spend) 竞价

class TargetROASBidder:
    """
    tROAS 竞价器
    
    适用于电商场景:
    - 每个转化价值不同 (不同产品价格不同)
    - 目标是最大化 revenue 而非 conversions
    
    公式:
    bid = target_roas × predicted_revenue × predicted_conversion_prob
    
    使用场景:
    ├── 电商网站 (不同产品价格差异大)
    ├── SaaS 产品 (不同套餐价格不同)
    └── B2B 服务 (不同客户 LTV 不同)
    """
    
    def __init__(self, target_roas: float):
        """
        初始化 tROAS 竞价器
        
        参数:
        └── target_roas: 目标 ROAS (400% = 4.0)
        """
        self.target_roas = target_roas  # 4.0 = 400%
    
    def calculate_bid(self, 
                      predicted_revenue: float,  # 预测收入 (USD)
                      predicted_conversion_prob: float,  # 转化概率
                      keyword: str = None) -> int:
        """
        计算 tROAS 出价
        
        流程:
        1. 获取预测收入
        2. 获取转化概率
        3. 计算出价
        4. 应用 keyword 特定调整
        
        参数:
        ├── predicted_revenue: 预测收入 (USD)
        ├── predicted_conversion_prob: 转化概率 (0-1)
        └── keyword: 关键词 (用于 keyword 特定调整)
        
        返回:
        └── bid_micros
        """
        from google_ads.utils.micros import MicrosConverter
        
        # 核心公式
        bid_micros = int(
            self.target_roas * predicted_revenue * predicted_conversion_prob * MicrosConverter.MICRO_UNITS
        )
        
        # 应用 keyword 特定调整
        if keyword:
            bid_micros = self._apply_keyword_adjustment(bid_micros, keyword)
        
        return bid_micros
    
    def _apply_keyword_adjustment(self, bid_micros: int, keyword: str) -> int:
        """
        关键词特定出价调整
        
        基于关键词的历史表现:
        - 高价值关键词: +20%
        - 中等价值: +0%
        - 低价值: -10%
        """
        keyword_performance = self._get_keyword_performance(keyword)
        
        if keyword_performance['roas'] > self.target_roas * 1.2:
            # 高价值关键词，提高出价
            return int(bid_micros * 1.2)
        elif keyword_performance['roas'] > self.target_roas:
            return int(bid_micros * 1.05)
        else:
            # 低价值关键词，降低出价
            return int(bid_micros * 0.85)


class KeywordPerformanceTracker:
    """关键词表现追踪"""
    
    def __init__(self):
        self.keyword_stats = {}
    
    def update(self, keyword: str, impressions: int, clicks: int,
               conversions: int, revenue: float):
        """更新关键词统计"""
        if keyword not in self.keyword_stats:
            self.keyword_stats[keyword] = {
                'impressions': 0, 'clicks': 0,
                'conversions': 0, 'revenue': 0.0,
            }
        
        stats = self.keyword_stats[keyword]
        stats['impressions'] += impressions
        stats['clicks'] += clicks
        stats['conversions'] += conversions
        stats['revenue'] += revenue
    
    def get_performance(self, keyword: str) -> dict:
        """获取关键词表现"""
        stats = self.keyword_stats.get(keyword, {})
        
        ctr = stats.get('clicks', 0) / max(stats.get('impressions', 1), 1)
        conversion_rate = stats.get('conversions', 0) / max(stats.get('clicks', 1), 1)
        roas = stats.get('revenue', 0) / max(stats.get('cost', 1), 1)
        
        return {
            'ctr': ctr,
            'conversion_rate': conversion_rate,
            'roas': roas,
        }
```

---

## 第三部分：广告优化实战

### 3.1 关键词优化策略

```python
# google_ads/optimization/keyword.py
# 关键词优化策略

class KeywordOptimizer:
    """
    关键词优化器
    
    核心策略:
    ├── 高表现关键词: 提高出价 + 扩展匹配
    ├── 低表现关键词: 降低出价 / 否定
    ├── 新关键词: 小预算测试
    └── 否定关键词: 排除不相关搜索
    """
    
    def optimize(self, ad_group_id: str, keywords: list) -> list:
        """
        执行关键词优化
        
        流程:
        1. 获取关键词表现数据
        2. 分类关键词 (高/中/低表现)
        3. 应用优化策略
        4. 返回优化建议
        
        参数:
        └── keywords: 关键词列表
        
        返回:
        └── 优化建议列表
        """
        optimizations = []
        
        for kw in keywords:
            if kw['conversions'] == 0 and kw['impressions'] > 100:
                # 有展示无转化 → 考虑否定或暂停
                optimizations.append({
                    'action': 'NEGATIVE',
                    'keyword': kw['text'],
                    'reason': '无转化，高展示',
                    'impact': 'high',
                })
            elif kw['cost_per_conversion'] > kw['target_cpa'] * 2:
                # CPA 过高 → 降低出价
                optimizations.append({
                    'action': 'DECREASE_BID',
                    'keyword': kw['text'],
                    'factor': 0.7,  # 降低 30%
                    'reason': f"CPA={kw['cost_per_conversion']} > 目标={kw['target_cpa']*2}",
                    'impact': 'medium',
                })
            elif kw['ctr'] > 0.1 and kw['cost_per_conversion'] < kw['target_cpa']:
                # 高 CTR + 低 CPA → 提高出价
                optimizations.append({
                    'action': 'INCREASE_BID',
                    'keyword': kw['text'],
                    'factor': 1.3,  # 提高 30%
                    'reason': f"CTR={kw['ctr']:.2%}, CPA={kw['cost_per_conversion']}",
                    'impact': 'high',
                })
            else:
                optimizations.append({
                    'action': 'KEEP',
                    'keyword': kw['text'],
                    'reason': '表现正常',
                    'impact': 'low',
                })
        
        return optimizations
```

### 3.2 广告文案 A/B 测试

```python
# google_ads/optimization/ad_copy.py
# 广告文案 A/B 测试

class AdCopyAABTester:
    """
    广告文案 A/B 测试
    
    测试维度:
    ├── 标题 (Title)
    ├── 描述 (Description)
    ├── CTA (行动号召)
    ├── 扩展 (Extensions)
    └── 目标受众 (Targeting)
    """
    
    def setup_test(self, ad_group_id: str, test_ads: list) -> str:
        """
        设置 A/B 测试
        
        流程:
        1. 创建多个广告变体
        2. 分配相同预算
        3. 确保统计显著性
        4. 持续监测
        
        统计显著性要求:
        ├── 至少 100 次点击/组
        ├── 至少 30 次转化/组
        └── p-value < 0.05
        """
        # 创建广告变体
        variants = []
        for i, ad_data in enumerate(test_ads):
            ad = self._create_ad_variation(ad_group_id, ad_data, i)
            variants.append(ad)
        
        return variants
    
    def analyze_results(self, test_id: str) -> dict:
        """
        分析测试结果
        
        使用 t-test 判断差异显著性:
        H0: 两个广告的 CTR 没有显著差异
        H1: 两个广告的 CTR 有显著差异
        
        返回:
        ├── winner: 获胜的广告
        ├── confidence: 置信度
        └── recommendation: 建议
        """
        import scipy.stats as stats
        
        # 获取两个广告的表现
        ad_a_data = self._get_ad_performance(test_id, 'A')
        ad_b_data = self._get_ad_performance(test_id, 'B')
        
        # 点击数据
        clicks_a = ad_a_data['clicks']
        impressions_a = ad_a_data['impressions']
        clicks_b = ad_b_data['clicks']
        impressions_b = ad_b_data['impressions']
        
        # 进行比例 t-test
        z_stat, p_value = stats.proportions_ztest(
            [clicks_a, clicks_b],
            [impressions_a, impressions_b],
            alternative='two-sided'
        )
        
        # 判断显著性
        if p_value < 0.05:
            winner = 'A' if clicks_a/impressions_a > clicks_b/impressions_b else 'B'
            confidence = 1 - p_value
            return {
                'winner': winner,
                'confidence': confidence,
                'p_value': p_value,
                'recommendation': f"广告 {winner} 显著优于另一组，建议推广",
            }
        else:
            return {
                'winner': None,
                'confidence': 0,
                'p_value': p_value,
                'recommendation': "差异不显著，需要更多数据",
            }
```

---

## 第三部分：自测

### 问题 1
Google Ads 的 Ad Rank 公式是什么？
<details>
<summary>查看答案</summary>

- Ad Rank = Bid × Quality Score × 广告格式调整因子
- Quality Score 越高，实际 CPC 越低
</details>

### 问题 2
tROAS 和 tCPA 的区别是什么？
<details>
<summary>查看答案</summary>

- tCPA: 目标每次转化费用，适合每个转化价值相同的场景
- tROAS: 目标广告支出回报率，适合每个转化价值不同的场景
- 电商推荐 tROAS，B2B 推荐 tCPA
</details>

### 问题 3
如何判断 A/B 测试是否有显著差异？
<details>
<summary>查看答案</summary>

- 使用 t-test 或 z-test
- p-value < 0.05 表示显著
- 每组至少需要 100 点击、30 次转化
</details>

---

## 第四部分：动手验证

### 4.1 关键词优化

```python
from google_ads.optimization.keyword import KeywordOptimizer

optimizer = KeywordOptimizer()
ad_group_id = "YOUR_AD_GROUP_ID"

# 获取关键词数据
keywords = self._fetch_keywords(ad_group_id)

# 执行优化
optimizations = optimizer.optimize(ad_group_id, keywords)

for opt in optimizations:
    print(f"关键词: {opt['keyword']}")
    print(f"  操作: {opt['action']}")
    print(f"  原因: {opt['reason']}")
    print(f"  影响: {opt['impact']}")
```

### 5. Go 实现：Google Ads 竞价优化器

```go
package main

import (
	"context"
	"encoding/json"
	"fmt"
	"math"
	"sync"
	"time"
)

// GoogleAdsBiddingClient 封装 Google Ads 竞价 API 操作
type GoogleAdsBiddingClient struct {
	customerID   string
	accessToken  string
	httpClient   *http.Client
	mu           sync.Mutex
	requestCount int
}

// BidStrategy 竞价策略基类
type BidStrategy interface {
	Name() string
	CalculateBid(params BidParams) float64
	RequiresConversionData() bool
	RequiresHistory() bool
}

// BidParams 竞价参数
type BidParams struct {
	CustomerID string
	AdGroupID  string
	CampaignID string
	Keyword    string
	MatchType  string // EXACT, PHRASE, BROAD
	Position   float64 // 广告位
	QualityScore int   // 质量得分
	HistoricalCTR float64
	HistoricalCVR float64
	TargetCPA  float64
	TargetROAS float64
	MaxCPC     float64
	MinCPC     float64
}

// ManualBidding 手动 CPC 竞价
type ManualBidding struct {
	maxBid float64
}

func NewManualBidding(maxBid float64) *ManualBidding {
	return &ManualBidding{maxBid: maxBid}
}

func (m *ManualBidding) Name() string { return "MANUAL_CPC" }
func (m *ManualBidding) RequiresConversionData() bool { return false }
func (m *ManualBidding) RequiresHistory() bool          { return false }
func (m *ManualBidding) CalculateBid(params BidParams) float64 {
	return m.maxBid
}

// TargetCPABidding tCPA 竞价策略
type TargetCPABidding struct {
	targetCPA    float64
	sensitivity  float64 // 调整敏感度 0.5-1.5
	learningRate float64 // 学习率
	history      []CPARecord
	mu           sync.Mutex
}

type CPARecord struct {
	Clicks    int
	Conversions int
	ClickCost float64
	Timestamp time.Time
}

func NewTargetCPABidding(targetCPA float64) *TargetCPABidding {
	return &TargetCPABidding{
		targetCPA:    targetCPA,
		sensitivity:  0.8,
		learningRate: 0.05,
	}
}

func (t *TargetCPABidding) Name() string { return "TARGET_CPA" }
func (t *TargetCPABidding) RequiresConversionData() bool { return true }
func (t *TargetCPABidding) RequiresHistory() bool        { return true }

func (t *TargetCPABidding) RecordClick(cost float64) {
	t.mu.Lock()
	defer t.mu.Unlock()
	t.history = append(t.history, CPARecord{Clicks: 1, ClickCost: cost})
}

func (t *TargetCPABidding) RecordConversion(clickCost, conversionValue float64) {
	t.mu.Lock()
	defer t.mu.Unlock()
	// 更新最近记录
	if len(t.history) > 0 {
		t.history[len(t.history)-1].Conversions = 1
	}
}

func (t *TargetCPABidding) CalculateBid(params BidParams) float64 {
	t.mu.Lock()
	defer t.mu.Unlock()

	// 计算历史 CPA
	var totalCost, totalConversions float64
	for _, r := range t.history {
		totalCost += r.ClickCost
		totalConversions += float64(r.Conversions)
	}

	avgCPA := totalCost / (totalConversions + 1)

	// 基于历史 CPA 和目标 CPA 调整出价
	if avgCPA > t.targetCPA {
		// 实际 CPA 高于目标，降低出价
		adjustment := 1.0 - t.sensitivity*(avgCPA/t.targetCPA-1.0)
		if adjustment < 0.5 {
			adjustment = 0.5
		}
		bid := params.TargetCPA * adjustment / (params.HistoricalCVR + 1e-10)
		return clamp(bid, params.MinCPC, params.MaxCPC)
	} else if avgCPA < t.targetCPa*0.8 {
		// 实际 CPA 低于目标，可以提高出价获取更多流量
		adjustment := 1.0 + t.sensitivity*(1.0-avgCPA/t.targetCPA)*0.5
		if adjustment > 1.5 {
			adjustment = 1.5
		}
		bid := params.TargetCPA * adjustment / (params.HistoricalCVR + 1e-10)
		return clamp(bid, params.MinCPC, params.MaxCPC)
	}

	// 稳定状态，返回基准出价
	bid := params.TargetCPA * params.HistoricalCVR / (params.HistoricalCTR + 1e-10)
	return clamp(bid, params.MinCPC, params.MaxCPC)
}

// TargetROAS 目标 ROAS 竞价策略
type TargetROAS struct {
	targetROAS  float64
	sensitivity float64
	history     []ROASRecord
	mu          sync.Mutex
}

type ROASRecord struct {
	Cost        float64
	ConversionValue float64
	Timestamp   time.Time
}

func NewTargetROAS(targetROAS float64) *TargetROAS {
	return &TargetROAS{
		targetROAS:  targetROAS,
		sensitivity: 0.6,
	}
}

func (t *TargetROAS) Name() string { return "TARGET_ROAS" }
func (t *TargetROAS) RequiresConversionData() bool { return true }
func (t *TargetROAS) RequiresHistory() bool        { return true }

func (t *TargetROAS) RecordRecord(cost, value float64) {
	t.mu.Lock()
	defer t.mu.Unlock()
	t.history = append(t.history, ROASRecord{Cost: cost, ConversionValue: value})
}

func (t *TargetROAS) CalculateBid(params BidParams) float64 {
	t.mu.Lock()
	defer t.mu.Unlock()

	// 计算历史 ROAS
	var totalCost, totalValue float64
	for _, r := range t.history {
		totalCost += r.Cost
		totalValue += r.ConversionValue
	}

	avgROAS := totalValue / (totalCost + 1)

	// 基于目标 ROAS 调整
	roasAdjustment := t.targetROAS / (avgROAS + 1)
	if roasAdjustment > 2.0 {
		roasAdjustment = 2.0
	} else if roasAdjustment < 0.3 {
		roasAdjustment = 0.3
	}

	bid := params.MaxCPC * roasAdjustment
	return clamp(bid, params.MinCPC, params.MaxCPC)
}

// EnhancedCPA 智能优化 CPC (eCPC)
type EnhancedCPA struct {
	baseBid      float64
	convRate     float64
	maxAdjustment float64
}

func NewEnhancedCPA(baseBid, convRate float64) *EnhancedCPA {
	return &EnhancedCPA{
		baseBid:       baseBid,
		convRate:      convRate,
		maxAdjustment: 0.5, // 最大调整 50%
	}
}

func (e *EnhancedCPA) Name() string { return "ENHANCED_CPC" }
func (e *EnhancedCPA) RequiresConversionData() bool { return true }
func (e *EnhancedCPA) RequiresHistory() bool        { return false }

func (e *EnhancedCPA) CalculateBid(params BidParams) float64 {
	// eCPC = baseBid * (1 + conversion_probability * adjustment_factor)
	bid := e.baseBid
	if params.HistoricalCVR > e.convRate {
		// 高转化潜力，提高出价
		factor := (params.HistoricalCVR - e.convRate) / (e.convRate + 1e-10)
		adjustment := factor * e.maxAdjustment
		if adjustment > e.maxAdjustment {
			adjustment = e.maxAdjustment
		}
		bid = e.baseBid * (1 + adjustment)
	} else if params.HistoricalCVR < e.convRate*0.5 {
		// 低转化潜力，降低出价
		adjustment := 1.0 - (e.convRate-params.HistoricalCVR)/e.convRate*0.5
		bid = e.baseBid * adjustment
	}
	return clamp(bid, params.MinCPC, params.MaxCPC)
}

// clamp 范围限制
func clamp(x, min, max float64) float64 {
	if x < min {
		return min
	}
	if x > max {
		return max
	}
	return x
}

// BidOptimizer 竞价优化器：汇总策略管理
type BidOptimizer struct {
	strategies map[string]BidStrategy
	client     *GoogleAdsBiddingClient
}

func NewBidOptimizer(client *GoogleAdsBiddingClient) *BidOptimizer {
	return &BidOptimizer{
		strategies: make(map[string]BidStrategy),
		client:     client,
	}
}

// Register 注册竞价策略
func (b *BidOptimizer) Register(name string, strategy BidStrategy) {
	b.strategies[name] = strategy
}

// OptimizeBid 优化竞价
func (b *BidOptimizer) OptimizeBid(strategyName string, params BidParams) float64 {
	strategy, ok := b.strategies[strategyName]
	if !ok {
		fmt.Printf("strategy %s not found, using manual bidding\n", strategyName)
		return params.MaxCPC * 0.5
	}
	return strategy.CalculateBid(params)
}

// BatchOptimize 批量优化多个关键词的竞价
func (b *BidOptimizer) BatchOptimize(
	ctx context.Context,
	strategyName string,
	keywords []KeywordBidInfo,
) []BidRecommendation {
	var recommendations []BidRecommendation

	for _, kw := range keywords {
		params := BidParams{
			CustomerID:      kw.CustomerID,
			AdGroupID:       kw.AdGroupID,
			Keyword:         kw.Keyword,
			MatchType:       kw.MatchType,
			Position:        kw.Position,
			QualityScore:    kw.QualityScore,
			HistoricalCTR:   kw.HistoricalCTR,
			HistoricalCVR:   kw.HistoricalCVR,
			TargetCPA:       kw.TargetCPA,
			TargetROAS:      kw.TargetROAS,
			MaxCPC:          kw.MaxCPC,
			MinCPC:          kw.MinCPC,
		}
		newBid := b.OptimizeBid(strategyName, params)
		recommendations = append(recommendations, BidRecommendation{
			Keyword:      kw.Keyword,
			MatchType:    kw.MatchType,
			OldBid:       kw.CurrentBid,
			NewBid:       newBid,
			ChangePercent:  calculateChangePct(kw.CurrentBid, newBid),
			Confidence:     kw.QualityScore / 10.0,
			LastUpdated:    time.Now(),
		})
	}
	return recommendations
}

// KeywordBidInfo 关键词竞价信息
type KeywordBidInfo struct {
	CustomerID     string
	AdGroupID      string
	Keyword        string
	MatchType      string
	CurrentBid     float64
	Position       float64
	QualityScore   int
	HistoricalCTR  float64
	HistoricalCVR  float64
	TargetCPA      float64
	TargetROAS     float64
	MaxCPC         float64
	MinCPC         float64
}

// BidRecommendation 竞价推荐结果
type BidRecommendation struct {
	Keyword      string
	MatchType    string
	OldBid       float64
	NewBid       float64
	ChangePercent float64
	Confidence   float64
	LastUpdated  time.Time
}

func calculateChangePct(old, newB float64) float64 {
	if old == 0 {
		return 0
	}
	return (newB - old) / old * 100
}

// BidAdjustment 广告位调整
type BidAdjustment struct {
	Adjustment  float64
	BidModifier float64
	Network     string
	Reason      string
}

// ApplyPositionAdjustment 应用广告位调整
func (b *BidOptimizer) ApplyPositionAdjustment(baseBid float64, targetPosition string) float64 {
	var modifier float64
	switch targetPosition {
	case "TOP":
		modifier = 1.2
	case "ABSOLUTE_TOP":
		modifier = 1.5
	case "PAGE":
		modifier = 0.8
	default:
		modifier = 1.0
	}
	return baseBid * modifier
}

// ApplyQualityScoreAdjustment 基于质量得分调整
func (b *BidOptimizer) ApplyQualityScoreAdjustment(baseBid float64, qualityScore int) float64 {
	// 质量得分越高，所需出价越低
	// Score 10 → 0.5x, Score 5 → 1.0x, Score 1 → 2.0x
	scoreFactor := (11 - qualityScore) / 5.0
	if scoreFactor > 2.0 {
		scoreFactor = 2.0
	} else if scoreFactor < 0.3 {
		scoreFactor = 0.3
	}
	return baseBid * scoreFactor
}

func main() {
	optimizer := BidOptimizer{strategies: make(map[string]BidStrategy)}
	optimizer.Register("MANUAL_CPC", NewManualBidding(2.0))
	optimizer.Register("TARGET_CPA", NewTargetCPABidding(15.0))
	optimizer.Register("TARGET_ROAS", NewTargetROAS(400.0))
	optimizer.Register("ECPC", NewEnhancedCPA(1.5, 0.03))

	// 关键词列表
	keywords := []KeywordBidInfo{
		{
			CustomerID:      "1234567890",
			AdGroupID:       "111",
			Keyword:         "digital marketing",
			MatchType:       "EXACT",
			CurrentBid:      1.50,
			Position:        1.5,
			QualityScore:    8,
			HistoricalCTR:   0.05,
			HistoricalCVR:   0.02,
			TargetCPA:       15.0,
			MaxCPC:          5.0,
			MinCPC:          0.10,
		},
		{
			CustomerID:      "1234567890",
			AdGroupID:       "111",
			Keyword:         "seo services",
			MatchType:       "PHRASE",
			CurrentBid:      2.00,
			Position:        2.0,
			QualityScore:    6,
			HistoricalCTR:   0.03,
			HistoricalCVR:   0.015,
			TargetCPA:       15.0,
			MaxCPC:          8.0,
			MinCPC:          0.10,
		},
	}

	// 批量优化
	recommendations := optimizer.BatchOptimize(context.Background(), "TARGET_CPA", keywords)
	for _, rec := range recommendations {
		direction := "↑"
		if rec.ChangePercent < 0 {
			direction = "↓"
		}
		fmt.Printf("[%s] Keyword: %s (%s) %.2f → %.2f (%s%.1f%%) confidence=%.0f%%\n",
			rec.MatchType, rec.Keyword, direction, rec.OldBid, rec.NewBid,
			direction, rec.ChangePercent, rec.Confidence*100)
	}

	// 质量得分调整示例
	baseBid := 2.0
	highQS := optimizer.ApplyQualityScoreAdjustment(baseBid, 9)
	lowQS := optimizer.ApplyQualityScoreAdjustment(baseBid, 3)
	fmt.Printf("QualityScore 9: bid=%.2f, QualityScore 3: bid=%.2f\n", highQS, lowQS)
}
```

---

### Google 竞价优化的 Go 实现

```go
// Google 竞价优化: 智能出价算法实现
// 覆盖 Target CPA、Target ROAS、Bid Shading
package googlebidding

import (
	"fmt"
	"math"
	"math/rand"
	"sync"
	"time"
)

// ==================== 竞价策略 ====================

// BidStrategy 竞价策略
type BidStrategy string

const (
	StrategyManualCPM      BidStrategy = "MANUAL_CPM"
	StrategyTargetCPA      BidStrategy = "TARGET_CPA"
	StrategyTargetROAS     BidStrategy = "TARGET_ROAS"
	StrategyMaxConversions BidStrategy = "MAXIMIZE_CONVERSIONS"
	StrategyTargetSPD      BidStrategy = "TARGET_Spend"
	StrategyEnhancedCPM    BidStrategy = "ENHANCED_CPM"
)

// ==================== 智能出价引擎 ====================

// SmartBidEngine 智能竞价引擎
type SmartBidEngine struct {
	strategy     BidStrategy
	targetCPA    float64  // Target CPA 目标
	targetROAS   float64  // Target ROAS 目标 (3.0 = 300%)
	beta         float64  // 探索因子
	conversionHistory []Conversion
	rng          *rand.Rand
	mu           sync.RWMutex
}

// Conversion 转化数据
type Conversion struct {
	Value     float64
	Timestamp time.Time
	BidPrice  float64
	ClickID   string
}

// NewSmartBidEngine 创建智能出价引擎
func NewSmartBidEngine(strategy BidStrategy, targetCPA, targetROAS float64) *SmartBidEngine {
	return &SmartBidEngine{
		strategy: strategy,
		targetCPA: math.Max(targetCPA, 1.0),
		targetROAS: math.Max(targetROAS, 1.0),
		beta:     0.95,
		rng:      rand.New(rand.NewSource(time.Now().UnixNano())),
	}
}

// ==================== Target CPA 算法 ====================

// TargetCPABid 计算 Target CPA 出价
func (e *SmartBidEngine) TargetCPABid(
	pCTR, pCVR, historicalCPA float64,
) float64 {
	// Bid = pCTR × pCVR × TargetCPA × β
	bid := pCTR * pCVR * e.targetCPA * e.beta

	// 自适应 β：根据历史 CPA 偏差调整
	adaptiveBeta := e.adaptiveBeta()
	bid *= adaptiveBeta

	// 价格平滑：防止出价波动过大
	bid = e.smoothBid(bid)

	return bid
}

// adaptiveBeta 自适应探索因子
func (e *SmartBidEngine) adaptiveBeta() float64 {
	e.mu.RLock()
	defer e.mu.RUnlock()

	if len(e.conversionHistory) < 10 {
		return e.beta
	}

	// 计算平均实际 CPA
	var totalCost, totalConv float64
	for _, c := range e.conversionHistory[len(e.conversionHistory)-50:] {
		totalCost += c.BidPrice
		if c.Value > 0 {
			totalConv++
		}
	}

	actualCPA := 0.0
	if totalConv > 0 {
		actualCPA = totalCost / totalConv
	}

	// CPA 偏差调整
	cpvRatio := e.targetCPA / actualCPA
	if cpvRatio > 1.1 {
		// 实际 CPA 高于目标 → 降低出价
		return e.beta * 0.9
	}
	if cpvRatio < 0.9 {
		// 实际 CPA 低于目标 → 提高出价
		return e.beta * 1.1
	}
	return e.beta
}

// smoothBid 价格平滑
func (e *SmartBidEngine) smoothBid(bid float64) float64 {
	// 限制单次出价波动不超过 ±50%
	if bid > 0 {
		lastBid := e.getLastBid()
		if lastBid > 0 {
			if bid > lastBid*1.5 {
				bid = lastBid * 1.5
			}
			if bid < lastBid*0.5 {
				bid = lastBid * 0.5
			}
		}
	}
	return bid
}

// ==================== Target ROAS 算法 ====================

// TargetROASBid 计算 Target ROAS 出价
func (e *SmartBidEngine) TargetROASBid(
	pCTR, pCVR, avgOrderValue float64,
) float64 {
	// Bid = pCTR × pCVR × AvgOrderValue × TargetROAS × β
	// 目标: Revenue / Cost = TargetROAS
	// Cost = Revenue / TargetROAS = pCTR × pCVR × AvgOrderValue / TargetROAS
	bid := pCTR * pCVR * avgOrderValue / e.targetROAS * e.beta
	return e.smoothBid(bid)
}

// ==================== Bid Shading ====================

// BidShader 出价衰减器
type BidShader struct {
	historicalBids []float64  // 历史中标/落标价格
	windowSize     int
}

// NewBidShader 创建出价衰减器
func NewBidShader(windowSize int) *BidShader {
	if windowSize == 0 {
		windowSize = 1000
	}
	return &BidShader{
		historicalBids: make([]float64, 0, windowSize),
		windowSize:     windowSize,
	}
}

// Shade 对原始出价进行衰减
func (s *BidShader) Shade(rawBid float64, minFloor float64) float64 {
	if len(s.historicalBids) == 0 {
		return rawBid // 无数据，原出价
	}

	// 计算历史中标价格分布
	sorted := make([]float64, len(s.historicalBids))
	copy(sorted, s.historicalBids)
	sort.Float64s(sorted)

	// P80: 80% 的竞价中，这个价格是中标价
	p80Idx := int(float64(len(sorted)) * 0.80)
	if p80Idx >= len(sorted) {
		p80Idx = len(sorted) - 1
	}
	p80 := sorted[p80Idx]

	// 衰减后出价 = min(rawBid, P80)
	shaded := math.Min(rawBid, p80)

	// 底价保护
	if shaded < minFloor {
		shaded = minFloor
	}

	return shaded
}

// RecordBid 记录竞价结果用于学习
func (s *BidShader) RecordBid(bid float64, won bool) {
	s.historicalBids = append(s.historicalBids, bid)
	if len(s.historicalBids) > s.windowSize {
		s.historicalBids = s.historicalBids[1:]
	}
}

// ==================== 预算 pacing ====================

// BudgetPacer 预算 pacing 控制器
type BudgetPacer struct {
	dailyBudget  float64
	spent       float64
	startTime    time.Time
	duration     time.Duration // 投放时长
	budgetSpend  BudgetSpendType
}

type BudgetSpendType int

const (
	SpendEvenly BudgetSpendType = iota // 均匀消耗
	SpendFrontload                     // 前期快速消耗
	SpendBackload                      // 后期加速消耗
)

// GetCurrentBidMultiplier 获取当前预算调整的出价乘数
func (p *BudgetPacer) GetCurrentBidMultiplier() float64 {
	elapsed := time.Since(p.startTime).Seconds()
	dayFraction := elapsed / (24 * 3600) // 今日已过去的比例

	// 计算目标消耗进度
	var targetFraction float64
	switch p.budgetSpend {
	case SpendEvenly:
		targetFraction = dayFraction
	case SpendFrontload:
		targetFraction = math.Pow(dayFraction, 0.5) // 前期快
	case SpendBackload:
		targetFraction = math.Pow(dayFraction, 2.0) // 后期快
	default:
		targetFraction = dayFraction
	}

	// 计算实际消耗进度
	actualFraction := p.spent / p.dailyBudget

	// 如果实际慢于目标 → 提高出价乘数
	if actualFraction < targetFraction*0.9 {
		return 1.2 // 提高 20% 出价
	}
	if actualFraction > targetFraction*1.1 {
		return 0.8 // 降低 20% 出价
	}
	return 1.0
}

// HasBudget 检查是否还有预算
func (p *BudgetPacer) HasBudget(bid float64) bool {
	remaining := p.dailyBudget - p.spent
	return remaining >= bid && actualFraction < 1.0
}

// ==================== 使用示例 ====================

func main() {
	// 1. Target CPA 引擎
	cpaEngine := NewSmartBidEngine(StrategyTargetCPA, 50.0, 0)
	bid := cpaEngine.TargetCPABid(0.03, 0.05, 60.0)
	fmt.Printf("Target CPA Bid: $%.2f\n", bid)

	// 2. Target ROAS 引擎
	roasEngine := NewSmartBidEngine(StrategyTargetROAS, 0, 3.0)
	bid = roasEngine.TargetROASBid(0.03, 0.05, 200.0)
	fmt.Printf("Target ROAS Bid: $%.2f\n", bid)

	// 3. Bid Shading
	shader := NewBidShader(1000)
	shader.RecordBid(1.5, true)
	shader.RecordBid(2.0, true)
	shader.RecordBid(1.8, false)
	shaded := shader.Shade(3.0, 1.0)
	fmt.Printf("Shaded Bid: $%.2f\n", shaded)

	// 4. Budget Pacing
	pacer := &BudgetPacer{
		dailyBudget: 1000.0,
		spent:      200.0,
		startTime:  time.Now(),
		budgetSpend: SpendEvenly,
	}
	multiplier := pacer.GetCurrentBidMultiplier()
	fmt.Printf("Budget Multiplier: %.2f\n", multiplier)
}
```

---

*今天花 60-90 分钟：深入理解竞价机制，实践优化策略*
*答不出自测题？回去重读对应章节。*
