# 微服务分布式追踪与链路追踪深度实战

> **来源**：OpenTelemetry 官方文档 + Jaeger 源码解析 + 生产实践
> **创建日期**：2026-07-10
> **深度等级**：🟢深（源码级）

---

## 一、入门引导：为什么微服务需要分布式追踪？

### 1.1 类比：快递追踪系统

想象你寄了一个快递：
- **传统单体应用** = 自己在家打包发货，你知道每一步
- **微服务架构** = 快递经过分拣中心A → 分拣中心B → 配送员C → 客户D
- **分布式追踪** = 快递单号，贯穿整个物流链路

每个分拣中心只知道自己的环节，不知道全局。分布式追踪就是那个"快递单号"——给每个请求分配唯一ID，跨服务传递，最终拼出完整调用链。

### 1.2 微服务监控的三个维度

| 维度 | 工具 | 解决的问题 |
|------|------|-----------|
| **指标监控** | Prometheus/Grafana | "系统整体健康吗？" |
| **日志聚合** | ELK/Loki | "某个时间点发生了什么？" |
| **分布式追踪** | Jaeger/Tempo | "一个请求经过了哪些服务？在哪慢的？" |

三者互补，缺一不可。但**分布式追踪是唯一能回答"端到端延迟分布"的工具**。

### 1.3 核心概念体系

```
Trace（追踪）
├── Span（跨度）— 一次操作的时间段
│   ├── TraceId — 整个请求的唯一ID
│   ├── SpanId — 当前操作的唯一ID
│   ├── ParentSpanId — 父操作的ID
│   ├── OperationName — 操作名称（如 HTTP GET /api/users）
│   ├── Timestamp — 开始时间
│   ├── Duration — 持续时间
│   ├── Tags — 键值对标签（HTTP status, DB table）
│   └── Logs — 事件日志（error, timeout）
└── SpanContext — 跨进程传播的上下文
    ├── TraceId
    └── SpanId
```

**传播机制**：TraceId 和 SpanId 通过 HTTP Header、gRPC Metadata、消息队列 Header 跨服务传递。

---

## 二、OpenTelemetry 原理与 Go 实现

### 2.1 OpenTelemetry 架构

```
┌─────────────────────────────────────────────────────┐
│                   Application                        │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐          │
│  │ HTTP SDK │  │ gRPC SDK │  │ DB SDK   │          │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘          │
│       └──────────────┼─────────────┘                │
│              ┌───────▼───────┐                       │
│              │  TracerProvider│                       │
│              │  (SDK Core)    │                       │
│              └───────┬───────┘                       │
│                      │                              │
│         ┌────────────┼────────────┐                 │
│         ▼            ▼            ▼                 │
│   OTLP Exporter  Zipkin Exporter  Jaeger Exporter   │
└─────────────────────────────────────────────────────┘
```

OpenTelemetry 的核心设计原则：**API 与 SDK 分离**。
- **API**：定义接口，不依赖具体实现
- **SDK**：实现接口，负责采样、缓冲、导出
- **Exporter**：将数据发送到后端（Jaeger/Zipkin/Prometheus）

### 2.2 Go 语言实现：完整可运行代码

