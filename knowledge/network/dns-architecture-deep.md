# DNS 系统架构深度解析：从递归查询到 DoH/DoT

> 来源：RFC 1034/1035 / RFC 7858 (DoT) / RFC 8484 (DoH) / 《DNS and BIND》
> 蒸馏日期：2026-07-10
> 板块：network | 深度等级：🟢

---

## 一、入门引导：DNS 是什么？

### 1.1 生活类比

DNS = **电话簿 + 邮局 + 翻译官**的组合体：

```
你: "我要访问 weread.qq.com"
     ↓
DNS 递归服务器: "让我查查..."
     ↓
根服务器(.): "com 归 .com 权威管"
     ↓
.com 权威: "weread 归 weread.qq.com 权威管"
     ↓
weread.qq.com 权威: "IP 是 103.235.46.39"
     ↓
返回给你: "103.235.46.39"
```

### 1.2 为什么 DNS 这么重要？

| 维度 | 影响 |
|------|------|
| 性能 | DNS 查询延迟直接增加页面加载时间（通常 20-200ms） |
| 可用性 | DNS 挂了 = 整个互联网不可用 |
| 安全 | DNS 劫持、缓存投毒是常见攻击面 |
| 调度 | CDN 通过 DNS GSLB 将用户导向最近的节点 |

---

## 二、DNS 层次结构

### 2.1 四层架构

```
                    ┌──────────────────────┐
                    │   本地 DNS 缓存       │  (浏览器/OS/resolver)
                    │   TTL: 最短 TTL       │
                    └──────────┬───────────┘
                               │ 递归查询
                               ▼
                    ┌──────────────────────┐
                    │  DNS 递归服务器       │  (ISP/公共: 8.8.8.8, 1.1.1.1)
                    │  缓存: 几分钟~几天    │
                    └──────────┬───────────┘
                               │ 迭代查询
                               ▼
              ┌────────────────┼────────────────┐
              ▼                ▼                ▼
        ┌──────────┐   ┌──────────────┐  ┌──────────────┐
        │  根服务器  │   │  .com 权威    │  │ .cn 权威      │
        │  13 台    │   │  Verisign    │  │ CNNIC        │
        │  a-m.ns  │   │  weread.qq.com│  │              │
        └──────────┘   └──────┬───────┘  └──────────────┘
                              │
                      ┌───────▼───────┐
                      │ weread.qq.com │
                      │ 权威服务器     │
                      │ A: 103.235.46.39│
                      │ AAAA: 240e::1  │
                      │ CNAME: cdn.weread.com │
                      └───────────────┘
```

### 2.2 根服务器详解

全球只有 **13 个 IP 地址**的根服务器（但实际有数百个 Anycast 镜像）：

| 名称 | 运营商 | 区域 |
|------|--------|------|
| A.ROOT-SERVERS.NET | University of Southern California | 全球 |
| B.ROOT-SERVERS.NET | Leland Stanford Jr. University | 全球 |
| ... | ... | ... |
| M.ROOT-SERVERS.NET | RIPE NCC / Sony | 欧洲/亚洲 |

**Anycast 部署**：每个根 IP 在全球有数百个镜像，BGP 路由将用户导向最近的镜像。

---

## 三、DNS 查询流程深度解析

### 3.1 完整递归查询流程（含缓存）

```
客户端 (192.168.1.100) 要访问 weread.qq.com

Step 1: 检查本地缓存 (浏览器/OS)
  → 有且未过期? 返回 ✅
  → 没有/过期? → Step 2

Step 2: 向配置的递归服务器发送查询
  192.168.1.100 → 8.8.8.8 (Google DNS)
  Query: A weread.qq.com IN
  
Step 3: 递归服务器检查自身缓存
  → 有且未过期? 返回 ✅
  → 没有/过期? → Step 4

Step 4: 递归服务器发起迭代查询

  4a. 查询根服务器 (a.root-servers.net: 198.41.0.4)
      Query: A weread.qq.com IN
      Response: NS .com → 192.5.6.30, 192.33.14.30, ...
      
  4b. 查询 .com 权威 (192.5.6.30)
      Query: A weread.qq.com IN
      Response: NS weread.qq.com → 10.0.1.1, 10.0.1.2
      
  4c. 查询 weread.qq.com 权威 (10.0.1.1)
      Query: A weread.qq.com IN
      Response: 103.235.46.39

Step 5: 递归服务器缓存结果并返回给客户端
  Cache: weread.qq.com → 103.235.46.39, TTL=300s
  Response: 103.235.46.39
```

