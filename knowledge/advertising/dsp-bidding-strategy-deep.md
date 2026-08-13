# DSP竞价策略深度实现 - 资深专家

## 一、竞价策略架构

### 1.1 核心策略模型

```go
// 竞价策略接口
type BiddingStrategy interface {
    // 计算 bids
    CalculateBid(ctx context.Context, request *BidRequest) (float64, error)
    
    // 策略类型
    Type() StrategyType
    
    // 参数配置
    Configure(params map[string]interface{}) error
}

type StrategyType int

const (
    // 固定出价
    FixedBid StrategyType = iota
    // 动态出价
    DynamicBid
    // 智能出价
    IntelligentBid
    // 强化学习出价
    RLBIdd
)

// 固定出价策略
type FixedBiddingStrategy struct {
    bid float64
}

func (s *FixedBiddingStrategy) CalculateBid(ctx context.Context, request *BidRequest) (float64, error) {
    return s.bid, nil
}

// 动态出价策略
type DynamicBiddingStrategy struct {
    budget       float64
    targetCPA    float64
    maxBid       float64
    minBid       float64
}

func (s *DynamicBiddingStrategy) CalculateBid(ctx context.Context, request *BidRequest) (float64, error) {
    // 1. 获取预估CTR
    pCTR := s.getPCTR(request)
    
    // 2. 获取预估CVR
    pCVR := s.getCVR(request)
    
    // 3. 计算期望转化成本
    expectedCPA := pCTR * pCVR * s.maxBid
    
    // 4. 调整出价
    bid := s.targetCPA * (expectedCPA / s.targetCPA)
    
    // 5. 限制范围
    bid = math.Max(s.minBid, math.Min(bid, s.maxBid))
    
    return bid, nil
}
```

### 1.2 预算控制

```go
// 预算控制器
type BudgetController struct {
    totalBudget   float64
    spentBudget   float64
    dailyBudget   float64
    pacingRate    float64
}

// 计算可出价金额
func (bc *BudgetController) GetAvailableBudget() float64 {
    elapsed := time.Since(bc.startTime).Seconds() / 86400
    remaining := bc.dailyBudget - bc.spentBudget
    
    // 理想 pacing: 均匀消耗
    idealSpent := bc.dailyBudget * elapsed
    if remaining < idealSpent*0.8 {
        // 加速消耗
        bc.pacingRate = 1.2
    } else if remaining > idealSpent*1.2 {
        // 减速消耗
        bc.pacingRate = 0.8
    }
    
    return remaining * bc.pacingRate
}

// 更新花费
func (bc *BudgetController) UpdateSpent(amount float64) {
    bc.spentBudget += amount
}
```

## 二、智能出价

### 2.1 pCTR/pCVR预估

```go
// 预估模型
type PredictionModel struct {
    ctrModel *MLModel
    cvrModel *MLModel
}

// 获取pCTR
func (pm *PredictionModel) GetPCTR(request *BidRequest) float64 {
    features := pm.extractFeatures(request)
    return pm.ctrModel.Predict(features)
}

// 获取pCVR
func (pm *PredictionModel) GetPCVR(request *BidRequest, bid float64) float64 {
    features := pm.extractFeatures(request)
    features["bid"] = bid
    
    return pm.cvrModel.Predict(features)
}

// 特征提取
func (pm *PredictionModel) extractFeatures(request *BidRequest) map[string]float64 {
    features := make(map[string]float64)
    
    // 用户特征
    features["user_age"] = float64(request.User.Age)
    features["user_gender"] = float64(request.User.Gender)
    
    // 上下文特征
    features["hour_of_day"] = float64(request.Timestamp.Hour())
    features["day_of_week"] = float64(request.Timestamp.Weekday())
    
    // 广告特征
    features["ad_category"] = float64(request.Ad.Category)
    features["ad_age"] = float64(request.Ad.Age)
    
    // 设备特征
    features["device_type"] = float64(request.Device.Type)
    features["os_version"] = float64(request.Device.OSVersion)
    
    return features
}
```

### 2.2 强化学习出价

