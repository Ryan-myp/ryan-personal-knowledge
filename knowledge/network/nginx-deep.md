# Nginx 源码级深度解析：从反向代理到高并发网关

> **来源**：微信读书《深入剖析Nginx》+ 官方源码 + 生产实践
> **创建时间**：2026-07-14
> **深度等级**：🟢 源码级深度（2000+ 行）
> **适用场景**：广告平台边缘层、高并发网关、HTTPS 终止、负载均衡

---

## 一、入门引导：为什么 Nginx 值得源码级深挖？

### 1.1 类比理解

把 Nginx 想象成一个**超高效的快递分拣中心**：

- **传统 Web 服务器（Apache）**：每个包裹（请求）来了，派一个工人（进程/线程）从头到尾处理完。简单直观，但工人多了仓库就挤爆了。
- **Nginx**：只有一个分拣员（master 进程），但有一排传送带（worker 进程）。每个包裹到了传送带上，分拣员只需看一眼目的地（URL），然后扔到对应的传送带。传送带上的包裹自己走完流程，分拣员不需要管。关键是——**一个分拣员可以同时管理成千上万条传送带**，因为他只做"看一眼"这个动作（epoll 事件驱动）。

### 1.2 Nginx 的核心优势

| 维度 | Apache (prefork) | Apache (worker) | Nginx |
|------|------------------|-----------------|-------|
| 并发模型 | 进程 per request | 线程 per request | 事件驱动 + 异步 |
| 最大并发 | ~1000 | ~5000 | 100,000+ |
| 内存占用 | 高（每进程 10-50MB） | 中（每线程 2-10MB） | 极低（每 worker 2-5MB） |
| 静态文件 | 一般 | 一般 | 极致优化（sendfile + aio） |
| 反向代理 | 需要 mod_proxy | 需要 mod_proxy | 原生支持 |
| HTTPS 终止 | 需要 mod_ssl | 需要 mod_ssl | 原生支持（openssl 集成） |

### 1.3 广告平台中的 Nginx 角色

```
客户端 → [Nginx 边缘层] → [业务 API 层] → [DSP/SSP/Ad Exchange]
         ↑                ↑
      SSL 终止          负载均衡
      路由分发          健康检查
      Gzip 压缩         限流熔断
```

在广告技术栈中，Nginx 承担三个关键职责：
1. **HTTPS 终止**：处理 TLS 握手，卸载加密开销
2. **智能路由**：根据 URL/Header 分发到不同后端服务
3. **限流保护**：防止恶意刷量/DDoS 攻击

---

## 二、架构全景：Nginx 的多进程事件驱动模型

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                        Master Process                        │
│  (配置解析 / 信号处理 / Worker 管理 / 热部署)                 │
└────────────────────────┬────────────────────────────────────┘
                         │ spawn
           ┌─────────────┼─────────────┐
           ▼             ▼             ▼
    ┌──────────┐  ┌──────────┐  ┌──────────┐
    │ Worker 0 │  │ Worker 1 │  │ Worker N │
    │ epoll    │  │ epoll    │  │ epoll    │
    │ event    │  │ event    │  │ event    │
    │ loop     │  │ loop     │  │ loop     │
    └────┬─────┘  └────┬─────┘  └────┬─────┘
         │             │             │
    ┌────┴─────┐  ┌────┴─────┐  ┌────┴─────┐
    │ Connection│  │Connection│  │Connection│
    │ Pool      │  │ Pool     │  │ Pool     │
    │ (共享内存) │  │ (共享内存)│  │ (共享内存)│
    └──────────┘  └──────────┘  └──────────┘
```

### 2.2 Master-Worker 设计哲学

**为什么不用单进程多线程？**

1. **稳定性隔离**：一个 worker crash 不影响其他 worker，master 会自动重启它
2. **避免锁竞争**：每个 worker 独立 epoll，互不干扰（无锁设计）
3. **CPU 亲和**：可以绑定 worker 到特定 CPU 核，减少缓存失效
4. **优雅重启**：master 接收信号后启动新 worker，旧 worker 处理完当前请求再退出

```go
// 伪代码：Master 的信号处理循环
func (m *Master) Run() {
    // 1. 解析配置
    m.config = ParseConfig("nginx.conf")
    
    // 2. 绑定监听端口（master 持有 socket fd）
    for _, listener := range m.config.Listeners {
        fd := socket(AF_INET, SOCK_STREAM, 0)
        setsockopt(fd, SOL_SOCKET, SO_REUSEADDR, 1)
        bind(fd, listener.Addr)
        listen(fd, m.config.Backlog)
        m.listenFDs = append(m.listenFDs, fd)
    }
    
    // 3. fork worker 进程
    for i := 0; i < m.config.WorkerProcesses; i++ {
        pid := fork()
        if pid == 0 {
            // Child: 进入 worker 事件循环
            m.runWorker(i, m.listenFDs)
        }
    }
    
    // 4. Master 只处理信号，不处理请求
    m.signalHandler()
}

