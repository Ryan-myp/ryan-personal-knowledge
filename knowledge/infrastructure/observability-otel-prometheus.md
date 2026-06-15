# 可观测性：OpenTelemetry/Prometheus/日志追踪

> 指标采集/分布式追踪/日志聚合/告警规则/性能分析

---

## 第一部分：入门引导（5 分钟速览）

### 为什么需要可观测性？

广告平台系统复杂：
- **分布式**：多个微服务协作
- **高并发**：百万级 QPS
- **实时性**：竞价延迟 < 100ms
- **可靠性**：99.99% 可用性

### 可观测性三支柱

```
Metrics（指标） → Prometheus + Grafana
Traces（追踪） → Jaeger/Tempo + OpenTelemetry
Logs（日志） → Loki/ELK
```

---

## 第二部分：OpenTelemetry 集成

### 2.1 手动埋点

```go
package observability

import (
    "context"
    "go.opentelemetry.io/otel"
    "go.opentelemetry.io/otel/attribute"
    "go.opentelemetry.io/otel/codes"
    "go.opentelemetry.io/otel/trace"
)

var tracer = otel.Tracer("bidding-service")

type BidService struct {
    tracer trace.Tracer
}

func (bs *BidService) Bid(ctx context.Context, req *BidRequest) (*BidResponse, error) {
    ctx, span := bs.tracer.Start(ctx, "BidService.Bid")
    defer span.End()
    
    span.SetAttributes(
        attribute.String("user.id", req.UserId),
        attribute.Float64("budget", req.Budget),
        attribute.Int("impressions.count", len(req.Impressions)),
    )
    
    // 1. 验证请求
    span.AddEvent("Validating request")
    if err := bs.validateRequest(req); err != nil {
        span.RecordError(err)
        span.SetStatus(codes.Error, "validation failed")
        return nil, err
    }
    
    // 2. 查询用户画像
    span.AddEvent("Fetching user profile")
    profile, err := bs.getUserProfile(ctx, req.UserId)
    if err != nil {
        span.RecordError(err)
        return nil, err
    }
    
    // 3. 执行竞价
    span.AddEvent("Executing bidding")
    result, err := bs.executeBid(ctx, req, profile)
    if err != nil {
        span.RecordError(err)
        span.SetStatus(codes.Error, "bid execution failed")
        return nil, err
    }
    
    // 4. 记录结果
    span.SetAttributes(
        attribute.Bool("win", result.Win),
        attribute.Float64("price", result.Price),
    )
    
    return result, nil
}

func (bs *BidService) getUserProfile(ctx context.Context, userId string) (*UserProfile, error) {
    _, span := bs.tracer.Start(ctx, "BidService.GetUserProfile")
    defer span.End()
    
    span.SetAttributes(attribute.String("user.id", userId))
    
    // 查询 Redis
    profile, err := bs.redis.Get(ctx, "user:"+userId)
    if err != nil {
        span.RecordError(err)
        return nil, err
    }
    
    return profile, nil
}
```

### 2.2 自定义指标

```go
import (
    "github.com/prometheus/client_golang/prometheus"
    "github.com/prometheus/client_golang/prometheus/promauto"
)

var (
    bidLatency = promauto.NewHistogramVec(
        prometheus.HistogramOpts{
            Name:    "bid_latency_ms",
            Help:    "Bid latency in milliseconds",
            Buckets: prometheus.ExponentialBuckets(1, 2, 15),
        },
        []string{"status"},
    )
    
    bidCount = promauto.NewCounterVec(
        prometheus.CounterOpts{
            Name: "bid_total",
            Help: "Total number of bids",
        },
        []string{"status"},
    )
    
    activeConnections = promauto.NewGauge(
        prometheus.GaugeOpts{
            Name: "active_connections",
            Help: "Number of active connections",
        },
    )
)

// 在竞价完成后记录指标
func recordMetrics(status string, latency float64) {
    bidLatency.WithLabelValues(status).Observe(latency)
    bidCount.WithLabelValues(status).Inc()
}
```

---

## 第三部分：分布式追踪

### 3.1 追踪上下文传递

