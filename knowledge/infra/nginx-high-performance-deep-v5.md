# Nginx 高性能配置与架构深度解析

> 深入 Nginx 核心：事件模型、负载均衡、缓存、安全配置、性能调优。
> 源码级分析，包含生产环境最佳实践。
> 适用对象：运维工程师、后端工程师、架构师

---

## 1. Nginx 架构

### 1.1 核心架构

```
Nginx 架构：

┌─────────────────────────────────────────────────────────────┐
│                   Nginx 架构                                 │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Master Process (主进程)                                      │
│  ├── 读取配置                                                │
│  ├── 维护 Socket                                              │
│  └── 管理 Worker                                              │
│                                                             │
│  Worker Process (工作进程)                                    │
│  ├── 处理请求                                                │
│  ├── 事件驱动 (epoll/kqueue)                                 │
│  └── 独立运行，互不影响                                       │
│                                                             │
│  Event Module (事件模块)                                      │
│  ├── epoll (Linux)                                          │
│  ├── kqueue (BSD/macOS)                                     │
│  ├── select/poll (兼容)                                      │
│  └── eventport (Solaris)                                    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 Go 模拟 Nginx 架构

```go
// nginx_arch.go

package nginx

import (
    "sync"
)

type MasterProcess struct {
    workerCount int
    workers     []*WorkerProcess
    config      *Config
}

type WorkerProcess struct {
    ID       int
    connNum  int
    running  bool
    mu       sync.Mutex
}

type Config struct {
    WorkerProcesses  int
    MaxConnections   int
    KeepaliveTimeout int
}

func NewMaster(config *Config) *MasterProcess {
    m := &MasterProcess{
        workerCount: config.WorkerProcesses,
        config:      config,
    }
    m.spawnWorkers()
    return m
}

func (m *MasterProcess) spawnWorkers() {
    for i := 0; i < m.workerCount; i++ {
        worker := &WorkerProcess{
            ID:      i,
            running: true,
        }
        m.workers = append(m.workers, worker)
        go worker.run()
    }
}

func (w *WorkerProcess) run() {
    for w.running {
        // 处理连接
        conn := w.accept()
        if conn != nil {
            w.handle(conn)
        }
    }
}
```

---

## 2. 负载均衡

### 2.1 调度算法

```
Nginx 负载均衡算法：

┌────────────────┬─────────────────────────────┬──────────────┐
│ 算法           │ 说明                        │ 适用场景     │
├────────────────┼─────────────────────────────┼──────────────┤
│ 轮询 (Round Robin)  │ 平均分配请求                 │ 通用         │
│ 加权轮询 (Weight)   │ 按权重分配                   │ 异构服务器   │
│ IP Hash       │ 同一 IP 固定后端             │ 会话保持     │
│ 最少连接      │ 分配给连接最少的服务器        │ 长连接       │
│ 响应时间      │ 优先分配给响应快的服务器      │ 性能敏感     │
└────────────────┴─────────────────────────────┴──────────────┘
```

### 2.2 Go 实现负载均衡

```go
// load_balancer.go

package nginx

import (
    "sync"
)

type Backend struct {
    Address  string
    Weight   int
    Active   int
    Failed   int
}

type LoadBalancer interface {
    Next() *Backend
    MarkSuccess(*Backend)
    MarkFailure(*Backend)
}

// 加权轮询
type WeightRoundRobin struct {
    backends []*Backend
    current  int
    mu       sync.Mutex
}

func (wrr *WeightRoundRobin) Next() *Backend {
    wrr.mu.Lock()
    defer wrr.mu.Unlock()
    
    total := 0
    for _, b := range wrr.backends {
        total += b.Weight
    }
    
    for i := 0; i < total; i++ {
        idx := wrr.current % len(wrr.backends)
        if wrr.backends[idx].Weight > 0 {
            wrr.current++
            return wrr.backends[idx]
        }
        wrr.current++
    }
    return nil
}

func (wrr *WeightRoundRobin) MarkSuccess(b *Backend) {
    wrr.mu.Lock()
    defer wrr.mu.Unlock()
    b.Failed = 0
}

func (wrr *WeightRoundRobin) MarkFailure(b *Backend) {
    wrr.mu.Lock()
    defer wrr.mu.Unlock()
    b.Failed++
}
```

---

## 3. 缓存机制

### 3.1 缓存类型

```
Nginx 缓存类型：

