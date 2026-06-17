# 可观测性三件套深度：Prometheus/OTel/Grafana 源码级

> 逐行分析 OTel Collector/Go SDK、Prometheus TSDB、Grafana 查询引擎，理解广告系统可观测性全链路

---

## 第一部分：OpenTelemetry 架构源码深度

### OTel 架构总览

```
OpenTelemetry 组件：
┌─────────────────────────────────────────────────┐
│                  Application                    │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐      │
│  │  OTel    │  │  OTel    │  │  OTel    │      │
│  │  Tracer  │  │ Meter    │  │ Logger   │      │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘      │
│       │              │             │              │
└───────┼──────────────┼─────────────┼──────────────┘
        │              │             │
        ▼              ▼             ▼
┌─────────────────────────────────────────────────┐
│           OTel Collector (收集器)                │
│                                                  │
│  Pipeline 架构：                                 │
│  Receiver → Processor → Exporter                 │
│                                                  │
│  Receiver:                                       │
│  - OTLP/HTTP, OTLP/gRPC, Jaeger, Zipkin,         │
│    Prometheus, Kafka, File                       │
│                                                  │
│  Processor:                                      │
│  - batch: 批量发送（默认 8192 span, 200ms）       │
│  - resource: 资源属性注入                        │
│  - attributes: 上下文属性注入/过滤               │
│  - filter: 过滤不需要的 span                     │
│  - transform: 使用 CEL 表达式转换 span           │
│  - probabilidad: 概率采样                        │
│                                                  │
│  Exporter:                                       │
│  - otlp: OTLP 格式（推荐，兼容性好）             │
│  - jaeger: Jaeger JSON                          │
│  - prometheus: Prometheus PushGateway            │
│  - logging: 输出到日志                           │
│  - file: 输出到本地文件                          │
└─────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────┐
│              Storage Backend                     │
│  - Prometheus: TSDB                             │
│  - Jaeger: Cassandra/Cassandra/ES                │
│  - Tempo: S3/MinIO（对象存储）                   │
└─────────────────────────────────────────────────┘
```

### OTel Go SDK 源码深度

#### 1. 全局 Tracer 注册

```go
// OTel Go SDK：sdk/trace/provider.go - NewTracerProvider
func NewTracerProvider(opts ...TracerProviderOption) *TracerProvider {
    // 1. 创建默认的 BatchSpanProcessor
    // 批量处理器：攒够 4096 个 span 或 5 秒后 flush
    exporter := &noopExporter{} // 由 ExporterOption 替换
    
    processor := sdktrace.NewBatchSpanProcessor(exporter,
        batch.WithMaxExportBatchSize(4096),
        batch.WithMaxExportTimeout(5*time.Second),
        batch.WithExportInterval(1*time.Second),
    )
    
    // 2. 创建 TracerProvider
    tp := &tracerProvider{
        schemaURL:           "",
        sdkTracerProvider:   &sdkTracerProvider{},
        forceFlush:          func() {},
        shutdown:            processor.Shutdown,
    }
    
    // 3. 应用选项
    for _, opt := range opts {
        tp = opt.apply(tp)
    }
    
    // 4. 注册为全局 Provider（全局单例）
    // 这样其他库可以通过 global.Tracer("xxx") 获取
    sdktrace.SetTracerProvider(tp)
    
    return tp
}
```

**关键点**：
- **BatchSpanProcessor**：攒批发送，减少网络请求
- **全局注册**：`sdktrace.SetTracerProvider(tp)` 让全局 `global.Tracer()` 能获取
- **Shutdown**：需要显式调用 tp.Shutdown() 确保所有 span 被发送

#### 2. Span 创建与传播

