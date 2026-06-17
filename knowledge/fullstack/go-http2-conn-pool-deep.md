# Go 网络编程深度：HTTP/2 协议实现 + TCP 连接池

> 从 HTTP/1.1 到 HTTP/2 的协议演进 + Go 连接池源码解析

---

## 第一部分：HTTP/1.1 vs HTTP/2

### HTTP/1.1 的问题

```
HTTP/1.1 的三大痛点：

1. 队头阻塞（Head-of-Line Blocking）：
   浏览器对同一域名最多 6 个并发连接
   请求 1（大文件）→ 请求 2（小图片）→ 请求 3（API）
   请求 1 没完，请求 2 和 3 都在排队
   
2. 头部冗余：
   Cookie: xxx
   User-Agent: Mozilla/5.0
   Accept: */*
   → 每个请求都重复发送，浪费带宽
   
3. 二进制解析困难：
   HTTP/1.1 是纯文本，解析慢且易出错

HTTP/2 的解决方案：
1. 多路复用：一个连接，多个流（Stream）
2. 头部压缩：HPACK 算法
3. 二进制帧：解析更快，更可靠
```

### HTTP/2 帧结构

```
HTTP/2 二进制帧：
┌─────────────────────────────────────────────────┐
│                  Frame Header (9 bytes)           │
│  Length (24 bits) | Type (8 bits) | Flags (8 bits)|
│  R (1 bit) | Stream ID (31 bits)                 │
├─────────────────────────────────────────────────┤
│                  Frame Payload                    │
│  (可变长度)                                       │
└─────────────────────────────────────────────────┘

Frame 类型：
├── DATA          → 传输请求/响应体
├── HEADERS       → 传输头部（HPACK 压缩）
├── PRIORITY      → 流优先级
├── RST_STREAM    → 重置流
├── SETTINGS      → 连接参数协商
├── PUSH_PROMISE  → 服务端推送
├── PING          → 连接保活
└── WINDOW_UPDATE → 流量控制
```

---

## 第二部分：Go HTTP/2 源码深度

### 源码逐行解析：http2.Server.ServeConn

```go
// Go 源码：net/http/h2_bundle.go - Server.ServeConn
// 处理一个 HTTP/2 连接

func (srv *Server) ServeConn(nc net.Conn, opts ServeConnOpts) error {
    // 1. 创建 conn 结构体
    sconn := &conn{
        srv:            srv,
        nc:             nc,
        rw:             &connReaderWriter{nc: nc},
        readerDone:     make(chan struct{}),
        frc:            &frameReadController{},
        peerMaxHeaderListSize: 0xffffffff, // 默认无限
        streamMap:      make(map[uint32]*stream),
        writeBuf:       newBufWriter(nc),
        writeScheduler: newWriteScheduler(),
    }
    
    // 2. 读取 CONNECTION PREFACE
    // 每个 HTTP/2 连接必须以 "PRI * HTTP/2.0\r\n\r\nSM\r\n\r\n" 开头
    if _, err := io.ReadFull(nc, sconn.prefaceBuf[:]); err != nil {
        return err
    }
    if !bytes.Equal(sconn.prefaceBuf, preface) {
        return errors.New("http2: invalid connection preface")
    }
    
    // 3. 读取 SETTINGS frame
    settings, err := sconn.readSettings()
    if err != nil {
        return err
    }
    
    // 4. 应用客户端设置的参数
    sconn.applyClientSettings(settings)
    
    // 5. 发送 SERVER PREFACE + SETTINGS frame
    sconn.writeConnectionPreface()
    sconn.writeSettings(srv.initialSettings())
    
    // 6. 启动读写循环
    go sconn.readFrames()  // 读取帧
    sconn.writeLoop()      // 写入帧
    
    // 7. 处理请求
    for {
        frame, err := sconn.readFrame()
        if err != nil {
            return err
        }
        
        switch f := frame.(type) {
        case *settingsFrame:
            sconn.handleSettings(f)
        case *headersFrame:
            sconn.handleHeaders(f)  // 创建新流
        case *dataFrame:
            sconn.handleData(f)     // 处理请求体
        case *windowUpdateFrame:
            sconn.handleWindowUpdate(f)
        case *goAwayFrame:
            return nil
        }
    }
}
```

**关键点**：
- **CONNECTION PREFACE**：HTTP/2 连接必须以特定字节序列开头
- **SETTINGS 协商**：双方协商最大帧大小、并发流数等参数
- **读写循环分离**：读帧和写帧在独立 goroutine 中

### 源码逐行解析：writeFrameSync