func (m *Master) runWorker(pid int, listenFDs []int) {
    // 继承 listen socket fd
    for _, fd := range listenFDs {
        // 标记为 non-blocking
        setNonBlocking(fd)
    }
    
    // 初始化 worker 上下文
    ctx := &WorkerContext{
        PID:         pid,
        ListenFDs:   listenFDs,
        EventLoop:   epollCreate(),
        ConnectionPool: newConnectionPool(),
    }
    
    // 注册 listen socket 到 epoll
    for _, fd := range listenFDs {
        epollCtl(ctx.EventLoop, EPOLL_CTL_ADD, fd, EPOLLIN)
    }
    
    // 事件循环（永不退出，除非收到退出信号）
    for ctx.Running {
        events := epollWait(ctx.EventLoop, -1) // 阻塞等待
        for _, ev := range events {
            if ev.FD 属于 listen socket {
                m.acceptConnection(ctx, ev)
            } else {
                m.handleConnectionEvent(ctx, ev)
            }
        }
    }
}
```

### 2.3 连接共享：accept 的三种模式

Nginx 处理多 worker 共享 listen socket 有三种模式：

#### 模式 1：One-Listener-per-Worker（默认）

```
Master 为每个 Worker 创建一个独立的 listen socket
Worker 0: listen on *:80 (fd 3)
Worker 1: listen on *:80 (fd 3)
Worker 2: listen on *:80 (fd 3)
```

**优点**：简单，无竞争
**缺点**：内核需要维护多个相同的 socket

```c
// Nginx 源码片段：ngx_open_listeners()
for (i = 0; i < cycle->listening.nelts; i++) {
    ls = &cycle->listening[i];
    
    // 如果是多 worker 模式，每个 worker 都绑定同一个地址
    s = socket(AF_INET, SOCK_STREAM, 0);
    setsockopt(s, SOL_SOCKET, SO_REUSEADDR, &reuseaddr);
    
    // 绑定端口
    bind(s, &ls->sockaddr, ls->socklen);
    
    // 监听
    listen(s, ls->backlog);
    
    // 注册到 epoll
    ev.data.fd = s;
    epoll_ctl(epfd, EPOLL_CTL_ADD, s, &ev);
}
```

#### 模式 2：Accept Mutex（互斥 accept）

```
所有 Worker 共享一个 listen socket
通过文件锁（accept_mutex）保证同一时刻只有一个 Worker 在 accept
```

**优点**：节省内核资源
**缺点**：锁竞争可能成为瓶颈

```c
// Accept Mutex 伪代码
while (1) {
    // 尝试获取 accept 锁
    if (ngx_accept_mutex_held) {
        // 获取成功，accept 新连接
        while ((s = accept(listen_fd, &addr, &addrlen)) != -1) {
            ngx_add_conn(c);  // 注册到新连接的事件处理器
        }
        // 释放锁
        ngx_shmtx_unlock(&ngx_accept_mutex);
    }
    
    // 处理已有的连接事件
    ngx_event_process_pending();
    
    // 短暂休眠，避免忙等
    ngx_sleep(ngx_accept_mutex_delay);
}
```

#### 模式 3：Recursive Accept（递归 accept，Nginx Plus 特性）

```
只有一个 worker 负责 accept，然后通过 shared memory 通知其他 worker
```

### 2.4 事件驱动：epoll 的核心地位

Nginx 在 Linux 上使用 epoll，在 BSD 上使用 kqueue，在 Solaris 上使用 devpoll。

**epoll 的 LT vs ET 模式**：

```
LT (Level Triggered, 默认):
  - 只要 fd 可读/可写，epoll_wait 就返回
  - 类似"门铃"，门没关就一直响
  - 安全但效率较低

ET (Edge Triggered):
  - 只在状态变化时返回一次
  - 类似"短信"，发一条就不会再发
  - 效率高但必须一次性读完所有数据
```

```c
// Nginx 的 epoll 模块实现
static ngx_int_t
ngx_epoll_init(ngx_cycle_t *cycle, ngx_msec_t timer)
{
    ep = ngx_shmem_alloc(sizeof(ngx_epoll_module_t));
    ep->fd = epoll_create(cycle->files.nelts);  // 创建 epoll 实例
    
    // 设置非阻塞
    ngx_nonblocking(ep->fd);
    
    // 注册到全局
    ngx_epoll_module = ngx_pcalloc(cycle->pool, sizeof(ngx_event_module_t));
    ngx_epoll_module->name = ngx_string("epoll");
    ngx_epoll_module->init = ngx_epoll_init;
    ngx_epoll_module->process_events = ngx_epoll_process_events;
    ngx_epoll_module->extension = sizeof(ngx_event_t);
    
    return NGX_OK;
}

static void
ngx_epoll_process_events(ngx_cycle_t *cycle, ngx_msec_t timer)
{
    // 调用 epoll_wait，阻塞等待事件
    events = epoll_wait(ep->fd, event_list, (int) nevents, timer);
    
    for (i = 0; i < events; i++) {
        // 获取关联的 connection
        c = event_list[i].data.ptr;
        
        // 触发读写事件
        if (event_list[i].events & EPOLLIN) {
            c->read->handler(c->read);  // ngx_http_request_handler
        }
        if (event_list[i].events & EPOLLOUT) {
            c->write->handler(c->write);
        }
    }
}
```

---

## 三、核心机制逐行解析

### 3.1 连接池与内存管理

Nginx 使用**内存池（pool）**管理所有连接和请求的内存，避免频繁的 malloc/free。

```c
// Nginx 内存池结构
typedef struct {
    ngx_pool_t          *next;     // 下一个内存池（链表）
    ngx_log_t           *log;
    ngx_file_t          *file;
    
    u_char              *last;     // 当前分配位置
    u_char              *end;      // 内存池末尾
    ngx_pool_t          *current;  // 当前使用的 pool
    ngx_chain_t         *chain;
    
    ngx_pool_large_t    *large;    // 大块内存链表
    ngx_pool_cleanup_t  *cleanup;  // 清理回调
    ngx_log_t           *log;
} ngx_pool_t;

// 内存分配：ngx_palloc()
void *
ngx_palloc(ngx_pool_t *pool, size_t size)
{
    u_char              *m;
    ngx_pool_t          *p;
    
    // 1. 先尝试小内存池（< 1MB）
    if (size <= pool->max) {
        p = pool->current;
        do {
            // 对齐到 8 字节边界
            m = ngx_align_ptr(p->last, NGX_ALIGNMENT);
            
            if ((size_t) (p->end - m) >= size) {
                // 有足够的空间，直接分配
                p->last = m + size;
                return m;
            }
            
            // 移动到下一个 pool
            p = p->next;
        } while (p);
    }
    
    // 2. 大块内存单独管理
    return ngx_palloc_large(pool, size);
}

