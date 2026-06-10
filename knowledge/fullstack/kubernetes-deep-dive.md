# Kubernetes 容器编排源码级深度 — 从 API Server 到调度器的全链路剖析

> 标签: `#Kubernetes` `#K8s` `#容器编排` `#etcd` `#Scheduler` `#kubelet` `#源码级`
> 创建日期: 2026-06-10 | 作者: Ryan
> 定位: 资深专家级 — 从 API Server 到 Pod 生命周期，全链路源码级剖析

---

## 第一部分：入门引导（5 分钟速览）

### 1.1 Kubernetes 是什么？

Kubernetes（K8s）是一个**分布式容器编排系统**，核心目标：自动化容器部署、扩缩容、故障转移。

```
┌────────────────────────────────────────────────────────────┐
│                   K8s 控制平面 (Control Plane)              │
│                                                            │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │ API Server│  │ Scheduler│  │Controller│  │ Cloud    │  │
│  │ (6443/TCP)│  │          │  │ Manager  │  │ Controller│ │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  │
│       │              │              │              │       │
│       └──────────────┴──────────────┴──────────────┘       │
│                          │                                 │
│  ┌───────────────────────┴──────────────────────────────┐  │
│  │                    etcd (分布式存储)                   │  │
│  │  存储所有 Cluster State（Pod/Service/ConfigMap/...）   │  │
│  └──────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────┘
       │  │  │                    │  │  │
       ▼  ▼  ▼                    ▼  ▼  ▼
  ┌────────────┐           ┌────────────┐
  │ Node 1     │           │ Node 2     │
  │ kubelet    │           │ kubelet    │
  │ kube-proxy │           │ kube-proxy │
  │ CRI (containerd)│     │ CRI        │
  └────────────┘           └────────────┘
```

### 1.2 核心组件

| 组件 | 角色 | 关键端口 |
|------|------|----------|
| **API Server** | 控制平面入口，所有操作的唯一入口 | 6443 (HTTPS) |
| **etcd** | 分布式 Key-Value 存储，保存集群状态 | 2379, 2380 |
| **Scheduler** | 决定 Pod 调度到哪个 Node | 无公开端口 |
| **Controller Manager** | 维护期望状态 vs 实际状态的一致性 | 10252 |
| **kubelet** | Node 代理，管理容器生命周期 | 10250 |
| **kube-proxy** | 维护网络规则，实现 Service 网络 | 无公开端口 |
| **Container Runtime** | 容器运行时（containerd/CRI-O） | 10250 |

### 1.3 核心概念速查

| 概念 | 定义 | 类比 |
|------|------|------|
| **Pod** | 最小调度单元，包含 1+N 个容器 | 一台虚拟机 |
| **Deployment** | 无状态应用管理器 | 工厂的流水线 |
| **StatefulSet** | 有状态应用管理器 | 有固定编号的工人 |
| **DaemonSet** | 每个 Node 运行一个 Pod | 每个岗位配一个监控 |
| **Job/CronJob** | 批量任务/定时任务 | 临时工/定时闹钟 |
| **Service** | Pod 的稳定访问入口 | 总机号码 |
| **Ingress** | 七层路由（HTTP/HTTPS） | 前台接待 |
| **ConfigMap** | 配置注入 | 环境变量/配置文件 |
| **Secret** | 敏感信息注入 | 加密的配置文件 |
| **PV/PVC** | 持久化存储抽象 | 硬盘/USB |
| **Namespace** | 资源隔离 | 文件夹 |
| **RBAC** | 基于角色的访问控制 | 权限管理 |
| **NetworkPolicy** | Pod 间网络隔离 | 防火墙规则 |
| **HPA/VPA** | 自动扩缩容 | 自动增减人手 |
| **CRD/Operator** | 自定义资源 + 控制器 | 插件系统 |

---

## 第二部分：源码级深度剖析

### 2.1 API Server — 控制平面的心脏

```go
// apiserver.go — API Server 启动核心逻辑（抽象）
package kubernetes

import (
	"context"
	"k8s.io/apiserver/pkg/endpoints/filters"
	"k8s.io/apiserver/pkg/server"
)

// CreateKubeAPIServerConfig 构建 API Server 配置
func CreateKubeAPIServerConfig(ctx context.Context) (*Config, error) {
	etcdConfig := etcd3.Config{
		ServerList:      etcdServers,    // http://etcd1:2379,http://etcd2:2379
		CertFile:        "/etc/ssl/apiserver-etcd-client.crt",
		KeyFile:         "/etc/ssl/apiserver-etcd-client.key",
		TrustedCAFile:   "/etc/ssl/etcd/ca.crt",
		CompactionInterval: 5 * time.Minute, // 控制 etcd 压缩频率
	}

	return &Config{
		Etcd: etcdConfig,
		CorsAllowedOrigins: corsOrigins,
		Authentication: authConfig,
		Authorization:  authzConfig,
		FeatureGates: map[string]bool{
			"APIListChunking":          true,  // 大列表分块返回
			"WatchList":                true,  //  WATCH 优化
			"StorageVersionMigration":  true,  // API 版本迁移
			"SeamlessUpgrade":          true,  // 无缝升级
			"PodTopologySpread":        true,  // 拓扑分布约束
		},
	}
}

// RunAPIServer 启动 API Server
func RunAPIServer(ctx context.Context, config *Config) error {
	s, err := server.GenericAPIServerFromConfig(config)
	if err != nil {
		return err
	}
	
	// 注册所有 API Resource
	s.InstallAPIs(getAPIResourceConfigs()...)
	
	// 安装内置控制器
	s.GenericAPIServer.PrepareRun()
	
	// 健康检查端点
	healthz.InstallHandler(s.Handler,
		&healthz.HealthChecker{Name: "etcd", Checker: checkEtcdHealth},
		&healthz.HealthChecker{Name: "poststart", Checker: checkPostStartHooks},
	)
	
	// 启动 HTTP 服务 (HTTPS)
	go func() {
		if err := s.Handler.ListenAndServe(); err != nil {
			log.Fatal(err)
		}
	}()
	
	<-ctx.Done()
	return nil
}
```

