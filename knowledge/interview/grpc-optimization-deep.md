# gRPC性能优化 - 资深专家深度实现

## 一、传输层优化

```go
package grpc

import (
    "google.golang.org/grpc"
    "google.golang.org/grpc/credentials/insecure"
)

func NewOptimizedClient() *grpc.ClientConn {
    conn, err := grpc.NewConnection(
        "localhost:50051",
        grpc.WithTransportCredentials(insecure.NewCredentials()),
        grpc.WithKeepaliveParams(keepalive.ClientParameters{
            Time:                10 * time.Second,
            Timeout:             20 * time.Second,
            PermitWithoutStream: true,
        }),
        grpc.WithInitialWindowSize(1<<20),
        grpc.WithInitialConnWindowSize(1<<20),
    )
    return conn
}
```

## 二、流式传输

```go
// 服务端流
func (s *server) StreamData(req *Empty, stream pb.Service_StreamDataServer) error {
    for i := 0; i < 100; i++ {
        stream.Send(&Data{Value: i})
    }
    return nil
}

// 客户端流
func (s *server) CollectData(stream pb.Service_CollectDataServer) error {
    var sum int32
    for {
        req, err := stream.Recv()
        if err == io.EOF {
            return stream.SendAndClose(&Result{Sum: sum})
        }
        sum += req.Value
    }
}

// 双向流
func (s *server) Chat(stream pb.Service_ChatServer) error {
    for {
        req, err := stream.Recv()
        if err == io.EOF {
            return nil
        }
        stream.Send(&Response{Message: req.Message})
    }
}
```

## 三、拦截器优化

```go
type timingInterceptor struct{}

func (i *timingInterceptor) UnaryInterceptor() grpc.UnaryServerInterceptor {
    return func(ctx context.Context, req interface{}, 
        info *grpc.UnaryServerInfo, handler grpc.UnaryHandler) (interface{}, error) {
        start := time.Now()
        resp, err := handler(ctx, req)
        elapsed := time.Since(start)
        log.Printf("RPC: %s, cost: %v", info.FullMethod, elapsed)
        return resp, err
    }
}
```

## 四、面试高频题

### Q1: gRPC和REST的区别？

```
A:
• gRPC: HTTP/2 + Protobuf，高性能
• REST: HTTP + JSON，兼容性好
```

### Q2: 如何实现服务熔断？

```
A:
1. Circuit Breaker模式
2. 超时控制
3. 重试策略
```

## 五、自测题

1. 解释流式传输类型
2. 如何实现负载均衡？
3. 如何优化延迟？

---

## 参考文档

- [gRPC官方文档](https://grpc.io/docs/)
- [gRPC-go源码](https://github.com/grpc/grpc-go)
