# 竞价引擎监控体系完整实现

> 可观测性架构、关键指标、告警策略、故障排查
> 创建日期: 2026-08-12
> 作者: Ryan
> 定位: 资深专家级 — 竞价引擎监控

---

## 第一部分：监控架构设计

### 1.1 三层监控架构

```
┌──────────────────────────────────────────────────────────────┐
│                    监控架构分层                               │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  L1: 基础设施层 (Infrastructure)                       │   │
│  │  ├─ CPU/内存/磁盘/网络                                │   │
│  │  ├─ K8s Pod/节点状态                                   │   │
│  │  └─ 容器运行时 (containerd/docker)                    │   │
│  └──────────────────────────────────────────────────────┘   │
│                          │                                   │
│                          ▼                                   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  L2: 服务层 (Service)                                  │   │
│  │  ├─ QPS/延迟/错误率                                   │   │
│  │  ├─ 连接池/线程池状态                                  │   │
│  │  └─ 依赖服务健康度 (Redis/MySQL/Kafka)                 │   │
│  └──────────────────────────────────────────────────────┘   │
│                          │                                   │
│                          ▼                                   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  L3: 业务层 (Business)                                 │   │
│  │  ├─ 竞价成功率/出价金额                                │   │
│  │  ├─ RTA命中率/过滤率                                   │   │
│  │  ├─ 模型推理延迟/准确率                                │   │
│  │  └─ 收入/填充率/CTR                                    │   │
│  └──────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
```

### 1.2 数据采集链路

```
Exporter (Go SDK) → Collector (Fluentd) → TSDB (VictoriaMetrics)
                                              ↓
                                      Grafana Dashboard
                                              ↓
                                      Alert Manager
                                     /         \
                                   Slack      PagerDuty
```

---

## 第二部分：核心指标体系

### 2.1 基础设施指标

```go
package monitoring

import "github.com/prometheus/client_golang/prometheus"

type InfrastructureMetrics struct {
	cpuUsage       *prometheus.GaugeVec
	memoryUsage    *prometheus.GaugeVec
	gcStats        *prometheus.GaugeVec
	goroutineCount *prometheus.Gauge
}

func NewInfrastructureMetrics() *InfrastructureMetrics {
	return &InfrastructureMetrics{
		cpuUsage: prometheus.NewGaugeVec(
			prometheus.GaugeOpts{Name: "dsp_cpu_usage_percent", Help: "CPU usage"},
			[]string{"host", "pod"},
		),
		memoryUsage: prometheus.NewGaugeVec(
			prometheus.GaugeOpts{Name: "dsp_memory_usage_bytes", Help: "Memory usage"},
			[]string{"host", "pod"},
		),
		gcStats: prometheus.NewGaugeVec(
			prometheus.GaugeOpts{Name: "dsp_gc_stats", Help: "GC stats"},
			[]string{"metric"},
		),
		goroutineCount: prometheus.NewGauge(
			prometheus.GaugeOpts{Name: "dsp_goroutine_count", Help: "Goroutine count"},
		),
	}
}
```

### 2.2 服务层指标

```go
package monitoring

import "github.com/prometheus/client_golang/prometheus/promauto"

type ServiceMetrics struct {
	requestCount     *prometheus.CounterVec
	requestDuration  *prometheus.HistogramVec
	errorCount       *prometheus.CounterVec
	activeConns      *prometheus.GaugeVec
	concurrentReqs   *prometheus.Gauge
}

func NewServiceMetrics() *ServiceMetrics {
	return &ServiceMetrics{
		requestCount: promauto.NewCounterVec(
			prometheus.CounterOpts{Name: "dsp_request_total", Help: "Total requests"},
			[]string{"endpoint", "status"},
		),
		requestDuration: promauto.NewHistogramVec(
			prometheus.HistogramOpts{
				Name:    "dsp_request_duration_seconds",
				Buckets: []float64{0.001, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1.0},
			},
			[]string{"endpoint", "method"},
		),
		errorCount: promauto.NewCounterVec(
			prometheus.CounterOpts{Name: "dsp_error_total", Help: "Error count"},
			[]string{"type", "source"},
		),
		activeConns: promauto.NewGaugeVec(
			prometheus.GaugeOpts{Name: "dsp_active_connections", Help: "Active connections"},
			[]string{"service"},
		),
		concurrentReqs: promauto.NewGauge(
			prometheus.GaugeOpts{Name: "dsp_concurrent_requests", Help: "Concurrent requests"},
		),
	}
}
```

### 2.3 业务层指标

