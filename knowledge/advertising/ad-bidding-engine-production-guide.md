# 广告竞价引擎生产环境完整指南

> **版本**: v2.0  
> **日期**: 2026-08-13  
> **作者**: Ryan  
> **分类**: 广告/竞价引擎  
> **代码密度**: 30%

---

## 一、生产环境架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                     竞价引擎生产架构                                  │
│                                                                     │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐            │
│  │   DSP       │    │  竞价引擎    │    │   SSP       │            │
│  │  Request    │───▶│  Engine     │───▶│  Response   │            │
│  └─────────────┘    └──────┬──────┘    └─────────────┘            │
│                            │                                       │
│              ┌─────────────┼─────────────┐                        │
│              ▼             ▼             ▼                        │
│        ┌──────────┐ ┌──────────┐ ┌──────────┐                    │
│        │ pCTR     │ │ 定价     │ │ 频控     │                    │
│        │ 预估模型 │ │ 策略     │ │ 系统     │                    │
│        └──────────┘ └──────────┘ └──────────┘                    │
│              │             │             │                        │
│              ▼             ▼             ▼                        │
│        ┌─────────────────────────────────────┐                   │
│        │         Redis Cluster               │                   │
│        │  - 实时特征缓存                      │                   │
│        │  - 频控计数器                       │                   │
│        │  - 预算池                           │                   │
│        └─────────────────────────────────────┘                   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 二、核心实现

### 2.1 竞价决策器

```go
// bidding/engine.go
package bidding

import (
    "context"
    "time"
)

// BidDecision 竞价决策
type BidDecision struct {
    BidPrice    float64   `json:"bid_price"`
    ShouldBid   bool      `json:"should_bid"`
    Reason      string    `json:"reason"`
    Latency     time.Duration `json:"latency"`
}

// Engine 竞价引擎
type Engine struct {
    ctrModel   CTRModel
    pacer      PacingController
    freqCtrl   FrequencyController
    budgetMgr  BudgetManager
}

// NewEngine 创建引擎
func NewEngine(ctr CTRModel, pacer PacingController, freq FrequencyController, budget BudgetManager) *Engine {
    return &Engine{
        ctrModel:  ctr,
        pacer:     pacer,
        freqCtrl:  freq,
        budgetMgr: budget,
    }
}

// Bid 执行竞价决策
func (e *Engine) Bid(ctx context.Context, req *BidRequest) (*BidDecision, error) {
    start := time.Now()
    
    // 1. 频控检查
    if !e.freqCtrl.Check(ctx, req.AdUnitID, req.UserID) {
        return &BidDecision{
            ShouldBid: false,
            Reason:    "frequency_capped",
            Latency:   time.Since(start),
        }, nil
    }
    
    // 2. 预算检查
    if !e.budgetMgr.HasBudget(ctx, req.AdvertiserID) {
        return &BidDecision{
            ShouldBid: false,
            Reason:    "budget_exhausted",
            Latency:   time.Since(start),
        }, nil
    }
    
    // 3. pCTR 预估
    pCTR, err := e.ctrModel.Predict(ctx, req)
    if err != nil {
        return nil, err
    }
    
    // 4. 出价计算 (oCPM)
    bidPrice := e.calculateBidPrice(pCTR, req.TargetCPM)
    
    // 5. 预算 pacing
    adjustedPrice := e.pacer.Adjust(ctx, bidPrice, req.Budget)
    
    return &BidDecision{
        BidPrice:  adjustedPrice,
        ShouldBid: adjustedPrice > 0,
        Reason:    "winning_bid",
        Latency:   time.Since(start),
    }, nil
}

// calculateBidPrice 计算出价
func (e *Engine) calculateBidPrice(pCTR, targetCPM float64) float64 {
    // oCPM: bid = targetCPM * pCTR / expectedCTR
    return targetCPM * pCTR
}
```

### 2.2 频控系统

