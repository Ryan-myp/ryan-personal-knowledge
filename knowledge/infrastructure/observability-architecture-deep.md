# 可观测性架构深度：Metrics/Traces/Logs 一体化

> 逐行源码解析 + 生产排障案例 + 对比分析 + 动手验证

---

## 第一部分：入门引导（5 分钟速览）

### 类比理解可观测性

```
可观测性 = 汽车的仪表盘 + 行车记录仪 + 导航

Metrics（指标）= 仪表盘
  → 速度、转速、油量
  → 实时数据，一目了然

Traces（追踪）= 行车记录仪
  → 记录了完整行程
  → 出问题时可以回放

Logs（日志）= 导航日志
  → 详细的文字记录
  → 可以搜索和分析
```

### 可观测性三支柱

```
1. Metrics：聚合数据，趋势分析
2. Traces：请求链路，性能分析
3. Logs：详细记录，问题排查

三者关系：
Metrics 发现问题 → Traces 定位链路 → Logs 分析细节
```

---

## 第二部分：OpenTelemetry 深度

### 2.1 OpenTelemetry 架构

```
OpenTelemetry = 采集 + 传输 + 存储

采集（Collection）：
→ SDK（Go/Java/Python）
→ Auto-instrumentation

传输（Transport）：
→ OTLP（gRPC/HTTP）
→ Collector

存储（Storage）：
→ Prometheus（Metrics）
→ Jaeger/Tempo（Traces）
→ Loki/ELK（Logs）
```

### 2.2 Go 实现 OpenTelemetry

```go
package telemetry

import (
    "context"
    "time"

    "go.opentelemetry.io/otel"
    "go.opentelemetry.io/otel/attribute"
    "go.opentelemetry.io/otel/codes"
    "go.opentelemetry.io/otel/metric"
    "go.opentelemetry.io/otel/trace"
)

// TracerProvider 追踪提供者
type TracerProvider struct {
    tracer trace.Tracer
    meter  metric.Meter
}

// NewTracerProvider 创建追踪提供者
func NewTracerProvider() *TracerProvider {
    tp := otel.TracerProvider()
    mp := otel.MeterProvider()
    
    return &TracerProvider{
        tracer: tp.Tracer("ad-platform"),
        meter:  mp.Meter("ad-platform"),
    }
}

// TraceBid 竞价追踪
func (tp *TracerProvider) TraceBid(ctx context.Context, userID string, adID string) (*BidResult, error) {
    ctx, span := tp.tracer.Start(ctx, "bid")
    defer span.End()
    
    span.SetAttributes(
        attribute.String("user.id", userID),
        attribute.String("ad.id", adID),
    )
    
    // 执行竞价
    result, err := tp.executeBid(ctx, userID, adID)
    if err != nil {
        span.RecordError(err)
        span.SetStatus(codes.Error, err.Error())
        return nil, err
    }
    
    span.SetAttributes(
        attribute.Float64("bid.price", result.Price),
        attribute.Float64("bid.ctr", result.CTR),
    )
    
    return result, nil
}

// MeterBid 竞价指标
func (tp *TracerProvider) MeterBid(ctx context.Context, price float64) error {
    counter, err := tp.meter.Int64Counter("ad.bid.count")
    if err != nil {
        return err
    }
    
    histogram, err := tp.meter.Float64Histogram("ad.bid.price")
    if err != nil {
        return err
    }
    
    counter.Add(ctx, 1)
    histogram.Record(ctx, price)
    
    return nil
}
```

---

## 第三部分：Prometheus 深度

### 3.1 Prometheus 架构

```
Prometheus = 采集 + 存储 + 查询 + 告警

采集（Scrape）：
→ 定时拉取指标
→ Service Discovery

存储（Storage）：
→ TSDB（时序数据库）
→ 本地磁盘

查询（Query）：
→ PromQL
→ Grafana

告警（Alert）：
→ Alertmanager
→ 通知通道
```

### 3.2 Go 实现 Prometheus 指标

