# Nginx 高性能配置与架构深度解析

> 深入 Nginx 核心：事件模型、负载均衡、缓存、安全配置。
> 源码级分析，包含性能调优和故障排查。
> 适用对象：运维工程师、后端工程师、架构师

---

## 1. Nginx 架构概览

### 1.1 核心组件

```
┌─────────────────────────────────────────────────────────────┐
│                    Nginx 架构                                │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Master Process (主进程)                                     │
│  ├── 读取配置                                                 │
│  ├── 维护 Worker 进程                                         │
│  └── 平滑重载配置                                             │
│                                                             │
│  Worker Processes (工作进程)                                  │
│  ├── 处理请求                                                │
│  ├── 事件循环                                                │
│  └── 共享内存                                                │
│                                                             │
│  核心模块：                                                   │
│  ├── ngx_http_core_module                                    │
│  ├── ngx_http_upstream_module                                │
│  ├── ngx_http_cache_module                                   │
│  └── ngx_http_rewrite_module                                 │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 事件模型

```c
// src/event/ngx_event.h (简化)

typedef struct {
    ngx_str_t             name;
    void               *(*init)(ngx_cycle_t *cycle, ngx_uint_t tier);
    void               (*done)(ngx_cycle_t *cycle);
    ngx_int_t            (*add)(ngx_event_t *ev, ngx_int_t flag);
    ngx_int_t            (*del)(ngx_event_t *ev, ngx_int_t flag);
    ngx_int_t            (*enable)(ngx_event_t *ev, ngx_int_t flag);
    ngx_int_t            (*disable)(ngx_event_t *ev, ngx_int_t flag);
    ngx_int_t            (*add_conn)(ngx_connection_t *c);
    ngx_int_t            (*del_conn)(ngx_connection_t *c, ngx_int_t flag);
    ngx_int_t            (*poll)(ngx_cycle_t *cycle, ngx_msec_t timer);
    const char           *name;
} ngx_event_actions_t;

// 事件处理方法
extern ngx_event_actions_t  ngx_event_actions;

// kqueue (macOS/BSD)
// epoll (Linux)
// /dev/poll (Solaris)
// select/poll (通用)
```

---

## 2. 负载均衡

### 2.1 算法实现

```nginx
# upstream 配置

upstream backend {
    # 轮询（默认）
    server backend1.example.com weight=5;
    server backend2.example.com;
    
    # IP Hash
    ip_hash;
    
    # 最少连接
    # least_conn;
    
    # 响应时间
    # fair;
    
    # 备份服务器
    server backup1.example.com backup;
    
    # 最大失败次数
    server backend3.example.com max_fails=3 fail_timeout=30s;
}

server {
    location / {
        proxy_pass http://backend;
        proxy_next_upstream error timeout http_500 http_502 http_503;
    }
}
```

### 2.2 Go 实现负载均衡器

```go
// load_balancer.go

package lb

import (
    "sync/atomic"
)

type Strategy int

const (
    RoundRobin Strategy = iota
    LeastConnections
    WeightedRoundRobin
    ConsistentHash
)

type LoadBalancer interface {
    Next() (*Server, error)
    Add(server *Server)
    Remove(server *Server)
}

// RoundRobin 轮询
type RoundRobin struct {
    servers   []*Server
    counter   uint64
}

func (lb *RoundRobin) Next() (*Server, error) {
    if len(lb.servers) == 0 {
        return nil, ErrNoServer
    }
    
    idx := atomic.AddUint64(&lb.counter, 1) % uint64(len(lb.servers))
    return lb.servers[idx], nil
}

// LeastConnections 最少连接
type LeastConnections struct {
    servers []*weightedServer
}

type weightedServer struct {
    *Server
    connections int32
}

