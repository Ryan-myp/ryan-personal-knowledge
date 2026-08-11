# Nginx 高性能配置与架构深度解析

> 深入 Nginx 核心：事件模型、负载均衡、缓存、安全配置。
> 源码级分析，包含性能调优和故障排查。
> 适用对象：运维工程师、后端工程师、架构师

---

## 1. Nginx 架构

### 1.1 核心架构

```
┌─────────────────────────────────────────────────────────────┐
│                    Nginx 架构                                │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  主进程 (Master Process)                                     │
│  ├── 读取配置文件                                            │
│  ├── 维护 Worker 进程                                        │
│  ├── 管理日志轮转                                            │
│  └── 平滑重启                                                │
│                                                             │
│  Worker 进程                                                  │
│  ├── 处理客户端请求                                          │
│  ├── 事件驱动架构                                            │
│  └── 独立工作，互不影响                                      │
│                                                             │
│  事件模块                                                     │
│  ├── epoll (Linux)                                          │
│  ├── kqueue (FreeBSD/macOS)                                 │
│  ├── select/poll (其他)                                      │
│  └── IOCP (Windows)                                        │
│                                                             │
│  模块体系                                                     │
│  ├── 核心模块                                                │
│  ├── 事件模块                                                │
│  ├── 输出过滤器                                              │
│  ├── HTTP 模块                                               │
│  └── 第三方模块                                              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 请求处理流程

```
请求处理流程：

1. 接收请求
   └── accept_mutex 控制并发

2. 读取请求头
   └── ngx_http_read_request_header()

3. 解析请求
   └── ngx_http_process_request()

4. 选择处理模块
   └── location 匹配

5. 执行处理
   └── content handler

6. 发送响应
   └── output filter chain
```

---

## 2. 事件模型

### 2.1 epoll 模型

```
epoll 工作原理：

┌─────────────────────────────────────────────────────────────┐
│  User Space                   Kernel Space                   │
│                                                             │
│  epoll_create() ─────────────► epoll instance               │
│       │                         │                           │
│       ▼                         ▼                           │
│  epoll_ctl() ───────────────► epoll table                   │
│       │                         │                           │
│       ▼                         ▼                           │
│  epoll_wait()  ◄───────────── ready list                    │
│                                                             │
└─────────────────────────────────────────────────────────────┘

优势：
- O(1) 复杂度查找就绪事件
- 只返回就绪的 fd
- 支持边缘触发和水平触发
```

### 2.2 Go 实现事件循环

```go
// event_loop.go

package nginx

import (
    "syscall"
    "time"
)

type EventLoop struct {
    epollFd  int
    events   []syscall.EpollEvent
    handlers map[int]EventHandler
}

type EventHandler func(fd int, events uint32)

func NewEventLoop() (*EventLoop, error) {
    fd, err := syscall.EpollCreate1(0)
    if err != nil {
        return nil, err
    }
    
    return &EventLoop{
        epollFd:  fd,
        events:   make([]syscall.EpollEvent, 1024),
        handlers: make(map[int]EventHandler),
    }, nil
}

func (el *EventLoop) Add(fd int, handler EventHandler, events uint32) error {
    ev := syscall.EpollEvent{
        Events: events,
        Fd:     int32(fd),
    }
    
    if err := syscall.EpollCtl(el.epollFd, syscall.EPOLL_CTL_ADD, fd, &ev); err != nil {
        return err
    }
    
    el.handlers[fd] = handler
    return nil
}

func (el *EventLoop) Run() error {
    for {
        n, err := syscall.EpollWait(el.epollFd, el.events, 5000)
        if err != nil {
            return err
        }
        
        for i := 0; i < n; i++ {
            if handler, ok := el.handlers[int(el.events[i].Fd)]; ok {
                handler(int(el.events[i].Fd), el.events[i].Events)
            }
        }
    }
}
```

---

## 3. 负载均衡

### 3.1 算法对比

```
┌─────────────────────────────────────────────────────────────┐
│                  负载均衡算法对比                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  算法              │ 特点                    │ 适用场景     │
├─────────────────────────────────────────────────────────────┤
│  Round Robin       │ 轮询分配                  │ 均匀负载    │
│  Weight Round Robin│ 加权轮询                  │ 异构服务器  │
│  Least Connections │ 最少连接                  │ 长连接场景  │
│  IP Hash           │ 按 IP 哈希                │ 会话保持    │
│  URL Hash          │ 按 URL 哈希               │ 缓存优化    │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 Go 实现负载均衡器

```go
// load_balancer.go

package nginx

import (
    "sync"
)

type Server struct {
    Address  string
    Weight   int
    CurrentWeight int
    Conns   int
}

type LoadBalancer interface {
    Next() *Server
}

type RoundRobinBalancer struct {
    servers []*Server
    mu      sync.Mutex
}

func (lb *RoundRobinBalancer) Next() *Server {
    lb.mu.Lock()
    defer lb.mu.Unlock()
    
    if len(lb.servers) == 0 {
        return nil
    }
    
    total := 0
    for _, s := range lb.servers {
        total += s.Weight
    }
    
    n := rand.Intn(total)
    for _, s := range lb.servers {
        n -= s.Weight
        if n < 0 {
            return s
        }
    }
    return lb.servers[0]
}
```

