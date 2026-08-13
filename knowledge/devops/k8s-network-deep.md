# K8s网络插件 - 资深专家深度实现

## 一、CNI接口

```go
package cni

// CNI Plugin接口
type Plugin interface {
    Add(ctx context.Context, nc *NetworkConfig) error
    Delete(ctx context.Context, nc *NetworkConfig) error
    Get(*cni.GetRequest, *cni.GetResponse) error
    Version() string
}

// NetworkConfig
type NetworkConfig struct {
    Name       string           `json:"name"`
    Type       string           `json:"type"`
    IPAM       *IPAMConfig      `json:"ipam,omitempty"`
    RuntimeCfg *RuntimeConfig   `json:"runtimeConfig,omitempty"`
}
```

## 二、Calico架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Calico架构                                       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   etcd (全局配置)                                                        │
│       │                                                                │
│       ▼                                                                │
│   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐               │
│   │ Node BGP    │    │ Node BGP    │    │ Node BGP    │               │
│   │ Router      │    │ Router      │    │ Router      │               │
│   └──────┬──────┘    └──────┬──────┘    └──────┬──────┘               │
│          │                  │                  │                       │
│   ┌──────▼──────┐    ┌──────▼──────┐    ┌──────▼──────┐               │
│   │  Felix      │    │  Felix      │    │  Felix      │               │
│   │ (网络配置)  │    │ (网络配置)  │    │ (网络配置)  │               │
│   └─────────────┘    └─────────────┘    └─────────────┘               │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## 三、网络策略

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: deny-all
  namespace: production
spec:
  podSelector: {}
  policyTypes:
  - Ingress
  - Egress
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-frontend
  namespace: production
spec:
  podSelector:
    matchLabels:
      app: frontend
  policyTypes:
  - Ingress
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app: backend
    ports:
    - protocol: TCP
      port: 80
```

## 四、面试高频题

### Q1: 为什么需要CNI？

```
A:
• 标准化容器网络接口
• 插件化架构
• 解耦网络和K8s核心
```

### Q2: Calico和Flannel的区别？

```
A:
• Calico: BGP路由，高性能，支持网络策略
• Flannel: VXLAN overlay，简单易用
```

## 五、自测题

1. 解释CNI接口规范
2. 如何实现网络隔离？
3. 如何优化网络性能？

---

## 参考文档

- [CNI规范](https://github.com/containernetworking/cni)
- [Calico官方文档](https://docs.projectcalico.org/)
