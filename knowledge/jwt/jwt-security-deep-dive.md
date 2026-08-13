# JWT 安全深度解析

> 深入 JWT 实现、安全最佳实践、常见攻击与防御。

---

## 1. JWT 结构

```
┌─────────────────────────────────────────────────────────────┐
│                        JWT Token                            │
├───────────────┬───────────────┬───────────────┤
│   Header      │    Payload    │    Signature  │
│  (base64)     │   (base64)    │   (base64)    │
├───────────────┼───────────────┼───────────────┤
│ {                                             │
│   "alg": "HS256",                            │
│   "typ": "JWT"                               │
│ }                                             │
├───────────────┼───────────────┼───────────────┤
│ {                                             │
│   "sub": "1234567890",                       │
│   "name": "John Doe",                        │
│   "iat": 1516239022                          │
│ }                                             │
├───────────────┴───────────────┴───────────────┤
│ HMACSHA256(                                    │
│   base64UrlEncode(header) + "." +              │
│   base64UrlEncode(payload),                    │
│   secret                                      │
│ )                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Go 实现

```go
import "github.com/golang-jwt/jwt/v5"

// 生成 Token
token := jwt.NewWithClaims(jwt.SigningMethodHS256, jwt.MapClaims{
    "sub":  userId,
    "name": userName,
    "iat":  time.Now().Unix(),
})
tokenString, err := token.SignedString([]byte(secret))

// 验证 Token
token, err := jwt.Parse(tokenString, func(token *jwt.Token) (interface{}, error) {
    return []byte(secret), nil
})
```

---

## 3. 安全最佳实践

| 实践 | 说明 | 重要性 |
|------|------|--------|
| 使用强密钥 | 至少 256 位 | 🔴 高 |
| 设置过期时间 | 短期有效 | 🔴 高 |
| 验证签名 | 防止篡改 | 🔴 高 |
| 不要存储敏感信息 | Payload 可解码 | 🟡 中 |
| 使用 HTTPS | 防止中间人攻击 | 🔴 高 |

---

## 4. 常见攻击与防御

| 攻击类型 | 防御措施 |
|----------|----------|
| 算法混淆 | 明确指定算法，拒绝 None |
| 弱密钥破解 | 使用强密钥，定期轮换 |
| 重放攻击 | 添加 nonce 或使用短期 Token |
| 信息泄露 | 不在 Payload 存储敏感数据 |

---

**参考**: JWT 官方规范、OWASP 认证欺骗防御
