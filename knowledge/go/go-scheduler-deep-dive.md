# Go 调度器深度蒸馏

> 来源：Go 官方源码 `runtime/proc.go`
> 蒸馏日期：2026-01-15
> 核心价值：官方设计意图 + 实战经验

---

## 一、G/M/P 模型设计意图

### 官方源码摘录
```go
// The main concepts are:
// G - goroutine.
// M - worker thread, or machine.
// P - processor, a resource that is required to execute Go code.
//     M must have an associated P to execute Go code, however it can be
//     blocked or in a syscall w/o an associated P.
```

### 我的理解
```
这是 Go 调度器的核心创新：

G (Goroutine)  → 轻量级用户态线程
                 - 初始栈 2KB，可动态增长
                 - 调度由 runtime 管理，无需系统调用

M (Machine)    → 操作系统线程
                 - 真正的执行者
                 - 绑定到 P 才能执行 G

P (Processor)  → 逻辑处理器
                 - 维护本地 runqueue（256个G）
                 - 实现 work stealing 负载均衡
                 - 数量 = GOMAXPROCS
```

### 为什么这样设计？
```
问题：纯用户态线程调度器如何高效利用多核？

答案：分布式调度
1. 每个 P 维护本地队列，减少锁竞争
2. M 绑定 P，避免上下文切换
3. Work stealing 解决负载不均衡
4. System call 时 M 可以脱离 P
```

---

## 二、关键数据结构

### G 结构体（来自 runtime2.go）
```go
type g struct {
    stack       stack   // [stack.lo, stack.hi)
    stackguard0 uintptr // 栈保护，触发 growth
    stackguard1 uintptr // systemstack 用
    
    _panic    *_panic     // 内层 panic
    _defer    *_defer     // 内层 defer
    m         *m          // 当前绑定的 M
    
    sched     gobuf       // 调度上下文
    goid      uint64      // 唯一标识
    
    // 预抢占相关
    preempt       bool   // 预抢占信号
    preemptStop   bool   // 是否停止执行
    preemptShrink bool   // 是否收缩栈
    
    atomicstatus atomic.Uint32  // 状态原子变量
    waitsince    int64        // 等待开始时间
    waitreason   waitReason   // 等待原因
}
```

### P 结构体（来自 runtime2.go）
```go
type p struct {
    id          int32       // P 编号
    status      uint32      // pidle/prunning/...
    link        puintptr    // idle P 链表
    m           muintptr    // 绑定的 M（nil=空闲）
    
    mcache      *mcache     // 内存分配缓存
    pcache      pageCache   // 页缓存
    
    // 运行队列（环形缓冲区）
    runqhead uint32
    runqtail uint32
    runq     [256]guintptr  // 本地队列
    
    runnext guintptr      // 下一个要运行的 G
    
    // GID 缓存
    goidcache    uint64
    goidcacheend uint64
    
    // 空闲 G 列表
    gFree gList
}
```

---

## 三、调度算法详解

### 3.1 调度入口（schedule 函数）
```go
func schedule() {
    _g_ := getg()
    
    // 1. 检查是否需要 GC assist
    if gp != nil {
        checkTimersp := _g_.locks
        if gcBlackenPercent <= 0 {
            gcAssistAlloc(_g_, gp)
        }
    }
    
    // 2. 尝试从本地队列获取 G
    if gp == nil && myp.runnext != 0 {
        gp = myp.getrunnext()
        myp.runnext = 0
    }
    
    // 3. 本地队列没有，尝试从全局队列获取
    if gp == nil {
        gp, inheritance := runqgrab(myp, false, _g_.schedtrace, _g_.schedwhen)
        if gp == nil {
            // 4. 全局也没有，尝试 work stealing
            if netpollin_progress == 0 && sched.npidle != uint32(gomaxprocs) {
                gp = findrunnable()
            }
        }
    }
    
    // 5. 执行 G
    if gp != nil {
        execute(gp, inheritance)
    }
}
```

### 3.2 Work Stealing 机制
```go
// 从其他 P 偷工作
func findrunnable() (gp *g, inheritance bool) {
    // 随机选择一个 P
    top := allp[fastrand()%uint32(len(allp))]
    
    // 尝试偷取工作
    if gp, inheritance := runqsteal(_g_.m.p, top, true); gp != nil {
        return gp, inheritance
    }
    
    // 尝试从全局队列获取
    if gp := globrunqget(_g_.m.p, 0); gp != nil {
        return gp, false
    }
    
    return nil, false
}
```

**设计意图**：
```
为什么需要 work stealing？
1. 不同 P 的负载可能不均衡
2. 本地队列空了，需要从其他地方"偷"工作
3. 随机选择目标 P，减少竞争
4. steal 一半，balance 一半
```

