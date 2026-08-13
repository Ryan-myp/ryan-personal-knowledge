# Redis缓存模式 - 资深专家深度实现

## 一、缓存模式

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    Redis 缓存模式                                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   模式                | 适用场景                  | 特点                │
│   ────────────────────┼─────────────────────────┼─────────────────────│
│   Cache-Aside        | 读多写少                 │ 简单可靠            │
│   Read-Through       | 读取为主                 │ 透明缓存            │
│   Write-Through      | 一致性要求高             │ 同步写入            │
│   Write-Behind       | 性能优先                 │ 异步写入            │
│   Refresh-Ahead      | 热点数据                 │ 主动刷新            │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、Cache-Aside模式

```go
package cache

import (
    "context"
)

// CacheAside 缓存旁路模式
type CacheAside struct {
    cache *RedisClient
    db    *Database
}

// Get 获取数据
func (c *CacheAside) Get(ctx context.Context, key string) ([]byte, error) {
    // 1. 尝试从缓存获取
    value, err := c.cache.Get(ctx, key)
    if err == nil && value != nil {
        return value, nil
    }
    
    // 2. 缓存未命中，从数据库获取
    data, err := c.db.Query(ctx, key)
    if err != nil {
        return nil, err
    }
    
    // 3. 写入缓存
    c.cache.Set(ctx, key, data, 5*time.Minute)
    
    return data, nil
}

// Set 更新数据
func (c *CacheAside) Set(ctx context.Context, key string, value []byte) error {
    // 1. 更新数据库
    if err := c.db.Update(ctx, key, value); err != nil {
        return err
    }
    
    // 2. 删除缓存（而非更新）
    c.cache.Del(ctx, key)
    
    return nil
}
```

## 三、面试高频题

### Q1: Cache-Aside的优缺点？

```
A:
1. 优点：简单可靠
2. 缺点：首次请求慢
```

### Q2: 如何解决缓存穿透？

```
A:
1. 布隆过滤器
2. 缓存空值
3. 参数校验
```

## 四、自测题

1. 解释缓存模式
2. 如何实现Cache-Aside？
3. 如何解决穿透？

---

## 参考文档

- [Redis Docs](https://redis.io/docs/)
- [Cache Patterns](https://docs.microsoft.com/azure/architecture/patterns/cache-aside)
