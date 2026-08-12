# gRPC Interceptor 拦截器链深度实现

> **版本**: v1.0  
> **日期**: 2026-08-13  
> **作者**: Ryan  
> **分类**: 全栈/后端  
> **难度**: 高级

---

## 一、gRPC 拦截器概述

### 1.1 什么是拦截器？

**gRPC 拦截器** 是在 RPC 调用执行前后插入的逻辑，用于横切关注点 (Cross-cutting Concerns) 的处理。

```
┌─────────────────────────────────────────────────────────────────────┐
│                      gRPC 拦截器链                                   │
│                                                                     │
│  Client-side                                                        │
│  ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐          │
│  │ Logger  │───▶│  Timeout│───▶│ Metadata│───▶│ Invoke  │          │
│  │ Inter.  │    │ Inter.  │    │ Inter.  │    │  Call   │          │
│  └─────────┘    └─────────┘    └─────────┘    └─────────┘          │
│                                                                     │
│  Server-side                                                        │
│  ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐          │
│  │ Auth    │───▶│ Logger  │───▶│ Metrics │───▶│ Handler │          │
│  │ Inter.  │    │ Inter.  │    │ Inter.  │    │  Impl   │          │
│  └─────────┘    └─────────┘    └─────────┘    └─────────┘          │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.2 拦截器类型

```
┌───────────────────────────────────────────────────────────────────────────┐
│                         gRPC 拦截器类型                                    │
├──────────────────────────┬────────────────────────────────────────────────┤
│ 类型                     │ 说明                                          │
├──────────────────────────┼────────────────────────────────────────────────┤
│ Unary Interceptor        │ 普通 RPC 调用拦截器                           │
│ Stream Interceptor       │ 流式 RPC 调用拦截器                           │
│ Client Interceptor       │ 客户端拦截器链                                │
│ Server Interceptor       │ 服务端拦截器链                                │
└──────────────────────────┴────────────────────────────────────────────────┘
```

---

## 二、实现基础拦截器

### 2.1 Unary 拦截器

```go
// interceptor/unary.go
package interceptor

import (
    "context"
    "time"
    
    "google.golang.org/grpc"
    "google.golang.org/grpc/meta"
)

// LoggerInterceptor 日志拦截器
func LoggerInterceptor() grpc.UnaryServerInterceptor {
    return func(ctx context.Context, req interface{}, 
                info *grpc.UnaryServerInfo, handler grpc.UnaryHandler) (interface{}, error) {
        
        start := time.Now()
        method := info.FullMethod
        
        // 调用实际 handler
        resp, err := handler(ctx, req)
        
        // 记录日志
        cost := time.Since(start)
        log.Printf("[RPC] method=%s cost=%v err=%v", method, cost, err)
        
        return resp, err
    }
}

// TimeoutInterceptor 超时拦截器
func TimeoutInterceptor(timeout time.Duration) grpc.UnaryServerInterceptor {
    return func(ctx context.Context, req interface{},
                info *grpc.UnaryServerInfo, handler grpc.UnaryHandler) (interface{}, error) {
        
        ctx, cancel := context.WithTimeout(ctx, timeout)
        defer cancel()
        
        return handler(ctx, req)
    }
}
```

### 2.2 Stream 拦截器

```go
// interceptor/stream.go
func StreamLoggerInterceptor() grpc.StreamServerInterceptor {
    return func(srv interface{}, ss grpc.ServerStream, 
                info *grpc.StreamServerInfo, handler grpc.StreamHandler) error {
        
        start := time.Now()
        method := info.FullMethod
        
        err := handler(srv, ss)
        
        cost := time.Since(start)
        log.Printf("[Stream] method=%s cost=%v err=%v", method, cost, err)
        
        return err
    }
}
```

### 2.3 客户端拦截器

```go
// interceptor/client.go
func ClientLoggerInterceptor() grpc.UnaryClientInterceptor {
    return func(ctx context.Context, method string, 
                req, resp interface{}, cc *grpc.ClientConn,
                invoker grpc.UnaryInvoker, opts ...grpc.CallOption) error {
        
        start := time.Now()
        
        err := invoker(ctx, method, req, resp, cc, opts...)
        
        cost := time.Since(start)
        log.Printf("[Client RPC] method=%s cost=%v err=%v", method, cost, err)
        
        return err
    }
}
```

---

## 三、拦截器链

### 3.1 构建拦截器链

```go
// chain.go
package interceptor

import (
    "google.golang.org/grpc"
)

// Chain 拦截器链
type Chain struct {
    interceptors []grpc.UnaryServerInterceptor
}

// NewChain 创建拦截器链
func NewChain(interceptors ...grpc.UnaryServerInterceptor) *Chain {
    return &Chain{interceptors: interceptors}
}

// Build 构建 grpc选项
func (c *Chain) Build() []grpc.ServerOption {
    var opts []grpc.ServerOption
    if len(c.interceptors) > 0 {
        opts = append(opts, grpc.ChainUnaryInterceptor(c.interceptors...))
    }
    return opts
}