**API Server 请求处理链路：**

```
Client Request
    │
    ▼
┌──────────────────────┐
│  Audit 日志记录       │ ← 记录所有请求
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  Authentication       │ ← Token/证书/X.509/Webhook
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  Admission Control    │ ← Webhook/AlwaysDeny/AlwaysAllow
│  (Mutating + Validating)│
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  Authorization (RBAC) │ ← Role → RoleBinding → Subject
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  Request Validation   │ ← schema 校验
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  Storage Interface    │ ← 写入 etcd
└──────────┬───────────┘
           │
           ▼
    Response to Client
```

**关键性能参数：**

| 参数 | 默认值 | 说明 | 调优建议 |
|------|--------|------|----------|
| `--etcd-servers` | - | etcd 端点 | 多副本用逗号分隔 |
| `--etcd-compaction-interval` | 5m | etcd 压缩间隔 | 大集群设 2-3m |
| `--max-requests-inflight` | 400 | 并发请求上限 | 根据 API Server 内存调整 |
| `--max-mutating-requests-inflight` | 200 | 写操作上限 | 生产建议 100-300 |
| `--watch-cache` | true | Watch 缓存 | 大集群建议开启 |
| `--watch-cache-sizes` | 500/200/50/20 | 不同资源类型缓存大小 | 根据资源频率调整 |
| `--request-timeout` | 5m | 请求超时 | 写操作建议 3-5m |
| `--service-cluster-ip-range` | - | Service IP 范围 | 不要与 Pod/Node CIDR 重叠 |

### 2.2 etcd — 分布式存储引擎

```go
// etcd 核心数据结构 — 集群状态存储
type ClusterState struct {
	// Pods
	Pods []corev1.Pod `json:"pods,omitempty"`
	
	// Services
	Services []corev1.Service `json:"services,omitempty"`
	
	// Deployments
	Deployments []appsv1.Deployment `json:"deployments,omitempty"`
	
	// ConfigMaps
	ConfigMaps []corev1.ConfigMap `json:"configmaps,omitempty"`
	
	// Secrets
	Secrets []corev1.Secret `json:"secrets,omitempty"`
	
	// Nodes
	Nodes []corev1.Node `json:"nodes,omitempty"`
	
	// PersistentVolumes
	PersistentVolumes []corev1.PersistentVolume `json:"persistentvolumes,omitempty"`
	
	// PersistentVolumeClaims
	PersistentVolumeClaims []corev1.PersistentVolumeClaim `json:"persistentvolumeclaims,omitempty"`
	
	// NetworkPolicies
	NetworkPolicies []networkingv1.NetworkPolicy `json:"networkpolicies,omitempty"`
	
	// Ingresses
	Ingresses []networkingv1.Ingress `json:"ingresses,omitempty"`
	
	// CustomResources (CRDs)
	CustomResources map[string]interface{} `json:"custom_resources,omitempty"`
}

// etcd 存储路径层级:
// /registry/<group>/<version>/<resource>/<namespace>/<name>
//
// 示例:
// /registry/pods/default/my-app-abc123-xyz789
// /registry/services/specs/default/kubernetes
// /registry/namespaces/default
// /registry/deployments/apps/my-app
// /registry/configmaps/kube-system/coredns

// etcd 存储优化
type EtcdOptimization struct {
	// 压缩: 定期压缩旧版本以减少磁盘空间
	CompactionInterval time.Duration // 5m 默认
	
	// 快照频率: 定期快照防止数据丢失
	SnapshotCount uint64 // 10000 默认
	
	// WAL 同步策略
	WALSyncInterval time.Duration // 0=自动
	
	// 最大存储限制
	QuotaBackendBytes int64 // 8GB 默认
	
	// 快照保留
	SnapshotCountRetention uint32 // 保留最近几个快照
}

// 存储路径示例:
// ├── registry/
// │   ├── pods/
// │   │   └── default/
// │   │       ├── my-app-abc123/  ← Pod
// │   │       └── my-app-def456/  ← Pod
// │   ├── services/
// │   │   └── specs/
// │   │       └── default/
// │   │           └── kubernetes/ ← Service
// │   ├── deployments/
// │   │   └── apps/
// │   │       └── default/
// │   │           └── my-app/ ← Deployment
// │   ├── namespaces/
// │   │   └── default/ ← Namespace
// │   └── nodes/
// │       └── worker-1/ ← Node
```

