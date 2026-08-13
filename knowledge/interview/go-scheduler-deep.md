# Go Scheduler深入 - 资深专家深度实现

## 一、M/P/G模型

### 1.1 核心数据结构

```go
// src/runtime/proc.go
type m struct {
    g0        *g         // m的goroutine（系统栈）
    p         p          // 绑定的p
    nextp     p          // 下一个p
    id        int32      // m的ID
    sched     gsched     // goroutine调度状态
    stopwait  int32      // 停止等待计数
    sysemask  sigset     // 系统信号掩码
}

type p struct {
    id          int32      // p的ID
    status      uint32     // p的状态
    link        p          // 链表指针
    schedtick   uint32     // 调度计数器
    syscalltick uint32     // 系统调用计数器
    runqhead    guintptr   // 运行队列头
    runqtail    guintptr   // 运行队列尾
    runqlen     int32      // 运行队列长度
    
    // 本地工作队列
    wbuf        *workbuf   // 工作缓冲区
    wbH, wbT    uint32     // 工作缓冲区头尾
    
    // GC相关
    gcBgMarkWorker g      // 后台标记worker
    gcw          gcWork     // GC工作队列
}

type g struct {
    stack       stack      // 栈信息
    stackguard0 uintptr   // 栈保护（防溢出）
    stackguard1 uintptr   // 栈保护（红 zone）
    pcsp        uintptr
    pcfile      uintptr
    lr          uintptr
    
    param       unsafe.P   // 参数
    waitreason  waitReason // 等待原因
    
    sched       g_sched    // 调度状态
    schedlink   guintptr   // 调度链表指针
    
    atomicstatus uint32    // 原子状态
    gopc         uintptr   // goroutine创建点
    startpc      uintptr   // 起始PC
}
```

### 1.2 状态转换图

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       Goroutine状态转换                                   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   GRunnable ──► running ──► running + waiting                          │
│       ↑            │                    │                               │
│       │            │                    ▼                               │
│       │      ┌─────┴──────┐          ┌──────────┐                       │
│       │      │  blocked   │◄─────────│ waiting  │                       │
│       │      └─────┬──────┘          └──────────┘                       │
│       │            │                                                     │
│       │            ▼                                                     │
│       │      ┌──────────┐                                                │
│       │      │  dead    │                                                │
│       │      └──────────┘                                                │
│       │                                                                 │
│       └─────────────────────────────────────────────────────────────── │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、调度算法实现

### 2.1 工作窃取算法

```go
// src/runtime/proc.go
func execute(gp *g, inheritTime bool) {
    // 设置当前goroutine
    setg(gp)
    
    // 执行goroutine
    goschedImpl(gp)
    
    // 检查是否需要抢占
    if gp.preempt {
        preemptOne(gp)
    }
}

// 工作窃取
func findrunnable() (gp *g, inheritTime bool) {
    // 1. 尝试从本地队列获取
    if gp := runqget(curp); gp != nil {
        return gp, true
    }
    
    // 2. 尝试从全局队列获取
    if gp := runqgrab(); gp != nil {
        return gp, true
    }
    
    // 3. 工作窃取（从其他P偷取）
    if gp := netpoll(false); gp != nil {
        return gp, true
    }
    
    // 4. 尝试从其他P窃取
    if gp := stealWork(); gp != nil {
        return gp, true
    }
    
    // 5. 阻塞等待
    stopm()
    return nil, false
}

// 窃取工作
func stealWork() *g {
    // 随机选择一个P
    for i := 0; i < 4; i++ {
        dest := pickRandomP()
        if dest == nil {
            continue
        }
        
        // 尝试窃取一半的工作
        n := int32(0)
        for s := uint(0); s < 8; s++ {
            n++
            if runqsteal(curp, dest, n) {
                break
            }
        }
        
        if n > 0 {
            return runqget(curp)
        }
    }
    return nil
}
```

### 2.2 抢占式调度

```go
// src/runtime/preempt.go
func preemptOne(gp *g) {
    // 设置抢占标志
    gp.stackguard0 = stackPreempt
    
    // 发送信号
    sigsend(gp.sig, _SIGURG)
}

// 栈保护
func checkTimeout() {
    // 检查栈是否溢出
    if gp.stack.lo > gp.stackguard0 {
        growstack(gp, 0)
    }
    
    // 检查是否需要主动调度
    if atomic.Load(&sched.nmidle) > 0 {
        osyield()
    }
}
```

## 三、网络轮询器

### 3.1 epoll实现

```go
// src/runtime/netpoll_epoll.go
type netpoller struct {
    fd     int          // epoll文件描述符
    lock   mutex        // 锁
    events netpollEvent // 事件列表
}

func netpollinit() {
    // 创建epoll实例
    fd, err := epollCreate1(EPOLL_CLOEXEC)
    if err != nil {
        throw("netpollinit: " + err.Error())
    }
    
    netpollers[0] = &netpoller{
        fd: fd,
    }
}

func netpoll(block bool) *g {
    // 等待事件
    var events [128]epollevent
    n := epollWait(netpollers[0].fd, &events[0], int32(len(events)), waitms)
    
    if n <= 0 {
        return nil
    }
    
    // 处理事件
    var ready guintptr
    for i := int32(0); i < n; i++ {
        ev := &events[i]
        
        // 读取事件
        if ev.events&EPOLLIN != 0 {
            if pd, ok := netpollDrop(ev.data); ok {
                ready.push(pd.g)
            }
        }
        
        // 写入事件
        if ev.events&EPOLLOUT != 0 {
            if pd, ok := netpollDrop(ev.data); ok {
                ready.push(pd.g)
            }
        }
    }
    
    // 返回第一个就绪的goroutine
    if !ready.empty() {
        return ready.pop()
    }
    
    return nil
}
```

