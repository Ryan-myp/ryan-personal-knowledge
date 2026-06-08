# Go 语言深入 — runtime 源码级 GMP、GC、网络轮询器、内存分配器

> 标签: `#Go` `#GMP调度器` `#GC` `#runtime` `#内存分配器` `#源码级`
> 创建日期: 20260608
> 作者: Ryan

---

## 1. GMP 调度器 — runtime 源码级

### 1.1 核心数据结构（src/runtime/runtime2.go）

```go
// G (Goroutine) 结构
type g struct {
    stack       stack     // 栈范围 [stack.lo, stack.hi)
    stack0      stack     // 原始栈（用于 stackguard 校验）
    goid        int64     // goroutine ID（单调递增，原子操作）
    sched       gobuf     // 保存的调度上下文（sp, pc, ip）
    scheduler   scheduler // 调度器相关状态
    atomicstatus uint32   // goroutine 状态（见下方状态机）
    waitreason   string   // 等待原因（用于调试）
    m            *m       // 当前绑定的 M（nil = 不在运行中）
    stackguard0 uintptr   // 栈溢出检查: stack0.guard + stackPrealloc
    stackguard1 uintptr   // 用于 NOSPLIT 调用
    param        unsafe.Pointer // 用于 runtime.call 传递参数
    locks        int32    // 外部锁计数
    gopc         uintptr  // goroutine 创建的 pc（goroutine 调用栈）
    startpc      uintptr  // goroutine 的起始函数地址
    raceignore   int8     // 忽略 race detector 的区域
    
    // 协程私有数据
    mcache       *mcache
    p            puintptr // 绑定的 P（可能为空）
    preempt       bool    // 抢占标志（用于替代 OS 线程）
    preemptStop   bool    // 是否需要在 stopTheWorld 时停止
    preemptScheduled bool // 抢占是否已排期
    stopWait      int32   // stopTheWorld 等待计数
    spinning      bool    // M 是否处于 spinnning 状态
    
    // 等待队列
    wait          *sudog       // 用于 select/channels 等待
    waitDone      func(*sudog) // 完成回调
    
    // GC 标记辅助
    gcAssistBytes int64    // GC 协助标记的字节数
    
    // 并发调度
    gopc          uintptr  // goroutine 创建点的 pc
    ancestry      []uintptr // GC 祖先链
}

// stack 结构
type stack struct {
    lo uintptr  // 栈底（低地址）
    hi uintptr  // 栈顶（高地址）
}

// gobuf — goroutine 调度上下文（被 save/restore 的寄存器状态）
type gobuf struct {
    sp   uintptr  // 栈指针
    pc   uintptr  // 程序计数器
    bp   uintptr  // 基址指针（仅用于调试）
    lr   uintptr  // 返回地址
    ret  uintptr  // 返回目标
    g    uintptr  // 当前 goroutine 指针
    ctxt unsafe.Pointer  // 闭包上下文
}

// P (Processor) 结构
type p struct {
    id          int32           // P 编号（0 ~ gomaxprocs-1）
    status      uint32          // _Psyscall / _Prunning / _Pgcscan / _Pdead
    link        p               // 空闲 P 链表（freelist）
    schedtick   uint32          // 每次 scheduler tick 递增（用于检测死锁）
    lastpolltime uint64         // 最后 poll network 时间
    syscalltick uint32          // 系统调用次数
    syscallsp   uintptr         // M 处于系统调用时的 sp
    syscallpc   uintptr         // M 处于系统调用时的 pc
    sudogcache  *sudog          // sudog 缓存（用于 channel 等待）
    sudogbuf    [128]*sudog     // sudog 缓冲池
    
    // 运行队列（核心！）
    runqhead    *g              // 本地 runnable G 队列头
    runqtail    *g              // 本地 runnable G 队列尾
    runqlen     int32           // 本地队列长度（0 ~ 256）
    
    // 全局队列
    runq        runq            // 从全局队列偷取的 G 队列
    
    // GC 相关
    palloc      persistentAlloc // 物理地址分配器
    cache       pallocCache     // 分配器缓存
    deferpool   [deferpoolSize]*_defer // defer 对象池
    
    // 网络轮询
    netpolldone  atomic        // netpoll 完成计数
    netpollinited int32       // 是否已初始化 netpoll
    
    // 计数器
    sysmontick   schedtick     // 系统监控 tick
    dmmask       uint32        // 死锁检测掩码
    idle         bool          // 是否空闲（非 running 且不在 syscall）
    wasmOffset   uint32        // WASM 偏移
    
    // 工作窃取相关
    wbase         uint32       // 工作基址
    whead         uint32       // 工作头
    wtail         uint32       // 工作尾
    wsize         uint32       // 工作大小
    winuse        uint32       // 正在使用的槽位数
    wincurs       uint32       // 当前工作光标
    wincursLock   mutex        // 工作光标锁
    
    // 其他
    cryptoRange   uintptr       // crypto 操作范围
    profilehz     int32         //  profiling 频率
}

// M (Machine / OS Thread) 结构
type m struct {
    g0      *g         // g0 栈（runtime 调用栈，每个 M 独有）
    curg    *g         // 当前执行的用户 goroutine
    lockedg *g         // 被 LockOSThread() 绑定的 goroutine
    
    // 调度上下文
    sched     m_sched   // M 的调度栈（sp, pc）
    syscallsp uintptr   // 系统调用时的 sp
    syscallpc uintptr   // 系统调用时的 pc
    
    // P 绑定
    p         puintptr  // 绑定的 P（nil 表示不在运行/在 syscall）
    nextp     puintptr  // 下一个 P（用于 steal）
    lastp     puintptr  // 最后一个 P（用于检测 P 变化）
    
    // 自旋状态
    spinning  bool      // M 是否处于 spinning（帮 P 找 G）
    block     bool      // M 是否被阻塞
    
    // 系统调用
    sig       uint64    // 信号掩码
    sigset    uint64    // 待处理的信号
    
    // TLS
    tls       [6]uintptr // Thread Local Storage
    
    // 诊断
    deadlock  bool      // 死锁检测标志
    dump      []byte    // 栈 dumps
    
    // M 关联数据
    mcache    *mcache   // 每 M 的分配器缓存
    fset      *tabler   // 函数表
    seenep    uintptr   // 事件循环计数
    seentick  uint32    // 事件循环 tick
    
    // 网络轮询
    netpollfd int32     // 网络轮询文件描述符
    
    // GC
    gcAssistTime   int64  // GC 协助时间
    waitReason     uint32 // 当前等待原因
}

// m_sched — M 的调度栈
type m_sched struct {
    sp        uintptr
    pc        uintptr
    lr        uintptr
    bp        uintptr
    ret       uintptr
    g         uintptr
    ctxt      unsafe.Pointer
    save      uintptr  // 保存的 sp
    gstatus   uint32   // goroutine 状态
    goid      int64    // goroutine ID
}
```

