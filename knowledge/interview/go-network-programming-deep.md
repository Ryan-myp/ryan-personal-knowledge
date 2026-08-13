# Go网络编程 - 资深专家深度实现

## 一、Netpoller架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      Go Netpoller架构                                     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐            │
│   │  netpoll     │    │  goroutine   │    │  system call │            │
│   │  (epoll/kqueue)◄─────────────────►│  (用户态)      │            │
│   └──────────────┘    └──────────────┘    └──────────────┘            │
│                                                                         │
│   实现:                                                                   │
│   • Linux:    epoll                                                    │
│   • macOS:    kqueue                                                   │
│   • Windows:  IOCP                                                     │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、epoll实现

```go
package netpoll

import (
    "syscall"
    "unsafe"
)

type Epoll struct {
    fd      int
    events  []syscall.EpollEvent
    maxfds  int
}

func NewEpoll(maxfds int) (*Epoll, error) {
    fd, err := syscall.EpollCreate1(0)
    if err != nil {
        return nil, err
    }
    
    return &Epoll{
        fd:     fd,
        events: make([]syscall.EpollEvent, maxfds),
        maxfds: maxfds,
    }, nil
}

func (e *Epoll) Add(fd int, mode int) error {
    event := syscall.EpollEvent{
        Events: uint32(mode),
        Fd:     int32(fd),
    }
    return syscall.EpollCtl(e.fd, syscall.EPOLL_CTL_ADD, fd, &event)
}

func (e *Epoll) Delete(fd int) error {
    return syscall.EpollCtl(e.fd, syscall.EPOLL_CTL_DEL, fd, nil)
}

func (e *Epoll) Wait(timeout int) (int, error) {
    n, err := syscall.EpollWait(e.fd, e.events, timeout)
    if err != nil {
        return 0, err
    }
    return n, nil
}
```

## 三、TCP连接池

```go
package pool

import (
    "sync"
    "time"
)

type ConnPool struct {
    mu         sync.Mutex
    conns      []*Conn
    maxIdle    int
    maxLifetime time.Duration
}

type Conn struct {
    net.Conn
    created    time.Time
    lastUse    time.Time
}

func (p *ConnPool) Get() (*Conn, error) {
    p.mu.Lock()
    defer p.mu.Unlock()
    
    // 复用空闲连接
    for len(p.conns) > 0 {
        conn := p.conns[len(p.conns)-1]
        p.conns = p.conns[:len(p.conns)-1]
        
        if conn.isAlive() {
            return conn, nil
        }
    }
    
    // 创建新连接
    return p.newConn()
}

func (p *ConnPool) Put(conn *Conn) {
    p.mu.Lock()
    defer p.mu.Unlock()
    
    if len(p.conns) < p.maxIdle && conn.isAlive() {
        conn.lastUse = time.Now()
        p.conns = append(p.conns, conn)
    }
}

func (c *Conn) isAlive() bool {
    return time.Since(c.created) < c.pool.maxLifetime
}
```

## 四、面试高频题

### Q1: Go的epoll和select有什么区别？

```
A:
• select: O(n)复杂度，有限数量
• epoll: O(1)复杂度，无限连接
• Go使用epoll/kqueue实现高性能网络
```

### Q2: 如何实现一个高性能的HTTP Server？

```
A:
1. 连接池复用
2. 读写分离
3. 零拷贝
4. 批量处理
```

## 五、自测题

1. Go的Netpoller如何工作？
2. 如何实现连接池？
3. 如何优化网络IO性能？

---

## 参考文档

- [Go源码](https://github.com/golang/go/tree/master/src/net)
- [Linux epoll文档](https://man7.org/linux/man-pages/man7/epoll.7.html)
