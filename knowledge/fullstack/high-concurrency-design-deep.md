# 高并发系统设计深度解析

> 深入高并发设计：限流、缓存、熔断、降级、异步化。
> 包含真实生产环境架构设计。
> 适用对象：架构师、技术负责人、高级工程师

---

## 1. 限流算法

### 1.1 常见限流算法

```
┌─────────────────────────────────────────────────────────────┐
│                    限流算法对比                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  计数器算法 (Counting)                                       │
│  ─────────────────────────                                  │
│  ├── 固定窗口：统计固定时间内的请求数                         │
│  ├── 缺点：窗口边界突发                                       │
│  └── 适用：简单场景                                          │
│                                                             │
│  滑动窗口 (Sliding Window)                                   │
│  ─────────────────────────                                  │
│  ├── 细分时间窗口，减少边界问题                               │
│  ├── 需要存储更多数据                                        │
│  └── 适用：中等规模                                          │
│                                                             │
│  令牌桶 (Token Bucket)                                       │
│  ─────────────────────────                                  │
│  ├── 以固定速率生成令牌                                       │
│  ├── 允许一定程度的突发                                       │
│  └── 适用：需要控制平均速率                                   │
│                                                             │
│  漏桶 (Leaky Bucket)                                        │
│  ─────────────────────────                                  │
│  ├── 固定速率处理请求                                        │
│  ├── 严格限制速率，不允许突发                                 │
│  └── 适用：需要严格限流                                       │
│                                                             │
│  GCRA (Generic Cell Rate Algorithm)                          │
│  ─────────────────────────                                  │
│  ├── 精确的限流算法                                           │
│  └── 适用：高精度场景                                        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 Go 实现令牌桶限流

```go
// token_bucket.go

package limiter

import (
    "sync"
    "time"
)

type TokenBucket struct {
    mu         sync.Mutex
    tokens     float64
    maxTokens  float64
    rate       float64 // tokens per second
    lastRefill time.Time
}

func NewTokenBucket(rate float64, capacity float64) *TokenBucket {
    return &TokenBucket{
        tokens:     capacity,
        maxTokens:  capacity,
        rate:       rate,
        lastRefill: time.Now(),
    }
}

func (tb *TokenBucket) Allow() bool {
    tb.mu.Lock()
    defer tb.mu.Unlock()
    
    now := time.Now()
    elapsed := now.Sub(tb.lastRefill).Seconds()
    tb.tokens += elapsed * tb.rate
    if tb.tokens > tb.maxTokens {
        tb.tokens = tb.maxTokens
    }
    tb.lastRefill = now
    
    if tb.tokens >= 1.0 {
        tb.tokens -= 1.0
        return true
    }
    return false
}

func (tb *TokenBucket) Wait() bool {
    for !tb.Allow() {
        time.Sleep(time.Millisecond * 10)
    }
    return true
}
```

---

## 2. 缓存架构

### 2.1 多级缓存架构

```
┌─────────────────────────────────────────────────────────────┐
│                    多级缓存架构                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  L1 Cache (本地缓存)                                         │
│  ├── Caffeine / Guava                                       │
│  ├── 速度：纳秒级                                            │
│  ├── 容量：MB 级别                                           │
│  └── 特点：无网络开销，但不同步                                │
│                                                             │
│  L2 Cache (分布式缓存)                                       │
│  ├── Redis / Memcached                                      │
│  ├── 速度：毫秒级                                            │
│  ├── 容量：GB 级别                                           │
│  └── 特点：共享，有网络开销                                   │
│                                                             │
│  L3 Cache (数据库)                                           │
│  ├── MySQL / PostgreSQL                                     │
│  ├── 速度：毫秒级                                            │
│  ├── 容量：TB 级别                                           │
│  └── 特点：持久化，可靠                                       │
│                                                             │
│  缓存穿透 / 击穿 / 雪崩 解决方案                               │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 缓存穿透解决方案