```go
package monitoring

type BusinessMetrics struct {
	bidSuccessRate     *prometheus.GaugeVec
	bidAmount          *prometheus.HistogramVec
	rtbLatency         *prometheus.HistogramVec
	rtaHitRate         *prometheus.GaugeVec
	rtaLatency         *prometheus.HistogramVec
	modelInferenceLat  *prometheus.HistogramVec
	modelAccuracy      *prometheus.GaugeVec
	revenue            *prometheus.CounterVec
	fillRate           *prometheus.GaugeVec
	ctr                *prometheus.GaugeVec
}

func NewBusinessMetrics() *BusinessMetrics {
	return &BusinessMetrics{
		bidSuccessRate: promauto.NewGaugeVec(
			prometheus.GaugeOpts{Name: "dsp_bid_success_rate", Help: "Bid success rate"},
			[]string{"campaign_id", "advertiser"},
		),
		bidAmount: promauto.NewHistogramVec(
			prometheus.HistogramOpts{
				Name:    "dsp_bid_amount",
				Buckets: []float64{0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0},
			},
			[]string{"campaign_id"},
		),
		rtbLatency: promauto.NewHistogramVec(
			prometheus.HistogramOpts{
				Name:    "dsp_rtb_latency_ms",
				Buckets: []float64{5, 10, 20, 50, 100, 200},
			},
			[]string{"ssp"},
		),
		rtaHitRate: promauto.NewGaugeVec(
			prometheus.GaugeOpts{Name: "dsp_rta_hit_rate", Help: "RTA hit rate"},
			[]string{"strategy"},
		),
		rtaLatency: promauto.NewHistogramVec(
			prometheus.HistogramOpts{
				Name:    "dsp_rta_latency_ms",
				Buckets: []float64{1, 5, 10, 20, 50},
			},
			[]string{},
		),
		modelInferenceLat: promauto.NewHistogramVec(
			prometheus.HistogramOpts{
				Name:    "dsp_model_inference_latency_ms",
				Buckets: []float64{1, 5, 10, 20, 50, 100},
			},
			[]string{"model"},
		),
		modelAccuracy: promauto.NewGaugeVec(
			prometheus.GaugeOpts{Name: "dsp_model_accuracy", Help: "Model accuracy"},
			[]string{"model"},
		),
		revenue: promauto.NewCounterVec(
			prometheus.CounterOpts{Name: "dsp_revenue", Help: "Revenue USD"},
			[]string{"campaign_id", "currency"},
		),
		fillRate: promauto.NewGaugeVec(
			prometheus.GaugeOpts{Name: "dsp_fill_rate", Help: "Fill rate"},
			[]string{"placement_id"},
		),
		ctr: promauto.NewGaugeVec(
			prometheus.GaugeOpts{Name: "dsp_ctr", Help: "Click-through rate"},
			[]string{"campaign_id"},
		),
	}
}
```

---

## 第三部分：分布式追踪

### 3.1 Trace 实现

```go
package tracing

import (
	"context"
	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/trace"
)

type Tracer struct {
	tracer trace.Tracer
}

func NewTracer(serviceName string) *Tracer {
	return &Tracer{tracer: otel.Tracer(serviceName)}
}

func (t *Tracer) StartSpan(ctx context.Context, name string) (context.Context, trace.Span) {
	return t.tracer.Start(ctx, name)
}

func (t *Tracer) RecordEvent(ctx context.Context, name string, attrs ...attribute.KeyValue) {
	span := trace.SpanFromContext(ctx)
	if span != nil {
		span.AddEvent(name, trace.WithAttributes(attrs...))
	}
}

func (t *Tracer) SetError(ctx context.Context, err error) {
	span := trace.SpanFromContext(ctx)
	if span != nil {
		span.RecordError(err)
		span.SetStatus(1, err.Error())
	}
}
```

### 3.2 竞价请求 Trace

```go
package tracing

func TraceBidRequest(ctx context.Context, req *BidRequest, tracer *Tracer) (*BidResult, error) {
	ctx, span := tracer.StartSpan(ctx, "bid_request")
	defer span.End()
	
	span.SetAttributes(
		attribute.String("request.id", req.RequestID),
		attribute.String("ssp", req.SSPID),
		attribute.Int("impressions", len(req.Impressments)),
	)
	
	// Step 1: RTA
	rtaResult, err := traceRTA(ctx, req, tracer)
	if err != nil {
		tracer.SetError(ctx, err)
		return nil, err
	}
	
	// Step 2: 规则引擎
	ruleResult, err := traceRuleEngine(ctx, req, tracer)
	if err != nil {
		tracer.SetError(ctx, err)
	}
	
	// Step 3: 模型推理
	modelResult, err := traceModelInference(ctx, req, tracer)
	if err != nil {
		tracer.SetError(ctx, err)
	}
	
	// Step 4: 出价计算
	bidResult, err := traceBidCalculation(ctx, req, ruleResult, modelResult, tracer)
	if err != nil {
		tracer.SetError(ctx, err)
		return nil, err
	}
	
	span.SetAttributes(
		attribute.Float64("bid_price", bidResult.Price),
		attribute.Bool("win", bidResult.Won),
	)
	
	return bidResult, nil
}
```

