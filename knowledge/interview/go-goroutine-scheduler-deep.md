# Go Goroutine调度器 - 资深专家深度实现

## 一、GMP调度模型

### 1.1 核心概念

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Go调度器 GMP模型                                   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   G (Goroutine)          M (Machine)          P (Processor)             │
│   ┌──────────────┐       ┌──────────────┐       ┌──────────────┐        │
│   │ goroutine #1 │       │ OS Thread #0 │       │ Local PQ    │        │
│   │ goroutine #2 │──────▶│              │◀──────│ Runnable: 5 │        │
│   │ goroutine #3 │       │ stack: 2KB   │       │ Global Q: 10│        │
│   │      ...     │       │ pc: 0x1234   │       │ spin: false │        │
│   └──────────────┘       └──────────────┘       └──────────────┘        │
│                                                                         │
│   • G: 用户态协程，轻量级执行单元                                        │
│   • M: OS线程，真正执行代码的载体                                        │
│   • P: 逻辑处理器，管理G队列和M的关联                                    │
│                                                                         │
│   关系:                                                                  │
│   • 1个M必须绑定1个P                                                   │
│   • 1个P可以关联多个G                                                  │
│   • G可以在不同M之间迁移                                                │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 1.2 核心数据结构

```go
// src/runtime/proc.go

// M 代表一个OS线程
type M struct {
    g0      *G       // 系统goroutine，用于调度
    curg    *G       // 当前运行的用户goroutine
    p       puintptr // 绑定的P
    
    sched   struct {
        sp     uintptr
        pc     uintptr
        fp     uintptr
        lr     uintptr
        ret    uintptr // 返回值
        ctxt unsafe.Pointer
    }
    
    stack       stack      // 当前使用的栈
    stackguard0 uintptr   // 栈溢出检查用
    stackguard1 uintptr   // ARM64专用
    
    // 自旋状态
    selfgen    bool
    spinlink   *m
    nextp      puintptr
    linkspeed  int8
    
    // 系统调用相关
    syscallsp   uintptr
    syscallpc   uintptr
    incgo       bool
    fd          uintptr // 文件描述符（用于epoll）
    sigmask     sigset  // 信号掩码
    
    // TLS
    tls       [6]uintptr
    mstartfn  func()
    
    // 工作相关
    work        unsafe.Pointer
    helpgc      int32
    stopping    bool
    fdpfd       [2]uintptr
    cputimedelta int64
}

// P 代表逻辑处理器
type P struct {
    id          int32
    status      uint32 // idle/runnable/running/gcwaiting/dead
    link        puintptr
    schedtick    uint32
    syscalltick  uint32
    sysmontick   sysmontick
    m            muintptr // 当前绑定的M
    gFree        *gList   // 空闲的G链表
    gFreeCount   int32
    
    // 本地runnable G队列
    runq     gQueue
    runqhead uint32
    runqtail uint32
    runqsize int32
    
    // 全局队列
    globalRunQ gQueue
    
    // GC相关
    gcBgMarkWorker guintptr
    gcw            gcWork
    wbBuf          writebuf
    lastPollTime   unixNano
    
    // 用户定时器
    timerp *_timer
    
    // 物理内存大小
    phyaddr int
    
    // 外部对象计数
    externalCallCount int32
    
    // ... 其他字段
}

// G 代表goroutine
type G struct {
    // Stack
    stack       stack   // [lo, hi)
    stackguard0 uintptr // 栈溢出检查（比较值）
    stackguard1 uintptr // ARM64专用
    
    // 调度信息
    sched      struct {
        sp     uintptr
        pc     uintptr
        fp     uintptr
        lr     uintptr
        ret    uintptr
        ctxt unsafe.Pointer
    }
    
    // 函数和参数
    fn       funcval  // 要执行的函数
    param    unsafe.Pointer
    waitreason waitReason
    
    // 状态
    atomicstatus uint32
    
    // 队列链接
    goid   int64
    waitsince int64
    waitercount int32
    
    // 系统调用
    syscallsp   uintptr
    syscallpc   uintptr
    stuck       bool
    spinning    bool
    preempt       bool
    preemptStop   bool
    preemptSchd   bool
    
    // 栈区间
    stacksiz   int32
    unused     uint8
    
    // goroutine组
    group      *gGroup
    
    // 外部对象计数
    extfreealloc uintptr
    
    // ... 其他字段
}
```

---

## 二、调度流程

### 2.1 启动流程

