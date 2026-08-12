# Prometheus Exporter 深度实现 - 自定义指标采集

> **版本**: v2.0  
> **日期**: 2026-08-13  
> **作者**: Ryan  
> **分类**: DevOps  
> **代码密度**: 28%

---

## 一、Exporter 架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Prometheus Exporter 架构                          │
│                                                                     │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐            │
│  │ Prometheus  │───▶│  Exporter   │───▶│  Target     │            │
│  │  Server     │    │  (HTTP)     │    │  (App/DB)   │            │
│  └─────────────┘    └──────┬──────┘    └─────────────┘            │
│                            │                                       │
│              ┌─────────────┼─────────────┐                        │
│              ▼             ▼             ▼                        │
│        ┌──────────┐ ┌──────────┐ ┌──────────┐                    │
│        │ Counter  │ │ Gauge    │ │ Histogram│                    │
│        │ (计数器) │ │ (仪表盘) │ │ (直方图) │                    │
│        └──────────┘ └──────────┘ └──────────┘                    │
│                                                                     │
│  常用 Exporter:                                                      │
│  • node_exporter    - 服务器指标                                     │
│  • mysql_exporter   - MySQL 指标                                     │
│  • redis_exporter   - Redis 指标                                     │
│  • blackbox_exporter - 黑盒探测                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 二、自定义 Exporter (Go)

```go
// exporter/custom.go
package main

import (
    "github.com/prometheus/client_golang/prometheus"
    "github.com/prometheus/client_golang/prometheus/promhttp"
    "net/http"
    "time"
)

// AdMetrics 广告业务指标
type AdMetrics struct {
    BidRequests      *prometheus.CounterVec
    BidWins          *prometheus.CounterVec
    BidLatency       *prometheus.HistogramVec
    BudgetRemaining  *prometheus.GaugeVec
}

// NewAdMetrics 创建指标
func NewAdMetrics() *AdMetrics {
    return &AdMetrics{
        BidRequests: prometheus.NewCounterVec(
            prometheus.CounterOpts{
                Name: "ad_bid_requests_total",
                Help: "Total bid requests",
            },
            []string{"advertiser_id", "status"},
        ),
        BidWins: prometheus.NewCounterVec(
            prometheus.CounterOpts{
                Name: "ad_bid_wins_total",
                Help: "Total bid wins",
            },
            []string{"advertiser_id"},
        ),
        BidLatency: prometheus.NewHistogramVec(
            prometheus.HistogramOpts{
                Name:    "ad_bid_latency_seconds",
                Help:    "Bid latency distribution",
                Buckets: []float64{0.001, 0.005, 0.01, 0.02, 0.05, 0.1},
            },
            []string{"advertiser_id"},
        ),
        BudgetRemaining: prometheus.NewGaugeVec(
            prometheus.GaugeOpts{
                Name: "ad_budget_remaining",
                Help: "Remaining budget",
            },
            []string{"advertiser_id"},
        ),
    }
}

// Register 注册指标
func (m *AdMetrics) Register(registry *prometheus.Registry) {
    registry.MustRegister(m.BidRequests)
    registry.MustRegister(m.BidWins)
    registry.MustRegister(m.BidLatency)
    registry.MustRegister(m.BudgetRemaining)
}

// 主函数
func main() {
    metrics := NewAdMetrics()
    registry := prometheus.NewRegistry()
    metrics.Register(registry)
    
    http.Handle("/metrics", promhttp.HandlerFor(registry, promhttp.HandlerOpts{}))
    http.ListenAndServe(":9100", nil)
}
```

---

## 三、指标类型详解

```go
// exporter/metric_types.go
package main

import (
    "github.com/prometheus/client_golang/prometheus"
)

// 1. Counter: 只增不减
var requestCount = prometheus.NewCounter(prometheus.CounterOpts{
    Name: "http_requests_total",
    Help: "Total HTTP requests",
})

// 2. Gauge: 可增可减
var temperature = prometheus.NewGauge(prometheus.GaugeOpts{
    Name: "cpu_temperature_celsius",
    Help: "CPU temperature",
})

// 3. Histogram: 直方图分布
var requestDuration = prometheus.NewHistogram(prometheus.HistogramOpts{
    Name:    "http_request_duration_seconds",
    Help:    "HTTP request duration",
    Buckets: prometheus.ExponentialBuckets(0.001, 2, 10), // 1ms ~ 512ms
})

// 4. Summary: 分位数摘要
var latencySummary = prometheus.NewSummary(prometheus.SummaryOpts{
    Name:       "request_latency_seconds",
    Help:       "Request latency summary",
    Objectives: map[float64]float64{0.5: 0.05, 0.9: 0.01, 0.99: 0.001},
})
```

---

## 四、Grafana Dashboard 配置

```json
{
  "dashboard": {
    "title": "广告竞价系统监控",
    "panels": [
      {
        "title": "竞价请求速率",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(ad_bid_requests_total[5m])",
            "legendFormat": "{{advertiser_id}}"
          }
        ]
      },
      {
        "title": "竞价延迟 P99",
        "type": "graph",
        "targets": [
          {
            "expr": "histogram_quantile(0.99, rate(ad_bid_latency_seconds_bucket[5m]))"
          }
        ]
      },
      {
        "title": "预算剩余",
        "type": "gauge",
        "targets": [
          {
            "expr": "ad_budget_remaining",
            "legendFormat": "{{advertiser_id}}"
          }
        ]
      }
    ]
  }
}
```

---

## 五、自测题

1. **Counter 和 Gauge 的区别？**
   - Counter 只增不减，Gauge 可增可减

2. **Histogram 和 Summary 的区别？**
   - Histogram 服务端计算分位数，Summary 客户端计算

3. **Exporter 端口为什么要独立？**
   - 避免与业务端口冲突，支持独立监控

