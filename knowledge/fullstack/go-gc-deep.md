# Go 垃圾回收（GC）深度：三色标记/写屏障/并发 GC/调优实战

> 逐行源码解析 + 生产排障案例 + 对比分析 + 调优指南

---

## 第一部分：入门引导（5 分钟速览）

### 类比理解 GC

想象你在整理房间：

```
白色物品 = 从未使用过的东西（待扫描）
灰色物品 = 正在整理的东西（已扫描，物品待整理）
黑色物品 = 整理完的东西（已扫描，物品已整理）
垃圾 = 白色物品（没人引用，可以扔掉）

GC 过程：
1. 从房间入口（根对象）开始
2. 把看到的物品标灰
3. 整理灰色的物品，把它们引用的标灰
4. 整理完后标黑
5. 最后白色的就是垃圾，扔掉
```

### 为什么 Go 的 GC 延迟低？

```
传统 GC（Stop-The-World）:
所有 goroutine 暂停 → GC 执行 → 所有 goroutine 恢复
延迟：50-500ms（不可接受）

Go 并发 GC:
goroutine 继续运行 + GC 在后台运行
STW 时间：< 10μs（几乎感知不到）
```

---

## 第二部分：三色标记法（逐行解析）

### 2.1 三色标记原理

```
┌─────────────────────────────────────────────────────┐
│ 根对象（Root）                                       │
│   ├── 灰色对象 A → 白色对象 B                        │
│   │     ├── 灰色对象 B → 白色对象 C                  │
│   │     │     └── 黑色对象 D                        │
│   │     └── 黑色对象 E                               │
│   └── 黑色对象 F                                     │
│                                                      │
│ 最终：白色对象 C 被回收（不可达）                     │
│ 黑色对象 D/E/F 保留（可达）                           │
└─────────────────────────────────────────────────────┘
```

### 2.2 Go GC 源码级解析

```go
package gc

import (
    "fmt"
    "runtime"
    "sync/atomic"
    "unsafe"
)

// GCState 表示 GC 的不同阶段
type GCState int

const (
    GCOff GCState = iota    // GC 关闭
    GCStackScan               // 扫描 goroutine 栈
    GCHeapScan                // 扫描堆对象
    GCFinish                  // 完成 GC
)

// GoGC 控制 GC 的目标延迟
// GOGC=100 表示：当存活对象达到上次 GC 后分配对象数量的 100% 时触发 GC
// GOGC=0 表示：禁用 GC
// GOGC=200 表示：延迟 GC，直到存活对象达到 200%
var GoGC int32 = 100

// MemStats 内存统计
type MemStats struct {
    Alloc       uint64 // 当前分配的堆字节数
    TotalAlloc  uint64 // 累计分配的堆字节数
    Sys         uint64 // 从 OS 获取的总字节数
    Lookups     uint64 // 指针查找次数（通常为 0）
    Mallocs     uint64 // 堆对象分配次数
    Frees       uint64 // 堆对象释放次数
    HeapAlloc   uint64 // 当前分配的堆字节数（同 Alloc）
    HeapSys     uint64 // 从 OS 获取的堆字节数
    HeapIdle    uint64 // 空闲（未使用）的堆字节数
    HeapInuse   uint64 // 正在使用的堆字节数
    HeapReleased uint64 // 释放给 OS 的堆字节数
    HeapObjects uint64 // 堆对象数量
    NextGC      uint64 // 下一次 GC 的 HeapAlloc 目标值
    LastGC      uint64 // 上一次 GC 的时间（Unix 纳秒）
    PauseTotalNs uint64 // GC 暂停总时间
    PauseNs     [256]uint64 // 最近的 GC 暂停时间环形缓冲区
    NumGC       uint32  // GC 循环次数
}

// 关键公式：NextGC = HeapAlloc * (1 + GOGC/100)
// 当 HeapAlloc >= NextGC 时触发 GC
func ShouldTriggerGC(heapAlloc uint64, goGC int32) bool {
    if goGC == 0 {
        return false // GC 关闭
    }
    nextGC := heapAlloc * uint64(1+goGC/100)
    return heapAlloc >= nextGC
}

// 使用示例
func main() {
    // 查看当前 GC 状态
    var stats runtime.MemStats
    runtime.ReadMemStats(&stats)
    
    fmt.Printf("HeapAlloc: %d bytes\n", stats.HeapAlloc)
    fmt.Printf("HeapInuse: %d bytes\n", stats.HeapInuse)
    fmt.Printf("HeapIdle: %d bytes\n", stats.HeapIdle)
    fmt.Printf("NextGC: %d bytes\n", stats.NextGC)
    fmt.Printf("NumGC: %d\n", stats.NumGC)
    fmt.Printf("PauseTotalNs: %d ns\n", stats.PauseTotalNs)
    
    // 触发手动 GC
    runtime.GC()
    
    // 查看 GC 暂停时间
    fmt.Printf("Last GC pause: %d ns\n", stats.PauseNs[stats.NumGC%256])
}
```

