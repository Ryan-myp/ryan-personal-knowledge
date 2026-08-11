# Go 网络编程深度解析

> 深入 Go 网络编程：net包源码、TCP/IP、HTTP/2、连接池。
> 源码级分析，包含性能调优。
> 适用对象：Go 工程师、后端工程师

---

## 1. net包架构

### 1.1 核心组件

```
┌─────────────────────────────────────────────────────────────┐
│                    Go net 包架构                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  网络抽象层                                                   │
│  ├── Dialer: 连接创建                                        │
│  ├── Listener: 监听器                                        │
│  └── Conn: 连接接口                                          │
│                                                             │
│  TCP 实现                                                     │
│  ├── netFD: 文件描述符封装                                   │
│  ├── tcpSocket: 套接字操作                                   │
│  └── tcp.go: TCP 连接管理                                    │
│                                                             │
│  协议栈                                                       │
│  ├── ip.go: IP 协议处理                                      │
│  ├── icmp.go: ICMP 协议                                     │
│  └── udp.go: UDP 协议                                        │
│                                                             │
│  DNS 解析                                                     │
│  ├── lookup.go: 域名解析                                     │
│  ├── host.go: 主机名处理                                     │
│  └── cgo_lookup.go: 系统调用                                 │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 连接生命周期

```
创建连接 → 建立连接 → 数据传输 → 关闭连接

1. Dial() 创建连接
2. syscall socket() 创建套接字
3. syscall connect() 建立连接
4. netFD.init() 初始化
5. 数据传输（Read/Write）
6. Close() 关闭连接
```

---

## 2. TCP 连接

### 2.1 TCP 三次握手

```
客户端                           服务器
  │                               │
  │──── SYN (seq=100) ──────────▶│
  │                               │
  │◀─── SYN+ACK (seq=200, ack=101)│
  │                               │
  │──── ACK (seq=101, ack=201) ──▶│
  │                               │
  └────────── 连接建立 ───────────┘
```

### 2.2 Go 实现 TCP 服务器

```go
// tcp_server.go

package network

import (
    "net"
    "sync"
)

type TCPServer struct {
    listener    net.Listener
    connections sync.Map
}

func NewTCPServer(addr string) (*TCPServer, error) {
    listener, err := net.Listen("tcp", addr)
    if err != nil {
        return nil, err
    }
    return &TCPServer{listener: listener}, nil
}

func (s *TCPServer) Start() {
    for {
        conn, err := s.listener.Accept()
        if err != nil {
            continue
        }
        s.connections.Store(conn.RemoteAddr().String(), conn)
        go s.handle(conn)
    }
}

func (s *TCPServer) handle(conn net.Conn) {
    defer conn.Close()
    buf := make([]byte, 4096)
    for {
        n, err := conn.Read(buf)
        if err != nil {
            return
        }
        // 处理请求
    }
}
```

---

## 3. HTTP/2

### 3.1 HTTP/2 特性

```
HTTP/2 主要特性：

1. 多路复用
   - 多个请求复用同一个 TCP 连接
   - 避免队头阻塞

2. 头部压缩
   - HPACK 算法压缩头部
   - 减少传输开销

3. 服务器推送
   - 服务器主动推送资源
   - 减少客户端请求

4. 二进制分帧
   - 所有通信都是二进制格式
   - 更高效解析
```

### 3.2 Go HTTP/2 实现

```go
// http2_server.go

package network

import (
    "net/http"
    "crypto/tls"
)

func StartHTTP2Server(addr string, handler http.Handler) error {
    // 需要 TLS
    config := &tls.Config{
        NextProtos: []string{"h2"},
    }
    
    listener, err := net.Listen("tcp", addr)
    if err != nil {
        return err
    }
    
    tlsListener := tls.NewListener(listener, config)
    
    server := &http.Server{
        Handler: handler,
    }
    
    return server.Serve(tlsListener)
}
```

---

## 4. 连接池

### 4.1 连接池设计

```
┌─────────────────────────────────────────────────────────────┐
│                    连接池架构                                │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │  Client     │───►│  Pool       │───►│  Connections│     │
│  │  (调用方)    │    │  (连接池)    │    │  (连接集合)  │     │
│  └─────────────┘    └─────────────┘    └─────────────┘     │
│                                                             │
│  操作流程：                                                  │
│  1. Client 请求连接                                          │
│  2. Pool 从连接集合获取空闲连接                               │
│  3. 如果没有空闲连接，创建新连接（有限制）                     │
│  4. Client 使用连接                                          │
│  5. 归还连接到 Pool                                          │
│  6. Pool 回收空闲连接                                        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 Go 实现连接池