**etcd 生产调优：**

```yaml
# etcd 优化配置
etcd:
  # 性能
  quota-backend-bytes: 8589934592  # 8GB
  snapshot-count: 10000
  max-requests-bytes: 1572864  # 1.5MB
  
  # 一致性
  election-timeout: 5000  # 5s
  heartbeat-interval: 500  # 500ms
  
  # 存储
  compaction-interval: 300000  # 5m
  auto-compaction-mode: periodic  # periodic 或 revision
  auto-compaction-retention: "1"  # 保留 1h 的旧版本
  
  # 日志
  log-level: info
  log-outputs: [stderr]
  enable-v2: false  # 禁用 v2 API
```

**etcd 监控指标：**

| 指标 | 告警阈值 | 说明 |
|------|----------|------|
| `etcd_server_leader_changes_seen_total` | > 0 (5min) | Leader 切换次数 |
| `etcd_disk_wal_fsync_duration_seconds` | p99 > 500ms | WAL fsync 延迟 |
| `etcd_disk_backend_commit_duration_seconds` | p99 > 250ms | 后端提交延迟 |
| `etcd_server_has_leader` | == 0 | 无 Leader → 集群不可用 |
| `etcd_mvcc_db_total_size_in_bytes` | > quota | 存储空间不足 |

### 2.3 Scheduler — 调度算法源码级

```go
// scheduler.go — 调度器核心流程（抽象）
package scheduler

import (
	"k8s.io/kubernetes/pkg/scheduler/framework"
)

// Scheduler 调度器核心
type Scheduler struct {
	profile       *framework.Framework
	queue         *Queue                        // 调度队列
	cache         *Cache                        // 节点缓存
	algorithm     *Algorithm                    // 调度算法
	evaluator     *PredicatesEvaluator         // 预选评估器
	scoreEvaluator *ScoringEvaluator           // 优先级评估器
}

// ScheduleOne 调度单个 Pod
func (s *Scheduler) ScheduleOne(ctx context.Context) {
	pod := s.queue.Pop()  // 从调度队列取 Pod
	
	// Phase 1: 预选 (Predicates) — 过滤不符合条件的节点
	filteredNodes, err := s.evaluator.FilterNodes(ctx, pod)
	if err != nil {
		handleError(pod, err)
		return
	}
	
	if len(filteredNodes) == 0 {
		// 没有节点满足预选条件 → 绑定失败
		handleBindingFailure(pod, "no nodes available")
		return
	}
	
	// Phase 2: 优选 (Priorities) — 从满足条件的节点中选最优
 scoredNodes := s.scoreEvaluator.ScoreNodes(ctx, pod, filteredNodes)
	bestNode := scoredNodes[0]  // 得分最高的节点
	
	// Phase 3: 绑定 (Binding)
	err = s.bind(pod, bestNode.Name)
	if err != nil {
		handleBindingFailure(pod, err)
		return
	}
	
	// Phase 4: 更新缓存
	s.cache.UpdateCache(pod, bestNode.Name)
}

// Predicates 预选规则 — 过滤节点
var DefaultPredicates = []framework.PreEnqueuePredicate{
	PodFitsHostPorts,         // Pod 端口不冲突
	PodFitsResources,         // 资源足够 (CPU/Memory)
	NodeAffinity,             // 节点亲和性
	PodToleratesNodeTaints,   // 容忍节点污点
	MatchNodeSelector,        // 节点选择器匹配
	NoDiskConflict,           // 磁盘不冲突
	HostName,                 // 主机名冲突检查
}

// Scoring 优选规则 — 给节点打分
var DefaultPriorities = []framework.NodeScore{
	{
		Name:  "NodeResourcesLeastAllocated",  // 资源最少分配 → 得分最高
		Priority: 1,
		Weight: 1,  // 权重可配
	},
	{
		Name:  "NodeResourcesMostAllocated",   // 资源最多分配 (Bin Packing)
		Priority: 2,
		Weight: 1,
	},
	{
		Name:  "ImageLocality",                // 本地镜像优先
		Priority: 3,
		Weight: 1,
	},
	{
		Name:  "InterPodAffinity",             // 亲和性优先
		Priority: 4,
		Weight: 1,
	},
	{
		Name:  "TaintToleration",              // 污点容忍度
		Priority: 5,
		Weight: 1,
	},
}
```

**调度器预选/优选对比：**

| 阶段 | 目的 | 算法复杂度 | 关键规则 |
|------|------|------------|----------|
| **预选 (Filter)** | 排除不符合的节点 | O(N) × R (N=节点数, R=规则数) | 资源检查/亲和性/污点/端口 |
| **优选 (Score)** | 从合格节点中选最优 | O(N) × S (S=打分规则数) | 资源均衡/镜像本地化/拓扑分布 |
| **绑定 (Bind)** | 将 Pod 绑定到节点 | O(1) (本地操作) | 更新 etcd 状态 |

**调度器关键参数：**

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--scheduler-name` | default-scheduler | 调度器名称 |
| `--port` | 10251 | HTTP 监听端口 |
| `--leader-elect` | true | 多副本高可用 |
| `--kubeconfig` | - | kubeconfig 路径 |
| `--policy-configfile` | - | 自定义调度策略文件 |
| `--profile-config` | - | 调度框架 Profile 配置 |

### 2.4 Controller Manager — 一致性守护者

```go
// controller_manager.go — Controller 管理器核心
package controller_manager