### 3.2 逐行源码解析：递归服务器实现

```go
// 简化版 DNS 递归服务器核心逻辑
type RecursiveResolver struct {
    cache       *DNSCache          // 缓存层
    rootServers []net.IP           // 根服务器列表
    forwarders  []string           // 上游转发器
    tcpTimeout  time.Duration      // TCP 超时
}

// Resolve: 递归查询入口
func (r *RecursiveResolver) Resolve(hostname string, qType uint16) (*DNSResponse, error) {
    // 1. 查缓存
    cached := r.cache.Get(hostname, qType)
    if cached != nil {
        return cached, nil
    }
    
    // 2. 迭代查询
    resp, err := r.iterativeQuery(hostname, qType, nil)
    if err != nil {
        return nil, err
    }
    
    // 3. 缓存结果
    r.cache.Set(resp)
    return resp, nil
}

// iterativeQuery: 迭代查询核心
func (r *RecursiveResolver) iterativeQuery(
    hostname string, 
    qType uint16, 
    previousNS []net.IP,
) (*DNSResponse, error) {
    
    // 尝试 TCP（超过 512 字节或 TC 标志时）
    // DNS 默认 UDP，但 EDNS0 允许更大消息
    conn, err := r.connectDNSServer(previousNS)
    if err != nil {
        // 回退到根服务器
        conn, err = r.connectDNSServer(r.rootServers)
        if err != nil {
            return nil, fmt.Errorf("cannot connect to root: %w", err)
        }
    }
    defer conn.Close()
    
    // 构造查询
    msg := &dns.Msg{}
    msg.SetQuestion(dns.Fqdn(hostname), qType)
    msg.RecursionDesired = false  // 迭代查询
    
    // 发送查询
    conn.SetWriteDeadline(time.Now().Add(r.tcpTimeout))
    if err := conn.WriteMsg(msg); err != nil {
        return nil, err
    }
    
    // 接收响应
    conn.SetReadDeadline(time.Now().Add(r.tcpTimeout))
    resp, err := conn.ReadMsg()
    if err != nil {
        return nil, err
    }
    
    // 处理响应
    if resp.Rcode == dns.RcodeSuccess {
        // 检查是否需要继续迭代（Referral）
        if len(resp.Ns) > 0 {
            // 这是中间引用，继续向下查询
            nextNS := extractNSAddresses(resp.Ns)
            return r.iterativeQuery(hostname, qType, nextNS)
        }
        // 最终答案
        return &DNSResponse{Answers: resp.Answer, TTL: resp.Expire()}, nil
    }
    
    return nil, fmt.Errorf("DNS error: %s", dns.RcodeToString[resp.Rcode])
}

// connectDNSServer: 智能选择 DNS 服务器
func (r *RecursiveResolver) connectDNSServer(servers []net.IP) (*dns.Conn, error) {
    // 优先使用 UDP（更快）
    for _, server := range servers {
        addr := net.UDPAddr{IP: server, Port: 53}
        conn, err := dns.DialUDP("udp", nil, &addr)
        if err == nil {
            return conn, nil
        }
    }
    // UDP 失败，回退 TCP
    for _, server := range servers {
        addr := net.TCPAddr{IP: server, Port: 53}
        conn, err := dns.Dial("tcp", &addr)
        if err == nil {
            return conn, nil
        }
    }
    return nil, fmt.Errorf("all DNS servers unreachable")
}
```

---

## 四、DNS 记录类型深度解析

### 4.1 核心记录类型

