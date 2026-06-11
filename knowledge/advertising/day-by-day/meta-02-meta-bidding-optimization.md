# Meta Ads — 竞价策略与深度优化

> 创建日期: 2026-06-09
> 作者: Ryan

---

## 第一部分：Meta 竞价机制深度解析

### 1.1 Meta 竞价机制

```
Meta 采用的是实时竞价 (RTB) 系统
与 Google 的广义第二价格拍卖类似，但有核心差异

┌────────────────────────────────────────────────────────┐
│              Meta 竞价流程                              │
│                                                        │
│  1. 用户刷 Facebook/Instagram Feed                      │
│       │                                                 │
│       ▼                                                 │
│  2. Meta 召回候选广告                                    │
│     - 基于用户画像                                       │
│     - 基于历史行为                                       │
│     - 基于广告定向                                       │
│       │                                                 │
│       ▼                                                 │
│  3. 计算 Total Value                                     │
│     Total Value = Bid × Estimated Action Rate × Bid Modifier │
│                                                        │
│     关键因素:                                            │
│     ├── Bid: 你愿意支付的金额                             │
│     ├── EAR (Estimated Action Rate): 预估行动率          │
│     │   └── P(action=conversion | user, ad)            │
│     └── Bid Modifier: 出价调整因子                       │
│         └── 考虑用户偏好 (Facebook 偏好视频广告等)        │
│       │                                                 │
│       ▼                                                 │
│  4. 排序并展示                                           │
│     - Total Value 最高的广告获胜                          │
└────────────────────────────────────────────────────────┘
```

### 1.2 Meta 竞价策略详解

```
┌────────────────────────────────────────────────────────────┐
│                  Meta 竞价策略                              │
│                                                            │
│  手动竞价 (Manual Bidding):                                 │
│  ├── Cost Cap: 目标每次行动费用上限                          │
│  ├── Bid Cap: 最高出价限制                                  │
│  ├── Lowest Bid: 最低成本竞价（默认）                       │
│  └── Enhanced CPC: 增强型 CPC                              │
│                                                            │
│  智能竞价 (Advantage+ Bidding):                             │
│  ├── Advantage+ Campaign Budget: 广告系列级别预算优化         │
│  ├── Cost Per Action Limit: 行动费用上限                    │
│  └── Lowest Cost: 尽可能获取转化                            │
│                                                            │
│  特殊竞价:                                                  │
│  ├── High Bid: 单条广告最高出价                             │
│  ├── Value Bid: 价值最大化出价                              │
│  └── Delivery Method: 投放方式                              │
│      ├── Standard: 标准投放 (均匀分布)                      │
│      └── Accelerated: 加速投放 (尽快消耗)                   │
└────────────────────────────────────────────────────────────┘
```

### 1.3 Estimated Action Rate (EAR) 源码分析

