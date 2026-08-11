# Kubernetes 生产环境深度实战

> 深入 K8s 生产实践：集群设计、调度优化、网络插件、存储方案、故障排查。
> 基于阿里云 ACK / 自建集群实战经验。
> 适用对象：SRE、DevOps 工程师、K8s 架构师

---

## 1. 集群架构设计

### 1.1 生产集群拓扑

```
┌─────────────────────────────────────────────────────────────────────┐
│                      K8s 生产集群架构                                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    API Server (高可用)                        │   │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐                     │   │
│  │  │ API 1   │  │ API 2   │  │ API 3   │  (3 Master 节点)     │   │
│  │  └────┬────┘  └────┬────┘  └────┬────┘                     │   │
│  │       └─────────────┼─────────────┘                          │   │
│  │                     ▼                                         │   │
│  │              etcd 集群 (3/5 节点)                              │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                           │                                         │
│         ┌─────────────────┼─────────────────┐                       │
│         ▼                 ▼                 ▼                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │ Worker 节点  │  │ Worker 节点  │  │ Worker 节点  │              │
│  │  (计算节点)   │  │  (计算节点)   │  │  (计算节点)   │              │
│  │  Pod 运行     │  │ Pod 运行     │  │ Pod 运行     │              │
│  └──────────────┘  └──────────────┘  └──────────────┘              │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    基础设施层                                 │   │
│  │  网络: Calico / Flannel / Cilium                            │   │
│  │  存储: Ceph / NFS / 云盘                                   │   │
│  │  监控: Prometheus + Grafana                                  │   │
│  │  日志: Fluentd + Elasticsearch                               │   │
│  │  网关: Ingress Controller (Nginx/Traefik)                   │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.2 Master 节点规划

```yaml
# master 节点配置
apiVersion: v1
kind: ConfigMap
metadata:
  name: kubeadm-config
  namespace: kube-system
data:
  ClusterConfiguration:
    kubernetesVersion: v1.28.0
    controlPlaneEndpoint: "k8s-api.example.com:6443"
    apiServer:
      certSANs:
        - "k8s-api.example.com"
        - "192.168.1.100"
      extraArgs:
        audit-log-path: /var/log/kubernetes/audit.log
        audit-policy-file: /etc/kubernetes/audit-policy.yaml
    controllerManager:
      extraArgs:
        node-cidr-mask-size: "24"
    networking:
      podSubnet: 10.244.0.0/16
      serviceSubnet: 10.96.0.0/12
      dnsDomain: cluster.local
    etcd:
      local:
        dataDir: /var/lib/etcd
        extraArgs:
          quota-backend-bytes: "8589934592"  # 8GB
          auto-compaction-retention: "24"
          auto-compaction-mode: "periodic"
```

---

## 2. 调度优化

### 2.1 节点标签与亲和性

```yaml
# 节点标签
apiVersion: v1
kind: Node
metadata:
  labels:
    topology.kubernetes.io/zone: cn-hangzhou-a
    topology.kubernetes.io/region: cn-hangzhou
    node-type: compute
    gpu-type: v100
    disk-type: ssd

---
# Pod 亲和性配置
apiVersion: v1
kind: Pod
metadata:
  name: my-app
spec:
  affinity:
    nodeAffinity:
      requiredDuringSchedulingIgnoredDuringExecution:
        nodeSelectorTerms:
        - matchExpressions:
          - key: node-type
            operator: In
            values:
            - compute
      preferredDuringSchedulingIgnoredDuringExecution:
      - weight: 100
        preference:
          matchExpressions:
          - key: topology.kubernetes.io/zone
            operator: In
            values:
            - cn-hangzhou-a
    podAntiAffinity:
      requiredDuringSchedulingIgnoredDuringExecution:
      - labelSelector:
          matchExpressions:
          - key: app
            operator: In
            values:
            - my-app
        topologyKey: kubernetes.io/hostname
  
  tolerations:
  - key: "dedicated"
    operator: "Equal"
    value: "gpu"
    effect: "NoSchedule"
```

### 2.2 资源配额与限制

```yaml
# Namespace 资源配额
apiVersion: v1
kind: ResourceQuota
metadata:
  name: production-quota
  namespace: production
spec:
  hard:
    requests.cpu: "100"
    requests.memory: 200Gi
    limits.cpu: "200"
    limits.memory: 400Gi
    pods: "100"
    services: "50"
    persistentvolumeclaims: "100"

