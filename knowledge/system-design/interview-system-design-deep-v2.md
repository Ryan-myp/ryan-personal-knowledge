# 系统设计面试深度解析

> 深入系统设计面试核心：缓存、消息队列、数据库分片、分布式ID、限流等经典问题。
> 包含真实的系统设计思考和权衡分析。
> 适用对象：准备高级工程师面试的开发者、系统设计师

---

## 1. URL 短链系统设计

### 1.1 需求分析

```
功能需求：
1. 长链接 → 短链接
2. 短链接 → 重定向到原链接
3. 支持自定义短码
4. 支持链接过期时间

非功能需求：
- 高并发读取（100万QPS）
- 短链接唯一性
- 低延迟（< 10ms）
```

### 1.2 设计方案

```
方案 1：数据库自增ID + 进制转换
├── 优点：简单、可靠
├── 缺点：ID可猜测、需要数据库
└── 适用：小规模场景

方案 2：雪花算法 + 哈希
├── 优点：分布式、不可预测
├── 缺点：需要ID生成器
└── 适用：中等规模

方案 3：Redis + 分布式ID
├── 优点：高性能、分布式
├── 缺点：依赖Redis
└── 适用：大规模场景
```

### 1.3 Go 实现

```go
// shortener.go

package shortener

import (
    "encoding/base62"
    "sync"
)

type Shortener struct {
    db       *Database
    idGen    *SnowflakeID
    mu       sync.RWMutex
    cache    map[string]string
}

func (s *Shortener) Shorten(longURL string) (string, error) {
    // 1. 生成短码
    id := s.idGen.NextID()
    shortCode := base62.Encode(id)
    
    // 2. 存储映射
    err := s.db.Set(shortCode, longURL)
    if err != nil {
        return "", err
    }
    
    // 3. 缓存
    s.mu.Lock()
    s.cache[shortCode] = longURL
    s.mu.Unlock()
    
    return shortCode, nil
}

func (s *Shortener) Expand(shortCode string) (string, error) {
    // 1. 缓存查询
    s.mu.RLock()
    url, ok := s.cache[shortCode]
    s.mu.RUnlock()
    
    if ok {
        return url, nil
    }
    
    // 2. 数据库查询
    url, err := s.db.Get(shortCode)
    if err != nil {
        return "", err
    }
    
    // 3. 写入缓存
    s.mu.Lock()
    s.cache[shortCode] = url
    s.mu.Unlock()
    
    return url, nil
}
```

---

## 2. 分布式ID生成

### 2.1 雪花算法

```
雪花算法结构 (64-bit):

┌─────────┬──────────────┬────────┬───────────┐
│ 符号位  │   时间戳     │ 机器ID │  序列号   │
│  1bit   │    41bit     │ 10bit  │   12bit   │
└─────────┴──────────────┴────────┴───────────┘

时间戳: 41 bit = 2^41 ms ≈ 69 年
机器ID: 10 bit = 1024 台机器
序列号: 12 bit = 每ms 4096 个ID

最大ID数: 2^12 * 每ms = 4096 万 QPS
```

### 2.2 Go 实现

```go
// snowflake.go

package id

import (
    "sync"
    "time"
)

const (
    epoch        = 1577836800000 // 2020-01-01
    workerBits   = 10
    sequenceBits = 12
    
    maxWorkerId     = -1 ^ (-1 << workerBits)
    maxSequence     = -1 ^ (-1 << sequenceBits)
    
    workerIdShift   = sequenceBits
    timestampShift  = sequenceBits + workerBits
)

type Snowflake struct {
    mu          sync.Mutex
    workerId    int64
    sequence    int64
    lastTimestamp int64
}

func NewSnowflake(workerId int64) *Snowflake {
    if workerId < 0 || workerId > maxWorkerId {
        panic("worker id out of range")
    }
    return &Snowflake{
        workerId: workerId,
    }
}

func (s *Snowflake) NextID() int64 {
    s.mu.Lock()
    defer s.mu.Unlock()
    
    timestamp := time.Now().UnixMilli()
    
    if timestamp < s.lastTimestamp {
        // 时钟回拨，等待
        for timestamp < s.lastTimestamp {
            timestamp = time.Now().UnixMilli()
        }
    }
    
    if timestamp == s.lastTimestamp {
        s.sequence = (s.sequence + 1) & maxSequence
        if s.sequence == 0 {
            timestamp = s.waitNextMillis(timestamp)
        }
    } else {
        s.sequence = 0
    }
    
    s.lastTimestamp = timestamp
    
    return ((timestamp - epoch) << timestampShift) |
        (s.workerId << workerIdShift) |
        s.sequence
}

func (s *Snowflake) waitNextMillis(lastTimestamp int64) int64 {
    timestamp := time.Now().UnixMilli()
    for timestamp <= lastTimestamp {
        timestamp = time.Now().UnixMilli()
    }
    return timestamp
}
```

---

## 3. 分布式锁

### 3.1 Redis 实现

```go
// redis_lock.go

package lock

import (
    "context"
    "time"
    
    "github.com/go-redis/redis/v8"
)

type RedisLock struct {
    client *redis.Client
    key    string
    value  string
    ttl    time.Duration
}

func NewRedisLock(client *redis.Client, key string, ttl time.Duration) *RedisLock {
    return &RedisLock{
        client: client,
        key:    key,
        ttl:    ttl,
    }
}

func (l *RedisLock) Lock(ctx context.Context) bool {
    // SET key value NX PX ttl
    result := l.client.Set(ctx, l.key, l.value, l.ttl)
    return result.Err() == nil
}

func (l *RedisLock) Unlock(ctx context.Context) error {
    // Lua 脚本原子删除
    script := `
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
    `
    _, err := l.client.Eval(ctx, script, []string{l.key}, l.value).Result()
    return err
}
```