```go
type TraceContext struct {
    TraceID   string
    SpanID    string
    ParentID  string
    Sampled   bool
}

func (tc *TraceContext) Inject(headers map[string]string) {
    headers["X-Trace-ID"] = tc.TraceID
    headers["X-Span-ID"] = tc.SpanID
    headers["X-Parent-ID"] = tc.ParentID
    headers["X-Sampled"] = fmt.Sprintf("%t", tc.Sampled)
}

func (tc *TraceContext) Extract(headers map[string]string) *TraceContext {
    return &TraceContext{
        TraceID:  headers["X-Trace-ID"],
        SpanID:   headers["X-Span-ID"],
        ParentID: headers["X-Parent-ID"],
        Sampled:  headers["X-Sampled"] == "true",
    }
}

// HTTP 中间件：提取和注入追踪上下文
func TraceMiddleware(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        ctx := r.Context()
        
        // 提取追踪上下文
        traceCtx := &TraceContext{}
        traceCtx.Extract(r.Header)
        
        // 创建 span
        if traceCtx.TraceID == "" {
            traceCtx.TraceID = generateTraceID()
            traceCtx.SpanID = generateSpanID()
            traceCtx.Sampled = true
        } else {
            traceCtx.SpanID = generateSpanID()
        }
        
        // 注入到上下文中
        ctx = context.WithValue(ctx, "traceContext", traceCtx)
        
        // 注入到响应头
        traceCtx.Inject(make(map[string]string))
        
        next.ServeHTTP(w, r.WithContext(ctx))
    })
}
```

### 3.2 Jaeger 集成

```go
import (
    "github.com/jaegertracing/jaeger-client-go/config"
    "github.com/jaegertracing/jaeger-client-go/reporter"
)

func InitJaeger(serviceName string) (*tracer.Tracer, io.Closer) {
    cfg := &config.Configuration{
        ServiceName: serviceName,
        Sampler: &config.SamplerConfig{
            Type:  "const",
            Param: 1,
        },
        Reporter: &config.ReporterConfig{
            LogSpans:           true,
            LocalAgentHostPort: "localhost:6831",
        },
    }
    
    tracer, closer, err := cfg.NewTracer(
        config.Logger(jaeger.StdLogger),
    )
    if err != nil {
        panic(fmt.Sprintf("Cannot initialize Jaeger: %v", err))
    }
    
    return tracer, closer
}
```

---

## 第四部分：日志聚合

### 4.1 结构化日志

```go
import (
    "go.uber.org/zap"
)

type Logger struct {
    logger *zap.Logger
}

func NewLogger() *Logger {
    logger, _ := zap.NewProduction()
    return &Logger{logger: logger}
}

func (l *Logger) Info(msg string, fields ...zap.Field) {
    l.logger.Info(msg, fields...)
}

func (l *Logger) Error(msg string, fields ...zap.Field) {
    l.logger.Error(msg, fields...)
}

// 使用示例
func (bs *BidService) Bid(ctx context.Context, req *BidRequest) (*BidResponse, error) {
    logger.Info("Processing bid request",
        zap.String("request_id", req.RequestId),
        zap.String("user_id", req.UserId),
        zap.Float64("budget", req.Budget),
    )
    
    // 业务逻辑...
    
    logger.Info("Bid processed",
        zap.String("request_id", req.RequestId),
        zap.Bool("win", result.Win),
        zap.Float64("price", result.Price),
        zap.Duration("latency", time.Since(startTime)),
    )
    
    return result, nil
}
```

### 4.2 告警规则

```yaml
groups:
  - name: bidding-alerts
    rules:
      - alert: HighBidLatency
        expr: histogram_quantile(0.99, rate(bid_latency_ms_bucket[5m])) > 100
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High bid latency detected"
          description: "99th percentile bid latency is {{ $value }}ms"
      
      - alert: HighErrorRate
        expr: rate(bid_total{status="error"}[5m]) / rate(bid_total[5m]) > 0.05
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High error rate detected"
          description: "Error rate is {{ $value | humanizePercentage }}"
      
      - alert: LowThroughput
        expr: rate(bid_total[5m]) < 1000
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Low bid throughput"
          description: "Bid throughput is {{ $value }}/s"
```

---

## 第五部分：自测题

### 问题 1
OpenTelemetry 相比 Jaeger 有什么优势？

<details>
<summary>查看答案</summary>

1. **厂商中立**：不绑定特定后端
2. **统一 API**：Metrics + Traces + Logs 统一
3. **自动插桩**：支持自动 instrumentation
4. **社区支持**：CNCF 项目，生态丰富
5. **Go 实现**：使用 otel-go SDK

</details>

### 问题 2
分布式追踪中 TraceID 和 SpanID 有什么区别？

<details>
<summary>查看答案</summary>

1. **TraceID**：标识整个请求链路
2. **SpanID**：标识链路中的一个操作
3. **ParentID**：标识父 Span
4. **传递**：通过 HTTP Header 传递
5. **采样**：并非所有请求都采样

</details>

### 问题 3
Prometheus 的 Histogram 和 Counter 有什么区别？

<details>
<summary>查看答案</summary>

1. **Counter**：单调递增计数器（如总请求数）
2. **Histogram**：分桶统计（如延迟分布）
3. **Histogram 优势**：可以计算百分位数
4. **Counter 优势**：简单高效，适合累计统计
5. **Go 实现**：prometheus.NewCounterVec/NewHistogramVec

</details>

---

*本文档基于可观测性原理整理。*