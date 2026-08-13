# Prometheus监控架构 - 资深专家深度实现

## 一、核心组件

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Prometheus架构                                   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐            │
│   │  Node Export │    │  cAdvisor    │    │  自定义Exporter│            │
│   │  (主机监控)  │    │ (容器监控)   │    │   (业务监控)  │            │
│   └──────┬───────┘    └──────┬───────┘    └──────┬───────┘            │
│          │                   │                   │                     │
│          └───────────────────┼───────────────────┘                     │
│                              ▼                                         │
│                    ┌─────────────────┐                                 │
│                    │   Prometheus    │                                 │
│                    │   Server        │                                 │
│                    │   (TSDB存储)    │                                 │
│                    └────────┬────────┘                                 │
│                             │                                          │
│              ┌──────────────┼──────────────┐                           │
│              ▼              ▼              ▼                           │
│        ┌──────────┐  ┌──────────┐  ┌──────────┐                       │
│        │ Grafana  │  │ Alert    │  │ Push     │                       │
│        │  (可视化)│  │ Manager  │  │ Gateway  │                       │
│        └──────────┘  └──────────┘  └──────────┘                       │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、指标类型

```go
package prometheus

import "github.com/prometheus/client_golang/prometheus"

// Counter: 只增不减
type Counter struct {
    prometheus.Counter
}

// Gauge: 可增可减
type Gauge struct {
    prometheus.Gauge
}

// Histogram: 直方图分布
type Histogram struct {
    prometheus.Histogram
}

// Summary: 分位数统计
type Summary struct {
    prometheus.Summary
}
```

## 三、服务发现

```yaml
# prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'kubernetes-pods'
    kubernetes_sd_configs:
      - role: pod
    relabel_configs:
      - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_scrape]
        action: keep
        regex: true
```

## 四、面试高频题

### Q1: Prometheus和Zabbix的区别？

```
A:
• Prometheus: 时序数据库，Pull模型
• Zabbix: 传统监控，Push/Pull混合
• Prometheus更适合云原生
```

### Q2: 如何实现高可用？

```
A:
1. 联邦架构 (Federation)
2. 多实例部署
3. Thanos/Cortex长期存储
```

## 五、自测题

1. 解释Prometheus数据模型
2. 如何实现服务发现？
3. 如何优化查询性能？

---

## 参考文档

- [Prometheus官方文档](https://prometheus.io/docs/)
- [Prometheus源码](https://github.com/prometheus/prometheus)
