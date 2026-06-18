# Go 运行时深度：GMP 调度/内存管理/GC 源码级

> 从 runtime 源码逐行解析 Go 调度器、内存管理和 GC 机制

---

## 第一部分：GMP 调度器源码深度

### GMP 架构

```
Go 调度器模型：G-M-P
┌─────────────────────────────────────────────────────────────────────┐
│ OS Thread (M)                                                        │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │ P (Processor)                                                   │ │
│  │                                                                 │ │
│  │  runq[] (Local Run Queue) - 最多 256 个 Goroutine               │ │
│  │  ├── G1 (ready)                                               │ │
│  │  ├── G2 (ready)                                               │ │
│  │  └── G3 (ready)                                               │ │
│  │                                                                 │ │
│  │  gfree[] (Free list - 空闲 Goroutine)                           │ │
│  │                                                                 │ │
│  │  schedtick (调度计数器)                                        │ │
│  │  sysmontick (系统监控 tick)                                    │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│                                                                        │
│  Goroutine (G):                                                      │
│  ├── stack [0-4GB] (初始 2KB, 动态伸缩)                               │ │
│  ├── sched (上下文保存: SP, PC, BP)                                   │ │
│  ├── goid (唯一 ID)                                                  │ │
│  ├── status (Gidle/Grunning/Gwaiting/Gsyscall/Gpreamble)             │ │
│  ├── param (用户参数)                                                │ │
│  └── atomicstatus                                                  │ │
└─────────────────────────────────────────────────────────────────────┘

全局队列：
• runq: 全局 goroutine 队列（当 P 本地队列满 256 时）
• gfree: 全局空闲 goroutine 链表
• netpoll: 网络事件就绪队列
```

### schedule 源码逐行解析

```c
// Go 源码：src/runtime/proc.go - schedule
func schedule(_g_ *g) {
    var gp *g
    var inheritTime bool
    
    // 1. 检查是否需要 GC 工作
    if (gcBlackenEnabled != 0) {
        gp = gcController.findRunnableGCWorker(_g_, inheritTime)
        if gp != nil {
            execute(gp, inheritTime)
        }
    }
    
    // 2. 从当前 P 的本地队列获取 G
    if gp == nil {
        gp, inheritTime = runqgrab(_g_.m.p)
        if gp == nil {
            // 3. 本地队列为空，从全局队列获取
            gp = globrunqget(_g_.m.p, 1)
        }
        if gp == nil {
            // 4. 全局队列也为空，尝试偷取其他 P 的 G
            gp = findrunnable()
        }
    }
    
    if gp == nil {
        // 5. 没有任何 G 可执行，进入 idle 状态
        mcall(goschedImpl)
        return
    }
    
    // 6. 切换到 G
    if trace.enabled {
        traceGoStart(gp)
    }
    
    // 7. 保存当前 G 的上下文，切换到目标 G
    gosched_impl(gp, _g_)
}

// runqgrab 从 P 的本地队列窃取最多 half 个 G
func runqgrab(_p_ *p) (*g, bool) {
    var gp *g
    var stealTime bool
    
    // 1. 获取本地队列长度
    n := runqgrablen(_p_)
    if n == 0 {
        return nil, false
    }
    
    // 2. 窃取一半（避免 P 饥饿）
    n = n / 2
    if n == 0 {
        n = 1
    }
    
    // 3. 从队尾窃取（减少竞争）
    for i := uint32(0); i < n; i++ {
        gp = _p_.runq[_p_.runqhead + i]
        if gp != nil {
            _p_.runqhead = (_p_.runqhead + 1) % uint32(len(_p_.runq))
        }
    }
    
    return gp, stealTime
}

// findrunnable 寻找可执行的 G
func findrunnable() *g {
    _g_ := getg()
    _p_ := _g_.m.p.get()
    
    // 1. 检查网络事件
    if netpollinited() {
        gp := netpoll(false)  // non-blocking
        if gp != nil {
            return gp
        }
    }
    
    // 2. 从全局队列获取
    gp := globrunqget(_p_, 1)
    if gp != nil {
        return gp
    }
    
    // 3. 从其他 P 偷取（work stealing）
    for i := 0; i < 4; i++ {
        start := int(allp[nrand()%uint32(len(allp))])
        for j := 0; j < 4; j++ {
            p := allp[start+j%len(allp)]
            if p == _p_ || p == nil {
                continue
            }
            gp := runqgrab(p)
            if gp != nil {
                return gp
            }
        }
    }
    
    // 4. GC 工作
    if gcBlackenEnabled != 0 {
        gp := gcController.findRunnableGCWorker(_g_, false)
        if gp != nil {
            return gp
        }
    }
    
    // 5. 没有可执行的 G，挂起当前 M
    if ioStop() {
        stopm()
        return findrunnable()
    }
    
    return nil
}
```

