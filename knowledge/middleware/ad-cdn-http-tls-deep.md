# CDN/HTTP/HTTPS 深度：协议/TLS/边缘计算源码级

> 从 HTTP/1.1 到 HTTP/3 协议演进，TLS 握手优化，边缘计算架构

---

## 第一部分：HTTP/3 协议源码深度

### HTTP/3 架构

```
HTTP/3 vs HTTP/2 vs HTTP/1.1:
┌────────────────┬────────────┬────────────┬────────────┐
│     特性       │ HTTP/1.1   │ HTTP/2     │ HTTP/3     │
├────────────────┼────────────┼────────────┼────────────┤
│ 传输协议       │ TCP        │ TCP        │ UDP (QUIC) │
│ 多路复用       │ ❌         │ ✅         │ ✅         │
│ 头部压缩       │ ❌         │ HPACK      │ QPACK      │
│ 连接迁移       │ ❌         │ ❌         │ ✅         │
│ 0-RTT 握手     │ ❌         │ ❌         │ ✅         │
│ 头部阻塞       │ ❌         │ ✅ (HOL)   │ ❌ (QPACK) │
│ 连接重建       │ 慢         │ 慢         │ 快         │
└────────────────┴────────────┴────────────┴────────────┘
```

### QUIC 源码逐行解析

```go
// QUIC 源码：quic-go@v0.30.0/internal/protocol/connection_id.go
type ConnectionID []byte

type ConnectionIDGenerator interface {
    GenerateConnectionID() ConnectionID
    GenerateConnectionIDForRetrieval() ConnectionID
}

// TransportParameters 传输参数
type TransportParameters struct {
    InitialMaxStreamDataBidiLocal  uint64
    InitialMaxStreamDataBidiRemote uint64
    InitialMaxStreamDataUni        uint64
    InitialMaxStreamsBidi          uint64
    InitialMaxStreamsUni           uint64
    MaxIdleTimeout                 time.Duration
    MaxAckDelay                    time.Duration
    DisableActiveMigration         bool
    Enable0RTT                     bool
    OriginalDestinationConnectionID ConnectionID
}

// Session 会话接口
type Session interface {
    OpenStream() (Stream, error)
    OpenStreamSync(context.Context) (Stream, error)
    AcceptStream(context.Context) (Stream, error)
    AcceptUniStream(context.Context) (ReceiveStream, error)
    SendMessage([]byte, string) error
    CloseWithError(ErrorCode, string) error
    Context() context.Context
    LocalAddr() net.Addr
    RemoteAddr() net.Addr
    NextConnectionID() ConnectionID
}
```

---

## 第二部分：TLS 握手源码深度

### TLS 1.3 握手流程

```
TLS 1.3 握手（1-RTT）:
1. ClientHello (Client → Server)
   • supported_versions: TLS 1.3
   • cipher_suites: [TLS_AES_128_GCM_SHA256]
   • key_shares: [x25519: client_public_key]
   • supported_groups: [x25519, secp256r1]
   • signature_algorithms: [ecdsa_secp256r1_sha256]
   
2. ServerHello (Server → Client)
   • selected_version: TLS 1.3
   • cipher_suite: TLS_AES_128_GCM_SHA256
   • key_share: [x25519: server_public_key]
   • renegotiation_info: []
   
3. EncryptedExtensions (Server → Client)
   • alpn_protocol: h3 (HTTP/3)
   • early_data: []
   
4. Certificate (Server → Client)
   • certificate_request: []
   • certificate_verify: [signature]
   
5. CertificateVerify (Server → Client)
   • signature: [server_signature]
   
6. Finished (Server → Client)
   
7. Finished (Client → Server)

TLS 1.3 0-RTT:
1. ClientHello 携带 early_data
2. Server 决定是否接受 0-RTT
3. 接受 → 直接发送数据
4. 拒绝 → 标准握手
```

### tls.go 源码逐行解析

