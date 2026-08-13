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
│  Control Plane（控制平面）                                    │
│  ├── API Server (高可用部署)                                 │
│  ├── etcd (集群模式)                                        │
│  ├── Controller Manager (leader election)                  │
│  ├── Scheduler (多副本)                                     │
│  └── Cloud Controller Manager                              │
│                                                             │
│  Worker Node（工作节点）                                      │
│  ├── kubelet                                              │
│  ├── kube-proxy                                           │
│  └── Container Runtime (containerd/Docker)                 │
│                                                             │
│  网络插件 (CNI)                                             │
│  ├── Calico (BGP + IPIP)                                  │
│  ├── Flannel (VXLAN)                                      │
│  └── Cilium (eBPF)                                        │
│                                                             │
│  存储插件 (CSI)                                             │
│  ├── NFS, Ceph, GlusterFS                                 │
│  └── 云厂商存储 (EBS, PVC)                                 │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 节点规划

```
节点类型：

1. Master 节点（控制平面）
   ├── CPU: 4+ 核
   ├── 内存: 8GB+
   └── 磁盘: SSD 推荐

2. Worker 节点（工作负载）
   ├── CPU: 8+ 核
   ├── 内存: 32GB+
   └── 根据负载调整

3. 专用节点
   ├── 数据库节点（高性能磁盘）
   ├── GPU 节点（AI 训练）
   └── 边缘节点（资源受限）
```

---

## 2. 调度策略

### 2.1 调度器工作原理

```
调度流程：

1. 调度队列
   ├── 抢占队列
   └── 普通队列

2. 过滤阶段 (Predicate)
   ├── 资源充足
   ├── 节点选择器
   ├── 亲和性/反亲和性
   └── 污点容忍

3. 打分阶段 (Priority)
   ├── 资源均衡
   ├── 节点亲和
   └── 拓扑分布

4. 绑定阶段
   └── 将 Pod 绑定到节点
```

### 2.2 Go 实现调度器

```go
// scheduler.go

package scheduler

import (
    "context"
    "sort"
)

type Scheduler struct {
    nodeLister *NodeLister
    podLister  *PodLister
}

func (s *Scheduler) Schedule(pod *v1.Pod) (string, error) {
    // 1. 获取候选节点
    nodes, err := s.filterNodes(pod)
    if err != nil {
        return "", err
    }
    
    // 2. 打分排序
    scoreMap := s.scoreNodes(pod, nodes)
    sort.Slice(nodes, func(i, j int) bool {
        return scoreMap[nodes[i].Name] > scoreMap[nodes[j].Name]
    })
    
    // 3. 绑定
    return nodes[0].Name, s.bind(pod, nodes[0].Name)
}

func (s *Scheduler) filterNodes(pod *v1.Pod) ([]*v1.Node, error) {
    // 过滤不可用节点
    // 过滤资源不足节点
    // 应用节点选择器
    // ...
}
```

---

## 3. 网络插件

### 3.1 Calico 架构

```
Calico 架构：

┌─────────────────────────────────────────────────────────────┐
│                  Calico 网络架构                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  BGP 路由器 (BGP Router)                                    │
│  ├── 与物理网络路由器建立 BGP 会话                          │
│  └── 宣告 Pod 网段                                          │
│                                                             │
│  路由表 (Route Table)                                       │
│  ├── IPIP 隧道                                             │
│  ├── BGP 路由                                              │
│  └── 主机路由                                              │
│                                                             │
│  Felix (节点代理)                                           │
│  ├── 管理 iptables 规则                                    │
│  ├── 更新 BGP 路由                                         │
│  └── 监控节点状态                                          │
│                                                             │
│  Bird (BGP 路由器)                                          │
│  └── 处理 BGP 协议                                         │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 Cilium + eBPF

```
Cilium eBPF 架构：

1. 数据平面
   ├── kprobe/uprobe
   ├── XDP (eXpress Data Path)
   └── tc (traffic control)

2. 关键组件
   ├── hubble (可观测性)
   ├── operators (Operator 控制器)
   └── node init (节点初始化)

3. 优势
   ├── 高性能网络
   ├── 原生 k8s 集成
   └── 安全策略可视化
```

---

## 4. 存储方案

### 4.1 CSI 架构

```
CSI (Container Storage Interface) 架构：

