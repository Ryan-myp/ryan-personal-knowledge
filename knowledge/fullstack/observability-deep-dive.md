# 可观测性三件套深度 — Prometheus/Grafana/OpenTelemetry 源码级剖析

> 标签: `#Prometheus` `#Grafana` `#OpenTelemetry` `#可观测性` `#Metrics` `#Tracing` `#Logging` `#源码级`
> 创建日期: 2026-06-10 | 作者: Ryan
> 定位: 资深专家级 — 从指标采集到链路追踪，全链路可观测性深度剖析

---

## 第一部分：入门引导（5 分钟速览）

### 1.1 可观测性的三支柱

```
┌─────────────────────────────────────────────────────────────┐
│                   可观测性三支柱                              │
│                                                             │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐ │
│  │   Metrics (指标) │  │  Tracing (链路)  │  │  Logging (日志)│ │
│  │                 │  │                 │  │             │ │
│  │ 量化数据         │  │ 请求链路追踪     │  │ 结构化日志   │ │
│  │ 如: CPU 85%,    │  │ 如: req-id       │  │ 如: error    │ │
│  │   qps=1000,     │  │   service-a→b→c  │  │   trace-id   │ │
│  │   latency=50ms  │  │   duration=120ms │  │   level=warn │ │
│  │                 │  │                 │  │             │ │
│  │ Prometheus      │  │ Jaeger/Tempo     │  │ Loki/ELK    │ │
│  └────────┬────────┘  └────────┬────────┘  └──────┬──────┘ │
│           │                    │                    │        │
│           └────────────────────┼────────────────────┘        │
│                                ▼                            │
│                    ┌─────────────────────┐                   │
│                    │   Grafana (统一看板) │                   │
│                    │   可视化 + 告警 +   │                   │
│                    │   告警通知           │                   │
│                    └─────────────────────┘                   │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 为什么选这三件套？

| 方案 | 优势 | 劣势 | 适用场景 |
|------|------|------|----------|
| **Prometheus + Grafana** | 生态最大、K8s 原生、告警强大 | 分布式追踪需额外组件 | **指标首选** ⭐ |
| **OpenTelemetry** | 厂商中立、统一 API | 生态较新、学习曲线 | **Tracing + Logging 统一标准** ⭐ |
| **Elasticsearch + Kibana** | 全文检索、日志分析强 | 资源消耗大、成本高 | 日志分析 |
| **Jaeger** | 追踪深度分析能力强 | 维护成本高 | 分布式追踪 |
| **Tempo** | 轻量、与 Loki 集成好 | 功能不如 Jaeger 丰富 | 云原生追踪 |

### 1.3 核心概念速查

| 概念 | 说明 |
|------|------|
| **Metric 类型** | Counter/Gauge/Histogram/Summary |
| **Label** | 维度标签，用于分组和过滤 |
| **Target** | 被监控的端点 |
| **Job** | 一组相同类型 Target 的集合 |
| **Instance** | 具体被监控的实例 |
| **Pull vs Push** | Prometheus 拉取 / OTel 推送 |
| **Span** | 单次操作的时间线 |
| **Trace** | 一次请求的完整链路 |
| **Resource** | 产生 span 的实体 (Pod/Node/Service) |
| **Instrument** | 采集数据的代码 |
| **Exporter** | 将指标暴露给 Prometheus 的组件 |
| **Service Discovery** | 自动发现监控目标 |
| **Recording Rule** | 预计算指标，加速查询 |
| **Alert Rule** | 告警规则 |
| **Alertmanager** | 告警去重/分组/路由 |

---

## 第二部分：Prometheus 源码级深度

### 2.1 存储引擎 — TSDB 架构

```go
// tsdb.go — Prometheus TSDB 核心结构
package tsdb

import (
	"github.com/prometheus/prometheus/storage"
	"github.com/prometheus/prometheus/tsdb/chunkenc"
)

// TSDB 时间序列数据库
type TSDB struct {
	dir           string              // 数据目录
	opts          Options             // 配置选项
	compactDir    string              // 压缩目录
	db            *db                 // 核心数据库
	queryable     storage.Queryable   // 查询接口
	blockReaders  []blockReader       // 块读取器
	
	// 写路径: Appender → WAL → Head → Memory → Blocks
	appender      *headAppender       // 追加器
	wal           *wal.WAL            // 预写日志 (Write-Ahead Log)
	head          *Head               // 内存头部存储
}

