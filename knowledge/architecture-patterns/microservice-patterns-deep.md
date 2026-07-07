# 微服务架构模式深度实战

## 一、API Gateway 模式

### 1.1 为什么需要 API Gateway？

微服务架构中，客户端需要调用多个服务。如果没有 Gateway：
- 客户端需要知道每个服务的地址
- 每个服务都要处理鉴权、限流、日志
- 跨域问题难以统一处理

API Gateway 作为统一入口，解决这些问题。

### 1.2 核心功能

| 功能 | 说明 | 实现方式 |
|------|------|----------|
| 路由转发 | 将请求转发到后端服务 | 反向代理 |
| 身份认证 | 验证用户身份 | JWT/OAuth2 |
| 限流熔断 | 防止系统过载 | 令牌桶/漏桶 |
| 日志监控 | 记录请求日志 | 结构化日志 |
| 协议转换 | HTTP/gRPC 转换 | 适配器模式 |
| 请求聚合 | 合并多个服务请求 | 组合模式 |

### 1.3 Go 实现 API Gateway

```go
package gateway

import (
	"context"
	"fmt"
	"net/http"
	"net/http/httputil"
	"net/url"
	"sync"
	"time"
)

// Route 路由配置
type Route struct {
	Path     string
	Backend  string
	Methods  []string
	Middleware []MiddlewareFunc
	Timeout  time.Duration
}

// MiddlewareFunc 中间件函数
type MiddlewareFunc func(http.Handler) http.Handler

// APIGateway API 网关
type APIGateway struct {
	routes      map[string]*Route
	middlewares []MiddlewareFunc
	stats       *StatsCollector
	mu          sync.RWMutex
}

// NewAPIGateway 创建网关
func NewAPIGateway() *APIGateway {
	return &APIGateway{
		routes: make(map[string]*Route),
		stats:  NewStatsCollector(),
	}
}

// AddRoute 添加路由
func (g *APIGateway) AddRoute(route *Route) {
	g.mu.Lock()
	defer g.mu.Unlock()
	g.routes[route.Path] = route
}

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
		
		// 将用户信息放入上下文
		ctx := context.WithValue(r.Context(), "userID", claims.UserID)
		ctx = context.WithValue(ctx, "roles", claims.Roles)
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
	// 应用全局中间件
	var handler http.Handler = http.HandlerFunc(g.handleRoute)
	for i := len(g.middlewares) - 1; i >= 0; i-- {
		handler = g.middlewares[i](handler)
	}
	handler.ServeHTTP(w, r)
}

func (g *APIGateway) handleRoute(w http.ResponseWriter, r *http.Request) {
	route := g.findRoute(r.URL.Path)
	if route == nil {
		http.Error(w, "Not found", http.StatusNotFound)
		return
	}
	
	// 应用路由级中间件
	var handler http.Handler = g.createProxy(route)
	for _, mw := range route.Middleware {
		handler = mw(handler)
	}
	
	start := time.Now()
	handler.ServeHTTP(w, r)
	duration := time.Since(start)
	
	g.stats.RecordRequest(route.Path, duration)
}

func (g *APIGateway) createProxy(route *Route) http.Handler {
	backendURL, _ := url.Parse(route.Backend)
	proxy := httputil.NewSingleHostReverseProxy(backendURL)
	
	// 设置超时
	timeout := route.Timeout
	if timeout == 0 {
		timeout = 30 * time.Second
	}
	proxy.FlushInterval = httputil.DefaultFlushInterval
	proxy.ErrorHandler = func(w http.ResponseWriter, r *http.Request, err error) {
		http.Error(w, "Service unavailable", http.StatusBadGateway)
	}
	
	return proxy
}

func (g *APIGateway) findRoute(path string) *Route {
	g.mu.RLock()
	defer g.mu.RUnlock()
	
	// 精确匹配
	if route, ok := g.routes[path]; ok {
		return route
	}
	
	// 前缀匹配
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

// ServiceInstance 服务实例
type ServiceInstance struct {
	ID        string            `json:"id"`
	Name      string            `json:"name"`
	Address   string            `json:"address"`
	Port      int               `json:"port"`
	Healthy   bool              `json:"healthy"`
	Tags      map[string]string `json:"tags"`
	Registered time.Time        `json:"registered"`
	LastHeartbeat time.Time    `json:"last_heartbeat"`
}

// ServiceRegistry 服务注册中心
type ServiceRegistry struct {
	services map[string][]*ServiceInstance
	mu       sync.RWMutex
	ttl      time.Duration
	stopCh   chan struct{}
}

// NewServiceRegistry 创建注册中心
func NewServiceRegistry(ttl time.Duration) *ServiceRegistry {
	reg := &ServiceRegistry{
		services: make(map[string][]*ServiceInstance),
		ttl:      ttl,
		stopCh:   make(chan struct{}),
	}
	
	// 启动健康检查协程
	go reg.healthCheck()
	
	return reg
}

// Register 注册服务
func (r *ServiceRegistry) Register(instance *ServiceInstance) error {
	r.mu.Lock()
	defer r.mu.Unlock()
	
	// 检查是否已存在
	for _, existing := range r.services[instance.Name] {
		if existing.ID == instance.ID {
			existing.Address = instance.Address
			existing.Port = instance.Port
			existing.Tags = instance.Tags
			existing.LastHeartbeat = time.Now()
			existing.Healthy = true
			return nil
		}
	}
	
	r.services[instance.Name] = append(r.services[instance.Name], instance)
	return nil
}

// Deregister 注销服务
func (r *ServiceRegistry) Deregister(instanceID string) error {
	r.mu.Lock()
	defer r.mu.Unlock()
	
	for name, instances := range r.services {
		for i, inst := range instances {
			if inst.ID == instanceID {
				r.services[name] = append(instances[:i], instances[i+1:]...)
				return nil
			}
		}
	}
	return fmt.Errorf("instance not found: %s", instanceID)
}

// GetInstances 获取服务实例列表
func (r *ServiceRegistry) GetInstances(name string) ([]*ServiceInstance, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()
	
	instances := r.services[name]
	if len(instances) == 0 {
		return nil, fmt.Errorf("no instances found for service: %s", name)
	}
	
	// 过滤健康实例
	healthy := make([]*ServiceInstance, 0)
	for _, inst := range instances {
		if inst.Healthy && time.Since(inst.LastHeartbeat) < r.ttl {
			healthy = append(healthy, inst)
		}
	}
	
	if len(healthy) == 0 {
		return nil, fmt.Errorf("no healthy instances for service: %s", name)
	}
	
	return healthy, nil
}

// healthCheck 健康检查
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

func (r *ServiceRegistry) checkHealth() {
	r.mu.Lock()
	defer r.mu.Unlock()
	
	now := time.Now()
	for name, instances := range r.services {
		for i, inst := range instances {
			if now.Sub(inst.LastHeartbeat) > r.ttl {
				instances[i].Healthy = false
			}
		}
	}
}

// Stop 停止注册中心
func (r *ServiceRegistry) Stop() {
	close(r.stopCh)
}
```

