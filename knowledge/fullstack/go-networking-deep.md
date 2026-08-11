# Go 网络编程深度解析

> 深入 Go 网络编程核心：net包源码、TCP连接管理、HTTP服务器、高性能网络模型。
> 包含 epoll/kqueue 实现和性能调优。
> 适用对象：Go工程师、网络工程师、高性能系统开发者

---

## 1. net 包源码解析

### 1.1 TCP Listener 实现

```go
// net/tcpsock.go

type TCPListener struct {
    fd *netFD
}

func (l *TCPListener) accept() (*TCPConn, error) {
    if err := l.fd.incref(); err != nil {
        return nil, err
    }
    fd, err := l.fd.accept()
    if err != nil {
        l.fd.decref()
        return nil, err
    }
    tc := newTCPConn(fd)
    tc.listener = l
    return tc, nil
}

func (fd *netFD) accept() (netfd *netFD, err error) {
    // 使用 epoll/kqueue 等待连接
    for {
        err = pollAsyncAccept(fd)
        if err == nil {
            break
        }
        if err == errTimeout || err == errInterrupted {
            continue
        }
        break
    }
    return
}
```

### 1.2 连接处理模型

```
                    accept() 调用
                        │
                        ▼
┌──────────────────────────────────────────────┐
│                 TCPListener                   │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐      │
│  │ epoll   │  │ accept  │  │ netFD   │      │
│  │ (IO复用) │──►(建连)   │──►(连接对象)│      │
│  └─────────┘  └─────────┘  └─────────┘      │
└──────────────────────────────────────────────┘
                        │
                        ▼
              ┌─────────────────────┐
              │   Goroutine 池      │
              │  (并发处理连接)      │
              └─────────────────────┘
```

---

## 2. HTTP Server 架构

### 2.1 Server 结构

```go
// net/http/server.go

type Server struct {
    Addr              string            // 监听地址
    Handler           Handler           // 请求处理器
    ReadTimeout       time.Duration     // 读取超时
    WriteTimeout      time.Duration     // 写入超时
    MaxHeaderBytes    int               // 最大请求头大小
    TLSConfig         *tls.Config       // TLS配置
    IdleTimeout       time.Duration     // 空闲超时
    ReadBufferSize    int               // 读取缓冲区
    WriteBufferSize   int               // 写入缓冲区
    
    // 连接管理
    connMu sync.Mutex
    conns map[*conn]struct{}
    
    // 服务器状态
    done chan struct{}
    closed bool
}
```

### 2.2 请求处理流程

```
客户端请求
    │
    ▼
┌─────────────────────────────────────┐
│           TCP连接处理               │
│  ┌─────────┐  ┌─────────┐         │
│  │ accept()│─►│newConn()│         │
│  └─────────┘  └─────────┘         │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│           请求解析                   │
│  ┌─────────┐  ┌─────────┐         │
│  │Read()   │─►│Parse()  │         │
│  └─────────┘  └─────────┘         │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│           路由匹配                   │
│  ┌─────────┐  ┌─────────┐         │
│  │ServeMux│─►│Handler  │         │
│  └─────────┘  └─────────┘         │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│           响应处理                   │
│  ┌─────────┐  ┌─────────┐         │
│  │Response│─►│Write()  │         │
│  └─────────┘  └─────────┘         │
└─────────────────────────────────────┘
```

### 2.3 高性能 Server 配置

```go
func NewHighPerformanceServer(addr string, handler http.Handler) *http.Server {
    return &http.Server{
        Addr:         addr,
        Handler:      handler,
        ReadTimeout:  10 * time.Second,
        WriteTimeout: 30 * time.Second,
        IdleTimeout:  60 * time.Second,
        MaxHeaderBytes: 1 << 20, // 1MB
        TLSConfig: &tls.Config{
            MinVersion: tls.VersionTLS12,
            CipherSuites: []uint16{
                tls.TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384,
                tls.TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256,
            },
        },
    }
}
```

---

## 3. 连接池设计

### 3.1 HTTP Client 连接池

