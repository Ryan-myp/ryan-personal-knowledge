# Service Mesh: Istio 深度解析

> 深入 Istio 架构、流量管理、安全策略。

---

## 1. 架构

```
┌─────────────────────────────────────────────────────────────┐
│                         Control Plane                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                   │
│  │  Pilot   │  │  Mixer   │  │ Citadel  │                   │
│  │ (配置分发) │  │ (策略执行) │  │ (证书管理) │                   │
│  └──────────┘  └──────────┘  └──────────┘                   │
└─────────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────────┐
│                        Data Plane                             │
│                    ┌──────────────┐                          │
│                    │  Envoy Sidecar│ ←→ 应用容器               │
│                    └──────────────┘                          │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Traffic Management

```yaml
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: my-service
spec:
  hosts:
  - my-service
  http:
  - match:
    - headers:
        x-canary: exact "true"
    route:
    - destination:
        host: my-service
        subset: v2
        weight: 100
  - route:
    - destination:
        host: my-service
        subset: v1
        weight: 90
    - destination:
        host: my-service
        subset: v2
        weight: 10
```

---

## 3. 实践 Checklist
- [ ] 启用 mTLS
- [ ] 配置链路追踪
- [ ] 设置熔断策略
- [ ] 监控服务网格

**参考**: Istio 官方文档、服务网格最佳实践
