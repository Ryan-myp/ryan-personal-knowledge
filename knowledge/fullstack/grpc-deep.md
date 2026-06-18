# gRPC 深度：传输/流控/拦截器源码级

> 逐行解析 gRPC 核心组件：HTTP/2 传输、流控、拦截器

---

## 第一部分：HTTP/2 传输源码深度

### HTTP/2 帧结构

```
HTTP/2 帧（Frame）：
┌─────────────────────────────────────────────────────────────────────┐
│ Frame Header (9 bytes)                                               │
│ ├── Length (24 bits): 载荷长度                                      │
│ ├── Type (8 bits): 帧类型                                           │
│ │   ├── 0x0: DATA                                                   │
│ │   ├── 0x1: HEADERS                                                │
│ │   ├── 0x2: PRIORITY                                             │
│ │   ├── 0x3: RST_STREAM                                             │
│ │   ├── 0x4: SETTINGS                                               │
│ │   ├── 0x5: PUSH_PROMISE                                           │
│ │   ├── 0x6: PING                                                   │
│ │   ├── 0x7: GOAWAY                                                 │
│ │   └── 0x8: WINDOW_UPDATE                                          │
│ ├── Flags (8 bits): 标志位                                          │
│ │   ├── 0x1: END_STREAM                                             │
│ │   └── 0x4: END_HEADERS                                            │
│ ├── R (1 bit): 保留位                                               │
│ └── Stream ID (31 bits): 流标识符                                   │
│                                                                     │
│ Frame Payload (可变长度)                                             │
│                                                                     │
│ 多路复用：                                                           │
│ • 一个 TCP 连接可并行多个 HTTP/2 Stream                              │
│ • Stream ID 奇数 = 客户端发起，偶数 = 服务端发起                     │
│ • Stream 0 = 控制流（SETTINGS/PING/GOAWAY）                         │
└─────────────────────────────────────────────────────────────────────┘
```

### http2_server.go 源码逐行解析

```go
// gRPC 源码：transport/http2_server.go
type http2Server struct {
    conn            net.Conn
    mu              sync.Mutex
    remoteAddr      net.Addr
    localAddr       net.Addr
    maxStreamID     uint32
    maxSendLength   int
    maxReceiveLength int
    writableChan    chan struct{}
    drainChan       chan struct{}
    state           transportState
    writer          io.Writer
    framer          *framer
    hBuf            *bytes.Buffer
    bufWriter       *bufio.Writer
    initialWindowSize uint32
    bdpEst          *bdpEstimator
    streams         map[uint32]*stream
    activeStreams   map[uint32]struct{}
    recvMsgs        chan struct{}
    done            chan struct{}
    controlBuf      *controlBuffer
    stats           []stats.Handler
    keepParams      keepalive.Parameters
    keepalivePolicy keepalive.EnforcementPolicy
    inboundBytes    int64
    outboundBytes   int64
}

// newHTTP2Transport 创建 HTTP/2 传输
func newHTTP2Transport(conn net.Conn, config *ServerConfig) (transport.Transport, error) {
    s := &http2Server{
        conn:            conn,
        state:         readable,
        writableChan:  make(chan struct{}, 1),
        drainChan:     make(chan struct{}),
        streams:       make(map[uint32]*stream),
        activeStreams: make(map[uint32]struct{}),
        done:          make(chan struct{}),
        controlBuf:    newControlBuffer(),
        stats:         config.StatsHandlers,
    }
    
    // 1. 初始化 framer
    s.framer = newFramer(conn, config.WriteBufferSize, config.ReadBufferSize)
    
    // 2. 初始化 bdp estimator
    s.bdpEst = &bdpEstimator{
        delta: 0,
        threshold: int64(config.InitialWindowSize),
    }
    
    // 3. 启动 reader goroutine
    go func() {
        s.readLoop()
        close(s.done)
    }()
    
    // 4. 启动 writer goroutine
    go func() {
        s.writeLoop()
    }()
    
    return s, nil
}

// readLoop 读取 HTTP/2 帧
func (s *http2Server) readLoop() {
    for {
        // 1. 读取 frame header
        frame, err := s.framer.readFrame()
        if err != nil {
            s.closeForErr(err)
            return
        }
        
        // 2. 处理不同类型的 frame
        switch frame := frame.(type) {
        case *http2.MetaHeadersFrame:
            // 2.1 处理 HEADERS frame（新请求）
            s.handleStream(frame)
            
        case *http2.DataFrame:
            // 2.2 处理 DATA frame（消息体）
            s.handleData(frame)
            
        case *http2.WindowUpdateFrame:
            // 2.3 处理 WINDOW_UPDATE frame（流控）
            s.handleWindowUpdate(frame)
            
        case *http2.SettingsFrame:
            // 2.4 处理 SETTINGS frame
            s.handleSettings(frame)
            
        case *http2.PingFrame:
            // 2.5 处理 PING frame
            s.handlePing(frame)
            
        case *http2.GoAwayFrame:
            // 2.6 处理 GOAWAY frame
            s.closeForErr(errors.New("received GOAWAY"))
            return
            
        case *http2.RSTStreamFrame:
            // 2.7 处理 RST_STREAM frame
            s.handleRSTStream(frame)
        }
    }
}

// handleStream 处理新流
func (s *http2Server) handleStream(frame *http2.MetaHeadersFrame) {
    streamID := frame.StreamID
    
    // 1. 创建 stream
    st := &stream{
        id:        streamID,
        state:     active,
        headerBuf: &bytes.Buffer{},
    }
    
    // 2. 解析 headers
    for _, hf := range frame.Fields {
        switch hf.Name {
        case ":method":
            st.method = hf.Value
        case ":path":
            st.path = hf.Value
        case "content-type":
            st.contentType = hf.Value
        case "grpc-timeout":
            st.timeout = hf.Value
        }
    }
    
    // 3. 添加到 active streams
    s.mu.Lock()
    s.streams[streamID] = st
    s.activeStreams[streamID] = struct{}{}
    s.mu.Unlock()
    
    // 4. 通知 caller
    select {
    case s.recvMsgs <- struct{}{}:
    default:
    }
}
```

