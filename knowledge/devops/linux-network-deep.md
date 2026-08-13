# Linux内核网络栈 - 资深专家深度实现

## 一、网络协议栈架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       Linux网络协议栈                                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   Application Layer                                                      │
│   ├── TCP/UDP Socket API                                                 │
│   └── epoll/kqueue/eventfd                                               │
│                │                                                        │
│   Transport Layer                                                        │
│   ├── TCP: 连接管理、拥塞控制、流量控制                                   │
│   └── UDP: 无连接传输                                                    │
│                │                                                        │
│   Network Layer                                                           │
│   ├── IP: 路由、分片、TTL                                                │
│   ├── ICMP: 错误报告                                                     │
│   └── Netfilter: iptables/nftables                                       │
│                │                                                        │
│   Data Link Layer                                                         │
│   ├── Ethernet: MAC地址、帧格式                                          │
│   └── Driver: 硬件抽象                                                   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、Socket实现

```c
// 文件: net/socket.c
struct socket {
    socket_state        state;
    unsigned long       flags;
    struct proto_ops    *ops;
    struct file         *file;
    struct sock         *sk;
};

struct sock {
    struct sock_common  __sk_common;
    struct sk_buff_head sk_receive_queue;
    struct sk_buff_head sk_write_queue;
    struct proto        *prot;
    void                *sk_protinfo;
    // ...
};
```

## 三、epoll实现

```c
// 文件: fs/eventpoll.c
struct epitem {
    struct rb_node    rbn;
    struct list_head  rdllink;
    struct epoll_filefd ffd;
    struct eventpoll    *ep;
    struct epoll_event  event;
};

struct eventpoll {
    spinlock_t          lock;
    struct mutex        mtx;
    wait_queue_head_t   wait;
    struct list_head    ready_list;
    struct rb_root      rbr;
};
```

## 四、拥塞控制

```c
// TCP拥塞控制算法
struct tcp_congestion_op {
    struct list_head    list;
    char                name[TCP_CA_NAME_MAX];
    int                 (*init)(struct sock *sk);
    void                (*release)(struct sock *sk);
    void                (*ssthresh)(struct sock *sk);
    u32                 (*undo_cwnd)(struct sock *sk);
    void                (*pkts_acked)(struct sock *sk, u32 acked, s32 rtt_us);
    void                (*cong_avoid)(struct sock *sk, u32 ack, u32 acked);
    void                (*set_state)(struct sock *sk, u8 new_state);
    // ...
};
```

## 五、面试高频题

### Q1: TCP三次握手过程？

```
A:
1. Client → SYN → Server
2. Server → SYN+ACK → Client
3. Client → ACK → Server
```

### Q2: epoll与select的区别？

```
A:
• select: O(n)扫描，最大1024
• epoll: O(1)回调，支持百万连接
```

## 六、自测题

1. 解释epoll的工作原理
2. 如何实现零拷贝？
3. 如何优化网络性能？

---

## 参考文档

- [Linux内核源码](https://github.com/torvalds/linux)
- [TCP/IP详解](https://en.wikipedia.org/wiki/TCP/IP)
