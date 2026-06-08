# Go 语言深入 — GMP 调度器、GC、runtime 源码

> 标签: `#Go` `#GMP调度器` `#GC` `#runtime` `#源码分析`
> 创建日期: 20260608
> 作者: Ryan

---

## 1. GMP 调度器深度分析

### 1.1 为什么需要 GMP 而非 G/M？

传统 1:1 模型（线程 = goroutine）在高并发下问题：
- **内存开销大**：每个 OS 线程 ~1MB stack
- **上下文切换慢**：频繁的系统调用导致 CPU 浪费
- **调度延迟高**：无法实现微秒级调度

Go 的 M:N 模型（M 个 OS 线程调度 N 个 goroutine）解决了这些问题。

### 1.2 GMP 核心数据结构

```go
// M: OS 线程 (machine)
type m struct {
    g0      *g          // 每�� M 的 g0 栈（用于 runtime 调用）
    curg    *g          // 当前执行的用户 goroutine
    p       p           // 绑定的 P，nil 时表示 M 在休眠/系统调用
    sched   m_sched     // M 的调度上下文
    lockedg *g          // 被 mLock() 绑定的 goroutine
    ...
}

// P: 处理器 (processor) — 调度的核心
type p struct {
    status       uint32      // 空闲/运行/休眠/死
    link             p           // 空闲 P 链表
    schedtick    uint32      // 每次 scheduler tick 递增
    lastpolltime uint64      // 最后 poll network 时间
    runq       runqhead    // P 本地的 runnable G 队列
    runqsize    int32      // 本地队列长度
    goidcache    uint64    // GID 缓存
    goidcacheend uint64   // GID 缓存上限
    ...
    
    // 工作队列（关键！）
    runqhead rung          // 本地队列头部
    runqtail rung          // 本地队列尾部
    runqlen  int32         // 队列长度
    runqsize int32         // 队列容量（最大 256）
    
    // global runq — P 偷取 G 的全局队列
    global runqhead
    globalrunq runqhead
}

// G: goroutine
type g struct {
    stack       stack       // 栈信息 [stack.lo, stack.hi)
    stackguard0 uintptr    // 栈保护值（== stack.lo + _StackGuard）
    stackguard1 uintptr    // 用于内联栈检查
    ...
    sched       g_sched     // 调度上下文（PC/SP 寄存器保存）
    p           p           // 当前绑定的 P
    params      unsafe.Pointer // 用户参数
    preempt       bool       // 抢占标记
    atomicstatus  uint32    // 运行状态
}
```

### 1.3 G 的生命周期与状态转换

```
G 状态机（runtime/proc.go）:

G Idle (0)
  │  Gnew → Gwait → 加入 runq
  ▼
Grunnable (1) ────→ 被 M 调度执行
  │
  ▼
Grunning (2) ──────→ 执行中
  │              │
  │              ├─ 完成 → 释放
  │              │
  │              ├─ syscall 结束 → Grunning → Go (通过 Gosched)
  │              │
  │              ├─ 阻塞（chan锁/network）→ Gwaiting
  │              │
  │              └─ 被抢占 → Grunnable
  
Gwaiting (3) ──→ 在 syscall/chan/lock 中等待
  │
  ├─ 等待完成 → Grunnable
  │
  └─ GC 标记 → GCscan

Gsyscall (4) ──→ 正在执行系统调用
  │
  ├─ syscall 返回 → Grunning（需要找到空闲 P）
  │
  └─ 超时 → 抢占（schedtick 机制）

GCscan (5) ────→ GC 标记阶段（atomic status）
  │
  └─ 标记完成 → 回到原状态

Gdead (6) ────→ goroutine 已终止
  │
  └─ 清理 → 放回 G freelist

Gcopystack (7) → 正在执行 stack copy（栈扩容）
```

### 1.4 调度器初始化（GODEBUG=gctrace=1 视角）

