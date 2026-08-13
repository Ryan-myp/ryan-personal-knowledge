# Nginx 高性能配置深度解析

> 深入 Nginx 核心：事件模型、负载均衡、缓存、安全配置。
> 源码级分析，包含性能调优和故障排查。
> 适用对象：运维工程师、后端工程师、架构师

---

## 1. Nginx 架构

### 1.1 核心架构

```
Nginx 架构：

┌─────────────────────────────────────────────────────────────┐
│                    Nginx 架构                               │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Master 进程                                                  │
│  ├── 读取配置                                                 │
│  ├── 管理 Worker 进程                                         │
│  └── 优雅重启                                                │
│                                                             │
│  Worker 进程                                                  │
│  ├── 处理请求                                                 │
│  ├── 事件驱动                                                 │
│  └── 多进程共享                                               │
│                                                             │
│  事件模型 (Event Model)                                       │
│  ├── Linux: epoll                                            │
│  ├── macOS: kqueue                                           │
│  ├── Solaris: /dev/poll                                     │
│  └── Windows: IOCP                                           │
│                                                             │
│  模块系统 (Module System)                                     │
│  ├── Core 模块                                              │
│  ├── HTTP 模块                                              │
│  ├── Mail 模块                                              │
│  └── Stream 模块                                             │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 事件处理流程

```
请求处理流程：

1. 接收请求
   └── accept() 系统调用

2. 读取请求头
   └── read() 系统调用

3. 路由匹配
   └── server_name + location

4. 处理请求
   ├── 静态文件：直接返回
   ├── 反向代理：转发到后端
   └── PHP：执行 FastCGI

5. 发送响应
   └── write() 系统调用
```

---

## 2. 事件模型

### 2.1 epoll 模型

```c
// Linux epoll 示例
int epoll_fd = epoll_create1(0);

struct epoll_event event;
event.events = EPOLLIN | EPOLLET;
event.data.fd = server_fd;

epoll_ctl(epoll_fd, EPOLL_CTL_ADD, server_fd, &event);

while (running) {
    int n = epoll_wait(epoll_fd, events, MAX_EVENTS, -1);
    for (int i = 0; i < n; i++) {
        if (events[i].data.fd == server_fd) {
            // 接受新连接
            accept(server_fd, ...);
        } else {
            // 处理读写
            handle_io(events[i].data.fd);
        }
    }
}
```

### 2.2 边缘触发 vs 水平触发

```
LT (Level Triggered) - 水平触发：
├── 只要缓冲区有数据，就持续触发
├── 安全但效率较低
└── 默认模式

ET (Edge Triggered) - 边缘触发：
├── 只在状态变化时触发一次
├── 效率高但需处理完整数据
└── Nginx 使用 ET 模式
```

---

## 3. 负载均衡

### 3.1 算法对比

```
┌─────────────────────────────────────────────────────────────┐
│                  负载均衡算法对比                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  算法              │ 原理              │ 适用场景            │
├─────────────────────────────────────────────────────────────┤
│  轮询 (Round Robin) │ 轮流分配           │ 均匀负载            │
│  加权轮询           │ 按权重分配         │ 服务器性能不同      │
│  最少连接           │ 分配给最少连接     │ 长连接场景          │
│  IP Hash           │ 按IP哈希           │ 会话保持            │
│  URL Hash          │ 按URL哈希          │ CDN缓存             │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 配置示例

```nginx
upstream backend {
    # 加权轮询
    server 192.168.1.10 weight=5;
    server 192.168.1.11 weight=3;
    server 192.168.1.12 weight=2;
    
    # 健康检查
    max_fails=3
    fail_timeout=30s;
    
    # IP Hash
    # ip_hash;
}

server {
    listen 80;
    
    location / {
        proxy_pass http://backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

---

## 4. 缓存机制

### 4.1 代理缓存

```nginx
# 缓存配置
proxy_cache_path /var/cache/nginx levels=1:2 keys_zone=my_cache:10m 
                 max_size=1g inactive=60m use_temp_path=off;