```go
package tracing

import (
	"context"
	"fmt"
	"net/http"
	"time"

	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/codes"
	"go.opentelemetry.io/otel/exporters/otlp/otlptrace"
	"go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracegrpc"
	"go.opentelemetry.io/otel/propagation"
	"go.opentelemetry.io/otel/sdk/resource"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
	semconv "go.opentelemetry.io/otel/semconv/v1.26.0"
	"go.opentelemetry.io/otel/trace"
)

// TracerProviderConfig 追踪提供者配置
type TracerProviderConfig struct {
	ServiceName    string
	ServiceVersion string
	Endpoint       string // OTLP endpoint, e.g., "localhost:4317"
	Sampler        string // "always_on", "always_off", "parentbased_traceidratio:0.1"
}

// SetupTracerProvider 初始化 OpenTelemetry TracerProvider
func SetupTracerProvider(ctx context.Context, cfg TracerProviderConfig) (*sdktrace.TracerProvider, error) {
	// 1. 配置采样器
	var sampler sdktrace.Sampler
	switch cfg.Sampler {
	case "always_off":
		sampler = sdktrace.NeverSample()
	case "parentbased_traceidratio":
		sampler = sdktrace.ParentBased(sdktrace.TraceIDRatio(0.1))
	default:
		sampler = sdktrace.AlwaysSample()
	}

	// 2. 创建 OTLP Exporter（gRPC 协议）
	exporter, err := otlptrace.New(ctx, otlptracegrpc.NewClient(
		otlptracegrpc.WithInsecure(),
		otlptracegrpc.WithEndpoint(cfg.Endpoint),
	))
	if err != nil {
		return nil, fmt.Errorf("create exporter: %w", err)
	}

	// 3. 创建 Resource（服务元数据）
	res, err := resource.New(ctx,
		resource.WithAttributes(
			semconv.ServiceName(cfg.ServiceName),
			semconv.ServiceVersion(cfg.ServiceVersion),
			semconv.TelemetrySDKName("otel-go"),
		),
		resource.WithFromEnv(),       // OTEL_RESOURCE_ATTRIBUTES
		resource.WithProcess(),        // 进程信息
		resource.WithHost(),           // 主机信息
	)
	if err != nil {
		return nil, fmt.Errorf("create resource: %w", err)
	}

	// 4. 创建 TracerProvider
	tp := sdktrace.NewTracerProvider(
		sdktrace.WithSampler(sampler),
		sdktrace.WithResource(res),
		sdktrace.WithBatcher(exporter,
			sdktrace.WithBatchTimeout(5*time.Second),  // 批量发送间隔
			sdktrace.WithMaxExportBatchSize(512),       // 每批最大 span 数
			sdktrace.WithMaxQueueSize(2048),             // 队列最大缓冲
		),
	)

	// 5. 设置全局 TracerProvider
	otel.SetTracerProvider(tp)

	// 6. 配置 Propagator（上下文传播）
	propagator := propagation.NewCompositeTextMapPropagator(
		propagation.TraceContext{}, // W3C TraceContext
		propagation.Baggage{},      // W3C Baggage
	)
	otel.SetTextMapPropagator(propagator)

	return tp, nil
}

// ShutdownTracerProvider 优雅关闭追踪器
func ShutdownTracerProvider(ctx context.Context, tp *sdktrace.TracerProvider) error {
	return tp.Shutdown(ctx)
}

// CreateHTTPMiddleware 创建 HTTP 中间件，自动注入/提取 SpanContext
func CreateHTTPMiddleware(tracer trace.Tracer) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			// 从 Request Header 提取 SpanContext（父服务传来的）
			ctx := tracer.Start(
				otel.GetTextMapPropagator().Extract(r.Context(), propagation.HeaderCarrier(r.Header)),
				r.URL.Path,
				trace.WithSpanKind(trace.SpanKindServer),
				trace.WithAttributes(
					semconv.HTTPMethod(r.Method),
					semconv.HTTPURL(r.URL.String()),
					semconv.NetPeerIP(r.RemoteAddr),
				),
			)
			defer r.Context().Value(spanKey{}).End()

			// 将 SpanContext 注入 Response Header（下游服务可见）
			otel.GetTextMapPropagator().Inject(ctx, propagation.HeaderCarrier(w.Header()))

			next.ServeHTTP(w, r.WithContext(ctx))
		})
	}
}

// CallDownstreamService 调用下游服务，自动传播 SpanContext
func CallDownstreamService(ctx context.Context, tracer trace.Tracer, url string) ([]byte, error) {
	ctx, span := tracer.Start(ctx, "CallDownstreamService", trace.WithSpanKind(trace.SpanKindClient))
	defer span.End()

	span.SetAttributes(attribute.String("http.url", url))

	req, err := http.NewRequestWithContext(ctx, "GET", url, nil)
	if err != nil {
		span.RecordError(err)
		span.SetStatus(codes.Error, err.Error())
		return nil, err
	}

	// 自动注入 TraceContext Header
	otel.GetTextMapPropagator().Inject(ctx, propagation.HeaderCarrier(req.Header))

	client := &http.Client{Timeout: 5 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		span.RecordError(err)
		span.SetStatus(codes.Error, err.Error())
		return nil, err
	}
	defer resp.Body.Close()

	span.SetAttributes(semconv.HTTPStatusCode(resp.StatusCode))

	if resp.StatusCode >= 400 {
		span.SetStatus(codes.Error, fmt.Sprintf("HTTP %d", resp.StatusCode))
	}

	return nil, nil
}
```

**关键点解析：**

| 组件 | 作用 | 生产配置建议 |
|------|------|-------------|
| `WithBatcher` | 批量发送 Span，减少网络开销 | 超时 5s，批次 512，队列 2048 |
| `WithSampler` | 采样策略，控制数据量 | 生产环境用 `ParentBased(Ratio)` |
| `resource.WithProcess()` | 自动收集 PID、启动时间等 | 必须开启，用于区分同一 Pod 多实例 |
| `propagation.TraceContext` | W3C 标准传播格式 | 必须使用，跨语言兼容 |

### 2.3 采样策略详解

采样是分布式追踪中最关键的决策——全量采样会淹没后端，采样率太低会丢失关键数据。

```go
// 采样策略对比
type SamplerType int

const (
	AlwaysSample      SamplerType = iota  // 全量采样：100%
	NeverSample                           // 不采样：0%
	ParentBasedAlwaysSample               // 根节点全量，子节点跟随
	ParentBasedNeverSample                // 根节点不采，子节点跟随
	TraceIDRatioBased                     // 按 TraceID 哈希均匀采样
	ParentBasedTraceIDRatio               // 根节点按比例，子节点跟随
)

// ParentBasedTraceIDRatio 实现
type ParentBasedSampler struct {
	root             Sampler
	remoteParentSampled  Sampler
	remoteParentNotSampled Sampler
	localParentSampled   Sampler
	localParentNotSampled Sampler
}

// 实际效果示例：
// RootSpan 采样率 10%，但如果是被 ParentSampled 的 Span，则继承父 Span 的采样结果
// 这意味着：如果父 Span 被采样了，所有子 Span 都会被采样（保证链路完整性）
// 如果父 Span 没被采样，子 Span 也不会被采样（节省资源）
```

