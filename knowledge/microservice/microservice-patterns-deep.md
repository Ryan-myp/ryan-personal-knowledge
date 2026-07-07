# 微服务架构模式深度实战

## 一、API Gateway 模式

### 1.1 为什么需要 API Gateway？

微服务架构中，客户端需要调用多个服务。API Gateway 作为统一入口，解决鉴权、限流、路由等问题。

**核心功能：**

| 功能 | 说明 | 实现方式 |
|------|------|----------|
| 路由转发 | 将请求转发到后端服务 | 反向代理 |
| 身份认证 | 验证用户身份 | JWT/OAuth2 |
| 限流熔断 | 防止系统过载 | 令牌桶/漏桶 |
| 日志监控 | 记录请求日志 | 结构化日志 |
| 协议转换 | HTTP/gRPC 转换 | 适配器模式 |

### 1.2 Go 实现 API Gateway

```go
package gateway

import (
	"context"
	"net/http"
	"net/http/httputil"
	"net/url"
	"sync"
	"time"
)

type APIGateway struct {
	routes      map[string]*Route
	middlewares []MiddlewareFunc
	timeout     time.Duration
	stats       *StatsCollector
	mu          sync.RWMutex
}

type Route struct {
	Path       string
	Backend    string
	Methods    []string
	Middleware []MiddlewareFunc
	Timeout    time.Duration
}

type MiddlewareFunc func(http.Handler) http.Handler

// AuthMiddleware 鉴权中间件
func (g *APIGateway) AuthMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		token := r.Header.Get("Authorization")
		if token == "" {
			http.Error(w, "Missing token", http.StatusUnauthorized)
			return
		}
		
		claims, err := ValidateJWT(token)
		if err != nil {
			http.Error(w, "Invalid token", http.StatusUnauthorized)
			return
		}
		
		ctx := context.WithValue(r.Context(), "userID", claims.UserID)
		next.ServeHTTP(w, r.WithContext(ctx))
	})
}

// RateLimitMiddleware 限流中间件
func (g *APIGateway) RateLimitMiddleware(limit int, window time.Duration) MiddlewareFunc {
	buckets := make(map[string]*TokenBucket)
	var mu sync.Mutex
	
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			clientIP := getClientIP(r)
			
			mu.Lock()
			bucket, exists := buckets[clientIP]
			if !exists {
				bucket = NewTokenBucket(limit, window)
				buckets[clientIP] = bucket
			}
			mu.Unlock()
			
			if !bucket.Allow() {
				g.stats.RecordRateLimit(clientIP)
				http.Error(w, "Rate limited", http.StatusTooManyRequests)
				return
			}
			next.ServeHTTP(w, r)
		})
	}
}

// ServeHTTP 处理请求
func (g *APIGateway) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	route := g.findRoute(r.URL.Path)
	if route == nil {
		http.Error(w, "Not found", http.StatusNotFound)
		return
	}
	
	backendURL, _ := url.Parse(route.Backend)
	proxy := httputil.NewSingleHostReverseProxy(backendURL)
	
	timeout := route.Timeout
	if timeout == 0 {
		timeout = 30 * time.Second
	}
	proxy.Timeout = timeout
	
	start := time.Now()
	proxy.ServeHTTP(w, r)
	duration := time.Since(start)
	
	g.stats.RecordRequest(route.Path, duration)
}

func (g *APIGateway) findRoute(path string) *Route {
	g.mu.RLock()
	defer g.mu.RUnlock()
	
	if route, ok := g.routes[path]; ok {
		return route
	}
	
	for routePath, route := range g.routes {
		if len(path) >= len(routePath) && path[:len(routePath)] == routePath {
			return route
		}
	}
	
	return nil
}
```

## 二、服务发现

### 2.1 服务发现模式

```
注册中心:
├── 服务注册: 服务启动时注册自己
├── 服务续约: 定期发送心跳
├── 服务注销: 服务关闭时注销
└── 服务拉取: 客户端获取服务列表

两种模式:
├── 客户端侧负载均衡
│   └── 客户端从注册中心获取服务列表
└── 服务端侧负载均衡
    └── 通过代理转发请求
```

### 2.2 Go 实现服务注册中心

