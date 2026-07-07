# DNS 与安全网络深度实战

## 一、DNS 协议深度解析

### 1.1 DNS 查询流程

```
递归查询流程:
1. 客户端 → 本地 DNS 缓存 (未命中)
2. 本地 DNS → Root 服务器 (. )
3. Root → TLD 服务器 (.com)
4. TLD → 权威服务器 (example.com)
5. 权威 → 返回 A 记录 (93.184.216.34)
6. 本地 DNS → 缓存 + 返回客户端

DNS 记录类型:
├── A: IPv4 地址
├── AAAA: IPv6 地址
├── CNAME: 别名
├── MX: 邮件服务器
├── NS: 名称服务器
├── TXT: 文本记录 (SPF/DKIM/DMARC)
├── SRV: 服务定位
└── SOA: 起始授权机构
```

### 1.2 DNS 报文格式

```
DNS Header (12 bytes):
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
|                      ID                       |
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
|QR|   Opcode  |AA|TC|RD|RA|   Z    |   RCODE |
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
|                    QDCOUNT                    |
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
|                    ANCOUNT                    |
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
|                    NSCOUNT                    |
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
|                    ARCOUNT                    |
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+

Question Section:
├── QNAME: 域名 (压缩格式)
├── QTYPE: 记录类型 (1=A, 28=AAAA)
└── QCLASS: 类 (1=IN)
```

### 1.3 Go DNS 实现

```go
package dns

import (
	"context"
	"net"
	"time"
)

type DNSResolver struct {
	servers []string
	timeout time.Duration
	cache   *LRUCache
}

func NewDNSResolver() *DNSResolver {
	return &DNSResolver{
		servers: []string{
			"8.8.8.8:53",   // Google
			"1.1.1.1:53",   // Cloudflare
			"223.5.5.5:53", // AliDNS
		},
		timeout: 2 * time.Second,
		cache:   NewLRUCache(1000),
	}
}

func (r *DNSResolver) Resolve(ctx context.Context, domain string) ([]net.IP, error) {
	// 检查缓存
	if ips, ok := r.cache.Get(domain); ok {
		return ips, nil
	}
	
	// 递归查询
	for _, server := range r.servers {
		ips, err := r.queryServer(ctx, server, domain)
		if err == nil {
			r.cache.Set(domain, ips)
			return ips, nil
		}
	}
	
	return nil, fmt.Errorf("DNS resolution failed for %s", domain)
}

func (r *DNSResolver) queryServer(ctx context.Context, server, domain string) ([]net.IP, error) {
	udpConn, err := net.DialTimeout("udp", server, r.timeout)
	if err != nil {
		return nil, err
	}
	defer udpConn.Close()
	
	// 构建 DNS 请求
	msg := &dns.Msg{}
	msg.SetQuestion(dns.Fqdn(domain), dns.TypeA)
	
	// 发送请求
	if err := dnsMsg.WriteTo(udpConn); err != nil {
		return nil, err
	}
	
	// 读取响应
	reply := &dns.Msg{}
	if err := reply.ReadFrom(udpConn); err != nil {
		return nil, err
	}
	
	// 解析 A 记录
	var ips []net.IP
	for _, ans := range reply.Answer {
		if a, ok := ans.(*dns.A); ok {
			ips = append(ips, a.A)
		}
	}
	
	return ips, nil
}
```

## 二、DNSSEC 安全扩展

### 2.1 DNSSEC 签名链

```
Root Zone (KSK + ZSK)
  └── .com Zone (DS + KSK + ZSK)
        └── example.com Zone (RRSIG + DNSKEY)
              ├── A Record (RRSIG)
              ├── AAAA Record (RRSIG)
              └── CNAME Record (RRSIG)
```

### 2.2 DNS over HTTPS (DoH)

```go
// Go 1.15+ 支持 DoH
resolver := &net.Resolver{
    PreferGo: true,
    Dial: func(ctx context.Context, network, address string) (net.Conn, error) {
        // 使用 HTTPS 而非 UDP
        d := &net.Dialer{Timeout: 5 * time.Second}
        return d.DialContext(ctx, "tcp", "dns.google:443")
    },
}

ips, err := resolver.LookupIP(ctx, "ip4", "example.com")
```

## 三、SDN 软件定义网络

### 3.1 SDN 架构

```
控制平面 (Control Plane)
├── SDN Controller (OpenDaylight, ONOS)
├── 网络拓扑管理
├── 路由策略
└── 流量工程

数据平面 (Data Plane)
├── OpenFlow Switch
├── 流表匹配
└── 数据包转发

应用平面 (Application Plane)
├── 网络应用
├── 负载均衡
└── 安全策略
```

### 3.2 OpenFlow 流表

```
OpenFlow 流表匹配:
├── Ingress Port
├── Ethernet Src/Dst
├── VLAN ID
├── IP Src/Dst
├── TCP/UDP Src/Dst Port
└── Actions:
    ├── Forward to Port
    ├── Drop
    ├── Modify Field
    └── Send to Controller
```

## 四、自测题

1. DNS 递归查询的完整流程是怎样的？
2. DNSSEC 如何防止 DNS 欺骗？
3. SDN 的控制平面和数据平面如何分离？

## 五、动手验证

```bash
# 1. 使用 dig/nslookup 分析 DNS 查询
# 2. 配置 DNSSEC 验证
# 3. 测试 DoH/DoT
# 4. 使用 Wireshark 分析 SDN 流量
```