**采样率选择指南：**

| 环境 | 推荐策略 | 原因 |
|------|---------|------|
| 开发 | AlwaysSample | 方便调试，数据量小 |
| 测试 | ParentBasedTraceIDRatio(0.5) | 一半数据，足够验证 |
| 预发 | ParentBasedTraceIDRatio(0.1) | 10% 采样，观察真实流量 |
| 生产 | ParentBasedTraceIDRatio(0.01) | 1% 采样，仅保留关键链路 |
| 关键路径 | AlwaysSample | 支付/下单等核心链路全量 |

### 2.4 Span 生命周期与内存管理

```go
// Span 内部结构（简化版）
type span struct {
	// 不可变字段
	traceID     trace.TraceID
	spanID      trace.SpanID
	parentSpanID trace.SpanID
	spanKind    trace.SpanKind
	name        string
	
	// 可变字段
	startTime   time.Time
	endTime     time.Time
	attributes  []attribute.KeyValue  // 预分配数组，避免扩容
	events      []sdktrace.Event      // 事件列表
	status      codes.Code
	message     string
	
	// 采样标记
	sampled     bool
	ended       bool
}

// End 方法的关键逻辑
func (s *span) End(options ...trace.SpanEndOption) {
	if s.ended {
		return // 幂等保护
	}
	s.ended = true
	s.endTime = internal.Now()
	
	// 1. 计算 duration
	duration := s.endTime.Sub(s.startTime)
	
	// 2. 检查采样
	if !s.sampled {
		return // 非采样 Span 直接丢弃
	}
	
	// 3. 绑定属性到 Span（采样时才能绑定）
	//    这是为什么 SDK 中 SetAttribute 在非采样 Span 上是 no-op
	
	// 4. 入队等待批量导出
	s.processor.OnEnd(s)
}
```

**性能优化要点：**
1. **Span 创建开销**：约 200ns（含内存分配），高频调用需考虑缓存
2. **属性绑定**：采样前设置的属性会被丢弃，采样后才生效
3. **批量导出**：5s 超时 + 512 条批次，平衡实时性和吞吐量
4. **队列溢出**：队列满时调用 `DropSpan` 回调，可记录告警

---

## 三、生产级微服务链路追踪框架

### 3.1 架构设计

```
┌──────────────────────────────────────────────────────────────┐
│                        Service Layer                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│  │ User Svc │  │ Order Svc│  │ Pay Svc  │  │ Notify Svc│   │
│  │ :8081    │  │ :8082    │  │ :8083    │  │ :8084     │   │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘    │
│       │             │             │             │            │
│       └─────────────┴──────┬──────┴─────────────┘            │
│                            │                                  │
│                    ┌───────▼───────┐                         │
│                    │  Message Queue │                         │
│                    │   (Kafka/RMQ)  │                         │
│                    └───────┬───────┘                         │
│                            │                                  │
│       ┌────────────────────┼────────────────────┐            │
│       ▼                    ▼                    ▼            │
│  ┌──────────┐      ┌──────────┐         ┌──────────┐       │
│  │ Jaeger   │      │ Tempo    │         │ Datadog  │       │
│  │ (gRPC)   │      │ (gRPC)   │         │ (HTTP)   │       │
│  └──────────┘      └──────────┘         └──────────┘       │
└──────────────────────────────────────────────────────────────┘
```

### 3.2 Go 实现：统一追踪中间件

