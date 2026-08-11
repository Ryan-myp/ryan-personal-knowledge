# 实时竞价系统设计深度解析

> 深入RTB（Real-Time Bidding）系统设计：低延迟架构、高并发处理、分布式一致性。
> 包含真实生产环境RTB系统设计。
> 适用对象：广告系统架构师、高并发系统工程师

---

## 1. RTB 系统架构

### 1.1 整体架构

```
RTB 系统架构：

┌─────────────────────────────────────────────────────────────┐
│                    RTB 架构                                  │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  接入层 (Edge)                                               │
│  ├── API Gateway                                            │
│  ├── 请求解析                                                  │
│  └── 限流熔断                                                │
│                                                             │
│  处理层 (Core)                                               │
│  ├── 特征获取                                                │
│  ├── 出价计算                                                │
│  ├── 竞价决策                                                │
│  └── 响应组装                                                │
│                                                             │
│  数据层 (Data)                                               │
│  ├── 特征存储 (Redis/Tair)                                   │
│  ├── 模型服务 (TensorFlow Serving)                          │
│  └── 日志存储 (Kafka)                                       │
│                                                             │
│  监控层 (Observability)                                      │
│  ├── 性能监控                                                │
│  ├── 业务监控                                                │
│  └── 告警系统                                                │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 Go 实现RTB核心

```go
// rtb_system.go

package ad

import (
    "context"
    "sync"
    "time"
)

type RTBSYSTEM struct {
    featureStore *FeatureStore
    modelServer  *ModelServer
    bidEngine    *BiddingEngine
    metrics      *Metrics
    config       *Config
}

type Config struct {
    Timeout          time.Duration
    MaxBid           float64
    MinBid           float64
    FeatureCacheTTL  time.Duration
    ModelCacheTTL    time.Duration
}

type RTBRequest struct {
    RequestID    string
    Impression   Impression
    User         User
    Site         Site
    Device       Device
    Timestamp    int64
}

type RTBResponse struct {
    RequestID    string
    BidPrice     float64
    CreativeID   string
    Targeting    map[string]string
    ResponseTime time.Duration
}

func NewRTBSYSTEM(config *Config) *RTBSYSTEM {
    return &RTBSYSTEM{
        featureStore: NewFeatureStore(config.FeatureCacheTTL),
        modelServer:  NewModelServer(config.ModelCacheTTL),
        bidEngine:    NewBiddingEngine(config),
        metrics:      NewMetrics(),
        config:       config,
    }
}

func (rtb *RTBSYSTEM) ProcessBid(ctx context.Context, req *RTBRequest) (*RTBResponse, error) {
    startTime := time.Now()
    
    // 1. 获取特征
    features := rtb.featureStore.GetFeatures(ctx, req.User.ID)
    
    // 2. 模型预测
    predictions := rtb.modelServer.Predict(ctx, features)
    
    // 3. 出价计算
    bidPrice, creativeID := rtb.bidEngine.CalculateBid(predictions, req)
    
    // 4. 限制出价范围
    bidPrice = clamp(bidPrice, rtb.config.MinBid, rtb.config.MaxBid)
    
    // 5. 记录指标
    rtb.metrics.RecordBid(time.Since(startTime), bidPrice > 0)
    
    return &RTBResponse{
        RequestID:    req.RequestID,
        BidPrice:     bidPrice,
        CreativeID:   creativeID,
        Targeting:    features.Targeting,
        ResponseTime: time.Since(startTime),
    }, nil
}
```

---

## 2. 低延迟优化

### 2.1 延迟优化策略

```
低延迟优化策略：

├── 网络优化
│   ├── 就近部署
│   ├── 连接复用
│   └── 协议优化 (HTTP/2, gRPC)
│
├── 缓存优化
│   ├── 本地缓存 (L1)
│   ├── 分布式缓存 (L2)
│   └── 预计算缓存
│
├── 计算优化
│   ├── 特征预计算
│   ├── 模型量化
│   └── 并行计算
│
└── 架构优化
    ├── 异步处理
    ├── 批量请求
    └── 超时控制
```

### 2.2 Go 实现延迟优化

```go
// latency_optimizer.go

package ad

import (
    "context"
    "sync"
    "time"
)

type LatencyOptimizer struct {
    l1Cache  *LocalCache
    l2Cache  *DistributedCache
    timeout  time.Duration
}

type BidPipeline struct {
    steps []PipelineStep
}

type PipelineStep func(ctx context.Context, state *BidState) error

func NewLatencyOptimizer() *LatencyOptimizer {
    return &LatencyOptimizer{
        l1Cache: NewLocalCache(10000),
        l2Cache: NewDistributedCache(),
        timeout: 50 * time.Millisecond,
    }
}

func (lo *LatencyOptimizer) ProcessBid(ctx context.Context, req *RTBRequest) (*RTBResponse, error) {
    ctx, cancel := context.WithTimeout(ctx, lo.timeout)
    defer cancel()
    
    state := &BidState{
        Request: req,
    }
    
    pipeline := lo.buildPipeline()
    
    var wg sync.WaitGroup
    errChan := make(chan error, len(pipeline))
    
    for _, step := range pipeline {
        wg.Add(1)
        go func(s PipelineStep) {
            defer wg.Done()
            errChan <- s(ctx, state)
        }(step)
    }
    
    go func() {
        wg.Wait()
        close(errChan)
    }()
    
    // 等待所有步骤完成或超时
    for err := range errChan {
        if err != nil {
            return nil, err
        }
    }
    
    return lo.buildResponse(state), nil
}
```

---

## 3. 高并发处理

### 3.1 并发策略

```
高并发处理策略：

