# 微服务容错与弹性设计

> 深入微服务容错：熔断、降级、限流、重试、超时控制。
> 源码级分析，包含生产环境实践。
> 适用对象：微服务架构师、后端工程师

---

## 1. 熔断器模式

### 1.1 状态机

```
熔断器状态机：

┌──────────┐    失败率>阈值    ┌──────────┐    超时后    ┌──────────┐
│  关闭     │─────────────────>│  半开    │───────────>│  开启   │
│  Closed   │                  │  Half-   │            │  Open   │
│           │<─────────────────│  Open    │            │          │
└──────────┘   恢复成功        └──────────┘            └──────────┘
```

### 1.2 Go 实现熔断器

```go
// circuit_breaker.go

package resilience

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
    failureThreshold int
    timeout          time.Duration
    lastFailureTime  time.Time
}

func NewCircuitBreaker(failureThreshold int, timeout time.Duration) *CircuitBreaker {
    return &CircuitBreaker{
        state:            Closed,
        failureThreshold: failureThreshold,
        timeout:          timeout,
    }
}

func (cb *CircuitBreaker) Execute(fn func() error) error {
    cb.mu.Lock()
    state := cb.state
    cb.mu.Unlock()
    
    if state == Open {
        if time.Since(cb.lastFailureTime) > cb.timeout {
            cb.mu.Lock()
            cb.state = HalfOpen
            cb.mu.Unlock()
        } else {
            return ErrCircuitOpen
        }
    }
    
    err := fn()
    
    cb.mu.Lock()
    defer cb.mu.Unlock()
    
    if err != nil {
        cb.failureCount++
        cb.successCount = 0
        cb.lastFailureTime = time.Now()
        
        if cb.failureCount >= cb.failureThreshold {
            cb.state = Open
        }
    } else {
        cb.successCount++
        cb.failureCount = 0
        
        if state == HalfOpen {
            cb.state = Closed
        }
    }
    
    return err
}
```

---

## 2. 限流算法

### 2.1 常见限流算法

```
┌────────────────┬─────────────────────────────┬──────────────┐
│ 算法           │ 原理                        │ 适用场景     │
├────────────────┼─────────────────────────────┼──────────────┤
│ 计数器         │ 固定窗口统计请求数            │ 简单限流     │
│ 滑动窗口       │ 细粒度统计                    │ 精确限流     │
│ 令牌桶         │ 匀速产生令牌                  │ 平滑流量     │
│ 漏桶           │ 匀速处理请求                  │ 流量整形     │
└────────────────┴─────────────────────────────┴──────────────┘
```

### 2.2 Go 实现令牌桶

```go
// token_bucket.go

package resilience

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

func NewTokenBucket(rate float64, maxTokens float64) *TokenBucket {
    return &TokenBucket{
        tokens:    maxTokens,
        maxTokens: maxTokens,
        rate:      rate,
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
    
    if tb.tokens >= 1 {
        tb.tokens--
        return true
    }
    return false
}

func (tb *TokenBucket) TryAcquire(n float64) bool {
    tb.mu.Lock()
    defer tb.mu.Unlock()
    
    now := time.Now()
    elapsed := now.Sub(tb.lastRefill).Seconds()
    tb.tokens += elapsed * tb.rate
    if tb.tokens > tb.maxTokens {
        tb.tokens = tb.maxTokens
    }
    tb.lastRefill = now
    
    if tb.tokens >= n {
        tb.tokens -= n
        return true
    }
    return false
}
```

---

## 3. 重试策略

### 3.1 重试类型

```
重试策略：

├── 立即重试
│   └── 连续失败立即重试

├── 固定间隔重试
│   └── 每次间隔相同时间

├── 指数退避
│   └── 间隔时间指数增长

└── 抖动退避
    └── 随机化退避时间
```

### 3.2 Go 实现重试

```go
// retry.go

package resilience

import (
    "context"
    "math/rand"
    "time"
)

type RetryConfig struct {
    MaxRetries    int
    BaseDelay     time.Duration
    MaxDelay      time.Duration
    BackoffFactor float64
    Jitter        bool
}

func Retry(ctx context.Context, fn func() error, config RetryConfig) error {
    var err error
    delay := config.BaseDelay
    
    for i := 0; i <= config.MaxRetries; i++ {
        err = fn()
        if err == nil {
            return nil
        }
        
        if i == config.MaxRetries {
            break
        }
        
        select {
        case <-ctx.Done():
            return ctx.Err()
        case <-time.After(delay):
        }
        
        // 指数退避
        delay = time.Duration(float64(delay) * config.BackoffFactor)
        if delay > config.MaxDelay {
            delay = config.MaxDelay
        }
        
        // 抖动
        if config.Jitter {
            jitter := time.Duration(rand.Float64() * float64(delay) * 0.5)
            delay += jitter
        }
    }
    
    return err
}
```

---

## 4. 降级策略

### 4.1 降级类型

```
降级策略：

├── 功能降级
│   ├── 返回默认值
│   └── 返回缓存数据
│
├── 服务降级
│   ├── 关闭非核心功能
│   └── 简化服务逻辑
│
└── 数据降级
    ├── 返回本地数据
    └── 返回降级数据
```

### 4.2 Go 实现降级

```go
// fallback.go

package resilience

import (
    "context"
    "sync"
)

type Fallback struct {
    primary   func(ctx context.Context) (interface{}, error)
    fallback  func(ctx context.Context) (interface{}, error)
    cache     sync.Map
}

func NewFallback(primary, fallback func(ctx context.Context) (interface{}, error)) *Fallback {
    return &Fallback{
        primary:  primary,
        fallback: fallback,
    }
}

func (fb *Fallback) Execute(ctx context.Context) (interface{}, error) {
    // 尝试主逻辑
    result, err := fb.primary(ctx)
    if err == nil {
        return result, nil
    }
    
    // 降级逻辑
    return fb.fallback(ctx)
}
```

---

## 5. 超时控制

### 5.1 超时策略

```
超时控制策略：

├── 请求超时
│   └── 单个请求最大等待时间

├── 连接超时
│   └── 建立连接最大时间

├── 读写超时
│   └── 数据读写最大时间

└── 整体超时
    └── 整个调用最大时间
```

### 5.2 Go 实现超时

```go
// timeout.go

package resilience

import (
    "context"
    "time"
)

type TimeoutManager struct {
    defaultTimeout time.Duration
}

func NewTimeoutManager(timeout time.Duration) *TimeoutManager {
    return &TimeoutManager{
        defaultTimeout: timeout,
    }
}

func (tm *TimeoutManager) WithTimeout(ctx context.Context, fn func(context.Context) error) error {
    ctx, cancel := context.WithTimeout(ctx, tm.defaultTimeout)
    defer cancel()
    
    return fn(ctx)
}

func (tm *TimeoutManager) WithDeadline(ctx context.Context, deadline time.Time, fn func(context.Context) error) error {
    ctx, cancel := context.WithDeadline(ctx, deadline)
    defer cancel()
    
    return fn(ctx)
}
```

---

## 6. 总结

### 6.1 核心原理回顾

| 模式 | 作用 |
|------|------|
| 熔断器 | 防止级联失败 |
| 限流 | 控制流量峰值 |
| 重试 | 提高成功率 |
| 降级 | 保障核心功能 |
| 超时 | 防止雪崩 |

### 6.2 最佳实践

- [ ] 合理设置熔断阈值
- [ ] 使用指数退避重试
- [ ] 实现多级降级策略
- [ ] 设置合理的超时时间

---

*最后更新：2026-08-11*
*作者：Ryan*