### 2.3 写屏障（Write Barrier）— 为什么需要它？

**核心问题**：并发 GC 时，goroutine 可能在 GC 扫描过程中修改指针

```
场景：GC 正在扫描灰色对象 A

时间线：
T1: GC 看到 A 引用 B（白色）→ 将 B 标灰
T2: goroutine 执行 A.B = C（C 原来是 A 的子对象，现在是黑色）
T3: GC 继续扫描，发现 B 没有引用 C 了 → C 被错误回收！

这就是"漏标"问题！
```

**解决方案**：写屏障 — 在每次指针赋值时通知 GC

```go
// 写屏障伪代码
// 在每次指针赋值时插入这段代码

func writeBarrier(obj **interface{}, newVal interface{}) {
    // 1. 如果 newVal 是白色对象
    if isNewObject(newVal) {
        // 2. 将 newVal 标为灰色
        markGray(newVal)
    }
    
    // 3. 如果 obj 指向的黑色对象
    oldVal := *obj
    if isBlack(oldVal) {
        // 4. 将 oldVal 重新标灰（混合写屏障）
        markGray(oldVal)
    }
    
    // 5. 执行实际的指针赋值
    *obj = newVal
}

// Go 使用混合写屏障（Hybrid Write Barrier）
// 结合了强屏障和弱屏障的优点
// 强屏障：确保新对象被标记
// 弱屏障：只在 STW 时处理特殊情况
```

### 2.4 四种屏障对比

| 屏障类型 | 优点 | 缺点 | 适用场景 |
|---------|------|------|---------|
| **Stepping** | 简单 | 需要 STW | 不适用 |
| **Strong** | 正确性最好 | 开销大 | 不适用 |
| **Weak** | 开销小 | 需要额外处理 | 不适用 |
| **Hybrid** | 正确+高效 | 实现复杂 | **Go 使用** |

```go
// Go 的 Hybrid Write Barrier 实现
// 来源：src/runtime/mgc.go

// go:linkname 用于内部调用
//go:linkname writebarrierptr

func writebarrierptr(p *unsafe.Pointer, val unsafe.Pointer) {
    // 1. 检查 GC 是否在运行
    if gcphase == GCMark {
        // 2. 如果 val 是新分配的对象，标记为 whiteToBlack
        if val != nil && isObjWhite(val) {
            whiteToBlack(val)
        }
        // 3. 标记 p 指向的对象为 black
        if *p != nil {
            blacken(*p)
        }
    }
    // 4. 执行实际的指针赋值
    *p = val
}
```

---

## 第三部分：并发 GC 流程

### 3.1 GC 三个阶段

```
┌─────────────────────────────────────────────────────┐
│ 阶段 1: GC 初始化 (STW)                              │
│ - 标记所有 goroutine 为 GC 栈扫描                     │
│ - 初始化标记数据结构                                  │
├─────────────────────────────────────────────────────┤
│ 阶段 2: 并发标记 (Concurrent Mark)                   │
│ - 后台 worker 扫描堆对象                              │
│ - goroutine 继续运行 + 执行写屏障                    │
│ - 直到所有对象都被标记                                │
├─────────────────────────────────────────────────────┤
│ 阶段 3: 终止阶段 (STW)                               │
│ - 停止所有 goroutine                                 │
│ - 处理写屏障留下的"脏"数据                           │
│ - 标记结束，准备 sweep                               │
├─────────────────────────────────────────────────────┤
│ 阶段 4: 并发清扫 (Concurrent Sweep)                  │
│ - 后台 worker 回收白色对象                            │
│ - goroutine 继续运行                                  │
│ - 释放内存回 OS                                      │
└─────────────────────────────────────────────────────┘
```