├── 连接管理
│   ├── 连接池
│   ├── 连接复用
│   └── 心跳检测
│
├── 请求处理
│   ├── Worker Pool
│   ├── 批处理
│   └── 背压控制
│
├── 资源隔离
│   ├── 租户隔离
│   ├── 优先级队列
│   └── 限流熔断
│
└── 故障恢复
    ├── 重试策略
    ├── 降级处理
    └── 熔断器
```

### 3.2 Go 实现高并发

```go
// concurrency_handler.go

package ad

import (
    "context"
    "sync"
    "sync/atomic"
)

type ConcurrencyHandler struct {
    workerPool  *WorkerPool
    rateLimiter *RateLimiter
    circuit     *CircuitBreaker
    metrics     atomic.Int64
}

type WorkerPool struct {
    workers int
    tasks   chan func()
    wg      sync.WaitGroup
}

func NewWorkerPool(workers int) *WorkerPool {
    wp := &WorkerPool{
        workers: workers,
        tasks:   make(chan func(), 10000),
    }
    wp.Start()
    return wp
}

func (wp *WorkerPool) Start() {
    for i := 0; i < wp.workers; i++ {
        go func() {
            for task := range wp.tasks {
                task()
                wp.wg.Done()
            }
        }()
    }
}

func (wp *WorkerPool) Submit(task func()) bool {
    select {
    case wp.tasks <- task:
        wp.wg.Add(1)
        return true
    default:
        return false
    }
}

type RateLimiter struct {
    rate     int
    burst    int
    tokens   float64
    lastTime time.Time
    mu       sync.Mutex
}

func NewRateLimiter(rate, burst int) *RateLimiter {
    return &RateLimiter{
        rate:  rate,
        burst: burst,
        tokens: float64(burst),
    }
}

func (rl *RateLimiter) Allow() bool {
    rl.mu.Lock()
    defer rl.mu.Unlock()
    
    now := time.Now()
    elapsed := now.Sub(rl.lastTime).Seconds()
    rl.tokens += elapsed * float64(rl.rate)
    if rl.tokens > float64(rl.burst) {
        rl.tokens = float64(rl.burst)
    }
    rl.lastTime = now
    
    if rl.tokens >= 1 {
        rl.tokens--
        return true
    }
    return false
}
```

---

## 4. 分布式一致性

### 4.1 一致性策略

```
分布式一致性策略：

├── 数据一致性
│   ├── 最终一致性
│   ├── 强一致性
│   └── 会话一致性
│
├── 状态管理
│   ├── 分布式锁
│   ├── 版本号
│   └── 时间戳
│
└── 故障恢复
    ├── 重试机制
    ├── 补偿事务
    └── 幂等性
```

### 4.2 Go 实现一致性

```go
// consistency.go

package ad

import (
    "context"
    "sync"
    "time"
)

type ConsistencyManager struct {
    locks     sync.Map
    versions  sync.Map
    retryPolicy *RetryPolicy
}

type RetryPolicy struct {
    MaxRetries int
    BaseDelay  time.Duration
    MaxDelay   time.Duration
}

func NewConsistencyManager() *ConsistencyManager {
    return &ConsistencyManager{
        retryPolicy: &RetryPolicy{
            MaxRetries: 3,
            BaseDelay:  100 * time.Millisecond,
            MaxDelay:   1 * time.Second,
        },
    }
}

func (cm *ConsistencyManager) WithLock(key string, fn func() error) error {
    lock, _ := cm.locks.LoadOrStore(key, &sync.Mutex{})
    mu := lock.(*sync.Mutex)
    
    mu.Lock()
    defer mu.Unlock()
    
    return fn()
}

func (cm *ConsistencyManager) VersionedWrite(key string, value interface{}, version int64) error {
    // 乐观锁
    currentVersion, ok := cm.versions.Load(key)
    if ok && currentVersion.(int64) != version {
        return ErrVersionConflict
    }
    
    cm.versions.Store(key, version+1)
    return nil
}

type RetryableError struct {
    Err error
}

func (e *RetryableError) Error() string {
    return e.Err.Error()
}

func (cm *ConsistencyManager) Retry(ctx context.Context, fn func() error) error {
    var lastErr error
    delay := cm.retryPolicy.BaseDelay
    
    for i := 0; i < cm.retryPolicy.MaxRetries; i++ {
        err := fn()
        if err == nil {
            return nil
        }
        
        lastErr = err
        select {
        case <-ctx.Done():
            return ctx.Err()
        case <-time.After(delay):
            delay = min(delay*2, cm.retryPolicy.MaxDelay)
        }
    }
    
    return lastErr
}
```

---

## 5. 总结

### 5.1 核心设计要点

| 维度 | 策略 | 目标 |
|------|------|------|
| 延迟 | 缓存+并行 | P99 < 50ms |
| 并发 | Worker Pool+限流 | QPS > 100K |
| 一致性 | 分布式锁+重试 | 最终一致 |

### 5.2 最佳实践

- [ ] 合理的超时设置
- [ ] 多层缓存架构
- [ ] 完善的监控告警
- [ ] 混沌工程验证

---

*最后更新：2026-08-11*
*作者：Ryan*
