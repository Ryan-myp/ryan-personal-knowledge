# Redis缓存模式 - 资深专家深度实现

## 一、缓存模式对比

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      缓存模式                                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   Cache-Aside (旁路缓存)    Read-Through (读穿透)    Write-Through (写穿透)│
│   ┌──────────────┐         ┌──────────────┐         ┌──────────────┐    │
│   │ App          │         │ App          │         │ App          │    │
│   │ • Read cache │         │ • Read       │         │ • Write      │    │
│   │ • Miss DB    │         │   proxy      │         │   cache+DB   │    │
│   │ • Write DB   │         │ • Cache loads│         │              │    │
│   │ • Delete cache│        │   from DB    │         │              │    │
│   └──────────────┘         └──────────────┘         └──────────────┘    │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、Cache-Aside实现

```go
package cache

import (
    "context"
    "sync"
    "time"
    
    "github.com/go-redis/redis/v8"
)

type CacheAside struct {
    redis  *redis.Client
    db     *Database
    local  *LocalCache
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
    // 先更新数据库
    if err := c.db.Set(ctx, key, val); err != nil {
        return err
    }
    
    // 再删除缓存（而非更新）
    c.redis.Del(ctx, key)
    c.local.Del(key)
    
    return nil
}
```

## 三、缓存一致性

### 3.1 延时双删

```go
func (c *Cache) SetWithDelayDelete(key, val string) error {
    // 1. 删除缓存
    c.redis.Del(key)
    
    // 2. 更新数据库
    if err := c.db.Set(key, val); err != nil {
        return err
    }
    
    // 3. 延时再删一次（防止并发读写）
    time.Sleep(500 * time.Millisecond)
    c.redis.Del(key)
    
    return nil
}
```

### 3.2 Canal订阅Binlog

```go
package binlog

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
    h.cache.Del(context.Background(), key)
}
```

## 四、面试高频题

### Q1: 缓存穿透/击穿/雪崩怎么解决？

```
A:
• 穿透: 布隆过滤器 + 空值缓存
• 击穿: 互斥锁 + 永不过期
• 雪崩: 随机TTL + 多级缓存
```

### Q2: 如何选择缓存TTL？

```
A:
• 根据数据变更频率
• 热点数据设置较长TTL
• 普通数据设置较短TTL
• 添加随机抖动避免同时过期
```

## 五、自测题

1. 如何设计多级缓存架构？
2. 缓存预热如何实现？
3. 如何监控缓存命中率？

---

## 参考文档

- [Redis最佳实践](https://redis.io/docs/manual/patterns/)
- [缓存一致性方案](https://code.fasol.me/post/cache-consistency/)