// ControllerManager 管理所有 Controller
type ControllerManager struct {
	controllers map[string]controller  // 控制器名称 → 控制器实例
	
	// 核心控制器:
	// 1. replicationController — 维持 ReplicaSet/Deployment 的副本数
	// 2. endpointController — 维护 Service Endpoint
	// 3. serviceController — 维护 Service ClusterIP/Proxy rules
	// 4. nodeController — 维护 Node 状态
	// 5. podGCController — 垃圾回收完成/失败的 Pod
	// 6. namespaceController — 维护 Namespace 状态
	// 7. persistentVolumeController — PV/PVC 绑定
	// 8. replicaSetController — 管理 ReplicaSet 副本
	// 9. deploymentController — 管理 Deployment 策略
	// 10. cronJobController — CronJob 调度
	// 11. tokenController — ServiceAccount Token 管理
}

// ReplicationController 核心逻辑 (维持副本数)
type ReplicationController struct {
	desiredPods   int32      // 期望的 Pod 数
	actualPods    []Pod      // 实际 Pod 列表
	enqueue       chan *Pod  // Pod 变更通知
	enqueueFunc   func(*Pod) error
}

// Sync 同步循环 — 核心一致性保证
func (rc *ReplicationController) Sync() {
	actualPods := rc.listActualPods()
	currentCount := len(actualPods)
	
	if currentCount < int(rc.desiredPods) {
		// 缺 Pod → 创建
		rc.createPods(rc.desiredPods - int32(currentCount))
	} else if currentCount > int(rc.desiredPods) {
		// 多 Pod → 删除
		rc.deletePods(int32(currentCount) - rc.desiredPods)
	}
}

// DeploymentController 滚动更新策略
type DeploymentController struct {
	strategy *appsv1.DeploymentStrategy
}

func (dc *DeploymentController) Sync(deployment *appsv1.Deployment) {
	replicas := *deployment.Spec.Replicas
	maxSurge := intstr.GetValueFromIntOrPercent(deployment.Spec.Strategy.RollingUpdate.MaxSurge, int(replicas), true)
	maxUnavailable := intstr.GetValueFromIntOrPercent(deployment.Spec.Strategy.RollingUpdate.MaxUnavailable, int(replicas), true)
	
	currentRevision := deployment.Status.UpdatedReplicas
	availableReplicas := deployment.Status.AvailableReplicas
	
	if currentRevision < replicas {
		// 滚动更新: 先创建新 Pod, 再删除旧 Pod
		surgePods := min(int(currentRevision)+maxSurge, int(replicas))
		createCount := surgePods - int(currentRevision)
		deleteCount := max(0, int(currentRevision)+maxUnavailable-int(replicas))
		
		dc.createNewPods(createCount, deployment)
		dc.deleteOldPods(deleteCount, deployment)
	}
	
	// 更新状态
	dc.updateStatus(deployment)
}
```

### 2.5 kubelet — 节点代理

```go
// kubelet.go — kubelet 核心逻辑
package kubelet

// Kubelet 核心结构
type Kubelet struct {
	containerRuntime containerd.Runtime  // 容器运行时 (containerd)
	podManager       pod.Manager         // Pod 管理器
	livenessManager  liveness.Manager    // 存活检查
	readinessManager readiness.Manager   // 就绪检查
	podWorkers       map[podUID]*worker  // Pod 工作器
	
	// 核心配置
	cfg            KubeletConfiguration
	nodeName       string
	resourceManager ResourceManager
}

// SyncPod — 同步单个 Pod 到期望状态
func (kl *Kubelet) SyncPod(pod *v1.Pod, status v1.PodStatus, oldStatus v1.PodStatus, mirrors podcontainer.DefinedPodMirror) (Result, error) {
	podContainer, err := kl.podManager.GetContainer(pod.UID)
	if err != nil {
		return Result{}, err
	}
	
	// 1. 启动/更新/杀掉容器
	switch podContainer.Status {
	case containerNotStarted:
		kl.podWorkers.UpdatePod(&UpdatePodOptions{
			Pod:        pod,
			PodContainer: podContainer,
			MirrorPod:  mirrors.MirrorPod(),
		})
	case containerRunning:
		// 检查是否需要更新 (镜像变化, 配置变化)
		if needsUpdate(pod, podContainer) {
			kl.killContainer(podContainer)
			kl.podWorkers.UpdatePod(...)
		}
		// 检查存活/就绪
		kl.livenessManager.Check(pod, podContainer)
		kl.readinessManager.Check(pod, podContainer)
	case containerFailed:
		kl.handlePodFailure(pod, podContainer)
	}
	
	// 2. 执行存活检查 (Liveness Probe)
	if kl.livenessManager.IsUnhealthy(pod.UID, containerID) {
		// 触发重启
		kl.killContainer(podContainer)
		kl.podWorkers.UpdatePod(...)
	}
	
	// 3. 更新节点状态
	kl.nodeStatusManager.UpdateStatus(pod, containerStatuses)
	
	return Result{}, nil
}
```

**kubelet 核心配置：**

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--kubeconfig` | - | kubeconfig 路径 |
| `--config` | - | kubelet 配置文件 |
| `--pod-infra-container-image` | k8s.gcr.io/pause:3.9 | 基础设施容器镜像 |
| `--cgroup-driver` | cgroupfs/systemd | cgroup 驱动 |
| `--container-runtime` | remote | 容器运行时 |
| `--container-runtime-endpoint` | /run/containerd/containerd.sock | CRI 端点 |
| `--max-pods` | 110 | 单节点最大 Pod 数 |
| `--eviction-hard` | memory.available<100Mi | 内存驱逐阈值 |
| `--image-gc-high-threshold` | 85 | 镜像 GC 触发阈值 (%) |
| `--image-gc-low-threshold` | 80 | 镜像 GC 低水位 (%) |
| `--rotate-certificates` | true | 自动旋转证书 |
| `--rotate-server-certificates` | true | 自动旋转服务端证书 |

