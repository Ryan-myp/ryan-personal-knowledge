# 监控栈设计 - 资深专家深度实现

## 一、监控架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                   监控栈架构                                               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   Metrics              Traces                Logs                      │
│   ┌─────────┐       ┌─────────┐         ┌─────────┐                   │
│   │Prometheus│      │ Jaeger  │         │ Loki    │                   │
│   │ 指标采集  │─────►│ 链路追踪 │────────►│ 日志聚合 │                   │
│   └────┬────┘       └────┬────┘         └────┬────┘                   │
│        │                 │                   │                          │
│        ▼                 ▼                   ▼                          │
│   ┌─────────────────────────────────────────────────┐                  │
│   │              Grafana (统一展示)                   │                  │
│   └─────────────────────────────────────────────────┘                  │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、Prometheus实现

```go
package monitoring

import (
    "context"
    "github.com/prometheus/client_golang/prometheus"
)

// MetricsCollector 指标采集器
type MetricsCollector struct {
    registry *prometheus.Registry
}

// CustomMetrics 自定义指标
type CustomMetrics struct {
    RequestLatency *prometheus.Histogram
    RequestCount   *prometheus.Counter
    ErrorCount     *prometheus.Counter
}

func NewMetricsCollector() *MetricsCollector {
    return &MetricsCollector{
        registry: prometheus.NewRegistry(),
    }
}

func (c *MetricsCollector) RegisterMetrics() *CustomMetrics {
    latency := prometheus.NewHistogram(prometheus.HistogramOpts{
        Name:    "request_latency_seconds",
        Help:    "Request latency distribution",
        Buckets: prometheus.ExponentialBuckets(0.001, 2, 10),
    })
    
    count := prometheus.NewCounter(prometheus.CounterOpts{
        Name: "request_count_total",
        Help: "Total request count",
    })
    
    errors := prometheus.NewCounter(prometheus.CounterOpts{
        Name: "error_count_total",
        Help: "Total error count",
    })
    
    c.registry.MustRegister(latency, count, errors)
    
    return &CustomMetrics{
        RequestLatency: latency,
        RequestCount:   count,
        ErrorCount:     errors,
    }
}
```

## 三、告警规则实现

```go
package monitoring

// AlertRule 告警规则
type AlertRule struct {
    Name        string
    Expression  string
    Duration    time.Duration
    Severity    string
    Description string
}

// AlertManager 告警管理器
type AlertManager struct {
    rules  []AlertRule
    client *AlertmanagerClient
}

// EvaluateRules 评估规则
func (m *AlertManager) EvaluateRules(ctx context.Context) ([]Alert, error) {
    var alerts []Alert
    
    for _, rule := range m.rules {
        value, err := m.client.Query(ctx, rule.Expression)
        if err != nil {
            continue
        }
        
        if value > rule.Threshold {
            alerts = append(alerts, Alert{
                Rule:      rule.Name,
                Value:     value,
                Severity:  rule.Severity,
                StartedAt: time.Now(),
            })
        }
    }
    
    return alerts, nil
}
```

## 四、面试高频题

### Q1: Prometheus如何工作？

```
A:
1. Pull模式采集
2. 时序存储
3. PromQL查询
```

### Q2: 如何设计告警规则？

```
A:
1. 阈值设定
2. 持续时间
3. 分级处理
```

## 五、自测题

1. 解释监控架构
2. 如何实现指标采集？
3. 如何设计告警？

---

## 参考文档

- [Prometheus](https://prometheus.io/docs/)
- [Grafana](https://grafana.com/docs/)
