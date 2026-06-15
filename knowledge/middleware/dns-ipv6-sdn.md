# 网络协议深度：DNS/IPv6/SDN

> DNS 解析优化/IPv6 迁移/软件定义网络 SDN

---

## 第一部分：入门引导（5 分钟速览）

### 为什么需要深入理解网络？

广告平台是典型的网络密集型系统：
- **低延迟**：竞价 RTT < 100ms
- **高吞吐**：日志传输 GB/s 级
- **高可用**：多机房容灾
- **安全**：DDoS 防护

---

## 第二部分：DNS 深度

### 2.1 DNS 解析流程

```
浏览器 → 本地缓存 → 递归 DNS → 根域名 → TLD → 权威 DNS → IP
```

### 2.2 Go 实现 DNS 优化

```go
package dns

import (
    "context"
    "net"
    "time"
)

type OptimizedResolver struct {
    resolver *net.Resolver
    cache    map[string]string
    cacheTTL time.Duration
}

func NewOptimizedResolver() *OptimizedResolver {
    return &OptimizedResolver{
        resolver: &net.Resolver{
            Dial: func(ctx context.Context, network, address string) (net.Conn, error) {
                // 使用专用 DNS 服务器
                d := net.Dialer{
                    Timeout: 100 * time.Millisecond,
                }
                return d.DialContext(ctx, network, "dns.google:53")
            },
        },
        cache: make(map[string]string),
        cacheTTL: 5 * time.Minute,
    }
}

func (r *OptimizedResolver) Resolve(ctx context.Context, host string) (string, error) {
    // 1. 检查缓存
    if ip, ok := r.cache[host]; ok {
        return ip, nil
    }
    
    // 2. 查询 DNS
    addrs, err := r.resolver.LookupIPAddr(ctx, host)
    if err != nil {
        return "", err
    }
    
    // 3. 缓存结果
    if len(addrs) > 0 {
        r.cache[host] = addrs[0].IP.String()
    }
    
    return addrs[0].IP.String(), nil
}
```

### 2.3 DNS 预解析

```go
func PreResolve(hosts []string) {
    for _, host := range hosts {
        go func(h string) {
            conn, err := net.Dial("tcp", h+":443")
            if err != nil {
                return
            }
            conn.Close()
        }(host)
    }
}
```

---

## 第三部分：IPv6

### 3.1 IPv6 适配

```go
package ipv6

import (
    "net"
)

// Dual Stack 支持
func ListenDualStack(addr string) (net.Listener, error) {
    // 同时监听 IPv4 和 IPv6
    listener, err := net.Listen("tcp6", "["+addr+"]:8080")
    if err != nil {
        return nil, err
    }
    
    // 启用 IPv4-mapped IPv6 地址
    if err := listener.(*net.TCPListener).SetDualStack(true); err != nil {
        return nil, err
    }
    
    return listener, nil
}

// IPv6 地址处理
func IsIPv6(ip net.IP) bool {
    return ip.To4() == nil && ip.To16() != nil
}
```

---

## 第四部分：SDN

### 4.1 SDN 控制器

```go
package sdn

import (
    "context"
)

type SDNController struct {
    switches map[string]*Switch
    routes   map[string][]Route
}

type Switch struct {
    ID       string
    Address  string
    Flows    []Flow
}

type Flow struct {
    Match    Match
    Actions  []Action
    Priority int
}

type Match struct {
    SrcIP   string
    DstIP   string
    Protocol string
    Port    int
}

type Action struct {
    Type string // forward, drop, modify
    Args map[string]string
}

func (ctrl *SDNController) AddFlow(switchID string, flow Flow) error {
    sw, ok := ctrl.switches[switchID]
    if !ok {
        return fmt.Errorf("switch not found: %s", switchID)
    }
    
    sw.Flows = append(sw.Flows, flow)
    return nil
}

func (ctrl *SDNController) CalculateRoutes(src, dst string) []Route {
    // 最短路径算法
    return shortestPath(ctrl, src, dst)
}
```

---

## 第五部分：自测题

### 问题 1
DNS 解析慢怎么优化？

<details>
<summary>查看答案</summary>

1. **本地缓存**：systemd-resolved/dnsmasq
2. **DNS 预解析**：提前解析常用域名
3. **DoH/DoT**：加密 DNS 减少劫持
4. **多 DNS 服务器**：主备 DNS
5. **Go 实现**：自定义 Resolver

</details>

### 问题 2
IPv6 相比 IPv4 的优势？

<details>
<summary>查看答案</summary>

1. **地址空间**：340 万亿亿亿个地址
2. **简化头部**：固定长度，处理更快
3. **内置安全**：IPsec 原生支持
4. **无 NAT**：端到端通信
5. **Go 实现**：net.Listen("tcp6")

</details>

### 问题 3
SDN 相比传统网络有什么优势？

<details>
<summary>查看答案</summary>

1. **集中控制**：全局视角优化流量
2. **灵活策略**：动态调整路由
3. **可编程**：通过 API 控制网络
4. **自动化**：自动故障切换
5. **广告场景**：多机房流量调度

</details>

---

*本文档基于网络协议原理整理。*