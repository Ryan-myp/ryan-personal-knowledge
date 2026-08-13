# Go网络编程 - 资深专家深度实现

## 一、TCP编程模型

### 1.1 Server模型

```go
package tcp

import (
	"bufio"
	"fmt"
	"net"
)

func StartServer(port string) {
	listener, err := net.Listen("tcp", ":"+port)
	if err != nil {
		panic(err)
	}
	defer listener.Close()
	
	fmt.Printf("Server listening on port %s\n", port)
	
	for {
		conn, err := listener.Accept()
		if err != nil {
			continue
		}
		go handleConnection(conn)
	}
}

func handleConnection(conn net.Conn) {
	defer conn.Close()
	
	scanner := bufio.NewScanner(conn)
	for scanner.Scan() {
		line := scanner.Text()
		fmt.Printf("Received: %s\n", line)
		
		// 回显
		conn.Write([]byte("Echo: " + line + "\n"))
	}
}
```

### 1.2 Client模型

```go
func StartClient(host string, port string) {
	conn, err := net.Dial("tcp", host+":"+port)
	if err != nil {
		panic(err)
	}
	defer conn.Close()
	
	fmt.Fprintf(conn, "Hello Server\n")
	
	buf := make([]byte, 1024)
	n, err := conn.Read(buf)
	if err != nil {
		panic(err)
	}
	fmt.Printf("Response: %s\n", buf[:n])
}
```

## 二、高性能服务器

### 2.1 Goroutine池

```go
package server

import (
	"net"
	"sync"
)

type WorkerPool struct {
	conns chan net.Conn
	wg    sync.WaitGroup
}

func NewWorkerPool(workerCount, queueSize int) *WorkerPool {
	return &WorkerPool{
		conns: make(chan net.Conn, queueSize),
	}
}

func (p *WorkerPool) Start() {
	for i := 0; i < cap(p.conns); i++ {
		p.wg.Add(1)
		go p.worker()
	}
}

func (p *WorkerPool) worker() {
	defer p.wg.Done()
	for conn := range p.conns {
		p.handle(conn)
		conn.Close()
	}
}

func (p *WorkerPool) handle(conn net.Conn) {
	// 处理连接
	buf := make([]byte, 4096)
	for {
		n, err := conn.Read(buf)
		if err != nil {
			return
		}
		conn.Write(buf[:n])
	}
}

func (p *WorkerPool) Submit(conn net.Conn) {
	p.conns <- conn
}
```

### 2.2 Zero-Copy优化

```go
package network

import (
	"net"
	"os"
)

// 使用sendfile实现零拷贝
func SendFileZeroCopy(conn net.Conn, file *os.File) error {
	// 获取文件描述符
	fileFD, err := file.FileDescriptor()
	if err != nil {
		return err
	}
	
	// 获取连接的文件描述符
	connFD, err := conn.(*net.TCPConn).SyscallConn()
	if err != nil {
		return err
	}
	
	// 使用sendfile系统调用
	// ... 系统调用实现
	return nil
}

// TCP零拷贝配置
func OptimizeTCP(conn *net.TCPConn) error {
	// 禁用Nagle算法
	conn.SetNoDelay(true)
	// 设置发送缓冲区
	conn.SetWriteBuffer(64 * 1024)
	// 设置接收缓冲区
	conn.SetReadBuffer(64 * 1024)
	return nil
}
```

## 三、HTTP/2与HTTP/3

### 3.1 HTTP/2多路复用

```go
package http2

import (
	"fmt"
	"net/http"
)

func StartHTTP2Server() {
	mux := http.NewServeMux()
	mux.HandleFunc("/api/orders", handleOrders)
	mux.HandleFunc("/api/users", handleUsers)
	
	server := &http.Server{
		Addr:    ":8443",
		Handler: mux,
		// HTTP/2配置
		TLSConfig: nil, // 需要证书
	}
	
	fmt.Println("HTTP/2 server starting...")
	server.ListenAndServeTLS("cert.pem", "key.pem")
}

func handleOrders(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	fmt.Fprintf(w, `{"orders": []}`)
}
```

### 3.2 HTTP/3 (QUIC)

```go
package http3

import (
	"fmt"
	"net/http"
	"github.com/quic-go/quic-go/http3"
)

func StartHTTP3Server() {
	mux := http.NewServeMux()
	mux.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		fmt.Fprintf(w, "Hello from HTTP/3!")
	})
	
	server := &http3.Server{
		Addr:      ":8443",
		Handler:   mux,
		TLSConfig: nil,
	}
	
	fmt.Println("HTTP/3 server starting...")
	server.ListenAndServeTLS("cert.pem", "key.pem")
}
```

