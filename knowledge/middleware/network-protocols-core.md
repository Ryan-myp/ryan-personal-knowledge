# 网络协议核心深度笔记 — TCP/UDP/HTTP2/gRPC/QUIC/TLS

> 标签: `#网络协议` `#TCP` `#UDP` `#HTTP2` `#gRPC` `#QUIC` `#TLS` `#广告平台` `#源码级`
> 创建日期: 2026-06-12 | 作者: Ryan
> 定位: 四件套——入门引导 + 源码级深度 + 自测题 + 动手验证

---

## 📋 文档导航

| 部分 | 主题 | 内容类型 | 预计耗时 |
|------|------|----------|----------|
| 一 | 入门引导 | 网络协议概览 | 5 min |
| 二 | TCP 核心原理 | 握手/拥塞/流量控制 + 源码 | 20 min |
| 三 | UDP 与 QUIC | 为什么广告平台需要 UDP | 15 min |
| 四 | HTTP/2 | 多路复用/头部压缩/服务器推送 | 15 min |
| 五 | gRPC | Protobuf/HTTP2传输/负载均衡 | 15 min |
| 六 | TLS/SSL | 证书/加密/HTTP/3 | 15 min |
| 七 | 自测题 | 3 道综合题 | 15 min |

---

## 第一部分：入门引导（5 分钟速览）— 网络协议概览

### 1.1 协议分层速查

```
应用层    HTTP / gRPC / QUIC(应用层语义) / TLS(会话层)
传输层    TCP (可靠/有序/拥塞控制) / UDP (无连接/低延迟)
网络层    IP (路由/分片) / ICMP
链路层    Ethernet / Wi-Fi (MAC/ARP)
```

### 1.2 广告平台的网络需求画像

| 场景 | 协议选择 | 原因 |
|------|----------|------|
| RTB 竞价请求 | HTTP/2 + gRPC | 高并发、低延迟、多路复用 |
| 实时 bidstream | WebSocket / QUIC | 长连接、低开销、避免队头阻塞 |
| 日志上报 | UDP (Kafka) | 高吞吐、可丢包、批量发送 |
| CDN 回源 | HTTP/2 + TLS | 缓存命中率优化、HTTPS 强制 |
| 内部微服务 | gRPC + mTLS | 强类型、高性能、双向认证 |

### 1.3 关键指标速记

```
RTT (Round-Trip Time): 一次往返时间
TPUT (Throughput):   实际吞吐量 = min(带宽, 拥塞窗口/RTT)
JITTER:              抖动 = RTT 的标准差，影响 QUIC/UDP 体验
CWND (Congestion Window): 拥塞窗口，决定发送速率上限
RTO (Retransmission Timeout): 重传超时 = SRTT + 4 * RTTVAR
```

---

## 第二部分：TCP 核心原理 — 三次握手、拥塞控制、流量控制

### 2.1 三次握手与四次挥手

#### 2.1.1 状态机全景

```
客户端                              服务端
  LISTEN                               -
   |                                   |
   |-------- SYN (seq=ISN_c) --------->|
   |        seq=x, flags=S             | LISTEN -> SYN_RECV
   |<------- SYN+ACK (seq=y) ---------|
   |        seq=y, ack=x+1, flags=SA   |
   |-------- ACK (ack=y+1) ---------->|| SYN_RECV -> ESTABLISHED
   |        seq=x+1, flags=A           |
  ESTABLISHED                        ESTABLISHED
```

**关键点：**
- `SYN_RECV` 是 Linux 内核特有的中间态，表示收到了 SYN 但尚未完成 ACK
- 半连接队列（syn queue）：存放 `SYN_RECV` 状态的连接，大小由 `tcp_max_syn_backlog` 控制
- 全连接队列（accept queue）：存放已完成握手的连接，大小由 `somaxconn` 和 `listen()` 参数共同决定

#### 2.1.2 Go 源码级：Dial 的握手过程

```go
// net/pipe.go + net/tcpsock_posix.go
// Dial 最终调用 sysDialer.dialTCP() -> func (c *TCPConn) dialConn()

func (d *sysDialer) dialTCP(ctx context.Context, laddr, raddr *net.TCPAddr) (*net.TCPConn, error) {
    // 1. 创建 socket (sysSocket)
    fd, err := net.sysSocket(net.AF_INET, net.SOCK_STREAM, 0)
    // 2. 设置非阻塞 (fcntl F_SETFL | O_NONBLOCK)
    net.SetNonblock(fd, true)
    // 3. 绑定本地地址（可选）
    if laddr != nil {
        net.Bind(fd, laddr.fd())
    }
    // 4. 发起 connect() syscall — 这是三次握手的第一步（发送SYN）
    //    connect() 在非阻塞模式下会返回 EINPROGRESS
    err = net.Connect(fd, raddr.fd())
    // 5. 等待 connect 完成（通过 poll 机制）
    //    内核完成三次握手后，poll 返回可写事件
    err = net.PollWrite(fd, ...)
    // 6. 获取 SO_ERROR 检查是否有错误
    err = net.GetsockoptInt(fd, net.SOL_SOCKET, net.SO_ERROR)
    // 7. 恢复阻塞模式
    net.SetNonblock(fd, false)
    return &net.TCPConn{fd: fd}, nil
}
```

**源码细节：**
- `net.Poll` 使用 `epoll` (Linux) / `kqueue` (macOS/BSD) / `IOCP` (Windows)
- 非阻塞 connect 的完整流程：`connect()` → `EINPROGRESS` → `epoll_wait(EPOLLOUT)` → `getsockopt(SO_ERROR)` → 成功

#### 2.1.3 四次挥手的 TIME_WAIT

```
客户端                              服务端
  ESTABLISHED                      ESTABLISHED
      |                                  |
      |-------- FIN (seq=u) ----------->|
      |                                  | CLOSE_WAIT
      |<------- ACK (ack=u+1) ---------|
  FIN_WAIT_1                         FIN_WAIT_2
      |                                  |
      |<------- FIN (seq=w) -----------|
      |        ack=u+1                  |
  CLOSING / TIME_WAIT                 LAST_ACK
      |                                  |
      |-------- ACK (ack=w+1) --------->|
  TIME_WAIT                          CLOSED
      |
      |  (等待 2MSL，约 60s)
      |
  CLOSED
```

