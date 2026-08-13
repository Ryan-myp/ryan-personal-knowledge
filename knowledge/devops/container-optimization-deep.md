# 容器优化 - 资深专家深度实现

## 一、镜像优化

### 1.1 多阶段构建

```dockerfile
# 构建阶段
FROM golang:1.21 AS builder
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -o app .

# 运行阶段
FROM alpine:3.18
RUN apk --no-cache add ca-certificates tzdata
COPY --from=builder /app/app /usr/local/bin/
ENTRYPOINT ["app"]
```

### 1.2 镜像体积对比

```
基础镜像体积:
- Ubuntu: 72MB
- Alpine: 5MB
- Distroless: 200KB
- Scratch: 0B
```

## 二、运行时优化

### 2.1 资源限制

```yaml
# deployment.yaml
spec:
  containers:
  - name: app
    resources:
      requests:
        memory: "128Mi"
        cpu: "250m"
      limits:
        memory: "512Mi"
        cpu: "1000m"
```

### 2.2 健康检查

```yaml
livenessProbe:
  httpGet:
    path: /healthz
    port: 8080
  initialDelaySeconds: 3
  periodSeconds: 10

readinessProbe:
  httpGet:
    path: /ready
    port: 8080
  initialDelaySeconds: 1
  periodSeconds: 5
```

## 三、性能调优

### 3.1 网络优化

```bash
# 调整内核参数
sysctl -w net.core.somaxconn=65535
sysctl -w net.ipv4.tcp_max_syn_backlog=65535
```

### 3.2 存储优化

```yaml
volumes:
- name: tmp
  emptyDir:
    medium: Memory
    sizeLimit: 100Mi
```

## 四、安全加固

```dockerfile
FROM gcr.io/distroless/static
USER nonroot
COPY --from=builder /app/app /
ENTRYPOINT ["/app"]
```

## 五、面试高频题

### Q1: 如何优化容器启动速度？

```
A:
1. 使用轻量级基础镜像
2. 减少层数
3. 并行拉取镜像层
```

### Q2: 如何监控容器资源？

```
A:
1. cgroup统计
2. metrics-server
3. Prometheus exporter
```

## 六、自测题

1. 设计一个最小化Go应用镜像
2. 如何实现容器资源限制？

---

## 参考文档

- [Docker官方文档](https://docs.docker.com/)
