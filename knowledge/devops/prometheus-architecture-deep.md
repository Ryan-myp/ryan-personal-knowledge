# Prometheus监控架构 - 资深专家深度实现

## 一、架构设计

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      Prometheus监控架构                                   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   ┌──────────────┐     ┌──────────────┐     ┌──────────────┐          │
│   │  Application │────▶│  Exporter    │────▶│ Prometheus   │          │
│   │              │     │              │     │              │          │
│   │ • HTTP应用   │     │ • node_exporter│   │ • TSDB存储   │          │
│   │ • 数据库     │     │ • mysql_exporter│  │ • 查询引擎   │          │
│   │ • 消息队列   │     │ • redis_exporter│  │ • 告警规则   │          │
│   └──────────────┘     └──────────────┘     └──────┬───────┘          │
│                                                      │                  │
│                                              ┌───────▼───────┐        │
│                                              │  Alertmanager │        │
│                                              │   (告警路由)   │        │
│                                              └───────┬───────┘        │
│                                                      │                  │
│                                              ┌───────▼───────┐        │
│                                              │  Grafana      │        │
│                                              │   (可视化)     │        │
│                                              └───────────────┘        │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、核心概念

### 2.1 Metric类型

```go
package prometheus

// Counter: 累加器
type Counter struct {
    value float64
}

func (c *Counter) Inc() { c.value++ }
func (c *Counter) Add(v float64) { c.value += v }

// Gauge: 可增可减
type Gauge struct {
    value float64
}

func (g *Gauge) Set(v float64) { g.value = v }
func (g *Gauge) Inc() { g.value++ }
func (g *Gauge) Dec() { g.value-- }

// Histogram: 直方图
type Histogram struct {
    buckets  map[float64]int
    sum      float64
    count    uint64
}

func (h *Histogram) Observe(v float64) {
    h.sum += v
    h.count++
    for bucket := range h.buckets {
        if v <= bucket {
            h.buckets[bucket]++
        }
    }
}

// Summary: 分位数统计
type Summary struct {
    quantiles map[float64]float64
}
```

### 2.2 服务发现

```yaml
# prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

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
      
  - job_name: 'kubernetes-nodes'
    kubernetes_sd_configs:
    - role: node
    
    tls_config:
      ca_file: /var/run/secrets/kubernetes.io/serviceaccount/ca.crt
    bearer_token_file: /var/run/secrets/kubernetes.io/serviceaccount/token
```

## 三、PromQL查询

```promql
# 请求速率
rate(http_requests_total[5m])

# 99分位延迟
histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m]))

# 错误率
sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m]))

# 内存使用率
(node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes) * 100

# 容器CPU使用率
container_cpu_usage_seconds_total / time()
```

## 四、告警规则

```yaml
groups:
- name: example
  rules:
  - alert: HighCPUUsage
    expr: process_cpu_seconds_total > 0.8
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "High CPU usage detected"
      description: "CPU usage is above 80% for {{ $value }} seconds"
      
  - alert: HighErrorRate
    expr: |
      sum(rate(http_requests_total{status=~"5.."}[5m])) 
      / sum(rate(http_requests_total[5m])) > 0.05
    for: 10m
    labels:
      severity: critical
    annotations:
      summary: "High error rate"
```

## 五、面试高频题

### Q1: Prometheus如何解决远程存储问题？

```
A: 使用Thanos/Cortex/VictoriaMetrics作为远程存储，支持长期存储和查询
```

### Q2: 如何优化Prometheus查询性能？

```
A:
• 避免在高基数指标上使用正则匹配
• 使用预聚合指标
• 合理设置retention
```

## 六、自测题

1. Counter和Gauge有什么区别？
2. 如何设计一个自定义Exporter？
3. PromQL的 aggregation 操作有哪些？

---

## 参考文档

- [Prometheus官方文档](https://prometheus.io/docs/)
- [Thanos项目](https://thanos.io/)