## 三、熔断器

### 3.1 熔断器状态机

```
CLOSED (关闭):
├── 正常处理请求
├── 失败计数增加
└── 超过阈值 → OPEN

OPEN (开启):
├── 拒绝所有请求
├── 等待恢复时间
└── 超时 → HALF_OPEN

HALF_OPEN (半开):
├── 允许少量请求通过
├── 成功 → CLOSED
└── 失败 → OPEN
```

### 3.2 Go 实现熔断器

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
	failureRate  float64
	windowSize   time.Duration
	windowStart  time.Time
	windowErrors int
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
	
	cb.windowErrors = 0
	cb.windowStart = time.Now()
	
	if cb.state == StateHalfOpen {
		cb.successes++
		if cb.successes >= cb.halfOpenMax {
			cb.state = StateClosed
			cb.failures = 0
			cb.successes = 0
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
	cb.windowErrors++
	
	if cb.state == StateHalfOpen {
		cb.state = StateOpen
	} else if cb.failures >= cb.maxFailures {
		cb.state = StateOpen
	}
}

func (cb *CircuitBreaker) GetState() State {
	cb.mu.RLock()
	defer cb.mu.RUnlock()
	return cb.state
}

func (cb *CircuitBreaker) GetFailureRate() float64 {
	cb.mu.RLock()
	defer cb.mu.RUnlock()
	
	now := time.Now()
	if now.Sub(cb.windowStart) > cb.windowSize {
		cb.windowErrors = 0
		cb.windowStart = now
	}
	
	total := cb.failures + cb.successes
	if total == 0 {
		return 0
	}
	return float64(cb.failures) / float64(total)
}
```

## 四、自测题

1. API Gateway 的核心功能有哪些？
2. Circuit Breaker 的三种状态如何转换？
3. 服务发现的健康检查机制是什么？

## 五、动手验证

```bash
# 1. 实现 API Gateway
# 2. 实现服务注册中心
# 3. 实现熔断器
# 4. 集成测试
```
