# 广告系统架构深度：归因/反作弊/流量分配

> 广告归因建模 / 反作弊系统 / 流量分配策略 / 竞价优化 / 实时竞价系统

---

## 第一部分：入门引导（5 分钟速览）

### 广告系统核心流程

```
用户浏览 → 广告请求 → 竞价 → 广告选择 → 展示 → 点击 → 转化
                    ↑        ↑
                 竞价引擎   广告排序
```

### 广告平台关键指标

| 指标 | 公式 | 说明 |
|------|------|------|
| CPM | 收入 / 展示 × 1000 | 千次展示收入 |
| CPC | 收入 / 点击 | 单次点击成本 |
| CPA | 收入 / 转化 | 单次转化成本 |
| eCPM | 预估点击率 × 预估出价 | 千次展示预估收入 |

---

## 第二部分：广告归因建模

### 2.1 归因模型

```
Last Click: 最后一次点击获得 100%  credit
First Click: 第一次点击获得 100% credit
Linear: 所有触点平分 credit
Time Decay: 越靠近转化的触点权重越高
Position Based: 首尾各 40%，中间平分 20%
```

### 2.2 Go 实现归因引擎

```go
package attribution

import (
    "math"
)

type Touchpoint struct {
    Channel  string
    Timestamp time.Time
    Cost     float64
    Converted bool
}

type AttributionModel interface {
    Calculate(touchpoints []Touchpoint) map[string]float64
}

// LastClick 归因模型
type LastClickModel struct{}

func (lc *LastClickModel) Calculate(touchpoints []Touchpoint) map[string]float64 {
    attribution := make(map[string]float64)
    
    // 找到最后一个点击
    lastTouchpoint := touchpoints[len(touchpoints)-1]
    attribution[lastTouchpoint.Channel] = 1.0
    
    return attribution
}

// Linear 归因模型
type LinearModel struct{}

func (lm *LinearModel) Calculate(touchpoints []Touchpoint) map[string]float64 {
    attribution := make(map[string]float64)
    credit := 1.0 / float64(len(touchpoints))
    
    for _, tp := range touchpoints {
        attribution[tp.Channel] += credit
    }
    
    return attribution
}

// TimeDecay 归因模型
type TimeDecayModel struct {
    halfLife time.Duration
}

func (td *TimeDecayModel) Calculate(touchpoints []Touchpoint) map[string]float64 {
    attribution := make(map[string]float64)
    totalWeight := 0.0
    
    // 计算每个触点的权重
    weights := make([]float64, len(touchpoints))
    for i, tp := range touchpoints {
        decay := math.Pow(0.5, float64(td.halfLife.Seconds()/time.Since(tp.Timestamp).Seconds()))
        weights[i] = decay
        totalWeight += decay
    }
    
    // 归一化
    for i, tp := range touchpoints {
        attribution[tp.Channel] = weights[i] / totalWeight
    }
    
    return attribution
}
```

### 2.3 多触点归因

```go
type MultiTouchAttribution struct {
    model AttributionModel
}

func (mta *MultiTouchAttribution) Analyze(conversion Conversion) map[string]float64 {
    touchpoints := mta.getTouchpoints(conversion)
    
    // 应用归因模型
    attribution := mta.model.Calculate(touchpoints)
    
    // 计算每个渠道的贡献
    results := make(map[string]float64)
    for channel, credit := range attribution {
        results[channel] = conversion.Revenue * credit
    }
    
    return results
}
```

---

## 第三部分：反作弊系统

### 3.1 作弊类型

```
1. 点击欺诈：机器人点击广告
2. 展示欺诈：虚假展示
3. 转化欺诈：伪造转化事件
4. 设备农场：大量设备模拟
5. IP 池：代理 IP 轮换
```

### 3.2 Go 实现反作弊引擎

```go
package antifraud

import (
    "time"
)

type FraudDetector struct {
    rules    []FraudRule
    blacklist map[string]bool
}

type FraudRule interface {
    Evaluate(event FraudEvent) bool
}

type FraudEvent struct {
    EventType   string // click, impression, conversion
    UserID      string
    DeviceID    string
    IPAddress   string
    Timestamp   time.Time
    Location    Location
    Metadata    map[string]interface{}
}

type Location struct {
    Latitude  float64
    Longitude float64
    Country   string
}

// 频率检测规则
type RateLimitRule struct {
    MaxEvents int
    Window    time.Duration
}

func (r *RateLimitRule) Evaluate(event FraudEvent) bool {
    // 检查用户在时间窗口内的事件频率
    events := r.getRecentEvents(event.UserID, r.Window)
    return len(events) > r.MaxEvents
}

// 地理位置异常检测
type GeoAnomalyRule struct {
    MaxSpeed float64 // km/h
}

func (g *GeoAnomalyRule) Evaluate(event FraudEvent) bool {
    if event.EventType != "click" {
        return false
    }
    
    // 检查是否有不可能的地理位置跳跃
    prevEvents := g.getPreviousEvents(event.UserID)
    for _, prev := range prevEvents {
        distance := g.calculateDistance(prev.Location, event.Location)
        timeDiff := event.Timestamp.Sub(prev.Timestamp).Hours()
        
        if timeDiff > 0 {
            speed := distance / timeDiff
            if speed > g.MaxSpeed {
                return true
            }
        }
    }
    
    return false
}

func (g *GeoAnomalyRule) calculateDistance(loc1, loc2 Location) float64 {
    // Haversine 公式计算距离
    R := 6371.0 // 地球半径 km
    dLat := (loc2.Latitude - loc1.Latitude) * math.Pi / 180
    dLon := (loc2.Longitude - loc1.Longitude) * math.Pi / 180
    
    a := math.Sin(dLat/2)*math.Sin(dLat/2) +
        math.Cos(loc1.Latitude*math.Pi/180)*math.Cos(loc2.Latitude*math.Pi/180)*
        math.Sin(dLon/2)*math.Sin(dLon/2)
    
    c := 2 * math.Atan2(math.Sqrt(a), math.Sqrt(1-a))
    return R * c
}

// 设备指纹检测
type DeviceFingerprintRule struct {
    knownFraudDevices map[string]bool
}

func (d *DeviceFingerprintRule) Evaluate(event FraudEvent) bool {
    // 检查设备是否在黑名单中
    if d.knownFraudDevices[event.DeviceID] {
        return true
    }
    
    // 检查设备指纹相似度
    fingerprint := d.generateFingerprint(event)
    similarDevices := d.findSimilarDevices(fingerprint)
    
    return len(similarDevices) > 10 // 超过 10 个相似设备判定为作弊
}
```

