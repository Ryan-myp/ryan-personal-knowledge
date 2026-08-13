# 高并发架构设计 --- 资深专家深度实现

## 概述

高并发系统设计是后端工程师的核心能力。本文总结秒杀、大促、实时竞价等场景的架构设计模式。

## 一、架构分层

```
┌─────────────────────────────────────────────────────────┐
│                    高并发架构分层                        │
├─────────────────────────────────────────────────────────┤
│  L7:  CDN / WAF / 负载均衡                               │
│  L4:  Nginx / HAProxy                                   │
│  App: 微服务 / 无状态服务                                │
│  Cache: Redis集群 / 本地缓存                             │
│  DB:   MySQL分库分表 / 读写分离                          │
│  MQ:   Kafka / RocketMQ / RabbitMQ                     │
│  Storage: 对象存储 / 时序数据库                          │
└─────────────────────────────────────────────────────────┘
```

## 二、核心模式

### 2.1 读写分离

```go
// 主从路由
type DBRouter struct {
    master *gorm.DB
    slaves []*gorm.DB
    index  int
}

func (r *DBRouter) Read() *gorm.DB {
    slave := r.slaves[r.index%len(r.slaves)]
    r.index++
    return slave
}

func (r *DBRouter) Write() *gorm.DB {
    return r.master
}
```

### 2.2 缓存穿透防护

```go
// 布隆过滤器
type BloomFilter struct {
    bits   []uint64
    size   int
    hashFn func(string) uint64
}

func (bf *BloomFilter) Add(item string) {
    h := bf.hashFn(item)
    bf.bits[h%uint64(len(bf.bits)*64)] |= 1 << (h % 64)
}

func (bf *BloomFilter) MightContain(item string) bool {
    h := bf.hashFn(item)
    return (bf.bits[h%uint64(len(bf.bits)*64)] >> (h % 64)) & 1 == 1
}
```

### 2.3 限流降级

```go
// 令牌桶限流
type TokenBucket struct {
    tokens     float64
    maxTokens  float64
    refillRate float64
    lastRefill time.Time
    mu         sync.Mutex
}

func (tb *TokenBucket) Allow() bool {
    tb.mu.Lock()
    defer tb.mu.Unlock()
    
    now := time.Now()
    tb.tokens += tb.refillRate * now.Sub(tb.lastRefill).Seconds()
    if tb.tokens > tb.maxTokens {
        tb.tokens = tb.maxTokens
    }
    tb.lastRefill = now
    
    if tb.tokens >= 1 {
        tb.tokens--
        return true
    }
    return false
}
```

## 三、容量规划

### 3.1 压测模型

```go
// 容量估算公式
// 峰值QPS = 日活 × 活跃度 × 转化率 / 高峰期时长
// 服务器数量 = 峰值QPS / 单机QPS × 冗余系数

func CalculateCapacity(dau, activityRate, conversionRate float64, 
    peakHours float64, singleQPS int) int {
    
    peakQPS := dau * activityRate * conversionRate / peakHours
    machines := int(math.Ceil(peakQPS / float64(singleQPS) * 1.5))
    return machines
}
```

### 3.2 压测工具

```bash
# ab压测
ab -n 10000 -c 100 http://example.com/api/test

# wrk压测
wrk -t12 -c400 -d30s http://example.com/api/test

# k6压测
k6 run script.js
```

## 四、故障恢复

### 4.1 熔断降级

```go
import "github.com/sony/gobreaker"

var settings = gobreaker.Settings{
    Name:    "OrderService",
    Timeout: 5 * time.Second,
    ReadyToTrip: func(counts Countss) bool {
        return counts.ConsecutiveFailures >= 5
    },
    OnStateChange: func(name string, from gobreaker.State, to gobreaker.State) {
        log.Printf("%s: %s -> %s", name, from, to)
    },
}

var breaker = gobreaker.NewCircuitBreaker(settings)

func CallService() error {
    result, err := breaker.Execute(func() (interface{}, error) {
        return httpClient.Get("http://backend/api")
    })
    return err
}
```

### 4.2 幂等设计

```go
// 基于Token的幂等
type IdempotentHandler struct {
    redis *redis.Client
}

func (h *IdempotentHandler) Handle(token string, handler func() error) error {
    // 1. 检查Token是否存在
    exist, _ := h.redis.Exists(context.Background(), 
        fmt.Sprintf("idempotent:%s", token)).Result()
    if exist > 0 {
        return errors.New("重复请求")
    }
    
    // 2. 设置Token（一次性）
    h.redis.SetNX(context.Background(), 
        fmt.Sprintf("idempotent:%s", token), "1", time.Minute*10)
    
    // 3. 执行业务逻辑
    err := handler()
    if err != nil {
        h.redis.Del(context.Background(), 
            fmt.Sprintf("idempotent:%s", token))
    }
    
    return err
}
```

## 五、监控告警

### 5.1 核心指标

```go
type SystemMetrics struct {
    CPUUsage    float64
    MemoryUsage float64
    DiskIO      float64
    NetworkIn   float64
    NetworkOut  float64
    QPS         float64
    LatencyP99  float64
    ErrorRate   float64
}
```

### 5.2 告警规则

```yaml
alerts:
  - name: high_cpu
    expr: cpu_usage > 80
    for: 5m
    labels:
      severity: warning
      
  - name: high_error_rate
    expr: error_rate > 0.05
    for: 1m
    labels:
      severity: critical
```

## 六、面试高频题

### 6.1 高频问题

**Q1: 高并发系统的核心挑战是什么？**

A: 流量控制、数据一致性、故障恢复、容量规划。

**Q2: 如何设计一个限流器？**

A: 令牌桶、漏桶、滑动窗口。

**Q3: 如何保证数据一致性？**

A: 最终一致性 + 补偿事务 + 对账机制。

### 6.2 自测题

1. 画出高并发系统架构图
2. 设计一个限流器
3. 分析缓存穿透/击穿/雪崩
4. 设计幂等接口方案
5. 解释熔断降级原理

---

**创建时间**: 2026-10-17
**作者**: Ryan
**领域**: Interview / 系统设计
**关键词**: high-concurrency, architecture, rate-limit, circuit-breaker, idempotent