// 存储层级:
// /prometheus/data/
// ├── 01F3J2K8L9M0N1P2Q3R4S5T6  ← 压缩后的时间序列块 (2h, 134MB)
// │   ├── meta.json             ← 元数据 (区间、索引位置、chunk 位置)
// │   ├── index                 ← 索引文件 (series → chunk 映射)
// │   ├── chunks                ← 压缩的原始数据 (XOR + Delta 编码)
// │   └── tombstones            ← 删除标记
// ├── 01F3J2K8L9M0N1P2Q3R4S5U7  ← 另一个块
// ├── 01F3J2K8L9M0N1P2Q3R4S5V8  ← ...
// └── head/                     ← 当前活跃的数据 (内存中 + WAL)
//     ├── wal/                  ← WAL 日志
//     │   ├── 000001            ← 日志段 1
//     │   ├── 000002            ← 日志段 2
//     │   └── ...
//     ├── chunks/               ← 当前活跃的 chunk
//     ├── meta.json             ← Head 元数据
//     └── queries.active.json   ← 活跃查询列表
//
// 数据生命周期:
// 1. 新数据写入 → Head (内存, 默认 2h)
// 2. Head 满 2h → 压缩为 Block → 持久化到磁盘 (2h, 134MB)
// 3. 每 2h 压缩一个 Block → 形成时间线
// 4. 旧 Block 超过 retention (默认 15d) → 删除
```

**TSDB 压缩算法详解：**

```go
// XOR + Delta + FastDelta 编码 — 极致压缩
type Encoding struct {
	// 时间戳编码: Delta
	// 示例时间戳序列: 1000, 1001, 1002, 1003, 1004, 1005
	// 编码为: 1000 (原始), 1, 1, 1, 1, 1 (差值)
	// → 从 4 字节 × 6 = 24 字节 → 1 + 1 × 5 = 6 字节
	
	// 值编码: XOR + Delta
	// 对于浮点数序列: 1.5, 1.7, 1.6, 1.8, 1.5, 1.6
	// XOR 编码: 将相邻值做 XOR 操作
	// → 减少熵，再压缩
	//
	// 对于整数序列: 100, 105, 98, 110, 102
	// 编码为: 100 (原始), 5, -7, 12, -8 (差值)
	// → Delta 编码对缓变数据效果极佳
}

// Series 索引结构
type Series struct {
	Labels Labels     // 标签集合
	Chunks []Chunk    // 压缩的数据块
	Ref    uint64     // 系列引用 ID
}

type Labels struct {
	// 示例:
	// {job="apiserver", namespace="default", pod="api-server-abc123", 
	//  method="GET", handler="/api/v1/namespaces"}
	// 
	// 存储优化: 标签字典压缩
	// 将相同 label name/value 提取为字典，series 只存索引
	// → 内存占用减少 50-80%
}

// 压缩率估算:
// 原始数据 (32位float64 + 64位timestamp = 12B/样本)
// 压缩后: ~2-4B/样本 (取决于数据变化频率)
// 压缩率: 3-6x
```

### 2.2 查询引擎 — PromQL 详解

```go
// query.go — PromQL 查询引擎
package promql

// Query 查询对象
type Query struct {
	engine    *Engine              // 查询引擎
	query     string               // PromQL 表达式
	ctx       context.Context      // 上下文 (超时控制)
	start     time.Time            // 开始时间
	end       time.Time            // 结束时间
	step      time.Duration        // 步长 (可选)
	
	// 优化: 查询缓存
	cache     *query.Cache
}

// 常用 PromQL 函数:
//
// ┌─────────────────────────────────────────────────────────────┐
│                     PromQL 速查                               │
│                                                             │
│  聚合:                                                      │
│  sum(ratio{job="api"})       → 所有 label 求和              │
│  sum by (pod)(ratio)         → 按 pod 分组求和             │
│  avg by (method)(latency)    → 按 method 分组求平均          │
│  rate(http_requests_total[5m]) → 5min 平均速率              │
│  increase(node_cpu_total[1h])  → 1h 增量                    │
│                                                             │
│  时间函数:                                                  │
│  time()                      → 当前时间 (秒)                 │
│  hour()                      → 当前小时                      │
│  day_of_week()               → 星期几 (0-6)                 │
│                                                             │
│  数学函数:                                                  │
│  abs(x)                      → 绝对值                       │
│  clamp(x, min, max)          → 限制范围                      │
│  round(x, to_nearest=1)      → 四舍五入                     │
│                                                             │
│  对比分析:                                                  │
│  increase(metric[1h]) / increase(metric[1h] offset 1d)     │
│  → 同比分析 (当前 vs 昨天同一时段)                           │
│                                                             │
│  窗口函数:                                                  │
│  histogram_quantile(0.95, rate(http_request_duration[5m]))  │
│  → P95 延迟                                                  │
└─────────────────────────────────────────────────────────────┘

// 性能优化: 预计算 (Recording Rule)
// 将复杂 PromQL 预计算为简单指标，加速查询

