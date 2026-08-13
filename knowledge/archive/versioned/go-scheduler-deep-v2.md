# Go 调度器深度解析

> 深入Go调度器：GMP模型、调度器、内存分配器、GC。
> 源码级分析，包含性能调优实践。
> 适用对象：Go工程师、系统工程师

---

## 1. GMP 调度模型

### 1.1 核心组件

```
GMP 调度模型：

├── G (Goroutine)
│   ├── 协程栈
│   ├── 执行状态
│   └── 调度信息
│
├── M (Machine)
│   ├── 操作系统线程
│   ├── 执行状态
│   └── P 引用
│
├── P (Processor)
│   ├── 本地runq
│   ├── 全局runq
│   ├── 工作窃取
│   └── 网络轮询
│
└── 调度器
    ├── 全局队列
    └── 调度循环
```

### 1.2 Go 实现 GMP

```go
// gmp_scheduler.go

package scheduler

type G struct {
    stack       stack
    sched       gsched
    fn          func()
    status      uint32
    pred        *G
    succ        *G
}

type M struct {
    g0      *G
    p       puintptr
    nextp   puintptr
    id      int32
    status  uint32
}

type P struct {
    id          int32
    status      uint32
    link        P
    schedtick   uint32
    suittick    uint32
    ldlib       int32
    ticksevent  uint32
    runqhead    guintptr
    runqtail    guintptr
    runq      [256]guintptr
    runqsize  int32
    gcing     bool
    gcscavenge bool
    gcphase   int32
    deferpool   [5]*_defer
    deferpoolbuf [5]*_defer
}

type Scheduler struct {
    allp      []*P
    npidle    uint32
    ngsys     uint32
    stopwait  uint32
    sysmonlock mutex
    releaseAllLock mutex
    deferpoolmu mutex
    deferpool [5]*_defer
    gcworkbufs [4]uintptr
}
```

---

## 2. 调度器源码解析

### 2.1 调度循环

```
调度循环流程：

1. findrunnable()
   ├── 本地队列取G
   ├── 全局队列取G
   ├── 工作窃取
   └── 阻塞网络IO

2. goready()
   ├── 设置G状态
   ├── 入队
   └── 唤醒M

3. gosched()
   ├── 当前G入队
   └── 切换执行
```

### 2.2 Go 实现调度器

```go
// scheduler_impl.go

package scheduler

import (
    "runtime"
    "unsafe"
)

func findrunnable() (gp *G, inheritTime bool) {
    _g_ := getg()
    _p_ := _g_.m.p.ptr()
    
    // 1. 本地队列
    if !runqempty(_p_) {
        gp = runqget(_p_)
        if gp != nil {
            ready(gp, true)
            return gp, false
        }
    }
    
    // 2. 全局队列
    if sched.negs > 0 {
        gp = globrunqget(_p_, 256)
        if gp != nil {
            ready(gp, true)
            return gp, false
        }
    }
    
    // 3. 工作窃取
    for i := 0; i < 4; i++ {
        offset := int(_p_.id+uint32(i+1)) % uint32(len(allp))
        _p := allp[offset]
        gp = runqsteal(_p_, _p, false)
        if gp != nil {
            ready(gp, true)
            return gp, false
        }
    }
    
    // 4. 网络轮询
    netpollWaiters++
    gp = netpoll(true)
    netpollWaiters--
    
    return gp, false
}
```

---

## 3. 内存分配器

### 3.1 mcache/mspan 结构

```
内存分配层级：

┌─────────────────────────────────────────────────────────────┐
│                     Mheap                                    │
│  ├── 大对象 (>32KB)                                        │
│  └── 物理内存管理                                          │
├─────────────────────────────────────────────────────────────┤
│                     Mcentral                                 │
│  ├── 大小为 2^x 的对象                                      │
│  └── 从 Mheap 获取 span                                    │
├─────────────────────────────────────────────────────────────┤
│                     Mcache                                   │
│  ├── 每P私有                                               │
│  └── 快速分配小对象 (<32KB)                                 │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 Go 实现内存分配

```go
// allocator.go

package scheduler

type mheap struct {
    lock      mutex
    pages     pagemap
    free      [numSpanClasses]freeList
    allocated uint64
}

type mcentral struct {
    lock      mutex
    spans     []*mspan
    nonempty  uint32
    full      uint32
}

type mcache struct {
    small [numSpanClasses]*mspan
    large [numSpanClasses]*mspan
    refreshes int32
}

type mspan struct {
    next      *mspan
    prev      *mspan
    startAddr uintptr
    npages    uintptr
    shape     spanClass
    state     spanState
    allocbits   bitvector
    freespan    bool
}

func (c *mcache) alloc(size uintptr, typ *_type) unsafe.Pointer {
    if size <= maxSmallSize {
        sc := sizeclass(size)
        sp := c.small[sc]
        if sp == nil || sp.base() == 0 {
            sp = c.refill(sc, size)
        }
        return sp.alloc(size)
    }
    return c.largeAlloc(size, typ)
}
```

---

## 4. 总结

### 4.1 核心原理回顾

| 组件 | 作用 |
|------|------|
| G | 协程控制块 |
| M | 操作系统线程 |
| P | 处理器，维护runq |
| 调度器 | 全局调度 |

### 4.2 最佳实践

- [ ] 合理设置GOMAXPROCS
- [ ] 避免Goroutine泄漏
- [ ] 使用对象池减少分配
- [ ] 监控调度延迟

---

*最后更新：2026-08-12*
*作者：Ryan*
