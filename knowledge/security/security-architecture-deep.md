# 安全架构深度：零信任/微隔离/密钥管理

> 逐行源码解析 + 生产排障案例 + 对比分析 + 动手验证

---

## 第一部分：入门引导（5 分钟速览）

### 类比理解安全架构

```
传统安全 = 城堡防御
  → 城墙很高（防火墙）
  → 但城内部随意走动（横向移动）
  → 一旦被攻破，全盘皆输

零信任 = 每间房都有锁
  → 不信任任何人，即使在内网
  → 每次访问都要验证
  → 最小权限原则
```

### 安全架构核心原则

```
1. 零信任（Zero Trust）：永不信任，始终验证
2. 最小权限（Least Privilege）：只给必要的权限
3. 纵深防御（Defense in Depth）：多层防护
4. 安全左移（Shift Left）：早期发现安全问题
5. 可观测性（Security Observability）：实时监控
```

---

## 第二部分：零信任架构

### 2.1 零信任核心组件

```
零信任架构 = 身份 + 设备 + 策略 + 持续验证

1. 身份认证（Authentication）
   → MFA、SSO、生物识别

2. 设备信任（Device Trust）
   → 设备健康检查、证书绑定

3. 策略引擎（Policy Engine）
   → ABAC/RBAC、动态授权

4. 持续监控（Continuous Monitoring）
   → UEBA、SIEM、SOAR
```

### 2.2 Go 实现零信任网关

```go
package zerotrust

import (
    "context"
    "crypto/tls"
    "fmt"
    "time"
)

// ZeroTrustGateway 零信任网关
type ZeroTrustGateway struct {
    identityProvider *IdentityProvider
    policyEngine     *PolicyEngine
    deviceTrust      *DeviceTrust
    sessionManager   *SessionManager
}

// AccessRequest 访问请求
type AccessRequest struct {
    UserID     string
    DeviceID   string
    Resource   string
    Action     string // read/write/exec
    Timestamp  time.Time
    Context    map[string]interface{}
}

// AccessDecision 访问决策
type AccessDecision struct {
    Allowed  bool
    Reason   string
    SessionID string
    TTL      time.Duration
}

// Evaluate 评估访问请求
func (g *ZeroTrustGateway) Evaluate(ctx context.Context, req AccessRequest) (*AccessDecision, error) {
    // 1. 验证身份
    identity, err := g.identityProvider.Verify(ctx, req.UserID)
    if err != nil {
        return &AccessDecision{
            Allowed: false,
            Reason:  fmt.Sprintf("identity verification failed: %v", err),
        }, nil
    }
    
    // 2. 验证设备
    deviceHealthy, err := g.deviceTrust.Check(ctx, req.DeviceID)
    if err != nil || !deviceHealthy {
        return &AccessDecision{
            Allowed: false,
            Reason:  fmt.Sprintf("device trust check failed: %v", err),
        }, nil
    }
    
    // 3. 策略评估
    decision, err := g.policyEngine.Evaluate(ctx, identity, req.Resource, req.Action)
    if err != nil {
        return &AccessDecision{
            Allowed: false,
            Reason:  fmt.Sprintf("policy evaluation failed: %v", err),
        }, nil
    }
    
    if !decision.Allowed {
        return decision, nil
    }
    
    // 4. 创建会话
    session, err := g.sessionManager.Create(ctx, identity.ID, decision.TTL)
    if err != nil {
        return &AccessDecision{
            Allowed: false,
            Reason:  fmt.Sprintf("session creation failed: %v", err),
        }, nil
    }
    
    return &AccessDecision{
        Allowed:   true,
        SessionID: session.ID,
        TTL:       session.TTL,
    }, nil
}

// IdentityProvider 身份提供商
type IdentityProvider struct {
    jwtVerifier *JWTVerifier
    mfaChecker  *MFAChecker
}

// Verify 验证身份
func (ip *IdentityProvider) Verify(ctx context.Context, userID string) (*Identity, error) {
    // 1. JWT 验证
    token, err := ip.getJWT(ctx, userID)
    if err != nil {
        return nil, err
    }
    
    if !ip.jwtVerifier.Verify(token) {
        return nil, fmt.Errorf("invalid JWT")
    }
    
    // 2. MFA 验证
    if !ip.mfaChecker.Check(ctx, userID) {
        return nil, fmt.Errorf("MFA verification failed")
    }
    
    return &Identity{
        ID:    userID,
        Token: token,
    }, nil
}

// PolicyEngine 策略引擎
type PolicyEngine struct {
    rules []PolicyRule
}

type PolicyRule struct {
    Resource string
    Action   string
    Condition func(context.Context, *Identity, map[string]interface{}) bool
    Decision bool
}

func (pe *PolicyEngine) Evaluate(ctx context.Context, identity *Identity, resource, action string) (*AccessDecision, error) {
    for _, rule := range pe.rules {
        if rule.Resource == resource && rule.Action == action {
            if rule.Condition(ctx, identity, nil) {
                return &AccessDecision{Allowed: true, TTL: 1 * time.Hour}, nil
            }
            return &AccessDecision{Allowed: false, Reason: "policy denied"}, nil
        }
    }
    
    return &AccessDecision{Allowed: false, Reason: "no matching policy"}, nil
}
```