### 3.2 源码级实现

```go
package gc

import (
    "runtime"
    "sync/atomic"
)

// GCWorker GC 后台工作线程
type GCWorker struct {
    id        int
    state     GCState
    workCount int64
    totalWork int64
}

// MarkWorker 标记工作线程
type MarkWorker struct {
    gcw *gclinkptr
}

// SweepWorker 清扫工作线程
type SweepWorker struct {
    freed uint64
}

// 启动 GC
func StartGC() {
    // 阶段 1: STW 初始化
    stopTheWorld("GC phase init")
    
    gcPhase = GCMark
    gcBgMarkStartWorkers()  // 启动后台标记
    gcMarkRootPrepare()      // 准备标记根
    
    startTheWorld()
    
    // 阶段 2: 并发标记
    // goroutine 继续运行，写屏障在运行
    // 后台 worker 扫描堆对象
    
    // 阶段 3: STW 终止
    stopTheWorld("GC mark termination")
    gcMarkDone()             // 标记完成
    startTheWorld()
    
    // 阶段 4: 并发清扫
    // goroutine 继续运行
    // 后台 worker 回收白色对象
    startSweepers()
}

// 关键：STW 时间为什么这么短？
// 1. 只停止需要扫描的 goroutine 栈
// 2. 堆扫描是并发的
// 3. 终止阶段只需要处理写屏障留下的数据
// 4. 通常 < 10μs
```

---

## 第四部分：GC 调优实战

### 4.1 调优参数

```bash
# 查看当前 GC 设置
go env GOGC

# 设置 GOGC=200（延迟 GC，直到堆翻倍）
export GOGC=200

# 设置 GOGC=50（激进 GC，堆增长 50% 就触发）
export GOGC=50

# 禁用 GC（不推荐生产环境）
export GOGC=0
```

### 4.2 调优策略

```go
package tuning

import (
    "runtime"
    "fmt"
)

// 场景 1: 低延迟要求（竞价服务）
func tuneForLowLatency() {
    // GOGC=25: 激进 GC，减少内存占用，降低 STW 时间
    runtime.GC()
    
    // 监控 GC 暂停时间
    var stats runtime.MemStats
    runtime.ReadMemStats(&stats)
    
    fmt.Printf("GC pause: %d ns\n", stats.PauseNs[stats.NumGC%256])
    fmt.Printf("GC frequency: %d times\n", stats.NumGC)
    
    // 如果 GC 太频繁，可以提高 GOGC
    // 如果 STW 太长，可以降低 GOGC
}

// 场景 2: 高吞吐要求（日志收集）
func tuneForHighThroughput() {
    // GOGC=200: 延迟 GC，减少 GC 频率，提高吞吐
    // 代价：内存占用更高
    runtime.GC()
    
    var stats runtime.MemStats
    runtime.ReadMemStats(&stats)
    
    fmt.Printf("HeapAlloc: %d MB\n", stats.HeapAlloc/1024/1024)
    fmt.Printf("HeapInuse: %d MB\n", stats.HeapInuse/1024/1024)
    fmt.Printf("HeapIdle: %d MB\n", stats.HeapIdle/1024/1024)
    
    // HeapIdle 太大 → 释放内存给 OS
    // runtime.GC() 会自动触发
}

// 场景 3: 内存受限（容器环境）
func tuneForMemoryConstraint() {
    // 1. 设置 GOGC=25 激进 GC
    // 2. 使用 GOMEMLIMIT 限制内存（Go 1.16+）
    // 3. 监控内存使用
    
    var stats runtime.MemStats
    runtime.ReadMemStats(&stats)
    
    // 如果内存使用超过限制，触发 GC
    limit := int64(512) * 1024 * 1024 // 512MB
    if int64(stats.HeapAlloc) > limit {
        runtime.GC()
    }
}
```

### 4.3 常见 GC 问题排查

```
问题 1: GC 太频繁
症状：CPU 使用率高，QPS 下降
原因：GOGC 太低，或者内存分配太快
解决：提高 GOGC，优化内存分配

问题 2: GC 暂停时间长
症状：P99 延迟飙升
原因：堆太大，或者写屏障开销高
解决：降低 GOGC，减少大对象分配

问题 3: 内存泄漏
症状：HeapAlloc 持续增长，GC 后不释放
原因：全局变量引用，goroutine 泄漏
解决：pprof heap profile 分析
```

