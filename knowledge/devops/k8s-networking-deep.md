# Kubernetes 网络深度实现

> **文档级别**: Level 5 - 专家级  
> **创建日期**: 2026-08-13  
> **状态**: ✅ 已补齐

---

## 一、K8s 网络模型

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        K8s 网络架构                                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Pod Network                                                                │
│  ├── Cluster IP: 虚拟IP，仅集群内可见                                        │
│  ├── NodePort: 节点端口，通过NodeIP:Port访问                                  │
│  ├── LoadBalancer: 云厂商LB，公网访问                                        │
│  └── Ingress: HTTP路由，TLS终止                                              │
│                                                                             │
│  CNI 插件选择                                                               │
│  ├── Calico: BGP路由，性能优秀                                               │
│  ├── Flannel: VXLAN，简单易用                                                │
│  ├── Cilium: eBPF，网络策略强                                                │
│  └── Containernetworking: 标准接口                                           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 二、参考资料

```
核心文档:
├── K8s Networking: https://kubernetes.io/docs/concepts/cluster-administration/networking/
├── Calico: https://docs.projectcalico.org/
└── Cilium: https://cilium.io/
```

---

*文档版本: v1.0*  
*最后更新: 2026-08-13*  
*作者: Ryan*
