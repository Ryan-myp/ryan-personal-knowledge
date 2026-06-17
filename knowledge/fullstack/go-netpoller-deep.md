# Go 网络编程深度：Netpoller 源码（epoll/kqueue 封装）

> 从 syscall.EpollWait 到 netpoller 完整源码解析，理解 Go 如何把 1000 万并发变成现实

---

## 第一部分：为什么 Go 需要 Netpoller？

### 传统 I/O 模型的问题

```
传统模型（每连接一线程）：
客户端 → accept() → 创建线程 → pthread_create(2MB stack) → 阻塞 read()
问题：
1. 线程栈 2MB，100 万连接 = 2TB 内存 ❌
2. 线程切换开销大（内核态↔用户态）
3. 上下文切换：10 万线程 ≈ 50% CPU 浪费

Go 模型（协程 + Netpoller）：
客户端 → accept() → goroutine → netpoller(epoll) 注册 fd → yield
优势：
1. 协程栈初始 2KB，100 万连接 ≈ 2GB ✅
2. 无阻塞时 goroutine 休眠，不占 CPU
3. epoll 单线程管理百万 fd
```

### Netpoller 架构总览

```
                    ┌──────────────────────────────────┐
                    │         netpoller (epoll)         │
                    │                                   │
fd ──► epoll_ctl ──► ready list ──► netpollBreak ──►  │
                    │                                   │
                    └──────────────────────────────────┘
                              ▲
                              │ netpoll(0) 非阻塞检查
                              │ netpoll(>0) 阻塞等待
                              │
                    ┌─────────┴─────────┐
                    │  goroutine 调度器   │
                    │  GMP Scheduler    │
                    │                   │
                    │  gopark() ──► 休眠  │
                    │  goready() ──► 唤醒  │
                    └───────────────────┘
```

---

## 第二部分：源码逐行解析

### 1. netpoller 初始化（runtime/netpoll_epoll.go）

```go
// Go 源码：runtime/netpoll_epoll.go
// netpollinit — 创建 epoll 实例

func netpollinit() {
    // 1. 调用 syscall.EpollCreate1 创建 epoll 实例
    // EPOLL_CLOEXEC: 确保 fork 后子进程关闭 epoll fd
    netpollfd = syscall.EpollCreate1(syscall.EPOLL_CLOEXEC)
    if netpollfd < 0 {
        throw("netpoll: epoll create failed")
    }
    
    // 2. 创建 netpollBreak pipe（用于唤醒 netpoll 循环）
    // 这是一个 self-pipe trick：向 pipe 写数据触发 netpoll 退出阻塞
    var fds [2]int
    if err := syscall.Pipe2(fds[:], syscall.O_NONBLOCK|syscall.O_CLOEXEC); err != nil {
        close(netpollfd)
        throw("netpoll: pipe create failed")
    }
    
    // 3. 注册 break pipe 的 read 事件到 epoll
    // EPOLLIN: 可读事件（有数据写入 pipe 时触发）
    ev := epollEvent{
        Events: syscall.EPOLLIN,
        Fd:     int32(fds[0]), // read end
    }
    if err := syscall.EpollCtl(netpollfd, syscall.EPOLL_CTL_ADD, fds[0], &ev); err != nil {
        close(fds[0])
        close(fds[1])
        close(netpollfd)
        throw("netpoll: epoll ctl failed")
    }
    
    // 4. 保存 break pipe 的 fd
    breakR = fds[0]
    breakW = fds[1]
    
    // 5. 启动 netpoll 后台 goroutine
    go netpollWake()
}
```

**关键点**：
- **EPOLL_CLOEXEC**：防止文件描述符泄漏
- **Self-Pipe Trick**：向 pipe 写 1 字节触发 epoll 返回，用于优雅退出 netpoll 循环
- **后台 goroutine**：`netpollWake()` 持续调用 `netpoll(0)` 检查就绪事件

### 2. 注册网络事件（netpollgoready）