---

## 第五部分：生产排障案例

### 5.1 GC 导致的 P99 延迟飙升

```
现象：竞价服务 P99 延迟从 50ms 飙升到 500ms

排查：
1. pprof profile -cpu=10s -output=cpu.pprof
2. go tool pprof cpu.pprof
3. top 10 函数 → 发现 runtime.gcBgMarkWorker
4. 检查 GC 频率 → NumGC 很高
5. 检查 GOGC → 默认 100

根因：每次 GC 都触发大量对象分配，导致 GC 频繁
```

```go
// 修复前：每次请求都创建新对象
func processBid(req *BidRequest) (*BidResponse, error) {
    // ❌ 每次请求都创建新的 slice
    tags := make([]string, 0)
    tags = append(tags, "sports")
    tags = append(tags, "outdoor")
    
    // ❌ 每次都创建新的 map
    targeting := make(map[string]string)
    targeting["age"] = "25-35"
    targeting["gender"] = "M"
    
    return &BidResponse{Tags: tags, Targeting: targeting}, nil
}

// 修复后：使用对象池
var tagPool = sync.Pool{
    New: func() interface{} {
        return make([]string, 0, 10)
    },
}

var targetingPool = sync.Pool{
    New: func() interface{} {
        return make(map[string]string, 5)
    },
}

func processBid(req *BidRequest) (*BidResponse, error) {
    // ✅ 从对象池获取
    tags := tagPool.Get().([]string)
    tags = tags[:0]
    tags = append(tags, "sports", "outdoor")
    defer tagPool.Put(tags)
    
    targeting := targetingPool.Get().(map[string]string)
    for k := range targeting {
        delete(targeting, k)
    }
    targeting["age"] = "25-35"
    targeting["gender"] = "M"
    defer targetingPool.Put(targeting)
    
    return &BidResponse{Tags: tags, Targeting: targeting}, nil
}
```

### 5.2 内存泄漏排查

```
现象：服务内存使用持续增长，GC 后不释放

排查步骤：
1. pprof heap -inuse_space -output=heap.pprof
2. go tool pprof heap.pprof
3. top 10 → 发现某个 map 持续增长
4. trace → 发现 goroutine 泄漏
```

```go
// 泄漏原因：goroutine 没有正确退出
func leakyWorker() {
    ch := make(chan int)
    
    go func() {
        for i := range ch {
            fmt.Println(i)
        }
    }()
    
    ch <- 1
    // ❌ ch 永远不会被关闭，goroutine 永远运行
}

// 修复：确保 channel 关闭
func safeWorker() {
    ch := make(chan int)
    
    go func() {
        defer close(ch)
        for i := 0; i < 10; i++ {
            ch <- i
        }
    }()
    
    for v := range ch {
        fmt.Println(v)
    }
}
```

---

## 第六部分：自测题

### 问题 1
Go GC 为什么比其他语言的 GC 延迟低？

<details>
<summary>查看答案</summary>

1. **并发标记**：goroutine 和 GC 并行运行
2. **混合写屏障**：兼顾正确性和性能
3. **STW 时间短**：只停栈扫描，不停堆扫描
4. **GOGC 可调**：按需调整 GC 频率
5. **Pacer 算法**：自动调整 GC 频率

</details>

### 问题 2
写屏障为什么能解决并发 GC 的漏标问题？

<details>
<summary>查看答案</summary>

1. **指针赋值时通知 GC**：新对象被标记
2. **黑色对象被引用时重新标灰**：防止漏标
3. **混合写屏障**：STW 时处理特殊情况
4. **开销小**：只在指针赋值时插入
5. **Go 实现**：writebarrierptr

</details>

### 问题 3
GOGC=100 是什么意思？

<details>
<summary>查看答案</summary>

1. **含义**：堆增长 100% 时触发 GC
2. **计算公式**：NextGC = HeapAlloc × (1 + GOGC/100)
3. **GOGC=0**：禁用 GC
4. **GOGC=200**：延迟 GC，堆翻倍才触发
5. **调优**：低延迟用 25-50，高吞吐用 200-400

</details>

---

*本文档基于 Go GC 源码和生产实战整理，包含逐行解析、排障案例、对比分析。*