# Nginx源码深度实现 - 资深专家

## 一、Event Model

```c
// src/event/ngx_event.h
typedef struct {
    ngx_event_actions_t   actions;
    
    // 事件处理函数
    ngx_int_t (*init)(ngx_cycle_t *cycle, ngx_msec_t timer);
    void        (*done)(ngx_cycle_t *cycle);
    ngx_int_t (*add)(ngx_event_t *ev, ngx_int_t event, ngx_uint_t flags);
    ngx_int_t (*del)(ngx_event_t *ev, ngx_int_t event, ngx_uint_t flags);
    ngx_int_t (*enable)(ngx_event_t *ev, ngx_int_t event, ngx_uint_t flags);
    ngx_int_t (*disable)(ngx_event_t *ev, ngx_int_t event, ngx_uint_t flags);
    ngx_int_t (*add_conn)(ngx_connection_t *c);
    ngx_int_t (*delete_conn)(ngx_connection_t *c);
    ngx_int_t (*send)(ngx_connection_t *c, u_char *buf, size_t size);
    ngx_int_t (*recv)(ngx_connection_t *c, u_char *buf, size_t size);
    ngx_int_t (*send_file)(ngx_connection_t *c, ngx_buf_t *file,
                           off_t offset, size_t size);
    ngx_int_t (*accept_connection)(ngx_event_t *rev);
} ngx_event_module_ctx_t;
```

## 二、Epoll实现

```c
// src/event/modules/ngx_epoll_module.c
static ngx_int_t
ngx_epoll_init(ngx_cycle_t *cycle, ngx_msec_t timer)
{
    // 创建epoll实例
    deg->ep = epoll_create(1024);
    if (deg->ep == -1) {
        return NGX_ERROR;
    }
    
    deg->events = ngx_alloc(sizeof(struct epoll_event) * ngx_event_max,
                            cycle->log);
    if (deg->events == NULL) {
        return NGX_ERROR;
    }
    
    return NGX_OK;
}

static ngx_int_t
ngx_epoll_add_event(ngx_event_t *ev, ngx_int_t event, ngx_uint_t flags)
{
    int                action = EPOLL_CTL_ADD;
    struct epoll_event  ee;
    
    ngx_memzero(&ee, sizeof(struct epoll_event));
    
    if (event == NGX_READ_EVENT) {
        ee.events = EPOLLIN;
        if (flags & NGX_CLEAR_EVENT) {
            ee.events |= EPOLLRDHUP;
        }
    } else {
        ee.events = EPOLLOUT;
    }
    
    ee.data.ptr = (void *) ((uintptr_t) ev | ev->instance);
    
    // 调用epoll_ctl
    if (epoll_ctl(deg->ep, action, ev->fd, &ee) == -1) {
        return NGX_ERROR;
    }
    
    return NGX_OK;
}
```

## 三、请求处理流程

```c
// src/http/ngx_http_request.c
void
ngx_http_init_connection(ngx_connection_t *c)
{
    // 1. 分配请求结构
    c->data = ngx_pcalloc(c->pool, sizeof(ngx_http_connection_t));
    if (c->data == NULL) {
        return;
    }
    
    hscf = ngx_http_get_module_loc_conf(c->http_connection->srv_conf,
                                        ngx_http_core_module);
    
    // 2. 设置读事件回调
    rev = c->read;
    rev->handler = ngx_http_process_request_line;
    ngx_add_timer(rev, hscf->client_body_timeout);
    ngx_enable_accept_events(c->loop);
    
    // 3. 开始处理请求
    ngx_process_request(c);
}

static void
ngx_http_process_request(ngx_connection_t *c)
{
    // 解析请求头
    ngx_http_read_request_header(r);
    
    // 处理请求
    ngx_http_handler(r);
}
```

## 四、面试高频题

### Q1: Nginx为什么快？

```
A:
1. 异步非阻塞IO（epoll）
2. 零拷贝（sendfile）
3. 内存映射（mmap）
4. 事件驱动架构
5. 内核态优化
```

### Q2: 如何实现反向代理？

```nginx
location /api/ {
    proxy_pass http://backend;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
}
```

## 五、自测题

1. Nginx的事件模型是什么？
2. 如何实现负载均衡？
3. 如何优化Nginx性能？

---

## 参考文档

- [Nginx源码](https://github.com/nginx/nginx)
- [Nginx官方文档](https://nginx.org/en/docs/)