server {
    location / {
        proxy_cache my_cache;
        proxy_cache_key $scheme$request_method$host$request_uri;
        
        # 缓存规则
        proxy_cache_valid 200 302 10m;
        proxy_cache_valid 404 1m;
        
        # 缓存头
        proxy_cache_use_stale error timeout updating;
        proxy_cache_lock on;
        
        proxy_pass http://backend;
    }
}
```

### 4.2 缓存命中率分析

```bash
# 查看缓存命中率
nginx -V 2>&1 | grep -o with-http_cache_module

# 监控缓存状态
location /cache_status {
    stub_status on;
}

# 缓存统计
nginx -s reload && tail -f /var/log/nginx/access.log | grep "cache"
```

---

## 5. 安全配置

### 5.1 基础安全

```nginx
# 隐藏版本信息
server_tokens off;

# HTTPS 配置
ssl_certificate /etc/nginx/ssl/server.crt;
ssl_certificate_key /etc/nginx/ssl/server.key;
ssl_protocols TLSv1.2 TLSv1.3;
ssl_ciphers HIGH:!aNULL:!MD5;

# 安全头
add_header X-Frame-Options "SAMEORIGIN" always;
add_header X-Content-Type-Options "nosniff" always;
add_header X-XSS-Protection "1; mode=block" always;
add_header Strict-Transport-Security "max-age=31536000" always;
```

### 5.2 防攻击配置

```nginx
# 限制请求频率
limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;

server {
    location /api/ {
        limit_req zone=api burst=20 nodelay;
        limit_req_status 429;
    }
}

# 限制连接数
limit_conn_zone $binary_remote_addr zone=addr:10m;

server {
    location / {
        limit_conn addr 10;
    }
}
```

---

## 6. 性能优化

### 6.1 核心参数

```nginx
# 进程数
worker_processes auto;

# 每个进程连接数
worker_connections 10240;

# 事件模型
events {
    use epoll;
    worker_connections 10240;
    multi_accept on;
}

# 文件描述符
worker_rlimit_nofile 65535;

# 缓冲区优化
client_body_buffer_size 128k;
client_max_body_size 100m;
sendfile on;
tcp_nopush on;
tcp_nodelay on;
keepalive_timeout 65;
keepalive_requests 1000;
```

### 6.2 Gzip 压缩

```nginx
gzip on;
gzip_vary on;
gzip_proxied any;
gzip_comp_level 6;
gzip_types text/plain text/css application/json application/javascript 
           text/xml application/xml application/xml+rss text/javascript;
gzip_min_length 1000;
```

---

## 7. 故障排查

### 7.1 常见问题

| 问题 | 症状 | 排查命令 | 解决方案 |
|------|------|----------|----------|
| 连接数溢出 | 502错误 | `netstat -an | grep ESTABLISHED` | 增加 worker_connections |
| 文件描述符耗尽 | 500错误 | `ulimit -n` | 增加限制 |
| CPU 100% | 响应慢 | `top` | 检查日志轮转 |
| 内存泄漏 | 内存增长 | `ps aux` | 重启 Nginx |

### 7.2 性能分析

```bash
# 查看连接状态
netstat -an | grep :80 | wc -l

# 查看进程状态
ps aux | grep nginx

# 性能测试
ab -n 10000 -c 100 http://localhost/

# 实时监控
nginx -s reopen && tail -f /var/log/nginx/access.log
```

---

## 8. 总结

### 8.1 核心原理回顾

| 模块 | 核心机制 |
|------|----------|
| 架构 | Master-Worker 多进程 |
| 事件 | epoll/IOCP 异步非阻塞 |
| 负载 | 多种负载均衡算法 |
| 缓存 | 多级缓存机制 |
| 安全 | 限流+防护头 |

### 8.2 最佳实践

- [ ] 合理配置 worker_processes
- [ ] 启用 gzip 压缩
- [ ] 配置缓存策略
- [ ] 设置安全头
- [ ] 定期性能测试

---

*最后更新：2026-08-11*
*作者：Ryan*