**TIME_WAIT 的作用：**
1. 确保最后一个 ACK 能到达服务端（如果丢失，服务端会重传 FIN）
2. 让旧连接的重复报文在网络中消散（防止新连接误接收旧数据）

**Go 中的 TIME_WAIT 处理：**

```go
package main

import (
    "fmt"
    "net"
    "os"
)

// 解决 TIME_WAIT 导致端口无法立即重用
func main() {
    // 方法：设置 SO_REUSEADDR + SO_REUSEPORT
    listener, err := net.Listen("tcp", ":8080")
    if err != nil {
        fmt.Fprintf(os.Stderr, "listen error: %v\n", err)
        return
    }
    defer listener.Close()

    // Go 标准库在 Listen 时自动设置了 SO_REUSEADDR
    // 如果需要 SO_REUSEPORT（多进程场景），需要通过 syscall 手动设置
    fmt.Println("Server listening on :8080")
    http.Serve(listener, nil)
}
```

### 2.2 拥塞控制算法演进

#### 2.2.1 四种经典算法对比

| 算法 | 发明年份 | 核心思想 | 适用场景 |
|------|----------|----------|----------|
| Reno | 1999 | 慢启动 + 拥塞避免 + 快速重传/恢复 | 通用 |
| Cubic | 2006 | 三次方函数增长，适应大带宽延迟积 | Linux 默认 |
| BBR | 2016 | 建模瓶颈带宽 + 最小 RTT，不依赖丢包 | 高带宽、高延迟 |
| BBRv2 | 2019 | 多 RTT 采样 + 公平性增强 | 多流场景 |

#### 2.2.2 Cubic 算法核心逻辑

```
慢启动阶段：cwnd += 1 (每RTT翻倍)
拥塞避免阶段：cwnd += c / cwnd (每RTT增加 c/cwnd 个MSS)

Cubic 的增长曲线：
cwnd(t) = C * (t - K)^3 + cwnd_last_loss

其中：
- C = 0.4 (默认值)
- t 距离上次拥塞发生的时间
- K 是理论最大点
- cwnd_last_loss 是上次拥塞时的窗口大小
```

#### 2.2.3 Go 源码级：TCP 拥塞控制接口

```go
// net/http2 使用了 Go 内置的 TCP 拥塞控制
// 但 Go 1.21+ 支持自定义拥塞控制 via net.ListenConfig.Control

package main

import (
    "context"
    "fmt"
    "log"
    "net"
    "syscall"
)

// 自定义 TCP 拥塞控制 - 切换为 BBR
func control(network, address string, c syscall.RawConn) error {
    var ctrlErr error
    err := c.Control(func(fd uintptr) {
        // 设置拥塞控制算法为 bbr
        ctrlErr = syscall.SetsockoptInt(
            int(fd),
            syscall.IPPROTO_TCP,
            253, // TCP_CONGESTION (Linux)
            3,   // "bbr" 的索引（需通过 getsockopt 获取）
        )
    })
    if err != nil {
        return err
    }
    return ctrlErr
}

func main() {
    lc := net.ListenConfig{
        Control: control,
    }
    ln, err := lc.Listen(context.Background(), "tcp", ":8080")
    if err != nil {
        log.Fatal(err)
    }
    defer ln.Close()
    log.Printf("Listening on :8080 with custom TCP settings")
    http.Serve(ln, nil)
}
```

**源码级真相：**
- Go 的 `net` 包不直接暴露拥塞控制算法选择（跨平台限制）
- 在 Linux 上，通过 `Control` 回调可以设置 `TCP_CONGESTION` sockopt
- Go 1.23+ 引入了 `net.Dialer.KeepAliveConfig`，但对拥塞控制的封装仍然有限
- 广告平台通常在内核层面配置 BBR：`sysctl -w net.ipv4.tcp_congestion_control=bbr`

### 2.3 流量控制 — 滑动窗口

#### 2.3.1 接收窗口 (rwnd) vs 拥塞窗口 (cwnd)

```
发送速率 = min(cwnd, rwnd) / RTT

- cwnd: 网络拥塞决定的上限（全局视角）
- rwnd: 接收方缓冲区决定的上限（局部视角）
```

#### 2.3.2 Go 源码级：Read 与缓冲

```go
package main

import (
    "bytes"
    "fmt"
    "io"
    "net"
    "time"
)

// 演示 TCP 读缓冲对应用层的影响
func tcpBufferDemo() {
    listener, _ := net.Listen("tcp", "127.0.0.1:0")
    defer listener.Close()

    go func() {
        conn, _ := listener.Accept()
        defer conn.Close()
        // 模拟大数据量写入
        data := bytes.Repeat([]byte("A"), 1024*1024) // 1MB
        conn.Write(data)
        time.Sleep(10 * time.Second)
    }()

    conn, _ := net.Dial("tcp", listener.Addr().String())
    defer conn.Close()

    // 默认 ReadBufferSize = 0（系统默认，通常 212KB）
    // 可以通过 net.ListenConfig 设置
    buf := make([]byte, 4096)
    total := 0
    for {
        n, err := conn.Read(buf)
        if n > 0 {
            total += n
        }
        if err == io.EOF {
            break
        }
        if err != nil {
            fmt.Printf("read error: %v\n", err)
            break
        }
    }
    fmt.Printf("Received %d bytes\n", total)
}

// 广告平台实战：大响应体 + 流式读取
func adResponseStreaming() {
    listener, _ := net.Listen("tcp", "127.0.0.1:0")
    defer listener.Close()

    go func() {
        conn, _ := listener.Accept()
        defer conn.Close()
        // 模拟广告创意 JSON（可能很大）
        bigJSON := bytes.Repeat([]byte(`{"slot":"hero","creative_id":123}`), 10000)
        conn.Write(bigJSON)
    }()

    conn, _ := net.Dial("tcp", listener.Addr().String())
    defer conn.Close()

    // 使用 bufio.Reader 避免一次性分配大内存
    reader := bufio.NewReaderSize(conn, 32*1024) // 32KB 缓冲
    data, _ := reader.ReadAll()
    fmt.Printf("Read %d bytes with streaming\n", len(data))
}
```

