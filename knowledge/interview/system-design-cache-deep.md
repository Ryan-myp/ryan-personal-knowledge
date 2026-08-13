# 缓存系统设计 - 资深专家深度实现

## 一、缓存架构设计

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        三级缓存架构                                       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐        │
│   │ 浏览器   │───▶│ CDN      │───▶│ 本地缓存  │───▶│ Redis    │───▶│ 数据库   │
│   │          │    │ (边缘)   │    │ (L1)     │    │ (L2)     │    │ (L3)   │
│   └──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘
│        <10ms           <50ms           <5ms            <5ms            >50ms       │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、缓存模式

### 2.1 Cache-Aside (旁路缓存)

```go
package cache

import (
    "context"
    "time"
    "github.com/go-redis/redis/v8"
)

type CacheAside struct {
    local  *LocalCache
    redis  *redis.Client
    db     *Database
}

func (c *CacheAside) Get(ctx context.Context, key string) (string, error) {
    // L1: 本地缓存
    if val, ok := c.local.Get(key); ok {
        return val, nil
    }
    
    // L2: Redis缓存
    val, err := c.redis.Get(ctx, key).Result()
    if err == nil {
        c.local.Set(key, val)
        return val, nil
    }
    
    // L3: 数据库
    val, err = c.db.Get(ctx, key)
    if err != nil {
        return "", err
    }
    
    // 回写缓存
    c.redis.Set(ctx, key, val, 5*time.Minute)
    c.local.Set(key, val)
    
    return val, nil
}

func (c *CacheAside) Set(ctx context.Context, key, val string) error {
    if err := c.db.Set(ctx, key, val); err != nil {
        return err
    }
    
    // 先删缓存
    c.redis.Del(ctx, key)
    c.local.Del(key)
    
    return nil
}
```

### 2.2 Read-Through / Write-Through

```go
// Read-Through: 缓存层负责从DB加载
type ReadThroughCache struct {
    cache  *redis.Client
    loader func(key string) (string, error)
}

func (c *ReadThroughCache) Get(key string) (string, error) {
    val, err := c.cache.Get(ctx, key).Result()
    if err == redis.Nil {
        val, err = c.loader(key)
        if err != nil {
            return "", err
        }
        c.cache.Set(ctx, key, val, 5*time.Minute)
    }
    return val, nil
}

// Write-Through: 写入时同步更新缓存
type WriteThroughCache struct {
    cache *redis.Client
    db    *Database
}

func (c *WriteThroughCache) Set(key, val string) error {
    var wg sync.WaitGroup
    wg.Add(2)
    
    go func() {
        defer wg.Done()
        c.cache.Set(ctx, key, val, 5*time.Minute)
    }()
    
    go func() {
        defer wg.Done()
        c.db.Set(ctx, key, val)
    }()
    
    wg.Wait()
    return nil
}
```

## 三、一致性策略

### 3.1 延时双删

```go
func (c *Cache) SetWithDelayDelete(key, val string) error {
    c.redis.Del(key)
    
    if err := c.db.Set(key, val); err != nil {
        return err
    }
    
    // 延时再删一次
    time.Sleep(500 * time.Millisecond)
    c.redis.Del(key)
    
    return nil
}
```

### 3.2 Canal订阅Binlog

```go
package cache

import (
    "github.com/go-mysql-org/go-mysql/canal"
)

type CanalHandler struct {
    cache *redis.Client
}

func (h *CanalHandler) OnRow(e *canal.RowEvent) error {
    tableName := string(e.Table.Schema) + "." + string(e.Table.Name)
    
    switch e.EventName {
    case canal.UpdateEvent:
        h.handleUpdate(tableName, e.After)
    case canal.DeleteEvent:
        h.handleDelete(tableName, e.After)
    }
    return nil
}

func (h *CanalHandler) handleDelete(table string, data map[string]interface{}) {
    key := buildKey(table, data["id"])
    h.cache.Del(ctx, key)
}
```

## 四、缓存预热与降级

```go
// 缓存预热
func (c *Cache) WarmUp(keys []string) error {
    for _, key := range keys {
        val, err := c.db.Get(key)
        if err != nil {
            continue
        }
        c.redis.Set(key, val, 30*time.Minute)
    }
    return nil
}

// 缓存降级
func (c *Cache) GetWithFallback(ctx context.Context, key string) (string, error) {
    val, err := c.redis.Get(ctx, key).Result()
    if err == nil {
        return val, nil
    }
    
    // 降级：直接从数据库读取
    val, err = c.db.Get(ctx, key)
    if err != nil {
        return "", err
    }
    
    c.redis.Set(ctx, key, val, 1*time.Minute)
    return val, nil
}
```

## 五、面试高频题

### Q1: 缓存穿透/击穿/雪崩的区别？

```
A:
• 穿透: 查询不存在的数据 → 布隆过滤器 + 空值缓存
• 击穿: 热点key过期 → 互斥锁 + 永不过期
• 雪崩: 大量key同时过期 → 随机TTL + 多级缓存
```

### Q2: 如何保证缓存和数据库的一致性？

```
A: 
1. Cache-Aside + 延时双删
2. Canal订阅Binlog
3. 队列异步更新
```

## 六、自测题

1. 设计一个支持高并发的缓存系统
2. 如何监控缓存命中率？
3. 如何实现缓存预热功能？

---

## 参考文档

- [Redis最佳实践](https://redis.io/docs/manual/patterns/)
- [缓存一致性方案](https://code.fasol.me/post/cache-consistency/)
