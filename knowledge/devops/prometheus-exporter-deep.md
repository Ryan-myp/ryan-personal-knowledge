# Prometheus Exporter 开发深度实现

> **版本**: v1.0  
> **日期**: 2026-08-13  
> **作者**: Ryan  
> **分类**: DevOps / 可观测性  
> **难度**: 高级

---

## 一、Overview

### 1.1 Prometheus Exporter 是什么？

**Prometheus Exporter** 是将非 Prometheus 原生指标转换为 Prometheus 格式的工具，让 Prometheus 能够监控各种基础设施和应用。

```
┌──────────────────────────────────────────────────────────────────────┐
│                       Prometheus Ecosystem                           │
│                                                                      │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐              │
│  │   Exporter   │───▶│   Prometheus│───▶│   Grafana   │              │
│  │  (指标采集)   │    │  (指标存储)  │    │  (指标展示)  │              │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘              │
│         │                  │                  │                      │
│         ▼                  ▼                  ▼                      │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐              │
│  │  黑箱 Exporter│    │  Pushgateway│    │  自定义 Dashboard │          │
│  │ (node_exporter)│   │  (指标推送)   │    │  (告警规则)    │              │
│  └─────────────┘    └─────────────┘    └─────────────┘              │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

### 1.2 Exporter 类型对比

```
┌───────────────────────────────────────────────────────────────────────────┐
│                         Exporter 类型对比                                  │
├──────────────────────────────────┬────────────────────────────────────────┤
│ 类型                           │ 说明                                     │
├──────────────────────────────────┼────────────────────────────────────────┤
│ Blackbox Exporter              │ HTTP/DNS/TCP 探测                        │
│ Node Exporter                  │ 主机指标 (CPU/内存/磁盘/网络)               │
│ mysqld Exporter                │ MySQL 指标                                │
│ cadvisor                      │ Docker 容器指标                          │
│ SNMP Exporter                  │ 网络设备指标                             │
│ 自定义 Exporter                │ 应用自定义指标                           │
└──────────────────────────────────┴────────────────────────────────────────┘
```

---

## 二、Exporter 架构设计

### 2.1 核心组件

```go
// exporter.go
package main

import (
    "github.com/prometheus/client_golang/prometheus"
    "github.com/prometheus/client_golang/prometheus/promhttp"
    "net/http"
)

// Collector 接口：所有 Exporter 必须实现此接口
type Collector interface {
    Describe(chan<- *Desc)
    Collect(chan<- Metric)
}

// 自定义 Exporter
type MyExporter struct {
    requestsTotal *prometheus.CounterVec
    latency       *prometheus.HistogramVec
}

// 实现 Describe 方法
func (e *MyExporter) Describe(ch chan<- *prometheus.Desc) {
    ch <- e.requestsTotal.Desc()
    ch <- e.latency.Desc()
}

// 实现 Collect 方法
func (e *MyExporter) Collect(ch chan<- prometheus.Metric) {
    // 收集指标数据
    ch <- e.requestsTotal.Collect()
    ch <- e.latency.Collect()
}
```

### 2.2 Exporter 生命周期

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Exporter 生命周期                               │
│                                                                     │
│  启动 ──▶ 注册指标 ──▶ 启动 HTTP Server ──▶ 接收采集请求             │
│    │          │              │                    │                 │
│    │          ▼              ▼                    ▼                 │
│    │     初始化        端口绑定           返回指标数据               │
│    │          │              │                    │                 │
│    │          ▼              ▼                    ▼                 │
│    │     Desc描述      /metrics端点       Counter/Histogram         │
│    │                                                                   │
│  停止 ◀── 优雅关闭 ◀── 注销指标 ◀── 关闭 HTTP Server                  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 三、完整实现

### 3.1 基础 Exporter

```go
// cmd/exporter/main.go
package main

