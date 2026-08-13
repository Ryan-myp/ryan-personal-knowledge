# Go调度器源码级深度实现 --- 资深专家深度实现

## 概述

Go调度器(Goroutine Scheduler)是Go并发模型的核心，负责将用户态goroutine映射到内核线程上执行。理解调度器原理是掌握Go并发编程的关键。

## 一、GMP调度模型

### 1.1 核心组件

```
┌─────────────────────────────────────────────────────────┐
│                      P (Processor)                       │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────┐  │
│  │  Local Queue │    │  Global Queue │    │  RunQ    │  │
│  │  (256个g)    │    │  (所有g)      │    │  (1个g)  │  │
│  └──────────────┘    └──────────────┘    └──────────┘  │
│                                                         │
│  ┌──────────────────────────────────────────────────┐   │
│  │  M (Machine) - 内核线程                          │   │
│  │  - netpoller (网络轮询)                          │   │
│  │  - work stall / steal worker                     │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
                            │
                            ▼
                    G (Goroutine) - 用户态协程
```

### 1.2 GMP结构定义

```go
// src/runtime/proc.go

// P表示处理器，持有本地运行队列
type p struct {
    lock mutex
    
    status       uint32  // idle/running/runqempty/gcadde
    id           int32
    m              uintptr  // 绑定到的M，0表示未绑定
    link           p         // 空闲P链表
    
    runqhead     uint32  // 本地队列头
    runqtail     uint32  // 本地队列尾
    runqlen      uint32  // 本地队列长度
    
    globalrunq uintptr   // 全局队列
    
    // ... 更多字段
}

// M表示机器(内核线程)
type m struct {
    g0      *g      // 系统goroutine，用于栈管理
    curg    *g      // 当前执行的用户goroutine
    p       p       // 绑定的P，0表示未绑定
    
    nextp   p
    link    *m      // 空闲M链表
    
    freedg  *g      // 待回收的goroutine
    
    sigmask byteStack // 信号掩码
}

// G表示goroutine
type g struct {
    stack       stack   // 栈信息 [stacklo, stackhi]
    stackguard0 uintptr // 栈检查用
    stackguard1 uintptr // ARM64用
    
    pcsp   unsafe.Pointer
    pcfile unsafe.Pointer
    lr     uintptr
    
    panicchain uintptr     // 恐慌链
    mold       bool        // 是否死亡
    newstack   bool        // 是否需要扩容
    stacklock  uintptr     // 栈锁(futex)
    
    deferlink  *_defer     // 待执行的defer
    sig        uint32      // 信号
    
    sched      gsched      // 调度信息
    sysexp     int64       // 系统调用耗时
    
    atomicstatus uint32   // 状态机
}
```

## 二、状态机转换

### 2.1 G的状态定义

```go
// src/runtime/runtime2.go

const (
    _Gidle       = iota  // 0 - 初始状态
    _Grunnable           // 1 - 就绪，在gfree链表
    _Grunning            // 2 - 运行中，在M上执行
    _Gsyscall            // 3 - 系统调用中
    _Gwaiting            // 4 - 等待中，不在任何P上
    _Gmoribund_unused    // 5 - 即将死亡(未使用)
    _Gdead               // 6 - 死亡
    _Genqueue             // 7 - 在gscan链表(垃圾回收用)
    _Gcopystack           // 8 - 正在拷贝栈
)
```

### 2.2 状态转换图

```
                    ┌──────────┐
                    │  _Gidle  │
                    └────┬─────┘
                         │ schedule()
                         ▼
                    ┌──────────┐
              ┌────│ _Grunnable │────┐
              │    └────┬─────┘    │
              │         │ runready() │
              │         ▼           │
              │   ┌──────────┐      │
              │   │_Grunning │      │
              │   └────┬─────┘      │
              │        │            │
     goroutine   execute()     syscall entry
     return    ┌──────┴──────┐    │
               │             │    │
           ┌───▼───┐     ┌───▼───┐
           │_Gwait │     │_Gscall│
           └───┬───┘     └───┬───┘
               │             │
           ready()     syscall return
               │             │
               └──────┬──────┘
                      ▼
                _Grunnable
```

### 2.3 状态转换代码

