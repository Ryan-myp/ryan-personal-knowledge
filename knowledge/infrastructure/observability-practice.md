# 可观测性实战：OpenTelemetry/Prometheus/Grafana

> 全链路追踪/指标采集/日志聚合/告警规则/性能分析

---

## 第一部分：入门引导（5 分钟速览）

### 可观测性三支柱

```
Metrics（指标） → Prometheus + Grafana
Traces（追踪） → OpenTelemetry + Jaeger
Logs（日志） → Loki/ELK + Fluentd
```

---

## 第二部分：OpenTelemetry 集成

### 2.1 Go 集成 OpenTelemetry

```go
package observability

import (
    "context"
    "go.opentelemetry.io/otel"
    "go.opentelemetry.io/otel/attribute"
    "go.opentelemetry.io/otel/codes"
    "go.opentelemetry.io/otel/exporters/otlp/otlptrace"
    "go.opentelemetry.io/otel/sdk/resource"
    sdktrace "go.opentelemetry.io/otel/sdk/trace"
    semconv "go.opentelemetry.io/otel/semconv/v1.21.0"
)

func InitTracer(ctx context.Context) (*sdktrace.TracerProvider, error) {
    // 创建 OTLP exporter
    exporter, err := otlptrace.New(ctx, otlptrace.WithEndpoint("jaeger:4317"))
    if err != nil {
        return nil, err
    }
    
    // 创建 TracerProvider
    tp := sdktrace.NewTracerProvider(
        sdktrace.WithBatcher(exporter),
        sdktrace.WithResource(resource.NewWithAttributes(
            semconv.SchemaURL,
            semconv.ServiceNameKey.String("bidding-service"),
            semconv.DeploymentEnvironmentKey.String("production"),
        )),
        sdktrace.WithSampler(sdktrace.AlwaysSample()),
    )
    
    // 设置全局 TracerProvider
    otel.SetTracerProvider(tp)
    
    return tp, nil
}

// 在竞价服务中创建 span
func (s *BidService) Bid(ctx context.Context, req *BidRequest) (*BidResponse, error) {
    tracer := otel.Tracer("bidding-service")
    
    ctx, span := tracer.Start(ctx, "BidService.Bid")
    defer span.End()
    
    span.SetAttributes(
        attribute.String("user.id", req.UserID),
        attribute.Float64("budget", req.Budget),
        attribute.Int("impressions", len(req.Impressions)),
    )
    
    // 1. 验证请求
    span.AddEvent("Validating request")
    if err := s.validateRequest(req); err != nil {
        span.RecordError(err)
        span.SetStatus(codes.Error, "validation failed")
        return nil, err
    }
    
    // 2. 查询用户画像
    span.AddEvent("Fetching user profile")
    profile, err := s.getUserProfile(ctx, req.UserID)
    if err != nil {
        span.RecordError(err)
        return nil, err
    }
    
    // 3. 执行竞价
    span.AddEvent("Executing bid")
    result, err := s.executeBid(ctx, req, profile)
    if err != nil {
        span.RecordError(err)
        span.SetStatus(codes.Error, "bid failed")
        return nil, err
    }
    
    // 4. 记录结果
    span.SetAttributes(
        attribute.Bool("win", result.Win),
        attribute.Float64("price", result.Price),
    )
    
    return result, nil
}
```

### 2.2 HTTP 中间件自动追踪

```go
// HTTP 中间件自动创建 span
func TraceMiddleware(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        tracer := otel.Tracer("http-middleware")
        
        ctx, span := tracer.Start(r.Context(), r.Method+" "+r.URL.Path)
        defer span.End()
        
        span.SetAttributes(
            attribute.String("http.method", r.Method),
            attribute.String("http.url", r.URL.Path),
            attribute.String("http.client_ip", r.RemoteAddr),
        )
        
        // 包装 ResponseWriter 以捕获状态码
        rw := &responseWriter{ResponseWriter: w, statusCode: 200}
        
        next.ServeHTTP(rw, r.WithContext(ctx))
        
        span.SetAttributes(
            attribute.Int("http.status_code", rw.statusCode),
        )
        
        if rw.statusCode >= 500 {
            span.SetStatus(codes.Error, "server error")
        }
    })
}

type responseWriter struct {
    http.ResponseWriter
    statusCode int
}

func (rw *responseWriter) WriteHeader(code int) {
    rw.statusCode = code
    rw.ResponseWriter.WriteHeader(code)
}
```

---

## 第三部分：Prometheus 指标

### 3.1 自定义指标