### 3.3 Goroutine 创建流程
```go
func newproc(siz int32, fn *funcval) {
    argsize := align(siz, pointerSize)
    
    // 1. 分配 G
    gp := gfget(myp)
    if gp == nil {
        gp = new(g)
        gp.sched.pc = ^uintptr(0)
        gp.gopc = getcallerpc()
        gp.ancestors = &emptyAncestors
        gp.startpc = fn.fn
    }
    
    // 2. 设置栈
    gp.stackalloc = argsize
    gp.stack = stackalloc(uintptr(gp.stackalloc))
    
    // 3. 添加到运行队列
    casGStatus(gp, _Gdead, _Grunnable)
    ready(gp, 0)
}

func ready(gp *g, traceback int32) {
    if trace.enabled {
        traceGoStart(gp)
    }
    
    // 设置为 runnable 状态
    casGStatus(gp, _Gdead, _Grunnable)
    
    // 添加到本地队列
    if runqput(myp, gp, true) {
        if sched.gcwaiting != 0 {
            gcw.wbBufFlush1()
        }
        return
    }
    
    // 本地队列满了，添加到全局队列
    if runqputslow(myp, gp, traceback) {
        return
    }
    
    // 唤醒另一个 M
    wakep()
}
```

---

## 四、实战经验：广告竞价系统中的应用

### 4.1 GOMAXPROCS 调优
```bash
# 广告竞价服务的推荐配置
GOMAXPROCS=7  # 8核机器，留1个给GC

# 在 Kubernetes 中的设置
resources:
  limits:
    cpu: "8"
  requests:
    cpu: "7"
```

**踩坑记录**：
```
问题：GC 停顿导致竞价延迟飙升
根因：GOMAXPROCS 设置为 8（全部核心），GC 与业务争抢 CPU
解决：GOMAXPROCS=7，预留核心给 GC
监控：go tool trace 查看 GC 与业务的 CPU 使用
```

### 4.2 Goroutine 泄漏排查
```go
// 泄漏场景示例
func handleBidRequest(ctx context.Context, req BidRequest) {
    // 错误：goroutine 可能泄漏
    go processBid(req)  // 没有 context 传递
    
    // 正确：传递 context 并处理
    go func() {
        select {
        case <-ctx.Done():
            return
        default:
            processBidWithContext(ctx, req)
        }
    }()
}
```

**排查工具**：
```bash
# 1. 查看 goroutine 数量
curl http://localhost:6064/debug/pprof/goroutine?debug=1

# 2. 生成 trace
go tool trace trace.out

# 3. 分析泄漏
import _ "net/http/pprof"
http.ListenAndServe("localhost:6060", nil)
```

### 4.3 Channel 性能优化
```go
// 反模式：频繁创建 channel
func handler() {
    ch := make(chan Result)  // 每次都创建新 channel
    go process(ch)
    <-ch
}

// 推荐：复用 channel pool
var chPool = sync.Pool{
    New: func() interface{} {
        return make(chan Result, 100)  // 有缓冲
    },
}

func handler() {
    ch := chPool.Get().(chan Result)
    go process(ch)
    <-ch
    chPool.Put(ch)  // 归还给 pool
}
```

---

## 五、调度器性能分析

### 5.1 关键指标
```go
// schedstat 结构体
type schedstats struct {
    nnsync        uint64  // non-blocking synchronize calls
    ngc0          uint64  // GC cycles without work
    ngc1          uint64  // GC cycles with minimal work
    ngc2          uint64  // GC cycles with moderate work
    ngcmarginal   uint64  // GC cycles with marginal work
    ngctime       uint64  // total GC time
    npspinwait    uint64  // non-blocking spin wait
    npidle        uint64  // number of idle Ps
    nhalt         uint64  // number of halts
}
```

### 5.2 监控命令
```bash
# 1. 查看调度统计
go tool trace trace.out | grep -i sched

# 2. 实时监控 goroutine 数量
watch -n 1 'curl -s localhost:6064/debug/pprof/goroutine | wc -l'

# 3. 分析 GC 行为
go tool trace trace.out | grep -i gc

# 4. 查看锁竞争
go tool pprof http://localhost:6064/debug/pprof/mutex
```

---

## 六、核心设计总结

### 1. 分布式调度
```
每个 P 维护本地队列 → 减少锁竞争
Work stealing → 负载均衡
```

### 2. 协作式抢占
```
G 主动让出 CPU（channel操作、系统调用）
被动抢占（长时间运行）
```

### 3. 栈管理
```
初始 2KB，可动态增长
Stack splitting → 防止栈溢出
Stack shrinking → 回收内存
```

### 4. GC 协作
```
Concurrent mark-sweep
Write barrier → 精确回收
GC assist → 分摊 GC 成本
```

---

## 七、进一步学习资源

### 官方文档
- Go Scheduler Design Doc: https://golang.org/s/go11sched
- Go Runtime Source: https://github.com/golang/go/tree/master/src/runtime

### 深入阅读
```bash
# 推荐阅读顺序
1. runtime/proc.go      - 调度器核心
2. runtime/runtime2.go  - 数据结构定义
3. runtime/mgc.go       - GC 实现
4. runtime/stack.go     - 栈管理
5. runtime/channel.go   - Channel 实现
```

---

**核心洞察**：Go 调度器的优雅在于"简单但高效"——分布式队列 + work stealing + 协作式抢占，这三个设计就解决了并发调度的核心问题。
