# 安全深度：mTLS/Zero Trust/供应链安全

> 双向 TLS 认证/零信任架构/供应链安全/CI/CD 安全/密钥管理

---

## 第一部分：入门引导（5 分钟速览）

### 为什么需要零信任？

传统安全模型：** perimeter-based **（边界防御）
零信任模型：** never trust, always verify **（永不信任，始终验证）

```
传统架构：
内网 → 可信 → 直接访问

零信任架构：
内网 → 始终验证 → mTLS → 细粒度授权
```

---

## 第二部分：mTLS（双向 TLS）

### 2.1 mTLS 原理

```
客户端 ←------ TLS Handshake ------→ 服务端
    |  Client Hello                    |
    | ←---- Server Hello + Cert -------|
    |  Client Cert + Proof             |
    | ←---- Server Cert + Proof -------|
    | ←------ Encrypted Data ----------|
```

### 2.2 Go 实现 mTLS

```go
package mtls

import (
    "crypto/tls"
    "crypto/x509"
    "fmt"
    "net/http"
)

// 服务端配置
func NewMTLSServer(certFile, keyFile, caCertFile string) (*http.Server, error) {
    cert, err := tls.LoadX509KeyPair(certFile, keyFile)
    if err != nil {
        return nil, fmt.Errorf("load server cert: %w", err)
    }
    
    caCert, err := os.ReadFile(caCertFile)
    if err != nil {
        return nil, fmt.Errorf("read CA cert: %w", err)
    }
    
    caCertPool := x509.NewCertPool()
    caCertPool.AppendCertsFromPEM(caCert)
    
    tlsConfig := &tls.Config{
        Certificates: []tls.Certificate{cert},
        ClientCAs:    caCertPool,
        ClientAuth:   tls.RequireAndVerifyClientCert, // 要求客户端证书
    }
    
    return &http.Server{
        Addr:      ":8443",
        TLSConfig: tlsConfig,
    }, nil
}

// 客户端配置
func NewMTLSClient(certFile, keyFile, caCertFile string) (*http.Client, error) {
    cert, err := tls.LoadX509KeyPair(certFile, keyFile)
    if err != nil {
        return nil, fmt.Errorf("load client cert: %w", err)
    }
    
    caCert, err := os.ReadFile(caCertFile)
    if err != nil {
        return nil, fmt.Errorf("read CA cert: %w", err)
    }
    
    caCertPool := x509.NewCertPool()
    caCertPool.AppendCertsFromPEM(caCert)
    
    tlsConfig := &tls.Config{
        Certificates: []tls.Certificate{cert},
        RootCAs:      caCertPool,
    }
    
    return &http.Client{
        Transport: &http.Transport{
            TLSClientConfig: tlsConfig,
        },
    }, nil
}
```

---

## 第三部分：零信任架构

### 3.1 零信任核心组件

```
┌─────────────────────────────────────────────────────┐
│                    零信任架构                         │
├─────────────────────────────────────────────────────┤
│                                                     │
│  身份认证 ──→ 设备认证 ──→ 上下文验证 ──→ 授权       │
│                                                     │
│  用户 PKI 证书     ──→  mTLS 双向认证               │
│  设备指纹        ──→  硬件 TPM                      │
│  地理位置/IP     ──→  动态策略                      │
│  时间戳          ──→  短期凭证                      │
│                                                     │
└─────────────────────────────────────────────────────┘
```

### 3.2 Go 实现零信任网关

```go
package zerotrust

import (
    "context"
    "net/http"
)

type ZeroTrustGateway struct {
    auth    *AuthService
    device  *DeviceValidator
    policy  *PolicyEngine
}

func (z *ZeroTrustGateway) Middleware(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        // 1. 用户认证
        token := r.Header.Get("Authorization")
        user, err := z.auth.ValidateToken(token)
        if err != nil {
            http.Error(w, "unauthorized", http.StatusUnauthorized)
            return
        }
        
        // 2. 设备验证
        deviceID := r.Header.Get("X-Device-ID")
        deviceCert := r.TLS.PeerCertificates[0]
        if !z.device.IsValid(deviceID, deviceCert) {
            http.Error(w, "device not trusted", http.StatusForbidden)
            return
        }
        
        // 3. 上下文验证
        if !z.policy.Check(r.Context(), user, deviceID) {
            http.Error(w, "policy violation", http.StatusForbidden)
            return
        }
        
        // 4. 放行
        next.ServeHTTP(w, r)
    })
}
```

---

## 第四部分：供应链安全

### 4.1 依赖扫描

```go
package security

import (
    "os/exec"
)

func ScanDependencies() error {
    // 使用 govulncheck 扫描漏洞
    cmd := exec.Command("go", "tool", "govulncheck", "./...")
    output, err := cmd.CombinedOutput()
    if err != nil {
        return fmt.Errorf("vulnerability scan failed: %v\n%s", err, output)
    }
    return nil
}

// 使用 dependency-track 扫描
func ScanWithDependencyTrack(apiURL string) error {
    // 上传 SBOM 到 Dependency-Track
    cmd := exec.Command("curl", "-X", "POST", apiURL,
        "-H", "Content-Type: application/json",
        "-d", "@sbom.json")
    
    output, err := cmd.CombinedOutput()
    if err != nil {
        return fmt.Errorf("scan failed: %v\n%s", err, output)
    }
    return nil
}
```

### 4.2 签名验证

```go
import (
    "crypto/ecdsa"
    "crypto/x509"
    "encoding/pem"
)

func VerifySignature(certPEM, signature, message []byte) error {
    // 解析证书
    block, _ := pem.Decode(certPEM)
    if block == nil {
        return fmt.Errorf("failed to parse PEM")
    }
    
    cert, err := x509.ParseCertificate(block.Bytes)
    if err != nil {
        return err
    }
    
    // 验证签名
    pubKey, ok := cert.PublicKey.(*ecdsa.PublicKey)
    if !ok {
        return fmt.Errorf("not ECDSA key")
    }
    
    hash := sha256.Sum256(message)
    if !ecdsa.VerifyASN1(pubKey, hash[:], signature) {
        return fmt.Errorf("invalid signature")
    }
    
    return nil
}
```

---

## 第五部分：自测题

### 问题 1
mTLS 和普通 TLS 的区别是什么？

<details>
<summary>查看答案</summary>

1. **普通 TLS**：只验证服务端证书
2. **mTLS**：双向验证，客户端和服务端都验证书
3. **适用场景**：微服务间通信、内部 API
4. **性能**：额外一次 TLS 握手
5. **Go 实现**：tls.RequireAndVerifyClientCert

</details>

### 问题 2
零信任架构的核心理念是什么？

<details>
<summary>查看答案</summary>

1. **永不信任**：不管内外网都要验证
2. **始终验证**：每次请求都要重新认证
3. **最小权限**：只授予必要权限
4. **持续监控**：实时监控异常行为
5. **微隔离**：服务间细粒度隔离

</details>

### 问题 3
供应链安全如何防范？

<details>
<summary>查看答案</summary>

1. **SBOM**：软件物料清单
2. **依赖扫描**：govulncheck/Dependency-Track
3. **签名验证**：代码/镜像签名
4. **最小权限**：CI/CD 最小权限原则
5. **Go 实现**：crypto.Sign/Verify

</details>

---

*本文档基于安全原理整理。*