```go
type Transport struct {
    mu              sync.Mutex
    idleConn        map[connectKey][]*persistConn  // 空闲连接池
    waitConn        map[waitKey][]*waitCh          // 等待连接
    maxIdleConns    int                            // 最大空闲连接
    maxIdleConnsPerHost int                          // 单主机最大空闲连接
    maxConnsPerHost int                              // 单主机最大连接数
}

type connectKey struct {
    network string
    addr    string
}

func (t *Transport) getConn(req *http.Request) (*persistConn, error) {
    key := connectKey{
        network: "tcp",
        addr:    req.URL.Host,
    }
    
    t.mu.Lock()
    // 1. 尝试复用空闲连接
    if conns := t.idleConn[key]; len(conns) > 0 {
        t.mu.Unlock()
        return conns[0], nil
    }
    
    // 2. 创建新连接
    if t.maxConnsPerHost > 0 {
        // 检查连接数限制
    }
    
    t.mu.Unlock()
    
    // 3. 建立新连接
    return t.dialConn(req)
}
```

### 3.2 连接复用策略

```go
func (p *persistConn) roundTrip(req *http.Request) (*http.Response, error) {
    // 1. 发送请求
    if err := p.writeRequest(req); err != nil {
        return nil, err
    }
    
    // 2. 读取响应
    resp, err := p.readResponse(req)
    if err != nil {
        p.close()
        return nil, err
    }
    
    // 3. 判断是否可复用
    shouldClose := shouldSendCloseHeader(req) || resp.Close
    if !shouldClose {
        p.keepAlive()
        return resp, nil
    }
    
    p.close()
    return resp, nil
}
```

---

## 4. 性能优化实战

### 4.1 高并发 Server 配置

```go
// 1. 调整goroutine数量
runtime.GOMAXPROCS(8)

// 2. 连接池配置
transport := &http.Transport{
    MaxIdleConns:        100,
    MaxIdleConnsPerHost: 10,
    IdleConnTimeout:     90 * time.Second,
    TLSHandshakeTimeout: 10 * time.Second,
}
client := &http.Client{
    Transport: transport,
    Timeout:   30 * time.Second,
}

// 3. 缓冲channel
ch := make(chan *Request, 1000)  // 缓冲1000个请求
```

### 4.2 内存优化

```go
// 1. 复用buffer
var bufPool = sync.Pool{
    New: func() interface{} {
        return new(bytes.Buffer)
    },
}

func getBuffer() *bytes.Buffer {
    return bufPool.Get().(*bytes.Buffer)
}

func putBuffer(buf *bytes.Buffer) {
    buf.Reset()
    bufPool.Put(buf)
}

// 2. 避免内存分配
func processRequest(data []byte) []byte {
    // 使用固定大小缓冲区
    var buf [4096]byte
    copy(buf[:], data)
    return buf[:]
}
```

---

## 5. 监控与调优

### 5.1 关键指标

```go
type ServerMetrics struct {
    activeConns   prometheus.Gauge
    totalRequests prometheus.Counter
    requestLatency prometheus.Histogram
    errorRate     prometheus.Gauge
}

func NewServerMetrics() *ServerMetrics {
    return &ServerMetrics{
        activeConns: prometheus.NewGauge(prometheus.GaugeOpts{
            Name: "active_connections",
            Help: "Current active connections",
        }),
        totalRequests: prometheus.NewCounter(prometheus.CounterOpts{
            Name: "total_requests",
            Help: "Total number of requests",
        }),
        requestLatency: prometheus.NewHistogram(prometheus.HistogramOpts{
            Name:    "request_latency_seconds",
            Help:    "Request latency in seconds",
            Buckets: prometheus.DefBuckets,
        }),
        errorRate: prometheus.NewGauge(prometheus.GaugeOpts{
            Name: "error_rate",
            Help: "Current error rate",
        }),
    }
}
```

### 5.2 性能调优 Checklist

- [ ] 设置合适的 GOMAXPROCS
- [ ] 配置连接池大小
- [ ] 设置合理的超时时间
- [ ] 启用 HTTP/2
- [ ] 使用缓冲 channel
- [ ] 复用对象（sync.Pool）
- [ ] 监控关键指标

---

## 6. 总结

### 6.1 核心原理回顾

| 组件 | 核心机制 | 关键优化点 |
|------|----------|-----------|
| TCP Listener | epoll/kqueue | 连接池管理 |
| HTTP Server | 请求解析+路由 | 并发控制 |
| 连接复用 | keep-alive | 减少建连开销 |
| 缓冲池 | sync.Pool | 减少GC压力 |

### 6.2 性能指标目标

| 指标 | 目标值 |
|------|--------|
| 连接数 | > 10K |
| QPS | > 50K |
| P99 延迟 | < 50ms |
| CPU 使用率 | < 70% |

---

*最后更新：2026-08-11*
*作者：Ryan*