```python
# meta_ads/early.py
# Estimated Action Rate (预估行动率)

class EarlyEstimator:
    """
    Estimated Action Rate (EAR) 预估器
    
    EAR = P(user performs desired_action | user sees ad)
    
    影响因素:
    ├── 用户画像 (age, gender, location, interests)
    ├── 广告特征 (creative type, copy, CTA)
    ├── 用户行为历史 (past conversions, engagement)
    └── 广告位 (feed, stories, reels, audience_network)
    """
    
    def __init__(self, model_version: str = 'v3.2'):
        self.model_version = model_version
    
    def predict_early(self, user_features: dict, ad_features: dict,
                      placement: str) -> float:
        """
        预测 EAR
        
        流程:
        1. 提取用户特征
        2. 提取广告特征
        3. 输入模型
        4. 输出转化概率
        
        参数:
        ├── user_features: 用户特征字典
        ├── ad_features: 广告特征字典
        └── placement: 广告位 (feed/stories/reels/...)
        
        返回:
        └── 转化概率 (0-1)
        """
        # 用户特征
        user_age = user_features.get('age', 25)
        user_gender = user_features.get('gender', 2)
        user_interests = user_features.get('interests', [])
        user_past_conversions = user_features.get('past_conversions', 0)
        
        # 广告特征
        ad_type = ad_features.get('type', 'image')  # image/video/text
        ad_relevance_score = ad_features.get('relevance_score', 0.5)
        ad_ctr_history = ad_features.get('ctr_history', 0.02)
        
        # 广告位
        placement_factor = self._get_placement_factor(placement)
        
        # 简化版模型 (实际是深度学习模型)
        base_prob = self._base_probability(
            user_age, user_gender, user_interests, user_past_conversions
        )
        
        # 应用调整
        ear = base_prob * ad_relevance_score * placement_factor
        
        return max(0.0, min(1.0, ear))
    
    def _base_probability(self, age: int, gender: int, 
                          interests: list, past_conversions: int) -> float:
        """基础转化概率"""
        # 基于历史数据的平均转化概率
        base = 0.01  # 1% 平均转化率
        
        # 年龄调整
        if 18 <= age <= 24:
            base *= 1.2
        elif 25 <= age <= 34:
            base *= 1.5  # 购买力最强
        elif 45 <= age <= 54:
            base *= 1.1
        
        # 过去转化调整
        if past_conversions > 0:
            base *= (1 + 0.1 * past_conversions)
        
        return base
    
    def _get_placement_factor(self, placement: str) -> float:
        """获取广告位调整因子"""
        placement_factors = {
            'feed': 1.0,
            'stories': 0.8,
            'reels': 0.9,
            'audience_network': 0.6,
            'instagram_feed': 1.1,
            'instagram_stories': 0.9,
            'instagram_reels': 1.0,
        }
        return placement_factors.get(placement, 0.8)


class BidCalculator:
    """
    Meta 出价计算器
    
    Total Value = Bid × EAR × Bid Modifier
    
    优化目标:
    - 在预算约束下最大化 Total Value
    - 平衡 bid 和 EAR
    """
    
    def calculate_optimal_bid(self, target_cpa: float,
                               early: float,
                               user_preference_modifier: float) -> float:
        """
        计算最优出价
        
        目标: 在目标 CPA 约束下最大化 total value
        
        公式:
        optimal_bid = target_cpa × EAR × user_preference_modifier
        
        参数:
        ├── target_cpa: 目标每次行动费用
        ├── early: 预估行动率
        └── user_preference_modifier: 用户偏好调整
            (用户偏好此广告位/格式时 > 1)
        
        返回:
        └── bid_amount (最小额货币)
        """
        bid = target_cpa * early * user_preference_modifier
        
        return max(0, bid)
```

---

## 第二部分：Meta 竞价优化源码

### 2.1 Cost Cap 竞价

```python
# meta_ads/bidding/cost_cap.py
# Cost Cap 竞价

class CostCapBidder:
    """
    Cost Cap 竞价器
    
    工作原理:
    1. 设定目标每次行动费用 (cost cap)
    2. 系统自动调整出价以接近目标
    3. 允许短期波动 (在目标 ±15%)
    
    优势:
    ├── 保证长期平均 CPA 接近目标
    ├── 允许短期波动以获取机会
    └── 自动适应竞争环境变化
    """
    
    def __init__(self, cost_cap: float, tolerance: float = 0.15):
        self.cost_cap = cost_cap
        self.tolerance = tolerance
        self.actual_cpa = None
        self.conversion_count = 0
        self.total_spend = 0
    
    def calculate_bid(self, early: float, 
                      competition_level: str = 'MEDIUM') -> float:
        """
        计算出价
        
        参数:
        ├── early: 预估行动率
        └── competition_level: 竞争程度
        
        返回:
        └── bid_amount
        """
        if self.actual_cpa is None or self.actual_cpa < self.cost_cap * (1 - self.tolerance):
            # CPA 低于目标，提高出价获取更多流量
            bid = self.cost_cap * early * 1.1
        elif self.actual_cpa > self.cost_cap * (1 + self.tolerance):
            # CPA 高于目标，降低出价控制成本
            bid = self.cost_cap * early * 0.9
        else:
            # CPA 在目标范围内，保持稳定
            bid = self.cost_cap * early
        
        return max(0, bid)
    
    def update(self, spend: float, conversions: int):
        """更新实际 CPA"""
        self.total_spend += spend
        self.conversion_count += conversions
        
        if self.conversion_count > 0:
            self.actual_cpa = self.total_spend / self.conversion_count
```

### 2.2 Advantage+ 预算优化