```go
package middleware

import (
	"context"
	"net/http"
	"strconv"
	"strings"
	"time"

	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/codes"
	"go.opentelemetry.io/otel/trace"
)

// OTelMiddleware 统一的 OpenTelemetry HTTP 中间件
type OTelMiddleware struct {
	tracer trace.Tracer
	opts   options
}

type options struct {
	publicPaths   []string       // 跳过追踪的公开路径
	errorStatuses []int          // 标记为错误 HTTP 状态码
	spanNameFmt   func(r *http.Request) string // 自定义 Span 命名
}

func WithPublicPaths(paths []string) func(*OTelMiddleware) {
	return func(m *OTelMiddleware) {
		m.opts.publicPaths = paths
	}
}

func WithErrorStatuses(statuses []int) func(*OTelMiddleware) {
	return func(m *OTelMiddleware) {
		m.opts.errorStatuss = statuses
	}
}

func NewOTelMiddleware(tracer trace.Tracer, setters ...func(*OTelMiddleware)) *OTelMiddleware {
	m := &OTelMiddleware{tracer: tracer}
	for _, s := range setters {
		s(m)
	}
	return m
}

// Handler HTTP 处理器中间件
func (m *OTelMiddleware) Handler(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// 1. 跳过公开路径
		if m.isPublicPath(r.URL.Path) {
			next.ServeHTTP(w, r)
			return
		}

		// 2. 创建 Span
		ctx, span := m.tracer.Start(
			r.Context(),
			m.getSpanName(r),
			trace.WithSpanKind(trace.SpanKindServer),
			trace.WithAttributes(
				attribute.String("http.method", r.Method),
				attribute.String("http.url", r.URL.Path),
				attribute.String("http.scheme", r.URL.Scheme),
				attribute.String("net.peer.ip", r.RemoteAddr),
				attribute.Bool("http.record_request_body", false), // 生产环境不记录 body
			),
		)
		defer span.End()

		// 3. 包装 ResponseWriter 以捕获状态码
		rw := &responseWriter{ResponseWriter: w, statusCode: http.StatusOK}

		// 4. 记录请求开始时间
		start := time.Now()
		
		// 5. 执行业务逻辑
		next.ServeHTTP(rw, r.WithContext(ctx))

		// 6. 记录响应
		duration := time.Since(start)
		span.SetAttributes(
			attribute.Int("http.status_code", rw.statusCode),
			attribute.Float64("http.response.duration_ms", float64(duration.Microseconds())/1000),
		)

		// 7. 判断是否错误
		if m.isErrorStatus(rw.statusCode) {
			span.SetStatus(codes.Error, http.StatusText(rw.statusCode))
		}
	})
}

func (m *OTelMiddleware) isPublicPath(path string) bool {
	for _, p := range m.opts.publicPaths {
		if path == p || strings.HasPrefix(path, p+"/") {
			return true
		}
	}
	return false
}

func (m *OTelMiddleware) isErrorStatus(code int) bool {
	for _, s := range m.opts.errorStatuss {
		if code == s {
			return true
		}
	}
	return code >= 500
}

// responseWriter 包装 http.ResponseWriter 以捕获状态码
type responseWriter struct {
	http.ResponseWriter
	statusCode int
	written    bool
}

func (rw *responseWriter) WriteHeader(code int) {
	if !rw.written {
		rw.statusCode = code
		rw.written = true
		rw.ResponseWriter.WriteHeader(code)
	}
}

func (rw *responseWriter) Write(b []byte) (int, error) {
	if !rw.written {
		rw.written = true
	}
	return rw.ResponseWriter.Write(b)
}
```

### 3.3 gRPC 链路追踪

```go
package grpcmiddleware

import (
	"context"
	"time"

	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/codes"
	"go.opentelemetry.io/otel/trace"
	"google.golang.org/grpc"
	"google.golang.org/grpc/metadata"
)

// ServerInterceptor gRPC 服务端拦截器
func ServerInterceptor(tracer trace.Tracer) grpc.UnaryServerInterceptor {
	return func(ctx context.Context, req interface{}, info *grpc.UnaryServerInfo, handler grpc.UnaryHandler) (interface{}, error) {
		// 1. 从 metadata 提取 SpanContext
		md, _ := metadata.FromIncomingContext(ctx)
		extractedCtx := tracer.Extract(ctx, metadataReaderWriter(md))

		// 2. 创建 Span
		ctx, span := tracer.Start(
			extractedCtx,
			info.FullMethod,
			trace.WithSpanKind(trace.SpanKindServer),
			trace.WithAttributes(
				attribute.String("rpc.system", "grpc"),
				attribute.String("rpc.grpc.status_code", "OK"),
			),
		)
		defer span.End()

		// 3. 执行 handler
		start := time.Now()
		resp, err := handler(ctx, req)
		duration := time.Since(start)

		// 4. 记录结果
		span.SetAttributes(
			attribute.Float64("rpc.duration_ms", float64(duration.Microseconds())/1000),
		)

		if err != nil {
			span.SetStatus(codes.Error, err.Error())
			span.SetAttributes(attribute.String("rpc.grpc.status_code", "ERROR"))
		}

		return resp, err
	}
}

// ClientInterceptor gRPC 客户端拦截器
func ClientInterceptor(tracer trace.Tracer) grpc.UnaryClientInterceptor {
	return func(ctx context.Context, method string, req, resp interface{}, cc *grpc.ClientConn, invoker grpc.UnaryInvoker, opts ...grpc.CallOption) error {
		// 1. 创建 Span
		ctx, span := tracer.Start(
			ctx,
			method,
			trace.WithSpanKind(trace.SpanKindClient),
			trace.WithAttributes(
				attribute.String("rpc.system", "grpc"),
				attribute.String("rpc.method", method),
			),
		)
		defer span.End()

		// 2. 注入 SpanContext 到 metadata
		md := metadata.New(nil)
		tracer.Inject(ctx, metadataWriter(md))
		ctx = metadata.NewOutgoingContext(ctx, md)

		// 3. 执行调用
		start := time.Now()
		err := invoker(ctx, method, req, resp, cc, opts...)
		duration := time.Since(start)

		// 4. 记录结果
		span.SetAttributes(
			attribute.Float64("rpc.duration_ms", float64(duration.Microseconds())/1000),
		)

		if err != nil {
			span.SetStatus(codes.Error, err.Error())
		}

		return err
	}
}

// metadataReaderWriter 实现 propagation.TextMapReader/Writer
type metadataReaderWriter metadata.MD

func (m metadataReaderWriter) Get(key string) string {
	values := m[key]
	if len(values) == 0 {
		return ""
	}
	return values[0]
}

func (m metadataReaderWriter) Keys() []string {
	keys := make([]string, 0, len(m))
	for k := range m {
		keys = append(keys, k)
	}
	return keys
}

func (m metadataReaderWriter) Set(key, value string) {
	m[key] = []string{value}
}
```