// recording_rules.yaml:
// groups:
//   - name: api_rules
//     interval: 30s
//     rules:
//       - record: job:http_requests:rate5m
//         expr: rate(http_requests_total[5m])
//       - record: job:http_request_latency:p95
//         expr: histogram_quantile(0.95, sum(rate(http_request_duration_bucket[5m])) by (le, job))
//       - record: namespace:pod_cpu_utilization:ratio
//         expr: sum(rate(container_cpu_usage_seconds_total[5m])) by (namespace, pod)
//                   / sum(container_spec_cpu_quota / container_spec_cpu_period) by (namespace, pod)

// 查询时直接使用:
// job:http_requests:rate5m{job="api"}  // 替代 rate(http_requests_total[5m])
// → 查询速度提升 5-50x
```

### 2.3 服务发现 — K8s 自动发现

```go
// kubernetes_sd.go — K8s 服务发现
package discover

// SDConfig K8s 服务发现配置
type SDConfig struct {
	Role string `yaml:"role"`  // node/pod/service/endpoint/endpoints/log
    
    // 支持的资源类型:
    // - node: 发现 K8s Node 资源 → 监控 kubelet
    // - pod: 发现 Pod 资源 → 监控 Pod 指标
    // - service: 发现 Service 资源 → 监控 Service 端点
    // - endpoint: 发现 Endpoints 资源 → 监控 Pod 端点
    // - endpoints: 同上 (别名)
    // - ingress: 发现 Ingress 资源 → 监控 Ingress Controller
    
    APIServers     []string        `yaml:"api_servers"`
    Role           string          `yaml:"role"`
    Namespaces     NamespaceFilter `yaml:"namespaces"`
    KubeConfig     string          `yaml:"kubeconfig"`
    TLSConfig      *TLSConfig      `yaml:"tls_config"`
    
    // 标签重命名 (关键配置)
    RelabelConfigs []*RelabelConfig `yaml:"relabel_configs"`
}

// RelabelConfig 标签处理规则
type RelabelConfig struct {
    SourceLabels []string `yaml:"source_labels"`  // 源标签
    Separator    string   `yaml:"separator"`      // 分隔符 (默认 ;)
    TargetLabel  string   `yaml:"target_label"`   // 目标标签
    Regex        Regexp   `yaml:"regex"`          // 正则表达式 (默认: (.*))
    Replacement  string   `yaml:"replacement"`     // 替换值 (默认: $1)
    Action       string   `yaml:"action"`          // replace|keep|drop|labelmap|labeldrop|labelkeep
}

// 典型 K8s 服务发现 + Relabel 配置:
// kubernetes_sd_configs:
//   - role: pod
//     namespaces:
//       names: [default, monitoring, kube-system]
//
//     relabel_configs:
//       # 1. 只保留有 prometheus.io/scrape=true 注解的 Pod
//       - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_scrape]
//         action: keep
//         regex: "true"
//
//       # 2. 设置 job 标签
//       - source_labels: [__meta_kubernetes_pod_label_app]
//         target_label: job
//         replacement: "${1}"
//
//       # 3. 设置 instance 标签为 Pod IP:Port
//       - source_labels: [__meta_kubernetes_pod_ip, __meta_kubernetes_pod_annotation_prometheus_io_port]
//         action: replace
//         regex: (.+);(.+)
//         replacement: ${1}:${2}
//         target_label: __address__
//
//       # 4. 保留 label 映射
//       - source_labels: [__meta_kubernetes_pod_label_version]
//         action: labelmap
//         regex: __meta_kubernetes_pod_label_(.+)
//
//       # 5. 清理内部标签
//       - action: labeldrop
//         regex: __meta_kubernetes_(pod|namespace|service)_(.+)
```

### 2.4 Alertmanager — 告警系统

```go
// alertmanager.go — 告警管理
package alertmanager

type Alertmanager struct {
    config    *Config           // 告警配置
    alerts    *AlertStore       // 告警存储
    routes    *Route            // 告警路由
    receivers []*Receiver       // 接收器 (Email/Slack/PagerDuty/Webhook)
    silence   *SilenceStore     // 静默管理
    
    // 核心能力:
    // 1. 告警去重 (fingerprint 相同视为同一告警)
    // 2. 告警分组 (GroupBy, GroupByAll)
    // 3. 告警静默 (Silence, 设置过期时间)
    // 4. 告警路由 (Route Tree, 匹配标签)
    // 5. 告警抑制 (Inhibit, 高级告警抑制低级别)
    // 6. 告警通知 (Webhook, Email, Slack, PagerDuty, WeChat)
}