---

## 第二部分：流控源码深度

### 流控层次

```
gRPC 流控层次：
┌─────────────────────────────────────────────────────────────────────┐
│ 1. Connection Level Flow Control (TCP)                               │
│    • TCP 滑动窗口（默认 64KB-1MB）                                    │
│    • 拥塞控制                                                        │
│                                                                     │
│ 2. Stream Level Flow Control (HTTP/2)                               │
│    • WINDOW_UPDATE frame                                             │
│    • 每个 stream 独立窗口（默认 64KB）                                │
│    • 接收方发送 WINDOW_UPDATE 增加窗口                                │
│                                                                     │
│ 3. Application Level Flow Control (gRPC)                            │
│    • SendQuota: 发送配额                                              │
│    • RecvQuota: 接收配额                                              │
│    • 超出配额时阻塞                                                   │
└─────────────────────────────────────────────────────────────────────┘
```

### flow.go 源码逐行解析

```go
// gRPC 源码：transport/flow.go
type flow control

// flow 结构
type flow struct {
    mu      sync.Mutex
    // 已发送但未收到 ACK 的字节数
    unsent  int32
    // 已接收但未处理的字节数
    unread  int32
    // 流控限制
    limit   int32
    // 等待流控的 goroutine 队列
    waiting []chan struct{}
}

// newFlow 创建流控器
func newFlow(limit int32) *flow {
    return &flow{
        limit: limit,
    }
}

// add 增加未处理字节数
func (f *flow) add(n int32) {
    f.mu.Lock()
    defer f.mu.Unlock()
    
    f.unread += n
    
    // 检查是否超过限制
    if f.unread > f.limit {
        // 通知等待的 goroutine
        for _, ch := range f.waiting {
            close(ch)
        }
        f.waiting = nil
    }
}

// tryUpdate 尝试更新流控状态
func (f *flow) tryUpdate(need int32) (int32, bool) {
    f.mu.Lock()
    defer f.mu.Unlock()
    
    // 检查是否有足够的配额
    if f.unsent+need > f.limit {
        return 0, false
    }
    
    f.unsent += need
    return need, true
}

// release 释放配额
func (f *flow) release(n int32) {
    f.mu.Lock()
    defer f.mu.Unlock()
    
    f.unsent -= n
    
    // 如果有等待的 goroutine，唤醒它们
    if len(f.waiting) > 0 {
        for _, ch := range f.waiting {
            close(ch)
        }
        f.waiting = nil
    }
}

// wait 等待流控
func (f *flow) wait() {
    f.mu.Lock()
    defer f.mu.Unlock()
    
    if f.unsent < f.limit {
        return
    }
    
    // 创建新的 channel
    ch := make(chan struct{})
    f.waiting = append(f.waiting, ch)
    
    f.mu.Unlock()
    <-ch // 阻塞直到流控
    f.mu.Lock()
}
```