### 1.2 goroutine 状态机

```c
// src/runtime/runtime2.go — goroutine 状态常量
const (
    _Gidle          = 0  // 初始状态（未使用）
    _Grunnable      = 1  // 可运行（在 runq 中，等待被 M 调度）
    _Grunning        = 2  // 运行中（绑定到 M，正在执行或等待网络 IO）
    _Gsyscall        = 3  // 系统调用中（绑定到 M，等待系统调用返回）
    _Gwaiting        = 4  // 等待中（在等待队列中，不占 M 的 CPU）
    _Gmoribund_unused = 5 // 已死（不被使用）
    _Gdead           = 6  // 已死（goroutine 已退出）
    _Gscan           = 7  // 正在被 GC 扫描（原子操作）
    _Gscanrunning    = 8  // 正在被 GC 扫描且正在运行
    _Gscansyscall    = 9  // 正在被 GC 扫描且在系统调用中
    _Gscanwaiting    = 10 // 正在被 GC 扫描且在等待中
)

// 状态转换:
// _Gidle -> _Grunnable:  创建 goroutine 时
// _Grunnable -> _Grunning: scheduler 调度时 (schedule())
// _Grunning -> _Gsyscall: 进入系统调用时 (startsyc())
// _Gsyscall -> _Grunnable: 系统调用返回时 (retainsys())
// _Grunning -> _Gwaiting:  等待 channel/锁/timer 时
// _Gwaiting -> _Grunnable: channel 操作完成/锁释放/timer 触发时
// _Grunning -> _Gdead:     goroutine 退出时 (exit())
// _Gdead -> _Gidle:        清理时
// _Grunning -> _Gscan:     GC 扫描时
```

### 1.3 调度器核心流程