```go
// Go 源码：crypto/tls/handshake_server.go
func (c *Conn) serverHandshake(ctx context.Context) error {
    // 1. 读取 ClientHello
    clientHello, err := c.readClientHello()
    if err != nil {
        return err
    }
    
    // 2. 验证协议版本
    if clientHello.supportedVersions == nil {
        return errors.New("tls: no supported versions")
    }
    
    // 3. 协商 cipher suite
    cipherSuite := selectCipherSuite(clientHello.cipherSuites)
    if cipherSuite == nil {
        return errors.New("tls: no cipher suite")
    }
    
    // 4. 协商 key share
    keyShare := selectKeyShare(clientHello.keyShares)
    if keyShare == nil {
        return errors.New("tls: no key share")
    }
    
    // 5. 生成 server key share
    serverKeyShare, err := generateKeyShare(c.config.Curves)
    if err != nil {
        return err
    }
    
    // 6. 发送 ServerHello
    c.writeServerHello(clientHello, cipherSuite, serverKeyShare)
    
    // 7. 发送 EncryptedExtensions
    c.writeEncryptedExtensions()
    
    // 8. 发送 Certificate
    c.writeCertificate(c.config.Certificates[0])
    
    // 9. 发送 CertificateVerify
    c.writeCertificateVerify()
    
    // 10. 发送 Finished
    c.writeFinished()
    
    // 11. 建立加密通道
    c.setupCipher(cipherSuite, keyShare, serverKeyShare)
    
    return nil
}

// selectCipherSuite 选择 cipher suite
func selectCipherSuite(available []uint16) *cipherSuite {
    preferred := []uint16{
        cipherTLS13_AES128_GCM_SHA256,
        cipherTLS13_AES256_GCM_SHA384,
        cipherTLS13_CHACHA20_POLY1305_SHA256,
    }
    
    for _, preferredCipher := range preferred {
        for _, availableCipher := range available {
            if availableCipher == preferredCipher {
                return findCipherSuite(availableCipher)
            }
        }
    }
    
    return nil
}
```

---

## 第三部分：CDN 架构源码深度

### CDN 调度架构

```
CDN 调度流程：
用户请求 → DNS 解析 → Anycast IP → Edge Node → Origin Server

DNS 调度策略：
1. GSLB (Global Server Load Balancing)
2. GeoDNS (地理位置)
3. Latency DNS (延迟最低)
4. Load-based (负载最低)

Edge Node 缓存策略：
1. Cache-Control: public, max-age=3600
2. Stale-while-revalidate: 60s
3. Stale-if-error: 300s
4. Edge-Control: 边缘缓存策略
```

### edge_cache.go 源码逐行解析

```go
// CDN 源码：edge/edge_cache.go
type EdgeCache struct {
    store       cache.Store
    ttl         time.Duration
    maxSize     int64
    evictionPolicy string // LRU/LFU/ARC
    hitRate     float64
    missRate    float64
}

// NewEdgeCache 创建边缘缓存
func NewEdgeCache(store cache.Store, ttl time.Duration) *EdgeCache {
    return &EdgeCache{
        store: store,
        ttl: ttl,
        evictionPolicy: "LRU",
    }
}

// Get 获取缓存
func (c *EdgeCache) Get(key string) (*cache.Item, error) {
    item, err := c.store.Get(key)
    if err != nil {
        c.missRate++
        return nil, err
    }
    
    // 检查 TTL
    if time.Since(item.CreatedAt) > c.ttl {
        c.store.Delete(key)
        c.missRate++
        return nil, nil
    }
    
    c.hitRate++
    return item, nil
}

// Set 设置缓存
func (c *EdgeCache) Set(key string, value []byte, ttl time.Duration) error {
    item := &cache.Item{
        Key:       key,
        Value:     value,
        CreatedAt: time.Now(),
        TTL:       ttl,
    }
    
    // 检查是否超过最大容量
    if c.store.Size() > c.maxSize {
        c.evict()
    }
    
    return c.store.Set(item)
}

// evict 驱逐策略
func (c *EdgeCache) evict() {
    switch c.evictionPolicy {
    case "LRU":
        c.store.EvictLRU()
    case "LFU":
        c.store.EvictLFU()
    case "ARC":
        c.store.EvictARC()
    }
}
```

---

## 第四部分：自测题

### Q1: HTTP/3 为什么用 UDP 而不用 TCP？

**A**: TCP 的头部阻塞（HOL）问题严重，一个丢包影响所有流。QUIC 基于 UDP，每个流独立，一个丢包不影响其他流。

### Q2: TLS 1.3 相比 1.2 的改进？

**A**:
- 握手从 2-RTT 降到 1-RTT（0-RTT 可选）
- 废弃不安全 cipher suite
- 前向保密强制
- 更简单的握手流程

### Q3: CDN 缓存策略？

**A**:
- Cache-Control: 控制缓存时间
- Stale-while-revalidate:  stale 期间提供旧内容
- Edge-Control: 边缘缓存策略

---

## 第五部分：生产实践

### 1. HTTP/3 部署

```
HTTP/3 部署要点：
1. 启用 QUIC
2. 配置 UDP 端口
3. 监控 QUIC 连接数
4. 回退到 HTTP/2
```

### 2. TLS 优化

```
TLS 优化要点：
1. 启用 TLS 1.3
2. 使用 OCSP stapling
3. 启用 session resumption
4. 监控 TLS 握手延迟
```

### 3. CDN 调优

```
CDN 调优要点：
1. 合理设置 TTL
2. 使用 Purge API
3. 监控 hit rate
4. 配置 Origin Shield
```