```go
// connection_pool.go

package pool

import (
    "net"
    "sync"
    "time"
)

type ConnectionPool struct {
    create    func() (net.Conn, error)
    close     func(net.Conn) error
    maxSize   int
    idleTimeout time.Duration
    mu        sync.Mutex
    conns     []*connItem
    waitQueue chan struct{}
}

type connItem struct {
    conn      net.Conn
    lastUsed  time.Time
}

func NewConnectionPool(
    create func() (net.Conn, error),
    close func(net.Conn) error,
    maxSize int,
    idleTimeout time.Duration,
) *ConnectionPool {
    return &ConnectionPool{
        create:      create,
        close:       close,
        maxSize:     maxSize,
        idleTimeout: idleTimeout,
        waitQueue:   make(chan struct{}, maxSize),
    }
}

func (p *ConnectionPool) Get() (net.Conn, error) {
    p.mu.Lock()
    defer p.mu.Unlock()
    
    // 查找空闲连接
    for i, item := range p.conns {
        if time.Since(item.lastUsed) < p.idleTimeout {
            conn := p.conns[i]
            p.conns = append(p.conns[:i], p.conns[i+1:]...)
            return conn.conn, nil
        }
    }
    
    // 创建新连接
    if len(p.conns) < p.maxSize {
        conn, err := p.create()
        if err != nil {
            return nil, err
        }
        return conn, nil
    }
    
    // 等待
    select {
    case <-p.waitQueue:
        return p.Get()
    case <-time.After(time.Second * 5):
        return nil, ErrTimeout
    }
}

func (p *ConnectionPool) Put(conn net.Conn) {
    p.mu.Lock()
    defer p.mu.Unlock()
    
    p.conns = append(p.conns, &connItem{
        conn:     conn,
        lastUsed: time.Now(),
    })
}

func (p *ConnectionPool) Close() error {
    p.mu.Lock()
    defer p.mu.Unlock()
    
    var err error
    for _, item := range p.conns {
        if p.close != nil {
            if e := p.close(item.conn); e != nil {
                err = e
            }
        }
    }
    p.conns = p.conns[:0]
    return err
}
```

---

## 5. 性能优化

### 5.1 优化策略

```
网络性能优化：

1. 连接复用
   - HTTP Keep-Alive
   - 连接池

2. 缓冲优化
   - 合理设置缓冲区大小
   - 减少系统调用

3. 并发优化
   - Goroutine 池
   - 异步 I/O

4. 协议优化
   - HTTP/2 多路复用
   - 头部压缩
```

### 5.2 Go 网络编程最佳实践

```go
// best_practices.go

package network

import (
    "context"
    "net"
    "net/http"
    "time"
)

// 1. 设置超时
func createClient() *http.Client {
    return &http.Client{
        Timeout: 5 * time.Second,
        Transport: &http.Transport{
            DialContext: func(ctx context.Context, network, addr string) (net.Conn, error) {
                dialer := &net.Dialer{
                    Timeout:   3 * time.Second,
                    KeepAlive: 30 * time.Second,
                }
                return dialer.DialContext(ctx, network, addr)
            },
            MaxIdleConns:        100,
            MaxIdleConnsPerHost: 10,
            IdleConnTimeout:     90 * time.Second,
        },
    }
}

// 2. 使用缓冲
func readWithBuffer(conn net.Conn) ([]byte, error) {
    buf := make([]byte, 4096)
    n, err := conn.Read(buf)
    if err != nil {
        return nil, err
    }
    return buf[:n], nil
}
```

---

## 6. 监控与调试

### 6.1 网络指标

```go
// metrics.go

package network

import "github.com/prometheus/client_golang/prometheus"

type NetworkMetrics struct {
    connections     prometheus.Gauge
    requestsTotal   prometheus.Counter
    requestDuration prometheus.Histogram
    errorsTotal     prometheus.Counter
}

func NewNetworkMetrics() *NetworkMetrics {
    return &NetworkMetrics{
        connections: prometheus.NewGauge(prometheus.GaugeOpts{
            Name: "network_connections",
            Help: "Current connections",
        }),
        requestsTotal: prometheus.NewCounter(prometheus.CounterOpts{
            Name: "network_requests_total",
            Help: "Total requests",
        }),
        requestDuration: prometheus.NewHistogram(prometheus.HistogramOpts{
            Name:    "network_request_duration_seconds",
            Help:    "Request duration",
            Buckets: []float64{0.01, 0.05, 0.1, 0.5, 1.0},
        }),
        errorsTotal: prometheus.NewCounter(prometheus.CounterOpts{
            Name: "network_errors_total",
            Help: "Total errors",
        }),
    }
}
```

---

## 7. 总结

### 7.1 核心原理回顾

| 模块 | 核心机制 |
|------|----------|
| TCP | 三次握手/四次挥手 |
| HTTP/2 | 多路复用/头部压缩 |
| 连接池 | 复用/超时回收 |
| 性能优化 | 缓冲/并发/协议 |

### 7.2 最佳实践

- [ ] 设置合理超时
- [ ] 使用连接池
- [ ] 缓冲优化
- [ ] 监控关键指标
- [ ] 错误处理完善

---

*最后更新：2026-08-11*
*作者：Ryan*
