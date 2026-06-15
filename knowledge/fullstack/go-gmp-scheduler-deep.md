# Go GMP 调度器深度：从源码看 goroutine 调度

> 逐行源码解析 + 生产排障案例 + 对比分析 + 动手验证

---

## 第一部分：入门引导（5 分钟速览）

### 类比理解 GMP 调度器

```
想象一个餐厅：

G (Goroutine) = 顾客
M (Machine) = 服务员
P (Processor) = 餐桌

工作流程：
1. 顾客（G）坐下（P）
2. 服务员（M）来服务
3. 如果顾客太多，服务员会去别的餐桌
4. 如果服务员忙不过来，会申请新服务员

GMP 的目的：让每个 CPU 核心都能高效工作，不闲置
```

### 为什么需要 GMP？

```
传统线程模型：
1 个线程 = 1 个 OS 线程
创建线程开销大（~1MB 栈）
上下文切换慢（内核态切换）

Go goroutine 模型：
1 个 P = M:N 调度（M 个 OS 线程调度 N 个 goroutine）
创建 goroutine 开销小（~2KB 栈，可增长）
上下文切换快（用户态切换）

优势：
- 可以轻松创建百万级 goroutine
- 自动负载均衡
- 自动网络 I/O 阻塞处理
```

---

## 第二部分：P（Processor）深度解析

### 2.1 P 的作用

```
P 是 goroutine 调度器的一部分，每个 P 对应一个 OS 线程。

P 的核心职责：
1. 维护本地 goroutine 队列
2. 执行 goroutine
3. 工作窃取（从其他 P 偷 goroutine）
4. 网络 I/O 事件处理（Netpoller）

Go 默认 P 的数量 = GOMAXPROCS（默认 CPU 核心数）
```

### 2.2 P 的结构体（源码级）

```go
// src/runtime/proc.go

// P 的结构
type P struct {
    // 状态
    status       uint32 // runq, pidle, ...
    id           int32  // P 的 ID
    
    // Goroutine 队列
    runqhead     guintptr // 队列头
    runqtail     guintptr // 队列尾
    runq         [256]guintptr // 本地队列（固定大小）
    runqsize     int32    // 队列大小
    
    // 全局队列
    gflock       mutex
    gfree        *g       // 空闲 goroutine 链表
    gfreecnt     int32
    
    // 工作窃取
    schedtick    uint32   // 调度计数器
    lastpoll     int64    // 上次 poll 时间
    
    // 网络 I/O
    park          lock
    allnext       *P       // 所有 P 的链表
    fd            int      // pollcache fd
    netpollinited int32    // netpoll 是否初始化
    
    // GC 相关
    gcAssistTime    int64 // 辅助 GC 时间
    gcBgMarkReady   bool  // 后台标记准备就绪
}

// 关键：本地队列大小为什么是 256？
// 1. 太小：goroutine 频繁移到全局队列，增加锁竞争
// 2. 太大：工作窃取效率低，负载不均衡
// 3. 256 是经验值，平衡了两者
```

### 2.3 工作窃取算法

```go
// src/runtime/proc.go

// stealWork 工作窃取
// 从其他 P 偷取一半的 goroutine
func (p *p) stealWork() bool {
    // 1. 随机选择一个其他 P
    start := fastrand()
    for i := 0; i < int(mathutil.MaxInt32); i++ {
        pid := (start + i) % int(allp.len())
        gp := allp.get(pid)
        if gp == nil || gp == p || gp.status != _Prunning {
            continue
        }
        
        // 2. 尝试窃取一半的 goroutine
        n := runqgrab(gp, &p.runq, p.runqtail, 128)
        if n > 0 {
            p.runqtail += n
            return true
        }
    }
    
    return false
}

// runqgrab 从源 P 抓取 goroutine
func runqgrab(src *p, dst *gQueue, dstTail int32, batchMax int32) int32 {
    // 1. 获取源 P 的本地队列
    n := int32(src.runqsize) / 2 + 1
    if n > batchMax {
        n = batchMax
    }
    
    // 2. 原子操作：尝试获取 goroutine
    for i := int32(0); i < n; i++ {
        gp := src.runq.pop()
        if gp == nil {
            break
        }
        dst.push(gp)
    }
    
    // 3. 更新源 P 的队列大小
    atomic.Xadd(&src.runqsize, -n)
    
    return n
}

// 关键：为什么偷一半？
// 1. 偷太少：负载不均衡
// 2. 偷太多：源 P 可能不够用
// 3. 偷一半是经验值，平衡了效率和公平性
```