---
# LimitRange 默认限制
apiVersion: v1
kind: LimitRange
metadata:
  name: default-limits
  namespace: production
spec:
  limits:
  - default:
      cpu: "500m"
      memory: 512Mi
    defaultRequest:
      cpu: "200m"
      memory: 256Mi
    max:
      cpu: "4"
      memory: 8Gi
    min:
      cpu: "50m"
      memory: 64Mi
    type: Container
```

### 2.3 调度器扩展

```go
// plugins/preemption/preemption.go

type PreemptionPlugin struct {
    handle framework.Handle
}

func (p *PreemptionPlugin) Name() string {
    return "Preemption"
}

func (p *PreemptionPlugin) PreFilter(ctx context.Context, cycleState *framework.CycleState, pod *v1.Pod) *framework.Status {
    // 检查是否需要抢占
    return framework.Success
}

func (p *PreemptionPlugin) Filter(ctx context.Context, cycleState *framework.CycleState, pod *v1.Pod, nodeInfo *framework.NodeInfo) *framework.Status {
    node := nodeInfo.Node()
    if node == nil {
        return framework.NewStatus(framework.Unschedulable, "node not found")
    }
    
    // 检查资源是否足够
    if !p.canFit(pod, nodeInfo) {
        return framework.NewStatus(framework.Unschedulable, "insufficient resources")
    }
    
    return framework.Success
}

func (p *PreemptionPlugin) PostFilter(ctx context.Context, cycleState *framework.CycleState, pod *v1.Pod, 
    nodes *v1.NodeList) *framework.PreFilterResult {
    // 尝试抢占
    for _, node := range nodes.Items {
        if p.canPreempt(pod, &node) {
            return &framework.PreFilterResult{
                Nodes: &v1.NodeList{Items: []v1.Node{node}},
            }
        }
    }
    return nil
}

func (p *PreemptionPlugin) canPreempt(pod *v1.Pod, node *v1.Node) bool {
    // 实现抢占逻辑
    return false
}
```

---

## 3. 网络插件

### 3.1 Calico BGP 模式

```yaml
# calico BGP 配置
apiVersion: operator.tigera.io/v1
kind: Installation
metadata:
  name: default
spec:
  calicoNetwork:
    bgp: Enabled
    ipPools:
    - blockSize: 26
      cidr: 10.244.0.0/16
      encapsulation: VXLANCrossSubnet
      natOutgoing: Enabled
      nodeSelector: all()
    nodeAddressAutodetectionV4:
      interface: eth0
  variant: Calico
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: bird-config
  namespace: calico-system
data:
  birdsASNum: |
    AS100 {
      router-id auto;
      
      neighbor 192.168.1.100 {
        password "secret";
        as 65000;
      }
    }
```

### 3.2 Cilium eBPF 模式

```yaml
# Cilium eBPF 配置
apiVersion: helm.cattle.io/v1
kind: HelmChartConfig
metadata:
  name: cilium
spec:
  valuesContent: |-
    k8sServiceHost: kubernetes.default.svc
    k8sServicePort: 443
    tunnel: disabled
    bpf:
      masquerade: true
      hostLegacyRouting: false
      egressMasquerade: true
    ipam:
      mode: kubernetes
    cluster:
      name: production
      id: 1
```

---

## 4. 存储方案

### 4.1 Ceph RBD 存储

```yaml
# Ceph RBD StorageClass
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: ceph-rbd
provisioner: ceph.rbd.csi.ceph.com
parameters:
  monitors: 10.0.0.1:6789,10.0.0.2:6789,10.0.0.3:6789
  pool: rbd
  userId: csi-rbd
  userSecretName: csi-rbd-secret
  imageFormat: "2"
  imageFeatures: layering,fast-diff,deep-flatten
  csi.storage.k8s.io/provisioner-secret-name: csi-rbd-secret
  csi.storage.k8s.io/provisioner-secret-namespace: default
  csi.storage.k8s.io/node_stage-secret-name: csi-rbd-secret
  csi.storage.k8s.io/node_stage-secret-namespace: default
reclaimPolicy: Retain
volumeBindingMode: Immediate
allowVolumeExpansion: true
```

### 4.2 本地存储

```yaml
# local-path StorageClass
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: local-path
provisioner: rancher.io/local-path
volumeBindingMode: WaitForFirstConsumer
reclaimPolicy: Delete
parameters:
  hostDir: /mnt/disks
  mountDir: /mnt/disks
  fsType: ext4
