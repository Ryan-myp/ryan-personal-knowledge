package main

import (
	"os"
	"strings"
)

func main() {
	var sb strings.Builder

	sb.WriteString(`# DevOps Core — CI/CD 进阶

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
// kubelet/cri/server/container_start.go (伪代码)

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

	// 判断在集群内还是集群外运行
	if _, ok := os.LookupEnv("KUBERNETES_SERVICE_HOST"); ok {
		// 集群内：使用 InClusterConfig
		config, err = rest.InClusterConfig()
	} else {
		// 集群外：使用 kubeconfig
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
	// 方法1: 通过 Endpoints 对象 (最底层)
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
    # nginx 控制器
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    nginx.ingress.kubernetes.io/rate-limit: "100"
    nginx.ingress.kubernetes.io/cors-allow-origin: "https://ads.example.com"
    # cert-manager 自动 TLS
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
	"log"
	"net/http"
	"sync"
	"time"

	v1 "k8s.io/api/autoscaling/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/runtime/schema"
	"k8s.io/client-go/dynamic"
	"k8s.io/client-go/kubernetes"
	"k8s.io/metrics/pkg/apis/external_metrics"
	"k8s.io/metrics/pkg/client/externalmetrics"
)

// BidLatencyCollector 采集竞价延迟作为 HPA 自定义指标
type BidLatencyCollector struct {
	clientset  *kubernetes.Clientset
	client     externalmetrics.ExternalMetricsClient
	mux        sync.RWMutex
	values     map[string]float64 // pod -> latency_ms
	podLatency map[string]float64
}

// Describe implements metrics.Collector interface
func (c *BidLatencyCollector) Describe(ch chan<- *metrics.Desc) {
	ch <- metrics.NewDesc("bid_latency_ms", "99th percentile bid processing latency in ms", nil, nil)
}

// Collect implements metrics.Collector interface
func (c *BidLatencyCollector) Collect(ch chan<- metrics.Metric) {
	c.mux.RLock()
	defer c.mux.RUnlock()
	for _, v := range c.podLatency {
		ch <- metrics.NewMetric(v)
	}
}

// GetExternalMetrics 被 K8s external metrics API 调用
func (c *BidLatencyCollector) GetExternalMetrics(ctx context.Context, metricSelector labels.Selector, info externalmetrics.CustomMetricInfo) ([]externalmetrics.ExternalMetricValue, error) {
	c.mux.RLock()
	defer c.mux.RUnlock()

	var values []externalmetrics.ExternalMetricValue
	for podName, latency := range c.podLatency {
		if latency > 500 { // 延迟阈值
			values = append(values, externalmetrics.ExternalMetricValue{
				MetricName: "bid_latency_ms",
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

// HPA Configuration for bid-engine:
// apiVersion: autoscaling/v2
// kind: HorizontalPodAutoscaler
// metadata:
//   name: bid-engine-hpa
// spec:
//   scaleTargetRef:
//     apiVersion: apps/v1
//     kind: Deployment
//     name: bid-engine
//   minReplicas: 3
//   maxReplicas: 50
//   metrics:
//   - type: Pods
//     pods:
//       metric:
//         name: bid_latency_ms
//       target:
//         type: AverageValue
//         averageValue: "200"  # 平均延迟 200ms 以下不扩容
`

	// 写入文件
	err := os.WriteFile(filePath, []byte(content), 0644)
	if err != nil {
		fmt.Fprintf(os.Stderr, "failed to write file: %v\n", err)
		os.Exit(1)
	}
	fmt.Println("File written successfully!")
}

`