| 类型 | 说明 | 示例 | 用途 |
|------|------|------|------|
| A | IPv4 地址 | `weread.qq.com. 300 IN A 103.235.46.39` | 基础域名解析 |
| AAAA | IPv6 地址 | `weread.qq.com. 300 IN AAAA 240e:xx::1` | IPv6 双栈 |
| CNAME | 别名 | `cdn.weread.com. 300 IN CNAME weread.qq.com.` | CDN/负载均衡 |
| MX | 邮件交换 | `qq.com. 3600 IN MX 10 mx1.qq.com.` | 邮件路由 |
| TXT | 文本记录 | `_dmarc.qq.com. 3600 IN TXT "v=DMARC1;..."` | SPF/DMARC/DKIM |
| NS | 名称服务器 | `qq.com. 86400 IN NS ns1.qq.com.` | 域授权 |
| SOA | 起始授权 | `qq.com. 86400 IN SOA ns1.qq.com. admin.qq.com. ...` | 区域管理 |
| SRV | 服务定位 | `_http._tcp.example.com. 3600 IN SRV 10 60 80 server.example.com.` | 服务发现 |

### 4.2 CNAME 链与性能影响

```
user → www.example.com (CNAME) → cdn.example.com (CNAME) → edge.cloudflare.com (A)
                                    ↓                        ↓
                              第 1 次查询               第 2 次查询
```

**问题**：每个 CNAME 都需要一次额外的 DNS 查询！

**优化方案**：
```go
// 预解析 CNAME 链
type DNSPreResolver struct {
    client *dns.Client
}

// ResolveChain: 一次性解析完整的 CNAME 链
func (p *DNSPreResolver) ResolveChain(hostname string) ([]net.IP, error) {
    var ips []net.IP
    visited := make(map[string]bool)
    current := hostname
    
    for !isIP(current) {
        if visited[current] {
            return nil, fmt.Errorf("CNAME loop detected: %s", current)
        }
        visited[current] = true
        
        resp, err := p.client.Exchange(
            p.makeQuery(current, dns.TypeA),
            "8.8.8.8:53",
        )
        if err != nil {
            return nil, err
        }
        
        for _, ans := range resp.Answer {
            switch v := ans.(type) {
            case *dns.CNAME:
                current = v.Target
            case *dns.A:
                ips = append(ips, v.A)
            case *dns.AAAA:
                ips = append(ips, v.AAAA...)
            }
        }
    }
    return ips, nil
}
```

---

## 五、高级 DNS 特性

### 5.1 EDNS0（扩展 DNS）

**问题**：原始 DNS 限制消息 512 字节，现代 DNS 响应远超此值。

**EDNS0 解决方案**：
```
传统 DNS:  [Header][Question][Answer]  ← 最大 512 字节
EDNS0 DNS: [Header][Question][Answer][OPT]  ← OPT 伪记录声明缓冲区大小

OPT 记录格式:
┌─────────────┬──────┬──────┬──────┬────────┬────────┐
│ CODE (0)    │ TYPE │ CLASS│ TTL  │ RDLEN  │ DATA   │
│ 伪记录      │ 41   │ 0    │ 版本  │ 数据长度│ 选项   │
└─────────────┴──────┴──────┴──────┴────────┴────────┘

UDP 缓冲区大小: 4096 字节（标准推荐）
```

### 5.2 DNSSEC（域名系统安全扩展）

```
签名链:
根区(.).DNSKEY
  └── .DS
       └── com..DNSKEY
            └── com..DS
                 └── qq.com..DNSKEY
                      └── qq.com..RRSIG(A)
                           └── weread.qq.com..A (带 RRSIG 签名)
```

**验证流程**：
```go
// DNSSEC 验证核心逻辑
type DNSSECVerifier struct {
    trustAnchor map[string]*dns.DNSKEY  // 根信任锚
}

func (v *DNSSECVerifier) Verify(response *dns.Msg, domain string) error {
    // 1. 找到 RRSIG 记录
    sigs := response.Extra
    for _, rr := range sigs {
        if sig, ok := rr.(*dns.RRSIG); ok && sig.Labels == countLabels(domain) {
            // 2. 用 DNSKEY 验证签名
            key := v.findKey(domain, sig.KeyTag)
            if key == nil {
                return fmt.Errorf("no matching DNSKEY for tag %d", sig.KeyTag)
            }
            
            // 3. 密码学校验
            pubKey := key.PublicKey()
            if !verifySignature(pubKey, sig, response) {
                return fmt.Errorf("DNSSEC validation failed for %s", domain)
            }
            
            // 4. 检查签名有效期
            if time.Now().Before(sig.Inception) || time.Now().After(sig.Expiration) {
                return fmt.Errorf("signature expired for %s", domain)
            }
            
            return nil
        }
    }
    return fmt.Errorf("no RRSIG found for %s", domain)
}
```

