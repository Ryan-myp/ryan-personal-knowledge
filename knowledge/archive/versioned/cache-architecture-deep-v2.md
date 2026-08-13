# 缓存架构深度解析

> 深入缓存架构：多级缓存、缓存一致性、缓存穿透/击穿/雪崩。
> 源码级分析，包含生产环境最佳实践。
> 适用对象：后端工程师、架构师

---

## 1. 多级缓存架构

### 1.1 缓存分层

```
多级缓存架构：

┌─────────────────────────────────────────────────────────────┐
│                    应用层缓存                                │
│  ├── L1: 本地缓存 (Caffeine/Guava)                         │
│  ├── L2: 分布式缓存 (Redis)                                 │
│  └── L3: 持久化存储 (DB)                                   │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 Go 实现多级缓存

```go
// multi_level_cache.go

package cache

import (
    "sync"
    "time"
)

type MultiLevelCache struct {
    l1 *LocalCache
    l2 *DistributedCache
    db *Database
}

type LocalCache struct {
    items  map[string]*cacheEntry
    mu     sync.RWMutex
    maxLen int
}

type DistributedCache struct {
    redis *RedisClient
}

type cacheEntry struct {
    value     interface{}
    expireAt  time.Time
}

func NewMultiLevelCache() *MultiLevelCache {
    return &MultiLevelCache{
        l1: NewLocalCache(10000),
        l2: NewDistributedCache(),
        db: NewDatabase(),
    }
}

func (mc *MultiLevelCache) Get(key string) (interface{}, bool) {
    // L1 本地缓存
    if val, ok := mc.l1.Get(key); ok {
        return val, true
    }
    
    // L2 分布式缓存
    if val, ok := mc.l2.Get(key); ok {
        mc.l1.Set(key, val)
        return val, true
    }
    
    // L3 数据库
    val, ok := mc.db.Get(key)
    if ok {
        mc.l2.Set(key, val)
        mc.l1.Set(key, val)
        return val, true
    }
    
    return nil, false
}
```

---

## 2. 缓存一致性

### 2.1 更新策略

```
缓存一致性策略：

├── Cache-Aside (旁路缓存)
│   ├── 读：缓存未命中 → 查DB → 写入缓存
│   └── 写：先更新DB → 再删除缓存
│
├── Read-Through (透明读)
│   └── 缓存封装数据库访问
│
├── Write-Through (直写)
│   └── 写缓存同时写DB
│
└── Write-Behind (回写)
    └── 异步写DB
```

### 2.2 Go 实现 Cache-Aside

```go
// cache_aside.go

package cache

type CacheAside struct {
    cache CacheInterface
    db    DBInterface
}

func (ca *CacheAside) Get(key string) (interface{}, error) {
    // 1. 查缓存
    val, err := ca.cache.Get(key)
    if err == nil && val != nil {
        return val, nil
    }
    
    // 2. 查DB
    val, err = ca.db.Get(key)
    if err != nil {
        return nil, err
    }
    
    // 3. 写入缓存
    ca.cache.Set(key, val)
    
    return val, nil
}

func (ca *CacheAside) Set(key string, val interface{}) error {
    // 1. 更新DB
    err := ca.db.Set(key, val)
    if err != nil {
        return err
    }
    
    // 2. 删除缓存
    ca.cache.Delete(key)
    
    return nil
}
```

---

## 3. 缓存问题防护

### 3.1 穿透/击穿/雪崩

```
缓存问题及解决方案：

┌────────────────┬───────────────────┬──────────────────────┐
│ 问题           │ 原因              │ 解决方案             │
├────────────────┼───────────────────┼──────────────────────┤
│ 穿透           │ 查询不存在的数据   │ 布隆过滤器/缓存空值   │
│ 击穿           │ 热点Key过期        │ 永不过期/互斥锁       │
│ 雪崩           │ 大量Key同时过期    │ 随机过期时间          │
│ 命中率低       │ 数据访问不均匀     │ 本地缓存+分布式       │
└────────────────┴───────────────────┴──────────────────────┘
```

### 3.2 Go 实现防护

```go
// cache_protection.go

package cache

import (
    "sync"
    "time"
)

// 布隆过滤器
type BloomFilter struct {
    bits []bool
    size int
}

func NewBloomFilter(size int) *BloomFilter {
    return &BloomFilter{
        bits: make([]bool, size),
        size: size,
    }
}

func (bf *BloomFilter) Add(key string) {
    // 简化实现
    idx := hash(key) % bf.size
    bf.bits[idx] = true
}

func (bf *BloomFilter) MightContain(key string) bool {
    idx := hash(key) % bf.size
    return bf.bits[idx]
}

// 热点 Key 保护
type HotKeyProtector struct {
    mutexes map[string]*sync.Mutex
    mu      sync.Mutex
}

func NewHotKeyProtector() *HotKeyProtector {
    return &HotKeyProtector{
        mutexes: make(map[string]*sync.Mutex),
    }
}

func (hkp *HotKeyProtector) GetOrCreate(key string, fetch func() (interface{}, error)) (interface{}, error) {
    hkp.mu.Lock()
    mutex, ok := hkp.mutexes[key]
    if !ok {
        mutex = &sync.Mutex{}
        hkp.mutexes[key] = mutex
    }
    hkp.mu.Unlock()
    
    mutex.Lock()
    defer mutex.Unlock()
    
    // 双重检查
    // ...
    return fetch()
}
```

---

## 4. 总结

### 4.1 核心原理回顾

| 组件 | 作用 |
|------|------|
| 多级缓存 | 性能优化 |
| Cache-Aside | 一致性保障 |
| 布隆过滤器 | 穿透防护 |
| 互斥锁 | 击穿防护 |

### 4.2 最佳实践

- [ ] 使用多级缓存架构
- [ ] 合理设置过期时间
- [ ] 防护缓存穿透/击穿/雪崩
- [ ] 监控缓存命中率

---

*最后更新：2026-08-12*
*作者：Ryan*