---

## 第三部分：UDP 与 QUIC — 为什么广告平台需要 UDP

### 3.1 UDP 极简模型

```
UDP 数据报 = 8字节头部 + 应用数据
- 无连接
- 无确认
- 无重传
- 无拥塞控制
- 保留消息边界（read 一次拿到完整 datagram）

Linux 内核限制：
- 默认 sendbuf: 212KB → sysctl net.core.wmem_max
- 默认 recvbuf: 212KB → sysctl net.core.rmem_max
- 单 datagram 最大: 65507 字节 (65535 - 20 IP - 8 UDP)
```

### 3.2 广告平台为什么用 UDP

| 场景 | 为什么选 UDP |
|------|-------------|
| 广告曝光/点击日志上报 | 可丢包、批量合并、低 CPU 开销 |
| Bidstream (OpenRTB over UDP) | 实时性优先于可靠性 |
| DMP 数据同步 | 增量更新、容忍少量丢失 |
| DNS 查询 | 短请求，单次往返足够 |
| QUIC 传输层 | 基于 UDP，解决 TCP 队头阻塞 |

### 3.3 QUIC 协议架构

```
QUIC = TCP(可靠传输) + TLS 1.3(加密) + 多路复用(应用层)

┌─────────────────────────────────────────────┐
│  QUIC 帧 (Frame)                             │
│  ├─ STREAM:  数据帧                          │
│  ├─ ACK:     确认帧                           │
│  ├─ CRYPTO:  密钥交换帧                       │
│  ├─ CONGESTION_CONTROL: 拥塞控制帧             │
│  └─ PADDING: 填充帧                           │
├─────────────────────────────────────────────┤
│  QUIC 数据流 (Data Stream)                    │
│  ├─ 0-RTT 数据 (早期数据)                      │
│  ├─ 控制流 (control)                          │
│  ├─ 双向流 (bidirectional)                    │
│  └─ 单向流 (unidirectional)                   │
├─────────────────────────────────────────────┤
│  QUIC 连接 (Connection)                       │
│  └─ 一个 Connection 包含多个 Streams           │
├─────────────────────────────────────────────┤
│  UDP 数据报                                  │
└─────────────────────────────────────────────┘
```

**QUIC 核心优势：**
1. **0-RTT 连接恢复**：之前建立过连接的话，可以直接发数据
2. **无队头阻塞**：每个 stream 独立，丢包只影响当前 stream
3. **连接迁移**：IP/port 变化时通过 connection ID 保持连接
4. **内建加密**：强制 TLS 1.3

### 3.4 Go 实现 QUIC 客户端与服务端

```go
package main

import (
    "context"
    "crypto/tls"
    "fmt"
    "io"
    "log"
    "net/http"
    "time"

    "github.com/quic-go/quic-go"
)

// QUIC 服务端
func quicServer() {
    tlsConf := &tls.Config{
        NextProtos: []string{"quic-test"},
    }

    handler := func(stream quic.OpenStream) {
        data, _ := io.ReadAll(stream)
        fmt.Printf("Received: %s\n", string(data))
        stream.Write([]byte("QUIC echo: " + string(data)))
    }

    listener, err := quic.Listen(
        nil, // 使用 net.ListenPacket("udp", ":9000") 可指定具体端口
        tlsConf,
        &quic.Config{
            MaxIdleTimeout:     30 * time.Second,
            MaxIncomingStreams: 100,
            KeepAlivePeriod:    10 * time.Second,
        },
    )
    if err != nil {
        log.Fatal(err)
    }
    defer listener.Close()

    fmt.Println("QUIC server listening on :9000")
    for {
        conn, err := listener.Accept(context.Background())
        if err != nil {
            log.Printf("accept error: %v", err)
            continue
        }
        go handleQUICConn(conn, handler)
    }
}

func handleQUICConn(conn quic.Connection, handler func(quic.OpenStream)) {
    for {
        stream, err := conn.AcceptStream(context.Background())
        if err != nil {
            return
        }
        go handler(stream)
    }
}

// QUIC 客户端
func quicClient() {
    tlsConf := &tls.Config{
        InsecureSkipVerify: true, // 测试环境
    }

    conn, err := quic.Dial(
        nil,
        &net.UDPAddr{IP: net.ParseIP("127.0.0.1"), Port: 9000},
        tlsConf,
        &quic.Config{
            MaxIdleTimeout: 30 * time.Second,
        },
    )
    if err != nil {
        log.Fatal(err)
    }
    defer conn.CloseWithError(0, "")

    // 打开双向流
    stream, err := conn.OpenStreamSync(context.Background())
    if err != nil {
        log.Fatal(err)
    }

    msg := []byte("Hello QUIC!")
    stream.Write(msg)
    stream.Write([]byte{0}) // 标记结束

    resp := make([]byte, 1024)
    n, _ := stream.Read(resp)
    fmt.Printf("Response: %s\n", string(resp[:n]))
}

// QUIC + HTTP/3 方式（更实用）
func http3Client() {
    transport := &http3.Transport{
        TLSClientConfig: &tls.Config{
            InsecureSkipVerify: true,
        },
    }
    client := &http.Client{
        Transport: transport,
    }

    resp, err := client.Get("https://localhost:9000/api/ad-slot")
    if err != nil {
        log.Fatal(err)
    }
    defer resp.Body.Close()
    body, _ := io.ReadAll(resp.Body)
    fmt.Printf("HTTP/3 response: %s\n", string(body))
}
```

### 3.5 QUIC vs TCP 性能对比（广告平台实测视角）

