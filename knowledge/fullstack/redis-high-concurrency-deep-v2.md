# Redis 高并发实战深度解析

> 深入 Redis 高并发场景：分布式锁、缓存穿透、缓存雪崩、热点 Key。
> 源码级分析，包含生产环境解决方案。
> 适用对象：后端工程师、DBA、架构师

---

## 1. Redis 高并发场景

### 1.1 缓存穿透

```
缓存穿透问题：
├── 查询不存在的数据
├── 每次都打到数据库
└── 可能导致数据库崩溃

解决方案：
├── 布隆过滤器 (Bloom Filter)
├── 缓存空值
└── 接口层校验
```

### 1.2 Go 实现布隆过滤器

```go
// bloom_filter.go

package redis

import (
    "github.com/bits-and-blooms/bloom/v3"
)

type CacheBloomFilter struct {
    bloom *bloom.BloomFilter
}

func NewCacheBloomFilter(expectedItems, falsePositiveRate float64) *CacheBloomFilter {
    return &CacheBloomFilter{
        bloom: bloom.NewWithEstimates(uint64(expectedItems), falsePositiveRate),
    }
}

func (bf *CacheBloomFilter) Add(key string) {
    bf.bloom.Add([]byte(key))
}

func (bf *CacheBloomFilter) MightExist(key string) bool {
    return bf.bloom.Test([]byte(key))
}

func (bf *CacheBloomFilter) LoadFromDB(keys []string) {
    for _, key := range keys {
        bf.Add(key)
    }
}
```

### 1.3 缓存雪崩

```
缓存雪崩问题：
├── 大量 Key 同时过期
├── 请求全部打到数据库
└── 数据库压力激增

解决方案：
├── 过期时间加随机值
├── 多级缓存
└── 限流降级
```

---

## 2. 热点 Key

### 2.1 问题分析

```
热点 Key 问题：
├── 单个 Key 访问量巨大
├── Redis 单线程瓶颈
└── 网络带宽限制

解决方案：
├── 本地缓存 (L1) + Redis (L2)
├── 热点 Key 本地缓存
└── 分片存储
```

### 2.2 Go 实现热点 Key 缓存

```go
// hot_key_cache.go

package redis

import (
    "sync"
    "time"
)

type HotKeyCache struct {
    local  *LocalCache
    remote *RedisClient
    mu     sync.RWMutex
}

type LocalCache struct {
    items    sync.Map
    capacity int
}

func NewHotKeyCache(remote *RedisClient, localCapacity int) *HotKeyCache {
    return &HotKeyCache{
        local: &LocalCache{capacity: localCapacity},
        remote: remote,
    }
}

func (hkc *HotKeyCache) Get(key string) (string, error) {
    // L1: 本地缓存
    if v, ok := hkc.local.Get(key); ok {
        return v, nil
    }
    
    // L2: Redis
    v, err := hkc.remote.Get(key)
    if err != nil {
        return "", err
    }
    
    // 回填本地缓存
    hkc.local.Set(key, v)
    return v, nil
}

func (lc *LocalCache) Get(key string) (string, bool) {
    if v, ok := lc.items.Load(key); ok {
        return v.(string), true
    }
    return "", false
}

func (lc *LocalCache) Set(key, value string) {
    lc.items.Store(key, value)
}
```

---

## 3. 分布式锁

### 3.1 Redis 分布式锁

```
Redis 分布式锁实现 (SET NX EX)：

1. 获取锁
   SET lock_key unique_value NX EX timeout

2. 释放锁
   Lua 脚本原子检查+删除

3. 看门狗续期
   后台 goroutine 定期续期
```

### 3.2 Go 实现 Redis 锁

```go
// redis_lock.go

package redis

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
```

---

## 4. 缓存一致性

### 4.1 更新策略

