# 广告系统故障排查案例库 - 资深专家深度实现

## 一、竞价系统故障排查

### 1.1 竞价超时问题

```go
// 竞价超时处理
func (b *BiddingEngine) HandleTimeout(request *BidRequest) error {
    // 1. 记录超时日志
    b.logger.Warn("bidding timeout", 
        "requestId", request.ID,
        "timeout", request.TimeoutMs,
        "dspCount", len(request.DSPs))
    
    // 2. 触发熔断器
    if b.circuitBreaker.IsOpen() {
        return errors.New("circuit breaker open")
    }
    
    // 3. 降级处理
    fallbackBid := b.generateFallbackBid(request)
    b.metrics.Increment("bidding.timeout.fallback")
    
    return nil
}

// 熔断器状态机
type CircuitBreaker struct {
    state      CircuitState
    failureCnt int
    threshold  int
}

type CircuitState int

const (
    Closed CircuitState = iota
    Open
    HalfOpen
)

func (cb *CircuitBreaker) Execute(fn func() error) error {
    switch cb.state {
    case Open:
        if time.Since(cb.openTime) > cb.recoveryTimeout {
            cb.state = HalfOpen
        } else {
            return errors.New("circuit breaker open")
        }
    case HalfOpen:
        err := fn()
        if err != nil {
            cb.state = Open
        } else {
            cb.state = Closed
        }
        return err
    default:
        return fn()
    }
}
```

### 1.2 内存泄漏问题

```go
// 内存泄漏检测
func (b *BiddingEngine) DetectMemoryLeak() {
    // 1. 检查goroutine数量
    numGoroutines := runtime.NumGoroutine()
    if numGoroutines > b.maxGoroutines {
        b.logger.Warn("high goroutine count", "count", numGoroutines)
    }
    
    // 2. 检查内存分配
    var m runtime.MemStats
    runtime.ReadMemStats(&m)
    
    // 3. 分析堆对象
    if m.HeapAlloc > b.maxHeapAlloc {
        b.logger.Warn("high heap alloc", "alloc", m.HeapAlloc)
    }
    
    // 4. GC频率分析
    gcCount := m.NumGC
    if gcCount > b.maxGcPerMinute && time.Since(b.lastGcTime) < time.Minute {
        b.logger.Warn("high gc frequency", "count", gcCount)
    }
}
```

## 二、Rta系统故障排查

### 2.1 数据同步延迟

```go
// RTA数据同步监控
func (r *RTAService) MonitorSyncLatency() {
    // 1. 监控同步延迟
    syncLatency := time.Since(r.lastSyncTime)
    if syncLatency > r.maxSyncLatency {
        r.logger.Warn("sync latency high", 
            "latency", syncLatency,
            "maxLatency", r.maxSyncLatency)
    }
    
    // 2. 检查队列堆积
    queueDepth := len(r.syncQueue)
    if queueDepth > r.maxQueueDepth {
        r.logger.Warn("sync queue deep", 
            "depth", queueDepth,
            "maxDepth", r.maxQueueDepth)
    }
    
    // 3. 分析同步失败率
    failRate := float64(r.syncFailures) / float64(r.syncAttempts)
    if failRate > r.maxFailRate {
        r.logger.Warn("sync fail rate high", 
            "rate", failRate,
            "maxRate", r.maxFailRate)
    }
}

// 补偿同步机制
func (r *RTAService) CompensateSync() {
    // 1. 查找未同步的数据
    pending := r.getPendingRecords()
    
    // 2. 批量同步
    for _, record := range pending {
        err := r.syncRecord(record)
        if err != nil {
            r.logger.Error("sync failed", "recordId", record.ID, "error", err)
            r.retrySync(record)
        }
    }
}
```

### 2.2 匹配准确率下降

```go
// 匹配质量监控
func (r *RTAService) MonitorMatchQuality() {
    // 1. 计算匹配率
    matchRate := float64(r.matchedRequests) / float64(r.totalRequests)
    if matchRate < r.minMatchRate {
        r.logger.Warn("match rate low", 
            "rate", matchRate,
            "minRate", r.minMatchRate)
    }
    
    // 2. 分析误判率
    falsePositiveRate := float64(r.falsePositives) / float64(r.totalMatches)
    if falsePositiveRate > r.maxFalsePositiveRate {
        r.logger.Warn("high false positive rate", 
            "rate", falsePositiveRate)
    }
    
    // 3. 检查数据 freshness
    staleDataRatio := r.calculateStaleDataRatio()
    if staleDataRatio > r.maxStaleRatio {
        r.logger.Warn("high stale data ratio", 
            "ratio", staleDataRatio)
    }
}
```

## 三、SSP系统故障排查

### 3.1 请求处理延迟

```go
// 延迟分析
func (s *SSPService) AnalyzeLatency(request *BidRequest) {
    // 1. 分段计时
    stages := map[string]time.Duration{
        "ad_unit_routing": s.adUnitRoutingTime,
        "dsp_selection":   s.dspSelectionTime,
        "bid_processing":  s.bidProcessingTime,
        "response_build":  s.responseBuildTime,
    }
    
    // 2. 找出瓶颈
    maxStage := ""
    maxTime := time.Duration(0)
    for stage, duration := range stages {
        if duration > maxTime {
            maxTime = duration
            maxStage = stage
        }
    }
    
    // 3. 告警
    if maxTime > s.maxStageLatency {
        s.logger.Warn("latency bottleneck", 
            "stage", maxStage,
            "time", maxTime)
    }
}
```

### 3.2 响应超时问题

```go
// 超时控制
func (s *SSPService) ControlTimeout(request *BidRequest) error {
    // 1. 设置超时
    ctx, cancel := context.WithTimeout(request.Context, s.timeout)
    defer cancel()
    
    // 2. 并行调用DSP
    results := make(chan *BidResponse, len(request.DSPs))
    errors := make(chan error, len(request.DSPs))
    
    for _, dsp := range request.DSPs {
        go func(dsp DSPClient) {
            resp, err := dsp.Bid(ctx, request)
            if err != nil {
                errors <- err
                return
            }
            results <- resp
        }(dsp)
    }
    
    // 3. 等待结果
    select {
    case resp := <-results:
        return s.processResponse(resp)
    case err := <-errors:
        return err
    case <-ctx.Done():
        return errors.New("timeout")
    }
}
```

## 四、面试高频题

### Q1: 如何排查竞价超时问题？

```
A:
1. 检查DSP响应时间
2. 分析网络延迟
3. 查看队列堆积情况
4. 检查熔断器状态
```

### Q2: 如何处理RTA数据同步延迟？

```
A:
1. 监控同步延迟指标
2. 分析队列堆积原因
3. 优化同步策略
4. 实现补偿机制
```

### Q3: 如何优化SSP响应速度？

```
A:
1. 并行调用DSP
2. 缓存常见响应
3. 优化路由策略
4. 调整超时配置
```

## 五、自测题

1. 竞价超时的排查步骤
2. RTA数据同步延迟的解决方案
3. SSP响应优化的方法

---

## 参考文档

- [竞价系统深度实现](./bidding-system-expert-deep.md)
- [RTA实现深度](../advertising/rta-implementation-deep.md)
- [SSP实现深度](../advertising/ssp/ssp-implementation-deep.md)
