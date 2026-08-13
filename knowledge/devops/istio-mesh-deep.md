# Istio服务网格 - 资深专家深度实现

## 一、核心组件

```
┌─────────────────────────────────────────────────────────────┐
│                      Istio架构                                │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Control Plane                                       │   │
│  │  ├── Istiod (Pilot)                                  │   │
│  │  ├── Citadel (证书)                                  │   │
│  │  └── Galley (配置验证)                               │   │
│  └─────────────────────────────────────────────────────┘   │
│                           │                                 │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Data Plane (Envoy Sidecar)                          │   │
│  │  ├── App Container                                   │   │
│  │  └── Sidecar Proxy                                  │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## 二、流量管理

### 2.1 VirtualService

```yaml
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: orders
spec:
  hosts:
  - orders.default.svc.cluster.local
  http:
  - match:
    - headers:
        x-user-type:
          exact: premium
    route:
    - destination:
        host: orders-v2
        weight: 100
  - route:
    - destination:
        host: orders-v1
        weight: 90
    - destination:
        host: orders-v2
        weight: 10
```

### 2.2 DestinationRule

```yaml
apiVersion: networking.istio.io/v1beta1
kind: DestinationRule
metadata:
  name: orders
spec:
  host: orders.default.svc.cluster.local
  trafficPolicy:
    loadBalancer:
      simple: ROUND_ROBIN
    connectionPool:
      tcp:
        maxConnections: 100
      http:
        h2UpgradePolicy: DEFAULT
        maxRequestsPerConnection: 10
```

## 三、安全策略

### 3.1 mTLS

```yaml
apiVersion: security.istio.io/v1beta1
kind: PeerAuthentication
metadata:
  name: default
spec:
  mtls:
    mode: STRICT
```

### 3.2 AuthorizationPolicy

```yaml
apiVersion: security.istio.io/v1beta1
kind: AuthorizationPolicy
metadata:
  name: orders-policy
spec:
  selector:
    matchLabels:
      app: orders
  rules:
  - from:
    - source:
        principals: ["cluster.local/ns/default/sa/frontend"]
    to:
    - operation:
        methods: ["GET", "POST"]
        paths: ["/api/orders/*"]
```

## 四、可观测性

```yaml
# Prometheus指标
istio_requests_total
istio_request_duration_milliseconds
istio_response_size_bytes
```

## 五、面试高频题

### Q1: Istio和Service Mesh有什么区别？

```
A: Istio是Service Mesh的实现之一。
```

### Q2: 为什么需要Sidecar？

```
A: 隔离业务逻辑和基础设施，无侵入式治理。
```

## 六、自测题

1. 解释Istio流量管理机制
2. 如何实现金丝雀发布？

---

## 参考文档

- [Istio官方文档](https://istio.io/latest/docs/)
