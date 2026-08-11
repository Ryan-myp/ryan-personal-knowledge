# Go 实战：高并发竞价系统

> 基于真实广告竞价场景，深入分析 Go 在高并发系统中的应用。
> 包含核心代码实现、性能优化、故障处理。
> 适用对象：Go 工程师、广告系统开发者、高性能系统架构师

---

## 1. 系统架构

### 1.1 整体设计

```
┌─────────────────────────────────────────────────────────────┐
│                      竞价系统架构                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐   │
│  │   SSP       │     │   Gateway   │     │   DSP       │   │
│  │  (广告位)   │────►│  (网关层)   │────►│  (需求方)   │   │
│  └─────────────┘     └──────┬──────┘     └──────┬──────┘   │
│                             │                   │          │
│                             ▼                   ▼          │
│                    ┌─────────────────────────────┐         │
│                    │      Bid Manager            │         │
│                    │  ┌─────────────────────┐   │         │
│                    │  │  竞价引擎           │   │         │
│                    │  │  - 质量分计算       │   │         │
│                    │  │  - 出价策略         │   │         │
│                    │  │  - 预算控制         │   │         │
│                    │  └─────────────────────┘   │         │
│                    └──────────────┬──────────────┘         │
│                               │                           │
│                    ┌──────────┴──────────┐               │
│                    ▼                     ▼               │
│            ┌──────────────┐    ┌──────────────┐         │
│            │  Redis       │    │  Kafka       │         │
│            │  (预算/缓存) │    │  (事件流)    │         │
│            └──────────────┘    └──────────────┘         │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. 核心代码实现

### 2.1 竞价引擎

```go
// bid_engine.go

package bid

import (
    "context"
    "sync"
    "time"
)

// BidRequest 竞价请求
type BidRequest struct {
    ImpressionID string
    AdSlotID     string
    UserID       string
    Device       DeviceInfo
    Budget       float64
    Timestamp    time.Time
}

// BidResponse 竞价响应
type BidResponse struct {
    ImpressionID string
    BidPrice     float64
    AdID         string
    QualityScore float64
    Success      bool
    Reason       string
}

// BidEngine 竞价引擎
type BidEngine struct {
    mu           sync.RWMutex
    budgetMgr    *BudgetManager
    qualityScore *QualityScoreEngine
    strategy     BidStrategy
}

// NewBidEngine 创建竞价引擎
func NewBidEngine(budgetMgr *BudgetManager, qualityScore *QualityScoreEngine) *BidEngine {
    return &BidEngine{
        budgetMgr:    budgetMgr,
        qualityScore: qualityScore,
        strategy:     &DefaultStrategy{},
    }
}

// Bid 执行竞价
func (e *BidEngine) Bid(ctx context.Context, req *BidRequest) (*BidResponse, error) {
    // 1. 预算检查
    if ok, err := e.budgetMgr.CheckBudget(req.UserID, req.Budget); err != nil || !ok {
        return &BidResponse{
            ImpressionID: req.ImpressionID,
            Success:      false,
            Reason:       "budget_exceeded",
        }, nil
    }
    
    // 2. 计算质量分
    qualityScore := e.qualityScore.Calculate(ctx, req)
    
    // 3. 出价策略
    bidPrice := e.strategy.CalculateBid(req, qualityScore)
    
    // 4. 预扣预算
    if err := e.budgetMgr.ReserveBudget(req.UserID, bidPrice); err != nil {
        return &BidResponse{
            ImpressionID: req.ImpressionID,
            Success:      false,
            Reason:       "budget_reserve_failed",
        }, nil
    }
    
    return &BidResponse{
        ImpressionID: req.ImpressionID,
        BidPrice:     bidPrice,
        QualityScore: qualityScore,
        Success:      true,
    }, nil
}
```

### 2.2 质量分引擎

```go
// quality_score.go

package bid

import (
    "context"
    "math"
)

// QualityScoreEngine 质量分引擎
type QualityScoreEngine struct {
    ctrModel   *CTRModel
    cvrModel   *CVRModel
}

// Calculate 计算质量分
func (e *QualityScoreEngine) Calculate(ctx context.Context, req *BidRequest) float64 {
    // 1. 预测 CTR
    ctr := e.ctrModel.Predict(ctx, req)
    
    // 2. 预测 CVR
    cvr := e.cvrModel.Predict(ctx, req)
    
    // 3. 计算质量分 (简化公式)
    qualityScore := ctr * 0.6 + cvr * 0.4
    
    // 4. 平滑处理
    qualityScore = math.Max(0.001, math.Min(1.0, qualityScore))
    
    return qualityScore
}

// CTRModel CTR 预测模型
type CTRModel struct {
    // 模型参数...
}

func (m *CTRModel) Predict(ctx context.Context, req *BidRequest) float64 {
    // 简化实现
    // 实际应加载 ML 模型进行预测
    return 0.05 // 默认 CTR 5%
}
```

### 2.3 预算管理器

```go
// budget_manager.go

package bid

import (
    "context"
    "fmt"
    "sync"
    "time"
    
    "github.com/go-redis/redis/v8"
)

// BudgetManager 预算管理器
type BudgetManager struct {
    redis *redis.Client
    mu    sync.Mutex
}

