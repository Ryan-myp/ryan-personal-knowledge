# API网关深度解析

> 深入API网关：Kong、APISIX、Nginx+Lua、网关架构。
> 源码级分析，包含生产环境实践。
> 适用对象：后端工程师、架构师

---

## 1. API网关架构

### 1.1 核心组件

```
API网关核心组件：

├── 路由引擎
│   ├── URL匹配
│   ├── 路径重写
│   └── 请求转发
│
├── 插件系统
│   ├── 限流插件
│   ├── 认证插件
│   ├── 日志插件
│   └── 转换插件
│
├── 负载均衡
│   ├── 轮询
│   ├── 加权
│   └── 一致性Hash
│
└── 监控告警
    ├── 指标采集
    ├── 日志收集
    └── 告警通知
```

### 1.2 Go 实现 API网关

```go
// api_gateway.go

package gateway

import (
    "context"
    "net/http"
    "sync"
)

type Gateway struct {
    routers    map[string]*Router
    plugins    []Plugin
    proxy      *Proxy
    config     *Config
    mu         sync.Mutex
}

type Router struct {
    Path     string
    Methods  []string
    Upstream string
    Plugins  []Plugin
}

type Plugin interface {
    Name() string
    Process(ctx context.Context, req *Request) (*Response, error)
}

type Config struct {
    Timeout     time.Duration
    MaxConns    int
    RateLimit   int
}

func NewGateway(config *Config) *Gateway {
    return &Gateway{
        routers: make(map[string]*Router),
        proxy:   NewProxy(),
        config:  config,
    }
}

func (g *Gateway) AddRouter(router *Router) {
    g.mu.Lock()
    defer g.mu.Unlock()
    g.routers[router.Path] = router
}

func (g *Gateway) HandleRequest(req *http.Request) (*http.Response, error) {
    // 1. 路由匹配
    router := g.matchRouter(req)
    if router == nil {
        return nil, ErrRouteNotFound
    }
    
    // 2. 执行插件
    for _, plugin := range g.plugins {
        // 插件处理
    }
    
    // 3. 代理转发
    return g.proxy.Forward(req, router.Upstream)
}
```

---

## 2. 限流插件

### 2.1 限流算法

```
限流算法：

├── 令牌桶
│   └── 匀速产生令牌
│
├── 漏桶
│   └── 匀速处理请求
│
├── 固定窗口
│   └── 时间窗口计数
│
└── 滑动窗口
    └── 细粒度统计
```

### 2.2 Go 实现限流

```go
// rate_limiter.go

package gateway

import (
    "sync"
    "time"
)

type RateLimiter struct {
    algorithms map[string]Limiter
    mu         sync.Mutex
}

type Limiter interface {
    Allow(key string) bool
}

type TokenBucket struct {
    rate     float64
    capacity float64
    tokens   float64
    lastTime time.Time
    mu       sync.Mutex
}

func (tb *TokenBucket) Allow(key string) bool {
    tb.mu.Lock()
    defer tb.mu.Unlock()
    
    now := time.Now()
    elapsed := now.Sub(tb.lastTime).Seconds()
    tb.tokens += elapsed * tb.rate
    if tb.tokens > tb.capacity {
        tb.tokens = tb.capacity
    }
    tb.lastTime = now
    
    if tb.tokens >= 1 {
        tb.tokens--
        return true
    }
    return false
}

type SlidingWindow struct {
    windows map[string]*Window
    size    int
    mu      sync.Mutex
}

type Window struct {
    startTime time.Time
    count     int
}

func (sw *SlidingWindow) Allow(key string) bool {
    sw.mu.Lock()
    defer sw.mu.Unlock()
    
    now := time.Now()
    window := sw.getOrCreateWindow(key, now)
    
    // 检查时间窗口
    if now.Sub(window.startTime) > time.Second {
        window.startTime = now
        window.count = 0
    }
    
    window.count++
    return window.count <= sw.size
}
```

---

## 3. 认证插件

### 3.1 JWT认证

```
JWT认证流程：

1. 客户端发送认证请求
2. 服务端验证并生成JWT
3. 客户端携带JWT访问API
4. 网关验证JWT有效性
5. 转发请求到后端
```

### 3.2 Go 实现JWT认证

```go
// jwt_auth.go

package gateway

import (
    "time"
)

type JWTAuth struct {
    secret     string
    expire     time.Duration
}

func NewJWTAuth(secret string, expire time.Duration) *JWTAuth {
    return &JWTAuth{
        secret: secret,
        expire: expire,
    }
}

func (j *JWTAuth) GenerateToken(userID string) (string, error) {
    // 生成JWT
    token := &Token{
        UserID:    userID,
        IssuedAt:  time.Now(),
        ExpiresAt: time.Now().Add(j.expire),
    }
    return token.Sign(j.secret)
}

func (j *JWTAuth) ValidateToken(tokenStr string) (*Token, error) {
    token, err := Token.Verify(tokenStr, j.secret)
    if err != nil {
        return nil, err
    }
    
    if token.IsExpired() {
        return nil, ErrTokenExpired
    }
    
    return token, nil
}
```

---

## 4. 日志插件

### 4.1 日志格式

```
请求日志格式：

├── 基本信息
│   ├── 请求ID
│   ├── 客户端IP
│   ├── 请求方法
│   └── 请求URL
│
├── 响应信息
│   ├── 状态码
│   ├── 响应时间
│   └── 响应大小
│
└── 性能指标
    ├── DNS解析
    ├── 连接时间
    └── TLS握手
```

### 4.2 Go 实现日志

```go
// logger.go

package gateway

import (
    "encoding/json"
    "log"
    "time"
)

type AccessLogger struct {
    output *log.Logger
}

type AccessLog struct {
    RequestID   string    `json:"request_id"`
    ClientIP    string    `json:"client_ip"`
    Method      string    `json:"method"`
    URL         string    `json:"url"`
    StatusCode  int       `json:"status_code"`
    Latency     float64   `json:"latency"`
    ResponseSize int64    `json:"response_size"`
    Timestamp   time.Time `json:"timestamp"`
}

func (al *AccessLogger) Log(log *AccessLog) {
    data, _ := json.Marshal(log)
    al.output.Println(string(data))
}

type PerformanceLogger struct{}

type PerformanceMetric struct {
    DNSDuration     float64 `json:"dns_duration"`
    ConnectDuration float64 `json:"connect_duration"`
    TLSDuration     float64 `json:"tls_duration"`
    WaitDuration    float64 `json:"wait_duration"`
    TotalDuration   float64 `json:"total_duration"`
}
```

---

## 5. 总结

### 5.1 核心原理回顾

| 组件 | 作用 |
|------|------|
| 路由引擎 | 请求路由 |
| 插件系统 | 功能扩展 |
| 限流插件 | 流量控制 |
| 认证插件 | 安全访问 |
| 日志插件 | 可观测性 |

### 5.2 最佳实践

- [ ] 合理配置限流策略
- [ ] 实现统一认证
- [ ] 收集关键指标
- [ ] 监控网关性能

---

*最后更新：2026-08-11*
*作者：Ryan*
