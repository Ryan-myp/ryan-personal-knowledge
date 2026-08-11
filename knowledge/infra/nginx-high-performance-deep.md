# Nginx 高性能配置与源码解析

> 深入 Nginx 核心架构：事件模型、负载均衡、缓存、安全配置。
> 源码级分析，包含性能调优和故障排查。
> 适用对象：运维工程师、后端工程师、架构师

---

## 1. Nginx 架构概览

### 1.1 核心组件

```
┌─────────────────────────────────────────────────────────────┐
│                     Nginx 架构                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Master Process                                            │
│  ├─ 配置解析                                                 │
│  ├─ 子进程管理                                               │
│  └─ 信号处理                                                 │
│                                                             │
│  Worker Processes (多个，每个绑定CPU核心)                     │
│  ├─ 事件循环 (epoll/kqueue)                                  │
│  ├─ 连接处理                                                 │
│  ├─ 请求解析                                                 │
│  └─ 响应发送                                                 │
│                                                             │
│  Modules (模块化设计)                                        │
│  ├─ HTTP Core Module                                         │
│  ├─ Upstream Module                                          │
│  ├─ Cache Module                                             │
│  └─ Security Module                                          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 事件模型

```c
// ngx_event.h

typedef struct {
    ngx_event_handler_pt      handler;
    
    ngx_connection_t         *connection;
    
    ngx_event_t              *prev;
    ngx_event_t              *next;
    
    u_char                    ident;
    ngx_event_id_t            event_id;
    
    ngx_event_actions_t       actions;
    
    ngx_uint_t                index;
    
    ngx_log_t                *log;
    
    void                     *data;
    
    ngx_event_t              *prev;
    ngx_event_t              *next;
    
    ngx_event_t              *prev;
    ngx_event_t              *next;
} ngx_event_t;
```

---

## 2. 高性能配置

### 2.1 Worker 配置

```nginx
# worker进程数，建议等于CPU核数
worker_processes auto;

# worker CPU绑定
worker_cpu_affinity auto;

# 每个worker最大连接数
worker_connections 65535;

# 事件模型
events {
    use epoll;
    worker_connections 65535;
    multi_accept on;
    accept_mutex off;
}
```

### 2.2 HTTP 配置

```nginx
http {
    # 基础配置
    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    
    # 超时配置
    keepalive_timeout 65;
    keepalive_requests 1000;
    client_body_timeout 10;
    client_header_timeout 10;
    send_timeout 10;
    
    # 缓冲配置
    client_body_buffer_size 128k;
    client_max_body_size 100m;
    client_header_buffer_size 1k;
    large_client_header_buffers 4 4k;
    
    # 输出缓冲
    output_buffers 1 32k;
    postpone_output 1460;
    
    # 文件缓存
    open_file_cache max=10000 inactive=20s;
    open_file_cache_valid 30s;
    open_file_cache_min_uses 2;
    open_file_cache_errors on;
}
```

### 2.3 Gzip 压缩

```nginx
gzip on;
gzip_min_length 1k;
gzip_buffers 4 16k;
gzip_http_version 1.1;
gzip_comp_level 6;
gzip_types text/plain text/css application/json application/javascript 
           text/xml application/xml application/xml+rss text/javascript;
gzip_vary on;
gzip_proxied any;
gzip_disable "MSIE [1-6]\.";
```

---

## 3. 负载均衡

### 3.1 负载均衡算法

```nginx
upstream backend {
    # 轮询（默认）
    # ip_hash
    # least_conn
    # hash $request_uri consistent
    
    server 10.0.0.1:8080 weight=5;
    server 10.0.0.2:8080 weight=3;
    server 10.0.0.3:8080 backup;
    server 10.0.0.4:8080 down;
    
    # 健康检查
    max_fails=3 fail_timeout=30s;
}
```

### 3.2 会话保持

```nginx
# ip_hash 会话保持
upstream backend {
    ip_hash;
    server 10.0.0.1:8080;
    server 10.0.0.2:8080;
    server 10.0.0.3:8080;
}