---

## 第二部分：内存管理源码深度

### 内存分配架构

```
Go 内存管理层次：
┌─────────────────────────────────────────────────────────────────────┐
│ Malloc (malloc.go)                                                  │
│  ├── mallocgc: 分配对象                                              │
│  ├── free: 释放对象                                                 │
│  └── newobject: 分配零值对象                                         │
│                                                                     │
│ Span (mspan.go)                                                     │
│  ├── span: 连续内存块（由 page 组成）                                 │
│  ├── spanclass: 大小类（128 种）                                     │
│  │   ├── size class 0: 8 bytes                                     │
│  │   ├── size class 1: 16 bytes                                    │
│  │   ├── ...                                                       │
│  │   └── size class 127: 32768 bytes                               │
│  └── alloc: 从 span 中分配对象                                       │
│                                                                     │
│ MHeap (mheap.go)                                                    │
│  ├── heaps: 内存堆（包含所有 span）                                   │
│  ├── free: 空闲 span 链表                                           │
│  └── sweep: 清扫线程                                               │
│                                                                     │
│ MCache (mcache.go)                                                  │
│  ├── local: 每个 P 的本地缓存                                       │
│  ├── spans: span 数组（按 spanclass 索引）                           │
│  └── cache: 小对象缓存                                             │
└─────────────────────────────────────────────────────────────────────┘

内存分配策略：
1. 小对象 (< 32KB): MCache → MSpan → MHeap → OS
2. 大对象 (>= 32KB): MHeap → OS mmap
3. 超大对象: mmap + 对齐到页边界
```

### mallocgc 源码逐行解析

```c
// Go 源码：src/runtime/malloc.go - mallocgc
func mallocgc(size uintptr, typ *_type, needzero bool) unsafe.Pointer {
    _g_ := getg()
    
    // 1. 检查是否是零大小对象
    if size == 0 {
        return unsafe.Pointer(&zerobase)
    }
    
    // 2. 确定大小类
    var sizeclass uint8
    if size <= maxSmallSize {
        sizeclass = size_to_class8((size + smallSizeDiv - 1) / smallSizeDiv)
    } else {
        sizeclass = size_to_class128((size + largeSizeDiv - 1) / largeSizeDiv)
    }
    
    // 3. 获取对象实际大小
    var spansize uintptr
    if sizeclass != 0 {
        spansize = class_to_size[sizeclass]
    } else {
        spansize = roundUp(size, PageSize)
    }
    
    // 4. 检查是否需要分配
    if spansize > maxMHeapMapped {
        throw("object too large")
    }
    
    // 5. 小对象：从 MCache 分配
    if size <= maxSmallSize {
        _p_ := _g_.m.p.get()
        if _p_ == nil {
            throw("mallocgc: no P")
        }
        
        mc := _p_.mcache
        
        // 5.1 检查 MCache 是否有空间
        if mc.freelist[sizeclass].empty() {
            // 5.2 从 MHeap 获取新 span
            span := mheap_.allocSmall(sizeclass)
            if span == nil {
                // 5.3 需要从 OS 分配新 span
                span = mheap_.alloc(sizeclass, _p_.id)
                if span == nil {
                    throw("out of memory")
                }
                // 5.4 将 span 放入 MCache
                mc.cache_alloc(span)
            }
        }
        
        // 5.5 从 MCache 分配对象
        obj := mc.nextFree(sizeclass)
        
        // 5.6 清零（如果需要）
        if needzero && obj != nil {
            memclrNoHeapPointers(obj, spansize)
        }
        
        return obj
    }
    
    // 6. 大对象：直接从 MHeap 分配
    if spansize > maxMHeapMapped {
        throw("object too large")
    }
    
    // 6.1 从 MHeap 分配
    span := mheap_.allocLarge(size, _g_.m.mcache)
    if span == nil {
        throw("out of memory")
    }
    
    // 6.2 清零
    if needzero {
        memclrNoHeapPointers(span.base(), spansize)
    }
    
    return span.base()
}
```

