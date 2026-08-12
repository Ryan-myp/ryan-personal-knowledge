# API 网关模式深度实现

> **文档级别**: Level 5 - 专家级  
> **创建日期**: 2026-08-13  
> **状态**: ✅ 已补齐

---

## 一、网关核心职责

```
┌─────────────────────────────────────────────────────────────────────┐
│                     API Gateway 职责层                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  客户端请求                                                  │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              │                                      │
│  ┌─────────────────────────▼─────────────────────────────────┐   │
│  │  1. 路由分发 (Routing)    2. 协议转换 (Protocol)          │   │
│  │     ─ HTTP → gRPC         ─ REST → GraphQL               │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              │                                      │
│  ┌─────────────────────────▼─────────────────────────────────┐   │
│  │  3. 认证授权 (Auth)      4. 限流熔断 (Resilience)         │   │
│  │     ─ JWT 验证            ─ 令牌桶限流                      │   │
│  │     ─ RBAC 鉴权           ─ 熔断器模式                      │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              │                                      │
│  ┌─────────────────────────▼─────────────────────────────────┐   │
│  │  5. 日志监控 (Observability) 6. 请求聚合 (Aggregation)     │   │
│  │     ─ Access Log          ─ Batch Request                  │   │
│  │     ─ Metrics             ─ Response Merging               │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              │                                      │
│  ┌─────────────────────────▼─────────────────────────────────┐   │
│  │  后端服务集群                                              │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 二、Go 网关实现

### 2.1 核心结构

```go
// 文件: gateway/core/gateway.go
package gateway

import (
    "context"
    "net/http"
    "sync"
)

// ─── 网关配置 ───
type Config struct {
    Port           int
    Timeout        time.Duration
    RateLimit      int
    CORS           CORSConfig
    Routes         []RouteConfig
}

type RouteConfig struct {
    Path     string
    Methods  []string
    Upstream string
    Middlewares []MiddlewareName
}

// ─── 网关主体 ───
type Gateway struct {
    config    Config
    router    *Router
    middlewares []Middleware
    metrics   *MetricsCollector
    
    mu      sync.RWMutex
    started bool
}

// ─── 中间件接口 ───
type Middleware interface {
    Name() string
    Handle(next http.Handler) http.Handler
}

// ─── 中间件链 ───
type MiddlewareChain struct {
    middlewares []Middleware
}

func (mc *MiddlewareChain) Add(m Middleware) {
    mc.middlewares = append(mc.middlewares, m)
}

func (mc *MiddlewareChain) Execute(handler http.Handler) http.Handler {
    for i := len(mc.middlewares) - 1; i >= 0; i-- {
        handler = mc.middlewares[i].Handle(handler)
    }
    return handler
}
```

### 2.2 限流中间件

```go
// 文件: gateway/middleware/rate_limiter.go
package middleware

import (
    "net/http"
    "sync"
    "time"
)

// ─── 令牌桶限流器 ───
type TokenBucket struct {
    tokens     float64
    maxTokens  float64
    refillRate float64 // tokens/second
    lastRefill time.Time
    
    mu sync.Mutex
}

func NewTokenBucket(maxTokens, refillRate float64) *TokenBucket {
    return &TokenBucket{
        tokens:     maxTokens,
        maxTokens:  maxTokens,
        refillRate: refillRate,
        lastRefill: time.Now(),
    }
}

func (tb *TokenBucket) Allow() bool {
    tb.mu.Lock()
    defer tb.mu.Unlock()
    
    now := time.Now()
    elapsed := now.Sub(tb.lastRefill).Seconds()
    tb.tokens = math.Min(tb.maxTokens, tb.tokens + elapsed * tb.refillRate)
    tb.lastRefill = now
    
    if tb.tokens >= 1 {
        tb.tokens--
        return true
    }
    return false
}

// ─── 基于 IP 的限流 ───
type IPRateLimiter struct {
    buckets map[string]*TokenBucket
    mu      sync.RWMutex
    ttl     time.Duration
}

func NewIPRateLimiter(limit, burst int) *IPRateLimiter {
    return &IPRateLimiter{
        buckets: make(map[string]*TokenBucket),
        ttl:     10 * time.Minute,
    }
}

func (rl *IPRateLimiter) Allow(ip string) bool {
    rl.mu.Lock()
    defer rl.mu.Unlock()
    
    bucket, exists := rl.buckets[ip]
    if !exists {
        bucket = NewTokenBucket(float64(burst), float64(limit))
        rl.buckets[ip] = bucket
    }
    
    return bucket.Allow()
}

