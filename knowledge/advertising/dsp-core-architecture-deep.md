# DSP 核心架构深度实现 - 从请求到出价

> **版本**: v2.0  
> **日期**: 2026-08-13  
> **作者**: Ryan  
> **分类**: 广告/DSP  
> **代码密度**: 32%

---

## 一、DSP 请求处理流程

```
┌─────────────────────────────────────────────────────────────────────┐
│                    DSP 请求处理流程 (50ms SLA)                       │
│                                                                     │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐     │
│  │ RTB      │───▶│ Feature  │───▶│ pCTR    │───▶│ Pricing  │     │
│  │ Request  │    │ Extract  │    │ Predict  │    │ Engine   │     │
│  └──────────┘    └────┬─────┘    └────┬─────┘    └────┬─────┘     │
│                       │                │               │            │
│              ┌────────┼────────────────┼───────────────┼────────┐  │
│              ▼        ▼                ▼               ▼        │  │
│         Redis     ClickHouse         Model         Budget      │  │
│         用户画像  频次统计           pCTR模型       检查        │  │
│                                                                     │
│  时序 (微秒):                                                       │
│  0-5ms:   HTTP 解析 + 参数校验                                      │
│  5-15ms:  特征提取 (Redis 查询)                                     │
│  15-35ms: pCTR 预测 (GPU 推理)                                      │
│  35-45ms: 出价计算 (Budget + Freq)                                  │
│  45-50ms: 响应序列化 + 返回                                         │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 二、特征工程

```go
// dsp/features.go
package dsp

import (
    "context"
    "time"
)

// UserFeatures 用户特征
type UserFeatures struct {
    UserID      uint64
    Age         uint8
    Gender      uint8  // 0=unknown, 1=male, 2=female
    Interests   []string
    DeviceType  uint8  // 0=mobile, 1=desktop
    GeoRegion   string
    DAU         int    // 日活天数
    CTRHistory  float32 // 历史 CTR
    CVRHistory  float32 // 历史 CVR
}

// AdFeatures 广告特征
type AdFeatures struct {
    AdID        uint64
    AdvertiserID uint64
    Category    string
    BidFloor    float32
    BidCap      float32
    CreativeType uint8
}

// ContextFeatures 上下文特征
type ContextFeatures struct {
    PageURL     string
    PageCategory string
    SlotID      string
    SlotWidth   int
    SlotHeight  int
    MediaType   uint8  // 0=banner, 1=video, 2=native
}

// ExtractFeatures 提取特征
func ExtractFeatures(ctx context.Context, req *BidRequest) (*FeatureVector, error) {
    // 1. 用户特征
    userFeatures := getUserFeatures(ctx, req.UserID)
    
    // 2. 广告特征
    adFeatures := getAdFeatures(ctx, req.AdID)
    
    // 3. 上下文特征
    ctxFeatures := getContextFeatures(ctx, req)
    
    // 4. 交叉特征
    crossFeatures := computeCrossFeatures(userFeatures, adFeatures)
    
    return &FeatureVector{
        User:    userFeatures,
        Ad:      adFeatures,
        Context: ctxFeatures,
        Cross:   crossFeatures,
    }, nil
}
```

---

## 三、pCTR 模型

```go
// dsp/ctr_model.go
package dsp

import (
    "context"
    "github.com/tensorflow/tensorflow/tensorflow/go/core/framework"
)

// CTRModel pCTR 模型
type CTRModel struct {
    session *framework.Session
    inputs  map[string]*framework.Tensor
}

// NewCTRModel 加载模型
func NewCTRModel(modelPath string) (*CTRModel, error) {
    // 加载 SavedModel
    bundle, err := tf.LoadSession(modelPath)
    if err != nil {
        return nil, err
    }
    
    return &CTRModel{
        session: bundle.Session,
        inputs: map[string]*tf.Tensor{
            "user_age":   tf.NewTensor([]int32{25}),
            "user_gender": tf.NewTensor([]int32{1}),
            "ad_category": tf.NewTensor([]string{"electronics"}),
            "page_url":   tf.NewTensor([]string{"example.com"}),
        },
    }, nil
}