```c
// src/runtime/proc.go — 调度入口: schedule()
func schedule() {
    _g_ := getg()
    
    // Step 1: 检查是否需要 GC
    if gcBlackenEnabled != 0 {
        gp := gcController.findRunnableGCWorker(_g_.m.p.ptr())
        if gp != nil {
            execute(gp, false) // GC worker goroutine
        }
    }
    
    // Step 2: 尝试从本地队列取 G
    gp, inheritTime := runqget(_g_.m.p.ptr())
    if gp != nil {
        execute(gp, inheritTime)
    }
    
    // Step 3: 尝试从其他 P 偷工作（work stealing）
    gp, inheritTime = findRunnable()
    if gp != nil {
        execute(gp, inheritTime)
    }
    
    // Step 4: 如果没有 G 可执行，进入休眠
    stopm()
    notewakeup(&sched.pauseNote)
    notesleep(&sched.pauseNote)
}

// runqget — 从本地队列取 G
func runqget(_p_ *p) (gp *g, inheritTime bool) {
    for {
        head := atomic.Load(&p.runqhead)
        tail := atomic.Load(&p.runqtail)
        if tail == head {
            return nil, false
        }
        gp := p.runq[head % uint32(len(p.runq))]
        if atomic.Cas(&p.runqhead, head, head+1) {
            return gp, true
        }
    }
}

// findRunnable — 全局工作窃取
func findRunnable() (gp *g, inheritTime bool) {
    // 1. 从全局队列取 G
    _p_ := getg().m.p.ptr()
    if !runqempty(&sched.runq) {
        return runqgrab(_p_, nil, 0)
    }
    
    // 2. 从其他 P 偷工作（最多偷一半）
    for i := 0; i < 4; i++ {
        _p_ = pickpid()
        if gp := stealRunNextG(_p_, 2); gp != nil {
            return gp, false
        }
    }
    
    // 3. 从网络轮询器取等待完成的 goroutine
    if netpollInited != 0 && atomic.Load(&netpollWaiters) > 0 {
        if gp := netpollGetReady(); gp != nil {
            return gp, false
        }
    }
    
    // 4. 从 timer 队列取
    if gp := findTimerG(); gp != nil {
        return gp, false
    }
    
    return nil, false
}

// execute — 执行 G
func execute(gp *g, inheritTime bool) {
    _g_ := getg()
    _g_.m.curg = gp
    gp.m = _g_.m
    atomic.Storeuint32(&gp.atomicstatus, _Grunning)
    
    // 栈检查: stackguard0 = stack.lo + StackGuard
    // 如果 stack.hi - sp > stackguard0，说明栈不够了，需要扩栈
    
    goschedImpl(gp) // 实际上就是切换上下文执行
}
```

### 1.4 工作窃取（Work Stealing）

```c
// 工作窃取: P 本地队列满了（>256），把一半偷给别人
// src/runtime/proc.go — runqsteal

func runqsteal(_p_, thief *p, t bool) bool {
    for {
        head := atomic.Load(&thief.runqhead)
        tail := atomic.Load(&thief.runqtail)
        n := tail - head
        n = n / 2
        if n > uint32(len(thief.runq)) - 1 {
            n = uint32(len(thief.runq)) - 1
        }
        if n == 0 {
            return false
        }
        
        // 从 thief 的尾部偷 n 个 G
        for i := uint32(0); i < n; i++ {
            g := thief.runq[(tail+i) % uint32(len(thief.runq))]
            if atomic.Cas(&thief.runqtail, tail, tail+n) {
                // 成功偷到，把偷到的 G 放到 _p_ 的头部
                runqput(_p_, g, false)
                return true
            }
            break
        }
    }
}

// 为什么从尾部偷？
// 因为本地队列是 LIFO（runqput 放头部），从尾部偷
// 可以避免和被偷的 P 抢同一批 G
```

### 1.5 网络轮询器（Netpoller）