```go
import (
    "github.com/prometheus/client_golang/prometheus"
    "github.com/prometheus/client_golang/prometheus/promauto"
)

var (
    // 竞价延迟直方图
    bidLatency = promauto.NewHistogramVec(
        prometheus.HistogramOpts{
            Name:    "bid_latency_ms",
            Help:    "Bid latency in milliseconds",
            Buckets: prometheus.ExponentialBuckets(1, 2, 15),
        },
        []string{"status", "dsp"},
    )
    
    // 竞价计数器
    bidCount = promauto.NewCounterVec(
        prometheus.CounterOpts{
            Name: "bid_total",
            Help: "Total number of bids",
        },
        []string{"status", "dsp"},
    )
    
    // 活跃连接数
    activeConnections = promauto.NewGauge(
        prometheus.GaugeOpts{
            Name: "active_connections",
            Help: "Number of active connections",
        },
    )
    
    // 预算消耗速率
    budgetSpendRate = promauto.NewGaugeVec(
        prometheus.GaugeOpts{
            Name: "budget_spend_rate",
            Help: "Budget spend rate per second",
        },
        []string{"campaign_id"},
    )
)

// 在竞价完成后记录指标
func recordBidMetrics(status string, dsp string, latency float64) {
    bidLatency.WithLabelValues(status, dsp).Observe(latency)
    bidCount.WithLabelValues(status, dsp).Inc()
}
```

### 3.2 Prometheus 查询

```promql
# 竞价 P99 延迟
histogram_quantile(0.99, rate(bid_latency_ms_bucket[5m]))

# 各 DSP 竞价成功率
sum(rate(bid_total{status="success"}[5m])) by (dsp) 
/ sum(rate(bid_total[5m])) by (dsp)

# 预算消耗速率
sum(rate(budget_spend_rate[1h])) by (campaign_id)

# 错误率
sum(rate(http_requests_total{status=~"5.."}[5m])) 
/ sum(rate(http_requests_total[5m]))

# QPS
sum(rate(http_requests_total[5m]))
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
    config := zap.NewProductionConfig()
    config.EncoderConfig.TimeKey = "timestamp"
    config.EncoderConfig.EncodeTime = zapcore.ISO8601TimeEncoder
    
    logger, _ := config.Build()
    return &Logger{logger: logger}
}

func (l *Logger) Info(msg string, fields ...zap.Field) {
    l.logger.Info(msg, fields...)
}

func (l *Logger) Error(msg string, fields ...zap.Field) {
    l.logger.Error(msg, fields...)
}

// 使用示例
l.Info("Bid processed",
    zap.String("request_id", req.RequestID),
    zap.String("user_id", req.UserID),
    zap.Float64("price", result.Price),
    zap.Duration("latency", time.Since(startTime)),
)
```

### 4.2 Loki 日志查询

```lucene
# 查询竞价错误日志
{app="bidding-service"} |= "error"

# 查询特定请求的日志
{app="bidding-service"} |= "request_id=abc123"

# 查询高延迟请求
{app="bidding-service"} |= "latency" |~ "100ms"
```

---

## 第五部分：告警规则

### 5.1 Prometheus 告警

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
          summary: "竞价延迟 P99 > 100ms"
      
      - alert: HighErrorRate
        expr: |
          sum(rate(http_requests_total{status=~"5.."}[5m])) 
          / sum(rate(http_requests_total[5m])) > 0.05
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "错误率 > 5%"
      
      - alert: LowQPS
        expr: sum(rate(http_requests_total[5m])) < 1000
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "QPS < 1000"
```

---

## 第六部分：自测题

### 问题 1
OpenTelemetry 相比 Jaeger 有什么优势？

<details>
<summary>查看答案</summary>

1. **厂商中立**：不绑定特定后端
2. **统一 API**：Metrics + Traces + Logs
3. **自动插桩**：支持自动 instrumentation
4. **社区支持**：CNCF 项目
5. **Go 实现**：otel-go SDK

</details>

### 问题 2
Prometheus Histogram 和 Summary 有什么区别？

<details>
<summary>查看答案</summary>

1. **Histogram**：服务端计算分位数
2. **Summary**：客户端计算分位数
3. **Histogram 优势**：可以聚合
4. **Summary 优势**：更精确
5. **广告场景**：竞价延迟用 Histogram

</details>

### 问题 3
结构化日志相比普通日志有什么优势？

<details>
<summary>查看答案</summary>

1. **机器可读**：便于解析
2. **字段查询**：按字段过滤
3. **性能分析**：关联 trace ID
4. **工具支持**：Loki/ELK 友好
5. **Go 实现**：zap/logger

</details>

---

*本文档基于可观测性原理整理。*