```go
// Go 源码：runtime/netpoll.go
// netpollgoready — 将 fd 注册到 epoll

func netpollgoready(dp *pollDesc, mode int32, gw *g) bool {
    // 1. 构建 epoll event
    var ev epollEvent
    ev.Events = 0
    if mode&'read' != 0 {
        ev.Events |= syscall.EPOLLIN   // 可读
    }
    if mode&'write' != 0 {
        ev.Events |= syscall.EPOLLOUT  // 可写
    }
    
    // 2. 设置 epoll data 为 goroutine 指针
    // 这样 epoll_wait 返回时可以直接拿到对应的 g
    ev.Data = uintptr(unsafe.Pointer(g))
    
    // 3. 尝试 EPOLL_CTL_MOD（修改已有注册）
    err := syscall.EpollCtl(netpollfd, syscall.EPOLL_CTL_MOD, int32(dp.fd), &ev)
    if err == syscall.ENOENT {
        // 4. ENOENT: fd 未注册，改为 ADD
        err = syscall.EpollCtl(netpollfd, syscall.EPOLL_CTL_ADD, int32(dp.fd), &ev)
    }
    
    return err == nil
}
```

**关键点**：
- **EPOLL_CTL_MOD vs ADD**：优先尝试 MOD，失败说明 fd 未注册，退化为 ADD
- **epoll.data = g 指针**：epoll_wait 返回时直接拿到对应的 goroutine
- **EPOLLIN + EPOLLOUT**：同时监听读写，支持 HTTP/2 全双工

### 3. netpoll 主循环（runtime/netpoll.go）

```go
// Go 源码：runtime/netpoll.go
// netpoll — epoll 事件循环

func netpoll(block bool) *g {
    // 1. 调用 syscall.EpollWait
    var events [128]epollEvent // 批量获取最多 128 个事件
    n := syscall.EpollWait(netpollfd, events[:], netpollBlockTimeout(block))
    if n <= 0 {
        return nil
    }
    
    // 2. 遍历就绪事件
    var gp *g
    for i := int32(0); i < n; i++ {
        ev := &events[i]
        
        // 3. 特殊处理：break pipe
        if ev.Fd == breakR {
            // 消费 pipe 中的数据，避免重复触发
            var buf [16]byte
            syscall.Read(int32(breakR), buf[:])
            continue
        }
        
        // 4. 获取对应的 g 指针
        g := *(***g)(unsafe.Pointer(&ev.Data))
        if g == nil {
            continue
        }
        
        // 5. 确定事件类型
        var mode int32
        if ev.Events&(syscall.EPOLLIN|syscall.EPOLLPRI) != 0 {
            mode |= 'read'
        }
        if ev.Events&syscall.EPOLLOUT != 0 {
            mode |= 'write'
        }
        
        // 6. 检查 fd 状态
        if netpollCheck(mode, int32(ev.Fd)) {
            // 7. 添加到 ready 链表
            *gp = g
            gp = g
        }
    }
    
    // 8. 批量就绪：一次性唤醒多个 goroutine
    if gp != nil {
        for g := gp; g != nil; g = g.scheduleLink {
            netpollgoready(g, mode)
        }
    }
    
    return gp
}
```

**关键点**：
- **批量获取**：一次 epoll_wait 最多拿 128 个事件，减少系统调用
- **break pipe 处理**：消费 pipe 数据避免重复触发
- **批量唤醒**：g.scheduleLink 链表，一次性唤醒多个 goroutine

### 4. goroutine 休眠与唤醒（runtime/proc.go）

```go
// Go 源码：runtime/proc.go
// gopark — goroutine 休眠（网络 I/O 阻塞时调用）

func gopark(unlockf func(*g, unsafe.Pointer) bool, lock unsafe.Pointer, reason string, traceEv byte, traceskip int) {
    // 1. 保存当前 goroutine 状态
    gp := getg()
    gp.waitreason = reason
    gp.waitUnlockf = unlockf
    gp.waitLock = lock
    
    // 2. 调用 schedule 让出 CPU
    schedule()
    
    // 3. 被唤醒后，清除等待状态
    gp.waitreason = 0
    gp.waitUnlockf = nil
    gp.waitLock = nil
}

// goready — 将 goroutine 加入调度队列

func goready(gp *g, traceskip int) {
    // 1. 检查是否已经在 runq 中
    if gp.status == _Grunning {
        throw("goready: running g")
    }
    
    // 2. 设置状态为 runnable
    casFromGStatus(gp.status, _Gwaiting, _Grunnable)
    
    // 3. 加入 P 的 runq
    runqpush(gp)
    
    // 4. 如果 P 忙，触发 steal
    if n := runqgrab(getg().m.p.ptr()); n > 0 {
        wakeupM()
    }
}
```