┌─────────────────────────────────────────────────────────────┐
│                    CSI 组件                                 │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  控制器侧 (Controller)                                      │
│  ├── CSI Controller Server                                  │
│  ├── Volume 创建/删除                                       │
│  └── 快照管理                                               │
│                                                             │
│  节点侧 (Node)                                              │
│  ├── CSI Node Server                                        │
│  ├── 挂载/卸载卷                                            │
│  └── 卷扩展                                                 │
│                                                             │
│  插件类型                                                    │
│  ├── 独立插件 (Sidecar)                                     │
│  ├── CSI Proxy (Windows)                                   │
│  └── 直接集成                                                │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 存储类配置

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: fast-ssd
provisioner: pd.csi.storage.gke.io
parameters:
  type: pd-ssd
  fstype: ext4
reclaimPolicy: Retain
volumeBindingMode: WaitForFirstConsumer
```

---

## 5. 监控告警

### 5.1 Prometheus 架构

```
Prometheus 监控架构：

┌─────────────────────────────────────────────────────────────┐
│                  监控架构                                    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Prometheus Server                                            │
│  ├── 数据采集 (Scrape)                                       │
│  ├── 时间序列存储                                            │
│  └── 查询引擎                                                │
│                                                             │
│  Exporter                                                    │
│  ├── Node Exporter (主机指标)                                │
│  ├── cAdvisor (容器指标)                                     │
│  └── Kube State Metrics (K8s 资源指标)                      │
│                                                             │
│  Grafana (可视化)                                            │
│  └── Dashboard 展示                                          │
│                                                             │
│  AlertManager (告警)                                         │
│  ├── 告警规则                                               │
│  └── 通知路由                                               │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 5.2 关键监控指标

```
K8s 监控指标：

1. 集群健康
   ├── 节点状态
   ├── Pod 重启次数
   └── API Server 延迟

2. 资源使用
   ├── CPU/内存使用率
   ├── 磁盘使用
   └── 网络带宽

3. 工作负载
   ├── 部署副本数
   ├── 服务端点
   └── Ingress 请求数
```

---

## 6. 故障排查

### 6.1 常见问题

| 问题 | 症状 | 排查命令 | 解决方案 |
|------|------|----------|----------|
| Pod 启动失败 | ContainerCreating | `kubectl describe pod` | 检查镜像/资源 |
| 网络不通 | Connection timeout | `kubectl exec` 调试 | 检查 CNI/策略 |
| 调度失败 | Pending | `kubectl get events` | 检查资源/亲和性 |
| 存储挂载失败 | MountVolume failed | `kubectl describe pod` | 检查 PVC/SC |

### 6.2 调试工具

```bash
# 查看 Pod 详情
kubectl describe pod <pod-name> -n <namespace>

# 查看事件
kubectl get events -n <namespace> --sort-by='.lastTimestamp'

# 进入容器调试
kubectl exec -it <pod-name> -- /bin/sh

# 日志查看
kubectl logs <pod-name> -f

# 端口转发
kubectl port-forward <pod-name> 8080:80
```

---

## 7. 生产最佳实践

### 7.1 资源管理

```yaml
# 资源限制
resources:
  requests:
    cpu: "500m"
    memory: "256Mi"
  limits:
    cpu: "1000m"
    memory: "512Mi"

# QoS 级别
# Guaranteed: requests == limits
# Burstable: requests < limits
# BestEffort: 无 requests/limits
```

### 7.2 安全配置

```yaml
# Pod 安全策略
securityContext:
  runAsNonRoot: true
  readOnlyRootFilesystem: true
  allowPrivilegeEscalation: false
  
# 网络策略
networkPolicy:
  ingress:
    - from:
        - podSelector:
            matchLabels:
              role: frontend
```

---

## 8. 总结

### 8.1 核心原理回顾

| 模块 | 核心机制 |
|------|----------|
| 调度 | 过滤+打分+绑定 |
| 网络 | CNI 插件 (Calico/Cilium) |
| 存储 | CSI 接口 |
| 监控 | Prometheus 生态 |
| 安全 | Pod 安全策略 |

### 8.2 最佳实践

- [ ] 合理规划节点资源
- [ ] 配置资源限制
- [ ] 实施网络策略
- [ ] 建立监控告警
- [ ] 定期备份 etcd

---

*最后更新：2026-08-11*
*作者：Ryan*