import (
    "fmt"
    "log"
    "net/http"
    "os"
    "os/signal"
    "syscall"

    "github.com/prometheus/client_golang/prometheus"
    "github.com/prometheus/client_golang/prometheus/promhttp"
)

// 应用指标
var (
    requestCount = prometheus.NewCounterVec(
        prometheus.CounterOpts{
            Name: "http_requests_total",
            Help: "Total HTTP requests",
        },
        []string{"method", "endpoint", "status"},
    )

    requestDuration = prometheus.NewHistogramVec(
        prometheus.HistogramOpts{
            Name:    "http_request_duration_seconds",
            Help:    "HTTP request duration",
            Buckets: prometheus.DefBuckets,
        },
        []string{"method", "endpoint"},
    )

    activeGoroutines = prometheus.NewGauge(
        prometheus.GaugeOpts{
            Name: "go_goroutines",
            Help: "Number of goroutines",
        },
    )
)

func init() {
    // 注册指标
    prometheus.MustRegister(requestCount)
    prometheus.MustRegister(requestDuration)
    prometheus.MustRegister(activeGoroutines)
}

func main() {
    port := os.Getenv("PORT")
    if port == "" {
        port = "9100"
    }

    http.Handle("/metrics", promhttp.Handler())

    http.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
        requestCount.WithLabelValues(r.Method, r.URL.Path, "200").Inc()
        requestDuration.WithLabelValues(r.Method, r.URL.Path).Observe(0.1)
        w.Write([]byte("OK"))
    })

    // 优雅关闭
    go func() {
        sigChan := make(chan os.Signal, 1)
        signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)
        <-sigChan
        log.Println("Shutting down...")
        os.Exit(0)
    }()

    log.Printf("Starting exporter on :%s", port)
    log.Fatal(http.ListenAndServe(":"+port, nil))
}
```

### 3.2 完整 Exporter (Collector 模式)

```go
// cmd/exporter/collector.go
package main

import (
    "fmt"
    "sync"
    "time"

    "github.com/prometheus/client_golang/prometheus"
)

// AdBidExporter 广告竞价 Exporter
type AdBidExporter struct {
    mu sync.Mutex

    // 指标定义
    bidsTotal         *prometheus.CounterVec
    bidsLatency       *prometheus.HistogramVec
    bidsFailed        *prometheus.CounterVec
    priceDistribution *prometheus.HistogramVec
    winRate           *prometheus.GaugeVec

    // 采集状态
    lastCollectTime time.Time
}

// NewAdBidExporter 创建新的 Exporter
func NewAdBidExporter() *AdBidExporter {
    return &AdBidExporter{
        bidsTotal: prometheus.NewCounterVec(
            prometheus.CounterOpts{
                Namespace: "ad",
                Subsystem: "bid",
                Name:      "total",
                Help:      "Total bid requests",
            },
            []string{"source", "ad_type", "country"},
        ),

        bidsLatency: prometheus.NewHistogramVec(
            prometheus.HistogramOpts{
                Namespace: "ad",
                Subsystem: "bid",
                Name:      "latency_seconds",
                Help:      "Bid request latency",
                Buckets:   []float64{0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0},
            },
            []string{"source"},
        ),

        bidsFailed: prometheus.NewCounterVec(
            prometheus.CounterOpts{
                Namespace: "ad",
                Subsystem: "bid",
                Name:      "failed_total",
                Help:      "Total failed bids",
            },
            []string{"reason"},
        ),

        priceDistribution: prometheus.NewHistogramVec(
            prometheus.HistogramOpts{
                Namespace: "ad",
                Subsystem: "bid",
                Name:      "price_distribution",
                Help:      "Bid price distribution",
                Buckets:   prometheus.ExponentialBuckets(0.01, 2, 10),
            },
            []string{"ad_type"},
        ),

        winRate: prometheus.NewGaugeVec(
            prometheus.GaugeOpts{
                Namespace: "ad",
                Subsystem: "bid",
                Name:      "win_rate",
                Help:      "Win rate by source",
            },
            []string{"source"},
        ),
    }
}

