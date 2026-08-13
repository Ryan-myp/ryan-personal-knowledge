# gRPC性能优化 - 资深专家深度实现

## 一、性能瓶颈分析

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      gRPC性能瓶颈                                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   1. 序列化/反序列化                                                      │
│   2. 网络传输                                                           │
│   3. 流控控制                                                           │
│   4. 连接管理                                                           │
│   5. 负载均衡                                                           │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、序列化优化

```go
package proto

import (
    "google.golang.org/protobuf/proto"
    "github.com/golang/protobuf/jsonpb"
)

// Protobuf序列化
func MarshalProto(msg proto.Message) ([]byte, error) {
    return proto.Marshal(msg)
}

func UnmarshalProto(data []byte, msg proto.Message) error {
    return proto.Unmarshal(data, msg)
}

// JSONPb序列化（用于调试）
func MarshalJSON(msg proto.Message) ([]byte, error) {
    m := jsonpb.Marshaler{}
    return m.MarshalToString(msg)
}

// 性能对比
// Protobuf: ~10ns/op
// JSON:     ~100ns/op
// 压缩:     ~50% 体积减少
```

## 三、流式传输

```go
package grpc

import (
    "context"
    "google.golang.org/grpc"
    "google.golang.org/grpc/stream"
)

// Server Streaming
func (s *Server) WatchEvents(req *WatchRequest, stream pb.EventService_WatchEventsServer) error {
    for {
        event, err := s.eventStore.GetNext()
        if err != nil {
            return err
        }
        if err := stream.Send(event); err != nil {
            return err
        }
    }
}

// Client Streaming
func (s *Server) CollectMetrics(stream pb.MetricService_CollectMetricsServer) error {
    for {
        metric, err := stream.Recv()
        if err == io.EOF {
            return nil
        }
        if err != nil {
            return err
        }
        s.metricsStore.Save(metric)
    }
}

// Bidirectional Streaming
func (s *Server) StreamData(stream pb.DataService_StreamDataServer) error {
    for {
        req, err := stream.Recv()
        if err == io.EOF {
            return stream.SendAndClose(&Response{Data: processedData})
        }
        if err != nil {
            return err
        }
        if err := stream.Send(process(req)); err != nil {
            return err
        }
    }
}
```

## 四、负载均衡

```go
package balancer

import (
    "google.golang.org/grpc"
    "google.golang.org/grpc/balancer"
    "google.golang.org/grpc/balancer/base"
)

// 轮询负载均衡器
func NewRoundRobinBuilder() balancer.Builder {
    return base.NewBalancerBuilder(
        "round_robin",
        &roundRobinPicker{},
        base.Config{},
    )
}

type roundRobinPicker struct {
    currentIndex int
}

func (p *roundRobinPicker) Pick(info base.PickInfo) (base.PickResult, error) {
    subconns := info.ReadySCs
    if len(subconns) == 0 {
        return base.PickResult{}, balancer.ErrNoSubConnAvailable
    }
    
    idx := p.currentIndex % len(subconns)
    p.currentIndex++
    
    return base.PickResult{SubConn: subconns[idx]}, nil
}

// 自定义负载均衡策略
func registerCustomBalancer() {
    balancer.Register(&customBalancerBuilder{})
}
```

## 五、面试高频题

### Q1: gRPC相比HTTP/1.1有什么优势？

```
A:
• HTTP/2多路复用
• Protobuf高效序列化
• 原生流式支持
• 代码生成
```

### Q2: 如何处理gRPC超时？

```go
func withTimeout(ctx context.Context, timeout time.Duration) context.Context {
    return context.WithTimeout(ctx, timeout)
}

// 调用时
ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
defer cancel()

resp, err := client.SayHello(ctx, req)
```

## 六、自测题

1. gRPC流式有哪些类型？
2. 如何实现gRPC拦截器？
3. 如何监控gRPC性能？

---

## 参考文档

- [gRPC官方文档](https://grpc.io/docs/)
- [Protobuf指南](https://protobuf.dev/)
