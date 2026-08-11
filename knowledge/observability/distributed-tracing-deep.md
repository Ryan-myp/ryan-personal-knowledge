# 分布式链路追踪深度解析

> 深入分布式追踪：Trace/Span、采样策略、上下文传播、性能分析。
> 包含生产环境Tracing系统设计。
> 适用对象：SRE、后端工程师

---

## 1. 链路追踪架构

### 1.1 核心概念

```
链路追踪核心概念：

├── Trace (追踪)
│   └── 一次请求的完整调用链

├── Span (跨度)
│   ├── 一次操作单元
│   ├── 包含开始时间、结束时间
│   └── 父子关系

├── Context (上下文)
│   ├── TraceID
│   ├── SpanID
│   └── 传播信息

└── Collector (收集器)
    ├── 接收Span数据
    └── 存储和查询
```

### 1.2 Go 实现追踪核心

```go
// tracing.go

package trace

import (
    "context"
    "sync"
    "time"
)

type Trace struct {
    TraceID string
    Spans   []*Span
    mu      sync.Mutex
}

type Span struct {
    TraceID     string
    SpanID      string
    ParentID    string
    Operation   string
    StartTime   time.Time
    EndTime     time.Time
    Tags        map[string]string
    Logs        []Log
    Duration    time.Duration
}

type Context struct {
    TraceID  string
    SpanID   string
    Sampled  bool
}

type Tracer struct {
    provider  Provider
    sampler   Sampler
    mu        sync.Mutex
    traces    map[string]*Trace
}

type Provider interface {
    Export(spans []*Span) error
}

type Sampler interface {
    ShouldSample(traceID string) bool
}

func NewTracer(provider Provider, sampler Sampler) *Tracer {
    return &Tracer{
        provider: provider,
        sampler:  sampler,
        traces:   make(map[string]*Trace),
    }
}

func (t *Tracer) StartSpan(ctx context.Context, operation string) (*Span, context.Context) {
    span := &Span{
        Operation: operation,
        StartTime: time.Now(),
        Tags:      make(map[string]string),
    }
    
    // 生成TraceID和SpanID
    span.TraceID = t.generateTraceID()
    span.SpanID = t.generateSpanID()
    
    // 检查采样
    if !t.sampler.ShouldSample(span.TraceID) {
        span.Tags["sampled"] = "false"
    } else {
        span.Tags["sampled"] = "true"
    }
    
    // 创建上下文
    ctx = context.WithValue(ctx, contextKey{}, &Context{
        TraceID: span.TraceID,
        SpanID:  span.SpanID,
        Sampled: span.Tags["sampled"] == "true",
    })
    
    t.mu.Lock()
    defer t.mu.Unlock()
    
    if t.traces[span.TraceID] == nil {
        t.traces[span.TraceID] = &Trace{TraceID: span.TraceID}
    }
    t.traces[span.TraceID].Spans = append(t.traces[span.TraceID].Spans, span)
    
    return span, ctx
}

func (t *Tracer) FinishSpan(span *Span) {
    span.EndTime = time.Now()
    span.Duration = span.EndTime.Sub(span.StartTime)
}
```

---

## 2. 采样策略

### 2.1 采样算法

```
采样策略：

├── 固定采样
│   └── 固定比例采样 (1%)

├── 优先采样
│   ├── 错误请求优先
│   └── 慢请求优先

├── 自适应采样
│   ├── 根据负载调整
│   └── 根据错误率调整

└── 分层采样
    ├── 根Span全量
    └── 子Span按比例
```

### 2.2 Go 实现采样

```go
// sampler.go

package trace

import (
    "sync/atomic"
)

type Sampler interface {
    ShouldSample(traceID string) bool
}

type RateSampler struct {
    rate     float64
    counter  uint64
}

func NewRateSampler(rate float64) *RateSampler {
    return &RateSampler{
        rate: rate,
    }
}

func (rs *RateSampler) ShouldSample(traceID string) bool {
    rs.counter++
    return float64(rs.counter%10000) < rs.rate*100
}

type PrioritySampler struct {
    errorRate  float64
    slowRate   float64
    defaultRate float64
}

func (ps *PrioritySampler) ShouldSample(traceID string, tags map[string]string) bool {
    // 错误请求优先采样
    if tags["error"] == "true" {
        return true
    }
    
    // 慢请求优先采样
    if duration, ok := tags["duration"]; ok {
        if duration > "1s" {
            return true
        }
    }
    
    // 默认采样
    return ps.defaultRate >= 0.01
}

type AdaptiveSampler struct {
    currentRate   float64
    targetRate    float64
    lastAdjust    time.Time
    interval      time.Duration
}

func NewAdaptiveSampler(targetRate float64) *AdaptiveSampler {
    return &AdaptiveSampler{
        currentRate: targetRate,
        targetRate:  targetRate,
        interval:    time.Minute,
    }
}

func (as *AdaptiveSampler) ShouldSample(traceID string) bool {
    // 调整采样率
    if time.Since(as.lastAdjust) > as.interval {
        as.adjustRate()
        as.lastAdjust = time.Now()
    }
    
    return float64(randomUint64()%10000) < as.currentRate*100
}

func (as *AdaptiveSampler) adjustRate() {
    // 根据系统负载调整采样率
    // ...[truncated]
}
```

