# 可观测性系统设计深度解析

> 深入可观测性：Metrics、Logs、Traces、SLO、告警设计。
> 源码级分析，包含生产环境最佳实践。
> 适用对象：SRE、后端架构师

---

## 1. 可观测性三大支柱

### 1.1 Metrics（指标）

```
Metrics 核心概念：

1. 指标类型
   ├── Counter (计数器)
   │   ├── 单调递增
   │   └── 适用：请求数、错误数
   ├── Gauge (仪表)
   │   ├── 可增可减
   │   └── 适用：内存使用、队列长度
   ├── Histogram (直方图)
   │   ├── 分布统计
   │   └── 适用：请求延迟
   └── Summary (摘要)
       ├── 客户端计算分位数
       └── 适用：P99 延迟

2. 标签 (Labels)
   └── key=value 维度

3. 采集方式
   ├── Pull (拉取)
   ├── Push (推送)
   └── Pushgateway (中间层)
```

### 1.2 Logs（日志）

```
日志系统架构：

┌─────────────────────────────────────────────────────────────┐
│                    日志架构                                   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  采集层 (Collection)                                         │
│  ├── Filebeat (文件日志)                                     │
│  ├── Fluentd (通用日志)                                     │
│  └── Vector (高性能日志)                                    │
│                                                             │
│  传输层 (Transport)                                          │
│  ├── Kafka (消息队列)                                       │
│  ├── Redis (缓存)                                           │
│  └── HTTP (直接推送)                                        │
│                                                             │
│  存储层 (Storage)                                            │
│  ├── Elasticsearch (搜索)                                   │
│  ├── Loki (轻量级)                                          │
│  └── ClickHouse (分析)                                      │
│                                                             │
│  查询层 (Query)                                              │
│  ├── Kibana (ES 可视化)                                     │
│  ├── Grafana Loki (Loki 可视化)                              │
│  └── Grafana (统一监控)                                     │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 1.3 Traces（链路追踪）

```
分布式追踪架构：

┌─────────────────────────────────────────────────────────────┐
│                    链路追踪                                   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Trace (追踪)                                                │
│  ├── 一次请求的完整调用链                                    │
│  └── 全局唯一 ID                                             │
│                                                             │
│  Span (跨度)                                                 │
│  ├── 一次操作                                                │
│  ├── 开始时间/结束时间                                       │
│  ├── 元数据 (标签)                                          │
│  └── 子 Span (嵌套)                                         │
│                                                             │
│  Context Propagation (上下文传播)                            │
│  ├── B3: X-B3-TraceId, X-B3-SpanId                         │
│  ├── W3C Trace Context: traceparent                        │
│  └── Jaeger: uber-trace-id                                  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. OpenTelemetry

### 2.1 架构

```
OpenTelemetry 架构：

┌─────────────────────────────────────────────────────────────┐
│                  OpenTelemetry 架构                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  API (接口层)                                               │
│  ├── Tracing API                                           │
│  ├── Metrics API                                           │
│  └── Logs API                                              │
│                                                             │
│  SDK (实现层)                                               │
│  ├── Tracing SDK                                           │
│  ├── Metrics SDK                                           │
│  └── Logs SDK                                              │
│                                                             │
│  Collector (收集器)                                          │
│  ├── 接收数据                                               │
│  ├── 处理转换                                              │
│  └── 导出数据                                               │
│                                                             │
│  Backends (后端)                                             │
│  ├── Prometheus                                            │
│  ├── Jaeger                                                 │
│  ├── Grafana Cloud                                         │
│  └── 自定义后端                                             │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 Go 实现

```go
// otel.go

package main

import (
    "context"
    "go.opentelemetry.io/otel"
    "go.opentelemetry.io/otel/trace"
    "go.opentelemetry.io/otel/exporters/jaeger"
    "go.opentelemetry.io/otel/sdk/resource"
    semconv "go.opentelemetry.io/otel/semconv/v1.7.0"
)

func main() {
    // 创建 Jaeger 导出器
    exporter, err := jaeger.New(jaeger.WithCollectorEndpoint(
        jaeger.WithEndpoint("http://localhost:14268/api/traces"),
    ))
    if err != nil {
        panic(err)
    }
    
    // 创建 TracerProvider
    tp := trace.NewTracerProvider(
        trace.WithBatcher(exporter),
        trace.WithResource(resource.NewWithAttributes(
            semconv.SchemaURL,
            semconv.ServiceNameKey.String("my-service"),
        )),
    )
    defer tp.Shutdown(context.Background())
    
    // 设置全局 TracerProvider
    otel.SetTracerProvider(tp)
    
    // 创建 Tracer
    tracer := otel.Tracer("example-tracer")
    
    // 创建 Span
    ctx, span := tracer.Start(context.Background(), "process-request")
    defer span.End()
    
    // 添加属性
    span.SetAttributes(
        attribute.String("http.method", "GET"),
        attribute.Int("http.status_code", 200),
    )
    
    // 添加事件
    span.AddEvent("processing-started")
    
    // 业务逻辑
    result := processRequest(ctx)
    
    span.SetAttributes(attribute.Int("result", result))
}
```

---

## 3. SLO 设计

### 3.1 SLO 三要素

```
SLO 设计原则：

1. 定义良好
   ├── 基于用户视角
   ├── 可量化测量
   └── 有明确目标值