### 2.6 kube-proxy — Service 网络实现

```go
// kube-proxy.go — Service 网络三种模式
package kubeProxy

// ProxyMode 服务模式
type ProxyMode string

const (
	ModeUserspace    ProxyMode = "userspace"    // 传统模式 (K8s < 1.1)
	ModeProxyTables  ProxyMode = "iptables"     // iptables 模式 (K8s 1.1-1.10)
	ModeIPTables     ProxyMode = "iptables"     // 推荐模式 (K8s 1.10+)
	ModeIPVS         ProxyMode = "ipvs"         // 高性能模式 (K8s 1.11+)
	ModeeBPF         ProxyMode = "ebpf"         // 下一代 (K8s 1.20+, Alpha)
)

// IPTables 模式 — 通过 iptables 规则实现 Service
// iptables 规则链:
// KUBE-SERVICES → KUBE-NODEPORTS → KUBE-PORTALS-HOST → KUBE-PORTALS-CONTAINER
//
// 示例 iptables 规则 (Service: my-app:80 → Pods: 10.244.1.5:8080, 10.244.2.3:8080):
//
// -A KUBE-SERVICES -d 10.96.0.10/32 -p tcp -m comment --comment "default/kubernetes:https" -m tcp --dport 443 -j KUBE-SVC-XXXX
// -A KUBE-SVC-XXXX -m statistic --mode random --probability 0.33333 -j KUBE-SEP-AAAA
// -A KUBE-SVC-XXXX -m statistic --mode random --probability 0.50000 -j KUBE-SEP-BBBB
// -A KUBE-SVC-XXXX -j KUBE-SEP-CCCC
// -A KUBE-SEP-AAAA -p tcp -j DNAT --to-destination 10.244.1.5:8080
// -A KUBE-SEP-BBBB -p tcp -j DNAT --to-destination 10.244.2.3:8080
// -A KUBE-SEP-CCCC -p tcp -j DNAT --to-destination 10.244.3.7:8080

// IPVS 模式 — 通过 IPVS 实现高性能负载均衡
type IPVSService struct {
	ClusterIP   string            // Service ClusterIP
	Port        int               // Service Port
	Protocol    string            // TCP/UDP
	Backends    []IPVSBackend     // 后端 Pod
	Scheduler   string            // rr|wrr|lc|wlc|dh|sh|sed|nq
	Timeout     int               // 连接超时 (秒)
	MaxRetries  int               // 最大重试次数
}

type IPVSBackend struct {
	Addr string  // Pod IP
	Port int     // Pod Port
	Weight int   // 权重 (WLC 模式下使用)
}

// IPVS vs iptables 对比:
// iptables: O(N) 匹配规则, 规则数量多时性能下降
// IPVS: O(1) hash 查找, 适合大规模集群
//
// 推荐: 节点 > 200 或 Pod > 5000 时优先使用 IPVS
```

### 2.7 网络插件 — CNI 插件架构

```go
// CNI 插件接口 — Kubernetes 网络标准
package cni

// CNI Plugin 接口
type CNIPlugin interface {
	// AddNetwork 将 Pod 添加到网络 (Pod 创建时调用)
	AddNetwork(ctx context.Context, netconf NetworkConfig, pod *Pod) error
	
	// DeleteNetwork 从网络中删除 Pod (Pod 删除时调用)
	DeleteNetwork(ctx context.Context, netconf NetworkConfig, pod *Pod) error
	
	// CheckNetwork 检查 Pod 网络是否可达
	CheckNetwork(ctx context.Context, netconf NetworkConfig, pod *Pod) error
	
	// Status 返回插件状态
	Status(ctx context.Context) (*Status, error)
}

// 主流 CNI 插件:
// 1. Calico — BGP 路由 + NetworkPolicy, 高性能
// 2. Cilium — eBPF 实现, L7 策略, 服务网格集成
// 3. Flannel — 简单 VxLAN overlay, 适合小规模集群
// 4. Weave Net — 自带加密, 易用
// 5. Canal — Flannel + Calico NetworkPolicy
// 6. Antrea — VMware 出品, eBPF + OVS

// Cilium eBPF 网络模型 (K8s 现代替代):
// ┌─────────────────────────────────────────────┐
// │  eBPF Map (BPF map)                          │
// │  ┌─────────────────────────────────────┐    │
// │  │ 服务 VIP → Pod IP 映射               │    │
// │  │ 策略规则 (L3/L4/L7)                  │    │
// │  │ DNS 查询缓存                          │    │
// │  │ 负载均衡 (L4)                         │    │
// │  └─────────────────────────────────────┘    │
// │                                              │
// │  所有网络操作在内核中完成, 零拷贝, 零用户态   │
// │  上下文切换                                   │
└─────────────────────────────────────────────┘
```

