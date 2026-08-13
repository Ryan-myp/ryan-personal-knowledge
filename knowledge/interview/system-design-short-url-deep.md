# 短链接系统设计 - 资深专家深度实现

## 一、系统架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         短链接系统架构                                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   ┌──────────┐    ┌──────────┐    ┌──────────┐                         │
│   │  用户浏览器 │───▶│  API网关  │───▶│ 短链服务  │                         │
│   └──────────┘    └──────────┘    └────┬─────┘                         │
│                                        │                                 │
│                              ┌─────────┼─────────┐                       │
│                              ▼         ▼         ▼                       │
│                        ┌────────┐ ┌────────┐ ┌────────┐                │
│                        │ Redis  │ │ MySQL  │ │ Redis  │                │
│                        │(缓存)  │ │(存储)  │ │(统计) │                │
│                        └────────┘ └────────┘ └────────┘                │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、核心实现

```go
package shortener

import (
    "context"
    "encoding/binary"
    "fmt"
    "hash/crc32"
    "sync/atomic"
    "time"
    
    "github.com/go-redis/redis/v8"
)

type Shortener struct {
    redis     *redis.Client
    counter   atomic.Uint64
    alphabet  string
}

const (
    base62 = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    prefix = "short:"
    urlKey = "url:"
)

func NewShortener(rds *redis.Client) *Shortener {
    return &Shortener{
        redis:    rds,
        alphabet: base62,
    }
}

// Generate 生成短链接
func (s *Shortener) Generate(ctx context.Context, longURL string, expireDays int) (string, error) {
    // 1. 检查是否已存在
    existing, err := s.getLongURL(ctx, longURL)
    if err == nil && existing != "" {
        return existing, nil
    }
    
    // 2. 生成唯一ID
    id := s.counter.Add(1)
    shortCode := s.encode(id)
    
    // 3. 存储映射关系
    key := fmt.Sprintf("%s%s", prefix, shortCode)
    ttl := time.Duration(expireDays) * 24 * time.Hour
    
    pipe := s.redis.Pipeline()
    pipe.Set(ctx, key, longURL, ttl)
    pipe.Set(ctx, fmt.Sprintf("%s%s", urlKey, longURL), shortCode, 0)
    _, err = pipe.Exec(ctx)
    
    if err != nil {
        return "", err
    }
    
    return shortCode, nil
}

// Redirect 短链接跳转
func (s *Shortener) Redirect(ctx context.Context, shortCode string) (string, error) {
    key := fmt.Sprintf("%s%s", prefix, shortCode)
    longURL, err := s.redis.Get(ctx, key).Result()
    if err != nil {
        return "", fmt.Errorf("短链接不存在")
    }
    
    // 增加访问计数
    s.redis.Incr(ctx, fmt.Sprintf("stats:%s", shortCode))
    
    return longURL, nil
}

// encode 将ID编码为短码
func (s *Shortener) encode(id uint64) string {
    if id == 0 {
        return string(s.alphabet[0])
    }
    
    var result []byte
    for id > 0 {
        result = append(result, s.alphabet[id%62])
        id /= 62
    }
    
    // 反转
    for i, j := 0, len(result)-1; i < j; i, j = i+1, j-1 {
        result[i], result[j] = result[j], result[i]
    }
    
    return string(result)
}
```

## 三、防重复设计

```go
// 方案1: 一致性哈希
func (s *Shortener) generateByHash(url string) string {
    hash := crc32.ChecksumIEEE([]byte(url))
    return s.encode(uint64(hash))
}

// 方案2: Snowflake ID
type Snowflake struct {
    workerID     int64
    sequence     int64
    lastTimestamp int64
}

func (sf *Snowflake) Next() int64 {
    timestamp := time.Now().UnixMilli()
    if timestamp < sf.lastTimestamp {
        // 时钟回退处理
        timestamp = sf.lastTimestamp
    }
    
    if timestamp == sf.lastTimestamp {
        sf.sequence = (sf.sequence + 1) & 0xFFF
        if sf.sequence == 0 {
            timestamp = sf.waitNextMillis()
        }
    } else {
        sf.sequence = 0
    }
    
    sf.lastTimestamp = timestamp
    return ((timestamp - sf.epoch) << 22) | (sf.workerID << 12) | sf.sequence
}
```

## 四、高并发优化

```go
// 本地缓存 + Redis二级缓存
type CacheShortener struct {
    local  *SyncMap   // 本地缓存
    remote *Shortener // Redis
}

func (c *CacheShortener) Generate(ctx context.Context, url string) (string, error) {
    // L1: 本地缓存
    if short, ok := c.local.Get(url); ok {
        return short, nil
    }
    
    // L2: Redis
    short, err := c.remote.Generate(ctx, url, 30)
    if err != nil {
        return "", err
    }
    
    // 回填本地缓存
    c.local.Set(url, short)
    return short, nil
}
```

## 五、面试高频题

### Q1: 如何保证短链接的唯一性？

```
A: 三种方案:
1. 自增ID + Base62编码: 最简单，可预测
2. 哈希截取: 有冲突风险，需要去重
3. 分布式ID(Snowflake): 唯一且有序

推荐方案: 自增ID + 分布式锁
```

### Q2: 如何处理短链接的过期？

```
A: Redis TTL自动过期 + 定期清理无效链接
```

### Q3: 如何统计短链接的访问量？

```
A: Redis INCR原子计数 + 定时聚合到ClickHouse
```

## 六、自测题

1. 短链接系统如何设计抗缓存穿透？
2. 如何实现短链接的预热功能？
3. 短链接系统的QPS瓶颈在哪里？

---

## 参考文档

- [TinyURL设计](https://blog.codinghorror.com/building-short-url-service/)
- [Redis最佳实践](https://redis.io/docs/manual/patterns/)
