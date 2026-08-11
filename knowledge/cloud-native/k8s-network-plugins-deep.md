# Kubernetes 网络插件深度解析

> 深入 K8s 网络插件：Calico、Flannel、Cilium、服务网格。
> 源码级分析，包含生产环境网络设计。
> 适用对象：K8s 工程师、网络工程师、DevOps

---

## 1. K8s 网络模型

### 1.1 核心要求

```
Kubernetes 网络模型：

1. 每个 Pod 拥有独立 IP
   └── Pod 间可直接通信

2. 所有 Pod 无需 NAT 即可通信
   └── 跨节点直接可达

3. Pod IP 与 Node IP 分离
   └── Pod IP 不重复使用
```

### 1.2 网络组件

```
K8s 网络组件：

├── CNI (Container Network Interface)
│   └── 插件接口标准
│
├── Network Policy
│   └── 网络访问控制
│
├── Service
│   ├── ClusterIP
│   ├── NodePort
│   ├── LoadBalancer
│   └── ExternalName
│
└── Ingress
    └── 七层负载均衡
```

---

## 2. Calico 网络插件

### 2.1 架构原理

```
Calico 架构：

┌─────────────────────────────────────────────────────────────┐
│                   Calico 架构                                │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  etcd (数据存储)                                             │
│  ├── BGP 路由表                                              │
│  ├── Network Policy                                         │
│  └── IP AM (IP 地址管理)                                    │
│                                                             │
│  BGP Router (路由器)                                         │
│  ├── 与 Node 建立 BGP 邻居                                   │
│  └── 广播 Pod 路由                                           │
│                                                             │
│  Felix (节点代理)                                            │
│  ├── 管理 iptables/ipset                                    │
│  ├── 执行 Network Policy                                     │
│  └── 监控节点状态                                            │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 Go 实现 BGP 路由

```go
// calico_bgp.go

package k8s

import (
    "github.com/projectcalico/api/pkg/apis/projectcalico/v3"
    "github.com/projectcalico/libcalico-go/lib/clientv3"
)

type CalicoBGP struct {
    client *clientv3.Client
}

func (c *CalicoBGP) CreateBGPPeer(peer v3.BGPPeer) error {
    _, err := c.client.BGPPeers().Create(c.ctx, &peer, metav1.CreateOptions{})
    return err
}

func (c *CalicoBGP) CreateNodeBGPSpec(nodeName string, spec v3.NodeBGPSpec) error {
    node, err := c.client.Nodes().Get(c.ctx, nodeName, metav1.GetOptions{})
    if err != nil {
        return err
    }
    node.Spec.BGP = &spec
    _, err = c.client.Nodes().Update(c.ctx, node, metav1.UpdateOptions{})
    return err
}
```

---

## 3. Cilium 网络插件

### 3.1 eBPF 架构

```
Cilium eBPF 架构：

┌─────────────────────────────────────────────────────────────┐
│                  Cilium eBPF 架构                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Kernel Space (内核空间)                                      │
│  ├── eBPF Program (BPF 程序)                                 │
│  │   ├── TC Hook (流量控制)                                  │
│  │   ├── cgroup Hook (容器组)                                │
│  │   └── Socket Hook (套接字)                                │
│  │                                                           │
│  └── Maps (BPF 映射)                                        │
│      ├── Endpoint Map (端点映射)                             │
│      ├── Policy Map (策略映射)                               │
│      └── IP Map (IP 映射)                                    │
│                                                             │
│  Userspace (用户空间)                                         │
│  ├── Hubble (可观测性)                                       │
│  ├── Operator (控制器)                                       │
│  └── CLI 工具                                                │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 Go 实现 Network Policy

```go
// cilium_policy.go

package k8s

import (
    "github.com/cilium/cilium/pkg/k8s/apis/cilium.io/v2"
    "k8s.io/client-go/kubernetes"
)

type CiliumPolicy struct {
    client kubernetes.Interface
}

func (c *CiliumPolicy) CreateNetworkPolicy(policy v2.CiliumNetworkPolicy) error {
    _, err := c.client.CiliumV2().CiliumNetworkPolicies("default").Create(c.ctx, &policy, metav1.CreateOptions{})
    return err
}

func (c *CiliumPolicy) GetEndpoints() ([]v2.CiliumEndpoint, error) {
    list, err := c.client.CiliumV2().CiliumEndpoints("default").List(c.ctx, metav1.ListOptions{})
    return list.Items, err
}
```

