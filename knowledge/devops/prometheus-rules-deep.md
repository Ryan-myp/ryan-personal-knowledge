# Prometheus告警规则设计 - 资深专家深度实现

## 一、规则架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    Prometheus Rules架构                                   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   Rule Group    │  Rule        │  Type        │  Evaluation            │
│   ──────────────┼──────────────┼──────────────┼───────────────────────│
│   infrastructure│  HighCPU     │  Alert       │  每15s                │
│   ──────────────┼──────────────┼──────────────┼───────────────────────│
│   application   │  ErrorRate   │  Alert       │  每15s                │
│   ──────────────┼──────────────┼──────────────┼───────────────────────│
│   business      │  Revenue     │  Recording   │  每30s                │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、告警规则完整配置

### 2.1 基础告警规则

```yaml
groups:
  - name: infrastructure
    interval: 15s  # 评估间隔
    rules:
      # CPU使用率告警
      - alert: HighCPUUsage
        expr: |
          100 - (avg by(instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100) > 80
        for: 5m
        labels:
          severity: warning
          team: infra
        annotations:
          summary: "高CPU使用率 - {{ $labels.instance }}"
          description: |
            实例 {{ $labels.instance }} 的CPU使用率超过80%
            当前值: {{ $value }}%
            持续时间: 5分钟
          runbook_url: "https://wiki.example.com/runbooks/high-cpu"
          
      # 内存告警
      - alert: HighMemoryUsage
        expr: |
          (1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100 > 85
        for: 10m
        labels:
          severity: critical
          team: infra
        annotations:
          summary: "高内存使用率 - {{ $labels.instance }}"
          description: "当前内存使用率: {{ $value }}%"
          
      # 磁盘告警
      - alert: DiskSpaceLow
        expr: |
          (1 - (node_filesystem_avail_bytes / node_filesystem_size_bytes)) * 100 > 90
        for: 15m
        labels:
          severity: critical
        annotations:
          summary: "磁盘空间不足 - {{ $labels.instance }}:{{ $labels.mountpoint }}"
          description: "磁盘使用率: {{ $value }}%"
```

### 2.2 应用层告警规则

```yaml
  - name: application
    rules:
      # HTTP错误率告警
      - alert: HighErrorRate
        expr: |
          sum(rate(http_requests_total{status=~"5.."}[5m])) 
          / sum(rate(http_requests_total[5m])) > 0.05
        for: 5m
        labels:
          severity: critical
          team: backend
        annotations:
          summary: "高HTTP错误率"
          description: "错误率: {{ $value | humanizePercentage }}"
          
      # API延迟告警
      - alert: HighAPILatency
        expr: |
          histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket[5m])) 
          by (le, service)) > 2
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "API P99延迟过高 - {{ $labels.service }}"
          description: "P99延迟: {{ $value }}s"
          
      # 服务不可用
      - alert: ServiceDown
        expr: up == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "服务不可用 - {{ $labels.job }}"
          description: "{{ $labels.instance }} 已下线超过1分钟"
```

### 2.3 业务层告警规则

```yaml
  - name: business
    rules:
      # 订单失败率
      - alert: OrderFailureRate
        expr: |
          sum(rate(order_failures_total[5m])) 
          / sum(rate(orders_total[5m])) > 0.02
        for: 10m
        labels:
          severity: critical
          team: business
        annotations:
          summary: "订单失败率过高"
          description: "失败率: {{ $value | humanizePercentage }}"
          
      # 支付超时
      - alert: PaymentTimeout
        expr: |
          sum(rate(payment_timeout_total[5m])) > 10
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "支付超时过多"
          description: "5分钟内超时次数: {{ $value }}"
```

## 三、Recording Rules（记录规则）

### 3.1 预计算常用指标

```yaml
  - name: recording_rules
    rules:
      # 请求速率预计算
      - record: job:http_requests_total:rate5m
        expr: sum(rate(http_requests_total[5m])) by (job)
        
      # 错误率预计算
      - record: job:http_error_rate:ratio5m
        expr: |
          sum(rate(http_requests_total{status=~"5.."}[5m])) by (job)
          / sum(rate(http_requests_total[5m])) by (job)
          
      # CPU利用率预计算
      - record: instance:cpu_utilization:ratio
        expr: |
          1 - avg by(instance) (rate(node_cpu_seconds_total{mode="idle"}[5m]))
          
      # 内存利用率
      - record: instance:memory_utilization:ratio
        expr: |
          1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)
          
      # QPS聚合
      - record: job:http_qps:rate1m
        expr: sum(rate(http_requests_total[1m])) by (job, endpoint)
```

