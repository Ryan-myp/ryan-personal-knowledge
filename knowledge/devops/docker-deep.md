# Docker容器化 - 资深专家深度实现

## 一、容器运行时

```go
// containerd-shim 实现
type shim interface {
    Start(ctx context.Context, r *taskspb.StartRequest) (*emptypb.Empty, error)
    DeleteTask(ctx context.Context, r *taskspb.DeleteTaskRequest) (*taskspb.DeleteTaskResponse, error)
    Wait(*taskspb.WaitRequest, taskpb.Task_WaitServer) error
}

// OCI Runtime Spec
type Spec struct {
    Version string `json:"ociVersion"`
    Platform Platform `json:"platform"`
    Root Root `json:"root"`
    Process Process `json:"process"`
    Linux Linux `json:"linux"`
}
```

## 二、镜像分层

```
┌─────────────────────────────────────┐
│            Layer 3 (RW)             │  ← 容器读写层
├─────────────────────────────────────┤
│            Layer 2 (RO)             │  ← 应用层
├─────────────────────────────────────┤
│            Layer 1 (RO)             │  ← 基础镜像
├─────────────────────────────────────┤
│         Union Filesystem            │  ← 合并视图
└─────────────────────────────────────┘
```

```dockerfile
# 多阶段构建优化
FROM golang:1.21 AS builder
WORKDIR /app
COPY . .
RUN go build -o main .

FROM alpine:3.18
COPY --from=builder /app/main /app/main
CMD ["/app/main"]
```

## 三、网络模式

```go
package network

type NetworkMode string

const (
    Bridge   NetworkMode = "bridge"
    Host     NetworkMode = "host"
    None     NetworkMode = "none"
    Container NetworkMode = "container"
)

func createNetwork(mode NetworkMode, config *NetworkConfig) error {
    switch mode {
    case Bridge:
        return createBridgeNetwork(config)
    case Host:
        return createHostNetwork(config)
    case None:
        return createNoneNetwork(config)
    default:
        return errors.New("unsupported network mode")
    }
}
```

## 四、面试高频题

### Q1: Docker和K8s的区别？

```
A:
• Docker: 容器运行时
• K8s: 容器编排平台
• Docker管理单容器，K8s管理集群
```

### Q2: 如何优化镜像大小？

```
A:
1. 使用多阶段构建
2. 选择小基础镜像 (alpine/distroless)
3. 减少RUN指令
4. 利用缓存层
```

## 五、自测题

1. 解释容器隔离原理
2. 如何实现镜像优化？
3. Docker网络有哪几种模式？

---

## 参考文档

- [Docker官方文档](https://docs.docker.com/)
- [containerd源码](https://github.com/containerd/containerd)