---

## 4. Service 实现原理

### 4.1 iptables 模式

```
iptables Service 模式：

1. kube-proxy 监听 Service 变化
2. 更新 iptables 规则
3. 流量匹配规则进行 DNAT
```

### 4.2 Go 实现 iptables 规则

```go
// iptables_service.go

package k8s

import (
    "github.com/coreos/go-iptables/iptables"
)

type ServiceProxy struct {
    ipt *iptables.IPTables
}

func (sp *ServiceProxy) CreateServiceRule(service Service) error {
    // 创建 iptables 规则
    return sp.ipt.Append("nat", "PREROUTING", 
        "-d", service.ClusterIP,
        "-p", string(service.Protocol),
        "-j", "REDIRECT",
        "--to-ports", service.Port)
}
```

---

## 5. Ingress 控制器

### 5.1 Nginx Ingress

```
Nginx Ingress 架构：

├── Ingress Controller
│   ├── 监听 Ingress 资源变化
│   └── 生成 Nginx 配置
│
├── Nginx Pod
│   ├── 七层负载均衡
│   ├── SSL 终止
│   └── 路径路由
│
└── Backend Service
    └── 实际处理请求
```

### 5.2 Go 实现 Ingress 控制器

```go
// ingress_controller.go

package k8s

import (
    "k8s.io/client-go/informers"
    "k8s.io/client-go/kubernetes"
)

type IngressController struct {
    client    kubernetes.Interface
    ingress   *nginx.Ingress
}

func (ic *IngressController) Run(stopCh <-chan struct{}) {
    factory := informers.NewSharedInformerFactory(ic.client, 0)
    ingressInformer := factory.Networking().V1().Ingresses()
    
    ingressInformer.Informer().AddEventHandler(cache.ResourceEventHandlerFuncs{
        AddFunc:    ic.addIngress,
        UpdateFunc: ic.updateIngress,
        DeleteFunc: ic.deleteIngress,
    })
    
    factory.Start(stopCh)
    cache.WaitForCacheSync(stopCh, ingressInformer.Informer().HasSynced)
    <-stopCh
}

func (ic *IngressController) addIngress(obj interface{}) {
    ingress := obj.(*networkingv1.Ingress)
    ic.ingress.Update(ingress)
}
```

---

## 6. 网络诊断工具

### 6.1 常用命令

```
K8s 网络诊断命令：

1. 检查 Pod 网络
   kubectl exec -n <ns> <pod> -- ip addr

2. 测试连通性
   kubectl run -it --rm test --image=busybox -- wget <service>

3. 查看 Service 端点
   kubectl get endpoints <service>

4. 查看网络策略
   kubectl get netpol -A

5. 分析流量
   kubectl debug -n <ns> <pod> --image=nicolaka/netshoot
```

### 6.2 Go 实现网络诊断

```go
// network_diag.go

package k8s

import (
    "context"
    "k8s.io/client-go/kubernetes"
)

type NetworkDiagnostic struct {
    client kubernetes.Interface
}

func (nd *NetworkDiagnostic) TestConnectivity(namespace, pod, target string) error {
    // 执行连通性测试
    cmd := []string{"wget", "--spider", target}
    _, err := nd.client.CoreV1().RESTClient().Post().
        Resource("pods").
        Name(pod).
        Namespace(namespace).
        SubResource("exec").
        VersionedParams(&v1.PodExecOptions{
            Command: cmd,
            Stdin:   false,
            Stdout:  true,
            Stderr:  true,
        }, scheme.ParameterCodec).
        Do(context.Background()).
        Into(&result)
    return err
}
```

---

## 7. 总结

### 7.1 核心原理回顾

| 组件 | 作用 |
|------|------|
| CNI | 容器网络接口 |
| Calico | BGP + iptables |
| Cilium | eBPF 高性能 |
| Service | 负载均衡 |
| Ingress | 七层路由 |

### 7.2 最佳实践

- [ ] 根据场景选择网络插件
- [ ] 配置合理的 Network Policy
- [ ] 监控网络性能指标
- [ ] 建立网络诊断工具
- [ ] 定期安全审计

---

*最后更新：2026-08-11*
*作者：Ryan*