---

## 第三部分：拦截器源码深度

### 拦截器架构

```
gRPC 拦截器链：
Client:
  ClientInterceptor1 → ClientInterceptor2 → RPC

Server:
  RPC → ServerInterceptor1 → ServerInterceptor2 → Handler

类型：
• Unary: 单向调用
• Stream: 流式调用
• Client: 客户端拦截器
• Server: 服务端拦截器
```

### interceptor.go 源码逐行解析

```go
// gRPC 源码：grpc/interceptor.go
type UnaryInterceptor func(ctx context.Context, method string, req, reply interface{}, cc *ClientConn, invoker UnaryInvoker, opts ...CallOption) error

// ClientUnaryInvoker 客户端调用器
type ClientUnaryInvoker func(ctx context.Context, method string, req, reply interface{}, cc *ClientConn, opts ...CallOption) error

// ChainUnaryClient 链式客户端拦截器
func ChainUnaryClient(interceptors ...UnaryClientInterceptor) UnaryClientInterceptor {
    n := len(interceptors)
    if n == 0 {
        return func(ctx context.Context, method string, req, reply interface{}, cc *ClientConn, invoker UnaryClientInvoker, opts ...CallOption) error {
            return invoker(ctx, method, req, reply, cc, opts...)
        }
    }
    
    return func(ctx context.Context, method string, req, reply interface{}, cc *ClientConn, invoker UnaryClientInvoker, opts ...CallOption) error {
        // 从后往前包装
        chain := invoker
        for i := n - 1; i >= 0; i-- {
            finalInvoker := chain
            chain = func(ctx context.Context, method string, req, reply interface{}, cc *ClientConn, opts ...CallOption) error {
                return interceptors[i](ctx, method, req, reply, cc, finalInvoker, opts...)
            }
        }
        return chain(ctx, method, req, reply, cc, opts...)
    }
}

// ServerUnaryInvoker 服务端调用器
type ServerUnaryInvoker func(ctx context.Context, req interface{}, desc *StreamDesc, cc *Server) (interface{}, error)

// ChainUnaryServer 链式服务端拦截器
func ChainUnaryServer(interceptors ...UnaryServerInterceptor) UnaryServerInterceptor {
    n := len(interceptors)
    if n == 0 {
        return func(ctx context.Context, req interface{}, desc *StreamDesc, srv *Server, handler UnaryHandler, opts ...CallOption) error {
            return handler(ctx, req)
        }
    }
    
    return func(ctx context.Context, req interface{}, desc *StreamDesc, srv *Server, handler UnaryHandler, opts ...CallOption) error {
        chain := handler
        for i := 0; i < n; i++ {
            finalHandler := chain
            chain = func(ctx context.Context, req interface{}) (interface{}, error) {
                return interceptors[i](ctx, req, desc, srv, finalHandler, opts...)
            }
        }
        return chain(ctx, req)
    }
}
```

---

## 第四部分：自测题

### Q1: gRPC 为什么用 HTTP/2 而不用 HTTP/1.1？

**A**:
- **多路复用**: 一个连接多个 stream
- **二进制帧**: 解析更快
- **头部压缩**: HPACK 减少开销
- **流控**: 内置流控机制
- **服务器推送**: 支持服务端主动推送

### Q2: gRPC 流控的原理？

**A**: 三层流控（TCP → HTTP/2 WINDOW_UPDATE → gRPC application level）。超出配额时阻塞，收到 WINDOW_UPDATE 后恢复。

### Q3: 拦截器的执行顺序？

**A**: 客户端从外到内，服务端从内到外。类似洋葱模型。

---

## 第五部分：生产实践

### 1. 性能调优

```
性能调优要点：
1. 合理设置 WriteBufferSize（默认 32KB）
2. 合理设置 ReadBufferSize（默认 32KB）
3. 启用 gzip 压缩
4. 使用 keepalive 检测死连接
```

### 2. 流控调优

```
流控调优要点：
1. 调整 initial_window_size（默认 64KB）
2. 监控 flow control pressure
3. 避免大消息（> 4MB）
```

### 3. 拦截器最佳实践

```
拦截器最佳实践：
1. 统一日志格式
2. 统一鉴权逻辑
3. 统一限流
4. 统一错误处理
```