```go
// OTel Go SDK：sdk/trace/span.go - startSpan
func (tp *tracerProvider) startSpan(
    ctx context.Context,
    name string,
    opts []trace.SpanStartOption,
) (trace.Span, context.Context) {
    // 1. 创建 SpanConfig
    config := trace.NewSpanStartConfig(opts...)
    
    // 2. 检查采样
    if !tp.sampler.ShouldSample(config) {
        // 采样率 1% → 返回 NoopSpan（不记录）
        return trace.NoopSpan{}, ctx
    }
    
    // 3. 获取 TraceID 和 SpanID
    traceID := config.TraceID
    spanID := config.SpanID
    if traceID == [16]byte{} {
        traceID = randomID() // 16 字节随机数
    }
    if spanID == [8]byte{} {
        spanID = randomID() // 8 字节随机数
    }
    
    // 4. 获取父 Span（如果有）
    parent := trace.SpanFromContext(ctx)
    var parentSpanID trace.SpanID
    if p, ok := parent.(*span); ok {
        parentSpanID = p.spanContext.SpanID()
    }
    
    // 5. 创建 Span 事件
    events := []trace.Event{
        {Name: "span_start", Time: time.Now()},
    }
    
    // 6. 创建 Span 记录
    record := sdktrace.Record{
        Name:       name,
        SpanKind:   config.SpanKind,
        TraceID:    traceID,
        SpanID:     spanID,
        ParentSpan: parentSpanID,
        Events:     events,
        Links:      config.Links,
        Attributes: config.Attributes,
        StartTime:  time.Now(),
        EndTime:    time.Time{}, // 未完成
    }
    
    // 7. 创建 span 对象
    span := &span{
        record: record,
        provider: tp,
        spanContext: trace.NewSpanContext(trace.SpanContextConfig{
            TraceID:    traceID,
            SpanID:     spanID,
            TraceFlags: trace.FlagsSampled,
        }),
    }
    
    // 8. 注入 TraceContext 到 context
    ctx = trace.ContextWithSpan(ctx, span)
    ctx = trace.ContextWithSpanContext(ctx, span.spanContext)
    
    return span, ctx
}
```

**关键点**：
- **TraceContext 传播**：通过 `trace.ContextWithSpan` 在 goroutine 间传播
- **采样**：`ShouldSample` 决定是否需要记录这个 span
- **父子关系**：通过 `ParentSpanID` 建立调用链

#### 3. 采样策略源码

```go
// OTel Go SDK：sdk/trace/provider.go - defaultSampler
var defaultSampler = parentBased(
    trace.TraceIDRatioBased(0.01), // 根 span 采样率 1%
)

type parentBased struct {
    root          trace.Sampler
    remoteParent  trace.Sampler
    remoteParentSampled  trace.Sampler
    remoteParentNotSampled trace.Sampler
    localParentSampled  trace.Sampler
    localParentNotSampled trace.Sampler
}

// ShouldSample 决策逻辑
func (p *parentBased) ShouldSample(params trace.SamplingParameters) trace.SamplingResult {
    // 1. 检查是否有父 span
    if !params.ParentSpanContext.IsValid() {
        // 无父 span → 使用 root 采样器（1%）
        return p.root.ShouldSample(params)
    }
    
    // 2. 父 span 是否被采样
    if params.ParentSpanContext.IsSampled() {
        // 父 span 已采样 → 子 span 100% 采样（关键！）
        return trace.SamplingResult{
            Decision: trace.RecordAndSample,
            Tracestate: params.ParentSpanContext.TraceState(),
        }
    }
    
    // 3. 父 span 未采样 → 子 span 不采样
    return trace.SamplingResult{
        Decision: trace.Drop,
    }
}
```

**关键点**：
- **ParentBased(Root(1%))**：根 span 1% 采样，但子 span 跟随父 span
- **为什么这样设计**：如果根 span 被采样，其所有子 span 必须一起采样，否则链路断裂
- **广告平台建议**：生产用 `Root(10%)` 或 `AlwaysOn()`（有 OTel Collector 批量）

---

### OTel Collector Pipeline 源码

```yaml
# OTel Collector 配置：otel-collector-config.yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318

processors:
  batch:
    timeout: 1s           # 1 秒或 8192 span 后 flush
    send_batch_max_size: 8192
  memory_limiter:
    check_interval: 1s
    limit_mib: 4096       # 内存限制 4GB
    spike_limit_mib: 512

exporters:
  otlp:
    endpoint: tempo:4317
    tls:
      insecure: true
  prometheus:
    endpoint: 0.0.0.0:8889
    const_labels:
      cluster: ad-platform

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [batch]
      exporters: [otlp]
    metrics:
      receivers: [otlp]
      processors: [batch]
      exporters: [prometheus]
    logs:
      receivers: [otlp]
      processors: [batch]
      exporters: [logging]
```