// ─── 中间件实现 ───
type RateLimitMiddleware struct {
    limiter *IPRateLimiter
}

func (m *RateLimitMiddleware) Name() string {
    return "rate-limit"
}

func (m *RateLimitMiddleware) Handle(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        ip := getClientIP(r)
        
        if !m.limiter.Allow(ip) {
            w.Header().Set("Retry-After", "1")
            http.Error(w, "429 Too Many Requests", http.StatusTooManyRequests)
            return
        }
        
        next.ServeHTTP(w, r)
    })
}
```

### 2.3 熔断器中间件

```go
// 文件: gateway/middleware/circuit_breaker.go
package middleware

import (
    "errors"
    "net/http"
    "sync"
    "time"
)

var ErrCircuitOpen = errors.New("circuit breaker is open")

type State int

const (
    Closed State = iota
    Open
    HalfOpen
)

type CircuitBreaker struct {
    state            State
    failureCount     int
    successCount     int
    failureThreshold int
    successThreshold int
    timeout          time.Duration
    lastFailureTime  time.Time
    
    mu sync.Mutex
}

func NewCircuitBreaker(failureTh, successTh int, timeout time.Duration) *CircuitBreaker {
    return &CircuitBreaker{
        state:            Closed,
        failureThreshold: failureTh,
        successThreshold: successTh,
        timeout:          timeout,
    }
}

func (cb *CircuitBreaker) Execute(fn func() error) error {
    cb.mu.Lock()
    defer cb.mu.Unlock()
    
    switch cb.state {
    case Open:
        if time.Since(cb.lastFailureTime) > cb.timeout {
            cb.state = HalfOpen
            cb.successCount = 0
        } else {
            return ErrCircuitOpen
        }
    }
    
    err := fn()
    
    if err != nil {
        cb.failureCount++
        cb.lastFailureTime = time.Now()
        if cb.failureCount >= cb.failureThreshold && cb.state != Open {
            cb.state = Open
        }
        return err
    }
    
    cb.failureCount = 0
    if cb.state == HalfOpen {
        cb.successCount++
        if cb.successCount >= cb.successThreshold {
            cb.state = Closed
        }
    }
    return nil
}

// ─── 熔断器中间件 ───
type CircuitBreakerMiddleware struct {
    breakers map[string]*CircuitBreaker
    mu       sync.RWMutex
}

func NewCircuitBreakerMiddleware() *CircuitBreakerMiddleware {
    return &CircuitBreakerMiddleware{
        breakers: make(map[string]*CircuitBreaker),
    }
}

func (m *CircuitBreakerMiddleware) getBreaker(service string) *CircuitBreaker {
    m.mu.Lock()
    defer m.mu.Unlock()
    
    if b, exists := m.breakers[service]; exists {
        return b
    }
    
    b := NewCircuitBreaker(5, 3, 30*time.Second)
    m.breakers[service] = b
    return b
}

func (m *CircuitBreakerMiddleware) Name() string {
    return "circuit-breaker"
}

func (m *CircuitBreakerMiddleware) Handle(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        service := getUpstreamService(r)
        breaker := m.getBreaker(service)
        
        err := breaker.Execute(func() error {
            // 转发请求
            return nil
        })
        
        if err == ErrCircuitOpen {
            w.WriteHeader(http.StatusServiceUnavailable)
            w.Write([]byte(`{"error":"service unavailable"}`))
            return
        }
        
        next.ServeHTTP(w, r)
    })
}
```

---

## 三、网关 vs Service Mesh

```
┌─────────────────────────────────────────────────────────────────┐
│                   网关 vs Service Mesh 对比                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  特性              API Gateway          Service Mesh           │
│  ───────────────────────────────────────────────────────────  │
│  部署位置          入口层                 Sidecar                │
│  服务发现          需配置                 自动发现                │
│  协议支持          HTTP/gRPC             多协议                  │
│  语言无关          否 (需 SDK)            是                      │
│  运维复杂度        中                     高                     │
│  适用场景          公网入口                内网服务通信            │
│                                                                 │
│  推荐组合:                                                     │
│  ├─ 外层: API Gateway (Kong/Traefik)                           │
│  └─ 内层: Service Mesh (Istio/Linkerd)                         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 四、参考资料

```
核心项目:
├── Kong (开源网关)
├── Envoy (云原生代理)
├── Traefik (现代网关)
└── NGINX Plus (商业方案)

设计模式:
├── Sidecar Pattern
├── Ambassador Pattern
└── Gateway Aggregation Pattern
```

---

*文档版本: v1.0*  
*最后更新: 2026-08-13*  
*作者: Ryan*