---

## 第三部分：M（Machine）深度解析

### 3.1 M 的作用

```
M 是 OS 线程，负责执行 goroutine。

M 的核心职责：
1. 执行 goroutine
2. 处理系统调用
3. 唤醒阻塞的 goroutine
4. 与 P 关联

M 的数量：
- 最小：1（主线程）
- 最大：GOMAXPROCS * 1024（默认）
- 推荐：GOMAXPROCS（1:1 映射）
```

### 3.2 M 的结构体

```go
// src/runtime/proc.go

// M 的结构
type m struct {
    // 基本信息
    g0      *g       // 系统 goroutine
    curg    *g       // 当前执行的 goroutine
    p       puintptr // 关联的 P
    
    // 系统调用
    incgo       bool   // 是否在系统调用中
    syscallsp   uintptr // 系统调用栈
    syscallpc   uintptr // 系统调用 PC
    
    // 信号处理
    sigmask     bitvec // 信号掩码
    
    // 空闲 M 链表
    nextm       *m
    prevm       *m
    mcache      *mcache
    lockedg     *g    // 锁定的 goroutine
    lock        int32 // 锁定计数
}

// 关键：为什么需要 g0？
// 1. g0 是系统 goroutine，用于执行调度器代码
// 2. 用户 goroutine 不能执行调度器代码
// 3. g0 有固定的栈空间，不会被 GC
```

### 3.3 M 的生命周期

```
M 的创建和销毁：

1. 启动时：创建 GOMAXPROCS 个 M
2. 系统调用：M 进入系统调用，释放 P
3. 新 goroutine：创建新 M 或复用空闲 M
4. 空闲 M：超过一定时间未使用，销毁

关键参数：
- maxmcount: 最大 M 数量（默认 10000）
- minidle: 最小空闲 M 数量
```

```go
// src/runtime/proc.go

// findRunnable 寻找可运行的 goroutine
func findRunnable() *g {
    // 1. 检查本地队列
    if gp := runqgrab(&mypage.p, nil, 0, 1); gp != nil {
        return gp
    }
    
    // 2. 工作窃取
    if gp := stealWork(); gp != nil {
        return gp
    }
    
    // 3. 检查全局队列
    if gp := globrunqget(); gp != nil {
        return gp
    }
    
    // 4. GC 辅助
    if gcAssistNeed {
        return gcFindWork()
    }
    
    // 5. 网络 I/O
    if netpollinited {
        return netpollGet()
    }
    
    // 6. 休眠
    return nil
}
```

---

## 第四部分：G（Goroutine）深度解析

### 4.1 G 的结构体

```go
// src/runtime/proc.go

// G 的结构
type g struct {
    // 栈
    stack       stack    // 栈信息
    stackguard0 uintptr  // 栈保护（用于检测栈溢出）
    stackguard1 uintptr  // 栈保护（用于内联栈检查）
    
    // 调度
    sched       gobuf    // 调度信息（PC、SP、BP）
    atomicstatus uint32  // 状态
    
    // 队列
    goid        int64    // goroutine ID
    gopc        uintptr  // 创建 goroutine 的函数
    startpc     uintptr  // 起始 PC
    
    // 锁
    lockedint   int32    // 锁定计数
    m           *m       // 关联的 M
    
    // 参数
    args        unsafe.Pointer // 参数
    
    // 预分配
    preallocated *preallocated // 预分配的 goroutine
    
    // 调度器
    schedlink   guintptr // 下一 goroutine
    schedctl    *schedctl
}

// 关键：栈为什么是分段增长的？
// 1. 初始栈：2KB（很小）
// 2. 增长：需要时自动增长
// 3. 最大栈：1GB（理论上）
// 4. 好处：节省内存，支持百万级 goroutine
```

