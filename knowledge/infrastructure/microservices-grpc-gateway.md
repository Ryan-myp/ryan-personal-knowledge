# 微服务架构：gRPC 服务治理/API Gateway

> gRPC 服务定义/Protobuf 优化/负载均衡/熔断降级/服务网格

---

## 第一部分：入门引导（5 分钟速览）

### 为什么需要微服务？

广告平台系统复杂度高：
- **竞价引擎**：独立部署，快速迭代
- **用户服务**：独立扩缩容
- **广告服务**：独立管理生命周期
- **数据分析**：独立资源隔离

### 微服务通信对比

| 方案 | 协议 | 序列化 | 性能 | 适用场景 |
|------|------|--------|------|---------|
| **gRPC** | HTTP/2 | Protobuf | 最快 | 内部服务通信 |
| **REST** | HTTP/1.1 | JSON | 中等 | 外部 API |
| **GraphQL** | HTTP/1.1 | JSON | 较慢 | 前端数据获取 |

---

## 第二部分：gRPC 服务定义

### 2.1 Protobuf 定义

```protobuf
syntax = "proto3";
package bidding;

service BidEngine {
    rpc Bid(BidRequest) returns (BidResponse) {}
    rpc StreamBids(stream BidRequest) returns (stream BidResponse) {}
}

message BidRequest {
    string request_id = 1;
    string user_id = 2;
    repeated Impression impressions = 3;
    double budget = 4;
}

message BidResponse {
    string request_id = 1;
    string ad_id = 2;
    double price = 3;
    bool win = 4;
}

message Impression {
    string placement_id = 1;
    double latitude = 2;
    double longitude = 3;
    int32 width = 4;
    int32 height = 5;
}
```

### 2.2 Go 实现 gRPC 服务端

```go
package grpc

import (
    "context"
    "google.golang.org/grpc"
)

type BidEngineServer struct {
    pb.UnimplementedBidEngineServer
    bidEngine *BidEngine
}

func (s *BidEngineServer) Bid(ctx context.Context, req *pb.BidRequest) (*pb.BidResponse, error) {
    // 1. 验证请求
    if req.User == nil || req.User.Id == "" {
        return nil, status.Error(codes.InvalidArgument, "missing user id")
    }
    
    // 2. 执行竞价
    result, err := s.bidEngine.Bid(ctx, req)
    if err != nil {
        return nil, status.Error(codes.Internal, err.Error())
    }
    
    // 3. 返回结果
    return &pb.BidResponse{
        RequestId: req.RequestId,
        AdId:      result.AdId,
        Price:     result.Price,
        Win:       result.Win,
    }, nil
}

func (s *BidEngineServer) StreamBids(stream pb.BidEngine_StreamBidsServer) error {
    for {
        req, err := stream.Recv()
        if err != nil {
            return err
        }
        
        result, err := s.bidEngine.Bid(stream.Context(), req)
        if err != nil {
            continue
        }
        
        err = stream.Send(&pb.BidResponse{
            RequestId: req.RequestId,
            AdId:      result.AdId,
            Price:     result.Price,
            Win:       result.Win,
        })
        if err != nil {
            return err
        }
    }
}

func StartGRPCServer(port int) error {
    lis, err := net.Listen("tcp", fmt.Sprintf(":%d", port))
    if err != nil {
        return err
    }
    
    s := grpc.NewServer(
        grpc.MaxConcurrentStreams(1000),
        grpc.MaxRecvMsgSize(1024*1024),
        grpc.KeepaliveParams(keepalive.ServerParameters{
            Time:    30 * time.Second,
            Timeout: 20 * time.Second,
        }),
    )
    
    pb.RegisterBidEngineServer(s, &BidEngineServer{})
    
    return s.Serve(lis)
}
```

### 2.3 负载均衡

```go
type LoadBalancer struct {
    backends []*Backend
    currentIndex int
}

type Backend struct {
    Address  string
    Weight   int
    Healthy  bool
    Requests int64
}

func (lb *LoadBalancer) Next() *Backend {
    // 加权轮询
    totalWeight := 0
    for _, b := range lb.backends {
        if b.Healthy {
            totalWeight += b.Weight
        }
    }
    
    if totalWeight == 0 {
        return nil
    }
    
    // 简单轮询
    idx := lb.currentIndex % len(lb.backends)
    lb.currentIndex++
    
    return lb.backends[idx]
}

func (lb *LoadBalancer) MarkUnhealthy(addr string) {
    for _, b := range lb.backends {
        if b.Address == addr {
            b.Healthy = false
        }
    }
}

func (lb *LoadBalancer) MarkHealthy(addr string) {
    for _, b := range lb.backends {
        if b.Address == addr {
            b.Healthy = true
        }
    }
}
```

---

## 第三部分：熔断降级

### 3.1 熔断器实现

```go
type CircuitBreaker struct {
    state        CircuitState
    failureCount int
    successCount int
    lastFailTime time.Time
    timeout      time.Duration
    threshold    int
    halfOpenMax  int
}

type CircuitState int

const (
    Closed CircuitState = iota
    Open
    HalfOpen
)

func (cb *CircuitBreaker) AllowRequest() bool {
    switch cb.state {
    case Closed:
        return true
    case Open:
        // 检查是否过了超时时间
        if time.Since(cb.lastFailTime) > cb.timeout {
            cb.state = HalfOpen
            cb.successCount = 0
            return true
        }
        return false
    case HalfOpen:
        return cb.successCount < cb.halfOpenMax
    }
    return false
}

func (cb *CircuitBreaker) RecordSuccess() {
    if cb.state == HalfOpen {
        cb.successCount++
        if cb.successCount >= cb.halfOpenMax {
            cb.state = Closed
            cb.failureCount = 0
        }
    } else {
        cb.failureCount = 0
    }
}

func (cb *CircuitBreaker) RecordFailure() {
    cb.failureCount++
    cb.lastFailTime = time.Now()
    
    if cb.failureCount >= cb.threshold {
        cb.state = Open
    }
}
```

