# Redis 缓存架构深度解析

> 深入Redis缓存架构：缓存设计、一致性、穿透、雪崩、热点Key。
> 源码级分析，包含生产环境最佳实践。
> 适用对象：后端工程师、架构师

---

## 1. 缓存架构设计

### 1.1 缓存分层

```
Redis 缓存分层架构：

┌─────────────────────────────────────────────────────────────┐
│                    缓存分层架构                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  L1 Cache (本地缓存)                                          │
│  ├── 缓存级别：JVM堆内                                        │
│  ├── 缓存大小：几十MB                                          │
│  ├── 延迟：微秒级                                              │
│  └── 适用：热点数据                                            │
│                                                             │
│  L2 Cache (分布式缓存)                                         │
│  ├── 缓存级别：Redis Cluster                                  │
│  ├── 缓存大小：GB级别                                          │
│  ├── 延迟：毫秒级                                              │
│  └── 适用：共享数据                                            │
│                                                             │
│  Backend (数据库)                                              │
│  ├── 缓存级别：MySQL/PostgreSQL                               │
│  ├── 缓存大小：TB级别                                          │
│  └── 延迟：毫秒-秒级                                           │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 Go 实现多级缓存

```go
// multi_level_cache.go

package cache

import (
    "context"
    "sync"
    "time"
)

type MultiLevelCache struct {
    l1  *LocalCache
    l2  *RedisCache
    db  *Database
}

type LocalCache struct {
    items sync.Map
    ttl   time.Duration
}

type RedisCache struct {
    client *redis.Client
    ttl    time.Duration
}

type Database struct {
    conn *sql.DB
}

func NewMultiLevelCache(l1TTL, l2TTL time.Duration) *MultiLevelCache {
    return &MultiLevelCache{
        l1: &LocalCache{ttl: l1TTL},
        l2: &RedisCache{ttl: l2TTL},
        db: &Database{},
    }
}

func (mlc *MultiLevelCache) Get(ctx context.Context, key string) (interface{}, error) {
    // 1. 查询L1缓存
    if val, ok := mlc.l1.Get(key); ok {
        return val, nil
    }
    
    // 2. 查询L2缓存
    if val, ok := mlc.l2.Get(key); ok {
        // 回填L1
        mlc.l1.Set(key, val)
        return val, nil
    }
    
    // 3. 查询数据库
    val, err := mlc.db.Query(ctx, key)
    if err != nil {
        return nil, err
    }
    
    // 4. 写入缓存
    mlc.l2.Set(key, val)
    mlc.l1.Set(key, val)
    
    return val, nil
}

func (mlc *MultiLevelCache) Set(ctx context.Context, key string, value interface{}) {
    mlc.l2.Set(key, value)
    mlc.l1.Set(key, value)
}

func (mlc *MultiLevelCache) Delete(ctx context.Context, key string) {
    mlc.l2.Delete(key)
    mlc.l1.Delete(key)
}
```

---

## 2. 缓存一致性

### 2.1 一致性策略

```
缓存一致性策略：

├── Cache-Aside (旁路缓存)
│   ├── 读：缓存未命中→查DB→写入缓存
│   └── 写：更新DB→删除缓存
│
├── Read-Through (读穿透)
│   └── 缓存层负责从DB加载
│
├── Write-Through (写穿透)
│   └── 写入缓存同时写入DB
│
└── Write-Behind (写回)
    └── 先写缓存，异步写DB
```

### 2.2 Go 实现 Cache-Aside

```go
// cache_aside.go

package cache

import (
    "context"
    "sync"
)

type CacheAside struct {
    cache  *RedisCache
    db     *Database
    mu     sync.Mutex
}

func NewCacheAside(cache *RedisCache, db *Database) *CacheAside {
    return &CacheAside{
        cache: cache,
        db:    db,
    }
}

func (ca *CacheAside) Get(ctx context.Context, key string) (interface{}, error) {
    // 1. 查询缓存
    val, err := ca.cache.Get(key)
    if err == nil && val != nil {
        return val, nil
    }
    
    // 2. 查询数据库
    dbVal, err := ca.db.Query(ctx, key)
    if err != nil {
        return nil, err
    }
    
    // 3. 写入缓存
    ca.cache.Set(key, dbVal)
    
    return dbVal, nil
}

func (ca *CacheAside) Set(ctx context.Context, key string, value interface{}) error {
    // 1. 更新数据库
    err := ca.db.Update(ctx, key, value)
    if err != nil {
        return err
    }
    
    // 2. 删除缓存
    ca.cache.Delete(key)
    
    return nil
}