```go
// bidding/frequency.go
package bidding

import (
    "context"
    "fmt"
    "time"
    
    "github.com/redis/go-redis/v9"
)

// FrequencyController 频控控制器
type FrequencyController struct {
    rdb *redis.Client
    ttl time.Duration
}

// NewFrequencyController 创建频控控制器
func NewFrequencyController(rdb *redis.Client) *FrequencyController {
    return &FrequencyController{
        rdb: rdb,
        ttl: 24 * time.Hour,
    }
}

// Check 检查是否触发频控
func (fc *FrequencyController) Check(ctx context.Context, adUnitID, userID string) bool {
    key := fmt.Sprintf("freq:%s:%s", adUnitID, userID)
    
    count, err := fc.rdb.Incr(ctx, key).Result()
    if err != nil {
        return true // 失败时放行
    }
    
    if count == 1 {
        fc.rdb.Expire(ctx, key, fc.ttl)
    }
    
    // 默认每天最多展示 5 次
    return count <= 5
}

// Reset 重置频控计数
func (fc *FrequencyController) Reset(ctx context.Context, adUnitID, userID string) {
    key := fmt.Sprintf("freq:%s:%s", adUnitID, userID)
    fc.rdb.Del(ctx, key)
}
```

---

## 三、延迟优化

### 3.1 超时控制

```go
// bidding/timeout.go
package bidding

import (
    "context"
    "time"
)

// WithTimeout 带超时的竞价
func (e *Engine) BidWithTimeout(ctx context.Context, req *BidRequest) (*BidDecision, error) {
    // 总超时 20ms
    ctx, cancel := context.WithTimeout(ctx, 20*time.Millisecond)
    defer cancel()
    
    // 并行执行独立检查
    chFreq := make(chan bool, 1)
    chBudget := make(chan bool, 1)
    
    go func() {
        chFreq <- e.freqCtrl.Check(ctx, req.AdUnitID, req.UserID)
    }()
    
    go func() {
        chBudget <- e.budgetMgr.HasBudget(ctx, req.AdvertiserID)
    }()
    
    // 等待结果
    select {
    case freqOK := <-chFreq:
        if !freqOK {
            return &BidDecision{ShouldBid: false, Reason: "freq"}, nil
        }
    case <-ctx.Done():
        return nil, ctx.Err()
    }
    
    select {
    case budgetOK := <-chBudget:
        if !budgetOK {
            return &BidDecision{ShouldBid: false, Reason: "budget"}, nil
        }
    case <-ctx.Done():
        return nil, ctx.Err()
    }
    
    // 串行执行 pCTR 预估 (关键路径)
    pCTR, err := e.ctrModel.Predict(ctx, req)
    if err != nil {
        return nil, err
    }
    
    bidPrice := e.calculateBidPrice(pCTR, req.TargetCPM)
    return &BidDecision{BidPrice: bidPrice, ShouldBid: true}, nil
}
```

---

## 四、监控与告警

```go
// bidding/monitor.go
package bidding

import (
    "context"
    "time"
)

// Metrics 竞价指标
type Metrics struct {
    TotalRequests   int64
    WinRequests     int64
    AvgLatency      time.Duration
    P99Latency      time.Duration
    CPMPayout       float64
}

// Monitor 监控器
type Monitor struct {
    metrics Metrics
    window  time.Duration
}

func (m *Monitor) Record(req *BidRequest, decision *BidDecision) {
    m.metrics.TotalRequests++
    if decision.ShouldBid {
        m.metrics.WinRequests++
    }
    m.metrics.AvgLatency += decision.Latency
}

func (m *Monitor) GetStats() Metrics {
    return m.metrics
}
```

---

## 五、故障排查清单

| 问题 | 可能原因 | 排查方法 |
|------|---------|---------|
| 延迟飙升 | Redis 热点 key | redis-cli KEYS "freq:*" |
| 预算耗尽过快 | pacing 算法偏差 | 检查 budget_mgr 日志 |
| 频控失效 | Redis 主从延迟 | 检查 replicate 状态 |
| pCTR 预测不准 | 模型过期 | 检查 model version |