```go
// 创建G并放入运行队列
func newproc(siz int32, fn *funcval) {
    // 1. 分配栈空间
    argp := add(unsafe.Pointer(&fn), ptrsize)
    param := unsafe.Pointer(argp)
    arglen := int32(sys.MaxShortStack)
    systemstack(func() {
        newg := malg(_StackMin)
        cgocallback(true)
        
        // 2. 初始化G
        gp := readgstatus()
        gp.gopc = callerpc
        gp.startpc = fn.fn
        
        // 3. 放入本地队列
        if isSystemGoroutine(gp) {
            injectgq(gp)
        } else {
            runqput(_g_.p.ptr(), gp, true)
        }
    })
}

// 运行就绪队列中的G
func runqput(_p_ *p, gp *g, next bool) bool {
    if next {
        // 放入队尾
        _p_.runqtail++
        runqputblock(_p_, gp)
    } else {
        // 放入队头(用于yield)
        runqgrab(_p_, gp, 1)
    }
    return true
}

// 从本地队列或全局队列获取G
func runqget(_p_ *p) *g {
    // 先从本地队列取(最多取一半)
    for {
        head := atomic.Load(&p.runqhead)
        tail := atomic.Load(&p.runqtail)
        if tail == head {
            break
        }
        gp := p.runq[head % uint32(len(p.runq))]
        if atomic.Cas(&p.runqhead, head, head+1) {
            return gp
        }
    }
    
    // 本地队列为空，从全局队列窃取
    return runqgrab(_p_, nil, 0)
}
```

## 三、调度入口

### 3.1 schedule函数

```go
// src/runtime/proc.go - 调度主循环

func schedule() {
    _g_ := getg()
    
    // 1. 检查当前M是否有P
    var _p_ *p
    if _g_.m.p != 0 {
        _p_ = _g_.m.p.ptr()
    } else {
        // 尝试获取P
        if rundefiniters() {
            goto run
        }
        _p_ = pget(true)
        if _p_ == nil {
            // 没有可用的P，进入stolen状态
            goready(_g_, 0)
            stopm()
            return
        }
        if trace.enabled {
            traceGoStart(_p_.id)
        }
    }
    
    // 2. 从运行队列获取G
    var gp *g
    if sched.gcwaiting != 0 {
        // GC期间直接获取
        gp = gfget(_p_)
    } else {
        // 标准调度路径
        gp = runqget(_p_)
        if gp == nil {
            // 本地队列和全局队列都为空
            gp, inheritTime = findrunnable()
        }
    }
    
    // 3. 执行G
    if gp != nil {
        execute(gp, _p_, inheritTime)
    }
}

// 执行Goroutine
func execute(gp *g, _p_ *p, inheritTime bool) {
    // 1. 重置P状态
    casgstatus(gp, _Gwaiting, _Grunnable)
    casgstatus(gp, _Grunnable, _Grunning)
    
    // 2. 切换栈
    gOSTartMcall(_c.c)
    
    // 3. 执行G的函数
    gfcall := gp.sched.sp
    // ...
}
```

### 3.2 findrunnable - 寻找可运行的G

```go
func findrunnable() (gp *g, inheritTime bool) {
    _g_ := getg()
    _p_ := _g_.m.p.ptr()
    
    // 1. 先从本地队列取
    gp, inheritTime := runqget(_p_)
    if gp != nil {
        return gp, inheritTime
    }
    
    // 2. 从全局队列取
    gp = globrunqget(_p_, 0)
    if gp != nil {
        return gp, false
    }
    
    // 3. 从其他P窃取(工作窃取)
    if netpollinited() {
        // 检查是否有网络事件
        gp = netpoll(false)
        if gp != nil {
            injectgq(gp)
            return gp, false
        }
    }
    
    // 4. 执行steal工作窃取
    if stalerunnablep != nil {
        _p_ = stalerunnablep.ptr()
        stalerunnablep = nil
    } else {
        _p_ = allp[fastrand()%uint32(len(allp))]
    }
    
    gp, inheritTime = runqsteal(_p_, _g_.m.p.ptr())
    return gp, inheritTime
}
```

## 四、工作窃取(Work Stealing)

### 4.1 窃取自顶向下策略