```go
// cache_penetration.go

package cache

import (
    "sync"
    "time"
)

type CacheService struct {
    localCache  map[string]*CacheItem
    redisClient *RedisClient
    bloomFilter *BloomFilter
    mu          sync.RWMutex
}

type CacheItem struct {
    Value      interface{}
    ExpireAt   time.Time
    IsNil      bool // 标记是否为空值
}

func (s *CacheService) Get(key string) (interface{}, error) {
    // 1. 布隆过滤器检查
    if !s.bloomFilter.Test(key) {
        return nil, ErrKeyNotExist
    }
    
    // 2. 本地缓存
    s.mu.RLock()
    item, ok := s.localCache[key]
    s.mu.RUnlock()
    
    if ok && !item.IsNil && time.Now().Before(item.ExpireAt) {
        return item.Value, nil
    }
    
    // 3. 分布式缓存
    val, err := s.redisClient.Get(key)
    if err != nil {
        return nil, err
    }
    
    // 4. 空值缓存（防穿透）
    if val == "" {
        s.mu.Lock()
        s.localCache[key] = &CacheItem{IsNil: true, ExpireAt: time.Now().Add(time.Second * 30)}
        s.mu.Unlock()
        return nil, nil
    }
    
    // 5. 写入缓存
    s.mu.Lock()
    s.localCache[key] = &CacheItem{Value: val, ExpireAt: time.Now().Add(time.Minute * 5)}
    s.mu.Unlock()
    
    return val, nil
}
```

---

## 3. 熔断降级

### 3.1 熔断器状态机

```
┌─────────────────────────────────────────────────────────────┐
│                    熔断器状态机                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│                      ┌─────────┐                            │
│                      │ CLOSED  │◄─────────────────────┐     │
│                      └────┬────┘                      │     │
│                           │                           │     │
│              失败次数超过阈值                            │     │
│                           │                           │     │
│                           ▼                           │     │
│                      ┌─────────┐                      │     │
│                      │  OPEN   │───────────────────►│     │
│                      └────┬────┘   超时后              │     │
│                           │                          │     │
│              部分请求通过（探活）                        │     │
│                           │                          │     │
│                           ▼                          │     │
│                      ┌──────────────┐                │     │
│                      │ HALF_OPEN    │──成功──► CLOSED │     │
│                      └──────────────┘                │     │
│                           │                         │     │
│                           └──失败──► OPEN           │     │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 Go 实现熔断器

```go
// circuit_breaker.go

package breaker

import (
    "sync"
    "time"
)

type State int

const (
    Closed State = iota
    Open
    HalfOpen
)

type CircuitBreaker struct {
    mu               sync.Mutex
    state            State
    failureCount     int
    successCount     int
    threshold        int
    resetTimeout     time.Duration
    halfOpenMax      int
    lastFailure      time.Time
}

func NewCircuitBreaker(threshold, resetTimeout, halfOpenMax int) *CircuitBreaker {
    return &CircuitBreaker{
        threshold:     threshold,
        resetTimeout:  time.Duration(resetTimeout) * time.Second,
        halfOpenMax:   halfOpenMax,
    }
}

func (cb *CircuitBreaker) Execute(fn func() error) error {
    cb.mu.Lock()
    defer cb.mu.Unlock()
    
    switch cb.state {
    case Closed:
        return cb.executeClosed(fn)
    case Open:
        if time.Since(cb.lastFailure) > cb.resetTimeout {
            cb.state = HalfOpen
            cb.successCount = 0
            return cb.executeHalfOpen(fn)
        }
        return ErrCircuitOpen
    case HalfOpen:
        return cb.executeHalfOpen(fn)
    }
    return nil
}

func (cb *CircuitBreaker) executeClosed(fn func() error) error {
    err := fn()
    if err != nil {
        cb.failureCount++
        cb.lastFailure = time.Now()
        if cb.failureCount >= cb.threshold {
            cb.state = Open
        }
        return err
    }
    cb.failureCount = 0
    return nil
}

