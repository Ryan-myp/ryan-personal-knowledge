# Kubernetes集群监控与告警深度实现 - 资深专家

## 一、Prometheus监控架构

### 1.1 组件架构

```
┌─────────────────────────────────────────────────────────────┐
│                      Kubernetes Cluster                      │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │ Pod 1    │  │ Pod 2    │  │ Pod 3    │  │ Pod N    │  │
│  │ (metrics)│  │ (metrics)│  │ (metrics)│  │ (metrics)│  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  │
│       │             │             │             │         │
│       └─────────────┴──────┬──────┴─────────────┘         │
│                            │                               │
│                    ┌───────▼───────┐                      │
│                    │  kube-state-metrics │                │
│                    │  (K8s资源指标)    │                │
│                    └───────┬───────┘                      │
│                            │                               │
│       ┌────────────────────┼────────────────────┐         │
│       │                    │                    │         │
│  ┌────▼────┐         ┌────▼────┐         ┌────▼────┐     │
│  │ Prometheus│        │ Grafana │         │ Alertman- │     │
│  │ Server   │        │ Dashboard│        │ ager     │     │
│  └────┬────┘         └────┬────┘         └────┬────┘     │
│       │                   │                   │          │
│       └───────────────────┴───────────────────┘          │
│                            │                              │
│                    ┌───────▼───────┐                     │
│                    │  External      │                    │
│                    │  Storage       │                    │
│                    │  (Thanos/Cortex)│                   │
│                    └─────────────────┘                   │
└─────────────────────────────────────────────────────────────┘
```

```yaml
# Prometheus Stack部署
apiVersion: v1
kind: ConfigMap
metadata:
  name: prometheus-config
  namespace: monitoring
data:
  prometheus.yml: |
    global:
      scrape_interval: 15s
      evaluation_interval: 15s
    
    rule_files:
      - /etc/prometheus/rules/*.yml
    
    alerting:
      alertmanagers:
        - static_configs:
            - targets: ['alertmanager:9093']
    
    scrape_configs:
      - job_name: 'kubernetes-apiservers'
        kubernetes_sd_configs:
          - role: endpoints
        scheme: https
        tls_config:
          ca_file: /var/run/secrets/kubernetes.io/serviceaccount/ca.crt
        bearer_token_file: /var/run/secrets/kubernetes.io/serviceaccount/token
        
      - job_name: 'kubernetes-nodes'
        kubernetes_sd_configs:
          - role: node
        scheme: https
        tls_config:
          ca_file: /var/run/secrets/kubernetes.io/serviceaccount/ca.crt
        bearer_token_file: /var/run/secrets/kubernetes.io/serviceaccount/token
        relabel_configs:
          - action: labelmap
            regex: __meta_kubernetes_node_label_(.+)
            
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
          - source_labels: [__address__, __meta_kubernetes_pod_annotation_prometheus_io_port]
            action: replace
            regex: ([^:]+)(?::\d+)?;(\d+)
            replacement: $1:$2
            target_label: __address__
```

### 1.2 Metrics采集

```go
package metrics

import (
    "github.com/prometheus/client_golang/prometheus"
    "github.com/prometheus/client_golang/prometheus/promauto"
)

// 自定义Metrics
var (
    requestDuration = promauto.NewHistogramVec(
        prometheus.HistogramOpts{
            Name:    "http_request_duration_seconds",
            Help:    "HTTP request duration",
            Buckets: prometheus.DefBuckets,
        },
        []string{"method", "endpoint", "status"},
    )
    
    activeConnections = promauto.NewGaugeVec(
        prometheus.GaugeOpts{
            Name: "active_connections",
            Help: "Number of active connections",
        },
        []string{"service"},
    )
    
    jobQueueLength = promauto.NewGaugeVec(
        prometheus.GaugeOpts{
            Name: "job_queue_length",
            Help: "Number of jobs in queue",
        },
        []string{"queue"},
    )
)

// 中间件记录指标
func MetricsMiddleware(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        start := time.Now()
        next.ServeHTTP(w, r)
        duration := time.Since(start)
        
        requestDuration.WithLabelValues(
            r.Method,
            r.URL.Path,
            strconv.Itoa(w.(*responseRecorder).StatusCode),
        ).Observe(duration.Seconds())
    })
}

type responseRecorder struct {
    http.ResponseWriter
    statusCode int
}

func (r *responseRecorder) WriteHeader(code int) {
    r.statusCode = code
    r.ResponseWriter.WriteHeader(code)
}
```