---

## 第三部分：mTLS 深度

### 3.1 mTLS 原理

```
TLS（单向认证）：
Client → Server（验证 Server 证书）

mTLS（双向认证）：
Client → Server（验证双方证书）

优势：
1. 双向验证，防止中间人攻击
2. 证书代替密码，更安全
3. 适合微服务间通信
```

### 3.2 Go 实现 mTLS

```go
package mtls

import (
    "crypto/tls"
    "crypto/x509"
    "fmt"
    "os"
)

// MTLSConfig mTLS 配置
type MTLSConfig struct {
    CAFile       string
    CertFile     string
    KeyFile      string
    ClientAuth   tls.ClientAuthType
}

// NewServerTLSConfig 创建服务端 TLS 配置
func NewServerTLSConfig(config MTLSConfig) (*tls.Config, error) {
    // 加载 CA 证书
    caCert, err := os.ReadFile(config.CAFile)
    if err != nil {
        return nil, fmt.Errorf("failed to read CA cert: %v", err)
    }
    
    caCertPool := x509.NewCertPool()
    if !caCertPool.AppendCertsFromPEM(caCert) {
        return nil, fmt.Errorf("failed to parse CA cert")
    }
    
    // 加载服务端证书
    cert, err := tls.LoadX509KeyPair(config.CertFile, config.KeyFile)
    if err != nil {
        return nil, fmt.Errorf("failed to load server cert: %v", err)
    }
    
    return &tls.Config{
        Certificates: []tls.Certificate{cert},
        ClientCAs:    caCertPool,
        ClientAuth:   tls.RequireAndVerifyClientCert,
        MinVersion:   tls.VersionTLS13,
    }, nil
}

// NewClientTLSConfig 创建客户端 TLS 配置
func NewClientTLSConfig(config MTLSConfig) (*tls.Config, error) {
    caCert, err := os.ReadFile(config.CAFile)
    if err != nil {
        return nil, fmt.Errorf("failed to read CA cert: %v", err)
    }
    
    caCertPool := x509.NewCertPool()
    if !caCertPool.AppendCertsFromPEM(caCert) {
        return nil, fmt.Errorf("failed to parse CA cert")
    }
    
    cert, err := tls.LoadX509KeyPair(config.CertFile, config.KeyFile)
    if err != nil {
        return nil, fmt.Errorf("failed to load client cert: %v", err)
    }
    
    return &tls.Config{
        Certificates: []tls.Certificate{cert},
        RootCAs:      caCertPool,
        MinVersion:   tls.VersionTLS13,
    }, nil
}

// 使用示例
func StartMTLSServer(config MTLSConfig) error {
    tlsConfig, err := NewServerTLSConfig(config)
    if err != nil {
        return err
    }
    
    listener, err := tls.Listen("tcp", ":443", tlsConfig)
    if err != nil {
        return err
    }
    defer listener.Close()
    
    for {
        conn, err := listener.Accept()
        if err != nil {
            continue
        }
        
        // 获取客户端证书
        tlsConn := conn.(*tls.Conn)
        state := tlsConn.ConnectionState()
        
        for _, cert := range state.PeerCertificates {
            fmt.Printf("Client cert: %s\n", cert.Subject.CommonName)
        }
        
        // 处理连接
        go handleConnection(conn)
    }
}
```