### 3.2 复杂聚合规则

```yaml
  - name: advanced_recording
    rules:
      # 多指标关联计算
      - record: app:latency_cost_ratio
        expr: |
          histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m]))
          / sum(rate(http_requests_total[5m]))
          
      # 业务指标聚合
      - record: business:daily_revenue
        expr: |
          sum(rate(revenue_total[24h])) by (business_line)
          
      # 资源效率指标
      - record: infra:cost_per_request
        expr: |
          sum(rate(infra_cost_total[1h])) 
          / sum(rate(http_requests_total[1h]))
```

## 四、告警分级策略

### 4.1 严重程度定义

```yaml
severity_levels:
  critical:
    response_time: "5分钟"
    channels: ["pagerduty", "sms", "phone"]
    escalation: "5分钟无响应升级至总监"
    
  warning:
    response_time: "30分钟"
    channels: ["slack", "email"]
    escalation: "2小时无响应升级"
    
  info:
    response_time: "4小时"
    channels: ["email"]
    escalation: "无"
```

### 4.2 告警抑制规则

```yaml
# alertmanager.yml
 inhibit_rules:
   # 主机宕机时抑制该主机上的所有告警
   - source_match:
       severity: "critical"
       alertname: "InstanceDown"
     target_match:
       severity: "warning"
     equal: ["instance"]
     
   # 数据中心故障时抑制单个服务器告警
   - source_match:
       alertname: "DatacenterDown"
     target_match:
       alertname: ".*"
     equal: ["datacenter"]
```

### 4.3 告警静默规则

```yaml
# 维护窗口静默
silences:
  - matchers:
      - name: instance
        value: "prod-web-01|prod-web-02"
        isRegex: true
    startsAt: "2024-01-15T02:00:00Z"
    endsAt: "2024-01-15T06:00:00Z"
    comment: "计划内维护"
```

## 五、生产环境最佳实践

### 5.1 告警数量控制

```
原则：告警数量 ≤ 指标数量的 10%

示例：
├── 监控指标: 1000个
├── 告警规则: ≤ 100个
└── 实际配置: 85个（8.5%）
```

### 5.2 避免告警风暴

```yaml
# 使用for子句避免瞬时波动
- alert: HighMemory
  expr: memory_usage > 90
  for: 10m  # 持续10分钟才告警
  
# 使用 aggregation 避免单点故障误报
- alert: ServiceDown
  expr: |
    count by(service) (up == 0) > 2  # 至少2个实例失败
  
# 使用 severity 分级处理
labels:
  severity: "{{ if gt $value 95 }}critical{{ else }}warning{{ end }}"
```

### 5.3 告警模板标准化

```go
// 告警消息模板
const AlertTemplate = `
🚨 {{ .Alertname }}
━━━━━━━━━━━━━━━━━━━
📍 实例: {{ .Labels.instance }}
🏢 服务: {{ .Labels.service }}
📊 当前值: {{ .Values.value }}
⏰ 持续时间: {{ .Annotations.for }}

📋 描述:
{{ .Annotations.description }}

🔗 Runbook: {{ .Annotations.runbook_url }}
`
```

## 六、面试高频题

### Q1: 如何设计有效的告警规则？

```
A:
1. 基于SLO设定阈值
2. 使用for子句避免瞬时波动
3. 分级告警（critical/warning/info）
4. 设置抑制规则避免风暴
5. 提供runbook链接
```

### Q2: Recording Rule有什么用？

```
A:
1. 预计算复杂查询，提升性能
2. 简化告警规则表达式
3. 支持跨指标计算
4. 减少Prometheus实时计算压力
```

### Q3: 如何处理告警疲劳？

```
A:
1. 控制告警数量（<10%指标数）
2. 使用抑制规则
3. 分级处理（不同severity不同渠道）
4. 定期审查无效告警
5. 提供明确的runbook
```

## 七、自测题

1. 告警规则有哪些类型？
2. 如何避免告警风暴？
3. Recording Rule的应用场景？

---

## 参考文档

- [Prometheus Rules文档](https://prometheus.io/docs/prometheus/latest/configuration/recording_rules/)
- [Alertmanager配置](https://prometheus.io/docs/alerting/latest/configuration/)
- [告警最佳实践](https://prometheus.io/docs/practices/alerting/)