// Describe 实现 Collector 接口
func (e *AdBidExporter) Describe(ch chan<- *prometheus.Desc) {
    ch <- e.bidsTotal.Desc()
    ch <- e.bidsLatency.Desc()
    ch <- e.bidsFailed.Desc()
    ch <- e.priceDistribution.Desc()
    ch <- e.winRate.Desc()
}

// Collect 实现 Collector 接口
func (e *AdBidExporter) Collect(ch chan<- prometheus.Metric) {
    e.mu.Lock()
    defer e.mu.Unlock()

    e.lastCollectTime = time.Now()

    // 收集指标
    e.bidsTotal.Collect(ch)
    e.bidsLatency.Collect(ch)
    e.bidsFailed.Collect(ch)
    e.priceDistribution.Collect(ch)
    e.winRate.Collect(ch)
}

// RecordBid 记录竞价指标
func (e *AdBidExporter) RecordBid(source, adType, country string, price float64, latency time.Duration, won bool, err error) {
    e.mu.Lock()
    defer e.mu.Unlock()

    // 更新计数器
    e.bidsTotal.WithLabelValues(source, adType, country).Inc()

    // 更新延迟
    e.bidsLatency.WithLabelValues(source).Observe(latency.Seconds())

    // 更新价格分布
    e.priceDistribution.WithLabelValues(adType).Observe(price)

    // 更新成功/失败
    if won {
        e.winRate.WithLabelValues(source).Inc()
    } else if err != nil {
        e.bidsFailed.WithLabelValues(err.Error()).Inc()
    }
}
```

### 3.3 Exporter 注册与启动

```go
// cmd/exporter/main.go
package main

import (
    "flag"
    "log"
    "net/http"
    "os"
    "os/signal"
    "syscall"

    "github.com/prometheus/client_golang/prometheus"
    "github.com/prometheus/client_golang/prometheus/promhttp"
)

var (
    port = flag.Int("port", 9100, "Exporter port")
)

func main() {
    flag.Parse()

    // 创建 Exporter
    exporter := NewAdBidExporter()

    // 注册 Exporter
    prometheus.MustRegister(exporter)

    // 健康检查端点
    http.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
        w.WriteHeader(http.StatusOK)
        w.Write([]byte("OK"))
    })

    // Prometheus 指标端点
    http.Handle("/metrics", promhttp.Handler())

    // 优雅关闭
    go func() {
        sigChan := make(chan os.Signal, 1)
        signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)
        <-sigChan
        log.Println("Shutting down exporter...")
        os.Exit(0)
    }()

    log.Printf("Starting Ad Bid Exporter on :%d", *port)
    log.Fatal(http.ListenAndServe(fmt.Sprintf(":%d", *port), nil))
}
```

---

## 四、Prometheus 配置

### 4.1 scrape_configs

```yaml
# prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'ad-bid-exporter'
    static_configs:
      - targets: ['localhost:9100']
        labels:
          environment: 'production'
          team: 'ads'

  - job_name: 'node-exporter'
    static_configs:
      - targets: ['node-exporter:9100']

  - job_name: 'mysqld-exporter'
    static_configs:
      - targets: ['mysqld-exporter:9104']
```

### 4.2 服务发现

```yaml
# 基于 K8s 的服务发现
scrape_configs:
  - job_name: 'kubernetes-pods'
    kubernetes_sd_configs:
      - role: pod
    relabel_configs:
      - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_scrape]
        action: keep
        regex: true
      - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_path]
        action: replace
        target_label: __metrics_path__
        regex: (.+)