1. 代理缓存 (proxy_cache)
   └── 缓存后端响应

2. FastCGI 缓存
   └── 缓存 PHP 响应

3. 缓存-key
   └── 自定义缓存键

4. 缓存有效期
   └── 控制缓存过期时间
```

### 3.2 Go 实现缓存

```go
// cache.go

package nginx

import (
    "sync"
    "time"
)

type CacheEntry struct {
    Value     interface{}
    ExpiresAt time.Time
}

type Cache struct {
    items    sync.Map
    defaultTTL time.Duration
}

func NewCache(defaultTTL time.Duration) *Cache {
    return &Cache{
        defaultTTL: defaultTTL,
    }
}

func (c *Cache) Get(key string) (interface{}, bool) {
    if v, ok := c.items.Load(key); ok {
        entry := v.(*CacheEntry)
        if time.Now().Before(entry.ExpiresAt) {
            return entry.Value, true
        }
        c.items.Delete(key)
    }
    return nil, false
}

func (c *Cache) Set(key string, value interface{}) {
    c.items.Store(key, &CacheEntry{
        Value:     value,
        ExpiresAt: time.Now().Add(c.defaultTTL),
    })
}

func (c *Cache) Delete(key string) {
    c.items.Delete(key)
}
```

---

## 4. 性能调优

### 4.1 核心参数

```
Nginx 性能调优参数：

1. 工作进程
   worker_processes auto;        # 自动设置
   worker_connections 65535;     # 每进程最大连接

2. 事件模型
   use epoll;                    # Linux epoll
   multi_accept on;              # 一次接受多个连接

3. 缓冲区
   client_body_buffer_size 128k;
   client_max_body_size 50m;
   proxy_buffer_size 4k;
   proxy_buffers 8 4k;

4. 超时
   keepalive_timeout 65;
   send_timeout 60;
```

### 4.2 Go 实现性能监控

```go
// performance_monitor.go

package nginx

type PerformanceMonitor struct {
    connections   int64
    requests      int64
    bytesSent     int64
    bytesReceived int64
    latency     float64
}

func (pm *PerformanceMonitor) RecordConnection() {
    pm.connections++
}

func (pm *PerformanceMonitor) RecordRequest(size int, latency float64) {
    pm.requests++
    pm.bytesSent += int64(size)
    pm.latency = latency
}

func (pm *PerformanceMonitor) GetStats() map[string]interface{} {
    return map[string]interface{}{
        "connections": pm.connections,
        "requests":    pm.requests,
        "bytes_sent":  pm.bytesSent,
        "bytes_recv":  pm.bytesReceived,
        "avg_latency": pm.latency,
    }
}
```

---

## 5. 安全配置

### 5.1 安全最佳实践

```
Nginx 安全配置：

1. 隐藏版本信息
   server_tokens off;

2. 限制请求方法
   if ($request_method !~ ^(GET|HEAD|POST)$) {
       return 444;
   }

3. 防 DDOS
   limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
   limit_req zone=api burst=20 nodelay;

4. SSL/TLS
   ssl_protocols TLSv1.2 TLSv1.3;
   ssl_ciphers HIGH:!aNULL:!MD5;
```

### 5.2 Go 实现安全检测

```go
// security.go

package nginx

import "strings"

type SecurityChecker struct {
    allowedMethods []string
    rateLimit     int
}

func (sc *SecurityChecker) CheckRequest(method, uri string) bool {
    // 检查请求方法
    if !contains(sc.allowedMethods, method) {
        return false
    }
    
    // 检查 URI 安全
    if strings.Contains(uri, "..") || strings.Contains(uri, "<script>") {
        return false
    }
    
    return true
}

func contains(slice []string, val string) bool {
    for _, s := range slice {
        if s == val {
            return true
        }
    }
    return false
}
```

---

## 6. 总结

### 6.1 核心原理回顾

| 模块 | 核心机制 |
|------|----------|
| 架构 | Master-Worker 模型 |
| 负载均衡 | 多种调度算法 |
| 缓存 | 多级缓存机制 |
| 性能 | 事件驱动模型 |
| 安全 | 多层防护策略 |

### 6.2 最佳实践

- [ ] 合理配置 worker 进程
- [ ] 使用 epoll 事件模型
- [ ] 配置合理的缓冲区
- [ ] 启用 Gzip 压缩
- [ ] 实施安全策略

---

*最后更新：2026-08-11*
*作者：Ryan*