### 3.4 数据库追踪

```go
package dbtracing

import (
	"context"
	"strings"
	"time"

	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/codes"
	"go.opentelemetry.io/otel/trace"
	"gorm.io/gorm"
	"gorm.io/gorm/callbacks"
)

// GORMPlugin GORM 插件，自动追踪 SQL 执行
type GORMPlugin struct {
	tracer trace.Tracer
}

func NewGORMPlugin(tracer trace.Tracer) *GORMPlugin {
	return &GORMPlugin{tracer: tracer}
}

// Name 插件名称
func (p *GORMPlugin) Name() string {
	return "otel-tracing"
}

// Initialize GORM 初始化回调
func (p *GORMPlugin) Initialize(db *gorm.DB) error {
	// 覆盖 Query 回调
	oldQuery := db.Callback().Query().Before("gorm:query").Register("otel:query:start", func(tx *gorm.DB) {
		tx.Set("otel:query_start_time", time.Now())
	})
	
	// 替换原有查询回调
	db.Callback().Query().After("gorm:query").Register("otel:query:end", func(tx *gorm.DB) {
		startTime, _ := tx.Get("otel:query_start_time")
		start := startTime.(time.Time)
		duration := time.Since(start)
		
		sql, vars := tx.SQL.String(), tx.SQL.Args()
		normalizedSQL := normalizeSQL(sql, vars)
		
		ctx := tx.Statement.Context
		if ctx == nil {
			ctx = context.Background()
		}
		
		tracer, _ := tx.Get("otel:tracer")
		if tracer == nil {
			return
		}
		
		tr := tracer.(trace.Tracer)
		_, span := tr.Start(ctx, normalizedSQL, trace.WithSpanKind(trace.SpanKindClient))
		span.SetAttributes(
			attribute.String("db.system", "mysql"),
			attribute.String("db.statement", normalizedSQL),
			attribute.Int("db.rows_affected", tx.RowsAffected),
			attribute.Float64("db.duration_ms", float64(duration.Microseconds())/1000),
		)
		
		if tx.Error != nil {
			span.SetStatus(codes.Error, tx.Error.Error())
		}
		span.End()
	})
	
	_ = oldQuery
	return nil
}

// normalizeSQL 将 SQL 参数化，保护敏感数据
func normalizeSQL(sql string, args []interface{}) string {
	// 替换 ? 为占位符
	parts := strings.Split(sql, "?")
	if len(parts) <= 1 {
		return sql
	}
	
	result := parts[0]
	for i, part := range parts[1:] {
		result += "?"
		if i < len(args) {
			// 根据类型做不同脱敏
			switch v := args[i].(type) {
			case string:
				if len(v) > 20 {
					result += v[:10] + "..." + v[len(v)-5:]
				} else {
					result += "[REDACTED]"
				}
			case int, int64, float64:
				result += "[NUM]"
			default:
				result += "[VAL]"
			}
		}
		result += part
	}
	return result
}
```

---

## 四、生产排障案例

### 4.1 案例一：间歇性超时 — 链路断裂

**现象**：用户反馈下单成功率下降 5%，但各服务 CPU/内存正常。

**排查步骤：**

```bash
# 1. 在 Jaeger UI 搜索错误 Trace
# 搜索条件：operation="POST /api/order", error=true

# 2. 发现链路断裂点
# Trace ID: a1b2c3d4e5f6
# 调用链：UserSvc → OrderSvc → PaymentSvc → ❌ Timeout

# 3. 分析 PaymentSvc 日志
# 2026-07-10 14:23:15 ERROR payment.go:45 timeout waiting for response from bank API
# 但银行 API 平均响应时间 200ms，为什么超时？

# 4. 查看 PaymentSvc 的 Span 详情
# Span: call-bank-api
# Duration: 5000ms (timeout)
# Tags: http.status_code=504
# Logs: [{"timestamp":"...","message":"retry attempt 1"}, {"timestamp":"...","message":"retry attempt 2"}]

# 5. 发现根本原因：PaymentSvc 配置了 3 次重试，每次 5s timeout
# 总耗时 = 3 × 5s = 15s，远超前端 5s timeout
```

