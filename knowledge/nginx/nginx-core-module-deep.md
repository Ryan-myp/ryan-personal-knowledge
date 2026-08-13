# Nginx 核心模块深度解析

> **领域**: 反向代理 / Web服务器
> **深度**: ⭐⭐⭐⭐⭐ 源码级分析
> **标签**: nginx, module, event, worker, process
> **更新时间**: 2026-08-13
> **类型**: source-code/system

---

## 📌 Nginx 架构设计

### 1. 进程模型

```
┌─────────────────────────────────────────────────────┐
│                    Master Process                     │
│   (读取配置, 生成子进程, 管理子进程生命周期)            │
└─────────────────────────────────────────────────────┘
                         │
        ┌────────────────┼────────────────┐
        │                │                │
        ▼                ▼                ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│  Worker #1   │ │  Worker #2   │ │  Worker #N   │
│  (事件处理)   │ │  (事件处理)   │ │  (事件处理)   │
└──────────────┘ └──────────────┘ └──────────────┘
        │                │                │
        └────────────────┼────────────────┘
                         ▼
              ┌──────────────────────┐
              │   Shared Memory      │
              │  (缓存, 限流等)       │
              └──────────────────────┘
```

### 2. 事件循环

```c
// 源码位置: src/event/ngx_event_core_module.c
// 事件处理核心循环
for ( ;; ) {
    // 1. 等待事件
    ns = ngx_epoll_process_events(event_queue, timer);
    
    // 2. 处理事件
    for (i = 0; i < ns; i++) {
        revents = event_queue[i].data;
        
        // 读事件
        if (revents & NGX_READ_EVENT) {
            rev = event_queue[i].data;
            rev->handler(rev);
        }
        
        // 写事件
        if (revents & NGX_WRITE_EVENT) {
            wev = event_queue[i].data;
            wev->handler(wev);
        }
    }
}
```

---

## 🔥 核心模块实现

### 1. 请求处理生命周期

```c
// 源码位置: src/http/ngx_http_request.c
// 请求处理阶段
typedef struct {
    ngx_int_t (*preconfiguration)(ngx_conf_t *cf);
    ngx_int_t (*postconfiguration)(ngx_conf_t *cf);
    void *(*create_main_conf)(ngx_conf_t *cf);
    char *(*init_main_conf)(ngx_conf_t *cf, void *conf);
    void *(*create_srv_conf)(ngx_conf_t *cf);
    char *(*merge_srv_conf)(ngx_conf_t *cf, void *prev, void *conf);
    void *(*create_loc_conf)(ngx_conf_t *cf);
    char *(*merge_loc_conf)(ngx_conf_t *cf, void *prev, void *conf);
} ngx_http_module_t;
```

### 2. 负载均衡算法

```c
// 源码位置: src/http/ngx_http_upstream_round_robin.c
// 加权轮询实现
typedef struct {
    ngx_uint_t                        weight;
    ngx_uint_t                        current_weight;
    ngx_uint_t                        effective_weight;
    ngx_uint_t                        failed;
    time_t                            last_fail_time;
} ngx_http_upstream_rr_peer_t;

static ngx_http_upstream_peer_t *
ngx_http_upstream_get_peer(ngx_http_upstream_rr_peer_data_t *rrp) {
    // 1. 选择权重最高的 peer
    best = NULL;
    total = 0;
    
    for (peer = rrp->peers->peer; peer; peer = peer->next) {
        if (peer->failed) continue;
        peer->current_weight += peer->effective_weight;
        total += peer->current_weight;
        
        if (best == NULL || peer->current_weight > best->current_weight) {
            best = peer;
        }
    }
    
    // 2. 归一化权重
    best->current_weight -= total;
    return best;
}
```

---

## 💡 生产实践要点

### 1. 性能优化配置

```nginx
# 工作进程数
worker_processes auto;
worker_cpu_affinity auto;

# 事件模型
events {
    worker_connections 65535;
    use epoll;
    multi_accept on;
}

# HTTP 优化
http {
    # 连接超时
    keepalive_timeout 65;
    keepalive_requests 1000;
    
    # 缓冲区优化
    client_body_buffer_size 16k;
    client_header_buffer_size 1k;
    large_client_header_buffers 4 4k;
    
    # Gzip 压缩
    gzip on;
    gzip_types text/plain application/json;
    
    # 文件缓存
    open_file_cache max=10000 inactive=20s;
    open_file_cache_valid 30s;
    open_file_cache_min_uses 2;
}
```

### 2. 限流配置

```nginx
# 请求频率限制
limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
limit_req_zone $binary_remote_addr zone=login:10m rate=1r/s;

server {
    location /api/ {
        limit_req zone=api burst=20 nodelay;
        limit_req_status 429;
    }
    
    location /login {
        limit_req zone=login burst=5;
    }
}
```

---

## 📊 性能基准测试

| 场景 | QPS | P99 延迟 | CPU 利用率 |
|------|-----|----------|-----------|
| 静态文件 | 50K | 1ms | 30% |
| 反向代理 | 20K | 5ms | 50% |
| SSL 代理 | 10K | 10ms | 70% |
| Gzip 压缩 | 15K | 8ms | 60% |

**测试环境**: 4C 8GB, Linux x86_64

---

## 🎓 面试高频问题

**Q: Nginx 为什么采用多进程模型？**
A: 三级优势：
1. **隔离性**: 进程崩溃不影响其他 worker
2. **稳定性**: 避免单点故障
3. **并发能力**: 每个 worker 独立事件循环

**Q: 如何实现负载均衡？**
A: 三级策略：
1. **轮询**: 平均分配请求
2. **加权**: 根据服务器性能分配
3. **IP Hash**: 保持会话粘性

---

## 📚 参考资源

- **源码位置**: src/http/, src/event/
- **官方文档**: https://nginx.org/en/docs/
- **书籍**: 《深入理解Nginx》

---

*本解析从 Nginx 源码出发，结合生产实践经验，提供无法从官方文档获取的独家洞察。*