```

---

## 5. 监控体系

### 5.1 Prometheus 配置

```yaml
# prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'kubernetes-apiservers'
    kubernetes_sd_configs:
    - role: endpoints
    scheme: https
    tls_config:
      ca_file: /var/run/secrets/kubernetes.io/serviceaccount/ca.crt
    bearer_token_file: /var/run/secrets/kubernetes.io/serviceaccount/token
    relabel_configs:
    - source_labels: [__meta_kubernetes_namespace, __meta_kubernetes_service_name, __meta_kubernetes_endpoint_port_name]
      action: keep
      regex: default;kubernetes;https

  - job_name: 'kubernetes-nodes'
    kubernetes_sd_configs:
    - role: node
    scheme: https
    tls_config:
      ca_file: /var/run/secrets/kubernetes.io/serviceaccount/ca.crt
    bearer_token_file: /var/run/secrets/kubernetes.io/serviceaccount/token
    relabel_configs:
    - action: labelmap
      regex: __meta_kubernetes_node_label_(.+)

  - job_name: 'kubernetes-pods'
    kubernetes_sd_configs:
    - role: pod
    relabel_configs:
    - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_scrape]
      action: keep
      regex: true
    - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_path]
      action: replace
      target_label: __metrics_path__
      regex: (.+)
```

### 5.2 Grafana 仪表盘

```json
{
  "dashboard": {
    "title": "Kubernetes Cluster Overview",
    "panels": [
      {
        "title": "CPU Usage",
        "type": "graph",
        "targets": [
          {
            "expr": "sum(rate(container_cpu_usage_seconds_total{namespace=\"$namespace\"}[5m])) by (pod)",
            "legendFormat": "{{pod}}"
          }
        ]
      },
      {
        "title": "Memory Usage",
        "type": "graph",
        "targets": [
          {
            "expr": "sum(container_memory_working_set_bytes{namespace=\"$namespace\"}) by (pod)",
            "legendFormat": "{{pod}}"
          }
        ]
      }
    ]
  }
}
```

---

## 6. 故障排查

### 6.1 常见问题排查

| 问题 | 症状 | 排查命令 | 解决方案 |
|------|------|----------|----------|
| Pod  Pending | 无法调度 | `kubectl describe pod` | 检查资源配额、节点标签 |
| CrashLoopBackOff | 反复重启 | `kubectl logs --previous` | 检查应用配置、资源限制 |
| ImagePullBackOff | 镜像拉取失败 | `kubectl describe pod` | 检查镜像地址、凭证 |
| OOMKilled | 内存不足 | `kubectl top pod` | 增加内存限制 |
| NetworkTimeout | 网络超时 | `kubectl exec ping` | 检查网络插件 |

### 6.2 节点故障排查

```bash
# 检查节点状态
kubectl get nodes
kubectl describe node <node-name>

# 检查 kubelet 日志
journalctl -u kubelet -f

# 检查网络
kubectl exec <pod> -- ping <other-pod-ip>

# 检查存储
kubectl get pv
kubectl get pvc

# 检查事件
kubectl get events --sort-by='.lastTimestamp'
```

---

## 7. 最佳实践

### 7.1 Pod 设计规范

1. **资源限制**：必须设置 requests 和 limits
2. **健康检查**：配置 liveness 和 readiness probe
3. **优雅退出**：实现 SIGTERM 处理
4. **日志收集**：输出到 stdout/stderr
5. **安全运行**：以非 root 用户运行

### 7.2 高可用设计

1. **多 Master**：至少 3 个 Master 节点
2. **etcd 集群**：3/5 节点，奇数配置
3. **跨可用区**：节点分布在不同 AZ
4. **Pod 反亲和**：关键服务多副本分散
5. **备份策略**：定期备份 etcd

---

## 8. 总结

### 8.1 核心配置回顾

| 组件 | 关键配置 |
|------|----------|
| Master | 3 节点高可用 |
| etcd | 3/5 节点集群 |
| CNI | Calico/Cilium |
| 存储 | Ceph RBD / 本地 |
| 监控 | Prometheus + Grafana |

### 8.2 生产 Checklist

- [ ] 集群高可用部署
- [ ] 网络插件配置
- [ ] 存储类定义
- [ ] 监控告警配置
- [ ] 备份恢复策略
- [ ] 安全加固

---

*最后更新：2026-08-11*
*作者：Ryan*
