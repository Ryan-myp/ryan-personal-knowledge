# 分布式锁实现 - 资深专家深度实现

## 一、锁类型对比

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    分布式锁实现方案                                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   方案              | 可靠性 | 性能   | 复杂度 | 适用场景                  │
│   ──────────────────┼────────┼────────┼────────┼─────────────────────────│
│   Redis SET NX      | 中     | 高     | 低     | 简单场景                    │
│   Redis Redlock     | 高     | 中     | 高     | 高可用要求                    │
│   ZooKeeper         | 高     | 中     | 中     | 有序锁需求                    │
│   Etcd              | 高     | 高     | 中     | K8s生态                     │
│   MySQL SELECT...   | 低     | 低     | 低     | 不推荐                      │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、Redis分布式锁实现

```go
package lock

import (
    "context"
    "github.com/go-redis/redis/v8"
    "time"
)

type RedisLock struct {
    client *redis.Client
    key    string
    value  string
}

func NewRedisLock(client *redis.Client, key string) *RedisLock {
    return &RedisLock{
        client: client,
        key:    key,
        value:  uuid.New().String(),
    }
}

// Acquire 获取锁
func (l *RedisLock) Acquire(ctx context.Context, ttl time.Duration) bool {
    // SET key value NX PX ttl
    result := l.client.Set(ctx, l.key, l.value, ttl, redis.SetNX)
    return result.Val()
}

// Release 释放锁
func (l *RedisLock) Release(ctx context.Context) bool {
    // Lua脚本保证原子性
    script := `
    if redis.call("get", KEYS[1]) == ARGV[1] then
        return redis.call("del", KEYS[1])
    else
        return 0
    end
    `
    result := l.client.Eval(ctx, script, []string{l.key}, l.value)
    return result.Int() == 1
}

// Renew 续期（防止业务未执行完锁过期）
func (l *RedisLock) Renew(ctx context.Context, ttl time.Duration) bool {
    script := `
    if redis.call("get", KEYS[1]) == ARGV[1] then
        return redis.call("pexpire", KEYS[1], ARGV[2])
    else
        return 0
    end
    `
    result := l.client.Eval(ctx, script, []string{l.key}, l.value, ttl.Milliseconds())
    return result.Int() == 1
}
```

## 三、面试高频题

### Q1: 如何解决锁过期问题？

```
A:
1. 看门狗机制
2. 异步续期
3. Redlock算法
```

### Q2: Redlock算法原理？

```
A:
1. N个Redis节点
2. 多数派成功即成功
3. 容错能力强
```

## 四、自测题

1. 解释Redis锁原理
2. 如何实现Redlock？
3. 如何解决锁过期？

---

## 参考文档

- [Redis分布式锁](https://redis.io/docs/reference/patterns/distributed-locks/)
- [Redlock论文](https://redis.io/docs/reference/patterns/distributed-locks/)
