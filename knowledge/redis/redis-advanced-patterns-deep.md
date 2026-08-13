# Redis 高级模式深度解析

> 深入 Redis 高级用法：缓存穿透/击穿/雪崩、分布式锁、Lua 脚本、集群架构。
> 适用对象：后端工程师、架构师

---

## 1. 缓存问题与解决方案

### 1.1 缓存穿透

```go
// 问题: 查询不存在的数据，绕过缓存直接打到 DB
func QueryWithBloom(key string) (interface{}, error) {
    // 布隆过滤器判断 key 是否存在
    if !bloomFilter.Exists(key) {
        return nil, nil // 直接返回空，不查 DB
    }
    return queryDB(key)
}

// 方案: 缓存空值 + 布隆过滤器
```

### 1.2 缓存击穿

```go
// 问题: 热点 key 过期，大量请求同时打到 DB
func HotKeyWithMutex(key string) interface{} {
    val := cache.Get(key)
    if val != nil {
        return val
    }
    
    // 分布式锁
    lock := redis.NewLock("lock:" + key, 10*time.Second)
    if err := lock.Lock(); err != nil {
        time.Sleep(50 * time.Millisecond)
        return cache.Get(key) // 重试
    }
    defer lock.Unlock()
    
    val = queryDB(key)
    cache.Set(key, val, 30*time.Minute)
    return val
}
```

### 1.3 缓存雪崩

```go
// 问题: 大量 key 同时过期
func PreventAvalanche(key string, val interface{}) {
    // 过期时间加随机值
    ttl := 30*time.Minute + time.Duration(rand.Intn(300))*time.Second
    cache.Set(key, val, ttl)
}
```

---

## 2. 分布式锁

### 2.1 Redis SETNX 锁

```go
// 原子设置 + 过期
func AcquireLock(key string, timeout time.Duration) (string, error) {
    token := uuid.New().String()
    ok, err := redis.SetNX(key, token, timeout).Result()
    if err != nil || !ok {
        return "", fmt.Errorf("lock failed")
    }
    return token, nil
}

func ReleaseLock(key, token string) error {
    // Lua 脚本保证原子性
    script := `
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
    `
    return redis.Eval(script, []string{key}, token).Err()
}
```

### 2.2 Redisson 实现

```java
RLock lock = redisson.getLock("myLock");
if (lock.tryLock(100, 10, TimeUnit.SECONDS)) {
    try {
        // 业务逻辑
    } finally {
        lock.unlock();
    }
}
```

---

## 3. Lua 脚本

```lua
-- 原子操作示例
local key = KEYS[1]
local value = ARGV[1]
local ttl = tonumber(ARGV[2])

-- 检查并设置
if redis.call('exists', key) == 0 then
    redis.call('set', key, value, 'ex', ttl)
    return 1
end
return 0
```

---

## 4. Redis 集群

```
┌─────────────────────────────────────────────────────────────────┐
│                     Redis Cluster 架构                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  16384 个 Hash Slot                                             │
│                                                                 │
│  Master Node 1  (Slots 0-5460)    Replica 1                    │
│  Master Node 2  (Slots 5461-10922) Replica 2                    │
│  Master Node 3  (Slots 10923-16383)Replica 3                    │
│                                                                 │
│  客户端路由:                                                    │
│  1. 计算 Key 的 Slot: CRC16(key) % 16384                        │
│  2. 找到对应 Master                                             │
│  3. MOVED/NOSLOT 重定向                                         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 5. 实践 Checklist

- [ ] 热点 Key 加随机 TTL
- [ ] 分布式锁使用 Lua 脚本
- [ ] 缓存击穿使用互斥锁
- [ ] 缓存雪崩错峰过期
- [ ] 大 Key 拆分 + 异步删除
- [ ] 慢查询监控 + 告警

---

**参考**: Redis 官方文档、Redis in Action、Netflix Redis 实践