### 5.3 DoT（DNS over TLS）和 DoH（DNS over HTTPS）

```
传统 DNS:    客户端 ──UDP──► 递归服务器 (明文!)
             192.168.1.100 ──► 8.8.8.8:53

DoT:         客户端 ──TLS──► 递归服务器 (加密)
             192.168.1.100 ──► 8.8.8.8:853

DoH:         客户端 ──HTTPS──► 递归服务器 (加密)
             192.168.1.100 ──► https://8.8.8.8/dns-query
```

**DoT vs DoH 对比**：

| 特性 | DoT (RFC 7858) | DoH (RFC 8484) |
|------|---------------|----------------|
| 端口 | 853 | 443 |
| 协议 | TLS over TCP | HTTPS (HTTP/2) |
| 穿透防火墙 | 可能被阻断 | 难检测（混在 HTTPS 流量中） |
| 缓存友好 | 独立连接 | 可利用 HTTP 缓存 |
| 隐私 | 加密传输 | 加密 + 难被 DPI 识别 |

```go
// DoH 客户端实现
type DoHClient struct {
    client  *http.Client
    baseURL string
}

func NewDoHClient(baseURL string) *DoHClient {
    return &DoHClient{
        client: &http.Client{
            Timeout: 5 * time.Second,
            Transport: &http.Transport{
                TLSClientConfig: &tls.Config{
                    MinVersion: tls.VersionTLS13,  // 强制 TLS 1.3
                },
            },
        },
        baseURL: baseURL,
    }
}

// Query: 发送 DoH 查询
func (c *DoHClient) Query(hostname string) ([]net.IP, error) {
    // 构造 DNS-over-HTTPS 请求
    reqBody := c.buildDNSMessage(hostname)
    
    resp, err := c.client.Post(
        c.baseURL+"/dns-query",
        "application/dns-message",
        bytes.NewReader(reqBody),
    )
    if err != nil {
        return nil, err
    }
    defer resp.Body.Close()
    
    // 解码响应
    respBody, _ := io.ReadAll(resp.Body)
    msg := &dns.Msg{}
    if err := msg.Unpack(respBody); err != nil {
        return nil, err
    }
    
    // 提取 IP
    var ips []net.IP
    for _, ans := range msg.Answer {
        if a, ok := ans.(*dns.A); ok {
            ips = append(ips, a.A)
        } else if aaaa, ok := ans.(*dns.AAAA); ok {
            ips = append(ips, aaaa.AAAA...)
        }
    }
    return ips, nil
}
```

---

## 六、生产排障案例

### 6.1 案例：DNS 缓存污染导致部分用户无法访问

**现象**：某地区用户访问 weread.qq.com 被解析到错误 IP。

**排查**：
```bash
# 1. 检查本地 DNS 缓存
$ dig @127.0.0.1 weread.qq.com +short
103.235.46.39

# 2. 检查不同递归服务器的结果
$ dig @8.8.8.8 weread.qq.com +short
103.235.46.39
$ dig @1.1.1.1 weread.qq.com +short
103.235.46.39

# 3. 检查 ISP DNS
$ dig @isp-dns weread.qq.com +short
192.168.1.100  ← 异常！

# 4. 检查 TTL
$ dig weread.qq.com +ttl
;; ANSWER SECTION:
weread.qq.com.  300  IN  A  103.235.46.39
```

**根因**：ISP DNS 缓存了旧的 A 记录，且 TTL 设置不合理。

**解决**：
```bash
# 应用层面：使用 DoH 绕过 ISP DNS
export RES_OPTIONS="options edns0 ndots:2"
# 或使用 cloudflared / doh-proxy

# 运维层面：调整 TTL 策略
# 常规记录: TTL = 300s (5 分钟)
# 变更频繁的记录: TTL = 60s (1 分钟)
# 稳定记录: TTL = 3600s (1 小时)
```

### 6.2 案例：DNS 查询超时优化

