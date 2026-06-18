# 系统设计深度：秒杀/分布式锁/最终一致性源码级

> 从秒杀系统到分布式事务，逐行解析高并发系统设计

---

## 第一部分：秒杀系统架构

### 秒杀架构

```
秒杀系统架构：
┌─────────────────────────────────────────────────────────────────────┐
│ 1. 用户请求 → CDN 静态资源                                           │
│ 2. API Gateway → 限流/防刷                                           │
│ 3. Redis → 库存扣减（Lua 脚本）                                       │
│ 4. Kafka → 异步下单                                                  │
│ 5. 订单服务 → 创建订单                                                │
│ 6. 支付服务 → 异步支付                                                │
│                                                                     │
│ 关键优化：                                                           │
│ • 前端：按钮置灰/倒计时/验证码                                        │
│ • CDN：静态资源缓存                                                   │
│ • Gateway：IP 限流 + 用户限流                                        │
│ • Redis：Lua 原子扣减                                               │
│ • Kafka：削峰填谷                                                   │
│ • 数据库：读写分离 + 分库分表                                         │
└─────────────────────────────────────────────────────────────────────┘
```

### Lua 库存扣减源码

```lua
-- Redis Lua 脚本：原子扣减库存
local key = KEYS[1]
local userId = ARGV[1]
local quantity = tonumber(ARGV[2])

-- 1. 检查用户是否已购买
local boughtKey = "bought:" .. userId
if redis.call('exists', boughtKey) == 1 then
    return -1  -- 重复购买
end

-- 2. 检查库存
local stock = tonumber(redis.call('get', key))
if stock == nil or stock < quantity then
    return -2  -- 库存不足
end

-- 3. 扣减库存
redis.call('decrby', key, quantity)

-- 4. 记录购买
redis.call('sadd', boughtKey, key)
redis.call('expire', boughtKey, 86400)  -- 24 小时过期

-- 5. 返回成功
return 1
```

---

## 第二部分：分布式锁源码

### Redis 分布式锁

```go
package distributedlock

import (
    "context"
    "time"
    "github.com/go-redis/redis/v8"
)

// Redlock Redis 分布式锁
type Redlock struct {
    clients []*redis.Client
    nonce   string
    ttl     time.Duration
}

// NewRedlock 创建 Redlock
func NewRedlock(addrs []string, ttl time.Duration) *Redlock {
    clients := make([]*redis.Client, len(addrs))
    for i, addr := range addrs {
        clients[i] = redis.NewClient(&redis.Options{
            Addr: addr,
        })
    }
    
    return &Redlock{
        clients: clients,
        nonce:   uuid.New().String(),
        ttl:     ttl,
    }
}

// Lock 加锁
func (r *Redlock) Lock(ctx context.Context, key string) bool {
    // 1. 在所有节点上尝试加锁
    n := 0
    startTime := time.Now()
    
    for _, client := range r.clients {
        ok, err := client.SetNX(ctx, key, r.nonce, r.ttl).Result()
        if err != nil {
            continue
        }
        if ok {
            n++
        }
    }
    
    // 2. 多数派成功才算加锁成功
    if n <= len(r.clients)/2 {
        // 失败则释放所有锁
        r.unlock(key)
        return false
    }
    
    // 3. 计算实际可用时间
    elapsed := time.Since(startTime)
    effectiveTTL := r.ttl - elapsed
    
    // 4. 在所有节点上延长 TTL
    for _, client := range r.clients {
        client.Expire(ctx, key, effectiveTTL)
    }
    
    return true
}

// Unlock 释放锁
func (r *Redlock) unlock(key string) {
    lua := redis.NewScript(`
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
    `)
    
    for _, client := range r.clients {
        lua.Run(context.Background(), client, []string{key}, r.nonce).Result()
    }
}
```

### ZooKeeper 分布式锁

