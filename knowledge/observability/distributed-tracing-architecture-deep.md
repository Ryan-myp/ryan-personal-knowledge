# 分布式追踪系统设计深度解析

> 深入分布式追踪核心：OpenTelemetry、Jaeger、Zipkin、链路采集、采样策略、性能分析。
> 适用对象：SRE 工程师、后端架构师

---

## 1. 追踪基础概念

### 1.1 核心术语

```
┌─────────────────────────────────────────────────────────────────┐
│                      追踪数据模型                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   Trace (链路)                                                  │
│   ├── Span 1: API Gateway (100ms)                              │
│   │   ├── Span 1.1: Auth Check (10ms)                          │
│   │   ├── Span 1.2: DB Query (50ms)                            │
│   │   │   └── Span 1.2.1: Redis Cache (5ms)                    │
│   │   └── Span 1.3: External API (40ms)                        │
│   └── Span 2: Worker (200ms)                                   │
│       └── Span 2.1: Message Queue (150ms)                      │
│                                                                 │
│   • TraceID: 标识一次完整请求链路                               │
│   • SpanID: 标识一个操作单元                                    │
│   • ParentSpanID: 父节点 SpanID                                 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 数据模型

```go
type Span struct {
    TraceID       string         `json:"trace_id"`
    SpanID        string         `json:"span_id"`
    ParentSpanID  string         `json:"parent_span_id"`
    OperationName string         `json:"operation_name"`
    ServiceName   string         `json:"service_name"`
    StartTime     time.Time      `json:"start_time"`
    Duration      time.Duration  `json:"duration"`
    Status        SpanStatus     `json:"status"`
    Tags          map[string]string `json:"tags"`
    Logs          []LogEntry     `json:"logs"`
    ChildSpans    []Span         `json:"child_spans"`
}

type SpanStatus int
const (
    STATUS_UNSET SpanStatus = iota
    STATUS_OK
    STATUS_ERROR
)
```

---

## 2. OpenTelemetry 架构

### 2.1 核心组件

```
┌─────────────────────────────────────────────────────────────────┐
│                     OpenTelemetry 架构                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────┐    ┌─────────────────┐                    │
│  │   Instrumentation│    │   SDK           │                    │
│  │   Libraries     │───▶│   - Tracer      │                    │
│  │   (自动/手动)   │    │   - Propagator  │                    │
│  └─────────────────┘    │   - Sampler     │                    │
│                         └────────┬────────┘                    │
│                                  │ Export                      │
│                         ┌────────┴────────┐                    │
│                         │   Collector     │                    │
│                         │   - 接收        │                    │
│                         │   - 处理        │                    │
│                         │   - 转发        │                    │
│                         └────────┬────────┘                    │
│                                  │                             │
│                    ┌─────────────┼─────────────┐               │
│                    ▼             ▼             ▼               │
│              ┌─────────┐  ┌─────────┐  ┌─────────┐            │
│              │ Jaeger  │  │Prometheus│  │ Loki   │            │
│              │ (存储)  │  │ (指标)   │  │ (日志)  │            │
│              └─────────┘  └─────────┘  └─────────┘            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Go SDK 实现

```go
package trace

import (
    "context"
    "go.opentelemetry.io/otel"
    "go.opentelemetry.io/otel/attribute"
    "go.opentelemetry.io/otel/exporters/jaeger"
    "go.opentelemetry.io/otel/sdk/trace"
    semconv "go.opentelemetry.io/otel/semconv/v1.21.0"
)

func InitTracer(serviceName string) (*trace.TracerProvider, error) {
    // 创建 Jaeger 导出器
    exporter, err := jaeger.New(jaeger.WithCollectorEndpoint(
        jaeger.WithEndpoint("http://localhost:14268/api/traces"),
    ))
    if err != nil {
        return nil, err
    }

    // 创建 TracerProvider
    tp := trace.NewTracerProvider(
        trace.WithBatcher(exporter),
        trace.WithSampler(trace.ParentBased(trace.TraceIDRatioBased(0.1))),
    )

    // 设置全局 TracerProvider
    otel.SetTracerProvider(tp)
    
    return tp, nil
}

// 使用示例
func ProcessOrder(ctx context.Context, orderID string) error {
    tracer := otel.Tracer("order-service")
    
    ctx, span := tracer.Start(ctx, "process_order")
    defer span.End()
    
    span.SetAttributes(
        attribute.String("order.id", orderID),
        attribute.Int("order.amount", 99),
    )
    
    // 子操作
    validateOrder(ctx, orderID)
    processPayment(ctx, orderID)
    notifyShipping(ctx, orderID)
    
    return nil
}

func validateOrder(ctx context.Context, orderID string) {
    tracer := otel.Tracer("order-service")
    _, span := tracer.Start(ctx, "validate_order")
    defer span.End()
    
    span.AddEvent("validation_started")
    // ... 业务逻辑
}
```