**修复方案：**

```go
// 修复前：重试策略不合理
func (s *PaymentService) Charge(ctx context.Context, amount float64) error {
	for i := 0; i < 3; i++ {
		if err := s.callBankAPI(ctx, amount); err != nil {
			continue // 盲目重试
		}
		return nil
	}
	return fmt.Errorf("payment failed after 3 retries")
}

// 修复后：基于 Span 的智能重试
func (s *PaymentService) Charge(ctx context.Context, amount float64) error {
	_, span := s.tracer.Start(ctx, "PaymentService.Charge")
	defer span.End()
	
	// 从上游继承 deadline
	deadline, hasDeadline := ctx.Deadline()
	if !hasDeadline {
		deadline = time.Now().Add(3 * time.Second) // 默认 3s
	}
	
	// 计算剩余可用时间
	remaining := time.Until(deadline)
	retryCount := 0
	maxRetries := 2
	
	for retryCount < maxRetries {
		// 每次重试减少 timeout
		timeout := remaining / time.Duration(maxRetries-retryCount)
		if timeout < 500*time.Millisecond {
			timeout = 500 * time.Millisecond // 最小 500ms
		}
		
		childCtx, cancel := context.WithTimeout(ctx, timeout)
		err := s.callBankAPI(childCtx, amount)
		cancel()
		
		if err == nil {
			return nil
		}
		
		// 记录重试 Span
		span.AddEvent("retry", trace.WithAttributes(
			attribute.Int("attempt", retryCount+1),
			attribute.String("error", err.Error()),
			attribute.Float64("remaining_timeout_ms", float64(timeout.Microseconds())/1000),
		))
		
		retryCount++
		remaining = time.Until(deadline)
	}
	
	span.SetStatus(codes.Error, "payment exhausted all retries")
	return fmt.Errorf("payment failed after %d retries", retryCount)
}
```

### 4.2 案例二：Trace 数据爆炸 — 存储成本飙升

**现象**：Jaeger 存储从 50GB 暴涨到 500GB，查询延迟从 2s 增加到 30s。

**根因分析：**

```
问题分析：
1. 全量采样（AlwaysSample）在生产环境启用
2. 健康检查路径也被追踪（/health, /ready）
3. 批量操作产生大量 Span（一次导入 1000 条记录 = 1000 个 Span）

数据估算：
- QPS: 10,000
- 每秒 Span 数: ~50,000（每个请求 5 个 Span）
- 每天 Span 数: 50,000 × 86,400 = 4.32B
- 每个 Span 平均大小: 1KB
- 每天存储: 4.32TB ← 这就是问题所在！
```

**修复方案：**

```yaml
# jaeger-collector-config.yaml
sampling:
  strategies:
    default_strategy:
      type: probabilistic
      param: 0.01  # 1% 随机采样
    service_strategies:
      - service: payment-service
        type: probabilistic
        param: 0.1   # 支付服务 10% 采样（关键业务）
      - service: health-check
        type: rate_limiting
        param: 1     # 健康检查每秒最多 1 个 Span
```

```go
// 代码层面：批量操作使用 Span 组
func (s *ImportService) ImportRecords(ctx context.Context, records []Record) error {
	ctx, span := s.tracer.Start(ctx, "ImportService.ImportRecords")
	defer span.End()
	
	span.SetAttributes(
		attribute.Int("record_count", len(records)),
	)
	
	// 方案 1：使用 ChildSpans 但不每个都采样
	for _, record := range records {
		// 使用 StartSpanWithConfig 控制采样
		_, childSpan := s.tracer.Start(
			ctx,
			"ImportService.importRecord",
			trace.WithSpanKind(trace.SpanKindInternal), // 内部 Span
		)
		
		if err := s.processRecord(ctx, record); err != nil {
			childSpan.RecordError(err)
			childSpan.End()
			return err
		}
		childSpan.End()
	}
	
	return nil
}
```

### 4.3 案例三：Span 丢失 — 异步链路断裂

**现象**：订单创建后，后续的通知链路在 Jaeger 中看不到。

**根因：**

```
问题链路：
HTTP Request → OrderSvc.CreateOrder() → Kafka.Send(OrderCreated)
                                                        ↓
                                               NotifySvc.ProcessOrder()
                                                        ↓
                                              ❌ TraceId 丢失！
```

**修复方案：**