---

## 4. 缓存架构

### 4.1 Cache-Aside 模式

```
┌─────────────────────────────────────────────────────────────┐
│                  Cache-Aside 模式                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  读取流程：                                                  │
│  1. 查询缓存                                                 │
│  2. 缓存命中 → 返回                                         │
│  3. 缓存未命中 → 查询数据库                                  │
│  4. 写入缓存                                                 │
│  5. 返回                                                     │
│                                                             │
│  写入流程：                                                  │
│  1. 更新数据库                                               │
│  2. 删除缓存（不更新，避免不一致）                            │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 Go 实现

```go
// cache_side.go

package cache

import (
    "context"
    "sync"
    "time"
)

type CacheAside struct {
    cache  *RedisClient
    db     *Database
    mu     sync.RWMutex
}

func (c *CacheAside) Get(ctx context.Context, key string) (string, error) {
    // 1. 查询缓存
    val, err := c.cache.Get(ctx, key)
    if err == nil && val != "" {
        return val, nil
    }
    
    // 2. 查询数据库
    dbVal, err := c.db.Get(ctx, key)
    if err != nil {
        return "", err
    }
    
    // 3. 写入缓存
    c.cache.Set(ctx, key, dbVal, time.Minute*5)
    
    return dbVal, nil
}

func (c *CacheAside) Set(ctx context.Context, key, value string) error {
    // 1. 更新数据库
    err := c.db.Set(ctx, key, value)
    if err != nil {
        return err
    }
    
    // 2. 删除缓存
    c.cache.Del(ctx, key)
    
    return nil
}
```

---

## 5. 消息队列

### 5.1 Kafka 架构

```
┌─────────────────────────────────────────────────────────────┐
│                    Kafka 架构                                │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Producer ──► Topic ──► Partition 0 ──► Broker 1           │
│                  │            Partition 1 ──► Broker 2      │
│                  │            Partition 2 ──► Broker 3      │
│                  └──────────────────────────────────► Consumer Group │
│                                                             │
│  关键特性：                                                  │
│  ├── 持久化存储                                              │
│  ├── 高吞吐                                                  │
│  ├── 可扩展                                                  │
│  └── 容错                                                    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 5.2 消息一致性

```
消息传递语义：

At-Most-Once (最多一次)
├── 可能丢消息
├── 不重复
└── 适用：日志收集

At-Least-Once (至少一次)
├── 不丢消息
├── 可能重复
└── 适用：需要保证不丢

Exactly-Once (精确一次)
├── 不丢不重复
├── 需要幂等处理
└── 适用：金融交易
```

---

## 6. 数据库分片

### 6.1 分片策略

```
分片键选择：

1. 用户ID分片
   ├── 优点：用户数据集中
   └── 缺点：热门用户热点

2. 时间分片
   ├── 优点：数据均匀
   └── 缺点：时间范围查询慢

3. 哈希分片
   ├── 优点：数据均匀
   └── 缺点：范围查询慢
```

### 6.2 Go 实现

```go
// sharding.go

package sharding

import (
    "fmt"
)

type ShardingStrategy struct {
    dbCount  int
    tablePerDB int
}

func NewShardingStrategy(dbCount, tablePerDB int) *ShardingStrategy {
    return &ShardingStrategy{
        dbCount:    dbCount,
        tablePerDB: tablePerDB,
    }
}

func (s *ShardingStrategy) GetShard(key interface{}) (dbIndex, tableIndex int) {
    keyStr := fmt.Sprintf("%v", key)
    hash := hash(keyStr)
    
    totalTables := s.dbCount * s.tablePerDB
    tableIndex = int(hash) % totalTables
    dbIndex = tableIndex / s.tablePerDB
    tableIndex = tableIndex % s.tablePerDB
    
    return
}

func hash(s string) uint32 {
    var hash uint32
    for _, c := range s {
        hash = hash*31 + uint32(c)
    }
    return hash
}
```

---

## 7. 面试要点总结

### 7.1 设计原则

```
1. 明确需求
   ├── 功能需求
   └── 非功能需求

2. 估算规模
   ├── QPS
   ├── 数据量
   └── 存储需求

3. 高层设计
   ├── 组件选型
   └── 数据流

4. 详细设计
   ├── API 设计
   ├── 数据结构
   └── 一致性保证

5. 瓶颈分析
   ├── 性能瓶颈
   └── 扩展性瓶颈
```

### 7.2 常见问题

| 问题 | 考察点 | 关键方案 |
|------|--------|----------|
| URL短链 | ID生成/存储 | 雪花算法/进制转换 |
| 分布式锁 | 一致性/幂等 | Redis SET NX + Lua |
| 缓存架构 | 一致性/穿透 | Cache-Aside + 布隆 |
| 消息队列 | 一致性/吞吐 | Kafka + 幂等处理 |
| 数据库分片 | 一致性/迁移 | 哈希分片 + 双写 |

---

## 8. 总结

### 8.1 核心设计模式

| 模式 | 适用场景 |
|------|----------|
| Cache-Aside | 读多写少 |
| Read-Through | 透明缓存 |
| Write-Through | 强一致性 |
| Write-Behind | 高吞吐写入 |
| Side-DB | 最终一致性 |

### 8.2 面试技巧

1. **先问清楚需求** - 不要急于给方案
2. **估算规模** - 展示工程思维
3. **分层设计** - 从高层到低层
4. **权衡分析** - 展示权衡能力
5. **考虑边界** - 展示全面性

---

*最后更新：2026-08-11*
*作者：Ryan*