**关键点**：
- **gopark**：goroutine 阻塞时调用，保存状态 + 让出 CPU
- **goready**：epoll 返回就绪事件时调用，恢复状态 + 加入 runq
- **casFromGStatus**：原子操作保证状态转换正确

---

## 第三部分：epoll 三种模式对比

### Edge Triggered（ET）vs Level Triggered（LT）

```
Level Triggered（LT，Go 默认）：
┌──────────────────────────────────────────┐
│ fd 可读 → epoll 持续返回 EPOLLIN          │
│ fd 不可读 → epoll 不再返回               │
│                                          │
│ 特点：                                    │
│ - 只要 fd 有数据，epoll 就一直通知        │
│ - 安全：不会漏事件                        │
│ - 性能：重复通知，但 Go 的 netpoller 处理  │
│   了批量唤醒，影响不大                     │
└──────────────────────────────────────────┘

Edge Triggered（ET）：
┌──────────────────────────────────────────┐
│ fd 可读 → epoll 只通知一次                │
│ fd 还有数据 → epoll 不再通知              │
│                                          │
│ 特点：                                    │
│ - 只在状态变化时通知一次                   │
│ - 性能更好（减少重复通知）                │
│ - 危险：如果一次性读完数据，后续数据会丢失  │
│ - Go 没有用 ET，因为 LT 更安全            │
└──────────────────────────────────────────┘
```

### Go 为什么不用 ET？

```go
// 如果使用 ET，需要确保一次性读完所有数据：
func readAll(fd int) ([]byte, error) {
    buf := make([]byte, 4096)
    var data []byte
    
    for {
        n, err := syscall.Read(fd, buf)
        if n > 0 {
            data = append(data, buf[:n]...)
        }
        if err == syscall.EAGAIN {
            // 没有更多数据了
            break
        }
        if err != nil {
            return data, err
        }
    }
    return data, nil
}

// Go 用 LT 的好处：即使某次没读完，epoll 还会再次通知
// 牺牲一点性能，换来极大的安全性
```

---

## 第四部分：自测题

### Q1: Go 的 netpoller 和 libuv 的 uv_poll 有什么区别？

**A**:
- **Go netpoller**：基于 epoll/kqueue，管理 goroutine 的休眠/唤醒
- **libuv uv_poll**：基于 epoll/kqueue/IOCP，管理 callback 的执行
- 核心区别：Go 是协程模型（gopark/goready），libuv 是回调模型

### Q2: netpollBreak 的作用是什么？

**A**: 
- 向 break pipe 写 1 字节，触发 epoll_wait 返回
- 用于在 netpoll 阻塞时强制唤醒它
- 典型场景：goroutine 被 kill、程序退出、定时器到期

### Q3: epoll 的 128 批量获取有什么意义？

**A**:
- 一次 syscall.EpollWait 最多拿 128 个就绪事件
- 减少系统调用次数（100 万连接不会触发 100 万次 epoll_wait）
- 配合 goroutine 批量唤醒，吞吐量极高

---

## 第五部分：生产排障

### 1. goroutine 泄漏

```go
// 症状：内存持续增长，CPU 使用率高
// 原因：goroutine 阻塞在 netpoll 上，但 fd 被关闭

// 排查：
pprof.Lookup("goroutine").WriteTo(os.Stdout, map[string]string{"state": "waiting"})

// 解决：
// 1. 确保所有 fd 正确关闭
// 2. 使用 context.WithTimeout 设置超时
// 3. 定期检查 goroutine 数量
```

### 2. epoll 文件描述符耗尽

```bash
# 检查系统限制
ulimit -n  # 默认 1024

# 修改限制
echo "* soft nofile 65535" >> /etc/security/limits.conf
echo "* hard nofile 65535" >> /etc/security/limits.conf

# 检查 Go 进程的 fd 数量
ls /proc/<pid>/fd | wc -l
```

### 3. netpoll 循环 CPU 100%

```go
// 症状：单个 goroutine 占用 100% CPU
// 原因：epoll_wait 频繁返回空事件

// 排查：
strace -p <pid> -e epoll_wait,read,write

# 解决：
# 1. 检查是否有大量短连接（建议用连接池）
# 2. 调整 netpollBlockTimeout
# 3. 优化 goroutine 调度
```
