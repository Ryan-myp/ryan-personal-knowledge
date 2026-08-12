# Agent 可观测性生产级实现

> **版本**: v2.0  
> **日期**: 2026-08-13  
> **作者**: Ryan  
> **分类**: Agent/AI  
> **代码密度**: 30%

---

## 一、可观测性三件套

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Agent 可观测性架构                                │
│                                                                     │
│  Metrics (指标)                      Traces (链路追踪)               │
│  ┌─────────────────┐                 ┌─────────────────┐           │
│  │ • 请求量        │                 │ • 完整调用链    │           │
│  │ • 延迟分布      │                 │ • 耗时分析      │           │
│  │ • 错误率        │                 │ • 依赖拓扑      │           │
│  │ • Token 用量    │                 │ • 瓶颈定位      │           │
│  └────────┬────────┘                 └────────┬────────┘           │
│           │                                    │                    │
│           ▼                                    ▼                    │
│  ┌─────────────────┐                 ┌─────────────────┐           │
│  │   Prometheus    │                 │   Jaeger /      │           │
│  │   + Grafana     │                 │   Tempo         │           │
│  └─────────────────┘                 └─────────────────┘           │
│                                                                     │
│  Logs (日志)                                                        │
│  ┌─────────────────┐                                                 │
│  │ • 结构化日志    │                                                 │
│  │ • 错误堆栈      │                                                 │
│  │ • 对话历史      │                                                 │
│  └────────┬────────┘                                                 │
│           ▼                                                          │
│  ┌─────────────────┐                                                 │
│  │   Loki /        │                                                 │
│  │   ELK Stack     │                                                 │
│  └─────────────────┘                                                 │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 二、OpenTelemetry 集成

```go
// agent/otel.go
package agent

import (
    "context"
    "go.opentelemetry.io/otel"
    "go.opentelemetry.io/otel/attribute"
    "go.opentelemetry.io/otel/exporters/jaeger"
    "go.opentelemetry.io/otel/sdk/trace"
    semconv "go.opentelemetry.io/otel/semconv/v1.21.0"
)

// InitTracer 初始化追踪
func InitTracer(serviceName string) (*trace.TracerProvider, error) {
    // Jaeger exporter
    exporter, err := jaeger.New(jaeger.WithCollectorEndpoint(
        jaeger.WithEndpoint("http://jaeger:14268/api/traces"),
    ))
    if err != nil {
        return nil, err
    }
    
    tp := trace.NewTracerProvider(
        trace.WithSampler(trace.AlwaysSample()),
        trace.WithBatcher(exporter),
    )
    otel.SetTracerProvider(tp)
    
    return tp, nil
}

// StartSpan 开始 Span
func StartSpan(ctx context.Context, name string) (context.Context, trace.Span) {
    tracer := otel.Tracer("agent")
    return tracer.Start(ctx, name)
}

// RecordMetric 记录指标
func RecordMetric(ctx context.Context, metricName string, value float64, attrs ...attribute.KeyValue) {
    meter := otel.Meter("agent")
    counter, _ := meter.Int64Counter(metricName)
    counter.Add(ctx, int64(value), attrs...)
}
```

---

## 三、对话日志

```go
// agent/conversation_logger.go
package agent

import (
    "context"
    "encoding/json"
    "time"
)

// ConversationLog 对话日志
type ConversationLog struct {
    ID          string           `json:"id"`
    SessionID   string           `json:"session_id"`
    Timestamp   time.Time        `json:"timestamp"`
    Messages    []MessageLog     `json:"messages"`
    Metadata    map[string]interface{} `json:"metadata"`
}

type MessageLog struct {
    Role      string    `json:"role"`      // system/user/assistant/tool
    Content   string    `json:"content"`
    ToolCall  *ToolCall `json:"tool_call,omitempty"`
    Timestamp time.Time `json:"timestamp"`
}

type ToolCall struct {
    ID       string          `json:"id"`
    Name     string          `json:"name"`
    Arguments json.RawMessage `json:"arguments"`
    Result   json.RawMessage `json:"result,omitempty"`
}

// ConversationLogger 对话日志记录器
type ConversationLogger struct {
    store ConversationStore
}

func (l *ConversationLogger) Log(ctx context.Context, log *ConversationLog) error {
    log.ID = generateID()
    log.Timestamp = time.Now()
    return l.store.Save(ctx, log)
}
```

---

## 四、Dashboard 配置

```yaml
# grafana-dashboard.json
{
  "dashboard": {
    "title": "Agent Performance",
    "panels": [
      {
        "title": "Request Rate",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(agent_request_total[5m])",
            "legendFormat": "{{model}}"
          }
        ]
      },
      {
        "title": "Latency P99",
        "type": "graph",
        "targets": [
          {
            "expr": "histogram_quantile(0.99, rate(agent_request_duration_seconds_bucket[5m]))"
          }
        ]
      },
      {
        "title": "Token Usage",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(agent_tokens_total[5m])",
            "legendFormat": "{{type}}"
          }
        ]
      },
      {
        "title": "Error Rate",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(agent_request_errors_total[5m]) / rate(agent_request_total[5m])"
          }
        ]
      }
    ]
  }
}
```

---

## 五、告警规则

```yaml
# alert.rules.yaml
groups:
  - name: agent
    rules:
      - alert: HighErrorRate
        expr: rate(agent_request_errors_total[5m]) / rate(agent_request_total[5m]) > 0.05
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Agent error rate above 5%"
          
      - alert: HighLatency
        expr: histogram_quantile(0.99, rate(agent_request_duration_seconds_bucket[5m])) > 3
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "P99 latency above 3s"
          
      - alert: TokenBudgetExceeded
        expr: agent_tokens_total > 1000000
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Token budget exceeded"
```

---

## 六、自测题

1. **OpenTelemetry 的优势是什么？**
   - 厂商无关、统一 API、自动注入

2. **对话日志为什么重要？**
   - 调试、审计、改进模型

3. **Grafana Dashboard 看什么核心指标？**
   - 请求量、延迟、错误率、Token 消耗