```
场景：跨国 RTB 竞价（RTT ~200ms）

TCP + TLS 1.2:
  握手: 2 RTT (TCP) + 2 RTT (TLS) = 4 RTT = 800ms
  首字节: 800ms + TTFB

TCP + TLS 1.3:
  握手: 1 RTT (TCP) + 1 RTT (TLS) = 2 RTT = 400ms
  首字节: 400ms + TTFB

QUIC + TLS 1.3:
  首次: 1 RTT (QUIC+TLS) = 200ms
  恢复: 0 RTT = 0ms (直接发数据)
  首字节: 200ms (首次) / 0ms (恢复)

结论：QUIC 在首次连接节省 50% 延迟，恢复连接节省 100% 握手延迟
```

---

## 第四部分：HTTP/2 — 多路复用、头部压缩、服务器推送

### 4.1 HTTP/1.x 痛点回顾

```
HTTP/1.x 问题：
1. 队头阻塞：一个连接串行处理请求，前面的阻塞后面的
2. 头部冗余：每次请求都带 Cookie/User-Agent 等重复头部
3. 连接数限制：浏览器限制同域名最多 6 个连接
4. 无法主动推送：只有客户端能发起请求

HTTP/2 解决方案：
1. 多路复用：一个连接并发多个请求
2. HPACK 头部压缩：动态字典 + Huffman 编码
3. 服务器推送：服务端可以主动推送资源
4. 二进制帧：解析更高效
```

### 4.2 HTTP/2 帧结构

```
+-----------------------------------------------+
|                 Frame Header (9 bytes)         |
|  Length (24 bits) | Type (8 bits) | Flags (8)|
|  R | Stream Identifier (31 bits)              |
+-----------------------------------------------+
|              Frame Payload (variable)          |
+-----------------------------------------------+

帧类型：
- DATA:        请求/响应体
- HEADERS:     头部块
- PRIORITY:    优先级声明
- RST_STREAM:  异常关闭流
- SETTINGS:    参数协商
- PUSH_PROMISE: 服务器推送
- PING:        心跳
- GOAWAY:      优雅关闭
- WINDOW_UPDATE: 流量控制
- CONTINUATION: 头部块连续帧
```

### 4.3 Go 源码级：HTTP/2 连接管理

```go
package main

import (
    "crypto/tls"
    "fmt"
    "io"
    "log"
    "net/http"
    "sync"
    "time"
)

// Go 标准库的 HTTP/2 实现
// net/textproto + golang.org/x/net/http2

// 1. 基础 HTTP/2 客户端（自动协商）
func basicHTTP2Client() {
    // Go 1.6+ 通过 h2 标识自动启用 HTTP/2
    client := &http.Client{
        Timeout: 10 * time.Second,
    }

    // 访问 HTTPS 站点会自动尝试 HTTP/2（通过 ALPN 协商）
    resp, err := client.Get("https://httpbin.org/get")
    if err != nil {
        log.Fatal(err)
    }
    defer resp.Body.Close()

    fmt.Printf("Protocol: %s\n", resp.Proto) // HTTP/2.0
    body, _ := io.ReadAll(resp.Body)
    fmt.Printf("Body length: %d\n", len(body))
}

// 2. 自定义 HTTP/2 Transport（广告平台常用调优）
func tunedHTTP2Transport() *http.Client {
    dialer := &net.Dialer{
        Timeout:   5 * time.Second,
        KeepAlive: 30 * time.Second,
    }

    transport := &http2.Transport{
        DialTLS: func(network, addr string, cfg *tls.Config) (net.Conn, error) {
            return tls.Dial(network, addr, cfg)
        },
        // 连接池配置
        MaxConnsPerHost:     100,   // 每主机最大连接数
        MaxReadFrameSize:    1 << 20, // 最大帧 1MB
        // 允许 HTTP/2 降级
        AllowHTTP:           false, // HTTP/2 必须 TLS
        // 禁用服务器推送（广告平台通常不需要）
        DisableCompression:  true,
    }

    return &http.Client{
        Transport: transport,
        Timeout:   15 * time.Second,
    }
}

// 3. 多路复用实战：并发请求同一个 HTTP/2 连接
func multiplexDemo() {
    client := &http.Client{} // 自动 HTTP/2

    urls := []string{
        "https://httpbin.org/delay/1",
        "https://httpbin.org/delay/1",
        "https://httpbin.org/delay/1",
        "https://httpbin.org/delay/1",
    }

    start := time.Now()
    var wg sync.WaitGroup
    var mu sync.Mutex
    results := make([]int, len(urls))

    for i, url := range urls {
        wg.Add(1)
        go func(idx int, u string) {
            defer wg.Done()
            resp, err := client.Get(u)
            if err != nil {
                log.Printf("request %d error: %v", idx, err)
                return
            }
            defer resp.Body.Close()
            io.Copy(io.Discard, resp.Body)
            mu.Lock()
            results[idx] = int(time.Since(start).Milliseconds())
            mu.Unlock()
        }(i, url)
    }

    wg.Wait()
    elapsed := time.Since(start)
    fmt.Printf("4 requests in parallel took %v\n", elapsed)
    // HTTP/1.x: ~4s (串行)
    // HTTP/2:   ~1s (并行，复用同一连接)
}

// 4. HTTP/2 Server Push 服务端实现
func http2ServerPush() {
    mux := http.NewServeMux()

    mux.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
        // 获取 pusher
        pusher, ok := w.(http.Pusher)
        if !ok {
            http.Error(w, "push not supported", http.StatusUnsupportedMediaType)
            return
        }

        // 主动推送 CSS 资源
        err := pusher.Push("/style.css", nil)
        if err != nil {
            log.Printf("push error: %v", err)
        }

        w.Header().Set("Content-Type", "text/html")
        fmt.Fprintln(w, "<html><head><link rel='stylesheet' href='/style.css'></head>")
        fmt.Fprintln(w, "<body><h1>Ad Platform Dashboard</h1></body></html>")
    })

    mux.HandleFunc("/style.css", func(w http.ResponseWriter, r *http.Request) {
        w.Header().Set("Content-Type", "text/css")
        fmt.Fprintln(w, "body { margin: 0; }")
    })

    srv := &http.Server{
        Addr:      ":8443",
        Handler:   mux,
        TLSConfig: &tls.Config{
            NextProtos: []string{"h2", "http/1.1"}, // ALPN 协商
        },
    }
    log.Fatal(srv.ListenAndServeTLS("cert.pem", "key.pem"))
}
```