// 告警路由配置:
// route:
//   receiver: 'default'           # 默认接收器
//   group_by: ['alertname', 'job']  # 分组标签
//   group_wait: 30s               # 首次分组等待时间
//   group_interval: 5m            # 后续分组间隔
//   repeat_interval: 4h           # 重复通知间隔
//   
//   routes:                     # 路由树
//     - match:
//         severity: 'critical'
//       receiver: 'pagerduty-critical'
//       group_wait: 10s
//       repeat_interval: 15m
//       
//     - match:
//         severity: 'warning'
//       receiver: 'slack-warnings'
//       
//     - match:
//         team: 'infra'
//       receiver: 'slack-infra'
//
// 告警抑制规则:
// inhibit_rules:
//   - source_match:
//       severity: 'critical'
//     target_match:
//       severity: 'warning'
//     equal: ['alertname', 'namespace']
//     # 当 critical 告警触发时, 抑制同 namespace 同 alertname 的 warning 告警
//     # 避免告警风暴: NodeDown → 抑制下面的 PodCrashLoopBackOff

// 告警抑制的实战价值:
// 没有抑制: Node1 宕机 → 触发 50 个 Pod 告警 = 51 条通知
// 有抑制: Node1 宕机 → 只触发 1 条 NodeDown 告警 = 1 条通知
```

### 2.5 Go 应用集成 — 自定义指标

```go
// metrics.go — Go 应用 Prometheus 指标定义
package metrics

import (
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
)

// 注册自定义指标
var (
	// Counter: 只增不减 (请求总数, 错误总数)
	httpRequestsTotal = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "http_requests_total",
			Help: "Total number of HTTP requests",
		},
		[]string{"method", "path", "status"},
	)

	// Gauge: 可增可减 (当前连接数, 队列长度)
	activeConnections = promauto.NewGauge(
		prometheus.GaugeOpts{
			Name: "active_connections",
			Help: "Current number of active connections",
		},
	)

	// Histogram: 分布统计 (请求延迟, 响应大小)
	// 自动计算: count, sum, 以及自定义 bucket 的分位数
	requestDuration = promauto.NewHistogramVec(
		prometheus.HistogramOpts{
			Name:    "http_request_duration_seconds",
			Help:    "HTTP request duration in seconds",
			Buckets: prometheus.DefBuckets, // [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10]
		},
		[]string{"method", "path"},
	)

	// Summary: 客户端计算分位数 (不推荐，用 Histogram 代替)
	// Summary 在客户端计算分位数，内存开销大

	// Info: 不可变标签 (版本信息, 部署时间)
	appInfo = promauto.NewGaugeVec(
		prometheus.GaugeOpts{
			Name: "app_info",
			Help: "Application info",
		},
		[]string{"version", "commit", "branch"},
	)

	// Collector: 自定义指标收集器
	// 适用于需要动态生成指标的场景
)

// 中间件示例: HTTP 请求指标采集
func MetricsMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		
		// 包装 ResponseWriter 获取状态码
		rw := &responseWriter{ResponseWriter: w, statusCode: 200}
		next.ServeHTTP(rw, r)
		
		duration := time.Since(start).Seconds()
		
		// 更新指标
		httpRequestsTotal.WithLabelValues(r.Method, r.URL.Path, strconv.Itoa(rw.statusCode)).Inc()
		requestDuration.WithLabelValues(r.Method, r.URL.Path).Observe(duration)
	})
}

type responseWriter struct {
	http.ResponseWriter
	statusCode int
}

func (rw *responseWriter) WriteHeader(code int) {
	rw.statusCode = code
	rw.ResponseWriter.WriteHeader(code)
}

// Prometheus 暴露端点:
// 需要在路由中注册:
// http.Handle("/metrics", promhttp.Handler())
// → 暴露端点: http://localhost:8080/metrics
// → 返回格式:
// # HELP http_requests_total Total number of HTTP requests
// # TYPE http_requests_total counter
// http_requests_total{method="GET",path="/api/v1/users",status="200"} 15234
// http_requests_total{method="POST",path="/api/v1/users",status="201"} 892
// # HELP http_request_duration_seconds HTTP request duration
// # TYPE http_request_duration_seconds histogram
// http_request_duration_seconds_bucket{le="0.1",method="GET",path="/api/v1/users"} 5234
// http_request_duration_seconds_bucket{le="+Inf",method="GET",path="/api/v1/users"} 6000
// http_request_duration_seconds_sum{method="GET",path="/api/v1/users"} 45.2
// http_request_duration_seconds_count{method="GET",path="/api/v1/users"} 6000
```

---

## 第三部分：OpenTelemetry 源码级深度

### 3.1 核心架构 — Trace/Span/Metric/Log

```go
// otel.go — OpenTelemetry 核心抽象
package otel