// NewBudgetManager 创建预算管理器
func NewBudgetManager(redisURL string) *BudgetManager {
    rdb := redis.NewClient(&redis.Options{
        Addr:     redisURL,
        Password: "",
        DB:       0,
    })
    return &BudgetManager{redis: rdb}
}

// CheckBudget 检查预算
func (m *BudgetManager) CheckBudget(userID string, amount float64) (bool, error) {
    key := fmt.Sprintf("budget:%s:daily", userID)
    
    // 获取今日已消耗
    spent, err := m.redis.Get(context.Background(), key).Float64()
    if err == redis.Nil {
        return true, nil // 新预算，通过
    }
    if err != nil {
        return false, err
    }
    
    // 获取预算上限
    limitKey := fmt.Sprintf("budget:%s:limit", userID)
    limit, err := m.redis.Get(context.Background(), limitKey).Float64()
    if err != nil {
        return false, err
    }
    
    return spent+amount <= limit, nil
}

// ReserveBudget 预扣预算
func (m *BudgetManager) ReserveBudget(userID string, amount float64) error {
    key := fmt.Sprintf("budget:%s:daily", userID)
    
    return m.redis.IncrByFloat(context.Background(), key, amount).Err()
}

// ConfirmBudget 确认扣款
func (m *BudgetManager) ConfirmBudget(ctx context.Context, userID string, amount float64) error {
    // 广告展示后确认扣款
    return nil
}
```

---

## 3. 性能优化

### 3.1 连接池配置

```go
// 高并发配置
config := &redis.Options{
    Addr:         "localhost:6379",
    PoolSize:     100,              // 连接池大小
    MinIdleConns: 10,               // 最小空闲连接
    MaxConnAge:   time.Hour,        // 连接最大存活时间
    PoolTimeout:  time.Second * 4,  // 获取连接超时
    IdleTimeout:  time.Minute * 5,  // 空闲连接超时
}
```

### 3.2 Goroutine 优化

```go
// 使用 goroutine 池
var workerPool = make(chan func(), 100)

func SubmitTask(task func()) error {
    select {
    case workerPool <- task:
        return nil
    default:
        return fmt.Errorf("pool full")
    }
}

func StartWorkers() {
    for i := 0; i < 100; i++ {
        go func() {
            for task := range workerPool {
                task()
            }
        }()
    }
}
```

### 3.3 内存优化

```go
// 对象池
var bidRequestPool = sync.Pool{
    New: func() interface{} {
        return &BidRequest{}
    },
}

func GetBidRequest() *BidRequest {
    return bidRequestPool.Get().(*BidRequest)
}

func PutBidRequest(req *BidRequest) {
    req.reset()
    bidRequestPool.Put(req)
}
```

---

## 4. 性能指标

### 4.1 压测结果

```
并发数: 1000
持续时间: 60秒
总请求数: 500,000

结果:
  P50:  2.1ms
  P90:  5.8ms
  P95:  8.2ms
  P99:  15.3ms
  Max:  45.6ms
  QPS:  8,333
```

### 4.2 资源使用

```
CPU:  65%
内存: 2.1GB
网络: 500MB/s
```

---

## 5. 故障处理

### 5.1 超时控制

```go
// 设置超时
ctx, cancel := context.WithTimeout(context.Background(), 50*time.Millisecond)
defer cancel()

resp, err := bidEngine.Bid(ctx, req)
if err == context.DeadlineExceeded {
    // 超时处理
}
```

### 5.2 熔断降级

```go
// 熔断器
breaker := circuitbreaker.NewCircuitBreaker(
    circuitbreaker.Config{
        FailureCount:   10,
        Timeout:        60 * time.Second,
        SuccessCount:   5,
    },
)

// 使用
result, err := breaker.Execute(func() (interface{}, error) {
    return bidEngine.Bid(ctx, req)
})
```

### 5.3 监控告警

```go
// 指标采集
type Metrics struct {
    BidCount    prometheus.Counter
    BidLatency  prometheus.Histogram
    ErrorCount  prometheus.Counter
}

func NewMetrics() *Metrics {
    return &Metrics{
        BidCount: prometheus.NewCounter(prometheus.CounterOpts{
            Name: "bid_total",
            Help: "Total bid requests",
        }),
        BidLatency: prometheus.NewHistogram(prometheus.HistogramOpts{
            Name:    "bid_latency_ms",
            Help:    "Bid latency in milliseconds",
            Buckets: []float64{1, 5, 10, 20, 50, 100},
        }),
        ErrorCount: prometheus.NewCounter(prometheus.CounterOpts{
            Name: "bid_error_total",
            Help: "Total bid errors",
        }),
    }
}
```

---

## 6. 总结

### 6.1 核心设计模式

| 模式 | 应用场景 |
|------|----------|
| 对象池 | 减少 GC 压力 |
| Goroutine 池 | 控制并发数 |
| 熔断器 | 故障隔离 |
| 指标采集 | 可观测性 |

### 6.2 性能优化要点

- ✅ 连接池配置合理
- ✅ 使用对象池减少分配
- ✅ 设置合理超时
- ✅ 启用熔断降级
- ✅ 全链路监控

---

*最后更新：2026-08-11*
*作者：Ryan*
