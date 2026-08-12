# Prometheus 监控体系深度实现

> **文档级别**: Level 5 - 专家级  
> **创建日期**: 2026-08-13  
> **状态**: ✅ 已补齐

---

## 一、Exporter 架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Prometheus 架构                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                    │
│  │  Node       │    │  MySQL      │    │  Kafka      │                    │
│  │  Exporter   │    │  Exporter   │    │  Exporter   │                    │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘                    │
│         │                  │                  │                            │
│         └──────────────────┼──────────────────┘                            │
│                            │                                                │
│                    ┌───────▼───────┐                                       │
│                    │  Prometheus   │                                       │
│                    │  Server       │                                       │
│                    └───────┬───────┘                                       │
│                            │                                                │
│         ┌──────────────────┼──────────────────┐                           │
│         ▼                  ▼                  ▼                            │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐                      │
│  │  Grafana    │   │  Alertman- │   │  Push       │                      │
│  │  Dashboard  │   │  ager      │   │  Gateway    │                      │
│  └─────────────┘   └─────────────┘   └─────────────┘                      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 二、自定义 Exporter

```go
// 文件: devops/prometheus/exporter.go

package main

import (
    "github.com/prometheus/client_golang/prometheus"
    "github.com/prometheus/client_golang/prometheus/promhttp"
    "net/http"
)

type AdExporter struct {
    requestCounter *prometheus.CounterVec
    latencySummary *prometheus.SummaryVec
}

func NewAdExporter() *AdExporter {
    return &AdExporter{
        requestCounter: prometheus.NewCounterVec(
            prometheus.CounterOpts{
                Name: "ad_requests_total",
                Help: "Total ad requests",
            },
            []string{"platform", "status"},
        ),
        latencySummary: prometheus.NewSummaryVec(
            prometheus.SummaryOpts{
                Name: "ad_request_latency_seconds",
                Help: "Ad request latency",
            },
            []string{"platform"},
        ),
    }
}

func (e *AdExporter) Describe(ch chan<- *prometheus.Desc) {
    e.requestCounter.Describe(ch)
    e.latencySummary.Describe(ch)
}

func (e *AdExporter) Collect(ch chan<- prometheus.Metric) {
    e.requestCounter.Collect(ch)
    e.latencySummary.Collect(ch)
}

func main() {
    exporter := NewAdExporter()
    prometheus.MustRegister(exporter)
    
    http.Handle("/metrics", promhttp.Handler())
    http.ListenAndServe(":9100", nil)
}
```

---

## 三、Grafana 仪表盘

```json
{
  "dashboard": {
    "title": "广告竞价系统监控",
    "panels": [
      {
        "title": "请求 QPS",
        "targets": [
          {
            "expr": "rate(ad_requests_total[5m])"
          }
        ]
      },
      {
        "title": "P99 延迟",
        "targets": [
          {
            "expr": "histogram_quantile(0.99, rate(ad_request_latency_seconds_bucket[5m]))"
          }
        ]
      }
    ]
  }
}
```

---

## 四、参考资料

```
核心文档:
├── Prometheus: https://prometheus.io/
├── Grafana: https://grafana.com/
└── Go Client: https://github.com/prometheus/client_golang
```

---

*文档版本: v1.0*  
*最后更新: 2026-08-13*  
*作者: Ryan*

## 四、告警配置

```yaml
groups:
- name: example
  rules:
  - alert: HighCPU
    expr: process_cpu_seconds_total > 0.8
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "High CPU usage"
      
  - alert: HighErrorRate
    expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.05
    for: 10m
    labels:
      severity: critical
    annotations:
      summary: "High error rate"
```

---

## 自测题

### Q1: Prometheus的四种指标类型？
**A**: Counter/Gauge/Histogram/Summary

### Q2: 如何开发自定义Exporter？
**A**: 使用prometheus/client_golang库，定义指标并暴露/metrics端点

### Q3: Alertmanager的作用？
**A**: 处理Prometheus告警，支持去重、分组、路由和静默

---

**关键词**: Prometheus, Exporter, Alertmanager, 监控, 告警
