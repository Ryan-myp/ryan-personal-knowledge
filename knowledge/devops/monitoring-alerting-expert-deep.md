# DevOps 监控与告警 - 资深专家深度实现

## 一、监控架构设计

### 1.1 监控层次

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        监控架构分层                                       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                      应用层监控 (APM)                             │   │
│  │  • 请求追踪 (Jaeger/Tempo)                                       │   │
│  │  • 链路分析                                                      │   │
│  │  • 性能瓶颈定位                                                  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                              ↓                                          │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                      指标监控 (Metrics)                           │   │
│  │  • Prometheus + Grafana                                          │   │
│  │  • 自定义业务指标                                                  │   │
│  │  • SLI/SLO定义                                                    │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                              ↓                                          │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                      日志监控 (Logging)                           │   │
│  │  • ELK/EFK Stack                                                 │   │
│  │  • 结构化日志                                                      │   │
│  │  • 日志聚合分析                                                    │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                              ↓                                          │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                      基础设施监控                                 │   │
│  │  • Node Exporter                                                 │   │
│  │  • cAdvisor                                                      │   │
│  │  • 系统资源监控                                                  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 1.2 OpenTelemetry 集成

```go
package observability

import (
    "context"
    "go.opentelemetry.io/otel"
    "go.opentelemetry.io/otel/exporters/jaeger"
    "go.opentelemetry.io/otel/sdk/resource"
    semconv "go.opentelemetry.io/otel/semconv/v1.12.0"
)

// SetupTracer 初始化Tracer
func SetupTracer(serviceName string) error {
    // Jaeger导出器
    exporter, err := jaeger.New(jaeger.WithCollectorEndpoint(
        jaeger.WithEndpoint("http://jaeger:14268/api/traces"),
    ))
    if err != nil {
        return err
    }

    // TracerProvider
    tracerProvider := otel.TracerProvider()
    tracerProvider.RegisterSpanProcessor(
        sdktrace.NewBatchSpanProcessor(exporter),
    )
    
    // Resource
    res := resource.NewWithAttributes(
        semconv.SchemaURL,
        semconv.ServiceNameKey.String(serviceName),
        semconv.ServiceVersionKey.String("1.0.0"),
        semconv.DeploymentEnvironmentKey.String("production"),
    )
    tracerProvider = trace.NewTracerProvider(
        trace.WithResource(res),
    )
    otel.SetTracerProvider(tracerProvider)

    return nil
}

// 使用示例
tracer := otel.Tracer("bidding-service")

ctx, span := tracer.Start(ctx, "handleBid")
defer span.End()

span.SetAttributes(
    semconv.HTTPMethodKey.String("POST"),
    semconv.HTTPTargetKey.String("/api/v1/bid"),
)

// 业务逻辑
result, err := processBid(ctx, req)
if err != nil {
    span.RecordError(err)
    span.SetStatus(codes.Error, err.Error())
}

return result, err
```

---

## 二、告警系统设计

### 2.1 告警规则配置

```yaml
# alerting_rules.yml
groups:
  - name: bidding_alerts
    rules:
      - alert: HighBidLatency
        expr: histogram_quantile(0.99, rate(bidding_latency_ms_bucket[5m])) > 100
        for: 5m
        labels:
          severity: warning
          team: bidding
        annotations:
          summary: "竞价延迟P99过高"
          description: "当前值 {{ $value }}ms，阈值100ms"
          runbook_url: "https://wiki.example.com/runbooks/bid-latency"
      
      - alert: BidSuccessRateLow
        expr: rate(bidding_success_total[5m]) / rate(bidding_request_total[5m]) < 0.95
        for: 10m
        labels:
          severity: critical
          team: bidding
        annotations:
          summary: "竞价成功率过低"
          description: "当前成功率 {{ $value | humanizePercentage }}"
      
      - alert: CTRPredictionDrift
        expr: abs(ctr_prediction_error_mean) > 0.1
        for: 30m
        labels:
          severity: warning
          team: ml
        annotations:
          summary: "CTR预测偏差过大"
          description: "预测误差 {{ $value }}"

  - name: infrastructure_alerts
    rules:
      - alert: HighCPUUsage
        expr: 100 - (avg by(instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100) > 80
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "CPU使用率过高"
          description: "{{ $labels.instance }} CPU使用率 {{ $value }}%"
      
      - alert: DiskSpaceLow
        expr: (node_filesystem_avail_bytes / node_filesystem_size_bytes) * 100 < 20
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "磁盘空间不足"
          description: "{{ $labels.instance }} 剩余空间 {{ $value | humanizePercentage }}"
```

