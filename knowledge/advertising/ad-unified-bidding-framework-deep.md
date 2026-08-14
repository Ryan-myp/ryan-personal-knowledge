# Google/Meta/TikTok/DV360 统一出价框架与智能出价 Agent

> **领域**: 广告投放 / 跨平台出价策略
> **深度**: ⭐⭐⭐⭐⭐ 实战级指南
> **标签**: bidding, cross-platform, agent, multi-armed-bandit, optimization
> **更新时间**: 2026-08-14
> **类型**: deep-dive/bidding

---

## 一、各平台出价系统对比

### 1.1 出价模型全景

```
                    Google Ads            Meta Ads          TikTok Ads         DV360
目标优化          Smart Bidding         Advantage+        Smart Bidding      Bid Surge
                   (10+ 策略)           (自动优化)          (基础智能)         (动态调整)
┌─────────────────────────────────────────────────────────────────────────────────┐
│  手动出价 (Manual Bidding)                                                    │
│  ├── Google: Manual CPC / eCPC                                             │
│  ├── Meta: Manual CPM / CPC                                                │
│  ├── TikTok: Manual CPC / oCPM                                             │
│  └── DV360: Manual CPM / pCPC                                              │
├─────────────────────────────────────────────────────────────────────────────────┤
│  目标成本出价 (Target Cost Bidding)                                            │
│  ├── Google: Target CPA / Target ROAS                                      │
│  ├── Meta: Cost Cap / Bid Cap                                               │
│  ├── TikTok: tCPA / tROAS                                                   │
│  └── DV360: Target CPA / Target ROAS                                        │
├─────────────────────────────────────────────────────────────────────────────────┤
│  最大化转化 (Maximize Conversion)                                              │
│  ├── Google: Maximize Conversions / Conv. Value                              │
│  ├── Meta: Lowest Cost / Advantage+                                         │
│  ├── TikTok: Maximize Conversions                                            │
│  └── DV360: Auto-bidding                                                     │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 出价参数标准化

```
平台出价参数 → 统一模型映射：

Google Ads:
├── strategyType = TARGET_CPA → UnifiedBid.targetCPA
├── strategyType = TARGET_ROAS → UnifiedBid.targetROAS
├── strategyType = MAXIMIZE_CONVERSIONS → UnifiedBid.strategy=MAX_CONV
└── tCpaBidStrategy.targetCpaMicros → UnifiedBid.targetCPA (÷1,000,000)

Meta Ads:
├── bidding_type = COST_CAP → UnifiedBid.targetCPA
├── bidding_type = BID_CAP → UnifiedBid.bidCap
├── optimization_goal = CONVERSIONS → UnifiedBid.strategy=MAX_CONV
└── cost_per_estimate → UnifiedBid.predictedCPA

TikTok Ads:
├── bidding_type = SMART_BID → UnifiedBid.strategy=SMART
├── bid_amount → UnifiedBid.targetCPA
└── estimated_target_cost → UnifiedBid.predictedCPA

DV360:
├── bidStrategy = TARGET_CPM → UnifiedBid.targetCPM
├── bidStrategy = AUTO → UnifiedBid.strategy=ADVANTAGE
└── bid → UnifiedBid.bid
```

---

## 二、统一出价 Agent 架构

### 2.1 系统架构图

```
┌─────────────────────────────────────────────────────────────────────┐
│                     统一出价 Agent 系统                              │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    Agent 控制器                              │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │   │
│  │  │ 状态感知    │  │ 决策引擎    │  │ 执行器      │         │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘         │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              │                                      │
│  ┌───────────────────────────┼───────────────────────────────────┐ │
│  │                    统一数据层                                │ │
│  │  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐  │ │
│  │  │Google     │  │ Meta      │  │ TikTok    │  │ DV360     │  │ │
│  │  │ Connector │  │ Connector │  │ Connector │  │ Connector │  │ │
│  │  └───────────┘  └───────────┘  └───────────┘  └───────────┘  │ │
│  └───────────────────────────────────────────────────────────────┘ │
│                              │                                      │
│  ┌───────────────────────────┼───────────────────────────────────┐ │
│  │                    优化引擎                                  │ │
│  │  ┌───────────────────────────────────────────────────────┐   │ │
│  │  │  Multi-Armed Bandit (MAB)                             │   │ │
│  │  │  ├── ε-Greedy (探索/利用平衡)                         │   │ │
│  │  │  ├── Thompson Sampling (贝叶斯优化)                    │   │ │
│  │  │  └── UCB (Upper Confidence Bound)                     │   │ │
│  │  └───────────────────────────────────────────────────────┘   │ │
│  │  ┌───────────────────────────────────────────────────────┐   │ │
│  │  │  约束优化 (Constrained Optimization)                    │   │ │
│  │  │  ├── 预算约束: Σbudget_i ≤ TotalBudget                 │   │ │
│  │  │  ├── ROAS 约束: ROAS_i ≥ TargetROAS                    │   │ │
│  │  │  └── CPA 约束: CPA_i ≤ TargetCPA                       │   │ │
│  │  └───────────────────────────────────────────────────────┘   │ │
│  └───────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 核心代码实现