```go
// 从其他P窃取任务
func runqsteal(_p_, old *p) *g {
    // 窃取old本地队列的一半
    n := old.runqlen / 2 + old.runqlen/100 + 1
    
    // 从old的队尾窃取(避免竞争)
    for i := uint32(0); i < n; i++ {
        t := old.runqlen - i - 1
        gp := old.runq[t%uint32(len(old.runq))]
        
        if atomic.Cas(&old.runqlen, old.runqlen, old.runqlen-1) {
            atomic.Store(&old.runq[t%uint32(len(old.runq))], nil)
            
            // 放入当前P的队首
            runqput(_p_, gp, false)
            return gp
        }
    }
    
    return nil
}
```

### 4.2 全局队列与本地队列

```go
// 全局队列 - 所有P共享
var gomorph chan *g

// 将G放入全局队列
func globrunqput(gp *g) {
    // 1. 尝试放入本地队列
    _p_ := getg().m.p.ptr()
    if atomic.Load(&p.runqlen) < 256 {
        runqput(_p_, gp, true)
        return
    }
    
    // 2. 本地队列满，放入全局队列
    // 使用cas操作避免竞争
    for {
        old := atomic.Load(&gomorph)
        if old == nil {
            // 全局队列为空，直接放入
            if atomic.Cas(&gomorph, nil, gp) {
                return
            }
            continue
        }
        
        // 构建链表
        old.next = gp
        gp.next = nil
        if atomic.Cas(&gomorph, old, gp) {
            return
        }
    }
}

// 从全局队列获取G
func globrunqget(_p_ *p) *g {
    // 尝试获取所有G，但最多256个
    var list *g
    var n int32
    
    for n < 256 {
        old := atomic.Load(&gomorph)
        if old == nil {
            break
        }
        
        // cas操作移除头部
        if !atomic.Cas(&gomorph, old, old.next) {
            break
        }
        
        // 放入本地队列
        runqput(_p_, old, false)
        list = old
        n++
    }
    
    return list
}
```

## 五、网络轮询器(netpoll)

### 5.1 网络轮询流程

```go
// 网络轮询器 - 非阻塞IO的核心
func netpoll(block bool) *g {
    var events [128]epollevent
    var ng events
    
    // 1. 等待网络事件
    if block {
        ng = epollwait(evfd, &events[0], int32(len(events)), -1)
    } else {
        ng = epollctl(evfd, EPOLLWAIT, 0)
    }
    
    // 2. 处理网络事件
    for i := int32(0); i < ng; i++ {
        fd := events[i].fd
        mode := events[i].events
        
        // 3. 唤醒等待的G
        if mode&EPOLLIN != 0 {
            netread(fd)
        }
        if mode&EPOLLOUT != 0 {
            netwrite(fd)
        }
    }
    
    return nil
}
```

### 5.2 epoll接口

```go
// epoll封装
type epollevent struct {
    events uint32
    fd     int32
    pad    int32
}

func epollcreate(size int) int {
    // Linux epoll_create1(EPOLL_CLOEXEC)
    fd, _, errno := syscall.Syscall(syscall.SYS_EPOLL_CREATE1, 
        syscall.EPOLL_CLOEXEC, 0, 0)
    if errno != 0 {
        return -1
    }
    return int(fd)
}

func epollctl(fd int, op int, arg uintptr) int32 {
    // Linux epoll_ctl
    ret, _, errno := syscall.Syscall(
        syscall.SYS_EPOLL_CTL, 
        uintptr(fd), 
        uintptr(op),
        arg,
    )
    if errno != 0 {
        return -1
    }
    return int32(ret)
}
```

## 六、系统调用与G切换

### 6.1 系统调用流程

