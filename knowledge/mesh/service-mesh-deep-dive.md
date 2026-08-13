# Service Mesh 深度解析

> 深入 Istio/Linkerd 架构、流量治理、可观测性。

---

## 1. 核心架构

```
┌─────────────────────────────────────────────────────────────┐
│                        Application                           │
│  ┌─────────┐              ┌─────────┐                       │
│  │ Service │◀────────────▶│ Service │  (Sidecar Proxy)      │
│  │   A     │  mTLS/HTTP2  │   B     │                       │
│  └────┬────┘              └────┬────┘                       │
│       │                        │                            │
│  ┌────▼────┐              ┌────▼────┐                       │
│  │ Envoy   │              │ Envoy   │                       │
│  │ Proxy   │              │ Proxy   │                       │
│  └────┬────┘              └────┬────┘                       │
│       │                        │                            │
│       └────────────┬───────────┘                            │
│                    │                                        │
│           ┌────────▼────────┐                               │
│           │    Control      │                               │
│           │    Plane        │                               │
│           └─────────────────┘                               │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Istio 核心组件

| 组件 | 功能 |
|------|------|
| Pilot | 服务发现、配置分发 |
| Mixer | 策略执行、遥测采集 |
| Citadel | 证书管理、mTLS |
| Ingress/Egress | 流量入口/出口 |

---

## 3. 流量治理

```yaml
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: ads-service
spec:
  hosts:
  - ads.example.com
  http:
  - match:
    - headers:
        x-user-type:
          exact: premium
    route:
    - destination:
        host: ads-v2
        weight: 100
  - route:
    - destination:
        host: ads-v1
        weight: 100
```

---

## 4. 可观测性

```bash
# Kiali 服务网格可视化
kubectl port-forward svc/kiali 20001:20001

# Prometheus 指标
curl http://prometheus:9090/metrics | grep istio

# Kibana 日志分析
# 通过 Fluentd 收集 Envoy 日志
```

---

**参考**: Istio 官方文档、Service Mesh 架构实践