### OTel Collector 发送队列源码

```go
// OTel Collector：exporter/exporterhelper/queued_retry.go
// sending_queue — 发送失败时的队列

type QueuedRetryExporter struct {
    baseExporter    *baseExporter
    sendingQueue    *internal.SendingQueue
    retryConfig     *RetryConfig
}

// Send 发送 Span/Metric
func (q *QueuedRetryExporter) Send(ctx context.Context, data pdata.Traces) error {
    // 1. 尝试直接发送
    err := q.baseExporter.Export(ctx, data)
    
    // 2. 发送失败 → 加入队列
    if err != nil {
        // 2.1 检查队列是否满
        if q.sendingQueue.IsFull() {
            // 队列满：丢弃最旧的 span
            q.metrics.droppedSpans.Inc(ctx, int64(data.SpanCount()))
            return err
        }
        
        // 2.2 加入队列
        q.sendingQueue.AddItem(data)
        
        // 2.3 异步发送（不阻塞调用者）
        go q.sendQueue()
    }
    
    return nil
}

// sendQueue 后台发送
func (q *QueuedRetryExporter) sendQueue() {
    for {
        // 1. 从队列取出数据
        data, ok := q.sendingQueue.TryConsume()
        if !ok {
            time.Sleep(q.retryConfig.Delay) // 等待后重试
            continue
        }
        
        // 2. 指数退避重试
        for attempt := 0; attempt < q.retryConfig.MaxAttempts; attempt++ {
            err := q.baseExporter.Export(context.Background(), data)
            if err == nil {
                break // 成功
            }
            
            // 指数退避：1s, 2s, 4s, 8s, ...
            time.Sleep(time.Duration(1<<attempt) * time.Second)
        }
    }
}
```

**关键点**：
- **sending_queue**：发送失败时自动排队，最多可存 8192 个 batch
- **指数退避**：1s → 2s → 4s → 8s → 16s
- **内存限制**：`memory_limiter` 防止 OOM

---

## 第二部分：Prometheus TSDB 源码深度

### Prometheus 架构

```
Prometheus 架构：
┌─────────────────────────────────────────────────┐
│              Prometheus Server                    │
│                                                  │
│  ┌────────────────────────────────────────────┐  │
│  │           TSDB (Time Series Database)       │  │
│  │                                            │  │
│  │  Head Block：                              │  │
│  │  - 当前写入的活跃时间序列                     │  │
│  │  - WAL (Write-Ahead Log)                   │  │
│  │  - 默认 2 小时 compact 成 block             │  │
│  │                                            │  │
│  │  永久 Block：                              │  │
│  │  - 压缩后的块文件                            │  │
│  │  - 默认保存 15 天                            │  │
│  │  - 可配置 retention                          │  │
│  │                                            │  │
│  │  TSDB 存储格式：                              │  │
│  │  ┌──────────────┐ ┌──────────────┐         │  │
│  │  │  series.json │ │  chunks/     │         │  │
│  │  │  meta.json   │ │  00000001    │         │  │
│  │  │  index       │ │  00000002    │         │  │
│  │  └──────────────┘ │  ...         │         │  │
│  └────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────┘
```

### TSDB 存储结构