### 3.2 限流器

```go
type RateLimiter struct {
    tokens     chan struct{}
    refillRate int
    maxTokens  int
}

func NewRateLimiter(rate, burst int) *RateLimiter {
    rl := &RateLimiter{
        tokens:     make(chan struct{}, burst),
        refillRate: rate,
        maxTokens:  burst,
    }
    
    // 填充令牌
    for i := 0; i < burst; i++ {
        rl.tokens <- struct{}{}
    }
    
    // 定期补充令牌
    go rl.refill()
    
    return rl
}

func (rl *RateLimiter) Wait(ctx context.Context) error {
    select {
    case <-rl.tokens:
        return nil
    case <-ctx.Done():
        return ctx.Err()
    }
}

func (rl *RateLimiter) refill() {
    ticker := time.NewTicker(time.Second / time.Duration(rl.refillRate))
    defer ticker.Stop()
    
    for range ticker.C {
        select {
        case rl.tokens <- struct{}{}:
        default:
            // 令牌已满，丢弃
        }
    }
}
```

---

## 第四部分：API Gateway

### 4.1 网关路由

```go
type Gateway struct {
    routes map[string]*Route
    middleware []Middleware
    circuitBreaker *CircuitBreaker
    rateLimiter *RateLimiter
}

type Route struct {
    Path     string
    Method   string
    Backend  string
    Timeout  time.Duration
}

type Middleware func(http.Handler) http.Handler

func (gw *Gateway) ServeHTTP(w http.ResponseWriter, r *http.Request) {
    // 1. 限流
    ctx, cancel := context.WithTimeout(r.Context(), 5*time.Second)
    defer cancel()
    
    err := gw.rateLimiter.Wait(ctx)
    if err != nil {
        http.Error(w, "rate limited", http.StatusTooManyRequests)
        return
    }
    
    // 2. 路由匹配
    route := gw.matchRoute(r.Method, r.URL.Path)
    if route == nil {
        http.Error(w, "not found", http.StatusNotFound)
        return
    }
    
    // 3. 执行中间件
    handler := gw.proxyHandler(route.Backend, route.Timeout)
    for _, mw := range gw.middleware {
        handler = mw(handler)
    }
    
    // 4. 转发请求
    handler.ServeHTTP(w, r)
}

func (gw *Gateway) proxyHandler(backend string, timeout time.Duration) http.Handler {
    return &reverseProxy{
        target:  backend,
        timeout: timeout,
        cb:      gw.circuitBreaker,
    }
}

type reverseProxy struct {
    target  string
    timeout time.Duration
    cb      *CircuitBreaker
}

func (rp *reverseProxy) ServeHTTP(w http.ResponseWriter, r *http.Request) {
    if !rp.cb.AllowRequest() {
        http.Error(w, "service unavailable", http.StatusServiceUnavailable)
        return
    }
    
    ctx, cancel := context.WithTimeout(r.Context(), rp.timeout)
    defer cancel()
    
    req := r.Clone(ctx)
    req.URL.Scheme = "http"
    req.URL.Host = rp.target
    
    client := &http.Client{Timeout: rp.timeout}
    resp, err := client.Do(req)
    if err != nil {
        rp.cb.RecordFailure()
        http.Error(w, "service error", http.StatusBadGateway)
        return
    }
    defer resp.Body.Close()
    
    rp.cb.RecordSuccess()
    
    // 转发响应
    for k, v := range resp.Header {
        for _, vv := range v {
            w.Header().Set(k, vv)
        }
    }
    w.WriteHeader(resp.StatusCode)
    io.Copy(w, resp.Body)
}
```

---

## 第五部分：自测题

### 问题 1
gRPC 相比 REST API 有什么优势？

<details>
<summary>查看答案</summary>

1. **性能**：HTTP/2 + Protobuf，传输效率高
2. **强类型**：Protobuf 定义接口，编译时检查
3. **流式通信**：支持 Server/Client/Bidi Streaming
4. **代码生成**：自动生成客户端和服务端代码
5. **服务发现**：原生支持负载均衡

</details>

### 问题 2
熔断器的三种状态如何转换？

<details>
<summary>查看答案</summary>

1. **Closed**：正常状态，允许请求
2. **Open**：故障过多，拒绝请求
3. **HalfOpen**：试探性允许少量请求
4. **转换**：Closed → Open（失败超阈值），Open → HalfOpen（超时后），HalfOpen → Closed（成功）
5. **Go 实现**：CircuitBreaker 结构体

</details>

### 问题 3
API Gateway 为什么需要限流？

<details>
<summary>查看答案</summary>

1. **保护后端**：防止后端被压垮
2. **公平性**：防止单个用户占用过多资源
3. **成本控制**：限制 API 调用成本
4. **令牌桶算法**：平滑流量，允许突发
5. **Go 实现**：RateLimiter 结构体

</details>

---

*本文档基于微服务架构原理整理。*