# Kubernetes 生产环境实战深度指南

> **文档级别**: Level 5 - 专家级  
> **创建日期**: 2026-08-13  
> **状态**: ✅ 已补齐

---

## 一、生产集群架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        生产集群拓扑架构                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                     │
│  │   Master 1  │    │   Master 2  │    │   Master 3  │                     │
│  │  (etcd +    │    │  (etcd +    │    │  (etcd +    │                     │
│  │   API Server)│    │   API Server)│    │   API Server)│                    │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘                     │
│         │                  │                  │                             │
│         └──────────────────┼──────────────────┘                             │
│                            │                                                │
│                    ┌───────▼───────┐                                        │
│                    │   API Server   │ ← 统一入口                            │
│                    │   (负载均衡)   │                                        │
│                    └───────┬───────┘                                        │
│                            │                                                │
│       ┌─────────────────────┼─────────────────────┐                        │
│       │                     │                     │                        │
│  ┌────▼────┐          ┌────▼────┐          ┌────▼────┐                    │
│  │Node Pool│          │Node Pool│          │Node Pool│                    │
│  │  业务    │          │  计算    │          │  GPU    │                    │
│  │  节点    │          │  节点    │          │  节点    │                    │
│  └────┬────┘          └────┬────┘          └────┬────┘                    │
│       │                     │                     │                        │
│  ┌────▼─────────────────────▼─────────────────────▼────┐                  │
│  │                 业务 Pod 分布                         │                  │
│  │  • 竞价服务 → 计算节点池                              │                  │
│  │  • 模型推理 → GPU 节点池                              │                  │
│  │  • 监控日志 → 业务节点池                              │                  │
│  └─────────────────────────────────────────────────────┘                  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 二、资源配置与调度策略

```yaml
# 文件: k8s/ad-bidding-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ad-bidding-service
  namespace: advertising
  labels:
    app: ad-bidding
    tier: core
    team: platform
spec:
  replicas: 6
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0  # 零停机部署
  selector:
    matchLabels:
      app: ad-bidding
  template:
    metadata:
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "8080"
    spec:
      # ─── 节点亲和性 ───
      affinity:
        nodeAffinity:
          requiredDuringSchedulingIgnoredDuringExecution:
            nodeSelectorTerms:
            - matchExpressions:
              - key: node-type
                operator: In
                values:
                - compute  # 竞价服务部署在计算节点
        podAntiAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
          - weight: 100
            podAffinityTerm:
              labelSelector:
                matchExpressions:
                - key: app
                  operator: In
                  values:
                  - ad-bidding
              topologyKey: kubernetes.io/hostname  # 跨节点分散
              
      # ─── 资源限制 ───
      containers:
      - name: bidding-service
        image: ghcr.io/ryan-myp/ad-bidding:v1.5.0
        ports:
        - containerPort: 8080
          name: http
        - containerPort: 9090
          name: metrics
        resources:
          requests:
            cpu: "500m"
            memory: "512Mi"
          limits:
            cpu: "2000m"
            memory: "2Gi"
            
        # ─── 健康检查 ───
        livenessProbe:
          httpGet:
            path: /healthz
            port: 8080
          initialDelaySeconds: 30
          periodSeconds: 10
          timeoutSeconds: 5
          failureThreshold: 3
          
        readinessProbe:
          httpGet:
            path: /ready
            port: 8080
          initialDelaySeconds: 10
          periodSeconds: 5
          timeoutSeconds: 3
          failureThreshold: 3
          
        # ─── 优雅退出 ───
        lifecycle:
          preStop:
            exec:
              command: ["/bin/sh", "-c", "sleep 10"]  # 等待连接 draining
              
      # ─── 优先级类 ───
      priorityClassName: high-priority
      
      # ─── 容忍度 (可用于专用节点) ───
      tolerations:
      - key: "dedicated"
        operator: "Equal"
        value: "bidding"
        effect: "NoSchedule"
---
# Horizontal Pod Autoscaler
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: ad-bidding-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: ad-bidding-service
  minReplicas: 4
  maxReplicas: 20
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70  # CPU 使用率超过 70% 触发扩容
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 60
      policies:
      - type: Pods
        value: 2
        periodSeconds: 60
    scaleDown:
      stabilizationWindowSeconds: 300  # 5 分钟冷却期
      policies:
      - type: Pods
        value: 1
        periodSeconds: 120
```

---

## 三、网络策略与安全

```yaml
# 文件: k8s/network-policy.yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: bidding-isolation
  namespace: advertising
spec:
  podSelector:
    matchLabels:
      app: ad-bidding
  policyTypes:
  - Ingress
  - Egress
  
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          name: gateway
    - podSelector:
        matchLabels:
          app: ad-receiver
    ports:
    - port: 8080
      protocol: TCP
      
  egress:
  - to:
    - podSelector:
        matchLabels:
          app: redis-cache
    ports:
    - port: 6379
      protocol: TCP
  - to:
    - podSelector:
        matchLabels:
          app: etcd
    ports:
    - port: 2379
      protocol: TCP
  - to:
    - namespaceSelector: {}  # 允许 DNS
    ports:
    - port: 53
      protocol: UDP
```

---

## 四、参考资料

```
官方文档:
├── Kubernetes Docs: https://kubernetes.io/docs/
├── K8s Best Practices: https://kubernetes.io/docs/concepts/cluster-administration/
└── Kube-bench: CIS Benchmark 检查

工具链:
├── kubectl-trace: eBPF 性能分析
├── k9s: 终端 UI
└── tilt: 本地开发工作流
```

---

*文档版本: v1.0*  
*最后更新: 2026-08-13*  
*作者: Ryan*