## 二、告警规则设计

### 2.1 告警规则配置

```yaml
# alert-rules.yml
groups:
  - name: kubernetes
    rules:
      # Pod级别告警
      - alert: PodCrashLooping
        expr: rate(kube_pod_container_status_restarts_total[15m]) > 0
        for: 1h
        labels:
          severity: warning
        annotations:
          summary: "Pod {{ $labels.namespace }}/{{ $labels.pod }} is crash looping"
          description: "Pod has been restarting frequently"
          
      - alert: PodNotReady
        expr: kube_pod_status_ready{condition="true"} == 0
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Pod {{ $labels.namespace }}/{{ $labels.pod }} is not ready"
          
      # Node级别告警
      - alert: NodeDiskPressure
        expr: kube_node_status_condition{condition="DiskPressure",status="true"} == 1
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Node {{ $labels.node }} has disk pressure"
          
      - alert: NodeMemoryPressure
        expr: kube_node_status_condition{condition="MemoryPressure",status="true"} == 1
        for: 5m
        labels:
          severity: critical
          
      # 资源使用告警
      - alert: HighCPUUsage
        expr: 100 - (avg by(instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100) > 80
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "High CPU usage on {{ $labels.instance }}"
          
      - alert: HighMemoryUsage
        expr: (node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) / node_memory_MemTotal_bytes * 100 > 85
        for: 10m
        labels:
          severity: warning
          
      # 网络告警
      - alert: HighNetworkTraffic
        expr: rate(node_network_receive_bytes_total[5m]) * 8 > 1000000000  # 1Gbps
        for: 5m
        labels:
          severity: warning
```

### 2.2 告警级别定义

```go
package alerting

import "time"

type Severity string

const (
    Info     Severity = "info"
    Warning  Severity = "warning"
    Critical Severity = "critical"
    Emergency Severity = "emergency"
)

// 告警规则配置
type AlertRule struct {
    Name        string      `json:"name"`
    Expr        string      `json:"expr"`
    For         time.Duration `json:"for"`
    Labels      Labels      `json:"labels"`
    Annotations Annotations `json:"annotations"`
}

type Labels map[string]string
type Annotations map[string]string

// 告警状态
type AlertStatus struct {
    Name       string    `json:"name"`
    State      string    `json:"state"` // pending, firing, resolved
    Severity   Severity  `json:"severity"`
    Value      float64   `json:"value"`
    StartedAt  time.Time `json:"started_at"`
    Labels     Labels    `json:"labels"`
}

// 告警抑制规则
type InhibitionRule struct {
    SourceMatchers []Matcher `json:"source_matchers"`
    TargetMatchers []Matcher `json:"target_matchers"`
    Equal          []string  `json:"equal"`
}

type Matcher struct {
    Name      string `json:"name"`
    Value     string `json:"value"`
    IsRegex   bool   `json:"is_regex"`
}
```

## 三、通知通道配置

### 3.1 Alertmanager配置

```yaml
# alertmanager.yml
global:
  resolve_timeout: 5m
  smtp_smarthost: 'smtp.example.com:587'
  smtp_from: 'alertmanager@example.com'
  smtp_auth_username: 'alertmanager'
  smtp_auth_password: 'password'

route:
  group_by: ['alertname', 'namespace']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h
  receiver: 'default-receiver'
  
  routes:
    - match:
        severity: critical
      receiver: 'pagerduty-critical'
      continue: true
      
    - match:
        severity: warning
      receiver: 'slack-warnings'
      
    - match:
        namespace: kube-system
      receiver: 'platform-team'

receivers:
  - name: 'default-receiver'
    webhook_configs:
      - url: 'http://alertmanager-webhook:5001/'
        
  - name: 'pagerduty-critical'
    pagerduty_configs:
      - service_key: <pagerduty-service-key>
        
  - name: 'slack-warnings'
    slack_configs:
      - api_url: 'https://hooks.slack.com/services/xxx/yyy/zzz'
        channel: '#alerts'
        title: '{{ .CommonLabels.alertname }}'
        text: '{{ range .Alerts }}*Alert*: {{ .Annotations.summary }}{{ "\n" }}*Description*: {{ .Annotations.description }}{{ "\n" }}{{ end }}'
        
  - name: 'platform-team'
    email_configs:
      - to: 'platform@example.com'
```