### 2.8 Pod 生命周期 — 完整流程图

```
┌──────────────────────────────────────────────────────────────────────┐
│                     Pod 完整生命周期                                    │
│                                                                      │
│  1. Create Request → API Server (etcd 持久化)                        │
│         │                                                             │
│         ▼                                                             │
│  2. Scheduler 调度                                                   │
│     ├─ 预选: 过滤不满足条件的节点                                     │
│     └─ 优选: 从合格节点中选最优                                       │
│         │                                                             │
│         ▼                                                             │
│  3. Binding (Pod → Node)                                            │
│     └─ API Server 更新 Pod.spec.nodeName                             │
│         │                                                             │
│         ▼                                                             │
│  4. kubelet 发现新 Pod (Watch 机制)                                  │
│     ├─ 拉取镜像: Pull Image                                          │
│     ├─ 创建 sandbox (pause container)                                │
│     └─ 创建应用容器 (Container)                                       │
│         │                                                             │
│         ▼                                                             │
│  5. Pod 就绪检查                                                     │
│     ├─ PreStart Hook (Init Container 完成)                            │
│     ├─ Liveness Probe 配置生效                                       │
│     ├─ Readiness Probe 配置生效                                      │
│     └─ Startup Probe 配置生效                                        │
│         │                                                             │
│         ▼                                                             │
│  6. Running — Pod 正常运行                                           │
│     ├─ kubelet 持续监控存活/就绪                                     │
│     ├─ kube-proxy 更新 iptables/IPVS 规则                            │
│     └─ Endpoint Controller 更新 Service Endpoint                     │
│         │                                                             │
│         ▼                                                             │
│  7. 终止信号 (SIGTERM → SIGKILL)                                     │
│     ├─ PreStop Hook 执行 (等待请求处理完)                              │
│     ├─ GracePeriod 超时 (默认 30s)                                    │
│     └─ SIGKILL (强制终止)                                             │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 第三部分：生产环境实战

### 3.1 集群架构推荐

```
┌──────────────────────────────────────────────────────────────┐
│                  生产级 K8s 集群架构 (高可用)                   │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │                   External LB (HAProxy/Nginx)          │  │
│  │              VIP: 10.0.1.100:6443                      │  │
│  └───────────────┬────────────────────────────────────────┘  │
│                  │                                             │
│     ┌────────────┼────────────┐                              │
│     ▼            ▼            ▼                              │
│ ┌───────┐  ┌───────┐  ┌───────┐                            │
│ │ APIS │  │ APIS │  │ APIS │                            │
│ │ 1    │  │ 2    │  │ 3    │   ← 多副本 API Server         │
│ └───┬───┘  └───┬───┘  └───┬───┘                            │
│     │          │          │                               │
│     └──────────┼──────────┘                               │
│                ▼                                           │
│  ┌──────────────────────┐                                 │
│  │    etcd Cluster (3/5 nodes) │                         │
│  │  奇数节点 (3/5/7), 跨 AZ     │                         │
│  └──────────────────────┘                                 │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │                  Worker Nodes                           │  │
│  │  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐        │  │
│  │  │Node-1│ │Node-2│ │Node-3│ │Node-4│ │Node-5│ ...    │  │
│  │  └──────┘ └──────┘ └──────┘ └──────┘ └──────┘        │  │
│  │  kubelet │ kube-proxy │ containerd │ Calico/Cilium   │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

### 3.2 关键调优参数速查

| 层级 | 参数 | 推荐值 | 说明 |
|------|------|--------|------|
| **API Server** | `--etcd-compaction-interval` | 3m | 大集群缩短 |
| **API Server** | `--max-requests-inflight` | 800 | 根据内存调整 |
| **API Server** | `--service-cluster-ip-range` | 10.96.0.0/12 | 不要与 Pod CIDR 重叠 |
| **etcd** | `quota-backend-bytes` | 8GB | 防止磁盘爆满 |
| **etcd** | `auto-compaction-retention` | 1h | 保留 1h 旧版本 |
| **Scheduler** | `max-pods-per-node` | 110 | 根据 Node 规格调整 |
| **kubelet** | `--max-pods` | 110 | 单节点最大 Pod |
| **kubelet** | `--eviction-hard` | memory.available<500Mi,nodefs.available<10% | 驱逐阈值 |
| **kube-proxy** | `mode` | ipvs | 大规模集群用 IPVS |
| **CNI** | MTU | 1450 (VxLAN) | 根据插件调整 |
| **Containerd** | `pids_limit` | 1024 | 防止 fork 炸弹 |

---

## 第四部分：实战排障与调优

### 4.1 常见问题速查

