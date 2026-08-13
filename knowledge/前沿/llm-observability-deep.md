# LLM可观测性 - 资深专家深度实现

## 一、可观测性架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                   LLM 可观测性架构                                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   Metrics                Traces                  Logs                   │
│   ┌─────────┐         ┌─────────┐          ┌─────────┐                │
│   │ 延迟    │         │ 调用链  │          │ 请求日志│                │
│   │ 吞吐    │────────►│ 追踪    │─────────►│ 错误日志│                │
│   │ 错误率  │         │ 分析    │          │ 审计日志│                │
│   └─────────┘         └─────────┘          └─────────┘                │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、实现代码

```go
package observability

import (
    "context"
    "github.com/prometheus/client_golang/prometheus"
)

// LLMObserver LLM可观测性
type LLMObserver struct {
    latency     *prometheus.Histogram
    throughput  *prometheus.Counter
    errors      *prometheus.Counter
    traces      *Tracer
}

func NewLLMObserver(registry *prometheus.Registry) *LLMObserver {
    return &LLMObserver{
        latency: prometheus.NewHistogram(prometheus.HistogramOpts{
            Name:    "llm_request_latency_seconds",
            Help:    "LLM请求延迟",
            Buckets: prometheus.ExponentialBuckets(0.1, 2, 10),
        }),
        throughput: prometheus.NewCounter(prometheus.CounterOpts{
            Name: "llm_request_total",
            Help: "LLM请求总数",
        }),
        errors: prometheus.NewCounter(prometheus.CounterOpts{
            Name: "llm_error_total",
            Help: "LLM错误总数",
        }),
        traces: NewTracer(),
    }
}

// ObserveRequest 观察请求
func (o *LLMObserver) ObserveRequest(ctx context.Context, req Request) (*Response, error) {
    start := time.Now()
    o.throughput.Inc()
    
    defer func() {
        elapsed := time.Since(start).Seconds()
        o.latency.Observe(elapsed)
    }()
    
    // 开始追踪
    span := o.traces.StartSpan(ctx, "llm_request")
    defer span.Finish()
    
    // 执行请求
    resp, err := o.model.Generate(ctx, req)
    if err != nil {
        o.errors.Inc()
        return nil, err
    }
    
    return resp, nil
}
```

## 三、面试高频题

### Q1: LLM可观测性关注什么？

```
A:
1. 延迟分布
2. 错误率
3. Token消耗
```

### Q2: 如何追踪Token使用？

```
A:
1. 请求计数
2. Prompt/Completion分离
3. 成本核算
```

## 四、自测题

1. 解释可观测性架构
2. 如何实现追踪？
3. 如何监控Token？

---

## 参考文档

- [OpenLLMetry](https://github.com/traceloop/openllmetry)
- [LangSmith](https://www.langchain.com/langsmith)
