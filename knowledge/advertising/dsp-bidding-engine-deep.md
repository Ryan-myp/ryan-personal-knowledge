# 广告系统DSP竞价引擎深度解析

> 深入DSP（需求方平台）竞价引擎：实时竞价、出价策略、质量分计算、反作弊机制。
> 包含真实生产环境DSP系统架构设计与实现。
> 适用对象：广告系统工程师、竞价引擎开发者、架构师

---

## 1. DSP 竞价引擎架构

### 1.1 整体架构

```
DSP 竞价引擎架构：

┌─────────────────────────────────────────────────────────────┐
│                    DSP 竞价引擎                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  入口层 (Gateway)                                            │
│  ├── 接收ADX竞价请求                                          │
│  ├── 参数校验                                                  │
│  └── 请求分发                                                  │
│                                                             │
│  特征工程层 (Feature Engine)                                  │
│  ├── 用户画像特征                                              │
│  ├── 上下文特征                                                │
│  ├── 创意特征                                                  │
│  └── 实时特征缓存                                              │
│                                                             │
│  出价策略层 (Bidding Strategy)                                │
│  ├── 基础出价计算                                              │
│  ├── 质量分调整                                                │
│  ├── 预算控制                                                  │
│  └── 出价封顶                                                  │
│                                                             │
│  决策层 (Decision Engine)                                     │
│  ├── 竞价决策                                                  │
│  ├── 创意选择                                                  │
│  └── 返回响应                                                  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 Go 实现DSP核心架构

```go
// dsp_engine.go

package dsp

import (
    "context"
    "sync"
    "time"
)

type DSPBidder struct {
    config        *Config
    featureEngine *FeatureEngine
    strategy      *BiddingStrategy
    decision      *DecisionEngine
}

type Config struct {
    BidTimeout       time.Duration
    MaxBid           float64
    BudgetPerDay     float64
    TargetCPA        float64
    FeatureCacheTTL  time.Duration
}

func NewDSPBidder(config *Config) *DSPBidder {
    return &DSPBidder{
        config:        config,
        featureEngine: NewFeatureEngine(config.FeatureCacheTTL),
        strategy:      NewBiddingStrategy(config.TargetCPA),
        decision:      NewDecisionEngine(),
    }
}

type BidRequest struct {
    ImpressionID string
    User         UserFeature
    Context      ContextFeature
    AdSlot       AdSlotFeature
    Timestamp    int64
}

type BidResponse struct {
    ImpressionID string
    BidPrice     float64
    CreativeID   string
    Reason       string
    Timestamp    int64
}

func (dsp *DSPBidder) ProcessBid(ctx context.Context, req *BidRequest) (*BidResponse, error) {
    // 1. 特征工程
    features := dsp.featureEngine.Extract(ctx, req)
    
    // 2. 出价策略
    bidPrice := dsp.strategy.CalculateBid(features)
    
    // 3. 竞价决策
    response, reason := dsp.decision.Decide(features, bidPrice)
    
    return &BidResponse{
        ImpressionID: req.ImpressionID,
        BidPrice:     response.BidPrice,
        CreativeID:   response.CreativeID,
        Reason:       reason,
        Timestamp:    time.Now().Unix(),
    }, nil
}
```

---

## 2. 特征工程

### 2.1 用户画像特征

```
用户画像特征：

1. 基础属性
   ├── 年龄
   ├── 性别
   ├── 地域
   └── 设备类型

2. 行为特征
   ├── 兴趣标签
   ├── 购买历史
   ├── 浏览偏好
   └── 活跃时段

3. 价值特征
   ├── LTV预估
   ├── CTR预估
   └── CVR预估
```

### 2.2 Go 实现特征工程

```go
// feature_engine.go

package dsp

import (
    "context"
    "sync"
)

type UserFeature struct {
    UserID      string
    Age         int
    Gender      string
    Location    string
    Device      string
    Interests   []string
    PurchaseVal float64
    CTREst      float64
    CVREst      float64
}

type ContextFeature struct {
    SiteID     string
    AppID      string
    AdSlotID   string
    Hour       int
    DayOfWeek  int
    Network    string
}

type FeatureEngine struct {
    userCache   sync.Map
    contextCache sync.Map
    ttl         time.Duration
}

func NewFeatureEngine(ttl time.Duration) *FeatureEngine {
    return &FeatureEngine{
        ttl: ttl,
    }
}

func (fe *FeatureEngine) Extract(ctx context.Context, req *BidRequest) *Features {
    // 获取用户特征
    userFeature := fe.getUserFeature(ctx, req.User.UserID)
    
    // 获取上下文特征
    contextFeature := fe.getContextFeature(ctx, req.Context)
    
    return &Features{
        User:        userFeature,
        Context:     contextFeature,
        BidPrice:    req.BidPrice,
        Timestamp:   req.Timestamp,
    }
}