# cookie 会话保持
upstream backend {
    server 10.0.0.1:8080;
    server 10.0.0.2:8080;
    
    sticky cookie srv_id expires=1h domain=.example.com path=/;
}
```

---

## 4. 缓存配置

### 4.1 Proxy Cache

```nginx
proxy_cache_path /var/cache/nginx levels=1:2 
                 keys_zone=my_cache:10m 
                 max_size=10g 
                 inactive=60m 
                 use_temp_path=off;

server {
    location / {
        proxy_cache my_cache;
        proxy_cache_key $scheme$request_method$host$request_uri;
        proxy_cache_valid 200 302 10m;
        proxy_cache_valid 404 1m;
        proxy_cache_use_stale error timeout updating http_500 http_502 http_503 http_504;
        add_header X-Cache-Status $upstream_cache_status;
    }
}
```

### 4.2 FastCGI Cache

```nginx
fastcgi_cache_path /var/cache/nginx/fastcgi 
                   levels=1:2 
                   keys_zone=FCACHE:10m 
                   max_size=1g 
                   inactive=60m;

server {
    location ~ \.php$ {
        fastcgi_cache FCACHE;
        fastcgi_cache_key $scheme$request_method$host$request_uri;
        fastcgi_cache_valid 200 302 10m;
        fastcgi_cache_valid 404 1m;
        fastcgi_cache_use_stale error timeout updating http_500 http_502 http_503 http_504;
        fastcgi_cache_lock on;
        fastcgi_cache_lock_timeout 5s;
        fastcgi_cache_lock_age 5s;
    }
}
```

---

## 5. 安全配置

### 5.1 SSL/TLS

```nginx
server {
    listen 443 ssl http2;
    server_name example.com;
    
    ssl_certificate /etc/nginx/ssl/example.com.crt;
    ssl_certificate_key /etc/nginx/ssl/example.com.key;
    
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;
    ssl_session_tickets off;
    ssl_stapling on;
    ssl_stapling_verify on;
    
    # HSTS
    add_header Strict-Transport-Security "max-age=63072000" always;
}
```

### 5.2 访问控制

```nginx
# IP 限制
deny 192.168.1.1;
allow 10.0.0.0/8;
deny all;

# 速率限制
limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
limit_req zone=api burst=20 nodelay;

# 连接限制
limit_conn_zone $binary_remote_addr zone=addr:10m;
limit_conn addr 100;
```

---

## 6. 性能调优

### 6.1 内核调优

```bash
# /etc/sysctl.conf
net.core.somaxconn = 65535
net.ipv4.tcp_max_syn_backlog = 65535
net.ipv4.tcp_tw_reuse = 1
net.ipv4.ip_local_port_range = 1024 65535
net.core.netdev_max_backlog = 65535
```

### 6.2 监控指标

```nginx
# stub_status 模块
location /nginx_status {
    stub_status;
    allow 127.0.0.1;
    deny all;
}
```

---

## 7. 故障排查

### 7.1 常见问题

| 问题 | 症状 | 排查命令 | 解决方案 |
|------|------|----------|----------|
| 连接数满 | 502/504 | `netstat -an | grep ESTABLISHED` | 增加 worker_connections |
| 文件描述符满 | 500 | `ulimit -n` | 增加 ulimit |
| 内存泄漏 | 内存持续增长 | `top` | 重启 nginx |
| 高CPU | CPU 100% | `top` | 检查配置、压缩级别 |

### 7.2 日志分析

```bash
# 查看错误日志
tail -f /var/log/nginx/error.log

# 分析访问日志
awk '{print $1}' access.log | sort | uniq -c | sort -rn | head

# 查找慢请求
awk '$7 > 1 {print $0}' access.log
```

---

## 8. 总结

### 8.1 核心配置回顾

| 配置项 | 推荐值 | 说明 |
|--------|--------|------|
| worker_processes | auto | 等于CPU核数 |
| worker_connections | 65535 | 根据内存调整 |
| keepalive_timeout | 65 | 根据业务调整 |
| gzip | on | 节省带宽 |
| sendfile | on | 提升性能 |

### 8.2 性能指标目标

| 指标 | 目标值 |
|------|--------|
| QPS | > 100K |
| P99 延迟 | < 10ms |
| CPU 使用率 | < 70% |
| 内存使用率 | < 80% |

---

*最后更新：2026-08-11*
*作者：Ryan*