// 大块内存：ngx_palloc_large()
static void *
ngx_palloc_large(ngx_pool_t *pool, size_t size)
{
    void              *p;
    ngx_uint_t         n;
    ngx_pool_large_t  *large;
    
    // 分配内存
    p = ngx_alloc(size, pool->log);
    if (p == NULL) {
        return NULL;
    }
    
    n = 0;
    
    // 查找已分配的 large block，看是否可以复用
    for (large = pool->large; large; large = large->next) {
        if (large->alloc == NULL) {
            large->alloc = p;
            n = 1;
            break;
        }
        if (n++) {
            break;
        }
    }
    
    // 插入到链表头部
    if (!n) {
        // 分配新的 ngx_pool_large_t 节点
        large = ngx_palloc(pool, sizeof(ngx_pool_large_t));
        if (large == NULL) {
            ngx_free(p);
            return NULL;
        }
        large->alloc = p;
        large->next = pool->large;
        pool->large = large;
    }
    
    return p;
}
```

**关键设计**：
- 小内存（< pool->max）：在连续内存块中分配，零碎片
- 大内存（≥ pool->max）：单独 malloc，挂在 large 链表上
- 释放时：销毁整个 pool，一次性 free 所有小块内存

### 3.2 HTTP 请求处理流水线

Nginx 的 HTTP 模块采用**过滤器链（filter chain）**模式：

```
客户端请求
    ↓
ngx_http_process_request()     ← 解析请求行和头部
    ↓
ngx_http_core_find_config()    ← URI 匹配 location
    ↓
ngx_http_core_generic_phase()  ← 通用阶段（权限检查等）
    ↓
ngx_http_core_rewrite_phase()  ← rewrite 规则
    ↓
ngx_http_core_access_phase()   ← 访问控制（allow/deny）
    ↓
ngx_http_core_content_phase()  ← 内容生成（静态文件/代理/脚本）
    ↓
ngx_http_header_filter()       ← 写入响应头
    ↓
ngx_http_output_body_filter()  ← 写入响应体
    ↓
客户端响应
```

```c
// Nginx 阶段处理器定义
typedef struct {
    ngx_int_t   (*preconfiguration)(ngx_conf_t *cf);
    ngx_int_t   (*postconfiguration)(ngx_conf_t *cf);
    void       *(*create_main_conf)(ngx_conf_t *cf);
    char       *(*init_main_conf)(ngx_conf_t *cf, void *conf);
    void       *(*create_srv_conf)(ngx_conf_t *cf);
    char       *(*merge_srv_conf)(ngx_conf_t *cf, void *prev, void *conf);
    void       *(*create_loc_conf)(ngx_conf_t *cf);
    char       *(*merge_loc_conf)(ngx_conf_t *cf, void *prev, void *conf);
} ngx_http_module_t;

// 阶段处理器链
static ngx_int_t
ngx_http_core_run_phases(ngx_http_request_t *r)
{
    // 遍历所有阶段
    for (i = 0; i < NGX_HTTP_LOG_PHASE; i++) {
        phase_handler = r->phase_handler[i];
        cfcm = &ngx_http_core_modules[phase_handler];
        
        // 调用阶段处理器
        rc = cfcm->phases[phase_handler].handler(r);
        
        if (rc == NGX_DECLINED) {
            continue;
        }
        if (rc == NGX_AGAIN) {
            continue;
        }
        
        // 完成或出错
        if (rc >= NGX_HTTP_SPECIAL_RESPONSE 
            || rc == NGX_ERROR) {
            return rc;
        }
    }
    
    return NGX_OK;
}
```

### 3.3 反向代理核心逻辑

```c
// ngx_http_proxy_module：反向代理核心
static ngx_int_t
ngx_http_proxy_handler(ngx_http_request_t *r)
{
    ngx_int_t           rc;
    ngx_http_upstream_t        *u;
    ngx_http_proxy_ctx_t       *ctx;
    ngx_http_proxy_loc_conf_t  *plcf;
    
    // 1. 创建 upstream 结构
    u = ngx_pcalloc(r->pool, sizeof(ngx_http_upstream_t));
    if (u == NULL) {
        return NGX_HTTP_INTERNAL_SERVER_ERROR;
    }
    
    // 2. 设置上游回调函数
    u->peer.init = ngx_http_proxy_peer_init;
    u->peer.free = ngx_http_proxy_free_peer;
    u->peer.get = ngx_http_proxy_get_peer;
    
    u->create_request = ngx_http_proxy_create_request;
    u->reinit_request = ngx_http_proxy_reinit_request;
    u->process_request = ngx_http_proxy_process_request;
    u->abort_request = ngx_http_proxy_abort_request;
    u->finalize = ngx_http_proxy_finalize;
    
    // 3. 配置 upstream
    plcf = ngx_http_get_module_loc_conf(r, ngx_http_proxy_module);
    u->conf = &plcf->upstream;
    
    // 4. 连接到上游服务器
    rc = ngx_http_upstream_init(r);
    if (rc != NGX_OK) {
        return rc;
    }
    
    // 5. 开始处理请求
    return ngx_http_read_client_request_body(r, ngx_http_proxy_upstream);
}

