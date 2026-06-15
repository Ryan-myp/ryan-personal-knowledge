# CI/CD 与工程化：Go 构建优化/Docker 多阶段/K8s 配置管理

> 多阶段构建/缓存优化/GitOps/K8s Operator/配置中心

---

## 第一部分：入门引导（5 分钟速览）

### 为什么需要 CI/CD？

广告平台需要：
- **快速迭代**：竞价算法每周优化
- **高可用**：99.99% 可用性
- **可追溯**：每次变更可回溯
- **自动化**：减少人为错误

### CI/CD 流水线

```
代码提交 → 单元测试 → 静态分析 → 构建镜像 → 推送仓库
    → 测试环境部署 → 集成测试 → 生产部署 → 监控告警
```

---

## 第二部分：Go 多阶段构建

### 2.1 优化 Dockerfile

```dockerfile
# 阶段1: 构建
FROM golang:1.21-alpine AS builder

# 安装依赖
RUN apk add --no-cache git ca-certificates

# 设置工作目录
WORKDIR /app

# 复制 go.mod/go.sum
COPY go.mod go.sum ./
RUN go mod download

# 复制源码
COPY . .

# 构建
RUN CGO_ENABLED=0 GOOS=linux go build -a -installsuffix cgo \
    -ldflags="-w -s" -o /app/server .

# 阶段2: 运行
FROM alpine:3.18

# 安装运行时依赖
RUN apk add --no-cache ca-certificates tzdata

# 创建非 root 用户
RUN adduser -D appuser

# 复制二进制
COPY --from=builder /app/server /app/server

# 切换到非 root 用户
USER appuser

# 暴露端口
EXPOSE 8080

# 健康检查
HEALTHCHECK --interval=30s --timeout=3s \
    CMD wget -q --spider http://localhost:8080/health || exit 1

# 启动
CMD ["/app/server"]
```

### 2.2 构建优化技巧

```dockerfile
# 使用 BuildKit 缓存
# syntax=docker/dockerfile:1

FROM golang:1.21-alpine AS builder

# 缓存 go module
RUN --mount=type=cache,target=/go/pkg/mod \
    --mount=type=cache,target=/root/.cache/go-build \
    go mod download

# 只重新构建变更的文件
COPY go.mod go.sum ./
RUN --mount=type=cache,target=/go/pkg/mod \
    --mount=type=cache,target=/root/.cache/go-build \
    go mod download

COPY . .

RUN --mount=type=cache,target=/go/pkg/mod \
    --mount=type=cache,target=/root/.cache/go-build \
    CGO_ENABLED=0 go build -ldflags="-w -s" -o server .
```

---

## 第三部分：GitOps 部署

### 3.1 声明式配置

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: bidding-service
  namespace: advertising
spec:
  replicas: 3
  selector:
    matchLabels:
      app: bidding-service
  template:
    metadata:
      labels:
        app: bidding-service
    spec:
      containers:
      - name: server
        image: registry.example.com/bidding-service:v1.2.3
        ports:
        - containerPort: 8080
        resources:
          requests:
            cpu: 500m
            memory: 512Mi
          limits:
            cpu: 1000m
            memory: 1Gi
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8080
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: bidding-service
spec:
  selector:
    app: bidding-service
  ports:
  - port: 80
    targetPort: 8080
  type: ClusterIP
```

### 3.2 ArgoCD 配置

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: bidding-service
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/example/k8s-configs.git
    targetRevision: main
    path: environments/production/bidding-service
  destination:
    server: https://kubernetes.default.svc
    namespace: advertising
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
    - CreateNamespace=true
```

---

## 第四部分：配置管理

### 4.1 配置热更新

```go
package config

import (
    "sync"
    "time"
)

type Config struct {
    BidTimeout    time.Duration
    MaxRetries    int
    PoolSize      int
    CacheTTL      time.Duration
    version       int64
    mu            sync.RWMutex
}

var globalConfig = &Config{
    BidTimeout: 100 * time.Millisecond,
    MaxRetries: 3,
    PoolSize:   100,
    CacheTTL:   5 * time.Minute,
    version:    1,
}

func GetConfig() *Config {
    globalConfig.mu.RLock()
    defer globalConfig.mu.RUnlock()
    return globalConfig
}

func ReloadConfig(newConfig *Config) {
    globalConfig.mu.Lock()
    defer globalConfig.mu.Unlock()
    globalConfig.version++
    *globalConfig = *newConfig
}
```

---

## 第五部分：自测题

### 问题 1
Docker 多阶段构建有什么好处？

<details>
<summary>查看答案</summary>

1. **镜像小**：不包含编译工具和源码
2. **安全**：非 root 用户运行
3. **构建快**：利用 Docker 缓存
4. **镜像分层**：依赖层和应用层分离
5. **Alpine 基础**：镜像只有 5MB

</details>

### 问题 2
GitOps 相比传统部署有什么优势？

<details>
<summary>查看答案</summary>

1. **版本控制**：所有配置在 Git 中
2. **可追溯**：每次变更有 commit
3. **自动化**：ArgoCD 自动同步
4. **回滚简单**：git checkout 回退
5. **一致性**：配置即代码

</details>

### 问题 3
K8s 中如何保证服务高可用？

<details>
<summary>查看答案</summary>

1. **多副本**：replicas > 1
2. **健康检查**：liveness + readiness probe
3. **自动重启**：kubelet 检测容器状态
4. **Pod 反亲和**：分散部署
5. **资源限制**：防止资源争抢

</details>

---

*本文档基于 CI/CD 原理整理。*