```go
// Kafka 消息生产者：注入 TraceContext
func (p *Producer) Send(ctx context.Context, topic string, key string, value []byte) error {
	_, span := p.tracer.Start(ctx, "KafkaProducer.Send")
	defer span.End()
	
	span.SetAttributes(
		attribute.String("messaging.system", "kafka"),
		attribute.String("messaging.destination", topic),
		attribute.String("messaging.kafka.message_key", key),
	)
	
	// 将 SpanContext 注入消息 Header
	headers := make([]sarama.RecordHeader, 0)
	propagator := otel.GetTextMapPropagator()
	
	// 创建临时 carrier
	carrier := &headerCarrier{}
	propagator.Inject(ctx, carrier)
	for k, v := range carrier.headers {
		headers = append(headers, sarama.RecordHeader{
			Key:   []byte(k),
			Value: []byte(v),
		})
	}
	
	msg := &sarama.ProducerMessage{
		Topic:   topic,
		Key:     sarama.StringEncoder(key),
		Value:   sarama.ByteEncoder(value),
		Headers: headers, // 携带追踪上下文
	}
	
	return p.client.SendMessage(msg)
}

// Kafka 消息消费者：提取 SpanContext
func (c *Consumer) processMessage(msg *sarama.ConsumerMessage) error {
	// 从 Header 提取 TraceContext
	carrier := &headerCarrier{headers: make(map[string]string)}
	for _, h := range msg.Headers {
		carrier.headers[string(h.Key)] = string(h.Value)
	}
	
	ctx := otel.GetTextMapPropagator().Extract(context.Background(), carrier)
	
	_, span := c.tracer.Start(ctx, "KafkaConsumer.Process", trace.WithSpanKind(trace.SpanKindConsumer))
	defer span.End()
	
	span.SetAttributes(
		attribute.String("messaging.system", "kafka"),
		attribute.String("messaging.destination", msg.Topic),
		attribute.Int64("messaging.kafka.partition", msg.Partition),
		attribute.Int64("messaging.kafka.offset", msg.Offset),
	)
	
	// 处理业务逻辑
	return c.handler(ctx, msg)
}
```

---

## 五、架构对比与 Trade-off

### 5.1 主流追踪方案对比

| 特性 | Jaeger | Zipkin | Tempo | OpenTelemetry |
|------|--------|--------|-------|--------------|
| **协议** | gRPC/HTTP | HTTP | gRPC | gRPC/HTTP |
| **存储后端** | Cassandra/Elastic | MySQL/Cassandra | Loki | 任意 |
| **查询语言** | UI + gRPC API | REST API | LogQL | 标准化 API |
| **采样支持** | ✅ 多种策略 | ✅ 基础采样 | ✅ | ✅ 最丰富 |
| **Go SDK** | ✅ 官方支持 | ✅ 官方支持 | ✅ | ✅ 官方首选 |
| **社区规模** | CNCF 毕业 | OpenZipkin | Grafana Labs | CNCF 毕业 |
| **适用场景** | 通用 | 轻量级 | 日志为主 | 多云/混合云 |

### 5.2 选型决策树

```
需要分布式追踪？
├── 是，主要用 Grafana/Loki？
│   └── 选 Tempo + OpenTelemetry
├── 是，需要完整 UI + 采样？
│   └── 选 Jaeger + OpenTelemetry
├── 轻量级需求？
│   └── 选 Zipkin
└── 否（只需要指标）
    └── Prometheus + Grafana 就够了
```

### 5.3 与现有知识库的对照

| 已有知识 | 本文件补充 | Gap 分析 |
|---------|-----------|---------|
| `microservice/service-mesh-observability-deep.md` | 链路追踪在 Service Mesh 层的实现 | 已有 Envoy Sidecar 层面的追踪，缺少应用层 SDK 集成 |
| `infrastructure/observability-otel-prometheus.md` | OpenTelemetry 指标部分 | 本文件专注 Tracing，补充了采样策略和 Go SDK |
| `infrastructure/observability-practice.md` | 日志聚合实践 | 本文件补充了 Trace-Log-Metric 关联方法 |

**新增 Gap**：
- 缺少 Trace 与 Metrics 关联的最佳实践（TraceID 注入到日志）
- 缺少大规模集群（>1000 服务）的追踪架构设计
- 缺少 APM 商业方案（Datadog/New Relic）与开源方案的对比

---

## 六、自测题

### Q1：在一个 10 万 QPS 的微服务系统中，如何设计采样策略才能在保证链路完整性的同时控制存储成本？

**参考答案：**

采用分层采样策略：
1. **根 Span 采样**：使用 `ParentBasedTraceIDRatio(0.01)`，即 1% 的根请求被采样
2. **关键路径强制采样**：支付、下单等核心链路使用 `AlwaysSample`，不受比例限制
3. **错误强制采样**：任何返回 5xx 的 Span 及其子 Span 全部采样
4. **内部 Span 降采样**：数据库、缓存等内部调用使用 `trace.SpanKindInternal`，不单独采样
5. **采样预算分配**：预留 0.5% 给调试/排障，0.5% 给常规链路

存储估算：
- 100,000 QPS × 1% = 1,000 采样 Trace/s
- 平均每 Trace 10 Span = 10,000 Span/s
- 每天 864M Span，每 Span 1KB ≈ 864GB/天
- 保留 7 天 ≈ 6TB，可控

### Q2：OpenTelemetry 的 API 和 SDK 为什么要分离？这种设计带来了什么好处和问题？

**参考答案：**

