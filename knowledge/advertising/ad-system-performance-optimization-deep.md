# 广告系统全链路性能优化

> 深入广告系统全链路性能优化：延迟优化、吞吐优化、资源优化。
> 包含真实生产环境优化案例。
> 适用对象：广告系统工程师、性能优化专家

---

## 1. 性能指标

### 1.1 核心指标

```
广告系统性能指标：

├── 延迟指标
│   ├── P50 Latency: < 50ms
│   ├── P99 Latency: < 200ms
│   └── 尾延迟: < 500ms
│
├── 吞吐指标
│   ├── QPS: > 100,000
│   └── 并发连接: > 10,000
│
├── 资源指标
│   ├── CPU: < 70%
│   ├── 内存: < 80%
│   └── 网络: < 60%
│
└── 业务指标
    ├── 填充率: > 95%
    ├── 点击率: > 2%
    └── 转化率: > 5%
```

### 1.2 Go 实现性能监控

```go
// performance_monitor.go

package ad

import (
    "sync"
    "time"
)

type PerformanceMetrics struct {
    latency     *LatencyTracker
    qps         *QPSTracker
    errors      *ErrorCounter
    resources   *ResourceMonitor
}

type LatencyTracker struct {
    p50, p90, p99 float64
    mu            sync.Mutex
    data          []time.Duration
}

func NewPerformanceMetrics() *PerformanceMetrics {
    return &PerformanceMetrics{
        latency:  NewLatencyTracker(),
        qps:      NewQPSTracker(),
        errors:   NewErrorCounter(),
        resources: NewResourceMonitor(),
    }
}

func (pm *PerformanceMetrics) RecordRequest(latency time.Duration, success bool) {
    pm.latency.Record(latency)
    pm.qps.Increment()
    if !success {
        pm.errors.Increment()
    }
}

func (pm *PerformanceMetrics) GetMetrics() map[string]interface{} {
    return map[string]interface{}{
        "p50_latency": pm.latency.P50(),
        "p90_latency": pm.latency.P90(),
        "p99_latency": pm.latency.P99(),
        "qps":         pm.qps.Current(),
        "error_rate":  pm.errors.Rate(),
    }
}
```

---

## 2. 延迟优化

### 2.1 优化策略

```
延迟优化策略：

1. 缓存优化
   ├── 本地缓存 (lru.Cache)
   ├── 分布式缓存 (Redis)
   └── CDN 缓存

2. 异步处理
   ├── 异步日志
   ├── 异步统计
   └── 批量处理

3. 连接优化
   ├── 连接池
   ├── 超时控制
   └── 重试策略

4. 并行处理
   ├── 并发请求
   ├── goroutine 池
   └── 流水线处理
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
    cache      *Cache
    timeout    time.Duration
    parallel   int
}

func NewLatencyOptimizer(cache *Cache, timeout time.Duration, parallel int) *LatencyOptimizer {
    return &LatencyOptimizer{
        cache:    cache,
        timeout:  timeout,
        parallel: parallel,
    }
}

func (lo *LatencyOptimizer) FetchAds(ctx context.Context, req *AdRequest) ([]AdCreative, error) {
    ctx, cancel := context.WithTimeout(ctx, lo.timeout)
    defer cancel()
    
    // 1. 检查缓存
    if cached, ok := lo.cache.Get(req.RequestID); ok {
        return cached.([]AdCreative), nil
    }
    
    // 2. 并行请求
    results := make(chan []AdCreative, lo.parallel)
    var wg sync.WaitGroup
    
    sources := lo.getSources(req)
    for _, source := range sources {
        wg.Add(1)
        go func(s Source) {
            defer wg.Done()
            ads, err := s.FetchAds(ctx, req)
            if err == nil {
                results <- ads
            }
        }(source)
    }
    
    go func() {
        wg.Wait()
        close(results)
    }()
    
    // 3. 合并结果
    var allAds []AdCreative
    deadline := time.After(lo.timeout / 2)
    
    for {
        select {
        case ads := <-results:
            allAds = append(allAds, ads...)
            if len(allAds) >= lo.parallel/2 {
                goto done
            }
        case <-deadline:
            goto done
        case <-ctx.Done():
            return nil, ctx.Err()
        }
    }
    
done:
    // 4. 写入缓存
    lo.cache.Set(req.RequestID, allAds, 5*time.Second)
    return allAds, nil
}
```