### 4.4 HPACK 头部压缩原理

```
HPACK 压缩策略：
1. 静态字典：预定义常见头部（Host, Content-Type, Cookie 等）
   - 使用索引号引用，1 byte 即可表示
2. 动态字典：协商过程中学习的头部键值对
   - LRU 缓存，默认 4KB
3. 未匹配头部：Huffman 编码 + 字面量

例如：Cookie: session=abc123
  第一次: 完整发送 (字面量 + Huffman)
  第二次: 只发索引号 (如果仍在动态字典中)
  第三次: 可能触发 evict（字典满了）

广告平台头部压缩收益：
- 请求头部平均压缩比: 50-70%
- Cookie 字段是最大受益者（每次必带，且很长）
```

---

## 第五部分：gRPC — Protobuf、HTTP/2 传输、负载均衡

### 5.1 gRPC 架构总览

```
┌──────────────────────────────────────────────┐
│ Application Layer                            │
│  ┌─────────────┐     ┌────────────────────┐  │
│  │ Proto 定义   │────▶│ Service Stub       │  │
│  │ .proto 文件  │     │ (Generated Code)   │  │
│  └─────────────┘     └────────────────────┘  │
├──────────────────────────────────────────────┤
│ gRPC Core Layer                              │
│  ┌────────────────────────────────────────┐   │
│  │  Transport Layer (HTTP/2)               │   │
│  │  - 多路复用                              │   │
│  │  - 流式传输 (Unary/Server/Client/Bidi)  │   │
│  │  - 压力控制 (Flow Control)              │   │
│  └────────────────────────────────────────┘   │
│  ┌────────────────────────────────────────┐   │
│  │  Serialization (Protobuf)               │   │
│  │  - 高效二进制序列化                      │   │
│  │  - 向后兼容 (field numbering)           │   │
│  └────────────────────────────────────────┘   │
└──────────────────────────────────────────────┘
```

### 5.2 Protobuf 核心概念

```protobuf
// ad_platform.proto
syntax = "proto3";
package adplatform;

option go_package = "github.com/ryan/ad-platform/proto";

// BidRequest: 竞价请求
message BidRequest {
    string impression_id = 1;      // 唯一标识
    string ad_slot = 2;            // 广告位
    int64 timestamp = 3;           // 时间戳
    User user = 4;                 // 用户信息
    Device device = 5;             // 设备信息
    repeated AdSlot slots = 6;     // 广告位列表
    BidRequestOptions options = 7; // 竞价选项
}

message User {
    string id_hash = 1;            // 哈希后的用户ID
    repeated string interests = 2; // 兴趣标签
    int32 age_range = 3;           // 年龄段
}

message Device {
    string os = 1;
    string model = 2;
    string ip = 3;
    GeoLocation geo = 4;
}

message GeoLocation {
    float latitude = 1;
    float longitude = 2;
    string city = 3;
    string country = 4;
}

// BidResponse: 竞价响应
message BidResponse {
    string impression_id = 1;
    int64 bid_price = 2;           // 出价（单位：厘）
    string creative_id = 3;
    string ad_url = 4;
    int64 ttl_seconds = 5;         // 缓存时长
    bytes tracking_urls = 6;       // 追踪 URL 列表
}

// BidService: 竞价服务
service BidService {
    // 一元调用：典型 RTB 请求-响应
    rpc Bid (BidRequest) returns (BidResponse);

    // 服务端流式：推送竞价结果
    rpc BidStream (BidRequest) returns (stream BidResponse);

    // 客户端流式：批量上报
    rpc ReportBatch (stream ImpressionEvent) returns (ReportAck);

    // 双向流：实时 bidstream
    rpc BidBidirectional (stream BidRequest) returns (stream BidResponse);
}
```

**Protobuf 序列化效率：**
```
JSON:     ~200-500 bytes (ad request)
Protobuf: ~80-150 bytes (same data)
压缩比:   ~60-70% 节省
解析速度: Protobuf 比 JSON 快 5-10x (Go protobuf 实现)
```

### 5.3 Go gRPC 客户端与服务端

```go
package main

import (
    "context"
    "fmt"
    "log"
    "time"

    "google.golang.org/grpc"
    "google.golang.org/grpc/credentials/insecure"
    pb "github.com/ryan/ad-platform/proto" // 生成的代码
)

// gRPC 客户端
type BidClient struct {
    conn    *grpc.ClientConn
    client  pb.BidServiceClient
    timeout time.Duration
}

func NewBidClient(target string, timeout time.Duration) (*BidClient, error) {
    // 连接选项（广告平台关键调优）
    opts := []grpc.DialOption{
        grpc.WithTransportCredentials(insecure.NewCredentials()), // 测试用
        grpc.WithDefaultCallOptions(grpc.WaitForReady(true)),
        grpc.WithInitialWindowSize(1 << 20),    // 1MB 窗口
        grpc.WithInitialConnWindowSize(1 << 20), // 1MB 连接窗口
        grpc.WithMaxCallRecvMsgSize(1 << 20),    // 最大接收 1MB
        grpc.WithKeepaliveParams(grpc.KeepaliveParams{
            Time:                10 * time.Second,
            Timeout:             5 * time.Second,
            PermitWithoutStream: true, // 空闲时也发 ping
        }),
    }

    conn, err := grpc.Dial(target, opts...)
    if err != nil {
        return nil, err
    }

    return &BidClient{
        conn:    conn,
        client:  pb.NewBidServiceClient(conn),
        timeout: timeout,
    },
}

// 一元调用
func (c *BidClient) PlaceBid(req *pb.BidRequest) (*pb.BidResponse, error) {
    ctx, cancel := context.WithTimeout(context.Background(), c.timeout)
    defer cancel()

    resp, err := c.client.Bid(ctx, req)
    if err != nil {
        return nil, fmt.Errorf("bid call failed: %w", err)
    }
    return resp, nil
}

// 服务端流式调用
func (c *BidClient) BidStream(req *pb.BidRequest) error {
    stream, err := c.client.BidStream(context.Background(), req)
    if err != nil {
        return err
    }

    for {
        resp, err := stream.Recv()
        if err == io.EOF {
            break
        }
        if err != nil {
            return err
        }
        fmt.Printf("Stream bid: price=%d creative=%s\n",
            resp.BidPrice, resp.CreativeId)
    }
    return nil
}

// gRPC 服务端
type BidServer struct {
    pb.UnimplementedBidServiceServer
    bidEngine *BidEngine // 业务逻辑
}

func (s *BidServer) Bid(ctx context.Context, req *pb.BidRequest) (*pb.BidResponse, error) {
    // 1. 解析请求
    // 2. 调用竞价引擎
    // 3. 返回响应
    resp, err := s.bidEngine.EvaluateBid(req)
    if err != nil {
        return nil, status.Errorf(codes.Internal, "bid eval error: %v", err)
    }
    return resp, nil
}

// 双向流：实时 bidstream
func (s *BidServer) BidBidirectional(stream pb.BidService_BidBidirectionalServer) error {
    for {
        req, err := stream.Recv()
        if err == io.EOF {
            return nil
        }
        if err != nil {
            return err
        }

        // 处理请求并推送响应
        resp, _ := s.bidEngine.EvaluateBid(req)
        if resp != nil {
            stream.Send(resp)
        }
    }
}
```

