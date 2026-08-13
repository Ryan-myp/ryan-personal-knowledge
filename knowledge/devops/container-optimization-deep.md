# 容器化优化 - 资深专家深度实现

## 一、镜像优化策略

### 1.1 多阶段构建

```dockerfile
# 阶段1: 构建
FROM golang:1.21-alpine AS builder
RUN apk add --no-cache git
WORKDIR /app
COPY . .
RUN go build -ldflags="-s -w" -o main .

# 阶段2: 运行
FROM alpine:3.19
RUN apk --no-cache add ca-certificates tzdata
COPY --from=builder /app/main /main
EXPOSE 8080
USER 65534:65534
CMD ["/main"]
```

### 1.2 镜像瘦身

```bash
# 优化前: 850MB
# 优化后: 25MB

# 使用Alpine基础镜像
FROM alpine:3.19

# 合并RUN命令减少层数
RUN apk add --no-cache git curl && \
    mkdir -p /app && \
    wget -O /app/app https://...

# 使用.dockerignore
node_modules/
.git/
*.md
```

## 二、运行时优化

```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-service
spec:
  template:
    spec:
      containers:
      - name: app
        image: my-app:latest
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
          runAsUser: 65534
```

## 三、安全加固

```dockerfile
# 非root用户运行
USER appuser

# 只读根文件系统
readOnlyRootFilesystem: true

# 最小权限
capabilities:
  drop: ["ALL"]
  add: ["NET_BIND_SERVICE"]
```

## 四、面试高频题

### Q1: 如何优化Docker镜像大小？

```
A:
1. 使用多阶段构建
2. 选择小基础镜像(Alpine/Distroless)
3. 合并RUN命令
4. 使用.dockerignore
```

### Q2: 如何保证容器安全？

```
A:
1. 非root运行
2. 只读文件系统
3. 镜像扫描
4. 最小权限原则
```

## 五、自测题

1. 实现一个安全的Go服务容器化配置
2. 如何优化构建速度？

---

## 参考文档

- [Docker最佳实践](https://docs.docker.com/build/building/best-practices/)
