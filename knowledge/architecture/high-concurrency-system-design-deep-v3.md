# 高并发系统设计深度解析

> 深入高并发系统设计：限流、熔断、缓存、消息队列、分布式锁。
> 源码级分析，包含生产环境最佳实践。
> 适用对象：架构师、后端工程师

---

## 1. 限流算法

### 1.1 令牌桶算法

```
令牌桶算法原理：

┌─────────────────────────────────────────────────────────────┐
│                    令牌桶结构                                │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────┐                                               │
│  │ 桶      │ ← 容量：最多容纳 N 个令牌                      │
│  │         │                                               │
│  └────┬────┘                                               │
│       │                                                    │
│  ┌────▼────┐    令牌以固定速率产生                         │
│  │ 产生器  │ → 每秒产生 k 个令牌                          │
│  └─────────┘                                               │
│                                                             │
│  请求处理：                                                  │
│  ├── 有令牌 → 消耗令牌，处理请求                            │
│  └── 无令牌 → 拒绝或排队                                    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 Go 实现令牌桶

```go
// token_bucket.go

package concurrency

import (
    "sync"
    "time"
)

type TokenBucket struct {
    capacity int
    tokens   int
    rate     int // 令牌产生速率（每秒）
    lastTime time.Time
    mu       sync.Mutex
}

func NewTokenBucket(capacity, rate int) *TokenBucket {
    return &TokenBucket{
        capacity: capacity,
        tokens:   capacity,
        rate:     rate,
        lastTime: time.Now(),
    }
}

func (tb *TokenBucket) Allow() bool {
    tb.mu.Lock()
    defer tb.mu.Unlock()
    
    now := time.Now()
    elapsed := now.Sub(tb.lastTime).Seconds()
    
    // 补充令牌
    tb.tokens += int(elapsed * float64(tb.rate))
    if tb.tokens > tb.capacity {
        tb.tokens = tb.capacity
    }
    tb.lastTime = now
    
    // 消耗令牌
    if tb.tokens >= 1 {
        tb.tokens--
        return true
    }
    return false
}
```

---

## 2. 熔断器模式

### 2.1 状态机

```
熔断器状态机：

┌──────────┐    失败率>阈值    ┌──────────┐    超时后    ┌──────────┐
│  关闭     │────────────────→│  打开     │──────────→│  半开    │
│  (Closed) │                 │ (Open)    │           │ (Half)   │
│          │←────────────────│          │←──────────│          │
│ 正常处理  │   成功恢复       │ 拒绝请求  │   探测    │ 探测请求  │
└──────────┘                 └──────────┘           └──────────┘

状态转换条件：
├── Closed → Open: 失败率超过阈值（如50%）
├── Open → Half:   超时时间到（如30秒）
└── Half → Closed: 探测成功
   Half → Open:    探测失败
```

### 2.2 Go 实现熔断器

```go
// circuit_breaker.go

package concurrency

import (
    "sync"
    "time"
)

type CircuitState int

const (
    Closed CircuitState = iota
    Open
    HalfOpen
)

type CircuitBreaker struct {
    state         CircuitState
    failureCount  int
    successCount  int
    threshold     int
    timeout       time.Duration
    lastFailTime  time.Time
    mu            sync.Mutex
}

func NewCircuitBreaker(threshold int, timeout time.Duration) *CircuitBreaker {
    return &CircuitBreaker{
        state:     Closed,
        threshold: threshold,
        timeout:   timeout,
    }
}

func (cb *CircuitBreaker) Execute(fn func() error) error {
    cb.mu.Lock()
    defer cb.mu.Unlock()
    
    switch cb.state {
    case Closed:
        return cb.executeClosed(fn)
    case Open:
        return cb.executeOpen(fn)
    case HalfOpen:
        return cb.executeHalfOpen(fn)
    }
    return nil
}

func (cb *CircuitBreaker) executeClosed(fn func() error) error {
    err := fn()
    if err != nil {
        cb.failureCount++
        if cb.failureCount >= cb.threshold {
            cb.state = Open
            cb.lastFailTime = time.Now()
        }
    } else {
        cb.failureCount = 0
    }
    return err
}

func (cb *CircuitBreaker) executeOpen(fn func() error) error {
    if time.Since(cb.lastFailTime) > cb.timeout {
        cb.state = HalfOpen
        cb.successCount = 0
        return cb.executeHalfOpen(fn)
    }
    return ErrCircuitOpen
}

func (cb *CircuitBreaker) executeHalfOpen(fn func() error) error {
    err := fn()
    if err != nil {
        cb.state = Open
        cb.lastFailTime = time.Now()
    } else {
        cb.successCount++
        if cb.successCount >= 3 {
            cb.state = Closed
            cb.failureCount = 0
        }
    }
    return err
}
```

---

## 3. 分布式锁

### 3.1 Redis 分布式锁

```
Redis 分布式锁实现：

