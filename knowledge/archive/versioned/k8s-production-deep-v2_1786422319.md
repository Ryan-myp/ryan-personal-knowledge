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
│  Control Plane (至少 3 节点)                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │  API Server │  │  API Server │  │  API Server │        │
│  │   (Node 1)  │  │   (Node 2)  │  │   (Node 3)  │        │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘        │
│         └─────────────────┼─────────────────┘              │
│                           │                                │
│                    ┌──────▼──────┐                         │
│                    │  etcd 集群   │                         │
│                    │ (3/5 节点)   │                         │
│                    └─────────────┘                         │
│                                                             │
│  Worker Nodes (按需扩展)                                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                 │
│  │ Node 1   │  │ Node 2   │  │ Node 3   │                 │
│  │ kubelet  │  │ kubelet  │  │ kubelet  │                 │
│  │ kube-proxy│  │ kube-proxy│  │ kube-proxy│                │
│  └──────────┘  └──────────┘  └──────────┘                 │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 节点规划

```yaml
# 控制平面节点
node-role.kubernetes.io/control-plane: ""
resources:
  CPU: 4 cores
  Memory: 8 GB
  Disk: 100 GB SSD

# Worker 节点 - 通用
node-role.kubernetes.io/worker: ""
resources:
  CPU: 16 cores
  Memory: 32 GB
  Disk: 500 GB SSD

# Worker 节点 - 计算密集
node-role.kubernetes.io/compute: ""
resources:
  CPU: 32 cores
  Memory: 64 GB
  Disk: 1 TB NVMe
```

---

## 2. 调度策略

### 2.1 亲和性调度

```yaml
# pod-affinity.yaml

apiVersion: v1
kind: Pod
metadata:
  name: api-server
spec:
  affinity:
    # 节点亲和性
    nodeAffinity:
      requiredDuringSchedulingIgnoredDuringExecution:
        nodeSelectorTerms:
        - matchExpressions:
          - key: node-role.kubernetes.io/worker
            operator: Exists
    
    # Pod 亲和性
    podAffinity:
      preferredDuringSchedulingIgnoredDuringExecution:
      - weight: 100
        podAffinityTerm:
          labelSelector:
            matchExpressions:
            - key: app
              operator: In
              values:
              - redis
          topologyKey: kubernetes.io/hostname
    
    # Pod 反亲和性
    podAntiAffinity:
      requiredDuringSchedulingIgnoredDuringExecution:
      - labelSelector:
          matchExpressions:
          - key: app
            operator: In
            values:
            - api-server
        topologyKey: kubernetes.io/hostname
  containers:
  - name: api
    image: api-server:v1.0
```

### 2.2 Taints 与 Toleration

```yaml
# taint-example.yaml

apiVersion: v1
kind: Pod
metadata:
  name: gpu-pod
spec:
  tolerations:
  - key: "gpu"
    operator: "Equal"
    value: "true"
    effect: "NoSchedule"
  - key: "dedicated"
    operator: "Equal"
    value: "ml-workload"
    effect: "NoExecute"
  containers:
  - name: gpu-app
    image: gpu-app:v1.0
```

---

## 3. 网络插件

### 3.1 CNI 架构

```
┌─────────────────────────────────────────────────────────────┐
│                    CNI 网络架构                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Pod Network                                                  │
│  ┌─────────┐    ┌─────────┐    ┌─────────┐                │
│  │ Pod 1   │    │ Pod 2   │    │ Pod 3   │                │
│  │ eth0    │    │ eth0    │    │ eth0    │                │
│  └────┬────┘    └────┬────┘    └────┬────┘                │
│       │              │              │                       │
│  ┌────▼────┐    ┌────▼────┐    ┌────▼────┐                │
│  │ veth pair│    │ veth pair│    │ veth pair│               │
│  └────┬────┘    └────┬────┘    └────┬────┘                │
│       └──────────────┼──────────────┘                      │
│                      ▼                                      │
│              ┌───────────────┐                              │
│              │   CNI Bridge   │                              │
│              │  (cni0/flannel)│                              │
│              └───────┬───────┘                              │
│                      │                                      │
│              ┌───────▼───────┐                              │
│              │  Host Network  │                              │
│              └───────────────┘                              │
│                                                             │
│  主流 CNI 插件：                                              │
│  ├── Flannel: 简单，Overlay                                 │
│  ├── Calico: BGP，高性能                                    │
│  ├── Cilium: eBPF，可观测性                                 │
│  └── Containernet: 大规模部署                               │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 Calico 配置

```yaml
# calico-config.yaml

apiVersion: v1
kind: ConfigMap
metadata:
  name: calico-config
  namespace: kube-system
data:
  # BGP 配置
  calico_backend: "bird"
  
  # MTU 配置
  veth_mtu: "1440"
  
  # 路由聚合
  ipip_enabled: "false"
  
  # eBPF 模式（高性能）
  bpf_kube_proxy: "true"
  bpf_data_iface: "eth0"
```

---

## 4. 存储方案

### 4.1 StorageClass

```yaml
# storage-class.yaml

apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: ssd-fast
provisioner: csi.trident.netapp.io
parameters:
  backendType: "ontap_nas"
  storagePool: "fast-spo"
reclaimPolicy: Delete
volumeBindingMode: Immediate

---

apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: hdd-archive
provisioner: csi.trident.netapp.io
parameters:
  backendType: "ontap_nas"
  storagePool: "archive-pool"
reclaimPolicy: Retain
volumeBindingMode: WaitForFirstConsumer
```

### 4.2 PV/PVC 示例

```yaml
# persistent-volume.yaml

apiVersion: v1
kind: PersistentVolume
metadata:
  name: redis-data
spec:
  capacity:
    storage: 100Gi
  accessModes:
    - ReadWriteOnce
  persistentVolumeReclaimPolicy: Retain
  storageClassName: ssd-fast
  csi:
    driver: csi.trident.netapp.io
    volumeHandle: redis-volume-001

---

apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: redis-data-pvc
  namespace: default
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: ssd-fast
  resources:
    requests:
      storage: 100Gi
```

---

## 5. 监控告警

### 5.1 Prometheus 架构

```
┌─────────────────────────────────────────────────────────────┐
│                  Prometheus 监控架构                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │  Prometheus │◄──►│   Alertman. │◄──►│    PagerDuty│     │
│  │   Server    │    │     er      │    │   /Opsgenie │     │
│  └──────┬──────┘    └─────────────┘    └─────────────┘     │
│         │                                                   │
│    ┌────┴────┐                                             │
│    │  Pull   │                                             │
│    └────┬────┘                                             │
│         │                                                   │
│  ┌──────▼──────┐    ┌───────┐    ┌───────┐                │
│  │ Kube State  │    │Node   │    │  App  │                │
│  │  Metrics    │    │Export.│    │ Export.│                │
│  └─────────────┘    └───────┘    └───────┘                │
│                                                             │
│  Grafana Dashboard:                                          │
│  ├── 集群概览                                               │
│  ├── 节点资源                                               │
│  ├──  Pod 状态                                              │
│  └── 应用指标                                               │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 5.2 告警规则

```yaml
# alert-rules.yaml

groups:
- name: kubernetes
  rules:
  - alert: NodeNotReady
    expr: kube_node_status_condition{condition="Ready",status="true"} == 0
    for: 5m
    labels:
      severity: critical
    annotations:
      summary: "节点 {{ $labels.node }} 不可用"
      description: "节点已不可用超过 5 分钟"

  - alert: PodCrashLooping
    expr: kube_pod_container_status_restarts_total > 3
    for: 10m
    labels:
      severity: warning
    annotations:
      summary: "Pod {{ $labels.pod }} 频繁重启"

  - alert: HighCPUUsage
    expr: container_cpu_usage_seconds_total / kube_pod_container_resource_limits_cpu > 0.8
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "容器 CPU 使用率过高"
```

---

## 6. 生产最佳实践

### 6.1 资源限制

```yaml
# resource-limits.yaml

apiVersion: v1
kind: Pod
metadata:
  name: web-app
spec:
  containers:
  - name: web
    image: web-app:v1.0
    resources:
      requests:
        cpu: "250m"
        memory: "256Mi"
      limits:
        cpu: "500m"
        memory: "512Mi"
    livenessProbe:
      httpGet:
        path: /healthz
        port: 8080
      initialDelaySeconds: 10
      periodSeconds: 5
    readinessProbe:
      httpGet:
        path: /ready
        port: 8080
      initialDelaySeconds: 5
      periodSeconds: 3
```

### 6.2 滚动更新

```yaml
# deployment-strategy.yaml

apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-server
spec:
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 25%
      maxUnavailable: 25%
  minReadySeconds: 30
  revisionHistoryLimit: 5
  progressDeadlineSeconds: 120
```

---

## 7. 故障排查

### 7.1 常见问题

| 问题 | 症状 | 排查命令 | 解决方案 |
|------|------|----------|----------|
| Pod CrashLoopBackOff | 容器反复重启 | `kubectl logs` | 检查日志、资源限制 |
| ImagePullBackOff | 镜像拉取失败 | `kubectl describe pod` | 检查镜像地址、secret |
| ContainerCreating | 长时间创建 | `kubectl describe pod` | 检查调度、存储 |
| NodeNotReady | 节点不可用 | `kubectl get nodes` | 检查 kubelet、网络 |

### 7.2 调试命令

```bash
# 查看 Pod 详情
kubectl describe pod <pod-name> -n <namespace>

# 查看 Pod 日志
kubectl logs <pod-name> -n <namespace>
kubectl logs -f <pod-name> -n <namespace>

# 进入 Pod 执行命令
kubectl exec -it <pod-name> -n <namespace> -- /bin/sh

# 查看事件
kubectl get events -n <namespace> --sort-by='.lastTimestamp'

# 资源使用情况
kubectl top pod -n <namespace>
kubectl top node
```

---

## 8. 总结

### 8.1 核心原理回顾

| 模块 | 核心技术 |
|------|----------|
| 调度 | 亲和性/Taint/Tolerations |
| 网络 | CNI/Calico/Cilium |
| 存储 | PV/PVC/StorageClass |
| 监控 | Prometheus/Grafana |
| 发布 | RollingUpdate/Canary |

### 8.2 最佳实践

- [ ] 控制平面高可用部署
- [ ] 合理设置资源限制
- [ ] 配置健康检查
- [ ] 建立监控告警体系
- [ ] 定期备份 etcd

---

*最后更新：2026-08-11*
*作者：Ryan*
