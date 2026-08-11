# 分布式链路追踪深度解析

> 深入分布式链路追踪：Jaeger、Zipkin、OpenTelemetry。
> 源码级分析，包含生产环境最佳实践。
> 适用对象：SRE、后端工程师

---

## 1. 链路追踪核心概念

### 1.1 Trace/Span

```
链路追踪数据结构：

┌─────────────────────────────────────────────────────────────┐
│  TraceId：一次请求的完整链路ID                               │
│  ├── 唯一标识一次请求的完整调用链                            │
│  └── 通常为32位十六进制字符串                                 │
│                                                             │
│  SpanId：一个操作的唯一ID                                   │
│  ├── 唯一标识一次RPC调用/数据库查询等操作                     │
│  └── 通常为16位十六进制字符串                                 │
│                                                             │
│  ParentSpanId：父操作的SpanId                                │
│  └── 用于构建调用树关系                                      │
│                                                             │
│  示例调用链：                                                │
│  TraceId=abc123                                             │
│  ├── Span1: API Gateway (root)                              │
│  │   ├── Span2: User Service                                │
│  │   │   └── Span3: Database Query                          │
│  │   └── Span4: Cache Service                               │
│  └── Span5: Order Service                                   │
│      └── Span6: Payment Gateway                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. OpenTelemetry

### 2.1 架构

```
OpenTelemetry 架构：

┌─────────────────────────────────────────────────────────────┐
│  采集层：                                                    │
│  ├── SDK：自动/手动埋点                                      │
│  ├── Agent： sidecar模式采集                                 │
│  └── Exporter：导出到后端                                     │
│                                                             │
│  传输层：                                                    │
│  └── OTLP（OpenTelemetry Protocol）                         │
│                                                             │
│  存储层：                                                    │
│  ├── Jaeger：分布式追踪存储                                  │
│  ├── Tempo：Grafana生态追踪存储                              │
│  └── ElasticSearch：日志+追踪统一存储                        │
│                                                             │
│  可视化层：                                                  │
│  ├── Jaeger UI                                             │
│  ├── Grafana：集成展示                                       │
│  └── Kibana：ELK生态展示                                     │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. 自测题

### 3.1 单选题

1. OpenTelemetry导出协议是：
   A. gRPC  B. OTLP  C. HTTP  D. Kafka
   答案：B

---

> 本文档适用对象：SRE、后端工程师
> 难度：资深专家级
