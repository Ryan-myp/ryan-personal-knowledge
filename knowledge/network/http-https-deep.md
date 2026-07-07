# HTTP/HTTPS 协议深度实战

## 一、HTTP/1.1 深入解析

### 1.1 HTTP 请求/响应模型

```
请求:
Method URI HTTP/1.1
Host: example.com
Accept: text/html
User-Agent: Go-http-client/1.1

响应:
HTTP/1.1 200 OK
Content-Type: text/html
Content-Length: 1234
Connection: keep-alive
```

**HTTP 方法语义：**

| 方法 | 幂等 | 安全 | 缓存 | 说明 |
|------|------|------|------|------|
| GET | ✅ | ✅ | ✅ | 获取资源 |
| HEAD | ✅ | ✅ | ✅ | 获取头部 |
| POST | ❌ | ❌ | ❌ | 提交数据 |
| PUT | ✅ | ❌ | ❌ | 全量更新 |
| PATCH | ❌ | ❌ | ❌ | 部分更新 |
| DELETE | ✅ | ❌ | ❌ | 删除资源 |

### 1.2 HTTP/1.1 连接复用

```go
// Go net/http 默认启用连接复用
client := &http.Client{
    Transport: &http.Transport{
        MaxIdleConns:        100,           // 最大空闲连接
        MaxIdleConnsPerHost: 10,            // 每个 host 最大空闲连接
        IdleConnTimeout:     90 * time.Second, // 空闲超时
        TLSHandshakeTimeout: 10 * time.Second, // TLS 握手超时
    },
}
```

**连接复用效果：**

```
不使用连接复用:
请求 1: DNS → TCP握手 → TLS握手 → 发送请求 → 接收响应 → 关闭连接
请求 2: DNS → TCP握手 → TLS握手 → 发送请求 → 接收响应 → 关闭连接
请求 3: DNS → TCP握手 → TLS握手 → 发送请求 → 接收响应 → 关闭连接

使用连接复用:
请求 1: DNS → TCP握手 → TLS握手 → 发送请求 → 接收响应 → 保持连接
请求 2: 发送请求 → 接收响应 → 保持连接
请求 3: 发送请求 → 接收响应 → 保持连接
```

## 二、HTTP/2 多路复用

### 2.1 HTTP/2 帧结构

```
HTTP/2 帧:
├── HEADERS 帧 - 头部块
├── DATA 帧 - 数据
├── RST_STREAM 帧 - 重置流
├── SETTINGS 帧 - 配置参数
├── PUSH_PROMISE 帧 - 服务端推送
├── PING 帧 - 心跳
└── WINDOW_UPDATE 帧 - 流量控制

帧格式:
+-----------------------------------------------+
|                 Length (24)                   |
+---------------+---------------+---------------+
|   Type (8)    |   Flags (8)   |R|
+---------------+---------------+---------------+
|                Stream Identifier (32)         |
+-----------------------------------------------+
```

### 2.2 Go HTTP/2 配置

```go
import "golang.org/x/net/http2"

transport := &http2.Transport{
    AllowHTTP:          false,       // 不允许明文 HTTP
    DisableCompression: false,       // 启用压缩
    MaxHeaderListSize:  16 << 10,    // 最大头部大小 16KB
    MaxReadFrameSize:   1 << 16,     // 最大帧大小 64KB
}

client := &http.Client{
    Transport: transport,
}
```

### 2.3 HTTP/2 服务器推送

```go
func pushHandler(w http.ResponseWriter, r *http.Request) {
    // 推送 CSS 和 JS
    pusher, ok := w.(http.Pusher)
    if !ok {
        http.Error(w, "Push not supported", http.StatusInternalServerError)
        return
    }
    
    pusher.Push("/styles/main.css", nil)
    pusher.Push("/js/app.js", nil)
    
    w.Header().Set("Content-Type", "text/html")
    w.Write([]byte("<html>...</html>"))
}
```

## 三、HTTPS/TLS 深度解析

### 3.1 TLS 握手流程

```
TLS 1.3 握手:
Client                          Server
  |--- ClientHello -------------->|
  |                               |
  |<-- ServerHello, EncryptedExt -|
  |<-- Certificate, CertVerify ---|
  |<-- Finished ------------------|
  |                               |
  |--- Finished ---------------->|
  |                               |
  |<== Application Data ==========|
  |==> Application Data ==>|
```

**TLS 1.2 vs TLS 1.3 对比：**

| 特性 | TLS 1.2 | TLS 1.3 |
|------|---------|---------|
| 握手往返 | 2-RTT | 1-RTT (0-RTT 可选) |
| 密钥交换 | RSA, DHE, ECDHE | 仅 ECDHE/DHE |
| 加密套件 | 大量 | 精简 (AES-GCM, ChaCha20) |
| 前向保密 | 可选 | 强制 |
| 压缩 | 支持 | 禁用 (CRIME/BREACH) |

### 3.2 Go TLS 配置

```go
tlsConfig := &tls.Config{
    MinVersion: tls.VersionTLS12,
    CipherSuites: []uint16{
        tls.TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384,
        tls.TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384,
        tls.TLS_ECDHE_ECDSA_WITH_CHACHA20_POLY1305,
        tls.TLS_ECDHE_RSA_WITH_CHACHA20_POLY1305,
    },
    PreferServerCipherSuites: true,
    CurvePreferences: []tls.CurveID{
        tls.CurveP256,
        tls.X25519,
    },
}
```

## 四、自测题

1. HTTP/1.1 连接复用的好处是什么？
2. HTTP/2 多路复用如何解决队头阻塞？
3. TLS 1.3 相比 1.2 有哪些改进？

## 五、动手验证

```bash
# 1. 使用 curl 分析 HTTP 请求
# 2. 使用 wireshark 抓包分析 TLS 握手
# 3. 测试 HTTP/2 服务器推送
# 4. 配置 Go TLS 参数
```
