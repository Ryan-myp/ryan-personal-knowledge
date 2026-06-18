# 广告架构深度：高并发/容量规划/压测实战

> 广告系统高并发架构设计、容量规划方法、压测实战

---

## 第一部分：广告系统高并发挑战

### 并发场景分析

```
广告系统高并发场景：
┌─────────────────────────────────────────────────────────────────────┐
│ 1. 竞价请求                                                           │
│    • QPS: 100K+                                                       │
│    • P99 延迟: < 50ms                                                 │
│    • 特点：读多写少，需要快速响应                                     │
│                                                                     │
│ 2. 曝光/点击追踪                                                      │
│    • QPS: 500K+                                                       │
│    • 特点：写多读少，需要高吞吐                                       │
│                                                                     │
│ 3. 预算扣减                                                           │
│    • QPS: 100K+                                                       │
│    • 特点：强一致性，需要原子操作                                     │
│                                                                     │
│ 4. 报表查询                                                           │
│    • QPS: 1K+                                                         │
│    • 特点：复杂聚合，需要高性能                                       │
└─────────────────────────────────────────────────────────────────────┘
```

### 高并发架构设计

```
┌─────────────────────────────────────────────────────────────────────┐
│                    广告系统高并发架构                                 │
│                                                                     │
│  Layer 1: 接入层                                                    │
│  • Nginx/Envoy 负载均衡                                               │
│  • 连接池管理                                                        │
│  • 限流/熔断                                                         │
│                                                                     │
│  Layer 2: 服务层                                                    │
│  • Bidder Service（竞价服务）- 无状态，水平扩展                         │
│  • Tracker Service（追踪服务）- 异步写入 Kafka                         │
│  • Billing Service（计费服务）- Redis 原子扣减                         │
│  • Ranker Service（排序服务）- GPU 加速                              │
│                                                                     │
│  Layer 3: 缓存层                                                    │
│  • L1: Go sync.Map（本地缓存）                                       │
│  • L2: Redis Cluster（分布式缓存）                                    │
│  • L3: MySQL/TiKV（持久化存储）                                     │
│                                                                     │
│  Layer 4: 消息队列                                                  │
│  • Kafka：事件流（曝光/点击/转化）                                    │
│  • 分区策略：按 campaign_id hash                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 第二部分：容量规划

### 容量规划方法

```
容量规划公式：
所需实例数 = 峰值 QPS / (单实例 QPS * 利用率)

示例：
• 峰值 QPS: 100,000
• 单实例 QPS: 10,000
• 目标利用率: 70%
• 所需实例 = 100,000 / (10,000 * 0.7) = 14.3 ≈ 15 实例

考虑因素：
1. 峰值系数：日常峰值 vs 大促峰值（通常 3-5 倍）
2. 增长预留：未来 6-12 个月增长（通常 +50%）
3. 故障容错：额外 +20% 应对实例故障
4. 最终：15 * 3（大促）* 1.5（增长）* 1.2（容错）≈ 324 实例
```

### 压测实战

```go
package loadtest

import (
    "context"
    "fmt"
    "net/http"
    "sync"
    "sync/atomic"
    "time"
)

// LoadTestConfig 压测配置
type LoadTestConfig struct {
    TargetURL     string
    Concurrency   int           // 并发数
    Duration      time.Duration // 持续时间
    RPS           int           // 目标 RPS
}

// LoadTestResult 压测结果
type LoadTestResult struct {
    TotalRequests  int64
    SuccessCount   int64
    ErrorCount     int64
    MinLatency     time.Duration
    MaxLatency     time.Duration
    AvgLatency     time.Duration
    P50Latency     time.Duration
    P99Latency     time.Duration
    RPS            float64
}