```go
package bidding

import (
    "math"
    "sort"
)

// PlatformBid 平台出价配置
type PlatformBid struct {
    Platform     string  `json:"platform"`
    CampaignID   string  `json:"campaign_id"`
    CurrentBid   float64 `json:"current_bid"`
    CurrentCPA   float64 `json:"current_cpa"`
    CurrentROAS  float64 `json:"current_roas"`
    DailySpend   float64 `json:"daily_spend"`
    Impressions  int64   `json:"impressions"`
    Clicks       int64   `json:"clicks"`
    Conversions  int64   `json:"conversions"`
}

// BidAdjustment 出价调整建议
type BidAdjustment struct {
    Platform      string  `json:"platform"`
    CampaignID    string  `json:"campaign_id"`
    OldBid        float64 `json:"old_bid"`
    NewBid        float64 `json:"new_bid"`
    AdjustmentPct float64 `json:"adjustment_percentage"`
    Reason        string  `json:"reason"`
    Confidence    float64 `json:"confidence"` // 0-1
}

// UnifiedBiddingAgent 统一出价 Agent
type UnifiedBiddingAgent struct {
    totalBudget    float64
    targetROAS     float64
    targetCPA      float64
    mabAlpha       float64 // Thompson Sampling 参数
    explorationRate float64 // ε-Greedy 探索率
}

// AdjustBids 执行出价调整
func (a *UnifiedBiddingAgent) AdjustBids(bids []PlatformBid) []BidAdjustment {
    var adjustments []BidAdjustment
    
    // Step 1: 计算各平台效率分数
    efficiency := make(map[string]float64)
    for _, b := range bids {
        if b.CurrentCPA > 0 {
            efficiency[b.Platform] = b.CurrentROAS / (b.CurrentCPA / a.targetCPA)
        } else {
            efficiency[b.Platform] = 0
        }
    }
    
    // Step 2: 按效率排序
    sortedBids := make([]PlatformBid, len(bids))
    copy(sortedBids, bids)
    sort.Slice(sortedBids, func(i, j int) bool {
        return efficiency[sortedBids[i].Platform] > efficiency[sortedBids[j].Platform]
    })
    
    // Step 3: 预算再分配 (Thompson Sampling)
    remainingBudget := a.totalBudget
    for i, b := range sortedBids {
        if remainingBudget <= 0 {
            break
        }
        
        // Thompson Sampling 调整
        mu := efficiency[b.Platform]
        sigma := 1.0 / math.Sqrt(float64(b.Conversions)+1)
        sample := a.thompsonSample(mu, sigma)
        
        // 基于 ROAS 和 CPA 的调整
        var adjustment float64
        if b.CurrentROAS > a.targetROAS*1.2 {
            // ROAS 远超目标，增加预算
            adjustment = 0.15
        } else if b.CurrentROAS < a.targetROAS*0.8 {
            // ROAS 低于目标，减少预算
            adjustment = -0.10
        } else if b.CurrentCPA > a.targetCPA*1.2 {
            // CPA 超标，减少预算
            adjustment = -0.08
        } else {
            // 正常范围，根据效率微调
            adjustment = (sample - 0.5) * 0.1
        }
        
        // 约束检查
        newBid := b.CurrentBid * (1 + adjustment)
        newBid = math.Max(newBid, b.CurrentBid*0.5) // 最低 50%
        newBid = math.Min(newBid, b.CurrentBid*1.5) // 最高 150%
        
        if adjustment != 0 {
            reason := a.buildReason(b, adjustment)
            adjustments = append(adjustments, BidAdjustment{
                Platform:      b.Platform,
                CampaignID:    b.CampaignID,
                OldBid:        b.CurrentBid,
                NewBid:        newBid,
                AdjustmentPct: adjustment * 100,
                Reason:        reason,
                Confidence:    math.Min(1.0, float64(b.Conversions)/50.0),
            })
        }
        
        // 更新剩余预算
        spendDiff := (newBid - b.CurrentBid) * float64(b.DailyImpressions/1000)
        remainingBudget -= spendDiff
    }
    
    return adjustments
}

// thompsonSample Thompson Sampling 采样
func (a *UnifiedBiddingAgent) thompsonSample(mu, sigma float64) float64 {
    // 简化版正态分布采样 (实际应使用更精确的算法)
    // Box-Muller transform
    u1 := math.Random()
    u2 := math.Random()
    z := math.Sqrt(-2*math.Log(u1)) * math.Cos(2*math.Pi*u2)
    return mu + sigma*z
}

func (a *UnifiedBiddingAgent) buildReason(b PlatformBid, adj float64) string {
    if adj > 0.05 {
        return "ROAS 优秀，增加投放"
    } else if adj < -0.05 {
        if b.CurrentCPA > a.targetCPA {
            return "CPA 超标，减少投放"
        }
        return "ROAS 不佳，减少投放"
    }
    return "微调优化"
}
```