func (fe *FeatureEngine) getUserFeature(ctx context.Context, userID string) *UserFeature {
    if v, ok := fe.userCache.Load(userID); ok {
        return v.(*UserFeature)
    }
    // 从DB获取
    user := fe.fetchFromDB(ctx, userID)
    fe.userCache.Store(userID, user)
    return user
}

func (fe *FeatureEngine) getContextFeature(ctx context.Context, ctxFeature ContextFeature) *ContextFeature {
    key := ctxFeature.SiteID + "_" + ctxFeature.AppID
    if v, ok := fe.contextCache.Load(key); ok {
        return v.(*ContextFeature)
    }
    ctxFeat := fe.fetchFromDB(ctx, key)
    fe.contextCache.Store(key, ctxFeat)
    return ctxFeat
}
```

---

## 3. 出价策略

### 3.1 出价算法

```
DSP出价算法：

1. 基础出价
   BaseBid = pCTR × pCVR × TargetCPA

2. 质量分调整
   QualityBid = BaseBid × QualityScore

3. 预算控制
   FinalBid = QualityBid × BudgetFactor

4. 出价封顶
   ResultBid = min(FinalBid, MaxBid)
```

### 3.2 Go 实现出价策略

```go
// bidding_strategy.go

package dsp

import "math"

type BiddingStrategy struct {
    targetCPA  float64
    maxBid     float64
    budgetPool float64
    spent      float64
    mu         sync.Mutex
}

func NewBiddingStrategy(targetCPA float64) *BiddingStrategy {
    return &BiddingStrategy{
        targetCPA: targetCPA,
        maxBid:    10.0, // 默认最大出价
    }
}

func (bs *BiddingStrategy) CalculateBid(features *Features) float64 {
    // 基础出价
    baseBid := features.User.CTREst * features.User.CVREst * bs.targetCPA
    
    // 质量分调整
    qualityScore := bs.calculateQualityScore(features)
    qualityBid := baseBid * qualityScore
    
    // 预算控制
    budgetFactor := bs.calculateBudgetFactor()
    finalBid := qualityBid * budgetFactor
    
    // 出价封顶
    return math.Min(finalBid, bs.maxBid)
}

func (bs *BiddingStrategy) calculateQualityScore(features *Features) float64 {
    // 质量分基于用户价值和上下文质量
    userValue := features.User.PurchaseVal / 100.0
    contextQuality := bs.calculateContextQuality(features.Context)
    
    return math.Min(1.0, (userValue+contextQuality)/2.0)
}

func (bs *BiddingStrategy) calculateContextQuality(ctx ContextFeature) float64 {
    // 基于时段、网络质量等计算
    hourBonus := 1.0
    if ctx.Hour >= 20 || ctx.Hour <= 6 {
        hourBonus = 1.2 // 晚间流量质量高
    }
    
    networkQuality := 1.0
    if ctx.Network == "wifi" {
        networkQuality = 1.1
    }
    
    return hourBonus * networkQuality
}

func (bs *BiddingStrategy) calculateBudgetFactor() float64 {
    bs.mu.Lock()
    defer bs.mu.Unlock()
    
    if bs.budgetPool <= 0 {
        return 0.0
    }
    
    remaining := bs.budgetPool - bs.spent
    if remaining <= 0 {
        return 0.0
    }
    
    // 预算消耗比例越高，出价越保守
    burnRate := bs.spent / bs.budgetPool
    return math.Max(0.1, 1.0-burnRate)
}

func (bs *BiddingStrategy) RecordSpend(amount float64) {
    bs.mu.Lock()
    defer bs.mu.Unlock()
    bs.spent += amount
}
```

---

## 4. 反作弊机制

### 4.1 作弊检测策略

```
广告作弊检测策略：

1. 点击作弊检测
   ├── 点击频率异常
   ├── IP集中度异常
   └── 设备指纹异常

2. 展示作弊检测
   ├── 不可见广告检测
   ├── 堆叠广告检测
   └── 自动刷新检测

3. 转化作弊检测
   ├── 虚假点击转化
   ├── 刷单检测
   └── 机器人转化检测
```

### 4.2 Go 实现反作弊

```go
// anti_fraud.go

package dsp

import (
    "sync"
    "time"
)

type AntiFraudDetector struct {
    clickPatterns  sync.Map
    ipPatterns     sync.Map
    devicePatterns sync.Map
}