```c
// src/runtime/netpoll.go — 网络 IO 多路复用

// epoll/kqueue/IOCP 的统一封装
type netpollWaiter struct {
    fd    int           // 文件描述符
    ev    uint32        // 事件（EPOLLIN/EPOLLOUT）
    link  *netpollWaiter // 链表指针
}

// netpoll — 阻塞等待网络事件
func netpoll(block bool) *g {
    var events [128]epollevent
    n := epollwait(epfd, &events[0], int32(len(events)), -1)
    
    var ready *g
    for i := int32(0); i < n; i++ {
        ev := &events[i]
        fd := int(ev.data)
        
        // 检查事件类型
        if (ev.events & EPOLLIN) != 0 {
            // 读事件: 把等待的 goroutine 放回 runq
            if gp := netpollfd(fd, true); gp != nil {
                ready = enqueue(gp)
            }
        }
        if (ev.events & EPOLLOUT) != 0 {
            // 写事件
            if gp := netpollfd(fd, false); gp != nil {
                ready = enqueue(gp)
            }
        }
    }
    
    return ready
}

// netpollblock — 注册 IO 等待
func netpollblock(pd *pollDesc, mode int32, waitio bool) bool {
    // 注册到 epoll
    ev := epollEvent{Events: pollEvent(mode)}
    epollctl(epfd, EPOLL_CTL_ADD, pd.fd, &ev)
    
    // 阻塞等待
    ret := netpollgoready(pd.g, mode)
    return ret
}

// pollDesc — 每个 FD 的描述符
type pollDesc struct {
    link    *pollDesc     // 链表指针
    fd      uintptr       // 文件描述符
    closing bool          // 是否已关闭
    seal    uint32        // 密封状态
    rg      uintptr       // 等待读的 G（guintptr）
    rd      int64         // 读的 deadline
    wg      uintptr       // 等待写的 G
    wd      int64         // 写的 deadline
    seq     uint32        // 序列号
    rt      netpollTimer  // 读定时器
    wt      netpollTimer  // 写定时器
    rseq    uintptr       // 读序列号
    wseq    uintptr       // 写序列号
}
```

---

## 2. GC — 三色标记 + 混合写屏障

### 2.1 GC 触发机制

```c
// src/runtime/mgc.go — GC 触发条件

func gcStart(trigger gcTrigger) {
    // 触发条件:
    // gcTrigger.time: 定时触发（默认 2 分钟，可由 GOGC 调整）
    // gcTrigger.heap: 堆增长达到阈值
    // gcTrigger.cycle: 上一轮 GC 未完成
    
    if trigger.heap() {
        // 堆大小 >= gcController.heapGoal
        // heapGoal = lastHeapLive * (1 + GOGC/100)
        // 默认 GOGC=100，即堆增长 100% 时触发 GC
        needCycle()
    }
    
    if trigger.time() {
        // 定时触发
        needCycle()
    }
}

// GC 阶段划分:
// 1. STW Mark Start: 标记所有根（根集合 = 全局变量 + 栈上的引用）
// 2. Concurrency Mark: 并发三色标记
// 3. STW Mark Termination: 确保写屏障一致性
// 4. STW Sweep Termination: 清理未释放的页
```

### 2.2 三色标记算法

```c
// 三色标记: White/Gray/Black
// White: 未访问（可能被回收）
// Gray: 已访问但子节点未扫描
// Black: 已访问且子节点已扫描

// 标记过程:
// 1. 从根节点出发，将可达对象标记为 Gray
// 2. 从 Gray 队列取对象，扫描其引用，将被引用的对象标为 Gray，自身标为 Black
// 3. 重复直到 Gray 队列为空

// 关键: 写屏障（Write Barrier）保证正确性
// 当并发标记期间发生写操作（引用变更），写屏障确保不漏标
```

### 2.3 混合写屏障（Hybrid Write Barrier）源码

```c
// src/runtime/mbarrier.go — 混合写屏障
// 核心: 在写引用时，如果目标对象是 White，将其预检为 Gray

// 写屏障伪代码:
// func WB_write(p *unsafe.Pointer, q *unsafe.Pointer) {
//     if q != nil {
//         // 如果 q 指向的对象是 White（未被扫描到）
//         // 将其预检为 Gray，防止被错误回收
//         if isWhite(q) {
//             enqueueToGrayQueue(q)
//         }
//     }
// }

// Go 的实现: 在汇编层插入写屏障指令
// src/runtime/stubs.go:
//go:nosplit
func writeBarrier() {
    // 内联到每个写操作前
    // 检查 gcphase == _GCmark
    // 如果是，执行写屏障逻辑
}

// 写屏障的两种模式:
// 1. 混合写屏障: 同时支持三色标记和增量标记
//    - 写操作时: 如果目标 White → 预检为 Gray
//    - 读操作时: 如果源 Black 且目标 White → 预检为 Gray
// 2. 单向写屏障: 只写操作，只预检

// Go 1.8+ 使用混合写屏障:
// func writeBarrierPre() {
//     if gcphase == _GCmark {
//         // 并发标记期间
//         _g_.m.gcAssistTime += timeNow() - t
//         // 如果 assist 不足，触发 goroutine 协助标记
//         if _g_.m.gcAssistBytes < 0 {
//             GCassist() // 协助 GC 标记
//         }
//     }
// }
```

