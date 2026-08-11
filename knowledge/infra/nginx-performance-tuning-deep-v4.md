# Nginx性能调优深度解析

> 深入Nginx性能调优：事件模型、缓存策略、压缩优化、安全加固。
> 源码级分析，包含生产环境最佳实践。
> 适用对象：运维工程师、后端工程师

---

## 1. 事件模型

### 1.1 工作模式

```
Nginx事件模型：

┌─────────────────────────────────────────────────────────────┐
│  事件处理模型：                                              │
│  ├── select：最多1024连接，轮询                              │
│  ├── poll：无连接数限制，轮询                                │
│  ├── epoll（Linux推荐）：边缘触发，高效                       │
│  ├── kqueue（BSD/macOS）：高效                               │
│  └── /dev/poll（Solaris）                                   │
│                                                             │
│  配置：                                                      │
│  events {                                                    │
│    use epoll;                                               │
│    worker_connections 65535;                                 │
│    multi_accept on;                                          │
│  }                                                           │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. 性能调优

### 2.1 关键参数

```
Nginx性能调优：

┌─────────────────────────────────────────────────────────────┐
│   worker_processes：auto（自动匹配CPU核数）                    │
│  ├── worker_connections：单worker最大连接数                    │
│  ├── keepalive_timeout：保持连接超时                           │
│  └── keepalive_requests：单连接最大请求数                      │
│                                                             │
│  文件描述符：                                                │
│  ├── worker_rlimit_nofile：最大打开文件数                      │
│  └── ulimit -n 65535                                        │
│                                                             │
│  缓冲优化：                                                  │
│  ├── client_body_buffer_size：请求体缓冲区                     │
│  ├── client_header_buffer_size：请求头缓冲区                   │
│  ├── large_client_header_buffers：大请求头缓冲区               │
│  └── proxy_buffer_size：代理缓冲区                            │
│                                                             │
│  压缩优化：                                                  │
│  ├── gzip on；gzip_types text/plain application/json         │
│  └── gzip_min_length 1000                                    │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. 自测题

### 3.1 单选题

1. Nginx在Linux上推荐的事件模型是：
   A. select  B. poll  C. epoll  D. kqueue
   答案：C

---

> 本文档适用对象：运维工程师、后端工程师
> 难度：资深专家级