```python
# meta_ads/bidding/advantage_budget.py
# Advantage+ Campaign Budget 优化

class AdvantageBudgetOptimizer:
    """
    Advantage+ Campaign Budget 优化器
    
    工作原理:
    1. 在广告组级别分配预算
    2. 根据表现自动调整预算分配
    3. 优先分配给表现好的广告组
    
    优化策略:
    ├── 高 ROI 广告组: 增加预算
    ├── 低 ROI 广告组: 减少预算
    └── 新广告组: 给予学习预算
    """
    
    def __init__(self, total_budget: float, learning_budget: float = 50.0):
        self.total_budget = total_budget
        self.learning_budget = learning_budget
        self.ad_group_budgets = {}
        self.ad_group_performance = {}
    
    def optimize_budget(self, ad_groups: list) -> dict:
        """
        优化预算分配
        
        流程:
        1. 获取广告组表现
        2. 计算每个广告组的 ROI
        3. 按 ROI 排序
        4. 分配预算
        
        参数:
        └── ad_groups: 广告组列表
        
        返回:
        └── 预算分配字典
        """
        budgets = {}
        
        # 计算每个广告组的 ROI
        roi_scores = {}
        for ag in ad_groups:
            ag_id = ag['id']
            spend = ag.get('spend', 0)
            revenue = ag.get('revenue', 0)
            
            roi = revenue / max(spend, 1)
            roi_scores[ag_id] = roi
        
        # 按 ROI 排序
        sorted_ag_ids = sorted(roi_scores.keys(), key=lambda x: roi_scores[x], reverse=True)
        
        # 分配预算
        remaining_budget = self.total_budget
        
        for i, ag_id in enumerate(sorted_ag_ids):
            if i == 0:
                # 最佳广告组获得最大预算
                budgets[ag_id] = min(remaining_budget * 0.5, remaining_budget)
            elif i == 1:
                # 第二广告组获得 30%
                budgets[ag_id] = min(remaining_budget * 0.3, remaining_budget - budgets.get(sorted_ag_ids[0], 0))
            else:
                # 其他广告组平分剩余
                remaining_ag = len(sorted_ag_ids) - 2
                if remaining_ag > 0:
                    per_ag = remaining_budget / remaining_ag
                    budgets[ag_id] = min(per_ag, remaining_budget - sum(budgets.values()))
        
        return budgets
```

---

## 第三部分：广告优化实战

### 3.1 受众优化

```python
# meta_ads/optimization/audience.py
# 受众优化

class AudienceOptimizer:
    """
    受众优化器
    
    策略:
    ├── Lookalike Audiences: 基于转化用户创建相似受众
    ├── Custom Audiences: 基于转化用户创建再营销受众
    └── Broad Targeting: 宽定向 + Advantage+ 受众
    """
    
    def find_best_audience(self, conversion_data: list) -> dict:
        """
        找出最佳受众
        
        基于:
        ├── CPA (每次行动费用)
        ├── CTR (点击率)
        ├── ROAS (广告支出回报率)
        └── Scale (规模)
        """
        best_audience = None
        best_score = 0
        
        for audience in conversion_data:
            # 综合评分
            cpa_score = 1.0 / max(audience['cpa'], 1)
            ctr_score = audience['ctr'] * 100
            roas_score = audience['roas'] / 10
            
            # 权重
            score = cpa_score * 0.4 + ctr_score * 0.3 + roas_score * 0.3
            
            if score > best_score:
                best_score = score
                best_audience = audience
        
        return best_audience
```

### 3.2 创意优化

```python
# meta_ads/optimization/creative.py
# 创意优化

class CreativeOptimizer:
    """
    创意优化器
    
    测试维度:
    ├── 格式 (视频 vs 图片 vs carousel)
    ├── 时长 (视频长度)
    ├── 文案 (文案 A/B 测试)
    ├── CTA (行动号召)
    └── 视觉 (颜色、人物、场景)
    """
    
    def recommend_creative(self, audience_type: str, 
                           objective: str) -> dict:
        """
        推荐最佳创意格式
        
        基于:
        ├── 受众类型
        ├── 广告目标
        └── 历史表现
        """
        recommendations = {
            'shopping': {
                'primary_format': 'carousel',
                'secondary_format': 'video',
                'preferred_creative': 'product_catalog',
                'copy_tone': 'product_focused',
                'cta': 'shop_now',
            },
            'brand': {
                'primary_format': 'video',
                'secondary_format': 'image',
                'preferred_creative': 'brand_story',
                'copy_tone': 'emotional',
                'cta': 'learn_more',
            },
            'lead': {
                'primary_format': 'image',
                'secondary_format': 'video',
                'preferred_creative': 'lead_form',
                'copy_tone': 'value_proposition',
                'cta': 'sign_up',
            },
        }
        
        return recommendations.get(objective, recommendations['brand'])
```

---

## 第四部分：自测

### 问题 1
Meta 竞价中，Total Value 的公式是什么？
<details>
<summary>查看答案</summary>

- Total Value = Bid × EAR × Bid Modifier
- EAR = Estimated Action Rate (预估行动率)
- Bid Modifier 考虑用户偏好
</details>

