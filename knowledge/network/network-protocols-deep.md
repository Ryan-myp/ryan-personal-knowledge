# 网络协议深度：TCP/HTTP2/gRPC/QUIC

> 逐行源码解析 + 生产排障案例 + 对比分析 + 动手验证

---

## 第一部分：入门引导（5 分钟速览）

### 类比理解网络协议

```
TCP = 打电话
  → 建立连接
  → 双方确认
  → 有序传输
  → 可靠交付

UDP = 寄明信片
  → 不建立连接
  → 不保证送达
  → 速度快

HTTP/2 = 多路复用电话会议
  → 一条连接，多个对话
  → 头部压缩
  → 服务器推送

QUIC = 改进版的电话会议
  → 基于 UDP
  → 内置加密
  → 零 RTT 握手
  → 更好的移动网络支持
```

### 网络协议栈

```
应用层：HTTP/2, gRPC, QUIC
传输层：TCP, UDP
网络层：IP
链路层：Ethernet, WiFi
```

---

## 第二部分：TCP 深度

### 2.1 TCP 三次握手

```
Client                          Server
  |--- SYN (seq=100) ---------->|
  |<-- SYN+ACK (seq=200, ack=101)|
  |--- ACK (ack=201) ---------->|

为什么需要三次？
1. 防止已失效的连接请求报文段突然到达
2. 双方确认序列号
3. 协商初始序列号
```

### 2.2 TCP 拥塞控制

```
四种算法：
1. 慢启动（Slow Start）：指数增长
2. 拥塞避免（Congestion Avoidance）：线性增长
3. 快重传（Fast Retransmit）：收到 3 个重复 ACK 立即重传
4. 快恢复（Fast Recovery）：不回到慢启动

关键变量：
- cwnd：拥塞窗口
- ssthresh：慢启动阈值
- RTT：往返时间
```

### 2.3 Go 实现 TCP 连接池

```go
package tcp

import (
    "context"
    "net"
    "sync"
    "time"
)

type TCPConnection struct {
    conn    net.Conn
    created time.Time
}

type ConnectionPool struct {
    conns     chan *TCPConnection
    factory   func() (*TCPConnection, error)
    maxOpen   int
    maxIdle   int
    ttl       time.Duration
    mu        sync.Mutex
    openCount int
}

func NewConnectionPool(maxOpen, maxIdle int, ttl time.Duration, factory func() (*TCPConnection, error)) *ConnectionPool {
    return &ConnectionPool{
        conns:   make(chan *TCPConnection, maxOpen),
        factory: factory,
        maxOpen: maxOpen,
        maxIdle: maxIdle,
        ttl:     ttl,
    }
}

func (cp *ConnectionPool) Get(ctx context.Context) (*TCPConnection, error) {
    select {
    case conn := <-cp.conns:
        if time.Since(conn.created) > cp.ttl {
            conn.conn.Close()
            return cp.factory()
        }
        return conn, nil
    case <-ctx.Done():
        return nil, ctx.Err()
    }
}

func (cp *ConnectionPool) Put(conn *TCPConnection) {
    if conn == nil {
        return
    }
    
    select {
    case cp.conns <- conn:
    default:
        conn.conn.Close()
    }
}
```

---

## 第三部分：HTTP/2 深度

### 3.1 HTTP/2 特性

```
1. 多路复用：一条 TCP 连接，多个请求并行
2. 头部压缩：HPACK 算法
3. 服务器推送：Server Push
4. 二进制帧：更高效解析
5. 流优先级：控制资源分配
```

### 3.2 Go 实现 HTTP/2 客户端

```go
package http2

import (
    "context"
    "net/http"
    "time"
)

type HTTP2Client struct {
    client *http.Client
    mux    *StreamMultiplexer
}

type StreamMultiplexer struct {
    streams   map[int64]*Stream
    mu        sync.Mutex
    nextID    int64
}

type Stream struct {
    ID       int64
    Request  *Request
    Response *Response
    Done     chan struct{}
}

func (mux *StreamMultiplexer) NewStream(ctx context.Context, req *Request) (*Stream, error) {
    mux.mu.Lock()
    streamID := mux.nextID
    mux.nextID += 2
    mux.mu.Unlock()
    
    stream := &Stream{
        ID:      streamID,
        Request: req,
        Done:    make(chan struct{}),
    }
    
    mux.mu.Lock()
    mux.streams[streamID] = stream
    mux.mu.Unlock()
    
    // 发送 HEADERS 帧
    // 发送 DATA 帧
    // 等待响应
    
    return stream, nil
}

func (c *HTTP2Client) Do(req *Request) (*Response, error) {
    stream, err := c.mux.NewStream(req.Context(), req)
    if err != nil {
        return nil, err
    }
    
    select {
    case <-stream.Done:
        return stream.Response, nil
    case <-req.Context().Done():
        return nil, req.Context().Err()
    }
}
```

---

## 第四部分：gRPC 深度

### 4.1 gRPC 原理

