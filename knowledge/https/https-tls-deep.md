# HTTPS/TLS 协议深度解析

> 深入 TLS 握手、加密算法、证书链验证。

---

## 1. TLS 握手流程

```
Client → Server: ClientHello (supported ciphers)
Server → Client: ServerHello + Certificate
Client → Server: ClientKeyExchange
Client → Server: ChangeCipherSpec + Finished
Server → Client: ChangeCipherSpec + Finished
```

---

## 2. 加密套件

```
TLS_AES_256_GCM_SHA384      // TLS 1.3
TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384  // TLS 1.2
ECDHE-RSA-AES128-GCM-SHA256
```

---

## 3. 证书链验证

```
Root CA → Intermediate CA → Server Certificate
```

---

## 4. 实践 Checklist
- [ ] 使用 TLS 1.2/1.3
- [ ] 禁用弱加密套件
- [ ] 配置 HSTS
- [ ] 定期更换证书

**参考**: RFC 8446、Mozilla TLS Config Generator
