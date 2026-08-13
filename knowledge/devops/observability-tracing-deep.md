# 可观测性链路追踪 - 资深专家深度实现

## 一、架构设计

```
┌─────────────────────────────────────────────────────────────────────────┐
│                   OpenTelemetry 链路追踪架构                               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   Instrumentation        Collector               Backend               │
│   ┌─────────────┐       ┌─────────────┐       ┌─────────────┐        │
│   │ SDK         │───►│ Exporter    │───►│ Jaeger      │        │
│   │ 埋点        │    │ 收集        │    │ Tempo       │        │
│   └─────────────┘       └─────────────┘       └─────────────┘        │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、实现代码

```go
package observability

import (
    "context"
    "go.opentelemetry.io/otel"
    "go.opentelemetry.io/otel/trace"
)

// TracerProvider 追踪提供者
type TracerProvider struct {
    tracer trace.Tracer
}

// StartSpan 开始span
func (p *TracerProvider) StartSpan(ctx context.Context, name string) (context.Context, trace.Span) {
    return p.tracer.Start(ctx, name)
}

// TraceHTTP 追踪HTTP请求
func TraceHTTP(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        ctx, span := otel.Tracer("http").Start(r.Context(), r.URL.Path)
        defer span.End()
        
        // 设置属性
        span.SetAttributes(
            attribute.String("http.method", r.Method),
            attribute.String("http.url", r.URL.String()),
        )
        
        // 调用下一个handler
        next.ServeHTTP(w, r.WithContext(ctx))
    })
}
```

## 三、面试高频题

### Q1: 链路追踪的核心价值？

```
A:
1. 定位性能瓶颈
2. 理解调用链
3. 排查分布式故障
```

### Q2: 如何选择Trace ID？

```
A:
1. 全局唯一
2. 关联父子span
3. 标准化格式
```

## 四、自测题

1. 解释链路追踪架构
2. 如何实现埋点？
3. 如何分析trace？

---

## 参考文档

- [OpenTelemetry](https://opentelemetry.io/)
- [Jaeger](https://www.jaegertracing.io/)