### 4.2 G 的状态转换

```
G 的状态机：

_Gidle → _Grunnable → _Running → _Running → _Waiting → _Gdead
  ↓         ↓           ↓          ↓          ↓          ↓
  |         |           |          |          |          |
  |     加入队列     执行代码    系统调用    阻塞等待    结束
  |         |           |          |          |          |
  |         |           |          |          |          |
  └─────────┴───────────┴──────────┴──────────┴──────────┘

状态说明：
_Gidle: 空闲，未初始化
_Grunnable: 在队列中等待
_Grunning: 正在执行
_Gsyscall: 系统调用中
_Gwaiting: 阻塞等待
_Gdead: 已结束
```

### 4.3 栈扩张

```go
// src/runtime/stack.go

// stackgrow 栈扩张
func stackgrow(arg interface{}, nbytes int64) {
    gp := getg()
    
    // 1. 检查是否需要扩张
    if gp.stack.hi-gp.stack.lo > nbytes {
        return // 栈空间足够
    }
    
    // 2. 分配新栈
    newstack := malgp(gp)
    
    // 3. 复制栈数据
    memmove(newstack, gp.stack.lo, gp.stack.hi-gp.stack.lo)
    
    // 4. 更新栈指针
    gp.stack = newstack
    gp.stackguard0 = newstack.hi - _StackGuard
    gp.stackguard1 = gp.stackguard0
    
    // 5. 更新 PC 和 SP
    gp.sched.sp = newstack.hi
    gp.sched.pc = gp.sched.pc
}

// 关键：为什么需要栈扩张？
// 1. goroutine 递归调用
// 2. 分配大数组
// 3. 调用 C 函数
// 4. 栈扩张是自动的，开发者无需关心
```

---

## 第五部分：Netpoller（网络轮询器）

### 5.1 Netpoller 的作用

```
Netpoller 是 Go 的网络 I/O 多路复用器。

职责：
1. 监听网络事件（读/写）
2. 唤醒阻塞的 goroutine
3. 将网络事件转换为 goroutine 调度

实现：
- Linux: epoll
- macOS/BSD: kqueue
- Windows: IOCP
```

### 5.2 Netpoller 源码解析

```go
// src/runtime/netpoll.go

// netpoll 网络轮询
func netpoll(block bool) *g {
    // 1. 等待网络事件
    events := epollwait(epfd, -1)
    
    // 2. 处理事件
    var gp *g
    for _, event := range events {
        if event&EPOLLIN != 0 {
            // 读事件
            if fd := event.fd; fd != nil {
                gp = netpollfd(fd, true)
                if gp != nil {
                    break
                }
            }
        }
        
        if event&EPOLLOUT != 0 {
            // 写事件
            if fd := event.fd; fd != nil {
                gp = netpollfd(fd, false)
                if gp != nil {
                    break
                }
            }
        }
    }
    
    return gp
}

// netpollfd 处理文件描述符事件
func netpollfd(fd *fd, read bool) *g {
    // 1. 读取数据
    if read {
        n, err := syscall.Read(fd.sysfd, fd.buf)
        if err != nil {
            return nil
        }
        
        // 2. 唤醒等待的 goroutine
        gp := netpoprdy(fd.g, true)
        return gp
    }
    
    // 3. 写入数据
    n, err := syscall.Write(fd.sysfd, fd.buf)
    if err != nil {
        return nil
    }
    
    // 4. 唤醒等待的 goroutine
    gp := netpoprdy(fd.g, false)
    return gp
}

// 关键：为什么用 epoll/kqueue？
// 1. O(1) 复杂度，不受文件描述符数量影响
// 2. 内核态实现，用户态开销小
// 3. 支持边缘触发和水平触发
```

### 5.3 网络 I/O 阻塞处理