### 3.2 IO多路复用

```go
// src/runtime/netpoll.go
type netpollData struct {
    g    *g        // 关联的goroutine
    fd   int       // 文件描述符
    mode int16     // 读/写模式
}

func netpolldo(fd int, mode int16, pd *netpollData) {
    // 注册到epoll
    var ev epollevent
    ev.events = 0
    if mode&'r' != 0 {
        ev.events |= EPOLLIN
    }
    if mode&'w' != 0 {
        ev.events |= EPOLLOUT
    }
    
    // 设置数据
    ev.data = uintptr(unsafe.Pointer(pd))
    
    // 添加到epoll
    epollAdd(netpollers[0].fd, fd, &ev)
}

func netpollBreak() {
    // 唤醒等待的goroutine
    for _, pd := range netpollers[0].breakCh {
        wakeg(pd.g)
    }
}
```

## 四、并发控制

### 4.1 锁机制

```go
// src/runtime/lock_sema.go
type semacquire struct {
    l       *mutex
    async   bool
    relink  bool
}

func semacquire(l *mutex) {
    // 尝试获取锁
    if atomic.Cas(&l.state, 0, 1) {
        return
    }
    
    // 自旋等待
    for !futexaddr(&l.state) {
        if atomic.Cas(&l.state, 0, 1) {
            return
        }
        osyield()
    }
    
    // 阻塞等待
    futex(&l.wait.lock, _FUTEX_WAIT, 0, nil, nil, 0)
}

func semrelease(l *mutex) {
    // 释放锁
    atomic.Store(&l.state, 0)
    
    // 唤醒等待者
    futex(&l.wait.lock, _FUTEX_WAKE, 1, nil, nil, 0)
}
```

### 4.2 条件变量

```go
// src/runtime/sema.go
type cond struct {
    lock *mutex
    sem  uint32
}

func (c *cond) Wait() {
    // 释放锁并等待
    semrelease(c.lock)
    futex(&c.sem, _FUTEX_WAIT, 0, nil, nil, 0)
    semacquire(c.lock)
}

func (c *cond) Signal() {
    // 唤醒一个等待者
    futex(&c.sem, _FUTEX_WAKE, 1, nil, nil, 0)
}

func (c *cond) Broadcast() {
    // 唤醒所有等待者
    futex(&c.sem, _FUTEX_WAKE, 1<<30, nil, nil, 0)
}
```

## 五、性能优化

### 5.1 锁优化策略

```go
// 自适应自旋
func adaptiveSpin() {
    spins := 0
    for spins < maxSpins {
        if atomic.Cas(&l.state, 0, 1) {
            return
        }
        // 指数退避
        for i := 0; i < (1 << uint(spins)); i++ {
            runtime·yield()
        }
        spins++
    }
}

// 锁分片
type shardedLock struct {
    locks [N]mutex
}

func (s *shardedLock) lock(key uintptr) {
    idx := key % N
    semacquire(&s.locks[idx])
}

func (s *shardedLock) unlock(key uintptr) {
    idx := key % N
    semrelease(&s.locks[idx])
}
```

### 5.2 内存屏障

```go
// 内存序
const (
    MemOrderRelaxed = iota
    MemOrderAcquire
    MemOrderRelease
    MemOrderAcqRel
)

// 内存屏障实现
func MemoryBarrier(order MemOrder) {
    switch order {
    case MemOrderAcquire:
        // LoadLoad + LoadStore
        asm("lfence")
    case MemOrderRelease:
        // StoreStore + StoreLoad
        asm("sfence")
    case MemOrderAcqRel:
        // 全屏障
        asm("mfence")
    }
}
```

## 六、面试高频题

### Q1: Go调度器如何实现？

```
A:
1. M:P:G三元模型
2. 工作窃取算法
3. 网络轮询器
4. 抢占式调度
```

### Q2: 如何解决GOMAXPROCS设置问题？

```
A:
1. 默认值为CPU核数
2. IO密集型可以适当增加
3. CPU密集型不建议超过核数
4. 通过runtime.GOMAXPROCS设置
```

### Q3: goroutine如何避免栈溢出？

```
A:
1. 栈自动扩容
2. 栈分裂技术
3. 栈跟踪保护
4. 红zone检查
```

## 七、自测题

1. 解释M:P:G模型
2. 工作窃取算法如何工作？
3. 如何实现goroutine抢占？

---

## 参考文档

- [Go调度器源码](https://github.com/golang/go/blob/master/src/runtime/proc.go)
- [Go调度器设计](https://go.dev/blog/Go-scheduler)
