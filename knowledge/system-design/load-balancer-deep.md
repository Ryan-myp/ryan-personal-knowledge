# 负载均衡架构深度解析

> 深入负载均衡核心：L4/L7 负载均衡、一致性哈希、会话保持、健康检查、流量调度算法。
> 适用对象：后端架构师、高并发系统开发者

---

## 1. 负载均衡层次

### 1.1 L4 vs L7 负载均衡

```
┌─────────────────────────────────────────────────────────────────┐
│                         负载均衡层次                            │
├──────────────┬──────────────────────────────────────────────────┤
│   L4 层      │  传输层（TCP/UDP）                              │
│              │  • 基于 IP + Port 转发                          │
│              │  • 不解析应用层协议                              │
│              │  • 性能高、延迟低                                │
│              │  • 典型：HAProxy (TCP模式), Nginx (stream)       │
├──────────────┼──────────────────────────────────────────────────┤
│   L7 层      │  应用层（HTTP/HTTPS）                           │
│              │  • 解析 HTTP 请求头、URL、Cookie                  │
│              │  • 支持内容路由、SSL 终止                        │
│              │  • 功能丰富但性能略低                            │
│              │  • 典型：Nginx (http), Envoy, Traefik            │
└──────────────┴──────────────────────────────────────────────────┘
```

### 1.2 性能对比

| 指标 | L4 负载均衡 | L7 负载均衡 |
|------|------------|------------|
| 延迟 | 1-5ms | 5-20ms |
| 吞吐量 | 100万+ QPS | 10万-50万 QPS |
| CPU 使用 | 低 | 中 |
| 功能 | 基础转发 | 内容路由、SSL、缓存 |
| 适用场景 | CDN、游戏、视频 | Web API、微服务 |

---

## 2. 流量调度算法

### 2.1 常见算法实现

```go
package loadbalancer

import (
    "hash/fnv"
    "sort"
)

// Server 后端服务器
type Server struct {
    Addr      string
    Weight    int
    ActiveConns int
}

// 1. 轮询 (Round Robin)
func RoundRobin(servers []Server, idx *int) *Server {
    if len(servers) == 0 {
        return nil
    }
    server := &servers[*idx % len(servers)]
    *idx = (*idx + 1) % len(servers)
    return server
}

// 2. 加权轮询 (Weighted Round Robin)
func WeightedRoundRobin(servers []Server, idx *int) *Server {
    totalWeight := 0
    for _, s := range servers {
        totalWeight += s.Weight
    }
    
    for i := 0; i < len(servers); i++ {
        *idx = (*idx + 1) % len(servers)
        current := servers[*idx]
        if current.Weight > 0 {
            current.Weight--
            servers[*idx] = current
            return &current
        }
    }
    return nil
}

// 3. 最少连接 (Least Connections)
func LeastConnections(servers []Server) *Server {
    if len(servers) == 0 {
        return nil
    }
    min := servers[0]
    for _, s := range servers[1:] {
        if s.ActiveConns < min.ActiveConns {
            min = s
        }
    }
    return min
}

// 4. 一致性哈希 (Consistent Hashing)
type ConsistentHash struct {
    hashFunc  func(string) uint32
    virtualNodes int
    ring      []uint32
    nodes     map[uint32]string
}

func NewConsistentHash(virtualNodes int) *ConsistentHash {
    return &ConsistentHash{
        hashFunc:     fnvHash,
        virtualNodes: virtualNodes,
        ring:         make([]uint32, 0),
        nodes:        make(map[uint32]string),
    }
}

func (ch *ConsistentHash) Add(node string) {
    for i := 0; i < ch.virtualNodes; i++ {
        hash := ch.hashFunc(node + strconv.Itoa(i))
        ch.ring = append(ch.ring, hash)
        ch.nodes[hash] = node
    }
    sort.Slice(ch.ring, func(i, j int) bool {
        return ch.ring[i] < ch.ring[j]
    })
}

func (ch *ConsistentHash) Get(key string) string {
    if len(ch.ring) == 0 {
        return ""
    }
    hash := ch.hashFunc(key)
    idx := sort.Search(len(ch.ring), func(i int) bool {
        return ch.ring[i] >= hash
    })
    if idx == len(ch.ring) {
        idx = 0
    }
    return ch.nodes[ch.ring[idx]]
}

func fnvHash(s string) uint32 {
    h := fnv.New32a()
    h.Write([]byte(s))
    return h.Sum32()
}
```

### 2.2 算法选择指南

| 场景 | 推荐算法 | 原因 |
|------|---------|------|
| 静态内容分发 | 轮询 | 简单高效 |
| 动态负载不均 | 最少连接 | 自动均衡 |
| 会话保持 | 一致性哈希 | 同一用户固定节点 |
| 微服务网格 | 加权轮询 | 按服务能力分配 |

---

## 3. 健康检查机制

### 3.1 检查类型

```go
type HealthCheck struct {
    Type       string        // tcp/http/https/gRPC
    Interval   time.Duration // 检查间隔
    Timeout    time.Duration // 超时时间
    Healthy    int           // 连续成功次数
    Unhealthy  int           // 连续失败次数
}

// HTTP 健康检查
func HTTPCheck(url string, timeout time.Duration) (bool, error) {
    client := &http.Client{Timeout: timeout}
    resp, err := client.Get(url)
    if err != nil {
        return false, err
    }
    defer resp.Body.Close()
    return resp.StatusCode >= 200 && resp.StatusCode < 500, nil
}

// TCP 健康检查
func TCPCheck(addr string, timeout time.Duration) (bool, error) {
    conn, err := net.DialTimeout("tcp", addr, timeout)
    if err != nil {
        return false, err
    }
    conn.Close()
    return true, nil
}
```

