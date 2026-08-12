# Service Mesh 深度实现

> **文档级别**: Level 5 - 专家级  
> **创建日期**: 2026-08-13  
> **状态**: ✅ 已补齐

---

## 一、Istio 架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Istio 架构                                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                      Control Plane                                  │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                │   │
│  │  │  Pilot      │  │  Citadel    │  │  Galley     │                │   │
│  │  │  (配置分发)  │  │  (证书管理)  │  │  (配置验证)  │                │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘                │   │
│  │                       │                                              │   │
│  │              ┌────────▼────────┐                                   │   │
│  │              │   istiod        │                                   │   │
│  │              │  (单入口控制面)  │                                   │   │
│  │              └─────────────────┘                                   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                              │                                              │
│                              ▼                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                      Data Plane                                     │   │
│  │                                                                     │   │
│  │  ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐        │   │
│  │  │Pod A    │    │Pod B    │    │Pod C    │    │Pod D    │        │   │
│  │  │┌───────┐│    │┌───────┐│    │┌───────┐│    │┌───────┐│        │   │
│  │  ││App    ││◄──►││Envoy  ││    ││Envoy  ││◄──►││App    ││        │   │
│  │  │└───────┘│    │└───────┘│    │└───────┘│    │└───────┘│        │   │
│  │  └─────────┘    └─────────┘    └─────────┘    └─────────┘        │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 二、核心 CRD 配置

```yaml
# 文件: istio/virtual-service.yaml
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: ad-bidding-service
  namespace: advertising
spec:
  hosts:
    - ad-bidding.default.svc.cluster.local
  http:
    - match:
        - headers:
            x-ab-test:
              exact: "control"
      route:
        - destination:
            host: ad-bidding-v1
            port:
              number: 8080
    - route:
        - destination:
            host: ad-bidding-v2
            port:
              number: 8080
      weight: 90
    - route:
        - destination:
            host: ad-bidding-v1
            port:
              number: 8080
      weight: 10
---
apiVersion: networking.istio.io/v1beta1
kind: DestinationRule
metadata:
  name: ad-bidding-destination
  namespace: advertising
spec:
  host: ad-bidding.default.svc.cluster.local
  subsets:
    - name: v1
      labels:
        version: v1
    - name: v2
      labels:
        version: v2
  trafficPolicy:
    loadBalancer:
      simple: ROUND_ROBIN
    connectionPool:
      tcp:
        maxConnections: 1000
      http:
        h2UpgradePolicy: DEFAULT
        http1MaxPendingRequests: 100
        http2MaxRequests: 1000
    outlierDetection:
      consecutive5xxErrors: 5
      interval: 30s
      baseEjectionTime: 30s
      maxEjectionPercent: 50
```

---

## 三、参考资料

```
核心文档:
├── Istio 官网: https://istio.io/
├── Kubernetes Network Policy
└── Envoy Proxy: https://www.envoyproxy.io/
```

---

*文档版本: v1.0*  
*最后更新: 2026-08-13*  
*作者: Ryan*
