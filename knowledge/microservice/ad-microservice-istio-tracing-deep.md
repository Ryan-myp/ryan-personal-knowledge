# 微服务深度：服务网格/链路追踪/熔断降级源码级

> 从 Istio 到链路追踪，逐行解析微服务核心组件

---

## 第一部分：服务网格（Istio）源码深度

### Istio 架构

```
Istio 架构：
┌─────────────────────────────────────────────────────────────────────┐
│ Control Plane                                                        │
│ ├── Pilot: 服务发现和配置分发                                         │
│ ├── Galley: 配置验证                                                 │
│ ├── Citadel: 证书管理                                                │
│ └── Mixer: 策略检查和遥测收集                                        │
│                                                                     │
│ Data Plane                                                           │
│ ├── Envoy Sidecar: 每个 Pod 一个 sidecar                             │
│ ├── 流量拦截: iptables → sidecar → app                              │
│ ├── 双向 TLS: mTLS 自动加密                                         │
│ └── 遥测: 访问日志 + 指标 + 追踪                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Envoy Filter 源码

```yaml
# Istio VirtualService：流量路由
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: ad-platform
spec:
  hosts:
  - ad-platform.production.svc.cluster.local
  http:
  - match:
    - headers:
        x-canary:
          exact: "true"
    route:
    - destination:
        host: ad-platform
        subset: canary
        port:
          number: 8080
    weight: 100
  - route:
    - destination:
        host: ad-platform
        subset: stable
        port:
          number: 8080
    weight: 90
  - route:
    - destination:
        host: ad-platform
        subset: canary
        port:
          number: 8080
    weight: 10
```

```yaml
# Istio DestinationRule：服务拆分
apiVersion: networking.istio.io/v1beta1
kind: DestinationRule
metadata:
  name: ad-platform
spec:
  host: ad-platform
  subsets:
  - name: stable
    labels:
      version: v1
  - name: canary
    labels:
      version: v2
```

---

## 第二部分：链路追踪源码深度

### OpenTelemetry 架构

```
OpenTelemetry 链路追踪：
┌─────────────────────────────────────────────────────────────────────┐
│ Trace: 一次完整的请求链路                                             │
│ ├── Span: 一个操作（API 调用/DB 查询）                               │
│ │   ├── trace_id: 全局唯一                                          │
│ │   ├── span_id: 当前 span 唯一                                     │
│ │   ├── parent_span_id: 父 span ID                                  │
│ │   ├── attributes: 键值对（HTTP 方法/状态码等）                      │
│ │   ├── events: 时间戳事件                                          │
│ │   └── links: 关联的其他 span                                      │
│                                                                     │
│ Exporter: 发送到 Jaeger/Zipkin/Prometheus                             │
└─────────────────────────────────────────────────────────────────────┘
```

### Go 链路追踪实现

```go
package tracing

import (
    "go.opentelemetry.io/otel"
    "go.opentelemetry.io/otel/trace"
    "context"
)

// Tracer 链路追踪器
type Tracer struct {
    tracer trace.Tracer
}

// NewTracer 创建追踪器
func NewTracer(serviceName string) *Tracer {
    provider := otel.GetTracerProvider()
    tracer := provider.Tracer(serviceName)
    return &Tracer{tracer: tracer}
}

// DoWithSpan 在 span 中执行函数
func (t *Tracer) DoWithSpan(
    ctx context.Context,
    name string,
    fn func(context.Context) error,
) error {
    ctx, span := t.tracer.Start(ctx, name)
    defer span.End()
    
    // 执行函数
    err := fn(ctx)
    
    // 记录错误
    if err != nil {
        span.RecordError(err)
        span.SetStatus(1, err.Error())
    }
    
    return err
}

// HTTPMiddleware HTTP 中间件
func (t *Tracer) HTTPMiddleware(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        ctx, span := t.tracer.Start(
            r.Context(),
            r.Method+" "+r.URL.Path,
            trace.WithAttributes(
                attribute.String("http.method", r.Method),
                attribute.String("http.url", r.URL.Path),
            ),
        )
        defer span.End()
        
        // 包装 ResponseWriter
        wrapped := &responseWriter{ResponseWriter: w, statusCode: 200}
        
        // 执行下一个中间件
        next.ServeHTTP(wrapped, r.WithContext(ctx))
        
        // 记录状态码
        span.SetAttributes(
            attribute.Int("http.status_code", wrapped.statusCode),
        )
    })
}

type responseWriter struct {
    http.ResponseWriter
    statusCode int
}

