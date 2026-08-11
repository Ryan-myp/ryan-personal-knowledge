# Kubernetes 生产环境深度实战

> 深入 K8s 生产实践：集群设计、调度策略、网络插件、存储方案、监控告警。
> 包含真实生产环境问题和解决方案。
> 适用对象：DevOps 工程师、SRE、后端架构师

---

## 1. 集群架构设计

### 1.1 高可用架构

```
┌─────────────────────────────────────────────────────────────┐
│                  K8s 高可用架构                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Master 节点（控制面）                                        │
│  ├── API Server（多副本）                                    │
│  ├── etcd（多副本，Raft 协议）                               │
│  ├── Controller Manager（单副本，Leader Election）           │
│  └── Scheduler（多副本，Leader Election）                    │
│                                                             │
│  Worker 节点（数据面）                                        │
│  ├── kubelet                                               │
│  ├── kube-proxy                                            │
│  └── Container Runtime（containerd/Docker）                 │
│                                                             │
│  网络插件                                                    │
│  ├── Calico（BGP + iptables）                              │
│  ├── Flannel（VXLAN）                                      │
│  ├── Cilium（eBPF）                                        │
│  └── CoreDNS                                               │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 集群规模规划

```
集群规模参考：

┌─────────────────────────────────────────────────────────────┐
│  规模        │ 节点数      │ etcd 节点  │ 推荐方案            │
├─────────────────────────────────────────────────────────────┤
│  小型        │ 10-50       │ 3          │ 单 Master + 高可用   │
│  中型        │ 50-200      │ 3-5        │ 多 Master + 高可用   │
│  大型        │ 200-1000    │ 5          │ 独立 etcd 集群       │
│  超大型      │ 1000+       │ 5-7        │ 多集群联邦           │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. 调度策略

### 2.1 调度原理

```
调度流程：

1. 预选（Predicate）
   ├── 节点资源充足
   ├── 亲和性规则
   ├── 反亲和性规则
   └── 拓扑约束

2. 优选（Priority）
   ├── 资源均衡
   ├── 节点亲和
   ├── 容忍度
   └── 自定义优先级

3. 绑定
   └── 将 Pod 绑定到选定的节点
```

### 2.2 Go 实现调度器

```go
// scheduler.go

package scheduler

import (
    "sort"
)

type Node struct {
    Name        string
    Capacity    Resource
    Allocatable Resource
    Labels      map[string]string
    Taints      []Taint
}

type Pod struct {
    Name      string
    Requests  Resource
    Affinity  *Affinity
    Tolerations []Toleration
}

type Scheduler struct {
    nodes []*Node
}

func (s *Scheduler) Schedule(pod *Pod) (string, error) {
    // 1. 预选
    var candidates []*Node
    for _, node := range s.nodes {
        if s.fits(node, pod) {
            candidates = append(candidates, node)
        }
    }
    
    if len(candidates) == 0 {
        return "", ErrNoNodeFound
    }
    
    // 2. 优选
    sort.Slice(candidates, func(i, j int) bool {
        return s.score(candidates[i], pod) > s.score(candidates[j], pod)
    })
    
    return candidates[0].Name, nil
}

func (s *Scheduler) fits(node *Node, pod *Pod) bool {
    // 检查资源是否充足
    if !node.HasEnoughResource(pod.Requests) {
        return false
    }
    
    // 检查亲和性
    if !s.matchesAffinity(node, pod) {
        return false
    }
    
    // 检查容忍度
    if !s.toleratesTaints(node, pod) {
        return false
    }
    
    return true
}
```

---

## 3. 网络插件

### 3.1 Calico 架构

```
Calico 架构：

┌─────────────────────────────────────────────────────────────┐
│                    Calico 组件                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  etcd                                                        │
│  ├── 存储网络策略                                            │
│  └── 存储 BGP 路由信息                                       │
│                                                             │
│  calico-node                                                 │
│  ├── BGP 客户端                                              │
│  ├── iptables/IPTABLES 规则                                  │
│  └── Felix：端点管理                                        │
│                                                             │
│  kube-controllers                                            │
│  ├── 节点控制器                                              │
│  ├── 策略控制器                                              │
│  └── 工作负载控制器                                          │
│                                                             │
│  CNI 插件                                                     │
│  └── 负责 Pod 网络配置                                       │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 Cilium + eBPF

```
Cilium eBPF 优势：

1. 性能
   ├── 内核态网络栈
   └── 零拷贝传输

2. 可观测性
   ├── L7 可视化
   └── 流量追踪

3. 安全性
   ├── 内核态网络策略
   └── 身份感知安全

4. 兼容性
   ├── 支持多种 CNI
   └── 支持 Kubernetes Network Policy
```

---

## 4. 存储方案

### 4.1 存储类型

```
K8s 存储类型：

1. PersistentVolume (PV)
   ├── 集群级存储资源
   └── 静态/动态 provision

2. PersistentVolumeClaim (PVC)
   ├── 用户存储请求
   └── 绑定到 PV

3. StorageClass
   ├── 动态 provision 模板
   └── 存储类型定义