| 症状 | 可能原因 | 排查命令 | 解决方案 |
|------|----------|----------|----------|
| **Pod Pending** | 资源不足/亲和性不满足 | `kubectl describe pod <name>` | 检查 Requests/Limits, 节点亲和性 |
| **Pod CrashLoopBackOff** | 应用启动失败 | `kubectl logs <name> -p` | 检查应用日志, 环境变量, 挂载卷 |
| **Node NotReady** | kubelet 异常/节点资源不足 | `kubectl get nodes` | 检查 kubelet 日志, 资源使用情况 |
| **Service 无法访问** | kube-proxy 异常/NetworkPolicy | `kubectl get endpoints <svc>` | 检查 endpoint, 检查 CNI 插件日志 |
| **etcd 延迟高** | 磁盘 I/O 慢/WAL fsync 阻塞 | `etcdctl endpoint health` | 换 SSD, 调优 etcd 参数 |
| **API Server 慢** | etcd 慢/请求过多 | `kubectl top nodes` | 检查 etcd, 增加 API Server 副本 |
| **Pod 频繁 Eviction** | 节点资源不足 | `kubectl describe node <name>` | 增加资源, 调整驱逐阈值 |
| **DNS 解析失败** | CoreDNS 异常 | `kubectl get pods -n kube-system | grep coredns` | 检查 CoreDNS 副本, 检查 resolv.conf |

### 4.2 排障黄金命令

```bash
# 1. 检查集群状态
kubectl get nodes -o wide
kubectl get namespaces
kubectl api-resources

# 2. 查看 Pod 详细信息 (排查 Pending/CrashLoop)
kubectl describe pod <name> [-n <namespace>]
kubectl get events --sort-by='.lastTimestamp'
kubectl logs <pod-name> -n <namespace> --previous  # 查看上一次崩溃日志

# 3. 查看资源使用
kubectl top nodes
kubectl top pods -n <namespace>

# 4. 检查网络
kubectl get svc
kubectl get endpoints <service-name> -n <namespace>
kubectl exec -it <pod> -- ping <target-ip>  # 测试 Pod 间连通

# 5. 检查 Node 状态
kubectl describe node <node-name>
kubectl logs -n kube-system kubelet-<node-name>

# 6. 检查 etcd
etcdctl endpoint health --cacert=/etc/ssl/etcd/ssl/ca.crt \
  --cert=/etc/ssl/etcd/ssl/healthcheck-client.crt \
  --key=/etc/ssl/etcd/ssl/healthcheck-client.key

# 7. 查看 API Server 性能
kubectl proxy --port=8001
curl http://localhost:8001/metrics  # Prometheus 指标

# 8. 查看调度事件
kubectl get events --field-selector reason=FailedScheduling
```

---

## 第五部分：自测

### Q1：K8s 中 Pod 从创建到 Running 的完整流程是什么？关键组件如何协作？

<details>
<summary>点击查看参考答案</summary>

1. **创建请求**: Client → API Server → etcd (持久化 Pod spec)
2. **调度**: Scheduler Watch etcd 新 Pod → 预选过滤节点 → 优选打分 → Binding (Pod.spec.nodeName)
3. **绑定**: API Server 更新 etcd 中 Pod 的 nodeName
4. **发现**: kubelet (通过 Watch 或 list-watch) 发现新 Pod
5. **镜像拉取**: kubelet → CRI (containerd) → Pull Image
6. **创建容器**: CRI → 创建 sandbox (pause) → 创建应用容器
7. **探针启动**: PreStart Hook → 容器启动 → Liveness/Readiness/Startup Probe
8. **网络就绪**: CNI 插件分配 IP, kube-proxy 更新 Service 规则
9. **Running**: Pod 进入 Running 状态, endpoint controller 更新 Service endpoint
</details>

### Q2：etcd 的压缩（compaction）和快照（snapshot）有什么区别？为什么要做这两个操作？

<details>
<summary>点击查看参考答案</summary>

**压缩 (Compaction)**:
- 清理 etcd 历史版本 (MVCC 多版本控制)
- 释放磁盘空间
- 类型：revision (按版本号) 或 periodic (按时间)
- 默认每 5 分钟执行一次

**快照 (Snapshot)**:
- 持久化 etcd 当前状态到磁盘
- 用于备份和恢复
- 默认每 10000 次写操作生成一个快照
- 可手动触发：`etcdctl snapshot save`

**为什么都需要**:
- 压缩：防止磁盘被旧版本占满
- 快照：防止数据丢失，灾难恢复

**生产建议**:
- 每 1h 压缩一次
- 每天快照备份 + 异地存储
- 保留最近 3-7 天的快照
</details>

### Q3：IPVS 模式相比 iptables 模式在性能上有什么优势？

<details>
<summary>点击查看参考答案</summary>

**iptables 模式**:
- 线性搜索规则链，O(N) 复杂度
- 规则越多，匹配越慢
- 大规模集群（>200 节点, >5000 Pod）时明显变慢
- 更新规则需要 flush + restore，有性能抖动

**IPVS 模式**:
- 使用 hash 表，O(1) 复杂度
- 内核态实现，零拷贝
- 支持多种负载均衡算法：rr/wrr/lc/wlc/dh/sh/sed/nq
- 支持健康检查和连接池
- 支持 TCP/UDP/SCTP 四层负载均衡

