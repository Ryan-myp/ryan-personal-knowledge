# Docker & Container 深度解析

> 深入 Docker 核心：命名空间、控制组、UnionFS、网络模型。
> 容器运行时实现，包含 Kubernetes 集成。
> 适用对象：DevOps 工程师、运维工程师、后端工程师

---

## 1. Docker 架构

### 1.1 核心组件

```
┌─────────────────────────────────────────────────────────────┐
│                      Docker 架构                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                    Docker Client                    │   │
│  │              (CLI / API)                            │   │
│  └──────────────────────┬──────────────────────────────┘   │
│                         │                                   │
│                         ▼                                   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                  Docker Daemon                       │   │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐             │   │
│  │  │ HTTP    │  │ Image   │  │ Container│             │   │
│  │  │ API     │  │ Manager │  │ Manager │             │   │
│  │  └─────────┘  └─────────┘  └─────────┘             │   │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐             │   │
│  │  │ Network │  │ Volume  │  │ Plugin  │             │   │
│  │  │ Manager │  │ Manager │  │ Manager│             │   │
│  │  └─────────┘  └─────────┘  └─────────┘             │   │
│  └─────────────────────────────────────────────────────┘   │
│                         │                                   │
│                         ▼                                   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                   runc / containerd                 │   │
│  │  (容器运行时)                                        │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 容器生命周期

```
镜像 → 创建容器 → 启动 → 运行 → 停止 → 删除
                ↑
              提交 → 新镜像
```

---

## 2. 命名空间 (Namespaces)

### 2.1 隔离机制

```c
// Linux Namespaces

// PID 命名空间 - 进程隔离
pid_t clone(NULL, child_stack, CLONE_NEWPID | SIGCHLD, NULL);

// NET 命名空间 - 网络隔离
int netns = socket(AF_NETLINK, SOCK_RAW, NETLINK_ROUTE);
setns(netns, CLONE_NEWNET);

// MNT 命名空间 - 文件系统隔离
mount("/var/lib/container/rootfs", "/", NULL, MS_REC | MS_PRIVATE, NULL);

// UTS 命名空间 - 主机名隔离
sethostname("container", 9);

// IPC 命名空间 - 进程间通信隔离
// SYS 命名空间 - 系统调用隔离

// USER 命名空间 - 用户权限隔离
```

### 2.2 实现原理

```
┌─────────────────────────────────────────────────────────────┐
│                    命名空间隔离                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  PID Namespace      NET Namespace     MNT Namespace         │
│  ┌──────────┐      ┌──────────┐      ┌──────────┐          │
│  │ PID 1    │      │ eth0     │      │ /        │          │
│  │ PID 2    │      │ eth1     │      │ /bin     │          │
│  │ PID 3    │      │ lo       │      │ /etc     │          │
│  └──────────┘      └──────────┘      └──────────┘          │
│                                                             │
│  宿主进程无法看到容器进程（反之亦然）                          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. 控制组 (cgroups)

### 3.1 资源限制

```bash
# 创建 cgroup
mkdir /sys/fs/cgroup/cpu/mycontainer
echo 50000 > /sys/fs/cgroup/cpu/mycontainer/cpu.cfs_quota_us
echo 100000 > /sys/fs/cgroup/cpu/mycontainer/cpu.cfs_period_us

# 限制内存
mkdir /sys/fs/cgroup/memory/mycontainer
echo 512M > /sys/fs/cgroup/memory/mycontainer/memory.limit_in_bytes

# 限制 IO
mkdir /sys/fs/cgroup blkio/mycontainer
echo "8:0 1000" > /sys/fs/cgroup/blkio/mycontainer/blkio.throttle.read_bps_device
```

### 3.2 cgroups 层级

```
┌─────────────────────────────────────────────────────────────┐
│                     cgroup 层级                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  system.slice                                               │
│  ├─ docker.service                                          │
│  │   └─ container1                                         │
│  │       ├─ cpu: 50%                                       │
│  │       ├─ memory: 512MB                                   │
│  │       └─ io: 100MB/s                                    │
│  │                                                         │
│  └─ container2                                             │
│      ├─ cpu: 30%                                           │
│      ├─ memory: 256MB                                      │
│      └─ io: 50MB/s                                         │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. UnionFS 文件系统

### 4.1 层叠文件系统

```
┌─────────────────────────────────────────────────────────────┐
│                  UnionFS 层叠结构                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Layer 3 (RW - 容器读写层)                                   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  + app.log                                          │   │
│  │  ~ /etc/config (修改)                                │   │
│  │  - /bin/bash (覆盖)                                  │   │
│  └─────────────────────────────────────────────────────┘   │
│                           ▲                                 │
│                           │ merge                           │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Layer 2 (RO - 镜像层)                                │   │
│  │  /etc/passwd                                        │   │
│  │  /bin/bash                                          │   │
│  │  /lib/libc.so                                       │   │
│  └─────────────────────────────────────────────────────┘   │
│                           ▲                                 │
│                           │ merge                           │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Layer 1 (RO - 基础镜像)                              │   │
│  │  /bin/sh                                            │   │
│  │  /lib                                               │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 Dockerfile 最佳实践