2. 错误预算
   ├── 总预算 - 已用预算 = 剩余预算
   ├── 预算耗尽 → 暂停新功能
   └── 预算健康 → 可加速迭代

3. 告警阈值
   ├── 错误预算消耗速率
   ├── 基于 SLO 而非指标
   └── 分级告警
```

### 3.2 SLO 计算

```go
// slo.go

package slo

import (
    "time"
)

type SLO struct {
    Name          string
    Target        float64  // 目标值 (0-1)
    Window        time.Duration
    TotalRequests int64
    SuccessRequests int64
}

func (s *SLO) Calculate() float64 {
    if s.TotalRequests == 0 {
        return 0
    }
    return float64(s.SuccessRequests) / float64(s.TotalRequests)
}

func (s *SLO) IsOK() bool {
    return s.Calculate() >= s.Target
}

func (s *SLO) ErrorBudget() float64 {
    compliance := s.Calculate()
    budget := 1.0 - s.Target
    used := s.Target - compliance
    if used < 0 {
        used = 0
    }
    return budget - used
}
```

---

## 4. 告警设计

### 4.1 告警策略

```
告警策略设计：

1. 告警级别
   ├── P0: 立即处理 (5分钟内)
   ├── P1: 紧急处理 (30分钟内)
   ├── P2: 重要处理 (2小时内)
   └── P3: 普通处理 (24小时内)

2. 通知方式
   ├── P0: 电话 + 短信 + 钉钉
   ├── P1: 短信 + 钉钉
   ├── P2: 钉钉 + 邮件
   └── P3: 邮件

3. 告警抑制
   ├── 相同告警合并
   ├── 维护时段抑制
   └── 依赖告警抑制
```

### 4.2 Go 实现告警系统

```go
// alert.go

package alert

import (
    "context"
    "sync"
    "time"
)

type AlertLevel int

const (
    P0 AlertLevel = iota
    P1
    P2
    P3
)

type Alert struct {
    ID        string
    Level     AlertLevel
    Message   string
    Timestamp time.Time
}

type AlertSystem struct {
    alerts     []*Alert
    handlers   map[AlertLevel][]AlertHandler
    mu         sync.RWMutex
}

type AlertHandler func(ctx context.Context, alert *Alert) error

func (s *AlertSystem) AddHandler(level AlertLevel, handler AlertHandler) {
    s.handlers[level] = append(s.handlers[level], handler)
}

func (s *AlertSystem) Send(alert *Alert) {
    s.mu.Lock()
    defer s.mu.Unlock()
    
    s.alerts = append(s.alerts, alert)
    
    for _, handler := range s.handlers[alert.Level] {
        go handler(context.Background(), alert)
    }
}
```

---

## 5. 监控架构

### 5.1 Prometheus 架构

```
Prometheus 监控架构：

┌─────────────────────────────────────────────────────────────┐
│                    Prometheus 架构                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Prometheus Server                                            │
│  ├── 时序数据库                                               │
│  ├── 数据拉取 (Scrape)                                       │
│  └── 查询引擎                                                │
│                                                             │
│  Exporter                                                    │
│  ├── Node Exporter (主机指标)                                │
│  ├── cAdvisor (容器指标)                                     │
│  ├── MySQL Exporter                                          │
│  └── 自定义 Exporter                                         │
│                                                             │
│  Alertmanager (告警管理)                                      │
│  ├── 告警路由                                               │
│  ├── 告警抑制                                               │
│  └── 告警分组                                               │
│                                                             │
│  Grafana (可视化)                                            │
│  └── Dashboard 展示                                          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 5.2 关键指标

```
核心监控指标：

1. 应用指标
   ├── QPS/TPS
   ├── 错误率
   ├── 响应时间 (P50/P95/P99)
   └── 并发连接数

2. 系统指标
   ├── CPU 使用率
   ├── 内存使用率
   ├── 磁盘 I/O
   └── 网络带宽

3. 业务指标
   ├── 订单量
   ├── 转化率
   ├── 用户活跃度
   └── 收入指标
```

---

## 6. 实战案例

### 6.1 案例一：API 延迟告警

```
场景：API P99 延迟突增

排查流程：
1. 查看 Grafana 监控面板
2. 确认延迟突增时间点
3. 检查相关服务健康状态
4. 分析慢查询日志
5. 定位瓶颈 (CPU/内存/DB)
6. 实施优化
7. 验证效果
```

### 6.2 案例二：错误率告警

```
场景：服务错误率超过 1%

处理流程：
1. 自动触发 P1 告警
2. 值班人员响应
3. 查看错误日志
4. 分析错误类型分布
5. 定位根因
6. 实施修复
7. 复盘改进
```

---

## 7. 总结

### 7.1 核心原理回顾

| 模块 | 核心机制 |
|------|----------|
| Metrics | Counter/Gauge/Histogram |
| Logs | 采集-传输-存储-查询 |
| Traces | Trace/Span 模型 |
| SLO | 目标值+错误预算 |
| 告警 | 分级+抑制 |

### 7.2 最佳实践

- [ ] 建立完整可观测性体系
- [ ] 设计合理 SLO
- [ ] 实施分级告警
- [ ] 定期演练故障
- [ ] 持续优化监控

---

*最后更新：2026-08-11*
*作者：Ryan*