### 3.2 主动 vs 被动检查

```
┌─────────────────────────────────────────────────────────────────┐
│                      健康检查策略                               │
├──────────────────┬──────────────────────────────────────────────┤
│   主动检查        │  负载均衡器定期探测后端                      │
│                  │  • 优点：及时发现问题                        │
│                  │  • 缺点：额外流量开销                        │
│                  │  • 适用：关键业务                            │
├──────────────────┼──────────────────────────────────────────────┤
│   被动检查        │  基于真实请求失败判断                        │
│                  │  • 优点：零额外开销                          │
│                  │  • 缺点：发现滞后                            │
│                  │  • 适用：高吞吐场景                          │
├──────────────────┼──────────────────────────────────────────────┤
│   混合检查        │  主动 + 被动结合                            │
│                  │  • 主动检查发现节点异常                      │
│                  │  • 被动检查验证实际可用性                    │
│                  │  • 推荐生产配置                              │
└──────────────────┴──────────────────────────────────────────────┘
```

---

## 4. 会话保持

### 4.1 实现方式

```
方式1: Cookie 注入 (Cookie Insertion)
┌─────────┐     ┌──────────┐     ┌─────────┐
│  Client  │────▶│  LB      │────▶│ Server A │
└─────────┘     └──────────┘     └─────────┘
                   ↓ 写入 Cookie
              set-cookie: SERVERID=abc123

方式2: Source IP 哈希
┌─────────┐     ┌──────────┐     ┌─────────┐
│  Client  │────▶│  LB      │────▶│ Server B │
│  192.168.│     │  hash()  │     │ (固定)   │
│  .1.100  │     └──────────┘     └─────────┘
└─────────┘
```

### 4.2 Cookie 实现

```go
func HandleWithSession(w http.ResponseWriter, r *http.Request) {
    // 读取会话 Cookie
    cookie, err := r.Cookie("SESSION_ID")
    if err != nil || cookie.Value == "" {
        // 新会话，分配服务器
        server := selectServer(r.RemoteAddr)
        http.SetCookie(w, &http.Cookie{
            Name:  "SESSION_ID",
            Value: generateSessionID(),
            Path:  "/",
        })
        // 代理到对应服务器
        proxyTo(server, w, r)
        return
    }
    
    // 已有会话，路由到对应服务器
    server := getServerForSession(cookie.Value)
    proxyTo(server, w, r)
}
```

---

## 5. 高可用架构

### 5.1 Keepalived + VIP

```
┌─────────────────────────────────────────────────────────────────┐
│                     高可用负载均衡架构                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ┌──────────┐    ┌──────────┐                                  │
│   │ Master   │    │ Backup   │                                  │
│   │ LB-01    │    │ LB-02    │                                  │
│   │ (活跃)   │    │ (热备)   │                                  │
│   └────┬─────┘    └────┬─────┘                                  │
│        │               │                                       │
│   ┌────┴───────────────┴────┐                                  │
│   │      VRRP 虚拟IP         │                                  │
│   │      192.168.1.100       │                                  │
│   └────────────┬────────────┘                                  │
│                │                                               │
│   ┌────────────┴────────────┐                                  │
│   │      后端服务器集群       │                                  │
│   │  Server-01 ~ Server-N   │                                  │
│   └─────────────────────────┘                                  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 5.2 故障转移流程

```go
func MonitorHealth(masterAlive chan bool) {
    ticker := time.NewTicker(5 * time.Second)
    for range ticker.C {
        if isMasterHealthy() {
            masterAlive <- true
        } else {
            masterAlive <- false
        }
    }
}

func Failover(masterAlive chan bool) {
    for alive := range masterAlive {
        if !alive {
            // 触发故障转移
            promoteBackup()
            sendARPUpdate()
        }
    }
}
```

---

## 6. 性能优化

### 6.1 连接池管理

```go
type ConnectionPool struct {
    maxConns  int
    conns     []*net.Conn
    mu        sync.Mutex
    available chan struct{}
}

func NewConnectionPool(maxConns int) *ConnectionPool {
    return &ConnectionPool{
        maxConns:  maxConns,
        available: make(chan struct{}, maxConns),
    }
}

func (cp *ConnectionPool) Get() (*net.Conn, error) {
    select {
    case cp.available <- struct{}{}:
        // 获取连接
        conn := cp.createConnection()
        return &conn, nil
    default:
        return nil, errors.New("pool exhausted")
    }
}

func (cp *ConnectionPool) Put(conn *net.Conn) {
    <-cp.available
    conn.Close()
}
```

### 6.2 内核参数调优

```bash
# /etc/sysctl.conf
# 增加 TCP 端口范围
net.ipv4.ip_local_port_range = 1024 65535

# 启用 TCP 快速打开
net.ipv4.tcp_fastopen = 3

# 增加 backlog 队列
net.core.somaxconn = 65535
net.ipv4.tcp_max_syn_backlog = 65535

# 启用 TCP 拥塞控制优化
net.ipv4.tcp_congestion_control = bbr

# 减少 TIME_WAIT  socket 回收时间
net.ipv4.tcp_fin_timeout = 15
net.ipv4.tcp_tw_reuse = 1
```

---

## 7. 生产实践 Checklist

- [ ] 选择 L4 还是 L7 负载均衡（根据协议和需求）
- [ ] 配置健康检查（主动+被动混合）
- [ ] 设置合理的超时和重试策略
- [ ] 实现会话保持（如需状态）
- [ ] 部署高可用架构（主备/集群）
- [ ] 监控关键指标（QPS、延迟、错误率）
- [ ] 压测验证容量（目标 2-3 倍峰值）
- [ ] 制定故障演练计划

---

**参考**: Nginx 源码、HAProxy 配置指南、Envoy 架构文档
