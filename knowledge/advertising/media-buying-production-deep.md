# 媒体采买生产实践深度实现 - 从投放到优化闭环

> **版本**: v2.0  
> **日期**: 2026-08-13  
> **作者**: Ryan  
> **分类**: 广告/采买  
> **代码密度**: 30%

---

## 一、采买流程架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                    媒体采买全流程                                     │
│                                                                     │
│  规划 ──▶ 策略 ──▶ 投放 ──▶ 监控 ──▶ 优化 ──▶ 归因                  │
│   │       │       │       │       │       │                         │
│   ▼       ▼       ▼       ▼       ▼       ▼                         │
│ 预算    出价    频控    数据    ROI   复盘                              │
│ 拆解    策略    频次    看板    提升   迭代                            │
│                                                                     │
│  时间轴 (天):                                                        │
│  Day 1-3:   预算分配 + 媒体选择                                     │
│  Day 4-7:   小预算测试 + A/B 测试                                   │
│  Day 8-14:  放量 + 频控调整                                         │
│  Day 15+:   持续优化 + 归因分析                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 二、预算分配算法

```go
// buying/budget.go
package buying

import "sort"

// BudgetAllocator 预算分配器
type BudgetAllocator struct {
    mediaPlans map[string]*MediaPlan
}

type MediaPlan struct {
    ID           string
    Name         string
    Platform     string // facebook/google/tiktok
    TotalBudget  float64
    TargetROAS   float64
    BidStrategy  string // cpc/cpm/ocpc
}

// Allocate 分配预算
func (a *BudgetAllocator) Allocate(plans []MediaPlan, totalBudget float64) map[string]float64 {
    // 1. 按预期 ROAS 排序
    sort.Slice(plans, func(i, j int) bool {
        return plans[i].TargetROAS > plans[j].TargetROAS
    })
    
    result := make(map[string]float64)
    remaining := totalBudget
    
    for i, plan := range plans {
        if i == len(plans)-1 {
            result[plan.ID] = remaining
        } else {
            // 按 ROAS 权重分配
            weight := plan.TargetROAS / a.totalROAS(plans)
            allocation := totalBudget * weight
            allocation = math.Min(allocation, plan.TotalBudget)
            result[plan.ID] = allocation
            remaining -= allocation
        }
    }
    
    return result
}
```

---

## 三、频控策略

```go
// buying/frequency.go
package buying

import (
    "context"
    "github.com/redis/go-redis/v9"
    "time"
)

// FrequencyController 频控控制器
type FrequencyController struct {
    rdb *redis.Client
}

// CheckFrequency 检查是否超频
func (c *FrequencyController) CheckFrequency(ctx context.Context, userID uint64, adID uint64, maxFreq int) (bool, int) {
    key := fmt.Sprintf("freq:%d:%d", userID, adID)
    
    // 滑动窗口: 过去 24 小时曝光次数
    windowKey := fmt.Sprintf("freq_win:%d:%d", userID, adID)
    pipe := c.rdb.Pipeline()
    pipe.ZAdd(ctx, windowKey, redis.Z{Score: float64(time.Now().Unix()), Member: time.Now().UnixNano()})
    pipe.ZRemRangeByScore(ctx, windowKey, "0", fmt.Sprintf("%d", time.Now().Unix()-86400))
    pipe.Expire(ctx, windowKey, 48*time.Hour)
    pipe.ZCard(ctx, windowKey)
    
    results, err := pipe.Exec(ctx)
    if err != nil {
        return true, 0 // 超频
    }
    
    count := results[len(results)-1].(*redis.IntCmd).Val()
    if int(count) >= maxFreq {
        return true, int(count)
    }
    return false, int(count)
}
```

---

## 四、ROI 监控

```go
// buying/roi_monitor.go
package buying

import "time"

// ROI 计算
type ROIMonitor struct {
    adSpend float64
    revenue float64
}

func (m *ROIMonitor) Calculate() float64 {
    if m.adSpend == 0 {
        return 0
    }
    return m.revenue / m.adSpend
}

// DailyReport 日报
type DailyReport struct {
    Date          time.Time
    Spend         float64
    Impressions   int64
    Clicks        int64
    Conversions   int64
    Revenue       float64
    CTR           float64
    CVR           float64
    CPC           float64
    CPA           float64
    ROAS          float64
}

// GenerateReport 生成报告
func GenerateReport(day time.Time) *DailyReport {
    // TODO: 从数据仓库查询
    return &DailyReport{
        Date:        day,
        Spend:       10000.0,
        Impressions: 1000000,
        Clicks:      5000,
        Conversions: 100,
        Revenue:     5000.0,
        CTR:         0.005,
        CVR:         0.02,
        CPC:         2.0,
        CPA:         100.0,
        ROAS:        0.5,
    }
}
```

---

## 五、A/B 测试

```python
# buying/ab_test.py
import numpy as np
from scipy import stats

class ABTest:
    """广告 A/B 测试"""
    
    def __init__(self, variant_a_clicks, variant_a_impressions,
                 variant_b_clicks, variant_b_impressions):
        self.variant_a = (variant_a_clicks, variant_a_impressions)
        self.variant_b = (variant_b_clicks, variant_b_impressions)
    
    def calculate_p_value(self):
        """计算 p 值"""
        n1, k1 = self.variant_a
        n2, k2 = self.variant_b
        
        p1 = k1 / n1
        p2 = k2 / n2
        
        # 合并比例
        p_pool = (k1 + k2) / (n1 + n2)
        
        # Z 统计量
        se = np.sqrt(p_pool * (1 - p_pool) * (1/n1 + 1/n2))
        z = (p2 - p1) / se
        
        # p 值 (双尾)
        p_value = 2 * (1 - stats.norm.cdf(abs(z)))
        return p_value, z
    
    def is_significant(self, alpha=0.05):
        p_value, _ = self.calculate_p_value()
        return p_value < alpha

# 示例
test = ABTest(
    variant_a_clicks=100, variant_a_impressions=10000,
    variant_b_clicks=150, variant_b_impressions=10000
)
p_value, z = test.calculate_p_value()
print(f"p_value={p_value:.4f}, z={z:.2f}")
if test.is_significant():
    print("实验显著，B 版本胜出")
```

---

## 六、自测题

1. **频控为什么用滑动窗口？**
   - 比固定窗口更平滑，避免窗口切换时的突增突降

2. **A/B 测试 p 值 < 0.05 意味着什么？**
   - 有 95% 把握认为差异是真实的，不是随机波动