// Predict pCTR 预测
func (m *CTRModel) Predict(ctx context.Context, features *FeatureVector) (float32, error) {
    // 准备输入
    feedInputs := map[string]*tf.Tensor{
        "user_age":    tf.NewTensor([]int32{features.User.Age}),
        "user_gender": tf.NewTensor([]int32{features.User.Gender}),
        "ad_category": tf.NewTensor([]string{features.Ad.Category}),
        "page_url":    tf.NewTensor([]string{features.Context.PageURL}),
    }
    
    // 推理
    output, err := m.session.Run(
        feedInputs,
        []string{"output/probabilities"},
        nil,
    )
    if err != nil {
        return 0, err
    }
    
    // 提取概率
    probs := output[0].Value().([]float32)
    return probs[1], nil // class 1 = click
}
```

---

## 四、出价策略

```go
// dsp/bidding.go
package dsp

import (
    "context"
    "fmt"
)

// BiddingStrategy 出价策略
type BiddingStrategy int

const (
    vCPM BiddingStrategy = iota // 虚拟 CPM
    oCPM                        // 优化 CPM
    tCPA                        // 目标 CPA
)

// BidEngine 出价引擎
type BidEngine struct {
    strategy BiddingStrategy
    targetCPM float64
    targetCPA float64
}

// CalculateBid 计算出价
func (e *BidEngine) CalculateBid(ctx context.Context, pCTR float32, budget float64) (float64, error) {
    switch e.strategy {
    case vCPM:
        // vCPM: bid = targetCPM * pCTR
        return e.targetCPM * float64(pCTR), nil
        
    case oCPM:
        // oCPM: bid = targetCPM * pCTR / expectedCTR
        // 需要校准
        calibratedCTR := e.calibrateCTR(pCTR)
        return e.targetCPM * calibratedCTR, nil
        
    case tCPA:
        // tCPA: bid = targetCPA * pCVR
        pCVR := e.predictCVR(ctx)
        return e.targetCPA * pCVR, nil
        
    default:
        return 0, fmt.Errorf("unknown bidding strategy")
    }
}

// calibrateCTR CTR 校准 ( Platt Scaling)
func (e *BidEngine) calibrateCTR(rawCTR float32) float32 {
    // logit 变换 + 线性校准
    logit := math.Log(float64(rawCTR) / (1 - float64(rawCTR)))
    calibrated := 1 / (1 + math.Exp(-(e.alpha*logit + e.beta)))
    return float32(calibrated)
}

// predictCVR CVR 预测
func (e *BidEngine) predictCVR(ctx context.Context) float32 {
    // 调用 CVR 模型
    return 0.05 // TODO: 接入真实模型
}
```

---

## 五、预算 pacing

```go
// dsp/pacing.go
package dsp

import (
    "sync"
    "time"
)

// Pacer 预算 pacing 控制器
type Pacer struct {
    mu          sync.Mutex
    totalBudget float64
    spent       float64
    startTime   time.Time
    duration    time.Duration
}

// NewPacer 创建 pacing 控制器
func NewPacer(totalBudget float64, duration time.Duration) *Pacer {
    return &Pacer{
        totalBudget: totalBudget,
        startTime:   time.Now(),
        duration:    duration,
    }
}

// AdjustBid 根据剩余预算调整出价
func (p *Pacer) AdjustBid(bid float64) float64 {
    p.mu.Lock()
    defer p.mu.Unlock()
    
    elapsed := time.Since(p.startTime).Seconds()
    totalSeconds := p.duration.Seconds()
    progress := elapsed / totalSeconds
    
    spent := p.spent
    remaining := p.totalBudget - spent
    
    // S-curve pacing
    idealProgress := 1 - math.Exp(-3*progress)
    budgetRate := remaining / (p.totalBudget * (1 - idealProgress))
    
    // 限制调整范围
    factor := math.Max(0.5, math.Min(2.0, budgetRate))
    return bid * factor
}

// RecordSpend 记录花费
func (p *Pacer) RecordSpend(amount float64) {
    p.mu.Lock()
    defer p.mu.Unlock()
    p.spent += amount
}
```

---

## 六、自测题

1. **pCTR 模型为什么需要校准？**
   - 模型输出是相对概率，需要校准到绝对概率

2. **S-curve pacing 的原理？**
   - 前期慢投、中期加速、后期收敛，避免提前耗尽预算

3. **oCPM 和 vCPM 的区别？**
   - oCPM 优化转化，vCPM 只看曝光

