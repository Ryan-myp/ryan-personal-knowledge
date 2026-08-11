# Go Runtime 调度器深度解析

> 深入 Go Runtime：GMP模型、调度器、GC、内存分配器。
> 源码级分析，包含性能调优实践。
> 适用对象：Go工程师、系统工程师

---

## 1. GMP 调度模型

### 1.1 核心组件

```
GMP 调度模型：

┌─────────────────────────────────────────────────────────────┐
│                      GMP 模型                               │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  G (Goroutine)                                              │
│  ├── 用户代码执行单元                                        │
│  ├── 大小固定 (2KB)                                         │
│  └── 可抢占式调度                                            │
│                                                             │
│  M (Machine)                                                │
│  ├── 操作系统线程                                            │
│  ├── 执行 Goroutine                                          │
│  └── 持有 P                                                   │
│                                                             │
│  P (Processor)                                              │
│  ├── 调度器上下文                                            │
│  ├── 本地队列 (256个G)                                       │
│  ├── 工作窃取                                                │
│  └── 最大数量 = GOMAXPROCS                                   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 Go 实现 GMP 核心

```go
// gmp_scheduler.go

package runtime

import (
    "sync"
    "sync/atomic"
)

type G struct {
    stack       stack
    fn          func()
    status      uint32
    next        *G
    preempt     bool
}

type M struct {
    g0       *G           // 系统Goroutine
    p        *P           // 绑定的P
    nextp    atomic.Pointer[P]
    id       int32
    stack    stack
}

type P struct {
    id          int32
    status      uint32
    m           atomic.Pointer[M]    // 绑定的M
    gsched      *G                   // 调度G队列
    runqhead    uint32               // 队列头
    runqtail    uint32               // 队列尾
    runqsize    int32                // 队列大小
    freelist    *iface               // 空闲G对象池
    gcdesc      [1024]*GDesc         // G描述符缓存
}

type Scheduler struct {
    np         int32                // P的数量
    pmCount    int32                // M的数量
    runq       []*G                 // 全局队列
    runqsize   int32                // 全局队列大小
    stop         bool
    mu         sync.Mutex
}

func NewScheduler(maxProcs int) *Scheduler {
    s := &Scheduler{
        np: int32(maxProcs),
    }
    s.start()
    return s
}

func (s *Scheduler) start() {
    // 创建P
    for i := 0; i < int(s.np); i++ {
        p := &P{id: int32(i)}
        s.createM(p)
    }
}

func (s *Scheduler) createM(p *P) {
    m := &M{p: p, id: atomic.AddInt32(&s.pmCount, 1)}
    p.m.Store(m)
    
    // 启动M线程
    go m.run()
}

func (m *M) run() {
    for {
        // 从本地队列获取G
        g := m.pollLocalRunq()
        if g != nil {
            m.execute(g)
            continue
        }
        
        // 工作窃取
        g = m.steal()
        if g != nil {
            m.execute(g)
            continue
        }
        
        // 从全局队列获取
        g = m.pollGlobalRunq()
        if g != nil {
            m.execute(g)
            continue
        }
        
        // 阻塞等待
        m.stopTheWorld()
    }
}
```

---

## 2. 内存分配器

### 2.1 分层架构

```
内存分配器架构：

┌─────────────────────────────────────────────────────────────┐
│                    内存分配器                                │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  mcache (每P缓存)                                            │
│  ├── 小对象缓存 ( < 32KB)                                   │
│  ├── 大对象缓存 (32KB - 1MB)                                │
│  └── 超大对象缓存 (> 1MB)                                   │
│                                                             │
│  mcentral (中央缓存)                                         │
│  ├── 管理相同大小的对象                                      │
│  └── 向 mheap 申请/归还                                      │
│                                                             │
│  mheap (堆)                                                  │
│  ├── 管理大块内存                                            │
│  └── 分配给 mcentral                                         │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 Go 实现内存分配

```go
// malloc.go

package runtime

import (
    "unsafe"
)

type mcache struct {
    local [numSpanClasses]*mspan
    large  [maxLargeSize]unsafe.Pointer  // 大对象缓存
}

type mcentral struct {
    spans    []*mspan                      // 管理的所有span
    nonempty [2]list                       // 有空闲对象的span列表
    empty    [2]list                       // 无空闲对象的span列表
}

type mheap struct {
    locks    mutex
    spans    []*mspan                      // 所有span
    free     [numSpanClasses]list          // 空闲span
    inuse    [numSpanClasses]uintptr       // 已使用大小
}

type allocator struct {
    mcache  unsafe.Pointer                // 每P的缓存
    mcentral mcentral                     // 中央缓存
    mheap   mheap                         // 堆
}

func (a *allocator) Malloc(size uintptr) unsafe.Pointer {
    // 1. 获取当前P的mcache
    mc := a.getMcache()
    
    // 2. 根据大小选择分配路径
    if size <= maxSmallSize {
        // 小对象：从mcache分配
        return a.allocSmall(mc, size)
    } else if size <= maxLargeSize {
        // 大对象：从mcentral分配
        return a.allocLarge(mc, size)
    } else {
        // 超大对象：直接从堆分配
        return a.allocHuge(size)
    }
}

func (a *allocator) allocSmall(mc *mcache, size uintptr) unsafe.Pointer {
    // 计算span class
    class := sizeToClass(size)
    
    // 从mcache获取span
    span := mc.local[class]
    if span == nil || span.allocCount >= span.nelems {
        // 从mcentral获取新span
        span = a.mcentral.growSpan(class)
        mc.local[class] = span
    }
    
    // 分配对象
    obj := span.alloc()
    span.allocCount++
    
    return unsafe.Pointer(obj)
}
```

---

## 3. GC 垃圾回收

### 3.1 GC 阶段

```
Go GC 阶段：

1. 标记阶段 (Mark)
   ├── 根对象标记
   ├── 遍历对象图
   └── 三色标记法

2.  Sweeping 阶段
    ├── 回收死对象
    └── 归还内存

3.  后台GC
    ├── 与用户代码并发执行
    └── STW (Stop The World) 短暂暂停
```

### 3.2 Go 实现 GC

```go
// gc.go

package runtime

type GC struct {
    state      gcState
    markWorkers uint32
    assistWork  int64
    flushWork   int64
}

type gcState int

const (
    gcFree gcState = iota
    gcmark
    gcscan
    gcflush
)

type GCWorker struct {
    id       uint32
    marked   uintptr
    scanned  uintptr
}

func (gc *GC) Start() {
    // 1. STW: 停止所有G
    gc.stopTheWorld()
    
    // 2. 重置GC状态
    gc.reset()
    
    // 3. 启动标记工作协程
    gc.startMarkWorkers()
    
    // 4. 开始标记
    gc.markRoots()
    
    // 5. 标记结束
    gc.endMark()
    
    // 6. 扫描阶段
    gc.scan()
    
    // 7. 刷新阶段
    gc.flush()
    
    // 8. 恢复所有G
    gc.restartTheWorld()
}

func (gc *GC) markRoots() {
    // 标记根对象
    roots := gc.getRoots()
    for _, root := range roots {
        gc.markObject(root)
    }
}

func (gc *GC) markObject(obj interface{}) {
    // 三色标记
    // 白色 -> 灰色 -> 黑色
    // ...[truncated]