# Grafana 仪表盘设计与告警实战

> Prometheus 查询语言 PromQL/Grafana 仪表盘/告警规则/通知通道

---

## 第一部分：入门引导（5 分钟速览）

### 为什么需要 Grafana？

```
Prometheus 采集指标
    ↓
Grafana 可视化仪表盘
    ↓
告警规则 → 通知通道
```

| 组件 | 作用 |
|------|------|
| Prometheus | 指标采集+存储 |
| Grafana | 可视化+告警 |
| Alertmanager | 告警路由+去重 |
| Loki | 日志聚合 |

---

## 第二部分：PromQL 深度

### 2.1 基础查询

```promql
# 请求速率
rate(http_requests_total[5m])

# 延迟 P99
histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m]))

# 错误率
sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m]))

# 活跃连接
up

# 内存使用
process_resident_memory_bytes{job="bidding-service"}
```

### 2.2 广告平台 PromQL 实战

```promql
# 竞价延迟分布
histogram_quantile(0.95, rate(bid_latency_seconds_bucket{service="bidding"}[5m]))

# 各 DSP 竞价成功率
sum(rate(bid_success_total{service="bidding"}[5m])) by (dsp) / sum(rate(bid_total{service="bidding"}[5m])) by (dsp)

# 预算消耗速率
rate(campaign_budget_spent_total{service="campaign"}[1h])

# 用户画像缓存命中率
sum(rate(user_profile_cache_hits_total[5m])) / sum(rate(user_profile_cache_requests_total[5m]))

# 广告曝光速率
sum(rate(ad_impression_total[5m])) by (slot)

# 点击率
sum(rate(ad_click_total[5m])) / sum(rate(ad_impression_total[5m]))

# 转化率
sum(rate(conversion_total[5m])) / sum(rate(ad_click_total[5m]))

# 每秒处理消息数
sum(rate(kafka_consumer_records_consumed_total[5m])) by (group)

# Kafka 消费延迟
kafka_consumer_current_offset - kafka_consumer_lag
```

### 2.3 聚合函数

```promql
# 按服务聚合
sum by (service) (rate(http_requests_total[5m]))

# 按状态码聚合
sum by (status) (rate(http_requests_total[5m]))

# 分位数聚合
quantile(0.99, http_request_duration_seconds)

# 比率计算
sum(rate(error_total[5m])) / sum(rate(request_total[5m]))

# 时间窗口
avg_over_time(process_cpu_seconds_total[1h])

# 增量计算
increase(http_requests_total[1h])
```

---

## 第三部分：Grafana 仪表盘

### 3.1 仪表盘结构

```
┌─────────────────────────────────────────────────────┐
│                    广告平台监控                        │
├─────────────────────────────────────────────────────┤
│  [概览] [竞价] [预算] [用户] [基础设施]              │
├─────────────────────────────────────────────────────┤
│                                                      │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐   │
│  │ QPS         │ │ P99延迟     │ │ 错误率      │   │
│  │ (时间线)    │ │ (时间线)    │ │ (仪表)      │   │
│  └─────────────┘ └─────────────┘ └─────────────┘   │
│                                                      │
│  ┌─────────────────────────────────────────────────┐│
│  │ 竞价成功率趋势                                   ││
│  │ (多线图)                                        ││
│  └─────────────────────────────────────────────────┘│
│                                                      │
│  ┌─────────────┐ ┌─────────────┐                    │
│  │ 预算消耗    │ │ 曝光/点击   │                    │
│  │ (柱状图)    │ │ (面积图)    │                    │
│  └─────────────┘ └─────────────┘                    │
│                                                      │
└─────────────────────────────────────────────────────┘
```

### 3.2 Go 集成 Grafana

```go
package grafana

import (
    "fmt"
    "time"
)

// Dashboard JSON 生成
func GenerateBiddingDashboard() map[string]interface{} {
    dashboard := map[string]interface{}{
        "title": "广告竞价监控",
        "uid":   "bidding-monitor",
        "timezone": "browser",
        "refresh": "10s",
        "panels": []map[string]interface{}{
            {
                "title": "QPS",
                "type": "timeseries",
                "datasource": "Prometheus",
                "targets": []map[string]interface{}{
                    {
                        "expr": "sum(rate(bid_total[5m]))",
                        "legendFormat": "QPS",
                    },
                },
                "gridPos": map[string]interface{}{
                    "h": 8,
                    "w": 12,
                    "x": 0,
                    "y": 0,
                },
            },
            {
                "title": "P99 延迟",
                "type": "timeseries",
                "datasource": "Prometheus",
                "targets": []map[string]interface{}{
                    {
                        "expr": "histogram_quantile(0.99, rate(bid_latency_seconds_bucket[5m]))",
                        "legendFormat": "P99",
                    },
                },
                "gridPos": map[string]interface{}{
                    "h": 8,
                    "w": 12,
                    "x": 12,
                    "y": 0,
                },
            },
        },
        "templating": map[string]interface{}{
            "list": []map[string]interface{}{
                {
                    "name": "service",
                    "type": "query",
                    "query": "label_values(bid_total, service)",
                },
            },
        },
    }
    
    return dashboard
}

// 通过 API 创建仪表盘
func CreateDashboard(grafanaURL, apiKey string, dashboard map[string]interface{}) error {
    body, _ := json.Marshal(dashboard)
    
    resp, err := http.Post(
        fmt.Sprintf("%s/api/dashboards/db", grafanaURL),
        "application/json",
        bytes.NewBuffer(body),
    )
    if err != nil {
        return err
    }
    defer resp.Body.Close()
    
    if resp.StatusCode != http.StatusOK {
        return fmt.Errorf("failed to create dashboard: %s", resp.Status)
    }
    
    return nil
}
```