### 5.4 gRPC 负载均衡

```
gRPC 负载均衡策略：

1. PickFirst (默认): 第一个可用子连接
   - 简单但不够智能
   - 适合单数据中心

2. RoundRobin: 轮询所有子连接
   - 均匀分发
   - 适合同质化集群

3. LeastRequested: 选择请求数最少的后端
   - 适合异步、可变延迟的场景

4. PickUnused: 优先选未使用的子连接
   - 适合连接复用场景

Go gRPC 负载均衡配置：
```go
import "google.golang.org/grpc/balancer/roundrobin"

conn, err := grpc.Dial(
    "dns:///resolver.ad-platform.internal",
    grpc.WithDefaultServiceName("adplatform.BidService"),
    grpc.WithBalancerName(roundrobin.Name), // 显式指定
)
```

**广告平台 LB 架构：**
```
客户端 gRPC
    │
    ▼
L4 LB (LVS/Envoy) ── 基于 IP 轮询
    │
    ▼
L7 LB (Envoy/Consul) ── 基于服务发现
    │
    ▼
Bid Engine Pods (K8s Deployment)
    ├── Pod A (CPU 30%, RTT 5ms)
    ├── Pod B (CPU 80%, RTT 20ms) ← 应减少流量
    └── Pod C (CPU 20%, RTT 3ms)  ← 应增加流量
```

### 5.5 gRPC 压力控制 (Flow Control)

```
gRPC 使用 HTTP/2 的 WINDOW_UPDATE 帧做流量控制：

┌──────────────┐         WINDOW_UPDATE          ┌──────────────┐
│   Client     │◄──────────────────────────────►│   Server     │
│              │                                  │              │
│  Send 64KB   │                                  │  Buffer: 1MB │
│  ──recv───   │    WINDOW_UPDATE +64KB           │  ──send───   │
│  Buffer: 1MB │                                  │  Buffer: 64KB│
└──────────────┘                                  └──────────────┘

Go gRPC 默认窗口:
- 初始窗口: 64KB (per-stream)
- 连接窗口: 1MB (per-connection)

广告平台调优:
- 大 bid request (>64KB): 调大 InitialWindowSize
- 高频小请求: 保持默认，避免内存膨胀
```

---

## 第六部分：TLS/SSL — 证书、加密、HTTP/3

### 6.1 TLS 握手流程

```
TLS 1.3 握手（最简 1-RTT）:

Client                              Server
   |------ ClientHello --------------->|
   |      - 支持的 cipher suites       |
   |      - key_share (X25519)         |
   |      - supported_versions: 1.3    |
   |<----- ServerHello + EncryptedExtensions -|
   |<----- Certificate + CertVerify + Finished -|
   |                                   |
   |------ Finished ------------------>|
   |                                   |
   ═══ 加密通道建立，后续所有数据加密 ═══
   |------ Application Data (encrypted) -->|
   |<------ Application Data (encrypted) -|
```

**TLS 1.3 相比 1.2 的关键改进：**
1. 握手从 2-RTT 降到 1-RTT（首次）/ 0-RTT（恢复）
2. 移除了不安全的 cipher suites（RC4, DES, CBC 模式等）
3. 前向保密 (PFS) 成为强制要求
4. 密钥派生改用 HKDF

### 6.2 证书链验证

```
信任链：
Root CA (自签名，预置在操作系统)
  └── Intermediate CA (由 Root 签发)
       └── Leaf Certificate (由 Intermediate 签发)
            └── *.ad-platform.com

OCSP Stapling:
客户端不直接查 OCSP 服务器，而是让服务端在握手时附带签名好的 OCSP 响应
- 减少延迟: 不需要额外 HTTP 请求
- 隐私保护: 不暴露访问记录给 OCSP 提供商
```

### 6.3 Go TLS 实战

```go
package main

import (
    "crypto/tls"
    "crypto/x509"
    "fmt"
    "io"
    "log"
    "net/http"
    "os"
)

// 1. 自定义 TLS 配置（广告平台标准配置）
func standardTLSConfig() *tls.Config {
    return &tls.Config{
        // 只允许 TLS 1.3
        MinVersion: tls.VersionTLS13,
        // 指定 cipher suites（按优先级排序）
        CipherSuites: []uint16{
            tls.TLS_AES_256_GCM_SHA384,
            tls.TLS_CHACHA20_POLY1305_SHA256,
            tls.TLS_AES_128_GCM_SHA256,
        },
        // 优先使用ECDHE
        PreferServerCipherSuites: true,
        // Curve 优先级
        CurvePreferences: []tls.CurveID{
            tls.X25519,
            tls.CurveP256,
        },
    }
}