```
TSDB 文件结构：
blocks/<timestamp>-<hash>/
├── meta.json          # 元数据（start, end, min/max time）
├── index              # 索引（Series ID → Chunk Location）
├── chunks/            # 压缩后的数据块
│   ├── 000001
│   └── 000002
└── tombstones         # 删除标记

Series 存储：
┌─────────────────────────────────────────────────┐
│ Series: {job="api", handler="/bid"}             │
│   ID: 1001                                       │
│   Labels: [{name:"job",value:"api"},             │
│           {name:"handler",value:"/bid"}]        │
│   Chunks:                                        │
│     Chunk #1: [t=0, v=1.2], [t=2, v=1.5], ...  │
│     Chunk #2: [t=60, v=1.3], [t=62, v=1.6], ...│
└─────────────────────────────────────────────────┘

Chunk 编码：
┌─────────────────────────────────────────────────┐
│ 使用 CHUNK_ENC_V1 (Delta encoding):             │
│   时间戳: 差分编码（相对于上一个）                │
│   值:     差分编码（相对于上一个）                │
└─────────────────────────────────────────────────┘
```

### 源码逐行解析：Head Appender

```go
// Prometheus 源码：tsdb/head.go - Head.Appender
// 追加数据到 Head Block

type Head struct {
    series     *memSeriesMap      // 内存 Series 缓存
    chunks     []*memChunk        // 内存 Chunk 链表
    wal        *wal.WAL           // Write-Ahead Log
    minTime    int64              // 最小时间（毫秒）
    maxTime    int64              // 最大时间（毫秒）
}

type memSeries struct {
    ref        uint64             // Series 引用
    series     *Series            // 元数据
    chunks     []*memChunk        // Chunk 链表
    pending    float64            // 未确认的值
    last       int64              // 最后写入时间
}

type memChunk struct {
    minTime    int64
    maxTime    int64
    samples    []prometheus.Sample // 采样点
    encoding   chunk.Encoding      // 编码类型
}

// Appender 追加一个样本
func (h *Head) Appender() storage.Appender {
    return &headAppender{
        head:  h,
        series: make(map[uint64]*memSeries),
    }
}

func (a *headAppender) Append(ref uint64, lset labels.Labels, ts int64, v float64) (uint64, error) {
    // 1. 查找或创建 Series
    ms, created := a.lookupSeries(lset)
    if created {
        // 1.1 创建新 Chunk
        chunk := newMemChunk(lset, ts, ts)
        ms.chunks = append(ms.chunks, chunk)
    }
    
    // 2. 检查 Chunk 是否已满（默认 2 小时）
    if ms.chunks[len(ms.chunks)-1].maxTime-ts > 2*time.Hour {
        // 2.1 创建新 Chunk
        newChunk := newMemChunk(lset, ts, ts)
        ms.chunks = append(ms.chunks, newChunk)
    }
    
    // 3. 写入 Chunk
    chunk := ms.chunks[len(ms.chunks)-1]
    chunk.samples = append(chunk.samples, prometheus.Sample{
        T: ts,
        V: v,
    })
    chunk.maxTime = ts
    
    // 4. 写入 WAL（Write-Ahead Log）
    a.head.wal.Log(wal.SeriesRecord{
        Ref: ref,
        Labels: lset,
    })
    a.head.wal.Log(wal.SamplesRecord{
        Ref: ref,
        Samples: []prometheus.Sample{{T: ts, V: v}},
    })
    
    return ref, nil
}

// Commit 提交所有写入
func (a *headAppender) Commit() error {
    // 1. 更新 Head Block 的时间范围
    for _, ms := range a.series {
        if len(ms.chunks) > 0 {
            chunk := ms.chunks[len(ms.chunks)-1]
            a.head.maxTime = chunk.maxTime
            a.head.minTime = chunk.minTime
        }
    }
    
    // 2. WAL fsync 确保持久化
    return a.head.wal.Sync()
}
```

**关键点**：
- **Head Block**：内存中的活跃数据，2 小时后 compact 成永久 block
- **WAL 优先**：先写 WAL，再写内存（WAL 崩溃恢复用）
- **Chunk 2 小时**：每 2 小时创建一个新 chunk

---

### TSDB Compact 源码

