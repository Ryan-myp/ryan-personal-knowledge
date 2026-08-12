# Prometheus 监控体系深度实现

> **文档级别**: Level 5 - 专家级  
> **创建日期**: 2026-08-13  
> **状态**: ✅ 已补齐

---

## 一、监控架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Prometheus 监控架构                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                   │
│   │   Node      │    │   Exporter  │    │  App        │                   │
│   │   Exporter  │    │  (Redis/    │    │  (HTTP      │                   │
│   │             │    │   MySQL)    │    │   /metrics) │                   │
│   └──────┬──────┘    └──────┬──────┘    └──────┬──────┘                   │
│          │                  │                  │                          │
│          └──────────────────┼──────────────────┘                          │
│                             │                                             │
│                      ┌──────▼──────┐                                      │
│                      │  Prometheus │                                     │
│                      │   Server    │                                      │
│                      │  (采集/存储) │                                      │
│                      └──────┬──────┘                                      │
│                             │                                             │
│              ┌──────────────┼──────────────┐                              │
│              │              │              │                              │
│      ┌───────▼──────┐ ┌────▼─────┐ ┌─────▼──────┐                       │
│      │   Grafana    │ │ Alert    │ │  Thanos    │                       │
│      │  (可视化)    │ │  Manager │ │  (长期存储)│                       │
│      └──────────────┘ └──────────┘ └────────────┘                       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 二、自定义 Metrics 设计

```go
// 文件: monitoring/metrics.go
package monitoring

import (
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
)

var (
	// ─── 竞价相关指标 ───
	adBidsTotal = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Namespace: "ad",
			Name:      "bids_total",
			Help:      "Total number of bids sent",
		},
		[]string{"ad_network", "creative_type"},
	)

	adBidLatency = promauto.NewHistogramVec(
		prometheus.HistogramOpts{
			Namespace: "ad",
			Name:      "bid_latency_ms",
			Help:      "Bid latency distribution",
			Buckets:   prometheus.DefBuckets,
		},
		[]string{"ad_network", "target_type"},
	)

	adBidSuccessRate = promauto.NewGaugeVec(
		prometheus.GaugeOpts{
			Namespace: "ad",
			Name:      "bid_success_rate",
			Help:      "Bid success rate by network",
		},
		[]string{"ad_network"},
	)

	// ─── 预算相关指标 ───
	budgetRemaining = promauto.NewGaugeVec(
		prometheus.GaugeOpts{
			Namespace: "ad",
			Name:      "budget_remaining_usd",
			Help:      "Remaining budget for campaign",
		},
		[]string{"campaign_id"},
	)

	// ─── 错误指标 ───
	errorCount = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Namespace: "ad",
			Name:      "errors_total",
			Help:      "Total errors by type",
		},
		[]string{"error_type", "source"},
	)
)

// 在代码中使用
func recordBid(network, creativeType string, latency float64, success bool) {
	adBidsTotal.WithLabelValues(network, creativeType).Inc()
	adBidLatency.WithLabelValues(network, creativeType).Observe(latency)
	
	if success {
		rate := calculateSuccessRate(network)
		adBidSuccessRate.WithLabelValues(network).Set(rate)
	} else {
		errorCount.WithLabelValues("bid_failed", "dsp").Inc()
	}
}
```

---

## 三、告警规则配置

```yaml
# 文件: prometheus/alert_rules.yaml
groups:
  - name: ad_bidding
    rules:
      # ─── 竞价延迟告警 ───
      - alert: HighBidLatency
        expr: histogram_quantile(0.99, rate(ad_bid_latency_ms_bucket[5m])) > 200
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "High bid latency on {{ $labels.ad_network }}"
          description: "P99 latency is {{ $value }}ms, threshold 200ms"

      - alert: CriticalBidLatency
        expr: histogram_quantile(0.99, rate(ad_bid_latency_ms_bucket[5m])) > 500
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Critical bid latency!"

      # ─── 预算告警 ───
      - alert: BudgetExhausted
        expr: ad_budget_remaining_usd < 10
        for: 1h
        labels:
          severity: warning
        annotations:
          summary: "Campaign {{ $labels.campaign_id }} budget running low"

      # ─── 错误率告警 ───
      - alert: HighErrorRate
        expr: rate(ad_errors_total[5m]) / rate(ad_bids_total[5m]) > 0.1
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High error rate on {{ $labels.source }}"
```

---

## 四、Grafana Dashboard 配置

```json
{
  "dashboard": {
    "title": "广告竞价系统监控",
    "panels": [
      {
        "title": "竞价延迟 P99",
        "type": "graph",
        "targets": [
          {
            "expr": "histogram_quantile(0.99, rate(ad_bid_latency_ms_bucket[5m]))"
          }
        ]
      },
      {
        "title": "每日预算消耗",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(ad_budget_spent_usd[24h])"
          }
        ]
      }
    ]
  }
}
```

---

## 五、参考资料

```
核心文档:
├── Prometheus: https://prometheus.io/docs/
├── Grafana: https://grafana.com/docs/
└── Prometheus Best Practices: https://prometheus.io/docs/practices/

 exporters:
├── Node Exporter: 系统指标
├── Redis Exporter: 缓存指标
├── mysqld Exporter: 数据库指标
└── Blackbox Exporter: 黑盒监控
```

---

*文档版本: v1.0*  
*最后更新: 2026-08-13*  
*作者: Ryan*