```go
// runtime/proc.go

// main函数入口
func main() {
    // 1. 初始化内存分配器
    mcommoninit(_g_.m)
    
    // 2. 创建P
    for i := 0; i < gomaxprocs; i++ {
        newproc1()
    }
    
    // 3. 启动m0的调度循环
    mstart()
}

// mstart 是M的入口函数
func mstart() {
    // 初始化M
    mcommoninit(_g_.m)
    
    // 进入调度循环
    mstart0()
}

func mstart0() {
    // 设置栈限制
    incargsp := setg(_g_)
    
    // 运行m->mstartfn
    if fn := _g_.m.mstartfn; fn != nil {
        fn()
    }
    
    // 进入调度循环
    schedule()
}

// schedule 是调度器核心
func schedule() {
    _g_ := getg()
    
    for {
        var gp *G
        var inheritTime bool
        
        // 1. 检查是否需要GC
        if _g_.m.p.ptr().status == _Pgcstop {
            gcwaitstopm(_g_.m)
            continue
        }
        
        // 2. 尝试从本地队列获取G
        if gp == nil && _g_.m.p.ptr().runqsize != 0 {
            gp, inheritTime = runqgrab(_g_.m.p.ptr(), &nil, 0)
        }
        
        // 3. 尝试从全局队列获取G
        if gp == nil {
            gp, inheritTime = globrunqget(_g_.m, 0)
        }
        
        // 4. 尝试从其他P偷取G
        if gp == nil {
            gp, inheritTime = findrunnable()
        }
        
        if gp == nil {
            // 没有可运行的G，进入休眠
            stopm()
            continue
        }
        
        // 5. 切换上下文执行G
        if inheritTime {
            _g_.schedlink = gp.schedlink
            gp.schedlink = 0
        }
        
        // 切换栈
        goschedImpl(gp)
    }
}
```

### 2.2 抢占式调度

```go
// 触发抢占
func preemptionHelper(gp *G) {
    // 1. 检查是否需要抢占
    if gp.preempt {
        // 设置栈保护指针，触发栈增长检查
        gp.stackguard0 = stackPreempt
        return
    }
    
    // 2. 检查时间片是否用完
    if _g_.m.p.ptr().schedtick > 0 && _g_.m.p.ptr().schedtick%10 == 0 {
        // 请求抢占
        gp.preempt = true
        gp.stackguard0 = stackPreempt
    }
}

// 栈增长检查
func checkTimeout() {
    _g_ := getg()
    
    // 检查时间片
    if _g_.m.p.ptr().schedtick > 0 && _g_.m.p.ptr().schedtick%128 == 0 {
        // 超时，触发GC或抢占
        osyield()
    }
    
    // 检查GC
    if _g_.m.p.ptr().gcwaiting != 0 {
        gcstoptheWorld()
    }
}
```

---

## 三、工作窃取算法

### 3.1 偷取逻辑

```go
// findrunnable 尝试找到可运行的G
func findrunnable() (gp *G, inheritTime bool) {
    _g_ := getg()
    pp := _g_.m.p.ptr()
    
    // 1. 从本地队列获取
    gp, inheritTime = runqgrab(pp, &nil, 0)
    if gp != nil {
        return gp, inheritTime
    }
    
    // 2. 从全局队列获取
    gp, inheritTime = globrunqget(_g_.m, 0)
    if gp != nil {
        return gp, inheritTime
    }
    
    // 3. 从其他P偷取（工作窃取）
    for i := 0; i < 4; i++ {
        start := int(boringUint32(uintptr(gettimings()), uint(len(allp))))
        for j := 0; j < len(allp); j++ {
            pid := int(uint(start+j) % uint(len(allp)))
            if pid == int(pp.id) {
                continue
            }
            
            victim := allp[pid]
            if victim.status != _Prunning {
                continue
            }
            
            // 尝试偷取
            gp, inheritTime = runqsteal(_g_.m, victim, pp)
            if gp != nil {
                return gp, inheritTime
            }
        }
    }
    
    return nil, false
}

// runqsteal 从目标P偷取一半的G
func runqsteal(m *m, victim *p, victimpp *p) (*G, bool) {
    n := victim.runqsize / 2 + victim.gFreeCount
    if n > 256 {
        n = 256
    }
    
    // 批量偷取
    var batch [256]*G
    n = runqgrab(victim, batch[:], n)
    
    if n == 0 {
        return nil, false
    }
    
    // 将偷取的G放入自己的队列
    for i := uint32(0); i < n; i++ {
        runqput(victimpp, batch[i], false)
    }
    
    // 返回第一个G
    return batch[0], false
}
```

---

## 四、系统调用处理

### 4.1 系统调用前后