### 2.2 告警通知策略

```go
package alerting

import (
    "context"
    "time"
)

// NotificationChannel 通知渠道
type NotificationChannel interface {
    Send(ctx context.Context, alert Alert) error
}

// AlertPipeline 告警处理管道
type AlertPipeline struct {
    channels []NotificationChannel
    dedup    *Deduplication
    throttle *Throttler
}

// Alert 告警结构
type Alert struct {
    ID          string    `json:"id"`
    Rule        string    `json:"rule"`
    Severity    string    `json:"severity"`
    Value       float64   `json:"value"`
    Labels      map[string]string `json:"labels"`
    Annotations map[string]string     `json:"annotations"`
    StartsAt    time.Time               `json:"starts_at"`
    EndsAt      time.Time               `json:"ends_at"`
}

// Send 发送告警
func (p *AlertPipeline) Send(ctx context.Context, alert Alert) error {
    // 1. 去重检查
    if p.dedup.IsDuplicate(alert) {
        return nil
    }
    
    // 2. 限流检查
    if !p.throttle.Allow(alert) {
        return nil
    }
    
    // 3. 根据 severity 选择渠道
    var channels []NotificationChannel
    switch alert.Severity {
    case "critical":
        channels = []NotificationChannel{
            &SlackNotifier{},
            &PagerDutyNotifier{},
            &SMSNotifier{},
        }
    case "warning":
        channels = []NotificationChannel{
            &SlackNotifier{},
            &EmailNotifier{},
        }
    default:
        channels = []NotificationChannel{
            &SlackNotifier{},
        }
    }
    
    // 4. 并发发送
    var wg sync.WaitGroup
    for _, ch := range channels {
        wg.Add(1)
        go func(c NotificationChannel) {
            defer wg.Done()
            if err := c.Send(ctx, alert); err != nil {
                log.Errorf("Failed to send alert: %v", err)
            }
        }(ch)
    }
    wg.Wait()
    
    return nil
}
```

---

## 三、SLO/SLI 定义

### 3.1 SLO 设计原则

```
SLO = Service Level Objective（服务等级目标）
SLI = Service Level Indicator（服务等级指标）
SLA = Service Level Agreement（服务等级协议）

关系：
• SLI 是实际测量的指标
• SLO 是基于 SLI 设定的目标
• SLA 是与用户承诺的法律协议
```

### 3.2 错误预算计算

```go
package slo

import (
    "time"
)

// ErrorBudget 错误预算
type ErrorBudget struct {
    totalBudget    float64  // 总预算（如99.9%可用性=0.1%错误预算）
    usedBudget     float64  // 已使用预算
    window         time.Duration // 评估窗口
}

// Calculate 计算当前错误预算
func (eb *ErrorBudget) Calculate(succeeded, total int64) float64 {
    errorRate := float64(total-succeeded) / float64(total)
    eb.usedBudget += errorRate
    
    return eb.totalBudget - eb.usedBudget
}

// IsExhausted 检查预算是否耗尽
func (eb *ErrorBudget) IsExhausted() bool {
    return eb.usedBudget >= eb.totalBudget
}

// 示例：可用性SLO 99.9%
const AvailabilitySLO = 99.9  // 目标99.9%可用性
const ErrorBudget = 100 - AvailabilitySLO  // 0.1%错误预算

// 月度错误预算
monthlyRequests := 1000000  // 假设月请求量
maxErrors := int64(monthlyRequests * ErrorBudget / 100)  // 最多允许1000个错误
```

---

## 四、日志系统设计

### 4.1 结构化日志

