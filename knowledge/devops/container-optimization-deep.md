# 容器化优化 - 资深专家深度实现

## 一、镜像优化策略

### 1.1 多阶段构建

```dockerfile
FROM golang:1.21-alpine AS builder
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -o /app/server .

FROM alpine:3.19
RUN apk --no-cache add ca-certificates tzdata
COPY --from=builder /app/server /server
EXPOSE 8080
CMD ["/server"]
```

### 1.2 镜像瘦身

| 优化项 | 优化前 | 优化后 |
|--------|--------|--------|
| 基础镜像 | Ubuntu 18.04 (72MB) | Alpine 3.19 (5MB) |
| 构建方式 | 单阶段 | 多阶段 |
| 层数 | 20层 | 5层 |

## 二、运行时优化

```yaml
resources:
  requests:
    memory: "256Mi"
    cpu: "250m"
  limits:
    memory: "512Mi"
    cpu: "500m"
securityContext:
  readOnlyRootFilesystem: true
  runAsNonRoot: true
```

## 三、面试高频题

### Q1: 如何优化Docker镜像大小？

```
A:
1. 多阶段构建
2. 使用Alpine基础镜像
3. 合并RUN命令
4. 使用.dockerignore
```

### Q2: 容器安全最佳实践？

```
A:
1. 非root运行
2. 只读文件系统
3. 镜像扫描
4. 最小权限
```

---

## 参考文档

- [Docker最佳实践](https://docs.docker.com/build/building/best-practices/)
