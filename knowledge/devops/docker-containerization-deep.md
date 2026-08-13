# Docker容器化 - 资深专家深度实现

## 一、容器架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       Docker容器架构                                     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │                        Host OS                                  │   │
│   │  ┌─────────────────────────────────────────────────────────┐   │   │
│   │  │                    Docker Daemon                         │   │   │
│   │  │  ┌──────────┐  ┌──────────┐  ┌──────────┐             │   │   │
│   │  │  │ Container│  │ Container│  │ Container│  ...        │   │   │
│   │  │  │    1     │  │    2     │  │    3     │             │   │   │
│   │  │  └──────────┘  └──────────┘  └──────────┘             │   │   │
│   │  └─────────────────────────────────────────────────────────┘   │   │
│   │                                                                  │   │
│   │  隔离机制:                                                       │   │
│   │  • PID Namespace - 进程隔离                                     │   │
│   │  • Network Namespace - 网络隔离                                 │   │
│   │  • Mount Namespace - 文件系统隔离                               │   │
│   │  • User Namespace - 用户隔离                                    │   │
│   │  • Cgroup - 资源限制                                            │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、Dockerfile最佳实践

```dockerfile
# 多阶段构建
FROM golang:1.21-alpine AS builder

WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -o main .

FROM alpine:3.18
WORKDIR /app
COPY --from=builder /app/main .
EXPOSE 8080
USER nobody
ENTRYPOINT ["./main"]
```

## 三、面试高频题

### Q1: Docker容器如何实现隔离？

```
A:
1. Linux Namespace
2. Cgroup限制
3. AppArmor/SELinux
```

### Q2: 容器与虚拟机的区别？

```
A:
• 容器: 共享内核，轻量级
• 虚拟机: 独立内核，重量级
```

## 四、自测题

1. 解释Docker构建流程
2. 如何实现容器安全？
3. 如何优化镜像大小？

---

## 参考文档

- [Docker文档](https://docs.docker.com/)
- [Docker源码](https://github.com/moby/moby)