```
缓存更新策略对比：

┌────────────────┬────────────┬────────────┬──────────────┐
│ 策略           │ 一致性     │ 性能       │ 适用场景     │
├────────────────┼────────────┼────────────┼──────────────┤
│ Cache-Aside    │ 最终一致   │ 高         │ 读多写少     │
│ Read-Through   │ 最终一致   │ 中         │ 透明缓存     │
│ Write-Through  │ 强一致     │ 低         │ 强一致要求   │
│ Write-Behind   │ 最终一致   │ 高         │ 高写入量     │
└────────────────┴────────────┴────────────┴──────────────┘
```

### 4.2 Go 实现 Cache-Aside

```go
// cache_aside.go

package redis

import (
    "github.com/go-redis/redis/v8"
)

type CacheAside struct {
    rdb *redis.Client
}

func (ca *CacheAside) Get(key string, fn func() (interface{}, error)) (interface{}, error) {
    // 1. 查缓存
    v, err := ca.rdb.Get(context.Background(), key).Result()
    if err == nil {
        return v, nil
    }
    
    // 2. 查数据库
    data, err := fn()
    if err != nil {
        return nil, err
    }
    
    // 3. 写缓存
    ca.rdb.Set(context.Background(), key, data, 5*time.Minute)
    return data, nil
}

func (ca *CacheAside) Invalidate(key string) error {
    return ca.rdb.Del(context.Background(), key).Err()
}
```

---

## 5. Redis 集群

### 5.1 集群架构

```
Redis Cluster 架构：

├── 16384 个哈希槽
├── 3 主 3 从 (最小配置)
├── 主节点处理读写
└── 从节点复制主节点
```

### 5.2 Go 实现集群客户端

```go
// redis_cluster.go

package redis

import (
    "github.com/go-redis/redis/v8"
)

func NewClusterClient(addrs []string) *redis.ClusterClient {
    return redis.NewClusterClient(&redis.ClusterOptions{
        Addrs:      addrs,
        MaxRetries: 3,
    })
}

func (rc *ClusterClient) Get(key string) (string, error) {
    slot := redis.CRC16([]byte(key)) % 16384
    // 路由到对应节点
    return rc.Client.ForSlot(slot).Get(context.Background(), key).Result()
}
```

---

## 6. 性能优化

### 6.1  Pipeline 批量操作

```
Pipeline 优化：

1. 单次 RTT 执行多条命令
2. 减少网络往返
3. 注意：Pipeline 不是原子操作
```

### 6.2 Go 实现 Pipeline

```go
// pipeline.go

package redis

import (
    "context"
    "github.com/go-redis/redis/v8"
)

func PipelineSet(rdb *redis.Client, keys []string, values []interface{}) error {
    pipe := rdb.Pipeline()
    for i, key := range keys {
        pipe.Set(context.Background(), key, values[i], 5*time.Minute)
    }
    _, err := pipe.Exec(context.Background())
    return err
}

func PipelineGet(rdb *redis.Client, keys []string) ([]interface{}, error) {
    pipe := rdb.Pipeline()
    for _, key := range keys {
        pipe.Get(context.Background(), key)
    }
    cmders, err := pipe.Exec(context.Background())
    if err != nil {
        return nil, err
    }
    
    results := make([]interface{}, len(cmders))
    for i, cmder := range cmders {
        results[i] = cmder.(*redis.StringCmd).Val()
    }
    return results, nil
}
```

---

## 7. 总结

### 7.1 核心原理回顾

| 场景 | 解决方案 |
|------|----------|
| 缓存穿透 | 布隆过滤器/空值缓存 |
| 缓存雪崩 | 随机过期/多级缓存 |
| 热点 Key | 本地缓存 + Redis |
| 分布式锁 | SET NX EX + Lua |
| 一致性 | Cache-Aside 模式 |

### 7.2 最佳实践

- [ ] 设置合理的过期时间
- [ ] 使用 Pipeline 批量操作
- [ ] 监控 Redis 性能指标
- [ ] 建立多级缓存架构
- [ ] 合理设计分布式锁

---

*最后更新：2026-08-11*
*作者：Ryan*