```go
// Go 源码：net/http/h2_bundle.go
// writeFrameSync — 同步写入帧（保证顺序）

func (s *conn) writeFrameSync(f Frame) error {
    // 1. 将帧写入 writeBuffer
    if err := f.write(s.writeBuf); err != nil {
        return err
    }
    
    // 2. 刷新 buffer，确保数据写入 socket
    if err := s.writeBuf.flush(); err != nil {
        return err
    }
    
    // 3. 更新流量控制窗口
    if data, ok := f.(*dataFrame); ok {
        s.incrRemainingReadQuota(int64(len(data.payload)))
    }
    
    return nil
}
```

### HPACK 头部压缩

```
HPACK 压缩原理：

静态表（61 个常用头部）：
┌─────────────────────────────────────────────┐
│ 0     :authority                            │
│ 1     :method GET                           │
│ 2     :method POST                          │
│ 3     :scheme http                          │
│ 4     :scheme https                         │
│ ...                                         │
│ 60    x-forwarded-proto                     │
└─────────────────────────────────────────────┘

动态表（协商大小，默认 4KB）：
┌─────────────────────────────────────────────┐
│ [0] Cookie: session=abc123                  │
│ [1] User-Agent: Go-http-client/2.0          │
│ [2] Content-Type: application/json          │
└─────────────────────────────────────────────┘

编码示例：
原始头部：
  :method: GET
  :path: /api/users
  cookie: session=abc123

HPACK 编码：
  0x82 → :method: GET (静态表索引 1，Huffman 编码)
  0x41 → :path: /api/users (索引 4 = 0x40 + 1，增量索引)
  0x5d → cookie: session=abc123 (动态表索引 0，Huffman)

解码：
  接收方维护同样的静态表和动态表
  收到 0x82 → 查静态表 → :method: GET
  收到 0x41 → 查动态表 → :path: /api/users
```

---

## 第三部分：TCP 连接池源码深度

### 连接池架构

```
http.Transport 连接池：
┌─────────────────────────────────────────────────┐
│              http.Transport                      │
│                                                  │
│  dialer: net.Dialer                              │
│  Proxy: HTTP CONNECT                             │
│  TLSClientConfig: tls.Config                     │
│                                                  │
│  ┌──────────────────────────────────────────┐   │
│  │        idleConnMap                       │   │
│  │  key: "host:port"                        │   │
│  │  value: []*persistConn                   │   │
│  └──────────────────────────────────────────┘   │
│                                                  │
│  限制：                                          │
│  MaxIdleConns: 100（默认）                       │
│  MaxIdleConnsPerHost: 2（默认）                  │
│  IdleConnTimeout: 90s（默认）                    │
│  DisableKeepAlives: false                        │
└─────────────────────────────────────────────────┘
```

### 源码逐行解析：Transport.getConn

```go
// Go 源码：net/http/transport.go
// Transport.getConn — 从连接池获取或创建连接

func (t *Transport) getConn(treq *transportRequest, cm connectMethod) (*persistConn, error) {
    // 1. 尝试从 idleConnMap 获取空闲连接
    conn, wait, done := t.getIdleConn(cm)
    if conn != nil {
        return conn, nil
    }
    if wait {
        // 2. 有连接正在被获取，等待
        ch := make(chan *persistConn)
        t.getIdleConnWait(cm, ch)
        select {
        case conn := <-ch:
            return conn, nil
        case <-treq.ctx.Done():
            return nil, treq.ctx.Err()
        }
    }
    
    // 3. 没有空闲连接，创建新连接
    conn, err := t.dialConn(treq, cm)
    if err != nil {
        return nil, err
    }
    
    return conn, nil
}

// getIdleConn — 获取空闲连接
func (t *Transport) getIdleConn(cm connectMethod) (*persistConn, bool, func()) {
    t.mu.Lock()
    defer t.mu.Unlock()
    
    // 1. 查找 key
    key := cm.key()
    conns, ok := t.idleConn[key]
    if !ok || len(conns) == 0 {
        return nil, false, nil
    }
    
    // 2. 取第一个空闲连接
    conn := conns[0]
    t.idleConn[key] = conns[1:]
    
    // 3. 检查连接是否过期
    if time.Now().After(conn.idleAt.Add(t.IdleConnTimeout)) {
        // 连接过期，关闭
        go conn.close()
        return nil, false, nil
    }
    
    // 4. 返回连接 + 释放函数
    done := func() {
        t.mu.Lock()
        defer t.mu.Unlock()
        // 放回 idleConnMap
        t.idleConn[key] = append(t.idleConn[key], conn)
    }
    
    return conn, false, done
}
```