### 2.4 GC 协助机制（GC Assist）

```c
// src/runtime/mgc.go — GC 协助
func GCassist() {
    // 每个 Goroutine 在分配内存时，需要贡献一部分给 GC 标记
    // 原理: goroutine 分配内存时，会先"借"给 GC，然后在标记阶段"还"
    
    _g_ := getg()
    
    // 计算需要标记的字节数
    assistBytes := (float64(alloc) * float64(GOGC)) / 100.0
    
    // 如果借给 GC 的字节不足，触发协助
    if _g_.m.gcAssistBytes < -assistBytes {
        // 执行标记工作
        for _g_.m.gcAssistBytes < 0 {
            markOne()  // 标记一个对象
            _g_.m.gcAssistBytes += 8 // 每标记一个对象，"还"给 GC 8 字节
        }
    }
}

// GC 扫描:
// 1. Stack Scanning: 扫描所有 G 的栈，找出存活对象
//    - 每个 M 的 g0 栈在调度时被扫描
//    - 扫描结果: 将栈上的指针标记为存活（预检为 Gray）
// 2. Root Scanning: 扫描全局变量
//    - 全局变量在 GC 开始时预检
// 3. Heap Scanning: 并发标记堆对象
```

---

## 3. 内存分配器 — mcache/mcentral/mspan

### 3.1 三级分配架构

```c
// Go 内存分配器: mspan → mcentral → mcache → P
// 核心思想: 分层缓存，减少锁竞争

// 分配流程:
// 1. 用户请求 malloc(size)
//    → 查找 P 的 mcache
//    → 如果 mcache 有空闲 span → 分配
//    → 如果 mcache 满了 → 从 mcentral 取新 span
//    → 如果 mcentral 满了 → 从 mmalloc 分配新 span（大页）

// 2. 释放流程:
//    → 释放到 mcache
//    → mcache 满了 → 归还给 mcentral
//    → mcentral 满了 → 归还给 OS（munmap）
```

### 3.2 核心数据结构

```c
// src/runtime/malloc.go — mspan 结构（最小分配单位）
type mspan struct {
    next      *mspan  // 链表指针
    prev      *mspan  // 前驱
    
    startAddr uintptr // span 的起始地址
    
    npages    uintptr // 页面数
    
    // 分配信息
    freeindex   uintptr  // 下一个空闲槽的索引
    freedcount  uintptr  // 已释放的槽数
    allocBits   *gcBits  // GC 分配位图（每 8 字节 1 bit）
    gcmarkwbuf  [3]pallocBits // GC 标记缓冲区
    
    // 尺寸类别
    sizeclass   uint8   // 尺寸类别（1-67，对应不同大小）
    cacheallocs uintptr  // 缓存分配的计数
    
    // 管理
    spanclass   spanClass // 尺寸类别 + 是否需要 zero
    
    // 队列
    alllink     *mspan    // 所有 span 的链表
    scavenged   *mspan    // 已回收的 span
    
    // 特殊
    baseMask      uint8     // 如果非 0，span 起始地址 + baseMask = 对齐边界
    allocCount    uint16    // 已分配槽数
    typeraw       [32]btype // 类型信息（用于调试）
    // ... 更多字段
}

// spanClass: 尺寸类别编码
type spanClass struct {
    sizeclass  uint8  // 尺寸类别（0-67）
    needszero  bool   // 是否需要清零
}

// mcentral: 管理同一尺寸类别的所有 mspan
type mcentral struct {
    lock       mutex          // 锁
    spans      **mspan        // 该尺寸类别的 spans 数组
    nonEmpty   mSpanList      // 非空的 span 链表
    empty      mSpanList      // 空的 span 链表
    sizeclass  uint8          // 尺寸类别
    // ...
}

// mcache: 每 P 的本地缓存（无锁分配）
type mcache struct {
    small    [numSpanClasses]mscacheSmallSpan // 小对象缓存
    large    [64]unsafe.Pointer               // 大对象缓存
    
    // 其他
    tcmallocStat      tcmallocStat
    // ...
}

// mcacheSmallSpan: 每个尺寸类别的缓存
type mcacheSmallSpan struct {
    list   mSpanList    // span 链表
    gcmark bool         // 是否在 GC 标记中
}
```