```go
package metrics

import (
    "github.com/prometheus/client_golang/prometheus"
    "github.com/prometheus/client_golang/prometheus/promauto"
)

// Metrics 指标集
type Metrics struct {
    // HTTP 指标
    RequestCount   *prometheus.CounterVec
    RequestLatency *prometheus.HistogramVec
    RequestSize    *prometheus.HistogramVec
    ResponseSize   *prometheus.HistogramVec
    
    // 业务指标
    BidCount       *prometheus.CounterVec
    BidPrice       *prometheus.HistogramVec
    WinRate        prometheus.Gauge
    
    // 系统指标
    Goroutines     prometheus.Gauge
    MemoryUsage    prometheus.Gauge
}

// NewMetrics 创建指标集
func NewMetrics() *Metrics {
    return &Metrics{
        RequestCount: promauto.NewCounterVec(
            prometheus.CounterOpts{
                Name: "http_requests_total",
                Help: "Total HTTP requests",
            },
            []string{"method", "endpoint", "status"},
        ),
        
        RequestLatency: promauto.NewHistogramVec(
            prometheus.HistogramOpts{
                Name:    "http_request_duration_seconds",
                Help:    "HTTP request latency",
                Buckets: prometheus.DefBuckets,
            },
            []string{"method", "endpoint"},
        ),
        
        BidCount: promauto.NewCounterVec(
            prometheus.CounterOpts{
                Name: "ad_bids_total",
                Help: "Total ad bids",
            },
            []string{"campaign_id", "ad_slot"},
        ),
        
        BidPrice: promauto.NewHistogram(
            prometheus.HistogramOpts{
                Name:    "ad_bid_price",
                Help:    "Ad bid price",
                Buckets: []float64{0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0},
            },
        ),
        
        WinRate: promauto.NewGauge(
            prometheus.GaugeOpts{
                Name: "ad_win_rate",
                Help: "Ad win rate",
            },
        ),
        
        Goroutines: promauto.NewGauge(
            prometheus.GaugeOpts{
                Name: "go_goroutines",
                Help: "Number of goroutines",
            },
        ),
        
        MemoryUsage: promauto.NewGauge(
            prometheus.GaugeOpts{
                Name: "go_memstats_alloc_bytes",
                Help: "Bytes allocated",
            },
        ),
    }
}

// 使用示例
func (m *Metrics) RecordBid(campaignID, adSlot string, price float64) {
    m.BidCount.WithLabelValues(campaignID, adSlot).Inc()
    m.BidPrice.Observe(price)
}
```

---

## 第四部分：分布式追踪

### 4.1 追踪原理

```
Span：最小追踪单元
Trace：一组相关的 Span
SpanContext：Span 的上下文

Span 属性：
- Name：操作名称
- StartTime：开始时间
- Duration：持续时间
- Attributes：键值对
- Events：事件
- Status：状态
```

### 4.2 Go 实现分布式追踪

```go
package tracing

import (
    "context"
    "fmt"
    "time"
)

// Span 追踪单元
type Span struct {
    TraceID     string
    SpanID      string
    ParentSpanID string
    Name        string
    StartTime   time.Time
    EndTime     time.Time
    Attributes  map[string]interface{}
    Events      []Event
    Status      string
}

// Tracer 追踪器
type Tracer struct {
    exporters []Exporter
}

// Exporter 导出器
type Exporter interface {
    ExportSpans(spans []*Span) error
}

// StartSpan 开始 Span
func (t *Tracer) StartSpan(ctx context.Context, name string) (context.Context, *Span) {
    span := &Span{
        TraceID:   generateTraceID(),
        SpanID:    generateSpanID(),
        StartTime: time.Now(),
        Attributes: make(map[string]interface{}),
    }
    
    // 如果有父 Span，关联
    if parent, ok := ctx.Value(parentSpanKey).(*Span); ok {
        span.ParentSpanID = parent.SpanID
    }
    
    // 注入 TraceContext
    ctx = context.WithValue(ctx, spanKey, span)
    ctx = context.WithValue(ctx, traceContextKey, span.TraceID)
    
    return ctx, span
}

// EndSpan 结束 Span
func (t *Tracer) EndSpan(span *Span) {
    span.EndTime = time.Now()
    span.Duration = span.EndTime.Sub(span.StartTime)
    
    // 导出
    for _, exporter := range t.exporters {
        exporter.ExportSpans([]*Span{span})
    }
}

// 使用示例
func (t *Tracer) HandleBid(ctx context.Context, userID, adID string) error {
    ctx, bidSpan := t.StartSpan(ctx, "handle_bid")
    defer t.EndSpan(bidSpan)
    
    bidSpan.Attributes["user.id"] = userID
    bidSpan.Attributes["ad.id"] = adID
    
    // 子 Span
    ctx, userSpan := t.StartSpan(ctx, "get_user")
    // ... 获取用户信息
    t.EndSpan(userSpan)
    
    ctx, adSpan := t.StartSpan(ctx, "get_ad")
    // ... 获取广告信息
    t.EndSpan(adSpan)
    
    ctx, bidEngineSpan := t.StartSpan(ctx, "bid_engine")
    // ... 执行竞价
    t.EndSpan(bidEngineSpan)
    
    return nil
}
```