// 四大核心概念:
// ┌──────────────────────────────────────────────────────┐
│  Trace (追踪)                                          │
│  ├─ Span (跨度)                                       │
│  │  ├─ SpanContext (上下文)                           │
│  │  │  ├─ TraceID (32-char hex)  ← 一次请求的 ID       │
│  │  │  ├─ SpanID (16-char hex)   ← 一次操作的 ID       │
│  │  │  └─ TraceFlags (采样标记)                         │
│  │  ├─ Attributes (属性/标签)                          │
│  │  │  ├─ service.name: "user-service"               │
│  │  │  ├─ http.method: "GET"                         │
│  │  │  └─ http.status_code: 200                       │
│  │  ├─ Events (事件)                                  │
│  │  │  └─ timestamp + name + attributes               │
│  │  ├─ Links (链接) — 关联其他 Span                    │
│  │  └─ Status (状态)                                  │
│  │     └─ Unset/Ok/Error                              │
│  └─ Trace (完整链路 = 所有 Span 的集合)                │
│                                                        │
│  Metric (指标)                                         │
│  ├─ Counter (只增)                                     │
│  ├─ Gauge (可增可减)                                   │
│  ├─ Histogram (分布统计)                               │
│  └─ UpDownCounter (可增可减)                           │
│                                                        │
│  Log (日志)                                            │
│  ├─ TraceID (关联 trace)                               │
│  ├─ SpanID (关联 span)                                 │
│  ├─ Level (INFO/WARN/ERROR)                           │
│  └─ Body (日志正文)                                    │
└──────────────────────────────────────────────────────┘

// Trace 传播 — W3C Trace Context 标准
// HTTP Header 中传递 trace context:
// Traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01
// └──┘└────trace-id────────────┘└───span-id───┘└─flags─┘
//
// Traceflags:
// 0x00 = 未采样
// 0x01 = 已采样

// Go 实现:
// ctx := trace.NewSpanContext(trace.SpanContextConfig{
//     TraceID:    trace.TraceID{...},
//     SpanID:     trace.SpanID{...},
//     TraceFlags: trace.FlagsSampled,
// })
// carrier := propagation.HeaderCarrier(http.Header)
// propagator := otel.GetTextMapPropagator()
// propagator.Inject(ctx, carrier) // 注入到 HTTP Header

// 接收端:
// ctx := propagator.Extract(context.Background(), carrier)
// ctx, span := tracer.Start(ctx, "handle-request", trace.WithSpanKind(trace.SpanKindServer))
```

### 3.2 采样策略 — 源码级

```go
// sampler.go — 采样策略
package otel

type SamplingStrategy int

const (
	SamplingAlwaysOn  SamplingStrategy = iota  // 始终采样 (100%)
	SamplingAlwaysOff                           // 从不采样 (0%)
	SamplingTraceIDRatio                        // 按 Trace ID 比例采样
	SamplingParentBased                         // 基于父 Span 决策
)

// 推荐配置: 父级采样决定子级采样
// ParentBased(Root(1%), RemoteParentAlwaysSample(), RemoteParentAlwaysIgnore())
//
// 含义:
// 1. 根 Span 以 1% 概率采样 (降低存储成本)
// 2. 如果父 Span 已采样 → 子 Span 也采样 (保证链路完整)
// 3. 如果父 Span 未采样 → 子 Span 不采样

// TraceIDRatioBased 实现:
// func (s TraceIDRatioBased) ShouldSample(params SamplingParameters) SamplingResult {
//     // 将 TraceID 转为 uint64
//     id := binary.BigEndian.Uint64(params.TraceID[0:8])
//     // 与上限比较
//     upperBound := uint64(s.ratio * math.MaxUint64)
//     if id <= upperBound {
//         return SamplingResult{Decision: RecordAndSample}
//     }
//     return SamplingResult{Decision: Drop}
// }

// 采样率推荐:
// | 环境 | 采样率 | 理由 |
// |------|--------|------|
// | 生产 | 1-5% | 控制存储成本 |
// | 预发 | 10-50% | 平衡成本和覆盖 |
// | 开发 | 100% | 调试需要 |
// | 错误 | 100% | 只采样错误 Span (ErrorSampler) |
```

### 3.3 Go SDK 集成 — 完整链路追踪

```go
// tracer.go — Go 应用 OpenTelemetry 集成
package otel

import (
	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/exporters/otlp/otlpmetric/otlpmetricgrpc"
	"go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracegrpc"
	"go.opentelemetry.io/otel/sdk/metric"
	"go.opentelemetry.io/otel/sdk/resource"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
	semconv "go.opentelemetry.io/otel/semconv/v1.21.0"
)