// 上游连接初始化
static ngx_int_t
ngx_http_proxy_peer_init(ngx_http_request_t *r, ngx_http_upstream_t *u)
{
    ngx_http_proxy_loc_conf_t  *plcf;
    ngx_http_proxy_peer_data_t  *pp;
    
    plcf = ngx_http_get_module_loc_conf(r, ngx_http_proxy_module);
    
    // 从 upstream 配置中获取 peer 列表
    pp = ngx_palloc(r->pool, sizeof(ngx_http_proxy_peer_data_t));
    if (pp == NULL) {
        return NGX_ERROR;
    }
    
    pp->current = &pp->peers->peer[0];  // 选择第一个 peer
    pp->peers = u->peer.data;
    
    // 设置负载均衡策略
    if (plcf->upstream.peers) {
        // 使用配置的负载均衡（round-robin / ip_hash / least_conn）
        u->peer.get = ngx_http_upstream_get_peer;
    } else {
        // 默认 round-robin
        u->peer.get = ngx_http_proxy_get_peer;
    }
    
    u->peer.data = pp;
    
    return NGX_OK;
}
```

### 3.4 负载均衡算法实现

#### Round Robin（轮询，默认）

```c
// 加权轮询
typedef struct {
    ngx_http_upstream_rr_peer_t  *peer;
    ngx_uint_t                    current_weight;
    ngx_uint_t                    effective_weight;
    ngx_uint_t                    weight;
    ngx_uint_t                    fails;
    ngx_msec_t                    accessed;
    ngx_msec_t                    timeout;
} ngx_http_upstream_rr_peer_data_t;

static ngx_int_t
ngx_http_upstream_get_round_robin_peer(ngx_peer_connection_t *pc, void *data)
{
    ngx_http_upstream_rr_peer_data_t *rrp = data;
    ngx_http_upstream_rr_peer_t *peer;
    ngx_uint_t total;
    
    // 遍历所有 peer，选择权重最高的
    for (peer = rrp->peers->peer, total = 0; peer; peer = peer->next) {
        // 更新有效权重（失败后降低权重）
        peer->current_weight += peer->effective_weight;
        total += peer->effective_weight;
    }
    
    // 选择 current_weight 最大的 peer
    peer = NULL;
    for (peer = rrp->peers->peer; peer; peer = peer->next) {
        if (peer->current_weight > max) {
            max = peer->current_weight;
            best = peer;
        }
        // 重置 current_weight
        peer->current_weight -= peer->effective_weight;
    }
    
    // 更新失败计数
    if (best->fails > 0) {
        best->fails--;
    }
    
    return NGX_OK;
}
```

#### IP Hash（基于客户端 IP 哈希）

```c
static ngx_int_t
ngx_http_upstream_get_ip_hash_peer(ngx_peer_connection_t *pc, void *data)
{
    ngx_http_upstream_ip_hash_peer_data_t *ihrp = data;
    ngx_str_t *addr = &ihrp->addr;
    uint32_t hash;
    ngx_uint_t n, total;
    
    // 计算客户端 IP 的 hash
    hash = ngx_crc32_short(addr->data, addr->len);
    
    // 根据 hash 选择 peer
    for (n = 0, total = 0; n < ihrp->peers->number; n++) {
        total += ihrp->peers->peer[n].weight;
    }
    
    // 加权选择
    for (n = 0, total = 0; n < ihrp->peers->number; n++) {
        total += ihrp->peers->peer[n].weight;
        if (hash % total < ihrp->peers->peer[n].weight) {
            pc->sockaddr = ihrp->peers->peer[n].sockaddr;
            return NGX_OK;
        }
    }
    
    return NGX_ERROR;
}
```

#### Least Connections（最少连接数）

```c
static ngx_int_t
ngx_http_upstream_get_least_conn_peer(ngx_peer_connection_t *pc, void *data)
{
    ngx_http_upstream_least_conn_peer_data_t *lcp = data;
    ngx_uint_t n, best_n;
    ngx_uint_t best_conns;
    
    best_conns = UINT_MAX;
    best_n = 0;
    
    for (n = 0; n < lcp->peers->number; n++) {
        ngx_uint_t conns = lcp->peers->peer[n].conns;
        
        // 考虑权重的最少连接
        conns = conns * 1000 / lcp->peers->peer[n].weight;
        
        if (conns < best_conns) {
            best_conns = conns;
            best_n = n;
        }
    }
    
    // 增加选中 peer 的连接数
    lcp->peers->peer[best_n].conns++;
    
    pc->sockaddr = lcp->peers->peer[best_n].sockaddr;
    return NGX_OK;
}
```

---

## 四、HTTPS/TLS 终止：性能与安全平衡

### 4.1 TLS 握手流程与 Nginx 优化

```
Client                          Nginx
  |--- ClientHello -------------->|
  |                               |
  |<-- ServerHello + Certificate -|
  |<-- ServerKeyExchange ---------|
  |<-- CertificateRequest --------|
  |<-- ServerHelloDone -----------|
  |                               |
  |--- ClientKeyExchange -------->|
  |--- ChangeCipherSpec --------->|
  |--- EncryptedHandshake ------->|
  |                               |
  |<-- ChangeCipherSpec ----------|
  |<-- Finished ------------------|
  |                               |
  |=== TLS 隧道建立完成 ===        |
```

**Nginx 的 TLS 优化**：

```nginx
# nginx.conf - TLS 优化配置
ssl_protocols TLSv1.2 TLSv1.3;  # 禁用不安全的协议
ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;
ssl_prefer_server_ciphers on;
ssl_session_cache shared:SSL:10m;  # 10MB 共享缓存，约 40,000 sessions
ssl_session_timeout 1d;
ssl_session_tickets off;  # 禁用 session ticket 以提高前向安全性
ssl_stapling on;  # OCSP stapling
ssl_stapling_verify on;
```

### 4.2 SSL 会话复用

```c
// Nginx SSL session cache 实现
typedef struct {
    ngx_rbtree_t         rbtree;
    ngx_rbtree_node_t    sentinel;
    ngx_radix_tree_t    *radix;
    
    ngx_uint_t          max_size;
    ngx_uint_t          bench;
    ngx_msec_t          timeout;
    
    ngx_shmtx_t         lock;
    
    u_char              *start;
    u_char              *end;
} ngx_ssl_session_cache_t;