func (lb *LeastConnections) Next() (*Server, error) {
    if len(lb.servers) == 0 {
        return nil, ErrNoServer
    }
    
    minConn := int32(^uint32(0) >> 1)
    var minServer *Server
    
    for _, s := range lb.servers {
        if s.connections < minConn {
            minConn = s.connections
            minServer = s.Server
        }
    }
    
    atomic.AddInt32(&minServer.connections, 1)
    return minServer, nil
}
```

---

## 3. 缓存机制

### 3.1 缓存架构

```
┌─────────────────────────────────────────────────────────────┐
│                    Nginx 缓存架构                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  客户端请求                                                  │
│       │                                                     │
│       ▼                                                     │
│  ┌─────────────┐                                            │
│  │  Cache Lookup│                                           │
│  └──────┬──────┘                                            │
│         │                                                   │
│    ┌────┴────┐                                             │
│    │         │                                             │
│  命中      未命中                                          │
│    │         │                                             │
│    ▼         ▼                                             │
│  返回缓存   向后端请求                                      │
│              │                                              │
│              ▼                                              │
│         ┌─────────┐                                        │
│         │ Backend │                                        │
│         └────┬────┘                                        │
│              │                                              │
│              ▼                                              │
│         ┌─────────┐                                        │
│         │ 缓存写入 │                                        │
│         └─────────┘                                        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 缓存配置

```nginx
# cache.conf

# 缓存路径和参数
proxy_cache_path /var/cache/nginx levels=1:2 keys_zone=my_cache:10m 
                 max_size=10g inactive=60m use_temp_path=off;

# 缓存key
proxy_cache_key "$scheme$request_method$host$request_uri";

# 缓存响应头
proxy_cache_valid 200 302 10m;
proxy_cache_valid 404 1m;

# 缓存条件
proxy_cache_methods GET HEAD;
proxy_cache_bypass $http_cache_control;
proxy_no_cache $http_pragma;

# 缓存状态
add_header X-Cache-Status $upstream_cache_status;
```

---

## 4. 安全配置

### 4.1 安全防护

```nginx
# security.conf

# 限制请求频率
limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
limit_req zone=api burst=20 nodelay;

# 限制连接数
limit_conn_zone $binary_remote_addr zone=addr:10m;
limit_conn addr 10;

# 隐藏版本信息
server_tokens off;

# 安全头
add_header X-Frame-Options "SAMEORIGIN" always;
add_header X-Content-Type-Options "nosniff" always;
add_header X-XSS-Protection "1; mode=block" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;

# SSL/TLS
ssl_protocols TLSv1.2 TLSv1.3;
ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;
ssl_prefer_server_ciphers on;

# 防止路径遍历
location ~* \.(?:jpg|jpeg|gif|png|css|js)$ {
    valid_referers none blocked server_names *.example.com;
    if ($invalid_referer) {
        return 403;
    }
}
```

---

## 5. 性能调优

### 5.1 核心参数

```nginx
# performance.conf

# 工作进程数（通常等于CPU核心数）
worker_processes auto;
worker_cpu_affinity auto;

# 单连接缓冲
worker_connections 10240;
use epoll;
multi_accept on;

# 文件描述符
worker_rlimit_nofile 65535;

# 发送文件
sendfile on;
tcp_nopush on;
tcp_nodelay on;

# 超时设置
keepalive_timeout 65;
keepalive_requests 1000;
client_body_timeout 12;
client_header_timeout 12;
send_timeout 10;

# 缓冲区
client_body_buffer_size 128k;
client_max_body_size 100m;
client_header_buffer_size 1k;
large_client_header_buffers 4 4k;
```

### 5.2 Go 实现高性能服务器

