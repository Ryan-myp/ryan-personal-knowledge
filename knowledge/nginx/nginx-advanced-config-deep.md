# Nginx 高级配置实战

> 深入 Nginx 高级配置：反向代理、负载均衡、SSL/TLS、缓存、限流。

---

## 1. 反向代理配置

```nginx
server {
    listen 80;
    server_name api.example.com;
    
    location / {
        proxy_pass http://backend_cluster;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
}
```

---

## 2. 负载均衡策略

```nginx
upstream backend_cluster {
    ip_hash;
    
    server 10.0.0.1:8080 weight=5;
    server 10.0.0.2:8080 weight=3;
    server 10.0.0.3:8080 backup;
}
```

---

## 3. SSL/TLS 配置

```nginx
server {
    listen 443 ssl http2;
    
    ssl_certificate /etc/ssl/certs/example.com.crt;
    ssl_certificate_key /etc/ssl/private/example.com.key;
    
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;
}
```

---

## 4. 限流配置

```nginx
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;

server {
    location /api/ {
        limit_req zone=api_limit burst=20 nodelay;
        limit_req_status 429;
    }
}
```

---

## 5. 实践 Checklist
- [ ] 配置合理的超时时间
- [ ] 选择合适的负载均衡策略
- [ ] 启用 TLS 1.2/1.3
- [ ] 设置限流规则

**参考**: Nginx 官方文档、高性能 Nginx 配置指南
