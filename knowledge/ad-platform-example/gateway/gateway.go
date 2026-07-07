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

// APIGateway API 网关
type APIGateway struct {
	routes      map[string]*Route
	middlewares []MiddlewareFunc
	timeout     time.Duration
	stats       *StatsCollector
	mu          sync.RWMutex
}

// Route 路由配置
type Route struct {
	Path       string
	Backend    string
	Methods    []string
	Middleware []MiddlewareFunc
	Timeout    time.Duration
}

// MiddlewareFunc 中间件函数
type MiddlewareFunc func(http.Handler) http.Handler

// StatsCollector 统计收集器
type StatsCollector struct {
	requestCount map[string]int
	errorCount   map[string]int
	latency      map[string][]time.Duration
	mu           sync.RWMutex
}

func NewStatsCollector() *StatsCollector {
	return &StatsCollector{
		requestCount: make(map[string]int),
		errorCount:   make(map[string]int),
		latency:      make(map[string][]time.Duration),
	}
}

func (s *StatsCollector) RecordRequest(path string, duration time.Duration) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.requestCount[path]++
	s.latency[path] = append(s.latency[path], duration)
}

func (s *StatsCollector) RecordError(path string) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.errorCount[path]++
}

func (s *StatsCollector) RecordRateLimit(clientIP string) {
	// 记录限流次数
	_ = clientIP
}

// NewAPIGateway 创建网关
func NewAPIGateway() *APIGateway {
	return &APIGateway{
		routes: make(map[string]*Route),
		stats:  NewStatsCollector(),
		timeout: 30 * time.Second,
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
		
		// 验证 JWT
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
	proxy.ErrorHandler = func(w http.ResponseWriter, r *http.Request, err error) {
		g.stats.RecordError(route.Path)
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

// getClientIP 获取客户端 IP
func getClientIP(r *http.Request) string {
	ip := r.Header.Get("X-Forwarded-For")
	if ip != "" {
		return ip
	}
	ip = r.Header.Get("X-Real-IP")
	if ip != "" {
		return ip
	}
	return r.RemoteAddr
}

// JWTClaims JWT 声明
type JWTClaims struct {
	UserID string   `json:"user_id"`
	Roles  []string `json:"roles"`
}

// ValidateJWT 验证 JWT
func ValidateJWT(token string) (*JWTClaims, error) {
	// 简化实现，实际应使用 jwt-go 库
	if token == "" {
		return nil, fmt.Errorf("empty token")
	}
	return &JWTClaims{
		UserID: "user_123",
		Roles:  []string{"admin"},
	}, nil
}

// TokenBucket 令牌桶限流
type TokenBucket struct {
	tokens     float64
	maxTokens  float64
	refillRate float64
	lastRefill time.Time
	mu         sync.Mutex
}

func NewTokenBucket(maxTokens int, window time.Duration) *TokenBucket {
	return &TokenBucket{
		tokens:     float64(maxTokens),
		maxTokens:  float64(maxTokens),
		refillRate: float64(maxTokens) / window.Seconds(),
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