---

## 三、Multi-Armed Bandit 出价策略

### 3.1 问题建模

```
将多平台出价优化建模为 Multi-Armed Bandit (MAB) 问题：

┌─────────────────────────────────────────────┐
│          多臂老虎机 (Multi-Armed Bandit)     │
├─────────────────────────────────────────────┤
│  Arms (臂) = 各广告平台                      │
│  Pull (拉臂) = 分配预算到该平台              │
│  Reward (奖励) = ROAS 或 -CPA                │
│  Goal (目标) = 最大化累计奖励 (总 ROAS)      │
└─────────────────────────────────────────────┘

arms = [Google, Meta, TikTok, DV360]
rewards[t] = [ROAS_Google, ROAS_Meta, ROAS_TikTok, ROAS_DV360]
budget_allocation = 从 rewards 中选择最优分配策略
```

### 3.2 三种 MAB 策略对比

```
┌─────────────────────────────────────────────────────────────────────┐
│                    MAB 策略对比                                     │
├──────────────┬───────────────┬───────────────┬──────────────────────┤
│    特性       │  ε-Greedy     │  Thompson     │  UCB                 │
│              │               │  Sampling     │                      │
├──────────────┼───────────────┼───────────────┼──────────────────────┤
│  核心思想     │ ε 概率探索    │ 贝叶斯 posterior│ 上置信界             │
│              │ 1-ε 概率利用  │ 采样最优臂    │ 选择不确定度最高的   │
├──────────────┼───────────────┼───────────────┼──────────────────────┤
│  实现复杂度   │ ⭐ 简单       │ ⭐⭐ 中等     │ ⭐⭐ 中等            │
│  收敛速度     │ 中            │ 快            │ 快                   │
│  探索效率     │ 低 (固定ε)   │ 高 (自适应)   │ 高 (自适应)          │
│  适合场景     │ 数据少        │ 数据量中等    │ 数据量大             │
│  平台适用性   │ 所有平台      │ 所有平台      │ 所有平台             │
├──────────────┼───────────────┼───────────────┼──────────────────────┤
│  推荐指数     │ ⭐⭐          │ ⭐⭐⭐⭐       │ ⭐⭐⭐                │
└──────────────┴───────────────┴───────────────┴──────────────────────┘
```

### 3.3 Thompson Sampling 实现