```go
// server.go

package main

import (
    "net"
    "sync/atomic"
    "time"
)

type HighPerfServer struct {
    listener    net.Listener
    connections atomic.Int64
    requests    atomic.Int64
}

func NewHighPerfServer(addr string) (*HighPerfServer, error) {
    listener, err := net.Listen("tcp", addr)
    if err != nil {
        return nil, err
    }
    return &HighPerfServer{listener: listener}, nil
}

func (s *HighPerfServer) Start(maxConns int) {
    for i := 0; i < maxConns; i++ {
        go s.accept()
    }
}

func (s *HighPerfServer) accept() {
    for {
        conn, err := s.listener.Accept()
        if err != nil {
            return
        }
        s.connections.Add(1)
        go s.handle(conn)
    }
}

func (s *HighPerfServer) handle(conn net.Conn) {
    defer s.connections.Add(-1)
    defer conn.Close()
    
    buf := make([]byte, 4096)
    for {
        n, err := conn.Read(buf)
        if err != nil {
            return
        }
        s.requests.Add(1)
        // 处理请求...
    }
}

func (s *HighPerfServer) Stats() map[string]int64 {
    return map[string]int64{
        "connections": s.connections.Load(),
        "requests":    s.requests.Load(),
    }
}
```

---

## 6. 监控与日志

### 6.1 访问日志

```nginx
# log_format.conf

log_format main '$remote_addr - $remote_user [$time_local] '
                '"$request" $status $body_bytes_sent '
                '"$http_referer" "$http_user_agent" '
                '$request_time $upstream_response_time';

access_log /var/log/nginx/access.log main;
```

### 6.2 监控指标

```go
// metrics.go

package metrics

import (
    "github.com/prometheus/client_golang/prometheus"
)

type NginxMetrics struct {
    connectionsAccepted prometheus.Counter
    connectionsHandled  prometheus.Counter
    requestsTotal       prometheus.Counter
    requestDuration     prometheus.Histogram
    activeConnections   prometheus.Gauge
}

func NewNginxMetrics() *NginxMetrics {
    return &NginxMetrics{
        connectionsAccepted: prometheus.NewCounter(prometheus.CounterOpts{
            Name: "nginx_connections_accepted",
            Help: "Accepted connections",
        }),
        connectionsHandled: prometheus.NewCounter(prometheus.CounterOpts{
            Name: "nginx_connections_handled",
            Help: "Handled connections",
        }),
        requestsTotal: prometheus.NewCounter(prometheus.CounterOpts{
            Name: "nginx_requests_total",
            Help: "Total requests",
        }),
        requestDuration: prometheus.NewHistogram(prometheus.HistogramOpts{
            Name:    "nginx_request_duration_seconds",
            Help:    "Request duration",
            Buckets: []float64{0.01, 0.05, 0.1, 0.5, 1.0, 5.0},
        }),
        activeConnections: prometheus.NewGauge(prometheus.GaugeOpts{
            Name: "nginx_active_connections",
            Help: "Active connections",
        }),
    }
}
```

---

## 7. 故障排查

### 7.1 常见问题

| 问题 | 症状 | 排查命令 | 解决方案 |
|------|------|----------|----------|
| 502 Bad Gateway | 后端不可达 | `nginx -t` | 检查后端服务 |
| 504 Gateway Timeout | 响应超时 | 查看日志 | 增加超时时间 |
| 连接数耗尽 | 拒绝连接 | `netstat -an` | 增加 worker_connections |
| 内存泄漏 | 内存持续增长 | `top` | 升级版本/调整参数 |

### 7.2 调试技巧

```bash
# 测试配置
nginx -t

# 查看错误日志
tail -f /var/log/nginx/error.log

# 实时监控
nginx -s reopen

# 优雅重启
nginx -s reload

# 查看状态
curl http://localhost/nginx_status
```

---

## 8. 总结

### 8.1 核心原理回顾

| 模块 | 核心技术 |
|------|----------|
| 事件模型 | epoll/kqueue |
| 负载均衡 | 轮询/最少连接/IP Hash |
| 缓存机制 | 磁盘缓存+内存缓存 |
| 性能调优 | 工作进程+缓冲区 |

### 8.2 最佳实践

- [ ] 合理配置 worker_processes
- [ ] 设置合适的缓存策略
- [ ] 配置安全头
- [ ] 监控关键指标
- [ ] 定期日志轮转

---

*最后更新：2026-08-11*
*作者：Ryan*
