# Nginx 生产环境实战

> 深入 Nginx 架构、性能优化、SSL 配置。

---

## 1. 核心配置

```nginx
worker_processes auto;
worker_rlimit_nofile 65535;

events {
    worker_connections 10240;
    multi_accept on;
    use epoll;
}

http {
    # 基础设置
    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    
    # 超时设置
    keepalive_timeout 65;
    keepalive_requests 1000;
    
    # Gzip 压缩
    gzip on;
    gzip_types text/plain application/json;
    
    # 日志格式
    log_format main '$remote_addr - $remote_user [$time_local] "$request" '
                    '$status $body_bytes_sent "$http_referer" '
                    '"$http_user_agent" "$http_x_forwarded_for"';
}
```

---

## 2. SSL 配置

```nginx
server {
    listen 443 ssl http2;
    server_name example.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;
}
```

---

## 3. 性能优化

| 优化项 | 配置 | 效果 |
|--------|------|------|
| 开启 Gzip | gzip on | 减少传输大小 |
| 启用缓存 | proxy_cache | 加速响应 |
| 调整 worker | worker_processes auto | 利用多核 |
| 连接复用 | keepalive_timeout | 减少握手 |

---

## 4. 常见问题排查

```bash
# 查看连接状态
ss -s

# 检查配置
nginx -t

# 实时监控
tail -f /var/log/nginx/access.log

# 性能分析
ab -n 1000 -c 100 http://example.com/
```

---

**参考**: Nginx 官方文档、高性能 Web 服务器最佳实践
