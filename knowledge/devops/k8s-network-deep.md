# Kubernetes网络插件 - 资深专家深度实现

## 一、网络模型

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     K8s网络模型                                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   Pod Network:                                                          │
│   • 每个Pod拥有独立IP                                                    │
│   • Pod之间可直接通信                                                    │
│   • 跨节点使用Overlay网络                                                │
│                                                                         │
│   Service Network:                                                      │
│   • ClusterIP: 虚拟IP                                                   │
│   • NodePort: 节点端口映射                                               │
│   • LoadBalancer: 云厂商负载均衡                                         │
│                                                                         │
│   Network Policy:                                                       │
│   • 入站规则                                                            │
│   • 出站规则                                                            │
│   • 命名空间隔离                                                         │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、Flannel实现

```go
package flannel

import (
    "net"
)

type Subnet struct {
    Net    net.IPNet
    EP     string
    Private  bool
}

type Backend struct {
    iface  *net.Interface
    subnet Subnet
}

func (b *Backend) Route() ([]Route, error) {
    // VxLAN封装
    routes := []Route{
        {
            Destination: b.subnet.Net.IP.String(),
            Gateway:     "0.0.0.0",
            Device:      "vxlan-" + b.subnet.Net.String(),
        },
    }
    return routes, nil
}
```

## 三、Calico实现

```go
package calico

import (
    "github.com/projectcalico/api/pkg/apis/projectcalico/v3"
)

type BGPPeer struct {
    Spec v3.BGPConfigurationSpec
}

type IPPool struct {
    Spec v3.IPPoolSpec
}

func NewIPPools(c CIDR) *IPPools {
    return &IPPools{
        CIDR: c,
        Size: 24,
    }
}
```

## 四、面试高频题

### Q1: K8s网络模型是什么？

```
A:
1. Pod网络: 每个Pod独立IP
2. Service网络: 虚拟IP负载均衡
3. NetworkPolicy: 访问控制
```

### Q2: 如何实现Pod网络？

```
A:
1. CNI插件
2. Overlay网络(VxLAN/IPIP)
3. BGP路由
```

## 五、自测题

1. 解释CNI插件原理
2. 如何实现服务发现？
3. 如何配置网络策略？

---

## 参考文档

- [K8s网络规范](https://kubernetes.io/docs/concepts/cluster-administration/networking/)
- [CNI规范](https://github.com/kubernetes/cni)