```

---

## 五、告警规则

```yaml
# alert_rules.yml
groups:
  - name: ad_bid_alerts
    rules:
      - alert: HighBidLatency
        expr: histogram_quantile(0.99, rate(ad_bid_latency_seconds_bucket[5m])) > 0.1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High bid latency detected"
          description: "P99 latency is {{ $value }}s"

      - alert: BidFailureRateHigh
        expr: rate(ad_bid_failed_total[5m]) / rate(ad_bid_total[5m]) > 0.05
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High bid failure rate"
          description: "Failure rate is {{ $value | humanizePercentage }}"
```

---

## 六、最佳实践

### 6.1 指标命名规范

```
<namespace>_<subsystem>_<name>_<unit>

示例:
  ad_bid_total              # 广告竞价总数
  ad_bid_latency_seconds    # 竞价延迟（秒）
  http_requests_total       # HTTP 请求总数
  process_cpu_seconds_total # CPU 时间（秒）
```

### 6.2 Label 使用规范

```
✅ 推荐:
  - 使用有限且固定的 label 集合
  - label 值长度适中
  - 避免高基数 label

❌ 不推荐:
  - 使用用户ID作为 label (高基数)
  - 使用 timestamp 作为 label
  - label 值过长或变化频繁
```

### 6.3 性能优化

```go
// 使用缓存避免重复计算
type CachedExporter struct {
    cache     map[string]prometheus.Metric
    cacheTime time.Time
    ttl       time.Duration
}

func (e *CachedExporter) Collect(ch chan<- prometheus.Metric) {
    if time.Since(e.cacheTime) < e.ttl {
        // 使用缓存
        for _, m := range e.cache {
            ch <- m
        }
        return
    }

    // 重新计算并缓存
    e.cache = make(map[string]prometheus.Metric)
    // ... 计算逻辑
    e.cacheTime = time.Now()
}
```

---

## 七、测试策略

### 7.1 单元测试

```go
// exporter_test.go
func TestAdBidExporter(t *testing.T) {
    exporter := NewAdBidExporter()

    // 记录指标
    exporter.RecordBid("google", "banner", "US", 1.5, 50*time.Millisecond, true, nil)

    // 收集指标
    ch := make(chan prometheus.Metric)
    go exporter.Collect(ch)

    // 验证
    metric := <-ch
    if metric == nil {
        t.Fatal("Expected metric")
    }
}
```

### 7.2 集成测试

```go
func TestExporterHTTP(t *testing.T) {
    exporter := NewAdBidExporter()
    prometheus.MustRegister(exporter)

    // 启动 HTTP server
    go http.ListenAndServe(":9101", nil)
    time.Sleep(100 * time.Millisecond)

    // 请求 metrics 端点
    resp, err := http.Get("http://localhost:9101/metrics")
    if err != nil {
        t.Fatal(err)
    }
    defer resp.Body.Close()

    // 验证响应
    if resp.StatusCode != http.StatusOK {
        t.Fatalf("Expected 200, got %d", resp.StatusCode)
    }
}
```

---

## 八、总结

| 项目 | 说明 |
|------|------|
| **核心概念** | Exporter 是 Prometheus 指标采集的桥梁 |
| **实现方式** | 实现 Collector 接口或使用 client_golang |
| **最佳实践** | 遵循命名规范、避免高基数、使用缓存 |
| **生产建议** | 健康检查端点、优雅关闭、日志记录 |

---

## 九、自测题

1. **Prometheus Exporter 的核心接口是什么？**
   - Collector 接口 (Describe + Collect)

2. **如何避免 Exporter 的指标收集性能问题？**
   - 使用缓存、避免重复计算、异步收集

3. **Label 基数过高会导致什么问题？**
   - 内存占用增加、查询性能下降、存储成本上升

4. **如何实现 Exporter 的优雅关闭？**
   - 监听 SIGTERM/SIGINT，关闭 HTTP server，等待在途请求

5. **Exporter 和健康检查端点应该如何设计？**
   - 独立的 /health 端点，/metrics 端点暴露 Prometheus 格式

EOF
echo "✅ 已创建: devops/prometheus-exporter-deep.md"