## 四、WebSocket实战

### 4.1 Server实现

```go
package websocket

import (
	"fmt"
	"log"
	"net/http"
	"sync"
	
	"github.com/gorilla/websocket"
)

var upgrader = websocket.Upgrader{
	ReadBufferSize:  1024,
	WriteBufferSize: 1024,
	CheckOrigin:     func(r *http.Request) bool { return true },
}

type Client struct {
	conn *websocket.Conn
	send chan []byte
	mu   sync.Mutex
}

type Hub struct {
	clients    map[string]*Client
	register   chan *Client
	unregister chan *Client
	mu         sync.RWMutex
}

func NewHub() *Hub {
	return &Hub{
		clients:    make(map[string]*Client),
		register:   make(chan *Client),
		unregister: make(chan *Client),
	}
}

func (h *Hub) Run() {
	for {
		select {
		case client := <-h.register:
			h.mu.Lock()
			h.clients[client.conn.RemoteAddr().String()] = client
			h.mu.Unlock()
		case client := <-h.unregister:
			h.mu.Lock()
			if _, ok := h.clients[client.conn.RemoteAddr().String()]; ok {
				delete(h.clients, client.conn.RemoteAddr().String())
				close(client.send)
			}
			h.mu.Unlock()
		case msg := <-client.send:
			client.mu.Lock()
			client.conn.WriteMessage(websocket.TextMessage, msg)
			client.mu.Unlock()
		}
	}
}

func (h *Hub) ServeWS(w http.ResponseWriter, r *http.Request) {
	conn, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		log.Println(err)
		return
	}
	
	client := &Client{
		conn: conn,
		send: make(chan []byte, 256),
	}
	
	h.register <- client
	defer func() { h.unregister <- client }()
	
	for {
		_, message, err := conn.ReadMessage()
		if err != nil {
			break
		}
		// 广播消息
		h.broadcast(message)
	}
}
```

## 五、DNS与CDN

### 5.1 DNS解析优化

```go
package dns

import (
	"context"
	"net"
	"time"
)

func FastDNSSolve(host string) (string, error) {
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel()
	
	ips, err := net.DefaultResolver.LookupIPAddr(ctx, host)
	if err != nil {
		return "", err
	}
	
	// 选择最优IP (优先IPv4)
	for _, ip := range ips {
		if ip.IP.To4() != nil {
			return ip.IP.String(), nil
		}
	}
	
	return ips[0].IP.String(), nil
}
```

### 5.2 CDN配置

```go
package cdn

import (
	"fmt"
	"net/http"
)

type CDNProxy struct {
	origin string
	cache  map[string][]byte
}

func (p *CDNProxy) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	url := r.URL.Path
	
	// 检查缓存
	if data, ok := p.cache[url]; ok {
		w.Header().Set("X-Cache", "HIT")
		w.Write(data)
		return
	}
	
	// 回源
	resp, err := http.Get(p.origin + url)
	if err != nil {
		http.Error(w, err.Error(), http.StatusBadGateway)
		return
	}
	defer resp.Body.Close()
	
	buf := make([]byte, 1024*1024)
	n, _ := resp.Body.Read(buf)
	
	p.cache[url] = buf[:n]
	w.Header().Set("X-Cache", "MISS")
	w.Write(buf[:n])
}
```

## 六、面试高频题

### Q1: goroutine和线程的区别？

```
A:
goroutine:
- 用户态，由Go运行时调度
- 初始栈空间2KB，动态扩展
- 轻量级，可创建百万级

线程:
- 内核态，由OS调度
- 固定栈空间 (通常1-8MB)
- 重量级，通常几千个
```

### Q2: TCP粘包如何解决？

```
A:
1. 定长消息
2. 分隔符 (如\n)
3. 消息长度前缀
4. 应用层协议 (如Protobuf)
```

## 七、自测题

1. 实现一个高性能的TCP服务器
2. 如何解决TCP粘包问题？
3. HTTP/2相比HTTP/1.1有哪些改进？

---

## 参考文档

- [Go网络编程](https://go.dev/blog/pipelines)
- [TCP/IP详解](https://www.cnblogs.com/itech/archive/2009/11/08/1598615.html)