**关键点**：
- **idleConnMap**：key 为 "host:port"，value 为空闲连接切片
- **MaxIdleConnsPerHost**：默认每个主机最多 2 个空闲连接
- **IdleConnTimeout**：默认 90s，超时自动关闭

### 源码逐行解析：persistConn.roundTrip

```go
// Go 源码：net/http/transport.go
// persistConn.roundTrip — 发送 HTTP 请求

func (t *Transport) roundTrip(req *Request) (*Response, error) {
    // 1. 获取连接
    pc, err := t.getConn(req, t.connectMethodForRequest(req))
    if err != nil {
        return nil, err
    }
    
    // 2. 发送请求
    if err := pc.writeRequest(req, t.reqCh); err != nil {
        return nil, err
    }
    
    // 3. 等待响应
    resp, err := pc.readResponse(req)
    if err != nil {
        // 4. 如果响应读取失败，连接放入 deadPool
        pc.close()
        return nil, err
    }
    
    // 5. 根据 Connection: close 决定是否放回连接池
    if req.Close || resp.Close {
        pc.close()
    } else {
        // 6. 放回 idleConnMap
        t.putIdleConn(pc)
    }
    
    return resp, nil
}
```

---

## 第四部分：连接池调优

### 关键参数

| 参数 | 默认值 | 含义 | 调优建议 |
|------|--------|------|---------|
| **MaxIdleConns** | 100 | 全局最大空闲连接 | 高 QPS 服务增加到 200-500 |
| **MaxIdleConnsPerHost** | 2 | 每个 host 最大空闲连接 | 增加到 10-50（高并发） |
| **IdleConnTimeout** | 90s | 空闲连接超时 | 减少到 30s（节省资源） |
| **DisableKeepAlives** | false | 是否禁用 keep-alive | 始终 false（除非特殊场景） |
| **TLSHandshakeTimeout** | 10s | TLS 握手超时 | 减少到 5s（快速失败） |
| **ResponseHeaderTimeout** | 0 | 响应头超时 | 设置为 30s |

### Go 标准库 vs fasthttp 对比

```
标准库 net/http：
- 基于 net.Conn，每连接一个 goroutine
- 连接池管理完善
- 支持 HTTP/1.1 + HTTP/2
- 吞吐：~10K QPS（单核）

fasthttp：
- 无 goroutine 分配，零 GC 压力
- 自定义连接池
- 仅支持 HTTP/1.1
- 吞吐：~100K QPS（单核）

选择建议：
- 通用场景：net/http（生态完善）
- 极致性能：fasthttp（牺牲 HTTP/2）
- 微服务：net/http（gRPC 原生支持）
```

---

## 第五部分：自测题

### Q1: HTTP/2 多路复用如何避免队头阻塞？

**A**: HTTP/2 在一个 TCP 连接上建立多个 Stream，每个 Stream 独立编号。HEADERS 和 DATA frame 可以交错传输，接收方根据 Stream ID 重组。但 TCP 层的队头阻塞仍然存在（丢包时整个连接阻塞），所以 HTTP/3（QUIC）改用 UDP 避免这个问题。

### Q2: MaxIdleConnsPerHost 为什么默认是 2？

**A**: 保守设计。大多数网站不需要太多并发连接。2 个连接足够处理 1 个请求 + 1 个预取。增加这个值会消耗更多服务器资源（文件描述符、内存）。

### Q3: HTTP/2 的 SETTINGS 帧可以协商什么？

**A**:
- SETTINGS_HEADER_TABLE_SIZE：动态表大小
- SETTINGS_ENABLE_PUSH：是否启用服务端推送
- SETTINGS_MAX_CONCURRENT_STREAMS：最大并发流数
- SETTINGS_INITIAL_WINDOW_SIZE：流量控制窗口
- SETTINGS_MAX_FRAME_SIZE：最大帧大小

---

## 第六部分：生产排障

### 1. 连接泄漏

```go
// 症状：文件描述符持续增长
// 排查：
import _ "net/http/pprof"
// http://localhost:6060/debug/pprof/heap

// 解决：
// 1. 确保 resp.Body.Close()
// 2. 设置 Transport 参数
// 3. 使用 context 超时
```

### 2. HTTP/2 连接复用失败

```bash
# 检查是否用了 HTTP/2
curl -v --http2 https://example.com

# 常见问题：
# 1. 代理不支持 HTTP/2
# 2. TLS 配置不正确
# 3. 连接数超过 MAX_CONCURRENT_STREAMS
```

### 3. 连接池打满

```go
// 症状：请求阻塞，等待连接
// 排查：
// 1. 增加 MaxIdleConnsPerHost
// 2. 检查是否有长连接未释放
// 3. 优化请求处理时间
```