---

## 4. 缓存

### 4.1 缓存类型

```
Nginx 缓存类型：

1. 代理缓存 (proxy_cache)
   ├── 缓存后端响应
   ├── 减少后端负载
   └── 提高响应速度

2.  fastcgi 缓存
   ├── 缓存 FastCGI 响应
   └── 适用于 PHP 应用

3. 缓存键
   ├── $request_uri
   ├── $host
   ├── $query_string
   └── 自定义键
```

### 4.2 缓存配置

```nginx
proxy_cache_path /var/cache/nginx levels=1:2 keys_zone=my_cache:10m max_size=10g inactive=60m;

server {
    location / {
        proxy_cache my_cache;
        proxy_cache_key $scheme$request_method$host$request_uri;
        proxy_cache_valid 200 302 10m;
        proxy_cache_valid 404 1m;
        proxy_pass http://backend;
    }
}
```

---

## 5. 安全配置

### 5.1 访问控制

```nginx
# 禁止访问敏感文件
location ~* \.(env|git|sql)$ {
    deny all;
}

# IP 白名单
allow 192.168.1.0/24;
deny all;

# 限流
limit_req_zone $binary_remote_addr zone=one:10m rate=10r/s;
limit_req zone=one burst=20 nodelay;
```

### 5.2 HTTPS 配置

```nginx
server {
    listen 443 ssl;
    server_name example.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    
    # HSTS
    add_header Strict-Transport-Security "max-age=31536000" always;
}
```

---

## 6. 性能优化

### 6.1 核心优化参数

```
worker_processes auto;
worker_connections 10240;
multi_accept on;
use epoll;

sendfile on;
tcp_nopush on;
tcp_nodelay on;

keepalive_timeout 65;
keepalive_requests 1000;

client_max_body_size 10m;
client_body_buffer_size 128k;
```

### 6.2 调优建议

```
优化建议：

1. 网络优化
   ├── 调整 TCP 参数
   ├── 启用 TCP Fast Open
   └── 优化内核参数

2. 磁盘优化
   ├── 使用 SSD
   ├── 调整 IO 调度器
   └── 日志异步写入

3. 进程优化
   ├── 设置 worker_processes
   ├── 调整 worker_connections
   └── 启用 multi_accept
```

---

## 7. 监控告警

### 7.1 关键指标

```
监控指标：

- 连接数：active, reading, writing, waiting
- 请求数：requests, handled
- 流量：bytes_sent, bytes_received
- 状态码：2xx, 3xx, 4xx, 5xx
- 延迟：响应时间
```

### 7.2 Go 实现监控

```go
// metrics.go

package nginx

import "github.com/prometheus/client_golang/prometheus"

type NginxMetrics struct {
    connections   prometheus.GaugeVec
    requests      prometheus.CounterVec
    bytesSent     prometheus.Counter
    bytesReceived prometheus.Counter
}

func NewNginxMetrics() *NginxMetrics {
    return &NginxMetrics{
        connections: *prometheus.NewGaugeVec(
            prometheus.GaugeOpts{Name: "nginx_connections", Help: "Active connections"},
            []string{"state"},
        ),
        requests: *prometheus.NewCounterVec(
            prometheus.CounterOpts{Name: "nginx_requests", Help: "Total requests"},
            []string{"status"},
        ),
        bytesSent: prometheus.NewCounter(prometheus.CounterOpts{
            Name: "nginx_bytes_sent",
            Help: "Bytes sent",
        }),
        bytesReceived: prometheus.NewCounter(prometheus.CounterOpts{
            Name: "nginx_bytes_received",
            Help: "Bytes received",
        }),
    }
}
```

---

## 8. 故障排查

### 8.1 常见问题

| 问题 | 症状 | 排查命令 | 解决方案 |
|------|------|----------|----------|
| 连接数爆满 | 502 错误 | `netstat -an | grep ESTABLISHED` | 增加 worker_connections |
| 内存泄漏 | 内存持续增长 | `top -p nginx_pid` | 升级版本/重启 |
| 响应慢 | 延迟高 | `access_log` 分析 | 优化缓存/后端 |
| 502 Bad Gateway | 后端不可达 | 检查后端服务 | 检查后端状态 |

---

## 9. 总结

### 9.1 核心原理回顾

| 模块 | 核心机制 |
|------|----------|
| 架构 | Master-Worker 多进程 |
| 事件 | epoll/kqueue |
| 负载均衡 | 多种算法 |
| 缓存 | 代理缓存 |
| 安全 | 访问控制/HTTPS |

### 9.2 最佳实践

- [ ] 合理配置 worker 进程
- [ ] 启用缓存优化
- [ ] 配置 SSL/TLS
- [ ] 监控关键指标
- [ ] 定期性能测试

---

*最后更新：2026-08-11*
*作者：Ryan*