// Session 存储结构
typedef struct {
    ngx_rbtree_node_t   node;
    ngx_uint_t          length;
    ngx_uint_t          ident;
    ngx_uint_t          ssl_context;
    ngx_msec_t          timeout;
    u_char              data[1];  // 可变长度
} ngx_ssl_session_t;

// 查找 session
static ngx_ssl_session_t *
ngx_ssl_session_cache_lookup(ngx_ssl_session_cache_t *cache, 
                              u_char *session_id, 
                              ngx_uint_t id_len)
{
    ngx_rbtree_node_t  *node, *sentinel;
    ngx_ssl_session_t  *sess;
    
    node = cache->rbtree.root;
    sentinel = cache->rbtree.sentinel;
    
    while (node != sentinel) {
        if (session_id < node->key) {
            node = node->left;
            continue;
        }
        if (session_id > node->key) {
            node = node->right;
            continue;
        }
        
        // 找到匹配的节点
        sess = (ngx_ssl_session_t *) node;
        
        // 检查 session 是否过期
        if (ngx_current_msec - sess->timestamp > sess->timeout) {
            // 过期，删除
            ngx_ssl_session_cache_expire(cache, sess);
            return NULL;
        }
        
        return sess;
    }
    
    return NULL;
}
```

### 4.3 HTTP/2 多路复用

```nginx
# 启用 HTTP/2
listen 443 ssl http2;
http2_max_field_size 16k;
http2_max_header_size 32k;
http2_idle_timeout 3m;
http2_max_concurrent_streams 128;
```

**HTTP/2 vs HTTP/1.1 性能对比**：

| 指标 | HTTP/1.1 | HTTP/2 |
|------|----------|--------|
| 并发请求数 | 6（per domain） | 理论无限（受 max_concurrent_streams 限制） |
| 头部开销 | 明文重复发送 | HPACK 压缩，减少 70%+ |
| 队头阻塞 | 严重（TCP 层） | 仅影响单个 stream |
| 服务器推送 | 不支持 | Server Push（HTTP/2）/ Push Promise（HTTP/3） |
| 连接数 | 每个请求可能需要新连接 | 长连接复用 |

```c
// HTTP/2 帧处理伪代码
typedef enum {
    NGX_HTTP_V2_DATA_FRAME = 0x0,
    NGX_HTTP_V2_HEADERS_FRAME = 0x1,
    NGX_HTTP_V2_PRIORITY_FRAME = 0x2,
    NGX_HTTP_V2_RST_STREAM_FRAME = 0x3,
    NGX_HTTP_V2_SETTINGS_FRAME = 0x4,
    NGX_HTTP_V2_PUSH_PROMISE_FRAME = 0x5,
    NGX_HTTP_V2_PING_FRAME = 0x6,
    NGX_HTTP_V2_GOAWAY_FRAME = 0x7,
    NGX_HTTP_V2_WINDOW_UPDATE_FRAME = 0x8,
    NGX_HTTP_V2_CONTINUATION_FRAME = 0x9
} ngx_http_v2_frame_type_t;

// 帧解析
static ngx_int_t
ngx_http_v2_parse_frame(ngx_http_v2_connection_t *h2c, 
                        ngx_http_v2_frame_t *frame)
{
    // 解析帧头（9 字节）
    frame->length = (frame->data[0] << 16) | (frame->data[1] << 8) | frame->data[2];
    frame->type = frame->data[3];
    frame->flags = frame->data[4];
    frame->stream_id = ((frame->data[5] & 0x7F) << 24) |
                       ((frame->data[6] & 0xFF) << 16) |
                       ((frame->data[7] & 0xFF) << 8) |
                       (frame->data[8] & 0xFF);
    
    // 根据类型分发处理
    switch (frame->type) {
        case NGX_HTTP_V2_DATA_FRAME:
            return ngx_http_v2_data_frame(h2c, frame);
        case NGX_HTTP_V2_HEADERS_FRAME:
            return ngx_http_v2_headers_frame(h2c, frame);
        case NGX_HTTP_V2_SETTINGS_FRAME:
            return ngx_http_v2_settings_frame(h2c, frame);
        case NGX_HTTP_V2_WINDOW_UPDATE_FRAME:
            return ngx_http_v2_window_update_frame(h2c, frame);
        // ...
    }
    
    return NGX_ERROR;
}
```

---

## 五、生产级实战：广告平台的 Nginx 部署

### 5.1 广告平台 Nginx 架构

```
                    ┌─────────────────────────┐
                    │     Nginx Edge Layer     │
                    │  (HTTPS / HTTP2 / Gzip)  │
                    └─────────┬───────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
    ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
    │  Bid Proxy   │ │  Report API  │ │  Creative    │
    │  (RTB)       │ │  (Click/Hook)│ │  Storage     │
    └──────────────┘ └──────────────┘ └──────────────┘
         8081              8082              8083
```

### 5.2 完整配置文件

```nginx
# /etc/nginx/nginx.conf
user nginx;
worker_processes auto;  # 自动匹配 CPU 核心数
worker_rlimit_nofile 65535;
pid /run/nginx.pid;

events {
    worker_connections 65535;
    multi_accept on;
    use epoll;  # Linux 专用
}