// 双写一致性方案
func (ca *CacheAside) SetWithRetry(ctx context.Context, key string, value interface{}) error {
    // 1. 先更新数据库
    err := ca.db.Update(ctx, key, value)
    if err != nil {
        return err
    }
    
    // 2. 删除缓存
    ca.cache.Delete(key)
    
    // 3. 延迟删除缓存（防止并发读写）
    time.Sleep(100 * time.Millisecond)
    ca.cache.Delete(key)
    
    return nil
}
```

---

## 3. 缓存问题

### 3.1 常见问题

```
缓存常见问题：

├── 缓存穿透
│   ├── 查询不存在的数据
│   └── 解决方案：布隆过滤器/缓存空值
│
├── 缓存击穿
│   ├── 热点Key过期
│   └── 解决方案：永不过期/互斥锁
│
├── 缓存雪崩
│   ├── 大量Key同时过期
│   └── 解决方案：随机TTL/多级缓存
│
└── 缓存倾斜
    ├── 热点Key集中在某节点
    └── 解决方案：本地缓存/分片
```

### 3.2 Go 实现问题防护

```go
// cache_protection.go

package cache

import (
    "sync"
    "time"
)

// 布隆过滤器 - 防止缓存穿透
type BloomFilter struct {
    bits   []bool
    size   int
    hashes []func(string) int
}

func NewBloomFilter(size int, hashCount int) *BloomFilter {
    bf := &BloomFilter{
        bits: make([]bool, size),
        size: size,
    }
    for i := 0; i < hashCount; i++ {
        bf.hashes = append(bf.hashes, generateHash(i))
    }
    return bf
}

func (bf *BloomFilter) Add(item string) {
    for _, hash := range bf.hashes {
        idx := hash(item) % bf.size
        bf.bits[idx] = true
    }
}

func (bf *BloomFilter) MightContain(item string) bool {
    for _, hash := range bf.hashes {
        idx := hash(item) % bf.size
        if !bf.bits[idx] {
            return false
        }
    }
    return true
}

// 互斥锁 - 防止缓存击穿
type MutexCache struct {
    locks  sync.Map
    cache  *RedisCache
}

func (mc *MutexCache) Get(key string) (interface{}, error) {
    // 尝试获取锁
    lock, loaded := mc.locks.LoadOrStore(key, &sync.Mutex{})
    mu := lock.(*sync.Mutex)
    
    mu.Lock()
    defer mu.Unlock()
    
    // 双重检查
    if val, ok := mc.cache.Get(key); ok {
        return val, nil
    }
    
    // 查询数据库
    val, err := mc.queryDB(key)
    if err != nil {
        return nil, err
    }
    
    // 写入缓存
    mc.cache.Set(key, val)
    
    return val, nil
}

// 随机TTL - 防止缓存雪崩
func RandomTTL(baseTTL time.Duration) time.Duration {
    jitter := time.Duration(rand.Int63n(int64(baseTTL) / 4))
    return baseTTL + jitter
}
```

---

## 4. 热点Key处理

### 4.1 热点检测

```
热点Key检测策略：

├── 访问频率统计
│   └── 单位时间访问次数
│
├── 访问分布统计
│   └── 单机访问占比
│
└── 动态调整
    └── 自动提升缓存级别
```

### 4.2 Go 实现热点检测

```go
// hot_key_detector.go

package cache

import (
    "sync"
    "time"
)

type HotKeyDetector struct {
    accessCount sync.Map  // key -> count
    windowSize  time.Duration
    threshold   int
}

func NewHotKeyDetector(windowSize time.Duration, threshold int) *HotKeyDetector {
    return &HotKeyDetector{
        windowSize: windowSize,
        threshold:  threshold,
    }
}

func (hkd *HotKeyDetector) Record(key string) {
    if v, ok := hkd.accessCount.Load(key); ok {
        hkd.accessCount.Store(key, v.(int)+1)
    } else {
        hkd.accessCount.Store(key, 1)
    }
}

func (hkd *HotKeyDetector) IsHot(key string) bool {
    if v, ok := hkd.accessCount.Load(key); ok {
        return v.(int) >= hkd.threshold
    }
    return false
}

func (hkd *HotKeyDetector) GetHotKeys() []string {
    var hotKeys []string
    
    hkd.accessCount.Range(func(k, v interface{}) bool {
        if count, ok := v.(int); ok && count >= hkd.threshold {
            hotKeys = append(hotKeys, k.(string))
        }
        return true
    })
    
    return hotKeys
}
```

---

## 5. 总结

### 5.1 核心原理回顾

| 问题 | 解决方案 |
|------|----------|
| 缓存穿透 | 布隆过滤器/缓存空值 |
| 缓存击穿 | 互斥锁/永不过期 |
| 缓存雪崩 | 随机TTL/多级缓存 |
| 热点Key | 本地缓存/分片 |

### 5.2 最佳实践

- [ ] 使用多级缓存架构
- [ ] 选择合适的缓存一致性策略
- [ ] 建立热点Key监控
- [ ] 设置合理的TTL

---

*最后更新：2026-08-11*
*作者：Ryan*
