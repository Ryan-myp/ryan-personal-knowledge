# Prometheus Exporter - 资深专家深度实现

## 一、Exporter架构

```go
package exporter

import (
    "github.com/prometheus/client_golang/prometheus"
    "github.com/prometheus/client_golang/prometheus/promhttp"
)

type MetricExporter struct {
    collector prometheus.Collector
    registry  *prometheus.Registry
}

func NewExporter(name string) *MetricExporter {
    return &MetricExporter{
        collector: NewCollector(name),
        registry:  prometheus.NewRegistry(),
    }
}

func (e *MetricExporter) Start(addr string) {
    e.registry.MustRegister(e.collector)
    http.Handle("/metrics", promhttp.HandlerFor(e.registry, promhttp.HandlerOpts{}))
    http.ListenAndServe(addr, nil)
}
```

## 二、自定义Collector

```go
package exporter

import "github.com/prometheus/client_golang/prometheus"

type SystemCollector struct {
    cpuUsage *prometheus.GaugeVec
    memUsage *prometheus.GaugeVec
}

func NewSystemCollector() *SystemCollector {
    return &SystemCollector{
        cpuUsage: prometheus.NewGaugeVec(
            prometheus.GaugeOpts{
                Name: "system_cpu_usage",
                Help: "CPU usage percentage",
            },
            []string{"host", "core"},
        ),
        memUsage: prometheus.NewGaugeVec(
            prometheus.GaugeOpts{
                Name: "system_memory_usage",
                Help: "Memory usage in bytes",
            },
            []string{"host", "type"},
        ),
    }
}

func (c *SystemCollector) Describe(ch chan<- *prometheus.Desc) {
    c.cpuUsage.Describe(ch)
    c.memUsage.Describe(ch)
}

func (c *SystemCollector) Collect(ch chan<- prometheus.Metric) {
    // 收集CPU指标
    cpuData := getCPUUsage()
    for core, usage := range cpuData {
        c.cpuUsage.WithLabelValues("host1", core).Set(usage)
        ch <- c.cpuUsage.WithLabelValues("host1", core).Metric
    }
    
    // 收集内存指标
    memData := getMemoryUsage()
    for typ, usage := range memData {
        c.memUsage.WithLabelValues("host1", typ).Set(usage)
        ch <- c.memUsage.WithLabelValues("host1", typ).Metric
    }
}
```

## 三、服务发现

```yaml
# scrape_configs
- job_name: 'custom-exporters'
  static_configs:
    - targets: ['exporter1:9100', 'exporter2:9101']
      labels:
        environment: 'production'
        
- job_name: 'kubernetes-pods'
  kubernetes_sd_configs:
    - role: pod
  relabel_configs:
    - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_scrape]
      action: keep
      regex: true
```

## 四、面试高频题

### Q1: 如何创建自定义Exporter？

```
A:
1. 实现Collector接口
2. 定义指标类型
3. 注册到Registry
```

### Q2: 如何处理高基数标签？

```
A:
1. 避免高基数标签
2. 使用Histogram替代Counter
3. 合理设计标签维度
```

## 五、自测题

1. 解释Collector接口
2. 如何实现服务发现？
3. 如何优化采集性能？

---

## 参考文档

- [Prometheus客户端库](https://github.com/prometheus/client_golang)
- [Exporter最佳实践](https://prometheus.io/docs/instrumenting/writing_exporters/)