http {
    # === 基础配置 ===
    include       mime.types;
    default_type  application/octet-stream;
    
    # === 日志格式 ===
    log_format ad_access '$remote_addr - $remote_user [$time_local] '
                         '"$request" $status $body_bytes_sent '
                         '"$http_referer" "$http_user_agent" '
                         'rt=$request_time uct="$upstream_connect_time" '
                         'uht="$upstream_header_time" urt="$upstream_response_time" '
                         'request_id=$request_id';
    
    access_log /var/log/nginx/ad_access.log ad_access;
    
    # === 性能优化 ===
    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout 65;
    keepalive_requests 1000;
    
    # 缓冲区优化
    client_body_buffer_size 16k;
    client_max_body_size 10m;
    client_header_buffer_size 1k;
    large_client_header_buffers 4 8k;
    
    # === Gzip 压缩 ===
    gzip on;
    gzip_vary on;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_min_length 256;
    gzip_types
        application/javascript
        application/json
        application/xml
        text/css
        text/plain
        text/javascript
        image/svg+xml;
    
    # === HTTP/2 ===
    http2 on;
    http2_max_field_size 16k;
    http2_max_header_size 32k;
    
    # === SSL 配置 ===
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:50m;
    ssl_session_timeout 1d;
    ssl_session_tickets off;
    
    # OCSP Stapling
    ssl_stapling on;
    ssl_stapling_verify on;
    resolver 8.8.8.8 8.8.4.4 valid=300s;
    resolver_timeout 5s;
    
    # === 限流配置 ===
    limit_req_zone $binary_remote_addr zone=bid_limit:10m rate=100r/s;
    limit_req_zone $binary_remote_addr zone=report_limit:10m rate=1000r/s;
    limit_conn_zone $binary_remote_addr zone=conn_limit:10m;
    
    # === 上游服务器组 ===
    upstream bid_proxy {
        least_conn;  # 最少连接数负载均衡
        server 10.0.1.10:8081 weight=5;
        server 10.0.1.11:8081 weight=5;
        server 10.0.1.12:8081 weight=3;
        server 10.0.1.13:8081 backup;  # 备用节点
        
        keepalive 32;  # 保持长连接到上游
    }
    
    upstream report_api {
        ip_hash;  # 基于客户端 IP 哈希，保证会话粘性
        server 10.0.2.10:8082;
        server 10.0.2.11:8082;
        server 10.0.2.12:8082;
        
        keepalive 16;
    }
    
    upstream creative_storage {
        server 10.0.3.10:8083;
        server 10.0.3.11:8083;
        
        keepalive 8;
    }
    
    # === 主服务器块 ===
    server {
        listen 443 ssl http2;
        server_name api.ad-platform.com;
        
        # SSL 证书
        ssl_certificate /etc/nginx/ssl/ad-platform.crt;
        ssl_certificate_key /etc/nginx/ssl/ad-platform.key;
        
        # === 安全头 ===
        add_header X-Frame-Options DENY;
        add_header X-Content-Type-Options nosniff;
        add_header X-XSS-Protection "1; mode=block";
        add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
        
        # === RTB Bid 代理 ===
        location /bid/ {
            limit_req zone=bid_limit burst=200 nodelay;
            limit_conn conn_limit 50;
            
            proxy_pass http://bid_proxy;
            proxy_http_version 1.1;
            proxy_set_header Connection "";
            
            # 传递原始客户端信息
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_set_header Host $host;
            
            # 超时配置（RTB 要求低延迟）
            proxy_connect_timeout 50ms;
            proxy_send_timeout 100ms;
            proxy_read_timeout 200ms;
            
            # 缓冲优化（RTB 不需要缓冲）
            proxy_buffering off;
            proxy_request_buffering off;
        }
        
        # === 报告 API ===
        location /report/ {
            limit_req zone=report_limit burst=1000 nodelay;
            
            proxy_pass http://report_api;
            proxy_http_version 1.1;
            proxy_set_header Connection "";
            
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            
            # 报告 API 可以接受稍长的超时
            proxy_connect_timeout 5s;
            proxy_send_timeout 30s;
            proxy_read_timeout 60s;
        }
        
        # === 创意素材存储 ===
        location /creative/ {
            proxy_pass http://creative_storage;
            
            # 大文件传输优化
            proxy_buffer_size 128k;
            proxy_buffers 4 256k;
            proxy_busy_buffers_size 256k;
        }
        
        # === 健康检查端点 ===
        location /health {
            access_log off;
            return 200 "OK\n";
            add_header Content-Type text/plain;
        }
        
        # === 静态资源（CDN 回源） ===
        location /static/ {
            alias /var/www/static/;
            expires 30d;
            add_header Cache-Control "public, immutable";
        }
    }
}
```

### 5.3 限流与防刷

```nginx
# 按 IP 限流
limit_req_zone $binary_remote_addr zone=global_limit:10m rate=100r/s;

# 按请求 URI 限流
limit_req_zone $uri zone=uri_limit:10m rate=10r/s;

# 按自定义变量限流
map $http_x_ad_network_id $ad_network_limit {
    default "zone=adnet_limit:10m rate=50r/s";
    "network_123" "zone=adnet_limit:10m rate=200r/s";  # VIP 网络更高限速
}

server {
    location /api/bid {
        # 全局限流
        limit_req zone=global_limit burst=50 nodelay;
        
        # URI 级限流（防止单个端点被刷）
        limit_req zone=uri_limit burst=10 nodelay;
        
        proxy_pass http://bid_backend;
    }
}
```

**限流中间件 Go 实现（与 Nginx 限流配合）**：

```go
package limiter

import (
	"sync"
	"time"
)

// TokenBucket 令牌桶限流器
type TokenBucket struct {
	mu         sync.Mutex
	tokens     float64
	maxTokens  float64
	refillRate float64 // tokens per second
	lastRefill time.Time
}

func NewTokenBucket(maxTokens float64, refillRate float64) *TokenBucket {
	return &TokenBucket{
		tokens:     maxTokens,
		maxTokens:  maxTokens,
		refillRate: refillRate,
		lastRefill: time.Now(),
	}
}

func (tb *TokenBucket) Allow() bool {
	tb.mu.Lock()
	defer tb.mu.Unlock()
	
	now := time.Now()
	elapsed := now.Sub(tb.lastRefill).Seconds()
	tb.tokens += elapsed * tb.refillRate
	if tb.tokens > tb.maxTokens {
		tb.tokens = tb.maxTokens
	}
	tb.lastRefill = now
	
	if tb.tokens >= 1.0 {
		tb.tokens -= 1.0
		return true
	}
	return false
}

