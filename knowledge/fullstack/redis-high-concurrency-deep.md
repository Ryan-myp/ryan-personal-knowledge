# Redis 高并发实战深度解析

> 深入 Redis 高并发场景：缓存穿透/击穿/雪崩、分布式锁、Lua 脚本、集群架构。
> 包含真实生产环境优化方案。
> 适用对象：后端工程师、DBA、系统架构师

---

## 1. 缓存问题深度解析

### 1.1 缓存穿透

```
问题：查询不存在的数据，绕过缓存直接查 DB

┌─────────────────────────────────────────────────────────────┐
│                    缓存穿透场景                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  用户请求 ID=-1 (不存在)                                     │
│       │                                                     │
│       ▼                                                     │
│  ┌─────────┐    缓存 miss    ┌─────────┐                  │
│  │ Redis   │ ──────────────► │   DB    │                  │
│  └─────────┘                 └─────────┘                  │
│       ▲                         │                         │
│       └──────── 空结果 ──────────┘                         │
│                                                             │
│  解决方案：                                                  │
│  1. 布隆过滤器预判断                                         │
│  2. 缓存空值（短 TTL）                                       │
│  3. 参数校验拦截                                             │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

```go
// bloom_filter.go

package cache

import (
    "github.com/bits-and-blooms/bloom/v3"
)

type CacheService struct {
    bloom *bloom.BloomFilter
    redis *RedisClient
}

func NewCacheService() *CacheService {
    return &CacheService{
        bloom: bloom.NewWithEstimates(1000000, 0.01),
    }
}

func (s *CacheService) Get(key string) (string, error) {
    // 1. 布隆过滤器检查
    if !s.bloom.TestString(key) {
        return "", ErrKeyNotExist
    }
    
    // 2. 缓存查询
    val, err := s.redis.Get(key)
    if err == RedisNil {
        // 3. 缓存空值
        s.redis.Set(key, "", 60*time.Second)
        return "", nil
    }
    
    return val, nil
}
```

### 1.2 缓存击穿

```
问题：热点 key 过期，大量请求同时打到 DB

┌─────────────────────────────────────────────────────────────┐
│                    缓存击穿场景                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  热点 key: user:10000                                        │
│       │                                                     │
│       ▼                                                     │
│  过期时间到达                                                │
│       │                                                     │
│       ▼                                                     │
│  大量并发请求同时 miss                                       │
│       │                                                     │
│       ▼                                                     │
│  ┌─────────┐    全部 miss    ┌─────────┐                    │
│  │ Redis   │ ──────────────► │   DB    │                    │
│  └─────────┘                 └─────────┘                    │
│                                                             │
│  解决方案：                                                  │
│  1. 热点 key 永不过期                                        │
│  2. 分布式锁保证单请求回源                                    │
│  3. 预加热热点数据                                           │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 1.3 缓存雪崩

```
问题：大量 key 同时过期，DB 压力骤增

┌─────────────────────────────────────────────────────────────┐
│                    缓存雪崩场景                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  同一时间大量 key 过期                                        │
│       │                                                     │
│       ▼                                                     │
│  所有请求同时 miss                                           │
│       │                                                     │
│       ▼                                                     │
│  ┌─────────┐    全部 miss    ┌─────────┐                    │
│  │ Redis   │ ──────────────► │   DB    │                    │
│  └─────────┘                 └─────────┘                    │
│                                                             │
│  解决方案：                                                  │
│  1. TTL 加随机值分散过期时间                                  │
│  2. 多级缓存                                                 │
│  3. 限流降级                                                 │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. 分布式锁

### 2.1 Redisson 实现

```go
// redislock.go

package lock

import (
    "context"
    "time"
    
    "github.com/mediocregopher/radix/v3"
)

type Redlock struct {
    clients []*radix.Client
    key     string
    ttl     time.Duration
}

func NewRedlock(addrs []string, key string, ttl time.Duration) *Redlock {
    clients := make([]*radix.Client, len(addrs))
    for i, addr := range addrs {
        clients[i] = radix.New(addr)
    }
    return &Redlock{
        clients: clients,
        key:     key,
        ttl:     ttl,
    }
}

func (l *Redlock) Lock(ctx context.Context) (bool, error) {
    // SET key value NX PX ttl
    var result bool
    var err error
    
    for _, client := range l.clients {
        err = client.Do(radix.Cmd(&result, "SET", l.key, uuid.New(), "NX", "PX", l.ttl.Milliseconds()))
        if err != nil {
            return false, err
        }
        if result {
            return true, nil
        }
    }
    
    return false, nil
}