### mcache_nextFree 源码逐行解析

```c
// Go 源码：src/runtime/mcache.go - nextFree
func (mc *mcache) nextFree(spc spanClass) unsafe.Pointer {
    s := mc.spans[spc]
    
    // 1. 检查 span 是否过期
    if s.refcount != 0 {
        throw("nextFree: bad reference count")
    }
    
    // 2. 检查 span 是否已满
    if s.freeindex >= s.nelems {
        // 2.1 从 MHeap 获取新 span
        mc.grow(spc)
        s = mc.spans[spc]
    }
    
    // 3. 分配对象
    obj := unsafe.Pointer(s.base() + s.freeindex*s.elemsize)
    
    // 4. 更新 freeindex
    s.freeindex++
    
    // 5. 如果 span 已满，标记为 full
    if s.freeindex >= s.nelems {
        s.state = mSpanFull
        mheap_.freeSpan(s)
    }
    
    return obj
}

// grow 从 MHeap 获取新 span
func (mc *mcache) grow(spc spanClass) {
    // 1. 从 MHeap 获取新 span
    s := mheap_.allocSmall(spc)
    if s == nil {
        throw("out of memory")
    }
    
    // 2. 重置 span
    s.freeindex = 1
    s.nelems = s.allocCount
    
    // 3. 放入 MCache
    mc.spans[spc] = s
}
```

---

## 第三部分：GC 源码深度

### Tri-color Mark Sweep 算法

```
三色标记法：
┌─────────────────────────────────────────────────────────────────────┐
│ 白色 (White) - 未被标记，可能是垃圾                                  │
│ 灰色 (Gray) - 已被标记，但其引用的对象尚未完全标记                     │
│ 黑色 (Black) - 已被标记，且其引用的对象已全部标记                      │
│                                                                     │
│ 规则：                                                              │
│ 1. 根对象（全局变量、栈变量）→ 灰色                                   │
│ 2. 灰色对象的引用对象 → 灰色                                         │
│ 3. 灰色对象处理完所有引用 → 黑色                                     │
│ 4. 白色对象在 GC 结束时仍存在 → 垃圾                                  │
│                                                                     │
│ 写屏障 (Write Barrier)：                                            │
│ • 插入屏障：赋值时，将新对象标记为灰色                                 │
│ • 删除屏障：删除引用时，将旧对象重新标记为灰色                         │
└─────────────────────────────────────────────────────────────────────┘

Go GC 阶段：
1. STW Mark Initiation: 标记开始，STW
2. Concurrent Mark: 并发标记（与用户 goroutine 并行）
3. STW Mark Termination: 标记结束，STW
4. Concurrent Sweep: 并发清扫（与用户 goroutine 并行）
5. STW Sweep Termination: 清扫结束，STW
```

### gcStart 源码逐行解析