```python
import numpy as np
from typing import List, Dict

class ThompsonSamplingBidder:
    """
    基于 Thompson Sampling 的跨平台出价优化器
    """
    
    def __init__(self, platforms: List[str], 
                 target_roas: float = 3.0,
                 target_cpa: float = 50.0):
        self.platforms = platforms
        self.target_roas = target_roas
        self.target_cpa = target_cpa
        
        # Beta 分布参数 (success, failure)
        # 初始化为 (1, 1) 表示无先验
        self.alpha = {p: 1.0 for p in platforms}
        self.beta = {p: 1.0 for p in platforms}
        
        # 历史记录
        self.history = {p: {'conversions': [], 'spend': []} for p in platforms}
    
    def update(self, platform: str, conversions: int, spend: float):
        """更新 Beta 分布参数"""
        self.alpha[platform] += conversions
        self.beta[platform] += max(1, int(spend / 50))  # 归一化 spend
    
    def sample(self, platform: str) -> float:
        """从 Beta 分布采样"""
        return np.random.beta(self.alpha[platform], self.beta[platform])
    
    def get_bid_adjustments(self) -> Dict[str, float]:
        """
        计算各平台的出价调整比例
        
        Returns:
            {platform: adjustment_percentage}
            例如: {'google': 0.15, 'meta': -0.08, 'tiktok': 0.0, 'dv360': 0.12}
        """
        adjustments = {}
        
        # 对每个平台进行 Thompson Sampling
        samples = {p: self.sample(p) for p in self.platforms}
        
        # 归一化样本值
        total_sample = sum(samples.values())
        normalized = {p: s/total_sample for p, s in samples.items()}
        
        # 计算调整比例 (相对于均匀分配)
        for p in self.platforms:
            # 如果该平台的归一化比例 > 1/N，则增加预算
            # 否则减少
            baseline = 1.0 / len(self.platforms)
            diff = normalized[p] - baseline
            # 缩放因子，避免过度调整
            adjustments[p] = diff * 2.0
        
        return adjustments
    
    def get_recommendations(self) -> List[Dict]:
        """生成出价建议"""
        adjustments = self.get_bid_adjustments()
        
        recommendations = []
        for platform, adj in adjustments.items():
            if abs(adj) > 0.05:  # 只返回有显著变化的
                direction = "增加" if adj > 0 else "减少"
                confidence = min(1.0, (self.alpha[platform] + self.beta[platform]) / 100)
                recommendations.append({
                    'platform': platform,
                    'action': f'{direction} {abs(adj)*100:.1f}% 预算',
                    'confidence': f'{confidence*100:.0f}%',
                    'reason': self._get_reason(platform, adj)
                })
        
        return recommendations
    
    def _get_reason(self, platform: str, adj: float) -> str:
        """解释调整原因"""
        history = self.history[platform]
        if not history['conversions']:
            return "数据不足，探索阶段"
        
        avg_roas = sum(history['conversions']) / max(1, sum(history['spend'])) * 100
        if adj > 0:
            return f"ROAS {avg_roas:.1f}% 优于目标，增加投入"
        else:
            return f"ROAS {avg_roas:.1f}% 低于目标，减少投入"
```

---

## 四、约束优化

### 4.1 约束定义

```
出价优化的约束条件：

硬约束 (必须满足):
├── 总预算约束: Σ(budget_i) ≤ TotalBudget
├── 最低 CPA 约束: CPA_i ≤ TargetCPA × 1.5 (允许 50% 超支)
├── 最高出价约束: bid_i ≤ CurrentBid × 2.0 (单次调整不超过 100%)
└── 最低出价约束: bid_i ≥ CurrentBid × 0.5

软约束 (尽量满足):
├── 目标 ROAS: ROAS_i ≥ TargetROAS
├── 预算均衡: |budget_i - budget_j| ≤ 20% (避免过度集中)
└── 探索要求: 每个平台至少分配 10% 预算 (保持数据收集)
```

### 4.2 约束求解