```
1. runtime·schedinit()
   ├── 计算 GOMAXPROCS（默认 1，上限 1024）
   ├── 创建所有 P（初始 status = Pidle）
   ├── 创建 m0 + g0（主线程的 runtime 栈）
   ├── 创建 g0 的调度上下文
   └── 设置 m0.p = nil（主线程还没绑定 P）

2. runtime·newproc() — 创建 goroutine
   ├── 从 gfree list 分配 G
   ├── 分配栈（初始 2KB，可自动扩容）
   ├── 设置 G 的 PC/SP（指向函数入口）
   └── 入队到当前 P 的本地队列 runq

3. runtime·startm() — 唤醒 M 执行 G
   ├── 如果有空闲 P → 唤醒空闲 M
   ├── 如果有 G 在全局队列 → steal work
   └── 否则创建新 M（受 limit 限制）

4. runtime·schedule() — M 的核心调度循环
   └── for {
         ├── 1. 从当前 P 的本地队列 runq 取 G（最高优先级）
         ├── 2. 从 global runq 取 G
         ├── 3. 从其他 P 偷取一半 G（work stealing）
         │       │
         │       └── 随机选一个 P，偷一半
         │
         └── 4. 阻塞（如果 P 的 runq 也空了）
                └── M 进入休眠，等待网络 poller 唤醒
       }
```

### 1.5 栈扩容与栈 shrinking

```go
// 栈布局:
//  [stack.lo] ──→ 栈底（低地址）
//      │
//      ▼ 栈增长方向（向下增长）
//  [stackguard0] = stack.lo + _StackGuard (2KB)
//  [SP 指针]     = 当前栈顶（高地址）
//  [stack.hi]    = 栈顶（高地址）

// 栈检查（内联到函数开头）:
//   if g.stackguard0 != stackPreempt && SP <= stackguard0 {
//       morestack() → runtime·morestack() → runtime·growstack()
//   }

// growstack() 扩容逻辑:
func growstack() {
    // 计算需要的栈空间
    needsp := getcallerpc(&needsp) - sp  // 已用栈
    if needsp < 4*1024 {
        needsp = 4 * 1024  // 最小扩容 4KB
    }
    // 双倍扩容
    needsp += stackpoolsize(needsp)
    
    // 跨帧扩容（copy stack）
    newstack := mal(needsp)  // 分配新栈
    memmove(newstack, stack, oldsize)  // 移动栈内容
    // 修复所有指针
    // ...
}
```

### 1.6 Work Stealing（工作窃取）

```
核心机制：P 的 runq 满了（>256）时，一半放入全局队列，一半留在本地

当 P 的本地队列空了：
  for i := 0; i < 4; i++ {
      // 随机选 4 个 P 偷取
      stealOrder[4:] = 随机排列
      for _, _p := range stealOrder {
          g := runqsteal(_p, p, true)  // 偷取一半
          if g != nil {
              goto startg  // 偷到了，执行这个 G
          }
      }
  }
  
  // 如果都没偷到，尝试从全局队列取
  if g := runqget(p); g != nil {
      goto startg
  }
  
  // 最后，阻塞等待
  stopm()
```

**关键优化**：
- `runqsteal` 偷取一半（_p.runqlen/2），避免全部被抢
- 每次从不同随机 P 偷取，负载均衡
- 最多尝试 4 次，避免空转

---

## 2. GC（垃圾回收）深度分析

### 2.1 Go GC 演进

| 版本 | 类型 | STW 时间 | 并发 |
|------|------|---------|------|
| Go 1.0-1.4 | 标记-清除 | 长 | 否 |
| Go 1.5+ | 三色标记（并发） | 短 | 是 |
| Go 1.8+ | 混合写屏障 | 更短 | 是 |
| Go 1.12+ | Pacer 调优 | 微秒级 | 是 |
| Go 1.16+ | 改进 Pacer | 微秒级 | 是 |
| Go 1.19+ | Pacer 改进 | 亚毫秒级 | 是 |

### 2.2 三色标记法