func NewAntiFraudDetector() *AntiFraudDetector {
    return &AntiFraudDetector{}
}

type FraudResult struct {
    IsFraud    bool
    Reason     string
    Score      float64
}

func (afd *AntiFraudDetector) DetectClickFraud(ip, deviceID string) *FraudResult {
    var scores []float64
    var reasons []string
    
    // 点击频率检测
    clickScore, clickReason := afd.checkClickFrequency(ip)
    scores = append(scores, clickScore)
    if clickReason != "" {
        reasons = append(reasons, clickReason)
    }
    
    // IP异常检测
    ipScore, ipReason := afd.checkIPAnomaly(ip)
    scores = append(scores, ipScore)
    if ipReason != "" {
        reasons = append(reasons, ipReason)
    }
    
    // 设备异常检测
    deviceScore, deviceReason := afd.checkDeviceAnomaly(deviceID)
    scores = append(scores, deviceScore)
    if deviceReason != "" {
        reasons = append(reasons, deviceReason)
    }
    
    // 综合评分
    avgScore := 0.0
    for _, s := range scores {
        avgScore += s
    }
    avgScore /= float64(len(scores))
    
    return &FraudResult{
        IsFraud: avgScore > 0.7,
        Reason:  joinReasons(reasons),
        Score:   avgScore,
    }
}

func (afd *AntiFraudDetector) checkClickFrequency(ip string) (float64, string) {
    if v, ok := afd.clickPatterns.Load(ip); ok {
        pattern := v.(*ClickPattern)
        if pattern.ClickCount > 100 && pattern.TimeWindow < time.Minute {
            return 1.0, "click_fraud_detected"
        }
    }
    return 0.0, ""
}

func (afd *AntiFraudDetector) checkIPAnomaly(ip string) (float64, string) {
    if v, ok := afd.ipPatterns.Load(ip); ok {
        count := v.(int)
        if count > 1000 {
            return 0.8, "ip_abuse_detected"
        }
    }
    return 0.0, ""
}

func (afd *AntiFraudDetector) checkDeviceAnomaly(deviceID string) (float64, string) {
    if v, ok := afd.devicePatterns.Load(deviceID); ok {
        count := v.(int)
        if count > 500 {
            return 0.9, "device_fraud_detected"
        }
    }
    return 0.0, ""
}
```

---

## 5. 竞价优化

### 5.1 优化策略

```
DSP竞价优化策略：

1. 出价优化
   ├── 基于历史数据调整
   ├── 实时反馈学习
   └── 多目标优化

2. 定向优化
   ├── 人群包优化
   ├── 时段优化
   └── 地域优化

3. 创意优化
   ├── 素材A/B测试
   └── 自动创意生成
```

### 5.2 Go 实现竞价优化

```go
// bidding_optimizer.go

package dsp

import (
    "sync"
)

type BiddingOptimizer struct {
    historicalData map[string][]float64
    learningRate   float64
    mu             sync.Mutex
}

func NewBiddingOptimizer(learningRate float64) *BiddingOptimizer {
    return &BiddingOptimizer{
        historicalData: make(map[string][]float64),
        learningRate:   learningRate,
    }
}

func (bo *BiddingOptimizer) OptimizeBid(
    impressionID string,
    currentBid float64,
    conversion float64,
) float64 {
    bo.mu.Lock()
    defer bo.mu.Unlock()
    
    // 记录历史数据
    bo.historicalData[impressionID] = append(
        bo.historicalData[impressionID],
        conversion,
    )
    
    // 计算平均转化率
    avgConversion := bo.calculateAvgConversion(impressionID)
    
    // 调整出价
    if conversion > avgConversion {
        return currentBid * (1 + bo.learningRate)
    } else if conversion < avgConversion {
        return currentBid * (1 - bo.learningRate)
    }
    
    return currentBid
}

func (bo *BiddingOptimizer) calculateAvgConversion(impressionID string) float64 {
    data := bo.historicalData[impressionID]
    if len(data) == 0 {
        return 0.01
    }
    
    sum := 0.0
    for _, v := range data {
        sum += v
    }
    return sum / float64(len(data))
}
```

---

## 6. 总结

### 6.1 核心原理回顾

| 模块 | 核心机制 |
|------|----------|
| 特征工程 | 用户画像+上下文特征 |
| 出价策略 | pCTR×pCVR×TargetCPA |
| 反作弊 | 多维度异常检测 |
| 竞价优化 | 历史数据学习调整 |

### 6.2 最佳实践

- [ ] 实时特征更新
- [ ] 多维度反作弊
- [ ] 预算智能分配
- [ ] 持续优化出价

---

*最后更新：2026-08-11*
*作者：Ryan*