┌─────────────────────────────────────────────────────────────┐
│                    Redis 锁结构                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  SET key value NX PX milliseconds                          │
│  ├── NX: 不存在才设置                                       │
│  └── PX: 过期时间（毫秒）                                   │
│                                                             │
│  释放锁（Lua 脚本）：                                        │
│  ├── 检查 value 是否匹配                                    │
│  └── 删除 key                                               │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 Go 实现分布式锁

```go
// distributed_lock.go

package concurrency

import (
    "context"
    "crypto/rand"
    "encoding/hex"
    "time"
)

type DistributedLock struct {
    key      string
    value    string
    ttl      time.Duration
    redis    *RedisClient
}

func NewDistributedLock(key string, ttl time.Duration, redis *RedisClient) *DistributedLock {
    // 生成唯一值
    bytes := make([]byte, 16)
    rand.Read(bytes)
    value := hex.EncodeToString(bytes)
    
    return &DistributedLock{
        key:   key,
        value: value,
        ttl:   ttl,
        redis: redis,
    }
}

func (dl *DistributedLock) Acquire(ctx context.Context) bool {
    // SET key value NX PX ttl
    return dl.redis.SetNX(ctx, dl.key, dl.value, dl.ttl)
}

func (dl *DistributedLock) Release(ctx context.Context) bool {
    // Lua 脚本释放锁
    script := `
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
    `
    return dl.redis.Eval(ctx, script, []string{dl.key}, dl.value)
}

// Redlock 算法（多Redis实例）
type Redlock struct {
    locks   []*DistributedLock
    quorum  int
    ttl     time.Duration
}

func NewRedlock(n int, ttl time.Duration) *Redlock {
    locks := make([]*DistributedLock, n)
    for i := 0; i < n; i++ {
        locks[i] = NewDistributedLock("lock", ttl, nil)
    }
    return &Redlock{
        locks:  locks,
        quorum: n/2 + 1,
        ttl:    ttl,
    }
}

func (rm *Redlock) Acquire(ctx context.Context) bool {
    acquired := 0
    startTime := time.Now()
    
    for _, lock := range rm.locks {
        if lock.Acquire(ctx) {
            acquired++
        }
    }
    
    // 计算实际锁持有时间
    elapsed := time.Since(startTime)
    validTTL := rm.ttl - elapsed
    
    if acquired >= rm.quorum {
        // 续期
        for _, lock := range rm.locks {
            if lock.IsHeld() {
                lock.Extend(ctx, validTTL)
            }
        }
        return true
    }
    
    // 释放已获取的锁
    for _, lock := range rm.locks {
        if lock.IsHeld() {
            lock.Release(ctx)
        }
    }
    return false
}
```

---

## 4. 缓存策略

### 4.1 缓存穿透/击穿/雪崩

```
缓存问题及解决方案：

┌─────────────────────────────────────────────────────────────┐
│  问题          │  原因                    │  解决方案         │
├─────────────────────────────────────────────────────────────┤
│  缓存穿透      │  查询不存在的数据         │  布隆过滤器        │
│  缓存击穿      │  热点key过期              │  永不过期/互斥锁   │
│  缓存雪崩      │  大量key同时过期          │  随机过期时间      │
│  缓存命中率低  │  数据访问不均匀           │  本地缓存+分布式   │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 Go 实现缓存防护

```go
// cache_protection.go

package concurrency

import (
    "sync"
    "time"
)

// 布隆过滤器
type BloomFilter struct {
    bits     []bool
    hashFuncs []func(string) uint32
    size     int
}

func NewBloomFilter(expectedItems int, falsePositiveRate float64) *BloomFilter {
    // 计算最优位数组大小和哈希函数数量
    size := int(-float64(expectedItems) * math.Log(falsePositiveRate) / math.Pow(math.Log(2), 2))
    k := int(float64(size) / float64(expectedItems) * math.Log(2))
    
    return &BloomFilter{
        bits:     make([]bool, size),
        hashFuncs: generateHashFunctions(k),
        size:     size,
    }
}

func (bf *BloomFilter) Add(item string) {
    for _, hash := range bf.hashFuncs {
        idx := hash(item) % uint32(bf.size)
        bf.bits[idx] = true
    }
}

func (bf *BloomFilter) MightContain(item string) bool {
    for _, hash := range bf.hashFuncs {
        idx := hash(item) % uint32(bf.size)
        if !bf.bits[idx] {
            return false
        }
    }
    return true
}

// 热点 Key 保护
type HotKeyProtector struct {
    localCache  *LocalCache
    distCache   *DistributedCache
    mu          sync.RWMutex
}