```go
// DNS 查询超时优化配置
type DNSConfig struct {
    Servers      []string       // DNS 服务器列表
    Timeout      time.Duration  // 单次查询超时
    Retry        int            // 重试次数
    Parallel     bool           // 并行查询多个 DNS
    SearchDomain []string       // 搜索域
}

func NewOptimizedDNS(cfg DNSConfig) *Resolver {
    return &Resolver{
        servers: cfg.Servers,
        timeout: cfg.Timeout,
        retry:   cfg.Retry,
        parallel: cfg.Parallel,
    }
}

// ParallelResolve: 并行查询多个 DNS 服务器
func (r *Resolver) ParallelResolve(hostname string) (*DNSResponse, error) {
    ctx, cancel := context.WithTimeout(context.Background(), r.timeout)
    defer cancel()
    
    type result struct {
        resp *DNSResponse
        err  error
        srv  string
    }
    
    ch := make(chan result, len(r.servers))
    
    for _, srv := range r.servers {
        go func(server string) {
            resp, err := r.querySingle(server, hostname)
            ch <- result{resp, err, server}
        }(srv)
    }
    
    // 取第一个成功的响应
    for i := 0; i < len(r.servers); i++ {
        select {
        case res := <-ch:
            if res.err == nil {
                return res.resp, nil
            }
        case <-ctx.Done():
            return nil, ctx.Err()
        }
    }
    
    return nil, fmt.Errorf("all DNS servers failed")
}
```

---

## 七、Trade-off 分析

### 7.1 DNS 架构选择

| 场景 | 推荐方案 | 理由 |
|------|---------|------|
| 内部服务发现 | CoreDNS + Kubernetes | 自动注册/注销 |
| 公网域名 | 云厂商 DNS + DNSSEC | 高可用 + 安全 |
| 隐私保护 | DoH/DoT | 加密查询 |
| 低延迟 | 本地递归 + 大缓存 | 减少迭代查询 |
| CDN 调度 | GSLB (全局服务器负载均衡) | 基于地理位置/负载调度 |

### 7.2 TTL 调优策略

```
TTL 短 (< 60s)    → 快速生效，但查询量大，缓存命中率低
TTL 长 (> 3600s)  → 缓存命中高，但故障切换慢

广告技术推荐:
- CDN 边缘: TTL = 60s (快速故障切换)
- 核心服务: TTL = 300s (平衡)
- 静态资源: TTL = 3600s+ (CDN 缓存)
```

---

## 八、自测题

### Q1：为什么 DNS 根服务器只有 13 个 IP，却能支撑全球数十亿查询？

**答**：每个根 IP 通过 Anycast 部署在全球数百个物理服务器上。BGP 路由将用户请求导向最近的镜像。加上递归服务器的大规模缓存（TTL 机制），绝大多数查询在递归层就解决了，不会到达根服务器。

### Q2：DoH 相比 DoT 有什么优势？

**答**：DoH 使用 HTTPS（443 端口），能更好地穿透防火墙和 DPI（深度包检测）。同时可以利用 HTTP/2 的多路复用、HTTP 缓存等机制。但 DoH 的问题是难以区分普通 HTTPS 流量和 DNS 流量，增加了运营商管理网络的难度。

### Q3：DNSSEC 如何防止缓存投毒攻击？

**答**：DNSSEC 为每条 DNS 记录提供数字签名。递归服务器收到响应后，会用 DNSKEY 验证签名。如果攻击者篡改了响应（如将 IP 改为恶意地址），签名验证会失败，递归服务器会丢弃该响应。

---

## 九、与知识库的对照

### 已有内容
- `network/tls-ssl-deep.md` — TLS 协议（DoT/DoH 的基础）
- `network/tcp-congestion-control-deep.md` — 本文件刚创建

### 补充内容
- 本文档填补了 DNS 系统的系统性知识空白
- 涵盖从基础查询到高级特性（DNSSEC/DoH/EDNS0）
- 生产排障案例直接关联广告系统的 CDN 调度问题

### 缺失内容（后续可扩展）
- DNS 负载均衡与 GSLB 深度
- CoreDNS 插件系统开发
- DNS-over-TLS 证书管理
- DNS 隐私保护最佳实践