### 3.3 尺寸类别（Size Classes）

```c
// Go 将内存分配按大小分成 68 个尺寸类别:
// 类别 1:  8 字节
// 类别 2: 16 字节
// 类别 3: 32 字节
// 类别 4: 48 字节
// 类别 5: 64 字节
// ...
// 类别 67: > 32MB（大对象，直接分配）

// 小对象 (< 32KB): 通过 mcache → mcentral → mspan 分配
// 大对象 (>= 32KB): 直接通过 mmap 分配（不经过 mspan）
// 巨对象 (> 1GB): 按页分配

// 为什么用尺寸类别？
// 1. 减少内存碎片: 同一尺寸类别的 span 可以复用
// 2. 加速分配: O(1) 查找尺寸类别
// 3. 简化 GC: 扫描时已知每个槽的大小
```

### 3.4 分配流程源码

```c
// src/runtime/malloc.go — mallocgc(size, typ, needzero bool)
func mallocgc(size uintptr, typ unsafe.Pointer, needzero bool) unsafe.Pointer {
    _g_ := getg()
    
    // Step 1: 检查是否是大对象
    if size <= maxSmallSize {
        // 小对象: 走 mcache 路径
        sc := makeSpanClass(size, needzero)
        mc := _g_.m.mcache
        
        // 从 mcache 取 span
        if mc.freeindex == mc.nelems {
            // mcache 满了，从 mcentral 取新 span
            span := mc.grow(sc)
            if span == nil {
                // mcentral 也没有了，从 mmalloc 分配
                span = mheap_.allocSpan(size, false)
                mc.insert(span)
            }
        }
        
        // 分配一个槽
        base := span.base() + mc.freeindex*uintptr(sc.size)
        mc.freeindex++
        mc.allocs++
        
        // 清零
        if needzero {
            memclrNoHeapPointers(base, size)
        }
        
        return unsafe.Pointer(base)
    }
    
    // Step 2: 大对象直接 mmap
    span := mheap_.allocLarge(size)
    if span == nil {
        throw("out of memory")
    }
    
    // 清零
    if needzero {
        memclrNoHeapPointers(span.base(), size)
    }
    
    return unsafe.Pointer(span.base())
}

// 释放流程:
func free(p unsafe.Pointer, size uintptr) {
    _g_ := getg()
    
    if size <= maxSmallSize {
        // 小对象: 释放到 mcache
        span := mheap_.pageFor(p)
        span.freeindex = span.freeindex + 1
        span.freedcount++
        
        if span.freedcount == span.nelems {
            // span 完全空闲，归还给 mcentral
            mcentral.free(span)
        }
    } else {
        // 大对象: 直接 munmap
        mheap_.freeLarge(p)
    }
}
```

---

## 4. 栈管理 — 动态扩缩栈

### 4.1 栈结构

```c
// src/runtime/stack.go — 栈管理
type stack struct {
    lo uintptr  // 栈底（低地址）
    hi uintptr  // 栈顶（高地址）
}

// 栈的初始大小:
// - Goroutine 初始栈: 2KB（Go 1.4+）
// - 如果不够，自动扩容
// - 如果太大，自动缩容

// 栈溢出检测:
// stackguard0 = stack.lo + StackGuard
// 每次函数调用前检查: sp < stackguard0 ? 需要扩栈

// StackGuard 常量的作用:
// const StackGuard = 4096 // 4KB 保护区域
// 确保 sp 不会跨过保护区域
```

### 4.2 栈扩缩逻辑