```
白色 → 未标记（可能是垃圾）
灰色 → 已扫描（对象本身已访问，但其引用的对象尚未扫描）
黑色 → 已扫描（对象及其引用的对象都已扫描）

算法:
  1. 初始标记（STW）: 从根对象出发，标记所有直接引用的对象为灰色
  2. 并发标记: 遍历灰色对象，将其引用的对象标记为灰色，自身变为黑色
     - 工作队列（wbuf）存放未扫描的灰色对象
     - GC worker 从 wbuf 取对象扫描
  3. 最终标记（STW）: 处理写屏障记录的变化
  4. 清扫（并发）: 遍历所有 mbuf，回收白色对象

写屏障（Write Barrier）:
  当 P 写指针时触发:
    if gcphase == _GCmark {
        // 写前: 将旧值对象标记为灰色（防止被误回收）
        // 写后: 将新值对象标记为灰色
    }
  
  混合写屏障（Go 1.8+）:
    // 写前: 将旧对象标记为灰色（标记阶段开始时已在黑/灰的对象不需要）
    // 写后: 将新对象标记为灰色
```

### 2.3 GC 触发条件

```
触发条件（满足任一即触发）:
  1. GCTrigger = 当前 heap 目标 × gcpercent/100
  2. 时间触发: GC 周期过长，强制触发
  3. GCBackgroundUtilization 目标: 保证 GC 不超过 CPU 的 25%

目标 heap 大小:
  target = 上一轮 GC 结束时 heapsize × (1 + gcpercent/100)
  
  gcpercent 默认 100，即 heap 翻倍时触发 GC
  可通过 GOGC=50 调低到 heap 增长 50% 就 GC（更频繁但延迟低）
```

### 2.4 Pacer 算法（Go 1.12+）

```
目标: 让 GC 尽可能在后台完成，减少 STW

Pacer 控制:
  nextGC = gcBgMarkStarters × (1 + gcpercent/100)
  
  Pacer 动态调整:
    - 如果 GC 耗时过长 → 降低目标 heap，更早触发 GC
    - 如果 GC 耗时过短 → 提高目标 heap，减少 GC 频率
    - 基于历史 GC 耗时做指数移动平均
```

### 2.5 GC 调优实战

```bash
# 查看 GC 日志
GOGC=off go run -gcflags="-m" app.go  # 关闭 GC，手动控制
GOGC=50 go run app.go                  # 50% 触发
GOGC=100 go run app.go                 # 默认 100%
GOGC=200 go run app.go                 # 200% 触发（更少 GC）

# 查看 GC 统计
runtime/debug.ReadGCStats()
GODEBUG=gctrace=1 go run app.go
```

```go
// 代码层面优化
import "runtime"

// 手动触发 GC
runtime.GC()

// 查看内存分配
runtime.NumGoroutine()  // 当前 goroutine 数
runtime.MemStats{}      // 内存统计

// 设置内存限制（Go 1.17+）
runtime.Gosched()       // 主动让出 CPU
```

---

## 3. Runtime 核心机制

### 3.1 网络轮询器（Netpoller）

```
Go 网络轮询器负责把 OS 网络 I/O 转化为 goroutine 调度

epoll/kqueue/IOCP 调用流程:
  1. goroutine 调用 sysmon
  2. sysmon 检查网络 poller 是否有 ready 事件
  3. 如果有，将对应的 goroutine 从 waiting 状态唤醒
  4. goroutine 被放入 P 的 runq，等待调度

关键函数:
  runtime·netpoll() — 检查网络事件（epoll_wait）
  runtime·netpollready() — 将 ready 的 goroutine 加入 runq
  runtime·netpollblock() — 阻塞等待网络事件
```

### 3.2 内存分配器

