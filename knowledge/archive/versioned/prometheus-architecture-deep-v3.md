# Prometheus监控架构深度解析

> 深入Prometheus：数据模型、查询语言、 exporters、Alertmanager。
> 源码级分析，包含生产环境最佳实践。
> 适用对象：SRE、运维工程师

---

## 1. 数据模型

### 1.1 Metrics类型

```
Prometheus数据模型：

┌─────────────────────────────────────────────────────────────┐
│  Metric类型：                                                │
│  ├── Counter：计数器（单调递增）                              │
│  ├── Gauge：仪表盘（可增可减）                                │
│  ├── Histogram：直方图（分布统计）                            │
│  └── Summary：摘要（客户端计算分位数）                        │
│                                                             │
│  标签（Labels）：                                            │
│  ├── key=value格式                                           │
│  ├── 标识Metric的不同维度                                    │
│  └── 唯一标识：Metric名 + Labels                             │
│                                                             │
│  时间序列：                                                  │
│  ├── 格式：<metric_name>{<label>=<value>}                    │
│  ├── 示例：http_requests_total{method="GET", status="200"}  │
│  └── 按时间戳存储                                            │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. PromQL查询

### 2.1 核心函数

```
PromQL核心函数：

┌─────────────────────────────────────────────────────────────┐
│  聚合操作：                                                  │
│  ├── sum/count/avg/min/max：基础聚合                          │
│  ├── by/without：分组维度                                    │
│  └── topk/bottomk：取TopN                                    │
│                                                             │
│  时间范围函数：                                              │
│  ├── rate()：增长率（Counter）                                │
│  ├── irate()：瞬时增长率                                     │
│  ├── increase()：增长量                                      │
│  └── histogram_quantile()：分位数                            │
│                                                             │
│  数学运算：                                                  │
│  ├── + - * / %                                               │
│  ├── ^（幂运算）                                             │
│  └── abs() round() ceil() floor()                           │
│                                                             │
│  示例：                                                      │
│  sum(rate(http_requests_total[5m])) by (method)             │
│  histogram_quantile(0.99, rate(http_request_duration_seconds[5m]))
└─────────────────────────────────────────────────────────────┘
```

---

## 3. 自测题

### 3.1 单选题

1. Prometheus中，rate()函数主要用于：
   A. 计算绝对值  B. 计算增长率  C. 计算分位数  D. 计算最大值
   答案：B

---

> 本文档适用对象：SRE、运维工程师
> 难度：资深专家级
