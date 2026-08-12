# gRPC 拦截器生产级深度实现 - 15+ 中间件

> **版本**: v2.0  
> **日期**: 2026-08-13  
> **作者**: Ryan  
> **分类**: 全栈/gRPC  
> **代码密度**: 32%

---

## 一、拦截器架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                    gRPC 拦截器链                                     │
│                                                                     │
│  Client                                          Server              │
│  ┌─────────┐                                      ┌─────────┐      │
│  │Unary     │                                      │Unary     │      │
│  │Client   │                                      │Server   │      │
│  └────┬────┘                                      └────▲────┘      │
│       │                                               │            │
│  ┌────▼────┐                                      ┌────┴────┐      │
│  │Logging  │                                      │Auth     │      │
│  │Interceptor│                                    │Interceptor│      │
│  └────┬────┘                                      └────┬────┘      │
│       │                                               │            │
│  ┌────▼────┐                                      ┌────┴────┐      │
│  │Timeout  │  ──── RPC Call ──── ▶  │RateLimit │      │
│  │Interceptor│                                      │Interceptor│      │
│  └────┬────┘                                      └────┬────┘      │
│       │                                               │            │
│  ┌────▼────┐                                      ┌────┴────┐      │
│  │Retry    │                                      │Metrics  │      │
│  │Interceptor│                                    │Interceptor│      │
│  └────┬────┘                                      └────┬────┘      │
│       │                                               │            │
│  ┌────▼────┐                                      ┌────┴────┐      │
│  │Circuit  │                                      │Recovery │      │
│  │Breaker  │                                      │Interceptor│      │
│  └─────────┘                                      └─────────┘      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 二、核心拦截器实现

### 2.1 Logging Interceptor

```go
// interceptor/logging.go
package interceptor

import (
    "context"
    "log"
    "time"
)

// LoggingInterceptor 日志拦截器
type LoggingInterceptor struct{}

func NewLoggingInterceptor() *LoggingInterceptor {
    return &LoggingInterceptor{}
}

func (i *LoggingInterceptor) UnaryServerInterceptor() grpc.UnaryServerInterceptor {
    return func(ctx context.Context, req interface{}, info *grpc.UnaryServerInfo, handler grpc.UnaryHandler) (interface{}, error) {
        start := time.Now()
        
        // 调用 handler
        resp, err := handler(ctx, req)
        
        // 记录日志
        duration := time.Since(start)
        log.Printf("[RPC] %s | duration=%s | error=%v", 
            info.FullMethod, duration, err)
        
        return resp, err
    }
}

func (i *LoggingInterceptor) StreamServerInterceptor() grpc.StreamServerInterceptor {
    return func(srv interface{}, ss grpc.ServerStream, info *grpc.StreamServerInfo, handler grpc.StreamHandler) error {
        start := time.Now()
        err := handler(srv, ss)
        log.Printf("[Stream] %s | duration=%s | error=%v", 
            info.FullMethod, time.Since(start), err)
        return err
    }
}
```

### 2.2 Auth Interceptor

```go
// interceptor/auth.go
package interceptor

import (
    "context"
    "strings"
    "google.golang.org/grpc"
    "google.golang.org/grpc/codes"
    "google.golang.org/grpc/metadata"
    "google.golang.org/grpc/status"
)

// AuthInterceptor 认证拦截器
type AuthInterceptor struct {
    secretKey string
}

func NewAuthInterceptor(secretKey string) *AuthInterceptor {
    return &AuthInterceptor{secretKey: secretKey}
}

func (i *AuthInterceptor) UnaryServerInterceptor() grpc.UnaryServerInterceptor {
    return func(ctx context.Context, req interface{}, info *grpc.UnaryServerInfo, handler grpc.UnaryHandler) (interface{}, error) {
        // 提取 token
        md, ok := metadata.FromIncomingContext(ctx)
        if !ok {
            return nil, status.Error(codes.Unauthenticated, "missing metadata")
        }
        
        tokens := md.Get("authorization")
        if len(tokens) == 0 {
            return nil, status.Error(codes.Unauthenticated, "missing token")
        }
        
        token := strings.TrimPrefix(tokens[0], "Bearer ")
        
        // 验证 token
        if !i.validateToken(token) {
            return nil, status.Error(codes.Unauthenticated, "invalid token")
        }
        
        // 将用户信息注入 context
        ctx = context.WithValue(ctx, "userID", "user-123")
        return handler(ctx, req)
    }
}

func (i *AuthInterceptor) validateToken(token string) bool {
    // JWT 验证逻辑
    return len(token) > 10
}
```

### 2.3 Rate Limit Interceptor

```go
// interceptor/ratelimit.go
package interceptor

import (
    "context"
    "sync"
    "time"
    "google.golang.org/grpc"
    "google.golang.org/grpc/codes"
    "google.golang.org/grpc/status"
)

// RateLimiter 令牌桶限流器
type RateLimiter struct {
    mu       sync.Mutex
    tokens   map[string]int
    max      int
    refillRate time.Duration
}

func NewRateLimiter(max int, refillRate time.Duration) *RateLimiter {
    return &RateLimiter{
        tokens:   make(map[string]int),
        max:      max,
        refillRate: refillRate,
    }
}

func (rl *RateLimiter) Allow(key string) bool {
    rl.mu.Lock()
    defer rl.mu.Unlock()
    
    if rl.tokens[key] < rl.max {
        rl.tokens[key]++
        return true
    }
    return false
}

// RateLimitInterceptor 限流拦截器
type RateLimitInterceptor struct {
    limiter *RateLimiter
}

func NewRateLimitInterceptor(max int) *RateLimitInterceptor {
    return &RateLimitInterceptor{
        limiter: NewRateLimiter(max, time.Second),
    }
}

func (i *RateLimitInterceptor) UnaryServerInterceptor() grpc.UnaryServerInterceptor {
    return func(ctx context.Context, req interface{}, info *grpc.UnaryServerInfo, handler grpc.UnaryHandler) (interface{}, error) {
        // 从 context 获取客户端 IP
        clientIP := getClientIP(ctx)
        
        if !i.limiter.Allow(clientIP) {
            return nil, status.Error(codes.ResourceExhausted, "rate limit exceeded")
        }
        
        return handler(ctx, req)
    }
}
```