```go
// 系统调用前
func sysmon() {
    // 1. 检查长时间运行的goroutine
    for {
        if gp := sched.pollUntil != 0 {
            // 超时，抢占
            gp.preempt = true
            gp.stackguard0 = stackPreempt
        }
        // 检查网络I/O
        netpoll(false)
        sleep <- 1
    }
}

// 进入系统调用
func gosyscall(sp uintptr) {
    _g_ := getg()
    
    // 1. 释放P
    releasem(_g_.m)
    
    // 2. 记录系统调用信息
    _g_.syscallsp = sp
    _g_.syscallpc = getcallerpc()
    _g_.incgo = true
    
    // 3. 系统调用实际执行
    // ... 内核代码 ...
}

// 从系统调用返回
func goruntime(syscallsp, syscallpc uintptr) {
    _g_ := getg()
    
    // 1. 获取P
    acquirem()
    
    // 2. 恢复上下文
    _g_.syscallsp = syscallsp
    _g_.syscallpc = syscallpc
    _g_.incgo = false
    
    // 3. 重新进入调度
    schedule()
}
```

---

## 五、Goroutine泄漏排查

### 5.1 常见泄漏模式

```go
package leak

import (
    "context"
    "sync"
    "time"
)

// 泄漏模式1: Channel未关闭
func channelLeak() {
    ch := make(chan int)
    
    go func() {
        for i := 0; i < 1000000; i++ {
            ch <- i  // 如果没有接收者，会阻塞
        }
    }()
    
    // 函数返回，goroutine泄漏
}

// 泄漏模式2: Context未取消
func contextLeak() {
    ctx, cancel := context.WithCancel(context.Background())
    
    go func() {
        for {
            select {
            case <-ctx.Done():
                return
            default:
                time.Sleep(time.Second)
            }
        }
    }()
    
    // 忘记调用cancel()
}

// 泄漏模式3: Mutex未释放
func mutexLeak() {
    var mu sync.Mutex
    var wg sync.WaitGroup
    
    for i := 0; i < 100; i++ {
        wg.Add(1)
        go func() {
            defer wg.Done()
            mu.Lock()
            defer mu.Unlock()
            // 如果panic，defer不会执行
        }()
    }
    
    wg.Wait()
}

// 正确写法: 使用 defer 和 context
func correctPattern() {
    ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
    defer cancel()
    
    ch := make(chan int, 100)
    
    go func() {
        defer close(ch)
        for i := 0; i < 100; i++ {
            select {
            case ch <- i:
            case <-ctx.Done():
                return
            }
        }
    }()
}
```

---

## 六、面试高频题

### 6.1 基础题

**Q: 解释GMP模型中每个角色的作用？**

```
A:
• G (Goroutine): 用户态协程，包含栈、指令指针、状态等，是最小的执行单元
• M (Machine): OS线程，真正执行代码的载体，与内核线程1:1映射
• P (Processor): 逻辑处理器，管理G队列和M的关联，控制并发度

关系:
• 1个M必须绑定1个P
• 1个P可以关联多个G（通过本地队列）
• G可以在不同M之间迁移（通过全局队列或工作窃取）
```

**Q: Goroutine和线程有什么区别？**

```
A:
• 启动成本: Goroutine ~2KB栈，线程 ~1-8MB栈
• 调度方式: Goroutine用户态调度，线程内核态调度
• 数量级: Goroutine可以创建百万级，线程通常千级
• 内存占用: Goroutine栈动态伸缩，线程栈固定大小
• 切换开销: Goroutine切换快（上下文小），线程切换慢
```

### 6.2 进阶题

**Q: 如何排查Goroutine泄漏？**

```go
// 使用 pprof 诊断
import _ "net/http/pprof"

// 1. 获取goroutine dump
go func() {
    http.ListenAndServe("localhost:6060", nil)
}()

// 2. 分析
go tool pprof http://localhost:6060/debug/pprof/goroutine

// 常见泄漏信号:
// • goroutine数量持续增长
// • 某些goroutine长期处于sleep状态
// • chan receive/send阻塞

// 3. 代码级排查
func findLeak() {
    // 使用 debug.SetTraceback 查看堆栈
    runtime.SetTraceback("all")
    
    // 定期检查
    go func() {
        for {
            time.Sleep(10 * time.Second)
            // 输出goroutine信息
            buf := make([]byte, 1<<20)
            n := runtime.Stack(buf, true)
            fmt.Printf("%s\n", buf[:n])
        }
    }()
}
```

---

## 七、自测题

### 7.1 基础题
1. 画出GMP模型的关系图
2. 解释为什么Go调度器是用户态调度
3. 什么情况下会发生Goroutine泄漏？

### 7.2 进阶题
1. 如何实现一个自定义的调度器？
2. 解释Goroutine抢占式的实现原理
3. 工作窃取算法的时间复杂度是多少？

### 7.3 实战题
1. 给定一段代码，找出可能的Goroutine泄漏点
2. 如何使用pprof定位Goroutine泄漏？
3. 如何设计一个高并发的任务队列？

---

## 参考文档

- [Go Scheduler源码](https://github.com/golang/go/blob/master/src/runtime/proc.go)
- [Go Scheduler详解](https://draveness.me/golang/docs/part2-foundation/ch05-concurrency/golang-scheduler/)
- [Understanding Go Scheduler](https://go.dev/blog/pipelines)