---

## 3. 采样策略

### 3.1 采样算法对比

```go
package sampler

import (
    "hash/fnv"
    "math/rand"
)

// 1. 头部采样 (Head-based)
type HeadSampler struct {
    Ratio float64
}

func (s *HeadSampler) ShouldSample(parentContext, traceID string) bool {
    return rand.Float64() < s.Ratio
}

// 2. 尾部采样 (Tail-based)
type TailSampler struct {
    WindowSize time.Duration
    Ratio      float64
}

func (s *TailSampler) ShouldSample(span *Span) bool {
    // 等待窗口结束，统计整个 Trace
    if span.Duration < s.WindowSize {
        return true // 先记录
    }
    // 基于 Trace 级别的采样决策
    hash := fnvHash(span.TraceID)
    return float64(hash%10000) < uint32(s.Ratio*10000)
}

// 3. 基于属性的采样
type AttributeSampler struct {
    Rules []SamplingRule
}

type SamplingRule struct {
    ServiceName string
    Operation   string
    Condition   SamplingCondition
    Ratio       float64
}

func (s *AttributeSampler) ShouldSample(span *Span) bool {
    for _, rule := range s.Rules {
        if span.ServiceName == rule.ServiceName &&
           span.Operation == rule.Operation {
            return rand.Float64() < rule.Ratio
        }
    }
    return true // 默认全量
}

// 4. 自适应采样
type AdaptiveSampler struct {
    BaseRatio    float64
    ErrorRatio   float64
    SlowRatio    float64
    Threshold    time.Duration
}

func (s *AdaptiveSampler) ShouldSample(span *Span) bool {
    // 错误链路全量采样
    if span.Status == STATUS_ERROR {
        return true
    }
    // 慢请求采样
    if span.Duration > s.Threshold {
        return true
    }
    // 正常链路按比例采样
    return rand.Float64() < s.BaseRatio
}
```

### 3.2 采样策略选择

| 场景 | 推荐策略 | 原因 |
|------|---------|------|
| 开发环境 | 100% 采样 | 便于调试 |
| 生产环境 | 尾部采样 | 准确统计 |
| 高流量 | 头部 10% + 错误 100% | 平衡成本与覆盖 |
| 关键链路 | 按服务采样 | 重点监控 |

---

## 4. 链路传播

### 4.1 W3C Trace Context 标准

```
Header: traceparent
Format: {version}-{trace-id}-{parent-id}-{trace-flags}

示例:
00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01
 │          │                    │         │
 version  trace-id             parent-id  flags
 (2hex)   (32hex)              (16hex)    (2hex)

trace-flags:
01 = sampled (采样)
00 = not sampled (未采样)
```

### 4.2 传播器实现

```go
package propagator

import (
    "context"
    "go.opentelemetry.io/otel"
    "go.opentelemetry.io/otel/propagation"
)

var textMapPropagator = propagation.NewCompositeTextMapPropagator(
    propagation.TraceContext{},
    propagation.Baggage{},
)

// 注入上下文到 HTTP Header
func Inject(ctx context.Context, header *http.Header) {
    textMapPropagator.Inject(ctx, propagation.HeaderCarrier(*header))
}

// 从 HTTP Header 提取上下文
func Extract(ctx context.Context, header http.Header) context.Context {
    return textMapPropagator.Extract(ctx, propagation.HeaderCarrier(header))
}

// 中间件示例
func TracingMiddleware(next http.HandlerFunc) http.HandlerFunc {
    return func(w http.ResponseWriter, r *http.Request) {
        ctx := Extract(r.Context(), r.Header)
        tracer := otel.Tracer("api-gateway")
        
        ctx, span := tracer.Start(ctx, r.URL.Path)
        defer span.End()
        
        span.SetAttributes(
            attribute.String("http.method", r.Method),
            attribute.String("http.target", r.URL.Path),
            attribute.String("http.user_agent", r.UserAgent()),
        )
        
        // 修改请求上下文
        r = r.WithContext(ctx)
        
        next(w, r)
    }
}
```