---

## 第四部分：告警策略

### 4.1 告警规则

```yaml
# config/alerts.yaml
groups:
  - name: dsp_critical
    rules:
      - alert: DSPHighErrorRate
        expr: rate(dsp_error_total[5m]) > 0.05
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "DSP 错误率过高"
          
      - alert: DSPHighLatency
        expr: histogram_quantile(0.99, rate(dsp_request_duration_seconds_bucket[5m])) > 0.1
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "DSP P99 延迟过高"
          
      - alert: DSPCircuitBreakerOpen
        expr: dsp_circuit_breaker_state == 1
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "DSP 熔断器打开"

  - name: dsp_warning
    rules:
      - alert: DSPLowBidSuccessRate
        expr: dsp_bid_success_rate < 0.8
        for: 15m
        labels:
          severity: warning
        annotations:
          summary: "DSP 竞价成功率下降"
```

### 4.2 告警分级

```
┌──────────────────────────────────────────────────────────────┐
│  Level  │  响应时间  │  通知方式              │  场景              │
├──────────────────────────────────────────────────────────────┤
│  P0     │  5 分钟    │  PagerDuty + 电话    │  系统不可用        │
│         │          │  + Slack #urgent     │  核心功能故障      │
├──────────────────────────────────────────────────────────────┤
│  P1     │  30 分钟   │  Slack #ops          │  性能下降          │
│         │          │  + 邮件               │  非核心功能异常    │
├──────────────────────────────────────────────────────────────┤
│  P2     │  4 小时    │  Slack #monitoring   │  业务指标波动      │
│         │          │  + 日报               │  容量预警          │
├──────────────────────────────────────────────────────────────┤
│  P3     │  次日     │  Slack #general      │  建议优化          │
│         │          │  + 周报               │  技术债            │
└──────────────────────────────────────────────────────────────┘
```

---

## 第五部分：故障排查指南

### 5.1 排查决策树

```
竞价延迟高
    │
    ├─ 检查 RTB 延迟
    │   ├─ SSP 响应慢 → 联系 SSP 排查
    │   └─ 网络超时 → 检查网络连接
    │
    ├─ 检查 RTA 延迟
    │   ├─ 命中率低 → 调整匹配策略
    │   └─ 查询慢 → 检查 Redis/DB
    │
    ├─ 检查模型推理
    │   ├─ 推理慢 → 检查模型服务
    │   └─ 超时 → 增加并发或降级模型
    │
    └─ 检查本地处理
        ├─ CPU 高 → 检查热点代码
        └─ 锁竞争 → 检查并发控制
```

### 5.2 常用排查命令

```bash
# 查看实时错误日志
kubectl logs -f deployment/dsp-server -n dsp --tail=100 | grep ERROR

# 检查 Pod 资源使用
kubectl top pod -l app=dsp-server -n dsp

# 查看 Prometheus 指标
curl http://prometheus:9090/api/v1/query?query=dsp_error_total

# 检查连接池状态
curl http://dsp-server:8080/metrics | grep connection_pool

# 检查熔断器状态
curl http://dsp-server:8080/health | jq '.circuit_breaker'
```

---

## 第六部分：性能基准

```
性能基准目标:

┌──────────────────────────────────────────────────────────────┐
│  指标                      │ 目标值      │ 测量方法         │
├──────────────────────────────────────────────────────────────┤
│  P50 延迟                   │ < 10ms     │ Prometheus       │
│  P95 延迟                   │ < 30ms     │ Prometheus       │
│  P99 延迟                   │ < 50ms     │ Prometheus       │
│  错误率                     │ < 0.1%     │ 监控告警         │
│  吞吐量 (QPS)               │ > 10000    │ JMeter/Locust    │
│  CPU 使用率 (单核)          │ < 80%      │ Prometheus       │
│  内存使用率                 │ < 4GB      │ Prometheus       │
│  Goroutine 数量             │ < 5000     │ pprof            │
└──────────────────────────────────────────────────────────────┘
```

---

## 第七部分：日志规范

```go
// 竞价请求开始
logger.Info("bid request received",
	zap.String("request_id", req.ID),
	zap.String("ssp", req.SSPID),
	zap.Int("impressions", len(req.Impressments)),
)

// RTA 检查完成
logger.Info("rta check completed",
	zap.String("request_id", req.ID),
	zap.Bool("hit", rtaResult.Hit),
	zap.Int64("latency_ms", rtaResult.Latency.Milliseconds()),
)

// 出价结果
logger.Info("bid response",
	zap.String("request_id", req.ID),
	zap.Float64("bid_price", bidResult.Price),
	zap.Bool("win", bidResult.Won),
	zap.Int64("total_latency_ms", totalLatency.Milliseconds()),
)
```

---

*最后更新：2026-08-12*
*作者：Ryan*