func (cb *CircuitBreaker) executeHalfOpen(fn func() error) error {
    err := fn()
    cb.successCount++
    
    if err != nil {
        cb.state = Open
        cb.lastFailure = time.Now()
        return err
    }
    
    if cb.successCount >= cb.halfOpenMax {
        cb.state = Closed
        cb.failureCount = 0
    }
    return nil
}
```

---

## 4. 异步化设计

### 4.1 异步架构模式

```
┌─────────────────────────────────────────────────────────────┐
│                    异步架构模式                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. 异步处理                                                 │
│     ├── 请求 → 消息队列 → 消费者异步处理                     │
│     └── 适用：耗时操作（邮件发送、报表生成）                    │
│                                                             │
│  2. 异步聚合                                                 │
│     ├── 并行调用多个服务，聚合结果                            │
│     └── 适用：需要聚合多个数据源                               │
│                                                             │
│  3. 异步补偿                                                 │
│     ├── 事务失败时异步补偿                                   │
│     └── 适用：分布式事务                                       │
│                                                             │
│  4. 异步编排                                                 │
│     ├── 复杂业务流程异步编排                                 │
│     └── 适用：长流程业务                                       │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 Go 异步编排

```go
// async_orchestration.go

package async

import (
    "context"
    "sync"
)

type AsyncOrchestrator struct {
    tasks []AsyncTask
}

type AsyncTask struct {
    Name     string
    Execute  func(context.Context) (interface{}, error)
    Timeout  time.Duration
}

type TaskResult struct {
    Name   string
    Value  interface{}
    Error  error
}

func (o *AsyncOrchestrator) Execute(ctx context.Context) ([]TaskResult, error) {
    var wg sync.WaitGroup
    results := make([]TaskResult, len(o.tasks))
    
    for i, task := range o.tasks {
        wg.Add(1)
        go func(idx int, t AsyncTask) {
            defer wg.Done()
            
            taskCtx, cancel := context.WithTimeout(ctx, t.Timeout)
            defer cancel()
            
            value, err := t.Execute(taskCtx)
            results[idx] = TaskResult{
                Name:  t.Name,
                Value: value,
                Error: err,
            }
        }(i, task)
    }
    
    wg.Wait()
    
    // 检查错误
    for _, result := range results {
        if result.Error != nil {
            return results, result.Error
        }
    }
    
    return results, nil
}
```

---

## 5. 性能优化

### 5.1 连接池优化

```go
// pool.go

package pool

import (
    "sync"
    "time"
)

type Pool struct {
    create   func() (interface{}, error)
    close    func(interface{}) error
    maxSize  int
    items    sync.Pool
}

func NewPool(create func() (interface{}, error), close func(interface{}) error, size int) *Pool {
    return &Pool{
        create:  create,
        close:   close,
        maxSize: size,
    }
}

func (p *Pool) Get() (interface{}, error) {
    if item := p.items.Get(); item != nil {
        return item, nil
    }
    return p.create()
}

func (p *Pool) Put(item interface{}) error {
    p.items.Put(item)
    return nil
}

func (p *Pool) Close() error {
    return nil
}
```

---

## 6. 总结

### 6.1 核心原理回顾

| 模块 | 核心机制 |
|------|----------|
| 限流 | 令牌桶/漏桶/滑动窗口 |
| 缓存 | 多级缓存/缓存穿透处理 |
| 熔断 | 状态机/半开探活 |
| 异步 | 异步编排/补偿 |

### 6.2 最佳实践

- [ ] 合理设置限流阈值
- [ ] 实现缓存穿透防护
- [ ] 配置熔断降级策略
- [ ] 异步化耗时操作
- [ ] 连接池复用

---

*最后更新：2026-08-11*
*作者：Ryan*
