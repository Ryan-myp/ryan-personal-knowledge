# 网络安全架构深度解析

> 深入网络安全：TLS/SSL、WAF、DDoS防护、零信任架构。
> 包含真实安全架构设计和攻击防御策略。
> 适用对象：安全工程师、架构师、后端工程师

---

## 1. TLS/SSL 协议

### 1.1 握手流程

```
TLS 1.3 握手流程：

1. Client Hello
   ├── 支持的 TLS 版本
   ├── 随机数
   └── 支持的 cipher suite

2. Server Hello
   ├── 选择的 cipher suite
   ├── 随机数
   └── 服务器证书

3. Key Exchange
   └── 密钥协商 (ECDHE)

4. Finished
   └── 验证握手完整性
```

### 1.2 Go 实现 TLS Server

```go
// tls_server.go

package main

import (
    "crypto/tls"
    "net/http"
)

func main() {
    // 配置 TLS
    config := &tls.Config{
        MinVersion: tls.VersionTLS12,
        CipherSuites: []uint16{
            tls.TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384,
            tls.TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256,
        },
    }
    
    mux := http.NewServeMux()
    mux.HandleFunc("/", handler)
    
    server := &http.Server{
        Addr:      ":443",
        Handler:   mux,
        TLSConfig: config,
    }
    
    server.ListenTLS("", "cert.pem", "key.pem")
}
```

---

## 2. WAF 架构

### 2.1 防护规则

```
WAF 防护规则：

1. SQL 注入防护
   ├── SELECT/INSERT/UPDATE/DELETE 关键字过滤
   ├── OR 1=1 等常见注入模式
   └── 预编译语句推荐

2. XSS 防护
   ├── <script> 标签过滤
   ├── onerror/onload 事件过滤
   └── HTML 实体编码

3. CC 防护
   ├── 请求频率限制
   ├── 浏览器验证
   └── 人机验证
```

### 2.2 Go 实现 WAF

```go
// waf.go

package waf

import (
    "regexp"
    "strings"
)

type WAF struct {
    sqlPatterns []*regexp.Regexp
    xssPatterns []*regexp.Regexp
}

func NewWAF() *WAF {
    return &WAF{
        sqlPatterns: []*regexp.Regexp{
            regexp.MustCompile(`(?i)(select|insert|update|delete|drop|union)\s`),
            regexp.MustCompile(`(?i)(or|and)\s+\d+=\d+`),
        },
        xssPatterns: []*regexp.Regexp{
            regexp.MustCompile(`(?i)<script.*?>`),
            regexp.MustCompile(`(?i)on(error|load|click)\s*=`),
        },
    }
}

func (w *WAF) Check(request string) bool {
    // 检查 SQL 注入
    for _, pattern := range w.sqlPatterns {
        if pattern.MatchString(request) {
            return false
        }
    }
    
    // 检查 XSS
    for _, pattern := range w.xssPatterns {
        if pattern.MatchString(request) {
            return false
        }
    }
    
    return true
}
```

---

## 3. DDoS 防护

### 3.1 攻击类型

```
DDoS 攻击类型：

1. 流量型攻击
   ├── SYN Flood
   ├── UDP Flood
   └── ICMP Flood

2. 应用层攻击
   ├── HTTP Flood
   ├── Slowloris
   └── GET/POST 洪水

3. 协议漏洞攻击
   ├── NTP Amplification
   ├── DNS Amplification
   └── Memcached Amplification
```

### 3.2 防护策略

```
DDoS 防护策略：

1. 流量清洗
   ├── 异常流量识别
   ├── 流量牵引
   └── 清洗后回源

2. 速率限制
   ├── IP 级别限流
   ├── 请求级别限流
   └── 连接级别限流

3. 黑洞路由
   └── 攻击流量丢弃
```

---

## 4. 零信任架构

### 4.1 核心原则

```
零信任架构原则：

1. 永不信任，始终验证
   ├── 每次访问都需要验证
   └── 不依赖网络位置

2. 最小权限
   ├── 按需授权
   └── 及时回收

3. 持续验证
   ├── 动态评估风险
   └── 实时调整策略
```

### 4.2 架构设计

```
零信任架构：

┌─────────────────────────────────────────────────────────────┐
│                    零信任架构                                │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  用户身份 (Identity)                                         │
│  ├── 多因素认证 (MFA)                                       │
│  └── 持续身份验证                                            │
│                                                             │
│  设备信任 (Device)                                           │
│  ├── 设备健康检查                                            │
│  └── 设备身份认证                                            │
│                                                             │
│  网络信任 (Network)                                          │
│  ├── 微隔离                                                  │
│  └── 加密通信                                                │
│                                                             │
│  应用信任 (Application)                                      │
│  ├── 应用认证                                                │
│  └── 持续监控                                                │
│                                                             │
│  策略引擎 (Policy Engine)                                    │
│  ├── 动态策略决策                                            │
│  └── 风险评分                                                │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 5. 安全实践

### 5.1 代码安全

```go
// 安全的密码存储
import "golang.org/x/crypto/bcrypt"

func HashPassword(password string) (string, error) {
    bytes, err := bcrypt.GenerateFromPassword([]byte(password), 14)
    return string(bytes), err
}

func CheckPassword(password, hash string) bool {
    err := bcrypt.CompareHashAndPassword([]byte(hash), []byte(password))
    return err == nil
}
```

### 5.2 安全配置

```
安全配置清单：

1. HTTP 头
   ├── Strict-Transport-Security
   ├── X-Content-Type-Options
   ├── X-Frame-Options
   └── Content-Security-Policy

2. 认证
   ├── JWT 使用 RS256
   ├── 设置合理的过期时间
   └── 安全存储密钥

3. 输入验证
   ├── 服务端验证
   ├── 参数化查询
   └── 输出编码
```

---

## 6. 安全监控

### 6.1 日志审计

```
安全日志字段：

├── 时间戳
├── 源 IP
├── 用户 ID
├── 操作类型
├── 目标资源
├── 操作结果
└── 用户代理
```

### 6.2 告警规则

```
告警规则：

1. 登录异常
   ├── 多次失败登录
   ├── 异地登录
   └── 非常用设备

2. 权限异常
   ├── 越权访问
   ├── 特权提升
   └── 异常数据访问

3. 流量异常
   ├── DDoS 攻击
   ├── 爬虫行为
   └── 异常请求模式
```

---

## 7. 总结

### 7.1 核心原理回顾

| 模块 | 核心机制 |
|------|----------|
| TLS | 非对称加密 + 对称加密 |
| WAF | 规则匹配 + 行为分析 |
| DDoS防护 | 流量清洗 + 速率限制 |
| 零信任 | 持续验证 + 最小权限 |

### 7.2 最佳实践

- [ ] 启用 TLS 1.3
- [ ] 实施 WAF 防护
- [ ] 配置 DDoS 防护
- [ ] 零信任架构设计
- [ ] 持续安全监控

---

*最后更新：2026-08-11*
*作者：Ryan*
