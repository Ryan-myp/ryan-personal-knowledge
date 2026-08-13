# Istio服务网格 - 资深专家深度实现

## 一、架构设计

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    Istio服务网格架构                                       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   Control Plane                                                          │
│   ├── Istiod (核心组件)                                                   │
│   │   ├── Pilot (服务发现/路由)                                            │
│   │   ├── Citadel (证书管理)                                              │
│   │   └── Galley (配置验证)                                               │
│   └── 配置注入                                                             │
│                                                                         →
│   Data Plane                                                             │
│   └── Envoy Sidecar (每个Pod)                                              │
│       ├── 流量拦截                                                          │
│       ├── 安全通信                                                          │
│       └── 可观测性                                                          │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、流量管理

```yaml
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: bookinfo
spec:
  hosts:
  - reviews.example.com
  http:
  - match:
    - headers:
        end-user:
          exact: john
    route:
    - destination:
        host: reviews
        subset: v2
    timeout: 10s
  - route:
    - destination:
        host: reviews
        subset: v1
    fault:
      abort:
        percentage: 10
        httpStatus: 500
```

## 三、面试高频题

### Q1: Istio相比传统网关有什么优势？

```
A:
1. 服务发现自动
2. mTLS默认
3. 细粒度路由
```

### Q2: 如何实现流量灰度？

```
A:
1. VirtualService权重路由
2. DestinationRule子集
3. 金丝雀发布
```

## 四、自测题

1. 解释Istio架构
2. 如何实现流量管理？
3. 如何保障安全？

---

## 参考文档

- [Istio Docs](https://istio.io/latest/docs/)
- [Service Mesh](https://istio.io/latest/docs/concepts/what-is-istio/)