// 2. 客户端证书验证（mTLS，用于内部服务间通信）
func mtlsClient() {
    // 加载客户端证书
    cert, err := tls.LoadX509KeyPair("client.crt", "client.key")
    if err != nil {
        log.Fatal(err)
    }

    // 加载 CA 证书（验证服务端证书）
    caCert, err := os.ReadFile("ca.crt")
    if err != nil {
        log.Fatal(err)
    }
    caCertPool := x509.NewCertPool()
    caCertPool.AppendCertsFromPEM(caCert)

    tlsCfg := &tls.Config{
        Certificates: []tls.Certificate{cert},
        RootCAs:      caCertPool,
        MinVersion:   tls.VersionTLS13,
    }

    transport := &http.Transport{
        TLSClientConfig: tlsCfg,
    }
    client := &http.Client{Transport: transport}

    resp, err := client.Get("https://internal.ad-platform.internal/api/bid")
    if err != nil {
        log.Fatal(err)
    }
    defer resp.Body.Close()
    io.Copy(io.Discard, resp.Body)
}

// 3. 服务端 TLS 配置
func tlsserver() {
    tlsCfg := standardTLSConfig()

    // 可选：要求客户端证书（mTLS）
    // tlsCfg.ClientAuth = tls.RequireAndVerifyClientCert

    srv := &http.Server{
        Addr:      ":443",
        TLSConfig: tlsCfg,
    }

    // 配合 Let's Encrypt 自动续期
    // certmagic 库可以简化这个流程
    log.Fatal(srv.ListenAndServeTLS("", ""))
}

// 4. 证书透明度 (CT) 检查
func ctCheck() {
    tlsCfg := &tls.Config{
        MinVersion: tls.VersionTLS13,
        // 启用 SCT 验证（证书透明度）
        // 需要额外的 CT 验证库
    }
    _ = tlsCfg
}

// 5. HTTP/3 + QUIC + TLS 1.3 组合
func http3server() {
    tlsCfg := standardTLSConfig()
    tlsCfg.NextProtos = []string{"h3"} // HTTP/3

    // quic-go 的 HTTP/3 服务器
    h3srv := &http3.Server{
        Addr:      ":443",
        Handler:   http.HandlerFunc(handleHTTP3),
        TLSConfig: tlsCfg,
    }
    log.Fatal(h3srv.ListenAndServe())
}

func handleHTTP3(w http.ResponseWriter, r *http.Request) {
    fmt.Fprintf(w, "Hello from HTTP/3!\n")
}
```

### 6.4 TLS 性能优化（广告平台视角）

```
TLS 开销分析（单次请求）:
- CPU:  握手阶段 ~1-2ms（ECDHE + AES-GCM）
- 网络: 1-RTT 握手（TLS 1.3）
- 内存: 每个连接 ~4KB TLS 上下文

优化策略：
1. Session Resumption (PSK): 跳过完整握手，节省 1 RTT
2. 0-RTT: 直接发加密数据，节省 2 RTT（有重放风险）
3. OCSP Stapling: 避免额外 OCSP 请求
4. ECDHE + X25519: 最快的密钥交换
5. AES-GCM / ChaCha20-Poly1305: 硬件加速（AES-NI）

广告平台实测：
- 不使用 session resumption: 首字节 ~150ms (含 TLS)
- 使用 session resumption: 首字节 ~50ms (含 TLS)
- 使用 0-RTT: 首字节 ~20ms (含 TLS)
```

---

## 第七部分：自测题

### 题目 1：TCP 拥塞与性能调优

**场景：** 你的广告竞价服务（Bid Engine）在高负载下出现以下症状：
- 连接数正常，但 p99 延迟从 5ms 飙升到 500ms
- `netstat` 显示大量 `TIME_WAIT` 连接
- `ss -s` 显示 `TCP: alloc 120000 (aborted 5000, syn 1000, retrans 2000)`
- `sysctl net.ipv4.tcp_tw_reuse = 1` 已设置，但问题依旧

**问题：**
1. `TIME_WAIT` 的根本原因是什么？`tcp_tw_reuse` 为什么不能解决？
2. 如何定位是服务端还是客户端的问题？
3. 给出完整的调优方案（内核参数 + Go 代码层面）。

<details>
<summary>点击查看答案</summary>

```
答案要点：

1. TIME_WAIT 根本原因：
   - 服务端频繁创建短连接（每个请求一个 TCP 连接）
   - 服务端主动关闭连接 → 进入 TIME_WAIT
   - tcp_tw_reuse 只对客户端生效（允许将 TIME_WAIT 连接作为客户端重连）
   - 服务端 TIME_WAIT 无法通过 reuse 解决

2. 定位方法：
   - ss -tan | awk '{print $1}' | sort | uniq -c  # 看连接状态分布
   - ss -s                                       # 查看各类统计
   - 检查服务端是否设置了 SO_REUSEADDR
   - 检查 Go 代码是否在每次请求后正确 Close() 连接
   - 检查是否是客户端行为导致（如浏览器并发请求）

3. 调优方案：

   内核参数：
   sysctl -w net.ipv4.tcp_tw_reuse=1          # 客户端复用
   sysctl -w net.ipv4.tcp_fin_timeout=30       # 缩短 FIN_WAIT_2
   sysctl -w net.ipv4.tcp_max_tw_buckets=262144 # 增加 TIME_WAIT 上限
   sysctl -w net.core.somaxconn=65535          # 增大 accept 队列
   sysctl -w net.ipv4.tcp_max_syn_backlog=65535 # 增大 syn 队列

   Go 代码：
   - 使用连接池（http.Transport 的 MaxIdleConns/IdleConnTimeout）
   - 设置 SO_REUSEADDR/SO_REUSEPORT
   - 长连接复用而非短连接
   - 考虑切换到 HTTP/2 或 gRPC（天然连接复用）

   架构层面：
   - 引入 Envoy/Nginx 做反向代理和连接复用
   - 使用 QUIC 替代 TCP（无 TIME_WAIT 问题）