```go
package logging

import (
    "go.uber.org/zap"
    "go.uber.org/zap/zapcore"
)

// Logger 结构化日志器
type Logger struct {
    logger *zap.Logger
}

func NewLogger() *Logger {
    config := zap.NewProductionConfig()
    config.EncoderConfig.TimeKey = "timestamp"
    config.EncoderConfig.EncodeTime = zapcore.ISO8601TimeEncoder
    
    logger, _ := config.Build()
    return &Logger{logger: logger}
}

// 使用示例
func (l *Logger) Info(msg string, fields ...zap.Field) {
    l.logger.Info(msg, fields...)
}

func (l *Logger) Error(msg string, err error, fields ...zap.Field) {
    fields = append(fields, zap.Error(err))
    l.logger.Error(msg, fields...)
}

// 业务日志
l.Info("bid handled",
    zap.String("request_id", req.ID),
    zap.String("user_id", req.UserID),
    zap.Float64("bid_price", bidPrice),
    zap.Bool("is_win", isWin),
    zap.Duration("latency", latency),
)
```

### 4.2 日志采集与聚合

```yaml
# fluentd config
<source>
  @type forward
  port 24224
  bind 0.0.0.0
</source>

<match **>
  @type elasticsearch
  host elasticsearch
  port 9200
  index_name bidding-logs
  type_name _doc
  logstash_format true
  logstash_prefix bidding
  <buffer>
    @type memory
    flush_interval 5s
  </buffer>
</match>
```

---

## 五、故障排查手册

### 5.1 常见问题排查

| 现象 | 可能原因 | 排查步骤 | 解决方案 |
|------|---------|---------|---------|
| CPU突增 | goroutine泄漏/死循环 | 1. pprof分析<br>2. 查看goroutine数 | 修复泄漏点 |
| 内存OOM | 大对象未释放 | 1. heap profile<br>2. 分析分配热点 | 优化对象生命周期 |
| GC暂停 | 堆内存压力大 | 1. GC统计<br>2. 调整GOGC | 调整参数或减少分配 |
| 连接泄漏 | DB/Redis连接未关闭 | 1. netstat查看<br>2. 连接池监控 | 修复连接管理 |

### 5.2 排查工具链

```bash
#!/bin/bash
# diagnose.sh

echo "=== 系统诊断 ==="

# 1. 系统资源
echo "【CPU】"
top -bn1 | head -10

echo "【内存】"
free -h

echo "【磁盘】"
df -h

echo "【网络】"
netstat -an | grep ESTABLISHED | wc -l

# 2. Go 诊断
echo "【Goroutine】"
curl -s http://localhost:6060/debug/pprof/goroutine?debug=2 | head -50

echo "【Heap】"
go tool pprof http://localhost:6060/debug/pprof/heap

echo "【Block】"
go tool pprof http://localhost:6060/debug/pprof/block

# 3. Kubernetes
echo "【Pod状态】"
kubectl get pods -A -o wide

echo "【Pod日志】"
kubectl logs -f <pod-name> -n <namespace>

echo "【Events】"
kubectl get events -A --sort-by='.lastTimestamp'
```

---

## 六、自测题

### 6.1 基础题

1. 解释Prometheus的拉取模型和推送模型的区别
2. Jaeger和Zipkin各有什么优缺点？
3. 如何设计一个高可用的日志采集系统？

### 6.2 进阶题

1. 设计一个分布式 tracing 系统：
   - 如何生成和传播 trace ID？
   - 如何处理跨服务调用？
   - 如何存储和查询 trace 数据？

2. 如何实现告警的降噪和去重：
   - 告警风暴如何避免？
   - 关联告警如何聚合？
   - 告警升级策略如何设计？

3. SRE 实战案例：
   - 线上服务延迟突增如何排查？
   - 数据库连接池耗尽如何处理？
   - Redis 集群脑裂如何应对？

---

## 参考文档

- [Site Reliability Engineering](https://sre.info/)
- [Google SLO Book](https://landing.google.com/sre/book/)
- [Prometheus Documentation](https://prometheus.io/docs/)