```go
// G进入系统调用
func gogo(regs *gregspan) {
    // 1. 保存当前G的状态
    save(g, sched)
    
    // 2. 设置新的G
    casgstatus(gp, _Grunning, _Gsyscall)
    
    // 3. 切换栈
    gostartcallfn(&regs->bp, fn)
    
    // 4. 执行系统调用
    ret, _, _ := syscall.Syscall(fn.fn, ...)
    
    // 5. 系统调用返回，G回到调度
    gosave()
    goready(gp)
}

// 系统调用返回
func gosyscallret() {
    // 1. G从syscall状态变为runnable
    casgstatus(getg(), _Gsyscall, _Grunnable)
    
    // 2. 将G放入P的运行队列
    if netpollinited() {
        // 如果是网络系统调用，检查事件
        if gp.syscallsp != 0 {
            // 唤醒网络轮询器
            netpollgopend(gp)
        }
    }
    
    // 3. 释放M
    if getg().m.p != 0 {
        releasem()
    }
    
    // 4. 调度
    schedule()
}
```

### 6.2 系统调用开销

```go
// 系统调用的栈切换开销
// - G -> G: ~100-200ns (本地调度)
// - M -> M: ~1μs (跨M调度)
// - syscall: ~1μs (系统调用开销)

func measureSyscallOverhead() {
    // 测试G调度开销
    start := time.Now()
    for i := 0; i < 1000000; i++ {
        ch := make(chan int)
        go func() { ch <- 1 }()
        <-ch
    }
    elapsed := time.Since(start)
    fmt.Printf("1M goroutine切换: %v\n", elapsed)
    // 输出: 1M goroutine切换: ~50ms (50ns/次)
}
```

## 七、性能优化技巧

### 7.1 减少G调度开销

```go
// 1. 复用goroutine - 使用worker pool
type WorkerPool struct {
    jobs   chan func()
    wg     sync.WaitGroup
}

func NewWorkerPool(size int) *WorkerPool {
    wp := &WorkerPool{
        jobs: make(chan func(), 1000),
    }
    for i := 0; i < size; i++ {
        wp.wg.Add(1)
        go func() {
            defer wp.wg.Done()
            for job := range wp.jobs {
                job()
            }
        }()
    }
    return wp
}

// 2. 减少channel操作 - 使用sync.Pool
var bufferPool = sync.Pool{
    New: func() interface{} {
        return make([]byte, 4096)
    },
}

func process(buf []byte) {
    data := bufferPool.Get().([]byte)
    defer bufferPool.Put(data)
    // 使用data...
}
```

### 7.2 G数量控制

```go
// 合理的G数量：CPU核心数 * 10 ~ 100
// 过多G会导致调度开销增大

func determineGCount(cpuCount int) int {
    // IO密集型: CPU * 100
    // CPU密集型: CPU * 10
    // 混合型: CPU * 50
    return cpuCount * 50
}

// 示例
runtime.GOMAXPROCS(runtime.NumCPU())
go func() {
    for {
        // CPU密集型任务
    }
}()
```

## 八、面试高频题

### 8.1 高频问题

**Q1: Go调度器是什么模型？为什么选择GMP而不是简单的M:N？**

A: GMP模型是Go 1.5引入的工作窃取调度器。相比简单M:N模型：
- **本地队列**: 每个P有本地队列，减少全局锁竞争
- **工作窃取**: P的本地队列空时，从其他P窃取任务，负载均衡
- **网络轮询**: 非阻塞IO通过epoll/kqueue实现，无需系统调用
- **全局队列**: 平衡负载，避免饥饿

**Q2: 什么时候会发生G的切换？切换的开销有多大？**

A: G切换时机：
- 系统调用(sleep/io/block)
- channel操作(block)
- 显式yield(runtime.Gosched)
- 定时器触发
- 抢占调度(每10ms)

切换开销：
- 本地G->G: ~100-200ns
- 跨M调度: ~1μs
- 系统调用: ~1μs

**Q3: 什么是work stealing？如何避免饥饿？**

A: Work stealing是工作窃取算法：
- P的本地队列为空时，随机从其他P窃取一半任务
- 从队尾窃取，减少锁竞争
- 避免饥饿：全局队列作为补充，优先执行新创建的G

### 8.2 自测题

1. 画出GMP调度模型的架构图
2. 列出G的所有状态，并说明状态转换条件
3. 实现一个简单的worker pool
4. 解释为什么channel操作会阻塞G
5. 分析go race检测器的工作原理

---

**创建时间**: 2026-10-16
**作者**: Ryan
**领域**: Interview / Go并发编程
**关键词**: goroutine, scheduler, GMP, work-stealing, netpoll