func NewHotKeyProtector() *HotKeyProtector {
    return &HotKeyProtector{
        localCache: NewLocalCache(1000),
        distCache:  NewDistributedCache(),
    }
}

func (hkp *HotKeyProtector) Get(key string) (string, bool) {
    // 1. 本地缓存
    if val, ok := hkp.localCache.Get(key); ok {
        return val, true
    }
    
    // 2. 分布式缓存
    val, ok := hkp.distCache.Get(key)
    if ok {
        hkp.localCache.Set(key, val)
        return val, true
    }
    
    return "", false
}

func (hkp *HotKeyProtector) Set(key, value string, ttl time.Duration) {
    hkp.localCache.Set(key, value)
    hkp.distCache.Set(key, value, ttl)
}

// 互斥锁防止缓存击穿
type MutexCache struct {
    cache   map[string]*CacheEntry
    mutexes map[string]*sync.Mutex
    mu      sync.Mutex
}

func NewMutexCache() *MutexCache {
    return &MutexCache{
        cache:   make(map[string]*CacheEntry),
        mutexes: make(map[string]*sync.Mutex),
    }
}

func (mc *MutexCache) Get(key string, fetchFunc func() (string, error)) (string, error) {
    // 检查缓存
    if entry, ok := mc.cache[key]; ok {
        if !entry.IsExpired() {
            return entry.Value, nil
        }
    }
    
    // 获取互斥锁
    mc.mu.Lock()
    mutex, ok := mc.mutexes[key]
    if !ok {
        mutex = &sync.Mutex{}
        mc.mutexes[key] = mutex
    }
    mc.mu.Unlock()
    
    // 互斥获取
    mutex.Lock()
    defer mutex.Unlock()
    
    // 双重检查
    if entry, ok := mc.cache[key]; ok {
        if !entry.IsExpired() {
            return entry.Value, nil
        }
    }
    
    // 从数据源获取
    value, err := fetchFunc()
    if err != nil {
        return "", err
    }
    
    // 写入缓存
    mc.cache[key] = &CacheEntry{
        Value:   value,
        Expire:  time.Now().Add(5 * time.Minute),
    }
    
    return value, nil
}
```

---

## 5. 消息队列选型

### 5.1 场景对比

```
消息队列选型决策树：

                        需要消息队列？
                              │
              ┌───────────────┼───────────────┐
              │               │               │
         高吞吐          事务消息          灵活路由
              │               │               │
         Kafka            RocketMQ        RabbitMQ
              │               │               │
         日志收集         金融场景         企业应用
         流处理          支付场景         微服务
```

### 5.2 Go 实现消息队列

```go
// message_queue.go

package concurrency

import (
    "sync"
    "time"
)

type MessageQueue interface {
    Produce(topic string, message []byte) error
    Consume(topic string, handler func([]byte)) error
    Subscribe(topic string) (<-chan []byte, error)
}

type KafkaProducer struct {
    brokers []string
    topic   string
}

type KafkaConsumer struct {
    brokers []string
    topic   string
    group   string
}

type RocketMQProducer struct {
    nameServer string
    topic      string
}

type RocketMQConsumer struct {
    nameServer string
    topic      string
    group      string
}

type RabbitMQProducer struct {
    address  string
    exchange string
}

type RabbitMQConsumer struct {
    address  string
    queue    string
}

// 消息队列抽象
type AbstractMQ struct {
    produce  func(topic string, msg []byte) error
    consume  func(topic string, handler func([]byte))
    subscribe func(topic string) (<-chan []byte, error)
}

func NewAbstractMQ() *AbstractMQ {
    return &AbstractMQ{}
}

func (mq *AbstractMQ) SetProduce(fn func(topic string, msg []byte) error) {
    mq.produce = fn
}

func (mq *AbstractMQ) SetConsume(fn func(topic string, handler func([]byte))) {
    mq.consume = fn
}

func (mq *AbstractMQ) SetSubscribe(fn func(topic string) (<-chan []byte, error)) {
    mq.subscribe = fn
}
```

---

## 6. 总结

### 6.1 核心原理回顾

| 技术 | 作用 | 适用场景 |
|------|------|----------|
| 限流 | 控制流量 | 保护后端 |
| 熔断 | 故障隔离 | 高可用 |
| 分布式锁 | 协调控制 | 并发安全 |
| 缓存防护 | 数据安全 | 一致性 |
| 消息队列 | 异步解耦 | 削峰填谷 |

### 6.2 最佳实践

- [ ] 根据场景选择限流算法
- [ ] 合理配置熔断阈值
- [ ] 使用 Redlock 算法
- [ ] 防护缓存穿透/击穿/雪崩
- [ ] 选择合适的消息队列

---

*最后更新：2026-08-12*
*作者：Ryan*