---

## 5. 性能优化

### 5.1 Collector 架构

```
┌─────────────────────────────────────────────────────────────────┐
│                    Collector 数据流                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Receivers ──▶ Processors ──▶ Exporters                         │
│     │           │                │                              │
│     ▼           ▼                ▼                              │
│  OTLP    Batch Processor    Jaeger                              │
│  Zipkin  Memory Limiter     Prometheus                         │
│  Jaeger  Trace Processor    Loki                               │
│                                                                 │
│  关键优化:                                                     │
│  • Batch 导出: 批量发送减少网络开销                              │
│  • Memory Limiter: 防止内存溢出                                │
│  • Sample Processor: 在导入前采样                              │
│  • Queue: 异步缓冲突发流量                                      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 5.2 资源预算控制

```yaml
# collector-config.yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318

processors:
  batch:
    timeout: 5s
    send_batch_size: 1024
    send_batch_max_size: 2048
  memory_limiter:
    limit_mib: 4096
    spike_limit_mib: 512
  sampling:
    policy:
      total_ratio: 0.1
      per_operation:
        - operation: /api/*
          ratio: 0.05

exporters:
  jaeger:
    endpoint: jaeger:14250
    tls:
      insecure: true

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [memory_limiter, sampling, batch]
      exporters: [jaeger]
```

---

## 6. 故障排查

### 6.1 常见问题诊断

```go
package troubleshooting

import (
    "context"
    "fmt"
    "time"
)

// 追踪断链诊断
func DiagnoseTraceBreak(ctx context.Context, traceID string) []string {
    var issues []string
    
    // 检查 TraceID 格式
    if !isValidTraceID(traceID) {
        issues = append(issues, "Invalid TraceID format")
    }
    
    // 检查传播头
    headers := extractHeaders(ctx)
    if _, ok := headers["traceparent"]; !ok {
        issues = append(issues, "Missing traceparent header")
    }
    
    // 检查时间戳连续性
    spans := fetchSpans(traceID)
    for i := 1; i < len(spans); i++ {
        if spans[i].StartTime < spans[i-1].StartTime {
            issues = append(issues, fmt.Sprintf(
                "Timeline inconsistency at span %d", i))
        }
    }
    
    return issues
}

// 延迟分析
func AnalyzeLatency(traceID string) LatencyAnalysis {
    spans := fetchSpans(traceID)
    
    analysis := LatencyAnalysis{
        TotalDuration: spans[0].EndTime - spans[0].StartTime,
        SelfTime:      make(map[string]time.Duration),
        Bottlenecks:   []string{},
    }
    
    // 计算每个操作的 Self Time (排除子调用)
    for _, span := range spans {
        childDuration := sumChildDuration(span)
        analysis.SelfTime[span.Operation] = span.Duration - childDuration
    }
    
    // 识别瓶颈
    for op, selfTime := range analysis.SelfTime {
        if selfTime > analysis.TotalDuration*0.3 {
            analysis.Bottlenecks = append(analysis.Bottlenecks, op)
        }
    }
    
    return analysis
}
```

---

## 7. 生产部署 Checklist

- [ ] 部署 OpenTelemetry Collector（建议 3 节点集群）
- [ ] 配置采样策略（开发 100%，生产 10%+错误全量）
- [ ] 集成 Jaeger/Prometheus 作为后端存储
- [ ] 设置告警规则（错误率、P99 延迟）
- [ ] 配置日志与追踪关联（TraceID 注入日志）
- [ ] 压测验证 Collector 吞吐量
- [ ] 制定 tracing 接入规范文档

---

**参考**: OpenTelemetry 官方文档、Jaeger 架构设计、Google SRE 手册