---

## 第四部分：微隔离

### 4.1 微隔离原理

```
传统网络：
┌─────────────────────────────────────────────────────┐
│                    DMZ/内网                           │
│  ┌────────┐ ┌────────┐ ┌────────┐                  │
│  │ Web    │ │ App    │ │ DB     │                  │
│  └────────┘ └────────┘ └────────┘                  │
└─────────────────────────────────────────────────────┘

微隔离：
┌────────┐  ┌────────┐  ┌────────┐
│ Web Pod│──│App Pod │──│DB Pod  │
│ 策略:  │  │ 策略:  │  │ 策略:  │
│ 只接受 │  │ 只接受 │  │ 只接受 │
│ 80端口 │  │ App端口│  │ 5432端口│
└────────┘  └────────┘  └────────┘
```

### 4.2 Go 实现网络策略

```go
package microsegmentation

import (
    "context"
    "net"
)

// NetworkPolicy 网络策略
type NetworkPolicy struct {
    Name       string
    Namespace  string
    Selector   map[string]string
    Ingress    []Rule
    Egress     []Rule
}

type Rule struct {
    Port     int
    Protocol string // TCP/UDP
    Source   string
    Action   string // allow/deny
}

// PolicyEngine 策略引擎
type PolicyEngine struct {
    policies map[string][]NetworkPolicy
}

func (pe *PolicyEngine) Allow(ctx context.Context, src, dst string, port int, protocol string) bool {
    // 查找匹配的策略
    for _, policy := range pe.policies[dst] {
        if pe.matchesSelector(policy.Selector, dst) {
            for _, rule := range policy.Ingress {
                if rule.Port == port && rule.Protocol == protocol {
                    if rule.Action == "allow" && pe.matchesSource(rule.Source, src) {
                        return true
                    }
                    if rule.Action == "deny" {
                        return false
                    }
                }
            }
        }
    }
    
    // 默认 deny
    return false
}

func (pe *PolicyEngine) matchesSelector(selector map[string]string, target string) bool {
    // 检查目标是否符合选择器
    // ...
    return true
}

func (pe *PolicyEngine) matchesSource(sourcePattern, source string) bool {
    // 检查源地址是否匹配
    // ...
    return true
}
```

---

## 第五部分：密钥管理

### 5.1 密钥管理挑战

```
1. 密钥轮换：定期更换密钥
2. 密钥存储：安全存储
3. 密钥访问：最小权限
4. 密钥销毁：彻底删除
```

### 5.2 Go 实现密钥管理