```dockerfile
# 多阶段构建
FROM golang:1.21 AS builder
WORKDIR /app
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -o main .

FROM alpine:3.18
RUN apk --no-cache add ca-certificates tzdata
COPY --from=builder /app/main /app/main
CMD ["/app/main"]
```

---

## 5. 网络模型

### 5.1 网络类型

```bash
# bridge 网络（默认）
docker network create --driver bridge mynet

# host 网络
docker run --network host nginx

# none 网络
docker run --network none nginx

# overlay 网络（Swarm）
docker network create -d overlay mynet
```

### 5.2 网络架构

```
┌─────────────────────────────────────────────────────────────┐
│                    Docker 网络模型                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  bridge 模式:                                               │
│  ┌─────────┐    ┌─────────────────┐    ┌─────────┐        │
│  │ Container│───►│  docker0 (桥接)  │───►│Container│        │
│  │   1     │    │  172.17.0.1/16   │    │   2    │        │
│  └─────────┘    └────────┬────────┘    └─────────┘        │
│                          │ NAT                              │
│                          ▼                                 │
│                    ┌──────────┐                             │
│                    │  宿主机   │                             │
│                    └──────────┘                             │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 6. Kubernetes 集成

### 6.1 Pod 网络

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: myapp
  labels:
    app: myapp
spec:
  containers:
  - name: app
    image: myapp:latest
    ports:
    - containerPort: 8080
    resources:
      limits:
        memory: "128Mi"
        cpu: "500m"
      requests:
        memory: "64Mi"
        cpu: "250m"
```

### 6.2 Service 网络

```yaml
apiVersion: v1
kind: Service
metadata:
  name: myapp-service
spec:
  selector:
    app: myapp
  ports:
  - port: 80
    targetPort: 8080
  type: ClusterIP
```

---

## 7. 性能优化

### 7.1 镜像优化

```dockerfile
# 使用多阶段构建减小镜像大小
FROM golang:1.21-alpine AS builder
RUN apk add --no-cache git ca-certificates
WORKDIR /build
COPY . .
RUN CGO_ENABLED=0 go build -ldflags="-w -s" -o app

FROM scratch
COPY --from=builder /build/app /app
COPY --from=builder /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/
CMD ["/app"]
```

### 7.2 资源限制

```yaml
resources:
  limits:
    cpu: "2"
    memory: "4Gi"
    ephemeral-storage: "10Gi"
  requests:
    cpu: "500m"
    memory: "1Gi"
    ephemeral-storage: "1Gi"
```

---

## 8. 故障排查

### 8.1 常用命令

```bash
# 查看容器状态
docker ps -a

# 查看容器日志
docker logs -f <container>

# 进入容器
docker exec -it <container> bash

# 查看资源使用
docker stats

# 查看镜像
docker images

# 清理无用资源
docker system prune -a
```

### 8.2 常见问题

| 问题 | 症状 | 排查命令 | 解决方案 |
|------|------|----------|----------|
| 容器启动失败 | Exit 1 | `docker logs` | 检查日志 |
| 端口冲突 | Bind failed | `netstat -tlnp` | 修改端口 |
| 磁盘满 | No space | `docker system df` | 清理资源 |
| OOM | OOMKilled | `docker stats` | 增加内存限制 |

---

## 9. 总结

### 9.1 核心原理回顾

| 特性 | 实现机制 |
|------|----------|
| 进程隔离 | PID Namespace |
| 网络隔离 | NET Namespace |
| 文件系统隔离 | MNT Namespace |
| 资源限制 | cgroups |
| 层叠存储 | UnionFS |

### 9.2 最佳实践

- [ ] 使用多阶段构建减小镜像
- [ ] 设置资源限制
- [ ] 使用 healthcheck
- [ ] 定期清理无用资源
- [ ] 监控容器性能

---

*最后更新：2026-08-11*
*作者：Ryan*