```go
package discovery

import (
	"fmt"
	"sync"
	"time"
)

type ServiceInstance struct {
	ID            string            `json:"id"`
	Name          string            `json:"name"`
	Address       string            `json:"address"`
	Port          int               `json:"port"`
	Healthy       bool              `json:"healthy"`
	Tags          map[string]string `json:"tags"`
	LastHeartbeat time.Time         `json:"last_heartbeat"`
}

type ServiceRegistry struct {
	services map[string][]*ServiceInstance
	mu       sync.RWMutex
	ttl      time.Duration
	stopCh   chan struct{}
}

func NewServiceRegistry(ttl time.Duration) *ServiceRegistry {
	reg := &ServiceRegistry{
		services: make(map[string][]*ServiceInstance),
		ttl:      ttl,
		stopCh:   make(chan struct{}),
	}
	go reg.healthCheck()
	return reg
}

func (r *ServiceRegistry) Register(instance *ServiceInstance) error {
	r.mu.Lock()
	defer r.mu.Unlock()
	
	for _, existing := range r.services[instance.Name] {
		if existing.ID == instance.ID {
			existing.Address = instance.Address
			existing.Port = instance.Port
			existing.LastHeartbeat = time.Now()
			existing.Healthy = true
			return nil
		}
	}
	
	r.services[instance.Name] = append(r.services[instance.Name], instance)
	return nil
}

func (r *ServiceRegistry) GetInstances(name string) ([]*ServiceInstance, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()
	
	instances := r.services[name]
	if len(instances) == 0 {
		return nil, fmt.Errorf("no instances for %s", name)
	}
	
	healthy := make([]*ServiceInstance, 0)
	for _, inst := range instances {
		if inst.Healthy && time.Since(inst.LastHeartbeat) < r.ttl {
			healthy = append(healthy, inst)
		}
	}
	
	if len(healthy) == 0 {
		return nil, fmt.Errorf("no healthy instances for %s", name)
	}
	
	return healthy, nil
}

func (r *ServiceRegistry) healthCheck() {
	ticker := time.NewTicker(10 * time.Second)
	defer ticker.Stop()
	
	for {
		select {
		case <-ticker.C:
			r.checkHealth()
		case <-r.stopCh:
			return
		}
	}
}
```

## 三、熔断器

### 3.1 Circuit Breaker 状态机

```
CLOSED → OPEN (失败次数超过阈值)
OPEN → HALF_OPEN (等待恢复时间)
HALF_OPEN → CLOSED (成功次数达到阈值)
HALF_OPEN → OPEN (失败)
```

### 3.2 Go 实现

```go
package circuitbreaker

import (
	"sync"
	"time"
)

type State int

const (
	StateClosed State = iota
	StateOpen
	StateHalfOpen
)

type CircuitBreaker struct {
	state        State
	mu           sync.RWMutex
	failures     int
	successes    int
	maxFailures  int
	resetTimeout time.Duration
	lastFailure  time.Time
	halfOpenMax  int
}

func NewCircuitBreaker(maxFailures int, resetTimeout time.Duration) *CircuitBreaker {
	return &CircuitBreaker{
		state:        StateClosed,
		maxFailures:  maxFailures,
		resetTimeout: resetTimeout,
		halfOpenMax:  3,
	}
}

func (cb *CircuitBreaker) Allow() bool {
	cb.mu.RLock()
	defer cb.mu.RUnlock()
	
	switch cb.state {
	case StateClosed:
		return true
	case StateOpen:
		if time.Since(cb.lastFailure) > cb.resetTimeout {
			cb.mu.RUnlock()
			cb.mu.Lock()
			cb.state = StateHalfOpen
			cb.successes = 0
			cb.mu.Unlock()
			cb.mu.RLock()
			return true
		}
		return false
	case StateHalfOpen:
		return true
	default:
		return false
	}
}

func (cb *CircuitBreaker) RecordSuccess() {
	cb.mu.Lock()
	defer cb.mu.Unlock()
	
	if cb.state == StateHalfOpen {
		cb.successes++
		if cb.successes >= cb.halfOpenMax {
			cb.state = StateClosed
			cb.failures = 0
		}
	} else {
		cb.failures = 0
	}
}

func (cb *CircuitBreaker) RecordFailure() {
	cb.mu.Lock()
	defer cb.mu.Unlock()
	
	cb.failures++
	cb.lastFailure = time.Now()
	
	if cb.state == StateHalfOpen {
		cb.state = StateOpen
	} else if cb.failures >= cb.maxFailures {
		cb.state = StateOpen
	}
}
```

## 四、限流器

### 4.1 令牌桶算法

```
令牌桶:
├── 固定速率生成令牌
├── 请求消耗令牌
└── 无令牌则拒绝

滑动窗口:
├── 将时间窗口分成多个小格
├── 统计每个小格的请求数
└── 总和超过阈值则拒绝
```

### 4.2 Go 实现令牌桶

```go
package ratelimit

import (
	"sync"
	"time"
)

type TokenBucket struct {
	tokens     float64
	maxTokens  float64
	refillRate float64 // tokens per second
	lastRefill time.Time
	mu         sync.Mutex
}

func NewTokenBucket(maxTokens float64, refillRate float64) *TokenBucket {
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
	tb.tokens += elapsed * tb.refillRate
	if tb.tokens > tb.maxTokens {
		tb.tokens = tb.maxTokens
	}
	tb.lastRefill = now
	
	if tb.tokens >= 1 {
		tb.tokens--
		return true
	}
	return false
}
```

## 五、自测题

1. API Gateway 的核心功能有哪些？
2. Circuit Breaker 的三种状态如何转换？
3. 服务发现的健康检查机制是什么？
4. 令牌桶算法与滑动窗口算法各有什么优缺点？

## 六、动手验证

```bash
# 1. 实现 API Gateway
# 2. 实现服务注册中心
# 3. 实现熔断器
# 4. 集成测试
```