```go
package distributedlock

import (
    "github.com/samuel/go-zookeeper/zk"
)

// ZKLock ZooKeeper 分布式锁
type ZKLock struct {
    client   *zk.Conn
    path     string
    sessionID int64
}

// Lock 加锁
func (l *ZKLock) Lock() error {
    // 1. 创建临时有序节点
    path, err := l.client.Create(
        l.path,
        []byte(""),
        zk.FlagEphemeral|zk.FlagSequence,
        zk.WorldACL(zk.PermAll),
    )
    if err != nil {
        return err
    }
    
    // 2. 获取所有子节点并排序
    children, _, err := l.client.Children(l.path)
    if err != nil {
        return err
    }
    
    // 3. 检查自己是否是最小节点
    myIndex := -1
    for i, child := range children {
        if child == path[len(l.path)+1:] {
            myIndex = i
            break
        }
    }
    
    if myIndex == 0 {
        return nil  // 获得锁
    }
    
    // 4. 监听前一个节点
    prev := children[myIndex-1]
    _, _, ch, err := l.client.ExistsW(l.path + "/" + prev)
    if err != nil {
        return err
    }
    
    // 5. 等待前一个节点删除
    <-ch
    return l.Lock()  // 递归尝试
}

// Unlock 释放锁
func (l *ZKLock) Unlock() error {
    return l.client.Delete(l.path, -1)
}
```

---

## 第三部分：最终一致性源码

### Saga 模式

```
Saga 模式：
┌─────────────────────────────────────────────────────────────────────┐
│ 事务 1: 创建订单 → 扣减库存 → 创建支付记录                           │
│ 事务 2: 扣减积分 → 发送优惠券                                        │
│ 事务 3: 发送短信通知                                                 │
│                                                                     │
│ 补偿操作：                                                           │
│ 如果事务 2 失败：                                                    │
│ → 取消订单（反向操作）                                               │
│ → 恢复库存（反向操作）                                               │
│ → 取消支付（反向操作）                                               │
└─────────────────────────────────────────────────────────────────────┘
```

### Saga 实现

```go
package saga

// Step 步骤
type Step struct {
    Name        string
    Execute     func() error
    Compensation func() error
}

// Saga 编排器
type Saga struct {
    steps []Step
}

// AddStep 添加步骤
func (s *Saga) AddStep(name string, execute, compensate func() error) {
    s.steps = append(s.steps, Step{
        Name:        name,
        Execute:     execute,
        Compensation: compensate,
    })
}

// Execute 执行 Saga
func (s *Saga) Execute() error {
    executed := make([]int, 0)
    
    // 正向执行
    for i, step := range s.steps {
        if err := step.Execute(); err != nil {
            // 执行失败，反向补偿
            for j := len(executed) - 1; j >= 0; j-- {
                idx := executed[j]
                if err := s.steps[idx].Compensation(); err != nil {
                    // 补偿也失败，记录日志
                    log.Printf("compensation failed: %v", err)
                }
            }
            return err
        }
        executed = append(executed, i)
    }
    
    return nil
}
```

---

## 第四部分：自测题

### Q1: 秒杀系统为什么用 Redis 而不是数据库？

**A**: Redis 内存操作，QPS 可达 10 万+；数据库 QPS 通常几千。Redis 的 Lua 脚本保证原子性。

### Q2: 分布式锁的 Redlock 和 Redission 区别？

**A**: Redlock 是多节点共识，Redission 是单节点 + 看门狗续期。Redlock 更可靠但延迟高。

### Q3: 最终一致性怎么保证？

**A**: Saga 模式（补偿事务）、TCC 模式（Try-Confirm-Cancel）、消息队列（最终一致性）。

---

## 第五部分：生产实践

### 1. 限流

```
限流策略：
1. 固定窗口：简单但有临界问题
2. 滑动窗口：精确但内存大
3. 漏桶：匀速处理
4. 令牌桶：允许突发
```

### 2. 防刷

```
防刷策略：
1. IP 限流
2. 用户限流
3. 验证码
4. 行为分析
```

### 3. 降级

```
降级策略：
1. 缓存兜底
2. 默认值
3. 功能开关
4. 流量隔离
```
