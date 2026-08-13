# JWT 认证机制深度解析

> 深入 JWT 结构、签名验证、安全实践。

---

## 1. JWT 结构

```
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.  // Header
eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.  // Payload
SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c  // Signature
```

---

## 2. 签名算法

| 算法 | 安全性 | 说明 |
|------|--------|------|
| HS256 | 中 | 对称签名，需要共享密钥 |
| RS256 | 高 | 非对称签名，公钥验签 |
| ES256 | 高 | 椭圆曲线签名 |

---

## 3. 安全实践

```go
// ❌ 不安全
token, _ := jwt.Parse(tokenString, func(token *jwt.Token) (interface{}, error) {
    return []byte("secret"), nil
})

// ✅ 安全
token, _ := jwt.Parse(tokenString, func(token *jwt.Token) (interface{}, error) {
    if _, ok := token.Method.(*jwt.SigningMethodHMAC); !ok {
        return nil, fmt.Errorf("unexpected signing method: %v", token.Header["alg"])
    }
    return publicKey, nil
})
```

---

## 4. 实践 Checklist
- [ ] 使用强密钥 (≥256位)
- [ ] 设置合理的过期时间
- [ ] 不要在 Payload 存敏感信息
- [ ] 实现 Token 黑名单/撤销

**参考**: JWT 官方文档、OAuth2 规范
