# HTTP/3 与 QUIC 协议深度实战

## 一、QUIC 协议架构

### 1.1 QUIC 为什么需要？

TCP 的三个问题：
1. **队头阻塞 (HOL)**：丢包导致所有连接等待
2. **握手延迟**：TCP 3次 + TLS 2次 = 5次往返
3. **连接迁移困难**：IP 变化需要重建连接

QUIC 的解决方案：
- 基于 UDP，应用层实现可靠传输
- 0-RTT 连接恢复
- 连接 ID 实现无缝迁移

### 1.2 QUIC 帧类型

```
QUIC 帧:
├── CONNECTION_CLOSE - 连接关闭
├── CRYPTO - TLS 加密数据
├── STREAM - 流数据
├── ACK - 确认
├── PADDING - 填充
├── PING - 心跳
├── PATH_CHALLENGE/RESPONSE - 路径验证
└── HANDSHAKE_DONE - 握手完成

流控制:
├── STREAM (0-7): 客户端到服务器
├── STREAM (8-15): 服务器到客户端
└── 双向流: 0, 1, 2, 3...
```

## 二、Go QUIC 实现

### 2.1 QUIC 服务器

```go
package main

import (
	"context"
	"crypto/tls"
	"log"
	"net/http"
	
	"github.com/quic-go/quic-go"
	"github.com/quic-go/quic-go/http3"
)

func main() {
	// TLS 配置 (QUIC 强制 TLS 1.3)
	tlsConfig := &tls.Config{
		NextProtos: []string{"h3"},
	}
	
	// HTTP/3 Handler
	handler := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/plain")
		w.Write([]byte("Hello from HTTP/3!"))
	})
	
	// 启动服务器
	err := http3.ListenAndServeQUIC(
		":443",
		"", // cert file
		"", // key file
		handler,
	)
	if err != nil {
		log.Fatal(err)
	}
}
```

### 2.2 QUIC 客户端

```go
func NewQUICClient() *http.Client {
	transport := &http3.Transport{
		TLSClientConfig: &tls.Config{
			NextProtos: []string{"h3"},
		},
	}
	
	return &http.Client{
		Transport: transport,
	}
}

func (c *Client) Fetch(ctx context.Context, url string) ([]byte, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
	if err != nil {
		return nil, err
	}
	
	resp, err := c.client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	
	return io.ReadAll(resp.Body)
}
```

## 三、HTTP/3 性能对比

### 3.1 延迟对比

```
HTTP/1.1:
请求: 1-RTT (TCP握手) + 1-RTT (TLS握手) + 1-RTT (请求) = 3-RTT

HTTP/2:
请求: 1-RTT (TCP握手) + 1-RTT (TLS握手) + 1-RTT (请求) = 3-RTT

HTTP/3 (首次):
请求: 1-RTT (QUIC握手+TLS) + 1-RTT (请求) = 2-RTT

HTTP/3 (恢复):
请求: 0-RTT (使用之前密钥) + 1-RTT (请求) = 1-RTT
```

### 3.2 队头阻塞对比

```
HTTP/1.1 单连接:
丢包 → 所有请求等待 → 延迟飙升

HTTP/2 多路复用:
丢包 → 该流等待 → 其他流继续 (但仍然受 TCP HOL 影响)

HTTP/3 多路复用:
丢包 → 该流等待 → 其他流立即继续 (应用层实现，无 HOL)
```

## 四、自测题

1. QUIC 相比 TCP 解决了哪些问题？
2. HTTP/3 的 0-RTT 连接恢复是如何实现的？
3. HTTP/3 为什么比 HTTP/2 更适合移动网络？

## 五、动手验证

```bash
# 1. 使用 nghttp 测试 HTTP/3
# 2. 使用 Wireshark 抓包分析 QUIC
# 3. 对比 HTTP/2 和 HTTP/3 性能
```