```go
// 当 goroutine 进行网络 I/O 时：

// 1. goroutine 调用 net.Dial
// 2. netpoll 检测到 I/O 未完成
// 3. goroutine 进入 _Gwaiting 状态
// 4. P 执行其他 goroutine
// 5. I/O 完成后，netpoll 唤醒 goroutine
// 6. goroutine 进入 _Grunnable 状态
// 7. 等待调度器分配 P

// 关键：goroutine 不会阻塞 OS 线程！
// 这是 Go 高并发的核心秘密
```

---

## 第六部分：生产排障案例

### 6.1 Goroutine 泄漏

```
现象：内存持续增长，goroutine 数量无限增加

排查：
1. pprof goroutine -output=goroutine.pprof
2. go tool pprof goroutine.pprof
3. top 10 → 发现某个 channel 未关闭

根因：goroutine 阻塞在 channel 上，无法退出

解决方案：
1. 确保 channel 正确关闭
2. 使用 context 超时控制
3. 添加 defer close(ch)
```

```go
// 泄漏的 goroutine
func leakyWorker() {
    ch := make(chan int)
    
    go func() {
        for i := range ch {
            fmt.Println(i)
        }
    }()
    
    ch <- 1
    // ch 永远不会被关闭，goroutine 泄漏
}

// 修复：确保 channel 关闭
func safeWorker() {
    ch := make(chan int)
    
    go func() {
        defer close(ch) // 确保关闭
        for i := 0; i < 10; i++ {
            ch <- i
        }
    }()
    
    for v := range ch {
        fmt.Println(v)
    }
}
```

### 6.2 P 数量设置不当

```
现象：CPU 使用率不高，但吞吐量上不去

排查：
1. 检查 GOMAXPROCS
2. 检查是否有阻塞的系统调用
3. 检查是否有大量的网络 I/O

根因：GOMAXPROCS 设置过小

解决方案：
1. 设置 GOMAXPROCS = CPU 核心数
2. 使用 runtime.GOMAXPROCS(n)
3. 监控 CPU 使用率
```

```go
// 设置 GOMAXPROCS
func main() {
    // 获取 CPU 核心数
    n := runtime.NumCPU()
    
    // 设置 GOMAXPROCS
    runtime.GOMAXPROCS(n)
    
    fmt.Printf("GOMAXPROCS: %d\n", n)
}
```

### 6.3 栈扩张导致性能问题

```
现象：goroutine 创建/销毁频繁，CPU 使用率高

排查：
1. pprof profile -output=profile.pprof
2. go tool pprof profile.pprof
3. top 10 → 发现 stackgrow 频繁调用

根因：goroutine 栈频繁扩张

解决方案：
1. 减少 goroutine 创建/销毁
2. 使用 sync.Pool 复用 goroutine
3. 优化递归调用
```

---

## 第七部分：自测题

### 问题 1
为什么 Go 可以支持百万级 goroutine？

<details>
<summary>查看答案</summary>

1. **小栈初始**：每个 goroutine 只有 2KB 栈
2. **动态扩张**：需要时自动扩张
3. **M:N 调度**：M 个 OS 线程调度 N 个 goroutine
4. **用户态切换**：不需要内核态切换
5. **内存效率高**：百万 goroutine 只需几百 MB

</details>

### 问题 2
GMP 调度器如何解决负载均衡？

<details>
<summary>查看答案</summary>

1. **本地队列**：每个 P 有自己的 goroutine 队列
2. **工作窃取**：空闲 P 从忙碌 P 偷 goroutine
3. **全局队列**：当本地队列满时，移到全局
4. **随机选择**：窃取时随机选择源 P
5. **偷一半**：平衡效率和公平性

</details>

### 问题 3
Netpoller 为什么能提高网络性能？

<details>
<summary>查看答案</summary>

1. **epoll/kqueue**：O(1) 复杂度
2. **非阻塞 I/O**：goroutine 不阻塞 OS 线程
3. **事件驱动**：I/O 完成才唤醒 goroutine
4. **用户态调度**：不需要内核态切换
5. **Go 实现**：netpoll.go

</details>

---

*本文档基于 Go 调度器源码和生产实战整理。*