### 问题 2
Cost Cap 竞价的优势是什么？
<details>
<summary>查看答案</summary>

- 保证长期平均 CPA 接近目标
- 允许短期波动以获取机会
- 自动适应竞争环境变化
</details>

### 问题 3
Advantage+ Campaign Budget 的核心优化策略是什么？
<details>
<summary>查看答案</summary>

- 根据 ROI 在广告组间分配预算
- 高 ROI 广告组获得更多预算
- 低 ROI 广告组减少预算
</details>

---

## 第五部分：动手验证

### 5.1 受众优化

```python
from meta_ads.optimization.audience import AudienceOptimizer

optimizer = AudienceOptimizer()
conversion_data = [
    {'name': 'Lookalike 1%', 'cpa': 10, 'ctr': 0.03, 'roas': 5.0, 'scale': 10000},
    {'name': 'Custom Audience', 'cpa': 15, 'ctr': 0.02, 'roas': 4.0, 'scale': 5000},
    {'name': 'Broad', 'cpa': 20, 'ctr': 0.01, 'roas': 3.0, 'scale': 50000},
]

best = optimizer.find_best_audience(conversion_data)
print(f"最佳受众: {best['name']}")
print(f"CPA: ${best['cpa']}")
print(f"ROAS: {best['roas']}")
```

---

*今天花 60-90 分钟：深入理解 Meta 竞价机制，实践优化策略*
*答不出自测题？回去重读对应章节。*

---

### Meta 竞价的 Go 实现

```go
package metabidding

import (
	"fmt"
	"math"
	"sync"
	"time"
)

type BidType string
const (
	BidTypeCPC BidType = "CPC"
	BidTypeCPM BidType = "CPM"
	BidTypeOCPM BidType = "OCPM"
)

type Bidder struct {
	bidType   BidType
	targetCPA float64
	targetROAS float64
	history   []BidRecord
	mu        sync.RWMutex
}

type BidRecord struct {
	AdID     string
	Clicked  bool
	Converted bool
	BidPrice float64
	Value    float64
	Time     time.Time
}

func NewBidder(bt BidType, targetCPA, targetROAS float64) *Bidder {
	return &Bidder{bidType: bt, targetCPA: targetCPA, targetROAS: targetROAS}
}

func (b *Bidder) CalculateBid(ctr, cvr float64, bidCap float64) float64 {
	switch b.bidType {
	case BidTypeCPC:
		return math.Min(ctr*100, bidCap)
	case BidTypeCPM:
		return math.Min(ctr*cvr*1000, bidCap)
	case BidTypeOCPM:
		pCTR := ctr
		pCVR := cvr
		expectedCPA := pCTR * pCVR * 1000
		if expectedCPA > 0 {
			return math.Min(b.targetCPA*expectedCPA, bidCap)
		}
		return 1.0
	default:
		return 1.0
	}
}

func (b *Bidder) AddRecord(r *BidRecord) {
	b.mu.Lock()
	defer b.mu.Unlock()
	b.history = append(b.history, *r)
}

func (b *Bidder) GetMetrics() (int, float64, float64, float64) {
	b.mu.RLock()
	defer b.mu.RUnlock()
	impressions, clicks, convs, revenue := 0, 0, 0, 0.0
	for _, r := range b.history {
		if r.Clicked { clicks++ }
		if r.Converted { convs++; revenue += r.Value }
	}
	// 假设 impression = clicks * 3 (简化)
	impressions = clicks * 3
	ctr := 0.0
	if impressions > 0 { ctr = float64(clicks) / float64(impressions) }
	cpa := 0.0
	if convs > 0 { cpa = float64(clicks) * 1.0 / float64(convs) }
	roas := 0.0
	if clicks > 0 { roas = revenue / float64(clicks) }
	return impressions, ctr, cpa, roas
}

func main() {
	bidder := NewBidder(BidTypeOCPM, 50.0, 3.0)
	bidder.AddRecord(&BidRecord{AdID: "ad1", Clicked: true, BidPrice: 1.5})
	bidder.AddRecord(&BidRecord{AdID: "ad1", Clicked: true, Converted: true, Value: 150, BidPrice: 1.2})
	imp, ctr, cpa, roas := bidder.GetMetrics()
	fmt.Printf("Imp: %d, CTR: %.4f, CPA: %.2f, ROAS: %.2f\n", imp, ctr, cpa, roas)
	fmt.Printf("Bid: $%.4f\n", bidder.CalculateBid(0.03, 0.05, 5.0))
}