```go
// Q-Learning出价器
type QLearningBidding struct {
    qTable      map[string]map[float64]float64
    lr          float64    // 学习率
    gamma       float64    // 折扣因子
    epsilon     float64    // 探索率
    stateDim    int
}

// 状态表示
type State struct {
    BudgetRemain float64
    TimeElapsed  float64
    WinRate      float64
}

// 计算Q值
func (ql *QLearningBidding) GetQValue(state State, action float64) float64 {
    stateKey := state.toString()
    if _, ok := ql.qTable[stateKey]; !ok {
        ql.qTable[stateKey] = make(map[float64]float64)
    }
    return ql.qTable[stateKey][action]
}

// 选择动作
func (ql *QLearningBidding) SelectAction(state State) float64 {
    if rand.Float64() < ql.epsilon {
        // 探索: 随机选择
        return ql.randomAction()
    }
    
    // 利用: 选择最优动作
    stateKey := state.toString()
    maxQ := math.Inf(-1)
    bestAction := 0.0
    
    for action, q := range ql.qTable[stateKey] {
        if q > maxQ {
            maxQ = q
            bestAction = action
        }
    }
    
    return bestAction
}

// 更新Q值
func (ql *QLearningBidding) UpdateQValue(state State, action float64, reward float64) {
    stateKey := state.toString()
    nextQ := ql.GetNextQValue(state, action)
    
    currentQ := ql.GetQValue(state, action)
    newQ := currentQ + ql.lr*(reward+ql.gamma*nextQ-currentQ)
    
    ql.qTable[stateKey][action] = newQ
}
```

## 三、竞价优化

### 3.1 实时优化

```go
// 实时优化器
type RealtimeOptimizer struct {
    windowSize int
    history    []BidRecord
}

type BidRecord struct {
    Timestamp time.Time
    Bid       float64
    Won       bool
    Cost      float64
    Conversions int
}

// 调整出价策略
func (ro *RealtimeOptimizer) AdjustStrategy(historical []BidRecord) StrategyParams {
    // 1. 计算转化率
    wins := 0
    conversions := 0
    for _, record := range historical {
        if record.Won {
            wins++
            conversions += record.Conversions
        }
    }
    
    winRate := float64(wins) / float64(len(historical))
    cvr := float64(conversions) / float64(wins)
    
    // 2. 计算平均出价
    totalBid := 0.0
    for _, record := range historical {
        totalBid += record.Bid
    }
    avgBid := totalBid / float64(len(historical))
    
    // 3. 生成优化建议
    return StrategyParams{
        TargetWinRate: 0.3,
        TargetCVR:     cvr,
        MaxBid:        avgBid * 1.2,
        MinBid:        avgBid * 0.8,
    }
}
```

### 3.2 A/B测试

```go
// A/B测试框架
type ABTest struct {
    experimentID string
    variants     map[string]*Variant
    trafficSplit map[string]float64
}

type Variant struct {
    ID          string
    Strategy    BiddingStrategy
    Weight      float64
    Stats       TestStats
}

type TestStats struct {
    Impressions int
    Clicks      int
    Conversions int
    Spend       float64
}

// 分配流量
func (ab *ABTest) GetVariant(userID string) *Variant {
    hash := hashUserID(userID)
    threshold := float64(hash%10000) / 10000
    
    cumulative := 0.0
    for name, variant := range ab.variants {
        cumulative += ab.trafficSplit[name]
        if threshold < cumulative {
            return variant
        }
    }
    
    return ab.variants["control"]
}

// 记录结果
func (ab *ABTest) RecordResult(variantID string, result BidResult) {
    variant := ab.variants[variantID]
    variant.Stats.Impressions++
    variant.Stats.Spend += result.Cost
    variant.Stats.Conversions += result.Conversions
}
```

## 四、面试高频题

### Q1: 如何设计竞价策略？

```
A:
1. 固定出价: 简单直接，适合新手
2. 动态出价: 根据pCTR/pCVR调整
3. 智能出价: 基于机器学习预测
4. 强化学习: 实时自我优化
```

### Q2: 如何控制预算？

```
A:
1. 设置日预算上限
2. 实时Pacing控制
3. 动态调整出价
4. 异常监控告警
```

## 五、自测题

1. 解释动态出价的计算公式
2. 如何实现强化学习出价？
3. A/B测试如何设计？

---

## 参考文档

- [竞价引擎核心](./bidding-engine-core-deep.md)
- [RTA匹配策略](../advertising/rta-matching-optimization-deep.md)
- [SSP网关架构](../advertising/ssp-gateway-design-deep.md)