```c
// Go 源码：src/runtime/mgc.go - gcStart
func gcStart(gcTrigger) {
    _g_ := getg()
    
    // 1. STW: 标记开始
    gcMarkStart()
    
    // 2. 启动标记 worker goroutines
    for i := 0; i < gomaxprocs; i++ {
        gp := gfget()
        if gp == nil {
            throw("no free G")
        }
        gp.status = Grunning
        gp.gopc = 0
        gp.arg = nil
        gp.argp = unsafe.Pointer(&gp.gopc)
        gp.pc = 0
        gp.sp = 0
        gp.sched = _g_.sched
        
        // 启动标记 goroutine
        go gcMarkWorker(i)
    }
    
    // 3. 等待所有标记 worker 完成
    gcWaitOnMark()
    
    // 4. STW: 标记结束
    gcMarkDone()
    
    // 5. 启动清扫 goroutine
    for i := 0; i < gomaxprocs; i++ {
        go gcSweepWorker(i)
    }
    
    // 6. 等待清扫完成
    gcWaitOnSweep()
    
    // 7. STW: 清扫结束
    gcSweepDone()
}

// gcMarkWorker 标记 worker
func gcMarkWorker(work uint32) {
    // 1. 获取标记工作单元
    for {
        // 1.1 从全局队列获取标记工作
        gp := gcDrain(nil)
        if gp == nil {
            break
        }
        
        // 1.2 标记该对象及其引用
        markObject(gp)
    }
}

// gcDrain 从队列中获取标记工作
func gcDrain(_p_ *p) bool {
    // 1. 从全局灰色队列获取
    gp := gcw.popGrey()
    if gp != nil {
        return true
    }
    
    // 2. 从 P 本地灰色队列获取
    if _p_ != nil {
        gp = _p_.gcw.popGrey()
        if gp != nil {
            return true
        }
    }
    
    // 3. 尝试从其他 P 偷取
    for i := 0; i < 4; i++ {
        start := int(nrand() % uint32(len(allp)))
        for j := 0; j < 4; j++ {
            p := allp[start+j%len(allp)]
            if p == _p_ || p == nil {
                continue
            }
            gp = p.gcw.popGrey()
            if gp != nil {
                return true
            }
        }
    }
    
    return false
}
```

---

## 第四部分：自测题

### Q1: GMP 调度器和线程池的区别？

**A**:
| 维度 | GMP 调度器 | 线程池 |
|------|-----------|--------|
| 调度层级 | 用户态调度 | 内核态调度 |
| 上下文切换 | 轻量（无系统调用） | 重量（需系统调用） |
| Goroutine 数量 | 百万级 | 千级 |
| 工作窃取 | 支持 | 不支持 |
| 阻塞处理 | M 阻塞时 P 创建新 M | 线程阻塞需等待 |

### Q2: Go GC 为什么是并发标记清扫？

**A**: 传统标记清扫需要 STW（Stop The World），导致停顿时间长。Go 采用并发标记清扫，标记和清扫都与用户 goroutine 并行，STW 时间极短（通常 < 1ms）。

### Q3: 内存分配中 MCache/MHeap/MSpan 的作用？

**A**:
- **MCache**: 每个 P 的本地缓存，避免锁竞争
- **MSpan**: 连续内存块，管理页分配
- **MHeap**: 全局内存堆，管理所有 span
- 分配路径：MCache → MSpan → MHeap → OS

---

## 第五部分：生产实践

### 1. 调度器调优

```
调度器调优要点：
1. GOMAXPROCS = CPU 核心数（默认自动）
2. 避免大量 goroutine 阻塞（chan/lock）
3. 使用 sync.Pool 复用对象
4. 监控 goroutine 数量（runtime.NumGoroutine）
```

### 2. 内存优化

```
内存优化要点：
1. 使用对象池（sync.Pool）
2. 避免大对象（> 32KB 不走 MCache）
3. 减少 GC 压力（降低对象分配率）
4. 监控 heap 使用（runtime.MemStats）
```

### 3. GC 调优

```
GC 调优要点：
1. GOGC=100（默认），可适当调高
2. 监控 GC 停顿时间（trace）
3. 减少指针数量（降低 GC 扫描时间）
4. 使用 []byte 替代 string（减少拷贝）
```
