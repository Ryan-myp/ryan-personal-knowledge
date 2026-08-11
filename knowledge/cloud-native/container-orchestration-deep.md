# 容器编排深度解析

> 深入容器编排：Kubernetes、Docker Swarm、容器网络、存储。
> 源码级分析，包含生产环境实践。
> 适用对象：DevOps工程师、SRE

---

## 1. Kubernetes 架构

### 1.1 核心组件

```
Kubernetes 核心组件：

├── Master Node
│   ├── API Server
│   ├── Controller Manager
│   ├── Scheduler
│   └── etcd
│
├── Worker Node
│   ├── Kubelet
│   ├── Kube-proxy
│   └── Container Runtime
│
└── 网络插件
    ├── Calico
    ├── Flannel
    └── Cilium
```

### 1.2 Go 实现 K8s 核心

```go
// k8s_core.go

package kubernetes

import (
    "context"
    "sync"
)

type APIServer struct {
    etcd     *ETCD
    registry *Registry
    mu       sync.Mutex
}

type Registry struct {
    pods       map[string]*Pod
    services   map[string]*Service
    deployments map[string]*Deployment
}

type Pod struct {
    Name      string
    Namespace string
    Spec      PodSpec
    Status    PodStatus
}

type PodSpec struct {
    Containers []Container
    Volumes    []Volume
}

type Container struct {
    Name      string
    Image     string
    Ports     []Port
    Resources ResourceRequirements
}

type Service struct {
    Name      string
    Namespace string
    Spec      ServiceSpec
    Status    ServiceStatus
}

type ServiceSpec struct {
    Type        string
    Ports       []ServicePort
    Selector    map[string]string
}

func NewAPIServer(etcd *ETCD) *APIServer {
    return &APIServer{
        etcd:     etcd,
        registry: &Registry{
            pods:       make(map[string]*Pod),
            services:   make(map[string]*Service),
            deployments: make(map[string]*Deployment),
        },
    }
}

func (api *APIServer) CreatePod(ctx context.Context, pod *Pod) error {
    api.mu.Lock()
    defer api.mu.Unlock()
    
    pod.Status.Phase = "Pending"
    api.registry.pods[pod.Name] = pod
    
    return api.etcd.Store(ctx, "/pods/"+pod.Name, pod)
}

func (api *APIServer) GetPod(name string) (*Pod, error) {
    api.mu.RLock()
    defer api.mu.RUnlock()
    
    return api.registry.pods[name], nil
}
```

---

## 2. 容器网络

### 2.1 CNI 插件

```
CNI (Container Network Interface):

├── 插件类型
│   ├── bridge
│   ├── host-device
│   ├── loopback
│   └── vlan
│
└── 接口规范
    ├── ADD: 添加网络
    ├── DEL: 删除网络
    └── CHECK: 检查网络
```

### 2.2 Go 实现 CNI

```go
// cni.go

package kubernetes

import (
    "net"
)

type CNIPlugin interface {
    Add(ctx context.Context, pod *Pod, netConf *NetworkConfig) error
    Delete(ctx context.Context, pod *Pod, netConf *NetworkConfig) error
    Check(ctx context.Context, pod *Pod, netConf *NetworkConfig) error
}

type BridgePlugin struct {
    bridgeName string
    ipam       IPAMPlugin
}

type IPAMPlugin interface {
    Allocate(addr string) (*net.IPNet, error)
    Release(addr string) error
}

func (bp *BridgePlugin) Add(ctx context.Context, pod *Pod, netConf *NetworkConfig) error {
    // 创建网桥
    // 分配IP
    // 配置网络
    return nil
}

func (bp *BridgePlugin) Delete(ctx context.Context, pod *Pod, netConf *NetworkConfig) error {
    // 清理网络配置
    return nil
}
```

---

## 3. 存储管理

### 3.1 PV/PVC

```
存储架构：

├── PV (PersistentVolume)
│   └── 集群存储资源

├── PVC (PersistentVolumeClaim)
│   └── 存储请求

├── StorageClass
│   └── 存储类

└── 动态供给
    └── 自动创建PV
```

### 3.2 Go 实现存储管理

```go
// storage.go

package kubernetes

import "sync"

type StorageManager struct {
    pvList   map[string]*PV
    pvcList  map[string]*PVC
    scList   map[string]*StorageClass
    mu       sync.Mutex
}

type PV struct {
    Name       string
    Spec       PVSpec
    Status     PVStatus
}

type PVSpec struct {
    Capacity    ResourceList
    AccessModes []AccessMode
    StorageClass string
}

type PVC struct {
    Name      string
    Namespace string
    Spec      PVCSpec
    Status    PVCStatus
}

type PVCSpec struct {
    Resources    ResourceRequirements
    StorageClass string
    VolumeName   string
}

func NewStorageManager() *StorageManager {
    return &StorageManager{
        pvList:  make(map[string]*PV),
        pvcList: make(map[string]*PVC),
        scList:  make(map[string]*StorageClass),
    }
}

func (sm *StorageManager) CreatePVC(pvc *PVC) error {
    sm.mu.Lock()
    defer sm.mu.Unlock()
    
    // 查找匹配的PV
    pv := sm.findMatchingPV(pvc)
    if pv == nil {
        return ErrNoAvailablePV
    }
    
    // 绑定
    pv.Status.ClaimRef = pvc.Name
    pvc.Spec.VolumeName = pv.Name
    pvc.Status.Phase = "Bound"
    
    return nil
}
```

---

## 4. 调度器

### 4.1 调度流程

```
调度流程：

1. 预选 (Predicate)
   └── 过滤不满足条件的节点

2. 优选 (Priority)
   └── 评分选择最佳节点

3. 绑定 (Bind)
   └── 将Pod绑定到节点
```

### 4.2 Go 实现调度器

```go
// scheduler.go

package kubernetes

import (
    "sort"
)

type Scheduler struct {
    nodeList []*Node
}

type Node struct {
    Name     string
    Capacity ResourceList
    Allocatable ResourceList
    Conditions []NodeCondition
}

type ResourceList map[string]ResourceQuantity

type ResourceQuantity struct {
    Value    int64
    Format string
}

func (s *Scheduler) Schedule(pod *Pod) (string, error) {
    // 1. 预选
    suitable := s.predicate(pod)
    
    // 2. 优选
    scored := s.priority(suitable, pod)
    
    // 3. 选择最佳节点
    if len(scored) == 0 {
        return "", ErrNoSuitableNode
    }
    
    best := scored[0]
    return best.Name, nil
}

func (s *Scheduler) predicate(pod *Pod) []*Node {
    var suitable []*Node
    for _, node := range s.nodeList {
        if s.fits(node, pod) {
            suitable = append(suitable, node)
        }
    }
    return suitable
}

func (s *Scheduler) fits(node *Node, pod *Pod) bool {
    // 检查资源是否足够
    return true
}
```

---

## 5. 总结

### 5.1 核心原理回顾

| 组件 | 作用 |
|------|------|
| API Server | 统一入口 |
| Scheduler | 节点调度 |
| Controller | 状态管理 |
| etcd | 数据存储 |

### 5.2 最佳实践

- [ ] 合理配置资源限制
- [ ] 使用健康检查
- [ ] 监控集群状态
- [ ] 定期备份etcd

---

*最后更新：2026-08-11*
*作者：Ryan*