**切换方法**:
```yaml
# kube-proxy config
apiVersion: kubeproxy.config.k8s.io/v1alpha1
kind: KubeProxyConfiguration
mode: ipvs
ipvs:
  scheduler: wlc  # 加权最少连接
  minSyncPeriod: 0s
  syncPeriod: 30s
```
</details>

### Q4：K8s 的 readiness probe 和 liveness probe 有什么区别？什么时候应该用 startup probe？

<details>
<summary>点击查看参考答案</summary>

**Readiness Probe**:
- 决定 Pod 是否接受流量
- 失败 → Pod 从 Service endpoint 中移除
- 不影响 Pod 状态（Pod 仍然 Running）
- 适用：应用启动慢、依赖外部服务不可用

**Liveness Probe**:
- 决定 Pod 是否应该重启
- 失败 → kubelet 重启容器（计数，超过 threshold 才 kill）
- 适用：检测死锁、永久错误

**Startup Probe**:
- 专门给启动慢的应用
- 在它完成之前，不触发 liveness/readiness probe
- 适用：Java 应用、大型框架（Spring Boot 可能需要 30s+ 启动）

```yaml
# 示例：启动慢的 Java 应用
startupProbe:
  httpGet:
    path: /healthz
    port: 8080
  failureThreshold: 30  # 最多检查 30 次
  periodSeconds: 10     # 每 10 秒检查一次
  # → 总共允许 300s 启动时间
  
livenessProbe:
  httpGet:
    path: /healthz
    port: 8080
  initialDelaySeconds: 5
  periodSeconds: 10

readinessProbe:
  httpGet:
    path: /ready
    port: 8080
  initialDelaySeconds: 10
  periodSeconds: 5
```
</details>

### Q5：如何设计 K8s 集群的高可用架构？

<details>
<summary>点击查看参考答案</summary>

**控制平面高可用**:
1. **API Server**: 3-5 个副本，前面放 LB (HAProxy/Nginx)
2. **etcd**: 奇数个节点 (3/5/7)，跨可用区部署
3. **Scheduler + Controller Manager**: `--leader-elect=true`，只有一个 active

**Worker 高可用**:
1. **节点**: 至少 3 个节点，分布在不同 AZ
2. **Pod 分布**: 使用 Pod Topology Spread 分散到不同节点
3. **PDB (Pod Disruption Budget)**: 确保最小副本数

**网络高可用**:
1. **CNI**: 多副本部署 (Calico/Cilium DaemonSet)
2. **Service**: 使用 IPVS 或 eBPF 模式
3. **Ingress**: 多副本 + HPA + LoadBalancer

**备份策略**:
1. etcd 定期快照 + 异地存储
2. CRD 定义版本控制
3. 配置备份 (ConfigMap/Secret)

**灾难恢复**:
1. etcd snapshot 恢复
2. kubeconfig 重新生成
3. CNI 重新安装
</details>

---

## 第六部分：动手验证

### 6.1 本地搭建 K8s 集群（minikube）

```bash
# 1. 安装 minikube (macOS)
brew install minikube
brew install kubectl

# 2. 启动集群
minikube start --driver=docker --cpus=4 --memory=8192 --disk-size=50g

# 3. 验证
kubectl cluster-info
kubectl get nodes
kubectl get pods -A

# 4. 部署测试
kubectl create deployment hello-minikube --image=k8s.gcr.io/echoserver:1.4
kubectl expose deployment hello-minikube --type=NodePort --port=8080
minikube service hello-minikube

# 5. 清理
minikube delete
```

### 6.2 验证 Pod 调度行为

```bash
# 1. 创建带资源限制的 Deployment
kubectl create deployment test-resource --image=nginx:alpine --replicas=3

# 2. 设置资源请求
kubectl set resources deployment test-resource \
  --requests=cpu=100m,memory=128Mi \
  --limits=cpu=500m,memory=256Mi

# 3. 观察调度
kubectl get pods -o wide -w  # 实时观察调度结果

# 4. 查看调度事件
kubectl get events --sort-by='.lastTimestamp'

# 5. 模拟节点压力 (驱逐测试)
kubectl cordon <node-name>  # 标记节点不可调度
kubectl drain <node-name> --ignore-daemonsets --delete-emptydir-data  # 驱逐 Pod
kubectl uncordon <node-name>  # 重新可用
```

### 6.3 验证 Service 网络

```bash
# 1. 创建测试 Service
kubectl create deployment nginx-test --image=nginx:alpine --replicas=2
kubectl expose deployment nginx-test --port=80 --target-port=80

# 2. 测试 Service 访问
kubectl run -it --rm debug --image=busybox --restart=Never -- \
  wget -qO- --timeout=5 http://nginx-test

# 3. 查看 Endpoint
kubectl get endpoints nginx-test
kubectl describe service nginx-test

# 4. 模拟 Pod 故障，验证 readiness probe
kubectl exec -it <pod-name> -- sh -c "kill -9 $(cat /tmp/pid)"
# 观察: 从 Service 中自动移除
```

---

*本文档基于 Kubernetes v1.29+ 源码整理，涵盖控制平面、Node 代理、网络、存储、调度全链路。建议配合 `kubeadm` 实际部署体验。*