---

## 3. 上下文传播

### 3.1 传播格式

```
上下文传播格式：

├── W3C Trace Context
│   ├── trace-id
│   ├── parent-id
│   └── flags
│
├── B3 Propagation
│   ├── X-B3-TraceId
│   ├── X-B3-SpanId
│   └── X-B3-Sampled
│
└── Jaeger Propagation
    ├── uber-trace-id
    └── 编码格式
```

### 3.2 Go 实现传播

```go
// propagation.go

package trace

import (
    "context"
    "encoding/binary"
    "encoding/hex"
    "net/http"
)

type ContextKey struct{}

type Propagator interface {
    Inject(ctx context.Context, carrier interface{}) error
    Extract(carrier interface{}) (context.Context, error)
}

type W3CPropagator struct{}

func (p *W3CPropagator) Inject(ctx context.Context, carrier interface{}) error {
    context := ctx.Value(ContextKey{}).(*Context)
    if context == nil {
        return nil
    }
    
    headers := carrier.(*http.Header)
    traceID := hex.EncodeToString([]byte(context.TraceID))
    spanID := hex.EncodeToString([]byte(context.SpanID))
    
    headers.Set("traceparent", 
        fmt.Sprintf("00-%s-%s-%02d", traceID, spanID, 
            boolToByte(context.Sampled)))
    
    return nil
}

func (p *W3CPropagator) Extract(carrier interface{}) (context.Context, error) {
    headers := carrier.(*http.Header)
    traceparent := headers.Get("traceparent")
    
    // 解析traceparent
    // ...[truncated]
    
    ctx := context.WithValue(context.Background(), ContextKey{}, &Context{
        TraceID: traceID,
        SpanID:  spanID,
        Sampled: sampled,
    })
    
    return ctx, nil
}

func boolToByte(b bool) byte {
    if b {
        return 01
    }
    return 00
}
```

---

## 4. 性能分析

### 4.1 分析指标

```
追踪性能分析指标：

├── 延迟分析
│   ├── P50/P90/P99延迟
│   └── 耗时分布
│
├── 吞吐量分析
│   ├── QPS趋势
│   └── 错误率
│
└── 依赖分析
    ├── 服务调用拓扑
    └── 热点链路
```

### 4.2 Go 实现分析

```go
// analyzer.go

package trace

import (
    "sort"
    "sync"
    "time"
)

type Analyzer struct {
    traces     []*Trace
    mu         sync.Mutex
}

type TraceStats struct {
    Total      int
    AvgLatency float64
    P50Latency float64
    P90Latency float64
    P99Latency float64
    ErrorRate  float64
}

func (a *Analyzer) GetStats() *TraceStats {
    a.mu.Lock()
    defer a.mu.Unlock()
    
    if len(a.traces) == 0 {
        return &TraceStats{}
    }
    
    // 计算延迟
    var latencies []float64
    var errors int
    
    for _, trace := range a.traces {
        for _, span := range trace.Spans {
            latencies = append(latencies, span.Duration.Seconds()*1000)
            if span.Tags["error"] == "true" {
                errors++
            }
        }
    }
    
    sort.Float64s(latencies)
    
    return &TraceStats{
        Total:      len(a.traces),
        AvgLatency: average(latencies),
        P50Latency: percentile(latencies, 50),
        P90Latency: percentile(latencies, 90),
        P99Latency: percentile(latencies, 99),
        ErrorRate:  float64(errors) / float64(len(latencies)),
    }
}

func average(values []float64) float64 {
    sum := 0.0
    for _, v := range values {
        sum += v
    }
    return sum / float64(len(values))
}

func percentile(values []float64, p float64) float64 {
    if len(values) == 0 {
        return 0
    }
    index := p / 100 * float64(len(values)-1)
    lower := int(index)
    upper := lower + 1
    if upper >= len(values) {
        upper = len(values) - 1
    }
    weight := index - float64(lower)
    return values[lower]*(1-weight) + values[upper]*weight
}
```

---

## 5. 总结

### 5.1 核心组件回顾

| 组件 | 职责 |
|------|------|
| Tracer | 创建和管理Span |
| Sampler | 控制采样率 |
| Propagator | 传播上下文 |
| Analyzer | 性能分析 |

### 5.2 最佳实践

- [ ] 选择合适的采样策略
- [ ] 统一上下文传播格式
- [ ] 监控追踪性能开销
- [ ] 建立告警机制

---

*最后更新：2026-08-11*
*作者：Ryan*