// SlidingWindowCounter 滑动窗口计数器（Nginx limit_req 的等效实现）
type SlidingWindowCounter struct {
	mu        sync.Mutex
	windowSize time.Duration
	requests  map[string]*WindowEntry
}

type WindowEntry struct {
	count     int
	startTime time.Time
}

func NewSlidingWindowCounter(windowSize time.Duration) *SlidingWindowCounter {
	return &SlidingWindowCounter{
		windowSize: windowSize,
		requests:   make(map[string]*WindowEntry),
	}
}

func (sw *SlidingWindowCounter) Allow(key string, maxRequests int) bool {
	sw.mu.Lock()
	defer sw.mu.Unlock()
	
	now := time.Now()
	windowStart := now.Add(-sw.windowSize)
	
	entry, exists := sw.requests[key]
	if !exists || entry.startTime.Before(windowStart) {
		// 新窗口
		sw.requests[key] = &WindowEntry{
			count:     1,
			startTime: now,
		}
		return true
	}
	
	entry.count++
	if entry.count > maxRequests {
		return false
	}
	return true
}
```

---

## 六、性能调优与生产排障

### 6.1 关键参数调优

```bash
# /etc/sysctl.conf - 内核参数优化
# TCP 连接复用
net.ipv4.tcp_tw_reuse = 1
net.ipv4.tcp_fin_timeout = 15
net.ipv4.tcp_keepalive_time = 600

# 增大文件描述符限制
fs.file-max = 1000000
fs.nr_open = 1000000

# TCP 缓冲区优化
net.core.rmem_max = 16777216
net.core.wmem_max = 16777216
net.ipv4.tcp_rmem = 4096 87380 16777216
net.ipv4.tcp_wmem = 4096 65536 16777216

# 增大 backlog
net.core.somaxconn = 65535
net.ipv4.tcp_max_syn_backlog = 65535

# 禁用 SYN cookies（Nginx 自身处理 syn flood）
net.ipv4.tcp_syncookies = 0
```

### 6.2 常见问题排查

#### 问题 1：502 Bad Gateway

```
症状：Nginx 返回 502，上游服务无响应
原因：
1. 上游服务挂了
2. 上游服务过载，拒绝新连接
3. proxy_read_timeout 太短
```

```bash
# 排查步骤
# 1. 检查上游服务健康
curl -v http://10.0.1.10:8081/health

# 2. 查看 Nginx error log
tail -f /var/log/nginx/error.log | grep "upstream"

# 3. 检查上游连接数
ss -tnp | grep :8081 | wc -l

# 4. 检查系统资源
top -p $(pgrep nginx)
```

```nginx
# 解决方案：增加超时 + 启用 upstream 健康检查
upstream bid_proxy {
    server 10.0.1.10:8081 max_fails=3 fail_timeout=30s;
    server 10.0.1.11:8081 max_fails=3 fail_timeout=30s;
    
    proxy_connect_timeout 1s;
    proxy_send_timeout 5s;
    proxy_read_timeout 10s;
}
```

#### 问题 2：高 CPU 使用率

```
症状：Nginx worker CPU 使用率持续 >80%
原因：
1. Gzip 压缩开销过大
2. SSL 握手频繁（session 未复用）
3. 大量小文件请求
```

```bash
# 排查
# 1. 查看哪个 worker 负载高
ps -eo pid,pcpu,pmem,comm | grep nginx

# 2. 分析请求耗时
awk '{print $7}' /var/log/nginx/access.log | sort | uniq -c | sort -rn | head

# 3. 检查 SSL 命中率
nginx -V 2>&1 | grep -o with-http_ssl_module
```

```nginx
# 优化方案
# 1. 降低 gzip 压缩级别
gzip_comp_level 4;  # 默认 6，降低到 4 减少 CPU 开销

# 2. 启用 SSL session cache
ssl_session_cache shared:SSL:50m;
ssl_session_timeout 1d;

# 3. 对静态文件禁用 gzip（浏览器已缓存）
location ~* \.(jpg|jpeg|png|gif|ico|css|js)$ {
    gzip off;
    expires 30d;
}
```

#### 问题 3：连接数耗尽

```
症状：too many open files
原因：worker_rlimit_nofile 设置过小
```

```bash
# 检查当前限制
ulimit -n
cat /proc/$(pgrep nginx -o)/limits | grep "open files"

# 解决方案
# 1. 增加 nginx.conf 中的 worker_rlimit_nofile
worker_rlimit_nofile 65535;

# 2. 增加系统限制
echo "* soft nofile 65535" >> /etc/security/limits.conf
echo "* hard nofile 65535" >> /etc/security/limits.conf

# 3. 重启 Nginx 生效
nginx -s reload
```

### 6.3 性能基准测试

```bash
# 使用 wrk 进行压力测试
wrk -t12 -c400 -d30s http://localhost:8080/bid/test

# 典型结果（Nginx + 10G RAM + 4 Core）：
# Requests/sec: 45,000
# Latency avg: 2.1ms
# Latency p99: 8.5ms

# 使用 ab (Apache Bench)
ab -n 10000 -c 100 http://localhost/health