```go
// Prometheus 源码：tsdb/tsdb.go - compact
// 将 Head Block compact 成永久 Block

func (t *TSDB) compact() error {
    // 1. 检查 Head Block 是否需要 compact
    headMaxTime := t.head.MaxTime()
    if headMaxTime < t.head.MinTime()+2*time.Hour {
        return nil // 未满 2 小时，不 compact
    }
    
    // 2. 创建 Block Writer
    blockWriter := &BlockWriter{
        dir:     t.dir,
        meta: &BlockMeta{
            MinTime: t.head.MinTime(),
            MaxTime: t.head.MaxTime(),
        },
    }
    
    // 3. 写入 Series 元数据
    t.head.Series.Range(func(ref uint64, ms *memSeries) bool {
        blockWriter.WriteSeries(ms.series.Labels, ref)
        return true
    })
    
    // 4. 写入 Chunks
    for _, ms := range t.head.Series.All() {
        for _, chunk := range ms.chunks {
            // 4.1 编码 Chunk（delta encoding）
            encoded := encodeChunk(chunk)
            blockWriter.WriteChunk(encoded)
        }
    }
    
    // 5. 创建 Block 目录
    blockDir := fmt.Sprintf("%08d", blockWriter.Meta.MinTime)
    os.MkdirAll(filepath.Join(t.dir, blockDir), 0755)
    
    // 6. 写入 index 文件
    blockWriter.WriteIndex()
    
    // 7. 写入 meta.json
    blockWriter.WriteMeta()
    
    // 8. 清理旧 Head Block 内存
    t.head.Truncate(t.head.MaxTime())
    
    return nil
}
```

---

## 第三部分：PromQL 查询引擎

### 查询执行流程

```
PromQL 查询：
  sum(rate(http_requests_total{job="api"}[5m])) by (handler)

执行流程：
1. 解析：PromQL → AST（抽象语法树）
2. 范围选择：5m → [t-5m, t]
3. 过滤：{job="api"} → SeriesFilter
4. 聚合：sum by (handler) → Group + Reduce
5. 返回结果
```

### 源码逐行解析：QueryExecutor

```go
// Prometheus 源码：storage/queries/query_engine.go - exec
// 执行 PromQL 查询

func (e *QueryEngine) exec(ctx context.Context, q promql.Query) ([]promql.MatrixValue, error) {
    // 1. 获取查询范围
    start := q.Start()
    end := q.End()
    step := q.Step()
    
    // 2. 解析查询表达式
    expr, err := parser.ParseExpr(q.String())
    if err != nil {
        return nil, err
    }
    
    // 3. 创建 Query
    query := promql.NewQuery(e.storage, e.logger, expr, q.Name(), start, end)
    
    // 4. 执行查询
    result, err := query.Exec(ctx)
    if err != nil {
        return nil, err
    }
    
    // 5. 返回 MatrixValue
    return result.(promql.MatrixValue), nil
}

// MatrixValue 结构：
type MatrixValue []Vector
type Vector []Sample
type Sample struct {
    T int64       // 时间戳
    V float64     // 值
    M Metric      // 指标元数据
}
```

---

## 第四部分：广告系统可观测性实践

### 关键指标体系

```
广告系统监控指标：
┌─────────────────────────────────────────────────┐
│ 业务指标（Business）：                           │
│ - ad_impression_total (计数)                     │
│ - ad_click_total (计数)                         │
│ - ad_conversation_total (计数)                  │
│ - ad_spend_total (gauge)                        │
│ - ad_cpm (histogram)                            │
│ - ad_ctr (histogram)                            │
│                                                 │
│ 系统指标（System）：                             │
│ - go_goroutines (gauge)                         │
│ - go_memstats_alloc_bytes (gauge)               │
│ - http_request_duration_seconds (histogram)      │
│ - grpc_server_handled_total (counter)            │
│                                                 │
│ 广告平台特有：                                   │
│ - bid_latency_seconds (histogram)               │
│ - recall_latency_seconds (histogram)            │
│ - rank_latency_seconds (histogram)              │
│ - rerank_latency_seconds (histogram)            │
│ - mcp_api_duration_seconds (histogram)          │
│ - tabpfn_training_duration_seconds (gauge)      │
│                                                 │
│ 错误指标：                                      │
│ - error_total (counter)                         │
│ - retry_total (counter)                         │
│ - circuit_breaker_open (gauge)                  │
└─────────────────────────────────────────────────┘
```

### Go 应用集成完整代码