---

## 第四部分：流量分配策略

### 4.1 流量分配算法

```go
type TrafficAllocator struct {
    campaigns map[string]*Campaign
    budgetTracker *BudgetTracker
}

type Campaign struct {
    ID       string
    Budget   float64
    Spent    float64
    Priority int
    Target   map[string]interface{}
}

type BudgetTracker struct {
    dailyBudgets map[string]float64
    spentToday   map[string]float64
}

func (ta *TrafficAllocator) Allocate(imp Impressions) map[string]float64 {
    // 1. 过滤预算不足的 campaign
    eligible := ta.filterByBudget(imp.Target)
    
    // 2. 按优先级和出价排序
    sort.Slice(eligible, func(i, j int) bool {
        return eligible[i].Priority > eligible[j].Priority ||
               (eligible[i].Priority == eligible[j].Priority &&
                eligible[i].Budget > eligible[j].Budget)
    })
    
    // 3. 分配流量
    allocation := make(map[string]float64)
    for _, campaign := range eligible {
        allocation[campaign.ID] = ta.calculateAllocation(campaign, imp)
    }
    
    return allocation
}

func (ta *TrafficAllocator) calculateAllocation(campaign *Campaign, imp Impressions) float64 {
    // 基于CTR预估和出价计算分配比例
    ctr := ta.predictCTR(campaign, imp)
    bid := campaign.Budget
    
    score := ctr * bid
    
    // 考虑预算约束
    remainingBudget := campaign.Budget - campaign.Spent
    if remainingBudget <= 0 {
        return 0
    }
    
    return score * (remainingBudget / campaign.Budget)
}
```

### 4.2 竞价优化

```go
type BidOptimizer struct {
    model *BidModel
}

type BidModel struct {
    ctrModel *CTRModel
    cvrModel *CVRModel
}

func (bo *BidOptimizer) OptimizeBid(imp Impressions, baseBid float64) float64 {
    // 1. 预测 CTR
    ctr := bo.model.ctrModel.Predict(imp)
    
    // 2. 预测 CVR
    cvr := bo.model.cvrModel.Predict(imp)
    
    // 3. 计算 eCPM
    eCPM := ctr * cvr * baseBid
    
    // 4. 优化出价
    optimizedBid := bo.adjustBid(eCPM, baseBid)
    
    return optimizedBid
}

func (bo *BidOptimizer) adjustBid(eCPM, baseBid float64) float64 {
    // 基于历史数据调整出价
    historicalWinRate := bo.getHistoricalWinRate(eCPM)
    
    if historicalWinRate < 0.5 {
        // 赢率低，提高出价
        return baseBid * 1.2
    } else if historicalWinRate > 0.8 {
        // 赢率高，降低出价
        return baseBid * 0.8
    }
    
    return baseBid
}
```

---

## 第五部分：自测题

### 问题 1
广告归因中为什么 Last Click 模型不够准确？

<details>
<summary>查看答案</summary>

1. **忽略早期触点**：忽略了用户决策路径上的其他渠道
2. **渠道冲突**：导致渠道间争夺 credit
3. **长期影响**：品牌广告的效果被低估
4. **解决方案**：使用多触点归因模型
5. **Go 实现**：使用 TimeDecay 模型更合理

</details>

### 问题 2
反作弊系统如何平衡误判率和漏判率？

<details>
<summary>查看答案</summary>

1. **阈值调优**：根据业务需求调整阈值
2. **多层检测**：规则引擎 + 机器学习
3. **人工审核**：可疑案例人工复核
4. **反馈循环**：根据审核结果优化模型
5. **Go 实现**：使用加权评分系统

</details>

### 问题 3
流量分配中如何平衡品牌广告和效果广告？

<details>
<summary>查看答案</summary>

1. **优先级设置**：品牌广告高优先级
2. **预算隔离**：不同类型广告独立预算
3. **时段分配**：不同时段侧重不同
4. **效果监控**：实时监控投放效果
5. **Go 实现**：使用 TrafficAllocator 动态分配

</details>

---

*本文档基于广告系统架构原理整理，结合广告平台实战场景。*