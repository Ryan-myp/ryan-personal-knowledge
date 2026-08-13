# 系统设计面试题库 --- 资深专家深度实现

## 概述

系统设计是高级工程师招聘的核心考察点。本文总结高频系统设计题目的解题思路和参考实现。

## 一、常用设计模式

### 1.1 分层架构

```
┌─────────────────────────────────────────────────────────┐
│                    标准分层架构                          │
├─────────────────────────────────────────────────────────┤
│  API Layer:  RESTful API / GraphQL                      │
│  Service Layer: 业务逻辑封装                           │
│  Domain Layer: 核心业务模型                             │
│  Infrastructure: 数据存储 / 消息队列                   │
└─────────────────────────────────────────────────────────┘
```

### 1.2 常用组件

| 组件 | 用途 | 选型 |
|------|------|------|
| 缓存 | 加速读操作 | Redis / Memcached |
| 消息队列 | 解耦/异步 | Kafka / RocketMQ |
| 搜索引擎 | 全文检索 | Elasticsearch |
| 数据库 | 持久化存储 | MySQL / PostgreSQL |

## 二、高频题目

### 2.1 短链接系统

```go
// 核心设计
type ShortLinkService struct {
    store    Store
    cache    *redis.Client
    generator *Snowflake
}

func (s *ShortLinkService) Create(originalURL string) (string, error) {
    // 1. 生成短链
    id := s.generator.Generate()
    shortCode := IDToShortLink(id)
    
    // 2. 存储映射
    s.store.Save(shortCode, originalURL)
    
    // 3. 缓存
    s.cache.Set(context.Background(), 
        fmt.Sprintf("short:%s", shortCode), originalURL, 24*time.Hour)
    
    return shortCode, nil
}
```

### 2.2 限流器

```go
type RateLimiter interface {
    Allow(key string) bool
}

// 滑动窗口限流
type SlidingWindowLimiter struct {
    windowSize time.Duration
    maxRequests int
    redis *redis.Client
}

func (l *SlidingWindowLimiter) Allow(key string) bool {
    ctx := context.Background()
    now := time.Now()
    
    // 删除过期记录
    l.redis.ZRemRangeByScore(ctx, key, 0, now.Add(-l.windowSize).UnixNano())
    
    // 检查数量
    count := l.redis.ZCard(ctx, key).Val()
    if count >= int64(l.maxRequests) {
        return false
    }
    
    // 添加新请求
    l.redis.ZAdd(ctx, key, redis.Z{
        Score:  float64(now.UnixNano()),
        Member: fmt.Sprintf("%d", now.UnixNano()),
    })
    
    return true
}
```

### 2.3 分布式锁

```go
type DistributedLock struct {
    redis *redis.Client
    key   string
    value string
}

func (l *DistributedLock) Lock(timeout time.Duration) bool {
    ctx := context.Background()
    end := time.Now().Add(timeout)
    
    for time.Now().Before(end) {
        acquired, err := l.redis.SetNX(ctx, l.key, l.value, timeout).Result()
        if err == nil && acquired {
            return true
        }
        time.Sleep(100 * time.Millisecond)
    }
    return false
}

func (l *DistributedLock) Unlock() error {
    // Lua脚本保证原子性
    script := `
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
    `
    return l.redis.Eval(context.Background(), script, []string{l.key}, l.value).Err()
}
```

## 三、解题框架

### 3.1 需求澄清

```
1. 功能需求
   - 核心功能是什么？
   - 有哪些约束条件？

2. 规模估算
   - 用户量级？
   - QPS多少？
   - 数据存储量？

3. API设计
   - 主要接口有哪些？
```

### 3.2 容量估算

```go
// 存储估算
func EstimateStorage日均PV, retentionDays int) int64 {
    dailyRecords := dailyPV * 1024  // 假设每PV 1KB
    totalBytes := int64(dailyRecords) * retentionDays
    return totalBytes / 1024 / 1024 / 1024  // GB
}

// 带宽估算
func EstimateBandwidth(qps, avgSizeKB int) float64 {
    return float64(qps) * float64(avgSizeKB) / 1024  // Gbps
}
```

### 3.3 核心组件

```
┌─────────────────────────────────────────────────────────┐
│                  系统设计检查清单                         │
├─────────────────────────────────────────────────────────┤
│ □ 数据存储选型                                          │
│ □ 缓存策略                                              │
│ □ 消息队列使用                                          │
│ □ 负载均衡方案                                          │
│ □ 限流降级策略                                          │
│ □ 容灾备份                                              │
│ □ 监控告警                                              │
└─────────────────────────────────────────────────────────┘
```

## 四、面试高频题

### 4.1 高频问题

**Q1: 如何设计一个URL短链系统？**

A: 核心是ID生成和跳转，使用Base62编码自增ID或Hash值。

**Q2: 如何设计一个限流器？**

A: 令牌桶、漏桶、滑动窗口三种算法，根据场景选择。

**Q3: 如何设计分布式锁？**

A: Redis SETNX + Lua脚本保证原子性，考虑看门狗续期。

### 4.2 自测题

1. 设计一个分布式ID生成器
2. 设计一个消息队列
3. 设计一个定时任务系统
4. 设计一个配置中心
5. 设计一个服务注册发现

---

**创建时间**: 2026-10-17
**作者**: Ryan
**领域**: Interview / 系统设计
**关键词**: system-design, interview, architecture, pattern
