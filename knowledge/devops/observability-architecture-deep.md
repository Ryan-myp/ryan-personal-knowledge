# 微服务可观测性架构深度实现

## 一、可观测性三支柱

### 1.1 Metrics (指标)

```go
// Prometheus客户端实现
type MetricsCollector struct {
    Registry *prometheus.Registry
}

// Counter：计数器
var RequestCount = prometheus.NewCounterVec(
    prometheus.CounterOpts{
        Name: "http_requests_total",
        Help: "Total HTTP requests",
    },
    []string{"method", "path", "status"},
)

// Gauge：仪表盘
var ActiveUsers = prometheus.NewGauge(
    prometheus.GaugeOpts{
        Name: "active_users",
        Help: "Current active users",
    },
)

// Histogram：直方图
var RequestDuration = prometheus.NewHistogram(
    prometheus.HistogramOpts{
        Name:    "http_request_duration_seconds",
        Help:    "HTTP request duration",
        Buckets: []float64{0.1, 0.5, 1, 5, 10},
    },
)

// Summary：摘要
var OrderProcessingTime = prometheus.NewSummary(
    prometheus.SummaryOpts{
        Name: "order_processing_time_seconds",
        Help: "Order processing time",
    },
)
```

### 1.2 Logs (日志)

```go
// 结构化日志实现
type StructuredLogger struct {
    logger *zap.Logger
}

func (l *StructuredLogger) Info(msg string, fields ...zap.Field) {
    l.logger.Info(msg, fields...)
}

// 日志采集
type LogCollector struct {
    Input    LogInput
    Filter   LogFilter
    Output   LogOutput
}

// Fluentd配置示例
// <source>
//   @type tail
//   path /var/log/app/*.log
//   pos_file /tmp/app.log.pos
//   tag app.*
//   <parse>
//     @type json
//   </parse>
// </source>
```

### 1.3 Traces (链路追踪)

```go
// OpenTelemetry Trace
import go.uber.org/zap
import "go.opentelemetry.io/otel"
import "go.opentelemetry.io/otel/trace"

type TraceService struct {
    tracer trace.Tracer
}

func (s *TraceService) ProcessOrder(ctx context.Context, orderID string) error {
    ctx, span := s.tracer.Start(ctx, "process-order")
    defer span.End()
    
    span.SetAttributes(
        attribute.String("order.id", orderID),
        attribute.Int("order.amount", 100),
    )
    
    // 业务逻辑
    return nil
}

// Trace采样策略
type SamplingStrategy struct {
    AlwaysOn    bool
    AlwaysOff   bool
    ParentBased trace.Sampler
    RateLimit   float64
}
```

## 二、Prometheus监控架构

### 2.1 组件架构

```go
// Prometheus监控组件
type PrometheusStack struct {
    Server       *PrometheusServer
    Alertmanager *Alertmanager
    Pushgateway  *Pushgateway
    Exporters    map[string]*Exporter
}

// Prometheus配置
type PrometheusConfig struct {
    Global     GlobalConfig
    ScrapeConfigs []ScrapeConfig
    RuleFiles  []string
    Alerting   AlertingConfig
}

type ScrapeConfig struct {
    JobName       string
    StaticConfigs []StaticConfig
    MetricsPath   string
    ScrapeInterval string
    Labels        map[string]string
}
```

### 2.2 Exporter实现

```go
// 自定义Exporter
type CustomExporter struct {
    registry *prometheus.Registry
}

func (e *CustomExporter) Describe(ch chan<- *prometheus.Desc) {
    ch <- prometheus.NewDesc(
        "custom_metric",
        "Custom metric description",
        nil,
        nil,
    )
}

func (e *CustomExporter) Collect(ch chan<- prometheus.Metric) {
    value := e.getMetricValue()
    ch <- prometheus.MustNewConstMetric(
        prometheus.NewDesc("custom_metric", "...", nil, nil),
        prometheus.GaugeValue,
        value,
    )
}

// Node Exporter
// - 系统指标：CPU、内存、磁盘、网络
// - 应用指标：Go runtime、进程状态
```

## 三、告警规则设计

### 3.1 告警规则

```yaml
# alert_rules.yml
groups:
  - name: service_alerts
    rules:
      - alert: HighErrorRate
        expr: rate(http_requests_errors_total[5m]) / rate(http_requests_total[5m]) > 0.05
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High error rate on {{ $labels.service }}"
          description: "Error rate is {{ $value | humanizePercentage }}"

      - alert: HighLatency
        expr: histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m])) > 1
        for: 10m
        labels:
          severity: critical
        annotations:
          summary: "High latency detected"

      - alert: InstanceDown
        expr: up == 0
        for: 1m
        labels:
          severity: critical
```

### 3.2 告警分级

```go
// 告警级别定义
type AlertSeverity string

const (
    SeverityInfo     AlertSeverity = "info"
    SeverityWarning  AlertSeverity = "warning"
    SeverityCritical AlertSeverity = "critical"
)

// 告警通知渠道
type AlertChannel struct {
    Type       string // email, slack, webhook, pagerduty
    Target     string
    RateLimit  time.Duration
    Conditions []string
}
```

## 四、面试高频题

### Q1: 如何设计监控指标体系？

```
A:
1. USE方法 (Utilization, Saturation, Errors)
2. RED方法 (Rate, Errors, Duration)
3. 黄金信号 (Latency, Traffic, Errors, Saturation)
```

### Q2: Prometheus如何采集指标？

```
A:
1. Pull模式：服务端主动拉取
2. Push模式：客户端主动推送
3. 配置Scrape Job
4. 服务发现自动发现目标
```

### Q3: 如何设计告警规则？

```
A:
1. 分层设计：系统层、应用层、业务层
2. 分级告警：info, warning, critical
3. 防抖动处理：for duration
4. 告警收敛：相同告警合并
```

## 五、自测题

1. 解释Metrics/Logs/Traces的区别
2. 如何实现自定义Exporter？
3. 告警规则如何设计？

---

## 参考文档

- [Prometheus Documentation](https://prometheus.io/docs/)
- [OpenTelemetry](https://opentelemetry.io/)
- [Observability Engineering](https://observable.com/)
