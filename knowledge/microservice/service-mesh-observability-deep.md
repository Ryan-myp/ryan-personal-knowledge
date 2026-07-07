# Service Mesh 与可观测性深度实战

## 一、Service Mesh 架构

### 1.1 Istio 架构

```
┌─────────────────┐    ┌─────────────────┐
│   Control Plane │    │   Data Plane    │
│  (Istiod)       │    │  (Envoy Proxies)│
├─────────────────┤    ├─────────────────┤
│ Pilot           │    │ Sidecar Proxy   │
│ (服务发现)       │    │ (流量管理)       │
│ Galley          │    │                 │
│ (配置验证)       │    │                 │
│ Citadel         │    │                 │
│ (证书管理)       │    │                 │
└─────────────────┘    └─────────────────┘
```

### 1.2 Envoy Sidecar 实现

```go
package sidecar

import (
	"context"
	"fmt"
	"net/http"
	"time"
)

type Sidecar struct {
	proxyPort   int
	adminPort   int
	healthCheck *HealthChecker
}

func (s *Sidecar) Start(ctx context.Context) error {
	adminMux := http.NewServeMux()
	adminMux.HandleFunc("/ready", s.readyHandler)
	adminMux.HandleFunc("/health", s.healthHandler)
	
	adminServer := &http.Server{
		Addr:    fmt.Sprintf(":%d", s.adminPort),
		Handler: adminMux,
	}
	
	go func() {
		<-ctx.Done()
		adminServer.Shutdown(ctx)
	}()
	
	return adminServer.ListenAndServe()
}

func (s *Sidecar) readyHandler(w http.ResponseWriter, r *http.Request) {
	if s.healthCheck.IsReady() {
		w.WriteHeader(http.StatusOK)
	} else {
		w.WriteHeader(http.StatusServiceUnavailable)
	}
}
```

## 二、流量管理

### 2.1 灰度发布

```go
type CanaryRelease struct {
	routes       map[string]*Route
	weight       map[string]int
	migration    MigrationStrategy
}

func (c *CanaryRelease) UpdateWeight(service, version string, weight int) {
	c.weight[service+"-"+version] = weight
}

func (c *CanaryRelease) RouteRequest(service string) string {
	total := 0
	for _, w := range c.weight {
		total += w
	}
	
	r := rand.Intn(total)
	for version, w := range c.weight {
		r -= w
		if r < 0 {
			return version
		}
	}
	return ""
}
```

### 2.2 熔断与降级

```go
type FallbackHandler struct {
	circuitBreaker *circuitbreaker.CircuitBreaker
	fallbackFunc   func() interface{}
}

func (h *FallbackHandler) Handle(request interface{}) interface{} {
	if !h.circuitBreaker.Allow() {
		// 熔断，使用降级逻辑
		return h.fallbackFunc()
	}
	
	result, err := h.processRequest(request)
	if err != nil {
		h.circuitBreaker.RecordFailure()
		return h.fallbackFunc()
	}
	
	h.circuitBreaker.RecordSuccess()
	return result
}
```

## 三、可观测性

### 3.1 分布式追踪

```go
type Tracer struct {
	spans map[string]*Span
}

type Span struct {
	TraceID   string
	SpanID    string
	ParentID  string
	Service   string
	Operation string
	Timestamp time.Time
	Duration  time.Duration
	Tags      map[string]string
	Logs      []LogEntry
}

func (t *Tracer) StartSpan(operation, traceID string) *Span {
	span := &Span{
		TraceID:   traceID,
		SpanID:    generateID(),
		Timestamp: time.Now(),
		Service:   "my-service",
		Operation: operation,
		Tags:      make(map[string]string),
	}
	t.spans[span.SpanID] = span
	return span
}

func (s *Span) Finish() {
	s.Duration = time.Since(s.Timestamp)
}
```

### 3.2 链路传播

```go
type PropagationContext struct {
	TraceID    string
	SpanID     string
	ParentSpan string
}

func ExtractFromHeader(header http.Header) *PropagationContext {
	return &PropagationContext{
		TraceID:    header.Get("X-Trace-Id"),
		SpanID:     header.Get("X-Span-Id"),
		ParentSpan: header.Get("X-Parent-Span"),
	}
}

func InjectIntoHeader(ctx context.Context, header http.Header) {
	header.Set("X-Trace-Id", getTraceID(ctx))
	header.Set("X-Span-Id", getSpanID(ctx))
}
```

## 四、日志聚合

### 4.1 结构化日志

```go
type LogEntry struct {
	Timestamp time.Time `json:"timestamp"`
	Level     string    `json:"level"`
	Service   string    `json:"service"`
	TraceID   string    `json:"trace_id"`
	Message   string    `json:"message"`
	Fields    map[string]interface{} `json:"fields"`
}

func (l *Logger) Info(traceID string, msg string, fields map[string]interface{}) {
	entry := LogEntry{
		Timestamp: time.Now(),
		Level:     "INFO",
		Service:   l.service,
		TraceID:   traceID,
		Message:   msg,
		Fields:    fields,
	}
	l.output <- entry
}
```

## 五、自测题

1. Istio 的控制平面和数据平面各有什么职责？
2. 灰度发布的流量分配策略有哪些？
3. 分布式追踪如何串联多个微服务？

## 六、动手验证

```bash
# 1. 部署 Istio
# 2. 配置流量规则
# 3. 测试熔断降级
# 4. 监控分布式追踪
```