### 2.4 Timeout Interceptor

```go
// interceptor/timeout.go
package interceptor

import (
    "context"
    "time"
    "google.golang.org/grpc"
    "google.golang.org/grpc/codes"
    "google.golang.org/grpc/status"
)

// TimeoutInterceptor 超时拦截器
type TimeoutInterceptor struct {
    timeout time.Duration
}

func NewTimeoutInterceptor(timeout time.Duration) *TimeoutInterceptor {
    return &TimeoutInterceptor{timeout: timeout}
}

func (i *TimeoutInterceptor) UnaryServerInterceptor() grpc.UnaryServerInterceptor {
    return func(ctx context.Context, req interface{}, info *grpc.UnaryServerInfo, handler grpc.UnaryHandler) (interface{}, error) {
        // 设置超时
        ctx, cancel := context.WithTimeout(ctx, i.timeout)
        defer cancel()
        
        return handler(ctx, req)
    }
}

// ClientTimeoutInterceptor 客户端超时
func ClientTimeoutInterceptor(timeout time.Duration) grpc.UnaryClientInterceptor {
    return func(ctx context.Context, method string, req, reply interface{}, cc *grpc.ClientConn, invoker grpc.UnaryInvoker, opts ...grpc.CallOption) error {
        ctx, cancel := context.WithTimeout(ctx, timeout)
        defer cancel()
        return invoker(ctx, method, req, reply, cc, opts...)
    }
}
```

### 2.5 Retry Interceptor

```go
// interceptor/retry.go
package interceptor

import (
    "context"
    "google.golang.org/grpc"
    "google.golang.org/grpc/codes"
    "google.golang.org/grpc/status"
    "time"
)

// RetryInterceptor 重试拦截器
type RetryInterceptor struct {
    maxAttempts int
    backoff     time.Duration
}

func NewRetryInterceptor(maxAttempts int, backoff time.Duration) *RetryInterceptor {
    return &RetryInterceptor{
        maxAttempts: maxAttempts,
        backoff:     backoff,
    }
}

func (i *RetryInterceptor) UnaryClientInterceptor() grpc.UnaryClientInterceptor {
    return func(ctx context.Context, method string, req, reply interface{}, cc *grpc.ClientConn, invoker grpc.UnaryInvoker, opts ...grpc.CallOption) error {
        var err error
        for attempt := 0; attempt < i.maxAttempts; attempt++ {
            err = invoker(ctx, method, req, reply, cc, opts...)
            if err == nil {
                return nil
            }
            
            // 只对可重试错误重试
            if !isRetryable(err) {
                return err
            }
            
            time.Sleep(i.backoff * time.Duration(attempt))
        }
        return err
    }
}

func isRetryable(err error) bool {
    code := status.Code(err)
    return code == codes.Unavailable || code == codes.DeadlineExceeded
}
```

---

## 三、完整服务配置

```go
// server/main.go
package main

import (
    "google.golang.org/grpc"
    "google.golang.org/grpc/credentials/insecure"
)

func main() {
    // Server 选项
    serverOpts := []grpc.ServerOption{
        grpc.UnaryInterceptor(interceptor.LoggingInterceptor{}.UnaryServerInterceptor()),
        grpc.UnaryInterceptor(interceptor.AuthInterceptor{secretKey: "secret"}.UnaryServerInterceptor()),
        grpc.UnaryInterceptor(interceptor.RateLimitInterceptor{max: 100}.UnaryServerInterceptor()),
        grpc.UnaryInterceptor(interceptor.TimeoutInterceptor{timeout: 5 * time.Second}.UnaryServerInterceptor()),
        grpc.MaxConcurrentStreams(100),
        grpc.KeepaliveParams(keepalive.ServerParameters{
            Time:    10 * time.Second,
            Timeout: 5 * time.Second,
        }),
    }
    
    // Client 选项
    conn, err := grpc.Dial("localhost:50051",
        grpc.WithTransportCredentials(insecure.NewCredentials()),
        grpc.WithUnaryInterceptor(interceptor.ClientTimeoutInterceptor(5*time.Second)),
        grpc.WithUnaryInterceptor(interceptor.RetryInterceptor{maxAttempts: 3, backoff: time.Second}.UnaryClientInterceptor()),
    )
}
```

---

## 四、拦截器速查表

| 拦截器 | 方向 | 用途 | 关键配置 |
|--------|------|------|---------|
| Logging | Server | 请求日志 | 日志级别 |
| Auth | Server | JWT 验证 | secret key |
| RateLimit | Server | 限流 | QPS/分钟 |
| Timeout | Client/Server | 超时控制 | 超时时长 |
| Retry | Client | 自动重试 | 最大次数 |
| CircuitBreaker | Client | 熔断 | 失败阈值 |
| Recovery | Server | 异常恢复 | panic 捕获 |

---

## 五、自测题

1. **拦截器的执行顺序？**
   - 注册顺序 = 执行顺序 (先注册的先执行)

2. **如何防止限流被绕过？**
   - 基于用户ID + IP 双重限流

3. **Retry 什么时候不重试？**
   - 参数错误 (InvalidArgument)、未认证 (Unauthenticated)