func (w *responseWriter) WriteHeader(code int) {
    w.statusCode = code
    w.ResponseWriter.WriteHeader(code)
}
```

---

## 第三部分：熔断降级源码深度

### 熔断器实现

```go
package circuitbreaker

import (
    "sync"
    "time"
)

// State 熔断器状态
type State int

const (
    StateClosed State = iota
    StateOpen
    StateHalfOpen
)

// CircuitBreaker 熔断器
type CircuitBreaker struct {
    mu               sync.Mutex
    state            State
    failureCount     int
    successCount     int
    failureThreshold int
    successThreshold int
    timeout          time.Duration
    lastFailure      time.Time
}

// NewCircuitBreaker 创建熔断器
func NewCircuitBreaker(
    failureThreshold, successThreshold int,
    timeout time.Duration,
) *CircuitBreaker {
    return &CircuitBreaker{
        state:            StateClosed,
        failureThreshold: failureThreshold,
        successThreshold: successThreshold,
        timeout:          timeout,
    }
}

// Allow 是否允许请求
func (cb *CircuitBreaker) Allow() bool {
    cb.mu.Lock()
    defer cb.mu.Unlock()
    
    switch cb.state {
    case StateClosed:
        return true
    case StateOpen:
        if time.Since(cb.lastFailure) > cb.timeout {
            cb.state = StateHalfOpen
            cb.successCount = 0
            return true
        }
        return false
    case StateHalfOpen:
        return true
    }
    return false
}

// RecordSuccess 记录成功
func (cb *CircuitBreaker) RecordSuccess() {
    cb.mu.Lock()
    defer cb.mu.Unlock()
    
    switch cb.state {
    case StateClosed:
        cb.failureCount = 0
    case StateHalfOpen:
        cb.successCount++
        if cb.successCount >= cb.successThreshold {
            cb.state = StateClosed
            cb.failureCount = 0
        }
    }
}

// RecordFailure 记录失败
func (cb *CircuitBreaker) RecordFailure() {
    cb.mu.Lock()
    defer cb.mu.Unlock()
    
    cb.failureCount++
    cb.lastFailure = time.Now()
    
    switch cb.state {
    case StateClosed:
        if cb.failureCount >= cb.failureThreshold {
            cb.state = StateOpen
        }
    case StateHalfOpen:
        cb.state = StateOpen
    }
}

// GetState 获取当前状态
func (cb *CircuitBreaker) GetState() State {
    cb.mu.Lock()
    defer cb.mu.Unlock()
    return cb.state
}
```

### 降级策略

```go
package fallback

import (
    "context"
    "time"
)

// Fallback 降级处理器
type Fallback struct {
    cache       Cache
    defaultVal  interface{}
    timeout     time.Duration
}

// NewFallback 创建降级处理器
func NewFallback(cache Cache, defaultVal interface{}) *Fallback {
    return &Fallback{
        cache: cache,
        defaultVal: defaultVal,
        timeout: 5 * time.Second,
    }
}

// GetWithFallback 获取数据，带降级
func (f *Fallback) GetWithFallback(
    ctx context.Context,
    key string,
    fetcher func(context.Context) (interface{}, error),
) (interface{}, error) {
    // 1. 尝试从缓存获取
    if val, ok := f.cache.Get(key); ok {
        return val, nil
    }
    
    // 2. 尝试从上游获取
    ctx, cancel := context.WithTimeout(ctx, f.timeout)
    defer cancel()
    
    val, err := fetcher(ctx)
    if err != nil {
        // 3. 降级：返回默认值
        return f.defaultVal, nil
    }
    
    // 4. 写入缓存
    f.cache.Set(key, val, 5*time.Minute)
    
    return val, nil
}
```

---

## 第四部分：自测题

### Q1: 服务网格解决了什么问题？

**A**: 将横切关注点（熔断/限流/监控/安全）从业务代码中抽离，放在 sidecar 中管理。

### Q2: 链路追踪的 trace_id 和 span_id 区别？

**A**: trace_id 标识一次完整请求，span_id 标识请求中的一个操作。

### Q3: 熔断器的三种状态？

**A**: Closed（正常）/ Open（熔断）/ Half-Open（试探）。

---

## 第五部分：生产实践

### 1. 服务网格

```
服务网格要点：
1. 渐进式引入
2. 监控 sidecar 资源
3. 配置灰度发布
4. 定期更新 Istio
```

### 2. 链路追踪

```
链路追踪要点：
1. 采样策略（10% 全量）
2. 采样率调整
3. 采样偏差修正
4. 日志关联
```

### 3. 熔断降级

```
熔断降级要点：
1. 合理设置阈值
2. 超时控制
3. 降级策略
4. 监控告警
```
