#!/usr/bin/env python3
"""Generate devops-core.md for personal knowledge base."""

import os

# Try both paths
target_dir = os.path.expanduser("~/ryan-personal-knowledge/knowledge/infrastructure")
output_path = os.path.join(target_dir, "devops-core.md")

content = r"""# DevOps Core — CI/CD 进阶

> 广告平台技术 TL 知识库 | Docker · K8s · Service Mesh · GitOps

---

## 第一部分：入门引导（5 分钟速览）— DevOps 工具链概览

### 1.1 DevOps 工具链全景

```
┌─────────────────────────────────────────────────────────────────┐
│                     DevOps 持续交付流水线                        │
├──────────┬──────────┬──────────┬──────────┬──────────┬─────────┤
│ 代码提交  │ 构建     │ 镜像构建  │ 静态扫描  │ 测试     │ 部署    │
│          │          │          │          │          │         │
│ Git      │ CI       │ Container│ SAST/DAST│ Unit/E2E │ CD      │
│          │ Pipeline │ Runtime  │          │ Test     │         │
└────┬─────┴────┬─────┴────┬─────┴────┬─────┴────┬─────┴────┬────┘
     │          │          │          │          │          │
     ▼          ▼          ▼          ▼          ▼          ▼
  PR/MR    Code/Lint   Docker     SonarQube   Jest/      ArgoCD
  Webhook  Pipeline    Build      /Semgrep   pytest      /Flux
```

**核心概念：**

| 概念 | 说明 | 对应工具 |
|------|------|----------|
| CI (Continuous Integration) | 每次提交触发构建+测试 | GitHub Actions, Jenkins, GitLab CI |
| CD (Continuous Delivery/Deployment) | 自动将可信构建部署到目标环境 | ArgoCD, Flux, Spinnaker |
| IaC (Infrastructure as Code) | 基础设施声明式定义 | Terraform, Pulumi |
| GitOps | 以 Git 为唯一真实来源的 CD 模式 | ArgoCD, Flux |
| Service Mesh | 透明的流量治理层 | Istio, Linkerd |

### 1.2 容器时代 DevOps 范式转变

传统部署 → 容器部署的核心变化：

1. **镜像即制品**：不再传输 WAR/JAR，而是传输不可变 Docker Image
2. **声明式编排**：不再 SSH 到机器执行脚本，而是声明期望状态由 K8s reconciler 收敛
3. **声明式 GitOps**：目标状态存储在 Git，CD 控制器持续 reconcile
4. **边车模式**：治理能力从应用代码下沉到 Sidecar，应用零侵入

---

## 第二部分：Docker 进阶 — 镜像优化、多阶段构建、容器运行时

### 2.1 镜像分层原理与缓存优化

**Docker 镜像分层是写时复制 (CoW) 的 UnionFS：**

```
┌──────────────────────────────────────────┐
│  Layer 4: app (rw) — 容器运行时可修改       │
├──────────────────────────────────────────┤
│  Layer 3: app layer (ro) — 应用文件        │
├──────────────────────────────────────────┤
│  Layer 2: base layer (ro) — 系统依赖        │
├──────────────────────────────────────────┤
│  Layer 1: scratch/OS (ro) — 基础 OS        │
└──────────────────────────────────────────┘
```

**关键洞察：** `RUN apt-get update && apt-get install -y` 必须在同一层，否则 `apt-get install` 触发新层但 `update` 缓存失效。

### 2.2 Go 多阶段构建实战

```dockerfile
# ===== 生产 Dockerfile 最佳实践 =====
# Stage 1: 编译
FROM golang:1.22-alpine AS builder
RUN apk add --no-cache git ca-certificates
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download  # 利用层缓存：依赖不变不重新下载
COPY . .
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 \
    go build -ldflags="-s -w" -o /bin/server ./cmd/server

# Stage 2: 运行时
FROM scratch
# 从 builder 只复制二进制 + CA 证书
COPY --from=builder /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/
COPY --from=builder /bin/server /server
USER 65534:65534  # nobody:nobody
EXPOSE 8080
ENTRYPOINT ["/server"]
```

**Go 代码：容器优雅关闭 + 健康检查**

```go
package main

import (
	"context"
	"fmt"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/prometheus/client_golang/prometheus/promhttp"
)

// GracefulServer 封装容器的优雅关闭逻辑
type GracefulServer struct {
	httpServer *http.Server
	ln         net.Listener
}

func NewGracefulServer(addr string) *GracefulServer {
	mux := http.NewServeMux()
	mux.HandleFunc("/healthz", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		fmt.Fprint(w, "ok")
	})
	mux.HandleFunc("/readyz", func(w http.ResponseWriter, r *http.Request) {
		// 检查依赖：DB, Redis 等
		w.WriteHeader(http.StatusOK)
		fmt.Fprint(w, "ready")
	})
	mux.Handle("/metrics", promhttp.Handler())

	return &GracefulServer{
		httpServer: &http.Server{
			Addr:         addr,
			Handler:      mux,
			ReadTimeout:  5 * time.Second,
			WriteTimeout: 10 * time.Second,
			IdleTimeout:  60 * time.Second,
		},
	}
}

func (s *GracefulServer) Start() error {
	ln, err := net.Listen("tcp", s.httpServer.Addr)
	if err != nil {
		return err
	}
	s.ln = ln
	go func() {
		fmt.Printf("Server listening on %s\n", s.httpServer.Addr)
		if err := s.httpServer.Serve(ln); err != nil && err != http.ErrServerClosed {
			fmt.Fprintf(os.Stderr, "server error: %v\n", err)
		}
	}()
	return nil
}

func (s *GracefulServer) Stop(ctx context.Context) error {
	fmt.Println("shutting down...")
	return s.httpServer.Shutdown(ctx)
}

// 使用示例
func main() {
	srv := NewGracefulServer(":8080")
	if err := srv.Start(); err != nil {
		panic(err)
	}

	// 捕获 SIGTERM/SIGINT — K8s 发送 SIGTERM，grace period 后 SIGKILL
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGTERM, syscall.SIGINT)
	sig := <-quit

	fmt.Printf("received signal %v, shutting down gracefully\n", sig)

	// 给 K8s 留足够时间做 Service 端移除 endpoints
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()
	if err := srv.Stop(ctx); err != nil {
		fmt.Fprintf(os.Stderr, "shutdown error: %v\n", err)
		os.Exit(1)
	}
}
```

### 2.3 镜像优化清单

| 优化项 | 效果 | 做法 |
|--------|------|------|
| scratch 基础镜像 | 镜像体积 ~100x 缩小 | Go 静态编译后 FROM scratch |
| `-s -w` ldflags | 去除调试符号 | `go build -ldflags="-s -w"` |
| 多阶段构建 | 编译工具不进入最终镜像 | builder → scratch 两层 |
| `.dockerignore` | 避免 .git/.mod 进入构建上下文 | 排除 node_modules, .git |
| 层合并 | 减少层数 | `RUN` 命令用 `\` 连接 |
| `COPY --link` | 避免上下文缓存问题 | `COPY --link . .` |

### 2.4 容器运行时深度解析

**K8s 容器运行时接口 (CRI) 层次：**

```
Kubelet
  │
  ▼
Container Runtime Interface (CRI)
  │ gRPC: RunPodSandbox, CreateContainer, StartContainer...
  ▼
containerd (CRI shim: containerd-shim)
  │
  ▼
runc (OCI 运行时)
  │
  ▼
Linux 内核特性:
  - Namespaces (PID, Net, IPC, User, UTS, Mount)
  - cgroups v2 (CPU, Memory, PIDs, IO)
  - seccomp / AppArmor / SELinux
  - capabilities (CAP_NET_BIND_SERVICE, etc.)
```

**源码级：Kubelet 启动容器的关键路径：**

```go
// kubelet/cri/server/container_start.go (伪代码，基于 v0.30)

func (c *containerService) StartContainer(ctx context.Context, req *pb.StartContainerRequest) (*pb.StartContainerResponse, error) {
    // 1. 获取 Sandbox (Pod) 的 namespace
    sandboxID := req.PodSandboxId
    sandbox, err := c.sandboxStore.Get(sandboxID)
    if err != nil {
        return nil, err
    }
    // 2. 获取容器实例
    container := c.runtime.GetContainer(containerID)
    // 3. 调用 OCI 运行时 Start()
    //    → containerd-shim → runc start <container-id>
    //    → runc 设置 cgroups, 执行 execve()
    if err := c.runtime.Start(ctx, container.ID); err != nil {
        return nil, fmt.Errorf("failed to start container: %w", err)
    }
    // 4. 更新容器状态
    container.State().Status = containerdcontainer.Running
    return &pb.StartContainerResponse{}, nil
}
```

**runc 启动容器的底层流程：**

```
runc run container-id
  ├─ 1. 解析 config.json (OCI runtime spec)
  ├─ 2. 创建 namespace
  │     → clone(CLONE_NEWPID|CLONE_NEWNS|CLONE_NEWNET|...)
  ├─ 3. 挂载 cgroup v2
  │     → mount("cgroup2", "/sys/fs/cgroup", ...)
  │     → write("cpu.weight", "50")
  ├─ 4. 设置 capabilities
  │     → capset() + drop all + add needed
  ├─ 5. 应用 seccomp filter
  │     → seccomp(SECCOMP_SET_MODE_FILTER, ...)
  ├─ 6. chroot/jail 到 container rootfs
  ├─ 7. execve() 执行容器 CMD/ENTRYPOINT
  └─ 8. 通过 exec socket 通知 parent 容器已启动
```

---

## 第三部分：K8s 进阶 — Pod 生命周期、Service 发现、Ingress、HPA

### 3.1 Pod 生命周期深度解析

K8s Pod 生命周期比表面看起来更复杂：

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Pending    → kube-scheduler 调度到 Node                   │
│ 2. ContainerCreating → kubelet 拉镜像 + 创建容器              │
│ 3. Running    → 至少一个容器在运行                            │
│    ├─ PreStop Hook 触发 (默认 30s grace)                     │
│    ├─ SIGTERM → 应用开始优雅关闭                              │
│    ├─ Endpoint 从 Service 移除                                │
│    └─ ContainerDeath (SIGKILL if exceeds grace)              │
│ 4. Terminated |
└─────────────────────────────────────────────────────────────┘
```

**关键信号量关系：**

- `preStop` hook 执行期间，Pod 仍在 running 状态，但**已被从 Service endpoints 移除**
- K8s 发送 SIGTERM → 应用启动优雅关闭 → 完成后再 SIGKILL
- `terminationGracePeriodSeconds` 默认 30s，可调整

### 3.2 K8s 服务发现机制

```
┌──────────┐   DNS query    ┌──────────┐
│ Pod A     │ ────────────→ │ CoreDNS   │ ──→ IP ClusterIP
│           │ my-svc.ns.svc│ (etcd     │
│           │ .cluster.local│  backed) │
└──────────┘               └──────────┘

kube-proxy 数据面三种模式:
1. userspace (legacy, slow)
2. iptables     (O(N) match, no load balancing in-kernel)
3. IPVS         (O(1) hash table, preferred for scale)
```

**Go 代码：原生 K8s Client-go 服务发现**

```go
package main

import (
	"context"
	"fmt"
	"log"
	"os"

	v1 "k8s.io/api/core/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/client-go/kubernetes"
	"k8s.io/client-go/rest"
	"k8s.io/client-go/tools/clientcmd"
)

// ServiceWatcher 监听 Service 变更并重建连接
type ServiceWatcher struct {
	clientset *kubernetes.Clientset
	namespace  string
}

func NewServiceWatcher() (*ServiceWatcher, error) {
	var config *rest.Config
	var err error

	if _, ok := os.LookupEnv("KUBERNETES_SERVICE_HOST"); ok {
		config, err = rest.InClusterConfig()
	} else {
		kubeconfig := os.Getenv("HOME") + "/.kube/config"
		config, err = clientcmd.BuildConfigFromFlags("", kubeconfig)
	}
	if err != nil {
		return nil, fmt.Errorf("failed to create k8s config: %w", err)
	}

	clientset, err := kubernetes.NewForConfig(config)
	if err != nil {
		return nil, fmt.Errorf("failed to create k8s client: %w", err)
	}

	return &ServiceWatcher{
		clientset: clientset,
		namespace: os.Getenv("POD_NAMESPACE") || "default",
	}, nil
}

// GetServiceEndpoints 获取 Service 的实时 Endpoints
func (w *ServiceWatcher) GetServiceEndpoints(ctx context.Context, svcName string) ([]string, error) {
	ep, err := w.clientset.CoreV1().Endpoints(w.namespace).Get(ctx, svcName, metav1.GetOptions{})
	if err != nil {
		return nil, err
	}

	var ips []string
	for _, subset := range ep.Subsets {
		for _, addr := range subset.Addresses {
			if addr.IP != "" {
				ips = append(ips, addr.IP)
			}
		}
	}
	return ips, nil
}

// WatchService 使用 Informer 监听 Service 变更
func (w *ServiceWatcher) WatchService(ctx context.Context, svcName string) {
	services := w.clientset.CoreV1().Services(w.namespace)
	watcher, err := services.Watch(ctx, metav1.ListOptions{
		FieldSelector: "metadata.name=" + svcName,
	})
	if err != nil {
		log.Fatalf("watch error: %v", err)
	}

	for {
		select {
		case event := <-watcher.ResultChan():
			svc, ok := event.Object.(*v1.Service)
			if !ok {
				continue
			}
			log.Printf("Service %s updated: %d endpoints", svc.Name, len(svc.Status.Conditions))
		case <-ctx.Done():
			return
		}
	}
}
```

### 3.3 Ingress 原理与配置

**Ingress 控制器架构：**

```
Client → Ingress (K8s Resource) → Ingress Controller (nginx/contour/envoy)
         ┌─────────────────────────────────────────────────────┐
         │ 规则匹配:                                              │
         │  Host: ads-platform.com → Service: ad-server         │
         │  Host: api.ads-platform.com → Service: api-gateway    │
         └─────────────────────────────────────────────────────┘
```

**Ingress YAML 最佳实践：**

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: ad-platform-ingress
  annotations:
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    nginx.ingress.kubernetes.io/rate-limit: "100"
    nginx.ingress.kubernetes.io/cors-allow-origin: "https://ads.example.com"
    cert-manager.io/cluster-issuer: letsencrypt-prod
spec:
  ingressClassName: nginx
  tls:
  - hosts:
    - ads.example.com
    secretName: ads-tls-cert
  rules:
  - host: ads.example.com
    http:
      paths:
      - path: /api/v1/ads
        pathType: Prefix
        backend:
          service:
            name: ad-server-svc
            port:
              number: 8080
      - path: /api/v1/bid
        pathType: Prefix
        backend:
          service:
            name: bid-engine-svc
            port:
              number: 8080
```

### 3.4 HPA 深度解析

**HPA (Horizontal Pod Autoscaler) 三种类型：**

| 类型 | 指标 | 说明 |
|------|------|------|
| CPU/Memory | `container_cpu_usage_seconds_total` | 最常用，metrics-server 提供 |
| Custom | Prometheus 自定义指标 | `prometheus-adapter` 桥接 |
| Object | PVC 大小、外部资源 | 对象指标 |

**HPA 扩缩容逻辑源码级：**

```
1. metrics-server 每 15s 采集各 Pod 指标
2. HPA controller 每 15s 轮询
3. 计算 desiredReplicas:
   desiredReplicas = ceil(currentReplicas * (currentMetricValue / desiredMetricValue))
4. 考虑 stabilizationWindowSeconds (默认 300s)
5. 执行 Scale 操作 → Deployment 副本数更新 → ReplicaSet 管理 Pod 数量
```

**Go 代码：Custom Metric HPA 指标采集器**

```go
package main

import (
	"context"
	"fmt"
	"sync"

	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/labels"
	"k8s.io/metrics/pkg/apis/external_metrics"
	"k8s.io/metrics/pkg/client/externalmetrics"
)

// BidLatencyCollector 采集竞价延迟作为 HPA 自定义指标
type BidLatencyCollector struct {
	mux        sync.RWMutex
	podLatency map[string]float64
}

// GetExternalMetrics 被 K8s external metrics API 调用
func (c *BidLatencyCollector) GetExternalMetrics(
	ctx context.Context,
	metricSelector labels.Selector,
	info externalmetrics.CustomMetricInfo,
) ([]externalmetrics.ExternalMetricValue, error) {
	c.mux.RLock()
	defer c.mux.RUnlock()

	var values []externalmetrics.ExternalMetricValue
	for podName, latency := range c.podLatency {
		if latency > 500 {
			values = append(values, externalmetrics.ExternalMetricValue{
				MetricName:  "bid_latency_ms",
				MetricValue: int64(latency),
				Labels: map[externalmetrics.LabelName]interface{}{
					"pod": externalmetrics.LabelName(podName),
				},
				Timestamp: metav1.Now(),
			})
		}
	}
	return values, nil
}

// UpdatePodLatency 更新 Pod 延迟指标
func (c *BidLatencyCollector) UpdatePodLatency(podName string, latencyMs float64) {
	c.mux.Lock()
	defer c.mux.Unlock()
	c.podLatency[podName] = latencyMs
}
```

**HPA 扩缩容防震荡机制：**

```
┌─────────────────────────────────────────────────────────────┐
│ 扩缩容防震荡 (Anti-Stabilization)                           │
├─────────────────────────────────────────────────────────────┤
│ • stabilizationWindowSeconds: 300s (默认)                   │
│   → 只有变更值比窗口内所有历史值更 extreme 时才执行           │
│ • minChange: 10% (默认)                                     │
│   → 小幅波动不触发扩缩容                                      │
│ • P99 指标比平均指标更稳定 (减少突发噪声)                      │
└─────────────────────────────────────────────────────────────┘
```

---

## 第四部分：Service Mesh — Istio、Sidecar、流量管理、熔断

### 4.1 Istio 架构

```
┌───────────────────────────────────────────────────────────────────────┐
│                        Istio 控制面 (Control Plane)                    │
│                                                                       │
│  ┌──────────┐  ┌──────────┐  ┌────────────┐  ┌──────────┐            │
│  │ Pilot     │  │ Citadel  │  │ Galley      │  │ Telemetry │            │
│  │ (XDS)     │  │ (mTLS)   │  │ (Config)    │  │ (Prom)    │            │
│  └────┬─────┘  └──────────┘  └────────────┘  └──────────┘            │
│       │ XDS (CDS/EDS/LDS/RDS)                                        │
└───────┼───────────────────────────────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────────────────────────────────────┐
│                        数据面 (Data Plane) — Envoy Sidecar            │
│                                                                       │
│  ┌──────────┐     ┌──────────┐     ┌──────────┐                      │
│  │ Pod A     │     │ Pod B     │     │ Pod C     │                     │
│  │ App +     │     │ App +     │     │ App +     │                     │
│  │ Envoy     │◄───►│ Envoy     │◄───►│ Envoy     │                     │
│  │ :15001    │     │ :15001    │     │ :15001    │                     │
│  └──────────┘     └──────────┘     └──────────┘                      │
│       ▲               ▲               ▲                                │
│       │ 双向 mTLS      │ 双向 mTLS      │ 双向 mTLS                     │
└───────┴───────────────┴───────────────┴───────────────────────────────┘
```

**Istio 核心组件：**

| 组件 | 职责 | 协议 |
|------|------|------|
| Pilot | 服务发现 + 配置分发 (XDS) | gRPC stream |
| Citadel | 证书签发 + mTLS 管理 | — |
| Mixer (deprecated in 1.20+) | 策略检查 + 遥测收集 | — |
| Ingress/Gateway | L7 流量入口 | HTTP/TCP/UDP |

### 4.2 Sidecar 注入原理

**自动注入过程：**

```
1. Pod 创建 → admission webhook 拦截
2. istio-injector 在 Pod spec 中:
   - 插入 envoy container (sidecar)
   - 修改 initContainer 设置 iptables 规则
   - 添加 env: ISTIO_INJECTION=enabled
3. kubelet 创建 initContainer:
   - 执行 iptables -t nat -A PREROUTING ...
   - 将 80/443 流量重定向到 Envoy :15006
4. Pod 启动:
   - App 绑定 :8080
   - Envoy 绑定 :15001 (管理), :15006 (Ingress), :15008 (Egress)
```

**initContainer iptables 规则（关键）：**

```bash
# istio-init 容器执行的核心规则
# 重定向所有出站 HTTP 到 Envoy
iptables -t nat -N ISTIO_OUTPUT
iptables -t nat -A OUTPUT -p tcp --dport 15008 -j ISTIO_OUTPUT
iptables -t nat -A OUTPUT -m owner --uid-owner 1337 -j ISTIO_OUTPUT
iptables -t nat -A OUTPUT -p tcp -j REDIRECT --to-port 15001
```

### 4.3 流量管理 — VirtualService + DestinationRule

```yaml
# 蓝绿/灰度发布 — 流量权重分配
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: ad-server-vs
spec:
  hosts:
  - ad-server
  http:
  - match:
    - headers:
        x-canary:
          exact: "true"
    route:
    - destination:
        host: ad-server
        subset: v2-canary
      weight: 100
  - route:
    - destination:
        host: ad-server
        subset: v1-stable
      weight: 90
    - destination:
        host: ad-server
        subset: v2-canary
      weight: 10
---
apiVersion: networking.istio.io/v1beta1
kind: DestinationRule
metadata:
  name: ad-server-dr
spec:
  host: ad-server
  subsets:
  - name: v1-stable
    labels:
      version: v1
  - name: v2-canary
    labels:
      version: v2
```

**Go 代码：Istio 客户端动态更新 VirtualService**

```go
package main

import (
	"context"
	"fmt"

	istioclientset "istio.io/client-go/pkg/clientset/versioned"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/client-go/rest"
)

// TrafficSplitter 动态调整灰度流量权重
type TrafficSplitter struct {
	client istioclientset.Interface
	ns     string
}

func NewTrafficSplitter() (*TrafficSplitter, error) {
	config, err := rest.InClusterConfig()
	if err != nil {
		return nil, err
	}
	client, err := istioclientset.NewForConfig(config)
	if err != nil {
		return nil, err
	}
	return &TrafficSplitter{
		client: client,
		ns:     "default",
	}, nil
}

// SetCanaryWeight 设置 canary 流量百分比
func (t *TrafficSplitter) SetCanaryWeight(ctx context.Context, vsName string, stableWeight, canaryWeight int) error {
	if stableWeight+canaryWeight != 100 {
		return fmt.Errorf("weights must sum to 100, got %d+%d", stableWeight, canaryWeight)
	}

	vs, err := t.client.NetworkingV1beta1().VirtualServices(t.ns).Get(ctx, vsName, metav1.GetOptions{})
	if err != nil {
		return fmt.Errorf("get vs: %w", err)
	}

	// 更新第一条 HTTP 路由的权重
	if len(vs.Spec.Http) == 0 {
		return fmt.Errorf("no http routes in VirtualService %s", vsName)
	}

	route := vs.Spec.Http[0].Route
	route[0].Weight = int32(stableWeight)
	if len(route) > 1 {
		route[1].Weight = int32(canaryWeight)
	}

	_, err = t.client.NetworkingV1beta1().VirtualServices(t.ns).Update(ctx, vs, metav1.UpdateOptions{})
	return err
}

// GradualRollout 渐进式灰度：从 0% → 5% → 10% → 30% → 50% → 100%
func (t *TrafficSplitter) GradualRollout(ctx context.Context, vsName string, steps []int, interval time.Duration) error {
	for _, step := range steps {
		if err := t.SetCanaryWeight(ctx, vsName, 100-step, step); err != nil {
			return err
		}
		fmt.Printf("canary weight: %d%%\n", step)
		time.Sleep(interval)
	}
	return nil
}
```

### 4.4 熔断与超时

```
请求链路:
Client → Gateway → [Istio Retry + Timeout] → [Circuit Breaker] → Backend

熔断三态:
┌─────────┐    错误率 > 阈值    ┌──────────┐    恢复期过去    ┌──────────┐
│ OPEN     │ ─────────────────→ │ HALF-OPEN │ ─────────────→ │ CLOSED   │
│ (拒绝)   │ ◄───────────────── │ (探测)   │                │ (正常)   │
└─────────┘                   └──────────┘                └──────────┘
  错误率 < 阈值
```

**熔断配置（YAML）：**

```yaml
apiVersion: networking.istio.io/v1beta1
kind: DestinationRule
metadata:
  name: bid-engine-dr
spec:
  host: bid-engine.default.svc.cluster.local
  trafficPolicy:
    connectionPool:
      tcp:
        maxConnections: 1000
        connectTimeout: 50ms
      http:
        http1MaxPendingRequests: 1024
        http2MaxRequests: 1024
        maxRequestsPerConnection: 10
        maxRetries: 3
    outlierDetection:
      consecutive5xxErrors: 5
      interval: 10s
      baseEjectionTime: 30s
      maxEjectionPercent: 50
    tls:
      mode: ISTIO_MUTUAL
```

**Go 代码：应用层 Circuit Breaker**

```go
package main

import (
	"context"
	"fmt"
	"sync"
	"sync/atomic"
	"time"

	"github.com/sony/gobreaker"
)

// CircuitBreaker 应用层熔断器
type CircuitBreaker struct {
	breaker *gobreaker.TypewriterBreaker[any]
	stats   *atomic.Uint64 // 总请求数
	errors  *atomic.Uint64 // 失败数
}

func NewCircuitBreaker(name string) *CircuitBreaker {
	cb := gobreaker.NewTypewriterBreaker[gobreaker.Settings]{
		Name:    name,
		ReadyToTrip: func(counts gobreaker.Counts) bool {
			failureRatio := float64(counts.TotalFailures) / float64(counts.Requests)
			return counts.Requests >= 10 && failureRatio >= 0.5
		},
		OnStateChange: func(name string, from gobreaker.State, to gobreaker.State) {
			fmt.Printf("circuit breaker [%s]: %s → %s\n", name, from, to)
		},
		Interval:   60 * time.Second,
		Timeout:    30 * time.Second,
	}
	return &CircuitBreaker{
		breaker: &cb,
		stats:   &atomic.Uint64{},
		errors:  &atomic.Uint64{},
	}
}

func (cb *CircuitBreaker) Execute(ctx context.Context, operation func(ctx context.Context) error) error {
	cb.stats.Add(1)
	result, err := cb.breaker.Execute(func() (any, error) {
		return nil, operation(ctx)
	})
	if err != nil {
		cb.errors.Add(1)
		return err
	}
	_ = result
	return nil
}

func (cb *CircuitBreaker) Stats() (total, failures uint64) {
	return cb.stats.Load(), cb.errors.Load()
}
```

---

## 第五部分：GitOps — ArgoCD、Flux、持续交付

### 5.1 GitOps 核心原则

| 原则 | 说明 |
|------|------|
| 声明式 | 系统状态用 YAML 声明，而非过程式脚本 |
| 版本化 | Git 是所有变更的唯一真实来源 (SSOT) |
| 拉模式 | CD 控制器主动拉取 Git 变更，而非推送 |
| 自动化 | 自动 reconcile 集群状态与 Git 声明 |
| 一致性 | 持续监控漂移并自动修复 |
| 审计 | 所有变更通过 Git commit/PR 审计 |

### 5.2 ArgoCD 架构

```
┌─────────────────────────────────────────────────────────────────┐
│                      Git (Source of Truth)                       │
│  repo: apps/production/                                          │
│    ├── k8s/                                                      │
│    │   ├── ad-server/                                           │
│    │   │   ├── kustomization.yaml                                │
│    │   │   ├── deployment.yaml                                   │
│    │   │   └── service.yaml                                      │
│    │   └── bid-engine/                                           │
│    └── overlays/                                                 │
│        ├── staging/                                              │
│        └── production/                                           │
└──────────────────────┬────────────────────────────────────────────┘
                       │ git pull (every 3min)
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                      ArgoCD Controller                           │
│                                                                 │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐                  │
│  │ Repo     │───►│ Diff     │───►│ Sync     │                  │
│  │ Server   │    │ Engine   │    │ Operator │                  │
│  └──────────┘    └──────────┘    └──────────┘                  │
│                                                                 │
│  状态: OutOfSync → 自动/手动 Sync → Healthy                     │
└──────────────────────┬────────────────────────────────────────────┘
                       │ kubectl apply
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                        K8s Cluster                               │
│  ad-server deployment: replicas=3, image:ads:v2.1               │
│  bid-engine deployment: replicas=5, image:bid:3.0               │
└─────────────────────────────────────────────────────────────────┘
```

**ArgoCD Application YAML：**

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: ad-platform
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/company/k8s-manifests.git
    targetRevision: main
    path: k8s/ad-server
  destination:
    server: https://kubernetes.default.svc
    namespace: ad-platform
  syncPolicy:
    automated:
      prune: true        # 自动删除 Git 中不存在的资源
      selfHeal: true     # 自动修复手动漂移
    syncOptions:
    - CreateNamespace=true
```

### 5.3 持续交付流水线（广告平台场景）

```
┌─────────────────────────────────────────────────────────────────┐
│ 广告平台 CI/CD Pipeline                                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Step 1: Code → Build → Test                                    │
│    git push → CI (GitHub Actions)                                │
│      ├── go test -race                                          │
│      ├── go build -ldflags="-s -w"                               │
│      ├── docker build -t ads-platform:sha123 .                   │
│      ├── trivy image ads-platform:sha123  # 镜像扫描            │
│      ├── push to ACR/ECR                                       │
│      └── update k8s manifest (image tag)                        │
│                                                                 │
│  Step 2: GitOps → Auto Sync                                    │
│    ArgoCD detects git change → sync to staging                  │
│      ├── ad-server → staging namespace                           │
│      ├── bid-engine → staging namespace                          │
│      └── run integration tests against staging                  │
│                                                                 │
│  Step 3: Promotion to Production                                │
│    PR to production branch → merge → ArgoCD auto-sync           │
│      ├── canary deployment (10% → 50% → 100%)                  │
│      ├── monitor error rate / latency                           │
│      └── auto rollback on anomaly                               │
│                                                                 │
│  Step 4: Monitoring & Feedback                                  │
│    Prometheus → Grafana → Alert on SLO violations               │
│    K6 load test → HPA scale out                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Go 代码：Git 文件同步器（简化版 ArgoCD AppManager）**

```go
package main

import (
	"context"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"time"
)

// GitRepoSyncer 定期拉取 Git 仓库并返回变更
type GitRepoSyncer struct {
	repoURL  string
	localDir string
	ref      string
	interval time.Duration
}

func NewGitRepoSyncer(repoURL, localDir, ref string, interval time.Duration) *GitRepoSyncer {
	return &GitRepoSyncer{
		repoURL:  repoURL,
		localDir: localDir,
		ref:      ref,
		interval: interval,
	}
}

// CloneOrPull 克隆或拉取最新代码
func (s *GitRepoSyncer) CloneOrPull(ctx context.Context) error {
	if _, err := os.Stat(s.localDir); os.IsNotExist(err) {
		// 首次克隆
		cmd := exec.CommandContext(ctx, "git", "clone", "--depth", "1", "-b", s.ref, s.repoURL, s.localDir)
		cmd.Stdout = os.Stdout
		cmd.Stderr = os.Stderr
		return cmd.Run()
	}
	// 拉取更新
	cmd := exec.CommandContext(ctx, "git", "-C", s.localDir, "pull", "--ff-only")
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	return cmd.Run()
}

// ListManifests 列出指定目录下的所有 YAML 文件
func (s *GitRepoSyncer) ListManifests(dir string) ([]string, error) {
	var manifests []string
	err := filepath.Walk(filepath.Join(s.localDir, dir), func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return err
		}
		if !info.IsDir() && (filepath.Ext(path) == ".yaml" || filepath.Ext(path) == ".yml") {
			manifests = append(manifests, path)
		}
		return nil
	})
	return manifests, err
}

// Sync 执行 sync 循环
func (s *GitRepoSyncer) Sync(ctx context.Context) error {
	for {
		select {
		case <-ctx.Done():
			return ctx.Err()
		default:
		}

		if err := s.CloneOrPull(ctx); err != nil {
			fmt.Fprintf(os.Stderr, "git pull failed: %v\n", err)
			time.Sleep(s.interval / 2)
			continue
		}

		manifests, err := s.ListManifests("k8s/ad-server")
		if err != nil {
			fmt.Fprintf(os.Stderr, "list manifests failed: %v\n", err)
			continue
		}

		for _, m := range manifests {
			cmd := exec.CommandContext(ctx, "kubectl", "apply", "-f", m, "--prune", "-l", "app=ad-server")
			out, err := cmd.CombinedOutput()
			fmt.Printf("applied %s: %s\n", m, string(out))
			if err != nil {
				fmt.Fprintf(os.Stderr, "apply failed: %v\n", err)
			}
		}

		time.Sleep(s.interval)
	}
}
```

### 5.4 Argo Rollouts — 渐进式交付

```yaml
# Argo Rollout CRD — 金丝雀发布
apiVersion: argoproj.io/v1alpha1
kind: Rollout
metadata:
  name: ad-server-rollout
spec:
  replicas: 10
  revisionHistoryLimit: 3
  selector:
    matchLabels:
      app: ad-server
  strategy:
    canary:
      steps:
      - setWeight: 10        # 10% → 10 replicas (1 canary)
      - pause: {duration: 5m} # 观察 5 分钟
      - setWeight: 30        # 30% → 3 canary
      - pause: {duration: 5m}
      - setWeight: 50        # 50%
      - pause: {duration: 10m}
      - setWeight: 100       # 全量
  analysis:
    templates:
    - templateName: ad-server-slo
  progressDeadlineSeconds: 600
```

---

## 第六部分：自测题

### 6.1 题目一：Docker 镜像层缓存

**问题：** 以下 Dockerfile 中 `RUN apt-get update` 和 `RUN apt-get install -y nginx` 分开写会导致什么问题？如何修复？

```dockerfile
FROM ubuntu:22.04
RUN apt-get update
RUN apt-get install -y nginx
```

**参考答案：**

```
问题：
- 两个 RUN 命令产生两个独立的层
- 修改任何后面的 RUN（如 apt-get install）都会使前面的层（apt-get update）缓存失效
- 每次重建镜像时 apt-get update 都会重新执行，浪费时间

修复：
FROM ubuntu:22.04
RUN apt-get update && apt-get install -y nginx && rm -rf /var/lib/apt/lists/*
- 合并为一条 RUN 命令，确保在同一层
- 清理 apt 缓存减少镜像体积
```

### 6.2 题目二：K8s Service 发现

**问题：** 在 K8s 集群中，Pod A 如何访问 Pod B？请描述完整的数据流，包括 DNS 查询和 kube-proxy 的角色。

**参考答案：**

```
完整数据流:

1. DNS 查询 (CoreDNS):
   Pod A → kube-dns ClusterIP (10.96.0.10:53)
   → query: my-svc.default.svc.cluster.local.
   → CoreDNS 查询 etcd/apisix → 返回 ClusterIP

2. Service ClusterIP:
   → kube-proxy 通过 iptables/IPVS 规则将 ClusterIP 流量
     负载均衡到后端 Pod IP (随机/轮询)

3. kube-proxy 数据面:
   - iptables 模式: 每条规则 O(N)，大量 Service 时性能下降
   - IPVS 模式: hash table O(1)，支持更多负载均衡算法

4. 最终到达 Pod B 的 network namespace
```

### 6.3 题目三：Service Mesh vs Sidecar

**问题：** Istio 的 Sidecar 注入后，Pod 内的应用是否需要修改代码？为什么？如果应用监听了 0.0.0.0:8080，流量是如何被 Envoy 拦截的？

**参考答案：**

```
答案:

1. 不需要修改代码 — 零侵入设计:
   - Envoy 作为 Sidecar 监听 :15001 (管理) + :15006 (Ingress)
   - initContainer 设置 iptables 规则，将所有出站 :80/:443 流量
     重定向到 Envoy :15001
   - 应用仍然监听 :8080，但入站流量通过 Envoy 代理

2. 流量拦截流程:
   Pod A :8080 (App)
     ▲
     │ iptables PREROUTING REDIRECT :80 → :15006
     │
   Envoy Sidecar :15006 (Ingress Listener)
     │
     │ mTLS 加密 → Envoy-to-Envoy 双向认证
     │
   Envoy Sidecar Pod B :15006 → :8080

3. 应用层 (App) 对 Service Mesh 完全透明:
   - 无需引入 Istio SDK
   - 无需修改网络库
   - 只需保证 liveness/readiness probe 指向 :8080
```

---

> **最后更新：** 2026-06-12
> **维护者：** Ryan (广告平台技术 TL)
"""

os.makedirs(os.path.dirname(output_path), exist_ok=True)
with open(output_path, "w", encoding="utf-8") as f:
    f.write(content)

# Print verification
stat = os.stat(output_path)
lines = content.count("\n")
print(f"OK: Written {stat.st_size} bytes, {lines} lines to {output_path}")