// InitTracer 初始化 tracer
func InitTracer() (*sdktrace.TracerProvider, error) {
	// 1. 创建资源 (属性)
	res, err := resource.New(context.Background(),
		resource.WithFromEnv(),     // 环境变量: OTEL_SERVICE_NAME
		resource.WithProcess(),     // 进程信息 (PID, exe name)
		resource.WithHost(),        // 主机信息
		resource.WithTelemetrySDK(),// SDK 版本信息
		resource.WithAttributes(
			semconv.ServiceName("my-api-service"),
			semconv.ServiceVersion("1.2.3"),
			semconv.DeploymentEnvironment("production"),
		),
	)
	if err != nil {
		return nil, err
	}

	// 2. 创建 OTLP Exporter (发送到 Tempo/Jaeger/Collector)
	traceExporter, err := otlptracegrpc.New(context.Background())
	if err != nil {
		return nil, err
	}

	// 3. 配置采样 (父级采样 + TraceID 比例)
	sampler := sdktrace.ParentBased(
		sdktrace.TraceIDRatioBased(0.05), // 根 Span 5% 采样
		sdktrace.WithRemoteParentSampled(sdktrace.AlwaysSample()),
		sdktrace.WithRemoteParentNotSampled(sdktrace.AlwaysSample()),
	)

	// 4. 创建 TracerProvider
	tp := sdktrace.NewTracerProvider(
		sdktrace.WithResource(res),
		sdktrace.WithSampler(sampler),
		sdktrace.WithBatcher(traceExporter), // 批量发送
		sdktrace.WithIDGenerator(),
	)

	otel.SetTracerProvider(tp)
	return tp, nil
}

// 中间件 — 自动注入 trace context
func TracingMiddleware(next http.Handler) http.Handler {
	tracer := otel.Tracer("my-api-service")
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		ctx, span := tracer.Start(
			r.Context(),
			r.URL.Path,
			trace.WithAttributes(
				semconv.HTTPMethod(r.Method),
				semconv.HTTPURL(r.URL.String()),
				semconv.NetPeerIP(r.RemoteAddr),
			),
			trace.WithSpanKind(trace.SpanKindServer),
		)
		defer span.End()

		// 注入 trace context 到下游请求
		req := r.WithContext(ctx)
		otel.GetTextMapPropagator().Inject(ctx, propagation.HeaderCarrier(req.Header))

		rw := &responseWriter{ResponseWriter: w, statusCode: 200}
		next.ServeHTTP(rw, req)

		span.SetStatus(codes.Ok, "")
		span.SetAttributes(semconv.HTTPStatusCode(rw.statusCode))
	})
}

// 跨服务调用 — HTTP 客户端自动注入 trace
func TracedHTTPClient() *http.Client {
	transport := &http.Transport{}
	wrapped := &roundTripper{
		transport: transport,
		tracer:    otel.Tracer("my-api-client"),
	}
	return &http.Client{Transport: wrapped}
}

type roundTripper struct {
	transport http.RoundTripper
	tracer    trace.Tracer
}

func (rt *roundTripper) RoundTrip(req *http.Request) (*http.Response, error) {
	ctx, span := rt.tracer.Start(
		req.Context(),
		req.Method+" "+req.URL.Path,
		trace.WithSpanKind(trace.SpanKindClient),
		trace.WithAttributes(
			semconv.HTTPMethod(req.Method),
			semconv.HTTPURL(req.URL.String()),
		),
	)
	defer span.End()
	
	otel.GetTextMapPropagator().Inject(ctx, propagation.HeaderCarrier(req.Header))
	return rt.transport.RoundTrip(req.WithContext(ctx))
}
```

---

## 第四部分：Grafana 实战

### 4.1 数据源配置

```yaml
# datasource.yaml — Grafana 数据源
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    jsonData:
      timeInterval: 15s       # 默认查询间隔
      queryTimeout: 60s       # 查询超时
      httpMethod: POST        # POST 方式查询
      exemplarTraceIdDestinations:  # 从指标跳转到 trace
        - name: trace_id
          datasourceUid: tempo

  - name: Tempo
    type: tempo
    access: proxy
    url: http://tempo:3200
    jsonData:
      tracesToLogs:            # Trace 跳转日志
        datasourceUid: loki
      nodeGraph:
        enabled: true
      tracesToMetrics:         # Trace 跳转指标
        datasourceUid: prometheus
      serviceMap:
        datasourceUid: prometheus
      search:
        enabled: true

  - name: Loki
    type: loki
    access: proxy
    url: http://loki:3100
    jsonData:
      maxLines: 1000           # 最大返回行数
      prometheusMode: true     # 启用 Promtail 集成
      prometheusScrape: true
```

### 4.2 关键 Dashboard 模板

```
推荐的 Dashboard 模板 (可以直接导入):

1. K8s Cluster Overview (Node/Pod 级别)
   - Nodes: CPU/Memory/Network/Disk I/O
   - Pods: CPU/Memory/Restart Count
   - 导入 ID: 315 (Kubernetes / Views / Cluster Total)

