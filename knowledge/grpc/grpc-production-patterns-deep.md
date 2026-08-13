# gRPC 生产环境最佳实践

> 深入 gRPC 生产部署：服务端设计、客户端实现、负载均衡、链路追踪。

---

## 1. Proto 定义规范

```protobuf
syntax = "proto3";
package ads.v1;

service AdService {
  rpc GetAd (GetAdRequest) returns (GetAdResponse) {}
  rpc SearchAds (SearchAdsRequest) returns (stream SearchAdsResponse) {}
}
```

---

## 2. 服务端实现

```go
type AdServiceServer struct {
    pb.UnimplementedAdServiceServer
    cache *redis.Client
}

func (s *AdServiceServer) GetAd(ctx context.Context, req *pb.GetAdRequest) (*pb.GetAdResponse, error) {
    if req.GetAdId() == "" {
        return nil, status.Errorf(codes.InvalidArgument, "ad_id required")
    }
    ad, err := s.fetchAd(ctx, req.GetAdId())
    if err != nil {
        return nil, status.Errorf(codes.Internal, "internal error")
    }
    return &pb.GetAdResponse{Ad: ad}, nil
}
```

---

## 3. 拦截器

```go
func AuthInterceptor(ctx context.Context, req interface{}, info *grpc.UnaryServerInfo, handler grpc.UnaryHandler) (interface{}, error) {
    token := metadata.ValueFromIncomingContext(ctx, "authorization")
    if !validateToken(token[0]) {
        return nil, status.Errorf(codes.Unauthenticated, "invalid token")
    }
    return handler(ctx, req)
}
```

---

## 4. 实践 Checklist
- [ ] 合理设计 Proto 消息
- [ ] 实现服务端拦截器
- [ ] 配置客户端超时和重试
- [ ] 启用链路追踪

**参考**: gRPC 官方文档、分布式系统 gRPC 最佳实践
