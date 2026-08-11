# 高并发系统设计深度解析

> 深入高并发系统设计：限流、熔断、缓存、消息队列、分布式锁。
> 包含真实生产环境架构设计。
> 适用对象：架构师、技术负责人、高级工程师

---

## 1. 限流算法

### 1.1 常见限流算法

```
┌─────────────────────────────────────────────────────────────┐
│                  限流算法对比                                │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  算法              │ 原理              │ 适用场景            │
├─────────────────────────────────────────────────────────────┤
│  固定窗口          │ 固定时间窗口计数   │ 简单场景            │
│  滑动窗口          │ 窗口细分滑动       │ 精确限流            │
│  令牌桶            │ 匀速产生令牌       │ 允许突发流量        │
│  漏桶              │ 匀速处理请求       │ 平滑流量            │
│  动态限流          │ 根据负载调整       │ 自适应场景          │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 Go 实现令牌桶

```go
// token_bucket.go

package limit

import (
    "sync"
    "time"
)

type TokenBucket struct {
    tokens     float64
    maxTokens  float64
    rate       float64 // 每秒产生令牌数
    lastRefill time.Time
    mu         sync.Mutex
}

func NewTokenBucket(maxTokens, rate float64) *TokenBucket {
    return &TokenBucket{
        tokens:     maxTokens,
        maxTokens:  maxTokens,
        rate:       rate,
        lastRefill: time.Now(),
    }
}

func (tb *TokenBucket) Allow() bool {
    tb.mu.Lock()
    defer tb.mu.Unlock()
    
    now := time.Now()
    elapsed := now.Sub(tb.lastRefill).Seconds()
    tb.tokens = min(tb.maxTokens, tb.tokens+elapsed*tb.rate)
    tb.lastRefill = now
    
    if tb.tokens >= 1 {
        tb.tokens--
        return true
    }
    return false
}

func min(a, b float64) float64 {
    if a < b {
        return a
    }
    return b
}
```

---

## 2. 熔断降级

### 2.1 熔断器状态机

```
熔断器状态转换：

Closed (关闭) ──失败率超阈值──► Open (开启)
                                      │
                          ──超时时间到──┘
                          (半开状态测试)
                          │
               ┌──────────┴──────────┐
               │                     │
          成功恢复            继续失败
               │                     │
               ▼                     ▼
          Closed              Open
```

### 2.2 Go 实现熔断器

```go
// circuit_breaker.go

package breaker

import (
    "sync"
    "time"
)

type State int

const (
    StateClosed State = iota
    StateOpen
    StateHalfOpen
)

type CircuitBreaker struct {
    mu               sync.Mutex
    state            State
    failureCount     int
    successCount     int
    timeout          time.Duration
    lastFailTime     time.Time
    failureThreshold int
    successThreshold int
}

func NewCircuitBreaker(failureThreshold, successThreshold int, timeout time.Duration) *CircuitBreaker {
    return &CircuitBreaker{
        failureThreshold: failureThreshold,
        successThreshold: successThreshold,
        timeout:          timeout,
    }
}

func (cb *CircuitBreaker) Execute(fn func() error) error {
    cb.mu.Lock()
    defer cb.mu.Unlock()
    
    switch cb.state {
    case StateOpen:
        if time.Since(cb.lastFailTime) > cb.timeout {
            cb.state = StateHalfOpen
            cb.successCount = 0
        } else {
            return ErrCircuitOpen
        }
    case StateHalfOpen:
        // 允许少量请求测试
    }
    
    err := fn()
    if err != nil {
        cb.failureCount++
        cb.lastFailTime = time.Now()
        if cb.failureCount >= cb.failureThreshold {
            cb.state = StateOpen
        }
        return err
    }
    
    cb.successCount++
    if cb.state == StateHalfOpen && cb.successCount >= cb.successThreshold {
        cb.state = StateClosed
        cb.failureCount = 0
    }
    return nil
}
```

---

## 3. 分布式锁

### 3.1 Redis 分布式锁

```
Redis 分布式锁实现 (SET NX EX)：

┌─────────────────────────────────────────────────────────────┐
│                  Redis 锁流程                                │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  获取锁                                                      │
│  └── SET lock_key unique_value NX EX timeout               │
│                                                             │
│  释放锁                                                      │
│  └── 检查 value 是否匹配（防止误删）                         │
│      └── DEL lock_key                                       │
│                                                             │
│  看门狗续期                                                   │
│  └── 后台 goroutine 定期续期                                │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 Go 实现 Redis 锁

