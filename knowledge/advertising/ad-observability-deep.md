# 广告系统可观测性深度：监控/日志/追踪/告警

> Prometheus + Jaeger + ELK + Grafana 在广告系统中的落地

---

## 第一部分：可观测性的三大支柱

```
监控（Metrics）：
→ 系统指标：CPU/内存/磁盘/网络
→ 业务指标：QPS/延迟/错误率/eCPM
→ 工具：Prometheus + Grafana

日志（Logs）：
→ 访问日志：API 请求/响应
→ 业务日志：竞价过程/扣费记录
→ 错误日志：异常堆栈/警告
→ 工具：ELK / Loki

追踪（Traces）：
→ 请求链路：TraceID 透传
→ 性能分析：每个 Span 耗时
→ 依赖分析：服务调用拓扑
→ 工具：Jaeger / Zipkin
```

---

## 第二部分：监控指标体系

### 2.1 系统指标

```go
package metrics

import (
    "github.com/prometheus/client_golang/prometheus"
)

// SystemMetrics 系统指标
var (
    CPUUsage = prometheus.NewGauge(prometheus.GaugeOpts{
        Name: "ad_system_cpu_usage",
        Help: "CPU 使用率",
    })
    
    MemoryUsage = prometheus.NewGauge(prometheus.GaugeOpts{
        Name: "ad_system_memory_usage",
        Help: "内存使用率",
    })
    
    GoroutineCount = prometheus.NewGauge(prometheus.GaugeOpts{
        Name: "ad_system_goroutine_count",
        Help: "Goroutine 数量",
    })
)

func init() {
    prometheus.MustRegister(CPUUsage, MemoryUsage, GoroutineCount)
}
```

### 2.2 业务指标

```go
// BusinessMetrics 业务指标
var (
    // QPS
    BidRequestCount = prometheus.NewCounter(prometheus.CounterOpts{
        Name: "ad_bid_request_total",
        Help: "竞价请求总数",
    })
    
    // 延迟
    BidLatency = prometheus.NewHistogram(prometheus.HistogramOpts{
        Name:    "ad_bid_latency_seconds",
        Help:    "竞价延迟",
        Buckets: prometheus.ExponentialBuckets(0.001, 2, 10), // 1ms - 512ms
    })
    
    // 错误率
    BidErrorCount = prometheus.NewCounterVec(
        prometheus.CounterOpts{
            Name: "ad_bid_error_total",
            Help: "竞价错误数",
        },
        []string{"error_type"}, // timeout/redis_error/db_error
    )
    
    // eCPM
    eCPMGauge = prometheus.NewGauge(prometheus.GaugeOpts{
        Name: "ad_ecpm",
        Help: "当前 eCPM",
    })
    
    // 填充率
    FillRateGauge = prometheus.NewGauge(prometheus.GaugeOpts{
        Name: "ad_fill_rate",
        Help: "填充率",
    })
)
```

### 2.3 Prometheus 配置

```yaml
# prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'ad-services'
    static_configs:
      - targets: ['bidding-service:8080', 'recall-service:8080', 'rank-service:8080']
        labels:
          env: 'production'
          
  - job_name: 'kafka'
    static_configs:
      - targets: ['kafka-exporter:9308']
      
  - job_name: 'redis'
    static_configs:
      - targets: ['redis-exporter:9121']
      
  - job_name: 'mysql'
    static_configs:
      - targets: ['mysqld-exporter:9104']
```

---

## 第三部分：日志系统

### 3.1 结构化日志

```go
package logger

import (
    "github.com/sirupsen/logrus"
)

var Log = logrus.New()

func init() {
    Log.SetFormatter(&logrus.JSONFormatter{
        TimestampFormat: "2006-01-02T15:04:05.000Z",
    })
    Log.SetLevel(logrus.InfoLevel)
}

// BidLog 竞价日志
func BidLog(traceID, userID, adID string, latency float64, eCPM float64, won bool) {
    Log.WithFields(logrus.Fields{
        "level":    "info",
        "service":  "bidding",
        "trace_id": traceID,
        "user_id":  userID,
        "ad_id":    adID,
        "latency_ms": latency,
        "ecpm":     eCPM,
        "won":      won,
        "timestamp": time.Now().UTC().Format(time.RFC3339Nano),
    }).Info("bid_result")
}
```

### 3.2 ELK 配置

```yaml
# elasticsearch mapping
{
  "mappings": {
    "properties": {
      "trace_id": { "type": "keyword" },
      "service": { "type": "keyword" },
      "level": { "type": "keyword" },
      "latency_ms": { "type": "float" },
      "timestamp": { "type": "date" }
    }
  }
}

# logstash pipeline
input {
  beats {
    port => 5044
  }
}

filter {
  if [fields][log_type] == "bidding" {
    mutate {
      add_field => { "service" => "bidding" }
    }
  }
}

output {
  elasticsearch {
    hosts => ["http://elasticsearch:9200"]
    index => "ad-logs-%{+YYYY.MM.dd}"
  }
}
```

---

## 第四部分：告警系统

### 4.1 告警规则

```yaml
# alertmanager.yml
groups:
  - name: ad-services
    rules:
      # QPS 过高
      - alert: HighQPS
        expr: rate(ad_bid_request_total[5m]) > 2000
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "竞价 QPS 过高"
          description: "当前 QPS: {{ $value }}"
          
      # 延迟 P99 > 100ms
      - alert: HighLatency
        expr: histogram_quantile(0.99, rate(ad_bid_latency_seconds_bucket[5m])) > 0.1
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "竞价延迟过高"
          
      # 错误率 > 5%
      - alert: HighErrorRate
        expr: rate(ad_bid_error_total[5m]) / rate(ad_bid_request_total[5m]) > 0.05
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "竞价错误率过高"
          
      # 填充率 < 90%
      - alert: LowFillRate
        expr: ad_fill_rate < 0.9
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "填充率过低"
```

### 4.2 告警通知

```
告警级别：
→ P0（紧急）：电话 + 短信 + 钉钉
→ P1（重要）：短信 + 钉钉
→ P2（一般）：钉钉 + 邮件
→ P3（提示）：邮件

通知渠道：
→ 钉钉机器人
→ 企业微信
→ 邮件
→ PagerDuty
```

---

## 第五部分：自测题

### 问题 1
广告系统监控哪些核心指标？

<details>
<summary>查看答案</summary>

1. **QPS**：竞价请求数
2. **延迟**：P50/P90/P99
3. **错误率**：超时/Redis错误/DB错误
4. **eCPM**：实时 eCPM
5. **填充率**：有广告展示的比例
</details>

### 问题 2
告警规则怎么设计？

<details>
<summary>查看答案</summary>

1. **QPS 过高**：> 2000，持续 2 分钟
2. **延迟 P99**：> 100ms，持续 1 分钟
3. **错误率**：> 5%，持续 2 分钟
4. **填充率**：< 90%，持续 5 分钟
5. **告警级别**：P0-P3，不同渠道通知
</details>

---

*本文档基于广告系统可观测性生产实战整理。*