### 3.2 通知模板

```html
<!-- Slack模板 -->
<div style="border-left: 4px solid {{ if eq .Status "firing" }}red{{ else }}green{{ end }}; padding-left: 10px;">
  <h3>🚨 {{ .CommonLabels.alertname }}</h3>
  <p><strong>Namespace:</strong> {{ .CommonLabels.namespace }}</p>
  <p><strong>Severity:</strong> {{ .CommonLabels.severity }}</p>
  <p><strong>Started:</strong> {{ .CommonStarts.At.Format "2006-01-02 15:04:05" }}</p>
  
  {{ range .Alerts }}
  <div style="background: #f5f5f5; padding: 10px; margin: 10px 0; border-radius: 4px;">
    <p><strong>Summary:</strong> {{ .Annotations.summary }}</p>
    <p><strong>Description:</strong> {{ .Annotations.description }}</p>
    <p><strong>Value:</strong> {{ .Value }}</p>
  </div>
  {{ end }}
  
  <p><a href="{{ .SilenceURL }}">Silence</a> | <a href="{{ .DashboardURL }}">Dashboard</a></p>
</div>
```

## 四、PromQL查询技巧

### 4.1 常用查询

```promql
rate(kube_pod_container_status_restarts_total[15m])

100 - (avg by(instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)

(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100

(1 - (node_filesystem_avail_bytes / node_filesystem_size_bytes)) * 100

rate(node_network_receive_bytes_total[5m]) * 8  # bits/s

kube_pod_status_phase{phase="Running"} == 1

kube_deployment_status_replicas_available / kube_deployment_spec_replicas

histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket[5m])) by (le, service))

sum(rate(http_requests_total[5m])) by (service)

sum(rate(http_requests_total{status=~"5.."}[5m])) by (service) / 
sum(rate(http_requests_total[5m])) by (service)
```

### 4.2 复杂查询

```promql
# 多条件组合告警
(
  kube_pod_container_status_restarts_total[15m] > 5
  and
  rate(kube_pod_container_status_restarts_total[15m]) > 0.1
)

# 同比告警
(
  rate(http_requests_total[5m])
  / on(job) group_left
  avg_over_time(rate(http_requests_total[5m])[24h ago])
) > 2

# 预测告警
predict_linear(node_filesystem_avail_bytes[1h], 3600 * 24) < 0
```

## 五、面试高频题

### Q1: Prometheus采集原理？

```
A:
1. Pull模式：Prometheus主动拉取metrics
2. Service Discovery：自动发现目标
3. Relabeling：标签重命名和过滤
4. Storage：时间序列数据库存储
```

### Q2: 如何设计告警规则？

```
A:
1. 分级：info/warning/critical
2. 去重：group_by聚合相似告警
3. 抑制：避免告警风暴
4. 路由：按severity分发到不同channel
```

### Q3: PromQL查询优化？

```
A:
1. 使用range vector避免重复计算
2. 合理使用by/group by
3. 避免高基数标签
4. 使用offset进行时间比较
```

## 六、自测题

1. 解释Prometheus架构组件
2. 如何配置告警路由？
3. 编写查询磁盘使用率超过80%的PromQL
4. 如何实现告警抑制？

---

## 参考文档

- [Prometheus官方文档](https://prometheus.io/docs/)
- [Alertmanager文档](https://prometheus.io/docs/alerting/alertmanager/)
- [Kubernetes监控指南](https://kubernetes.io/docs/concepts/cluster-administration/monitoring/)