---

## 3. 吞吐优化

### 3.1 优化策略

```
吞吐优化策略：

1. 连接池优化
   ├── TCP 连接复用
   ├── HTTP/2 多路复用
   └── 连接池大小调优

2. 批量处理
   ├── 请求批处理
   ├── 响应批量返回
   └── 批量写入

3. 限流控制
   ├── 令牌桶
   ├── 漏桶
   └── 自适应限流

4. 资源隔离
   ├── 租户隔离
   ├── 优先级队列
   └── 资源配额
```

### 3.2 Go 实现吞吐优化

```go
// throughput_optimizer.go

package ad

import (
    "sync"
    "sync/atomic"
)

type ThroughputOptimizer struct {
    workerPool  *WorkerPool
    rateLimiter *RateLimiter
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
        tasks:   make(chan func(), 1000),
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

func (wp *WorkerPool) Submit(task func()) {
    wp.wg.Add(1)
    wp.tasks <- task
}

func (wp *WorkerPool) Wait() {
    wp.wg.Wait()
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

## 4. 资源优化

### 4.1 优化策略

```
资源优化策略：

1. 内存优化
   ├── 对象池 (sync.Pool)
   ├── 内存回收
   └── 内存限流

2. CPU 优化
   ├── GOMAXPROCS 调优
   ├── CPU 亲和性
   └── 算法优化

3. 网络优化
   ├── 压缩传输
   ├── 连接复用
   └── 协议优化

4. 磁盘优化
   ├── 顺序写入
   ├── 日志轮转
   └── 压缩存储
```

### 4.2 Go 实现资源优化

```go
// resource_optimizer.go

package ad

import (
    "sync"
)

type ResourceOptimizer struct {
    objectPool  *sync.Pool
    memoryLimit int64
    currentMem  int64
    mu          sync.Mutex
}

type ObjectPool struct {
    pool sync.Pool
}

func NewObjectPool() *ObjectPool {
    return &ObjectPool{
        pool: sync.Pool{
            New: func() interface{} {
                return &AdCreative{}
            },
        },
    }
}

func (op *ObjectPool) Get() *AdCreative {
    return op.pool.Get().(*AdCreative)
}

func (op *ObjectPool) Put(creative *AdCreative) {
    // 重置对象状态
    creative.Reset()
    op.pool.Put(creative)
}

type MemoryMonitor struct {
    limit    int64
    current  int64
    mu       sync.Mutex
}

func NewMemoryMonitor(limit int64) *MemoryMonitor {
    return &MemoryMonitor{
        limit: limit,
    }
}

func (mm *MemoryMonitor) Allocate(size int64) bool {
    mm.mu.Lock()
    defer mm.mu.Unlock()
    
    if mm.current+size > mm.limit {
        return false
    }
    mm.current += size
    return true
}

func (mm *MemoryMonitor) Free(size int64) {
    mm.mu.Lock()
    defer mm.mu.Unlock()
    mm.current -= size
}
```

---

## 5. 总结

### 5.1 核心优化策略

| 维度 | 策略 | 效果 |
|------|------|------|
| 延迟 | 缓存+并行 | P99 < 200ms |
| 吞吐 | 连接池+限流 | QPS > 100K |
| 资源 | 对象池+内存监控 | CPU < 70% |

### 5.2 最佳实践

- [ ] 建立性能监控体系
- [ ] 定期性能压测
- [ ] 优化热点路径
- [ ] 资源隔离保障

---

*最后更新：2026-08-11*
*作者：Ryan*
