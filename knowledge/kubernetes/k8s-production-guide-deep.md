# Kubernetes 生产环境实战指南

> 深入 K8s 生产部署：调度策略、资源管理、网络模型、故障排查。
> 适用对象：运维工程师、SRE、后端开发

---

## 1. Pod 调度机制

### 1.1 调度流程

```
┌─────────────────────────────────────────────────────────────────┐
│                     K8s 调度流程                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. 调度器监听 API Server，获取 Pending Pod                     │
│  2. 首选阶段 (Predicate): 过滤不满足条件的 Node                 │
│     ├── 资源不足                                              │
│     ├── 节点选择器不匹配                                        │
│     ├── 亲和性/反亲和性不满足                                   │
│     └── 污点容忍                                              │
│  3. 优选阶段 (Priority): 选择最优 Node                          │
│     ├── 资源最饱和 / 最空闲                                      │
│     ├── 拓扑分布                                              │
│     └── 自定义 Score                                           │
│  4. 绑定: 将 Pod 绑定到选定 Node                                │
│  5. Kubelet 启动容器                                          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 资源限制

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: app
spec:
  containers:
  - name: app
    image: myapp
    resources:
      requests:
        cpu: "500m"      # 保证 0.5 核
        memory: "512Mi"  # 保证 512MB
      limits:
        cpu: "2000m"     # 最多 2 核
        memory: "2Gi"    # 最多 2GB
```

---

## 2. 网络模型

### 2.1 CNI 插件

```
┌─────────────────────────────────────────────────────────────────┐
│                     K8s 网络架构                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Pod Network (Flat Network)                                     │
│  ├── 每个 Pod 有唯一 IP                                          │
│  ├── Pod 间可直接通信                                            │
│  └── 常用插件: Calico, Flannel, Cilium                         │
│                                                                 │
│  Service 网络                                                   │
│  ├── ClusterIP: 集群内部访问                                      │
│  ├── NodePort: 节点端口暴露                                       │
│  ├── LoadBalancer: 云厂商 LB                                    │
│  └── ExternalIP: 外部 IP                                       │
│                                                                 │
│  DNS 服务                                                       │
│  ├── kube-dns / CoreDNS                                        │
│  ├── Service: my-svc.ns.svc.cluster.local                      │
│  └── Pod: pod-ip.ns.pod.cluster.local                          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. 存储系统

```yaml
# PersistentVolume (PV)
apiVersion: v1
kind: PersistentVolume
metadata:
  name: pv-nfs
spec:
  capacity:
    storage: 100Gi
  accessModes:
    - ReadWriteMany
  persistentVolumeReclaimPolicy: Retain
  nfs:
    server: nfs-server
    path: /exports

# PersistentVolumeClaim (PVC)
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: pvc-app
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 50Gi
  storageClassName: fast-ssd
```

---

## 4. 高可用配置

```yaml
# Deployment 高可用
apiVersion: apps/v1
kind: Deployment
metadata:
  name: app
spec:
  replicas: 3
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  affinity:
    podAntiAffinity:
      preferredDuringSchedulingIgnoredDuringExecution:
      - weight: 100
        podAffinityTerm:
          labelSelector:
            matchExpressions:
            - key: app
              operator: In
              values:
              - app
          topologyKey: kubernetes.io/hostname
```

---

## 5. 故障排查

```bash
# 查看 Pod 状态
kubectl describe pod <pod-name> -n <namespace>

# 查看事件
kubectl get events --sort-by='.lastTimestamp'

# 日志查看
kubectl logs <pod-name> -n <namespace>
kubectl logs -f <pod-name> -n <namespace>

# 进入容器调试
kubectl exec -it <pod-name> -n <namespace> -- /bin/sh

# 端口转发
kubectl port-forward <pod-name> 8080:80 -n <namespace>
```

---

## 6. 实践 Checklist

- [ ] 设置合理的 Resource Request/Limit
- [ ] 配置 Pod 反亲和性分散故障域
- [ ] 使用 PDB (PodDisruptionBudget) 保护滚动更新
- [ ] 配置 Liveness/Readiness Probe
- [ ] 开启 Audit Log
- [ ] 备份 etcd

---

**参考**: K8s 官方文档、Kelsey Hightower Kubernetes Handbook、CNCF 最佳实践
