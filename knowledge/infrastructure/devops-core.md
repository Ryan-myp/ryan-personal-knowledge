# DevOps 与 CI/CD 核心知识

> Docker / K8s 进阶 / Service Mesh / GitOps — 广告平台工程效率基石

---

## 第一部分：入门引导（5 分钟速览）

### 为什么广告平台需要 DevOps？

广告平台需要：
- **快速迭代**：竞价算法每周优化
- **高可用**：99.99% 可用性
- **弹性伸缩**：QPS 从 1 万到 100 万
- **灰度发布**：新算法先 1% 流量验证

### DevOps 工具链

```
代码 → 测试 → 构建 → 镜像 → 部署 → 监控
  │       │       │       │       │       │
  GitHub  Unit    Docker  K8s     Prometheus
  Codecov e2e     Registry  Helm    Grafana
```

---

## 第二部分：Docker 进阶

### 2.1 多阶段构建

```dockerfile
# 阶段 1: 构建
FROM golang:1.22 AS builder
WORKDIR /app
COPY . .
RUN CGO_ENABLED=0 go build -o my-service ./cmd/my-service

# 阶段 2: 运行
FROM alpine:3.19
COPY --from=builder /app/my-service /my-service
ENTRYPOINT ["/my-service"]
```

### 2.2 镜像优化

```
镜像大小对比：
- golang:1.22 → 1.2GB（不推荐作为基础镜像）
- golang:1.22-alpine → 400MB
- 多阶段 + alpine → 50MB

优化技巧：
1. 使用 alpine 基础镜像
2. 多阶段构建
3. 合并 RUN 指令（减少层）
4. .dockerignore 排除不必要的文件
```

### 2.3 Docker 网络

```
Docker 网络模式：
- bridge: 默认，容器间通过虚拟网卡通信
- host: 直接使用宿主机网络
- none: 无网络

广告平台实践：
- 微服务：bridge + Service Discovery
- 高性能场景：host（减少网络栈开销）
```

---

## 第三部分：K8s 进阶

### 3.1 Pod 生命周期

```
Pod 创建流程：
1. Scheduler 选择 Node
2. Kubelet 创建容器
3. PreStop Hook 执行（优雅关闭）
4. 容器启动
5. Liveness/Readiness Probe 检查

广告平台 Pod 配置：
resources:
  requests:
    memory: "512Mi"
    cpu: "500m"
  limits:
    memory: "1Gi"
    cpu: "1000m"
```

### 3.2 Service 发现

```yaml
apiVersion: v1
kind: Service
metadata:
  name: bid-service
spec:
  selector:
    app: bid-service
  ports:
  - port: 80
    targetPort: 8080
  type: ClusterIP
---
apiVersion: v1
kind: Ingress
metadata:
  name: bid-ingress
spec:
  rules:
  - host: bid.adplatform.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: bid-service
            port:
              number: 80
```

### 3.3 HPA 弹性伸缩

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: bid-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: bid-service
  minReplicas: 3
  maxReplicas: 100
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

---

## 第四部分：Service Mesh（Istio）

### 4.1 Sidecar 模式

```
Pod 结构：
┌─────────────────────────────────┐
│  App Container (bid-service)    │
│  Go HTTP Server                 │
│  ↓                             │
│  Envoy Sidecar                  │
│  - 负载均衡                     │
│  - 熔断                        │
│  - 限流                        │
│  - 监控                        │
│  ↓                             │
│  kube-proxy                     │
└─────────────────────────────────┘
```

### 4.2 Istio 流量管理

```yaml
# 灰度发布：10% 流量到新版本
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: bid-vsvc
spec:
  hosts:
  - bid.adplatform.com
  http:
  - route:
    - destination:
        host: bid-service
        subset: v1
      weight: 90
    - destination:
        host: bid-service
        subset: v2
      weight: 10
---
apiVersion: networking.istio.io/v1beta1
kind: DestinationRule
metadata:
  name: bid-dr
spec:
  host: bid-service
  subsets:
  - name: v1
    labels:
      version: v1
  - name: v2
    labels:
      version: v2
```

### 4.3 Go 中配合 Sidecar

```go
// Sidecar 透明代理，无需修改应用代码
// 但需要注意：
// 1. gRPC 连接池管理
// 2. TLS 终止在 Sidecar
// 3. 超时配置：virtualService + envoy
```

---

## 第五部分：GitOps（ArgoCD）

### 5.1 GitOps 流程

```
开发 → PR → CI 构建 → Push 镜像 → Update K8s YAML → Push Git
                                                              ↓
ArgoCD 监听 Git 仓库 → 自动同步 K8s 集群
```

### 5.2 ArgoCD 配置

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: bid-service
spec:
  project: default
  source:
    repoURL: https://github.com/myorg/k8s-manifests.git
    targetRevision: main
    path: manifests/bid-service
  destination:
    server: https://kubernetes.default.svc
    namespace: production
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
```

---

## 第六部分：自测题

### 问题 1
K8s 中如何优雅关闭 Pod？

<details>
<summary>查看答案</summary>

1. **SIGTERM → Grace Period → SIGKILL**：默认 30s
2. **Go 中优雅关闭**：
```go
signalCh := make(chan os.Signal, 1)
signal.Notify(signalCh, syscall.SIGTERM)
go func() {
    sig := <-signalCh
    log.Printf("Received %v, shutting down...", sig)
    ctx, cancel := context.WithTimeout(context.Background(), 20*time.Second)
    defer cancel()
    server.Shutdown(ctx)
}()
```
3. **PreStop Hook**：延迟 10s 后再发送 SIGTERM
4. **Readiness Probe**：关闭时立即失败，流量不再进来

</details>

### 问题 2
Service Mesh 相比传统 API Gateway 有什么优势？

<details>
<summary>查看答案</summary>

1. **透明代理**：应用无需修改代码
2. **统一治理**：负载均衡、熔断、限流统一配置
3. **可观测性**：自动收集请求指标、链路追踪
4. **多语言支持**：Go/Java/Python 等统一治理
5. **缺点**：Sidecar 增加网络延迟、运维复杂度

</details>

### 问题 3
GitOps 相比传统 CI/CD 有什么优势？

<details>
<summary>查看答案</summary>

1. **版本控制**：所有配置在 Git 中，可追溯
2. **自动化**：ArgoCD 自动同步，无需手动部署
3. **自我修复**：检测漂移并自动修复
4. **审计**：Git history 即审计日志
5. **回滚**：git revert 即可回滚

</details>

---

*本文档基于 DevOps 最佳实践整理，结合广告平台实战场景。*