2. K8s Deployment Overview
   - Replicas Available/Unavailable
   - Request/Limit 对比
   - HPA 缩放量
   - 导入 ID: 2246 (Kubernetes / Compute / Deployment)

3. Prometheus 自监控
   - TSDB 健康状态
   - Query 性能
   - Target 健康
   - 导入 ID: 3662 (Prometheus)

4. 应用服务监控 (Go 应用)
   - HTTP 请求速率/延迟/错误率 (RED 方法)
   - Go Runtime (GC, Goroutine, Memory)
   - gRPC 请求 (如有)
   - 自定义业务指标
   - 导入 ID: 8704 (Go Application Dashboard)

5. 数据库监控
   - MySQL: QPS, 连接数, 锁等待, 慢查询
   - Redis: 命中率, 内存, 连接, 慢查询
   - 导入 ID: 8919 (MySQL), 763 (Redis)
```

---

## 第五部分：实战排障与调优

### 5.1 常见问题速查

| 症状 | 可能原因 | 排查命令 | 解决方案 |
|------|----------|----------|----------|
| **Prometheus 内存高** | 指标基数过大/查询慢 | `/debug/pprof/heap` | 减少 label 基数, 使用 Recording Rule |
| **Prometheus 查询慢** | 无索引/大窗口/复杂计算 | `/debug/requests` | 加 Recording Rule, 限制时间范围 |
| **Target 丢失** | SD 配置错误/网络不通 | `Targets` 页面 | 检查 Service Discovery 日志 |
| **Trace 丢失** | 采样率 0/Exporter 未配置 | `OTEL_EXPORTER_OTLP_ENDPOINT` | 检查 Exporter 配置, 检查网络 |
| **Span 不完整** | 链路断裂/Header 丢失 | 检查 HTTP Header | 检查中间件是否注入 Context |
| **Grafana 慢** | 查询超时/数据源延迟 | 浏览器 Network 面板 | 检查数据源延迟, 加 Recording Rule |
| **告警风暴** | 未配置抑制/分组 | Alertmanager 配置 | 配置 Inhibit Rules, 调整 group_by |

### 5.2 性能调优

```yaml
# Prometheus 调优:
global:
  scrape_interval: 15s      # 拉取间隔 (默认 15s)
  evaluation_interval: 15s  # 规则评估间隔
  scrape_timeout: 10s       # 拉取超时

  # 存储优化
  storage:
    tsdb:
      out-of-order-time-window: 5m  # 允许乱序数据
    retention: 15d                  # 数据保留天数
    tsdb_retention_size: 50GB       # 最大存储量

# OTel Collector 调优:
exporters:
  otlp/tempo:
    endpoint: tempo:4317
    tls:
      insecure: true
    sending_queue:
      enabled: true
      num_consumers: 10
      queue_size: 5000        # 队列缓冲, 应对 burst
    retry_on_failure:
      enabled: true
      initial_interval: 5s
      max_interval: 30s
      max_elapsed_time: 300s
```

---

## 第六部分：自测

### Q1：Prometheus 的 Histogram 和 Summary 有什么区别？为什么推荐用 Histogram？

<details>
<summary>点击查看参考答案</summary>

**Histogram**:
- 服务端计算 bucket 计数 (Prometheus 侧)
- 通过 `histogram_quantile()` 函数计算分位数
- 内存占用小，只维护固定 bucket 计数
- 适合大规模指标

**Summary**:
- 客户端计算分位数 (应用侧)
- 维护滑动窗口统计，内存开销大
- 不适合分布式场景 (多个实例合并后分位数不准)

**为什么用 Histogram**:
1. 内存占用少
2. 分布式聚合准确 (Prometheus 聚合多个实例的 bucket 后计算分位数)
3. 支持预计算 (Recording Rule)
4. Prometheus 官方推荐

```go
// 推荐: Histogram + DefBuckets
requestDuration := promauto.NewHistogramVec(
    prometheus.HistogramOpts{
        Name:    "http_request_duration_seconds",
        Help:    "Duration in seconds",
        Buckets: []float64{0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10},
    },
    []string{"method", "path"},
)
// 查询 P95: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))
```
</details>

### Q2：OpenTelemetry 的采样策略中，为什么推荐 "ParentBased(Root(1%))"？

<details>
<summary>点击查看参考答案</summary>

**原因**:

1. **成本控制**: 100% 采样会产生海量数据，存储和计算成本极高。1-5% 采样率可大幅降低成本。

2. **链路完整性**: 如果只用 TraceIDRatioBased 独立采样每个 Span，会导致链路断裂——父 Span 采样了但子 Span 没采样。ParentBased 确保如果父级采样了，子级也采样，保持完整链路。

3. **错误优先**: 可以组合 ErrorSampler——只采样错误的 Span，正常流量低采样。

```
推荐配置:
ParentBased(
    Root(1%),                    // 正常流量: 1% 采样
    RemoteParentSampled(AlwaysSample()),   // 上游已采样 → 全部采样
    RemoteParentNotSampled(Drop()),        // 上游未采样 → 丢弃
    LocalParentSampled(AlwaysSample()),    // 本地已采样 → 全部采样
    LocalParentNotSampled(Drop()),         // 本地未采样 → 丢弃
)