// 使用示例
func main() {
    chain := NewChain(
        AuthInterceptor(),
        LoggerInterceptor(),
        MetricsInterceptor(),
        TimeoutInterceptor(5*time.Second),
    )
    
    srv := grpc.NewServer(chain.Build()...)
}
```

### 3.2 拦截器执行顺序

```
请求进入顺序: Auth → Logger → Metrics → Timeout → Handler
响应返回顺序: Handler → Timeout → Metrics → Logger → Auth
```

---

## 四、高级拦截器实现

### 4.1 认证拦截器

```go
// auth_interceptor.go
func AuthInterceptor() grpc.UnaryServerInterceptor {
    return func(ctx context.Context, req interface{},
                info *grpc.UnaryServerInfo, handler grpc.UnaryHandler) (interface{}, error) {
        
        // 从 metadata 获取 token
        md, ok := metadata.FromIncomingContext(ctx)
        if !ok {
            return nil, status.Errorf(codes.Unauthenticated, "missing metadata")
        }
        
        tokens := md.Get("authorization")
        if len(tokens) == 0 {
            return nil, status.Errorf(codes.Unauthenticated, "missing token")
        }
        
        token := tokens[0]
        
        // 验证 token
        if !validateToken(token) {
            return nil, status.Errorf(codes.Unauthenticated, "invalid token")
        }
        
        // 将用户信息注入 context
        ctx = context.WithValue(ctx, "userID", getUserID(token))
        
        return handler(ctx, req)
    }
}

func validateToken(token string) bool {
    // JWT 验证逻辑
    return true
}

func getUserID(token string) string {
    // 解析 token 获取用户 ID
    return "user123"
}
```

### 4.2 监控拦截器

```go
// metrics_interceptor.go
var (
    rpcCount = prometheus.NewCounterVec(
        prometheus.CounterOpts{
            Name: "rpc_count",
            Help: "Total RPC calls",
        },
        []string{"method", "status"},
    )
    
    rpcDuration = prometheus.NewHistogramVec(
        prometheus.HistogramOpts{
            Name: "rpc_duration_seconds",
            Help: "RPC duration",
            Buckets: prometheus.DefBuckets,
        },
        []string{"method"},
    )
)

func MetricsInterceptor() grpc.UnaryServerInterceptor {
    return func(ctx context.Context, req interface{},
                info *grpc.UnaryServerInfo, handler grpc.UnaryHandler) (interface{}, error) {
        
        start := time.Now()
        method := info.FullMethod
        
        resp, err := handler(ctx, req)
        
        // 记录指标
        status := "OK"
        if err != nil {
            status = "ERROR"
        }
        
        rpcCount.WithLabelValues(method, status).Inc()
        rpcDuration.WithLabelValues(method).Observe(time.Since(start).Seconds())
        
        return resp, err
    }
}
```

### 4.3 限流拦截器

```go
// rate_limit_interceptor.go
type RateLimiter struct {
    limiter *rate.Limiter
}

func NewRateLimiter(rps float64) *RateLimiter {
    return &RateLimiter{
        limiter: rate.NewLimiter(rate.Limit(rps), 100),
    }
}

func (rl *RateLimiter) Interceptor() grpc.UnaryServerInterceptor {
    return func(ctx context.Context, req interface{},
                info *grpc.UnaryServerInfo, handler grpc.UnaryHandler) (interface{}, error) {
        
        if !rl.limiter.Allow() {
            return nil, status.Errorf(codes.ResourceExhausted, "rate limit exceeded")
        }
        
        return handler(ctx, req)
    }
}
```

---

## 五、错误处理

### 5.1 统一错误处理

```go
// error_interceptor.go
func ErrorInterceptor() grpc.UnaryServerInterceptor {
    return func(ctx context.Context, req interface{},
                info *grpc.UnaryServerInfo, handler grpc.UnaryHandler) (interface{}, error) {
        
        resp, err := handler(ctx, req)
        
        if err != nil {
            // 统一错误处理
            grpcLog.Error("RPC error:", err)
            
            // 返回标准化错误
            return nil, status.Errorf(codes.Internal, "internal error")
        }
        
        return resp, nil
    }
}
```

---

## 六、最佳实践

### 6.1 拦截器设计原则

```
✅ 推荐:
  - 拦截器保持单一职责
  - 使用 context 传递信息
  - 注意性能开销
  - 统一错误处理
  - 日志脱敏

❌ 不推荐:
  - 在拦截器中做业务逻辑
  - 阻塞拦截器
  - 泄露敏感信息
  - 忽略错误
```

### 6.2 性能优化

```go
// 使用 sync.Pool 减少分配
var logBufPool = sync.Pool{
    New: func() interface{} {
        return new(bytes.Buffer)
    },
}

func (l *LoggerInterceptor) Intercept(...) {
    buf := logBufPool.Get().(*bytes.Buffer)
    defer logBufPool.Put(buf)
    buf.Reset()
    
    // 使用 buf 记录日志...
}
```

---

## 七、测试

```go
func TestAuthInterceptor(t *testing.T) {
    srv := grpc.NewServer(
        grpc.UnaryInterceptor(AuthInterceptor()),
    )
    
    // 测试未认证请求
    // 测试有效 token
    // 测试过期 token
}
```

---

## 八、总结

| 项目 | 说明 |
|------|------|
| **核心概念** | 拦截器是横切关注点的实现机制 |
| **类型** | Unary/Stream, Client/Server |
| **链式调用** | 使用 grpc.ChainUnaryInterceptor |
| **最佳实践** | 单一职责、性能优化、统一错误 |

---

## 九、自测题

1. **拦截器链的执行顺序是怎样的？**
   - 请求: 按注册顺序执行
   - 响应: 按逆序执行

2. **如何传递用户信息到后续拦截器？**
   - 使用 context.WithValue

3. **拦截器可以做哪些事情？**
   - 认证、日志、监控、限流、重试、错误处理

4. **客户端和服务端拦截器的区别？**
   - 客户端: invoker 包装
   - 服务端: handler 包装

EOF
echo "✅ 已创建: fullstack/grpc-interceptor-deep.md"