```c
// src/runtime/stack.go — 栈扩容
func newstack() {
    // 当前 goroutine 的栈不够了，需要扩容
    
    // 1. 计算新栈大小（通常是当前栈的 2 倍）
    newsize := gp.stack.hi - gp.stack.lo
    if newsize < maxstacksize {
        newsize *= 2
    }
    if newsize > maxstacksize {
        newsize = maxstacksize
    }
    
    // 2. 分配新栈
    newstack := malg(newsize)
    
    // 3. 拷贝栈内容（包括局部变量、参数、返回地址）
    memmove(newstack.lo, gp.stack.lo, newstack.hi - newstack.lo)
    
    // 4. 更新 goroutine 的栈指针
    gp.stack = *newstack
    gp.stackguard0 = gp.stack.lo + StackGuard
    
    // 5. 更新 P 的缓存（mcache）
    _g_.m.cachep = newstack
    
    // 6. 继续执行（递归返回到新栈上）
    gogo(&sig.uc.uc_mcontext.gregs[REG_SP])
}

// 栈缩容:
// 如果当前栈使用率 < 25%，且栈大小 > 初始大小，触发缩容
// 缩容不是立即发生的，而是在下次栈溢出时检查
```

---

## 5. 同步原语 — sync 包源码

### 5.1 Mutex 源码

```c
// src/sync/mutex.go — Mutex 实现
type Mutex struct {
    state int32
    sema  uint32 // 信号量
}

// Mutex 的状态位:
const (
    mutexLocked = 1 << iota // 锁已持有
    mutexWakeup             // 唤醒等待者
    mutexSleeping           // 正在睡眠
    mutexStarving           // 饥饿模式
    mutexWaitIncrement = 4  // 等待者增量
    mutexLIFOThreshold = 1  // LIFO 阈值
)

// Lock 流程:
func (m *Mutex) Lock() {
    // 快速路径: 无竞争
    if atomic.CompareAndSwapInt32(&m.state, 0, mutexLocked) {
        return
    }
    
    // 慢速路径: 有竞争
    m.lockSlow()
}

func (m *Mutex) lockSlow() {
    // 1. 检查是否进入饥饿模式
    if m.state&mutexLocked != 0 {
        // 锁已被持有
        if m.state&mutexStarving != 0 {
            // 饥饿模式: 直接放到队尾
            m.starving = true
            m.sema++
            return
        }
        
        // 正常模式: 自旋或休眠
        for m.state&mutexLocked != 0 {
            if m.state&mutexSleeping == 0 {
                // 进入休眠
                atomic.Or(&m.state, mutexSleeping)
            }
            // 休眠等待
            runtime_SemacquireMutex(&m.sema, false)
        }
    }
}

// 饥饿模式:
// 当等待者 > 1 时，进入饥饿模式:
// 1. 新获取锁的 goroutine 直接放到队尾
// 2. 等待的 goroutine 直接获取锁
// 3. 等待者 <= 1 时，退出饥饿模式
// 目的: 避免长线程饿死
```

### 5.2 RWMutex 源码

```c
// src/sync/rwmutex.go — RWMutex 实现
type RWMutex struct {
    w           Mutex      // 写锁
    waiterCount int32      // 等待写锁的读者数
    mu          sync.Mutex // 内部锁
    rd          [16]*sem   // 读信号量数组
    rdmu        sync.Mutex // 读锁内部锁
}

// 写优先策略:
// 当有写者等待时，新的读者必须等待写者完成
// 实现: 通过 waiterCount 和 rd 信号量实现
```

### 5.3 WaitGroup 源码

```c
// src/sync/waitgroup.go — WaitGroup 实现
type WaitGroup struct {
    state1 [3]uint64 // state 高位 + semamutex + refcount
    // 实际: [state] [sema]
    // state: 高 32 位 = waiterCount，低 32 位 = refcount
    // sema: 信号量
}

func (wg *WaitGroup) Add(delta int) {
    // 原子操作: state += (uint64(delta) << 32)
    state := atomic.AddUint64(&wg.state1[0], uint64(delta)<<32)
    
    if state&0xffffffff == 0 {
        // refcount 变为 0，唤醒所有等待者
        runtime_Semrelease(&wg.state1[1], false)
    }
}

func (wg *WaitGroup) Wait() {
    for {
        state := atomic.LoadUint64(&wg.state1[0])
        waiter := (state >> 32) + 1
        if waiter == 0 {
            return
        }
        if atomic.CompareAndSwapUint64(&wg.state1[0], state, waiter<<32) {
            runtime_Semacquire(&wg.state1[1])
        }
    }
}
```

---

## 6. channel 源码

### 6.1 channel 结构