```
</details>

### 题目 2：HTTP/2 多路复用与队头阻塞

**场景：** 你的广告创意 API 使用 HTTP/2，但监控发现：
- 一个慢请求（/creative/render，~2s）导致其他快速请求（/bid/status，~5ms）也被拖慢
- 同一个连接上，快速请求的 p99 延迟从 5ms 变成 1500ms
- 增大连接数可以缓解，但不能根治

**问题：**
1. 这是 HTTP/2 的队头阻塞吗？为什么？
2. HTTP/2 的 STREAM 级别流量控制能解决这个问题吗？
3. 给出解决方案。

<details>
<summary>点击查看答案</summary>

```
答案要点：

1. 是的，这是 HTTP/2 的帧级队头阻塞：
   - HTTP/2 多路复用在 STREAM 级别并行
   - 但在 CONNECTION 级别的 WINDOW_UPDATE 是共享的
   - 如果某个 STREAM 的 DATA 帧很大，会占用连接级流量控制窗口
   - 其他 STREAM 因为窗口满而被阻塞
   - 另外，如果底层 TCP 层有丢包，整个连接的所有 STREAM 都会被阻塞
     （TCP 是有序的，丢包后必须重传前面丢失的包）

2. STREAM 级流量控制不能完全解决：
   - gRPC 默认每个 STREAM 64KB 窗口
   - 但连接级窗口（默认 1MB）是共享的
   - 更重要的是：TCP 层的队头阻塞仍然存在

3. 解决方案：
   a) 代码层面：
      - 大响应使用分块传输 (chunked)
      - 使用不同的 HTTP/2 连接发送不同优先级的请求
      - 设置 HTTP/2 PRIORITY 标签

   b) 协议层面：
      - 切换到 HTTP/3 (QUIC)，彻底消除队头阻塞
      - QUIC 的每个 STREAM 独立，丢包不影响其他 STREAM

   c) 架构层面：
      - 慢接口和快接口走不同的服务/连接
      - 引入 CDN 缓存创意渲染结果
      - 使用边缘计算提前渲染创意
```
</details>

### 题目 3：gRPC 连接管理与负载均衡

**场景：** 你的 gRPC 客户端（Go）连接了 50 个 Bid Engine 后端 Pod：
- 连接建立后，只有一个 Pod 被选中处理所有请求
- 其他 Pod 几乎空闲
- 被选中的 Pod CPU 打满，其他 Pod CPU 很低
- 你用了 RoundRobin balancer，但似乎没生效

**问题：**
1. 为什么 RoundRobin 没有生效？
2. gRPC 的连接管理模型是怎样的？
3. 如何正确实现负载均衡？

<details>
<summary>点击查看答案</summary>

```
答案要点：

1. RoundRobin 没生效的原因：
   - gRPC 的 resolver 返回多个地址时，默认使用 PickFirst
   - PickFirst 只使用第一个可用的子连接
   - 即使指定了 RoundRobin，如果只有一个子连接，也只会用这一个
   - 常见原因：DNS 解析只返回一个 IP，或服务发现配置不正确

2. gRPC 连接管理模型：
   - grpc.Dial() 创建一个 ClientConn
   - ClientConn 包含一个或多个 SubConn（子连接）
   - Balancer 决定哪个 SubConn 处理下一个 RPC
   - RoundRobin 需要在多个 SubConn 之间轮询

3. 正确实现负载均衡：
   a) 确保 resolver 返回多个地址：
      conn, err := grpc.Dial(
          "dns:///bid-engine.default.svc.cluster.local:9090",
          grpc.WithBalancerName(roundrobin.Name),
      )

   b) 使用 Kubernetes Service（内部 DNS 负载均衡）：
      - k8s Service 的 DNS 返回所有 Pod IP
      - kube-proxy 的 iptables/IPVS 模式做 L4 负载均衡

   c) 使用外部 LB：
      - Envoy xDS 动态配置
      - Consul Connect 服务网格
      - Istio Sidecar 自动注入

   d) 监控和调试：
      - grpc.WithStatsHandler 添加统计
      - 检查 resolver 返回的地址数量
      - 检查 SubConn 的状态
```
</details>

---

## 附录：关键命令速查

### Linux 网络诊断

```bash
# 查看连接状态分布
ss -tan | awk '{print $1}' | sort | uniq -c

# 查看 TIME_WAIT 连接
ss -tan state time-wait | wc -l

# 查看 TCP 拥塞控制算法
cat /proc/sys/net/ipv4/tcp_congestion_control

# 查看 TCP 缓冲区
cat /proc/sys/net/core/rmem_default
cat /proc/sys/net/core/wmem_default
cat /proc/sys/net/core/rmem_max
cat /proc/sys/net/core/wmem_max

# 实时监控 TCP 重传
watch -n 1 'ss -s'

# 查看 QUIC 连接（需要 nghttp3 工具）
nghttpq list

# 查看 TLS 握手详情
openssl s_client -connect example.com:443 -tls1_3 -state -debug

# 测试 HTTP/2
curl -I --http2 https://example.com

# 测试 HTTP/3
curl -I --http3 https://example.com
```

### Go 网络诊断

```go
// 打印当前 goroutine 的网络统计
import _ "net/http/pprof"
// GET /debug/pprof/trace?seconds=5

// 检查 HTTP/2 连接复用
import "golang.org/x/net/http2"
// h2c.Debug = true (开发环境)

// gRPC 连接状态监控
import "google.golang.org/grpc/connectivity"
// conn.GetState() -> IDLE/CONNECTING/READY/TRANSIENT_FAILURE
```

---

> 📝 **总结：** 广告平台的网络协议选型核心原则：**低延迟优先、连接复用最大化、协议栈尽可能靠前**。从 TCP→HTTP/2→gRPC→QUIC/HTTP/3，每一层都在解决上一层的瓶颈。实际架构中通常是混合使用：内部服务用 gRPC+mTLS，外部接口用 HTTP/2+TLS，实时 bidstream 用 QUIC。
