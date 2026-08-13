# 容器化与镜像优化深度实现 - 资深专家

## 一、镜像构建优化

### 1.1 多阶段构建

```dockerfile
# 第一阶段：编译
FROM golang:1.21 AS builder
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -o /app/bin/server .

# 第二阶段：运行时
FROM scratch
COPY --from=builder /app/bin/server /server
EXPOSE 8080
ENTRYPOINT ["/server"]
```

### 1.2 层级缓存优化

```dockerfile
# 错误示例：频繁变更的代码放在前面
COPY . .
RUN go build

# 正确示例：先复制依赖文件，利用缓存
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN go build
```

## 二、运行时优化

### 2.1 资源限制

```yaml
# Kubernetes资源配置
resources:
  limits:
    cpu: "2"
    memory: "2Gi"
  requests:
    cpu: "500m"
    memory: "512Mi"

# cgroup配置
# memory.limit_in_bytes = 2147483648
# cpu.cfs_quota_us = 200000
```

### 2.2 安全加固

```dockerfile
# 非root用户运行
USER nobody
# 只读文件系统
RO
# 禁止信号
-no-new-privileges
```

## 三、面试高频题

1. 如何实现最小镜像？
2. 多阶段构建的原理？
3. 容器安全最佳实践？

---

## 参考文档

- [Docker Best Practices](https://docs.docker.com/develop/develop-images/dockerfile_best-practices/)
- [Container Security](https://kubernetes.io/docs/concepts/security/)