```go
package secrets

import (
    "context"
    "crypto/aes"
    "crypto/cipher"
    "crypto/rand"
    "encoding/base64"
    "fmt"
    "sync"
    "time"
)

// SecretManager 密钥管理器
type SecretManager struct {
    store    map[string]*Secret
    encryptor *Encryptor
    mu       sync.RWMutex
}

type Secret struct {
    Value      []byte
    CreatedAt  time.Time
    ExpiresAt  time.Time
    RotationID int
}

// Encryptor 加密器
type Encryptor struct {
    key []byte
}

func NewEncryptor(key []byte) *Encryptor {
    return &Encryptor{key: key}
}

func (e *Encryptor) Encrypt(plaintext []byte) (string, error) {
    block, err := aes.NewCipher(e.key)
    if err != nil {
        return "", err
    }
    
    gcm, err := cipher.NewGCM(block)
    if err != nil {
        return "", err
    }
    
    nonce := make([]byte, gcm.NonceSize())
    if _, err := rand.Read(nonce); err != nil {
        return "", err
    }
    
    ciphertext := gcm.Seal(nonce, nonce, plaintext, nil)
    return base64.StdEncoding.EncodeToString(ciphertext), nil
}

func (e *Encryptor) Decrypt(ciphertext string) ([]byte, error) {
    data, err := base64.StdEncoding.DecodeString(ciphertext)
    if err != nil {
        return nil, err
    }
    
    block, err := aes.NewCipher(e.key)
    if err != nil {
        return nil, err
    }
    
    gcm, err := cipher.NewGCM(block)
    if err != nil {
        return nil, err
    }
    
    nonceSize := gcm.NonceSize()
    if len(data) < nonceSize {
        return nil, fmt.Errorf("ciphertext too short")
    }
    
    nonce, ciphertext := data[:nonceSize], data[nonceSize:]
    plaintext, err := gcm.Open(nil, nonce, ciphertext, nil)
    if err != nil {
        return nil, err
    }
    
    return plaintext, nil
}

// RotateKey 密钥轮换
func (sm *SecretManager) RotateKey(ctx context.Context, secretID string) error {
    sm.mu.Lock()
    defer sm.mu.Unlock()
    
    secret, ok := sm.store[secretID]
    if !ok {
        return fmt.Errorf("secret not found")
    }
    
    // 生成新密钥
    newKey := make([]byte, 32)
    rand.Read(newKey)
    
    // 解密旧密钥
    plaintext, err := sm.encryptor.Decrypt(base64.StdEncoding.EncodeToString(secret.Value))
    if err != nil {
        return err
    }
    
    // 用新密钥加密
    encrypted, err := sm.encryptor.Encrypt(plaintext)
    if err != nil {
        return err
    }
    
    secret.Value = []byte(encrypted)
    secret.RotationID++
    secret.ExpiresAt = time.Now().Add(90 * 24 * time.Hour)
    
    return nil
}
```

---

## 第六部分：生产排障案例

### 6.1 mTLS 证书过期

```
现象：服务间通信失败

排查：
1. 检查证书有效期
2. 检查证书链
3. 检查密钥匹配

根因：证书过期

解决方案：
1. 自动化证书轮换
2. 添加证书过期告警
3. 使用 cert-manager
```

### 6.2 密钥泄露

```
现象：密钥出现在代码仓库

排查：
1. git log 搜索密钥
2. 检查 CI/CD 日志
3. 检查环境变量

根因：硬编码密钥

解决方案：
1. 使用 Vault 管理密钥
2. 添加 pre-commit 钩子
3. 定期扫描密钥泄露
```

---

## 第七部分：自测题

### 问题 1
零信任架构的核心组件？

<details>
<summary>查看答案</summary>

1. **身份认证**：MFA、SSO
2. **设备信任**：健康检查
3. **策略引擎**：动态授权
4. **持续监控**：UEBA、SIEM
5. **Go 实现**：ZeroTrustGateway

</details>

### 问题 2
mTLS 相比 TLS 的优势？

<details>
<summary>查看答案</summary>

1. **双向验证**：Client 和 Server 都验证
2. **防止中间人**：证书代替密码
3. **微服务通信**：服务间安全
4. **Go 实现**：tls.Config
5. **TLS 1.3**：更安全

</details>

### 问题 3
密钥管理的最佳实践？

<details>
<summary>查看答案</summary>

1. **定期轮换**：90 天一次
2. **最小权限**：只给必要的
3. **安全存储**：Vault/Secrets Manager
4. **自动化**：CI/CD 集成
5. **Go 实现**：SecretManager

</details>

---

*本文档基于安全架构原理整理。*