效果:
- 正常流量: ~1% Span 被记录
- 错误流量: 100% Span 被记录 (用 ErrorSampler)
- 链路完整: 父级采样 → 子级采样, 不会出现断裂
```
</details>

### Q3：Prometheus 的告警抑制 (Inhibit Rule) 实际场景是什么？

<details>
<summary>点击查看参考答案</summary>

**实际场景**: Node 宕机时，避免下面的 Pod 告警风暴。

```
没有抑制:
Node1 宕机
├── Pod-A CrashLoopBackOff ← 告警
├── Pod-B CrashLoopBackOff ← 告警
├── Pod-C CrashLoopBackOff ← 告警
├── Pod-D CrashLoopBackOff ← 告警
└── Pod-E CrashLoopBackOff ← 告警
= 5 条告警 (但其实都是 Node1 宕机的原因)

有抑制:
Node1 宕机 → 只触发 NodeNotReady 告警
→ 抑制同 namespace 下所有 Pod 的 CrashLoopBackOff
= 1 条告警 (真正需要关注的根因告警)

配置:
inhibit_rules:
  - source_match:
      alertname: NodeNotReady
      severity: critical
    target_match:
      alertname: PodCrashLoopBackOff
      severity: warning
    equal: ['namespace']
    # 当 NodeNotReady 触发时, 抑制同 namespace 的 PodCrashLoopBackOff
```
</details>

### Q4：OTel Collector 的 sending_queue 有什么用？

<details>
<summary>点击查看参考答案</summary>

**作用**: 应对 OTel Exporter 不可用或网络波动时的数据缓冲。

**工作原理**:
```
Span 产生 → OTel SDK → OTel Collector → sending_queue → OTLP Exporter → Tempo
                                                ↑
                                        网络中断时, 缓存到队列
                                        网络恢复后, 自动重试发送
```

**关键参数**:
- `num_consumers`: 并发消费者数量 (默认 10)
- `queue_size`: 最大缓冲量 (默认 5000)
- `retry_on_failure.enabled`: 启用自动重试
- `initial_interval`: 首次重试间隔
- `max_interval`: 最大重试间隔
- `max_elapsed_time`: 最大重试总时间

**生产配置推荐**:
```yaml
exporters:
  otlp/tempo:
    sending_queue:
      enabled: true
      num_consumers: 20  # 提高并发
      queue_size: 10000  # 缓存 10K spans
    retry_on_failure:
      enabled: true
      initial_interval: 5s
      max_interval: 60s
      max_elapsed_time: 600s
```

**权衡**: 队列越大，丢数据概率越低，但内存占用越高。需要根据实例内存和 Span 大小估算。
</details>

---

## 第七部分：动手验证

### 7.1 本地搭建可观测性栈 (Prometheus + Grafana + OTel + Tempo)

```bash
# 使用 docker-compose 快速搭建
cat > docker-compose.yml << 'EOF'
version: '3.8'
services:
  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    command: --config.file=/etc/prometheus/prometheus.yml

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin

  tempo:
    image: grafana/tempo:latest
    ports:
      - "3200:3200"   # gRPC (接收 Trace)
      - "9095:9095"   # HTTP (接收 HTTP Trace)
    command: -config.file=/etc/tempo/tempo.yml

  loki:
    image: grafana/loki:latest
    ports:
      - "3100:3100"

  # 你的 Go 应用需要集成 OTel:
  # go run -mod=mod main.go
EOF

docker-compose up -d
```

### 7.2 Go 应用集成验证

```bash
# 1. 创建 Go 项目
cd /tmp && mkdir otel-demo && cd otel-demo
go mod init otel-demo

# 2. 添加依赖
go get go.opentelemetry.io/otel
go get go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracegrpc
go get go.opentelemetry.io/otel/sdk
go get github.com/prometheus/client_golang/prometheus

# 3. 编写应用代码 (参考上方示例)
# 4. 运行应用 → 访问 localhost:8080/metrics 查看指标
# 5. 访问 Grafana localhost:3000 查看 Dashboard
```

---

*本文档基于 Prometheus v2.48+、OpenTelemetry v1.22+、Grafana v10.x 整理。建议配合实际集群体验。*
