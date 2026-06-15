# Go 进阶：内存分配器/垃圾回收/锁优化

> TCMalloc 实现/GC 三色标记/自旋锁/Futex

---

## 第一部分：入门引导（5 分钟速览）

### Go 性能优化的三大方向

```
内存分配 → TCMalloc 变种，减少锁竞争
垃圾回收 → 三色标记 + 写屏障，低延迟
锁优化 → 自旋锁 + Futex，减少阻塞
```

---

## 第二部分：内存分配器深度

### 2.1 TCMalloc 架构

```
Malloc:
┌───────────────────────────────────────┐
│ Thread Caches (P.mcache)              │
│ ├─ Span (2KB)                         │
│ ├─ Span (4KB)                         │
│ ├─ Span (8KB)                         │
│ └─ Span (64KB)                        │
├───────────────────────────────────────┤
│ Central Free Lists (P.mcentral)       │
│ ├─ FreeList (2KB)                     │
│ ├─ FreeList (4KB)                     │
│ └─ FreeList (64KB)                    │
├───────────────────────────────────────┤
│ Spans (physical memory pages)         │
└───────────────────────────────────────┘
```

### 2.2 Go 内存分配实现

```go
package mimalloc

import (
    "runtime"
    "sync/atomic"
    "unsafe"
)

// mspan 内存块
type mspan struct {
    next  *mspan      // 下一个 span
    prev  *mspan      // 上一个 span
    base  uintptr     // 起始地址
    limit uintptr     // 结束地址
    npages uintptr     // 页数
    free  uintptr     // 空闲位置
}

// mcache 线程本地缓存
type mcache struct {
    small   [numSmallSizeClasses]*mspan  // 小对象缓存
    large   map[uintptr]*mspan            // 大对象缓存
}

// mcentral 全局中央列表
type mcentral struct {
    locks   mutex
    free    [numSmallSizeClasses]freelist // 空闲链表
    nonempty uintptr                     // 非空计数
}

// Malloc 分配
func (c *mcache) Malloc(size uintptr) unsafe.Pointer {
    // 1. 确定大小类
    class := sizeToClass(size)
    
    // 2. 从线程缓存获取
    if sp := c.small[class]; sp != nil && sp.free != 0 {
        addr := sp.free
        sp.free = *(*(uintptr)(unsafe.Pointer(addr)))
        return unsafe.Pointer(addr)
    }
    
    // 3. 从中央列表获取
    sp := c.central[class].Alloc()
    if sp != nil {
        c.small[class] = sp
        addr := sp.free
        sp.free = *(*(uintptr)(unsafe.Pointer(addr)))
        return unsafe.Pointer(addr)
    }
    
    // 4. 从 OS 获取新内存
    sp = c.growSpan(size)
    c.small[class] = sp
    addr := sp.free
    sp.free = *(*(uintptr)(unsafe.Pointer(addr)))
    return unsafe.Pointer(addr)
}

// Free 释放
func (c *mcache) Free(ptr unsafe.Pointer, size uintptr) {
    class := sizeToClass(size)
    
    // 1. 放回线程缓存
    if c.small[class] == nil {
        // 2. 放回中央列表
        c.central[class].Free(ptr)
    } else {
        // 3. 放回线程缓存
        sp := c.small[class]
        *(*(uintptr)(ptr)) = sp.free
        sp.free = uintptr(ptr)
    }
}
```

### 2.3 对象池优化

```go
// 使用 sync.Pool 减少分配
type BidRequest struct {
    ImpressionID string
    UserID       string
    Budget       float64
}

var bidReqPool = sync.Pool{
    New: func() interface{} {
        return &BidRequest{}
    },
}

func GetBidRequest() *BidRequest {
    return bidReqPool.Get().(*BidRequest)
}

func PutBidRequest(req *BidRequest) {
    req.ImpressionID = ""
    req.UserID = ""
    req.Budget = 0
    bidReqPool.Put(req)
}

// 预分配缓冲区
type BufferPool struct {
    pools [8]*sync.Pool  // 不同大小
}

func (bp *BufferPool) Get(size int) []byte {
    idx := size / 1024
    if idx >= len(bp.pools) {
        idx = len(bp.pools) - 1
    }
    return bp.pools[idx].Get().([]byte)
}

func (bp *BufferPool) Put(buf []byte) {
    idx := len(buf) / 1024
    if idx >= len(bp.pools) {
        idx = len(bp.pools) - 1
    }
    bp.pools[idx].Put(buf)
}
```

---

## 第三部分：垃圾回收深度

### 3.1 三色标记法

```
白色 (White): 未被 GC 扫描
灰色 (Gray): 已被扫描，子对象待扫描
黑色 (Black): 已扫描，子对象已扫描

流程:
1. 将所有对象标记为白色
2. 从根对象开始，将可达对象标记为灰色
3. 扫描灰色对象，将子对象标记为灰色，自身变为黑色
4. 重复直到没有灰色对象
5. 白色对象不可达，回收
```

### 3.2 写屏障

```go
// 写屏障：在赋值时通知 GC

// 黑色指针 → 白色对象：禁止！
// 灰色指针 → 白色对象：允许，标记灰色
// 灰色指针 → 黑色对象：允许
// 白色指针 → 白色对象：允许，标记灰色

// Go 实现写屏障
func writeBarrier(obj **interface{}, newVal interface{}) {
    // 1. 检查新对象是否已标记
    if !isMarked(newVal) {
        // 2. 标记为新对象
        mark(newVal)
    }
    
    // 3. 检查旧对象
    oldVal := *obj
    if oldVal != nil && isMarked(oldVal) {
        // 4. 旧对象可能变为不可达
        // 在最终标记阶段处理
    }
    
    // 5. 赋值
    *obj = newVal
}
```