**好处：**
1. **解耦**：应用代码只依赖 API（轻量），不依赖 SDK（重）
2. **可替换**：可以无缝切换不同的 SDK 实现（Jaeger/Zipkin/Prometheus）
3. **零开销**：未初始化 SDK 时，API 调用是 no-op，不影响性能
4. **测试友好**：可以用 InMemoryExporter 做单元测试

**问题：**
1. **复杂性增加**：开发者需要理解 API vs SDK 的职责边界
2. **配置分散**：SDK 配置（采样、导出）与应用代码分离，容易遗漏
3. **版本兼容**：API 和 SDK 需要保持版本一致，否则行为不确定

### Q3：如何在一个已有的单体应用中逐步迁移到分布式追踪？给出渐进式方案。

**参考答案：**

**Phase 1：基础接入（1-2 周）**
- 在单体应用中引入 OpenTelemetry SDK
- 为每个 HTTP 请求创建一个 Root Span
- 配置 OTLP Exporter 到本地 Jaeger

**Phase 2：内部模块追踪（2-4 周）**
- 将单体拆分为内部模块（包）
- 每个模块入口创建 Child Span
- 使用 `trace.WithSpanKind(trace.SpanKindInternal)`

**Phase 3：数据库追踪（1-2 周）**
- 集成 GORM/SQL 插件
- 自动追踪所有 SQL 执行

**Phase 4：服务拆分（持续）**
- 每次拆分出一个微服务，立即接入追踪
- 确保新服务自动继承上游 TraceContext

**Phase 5：全链路优化（2-4 周）**
- 调整采样策略
- 添加自定义 Span Events
- 配置告警规则

---

## 七、动手验证

### 7.1 本地搭建追踪链路

```bash
# 1. 启动 Jaeger（Docker Compose）
cat > docker-compose.yaml << 'EOF'
version: '3.8'
services:
  jaeger-all-in-one:
    image: jaegertracing/all-in-one:1.58
    ports:
      - "16686:16686"  # UI
      - "4317:4317"    # OTLP gRPC
      - "4318:4318"    # OTLP HTTP
    environment:
      - COLLECTOR_OTLP_ENABLED=true
EOF

docker compose up -d

# 2. 访问 http://localhost:16686 查看 Jaeger UI

# 3. 运行 Go 示例
go run main.go --endpoint=localhost:4317
```

### 7.2 验证 Trace 传播

```go
// 验证代码：手动构造跨服务调用链
func TestTracePropagation(t *testing.T) {
	// 创建 InMemoryExporter（不需要真实的 Jaeger）
	exporter := newInMemoryExporter()
	tp := sdktrace.NewTracerProvider(
		sdktrace.WithSyncer(exporter),
		sdktrace.WithSampler(sdktrace.AlwaysSample()),
	)
	otel.SetTracerProvider(tp)
	otel.SetTextMapPropagator(propagation.NewCompositeTextMapPropagator(
		propagation.TraceContext{},
	))
	
	tracer := otel.Tracer("test-service")
	
	// 模拟服务 A 调用服务 B
	ctx := context.Background()
	_, spanA := tracer.Start(ctx, "ServiceA.Operation")
	
	// 提取 SpanContext 并注入 Header
	header := make(http.Header)
	otel.GetTextMapPropagator().Inject(spanA.Context(), propagation.HeaderCarrier(header))
	
	// 模拟服务 B 从 Header 提取
	extractedCtx := tracer.Extract(context.Background(), propagation.HeaderCarrier(header))
	_, spanB := tracer.Start(extractedCtx, "ServiceB.Operation")
	
	// 验证：两个 Span 应该有相同的 TraceID
	assert.Equal(t, spanA.SpanContext().TraceID(), spanB.SpanContext().TraceID())
	
	// 验证：spanB 的 ParentSpanID 应该是 spanA 的 SpanID
	assert.Equal(t, spanA.SpanContext().SpanID(), spanB.SpanContext().Parent())
	
	spanA.End()
	spanB.End()
	
	// 检查导出的 Span
	spans := exporter.GetSpans()
	assert.Len(t, spans, 2)
}
```

---

## 八、与知识库的对照

### 已有知识
1. **`microservice/service-mesh-observability-deep.md`** — 覆盖了 Envoy Sidecar 层面的流量管理和日志聚合，但未涉及应用层 SDK 集成
2. **`infrastructure/observability-otel-prometheus.md`** — 侧重 Metrics 采集，Tracing 部分较浅
3. **`architecture/ad-architecture-high-concurrency-deep.md`** — 有监控章节，但未深入分布式追踪

### 本文件补充
1. **OpenTelemetry Go SDK 源码级实现** — 从 TracerProvider 到 Exporter 的完整链路
2. **生产级中间件实现** — HTTP/gRPC/DB 三层中间件代码
3. **三大生产排障案例** — 超时/存储爆炸/异步链路断裂
4. **采样策略深度分析** — 从算法到存储成本估算

### 缺失内容（待补充）
1. Trace 与 Log 关联（TraceID 注入日志）
2. 大规模微服务集群（>1000 服务）的追踪架构
3. APM 商业方案对比
