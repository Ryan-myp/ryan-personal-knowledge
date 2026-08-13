# K8s HPA/VPA自动扩缩容 - 资深专家深度实现

## 一、HPA架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      Kubernetes HPA架构                                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   ┌─────────────┐      ┌─────────────┐      ┌─────────────┐           │
│   │   Metrics   │      │   Controller│      │   Scheduler │           │
│   │   Server    │◄────►│   Manager   │◄────►│             │           │
│   └─────────────┘      └──────┬──────┘      └─────────────┘           │
│          ▲                    │                                       │
│          │                    ▼                                       │
│   ┌─────────────┐      ┌─────────────┐                               │
│   │  Prometheus │      │  kube-controller-manager              │       │
│   │  Adapter    │      │             │                             │
│   └─────────────┘      └─────────────┘                               │
│                                                                         │
│   工作流程:                                                             │
│   1. Metrics Server收集资源指标                                         │
│   2. HPA Controller对比期望副本数                                       │
│   3. 调用Scale API调整Deployment副本                                    │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、HPA配置

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: frontend-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: frontend
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 0
      policies:
      - type: Pods
        value: 2
        periodSeconds: 60
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
      - type: Percent
        value: 10
        periodSeconds: 60
```

## 三、VPA配置

```yaml
apiVersion: autoscaling.k8s.io/v1
kind: VerticalPodAutoscaler
metadata:
  name: frontend-vpa
spec:
  targetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: frontend
  updatePolicy:
    updateMode: "Auto"
  resourcePolicy:
    containerPolicies:
    - containerName: '*'
      minAllowed:
        cpu: 100m
        memory: 128Mi
      maxAllowed:
        cpu: "2"
        memory: 2Gi
      controlledResources: ["cpu", "memory"]
```

## 四、面试高频题

### Q1: HPA和VPA的区别？

```
A:
• HPA: 水平扩缩容，调整Pod数量
• VPA: 垂直扩缩容，调整资源配额
• HPA响应快，VPA需要重启Pod
```

### Q2: HPA扩容策略有哪些？

```
A:
1. CPU利用率
2. 自定义Metrics
3. 外部Metrics
4. 对象Metrics
```

## 五、自测题

1. 解释HPA工作原理
2. 如何配置扩缩容策略？
3. VPA的更新模式有哪些？

---

## 参考文档

- [K8s HPA文档](https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/)
- [K8s VPA文档](https://github.com/kubernetes/autoscaler/tree/master/vertical-pod-autoscaler)
