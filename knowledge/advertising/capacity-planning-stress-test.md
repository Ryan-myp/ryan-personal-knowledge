# 广告平台容量规划与压测实战

> QPS 估算/瓶颈识别/压测方案/容量规划/弹性伸缩

---

## 第一部分：入门引导（5 分钟速览）

### 广告平台容量规划要素

```
用户规模 → 日活跃用户(DAU) → 请求率 → 峰值 QPS → 服务器数量
    ↓
竞价延迟要求 → RTT < 100ms → 优化方向
    ↓
存储需求 → 日志量 → 磁盘/内存规划
```

---

## 第二部分：QPS 估算

### 2.1 流量估算公式

```
日活用户(DAU): 1000万
人均浏览: 50次/天
曝光请求率: 80% (50 * 0.8 = 40次/天)
总日请求: 1000万 * 40 = 4亿次/天
峰值系数: 3x (午高峰)
小时均匀分布: 4亿 / 24 = 1670万次/小时
分钟均匀分布: 1670万 / 60 = 278万次/分钟
秒均匀分布: 278万 / 60 = 46300次/秒
峰值系数: 5x (秒级峰值)
峰值 QPS: 46300 * 5 = 231500次/秒

结论: 需要支撑 25万 QPS
```

### 2.2 资源估算

```
单实例 QPS: 5000 (Go + SSD)
需要实例数: 250000 / 5000 = 50 实例

单机资源:
CPU: 8核
内存: 32GB
网络: 10Gbps

总资源:
CPU: 50 * 8 = 400核
内存: 50 * 32GB = 1600GB
```

---

## 第三部分：压测方案

### 3.1 Go 压测工具

```go
package stress

import (
    "context"
    "fmt"
    "sync"
    "time"
)

type StressTest struct {
    workers int
    total   int
    targetQPS int
}

func (st *StressTest) Run() *Result {
    var wg sync.WaitGroup
    var mu sync.Mutex
    var success, fail int
    var latencies []time.Duration
    
    start := time.Now()
    
    // 速率控制
    ticker := time.NewTicker(time.Second / time.Duration(st.targetQPS/st.workers))
    defer ticker.Stop()
    
    for i := 0; i < st.total; i++ {
        wg.Add(1)
        
        go func(idx int) {
            defer wg.Done()
            
            <-ticker.C
            
            reqStart := time.Now()
            err := st.makeRequest(idx)
            latency := time.Since(reqStart)
            
            mu.Lock()
            if err == nil {
                success++
            } else {
                fail++
            }
            latencies = append(latencies, latency)
            mu.Unlock()
        }(i)
    }
    
    wg.Wait()
    duration := time.Since(start)
    
    // 计算百分位数
    p50, p90, p95, p99 := st.calculatePercentiles(latencies)
    
    return &Result{
        Duration: duration,
        Success:  success,
        Fail:     fail,
        QPS:      float64(success) / duration.Seconds(),
        P50:      p50,
        P90:      p90,
        P95:      p95,
        P99:      p99,
    }
}

func (st *StressTest) makeRequest(id int) error {
    // 模拟请求
    return nil
}

func (st *StressTest) calculatePercentiles(latencies []time.Duration) (time.Duration, time.Duration, time.Duration, time.Duration) {
    // 排序
    sort.Slice(latencies, func(i, j int) bool {
        return latencies[i] < latencies[j]
    })
    
    n := len(latencies)
    return latencies[n/2], latencies[n*9/10], latencies[n*95/100], latencies[n*99/100]
}

type Result struct {
    Duration time.Duration
    Success  int
    Fail     int
    QPS      float64
    P50, P90, P95, P99 time.Duration
}
```

### 3.2 压测报告

```
压测结果:
┌─────────────┬──────────────┐
│ 指标         │ 数值         │
├─────────────┼──────────────┤
│ 持续时间     │ 300s         │
│ 总请求数     │ 7,500,000    │
│ 成功数       │ 7,492,500    │
│ 失败数       │ 7,500        │
│ QPS          │ 25,000       │
│ P50          │ 12ms         │
│ P90          │ 45ms         │
│ P95          │ 89ms         │
│ P99          │ 156ms        │
│ 错误率       │ 0.1%         │
└─────────────┴──────────────┘

瓶颈分析:
1. CPU: 65% - 正常
2. 内存: 70% - 接近上限
3. 网络: 40% - 正常
4. 磁盘: 85% - IO 瓶颈
5. 数据库: 90% - 连接池满

优化建议:
1. 增加磁盘 IO (SSD)
2. 增加数据库连接池
3. 优化慢查询
4. 增加缓存命中率
```

---

## 第四部分：容量规划

### 4.1 弹性伸缩策略

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: bidding-service-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: bidding-service
  minReplicas: 10
  maxReplicas: 100
  metrics:
  - type: Pods
    pods:
      metric:
        name: bids_per_second
      target:
        type: AverageValue
        averageValue: "5000"
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
```

### 4.2 多机房容灾

```
机房规划:
- 北京机房: 主要流量 60%
- 上海机房: 次要流量 30%
- 广州机房: 容灾 10%

流量切换:
1. 正常: 北京 60% / 上海 30% / 广州 10%
2. 上海故障: 北京 80% / 广州 20%
3. 北京故障: 上海 70% / 广州 30%

数据同步:
- 实时同步: MySQL 主从 + Kafka 同步
- 异步同步: Redis 跨机房复制
- 备份: 每日全量备份 + binlog
```

---

## 第五部分：自测题

### 问题 1
如何估算广告平台 QPS？

<details>
<summary>查看答案</summary>

1. DAU * 人均浏览 * 曝光率 = 日请求
2. 日请求 / 24h / 60min / 60s = 平均 QPS
3. 平均 QPS * 峰值系数 = 峰值 QPS
4. 考虑节假日效应
5. 预留 30% 余量

</details>

### 问题 2
压测时如何识别瓶颈？

<details>
<summary>查看答案</summary>

1. 监控 CPU/内存/网络/磁盘
2. 分析 P99 延迟分布
3. 检查数据库连接池
4. 检查缓存命中率
5. 使用 PPROF 分析

</details>

### 问题 3
弹性伸缩怎么配置？

<details>
<summary>查看答案</summary>

1. HPA 基于 CPU 和目标 QPS
2. minReplicas 保证可用性
3. maxReplicas 控制成本
4. 预热/冷却时间避免抖动
5. 多机房容灾配合

</details>

---

*本文档基于容量规划与压测经验整理。*