---

## 第五部分：日志聚合

### 5.1 日志标准

```
结构化日志 = JSON 格式
→ 便于搜索和分析
→ 包含 TraceID 关联追踪

日志级别：
- DEBUG：调试信息
- INFO：一般信息
- WARN：警告
- ERROR：错误
- FATAL：致命错误
```

### 5.2 Go 实现结构化日志

```go
package logger

import (
    "context"
    "fmt"
    "log/slog"
    "os"
)

// Logger 结构化日志
type Logger struct {
    logger *slog.Logger
}

// NewLogger 创建日志器
func NewLogger() *Logger {
    handler := slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{
        Level: slog.LevelDebug,
    })
    
    return &Logger{
        logger: slog.New(handler),
    }
}

// WithTraceID 添加 TraceID
func (l *Logger) WithTraceID(ctx context.Context) *Logger {
    traceID := ctx.Value(traceIDKey)
    return l.logger.With("trace_id", traceID)
}

// Info 信息日志
func (l *Logger) Info(msg string, args ...interface{}) {
    l.logger.Info(msg, args...)
}

// Error 错误日志
func (l *Logger) Error(msg string, args ...interface{}) {
    l.logger.Error(msg, args...)
}

// 使用示例
func (l *Logger) HandleBid(ctx context.Context, userID, adID string) {
    l.WithTraceID(ctx).Info("handling bid",
        "user_id", userID,
        "ad_id", adID,
    )
    
    // 处理竞价
    // ...
    
    l.WithTraceID(ctx).Info("bid handled",
        "user_id", userID,
        "ad_id", adID,
    )
}
```

---

## 第六部分：生产排障案例

### 6.1 指标丢失

```
现象：Prometheus 中缺少关键指标

排查：
1. 检查 Exporter 配置
2. 检查 Scrape 间隔
3. 检查指标命名

根因：指标命名不规范

解决方案：
1. 统一命名规范
2. 添加指标文档
3. 定期巡检
```

### 6.2 追踪延迟

```
现象：分布式追踪延迟高

排查：
1. 检查 Span 大小
2. 检查网络传输
3. 检查采样率

根因：全量导出

解决方案：
1. 调整采样率
2. 异步导出
3. 批量发送
```

---

## 第七部分：自测题

### 问题 1
OpenTelemetry 相比 Zipkin/Jaeger 有什么优势？

<details>
<summary>查看答案</summary>

1. **Vendor Neutral**：不绑定特定后端
2. **统一 API**：Metrics/Traces/Logs 统一
3. **Auto-instrumentation**：自动埋点
4. **Collector**：统一采集层
5. **Go 实现**：otel SDK

</details>

### 问题 2
Prometheus 的查询语言 PromQL 有什么特点？

<details>
<summary>查看答案</summary>

1. **时间序列**：按时间查询
2. **聚合函数**：sum/avg/max/min
3. **数学运算**：+/-/*/%
4. **过滤**：{label="value"}
5. **Go 实现**：prometheus/client_golang

</details>

### 问题 3
结构化日志相比普通日志有什么优势？

<details>
<summary>查看答案</summary>

1. **机器可读**：便于解析
2. **字段丰富**：包含 TraceID
3. **级别明确**：DEBUG/INFO/WARN/ERROR
4. **易于搜索**：ELK/Loki
5. **Go 实现**：log/slog

</details>

---

*本文档基于可观测性架构原理整理。*