func (l *Redlock) Unlock(ctx context.Context) error {
    // Lua 脚本原子删除
    script := `
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
    `
    
    for _, client := range l.clients {
        err := client.Do(radix.Cmd(nil, "EVAL", script, 1, l.key, l.value))
        if err != nil {
            return err
        }
    }
    return nil
}
```

### 2.2 看门狗机制

```go
// watchdog.go

package lock

import (
    "context"
    "sync"
    "time"
)

type Watchdog struct {
    lock     *Redlock
    renewPeriod time.Duration
    stopCh   chan struct{}
    mu       sync.Mutex
}

func NewWatchdog(lock *Redlock, renewPeriod time.Duration) *Watchdog {
    return &Watchdog{
        lock:        lock,
        renewPeriod: renewPeriod,
    }
}

func (w *Watchdog) Start(ctx context.Context) {
    w.mu.Lock()
    defer w.mu.Unlock()
    
    if w.stopCh != nil {
        close(w.stopCh)
    }
    
    w.stopCh = make(chan struct{})
    
    go func() {
        ticker := time.NewTicker(w.renewPeriod)
        defer ticker.Stop()
        
        for {
            select {
            case <-ctx.Done():
                return
            case <-w.stopCh:
                return
            case <-ticker.C:
                w.lock.extendTTL()
            }
        }
    }()
}

func (w *Watchdog) Stop() {
    w.mu.Lock()
    defer w.mu.Unlock()
    
    if w.stopCh != nil {
        close(w.stopCh)
        w.stopCh = nil
    }
}
```

---

## 3. Lua 脚本

### 3.1 原子操作

```lua
-- atomic_counter.lua

local key = KEYS[1]
local increment = tonumber(ARGV[1])

-- 原子递增并返回新值
local new_value = redis.call('INCRBY', key, increment)

-- 设置过期时间（只在第一次）
if new_value == increment then
    redis.call('EXPIRE', key, tonumber(ARGV[2]))
end

return new_value
```

### 3.2 Go 调用

```go
// lua_script.go

package cache

import (
    "context"
    "github.com/go-redis/redis/v8"
)

type LuaScript struct {
    client *redis.Client
}

func NewLuaScript(client *redis.Client) *LuaScript {
    return &LuaScript{client: client}
}

func (s *LuaScript) IncrementCounter(ctx context.Context, key string, amount int, ttl int) (int64, error) {
    script := redis.NewScript(`
        local new_value = redis.call('INCRBY', KEYS[1], ARGV[1])
        if new_value == tonumber(ARGV[1]) then
            redis.call('EXPIRE', KEYS[1], ARGV[2])
        end
        return new_value
    `)
    
    result, err := script.Run(ctx, s.client, []string{key}, amount, ttl).Int64()
    if err != nil {
        return 0, err
    }
    
    return result, nil
}
```

---

## 4. 集群架构

### 4.1 Redis Cluster

```
┌─────────────────────────────────────────────────────────────┐
│                    Redis Cluster 架构                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│                    ┌──────────┐                             │
│                    │  Master  │                             │
│                    │  Node 0  │                             │
│                    └────┬─────┘                             │
│                         │                                   │
│          ┌──────────────┼──────────────┐                    │
│          ▼              ▼              ▼                    │
│    ┌──────────┐  ┌──────────┐  ┌──────────┐               │
│    │ Replica  │  │  Master  │  │ Replica  │               │
│    │  Node 0  │  │  Node 1  │  │  Node 1  │               │
│    └──────────┘  └────┬─────┘  └────┬─────┘               │
│                       │             │                      │
│               ┌───────┴─────────────┴───────┐             │
│               ▼                           ▼              │
│        ┌──────────┐                  ┌──────────┐        │
│        │  Master  │                  │ Replica  │        │
│        │  Node 2  │                  │  Node 2  │        │
│        └──────────┘                  └──────────┘        │
│                                                             │
│  16384 个哈希槽，数据分片存储                                 │
│  故障自动转移，支持水平扩展                                   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 分片策略