```
gRPC = HTTP/2 + Protocol Buffers

优势：
1. 高性能：二进制协议 + HTTP/2
2. 强类型：IDL 定义接口
3. 多语言：支持多种语言
4. 流式：支持双向流
```

### 4.2 Go 实现 gRPC 服务

```go
package grpc

import (
    "context"
    "google.golang.org/grpc"
    "google.golang.org/grpc/metadata"
)

type GRPCServer struct {
    services map[string]*Service
}

type Service struct {
    name    string
    methods map[string]MethodHandler
}

type MethodHandler func(ctx context.Context, req interface{}) (interface{}, error)

func (gs *GRPCServer) RegisterService(name string, methods map[string]MethodHandler) {
    gs.services[name] = &Service{
        name:    name,
        methods: methods,
    }
}

func (gs *GRPCServer) Handle(ctx context.Context, service, method string, req interface{}) (interface{}, error) {
    svc, ok := gs.services[service]
    if !ok {
        return nil, fmt.Errorf("service not found: %s", service)
    }
    
    handler, ok := svc.methods[method]
    if !ok {
        return nil, fmt.Errorf("method not found: %s.%s", service, method)
    }
    
    return handler(ctx, req)
}

// 拦截器示例
func AuthInterceptor(ctx context.Context, req interface{}, info *grpc.UnaryServerInfo, handler grpc.UnaryHandler) (interface{}, error) {
    // 提取 token
    md, ok := metadata.FromIncomingContext(ctx)
    if !ok {
        return nil, status.Errorf(codes.Unauthenticated, "missing metadata")
    }
    
    tokens := md.Get("authorization")
    if len(tokens) == 0 {
        return nil, status.Errorf(codes.Unauthenticated, "missing token")
    }
    
    // 验证 token
    if !validateToken(tokens[0]) {
        return nil, status.Errorf(codes.Unauthenticated, "invalid token")
    }
    
    return handler(ctx, req)
}
```

---

## 第五部分：QUIC 深度

### 5.1 QUIC 原理

```
QUIC = UDP + TLS 1.3 + 多路复用

优势：
1. 零 RTT 握手：恢复连接时零 RTT
2. 头部加密：防止中间人
3. 连接迁移：IP 变化不中断
4. 更好的拥塞控制
```

### 5.2 Go 实现 QUIC 客户端

```go
package quic

import (
    "context"
    "crypto/tls"
    "github.com/quic-go/quic-go"
)

type QUICClient struct {
    session quic.Session
}

func NewQUICClient(addr string, config *tls.Config) (*QUICClient, error) {
    session, err := quic.DialAddr(context.Background(), addr, config, nil)
    if err != nil {
        return nil, err
    }
    
    return &QUICClient{session: session}, nil
}

func (c *QUICClient) OpenStream() (quic.Stream, error) {
    return c.session.OpenStreamSync(context.Background())
}

func (c *QUICClient) SendRequest(stream quic.Stream, req []byte) ([]byte, error) {
    _, err := stream.Write(req)
    if err != nil {
        return nil, err
    }
    
    // 读取响应
    resp := make([]byte, 4096)
    n, err := stream.Read(resp)
    if err != nil {
        return nil, err
    }
    
    return resp[:n], nil
}
```

---

## 第六部分：生产排障案例

### 6.1 TCP  TIME_WAIT 过多

```
现象：服务器 TIME_WAIT 连接数过多

排查：
1. ss -s 查看连接状态
2. netstat -an | grep TIME_WAIT

根因：短连接过多

解决方案：
1. 使用连接池
2. 开启 TCP_NODELAY
3. 调整内核参数
```

### 6.2 HTTP/2 连接冻结

```
现象：HTTP/2 连接无响应

排查：
1. 检查 GOAWAY 帧
2. 检查流优先级
3. 检查服务器负载

根因：服务器 GOAWAY

解决方案：
1. 客户端重试
2. 调整流优先级
3. 增加并发连接
```

---

## 第七部分：自测题

### 问题 1
HTTP/2 相比 HTTP/1.1 有什么优势？

<details>
<summary>查看答案</summary>

1. **多路复用**：一条连接多个请求
2. **头部压缩**：HPACK 算法
3. **服务器推送**：提前推送资源
4. **二进制帧**：更高效
5. **Go 实现**：http2.Transport

</details>

### 问题 2
gRPC 相比 RESTful API 有什么优势？

<details>
<summary>查看答案</summary>

1. **强类型**：IDL 定义
2. **高性能**：Protobuf + HTTP/2
3. **流式**：支持双向流
4. **多语言**：代码生成
5. **Go 实现**：gRPC Server

</details>

### 问题 3
QUIC 相比 TCP 有什么优势？

<details>
<summary>查看答案</summary>

1. **零 RTT**：恢复连接快速
2. **头部加密**：更安全
3. **连接迁移**：IP 变化不中断
4. **更好的拥塞控制**
5. **Go 实现**：quic-go

</details>

---

*本文档基于网络协议原理整理。*