```go
package main

import (
    "context"
    "fmt"
    "log"
    "net/http"
    "time"

    "go.opentelemetry.io/otel"
    "go.opentelemetry.io/otel/exporters/otlp/otlpmetric/otlpmetricgrpc"
    "go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracegrpc"
    "go.opentelemetry.io/otel/metric"
    "go.opentelemetry.io/otel/propagation"
    sdkmetric "go.opentelemetry.io/otel/sdk/metric"
    sdktrace "go.opentelemetry.io/otel/sdk/trace"
)

func main() {
    // 1. 创建 OTel 导出器
    ctx := context.Background()
    
    // Trace Exporter
    traceExporter, err := otlptracegrpc.New(ctx)
    if err != nil {
        log.Fatalf("创建 Trace Exporter: %v", err)
    }
    
    // Metric Exporter
    metricExporter, err := otlpmetricgrpc.New(ctx)
    if err != nil {
        log.Fatalf("创建 Metric Exporter: %v", err)
    }
    
    // 2. 创建 TracerProvider
    tp := sdktrace.NewTracerProvider(
        sdktrace.WithBatcher(traceExporter), // BatchSpanProcessor
        sdktrace.WithSampler(sdktrace.ParentBased(sdktrace.TraceIDRatioBased(0.1))), // 10% 采样
    )
    otel.SetTracerProvider(tp)
    
    // 3. 创建 MeterProvider
    mp := sdkmetric.NewMeterProvider(
        sdkmetric.WithReader(sdkmetric.NewPeriodicReader(metricExporter,
            sdkmetric.WithInterval(10*time.Second))), // 10s 推送
    )
    otel.SetMeterProvider(mp)
    
    // 4. 设置 propagator（W3C TraceContext）
    otel.SetTextMapPropagator(propagation.NewCompositeTextMapPropagator(
        propagation.TraceContext{},
        propagation.Baggage{},
    ))
    
    // 5. 定义业务指标
    tracer := otel.Tracer("ad-platform")
    meter := otel.Meter("ad-platform")
    
    // 竞价延迟 Histogram
    bidLatency, _ := meter.Float64Histogram("bid_latency_seconds",
        metric.WithExplicitBucketBoundaries(
            0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0,
        ),
        metric.WithDescription("广告竞价延迟"),
    )
    
    // 曝光计数 Counter
    impressionCount, _ := meter.Int64Counter("ad_impression_total",
        metric.WithDescription("广告曝光次数"),
    )
    
    // 6. HTTP 中间件（自动追踪）
    handler := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        ctx, span := tracer.Start(r.Context(), "BidRequest")
        defer span.End()
        
        // 记录竞价延迟
        start := time.Now()
        
        // 模拟竞价逻辑
        result := doBid(ctx)
        
        latency := time.Since(start).Seconds()
        bidLatency.Record(ctx, latency,
            metric.WithAttributes(attribute.String("platform", "facebook")),
        )
        
        // 记录曝光
        if result.ShouldShow {
            impressionCount.Add(ctx, 1)
        }
        
        w.WriteHeader(http.StatusOK)
        fmt.Fprintf(w, "Bid Result: %+v", result)
    })
    
    // 7. 启动 HTTP 服务
    go func() {
        http.ListenAndServe(":8080", handler)
    }()
    
    // 8. 优雅关闭
    <-ctx.Done()
    tp.Shutdown(ctx)
    mp.Shutdown(ctx)
}
```

### OTel Collector 完整配置（广告平台）

```yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
        max_recv_msg_size_mib: 16
      http:
        endpoint: 0.0.0.0:4318
  prometheus:
    config:
      scrape_configs:
        - job_name: 'prometheus'
          static_configs:
            - targets: ['localhost:9090']
        - job_name: 'node-exporter'
          static_configs:
            - targets: ['localhost:9100']

processors:
  batch:
    timeout: 1s
    send_batch_max_size: 16384
    send_batch_size: 8192
  memory_limiter:
    check_interval: 1s
    limit_mib: 4096
    spike_limit_mib: 512
  attributes:
    actions:
      - key: environment
        value: "production"
        action: upsert
      - key: cluster
        value: "ad-cluster-1"
        action: upsert

exporters:
  otlp/tempo:
    endpoint: tempo:4317
    tls:
      insecure: true
  prometheus:
    endpoint: 0.0.0.0:8889
    const_labels:
      cluster: ad-cluster-1
  logging:
    loglevel: debug

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [batch]
      exporters: [otlp/tempo, logging]
    metrics:
      receivers: [otlp, prometheus]
      processors: [batch]
      exporters: [prometheus]
    logs:
      receivers: [otlp]
      processors: [batch]
      exporters: [logging]
```

---

## 第五部分：Grafana 告警规则

```yaml
# Grafana Alerting Rules
groups:
  - name: ad-platform-alerts
    rules:
      # 竞价延迟 P99 > 1s
      - alert: HighBidLatency
        expr: histogram_quantile(0.99, rate(bid_latency_seconds_bucket[5m])) > 1
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "广告竞价 P99 延迟过高"
          description: "P99 延迟 {{ $value }}s，超过阈值 1s"
      
      # API 错误率 > 1%
      - alert: HighAPIErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m]) > 0.01
        for: 3m
        labels:
          severity: critical
        annotations:
          summary: "API 错误率过高"
      
      # Goroutine 泄漏
      - alert: GoroutineLeak
        expr: go_goroutines > 50000
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Goroutine 数量异常"
      
      # Memory 使用率 > 80%
      - alert: HighMemoryUsage
        expr: go_memstats_alloc_bytes / go_memstats_sys_bytes > 0.8
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "内存使用率过高"
```

---

## 第六部分：自测题

### Q1: OTel 的 BatchSpanProcessor 为什么推荐 8192 batch size？

**A**: 
- 太小：频繁发送，增加网络开销
- 太大：延迟增加，span 堆积
- 8192 是经验值：~500KB 数据（100 bytes × 8192），网络一次 HTTP POST 足够
- 配合 1s timeout，既能批量又能保证实时性

### Q2: Prometheus Histogram 和 Summary 有什么区别？

**A**:
- **Histogram**：客户端计算桶分布，服务端聚合（推荐，性能好）
- **Summary**：客户端计算分位数，服务端直接聚合（内存密集，不推荐）
- 广告平台推荐 Histogram + `histogram_quantile()` 计算分位数

### Q3: OTel Collector 的 sending_queue 什么时候触发？

**A**: 当 exporter 发送失败时触发。默认 8192 batch 容量，使用 FIFO 队列。队列满时丢弃最旧的 batch。配合指数退避重试（1s, 2s, 4s, ...）。

---

## 第七部分：生产排障

### 1. OTel Collector 内存飙升

```bash
# 检查 OTel Collector 内存
kubectl top pod -l app=otel-collector

# 常见原因：
# 1. Batch size 太大 → 减小 send_batch_max_size
# 2. memory_limiter 未配置 → 添加 memory_limiter processor
# 3. Exporter 发送太慢 → 增加 timeout 或并行发送

# 修复：
processors:
  memory_limiter:
    check_interval: 1s
    limit_mib: 4096
    spike_limit_mib: 512
```

### 2. Prometheus 查询慢

```bash
# 查看查询耗时
prometheus -web.enable-admin-api

# 常见问题：
# 1. 范围选择器太大 [30m] → 改为 [5m]
# 2. 聚合维度太多 by (...) → 减少维度
# 3. TSDB 压缩慢 → 增加 storage.tsdb.retention.time

# 调优：
storage:
  tsdb:
    retention.time: 15d
    tsdb.max-block-duration: 2h
    wal-compression: true
```

### 3. Grafana Dashboard 加载慢

```bash
# 常见问题：
# 1. Panel 太多 → 拆分 Dashboard
# 2. 查询范围太大 [30d] → 改为 [6h]
# 3. 数据源太多 → 合并相同数据源

# 优化：
# - 使用 Template Variables 动态选择时间范围
# - 使用 Dashboard Link 跳转子 Dashboard
# - 使用 Variable 过滤目标服务
```