```go
// redis_lock.go

package lock

import (
    "context"
    "fmt"
    "sync"
    "time"
    
    "github.com/go-redis/redis/v8"
)

type RedisLock struct {
    client   *redis.Client
    key      string
    value    string
    ttl      time.Duration
    renewCh  chan struct{}
    cancelled bool
    mu       sync.Mutex
}

func NewRedisLock(client *redis.Client, key string, ttl time.Duration) *RedisLock {
    return &RedisLock{
        client: client,
        key:    key,
        value:  fmt.Sprintf("%d", time.Now().UnixNano()),
        ttl:    ttl,
    }
}

func (l *RedisLock) Lock(ctx context.Context) (bool, error) {
    result, err := l.client.SetNX(ctx, l.key, l.value, l.ttl).Result()
    if err != nil {
        return false, err
    }
    if result {
        l.startRenew(ctx)
    }
    return result, nil
}

func (l *RedisLock) Unlock(ctx context.Context) error {
    // Lua 脚本原子检查+删除
    script := `
        if redis.call("get",KEYS[1]) == ARGV[1] then
            return redis.call("del",KEYS[1])
        else
            return 0
        end
    `
    _, err := l.client.Eval(ctx, script, []string{l.key}, l.value).Result()
    if err != nil {
        return err
    }
    l.cancelRenew()
    return nil
}

func (l *RedisLock) startRenew(ctx context.Context) {
    go func() {
        ticker := time.NewTicker(l.ttl / 3)
        defer ticker.Stop()
        for {
            select {
            case <-ctx.Done():
                return
            case <-l.renewCh:
                return
            case <-ticker.C:
                l.client.Expire(ctx, l.key, l.ttl)
            }
        }
    }()
}

func (l *RedisLock) cancelRenew() {
    l.mu.Lock()
    defer l.mu.Unlock()
    l.cancelled = true
    close(l.renewCh)
}
```

---

## 4. 多级缓存

### 4.1 缓存架构

```
多级缓存架构：

┌─────────────────────────────────────────────────────────────┐
│                    多级缓存                                  │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  L1: 进程内缓存 (Local Cache)                                │
│  ├── sync.Map / map                                        │
│  ├── Caffeine / ThreeTenBP                                  │
│  └── TTL: 秒级                                             │
│                                                             │
│  L2: 分布式缓存 (Redis/Memcached)                           │
│  ├── 集群部署                                                │
│  ├── 持久化                                                  │
│  └── TTL: 分钟~小时级                                        │
│                                                             │
│  L3: 数据库 (MySQL/PostgreSQL)                               │
│  └── 持久化存储                                              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 Go 实现多级缓存

```go
// multi_level_cache.go

package cache

import (
    "sync"
    "time"
)

type CacheEntry struct {
    Value     interface{}
    ExpiresAt time.Time
}

type LocalCache struct {
    items sync.Map
    ttl   time.Duration
}

func (lc *LocalCache) Get(key string) (interface{}, bool) {
    if v, ok := lc.items.Load(key); ok {
        entry := v.(*CacheEntry)
        if time.Now().Before(entry.ExpiresAt) {
            return entry.Value, true
        }
        lc.items.Delete(key)
    }
    return nil, false
}

func (lc *LocalCache) Set(key string, value interface{}) {
    lc.items.Store(key, &CacheEntry{
        Value:     value,
        ExpiresAt: time.Now().Add(lc.ttl),
    })
}

type MultiLevelCache struct {
    local  *LocalCache
    remote *RemoteCache
}

func (mc *MultiLevelCache) Get(key string) (interface{}, bool) {
    // L1: 本地缓存
    if v, ok := mc.local.Get(key); ok {
        return v, true
    }
    
    // L2: 远程缓存
    if v, ok := mc.remote.Get(key); ok {
        // 回填本地缓存
        mc.local.Set(key, v)
        return v, true
    }
    
    return nil, false
}
```

---

## 5. 消息队列削峰

### 5.1 削峰架构

```
消息队列削峰架构：

┌─────────────────────────────────────────────────────────────┐
│                  削峰架构                                    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  流量洪峰                                                    │
│  └──► 消息队列 (Kafka/RabbitMQ)                            │
│         └──► 消费者（固定速率处理）                          │
│               └──► 后端服务                                  │
│                                                             │
│  优点：                                                      │
│  ├── 平滑流量                                              │
│  ├── 解耦系统                                                │
│  └── 提高系统稳定性                                          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 6. 总结

### 6.1 核心原理回顾

| 模块 | 核心机制 |
|------|----------|
| 限流 | 令牌桶/漏桶 |
| 熔断 | 状态机模型 |
| 分布式锁 | Redis SETNX |
| 缓存 | 多级缓存 |
| 削峰 | 消息队列 |

### 6.2 最佳实践

- [ ] 合理配置限流阈值
- [ ] 熔断降级保护下游
- [ ] 分布式锁防误删
- [ ] 多级缓存提升性能
- [ ] 消息队列削峰平滑

---

*最后更新：2026-08-11*
*作者：Ryan*