```go
// shard_strategy.go

package cache

import (
    "hash/crc32"
)

type ShardStrategy struct {
    shards []*Shard
}

type Shard struct {
    client *redis.Client
    index  int
}

func NewShardStrategy(shards []*Shard) *ShardStrategy {
    return &ShardStrategy{shards: shards}
}

func (s *ShardStrategy) GetShard(key string) *Shard {
    hash := crc32.ChecksumIEEE([]byte(key))
    index := int(hash) % len(s.shards)
    return s.shards[index]
}

func (s *ShardStrategy) Set(key, value string, ttl time.Duration) error {
    shard := s.GetShard(key)
    return shard.client.Set(key, value, ttl).Err()
}

func (s *ShardStrategy) Get(key string) (string, error) {
    shard := s.GetShard(key)
    return shard.client.Get(key).Result()
}
```

---

## 5. 性能优化

### 5.1 Pipeline 批量操作

```go
// pipeline.go

package cache

import (
    "context"
    "github.com/go-redis/redis/v8"
)

func PipelineSet(client *redis.Client, data map[string]string) error {
    pipe := client.Pipeline()
    
    for key, value := range data {
        pipe.Set(key, value, 0)
    }
    
    _, err := pipe.Exec(context.Background())
    return err
}

func PipelineGet(client *redis.Client, keys []string) (map[string]string, error) {
    pipe := client.Pipeline()
    
    var cmds []*redis.StringCmd
    for _, key := range keys {
        cmds = append(cmds, pipe.Get(key))
    }
    
    _, err := pipe.Exec(context.Background())
    if err != nil {
        return nil, err
    }
    
    result := make(map[string]string)
    for i, cmd := range cmds {
        val, _ := cmd.Result()
        result[keys[i]] = val
    }
    
    return result, nil
}
```

### 5.2 连接池配置

```go
// pool_config.go

package cache

import (
    "github.com/go-redis/redis/v8"
)

func NewRedisClient(addr string) *redis.Client {
    return redis.NewClient(&redis.Options{
        Addr:         addr,
        Password:     "",
        DB:           0,
        
        // 连接池配置
        PoolSize:     50,
        MinIdleConns: 10,
        MaxConnAge:   time.Hour,
        PoolTimeout:  time.Second * 4,
        IdleTimeout:  time.Minute * 5,
        
        // 重试配置
        MaxRetries:   3,
        RetryDelay:   time.Millisecond * 100,
        
        // 读写超时
        ReadTimeout:  time.Second * 3,
        WriteTimeout: time.Second * 3,
    })
}
```

---

## 6. 监控告警

### 6.1 关键指标

```go
// metrics.go

package cache

import "github.com/prometheus/client_golang/prometheus"

type Metrics struct {
    opsTotal    prometheus.Counter
    opsLatency  prometheus.Histogram
    hits        prometheus.Counter
    misses      prometheus.Counter
    evictions   prometheus.Counter
    connected   prometheus.Gauge
}

func NewMetrics() *Metrics {
    return &Metrics{
        opsTotal: prometheus.NewCounter(prometheus.CounterOpts{
            Name: "redis_ops_total",
            Help: "Total redis operations",
        }),
        opsLatency: prometheus.NewHistogram(prometheus.HistogramOpts{
            Name:    "redis_ops_latency_seconds",
            Help:    "Redis operation latency",
            Buckets: []float64{0.001, 0.005, 0.01, 0.05, 0.1, 0.5},
        }),
        hits: prometheus.NewCounter(prometheus.CounterOpts{
            Name: "redis_hits_total",
            Help: "Cache hits",
        }),
        misses: prometheus.NewCounter(prometheus.CounterOpts{
            Name: "redis_misses_total",
            Help: "Cache misses",
        }),
        evictions: prometheus.NewCounter(prometheus.CounterOpts{
            Name: "redis_evictions_total",
            Help: "Cache evictions",
        }),
        connected: prometheus.NewGauge(prometheus.GaugeOpts{
            Name: "redis_connected_clients",
            Help: "Connected clients",
        }),
    }
}
```

---

## 7. 总结

### 7.1 核心原理回顾

| 模块 | 核心机制 |
|------|----------|
| 缓存问题 | 布隆过滤器/分布式锁/随机 TTL |
| 分布式锁 | SET NX PX + Lua 脚本 |
| 集群 | 哈希槽分片 + 主从复制 |
| 性能 | Pipeline + 连接池 |

### 7.2 最佳实践

- [ ] 设置合理 TTL
- [ ] 使用 Pipeline 批量操作
- [ ] 配置连接池
- [ ] 监控关键指标
- [ ] 处理缓存穿透/击穿/雪崩

---

*最后更新：2026-08-11*
*作者：Ryan*