### 3.3 GC 调优

```go
// 查看当前 GC 设置
fmt.Println("GOGC:", os.Getenv("GOGC"))  // 默认 100

// 调整 GC 目标延迟
runtime.GC()  // 手动触发

// 监控 GC 统计
var stats runtime.MemStats
runtime.ReadMemStats(&stats)
fmt.Printf("GC runs: %d\n", stats.NumGC)
fmt.Printf("GC pause: %v\n", stats.PauseTotalNs)

// 广告平台 GC 调优
// 1. 减少临时对象分配
// 2. 使用对象池
// 3. 避免大对象分配
// 4. 使用 []byte 替代 string
// 5. 预分配 slice 容量

func optimizeBidRequest(req *BidRequest) {
    // ❌ 低效：每次创建新 slice
    tags := make([]string, 0)
    tags = append(tags, "sports")
    tags = append(tags, "outdoor")
    
    // ✅ 高效：预分配容量
    tags := make([]string, 0, 10)
    tags = append(tags, "sports")
    tags = append(tags, "outdoor")
}
```

---

## 第四部分：锁优化

### 4.1 自旋锁

```go
type SpinLock struct {
    state int32 // 0 = unlocked, 1 = locked
}

func (sl *SpinLock) Lock() {
    for !atomic.CompareAndSwapInt32(&sl.state, 0, 1) {
        // 自旋等待
        runtime.Gosched() // 让出时间片
    }
}

func (sl *SpinLock) Unlock() {
    atomic.StoreInt32(&sl.state, 0)
}

// 自旋锁 vs 互斥锁
// 自旋锁：适合短临界区（< 100ns），避免上下文切换
// 互斥锁：适合长临界区，会阻塞等待
```

### 4.2 Futex 实现

```go
type Futex struct {
    key int32
    waiters int32
}

// futex 系统调用
// SYS_futex(addr, OP, val, timeout, addr2, val3)
// OP: FUTEX_WAIT, FUTEX_WAKE, FUTEX_REQUEUE

func (f *Futex) Wait() {
    for atomic.LoadInt32(&f.waiters) == 0 {
        // 没有等待者，快速返回
        return
    }
    
    // FUTEX_WAIT: 如果 val == *addr, 进入休眠
    // 如果 val != *addr, 立即返回 EAGAIN
    syscall.Syscall6(
        SYS_FUTEX,
        uintptr(unsafe.Pointer(&f.key)),
        FUTEX_WAIT,
        0,  // val
        0,  // timeout
        0,  // addr2
        0,  // val3
    )
}

func (f *Futex) Wake() {
    // FUTEX_WAKE: 唤醒最多 val 个等待者
    atomic.StoreInt32(&f.waiters, 1)
    syscall.Syscall6(
        SYS_FUTEX,
        uintptr(unsafe.Pointer(&f.key)),
        FUTEX_WAKE,
        1,  // val: 唤醒 1 个
        0,
        0,
        0,
    )
}
```

### 4.3 sync.RWMutex 优化

```go
// 写多读少：用 sync.Mutex
// 读多写少：用 sync.RWMutex
// 无竞争：用 atomic

type OptimizedCounter struct {
    count   atomic.Int64
    mu      sync.Mutex
    snapshot int64
}

func (c *OptimizedCounter) Incr() {
    c.count.Add(1)
}

func (c *OptimizedCounter) GetSnapshot() int64 {
    c.mu.Lock()
    defer c.mu.Unlock()
    
    c.snapshot = c.count.Load()
    return c.snapshot
}

// 分片锁减少竞争
type ShardedLock struct {
    shards []shard
    mask   uint64
}

type shard struct {
    mu   sync.Mutex
    data map[string]int64
}

func (sl *ShardedLock) Incr(key string) {
    idx := sl.hash(key) & sl.mask
    sl.shards[idx].mu.Lock()
    sl.shards[idx].data[key]++
    sl.shards[idx].mu.Unlock()
}
```

---

## 第五部分：自测题

### 问题 1
Go GC 为什么延迟低？

<details>
<summary>查看答案</summary>

1. **三色标记**：并行标记，减少 STW
2. **写屏障**：保证标记正确性
3. **混合屏障**：兼顾吞吐和延迟
4. **GOGC 可调**：按需调整
5. **Go 实现**：runtime.mgc.go

</details>

### 问题 2
TCMalloc 相比 malloc 有什么优势？

<details>
<summary>查看答案</summary>

1. **线程缓存**：减少锁竞争
2. **大小类**：固定大小分配，避免碎片
3. **Central Lists**：跨线程共享
4. **O(1) 分配**：常数时间
5. **Go 实现**：runtime.malloc.go

</details>

### 问题 3
什么时候用原子操作，什么时候用锁？

<details>
<summary>查看答案</summary>

1. **原子操作**：简单计数器，无复杂逻辑
2. **锁**：需要保证多个操作的原子性
3. **性能**：无竞争时原子操作更快
4. **复杂度**：原子操作适合简单场景
5. **Go 实现**：sync/atomic vs sync.Mutex

</details>

---

*本文档基于 Go 底层原理整理。*