```c
// src/runtime/chan.go — hchan 结构
type hchan struct {
    qcount   uint           // 队列中元素数量
    dataqsiz uint           // 环形队列容量
    buf      unsafe.Pointer // 环形队列缓冲区
    elemsize uint16         // 元素大小
    
    closed   uint16         // 是否已关闭
    elemtype *_type         // 元素类型
    
    sendx    uint           // 发送索引
    recvx    uint           // 接收索引
    recvq    waitq          // 等待接收的 G 队列
    sendq    waitq          // 等待发送的 G 队列
    
    lock     mutex          // 保护以上所有字段
}

// waitq — 等待队列
type waitq struct {
    first *sudog
    last  *sudog
}

// sudog — 等待的 goroutine 描述
type sudog struct {
    g        *g           // 等待的 goroutine
    elem     unsafe.Pointer // 传递的数据
    next     *sudog       // 下一个 sudog
    prev     *sudog       // 上一个 sudog
    list     *sudog       // 列表头
    selectsio uint32      // 选择操作 ID
    acqcount uint16       // 获取计数
    releasetime int64     // 释放时间
    // ...
}
```

### 6.2 send/recv 流程

```c
// src/runtime/chan.go — chan send
func chansend(c *hchan, ep unsafe.Pointer, block bool, callerpc uintptr) bool {
    // 快速路径: 队列有空间且有人等待接收
    if c.qcount < c.dataqsiz {
        // 环形队列有空间
        if c.recvq.first != nil {
            // 有人等待接收: 直接传输
            sg := c.recvq.dequeue()
            memmove(sg.elem, ep, c.elemsize)
            sg.g.atomicstatus = _Grunning
            goready(sg.g, 0)
            return true
        }
        // 否则: 放入环形队列
        memmove(c.buf+c.sendx*c.elemsize, ep, c.elemsize)
        c.sendx++
        c.qcount++
        return true
    }
    
    // 慢速路径: 队列满了，等待
    if !block {
        return false
    }
    
    // 等待接收者
    sg := acquireSudog()
    sg.elem = ep
    sg.g = getg()
    c.sendq.enqueue(sg)
    goready(nil, 0) // 挂起当前 goroutine
    
    // 被唤醒时，数据已传走
    return true
}

// 双向同步: send 和 recv 都先检查对端是否有等待者
// 如果有，直接传输（O(1)）
// 如果没有，放入等待队列（阻塞）
```

---

## 7. 常见坑与优化

### 7.1 goroutine 泄漏

```c
// 常见泄漏场景:
// 1. channel 读写不配对
//    ch := make(chan int)
//    go func() { ch <- 1 }() // 无接收者 → goroutine 永远阻塞
//    解决: 使用 select + case <-ctx.Done()
//
// 2. 死锁
//    m.Lock()
//    m.Lock() // 同一 goroutine 重复加锁 → 死锁
//    解决: 使用 RWMutex 或 reentrant mutex
//
// 3. 忘记关闭 channel
//    ch := make(chan int, 100)
//    长时间不关闭 → 内存泄漏（buffer 无法回收）
//    解决: defer close(ch)
//
// 4. select 无 default
//    select {
//    case <-ch: // ch 永远不发数据 → goroutine 泄漏
//    }
//    解决: 加 default 或 context
```

### 7.2 栈溢出

```c
// 递归过深导致栈溢出:
// func foo() { foo() } // 无限递归 → stack overflow
// Go 的栈动态扩缩，但最大 1GB
// 解决: 改用迭代或增加 GOMAXPROCS

// NOSPLIT 调用:
// runtime 内部使用 NOSPLIT 确保不会在扩栈期间被抢占
// 用户代码一般不需要 NOSPLIT
```

### 7.3 性能优化

```c
// 1. 减少 channel 使用: channel 有锁，高频场景用 atomic
// 2. sync.Pool 复用对象: 减少 GC 压力
// 3. 避免大对象分配: 小对象走 mcache，大对象走 mmap
// 4. 减少锁竞争: 用读写锁、局部变量、无锁数据结构
// 5. 使用 GOGC 调整 GC 频率: GOGC=50（更频繁 GC）/ GOGC=200（更少 GC）
// 6. 使用 GOMEMLIMIT 限制内存: 防止 OOM
// 7. 避免频繁字符串拼接: 用 strings.Builder
// 8. 避免接口逃逸: 接口参数会触发 heap 分配
```

---

*本文档基于 Go 1.22 runtime 源码整理，覆盖 GMP/GC/内存/同步/channel 核心机制*