---

## 第四部分：告警规则

### 4.1 告警规则定义

```yaml
groups:
  - name: bidding-alerts
    interval: 30s
    rules:
      # P99 延迟过高
      - alert: HighBidLatency
        expr: histogram_quantile(0.99, rate(bid_latency_seconds_bucket[5m])) > 0.1
        for: 5m
        labels:
          severity: warning
          team: bidding
        annotations:
          summary: "竞价延迟 P99 > 100ms"
          description: "当前值: {{ $value }}s"
          runbook_url: "https://wiki/bid-latency"
      
      # 错误率过高
      - alert: HighErrorRate
        expr: |
          sum(rate(http_requests_total{status=~"5.."}[5m])) 
          / sum(rate(http_requests_total[5m])) > 0.05
        for: 5m
        labels:
          severity: critical
          team: bidding
        annotations:
          summary: "错误率 > 5%"
      
      # QPS 过低
      - alert: LowQPS
        expr: sum(rate(bid_total[5m])) < 1000
        for: 10m
        labels:
          severity: warning
          team: bidding
        annotations:
          summary: "QPS < 1000"
      
      # 预算消耗异常
      - alert: BudgetAnomaly
        expr: |
          rate(campaign_budget_spent_total[1h]) 
          > 2 * on() group_left() 
          avg_over_time(rate(campaign_budget_spent_total[1h])[1d])
        for: 30m
        labels:
          severity: warning
          team: campaign
        annotations:
          summary: "预算消耗速度是昨日均值的 2 倍"

  - name: infrastructure-alerts
    rules:
      - alert: HighCPU
        expr: 100 - (avg by(instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100) > 80
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "CPU 使用率 > 80%"
      
      - alert: HighMemory
        expr: node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes * 100 < 10
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "内存使用率 > 90%"
      
      - alert: DiskSpaceLow
        expr: node_filesystem_avail_bytes / node_filesystem_size_bytes * 100 < 15
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "磁盘使用率 > 85%"
```

### 4.2 告警路由

```yaml
# Alertmanager 配置
global:
  resolve_timeout: 5m

route:
  group_by: ['alertname', 'severity']
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
      receiver: 'slack-warning'

receivers:
  - name: 'default-receiver'
    webhook_configs:
      - url: 'http://alertmanager-webhook:5001/'
  
  - name: 'pagerduty-critical'
    pagerduty_configs:
      - service_key: '<pagerduty-key>'
  
  - name: 'slack-warning'
    slack_configs:
      - api_url: '<slack-webhook>'
        channel: '#alerts'
        title: '{{ .CommonAnnotations.summary }}'
        text: '{{ .CommonAnnotations.description }}'
```

---

## 第五部分：自测题

### 问题 1
PromQL 中 rate() 和 increase() 的区别？

<details>
<summary>查看答案</summary>

1. **rate()**：每秒增长率，适用于计数器
2. **increase()**：时间窗口内增长量
3. **使用场景**：rate() 用于 P99 计算，increase() 用于统计总量
4. **Counter 重置**：rate() 自动处理重置
5. **广告场景**：QPS 用 rate，日统计用 increase

</details>

### 问题 2
Grafana 仪表盘设计原则是什么？

<details>
<summary>查看答案</summary>

1. **层次清晰**：概览 → 详情
2. **关键指标优先**：QPS、延迟、错误率
3. **时间范围选择**：支持 1h/6h/24h/7d
4. **变量模板**：服务名、实例名可切换
5. **颜色语义**：红=错误，绿=正常

</details>

### 问题 3
告警规则如何避免告警风暴？

<details>
<summary>查看答案</summary>

1. **分组**：按 severity 分组
2. **等待时间**：for: 5m 避免瞬时波动
3. **去重**：Alertmanager group_by
4. **抑制**：严重告警抑制次要告警
5. **静默**：维护期间静默

</details>

---

*本文档基于可观测性原理整理。*