# HTTPS 安全深度解析

> TLS 协议原理、证书管理、常见攻击与防御。

---

## 1. TLS 握手流程

```
Client                          Server
  │                               │
  │─── ClientHello ─────────────▶│  (支持的密码套件、随机数)
  │◀──── ServerHello ─────────────│  (选择的密码套件、证书)
  │                               │
  │─── ClientKeyExchange ────────▶│  (客户端密钥交换)
  │─── ChangeCipherSpec ─────────▶│
  │─── Finished ─────────────────▶│  (握手完成)
  │◀──── ChangeCipherSpec ─────────│
  │◀──── Finished ─────────────────│
  │                               │
  │◀═══════════ 加密通信 ══════════▶│
```

---

## 2. Go 实现

```go
import "crypto/tls"

// 配置 TLS
config := &tls.Config{
    MinVersion: tls.VersionTLS12,
    CipherSuites: []uint16{
        tls.TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384,
        tls.TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256,
    },
}

// 建立连接
conn, err := tls.Dial("tcp", "example.com:443", config)
defer conn.Close()
```

---

## 3. 安全实践

| 实践 | 说明 | 重要性 |
|------|------|--------|
| 启用 TLS 1.2+ | 禁用 SSLv3/TLS 1.0 | 🔴 高 |
| 使用强密码套件 | 优先 GCM/AEAD | 🔴 高 |
| HSTS 头部 | 强制 HTTPS | 🟡 中 |
| 证书透明 | 检测异常证书 | 🟡 中 |
| OCSP Stapling | 加速证书验证 | 🟢 低 |

---

## 4. 常见攻击

| 攻击 | 防御 |
|------|------|
| POODLE | 禁用 SSLv3 |
| BEAST | 使用 TLS 1.1+ |
| Heartbleed | 更新 OpenSSL |
| DROWN | 禁用 SSLv2 |
| 中间人攻击 | 证书锁定 |

---

**参考**: TLS 官方规范、Mozilla SSL 配置生成器