```python
from scipy.optimize import linprog
import numpy as np

def optimize_budget_allocation(
    platforms: List[str],
    current_bids: Dict[str, float],
    current_roas: Dict[str, float],
    total_budget: float,
    target_roas: float
) -> Dict[str, float]:
    """
    在约束条件下优化预算分配
    
    目标: 最大化 Σ(roas_i × budget_i)
    约束:
      - Σ(budget_i) = total_budget
      - budget_i ≥ 0
      - roas_i ≥ target_roas (软约束，通过 penalty 处理)
    """
    n = len(platforms)
    
    # 目标函数系数 (最大化 → 取负)
    c = [-current_roas[p] for p in platforms]
    
    # 等式约束: Σ(budget_i) = total_budget
    A_eq = [[1] * n]
    b_eq = [total_budget]
    
    # 边界: 0 ≤ budget_i ≤ total_budget
    bounds = [(0, total_budget) for _ in range(n)]
    
    # 求解线性规划
    result = linprog(c, A_eq=A_eq, b_eq=b_eq, bounds=bounds, method='highs')
    
    if result.success:
        return dict(zip(platforms, result.x))
    else:
        # 回退: 按 ROAS 比例分配
        total_roas = sum(current_roas.values())
        return {p: total_budget * (current_roas[p] / total_roas) 
                for p in platforms}
```

---

## 五、生产部署

### 5.1 调度策略

```
出价优化调度：

实时层 (Real-time):
├── 频率: 每分钟
├── 范围: 单 campaign 内出价微调
├── 约束: ±10% 调整幅度
└── 工具: 各平台原生出价 API

近实时层 (Near-real-time):
├── 频率: 每小时
├── 范围: 跨 campaign 预算重分配
├── 约束: ±20% 调整幅度
└── 工具: 统一出价 Agent

批量层 (Batch):
├── 频率: 每日
├── 范围: 全平台出价策略调整
├── 约束: ±50% 调整幅度
└── 工具: Thompson Sampling + 约束优化

人工审核层 (Human-in-the-loop):
├── 触发条件: 异常检测、重大策略变更
├── 审核人: 投放经理
└── 执行: 确认后自动下发
```

### 5.2 安全机制

```
出价安全护栏：

1. 熔断机制
   ├── 如果 ROAS < 目标 × 0.5 → 暂停该 campaign
   ├── 如果 CPA > 目标 × 2.0 → 暂停该 campaign
   └── 如果单日花费 > 预算 × 1.5 → 暂停

2. 突变检测
   ├── 如果出价调整 > 50% → 需要人工确认
   ├── 如果预算变化 > 30% → 发送告警
   └── 如果 ROAS 骤降 > 20% → 自动回滚

3. 回滚机制
   ├── 保留最近 24h 的出价历史
   ├── 检测到异常时自动回滚到上一合理出价
   └── 回滚后通知运营人员
```

---

## 六、自测题

### Q1: 为什么 Thompson Sampling 比 ε-Greedy 更适合跨平台出价优化？

<details>
<summary>点击查看答案</summary>

核心区别：

**ε-Greedy**:
- 以固定概率 ε 探索随机平台
- 探索效率低（无论数据多少，ε 不变）
- 收敛慢（需要大量探索才能找到最优）

**Thompson Sampling**:
- 根据各平台的 posterior 分布自动调整探索/利用比例
- 数据少的平台 → posterior 方差大 → 更容易被采样（更多探索）
- 数据多的平台 → posterior 方差小 → 更稳定（更多利用）
- 自适应探索，收敛更快

在出价优化场景中：
- 新平台（如 TikTok）数据少，需要更多探索
- 成熟平台（如 Google）数据充足，可以更多利用
- Thompson Sampling 天然适配这种需求
</details>

### Q2: 出价 Agent 的熔断机制什么时候应该触发？

<details>
<summary>点击查看答案</summary>

触发条件：
1. **ROAS 骤降**: 当前 ROAS < 目标 ROAS × 0.5，且持续 2 小时
2. **CPA 超标**: 当前 CPA > 目标 CPA × 2.0，且持续 4 小时
3. **预算超支**: 单日花费 > 日预算 × 1.5
4. **异常波动**: 5 分钟内花费变化 > 50%
5. **转化率异常**: CVR 较前 7 天均值下降 > 30%

熔断后：
- 自动暂停受影响 campaign
- 发送告警通知投放经理
- 记录断点，便于后续分析
- 等待人工确认或自动恢复
</details>

---

*本文档提供了跨平台统一出价 Agent 的完整设计和实现参考。*