```
Go 内存分配器采用 Tcmalloc 风格：

层级结构:
  MallocCache (per-M 缓存)
    → MSpan (16 个 size class，对应不同对象大小)
      → MCache (per-P 缓存)
        → Span (物理页 8KB 的连续区域)

Size Classes:
  < 32B:    Tiny 对象（放在 span 开头，不占用 size class）
  32-1024B: 按 16B 递增（8 个 size class）
  1024-32768B: 按 256B 递增
  > 32768B: 直接分配 OS 页

分配流程:
  1. 从 P 的 mcache 取对应 size class 的 span
  2. 如果 mcache 满了，flush 到 mspan
  3. 如果 mspan 空了，从 mcentral 取新 span
  4. 如果 mcentral 空了，从 mheap 取 OS 页（2MB 大页）
  5. 如果 mheap 空了，brk/sbrk 向 OS 申请更多内存
```

### 3.3 sync.Mutex 源码分析

```go
// Mutex 结构
type Mutex struct {
    state int32  // 位域:
    // bit 0:       locked (1=locked, 0=unlocked)
    // bit 1-2:     semaphore (semaphore 信号量，用于阻塞)
    // bit 3-30:    waiter count (等待者数量)
    // bit 31:       wake (唤醒标记)
}

// Lock 流程（非竞争）:
func (m *Mutex) Lock() {
    // 快速路径：直接 CAS
    if atomic.CompareAndSwapInt32(&m.state, 0, mutexLocked) {
        return
    }
    // 慢路径：调用 asyncSafePoint
    m.lockSlow()
}

// lockSlow() 竞争处理:
func (m *Mutex) lockSlow() {
    // 1. 等待锁释放
    for !m.tryLockSlow() {
        // 2. 自旋（有限次数）
        for atomic.Load(&m.state) & mutexLocked != 0 {
            if isAsyncSafePoint() {
                // 3. 检查是否被唤醒
                if atomic.Load(&m.state) & mutexWake != 0 {
                    atomic.Xadd(&m.state, -mutexWake)
                }
            }
        }
    }
}
```

---

## 4. 性能剖析（pprof）实战

```bash
# CPU Profiling
go tool pprof http://localhost:6060/debug/pprof/profile?seconds=30

# Memory Profiling
go tool pprof http://localhost:6060/debug/pprof/heap

# Goroutine Profiling
go tool pprof http://localhost:6060/debug/pprof/goroutine

# Block Profiling
go tool pprof http://localhost:6060/debug/pprof/block

# 可视化
go tool pprof -http=:8080 cpu.prof

# 命令行分析
go tool pprof -top cpu.prof  # 按函数排序
go tool pprof -web cpu.prof  # 生成调用图
```

```go
// 代码中埋点
import _ "net/http/pprof"

// 在 main 中启动 pprof
go func() {
    log.Println(http.ListenAndServe("localhost:6060", nil))
}()
```

---

## 5. 常见坑与优化

### 5.1 Goroutine 泄漏

```go
// ❌ 泄漏: goroutine 等待 chan 永远没有人发送
go func() {
    ch := make(chan int)
    <-ch  // 没人 close ch，goroutine 永远阻塞
}()

// ✅ 修复: 用 context 控制
ctx, cancel := context.WithCancel(context.Background())
go func() {
    select {
    case <-ch:
        // 正常处理
    case <-ctx.Done():
        return  // 取消时退出
    }
}()
```

### 5.2 栈分配 vs 堆分配逃逸

```go
// ✅ 栈分配（不逃逸）:
func f() int {
    x := 100  // x 在栈上
    return x
}

// ❌ 堆分配（逃逸）:
func f() *int {
    x := 100  // x 逃逸到堆
    return &x  // 返回地址，编译器被迫逃逸
}

// 查看逃逸:
go build -gcflags="-m"
```

### 5.3 CPU Cache Line 优化

```go
// ❌ False Sharing: 两个变量在同一 Cache Line
type Bad struct {
    countA int64  // 可能在同一 cache line
    countB int64  // 与 countA 共享 cache line，导致缓存失效
}

// ✅ 修复: 用 padding 隔离
type Good struct {
    countA int64
    _      [cacheLineSize - 8]byte  // padding
    countB int64
}

const cacheLineSize = 64  // x86_64 cache line
```

---

*本文档基于 Go 源码（1.21+）整理，适用于有 Go 基础的工程师*
