# 可观测性追踪 - 资深专家深度实现

## 一、OpenTelemetry架构

```
┌─────────────────────────────────────────────────────────────┐
│                    OpenTelemetry架构                          │
│                                                             │
│  ┌─────────┐    ┌─────────────┐    ┌─────────────┐        │
│  │  App A  │───►│ OTel Agent  │───►│  Collector  │        │
│  │  App B  │───►│ (Sidecar)   │    │  (采集器)    │        │
│  └─────────┘    └─────────────┘    └──────┬──────┘        │
│                                            │                │
│                                       ┌────┴────┐          │
│                                       │  Backends │        │
│                                       │(Jaeger/  │        │
│                                       │ Prometheus)       │
│                                       └───────────┘        │
└─────────────────────────────────────────────────────────────┘
```

## 二、Trace实现

### 2.1 Go实现

```go
package tracing

import (
	"context"
	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/trace"
)

var tracer = otel.Tracer("my-service")

func DoWork(ctx context.Context) error {
	ctx, span := tracer.Start(ctx, "do-work")
	defer span.End()
	
	// 业务逻辑
	span.AddEvent("work started")
	span.SetAttributes(
		traceattribute.String("work.type", "complex"),
	)
	
	return nil
}
```

### 2.2 Span配置

```go
span := tracer.Start(
	context.Background(),
	"process-order",
	trace.WithSpanKind(trace.SpanKindServer),
	trace.WithAttributes(
	 attribute.String("order.id", orderID),
	 attribute.Int("order.amount", amount),
	),
)
```

## 三、Metrics采集

### 3.1 指标类型

```go
// Counter: 只增不减
counter := meter.Int64Counter("http.requests.total")
counter.Add(ctx, 1)

// Histogram: 分布统计
histogram := meter.Int64Histogram("http.request.duration")
histogram.Record(ctx, duration.Milliseconds())

// UpDownCounter: 可增可减
updown := meter.Int64UpDownCounter("active.users")
updown.Add(ctx, 1)
```

### 3.2 Prometheus导出

```go
import "go.opentelemetry.io/otel/exporters/prometheus"

exporter, _ := prometheus.New()
meterProvider := sdkmeter.NewMeterProvider(
	sdkmeter.WithReader(exporter),
)
otel.SetMeterProvider(meterProvider)
```

## 四、日志关联

```json
{
  "trace_id": "0x89c5...",
  "span_id": "0x5b8cf...",
  "service.name": "order-service",
  "level": "INFO",
  "message": "Order processed"
}
```

## 五、集成Jaeger

```yaml
# docker-compose.yml
services:
  jaeger:
    image: jaegertracing/all-in-one:latest
    ports:
      - "16686:16686"  # UI
      - "14268:14268"  # Collector
      - "4317:4317"    # OTLP gRPC
```

## 六、面试高频题

### Q1: 为什么要用OpenTelemetry？

```
A: 统一的可观测性标准，支持多种后端。
```

### Q2: Trace如何采样？

```
A: 概率采样、确定性采样、自适应采样。
```

## 七、自测题

1. 实现一个完整的Tracing系统
2. 如何关联Logs和Traces？

---

## 参考文档

- [OpenTelemetry文档](https://opentelemetry.io/docs/)