```

### 4.2 存储驱动对比

```
┌─────────────────────────────────────────────────────────────┐
│                  存储驱动对比                                │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  驱动              │ 类型     │ 性能   │ 适用场景              │
├─────────────────────────────────────────────────────────────┤
│  NFS               │ 网络存储  │ 中     │ 共享存储              │
│  Ceph RBD          │ 块存储   │ 高     │ 高性能数据库           │
│  GlusterFS         │ 文件存储  │ 中     │ 文件共享              │
│  Local             │ 本地存储  │ 最高   │ 性能敏感应用           │
│  AWS EBS           │ 云存储   │ 高     │ AWS 环境              │
│  Google PD         │ 云存储   │ 高     │ GCP 环境              │
│  Azure Disk        │ 云存储   │ 高     │ Azure 环境            │
└─────────────────────────────────────────────────────────────┘
```

---

## 5. 监控告警

### 5.1 监控栈

```
K8s 监控栈：

┌─────────────────────────────────────────────────────────────┐
│                    监控组件                                  │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Metrics Server                                             │
│  └── 集群资源指标（CPU、内存）                               │
│                                                             │
│  Prometheus                                                  │
│  ├── 指标采集                                               │
│  ├── 存储                                                  │
│  └── 查询                                                   │
│                                                             │
│  Grafana                                                     │
│  ├── 可视化                                                 │
│  └── 告警                                                   │
│                                                             │
│  Alertmanager                                                │
│  ├── 告警路由                                               │
│  ├── 去重                                                  │
│  └── 通知                                                   │
│                                                             │
│  kube-state-metrics                                          │
│  └── K8s 对象状态指标                                       │
│                                                             │
│  node-exporter                                               │
│  └── 节点资源指标                                           │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 5.2 Go 实现监控采集

```go
// monitor.go

package monitor

import (
    "github.com/prometheus/client_golang/prometheus"
    "k8s.io/client-go/kubernetes"
)

type K8sMonitor struct {
    client        *kubernetes.Clientset
    podCount      *prometheus.GaugeVec
    containerCount *prometheus.GaugeVec
}

func NewK8sMonitor(client *kubernetes.Clientset) *K8sMonitor {
    return &K8sMonitor{
        client: client,
        podCount: prometheus.NewGaugeVec(
            prometheus.GaugeOpts{
                Name: "k8s_pods",
                Help: "Pod count by status",
            },
            []string{"status"},
        ),
        containerCount: prometheus.NewGaugeVec(
            prometheus.GaugeOpts{
                Name: "k8s_containers",
                Help: "Container count by status",
            },
            []string{"status"},
        ),
    }
}

func (m *K8sMonitor) Register() {
    prometheus.MustRegister(m.podCount)
    prometheus.MustRegister(m.containerCount)
}

func (m *K8sMonitor) Collect() {
    pods, _ := m.client.CoreV1().Pods("").List(context.TODO(), metav1.ListOptions{})
    for _, pod := range pods.Items {
        m.podCount.WithLabelValues(string(pod.Status.Phase)).Inc()
    }
}
```

---

## 6. 故障排查

### 6.1 常见问题

| 问题 | 症状 | 排查命令 | 解决方案 |
|------|------|----------|----------|
| Pod 启动失败 | ContainerCreating | `kubectl describe pod` | 检查资源配置 |
| 网络不通 | DNS 解析失败 | `kubectl exec -it` | 检查 CNI 插件 |
| 调度失败 | ContainerCreating | `kubectl get nodes` | 检查节点资源 |
| 存储挂载失败 | FailedMount | `kubectl describe pvc` | 检查 StorageClass |
| 节点 NotReady | Ready=False | `kubectl describe node` | 检查 kubelet |

### 6.2 调试命令

```bash
# 查看 Pod 状态
kubectl get pods -n <namespace>

# 查看 Pod 详情
kubectl describe pod <pod-name> -n <namespace>

# 查看 Pod 日志
kubectl logs <pod-name> -n <namespace>

# 进入 Pod 执行命令
kubectl exec -it <pod-name> -n <namespace> -- /bin/sh

# 查看事件
kubectl get events -n <namespace>

# 查看节点状态
kubectl get nodes -o wide

# 查看调度信息
kubectl describe node <node-name>
```

---

## 7. 安全最佳实践

### 7.1 RBAC 配置

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: app-reader
rules:
- apiGroups: [""]
  resources: ["pods", "services"]
  verbs: ["get", "list", "watch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: app-reader-binding
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: app-reader
subjects:
- kind: ServiceAccount
  name: app-service-account
  namespace: default
```

### 7.2 Network Policy

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: deny-all
  namespace: production
spec:
  podSelector: {}
  policyTypes:
  - Ingress
  - Egress
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-frontend
  namespace: production
spec:
  podSelector:
    matchLabels:
      app: frontend
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app: backend
```

---

## 8. 总结

### 8.1 核心原理回顾

| 模块 | 核心机制 |
|------|----------|
| 调度 | 预选 + 优选 |
| 网络 | CNI 插件 |
| 存储 | PV + PVC + SC |
| 监控 | Prometheus + Grafana |
| 安全 | RBAC + NetworkPolicy |

### 8.2 最佳实践

- [ ] 高可用架构设计
- [ ] 合理调度策略
- [ ] 完善监控告警
- [ ] 网络安全隔离
- [ ] 定期故障演练

---

*最后更新：2026-08-11*
*作者：Ryan*
