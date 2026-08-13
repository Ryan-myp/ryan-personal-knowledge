# K8s网络插件(CNI) - 资深专家深度实现

## 一、CNI架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      CNI 插件架构                                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   kubelet ──► CNI Plugin ──► Network Plugin                              │
│      │              │                │                                   │
│      │         添加网络接口       配置IP路由                              │
│      │              │                │                                   │
│      └──────────────┴────────────────┘                                   │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、插件实现

```go
package main

import (
    "github.com/containernetworking/cni/pkg/skel"
    "github.com/containernetworking/cni/pkg/types"
    "github.com/containernetworking/cni/pkg/types/current"
    "github.com/containernetworking/plugins/pkg/utils"
)

type NetConf struct {
    types.NetConf
    Name string `json:"name"`
    IP   IPConfig `json:"ip"`
}

type IPConfig struct {
    Address string `json:"address"`
}

func cmdAdd(args *skel.CmdArgs) error {
    conf := NetConf{}
    if err := types.LoadConf(args.StdinData, &conf); err != nil {
        return err
    }
    
    // 创建网络接口
    containerIF, err := current.NewCurrentFromOld(&current.NetConf{}, args.StdinData)
    if err != nil {
        return err
    }
    
    // 配置IP地址
    ipAddr, err := net.ParseCIDR(conf.IP.Address)
    if err != nil {
        return err
    }
    
    result := &current.Result{
        Interfaces: []*current.Interface{
            {Name: containerIF.Name},
        },
        IPs: []*current.IPConfig{
            {
                Address: *ipAddr,
                Interface: intPtr(0),
            },
        },
    }
    
    return types.PrintResult(result, conf.CNIVersion)
}
```

## 三、面试高频题

### Q1: CNI插件如何工作？

```
A:
1. 接收Pod网络请求
2. 创建veth对
3. 配置IP和路由
```

### Q2: 主流CNI插件有哪些？

```
A:
1. Calico: BGP路由
2. Flannel: VXLAN overlay
3. Cilium: eBPF高性能
```

## 四、自测题

1. 解释CNI架构
2. 如何实现插件？
3. 如何选择CNI？

---

## 参考文档

- [CNI Spec](https://github.com/containerd/cni)
- [Calico](https://projectcalico.docs.tigera.io/)