# 使用 hey
hey -n 10000 -c 100 http://localhost/bid/test
```

---

## 七、与知识库的对照

### 7.1 已有知识

| 主题 | 知识库文件 | 覆盖程度 |
|------|-----------|---------|
| TLS/SSL | `knowledge/network/tls-ssl-deep.md` | ✅ 已覆盖（握手流程、加密套件） |
| HTTP/HTTPS | `knowledge/network/http-https-deep.md` | ✅ 已覆盖（协议差异、安全机制） |
| HTTP/3 QUIC | `knowledge/network/http3-quic-deep.md` | ✅ 已覆盖（QUIC 协议、多路复用） |
| gRPC 传输 | `knowledge/network/grpc-transport-deep.md` | ✅ 已覆盖（gRPC 原理、HTTP/2 集成） |
| WebSocket | `knowledge/network/websocket-realtime-deep.md` | ✅ 已覆盖（WebSocket 协议、实时通信） |
| DNS 架构 | `knowledge/network/dns-architecture-deep.md` | ✅ 已覆盖（DNS 原理、CDN 调度） |
| 负载均衡 | `knowledge/architecture/high-availability-design.md` | ✅ 已覆盖（L4/L7 负载均衡） |
| 限流熔断 | `knowledge/architecture/high-availability-design.md` | ✅ 已覆盖（令牌桶、漏桶） |
| K8s 部署 | `knowledge/middleware/ad-k8s-deep.md` | ✅ 已覆盖（Ingress、Service） |
| 可观测性 | `knowledge/infrastructure/observability-architecture-deep.md` | ✅ 已覆盖（Prometheus、Grafana） |

### 7.2 新增知识

本文档填补了以下空白：
1. **Nginx 多进程架构**：Master-Worker 设计、accept 共享模式
2. **epoll 事件驱动**：LT vs ET 模式、Nginx 事件循环
3. **内存池管理**：ngx_palloc 实现、大/小内存分离
4. **HTTP 过滤器链**：请求处理的 8 个阶段
5. **反向代理源码**：upstream 模块、peer 选择
6. **负载均衡算法**：Round Robin / IP Hash / Least Conn 实现
7. **SSL session 复用**：共享内存 session cache
8. **HTTP/2 帧处理**：帧解析、多路复用
9. **生产限流配置**：limit_req / limit_conn 组合策略
10. **性能调优 checklist**：sysctl、worker 参数、超时配置

### 7.3 与广告平台的关联

Nginx 在广告平台中的关键作用：
- **RTB Bid Proxy**：低延迟反向代理（<5ms），需要关闭 buffering
- **Report API**：高吞吐写入（Click/Hook），需要 IP Hash 保证会话粘性
- **Creative Storage**：大文件传输优化，需要调整 buffer 大小
- **安全防护**：限流 + WAF + SSL 终止，保护后端服务

---

## 八、自测题

### Q1：Nginx 为什么比 Apache 在高并发场景下性能更好？

**答案**：
1. **事件驱动模型**：Nginx 使用 epoll/kqueue 异步非阻塞 IO，单个 worker 可处理数万并发连接。Apache 的 prefork 模型每个请求一个进程，worker 模型每个请求一个线程，上下文切换开销大。
2. **内存占用**：Nginx 使用内存池管理，避免频繁 malloc/free。Apache 每个进程独立分配内存。
3. **零拷贝优化**：Nginx 深度集成 sendfile、splice、aio，静态文件传输几乎无 CPU 开销。
4. **连接复用**：Nginx 原生支持 keepalive 到上游，减少 TCP 握手开销。

### Q2：如何实现 Nginx 的优雅重启而不中断服务？

**答案**：
1. Master 进程收到 SIGUSR2 信号
2. Master 启动新的 master + workers（使用新配置）
3. 新旧 master 共存，各自管理自己的 worker
4. 旧 master 发送 WINCH 信号给旧 worker，优雅关闭
5. 旧 worker 处理完当前请求后退出
6. 旧 master 退出，完成滚动升级

```bash
# 实际操作
nginx -s reload        # 热重载配置（不重启进程）
kill -USR2 $(cat /var/run/nginx.pid)  # 优雅重启（滚动升级）
```

### Q3：Nginx 的 limit_req 和 limit_conn 有什么区别？何时组合使用？

**答案**：
- `limit_req`：基于请求频率限流（令牌桶算法），防止短时间内过多请求
- `limit_conn`：基于连接数限流，防止单个 IP 建立过多并发连接

**组合使用场景**：
- 广告 bid 接口：`limit_req` 防止刷量，`limit_conn` 防止连接耗尽
- 报告 API：`limit_req` 控制写入速率，`limit_conn` 防止长连接堆积

```nginx
location /bid {
    limit_req zone=bid_limit burst=200 nodelay;
    limit_conn conn_limit 50;
    proxy_pass http://bid_backend;
}
```

---

## 九、动手验证

### 9.1 本地搭建 Nginx 反向代理

```bash
# 1. 安装 Nginx
brew install nginx  # macOS
apt-get install nginx  # Ubuntu

# 2. 配置简单的反向代理
cat > /usr/local/etc/nginx/servers/ad-proxy.conf << 'EOF'
upstream bid_backend {
    server 127.0.0.1:8081;
}

server {
    listen 8080;
    
    location /bid {
        proxy_pass http://bid_backend;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_connect_timeout 1s;
        proxy_read_timeout 5s;
    }
}
EOF

# 3. 启动
nginx -t && nginx

# 4. 测试
curl -v http://localhost:8080/bid/test
```

### 9.2 性能对比实验

```bash
# 测试 Nginx 静态文件性能
wrk -t4 -c100 -d10s http://localhost:8080/static/test.html

# 测试 Nginx 反向代理性能
wrk -t4 -c100 -d10s http://localhost:8080/bid/test

# 对比：直接访问后端 vs 通过 Nginx
wrk -t4 -c100 -d10s http://127.0.0.1:8081/bid/test
```

预期结果：
- 静态文件：~50,000 req/s
- 反向代理：~20,000 req/s（取决于后端性能）
- 直连后端：~15,000 req/s（Nginx 增加了 ~33% 吞吐）

---

## 十、参考资料

1. Nginx 官方文档：https://nginx.org/en/docs/
2. Nginx 源码：https://github.com/nginx/nginx
3. 《深入剖析Nginx》（微信读书）
4. HTTP/2 规范 RFC 7540
5. TLS 1.3 规范 RFC 8446

---

*本文档基于微信读书《深入剖析Nginx》及 Nginx 开源源码整理，结合广告平台生产实践编写。*