// RunLoadTest 执行压测
func RunLoadTest(ctx context.Context, cfg LoadTestConfig) (*LoadTestResult, error) {
    var (
        successCount int64
        errorCount   int64
        latencies    []time.Duration
        latencyMu    sync.Mutex
        wg           sync.WaitGroup
    )
    
    start := time.Now()
    rpsCh := make(chan time.Time, cfg.RPS)
    
    // 限速器
    go func() {
        ticker := time.NewTicker(time.Second / time.Duration(cfg.RPS))
        defer ticker.Stop()
        for t := range ticker.C {
            select {
            case rpsCh <- t:
            case <-ctx.Done():
                return
            }
        }
    }()
    
    // 并发请求
    for i := 0; i < cfg.Concurrency; i++ {
        wg.Add(1)
        go func() {
            defer wg.Done()
            for {
                select {
                case <-rpsCh:
                    reqStart := time.Now()
                    resp, err := http.Get(cfg.TargetURL)
                    elapsed := time.Since(reqStart)
                    
                    latencyMu.Lock()
                    latencies = append(latencies, elapsed)
                    latencyMu.Unlock()
                    
                    if err == nil && resp.StatusCode == 200 {
                        atomic.AddInt64(&successCount, 1)
                    } else {
                        atomic.AddInt64(&errorCount, 1)
                    }
                    resp.Body.Close()
                    
                case <-ctx.Done():
                    return
                }
            }
        }()
    }
    
    // 等待完成
    time.Sleep(cfg.Duration)
    close(rpsCh)
    wg.Wait()
    
    // 计算统计
    result := &LoadTestResult{
        TotalRequests: atomic.LoadInt64(&successCount) + atomic.LoadInt64(&errorCount),
        SuccessCount:  successCount,
        ErrorCount:    errorCount,
        RPS:           float64(atomic.LoadInt64(&successCount)) / cfg.Duration.Seconds(),
    }
    
    // 计算延迟统计
    if len(latencies) > 0 {
        min, max, avg := latencies[0], latencies[0], time.Duration(0)
        for _, l := range latencies {
            if l < min { min = l }
            if l > max { max = l }
            avg += l
        }
        avg /= time.Duration(len(latencies))
        
        result.MinLatency = min
        result.MaxLatency = max
        result.AvgLatency = avg
        result.P50Latency = percentile(latencies, 50)
        result.P99Latency = percentile(latencies, 99)
    }
    
    return result, nil
}

func percentile(latencies []time.Duration, p float64) time.Duration {
    if len(latencies) == 0 {
        return 0
    }
    // 排序
    sorted := make([]time.Duration, len(latencies))
    copy(sorted, latencies)
    // ... 排序逻辑
    idx := int(float64(len(sorted)) * p / 100)
    if idx >= len(sorted) {
        idx = len(sorted) - 1
    }
    return sorted[idx]
}
```

---

## 第三部分：自测题

### Q1: 广告系统高并发的核心挑战是什么？

**A**: 竞价请求需要低延迟（< 50ms），追踪事件需要高吞吐（500K+ QPS），预算扣减需要强一致性。这三者需要不同的架构策略。

### Q2: 容量规划的关键因素？

**A**: 峰值 QPS、单实例能力、利用率目标、增长预留、故障容错。公式：实例数 = 峰值 QPS / (单实例 QPS * 利用率)。

### Q3: 压测的核心指标？

**A**: 总请求数、成功率、P50/P99 延迟、RPS、错误数。重点关注 P99 延迟，因为广告竞价对尾部延迟敏感。

---

## 第四部分：生产实践

### 1. 限流策略

```
限流策略：
1. 令牌桶：平滑限流，适合竞价服务
2. 漏桶：匀速处理，适合追踪服务
3. 滑动窗口：精确控制，适合预算扣减
4. 自适应限流：根据系统负载动态调整
```

### 2. 缓存策略

```
缓存策略：
1. 本地缓存（sync.Map）：热点数据，TTL 30s
2. Redis Cluster：分布式缓存，TTL 5min
3. 多级缓存：L1 本地 → L2 Redis → L3 DB
4. 缓存预热：启动时加载热点数据
```

### 3. 监控告警

```
监控告警：
1. QPS 突增/突降 → 告警
2. P99 延迟 > 100ms → 告警
3. 错误率 > 1% → 告警
4. 缓存命中率 < 90% → 告警
5. 连接池使用率 > 80% → 告警
```
